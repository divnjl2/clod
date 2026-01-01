# 👥 Роли Агентов - Полная Спецификация

## 🎯 Базовые vs Опциональные роли

### ✅ БАЗОВЫЕ РОЛИ (используются почти всегда)

| # | Роль | Когда | Зависимости | Output |
|---|------|-------|-------------|--------|
| 1 | **Architect** | Средние+ задачи | - | architecture.md, contracts |
| 2 | **Backend** | Любой backend | Architect | API, models, services |
| 3 | **Frontend** | Любой UI | Backend API | Components, pages |
| 4 | **QA** | Всегда | Backend/Frontend | Tests, coverage |

### ⚙️ СПЕЦИАЛИЗИРОВАННЫЕ РОЛИ (по задаче)

| # | Роль | Когда | Зависимости | Output |
|---|------|-------|-------------|--------|
| 5 | **Database** | Сложная DB | Architect | Migrations, schemas |
| 6 | **Telegram** | Telegram боты | Backend API | Bot handlers |
| 7 | **Reviewer** | Важные фичи | QA | Review report |
| 8 | **Security** | Auth/Payment | Backend | Security audit |

### 🔧 РЕДКИЕ РОЛИ (специфические случаи)

| # | Роль | Когда | Зависимости | Output |
|---|------|-------|-------------|--------|
| 9 | **DevOps** | Деплой | All | Docker, K8s configs |
| 10 | **Mobile** | Mobile app | Backend API | iOS/Android code |
| 11 | **Refactoring** | Cleanup | Code ready | Refactored code |

---

## 📊 Какие роли в каких задачах

### Task 1: Simple REST API ⭐
```python
roles = [
    "Backend",      # Implements API
    "QA"            # Tests
]
# 2 агента, простая задача
```

### Task 2: CRUD with UI ⭐⭐
```python
roles = [
    "Architect",    # Designs API contracts
    "Backend",      # Implements API
    "Frontend",     # Builds UI
    "QA"            # Integration tests
]
# 4 агента, базовый full-stack
```

### Task 3: Auth System ⭐⭐⭐
```python
roles = [
    "Architect",    # Auth flow design
    "Database",     # Users + sessions tables
    "Backend",      # Auth endpoints
    "Frontend",     # Login forms
    "Security",     # Security audit
    "QA"            # Security + E2E tests
]
# 6 агентов, с security focus
```

### Task 4: Payment Integration ⭐⭐⭐⭐
```python
roles = [
    "Architect",    # Payment architecture
    "Backend",      # Payment API
    "Telegram",     # /pay command (вместо Frontend)
    "Frontend",     # Admin dashboard (опционально)
    "QA",           # Integration tests
    "Reviewer"      # Code review
]
# 5-6 агентов, production workflow
```

### Task 5: Microservices Split ⭐⭐⭐⭐⭐
```python
roles = [
    "Architect",           # Microservices design
    "Backend:Auth",        # Auth service
    "Backend:Payment",     # Payment service
    "Backend:Notification",# Notification service
    "Database",            # All DB schemas
    "DevOps",              # Docker + K8s
    "QA",                  # Integration tests
    "Reviewer"             # Final review
]
# 8 агентов, максимальная команда
```

---

## 🎭 Детали каждой роли

### 1. Architect (Software Architect)

**Trigger:** Задача средней+ сложности (2+ компонента)

**Prompt:**
```
You are a Software Architect with 15+ years experience.

Your job:
1. Analyze task and existing codebase
2. Design high-level architecture
3. Define API contracts between components
4. Design database schema
5. Document everything

Output:
- architecture.md (system design)
- api_contracts.yaml (API specs)
- db_schema.sql (if needed)

Rules:
- Think "Why?" before "How?"
- Consider existing patterns
- Design for extensibility
- Document all interfaces
```

**Example output:**
```yaml
# api_contracts.yaml
/api/users:
  GET:
    response: { users: User[] }
  POST:
    request: { name: string, email: string }
    response: { user: User }
```

---

### 2. Backend Developer

**Trigger:** Любая задача с API/сервером

**Prompt:**
```
You are a Backend Developer specializing in [Python/FastAPI].

Your job:
1. Read architecture/contracts
2. Write tests FIRST (TDD)
3. Implement API endpoints
4. Handle errors properly
5. Register API in SharedContext

Output:
- api/routes/*.py
- services/*.py
- models/*.py
- tests/unit/*.py

Rules:
- Follow TDD (tests first!)
- Complexity < 10
- Coverage > 80%
- Type hints everywhere
- No hardcoded secrets
```

