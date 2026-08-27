# -*- coding: utf-8 -*-
# SURFACES: printed
r"""check-false-signature.py — МЕХАНИЗМ ПЕЧАТАЕТ ИМЯ, КОТОРОГО У НЕГО НЕТ (карточка #87).

Поручение владельца 07.08 10:10 UTC: у справок и подписей не было НИ ОДНОЙ проверки.
Читатель верит подписи — а подпись никем не судится.

═══ ТРИ ПРАВИЛА (из разбора шести живых экземпляров ПО ТЕЛУ, карточка #87) ═══
  А. ИМЯ, КОТОРОГО НЕТ: справка называет флаг, которого нет в argparse этого же скрипта,
     или обещает СОСУД («ставит признак…», «пишет в поле…») БЕЗ проверяемого имени —
     прозой в «ёлочках». Живой экземпляр: --to «ставит признак „адресат задан полем"» —
     ни поля, ни таблицы тогда не существовало, и проверить обещание было НЕЧЕМ.
     После починки имя названо: «признак addressed_by=field» — и стало проверяемым.
  Б. ОБЯЗАТЕЛЬНОСТЬ БЕЗ ПРИНУЖДЕНИЯ: help говорит «обязателен/required/нельзя без»,
     а required=True не стоит и отказа в коде нет. Живой экземпляр: backlog
     «критерий … (обязателен по слову владельца)» — и молча принимал без критерия.
  В. КАНОН ГОВОРИТ ЗА ВСЕХ, А ИСПОЛНЯЮТ НЕ ВСЕ: канон объявляет «--db НЕОБЯЗАТЕЛЕН»,
     а у инструмента стоит required=True. Роль, поверившая канону, получает отказ.

═══ ⚖️ ГРАНИЦА — ПЕЧАТАЕТСЯ КАЖДЫМ ПРОГОНОМ (критерий ④): молчание ≠ «ложных строк нет» ═══
НЕ ЛОВИТСЯ по построению (разбор #87, три экземпляра из шести):
  · ложная ПРИЧИНА («--limit здесь ни при чём») — причину не сверить с кодом регекспом;
  · ложный СРОК («умрёт с чатом») — срок не имя;
  · подмена источника пересказчиком — не автоматизируется вовсе.
Правило А видит только ДВЕ формы: флаг в справке и «признак/поле/таблица …» рядом
с «ёлочками»/идентификатором. Имя, названное иначе, невидимо.

ЗАПУСК:
    python check-false-signature.py                    # все инструменты живого контура
    python check-false-signature.py --root <каталог>   # копия (история, стенд)
    python check-false-signature.py --file <скрипт>    # один файл
Выход: 0 — находок нет · 1 — находки напечатаны (файл+строка+правило) · 2 — отказ мерить
"""
import argparse
import ast
import re
import sqlite3
import sys
from pathlib import Path

import mezo_paths  # пути машины выводятся, не впечатаны (#153)

# Б: слова обязательности в help-тексте
MANDATORY = re.compile(r"(?<!не)обязател|required|нельзя без", re.I)
# (?<!не): «НЕобязателен» содержит «обязателен» подстрокой — без просмотра назад признак
# обвинял честный help (track.py --db, найдено прогоном 28.08). Отрицание — не обещание.
# исключение к Б: обязательность, о которой говорит help, может навязываться НЕ argparse,
# а отказом в теле — тогда рядом с dest обязан жить sys.exit/raise/refuse
ENFORCE = re.compile(r"sys\.exit|raise |refuse|return 2|печат\w+ отказ", re.I)
# А-безымянность: обещание сосуда прозой — «признак «…»» без идентификатора
# 🪤 re.I обязателен: первая редакция без него пропустила ЖИВОЙ исторический экземпляр —
# «Ставит признак…» с заглавной. Нашла собственная приёмка, не глаз.
VESSEL_CLAIM = re.compile(r"(?:ставит|пишет|кладёт)\s+(?:признак|в?\s?пол[ея])\s*«([^»]+)»",
                          re.I)
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_.=]*$")
# А-имя: «признак X=» / упоминание колонки — идентификатор сверяется с базой
NAMED_VESSEL = re.compile(r"признак\s+([A-Za-z_][A-Za-z0-9_]*)\s*=")
# В: канон объявляет --db необязательным (строка живёт в шапке CANON read-phoenix.py)
CANON_CLAIM = re.compile(r"--db.{0,30}НЕОБЯЗАТЕЛЕН", re.S)
FLAG_IN_HELP = re.compile(r"(?<![\w-])--([a-z][a-z0-9-]{1,30})\b")


def db_names(db_path):
    """Все имена таблиц и колонок живой базы — чем сверяется правило А."""
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    names = set()
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')"):
        names.add(t)
        try:
            names.update(c[1] for c in con.execute(f"PRAGMA table_info({t})"))
        except sqlite3.Error:
            pass
    con.close()
    return names


