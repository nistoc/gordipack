# CLAUDE.md — gordipack

Пак артефактов «Горди»: схема SQLite-базы координации, стартовый свод правил, архетипы ролей и
инструменты на Python (только stdlib), из которых `scripts/init-group.py` собирает **контур** —
группу Claude-агентов с общей базой `.mezosync/mezosync.db`. Плюс Перископ (`src/` на C# и `srcclient/`
на React) — окно просмотра базы только на чтение.

Что это и как устроено — [`README.md`](README.md); версии контура и порядок обновления —
[`UPGRADE.md`](UPGRADE.md); переход md → SQLite — [`MIGRATION.md`](MIGRATION.md); Перископ —
`src/README.md`, `srcclient/README.md`; расширения, навыки, хуки — `plugins/`, `skills/`, `hooks/` (у каждого
свой README). AGENTS.md и .cursorrules в repo нет.

Этот файл — про работу с **репозиторием пака**. `CLAUDE.md` контура (его судят `guard-all.py`,
`guard-printed-forms.py`, `guard-launcher-forms.py`) — другой файл: инструменты ищут его в каталоге-контейнере
контура (`container_root()/CLAUDE.md`), а не в корне пака.

## Структура

| Каталог | Что в нём |
|---|---|
| `scripts/` | инструменты контура (68 `.py`); `init-group.py` копирует их в `<контейнер>/.mezosync/scripts/` |
| `scripts/migrations/` | шаги схемы `YYYYMMDD-тема.py`; порядок — `STEPS` в `scripts/schema_step_order.py` |
| `schema/` | DDL `mezosync_v1…v6.sql`; сборка контура берёт самый свежий файл |
| `rules/` | `universal.sql` (посев правил), `domain-specific/*.sql`, `annex/*.md`, `pack-rules.db` (собранная база правил пакета, лежит в git) |
| `vnext/prototype/` | приёмки `bite-*.py` (205 шт.), проверки `guard-*` / `check-*` / `measure-*`, запускатель `bite-all.py`, список ядра `core-bites.txt` |
| `vnext/tools/` | инструменты самого пака: `guard-donor-literals.py` + `core-files.txt`, `build-pack-rules-db.py`, `gen-schema.py` |
| `vnext/*.md` | проектные заметки следующей версии |
| `templates/` | 7 архетипов ролей |
| `plugins/turn-status/` | расширение Claude Code на Node (Apache-2.0, свои `LICENSE` и `NOTICE`), проверки — `test/run.js` |
| `src/Gordi.Periscope.Api/` | служба Перископа, ASP.NET Core `net10.0` |
| `srcclient/` | клиент Перископа: React 19 + TypeScript + Vite 7 |
| `examples/` | обезличенные составы ролей реальных проектов |
| корень | `README.md`, `UPGRADE*.md` (документ на каждый выпуск), `DELTA-*.md`, `MIGRATION.md`, `periscope-alive.py` |

## Команды

Проверено в Linux VM 2026-10-27 на Python 3.12, 3.13 и 3.14 и Node 22. Инструментам пака зависимости не нужны
(только stdlib); тестам `tests/` нужен pytest (`tests/requirements.txt`). CI (`.github/workflows/ci.yml`) гоняет
те же команды на Linux, а тесты `tests/` и `turn-status` — ещё и на Windows.

```bash
# синтаксис всех .py; SyntaxWarning — ошибка
python -W error::SyntaxWarning -m compileall -q .
# литералы донора в файлах ядра — та же проверка, что .githooks/pre-commit (≈8 с)
python vnext/tools/guard-donor-literals.py
# rules/pack-rules.db сходится с правилами HEAD; приёмка сборщика базы правил
python vnext/tools/build-pack-rules-db.py --check
python vnext/tools/bite-pack-rules-db.py
```

Тесты контрактов — pytest в `tests/`. Каждый тест собирает себе контур во временной папке: раскладка `<ws>/pack`,
живой контур и сеть не нужны.

