# -*- coding: utf-8 -*-
r"""ПРИЁМКА трёх исходов проверки режима «только чтение» — карточка #247.

🩸 ЧЕМ ОПЛАЧЕНО (контур tapas, воспроизведено @COORD 23.08). Два дефекта одного корня:
```
① их служба не поднялась («порт занят»), на запрос здоровья ответила НАША —
  и проверка честно доказала read-only ЧУЖОЙ базы. Путь ПЕЧАТАЛСЯ первой строкой,
  его видели и всё равно ошиблись: напечатать ≠ проверить
② «службы нет» падало трассировкой в 40 строк с КОДОМ 1 — тем же, что настоящая
  находка: «не смогла проверить» было слито с «опровергнуто»
```

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① подставная служба, база совпадает, замки целы → 0 «доказано»           РАЗЛИЧАЮЩИЙ
  ② та же служба, ожидание — ДРУГАЯ база → 2, обе стороны названы          РАЗЛИЧАЮЩИЙ
  ③ службы нет вовсе → 2, человеческая строка, БЕЗ трассировки            РАЗЛИЧАЮЩИЙ
  ④ замок снят (readOnly=false) → 1 «ОПРОВЕРГНУТО» — код ИНОЙ, чем у ②③   РАЗЛИЧАЮЩИЙ
  ⑤ ОБРАТНЫЙ ХОД: сверка баз ослаблена → случай ② зеленеет у сломанной    РАЗЛИЧАЮЩИЙ

🎯 ④ — сердце различения: «не смогла проверить» (2) и «опровергнуто» (1) обязаны
нести РАЗНЫЕ коды, иначе зовущий в связке не отличит сломанный замок от занятого порта.
⚖️ Подставная служба здесь — не подмена предмета: испытывается ПРОВЕРКА (её исходы),
а не служба. Живая служба проверена отдельно, двумя прогонами по критерию ③ карточки.

⛔ Живой базы не пишет: подставная служба отдаёт пути СВОИХ копий.

⬆️ ДОПИСАНО 15.09, возврат владельца по карточке #646. Правка карточки #646 научила
check-viewer-readonly.py САМ разбирать перечень маршрутов из ApiEndpoints.cs (по
умолчанию, без --api-source) — и из клона пакета GORDI этот разбор ТЕПЕРЬ УДАЁТСЯ
(служба лежит рядом), а здешняя подставная служба (StubService) отвечает на любой
путь голым `[]`: для двух маршрутов с {id} (tasks/{id}, messages/{id}) это честное
«нет данных» по новой логике — и красит прогон ЭТОЙ приёмки, хотя её предмет (три
исхода health-замера) тут ни при чём. Выбор (не первый из предложенных владельцем):
подставная служба НЕ учится отвечать на списки/id-маршруты чужого предмета
(это раздуло бы её знанием внутренностей check-viewer-readonly.py, которых у неё
нет причины знать, и снова сломалось бы при следующей правке ApiEndpoints.cs) —
вместо этого КАЖДЫЙ прогон здесь явно просит check-viewer-readonly.py режим
«покрытие не судится» (`--api-source` на заведомо несуществующий путь). Так
приёмка судит РОВНО свой предмет (health/db/три исхода) и не зависит от того,
откуда её запустили — из дерева контура или из клона пакета.
"""
from __future__ import annotations

import http.server
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

TOOL = pathlib.Path(__file__).with_name("check-viewer-readonly.py")
CASES = DIFFER = 0
# Имя заведомо несуществующего файла — просит check-viewer-readonly.py режим
# «покрытие не судится», чтобы приёмка не зависела от того, находит ли разбор
# ApiEndpoints.cs (это НЕ её предмет — см. дописку 15.09 в шапке).
NO_SUCH_SOURCE_NAME = "no-such-source.cs"


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def make_mini_db(work_dir: pathlib.Path, name: str) -> pathlib.Path:
    db = work_dir / name
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()
    return db


class StubService(http.server.BaseHTTPRequestHandler):
    """Служба-стенд: health с заданными полями, 200 на остальные точки."""
    db_path = ""
    read_only = True

    def do_GET(self):  # noqa: N802 — имя диктует базовый класс
        if self.path == "/api/health":
            body = json.dumps({"status": "ok", "activeDbPath": self.db_path,
                               "readOnly": self.read_only}).encode()
        else:
            body = b"[]"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # тишина: журнал стенда — шум приёмки
        pass


