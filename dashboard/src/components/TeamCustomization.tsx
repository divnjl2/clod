// Team Customization UI
// dashboard/src/components/TeamCustomization.tsx

import React, { useState, useEffect } from 'react';
import {
  Users, Plus, Trash2, Save, Download, Upload,
  Settings, Brain, Wrench, Database, Zap,
  ChevronDown, ChevronUp, Copy, Check
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface ModelConfig {
  provider: string;
  model: string;
  auto_select: boolean;
  complexity_mapping?: Record<string, string>;
  temperature: number;
  max_tokens: number;
  budget_limit?: number;
}

interface ReasoningConfig {
  default_pattern: string;
  pattern_by_task?: Record<string, string>;
  min_confidence: number;
  verification_enabled: boolean;
  max_retries: number;
}

interface ToolsConfig {
  mcp_servers: string[];
  custom_tools: string[];
  web_search_enabled: boolean;
  code_execution_enabled: boolean;
  git_enabled: boolean;
}

interface CustomAgentConfig {
  name: string;
  role: string;
  specialization: string;
  description: string;
  responsibilities: string[];
  model: ModelConfig;
  reasoning: ReasoningConfig;
  tools: ToolsConfig;
  system_prompt?: string;
}

interface CustomTeamConfig {
  name: string;
  description: string;
  use_case: string;
  agents: CustomAgentConfig[];
  communication_style: string;
  max_parallel_agents: number;
  shared_mcp_servers: string[];
  total_budget?: number;
}

// ============================================================================
// AGENT CARD EDITOR
// ============================================================================

const AgentEditor: React.FC<{
  agent: CustomAgentConfig;
  onUpdate: (agent: CustomAgentConfig) => void;
  onDelete: () => void;
}> = ({ agent, onUpdate, onDelete }) => {
  const [expanded, setExpanded] = useState(false);
  const [localAgent, setLocalAgent] = useState(agent);

  const updateField = (field: string, value: any) => {
    const updated = { ...localAgent, [field]: value };
    setLocalAgent(updated);
    onUpdate(updated);
  };

  const updateNested = (parent: string, field: string, value: any) => {
    const updated = {
      ...localAgent,
      [parent]: {
        ...localAgent[parent as keyof CustomAgentConfig],
        [field]: value
      }
    };
    setLocalAgent(updated);
    onUpdate(updated);
  };

  return (
    <div className="border rounded-lg p-4 mb-4 bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 bg-blue-100 rounded-full flex items-center justify-center">
            <Users className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <input
              type="text"
              value={localAgent.name}
              onChange={(e) => updateField('name', e.target.value)}
              className="font-semibold text-lg border-b border-transparent hover:border-gray-300 focus:border-blue-500 outline-none"
            />
            <div className="text-sm text-gray-600">{localAgent.role}</div>
          </div>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-2 hover:bg-gray-100 rounded"
          >
            {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
          </button>
          <button
            onClick={onDelete}
            className="p-2 hover:bg-red-50 rounded text-red-600"
          >
            <Trash2 className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Quick Settings */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <label className="text-xs text-gray-600">Specialization</label>
          <select
            value={localAgent.specialization}
            onChange={(e) => updateField('specialization', e.target.value)}
            className="w-full p-2 border rounded text-sm"
          >
            <option value="backend_api">Backend API</option>
            <option value="backend_database">Backend Database</option>
            <option value="frontend_react">Frontend React</option>
            <option value="frontend_ui_ux">Frontend UI/UX</option>
            <option value="devops_infrastructure">DevOps Infrastructure</option>
            <option value="security_pentesting">Security Pentesting</option>
            <option value="data_engineering">Data Engineering</option>
          </select>
        </div>

        <div>
          <label className="text-xs text-gray-600">Model</label>
          <select
            value={localAgent.model.model}
            onChange={(e) => updateNested('model', 'model', e.target.value)}
            className="w-full p-2 border rounded text-sm"
          >
            <option value="claude-haiku-4">Claude Haiku 4 ($)</option>
            <option value="claude-sonnet-4">Claude Sonnet 4 ($$)</option>
            <option value="claude-opus-4">Claude Opus 4 ($$$)</option>
            <option value="gpt-4o">GPT-4o ($$)</option>
            <option value="o1-preview">O1 Preview ($$$)</option>
          </select>
        </div>
      </div>

      {/* Expanded Settings */}
      {expanded && (
        <div className="border-t pt-4 space-y-4">
          {/* Description */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">
              Description
            </label>
            <textarea
              value={localAgent.description}
              onChange={(e) => updateField('description', e.target.value)}
              className="w-full p-2 border rounded text-sm"
              rows={2}
              placeholder="What does this agent do?"
            />
          </div>

          {/* Responsibilities */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-2 block flex items-center space-x-2">
              <Check className="w-4 h-4" />
              <span>Responsibilities</span>
            </label>
            <div className="space-y-2">
              {localAgent.responsibilities.map((resp, i) => (
                <div key={i} className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={resp}
                    onChange={(e) => {
                      const updated = [...localAgent.responsibilities];
                      updated[i] = e.target.value;
                      updateField('responsibilities', updated);
                    }}
                    className="flex-1 p-2 border rounded text-sm"
                  />
                  <button
                    onClick={() => {
                      const updated = localAgent.responsibilities.filter((_, idx) => idx !== i);
                      updateField('responsibilities', updated);
                    }}
                    className="p-2 text-red-600 hover:bg-red-50 rounded"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
              <button
                onClick={() => {
                  const updated = [...localAgent.responsibilities, ''];
                  updateField('responsibilities', updated);
                }}
                className="text-sm text-blue-600 hover:text-blue-700 flex items-center space-x-1"
              >
                <Plus className="w-4 h-4" />
                <span>Add Responsibility</span>
              </button>
            </div>
          </div>

          {/* Model Settings */}
          <div className="bg-purple-50 p-3 rounded">
            <h4 className="font-medium text-purple-900 mb-3 flex items-center space-x-2">
              <Brain className="w-4 h-4" />
              <span>Model Settings</span>
            </h4>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-700">Provider</label>
                <select
                  value={localAgent.model.provider}
                  onChange={(e) => updateNested('model', 'provider', e.target.value)}
                  className="w-full p-2 border rounded text-sm"
                >
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="local">Local (Ollama)</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-700">Temperature</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={localAgent.model.temperature}
                  onChange={(e) => updateNested('model', 'temperature', parseFloat(e.target.value))}
                  className="w-full p-2 border rounded text-sm"
                />
              </div>

              <div className="col-span-2">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localAgent.model.auto_select}
                    onChange={(e) => updateNested('model', 'auto_select', e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Auto-select model by complexity</span>
                </label>
              </div>
            </div>
          </div>

          {/* Reasoning Settings */}
          <div className="bg-green-50 p-3 rounded">
            <h4 className="font-medium text-green-900 mb-3 flex items-center space-x-2">
              <Zap className="w-4 h-4" />
              <span>Reasoning Settings</span>
            </h4>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-700">Default Pattern</label>
                <select
                  value={localAgent.reasoning.default_pattern}
                  onChange={(e) => updateNested('reasoning', 'default_pattern', e.target.value)}
                  className="w-full p-2 border rounded text-sm"
                >
                  <option value="cot">Chain-of-Thought</option>
                  <option value="tot">Tree-of-Thoughts</option>
                  <option value="self_consistency">Self-Consistency</option>
                  <option value="reflection">Reflection</option>
                  <option value="react">ReAct</option>
                </select>
              </div>

              <div>
                <label className="text-xs text-gray-700">Min Confidence</label>
                <input
                  type="number"
                  step="0.05"
                  min="0"
                  max="1"
                  value={localAgent.reasoning.min_confidence}
                  onChange={(e) => updateNested('reasoning', 'min_confidence', parseFloat(e.target.value))}
                  className="w-full p-2 border rounded text-sm"
                />
              </div>

              <div className="col-span-2">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localAgent.reasoning.verification_enabled}
                    onChange={(e) => updateNested('reasoning', 'verification_enabled', e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Enable verification</span>
                </label>
              </div>
            </div>
          </div>

          {/* Tools Settings */}
          <div className="bg-orange-50 p-3 rounded">
            <h4 className="font-medium text-orange-900 mb-3 flex items-center space-x-2">
              <Wrench className="w-4 h-4" />
              <span>Tools & MCP</span>
            </h4>
            
            <div className="space-y-2">
              <div>
                <label className="text-xs text-gray-700 mb-1 block">MCP Servers</label>
                <div className="flex flex-wrap gap-2">
                  {['memory', 'filesystem', 'postgres', 'redis', 'github', 's3'].map(server => (
                    <label key={server} className="flex items-center space-x-1 text-sm">
                      <input
                        type="checkbox"
                        checked={localAgent.tools.mcp_servers.includes(server)}
                        onChange={(e) => {
                          const servers = e.target.checked
                            ? [...localAgent.tools.mcp_servers, server]
                            : localAgent.tools.mcp_servers.filter(s => s !== server);
                          updateNested('tools', 'mcp_servers', servers);
                        }}
                        className="rounded"
                      />
                      <span>{server}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localAgent.tools.web_search_enabled}
                    onChange={(e) => updateNested('tools', 'web_search_enabled', e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Web Search</span>
                </label>

                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localAgent.tools.code_execution_enabled}
                    onChange={(e) => updateNested('tools', 'code_execution_enabled', e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Code Execution</span>
                </label>

                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localAgent.tools.git_enabled}
                    onChange={(e) => updateNested('tools', 'git_enabled', e.target.checked)}
                    className="rounded"
                  />
                  <span className="text-sm">Git Access</span>
                </label>
              </div>
            </div>
          </div>

          {/* System Prompt */}
          <div>
            <label className="text-sm font-medium text-gray-700 mb-1 block">
              Custom System Prompt (Optional)
            </label>
            <textarea
              value={localAgent.system_prompt || ''}
              onChange={(e) => updateField('system_prompt', e.target.value)}
              className="w-full p-2 border rounded text-sm font-mono"
              rows={4}
              placeholder="You are a specialized agent for..."
            />
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// TEAM CONFIGURATOR
// ============================================================================

const TeamConfigurator: React.FC = () => {
  const [team, setTeam] = useState<CustomTeamConfig>({
    name: 'New Team',
    description: '',
    use_case: 'web_app',
    agents: [],
    communication_style: 'async_messages',
    max_parallel_agents: 3,
    shared_mcp_servers: [],
    total_budget: undefined
  });

  const [templates, setTemplates] = useState<string[]>([
    'Full-Stack Web App',
    'VPN Service',
    'Data Pipeline',
    'Microservices'
  ]);

  const [saved, setSaved] = useState(false);

  // Add new agent
  const addAgent = () => {
    const newAgent: CustomAgentConfig = {
      name: `Agent ${team.agents.length + 1}`,
      role: 'backend',
      specialization: 'backend_api',
      description: '',
      responsibilities: [],
      model: {
        provider: 'anthropic',
        model: 'claude-sonnet-4',
        auto_select: false,
        temperature: 1.0,
        max_tokens: 4096
      },
      reasoning: {
        default_pattern: 'cot',
        min_confidence: 0.7,
        verification_enabled: true,
        max_retries: 2
      },
      tools: {
        mcp_servers: ['memory', 'filesystem'],
        custom_tools: [],
        web_search_enabled: false,
        code_execution_enabled: true,
        git_enabled: true
      }
    };

    setTeam({ ...team, agents: [...team.agents, newAgent] });
  };

  // Update agent
  const updateAgent = (index: number, updated: CustomAgentConfig) => {
    const newAgents = [...team.agents];
    newAgents[index] = updated;
    setTeam({ ...team, agents: newAgents });
  };

  // Delete agent
  const deleteAgent = (index: number) => {
    setTeam({
      ...team,
      agents: team.agents.filter((_, i) => i !== index)
    });
  };

  // Load template
  const loadTemplate = async (templateName: string) => {
    // In production, fetch from API
    // For now, mock data
    console.log('Loading template:', templateName);
  };

  // Save team
  const saveTeam = async () => {
    // In production, POST to API
    console.log('Saving team:', team);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  // Export team
  const exportTeam = () => {
    const blob = new Blob([JSON.stringify(team, null, 2)], {
      type: 'application/json'
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${team.name.toLowerCase().replace(/\s+/g, '_')}.json`;
    a.click();
  };

  // Import team
  const importTeam = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      const content = e.target?.result as string;
      const imported = JSON.parse(content);
      setTeam(imported);
    };
    reader.readAsText(file);
  };

  return (
    <div className="team-configurator max-w-6xl mx-auto p-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Team Customization</h1>
        <p className="text-gray-600">
          Create and customize your perfect AI agent team
        </p>
      </div>

      {/* Team Settings */}
      <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4 flex items-center space-x-2">
          <Settings className="w-5 h-5" />
          <span>Team Settings</span>
        </h2>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Team Name
            </label>
            <input
              type="text"
              value={team.name}
              onChange={(e) => setTeam({ ...team, name: e.target.value })}
              className="w-full p-2 border rounded"
              placeholder="My Awesome Team"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Use Case
            </label>
            <select
              value={team.use_case}
              onChange={(e) => setTeam({ ...team, use_case: e.target.value })}
              className="w-full p-2 border rounded"
            >
              <option value="web_app">Web Application</option>
              <option value="microservices">Microservices</option>
              <option value="vpn_service">VPN Service</option>
              <option value="data_pipeline">Data Pipeline</option>
              <option value="mobile_app">Mobile App</option>
            </select>
          </div>

          <div className="col-span-2">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={team.description}
              onChange={(e) => setTeam({ ...team, description: e.target.value })}
              className="w-full p-2 border rounded"
              rows={2}
              placeholder="What does this team do?"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Communication Style
            </label>
            <select
              value={team.communication_style}
              onChange={(e) => setTeam({ ...team, communication_style: e.target.value })}
              className="w-full p-2 border rounded"
            >
              <option value="async_messages">Async Messages (AutoGen)</option>
              <option value="sequential">Sequential (CrewAI)</option>
              <option value="broadcast">Broadcast (MetaGPT)</option>
              <option value="hierarchical">Hierarchical (Manager)</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Max Parallel Agents
            </label>
            <input
              type="number"
              min="1"
              max="10"
              value={team.max_parallel_agents}
              onChange={(e) => setTeam({ ...team, max_parallel_agents: parseInt(e.target.value) })}
              className="w-full p-2 border rounded"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Budget Limit ($)
            </label>
            <input
              type="number"
              step="0.01"
              value={team.total_budget || ''}
              onChange={(e) => setTeam({ ...team, total_budget: e.target.value ? parseFloat(e.target.value) : undefined })}
              className="w-full p-2 border rounded"
              placeholder="No limit"
            />
          </div>
        </div>
      </div>

      {/* Templates */}
      <div className="bg-gradient-to-r from-blue-50 to-purple-50 rounded-lg p-4 mb-6">
        <h3 className="font-medium mb-3">Quick Start Templates</h3>
        <div className="flex flex-wrap gap-2">
          {templates.map(template => (
            <button
              key={template}
              onClick={() => loadTemplate(template)}
              className="px-4 py-2 bg-white border rounded hover:bg-blue-50 text-sm"
            >
              {template}
            </button>
          ))}
        </div>
      </div>

      {/* Agents */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center space-x-2">
            <Users className="w-5 h-5" />
            <span>Agents ({team.agents.length})</span>
          </h2>
          
          <button
            onClick={addAgent}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 flex items-center space-x-2"
          >
            <Plus className="w-5 h-5" />
            <span>Add Agent</span>
          </button>
        </div>

        {team.agents.length === 0 ? (
          <div className="text-center py-12 bg-gray-50 rounded-lg">
            <Users className="w-16 h-16 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-600 mb-4">No agents yet</p>
            <button
              onClick={addAgent}
              className="px-6 py-3 bg-blue-600 text-white rounded hover:bg-blue-700"
            >
              Add Your First Agent
            </button>
          </div>
        ) : (
          <div>
            {team.agents.map((agent, index) => (
              <AgentEditor
                key={index}
                agent={agent}
                onUpdate={(updated) => updateAgent(index, updated)}
                onDelete={() => deleteAgent(index)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between border-t pt-6">
        <div className="flex items-center space-x-3">
          <button
            onClick={exportTeam}
            className="px-4 py-2 border rounded hover:bg-gray-50 flex items-center space-x-2"
          >
            <Download className="w-4 h-4" />
            <span>Export JSON</span>
          </button>
          
          <label className="px-4 py-2 border rounded hover:bg-gray-50 flex items-center space-x-2 cursor-pointer">
            <Upload className="w-4 h-4" />
            <span>Import JSON</span>
            <input
              type="file"
              accept=".json"
              onChange={importTeam}
              className="hidden"
            />
          </label>
        </div>

        <button
          onClick={saveTeam}
          className={`px-6 py-3 rounded font-medium flex items-center space-x-2 ${
            saved
              ? 'bg-green-600 text-white'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          {saved ? (
            <>
              <Check className="w-5 h-5" />
              <span>Saved!</span>
            </>
          ) : (
            <>
              <Save className="w-5 h-5" />
              <span>Save Team</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default TeamConfigurator;
export { AgentEditor };
