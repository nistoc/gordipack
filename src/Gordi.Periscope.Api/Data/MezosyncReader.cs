using Gordi.Periscope.Api.Model;
using Microsoft.Data.Sqlite;

namespace Gordi.Periscope.Api.Data;

/// <summary>Фильтры ленты.</summary>
public sealed record MessageQuery(
    int Limit,
    int Offset,
    string? Role = null,
    string? Priority = null,
    string? Search = null,
    string? Source = null);

/// <summary>
/// ВЕСЬ SQL просмотрщика. Только SELECT и PRAGMA, только параметризованный.
/// Каждый запрос сначала спрашивает SchemaCapabilities «есть ли, из чего читать».
/// </summary>
public static class MezosyncReader
{
    // Пусто-подобный критерий: NULL, пробелы, табуляция, переводы строки.
    // ⚠️ ЯВНЫЙ НАБОР СИМВОЛОВ, а не голый TRIM: в SQLite голый TRIM снимает ТОЛЬКО
    //    пробел, и критерий из одной табуляции прошёл бы за настоящий. Ровно эта
    //    ошибка поймана в эталоне схемы — повторять её во втором месте незачем.
    // 📌 Почему НЕ читаем готовое представление backlog_without_criterion, которое
    //    в живой базе уже появилось: оно есть не везде (в базе на v2 его нет вовсе),
    //    а вопрос «сколько задач без критерия» должен иметь ответ в любой базе,
    //    где есть сама колонка. Условие здесь — слово в слово из эталона, чтобы два
    //    места не разошлись молча; если разойдутся — видно будет по числу.
    private const string BlankCriterion =
        "(done_when IS NULL OR TRIM(done_when, ' ' || char(9) || char(10) || char(13)) = '')";

    /// <summary>Объекты, которые объявляет эталон схемы v3 (vnext/prototype/schema_vnext.sql).</summary>
    private static readonly string[] ReferenceObjects =
    [
        "roles", "rules", "rules_active", "role_presence", "role_presence_read",
        "phoenix_sections", "phoenix", "phoenix_gaps", "schema_migrations",
        "mechanism_changes", "phoenix_vs_mechanisms", "messages", "message_addressee",
        "messages_for_role", "messages_unaddressed", "cursor_segments", "cursor_truth",
        "cursor_gaps", "message_closure", "message_urgency", "open_high_for_role",
        "message_thread", "thread_view", "open_questions_for_role",
        "thread_backfill_candidates", "backlog", "message_task", "task_history",
        "backlog_without_criterion", "meta", "schema_version"
    ];

    /// <summary>Объекты прежних версий, которые просмотрщик знает и умеет показывать.</summary>
    private static readonly string[] LegacyKnownObjects =
    [
        "messages_history", "messages_all", "backlog_events", "backlog_tests",
        "role_status", "read_cursors", "read_batches", "tracks", "invariants",
        "templates", "audit_log", "stats_log", "broadcast_acks", "cross_links"
    ];

    // ── обзор ────────────────────────────────────────────────────────────────

    public static OverviewDto ReadOverview(SqliteConnection c, SchemaCapabilities s)
    {
        var groupName = s.Has("meta")
            ? ScalarString(c, "SELECT value FROM meta WHERE key = 'group_name'")
            : null;

        var criterionSupported = s.HasColumn("backlog", "done_when");

        return new OverviewDto(
            GroupName: groupName,
            SchemaVersion: ReadSchemaVersion(c, s),
            Messages: CountOf(c, s, "messages"),
            MessagesHistory: CountOf(c, s, "messages_history"),
            Roles: s.Has("roles")
                ? CountOf(c, s, "roles")
                : s.Has("messages")
                    ? new Measure(ScalarLong(c, "SELECT COUNT(DISTINCT writer_role) FROM messages"), true,
                        "таблицы roles нет — считано по авторам записок")
                    : Measure.Unsupported("нет ни roles, ни messages"),
            Rules: CountOf(c, s, "rules"),
            TasksTotal: CountOf(c, s, "backlog"),
            TasksOpen: s.Has("backlog")
                ? new Measure(ScalarLong(c, "SELECT COUNT(*) FROM backlog WHERE status = 'open'"), true)
                : Measure.Unsupported("нет таблицы backlog"),
            TasksDone: s.Has("backlog")
                ? new Measure(ScalarLong(c, "SELECT COUNT(*) FROM backlog WHERE status = 'done'"), true)
                : Measure.Unsupported("нет таблицы backlog"),
            TasksOpenWithoutCriterion: !s.Has("backlog")
                ? Measure.Unsupported("нет таблицы backlog")
                : !criterionSupported
                    // 🔴 Именно здесь ноль был бы ложью: «0 задач без критерия» читается
                    //    как «всё в порядке», а на деле поля критерия в базе нет вовсе.
                    ? Measure.Unsupported("в этой базе нет колонки backlog.done_when — критерий приёмки не хранится")
                    : new Measure(
                        ScalarLong(c, $"SELECT COUNT(*) FROM backlog WHERE status = 'open' AND {BlankCriterion}"),
                        true),
            LastMessageUtc: s.Has("messages")
                ? Row.Utc(ScalarString(c, "SELECT MAX(timestamp) FROM messages"))
                : null,
            BuiltAtUtc: DateTimeOffset.UtcNow);
    }

