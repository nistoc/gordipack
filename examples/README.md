# examples/ — sanitized примеры из реальных проектов

Три реальных развёртывания Горди на проектах разного масштаба и домена.
Конкретные коммиты, пути, баги, имена заменены на плейсхолдеры `{...}`.
Структура и паттерны — настоящие.

| Проект | Домен | Ролей | Архетипы |
|--------|-------|-------|----------|
| **semantic-platform** (на базе Atlas) | Семантическая платформа, DWH | 8 | coordinator + 3×repo-dev + domain-specialist + cross-integrator + bridge-external + tool-engineer |
| **fitness-saas** (на базе Dominal) | Фитнес SaaS, AWS | 5 | coordinator + 2×repo-dev + cross-integrator + watchdog |
| **ai-assistant** (на базе AIA) | AI-ассистент, микросервисы | 9 | coordinator + 8×repo-dev |

## Что в каждой папке

- `sync.rules.md` — боевой протокол группы (правила, формат, таймеры, эскалация)
- `phoenix.README.md` — спека формата слепков
- `phoenix.{role}.md` — примеры слепков разных архетипов
