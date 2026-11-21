using System.Diagnostics;
using System.Text;
using System.Text.Json.Nodes;

namespace GordiWall;

/// <summary>
/// Ответ стены. Поля обязательны все, кроме error: роль не обязана догадываться,
/// полон ли текст и кто её судит.
/// Предупреждения тела (поток ошибок) идут ОТДЕЛЬНЫМ полем и к тексту не приклеиваются.
/// Длинный вывод выдаётся частями: part / parts / next_part; у ответа не по частям part=1, parts=1.
/// Details — необязательные поля, которые объявляет сам вызов (у contour_info это блоки manifest и judge); у остальных вызовов null.
/// </summary>
public sealed record Answer(
    Outcome Outcome,
    bool Truncated,
    string? TruncateReason,
    string Text,
    string Contour,
    string ToolingVersion,
    int? ChildExit,
    string? Error,
    string Warnings = "",
    int Part = 1,
    int Parts = 1,
    string? NextPart = null,
    Outcome? FinalOutcome = null,
    string? NextHint = null,
    JsonObject? Details = null)
{
    /// <summary>Строка, которой кончается блок предупреждений: по ней отделяют предупреждения от текста.</summary>
    public const string WarningsEnd = "── конец предупреждений ──";

    public static Answer Refuse(string why, string contour = "", string toolingVersion = "") =>
        new(Outcome.Refused, false, null, "", contour, toolingVersion, null, why);

    /// <summary>Шапка одной строкой — то, что роль читает первым.</summary>
    public string Header()
    {
        var sb = new StringBuilder();
        sb.Append("исход: ").Append(OutcomeNames.Title(Outcome));
        if (Parts > 1) sb.Append(" · часть ").Append(Part).Append(" из ").Append(Parts);
        if (FinalOutcome is { } fin) sb.Append(" · итоговый исход тела: ").Append(OutcomeNames.Title(fin));
        sb.Append(" · усечено: ").Append(Truncated ? "ДА — " + (TruncateReason ?? "без причины") : "нет");
        if (!string.IsNullOrEmpty(Contour)) sb.Append(" · контур: ").Append(Contour);
        if (!string.IsNullOrEmpty(ToolingVersion)) sb.Append(" · версия тулинга: ").Append(ToolingVersion);
        if (ChildExit is { } code) sb.Append(" · код тела: ").Append(code).Append(" (справочно, не договор)");
        if (NextPart is not null && NextHint is not null)
        {
            sb.AppendLine();
            sb.Append("ответ отдан НЕ целиком, продолжение: ").Append(NextHint);
        }
        return sb.ToString();
    }

    public string ForRole()
    {
        var sb = new StringBuilder();
        sb.AppendLine(Header());
        if (!string.IsNullOrEmpty(Error)) sb.Append("причина: ").AppendLine(Error);
        if (!string.IsNullOrEmpty(Warnings))
        {
            sb.AppendLine("── предупреждения тела (поток ошибок; к ответу НЕ относятся) ──");
            sb.AppendLine(Warnings.TrimEnd('\r', '\n'));
            sb.AppendLine(WarningsEnd);
        }
        if (!string.IsNullOrEmpty(Text)) sb.AppendLine().Append(Text);
        return sb.ToString();
    }
}

public sealed class ToolRunner(Contract contract, Manifest manifest, bool readOnly)
{
    private readonly Contract _contract = contract;
    private readonly Manifest _manifest = manifest;
    private readonly bool _readOnly = readOnly;

    // Версия тулинга спрашивается У ХРАНИЛИЩА КОНТУРА на КАЖДЫЙ вызов, в памяти службы не держится: запись установки меняется
    // за время жизни службы, а запомненное значение расходилось бы с записью молча (карточка 821). Манифест версию как истину
    // не держит: установщик пишет её в таблицу meta, и второй список версий расходился бы с первым.

    /// <summary>Имя общего аргумента «метка продолжения». Объявлен в договоре; имя нужно и коду, как имя вызова contour_info.</summary>
    public const string NextPartArg = "next_part";

