# -*- coding: utf-8 -*-
r"""ПРИЁМКА покрытия маршрутов check-viewer-readonly.py — карточка #646.

🩸 ЧЕМ ОПЛАЧЕНО (находка tapas @COORD, 2026-09-15). Перечень маршрутов держали рукой —
9 адресов; у службы (`ApiEndpoints.cs`) их 15. Вывод «эндпоинтов отвечено 200: 18 из 18»
читался как «всё обойдено», а составом это было 9 из 15: pool · tracks · tasks/grouped ·
tasks/history · tasks/{id} · messages/{id} не обходились вовсе, и находка об этом молчала.

Правка (см. check-viewer-readonly.py): перечень маршрутов теперь РАЗБИРАЕТСЯ из исходника
службы (MapGet в ApiEndpoints.cs), маршрут с {id} разворачивается ЖИВЫМ id из ответа
маршрута-списка, а исходник недостижим — говорит об этом строкой, не молчит и не врёт
про полное покрытие.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково; у каждого — своя поломка):
  ① НОВЫЙ MapGet без реализации в службе → проверка называет его «не обойдён» поимённо
     и красится (было бы молча зелено на старом рукописном списке)             РАЗЛИЧАЮЩИЙ
  ② маршрут с {id} разворачивается ЖИВЫМ id ответа списка, не константой:
     две разные службы с разными id получают РАЗНЫЕ запросы                    РАЗЛИЧАЮЩИЙ
  ③ исходник недостижим → «перечень маршрутов службы недоступен — покрытие не
     судится», БЕЗ ложной заявки о полном покрытии                             РАЗЛИЧАЮЩИЙ
  ④ копия НЕ в раскладке пакета (vnext/prototype рядом со src/…), но mezo_paths знает
     образец (MEZO_TEMPLATE) → покрытие судится и БЕЗ --api-source; тот же инструмент
     без MEZO_TEMPLATE — по-прежнему «не судится» (возврат владельца по карточке #646) РАЗЛИЧАЮЩИЙ

Разбор ЦЕЛИКОМ читает исходник службы С ДИСКА (не ходит в сеть за ним) — поэтому подставной
службой (маленький HTTP-сервер в песочнице, свой порт, глушится сам по своему объекту)
подменяется только ОБХОД маршрутов; разбор судится отдельно, без сети.

⛔ Живой службы 5177 и живой базы не касается: фикстура службы — синтетический текст,
   построенный ЗДЕСЬ (не читается из контура/пакета/клона), база подставной службы —
   собственный временный sqlite-файл.
"""
from __future__ import annotations

import http.server
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402

TOOL = pathlib.Path(__file__).with_name("check-viewer-readonly.py")
CASES = DIFFER = 0

# ── фикстура исходника службы: 15 маршрутов, та же форма, что у ApiEndpoints.cs ──────
FIXTURE_BASE = """
using Microsoft.Extensions.Options;
namespace Gordi.Periscope.Api.Endpoints;
public static class ApiEndpoints
{
    public static void MapApi(this WebApplication app)
    {
        var api = app.MapGroup("/api");
        api.MapGet("/health", (SourceRegistry s) => Results.Ok());
        api.MapGet("/sources", (SourceRegistry s) => Results.Ok());
        api.MapGet("/overview", (SnapshotStore s) => Results.Ok());
        api.MapGet("/schema", (SnapshotStore s) => Results.Ok());
        api.MapGet("/roles", (SnapshotStore s) => Results.Ok());
        api.MapGet("/rules", (SnapshotStore s) => Results.Ok());
        api.MapGet("/pool", (SnapshotStore s) => Results.Ok());
        api.MapGet("/tracks", (SnapshotStore s) => Results.Ok());
        api.MapGet("/tasks", (SnapshotStore s) => Results.Ok());
        api.MapGet("/tasks/grouped", (SnapshotStore s) => Results.Ok());
        api.MapGet("/tasks/{id:long}", (long id, SnapshotStore s) => Results.Ok());
        api.MapGet("/tasks/history", (SourceRegistry s) => Results.Ok());
        api.MapGet("/messages", (SourceRegistry s) => Results.Ok());
        api.MapGet("/messages/{id:long}", (long id, SourceRegistry s) => Results.Ok());
        api.MapGet("/writers", (SourceRegistry s) => Results.Ok());
    }
}
"""
# Тот самый класс беды карточки #646: маршрут, добавленный ПОСЛЕ того, как рукописный
# список составлен, — служба его знает, стенд его НЕ реализует (как новый маршрут,
# который ещё не задеплоен).
NEW_ROUTE = "/tasks/pinned"
FIXTURE_WITH_NEW_ROUTE = FIXTURE_BASE.replace(
    'api.MapGet("/writers"',
    f'api.MapGet("{NEW_ROUTE}", (SnapshotStore s) => Results.Ok());\n'
    '        api.MapGet("/writers"')

