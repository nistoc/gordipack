using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Text.RegularExpressions;

namespace GordiWall;

/// <summary>
/// Одно поле ответа contour_info: значение, источник словами, состояние. Состояний два: «заполнено» (filled) и
/// «нечем проверить» (cannot_verify). У второго значения НЕТ (null), причина названа; у первого причины нет.
/// Пустая строка под видом заполненного поля не выдаётся: нечем заполнить — состояние «нечем проверить».
/// </summary>
public sealed record Field(string Path, string Label, object? Value, string Source, string State, string? Reason)
{
    public const string FilledState = "filled";
    public const string CannotVerifyState = "cannot_verify";

    public static Field Fill(string path, string label, object value, string source) =>
        new(path, label, value, source, FilledState, null);

    public static Field Unknown(string path, string label, string source, string reason) =>
        new(path, label, null, source, CannotVerifyState, reason);

    public bool IsFilled => string.Equals(State, FilledState, StringComparison.Ordinal);

    /// <summary>Поле в ответе: ровно четыре ключа — value, source, state, reason.</summary>
    public JsonObject ToJson() => new()
    {
        ["value"] = ValueNode(),
        ["source"] = Source,
        ["state"] = State,
        ["reason"] = Reason,
    };

    private JsonNode? ValueNode() => Value switch
    {
        null => null,
        long l => JsonValue.Create(l),
        int i => JsonValue.Create(i),
        _ => JsonValue.Create(Convert.ToString(Value, CultureInfo.InvariantCulture)),
    };

    /// <summary>Строка текста ответа: тот же объект поля, а не параллельный код — значение, источник, состояние.</summary>
    public string Line()
    {
        var dots = new string('.', Math.Max(2, 26 - Label.Length));
        return IsFilled
            ? $"{Label} {dots} {Convert.ToString(Value, CultureInfo.InvariantCulture)} · источник: {Source} · состояние: заполнено"
            : $"{Label} {dots} нечем проверить: {Reason} · источник: {Source} · состояние: нечем проверить";
    }
}

/// <summary>Кусок записи, прочитанный из хранилища: значение либо причина, по которой его нет.</summary>
public sealed record Piece(object? Value, string? Reason)
{
    public static Piece Of(object value) => new(value, null);

    public static Piece Fail(string reason) => new(null, reason);

    public Field ToField(string path, string label, string source) =>
        Reason is null ? Field.Fill(path, label, Value!, source) : Field.Unknown(path, label, source, Reason!);
}

/// <summary>
/// Ответ читающего инструмента хранилища (db-q.py), разобранный НЕДОВЕРЧИВО: строки значений сверены с числом
/// в строке-шапке; слова об обрезании, пустой ответ и неразбираемая форма — отказ с причиной, а не догадка.
/// </summary>
public sealed record StorageResult(bool Ok, IReadOnlyList<string[]> Rows, string Reason)
{
    /// <summary>Так читающий инструмент печатает NULL.</summary>
    public const string NullMark = "∅";

    private static readonly Regex CountLine = new(@"^──\s*строк:\s*(\d+)\b", RegexOptions.Compiled);

    public static StorageResult Fail(string reason) => new(false, [], reason);

    public static StorageResult Parse(string stdout, string stderr)
    {
        var lines = stdout.Replace("\r\n", "\n").Split('\n').ToList();
        if (lines.Count > 0 && lines[^1].Length == 0) lines.RemoveAt(lines.Count - 1);

        // Число строк называет читающий инструмент: в потоке ошибок (так печатает нынешний) или в выводе (так могла печатать старая копия)
        int? declared = null;
        foreach (var l in stderr.Replace("\r\n", "\n").Split('\n'))
            if (CountLine.Match(l.Trim()) is { Success: true } m) declared = int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture);
        for (var i = lines.Count - 1; i >= 0; i--)
            if (CountLine.Match(lines[i].Trim()) is { Success: true } m)
            {
                declared = int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture);
                lines.RemoveAt(i);
            }

        var cut = stderr.Replace("\r\n", "\n").Split('\n')
            .FirstOrDefault(l => l.Contains("ЕСТЬ ЕЩЁ", StringComparison.Ordinal) || l.Contains("обреза", StringComparison.OrdinalIgnoreCase));
        if (cut is not null)
            return Fail("ответ читающего инструмента прочитан не целиком: он сам назвал обрезание («" + Short(cut) + "»)");

        if (lines.Count == 0)
            return Fail("ответ читающего инструмента пуст: нет даже строки имён столбцов");
        if (declared is null)
            return Fail("полноту ответа проверить нечем: в выводе читающего инструмента нет строки с числом строк (установленная копия db-q.py старше?)");

        var header = lines[0].Split('\t');
        var rows = new List<string[]>();
        foreach (var l in lines.Skip(1))
        {
            var cells = l.Split('\t', header.Length);
            if (cells.Length != header.Length)
                return Fail($"ответ читающего инструмента не разбирается: у строки {cells.Length} столбцов вместо {header.Length}");
            rows.Add(cells);
        }
        if (rows.Count != declared)
            return Fail($"ответ читающего инструмента прочитан не целиком: в строке-шапке строк {declared}, разобрано {rows.Count}");

        return new StorageResult(true, rows, "");
    }

    private static string Short(string s) => s.Trim().Length > 120 ? s.Trim()[..120] + "…" : s.Trim();
}

