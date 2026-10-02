#!/usr/bin/env python
# SURFACES: memory
# -*- coding: utf-8 -*-
r"""ПРИЁМКА memory-records.py — карточка #524, встречные случаи + порча на копии.

⚖️ ЗАЧЕМ ЭТОТ ФАЙЛ. Зелёный прогон инструмента доказывает, что инструмент РАБОТАЕТ.
Он НЕ доказывает, что инструмент СПОСОБЕН ПОКРАСНЕТЬ. Приёмка ломает инструмент нарочно
и требует красного: проверка, которая не краснеет на поломке, не проверяет ничего.

🩸 ОПЛАЧЕНО ДВА ЧАСА НАЗАД, НА СОСЕДНЕЙ ПРИЁМКЕ (bite-memory-archive.py, 04.09):
первый же прогон порчи дал ✅ вместо 🔴 — приёмка звала инструмент по ВПЕЧАТАННОМУ
абсолютному пути и потому судила ЖИВОЙ файл, а не испорченную копию.
⚡ КЛАСС: ИСПЫТЫВАЕМ НЕ ТО, ЧТО ЧИНИМ. ⇒ здесь инструмент берётся строго от себя:
`Path(__file__).with_name(...)`, а порченая копия зовётся СВОИМ путём.

ЧТО ПРОВЕРЯЕТСЯ
    ① сборка сходится знак в знак по всем разделам          (критерий ④ карточки)
    ② сумма знаков записей = сумме прежних тел              (критерий ③)
    ③ жребий: куски прежнего тела находятся в записях,
       причём КУСОК НА СТЫКЕ двух записей — не потеря       (критерий ③, вторая половина)
    ④ поле «условие снятия» различает ТРИ состояния         (критерий ⑥)
    ⑤ снятая запись читается отбором вместе с «чем снята»   (критерий ②, вопрос 3)
    ⑥ отбор отвечает СПИСКОМ, а не потоком тел              (критерий ②, буква)
    ⑦ правка чужой записи ОТКАЗЫВАЕТ                        (слово владельца 04.09)
    ⑧ правка несуществующей записи КРАСНЕЕТ, а не молчит
    ⑨ повторный разбор ОТКАЗЫВАЕТ (не затирает ручные поля)
    ⑩ ПОРЧА: сломанная сборка обязана покраснеть
    ⑪ ПОРЧА: потерянный кусок обязан покраснеть

Зовут так:
    python <КОНТУР>/vnext-tools/bite-memory-records.py
"""
from __future__ import annotations

import io
import os
import pathlib
import random
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

HERE = pathlib.Path(__file__).resolve().parent
# ⛔ НЕ ВПЕЧАТАННЫЙ ПУТЬ: инструмент берётся от РАСПОЛОЖЕНИЯ ЭТОГО ФАЙЛА, иначе приёмка,
# положенная в песочницу вместе с копией инструмента, продолжит судить живой оригинал.
TOOL = HERE / "memory-records.py"
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402 — база контура выводится от расположения, не впечатана (перенос в образец 13.09)
import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

DB = mezo_paths.live_db(__file__)
ROLE = "PROTO"
SEED = 524

# 🩹 ДОГОН (карточка #667, пустой новый контур): на свежесобранном контуре у PROTO
# ещё нет НИ ОДНОЙ разобранной записи (память пуста по построению пакета, а не по
# чьей-то ошибке) — приёмке нечем судить, и она падала отказом ДО единого случая.
# Подставная роль заводится своим ходом: тело раздела пишется штатно (save-phoenix.py),
# разбор на записи — ЭТИМ ЖЕ инструментом (--разобрать). Приёмка продолжает проверять
# МЕХАНИЗМ разбора/сборки, а не слова живой памяти PROTO — живой контур не тронут:
# подставная роль заводится на КОПИИ базы.
SEED_ROLE = "BITEMEMREC"