# Полные пути (с префиксом /api) — ровно то, что несёт self.path у стенда.
KNOWN_STATIC = ["/api/health", "/api/sources", "/api/overview", "/api/schema",
                "/api/roles", "/api/rules", "/api/pool", "/api/tracks", "/api/tasks",
                "/api/tasks/grouped", "/api/tasks/history", "/api/messages",
                "/api/writers"]


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def make_db(path: pathlib.Path) -> pathlib.Path:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()
    return path


class StubApi(http.server.BaseHTTPRequestHandler):
    """Подставная служба перископа: health + известные маршруты 200, остальное — 404.
    task_id/message_id задают ЖИВЫЕ id для списков tasks/messages (случай ②:
    у разных стендов — разные id, и запрос обязан пойти по НИМ, не по константе)."""
    db_path = ""
    task_id = 111
    message_id = 222
    extra_ok_paths: set = set()
    log: list = []

    def do_GET(self):  # noqa: N802 — имя диктует базовый класс
        path = self.path.split("?")[0]
        StubApi.log.append(path)
        if path == "/api/health":
            self._reply(200, {"status": "ok", "activeDbPath": self.db_path, "readOnly": True})
        elif path == "/api/tasks":
            self._reply(200, [{"id": self.task_id}])
        elif path == "/api/messages":
            self._reply(200, {"items": [{"id": self.message_id}], "limit": 50,
                               "offset": 0, "total": 1, "sourceObject": "messages"})
        elif path == f"/api/tasks/{self.task_id}":
            self._reply(200, {"id": self.task_id})
        elif path == f"/api/messages/{self.message_id}":
            self._reply(200, {"id": self.message_id})
        elif path in self.extra_ok_paths:
            self._reply(200, {})
        else:
            self._reply(404, {"error": "not found"})

    def _reply(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # тишина: журнал стенда — шум приёмки
        pass


def start_stub(db_path: str, task_id: int, message_id: int, extra_ok_paths: set):
    StubApi.db_path = db_path
    StubApi.task_id = task_id
    StubApi.message_id = message_id
    StubApi.extra_ok_paths = extra_ok_paths
    StubApi.log = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StubApi)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def materialize(root: pathlib.Path, name: str, text: str) -> pathlib.Path:
    """Копия TOOL с ПОДМЕНЁННЫМ текстом — вместе с соседями (mezo_paths.py и т.п.),
    без которых копия не запустится (см. mezo_stand.neighbours_of)."""
    dest = root / name
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / TOOL.name
    target.write_text(text, encoding="utf-8")
    for neighbour in mezo_stand.neighbours_of(TOOL):
        shutil.copy2(neighbour, dest / neighbour.name)
    return target


def run_check(tool: pathlib.Path, stand: pathlib.Path, api: str, expect_db,
              api_source=None, extra_env: dict | None = None) -> tuple[int, str]:
    args = [sys.executable, str(tool), "--api", api, "--expect-db", str(expect_db)]
    if api_source is not None:
        args += ["--api-source", str(api_source)]
    env = mezo_stand.stand_env(stand, **(extra_env or {}))
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def patched(anchor: str, replacement: str) -> str | None:
    """Копия ЖИВОГО текста TOOL с РОВНО ОДНОЙ заменой. Якорь встретился не ровно один
    раз (файл менялся) — None, приёмка обязана сказать об этом словами, не тихо."""
    text = TOOL.read_text(encoding="utf-8")
    if text.count(anchor) != 1:
        return None
    return text.replace(anchor, replacement, 1)


