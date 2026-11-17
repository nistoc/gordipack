using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Nodes;

namespace GordiWall;

/// <summary>
/// Стена контура gordi. Три режима одной сборки — договор у них ОДИН файл:
///   serve  — служба MCP по стандартному вводу-выводу (роли зовут её как инструменты);
///   run    — однократный вызов мимо службы, ТОЛЬКО чтение (запас на случай, когда служба не поднялась);
///   tools  — перечень вызовов и отпечатки (ими судит приёмка).
/// </summary>
public static class Program
{
    private static readonly JsonSerializerOptions Json = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        WriteIndented = false,
    };

    public static async Task<int> Main(string[] rawArgs)
    {
        Console.OutputEncoding = new UTF8Encoding(false);
        var args = rawArgs.ToList();
        var mode = args.Count > 0 && !args[0].StartsWith('-') ? args[0] : "serve";
        if (args.Count > 0 && !args[0].StartsWith('-')) args.RemoveAt(0);

        var contractPath = Take(args, "--contract") ?? Environment.GetEnvironmentVariable("GORDI_CONTRACT") ?? ProbeContract();
        var contoursPath = Take(args, "--contours") ?? Environment.GetEnvironmentVariable("GORDI_CONTOURS") ?? ProbeContours();
        var readOnly = TakeSwitch(args, "--read-only") || mode == "run";

        if (contractPath is null)
        {
            await Console.Error.WriteLineAsync("отказ: файла договора нет. Укажите --contract <путь> или GORDI_CONTRACT. "
                + "Ожидался contract/gordi-contract.json рядом со сборкой или выше по дереву.");
            return 4;
        }

        Contract contract;
        try
        {
            contract = Contract.Load(contractPath);
        }
        catch (Exception e) when (e is IOException or JsonException or InvalidDataException)
        {
            await Console.Error.WriteLineAsync($"отказ: договор не читается ({contractPath}): {e.Message}");
            return 4;
        }

        if (mode == "tools")
            return await PrintToolsAsync(contract, contoursPath);

        if (contoursPath is null)
        {
            await Console.Error.WriteLineAsync("отказ: манифеста контуров нет. Укажите --contours <путь> или GORDI_CONTOURS. "
                + "Стена НАМЕРЕННО не угадывает контур по своему расположению: образец — contour/gordi-contours.example.json, "
                + "боевой файл кладёт установщик тулинга под именем contour/gordi-contours.json.");
            return 4;
        }

        Manifest manifest;
        try
        {
            manifest = Manifest.Load(contoursPath);
        }
        catch (Exception e) when (e is IOException or JsonException or InvalidDataException)
        {
            await Console.Error.WriteLineAsync($"отказ: манифест не читается ({contoursPath}): {e.Message}");
            return 4;
        }

        var runner = new ToolRunner(contract, manifest, readOnly);

        return mode switch
        {
            "serve" => await ServeAsync(contract, manifest, runner),
            "run" => await RunOnceAsync(contract, runner, args),
            _ => await UnknownModeAsync(mode),
        };
    }

    private static async Task<int> UnknownModeAsync(string mode)
    {
        await Console.Error.WriteLineAsync($"отказ: режима «{mode}» нет. Есть: serve · run · tools");
        return 4;
    }

    // ────────────────────────────────── перечень вызовов

    private static async Task<int> PrintToolsAsync(Contract contract, string? contoursPath)
    {
        var sb = new StringBuilder();
        sb.AppendLine($"договор ................ {contract.Path}");
        sb.AppendLine($"версия ................. {contract.Version} (этап {contract.Stage})");
        sb.AppendLine($"отпечаток договора ..... {contract.Fingerprint}");
        sb.AppendLine($"отпечаток перечня ...... {contract.ToolsFingerprint()}");
        sb.AppendLine($"манифест контуров ...... {contoursPath ?? "НЕ НАЗВАН"}");
        sb.AppendLine($"вызовов ................ {contract.Tools.Count}");
        sb.AppendLine();
        var commonNames = string.Join(" ", contract.CommonArgs.Select(a => a.Required ? a.Name : "[" + a.Name + "]"));
        foreach (var t in contract.Tools)
        {
            var mode = t.Mode == "write" ? "запись " : "чтение ";
            var argNames = t.Args.Count == 0 ? "—" : string.Join(" ", t.Args.Select(a => a.Required ? a.Name : "[" + a.Name + "]"));
            sb.AppendLine($"  {mode} {t.Name,-18} {commonNames} {argNames}");
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

    private static async Task<int> RunOnceAsync(Contract contract, ToolRunner runner, List<string> args)
    {
        if (args.Count == 0 || args[0].StartsWith('-'))
        {
            // Имя аргумента выбора контура — из договора, а не литерал: договор вправе его переименовать
            await Console.Error.WriteLineAsync("отказ: не назван вызов. Форма: gordi-wall run <вызов> --"
                + contract.ContourArgName.Replace('_', '-') + " <контур> [--аргумент значение]");
            return 4;
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
        await Console.Out.WriteAsync(answer.ForRole());
        // У ответа по частям текст печатается как есть: лишний перевод строки сломал бы точность склейки частей
        if (answer.Parts == 1 && !answer.ForRole().EndsWith('\n')) await Console.Out.WriteLineAsync();

        // Код выхода ПОВТОРЯЕТ типизированный исход, а не заменяет его: договор — в тексте
        return answer.Outcome switch
        {
            Outcome.Passed => 0,
            Outcome.Mismatch => 1,
            Outcome.NotStarted => 2,
            Outcome.CannotVerify => 3,
            Outcome.Partial => 5,       // ответ отдан частями: есть продолжение (аргумент next_part)
            Outcome.ToolFailed => 6,    // тело запустилось и отказало определённо (ненулевой код тела), причина — в error
            _ => 4,
        };
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

        var structured = new JsonObject
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
        };

        return Result(id, new JsonObject
        {
            ["content"] = new JsonArray(new JsonObject
            {
                ["type"] = "text",
                ["text"] = answer.ForRole(),
            }),
            ["structuredContent"] = structured,
            // isError НЕ равен «исход не passed»: расхождение и явное незнание — тоже честные ответы,
            // а не поломка вызова. Поломкой здесь считается только отказ договора.
            ["isError"] = answer.Outcome == Outcome.Refused,
        });
    }

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