    public async Task<Answer> CallAsync(string toolName, IReadOnlyDictionary<string, object?> given, CancellationToken ct)
    {
        var tool = _contract.Find(toolName);
        if (tool is null)
            return Answer.Refuse($"вызова «{toolName}» в договоре нет. Есть: {string.Join(" · ", _contract.Tools.Select(t => t.Name))}");

        // ── общие аргументы и аргументы вызова проверяются ОДНИМ методом по одним полям договора (required, enum).
        //    Какой из общих аргументов выбирает контур, говорит договор (selects=contour), а не код.
        foreach (var a in _contract.CommonArgs)
        {
            var refusal = CheckArg(a, given);
            if (refusal is not null) return Answer.Refuse(refusal);
        }

        var contourId = Val(given, _contract.ContourArgName)!;
        var contour = _manifest.Find(contourId);
        if (contour is null)
            return Answer.Refuse($"контур «{contourId}» в манифесте не объявлен (манифест: {_manifest.Path}). "
                                 + $"Известные: {_manifest.KnownIds()}", contourId);

        // Незнакомый аргумент — отказ, а не молчаливое «не поедет в тело»: опечатка вроде limt вместо limit иначе
        // давала бы ответ на ДРУГОЙ вопрос и выглядела бы как «прошло». Место одно — для службы и для режима run.
        var extra = given.Keys.Where(k => !IsDeclared(tool, k)).OrderBy(k => k, StringComparer.Ordinal).ToList();
        if (extra.Count > 0)
            return Answer.Refuse(
                $"в вызове «{tool.Name}» есть аргумент, которого договор не объявляет: «{string.Join("», «", extra)}». "
                + $"Объявлены общие: {string.Join(", ", _contract.CommonArgs.Select(a => a.Name))}; "
                + $"вызова: {(tool.Args.Count == 0 ? "нет" : string.Join(", ", tool.Args.Select(a => a.Name)))}. "
                + "Тело не запускалось: молча выбросить лишний аргумент значило бы ответить на другой вопрос.",
                contour.Id, ToolingVersion(contour));

        if (_readOnly && !string.Equals(tool.Mode, "read", StringComparison.Ordinal))
            return Answer.Refuse($"вызов «{tool.Name}» пишет, а стена поднята в режиме только-чтение. "
                                 + "Запись мимо службы отвергнута намеренно: иначе обход стены стал бы обычной дорогой.",
                                 contour.Id, ToolingVersion(contour));

        // Вызов с next_part тело НЕ запускает: отдаёт следующую часть уже сохранённого ответа.
        // Аргументы вызова при этом не требуются — они были в первом вызове.
        var nextLabel = Val(given, NextPartArg);
        if (!string.IsNullOrWhiteSpace(nextLabel))
            return ContinuePart(tool, contour, nextLabel);

        // Вариант вызова: выбирается значением аргумента выбора или умолчанием договора. Новое место проверок —
        // после next_part (часть сохранённого ответа вариантов не знает) и ДО обязательности аргументов.
        var exec = tool.Exec;
        if (tool.HasVariants)
        {
            var (picked, variantRefusal) = PickVariant(tool, given, contour);
            if (variantRefusal is not null) return variantRefusal;
            exec = picked!.Exec;
        }

        foreach (var a in tool.Args)
        {
            var refusal = CheckArg(a, given);
            if (refusal is not null) return Answer.Refuse(refusal, contour.Id, ToolingVersion(contour));
        }

        if (exec!.Kind == "builtin")
            return Builtin(exec, contour);

        return await RunPythonAsync(tool, exec, contour, given, ct);
    }

    /// <summary>Аргумент передан: есть в вызове и не пуст. Пустая строка — как «не передан».</summary>
    private static bool Passed(IReadOnlyDictionary<string, object?> given, string name) =>
        !string.IsNullOrWhiteSpace(Val(given, name));

