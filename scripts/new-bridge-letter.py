# -*- coding: utf-8 -*-
r"""new-bridge-letter.py — письмо соседнему контуру с полями «от кого / кому / ответ на»; проверка шапки.
Этап Э7 набора TRACK-GORDI-CORE, карточка #681. Разбор и вид шапки — модуль bridge_letter.py.

ЗАПУСК:
    python <контур>/.mezosync/scripts/new-bridge-letter.py --role PROTO --to COORD@onto --kind ask \
        --topic e7-fields --file <текст.md> [--due 2026-10-20] [--dry-run]
    python <контур>/.mezosync/scripts/new-bridge-letter.py --role PROTO --to COORD@onto --kind answer \
        --topic e7-fields --reply-to onto:atlas-onto/ask.atlas.e7-fields.20261013-0930 --file <текст.md>
    python <контур>/.mezosync/scripts/new-bridge-letter.py --check <файл письма>

ЧТО ДЕЛАЕТ. Кладёт письмо в НАШУ исходящую папку моста для контура-адресата (с 25.08 каждый контур
пишет только в свою папку): имя <kind>.<контур-адресат>.<тема>.<ГГГГММДД-ЧЧММ>.md, первая строка —
для человека, вторым — блок полей. Имя контура-автора — из базы (meta.group_name), не впечатано.
Файл пишется только новым: существующий не перезаписывается (второй ответ не стирает первый).
--check читает шапку готового письма и говорит: годна · негодна (с причинами) · шапки нет.

КОДЫ ВЫХОДА: 0 — письмо записано (или шапка годна) · 1 — отказ, письмо не записано (или шапка
негодна) · 2 — у проверяемого письма шапки нет либо файл не прочитан.

⛔ ГРАНИЦА. Инструмент не ходит в базы соседей и не читает их истории (правило
no-scan-external-contours): reply-to сверяется только с файлами в папках моста — наших и соседних,
записанных в cross_links. Не нашлось — предупреждение, не отказ: папка соседа могла переехать.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge_letter  # noqa: E402
import mezo_paths  # noqa: E402
from sync_backoff import BRIDGE_LAYOUTS  # noqa: E402


def own_group(db: Path) -> str:
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            row = con.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        return ""
    return bridge_letter.norm_contour((row[0] if row else "") or "")


def known_roles(db: Path):
    """Роли контура из реестра; None — реестра прочесть не удалось (тогда роль не сверяется)."""
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            return {(r[0] or "").upper() for r in con.execute("SELECT role FROM roles")}
        finally:
            con.close()
    except sqlite3.Error:
        return None


def neighbour_containers(db: Path) -> list:
    """[(контур, каталог контура)] из cross_links. Базу соседа не открываем — только каталог."""
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT target_group, target_db_path FROM cross_links ORDER BY rowid").fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return []
    return [(bridge_letter.norm_contour(g or ""), Path(p).parent.parent) for g, p in rows if g and p]


def bridge_places(container: Path) -> list:
    """Папки моста контура по обоим устройствам (тот же список BRIDGE_LAYOUTS, что у чтения ленты)."""
    found = []
    for layout in BRIDGE_LAYOUTS:
        try:
            found += [d for d in sorted(container.glob(layout)) if d.is_dir()]
        except OSError:
            continue
    return found


def outgoing_box(places: list, ours: str, to_contour: str):
    """Наша исходящая папка для контура-адресата → (папка | None, слова для отказа).
    Сперва «<мы>-<он>»; иначе — единственная папка, где оба имени стоят отдельными словами
    (у onto обе стороны пишут в одну папку «atlas-onto»). Иначе — отказ с перечнем."""
    exact = [d for d in places if d.name == f"{ours}-{to_contour}"]
    if len(exact) == 1:
        return exact[0], ""
    both = [d for d in places if {ours, to_contour} <= set(d.name.split("-"))]
    if not exact and len(both) == 1:
        return both[0], ""
    seen = exact or both
    if seen:
        return None, ("папок-кандидатов несколько: " + " · ".join(d.as_posix() for d in seen)
                      + " — назови нужную флагом --box")
    return None, (f"нашей исходящей папки для контура «{to_contour}» нет (искала «{ours}-{to_contour}» "
                  "и папку с обоими именами в папках моста контура) — заведи её или назови флагом --box")


def check_letter(path: Path) -> int:
    h = bridge_letter.read_header(path)
    if not h.found:
        print(f"ℹ️ {path.name}: {h.describe()} — такое письмо судят прежние правила по имени и первой строке")
        return 2
    if h.problems:
        print(f"⛔ {path.name}: шапка негодна (блок открыт {h.block_line}-й непустой строкой)")
        for p in h.problems:
            print(f"   · {p}")
    else:
        print(f"✅ {path.name}: шапка годна — {h.describe()}")
        if h.letter_id:
            print(f"   id: {h.letter_id}")
    for n in h.notes:
        print(f"   ⚠️ {n}")
    return 0 if h.valid else 1


def refuse(words: str) -> int:
    print(f"⛔ письмо НЕ записано: {words}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Письмо соседнему контуру с полями «от кого / кому / ответ на» (этап Э7) "
                    "или проверка шапки готового письма (--check).")
    ap.add_argument("--check", metavar="ФАЙЛ", help="проверить шапку готового письма и выйти")
    ap.add_argument("--role", help="роль-автор нашего контура (системное имя)")
    ap.add_argument("--to", action="append", default=[],
                    help="адресат РОЛЬ@контур; несколько — повтором флага или через запятую; all@контур — всем ролям")
    ap.add_argument("--kind", choices=bridge_letter.KINDS, help="ask · answer · status · fix")
    ap.add_argument("--topic", help="тема для имени файла: буквы, цифры, «-» и «_»")
    ap.add_argument("--reply-to", default="", help="id письма, на которое это ответ (у answer и fix обязателен)")
    ap.add_argument("--due", default="", help="у вопроса: до какой даты ждём ответа, ГГГГ-ММ-ДД")
    ap.add_argument("--file", help="текст письма (UTF-8); шапку инструмент ставит сам")
    ap.add_argument("--box", help="папка, куда положить письмо, если инструмент не нашёл её сам")
    ap.add_argument("--db", help="база контура (по умолчанию — рядом с инструментом)")
    ap.add_argument("--dry-run", action="store_true", help="показать имя и текст письма, ничего не записывать")
    args = ap.parse_args()

    if args.check:
        return check_letter(Path(args.check))

    missing = [f"--{n}" for n, v in (("role", args.role), ("kind", args.kind), ("topic", args.topic),
                                      ("file", args.file)) if not v]
    if not args.to:
        missing.append("--to")
    if missing:
        return refuse("не хватает флагов " + ", ".join(missing))

    db = Path(args.db) if args.db else mezo_paths.default_db(__file__)
    ours = own_group(db)
    if not ours:
        return refuse(f"имя контура не прочитано из базы {db} (meta.group_name) — без него поле from не заполнить")
    role = args.role.upper()
    roles = known_roles(db)
    if roles is not None and role not in roles:
        return refuse(f"роли «{role}» нет в реестре ролей контура «{ours}»")

    to = []
    for chunk in args.to:
        for part in [p for p in chunk.split(",") if p.strip()]:
            address = bridge_letter.parse_address(part)
            if not address:
                return refuse(f"адресат «{part.strip()}» — не вида РОЛЬ@контур")
            to.append(address)
    to = list(dict.fromkeys(to))
    foreign = [c for _, c in to if c != ours]
    if not foreign:
        return refuse(f"все адресаты — наш же контур «{ours}»: письмо моста идёт соседу, своим — записка в ленту")
    to_contour = foreign[0]

    if args.kind in bridge_letter.REPLY_KINDS and not args.reply_to:
        return refuse(f"у письма вида {args.kind} нужен --reply-to: id письма, на которое это ответ")
    if args.reply_to and not bridge_letter.split_id(args.reply_to):
        return refuse(f"--reply-to «{args.reply_to}» — не вида контур:папка/имя")
    if args.kind == "fix" and bridge_letter.split_id(args.reply_to)[0] != ours:
        return refuse("поправка (fix) — только к своему письму: reply-to должен называть письмо контура "
                      f"«{ours}» (решение В3)")
    if args.due and args.kind != "ask":
        return refuse(f"--due — только у вопроса (ask): письмо вида {args.kind} ответа не ждёт")
    if args.due and not bridge_letter.DUE_RE.match(args.due):
        return refuse(f"--due «{args.due}» — не вида ГГГГ-ММ-ДД")

    try:
        body = Path(args.file).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return refuse(f"текст письма не прочитан: {args.file} ({exc.__class__.__name__})")
    if bridge_letter.parse_header(body).found:
        return refuse("в тексте уже есть блок полей — шапку ставит инструмент, в тексте её быть не должно")

    container = mezo_paths.container_root(__file__)
    places = bridge_places(container)
    if args.box:
        box = Path(args.box)
        if not box.is_dir():
            return refuse(f"папки {box} нет")
    else:
        box, words = outgoing_box(places, ours, to_contour)
        if box is None:
            return refuse(words)

    when = bridge_letter.utc_now()
    try:
        name = bridge_letter.letter_name(args.kind, to_contour, args.topic, when)
    except ValueError as exc:
        return refuse(str(exc))
    letter_id = bridge_letter.place_id(ours, box.name, name)
    text = bridge_letter.compose(when, (role, ours), to, args.kind, letter_id,
                                 reply_to=args.reply_to, due=args.due, body=body)
    path = box / name

    warnings = []
    if len(set(foreign)) > 1:
        warnings.append(f"адресаты в нескольких контурах — письмо легло в папку для «{to_contour}»; "
                        "остальные увидят его, только если читают эту папку")
    if args.reply_to:
        owners = {d: ours for d in places}
        for group, root in neighbour_containers(db):
            owners.update({d: group for d in bridge_places(root)})
        hits = bridge_letter.resolve_id(args.reply_to, owners)
        if len(hits) != 1:
            warnings.append(f"письмо по reply-to «{args.reply_to}» отсюда не видно (нашлось {len(hits)}) — "
                            "проверь id: контур-владелец места, папка, имя без .md")

    if args.dry_run:
        print(f"ℹ️ ХОЛОСТОЙ ПРОГОН — ничего не записано. Письмо легло бы в {path.as_posix()}")
        for w in warnings:
            print(f"⚠️ {w}")
        print("─" * 60)
        print(text, end="")
        return 0

    try:
        with open(path, "x", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    except FileExistsError:
        return refuse(f"файл {path.as_posix()} уже есть — письмо не перезаписывает другое")
    except OSError as exc:
        return refuse(f"файл {path.as_posix()} не записан ({exc.__class__.__name__})")

    h = bridge_letter.read_header(path)
    if not h.valid:
        print(f"⛔ письмо записано, но его шапка при чтении негодна: {h.describe()} — {path.as_posix()}")
        return 1
    print(f"✅ письмо записано: {path.as_posix()}")
    print(f"   {h.describe()}")
    print(f"   id: {letter_id}")
    for w in warnings:
        print(f"⚠️ {w}")
    print("   👉 внутри контура о письме узнают из ленты: назови его в записке (имя файла и адресата)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
