# Claude Agent Manager

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey.svg)](https://www.microsoft.com/windows)

**Multi-agent orchestration for Claude Code CLI** — Run multiple isolated Claude Code instances with their own memory, permissions, and project contexts. Perfect for developers juggling multiple projects or teams managing AI-assisted workflows.

## The Problem

Claude Code CLI is powerful, but it's designed for single-project use:
- One instance per terminal
- Shared configuration across projects
- No built-in way to manage multiple agents
- Manual window management when multitasking

## The Solution

Claude Agent Manager provides:

- **Multi-Agent Support** — Run 2, 4, or more Claude instances simultaneously
- **Project Isolation** — Each agent has its own project path, memory, and config
- **Per-Agent Permissions** — Granular control over what each agent can do
- **Smart Window Tiling** — Auto-arrange agent windows with hotkeys
- **Embedded Console** — Native terminal embedding (no external windows)
- **Global Hotkeys** — Quick access without switching windows

## Features

### Agent Management
- Create agents bound to specific project directories
- Each agent runs on its own port with isolated memory
- Start/stop agents individually or in batches
- Visual status tracking (online/offline)

### Permission System
Control what each agent can do with preset profiles or custom rules:

```json
{
  "permissions": {
    "allow": [
      "Read(*)",
      "Write(~/projects/myproject/**)",
      "Edit(~/projects/myproject/**)",
      "Bash(git:*)",
      "Bash(npm:*)",
      "Bash(python:*)",
      "mcp__*",
      "WebFetch"
    ],
    "deny": [
      "Bash(rm -rf /*)",
      "Bash(sudo:*)"
    ]
  }
}
```

**Presets:**
| Preset | Description |
|--------|-------------|
| `default` | Balanced — read access, common dev tools, MCP servers |
| `strict` | Minimal — read-only, limited git, no network tools |
| `permissive` | Full access — all dev tools, docker, process management |
| `custom` | Define your own allow/deny rules |

### Window Tiling
Smart layouts based on active agent count:

| Agents | Layout |
|--------|--------|
| 1 | Maximized with margins |
| 2 | Side by side |
| 3 | 2+1 (two left, one right) |
| 4+ | Grid |

### Global Hotkeys
| Hotkey | Action |
|--------|--------|
| `Ctrl+Alt+T` | Tile all agent windows |
| `Ctrl+Alt+M` | Minimize all agents |
| `Ctrl+Alt+1-4` | Focus specific agent |
| `Ctrl+Alt+D` | Toggle dashboard |

## Installation

### Prerequisites
1. **Python 3.10+**
2. **Node.js LTS** (for Claude Code CLI)
3. **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
4. **PM2** (optional, for background workers): `npm install -g pm2`

### Install Claude Agent Manager

```powershell
# Clone the repository
git clone https://github.com/divnjl2/clod.git claude-agent-manager
cd claude-agent-manager

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install
pip install -e .
```

### Initial Configuration

```powershell
# Configure paths (adjust to your setup)
cam config --claude-mem-root "C:\path\to\claude-mem" --browser "edge-app"

# Verify configuration
cam config-show
```

## Usage

### CLI Commands

```powershell
# Create a new agent
cam new --purpose "backend-api" --project "C:\projects\my-api"

# List all agents
cam list

# Start an agent
cam start <agent_id>

# Stop an agent
cam stop <agent_id>

# Tile windows
cam tile --count 4

# Open dashboard GUI
cam-gui
```

### Dashboard (GUI)

Launch the visual dashboard:
```powershell
cam-gui
```

Features:
- Visual agent cards with status indicators
- One-click start/stop
- Inline name editing
- Settings panel for each agent
- Theme toggle (dark/light)

## Architecture

```
claude-agent-manager/
├── src/claude_agent_manager/
│   ├── cli.py              # CLI commands (typer)
│   ├── manager.py          # Core agent lifecycle
│   ├── registry.py         # Agent records & permissions
│   ├── settings.py         # App settings
│   ├── simple_dashboard.py # Tkinter GUI
│   ├── tile.py             # Window tiling logic
│   ├── hotkeys.py          # Global hotkey support
│   ├── windows.py          # Win32 API helpers
│   └── terminal/
│       └── embedded_console.py  # Native terminal embedding
├── pyproject.toml
└── README.md
```

### Data Storage

```
%USERPROFILE%\.claude-agents\
├── <agent-id>/
│   ├── agent.json          # Agent configuration
│   ├── memory/             # Agent-specific memory
│   └── CLAUDE.md           # Agent system prompt
└── ...

%LOCALAPPDATA%\ClaudeAgentManager\
└── settings.json           # App settings
```

## Configuration

### Agent Configuration (`agent.json`)

```json
{
  "id": "abc123",
  "purpose": "backend-api",
  "project_path": "C:\\projects\\my-api",
  "port": 7860,
  "permissions": {
    "preset": "default",
    "allow": ["Bash(docker *)"],
    "deny": []
  }
}
```

### App Settings (`settings.json`)

```json
{
  "theme": "dark",
  "tile_layout": "smart",
  "tile_gap": 8,
  "hotkey_tile_all": "ctrl+alt+t",
  "hotkey_minimize_all": "ctrl+alt+m",
  "auto_tile_on_start": true
}
```

## Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```powershell
git clone https://github.com/divnjl2/clod.git
cd clod
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

### Areas for Contribution

- **Cross-platform support** — macOS/Linux compatibility
- **More MCP integrations** — Pre-configured server templates
- **Agent templates** — Purpose-specific agent presets
- **Improved tiling** — Monitor selection, custom layouts
- **Session persistence** — Remember window positions
- **Agent communication** — Inter-agent messaging
- **Metrics & logging** — Usage tracking, performance monitoring

### Code Style

- Python 3.10+ with type hints
- Black for formatting
- Pydantic for data models
- Tkinter for GUI (keeping it dependency-light)

## Roadmap

- [ ] macOS support
- [ ] Linux support
- [ ] Agent groups/workspaces
- [ ] Shared memory between agents
- [ ] Web-based dashboard alternative
- [ ] Docker deployment
- [ ] VS Code extension

## FAQ

**Q: Does this work with the Claude Code VS Code extension?**
A: This is designed for the CLI version. VS Code extension has its own instance management.

**Q: Can agents share memory?**
A: Currently each agent has isolated memory. Shared memory is on the roadmap.

**Q: Why Windows-first?**
A: The embedded console feature uses Windows APIs. Cross-platform is planned.

**Q: How many agents can I run?**
A: Limited only by your system resources. Tested with 8+ concurrent agents.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- [Anthropic](https://anthropic.com) for Claude and Claude Code
- The open-source community for inspiration and contributions

---

**Made with Claude Code** — This project itself was developed using Claude Code, demonstrating the multi-agent workflow it enables.
