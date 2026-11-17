using System.Text.Json;
using System.Text.RegularExpressions;

namespace GordiWall;

/// <summary>
/// Весь ответ длинного вывода, сохранённый на диске: из него выдаются части по метке продолжения.
/// Диск, а не память: режим run — отдельный процесс на каждый вызов, память живёт один вызов.
/// </summary>
public sealed class SpoolEntry
{
    public string Tool { get; set; } = "";
    public string Contour { get; set; } = "";
    public string ToolingVersion { get; set; } = "";
    /// <summary>Исход ТЕЛА (id из закрытого перечня): его получает последняя часть.</summary>
    public string FinalOutcome { get; set; } = "";
    public int? ChildExit { get; set; }
    public string? Error { get; set; }
    public string Warnings { get; set; } = "";
    public bool Truncated { get; set; }
    public string? TruncateReason { get; set; }
    public List<string> Parts { get; set; } = [];
}

public static class PartSpool
{
    /// <summary>Срок хранения ответа. Просроченные файлы стена убирает при каждом обращении к каталогу.</summary>
    public static readonly TimeSpan Lifetime = TimeSpan.FromHours(2);

    public const string DirName = "gordi-wall-spool";

    // Имя нашего файла — 32 шестнадцатеричных знака. По этому образцу стена опознаёт СВОИ файлы
    // и не трогает чужие, а метка продолжения не может увести путь за пределы каталога.
    private static readonly Regex FileName = new(@"^[0-9a-f]{32}\.(json|tmp)$", RegexOptions.Compiled);
    private static readonly Regex Label = new(@"^([0-9a-f]{32})\.([0-9]{1,6})$", RegexOptions.Compiled);

    public static string Dir => Path.Combine(Path.GetTempPath(), DirName);

    /// <summary>Делит текст на части по границам строк. Часть не длиннее предела; строка длиннее предела режется по пределу.</summary>
    public static List<string> Split(string text, int limit)
    {
        var parts = new List<string>();
        var cur = new System.Text.StringBuilder();
        var pos = 0;
        while (pos < text.Length)
        {
            var nl = text.IndexOf('\n', pos);
            var end = nl < 0 ? text.Length : nl + 1;      // строка вместе со своим переводом строки
            var line = text.AsSpan(pos, end - pos);
            pos = end;

            if (cur.Length + line.Length <= limit)
            {
                cur.Append(line);
                continue;
            }

            if (cur.Length > 0) { parts.Add(cur.ToString()); cur.Clear(); }

            // строка длиннее предела режется по пределу; парная суррогатная пара не рвётся
            while (line.Length > limit)
            {
                var take = limit;
                if (take > 1 && char.IsHighSurrogate(line[take - 1])) take--;
                parts.Add(line[..take].ToString());
                line = line[take..];
            }
            cur.Append(line);
        }
        if (cur.Length > 0) parts.Add(cur.ToString());
        return parts;
    }

    public static string MakeLabel(string id, int part) => id + "." + part;

    /// <summary>Сохраняет ответ; отдаёт случайный id. Ошибка записи — исключение, выше её называют словами.</summary>
    public static string Save(SpoolEntry entry)
    {
        var dir = Dir;
        Directory.CreateDirectory(dir);
        Purge(dir);
        var id = Guid.NewGuid().ToString("n");
        var tmp = Path.Combine(dir, id + ".tmp");
        File.WriteAllText(tmp, JsonSerializer.Serialize(entry), new System.Text.UTF8Encoding(false));
        File.Move(tmp, Path.Combine(dir, id + ".json"));
        return id;
    }

    /// <summary>Находит сохранённый ответ по метке. Отказ — понятная причина.</summary>
    public static bool TryLoad(string label, out SpoolEntry? entry, out int part, out string why)
    {
        entry = null;
        part = 0;
        var m = Label.Match(label.Trim());
        if (!m.Success)
        {
            why = $"метка продолжения «{label}» не опознана: такую метку стена не печатала";
            return false;
        }

        var dir = Dir;
        if (Directory.Exists(dir)) Purge(dir);
        var file = Path.Combine(dir, m.Groups[1].Value + ".json");
        if (!File.Exists(file))
        {
            why = $"метка продолжения «{label}» неизвестна или просрочена: части хранятся {Lifetime.TotalHours:0} ч. "
                  + "Повторите исходный вызов без next_part.";
            return false;
        }

        try
        {
            entry = JsonSerializer.Deserialize<SpoolEntry>(File.ReadAllText(file));
        }
        catch (Exception e) when (e is IOException or JsonException)
        {
            why = $"сохранённый ответ по метке «{label}» не читается: {e.Message}";
            return false;
        }

        part = int.Parse(m.Groups[2].Value, System.Globalization.CultureInfo.InvariantCulture);
        if (entry is null || part < 1 || part > entry.Parts.Count)
        {
            why = $"метка продолжения «{label}» называет часть {part}, а в сохранённом ответе частей "
                  + (entry?.Parts.Count ?? 0);
            return false;
        }

        why = "";
        return true;
    }

    /// <summary>Убирает просроченные файлы — только СВОИ (по образцу имени) и только в своём подкаталоге.</summary>
    private static void Purge(string dir)
    {
        try
        {
            var border = DateTime.UtcNow - Lifetime;
            foreach (var f in Directory.EnumerateFiles(dir))
            {
                if (!FileName.IsMatch(Path.GetFileName(f))) continue;
                try
                {
                    if (File.GetLastWriteTimeUtc(f) < border) File.Delete(f);
                }
                catch (IOException) { }
                catch (UnauthorizedAccessException) { }
            }
        }
        catch (IOException) { }
        catch (UnauthorizedAccessException) { }
    }
}
