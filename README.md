# 🐉 gordipack

Пак артефактов для запуска нового Горыныча — группы AI-агентов, координируемых через SQLite.

## Что это

**Горди** — методология со-работы нескольких Claude-агентов (чатов) над одним проектом.
Каждый агент — отдельная роль (COORD, CORE, STUD, TAXO, ING, EYE, ...).
Коммуникация — через общую SQLite-базу `mezosync.db`.

## Структура

```
gordipack/
├── schema/
│   └── mezosync_v1.sql          ← DDL для новой группы
├── rules/
│   ├── universal.sql            ← правила для ВСЕХ групп
│   └── domain-specific/
│       ├── data-platform.sql    ← семантика/DWH проекты
│       └── frontend-spa.sql     ← SPA/UI проекты
├── templates/
│   ├── README.md                ← как использовать архетипы
│   ├── coordinator.md           ← координатор (3P / COORD / COORD-A)
│   ├── repo-dev.md              ← владелец репо/сервиса (BE/FE/CORE/DIAL/...)
│   ├── domain-specialist.md     ← владелец знаний/канона (TAXO)
│   ├── cross-integrator.md      ← мост между системами (S2S / RCC)
│   ├── watchdog.md              ← read-only мониторинг (COST)
│   └── bridge-external.md       ← мост наружу (EYE)
├── scripts/
│   ├── init-group.py            ← создаёт новую группу
│   ├── bridge-groups.py         ← связывает две группы
│   └── export-markdown.py       ← экспорт в MD для человека
├── viewer/
│   └── index.html               ← live-viewer (drag-and-drop .db)
├── MIGRATION.md                 ← план мягкого перехода md→SQLite
└── README.md
```

## Быстрый старт

### 1. Создать группу
```bash
python scripts/init-group.py \
    --name "my-project" \
    --path "./my-project/.mezosync" \
    --domain data-platform \
    --roles coord core stud taxo
```

### 2. Собрать роли из архетипов
Каждая роль проекта = один из 6 архетипов (`templates/`) + проектная специфика:
- Имя роли, зона ответственности, путь к репо
- Гейты (какой билд/тесты)
- Источники для ребёрса (phoenix sources)

### 3. Запустить COORD → роли
Координатора первым, остальных — в отдельных чатах Claude.
Launcher = одна строка: `Прочитай {phoenix_path} и начни работать по нему.`

### 4. Смотреть статус
Открыть `viewer/index.html` в браузере, drag-and-drop файл `mezosync.db`.

## Связь между группами
```bash
python scripts/bridge-groups.py \
    --source-db "project-a/.mezosync/mezosync.db" \
    --target-db "project-b/.mezosync/mezosync.db" \
    --bidirectional
```

COORD каждой группы периодически проверяет cross_links и транслирует релевантные сообщения.

## Примеры составов (реальные проекты)

| Проект | Роли | Архетипы |
|--------|------|----------|
| **Atlas** (семантическая платформа) | COORD, CORE, ING, STUD, TAXO, RCC, EYE | coordinator + 3×repo-dev + domain-specialist + cross-integrator + bridge-external |
| **Dominal** (фитнес SaaS) | 3P, BE, FE, S2S, COST | coordinator + 2×repo-dev + cross-integrator + watchdog |
| **AIA** (AI-ассистент) | COORD-A, ADMIN, DIAL, KNOW, LLMG, PRMT, SAUTH, SPACE, STUD-A | coordinator + 8×repo-dev |

## Принципы
- **Один писатель = одна роль** — агент пишет только от своего имени
- **Append-only** — сообщения не редактируются, только дополняются
- **Phoenix** — каждый агент может быть «воскрешён» из слепка
- **Владелец решает** — push, деструктивные действия, продуктовые решения — только по слову человека
- **SQLite WAL** — параллельное чтение, один писатель в момент (busy_timeout = 5s)

## Версионирование
- Схема (`schema/`) — версионируется в этом репо
- Рабочие `.db` файлы проектов — НЕ версионируются (в .gitignore проекта)
- Экспорт в Markdown — по запросу (`export-markdown.py`)
