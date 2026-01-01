// AgentRolesList - Interactive agent list with full customization
// Split panel: Left = agent cards, Right = config panel

import React, { useState, useRef, useEffect } from 'react';
import {
  Settings, Plus, Trash2, Copy, Edit2, Check, X,
  GripVertical, ChevronRight, Users, Cpu, Database,
  MessageSquare, MoreVertical
} from 'lucide-react';

// Import the config panel
import TeamAgentConfig from './TeamAgentConfig';

// ============================================================================
// TYPES
// ============================================================================

interface AgentRole {
  id: string;
  name: string;
  role: string;
  description: string;
  color: string;

  // Configuration (same as TeamAgentConfig)
  system_prompt: string;
  custom_instructions?: string;
  model: string;
  temperature: number;
  max_tokens: number;
  top_p: number;

  // MCP tools
  mcp_tools: string[];

  // Advanced
  thinking_mode?: 'enabled' | 'disabled';
  memory_enabled: boolean;
  auto_save_context: boolean;

  // Team specific
  dependencies: string[];
  outputs: string[];
  priority: number;
}

// ============================================================================
// DEFAULT AGENTS
// ============================================================================

const DEFAULT_AGENTS: AgentRole[] = [
  {
    id: 'architect',
    name: 'Architect',
    role: 'architect',
    description: 'System design & API planning',
    color: '#8B5CF6',
    system_prompt: `You are a senior system architect.

Your responsibilities:
- Design system architecture
- Define API contracts
- Plan database schemas
- Consider scalability and security
- Create technical specifications`,
    model: 'claude-opus-4',
    temperature: 0.5,
    max_tokens: 6000,
    top_p: 0.95,
    mcp_tools: ['memory', 'filesystem'],
    memory_enabled: true,
    auto_save_context: true,
    dependencies: [],
    outputs: ['architecture', 'api_design'],
    priority: 0
  },
  {
    id: 'backend',
    name: 'Backend',
    role: 'backend',
    description: 'Server-side logic & APIs',
    color: '#10B981',
    system_prompt: `You are a senior backend developer.

Stack:
- FastAPI (async Python)
- PostgreSQL, Redis
- Docker, Kubernetes

Focus on:
- Clean, maintainable code
- Performance optimization
- Security best practices
- Comprehensive error handling`,
    model: 'claude-sonnet-4',
    temperature: 0.7,
    max_tokens: 4000,
    top_p: 0.95,
    mcp_tools: ['memory', 'filesystem', 'database'],
    memory_enabled: true,
    auto_save_context: true,
    dependencies: ['architecture'],
    outputs: ['backend_code', 'api_endpoints'],
    priority: 1
  },
  {
    id: 'frontend',
    name: 'Frontend',
    role: 'frontend',
    description: 'React/TypeScript UI',
    color: '#0EA5E9',
    system_prompt: `You are a senior frontend developer.

Stack:
- React 18 with TypeScript
- Tailwind CSS
- Zustand/React Query

Focus on:
- Clean component architecture
- Responsive design
- Accessibility
- Performance optimization`,
    model: 'claude-sonnet-4',
    temperature: 0.7,
    max_tokens: 4000,
    top_p: 0.95,
    mcp_tools: ['memory', 'filesystem'],
    memory_enabled: true,
    auto_save_context: true,
    dependencies: ['architecture', 'api_design'],
    outputs: ['frontend_code', 'components'],
    priority: 1
  },
  {
    id: 'telegram',
    name: 'Telegram Bot',
    role: 'telegram',
    description: 'Bot handlers & commands',
    color: '#0088CC',
    system_prompt: `You are a Telegram bot developer.

Framework: aiogram (async Python)

Focus on:
- User-friendly interface
- Command handlers
- Inline keyboards
- Payment integration
- Error handling`,
    model: 'claude-sonnet-4',
    temperature: 0.7,
    max_tokens: 4000,
    top_p: 0.95,
    mcp_tools: ['memory', 'filesystem'],
    memory_enabled: true,
    auto_save_context: true,
    dependencies: ['architecture', 'api_design'],
    outputs: ['telegram_bot', 'bot_handlers'],
    priority: 1
  },
  {
    id: 'qa',
    name: 'QA Engineer',
    role: 'qa',
    description: 'Testing & quality assurance',
    color: '#F59E0B',
    system_prompt: `You are a QA engineer.

Focus on:
- Unit tests (pytest, jest)
- Integration tests
- E2E tests (Playwright)
- Test coverage
- Bug detection`,
    model: 'claude-sonnet-4',
    temperature: 0.5,
    max_tokens: 4000,
    top_p: 0.95,
    mcp_tools: ['memory', 'filesystem', 'code_execution'],
    memory_enabled: true,
    auto_save_context: true,
    dependencies: ['backend_code', 'frontend_code'],
    outputs: ['test_suite', 'qa_report'],
    priority: 2
  }
];

