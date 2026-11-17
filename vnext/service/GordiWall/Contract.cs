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
    /// <summary>Тело запустилось и кончилось ненулевым кодом: определённый отказ по его правилам или сбой внутри тела.</summary>
    ToolFailed,
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
        Outcome.ToolFailed => "tool_failed",
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
        "tool_failed" => Outcome.ToolFailed,
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
        Outcome.ToolFailed => "тело отказало",
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
    IReadOnlyList<string> MismatchWhen,
    // Объявленная передача значения аргумента вызова в переменную среды тела: имя переменной → имя аргумента.
    // Это единственный путь, которым значение попадает телу не командной строкой; прочие MEZO_* служба стирает.
    IReadOnlyDictionary<string, string>? Env = null)
{
    public IReadOnlyDictionary<string, string> EnvMap => Env ?? new Dictionary<string, string>();

    /// <summary>Имена аргументов вызова, которые это тело использует: командной строкой или переменной среды.</summary>
    public IEnumerable<string> UsedArgs => Args.Select(a => a.Arg).Concat(EnvMap.Values);
}

/// <summary>Один вариант вызова: своё тело и свой перечень обязательных аргументов.</summary>
public sealed record ToolVariant(
    string Key,                         // значение аргумента выбора, которым вариант выбирается
    string Title,
    IReadOnlyList<string> Requires,     // аргументы, обязательные именно в этом варианте
    ToolExec Exec);

