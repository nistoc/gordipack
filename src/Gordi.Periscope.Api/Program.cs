using Gordi.Periscope.Api.Configuration;
using Gordi.Periscope.Api.Endpoints;
using Gordi.Periscope.Api.Services;

var builder = WebApplication.CreateBuilder(args);

// ── Конфигурация ─────────────────────────────────────────────────────────────
// Приоритет снизу вверх: appsettings.json → переменные среды → аргументы запуска.
//
// Почему именно так, а не «только аргумент» или «только файл»:
//   · аргумент  — для разового запуска над чужой базой, ничего не сохраняя;
//   · переменная среды — для ярлыка/скрипта, чтобы не повторять путь руками;
//   · appsettings — для «моей обычной базы», которую открываешь каждый день.
// Все три уже есть в самом ASP.NET Core, свой разбор командной строки не нужен.
// Читаемые имена (--db, GORDI_DB) вместо канонических Periscope:Db — ниже отображением.

var envOverrides = new Dictionary<string, string?>();
void FromEnv(string variable, string key)
{
    var value = Environment.GetEnvironmentVariable(variable);
    if (!string.IsNullOrWhiteSpace(value)) envOverrides[key] = value;
}

FromEnv("GORDI_DB", "Periscope:Db");
FromEnv("GORDI_DIR", "Periscope:Directory");
FromEnv("GORDI_REFRESH_SECONDS", "Periscope:RefreshSeconds");
FromEnv("GORDI_PORT", "Periscope:Port");
builder.Configuration.AddInMemoryCollection(envOverrides);

// Командная строка добавляется ПОСЛЕ переменных среды — значит побеждает.
builder.Configuration.AddCommandLine(args, new Dictionary<string, string>
{
    ["--db"] = "Periscope:Db",
    ["--dir"] = "Periscope:Directory",
    ["--refresh"] = "Periscope:RefreshSeconds",
    ["--port"] = "Periscope:Port"
});

builder.Services.Configure<PeriscopeOptions>(builder.Configuration.GetSection(PeriscopeOptions.SectionName));
var options = builder.Configuration.GetSection(PeriscopeOptions.SectionName).Get<PeriscopeOptions>() ?? new PeriscopeOptions();

// ⛔ Слушаем ТОЛЬКО петлевой адрес. Сервис отдаёт содержимое координационной базы
//    без всякой аутентификации — на 0.0.0.0 это означало бы отдать её всей сети.
//    Порт меняется (--port), адрес — нет.
builder.WebHost.UseUrls($"http://127.0.0.1:{options.Port}");

builder.Services.AddSingleton<SourceRegistry>();
builder.Services.AddSingleton<SnapshotStore>();
builder.Services.AddSingleton<SnapshotRefreshService>();
builder.Services.AddHostedService(sp => sp.GetRequiredService<SnapshotRefreshService>());

builder.Services.AddCors(o => o.AddPolicy("client", p => p
    .WithOrigins(options.ClientOrigins)
    .AllowAnyHeader()
    .AllowAnyMethod()));

var app = builder.Build();

// Провайдер SQLite инициализируется явно: пакет Microsoft.Data.Sqlite.Core сам
// этого не делает, а без инициализации первое же открытие падает в рантайме.
SQLitePCL.Batteries_V2.Init();

app.UseCors("client");
app.MapApi();

// Фронтенд в этой сборке НЕ раздаётся: в разработке он живёт на своём порту (Vite),
// и склеивание двух режимов раздачи — отдельное решение, а не умолчание. См. README.
app.MapGet("/", () => Results.Text(
    $"""
     Gordi Periscope API — только чтение.
     Активная база: {app.Services.GetRequiredService<SourceRegistry>().ActivePath ?? "не задана (--db / --dir)"}
     Проверка: /api/health
     """, "text/plain; charset=utf-8"));

app.Run();
