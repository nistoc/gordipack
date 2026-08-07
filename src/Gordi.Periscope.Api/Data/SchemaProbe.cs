using Microsoft.Data.Sqlite;

namespace Gordi.Periscope.Api.Data;

/// <summary>
/// Что в ЭТОЙ базе есть на самом деле: таблицы, представления, колонки.
///
/// 📌 ЗАЧЕМ ЭТО ВООБЩЕ НУЖНО (замер, а не предосторожность вообще):
///    2026-08-06 живая база и эталон схемы `vnext/prototype/schema_vnext.sql` РАЗОШЛИСЬ.
///    В живой есть таблицы, которых в эталоне нет (audit_log, tracks, invariants,
///    templates, messages_history, backlog_events, backlog_tests, read_cursors,
///    role_status, broadcast_acks, stats_log, cross_links, read_batches),
///    а из эталонных отсутствуют message_addressee, message_closure, role_presence,
///    phoenix_sections, mechanism_changes — и большинство VIEW.
///    Совпадающие таблицы тоже отличаются составом колонок (roles, rules, schema_migrations).
///    ⇒ Просмотрщик, написанный «по эталону», упал бы на живой базе,
///      а написанный «по живой» — на новой. Поэтому он спрашивает базу, а не помнит.
///
/// 🔴 И это не теория: за двадцать минут между двумя замерами 2026-08-06 в живой базе
///    ПОЯВИЛИСЬ два представления (backlog_without_criterion, schema_version) и рубеж
///    версии 'v3' в журнале миграций. Схема меняется под работающим просмотрщиком —
///    значит список объектов нельзя знать заранее, его можно только спросить, и спросить
///    ЗАНОВО при каждой пересборке снимка. Ровно так и сделано.
///
/// ⚠️ И ГЛАВНОЕ ПРАВИЛО ЧЕСТНОСТИ, ради которого класс существует:
///    отсутствие колонки — это НЕ ноль. Если в базе нет `backlog.done_when`,
///    правильный ответ «в этой базе поля критерия нет вовсе», а НЕ «задач без
///    критерия: 0». Ноль здесь читался бы как хорошая новость и был бы ложью.
/// </summary>
public sealed class SchemaCapabilities
{
    private readonly Dictionary<string, string> _objects;                 // имя → type (table|view)
    private readonly Dictionary<string, HashSet<string>> _columns;

    private SchemaCapabilities(
        Dictionary<string, string> objects,
        Dictionary<string, HashSet<string>> columns)
    {
        _objects = objects;
        _columns = columns;
    }

    public bool Has(string name) => _objects.ContainsKey(name);

    public bool HasColumn(string table, string column) =>
        _columns.TryGetValue(table, out var cols) && cols.Contains(column);

    /// <summary>Первая из перечисленных колонок, которая в таблице реально есть.</summary>
    public string? FirstColumn(string table, params string[] candidates) =>
        candidates.FirstOrDefault(c => HasColumn(table, c));

    public IReadOnlyDictionary<string, string> Objects => _objects;

    public IReadOnlyList<string> ColumnsOf(string table) =>
        _columns.TryGetValue(table, out var cols) ? cols.OrderBy(x => x).ToArray() : [];

    public static SchemaCapabilities Probe(SqliteConnection c)
    {
        var objects = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        var columns = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);

        using (var cmd = c.CreateCommand())
        {
            cmd.CommandText =
                """
                SELECT name, type FROM sqlite_master
                WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """;
            using var r = cmd.ExecuteReader();
            while (r.Read())
                objects[r.GetString(0)] = r.GetString(1);
        }

        foreach (var name in objects.Keys.ToArray())
        {
            var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            using var cmd = c.CreateCommand();
            // Имя объекта пришло из sqlite_master, а не снаружи; кавычки — от имён
            // со спецсимволами, не от подстановки пользователя.
            cmd.CommandText = $"PRAGMA table_info(\"{name.Replace("\"", "\"\"")}\")";
            using var r = cmd.ExecuteReader();
            while (r.Read())
                set.Add(r.GetString(1));
            columns[name] = set;
        }

        return new SchemaCapabilities(objects, columns);
    }
}
