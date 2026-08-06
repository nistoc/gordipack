using Gordi.Viewer.Api.Model;

namespace Gordi.Viewer.Api.Services;

/// <summary>
/// Последний удачно собранный снимок и последняя ошибка сборки — рядом, а не вместо.
///
/// 📌 Почему ошибка НЕ затирает снимок: если база на минуту стала недоступна
///    (её копируют, чинят, переименовали), правильное поведение — показать
///    прежние данные С ПОМЕТКОЙ, когда они собраны и что случилось потом.
///    Пустой экран вместо этого сообщал бы «данных нет», а это неправда.
/// </summary>
public sealed class SnapshotStore
{
    private ViewerSnapshot? _snapshot;
    private string? _lastError;
    private DateTimeOffset? _lastRefreshUtc;
    private DateTimeOffset? _lastChangeUtc;

    public ViewerSnapshot? Current => Volatile.Read(ref _snapshot);
    public string? LastError => Volatile.Read(ref _lastError);
    public DateTimeOffset? LastRefreshUtc => _lastRefreshUtc;
    public DateTimeOffset? LastChangeDetectedUtc => _lastChangeUtc;

    public void Publish(ViewerSnapshot snapshot, bool changed)
    {
        Volatile.Write(ref _snapshot, snapshot);
        Volatile.Write(ref _lastError, null);
        _lastRefreshUtc = DateTimeOffset.UtcNow;
        if (changed) _lastChangeUtc = snapshot.BuiltAtUtc;
    }

    public void Touch() => _lastRefreshUtc = DateTimeOffset.UtcNow;

    public void Fail(string error)
    {
        Volatile.Write(ref _lastError, error);
        _lastRefreshUtc = DateTimeOffset.UtcNow;
    }

    /// <summary>Сбросить снимок — при смене источника, чтобы не показывать чужие числа.</summary>
    public void Clear()
    {
        Volatile.Write(ref _snapshot, null);
        Volatile.Write(ref _lastError, null);
        _lastChangeUtc = null;
    }
}