```bash
python -m pip install -r tests/requirements.txt
python -m pytest tests                                      # ≈3 мин на Linux, ≈5 мин на Windows
python -m pytest tests/test_messaging.py -q                 # один файл
python -m pytest tests/test_schema.py --update-snapshots    # схема изменена намеренно: обновить snapshot
```

Свежий контур. Голый клон контуром не является (см. «Подвохи»). Поэтому клон кладут в `<ws>/pack`, а контур
собирают рядом, в `<ws>/.mezosync`. Тогда инструменты и приёмки клона находят контур сами, без переменных среды:

```bash
cd <ws>
python pack/scripts/init-group.py --name ci --path "<ws>/.mezosync" --domain data-platform --roles coord core stud taxo
python .mezosync/scripts/guard-all.py                       # «ВСЕ ГАРДЫ ЗЕЛЁНЫЕ (40 проверок)»
python .mezosync/scripts/read-phoenix.py --role COORD
python .mezosync/scripts/rules-from-pack.py --summary --source <ws>/pack
python pack/vnext/prototype/bite-fresh-circuit.py           # приёмка сборки с нуля, ≈40 с
python pack/vnext/prototype/bite-core-fixture.py            # «ИТОГ: 16/16», ≈7 с
python pack/vnext/prototype/bite-db-q.py                    # одна приёмка
python pack/vnext/prototype/bite-all.py --set core          # 61 приёмка против «было» из core-bites.txt, ≈5 мин
```

Node:

```bash
node plugins/turn-status/test/run.js                        # «all 53 checks pass», зависимостей нет
cd srcclient && npm ci && npm run build                     # tsc --noEmit + vite build; Node ^20.19 или >=22.12
```

C#-служба: сборка и запуск — в `src/README.md`. В VM она не собиралась, потому что dotnet там нет.

Pre-commit hook включается в каждом клоне отдельно: `git config core.hooksPath .githooks`.

## Соглашения

- Язык. Документы, комментарии и печать — по-русски. Имена функций, переменных, констант и флагов — по-английски
  (`UPGRADE-v5-to-2026-09-07.md`, раздел 1). Старый код переводится, когда файл всё равно правят.
- Commit — по-русски, впереди этап или карточка: `Э6 карточка #671: …`, `Карточка #686: …`. Выпуск —
  это документ `UPGRADE-YYYY-MM-DD-<тема>.md` и строка о нём в таблице раздела 4 `UPGRADE.md`.
- Пакет — единственный источник инструментов. Правят в клоне пакета, в контур правку ставит
  `update-tools.py --rev <commit>`. Снятый инструмент не удаляют: он остаётся и отказывает кодом 2, называя
  новый путь (пример — `vnext/tools/sync-vnext-pair.py`). Устаревший абзац документа заменяют надгробием
  `⚰️ Здесь стояло …` с причиной.
- Исходы проверок: 0 — чисто, 1 — находки, 2 — проверить не удалось. «Не проверено» не выдаётся за «чисто»
  (шапки `.githooks/pre-commit` и `vnext/prototype/bite-all.py`).
- Пишущий инструмент без флагов печатает план, пишет — с `--apply`. У шага схемы холостой прогон — `--dry-run`.
  Шаг идемпотентен: повтор отвечает «уже сведено». Автора шага в журнал пишет переменная `MEZO_ROLE`.
- Новый шаг схемы — это файл в `scripts/migrations/` и имя в `STEPS` (`scripts/schema_step_order.py`) в порядке
  применения, а не по алфавиту. Шаг, который схему не меняет, вносят в `NOT_SCHEMA_STEPS`. Шаг, который меняет
  схему, обновляет и snapshot `tests/snapshots/schema.json` (`--update-snapshots`, см. «Команды»).
- Новый `.py` в `scripts/` (кроме `bite-*.py` и `migrations/`) вносят строкой в `vnext/tools/core-files.txt`:
  в раздел `[ядро]` или в `[вне ядра]` с причиной. Иначе `guard-donor-literals.py` даёт находку.
