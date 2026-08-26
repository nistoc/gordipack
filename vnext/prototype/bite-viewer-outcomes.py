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

ПРОВЕРКА = pathlib.Path(__file__).with_name("check-viewer-readonly.py")
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def мини_база(d: pathlib.Path, имя: str) -> pathlib.Path:
    db = d / имя
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE t (x)")
    con.execute("INSERT INTO t VALUES (1)")
    con.commit()
    con.close()
    return db


class Подставная(http.server.BaseHTTPRequestHandler):
    """Служба-стенд: health с заданными полями, 200 на остальные точки."""
    db_path = ""
    read_only = True

    def do_GET(self):  # noqa: N802 — имя диктует базовый класс
        if self.path == "/api/health":
            тело = json.dumps({"status": "ok", "activeDbPath": self.db_path,
                               "readOnly": self.read_only}).encode()
        else:
            тело = b"[]"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(тело)))
        self.end_headers()
        self.wfile.write(тело)

    def log_message(self, *a):  # тишина: журнал стенда — шум приёмки
        pass


def поднять(db_path: str, read_only: bool):
    Подставная.db_path = db_path
    Подставная.read_only = read_only
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Подставная)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def прогон(api: str, *доводы):
    r = subprocess.run([sys.executable, str(ПРОВЕРКА), "--api", api, *доводы],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-viewer-"))
    try:
        своя = мини_база(d, "своя.db")
        чужая = мини_база(d, "чужая.db")

        # ① доказано: база совпадает, замки целы
        srv, api = поднять(str(своя), True)
        код1, вывод1 = прогон(api, "--expect-db", str(своя))
        srv.shutdown()
        ok &= case("① база совпадает, замки целы → 0 «доказано»",
                   код1 == 0 and "доказан" in вывод1,
                   f"код {код1}", differ=True)

        # ② ожидание — другая база: код 2, обе названы
        srv, api = поднять(str(своя), True)
        код2, вывод2 = прогон(api, "--expect-db", str(чужая))
        srv.shutdown()
        ok &= case("② служба держит НЕ ТУ базу → 2, обе стороны названы",
                   код2 == 2 and "своя.db" in вывод2 and "чужая.db" in вывод2,
                   f"код {код2}; ровно здесь соседи «доказали» чужой предмет — теперь"
                   " сверка машиной, а не глазом", differ=True)

        # ③ службы нет: код 2, человеческая строка, без трассировки
        код3, вывод3 = прогон("http://127.0.0.1:59987")
        ok &= case("③ службы нет → 2, человеческая строка, БЕЗ трассировки",
                   код3 == 2 and "не ответила" in вывод3 and "Traceback" not in вывод3,
                   f"код {код3}; прежде здесь было 40 строк трассировки с кодом находки",
                   differ=True)

        # ④ замок снят: код 1 — ИНОЙ, чем у ②③
        srv, api = поднять(str(своя), False)
        код4, вывод4 = прогон(api, "--expect-db", str(своя))
        srv.shutdown()
        ok &= case("④ замок снят (readOnly=false) → 1 «ОПРОВЕРГНУТО», код иной, чем 2",
                   код4 == 1 and код4 != код2 and "ЗАМОК СНЯТ" in вывод4,
                   f"код {код4} против {код2} у «не смогла» — зовущий в связке различает"
                   " сломанный замок и занятый порт", differ=True)

        # ⑤ ОБРАТНЫЙ ХОД: сверка ослаблена → случай ② зеленеет у сломанной копии
        цел = ПРОВЕРКА.read_text(encoding="utf-8")
        поломка = цел.replace("if нормализованный(db) != нормализованный(ожидание):",
                              "if False:", 1)
        if поломка == цел:
            ok &= case("⑤ ОБРАТНЫЙ ХОД: сверка ослаблена — случай ② зеленеет", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: места сверки в проверке нет — она менялась,"
                       " правь приёмку")
        else:
            слаб = d / "прежняя.py"
            слаб.write_text(поломка, encoding="utf-8")
            shutil.copy(ПРОВЕРКА.with_name("mezo_paths.py"), d / "mezo_paths.py")
            srv, api = поднять(str(своя), True)
            r = subprocess.run([sys.executable, str(слаб), "--api", api,
                                "--expect-db", str(чужая)],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=300)
            srv.shutdown()
            ok &= case("⑤ ОБРАТНЫЙ ХОД: сверка ослаблена — случай ② ЗЕЛЕНЕЕТ у сломанной",
                       r.returncode == 0 and код2 == 2,
                       f"слабая {r.returncode} против настоящей {код2} — разница и есть"
                       " доказательство, что различает именно СВЕРКА", differ=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ ТРИ ИСХОДА ПРИНЯТЫ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