def main() -> int:
    ok = True
    root = mezo_stand.new("bite-viewer-routes-")

    fixture_base = root / "fixture-base.cs"
    fixture_base.write_text(FIXTURE_BASE, encoding="utf-8")
    fixture_new = root / "fixture-new-route.cs"
    fixture_new.write_text(FIXTURE_WITH_NEW_ROUTE, encoding="utf-8")
    missing_source = root / "does-not-exist.cs"

    db = make_db(root / "readonly.db")
    extra_no_lists = set(KNOWN_STATIC) - {"/api/health", "/api/tasks", "/api/messages"}

    # ① новый MapGet, служба его не реализует → «не обойдён» поимённо, код красный
    srv, api = start_stub(str(db), 111, 222, extra_no_lists)
    code1, out1 = run_check(TOOL, root, api, db, api_source=fixture_new)
    srv.shutdown()
    ok &= case("① новый маршрут без реализации в службе → назван «не обойдён», код красный",
               code1 == 1 and f"не обойдён: /api{NEW_ROUTE}" in out1
               and "обойдено 15 из 16" in out1,
               f"код {code1}; строка о {NEW_ROUTE} в выводе: "
               f"{'да' if NEW_ROUTE in out1 else 'НЕТ'}", differ=True)

    # ② {id} разворачивается ЖИВЫМ id — две разные службы дают РАЗНЫЕ запросы
    srv, api = start_stub(str(db), 111, 222, extra_no_lists)
    code2a, out2a = run_check(TOOL, root, api, db, api_source=fixture_base)
    log2a = list(StubApi.log)
    srv.shutdown()
    srv, api = start_stub(str(db), 777, 888, extra_no_lists)
    code2b, out2b = run_check(TOOL, root, api, db, api_source=fixture_base)
    log2b = list(StubApi.log)
    srv.shutdown()
    ok &= case("② маршрут с {id} — id из ЖИВОГО ответа списка (не константа)",
               code2a == 0 and code2b == 0
               and "/api/tasks/111" in log2a and "/api/messages/222" in log2a
               and "/api/tasks/777" in log2b and "/api/messages/888" in log2b
               and "обойдено 15 из 15" in out2a and "обойдено 15 из 15" in out2b,
               f"коды {code2a}/{code2b}; запросы стенда А содержат id 111/222: "
               f"{'да' if '/api/tasks/111' in log2a else 'НЕТ'}; стенда Б — 777/888: "
               f"{'да' if '/api/tasks/777' in log2b else 'НЕТ'}", differ=True)

    # ③ исходник недостижим → строка есть, ложной «обойдено» нет
    srv, api = start_stub(str(db), 111, 222, set(KNOWN_STATIC) - {"/api/health"})
    code3, out3 = run_check(TOOL, root, api, db, api_source=missing_source)
    srv.shutdown()
    ok &= case("③ исходник недостижим → «покрытие не судится», без ложного «обойдено»",
               code3 == 0
               and "перечень маршрутов службы недоступен — покрытие не судится" in out3
               and "обойдено" not in out3,
               f"код {code3}; строка есть: "
               f"{'да' if 'покрытие не судится' in out3 else 'НЕТ'}; "
               f"заявки «обойдено» нет: {'да' if 'обойдено' not in out3 else 'НЕТ, ЕСТЬ'}",
               differ=True)

    # ④ копия НЕ в раскладке пакета, но mezo_paths знает образец (MEZO_TEMPLATE) —
    # покрытие судится и без --api-source (возврат владельца по карточке #646).
    # Стенд template_pkg — синтетический «пакет-образец» в песочнице: маркер
    # scripts/init-group.py и src/.../ApiEndpoints.cs с той же базовой фикстурой.
    template_pkg = root / "template-pkg"
    (template_pkg / "scripts").mkdir(parents=True, exist_ok=True)
    (template_pkg / "scripts" / "init-group.py").write_text("# маркер образца\n", encoding="utf-8")
    template_endpoints = template_pkg / "src" / "Gordi.Periscope.Api" / "Endpoints"
    template_endpoints.mkdir(parents=True, exist_ok=True)
    (template_endpoints / "ApiEndpoints.cs").write_text(FIXTURE_BASE, encoding="utf-8")
    # Копия TOOL, вынесенная В СТОРОНУ от какой-либо раскладки пакета (materialize
    # кладёт её в отдельный каталог песочницы, а не рядом с vnext/prototype) — раскладка
    # ① из locate_api_source заведомо не сработает, судьба случая — ЦЕЛИКОМ на раскладке ②.
    standalone_tool = materialize(root, "standalone", TOOL.read_text(encoding="utf-8"))

    # ④а (встречный внутри случая): БЕЗ MEZO_TEMPLATE и БЕЗ --api-source — тот же
    # инструмент, что и в ④б, обязан вести себя КАК ДО ЭТОГО ВОЗВРАТА: «не судится».
    srv, api = start_stub(str(db), 111, 222, extra_no_lists)
    code4a, out4a = run_check(standalone_tool, root, api, db)
    srv.shutdown()
    case4a = case("④а (встречный): образца НЕТ (MEZO_TEMPLATE не задан) → по-прежнему «не судится»",
                  code4a == 0 and "перечень маршрутов службы недоступен — покрытие не судится" in out4a,
                  f"код {code4a}", differ=True)

    # ④б: тот же инструмент, MEZO_TEMPLATE указывает на образец → покрытие судится
    srv, api = start_stub(str(db), 111, 222, extra_no_lists)
    code4b, out4b = run_check(standalone_tool, root, api, db,
                              extra_env={"MEZO_TEMPLATE": str(template_pkg)})
    srv.shutdown()
    case4b = case("④б: MEZO_TEMPLATE указывает на образец → покрытие судится БЕЗ --api-source",
                  code4b == 0 and "обойдено 15 из 15" in out4b,
                  f"код {code4b}; «обойдено 15 из 15» в выводе: "
                  f"{'да' if 'обойдено 15 из 15' in out4b else 'НЕТ'}", differ=True)
    ok &= case4a and case4b

    # ── ОБРАТНЫЕ ХОДЫ: по поломке на каждое новое требование ────────────────────────
    # ①-обратный: разбор снова СУЖЕН до старого рукописного списка (сердце беды
    # карточки #646) — новый маршрут при этом не просто не назван, он вообще не
    # попадает в план и не запрашивается: ровно то поведение, которое искала tapas.
    legacy_9 = ('{"/health", "/sources", "/overview", "/schema", "/roles", "/rules", '
                '"/tasks", "/messages", "/writers"}')
    broken1_text = patched(
        "    routes = sorted(set(ROUTE_RE.findall(text)))",
        f"    routes = sorted(set(ROUTE_RE.findall(text)) & {legacy_9})"
        "  # ПОЛОМКА: снова рукописный список")
    if broken1_text is None:
        ok &= case("①-обратный: якорь разбора маршрутов не найден — приёмка не запустилась",
                   False, "⛔ строка изменилась — правь приёмку")
    else:
        broken1_tool = materialize(root, "broken-coverage", broken1_text)
        srv, api = start_stub(str(db), 111, 222, extra_no_lists)
        code1_b, out1_b = run_check(broken1_tool, root, api, db, api_source=fixture_new)
        srv.shutdown()
        ok &= case("①-обратный: разбор сужен до старых 9 → новый маршрут МОЛЧА не попадает в план",
                   code1_b == 0 and NEW_ROUTE not in out1_b and "обойдено 9 из 9" in out1_b,
                   f"сломанная {code1_b} (настоящая была {code1}) и '{NEW_ROUTE}' в выводе: "
                   f"{'да, ОШИБКА' if NEW_ROUTE in out1_b else 'нет'} — разница доказывает, что "
                   "различает ИМЕННО разбор ApiEndpoints.cs, а не рукописный список", differ=True)

    # ②-обратный: id подменён константой — запрос перестаёт зависеть от данных стенда
    broken2_text = patched(
        "        ident = extract_first_id(payload) if payload is not None else None",
        "        ident = 1  # ПОЛОМКА: id — константа, не из ответа списка")
    if broken2_text is None:
        ok &= case("②-обратный: якорь id не найден — приёмка не запустилась", False,
                   "⛔ строка изменилась — правь приёмку")
    else:
        broken2_tool = materialize(root, "broken-id", broken2_text)
        srv, api = start_stub(str(db), 777, 888, extra_no_lists)
        code2_b, out2_b = run_check(broken2_tool, root, api, db, api_source=fixture_base)
        log2_b = list(StubApi.log)
        srv.shutdown()
        ok &= case("②-обратный: id-константа → запрос НЕ доезжает до живого id стенда",
                   "/api/tasks/777" not in log2_b and "/api/tasks/1" in log2_b,
                   f"сломанная зовёт {[p for p in log2_b if p.startswith('/api/tasks/')]} "
                   "вместо /api/tasks/777 — разница доказывает, что именно ЖИВОЙ id "
                   "различает случай ②", differ=True)

    # ③-обратный: строка «недоступен» подавлена — молчание вместо честного отказа
    broken3_text = patched(
        '        print("⚪ перечень маршрутов службы недоступен — покрытие не судится")',
        "        pass  # ПОЛОМКА: строка скрыта")
    if broken3_text is None:
        ok &= case("③-обратный: якорь строки «недоступен» не найден — приёмка не запустилась",
                   False, "⛔ строка изменилась — правь приёмку")
    else:
        broken3_tool = materialize(root, "broken-note", broken3_text)
        srv, api = start_stub(str(db), 111, 222, set(KNOWN_STATIC) - {"/api/health"})
        code3_b, out3_b = run_check(broken3_tool, root, api, db, api_source=missing_source)
        srv.shutdown()
        ok &= case("③-обратный: строка «недоступен» подавлена → молчание об источнике",
                   "покрытие не судится" not in out3_b,
                   f"сломанная {code3_b}, строки о недоступности источника в выводе НЕТ — "
                   "разница доказывает, что именно эта строка честно предупреждает",
                   differ=True)

    # ④-обратный: раскладка ② (через mezo_paths.template_root) вырезана — MEZO_TEMPLATE
    # больше не помогает, копия снова «не судится» даже когда образец назван явно.
    broken4_text = patched(
        '    try:\n'
        '        template = mezo_paths.template_root(script_file)\n'
        '    except SystemExit:\n'
        '        return None\n'
        '    candidate = template / "src" / "Gordi.Periscope.Api" / "Endpoints" / "ApiEndpoints.cs"\n'
        '    return candidate if candidate.exists() else None',
        '    return None  # ПОЛОМКА: раскладка через mezo_paths.template_root вырезана')
    if broken4_text is None:
        ok &= case("④-обратный: якорь раскладки через mezo_paths не найден — приёмка не запустилась",
                   False, "⛔ строка изменилась — правь приёмку")
    else:
        broken4_tool = materialize(root, "broken-template", broken4_text)
        srv, api = start_stub(str(db), 111, 222, extra_no_lists)
        code4_b, out4_b = run_check(broken4_tool, root, api, db,
                                    extra_env={"MEZO_TEMPLATE": str(template_pkg)})
        srv.shutdown()
        ok &= case("④-обратный: раскладка через mezo_paths вырезана → MEZO_TEMPLATE больше не помогает",
                   code4_b == 0 and "покрытие не судится" in out4_b and "обойдено" not in out4_b,
                   f"сломанная {code4_b} (настоящая ④б была {code4b}) — разница доказывает, "
                   "что именно раскладка через mezo_paths.template_root даёт покрытие "
                   "без --api-source", differ=True)

    print()
    print(f"{'✅ ПОКРЫТИЕ МАРШРУТОВ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