def start_stub(db_path: str, read_only: bool):
    StubService.db_path = db_path
    StubService.read_only = read_only
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StubService)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def run_check(work_dir: pathlib.Path, api: str, *extra_args):
    """Прогон check-viewer-readonly.py — ВСЕГДА с `--api-source` на заведомо
    несуществующий путь: этой приёмке нужен режим «покрытие не судится» (её предмет —
    три исхода health/db-замера, не перечень маршрутов службы — см. шапку файла),
    и `env=mezo_stand.stand_env(...)`, чтобы не унести чужой MEZO_CONTAINER/
    MEZO_TEMPLATE вызывающего в испытуемый процесс (карточка #613)."""
    no_such_source = work_dir / NO_SUCH_SOURCE_NAME
    args = [sys.executable, str(TOOL), "--api", api,
            "--api-source", str(no_such_source), *extra_args]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, env=mezo_stand.stand_env(work_dir))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    work_dir = pathlib.Path(tempfile.mkdtemp(prefix="bite-viewer-"))
    try:
        own_db = make_mini_db(work_dir, "own.db")
        other_db = make_mini_db(work_dir, "other.db")

        # ① доказано: база совпадает, замки целы
        srv, api = start_stub(str(own_db), True)
        code1, out1 = run_check(work_dir, api, "--expect-db", str(own_db))
        srv.shutdown()
        ok &= case("① база совпадает, замки целы → 0 «доказано»",
                   code1 == 0 and "доказан" in out1,
                   f"код {code1}", differ=True)

        # ② ожидание — другая база: код 2, обе названы
        srv, api = start_stub(str(own_db), True)
        code2, out2 = run_check(work_dir, api, "--expect-db", str(other_db))
        srv.shutdown()
        ok &= case("② служба держит НЕ ТУ базу → 2, обе стороны названы",
                   code2 == 2 and "own.db" in out2 and "other.db" in out2,
                   f"код {code2}; ровно здесь соседи «доказали» чужой предмет — теперь"
                   " сверка машиной, а не глазом", differ=True)

        # ③ службы нет: код 2, человеческая строка, без трассировки
        code3, out3 = run_check(work_dir, "http://127.0.0.1:59987")
        ok &= case("③ службы нет → 2, человеческая строка, БЕЗ трассировки",
                   code3 == 2 and "не ответила" in out3 and "Traceback" not in out3,
                   f"код {code3}; прежде здесь было 40 строк трассировки с кодом находки",
                   differ=True)

        # ④ замок снят: код 1 — ИНОЙ, чем у ②③
        srv, api = start_stub(str(own_db), False)
        code4, out4 = run_check(work_dir, api, "--expect-db", str(own_db))
        srv.shutdown()
        ok &= case("④ замок снят (readOnly=false) → 1 «ОПРОВЕРГНУТО», код иной, чем 2",
                   code4 == 1 and code4 != code2 and "ЗАМОК СНЯТ" in out4,
                   f"код {code4} против {code2} у «не смогла» — зовущий в связке различает"
                   " сломанный замок и занятый порт", differ=True)

        # ⑤ ОБРАТНЫЙ ХОД: сверка ослаблена → случай ② зеленеет у сломанной копии
        live_text = TOOL.read_text(encoding="utf-8")
        broken_text = live_text.replace(
            "if normalized_path(db) != normalized_path(expected):",
            "if False:", 1)
        if broken_text == live_text:
            ok &= case("⑤ ОБРАТНЫЙ ХОД: сверка ослаблена — случай ② зеленеет", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: места сверки в проверке нет — она менялась,"
                       " правь приёмку")
        else:
            weak_tool = work_dir / "weak.py"
            weak_tool.write_text(broken_text, encoding="utf-8")
            for neighbour in mezo_stand.neighbours_of(TOOL):
                shutil.copy2(neighbour, work_dir / neighbour.name)
            srv, api = start_stub(str(own_db), True)
            no_such_source = work_dir / NO_SUCH_SOURCE_NAME
            r = subprocess.run([sys.executable, str(weak_tool), "--api", api,
                                "--expect-db", str(other_db),
                                "--api-source", str(no_such_source)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=300,
                               env=mezo_stand.stand_env(work_dir))
            srv.shutdown()
            ok &= case("⑤ ОБРАТНЫЙ ХОД: сверка ослаблена — случай ② ЗЕЛЕНЕЕТ у сломанной",
                       r.returncode == 0 and code2 == 2,
                       f"слабая {r.returncode} против настоящей {code2} — разница и есть"
                       " доказательство, что различает именно СВЕРКА", differ=True)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)

    print()
    print(f"{'✅ ТРИ ИСХОДА ПРИНЯТЫ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
