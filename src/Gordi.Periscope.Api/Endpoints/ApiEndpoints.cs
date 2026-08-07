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
            return Results.Ok(new HealthDto(
                Status: status,
                ActiveDbPath: path,
                ScanRoot: sources.ScanRoot,
                ReadOnly: true,
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

        // ── задачи ───────────────────────────────────────────────────────────
        api.MapGet("/tasks", (SnapshotStore store, string? status, string? role, bool? missingCriterion) =>
        {
            if (store.Current is not { } s) return NoSnapshot(store);

            IEnumerable<TaskDto> items = s.Tasks;

            if (!string.IsNullOrWhiteSpace(status) && status != "all")
                items = items.Where(t => string.Equals(t.Status, status, StringComparison.OrdinalIgnoreCase));

            if (!string.IsNullOrWhiteSpace(role) && role != "all")
                items = items.Where(t => string.Equals(t.Role, role, StringComparison.OrdinalIgnoreCase));

            if (missingCriterion == true)
                items = items.Where(t => t.CriterionSupported && !t.HasCriterion);

            return Results.Ok(items.ToArray());
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
