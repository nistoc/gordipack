# -*- coding: utf-8 -*-
"""ПРИЁМКА перемера «документы учат снятому» (measure-docs-retired.py).

Судит ПОДСАЖЕННЫМ дефектом в песочном git-корне, не общим исходом на живом образце:
зелёное на живом само по себе не доказывает, что перемер что-то ищет.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEASURE = HERE / "measure-docs-retired.py"

CASES = 0
OK = True


def case(title, verdict, detail=""):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")


def stand(tmp, name, docs):
    root = Path(tmp) / name
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], capture_output=True)
    for fn, body in docs.items():
        (root / fn).write_text(body, encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "-A"], capture_output=True)
    return root


def run(root):
    r = subprocess.run([sys.executable, str(MEASURE), "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-docs-ret-")

    r = stand(tmp, "one", {"doc.md": "пример:\n    python .mezosync/scripts/x.py --role A\n"})
    out, code = run(r)
    case("① относительная форма в команде БЕЗ надгробия → 🔴 поимённо",
         code == 1 and "doc.md:2" in out and "относительная форма" in out)

    r = stand(tmp, "two", {"doc.md":
              "⛔ раньше звали `python .mezosync/scripts/x.py` — отменено каноном 26.07\n"})
    out, code = run(r)
    case("② надгробие В ТОЙ ЖЕ строке гасит — история, не учение",
         code == 0 and "учат снятому: 0" in out)

    r = stand(tmp, "three", {"doc.md":
              "    python .mezosync/scripts/x.py --role A\n⛔ строкой выше — отменённая форма\n"})
    out, code = run(r)
    case("③ надгробие СТРОКОЙ НИЖЕ не гасит → 🔴 (роль копирует по строке)",
         code == 1 and "doc.md:1" in out)

    r = stand(tmp, "four", {"doc.md":
              "    python migrate.py --db <копия> --dry\n    python tool.py --db prod/mezosync.db\n"})
    out, code = run(r)
    case("④ «--db <заглушка>» законен, «--db живой-путь» — долг (обе границы разом)",
         code == 1 and "doc.md:2" in out and "doc.md:1" not in out,
         "ключ жив для копий; живую базу в примерах не называют (R15a)")

    nogit = Path(tmp) / "nogit"; nogit.mkdir()
    (nogit / "doc.md").write_text("python .mezosync/scripts/x.py\n", encoding="utf-8")
    out, code = run(nogit)
    case("⑤ каталог без git → «НЕ ПРОВЕРЕНО» кодом 2, а не «чисто»",
         code == 2 and "НЕ ПРОВЕРЕНО" in out)

    sys.path.insert(0, str(HERE))
    import mezo_paths
    tpl = mezo_paths.template_root()
    before = {p: p.stat().st_mtime_ns for p in Path(tpl).rglob("*.md")}
    run(Path(tpl))
    after = {p: p.stat().st_mtime_ns for p in Path(tpl).rglob("*.md")}
    case("⑥ живой образец прогоном не изменён (перемер только читает)", before == after)

    print()
    print(f"{'✅ ПЕРЕМЕР ПРИНЯТ' if OK else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}")
    if OK:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"📂 стенд сохранён: {tmp}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