    /// <summary>
    /// Выбор варианта вызова и проверки, которые зависят от него: аргумент чужого варианта и не переданный обязательный
    /// аргумент выбранного — отказ ДО запуска тела. Значение выбора вне перечня или пропущенное без умолчания даёт прежний
    /// отказ по обязательности и enum (его формулирует CheckArg).
    /// </summary>
    private (ToolVariant? Variant, Answer? Refusal) PickVariant(ToolDef tool, IReadOnlyDictionary<string, object?> given, ContourInfo contour)
    {
        var selector = tool.Args.First(a => a.Name == tool.VariantBy);
        var key = Val(given, selector.Name);
        if (string.IsNullOrWhiteSpace(key)) key = tool.DefaultVariant;
        var variant = tool.FindVariant(key);
        if (variant is null)
        {
            var why = CheckArg(selector, given)
                      ?? $"у аргумента «{selector.Name}» нет варианта «{key}»: {string.Join(" · ", selector.Enum ?? [])}";
            return (null, Answer.Refuse(why, contour.Id, ToolingVersion(contour)));
        }

        var own = tool.ArgsOf(variant);
        foreach (var a in tool.Args)
        {
            if (a.Name == selector.Name || !Passed(given, a.Name) || own.Contains(a.Name)) continue;
            var owners = tool.VariantList.Where(v => tool.ArgsOf(v).Contains(a.Name)).Select(v => selector.Name + "=" + v.Key);
            return (null, Answer.Refuse(
                $"аргумент «{a.Name}» не относится к варианту «{selector.Name}={variant.Key}» вызова «{tool.Name}»; "
                + $"он относится к вариантам: {string.Join(", ", owners)}. "
                + "Тело не запускалось: молча выбросить аргумент чужого варианта значило бы ответить на другой вопрос.",
                contour.Id, ToolingVersion(contour)));
        }

        foreach (var r in variant.Requires)
        {
            if (Passed(given, r)) continue;
            var decl = tool.Args.FirstOrDefault(a => a.Name == r);
            return (null, Answer.Refuse(
                $"в варианте «{selector.Name}={variant.Key}» вызова «{tool.Name}» не передан обязательный аргумент «{r}»"
                + (string.IsNullOrEmpty(decl?.Description) ? "" : ": " + decl!.Description)
                + ". Тело не запускалось.",
                contour.Id, ToolingVersion(contour)));
        }

        return (variant, null);
    }

    /// <summary>Аргумент объявлен в договоре: среди общих или среди аргументов вызова.</summary>
    private bool IsDeclared(ToolDef tool, string name) =>
        _contract.CommonArgs.Any(a => string.Equals(a.Name, name, StringComparison.Ordinal))
        || tool.Args.Any(a => string.Equals(a.Name, name, StringComparison.Ordinal));

    /// <summary>
    /// Проверка одного аргумента по договору: обязательность и перечень значений. Единственное место,
    /// где это делается, — и для общих аргументов, и для аргументов вызова. Отказ — текст или null.
    /// </summary>
    private string? CheckArg(ToolArg a, IReadOnlyDictionary<string, object?> given)
    {
        var v = Val(given, a.Name);
        var hint = string.Equals(a.Name, _contract.ContourArgName, StringComparison.Ordinal)
            ? $" Известные контуры: {_manifest.KnownIds()}"
            : "";
        if (a.Required && string.IsNullOrWhiteSpace(v))
            return $"не передан обязательный аргумент «{a.Name}»: {a.Description ?? a.Title()}{hint}";
        if (a.Enum is { Count: > 0 } && !string.IsNullOrWhiteSpace(v) && !a.Enum.Contains(v))
            return $"у аргумента «{a.Name}» значение «{v}» вне перечня: {string.Join(" · ", a.Enum)}";
        return null;
    }

    // ── «кто меня судит» отвечает сама стена: это единственный вызов, который обязан отвечать и тогда, когда за стеной
    //    ничего не работает. Ответ строится из ПОЛЕЙ (значение · источник · состояние): текст — из тех же объектов,
    //    структура для CLI и MCP — из них же. Исход всегда «прошло»: «нечем проверить» говорит поле, а не вызов.
    private Answer Builtin(ToolExec exec, ContourInfo contour)
    {
        if (exec.Builtin != "contour_info")
            return Answer.Refuse($"встроенного ответчика «{exec.Builtin}» нет", contour.Id, ToolingVersion(contour));

        Func<string, int, StorageResult> ask = (sql, limit) => AskStorage(contour, sql, limit);
        var install = InstallRecord.Read(ask);
        var manifestFields = ContourReport.ManifestBlock(_manifest, contour, install);
        var judgeFields = ContourReport.JudgeBlock(_contract, RulesRecord.Read(ask));
        var notes = ContourReport.Notes(contour);
        var text = ContourReport.Text(_contract, _manifest, contour, _readOnly, manifestFields, judgeFields, notes);

        // оба поля версии (общее tooling_version и manifest.tooling.version) — из ОДНОГО чтения записи установки выше
        return new Answer(Outcome.Passed, false, null, text, contour.Id, install.Version, null, null,
                          Details: ContourReport.Details(manifestFields, judgeFields, notes));
    }

