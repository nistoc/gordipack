# -*- coding: utf-8 -*-
r"""ПРИЁМКА ПОИСКА КАТАЛОГА КООРДИНАЦИИ (карточка #248, класс принесён контуром tapas).

🩸 ЧЕМ ОПЛАЧЕНО. Прежняя редакция `guard-all.py` перебирала ДВА кандидата, и оба были наши:
`atlas.archs/.mezosync/coordination` и корень контейнера. У соседей репозиторий зовётся
иначе ⇒ путь несуществующий ⇒ проверка «замороженные md» брала оттуда НОЛЬ файлов
и печатала ✅. Молчало ПЯТЬ СУТОК — всю жизнь их контура.
⛔ Их формулировка: **это хуже ложной тревоги. Ложная учит не верить красному; эта учит
ВЕРИТЬ ЗЕЛЁНОМУ.** Пустой набор проходит любую проверку.

🎯 ПОЧЕМУ ЭТА ПРИЁМКА НУЖНА ОТДЕЛЬНО ОТ ОСТАЛЬНЫХ: у нас нет отрицательного случая
по построению. Имя нашего репозитория совпало с впечатанным, поэтому у нас всё зелёное —
и останется зелёным при любой починке И БЕЗ НЕЁ. Проверка без отрицательного случая
не различает причин. Здесь отрицательный случай строится руками.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① каталог под ЧУЖИМ именем репозитория — НАХОДИТСЯ                        РАЗЛИЧАЮЩИЙ
  ② каталог в корне контура (раскладка образца) — находится                 РАЗЛИЧАЮЩИЙ
  ③ каталогов нет вовсе — пустой список, а НЕ выдуманный путь               РАЗЛИЧАЮЩИЙ
  ④ два каталога сразу — возвращаются ОБА, а не первый                      РАЗЛИЧАЮЩИЙ
  ⑤ ⛔ ЗАПРЕЩЁННЫЙ СПОСОБ ПРОЙТИ: имя `atlas.archs` не привилегированно      РАЗЛИЧАЮЩИЙ
  ⑥ ЖИВОЙ КОНТУР: каталог по-прежнему находится (починка не сломала своё)   РАЗЛИЧАЮЩИЙ
  ⑦ ПРОГОН В КОНТУРЕ БЕЗ КАТАЛОГА: проверка ОТКАЗЫВАЕТ и называет признак   РАЗЛИЧАЮЩИЙ
  ⑧ ВСТРЕЧНЫЙ к ⑦: явное слово превращает отказ в жёлтое «не поставлена»    РАЗЛИЧАЮЩИЙ
  ⑨ ВТОРАЯ ПРОВЕРКА ТОГО ЖЕ КАТАЛОГА: мост соседей тоже говорит вслух       РАЗЛИЧАЮЩИЙ
  ⑩ отказ ⑦ не гасит остальные проверки: их число не падает                 РАЗЛИЧАЮЩИЙ
  ⑭ под git, таких файлов git НЕ ЗНАЕТ (в ленте записка) — «ℹ️ … не вёл»      РАЗЛИЧАЮЩИЙ
  ⑮ git знает два файла, оба на диске — проверка зелёная, как было           РАЗЛИЧАЮЩИЙ
  ⑯ унесён ОДИН из двух — провал С ИМЕНЕМ унесённого                         РАЗЛИЧАЮЩИЙ
  ⑰ унесены ОБА — провал «ПРОПАЛИ», а НЕ «ℹ️ … не вёл»                       РАЗЛИЧАЮЩИЙ
  ⑱ НАРОЧНАЯ ПОЛОМКА копии: признак замороженного файла не узнаёт ни одного —
    краснеют РОВНО ⑯ и ⑰ (пустой ответ git неотличим от чистоты)             РАЗЛИЧАЮЩИЙ

⛔ Живой базы не касается: ①–⑤ строят пустые деревья каталогов, ⑦–⑩ собирают контур
   из образца во временном каталоге. ⑥ только ЧИТАЕТ раскладку живого контура.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#208)
import mezo_stand  # noqa: E402 — среда запусков на стенде (записка #5096)
import mezo_target  # noqa: E402 — какую копию испытываем (карточка #148)

# 🪤 17.10 (записка #5838): прежде GUARD брался из корня контейнера по файлу путей — то есть
# всегда из ЖИВОГО контура, и при --target на копию приёмка испытывала оригинал. А с Э7
# (import bridge_letter в guard-all.py, карточка #681) загрузка падала ModuleNotFoundError и на
# живом: bridge_letter лежит только рядом с guard-all.py, а в sys.path стоял каталог приёмки.
# ⇒ Испытуемая копия — через mezo_target; её соседи — первыми в sys.path, как при её запуске.
GUARD = mezo_target.script("guard-all.py")
sys.path.insert(0, str(GUARD.parent))
TEMPLATE = next((p for p in (mezo_paths.template_root(),
                            pathlib.Path(__file__).resolve().parents[2] / "gordipack")
                if (p / "scripts" / "init-group.py").exists()), None)
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def find_dirs(root: pathlib.Path):
    """Зовём ТУ ЖЕ функцию, что живёт в стороже, — не её пересказ.

    ⚠️ Копия признака в приёмке — отдельная беда: она сходится с продуктом в день написания
    и расходится молча. Поэтому модуль грузится с диска, а функция берётся из него.
    """
    spec = importlib.util.spec_from_file_location("_guard_for_bite", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._coordination_dirs(root)


def find_bridge(root: pathlib.Path):
    spec = importlib.util.spec_from_file_location("_guard_for_bite_bridge", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._bridge_dirs(root)


def make_tree(base: pathlib.Path, *paths: str) -> pathlib.Path:
    for rel in paths:
        (base / rel).mkdir(parents=True, exist_ok=True)
    return base


def run_guard(circuit: pathlib.Path, extra_env: dict | None = None) -> str:
    """guard-all.py в собранном контуре → его вывод (код не важен: судим строки)."""
    r = subprocess.run([sys.executable, str(circuit / ".mezosync" / "scripts" / "guard-all.py")],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900, env=mezo_stand.stand_env(circuit, **(extra_env or {})))
    return (r.stdout or "") + (r.stderr or "")


def line_of(output: str, key: str) -> str:
    return next((s for s in output.splitlines() if key in s), "")


# ═══ ⑭–⑱ ЧТО ЗНАЕТ GIT О ЗАМОРОЖЕННЫХ md (карточка #687) ══════════════════════════════════════
# Проверка «замороженные md» различает ТРИ разных пустоты, и различитель у неё один — ответ git:
#   git таких файлов не знает ..... контур md-каналов не вёл ⇒ «ℹ️», и так будет всегда
#   знает, а на диске их нет ...... ПРОПАЛИ ⇒ провал с именами
#   спросить нечем ................ «⚠️», не путать с «цело»
# 🩸 Прежний различитель смотрел на ЛЕНТУ (пуста ли она): у контура из пакета замороженных md
# нет никогда, и первая же записка включала «⚠️ … НОЛЬ» навсегда. Замер 13.11 21:27 UTC.
# ⚠️ А пропажа ЧАСТИ файлов не была видна вовсе: git спрашивали только о файлах, НАЙДЕННЫХ
# на диске — унесённого в списке нет, и о нём не спрашивали.
FROZEN_MARKS = ("⑭", "⑮", "⑯", "⑰")
BREAK_687 = ('    if path.name == "sync.rules.md":',
             '    if True:  # ПОЛОМКА (⑱): признак не узнаёт ни одного замороженного файла')


def git_say(args, cwd) -> tuple:
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=120, cwd=str(cwd))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def frozen_line(out: str) -> str:
    """Строка проверки о замороженных md — БЕЗ строки перечня прошедших: имя стои́т и в ней,
    и тогда любой исход читался бы как её текст."""
    for s in out.splitlines():
        t = s.strip()
        if "замороженные md" in t and not t.startswith("✅ прошли"):
            return t
    return ""


def frozen_is_green(out: str) -> bool:
    return any("прошли" in s and "замороженные md" in s for s in out.splitlines())


def frozen_verdict(mark: str, out: str, gone: list) -> tuple:
    """Сошлось ли положение. → (сошлось, строка для глаз)."""
    line = frozen_line(out)
    if mark == "⑭":
        return (line.startswith("ℹ️") and "не вёл" in line), line or "(строки нет вовсе)"
    if mark == "⑮":
        return (frozen_is_green(out) and not line), line or "✅ (в перечне прошедших без слова)"
    named = all(n in line for n in gone)
    return (line.startswith("⛔") and "ПРОПАЛИ" in line and named), line or "(строки нет вовсе)"


def frozen_git_cases(circuit: pathlib.Path) -> bool:
    """Четыре положения ОДНОГО контура под git + нарочная поломка на каждом из них.

    ⚖️ Поломанная копия кладётся РЯДОМ С ОРИГИНАЛОМ (соседи ей нужны: мост писем, остальные
    проверки) и убирается сразу после прогона — иначе её подхватили бы проверки самого контура.
    """
    ok = True
    dirs = find_dirs(circuit)
    if not dirs:
        return case("⑭–⑱ НЕ ПРОГНАНЫ: каталога согласования в собранном контуре нет",
                    False, "положения строить негде — это отказ мерить, а не «чисто»")
    coord = dirs[0]
    guard = circuit / ".mezosync" / "scripts" / "guard-all.py"
    whole = guard.read_text(encoding="utf-8")
    if whole.count(BREAK_687[0]) != 1:
        ok &= case("⑱ НАРОЧНАЯ ПОЛОМКА: якоря поломки в испытуемом нет",
                   False, f"строка {BREAK_687[0].strip()!r} встречается "
                   f"{whole.count(BREAK_687[0])} раз — случаи ⑯ ⑰ остались бы без различителя")
    broken = guard.parent / "guard-all-break687.py"

    # записка в ленту: критерий карточки говорит о контуре, у которого лента НЕ пуста
    note = circuit / "записка-687.md"
    note.write_text("Приёмка карточки #687: одна записка, чтобы лента не была пустой.\n",
                    encoding="utf-8")
    wcode, wout = 1, ""
    writer = guard.parent / "write-message.py"
    if writer.exists():
        r = subprocess.run([sys.executable, str(writer), "--role", "COORD", "--to", "COORD",
                            "--file", str(note)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=300,
                           env=mezo_stand.stand_env(circuit))
        wcode, wout = r.returncode, ((r.stdout or "") + (r.stderr or ""))[-200:]

    # каталог под git: в коммите есть НЕ замороженный файл — git знает каталог, но не md-каналы
    (coord / "README.md").write_text("каталог согласования без md-каналов\n", encoding="utf-8")
    for args in (["init", "-q"], ["config", "user.email", "bite@example.invalid"],
                 ["config", "user.name", "bite"], ["add", "--", str(coord)],
                 ["commit", "-q", "-m", "приёмка 687: каталог без замороженных md"]):
        code, out = git_say(args, circuit)
        if code != 0 and args[0] in ("init", "commit", "add"):
            return case("⑭–⑱ НЕ ПРОГНАНЫ: контур не удалось положить под git",
                        False, f"git {args[0]} вернул {code}: {out.strip()[:200]}")

    healthy, broke, seen = {}, {}, {}
    sync_md, ph_md = coord / "sync.bite.md", coord / "phoenix" / "phoenix.bite.md"

    def positions(mark):
        """Состояние диска под каждую метку. Порядок МЕНЯТЬ НЕЛЬЗЯ: каждое следующее строится
        из предыдущего (файлы добавляются, потом уносятся по одному)."""
        if mark == "⑮":
            ph_md.parent.mkdir(exist_ok=True)
            sync_md.write_text("замороженный канал — приёмка 687\n", encoding="utf-8")
            ph_md.write_text("память роли — приёмка 687\n", encoding="utf-8")
            git_say(["add", "--", str(coord)], circuit)
            git_say(["commit", "-q", "-m", "приёмка 687: два замороженных md"], circuit)
            return []
        if mark == "⑯":
            sync_md.unlink()
            return [sync_md.name]
        if mark == "⑰":
            ph_md.unlink()
            return [sync_md.name, ph_md.name]
        return []

    for mark in FROZEN_MARKS:
        gone = positions(mark)
        seen[mark] = gone
        healthy[mark] = frozen_verdict(mark, run_guard(circuit), gone)
        broken.write_bytes(whole.replace(*BREAK_687).encode("utf-8"))
        try:
            r = subprocess.run([sys.executable, str(broken)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=900,
                               env=mezo_stand.stand_env(circuit))
            broke[mark] = frozen_verdict(mark, (r.stdout or "") + (r.stderr or ""), gone)
        finally:
            broken.unlink(missing_ok=True)

    ok &= case("⑭ под git, замороженных файлов git НЕ ЗНАЕТ — «ℹ️ … не вёл», а не «⚠️ … НОЛЬ»",
               healthy["⑭"][0],
               f"записка в ленту: код {wcode} · строка: {healthy['⑭'][1][:190]}", differ=True)
    ok &= case("⑮ git знает два файла, оба на диске — проверка зелёная, как было",
               healthy["⑮"][0], f"строка: {healthy['⑮'][1][:190]}", differ=True)
    ok &= case("⑯ унесён ОДИН из двух — провал С ИМЕНЕМ унесённого (прежде пропажа ЧАСТИ "
               "файлов была невидима: git спрашивали только о найденных на диске)",
               healthy["⑯"][0], f"строка: {healthy['⑯'][1][:190]}", differ=True)
    ok &= case("⑰ унесены ОБА — провал «ПРОПАЛИ», а НЕ «ℹ️ … не вёл» (две пустоты различимы)",
               healthy["⑰"][0], f"строка: {healthy['⑰'][1][:190]}", differ=True)
    flipped = sorted(m for m in FROZEN_MARKS if healthy[m][0] and not broke[m][0])
    ok &= case("⑱ НАРОЧНАЯ ПОЛОМКА (признак замороженного файла не узнаёт ни одного): "
               "краснеют РОВНО ⑯ и ⑰",
               flipped == ["⑯", "⑰"],
               f"покраснели {flipped or 'ничего — поломка не различима'} (ждали ['⑯', '⑰']) · "
               "пустой ответ git неотличим от чистоты: при файлах на диске проверка «не нашла "
               "расхождений» и была бы зелёной", differ=True)
    return ok



def main() -> int:
    ok = True
    if not GUARD.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: файла проверок нет — {GUARD}")

    with tempfile.TemporaryDirectory(prefix="bite-coord-") as tmp:
        root = pathlib.Path(tmp)

        # ① ЧУЖОЕ ИМЯ РЕПОЗИТОРИЯ. Здесь и умирала прежняя редакция.
        case_a = make_tree(root / "а", "tapas.archs/.mezosync/coordination")
        found = find_dirs(case_a)
        ok &= case("① каталог под ЧУЖИМ именем репозитория — НАХОДИТСЯ",
                   len(found) == 1 and found[0].parts[-3] == "tapas.archs",
                   f"нашлось: {[str(p.relative_to(case_a)) for p in found]} — прежняя редакция "
                   "искала `atlas.archs` и `<корень>/coordination`, и не нашла бы ничего",
                   differ=True)

        # ② РАСКЛАДКА ОБРАЗЦА: каталог прямо в корне контура.
        case_b = make_tree(root / "б", "coordination")
        ok &= case("② каталог в корне контура (раскладка образца) — находится",
                   [p.name for p in find_dirs(case_b)] == ["coordination"],
                   "вторая живая раскладка обязана остаться рабочей", differ=True)

        # ③ НЕТ ВОВСЕ. ⛔ Пустой список, а не выдуманный путь: «не нашли» обязано
        #    отличаться от «нашли». Прежняя редакция отдавала первый кандидат, и дальше он
        #    вёл себя как пустой каталог — то есть как чистый.
        case_v = make_tree(root / "в", "какой-то-репозиторий/src")
        ok &= case("③ каталогов нет вовсе — пустой список, а НЕ выдуманный путь",
                   find_dirs(case_v) == [],
                   "несуществующий путь ведёт себя как пустой каталог, а пустой каталог "
                   "проходит любую проверку", differ=True)

        # ④ ДВА СРАЗУ. Возвращаются оба: два каталога координации — тоже факт, и лучше
        #    увидеть оба, чем судить по одному.
        case_g = make_tree(root / "г", "coordination", "some.archs/.mezosync/coordination")
        ok &= case("④ два каталога сразу — возвращаются ОБА, а не первый",
                   len(find_dirs(case_g)) == 2,
                   "судить по первому значит молча не смотреть во второй", differ=True)

        # ⑤ ЗАПРЕЩЁННЫЙ СПОСОБ ПРОЙТИ, названный в критерии карточки: дописать чужое имя
        #    рядом с нашим. Проверяем, что имя `atlas.archs` НЕ привилегированно: контур,
        #    где такого репозитория нет вовсе, обслуживается ровно так же.
        case_d = make_tree(root / "д", "совсем-другое-имя/.mezosync/coordination")
        ok &= case("⑤ ⛔ имя `atlas.archs` не привилегированно",
                   len(find_dirs(case_d)) == 1 and "atlas" not in find_dirs(case_d)[0].parts[-3],
                   "перечень имён неполон ровно на то имя, которым ещё не обожглись — "
                   "поэтому признак, а не перечень", differ=True)

    # ⑥ ЖИВОЙ КОНТУР. Починка обязана не сломать своё: у нас каталог лежит в репозитории
    #    координатора, и он должен находиться тем же признаком.
    own = find_dirs(mezo_paths.container_root(__file__))
    ok &= case("⑥ ЖИВОЙ КОНТУР: каталог по-прежнему находится",
               len(own) >= 1 and all(p.is_dir() for p in own),
               f"нашлось {len(own)}: {[p.parts[-3] for p in own]}", differ=True)

    # ⑦⑧⑨⑩ ПРОГОН В КОНТУРЕ, ГДЕ КАТАЛОГА НЕТ. Критерий карточки требует именно прогона:
    #        у нас нет отрицательного случая по построению, значит его надо построить.
    if TEMPLATE is None:
        print("⚠️ ⑦–⑩ НЕ ПРОГНАНЫ: образца контура нет на диске — это отказ мерить, "
              "а не «чисто»")
        return 0 if ok else 1
    with tempfile.TemporaryDirectory(prefix="bite-coord-run-") as tmp:
        circuit = pathlib.Path(tmp) / "контур"
        # ⚠️ `--path` — это САМ каталог мезосинка, а не контейнер: сборка кладёт скрипты
        #    прямо в него. Первая редакция приёмки передала сюда контейнер и потом искала
        #    сторожа на уровень глубже — прогон падал «нет файла», а случаи ⑦–⑩ краснели
        #    так, будто дефект в стороже. Приёмка, ошибающаяся в раскладке, обвиняет продукт.
        r = subprocess.run([sys.executable, str(TEMPLATE / "scripts" / "init-group.py"),
                            "--name", "bite", "--path", str(circuit / ".mezosync"),
                            "--roles", "COORD"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=900, env=mezo_stand.stand_env(circuit))
        if r.returncode != 0:
            print(f"⛔ ⑦–⑩ НЕ ЗАПУСТИЛИСЬ: сборка контура вернула {r.returncode}\n{r.stdout}"
                  f"\n{r.stderr}")
            return 1
        # ⚡ ИСПЫТЫВАЕМ ЖИВОГО СТОРОЖА, А НЕ КОПИЮ ИЗ ОБРАЗЦА. Сборка кладёт в контур
        #    сторожа ИЗ ОБРАЗЦА — то есть последнюю ПЕРЕНЕСЁННУЮ редакцию, а не ту, что
        #    сейчас правится. 🩸 Первая редакция приёмки этого не делала, и нарочные поломки
        #    живого файла её не будили: пять из семи прошли мимо, приёмка была зелёной
        #    на сломанном коде. Класс известный — «испытываем не то, что чиним».
        #    ⚖️ Контур нужен ради РАСКЛАДКИ (чужие имена, отсутствие каталога), код — живой.
        shutil.copy(GUARD, circuit / ".mezosync" / "scripts" / "guard-all.py")
        # сносим ВСЕ каталоги координации И папки моста — строим то самое положение,
        # которого у нас нет. ⚠️ Мост сносится отдельно: он ищется своим признаком,
        # а не отсчитывается от координации (первая редакция починки их связала, и пять
        # случаев приёмки моста покраснели разом).
        for rel in find_dirs(circuit) + find_bridge(circuit):
            shutil.rmtree(rel)
        before = run_guard(circuit)
        with_yellow = run_guard(circuit, {"MEZO_NO_COORDINATION": "yes"})

        refusal_line = line_of(before, "замороженные md")
        ok &= case("⑦ ПРОГОН БЕЗ КАТАЛОГА: проверка ОТКАЗЫВАЕТ и называет признак",
                   refusal_line.startswith("⛔") and "НЕ НАЙДЕН" in refusal_line
                   and "coordination" in refusal_line,
                   f"строка: {refusal_line[:150] or '(строки нет вовсе)'}", differ=True)

        yellow_line = line_of(with_yellow, "замороженные md")
        ok &= case("⑧ ВСТРЕЧНЫЙ: явное слово превращает отказ в жёлтое «не поставлена»",
                   not yellow_line.startswith("⛔")
                   and "НЕ ПОСТАВЛЕНА" in (line_of(with_yellow, "НЕ ПОСТАВЛЕНА") or ""),
                   "без этого выхода отказ стал бы вечно-красным у контура, который "
                   "каталогом не пользуется, — а вечно-красный учит не верить красному",
                   differ=True)

        bridge = line_of(before, "мост соседей")
        ok &= case("⑨ ВТОРАЯ проверка того же каталога: мост соседей говорит вслух",
                   "НЕ ПРОВЕРЯЛИСЬ" in bridge or "смотреть негде" in bridge,
                   f"строка: {bridge[:150] or '(строки нет вовсе — молчит зелёным)'}",
                   differ=True)

        # ⑩ ОТКАЗ НЕ ГАСИТ ОСТАЛЬНОЕ. Первая редакция починки писала здесь `return`, и он
        #    погасил бы восемь следующих проверок МОЛЧА — тот же класс в новом месте.
        counts = [int(m) for m in re.findall(r"\((\d+) проверок\)", before + with_yellow)]
        ok &= case("⑩ отказ не гасит остальные проверки: их число не падает",
                   len(counts) == 2 and counts[0] == counts[1] and counts[0] > 5,
                   f"проверок при отказе {counts[0] if counts else '?'}, "
                   f"при жёлтом {counts[1] if len(counts) > 1 else '?'} — «return» здесь "
                   "унёс бы восемь следующих, и итог назвал бы меньше, чем есть",
                   differ=True)

    # ⑪⑫⑬ ДВА НОСИТЕЛЯ ОБЪЯВЛЕНИЯ И ЕГО СРОК ГОДНОСТИ (записка @COORD #3766).
    #      Переменная окружения живёт ОДИН ВЫЗОВ ⇒ полнота держалась памятью зовущего.
    #      Файл живёт долго ⇒ переживает свою причину. Нужны оба и сигнал о споре.
    if TEMPLATE is not None:
        with tempfile.TemporaryDirectory(prefix="bite-coord-carrier-") as tmp2:
            circuit2 = pathlib.Path(tmp2) / "контур"
            r2 = subprocess.run([sys.executable, str(TEMPLATE / "scripts" / "init-group.py"),
                                 "--name", "bite", "--path", str(circuit2 / ".mezosync"),
                                 "--roles", "COORD"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=900,
                                env=mezo_stand.stand_env(circuit2))
            if r2.returncode == 0:
                shutil.copy(GUARD, circuit2 / ".mezosync" / "scripts" / "guard-all.py")
                marker = circuit2 / ".mezo-no-coordination"

                # ⑪ ДОЛГИЙ НОСИТЕЛЬ: каталогов нет, объявление лежит ФАЙЛОМ.
                for rel in find_dirs(circuit2) + find_bridge(circuit2):
                    shutil.rmtree(rel)
                marker.write_text("", encoding="utf-8")
                by_file = run_guard(circuit2)
                line11 = line_of(by_file, "замороженные md")
                ok &= case("⑪ объявление ФАЙЛОМ переживает вызов — жёлтое, носитель назван",
                           not line11.startswith("⛔") and "НЕ ПОСТАВЛЕНА" in by_file
                           and ".mezo-no-coordination" in by_file,
                           f"строка: {(line_of(by_file, 'НЕ ПОСТАВЛЕНА') or '(нет)').strip()[:110]}",
                           differ=True)

                # ⑫ ОБЪЯВЛЕНИЕ ПЕРЕЖИЛО ПРИЧИНУ: каталог вернулся, файл лежит.
                (circuit2 / "coordination").mkdir(exist_ok=True)
                dispute = run_guard(circuit2)
                ok &= case("⑫ каталог НАЙДЕН, а объявление лежит — «спорит с находкой»",
                           "СПОРИТ С НАХОДКОЙ" in dispute,
                           "долгий носитель переживает свою причину; тихо продолжать — "
                           "значит завести вечно-жёлтую проверку при живом предмете",
                           differ=True)

                # ⑬ ВСТРЕЧНЫЙ к ⑫: объявления нет — и спора нет. Иначе строка печаталась
                #    бы всегда и перестала что-либо значить.
                marker.unlink()
                quiet = run_guard(circuit2)
                ok &= case("⑬ ВСТРЕЧНЫЙ: объявления нет — о споре молчим",
                           "СПОРИТ С НАХОДКОЙ" not in quiet,
                           "сигнал, звучащий всегда, неотличим от сломанного", differ=True)

    # ⑭–⑱ ЧТО ЗНАЕТ GIT О ЗАМОРОЖЕННЫХ md (карточка #687) — в контуре ПОД git
    if TEMPLATE is not None:
        with tempfile.TemporaryDirectory(prefix="bite-coord-git-") as tmp3:
            circuit3 = pathlib.Path(tmp3) / "контур"
            r3 = subprocess.run([sys.executable, str(TEMPLATE / "scripts" / "init-group.py"),
                                 "--name", "bite", "--path", str(circuit3 / ".mezosync"),
                                 "--roles", "COORD"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=900,
                                env=mezo_stand.stand_env(circuit3))
            if r3.returncode != 0:
                ok &= case("⑭–⑱ НЕ ПРОГНАНЫ: сборка контура не удалась", False,
                           f"init-group.py вернул {r3.returncode}: "
                           f"{((r3.stdout or '') + (r3.stderr or '')).strip()[-200:]}")
            else:
                # испытуемая копия — живая, как у ⑦–⑩: сборка кладёт редакцию ИЗ ПАКЕТА
                shutil.copy(GUARD, circuit3 / ".mezosync" / "scripts" / "guard-all.py")
                ok &= frozen_git_cases(circuit3)

    print()
    print(f"{'✅ ПОИСК КАТАЛОГА ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
