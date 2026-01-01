// Team Agent Configuration Panel
// Детальная настройка каждого агента в команде (как в обычном режиме)

import React, { useState } from 'react';
import {
  Settings, Brain, Code, Database, MessageSquare,
  ChevronDown, ChevronUp, Sliders, Zap, Shield,
  Eye, EyeOff, Copy, RotateCcw, Save
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface AgentConfig {
  // Basic info
  id: string;
  role: string;
  name: string;
  
  // System prompt
  system_prompt: string;
  custom_instructions?: string;
  
  // Model config
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
// AGENT CONFIG PANEL - Main component
// ============================================================================

const TeamAgentConfig: React.FC<{
  agent: AgentConfig;
  onChange: (updates: Partial<AgentConfig>) => void;
  allAgents: AgentConfig[]; // For dependency selection
}> = ({ agent, onChange, allAgents }) => {
  const [expandedSections, setExpandedSections] = useState({
    basic: true,
    prompt: false,
    model: false,
    mcp: false,
    advanced: false,
    team: false
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  return (
    <div className="team-agent-config space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg">
        <div className="flex items-center space-x-3">
          <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold text-xl">
            {agent.name[0]}
          </div>
          <div>
            <h3 className="font-bold text-lg">{agent.name}</h3>
            <p className="text-sm text-gray-600">Role: {agent.role}</p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button className="p-2 hover:bg-white rounded">
            <Copy className="w-4 h-4 text-gray-600" />
          </button>
          <button className="p-2 hover:bg-white rounded">
            <RotateCcw className="w-4 h-4 text-gray-600" />
          </button>
        </div>
      </div>

      {/* 1. BASIC INFO */}
      <ConfigSection
        title="Basic Information"
        icon={<MessageSquare className="w-5 h-5" />}
        expanded={expandedSections.basic}
        onToggle={() => toggleSection('basic')}
      >
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium mb-1">Agent Name</label>
              <input
                type="text"
                value={agent.name}
                onChange={(e) => onChange({ name: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
                placeholder="e.g., Frontend Developer"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Role</label>
              <input
                type="text"
                value={agent.role}
                onChange={(e) => onChange({ role: e.target.value })}
                className="w-full px-3 py-2 border rounded-lg"
                placeholder="e.g., frontend"
              />
            </div>
          </div>
        </div>
      </ConfigSection>

      {/* 2. SYSTEM PROMPT */}
      <ConfigSection
        title="System Prompt & Instructions"
        icon={<Brain className="w-5 h-5" />}
        expanded={expandedSections.prompt}
        onToggle={() => toggleSection('prompt')}
      >
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium mb-1">
              System Prompt
              <span className="text-xs text-gray-500 ml-2">
                (Defines agent's role and behavior)
              </span>
            </label>
            <textarea
              value={agent.system_prompt}
              onChange={(e) => onChange({ system_prompt: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg font-mono text-sm"
              rows={8}
              placeholder="You are a senior frontend developer specializing in React and TypeScript..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Custom Instructions
              <span className="text-xs text-gray-500 ml-2">(Optional)</span>
            </label>
            <textarea
              value={agent.custom_instructions || ''}
              onChange={(e) => onChange({ custom_instructions: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg font-mono text-sm"
              rows={4}
              placeholder="Additional instructions, preferences, or constraints..."
            />
          </div>

          {/* Prompt templates */}
          <div>
            <label className="block text-sm font-medium mb-2">Quick Templates</label>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => onChange({
                  system_prompt: `You are a senior ${agent.role} developer.

Your responsibilities:
- Write clean, maintainable code
- Follow best practices and patterns
- Consider performance and scalability
- Collaborate with team members

When working on tasks:
1. Understand requirements thoroughly
2. Plan your approach
3. Implement step by step
4. Test your work
5. Document important decisions`
                })}
                className="px-3 py-2 text-sm border rounded hover:bg-gray-50"
              >
                🎯 Professional
              </button>
              <button
                onClick={() => onChange({
                  system_prompt: `You are an expert ${agent.role}.

Focus on:
- Code quality and best practices
- Performance optimization
- Security considerations
- Team collaboration`
                })}
                className="px-3 py-2 text-sm border rounded hover:bg-gray-50"
              >
                ⚡ Concise
              </button>
            </div>
          </div>
        </div>
      </ConfigSection>

      {/* 3. MODEL CONFIGURATION */}
      <ConfigSection
        title="Model Configuration"
        icon={<Zap className="w-5 h-5" />}
        expanded={expandedSections.model}
        onToggle={() => toggleSection('model')}
      >
        <div className="space-y-4">
          {/* Model Selection */}
          <div>
            <label className="block text-sm font-medium mb-1">Model</label>
            <select
              value={agent.model}
              onChange={(e) => onChange({ model: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg"
            >
              <optgroup label="Claude (Anthropic)">
                <option value="claude-opus-4">Claude Opus 4 (Most capable)</option>
                <option value="claude-sonnet-4">Claude Sonnet 4 (Balanced)</option>
                <option value="claude-haiku-4">Claude Haiku 4 (Fast & efficient)</option>
              </optgroup>
              <optgroup label="GPT (OpenAI)">
                <option value="gpt-4o">GPT-4o (Advanced)</option>
                <option value="gpt-4o-mini">GPT-4o Mini (Fast)</option>
                <option value="o1">o1 (Reasoning)</option>
              </optgroup>
              <optgroup label="Local">
                <option value="llama3:70b">Llama 3 70B (Free)</option>
                <option value="deepseek-coder">DeepSeek Coder (Free)</option>
              </optgroup>
            </select>
          </div>

          {/* Temperature */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium">
                Temperature
                <span className="text-xs text-gray-500 ml-2">
                  (Creativity vs Precision)
                </span>
              </label>
              <span className="text-sm font-mono bg-gray-100 px-2 py-1 rounded">
                {agent.temperature.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={agent.temperature}
              onChange={(e) => onChange({ temperature: parseFloat(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0.0 (Focused)</span>
              <span>1.0 (Creative)</span>
            </div>
          </div>

          {/* Max Tokens */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium">Max Tokens</label>
              <span className="text-sm font-mono bg-gray-100 px-2 py-1 rounded">
                {agent.max_tokens}
              </span>
            </div>
            <input
              type="range"
              min="1000"
              max="8000"
              step="100"
              value={agent.max_tokens}
              onChange={(e) => onChange({ max_tokens: parseInt(e.target.value) })}
              className="w-full"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>1k (Short)</span>
              <span>8k (Long)</span>
            </div>
          </div>

          {/* Top P */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm font-medium">
                Top P
                <span className="text-xs text-gray-500 ml-2">
                  (Nucleus sampling)
                </span>
              </label>
              <span className="text-sm font-mono bg-gray-100 px-2 py-1 rounded">
                {agent.top_p.toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={agent.top_p}
              onChange={(e) => onChange({ top_p: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>

          {/* Presets */}
          <div>
            <label className="block text-sm font-medium mb-2">Quick Presets</label>
            <div className="grid grid-cols-3 gap-2">
              <button
                onClick={() => onChange({
                  temperature: 0.3,
                  top_p: 0.9,
                  max_tokens: 4000
                })}
                className="px-3 py-2 text-sm border rounded hover:bg-gray-50"
              >
                🎯 Precise
              </button>
              <button
                onClick={() => onChange({
                  temperature: 0.7,
                  top_p: 0.95,
                  max_tokens: 4000
                })}
                className="px-3 py-2 text-sm border rounded hover:bg-gray-50"
              >
                ⚖️ Balanced
              </button>
              <button
                onClick={() => onChange({
                  temperature: 0.9,
                  top_p: 1.0,
                  max_tokens: 6000
                })}
                className="px-3 py-2 text-sm border rounded hover:bg-gray-50"
              >
                🎨 Creative
              </button>
            </div>
          </div>
        </div>
      </ConfigSection>

      {/* 4. MCP TOOLS */}
      <ConfigSection
        title="MCP Tools"
        icon={<Database className="w-5 h-5" />}
        expanded={expandedSections.mcp}
        onToggle={() => toggleSection('mcp')}
      >
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            Select which MCP tools this agent can use
          </p>

          <div className="space-y-2">
            {[
              { id: 'filesystem', name: 'Filesystem', description: 'Read/write files' },
              { id: 'memory', name: 'Memory', description: 'Store/recall information' },
              { id: 'database', name: 'Database', description: 'Query database' },
              { id: 'web_search', name: 'Web Search', description: 'Search the web' },
              { id: 'code_execution', name: 'Code Execution', description: 'Run code' },
              { id: 'slack', name: 'Slack', description: 'Send messages' },
              { id: 'github', name: 'GitHub', description: 'Git operations' },
              { id: 'google_drive', name: 'Google Drive', description: 'Access files' }
            ].map(tool => (
              <label
                key={tool.id}
                className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={agent.mcp_tools.includes(tool.id)}
                  onChange={(e) => {
                    const tools = e.target.checked
                      ? [...agent.mcp_tools, tool.id]
                      : agent.mcp_tools.filter(t => t !== tool.id);
                    onChange({ mcp_tools: tools });
                  }}
                  className="w-4 h-4"
                />
                <div className="flex-1">
                  <div className="font-medium text-sm">{tool.name}</div>
                  <div className="text-xs text-gray-500">{tool.description}</div>
                </div>
              </label>
            ))}
          </div>
        </div>
      </ConfigSection>

      {/* 5. ADVANCED OPTIONS */}
      <ConfigSection
        title="Advanced Options"
        icon={<Sliders className="w-5 h-5" />}
        expanded={expandedSections.advanced}
        onToggle={() => toggleSection('advanced')}
      >
        <div className="space-y-3">
          <label className="flex items-center justify-between p-3 border rounded-lg">
            <div>
              <div className="font-medium text-sm">Thinking Mode</div>
              <div className="text-xs text-gray-500">
                Show internal reasoning process
              </div>
            </div>
            <select
              value={agent.thinking_mode || 'disabled'}
              onChange={(e) => onChange({ thinking_mode: e.target.value as any })}
              className="px-3 py-1 border rounded text-sm"
            >
              <option value="enabled">Enabled</option>
              <option value="disabled">Disabled</option>
            </select>
          </label>

          <label className="flex items-center justify-between p-3 border rounded-lg">
            <div>
              <div className="font-medium text-sm">Memory</div>
              <div className="text-xs text-gray-500">
                Remember context across conversations
              </div>
            </div>
            <input
              type="checkbox"
              checked={agent.memory_enabled}
              onChange={(e) => onChange({ memory_enabled: e.target.checked })}
              className="w-4 h-4"
            />
          </label>

          <label className="flex items-center justify-between p-3 border rounded-lg">
            <div>
              <div className="font-medium text-sm">Auto-save Context</div>
              <div className="text-xs text-gray-500">
                Automatically save work to shared context
              </div>
            </div>
            <input
              type="checkbox"
              checked={agent.auto_save_context}
              onChange={(e) => onChange({ auto_save_context: e.target.checked })}
              className="w-4 h-4"
            />
          </label>
        </div>
      </ConfigSection>

      {/* 6. TEAM-SPECIFIC */}
      <ConfigSection
        title="Team Configuration"
        icon={<Users className="w-5 h-5" />}
        expanded={expandedSections.team}
        onToggle={() => toggleSection('team')}
      >
        <div className="space-y-4">
          {/* Priority */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Execution Priority
              <span className="text-xs text-gray-500 ml-2">
                (Lower = executes first)
              </span>
            </label>
            <input
              type="number"
              min="0"
              value={agent.priority}
              onChange={(e) => onChange({ priority: parseInt(e.target.value) })}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>

          {/* Dependencies */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Dependencies
              <span className="text-xs text-gray-500 ml-2">
                (Waits for these outputs before starting)
              </span>
            </label>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {allAgents
                .filter(a => a.id !== agent.id)
                .map(otherAgent => (
                  otherAgent.outputs.map(output => (
                    <label
                      key={`${otherAgent.id}-${output}`}
                      className="flex items-center space-x-2 p-2 border rounded hover:bg-gray-50"
                    >
                      <input
                        type="checkbox"
                        checked={agent.dependencies.includes(output)}
                        onChange={(e) => {
                          const deps = e.target.checked
                            ? [...agent.dependencies, output]
                            : agent.dependencies.filter(d => d !== output);
                          onChange({ dependencies: deps });
                        }}
                        className="w-4 h-4"
                      />
                      <span className="text-sm">
                        <span className="font-medium">{otherAgent.name}</span>
                        {' → '}
                        <span className="text-gray-600">{output}</span>
                      </span>
                    </label>
                  ))
                ))
              }
            </div>
          </div>

          {/* Outputs */}
          <div>
            <label className="block text-sm font-medium mb-1">
              Outputs
              <span className="text-xs text-gray-500 ml-2">
                (What this agent produces)
              </span>
            </label>
            <div className="space-y-2">
              {agent.outputs.map((output, index) => (
                <div key={index} className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={output}
                    onChange={(e) => {
                      const newOutputs = [...agent.outputs];
                      newOutputs[index] = e.target.value;
                      onChange({ outputs: newOutputs });
                    }}
                    className="flex-1 px-3 py-2 border rounded-lg text-sm"
                    placeholder="e.g., frontend_code"
                  />
                  <button
                    onClick={() => {
                      const newOutputs = agent.outputs.filter((_, i) => i !== index);
                      onChange({ outputs: newOutputs });
                    }}
                    className="p-2 text-red-600 hover:bg-red-50 rounded"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                onClick={() => onChange({ outputs: [...agent.outputs, ''] })}
                className="w-full px-3 py-2 border border-dashed rounded-lg hover:bg-gray-50 text-sm"
              >
                + Add Output
              </button>
            </div>
          </div>
        </div>
      </ConfigSection>

      {/* Save Button */}
      <div className="flex items-center justify-end space-x-2 pt-4 border-t">
        <button className="px-4 py-2 border rounded-lg hover:bg-gray-50">
          Reset to Defaults
        </button>
        <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center space-x-2">
          <Save className="w-4 h-4" />
          <span>Save Configuration</span>
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// CONFIG SECTION - Collapsible section component
// ============================================================================

const ConfigSection: React.FC<{
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}> = ({ title, icon, expanded, onToggle, children }) => {
  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 hover:bg-gray-50"
      >
        <div className="flex items-center space-x-2">
          <div className="text-blue-600">{icon}</div>
          <span className="font-semibold">{title}</span>
        </div>
        {expanded ? (
          <ChevronUp className="w-5 h-5 text-gray-400" />
        ) : (
          <ChevronDown className="w-5 h-5 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="p-4 border-t bg-gray-50">
          {children}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// EXAMPLE USAGE
// ============================================================================

const ExampleUsage = () => {
  const [agent, setAgent] = useState<AgentConfig>({
    id: 'agent_1',
    role: 'frontend',
    name: 'Frontend Developer',
    system_prompt: 'You are a senior frontend developer...',
    model: 'claude-sonnet-4',
    temperature: 0.7,
    max_tokens: 4000,
    top_p: 0.95,
    mcp_tools: ['filesystem', 'memory'],
    memory_enabled: true,
    auto_save_context: true,
    dependencies: ['architecture'],
    outputs: ['frontend_code'],
    priority: 1
  });

  const allAgents = [
    agent,
    // ... other agents
  ];

  return (
    <TeamAgentConfig
      agent={agent}
      onChange={(updates) => setAgent({ ...agent, ...updates })}
      allAgents={allAgents}
    />
  );
};

export default TeamAgentConfig;
export { ConfigSection };
