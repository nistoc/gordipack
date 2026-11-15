using System.Diagnostics;
using System.Text;

namespace GordiWall;

/// <summary>
/// Ответ стены. Поля обязательны все, кроме error: роль не обязана догадываться,
/// полон ли текст и кто её судит.
/// </summary>
public sealed record Answer(
    Outcome Outcome,
    bool Truncated,
    string? TruncateReason,
    string Text,
    string Contour,
    string ToolingVersion,
    int? ChildExit,
    string? Error)
{
    public static Answer Refuse(string why, string contour = "", string toolingVersion = "") =>
        new(Outcome.Refused, false, null, "", contour, toolingVersion, null, why);

    /// <summary>Шапка одной строкой — то, что роль читает первым.</summary>
    public string Header()
    {
        var sb = new StringBuilder();
        sb.Append("исход: ").Append(OutcomeNames.Title(Outcome));
        sb.Append(" · усечено: ").Append(Truncated ? "ДА — " + (TruncateReason ?? "без причины") : "нет");
        if (!string.IsNullOrEmpty(Contour)) sb.Append(" · контур: ").Append(Contour);
        if (!string.IsNullOrEmpty(ToolingVersion)) sb.Append(" · версия тулинга: ").Append(ToolingVersion);
        if (ChildExit is { } code) sb.Append(" · код тела: ").Append(code).Append(" (справочно, не договор)");
        return sb.ToString();
    }

    public string ForRole()
    {
        var sb = new StringBuilder();
        sb.AppendLine(Header());
        if (!string.IsNullOrEmpty(Error)) sb.Append("причина: ").AppendLine(Error);
        if (!string.IsNullOrEmpty(Text)) sb.AppendLine().Append(Text);
        return sb.ToString();
    }
}

public sealed class ToolRunner(Contract contract, Manifest manifest, bool readOnly)
{
    private readonly Contract _contract = contract;
    private readonly Manifest _manifest = manifest;
    private readonly bool _readOnly = readOnly;

    // Версия тулинга спрашивается У ХРАНИЛИЩА КОНТУРА один раз за жизнь службы.
    // Манифест её НЕ держит как истину: установщик пишет версию в таблицу meta,
    // и второй список версий расходился бы с первым молча.
    private readonly Dictionary<string, string> _versionCache = new(StringComparer.Ordinal);

    public async Task<Answer> CallAsync(string toolName, IReadOnlyDictionary<string, object?> given, CancellationToken ct)
    {
        var tool = _contract.Find(toolName);
        if (tool is null)
            return Answer.Refuse($"вызова «{toolName}» в договоре нет. Есть: {string.Join(" · ", _contract.Tools.Select(t => t.Name))}");

        // ── контур обязателен У КАЖДОГО вызова: стена не вычисляет его сама и не берёт из среды
        var contourId = Val(given, "contour");
        if (string.IsNullOrWhiteSpace(contourId))
            return Answer.Refuse("не передан обязательный аргумент «contour». Стена НЕ вычисляет контур от своего расположения "
                                 + $"и НЕ читает его из переменных среды. Известные контуры: {_manifest.KnownIds()}");

        var contour = _manifest.Find(contourId);
        if (contour is null)
            return Answer.Refuse($"контур «{contourId}» в манифесте не объявлен (манифест: {_manifest.Path}). "
                                 + $"Известные: {_manifest.KnownIds()}", contourId);

        if (_readOnly && !string.Equals(tool.Mode, "read", StringComparison.Ordinal))
            return Answer.Refuse($"вызов «{tool.Name}» пишет, а стена поднята в режиме только-чтение. "
                                 + "Запись мимо службы отвергнута намеренно: иначе обход стены стал бы обычной дорогой.",
                                 contour.Id, ToolingVersion(contour));

        // ── обязательные аргументы и перечни значений
        foreach (var a in tool.Args)
        {
            var v = Val(given, a.Name);
            if (a.Required && string.IsNullOrWhiteSpace(v))
                return Answer.Refuse($"не передан обязательный аргумент «{a.Name}»: {a.Description ?? a.Title()}",
                                     contour.Id, ToolingVersion(contour));
            if (a.Enum is { Count: > 0 } && !string.IsNullOrWhiteSpace(v) && !a.Enum.Contains(v))
                return Answer.Refuse($"у аргумента «{a.Name}» значение «{v}» вне перечня: {string.Join(" · ", a.Enum)}",
                                     contour.Id, ToolingVersion(contour));
        }

        if (tool.Exec.Kind == "builtin")
            return Builtin(tool, contour);

        return await RunPythonAsync(tool, contour, given, ct);
    }

