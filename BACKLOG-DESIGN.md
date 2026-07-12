# Backlog — дизайн (ПЛАН, не реализация)

> Статус: черновик на согласование владельцем. Реализация — только по слову.
> Цель: durable per-role backlog, чтобы **при перезапуске агента не терялся контекст истории**;
> rich-md; отслеживание статуса; приёмочные тесты 4 способами (агент / скрипт / прогон кода / пользователь через UI).

## 1. Зачем

Сейчас «бэклог» роли живёт прозой в phoenix (`§5 что дальше`, разрозненные F-*), и при
ребёрсе агент реконструирует рабочий набор из текста слепка — хрупко и лоссово. Нужен
**структурированный, персистентный backlog в SQLite**: первым делом на пробуждении агент
делает `backlog.py list --role X` и получает точный список незакрытых задач с историей,
а не пересобирает его из прозы.

Соотношение с существующими сущностями:
- `tracks` — крупные цели/эпики (остаются). `backlog.parent_track` может ссылаться на трек.
- `messages` — лента коммуникации (эфемерные ноты). Backlog — durable рабочие единицы.
- `phoenix` — снимок состояния роли; backlog его РАЗГРУЖАЕТ (задачи уходят из прозы в таблицу).

## 2. Модель данных (3 новые таблицы SQLite)

### `backlog` — задачи
| Колонка | Тип | Назначение |
|---|---|---|
| `id` | INTEGER PK | |
| `role` | TEXT | владелец: роль (`CORE`…) или `SHARED` для общих |
| `title` | TEXT | короткий заголовок |
| `body_md` | TEXT | **rich markdown**: описание, контекст, ссылки, критерии |
| `status` | TEXT | `open`·`in_progress`·`blocked`·`in_review`·`done`·`dropped` |
| `priority` | TEXT | `low`·`normal`·`high`·`critical` |
| `tags` | TEXT(JSON) | `["prov","F-24"]` |
| `parent_id` | INTEGER? | подзадача/эпик |
| `parent_track` | TEXT? | ссылка на `tracks.track_id` |
| `rank` | INTEGER? | ручной порядок |
| `blocked_reason` | TEXT? | если `blocked` |
| `created_by`·`created_at`·`updated_at` | TEXT | аудит |

### `backlog_events` — append-only история (ключ к «не терять контекст»)
| Колонка | Тип | Назначение |
|---|---|---|
| `id` | INTEGER PK | |
| `backlog_id` | INTEGER FK | |
| `at` | TEXT | UTC (правило `timestamp-utc-in-sqlite`) |
| `actor_role` | TEXT | кто |
| `event_type` | TEXT | `created`·`status_change`·`comment`·`edited`·`test_added`·`test_result` |
| `from_status`·`to_status` | TEXT? | для смены статуса |
| `body_md` | TEXT | **rich markdown** комментарий/детали |

Полный трейл задачи переживает любой ребёрс — новый агент читает историю, а не догадывается.

### `backlog_tests` — приёмочные тесты (4 способа верификации)
| Колонка | Тип | Назначение |
|---|---|---|
| `id` | INTEGER PK | |
| `backlog_id` | INTEGER FK | |
| `title` | TEXT | что проверяем |
| `method` | TEXT | **`agent`·`script`·`code`·`user_ui`** |
| `spec_md` | TEXT | **rich md**: как прогнать / что считать успехом |
| `command` | TEXT? | для `script`/`code`: команда запуска |
| `expected` | TEXT? | ожидаемый результат/маркер |
| `status` | TEXT | `pending`·`passing`·`failing`·`skipped` |
| `last_run_at`·`last_result_md` | TEXT? | последний прогон |
| `created_by` | TEXT | |

## 3. Четыре способа верификации (как просил владелец)

| Способ | Кто прогоняет | Авто? | Откуда результат |
|---|---|---|---|
| `agent` | сам агент | ручной | суждение агента → `test-result` |
| `script` | CLI/скрипт | ✅ авто (`test-run`) | exit-code / вывод команды |
| `code` | build/test (`dotnet test`, `vitest`) | ✅ авто (`test-run`) | exit-код тест-раннера |
| `user_ui` | пользователь через UI | ручной | пользователь → `test-result` (см. §6 ограничение) |