    private static SchemaVersionDto ReadSchemaVersion(SqliteConnection c, SchemaCapabilities s)
    {
        var declared = s.Has("meta")
            ? ScalarString(c, "SELECT value FROM meta WHERE key = 'schema_version'")
            : null;

        if (!s.Has("schema_migrations"))
            return new SchemaVersionDto(declared, null, null, null,
                "журнала миграций в базе нет — версию подтвердить нечем");

        // Рубеж — ЯВНАЯ строка вида 'v3'; шаги ('001-roles') версией не являются.
        // Порядок — по rowid, а не по времени: все строки журнала обычно ложатся
        // в одну секунду, и сравнение по времени дало бы ноль всегда.
        var milestone = ScalarString(c,
            "SELECT version FROM schema_migrations WHERE version GLOB 'v[0-9]*' ORDER BY rowid DESC LIMIT 1");
        var stepsTotal = ScalarLong(c,
            "SELECT COUNT(*) FROM schema_migrations WHERE version NOT GLOB 'v[0-9]*'");
        var stepsAfter = ScalarLong(c,
            """
            SELECT COUNT(*) FROM schema_migrations m
             WHERE m.version NOT GLOB 'v[0-9]*'
               AND m.rowid > COALESCE((SELECT rowid FROM schema_migrations
                                        WHERE version GLOB 'v[0-9]*'
                                        ORDER BY rowid DESC LIMIT 1), 0)
            """);

        var note = milestone is null
            ? "рубеж версии в журнале не объявлен — есть только номера шагов"
            : stepsAfter > 0
                ? $"после рубежа {milestone} внесено шагов: {stepsAfter} — версия объявлена не до конца"
                : null;

        if (declared is not null && milestone is not null &&
            !declared.Contains(milestone.TrimStart('v'), StringComparison.OrdinalIgnoreCase))
        {
            note = (note is null ? "" : note + "; ") +
                   $"meta.schema_version = '{declared}' расходится с рубежом журнала '{milestone}'";
        }

        return new SchemaVersionDto(declared, milestone, (int?)stepsTotal, (int?)stepsAfter, note);
    }

    // ── задачи ───────────────────────────────────────────────────────────────

    public static IReadOnlyList<TaskDto> ReadTasks(SqliteConnection c, SchemaCapabilities s)
    {
        if (!s.Has("backlog")) return [];

        var criterionSupported = s.HasColumn("backlog", "done_when");
        var droppedReasons = ReadDroppedReasons(c, s);

        using var cmd = c.CreateCommand();
        cmd.CommandText = "SELECT * FROM backlog ORDER BY id";
        using var r = cmd.ExecuteReader();
        var m = Row.Map(r);

        var list = new List<TaskDto>();
        while (r.Read())
        {
            var doneWhen = criterionSupported ? Row.Str(r, m, "done_when") : null;
            var id = Row.Num(r, m, "id") ?? 0;
            var status = Row.Str(r, m, "status");
            list.Add(new TaskDto(
                Id: id,
                Role: Row.Str(r, m, "role"),
                Title: Row.Str(r, m, "title"),
                Status: status,
                Priority: Row.Str(r, m, "priority"),
                DoneWhen: doneWhen,
                CriterionSupported: criterionSupported,
                HasCriterion: !string.IsNullOrWhiteSpace(doneWhen),
                Tags: Row.Tags(r, m, "tags"),
                ParentId: Row.Num(r, m, "parent_id"),
                ParentTrack: Row.Str(r, m, "parent_track"),
                BlockedReason: Row.Str(r, m, "blocked_reason"),
                DroppedReason: status == "dropped" ? droppedReasons.GetValueOrDefault(id) : null,
                CreatedBy: Row.Str(r, m, "created_by"),
                CreatedAt: Row.Str(r, m, "created_at"),
                UpdatedAt: Row.Str(r, m, "updated_at"),
                BodyLength: (Row.Str(r, m, "body_md") ?? "").Length));
        }

        return list;
    }

