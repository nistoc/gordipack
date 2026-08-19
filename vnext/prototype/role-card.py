#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""role-card — карточка роли для СОСЕДНЕГО контура: собирается из базы, а не пишется рукой.

ЗАЧЕМ (карточка #234, заявка @RCC #3691). Правило `task-states-and-role-card` ввело понятие
карточки роли — «что роль умеет, где её зона, куда ей писать» — и объяснило, кому она нужна:
соседнему контуру, которому неоткуда узнать, кому из нас адресовать вопрос. Но МЕСТА под неё
правило не ввело. @RCC пошла класть свою карточку и положила её в собственный каталог, где
её не увидит ни один сосед. Это не её ошибка: правило ввело понятие без места.

РАЗВИЛКА И РЕШЕНИЕ (19.08, @PROTO — договор обмена мой):
    ① только в базе ....... не расходится с правдой, но сосед в нашу базу не ходит и не должен
    ② только файлом ....... сосед видит сразу, но это ВТОРАЯ копия — она разъедется молча
    ③ база + порождение ... истина в базе, файл собирается ею же командой  ← ВЫБРАНО
Довод за ③ не «дороже, зато красивее», а замер класса: у нас уже есть свод правил, который
существует в базе и в файле, и файл лгал пять часов, пока роль читала его как приказ. Вторая
копия без порождения — не удобство, а отложенная неправда.

ЧТО ЭТО НЕ ДЕЛАЕТ. Не заводит сетевых ручек и не ходит в чужую базу: файл кладётся в НАШУ
исходящую папку, сосед читает его как обычный файл обмена (договор — bridges/*/README.md).

    python <КОНТУР>/vnext-tools/role-card.py --role PROTO            # показать, не писать
    python <КОНТУР>/vnext-tools/role-card.py --role PROTO --write    # положить в исходящие
    python <КОНТУР>/vnext-tools/role-card.py --role PROTO --check    # файл ≠ база → отказ
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

# Куда кладётся карточка. Имя — ЧЕТВЁРТЫЙ вид в договоре обмена, рядом с ask/answer/status.
# Порождаемое имя отличают по приставке `card.`: сосед по нему видит, что файл собран
# машиной и правка его рукой будет затёрта следующим прогоном.
CARD_PREFIX = "card."


def bridges_root(container: Path) -> Path:
    return container / "atlas.archs" / ".mezosync" / "bridges"


def _group_name(db: Path) -> str:
    """Имя нашей группы — из базы. Впечатать его сюда значило бы отдать соседу наш образец
    с нашим же именем внутри: у него он молча выберет не те папки."""
    con = sqlite3.connect(str(db))
    try:
        row = con.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
    except sqlite3.OperationalError:
        row = None
    con.close()
    return (row[0] if row and row[0] else "")


def collect(db: Path, role: str) -> dict:
    """Всё, что база знает о роли. Пустое поле остаётся ПУСТЫМ и называется вслух."""
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    r = con.execute("SELECT role, lifecycle, lifecycle_at, lifecycle_by, lifecycle_reason,"
                    " zone, seen_in FROM roles WHERE role = ?", (role,)).fetchone()
    if r is None:
        con.close()
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: роли «{role}» нет в базе. Это отказ собрать карточку,\n"
                 f"   а не пустая карточка: несуществующей роли нельзя писать.")
    # Только ЖИВЫЕ права: снятое и потраченное в карточку не идёт — иначе сосед прочитает
    # отменённое разрешение как действующее, а это худший род неправды в такой записи.
    rights = con.execute(
        "SELECT role, right_key, scope, kind, authorized_by, granted_at, source_ref, note"
        " FROM role_rights"
        " WHERE (role = ? OR role = 'ALL')"
        "   AND (revoked_at IS NULL OR revoked_at = '')"
        "   AND (spent_at IS NULL OR spent_at = '')"
        " ORDER BY id", (role,)).fetchall()
    card = {
        "роль": r["role"],
        "состояние": r["lifecycle"],
        "состояние_с": r["lifecycle_at"] or "",
        "зона": r["zone"] or "",
        "права": [dict(x) for x in rights],
    }
    con.close()
    return card


def render(card: dict, container: Path) -> str:
    """Текст карточки. Незаполненное НЕ выдумывается и не молчит — оно названо."""
    L = []
    L.append(f"# card.{card['роль'].lower()} — карточка роли {card['роль']} (контур Atlas)")
    L.append("")
    L.append("⚙️ Файл СОБРАН ИЗ БАЗЫ командой `role-card.py`. Правка рукой будет затёрта")
    L.append("   следующим прогоном: чтобы поменять содержимое, меняют запись в базе.")
    L.append("")
    L.append(f"**Состояние:** {card['состояние']}"
             + (f" (с {card['состояние_с']} UTC)" if card["состояние_с"] else ""))
    L.append("")
    L.append("## Зона — за что роль отвечает")
    L.append("")
    L.append(card["зона"] if card["зона"]
             else "⚠️ в базе НЕ ЗАПОЛНЕНО. Это пустое поле, а не «зоны нет».")
    L.append("")
    L.append("## Что роль умеет")
    L.append("")
    L.append("⚠️ В БАЗЕ ПОКА НЕТ МЕСТА ПОД ЭТО ПОЛЕ — карточка #234, шаг схемы отдан @COORD.")
    L.append("   Пока поля нет, карточка честно молчит об умениях, а не пересказывает их")
    L.append("   по памяти автора: пересказ разошёлся бы с правдой ровно так, как вторая копия.")
    L.append("")
    L.append("## Куда ей писать")
    L.append("")
    L.append("Через обмен контуров: файл в вашей исходящей папке, имя `ask.atlas.<тема>.md`.")
    L.append("Внутри контура Atlas записка адресуется полем, а не прозой в теле.")
    L.append("")
    L.append("## Права — что роли разрешено (из базы, полями)")
    L.append("")
    if not card["права"]:
        L.append("⚠️ живых прав в базе не записано.")
    for p in card["права"]:
        вид = "стоячее" if p["kind"] == "standing" else "разовое"
        общее = " (выдано ВСЕМ ролям)" if p["role"] == "ALL" else ""
        # Час берётся как есть: у части записей суффикс уже стои́т в самом поле, и дописывать
        # свой — значит печатать «UTC UTC». Метка без зоны в базе не заводится.
        час = p["granted_at"] if "UTC" in (p["granted_at"] or "") else f"{p['granted_at']} UTC"
        L.append(f"- **{p['right_key']}** — {вид}{общее} · разрешил {p['authorized_by']} {час}")
        if p.get("scope"):
            L.append(f"  - область: {p['scope']}")
        if p.get("note"):
            L.append(f"  - ⛔ границы: {p['note']}")
    L.append("")
    L.append("— собрано из mezosync.db контура Atlas")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="карточка роли для соседнего контура")
    ap.add_argument("--role", required=True)
    ap.add_argument("--db", default=None)
    ap.add_argument("--write", action="store_true", help="положить в исходящие папки обмена")
    ap.add_argument("--check", action="store_true",
                    help="сверить лежащие файлы с тем, что собрала бы база (код 1 при расхождении)")
    ap.add_argument("--bridges", default=None, help="каталог обмена (по умолчанию — от контура)")
    ap.add_argument("--group", default=None,
                    help="имя нашей группы (по умолчанию — запись meta.group_name в базе)")
    a = ap.parse_args()

    role = a.role.upper()
    container = mezo_paths.container_root(__file__)
    # ⚠️ НЕ resolve_db: он ищет базу РЯДОМ со скриптом, а этот инструмент лежит этажом выше
    # каталога группы (vnext-tools рядом с .mezosync, а не внутри). Живая база — от контура.
    db = Path(a.db) if a.db else mezo_paths.live_db(__file__)
    if not db.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: базы нет — {db}")
    root = Path(a.bridges) if a.bridges else bridges_root(container)

    text = render(collect(db, role), container)

    if not (a.write or a.check):
        print(text)
        return 0

    if not root.is_dir():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: каталога обмена нет — {root}\n"
                 f"   Это отказ, а не «соседей нет»: сосед мог быть, а каталог переехать.")

    name = f"{CARD_PREFIX}{role.lower()}.md"
    # 🪤 НЕ ВСЯКАЯ ПАПКА ЗДЕСЬ — ОБМЕН КОНТУРОВ. Рядом лежат обмены отдельных ролей с чужими
    # продуктами (например, роли портала с соседним продуктом): карточка роли контура там
    # никому не адресована и только засоряет чужую переписку. Отбираем по имени НАШЕЙ группы
    # из базы, а не по виду каталога: имя группы — запись, вид каталога — догадка.
    группа = (a.group or _group_name(db) or "").strip().lower()
    if not группа:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: имя нашей группы не записано в базе (meta.group_name).\n"
                 "   Без него нельзя отличить обмен контуров от обмена отдельной роли.")
    все = sorted(p for p in root.iterdir() if p.is_dir())
    targets = [p for p in все if p.name.lower().startswith(f"{группа}-")]
    пропущены = [p.name for p in все if p not in targets]
    if пропущены:
        print(f"ℹ️ пропущено папок: {len(пропущены)} — это не обмен контуров, а чужая "
              f"переписка ({', '.join(пропущены)})")
    if not targets:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {root} нет ни одной папки обмена контура «{группа}» — "
                 f"класть некуда.")

    bad = 0
    for d in targets:
        f = d / name
        if a.check:
            if not f.exists():
                print(f"🔴 {d.name}: карточки нет — {f.name}")
                bad += 1
            elif f.read_text(encoding="utf-8") != text:
                print(f"🔴 {d.name}: файл РАСХОДИТСЯ с базой — правили рукой либо база ушла вперёд")
                bad += 1
            else:
                print(f"✅ {d.name}: файл совпадает с тем, что собрала бы база")
        else:
            f.write_text(text, encoding="utf-8")
            print(f"✍️  положено: {f}")

    if a.check and bad:
        print(f"\n🔴 расхождений {bad} — карточка перестала быть порождаемой; "
              f"перепороди: role-card.py --role {role} --write")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