public sealed record ToolDef(
    string Name,
    string Mode,            // read | write
    string Title,
    string? Description,
    IReadOnlyList<ToolArg> Args,
    ToolExec? Exec,         // null у вызова с вариантами: тело тогда у каждого варианта своё
    // Служебные таблицы, которые вызов вправе менять. null — поле в договоре не объявлено (у пишущих вызовов
    // так и бывает; у читающего это нарушение, его ловит приёмка); пустой список — читающий вызов не пишет ничего.
    IReadOnlyList<string>? ServiceWrites = null,
    string? VariantBy = null,                       // имя аргумента выбора варианта (у него есть enum)
    IReadOnlyList<ToolVariant>? Variants = null,    // по порядку договора
    string? DefaultVariant = null)                  // только у читающего вызова
{
    public bool HasVariants => VariantBy is not null;

    public IReadOnlyList<ToolVariant> VariantList => Variants ?? [];

    public ToolVariant? FindVariant(string? key) =>
        VariantList.FirstOrDefault(v => string.Equals(v.Key, key, StringComparison.Ordinal));

    /// <summary>Имена аргументов, которые относятся к варианту: упомянуты в его exec.args или exec.env.</summary>
    public HashSet<string> ArgsOf(ToolVariant v) => new(v.Exec.UsedArgs, StringComparer.Ordinal);
}

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

        var name = Str(t, "name") ?? throw new InvalidDataException("в договоре вызов без имени");
        var hasExec = t.TryGetProperty("exec", out var jex);
        var hasBy = t.TryGetProperty("variant_by", out _);
        var hasVariants = t.TryGetProperty("variants", out var jvars);
        if (hasExec == (hasBy || hasVariants))
            throw new InvalidDataException(hasExec
                ? $"у вызова «{name}» есть и exec, и variant_by/variants: тело либо одно, либо по вариантам, не оба"
                : $"у вызова «{name}» нет ни exec, ни variant_by с variants: исполнять нечем");
        if (hasBy != hasVariants)
            throw new InvalidDataException($"у вызова «{name}» {(hasBy ? "есть variant_by, а variants нет" : "есть variants, а variant_by нет")}: "
                                           + "вариантам нужны оба поля");

        var variants = new List<ToolVariant>();
        if (hasVariants)
        {
            if (jvars.ValueKind != JsonValueKind.Object)
                throw new InvalidDataException($"у вызова «{name}» variants — не объект «значение → вариант»");
            foreach (var kv in jvars.EnumerateObject())
            {
                if (!kv.Value.TryGetProperty("exec", out var vexec))
                    throw new InvalidDataException($"у варианта «{kv.Name}» вызова «{name}» нет exec");
                var requires = new List<string>();
                if (kv.Value.TryGetProperty("requires", out var jrq))
                {
                    if (jrq.ValueKind != JsonValueKind.Array)
                        throw new InvalidDataException($"у варианта «{kv.Name}» вызова «{name}» requires — не массив имён аргументов");
                    foreach (var r in jrq.EnumerateArray())
                        requires.Add(StrOnly(r, $"requires варианта «{kv.Name}» вызова «{name}»"));
                }
                variants.Add(new ToolVariant(kv.Name, Str(kv.Value, "title") ?? "", requires, ReadExec(vexec)));
            }
        }

        var tool = new ToolDef(
            Name: name,
            Mode: Str(t, "mode") ?? "read",
            Title: Str(t, "title") ?? "",
            Description: Str(t, "description"),
            Args: args,
            Exec: hasExec ? ReadExec(jex) : null,
            ServiceWrites: ReadServiceWrites(t),
            VariantBy: Str(t, "variant_by"),
            Variants: variants,
            DefaultVariant: Str(t, "default_variant"));
        Validate(tool);
        return tool;
    }

    private static readonly System.Text.RegularExpressions.Regex EnvName =
        new(@"^MEZO_[A-Z0-9_]+$", System.Text.RegularExpressions.RegexOptions.CultureInvariant);

    /// <summary>
    /// Разбор договора: правила о вариантах и передаче в среду. Нарушение — договор не загружается,
    /// причина названа вызовом и аргументом. Проверяется здесь, а не при вызове: кривой договор не должен доживать до роли.
    /// </summary>
    private static void Validate(ToolDef tool)
    {
        var declared = tool.Args.Select(a => a.Name).ToHashSet(StringComparer.Ordinal);
        var execs = new List<(string Where, ToolExec Exec, IReadOnlyList<string> Requires)>();
        if (tool.HasVariants)
            foreach (var v in tool.VariantList)
                execs.Add(($"вариант «{v.Key}» вызова «{tool.Name}»", v.Exec, v.Requires));
        else if (tool.Exec is { } single)
            execs.Add(($"вызов «{tool.Name}»", single, new List<string>()));

        // правила 4 и 7: всё названное в exec и requires — объявленные аргументы вызова; имя переменной среды — по образцу
        foreach (var (where, exec, requires) in execs)
        {
            foreach (var m in exec.Args)
                if (!declared.Contains(m.Arg))
                    throw new InvalidDataException($"в {where} exec.args ссылается на аргумент «{m.Arg}», которого вызов не объявляет");
            // сначала env (имя переменной и объявленность аргумента), потом requires: у него причина «не использует» зависит от env
            foreach (var (envName, argName) in exec.EnvMap)
            {
                if (!EnvName.IsMatch(envName))
                    throw new InvalidDataException($"в {where} имя переменной среды «{envName}» не по образцу ^MEZO_[A-Z0-9_]+$: договор не вправе подменять телу чужие переменные среды");
                if (!declared.Contains(argName))
                    throw new InvalidDataException($"в {where} exec.env передаёт в «{envName}» аргумент «{argName}», которого вызов не объявляет");
            }
            foreach (var r in requires)
            {
                if (!declared.Contains(r))
                    throw new InvalidDataException($"в {where} requires называет аргумент «{r}», которого вызов не объявляет");
                // свой аргумент варианта — тот, что назван в его exec.args или exec.env; иначе вариант невызываем
                if (!exec.UsedArgs.Contains(r))
                    throw new InvalidDataException($"в {where} requires называет аргумент «{r}», которого тело этого варианта не использует "
                                                   + "(нет ни в exec.args, ни в exec.env): вариант стал бы невызываемым");
            }
        }

        if (!tool.HasVariants)
        {
            if (tool.DefaultVariant is not null)
                throw new InvalidDataException($"у вызова «{tool.Name}» есть default_variant, а вариантов нет");
            return;
        }

        // правило 2: аргумент выбора объявлен, у него есть enum, и перечень значений равен набору вариантов
        var selector = tool.Args.FirstOrDefault(a => a.Name == tool.VariantBy)
            ?? throw new InvalidDataException($"у вызова «{tool.Name}» variant_by называет «{tool.VariantBy}», а такого аргумента вызов не объявляет");
        if (selector.Enum is not { Count: > 0 })
            throw new InvalidDataException($"у вызова «{tool.Name}» аргумент выбора «{selector.Name}» без enum: нечем перечислить варианты");
        var keys = tool.VariantList.Select(v => v.Key).ToHashSet(StringComparer.Ordinal);
        if (!keys.SetEquals(selector.Enum))
        {
            var noVariant = selector.Enum.Where(e => !keys.Contains(e)).ToList();
            var noValue = keys.Where(k => !selector.Enum.Contains(k)).ToList();
            throw new InvalidDataException($"у вызова «{tool.Name}» перечень значений «{selector.Name}» расходится с вариантами: "
                + (noVariant.Count > 0 ? $"у значений {string.Join(", ", noVariant)} нет варианта; " : "")
                + (noValue.Count > 0 ? $"у вариантов {string.Join(", ", noValue)} нет значения в enum" : ""));
        }

        // правило 3: умолчание — из перечня, пишущему вызову его не положено; без умолчания выбор обязателен
        if (tool.DefaultVariant is { } def)
        {
            if (!selector.Enum.Contains(def))
                throw new InvalidDataException($"у вызова «{tool.Name}» default_variant «{def}» не входит в enum аргумента «{selector.Name}»");
            if (!string.Equals(tool.Mode, "read", StringComparison.Ordinal))
                throw new InvalidDataException($"у пишущего вызова «{tool.Name}» есть default_variant «{def}»: "
                                               + "у записи умолчания быть не может, действие называется явно");
        }
        else if (!selector.Required)
            throw new InvalidDataException($"у вызова «{tool.Name}» нет default_variant, а аргумент выбора «{selector.Name}» не обязателен: "
                                           + "вариант выбирать нечем");

        // правила 5 и 6: каждый аргумент, кроме выбора, относится хоть к одному варианту; required на вызове значит «в каждом»
        foreach (var a in tool.Args.Where(a => a.Name != selector.Name))
        {
            var owners = tool.VariantList.Where(v => tool.ArgsOf(v).Contains(a.Name)).Select(v => v.Key).ToList();
            if (owners.Count == 0)
                throw new InvalidDataException($"у вызова «{tool.Name}» аргумент «{a.Name}» не относится ни к одному варианту: "
                                               + "его не упоминает ни один exec.args и ни один exec.env");
            if (a.Required && owners.Count != tool.VariantList.Count)
                throw new InvalidDataException($"у вызова «{tool.Name}» аргумент «{a.Name}» обязателен (required=true значит «в каждом варианте»), "
                                               + $"а относится только к вариантам: {string.Join(", ", owners)}");
        }
    }

    /// <summary>
    /// Строки вариантов вызова для справки и схемы MCP: «вариант X: обязательны …; можно …». Строятся из договора,
    /// второго текста нет. Обязательны — требуемое на вызове и в варианте; можно — остальные аргументы варианта.
    /// </summary>
    public static IReadOnlyList<string> VariantLines(ToolDef tool)
    {
        var lines = new List<string>();
        foreach (var v in tool.VariantList)
        {
            var own = tool.ArgsOf(v);
            var required = tool.Args.Where(a => a.Name != tool.VariantBy && ((a.Required && own.Contains(a.Name)) || v.Requires.Contains(a.Name)))
                                    .Select(a => a.Name).ToList();
            var optional = tool.Args.Where(a => a.Name != tool.VariantBy && own.Contains(a.Name) && !required.Contains(a.Name))
                                    .Select(a => a.Name).ToList();
            var def = string.Equals(v.Key, tool.DefaultVariant, StringComparison.Ordinal) ? " (по умолчанию)" : "";
            lines.Add($"вариант {tool.VariantBy}={v.Key}{def}: обязательны {(required.Count == 0 ? "—" : string.Join(", ", required))}; "
                      + $"можно {(optional.Count == 0 ? "—" : string.Join(", ", optional))} · {v.Title}");
        }
        return lines;
    }

    private static List<string>? ReadServiceWrites(JsonElement t)
    {
        if (!t.TryGetProperty("service_writes", out var jw) || jw.ValueKind != JsonValueKind.Array) return null;
        var list = new List<string>();
        foreach (var w in jw.EnumerateArray())
            list.Add(StrOnly(w, "service_writes"));
        return list;
    }

    private static ToolArg ReadArg(JsonElement a)
    {
        List<string>? values = null;
        if (a.TryGetProperty("enum", out var je) && je.ValueKind == JsonValueKind.Array)
        {
            values = new List<string>();
            foreach (var v in je.EnumerateArray())
                values.Add(StrOnly(v, "enum аргумента"));
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
                        pre.Add(StrOnly(w, "exec.pre"));
                else pre.Add(StrOnly(group, "exec.pre"));

        var sub = new List<string>();
        if (e.TryGetProperty("sub", out var js) && js.ValueKind == JsonValueKind.Array)
            foreach (var w in js.EnumerateArray())
                sub.Add(StrOnly(w, "exec.sub"));

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
                mismatch.Add(StrOnly(w, "exec.mismatch_when"));

        var env = new Dictionary<string, string>(StringComparer.Ordinal);
        if (e.TryGetProperty("env", out var jenv))
        {
            if (jenv.ValueKind != JsonValueKind.Object)
                throw new InvalidDataException("в договоре exec.env — не объект «имя переменной → имя аргумента»");
            foreach (var kv in jenv.EnumerateObject())
                env[kv.Name] = StrOnly(kv.Value, $"exec.env, переменная «{kv.Name}»");
        }

        return new ToolExec("python", null, Str(e, "dir"), Str(e, "script"), pre, sub, maps, mismatch, env);
    }

    /// <summary>
    /// Строгое чтение строки из перечня: значение не строки (число, null, объект) — договор не загружается,
    /// причина называет место. Прямой GetString() бросил бы InvalidOperationException и уронил службу трассировкой.
    /// </summary>
    private static string StrOnly(JsonElement v, string where) =>
        v.ValueKind == JsonValueKind.String
            ? v.GetString()!
            : throw new InvalidDataException($"в договоре в {where} значение вида {v.ValueKind}, а нужна строка");

    private static string? Str(JsonElement o, string name) =>
        o.TryGetProperty(name, out var v) && v.ValueKind == JsonValueKind.String ? v.GetString() : null;

    /// <summary>
    /// Отпечаток самого перечня вызовов — имена и режимы по порядку, у вызовов с вариантами ещё аргумент выбора и ключи
    /// вариантов. Нужен приёмке: он меняется при добавлении вызова и при снятии варианта (договор 2.0.0, карточка 781).
    /// </summary>
    public string ToolsFingerprint()
    {
        var joined = string.Join("\n", Tools.Select(t => t.Name + ":" + t.Mode
            + (t.HasVariants ? ":" + t.VariantBy + "=" + string.Join(",", t.VariantList.Select(v => v.Key)) : "")));
        return Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(joined)))[..12];
    }
}