# Заполнитель БЕЗ слова «право» — нужен числом знаков: случай ⑥ судит, что отбор
# отвечает КОРОТКИМ списком, а не потоком тел (критерий «вывод < тела ÷ 3»), и это
# различимо только когда тело ЗАМЕТНО больше служебного оформления списка (разделители,
# шапка, подвал — у списка из одной-двух строк это ~700 знаков само по себе).
_FILLER = (
    "строка заполнителя приёмки bite-memory-records, без искомого слова — нужна "
    "числом знаков, чтобы тело раздела было заметно больше служебного оформления "
    "списка (разделители, шапка, подвал печатаются всегда, независимо от числа строк). "
)
SEED_FIXTURES = {
    "state": (
        "## 🎯 ПОДСТАВНОЙ РАЗДЕЛ ПРИЁМКИ bite-memory-records (карточка #667)\n"
        "Этот текст заведён САМОЙ приёмкой на копии базы — на пустом свежесобранном\n"
        "контуре у роли PROTO ещё нет ни одной разобранной записи, и мерить нечем.\n"
        "Подставная роль разбирается ТЕМ ЖЕ инструментом (хук save-phoenix.py после\n"
        "сохранения тела), что и живая память, — проверяется МЕХАНИЗМ, а не слова\n"
        "чужой памяти. " + _FILLER * 2 + "\n\n"
        "## право на отправку записки\n"
        "⛔ слово владельца: право отправлять записки есть только у ролей из реестра.\n"
        "мандат подтверждён 2026-09-04 13:41 UTC.\n\n"
        "## 📏 замер числом\n"
        "замер приёмки: подставных записей несколько, разделов два, слово «право» "
        "встречается в ОДНОМ блоке — отбор обязан вернуть короткий список, не все тела. "
        + _FILLER * 2 + "\n\n"
        "## ⚡ класс урока первый\n"
        "класс: подставные данные не должны зависеть от того, что уже лежит в памяти "
        "ролей контура — иначе приёмка молчит там, где обязана измерить механизм. "
        + _FILLER * 2 + "\n\n"
        "## ⚡ класс урока второй\n"
        "класс: тело заметно больше оформления списка — иначе проверка «список, а не "
        "поток тел» красится не по предмету, а по масштабу подставных данных. "
        + _FILLER * 2 + "\n"
    ),
    "plan": (
        "## план приёмки: следующий шаг\n"
        "следующий шаг — разобрать оба раздела подставной роли и свериться с суммой "
        "знаков; очередь — по порядку, без спешки. " + _FILLER * 2 + "\n\n"
        "## позиция на час посева\n"
        "сейчас: раздел только что посеян, в работе — разбор на записи, сделано — "
        "тело записано штатным save-phoenix.py. " + _FILLER * 2 + "\n\n"
        "## инвариант сборки\n"
        "инвариант: сборка записей обратно обязана сойтись с телом знак в знак, "
        "иначе не переучиваться на ложном 🔁. " + _FILLER * 2 + "\n\n"
        "## указатель на происхождение\n"
        "смотри: это данные приёмки bite-memory-records.py, не живая память роли — "
        "живое берите запросом к базе, не этим текстом. " + _FILLER * 2 + "\n"
    ),
}

passed: list[str] = []
failed: list[str] = []


def record_case(name: str, ok: bool, detail: str = "") -> None:
    (passed if ok else failed).append(name)
    print(f"  {'✅' if ok else '🔴'} {name}" + (f"\n       {detail}" if detail and not ok else ""))


