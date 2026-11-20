using System.Text.Json;

namespace GordiWall;

/// <summary>
/// Один контур: ЕГО хранилище и ЕГО каталоги инструментов. О версии и отпечатках тулинга манифест НЕ судит: их пишет
/// установщик в хранилище. LegacyToolingBlock — только ФАКТ «в файле остался блок tooling»; его значения не читаются.
/// </summary>
public sealed record ContourInfo(
    string Id,
    string Title,
    string Storage,
    IReadOnlyDictionary<string, string> ToolDirs,
    bool LegacyToolingBlock);

/// <summary>
/// Манифест контуров. Отвечает на имя контура, переданное В ВЫЗОВЕ, — и только на него.
/// Имени, которого здесь нет, стена отказывает: догадываться о пути ей нечем и не нужно.
/// </summary>
public sealed class Manifest
{
    public required string Python { get; init; }
    public required int TimeoutSeconds { get; init; }
    public required int MaxOutputChars { get; init; }
    public required IReadOnlyList<ContourInfo> Contours { get; init; }
    public required string Path { get; init; }

    public ContourInfo? Find(string id) =>
        Contours.FirstOrDefault(c => string.Equals(c.Id, id, StringComparison.Ordinal));

    public static Manifest Load(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllBytes(path));
        var root = doc.RootElement;

        var timeout = 120;
        var maxChars = 60000;
        if (root.TryGetProperty("limits", out var lim))
        {
            if (lim.TryGetProperty("timeout_seconds", out var ts) && ts.TryGetInt32(out var tv)) timeout = tv;
            if (lim.TryGetProperty("max_output_chars", out var mc) && mc.TryGetInt32(out var mv)) maxChars = mv;
        }

        var contours = new List<ContourInfo>();
        foreach (var c in root.GetProperty("contours").EnumerateArray())
        {
            var dirs = new Dictionary<string, string>(StringComparer.Ordinal);
            if (c.TryGetProperty("tools", out var jt) && jt.ValueKind == JsonValueKind.Object)
                foreach (var p in jt.EnumerateObject())
                    if (p.Value.GetString() is { } dir) dirs[p.Name] = dir;

            contours.Add(new ContourInfo(
                Id: Str(c, "id") ?? throw new InvalidDataException("в манифесте контур без имени"),
                Title: Str(c, "title") ?? "",
                Storage: Str(c, "storage") ?? throw new InvalidDataException("в манифесте контур без хранилища"),
                ToolDirs: dirs,
                LegacyToolingBlock: c.TryGetProperty("tooling", out _)));
        }

        return new Manifest
        {
            Python = Str(root, "python") ?? "python",
            TimeoutSeconds = timeout,
            MaxOutputChars = maxChars,
            Contours = contours,
            Path = System.IO.Path.GetFullPath(path),
        };
    }

    private static string? Str(JsonElement o, string name) =>
        o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    /// <summary>Имена контуров через точку-разделитель — для текста отказа: роль должна видеть, из чего выбирать.</summary>
    public string KnownIds() => string.Join(" · ", Contours.Select(c => c.Id));
}
