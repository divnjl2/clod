# 🎯 План: Кастомизация агентов в Team Mode

## 📋 Что нужно

Каждый агент в команде должен иметь **такие же детальные настройки** как обычный агент:

✅ System Prompt & Instructions  
✅ Model Configuration (model, temperature, max_tokens, top_p)  
✅ MCP Tools  
✅ Advanced Options (thinking mode, memory, auto-save)  
✅ Team-specific (dependencies, outputs, priority)

---

## 🎨 UI Design

### Вариант 1: Settings в карточке агента

```
┌─ Team Roster ──────────────────────────────────┐
│ ┌────────────────────────────────────────────┐ │
│ │ 🏛️ Architect                         [⚙️]  │ │
│ │ Status: Working                            │ │
│ │ Progress: ████████░░ 80%                   │ │
│ │                                            │ │
│ │ [Click ⚙️ to configure agent details]     │ │
│ └────────────────────────────────────────────┘ │
│                                                 │
│ ┌────────────────────────────────────────────┐ │
│ │ 💻 Frontend Dev                      [⚙️]  │ │
│ │ Status: Waiting for architecture           │ │
│ └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘

При клике на ⚙️ открывается:

┌─ Agent Configuration ──────────────────────────┐
│ 🏛️ Architect                   [✕]            │
├─────────────────────────────────────────────────┤
│                                                 │
│ ▼ Basic Information                            │
│ ┌─────────────────────────────────────────────┐│
│ │ Name: [Architect                 ]          ││
│ │ Role: [architect                 ]          ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ▶ System Prompt & Instructions                 │
│                                                 │
│ ▶ Model Configuration                          │
│                                                 │
│ ▶ MCP Tools                                    │
│                                                 │
│ ▶ Advanced Options                             │
│                                                 │
│ ▶ Team Configuration                           │
│                                                 │
│                              [Cancel] [Save]   │
└─────────────────────────────────────────────────┘
```

### Вариант 2: Dedicated Settings Panel

```
┌─ Team Mode ────────────────────────────────────┐
│ [Team View] [Agent Settings] [Memory Graph]   │
├─────────────────────────────────────────────────┤
│                                                 │
│ Left: Team Roster          Right: Settings     │
│ ┌─────────────┐            ┌─────────────────┐│
│ │ Agents:     │            │ Selected:       ││
│ │             │            │ 🏛️ Architect    ││
│ │ ✓ Architect │◀───────────│                 ││
│ │   Frontend  │            │ [All config     ││
│ │   Backend   │            │  panels here]   ││
│ │   QA        │            │                 ││
│ │             │            │                 ││
│ └─────────────┘            └─────────────────┘│
└─────────────────────────────────────────────────┘
```

---

## 🏗️ Implementation Plan

### ✅ ШАГ 1: Добавить кнопку Settings в Team Roster (5 min)

**Файл:** `dashboard/src/components/TeamRoster.tsx`

```typescript
import { Settings } from 'lucide-react';
import { useState } from 'react';
import TeamAgentConfig from './TeamAgentConfig';

const TeamRoster: React.FC<{ agents: Agent[] }> = ({ agents }) => {
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  return (
    <div className="team-roster">
      <h3 className="font-bold mb-3">Team Members</h3>
      
      {agents.map(agent => (
        <div key={agent.id} className="agent-card p-3 border rounded-lg mb-2">
          {/* Agent Info */}
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center text-white">
                {agent.name[0]}
              </div>
              <div>
                <div className="font-semibold">{agent.name}</div>
                <div className="text-xs text-gray-500">{agent.status}</div>
              </div>
            </div>

            {/* NEW: Settings Button */}
            <button
              onClick={() => setSelectedAgent(agent)}
              className="p-2 hover:bg-gray-100 rounded transition-colors"
              title="Configure agent"
            >
              <Settings className="w-5 h-5 text-gray-600" />
            </button>
          </div>

          {/* Progress bar */}
          <div className="mt-2">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full"
                style={{ width: `${agent.progress}%` }}
              />
            </div>
          </div>
        </div>
      ))}

      {/* Settings Modal */}
      {selectedAgent && (
        <AgentSettingsModal
          agent={selectedAgent}
          onClose={() => setSelectedAgent(null)}
          onSave={(updates) => {
            // Update agent config
            updateAgent(selectedAgent.id, updates);
            setSelectedAgent(null);
          }}
        />
      )}
    </div>
  );
};
```

---

### ✅ ШАГ 2: Создать Settings Modal (10 min)

**Файл:** `dashboard/src/components/AgentSettingsModal.tsx`

