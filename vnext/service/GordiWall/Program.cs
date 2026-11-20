using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace GordiWall;

/// <summary>
/// Стена контура gordi. Три режима одной сборки — договор у них ОДИН файл:
///   serve  — служба MCP по стандартному вводу-выводу (роли зовут её как инструменты);
///   run    — однократный вызов мимо службы, ТОЛЬКО чтение (запас на случай, когда служба не поднялась);
///   tools  — перечень вызовов и отпечатки (ими судит приёмка);
///   help   — справка: общая и по вызову (то же дают --help и -h). Ей нужен только договор.
/// </summary>
public static class Program
{
    private static readonly JsonSerializerOptions Json = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        WriteIndented = false,
    };

    // ────────────────────────────────── перечень режимов: ОДНО место, его берут справка и отказ «режима нет»

    private const string ServeMode = "serve", RunMode = "run", ToolsMode = "tools", HelpMode = "help";

    /// <summary>Флаг режима run: вместо текста один документ JSON. Имя занято: договор не вправе объявить аргумент с таким именем.</summary>
    private const string JsonFlag = "--json";

    private sealed record ModeInfo(string Name, string Purpose);

    private static readonly ModeInfo[] Modes =
    [
        new(ServeMode, "служба MCP по стандартному вводу-выводу (так её зовут роли)"),
        new(RunMode, "однократный вызов мимо службы, только чтение (запас на случай, когда служба не поднялась)"),
        new(ToolsMode, "перечень вызовов, число и отпечатки договора (ими судит приёмка)"),
        new(HelpMode, "эта справка; «help <вызов>» — справка по вызову; то же дают --help и -h"),
    ];

    private static string ModeNames => string.Join(" · ", Modes.Select(m => m.Name));

    // флаги режима run: ТО ЖЕ место, откуда справка берёт режимы
    private static readonly ModeInfo[] RunFlags =
    [
        new(JsonFlag, "вместо текста один документ JSON: тот же структурный ответ, что служба MCP кладёт в structuredContent "
                      + "(общие поля и details); код выхода прежний, по исходу; действует для любого вызова"),
    ];

    // ────────────────────────────────── исход → код выхода режима run: ОДНО место, его берут RunOnceAsync и справка

    private static readonly (Outcome Outcome, int Code)[] ExitCodes =
    [
        (Outcome.Passed, 0),
        (Outcome.Mismatch, 1),
        (Outcome.NotStarted, 2),
        (Outcome.CannotVerify, 3),
        (Outcome.Refused, 4),
        (Outcome.Partial, 5),       // ответ отдан частями: есть продолжение (аргумент next_part)
        (Outcome.ToolFailed, 6),    // тело запустилось и отказало определённо (ненулевой код тела), причина — в error
    ];

    // Код выхода ПОВТОРЯЕТ типизированный исход, а не заменяет его: договор — в тексте. Неизвестный исход — как отказ.
    private static int ExitCodeOf(Outcome o) =>
        ExitCodes.Where(e => e.Outcome == o).Select(e => e.Code).DefaultIfEmpty(4).First();

    // Код отказа до исполнения: и для отказов самого режима (нет договора, нет вызова), и для исхода Refused.
    private static readonly int RefusalCode = ExitCodeOf(Outcome.Refused);

    public static async Task<int> Main(string[] rawArgs)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        var args = rawArgs.ToList();

        // --help и -h распознаются ДО выбора режима по умолчанию: иначе первый аргумент с «-» дал бы режим serve,
        // и вместо справки поднялась бы служба и стала ждать ввода.
        var wantsHelp = args.Any(IsHelpFlag);
        string mode;
        if (args.Count > 0 && !args[0].StartsWith('-'))
        {
            mode = args[0];
            args.RemoveAt(0);
        }
        else mode = wantsHelp ? HelpMode : ServeMode;

        // Справку по вызову берут режимы help и run (run <вызов> --help); у остальных режимов справка общая
        var modeTakesTool = mode is RunMode or HelpMode;
        if (wantsHelp && Modes.Any(m => m.Name == mode))
        {
            args.RemoveAll(IsHelpFlag);
            mode = HelpMode;
        }

        var contractPath = Take(args, "--contract") ?? Environment.GetEnvironmentVariable("GORDI_CONTRACT") ?? ProbeContract();
        var contoursPath = Take(args, "--contours") ?? Environment.GetEnvironmentVariable("GORDI_CONTOURS") ?? ProbeContours();
        var readOnly = TakeSwitch(args, "--read-only") || mode == RunMode;
        var asJson = TakeSwitch(args, JsonFlag);
        var helpTool = mode == HelpMode && modeTakesTool && args.Count > 0 && !args[0].StartsWith('-') ? args[0] : null;

        if (asJson && mode != RunMode)
        {
            await Console.Error.WriteLineAsync($"отказ: флаг {JsonFlag} действует только в режиме {RunMode}, а режим здесь «{mode}».");
            return RefusalCode;
        }

        if (contractPath is null)
        {
            await Console.Error.WriteLineAsync("отказ: файла договора нет. Укажите --contract <путь> или GORDI_CONTRACT. "
                + "Ожидался contract/gordi-contract.json рядом со сборкой или выше по дереву.");
            return RefusalCode;
        }

        Contract contract;
        try
        {
            contract = Contract.Load(contractPath);
        }
        catch (Exception e) when (e is IOException or JsonException or InvalidDataException)
        {
            await Console.Error.WriteLineAsync($"отказ: договор не читается ({contractPath}): {e.Message}");
            return RefusalCode;
        }

        if (mode == ToolsMode)
            return await PrintToolsAsync(contract, contoursPath);

        // Имя флага занято: договор с таким аргументом не должен молча терять его за флагом режима run
        if ((mode == RunMode || mode == ServeMode) && JsonFlagClash(contract) is { } clash)
        {
            await Console.Error.WriteLineAsync($"отказ: договор объявляет аргумент «json» ({clash}), а имя {JsonFlag} занято флагом режима {RunMode} "
                + "(вывод одним документом JSON). Переименуйте аргумент в договоре: флаг не должен молча заслонять аргумент.");
            return RefusalCode;
        }

        // Справке нужен только договор: ветка стоит ДО проверки манифеста контуров, как и tools
        if (mode == HelpMode)
            return await PrintHelpAsync(contract, helpTool);

        if (contoursPath is null)
        {
            await Console.Error.WriteLineAsync("отказ: манифеста контуров нет. Укажите --contours <путь> или GORDI_CONTOURS. "
                + "Стена НАМЕРЕННО не угадывает контур по своему расположению: образец — contour/gordi-contours.example.json, "
                + "боевой файл кладёт установщик тулинга под именем contour/gordi-contours.json.");
            return RefusalCode;
        }

        Manifest manifest;
        try
        {
            manifest = Manifest.Load(contoursPath);
        }
        catch (Exception e) when (e is IOException or JsonException or InvalidDataException)
        {
            await Console.Error.WriteLineAsync($"отказ: манифест не читается ({contoursPath}): {e.Message}");
            return RefusalCode;
        }

        var runner = new ToolRunner(contract, manifest, readOnly);

        return mode switch
        {
            ServeMode => await ServeAsync(contract, manifest, runner),
            RunMode => await RunOnceAsync(contract, runner, args, asJson),
            _ => await UnknownModeAsync(mode),
        };
    }

    /// <summary>Где в договоре объявлен аргумент с именем «json» (общий или аргумент вызова); нет такого — null.</summary>
    private static string? JsonFlagClash(Contract contract)
    {
        if (contract.CommonArgs.Any(a => Flag(a.Name) == JsonFlag)) return "общий аргумент";
        var tool = contract.Tools.FirstOrDefault(t => t.Args.Any(a => Flag(a.Name) == JsonFlag));
        return tool is null ? null : $"аргумент вызова «{tool.Name}»";
    }

    private static bool IsHelpFlag(string a) =>
        string.Equals(a, "--help", StringComparison.Ordinal) || string.Equals(a, "-h", StringComparison.Ordinal);

    private static async Task<int> UnknownModeAsync(string mode)
    {
        await Console.Error.WriteLineAsync($"отказ: режима «{mode}» нет. Есть: {ModeNames}");
        return RefusalCode;
    }

    // ────────────────────────────────── справка: всё из договора и из двух мест кода (режимы, коды выхода)

    private static string ModeWord(ToolDef t) => t.Mode == "write" ? "запись" : "чтение";

    /// <summary>Имя аргумента как флаг командной строки: «next_part» → «--next-part» (обратное правило — в RunOnceAsync).</summary>
    private static string Flag(string argName) => "--" + argName.Replace('_', '-');

    /// <summary>Первые строки договора: их печатают и tools, и справка, расходиться им не с чем.</summary>
    private static void AppendContractLines(StringBuilder sb, Contract contract)
    {
        sb.AppendLine($"договор ................ {contract.Path}");
        sb.AppendLine($"версия ................. {contract.Version} (этап {contract.Stage})");
        sb.AppendLine($"отпечаток договора ..... {contract.Fingerprint}");
        sb.AppendLine($"отпечаток перечня ...... {contract.ToolsFingerprint()}");
    }

    private static async Task<int> PrintHelpAsync(Contract contract, string? toolName)
    {
        if (toolName is null)
        {
            await Console.Out.WriteAsync(GeneralHelp(contract));
            return 0;
        }

        var tool = contract.Find(toolName);
        if (tool is null)
        {
            // стандартный вывод остаётся пустым: справка по несуществующему вызову не должна ничего выдавать за ответ
            await Console.Error.WriteLineAsync($"отказ: вызова «{toolName}» в договоре нет. Есть: "
                + string.Join(" · ", contract.Tools.Select(t => t.Name)));
            return RefusalCode;
        }

        await Console.Out.WriteAsync(ToolHelp(contract, tool));
        return 0;
    }

    private static string GeneralHelp(Contract contract)
    {
        var sb = new StringBuilder();
        sb.AppendLine("gordi-wall — стена контура: вызовы тулинга по одному файлу договора");
        sb.AppendLine();
        sb.AppendLine("режимы:");
        foreach (var m in Modes)
            sb.AppendLine($"  {m.Name,-8} {m.Purpose}");
        sb.AppendLine();
        sb.AppendLine("флаги режима run:");
        foreach (var f in RunFlags)
            sb.AppendLine($"  {f.Name,-8} {f.Purpose}");
        sb.AppendLine();
        sb.AppendLine("договор:");
        AppendContractLines(sb, contract);
        sb.AppendLine();
        sb.AppendLine($"вызовы ({contract.Tools.Count}): чтение или запись · имя · заголовок");
        foreach (var t in contract.Tools)
            sb.AppendLine($"  {ModeWord(t)}  {t.Name,-18} {t.Title}");
        sb.AppendLine();
        sb.AppendLine("форма вызова в режиме run (только чтение):");
        // Имя аргумента выбора контура — из договора, как и в отказе «не назван вызов»
        sb.AppendLine($"  gordi-wall run <вызов> {Flag(contract.ContourArgName)} <контур> [--аргумент значение]");
        sb.AppendLine("справка по вызову:");
        sb.AppendLine("  gordi-wall help <вызов>");
        sb.AppendLine();
        sb.AppendLine("исход вызова и код выхода режима run:");
        foreach (var (outcome, code) in ExitCodes)
            sb.AppendLine($"  {code}  {OutcomeNames.Id(outcome),-14} {OutcomeNames.Title(outcome)}");
        return sb.ToString();
    }

    private static string ToolHelp(Contract contract, ToolDef t)
    {
        var sb = new StringBuilder();
        sb.AppendLine($"вызов {t.Name} — {ModeWord(t)}");
        sb.AppendLine($"заголовок: {t.Title}");
        if (!string.IsNullOrEmpty(t.Description))
            sb.AppendLine($"описание: {t.Description.ReplaceLineEndings(" ")}");
        sb.AppendLine();
        sb.AppendLine("общие аргументы (у каждого вызова):");
        foreach (var a in contract.CommonArgs)
            AppendArg(sb, a);
        sb.AppendLine("аргументы вызова:");
        if (t.Args.Count == 0)
            sb.AppendLine("  нет");
        foreach (var a in t.Args)
            AppendArg(sb, a);
        if (t.HasVariants)
        {
            sb.AppendLine("варианты (строки те же, что в режиме tools):");
            // строки вариантов строятся из договора, руками не пишутся
            foreach (var line in Contract.VariantLines(t))
                sb.AppendLine($"  {line}");
        }
        sb.AppendLine(t.ServiceWrites is { Count: > 0 } writes
            ? $"служебные записи: {string.Join(", ", writes)}"
            : t.ServiceWrites is null ? "служебные записи: в договоре не объявлены" : "служебные записи: нет");
        sb.AppendLine();
        sb.AppendLine("пример формы вызова через run:");
        sb.AppendLine($"  {ExampleLine(contract, t)}");
        if (t.Mode == "write")
            sb.AppendLine("  режим run этот вызов отвергнет: он пишет; зовите его через службу MCP.");
        else if (t.HasVariants)
            sb.AppendLine("  обязательное по вариантам — в строках вариантов выше.");
        return sb.ToString();
    }

    private static void AppendArg(StringBuilder sb, ToolArg a)
    {
        var line = $"  {Flag(a.Name)} <{a.Type}> · {(a.Required ? "обязателен" : "не обязателен")}";
        if (a.Enum is { Count: > 0 } values)
            line += " · значения: " + string.Join(" | ", values);
        sb.AppendLine(line);
        if (!string.IsNullOrEmpty(a.Description))
            sb.AppendLine("      " + a.Description.ReplaceLineEndings(" "));
    }

    /// <summary>Форма вызова: обязательные общие аргументы и все аргументы вызова (необязательные — в скобках).</summary>
    private static string ExampleLine(Contract contract, ToolDef t)
    {
        static string Placeholder(ToolArg a) =>
            a.Selects == Contract.SelectsContour ? " <контур>" : a.Type == "bool" ? "" : $" <{a.Type}>";

        var parts = new List<string> { "gordi-wall", RunMode, t.Name };
        parts.AddRange(contract.CommonArgs.Where(a => a.Required).Select(a => Flag(a.Name) + Placeholder(a)));
        parts.AddRange(t.Args.Select(a => a.Required ? Flag(a.Name) + Placeholder(a) : "[" + Flag(a.Name) + Placeholder(a) + "]"));
        return string.Join(" ", parts);
    }

    // ────────────────────────────────── перечень вызовов

    private static async Task<int> PrintToolsAsync(Contract contract, string? contoursPath)
    {
        var sb = new StringBuilder();
        AppendContractLines(sb, contract);
        sb.AppendLine($"манифест контуров ...... {contoursPath ?? "НЕ НАЗВАН"}");
        sb.AppendLine($"вызовов ................ {contract.Tools.Count}");
        sb.AppendLine();
        var commonNames = string.Join(" ", contract.CommonArgs.Select(a => a.Required ? a.Name : "[" + a.Name + "]"));
        foreach (var t in contract.Tools)
        {
            var argNames = t.Args.Count == 0 ? "—" : string.Join(" ", t.Args.Select(a => a.Required ? a.Name : "[" + a.Name + "]"));
            sb.AppendLine($"  {ModeWord(t)}  {t.Name,-18} {commonNames} {argNames}");
            if (t.ServiceWrites is { Count: > 0 } writes)
                sb.AppendLine($"          служебные записи: {string.Join(", ", writes)}");
            // строки вариантов строятся из договора, руками не пишутся
            foreach (var line in Contract.VariantLines(t))
                sb.AppendLine($"          {line}");
        }
        await Console.Out.WriteAsync(sb.ToString());
        return 0;
    }

    // ────────────────────────────────── однократный вызов мимо службы (только чтение)

    private static async Task<int> RunOnceAsync(Contract contract, ToolRunner runner, List<string> args, bool asJson)
    {
        if (args.Count == 0 || args[0].StartsWith('-'))
        {
            // Имя аргумента выбора контура — из договора, а не литерал: договор вправе его переименовать
            await Console.Error.WriteLineAsync("отказ: не назван вызов. Форма: gordi-wall run <вызов> --"
                + contract.ContourArgName.Replace('_', '-') + " <контур> [--аргумент значение]");
            return RefusalCode;
        }

        var toolName = args[0];
        args.RemoveAt(0);

        // Незнакомый аргумент отвергает сам ToolRunner.CallAsync — одно место для службы и для режима run
        var given = new Dictionary<string, object?>(StringComparer.Ordinal);

        for (var i = 0; i < args.Count; i++)
        {
            if (!args[i].StartsWith("--", StringComparison.Ordinal)) continue;
            var name = args[i][2..].Replace('-', '_');
            var hasValue = i + 1 < args.Count && !args[i + 1].StartsWith("--", StringComparison.Ordinal);
            given[name] = hasValue ? args[++i] : true;
        }

        await Console.Error.WriteLineAsync("⚠️ вызов идёт МИМО службы, режим только-чтение: служба MCP либо не поднята, либо её обошли. "
            + "Запись этим путём отвергается намеренно.");

        var answer = await runner.CallAsync(toolName, given, CancellationToken.None);

        // --json: один документ JSON, тот же структурный ответ, что служба MCP кладёт в structuredContent
        if (asJson)
        {
            await Console.Out.WriteLineAsync(StructuredOf(answer).ToJsonString(Json));
            return ExitCodeOf(answer.Outcome);
        }

        await Console.Out.WriteAsync(answer.ForRole());
        // У ответа по частям текст печатается как есть: лишний перевод строки сломал бы точность склейки частей
        if (answer.Parts == 1 && !answer.ForRole().EndsWith('\n')) await Console.Out.WriteLineAsync();

        // Таблица «исход → код выхода» — одна, над Main: её же печатает справка
        return ExitCodeOf(answer.Outcome);
    }

    // ────────────────────────────────── служба MCP по стандартному вводу-выводу

    private static async Task<int> ServeAsync(Contract contract, Manifest manifest, ToolRunner runner)
    {
        using var stdin = new StreamReader(Console.OpenStandardInput(), new UTF8Encoding(false));
        await using var stdout = new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true };

        await Console.Error.WriteLineAsync($"стена поднята: вызовов {contract.Tools.Count} · отпечаток договора {contract.Fingerprint} "
            + $"· контуров {manifest.Contours.Count} ({manifest.KnownIds()})");

        while (await stdin.ReadLineAsync() is { } line)
        {
            if (string.IsNullOrWhiteSpace(line)) continue;

            JsonNode? req;
            try { req = JsonNode.Parse(line); }
            catch (JsonException e)
            {
                await WriteAsync(stdout, Error(null, -32700, "разбор запроса не удался: " + e.Message));
                continue;
            }
            if (req is null) continue;

            var method = req["method"]?.GetValue<string>();
            var id = req["id"];

            try
            {
                switch (method)
                {
                    case "initialize":
                        await WriteAsync(stdout, Result(id, new JsonObject
                        {
                            ["protocolVersion"] = "2024-11-05",
                            ["capabilities"] = new JsonObject { ["tools"] = new JsonObject() },
                            ["serverInfo"] = new JsonObject
                            {
                                ["name"] = "gordi-wall",
                                ["version"] = contract.Version,
                                // commit, из которого собрана стена: «кто меня судит» с точностью до сборки
                                ["build_commit"] = BuildInfo.CommitForServerInfo,
                            },
                            ["instructions"] = contract.Description,
                        }));
                        break;

                    case "notifications/initialized":
                    case "initialized":
                        break;  // извещение — ответа не ждут

                    case "ping":
                        await WriteAsync(stdout, Result(id, new JsonObject()));
                        break;

                    case "tools/list":
                        await WriteAsync(stdout, Result(id, new JsonObject { ["tools"] = ToolList(contract) }));
                        break;

                    case "tools/call":
                        await WriteAsync(stdout, await CallAsync(runner, req, id));
                        break;

                    default:
                        if (id is not null)
                            await WriteAsync(stdout, Error(id, -32601, $"метода «{method}» у стены нет"));
                        break;
                }
            }
            catch (Exception e) when (e is IOException or JsonException or InvalidOperationException)
            {
                if (id is not null)
                    await WriteAsync(stdout, Error(id, -32603, "стена отказала: " + e.Message));
            }
        }

        return 0;
    }

    private static async Task<JsonObject> CallAsync(ToolRunner runner, JsonNode req, JsonNode? id)
    {
        var p = req["params"];
        var name = p?["name"]?.GetValue<string>();
        if (string.IsNullOrEmpty(name))
            return Error(id, -32602, "в вызове не назван инструмент");

        var given = new Dictionary<string, object?>(StringComparer.Ordinal);
        if (p?["arguments"] is JsonObject jo)
            foreach (var kv in jo)
                given[kv.Key] = kv.Value switch
                {
                    null => null,
                    JsonValue v when v.TryGetValue<bool>(out var b) => b,
                    JsonValue v when v.TryGetValue<long>(out var l) => l,
                    JsonValue v when v.TryGetValue<string>(out var s) => s,
                    JsonArray arr => string.Join(",", arr.Select(x => x?.ToString() ?? "")),
                    var other => other.ToJsonString(),
                };

        var answer = await runner.CallAsync(name, given, CancellationToken.None);

        return Result(id, new JsonObject
        {
            ["content"] = new JsonArray(new JsonObject
            {
                ["type"] = "text",
                ["text"] = answer.ForRole(),
            }),
            ["structuredContent"] = StructuredOf(answer),
            // isError НЕ равен «исход не passed»: расхождение и явное незнание — тоже честные ответы,
            // а не поломка вызова. Поломкой здесь считается только отказ договора.
            ["isError"] = answer.Outcome == Outcome.Refused,
        });
    }

    /// <summary>Структурный ответ вызова: его кладёт в structuredContent служба MCP и печатает режим run с флагом --json. Одно место для обоих.</summary>
    private static JsonObject StructuredOf(Answer answer) => new()
    {
        ["outcome"] = OutcomeNames.Id(answer.Outcome),
        ["outcome_title"] = OutcomeNames.Title(answer.Outcome),
        ["truncated"] = answer.Truncated,
        ["truncate_reason"] = answer.TruncateReason,
        ["text"] = answer.Text,
        ["warnings"] = answer.Warnings,
        ["part"] = answer.Part,
        ["parts"] = answer.Parts,
        ["next_part"] = answer.NextPart,
        ["final_outcome"] = answer.FinalOutcome is { } fin ? OutcomeNames.Id(fin) : null,
        ["contour"] = answer.Contour,
        ["tooling_version"] = answer.ToolingVersion,
        ["child_exit"] = answer.ChildExit,
        ["error"] = answer.Error,
        ["details"] = answer.Details?.DeepClone(),
    };

    private static JsonArray ToolList(Contract contract)
    {
        var list = new JsonArray();
        foreach (var t in contract.Tools)
        {
            var props = new JsonObject();
            var required = new JsonArray();

            foreach (var a in contract.CommonArgs.Concat(t.Args))
            {
                var schema = new JsonObject { ["type"] = JsonType(a.Type) };
                if (a.Type == "list<string>") schema["items"] = new JsonObject { ["type"] = "string" };
                if (!string.IsNullOrEmpty(a.Description)) schema["description"] = a.Description;
                if (a.Enum is { Count: > 0 })
                    schema["enum"] = new JsonArray(a.Enum.Select(v => (JsonNode)JsonValue.Create(v)!).ToArray());
                props[a.Name] = schema;
                if (a.Required) required.Add(a.Name);
            }

            list.Add(new JsonObject
            {
                ["name"] = t.Name,
                ["description"] = (string.IsNullOrEmpty(t.Description) ? t.Title : t.Title + ". " + t.Description)
                                  + (t.ServiceWrites is { Count: > 0 } sw ? " Служебные записи: " + string.Join(", ", sw) + "." : "")
                                  // «обязателен в варианте» схема MCP не выражает: в required остаётся только обязательное на уровне вызова,
                                  // а перечень вариантов строится из договора и идёт в описании
                                  + (t.HasVariants ? "\n" + string.Join("\n", Contract.VariantLines(t)) : ""),
                ["inputSchema"] = new JsonObject
                {
                    ["type"] = "object",
                    ["properties"] = props,
                    ["required"] = required,
                    // Незнакомый аргумент стена отвергает отказом (ToolRunner.CallAsync); схема говорит о том же заранее
                    ["additionalProperties"] = false,
                },
            });
        }
        return list;
    }

    private static string JsonType(string t) => t switch
    {
        "int" => "integer",
        "bool" => "boolean",
        "list<string>" => "array",
        _ => "string",
    };

    private static JsonObject Result(JsonNode? id, JsonObject result) => new()
    {
        ["jsonrpc"] = "2.0",
        ["id"] = id?.DeepClone(),
        ["result"] = result,
    };

    private static JsonObject Error(JsonNode? id, int code, string message) => new()
    {
        ["jsonrpc"] = "2.0",
        ["id"] = id?.DeepClone(),
        ["error"] = new JsonObject { ["code"] = code, ["message"] = message },
    };

    private static Task WriteAsync(StreamWriter w, JsonObject o) =>
        w.WriteLineAsync(o.ToJsonString(Json));

    // ────────────────────────────────── поиск своих файлов

    private static string? ProbeContract() => ProbeUp(Path.Combine("contract", "gordi-contract.json"));

    private static string? ProbeContours()
    {
        // Боевой манифест ищем, образец — НЕТ: образец указывает на живое хранилище,
        // и принять его за боевой значило бы судить не тот контур молча.
        return ProbeUp(Path.Combine("contour", "gordi-contours.json"));
    }

    private static string? ProbeUp(string tail)
    {
        var dir = AppContext.BaseDirectory;
        for (var i = 0; i < 8 && dir is not null; i++)
        {
            var candidate = Path.Combine(dir, tail);
            if (File.Exists(candidate)) return candidate;
            dir = Path.GetDirectoryName(dir.TrimEnd(Path.DirectorySeparatorChar));
        }
        return null;
    }

    private static string? Take(List<string> args, string name)
    {
        var i = args.IndexOf(name);
        if (i < 0 || i + 1 >= args.Count) return null;
        var value = args[i + 1];
        args.RemoveRange(i, 2);
        return value;
    }

    private static bool TakeSwitch(List<string> args, string name)
    {
        var i = args.IndexOf(name);
        if (i < 0) return false;
        args.RemoveAt(i);
        return true;
    }
}