    private async Task<Answer> RunPythonAsync(ToolDef tool, ToolExec exec, ContourInfo contour,
                                              IReadOnlyDictionary<string, object?> given, CancellationToken ct)
    {
        if (exec.Dir is null || !contour.ToolDirs.TryGetValue(exec.Dir, out var dir))
            return Answer.Refuse($"у контура «{contour.Id}» не объявлен каталог инструментов «{exec.Dir}»",
                                 contour.Id, ToolingVersion(contour));

        var script = Path.Combine(dir, exec.Script!);
        if (!File.Exists(script))
            return new Answer(Outcome.NotStarted, false, null, "", contour.Id, ToolingVersion(contour), null,
                              $"тела инструмента нет на месте: {script}. Это НЕ «нечего проверять» — установка неполна.");

        var temps = new List<string>();
        try
        {
            var argv = BuildArgv(exec, contour, given, temps);

            var psi = new ProcessStartInfo
            {
                FileName = _manifest.Python,
                WorkingDirectory = dir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                RedirectStandardInput = true,
                UseShellExecute = false,
                StandardOutputEncoding = new UTF8Encoding(false),
                StandardErrorEncoding = new UTF8Encoding(false),
            };
            psi.ArgumentList.Add(script);
            foreach (var a in argv) psi.ArgumentList.Add(a);

            // ⚡ Среда ребёнка ЧИСТАЯ от переменных контура: подмена MEZO_* не должна менять
            //    поведение вызова — контур приходит ТОЛЬКО аргументом (встречный случай ④ карточки 779)
            foreach (var key in psi.Environment.Keys.Where(k => k.StartsWith("MEZO_", StringComparison.OrdinalIgnoreCase)).ToList())
                psi.Environment.Remove(key);
            psi.Environment["PYTHONUTF8"] = "1";
            psi.Environment["PYTHONIOENCODING"] = "utf-8";
            psi.Environment["GORDI_CONTOUR"] = contour.Id;     // для сообщений тела, не для выбора пути
            psi.Environment["GORDI_ACTOR_WALL"] = "1";
            // Объявленная передача значения аргумента в среду тела (exec.env договора): ПОСЛЕ стирания MEZO_*, только непустое.
            // Среда самой службы к телу не протекает: ставится лишь то, что договор назвал, и значение берётся из вызова.
            foreach (var (envName, argName) in exec.EnvMap)
                if (Val(given, argName) is { } envValue && !string.IsNullOrWhiteSpace(envValue))
                    psi.Environment[envName] = envValue;

            using var p = Process.Start(psi);
            if (p is null)
                return new Answer(Outcome.NotStarted, false, null, "", contour.Id, ToolingVersion(contour), null,
                                  "процесс тела инструмента не запустился");

            p.StandardInput.Close();
            var stdoutTask = p.StandardOutput.ReadToEndAsync(ct);
            var stderrTask = p.StandardError.ReadToEndAsync(ct);

            using var limit = CancellationTokenSource.CreateLinkedTokenSource(ct);
            limit.CancelAfter(TimeSpan.FromSeconds(_manifest.TimeoutSeconds));

            try
            {
                await p.WaitForExitAsync(limit.Token);
            }
            catch (OperationCanceledException) when (!ct.IsCancellationRequested)
            {
                try { p.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
                return new Answer(Outcome.CannotVerify, true, $"предел времени {_manifest.TimeoutSeconds} с",
                                  "", contour.Id, ToolingVersion(contour), null,
                                  "тело инструмента не ответило в срок и остановлено. Ответа по предмету НЕТ — "
                                  + "это явное незнание, а не «всё хорошо».");
            }

            var stdout = await stdoutTask;
            var stderr = await stderrTask;
            var exit = p.ExitCode;

            var outcome = Judge(exec, exit, stdout, stderr);
            string? error = outcome == Outcome.Passed ? null : ShortReason(outcome, stderr, stdout);

            // Поток ошибок — ОТДЕЛЬНОЕ поле. Отсечение допустимо только здесь, и оно названо.
            var maxChars = _manifest.MaxOutputChars;
            var (warnings, warnCut, warnReason) = FitWarnings(stderr, maxChars);

            if (stdout.Length <= maxChars)
                return new Answer(outcome, warnCut, warnReason, stdout, contour.Id, ToolingVersion(contour), exit, error, warnings);

            // Вывод длиннее предела не режется, а делится на части; весь ответ ложится на диск.
            var parts = PartSpool.Split(stdout, maxChars);
            var entry = new SpoolEntry
            {
                Tool = tool.Name,
                Contour = contour.Id,
                ToolingVersion = ToolingVersion(contour),
                FinalOutcome = OutcomeNames.Id(outcome),
                ChildExit = exit,
                Error = error,
                Warnings = warnings,
                Truncated = warnCut,
                TruncateReason = warnReason,
                Parts = parts,
            };
            string id;
            try
            {
                id = PartSpool.Save(entry);
            }
            catch (Exception e) when (e is IOException or UnauthorizedAccessException)
            {
                return new Answer(Outcome.CannotVerify, false, null, "", contour.Id, ToolingVersion(contour), exit,
                                  $"ответ тела длиннее предела ({stdout.Length} знаков при пределе {maxChars}), а сохранить его части на диск не удалось: {e.Message}. "
                                  + "Отдать часть без остальных стена не вправе: молча обрезанный ответ ввёл бы в заблуждение.",
                                  warnings);
            }

            return PartAnswer(entry, id, 1, tool.Name);
        }
        catch (System.ComponentModel.Win32Exception e)
        {
            return new Answer(Outcome.NotStarted, false, null, "", contour.Id, ToolingVersion(contour), null,
                              $"запуск не состоялся: {e.Message} (язык тела: {_manifest.Python})");
        }
        finally
        {
            foreach (var f in temps)
                try { File.Delete(f); } catch (IOException) { }
        }
    }

    /// <summary>
    /// Выбор исхода. Код выхода — ОДИН из признаков, а не договор:
    /// у тела исходов больше, чем значений у кода.
    /// </summary>
    private static Outcome Judge(ToolExec exec, int exit, string stdout, string stderr)
    {
        if (exit == 0) return Outcome.Passed;

        // «Не запустилось» — только когда тело и впрямь не начало работу: интерпретатор сказал, что не открывает
        // файл (код 2, stdout пуст, первая непустая строка потока ошибок — его сообщение). Фраза «No such file or
        // directory» где-либо в выводе — это слова отработавшего тела, а не отказ запуска.
        if (exit == 2 && string.IsNullOrWhiteSpace(stdout) && InterpreterCannotOpen(stderr))
            return Outcome.NotStarted;

        var all = stdout + "\n" + stderr;
        foreach (var mark in exec.MismatchWhen)
            if (all.Contains(mark, StringComparison.OrdinalIgnoreCase))
                return Outcome.Mismatch;

        // Тело запустилось и кончилось ненулевым кодом: это ОПРЕДЕЛЁННЫЙ ответ тела («нет такой роли», неверный ключ
        // подтверждения, сбой внутри): служба его получила и отдаёт как есть. «Не смог проверить» здесь не годится:
        // оно оставлено службе для случаев, когда ответа тела по предмету она НЕ получила (обрыв по времени, потеря частей).
        return Outcome.ToolFailed;
    }

    private static readonly System.Text.RegularExpressions.Regex InterpreterMessage =
        new(@"python[^\r\n]*: can't open file", System.Text.RegularExpressions.RegexOptions.IgnoreCase);

    /// <summary>Первая непустая строка потока ошибок — сообщение интерпретатора «…python…: can't open file …».</summary>
    private static bool InterpreterCannotOpen(string stderr)
    {
        var first = stderr.Split('\n').Select(l => l.Trim()).FirstOrDefault(l => l.Length > 0);
        return first is not null && InterpreterMessage.IsMatch(first);
    }

    /// <summary>
    /// Предупреждения тела укладываются в предел: если длиннее — начало и конец, между ними строка «вырезано N знаков».
    /// Это единственное место, где стена вправе отсечь, и отсечение названо признаком и причиной.
    /// </summary>
    private static (string Text, bool Cut, string? Reason) FitWarnings(string stderr, int maxChars)
    {
        var text = stderr.TrimEnd('\r', '\n');
        if (string.IsNullOrWhiteSpace(text)) return ("", false, null);
        if (text.Length <= maxChars) return (text, false, null);

        var keep = Math.Max(2, maxChars - 60);   // 60 знаков — запас под строку «вырезано N знаков»
        var head = keep / 2;
        var tail = keep - head;
        var cut = text.Length - head - tail;
        var fitted = text[..head] + $"\n… вырезано {cut} знаков …\n" + text[^tail..];
        return (fitted, true, $"предупреждения тела длиннее предела: предел знаков {maxChars} (было {text.Length}), вырезано {cut}");
    }

    /// <summary>Часть number из сохранённого ответа: все части, кроме последней, имеют исход «частично».</summary>
    private Answer PartAnswer(SpoolEntry entry, string id, int number, string toolName)
    {
        var total = entry.Parts.Count;
        var last = number == total;
        var final = OutcomeNames.Parse(entry.FinalOutcome) ?? Outcome.CannotVerify;
        var next = last ? null : PartSpool.MakeLabel(id, number + 1);
        // Предупреждения целиком идут в первой части и повторяются в последней.
        var warnings = number == 1 || last ? entry.Warnings : "";
        return new Answer(
            last ? final : Outcome.Partial,
            entry.Truncated,
            entry.TruncateReason,
            entry.Parts[number - 1],
            entry.Contour,
            entry.ToolingVersion,
            entry.ChildExit,
            last ? entry.Error : null,
            warnings,
            number,
            total,
            next,
            last ? null : final,
            next is null ? null : NextHint(toolName, entry.Contour, next));
    }

    /// <summary>Точная форма следующего вызова — для службы и для режима run.</summary>
    private string NextHint(string toolName, string contourId, string label)
    {
        var contourArg = _contract.ContourArgName;
        var runArg = "--" + NextPartArg.Replace('_', '-');
        return $"вызвать «{toolName}» с аргументами {contourArg}=\"{contourId}\" и {NextPartArg}=\"{label}\" "
               + $"(мимо службы: gordi-wall run {toolName} --{contourArg.Replace('_', '-')} {contourId} {runArg} {label})";
    }

    /// <summary>Отдаёт следующую часть сохранённого ответа. Метка привязана к вызову и контуру.</summary>
    private Answer ContinuePart(ToolDef tool, ContourInfo contour, string label)
    {
        if (!PartSpool.TryLoad(label, out var entry, out var number, out var why))
            return Answer.Refuse(why, contour.Id, ToolingVersion(contour));

        if (!string.Equals(entry!.Tool, tool.Name, StringComparison.Ordinal)
            || !string.Equals(entry.Contour, contour.Id, StringComparison.Ordinal))
            return Answer.Refuse($"метка продолжения «{label}» выдана для вызова «{entry.Tool}» на контуре «{entry.Contour}», "
                                 + $"а просят «{tool.Name}» на контуре «{contour.Id}». Чужую метку стена не принимает; тело не запускалось.",
                                 contour.Id, ToolingVersion(contour));

        var id = label.Trim().Split('.')[0];
        return PartAnswer(entry, id, number, tool.Name);
    }

    // Признаки ошибки, которыми инструменты контура начинают строку с причиной отказа.
    private static readonly string[] ReasonMarks = { "ERR", "🔴", "⛔", "❌", "ОТКАЗ" };

    /// <summary>
    /// Строка начинается с признака ошибки. Признак-слово («ERR», «ОТКАЗ») считается только ЦЕЛЫМ словом: за ним
    /// не буква и не цифра. Иначе сводка «ERRORS: 0» сошла бы за причину отказа (замечание COORD 2, карточка 791).
    /// </summary>
    private static bool StartsWithMark(string line)
    {
        foreach (var mark in ReasonMarks)
        {
            if (!line.StartsWith(mark, StringComparison.Ordinal)) continue;
            // у значка границы слова нет: он признак сам по себе
            if (!char.IsLetter(mark[0])) return true;
            if (line.Length == mark.Length || !char.IsLetterOrDigit(line[mark.Length])) return true;
        }
        return false;
    }

    /// <summary>
    /// ПОСЛЕДНЯЯ строка текста, начинающаяся с признака ошибки; нет такой — null. Последняя, а не первая: причину
    /// выхода тело говорит последней (сообщение выхода уходит в поток последним), а предупреждения с тем же
    /// признаком печатает раньше (замечание COORD 1, карточка 791).
    /// </summary>
    private static string? MarkedLine(string text) =>
        text.Split('\n').Select(l => l.Trim()).LastOrDefault(l => l.Length > 0 && StartsWithMark(l));

    /// <summary>
    /// Короткая причина отказа — ОДНА строка тела. Сперва ищется строка с признаком ошибки: в потоке ошибок,
    /// затем в stdout; берётся ПОСЛЕДНЯЯ такая. Признака нет ни в одном потоке — последняя непустая строка потока ошибок,
    /// а при пустом потоке ошибок — stdout: так кончаются разбор аргументов и необработанное исключение Python.
    /// Прежде бралась только последняя строка, и причиной становился хвост подсказки (находка COORD Н2, карточка 791).
    /// ⚠️ Граница: если тело ПОСЛЕ причины печатает ещё одну строку с признаком, причиной станет она.
    /// </summary>
    private static string ShortReason(Outcome outcome, string stderr, string stdout)
    {
        var src = !string.IsNullOrWhiteSpace(stderr) ? stderr : stdout;
        var line = MarkedLine(stderr) ?? MarkedLine(stdout)
                   ?? src.Split('\n').Select(l => l.Trim()).LastOrDefault(l => l.Length > 0) ?? "";
        if (line.Length > 400) line = line[..400] + "…";
        return outcome switch
        {
            Outcome.Mismatch => "состояние разошлось с ожидаемым, тело НЕ записано: " + line,
            Outcome.NotStarted => "тело инструмента не начало работу: " + line,
            _ => "тело отказало: " + line,
        };
    }

    private List<string> BuildArgv(ToolExec exec, ContourInfo contour,
                                   IReadOnlyDictionary<string, object?> given, List<string> temps)
    {
        var argv = new List<string>();

        // ── «pre» идёт ДО подкоманды: у инструмента карточек --db объявлен у корневого разбора
        foreach (var w in exec.Pre)
            argv.Add(w.Replace("{db}", contour.Storage, StringComparison.Ordinal));

        argv.AddRange(exec.Sub);

        foreach (var m in exec.Args)
        {
            var raw = Val(given, m.Arg);
            var isTrue = IsTrue(given, m.Arg);

            switch (m.Form)
            {
                case "switch":
                    if (isTrue) argv.Add(m.Flag!);
                    break;

                case "positional":
                    if (!string.IsNullOrWhiteSpace(raw)) argv.Add(raw);
                    break;

                case "flag_csv":
                    if (!string.IsNullOrWhiteSpace(raw)) { argv.Add(m.Flag!); argv.Add(raw); }
                    break;

                case "flag_with_const":
                    if (!string.IsNullOrWhiteSpace(raw))
                    {
                        argv.Add(m.Flag!);
                        argv.Add(raw);
                        if (m.ConstAfter is { } c) argv.Add(c);
                    }
                    break;

                case "tempfile":
                    if (!string.IsNullOrEmpty(raw))
                    {
                        // Длинный текст идёт ФАЙЛОМ, не аргументом: так он не ломается ни кавычкой,
                        // ни переводом строки, ни пределом длины командной строки
                        var f = Path.Combine(Path.GetTempPath(), "gordi-wall-" + Guid.NewGuid().ToString("n") + ".md");
                        File.WriteAllText(f, raw, new UTF8Encoding(false));
                        temps.Add(f);
                        argv.Add(m.Flag!);
                        argv.Add(f);
                    }
                    break;

                default: // flag
                    if (!string.IsNullOrWhiteSpace(raw)) { argv.Add(m.Flag!); argv.Add(raw); }
                    break;
            }
        }

        return argv;
    }

    private static string? Val(IReadOnlyDictionary<string, object?> given, string name) =>
        given.TryGetValue(name, out var v) && v is not null ? Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture) : null;

