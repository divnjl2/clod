# Team Mode - Multi-Agent Coordination

Полноценная командная работа нескольких Claude агентов с автоматической координацией, изоляцией через git worktrees и интеллектуальным мержингом.

## 🚀 Возможности

### Что нового в Team Mode:

1. **Автоматическое планирование задач**
   - Claude анализирует задачу и создает план выполнения
   - Разбивает на подзадачи с ролями (backend, frontend, database, etc)
   - Определяет зависимости между задачами

2. **Изоляция через Worktrees**
   - Каждый агент работает в своем git worktree
   - Параллельная работа без конфликтов
   - Автоматическое создание веток

3. **Shared Context для координации**
   - Агенты общаются через shared context файл
   - Регистрация интерфейсов (API endpoints, schemas)
   - Отслеживание blockers и зависимостей
   - Real-time синхронизация

4. **Умное выполнение**
   - Sequential: по очереди
   - Parallel: все сразу
   - Smart: учитывает зависимости

5. **Автомержинг**
   - Автоматический merge в main ветку
   - Разрешение конфликтов
   - Сохранение истории

6. **AutoGen интеграция** (опционально)
   - Multi-agent conversations
   - Групповые чаты между агентами
   - Автоматическое делегирование

## 📦 Установка

```bash
# Основные зависимости (уже есть в clod)
pip install rich typer anthropic --break-system-packages

# Опционально: AutoGen для продвинутых сценариев
pip install pyautogen --break-system-packages

# Или все сразу
pip install -r requirements-team.txt --break-system-packages
```

## 🎯 Быстрый старт

### Пример 1: Простая команда

```bash
# Запуск команды на задачу
cam team run "Add CryptoBot payment integration to VPN service" --project ./vpn-service

# Claude создаст план:
# 1. [backend] Create payment API with webhook handling
# 2. [frontend] Build payment selection UI
# 3. [telegram] Add /pay command to bot
# 4. [devops] Deploy and test

# Каждый агент работает в своем worktree:
# .worktrees/task_backend/
# .worktrees/task_frontend/
# .worktrees/task_telegram/
```

### Пример 2: Dry run (только план)

```bash
# Посмотреть план без создания агентов
cam team run "Refactor authentication system" --dry-run
```

### Пример 3: С AutoGen

```bash
# Использовать AutoGen для координации
export ANTHROPIC_API_KEY=your_key

cam team autogen "Build microservices architecture" --preset fullstack
```

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                  TeamOrchestrator                        │
│  • Создает план через Claude API                        │
│  • Управляет жизненным циклом агентов                   │
│  • Координирует выполнение                              │
└─────────────────────────────────────────────────────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
┌───────▼───────┐  ┌──────▼──────┐  ┌──────▼──────┐
│  Agent 1      │  │  Agent 2    │  │  Agent 3    │
│  (Backend)    │  │  (Frontend) │  │  (Database) │
│               │  │             │  │             │
│  Worktree:    │  │  Worktree:  │  │  Worktree:  │
│  .worktrees/  │  │  .worktrees/│  │  .worktrees/│
│  backend/     │  │  frontend/  │  │  database/  │
│               │  │             │  │             │
│  Branch:      │  │  Branch:    │  │  Branch:    │
│  agent/       │  │  agent/     │  │  agent/     │
│  backend/...  │  │  frontend/.│  │  database/..│
└───────┬───────┘  └──────┬──────┘  └──────┬──────┘
        │                 │                 │
        └─────────────────┼─────────────────┘
                          │
                ┌─────────▼─────────┐
                │  Shared Context   │
                │                   │
                │  • Agent statuses │
                │  • Interfaces     │
                │  • Blockers       │
                │  • Artifacts      │
                └───────────────────┘
```

## 🔧 Как это работает

### 1. Планирование

Claude анализирует задачу и проект:

```python
orchestrator = TeamOrchestrator(project_path)
plan = await orchestrator.create_plan("Add crypto payments")

# План содержит:
# - Роли агентов (backend, frontend, etc)
# - Описание задач
# - Зависимости между задачами
# - Required/Provided интерфейсы
```

### 2. Создание агентов

Для каждой задачи создается:
- Git worktree в `.worktrees/{role}/`
- Ветка `agent/{role}/{task_id}`
- Claude Code агент с нужной ролью

```python
agent_id = await orchestrator.spawn_agent(task)
# Агент работает в изолированном worktree
```

### 3. Координация

Агенты общаются через shared context:

```python
# Backend регистрирует API
await shared_context.register_interface(SharedInterface(
    name="payment_api",
    type="api",
    spec={
        "endpoints": [...]
    },
    status="ready"
))

# Frontend проверяет готовность
deps = await shared_context.check_dependencies(
    agent_id, 
    ["payment_api"]
)
```

### 4. Выполнение

Умный режим учитывает зависимости:

```python
# Параллельно запускаются только независимые задачи
# Task 1 (database) → готова
# Task 2 (backend) зависит от Task 1 → ждет
# Task 3 (frontend) зависит от Task 2 → ждет
```

### 5. Мержинг

После завершения автоматический merge:

```bash
git merge agent/backend/payment-api
git merge agent/frontend/payment-ui
git merge agent/telegram/pay-command
```

## 📚 API Reference

### TeamOrchestrator

```python
from claude_agent_manager.team import TeamOrchestrator

orchestrator = TeamOrchestrator(
    project_path=Path("./project"),
    max_parallel=3,        # Максимум параллельных агентов
    auto_merge=True        # Автомерж после завершения
)

