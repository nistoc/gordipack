using Gordi.Periscope.Api.Configuration;
using Gordi.Periscope.Api.Data;
using Gordi.Periscope.Api.Model;
using Microsoft.Extensions.Options;

namespace Gordi.Periscope.Api.Services;

/// <summary>
/// Фоновое перечитывание базы по таймеру. Это и есть «периодически берёт инфу».
///
/// Что в снимок ВХОДИТ: обзор, задачи, роли, правила, отчёт по схеме — вместе
/// это единицы сотен строк, дёшево и держать, и пересобирать.
/// Что НЕ входит: лента. Замер живой базы 2026-08-06 16:39 UTC — 3028 записок,
/// суммарно ~5.25 МБ тел, самое длинное 10 938 символов. Держать это в памяти ради
/// страницы из 50 строк незачем: лента читается запросом, тоже только на чтение.
///
/// ⚠️ Числа выше — со ЗВОНКОЙ датой, потому что база живая: за двадцать минут того же
///    замера в ней прибавилось 7 записок и появились два новых представления.
///    Порядок величины устойчив, точное значение — нет.
/// </summary>
public sealed class SnapshotRefreshService(
    SourceRegistry sources,
    SnapshotStore store,
    IOptions<PeriscopeOptions> options,
    ILogger<SnapshotRefreshService> log) : BackgroundService
{
    private readonly PeriscopeOptions _options = options.Value;

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var period = TimeSpan.FromSeconds(Math.Max(2, _options.RefreshSeconds));
        log.LogInformation("Перечитывание базы каждые {Seconds} с", period.TotalSeconds);

        using var timer = new PeriodicTimer(period);
        do
        {
            try
            {
                Refresh();
            }
            catch (Exception ex)
            {
                // Ошибка одного тика не должна убивать службу: база могла
                // на секунду оказаться занята, источник — исчезнуть.
                store.Fail(ex.Message);
                log.LogWarning(ex, "Не удалось перечитать базу");
            }
        } while (await timer.WaitForNextTickAsync(stoppingToken).ConfigureAwait(false));
    }

    /// <summary>Пересобрать снимок немедленно (таймер и ручное «обновить»).</summary>
    public void Refresh()
    {
        var path = sources.ActivePath;
        if (path is null)
        {
            store.Touch();
            return;
        }

        var fingerprint = sources.Fingerprint();
        var previous = store.Current;

        // Отпечаток совпал — файл, скорее всего, не менялся, пересборка не нужна.
        // «Скорее всего» здесь не отговорка: отпечаток строится по длине и времени
        // правки .db и -wal, а время правки файла ненадёжно в принципе. Если отпечаток
        // ошибётся, цена — снимок на один тик старше, не более.
        if (previous is not null && previous.Fingerprint == fingerprint && previous.DbPath == path)
        {
            store.Touch();
            return;
        }

        using var c = sources.OpenActive();
        var caps = SchemaCapabilities.Probe(c);

        var snapshot = new PeriscopeSnapshot(
            DbPath: path,
            Fingerprint: fingerprint,
            BuiltAtUtc: DateTimeOffset.UtcNow,
            Overview: MezosyncReader.ReadOverview(c, caps),
            Tasks: MezosyncReader.ReadTasks(c, caps),
            Roles: MezosyncReader.ReadRoles(c, caps),
            Rules: MezosyncReader.ReadRules(c, caps),
            Schema: MezosyncReader.ReadSchemaReport(caps),
            Pools: MezosyncReader.ReadPools(c, caps),
            TrackDeclarations: MezosyncReader.ReadTrackDeclarations(c, caps));

        store.Publish(snapshot, changed: previous is null || previous.Fingerprint != fingerprint);
    }
}
