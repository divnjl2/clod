"""Git utilities module."""

from .conflict_resolver import ConflictResolver, MergeResult, ConflictInfo
from .changelog import ChangelogGenerator, ChangelogEntry

__all__ = [
    "ConflictResolver",
    "MergeResult",
    "ConflictInfo",
    "ChangelogGenerator",
    "ChangelogEntry"
]
