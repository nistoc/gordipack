# -*- coding: utf-8 -*-
r"""
bite-milestone-step-set.py — приёмка карточки #509: веха-рубеж сверяет НАБОР записанных
шагов с каталогом миграций и при пропуске В СЕРЕДИНЕ отказывает ПОИМЁННО.

🔴 ПОВОД. Защита вехи смотрела на ЧИСЛО шагов сверх отметки: «7 из 7» и «7 из 9» для
счётчика одно и то же. Пустой ХВОСТ ловился, дырка В СЕРЕДИНЕ — нет. Нашёл второй
потребитель нашего набора шагов (соседний контур AIA), мы воспроизвели на копии.

Каждый случай идёт на СВОЁМ стенде — копии живой базы И копии каталога скриптов
(scripts/schema_journal.py + scripts/migrations/*.py). Живое не открывается на запись
ни разу: веха на стенде находит свою базу сама, потому что её умолчание --db считается
от расположения файла.

СЛУЧАИ
  ① полный набор проходит без возражений: копия без рубежа v5 ⇒ «набор полон: все 7»,
     код 0. Без этого случая любой зелёный ответ ниже ничего не значит
  ② 🎯 ГЛАВНЫЙ: из журнала убраны ДВА шага ИЗ СЕРЕДИНЫ ⇒ отказ, и в тексте названы
     ОБА имени файла. Это тот самый случай, который прежняя защита пропускала молча
  ③ ВСТРЕЧНЫЙ (прежняя защита цела): убраны ВСЕ шаги после v4 ⇒ отказ приходит от
     счётчика («сверх отметки ноль шагов»), а не от новой сверки
  ④ ВСТРЕЧНЫЙ ложным находкам: веха v4, окно «с начала». Три шага записаны под
     ПОРЯДКОВЫМИ именами (008-, 009-), а файлы переименованы на именование с датой ⇒
     сверка обязана свести их по хвосту и НЕ объявить пропажей. 11 из 11
  ⑤ различение внутри ④: из журнала убрана запись «009-role-rights» ⇒ отказ ПОИМЁННО,
     назван файл 20260808-role-rights.py. Без ⑤ случай ④ был бы зелёным по построению
  ⑥ запись в журнале БЕЗ файла на диске ⇒ ЗАМЕЧАНИЕ, а не отказ: код 0, имя названо
  ⑦ ВСТРЕЧНЫЙ к ⑥ и предел, названный вслух: файл убран из каталога, запись в журнале
     цела ⇒ проверка его НЕ требует. Ожидаемое строится ИЗ КАТАЛОГА, а не из описи
  ⑧ отказ ⑤ имеет СВОЮ причину: в его выводе НЕТ слов прежней защиты. Красное,
     пришедшее не от того сторожа, посылает чинить не то
  ⑨ при отказе веха НИЧЕГО не пишет: записи рубежа в стенде ② после прогона нет
  ⑪ 🎯 ДВОЙНИК ХВОСТА ПРЯЧЕТ ДЫРКУ (карточка #536, стенд @COORD ⓑ, записка #4722): в каталог
     подсажен 20260821-tool-leases.py — копия настоящего шага с датой в окне, тот же хвост, —
     и из журнала убрана запись 20260816-tool-leases ⇒ отказ, код ≠ 0, и названы ОБА файла
     (ни у одного нет записи под своим полным именем). До 04.09 22:15 UTC веха отвечала
     «⚠️ исключены: tool-leases · ожидается 6 · ✅ набор полон · код 0». Контроль без
     двойника — случай ②: он отказывал и раньше, и отказывает теперь
  ⑫ ВСТРЕЧНЫЙ к ⑪ (стенд ⓔ): тот же двойник при ЦЕЛОЙ записи ⇒ замечания «файла в
     каталоге нет» НЕТ (файлов на диске два, пропажи не было), слова «исключены» нет,
     ожидается 8 (семь шагов + двойник), и красен РОВНО двойник 20260821-tool-leases.py —
     файл-шаг в окне без записи под своим именем. Это не смягчение, а тот же принцип,
     что у ⑦: ожидаемое строится ИЗ КАТАЛОГА, и двойник — не исключение из него
  ⑩ контроль: живая база и живые файлы вех не изменились (размер и содержимое сверены
     ДО и ПОСЛЕ; первая редакция моей прошлой приёмки судила живую базу и краснела
     от честной работы коллег — карточка #483)

⚖️ СПИСОК ШАГОВ ДЛЯ ③ БЕРЁТСЯ ИЗ ЖИВОГО ЖУРНАЛА (только чтение), а не снимком: снимок из
   девяти имён (31.08) протух через четверо суток — три шага 04.09 легли ПОСЛЕ него, хвост
   стенда ③ перестал быть пустым, и случай краснел не по своей причине (нашёл @COORD,
   приёмка карточки #509). Снимок лечили снимком побольше — и он протух так же.

КОНТРОЛЬНАЯ ПАРА — приёмка обязана краснеть на больном:
    --break slug   голова имени снова «6–8 цифр» ⇒ хвосты 008-/009- не сводятся
                   ПРОГНОЗ: 11 из 12, красный РОВНО ④ (три ложных пропажи из одиннадцати)
    --break guard  вызов сверки набора выключен ⇒ дырка в середине снова не видна
                   ПРОГНОЗ: 3 из 12; зелёными остаются РОВНО ③ ⑨ ⑩ — то есть встречный
                   на прежнюю защиту, «при отказе ничего не пишет» и контроль живого.
                   🩸 Первый мой прогноз здесь был «6 из 10, красные ② ⑤ ⑥ ⑧» и он НЕВЕРЕН:
                   я считала только случаи, ждущие ОТКАЗА, и забыла, что ① ④ ⑦ сверяют
                   ЧИСЛО ожидаемых шагов, а выключенная сверка отвечает нулём на всё.
                   Пересчитан ДО прогона и оставлен здесь надгробием: прогноз, который
                   подгоняют ПОСЛЕ, не проверяет ничего
    --break twin   двойники хвоста снова НЕ ожидаются (прежнее поведение) ⇒ дырка под
                   двойником снова невидима. ПРОГНОЗ: 10 из 12, красные РОВНО ⑪ ⑫
                   (прогноз назван ДО прогона 04.09 22:16 UTC, сошёлся первым же прогоном)
                   🩸 А чистый прогон первым разом дал 10 из 12 — ⑪⑫ красные ПРИ ВЕРНОМ
                   поведении вехи: условие искало слово «исключены», а новая честная строка
                   вехи говорит «из сверки НЕ исключены». Проверка споткнулась о мой же
                   текст. ⚡ КЛАСС: условие «плохого слова нет» обязано искать ФРАЗУ ЦЕЛИКОМ,
                   иначе отрицание той же фразы красит исправное

Запуск:
    python <КОНТУР>/vnext-tools/bite-milestone-step-set.py
"""
import argparse
import hashlib
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

