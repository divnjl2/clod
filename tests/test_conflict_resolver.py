"""
Tests for git/conflict_resolver.py - AI-powered Git Conflict Resolver.

Phase 2: Conflict Resolution
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claude_agent_manager.git.conflict_resolver import (
    ConflictResolver,
    ConflictInfo,
    MergeResult,
    ConflictSeverity,
    MergeStrategy,
    print_conflict,
)


class TestConflictSeverity:
    """Tests for ConflictSeverity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert ConflictSeverity.LOW.value == "low"
        assert ConflictSeverity.MEDIUM.value == "medium"
        assert ConflictSeverity.HIGH.value == "high"


class TestMergeStrategy:
    """Tests for MergeStrategy enum."""

    def test_strategy_values(self):
        """Test strategy enum values."""
        assert MergeStrategy.OURS.value == "ours"
        assert MergeStrategy.THEIRS.value == "theirs"
        assert MergeStrategy.BOTH.value == "both"
        assert MergeStrategy.MANUAL.value == "manual"
        assert MergeStrategy.AI_MERGE.value == "ai_merge"


class TestConflictInfo:
    """Tests for ConflictInfo dataclass."""

    def test_conflict_info_creation(self):
        """Test creating conflict info."""
        conflict = ConflictInfo(
            file_path="src/main.py",
            start_line=10,
            end_line=20,
            ours_content="def foo(): pass",
            theirs_content="def foo(): return None"
        )

        assert conflict.file_path == "src/main.py"
        assert conflict.start_line == 10
        assert conflict.end_line == 20
        assert conflict.ours_content == "def foo(): pass"
        assert conflict.theirs_content == "def foo(): return None"
        assert conflict.severity == ConflictSeverity.MEDIUM

    def test_conflict_info_with_all_fields(self):
        """Test conflict info with all optional fields."""
        conflict = ConflictInfo(
            file_path="src/main.py",
            start_line=10,
            end_line=20,
            ours_content="foo",
            theirs_content="bar",
            base_content="baz",
            severity=ConflictSeverity.HIGH,
            suggested_strategy=MergeStrategy.AI_MERGE,
            resolution="resolved",
            explanation="Test explanation"
        )

        assert conflict.base_content == "baz"
        assert conflict.severity == ConflictSeverity.HIGH
        assert conflict.suggested_strategy == MergeStrategy.AI_MERGE
        assert conflict.resolution == "resolved"


