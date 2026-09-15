# -*- coding: utf-8 -*-
"""bite-memory-section-refs.py — ПРИЁМКА guard-memory-section-refs.py (карточка #643 ⑥).

Судит на СВОЕЙ подсаженной базе (mezo_stand.new), не на живой: живой замер меняется
чужими руками и не даёт различающих случаев по требованию (русское имя в конкретном
падеже, цель в архиве и т.п. — живых примеров мало и они не выбираются по заказу).

Каждое требование — свой случай И своя НАРОЧНАЯ ПОЛОМКА (норма песочницы): поломка
строится в КОПИИ инструмента внутри стенда, якорь — строка, которая в файле ровно
одна (проверено `grep -c` перед приёмкой). Прогон «версия ДО правки» не нужен — файл
новый; поломки на НЁМ — доказательство, что случаи различают, а не просто зелёные.

    python bite-memory-section-refs.py
"""
from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402 — временный стенд: убирается при успехе, сохраняется при провале
GUARD = HERE / "guard-memory-section-refs.py"

CASES, OK = 0, True
_ROOT = None  # корень стенда (mezo_stand.new) — выставляется в main() ДО первого run()


def case(title, verdict, detail="", differ=False):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")
    return bool(verdict)


def make_db(path: Path, phoenix_rows, archive_rows=()):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, "
                "saved_at TEXT, confirmed_at TEXT)")
    con.execute("CREATE TABLE phoenix_archive (id INTEGER PRIMARY KEY, role TEXT, "
                "section TEXT, topic TEXT, body TEXT, body_chars INT, moved_at TEXT, "
                "moved_by TEXT, origin_saved_at TEXT)")
    for role, section, body in phoenix_rows:
        con.execute("INSERT INTO phoenix (role, section, body, saved_at) "
                    "VALUES (?,?,?,datetime('now'))", (role, section, body))
    for role, section, topic, body in archive_rows:
        con.execute("INSERT INTO phoenix_archive (role, section, topic, body, body_chars, "
                    "moved_at) VALUES (?,?,?,?,?,datetime('now'))",
                    (role, section, topic, body, len(body)))
    con.commit()
    con.close()
    return path