    // ── «кто меня судит» отвечает сама стена: это единственный вызов, который обязан
    //    отвечать и тогда, когда за стеной ничего не работает
    private Answer Builtin(ToolDef tool, ContourInfo contour)
    {
        if (tool.Exec.Builtin != "contour_info")
            return Answer.Refuse($"встроенного ответчика «{tool.Exec.Builtin}» нет", contour.Id, ToolingVersion(contour));

        var sb = new StringBuilder();
        sb.AppendLine("── отвечает САМА стена (эта половина есть всегда, даже когда за стеной ничего не работает)");
        sb.AppendLine($"контур ................. {contour.Id} — {contour.Title}");
        sb.AppendLine($"хранилище .............. {contour.Storage}");
        foreach (var (key, dir) in contour.ToolDirs)
            sb.AppendLine($"каталог «{key}» ........ {dir}");
        sb.AppendLine($"договор ................ {_contract.Path}");
        sb.AppendLine($"версия договора ........ {_contract.Version} (этап {_contract.Stage})");
        sb.AppendLine($"отпечаток договора ..... {_contract.Fingerprint} (по содержимому файла)");
        sb.AppendLine($"вызовов в договоре ..... {_contract.Tools.Count}, отпечаток перечня {_contract.ToolsFingerprint()}");
        sb.AppendLine($"режим стены ............ {(_readOnly ? "только-чтение" : "чтение и запись")}");
        sb.AppendLine($"манифест контуров ...... {_manifest.Path}");

        // Вторая половина — из ХРАНИЛИЩА контура: там установщик и пишет версию.
        // Манифест её не держит намеренно: два списка версий расходятся молча.
        sb.AppendLine();
        const string sql = "SELECT key, value FROM meta WHERE key IN "
            + "('group_name','template_commit','template_source','template_recorded_at','template_checkout','md_phase') "
            + "UNION ALL SELECT 'template_files_count', count(*) FROM json_each((SELECT value FROM meta WHERE key='template_files_sha'))";
        if (AskStorage(contour, sql, out var meta))
        {
            sb.AppendLine("── из хранилища контура (запись установщика; это и есть источник о версии тулинга)");
            sb.Append(meta.TrimEnd());
            sb.AppendLine();
            sb.Append("⚖️ отпечатки установленных файлов считаются по СОДЕРЖИМОМУ (meta.template_files_sha), "
                      + "а не по именам: сверка по именам уже один раз показала совпадение там, где его не было (карточка 771)");
        }
        else
        {
            sb.AppendLine("── из хранилища контура: НЕ ОТВЕТИЛО");
            sb.Append("⚠️ версия тулинга и отпечатки установки НЕ ПРОЧИТАНЫ. Это «нечем проверить», а не «всё совпадает». "
                      + Or(contour.Tooling.Version, "Запасного поля в манифесте тоже нет"));
        }

        return new Answer(Outcome.Passed, false, null, sb.ToString(), contour.Id, ToolingVersion(contour), null, null);
    }

