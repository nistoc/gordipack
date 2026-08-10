#!/usr/bin/env python3
"""Признак: НАПЕЧАТАННАЯ КОМАНДА ВЕДЁТ В ПУСТОТУ.

Повод — заявка CORE (карточка #161, 2026-08-10 13:06 UTC). Строка пробуждения CORE
приказывала звать гейт как `C:\\guts\\.atlas\\atlas.core\\askgate.ps1 -Full`. Файла по этому
пути нет — он живёт в `.run/`. Отказ пришёл кодом 127, то есть громко, но стоял он ровно
в разделе, который сам предупреждает про третий исход «НЕ ЗАПУСТИЛАСЬ»: роль, звавшая гейт
через конвейер (а он печатает сотни строк), увидела бы пустоту вместо красного.

🎯 ЧЕМ ЭТОТ ПРИЗНАК ОТЛИЧАЕТСЯ ОТ УЖЕ ЖИВУЩЕГО «форма вызова». Тот судит ФОРМУ —
абсолютный путь против относительного — и на этой команде молчал бы вечно: форма
безупречна, путь абсолютен, цели не существует. Форма и существование — разные свойства,
и второе до сегодня не проверял никто.

⚖️ ГРАНИЦА, НАЗЫВАЮ ВСЛУХ: признак проверяет РОВНО ОДНО — что вызываемый файл есть на диске.
«Файл есть, но делает не то», «ключ переименован», «скрипт упадёт на этих данных» он не ловит
и ловить не может. Это НЕ проверка работоспособности команды.

⚠️ ЗОНЫ РАЗНЫЕ, ПОЭТОМУ И ЦВЕТ РАЗНЫЙ:
  🔴 источники и §launcher — их пишет PROTO (реестр зон v12 от 2026-08-10): чинятся здесь же;
  🟡 прочие секции слепков — их пишет сама роль: показываем, но не красим, иначе вечно-красный
     сторож обесценится (урок ⑪ контура).
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

import mezo_paths

# Строка не приказывает, а ПРЕДОСТЕРЕГАЕТ — судим по тому, что она делает с читателем.
# Тот же приём, что в признаке «форма вызова»: иначе роль, записавшая урок «⛔ не зови так:
# <несуществующий путь>», получала бы красное ЗА ПРАВИЛЬНО ЗАПИСАННЫЙ УРОК.
COUNTER_RE = re.compile(
    r"⛔|✗|❌|⚰️|\bНЕ\s|\bне\s+зов|нельзя|запрещ|падает|неверн|ошибочн|было:|вместо"
    r"|прежн|устарел|надгроб|файла нет|не существует",
    re.IGNORECASE)

# Путь Windows с расширением исполняемого. Кавычки и завершающая пунктуация срезаются ниже.
PATH_RE = re.compile(r"""([A-Za-z]:[\\/][^\s"'`,;)\]]+\.(?:py|ps1|cmd|bat|sh))""")

# Заглушка вместо настоящего пути — не находка, а форма обучения.
# ⚡ `*` добавлена по BASELINE 2026-08-10 13:38 UTC: обе первые находки оказались МАСКОЙ
# (`vnext-tools/guard-*.py` у RCC) — то есть указанием на НАБОР файлов, а не на файл.
# Маска не может «существовать»; краснеть на ней — обвинять верную запись.
PLACEHOLDER_RE = re.compile(r"[<>{}*]|\.\.\.|ПУТЬ|ФАЙЛ|нота\.md", re.IGNORECASE)


def calls_in(text):
    """→ [(строка, путь)] по приказывающим строкам. Контекст живёт в СТРОКЕ:
    поиск по всему тексту разом теряет его и обвиняет предостережения."""
    out = []
    for line in (text or "").splitlines():
        if COUNTER_RE.search(line):
            continue
        for m in PATH_RE.finditer(line):
            target = m.group(1).rstrip(".,;:)»\"'`")
            if PLACEHOLDER_RE.search(target):
                continue
            out.append((line.strip(), target))
    return out


def scan_text(label, text, sink):
    for line, target in calls_in(text):
        if not Path(target).exists():
            sink.append((label, target, line))


def run(db_path, prompts_dir, verbose=False):
    scripts = mezo_paths.mezo_root(__file__) / "scripts"
    red, yellow = [], []

    # ① ИСТОЧНИКИ — то, что роль читает первым и копирует себе.
    sources = [
        ("CLAUDE.md", mezo_paths.container_root(__file__) / "CLAUDE.md"),
        ("read-phoenix.py", scripts / "read-phoenix.py"),
    ]
    if prompts_dir and Path(prompts_dir).is_dir():
        for p in sorted(Path(prompts_dir).glob("*.md")):
            sources.append((f"prompts/{p.name}", p))
    for label, path in sources:
        if path.exists():
            scan_text(label, path.read_text(encoding="utf-8"), red)

    # ② СЛЕПКИ. §launcher — зона PROTO (строка пробуждения), остальное — зона роли.
    conn = sqlite3.connect(db_path)
    for role, section, body in conn.execute("SELECT role, section, body FROM phoenix"):
        sink = red if section.lower() == "launcher" else yellow
        scan_text(f"{role}/{section}", body, sink)
    conn.close()

    for label, target, line in red:
        print(f"   🔴 ЦЕЛИ НЕТ [{label}] {target}")
        if verbose:
            print(f"        строка: {line[:120]}")
    for label, target, line in yellow:
        print(f"   🟡 цели нет [{label}] {target} — правит роль-владелец слепка")
        if verbose:
            print(f"        строка: {line[:120]}")

    ok = not red
    print(("✅" if ok else "🔴") + f" цели команд: 🔴 {len(red)} · 🟡 {len(yellow)}"
          + ("" if ok else " — напечатанная команда ведёт в пустоту"))
    print("   ⚖️ проверено РОВНО одно: файл есть на диске. «Есть, но делает не то» — не ловится")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="Проверить, что напечатанные команды ведут к существующим файлам")
    ap.add_argument("--db", default=None)
    ap.add_argument("--prompts", default=None,
                    help="каталог с промптами пересоздания (по умолчанию — штатный)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    db = str(mezo_paths.resolve_db(a.db, __file__))
    prompts = a.prompts
    if prompts is None:
        guess = mezo_paths.container_root(__file__) / "atlas.archs" / ".mezosync" / "prompts"
        prompts = str(guess) if guess.is_dir() else None
    return run(db, prompts, a.verbose)


if __name__ == "__main__":
    sys.exit(main())
