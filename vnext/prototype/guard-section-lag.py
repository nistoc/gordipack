# -*- coding: utf-8 -*-
"""guard-section-lag.py — признак «секция слепка отстала от собственной работы роли».

ОТКУДА ВЗЯЛСЯ. Предложен @opssre (#3043) после того, как контур за час поймал троих подряд:
у одной роли работа лежала на диске без записи, у второй — девять правок безопасности мимо
слепка, у третьей план не правился ДЕСЯТЬ СУТОК. Цепочка сработала на трёх случайностях,
а не на механизме.

🔴 ГЛАВНОЕ, И ЭТО ЗАМЕР, А НЕ ПРЕДПОЛОЖЕНИЕ (2026-08-06 17:01 UTC):
   Признак свежести слепков в общем прогоне УЖЕ ЕСТЬ — и он слеп к этому случаю по построению.
   Он берёт `MAX(saved_at)` ПО ВСЕЙ РОЛИ, поэтому сохранение ОДНОЙ секции гасит его для ВСЕХ:
       гард показывает +0 ч ....... у четырёх ролей
       план на самом деле ......... +18 ч · +247 ч · +228 ч · +19 ч
   ⇒ Это не «признака нет», а **признак, ослепший через агрегацию**: он отработал и честно
     вернул «чисто» по той величине, которую видел. Родня класса «проверка, ослепшая на части
     входа, зелена так же, как ничего не нашедшая» (свод §7.5).

⚠️ ПОЧЕМУ НЕ ВСЕ СЕКЦИИ РАВНЫ — иначе признак станет фоном за сутки.
   Секции живут в РАЗНОМ темпе по своей природе, и мерить их одной меркой значит красить
   вечно. Замер по себе 17:03: state и plan свежие, а identity/history/launcher/rebirth/sources —
   246–270 часов, и это НОРМА: они меняются при смене устройства работы, а не при каждой смене.
       state · plan ........ БЫСТРЫЕ. Обязаны следовать за работой ⇒ проверяются здесь
       rebirth · launcher .. ИСПОЛНЯЕМЫЕ. Их протухание ловит другой признак —
                             guard-stale-commands (команда старше правки инструмента)
       identity · history .. МЕДЛЕННЫЕ по природе. По времени не проверяются вовсе

    python guard-section-lag.py                 # весь контур
    python guard-section-lag.py --role PROTO
    python guard-section-lag.py --selftest
"""
import argparse
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

DB = mezo_paths.live_db()

# Порог взят у существующего гарда свежести (3 ч, обоснование его автора: роль пишет ноты чаще,
# чем сохраняется, и это нормально). Не изобретаю свой — два разных порога на один предмет
# разойдутся, и объяснять расхождение будет нечем.
LAG_HOURS = 3
FAST_SECTIONS = ("state", "plan")


def measure(con, role=None):
    """Возвращает список (роль, секция, saved_at, последняя нота, отставание в часах).

    Сравниваем с ПОСЛЕДНЕЙ НОТОЙ роли, а не с текущим временем: роль в дормане молчит
    по слову владельца, её слепок совпал с её работой и честен. Уснувшую роль будить нечем.
    """
    q = "SELECT DISTINCT role FROM phoenix"
    args = []
    if role:
        q += " WHERE UPPER(role) = UPPER(?)"
        args.append(role)
    out = []
    for (r,) in con.execute(q, args):
        note = con.execute(
            "SELECT MAX(timestamp) FROM messages WHERE UPPER(writer_role) = UPPER(?)",
            (r,)).fetchone()[0]
        if not note:
            continue
        for sec in FAST_SECTIONS:
            row = con.execute("SELECT saved_at FROM phoenix WHERE role = ? AND section = ?",
                              (r, sec)).fetchone()
            if not row or not row[0]:
                out.append((r, sec, None, note, None))   # секции нет — отдельный случай
                continue
            lag = con.execute("SELECT (julianday(?) - julianday(?)) * 24",
                              (note, row[0])).fetchone()[0]
            out.append((r, sec, row[0], note, lag))
    return out


def run(role=None, db_path=DB):
    p = Path(db_path)
    if not p.exists():
        print(f"⛔ ОТКАЗ: базы нет — {p}")
        return 2
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    rows = measure(con, role)
    con.close()

    if not rows:
        print(f"⛔ ОТКАЗ: слепков не найдено ({'роль ' + role if role else 'все роли'}). "
              f"Отсутствие данных — отказ, а не зелёное.")
        return 2

    missing = [x for x in rows if x[2] is None]
    lagging = [x for x in rows if x[4] is not None and x[4] > LAG_HOURS]

    print(f"📏 охват: проверено {len(rows)} секций "
          f"({', '.join(FAST_SECTIONS)}) у {len(set(x[0] for x in rows))} ролей · порог {LAG_HOURS} ч")
    print(f"   ⚠️ НЕ проверяются: identity, history — медленные по природе; "
          f"rebirth, launcher — их протухание ловит guard-stale-commands")
    print(f"   отставание считается от ПОСЛЕДНЕЙ НОТЫ роли, а не от текущего времени: "
          f"роль в дормане молчит по слову владельца и её слепок честен")

    if missing:
        print(f"\n🔴 {len(missing)}: секции НЕТ ВООБЩЕ")
        for r, sec, _, _, _ in sorted(missing):
            print(f"   {r} · {sec}")

    if not lagging:
        print(f"\n✅ секций, отставших от собственной работы роли, не найдено "
              f"(ВЫПОЛНЕНО {len(rows)} проверок)")
        return 1 if missing else 0

    print(f"\n🔴 {len(lagging)}: секция отстала от того, что роль успела сделать")
    print("   Это РЕЛЯЦИЯ, а не приговор: роль пишет ноты чаще, чем сохраняется. Но секция,")
    print("   отставшая на смену работы, воскресит роль в состояние, которого уже нет.")
    for r, sec, saved, note, lag in sorted(lagging, key=lambda x: -x[4]):
        print(f"\n   [{r} · {sec}]  отставание {lag:.0f} ч")
        print(f"      секция сохранена: {saved} UTC")
        print(f"      последняя работа: {note} UTC")
    print(f"\nВЫПОЛНЕНО {len(rows)} проверок, красных {len(lagging) + len(missing)}")
    return 1