/// <summary>Порядок имён по байтам UTF-8: так сортируют обе стороны (служба и приёмка), а не по алфавиту и не без учёта регистра.</summary>
public sealed class Utf8Order : IComparer<string>
{
    public static readonly Utf8Order Instance = new();

    public int Compare(string? a, string? b)
    {
        var x = Encoding.UTF8.GetBytes(a ?? "");
        var y = Encoding.UTF8.GetBytes(b ?? "");
        return x.AsSpan().SequenceCompareTo(y);
    }
}

public static class Fold
{
    /// <summary>sha256 по тексту в UTF-8, первые 12 знаков в нижнем регистре.</summary>
    public static string Sha12(string text) =>
        Convert.ToHexStringLower(SHA256.HashData(Encoding.UTF8.GetBytes(text)))[..12];
}

/// <summary>
/// Запись установщика в таблице meta хранилища: commit, пакет, час записи и отпечатки файлов. Принимается ЦЕЛИКОМ либо никак:
/// не вышло прочесть или разобрать любой её кусок — «нечем проверить» у каждого поля записи, с причиной.
/// </summary>
public sealed record InstallRecord(Piece Commit, Piece Package, Piece RecordedAt, Piece Hash, Piece Files, string Version = "")
{
    /// <summary>Значение общего поля версии из строки template_commit: обрезка пробелов, длина 1..80, не метка пустого значения; иначе пустая строка.</summary>
    public static string PickVersion(string raw)
    {
        var one = raw.Trim();
        return one.Length is > 0 and <= 80 && one != StorageResult.NullMark ? one : "";
    }

    public static InstallRecord Read(Func<string, int, StorageResult> ask)
    {
        var small = ask("SELECT key, value FROM meta WHERE key IN ('template_commit','template_source','template_recorded_at')", 100);
        var files = ask("SELECT value FROM meta WHERE key='template_files_sha'", 10);

        Piece FromMeta(string key)
        {
            if (!small.Ok) return Piece.Fail(small.Reason);
            var row = small.Rows.FirstOrDefault(r => r.Length == 2 && r[0] == key);
            if (row is null) return Piece.Fail($"хранилище ответило, но записи установщика НЕТ: в таблице meta нет строки {key}");
            var v = row[1].Trim();
            return v.Length == 0 || v == StorageResult.NullMark ? Piece.Fail($"в строке meta.{key} значения нет (пусто)") : Piece.Of(v);
        }

        var (hash, count) = ReadFiles(files);
        var all = new[] { FromMeta("template_commit"), FromMeta("template_source"), FromMeta("template_recorded_at"), hash, count };

        var firstFail = all.FirstOrDefault(p => p.Reason is not null);
        if (firstFail is not null)
            all = all.Select(p => p.Reason is null ? Piece.Fail("запись установки в целом не принята — " + firstFail.Reason) : p).ToArray();

        // общее поле версии — из того же чтения, что и поля записи; не вышло прочесть commit — пустая строка, а не догадка
        var version = small.Ok ? PickVersion(small.Rows.FirstOrDefault(r => r.Length == 2 && r[0] == "template_commit")?[1] ?? "") : "";
        return new InstallRecord(all[0], all[1], all[2], all[3], all[4], version);
    }

