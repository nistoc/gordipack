-- Дополнительные правила для frontend/SPA проектов

INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES
('200-not-works',
 'INVARIANT: HTTP 200 ≠ "работает". Любая проверка готовности SPA ОБЯЗАНА верифицировать Content-Type и размер ответа, а не только статус-код.',
 'coord', 1),

('prototype-is-canon',
 'UX-прототипы (HTML/SVG от дизайнера/таксономиста) — канон. data-* селекторы прототипа = канон селекторов React. Расхождение = баг.',
 'coord', 1),

('live-data-wins',
 'При конфликте прототипа с живыми данными API — выигрывают живые данные. Прототип правится нотой от UX-роли.',
 'coord', 1);
