#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: свои записки роли после записи памяти возвращаются к ней при пробуждении —
все, а не одна последняя (машинный слой памяти, machine_layer.py; карточка #466 ③,
заказ PROTO — записка #5189 ②, разбор OPSSRE — записка #5188).

📏 ПОВОД — ЗАМЕР 14.09 10:33 UTC: у COORD после записи раздела state 40 своих записок, а строка
«последняя своя записка» называла одну. Тридцать девять к роли при пробуждении не возвращались.

Случаи (различающий = прежняя редакция или нарочная поломка отвечает иначе):
  ① своих записок после отметки нет — новой строки нет, «ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА» на месте  (контроль)
  ② три записки после отметки — заголовок и три строки по порядку, «ОНА НОВЕЕ…» на месте   РАЗЛИЧАЮЩИЙ
  ③ тринадцать — ровно десять строк и «и ещё 3»; команда исполнена как напечатана, дала 13 РАЗЛИЧАЮЩИЙ
     (одна из тринадцати — в архиве: иначе проходила бы команда «из messages»; команду «без отбора
     по роли» ловят чужая #300, раньше своих по номеру, и обрезка пределом, а чужая #350 отдельной
     поломки не держит — находка PROTO 03.10; своя #299 РОВНО в час отметки: без неё не проверялось
     условие по часу в команде — вторая приёмка PROTO 03.10; state подтверждён в час отметки, а plan
     записан позже: без этого не проверялось, ОТКУДА команда берёт час, — третья приёмка PROTO 03.10)
  ③б то же, но state БЕЗ отметки «правок нет», identity старше, plan свежее — команда от    РАЗЛИЧАЮЩИЙ
     saved_at state (с отметкой у state подмены «confirmed_at без COALESCE», «MAX(confirmed_at)» и
     «MIN(COALESCE)» дают тот же час, что верный модуль, — четвёртая приёмка PROTO 03.10)
  ④ отметка «правок нет» после записок — записки до неё не показаны                        РАЗЛИЧАЮЩИЙ
  ⑤ записка, унесённая в архив по возрасту, — показана                                     РАЗЛИЧАЮЩИЙ
  ⑥ чужие записки не показаны                                                              (контроль)
  ⑦ другой раздел свежее state — отсчёт всё равно от state (случай COORD 14.09)            РАЗЛИЧАЮЩИЙ
  ⑧ последняя своя записка в архиве, старая в ленте — строка «ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА»
     называет архивную и предупреждает (находка PROTO 03.10, карточка #466)                  РАЗЛИЧАЮЩИЙ

Схема песочницы — из ЖИВОЙ базы: определения только затронутых таблиц и вида messages_all,
без данных; живая открыта только на чтение. Своя схема разошлась бы с живой молча, а вид
messages_all и есть предмет случая ⑤.
⛔ Живую базу не пишет. Команду без --db песочницы (случай ③) НЕ исполняет: она ушла бы в живую.

⚖️ НЕ ЛОВИТ (известно; печатается и в выводе): команда без --limit (предел db-q.py по умолчанию 200,
своих записок здесь 14) · ORDER BY timestamp в команде (у своих записок номер и час растут вместе) ·
строка «ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА» меряет «ОНА НОВЕЕ…» самым новым разделом, а блок ниже — отметкой
state (вне этой приёмки; находка PROTO 03.10, комментарий карточки #466 16:37 UTC).
"""
import importlib.util
import re
import shlex
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — где живая база (только за схемой)
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = Path(mezo_target.scripts_root())
ROLE = "PROTO"
# таблицы раньше вида: вид ссылается на них
SCHEMA_OBJECTS = ("messages", "messages_history", "messages_archive", "phoenix", "read_cursors",
                  "rules", "backlog", "backlog_events", "messages_all")
HEADER = "после записи памяти"
MARK = "2026-09-14 08:00:00"


def load_module():
    path = SCRIPTS / "machine_layer.py"
    if not path.exists():
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {path} не найден — приёмке нечего испытывать.")
    spec = importlib.util.spec_from_file_location("machine_layer_tested", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def live_schema():
    # от расположения mezo_paths, а не приёмки: копию приёмки гоняют и из рабочего каталога роли
    live = mezo_paths.container_root() / ".mezosync" / "mezosync.db"
    con = sqlite3.connect(f"file:{live.as_posix()}?mode=ro", uri=True)
    try:
        marks = ",".join("?" * len(SCHEMA_OBJECTS))
        got = dict(con.execute(f"SELECT name, sql FROM sqlite_master WHERE name IN ({marks})",
                               SCHEMA_OBJECTS).fetchall())
    finally:
        con.close()
    missing = [n for n in SCHEMA_OBJECTS if n not in got]
    if missing:
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в базе {live} нет {missing} — схему взять неоткуда.")
    return live, [got[n] for n in SCHEMA_OBJECTS]


def build(ddl, own=(), foreign=(), archived=(), sections=(("state", MARK, None),)):
    stand = mezo_stand.new("bite-own-notes-")
    path = stand / "mezosync.db"
    con = sqlite3.connect(path)
    for sql in ddl:
        con.execute(sql)
    for note_id, stamp, body in own:
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md) VALUES (?,?,?,?)",
                    (note_id, ROLE, stamp, body))
    for note_id, who, stamp, body in foreign:
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md) VALUES (?,?,?,?)",
                    (note_id, who, stamp, body))
    for note_id, stamp, body in archived:
        con.execute("INSERT INTO messages_archive (id, writer_role, timestamp, body_md, moved_by, rule) "
                    "VALUES (?,?,?,?, 'messages-fold.py', 'приёмка')", (note_id, ROLE, stamp, body))
    con.execute("INSERT INTO read_cursors (reader_role, last_read_id) VALUES (?, 0)", (ROLE,))
    for section, saved, confirmed in sections:
        con.execute("INSERT INTO phoenix (role, section, body, saved_at, confirmed_at) VALUES (?,?,?,?,?)",
                    (ROLE, section, "тело раздела", saved, confirmed))
    con.commit()
    con.close()
    return stand, path


def listed(text):
    """Номера записок в строках под заголовком — в порядке показа."""
    out, inside = [], False
    for ln in text.splitlines():
        if HEADER in ln:
            inside = True
            continue
        if inside and ln.startswith("     #"):
            out.append(int(ln.split()[0][1:]))
        elif inside:
            inside = ln.startswith("     ")
    return out


CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def main() -> int:
    m = load_module()
    live, ddl = live_schema()
    ok = True

    # ① после отметки своих записок нет (есть только до неё) — новой строки быть не должно
    _, db = build(ddl, own=[(101, "2026-09-14 07:00:00", "# старая первая"),
                            (102, "2026-09-14 07:30:00", "# старая вторая")],
                  foreign=[(103, "COORD", "2026-09-14 09:00:00", "# чужая после отметки")])
    text = "\n".join(m.machine_block(db, ROLE))
    ok &= case("① своих записок после отметки нет — новой строки нет, прежняя строка на месте (контроль)",
               HEADER not in text and "ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА: #102" in text,
               f"заголовок {'ЕСТЬ' if HEADER in text else 'нет'} · прежняя строка "
               f"{'на месте' if 'ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА: #102' in text else 'ПРОПАЛА'}")

    # ② три записки после отметки — все три, по порядку, прежнее предупреждение не тронуто
    _, db = build(ddl, own=[(201, "2026-09-14 07:00:00", "# до отметки"),
                            (202, "2026-09-14 08:10:00", "# первая после\nтело"),
                            (204, "2026-09-14 08:20:00", "## вторая после"),
                            (206, "2026-09-14 08:30:00", "третья после")],
                  foreign=[(203, "CORE", "2026-09-14 08:15:00", "# чужая")])
    text = "\n".join(m.machine_block(db, ROLE))
    got = listed(text)
    ok &= case("② три записки после отметки — заголовок и три строки по порядку, «ОНА НОВЕЕ…» на месте",
               "твоих записок 3" in text and got == [202, 204, 206]
               and "ОНА НОВЕЕ СОХРАНЁННОЙ ПАМЯТИ" in text and "первая после" in text
               and "вторая после" in text,
               f"показаны {got} · ждали [202, 204, 206] и первые строки записок без «#»", differ=True)

    # ③ тринадцать — десять строк, остаток назван, команда исполнима как напечатана.
    # 🩸 Находка PROTO 03.10 (карточка #466): на тринадцати своих в ленте и без чужих команда
    # «из messages» и команда «без отбора по роли» давали тот же ответ — случай их не различал.
    # Поэтому одна своя — в архиве; «без отбора по роли» ловят чужая #300 (раньше своих по номеру)
    # и обрезка пределом («ЕСТЬ ЕЩЁ»), каждая сама по себе; чужая #350 (позже своих) отдельной
    # поломки не держит.
    # 🩸 Вторая приёмка PROTO 03.10: все тринадцать своих стояли ПОСЛЕ отметки, отсекать было нечего —
    # команда без условия по часу проходила 8/8. Своя #299 РОВНО в час отметки ловит три поломки:
    # условия нет · «>=» вместо «>» · отсечка по дате вместо часа. Своя ДО отметки (07:50 того же дня)
    # поймала бы «условия нет» и «отсечку по дате», но не «>=» — поэтому ровно в час отметки.
    # 🩸 Третья приёмка PROTO 03.10 (комментарий карточки #466 16:37 UTC): раздел был один — state без
    # отметки «правок нет», и отметка блока, час самого нового раздела и saved_at без confirmed_at
    # совпадали: три подмены источника часа в команде проходили 8/8. Теперь state записан в 07:00 и
    # подтверждён в час отметки, plan записан позже, в 09:00 — команда обязана брать час от отметки
    # блока. «Час самого нового раздела» и «MAX по разделам» дают 09:00 — недостающие #301…#305;
    # «saved_at без confirmed_at» даёт 07:00 — лишняя #299 и обрезка пределом. Одного раздела plan
    # мало: saved_at без confirmed_at он не ловит.
    # ⚖️ Не ловятся (известно): команда без --limit (предел db-q.py по умолчанию 200) и ORDER BY timestamp
    # (у своих записок здесь номер и час растут вместе).
    def check_thirteen(title, sections):
        own13 = [(300 + k, f"2026-09-14 {8 + k // 6:02d}:{(k % 6) * 10:02d}:30", f"# записка {k}")
                 for k in range(1, 14)]
        in_archive = own13[1]                                   # #302 — унесена переносом
        at_mark = (299, MARK, "# своя, ровно в час отметки — не после неё")
        stand, db = build(ddl, own=[at_mark] + [n for n in own13 if n is not in_archive], archived=[in_archive],
                          foreign=[(300, "COORD", "2026-09-14 08:05:00", "# чужая, раньше своих по номеру"),
                                   (350, "CORE", "2026-09-14 10:05:00", "# чужая, позже своих по номеру")],
                          sections=sections)
        text = "\n".join(m.machine_block(db, ROLE))
        got = listed(text)
        cmd_line = next((ln.strip() for ln in text.splitlines() if "db-q.py" in ln), "")
        args = shlex.split(cmd_line) if cmd_line else []
        has_db = "--db" in args and Path(args[args.index("--db") + 1]).resolve() == db.resolve()
        ran, detail = False, "команды нет"
        if cmd_line and not has_db:
            detail = f"команда БЕЗ --db песочницы — не исполняю (ушла бы в живую базу): {cmd_line[:120]}"
        elif cmd_line:
            r = subprocess.run([sys.executable, *args[1:]], capture_output=True, text=True, encoding="utf-8",
                               env=mezo_stand.stand_env(stand, PYTHONIOENCODING="utf-8"), timeout=60)
            ids = [int(ln.split("\t")[0]) for ln in r.stdout.splitlines() if ln.split("\t")[0].isdigit()]
            want = [n for n, _, _ in own13]
            cut = "ЕСТЬ ЕЩЁ" in (r.stderr or "")
            ran = r.returncode == 0 and ids == want and not cut
            extra = sorted(set(ids) - set(want))
            missing = sorted(set(want) - set(ids))
            in_order = ids == sorted(ids)
            detail = (f"код {r.returncode} · команда дала {len(ids)} записок, ждали 13 по порядку · "
                      f"лишние {extra or 'нет'} · недостающие {missing or 'нет'} · "
                      f"обрезано пределом: {'ДА' if cut else 'нет'} · порядок: {'верен' if in_order else 'НАРУШЕН'}")
        in_block = re.search(r"твоих записок (\d+)", text)
        rest = re.search(r"и ещё (\d+)", text)
        return case(title,
                    "твоих записок 13" in text and got == list(range(304, 314)) and "и ещё 3" in text
                    and has_db and ran,
                    f"в блоке: твоих записок {in_block.group(1) if in_block else 'НЕТ строки'} · "
                    f"«и ещё {rest.group(1) if rest else '—'}» · "
                    f"показаны {len(got)}: {got[:1]}…{got[-1:]} · {detail}", differ=True)

    ok &= check_thirteen("③ тринадцать — ровно десять строк и «и ещё 3»; команда исполнена как напечатана и дала 13",
                         (("state", "2026-09-14 07:00:00", MARK), ("plan", "2026-09-14 09:00:00", None)))
    # 🩸 Четвёртая приёмка PROTO 03.10 (комментарий карточки #466 21:05 UTC): с отметкой у state подмены
    # «confirmed_at без COALESCE», «MAX(confirmed_at)» и «MIN(COALESCE)» дают тот же час, что верный модуль, —
    # данные ③ закрыли одну дыру и открыли две, которые прежняя приёмка ловила. ③б — роль без отметки «правок
    # нет»: confirmed_at пуст, identity старше, plan свежее; команда обязана взять saved_at state.
    ok &= check_thirteen("③б то же, но state без отметки «правок нет», identity старше, plan свежее — команда от saved_at state",
                         (("identity", "2026-09-14 07:00:00", None), ("state", MARK, None),
                          ("plan", "2026-09-14 09:00:00", None)))

    # ④ отметка «правок нет» после двух записок — показана только третья
    _, db = build(ddl, own=[(401, "2026-09-14 08:10:00", "# до взгляда 1"),
                            (402, "2026-09-14 08:20:00", "# до взгляда 2"),
                            (403, "2026-09-14 08:30:00", "# после взгляда")],
                  sections=(("state", MARK, "2026-09-14 08:25:00"),))
    text = "\n".join(m.machine_block(db, ROLE))
    got = listed(text)
    ok &= case("④ отметка «правок нет» после записок — записки до неё не показаны",
               "твоих записок 1" in text and got == [403],
               f"показаны {got} · ждали [403]: взгляд 08:25 отсекает 08:10 и 08:20", differ=True)

    # ⑤ записка, унесённая в архив по возрасту (messages-fold.py), своей быть не перестаёт
    _, db = build(ddl, own=[(502, "2026-09-13 09:00:00", "# в ленте")],
                  archived=[(501, "2026-09-02 09:00:00", "# унесена в архив")],
                  sections=(("state", "2026-09-01 08:00:00", None),))
    text = "\n".join(m.machine_block(db, ROLE))
    got = listed(text)
    ok &= case("⑤ записка, унесённая в архив по возрасту, — показана",
               "твоих записок 2" in text and got == [501, 502],
               f"показаны {got} · ждали [501, 502]: #501 лежит в messages_archive", differ=True)

    # ⑥ чужие записки после отметки — не показаны
    _, db = build(ddl, own=[(602, "2026-09-14 08:20:00", "# своя")],
                  foreign=[(601, "COORD", "2026-09-14 08:10:00", "# чужая COORD"),
                           (603, "CORE", "2026-09-14 08:30:00", "# чужая CORE @PROTO")])
    text = "\n".join(m.machine_block(db, ROLE))
    got = listed(text)
    ok &= case("⑥ чужие записки не показаны (контроль)",
               601 not in got and 603 not in got and "чужая" not in text,
               f"показаны {got} · чужих #601 #603 среди них быть не должно")

    # ⑦ случай COORD 14.09: мелкий раздел записан позже state — отсчёт всё равно от state
    _, db = build(ddl, own=[(701, "2026-09-14 08:10:00", "# 1"), (702, "2026-09-14 08:20:00", "# 2"),
                            (703, "2026-09-14 08:30:00", "# 3"), (704, "2026-09-14 08:40:00", "# 4")],
                  sections=(("identity", "2026-09-14 07:00:00", None), ("state", MARK, None),
                            ("plan", "2026-09-14 09:00:00", None)))
    text = "\n".join(m.machine_block(db, ROLE))
    got = listed(text)
    ok &= case("⑦ другой раздел свежее state — отсчёт всё равно от state (случай COORD)",
               "твоих записок 4" in text and f"(state, {MARK[:16]} UTC)" in text and got == [701, 702, 703, 704],
               f"показаны {got} · раздел plan записан в 09:00, после state — все четыре", differ=True)

    # ⑧ живой случай CHROME после переноса в архив (находка PROTO 03.10, карточка #466): самая
    # новая своя записка унесена, а старая осталась в ленте («жив разговор», срочное). Строка
    # «ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА» обязана назвать архивную и предупредить — как и часть ниже.
    # Заготовка случая — PROTO (её приёмка 03.10, комментарий карточки #466 11:20 UTC).
    _, db = build(ddl, own=[(801, "2026-09-05 06:24:00", "# старая, оставлена в ленте")],
                  archived=[(802, "2026-09-24 10:54:16", "# последняя, унесена в архив")],
                  sections=(("state", "2026-09-24 10:54:00", None),))
    text = "\n".join(m.machine_block(db, ROLE))
    line = next((ln for ln in text.splitlines() if "ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА" in ln), "строки нет")
    ok &= case("⑧ последняя своя записка в архиве, старая в ленте — строка называет архивную и предупреждает",
               "ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА: #802" in text and "ОНА НОВЕЕ СОХРАНЁННОЙ ПАМЯТИ" in text
               and listed(text) == [802],
               f"строка: «{line.strip()[:70]}» · ждали #802 с предупреждением; ниже показаны {listed(text)}",
               differ=True)

    print()
    print("   ⚖️ не ловит (известно): команда без --limit · ORDER BY timestamp в команде · «ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА»")
    print("      меряет «ОНА НОВЕЕ…» самым новым разделом, а блок — отметкой state (вне этой приёмки)")
    print(f"   схема песочницы — из {live.as_posix()} (только определения, без данных)")
    print(f"{'✅ СВОИ ЗАПИСКИ ПОСЛЕ ПАМЯТИ ВОЗВРАЩАЮТСЯ' if ok else '🔴 СВОИ ЗАПИСКИ ПОСЛЕ ПАМЯТИ НЕ ВОЗВРАЩАЮТСЯ'}"
          f" — случаев {CASES}, различающих {DIFFER}, испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
