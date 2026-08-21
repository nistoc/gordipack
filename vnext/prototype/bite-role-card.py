#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-role-card — приёмка карточки роли: она ПОРОЖДАЕТСЯ базой, а не пишется рукой.

ЗАЧЕМ. Карточка #234: правило ввело понятие карточки роли и не ввело места, где она живёт.
Выбран вариант ③ — истина в базе, файл собирается ею же. Такой выбор ценен ровно настолько,
насколько доказано, что файл ДЕЙСТВИТЕЛЬНО порождается: вторая копия, которую никто не
сверяет, отличается от первой копии только словами о намерениях.

ЧТО ПРОВЕРЯЕТСЯ, И ПОЧЕМУ ИМЕННО ЭТО:
  ① собранная карточка содержит зону и права — иначе соседу она бесполезна;
  ② правка файла РУКОЙ ловится сверкой (это и есть смысл варианта ③);
  ③ встречный к ②: нетронутый файл сверку НЕ красит — иначе ② зеленел бы всегда;
  ④ роли нет в базе — ОТКАЗ собрать, а не пустая карточка;
  ⑤ снятое право в карточку НЕ идёт: отменённое разрешение, прочитанное соседом как
     действующее, — худший род неправды в этой записи;
  ⑥ карточки нет на месте — сверка КРАСНЕЕТ, а не молчит (отсутствие ≠ совпадение).

    python <КОНТУР>/vnext-tools/bite-role-card.py
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

TOOL = Path(__file__).resolve().parent / "role-card.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def build_db(path: Path, with_spent_right: bool = False) -> None:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('group_name','atlas')")
    con.execute("CREATE TABLE roles (role TEXT PRIMARY KEY, lifecycle TEXT, lifecycle_at TEXT,"
                " lifecycle_by TEXT, lifecycle_reason TEXT, zone TEXT, seen_in TEXT)")
    con.execute("INSERT INTO roles VALUES ('PROBE','alive','2026-08-01','owner','',"
                "'испытательная зона','чат')")
    con.execute("CREATE TABLE role_skill (id INTEGER PRIMARY KEY, role TEXT, skill TEXT,"
                " evidence TEXT, measured_at TEXT, until_cond TEXT, written_by TEXT,"
                " UNIQUE (role, skill))")
    con.execute("CREATE TABLE role_rights (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT,"
                " right_key TEXT, scope TEXT, kind TEXT, authorized_by TEXT, granted_at TEXT,"
                " source_ref TEXT, spent_at TEXT, revoked_at TEXT, revoked_why TEXT,"
                " declared_by TEXT, note TEXT)")
    con.execute("INSERT INTO role_rights (role, right_key, scope, kind, authorized_by,"
                " granted_at, source_ref, note) VALUES"
                " ('PROBE','живое-право','весь контур','standing','owner',"
                "'2026-08-01 10:00 UTC','чат','границы названы')")
    if with_spent_right:
        con.execute("INSERT INTO role_rights (role, right_key, scope, kind, authorized_by,"
                    " granted_at, source_ref, spent_at) VALUES"
                    " ('PROBE','ПОТРАЧЕННОЕ-ПРАВО','раз','once','owner',"
                    "'2026-08-02 10:00 UTC','чат','2026-08-03 10:00 UTC')")
        con.execute("INSERT INTO role_rights (role, right_key, scope, kind, authorized_by,"
                    " granted_at, source_ref, revoked_at) VALUES"
                    " ('PROBE','СНЯТОЕ-ПРАВО','весь','standing','owner',"
                    "'2026-08-02 10:00 UTC','чат','2026-08-04 10:00 UTC')")
    con.commit()
    con.close()