def parse_args_of(tree):
    """{dest: (required, help, lineno, flags)} по add_argument; flags — все имена флагов."""
    out, flags = {}, set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "add_argument"):
            continue
        names = [a.value for a in node.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        kw = {k.arg: k.value for k in node.keywords if k.arg}
        req = isinstance(kw.get("required"), ast.Constant) and kw["required"].value is True
        hlp = kw.get("help")
        hlp_text = ""
        if isinstance(hlp, ast.Constant):
            hlp_text = str(hlp.value)
        elif isinstance(hlp, ast.JoinedStr) or isinstance(hlp, ast.BinOp):
            hlp_text = " ".join(str(c.value) for c in ast.walk(hlp)
                                if isinstance(c, ast.Constant))
        dest = next((n.lstrip("-") for n in names if n.startswith("--")),
                    names[0] if names else "?")
        out[dest] = (req, hlp_text, node.lineno)
        flags.update(n.lstrip("-") for n in names if n.startswith("--"))
    return out, flags


def scan_file(path, names_in_db):
    """[(строка, правило, что)] — находки по одному файлу."""
    try:
        src = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(src)
    except SyntaxError as e:
        return [(e.lineno or 0, "⛔", f"файл не разбирается: {e.msg} — НЕ проверен, это не «чисто»")]
    finds = []
    args, flags = parse_args_of(tree)

    for dest, (req, hlp, ln) in args.items():
        # ── Б: help обещает обязательность, argparse не требует, отказа рядом нет
        if hlp and MANDATORY.search(hlp) and not req:
            window = "\n".join(src.splitlines()[max(0, ln - 1):ln + 40])
            if not (re.search(rf"\b{re.escape(dest.replace('-', '_'))}\b", window)
                    and ENFORCE.search(window)):
                finds.append((ln, "Б", f"--{dest}: help говорит «обязателен», а required "
                                       f"не стоит и отказа рядом нет — читатель верит слову,"
                                       f" код не держит"))
        # ── А-флаг: help называет флаг, которого нет у этого скрипта
        if hlp:
            for f in FLAG_IN_HELP.findall(hlp):
                if f not in flags and f != dest:
                    finds.append((ln, "А", f"--{dest}: help называет «--{f}», а такого флага"
                                           f" у скрипта нет"))
        # ── А-безымянность: обещание сосуда прозой, проверить нечем
        if hlp:
            for m in VESSEL_CLAIM.finditer(hlp):
                if not IDENT.match(m.group(1).strip()):
                    finds.append((ln, "А", f"--{dest}: обещан сосуд «{m.group(1)}» ПРОЗОЙ —"
                                           f" ни поля, ни таблицы с именем; проверить нечем"))
        # ── А-имя: названный сосуд сверяется с базой
        if hlp and names_in_db is not None:
            for m in NAMED_VESSEL.finditer(hlp):
                if m.group(1) not in names_in_db:
                    finds.append((ln, "А", f"--{dest}: признак «{m.group(1)}» — в базе нет"
                                           f" ни таблицы, ни колонки с этим именем"))
    return finds


def canon_violations(root, files_args):
    """В: канон «--db необязателен» против required=True у инструментов."""
    canon_src = None
    for name in ("read-phoenix.py",):
        p = root / name
        if p.exists():
            canon_src = p.read_text(encoding="utf-8", errors="replace")
    if not canon_src or not CANON_CLAIM.search(canon_src):
        return None                                  # канона нет — сверять не с чем
    finds = []
    for path, args in files_args.items():
        info = args.get("db")
        if info and info[0]:                          # required=True
            finds.append((path.name, info[2], "В",
                          f"--db required=True при каноне «--db НЕОБЯЗАТЕЛЕН» — роль,"
                          f" поверившая канону, получит отказ этого инструмента"))
    return finds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="каталог инструментов (дефолт — живой)")
    ap.add_argument("--file", default=None, help="один файл")
    ap.add_argument("--db", default=None, help="база для сверки имён (дефолт — живая)")
    a = ap.parse_args()
    root = Path(a.root) if a.root else mezo_paths.live_scripts()
    db = Path(a.db) if a.db else mezo_paths.live_db()
    if a.file:
        targets = [Path(a.file)]
    elif root.is_dir():
        targets = sorted(root.glob("*.py"))
    else:
        print(f"⛔ каталога нет: {root} — мерить нечего, это НЕ «чисто»")
        return 2
    if not targets:
        print(f"⛔ в {root} нет ни одного .py — мерить нечего, это НЕ «чисто»")
        return 2

    names = db_names(db)
    if names is None:
        print(f"⚠️ база {db} недоступна — правило А-имя НЕ сверялось (А-флаг и Б работали)")

    total = []
    files_args = {}
    for p in targets:
        try:
            files_args[p] = parse_args_of(ast.parse(
                p.read_text(encoding="utf-8", errors="replace")))[0]
        except SyntaxError:
            files_args[p] = {}
        for ln, rule, what in scan_file(p, names):
            total.append((p.name, ln, rule, what))

    cv = canon_violations(root if not a.file else Path(a.file).parent, files_args)
    if cv is None:
        print("⚠️ канона «--db необязателен» в каталоге нет — правило В НЕ проверялось"
              " (это не «чисто по В», это «В без предмета»)")
    else:
        total.extend(cv)

    for name, ln, rule, what in sorted(total):
        print(f"🔴 [{rule}] {name}:{ln} — {what}")
    verdict = "🔴" if total else "✅"
    print(f"{verdict} ложная подпись: находок {len(total)} · файлов проверено {len(targets)}"
          f" · правила: А (имя/безымянный сосуд) · Б (обязательность без принуждения)"
          f" · В (канон против инструмента)")
    print("⚖️ ГРАНИЦА (не ловится ПО ПОСТРОЕНИЮ): ложная ПРИЧИНА · ложный СРОК · подмена"
          " источника пересказчиком. Молчание выше НЕ значит, что таких строк нет.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
