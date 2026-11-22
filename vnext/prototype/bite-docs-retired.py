# -*- coding: utf-8 -*-
# PLANTS: template-docs
"""ПРИЁМКА перемера «документы учат снятому» (measure-docs-retired.py).

Судит ПОДСАЖЕННЫМ дефектом в песочном git-корне, не общим исходом на живом образце:
зелёное на живом само по себе не доказывает, что перемер что-то ищет.
"""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MEASURE = HERE / "measure-docs-retired.py"
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402 — среда запуска перемера (карточка #613)

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


def run(root, stand_root):
    # Среда стенда (карточка #613): MEZO_CONTAINER — корень стенда приёмки, номер чата не
    # передаётся. Прежде перемер получал среду вызывающего. Что судить, задаёт --root; корень
    # стенда передаётся отдельно, потому что в случае ⑥ --root — живой образец, а не стенд.
    r = subprocess.run([sys.executable, str(MEASURE), "--root", str(root)],
                       capture_output=True, text=True, encoding="utf-8",
                       env=mezo_stand.stand_env(stand_root))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-docs-ret-")

    r = stand(tmp, "one", {"doc.md": "пример:\n    python .mezosync/scripts/x.py --role A\n"})
    out, code = run(r, tmp)
    case("① относительная форма в команде БЕЗ надгробия → 🔴 поимённо",
         code == 1 and "doc.md:2" in out and "относительная форма" in out)

    r = stand(tmp, "two", {"doc.md":
              "⛔ раньше звали `python .mezosync/scripts/x.py` — отменено каноном 26.07\n"})
    out, code = run(r, tmp)
    case("② надгробие В ТОЙ ЖЕ строке гасит — история, не учение",
         code == 0 and "учат снятому: 0" in out)

    r = stand(tmp, "three", {"doc.md":
              "    python .mezosync/scripts/x.py --role A\n⛔ строкой выше — отменённая форма\n"})
    out, code = run(r, tmp)
    case("③ надгробие СТРОКОЙ НИЖЕ не гасит → 🔴 (роль копирует по строке)",
         code == 1 and "doc.md:1" in out)

    r = stand(tmp, "four", {"doc.md":
              "    python migrate.py --db <копия> --dry\n    python tool.py --db prod/mezosync.db\n"})
    out, code = run(r, tmp)
    case("④ «--db <заглушка>» законен, «--db живой-путь» — долг (обе границы разом)",
         code == 1 and "doc.md:2" in out and "doc.md:1" not in out,
         "ключ жив для копий; живую базу в примерах не называют (R15a)")

    nogit = Path(tmp) / "nogit"; nogit.mkdir()
    (nogit / "doc.md").write_text("python .mezosync/scripts/x.py\n", encoding="utf-8")
    out, code = run(nogit, tmp)
    case("⑤ каталог без git → «НЕ ПРОВЕРЕНО» кодом 2, а не «чисто»",
         code == 2 and "НЕ ПРОВЕРЕНО" in out)

    sys.path.insert(0, str(HERE))
    import mezo_paths
    tpl = mezo_paths.template_root()
    # ⑥ судит разницей состояния (время изменения файлов до и после) — НЕ ЧИНЮ, потому что своих следов
    # у перемера нет по построению: он ничего не сеет и пробных имён не несёт, спросить «мои ли это
    # записи» не о чем (карточка #804). Что держит случай от ложного провала — замер 21.11.2026:
    #   окно ...... один вызов перемера: 0,3–1,1 с (три вызова подряд, в образце 128 файлов *.md)
    #   предмет ... файлы *.md клона пакета, а не база контура: записки, карточки и память соседей
    #               их не трогают. Меняет их только git в самом клоне (checkout · merge · pull)
    #   соседи .... у приёмщика образец — его собственный клон, пишет в него только он. В контуре, где
    #               образцом служит общий клон пакета, журнал движений HEAD дал 77 движений за 30 суток
    #               (17.10–15.11), в самый плотный день 21 ⇒ совпадение с окном ≈0,003 % на прогон,
    #               в плотный день ≈0,03 %; после 15.11 движений нет — пакет правят в отдельных worktree
    # Слабое место названо, а не спрятано: движение клона, пришедшееся ровно на вызов, провалит случай
    # без вины перемера — поэтому при провале изменившиеся файлы называются поимённо.
    before = {p: p.stat().st_mtime_ns for p in Path(tpl).rglob("*.md")}
    started = time.perf_counter()
    run(Path(tpl), tmp)
    window = time.perf_counter() - started
    after = {p: p.stat().st_mtime_ns for p in Path(tpl).rglob("*.md")}
    moved = sorted(p.relative_to(tpl).as_posix() for p in set(before) | set(after)
                   if before.get(p) != after.get(p))
    case("⑥ живой образец прогоном не изменён (перемер только читает)", before == after,
         f"сверено файлов *.md: {len(before)} · окно — один вызов перемера: {window:.1f} с"
         + ("" if not moved else " · изменились: " + ", ".join(moved[:5]) + (" …" if len(moved) > 5 else "")
            + " — если в это время двигался сам клон образца (checkout, merge, pull), перемер не виноват:"
              " сверь журнал движений HEAD клона и повтори прогон"))

    print()
    print(f"{'✅ ПЕРЕМЕР ПРИНЯТ' if OK else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}")
    if OK:
        # карточка #817: git кладёт .git/objects «только чтение», Windows такие не удаляет — помощник
        # снимает метку до удаления, а чего убрать не смог, называет в выводе
        mezo_stand.remove_tree(tmp)
    else:
        print(f"📂 стенд сохранён: {tmp}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