    private static bool IsTrue(IReadOnlyDictionary<string, object?> given, string name)
    {
        if (!given.TryGetValue(name, out var v) || v is null) return false;
        if (v is bool b) return b;
        var s = Convert.ToString(v, System.Globalization.CultureInfo.InvariantCulture);
        return string.Equals(s, "true", StringComparison.OrdinalIgnoreCase) || s == "1";
    }

    // ──────────────────── версия тулинга: спрашиваем ХРАНИЛИЩЕ контура

    private string ToolingVersion(ContourInfo contour)
    {
        // Общее поле ответа «версия тулинга» берётся ТОЛЬКО из хранилища; нечем взять — пустая строка, а не догадка.
        // Одно чтение на вызов. Правило отбора значения одно с InstallRecord.Read (InstallRecord.PickVersion): ответ contour_info
        // берёт оба поля версии из ОДНОГО чтения, а этот метод — для остальных ответов.
        var asked = AskStorage(contour, "SELECT value FROM meta WHERE key='template_commit'", 10);
        return asked.Ok && asked.Rows.Count == 1 && asked.Rows[0].Length == 1 ? InstallRecord.PickVersion(asked.Rows[0][0]) : "";
    }

    /// <summary>
    /// Один читающий запрос к хранилищу контура через штатный читающий инструмент (db-q.py). Ничего не меняет.
    /// Ответ разбирается недоверчиво (StorageResult.Parse): число строк сверено с шапкой, слова об обрезании, пустой ответ
    /// и неразбираемая форма дают отказ с причиной, а не значение из усечённого чтения. limit — явный предел строк запроса.
    /// </summary>
    private StorageResult AskStorage(ContourInfo contour, string sql, int limit)
    {
        if (!contour.ToolDirs.TryGetValue("runtime", out var dir))
            return StorageResult.Fail("хранилище не ответило: у контура не объявлен каталог инструментов «runtime»");
        var script = Path.Combine(dir, "db-q.py");
        if (!File.Exists(script))
            return StorageResult.Fail($"хранилище не ответило: читающего инструмента db-q.py нет на месте: {script}");

        try
        {
            var psi = new ProcessStartInfo
            {
                FileName = _manifest.Python,
                WorkingDirectory = dir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                StandardOutputEncoding = new UTF8Encoding(false),
                StandardErrorEncoding = new UTF8Encoding(false),
            };
            psi.ArgumentList.Add(script);
            psi.ArgumentList.Add("--db");
            psi.ArgumentList.Add(contour.Storage);
            psi.ArgumentList.Add("--limit");
            psi.ArgumentList.Add(limit.ToString(System.Globalization.CultureInfo.InvariantCulture));
            psi.ArgumentList.Add(sql);
            foreach (var key in psi.Environment.Keys.Where(k => k.StartsWith("MEZO_", StringComparison.OrdinalIgnoreCase)).ToList())
                psi.Environment.Remove(key);
            psi.Environment["PYTHONUTF8"] = "1";
            psi.Environment["PYTHONIOENCODING"] = "utf-8";

            using var p = Process.Start(psi);
            if (p is null) return StorageResult.Fail("хранилище не ответило: процесс читающего инструмента не запустился");
            var stdoutTask = p.StandardOutput.ReadToEndAsync();
            var stderrTask = p.StandardError.ReadToEndAsync();
            if (!p.WaitForExit(20_000))
            {
                try { p.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
                return StorageResult.Fail("хранилище не ответило: читающий инструмент не уложился в 20 с и остановлен");
            }
            var stdout = stdoutTask.GetAwaiter().GetResult();
            var stderr = stderrTask.GetAwaiter().GetResult();
            if (p.ExitCode != 0)
            {
                var first = stderr.Split('\n').Select(l => l.Trim()).FirstOrDefault(l => l.Length > 0) ?? "(поток ошибок пуст)";
                if (first.Length > 160) first = first[..160] + "…";
                return StorageResult.Fail($"хранилище не ответило: читающий инструмент вернул код {p.ExitCode}: {first}");
            }
            return StorageResult.Parse(stdout, stderr);
        }
        catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException)
        {
            return StorageResult.Fail("хранилище не ответило: " + e.Message);
        }
    }
}

internal static class ToolArgText
{
    public static string Title(this ToolArg a) => a.Name;
}
