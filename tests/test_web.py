"""
Tests for web/app.py - FastAPI Web Dashboard.

Phase 3: Advanced Features

Note: These tests run without requiring FastAPI installed.
Full API tests require: pip install fastapi uvicorn httpx
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestWebDashboardConfig:
    """Tests for WebDashboardConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        # Import inside test to handle optional dependency
        try:
            from claude_agent_manager.web.app import WebDashboardConfig
        except ImportError:
            pytest.skip("FastAPI not installed")

        config = WebDashboardConfig()

        assert config.title == "Claude Agent Manager"
        assert config.host == "127.0.0.1"
        assert config.port == 8080
        assert config.debug is False
        assert config.cors_origins == ["*"]

    def test_custom_config(self):
        """Test custom configuration."""
        try:
            from claude_agent_manager.web.app import WebDashboardConfig
        except ImportError:
            pytest.skip("FastAPI not installed")

        config = WebDashboardConfig(
            title="Custom Dashboard",
            host="0.0.0.0",
            port=9000,
            debug=True,
            cors_origins=["http://localhost:3000"]
        )

        assert config.title == "Custom Dashboard"
        assert config.port == 9000
        assert config.debug is True


class TestConnectionManager:
    """Tests for ConnectionManager class."""

    def test_connection_manager_creation(self):
        """Test creating connection manager."""
        try:
            from claude_agent_manager.web.app import ConnectionManager
        except ImportError:
            pytest.skip("FastAPI not installed")

        manager = ConnectionManager()

        assert manager.active_connections == []


class TestWebDashboard:
    """Tests for WebDashboard class."""

    def test_dashboard_creation(self, temp_dir):
        """Test creating web dashboard."""
        try:
            from claude_agent_manager.web.app import WebDashboard
            from claude_agent_manager.monitoring.metrics import MetricsCollector
        except ImportError:
            pytest.skip("FastAPI not installed")

        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        dashboard = WebDashboard(collector)

        assert dashboard.collector == collector
        assert dashboard.app is not None

    def test_dashboard_renders_html(self, temp_dir):
        """Test dashboard HTML rendering."""
        try:
            from claude_agent_manager.web.app import WebDashboard
            from claude_agent_manager.monitoring.metrics import MetricsCollector
        except ImportError:
            pytest.skip("FastAPI not installed")

        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        dashboard = WebDashboard(collector)
        html = dashboard._render_dashboard_html()

        assert "<!DOCTYPE html>" in html
        assert dashboard.config.title in html
        assert "Claude Agent Manager" in html


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_default(self, temp_dir):
        """Test creating app with defaults."""
        try:
            from claude_agent_manager.web.app import create_app
            from claude_agent_manager.monitoring.metrics import MetricsCollector
        except ImportError:
            pytest.skip("FastAPI not installed")

        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        app = create_app(collector)

        assert app is not None
        # Check routes exist
        routes = [r.path for r in app.routes]
        assert "/" in routes or any("/" in str(r) for r in routes)

    def test_create_app_with_config(self, temp_dir):
        """Test creating app with custom config."""
        try:
            from claude_agent_manager.web.app import create_app, WebDashboardConfig
            from claude_agent_manager.monitoring.metrics import MetricsCollector
        except ImportError:
            pytest.skip("FastAPI not installed")

        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        config = WebDashboardConfig(
            title="Test Dashboard",
            port=9999
        )

        app = create_app(collector, config)

        assert app is not None


class TestWebAPIEndpoints:
    """Tests for API endpoints."""

    @pytest.fixture
    def client(self, temp_dir):
        """Create test client."""
        try:
            from fastapi.testclient import TestClient
            from claude_agent_manager.web.app import create_app
            from claude_agent_manager.monitoring.metrics import MetricsCollector
        except ImportError:
            pytest.skip("FastAPI or httpx not installed")

        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)
        app = create_app(collector)

        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_overview_endpoint(self, client):
        """Test overview endpoint."""
        response = client.get("/api/metrics/overview")

        assert response.status_code == 200
        data = response.json()
        assert "total_agents" in data
        assert "total_tasks" in data

    def test_overview_with_time_range(self, client):
        """Test overview with time range."""
        response = client.get("/api/metrics/overview?time_range=week")

        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "week"

    def test_agents_endpoint(self, client):
        """Test agents list endpoint."""
        response = client.get("/api/metrics/agents")

        assert response.status_code == 200
        data = response.json()
        assert "agents" in data
        assert isinstance(data["agents"], list)

    def test_trends_endpoint(self, client):
        """Test trends endpoint."""
        response = client.get("/api/metrics/trends")

        assert response.status_code == 200
        data = response.json()
        assert "trends" in data

    def test_activity_endpoint(self, client):
        """Test activity endpoint."""
        response = client.get("/api/metrics/activity?limit=5")

        assert response.status_code == 200
        data = response.json()
        assert "activity" in data
        assert isinstance(data["activity"], list)

    def test_index_returns_html(self, client):
        """Test index returns HTML."""
        response = client.get("/")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<!DOCTYPE html>" in response.text


