"""
Extended Team CLI - Complete team management commands
"""

import typer
import asyncio
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich.prompt import Prompt, Confirm

from .team_manager import TeamManager, AgentStack, MCPPermission

app = typer.Typer(name="team", help="Multi-agent team management")
console = Console()


# ============================================================================
# Team Mode Commands
# ============================================================================

@app.command()
def activate(
    project: Path = typer.Option(".", help="Project path")
):
    """Activate team mode for the project."""
    async def run():
        manager = TeamManager(project)
        result = await manager.activate_team_mode()
        
        console.print(Panel(
            f"[bold green]✓ Team Mode Activated![/bold green]\n\n"
            f"Active agents: {len(result['active_agents'])}\n"
            f"Work graph: {result['work_graph_id']}",
            title="🚀 Team Mode",
            border_style="green"
        ))
        
        # Show active agents
        table = Table(title="Active Agents")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Role", style="yellow")
        
        for agent in manager.list_agents(enabled_only=True):
            table.add_row(agent.id, agent.name, agent.role_type)
        
        console.print(table)
    
    asyncio.run(run())


@app.command()
def deactivate(
    project: Path = typer.Option(".", help="Project path")
):
    """Deactivate team mode."""
    async def run():
        manager = TeamManager(project)
        await manager.deactivate_team_mode()
        
        console.print("[yellow]Team mode deactivated[/yellow]")
    
    asyncio.run(run())


@app.command()
def status(
    project: Path = typer.Option(".", help="Project path")
):
    """Show team status and active agents."""
    async def run():
        manager = TeamManager(project)
        state = await manager.get_dashboard_state()
        
        # Mode status
        mode_status = "🟢 ACTIVE" if state['team_mode_active'] else "🔴 INACTIVE"
        console.print(f"\n[bold]Team Mode:[/bold] {mode_status}\n")
        
        # Agents summary
        console.print(f"Total agents: {state['total_agents']}")
        console.print(f"Enabled agents: {state['enabled_agents']}\n")
        
        # Agents table
        table = Table(title="Agents")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Role", style="yellow")
        table.add_column("Stack", style="blue")
        table.add_column("Status", style="bold")
        
        for agent_data in state['agents']:
            status_icon = "✅" if agent_data['enabled'] else "❌"
            table.add_row(
                agent_data['id'],
                agent_data['name'],
                agent_data['role_type'],
                agent_data['stack'],
                status_icon
            )
        
        console.print(table)
        
        # Work graph
        if state['work_graph']:
            console.print(f"\n[bold]Work Graph:[/bold] {state['work_graph']['graph_id']}")
            console.print(f"Nodes: {len(state['work_graph']['nodes'])}")
            console.print(f"Edges: {len(state['work_graph']['edges'])}")
    
    asyncio.run(run())


# ============================================================================
# Agent Management Commands
# ============================================================================

@app.command()
def add(
    role_type: str = typer.Argument(..., help="Role type (backend, frontend, qa, etc)"),
    name: str = typer.Option(..., "--name", "-n", help="Agent name"),
    stack: str = typer.Option("python", "--stack", "-s", help="Technology stack"),
    description: str = typer.Option("", "--desc", "-d", help="Agent description"),
    enabled: bool = typer.Option(True, "--enabled/--disabled", help="Enable agent"),
    project: Path = typer.Option(".", help="Project path")
):
    """Add new agent to the team."""
    async def run():
        manager = TeamManager(project)
        
        try:
            stack_enum = AgentStack(stack.lower())
        except ValueError:
            console.print(f"[red]Invalid stack: {stack}[/red]")
            console.print(f"Valid stacks: {', '.join([s.value for s in AgentStack])}")
            return
        
        agent = await manager.add_agent(
            role_type=role_type,
            name=name,
            description=description or f"{role_type.capitalize()} agent",
            stack=stack_enum,
            enabled=enabled
        )
        
        console.print(Panel(
            f"[bold green]✓ Agent Added![/bold green]\n\n"
            f"ID: {agent.id}\n"
            f"Name: {agent.name}\n"
            f"Role: {agent.role_type}\n"
            f"Stack: {agent.stack.value}\n"
            f"Enabled: {agent.enabled}",
            title="🤖 New Agent",
            border_style="green"
        ))
    
    asyncio.run(run())