# Создать план
plan = await orchestrator.create_plan("Add feature X")

# Выполнить
await orchestrator.execute_plan()

# Статус
orchestrator.print_status()
```

### SharedContext

```python
from claude_agent_manager.team import SharedContext, AgentUpdate, TaskStatus

sc = SharedContext(Path(".claude-team/shared_context.json"))

# Обновить статус агента
await sc.update_agent_status(AgentUpdate(
    agent_id="agent_001",
    role="backend",
    timestamp=datetime.now().isoformat(),
    status=TaskStatus.IN_PROGRESS,
    message="Creating API",
    artifacts={"endpoints": [...]}
))

# Зарегистрировать интерфейс
await sc.register_interface(SharedInterface(
    name="payment_api",
    type="api",
    owner="agent_001",
    spec={...},
    status="ready"
))

# Проверить зависимости
deps = await sc.check_dependencies("agent_002", ["payment_api"])
```

### AutoGen Integration

```python
from claude_agent_manager.team import AutoGenTeam, TeamPresets

# Создать fullstack команду
team = TeamPresets.fullstack_team(
    project_path=Path("./project"),
    api_key="your-key"
)

# Создать агентов
architect = team.create_agent("architect", worktree_path, "Design system")
backend = team.create_agent("backend", worktree_path, "Implement API")
frontend = team.create_agent("frontend", worktree_path, "Build UI")

# Запустить групповую задачу
result = team.run_team_task(
    "Build payment system",
    [architect, backend, frontend]
)
```

## 🎭 Примеры сценариев

### Сценарий 1: Fullstack фича

```bash
cam team run "Add user profile page with avatar upload" \
  --project ./my-app \
  --parallel 3

# Создаст:
# - Backend: API для upload + user profile endpoint
# - Frontend: Profile UI component
# - Database: Schema для user avatars
# - Tests: E2E тесты
```

### Сценарий 2: Microservices рефакторинг

```bash
cam team run "Split monolith into 3 microservices: auth, payments, notifications" \
  --project ./monolith \
  --parallel 3

# Каждый агент работает над своим сервисом
# Координация через shared interfaces
```

### Сценарий 3: Добавление фичи в твой VPN проект

```bash
cam team run "Integrate CryptoBot payments: API, Telegram bot, and admin panel" \
  --project ./vpn-service \
  --parallel 3

# Agent 1: Backend - FastAPI endpoints для CryptoBot webhook
# Agent 2: Telegram - /pay команда в бота
# Agent 3: Admin - UI для просмотра платежей
```

## 🧪 Тестирование

```bash
# Запустить тесты
python test_team.py

# Тесты проверяют:
# ✓ Shared Context коммуникацию
# ✓ Dependency resolution
# ✓ Worktree isolation
# ✓ Планирование задач
```

## 🔍 Мониторинг

```bash
# Статус команды
cam team status --project ./my-project

# Вывод:
# ┌────────────────┬─────────┬─────────────┬──────────────────────┐
# │ Task           │ Role    │ Status      │ Branch               │
# ├────────────────┼─────────┼─────────────┼──────────────────────┤
# │ task_backend   │ backend │ in_progress │ agent/backend/...    │
# │ task_frontend  │ frontend│ blocked     │ agent/frontend/...   │
# │ task_telegram  │ telegram│ pending     │ agent/telegram/...   │
# └────────────────┴─────────┴─────────────┴──────────────────────┘
```

## 🛠️ Troubleshooting

### Агент заблокирован

```python
# Проверить blockers
blockers = await shared_context.get_blockers()
# {'agent_002': ['payment_api']}

# Проверить статус интерфейса
interface = await shared_context.get_interface('payment_api')
# status: "draft" -> надо завершить в backend агенте
```

### Конфликты при мержинге

```bash
# Используется встроенный conflict resolver
# Или вручную:
git checkout main
git merge agent/backend/feature --no-ff
# Разрешить конфликты
git add .
git commit
```

### AutoGen не работает

```bash
# Проверить установку
pip show pyautogen

# Проверить API key
echo $ANTHROPIC_API_KEY

# Логи
cam team autogen "task" --preset fullstack --verbose
```

## 🎯 Best Practices

1. **Четкое описание задачи**
   - ✅ "Add CryptoBot payment: backend API, Telegram /pay command, admin UI"
   - ❌ "Add payments"

2. **Правильный scope**
   - Задачи должны быть независимыми где возможно
   - Явно указывать зависимости

3. **Используйте shared context**
   - Регистрируйте все API endpoints как interfaces
   - Обновляйте статус при прогрессе

4. **Worktree изоляция**
   - Каждый агент работает только в своем worktree
   - Не трогайте чужие файлы

5. **Инкрементальные коммиты**
   - Коммитите часто
   - Понятные commit messages

## 🚀 Roadmap

- [ ] Real-time UI для мониторинга команды
- [ ] Интеграция с CrewAI
- [ ] Автоматическое тестирование после merge
- [ ] Rollback механизм
- [ ] Поддержка большего количества ролей
- [ ] LangGraph integration
- [ ] Voice coordination между агентами

## 📖 Дополнительно

- [Основной README](../README.md)
- [Worktree Manager](../docs/worktrees.md)
- [AutoGen Docs](https://microsoft.github.io/autogen/)
- [CrewAI Docs](https://docs.crewai.com/)

---

**Создано для clod - Claude Agent Manager**
Разработано с ❤️ и Claude
