namespace Gordi.Viewer.Api.Configuration;

/// <summary>
/// Настройки просмотрщика. Читаются из трёх источников, приоритет снизу вверх:
///   1. appsettings.json      — секция "Viewer"
///   2. переменные среды      — GORDI_DB, GORDI_DIR, GORDI_REFRESH_SECONDS, GORDI_PORT
///   3. аргументы запуска     — --db, --dir, --refresh, --port   (побеждают всё)
/// </summary>
public sealed class ViewerOptions
{
    public const string SectionName = "Viewer";

    /// <summary>Путь к конкретному файлу базы. Если задан — он и есть активный источник.</summary>
    public string? Db { get; set; }

    /// <summary>
    /// Каталог для поиска баз (*.db). Найденное отдаётся в GET /api/sources,
    /// и переключаться можно ТОЛЬКО между найденным здесь — произвольный путь
    /// с фронтенда не принимается (иначе просмотрщик = чтение любого файла на диске).
    /// </summary>
    public string? Directory { get; set; }

    /// <summary>Глубина обхода каталога. 0 = только сам каталог.</summary>
    public int ScanDepth { get; set; } = 3;

    /// <summary>Период фонового перечитывания базы, секунды.</summary>
    public int RefreshSeconds { get; set; } = 15;

    /// <summary>Порт локального сервиса. Слушаем ТОЛЬКО 127.0.0.1.</summary>
    public int Port { get; set; } = 5177;

    /// <summary>Размер страницы ленты по умолчанию.</summary>
    public int FeedPageSize { get; set; } = 50;

    /// <summary>Потолок размера страницы ленты (защита от ?limit=100000).</summary>
    public int FeedMaxPageSize { get; set; } = 200;

    /// <summary>
    /// Читать не сам файл, а его свежую копию во временном каталоге.
    /// По умолчанию ВЫКЛЮЧЕНО. Включать, если прямое открытие живого файла
    /// невозможно (нет прав на -shm рядом с WAL) или нежелательно.
    /// </summary>
    public bool CopyBeforeRead { get; set; }

    /// <summary>Разрешённые источники CORS для дев-режима фронтенда.</summary>
    public string[] ClientOrigins { get; set; } =
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ];
}
