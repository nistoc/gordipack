using Gordi.Periscope.Api.Configuration;
using Gordi.Periscope.Api.Data;
using Gordi.Periscope.Api.Model;
using Gordi.Periscope.Api.Services;
using Microsoft.Extensions.Options;

namespace Gordi.Periscope.Api.Endpoints;

public static class ApiEndpoints
{
    public static void MapApi(this WebApplication app)
    {
        var api = app.MapGroup("/api");

        // ── состояние сервиса ────────────────────────────────────────────────
        api.MapGet("/health", (SourceRegistry sources, SnapshotStore store, IOptions<PeriscopeOptions> opt) =>
        {
            var path = sources.ActivePath;
            var status = path is null ? "no-source" : store.LastError is not null ? "error" : "ok";

            // ReadOnly — ЗАМЕРОМ по живому соединению, не константой: подмена любого из
            // трёх замков (Mode / query_only / канарейка записи) делает поле false.
            var readOnly = true;
            if (path is not null)
            {
                try
                {
                    using var probe = ReadOnlyDb.Open(path);
                    readOnly = ReadOnlyDb.ProveReadOnly(probe);
                }
                catch { /* база недоступна — статус скажет своё, замок не о чем мерить */ }
            }

            return Results.Ok(new HealthDto(
                Status: status,
                ActiveDbPath: path,
                ScanRoot: sources.ScanRoot,
                ReadOnly: readOnly,
                RefreshSeconds: opt.Value.RefreshSeconds,
                LastRefreshUtc: store.LastRefreshUtc,
                LastChangeDetectedUtc: store.LastChangeDetectedUtc,
                LastError: store.LastError,
                NowUtc: DateTimeOffset.UtcNow));
        });

        // ── источники ────────────────────────────────────────────────────────
        api.MapGet("/sources", (SourceRegistry sources) => Results.Ok(sources.Discover()));

        api.MapPost("/sources/select",
            (SelectSourceRequest body, SourceRegistry sources, SnapshotStore store, SnapshotRefreshService refresher) =>
            {
                if (string.IsNullOrWhiteSpace(body.Path))
                    return Results.BadRequest(new { error = "не передан путь" });

                if (!sources.TrySelect(body.Path, out var error))
                    return Results.BadRequest(new { error });

                // Старый снимок принадлежит другой базе — показывать его под новым
                // именем источника значит показывать чужие числа.
                store.Clear();
                try { refresher.Refresh(); }
                catch (Exception ex) { store.Fail(ex.Message); }

                return Results.Ok(new { active = sources.ActivePath });
            });

        api.MapPost("/refresh", (SnapshotRefreshService refresher, SnapshotStore store) =>
        {
            try
            {
                refresher.Refresh();
                return Results.Ok(new { refreshedAtUtc = store.LastRefreshUtc, error = store.LastError });
            }
            catch (Exception ex)
            {
                store.Fail(ex.Message);
                return Results.Problem(ex.Message, statusCode: StatusCodes.Status503ServiceUnavailable);
            }
        });

        // ── снимок ───────────────────────────────────────────────────────────
        api.MapGet("/overview", (SnapshotStore store) =>
            store.Current is { } s ? Results.Ok(s.Overview) : NoSnapshot(store));

        api.MapGet("/schema", (SnapshotStore store) =>
            store.Current is { } s ? Results.Ok(s.Schema) : NoSnapshot(store));

        api.MapGet("/roles", (SnapshotStore store) =>
            store.Current is { } s ? Results.Ok(s.Roles) : NoSnapshot(store));

        api.MapGet("/rules", (SnapshotStore store) =>
            store.Current is { } s ? Results.Ok(s.Rules) : NoSnapshot(store));

        // ── пул (П③ нового порядка): план, части по ролям, «кто где», застрявшее ──
        api.MapGet("/pool", (SnapshotStore store) =>
            store.Current is { } s ? Results.Ok(s.Pools) : NoSnapshot(store));

        // ── наборы задач ─────────────────────────────────────────────────────
        api.MapGet("/tracks", (SnapshotStore store) =>
            store.Current is { } s ? Results.Ok(BuildTracks(s)) : NoSnapshot(store));

        // ── задачи ───────────────────────────────────────────────────────────
        api.MapGet("/tasks", (SnapshotStore store, string? status, string? role, string? track, bool? missingCriterion) =>
        {
            if (store.Current is not { } s) return NoSnapshot(store);

            IEnumerable<TaskDto> items = s.Tasks;

            if (!string.IsNullOrWhiteSpace(status) && status != "all")
                items = items.Where(t => string.Equals(t.Status, status, StringComparison.OrdinalIgnoreCase));

            if (!string.IsNullOrWhiteSpace(role) && role != "all")
                items = items.Where(t => string.Equals(t.Role, role, StringComparison.OrdinalIgnoreCase));

            if (!string.IsNullOrWhiteSpace(track) && !IsAllKey(track))
            {
                // «none» и «all» — СЛУЖЕБНЫЕ значения отбора. Если такое имя однажды
                // окажется настоящим набором, отбор молча вернул бы не то — поэтому
                // здесь отказ СО СЛОВОМ и с названным обходным путём, а не тихий ответ.
                if (TrackNameTaken(s, track))
                    return Results.BadRequest(new
                    {
                        error = $"имя набора «{track}» совпадает со служебным значением отбора " +
                                "(«all» — все наборы, «none» — задачи без набора). " +
                                "Возьмите этот набор через GET /api/tasks/grouped — там имена не толкуются."
                    });

                items = IsUntrackedKey(track)
                    ? items.Where(t => string.IsNullOrWhiteSpace(t.ParentTrack))
                    : items.Where(t => string.Equals(t.ParentTrack, track, StringComparison.OrdinalIgnoreCase));
            }

            if (missingCriterion == true)
                items = items.Where(t => t.CriterionSupported && !t.HasCriterion);

            return Results.Ok(items.ToArray());
        });

        // Задачи, сгруппированные по наборам. Группа «без набора» — ПОСЛЕДНЯЯ и всегда
        // на месте, пока такие задачи есть: её отсутствие читалось бы как «таких нет».
        api.MapGet("/tasks/grouped", (SnapshotStore store, string? status, string? role) =>
        {
            if (store.Current is not { } s) return NoSnapshot(store);

            IEnumerable<TaskDto> items = s.Tasks;

            if (!string.IsNullOrWhiteSpace(status) && status != "all")
                items = items.Where(t => string.Equals(t.Status, status, StringComparison.OrdinalIgnoreCase));

            if (!string.IsNullOrWhiteSpace(role) && role != "all")
                items = items.Where(t => string.Equals(t.Role, role, StringComparison.OrdinalIgnoreCase));

            return Results.Ok(BuildGroups(s, items.ToArray()));
        });

        api.MapGet("/tasks/{id:long}", (long id, SourceRegistry sources, SnapshotStore store) =>
        {
            if (sources.ActivePath is null) return NoSnapshot(store);
            using var c = sources.OpenActive();
            var caps = SchemaCapabilities.Probe(c);
            var detail = MezosyncReader.ReadTask(c, caps, id);
            return detail is null ? Results.NotFound() : Results.Ok(detail);
        });

        // ── лента ────────────────────────────────────────────────────────────
        api.MapGet("/messages",
            (SourceRegistry sources, SnapshotStore store, IOptions<PeriscopeOptions> opt,
                int? limit, int? offset, string? role, string? priority, string? search, string? source) =>
            {
                if (sources.ActivePath is null) return NoSnapshot(store);

                var o = opt.Value;
                var take = Math.Clamp(limit ?? o.FeedPageSize, 1, o.FeedMaxPageSize);
                var skip = Math.Max(0, offset ?? 0);

                using var c = sources.OpenActive();
                var caps = SchemaCapabilities.Probe(c);
                var page = MezosyncReader.ReadMessages(c, caps,
                    new MessageQuery(take, skip, role, priority, search, source));
                return Results.Ok(page);
            });

        api.MapGet("/messages/{id:long}", (long id, SourceRegistry sources, SnapshotStore store) =>
        {
            if (sources.ActivePath is null) return NoSnapshot(store);
            using var c = sources.OpenActive();
            var caps = SchemaCapabilities.Probe(c);
            var message = MezosyncReader.ReadMessage(c, caps, id);
            return message is null ? Results.NotFound() : Results.Ok(message);
        });

        api.MapGet("/writers", (SourceRegistry sources, SnapshotStore store) =>
        {
            if (sources.ActivePath is null) return NoSnapshot(store);
            using var c = sources.OpenActive();
            var caps = SchemaCapabilities.Probe(c);
            return Results.Ok(MezosyncReader.DistinctWriters(c, caps));
        });
    }