```typescript
import React from 'react';
import { X } from 'lucide-react';
import TeamAgentConfig from './TeamAgentConfig';
import type { AgentConfig } from '../types/agent';

interface AgentSettingsModalProps {
  agent: AgentConfig;
  onClose: () => void;
  onSave: (updates: Partial<AgentConfig>) => void;
}

const AgentSettingsModal: React.FC<AgentSettingsModalProps> = ({
  agent,
  onClose,
  onSave
}) => {
  const [config, setConfig] = React.useState(agent);

  const handleSave = () => {
    onSave(config);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <h2 className="text-xl font-bold">Configure Agent: {agent.name}</h2>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          <TeamAgentConfig
            agent={config}
            onChange={(updates) => setConfig({ ...config, ...updates })}
            allAgents={[]} // Pass all team agents for dependency selection
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end space-x-2 p-4 border-t">
          <button
            onClick={onClose}
            className="px-4 py-2 border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Save Changes
          </button>
        </div>
      </div>
    </div>
  );
};

export default AgentSettingsModal;
```

---

### ✅ ШАГ 3: Интеграция в Team Mode (10 min)

**Файл:** `dashboard/src/components/TeamMode.tsx`

```typescript
import React, { useState } from 'react';
import TeamRoster from './TeamRoster';
import AgentConversations from './AgentConversations';
import MemoryGraph from './MemoryGraph';
import type { AgentConfig } from '../types/agent';

const TeamMode: React.FC = () => {
  const [agents, setAgents] = useState<AgentConfig[]>([
    {
      id: 'agent_1',
      role: 'architect',
      name: 'Architect',
      system_prompt: 'You are a system architect...',
      model: 'claude-opus-4',
      temperature: 0.7,
      max_tokens: 4000,
      top_p: 0.95,
      mcp_tools: ['memory', 'filesystem'],
      thinking_mode: 'enabled',
      memory_enabled: true,
      auto_save_context: true,
      dependencies: [],
      outputs: ['architecture', 'api_design'],
      priority: 0,
      status: 'working',
      progress: 45
    },
    // ... more agents
  ]);

  const updateAgent = (id: string, updates: Partial<AgentConfig>) => {
    setAgents(prev => prev.map(agent => 
      agent.id === id ? { ...agent, ...updates } : agent
    ));
  };

  return (
    <div className="team-mode p-6">
      <div className="grid grid-cols-3 gap-6">
        {/* Team Roster - with settings buttons */}
        <div>
          <TeamRoster 
            agents={agents}
            onUpdateAgent={updateAgent}
          />
        </div>

        {/* Agent Conversations */}
        <div className="col-span-2">
          <AgentConversations agents={agents} />
        </div>
      </div>

      {/* Memory Graph */}
      <div className="mt-6">
        <MemoryGraph agents={agents} />
      </div>
    </div>
  );
};

export default TeamMode;
```

---

## 📊 Что получаем

### До (простые настройки):
```typescript
const agent = {
  role: 'frontend',
  name: 'Frontend Dev'
  // Только базовые настройки
};
```

### После (полные настройки):
```typescript
const agent = {
  // Basic
  id: 'agent_1',
  role: 'frontend',
  name: 'Frontend Developer',
  
  // System Prompt
  system_prompt: `You are a senior frontend developer specializing in React...`,
  custom_instructions: `Prefer functional components, use TypeScript...`,
  
  // Model Config
  model: 'claude-sonnet-4',
  temperature: 0.7,
  max_tokens: 4000,
  top_p: 0.95,
  
  // MCP Tools
  mcp_tools: ['filesystem', 'memory', 'github'],
  
  // Advanced
  thinking_mode: 'enabled',
  memory_enabled: true,
  auto_save_context: true,
  
  // Team
  dependencies: ['architecture', 'api_design'],
  outputs: ['frontend_code', 'component_tests'],
  priority: 1
};
```

---

## 🎨 UI Walkthrough

### 1. Team Roster с Settings

```
┌─ Team Members ─────────────────────────────────┐
│                                                 │
│ ┌─────────────────────────────────────────────┐│
│ │ 🏛️  Architect               [⚙️]            ││
│ │     Status: Working                         ││
│ │     ████████░░ 80%                          ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ┌─────────────────────────────────────────────┐│
│ │ 💻  Frontend Developer      [⚙️]            ││
│ │     Status: Waiting for architecture        ││
│ │     ░░░░░░░░░░ 0%                           ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ┌─────────────────────────────────────────────┐│
│ │ 🔧  Backend Developer       [⚙️]            ││
│ │     Status: Waiting for architecture        ││
│ │     ░░░░░░░░░░ 0%                           ││
│ └─────────────────────────────────────────────┘│
└─────────────────────────────────────────────────┘
```