MILESTONE_V4 = "20260810-milestone-v4.py"
MILESTONE_V5 = "20260828-milestone-v5.py"

SLUG_INTACT = "_DATED = _re.compile(r'^(\\d+)-(.+)$')"
SLUG_BROKEN = "_DATED = _re.compile(r'^(\\d{6,8})-(.+)$')"
CHECK_CALL_INTACT = "step_set = milestone_step_set(conn, __file__, VERSION)"
CHECK_CALL_EMPTY = ("step_set = {'window': ('', ''), 'prev': None, 'expected': {},\n"
                "             'missing': [], 'orphan': [], 'ambiguous': []}")
# двойник хвоста ожидается под полным именем — эта строка и есть починка карточки #536
TWIN_INTACT = "expected[f[:-3]] = f"
TWIN_BROKEN = "pass  # ⟨порча twin: двойник не ожидается⟩"
STEP_REAL = "20260816-tool-leases.py"
STEP_TWIN = "20260821-tool-leases.py"

OK = FAIL = 0


def case(name, ok, detail=""):
    global OK, FAIL
    print(("[ok]  " if ok else "[FAIL]"), name)
    if detail:
        print("       " + detail)
    OK, FAIL = OK + (1 if ok else 0), FAIL + (0 if ok else 1)


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def line_with(output, word, otherwise="строки нет"):
    return next((s.strip() for s in output.splitlines() if word in s), otherwise)


