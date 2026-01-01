// Model Configuration & Todo List UI Components
// dashboard/src/components/AgentPlanning.tsx

import React, { useState, useEffect } from 'react';
import {
  Brain, CheckCircle, Circle, AlertCircle, Clock, Zap,
  Settings, ChevronDown, ChevronUp, Play, Pause
} from 'lucide-react';

// ============================================================================
// TYPES
// ============================================================================

interface SubTask {
  id: string;
  description: string;
  complexity: 'TRIVIAL' | 'SIMPLE' | 'MEDIUM' | 'COMPLEX' | 'EXPERT';
  estimated_time: number;
  dependencies: string[];
  status: 'pending' | 'in_progress' | 'done' | 'failed';
  reasoning?: string;
  result?: string;
  model_used?: string;
  actual_time?: number;
}

interface AgentPlan {
  agent_id: string;
  agent_role: string;
  global_task: string;
  subtasks: SubTask[];
  auto_select_model: boolean;
  default_model: string;
  model_mapping: Record<string, string>;
}

interface ModelConfig {
  tier: 'fast' | 'balanced' | 'smart' | 'custom' | 'local';
  model_name: string;
  api_provider: string;
  base_url?: string;
  cost_per_1k_input: number;
  cost_per_1k_output: number;
}

// ============================================================================
// MODEL SELECTOR COMPONENT
// ============================================================================

