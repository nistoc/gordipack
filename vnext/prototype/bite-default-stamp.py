"""
bite-default-stamp.py — укус на правку ① : умолчание штампа 'backfill' → 'unset'.

═══ ЧТО ЧИНИТСЯ И ПОЧЕМУ ЭТО МОЙ ДОЛГ ═══
В шаге 002 перевода я поставил пометку происхождения `addressed_by` значением ПО УМОЛЧАНИЮ
равным 'backfill' («перенесено из старого архива»). В результате КАЖДАЯ новая записка,
написанная сегодня, штампуется как перенесённая из архива. На 07.08 таких больше сотни.

Слово владельца на правку: 2026-08-07 10:00 UTC, «даю слово: ① и ② делаем».
Рука — координатора (живая база и рабочие скрипты его зона). Мой вклад — этот укус.

═══ ЧЕГО УКУС НЕ ДЕЛАЕТ (граница названа, чтобы зелёное не читалось шире) ═══
Он проверяет ЗАПИСЬ, а не смысл. 'unset' честнее 'backfill', но имён адресатов
по-прежнему нет ни в одной таблице — сторож `guard-mechanism-unused.py` так и будет
выносить по этой ручке «🔴 ПРИЗНАК БЕЗ ОТВЕТА», и это верно.
⇒ ① чинит ЛОЖЬ О ПРОИСХОЖДЕНИИ, а не мёртвый сосуд. Разные предметы, разная приёмка.

═══ ТРИ СЛУЧАЯ, И ДВА ИЗ НИХ РАЗЛИЧАЮЩИЕ ═══
    ① новая записка без --to      → 'unset'      (это и есть починка)
    ② СТАРЫЕ записки              → 'backfill'   РАЗЛИЧАЮЩИЙ: если правка пройдётся
                                                 по всей таблице, укус покраснеет.
                                                 Без него «зелено» значило бы «поле
                                                 заполнено чем-то», а не «заполнено верно»
    ③ новая записка С --to        → 'field'      РАЗЛИЧАЮЩИЙ: правка не должна съесть
                                                 работающую ветку
Укус зовёт НАСТОЯЩИЙ write-message.py на КОПИИ живой базы. Живая база не касается вовсе.

Запуск:  python <абсолютный путь>/bite-default-stamp.py
Выход:   0 — правка на месте и различает · 1 — правки ещё нет · 2 — правка есть, но ломает
"""

import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_db()
SANDBOX = Path.home() / ".mezosync-sandbox" / "bite-stamp.db"
WRITER = mezo_target.script("write-message.py")
ROLE = "PROTO"


def prepare() -> None:
    SANDBOX.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE, SANDBOX)


def write_note(body: str, *extra) -> int | None:
    """Зовём настоящий инструмент. Возвращаем id записанной записки."""
    out = subprocess.run(
        [sys.executable, str(WRITER), "--db", str(SANDBOX), "--role", ROLE,
         "--body", body, *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        print(f"   ⛔ инструмент отказал: {out.stderr.strip()[:200]}")
        return None
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    last = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    con.close()
    return last


def stamp_of(msg_id: int) -> str | None:
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    row = con.execute("SELECT addressed_by FROM messages WHERE id=?", (msg_id,)).fetchone()
    con.close()
    return row[0] if row else None


def stamps_upto(max_id: int) -> dict:
    """
    Распределение штампов СРЕДИ ЗАПИСОК ДО ГРАНИЦЫ max_id.

    🪤 Граница здесь не украшение — на ней укус уже соврал один раз. Первая версия
    считала штампы по ВСЕЙ таблице до и после, а между замерами сама дописывала
    две записки. Те получили 'backfill' (правки ещё нет), счёт вырос с 1677 до 1678,
    и укус объявил «ИСТОРИЯ ЗАТЁРТА» — при том, что история цела, а лишнюю строку
    добавил он сам.
    ⇒ Класс мой же, шестой за сутки: ИЗМЕРИТЕЛЬ ВКЛЮЧИЛ СЕБЯ В ИЗМЕРЯЕМОЕ.
      Проверка «старое не тронуто» обязана смотреть только на СТАРОЕ, а границу
      старого брать ДО первого своего действия.
    """
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT addressed_by, COUNT(*) FROM messages WHERE id <= ? GROUP BY addressed_by",
        (max_id,)).fetchall()
    con.close()
    return dict(rows)


def max_id_now() -> int:
    con = sqlite3.connect(f"file:{SANDBOX.as_posix()}?mode=ro", uri=True)
    v = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    con.close()
    return v


def main() -> int:
    print("ПРИЁМКА ①: умолчание штампа происхождения")
    print(f"копия базы ..... {SANDBOX}")
    prepare()

    border = max_id_now()          # граница «старого» — ДО первого своего действия
    before = stamps_upto(border)
    print(f"граница старого . #{border} (всё, что ниже, приёмка не создавала)")
    print(f"штампы ДО приёмки  {before}\n")

    # ── СЛУЧАЙ ① — новая записка без адресата
    id1 = write_note("укус: записка без адресата")
    s1 = stamp_of(id1) if id1 else None
    fixed = s1 == "unset"
    print(f"① записка без --to  → #{id1}, штамп {s1!r}   "
          f"{'✅ ПОЧИНЕНО' if fixed else '🔴 правки ещё нет (ожидалось unset)'}")

    # ── СЛУЧАЙ ③ — новая записка С адресатом (различающий)
    id3 = write_note("укус: записка с адресатом", "--to", "COORD")
    s3 = stamp_of(id3) if id3 else None
    branch_ok = s3 == "field"
    print(f"③ записка С --to    → #{id3}, штамп {s3!r}   "
          f"{'✅ ветка цела' if branch_ok else '🔴 РАБОЧАЯ ВЕТКА СЛОМАНА'}")

    # ── СЛУЧАЙ ② — старые записки не тронуты (различающий)
    # Смотрим ТОЛЬКО до границы: записки, созданные этим укусом, в счёт не входят.
    after = stamps_upto(border)
    history_ok = after == before
    print(f"② старые записки    → до #{border}: было {before}, стало {after}   "
          f"{'✅ история цела' if history_ok else '🔴 ИСТОРИЯ ЗАТЁРТА'}")

    # ── ИТОГ ────────────────────────────────────────────────────────────
    print("\nСВОЙСТВО: новая записка честна о происхождении, старая не переписана,")
    print("          работающая ветка --to не задета")

    if not history_ok or not branch_ok:
        print("\nИТОГ: 🔴 ПРАВКА ЛОМАЕТ — принимать нельзя")
        return 2
    if not fixed:
        print("\nИТОГ: ⏳ правки ещё нет. Приёмка исправна: она ВИДИТ дефект"
              f" (новая записка штампуется {s1!r}) и различает соседние случаи —"
              " история цела, ветка --to цела")
        return 1
    print("\nИТОГ: ✅ ПРАВКА НА МЕСТЕ И РАЗЛИЧАЕТ — три случая из трёх")
    return 0


if __name__ == "__main__":
    sys.exit(main())