# ═════════════════════════════════════════════════════════════════════════════

def selftest():
    """🪤 Счёт случаев — норма @STUD: прогон, не назвавший ЧИСЛО выполненных проверок,
    не считается прогоном. Ноль случаев — красный, замаскированный под зелёный."""
    import tempfile
    ok, cases = True, 0

    def db_with(tmp, name, rows_phx, rows_msg):
        p = Path(tmp) / name
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
        con.execute("CREATE TABLE messages (id INTEGER, writer_role TEXT, body_md TEXT, timestamp TEXT)")
        con.executemany("INSERT INTO phoenix VALUES (?,?,'x',?)", rows_phx)
        con.executemany("INSERT INTO messages VALUES (1,?,'x',?)", rows_msg)
        con.commit(); con.close()
        return p

    with tempfile.TemporaryDirectory() as tmp:
        # ① секция отстала на смену работы — обязано краснеть
        print("── ① план отстал на 18 ч ─────────────────────────────────────")
        cases += 1
        p = db_with(tmp, "a.db",
                    [("X", "state", "2026-08-06 16:00:00"), ("X", "plan", "2026-08-05 22:00:00")],
                    [("X", "2026-08-06 16:30:00")])
        if run("X", p) != 1:
            print("🔴 не покраснел на отставшей секции"); ok = False

        # ② РАЗЛИЧАЮЩИЙ: обе секции свежие — обязано молчать. Без этого признак,
        #    красящий всё подряд, прошёл бы ①.
        print("── ② обе секции свежие ───────────────────────────────────────")
        cases += 1
        p = db_with(tmp, "b.db",
                    [("X", "state", "2026-08-06 16:00:00"), ("X", "plan", "2026-08-06 16:10:00")],
                    [("X", "2026-08-06 16:30:00")])
        if run("X", p) != 0:
            print("🔴 краснеет на свежих секциях — ложная тревога"); ok = False

        # ③ РАЗЛИЧАЮЩИЙ, ГЛАВНЫЙ: свежий state НЕ ДОЛЖЕН гасить отставший plan.
        #    Именно этим слеп существующий гард — он берёт MAX по роли.
        print("── ③ свежий state не гасит отставший plan ────────────────────")
        cases += 1
        p = db_with(tmp, "c.db",
                    [("X", "state", "2026-08-06 16:29:00"), ("X", "plan", "2026-07-27 09:00:00")],
                    [("X", "2026-08-06 16:30:00")])
        if run("X", p) != 1:
            print("🔴 свежая секция погасила отставшую — та же слепота, что у прежнего гарда")
            ok = False

        # ④ РАЗЛИЧАЮЩИЙ: дормантная роль молчит — её слепок честен, красить нельзя
        print("── ④ дормант: память старая, но и работы нет ─────────────────")
        cases += 1
        p = db_with(tmp, "d.db",
                    [("X", "state", "2026-07-01 10:00:00"), ("X", "plan", "2026-07-01 10:00:00")],
                    [("X", "2026-07-01 10:05:00")])
        if run("X", p) != 0:
            print("🔴 покраснел на дормантной роли — будить её нечем"); ok = False

        # ⑤ отсутствие данных = ОТКАЗ, а не зелёное
        print("── ⑤ пустая выборка ──────────────────────────────────────────")
        cases += 1
        p = db_with(tmp, "e.db", [], [])
        if run("НЕТ_ТАКОЙ", p) != 2:
            print("🔴 пустая выборка прошла как зелёное"); ok = False

    if cases == 0:
        print("\n⛔ ОТКАЗ: ни одного случая не выполнено — это не «чисто»")
        return 2
    print(f"\n{'✅ САМОПРОВЕРКА ПРОЙДЕНА' if ok else '🔴 САМОПРОВЕРКА ПРОВАЛЕНА'} — "
          f"ВЫПОЛНЕНО {cases} случаев")
    print("   краснеет на отставшей секции · молчит на свежих · СВЕЖАЯ НЕ ГАСИТ ОТСТАВШУЮ · "
          "не будит дормант · на пустоте отказывает")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="раздел памяти отстал от работы роли")
    ap.add_argument("--role")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else run(a.role, a.db))