const ModelSelector: React.FC<{
  value: string;
  onChange: (model: string) => void;
  availableModels: Record<string, ModelConfig>;
  complexity?: string;
}> = ({ value, onChange, availableModels, complexity }) => {
  const [isOpen, setIsOpen] = useState(false);

  const getTierIcon = (tier: string) => {
    switch (tier) {
      case 'fast':
        return <Zap className="w-4 h-4 text-yellow-500" />;
      case 'balanced':
        return <Brain className="w-4 h-4 text-blue-500" />;
      case 'smart':
        return <Brain className="w-4 h-4 text-purple-500" />;
      case 'local':
        return <Circle className="w-4 h-4 text-green-500" />;
      default:
        return <Settings className="w-4 h-4 text-gray-500" />;
    }
  };

  const getTierLabel = (tier: string) => {
    const labels = {
      fast: 'Fast & Cheap',
      balanced: 'Balanced',
      smart: 'Smart & Capable',
      local: 'Local (Free)',
      custom: 'Custom'
    };
    return labels[tier as keyof typeof labels] || tier;
  };

  const selectedModel = availableModels[value];

  return (
    <div className="relative">
      {/* Selected Model */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2 border rounded-lg hover:bg-gray-50"
      >
        <div className="flex items-center space-x-2">
          {selectedModel && getTierIcon(selectedModel.tier)}
          <div className="text-left">
            <div className="font-medium text-sm">{value}</div>
            {selectedModel && (
              <div className="text-xs text-gray-500">
                {getTierLabel(selectedModel.tier)} • {selectedModel.api_provider}
              </div>
            )}
          </div>
        </div>
        {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute z-10 w-full mt-1 bg-white border rounded-lg shadow-lg max-h-96 overflow-y-auto">
          {/* Fast Models */}
          <div className="p-2">
            <div className="text-xs font-semibold text-gray-500 px-2 py-1">
              ⚡ Fast Models (Simple Tasks)
            </div>
            {Object.entries(availableModels)
              .filter(([_, config]) => config.tier === 'fast')
              .map(([name, config]) => (
                <button
                  key={name}
                  onClick={() => {
                    onChange(name);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-2 py-2 hover:bg-blue-50 rounded"
                >
                  <div className="flex items-center space-x-2">
                    {getTierIcon(config.tier)}
                    <div className="text-left">
                      <div className="text-sm font-medium">{name}</div>
                      <div className="text-xs text-gray-500">{config.api_provider}</div>
                    </div>
                  </div>
                  <div className="text-xs text-gray-600">
                    ${config.cost_per_1k_output.toFixed(4)}/1k
                  </div>
                </button>
              ))}
          </div>

          {/* Balanced Models */}
          <div className="p-2 border-t">
            <div className="text-xs font-semibold text-gray-500 px-2 py-1">
              ⚖️ Balanced Models (Medium Tasks)
            </div>
            {Object.entries(availableModels)
              .filter(([_, config]) => config.tier === 'balanced')
              .map(([name, config]) => (
                <button
                  key={name}
                  onClick={() => {
                    onChange(name);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-2 py-2 hover:bg-blue-50 rounded"
                >
                  <div className="flex items-center space-x-2">
                    {getTierIcon(config.tier)}
                    <div className="text-left">
                      <div className="text-sm font-medium">{name}</div>
                      <div className="text-xs text-gray-500">{config.api_provider}</div>
                    </div>
                  </div>
                  <div className="text-xs text-gray-600">
                    ${config.cost_per_1k_output.toFixed(4)}/1k
                  </div>
                </button>
              ))}
          </div>

          {/* Smart Models */}
          <div className="p-2 border-t">
            <div className="text-xs font-semibold text-gray-500 px-2 py-1">
              🧠 Smart Models (Complex Tasks)
            </div>
            {Object.entries(availableModels)
              .filter(([_, config]) => config.tier === 'smart')
              .map(([name, config]) => (
                <button
                  key={name}
                  onClick={() => {
                    onChange(name);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-2 py-2 hover:bg-blue-50 rounded"
                >
                  <div className="flex items-center space-x-2">
                    {getTierIcon(config.tier)}
                    <div className="text-left">
                      <div className="text-sm font-medium">{name}</div>
                      <div className="text-xs text-gray-500">{config.api_provider}</div>
                    </div>
                  </div>
                  <div className="text-xs text-gray-600">
                    ${config.cost_per_1k_output.toFixed(4)}/1k
                  </div>
                </button>
              ))}
          </div>

          {/* Local Models */}
          <div className="p-2 border-t">
            <div className="text-xs font-semibold text-gray-500 px-2 py-1">
              💻 Local Models (Free)
            </div>
            {Object.entries(availableModels)
              .filter(([_, config]) => config.tier === 'local')
              .map(([name, config]) => (
                <button
                  key={name}
                  onClick={() => {
                    onChange(name);
                    setIsOpen(false);
                  }}
                  className="w-full flex items-center justify-between px-2 py-2 hover:bg-blue-50 rounded"
                >
                  <div className="flex items-center space-x-2">
                    {getTierIcon(config.tier)}
                    <div className="text-left">
                      <div className="text-sm font-medium">{name}</div>
                      <div className="text-xs text-gray-500">
                        {config.base_url || 'localhost'}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-green-600">FREE</div>
                </button>
              ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// TODO LIST COMPONENT
// ============================================================================

const TodoList: React.FC<{
  plan: AgentPlan;
  onStartTask?: (taskId: string) => void;
}> = ({ plan, onStartTask }) => {
  const [expandedTask, setExpandedTask] = useState<string | null>(null);

  const getComplexityColor = (complexity: string) => {
    const colors = {
      TRIVIAL: 'bg-gray-100 text-gray-700',
      SIMPLE: 'bg-blue-100 text-blue-700',
      MEDIUM: 'bg-yellow-100 text-yellow-700',
      COMPLEX: 'bg-orange-100 text-orange-700',
      EXPERT: 'bg-red-100 text-red-700'
    };
    return colors[complexity as keyof typeof colors] || 'bg-gray-100';
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'done':
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case 'in_progress':
        return <Play className="w-5 h-5 text-blue-500 animate-pulse" />;
      case 'failed':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      default:
        return <Circle className="w-5 h-5 text-gray-400" />;
    }
  };

  const groupedTasks = {
    in_progress: plan.subtasks.filter(t => t.status === 'in_progress'),
    pending: plan.subtasks.filter(t => t.status === 'pending'),
    done: plan.subtasks.filter(t => t.status === 'done'),
    failed: plan.subtasks.filter(t => t.status === 'failed')
  };

  const progress = plan.subtasks.length > 0
    ? (groupedTasks.done.length / plan.subtasks.length) * 100
    : 0;

  return (
    <div className="todo-list">
      {/* Header */}
      <div className="mb-4">
        <h3 className="font-semibold text-lg mb-2">Task Plan</h3>
        <div className="flex items-center space-x-3">
          <div className="flex-1">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
          <div className="text-sm text-gray-600">
            {groupedTasks.done.length}/{plan.subtasks.length} done
          </div>
        </div>
      </div>

      {/* In Progress */}
      {groupedTasks.in_progress.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-semibold text-blue-600 mb-2">
            🔵 In Progress
          </div>
          {groupedTasks.in_progress.map(task => (
            <TaskCard
              key={task.id}
              task={task}
              expanded={expandedTask === task.id}
              onToggle={() =>
                setExpandedTask(expandedTask === task.id ? null : task.id)
              }
              getComplexityColor={getComplexityColor}
              getStatusIcon={getStatusIcon}
            />
          ))}
        </div>
      )}

      {/* Pending */}
      {groupedTasks.pending.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-semibold text-gray-600 mb-2">
            ⏳ Pending ({groupedTasks.pending.length})
          </div>
          {groupedTasks.pending.map(task => (
            <TaskCard
              key={task.id}
              task={task}
              expanded={expandedTask === task.id}
              onToggle={() =>
                setExpandedTask(expandedTask === task.id ? null : task.id)
              }
              getComplexityColor={getComplexityColor}
              getStatusIcon={getStatusIcon}
              onStart={onStartTask}
            />
          ))}
        </div>
      )}

      {/* Done */}
      {groupedTasks.done.length > 0 && (
        <div className="mb-4">
          <div className="text-xs font-semibold text-green-600 mb-2">
            ✅ Done ({groupedTasks.done.length})
          </div>
          {groupedTasks.done.map(task => (
            <TaskCard
              key={task.id}
              task={task}
              expanded={expandedTask === task.id}
              onToggle={() =>
                setExpandedTask(expandedTask === task.id ? null : task.id)
              }
              getComplexityColor={getComplexityColor}
              getStatusIcon={getStatusIcon}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const TaskCard: React.FC<{
  task: SubTask;
  expanded: boolean;
  onToggle: () => void;
  getComplexityColor: (complexity: string) => string;
  getStatusIcon: (status: string) => React.ReactNode;
  onStart?: (taskId: string) => void;
}> = ({ task, expanded, onToggle, getComplexityColor, getStatusIcon, onStart }) => {
  return (
    <div className="border rounded-lg mb-2 overflow-hidden">
      {/* Task Header */}
      <button
        onClick={onToggle}
        className="w-full flex items-start space-x-3 p-3 hover:bg-gray-50"
      >
        <div className="mt-0.5">{getStatusIcon(task.status)}</div>
        <div className="flex-1 text-left">
          <div className="font-medium text-sm">{task.description}</div>
          <div className="flex items-center space-x-2 mt-1">
            <span
              className={`px-2 py-0.5 rounded text-xs ${getComplexityColor(
                task.complexity
              )}`}
            >
              {task.complexity}
            </span>
            <span className="text-xs text-gray-500 flex items-center space-x-1">
              <Clock className="w-3 h-3" />
              <span>{task.estimated_time}min</span>
            </span>
            {task.model_used && (
              <span className="text-xs text-gray-500">{task.model_used}</span>
            )}
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>

      {/* Expanded Details */}
      {expanded && (
        <div className="border-t p-3 bg-gray-50 space-y-2">
          {/* Dependencies */}
          {task.dependencies.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-gray-600 mb-1">
                Dependencies:
              </div>
              <div className="flex flex-wrap gap-1">
                {task.dependencies.map(dep => (
                  <span
                    key={dep}
                    className="px-2 py-1 bg-blue-100 text-blue-700 rounded text-xs"
                  >
                    {dep}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Reasoning */}
          {task.reasoning && (
            <div>
              <div className="text-xs font-semibold text-gray-600 mb-1">
                Reasoning:
              </div>
              <div className="text-xs text-gray-700 bg-white p-2 rounded">
                {task.reasoning}
              </div>
            </div>
          )}

          {/* Result */}
          {task.result && (
            <div>
              <div className="text-xs font-semibold text-gray-600 mb-1">
                Result:
              </div>
              <div className="text-xs text-gray-700 bg-white p-2 rounded">
                {task.result}
              </div>
            </div>
          )}

          {/* Actions */}
          {task.status === 'pending' && onStart && (
            <button
              onClick={() => onStart(task.id)}
              className="px-3 py-1 bg-blue-500 text-white rounded text-sm hover:bg-blue-600"
            >
              Start Task
            </button>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// MODEL CONFIGURATION PANEL
// ============================================================================

const ModelConfigPanel: React.FC<{
  plan: AgentPlan;
  availableModels: Record<string, ModelConfig>;
  onUpdate: (updates: Partial<AgentPlan>) => void;
}> = ({ plan, availableModels, onUpdate }) => {
  return (
    <div className="model-config-panel bg-white rounded-lg shadow p-4">
      <h3 className="font-semibold text-lg mb-4">Model Configuration</h3>

      {/* Auto Select Toggle */}
      <div className="mb-4">
        <label className="flex items-center space-x-2">
          <input
            type="checkbox"
            checked={plan.auto_select_model}
            onChange={e =>
              onUpdate({ auto_select_model: e.target.checked })
            }
            className="rounded"
          />
          <span className="text-sm">
            Auto-select model based on task complexity
          </span>
        </label>
      </div>

      {/* Default Model */}
      <div className="mb-4">
        <label className="block text-sm font-medium mb-2">
          Default Model
        </label>
        <ModelSelector
          value={plan.default_model}
          onChange={model => onUpdate({ default_model: model })}
          availableModels={availableModels}
        />
      </div>

      {/* Complexity Mapping */}
      {plan.auto_select_model && (
        <div className="space-y-3">
          <div className="text-sm font-medium">Model Selection by Complexity</div>

          {['TRIVIAL', 'SIMPLE', 'MEDIUM', 'COMPLEX', 'EXPERT'].map(
            complexity => (
              <div key={complexity} className="flex items-center space-x-2">
                <div className="w-20 text-xs text-gray-600">{complexity}</div>
                <ModelSelector
                  value={
                    plan.model_mapping[complexity] || plan.default_model
                  }
                  onChange={model =>
                    onUpdate({
                      model_mapping: {
                        ...plan.model_mapping,
                        [complexity]: model
                      }
                    })
                  }
                  availableModels={availableModels}
                  complexity={complexity}
                />
              </div>
            )
          )}
        </div>
      )}

      {/* Cost Estimate */}
      <div className="mt-4 p-3 bg-blue-50 rounded">
        <div className="text-sm font-medium mb-2">Estimated Cost</div>
        <div className="text-xs text-gray-600">
          Based on {plan.subtasks.length} subtasks with average 2k input / 1k
          output tokens each
        </div>
        {/* TODO: Calculate actual cost */}
        <div className="text-lg font-bold text-blue-600 mt-1">$0.15</div>
      </div>
    </div>
  );
};

export { ModelSelector, TodoList, ModelConfigPanel };