@app.command()
def remove(
    agent_id: str = typer.Argument(..., help="Agent ID to remove"),
    project: Path = typer.Option(".", help="Project path"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Remove agent from the team."""
    async def run():
        manager = TeamManager(project)
        
        agent = manager.get_agent(agent_id)
        if not agent:
            console.print(f"[red]Agent not found: {agent_id}[/red]")
            return
        
        if not force:
            confirm = Confirm.ask(f"Remove agent '{agent.name}' ({agent_id})?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                return
        
        success = await manager.remove_agent(agent_id)
        if success:
            console.print(f"[green]✓ Agent removed: {agent_id}[/green]")
        else:
            console.print(f"[red]Failed to remove agent[/red]")
    
    asyncio.run(run())


@app.command()
def enable(
    agent_id: str = typer.Argument(..., help="Agent ID to enable"),
    project: Path = typer.Option(".", help="Project path")
):
    """Enable agent."""
    async def run():
        manager = TeamManager(project)
        success = await manager.toggle_agent(agent_id, True)
        
        if success:
            console.print(f"[green]✓ Agent enabled: {agent_id}[/green]")
        else:
            console.print(f"[red]Agent not found: {agent_id}[/red]")
    
    asyncio.run(run())


@app.command()
def disable(
    agent_id: str = typer.Argument(..., help="Agent ID to disable"),
    project: Path = typer.Option(".", help="Project path")
):
    """Disable agent."""
    async def run():
        manager = TeamManager(project)
        success = await manager.toggle_agent(agent_id, False)
        
        if success:
            console.print(f"[yellow]Agent disabled: {agent_id}[/yellow]")
        else:
            console.print(f"[red]Agent not found: {agent_id}[/red]")
    
    asyncio.run(run())


@app.command()
def update(
    agent_id: str = typer.Argument(..., help="Agent ID to update"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="New name"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="New description"),
    stack: Optional[str] = typer.Option(None, "--stack", "-s", help="New stack"),
    prompt: Optional[str] = typer.Option(None, "--prompt", "-p", help="System prompt file"),
    project: Path = typer.Option(".", help="Project path")
):
    """Update agent configuration."""
    async def run():
        manager = TeamManager(project)
        
        updates = {}
        if name:
            updates['name'] = name
        if description:
            updates['description'] = description
        if stack:
            try:
                updates['stack'] = AgentStack(stack.lower())
            except ValueError:
                console.print(f"[red]Invalid stack: {stack}[/red]")
                return
        if prompt:
            prompt_path = Path(prompt)
            if prompt_path.exists():
                updates['system_prompt'] = prompt_path.read_text()
            else:
                console.print(f"[red]Prompt file not found: {prompt}[/red]")
                return
        
        agent = await manager.update_agent(agent_id, **updates)
        
        if agent:
            console.print(Panel(
                f"[bold green]✓ Agent Updated![/bold green]\n\n"
                f"{agent.name} ({agent.id})\n"
                f"Updated fields: {', '.join(updates.keys())}",
                title="🔄 Update Complete",
                border_style="green"
            ))
        else:
            console.print(f"[red]Agent not found: {agent_id}[/red]")
    
    asyncio.run(run())


@app.command()
def info(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    project: Path = typer.Option(".", help="Project path")
):
    """Show detailed agent information."""
    async def run():
        manager = TeamManager(project)
        status = await manager.get_agent_status(agent_id)
        
        if 'error' in status:
            console.print(f"[red]{status['error']}[/red]")
            return
        
        # Basic info
        console.print(Panel(
            f"[bold cyan]{status['name']}[/bold cyan]\n\n"
            f"ID: {status['id']}\n"
            f"Role: {status['role_type']}\n"
            f"Stack: {status['stack']}\n"
            f"Description: {status['description']}\n"
            f"Enabled: {'✅' if status['enabled'] else '❌'}",
            title="🤖 Agent Info",
            border_style="cyan"
        ))
        
        # Skills
        if status['skills']:
            console.print("\n[bold]Skills:[/bold]")
            for skill in status['skills']:
                console.print(f"  • {skill}")
        
        # Permissions
        if status['mcp_permissions']:
            console.print("\n[bold]MCP Permissions:[/bold]")
            for perm in status['mcp_permissions']:
                console.print(f"  🔐 {perm}")
        
        # Dependencies
        if status.get('dependencies'):
            console.print("\n[bold]Dependencies:[/bold]")
            for dep in status['dependencies']:
                console.print(f"  → {dep}")
        
        # System prompt
        if status['system_prompt']:
            console.print(f"\n[bold]System Prompt:[/bold]")
            console.print(Panel(status['system_prompt'][:200] + "...", border_style="dim"))
    
    asyncio.run(run())


# ============================================================================
# MCP Permissions Commands
# ============================================================================

@app.command()
def grant(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    permission: str = typer.Argument(..., help="Permission to grant"),
    project: Path = typer.Option(".", help="Project path")
):
    """Grant MCP permission to agent."""
    async def run():
        manager = TeamManager(project)
        
        try:
            perm = MCPPermission(permission.lower())
        except ValueError:
            console.print(f"[red]Invalid permission: {permission}[/red]")
            console.print(f"Valid permissions: {', '.join([p.value for p in MCPPermission])}")
            return
        
        success = await manager.grant_permission(agent_id, perm)
        
        if success:
            console.print(f"[green]✓ Granted {perm.value} to {agent_id}[/green]")
        else:
            console.print(f"[red]Agent not found: {agent_id}[/red]")
    
    asyncio.run(run())


@app.command()
def revoke(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    permission: str = typer.Argument(..., help="Permission to revoke"),
    project: Path = typer.Option(".", help="Project path")
):
    """Revoke MCP permission from agent."""
    async def run():
        manager = TeamManager(project)
        
        try:
            perm = MCPPermission(permission.lower())
        except ValueError:
            console.print(f"[red]Invalid permission: {permission}[/red]")
            return
        
        success = await manager.revoke_permission(agent_id, perm)
        
        if success:
            console.print(f"[yellow]Revoked {perm.value} from {agent_id}[/yellow]")
        else:
            console.print(f"[red]Agent not found: {agent_id}[/red]")
    
    asyncio.run(run())


# ============================================================================
# Work Graph Commands
# ============================================================================

@app.command()
def graph(
    project: Path = typer.Option(".", help="Project path"),
    show_memory: bool = typer.Option(False, "--memory", "-m", help="Show shared memory")
):
    """Show work graph visualization."""
    async def run():
        manager = TeamManager(project)
        
        if not manager.is_team_mode_active():
            console.print("[yellow]Team mode is not active[/yellow]")
            return
        
        state = await manager.get_work_graph_state()
        
        # Create tree visualization
        tree = Tree(f"[bold]Work Graph: {state['graph_id']}[/bold]")
        
        # Add nodes
        nodes_branch = tree.add("📊 Nodes")
        for node_id, node_data in state['nodes'].items():
            node_branch = nodes_branch.add(
                f"[cyan]{node_id}[/cyan]: {node_data.get('name', 'Unknown')}"
            )
            node_branch.add(f"Status: {node_data.get('status', 'unknown')}")
        
        # Add edges
        if state['edges']:
            edges_branch = tree.add("🔗 Dependencies")
            for edge in state['edges']:
                edges_branch.add(
                    f"[yellow]{edge['from']}[/yellow] → [green]{edge['to']}[/green]"
                )
        
        # Add shared memory
        if show_memory and state['shared_memory']:
            memory_branch = tree.add("💾 Shared Memory")
            for key, value in state['shared_memory'].items():
                memory_branch.add(f"{key}: {value}")
        
        console.print(tree)
    
    asyncio.run(run())


@app.command()
def depends(
    from_agent: str = typer.Argument(..., help="Dependent agent ID"),
    to_agent: str = typer.Argument(..., help="Dependency agent ID"),
    project: Path = typer.Option(".", help="Project path")
):
    """Add dependency between agents."""
    async def run():
        manager = TeamManager(project)
        await manager.add_dependency(from_agent, to_agent)
        
        console.print(f"[green]✓ Added dependency: {from_agent} → {to_agent}[/green]")
    
    asyncio.run(run())


if __name__ == "__main__":
    app()
