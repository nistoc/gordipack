-- Дополнительные правила для data-platform проектов (DWH, ETL, семантика)

INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES
('no-scan-external-contours',
 'Контуры за пределами рабочей директории группы НЕ сканировать без явного разрешения владельца. Пример: AIA, внешние DWH-репо.',
 'owner', 1),

('migration-safety',
 'SQL-миграции: всегда идемпотентны (IF NOT EXISTS / OR REPLACE), всегда в транзакции, pre-flight проверка на дубли/конфликты обязательна.',
 'coord', 1),

('semantic-canon',
 'Источник правды для семантики (концепты, таксономии, связи) — TAXO-роль. CORE/ING реализуют, но НЕ изобретают семантику самостоятельно.',
 'coord', 1);
