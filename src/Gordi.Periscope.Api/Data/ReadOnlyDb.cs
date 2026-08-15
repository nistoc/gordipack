using Microsoft.Data.Sqlite;

namespace Gordi.Periscope.Api.Data;

/// <summary>
/// ЕДИНСТВЕННОЕ место, где открывается соединение с базой. Открывается только на чтение.
///
/// ⛔ ГРАНИЦА СЕРВИСА: он НЕ ПИШЕТ в координационную базу — ни строки, ни DDL.
///    Здесь это не обещание в документации, а три независимых замка:
///      1) Mode=ReadOnly            — SQLite открывает файл флагом SQLITE_OPEN_READONLY;
///      2) PRAGMA query_only = 1    — соединение отказывает любой пишущей инструкции,
///                                    даже если Mode кто-то поменяет;
///      3) весь SQL живёт в MezosyncReader и состоит из SELECT/PRAGMA — параметризованных.
///    Одного замка мало намеренно: каждый из трёх снимается своей ошибкой, все три — нет.
/// </summary>
public static class ReadOnlyDb
{
    public static SqliteConnection Open(string path)
    {
        var cs = new SqliteConnectionStringBuilder
        {
            DataSource = path,
            Mode = SqliteOpenMode.ReadOnly,
            Cache = SqliteCacheMode.Private,
            // Пул держал бы соединение живым после Dispose. Живое читающее соединение
            // к базе в режиме WAL мешает усечению журнала у ПИШУЩЕЙ стороны — то есть
            // просмотрщик начал бы влиять на работу контура. Не влияем.
            Pooling = false,
            DefaultTimeout = 5
        }.ToString();

        var connection = new SqliteConnection(cs);
        connection.Open();

        using (var pragma = connection.CreateCommand())
        {
            // busy_timeout — чтобы кратковременная блокировка писателя давала паузу,
            // а не мгновенную ошибку. query_only — второй замок, см. шапку.
            pragma.CommandText = "PRAGMA busy_timeout = 3000; PRAGMA query_only = 1;";
            pragma.ExecuteNonQuery();
        }

        return connection;
    }

    /// <summary>
    /// ЗАМЕР read-only по живому соединению — а не пересказ конфигурации.
    /// До этого замера /api/health печатал ReadOnly: true КОНСТАНТОЙ: подмени Mode —
    /// и витрина продолжила бы говорить «только чтение». Сторож, который не краснеет
    /// ни на чём, сторожем не считается (критерий приёмки просмотрщика, пункт ②).
    ///
    /// Три независимых показания — по одному на замок:
    ///   modeReadOnly — строка ФАКТИЧЕСКОГО соединения несёт Mode=ReadOnly (замок 1);
    ///   queryOnly    — PRAGMA query_only отвечает 1 (замок 2);
    ///   writeRefused — канарейка BEGIN IMMEDIATE (захват пишущей блокировки, данных
    ///                  не трогает) ПОЛУЧИЛА ОТКАЗ; если прошла — откатывается и
    ///                  честно возвращает false (оба первых замка сняты).
    /// Итог true только когда все три true: подмена любого замка красит health.
    /// </summary>
    public static bool ProveReadOnly(SqliteConnection c)
    {
        var modeReadOnly = c.ConnectionString.Contains("Mode=ReadOnly", StringComparison.OrdinalIgnoreCase);

        bool queryOnly;
        using (var q = c.CreateCommand())
        {
            q.CommandText = "PRAGMA query_only;";
            queryOnly = Convert.ToInt64(q.ExecuteScalar() ?? 0L) == 1;
        }

        bool writeRefused;
        try
        {
            using var canary = c.CreateCommand();
            canary.CommandText = "BEGIN IMMEDIATE; ROLLBACK;";
            canary.ExecuteNonQuery();
            writeRefused = false;   // пишущая блокировка ВЗЯЛАСЬ — соединение умеет писать
        }
        catch (SqliteException)
        {
            writeRefused = true;    // отказ и есть искомое поведение
        }

        return modeReadOnly && queryOnly && writeRefused;
    }

    /// <summary>
    /// Отпечаток файла базы: длина и время правки самого файла И его журнала WAL.
    /// Нужен, чтобы (а) не перечитывать неизменившуюся базу, (б) честно показывать
    /// в интерфейсе «источник менялся в такое-то время».
    ///
    /// ⚠️ ЧЕГО ЭТОТ ОТПЕЧАТОК НЕ УМЕЕТ — сказано здесь, а не выяснится потом:
    ///    в режиме WAL запись сначала уходит в файл -wal, и mtime самой .db может
    ///    не двигаться минутами. Поэтому в отпечаток входит и -wal. Но время правки
    ///    файла в принципе ненадёжно (его сбрасывает копирование), поэтому отпечаток —
    ///    признак «скорее всего изменилось», а НЕ доказательство. Он только экономит
    ///    перечитывание; правильность данных на нём не держится.
    /// </summary>
    public static string Fingerprint(string path)
    {
        static string Part(string p)
        {
            var fi = new FileInfo(p);
            return fi.Exists ? $"{fi.Length}:{fi.LastWriteTimeUtc.Ticks}" : "-";
        }

        return $"{Part(path)}|{Part(path + "-wal")}|{Part(path + "-shm")}";
    }
}
