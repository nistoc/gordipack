"""
guard-printed-names.py — признак: НАДПИСЬ, КОТОРУЮ ПЕЧАТАЕТ МЕХАНИЗМ, РАСХОДИТСЯ С МЕХАНИЗМОМ.

═══ ЗАЧЕМ ═══
Поручение владельца 2026-08-07 10:10 UTC (через @CORE, записка #3148):
    «Прошу тебя сообщить об этом к coord, чтобы он вместе с proto это поправили»
Речь о классе **«врёт не код, а текст, который код печатает»**. Шесть экземпляров за двое суток,
все в наших зонах, и НИ ОДИН не пойман прогоном: каждый нашёлся, когда роль сравнила надпись
с поведением РУКАМИ. У справок и подписей не было НИ ОДНОЙ автоматической проверки — не мало, ноль.

═══ ⚖️ ГРАНИЦА — ПЕЧАТАЕТСЯ ПРИЗНАКОМ ЖЕ, А НЕ ТОЛЬКО ЗДЕСЬ ═══
Признак ловит ТРИ экземпляра из шести. Молчание признака НЕ ОЗНАЧАЕТ «ложных строк нет».
Не выдавать частичное покрытие за полное — это тот самый класс, за который контур платил
сегодня: разовая подчистка данных выдала себя за починку механизма и продержалась месяц.

    ЛОВИТ                                   НЕ ЛОВИТ
    ① справка --db «обязателен»    (Б)      ③ «--limit здесь ни при чём» — ложная ПРИЧИНА
    ② справка --to «задан полем»   (Г)      ④ «умрёт с чатом» — ложный СРОК
    ⑥ «--done-when обязателен»     (Б)      ⑤ поправлен ПЕРЕСКАЗЧИК, а не источник

🪤 Первая редакция этого предмета обещала «четыре из шести» и включала ③ — там есть подстрока
   «--limit», и глаз принял её за имя. **Совпадение формы приняло себя за совпадение смысла.**
   Ровно так и завышают покрытие: считают по виду строки, а не по тому, ЧЕМ она врёт.

═══ ЧЕТЫРЕ ПРАВИЛА ═══
  А. ИМЯ, КОТОРОГО НЕТ — текст называет флаг/таблицу/колонку, которых не существует.
  Б. ОБЯЗАТЕЛЬНОСТЬ БЕЗ ПРИНУЖДЕНИЯ — текст говорит «обязателен», код не требует и не отказывает.
  В. КАНОН ГОВОРИТ ЗА ВСЕХ, ИСПОЛНЯЮТ НЕ ВСЕ — общее правило объявлено от имени всех
     инструментов, часть ведёт себя иначе.
  Г. ЗНАЧЕНИЕ ПРОСЯТ И ВЫБРАСЫВАЮТ — флаг принимает значение, а код смотрит только,
     задан ли он. Читающий справку уверен, что его значение куда-то легло. Оно никуда не легло.

Запуск:  python C:/guts/.atlas/vnext-tools/guard-printed-names.py
         [--dir <папка со скриптами>] [--quiet]
Выход:   0 — находок нет · 1 — есть находки · 2 — не смог прочитать предмет
"""

import argparse
import ast
import re
import sqlite3
import sys
from pathlib import Path

SCRIPTS = Path(r"C:\guts\.atlas\.mezosync\scripts")
LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")

FLAG_RE = re.compile(r"--[a-z][a-z0-9-]*")
SCRIPT_RE = re.compile(r"\b([a-z][a-z0-9_-]*\.py)\b")
# Идентификатор БД называют либо в обратных кавычках, либо сразу за словом-указателем.
IDENT_RE = re.compile(
    r"(?:`([a-z][a-z0-9_]*)`|"
    r"(?:поле|поля|полю|колонк\w*|таблиц\w*|признак)\s+([a-z][a-z0-9_]{3,}))")
MUST_RE = re.compile(r"обязател|обязан|нельзя без|required|требуется указать", re.I)


# ─────────────────────────────────────────────────────────────────────────────
def db_identifiers() -> set:
    """Имена таблиц и колонок живой базы. ТОЛЬКО ЧТЕНИЕ — три замка, как у перископа."""
    names = set()
    if not LIVE_DB.exists():
        return names
    con = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')"):
        names.add(t)
        for r in con.execute(f"PRAGMA table_info([{t}])"):
            names.add(r[1])
    con.close()
    return names