## 4. Инструменты (CLI, gordipack/scripts)

```
backlog.py add --role CORE --title "..." --body-file note.md [--priority high] [--tags "prov"] [--parent 12] [--track NEWUX]
backlog.py list --role CORE [--status open]        # ПЕРВОЕ на пробуждении — восстановление контекста
backlog.py show 34                                  # rich-md + история событий + тесты
backlog.py status 34 in_progress [--note-file n.md] # смена статуса (пишет event)
backlog.py comment 34 --body-file n.md              # rich-md заметка (event)
backlog.py test-add 34 --method code --title "гейт зелёный" --command "dotnet test ..." --expected "Passed!"
backlog.py test-result 34.2 --status passing --note "..."   # ручная фиксация (agent/user_ui)
backlog.py test-run 34.2                             # авто-прогон (только script/code): исполняет command, пишет результат
```

Rich-md подаётся через `--body-file`/`--note-file` (чтобы не терять переносы/разметку в CLI).

## 5. Интеграция «восстановление при перезапуске»

- Новое правило `backlog-restart-recovery` (owner-locked): при ребёрсе роль ПЕРВЫМ делом
  делает `backlog.py list --role X` и восстанавливает незакрытые задачи из БД, а не из прозы phoenix.
- В §5/§блок «ДВОЙНАЯ ЗАПИСЬ» каждого phoenix — строка-рецепт `backlog.py list --role X`.
- Phoenix худеет: «что дальше» ссылается на backlog, не дублирует его.

## 6. Viewer

- Новая карточка **Backlog** в `viewer/index.html`: фильтр по роли+статусу, разворот задачи →
  rich-md (рендер markdown) + список тестов (со статусами) + лента событий.
- ⚠️ Ограничение: viewer на sql.js **read-only** (не пишет в файл). Значит результат `user_ui`-теста
  пользователь фиксирует НЕ из вьюера, а: (вариант A) говорит COORD → COORD пишет `test-result`;
  (вариант B) мини-CLI `backlog.py test-result` запускает пользователь. Отдельный write-back UI —
  за рамками (нужен бэкенд). Предлагаю вариант A.

## 7. План работ (по фазам, реализация по слову)

| Фаза | Содержание |
|---|---|
| B1 | Схема (3 таблицы) в `schema/mezosync_v1.sql` + `backlog.py` (add/list/show/status/comment) |
| B2 | Тесты: `test-add`/`test-result`/`test-run` + 4 метода (авто для script/code) |
| B3 | Карточка Backlog во вьюере (рендер rich-md + тесты + события) |
| B4 | Правило `backlog-restart-recovery` + строка-рецепт в 8 phoenix + templates |
| B5 | Посев текущих открытых задач в backlog (seed) — см. §8 |

## 8. Seed текущих задач (чтобы backlog сразу был полезен)

Кандидаты на первичное наполнение (по факту из каналов):
- **CORE:** `prov-reject-events` (TASK от COORD 10:39; дизайн-эскиз #40; тест: `code` = миграция+гейт, `agent` = проверка PROV-записи).
- **STUD:** `role-request-flow` (сестринская, зона STUD-host; тест: `user_ui` = approve/reject в UI + `code` vitest).
- **STUD:** SchemeDetail «6 лиц» + ADMIN-города (ждут GO владельца).
- **CORE-бэклог:** F-post-14 (per-element EXISTS-гард), OQ-CORE-1/F-24 (silent-drop descriptionPlain).
- **ING-бэклог:** F-post-22/F-post-18/F-2 (ждут gateway/owner).
- **GRF:** предложение по устойчивости graphify (валидация LLM-вывода на входе сборки).

## 9. Открытые вопросы владельцу

1. **Область backlog:** только per-role, или и `SHARED` (общие задачи)? (предлагаю оба)
2. **Авто-прогон `code`-тестов** (dotnet/vitest): агент гоняет их каждый тик автоматически, или
   только по требованию + гейт? (предлагаю по требованию — дорого/долго каждый тик)
3. **Результат `user_ui`-теста:** вариант A (через COORD) или B (пользователь сам зовёт CLI)?
4. **Миграция прозы:** переносить старые «бэклоги» из phoenix в таблицу разом или по мере касания?
