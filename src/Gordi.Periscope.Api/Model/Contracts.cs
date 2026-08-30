namespace Gordi.Periscope.Api.Model;

// ── Источники ────────────────────────────────────────────────────────────────

/// <summary>Найденный файл базы — кандидат в источники.</summary>
public sealed record SourceInfo(
    string Path,
    string Name,
    long SizeBytes,
    DateTimeOffset ModifiedUtc,
    bool IsActive);

// ── Состояние сервиса ────────────────────────────────────────────────────────

public sealed record HealthDto(
    string Status,                       // ok | no-source | error
    string? ActiveDbPath,
    string? ScanRoot,
    bool ReadOnly,                       // всегда true — см. ReadOnlyDb
    int RefreshSeconds,
    DateTimeOffset? LastRefreshUtc,
    DateTimeOffset? LastChangeDetectedUtc,
    string? LastError,
    DateTimeOffset NowUtc);

// ── Обзор ────────────────────────────────────────────────────────────────────

/// <summary>
/// Счётчик, который умеет сказать «не поддерживается этой базой».
/// Именно ради этого он не просто long: 0 и «нечем посчитать» — разные новости.
/// </summary>
public sealed record Measure(long? Value, bool Supported, string? Note = null)
{
    public static Measure Of(long v) => new(v, true);
    public static Measure Unsupported(string why) => new(null, false, why);
}

public sealed record OverviewDto(
    string? GroupName,
    SchemaVersionDto SchemaVersion,
    Measure Messages,
    Measure MessagesHistory,
    Measure Roles,
    Measure Rules,
    Measure TasksTotal,
    Measure TasksOpen,
    Measure TasksDone,
    Measure TasksOpenWithoutCriterion,
    DateTimeOffset? LastMessageUtc,
    DateTimeOffset BuiltAtUtc);

public sealed record SchemaVersionDto(
    string? Declared,          // meta.schema_version, если есть
    string? Milestone,         // последний рубеж 'vN' из schema_migrations
    int? StepsTotal,
    int? StepsAfterMilestone,
    string? Note);

// ── Задачи ───────────────────────────────────────────────────────────────────

public sealed record TaskDto(
    long Id,
    string? Role,
    string? Title,
    string? Status,
    string? Priority,
    string? DoneWhen,
    bool CriterionSupported,   // есть ли в этой базе колонка done_when
    bool HasCriterion,         // если не supported — всегда false, и это видно по флагу выше
    string[] Tags,
    long? ParentId,
    string? ParentTrack,
    string? BlockedReason,
    // Причина устаревания: последний status_change → dropped с непустой запиской.
    // null у dropped-карточки значит «причина НЕ ЗАПИСАНА» (устарела до ворот на
    // обязательную причину) — витрина обязана сказать это словами, а не молчать.
    string? DroppedReason,
    string? CreatedBy,
    string? CreatedAt,
    string? UpdatedAt,
    int BodyLength);

public sealed record TaskDetailDto(
    TaskDto Task,
    string? BodyMd,
    IReadOnlyList<TaskEventDto> Events,
    IReadOnlyList<TaskTestDto> Tests,
    IReadOnlyList<MessageDto> LinkedMessages,
    IReadOnlyList<string> MissingFeatures);   // чего в этой базе нет: backlog_events, message_task, …

public sealed record TaskEventDto(
    long Id, string? At, string? ActorRole, string? EventType,
    string? FromStatus, string? ToStatus, string? BodyMd);

public sealed record TaskTestDto(
    long Id, string? Title, string? Method, string? Status,
    string? Command, string? Expected, string? LastRunAt, string? LastResultMd);

// ── Лента ────────────────────────────────────────────────────────────────────

public sealed record MessageDto(
    long Id,
    string? WriterRole,
    string? Timestamp,
    string? Priority,
    string[] Tags,
    bool? Broadcast,
    string? Source,            // live | history — только если есть VIEW messages_all
    int BodyLength,
    string BodyPreview,
    string? BodyMd);           // заполняется только в GET /api/messages/{id}