    /// <summary>Запись meta.template_files_sha — одно значение: JSON «имя файла → отпечаток». Свёртка и число файлов — по всей записи.</summary>
    private static (Piece Hash, Piece Count) ReadFiles(StorageResult files)
    {
        static (Piece, Piece) Bad(string reason) => (Piece.Fail(reason), Piece.Fail(reason));

        if (!files.Ok) return Bad(files.Reason);
        if (files.Rows.Count != 1)
            return Bad("хранилище ответило, но записи установщика НЕТ: в таблице meta нет строки template_files_sha");

        var pairs = new List<(string Name, string Print)>();
        try
        {
            using var doc = JsonDocument.Parse(files.Rows[0][0]);
            if (doc.RootElement.ValueKind != JsonValueKind.Object)
                return Bad($"запись установки (meta.template_files_sha) не разбирается: ждали объект «имя файла → отпечаток», пришло {doc.RootElement.ValueKind}");
            var seen = new HashSet<string>(StringComparer.Ordinal);
            foreach (var p in doc.RootElement.EnumerateObject())
            {
                if (p.Value.ValueKind != JsonValueKind.String)
                    return Bad($"запись установки (meta.template_files_sha) не разбирается: у файла «{p.Name}» отпечаток не строка");
                if (!seen.Add(p.Name))
                    return Bad($"запись установки (meta.template_files_sha) не разбирается: имя файла «{p.Name}» повторено");
                pairs.Add((p.Name, p.Value.GetString()!));
            }
        }
        catch (JsonException e)
        {
            return Bad("запись установки (meta.template_files_sha) не разбирается как JSON: " + e.Message.Split('\n')[0].Trim());
        }

        if (pairs.Count == 0)
            return Bad("запись установки (meta.template_files_sha) пуста: в ней нет ни одного файла");

        pairs.Sort((a, b) => Utf8Order.Instance.Compare(a.Name, b.Name));
        var installText = string.Concat(pairs.Select(p => p.Name + "\t" + p.Print + "\n"));
        var installFold = Fold.Sha12(installText);
        return (Piece.Of(installFold), Piece.Of((long)pairs.Count));
    }
}

/// <summary>Свод правил: таблица rules, правила со status='active' по ключу побайтно, строки «ключ — номер редакции».</summary>
public static class RulesRecord
{
    public const string SourceFold =
        "хранилище контура, таблица rules: свёртка sha256 по строкам «ключ → номер редакции» действующих правил (status='active') по порядку ключей, 12 знаков; "
        + "граница: правка тела правила без смены номера редакции свёртку не меняет";
    public const string SourceActive = "хранилище контура, таблица rules: число правил со status='active'";
    public const string SourceRevoked = "хранилище контура, таблица rules: число правил с любым другим status (снятых и замещённых)";

    public static IReadOnlyList<Field> Read(Func<string, int, StorageResult> ask)
    {
        var r = ask("SELECT rule_key, version, status FROM rules ORDER BY rule_key", 100000);
        if (!r.Ok || r.Rows.Any(x => x.Length != 3))
        {
            var why = r.Ok ? "ответ по таблице rules не разбирается: ждали три столбца" : r.Reason;
            return
            [
                Field.Unknown("judge.rules", "отпечаток свода правил", SourceFold, why),
                Field.Unknown("judge.rules_active", "правил действующих", SourceActive, why),
                Field.Unknown("judge.rules_revoked", "правил снятых", SourceRevoked, why),
            ];
        }

        var active = r.Rows.Where(x => x[2] == "active").Select(x => (Key: x[0], Version: x[1])).ToList();
        active.Sort((a, b) => Utf8Order.Instance.Compare(a.Key, b.Key));
        var rulesText = string.Concat(active.Select(x => x.Key + "\t" + x.Version + "\n"));
        var rulesFold = Fold.Sha12(rulesText);
        return
        [
            Field.Fill("judge.rules", "отпечаток свода правил", rulesFold, SourceFold),
            Field.Fill("judge.rules_active", "правил действующих", (long)active.Count, SourceActive),
            Field.Fill("judge.rules_revoked", "правил снятых", (long)(r.Rows.Count - active.Count), SourceRevoked),
        ];
    }
}

/// <summary>Блоки manifest и judge ответа contour_info: поля, текст из полей, структура для CLI и MCP.</summary>
public static class ContourReport
{
    private const string SourceVersion =
        "хранилище контура, таблица meta, строка template_commit; номера версии пакет не ведёт — версией установленного служит commit";
    private const string SourcePackage = "хранилище контура, таблица meta, строка template_source";
    private const string SourceCommit = "хранилище контура, таблица meta, строка template_commit";
    private const string SourceHash =
        "хранилище контура, таблица meta, строка template_files_sha: свёртка sha256 по парам «имя файла → отпечаток» по порядку имён, 12 знаков; "
        + "тела файлов служба не перечитывает, сверка тел — отдельная команда";
    private const string SourceFiles = "хранилище контура, таблица meta, строка template_files_sha: число пар «имя файла → отпечаток»";
    private const string SourceRecordedAt =
        "хранилище контура, таблица meta, строка template_recorded_at; "
        + "граница: это час записи происхождения установщиком — обновление установленного эту строку не двигает";