class Tool:
    """Один инструмент: что он ОБЪЯВЛЯЕТ и что ПЕЧАТАЕТ. Разбор кодом, не глазами."""

    def __init__(self, path: Path):
        self.path = path
        self.tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        self.flags = {}      # "--to" -> {"required": bool, "takes_value": bool, "dest": str}
        self.texts = []      # (lineno, kind, text)
        self.py_names = set()
        # 🪤 Имя переменной с разобранными доводами БЕРЁТСЯ ИЗ КОДА, а не считается «args».
        #    Первая редакция зашила «args» — и укус тут же поймал: образец назвал её `a`,
        #    правило Г промолчало. Признак, слепой к чужому стилю, тих там, где должен
        #    кричать, а тихий признак читается как «чисто».
        self.arg_vars = self._parse_args_targets()
        self._walk()

    def _parse_args_targets(self) -> set:
        names = {"args"}
        for node in ast.walk(self.tree):
            if not isinstance(node, ast.Assign):
                continue
            call = node.value
            if isinstance(call, ast.Call) and getattr(call.func, "attr", None) == "parse_args":
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
        return names

    # ── что объявлено ───────────────────────────────────────────────────────
    def _walk(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Name):
                self.py_names.add(node.id)
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                self.py_names.add(node.name)
            elif isinstance(node, ast.Call):
                fn = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if fn == "add_argument":
                    self._add_argument(node)
                elif fn in ("ArgumentParser", "add_parser"):
                    self._collect_kwargs(node, ("description", "epilog", "help"))
                elif fn == "print":
                    for a in node.args:
                        if isinstance(a, ast.Constant) and isinstance(a.value, str):
                            self.texts.append((a.lineno, "print", a.value))
                        elif isinstance(a, ast.JoinedStr):   # f-строка
                            self.texts.append((a.lineno, "print", self._join(a)))

    def _add_argument(self, node: ast.Call):
        names = [a.value for a in node.args
                 if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        flags = [n for n in names if n.startswith("--")]
        kw = {k.arg: k.value for k in node.keywords}
        action = kw.get("action")
        action_v = action.value if isinstance(action, ast.Constant) else None
        required = isinstance(kw.get("required"), ast.Constant) and kw["required"].value is True
        takes_value = action_v not in ("store_true", "store_false", "count", "store_const")
        dest = None
        if isinstance(kw.get("dest"), ast.Constant):
            dest = kw["dest"].value
        elif flags:
            dest = flags[0][2:].replace("-", "_")
        for f in flags:
            self.flags[f] = {"required": required, "takes_value": takes_value,
                             "dest": dest, "lineno": node.lineno}
        h = kw.get("help")
        if isinstance(h, ast.Constant) and isinstance(h.value, str):
            self.texts.append((node.lineno, f"help {flags[0] if flags else ''}".strip(),
                               h.value))

    def _collect_kwargs(self, node: ast.Call, keys):
        for k in node.keywords:
            if k.arg in keys and isinstance(k.value, ast.Constant) \
                    and isinstance(k.value.value, str):
                self.texts.append((k.value.lineno, k.arg, k.value.value))

    @staticmethod
    def _join(node: ast.JoinedStr) -> str:
        return "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))

    # ── правило Г: значение просят и выбрасывают ────────────────────────────
    def value_thrown_away(self, dest: str) -> bool:
        """True, если args.<dest> встречается ТОЛЬКО как «задан или нет»."""
        uses, bool_uses = 0, 0
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Attribute) and node.attr == dest \
                    and isinstance(node.value, ast.Name) and node.value.id in self.arg_vars:
                uses += 1
        for node in ast.walk(self.tree):
            # 🪤 Только УСЛОВИЕ ветвления — истинностный контекст. Первая редакция считала
            #    таким и ast.BoolOp где угодно, и оговорила 5 инструментов зря: `args.body
            #    or read(args.file)` — это ВЫЧИСЛЕНИЕ ЗНАЧЕНИЯ, а не проверка «задан ли».
            #    Признак, объявляющий ложь там, где её нет, — сам экземпляр своего класса.
            if not isinstance(node, (ast.If, ast.IfExp, ast.While)):
                continue
            for t in [node.test]:
                for sub in ast.walk(t):
                    if isinstance(sub, ast.Attribute) and sub.attr == dest \
                            and isinstance(sub.value, ast.Name) and sub.value.id in self.arg_vars:
                        bool_uses += 1
        return uses > 0 and uses == bool_uses


