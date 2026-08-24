# -*- coding: utf-8 -*-
"""
bite-stand-cleanup.py — приёмка помощника mezo_stand.py и утилиты janitor-stands.py.

Проверяет ЗАПУСКОМ, а не чтением: поднимает подставные проверки, смотрит, остался
каталог на диске или нет. Есть НАРОЧНАЯ ПОЛОМКА — если её не поймали, приёмка слепа
и её зелёный цвет ничего не доказывает.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = 0
OK = True


def case(title, ok, detail):
    global CASES, OK
    CASES += 1
    OK &= bool(ok)
    print(f"{'OK ' if ok else 'RED'} {title}\n    {detail}")
    return ok


def run_probe(body, env_extra=None, helper=None):
    """Подставная проверка: заводит каталог помощником и завершается как велено."""
    helper = helper or (HERE / "mezo_stand.py")
    d = Path(tempfile.mkdtemp(prefix="probe-host-"))
    shutil.copy2(helper, d / "mezo_stand.py")
    head = (
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        "import mezo_stand\n"
        "root = mezo_stand.new('probe-stand-')\n"
        "(root / 'marker.txt').write_text('x', encoding='utf-8')\n"
        "print('STAND=' + str(root))\n"
    )
    (d / "probe.py").write_text(head + body, encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env.pop("MEZO_KEEP_STANDS", None)
    env.update(env_extra or {})
    p = subprocess.run([sys.executable, "probe.py"], cwd=d, capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    out = (p.stdout or "") + (p.stderr or "")
    m = re.search(r"STAND=(.+)", out)
    stand = Path(m.group(1).strip()) if m else None
    shutil.rmtree(d, ignore_errors=True)
    return stand, out, p.returncode


def janitor(sandbox, tools, *extra):
    p = subprocess.run([sys.executable, str(HERE / "janitor-stands.py"),
                        "--temp-dir", str(sandbox), "--tools-dir", str(tools), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return (p.stdout or "") + (p.stderr or ""), p.returncode


def main():
    print("=" * 78)
    print("ПРИЁМКА: уборка временных каталогов проверок")
    print("=" * 78)

    # (1) успех — каталог убран
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(0))")
    reported = "убрано временных каталогов: 1" in out
    case("(1) прогон УСПЕШЕН — каталог убран",
         st is not None and not st.exists() and reported,
         f"код {rc} · каталог существует: {st.exists() if st else '-'} · "
         f"отчёт об уборке напечатан: {'да' if reported else 'НЕТ'}")

    # (2) провал — каталог СОХРАНЁН и путь НАПЕЧАТАН
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(1))")
    kept = st is not None and st.exists()
    printed = st is not None and str(st) in out and "СОХРАНЕНЫ" in out
    case("(2) прогон ПРОВАЛИЛСЯ — каталог сохранён, путь напечатан",
         kept and printed and "прогон провалился" in out,
         f"код {rc} · каталог на месте: {kept} · путь в выводе: {printed}")
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # (3) падение без объявления исхода — каталог СОХРАНЁН
    st, out, rc = run_probe("raise SystemExit('упало до объявления исхода')")
    kept = st is not None and st.exists()
    case("(3) упал, не объявив исход — каталог сохранён (неизвестность = провал)",
         kept and "не объявлен" in out,
         f"код {rc} · каталог на месте: {kept} · "
         f"причина названа: {'да' if 'не объявлен' in out else 'НЕТ'}")
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # (4) успех, но велено сохранять — каталог СОХРАНЁН
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(0))", {"MEZO_KEEP_STANDS": "1"})
    kept = st is not None and st.exists()
    case("(4) успех + MEZO_KEEP_STANDS=1 — каталог всё равно сохранён",
         kept and "MEZO_KEEP_STANDS" in out,
         f"каталог на месте: {kept}")
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # (5) НАРОЧНАЯ ПОЛОМКА: убирать всегда => случай (2) обязан покраснеть
    broken_dir = Path(tempfile.mkdtemp(prefix="probe-broken-"))
    src = (HERE / "mezo_stand.py").read_text(encoding="utf-8")
    needle = "    why = keep_reason()"
    if needle not in src:
        sys.exit("НЕ ЗАПУСТИЛАСЬ: место для нарочной поломки не найдено — "
                 "помощник менялся, правь приёмку")
    broken = broken_dir / "mezo_stand.py"
    broken.write_text(src.replace(needle, "    why = None", 1), encoding="utf-8")
    st, out, rc = run_probe("sys.exit(mezo_stand.finish(1))", helper=broken)
    caught = not (st is not None and st.exists())
    case("(5) НАРОЧНАЯ ПОЛОМКА (убирать всегда) — приёмка обязана это заметить",
         caught,
         "поломанный помощник убрал каталог даже при провале => случай (2) на нём покраснел бы"
         if caught else
         "ПРИЁМКА СЛЕПА: поломанный помощник ведёт себя как целый — случай (2) ничего не доказывает")
    shutil.rmtree(broken_dir, ignore_errors=True)
    if st and st.exists():
        shutil.rmtree(st, ignore_errors=True)

    # обстановка для утилиты уборки
    sandbox = Path(tempfile.mkdtemp(prefix="probe-temp-"))
    tools = Path(tempfile.mkdtemp(prefix="probe-tools-"))
    (tools / "fake-check.py").write_text(
        'import tempfile\nd = tempfile.mkdtemp(prefix="oldstand-")\n', encoding="utf-8")
    old = sandbox / "oldstand-aaaaaa"
    old.mkdir()
    (old / "copy.db").write_bytes(b"x" * 4096)
    long_ago = time.time() - 72 * 3600
    os.utime(old, (long_ago, long_ago))
    young = sandbox / "oldstand-bbbbbb"
    young.mkdir()

    # (6) показ НЕ удаляет
    out, rc = janitor(sandbox, tools)
    case("(6) утилита уборки БЕЗ --apply — показывает, но не удаляет",
         old.exists() and young.exists() and "ПОКАЗ, НЕ УДАЛЕНИЕ" in out and "подпадает: 1" in out,
         f"старый каталог на месте: {old.exists()} · молодой на месте: {young.exists()}")

    # (7) --apply удаляет ТОЛЬКО старое
    out, rc = janitor(sandbox, tools, "--apply")
    case("(7) утилита уборки С --apply — удалила старое, не тронула молодое",
         not old.exists() and young.exists() and "УДАЛЕНО: 1" in out,
         f"старый удалён: {not old.exists()} · молодой уцелел: {young.exists()}")

    # (8) ноль под порогом печатается СЛОВОМ
    out, rc = janitor(sandbox, tools)
    case("(8) под порог никто не подпал — сказано словом НОЛЬ, а не тишиной",
         "НОЛЬ" in out and "Ни один каталог не старше порога" in out,
         "иначе прогон, ничего не удаливший, читался бы как успешная уборка")

    # (9) начал имён нет — громкий отказ, а не тихое «удалено 0»
    empty_tools = Path(tempfile.mkdtemp(prefix="probe-empty-"))
    (empty_tools / "nothing.py").write_text("x = 1\n", encoding="utf-8")
    out, rc = janitor(sandbox, empty_tools, "--apply")
    case("(9) начал имён в исходниках нет — громкий отказ, а не тихое «удалено 0»",
         rc == 2 and "НЕ ЗАПУСТИЛАСЬ" in out and young.exists(),
         f"код {rc} · отказ назван: {'да' if 'НЕ ЗАПУСТИЛАСЬ' in out else 'НЕТ'}")

    for d in (sandbox, tools, empty_tools):
        shutil.rmtree(d, ignore_errors=True)

    print("\n" + "=" * 78)
    print(f"{'ПРИЁМКА ПРОЙДЕНА' if OK else 'ПРИЁМКА ПРОВАЛЕНА'} — случаев {CASES}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
