# -*- coding: utf-8 -*-
"""
cursor-advance.py — курьерский курсор (Э-З): сдвиг БЕЗ чтения, но только ЗАЯВЛЕННЫЙ.

⛔ ПРОТОТИП. Пишет только в песочницу/демо-БД по схеме v-next. Живую mezosync.db не
   открывает вовсе (этот инструмент ПИШЕТ — сюда допуск --live-readonly не относится).

ЗАЧЕМ (оплачено дважды в один день, 2026-08-05):
  · @RCC #2897/#2898: 692 ноты ≈ 83 окна вывода. Честный путь «дочитать» НЕ дорог —
    он непроходим. Позеленеть можно было ровно одним действием: соврать `ack`.
    Его формула: «если честный путь НЕВОЗМОЖЕН, а нечестный зеленит гард, роль выберет
    ложный ack. Молчание хотя бы видно как молчание — ложный ack неотличим от работы.»
  · AIA (дельта §5.1): курсор врал о 3436 нотах, три инкарнации подряд не двигали его.
    Ввели `--advance-to --basis`. Их вывод, который я забираю дословно: **перед введением
    требования проверить, что его можно выполнить, не платя дороже, чем оно стоит.**

ЧТО ЗДЕСЬ СВЕРХ ИХ РЕШЕНИЯ:
  сегменты вместо поля (см. schema_vnext.sql ⑨) ⇒ основание не затирается следующим
  честным чтением, и «видела ли роль ноту N» отвечается ВСЕГДА, а не до ближайшего ack.

ОТКАЗЫ (три от AIA + два моих):
  ① без основания .............. отказ  (их)
  ② назад ...................... отказ  (их: «стирание факта чтения»)
  ③ за горизонт ленты .......... отказ  (их)
  ④ перекрытие сегментов ....... отказ  (мой: иначе одна нота и «прочитана», и «заявлена»)
  ⑤ дыра между сегментами ...... отказ  (мой: молчаливый пропуск — то самое, что лечим)

    python cursor-advance.py --db <demo.db> --role RCC --to 2896 \
        --basis "сводка COORD за 7 недель дормана вместо ленты" --authorized owner --note 2898
    python cursor-advance.py --db <demo.db> --role RCC --show
"""
import argparse
import sqlite3
import sys
from pathlib import Path

LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")


def connect(db: str) -> sqlite3.Connection:
    p = Path(db)
    if p.resolve() == LIVE_DB.resolve():
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Инструмент ПИШЕТ — к живому контуру не "
                 "допускается ни под каким флагом. Мандат PROTO: живой субстрат — только чтение.")
    if not p.exists():
        sys.exit(f"ERR: БД не найдена: {p}")
    con = sqlite3.connect(str(p))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def current(con, role):
    r = con.execute("SELECT COALESCE(MAX(to_id), 0) FROM cursor_segments WHERE role = ?",
                    (role,)).fetchone()
    return r[0]


def head(con):
    r = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()
    return r[0]


def advance(con, role, to_id, kind, basis=None, authorized=None, note_id=None):
    """Возвращает (ok: bool, message: str). Все отказы — ДО записи, ни одной частичной."""
    cur = current(con, role)
    lo = cur + 1

    # ① основание обязательно для заявленного сдвига
    if kind == "declared" and not (basis and authorized):
        return False, ("⛔ ОТКАЗ ①: заявленный сдвиг без основания или без авторизации. "
                       "Сдвиг без чтения разрешён, но НЕ молча — назови --basis и --authorized.")
    # ② назад
    if to_id <= cur:
        return False, (f"⛔ ОТКАЗ ②: назад ({cur} → {to_id}). Это стирание факта чтения: "
                       f"участок уже пройден и его способ прохождения записан.")
    # ③ за горизонт ленты
    h = head(con)
    if to_id > h:
        return False, (f"⛔ ОТКАЗ ③: за горизонт ленты (голова #{h}, просят {to_id}). "
                       f"Курсор не может знать про ноты, которых нет.")
    # ④ перекрытие
    ov = con.execute("SELECT id, from_id, to_id, kind FROM cursor_segments "
                     "WHERE role = ? AND NOT (to_id < ? OR from_id > ?)",
                     (role, lo, to_id)).fetchone()
    if ov:
        return False, (f"⛔ ОТКАЗ ④: перекрытие с сегментом #{ov[0]} [{ov[1]}..{ov[2]}, {ov[3]}]. "
                       f"Одна нота не может быть и прочитанной, и заявленной.")
    # ⑤ дыра
    if lo > to_id:
        return False, "⛔ ОТКАЗ ⑤: пустой интервал."

    con.execute("INSERT INTO cursor_segments (role, from_id, to_id, kind, basis, authorized, "
                "note_id) VALUES (?,?,?,?,?,?,?)",
                (role, lo, to_id, kind, basis, authorized, note_id))
    con.commit()
    n = to_id - lo + 1
    word = "ПРОЧИТАНО" if kind == "read" else "ЗАЯВЛЕНО (не читано)"
    return True, f"✅ {role}: [{lo}..{to_id}] {n} нот — {word}"


def show(con, role):
    rows = con.execute("SELECT from_id, to_id, kind, basis, authorized, note_id, at "
                       "FROM cursor_segments WHERE role = ? ORDER BY from_id",
                       (role,)).fetchall()
    if not rows:
        print(f"[{role}] сегментов нет — лента не пройдена ни глазами, ни заявлением.")
        return
    t = con.execute("SELECT cursor_at, notes_read, notes_declared, segments "
                    "FROM cursor_truth WHERE role = ?", (role,)).fetchone()
    print(f"[{role}] курсор #{t[0]} — но это НЕ «прочитано {t[0]} нот»:")
    print(f"   глазами ..... {t[1] or 0}")
    print(f"   заявлением .. {t[2] or 0}   ⇐ эти НЕ читаны, и это записано, а не подразумевается")
    print(f"   сегментов ... {t[3]}")
    print()
    for f, t2, kind, basis, auth, nid, at in rows:
        mark = "👁 " if kind == "read" else "📄"
        line = f"   {mark} [{f}..{t2}] {t2-f+1:5d} нот  {at[:16]}"
        if kind == "declared":
            line += f"\n        основание: {basis}\n        разрешил: {auth}" + \
                    (f" · нота #{nid}" if nid else "")
        print(line)
    gaps = con.execute("SELECT SUM(to_id - from_id + 1) FROM cursor_gaps WHERE role = ?",
                       (role,)).fetchone()[0]
    if gaps:
        print(f"\n   ⚠️ Писавшим этой роли: {gaps} нот в заявленных участках до неё НЕ ДОШЛИ. "
              f"Нужен ответ — повторите запрос свежей нотой.")


def main():
    ap = argparse.ArgumentParser(description="Курьерский курсор (Э-З)")
    ap.add_argument("--db", required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--to", type=int)
    ap.add_argument("--kind", choices=("read", "declared"), default="declared")
    ap.add_argument("--basis")
    ap.add_argument("--authorized", help="'owner' или роль, давшая основание")
    ap.add_argument("--note", type=int, help="id ноты, где основание объявлено")
    ap.add_argument("--show", action="store_true")
    args = ap.parse_args()

    con = connect(args.db)
    role = args.role.upper()
    if args.show or args.to is None:
        show(con, role)
        return
    ok, msg = advance(con, role, args.to, args.kind, args.basis, args.authorized, args.note)
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
