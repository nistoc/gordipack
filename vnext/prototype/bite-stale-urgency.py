r"""
bite-stale-urgency.py — проверка проверки «срочность горит, а вопрос закрыт».

Число «49 горящих с ответом» стоит ровно столько, сколько доказано про сам счётчик.
Здесь доказывается ЧЕТЫРЬМЯ случаями на КОПИИ живой базы, два из них встречные:

    ① срочная + есть ответ в треде ....... ОБЯЗАНА попасть в список
    ② срочная БЕЗ ответа ................. НЕ попадает            [встречный]
    ③ НЕ срочная + есть ответ ............ НЕ попадает            [встречный]
    ④ срочная + ответ + помечена снятой .. НЕ попадает            [встречный]

Без ② проверка ловила бы «все срочные подряд» и выглядела бы работающей.
Без ③ она ловила бы «всё, на что ответили», и слово «срочность» в её имени было бы ложью.
Без ④ она спорила бы с уже принятым решением человека.

ЗАПУСК: python bite-stale-urgency.py
ВЫХОД:  0 — все четыре · 1 — есть провал
"""

import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).with_name("check-stale-urgency.py")
LIVE = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")


def run(db: Path) -> tuple:
    # --all обязателен: без него приёмка читала бы УСЕЧЁННЫЙ список и приняла бы
    # «не показано» за «не найдено». Именно так первый прогон и соврал.
    r = subprocess.run([sys.executable, str(TOOL), "--db", str(db), "--all"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    listed = {int(x) for x in re.findall(r"записка #(\d+)", r.stdout)}
    return r.returncode, listed, r.stdout


def main() -> int:
    if not LIVE.exists():
        print("⛔ живой базы нет — не на чем проверять")
        return 1
    tmp = Path(tempfile.mkdtemp(prefix="bite-urgency-"))
    try:
        db = tmp / "copy.db"
        shutil.copy2(LIVE, db)
        con = sqlite3.connect(db)

        # Четыре искусственные записки + ответы к ним. Строим состояние сами,
        # чтобы ответ был известен ДО прогона, а не вычитан из его же вывода.
        base = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
        ids = {}
        cases = [
            ("срочная с ответом", "critical", True, 0),
            ("срочная без ответа", "critical", False, 0),
            ("обычная с ответом", "normal", True, 0),
            ("срочная с ответом, снятая", "high", True, 1),
        ]
        for name, prio, answered, resolved in cases:
            cur = con.execute(
                "INSERT INTO messages (writer_role, timestamp, body_md, priority, resolved,"
                " broadcast, addressed_by) VALUES (?, datetime('now','-2 days'), ?, ?, ?, 0, 'unset')",
                ("PROTO", f"ОБРАЗЕЦ ПРИЁМКИ: {name}", prio, resolved))
            ids[name] = cur.lastrowid
            if answered:
                a = con.execute(
                    "INSERT INTO messages (writer_role, timestamp, body_md, priority, resolved,"
                    " broadcast, addressed_by) VALUES (?, datetime('now','-1 days'), ?, 'normal',"
                    " 0, 0, 'unset')", ("COORD", f"ОТВЕТ на образец: {name}")).lastrowid
                con.execute("INSERT INTO message_thread (message_id, reply_to, thread_id, kind,"
                            " linked_by) VALUES (?, ?, ?, 'answer', 'field')",
                            (a, ids[name], ids[name]))
        con.commit()
        con.close()

        code, listed, out = run(db)
        print("ПРИЁМКА: проверка «срочность горит, а вопрос закрыт»")
        print(f"  образцы заведены на копии, id от {base + 1}\n")

        expect = {
            "срочная с ответом": True,
            "срочная без ответа": False,
            "обычная с ответом": False,
            "срочная с ответом, снятая": False,
        }
        fails = []
        for name, want in expect.items():
            got = ids[name] in listed
            ok = got == want
            mark = "[встречный]" if not want else ""
            print(f"   {'✅' if ok else '🔴'} {name:28} "
                  f"{'в списке' if got else 'не в списке':12} {mark}")
            if not ok:
                fails.append(name)

        print("\n   ⑤ печатает ли проверка СВОЙ ПОТОЛОК (сколько ответов ей не видно)")
        ceiling = "ЧЕГО ЭТА ПРОВЕРКА НЕ ВИДИТ" in out
        print(f"   {'✅ печатает' if ceiling else '🔴 МОЛЧИТ О СВОЁМ ПОТОЛКЕ'}")
        if not ceiling:
            fails.append("потолок не назван")

        if fails:
            print(f"\nИТОГ: 🔴 ПРОВАЛ — {', '.join(fails)}")
            return 1
        print("\nИТОГ: ✅ ЛОВИТ ТОЛЬКО СРОЧНОЕ С ОТВЕТОМ И НЕ ТРОГАЕТ ОСТАЛЬНОЕ")
        print("      Три встречных случая доказывают, что она мерит именно это свойство,")
        print("      а не «все срочные» и не «всё, на что ответили».")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
