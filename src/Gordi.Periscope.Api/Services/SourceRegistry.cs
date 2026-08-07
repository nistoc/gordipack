using Gordi.Periscope.Api.Configuration;
using Gordi.Periscope.Api.Data;
using Gordi.Periscope.Api.Model;
using Microsoft.Data.Sqlite;
using Microsoft.Extensions.Options;

namespace Gordi.Periscope.Api.Services;

/// <summary>
/// Какие базы видны и какая сейчас активна.
///
/// ⛔ ГРАНИЦА, ВЫБРАННАЯ НАМЕРЕННО: переключиться можно ТОЛЬКО на файл, найденный
///    под корнем обхода, заданным при запуске. Произвольный путь с фронтенда
///    не принимается — иначе локальный просмотрщик превращается в «прочитай любой
///    файл на этой машине по HTTP», и это уже не просмотрщик базы.
///    Корень задаёт человек аргументом запуска; интерфейс только выбирает из найденного.
/// </summary>
public sealed class SourceRegistry
{
    private static readonly string[] Patterns = ["*.db", "*.sqlite", "*.sqlite3"];

    private readonly PeriscopeOptions _options;
    private readonly ILogger<SourceRegistry> _log;
    private readonly Lock _gate = new();
    private string? _activePath;

    public SourceRegistry(IOptions<PeriscopeOptions> options, ILogger<SourceRegistry> log)
    {
        _options = options.Value;
        _log = log;

        if (!string.IsNullOrWhiteSpace(_options.Db))
        {
            var full = Path.GetFullPath(_options.Db);
            if (File.Exists(full)) _activePath = full;
            else _log.LogWarning("Файл базы не найден: {Path}", full);
        }
        else if (ScanRoot is { } root)
        {
            _activePath = Discover().FirstOrDefault()?.Path;
            if (_activePath is null) _log.LogWarning("В каталоге {Root} баз не найдено", root);
        }
        else
        {
            _log.LogWarning(
                "Источник не задан. Укажи --db <файл.db> или --dir <каталог> (либо GORDI_DB / GORDI_DIR).");
        }
    }

    /// <summary>Корень обхода: явный --dir, иначе каталог указанного файла базы.</summary>
    public string? ScanRoot
    {
        get
        {
            if (!string.IsNullOrWhiteSpace(_options.Directory))
            {
                var d = Path.GetFullPath(_options.Directory);
                return Directory.Exists(d) ? d : null;
            }

            var active = ActivePath;
            return active is null ? null : Path.GetDirectoryName(active);
        }
    }

    public string? ActivePath
    {
        get { lock (_gate) return _activePath; }
    }

    public IReadOnlyList<SourceInfo> Discover()
    {
        var root = ScanRoot;
        var active = ActivePath;
        var result = new List<SourceInfo>();

        if (root is not null && Directory.Exists(root))
        {
            var opts = new EnumerationOptions
            {
                RecurseSubdirectories = _options.ScanDepth > 0,
                MaxRecursionDepth = Math.Max(0, _options.ScanDepth),
                IgnoreInaccessible = true,
                AttributesToSkip = FileAttributes.System
            };

            foreach (var pattern in Patterns)
            {
                foreach (var path in Directory.EnumerateFiles(root, pattern, opts))
                {
                    try
                    {
                        var fi = new FileInfo(path);
                        result.Add(new SourceInfo(fi.FullName, fi.Name, fi.Length,
                            new DateTimeOffset(fi.LastWriteTimeUtc, TimeSpan.Zero),
                            string.Equals(fi.FullName, active, StringComparison.OrdinalIgnoreCase)));
                    }
                    catch (IOException)
                    {
                        // Файл исчез между перечислением и чтением — не повод падать.
                    }
                }
            }
        }

        // Активная база показывается всегда, даже если лежит вне корня обхода
        // (её указали явным --db). Иначе интерфейс показывал бы список, в котором
        // нет того, что сейчас открыто, — само по себе вводит в заблуждение.
        if (active is not null && !result.Any(x => string.Equals(x.Path, active, StringComparison.OrdinalIgnoreCase)))
        {
            var fi = new FileInfo(active);
            if (fi.Exists)
                result.Insert(0, new SourceInfo(fi.FullName, fi.Name, fi.Length,
                    new DateTimeOffset(fi.LastWriteTimeUtc, TimeSpan.Zero), true));
        }

        return result
            .DistinctBy(x => x.Path, StringComparer.OrdinalIgnoreCase)
            .OrderByDescending(x => x.IsActive)
            .ThenBy(x => x.Name, StringComparer.OrdinalIgnoreCase)
            .ToArray();
    }

    public bool TrySelect(string path, out string? error)
    {
        error = null;
        string full;
        try { full = Path.GetFullPath(path); }
        catch (Exception ex) { error = "путь не разобран: " + ex.Message; return false; }

        var candidates = Discover();
        if (!candidates.Any(x => string.Equals(x.Path, full, StringComparison.OrdinalIgnoreCase)))
        {
            error = "этот путь не входит в список найденных источников — " +
                    "переключение возможно только на базы под корнем обхода, заданным при запуске";
            return false;
        }

        lock (_gate) _activePath = full;
        _log.LogInformation("Активная база переключена на {Path}", full);
        return true;
    }

    /// <summary>
    /// Открыть активную базу на чтение. Бросает, если источник не задан.
    /// </summary>
    public SqliteConnection OpenActive()
    {
        var path = ActivePath
                   ?? throw new InvalidOperationException("Источник не задан: нет активной базы.");
        return ReadOnlyDb.Open(_options.CopyBeforeRead ? EnsureCopy(path) : path);
    }

    public string Fingerprint()
    {
        var path = ActivePath;
        return path is null ? "" : ReadOnlyDb.Fingerprint(path);
    }

    // ── копия перед чтением (по умолчанию выключено) ──────────────────────────
    //
    // ⚠️ ЧЕСТНО ПРО ЭТУ ВЕТКУ: она НЕ ПРОВЕРЕНА на живой базе. Копируются три файла
    //    (.db, -wal, -shm), и открывается копия. Если журнал -wal при копировании был
    //    непуст, копии может понадобиться восстановление, а на чтение оно не всегда
    //    возможно. Прямое чтение живого файла (ветка по умолчанию) на базе в режиме WAL
    //    ПРОВЕРЕНО и работает. Ветку оставляю как заготовку под случай «нет прав рядом
    //    с файлом» — включать осознанно, флагом CopyBeforeRead.

    private string _copyFingerprint = "";
    private string? _copyPath;

    private string EnsureCopy(string source)
    {
        lock (_gate)
        {
            var fp = ReadOnlyDb.Fingerprint(source);
            if (_copyPath is not null && fp == _copyFingerprint && File.Exists(_copyPath))
                return _copyPath;

            var dir = Path.Combine(Path.GetTempPath(), "gordi-periscope",
                Math.Abs(source.GetHashCode()).ToString());
            Directory.CreateDirectory(dir);
            var target = Path.Combine(dir, Path.GetFileName(source));

            foreach (var suffix in new[] { "", "-wal", "-shm" })
            {
                if (File.Exists(source + suffix))
                    File.Copy(source + suffix, target + suffix, overwrite: true);
                else if (File.Exists(target + suffix))
                    File.Delete(target + suffix);
            }

            _copyPath = target;
            _copyFingerprint = fp;
            return target;
        }
    }
}
