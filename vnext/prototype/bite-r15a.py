# -*- coding: utf-8 -*-
"""
bite-r15a.py — R15a: инструмент координации не зависит от рабочего каталога.

⚠️ ПЕРЕПИСАН 2026-07-26 09:50 UTC. Прежняя версия болела тем же классом, что и `bite-r16`
до починки, только мягче — и я назвал это сам, до чужого замечания:
  · секция «ДО: абсолютный скрипт, относительный `--db`» брала копию ЖИВОГО скрипта из
    песочницы. После врезки R15a (COORD, `7b6b106`) эта копия УЖЕ пропатчена, и укус
    печатал **верный отказ с ЛОЖНЫМ объяснением**: «⇒ путь резолвится ОТ CWD», тогда как
    он резолвился от корня мезосинка. Наблюдение было настоящим, вывод — вчерашним.
  · «ПОСЛЕ» проверялось на моём прототипе, хотя механизм давно живёт в рабочем скрипте.
📌 Класс (общий с `bite-r16`): **укус, сравнивающий с baseline из песочницы, устаревает
   в момент врезки — копии живых скриптов уже «после».**

РЕЖИМЫ РАЗВЕДЕНЫ:
    verify   (по умолчанию) — РЕГРЕССИЯ по свойствам целевого скрипта. Про «до» не знает.
    demo     --baseline P   — ДЕМОНСТРАЦИЯ боли; предусловие проверяется, иначе rc=2.
    selftest                — доказывает, что укус УМЕЕТ КРАСНЕТЬ (мутанты `mezo_paths`).

Живой субстрат не открывается: всё на временных копиях. Предусловие не выполнено — rc=2.
"""
import argparse
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROLE = "PROTO"


def die(reason, *details):
    print(f"⛔ УКУС НЕ ПОСТАВЛЕН: {reason}")
    for d in details:
        print("   ·", d)
    sys.exit(2)


