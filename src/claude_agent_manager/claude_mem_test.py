"""
Synthetic test for claude-mem memory system.

Creates test observations and verifies they're stored correctly.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

from .claude_mem_setup import (
    get_claude_mem_paths,
    is_bun_installed,
    install_bun,
    is_worker_running,
    start_worker,
    get_worker_port,
    get_worker_stats,
    ensure_worker_running,
    diagnose_claude_mem,
)

# Test data
TEST_PROJECT = "cam-synthetic-test"
TEST_SESSION_ID = f"test-session-{int(time.time())}"


def create_test_observation(
    obs_type: str = "discovery",
    text: str = "Test observation",
    title: str = "Test Title",
    narrative: str = "This is a test narrative",
    concepts: List[str] = None,
) -> Dict[str, Any]:
    """Create a test observation record."""
    now = datetime.utcnow()
    epoch = int(now.timestamp() * 1000)

    return {
        "sdk_session_id": TEST_SESSION_ID,
        "project": TEST_PROJECT,
        "type": obs_type,
        "text": text,
        "title": title,
        "subtitle": f"Subtitle for {obs_type}",
        "facts": json.dumps(["Fact 1", "Fact 2"]),
        "narrative": narrative,
        "concepts": json.dumps(concepts or ["test", "synthetic"]),
        "files_read": json.dumps([]),
        "files_modified": json.dumps([]),
        "created_at_epoch": epoch,
        "created_at": now.isoformat() + "Z",
        "prompt_number": 1,
        "discovery_tokens": 100,
    }


def create_test_session() -> Dict[str, Any]:
    """Create a test session record."""
    now = datetime.utcnow()
    epoch = int(now.timestamp() * 1000)

    return {
        "sdk_session_id": TEST_SESSION_ID,
        "claude_session_id": f"claude-{TEST_SESSION_ID}",
        "project": TEST_PROJECT,
        "status": "active",
        "started_at_epoch": epoch,
        "started_at": now.isoformat() + "Z",
        "completed_at_epoch": None,
        "completed_at": None,
        "user_prompt": "Synthetic test session",
        "prompt_counter": 1,
        "worker_port": get_worker_port(),
    }


def import_test_data(observations: List[Dict], sessions: List[Dict] = None) -> Dict[str, Any]:
    """
    Import test data via worker API.

    Returns import stats.
    """
    port = get_worker_port()
    url = f"http://127.0.0.1:{port}/api/import"

    payload = {
        "observations": observations,
        "sessions": sessions or [],
        "summaries": [],
        "prompts": [],
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        raise RuntimeError(f"Import failed: {e.code} - {error_body}")


def search_observations(query: str, project: str = None) -> Dict[str, Any]:
    """Search observations via worker API."""
    port = get_worker_port()
    params = f"query={query}&limit=10"
    if project:
        params += f"&project={project}"

    url = f"http://127.0.0.1:{port}/api/search/observations?{params}"

    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        return {"error": str(e), "results": []}


def query_db_directly(query: str) -> List[Any]:
    """Query claude-mem DB directly."""
    paths = get_claude_mem_paths()
    db_path = paths["db"]

    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def count_observations(project: str = None) -> int:
    """Count observations in database."""
    if project:
        query = f"SELECT COUNT(*) as cnt FROM observations WHERE project = '{project}'"
    else:
        query = "SELECT COUNT(*) as cnt FROM observations"

    result = query_db_directly(query)
    return result[0]["cnt"] if result else 0


def cleanup_test_data():
    """Remove test data from database."""
    paths = get_claude_mem_paths()
    db_path = paths["db"]

    if not db_path.exists():
        return

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        cursor.execute(f"DELETE FROM observations WHERE project = ?", (TEST_PROJECT,))
        cursor.execute(f"DELETE FROM sdk_sessions WHERE project = ?", (TEST_PROJECT,))
        conn.commit()
        print(f"[CLEANUP] Removed test data for project: {TEST_PROJECT}")
    finally:
        conn.close()


def run_synthetic_test(verbose: bool = True) -> Dict[str, Any]:
    """
    Run full synthetic test of claude-mem system.

    Returns test results dict.
    """
    results = {
        "success": False,
        "steps": [],
        "errors": [],
        "observations_created": 0,
        "observations_found": 0,
    }

    def log(msg: str):
        if verbose:
            print(msg)
        results["steps"].append(msg)

    # Step 1: Diagnose current state
    log("[TEST] Step 1: Diagnosing claude-mem...")
    diag = diagnose_claude_mem()

    if not diag["plugin_installed"]:
        results["errors"].append("claude-mem plugin not installed")
        log("[FAIL] Plugin not installed. Run: /plugin install claude-mem")
        return results

    # Step 2: Ensure Bun is installed
    log("[TEST] Step 2: Checking Bun...")
    if not is_bun_installed():
        log("[TEST] Installing Bun...")
        if not install_bun(silent=False):
            results["errors"].append("Failed to install Bun")
            log("[FAIL] Bun installation failed")
            return results
        log("[OK] Bun installed")
    else:
        log("[OK] Bun already installed")

    # Step 3: Ensure worker is running
    log("[TEST] Step 3: Starting worker...")
    if not ensure_worker_running(silent=False):
        results["errors"].append("Failed to start worker")
        log("[FAIL] Worker start failed")
        return results
    log(f"[OK] Worker running on port {get_worker_port()}")

    # Step 4: Get initial count
    log("[TEST] Step 4: Checking initial observation count...")
    initial_count = count_observations()
    initial_test_count = count_observations(TEST_PROJECT)
    log(f"[INFO] Total observations: {initial_count}, test project: {initial_test_count}")

    # Step 5: Create test observations
    log("[TEST] Step 5: Creating test observations...")
    test_observations = [
        create_test_observation(
            obs_type="discovery",
            text="Discovered new memory test pattern",
            title="Memory Test Discovery",
            narrative="Testing the claude-mem observation storage system with synthetic data.",
            concepts=["testing", "memory", "synthetic"],
        ),
        create_test_observation(
            obs_type="decision",
            text="Decided to implement comprehensive tests",
            title="Testing Decision",
            narrative="Made the decision to add synthetic tests for memory verification.",
            concepts=["decision", "testing", "quality"],
        ),
        create_test_observation(
            obs_type="bugfix",
            text="Fixed memory worker startup issue",
            title="Worker Bugfix",
            narrative="Resolved issue where Bun was not installed automatically.",
            concepts=["bugfix", "worker", "bun"],
        ),
    ]

    test_sessions = [create_test_session()]

    # Step 6: Import via API
    log("[TEST] Step 6: Importing test data via API...")
    try:
        import_result = import_test_data(test_observations, test_sessions)
        log(f"[OK] Import result: {import_result}")
        results["observations_created"] = import_result.get("stats", {}).get("observationsImported", 0)
    except Exception as e:
        results["errors"].append(f"Import failed: {e}")
        log(f"[FAIL] Import error: {e}")
        return results

    # Step 7: Verify via DB
    log("[TEST] Step 7: Verifying observations in database...")
    time.sleep(0.5)  # Give DB time to commit
    final_test_count = count_observations(TEST_PROJECT)
    log(f"[INFO] Test project observations: {final_test_count}")

    # Step 8: Test search API
    log("[TEST] Step 8: Testing search API...")
    search_result = search_observations("memory test", TEST_PROJECT)
    results["observations_found"] = len(search_result.get("results", []))
    log(f"[INFO] Search found {results['observations_found']} results")

    # Step 9: Verify stats API
    log("[TEST] Step 9: Checking worker stats...")
    stats = get_worker_stats()
    if stats:
        total_obs = stats.get("database", {}).get("observations", 0)
        log(f"[OK] Worker stats: {total_obs} total observations")
    else:
        log("[WARN] Could not get worker stats")

    # Determine success
    results["success"] = (
        results["observations_created"] > 0 and
        final_test_count >= len(test_observations)
    )

    if results["success"]:
        log("[SUCCESS] All tests passed! Memory system is working.")
    else:
        log("[FAIL] Some tests failed. Check errors.")
        if results["observations_created"] == 0:
            results["errors"].append("No observations were imported")

    return results


def run_and_cleanup(verbose: bool = True) -> Dict[str, Any]:
    """Run test and cleanup afterwards."""
    try:
        results = run_synthetic_test(verbose=verbose)
        return results
    finally:
        if verbose:
            print("\n[CLEANUP] Removing test data...")
        cleanup_test_data()


# CLI interface
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Claude-mem synthetic test")
    parser.add_argument("--no-cleanup", action="store_true", help="Don't cleanup test data")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    args = parser.parse_args()

    if args.no_cleanup:
        results = run_synthetic_test(verbose=not args.quiet)
    else:
        results = run_and_cleanup(verbose=not args.quiet)

    print("\n" + "=" * 50)
    print(f"Test Result: {'PASSED' if results['success'] else 'FAILED'}")
    print(f"Observations created: {results['observations_created']}")
    print(f"Observations found via search: {results['observations_found']}")

    if results["errors"]:
        print(f"Errors: {results['errors']}")

    sys.exit(0 if results["success"] else 1)
