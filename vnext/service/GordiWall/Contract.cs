using System.Security.Cryptography;
using System.Text;
using System.Text.Json;

namespace GordiWall;

/// <summary>Исход вызова. Закрытый перечень: код выхода дочернего процесса договором НЕ является.</summary>
public enum Outcome
{
    Passed,
    Mismatch,
    NotStarted,
    CannotVerify,
    Refused,
    /// <summary>Тело отработало, но ответ отдан НЕ целиком: есть продолжение (аргумент next_part).</summary>
    Partial,
}

public static class OutcomeNames
{
    // Левое уходит машине (приёмке), правое — человеку. Оба из договора, второго источника нет.
    public static string Id(Outcome o) => o switch
    {
        Outcome.Passed => "passed",
        Outcome.Mismatch => "mismatch",
        Outcome.NotStarted => "not_started",
        Outcome.CannotVerify => "cannot_verify",
        Outcome.Refused => "refused",
        Outcome.Partial => "partial",
        _ => "cannot_verify",
    };

    public static Outcome? Parse(string? id) => id switch
    {
        "passed" => Outcome.Passed,
        "mismatch" => Outcome.Mismatch,
        "not_started" => Outcome.NotStarted,
        "cannot_verify" => Outcome.CannotVerify,
        "refused" => Outcome.Refused,
        "partial" => Outcome.Partial,
        _ => null,
    };

    public static string Title(Outcome o) => o switch
    {
        Outcome.Passed => "прошло",
        Outcome.Mismatch => "расхождение",
        Outcome.NotStarted => "не запустилось",
        Outcome.CannotVerify => "не смог проверить",
        Outcome.Refused => "отказ",
        Outcome.Partial => "частично",
        _ => "не смог проверить",
    };
}

/// <summary>Один аргумент вызова, как его видит роль.</summary>
public sealed record ToolArg(
    string Name,
    string Type,
    bool Required,
    string? Description,
    IReadOnlyList<string>? Enum,
    string? Selects = null);   // что выбирает значение аргумента; «contour» — контур, на котором исполняется вызов

/// <summary>Как аргумент ложится в командную строку тела инструмента.</summary>
public sealed record ArgMap(string Arg, string Form, string? Flag, string? ConstAfter);

/// <summary>Чем именно исполняется вызов.</summary>
public sealed record ToolExec(
    string Kind,            // "python" — тело на Python; "builtin" — отвечает сама служба
    string? Builtin,
    string? Dir,            // ключ каталога инструментов в манифесте контура: runtime | vnext
    string? Script,
    IReadOnlyList<string> Pre,
    IReadOnlyList<string> Sub,
    IReadOnlyList<ArgMap> Args,
    IReadOnlyList<string> MismatchWhen);

public sealed record ToolDef(
    string Name,
    string Mode,            // read | write
    string Title,
    string? Description,
    IReadOnlyList<ToolArg> Args,
    ToolExec Exec);

/// <summary>
/// Договор, прочитанный из ОДНОГО файла. И служба, и однократный вызов мимо службы
/// строят свои перечни из него же: расходиться не с чем.
/// </summary>
public sealed class Contract
{
    public required string Name { get; init; }
    public required string Version { get; init; }
    public required string Stage { get; init; }
    public required string Description { get; init; }
    public required string Basis { get; init; }
    public required IReadOnlyList<ToolDef> Tools { get; init; }
    /// <summary>Все общие аргументы договора — весь массив common_args, а не первый его элемент.</summary>
    public required IReadOnlyList<ToolArg> CommonArgs { get; init; }
    /// <summary>Имя общего аргумента, выбирающего контур. Узнаётся из пометки selects=contour в договоре, в коде имени нет.</summary>
    public required string ContourArgName { get; init; }
    public required string Fingerprint { get; init; }   // sha256 по СОДЕРЖИМОМУ файла договора
    public required string Path { get; init; }

    public const string SelectsContour = "contour";

    public ToolDef? Find(string name) =>
        Tools.FirstOrDefault(t => string.Equals(t.Name, name, StringComparison.Ordinal));

