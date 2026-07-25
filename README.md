# 🐉 gordipack

Пак артефактов для запуска нового Горыныча — группы AI-агентов, координируемых через SQLite.

> **Синхронизировано с живым рантаймом 2026-07-25 (Фаза 4).** Шаблон был снят 12.07 на откате
> Фазы 4 и отставал от эталонного контура на все главные уроки. Что изменилось и что стоит перенять
> команде с собственной системой коллег — **[`DELTA-2026-07-lessons-since-phase4.md`](DELTA-2026-07-lessons-since-phase4.md)**.
> Текущая схема — `schema/mezosync_v2.sql`; координация — **только БД** (md заморожены, см. `MIGRATION.md`).

## Что это

**Горди** — методология со-работы нескольких Claude-агентов (чатов) над одним проектом.
Каждый агент — отдельная роль (COORD, CORE, STUD, TAXO, ING, OPSSRE, ...).
Коммуникация — через общую SQLite-базу `mezosync.db` (**единственный источник координации — Фаза 4**).

## Структура

```
gordipack/
├── schema/
│   ├── mezosync_v1.sql          ← DDL v1 (история)
│   └── mezosync_v2.sql          ← DDL текущий (Фаза 4: +read_batches, role_status,
│                                   stats_log, messages_history, VIEW messages_all; phoenix 7 секций)
├── rules/
│   ├── universal.sql            ← правила для ВСЕХ групп (+ v2-блок операционных правил)
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
│   ├── ops-sre.md               ← раскатка/стоимость/эксплуатация (OPSSRE) ← новый
│   └── bridge-external.md       ← мост наружу
├── scripts/                     ← при init-group КОПИРУЮТСЯ в <container>/.mezosync/scripts/
│   ├── init-group.py · bridge-groups.py           ← бутстрап группы / связь групп
│   ├── read-messages.py · write-message.py        ← лента (read: разрезанный ACK-токен)
│   ├── broadcast.py · read-broadcasts.py          ← общий канал
│   ├── read-phoenix.py · save-phoenix.py          ← воскрешение роли из БД (7 секций)
│   ├── guard-all.py (+ guard-utc/-scripts-drift/   ← ВСЕ гарды одним вызовом
│   │   -write-without-read/-stub-expectations)       («механизм > дисциплина»)
│   ├── set-rule.py · set-registry.py              ← правила / реестр (инварианты, треки)
│   ├── backup-db.py · dashboard.py · check-errors.py · stats.py · backlog.py
│   └── export-markdown.py · export-rules.py · export-channels.py  ← человекочитаемый вид из БД
├── viewer/
│   └── index.html               ← live-viewer (drag-and-drop .db)
├── DELTA-2026-07-lessons-since-phase4.md  ← дельта/уроки с 12.07 (для передачи команде)
├── MIGRATION.md                 ← фазовая модель перехода md→SQLite (Фаза 4 достигнута)
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
Каждая роль проекта = один из 7 архетипов (`templates/`) + проектная специфика:
- Имя роли (токен — ВЕРХНИМ регистром везде), зона ответственности, путь к репо
- Гейты (какой билд/тесты)
- Источники для ребёрса (phoenix sources) — 7 секций

### 3. Запустить COORD → роли
Координатора первым, остальных — в отдельных чатах Claude.
Launcher = одна строка, читающая слепок ИЗ БД (Фаза 4 — не из .md):
`python .mezosync/scripts/read-phoenix.py --db .mezosync/mezosync.db --role <РОЛЬ>`
Роль первым ходом: `guard-all.py` → слепок → поднять ритм чтения ленты (`rhythm-survives-rebirth`).

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
| **Atlas** (семантическая платформа) | COORD, CORE, ING, STUD, TAXO, RCC, **OPSSRE** | coordinator + 3×repo-dev + domain-specialist + cross-integrator + ops-sre |
| **Dominal** (фитнес SaaS) | 3P, BE, FE, S2S, COST | coordinator + 2×repo-dev + cross-integrator + watchdog |
| **AIA** (AI-ассистент) | COORD-A, ADMIN, DIAL, KNOW, LLMG, PRMT, SAUTH, SPACE, STUD-A | coordinator + 8×repo-dev |

> Реестр ролей ЖИВОЙ (правило `role-roster-and-zones`): роли рождаются, спят по слову (дормант) и
> закрываются (апоптоз). Пример: в Atlas EYE и GRF закрыты 16.07, OPSSRE заведён 25.07 — «спит по
> слову» обязано быть отличимо от «закрыт» (см. `role-lifecycle` в `rules/universal.sql`).

## Принципы
- **Один писатель = одна роль** — агент пишет только от своего имени
- **Append-only** — сообщения не редактируются, только дополняются
- **БД — единственный источник координации** (Фаза 4): md заморожены, человекочитаемый вид генерируется из БД
- **Phoenix из 7 секций** — каждый агент воскрешается из слепка ИЗ БД (`read-phoenix.py`)
- **Механизм > дисциплина** — `guard-all.py` при каждом пробуждении/цикле, а не «когда вспомнили»
- **Чтение ленты — разрезанный ACK-токен** — чтение не двигает курсор, ack отдельным вызовом (анти-обрезка)
- **Владелец решает** — push, деструктивные действия, продуктовые решения — только по живому слову человека
- **SQLite WAL** — параллельное чтение, один писатель в момент (busy_timeout = 5s)
- **Время — UTC везде** с явным суффиксом (две шкалы порождают фантомные «лаги» = разница зон)

## Версионирование
- Схема (`schema/`) — версионируется в этом репо
- Рабочие `.db` файлы проектов — НЕ версионируются (в .gitignore проекта)
- Экспорт в Markdown — по запросу (`export-markdown.py`)
