"""
bite-shown-count.py — укус на правку ② : журнал выдач помнит, СКОЛЬКО ПОКАЗАЛ.

═══ ЗАЧЕМ ЭТО ПОЛЕ ═══
06.08 читалка показала мне 12 записок и отметила прочитанными 40. Расхождение существовало
ТОЛЬКО в моих глазах: `read_batches` хранит `token · role · last_id · issued_at` — сколько
было ПОКАЗАНО, там нет. Замер Ops/SRE (#3123): проверить остальных восемь ролей нечем,
и после починки читалки мы не узнаем, помогла ли она, — нет ни одного зафиксированного
случая, кроме моего.

Слово владельца: 2026-08-07 10:00 UTC, «даю слово: ① и ② делаем». Рука — координатора.

═══ ДВА СВОЙСТВА, И ВТОРОЕ ВАЖНЕЕ ═══
    ① РАСХОЖДЕНИЕ ВИДНО В БАЗЕ. После перевыдачи с уменьшенным лимитом в журнале
       выдач должно стоять «показано < отмечено». Сегодня этого не видно ничем.
    ② УЛИКА ЖИВЁТ ДОЛЬШЕ СОБЫТИЯ. Сейчас строка СТИРАЕТСЯ при подтверждении — то есть
       ровно в тот момент, когда расхождение и возникает. Добавить поле, оставив
       стирание, значит получить механизм, чья улика короче события: четвёртый такой
       за сутки (запись о выдаче · окно правки инструмента · черновик без провенанса ·
       незакоммиченный файл).
       ⇒ Укус проверяет ОБА. Первое без второго бесполезно: поле будет заполняться
         и исчезать в ту же секунду.

═══ ИМЯ КОЛОНКИ НЕ ЗАШИТО ═══
Как назвать поле — решает координатор. Укус ищет колонку по смыслу среди кандидатов
и печатает, что нашёл. Проверяется СВОЙСТВО, а не чужой выбор имени: укус, требующий
конкретного имени, красил бы верную правку.

Запуск:  python C:/guts/.atlas/vnext-tools/bite-shown-count.py
Выход:   0 — оба свойства держатся · 1 — правки ещё нет · 2 — поле есть, но не спасает
"""

import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

LIVE = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")
SANDBOX = Path.home() / ".mezosync-sandbox" / "bite-shown.db"
READER = Path(r"C:\guts\.atlas\.mezosync\scripts\read-messages.py")
ROLE = "PROTO"
START = 3069           # точка, с которой воспроизводится мой случай 06.08

CANDIDATES = ("shown", "shown_count", "shown_last_id", "shown_max", "batch_max",
              "displayed", "last_shown", "shown_id", "visible_last_id")


def prepare() -> None:
    SANDBOX.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, SANDBOX)
    con = sqlite3.connect(SANDBOX)
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (START, ROLE))
    con.execute("DELETE FROM read_batches WHERE role=?", (ROLE,))
    con.commit()
    con.close()


def columns() -> list:
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    cols = [r[1] for r in con.execute("PRAGMA table_info(read_batches)")]
    con.close()
    return cols


def shown_column(cols: list) -> str | None:
    for c in CANDIDATES:
        if c in cols:
            return c
    return None


def call_reader(*extra) -> str:
    out = subprocess.run([sys.executable, str(READER), "--db", str(SANDBOX),
                          "--role", ROLE, *extra],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def batch_row() -> tuple | None:
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM read_batches WHERE role=? ORDER BY rowid DESC LIMIT 1",
                      (ROLE,)).fetchone()
    con.close()
    return dict(row) if row else None


def shown_ids(text: str) -> list:
    return [int(x) for x in re.findall(r"^--- #(\d+) \[", text, re.M)]


def parse_token(text: str):
    a = re.search(r"ПЕРВАЯ половина ([0-9a-f]{6})", text)
    b = re.search(r"--ack\s+<первая>-([0-9a-f]{6})", text)
    return (a.group(1), b.group(1)) if (a and b) else None


def main() -> int:
    print("УКУС ②: журнал выдач помнит, сколько показал")
    print(f"копия базы ..... {SANDBOX}\n")
    prepare()

    cols = columns()
    col = shown_column(cols)
    print(f"колонки журнала выдач: {cols}")
    if col:
        print(f"колонка «показано» .... найдена: {col!r}\n")
    else:
        print("колонка «показано» .... 🔴 НЕ НАЙДЕНА (искал среди "
              f"{', '.join(CANDIDATES[:5])} …)\n")

    # ── воспроизводим мой случай: большая выдача, затем УМЕНЬШЕННЫЙ лимит
    call_reader("--limit", "40")
    small = call_reader("--limit", "12")
    ids = shown_ids(small)
    row = batch_row()
    print(f"① выдано 40, затем показано {len(ids)} (до #{max(ids)})")
    print(f"   строка журнала: {row}")

    visible = False
    if col and row:
        visible = row.get(col) is not None and row[col] < row["last_id"]
        print(f"   расхождение в базе: показано {row.get(col)} < отмечено {row['last_id']}"
              f"   {'✅ ВИДНО' if visible else '🔴 не видно'}")
    else:
        print("   расхождение в базе: 🔴 НЕ ВИДНО НИЧЕМ — хранится только отметка")

    # ── ② улика переживает подтверждение
    token = parse_token(small)
    survives = False
    if token:
        call_reader("--ack", f"{token[0]}-{token[1]}")
        after = batch_row()
        survives = after is not None
        print(f"\n② после подтверждения строка журнала: "
              f"{'ЖИВА ✅' if survives else 'СТЁРТА 🔴'}")
        if not survives:
            print("   ⇒ улика исчезает в тот же момент, когда расхождение возникает.")
            print("     Поле, стираемое вместе со строкой, не даст проверить починку")

    # ── различающий случай: без уменьшения лимита расхождения быть не должно
    print("\nРАЗЛИЧАЮЩИЙ СЛУЧАЙ: лимит НЕ уменьшается")
    prepare()
    a = call_reader("--limit", "12")
    ids_a, row_a = shown_ids(a), batch_row()
    clean = True
    if col and row_a and row_a.get(col) is not None:
        clean = row_a[col] == row_a["last_id"]
        print(f"   показано {row_a[col]} · отмечено {row_a['last_id']}   "
              f"{'✅ совпадает' if clean else '🔴 расходится там, где не должно'}")
    else:
        print(f"   показано {len(ids_a)} записок, поля «показано» нет — сравнить нечем")

    # ── ИТОГ ────────────────────────────────────────────────────────────
    print("\nСВОЙСТВА: ① расхождение показано/отмечено видно В БАЗЕ")
    print("          ② улика переживает подтверждение")
    if not col:
        print("\nИТОГ: ⏳ правки ещё нет. Укус исправен: он воспроизводит случай"
              " (показано 12, отмечено 40) и показывает, что в базе следа не остаётся")
        return 1
    if not (visible and survives and clean):
        print("\nИТОГ: 🔴 ПОЛЕ ЕСТЬ, НО НЕ СПАСАЕТ — "
              f"видно={visible} · переживает={survives} · чисто={clean}")
        return 2
    print("\nИТОГ: ✅ ОБА СВОЙСТВА ДЕРЖАТСЯ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
