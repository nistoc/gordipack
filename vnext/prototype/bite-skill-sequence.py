# -*- coding: utf-8 -*-
# PLANTS: skills
"""ПРИЁМКА последовательности правки общих текстов (заход 4 ⑧).

Испытуемые: правило свода `shared-text-edit-sequence` (источник) и порождённый из него
навык atlas-shared-edit (витрина). Последовательность держалась памятью одной роли —
теперь она в своде, а здесь доказывается, что: якоря на месте · команды навыка судимы
проверкой печатных форм без красного · склейка контроля с отправкой в `&&` ловится ·
правило ССЫЛАЕТСЯ на соседей, а не копирует их тела.
"""
import importlib.util
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402

SKILL = mezo_paths.container_root() / ".claude" / "skills" / "atlas-shared-edit" / "SKILL.md"
GUARD = HERE / "guard-printed-forms.py"
CANON = mezo_paths.container_root() / "CLAUDE.md"

CASES, OK = 0, True


def case(title, verdict, detail=""):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")


def seq_flaw(lines):
    """Признак склейки: контроль заглушек стоит в одной строке с чем-то ещё через `&&`.
    Ровно эта склейка дважды печатала красное ПОСЛЕ ушедшего push."""
    return [l for l in lines if "guard-machine-paths" in l and "&&" in l]


def main() -> int:
    if not SKILL.exists():
        print(f"⛔ навыка нет: {SKILL} — приёмке нечего судить (это НЕ «зелёное»)")
        return 2
    text = SKILL.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    anchors = ["ОБЪЯВИ И ПРАВЬ БЕЗОПАСНО", "ПРОГОНИ СРАЗУ", "СВЕДИ ПАРУ",
               "ОТДЕЛЬНОЙ КОМАНДОЙ"]
    missing = [a for a in anchors if a not in text]
    case("① четыре якоря последовательности на месте (порождены из свода)",
         not missing, "нет: " + ", ".join(missing) if missing else "①→②→③→④")

    spec = importlib.util.spec_from_file_location("gpf_seq", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    defs = mod.canon_defs(CANON) or {}
    known = ({p.name for p in mezo_paths.live_scripts().glob("*.py")}
             | {p.name for p in HERE.glob("*.py")})
    red = [(k, f) for _i, k, f in mod.judged_lines(lines, known, HERE, defs)
           if k.startswith("🔴")]
    case("② команды навыка судимы проверкой печатных форм → 0 красных",
         not red, " · ".join(k for k, _ in red[:3]))

    case("③ живой навык: контроль заглушек НЕ склеен с другим шагом через `&&`",
         not seq_flaw(lines))

    dirty = [l if "guard-machine-paths" not in l else
             "python <КОНТУР>/vnext/tools/sync-vnext-pair.py --apply && " + l.strip()
             for l in lines]
    case("③б подсадка: сведение и контроль склеены `&&` → признак краснеет",
         bool(seq_flaw(dirty)),
         "контроль в одной строке с отправкой не успевает её остановить")

    con = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    rule = con.execute("SELECT body FROM rules WHERE rule_key='shared-text-edit-sequence' "
                       "AND status='active'").fetchone()
    nb = con.execute("SELECT body FROM rules WHERE rule_key='tool-edit-announce'").fetchone()
    con.close()
    case("④ правило существует active и ССЫЛАЕТСЯ на tool-edit-announce по имени",
         rule is not None and "tool-edit-announce" in rule[0])
    if rule and nb:
        chunk = "ЧТО ПРОИСХОДИТ У ОСТАЛЬНЫХ"
        case("④б встречный: тело соседа НЕ скопировано в правило (ссылка, не дубль)",
             chunk in nb[0] and chunk not in rule[0],
             "вторая копия текста расходится молча — за это уже плачено")

    print()
    print(f"{'✅ ПОСЛЕДОВАТЕЛЬНОСТЬ ПРИНЯТА' if OK else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