def run(db: Path, bridges: Path, *args):
    r = subprocess.run([sys.executable, str(TOOL), "--role", "PROBE", "--db", str(db),
                        "--bridges", str(bridges), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    if not TOOL.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: испытуемого нет — {TOOL}")
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="bite-card-"))
    try:
        db = tmp / "c.db"
        build_db(db)
        bridges = tmp / "bridges"
        (bridges / "atlas-сосед").mkdir(parents=True)

        # ① СОБРАННАЯ КАРТОЧКА НЕСЁТ ГЛАВНОЕ
        code, out = run(db, bridges)
        ok &= case("① карточка собрана из базы и несёт зону и живое право",
                   code == 0 and "испытательная зона" in out and "живое-право" in out,
                   "без зоны и прав карточка бесполезна тому, ради кого заведена — соседу",
                   differ=True)

        # ② ПРАВКА РУКОЙ ЛОВИТСЯ — СМЫСЛ ВАРИАНТА ③
        run(db, bridges, "--write")
        файл = bridges / "atlas-сосед" / "card.probe.md"
        файл.write_text(файл.read_text(encoding="utf-8") + "\nдописано рукой\n",
                        encoding="utf-8")
        code2, out2 = run(db, bridges, "--check")
        ok &= case("② правка файла РУКОЙ ловится сверкой, и отказ называет ТРИ причины",
                   code2 == 1 and "РАСХОДИТСЯ" in out2 and "СБОРЩИК" in out2,
                   "если правку рукой не видно, вариант «истина в базе» — только слова; "
                   "а отказ с ДВУМЯ причинами посылал искать чужую правку, которой не было: "
                   "после смены ПОКАЗА красное увидели все, кто разложил карточку (@CHROME)",
                   differ=True)

        # ③ ВСТРЕЧНЫЙ к ②
        run(db, bridges, "--write")
        code3, out3 = run(db, bridges, "--check")
        ok &= case("③ нетронутый файл сверку НЕ красит (встречный к ②)",
                   code3 == 0 and "совпадает" in out3,
                   "без этого случая ② зеленел бы всегда — и краснота ничего не значила бы",
                   differ=True)

        # ④ РОЛИ НЕТ — ОТКАЗ, А НЕ ПУСТАЯ КАРТОЧКА
        r4 = subprocess.run([sys.executable, str(TOOL), "--role", "НЕТТАКОЙ", "--db", str(db),
                             "--bridges", str(bridges)],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        out4 = (r4.stdout or "") + (r4.stderr or "")
        ok &= case("④ роли нет в базе — ОТКАЗ собрать карточку",
                   r4.returncode == 1 and "НЕ ЗАПУСТИЛАСЬ" in out4,
                   "пустая карточка несуществующей роли пригласила бы соседа писать в пустоту",
                   differ=True)

        # ⑤ СНЯТОЕ И ПОТРАЧЕННОЕ ПРАВО В КАРТОЧКУ НЕ ИДЁТ
        db2 = tmp / "d.db"
        build_db(db2, with_spent_right=True)
        code5, out5 = run(db2, bridges)
        ok &= case("⑤ снятое и потраченное право в карточку НЕ попадает",
                   code5 == 0 and "живое-право" in out5
                   and "СНЯТОЕ-ПРАВО" not in out5 and "ПОТРАЧЕННОЕ-ПРАВО" not in out5,
                   "отменённое разрешение, прочитанное соседом как действующее, — худший род "
                   "неправды здесь: он попросит того, что роли уже нельзя", differ=True)

        # ⑥ ФАЙЛА НЕТ — КРАСНОЕ, А НЕ МОЛЧАНИЕ
        файл.unlink()
        code6, out6 = run(db, bridges, "--check")
        ok &= case("⑥ карточки нет на месте — сверка КРАСНЕЕТ, а не молчит",
                   code6 == 1 and "карточки нет" in out6,
                   "отсутствие файла неотличимо от совпадения, если о нём молчать", differ=True)

        # ⑦ ЧУЖАЯ ПЕРЕПИСКА НЕ ЗАСОРЯЕТСЯ. Рядом с обменом контуров лежат обмены отдельных
        #    ролей с чужими продуктами: карточка роли контура там никому не адресована.
        чужая = bridges / "aia-stud-exchange"
        чужая.mkdir()
        code7, out7 = run(db, bridges, "--write")
        ok &= case("⑦ папка чужой переписки пропускается, и это СКАЗАНО",
                   code7 == 0 and not (чужая / "card.probe.md").exists()
                   and "пропущено папок" in out7,
                   "молчаливый пропуск читался бы как «других папок не было»; отбор идёт по "
                   "имени нашей группы ИЗ БАЗЫ, а не по виду каталога", differ=True)

        # ⑨ УМЕНИЯ ПОКАЗЫВАЮТСЯ ВМЕСТЕ С ТЕМ, ЧЕМ ПОДТВЕРЖДЕНЫ (заявка #3698).
        #    Умение без доказательства и часа замера — утверждение роли о себе, которое
        #    стареет молча: умевшая в июле могла потерять доступ в августе, и обе записи
        #    честны. Соседу нужна не строка «умею», а то, чем она держится.
        db_sk = tmp / "sk.db"
        build_db(db_sk)
        con = sqlite3.connect(str(db_sk))
        con.execute("INSERT INTO role_skill (role, skill, evidence, measured_at, until_cond,"
                    " written_by) VALUES ('PROBE','читать графы','записка #1','2026-08-01',"
                    "'если доступ отзовут','PROBE')")
        con.commit()
        con.close()
        code9, out9 = run(db_sk, bridges)
        ok &= case("⑨ умение показано ВМЕСТЕ с доказательством, часом и условием устаревания",
                   code9 == 0 and "читать графы" in out9 and "записка #1" in out9
                   and "2026-08-01" in out9 and "если доступ отзовут" in out9,
                   "«умею» без того, чем это держится, сосед проверить не может, а время "
                   "старит запись молча", differ=True)

        # ⑨а ЧАС С ЗОНОЙ В БАЗЕ — ЗОНА НЕ УДВАИВАЕТСЯ. Нашла @CHROME на своих строках
        #     (записка #3712 ⑥): у ролей, пишущих час с зоной, выходило «UTC UTC».
        #     ⚖️ Решение было принято мной же на соседних строках — и не применено здесь.
        db_tz = tmp / "tz.db"
        build_db(db_tz)
        con = sqlite3.connect(str(db_tz))
        con.execute("INSERT INTO role_skill (role, skill, evidence, measured_at, until_cond,"
                    " written_by) VALUES ('PROBE','читать графы','записка #1',"
                    "'2026-08-01 09:00 UTC',NULL,'PROBE')")
        con.commit()
        con.close()
        code9a, out9a = run(db_tz, bridges)
        ok &= case("⑨а час, уже несущий зону, не получает вторую",
                   code9a == 0 and "UTC UTC" not in out9a and "2026-08-01 09:00 UTC" in out9a,
                   "у половины ролей час лежит с зоной, у половины без — печатать надо оба",
                   differ=True)

        # ⑨б ВСТРЕЧНЫЙ: час БЕЗ зоны зону получает. Без него ⑨а зеленел бы и на правке
        #     «просто перестать дописывать», а метка без зоны запрещена сводом правил.
        ok &= case("⑨б ВСТРЕЧНЫЙ: час без зоны её получает",
                   "2026-08-01 UTC" in out9,
                   "иначе метку нельзя отличить от местного времени — ровно та беда, "
                   "ради которой зона обязательна", differ=True)

        # ⑩ ДВА РАЗНЫХ «УМЕНИЙ НЕТ» — их нельзя склеивать (тот же класс, что «правила нет»)
        code10, out10 = run(db, bridges)          # место есть, записей нет
        ok &= case("⑩ место под умения ЕСТЬ, записей нет — сказано именно это",
                   code10 == 0 and "НЕ ВПИСАНЫ" in out10,
                   "молчание здесь читалось бы как «роль ничего не умеет»", differ=True)

        db_old = tmp / "old.db"
        build_db(db_old)
        con = sqlite3.connect(str(db_old))
        con.execute("DROP TABLE role_skill")      # сборка старше шага схемы
        con.commit()
        con.close()
        code11, out11 = run(db_old, bridges)
        ok &= case("⑪ ВСТРЕЧНЫЙ: места под умения НЕТ ВОВСЕ — это другой ответ",
                   code11 == 0 and "НЕТ МЕСТА" in out11 and "НЕ «умений нет»" in out11,
                   "контур, собранный до этого шага схемы, иначе выглядел бы ролью без "
                   "умений — та же склейка двух «нет», что мы чинили в перечне правил",
                   differ=True)

        # ⑧ ВСТРЕЧНЫЙ к ⑦: имя группы не записано — ОТКАЗ, а не «положу везде»
        db3 = tmp / "e.db"
        build_db(db3)
        con = sqlite3.connect(str(db3))
        con.execute("DELETE FROM meta WHERE key='group_name'")
        con.commit()
        con.close()
        code8, out8 = run(db3, bridges, "--write")
        ok &= case("⑧ имя группы не записано — ОТКАЗ (встречный к ⑦)",
                   code8 == 1 and "НЕ ЗАПУСТИЛАСЬ" in out8,
                   "без имени группы отличить обмен контуров от чужой переписки нечем; "
                   "разложить «на всякий случай везде» — тихо сделать не то", differ=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{'✅ КАРТОЧКА РОЛИ — ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — "
          f"случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
