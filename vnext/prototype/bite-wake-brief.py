# -*- coding: utf-8 -*-
r"""ПРИЁМКА обзора пробуждения (--wake) — карточка #258, вторая половина.

🩸 ЧЕМ ОПЛАЧЕНО (замер 26.08): пробуждение роли читало ТЕЛА всего долга. У @RCC это
4942 КБ ≈ 1.2 млн токенов — БОЛЬШЕ ЛЮБОГО ОКНА: пробуждение было невыполнимо, и роль
узнавала об этом, уже начав читать.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① обзор показывает ОБЕ половины: тела обращённого лично И указатель остального  РАЗЛИЧАЮЩИЙ
  ② отметка прочитанного НЕ двинута — обзор не есть чтение ленты                   РАЗЛИЧАЮЩИЙ
  ③ ключа подтверждения НЕ выдано: нечем случайно объявить ленту прочитанной        РАЗЛИЧАЮЩИЙ
  ④ обзор ДЕШЕВЛЕ тел на роли с долгом — числом, а не обещанием                     РАЗЛИЧАЮЩИЙ
  ⑤ ОБРАТНЫЙ ХОД: выключить вторую половину → указателя в выводе НЕТ                РАЗЛИЧАЮЩИЙ
  ⑥ КОНТРОЛЬ: обычное чтение телами ключ ВЫДАЁТ — значит ③ говорит о режиме,
    а не о том, что ключей не бывает вовсе                                          КОНТРОЛЬ

⛔ Живой базы НЕ ПИШЕТ: работает на копии.
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
ЧИТАТЕЛЬ = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "read-messages.py"
ЖИВАЯ = mezo_paths.live_db()
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def прогон(скрипт, *доводы):
    r = subprocess.run([sys.executable, str(скрипт), *доводы], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def отметка(db, роль):
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    row = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?", (роль,)).fetchone()
    con.close()
    return row[0] if row else None


def с_долгом(db):
    """Роль, у которой долг больше сотни: на пустом долге мерить экономию нечего."""
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    строки = con.execute(
        "SELECT c.reader_role, (SELECT COUNT(*) FROM messages m"
        " WHERE m.id > c.last_read_id"
        "  AND m.writer_role <> c.reader_role) AS n"
        " FROM read_cursors c ORDER BY n DESC LIMIT 1").fetchall()
    con.close()
    return строки[0] if строки else (None, 0)


def main() -> int:
    ok = True
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-wake-"))
    try:
        db = d / "sand.db"
        shutil.copy(ЖИВАЯ, db)
        роль, долг = с_долгом(db)
        if not роль or долг < 20:
            print(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: в копии нет роли с долгом ≥20 (лучшая: "
                  f"{роль} с {долг}). Молчать об этом нельзя — вышло бы зелёное")
            return 2

        было = отметка(db, роль)
        код, вывод = прогон(ЧИТАТЕЛЬ, "--db", str(db), "--role", роль, "--wake")
        стало = отметка(db, роль)

        ok &= case("① обзор показывает ОБЕ половины: тела личного И указатель остального",
                   код == 0 and "ТЕЛА ОБРАЩЁННОГО ЛИЧНО" in вывод
                   and "УКАЗАТЕЛЬ ПО ВСЕМУ ОСТАЛЬНОМУ" in вывод and "📇 УКАЗАТЕЛЬ" in вывод,
                   f"код {код}; роль {роль}, долг {долг}. Одна половина без другой — "
                   f"это не обзор: либо тела без охвата, либо охват без важного", differ=True)

        ok &= case("② отметка прочитанного НЕ двинута",
                   было == стало,
                   f"было {было}, стало {стало} — обзор не есть чтение ленты, и механизм "
                   f"не должен позволять спутать одно с другим", differ=True)

        ok &= case("③ ключа подтверждения НЕ выдано",
                   "--ack" not in вывод and "Токен разрезан" not in вывод,
                   "иначе роль погасила бы долг, увидев ЗАГОЛОВКИ: писавшим было бы "
                   "сказано «дошло» про тела, которых никто не читал", differ=True)

        _, телами = прогон(ЧИТАТЕЛЬ, "--db", str(db), "--role", роль, "--limit", "500")
        a, b = len(телами.encode("utf-8")), len(вывод.encode("utf-8"))
        ok &= case("④ обзор ДЕШЕВЛЕ тел на роли с долгом — числом",
                   b < a and a > 50000,
                   f"телами {a} байт, обзором {b} байт — экономия {100 * (1 - b / a):.0f} %. "
                   f"⚖️ на ПУСТОМ долге обзор дороже, и это названо в его замере", differ=True)

        # ⑤ ОБРАТНЫЙ ХОД: выключаем ВТОРУЮ половину обзора.
        цел = ЧИТАТЕЛЬ.read_text(encoding="utf-8")
        КУСОК = '("УКАЗАТЕЛЬ ПО ВСЕМУ ОСТАЛЬНОМУ ДОЛГУ", ["--index"])'
        if цел.count(КУСОК) != 1:
            ok &= case("⑤ ОБРАТНЫЙ ХОД: выключить вторую половину", False,
                       f"⛔ якорь второй половины найден {цел.count(КУСОК)} раз — "
                       f"ослабление НЕ состоялось, а молчание тут читалось бы как успех",
                       differ=True)
        else:
            слабый = d / "читатель-слабый.py"
            слабый.write_text(цел.replace(КУСОК, '("ВТОРАЯ ПОЛОВИНА ВЫКЛЮЧЕНА ПРИЁМКОЙ", [])'),
                              encoding="utf-8")
            import os
            env = dict(os.environ, PYTHONPATH=str(ЧИТАТЕЛЬ.parent))
            r5 = subprocess.run([sys.executable, str(слабый), "--db", str(db),
                                 "--role", роль, "--wake"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=300, env=env)
            слабый_вывод = (r5.stdout or "") + (r5.stderr or "")
            хвост = слабый_вывод.strip().splitlines()
            ok &= case("⑤ ОБРАТНЫЙ ХОД: вторая половина выключена → указателя в выводе НЕТ",
                       "📇 УКАЗАТЕЛЬ" not in слабый_вывод and "📇 УКАЗАТЕЛЬ" in вывод,
                       f"у ослабленного указателя нет, у целого есть — разница и есть "
                       f"вторая половина. Слабый сказал: "
                       f"{(хвост[0][:70] if хвост else '(молча)')}", differ=True)

        код6, вывод6 = прогон(ЧИТАТЕЛЬ, "--db", str(db), "--role", роль, "--limit", "3")
        ok &= case("⑥ КОНТРОЛЬ: обычное чтение телами ключ ВЫДАЁТ",
                   "--ack" in вывод6,
                   "без этого случая ③ мог бы зеленеть просто оттого, что ключей "
                   "не бывает вовсе — а он про РЕЖИМ, а не про механизм")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ ОБЗОР ПРОБУЖДЕНИЯ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
