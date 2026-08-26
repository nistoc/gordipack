# -*- coding: utf-8 -*-
r"""check-phoenix-invariant.py — ТЕКСТ ПАМЯТИ ПРАВИЛИ МИМО ИНСТРУМЕНТА.

═══ ЗАЧЕМ (карточка #252, применение защиты памяти 24.08) ═══
Защита сохранённой памяти держится на одном условии: НОВЕЙШАЯ версия в истории
каждого раздела дословно равна его текущему телу. Из него следуют три вещи разом:
пустая история значит «механизм не работал», правка мимо инструмента становится
ВИДИМОЙ, приёмке есть что сличать.

🩸 До этой проверки условие печаталось РОВНО ОДИН РАЗ — шагом схемы, в момент
применения. Сегодня оно верно, а о завтрашнем нарушении никто бы не узнал.
Замер путей записи (24.08): их оказалось ТРИ, а не один, как обещал README заявки:
```
save-phoenix.py .... пишет версию                        ✅
init-group.py ...... писал напрямую, версий не клал      ✅ починено 24.08
прямая правка базы . никем не запрещена                  ⛔ ловится ТОЛЬКО этой проверкой
```
Третий путь закрыть нельзя (SQL доступен всем) — его можно только ЗАМЕЧАТЬ.

═══ ЧТО ПРОВЕРЯЕТСЯ ═══
  · новейшая версия каждого раздела равна его телу (сильная форма: не «есть равная
    где-то в истории», а РАВНА ПОСЛЕДНЯЯ — любая штатная запись оставляет ровно это)
  · у раздела есть хотя бы одна версия вовсе (раздел без истории = «родился мимо»)
📏 Замер перед включением (26.08 13:09 UTC, живая база): 63 раздела, 88 версий,
расхождений 0 ⇒ включается зелёной, а не вечно-красной.

⚖️ ЧЕГО НЕ ДЕЛАЕТ: не чинит. Расхождение — предмет РАЗБОРА (кто и зачем правил мимо),
а не автоматического отката: молчаливый откат уничтожил бы именно ту правку, которую
надо разглядеть. Вернуть штатно: save-phoenix.py --history / --restore <id>.

Запуск:  python check-phoenix-invariant.py [--db <копия>]
Выход:   0 — сошлось · 1 — есть расхождения (перечень поимённо) · 2 — мерить нечем
"""
import argparse
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны


def main() -> int:
    ap = argparse.ArgumentParser(description="текст памяти правили мимо инструмента")
    ap.add_argument("--db", default=None, help="иная база — только для проверок на копии")
    a = ap.parse_args()
    db = pathlib.Path(a.db) if a.db else mezo_paths.live_db()
    if not db.exists():
        print(f"⛔ базы нет: {db} — сверять нечем (это НЕ «сошлось»)")
        return 2
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    if not con.execute("SELECT 1 FROM sqlite_master WHERE type='table'"
                       " AND name='phoenix_history'").fetchone():
        # ⛔ Отказ мерить ≠ «чисто»: база до шага схемы историю не ведёт, и говорить
        # про неё «инвариант держится» значило бы выдавать бессилие за исправность.
        print("⛔ таблицы phoenix_history нет — истории не существует, сверять нечем.")
        print("   Прогони migrations/20260823-phoenix-history.py")
        return 2

    битые, без_истории = [], []
    for role, section, body in con.execute("SELECT role, section, body FROM phoenix"):
        row = con.execute(
            "SELECT body, id, saved_at FROM phoenix_history"
            " WHERE role=? AND section=? ORDER BY id DESC LIMIT 1",
            (role, section)).fetchone()
        if row is None:
            без_истории.append((role, section, len(body or "")))
        elif row[0] != (body or ""):
            битые.append((role, section, len(body or ""), len(row[0]), row[1], row[2]))
    con.close()

    if not битые and not без_истории:
        print("✅ память: новейшая версия каждого раздела равна его телу"
              " — правок мимо инструмента нет")
        return 0
    for role, section, тело, верс, vid, ts in битые:
        print(f"🔴 ПРАВКА МИМО ИНСТРУМЕНТА [{role}/{section}]: тело {тело} зн ≠ "
              f"новейшая версия id={vid} ({верс} зн, записана {ts} UTC)")
    for role, section, тело in без_истории:
        print(f"🔴 РАЗДЕЛ БЕЗ ИСТОРИИ [{role}/{section}] ({тело} зн): версий нет вовсе"
              f" — раздел появился мимо инструмента И мимо посева")
    print(f"\n🔴 ИТОГО расхождений {len(битые) + len(без_истории)}."
          f" Это предмет РАЗБОРА, не отката: выясни, кто и зачем правил мимо,"
          f" прежде чем возвращать (save-phoenix.py --history / --restore <id>)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