def sandbox(label, remove_versions=(), remove_steps=(), remove_files=(), seed=(),
          duplicate=(), break_kind=None):
    """Копия базы + копия скриптов. Возвращает (корень, путь_к_базе, каталог_вех).

    удвоить — пары (файл, имя_копии): двойник хвоста в каталоге стенда (карточка #536).
    """
    root = mezo_stand.new(label)
    scripts_dir = root / "scripts"
    (scripts_dir / "migrations").mkdir(parents=True)
    shutil.copy2(SCRIPTS / "schema_journal.py", scripts_dir / "schema_journal.py")
    for f in sorted((SCRIPTS / "migrations").glob("*.py")):
        shutil.copy2(f, scripts_dir / "migrations" / f.name)
    for name in remove_files:
        (scripts_dir / "migrations" / name).unlink()
    for name, copy_name in duplicate:
        shutil.copy2(scripts_dir / "migrations" / name, scripts_dir / "migrations" / copy_name)

    if break_kind == "twin":
        p = scripts_dir / "schema_journal.py"
        t = p.read_text(encoding="utf-8")
        assert TWIN_INTACT in t, "нечего портить: строка ожидания двойника не найдена"
        p.write_text(t.replace(TWIN_INTACT, TWIN_BROKEN, 1), encoding="utf-8", newline="")
    if break_kind == "slug":
        p = scripts_dir / "schema_journal.py"
        t = p.read_text(encoding="utf-8")
        assert SLUG_INTACT in t, "нечего портить: строка свёртки не найдена"
        p.write_text(t.replace(SLUG_INTACT, SLUG_BROKEN, 1), encoding="utf-8", newline="")
    if break_kind == "guard":
        for name in (MILESTONE_V4, MILESTONE_V5):
            p = scripts_dir / "migrations" / name
            t = p.read_text(encoding="utf-8")
            assert CHECK_CALL_INTACT in t, "нечего портить: вызов сверки не найден"
            p.write_text(t.replace(CHECK_CALL_INTACT, CHECK_CALL_EMPTY, 1), encoding="utf-8", newline="")

    db_path = root / "mezosync.db"
    shutil.copy2(LIVE_DB, db_path)
    c = sqlite3.connect(db_path)
    # 🩸 07.09 (объявлена v6): снимая на копии отметку, снимаем и все ПОЗДНЕЙШИЕ — иначе
    # выборка версии считает «сверх отметки» от оставшейся поздней (v6) и отвечает 0,
    # веха v5 отказывает первой же защитой («объявлять нечего»), и все стенды красны
    # не по своей причине. Поздние — по ДАТЕ ФАЙЛА вехи в живом каталоге шагов.
    for v in list(remove_versions) + list(remove_steps) + later_milestones(remove_versions):
        c.execute("DELETE FROM schema_migrations WHERE version=?", (v,))
    for v in seed:
        c.execute("INSERT INTO schema_migrations(version, applied_at, note) VALUES(?,?,?)",
                  (v, "2026-08-26 00:00:00", "подсадка приёмки #509"))
    c.commit()
    c.close()
    return root, db_path, scripts_dir / "migrations"


def later_milestones(versions):
    """Отметки версий, чей файл вехи датирован ПОЗЖЕ самой поздней из снимаемых (только чтение)."""
    dates = {}
    for f in (SCRIPTS / "migrations").glob("*-milestone-v*.py"):
        m = re.match(r"^(\d{8})-milestone-(v\d+)\.py$", f.name)
        if m:
            dates[m.group(2)] = m.group(1)
    floor = max((dates.get(v, "") for v in versions), default="")
    return sorted(v for v, d in dates.items() if v not in versions and floor and d > floor)


