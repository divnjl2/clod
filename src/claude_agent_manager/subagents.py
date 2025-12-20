"""
Включение поддержки субагентов для агента.

Добавляет MCP сервер subagents в конфиг агента.

Использование:
    cam enable-subagents <agent_id>
    
    # Или программно
    from claude_agent_manager.subagents import enable_subagents
    enable_subagents("agent-1234")
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel

console = Console()


def get_mcp_server_path() -> Path:
    """Получить путь к MCP серверу субагентов."""
    # Сначала ищем рядом с этим файлом
    local = Path(__file__).parent / "subagent_mcp.py"
    if local.exists():
        return local
    
    # Потом в стандартных местах
    candidates = [
        Path.home() / ".claude-agent-manager" / "mcp" / "subagent_mcp.py",
        Path("/usr/local/share/claude-agent-manager/subagent_mcp.py"),
    ]
    
    for path in candidates:
        if path.exists():
            return path
    
    return local  # Вернём local даже если не существует


def enable_subagents(
    agent_id: str,
    max_subagents: int = 5,
    copy_mcp: bool = True
) -> bool:
    """
    Включить поддержку субагентов для агента.
    
    Args:
        agent_id: ID агента
        max_subagents: Максимум субагентов
        copy_mcp: Скопировать MCP сервер в директорию агента
    
    Returns:
        True если успешно
    """
    from .config import load_config
    from .registry import load_agent, save_agent

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agent_dir = agent_root / agent_id
    
    if not agent_dir.exists():
        console.print(f"[red]Agent not found: {agent_id}[/red]")
        return False
    
    # Путь к MCP серверу
    mcp_source = get_mcp_server_path()
    
    if copy_mcp:
        # Копируем MCP в директорию агента
        mcp_dir = agent_dir / "mcp"
        mcp_dir.mkdir(exist_ok=True)
        mcp_dest = mcp_dir / "subagent_mcp.py"
        
        if mcp_source.exists():
            shutil.copy2(mcp_source, mcp_dest)
            mcp_path = str(mcp_dest)
        else:
            # Создаём минимальный MCP
            console.print("[yellow]MCP source not found, agent won't have subagent tools[/yellow]")
            return False
    else:
        mcp_path = str(mcp_source)
    
    # Читаем текущий .mcp.json
    mcp_json_path = agent_dir / ".mcp.json"
    
    if mcp_json_path.exists():
        try:
            mcp_config = json.loads(mcp_json_path.read_text())
        except:
            mcp_config = {"mcpServers": {}}
    else:
        mcp_config = {"mcpServers": {}}
    
    if "mcpServers" not in mcp_config:
        mcp_config["mcpServers"] = {}
    
    # Добавляем subagents MCP
    mcp_config["mcpServers"]["subagents"] = {
        "command": "python",
        "args": [mcp_path],
        "env": {
            "PARENT_AGENT_ID": agent_id,
            "MAX_SUBAGENTS": str(max_subagents),
            "AGENT_ROOT": str(paths.agents_dir.parent)
        }
    }
    
    # Сохраняем
    mcp_json_path.write_text(json.dumps(mcp_config, indent=2))
    
    # Обновляем CLAUDE.md с инструкциями
    claude_md = agent_dir / "CLAUDE.md"
    
    subagent_instructions = """

## 🤖 Sub-Agent Orchestration

You have the ability to CREATE and MANAGE sub-agents. This is a powerful feature - USE IT for complex tasks!

### WHEN TO CREATE SUB-AGENTS

**CREATE sub-agents when:**
- Task involves multiple distinct parts (backend + frontend + tests)
- Task is complex and would benefit from parallel work
- Task requires different expertise areas
- You need to work on multiple files/directories simultaneously
- Task would take too long to do alone

**DON'T create sub-agents for:**
- Simple single-file changes
- Quick fixes or small edits
- Tasks you can complete in under 5 minutes

### HOW TO USE

1. **Analyze the task** - Break it into parts
2. **Create sub-agents** for each part:
```
create_subagent(
    role="backend",           # Role: backend, frontend, tests, docs, etc.
    task="Implement OAuth API endpoints",  # Specific task
    scope="./src/api",        # Directory to focus on
    instructions="Use FastAPI, add JWT tokens"  # Extra context
)
```
3. **Start them**: `start_subagent(subagent_id)`
4. **Monitor**: `list_subagents()` 
5. **Cleanup when done**: `cleanup_all(confirm=true)`

