"""
Session Memory for Agents
=========================

Handles session memory storage for agents using dual-layer approach:
- PRIMARY: Graph Memory (when enabled) - semantic search, cross-session context
- FALLBACK: File-based memory - zero dependencies, always available

This is used to persist learnings between agent sessions.

Integrated from Auto-Claude memory_manager.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SessionInsights:
    """Insights from a single agent session."""

    session_number: int
    agent_id: str
    subtasks_completed: List[str] = field(default_factory=list)
    discoveries: Dict[str, Any] = field(default_factory=dict)
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    recommendations_for_next_session: List[str] = field(default_factory=list)
    files_understood: Dict[str, str] = field(default_factory=dict)
    patterns_found: List[str] = field(default_factory=list)
    gotchas_encountered: List[str] = field(default_factory=list)
    created_at: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionInsights":
        """Create from dictionary."""
        return cls(
            session_number=data.get("session_number", 0),
            agent_id=data.get("agent_id", ""),
            subtasks_completed=data.get("subtasks_completed", []),
            discoveries=data.get("discoveries", {}),
            what_worked=data.get("what_worked", []),
            what_failed=data.get("what_failed", []),
            recommendations_for_next_session=data.get("recommendations_for_next_session", []),
            files_understood=data.get("files_understood", {}),
            patterns_found=data.get("patterns_found", []),
            gotchas_encountered=data.get("gotchas_encountered", []),
            created_at=data.get("created_at"),
        )


class SessionMemory:
    """
    Manages session memory for agents.

    Provides a unified interface for saving and retrieving session insights,
    with automatic fallback from Graph Memory to file-based storage.

    Usage:
        memory = SessionMemory(memory_dir, agent_id)

        # Save session insights
        insights = SessionInsights(
            session_number=1,
            agent_id="agent-123",
            subtasks_completed=["s1", "s2"],
            what_worked=["Used proper error handling"],
        )
        memory.save_session(insights)

        # Get recent insights
        recent = memory.get_recent_insights(limit=3)

        # Get recommendations for next session
        recs = memory.get_recommendations()
    """

    MEMORY_DIR_NAME = "session_insights"

    def __init__(
        self,
        base_dir: Path,
        agent_id: str,
        use_graph_memory: bool = False,
    ):
        """
        Initialize session memory.

        Args:
            base_dir: Base directory for memory storage
            agent_id: ID of the agent
            use_graph_memory: Whether to try using graph memory first
        """
        self.base_dir = Path(base_dir)
        self.agent_id = agent_id
        self.use_graph_memory = use_graph_memory
        self._graph_memory = None

        # Ensure memory directory exists
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    @property
    def memory_dir(self) -> Path:
        """Path to memory directory."""
        return self.base_dir / self.MEMORY_DIR_NAME

    def save_session(self, insights: SessionInsights) -> Tuple[bool, str]:
        """
        Save session insights.

        Args:
            insights: Session insights to save

        Returns:
            Tuple of (success, storage_type)
        """
        insights.created_at = datetime.now().isoformat()
        insights.agent_id = self.agent_id

        # Try graph memory first if enabled
        if self.use_graph_memory:
            try:
                success = self._save_to_graph(insights)
                if success:
                    # Also save to file as backup
                    self._save_to_file(insights)
                    return True, "graph"
            except Exception as e:
                logger.warning(f"Graph memory save failed: {e}")

        # Fallback to file-based storage
        try:
            self._save_to_file(insights)
            return True, "file"
        except Exception as e:
            logger.error(f"File-based memory save failed: {e}")
            return False, "none"

    def _save_to_file(self, insights: SessionInsights) -> None:
        """Save insights to file."""
        filename = f"session_{insights.session_number:03d}.json"
        filepath = self.memory_dir / filename

        with open(filepath, "w") as f:
            json.dump(insights.to_dict(), f, indent=2)

        logger.info(f"Saved session {insights.session_number} insights to {filepath}")

    def _save_to_graph(self, insights: SessionInsights) -> bool:
        """Save insights to graph memory."""
        try:
            from .graph_memory import GraphMemory

            if self._graph_memory is None:
                self._graph_memory = GraphMemory(self.base_dir)

            # Store as a memory node
            self._graph_memory.store_memory(
                content=f"Session {insights.session_number}: {json.dumps(insights.to_dict())}",
                metadata={
                    "type": "session_insights",
                    "session_number": insights.session_number,
                    "agent_id": insights.agent_id,
                },
                category="session",
            )
            return True
        except ImportError:
            logger.debug("Graph memory not available")
            return False
        except Exception as e:
            logger.warning(f"Graph memory save failed: {e}")
            return False

    def get_recent_insights(self, limit: int = 5) -> List[SessionInsights]:
        """
        Get recent session insights.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of SessionInsights, most recent first
        """
        insights = []

        # Load from files
        session_files = sorted(
            self.memory_dir.glob("session_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        for filepath in session_files[:limit]:
            try:
                with open(filepath) as f:
                    data = json.load(f)
                insights.append(SessionInsights.from_dict(data))
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(f"Failed to load {filepath}: {e}")

        return insights

    def get_recommendations(self) -> List[str]:
        """
        Get all recommendations from recent sessions.

        Returns:
            List of recommendation strings
        """
        all_recs = []
        recent = self.get_recent_insights(limit=3)

        for insight in recent:
            all_recs.extend(insight.recommendations_for_next_session)

        # Remove duplicates while preserving order
        seen = set()
        unique_recs = []
        for rec in all_recs:
            if rec not in seen:
                seen.add(rec)
                unique_recs.append(rec)

        return unique_recs

    def get_patterns(self) -> List[str]:
        """
        Get all patterns discovered in recent sessions.

        Returns:
            List of pattern descriptions
        """
        all_patterns = []
        recent = self.get_recent_insights(limit=5)

        for insight in recent:
            all_patterns.extend(insight.patterns_found)

        # Remove duplicates
        return list(set(all_patterns))

    def get_gotchas(self) -> List[str]:
        """
        Get all gotchas encountered in recent sessions.

        Returns:
            List of gotcha descriptions
        """
        all_gotchas = []
        recent = self.get_recent_insights(limit=5)

        for insight in recent:
            all_gotchas.extend(insight.gotchas_encountered)

        # Remove duplicates
        return list(set(all_gotchas))

    def get_files_understood(self) -> Dict[str, str]:
        """
        Get map of files understood from recent sessions.

        Returns:
            Dict mapping file path to understanding description
        """
        files = {}
        recent = self.get_recent_insights(limit=5)

        for insight in recent:
            files.update(insight.files_understood)

        return files

    def get_context_for_subtask(self, subtask_description: str) -> str:
        """
        Get relevant context for a subtask.

        Args:
            subtask_description: Description of the subtask

        Returns:
            Formatted context string
        """
        sections = ["## Session Memory Context\n"]

        # Get recommendations
        recs = self.get_recommendations()
        if recs:
            sections.append("### Recommendations from Previous Sessions\n")
            for rec in recs[:5]:
                sections.append(f"- {rec}\n")
            sections.append("\n")

        # Get gotchas
        gotchas = self.get_gotchas()
        if gotchas:
            sections.append("### Known Gotchas\n")
            for gotcha in gotchas[:5]:
                sections.append(f"- {gotcha}\n")
            sections.append("\n")

        # Get patterns
        patterns = self.get_patterns()
        if patterns:
            sections.append("### Discovered Patterns\n")
            for pattern in patterns[:5]:
                sections.append(f"- {pattern}\n")
            sections.append("\n")

        if len(sections) == 1:
            return ""  # No context available

        return "".join(sections)

    def get_total_sessions(self) -> int:
        """Get total number of saved sessions."""
        return len(list(self.memory_dir.glob("session_*.json")))

    def get_total_subtasks_completed(self) -> int:
        """Get total subtasks completed across all sessions."""
        total = 0
        for insight in self.get_recent_insights(limit=100):
            total += len(insight.subtasks_completed)
        return total


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


def save_session_insights(
    base_dir: Path,
    session_number: int,
    agent_id: str,
    insights_data: Dict,
) -> Tuple[bool, str]:
    """
    Convenience function to save session insights.

    Args:
        base_dir: Base directory for memory storage
        session_number: Session number
        agent_id: Agent ID
        insights_data: Dictionary with insights data

    Returns:
        Tuple of (success, storage_type)
    """
    insights = SessionInsights(
        session_number=session_number,
        agent_id=agent_id,
        subtasks_completed=insights_data.get("subtasks_completed", []),
        discoveries=insights_data.get("discoveries", {}),
        what_worked=insights_data.get("what_worked", []),
        what_failed=insights_data.get("what_failed", []),
        recommendations_for_next_session=insights_data.get("recommendations_for_next_session", []),
        files_understood=insights_data.get("files_understood", {}),
        patterns_found=insights_data.get("patterns_found", []),
        gotchas_encountered=insights_data.get("gotchas_encountered", []),
    )

    memory = SessionMemory(base_dir, agent_id)
    return memory.save_session(insights)


def get_session_context(
    base_dir: Path,
    agent_id: str,
    subtask_description: str = "",
) -> str:
    """
    Get session context for an agent.

    Args:
        base_dir: Base directory for memory storage
        agent_id: Agent ID
        subtask_description: Optional subtask description for relevance

    Returns:
        Formatted context string
    """
    memory = SessionMemory(base_dir, agent_id)
    return memory.get_context_for_subtask(subtask_description)