def run(migrations_dir, milestone_file, flags=("--dry-run",)):
    r = subprocess.run([sys.executable, str(migrations_dir / milestone_file), *flags],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# 🩸 Первая редакция перечисляла только СЕМЬ шагов окна v5 — и случай ③ покраснел
# не по своей причине: сверх отметки оставались ещё два шага от 30.08, которые лежат
# ПОЗЖЕ рубежа v5. Счётчик честно отвечал «2», прежняя защита молчала, и красное
# приходило от новой сверки — то есть случай судил не то, что называл.
# ⚡ Чтобы «пустой хвост» был правда пустым, убирать надо ВСЁ после предыдущего рубежа,
# а не только то, что укладывается в окно объявляемого.
# ⚰️ ЗДЕСЬ СТОЯЛ СНИМОК ИЗ ДЕВЯТИ ИМЁН (31.08) — и протух через четверо суток тем же
# классом: три шага 04.09 легли после него, хвост стенда ③ перестал быть пустым, случай
# краснел не по своей причине (нашёл @COORD приёмкой карточки #509 — записка #4722).
# Снимок лечили снимком побольше. Теперь список берётся ИЗ ЖИВОГО ЖУРНАЛА, только чтение:
# всё, что записано ПОСЛЕ рубежа-предшественника (по порядку записи, рубежи не в счёт).
def steps_after(after_version):
    c = sqlite3.connect("file:" + str(LIVE_DB) + "?mode=ro", uri=True)
    r = c.execute("SELECT rowid FROM schema_migrations WHERE version=?", (after_version,)).fetchone()
    assert r, "в живом журнале нет рубежа " + after_version + " — стенд ③ строить не от чего"
    steps = [v for (v,) in c.execute(
        "SELECT version FROM schema_migrations WHERE rowid > ? AND version NOT GLOB 'v[0-9]*' "
        "ORDER BY rowid", (r[0],))]
    c.close()
    return steps


def main():
    ap = argparse.ArgumentParser(description="приёмка #509: веха сверяет НАБОР шагов")
    ap.add_argument("--break", "--порча", dest="break_kind", choices=["slug", "guard", "twin"], default=None,
                    help="контрольная пара: нарочно сломать и убедиться, что краснеет")
    a = ap.parse_args()
    break_kind = a.break_kind

    live_before = (LIVE_DB.stat().st_size, fingerprint(LIVE_DB))
    milestones_before = {milestone_name: fingerprint(SCRIPTS / "migrations" / milestone_name) for milestone_name in (MILESTONE_V4, MILESTONE_V5)}

    print("=" * 78)
    print("ПРИЁМКА #509 — веха сверяет НАБОР шагов, а не их число")
    print("живая база (только чтение): " + str(LIVE_DB))
    if break_kind:
        print("⚠️ КОНТРОЛЬНАЯ ПАРА: нарочная поломка «" + break_kind + "» — приёмка ОБЯЗАНА покраснеть")
    print("=" * 78)

    # ① полный набор
    _, _, migrations_dir = sandbox("m509-a", remove_versions=["v5"], break_kind=break_kind)
    code1, output1 = run(migrations_dir, MILESTONE_V5)
    case("① полный набор проходит без возражений (v5: 7 из 7)",
           code1 == 0 and "набор полон" in output1 and "ожидается шагов 7" in output1,
           "код " + str(code1) + " · " + line_with(output1, "ожидается"))

    # ② главный: две дырки в середине
    _, db_b, migrations_dir = sandbox("m509-b", remove_versions=["v5"],
                            remove_steps=["20260816-tool-leases",
                                         "20260822-sync-backoff-bridge-mtime"],
                            break_kind=break_kind)
    code2, output2 = run(migrations_dir, MILESTONE_V5)
    named_1 = "20260816-tool-leases.py" in output2
    named_2 = "20260822-sync-backoff-bridge-mtime.py" in output2
    case("② дырка В СЕРЕДИНЕ: отказ, и названы ОБА пропавших шага",
           code2 != 0 and named_1 and named_2 and "не хватает шагов" in output2,
           "код " + str(code2) + " · назван первый: " + str(named_1)
           + " · назван второй: " + str(named_2))

    # ③ встречный: пустой хвост ловится прежней защитой
    _, _, migrations_dir = sandbox("m509-c", remove_versions=["v5"], remove_steps=steps_after("v4"), break_kind=break_kind)
    code3, output3 = run(migrations_dir, MILESTONE_V5)
    case("③ ВСТРЕЧНЫЙ: пустой ХВОСТ по-прежнему ловит прежняя защита (счётчик)",
           code3 != 0 and "сверх отметки ноль шагов" in output3,
           "код " + str(code3) + " · причина: "
           + ("счётчик" if "сверх отметки ноль шагов" in output3 else "НЕ счётчик"))

    # ④ окно «с начала»: порядковые имена не считаются пропажей
    _, _, migrations_dir = sandbox("m509-d", remove_versions=["v4", "v5"], break_kind=break_kind)
    code4, output4 = run(migrations_dir, MILESTONE_V4)
    case("④ ВСТРЕЧНЫЙ ложным находкам: 008-/009- сведены по хвосту, 11 из 11",
           code4 == 0 and "набор полон" in output4 and "ожидается шагов 11" in output4,
           "код " + str(code4) + " · " + line_with(output4, "ожидается"))

    # ⑤ различение внутри ④
    _, _, migrations_dir = sandbox("m509-e", remove_versions=["v4", "v5"],
                       remove_steps=["009-role-rights"], break_kind=break_kind)
    code5, output5 = run(migrations_dir, MILESTONE_V4)
    case("⑤ различает: убрана запись 009-role-rights ⇒ отказ ПОИМЁННО",
           code5 != 0 and "20260808-role-rights.py" in output5,
           "код " + str(code5) + " · имя в тексте: " + str("20260808-role-rights.py" in output5))

    # ⑥ запись без файла — замечание, не отказ
    _, _, migrations_dir = sandbox("m509-f", remove_versions=["v5"],
                       seed=["20260826-nothing-on-disk"], break_kind=break_kind)
    code6, output6 = run(migrations_dir, MILESTONE_V5)
    case("⑥ запись в журнале БЕЗ файла — ЗАМЕЧАНИЕ, не отказ",
           code6 == 0 and "20260826-nothing-on-disk" in output6
           and "файла в каталоге нет" in output6,
           "код " + str(code6) + " · замечание напечатано: "
           + str("файла в каталоге нет" in output6))

    # ⑦ файл убран, запись цела — проверка его не требует
    _, _, migrations_dir = sandbox("m509-g", remove_versions=["v5"],
                       remove_files=["20260816-tool-leases.py"], break_kind=break_kind)
    code7, output7 = run(migrations_dir, MILESTONE_V5)
    case("⑦ предел вслух: файла нет в каталоге ⇒ шаг не требуется (6 из 6)",
           code7 == 0 and "ожидается шагов 6" in output7,
           "код " + str(code7) + " · " + line_with(output7, "ожидается"))

    # ⑧ отказ ⑤ пришёл от СВОЕГО сторожа
    case("⑧ отказ ⑤ имеет СВОЮ причину: слов прежней защиты в нём нет",
           code5 != 0 and "сверх отметки ноль шагов" not in output5,
           "в тексте отказа ⑤ "
           + ("нет" if "сверх отметки ноль шагов" not in output5 else "ЕСТЬ")
           + " слов счётчика")

    # ⑨ при отказе веха ничего не пишет
    c = sqlite3.connect("file:" + str(db_b) + "?mode=ro", uri=True)
    found = c.execute("SELECT 1 FROM schema_migrations WHERE version='v5'").fetchone()
    c.close()
    case("⑨ при отказе веха НИЧЕГО не записала: отметки версии v5 в стенде ② нет",
           found is None, "запись v5 " + ("отсутствует" if found is None else "ПОЯВИЛАСЬ"))

    # ⑪ 🎯 двойник хвоста + убранная запись настоящего шага (карточка #536, стенд ⓑ)
    _, _, migrations_dir = sandbox("m536-b", remove_versions=["v5"],
                       remove_steps=[STEP_REAL[:-3]],
                       duplicate=[(STEP_REAL, STEP_TWIN)], break_kind=break_kind)
    code11, output11 = run(migrations_dir, MILESTONE_V5)
    case("⑪ ДВОЙНИК ХВОСТА не прячет дырку: отказ, названы ОБА файла, слова «исключены» нет",
           code11 != 0 and "не хватает шагов" in output11
           and STEP_REAL in output11 and STEP_TWIN in output11
           and "из сверки исключены" not in output11,
           "код " + str(code11) + " · " + line_with(output11, "ожидается")
           + " · настоящий назван: " + str(STEP_REAL in output11)
           + " · двойник назван: " + str(STEP_TWIN in output11))

    # ⑫ встречный: двойник при ЦЕЛОЙ записи (стенд ⓔ)
    _, _, migrations_dir = sandbox("m536-e", remove_versions=["v5"],
                       duplicate=[(STEP_REAL, STEP_TWIN)], break_kind=break_kind)
    code12, output12 = run(migrations_dir, MILESTONE_V5)
    red12 = [s.strip() for s in output12.splitlines() if s.strip().startswith("🔴")]
    case("⑫ ВСТРЕЧНЫЙ: двойник при целой записи — «файла нет» НЕ печатается, ожидается 8, "
           "красен РОВНО двойник",
           code12 != 0 and "файла в каталоге нет" not in output12
           and "из сверки исключены" not in output12 and "ожидается шагов 8" in output12
           and red12 == ["🔴 " + STEP_TWIN],
           "код " + str(code12) + " · " + line_with(output12, "ожидается")
           + " · красные: " + (", ".join(red12) or "нет")
           + " · «файла нет»: " + str("файла в каталоге нет" in output12))

    # ⑩ контроль: живое не тронуто
    live_after = (LIVE_DB.stat().st_size, fingerprint(LIVE_DB))
    milestones_after = {milestone_name: fingerprint(SCRIPTS / "migrations" / milestone_name) for milestone_name in (MILESTONE_V4, MILESTONE_V5)}
    case("⑩ контроль: живая база и живые вехи не изменились",
           live_before == live_after and milestones_before == milestones_after,
           "база " + ("цела" if live_before == live_after else "ИЗМЕНИЛАСЬ")
           + " · вехи " + ("целы" if milestones_before == milestones_after else "ИЗМЕНИЛИСЬ"))

    print("=" * 78)
    print("ИТОГ: " + str(OK) + " из " + str(OK + FAIL))
    if break_kind:
        print("⚠️ это был прогон с нарочной поломкой «" + break_kind + "» — красное здесь ОЖИДАЕТСЯ")
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