### AVAILABLE TOOLS

| Tool | When to use |
|------|-------------|
| `create_subagent(role, task, scope?, instructions?)` | Create a specialized helper |
| `start_subagent(subagent_id)` | Begin sub-agent's work |
| `stop_subagent(subagent_id)` | Pause a sub-agent |
| `remove_subagent(subagent_id)` | Delete one sub-agent |
| `list_subagents()` | Check status of all |
| `cleanup_all(confirm=true)` | Remove ALL sub-agents |

### EXAMPLE WORKFLOW

Task: "Add user authentication with OAuth"

```
# Step 1: Create specialized sub-agents
create_subagent(role="backend", task="Create OAuth endpoints and JWT handling", scope="./src/api")
create_subagent(role="frontend", task="Create login/logout UI components", scope="./src/components") 
create_subagent(role="database", task="Add users table and migrations", scope="./src/models")

# Step 2: Start them
start_subagent("sub-backend-...")
start_subagent("sub-frontend-...")
start_subagent("sub-database-...")

# Step 3: Monitor progress
list_subagents()

# Step 4: When all done, cleanup
cleanup_all(confirm=true)
```

### LIMITS
- Maximum {max_subagents} sub-agents at once
- Sub-agents cannot create their own sub-agents
- Each sub-agent has isolated memory (won't see your context)
- Always cleanup when task is complete!

### IMPORTANT
You are ENCOURAGED to use sub-agents for complex tasks. Don't try to do everything yourself!
Think of sub-agents as your team members - delegate work appropriately.
""".format(max_subagents=max_subagents)
    
    if claude_md.exists():
        content = claude_md.read_text()
        if "Sub-Agent Capabilities" not in content:
            content += subagent_instructions
            claude_md.write_text(content)
    else:
        claude_md.write_text(f"# Agent Instructions\n{subagent_instructions}")
    
    console.print(f"[green]✓ Sub-agents enabled for {agent_id}[/green]")
    console.print(f"  Max sub-agents: {max_subagents}")
    console.print(f"  MCP path: {mcp_path}")
    
    return True


def disable_subagents(agent_id: str) -> bool:
    """Отключить субагентов для агента."""
    from .config import load_config

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agent_dir = agent_root / agent_id
    
    if not agent_dir.exists():
        console.print(f"[red]Agent not found: {agent_id}[/red]")
        return False
    
    mcp_json_path = agent_dir / ".mcp.json"
    
    if mcp_json_path.exists():
        try:
            mcp_config = json.loads(mcp_json_path.read_text())
            if "mcpServers" in mcp_config and "subagents" in mcp_config["mcpServers"]:
                del mcp_config["mcpServers"]["subagents"]
                mcp_json_path.write_text(json.dumps(mcp_config, indent=2))
                console.print(f"[green]✓ Sub-agents disabled for {agent_id}[/green]")
                return True
        except:
            pass
    
    console.print(f"[yellow]Sub-agents not enabled for {agent_id}[/yellow]")
    return False


def check_subagents_enabled(agent_id: str) -> bool:
    """Проверить включены ли субагенты."""
    from .config import load_config

    cfg = load_config()
    agent_root = Path(cfg.agent_root)
    agent_dir = agent_root / agent_id
    
    mcp_json_path = agent_dir / ".mcp.json"
    
    if mcp_json_path.exists():
        try:
            mcp_config = json.loads(mcp_json_path.read_text())
            return "subagents" in mcp_config.get("mcpServers", {})
        except:
            pass
    
    return False


# ============================================================================
# CLI
# ============================================================================

def cmd_enable_subagents(agent_id: str, max_subagents: int = 5):
    """CLI: Включить субагентов."""
    enable_subagents(agent_id, max_subagents)


def cmd_disable_subagents(agent_id: str):
    """CLI: Отключить субагентов."""
    disable_subagents(agent_id)


def create_subagents_commands():
    """Создать CLI команды для субагентов."""
    import typer

    def enable_cmd(
        agent_id: str = typer.Argument(..., help="Agent ID"),
        max_subagents: int = typer.Option(5, "--max", "-m", help="Max sub-agents")
    ):
        """Enable sub-agent creation for an agent."""
        enable_subagents(agent_id, max_subagents)

    def disable_cmd(
        agent_id: str = typer.Argument(..., help="Agent ID")
    ):
        """Disable sub-agent creation for an agent."""
        disable_subagents(agent_id)
    
    return enable_cmd, disable_cmd
