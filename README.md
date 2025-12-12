# Claude Agent Manager (Python)

Windows-first CLI-менеджер для запуска **изолированных “агентов” Claude Code** вместе с **claude-mem** (память/вьювер) на отдельных портах и в отдельных data-dir.

## Что решает
- Один логин Claude Code на пользователя Windows (единые креды).
- `agent = purpose + project + port + memory dir + pm2 worker + terminal + viewer`.
- Прозрачный реестр агентов: что запущено/что закрыто.
- Точное закрытие агента: pm2 worker + cmd-окно + viewer + (опционально) удаление памяти.
- Раскладка окон (tile) для 4 агентов 2x2.

## Быстрый старт

### 0) Предпосылки (однократно)
1. Установи Node.js LTS.
2. Убедись, что глобальная npm-папка в PATH (обычно `%APPDATA%\npm`), иначе `claude` может “не находиться”.
3. Установи Claude Code и PM2:
   - `npm install -g @anthropic-ai/claude-code`
   - `npm install -g pm2`
4. Поставь/собери `claude-mem` (как у тебя сейчас) и запомни путь до `worker-service.cjs`.

### 1) Установка этого менеджера
```powershell
cd C:\path\to\claude-agent-manager
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -e .
```

### 2) Настройка путей (один раз)
```powershell
cam config --claude-mem-root "C:\Users\Administrator\Desktop\claude-mem" --worker-script "C:\Users\Administrator\Desktop\claude-mem\plugin\scripts\worker-service.cjs" --browser "edge-app"
```

### 3) Создать агента
```powershell
cam new --purpose "kyc-licensing" --project "C:\repo\cex-suite"
```

### 4) Список агентов
```powershell
cam list
```

### 5) Остановить агента
```powershell
cam stop <agent_id> --purge
```

### 6) Раскладка последних 4 агентов
```powershell
cam tile --count 4
```

## Примечания по браузеру
- `edge-app` — рекомендуется для раскладки окон: создаёт отдельное окно/процесс на URL.
- `default` — системный браузер (PID может не отслеживаться).
- `path:<exe>` — явно указанный браузер.

## Директории
- Реестр и память по агентам: `%USERPROFILE%\.claude-agents\<agent_id>\`
- Конфиг менеджера: `%USERPROFILE%\.cam\config.json`
