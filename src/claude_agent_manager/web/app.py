"""
FastAPI Web Dashboard.

Web-интерфейс для мониторинга и управления агентами.

Использование:
    from claude_agent_manager.web import run_server

    run_server(port=8080)  # Запустить на порту 8080

Или через CLI:
    cam web --port 8080
"""

from __future__ import annotations

import json
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from ..monitoring.metrics import MetricsCollector, TimeRange


@dataclass
class WebDashboardConfig:
    """Конфигурация веб-дашборда."""
    title: str = "Claude Agent Manager"
    host: str = "127.0.0.1"
    port: int = 8080
    debug: bool = False
    cors_origins: List[str] = None

    def __post_init__(self):
        if self.cors_origins is None:
            self.cors_origins = ["*"]


class ConnectionManager:
    """Менеджер WebSocket соединений."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Отправить сообщение всем подключённым клиентам."""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


class WebDashboard:
    """
    FastAPI веб-дашборд.

    Предоставляет веб-интерфейс для мониторинга агентов.
    """

    def __init__(
        self,
        collector: Optional[MetricsCollector] = None,
        config: Optional[WebDashboardConfig] = None
    ):
        if not HAS_FASTAPI:
            raise ImportError(
                "FastAPI is required for web dashboard. "
                "Install with: pip install fastapi uvicorn websockets"
            )

        self.collector = collector or MetricsCollector()
        self.config = config or WebDashboardConfig()
        self.manager = ConnectionManager()
        self.app = self._create_app()

    def _create_app(self) -> FastAPI:
        """Создать FastAPI приложение."""
        app = FastAPI(
            title=self.config.title,
            description="Claude Agent Manager Web Dashboard",
            version="1.0.0"
        )

        # CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Routes
        self._setup_routes(app)

        return app

    def _setup_routes(self, app: FastAPI) -> None:
        """Настроить маршруты."""

        @app.get("/", response_class=HTMLResponse)
        async def index():
            """Главная страница дашборда."""
            return self._render_dashboard_html()

        @app.get("/api/health")
        async def health():
            """Health check."""
            return {"status": "ok", "timestamp": datetime.now().isoformat()}

        @app.get("/api/metrics/overview")
        async def get_overview(time_range: str = "day"):
            """Получить обзор метрик."""
            try:
                tr = TimeRange(time_range)
            except ValueError:
                tr = TimeRange.DAY

            perf = self.collector.get_performance_metrics(tr)
            return perf.to_dict()

        @app.get("/api/metrics/agents")
        async def get_agents():
            """Получить список агентов."""
            agents = self.collector.get_all_agents()
            return {"agents": agents}

        @app.get("/api/metrics/agent/{agent_id}")
        async def get_agent_metrics(agent_id: str, time_range: str = "day"):
            """Получить метрики агента."""
            try:
                tr = TimeRange(time_range)
            except ValueError:
                tr = TimeRange.DAY

            stats = self.collector.get_agent_stats(agent_id, tr)
            return stats.to_dict()

        @app.get("/api/metrics/trends")
        async def get_trends(time_range: str = "day"):
            """Получить тренды."""
            try:
                tr = TimeRange(time_range)
            except ValueError:
                tr = TimeRange.DAY

            trends = self.collector.get_trends(tr)
            return {"trends": trends}

        @app.get("/api/metrics/activity")
        async def get_activity(limit: int = 20):
            """Получить последнюю активность."""
            activity = self.collector.get_recent_activity(limit)
            return {"activity": activity}

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket для real-time обновлений."""
            await self.manager.connect(websocket)
            try:
                while True:
                    # Отправляем обновления каждые 5 секунд
                    await asyncio.sleep(5)

                    perf = self.collector.get_performance_metrics(TimeRange.HOUR)
                    trends = self.collector.get_trends(TimeRange.HOUR)
                    activity = self.collector.get_recent_activity(5)

                    await websocket.send_json({
                        "type": "update",
                        "timestamp": datetime.now().isoformat(),
                        "overview": perf.to_dict(),
                        "trends": trends,
                        "activity": activity
                    })

            except WebSocketDisconnect:
                self.manager.disconnect(websocket)

        @app.post("/api/metrics/cleanup")
        async def cleanup_metrics(days: int = 90):
            """Очистить старые метрики."""
            deleted = self.collector.cleanup_old_metrics(days)
            return {"deleted": deleted}

    def _render_dashboard_html(self) -> str:
        """Сгенерировать HTML дашборда."""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config.title}</title>
    <style>
        :root {{
            --bg-primary: #1a1a2e;
            --bg-secondary: #16213e;
            --bg-card: #0f3460;
            --text-primary: #eee;
            --text-secondary: #aaa;
            --accent: #e94560;
            --success: #4ade80;
            --warning: #fbbf24;
            --error: #ef4444;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
        }}

        .header {{
            background: var(--bg-secondary);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--bg-card);
        }}

        .header h1 {{
            font-size: 1.5rem;
            color: var(--accent);
        }}

        .status {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .status-dot {{
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: var(--success);
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}

        .container {{
            padding: 1.5rem;
            max-width: 1400px;
            margin: 0 auto;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 1.5rem;
        }}

        .card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 1.5rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        }}

        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}

        .card-title {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .metric-value {{
            font-size: 2.5rem;
            font-weight: bold;
            color: var(--accent);
        }}

        .metric-label {{
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        .metric-row {{
            display: flex;
            justify-content: space-between;
            padding: 0.5rem 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}

        .metric-row:last-child {{
            border-bottom: none;
        }}

        .progress-bar {{
            height: 8px;
            background: var(--bg-secondary);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.5rem;
        }}

        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent), var(--success));
            border-radius: 4px;
            transition: width 0.5s ease;
        }}

        .activity-list {{
            max-height: 300px;
            overflow-y: auto;
        }}

        .activity-item {{
            display: flex;
            gap: 1rem;
            padding: 0.75rem;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.85rem;
        }}

        .activity-time {{
            color: var(--text-secondary);
            white-space: nowrap;
        }}

        .activity-type {{
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            background: var(--bg-secondary);
        }}

        .chart-container {{
            height: 200px;
            display: flex;
            align-items: flex-end;
            gap: 4px;
            padding-top: 1rem;
        }}

        .chart-bar {{
            flex: 1;
            background: linear-gradient(to top, var(--accent), var(--success));
            border-radius: 4px 4px 0 0;
            transition: height 0.3s ease;
            min-height: 4px;
        }}

        .time-range {{
            display: flex;
            gap: 0.5rem;
        }}

        .time-btn {{
            padding: 0.5rem 1rem;
            border: none;
            background: var(--bg-secondary);
            color: var(--text-primary);
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.2s;
        }}

        .time-btn:hover, .time-btn.active {{
            background: var(--accent);
        }}

        .agents-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .agents-table th {{
            text-align: left;
            padding: 0.75rem;
            color: var(--text-secondary);
            font-weight: 500;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}

        .agents-table td {{
            padding: 0.75rem;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }}

        .badge {{
            padding: 0.2rem 0.6rem;
            border-radius: 12px;
            font-size: 0.75rem;
        }}

        .badge-success {{
            background: rgba(74, 222, 128, 0.2);
            color: var(--success);
        }}

        .badge-warning {{
            background: rgba(251, 191, 36, 0.2);
            color: var(--warning);
        }}

        .badge-error {{
            background: rgba(239, 68, 68, 0.2);
            color: var(--error);
        }}

        .full-width {{
            grid-column: 1 / -1;
        }}

        @media (max-width: 768px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <header class="header">
        <h1>{self.config.title}</h1>
        <div class="status">
            <span class="status-dot"></span>
            <span id="connection-status">Connected</span>
        </div>
    </header>

    <div class="container">
        <div class="time-range" style="margin-bottom: 1.5rem;">
            <button class="time-btn active" data-range="hour">Hour</button>
            <button class="time-btn" data-range="day">Day</button>
            <button class="time-btn" data-range="week">Week</button>
            <button class="time-btn" data-range="month">Month</button>
        </div>

        <div class="grid">
            <!-- Key Metrics -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">Total Agents</span>
                </div>
                <div class="metric-value" id="total-agents">-</div>
                <div class="metric-label">Active agents</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Tasks</span>
                </div>
                <div class="metric-value" id="total-tasks">-</div>
                <div class="metric-label">Completed tasks</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Success Rate</span>
                </div>
                <div class="metric-value" id="success-rate">-</div>
                <div class="progress-bar">
                    <div class="progress-fill" id="success-bar" style="width: 0%"></div>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">Tool Calls</span>
                </div>
                <div class="metric-value" id="total-tools">-</div>
                <div class="metric-label">Total invocations</div>
            </div>

            <!-- Activity Chart -->
            <div class="card full-width">
                <div class="card-header">
                    <span class="card-title">Activity Trend</span>
                </div>
                <div class="chart-container" id="activity-chart">
                    <!-- Bars will be generated dynamically -->
                </div>
            </div>

            <!-- Agents Table -->
            <div class="card full-width">
                <div class="card-header">
                    <span class="card-title">Agents</span>
                </div>
                <table class="agents-table">
                    <thead>
                        <tr>
                            <th>Agent ID</th>
                            <th>Tasks</th>
                            <th>Success</th>
                            <th>Tools</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody id="agents-tbody">
                        <tr><td colspan="5">Loading...</td></tr>
                    </tbody>
                </table>
            </div>

            <!-- Recent Activity -->
            <div class="card full-width">
                <div class="card-header">
                    <span class="card-title">Recent Activity</span>
                </div>
                <div class="activity-list" id="activity-list">
                    <div class="activity-item">Loading...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentTimeRange = 'hour';
        let ws = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            setupTimeRangeButtons();
            connectWebSocket();
            loadData();
        }});

        function setupTimeRangeButtons() {{
            document.querySelectorAll('.time-btn').forEach(btn => {{
                btn.addEventListener('click', () => {{
                    document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentTimeRange = btn.dataset.range;
                    loadData();
                }});
            }});
        }}

        function connectWebSocket() {{
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${{protocol}}//${{window.location.host}}/ws`);

            ws.onopen = () => {{
                document.getElementById('connection-status').textContent = 'Connected';
                document.querySelector('.status-dot').style.background = 'var(--success)';
            }};

            ws.onclose = () => {{
                document.getElementById('connection-status').textContent = 'Disconnected';
                document.querySelector('.status-dot').style.background = 'var(--error)';
                // Reconnect after 5 seconds
                setTimeout(connectWebSocket, 5000);
            }};

            ws.onmessage = (event) => {{
                const data = JSON.parse(event.data);
                if (data.type === 'update') {{
                    updateDashboard(data);
                }}
            }};
        }}

        async function loadData() {{
            try {{
                const [overview, trends, agents, activity] = await Promise.all([
                    fetch(`/api/metrics/overview?time_range=${{currentTimeRange}}`).then(r => r.json()),
                    fetch(`/api/metrics/trends?time_range=${{currentTimeRange}}`).then(r => r.json()),
                    fetch('/api/metrics/agents').then(r => r.json()),
                    fetch('/api/metrics/activity?limit=10').then(r => r.json())
                ]);

                updateOverview(overview);
                updateChart(trends.trends);
                updateAgents(agents.agents);
                updateActivity(activity.activity);
            }} catch (error) {{
                console.error('Failed to load data:', error);
            }}
        }}

        function updateDashboard(data) {{
            if (data.overview) updateOverview(data.overview);
            if (data.trends) updateChart(data.trends);
            if (data.activity) updateActivity(data.activity);
        }}

        function updateOverview(data) {{
            document.getElementById('total-agents').textContent = data.total_agents || 0;
            document.getElementById('total-tasks').textContent = data.total_tasks || 0;
            document.getElementById('total-tools').textContent = data.total_tool_calls || 0;

            const successRate = (data.success_rate || 0).toFixed(1);
            document.getElementById('success-rate').textContent = successRate + '%';
            document.getElementById('success-bar').style.width = successRate + '%';
        }}

        function updateChart(trends) {{
            const container = document.getElementById('activity-chart');
            container.innerHTML = '';

            if (!trends || trends.length === 0) {{
                container.innerHTML = '<div style="color: var(--text-secondary)">No data</div>';
                return;
            }}

            const maxCount = Math.max(...trends.map(t => t.count));

            trends.forEach(t => {{
                const bar = document.createElement('div');
                bar.className = 'chart-bar';
                const height = maxCount > 0 ? (t.count / maxCount) * 100 : 0;
                bar.style.height = height + '%';
                bar.title = `${{t.period}}: ${{t.count}}`;
                container.appendChild(bar);
            }});
        }}

        async function updateAgents(agentIds) {{
            const tbody = document.getElementById('agents-tbody');

            if (!agentIds || agentIds.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="5">No agents found</td></tr>';
                return;
            }}

            let rows = '';
            for (const agentId of agentIds.slice(0, 10)) {{
                try {{
                    const stats = await fetch(
                        `/api/metrics/agent/${{agentId}}?time_range=${{currentTimeRange}}`
                    ).then(r => r.json());

                    const rate = (stats.success_rate || 0).toFixed(0);
                    let badgeClass = 'badge-success';
                    if (rate < 50) badgeClass = 'badge-error';
                    else if (rate < 80) badgeClass = 'badge-warning';

                    rows += `
                        <tr>
                            <td>${{agentId}}</td>
                            <td>${{stats.total_tasks || 0}}</td>
                            <td>${{stats.completed_tasks || 0}}</td>
                            <td>${{stats.total_tool_calls || 0}}</td>
                            <td><span class="badge ${{badgeClass}}">${{rate}}%</span></td>
                        </tr>
                    `;
                }} catch (e) {{
                    console.error('Failed to load agent stats:', e);
                }}
            }}

            tbody.innerHTML = rows || '<tr><td colspan="5">No data</td></tr>';
        }}

        function updateActivity(activity) {{
            const container = document.getElementById('activity-list');

            if (!activity || activity.length === 0) {{
                container.innerHTML = '<div class="activity-item">No recent activity</div>';
                return;
            }}

            let html = '';
            for (const item of activity) {{
                const time = item.timestamp.split('T')[1].substring(0, 8);
                html += `
                    <div class="activity-item">
                        <span class="activity-time">${{time}}</span>
                        <span class="activity-type">${{item.type}}</span>
                        <span>${{item.agent_id}}</span>
                    </div>
                `;
            }}

            container.innerHTML = html;
        }}
    </script>
</body>
</html>
"""

    def run(self) -> None:
        """Запустить веб-сервер."""
        uvicorn.run(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info" if self.config.debug else "warning"
        )


def create_app(
    collector: Optional[MetricsCollector] = None,
    config: Optional[WebDashboardConfig] = None
) -> FastAPI:
    """
    Создать FastAPI приложение.

    Args:
        collector: MetricsCollector (опционально)
        config: Конфигурация (опционально)

    Returns:
        FastAPI приложение
    """
    dashboard = WebDashboard(collector, config)
    return dashboard.app


def run_server(
    port: int = 8080,
    host: str = "127.0.0.1",
    debug: bool = False,
    collector: Optional[MetricsCollector] = None
) -> None:
    """
    Запустить веб-сервер.

    Args:
        port: Порт
        host: Хост
        debug: Режим отладки
        collector: MetricsCollector (опционально)
    """
    if not HAS_FASTAPI:
        print("FastAPI is required for web dashboard.")
        print("Install with: pip install fastapi uvicorn websockets")
        return

    config = WebDashboardConfig(host=host, port=port, debug=debug)
    dashboard = WebDashboard(collector, config)
    dashboard.run()