- Пути машины в код не впечатывают: базу и контейнер ищут через `mezo_paths` (`container_root()`, `live_db()`,
  `resolve_db()`). Имена ролей берут из данных контура, а не литералом.
- Время — UTC с явным суффиксом ` UTC`. SQLite — режим WAL, `PRAGMA busy_timeout=5000`.
- Приёмка печатает строку на каждый случай (`✅` или `🔴`) и итог. Случаи «нарочная поломка» и «обратный ход»
  проверяют, что сама приёмка умеет краснеть.
- Перископ базу только читает: `Mode=ReadOnly` и `PRAGMA query_only = 1`
  (`src/Gordi.Periscope.Api/Data/ReadOnlyDb.cs`), запросы — только SELECT.
- Лицензия пака — GPL-3.0. `plugins/turn-status` — Apache-2.0.

## Подвохи

- Голый клон — не контур. Инструмент или приёмка из клона без контура рядом падает кодом 1:
  «контейнер группы НЕ НАЙДЕН». Выходов два: раскладка `<ws>/pack` + `<ws>/.mezosync` (см. выше) или
  `MEZO_CONTAINER=<контейнер>`. Случай ⑰ `bite-core-fixture.py` нарочно снимает `MEZO_CONTAINER`, поэтому
  проходит только в раскладке.
- Пять модулей лежат двумя одинаковыми копиями, в `scripts/` и в `vnext/prototype/`: `mezo_paths.py`,
  `mezo_stand.py`, `mezo_hints.py`, `mezo_sessions.py`, `check-rules-mirror.py`. Правьте обе.
- Версия Python. На 3.9 `init-group.py` падает на аннотации `str | None`. На 3.10 и 3.11 не компилируется
  `vnext/prototype/bite-signal-templates.py` (f-строка PEP 701, строка 598). Нужен 3.12 или новее.
- Мелкий клон (`--depth`): `bite-update-tools-rev.py` отказывает кодом 2 и требует полную историю.
  `rules-from-pack.py` без `--source` сам клонирует пак с GitHub, то есть ходит в сеть.
- `bite-all.py --set core` на свежем контуре кончается кодом 1, поэтому в CI его нет. С «было» расходятся:
  `bite-brief-views.py` и `bite-two-locks.py` (exit 0, но число ✅ зависит от данных живого контура);
  `bite-printed-forms-sources.py` (exit 2: нет `<контейнер>/CLAUDE.md`).
- Код писан под Windows: `winreg`, `ctypes.windll`, `_winapi`. Импорты ленивые, на Linux не мешают. Случаи
  про файл, занятый процессом (`bite-scratch-folders.py` ⑮, `bite-stand-keep-last.py` ㉑ ㊶), на Linux красные.
  Файлы `.githooks/*` — только с LF (`.gitattributes`).
- `.githooks/pre-commit` читает рабочее дерево, а не индекс, и `git commit --no-verify` его обходит. Проверить
  уже сделанный commit: `python vnext/tools/guard-donor-literals.py --commit HEAD`.
- `plugins/turn-status/test/run.js` краснеет, если в среде задана `CLAUDE_PROJECT_DIR` или `TURN_STATUS_DISABLE`
  (так бывает внутри сессии Claude Code). Запускайте с `env -u CLAUDE_PROJECT_DIR -u TURN_STATUS_DISABLE`.
- В `tests/` найденные ошибки `scripts/` стоят как `xfail(strict=True)` с файлом и строкой в причине. Починил такую
  ошибку — тест станет XPASS и уронит CI: сними пометку в том же commit.
- `tests/test_hooks.py` запускает `hooks/*.json` в PowerShell. Без `pwsh` и `powershell` эти тесты пропускаются
  (skip), в CI выполняются.
- У `dashboard.py` `--db` по умолчанию относительный (`.mezosync/mezosync.db`). Вне контейнера передавайте его явно.
- `vnext/prototype/guard-machine-paths.py` на клоне пака сейчас красный (exit 1): 72 пути одной машины в коде
  и примерах, ещё 25 — в прозе. Поэтому в CI его нет.
