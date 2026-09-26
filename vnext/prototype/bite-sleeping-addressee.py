# -*- coding: utf-8 -*-
r"""ПРИЁМКА предупреждения о СПЯЩЕМ АДРЕСАТЕ в живом писателе — карточка #330.

🩸 ЧЕМ ОПЛАЧЕНО (27.08 16:34 UTC, записка #4000). @CORE отправил договор четырём ролям
и написал «молчание ответом не считаю, через сутки спрошу ещё раз». Замер 16:36 UTC:
двое из четырёх адресатов не подавали признаков жизни 21 час. Сутки ожидания ушли бы
на роли, которых никто не запускал, — и спрашивать «ещё раз» было бы некого и завтра.
Знать этого он не мог: писатель не обращался к отметкам прочтения ВООБЩЕ.
Класс наш собственный — «молчащий отказ читается как успех», только про доставку:
записка ушла, отчёт зелёный, адресата нет.

⚖️ ПОЧЕМУ ПРЕДУПРЕЖДЕНИЕ, А НЕ ОТКАЗ: записка спящему обязана лечь в ленту — он прочтёт
её, когда проснётся, и это работает сегодня. Правило владельца прямое: предупреждать,
а не запрещать.
⛔ А вот ЗАКРЫТАЯ роль (апоптоз) — отказ ДО записи: её никто не прочтёт никогда, и записка
ей есть ровно то же, что опечатка в имени, за которую отказ уже стои́т.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① спящий адресат НАЗВАН поимённо и с числом часов                    РАЗЛИЧАЮЩИЙ
  ② ВСТРЕЧНЫЙ к ①: читающий адресат в предупреждении НЕ появляется     РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ ПО ПРИЗНАКУ: роль читает, но давно не писала — НЕ спящая РАЗЛИЧАЮЩИЙ
  ④ ВСТРЕЧНЫЙ ПО ПРИЗНАКУ: роль пишет, но давно не подтверждала — тоже РАЗЛИЧАЮЩИЙ
  ⑤ отправка НЕ отказывает и НЕ задерживается: записка в ленте, код 0  РАЗЛИЧАЮЩИЙ
  ⑥ адресат в копии (cc) судится так же, как прямой                    РАЗЛИЧАЮЩИЙ
  ⑦ ЗАКРЫТАЯ роль адресатом → ОТКАЗ ДО записи, записки НЕТ             РАЗЛИЧАЮЩИЙ
  ⑧ ВСТРЕЧНЫЙ к ⑦: живая роль отказа не вызывает                       КОНТРОЛЬ
  ⑨ ОБРАТНЫЙ ХОД: признак ослаблен до «только отметка прочтения» —
    случай ③ обязан ПОКРАСНЕТЬ у ослабленной копии                     РАЗЛИЧАЮЩИЙ
  ⑩ ОБРАТНЫЙ ХОД: признак ослаблен до «только своя нота» —
    случай ④ обязан ПОКРАСНЕТЬ у ослабленной копии                     РАЗЛИЧАЮЩИЙ

⛔ Живой базы не касается: всё на копии. Состояние ролей ПОСЕЯНО, а не взято как есть —
иначе случай проверял бы не признак, а погоду в контуре на час прогона.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths   # noqa: E402
import mezo_stand   # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
WRITER_TOOL = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "write-message.py"
LIVE_DB = mezo_paths.live_db()

# 🩸 РОЛИ ПОСЕВА (класс ошибок (107)/(127), приёмка для пакета). Раньше здесь стояли
# НАСТОЯЩИЕ имена живого контура (TAXO/STUD/CHROME/RCC/EYE) — писатель сверяет адресата
# со словарём (таблица roles), и выдуманное имя дало бы отказ ДО того, как признак вообще
# успеет сработать. На свежей выгрузке пакета в реестре ТОЛЬКО COORD, и все пять настоящих
# имён были бы отказом одинаково — приёмка красилась бы ДО единого случая. Приёмка теперь
# заводит СВОИ подставные роли САМА, на своей копии (см. seed() ниже — INSERT в таблицу
# roles), явными BITE-именами, которые ни с одной настоящей ролью не спутать. Смысл каждой
# роли — тот же, что был:
SLEEPER = "BITESLEEPER"   # ни своих нот, ни подтверждений — предупреждение обязано назвать
ACTIVE = "BITEACTIVE"     # и пишет, и подтверждает — обязан молчать
READS = "BITEREADER"      # подтверждает, но давно не писала: работает, значит НЕ спящая
WRITES = "BITEWRITER"     # пишет, но давно не подтверждала: тоже работает
CLOSED = "BITECLOSED"     # подставной апоптоз: записка ей не будет прочитана никогда

# 🪤 МЕТКА ПРОГОНА. Первая редакция считала свои записки по строке «случай ①» — и нашла
# ЧЕТЫРЕ вместо одной: копия живой базы полна чужих записок, где коллеги нумеруют разделы
# теми же кружками. Случай ⑦ («записки-призрака нет») от этого краснел на исправном отказе.
# ⇒ Своё узнаём по метке, которой в чужих текстах быть не может, а не по словам предмета.
MARKER = f"[приёмка330-{os.getpid()}]"

CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def run(script, *args):
    """PYTHONPATH на каталог инструментов: ослабленная копия писателя живёт во временном
    каталоге и без этого умерла бы на импорте. 🪤 Обратный ход уже был однажды ПУСТЫМ
    ровно так: копия падала на импорте, ненулевой код читался как работа признака.

    🩹 ДОГОН (класс ошибок (107)/(127), приёмка для пакета): MEZO_CONTAINER ВЫЗЫВАЮЩЕГО
    (самой приёмки) здесь ГЛУШИТСЯ, а не наследуется молча. Рецепт прогона приёмки на
    свежей выгрузке пакета зовёт ЕЁ САМУ с MEZO_CONTAINER=<пакет> — без глушения подопытный
    писатель унаследовал бы эту переменную и мог бы решить, что его контейнер — сам пакет,
    а не временная копия-песочница в --db (тот же класс и та же починка, что в
    bite-signal-templates.py; довод — mezo_stand.stand_env(): «направление закрепляет
    ЗАПУСКАЮЩИЙ, а не mezo_paths»)."""
    env = dict(os.environ)
    env.pop("MEZO_CONTAINER", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [p for p in (str(pathlib.Path(script).parent), str(WRITER_TOOL.parent),
                     env.get("PYTHONPATH", "")) if p])
    r = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def seed(db):
    """Выставить в КОПИИ пять состояний, которые различает признак — и САМИ роли-заготовки.

    ⚠️ Сеем ОБА признака сразу — и последнюю свою ноту, и отметку прочтения. Посеяв
    один, мы бы проверяли не «И», а то, какой из двух случайно оказался решающим.

    🩹 ДОГОН (класс ошибок (107)/(127), приёмка для пакета): роли BITE* — ПОДСТАВНЫЕ,
    их нет в реестре свежей выгрузки пакета (там только COORD), а на живом контуре они
    заведомо не значатся настоящими именами. Заводим строки в `roles` ЗДЕСЬ ЖЕ, тем же
    посевом, — иначе писатель отказал бы адресату ДО того, как признак вообще успел бы
    сработать. По той же причине здесь INSERT в read_cursors/messages, а не UPDATE:
    у подставных ролей никакой предшествующей строки нет вовсе, и UPDATE молча правил бы
    ноль строк.
    """
    con = sqlite3.connect(db)
    old_ts = "2026-08-01 00:00:00"
    for role, lifecycle in ((SLEEPER, "alive"), (ACTIVE, "alive"), (READS, "alive"),
                            (WRITES, "alive"), (CLOSED, "closed")):
        con.execute("INSERT INTO roles (role, lifecycle) VALUES (?, ?) "
                    "ON CONFLICT(role) DO UPDATE SET lifecycle = excluded.lifecycle",
                    (role, lifecycle))
    # своя СТАРАЯ нота у СПЯЩЕГО и ЧИТАЮЩЕГО — у подставных ролей истории нет вовсе,
    # значит заводим её сами (раньше это делал UPDATE поверх настоящей истории TAXO/CHROME)
    for role in (SLEEPER, READS):
        con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority)"
                    " VALUES (?, ?, ?, '[]', 'normal')",
                    (role, old_ts, f"посев приёмки #330: старая нота роли {role}"))
    for role, read_at in ((SLEEPER, old_ts), (ACTIVE, "now"), (READS, "now"), (WRITES, old_ts)):
        when_expr = "datetime('now')" if read_at == "now" else "?"
        values = (role,) if read_at == "now" else (role, read_at)
        con.execute(
            f"INSERT INTO read_cursors (reader_role, updated_at) VALUES (?, {when_expr}) "
            f"ON CONFLICT(reader_role) DO UPDATE SET updated_at = excluded.updated_at",
            values)
    # У «пишущего» и «живого» своя нота обязана быть СВЕЖЕЙ, иначе они уедут в спящие
    boundary_id = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    for role in (ACTIVE, WRITES):
        con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority)"
                    " VALUES (?, datetime('now'), ?, '[]', 'normal')",
                    (role, f"посев приёмки #330: свежая нота роли {role}"))
    con.commit()
    con.close()
    return boundary_id


def sleeping_section(output: str) -> str:
    """Часть вывода МЕЖДУ заголовком «АДРЕСАТ НЕ ПОДАВАЛ ПРИЗНАКОВ ЖИЗНИ» и следующим
    разделом/«OK #».

    🩹 ДОГОН (план «убрать будильники», 24.09, записка #5312): «АДРЕСАТ НЕДОСТИЖИМ
    СИГНАЛОМ» тоже печатает имя роли — по СВОЕЙ причине (нет номера сессии), не по
    спящей. Проверка «имени в выводе нет» без сужения ловит ЧУЖОЙ раздел: живой
    адресат без сессии красил бы случаи ②③④ по признаку, который они не проверяют.
    """
    tail = output.split("АДРЕСАТ НЕ ПОДАВАЛ ПРИЗНАКОВ ЖИЗНИ", 1)
    if len(tail) < 2:
        return ""
    return tail[1].split("АДРЕСАТ НЕДОСТИЖИМ СИГНАЛОМ")[0].split("OK #")[0].replace("--to", "")


def send(db, body, to, cc=None):
    note_path = pathlib.Path(db).parent / "nota.md"
    note_path.write_text(body + chr(10) + MARKER + chr(10), encoding="utf-8")
    args = ["--role", "PROTO", "--db", str(db), "--file", str(note_path), "--to", to]
    if cc:
        args += ["--cc", cc]
    return run(WRITER_TOOL, *args)


def weaken(root, which: str) -> pathlib.Path:
    """Копия писателя, у которой признак судит ТОЛЬКО ОДНО из двух условий.

    Ломаем ровно ту ветку, которую стережёт встречный случай: «только отметка прочтения»
    обязана уронить ③, «только своя нота» — ④. Ослабление, ломающее оба, доказывало бы
    лишь то, что признак вообще работает.
    """
    text = WRITER_TOOL.read_text(encoding="utf-8")
    original = "MAX(COALESCE(c.updated_at,''), COALESCE(m.последняя,''))"
    replacement = {"курсор": "COALESCE(c.updated_at,'')",
                   "нота": "COALESCE(m.последняя,'')"}[which]
    if original not in text:
        raise SystemExit("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: в писателе нет места, которое ослабляют."
                         " Молчать нельзя — вышло бы зелёное на непроверенном коде.")
    weak_copy = root / f"weak-{which}.py"
    weak_copy.write_text(text.replace(original, replacement), encoding="utf-8")
    return weak_copy


def main() -> int:
    ok = True
    root = mezo_stand.new("bite-sleep-")
    db = root / "sand.db"
    mezo_stand.snapshot_db(LIVE_DB, db)
    seed(db)

    # ① спящий назван поимённо
    code, output = send(db, "# приёмка #330: случай ①\n\nтело\n", SLEEPER)
    ok &= case("① спящий адресат НАЗВАН поимённо",
               SLEEPER in output and "не подава" in output,
               f"код {code}; молчание тут и есть предмет карточки", differ=True)

    # ② ВСТРЕЧНЫЙ: читающий адресат не назван. Без него ① зеленел бы от предупреждения ВСЕГДА
    code2, output2 = send(db, "# приёмка #330: случай ②\n\nтело\n", ACTIVE)
    ok &= case("② ВСТРЕЧНЫЙ: живой адресат в предупреждении НЕ появляется",
               ACTIVE not in sleeping_section(output2),
               "проверка, кричащая на исправном, учит не слышать крик", differ=True)

    # ③ читает, но давно не писала — работает, значит НЕ спящая
    code3, output3 = send(db, "# приёмка #330: случай ③\n\nтело\n", READS)
    ok &= case("③ ВСТРЕЧНЫЙ ПО ПРИЗНАКУ: роль читает, но давно не писала — НЕ названа",
               READS not in sleeping_section(output3),
               "судить по одной своей ноте — оболгать всякого, кто в этот час только читает",
               differ=True)

    # ④ пишет, но давно не подтверждала — тоже работает
    code4, output4 = send(db, "# приёмка #330: случай ④\n\nтело\n", WRITES)
    ok &= case("④ ВСТРЕЧНЫЙ ПО ПРИЗНАКУ: роль пишет, но давно не подтверждала — НЕ названа",
               WRITES not in sleeping_section(output4),
               "отметка прочтения двигается только подтверждением: читающий её мог не поставить",
               differ=True)

    # ⑤ отправка не отказывает — записка обязана лечь в ленту
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    landed = con.execute("SELECT COUNT(*) FROM messages WHERE body_md LIKE ? AND body_md LIKE '%случай ①%'",
                        (f"%{MARKER}%",)).fetchone()[0]
    con.close()
    ok &= case("⑤ отправка НЕ отказала: записка спящему легла в ленту, код 0",
               code == 0 and landed == 1,
               "он прочтёт её, когда проснётся; отказ отнял бы работающее сегодня", differ=True)

    # ⑥ адресат в копии судится так же, как прямой
    code6, output6 = send(db, "# приёмка #330: случай ⑥\n\nтело\n", ACTIVE, cc=SLEEPER)
    ok &= case("⑥ спящий в КОПИИ назван так же, как прямой адресат",
               SLEEPER in output6 and "не подава" in output6,
               "молчание про копию читалось бы как «там все на месте»", differ=True)

    # ⑦ закрытая роль — отказ ДО записи
    code7, output7 = send(db, "# приёмка #330: случай ⑦\n\nтело\n", CLOSED)
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    ghost = con.execute("SELECT COUNT(*) FROM messages WHERE body_md LIKE ? AND body_md LIKE '%случай ⑦%'",
                          (f"%{MARKER}%",)).fetchone()[0]
    con.close()
    ok &= case("⑦ ЗАКРЫТАЯ роль адресатом — ОТКАЗ ДО записи, записки НЕТ",
               code7 != 0 and ghost == 0 and CLOSED in output7,
               "её не прочтёт никто и никогда: это опечатка, а не молчание", differ=True)

    # ⑧ ВСТРЕЧНЫЙ к ⑦: живая роль отказа не вызывает
    ok &= case("⑧ ВСТРЕЧНЫЙ: живая роль адресатом — отказа нет",
               code2 == 0,
               "без этого ⑦ зеленел бы у писателя, который отвергает всех подряд")

    # ⑨⑩ ОБРАТНЫЙ ХОД — ослабляем ровно ту ветку, которую стережёт встречный
    for which, case_label, role, output_prev in (("нота", "③", READS, output3),
                                       ("курсор", "④", WRITES, output4)):
        weak_tool = weaken(root, which)
        code_x, output_x = run(weak_tool, "--role", "PROTO", "--db", str(db),
                              "--body", f"обратный ход {which}", "--to", role)
        named = role in sleeping_section(output_x)
        ok &= case(f"{'⑨' if which == 'нота' else '⑩'} ОБРАТНЫЙ ХОД «только {which}»:"
                   f" случай {case_label} у ослабленной копии КРАСНЕЕТ",
                   named and code_x == 0,
                   f"ослабленный признак обязан назвать {role}; если он молчит и тут — "
                   f"случай {case_label} зеленел не от признака, а сам по себе", differ=True)

    print()
    print(f"{'✅ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