    // Причины устаревания одним запросом на весь список: последний status_change → dropped
    // с непустой запиской побеждает (ORDER BY id — поздние перезаписывают ранние в словаре).
    // Тот же отбор, что у CLI-списка: NULL/пустое тело причиной не считается.
    private static Dictionary<long, string> ReadDroppedReasons(SqliteConnection c, SchemaCapabilities s)
    {
        var reasons = new Dictionary<long, string>();
        if (!s.Has("backlog_events")) return reasons;

        using var cmd = c.CreateCommand();
        cmd.CommandText =
            "SELECT backlog_id, body_md FROM backlog_events " +
            "WHERE event_type = 'status_change' AND to_status = 'dropped' " +
            "AND body_md IS NOT NULL AND TRIM(body_md) != '' ORDER BY id";
        using var r = cmd.ExecuteReader();
        while (r.Read())
            reasons[r.GetInt64(0)] = r.GetString(1);
        return reasons;
    }

    public static TaskDetailDto? ReadTask(SqliteConnection c, SchemaCapabilities s, long id)
    {
        if (!s.Has("backlog")) return null;

        TaskDto? task = null;
        string? bodyMd = null;
        var criterionSupported = s.HasColumn("backlog", "done_when");

        using (var cmd = c.CreateCommand())
        {
            cmd.CommandText = "SELECT * FROM backlog WHERE id = @id";
            cmd.Parameters.AddWithValue("@id", id);
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            if (r.Read())
            {
                var doneWhen = criterionSupported ? Row.Str(r, m, "done_when") : null;
                bodyMd = Row.Str(r, m, "body_md");
                var status = Row.Str(r, m, "status");
                task = new TaskDto(
                    Row.Num(r, m, "id") ?? id, Row.Str(r, m, "role"), Row.Str(r, m, "title"),
                    status, Row.Str(r, m, "priority"), doneWhen,
                    criterionSupported, !string.IsNullOrWhiteSpace(doneWhen),
                    Row.Tags(r, m, "tags"), Row.Num(r, m, "parent_id"), Row.Str(r, m, "parent_track"),
                    Row.Str(r, m, "blocked_reason"),
                    status == "dropped" ? ReadDroppedReasons(c, s).GetValueOrDefault(id) : null,
                    Row.Str(r, m, "created_by"),
                    Row.Str(r, m, "created_at"), Row.Str(r, m, "updated_at"),
                    (bodyMd ?? "").Length);
            }
        }

        if (task is null) return null;

        var missing = new List<string>();
        var events = new List<TaskEventDto>();
        if (s.Has("backlog_events"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT * FROM backlog_events WHERE backlog_id = @id ORDER BY id";
            cmd.Parameters.AddWithValue("@id", id);
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
                events.Add(new TaskEventDto(
                    Row.Num(r, m, "id") ?? 0, Row.Str(r, m, "at"), Row.Str(r, m, "actor_role"),
                    Row.Str(r, m, "event_type"), Row.Str(r, m, "from_status"),
                    Row.Str(r, m, "to_status"), Row.Str(r, m, "body_md")));
        }
        else missing.Add("backlog_events");

        var tests = new List<TaskTestDto>();
        if (s.Has("backlog_tests"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT * FROM backlog_tests WHERE backlog_id = @id ORDER BY id";
            cmd.Parameters.AddWithValue("@id", id);
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
                tests.Add(new TaskTestDto(
                    Row.Num(r, m, "id") ?? 0, Row.Str(r, m, "title"), Row.Str(r, m, "method"),
                    Row.Str(r, m, "status"), Row.Str(r, m, "command"), Row.Str(r, m, "expected"),
                    Row.Str(r, m, "last_run_at"), Row.Str(r, m, "last_result_md")));
        }
        else missing.Add("backlog_tests");

        var linked = new List<MessageDto>();
        if (s.Has("message_task") && s.Has("messages"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText =
                """
                SELECT m.* FROM message_task mt
                  JOIN messages m ON m.id = mt.message_id
                 WHERE mt.task_id = @id
                 ORDER BY m.id
                """;
            cmd.Parameters.AddWithValue("@id", id);
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read()) linked.Add(MapMessage(r, m, includeBody: false));
        }
        else missing.Add("message_task");

        return new TaskDetailDto(task, bodyMd, events, tests, linked, missing);
    }

    // ── лента ────────────────────────────────────────────────────────────────

    /// <summary>Из чего читать ленту: VIEW messages_all (живое + история) или голая таблица.</summary>
    public static string FeedObject(SchemaCapabilities s) =>
        s.Has("messages_all") ? "messages_all" : "messages";

    public static MessagePageDto ReadMessages(SqliteConnection c, SchemaCapabilities s, MessageQuery q)
    {
        var obj = FeedObject(s);
        if (!s.Has(obj)) return new MessagePageDto([], q.Limit, q.Offset, 0, obj);

        var where = new List<string>();
        var ps = new List<(string Name, object Value)>();

        if (!string.IsNullOrWhiteSpace(q.Role))
        {
            where.Add("writer_role = @role");
            ps.Add(("@role", q.Role));
        }

        if (!string.IsNullOrWhiteSpace(q.Priority))
        {
            where.Add("priority = @priority");
            ps.Add(("@priority", q.Priority));
        }

        if (!string.IsNullOrWhiteSpace(q.Search))
        {
            where.Add(@"body_md LIKE @search ESCAPE '\'");
            var escaped = q.Search.Replace(@"\", @"\\").Replace("%", @"\%").Replace("_", @"\_");
            ps.Add(("@search", $"%{escaped}%"));
        }

        if (!string.IsNullOrWhiteSpace(q.Source) && s.HasColumn(obj, "source"))
        {
            where.Add("source = @src");
            ps.Add(("@src", q.Source));
        }

        var whereSql = where.Count > 0 ? " WHERE " + string.Join(" AND ", where) : "";

        long total;
        using (var cmd = c.CreateCommand())
        {
            cmd.CommandText = $"SELECT COUNT(*) FROM {obj}{whereSql}";
            foreach (var (n, v) in ps) cmd.Parameters.AddWithValue(n, v);
            total = Convert.ToInt64(cmd.ExecuteScalar() ?? 0L);
        }

        var items = new List<MessageDto>();
        using (var cmd = c.CreateCommand())
        {
            cmd.CommandText = $"SELECT * FROM {obj}{whereSql} ORDER BY id DESC LIMIT @limit OFFSET @offset";
            foreach (var (n, v) in ps) cmd.Parameters.AddWithValue(n, v);
            cmd.Parameters.AddWithValue("@limit", q.Limit);
            cmd.Parameters.AddWithValue("@offset", q.Offset);
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read()) items.Add(MapMessage(r, m, includeBody: false));
        }

        return new MessagePageDto(items, q.Limit, q.Offset, total, obj);
    }

    public static MessageDto? ReadMessage(SqliteConnection c, SchemaCapabilities s, long id)
    {
        var obj = FeedObject(s);
        if (!s.Has(obj)) return null;

        using var cmd = c.CreateCommand();
        cmd.CommandText = $"SELECT * FROM {obj} WHERE id = @id LIMIT 1";
        cmd.Parameters.AddWithValue("@id", id);
        using var r = cmd.ExecuteReader();
        var m = Row.Map(r);
        return r.Read() ? MapMessage(r, m, includeBody: true) : null;
    }

    private static MessageDto MapMessage(SqliteDataReader r, Dictionary<string, int> m, bool includeBody)
    {
        var body = Row.Str(r, m, "body_md") ?? "";
        return new MessageDto(
            Id: Row.Num(r, m, "id") ?? 0,
            WriterRole: Row.Str(r, m, "writer_role"),
            Timestamp: Row.Str(r, m, "timestamp"),
            Priority: Row.Str(r, m, "priority"),
            Tags: Row.Tags(r, m, "tags"),
            Broadcast: Row.Bool(r, m, "broadcast"),
            Source: Row.Str(r, m, "source"),
            BodyLength: body.Length,
            BodyPreview: Row.Preview(body),
            BodyMd: includeBody ? body : null);
    }

    public static IReadOnlyList<string> DistinctWriters(SqliteConnection c, SchemaCapabilities s)
    {
        var obj = FeedObject(s);
        if (!s.Has(obj)) return [];
        var list = new List<string>();
        using var cmd = c.CreateCommand();
        cmd.CommandText = $"SELECT DISTINCT writer_role FROM {obj} WHERE writer_role IS NOT NULL ORDER BY writer_role";
        using var r = cmd.ExecuteReader();
        while (r.Read()) list.Add(r.GetString(0));
        return list;
    }

    // ── роли ─────────────────────────────────────────────────────────────────

    public static RolesDto ReadRoles(SqliteConnection c, SchemaCapabilities s)
    {
        var missing = new List<string>();
        var acc = new Dictionary<string, RoleAcc>(StringComparer.OrdinalIgnoreCase);

        RoleAcc Get(string role)
        {
            if (!acc.TryGetValue(role, out var a)) acc[role] = a = new RoleAcc { Role = role };
            return a;
        }

        if (s.Has("roles"))
        {
            // Живая база: roles(role, status, seen_in, in_roster, created_at)
            // Эталон v3:  roles(role, lifecycle, zone, ...) — берём то, что есть.
            var statusCol = s.FirstColumn("roles", "status", "lifecycle");
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT * FROM roles";
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
            {
                var role = Row.Str(r, m, "role");
                if (string.IsNullOrWhiteSpace(role)) continue;
                var a = Get(role);
                a.Status = statusCol is null ? null : Row.Str(r, m, statusCol);
                a.InRoster = Row.Bool(r, m, "in_roster");
            }
        }
        else missing.Add("roles");

        if (s.Has("role_status"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT role, status, updated_at FROM role_status";
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
            {
                var role = Row.Str(r, m, "role");
                if (string.IsNullOrWhiteSpace(role)) continue;
                var a = Get(role);
                a.StatusNote = Row.Str(r, m, "status");
                a.StatusUpdatedAt = Row.Str(r, m, "updated_at");
            }
        }
        else missing.Add("role_status");

        // Курсор: сначала честный отрезками, если он есть; иначе одна строка на роль.
        if (s.Has("cursor_segments"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT role, MAX(to_id) AS cursor_at FROM cursor_segments GROUP BY role";
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
            {
                var role = Row.Str(r, m, "role");
                if (string.IsNullOrWhiteSpace(role)) continue;
                Get(role).CursorAt = Row.Num(r, m, "cursor_at");
            }
        }
        else if (s.Has("read_cursors"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT reader_role, last_read_id FROM read_cursors";
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
            {
                var role = Row.Str(r, m, "reader_role");
                if (string.IsNullOrWhiteSpace(role)) continue;
                Get(role).CursorAt = Row.Num(r, m, "last_read_id");
            }
        }
        else missing.Add("cursor_segments / read_cursors");

        if (s.Has("phoenix"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT role, COUNT(*) AS n, MAX(saved_at) AS last_saved FROM phoenix GROUP BY role";
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
            {
                var role = Row.Str(r, m, "role");
                if (string.IsNullOrWhiteSpace(role)) continue;
                var a = Get(role);
                a.PhoenixSections = (int)(Row.Num(r, m, "n") ?? 0);
                a.PhoenixSavedAt = Row.Str(r, m, "last_saved");
            }
        }
        else missing.Add("phoenix");

        if (s.Has("messages"))
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText =
                "SELECT writer_role, COUNT(*) AS n, MAX(timestamp) AS last_at FROM messages GROUP BY writer_role";
            using var r = cmd.ExecuteReader();
            var m = Row.Map(r);
            while (r.Read())
            {
                var role = Row.Str(r, m, "writer_role");
                if (string.IsNullOrWhiteSpace(role)) continue;
                var a = Get(role);
                a.MessagesWritten = Row.Num(r, m, "n");
                a.LastMessageAt = Row.Str(r, m, "last_at");
            }
        }

        var items = acc.Values
            .OrderBy(a => a.Role, StringComparer.OrdinalIgnoreCase)
            .Select(a => new RoleDto(a.Role, a.Status, a.StatusNote, a.StatusUpdatedAt, a.InRoster,
                a.CursorAt, a.MessagesWritten, a.LastMessageAt, a.PhoenixSections, a.PhoenixSavedAt))
            .ToArray();

        return new RolesDto(items, missing);
    }

    private sealed class RoleAcc
    {
        public string Role = "";
        public string? Status;
        public string? StatusNote;
        public string? StatusUpdatedAt;
        public bool? InRoster;
        public long? CursorAt;
        public long? MessagesWritten;
        public string? LastMessageAt;
        public int PhoenixSections;
        public string? PhoenixSavedAt;
    }

    // ── правила ──────────────────────────────────────────────────────────────

    /// <summary>
    /// Надгробие — правило, отменённое владельцем. Тела таких правил НЕ удаляют: видно,
    /// что было и почему отменили. Признак — ЯВНАЯ шапка в самом начале тела.
    ///
    /// ⚠️ Проверка нарочно узкая: якорь «в начале строки» плюс закрытый список слов.
    ///    Свободный поиск «ОТОЗВАНО» где угодно в теле объявил бы отозванным ДЕЙСТВУЮЩЕЕ
    ///    правило, которое лишь упоминает отмену соседнего, — а это ошибка в опасную
    ///    сторону: приказ пропадает с глаз. Ошибка в другую сторону (отозванное не
    ///    распознано) оставляет правило среди тематических, то есть не хуже прежнего
    ///    плоского списка, где оно и лежало вперемешку.
    /// </summary>
    private static readonly System.Text.RegularExpressions.Regex TombstoneHead =
        new(@"^\s*(?:⛔\s*)?(ОТОЗВАНО|ОТМЕНЕНО|ОТМЕНЁНО)\b",
            System.Text.RegularExpressions.RegexOptions.Compiled);

    public static IReadOnlyList<RuleDto> ReadRules(SqliteConnection c, SchemaCapabilities s)
    {
        if (!s.Has("rules")) return [];

        var hasStatus = s.HasColumn("rules", "status");
        var list = new List<RuleDto>();

        using var cmd = c.CreateCommand();
        cmd.CommandText = "SELECT * FROM rules ORDER BY rule_key";
        using var r = cmd.ExecuteReader();
        var m = Row.Map(r);
        while (r.Read())
        {
            var body = Row.Str(r, m, "body") ?? "";
            var status = hasStatus ? Row.Str(r, m, "status") : null;

            // Порядок источников: поле статуса сильнее текста. Текст читаем ТОЛЬКО когда
            // поля нет вовсе — иначе просмотрщик спорил бы с самой базой.
            var (revoked, revokedBasis) = hasStatus
                ? (IsRevokedStatus(status), IsRevokedStatus(status) ? $"поле статуса: '{status}'" : null)
                : TombstoneHead.IsMatch(body)
                    ? (true, "шапка «⛔ ОТОЗВАНО» в начале текста (поля статуса в этой базе нет)")
                    : (false, (string?)null);

            list.Add(new RuleDto(
                RuleKey: Row.Str(r, m, "rule_key") ?? "?",
                // ⚠️ Если колонки статуса нет — НЕ пишем 'active'. В такой базе статус
                //    живёт прозой в теле («⛔ ОТОЗВАНО» в шапке), и объявить правило
                //    действующим за неё значит соврать ровно тем способом, ради которого
                //    статус и переносили в поле.
                Status: status,
                StatusNote: hasStatus ? null : "в этой базе у правил нет поля статуса — отзыв виден только по шапке текста",
                Version: (int?)Row.Num(r, m, "version"),
                LockedBy: Row.Str(r, m, "locked_by"),
                UpdatedAt: Row.Str(r, m, "updated_at"),
                BodyLength: body.Length,
                BodyPreview: Row.Preview(body, 300),
                Body: body,
                ExpiryKind: Row.Str(r, m, "expiry_kind"),
                ExpiryCond: Row.Str(r, m, "expiry_cond"),
                Basis: Row.Str(r, m, "basis"),
                Authorized: Row.Str(r, m, "authorized"),
                SourceRef: Row.Str(r, m, "source_ref"),
                Revoked: revoked,
                RevokedBasis: revokedBasis));
        }

        return list;
    }

    private static bool IsRevokedStatus(string? status) =>
        status is not null &&
        (status.Equals("revoked", StringComparison.OrdinalIgnoreCase) ||
         status.Equals("cancelled", StringComparison.OrdinalIgnoreCase) ||
         status.Equals("canceled", StringComparison.OrdinalIgnoreCase) ||
         status.Equals("отозвано", StringComparison.OrdinalIgnoreCase));

    // ── пул (П③ нового порядка, 28.08) ──────────────────────────────────────

    public static PoolsDto ReadPools(SqliteConnection c, SchemaCapabilities s)
    {
        // Пустой список БЕЗ причины читался бы как «пулов нет» и тогда, когда таблицы
        // нет вовсе, — тот же класс, что у критерия приёмки в обзоре.
        if (!s.Has("tracks"))
            return new PoolsDto([], "таблицы tracks в этой базе нет — пулы показать нечем");
        if (!s.Has("backlog"))
            return new PoolsDto([], "таблицы backlog нет — пул без карточек показать нечем");

        var hasSkills = s.HasColumn("tracks", "skills");
        var hasVerdicts = s.Has("track_verdicts");
        var pools = new List<PoolDto>();

        using (var cmd = c.CreateCommand())
        {
            cmd.CommandText = hasSkills
                ? "SELECT track_id, title, owner_decision, skills, plan_md FROM tracks WHERE status='active' ORDER BY track_id"
                : "SELECT track_id, title, owner_decision, NULL, plan_md FROM tracks WHERE status='active' ORDER BY track_id";
            using var r = cmd.ExecuteReader();
            while (r.Read())
            {
                var trackId = r.GetString(0);
                var plan = r.IsDBNull(4) ? null : r.GetString(4);
                var planHead = plan is null
                    ? null
                    : string.Join('\n', plan.Trim().Split('\n').Take(8));
                pools.Add(new PoolDto(
                    TrackId: trackId,
                    Title: r.IsDBNull(1) ? null : r.GetString(1),
                    OwnerWord: r.IsDBNull(2) ? null : r.GetString(2),
                    Skills: r.IsDBNull(3) ? null : r.GetString(3),
                    PlanHead: planHead,
                    CardsTotal: 0, CardsClosed: 0,
                    Cards: [], LiveClaims: [], OverdueClaims: [], Stuck: [], Verdicts: []));
            }
        }

        for (var i = 0; i < pools.Count; i++)
            pools[i] = FillPool(c, s, pools[i], hasVerdicts);

        var note = pools.Count == 0
            ? "активного пула нет (это опрошено, а не предположено)"
            : pools.Count > 1
                ? $"активных пулов {pools.Count} — норма нового порядка: ОДИН"
                : null;
        return new PoolsDto(pools, note);
    }

    private static PoolDto FillPool(SqliteConnection c, SchemaCapabilities s, PoolDto pool, bool hasVerdicts)
    {
        var criterionSupported = s.HasColumn("backlog", "done_when");
        var cards = new List<PoolCardDto>();
        using (var cmd = c.CreateCommand())
        {
            cmd.CommandText = "SELECT id, role, title, status, priority" +
                              (criterionSupported ? ", done_when" : ", NULL") +
                              " FROM backlog WHERE parent_track = $t ORDER BY role, id";
            cmd.Parameters.AddWithValue("$t", pool.TrackId);
            using var r = cmd.ExecuteReader();
            while (r.Read())
            {
                var role = r.IsDBNull(1) ? null : r.GetString(1);
                cards.Add(new PoolCardDto(
                    Id: r.GetInt64(0),
                    Role: role,
                    Title: r.IsDBNull(2) ? null : r.GetString(2),
                    Status: r.IsDBNull(3) ? null : r.GetString(3),
                    Priority: r.IsDBNull(4) ? null : r.GetString(4),
                    HasCriterion: !r.IsDBNull(5) && !string.IsNullOrWhiteSpace(r.GetString(5)),
                    // «Часть без хозяина» — витрина говорит СЛОВАМИ (П③: «⚠️ без хозяина»)
                    Ownerless: string.Equals(role, "SHARED", StringComparison.OrdinalIgnoreCase)));
            }
        }

        string[] closed = ["done", "failed", "dropped"];
        var openCards = cards.Where(k => !closed.Contains(k.Status ?? "")).ToArray();
        var stuck = openCards.Where(k => k.Status is "blocked" or "awaiting_word").ToArray();
        var (live, overdue) = ReadClaims(c, s, openCards.Select(k => k.Id).ToArray());

        var verdicts = new List<PoolVerdictDto>();
        if (hasVerdicts)
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText = "SELECT role, kind, verdict FROM track_verdicts WHERE track_id = $t ORDER BY id";
            cmd.Parameters.AddWithValue("$t", pool.TrackId);
            using var r = cmd.ExecuteReader();
            while (r.Read())
                verdicts.Add(new PoolVerdictDto(
                    r.IsDBNull(0) ? null : r.GetString(0),
                    r.IsDBNull(1) ? null : r.GetString(1),
                    r.IsDBNull(2) ? null : r.GetString(2)));
        }

        return pool with
        {
            CardsTotal = cards.Count,
            CardsClosed = cards.Count(k => closed.Contains(k.Status ?? "")),
            Cards = cards,
            LiveClaims = live,
            OverdueClaims = overdue,
            Stuck = stuck,
            Verdicts = verdicts
        };
    }

    /// <summary>
    /// Живые и просроченные объявления. ⚠️ КАНОН предиката — backlog.py::live_and_overdue
    /// (его зовут список карточек, обзор пробуждения, витрина пула и механизм сна);
    /// эта копия на C# меняется ВМЕСТЕ с ним. Просрочено = срок вышел, карточка
    /// не закрыта, объявление не снято, и ПОСЛЕ срока от роли на карточке ни события.
    /// </summary>
    private static (IReadOnlyList<PoolClaimDto> live, IReadOnlyList<PoolClaimDto> overdue)
        ReadClaims(SqliteConnection c, SchemaCapabilities s, long[] cardIds)
    {
        if (!s.Has("backlog_events") || cardIds.Length == 0) return ([], []);
        var live = new List<PoolClaimDto>();
        var overdue = new List<PoolClaimDto>();
        foreach (var id in cardIds)
        {
            using var cmd = c.CreateCommand();
            cmd.CommandText =
                "SELECT actor_role, event_type, body_md FROM backlog_events " +
                "WHERE backlog_id = $id AND event_type IN ('claim','claim_release') " +
                "ORDER BY id DESC LIMIT 1";
            cmd.Parameters.AddWithValue("$id", id);
            string? actor = null, body = null;
            using (var r = cmd.ExecuteReader())
            {
                if (!r.Read() || r.GetString(1) == "claim_release") continue;
                actor = r.IsDBNull(0) ? null : r.GetString(0);
                body = r.IsDBNull(2) ? null : r.GetString(2);
            }
            var m = System.Text.RegularExpressions.Regex.Match(
                body ?? "", @"^до (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC · (.*)$",
                System.Text.RegularExpressions.RegexOptions.Singleline);
            if (!m.Success) continue;
            var until = m.Groups[1].Value;
            var note = m.Groups[2].Value;
            var expired = ScalarLong(c, $"SELECT datetime('now') > '{until}'") == 1;
            if (!expired)
            {
                live.Add(new PoolClaimDto(id, actor, until, note, false, null));
                continue;
            }
            using var later = c.CreateCommand();
            later.CommandText = "SELECT 1 FROM backlog_events WHERE backlog_id = $id " +
                                "AND actor_role = $a AND at > $u LIMIT 1";
            later.Parameters.AddWithValue("$id", id);
            later.Parameters.AddWithValue("$a", actor ?? "");
            later.Parameters.AddWithValue("$u", until);
            if (later.ExecuteScalar() is not null) continue;      // роль подавала голос — не «молчит»
            var hours = ScalarLong(c,
                $"SELECT CAST((julianday('now') - julianday('{until}')) * 24 AS INTEGER)");
            overdue.Add(new PoolClaimDto(id, actor, until, note, true, hours));
        }
        return (live, overdue);
    }

    // ── схема ────────────────────────────────────────────────────────────────

    public static SchemaReportDto ReadSchemaReport(SchemaCapabilities s)
    {
        var present = s.Objects
            .OrderBy(o => o.Key, StringComparer.OrdinalIgnoreCase)
            .Select(o => new SchemaObjectDto(o.Key, o.Value, s.ColumnsOf(o.Key)))
            .ToArray();

        var known = ReferenceObjects.Concat(LegacyKnownObjects).ToHashSet(StringComparer.OrdinalIgnoreCase);

        return new SchemaReportDto(
            Present: present,
            ExpectedButMissing: ReferenceObjects.Where(o => !s.Has(o)).ToArray(),
            PresentButUnknownToPeriscope: s.Objects.Keys.Where(k => !known.Contains(k))
                .OrderBy(k => k, StringComparer.OrdinalIgnoreCase).ToArray(),
            Note: "«Ожидалось, но нет» — относительно эталона vnext/prototype/schema_vnext.sql. " +
                  "Это НЕ поломка: живая база и эталон расходятся законно, пока шаги перевода не применены. " +
                  "Список нужен, чтобы просмотрщик не выдавал отсутствие данных за их нулевое значение.");
    }

    // ── мелочь ───────────────────────────────────────────────────────────────

    private static Measure CountOf(SqliteConnection c, SchemaCapabilities s, string table) =>
        s.Has(table)
            ? new Measure(ScalarLong(c, $"SELECT COUNT(*) FROM \"{table}\""), true)
            : Measure.Unsupported($"нет объекта {table}");

    private static long? ScalarLong(SqliteConnection c, string sql)
    {
        using var cmd = c.CreateCommand();
        cmd.CommandText = sql;
        var v = cmd.ExecuteScalar();
        return v is null or DBNull ? null : Convert.ToInt64(v);
    }

    private static string? ScalarString(SqliteConnection c, string sql)
    {
        using var cmd = c.CreateCommand();
        cmd.CommandText = sql;
        var v = cmd.ExecuteScalar();
        return v is null or DBNull ? null : Convert.ToString(v);
    }
}
