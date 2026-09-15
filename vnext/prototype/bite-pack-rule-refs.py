#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: правило, названное инструментом ПАКЕТА, обязано быть в правилах пакета
(rules/universal.sql · rules/domain-specific/*.sql) — иначе сосед открывает подсказку
инструмента и получает отказ вместо правила (карточка #647, находка tapas: memory-archive.py
печатал «set-rule.py --key memory-hot-and-archive --show», а пакет ключ не вёз).

ЧТО ИЩЕТ, В ДВУХ ФОРМАХ:
  · «--key <ключ>» — аргумент, который роль буквально наберёт (set-rule.py --key K --show);
  · проза «правило [свода] K» — то же имя, названное текстом инструмента.
Обе формы судятся ТОЛЬКО там, где текст реально доедет до экрана роли: строковый литерал
кода (print/f-string/присвоенная переменная), а не докстрока и не «#»-комментарий — их
роль, позвавшая инструмент, не увидит НИКОГДА (докстрока — не то же самое, что вывод).
Разбор — через ast, а не текстовым поиском по строке: комментарии Python в дерево
разбора не попадают вовсе, докстрока — первое Expr-выражение тела модуля/функции/класса
(та же проверка, что делает ast.get_docstring).

ГРАНИЦА (встречный случай — «не судится»):
  ① ПЛЕЙСХОЛДЕР ПРИМЕРА: «--key <ключ>» / «--key <rule-key>» — форма подсказки в справке
     самого инструмента, а не имя настоящего правила.
  ② ДОКСТРОКА/КОММЕНТАРИЙ — см. выше: не печатный текст, роль его не читает.
Разобрано ГЛАЗАМИ по факту (карточка #647): рабочая табличная форма «ключ → возможные
слова пакета» (`export-rules.py` ORDER, `rules-to-skills.py` PACKAGES, `migrations/*` —
исторические карты отзыва) НИКОГДА не ставит слово «правило» рядом с голым именем ключа
в списке/словаре — только рядом с ПРОЗОЙ, адресованной читателю. Проверено замером
(карточка #647, замер 2026-09-15 — в комментарии карточки): после исключения докстрок/комментариев
и требования соседства слова «правило» с ключом эти таблицы совпадений не дают — граница
не угадана, а замерена.

ИЗВЕСТНЫЙ ОСТАТОК (KNOWN_OPEN ниже) — ключи, которые эта проверка сегодня НАМЕРЕННО
НЕ считает решёнными; если список разойдётся с находкой (новый ключ или один из этих
пропал) — проверка красна, названо поимённо:
  · md-to-sqlite-phased-cutover — Атлас-специфичное разовое событие (переход с md-файлов
    на SQLite, 2026-07/08); новый контур из шаблона рождается уже на SQLite и такого
    перехода не проходит — везти правило в пакет значило бы учить чужую роль истории,
    которой у неё не было. Отсылка печатается в write-message.py (строка про «--md
    ОТКЛОНЁН») — файл правит другой помощник (карточка #647, TASK.md), здесь только названо.
  · core-service-start-and-migrations — НЕ живая отсылка, а самодостаточная ТЕСТОВАЯ
    ФИКСТУРА внутри bite-rights-registry.py (строка ⑲: «источник — ДЕЙСТВУЮЩЕЕ правило
    свода»): пример-таблица для проверки guard-role-standard.py, роль эту строку не читает
    и по ней ничего не открывает. Класс встречного случая шире, чем докстрока/комментарий
    (граница ① и ② выше), но автоматически (по AST) от печатного текста неотличим —
    назван здесь явно, а не угадан регулярным выражением.
"""
from __future__ import annotations

import ast
import re
import sqlite3
import sys
from pathlib import Path

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

HERE = Path(__file__).resolve().parent


def _resolve_pack_root() -> Path:
    """Внутри репозитория-образца (vnext/prototype/…) — HERE.parent.parent, тот же приём,
    что у build-pack-rules-db.py. В РАЗВЁРНУТОМ контуре (файл лежит плоско в его tools/,
    вложенность vnext/prototype потеряна при копировании — см. init-group.py шаг 7б) этот
    путь ничего не значит: падаем на mezo_paths.template_root() — ту же опору, которой уже
    пользуются rules-from-pack.py и guard-seed-rules.py, чтобы найти корень образца (местный
    local.paths / MEZO_TEMPLATE / маркер scripts/init-group.py)."""
    cand = HERE.parent.parent
    if (cand / "rules" / "universal.sql").exists():
        return cand
    try:
        import mezo_paths  # рядом с этим файлом — и в образце, и в развёрнутом контуре
        return mezo_paths.template_root(__file__)
    except SystemExit:
        return cand  # опора не нашлась — вернём кандидата как есть, судить дальше нечем
    except ImportError:
        return cand


PACK_ROOT_DEFAULT = _resolve_pack_root()

KEY_RE = r"[a-zA-Z][a-zA-Z0-9]*(?:-[a-zA-Z0-9]+)+"
PAT_FLAG = re.compile(r"--key[= ]+[\"'`]?(" + KEY_RE + r")")
PAT_PLACEHOLDER = re.compile(r"--key[= ]+[<\[](?:ключ|rule-key|key|имя)", re.I)
PAT_PROSE = re.compile(r"правил[оa]\s+(?:свода\s+)?[`\"']?(" + KEY_RE + r")")

# Атлас-специфичное разовое событие; см. докстрока выше. Единственный сознательно
# оставленный открытым ключ — не молчаливое исключение, а названное решение.
KNOWN_OPEN = {"md-to-sqlite-phased-cutover", "core-service-start-and-migrations"}


# ── ЯДРО: где текст реально доезжает до роли (AST, не текстовый поиск построчно) ──────

def _docstring_nodes(tree: ast.Module) -> set[int]:
    """id() узлов ast.Constant(str), которые ЯВЛЯЮТСЯ докстрокой модуля/функции/класса —
    первым Expr-выражением тела. Те же критерии, что у ast.get_docstring, но для ВСЕХ
    функций/классов файла, не только одного узла."""
    doc_ids: set[int] = set()

    def mark(body):
        if body and isinstance(body[0], ast.Expr):
            v = body[0].value
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                doc_ids.add(id(v))

    mark(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            mark(node.body)
    return doc_ids


def printable_strings(source: str, filename: str):
    """→ [(текст, номер_строки)] для КАЖДОГО строкового литерала файла, КРОМЕ докстрок.
    Комментарии «#» сюда не попадают вовсе — их не видит ast.parse. При синтаксической
    ошибке файла — пустой список (не эта проверка ловит битый файл)."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return []
    skip = _docstring_nodes(tree)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in skip:
                continue
            out.append((node.value, getattr(node, "lineno", 0)))
        elif isinstance(node, ast.JoinedStr):  # f-строка — берём куски-константы
            parts = [v.value for v in node.values
                     if isinstance(v, ast.Constant) and isinstance(v.value, str)]
            if parts:
                out.append(("".join(parts), getattr(node, "lineno", 0)))
    return out


def find_refs(source: str, filename: str):
    """→ [(ключ, номер_строки, форма)] — ссылки на ключи правил в ПЕЧАТНОМ тексте файла."""
    refs = []
    for text, lineno in printable_strings(source, filename):
        for m in PAT_FLAG.finditer(text):
            if PAT_PLACEHOLDER.search(text[max(0, m.start() - 12):m.end() + 4]):
                continue
            refs.append((m.group(1), lineno, "--key"))
        for m in PAT_PROSE.finditer(text):
            refs.append((m.group(1), lineno, "проза"))
    return refs


def load_pack_keys(pack_root: Path) -> set[str]:
    keys: set[str] = set()
    universal = pack_root / "rules" / "universal.sql"
    if universal.exists():
        text = universal.read_text(encoding="utf-8")
        keys |= set(re.findall(r"^\('(" + KEY_RE + r")',", text, re.M))
    dom_dir = pack_root / "rules" / "domain-specific"
    if dom_dir.is_dir():
        for f in sorted(dom_dir.glob("*.sql")):
            text = f.read_text(encoding="utf-8")
            keys |= set(re.findall(r"^\('(" + KEY_RE + r")',", text, re.M))
    return keys


def scan_pack(pack_root: Path):
    """→ [(ключ, файл_относительно_пакета, строка, форма)] для КАЖДОЙ ссылки на ключ,
    которого нет в правилах пакета. Ищет по scripts/ и vnext/prototype/ (сама эта
    приёмка себя не судит — файл с приёмкой не значится в её же списке ссылок)."""
    pack_keys = load_pack_keys(pack_root)
    missing = []
    for d in (pack_root / "scripts", pack_root / "vnext" / "prototype"):
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*.py")):
            if "__pycache__" in f.parts or f.name.endswith(".bak"):
                continue
            if f.name == Path(__file__).name:
                # сама приёмка себя не судит: её фикстуры — не ссылки инструмента.
                # ПО ИМЕНИ, не по resolve(): в развёрнутом контуре сканируемый пакет —
                # ДРУГОЙ файл на диске (образец), с тем же именем, но не тем же путём.
                continue
            try:
                source = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = str(f.relative_to(pack_root))
            for key, lineno, form in find_refs(source, str(f)):
                if key not in pack_keys:
                    missing.append((key, rel, lineno, form))
    return missing


# ── ГАРНИЗОН СЛУЧАЕВ (та же форма, что у соседних bite-*.py: case(), НЕ assert) ────────

CASES = 0
DIFFERENTIATING = 0


def case(title: str, verdict: bool, detail: str, differ: bool = False) -> bool:
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def write_fixture(tmp: Path, universal_keys: list[str], tool_body: str):
    """Синтетический пакет: rules/universal.sql с названными ключами + один файл
    scripts/tool.py с испытуемым телом. Приёмка строит СВОЮ старую фикстуру САМА —
    не берёт «раньше/сейчас» из среды, пакета или клона (норма RULES-HELPER)."""
    (tmp / "rules" / "domain-specific").mkdir(parents=True, exist_ok=True)
    (tmp / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp / "vnext" / "prototype").mkdir(parents=True, exist_ok=True)
    rows = ",\n".join(f"('{k}', 'тело {k}', 'coord', 1)" for k in universal_keys)
    sql = f"INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n{rows};\n"
    (tmp / "rules" / "universal.sql").write_text(sql, encoding="utf-8")
    (tmp / "scripts" / "tool.py").write_text(tool_body, encoding="utf-8")


def main() -> int:
    tmp_root = mezo_stand.new("bite-pack-rule-refs-")
    ok = True

    # ① --key реального отсутствующего ключа — обязан найтись, с файлом и строкой.
    tmp = tmp_root / "c1"
    write_fixture(tmp, ["present-rule"], (
        "# -*- coding: utf-8 -*-\n"
        "def show():\n"
        "    print('   python set-rule.py --key absent-rule --show')\n"
    ))
    found = scan_pack(tmp)
    ok &= case("① --key отсутствующего правила — найден с именем и строкой",
               [x[0] for x in found] == ["absent-rule"] and found[0][2] == 3,
               f"найдено: {found}", differ=True)

    # ② проза «правило свода K» отсутствующего ключа — обязана найтись.
    tmp = tmp_root / "c2"
    write_fixture(tmp, ["present-rule"], (
        "# -*- coding: utf-8 -*-\n"
        "def show():\n"
        "    out = []\n"
        "    out.append('РИТМ: правило свода absent-rule не активно')\n"
        "    return out\n"
    ))
    found = scan_pack(tmp)
    ok &= case("② проза «правило свода K» отсутствующего правила — найдена",
               [x[0] for x in found] == ["absent-rule"],
               f"найдено: {found}", differ=True)

    # ③ ВСТРЕЧНЫЙ: «--key <ключ>» — плейсхолдер примера, не реальное имя — НЕ судится.
    tmp = tmp_root / "c3"
    write_fixture(tmp, ["present-rule"], (
        "# -*- coding: utf-8 -*-\n"
        "USAGE = 'python set-rule.py --key <ключ> --show'\n"
    ))
    found = scan_pack(tmp)
    ok &= case("③ встречный: «--key <ключ>» плейсхолдер — не судится",
               found == [],
               f"найдено (ждали пусто): {found}", differ=True)

    # ④ ВСТРЕЧНЫЙ: ключ упомянут ТОЛЬКО в докстроке — не судится (роль текст не увидит).
    tmp = tmp_root / "c4"
    write_fixture(tmp, ["present-rule"], (
        "# -*- coding: utf-8 -*-\n"
        '"""ЗАЧЕМ: связано с правилом свода absent-rule (история решения)."""\n'
        "def show():\n"
        "    pass\n"
    ))
    found = scan_pack(tmp)
    ok &= case("④ встречный: ключ только в докстроке модуля — не судится",
               found == [],
               f"найдено (ждали пусто): {found}", differ=True)

    # ⑤ ВСТРЕЧНЫЙ: ключ упомянут ТОЛЬКО в «#»-комментарии — не судится (то же основание).
    tmp = tmp_root / "c5"
    write_fixture(tmp, ["present-rule"], (
        "# -*- coding: utf-8 -*-\n"
        "# история: правило свода absent-rule когда-то это решало\n"
        "def show():\n"
        "    pass\n"
    ))
    found = scan_pack(tmp)
    ok &= case("⑤ встречный: ключ только в «#»-комментарии — не судится",
               found == [],
               f"найдено (ждали пусто): {found}", differ=True)

    # ⑥ КОНТРОЛЬ: ключ, который И назван, И есть в пакете — молчание.
    tmp = tmp_root / "c6"
    write_fixture(tmp, ["present-rule"], (
        "# -*- coding: utf-8 -*-\n"
        "def show():\n"
        "    print('   python set-rule.py --key present-rule --show')\n"
    ))
    found = scan_pack(tmp)
    ok &= case("⑥ контроль: ключ есть в пакете — не судится (иначе проверка красит всё подряд)",
               found == [],
               f"найдено (ждали пусто): {found}", differ=True)

    # ⑦ НАРОЧНАЯ ПОЛОМКА: убрать ОДНО правило из копии правил пакета → называет ровно его.
    tmp = tmp_root / "c7"
    write_fixture(tmp, ["rule-a", "rule-b"], (
        "# -*- coding: utf-8 -*-\n"
        "def show():\n"
        "    print('   python set-rule.py --key rule-a --show')\n"
        "    print('   python set-rule.py --key rule-b --show')\n"
    ))
    (tmp / "rules" / "universal.sql").write_text(
        "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES\n"
        "('rule-a', 'тело rule-a', 'coord', 1);\n", encoding="utf-8")  # rule-b УБРАНО
    found = scan_pack(tmp)
    ok &= case("⑦ нарочная поломка: убрано rule-b из копии правил — названо ровно оно",
               [x[0] for x in found] == ["rule-b"],
               f"найдено: {found}", differ=True)

    # ⑧ ЖИВОЙ СЛУЧАЙ: настоящий пакет (PACK_ROOT). Единственный сознательно открытый
    # ключ — KNOWN_OPEN (см. докстрока файла); любой ДРУГОЙ ключ здесь — новая находка.
    real = scan_pack(PACK_ROOT_DEFAULT)
    real_keys = sorted({x[0] for x in real})
    unexpected = sorted(set(real_keys) - KNOWN_OPEN)
    still_missing_known = sorted(KNOWN_OPEN - set(real_keys))
    detail = (f"найдены ключи: {real_keys or '(пусто)'} · KNOWN_OPEN: {sorted(KNOWN_OPEN)} · "
              f"неожиданные (новая находка): {unexpected or '—'} · "
              f"KNOWN_OPEN, которых сейчас НЕТ (список устарел): {still_missing_known or '—'}")
    ok &= case("⑧ живой пакет: ссылок сверх KNOWN_OPEN нет",
               not unexpected and not still_missing_known,
               detail, differ=True)
    if real:
        print("   подробности живого случая:")
        for key, rel, lineno, form in real:
            print(f"      {key:34} {rel}:{lineno} [{form}]")

    print()
    if ok:
        print(f"✅ ПРОВЕРКА ПРИНЯТА — случаев {CASES}, различающих {DIFFERENTIATING}")
    else:
        print("🔴 ПРОВЕРКА НЕ ПРИНЯТА")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