    // ── служебные значения отбора по набору ──────────────────────────────────
    private const string UntrackedKey = "none";
    private const string AllKey = "all";

    private static bool IsUntrackedKey(string v) => string.Equals(v, UntrackedKey, StringComparison.OrdinalIgnoreCase);
    private static bool IsAllKey(string v) => string.Equals(v, AllKey, StringComparison.OrdinalIgnoreCase);

    /// <summary>Правда ли, что служебное имя занято настоящим набором — по задачам И по
    /// таблице наборов: набор может быть заявлен и пока пуст.</summary>
    private static bool TrackNameTaken(PeriscopeSnapshot s, string name) =>
        (IsUntrackedKey(name) || IsAllKey(name)) &&
        (s.Tasks.Any(t => string.Equals(t.ParentTrack, name, StringComparison.OrdinalIgnoreCase)) ||
         s.TrackDeclarations.Any(d => string.Equals(d.TrackId, name, StringComparison.OrdinalIgnoreCase)));

    /// <summary>
    /// Витрина наборов: заявленные (включая пустые — «набор есть и пуст» это факт,
    /// а его отсутствие читалось бы как «набора нет») и НЕзаявленные, которые задачи
    /// называют сами.
    /// </summary>
    private static TracksDto BuildTracks(PeriscopeSnapshot s)
    {
        var counts = s.Tasks
            .Where(t => !string.IsNullOrWhiteSpace(t.ParentTrack))
            .GroupBy(t => t.ParentTrack!, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(g => g.Key, g => g.Count(), StringComparer.OrdinalIgnoreCase);

        var items = new List<TrackInfoDto>();
        foreach (var d in s.TrackDeclarations)
            items.Add(new TrackInfoDto(d.TrackId, d.Title, d.Status, Declared: true,
                TaskCount: counts.TryGetValue(d.TrackId, out var n) ? n : 0));

        var declared = new HashSet<string>(s.TrackDeclarations.Select(d => d.TrackId), StringComparer.OrdinalIgnoreCase);
        foreach (var pair in counts.Where(p => !declared.Contains(p.Key)).OrderBy(p => p.Key, StringComparer.OrdinalIgnoreCase))
            items.Add(new TrackInfoDto(pair.Key, Title: null, Status: null, Declared: false, TaskCount: pair.Value));

        var untracked = s.Tasks.Count(t => string.IsNullOrWhiteSpace(t.ParentTrack));
        var undeclared = items.Count(i => !i.Declared);

        var note = s.TrackDeclarations.Count == 0
            ? "таблицы tracks в этой базе нет — наборы собраны по одним значениям parent_track, заголовков и статусов у них не будет"
            : undeclared > 0
                ? $"наборов, которых нет в таблице tracks: {undeclared} — их задачи видны, но заголовка и статуса у них нет"
                : null;

        return new TracksDto(items, untracked, s.Tasks.Count, note);
    }

    /// <summary>
    /// Группировка задач по наборам. Порядок: заявленные (active → paused → done → прочее,
    /// внутри по имени) → незаявленные → «без набора» последней.
    /// Сумма Count по группам обязана равняться числу поданных задач; расхождение
    /// называется в Note, а не молчит.
    /// </summary>
    private static TasksGroupedDto BuildGroups(PeriscopeSnapshot s, IReadOnlyList<TaskDto> tasks)
    {
        static int StatusOrder(string? status) => status?.ToLowerInvariant() switch
        {
            "active" => 0,
            "paused" => 1,
            "done" => 2,
            _ => 3
        };

        var byTrack = tasks
            .Where(t => !string.IsNullOrWhiteSpace(t.ParentTrack))
            .GroupBy(t => t.ParentTrack!, StringComparer.OrdinalIgnoreCase)
            .ToDictionary(g => g.Key, g => (IReadOnlyList<TaskDto>)g.OrderBy(t => t.Id).ToArray(),
                StringComparer.OrdinalIgnoreCase);

        var groups = new List<TaskGroupDto>();

        foreach (var d in s.TrackDeclarations
                     .OrderBy(d => StatusOrder(d.Status))
                     .ThenBy(d => d.TrackId, StringComparer.OrdinalIgnoreCase))
        {
            var items = byTrack.TryGetValue(d.TrackId, out var list) ? list : [];
            groups.Add(new TaskGroupDto(d.TrackId, d.Title, d.Status, Declared: true, items.Count, items));
        }

        var declared = new HashSet<string>(s.TrackDeclarations.Select(d => d.TrackId), StringComparer.OrdinalIgnoreCase);
        foreach (var pair in byTrack.Where(p => !declared.Contains(p.Key))
                     .OrderBy(p => p.Key, StringComparer.OrdinalIgnoreCase))
            groups.Add(new TaskGroupDto(pair.Key, Title: null, Status: null, Declared: false,
                pair.Value.Count, pair.Value));

        var untracked = tasks.Where(t => string.IsNullOrWhiteSpace(t.ParentTrack)).OrderBy(t => t.Id).ToArray();
        if (untracked.Length > 0)
            groups.Add(new TaskGroupDto(TrackId: null, Title: "без набора", Status: null,
                Declared: false, untracked.Length, untracked));

        var undeclared = groups.Count(g => g.TrackId is not null && !g.Declared);
        var sum = groups.Sum(g => g.Count);

        var notes = new List<string>();
        if (s.TrackDeclarations.Count == 0)
            notes.Add("таблицы tracks в этой базе нет — группы собраны по одним значениям parent_track");
        if (undeclared > 0)
            notes.Add($"групп без записи в таблице tracks: {undeclared} — их задачи показаны, заголовка и статуса у них нет");
        if (sum != tasks.Count)
            notes.Add($"🔴 сумма по группам {sum} не сошлась с числом задач {tasks.Count} — часть задач потеряна группировкой");

        return new TasksGroupedDto(groups, tasks.Count, untracked.Length, undeclared,
            notes.Count == 0 ? null : string.Join("; ", notes));
    }

    /// <summary>
    /// Снимка ещё нет. Отвечаем 503 с причиной, а НЕ пустым списком:
    /// пустой список читался бы как «в базе ничего нет».
    /// </summary>
    private static IResult NoSnapshot(SnapshotStore store) =>
        Results.Problem(
            detail: store.LastError ?? "источник не задан или снимок ещё не собран",
            statusCode: StatusCodes.Status503ServiceUnavailable,
            title: "Данных пока нет");
}

public sealed record SelectSourceRequest(string Path);