# ─────────────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(SCRIPTS), help="папка с инструментами")
    ap.add_argument("--quiet", action="store_true", help="только находки, без сводки")
    args = ap.parse_args()

    root = Path(args.dir)
    files = sorted(root.glob("*.py"))
    if not files:
        print(f"⛔ не нашёл ни одного инструмента в {root}")
        return 2

    tools, broken = {}, []
    for f in files:
        try:
            tools[f.name] = Tool(f)
        except SyntaxError as e:
            broken.append((f.name, e))

    all_flags = {}
    for name, t in tools.items():
        for fl in t.flags:
            all_flags.setdefault(fl, set()).add(name)
    idents = db_identifiers()

    findings = []   # (правило, файл, строка, что, пояснение)

    for name, t in tools.items():
        for lineno, kind, text in t.texts:
            named_scripts = {s for s in SCRIPT_RE.findall(text) if s in tools}

            # ── А: флаг, которого нет ────────────────────────────────────────
            for fl in set(FLAG_RE.findall(text)):
                if fl in t.flags:
                    continue
                if any(fl in tools[s].flags for s in named_scripts):
                    continue          # текст явно про ДРУГОЙ инструмент и там флаг есть
                if fl in all_flags:
                    continue          # флаг существует где-то ещё, инструмент не назван — слабо
                findings.append(("А", name, lineno,
                                 f"текст называет флаг {fl}",
                                 f"такого флага нет НИ В ОДНОМ инструменте · [{kind}]"))

            # ── А: имя таблицы/колонки, которого нет в базе ──────────────────
            if idents:
                for m in IDENT_RE.finditer(text):
                    tok = m.group(1) or m.group(2)
                    if not tok or "_" not in tok:
                        continue
                    if tok in idents or tok in t.py_names:
                        continue
                    if tok.endswith(".py") or tok in tools:
                        continue
                    findings.append(("А", name, lineno,
                                     f"текст называет поле/таблицу «{tok}»",
                                     f"такого имени в базе НЕТ · [{kind}]"))

            # ── Б: обязательность без принуждения ────────────────────────────
            if MUST_RE.search(text):
                # 🪤 Подпись флага говорит о СЕБЕ и своего имени не повторяет: «критерий
                #    приёмки … (обязателен по слову владельца)» — слова «--done-when» в ней
                #    нет. Первая редакция искала имя только ВНУТРИ текста и потому молчала
                #    на самом свежем экземпляре класса. Предмет подписи — тот флаг, к
                #    которому она прикреплена, и он обязан считаться названным.
                subject = set(FLAG_RE.findall(text))
                if kind.startswith("help "):
                    subject.add(kind.split(" ", 1)[1])
                for fl in subject:
                    info = t.flags.get(fl)
                    if info and not info["required"]:
                        findings.append(("Б", name, lineno,
                                         f"текст объявляет {fl} обязательным",
                                         f"код НЕ требует (объявлен на строке "
                                         f"{info['lineno']} без required) · [{kind}]"))

    # ── Г: значение просят и выбрасывают ────────────────────────────────────
    for name, t in tools.items():
        for fl, info in t.flags.items():
            if info["takes_value"] and info["dest"] and t.value_thrown_away(info["dest"]):
                findings.append(("Г", name, info["lineno"],
                                 f"{fl} принимает ЗНАЧЕНИЕ, а код смотрит только «задан или нет»",
                                 "значение читающего никуда не ложится"))

    # ── В: канон говорит за всех — исполняют не все ─────────────────────────
    for name, t in tools.items():
        info = t.flags.get("--db")
        if info and info["required"]:
            findings.append(("В", name, info["lineno"],
                             "--db объявлен ОБЯЗАТЕЛЬНЫМ",
                             "канон гласит «--db НЕОБЯЗАТЕЛЕН с 26.07 (R15a), резолвится "
                             "от расположения скрипта» — роль, поверившая канону, получит отказ"))

    # ── ВЫВОД ───────────────────────────────────────────────────────────────
    if not args.quiet:
        print("ПРИЗНАК: надпись механизма расходится с механизмом")
        print(f"предмет ........ {root}  ({len(tools)} инструментов, "
              f"{sum(len(t.texts) for t in tools.values())} печатаемых строк)")
        print(f"имён в базе .... {len(idents)}")
        if broken:
            print(f"⚠️ не разобрал: {', '.join(n for n, _ in broken)}")
        print()

    RULE = {"А": "ИМЯ, КОТОРОГО НЕТ", "Б": "ОБЯЗАТЕЛЬНОСТЬ БЕЗ ПРИНУЖДЕНИЯ",
            "В": "КАНОН ГОВОРИТ ЗА ВСЕХ, ИСПОЛНЯЮТ НЕ ВСЕ",
            "Г": "ЗНАЧЕНИЕ ПРОСЯТ И ВЫБРАСЫВАЮТ"}
    for rule in ("А", "Б", "В", "Г"):
        got = [f for f in findings if f[0] == rule]
        if not got:
            continue
        print(f"🔴 ПРАВИЛО {rule} — {RULE[rule]}  ({len(got)})")
        for _, name, lineno, what, why in got:
            print(f"   {name}:{lineno}")
            print(f"      {what}")
            print(f"      ↳ {why}")
        print()

    print("⚖️ ЧЕГО ЭТОТ ПРИЗНАК НЕ ЛОВИТ — молчание выше НЕ означает «ложных строк нет»:")
    print("   · ложную ПРИЧИНУ («--limit здесь ни при чём», когда он ровно при чём)")
    print("   · ложный СРОК («умрёт с чатом» о том, что переживает чат)")
    print("   · подмену источника пересказчиком (поправлен тот, кто повторил, а не тот, кто сказал)")
    print("   Эти три сорта находятся только глазами. Признак закрывает 3 экземпляра из 6.")

    print(f"\nИТОГ: {'🔴 находок ' + str(len(findings)) if findings else '✅ находок нет'}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