    public static Contract Load(string path)
    {
        var bytes = File.ReadAllBytes(path);
        var fingerprint = Convert.ToHexStringLower(SHA256.HashData(bytes))[..12];
        using var doc = JsonDocument.Parse(bytes);
        var root = doc.RootElement;

        var head = root.GetProperty("contract");
        var tools = new List<ToolDef>();
        foreach (var t in root.GetProperty("tools").EnumerateArray())
            tools.Add(ReadTool(t));

        var common = new List<ToolArg>();
        foreach (var a in root.GetProperty("common_args").EnumerateArray())
            common.Add(ReadArg(a));

        // Какой общий аргумент выбирает контур — говорит договор пометкой selects=contour. Угадывать нельзя.
        var marked = common.Where(a => string.Equals(a.Selects, SelectsContour, StringComparison.Ordinal)).ToList();
        if (marked.Count == 0)
            throw new InvalidDataException($"в договоре {path} ни у одного общего аргумента нет пометки selects=\"{SelectsContour}\": "
                                           + "служба не знает, какой аргумент выбирает контур, и угадывать не вправе");
        if (marked.Count > 1)
            throw new InvalidDataException($"в договоре {path} пометка selects=\"{SelectsContour}\" стоит у {marked.Count} общих аргументов "
                                           + $"({string.Join(", ", marked.Select(a => a.Name))}): выбирать контур может ровно один");
        if (!marked[0].Required)
            throw new InvalidDataException($"в договоре {path} аргумент выбора контура «{marked[0].Name}» не обязателен (required не true): "
                                           + "исполнять вызов без контура не на чем, а угадывать контур служба не вправе");

        return new Contract
        {
            Name = Str(head, "name") ?? "gordi",
            Version = Str(head, "version") ?? "0",
            Stage = Str(head, "stage") ?? "",
            Description = Str(head, "description") ?? "",
            Basis = Str(head, "basis") ?? "",
            Tools = tools,
            CommonArgs = common,
            ContourArgName = marked[0].Name,
            Fingerprint = fingerprint,
            Path = System.IO.Path.GetFullPath(path),
        };
    }

    private static ToolDef ReadTool(JsonElement t)
    {
        var args = new List<ToolArg>();
        if (t.TryGetProperty("args", out var ja) && ja.ValueKind == JsonValueKind.Array)
            foreach (var a in ja.EnumerateArray())
                args.Add(ReadArg(a));

        return new ToolDef(
            Name: Str(t, "name") ?? throw new InvalidDataException("в договоре вызов без имени"),
            Mode: Str(t, "mode") ?? "read",
            Title: Str(t, "title") ?? "",
            Description: Str(t, "description"),
            Args: args,
            Exec: ReadExec(t.GetProperty("exec")));
    }

    private static ToolArg ReadArg(JsonElement a)
    {
        List<string>? values = null;
        if (a.TryGetProperty("enum", out var je) && je.ValueKind == JsonValueKind.Array)
        {
            values = new List<string>();
            foreach (var v in je.EnumerateArray())
                if (v.GetString() is { } s) values.Add(s);
        }

        return new ToolArg(
            Name: Str(a, "name") ?? throw new InvalidDataException("в договоре аргумент без имени"),
            Type: Str(a, "type") ?? "string",
            Required: a.TryGetProperty("required", out var jr) && jr.ValueKind == JsonValueKind.True,
            Description: Str(a, "description"),
            Enum: values,
            Selects: Str(a, "selects"));
    }

    private static ToolExec ReadExec(JsonElement e)
    {
        if (Str(e, "kind") == "builtin")
            return new ToolExec("builtin", Str(e, "builtin"), null, null, [], [], [], []);

        var pre = new List<string>();
        if (e.TryGetProperty("pre", out var jp) && jp.ValueKind == JsonValueKind.Array)
            foreach (var group in jp.EnumerateArray())
                // «pre» — список групп: группа может быть парой («--db», «{db}») или одиночным словом
                if (group.ValueKind == JsonValueKind.Array)
                    foreach (var w in group.EnumerateArray())
                    { if (w.GetString() is { } s) pre.Add(s); }
                else if (group.GetString() is { } single) pre.Add(single);

        var sub = new List<string>();
        if (e.TryGetProperty("sub", out var js) && js.ValueKind == JsonValueKind.Array)
            foreach (var w in js.EnumerateArray())
                if (w.GetString() is { } s) sub.Add(s);

        var maps = new List<ArgMap>();
        if (e.TryGetProperty("args", out var ja) && ja.ValueKind == JsonValueKind.Array)
            foreach (var m in ja.EnumerateArray())
                maps.Add(new ArgMap(
                    Arg: Str(m, "arg") ?? throw new InvalidDataException("в договоре отображение без имени аргумента"),
                    Form: Str(m, "form") ?? "flag",
                    Flag: Str(m, "flag"),
                    ConstAfter: Str(m, "const_after")));

        var mismatch = new List<string>();
        if (e.TryGetProperty("mismatch_when", out var jm) && jm.ValueKind == JsonValueKind.Array)
            foreach (var w in jm.EnumerateArray())
                if (w.GetString() is { } s) mismatch.Add(s);

        return new ToolExec("python", null, Str(e, "dir"), Str(e, "script"), pre, sub, maps, mismatch);
    }

    private static string? Str(JsonElement o, string name) =>
        o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    /// <summary>Отпечаток самого перечня вызовов — имена по порядку. Нужен приёмке: он меняется при добавлении вызова.</summary>
    public string ToolsFingerprint()
    {
        var joined = string.Join("\n", Tools.Select(t => t.Name + ":" + t.Mode));
        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(joined)))[..12];
    }
}