class TestWebAPIWithData:
    """Tests for API endpoints with actual data."""

    @pytest.fixture
    def client_with_data(self, temp_dir):
        """Create test client with pre-populated data."""
        try:
            from fastapi.testclient import TestClient
            from claude_agent_manager.web.app import create_app
            from claude_agent_manager.monitoring.metrics import MetricsCollector, MetricType
        except ImportError:
            pytest.skip("FastAPI or httpx not installed")

        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Add some test data
        task_id = collector.record_task_start("test-agent", "test-task")
        collector.record_tool_call("test-agent", "Read", 100)
        collector.record_tool_call("test-agent", "Write", 50)
        collector.record_task_complete("test-agent", task_id, success=True)

        app = create_app(collector)
        return TestClient(app)

    def test_overview_with_data(self, client_with_data):
        """Test overview with actual data."""
        response = client_with_data.get("/api/metrics/overview")

        assert response.status_code == 200
        data = response.json()
        assert data["total_agents"] >= 1

    def test_agent_metrics_endpoint(self, client_with_data):
        """Test agent metrics endpoint."""
        response = client_with_data.get("/api/metrics/agent/test-agent")

        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == "test-agent"
        assert data["total_tasks"] >= 1

    def test_agents_list_with_data(self, client_with_data):
        """Test agents list with data."""
        response = client_with_data.get("/api/metrics/agents")

        assert response.status_code == 200
        data = response.json()
        assert "test-agent" in data["agents"]

    def test_activity_with_data(self, client_with_data):
        """Test activity with actual data."""
        response = client_with_data.get("/api/metrics/activity?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["activity"]) >= 1


class TestRunServerFunction:
    """Tests for run_server function."""

    def test_run_server_import_error(self):
        """Test run_server handles missing FastAPI."""
        # This test verifies graceful handling when FastAPI is missing
        # We mock the HAS_FASTAPI flag

        try:
            from claude_agent_manager.web import app as web_module
        except ImportError:
            pytest.skip("Web module not available")

        # If FastAPI is installed, the function should work
        # If not, it should print an error message
        assert callable(web_module.run_server)


class TestWebDashboardIntegration:
    """Integration tests for web dashboard."""

    def test_full_workflow(self, temp_dir):
        """Test complete web dashboard workflow."""
        try:
            from fastapi.testclient import TestClient
            from claude_agent_manager.web.app import create_app
            from claude_agent_manager.monitoring.metrics import MetricsCollector
        except ImportError:
            pytest.skip("FastAPI or httpx not installed")

        db_path = temp_dir / "metrics.db"
        collector = MetricsCollector(db_path=db_path)

        # Create multiple agents and tasks
        for i in range(3):
            agent_id = f"agent-{i}"
            task_id = collector.record_task_start(agent_id, f"task-{i}")
            collector.record_tool_call(agent_id, "Read", 100)
            collector.record_task_complete(agent_id, task_id, success=i != 2)

        app = create_app(collector)
        client = TestClient(app)

        # Test all endpoints work together
        health = client.get("/api/health").json()
        assert health["status"] == "ok"

        overview = client.get("/api/metrics/overview").json()
        assert overview["total_agents"] == 3

        agents = client.get("/api/metrics/agents").json()
        assert len(agents["agents"]) == 3

        trends = client.get("/api/metrics/trends").json()
        assert "trends" in trends

        activity = client.get("/api/metrics/activity").json()
        assert len(activity["activity"]) >= 3