// ============================================================================
// AGENT CARD COMPONENT
// ============================================================================

interface AgentCardProps {
  agent: AgentRole;
  isSelected: boolean;
  isEditing: boolean;
  onSelect: () => void;
  onRename: (newName: string) => void;
  onDelete: () => void;
  onDuplicate: () => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
}

const AgentCard: React.FC<AgentCardProps> = ({
  agent,
  isSelected,
  isEditing,
  onSelect,
  onRename,
  onDelete,
  onDuplicate,
  onStartEdit,
  onCancelEdit
}) => {
  const [editName, setEditName] = useState(agent.name);
  const [showMenu, setShowMenu] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isEditing]);

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSaveEdit = () => {
    if (editName.trim()) {
      onRename(editName.trim());
    }
    onCancelEdit();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSaveEdit();
    } else if (e.key === 'Escape') {
      setEditName(agent.name);
      onCancelEdit();
    }
  };

  return (
    <div
      onClick={onSelect}
      className={`
        relative p-4 border-l-4 rounded-lg cursor-pointer transition-all
        ${isSelected
          ? 'bg-blue-50 border-blue-500 shadow-md'
          : 'bg-white hover:bg-gray-50 border-gray-200'
        }
      `}
      style={{ borderLeftColor: isSelected ? undefined : agent.color }}
    >
      {/* Drag handle */}
      <div className="absolute left-1 top-1/2 -translate-y-1/2 text-gray-300 cursor-grab">
        <GripVertical className="w-4 h-4" />
      </div>

      <div className="ml-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          {isEditing ? (
            <div className="flex items-center space-x-2 flex-1">
              <input
                ref={inputRef}
                type="text"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                onKeyDown={handleKeyDown}
                className="flex-1 px-2 py-1 border rounded text-sm font-semibold"
                onClick={(e) => e.stopPropagation()}
              />
              <button
                onClick={(e) => { e.stopPropagation(); handleSaveEdit(); }}
                className="p-1 text-green-600 hover:bg-green-50 rounded"
              >
                <Check className="w-4 h-4" />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); setEditName(agent.name); onCancelEdit(); }}
                className="p-1 text-gray-400 hover:bg-gray-100 rounded"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <>
              <h4 className="font-semibold text-gray-800">{agent.name}</h4>

              {/* Actions menu */}
              <div className="relative" ref={menuRef}>
                <button
                  onClick={(e) => { e.stopPropagation(); setShowMenu(!showMenu); }}
                  className="p-1 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded"
                >
                  <MoreVertical className="w-4 h-4" />
                </button>

                {showMenu && (
                  <div className="absolute right-0 top-full mt-1 bg-white border rounded-lg shadow-lg py-1 z-10 min-w-[140px]">
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowMenu(false); onStartEdit(); }}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center space-x-2"
                    >
                      <Edit2 className="w-4 h-4" />
                      <span>Rename</span>
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowMenu(false); onDuplicate(); }}
                      className="w-full px-3 py-2 text-left text-sm hover:bg-gray-50 flex items-center space-x-2"
                    >
                      <Copy className="w-4 h-4" />
                      <span>Duplicate</span>
                    </button>
                    <hr className="my-1" />
                    <button
                      onClick={(e) => { e.stopPropagation(); setShowMenu(false); onDelete(); }}
                      className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
                    >
                      <Trash2 className="w-4 h-4" />
                      <span>Delete</span>
                    </button>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Description */}
        <p className="text-sm text-gray-500 mt-1">{agent.description}</p>

        {/* Tags */}
        <div className="flex flex-wrap gap-1 mt-2">
          {agent.mcp_tools.slice(0, 3).map(tool => (
            <span
              key={tool}
              className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded"
            >
              {tool}
            </span>
          ))}
          {agent.mcp_tools.length > 3 && (
            <span className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
              +{agent.mcp_tools.length - 3}
            </span>
          )}
        </div>

        {/* Model badge */}
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-gray-400">{agent.model}</span>
          {isSelected && (
            <ChevronRight className="w-4 h-4 text-blue-500" />
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const AgentRolesList: React.FC = () => {
  const [agents, setAgents] = useState<AgentRole[]>(DEFAULT_AGENTS);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [editingAgentId, setEditingAgentId] = useState<string | null>(null);

  const selectedAgent = agents.find(a => a.id === selectedAgentId);

  // Add new agent
  const handleAddAgent = () => {
    const newAgent: AgentRole = {
      id: `agent_${Date.now()}`,
      name: 'New Agent',
      role: 'custom',
      description: 'Custom agent',
      color: '#6366F1',
      system_prompt: 'You are a helpful assistant.',
      model: 'claude-sonnet-4',
      temperature: 0.7,
      max_tokens: 4000,
      top_p: 0.95,
      mcp_tools: ['memory', 'filesystem'],
      memory_enabled: true,
      auto_save_context: true,
      dependencies: [],
      outputs: [],
      priority: agents.length
    };
    setAgents([...agents, newAgent]);
    setSelectedAgentId(newAgent.id);
    setEditingAgentId(newAgent.id);
  };

  // Delete agent
  const handleDeleteAgent = (id: string) => {
    if (confirm('Delete this agent?')) {
      setAgents(agents.filter(a => a.id !== id));
      if (selectedAgentId === id) {
        setSelectedAgentId(null);
      }
    }
  };

  // Duplicate agent
  const handleDuplicateAgent = (agent: AgentRole) => {
    const newAgent: AgentRole = {
      ...agent,
      id: `${agent.id}_copy_${Date.now()}`,
      name: `${agent.name} (Copy)`
    };
    setAgents([...agents, newAgent]);
    setSelectedAgentId(newAgent.id);
  };

  // Rename agent
  const handleRenameAgent = (id: string, newName: string) => {
    setAgents(agents.map(a =>
      a.id === id ? { ...a, name: newName } : a
    ));
  };

  // Update agent config
  const handleUpdateAgent = (updates: Partial<AgentRole>) => {
    if (!selectedAgentId) return;
    setAgents(agents.map(a =>
      a.id === selectedAgentId ? { ...a, ...updates } : a
    ));
  };

  return (
    <div className="h-full flex bg-gray-100">
      {/* LEFT PANEL - Agent List */}
      <div className="w-80 bg-white border-r flex flex-col">
        {/* Header */}
        <div className="p-4 border-b flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Users className="w-5 h-5 text-gray-600" />
            <h3 className="font-semibold">Agent Roles</h3>
          </div>
          <button
            onClick={handleAddAgent}
            className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg"
            title="Add Agent"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>

        {/* Agent List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {agents.map(agent => (
            <AgentCard
              key={agent.id}
              agent={agent}
              isSelected={selectedAgentId === agent.id}
              isEditing={editingAgentId === agent.id}
              onSelect={() => setSelectedAgentId(agent.id)}
              onRename={(name) => handleRenameAgent(agent.id, name)}
              onDelete={() => handleDeleteAgent(agent.id)}
              onDuplicate={() => handleDuplicateAgent(agent)}
              onStartEdit={() => setEditingAgentId(agent.id)}
              onCancelEdit={() => setEditingAgentId(null)}
            />
          ))}
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-gray-50">
          <div className="text-sm text-gray-500 text-center">
            {agents.length} agents configured
          </div>
        </div>
      </div>

      {/* RIGHT PANEL - Config */}
      <div className="flex-1 overflow-y-auto p-6">
        {selectedAgent ? (
          <div className="max-w-2xl mx-auto">
            <TeamAgentConfig
              agent={selectedAgent}
              onChange={handleUpdateAgent}
              allAgents={agents}
            />
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center text-gray-400">
            <Settings className="w-16 h-16 mb-4 opacity-50" />
            <h3 className="text-lg font-medium">Select an agent</h3>
            <p className="text-sm mt-1">Click on an agent to configure</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default AgentRolesList;
export type { AgentRole };