def run(script, args, cwd):
    p = subprocess.run([sys.executable, str(script), *args], cwd=str(cwd),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def notes(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    n, = con.execute("SELECT COUNT(*) FROM messages").fetchone()
    con.close()
    return n


def stage(sandbox, target, bait=False):
    """Стенд: копия БД + копия целевого скрипта с зависимостями + ЧУЖОЙ рабочий каталог.

    bait=True кладёт в чужой каталог ПРИМАНКУ — валидную БД по тому же относительному
    пути. Это ядро F20: относительный `--db`, случайно совпавший с реальным файлом,
    не падает и не создаёт фантом — он МОЛЧА пишет в ДРУГУЮ живую БД и отвечает «OK».
    Именно так 26.07 моя тестовая нота ушла в боевую ленту (#2691, надгробие #2693).
    """
    src = sandbox / "mezosync.db"
    if not src.exists():
        die(f"нет песочницы: {src}", "подними её: python vnext/sandbox/bootstrap.py")
    root = Path(tempfile.mkdtemp(prefix="bite-r15a-"))
    mezo = root / ".mezosync"
    (mezo / "scripts").mkdir(parents=True)
    shutil.copy2(src, mezo / "mezosync.db")
    dest = mezo / "scripts" / target.name
    shutil.copy2(target, dest)
    dep = target.parent / "mezo_paths.py"
    if dep.exists():
        shutil.copy2(dep, mezo / "scripts" / "mezo_paths.py")
    foreign = root / "foreign-cwd"
    foreign.mkdir()
    baitdb = None
    if bait:
        baitdb = foreign / "mezosync.db"
        shutil.copy2(src, baitdb)
    return mezo / "mezosync.db", dest, foreign, baitdb


def verify(target, sandbox):
    """РЕГРЕССИЯ: свойства целевого скрипта. Каждое — на своём стенде."""
    print(f"[регрессия R15a] цель: {target}")
    v, names = [], []

    # S1 — без --db: БД находится от расположения СКРИПТА,CWD ни при чём
    db, sc, foreign, _ = stage(sandbox, target)
    before = notes(db)
    rc, out = run(sc, ["--role", ROLE, "--body", "[укус R15a] без --db"], cwd=foreign)
    ok = rc == 0 and notes(db) == before + 1
    v.append(ok); names.append("S1")
    print(f"S1 без --db из ЧУЖОГО каталога: rc={rc} · нот {before}→{notes(db)} "
          f"→ {'✅ нашёл БД от себя' if ok else '🔴 не нашёл'}")

    # S2 — относительный --db резолвится ОТ КОРНЯ МЕЗОСИНКА, не от CWD
    db, sc, foreign, _ = stage(sandbox, target)
    before = notes(db)
    rc, out = run(sc, ["--db", "mezosync.db", "--role", ROLE,
                       "--body", "[укус R15a] относительный --db"], cwd=foreign)
    ok = rc == 0 and notes(db) == before + 1
    v.append(ok); names.append("S2")
    print(f"S2 относительный --db из чужого каталога: rc={rc} · нот {before}→{notes(db)} "
          f"→ {'✅ резолвится от корня' if ok else '🔴 резолвится от CWD'}")

    # S3 — несуществующая БД: ГРОМКО и с названной причиной, без тихого фантома
    db, sc, foreign, _ = stage(sandbox, target)
    rc, out = run(sc, ["--db", "нет-такой.db", "--role", ROLE, "--body", "x"], cwd=foreign)
    named = ("не найдена" in out) and ("CWD" in out or "текущего каталога" in out)
    phantom = list(foreign.glob("*.db")) + list(db.parent.glob("нет-такой.db"))
    ok = rc != 0 and named and not phantom
    v.append(ok); names.append("S3")
    print(f"S3 несуществующая БД: rc={rc} · причина названа: {'да' if named else 'НЕТ'} · "
          f"фантомов создано {len(phantom)} "
          f"→ {'✅ громкий отказ' if ok else '🔴 тихий фантом или немой отказ'}")

    # S4 — ЯДРО F20: приманка в чужом каталоге НЕ должна перехватить запись
    db, sc, foreign, bait = stage(sandbox, target, bait=True)
    b_before, d_before = notes(bait), notes(db)
    rc, out = run(sc, ["--db", "mezosync.db", "--role", ROLE,
                       "--body", "[укус R15a] проверка приманки"], cwd=foreign)
    b_after, d_after = notes(bait), notes(db)
    ok = rc == 0 and b_after == b_before and d_after == d_before + 1
    v.append(ok); names.append("S4")
    print(f"S4 ПРИМАНКА в чужом каталоге (F20): своя БД {d_before}→{d_after} · "
          f"чужая {b_before}→{b_after} "
          f"→ {'✅ писал в свою' if ok else '🔴 НОТА УШЛА В ЧУЖУЮ ЖИВУЮ БД'}")

    # S5 — абсолютный --db работает как раньше (обратная совместимость)
    db, sc, foreign, _ = stage(sandbox, target)
    before = notes(db)
    rc, out = run(sc, ["--db", str(db), "--role", ROLE,
                       "--body", "[укус R15a] абсолютный --db"], cwd=foreign)
    ok = rc == 0 and notes(db) == before + 1
    v.append(ok); names.append("S5")
    print(f"S5 абсолютный --db: rc={rc} · нот {before}→{notes(db)} "
          f"→ {'✅ как раньше' if ok else '🔴 сломана совместимость'}")

    ok_all = all(v)
    print(f"\n{'✅ R15a ДЕРЖИТСЯ' if ok_all else '🔴 R15a ДЕРЖИТСЯ НЕ ЦЕЛИКОМ'} — "
          f"{sum(v)}/{len(v)} свойств"
          + ("" if ok_all else f" · провалено: {[n for n, x in zip(names, v) if not x]}"))
    print("⚠️ ГРАНИЦА: запуск САМОГО скрипта относительным путём (`python .mezosync/scripts/x.py`)")
    print("   этим не лечится и лечиться не может — интерпретатор ищет файл до старта кода.")
    print("   Вторая половина — гард формы вызова (R15b), он правит ИСТОЧНИК формы.")
    verify.last = dict(zip(names, v))
    return 0 if ok_all else 1


MUTANTS = {
    # M1 — вернуть резолв ОТ CWD: ровно то, что было до R15a.
    "M1-резолв-от-CWD": ([
        ("        db = p if p.is_absolute() else (root / p)", "        db = p"),
    ], ("S2", "S4")),
    # M2 — снять громкий отказ: путь не существует ⇒ тихо поедем дальше и создадим фантом.
    "M2-тихий-фантом": ([
        ("    if must_exist and not db.exists():", "    if False and not db.exists():"),
    ], ("S3",)),
}


def selftest(target, sandbox):
    """Доказываем чувствительность: портим mezo_paths и требуем красного по нужным свойствам."""
    dep = target.parent / "mezo_paths.py"
    if not dep.exists():
        die(f"нет mezo_paths.py рядом с {target}", "мутанты накладываются на него")
    src = dep.read_text(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp(prefix="bite-r15a-mutants-"))
    all_ok = True
    for name, (edits, expect) in MUTANTS.items():
        print(f"\n{'='*72}\n[мутант {name}] ожидаем 🔴 по {', '.join(expect)}\n{'='*72}")
        mutated = src
        for needle, repl in edits:
            if needle not in mutated:
                die(f"мутант {name} не накладывается: якорь не найден в {dep}",
                    "код изменился — мутанта надо перепривязать, иначе самопроверка лжёт",
                    f"якорь: {needle.strip()[:70]}")
            mutated = mutated.replace(needle, repl, 1)
        mdir = tmp / name
        mdir.mkdir()
        shutil.copy2(target, mdir / target.name)
        (mdir / "mezo_paths.py").write_text(mutated, encoding="utf-8")
        rc = verify(mdir / target.name, sandbox)
        got = getattr(verify, "last", {})
        good = rc != 0 and all(got.get(e) is False for e in expect)
        all_ok &= good
        print(f"\n⇒ мутант {name}: rc={rc}, "
              f"{{{', '.join(f'{e}={got.get(e)}' for e in expect)}}} — "
              f"{'✅ укус ЧУВСТВИТЕЛЕН' if good else '🔴 УКУС СЛЕП: порча не поймана'}")
    print(f"\n{'='*72}\n{'✅ САМОПРОВЕРКА ПРОЙДЕНА' if all_ok else '🔴 САМОПРОВЕРКА ПРОВАЛЕНА'} "
          f"— укус {'ловит' if all_ok else 'НЕ ловит'} обе известные порчи")
    return 0 if all_ok else 1


def demo(baseline, sandbox):
    """ДЕМОНСТРАЦИЯ боли. Предусловие «baseline действительно ДО» ПРОВЕРЯЕТСЯ."""
    db, sc, foreign, bait = stage(sandbox, baseline, bait=True)
    b_before, d_before = notes(bait), notes(db)
    rc, out = run(sc, ["--db", "mezosync.db", "--role", ROLE, "--body", "[demo]"], cwd=foreign)
    if notes(bait) == b_before and notes(db) == d_before + 1:
        die("указанный baseline УЖЕ несёт R15a — это не «до»-версия",
            "относительный --db резолвился от корня, приманка не сработала",
            "возьми версию ДО врезки: git show <коммит-до>:scripts/write-message.py",
            "или гоняй регрессию: bite-r15a.py verify")
    print("── ДО (baseline): относительный --db из чужого каталога")
    print(f"   rc={rc} · своя БД {d_before}→{notes(db)} · ЧУЖАЯ {b_before}→{notes(bait)}")
    print("   ⇒ вот F20 целиком: запись ушла не туда, а инструмент ответил честным «OK».")
    print("\n📌 Это ДЕМОНСТРАЦИЯ, а не приёмка. Приёмка — `bite-r15a.py verify`.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="verify", choices=["verify", "demo", "selftest"])
    ap.add_argument("--sandbox", default=str(Path.home() / ".mezosync-sandbox"))
    ap.add_argument("--target", default=None,
                    help="проверяемый писатель (по умолчанию — копия живого в песочнице)")
    ap.add_argument("--baseline", default=None, help="ДО-версия (только для demo)")
    a = ap.parse_args()
    sandbox = Path(a.sandbox).resolve()
    target = Path(a.target).resolve() if a.target else sandbox / "scripts" / "write-message.py"
    if not target.exists():
        die(f"нет целевого скрипта: {target}")
    if a.mode == "verify":
        return verify(target, sandbox)
    if a.mode == "selftest":
        return selftest(target, sandbox)
    if not a.baseline:
        die("demo требует --baseline <ДО-версия write-message.py>",
            "именно этого не хватало прежней версии укуса: baseline брался молча "
            "из песочницы и после врезки оказывался уже почищенным")
    bp = Path(a.baseline).resolve()
    if not bp.exists():
        die(f"нет baseline: {bp}")
    return demo(bp, sandbox)


if __name__ == "__main__":
    sys.exit(main())