    private async Task<Answer> RunPythonAsync(ToolDef tool, ContourInfo contour,
                                              IReadOnlyDictionary<string, object?> given, CancellationToken ct)
    {
        if (tool.Exec.Dir is null || !contour.ToolDirs.TryGetValue(tool.Exec.Dir, out var dir))
            return Answer.Refuse($"у контура «{contour.Id}» не объявлен каталог инструментов «{tool.Exec.Dir}»",
                                 contour.Id, ToolingVersion(contour));

        var script = Path.Combine(dir, tool.Exec.Script!);
        if (!File.Exists(script))
            return new Answer(Outcome.NotStarted, false, null, "", contour.Id, ToolingVersion(contour), null,
                              $"тела инструмента нет на месте: {script}. Это НЕ «нечего проверять» — установка неполна.");

        var temps = new List<string>();
        try
        {
            var argv = BuildArgv(tool, contour, given, temps);

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

            var text = stdout;
            if (!string.IsNullOrWhiteSpace(stderr))
                text = string.IsNullOrEmpty(text) ? stderr : text + "\n--- поток ошибок тела ---\n" + stderr;

            var truncated = false;
            string? reason = null;
            if (text.Length > _manifest.MaxOutputChars)
            {
                truncated = true;
                reason = $"предел знаков {_manifest.MaxOutputChars} (было {text.Length})";
                text = text[.._manifest.MaxOutputChars];
            }

            var outcome = Judge(tool, exit, stdout, stderr);
            string? error = outcome == Outcome.Passed ? null : ShortReason(outcome, stderr, stdout);

            return new Answer(outcome, truncated, reason, text, contour.Id, ToolingVersion(contour), exit, error);
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
    private static Outcome Judge(ToolDef tool, int exit, string stdout, string stderr)
    {
        if (exit == 0) return Outcome.Passed;

        var all = stdout + "\n" + stderr;
        if (all.Contains("can't open file", StringComparison.OrdinalIgnoreCase)
            || all.Contains("No such file or directory", StringComparison.OrdinalIgnoreCase))
            return Outcome.NotStarted;

        foreach (var mark in tool.Exec.MismatchWhen)
            if (all.Contains(mark, StringComparison.OrdinalIgnoreCase))
                return Outcome.Mismatch;

        // Тело запустилось и отказало по своей причине: ответа по предмету нет.
        return Outcome.CannotVerify;
    }

    private static string ShortReason(Outcome outcome, string stderr, string stdout)
    {
        var src = !string.IsNullOrWhiteSpace(stderr) ? stderr : stdout;
        var line = src.Split('\n', StringSplitOptions.RemoveEmptyEntries).LastOrDefault()?.Trim() ?? "";
        if (line.Length > 400) line = line[..400] + "…";
        return outcome switch
        {
            Outcome.Mismatch => "состояние разошлось с ожидаемым, тело НЕ записано: " + line,
            Outcome.NotStarted => "тело инструмента не начало работу: " + line,
            _ => "тело отказало: " + line,
        };
    }

    private List<string> BuildArgv(ToolDef tool, ContourInfo contour,
                                   IReadOnlyDictionary<string, object?> given, List<string> temps)
    {
        var argv = new List<string>();

        // ── «pre» идёт ДО подкоманды: у инструмента карточек --db объявлен у корневого разбора
        foreach (var w in tool.Exec.Pre)
            argv.Add(w.Replace("{db}", contour.Storage, StringComparison.Ordinal));

        argv.AddRange(tool.Exec.Sub);

        foreach (var m in tool.Exec.Args)
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

    private static string Or(string value, string whenEmpty) => string.IsNullOrWhiteSpace(value) ? whenEmpty : value;

    // ──────────────────── версия тулинга: спрашиваем ХРАНИЛИЩЕ контура

    private string ToolingVersion(ContourInfo contour)
    {
        if (_versionCache.TryGetValue(contour.Id, out var cached)) return cached;

        var value = "";
        if (AskStorage(contour, "SELECT value FROM meta WHERE key='template_commit'", out var text))
        {
            // Вывод читающего инструмента: шапка, имя столбца, значения. Берём последнюю непустую строку.
            var last = text.Split('\n', StringSplitOptions.RemoveEmptyEntries).LastOrDefault()?.Trim() ?? "";
            if (last.Length is > 0 and <= 80 && !last.StartsWith("──", StringComparison.Ordinal) && last != "value")
                value = last;
        }

        if (value.Length == 0)
            // Не выдумываем: пусто — значит хранилище не ответило, а запасное поле манифеста необязательно
            value = string.IsNullOrWhiteSpace(contour.Tooling.Version) ? "" : contour.Tooling.Version + " (из манифеста, не из хранилища)";

        _versionCache[contour.Id] = value;
        return value;
    }

    /// <summary>Один читающий запрос к хранилищу контура через штатный читающий инструмент. Ничего не меняет.</summary>
    private bool AskStorage(ContourInfo contour, string sql, out string text)
    {
        text = "";
        if (!contour.ToolDirs.TryGetValue("runtime", out var dir)) return false;
        var script = Path.Combine(dir, "db-q.py");
        if (!File.Exists(script)) return false;

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
            psi.ArgumentList.Add(sql);
            foreach (var key in psi.Environment.Keys.Where(k => k.StartsWith("MEZO_", StringComparison.OrdinalIgnoreCase)).ToList())
                psi.Environment.Remove(key);
            psi.Environment["PYTHONUTF8"] = "1";
            psi.Environment["PYTHONIOENCODING"] = "utf-8";

            using var p = Process.Start(psi);
            if (p is null) return false;
            var stdout = p.StandardOutput.ReadToEnd();
            var stderr = p.StandardError.ReadToEnd();
            if (!p.WaitForExit(20_000))
            {
                try { p.Kill(entireProcessTree: true); } catch (InvalidOperationException) { }
                return false;
            }
            if (p.ExitCode != 0) { text = stderr; return false; }
            text = stdout;
            return true;
        }
        catch (Exception e) when (e is System.ComponentModel.Win32Exception or IOException)
        {
            return false;
        }
    }
}

internal static class ToolArgText
{
    public static string Title(this ToolArg a) => a.Name;
}
