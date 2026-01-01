// Team Mode Dashboard - React Components
// src/dashboard/components/TeamMode.tsx

import React, { useState, useEffect } from 'react';
import { 
  Users, Plus, Trash2, Settings, Play, 
  GitBranch, CheckCircle, XCircle, Clock,
  AlertCircle, Brain, Database
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface AgentRole {
  id: string;
  name: string;
  description: string;
  tech_stack: string[];
  system_prompt: string;
  mcp_permissions: string[];
  color: string;
}

interface AgentConfig {
  role: string;
  name?: string;
  tech_stack: string[];
  custom_prompt?: string;
  mcp_servers: string[];
  mcp_tools: string[];
  depends_on: string[];
  max_iterations: number;
  auto_commit: boolean;
}

interface AgentStatus {
  agent_id: string;
  role: string;
  name: string;
  status: 'pending' | 'in_progress' | 'blocked' | 'done' | 'failed';
  worktree_path?: string;
  branch?: string;
  progress: number;
  blockers: string[];
  current_task?: string;
  mcp_tools_used: string[];
  memory_context: Record<string, any>;
}

interface TeamState {
  active: boolean;
  agents: AgentStatus[];
  shared_context: Record<string, any>;
  graph_memory: Record<string, any>;
  conflicts: any[];
  merge_ready: boolean;
}

// ============================================================================
// AGENT CARD COMPONENT
// ============================================================================

const AgentCard: React.FC<{
  agent: AgentStatus;
  onRemove: (id: string) => void;
  onConfigure: (id: string) => void;
}> = ({ agent, onRemove, onConfigure }) => {
  const statusColors = {
    pending: 'bg-gray-500',
    in_progress: 'bg-blue-500',
    blocked: 'bg-yellow-500',
    done: 'bg-green-500',
    failed: 'bg-red-500'
  };

  const statusIcons = {
    pending: <Clock className="w-4 h-4" />,
    in_progress: <Play className="w-4 h-4 animate-pulse" />,
    blocked: <AlertCircle className="w-4 h-4" />,
    done: <CheckCircle className="w-4 h-4" />,
    failed: <XCircle className="w-4 h-4" />
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-4 border-l-4" 
         style={{ borderLeftColor: getAgentColor(agent.role) }}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <Users className="w-5 h-5" style={{ color: getAgentColor(agent.role) }} />
          <div>
            <h3 className="font-semibold">{agent.name || agent.role}</h3>
            <p className="text-xs text-gray-500">{agent.role}</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={() => onConfigure(agent.agent_id)}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <Settings className="w-4 h-4 text-gray-600" />
          </button>
          <button
            onClick={() => onRemove(agent.agent_id)}
            className="p-1 hover:bg-red-50 rounded"
          >
            <Trash2 className="w-4 h-4 text-red-600" />
          </button>
        </div>
      </div>

      {/* Status */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-1">
          <div className="flex items-center space-x-2">
            {statusIcons[agent.status]}
            <span className="capitalize">{agent.status.replace('_', ' ')}</span>
          </div>
          <span className="text-gray-500">{Math.round(agent.progress)}%</span>
        </div>
        
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className={`h-2 rounded-full ${statusColors[agent.status]}`}
            style={{ width: `${agent.progress}%` }}
          />
        </div>
      </div>

      {/* Current Task */}
      {agent.current_task && (
        <div className="mb-3 p-2 bg-gray-50 rounded text-sm">
          <div className="text-gray-600 text-xs mb-1">Current Task:</div>
          <div className="text-gray-800">{agent.current_task}</div>
        </div>
      )}

      {/* Blockers */}
      {agent.blockers.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-yellow-600 mb-1">Blocked by:</div>
          <div className="flex flex-wrap gap-1">
            {agent.blockers.map(blocker => (
              <span key={blocker} className="px-2 py-1 bg-yellow-100 text-yellow-700 rounded text-xs">
                {blocker}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* MCP Tools */}
      {agent.mcp_tools_used.length > 0 && (
        <div className="mb-2">
          <div className="text-xs text-gray-600 mb-1">MCP Tools:</div>
          <div className="flex flex-wrap gap-1">
            {agent.mcp_tools_used.map(tool => (
              <span key={tool} className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs">
                {tool}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Branch */}
      {agent.branch && (
        <div className="flex items-center space-x-2 text-xs text-gray-500">
          <GitBranch className="w-3 h-3" />
          <span>{agent.branch}</span>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// ADD AGENT MODAL
// ============================================================================

const AddAgentModal: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  onAdd: (config: AgentConfig) => void;
  availableRoles: AgentRole[];
}> = ({ isOpen, onClose, onAdd, availableRoles }) => {
  const [selectedRole, setSelectedRole] = useState<string>('');
  const [customName, setCustomName] = useState<string>('');
  const [techStack, setTechStack] = useState<string[]>([]);
  const [mcpServers, setMcpServers] = useState<string[]>(['memory', 'filesystem']);
  const [mcpTools, setMcpTools] = useState<string[]>([]);
  const [dependsOn, setDependsOn] = useState<string[]>([]);

  if (!isOpen) return null;

  const role = availableRoles.find(r => r.id === selectedRole);

  const handleAdd = () => {
    onAdd({
      role: selectedRole,
      name: customName || role?.name,
      tech_stack: techStack.length > 0 ? techStack : role?.tech_stack || [],
      mcp_servers: mcpServers,
      mcp_tools: mcpTools,
      depends_on: dependsOn,
      max_iterations: 10,
      auto_commit: true
    });
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <h2 className="text-2xl font-bold mb-4">Add Agent to Team</h2>

        {/* Role Selection */}
        <div className="mb-4">
          <label className="block text-sm font-medium mb-2">Agent Role</label>
          <select
            value={selectedRole}
            onChange={(e) => setSelectedRole(e.target.value)}
            className="w-full border rounded px-3 py-2"
          >
            <option value="">Select a role...</option>
            {availableRoles.map(role => (
              <option key={role.id} value={role.id}>
                {role.name} - {role.description}
              </option>
            ))}
          </select>
        </div>

        {role && (
          <>
            {/* Custom Name */}
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">
                Custom Name (optional)
              </label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder={role.name}
                className="w-full border rounded px-3 py-2"
              />
            </div>

            {/* Tech Stack */}
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">
                Tech Stack
              </label>
              <div className="flex flex-wrap gap-2 mb-2">
                {(techStack.length > 0 ? techStack : role.tech_stack).map(tech => (
                  <span key={tech} className="px-3 py-1 bg-blue-100 text-blue-700 rounded">
                    {tech}
                  </span>
                ))}
              </div>
              <input
                type="text"
                placeholder="Add technology (press Enter)"
                className="w-full border rounded px-3 py-2"
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.currentTarget.value) {
                    setTechStack([...techStack, e.currentTarget.value]);
                    e.currentTarget.value = '';
                  }
                }}
              />
            </div>

            {/* MCP Servers */}
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">
                MCP Servers
              </label>
              <div className="space-y-2">
                {['memory', 'filesystem', 'git', 'browser', 'code_analysis'].map(server => (
                  <label key={server} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={mcpServers.includes(server)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setMcpServers([...mcpServers, server]);
                        } else {
                          setMcpServers(mcpServers.filter(s => s !== server));
                        }
                      }}
                      className="rounded"
                    />
                    <span className="text-sm">{server}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* MCP Permissions */}
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">
                MCP Permissions
              </label>
              <div className="bg-gray-50 p-3 rounded">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {role.mcp_permissions.map(perm => (
                    <div key={perm} className="flex items-center space-x-2">
                      <CheckCircle className="w-4 h-4 text-green-500" />
                      <span>{perm}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Dependencies */}
            <div className="mb-4">
              <label className="block text-sm font-medium mb-2">
                Dependencies (blocks until these agents complete)
              </label>
              <input
                type="text"
                placeholder="e.g., architect, backend (comma-separated)"
                className="w-full border rounded px-3 py-2"
                onChange={(e) => {
                  const deps = e.target.value.split(',').map(d => d.trim()).filter(Boolean);
                  setDependsOn(deps);
                }}
              />
            </div>
          </>
        )}

        {/* Actions */}
        <div className="flex justify-end space-x-3">
          <button
            onClick={onClose}
            className="px-4 py-2 border rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleAdd}
            disabled={!selectedRole}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          >
            Add Agent
          </button>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// MEMORY GRAPH VISUALIZATION
// ============================================================================

const MemoryGraphView: React.FC<{
  graphData: Record<string, any>;
}> = ({ graphData }) => {
  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="flex items-center space-x-2 mb-4">
        <Brain className="w-5 h-5 text-purple-600" />
        <h3 className="font-semibold">Shared Memory Graph</h3>
      </div>

      <div className="space-y-3">
        {Object.entries(graphData).map(([key, value]) => (
          <div key={key} className="border rounded p-3">
            <div className="font-medium text-sm mb-2">{key}</div>
            <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto">
              {JSON.stringify(value, null, 2)}
            </pre>
          </div>
        ))}
      </div>
    </div>
  );
};

// ============================================================================
// MAIN TEAM MODE COMPONENT
// ============================================================================

const TeamMode: React.FC<{
  projectPath: string;
}> = ({ projectPath }) => {
  const [teamState, setTeamState] = useState<TeamState | null>(null);
  const [availableRoles, setAvailableRoles] = useState<AgentRole[]>([]);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  // Fetch team state
  useEffect(() => {
    const fetchState = async () => {
      try {
        const response = await fetch(`/api/team/status/${encodeURIComponent(projectPath)}`);
        const data = await response.json();
        setTeamState(data);
      } catch (error) {
        console.error('Failed to fetch team state:', error);
      }
    };

    fetchState();
    const interval = setInterval(fetchState, 2000); // Poll every 2s

    return () => clearInterval(interval);
  }, [projectPath]);

  // Fetch available roles
  useEffect(() => {
    const fetchRoles = async () => {
      try {
        const response = await fetch('/api/team/roles');
        const data = await response.json();
        setAvailableRoles(Object.values(data));
      } catch (error) {
        console.error('Failed to fetch roles:', error);
      }
    };

    fetchRoles();
  }, []);

  const handleAddAgent = async (config: AgentConfig) => {
    try {
      await fetch('/api/team/agents/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath, ...config })
      });
      // Refresh state
      const response = await fetch(`/api/team/status/${encodeURIComponent(projectPath)}`);
      const data = await response.json();
      setTeamState(data);
    } catch (error) {
      console.error('Failed to add agent:', error);
    }
  };

  const handleRemoveAgent = async (agentId: string) => {
    if (!confirm('Are you sure you want to remove this agent?')) return;

    try {
      await fetch(`/api/team/agents/${agentId}?project_path=${encodeURIComponent(projectPath)}`, {
        method: 'DELETE'
      });
      // Refresh state
      const response = await fetch(`/api/team/status/${encodeURIComponent(projectPath)}`);
      const data = await response.json();
      setTeamState(data);
    } catch (error) {
      console.error('Failed to remove agent:', error);
    }
  };

  const handleExecute = async () => {
    setIsExecuting(true);
    try {
      await fetch('/api/team/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath })
      });
    } catch (error) {
      console.error('Failed to execute team:', error);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleMerge = async () => {
    try {
      await fetch('/api/team/merge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_path: projectPath })
      });
    } catch (error) {
      console.error('Failed to merge:', error);
    }
  };

  if (!teamState) {
    return <div>Loading team state...</div>;
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">Team Mode</h1>
          <p className="text-gray-600">{projectPath}</p>
        </div>

        <div className="flex items-center space-x-3">
          {teamState.merge_ready && (
            <button
              onClick={handleMerge}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 flex items-center space-x-2"
            >
              <GitBranch className="w-4 h-4" />
              <span>Merge Branches</span>
            </button>
          )}

          <button
            onClick={handleExecute}
            disabled={isExecuting || teamState.agents.length === 0}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 flex items-center space-x-2"
          >
            <Play className="w-4 h-4" />
            <span>{isExecuting ? 'Executing...' : 'Execute Team'}</span>
          </button>

          <button
            onClick={() => setIsAddModalOpen(true)}
            className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 flex items-center space-x-2"
          >
            <Plus className="w-4 h-4" />
            <span>Add Agent</span>
          </button>
        </div>
      </div>

      {/* Agents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {teamState.agents.map(agent => (
          <AgentCard
            key={agent.agent_id}
            agent={agent}
            onRemove={handleRemoveAgent}
            onConfigure={(id) => console.log('Configure', id)}
          />
        ))}

        {teamState.agents.length === 0 && (
          <div className="col-span-3 text-center py-12 text-gray-500">
            <Users className="w-16 h-16 mx-auto mb-4 text-gray-400" />
            <p className="text-lg mb-2">No agents in team</p>
            <p className="text-sm">Click "Add Agent" to create your first team member</p>
          </div>
        )}
      </div>

      {/* Memory Graph */}
      {Object.keys(teamState.graph_memory).length > 0 && (
        <MemoryGraphView graphData={teamState.graph_memory} />
      )}

      {/* Add Agent Modal */}
      <AddAgentModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onAdd={handleAddAgent}
        availableRoles={availableRoles}
      />
    </div>
  );
};

// Helper function
function getAgentColor(role: string): string {
  const colors: Record<string, string> = {
    architect: '#8B5CF6',
    backend: '#10B981',
    frontend: '#F59E0B',
    telegram: '#0EA5E9',
    qa: '#EF4444',
    reviewer: '#EC4899',
    database: '#6366F1',
    security: '#DC2626',
    devops: '#059669'
  };
  return colors[role] || '#3B82F6';
}

export default TeamMode;
