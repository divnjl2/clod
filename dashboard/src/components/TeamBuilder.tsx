// Team Builder UI Components
// dashboard/src/components/TeamBuilder.tsx

import React, { useState } from 'react';
import {
  Users, Plus, Trash2, Copy, Download, Upload, Save,
  Settings, ArrowRight, Grid, List, Search, Filter,
  Star, Zap, Shield, Code, Rocket
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface AgentTemplate {
  role: string;
  name: string;
  system_prompt?: string;
  mcp_tools: string[];
  model_config: Record<string, any>;
  dependencies: string[];
  outputs: string[];
  priority: number;
}

interface TeamTemplate {
  id: string;
  name: string;
  description: string;
  team_type: string;
  agents: AgentTemplate[];
  coordination: string;
  tags: string[];
  author?: string;
}

// ============================================================================
// TEAM LIBRARY - Browse Pre-built Teams
// ============================================================================

const TeamLibrary: React.FC<{
  onSelectTemplate: (template: TeamTemplate) => void;
}> = ({ onSelectTemplate }) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Sample templates (from backend)
  const templates: TeamTemplate[] = [
    {
      id: 'team_full_stack_web',
      name: 'Full-Stack Web Team',
      description: 'Complete web development team with frontend, backend, and DevOps',
      team_type: 'full_stack',
      agents: [
        { role: 'architect', name: 'Architect', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: [], outputs: ['architecture'], priority: 0 },
        { role: 'frontend', name: 'Frontend', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['architecture'], outputs: ['frontend'], priority: 1 },
        { role: 'backend', name: 'Backend', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['architecture'], outputs: ['backend'], priority: 1 },
        { role: 'qa', name: 'QA', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['frontend', 'backend'], outputs: ['tests'], priority: 2 },
        { role: 'devops', name: 'DevOps', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['tests'], outputs: ['deployment'], priority: 3 },
      ],
      coordination: 'staged',
      tags: ['web', 'full-stack', 'popular'],
      author: 'ClodAI'
    },
    {
      id: 'team_vpn_service',
      name: 'VPN Service Team',
      description: 'Team specialized in VPN service with payments and Telegram',
      team_type: 'custom',
      agents: [
        { role: 'architect', name: 'VPN Architect', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: [], outputs: ['architecture'], priority: 0 },
        { role: 'backend', name: 'Backend Dev', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['architecture'], outputs: ['backend'], priority: 1 },
        { role: 'telegram', name: 'Telegram Bot', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['architecture'], outputs: ['bot'], priority: 1 },
        { role: 'qa', name: 'QA', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['backend', 'bot'], outputs: ['tests'], priority: 2 },
      ],
      coordination: 'staged',
      tags: ['vpn', 'payments', 'telegram', 'russia'],
      author: 'ClodAI'
    },
    {
      id: 'team_mobile_app',
      name: 'Mobile App Team',
      description: 'Cross-platform mobile development with backend',
      team_type: 'mobile_dev',
      agents: [
        { role: 'architect', name: 'Architect', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: [], outputs: ['architecture'], priority: 0 },
        { role: 'mobile', name: 'Mobile Dev', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['architecture'], outputs: ['app'], priority: 1 },
        { role: 'backend', name: 'Backend', system_prompt: '', mcp_tools: [], model_config: {}, dependencies: ['architecture'], outputs: ['api'], priority: 1 },
      ],
      coordination: 'staged',
      tags: ['mobile', 'ios', 'android'],
      author: 'ClodAI'
    }
  ];

  const filteredTemplates = templates.filter(t => {
    const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         t.description.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTags = selectedTags.length === 0 || selectedTags.some(tag => t.tags.includes(tag));
    return matchesSearch && matchesTags;
  });

  const allTags = Array.from(new Set(templates.flatMap(t => t.tags)));

  const getTeamIcon = (type: string) => {
    const icons = {
      full_stack: <Code className="w-5 h-5" />,
      mobile_dev: <Rocket className="w-5 h-5" />,
      security: <Shield className="w-5 h-5" />,
      custom: <Zap className="w-5 h-5" />
    };
    return icons[type as keyof typeof icons] || <Users className="w-5 h-5" />;
  };

  return (
    <div className="team-library">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-2xl font-bold mb-2">Team Library</h2>
        <p className="text-gray-600">Choose a pre-built team or create your own</p>
      </div>

      {/* Search & Filter */}
      <div className="mb-6 space-y-4">
        <div className="flex items-center space-x-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search teams..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border rounded-lg"
            />
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded ${viewMode === 'grid' ? 'bg-blue-100' : 'bg-gray-100'}`}
            >
              <Grid className="w-5 h-5" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 rounded ${viewMode === 'list' ? 'bg-blue-100' : 'bg-gray-100'}`}
            >
              <List className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tags */}
        <div className="flex items-center space-x-2 flex-wrap">
          <Filter className="w-4 h-4 text-gray-500" />
          {allTags.map(tag => (
            <button
              key={tag}
              onClick={() => {
                if (selectedTags.includes(tag)) {
                  setSelectedTags(selectedTags.filter(t => t !== tag));
                } else {
                  setSelectedTags([...selectedTags, tag]);
                }
              }}
              className={`px-3 py-1 rounded-full text-sm ${
                selectedTags.includes(tag)
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700'
              }`}
            >
              {tag}
            </button>
          ))}
        </div>
      </div>

      {/* Templates Grid/List */}
      {viewMode === 'grid' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredTemplates.map(template => (
            <TeamTemplateCard
              key={template.id}
              template={template}
              onSelect={onSelectTemplate}
              icon={getTeamIcon(template.team_type)}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {filteredTemplates.map(template => (
            <TeamTemplateRow
              key={template.id}
              template={template}
              onSelect={onSelectTemplate}
              icon={getTeamIcon(template.team_type)}
            />
          ))}
        </div>
      )}

      {/* Create Custom */}
      <div className="mt-6">
        <button
          onClick={() => onSelectTemplate({
            id: 'custom_new',
            name: 'New Custom Team',
            description: '',
            team_type: 'custom',
            agents: [],
            coordination: 'sequential',
            tags: [],
          })}
          className="w-full py-4 border-2 border-dashed border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 flex items-center justify-center space-x-2"
        >
          <Plus className="w-5 h-5" />
          <span className="font-medium">Create Custom Team</span>
        </button>
      </div>
    </div>
  );
};

