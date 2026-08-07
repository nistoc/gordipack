using System.Globalization;
using System.Text.Json;
using Microsoft.Data.Sqlite;

namespace Gordi.Periscope.Api.Data;

/// <summary>
/// Доступ к полям строки ПО ИМЕНИ, с честным «такой колонки тут нет».
///
/// Почему не обычное чтение по индексу: состав колонок в живой базе и в эталоне
/// отличается (замер — см. шапку SchemaProbe). Чтение по индексу упало бы на первой
/// же базе с другим порядком колонок; чтение по имени с проверкой — не упадёт,
/// а вернёт null, и вызывающий сам решит, что это значит.
///
/// ⚠️ И про типы: SQLite типизирован ДИНАМИЧЕСКИ — в колонке TEXT может лежать число.
///    Поэтому берём GetValue и конвертируем, а не GetString/GetInt64, которые в этом
///    случае бросают InvalidCastException.
/// </summary>
public static class Row
{
    public static Dictionary<string, int> Map(SqliteDataReader r)
    {
        var map = new Dictionary<string, int>(r.FieldCount, StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < r.FieldCount; i++)
            map[r.GetName(i)] = i;
        return map;
    }

    public static string? Str(SqliteDataReader r, Dictionary<string, int> m, string name)
    {
        if (!m.TryGetValue(name, out var i) || r.IsDBNull(i)) return null;
        var v = r.GetValue(i);
        return v as string ?? Convert.ToString(v, CultureInfo.InvariantCulture);
    }

    public static long? Num(SqliteDataReader r, Dictionary<string, int> m, string name)
    {
        if (!m.TryGetValue(name, out var i) || r.IsDBNull(i)) return null;
        try { return Convert.ToInt64(r.GetValue(i), CultureInfo.InvariantCulture); }
        catch { return null; }
    }

    public static bool? Bool(SqliteDataReader r, Dictionary<string, int> m, string name)
        => Num(r, m, name) is { } n ? n != 0 : null;

    /// <summary>Теги лежат строкой JSON-массива. Кривой JSON — не повод падать.</summary>
    public static string[] Tags(SqliteDataReader r, Dictionary<string, int> m, string name)
    {
        var raw = Str(r, m, name);
        if (string.IsNullOrWhiteSpace(raw)) return [];
        try
        {
            return JsonSerializer.Deserialize<string[]>(raw) ?? [];
        }
        catch (JsonException)
        {
            return [];
        }
    }

    /// <summary>
    /// Метки в базе — строки вида 'YYYY-MM-DD HH:MM:SS' в UTC (правило контура:
    /// время везде UTC). Часовой пояс НЕ угадываем: если разобрать не вышло —
    /// возвращаем null и показываем исходную строку как есть.
    /// </summary>
    public static DateTimeOffset? Utc(string? raw)
    {
        if (string.IsNullOrWhiteSpace(raw)) return null;
        var s = raw.Trim().Replace("UTC", "", StringComparison.OrdinalIgnoreCase).Replace('T', ' ').Trim();
        string[] formats = ["yyyy-MM-dd HH:mm:ss", "yyyy-MM-dd HH:mm", "yyyy-MM-dd"];
        if (DateTime.TryParseExact(s, formats, CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal, out var dt))
            return new DateTimeOffset(dt, TimeSpan.Zero);
        return null;
    }

    public static string Preview(string? body, int max = 400)
    {
        if (string.IsNullOrEmpty(body)) return "";
        return body.Length <= max ? body : body[..max] + "…";
    }
}