def call_tool(tool: pathlib.Path, *args: str, db: pathlib.Path = None):
    # ⚠️ db=None, А НЕ db=DB: значение параметра по умолчанию вычисляется ОДИН РАЗ,
    # при определении функции, — а приёмка на пустом контуре переназначает глобальный
    # DB уже ВНУТРИ main() (см. ensure_subject). Если бы умолчание держало старое
    # значение DB, случаи, зовущие call_tool без явного db=, тихо продолжили бы
    # спрашивать живую базу даже после переключения на подставную копию.
    if db is None:
        db = DB
    env = dict(os.environ, MEZO_ROLE=ROLE, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(tool), "--role", ROLE,
                        "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ensure_subject(base_db: pathlib.Path) -> tuple[pathlib.Path, str, bool]:
    """(база, роль, была_ли_заведена_подставная) — на которых приёмка измеряет.

    У роли PROTO в этой базе уже есть разобранные записи (живой контур) → работаем
    НА НЕЙ САМОЙ, ничего не меняя: прежнее поведение сохраняется знак в знак. Иначе
    (пустой/свежесобранный контур) заводим подставную роль SEED_ROLE на КОПИИ базы —
    своим ходом, штатными инструментами."""
    probe = sqlite3.connect(f"file:{base_db}?mode=ro", uri=True)
    has_records = probe.execute(
        "SELECT 1 FROM phoenix_records WHERE role=? LIMIT 1", (ROLE,)).fetchone()
    probe.close()
    if has_records:
        return base_db, ROLE, False

    seed_dir = pathlib.Path(tempfile.mkdtemp(prefix="bite-memory-records-seed-"))
    seeded_db = seed_dir / "mezosync.db"
    mezo_stand.snapshot_db(base_db, seeded_db)
    save_tool = mezo_paths.live_scripts(__file__) / "save-phoenix.py"
    if not save_tool.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: инструмента save-phoenix.py нет: {save_tool}")
    for section, body in SEED_FIXTURES.items():
        body_file = seed_dir / f"{section}.md"
        body_file.write_text(body, encoding="utf-8")
        # ⚡ save-phoenix.py САМА пересобирает phoenix_records ТЕМ ЖЕ ходом (хук
        # rebuild_records — карточка #525 часть А): первое сохранение раздела без
        # предыдущих записей вызывает её же parse(), отдельный --разобрать не нужен
        # и после хука только мешает («уже N записей» — находка первого же прогона
        # на pcK).
        save_env = dict(os.environ, PYTHONIOENCODING="utf-8")
        r = subprocess.run([sys.executable, str(save_tool), "--db", str(seeded_db),
                            "--role", SEED_ROLE, "--section", section,
                            "--file", str(body_file), "--actor", SEED_ROLE],
                           capture_output=True, text=True, encoding="utf-8", env=save_env)
        if r.returncode != 0:
            sys.exit("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: заведение подставного раздела "
                     f"{section} (save-phoenix.py) отказало кодом {r.returncode}:\n"
                     f"{r.stdout}{r.stderr}")
    return seeded_db, SEED_ROLE, True


def random_chunks(bodies: dict, records: dict, count: int = 10):
    """Вернуть [(раздел, начало, кусок, найден_целиком, найден_в_склейке)]."""
    rnd = random.Random(SEED)
    sections = sorted(bodies)
    result = []
    for _ in range(count):
        sect = rnd.choice(sections)
        body = bodies[sect]
        start = rnd.randrange(0, max(1, len(body) - 90))
        chunk = body[start:start + 80]
        whole = any(chunk in rec for rec in records.get(sect, []))
        # ⚖️ КУСОК, ЛЁГШИЙ НА СТЫК ДВУХ ЗАПИСЕЙ, — НЕ ПОТЕРЯ. Он есть целиком, просто
        # разрезан границей. Проверка, не умеющая этого различить, краснеет на здоровом
        # переносе — а ложная тревога дороже пропуска: перестают верить проверке ЦЕЛИКОМ.
        joined = "".join(records.get(sect, []))
        result.append((sect, start, chunk, whole, chunk in joined))
    return result


def main() -> int:
    global DB, ROLE
    if not TOOL.is_file():
        sys.exit(f"⛔ инструмента нет рядом: {TOOL}")

    DB, ROLE, seeded = ensure_subject(DB)

    print("=" * 88)
    print("ПРИЁМКА memory-records.py — карточка #524")
    print(f"инструмент: {TOOL}")
    print(f"база:       {DB}")
    if seeded:
        print(f"ℹ️ у роли PROTO в базе нет разобранных записей (пустой/свежий контур,"
              f" карточка #667) — приёмка завела подставную роль {ROLE} НА КОПИИ:"
              f" тело разделов записано save-phoenix.py, он же ТЕМ ЖЕ ходом (хук"
              f" пересборки) разобрал его на записи")
    print("=" * 88)

    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    bodies = dict(conn.execute(
        "SELECT section, body FROM phoenix WHERE role=?", (ROLE,)))
    records: dict[str, list[str]] = {}
    for sect, body in conn.execute(
            "SELECT section, body FROM phoenix_records WHERE role=? ORDER BY ord",
            (ROLE,)):
        records.setdefault(sect, []).append(body)
    if not records:
        sys.exit(f"⛔ у {ROLE} нет записей — приёмке нечего судить. Сначала --разобрать")

    print("\n── ЖИВЫЕ СЛУЧАИ ───────────────────────────────────────────────────────")

    # ① сборка по каждому разделу
    bad_sections = []
    for sect in sorted(bodies):
        code, output = call_tool(TOOL, "--section", sect, "--собрать")
        if code != 0 or "СОВПАДАЕТ ЗНАК В ЗНАК" not in output:
            bad_sections.append(sect)
    record_case(f"① сборка сходится знак в знак по всем разделам ({len(bodies)})",
           not bad_sections, f"не сошлись: {', '.join(bad_sections)}")

    # ② суммы
    body_total = sum(len(v) for v in bodies.values())
    records_total = sum(len(x) for v in records.values() for x in v)
    record_case(f"② сумма знаков совпадает ({records_total} = {body_total})", body_total == records_total,
           f"расхождение {records_total - body_total}")

    # ③ жребий со стыками
    draws = random_chunks(bodies, records)
    lost = [(sect, start) for sect, start, _, whole, joined in draws if not whole and not joined]
    at_seam = sum(1 for *_, whole, joined in draws if not whole and joined)
    record_case(f"③ жребий: 10 из 10 на месте (целиком {10 - at_seam - len(lost)} · "
           f"на стыке записей {at_seam} · потеряно {len(lost)})",
           not lost, f"потеряны: {lost}")

    # ④ три состояния поля «условие снятия»
    code, output = call_tool(TOOL, "--показать")
    m = re.search(r"условие снятия: назначено (\d+) · решено «условия нет» (\d+) · "
                  r"⚠️ НЕ РЕШЕНО (\d+)", output)
    record_case("④ поле «условие снятия» различает ТРИ состояния числом", bool(m),
           "строки с тремя числами в выводе --показать нет")
    if m:
        print(f"       назначено {m.group(1)} · «условия нет» {m.group(2)} · "
              f"НЕ решено {m.group(3)}")

    # ⑤ снятое читается вместе с «чем снята»
    code, output = call_tool(TOOL, "--снятые")
    revoked_count = conn.execute("SELECT COUNT(*) FROM phoenix_records "
                          "WHERE role=? AND alive='revoked'", (ROLE,)).fetchone()[0]
    record_case(f"⑤ отбор снятых показывает «чем снята» (снятых {revoked_count})",
           revoked_count == 0 or "чем снята каждая" in output,
           "снятые есть, а причины в выводе нет — снятое без причины "
           "неотличимо от потерянного")

    # ⑥ отбор отвечает списком, а не телами
    code, output = call_tool(TOOL, "--отобрать", "право")
    body_len = sum(len(x) for v in records.values() for x in v)
    record_case("⑥ отбор отвечает СПИСКОМ, а не потоком тел",
           len(output) < body_len // 3 and "начало" in output,
           f"вывод {len(output)} знаков — это тела, а критерий ② требует список")

    print("\n── ВСТРЕЧНЫЕ: ЧТО ОБЯЗАНО ОТКАЗАТЬ ────────────────────────────────────")

    # ⑦ чужая запись
    foreign = conn.execute("SELECT id, role FROM phoenix_records WHERE role<>? LIMIT 1",
                         (ROLE,)).fetchone()
    if foreign:
        code, output = call_tool(TOOL, "--поля", str(foreign[0]), "--источник", "порча")
        record_case(f"⑦ правка ЧУЖОЙ записи #{foreign[0]} (роль {foreign[1]}) отказывает",
               code != 0 and "НЕ ДОПИСАНО" in output, output.strip()[:200])
    else:
        # ⚖️ Случай не пропускается молча: сказать «проверить нечем» честнее, чем
        # промолчать — молчание неотличимо от пройденной проверки.
        print("  ⚪ ⑦ чужих записей в базе нет — случай проверен на копии ниже")

    # ⑧ несуществующая запись
    code, output = call_tool(TOOL, "--поля", "999999", "--источник", "порча")
    record_case("⑧ правка НЕСУЩЕСТВУЮЩЕЙ записи краснеет, а не молчит зелёным",
           code != 0 and "НЕ ДОПИСАНО" in output, output.strip()[:200])

    # ⑨ повторный разбор
    section = sorted(records)[0]
    code, output = call_tool(TOOL, "--section", section, "--разобрать")
    record_case(f"⑨ повторный разбор «{section}» отказывает (не затирает ручные поля)",
           code != 0 and "НЕ РАЗОБРАНО" in output, output.strip()[:200])

    # ⑨-бис (карточка #600, найдено контуром AIA, подтверждено в нашем коде): --пересобрать
    # ЗДЕСЬ НЕ СЧИТАЛСЯ пишущей операцией и обходил проверку «роль правит СВОЮ память
    # сама» — чужая роль могла пересобрать разбор чужого раздела молча. Отказ ничего
    # не мутирует (как ⑦⑧⑨ выше), поэтому случай безопасен на ЖИВОЙ базе.
    foreign_role = "STUD" if ROLE != "STUD" else "CORE"
    foreign_env = dict(os.environ, MEZO_ROLE=foreign_role, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(TOOL), "--role", ROLE,
                        "--db", str(DB), "--section", section, "--пересобрать"],
                       capture_output=True, text=True, encoding="utf-8", env=foreign_env)
    code, output = p.returncode, (p.stdout or "") + (p.stderr or "")
    record_case(f"⑨-бис карточка #600: --пересобрать ЧУЖОЙ ролью ({foreign_role} правит "
           f"{ROLE}) отказывает",
           code != 0 and "ОТКАЗ" in output and foreign_role in output, output.strip()[:200])

    conn.close()

    print("\n── ПОРЧА НА КОПИИ: ИНСТРУМЕНТ ОБЯЗАН ПОКРАСНЕТЬ ───────────────────────")
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = pathlib.Path(tmp)
        db_copy = sandbox / "mezosync.db"
        mezo_stand.snapshot_db(DB, db_copy)
        # инструмент и его сосед-резак кладутся РЯДОМ: инструмент импортирует резак
        # от своего расположения, значит в песочнице он возьмёт песочный.
        for filename in ("memory-records.py", "memory-archive.py", "mezo_paths.py"):
            if (HERE / filename).is_file():
                shutil.copy2(HERE / filename, sandbox / filename)
        tool_copy = sandbox / "memory-records.py"

        c = sqlite3.connect(db_copy)
        # ⑩ ломаем ОДНУ запись: сборка обязана перестать сходиться
        corrupted_id = c.execute(
            "SELECT id FROM phoenix_records WHERE role=? AND section=? "
            "ORDER BY ord LIMIT 1", (ROLE, section)).fetchone()[0]
        c.execute("UPDATE phoenix_records SET body=body||'ПОРЧА' WHERE id=?",
                  (corrupted_id,))
        c.commit()
        code, output = call_tool(tool_copy, "--section", section, "--собрать", db=db_copy)
        record_case("⑩ ПОРЧА сборки: расхождение поймано и показано первым различием",
               code != 0 and "РАСХОЖДЕНИЕ" in output and "первое различие" in output,
               "порча прошла как ✅ — сборка не сверяет содержимое")

        # ⑪ теперь наоборот: УДАЛЯЕМ запись — потеря обязана вылезти числом
        c.execute("UPDATE phoenix_records SET body=replace(body,'ПОРЧА','') WHERE id=?",
                  (corrupted_id,))
        c.execute("DELETE FROM phoenix_records WHERE id=?", (corrupted_id,))
        c.commit()
        code, output = call_tool(tool_copy, "--section", section, "--собрать", db=db_copy)
        record_case("⑪ ПОРЧА потерей: удалённая запись ломает сборку",
               code != 0 and "РАСХОЖДЕНИЕ" in output,
               "запись пропала, а сборка сказала ✅")

        # ⑫ ЗАДАЧА #532 (находка @TAXO): правка тела ВЫШЕ по тексту не должна сдвигать
        #    адреса неизменённых записей. Прежде все номера уезжали на единицу, и
        #    обращение по прежнему номеру МОЛЧА попадало в соседнюю запись.
        # ⚖️ Судим ДВА исхода раздельно: ПОДМЕНА (за номером другая запись — беда) и
        #    ОТСУТСТВИЕ (номера нет вовсе — законно, вызов откажет поимённо).
        #    Слить их в один ответ значило бы повторить ровно ту беду, что чиним.
        # ⚠️ Соединение блока порчи ⑩⑪ закрываем ЯВНО: перезаписать переменную мало —
        # незакрытый файл базы не даёт снести песочницу, и приёмка падает уже ПОСЛЕ
        # того, как все случаи сошлись. Зелёный итог при ненулевом коде выхода — худший
        # вид отчёта: и «прошло», и «упало» одновременно.
        c.close()
        c = sqlite3.connect(db_copy)
        # раздел с НАИБОЛЬШИМ числом записей: там резка складывает соседей, и случай
        # получается настоящий, а не вырожденный (на разделе из двух записей сдвигать нечего)
        section = c.execute(
            "SELECT section FROM phoenix_records WHERE role=? "
            "GROUP BY section ORDER BY COUNT(*) DESC LIMIT 1", (ROLE,)).fetchone()[0]
        before = dict(c.execute("SELECT id, body FROM phoenix_records "
                            "WHERE role=? AND section=?", (ROLE, section)).fetchall())
        body = c.execute("SELECT body FROM phoenix WHERE role=? AND section=?",
                         (ROLE, section)).fetchone()[0]
        # ⚖️ Порча ДВОЙНАЯ и нарочно: вставка в начало (сдвигает порядок) плюс правка
        # ОДНОГО куска в середине (его запись обязана исчезнуть). Без второй половины
        # встречный случай ⑬ не поставить — а без него ⑫ доказывает только полдела.
        midpoint = len(body) // 2
        corrupted_body = ("## БЛОК, ВСТАВЛЕННЫЙ ПРИЁМКОЙ В НАЧАЛО\nстрока\n\n"
                    + body[:midpoint] + "ПРАВКА-ПРИЁМКИ" + body[midpoint:])
        c.execute("UPDATE phoenix SET body=? WHERE role=? AND section=?",
                  (corrupted_body, ROLE, section))
        c.commit()
        c.close()
        code, output = call_tool(tool_copy, "--section", section, "--пересобрать", db=db_copy)
        c = sqlite3.connect(db_copy)
        after = dict(c.execute("SELECT id, body FROM phoenix_records "
                               "WHERE role=? AND section=?", (ROLE, section)).fetchall())
        replaced = [i for i, old_body in before.items() if i in after and after[i] != old_body]
        vanished = [i for i in before if i not in after]
        record_case(f"⑫ правка ВЫШЕ по тексту: тихой подмены НЕТ "
               f"(номеров {len(before)} · сохранили себя {len(before) - len(replaced) - len(vanished)}"
               f" · исчезли законно {len(vanished)})",
               not replaced,
               f"за номерами {replaced[:5]} теперь ДРУГИЕ записи — вызов пройдёт с ✅")
        # ⑬ встречный к ⑫: исчезнувший номер обязан ОТКАЗАТЬ, а не молчать
        if vanished:
            code2, output2 = call_tool(tool_copy, "--поля", str(vanished[0]),
                               "--источник", "проба", db=db_copy)
            record_case("⑬ ВСТРЕЧНЫЙ: обращение по исчезнувшему номеру ОТКАЗЫВАЕТ поимённо",
                   code2 != 0 and "НЕ ДОПИСАНО" in output2, output2.strip()[:200])
        else:
            # ⛔ Не зелёное и не молчание: опыт не поставлен — значит ⑫ доказал полдела
            record_case("⑬ ВСТРЕЧНЫЙ: исчезнувших номеров не возникло — ОПЫТ НЕ ПОСТАВЛЕН",
                   False, "правка середины не изменила ни одной записи; без этого "
                          "случая не видно, отказывает ли обращение по исчезнувшему номеру")

        # ⑦-бис: чужая запись на копии — заводим её нарочно, если в живой базе таких нет
        c.execute("INSERT INTO phoenix_records (role, section, subject, body, "
                  "body_chars, alive, ord, created_by) "
                  "VALUES ('COORD','state','право','чужое тело',10,'active',1,'COORD')")
        c.commit()
        foreign_id = c.execute("SELECT id FROM phoenix_records WHERE role='COORD'"
                             ).fetchone()[0]
        code, output = call_tool(tool_copy, "--поля", str(foreign_id), "--источник", "порча",
                         db=db_copy)
        touched = c.execute("SELECT source FROM phoenix_records WHERE id=?",
                            (foreign_id,)).fetchone()[0]
        record_case("⑦-бис чужая запись на копии: отказ И поле НЕ тронуто",
               code != 0 and "принадлежит роли COORD" in output and touched is None,
               f"код {code} · поле source={touched!r}")
        c.close()

        # ── ПРЕДМЕТ ЗАПИСИ — карточка #534 (замеры @TAXO и @CHROME) ──
        # Судится сама подсказка, без базы: вход — тело блока, выход — (предмет, спор).
        import importlib.util as _ilu
        def _load_module(path):
            sp = _ilu.spec_from_file_location("mr_под_судом", str(path))
            m = _ilu.module_from_spec(sp); sp.loader.exec_module(m); return m
        mr = _load_module(TOOL)
        chrome_case = ("## 🪤 УРОКИ — ОНИ ДОРОЖЕ СДЕЛАННОГО" + chr(10)
                + "1. ⚰️ прежний порядок отозван, правило снято." + chr(10)
                + "2. ⚰️ второе тоже снято 30.08.")
        taxo_case = ("## 🎯 МОИ КЛАССЫ — ЖИВЫЕ, ОПЛАЧЕННЫЕ СОБОЙ" + chr(10)
                 + "🩸 первый поймал сам; 🩸 второй поймал на приёмке; ошибся дважды.")
        single_case = "замер сделан: померил числом, 📏 три раза."
        # ⚖️ заголовок нарочно НЕМОЙ — иначе судится ветка «заголовок называет два»
        disputed_case = "## Заметка" + chr(10) + "право ⛔ на отправку есть; замер померил дважды."
        two_case = "## ⚡ УРОК, ИЗ КОТОРОГО ВЫРОС ПЛАН" + chr(10) + "план: следующий шаг один. урок оплачен."

        subj, dispute = mr.subject_and_dispute(chrome_case)
        record_case("⑭ случай @CHROME поимённо: «🪤 УРОКИ…» с тремя словами отзыва в теле → «урок», без спора",
               subj == "урок" and dispute is None, f"получено {subj!r}, спор {dispute!r}")
        subj, dispute = mr.subject_and_dispute(taxo_case)
        record_case("⑮ случай @TAXO поимённо: «🎯 МОИ КЛАССЫ…» с двумя 🩸 в теле → «урок», не «ошибка»",
               subj == "урок" and dispute is None, f"получено {subj!r}, спор {dispute!r}")
        subj, dispute = mr.subject_and_dispute(single_case)
        record_case("⑯ ВСТРЕЧНЫЙ: одна примета, заголовок молчит → предмет как прежде, спора НЕТ",
               subj == "замер" and dispute is None, f"получено {subj!r}, спор {dispute!r}")
        subj, dispute = mr.subject_and_dispute(disputed_case)
        record_case("⑰ спор помечен: заголовок молчит, тело 2:2 → спор назван с соперником и счётом",
               dispute is not None and "замер" in dispute and "2:2" in dispute, f"получено {subj!r}, спор {dispute!r}")
        subj, dispute = mr.subject_and_dispute(two_case)
        record_case("⑱ заголовок называет ДВА предмета → спор между ними, решает тело",
               subj in ("план", "урок") and dispute is not None and "заголовок называет" in dispute,
               f"получено {subj!r}, спор {dispute!r}")

        # ⑲ ПОРЧА правила «заголовок решает» на КОПИИ инструмента → случай @CHROME обязан вернуться
        original = TOOL.read_text(encoding="utf-8")
        corrupted = original.replace("    if len(in_head) == 1:", "    if False:")
        if corrupted == original:
            record_case("⑲ ПОРЧА правила заголовка: образец не найден — ОПЫТ НЕ ПОСТАВЛЕН", False,
                   "порча не легла; прогон бессмыслен, а не зелён")
        else:
            patched_copy = pathlib.Path(tempfile.mkdtemp()) / "memory-records.py"
            patched_copy.write_text(corrupted, encoding="utf-8")
            # инструмент подгружает соседа (резак блоков) ИЗ СВОЕГО каталога — без него копия
            # не поднимется, и порча упадёт ДО суда: поймано первым прогоном 20:29 UTC
            shutil.copy(TOOL.parent / "memory-archive.py", patched_copy.parent)
            subj2, _ = _load_module(patched_copy).subject_and_dispute(chrome_case)
            record_case("⑲ ПОРЧА правила заголовка → «🪤 УРОКИ…» снова становится «надгробие»",
                   subj2 == "надгробие",
                   f"порченый инструмент дал {subj2!r} ⇒ ⑭ проходил не по правилу заголовка")

    print("\n" + "=" * 88)
    print(f"ИТОГ: прошло {len(passed)} · пало {len(failed)}")
    if failed:
        for item in failed:
            print(f"   🔴 {item}")
    else:
        print("   ✅ все случаи сошлись, и порча краснеет — значит проверка способна")
        print("      отличить рабочий инструмент от сломанного, а не только сказать ✅")
    print("=" * 88)
    print("⚖️ ЧЕГО ЭТА ПРИЁМКА НЕ ПРОВЕРЯЕТ, названо прямо: ВЕРНОСТЬ предмета и часа")
    print("   в общем случае. Это смысл, а не форма. Случаи ⑭–⑲ судят ПРАВИЛО подсказки")
    print("   (заголовок решает · спор помечен), а не её попадание на чужой памяти: замер")
    print("   04.09 20:28 UTC — на 233 живых записях предмет сменился у 31, споров помечено")
    print("   84; по чтению заголовков у @TAXO промахов было 4 из 14, осталось 1 (#257:")
    print("   «очередью ввода» ушло в «план»). Остаток — не ноль, и он назван числом.")
    print("   Судит здесь рука роли — ключом --поля.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