const TeamTemplateCard: React.FC<{
  template: TeamTemplate;
  onSelect: (template: TeamTemplate) => void;
  icon: React.ReactNode;
}> = ({ template, onSelect, icon }) => {
  return (
    <div
      onClick={() => onSelect(template)}
      className="p-4 border rounded-lg hover:shadow-lg cursor-pointer transition-all"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-2">
          <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
            {icon}
          </div>
          {template.tags.includes('popular') && (
            <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
          )}
        </div>
      </div>

      <h3 className="font-semibold mb-1">{template.name}</h3>
      <p className="text-sm text-gray-600 mb-3">{template.description}</p>

      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>{template.agents.length} agents</span>
        <span>{template.coordination}</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {template.tags.map(tag => (
          <span
            key={tag}
            className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs"
          >
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
};

const TeamTemplateRow: React.FC<{
  template: TeamTemplate;
  onSelect: (template: TeamTemplate) => void;
  icon: React.ReactNode;
}> = ({ template, onSelect, icon }) => {
  return (
    <div
      onClick={() => onSelect(template)}
      className="p-4 border rounded-lg hover:bg-gray-50 cursor-pointer flex items-center justify-between"
    >
      <div className="flex items-center space-x-4">
        <div className="p-2 bg-blue-100 rounded-lg text-blue-600">
          {icon}
        </div>
        <div>
          <h3 className="font-semibold">{template.name}</h3>
          <p className="text-sm text-gray-600">{template.description}</p>
        </div>
      </div>

      <div className="flex items-center space-x-4">
        <div className="text-sm text-gray-500">
          {template.agents.length} agents
        </div>
        <ArrowRight className="w-5 h-5 text-gray-400" />
      </div>
    </div>
  );
};

// ============================================================================
// TEAM EDITOR - Create/Edit Custom Teams
// ============================================================================

const TeamEditor: React.FC<{
  template: TeamTemplate;
  onSave: (template: TeamTemplate) => void;
  onCancel: () => void;
}> = ({ template: initialTemplate, onSave, onCancel }) => {
  const [template, setTemplate] = useState(initialTemplate);
  const [selectedAgent, setSelectedAgent] = useState<number | null>(null);

  const addAgent = () => {
    const newAgent: AgentTemplate = {
      role: 'new_role',
      name: 'New Agent',
      system_prompt: '',
      mcp_tools: [],
      model_config: { model: 'claude-sonnet-4' },
      dependencies: [],
      outputs: [],
      priority: template.agents.length
    };

    setTemplate({
      ...template,
      agents: [...template.agents, newAgent]
    });
  };

  const removeAgent = (index: number) => {
    setTemplate({
      ...template,
      agents: template.agents.filter((_, i) => i !== index)
    });
  };

  const updateAgent = (index: number, updates: Partial<AgentTemplate>) => {
    const newAgents = [...template.agents];
    newAgents[index] = { ...newAgents[index], ...updates };
    setTemplate({ ...template, agents: newAgents });
  };

  return (
    <div className="team-editor space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Team Editor</h2>
          <p className="text-gray-600">Customize your team</p>
        </div>
        <div className="flex items-center space-x-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={() => onSave(template)}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 flex items-center space-x-2"
          >
            <Save className="w-4 h-4" />
            <span>Save Team</span>
          </button>
        </div>
      </div>

      {/* Team Settings */}
      <div className="bg-white border rounded-lg p-4 space-y-4">
        <h3 className="font-semibold">Team Settings</h3>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Team Name</label>
            <input
              type="text"
              value={template.name}
              onChange={(e) => setTemplate({ ...template, name: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Coordination</label>
            <select
              value={template.coordination}
              onChange={(e) => setTemplate({ ...template, coordination: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg"
            >
              <option value="sequential">Sequential</option>
              <option value="parallel">Parallel</option>
              <option value="staged">Staged</option>
              <option value="leader_based">Leader-Based</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Description</label>
          <textarea
            value={template.description}
            onChange={(e) => setTemplate({ ...template, description: e.target.value })}
            className="w-full px-3 py-2 border rounded-lg"
            rows={2}
          />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Tags (comma-separated)</label>
          <input
            type="text"
            value={template.tags.join(', ')}
            onChange={(e) => setTemplate({ ...template, tags: e.target.value.split(',').map(t => t.trim()) })}
            className="w-full px-3 py-2 border rounded-lg"
            placeholder="web, full-stack, react"
          />
        </div>
      </div>

      {/* Agents List */}
      <div className="bg-white border rounded-lg p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Team Agents ({template.agents.length})</h3>
          <button
            onClick={addAgent}
            className="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 flex items-center space-x-1"
          >
            <Plus className="w-4 h-4" />
            <span>Add Agent</span>
          </button>
        </div>

        <div className="space-y-2">
          {template.agents.map((agent, index) => (
            <div
              key={index}
              className={`p-3 border rounded-lg cursor-pointer ${
                selectedAgent === index ? 'border-blue-500 bg-blue-50' : 'hover:bg-gray-50'
              }`}
              onClick={() => setSelectedAgent(index)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-sm font-semibold">
                    {index + 1}
                  </div>
                  <div>
                    <div className="font-medium">{agent.name}</div>
                    <div className="text-xs text-gray-500">Role: {agent.role}</div>
                  </div>
                </div>

                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeAgent(index);
                  }}
                  className="p-1 hover:bg-red-100 rounded"
                >
                  <Trash2 className="w-4 h-4 text-red-500" />
                </button>
              </div>

              {selectedAgent === index && (
                <div className="mt-3 pt-3 border-t space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium mb-1">Name</label>
                      <input
                        type="text"
                        value={agent.name}
                        onChange={(e) => updateAgent(index, { name: e.target.value })}
                        className="w-full px-2 py-1 text-sm border rounded"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium mb-1">Role</label>
                      <input
                        type="text"
                        value={agent.role}
                        onChange={(e) => updateAgent(index, { role: e.target.value })}
                        className="w-full px-2 py-1 text-sm border rounded"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium mb-1">System Prompt</label>
                    <textarea
                      value={agent.system_prompt || ''}
                      onChange={(e) => updateAgent(index, { system_prompt: e.target.value })}
                      className="w-full px-2 py-1 text-sm border rounded"
                      rows={3}
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium mb-1">Dependencies</label>
                      <input
                        type="text"
                        value={agent.dependencies.join(', ')}
                        onChange={(e) => updateAgent(index, {
                          dependencies: e.target.value.split(',').map(d => d.trim()).filter(Boolean)
                        })}
                        className="w-full px-2 py-1 text-sm border rounded"
                        placeholder="architecture, api_design"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium mb-1">Outputs</label>
                      <input
                        type="text"
                        value={agent.outputs.join(', ')}
                        onChange={(e) => updateAgent(index, {
                          outputs: e.target.value.split(',').map(o => o.trim()).filter(Boolean)
                        })}
                        className="w-full px-2 py-1 text-sm border rounded"
                        placeholder="frontend_code, tests"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Export/Import */}
      <div className="flex items-center space-x-2">
        <button className="px-3 py-2 border rounded-lg hover:bg-gray-50 flex items-center space-x-2">
          <Download className="w-4 h-4" />
          <span>Export</span>
        </button>
        <button className="px-3 py-2 border rounded-lg hover:bg-gray-50 flex items-center space-x-2">
          <Upload className="w-4 h-4" />
          <span>Import</span>
        </button>
        <button className="px-3 py-2 border rounded-lg hover:bg-gray-50 flex items-center space-x-2">
          <Copy className="w-4 h-4" />
          <span>Clone</span>
        </button>
      </div>
    </div>
  );
};

// ============================================================================
// MAIN COMPONENT
// ============================================================================

const TeamBuilderMain: React.FC = () => {
  const [currentView, setCurrentView] = useState<'library' | 'editor'>('library');
  const [selectedTemplate, setSelectedTemplate] = useState<TeamTemplate | null>(null);

  const handleSelectTemplate = (template: TeamTemplate) => {
    setSelectedTemplate(template);
    setCurrentView('editor');
  };

  const handleSaveTeam = (template: TeamTemplate) => {
    // Save to backend
    console.log('Saving team:', template);
    setCurrentView('library');
  };

  const handleCancel = () => {
    setCurrentView('library');
    setSelectedTemplate(null);
  };

  return (
    <div className="team-builder-main p-6">
      {currentView === 'library' ? (
        <TeamLibrary onSelectTemplate={handleSelectTemplate} />
      ) : (
        selectedTemplate && (
          <TeamEditor
            template={selectedTemplate}
            onSave={handleSaveTeam}
            onCancel={handleCancel}
          />
        )
      )}
    </div>
  );
};

export default TeamBuilderMain;
export { TeamLibrary, TeamEditor };
