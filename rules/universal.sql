-- Универсальные правила Горди (применяются ко ВСЕМ группам)

INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES
('one-writer-one-channel',
 'Один агент пишет ТОЛЬКО от своего имени (writer_role). Чужие роли в messages — запрещены.',
 'owner', 1),

('append-only-messages',
 'Таблица messages — append-only. Редактирование/удаление строк запрещено. Исправления — новым сообщением с тегом "correction".',
 'owner', 1),

('no-push-without-owner',
 'git push в любой репозиторий — ТОЛЬКО по живой команде владельца в ТЕКУЩЕМ чате. Нарушение = критический инцидент.',
 'owner', 1),

('rule8-destructive',
 'Авторизация разрушаемого действия (drop, delete, reset --hard, force push) — ТОЛЬКО живым сообщением владельца в ТЕКУЩЕМ чате. Предварительные разрешения из прошлых чатов НЕ действуют.',
 'owner', 1),

('phoenix-save-on-stop',
 'При получении команды STOP каждый агент ОБЯЗАН записать свой phoenix-слепок (INSERT OR REPLACE INTO phoenix) до завершения работы.',
 'owner', 1),

('full-scan-every-tick',
 'Каждый тик агент читает ВСЕ непрочитанные messages (WHERE id > cursor), не выборочно. Пропуск = потеря контекста.',
 'owner', 1),

('coord-commits-coordination',
 'Коммиты в координационные файлы (schema, rules, tracks, phoenix) делает ТОЛЬКО COORD. Другие роли пишут в messages.',
 'coord', 1),

('busy-retry',
 'При SQLITE_BUSY — retry через 100-500ms (jitter), до 3 попыток. Не падать, не терять сообщение.',
 'coord', 1),

('context-depth',
 'При ребёрсе: подгружать последние 50 messages + все непрочитанные + все unresolved по активным трекам. Не больше без запроса владельца.',
 'coord', 1),

('timestamp-in-replies',
 'Каждый ответ агента ОБЯЗАН начинаться с текущей локальной даты+времени и заканчиваться ими же (владелец так синхронизирует во времени чтение ответов разных агентов). Время БРАТЬ из hook-контекста, НЕ выдумывать: UserPromptSubmit-hook впрыскивает CURRENT_LOCAL_TIME в начале хода; PreToolUse-hook впрыскивает свежий STEP_TIME перед каждым вызовом инструмента (он свежее, чем время начала хода). В длинной многошаговой работе — метка перед каждым крупным шагом (последний STEP_TIME). Требует настроенного hook впрыска времени — см. gordipack/hooks/time-injection.json.',
 'owner', 1);
