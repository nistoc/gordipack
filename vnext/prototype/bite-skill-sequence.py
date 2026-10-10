# -*- coding: utf-8 -*-
# PLANTS: skills
"""ПРИЁМКА последовательности правки общих текстов (заход 4 ⑧).

Испытуемые: правило свода `shared-text-edit-sequence` (источник) и порождённый из него
навык atlas-shared-edit (витрина). Последовательность держалась памятью одной роли —
теперь она в своде, а здесь доказывается, что: якоря на месте · команды навыка судимы
проверкой печатных форм без красного · склейка контроля с отправкой в `&&` ловится ·
правило ССЫЛАЕТСЯ на соседей, а не копирует их тела.

Якоря шагов берутся из ДЕЙСТВУЮЩЕЙ редакции правила, а не списком в коде (карточка #692):
список в коде пережил правку правила v2 (2026-10-06: ③ «СВЕДИ ПАРУ» → «COMMIT ПО ИМЕНАМ
ФАЙЛОВ») и судил навык по снятому шагу.
"""
import importlib.util
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402

SKILL = mezo_paths.container_root() / ".claude" / "skills" / "atlas-shared-edit" / "SKILL.md"
GUARD = HERE / "guard-printed-forms.py"
CANON = mezo_paths.container_root() / "CLAUDE.md"

# Строка шага в правиле: «① ОБЪЯВИ И ПРАВЬ БЕЗОПАСНО — …», «③ COMMIT ПО ИМЕНАМ ФАЙЛОВ (…)».
# Якорь — заглавная часть после номера шага, до первого знака, который не буква и не пробел.
STEP_RE = re.compile(r"^\s*[①②③④⑤⑥⑦⑧⑨]\s+([A-ZА-ЯЁ][A-ZА-ЯЁ ]*[A-ZА-ЯЁ])")

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


def rule_anchors(rule_body):
    """Якоря шагов из текста правила — по строкам, начинающимся с номера шага."""
    return [m.group(1).strip() for l in rule_body.splitlines() if (m := STEP_RE.match(l))]


def skill_verdicts(text, anchors, judge):
    """Случаи ①②③ над текстом навыка: {номер: (держится, пояснение)}.
    Одна функция и для живого навыка, и для его копии с нарочной поломкой —
    иначе поломка испытывала бы не тот суд, что живой."""
    lines = text.splitlines()
    missing = [a for a in anchors if a not in text]
    if not anchors:
        one = (False, "из правила не извлечено ни одного шага «① …» — сверять навык не с чем")
    else:
        one = (not missing, "нет: " + ", ".join(missing) if missing else " → ".join(anchors))
    red = judge(lines)
    return {"①": one,
            "②": (not red, " · ".join(k for k, _ in red[:3])),
            "③": (not seq_flaw(lines), "")}


def main() -> int:
    if not SKILL.exists():
        print(f"⛔ навыка нет: {SKILL} — приёмке нечего судить (это НЕ «зелёное»)")
        return 2
    text = SKILL.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    con = sqlite3.connect(f"file:{mezo_paths.live_db().as_posix()}?mode=ro", uri=True)
    rule = con.execute("SELECT body FROM rules WHERE rule_key='shared-text-edit-sequence' "
                       "AND status='active'").fetchone()
    nb = con.execute("SELECT body FROM rules WHERE rule_key='tool-edit-announce'").fetchone()
    con.close()
    anchors = rule_anchors(rule[0]) if rule else []

    spec = importlib.util.spec_from_file_location("gpf_seq", GUARD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    defs = mod.canon_defs(CANON) or {}
    known = ({p.name for p in mezo_paths.live_scripts().glob("*.py")}
             | {p.name for p in HERE.glob("*.py")})

    def judge(ls):
        return [(k, f) for _i, k, f in mod.judged_lines(ls, known, HERE, defs)
                if k.startswith("🔴")]

    live = skill_verdicts(text, anchors, judge)
    case(f"① якоря шагов ДЕЙСТВУЮЩЕЙ редакции правила на месте в навыке ({len(anchors)} шт.)",
         *live["①"])

    # ①б Встречный к источнику якорей: в копии ПРАВИЛА шаг ③ возвращён к редакции v1.
    # Если якоря действительно идут из правила, живой навык обязан провалить ①
    # и назвать ровно возвращённый шаг; список в коде этого не увидел бы.
    if rule:
        old_body = re.sub(r"^(\s*③\s+)[A-ZА-ЯЁ][A-ZА-ЯЁ ]*[A-ZА-ЯЁ]", r"\1СВЕДИ ПАРУ",
                          rule[0], count=1, flags=re.M)
        old = skill_verdicts(text, rule_anchors(old_body), judge)["①"]
        case("①б встречный: копия правила с прежним шагом ③ «СВЕДИ ПАРУ» → ① на живом навыке "
             "проваливается и называет его",
             not old[0] and old[1] == "нет: СВЕДИ ПАРУ", old[1])

    # ①в Нарочная поломка: каждый якорь по очереди снят из КОПИИ навыка —
    # проваливается ровно ① и называет ровно снятый якорь; ② и ③ держатся.
    stray = []
    for a in anchors:
        broken = skill_verdicts(text.replace(a, ""), anchors, judge)
        failed = {n for n, (ok, _d) in broken.items() if not ok}
        if failed != {"①"} or broken["①"][1] != "нет: " + a:
            stray.append(f"«{a}»: провалились {sorted(failed) or 'никто'} · {broken['①'][1]}")
    case(f"①в поломка: якорь снят из копии навыка ({len(anchors)} раз по одному) → "
         "проваливается РОВНО ① и называет снятый",
         bool(anchors) and not stray, " | ".join(stray[:2]))

    case("② команды навыка судимы проверкой печатных форм → 0 красных", *live["②"])

    case("③ живой навык: контроль заглушек НЕ склеен с другим шагом через `&&`", *live["③"])

    dirty = [l if "guard-machine-paths" not in l else
             "python <КОНТУР>/vnext/tools/sync-vnext-pair.py --apply && " + l.strip()
             for l in lines]
    case("③б подсадка: сведение и контроль склеены `&&` → признак краснеет",
         bool(seq_flaw(dirty)),
         "контроль в одной строке с отправкой не успевает её остановить")

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