public sealed record MessagePageDto(
    IReadOnlyList<MessageDto> Items,
    int Limit,
    int Offset,
    long Total,
    string SourceObject);      // из чего читали: messages_all | messages

// ── Роли ─────────────────────────────────────────────────────────────────────

public sealed record RoleDto(
    string Role,
    string? Status,            // из roles.status / roles.lifecycle — что нашлось
    string? StatusNote,        // из role_status.status (свободный текст), если есть
    string? StatusUpdatedAt,
    bool? InRoster,
    long? CursorAt,            // read_cursors.last_read_id
    long? MessagesWritten,
    string? LastMessageAt,
    int PhoenixSections,
    string? PhoenixSavedAt);

public sealed record RolesDto(
    IReadOnlyList<RoleDto> Items,
    IReadOnlyList<string> MissingFeatures);

// ── Правила ──────────────────────────────────────────────────────────────────

public sealed record RuleDto(
    string RuleKey,
    string? Status,            // 'active' если в базе нет колонки статуса — см. Note
    string? StatusNote,
    int? Version,
    string? LockedBy,
    string? UpdatedAt,
    int BodyLength,
    string BodyPreview,
    string? Body,
    // ── при каком условии правило перестаёт действовать ──────────────────────
    string? ExpiryKind,        // forever | until_date | until_event | while_measured | null
    string? ExpiryCond,        // словами: до какой даты, до какого события
    // ── основание: почему правило вообще есть ───────────────────────────────
    string? Basis,
    string? Authorized,
    string? SourceRef,
    // ── отозвано или нет ────────────────────────────────────────────────────
    // true — правило БОЛЬШЕ НЕ ДЕЙСТВУЕТ. Отдельным полем, а не догадкой на стороне
    // интерфейса: это самый дорогой факт на странице правил, и определяться он обязан
    // в ОДНОМ месте, иначе сервис и интерфейс однажды разойдутся в ответе молча.
    bool Revoked,
    // Чем именно установлено «отозвано» — чтобы вывод можно было перепроверить, а не
    // принимать на веру. Пусто, когда правило не отозвано.
    string? RevokedBasis);

// ── Схема ────────────────────────────────────────────────────────────────────

public sealed record SchemaObjectDto(string Name, string Type, IReadOnlyList<string> Columns);

public sealed record SchemaReportDto(
    IReadOnlyList<SchemaObjectDto> Present,
    IReadOnlyList<string> ExpectedButMissing,
    IReadOnlyList<string> PresentButUnknownToPeriscope,
    string Note);

// ── Пул (П③ нового порядка, 28.08) ──────────────────────────────────────────

/// <summary>Карточка пула. Ownerless = role SHARED: «часть без хозяина» — витрина
/// обязана показать это словами, а не отсутствием строки.</summary>
public sealed record PoolCardDto(
    long Id, string? Role, string? Title, string? Status, string? Priority,
    bool HasCriterion, bool Ownerless);

/// <summary>Объявление работы над карточкой пула («кто где»). Overdue = срок вышел,
/// карточка не закрыта, объявление не снято, и после срока от роли ни одного события.
/// ⚠️ КАНОН предиката — backlog.py::live_and_overdue (живой контур); эта копия на C#
/// обязана меняться ВМЕСТЕ с ним — расхождение витрины с инструментом хуже отсутствия.</summary>
public sealed record PoolClaimDto(
    long CardId, string? Role, string? UntilUtc, string? Note, bool Overdue, long? OverdueHours);

public sealed record PoolVerdictDto(string? Role, string? Kind, string? Verdict);

