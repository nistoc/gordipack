using Microsoft.Data.Sqlite;

namespace Gordi.Viewer.Api.Data;

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