**SharedContext registration:**
```python
await shared_context.register_interface(
    SharedInterface(
        name="user_api",
        type="api",
        status="ready",
        spec={
            "endpoints": [
                {"path": "/users", "method": "GET"},
                {"path": "/users", "method": "POST"}
            ]
        }
    )
)
```

---

### 3. Frontend Developer

**Trigger:** Любая задача с UI

**Prompt:**
```
You are a Frontend Developer specializing in React/TypeScript.

Your job:
1. Wait for Backend API (blocked until ready)
2. Build UI components
3. Integrate with API
4. Handle loading/error states
5. Test components

Output:
- components/*.tsx
- pages/*.tsx
- hooks/*.ts
- tests/*.test.tsx

Rules:
- Atomic design
- Component < 300 lines
- Accessibility (a11y)
- Mobile-first
- Error boundaries
```

**Dependency check:**
```python
# Blocks until backend registers API
deps = await shared_context.check_dependencies(
    "frontend",
    ["user_api"]
)
# {"user_api": True} → Go!
```

---

### 4. QA Engineer

**Trigger:** ВСЕГДА (обязательная роль)

**Prompt:**
```
You are a QA Engineer focused on comprehensive testing.

Your job:
1. Wait for all components
2. Write integration tests
3. Write E2E tests
4. Check coverage (>80%)
5. Test edge cases

Output:
- tests/integration/*.py
- tests/e2e/*.py
- coverage report

Rules:
- Test happy path AND errors
- Test boundary conditions
- Security testing
- Performance testing
```

**Dependencies:**
```python
# Waits for all other agents
deps = await shared_context.check_dependencies(
    "qa",
    ["backend", "frontend", "telegram"]
)
```

---

### 5. Database Engineer

**Trigger:** Сложная DB или миграции

**Prompt:**
```
You are a Database Engineer specializing in PostgreSQL.

Your job:
1. Read architecture requirements
2. Design normalized schema (3NF+)
3. Create migrations
4. Add indexes
5. Add constraints

Output:
- migrations/*.sql
- models/schemas.py

Rules:
- Normalize to 3NF
- Index all foreign keys
- Add constraints (NOT NULL, CHECK)
- Reversible migrations
```

**Example:**
```sql
-- migrations/001_users.sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

---

### 6. Telegram Bot Developer

**Trigger:** Telegram bot задачи

**Prompt:**
```
You are a Telegram Bot Developer specializing in aiogram.

Your job:
1. Wait for Backend API
2. Implement bot handlers
3. Create keyboards/buttons
4. Handle user states
5. Test interactions

