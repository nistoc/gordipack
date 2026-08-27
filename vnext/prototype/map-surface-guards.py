# -*- coding: utf-8 -*-
"""map-surface-guards.py — карта учащих поверхностей: «поверхность → сторож» (заход 4 ⑥).

ЗАЧЕМ. Зелёное по слепоте живёт в ЗАЗОРЕ между поверхностями: каждый сторож честен
в своей границе, а поверхность, не приписанная никому, не красна НИКОГДА — и это
не видно ниоткуда. Карта делает пустую клетку ВИДИМОЙ строкой, а не отсутствием строки.

ТРИ состояния клетки — и все печатаются:
  · сторож(а) поимённо — файлы проверяются на существование (протухшее имя = красное);
  · «⚠️ БЕЗ СТОРОЖА» — честный долг, кандидат на подсадку захода ⑦;
  · «не сужу: причина» — осознанный отказ, пустой клеткой НЕ считается.

ОБРАТНАЯ СВЕРКА — ПО ОБЪЯВЛЕНИЮ, НЕ ПО ПРОЗЕ. Первая редакция искала якорные слова
в шапках сторожей и дала 14 ложных красных из 14: упоминание границы («память — зона
соседа») читалось как объявление зоны. Упоминание ≠ объявление — судить по виду нельзя.
Контракт: сторож несёт машинную строку `# SURFACES: <ключи через пробел>` в первых
40 строках. Есть строка → сверка В ОБЕ СТОРОНЫ (объявил чужое карте → красное; карта
приписала, а он не объявил → красное). Нет строки → счётом «без машинного объявления»,
односторонняя сверка — это названо, не спрятано.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

NOT_JUDGED = object()

# ── карта: (поверхность, машинный ключ, сторожа | (NOT_JUDGED, причина) | None) ──
MAP = [
    ("канон контейнера (CLAUDE.md — формы вызова, сокращение <s>)",
     "canon", ["guard-printed-forms.py"]),
    ("свод правил (rules.body, active)",
     "rules", ["guard-printed-forms.py", "guard-rule-expiry.py", "check-rule-basis.py"]),
    ("наказы-файлы (scheduled-tasks/*/SKILL.md)",
     "tasks", ["guard-printed-forms.py"]),
    ("память ролей (phoenix: формы вызова в слепках)",
     "phoenix", ["guard-launcher-forms.py"]),
    ("живые скрипты: печатаемые ими строки и справка",
     "printed", ["guard-printed-forms.py", "bite-plain-words.py",
                 "check-false-signature.py"]),
    ("витрины generated/ (порождаются из БД)",
     "vitrina", ["guard-printed-forms.py"]),
    ("документы образца (*.md в git образца)",
     "template-docs", ["measure-docs-retired.py", "guard-machine-paths.py"]),
    ("файлы навыков (порождаются rules-to-skills)",
     "skills", ["guard-skills-fresh.py"]),
    ("лента и история (messages, messages_history)",
     "feed", (NOT_JUDGED, "история не переписывается; цитаты старых форм в телах нот — "
                          "история, не учение (граница guard-printed-forms)")),
    ("шаблоны ролей (таблица templates)",
     "role-templates", None),          # ⚠️ БЕЗ СТОРОЖА — честная пустая клетка
    ("тела карточек backlog (учат рецептом внутри карточки)",
     "backlog-bodies", None),          # ⚠️ БЕЗ СТОРОЖА
]

DECLARE = re.compile(r"^#\s*SURFACES:\s*(.+)$", re.M)


def declared_surfaces(guard_file: Path):
    """Машинное объявление сторожа; None — строки нет (не то же, что «пусто»)."""
    head = "\n".join(guard_file.read_text(encoding="utf-8",
                                          errors="replace").splitlines()[:40])
    m = DECLARE.search(head)
    return set(m.group(1).split()) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tools", default=None, help="каталог проверок (по умолчанию — свой)")
    a = ap.parse_args()
    tools = Path(a.tools) if a.tools else HERE

    red, empty, undeclared = 0, 0, []
    print("КАРТА «ПОВЕРХНОСТЬ → ПРОВЕРКА» — клеток:", len(MAP))
    guard_keys = {}                     # файл сторожа → ключи, приписанные картой
    for surface, key, guards in MAP:
        if guards is None:
            empty += 1
            print(f"⚠️ БЕЗ ПРОВЕРКИ  · {surface}")
        elif isinstance(guards, tuple) and guards[0] is NOT_JUDGED:
            print(f"·  не сужу      · {surface}\n      причина: {guards[1]}")
        else:
            missing = [g for g in guards if not (tools / g).exists()]
            for g in guards:
                guard_keys.setdefault(g, set()).add(key)
            mark = "🔴" if missing else "✅"
            red += len(missing)
            print(f"{mark} {', '.join(guards)}  ← {surface}")
            for g in missing:
                print(f"      🔴 файла проверки НЕТ: {g} — имя протухло, клетка ЛЖЁТ о покрытии")

    known_keys = {key for _s, key, _g in MAP}
    for g, keys in sorted(guard_keys.items()):
        gp = tools / g
        if not gp.exists():
            continue
        decl = declared_surfaces(gp)
        if decl is None:
            undeclared.append(g)
            continue
        for k in sorted(decl - keys):
            red += 1
            где = "ключ неизвестен карте вовсе" if k not in known_keys else \
                  "карта эту связь не держит"
            print(f"🔴 проверка {g} объявляет поверхность «{k}» — {где}")
        for k in sorted(keys - decl):
            red += 1
            print(f"🔴 карта приписывает {g} поверхность «{k}», а сама проверка её НЕ объявляет")
    if undeclared:
        print(f"· без машинного объявления SURFACES: {len(undeclared)} "
              f"({', '.join(undeclared)}) — сверка по ним односторонняя")

    print(f"\nитого: клеток {len(MAP)} · пустых {empty} · красных {red}")
    if empty:
        print("⚠️ пустая клетка — это ДОЛГ захода ⑦ (подсадка дефекта), а не фон.")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