### 2. Click ⚙️ → Settings Modal opens

```
┌─ Configure Agent: Frontend Developer ─────────┐
│                                          [✕]   │
├─────────────────────────────────────────────────┤
│                                                 │
│ ▼ Basic Information                            │
│ ┌─────────────────────────────────────────────┐│
│ │ Name: [Frontend Developer          ]       ││
│ │ Role: [frontend                    ]       ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ▼ System Prompt & Instructions                 │
│ ┌─────────────────────────────────────────────┐│
│ │ System Prompt:                              ││
│ │ ┌─────────────────────────────────────────┐ ││
│ │ │You are a senior frontend developer     │ ││
│ │ │specializing in React and TypeScript.   │ ││
│ │ │                                         │ ││
│ │ │Your responsibilities:                   │ ││
│ │ │- Write clean, maintainable code        │ ││
│ │ │- Follow best practices                 │ ││
│ │ │- ...                                   │ ││
│ │ └─────────────────────────────────────────┘ ││
│ │                                             ││
│ │ Quick Templates: [🎯 Professional] [⚡ Concise] ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ▼ Model Configuration                          │
│ ┌─────────────────────────────────────────────┐│
│ │ Model: [claude-sonnet-4            ▾]      ││
│ │                                             ││
│ │ Temperature: 0.70    [─────●───────]       ││
│ │                      0.0          1.0      ││
│ │                                             ││
│ │ Max Tokens: 4000     [──────●──────]       ││
│ │                      1k           8k       ││
│ │                                             ││
│ │ Presets: [🎯 Precise] [⚖️ Balanced] [🎨 Creative] ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ▼ MCP Tools                                    │
│ ┌─────────────────────────────────────────────┐│
│ │ ☑ Filesystem - Read/write files            ││
│ │ ☑ Memory - Store/recall information        ││
│ │ ☐ Database - Query database                ││
│ │ ☐ Web Search - Search the web              ││
│ │ ☑ GitHub - Git operations                  ││
│ └─────────────────────────────────────────────┘│
│                                                 │
│ ▶ Advanced Options                             │
│                                                 │
│ ▶ Team Configuration                           │
│                                                 │
│                              [Cancel] [Save]   │
└─────────────────────────────────────────────────┘
```

### 3. Expand Team Configuration

```
│ ▼ Team Configuration                           │
│ ┌─────────────────────────────────────────────┐│
│ │ Execution Priority: [1]                     ││
│ │                                             ││
│ │ Dependencies:                               ││
│ │ ☑ Architect → architecture                 ││
│ │ ☑ Architect → api_design                   ││
│ │ ☐ Backend → backend_api                    ││
│ │                                             ││
│ │ Outputs:                                    ││
│ │ [frontend_code          ] [×]              ││
│ │ [component_tests        ] [×]              ││
│ │ [+ Add Output]                             ││
│ └─────────────────────────────────────────────┘│
```

---

## 🔄 User Flow

1. **User opens Team Mode**
   - Sees team roster with agents

2. **User clicks ⚙️ on Frontend agent**
   - Settings modal opens

3. **User configures agent:**
   - Updates system prompt
   - Changes model to `claude-sonnet-4`
   - Adjusts temperature to 0.7
   - Enables MCP tools: filesystem, memory, github
   - Sets dependencies: architecture, api_design
   - Defines outputs: frontend_code, tests

4. **User clicks Save**
   - Agent configuration updated
   - Modal closes
   - Agent uses new settings

5. **Execute team**
   - Each agent uses its custom configuration
   - Full control like individual agents!

---

## ✅ Benefits

**Same as individual agents:**
- ✅ Full system prompt customization
- ✅ Model selection & parameters
- ✅ MCP tools configuration
- ✅ Advanced options
- ✅ Thinking mode, memory, etc.

**Plus team-specific:**
- ✅ Dependencies management
- ✅ Outputs definition
- ✅ Execution priority

**Result:**
- 🎯 Each agent fully customizable
- 🎯 Team coordination preserved
- 🎯 Best of both worlds!

---

## 📦 Files Created

```
dashboard/src/components/
├── TeamAgentConfig.tsx        ✨ 600 lines (full config panel)
├── AgentSettingsModal.tsx     ✨ 100 lines (modal wrapper)
└── TeamRoster.tsx             ✨ Updated (settings button)

Total: 700+ new lines
```

---

## 🚀 Next Steps

1. **Integrate into Team Mode** (done ✅)
2. **Test configuration UI**
3. **Save/load agent configs**
4. **Apply configs during execution**

---

**ГОТОВО! Теперь каждый агент в Team Mode имеет полный уровень кастомизации как обычный агент! 🎉**