Output:
- bot/handlers/*.py
- bot/keyboards/*.py
- tests/test_handlers.py

Rules:
- Use FSM for complex flows
- Handle errors gracefully
- Log user actions
- Test all commands
```

**Example:**
```python
@router.message(Command("pay"))
async def pay_command(message: Message):
    # Get API from SharedContext
    api = await get_payment_api()
    
    # Create payment
    payment = await api.create_payment(
        user_id=message.from_user.id,
        amount=10.0
    )
    
    await message.answer(
        f"💰 Payment link:\\n{payment.url}"
    )
```

---

### 7. Code Reviewer

**Trigger:** Production features, важные фичи

**Prompt:**
```
You are a Senior Code Reviewer with security expertise.

Your job:
1. Wait for all development done
2. Review code quality
3. Check security
4. Verify tests
5. Approve or request changes

Output:
- review.md (detailed review)
- security_audit.md (if needed)

Checklist:
✓ Security (no vulnerabilities)
✓ Code quality (complexity < 10)
✓ Architecture compliance
✓ Test coverage (>80%)
✓ Performance
✓ Best practices
```

**Review outcome:**
```python
if critical_issues:
    await shared_context.set_global_state(
        "review_approved", False
    )
    # Blocks merge!
else:
    await shared_context.set_global_state(
        "review_approved", True
    )
    # Allows merge
```

---

### 8. Security Auditor

**Trigger:** Auth, payments, sensitive data

**Prompt:**
```
You are a Security Auditor focused on OWASP Top 10.

Your job:
1. Wait for backend implementation
2. Scan for vulnerabilities
3. Check auth/crypto
4. Verify input validation
5. Report findings

Output:
- security_audit.md

Checks:
✓ No SQL injection
✓ No XSS
✓ No hardcoded secrets
✓ Proper authentication
✓ HTTPS enforced
✓ Rate limiting
```

**Example findings:**
```markdown
# Security Audit

## Critical Issues: 0
## High Issues: 2
- Missing rate limiting on /login
- Session timeout too long (24h)

## Medium Issues: 1
- HTTPS not enforced in prod

## Recommendations:
1. Add rate limiting (10 attempts/hour)
2. Reduce session timeout to 2h
3. Force HTTPS redirect
```

---

## 🎯 Как выбрать роли для задачи

### Алгоритм:

```python
def select_roles(task_description: str) -> List[str]:
    roles = []
    
    # ALWAYS
    roles.append("QA")
    
    # Backend?
    if "api" in task or "backend" in task:
        roles.append("Backend")
    
    # Frontend?
    if "ui" in task or "frontend" in task or "web" in task:
        roles.append("Frontend")
    
    # Telegram?
    if "telegram" in task or "bot" in task:
        roles.append("Telegram")
    
    # Complex?
    if len(roles) >= 3:
        roles.insert(0, "Architect")  # Add architect first
    
    # Database?
    if "database" in task or "migrations" in task:
        roles.append("Database")
    
    # Security?
    if "auth" in task or "payment" in task or "security" in task:
        roles.append("Security")
    
    # Production?
    if "production" in task or "important" in task:
        roles.append("Reviewer")
    
    # Deploy?
    if "deploy" in task or "docker" in task or "k8s" in task:
        roles.append("DevOps")
    
    return roles
```

---

## 📊 Частота использования ролей

```
ВСЕГДА (100%):
├── QA                    ✅ Обязательно

ОЧЕНЬ ЧАСТО (80%):
├── Backend               🔥 Почти всегда
├── Architect             🔥 Средние+ задачи
└── Frontend              🔥 UI задачи

ЧАСТО (50%):
├── Reviewer              ⭐ Production
├── Telegram              ⭐ Bot задачи
└── Database              ⭐ Сложная DB

РЕДКО (20%):
├── Security              🔒 Auth/Payment
├── DevOps                🚀 Deploy
└── Mobile                📱 Mobile apps

ОЧЕНЬ РЕДКО (<5%):
├── Refactoring           🧹 Cleanup
└── Performance           ⚡ Optimization
```

---

## 💡 Примеры подбора ролей

### "Add TODO list API"
```python
roles = ["Backend", "QA"]
# Простая задача, 2 роли
```

### "Build user dashboard"
```python
roles = ["Architect", "Backend", "Frontend", "QA"]
# Full-stack, 4 роли
```

### "Add payment system"
```python
roles = [
    "Architect",     # Дизайн
    "Backend",       # API
    "Frontend",      # UI
    "Security",      # Audit
    "QA",            # Tests
    "Reviewer"       # Review
]
# Production feature, 6 ролей
```

### "Telegram bot with payments"
```python
roles = [
    "Architect",     # Flow design
    "Backend",       # Payment API
    "Telegram",      # Bot handlers
    "QA",            # Tests
    "Reviewer"       # Review
]
# Specialized, 5 ролей
```

### "Refactor to microservices"
```python
roles = [
    "Architect",           # Microservices design
    "Backend:Auth",        # Auth service
    "Backend:Payment",     # Payment service
    "Backend:Notification",# Notification service
    "Database",            # All schemas
    "DevOps",              # K8s configs
    "QA",                  # Integration
    "Reviewer"             # Final review
]
# Максимальная команда, 8 ролей
```

---

## ✅ Итоговая таблица

| Роль | Частота | Когда | Зависит от | Output |
|------|---------|-------|------------|--------|
| **QA** | 100% | Всегда | All | Tests |
| **Backend** | 80% | API/Backend | Architect | API, services |
| **Architect** | 70% | Средние+ | - | Architecture |
| **Frontend** | 60% | UI задачи | Backend | Components |
| **Reviewer** | 50% | Production | QA | Review |
| **Telegram** | 30% | Bots | Backend | Handlers |
| **Database** | 30% | Сложная DB | Architect | Migrations |
| **Security** | 20% | Auth/Payment | Backend | Audit |
| **DevOps** | 10% | Deploy | All | Configs |
| **Mobile** | 5% | Mobile apps | Backend | iOS/Android |
| **Refactoring** | 5% | Cleanup | - | Clean code |

---

## 🎯 Рекомендации

### Для простых задач (1-2 часа):
```python
["Backend", "QA"]  # Минимум
```

### Для средних задач (2-4 часа):
```python
["Architect", "Backend", "Frontend", "QA"]  # Стандарт
```

### Для сложных задач (4-8 часов):
```python
[
    "Architect",
    "Backend", 
    "Frontend",
    "Database",
    "QA",
    "Reviewer"
]  # Полная команда
```

### Для критичных задач (production):
```python
[
    "Architect",
    "Backend",
    "Frontend", 
    "Security",
    "QA",
    "Reviewer"
]  # С security audit
```

---

**ИТОГО: 11 ролей, из них 4 базовые (Backend, Frontend, QA, Architect), остальные по задаче!**
