# -*- coding: utf-8 -*-
"""measure-docs-retired.py — документы образца, УЧАЩИЕ СНЯТОМУ (зона PROTO, заход 3 ④).

ЧТО СЧИТАЕТСЯ УЧЕНИЕМ СНЯТОМУ (и только это — долг):
  · ОТНОСИТЕЛЬНАЯ форма вызова в КОМАНДЕ: `python .mezosync/...` — отменена каноном 26.07;
  · ключ `--db <живой путь>` в команде примера — R15a (26.07): дефолт выводится, живую
    базу в примерах не называют.

ЧТО ДОЛГОМ НЕ ЯВЛЯЕТСЯ — границы названы, потому что первый перемер (27.08) считал
грубее и получил 12 там, где долгов ноль:
  · `--db <копия>` / `--db <ваша копия>` — ЗАГЛУШКА: ключ ЖИВ для не-дефолтной базы,
    R15a снял обязательность, а не сам ключ. Документы перехода учат прогону НА КОПИИ —
    это ровно случай ключа;
  · строка с надгробием В ТОЙ ЖЕ строке (⛔/раньше/прежде/отменено/печатал/гасило/…) —
    история, а не учение. Надгробие СТРОКОЙ НИЖЕ не гасит: роль копирует по строке
    (класс карточек #151/#152);
  · путь без слова `python` в строке — имя места в описи, не команда (граница признака G
    сторожа печатных форм — тот же водораздел, два инструмента не спорят об одном).

Выход: 0 долгов → код 0; долги напечатаны поимённо (файл:строка) → код 1.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# прошедшее время («печатал», «гасило») — рассказ о починенном, не учение
REVOKED = re.compile(
    r"⛔|⚰|НЕЛЬЗЯ|раньше|прежде|вместо|отменен|отменён|снят|устарел|больше не|история|"
    r"печатал\w?|гасил\w?", re.I)
REL_CMD = re.compile(r"python3?\s+\.mezosync[\\/]")
DB_IN_CMD = re.compile(r"--db\s+(?P<arg>\S+)")
STUB = re.compile(r"^[<«]")          # --db <копия> / «копия» — заглушка, не живой путь


def judge_line(line: str):
    """Вердикт одной строке: None — чисто; иначе (вид, фрагмент)."""
    if REVOKED.search(line):
        return None                   # надгробие/рассказ В ТОЙ ЖЕ строке — история
    if REL_CMD.search(line):
        return ("относительная форма в команде", line.strip()[:100])
    m = DB_IN_CMD.search(line)
    if m and ("python" in line or ".py" in line):
        if not STUB.match(m.group("arg")):
            return ("--db с живым путём в примере", line.strip()[:100])
    return None


def scan(root: Path):
    """Публикуемые .md (git ls-files) → {файл: [(строка, вид, фрагмент)]}."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "*.md"],
                         capture_output=True, text=True, encoding="utf-8")
    finds, files = {}, [l for l in out.stdout.splitlines() if l.strip()]
    for rel in files:
        p = root / rel
        if not p.exists():
            continue
        for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            v = judge_line(l)
            if v:
                finds.setdefault(rel, []).append((i, *v))
    return files, finds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="корень образца (git-репозиторий)")
    a = ap.parse_args()
    if a.root:
        root = Path(a.root)
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mezo_paths
        root = mezo_paths.template_root()
    # публикуемое отделяет git; без git-корня судить нечего
    if not (root / ".git").exists():
        print(f"⛔ {root} — не git-корень: публикуемое неотличимо от черновиков, НЕ ПРОВЕРЕНО")
        return 2
    files, finds = scan(root)
    if not files:
        print("⛔ git ls-files не дал ни одного .md — это НЕ «чисто»")
        return 2
    total = sum(len(v) for v in finds.values())
    print(f"документов .md: {len(files)} · учат снятому: {total}")
    for rel, hits in sorted(finds.items()):
        for i, kind, frag in hits:
            print(f"🔴 {rel}:{i} [{kind}] {frag}")
    if not total:
        print("✅ долгов нет. Границы: --db <заглушка> законен (ключ жив для копий); "
              "надгробие/рассказ в ТОЙ ЖЕ строке — история; путь без «python» — опись.")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
