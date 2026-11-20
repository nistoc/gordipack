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

    /// <summary>
    /// Слова об отметке сборки для источника поля commit сборки: были ли незакоммиченные правки, адрес исходника и каталог сборки.
    /// Незнание названо прямо: «собрано не из git», а не пустое место.
    /// </summary>
    public static string SourceNote()
    {
        if (!CommitKnown)
            return $"каталог сборки {Or(BuildDir)}";

        var dirty = Dirty switch
        {
            "yes" => "в дереве были незакоммиченные правки: ДА — по этому commit сборку не воспроизвести",
            "no" => "незакоммиченных правок в дереве не было",
            _ => "были ли незакоммиченные правки — неизвестно (сборка из выгрузки)",
        };
        return $"{dirty}; исходник {Or(SourceUrl, "адрес origin неизвестен")} · {Or(SourcePath)}; каталог сборки {Or(BuildDir)}";
    }

    private static string Or(string value, string whenEmpty = "неизвестно") =>
        string.IsNullOrWhiteSpace(value) ? whenEmpty : value;
}
