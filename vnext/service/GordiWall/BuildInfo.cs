using System.Reflection;

namespace GordiWall;

/// <summary>
/// Отметка сборки: из какого commit собрана стена. Значения вшиты при сборке (цель GordiBuildStamp в GordiWall.csproj)
/// атрибутами сборки; здесь они только читаются. Пустой commit значит «собрано не из git и без выгрузки с подстановкой».
/// </summary>
public static class BuildInfo
{
    private static string Meta(string key) =>
        typeof(BuildInfo).Assembly.GetCustomAttributes<AssemblyMetadataAttribute>()
            .FirstOrDefault(a => string.Equals(a.Key, key, StringComparison.Ordinal))?.Value ?? "";

    /// <summary>Commit сборки, 40 знаков; пусто, если неизвестен.</summary>
    public static string Commit => Meta("GordiCommit");

    public static bool CommitKnown => Commit.Length == 40;

    /// <summary>yes — в каталоге службы были незакоммиченные правки; no — не было; unknown — git рядом не было.</summary>
    public static string Dirty => Meta("GordiDirty");

    public static string SourceUrl => Meta("GordiSourceUrl");

    public static string SourcePath => Meta("GordiSourcePath");

    public static string BuildDir => Meta("GordiBuildDir");

    /// <summary>Значение для поля serverInfo: commit или слово «unknown».</summary>
    public static string CommitForServerInfo => CommitKnown ? Commit : "unknown";

    /// <summary>Строки для contour_info. Незнание названо прямо: «собрано не из git», а не пустое место.</summary>
    public static IEnumerable<string> Lines()
    {
        if (!CommitKnown)
        {
            yield return "commit сборки ......... НЕИЗВЕСТЕН — собрано не из git (и не из выгрузки git archive с подстановкой commit)";
            yield return $"каталог сборки ........ {Or(BuildDir)}";
            yield break;
        }

        var dirty = Dirty switch
        {
            "yes" => "в дереве были незакоммиченные правки: ДА — по этому commit сборку не воспроизвести",
            "no" => "незакоммиченных правок в дереве не было",
            _ => "были ли незакоммиченные правки — неизвестно (сборка из выгрузки)",
        };
        yield return $"commit сборки ......... {Commit} ({dirty})";
        yield return $"исходник .............. {Or(SourceUrl, "адрес origin неизвестен")} · {Or(SourcePath)}";
        yield return $"каталог сборки ........ {Or(BuildDir)}";
    }

    private static string Or(string value, string whenEmpty = "неизвестно") =>
        string.IsNullOrWhiteSpace(value) ? whenEmpty : value;
}