public sealed record PoolDto(
    string TrackId,
    string? Title,
    string? OwnerWord,
    string? Skills,          // null = «скиллы под пул не названы» — фронт говорит словами
    string? PlanHead,        // первые строки словесного слоя; null = план не записан
    int CardsTotal,
    int CardsClosed,
    IReadOnlyList<PoolCardDto> Cards,          // отсортированы role,id — группировка фронта
    IReadOnlyList<PoolClaimDto> LiveClaims,
    IReadOnlyList<PoolClaimDto> OverdueClaims,
    IReadOnlyList<PoolCardDto> Stuck,          // blocked | awaiting_word — «застряло»
    IReadOnlyList<PoolVerdictDto> Verdicts);

/// <summary>Витрина пулов. Note несёт причину пустоты/неполноты — пустой список без
/// причины читался бы как «пулов нет», даже когда таблицы tracks нет вовсе.</summary>
public sealed record PoolsDto(
    IReadOnlyList<PoolDto> Active,
    string? Note);

// ── Наборы задач ─────────────────────────────────────────────────────────────

/// <summary>
/// Набор задач. Declared=false — набор, который задачи НАЗЫВАЮТ, а в таблице tracks
/// его нет вовсе (замер живой базы 2026-08-30 22:39 UTC: таких задач 8, набор «vnext»).
/// Такой набор обязан быть виден: показать только заявленные значило бы потерять задачи
/// молча — ровно тот случай, когда список не лжёт построчно и лжёт СОСТАВОМ.
/// </summary>
public sealed record TrackInfoDto(
    string TrackId,
    string? Title,
    string? Status,            // active | paused | done — как в базе; null у незаявленного
    bool Declared,
    int TaskCount);

/// <summary>Витрина наборов. Untracked — задачи БЕЗ набора: это не набор, и потому
/// отдельным числом, а не строкой в списке.</summary>
public sealed record TracksDto(
    IReadOnlyList<TrackInfoDto> Items,
    int Untracked,
    int TasksTotal,
    string? Note);

/// <summary>
/// Группа задач одного набора. TrackId=null — группа «без набора»: она есть в ответе
/// ВСЕГДА, когда такие задачи есть, и стои́т последней.
/// </summary>
public sealed record TaskGroupDto(
    string? TrackId,
    string? Title,
    string? Status,
    bool Declared,
    int Count,
    IReadOnlyList<TaskDto> Items);

/// <summary>
/// Задачи, сгруппированные по наборам. TotalTasks обязан равняться сумме Count по группам —
/// это и есть проверка «ничего не потеряно»; расхождение называется в Note, а не молчит.
/// </summary>
public sealed record TasksGroupedDto(
    IReadOnlyList<TaskGroupDto> Groups,
    int TotalTasks,
    int Ungrouped,             // задач без набора
    int UndeclaredTracks,      // наборов, которых нет в таблице tracks
    string? Note);

// ── Снимок ───────────────────────────────────────────────────────────────────

/// <summary>
/// То, что фоновая служба перечитывает по таймеру и кладёт целиком.
/// Лента сюда НЕ входит намеренно: 3021 запись × ~2.5 КБ тела ≈ 4 МБ —
/// держать это в памяти ради страницы из 50 строк незачем, лента читается запросом.
/// </summary>
public sealed record PeriscopeSnapshot(
    string DbPath,
    string Fingerprint,
    DateTimeOffset BuiltAtUtc,
    OverviewDto Overview,
    IReadOnlyList<TaskDto> Tasks,
    RolesDto Roles,
    IReadOnlyList<RuleDto> Rules,
    SchemaReportDto Schema,
    PoolsDto Pools,
    // Заявленные наборы задач (таблица tracks). Пусто, если таблицы нет — тогда
    // группировка строится по одним значениям parent_track и говорит об этом словом.
    IReadOnlyList<TrackDeclarationDto> TrackDeclarations);

/// <summary>Строка таблицы tracks — как она есть, без счёта задач: счёт делается
/// в ОДНОМ месте (витрина), иначе два счёта однажды разойдутся молча.</summary>
public sealed record TrackDeclarationDto(string TrackId, string? Title, string? Status);