class TestMergeResult:
    """Tests for MergeResult dataclass."""

    def test_merge_result_success(self):
        """Test successful merge result."""
        result = MergeResult(
            success=True,
            file_path="src/main.py",
            merged_content="merged code",
            explanation="All conflicts resolved"
        )

        assert result.success is True
        assert result.merged_content == "merged code"

    def test_merge_result_failure(self):
        """Test failed merge result."""
        conflict = ConflictInfo(
            file_path="src/main.py",
            start_line=1,
            end_line=10,
            ours_content="a",
            theirs_content="b"
        )

        result = MergeResult(
            success=False,
            file_path="src/main.py",
            conflicts_remaining=[conflict],
            explanation="Need manual review"
        )

        assert result.success is False
        assert len(result.conflicts_remaining) == 1

    def test_merge_result_to_dict(self):
        """Test converting result to dict."""
        result = MergeResult(
            success=True,
            file_path="src/main.py",
            conflicts_resolved=[ConflictInfo(
                file_path="src/main.py",
                start_line=1,
                end_line=5,
                ours_content="a",
                theirs_content="b"
            )],
            explanation="Resolved 1 conflict"
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["file_path"] == "src/main.py"
        assert data["conflicts_resolved"] == 1
        assert data["conflicts_remaining"] == 0


class TestConflictResolver:
    """Tests for ConflictResolver class."""

    def test_resolver_creation(self, temp_dir):
        """Test creating resolver."""
        resolver = ConflictResolver(temp_dir)

        assert resolver.project_path == temp_dir.resolve()
        assert resolver.enable_ai is True

    def test_resolver_creation_no_ai(self, temp_dir):
        """Test creating resolver with AI disabled."""
        resolver = ConflictResolver(temp_dir, enable_ai=False)

        assert resolver.enable_ai is False


class TestConflictParsing:
    """Tests for conflict parsing."""

    def test_parse_simple_conflict(self, temp_dir):
        """Test parsing a simple conflict."""
        resolver = ConflictResolver(temp_dir)

        # Create file with conflict markers
        conflict_file = temp_dir / "conflict.py"
        conflict_file.write_text(
            "normal line\n"
            "<<<<<<< HEAD\n"
            "ours version\n"
            "=======\n"
            "theirs version\n"
            ">>>>>>> feature\n"
            "after conflict\n"
        )

        conflicts = resolver.parse_conflicts(conflict_file)

        assert len(conflicts) == 1
        assert conflicts[0].ours_content == "ours version"
        assert conflicts[0].theirs_content == "theirs version"

    def test_parse_multiple_conflicts(self, temp_dir):
        """Test parsing multiple conflicts."""
        resolver = ConflictResolver(temp_dir)

        conflict_file = temp_dir / "multi.py"
        conflict_file.write_text(
            "<<<<<<< HEAD\n"
            "first ours\n"
            "=======\n"
            "first theirs\n"
            ">>>>>>> branch\n"
            "\n"
            "middle code\n"
            "\n"
            "<<<<<<< HEAD\n"
            "second ours\n"
            "=======\n"
            "second theirs\n"
            ">>>>>>> branch\n"
        )

        conflicts = resolver.parse_conflicts(conflict_file)

        assert len(conflicts) == 2
        assert conflicts[0].ours_content == "first ours"
        assert conflicts[1].ours_content == "second ours"

    def test_parse_no_conflicts(self, temp_dir):
        """Test parsing file without conflicts."""
        resolver = ConflictResolver(temp_dir)

        clean_file = temp_dir / "clean.py"
        clean_file.write_text("def foo(): pass\n")

        conflicts = resolver.parse_conflicts(clean_file)

        assert len(conflicts) == 0

    def test_parse_nonexistent_file(self, temp_dir):
        """Test parsing nonexistent file."""
        resolver = ConflictResolver(temp_dir)

        conflicts = resolver.parse_conflicts(temp_dir / "nonexistent.py")

        assert len(conflicts) == 0


class TestSeverityAssessment:
    """Tests for conflict severity assessment."""

    def test_severity_identical_content(self, temp_dir):
        """Test LOW severity for identical content."""
        resolver = ConflictResolver(temp_dir)

        severity = resolver._assess_severity("same", "same")

        assert severity == ConflictSeverity.LOW

    def test_severity_whitespace_only(self, temp_dir):
        """Test LOW severity for whitespace differences."""
        resolver = ConflictResolver(temp_dir)

        severity = resolver._assess_severity("foo bar", "foo  bar")

        assert severity == ConflictSeverity.LOW

    def test_severity_empty_side(self, temp_dir):
        """Test LOW severity when one side is empty."""
        resolver = ConflictResolver(temp_dir)

        severity = resolver._assess_severity("", "some content")

        assert severity == ConflictSeverity.LOW

    def test_severity_high_for_function_changes(self, temp_dir):
        """Test HIGH severity for function definition changes."""
        resolver = ConflictResolver(temp_dir)

        severity = resolver._assess_severity(
            "def foo(): pass",
            "x = 5"  # No def
        )

        assert severity == ConflictSeverity.HIGH

    def test_severity_high_for_class_changes(self, temp_dir):
        """Test HIGH severity for class definition changes."""
        resolver = ConflictResolver(temp_dir)

        severity = resolver._assess_severity(
            "class Foo: pass",
            "x = Foo()"  # No class
        )

        assert severity == ConflictSeverity.HIGH

    def test_severity_medium_default(self, temp_dir):
        """Test MEDIUM severity by default."""
        resolver = ConflictResolver(temp_dir)

        severity = resolver._assess_severity(
            "x = 5",
            "x = 10"
        )

        assert severity == ConflictSeverity.MEDIUM


class TestStrategySelection:
    """Tests for merge strategy selection."""

    def test_strategy_identical(self, temp_dir):
        """Test OURS for identical content."""
        resolver = ConflictResolver(temp_dir)

        strategy = resolver._suggest_strategy("same", "same", None)

        assert strategy == MergeStrategy.OURS

    def test_strategy_ours_empty(self, temp_dir):
        """Test THEIRS when ours is empty."""
        resolver = ConflictResolver(temp_dir)

        strategy = resolver._suggest_strategy("", "content", None)

        assert strategy == MergeStrategy.THEIRS

    def test_strategy_theirs_empty(self, temp_dir):
        """Test OURS when theirs is empty."""
        resolver = ConflictResolver(temp_dir)

        strategy = resolver._suggest_strategy("content", "", None)

        assert strategy == MergeStrategy.OURS

    def test_strategy_only_theirs_changed(self, temp_dir):
        """Test THEIRS when only theirs changed from base."""
        resolver = ConflictResolver(temp_dir)

        strategy = resolver._suggest_strategy("base", "new", "base")

        assert strategy == MergeStrategy.THEIRS

    def test_strategy_only_ours_changed(self, temp_dir):
        """Test OURS when only ours changed from base."""
        resolver = ConflictResolver(temp_dir)

        strategy = resolver._suggest_strategy("new", "base", "base")

        assert strategy == MergeStrategy.OURS


class TestConflictResolution:
    """Tests for resolving conflicts."""

    def test_resolve_ours_strategy(self, temp_dir):
        """Test resolving with OURS strategy."""
        resolver = ConflictResolver(temp_dir)

        conflict = ConflictInfo(
            file_path="test.py",
            start_line=1,
            end_line=5,
            ours_content="our code",
            theirs_content="their code",
            suggested_strategy=MergeStrategy.OURS
        )

        resolved = resolver.resolve_conflict(conflict)

        assert resolved.resolution == "our code"
        assert "our version" in resolved.explanation.lower()

    def test_resolve_theirs_strategy(self, temp_dir):
        """Test resolving with THEIRS strategy."""
        resolver = ConflictResolver(temp_dir)

        conflict = ConflictInfo(
            file_path="test.py",
            start_line=1,
            end_line=5,
            ours_content="our code",
            theirs_content="their code",
            suggested_strategy=MergeStrategy.THEIRS
        )

        resolved = resolver.resolve_conflict(conflict)

        assert resolved.resolution == "their code"
        assert "their version" in resolved.explanation.lower()

    def test_resolve_both_strategy(self, temp_dir):
        """Test resolving with BOTH strategy."""
        resolver = ConflictResolver(temp_dir)

        conflict = ConflictInfo(
            file_path="test.py",
            start_line=1,
            end_line=5,
            ours_content="line1\nline2",
            theirs_content="line1\nline3",
            suggested_strategy=MergeStrategy.BOTH
        )

        resolved = resolver.resolve_conflict(conflict)

        # Should combine both versions
        assert "line1" in resolved.resolution
        assert "line2" in resolved.resolution
        assert "line3" in resolved.resolution

    def test_resolve_manual_strategy(self, temp_dir):
        """Test resolving with MANUAL strategy."""
        resolver = ConflictResolver(temp_dir)

        conflict = ConflictInfo(
            file_path="test.py",
            start_line=1,
            end_line=5,
            ours_content="complex",
            theirs_content="different",
            suggested_strategy=MergeStrategy.MANUAL
        )

        resolved = resolver.resolve_conflict(conflict)

        assert resolved.resolution is None
        assert "manual" in resolved.explanation.lower()

    def test_resolve_ai_merge_strategy(self, temp_dir):
        """Test resolving with AI_MERGE strategy."""
        resolver = ConflictResolver(temp_dir, enable_ai=True)

        conflict = ConflictInfo(
            file_path="test.py",
            start_line=1,
            end_line=5,
            ours_content="code version one",
            theirs_content="code version two",
            suggested_strategy=MergeStrategy.AI_MERGE
        )

        resolved = resolver.resolve_conflict(conflict)

        # Should have some resolution
        assert resolved.resolution is not None
        assert "ai" in resolved.explanation.lower()


class TestFileConflictResolution:
    """Tests for resolving file conflicts."""

    def test_resolve_file_not_found(self, temp_dir):
        """Test resolving nonexistent file."""
        resolver = ConflictResolver(temp_dir)

        result = resolver.resolve_file_conflicts(temp_dir / "missing.py")

        assert result.success is False
        assert "not found" in result.explanation.lower()

    def test_resolve_file_no_conflicts(self, temp_dir):
        """Test resolving file without conflicts."""
        resolver = ConflictResolver(temp_dir)

        clean_file = temp_dir / "clean.py"
        clean_file.write_text("def foo(): pass\n")

        result = resolver.resolve_file_conflicts(clean_file)

        assert result.success is True
        assert "no conflicts" in result.explanation.lower()

    def test_resolve_file_with_simple_conflicts(self, temp_dir):
        """Test resolving file with simple conflicts."""
        resolver = ConflictResolver(temp_dir)

        conflict_file = temp_dir / "simple.py"
        conflict_file.write_text(
            "<<<<<<< HEAD\n"
            "\n"  # Empty ours
            "=======\n"
            "added content\n"
            ">>>>>>> feature\n"
        )

        result = resolver.resolve_file_conflicts(conflict_file)

        # Empty ours -> should use theirs
        assert result.success is True
        assert len(result.conflicts_resolved) == 1


class TestMergeBoth:
    """Tests for _merge_both method."""

    def test_merge_both_unique_lines(self, temp_dir):
        """Test merging with unique lines."""
        resolver = ConflictResolver(temp_dir)

        result = resolver._merge_both(
            "line1\nline2",
            "line3\nline4",
            None
        )

        assert "line1" in result
        assert "line2" in result
        assert "line3" in result
        assert "line4" in result

    def test_merge_both_overlapping_lines(self, temp_dir):
        """Test merging with overlapping lines."""
        resolver = ConflictResolver(temp_dir)

        result = resolver._merge_both(
            "common\nours_only",
            "common\ntheirs_only",
            None
        )

        # Should have all lines without duplication
        lines = result.split('\n')
        assert lines.count("common") == 1


class TestCanCombine:
    """Tests for _can_combine method."""

    def test_can_combine_with_common(self, temp_dir):
        """Test can combine when there's majority common content."""
        resolver = ConflictResolver(temp_dir)

        # Need >50% common lines for _can_combine to return True
        result = resolver._can_combine(
            "common1\ncommon2\nours",
            "common1\ncommon2\ntheirs"
        )

        assert result is True

    def test_cannot_combine_different(self, temp_dir):
        """Test cannot combine when completely different."""
        resolver = ConflictResolver(temp_dir)

        result = resolver._can_combine(
            "completely\ndifferent",
            "nothing\ncommon"
        )

        assert result is False


class TestPrintConflict:
    """Tests for print_conflict function."""

    def test_print_conflict(self, capsys):
        """Test printing conflict info."""
        conflict = ConflictInfo(
            file_path="src/main.py",
            start_line=10,
            end_line=20,
            ours_content="def ours(): pass",
            theirs_content="def theirs(): pass",
            severity=ConflictSeverity.MEDIUM,
            suggested_strategy=MergeStrategy.AI_MERGE
        )

        print_conflict(conflict)

        captured = capsys.readouterr()
        assert "src/main.py" in captured.out
        assert "10" in captured.out

    def test_print_conflict_with_resolution(self, capsys):
        """Test printing conflict with resolution."""
        conflict = ConflictInfo(
            file_path="test.py",
            start_line=1,
            end_line=5,
            ours_content="ours",
            theirs_content="theirs",
            resolution="resolved content"
        )

        print_conflict(conflict)

        captured = capsys.readouterr()
        assert "resolved content" in captured.out.lower() or "Resolution" in captured.out