    public static IReadOnlyList<Field> ManifestBlock(Manifest manifest, ContourInfo contour, InstallRecord install) =>
    [
        Field.Fill("manifest.contour.id", "контур", contour.Id, "манифест контуров (" + manifest.Path + "): имя контура из вызова"),
        install.Commit.ToField("manifest.tooling.version", "версия тулинга", SourceVersion),
        install.Package.ToField("manifest.tooling.source.package", "источник: пакет", SourcePackage),
        install.Commit.ToField("manifest.tooling.source.commit", "источник: commit", SourceCommit),
        install.Hash.ToField("manifest.tooling.hash", "отпечаток установки", SourceHash),
        install.Files.ToField("manifest.tooling.files", "файлов в записи установки", SourceFiles),
        Field.Fill("manifest.storage.path", "хранилище", contour.Storage, "манифест контуров (" + manifest.Path + "): поле storage"),
        install.RecordedAt.ToField("manifest.installed.at", "час записи установщика", SourceRecordedAt),
    ];

    public static IReadOnlyList<Field> JudgeBlock(Contract contract, IReadOnlyList<Field> rules) =>
    [
        BuildCommit(),
        Field.Fill("judge.contract_version", "версия договора", contract.Version, "файл договора: поле contract.version"),
        Field.Fill("judge.contract_fingerprint", "отпечаток договора", contract.Fingerprint, "файл договора: sha256 по содержимому файла, 12 знаков"),
        .. rules,
    ];

    private static Field BuildCommit() => BuildInfo.CommitKnown
        ? Field.Fill("judge.service_build_commit", "commit сборки", BuildInfo.Commit, "отметка сборки службы: " + BuildInfo.SourceNote())
        : Field.Unknown("judge.service_build_commit", "commit сборки", "отметка сборки службы",
                        "commit НЕИЗВЕСТЕН — собрано не из git (и не из выгрузки git archive с подстановкой commit); " + BuildInfo.SourceNote());

    /// <summary>Предупреждения ответа. Оставшийся в манифесте блок tooling служба не читает и не печатает — только говорит, что он есть.</summary>
    public static IReadOnlyList<string> Notes(ContourInfo contour) =>
        contour.LegacyToolingBlock
            ? ["⚠️ в манифесте контуров у контура «" + contour.Id + "» остался блок tooling: служба его НЕ читает, версия, источник, отпечаток и час установки "
               + "берутся только из хранилища. Блок можно удалить из файла манифеста."]
            : [];

    /// <summary>Структура ответа: details.manifest.*, details.judge.*, details.notes. Её же печатает режим run --json.</summary>
    public static JsonObject Details(IReadOnlyList<Field> manifest, IReadOnlyList<Field> judge, IReadOnlyList<string> notes)
    {
        var root = new JsonObject { ["manifest"] = new JsonObject(), ["judge"] = new JsonObject() };
        foreach (var f in manifest.Concat(judge))
            Put(root, f.Path, f.ToJson());
        var list = new JsonArray();
        foreach (var n in notes) list.Add(n);
        root["notes"] = list;
        return root;
    }

    private static void Put(JsonObject root, string path, JsonNode node)
    {
        var parts = path.Split('.');
        var cur = root;
        for (var i = 0; i < parts.Length - 1; i++)
        {
            cur[parts[i]] ??= new JsonObject();
            cur = (JsonObject)cur[parts[i]]!;
        }
        cur[parts[^1]] = node;
    }

    /// <summary>Текст ответа строится из тех же полей: каждая строка поля — значение, источник, состояние.</summary>
    public static string Text(Contract contract, Manifest manifest, ContourInfo contour, bool readOnly,
                              IReadOnlyList<Field> manifestFields, IReadOnlyList<Field> judgeFields, IReadOnlyList<string> notes)
    {
        var sb = new StringBuilder();
        sb.AppendLine("── манифест контура (у каждого поля свой источник; поля из хранилища отвечают «нечем проверить», когда оно молчит)");
        foreach (var f in manifestFields) sb.AppendLine(f.Line());
        sb.AppendLine("── кто меня судит");
        foreach (var f in judgeFields) sb.AppendLine(f.Line());
        sb.AppendLine("── прочее");
        foreach (var (key, dir) in contour.ToolDirs)
            sb.AppendLine($"каталог «{key}» ........ {dir}");
        sb.AppendLine($"договор ................ {contract.Path}");
        sb.AppendLine($"вызовов в договоре ..... {contract.Tools.Count}, отпечаток перечня {contract.ToolsFingerprint()}");
        sb.AppendLine($"режим стены ............ {(readOnly ? "только-чтение" : "чтение и запись")}");
        foreach (var n in notes) sb.AppendLine(n);
        return sb.ToString();
    }
}