def run(db_path: Path, guard=GUARD, role=None, soft=False):
    """Подпроцесс ТОЛЬКО со средой стенда — без неё испытуемый инструмент унаследовал бы
    MEZO_CONTAINER вызывающего и мог бы читать чужой живой контур мимо явного --db
    (заметка #5096, норма песочницы)."""
    env = mezo_stand.stand_env(_ROOT)
    cmd = [sys.executable, str(guard), "--db", str(db_path)]
    if role:
        cmd += ["--role", role]
    if soft:
        cmd += ["--soft"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def broken_copy(root: Path, name: str, anchor: str, replacement: str) -> Path:
    """Копия guard-а с НАРОЧНОЙ ПОЛОМКОЙ: anchor обязан встретиться РОВНО ОДИН раз.

    Копия едет В СВОЙ каталог ВМЕСТЕ С СОСЕДЯМИ (mezo_stand.neighbours_of, тот же приём,
    что у copy_tool) — без mezo_paths.py рядом импорт падает `ModuleNotFoundError`,
    и это была бы поломка ЗАПУСКА, а не поломка ПРОВЕРЯЕМОГО ПРИЗНАКА (нашлось прогоном
    первой же версии этого файла — «поймано на себе», не сочинено заранее).
    """
    src = GUARD.read_text(encoding="utf-8")
    n = src.count(anchor)
    if n != 1:
        sys.exit(f"⛔ ЯКОРЬ ПОЛОМКИ «{name}» встречен {n} раз(а), а не 1 — поломка мимо цели")
    d = root / f"broken-{name}"
    d.mkdir(exist_ok=True)
    for neighbour in mezo_stand.neighbours_of(GUARD):
        target = d / neighbour.name
        if not target.exists():
            import shutil
            shutil.copy2(neighbour, target)
    dst = d / GUARD.name
    dst.write_text(src.replace(anchor, replacement), encoding="utf-8")
    return dst


def main() -> int:
    global _ROOT
    root = mezo_stand.new("bite-msr-")
    _ROOT = root

    # ── ① русское имя раздела, РОДИТЕЛЬНЫЙ падеж → найден ──────────────────────────
    db1 = make_db(root / "c1.db", [
        ("ZZ1", "state", "Разбор — в разделе ВОСКРЕШЕНИЯ, читать до работы"),
        ("ZZ1", "rebirth", "тело раздела живо"),
    ])
    out, code = run(db1, role="ZZ1")
    case("① русское имя раздела в родительном падеже («раздела ВОСКРЕШЕНИЯ» → rebirth) → найден",
         code == 0 and "найден 1" in out and "без адресата 0" in out, out.strip()[-200:])

    # ── ② латинское имя → найден ────────────────────────────────────────────────────
    db2 = make_db(root / "c2.db", [
        ("ZZ2", "plan", "блок переехал в §REBIRTH сегодня"),
        ("ZZ2", "rebirth", "тело раздела живо"),
    ])
    out, code = run(db2, role="ZZ2")
    case("② латинское имя раздела (§REBIRTH) → найден",
         code == 0 and "найден 1" in out and "без адресата 0" in out, out.strip()[-200:])

    # ── ③ заголовок блока В ДРУГОМ РАЗДЕЛЕ → найден ────────────────────────────────
    db3 = make_db(root / "c3.db", [
        ("ZZ3", "identity", "## ОСОБЫЙ БЛОК\nтекст особого блока"),
        ("ZZ3", "plan", "подробности — смотри блок «ОСОБЫЙ БЛОК»"),
    ])
    out, code = run(db3, role="ZZ3")
    case("③ заголовок блока в ДРУГОМ разделе той же роли → найден",
         code == 0 and "найден 1" in out and "без адресата 0" in out, out.strip()[-200:])

    # ── ④ цель унесена в архив → «в архиве» + команда, как достать ─────────────────
    db4 = make_db(root / "c4.db",
        [("ZZ4", "state", "Разбор — в архиве, блок «СТАРЫЙ»")],
        [("ZZ4", "history", "СТАРЫЙ формат учёта времени", "тело унесённого куска")])
    out, code = run(db4, role="ZZ4")
    case("④ цели нет в горячей памяти, есть в архиве роли → «в архиве» + команда memory-archive.py --find",
         code == 0 and "в архиве 1" in out and "без адресата 0" in out
         and "memory-archive.py --role" in out and "--find" in out, out.strip()[-260:])

    # ── ⑤ цели нет НИГДЕ → без адресата ─────────────────────────────────────────────
    db5 = make_db(root / "c5.db", [("ZZ5", "state", "смотри блок «ПРИЗРАК»")])
    out, code = run(db5, role="ZZ5")
    case("⑤ цели нет нигде (ни в памяти, ни в архиве) → без адресата, код 1",
         code == 1 and "без адресата 1" in out and "ПРИЗРАК" in out, out.strip()[-200:])

    # ── ⑥ строка с пометкой о снятии → НЕ судится ───────────────────────────────────
    db6 = make_db(root / "c6.db",
        [("ZZ6", "state", "⚰️ блок «ПРИЗРАК» снят, не искать — прежняя мысль устарела")])
    out, code = run(db6, role="ZZ6")
    case("⑥ строка с пометкой о снятии (⚰️) → не судится (не found/archive/orphan, счёт отдельно)",
         code == 0 and "без адресата 0" in out and "в архиве 0" in out
         and "найден 0" in out and "пропущено 1" in out, out.strip()[-200:])

    # ── ⑦ «раздел памяти» БЕЗ имени → не указатель вовсе ────────────────────────────
    db7 = make_db(root / "c7.db",
        [("ZZ7", "state", "раздел памяти большой, чистить его не будем; читай раздел целиком")])
    out, code = run(db7, role="ZZ7")
    case("⑦ «раздел памяти» / «раздел целиком» без заглавного имени цели — не указатель",
         code == 0 and "найден 0" in out and "в архиве 0" in out and "без адресата 0" in out,
         out.strip()[-200:])

    # ── ⑧ роль БЕЗ памяти → «судить нечем», НЕ «чисто» ──────────────────────────────
    db8 = make_db(root / "c8.db", [("ZZ_ЖИВАЯ", "state", "текст")])
    out, code = run(db8, role="ZZNOSUCHROLE")
    case("⑧ роль без памяти → «судить нечем» (не путать с ✅ «чисто»), код 0",
         code == 0 and "судить нечем" in out and "✅" not in out, out.strip()[-200:])

    # ── СВЕЖИЙ КОНТУР: пустая база (схема есть, ролей нет) → «судить нечем», не падает ──
    db9 = make_db(root / "c9-empty.db", [])
    out, code = run(db9)
    case("⑨ свежий контур (схема есть, памяти ролей нет вовсе) → не падает, «судить нечем», код 0",
         code == 0 and "судить нечем" in out, out.strip()[-200:])

    # ── ⑩ корень «УНЕС» — пометка о переносе в архив → не судится ───────────────────
    # Живая форма (STUD/state:10, карточка #643 ⑥ круг доделки): цель названа УНЕСЁННОЙ
    # в ТОМ ЖЕ предложении, что и указатель — роль предупреждена, не находит пустоту молча.
    db10 = make_db(root / "c10.db",
        [("ZZ10", "state", "Прежний блок «ПРИЗРАК» унесён — протухшее, верь этой строке")])
    out, code = run(db10, role="ZZ10")
    case("⑩ корень «УНЕС» (унесён/унесено/унесли) рядом с указателем → не судится, пометка",
         code == 0 and "без адресата 0" in out and "пропущено 1" in out, out.strip()[-200:])

    # ── ⑪/⑫ --soft: код 0 + «⚠️»-префикс на сироте · без флага — прежнее поведение ──
    out_soft, code_soft = run(db5, role="ZZ5", soft=True)
    case("⑪ --soft на сироте: код 0, строка находки начинается с «⚠️», фраза о мягком режиме",
         code_soft == 0 and "⚠️ без адресата" in out_soft
         and "мягкий режим: общий прогон не проваливается" in out_soft, out_soft.strip()[-260:])
    out_hard, code_hard = run(db5, role="ZZ5", soft=False)
    case("⑫ ВСТРЕЧНЫЙ: та же сирота БЕЗ --soft → код 1, префикса «⚠️» нет (прежнее поведение)",
         code_hard == 1 and "⚠️ без адресата" not in out_hard, out_hard.strip()[-200:])

    # ═══════════════════════════════════════════════════════════════════════════════
    # НАРОЧНЫЕ ПОЛОМКИ — каждая обязана провалить РОВНО свой случай, прежние остаются
    # ═══════════════════════════════════════════════════════════════════════════════

    # Поломка А: снять русские корни → случай ① обязан провалиться, ②③④ — остаться в силе.
    guard_a = broken_copy(root, "ru-stems", "for canon, stems in RU_STEMS.items():",
                          "for canon, stems in {}.items():")
    out1, code1 = run(db1, guard=guard_a, role="ZZ1")
    out2, code2 = run(db2, guard=guard_a, role="ZZ2")
    out4, code4 = run(db4, guard=guard_a, role="ZZ4")
    case("ПОЛОМКА А (сняты русские корни): случай ① валится (ВОСКРЕШЕНИЯ не узнан)",
         code1 == 1 and "без адресата 1" in out1, out1.strip()[-160:], differ=True)
    case("ПОЛОМКА А — встречный: случай ② (латиница) НЕ задет чужой поломкой",
         code2 == 0 and "найден 1" in out2, out2.strip()[-160:], differ=True)
    case("ПОЛОМКА А — встречный: случай ④ (архив) НЕ задет чужой поломкой",
         code4 == 0 and "в архиве 1" in out4, out4.strip()[-160:], differ=True)

    # Поломка Б: снять поиск в архиве → случай ④ обязан стать «без адресата».
    guard_b = broken_copy(root, "no-archive", "for _id, sec, topic, body in archive_rows:",
                          "for _id, sec, topic, body in []:")
    out4b, code4b = run(db4, guard=guard_b, role="ZZ4")
    out1b, code1b = run(db1, guard=guard_b, role="ZZ1")
    case("ПОЛОМКА Б (снят поиск в архиве): случай ④ становится «без адресата» вместо «в архиве»",
         code4b == 1 and "в архиве 0" in out4b and "без адресата 1" in out4b,
         out4b.strip()[-160:], differ=True)
    case("ПОЛОМКА Б — встречный: случай ① (найден раньше архива) НЕ задет",
         code1b == 0 and "найден 1" in out1b, out1b.strip()[-160:], differ=True)

    # Поломка В: снять пропуск пометок о снятии → случай ⑥ обязан провалиться.
    guard_c = broken_copy(root, "no-tomb-skip", "if _is_tomb(line):", "if False:")
    out6c, code6c = run(db6, guard=guard_c, role="ZZ6")
    out5c, code5c = run(db5, guard=guard_c, role="ZZ5")
    case("ПОЛОМКА В (снят пропуск пометок ⚰️): случай ⑥ валится (пометка больше не гасит находку)",
         "пропущено 0" in out6c and ("без адресата 1" in out6c or "найден 1" in out6c),
         out6c.strip()[-200:], differ=True)
    case("ПОЛОМКА В — встречный: случай ⑤ (обычная сирота, без пометки) НЕ задет",
         code5c == 1 and "без адресата 1" in out5c, out5c.strip()[-160:], differ=True)

    # Поломка Г: снять корень «УНЕС» из TOMB_RX → случай ⑩ обязан провалиться (снова сирота).
    guard_d = broken_copy(
        root, "no-unes-root",
        'TOMB_RX = re.compile(r"⚰️|📦|🪦|~~|УБРАН|СНЯТО|БОЛЬШЕ НЕ ХРАН|УНЕС", re.IGNORECASE)',
        'TOMB_RX = re.compile(r"⚰️|📦|🪦|~~|УБРАН|СНЯТО|БОЛЬШЕ НЕ ХРАН", re.IGNORECASE)')
    out10d, code10d = run(db10, guard=guard_d, role="ZZ10")
    out6d, code6d = run(db6, guard=guard_d, role="ZZ6")
    case("ПОЛОМКА Г (снят корень «УНЕС»): случай ⑩ валится — «блок «ПРИЗРАК» унесён…» "
         "снова читается как «без адресата» (STUD-вид)",
         code10d == 1 and "пропущено 0" in out10d and "без адресата 1" in out10d,
         out10d.strip()[-200:], differ=True)
    case("ПОЛОМКА Г — встречный: случай ⑥ (⚰️) НЕ задет — свой знак снятия цел",
         code6d == 0 and "пропущено 1" in out6d, out6d.strip()[-160:], differ=True)

    # Поломка Д: --soft перестаёт гасить код возврата → случай ⑪ обязан провалиться.
    guard_e = broken_copy(
        root, "soft-no-suppress",
        '    if a.soft:\n        print("мягкий режим: общий прогон не проваливается")\n'
        '        return 0\n    return 1 if o else 0',
        '    return 1 if o else 0')
    out_soft_e, code_soft_e = run(db5, guard=guard_e, role="ZZ5", soft=True)
    out_arch_e, code_arch_e = run(db4, guard=guard_e, role="ZZ4", soft=True)
    case("ПОЛОМКА Д (--soft перестаёт гасить код): случай ⑪ валится — код снова 1 при сироте",
         code_soft_e == 1 and "мягкий режим" not in out_soft_e, out_soft_e.strip()[-200:], differ=True)
    case("ПОЛОМКА Д — встречный: --soft БЕЗ сирот (архивный случай) остаётся кодом 0 — "
         "поломка бьёт именно ГАШЕНИЕ КОДА НА СИРОТЕ, не сам флаг",
         code_arch_e == 0, out_arch_e.strip()[-160:], differ=True)

    print()
    print(f"{'✅ ПРИЁМКА ПРИНЯТА' if OK else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}")
    return mezo_stand.finish(0 if OK else 1)


if __name__ == "__main__":
    sys.exit(main())
