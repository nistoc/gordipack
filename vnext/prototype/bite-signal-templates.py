# -*- coding: utf-8 -*-
r"""ПРИЁМКА печатника сигналов соседней роли — карточка #564 (реализация В1 карточки #548).

🩸 ЧЕМ ОПЛАЧЕНЫ СЛУЧАИ. Два дефекта поймал первый же прогон печатника 05.09, оба в САМОЙ
СРОЧНОЙ заготовке — той, по которой роль бросает свою работу и идёт разбираться:
```
① «ТЫ держишь карточку #561» ушло роли, которая её НЕ ДЕРЖИТ (держала другая).
   Рядом печаталось предупреждение — но адресат читает ТЕКСТ, а не вывод печатника
② «ТЫ держишь объявление о правке #145 (до 2026-09-04 17:40 UTC)» — сутками позже срока.
   Объявление гаснет САМО, поэтому непроставленная отметка снятия ≠ «держит»
```
⚡ КЛАСС ОБОИХ: сигнал уверенно утверждал неправду, и вся его сила — срочность — работала
на эту неправду. Молчание тут дешевле ошибки, потому и случаи ③④ — про ОТКАЗ печатать.

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① адрес есть, вид «записка» → 0, в тексте номер записки из ЖИВОЙ базы          РАЗЛИЧАЮЩИЙ
  ② имя отправителя не впечатано: тот же вызов от другой роли меняет «X →»       РАЗЛИЧАЮЩИЙ
  ③ адреса роли в реестре НЕТ → 2 и словами, чего не хватает (не пустота)        РАЗЛИЧАЮЩИЙ
  ④ «держишь» про карточку ЧУЖОГО держателя → 2, текст НЕ печатается             РАЗЛИЧАЮЩИЙ
  ⑤ адрес старше суток → 2, назван час записи и почему это важно                 РАЗЛИЧАЮЩИЙ
  ⑥ истёкшее объявление о правке в текст не входит                               РАЗЛИЧАЮЩИЙ
  ⑦ контроль: печатник ничего не отправляет — в коде нет средства отправки

ПОРЧА (--porcha впечатанное-имя): в заготовке «записка» подстановка отправителя заменяется
на впечатанное «PROTO». ОЖИДАНИЕ, НАЗВАННОЕ ДО ПРОГОНА: краснеет РОВНО случай ②, остальные
целы — ② единственный, кто спрашивает про отправителя.

⛔ Живой базы не касается: работает на КОПИИ, снятой в свой временный каталог.
"""
from __future__ import annotations

import argparse
import io
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import tokenize

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

CASES = DIFFER = ЗЕЛЁНЫХ = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, ЗЕЛЁНЫХ
    CASES += 1
    DIFFER += bool(differ)
    ЗЕЛЁНЫХ += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def зови(инструмент: pathlib.Path, db: pathlib.Path, *args):
    r = subprocess.run([sys.executable, "-B", str(инструмент), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["впечатанное-имя"])
    a = ap.parse_args()

    живой = pathlib.Path(__file__).resolve().parent / "signal-templates.py"
    шаг = mezo_paths.live_scripts(__file__) / "migrations" / "20260905-role-sessions.py"
    if not живой.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: печатника нет: {живой}")

    стенд = pathlib.Path(tempfile.mkdtemp(prefix="bite-signal-"))
    try:
        # копия базы (backup API — согласованный снимок, не копия файла на ходу)
        db = стенд / "copy.db"
        src = sqlite3.connect(str(mezo_paths.live_db(__file__)))
        dst = sqlite3.connect(str(db))
        src.backup(dst)
        dst.close()
        src.close()

        инструмент = стенд / "signal-templates.py"
        shutil.copy2(живой, инструмент)
        shutil.copy2(pathlib.Path(__file__).resolve().parent / "mezo_paths.py", стенд / "mezo_paths.py")
        if a.porcha == "впечатанное-имя":
            текст = инструмент.read_text(encoding="utf-8")
            до = текст
            текст = текст.replace(
                '"текст": ("{from} → {role}: в ленте записка #{last_note} к тебе. ',
                '"текст": ("PROTO → {role}: в ленте записка #{last_note} к тебе. ')
            assert текст != до, "порча не легла — строка заготовки изменилась, поправь приёмку"
            инструмент.write_text(текст, encoding="utf-8")
            print("🧪 ПОРЧА «впечатанное-имя»: ждём красным РОВНО ② (имя отправителя), "
                  "остальные целы\n")

        con = sqlite3.connect(str(db))
        if "role_sessions" not in {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            con.close()
            код, вывод = зови(шаг, db)
            if код != 0:
                sys.exit(f"⛔ шаг схемы на копии не прошёл:\n{вывод}")
            con = sqlite3.connect(str(db))

        # ── подготовка: две роли с адресами, одна со СТАРЫМ адресом
        con.execute("DELETE FROM role_sessions")
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source) "
                    "VALUES ('PROTO', 'atlas-dd [245891]', datetime('now'), 'PROTO', 'self')")
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source) "
                    "VALUES ('COORD', 'atlas-17 [08a16e]', datetime('now'), 'COORD', 'self')")
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source) "
                    "VALUES ('STUD', 'atlas-old [000000]', datetime('now','-30 hours'), 'STUD', 'self')")
        # свежая записка PROTO к COORD — чтобы номер в тексте брался из живой базы
        нота = con.execute("SELECT max(id) FROM messages WHERE writer_role='PROTO'").fetchone()[0]
        # карточка с ЧУЖИМ держателем: взятие от CHROME
        карточка = con.execute("SELECT max(id) FROM backlog").fetchone()[0]
        con.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type, body_md) "
                    "VALUES (?, datetime('now'), 'CHROME', 'claim', ?)",
                    (карточка, "до 2026-09-09 10:00:00 UTC · чужая рука"))
        # истёкшее объявление о правке у COORD
        con.execute("INSERT INTO tool_leases (role, tools, reason, taken_at, until_utc) "
                    "VALUES ('COORD', 'x.py', 'опыт приёмки', datetime('now','-3 hours'), "
                    "datetime('now','-2 hours'))")
        con.commit()
        con.close()
        con2 = sqlite3.connect(str(db))

        # ① сигнал о записке.
        # 🩸 ЗДЕСЬ БЫЛА ОШИБКА АВТОРА, НАЙДЕННАЯ ЧУЖОЙ РУКОЙ В ПЕРВЫЙ ЖЕ ЧАС: случай ждал
        # «последнюю записку отправителя ВООБЩЕ» (наибольший номер), а печатник по своей же
        # справке даёт последнюю записку К АДРЕСАТУ. У автора эти два совпадали — и случай
        # был зелен всегда; у первого чужого прогонщика разошлись, и он покраснел.
        # ⚡ КЛАСС: приёмка мерила случай СВОЕГО АВТОРА. Пока автор и есть прогонщик, она
        # зелена по построению — ровно то, зачем нужна чужая рука.
        нота_к = con2.execute(
            "SELECT m.id FROM messages m JOIN message_addressee a ON a.message_id = m.id "
            "WHERE m.writer_role = 'PROTO' AND upper(a.role) = 'COORD' "
            "ORDER BY m.id DESC LIMIT 1").fetchone()
        ждём = нота_к[0] if нота_к else нота
        код, вывод = зови(инструмент, db, "--role", "PROTO", "--to", "COORD", "--kind", "записка")
        есть_номер = f"#{ждём}" in вывод
        case("① сигнал о записке печатается, номер — последняя записка К АДРЕСАТУ из живой базы",
             код == 0 and есть_номер and "SendMessage(" in вывод,
             f"код {код} · номер #{ждём} (последняя к COORD) в тексте: "
             f"{'да' if есть_номер else 'НЕТ'}", differ=True)

        # ② имя отправителя не впечатано
        код2, вывод2 = зови(инструмент, db, "--role", "COORD", "--to", "PROTO", "--kind", "записка")
        от_coord = "COORD → PROTO:" in вывод2
        case("② имя отправителя подставляется, а не впечатано",
             код2 == 0 and от_coord,
             f"вызов от COORD даёт «COORD → PROTO»: {'да' if от_coord else 'НЕТ — имя впечатано'}",
             differ=True)

        # ③ адреса нет
        код3, вывод3 = зови(инструмент, db, "--role", "PROTO", "--to", "CORE", "--kind", "записка")
        case("③ адреса роли в реестре нет → отказ СЛОВАМИ, не пустота",
             код3 == 2 and "АДРЕСА РОЛИ CORE" in вывод3 and "--set-address" in вывод3,
             f"код {код3} · сказано, чего не хватает и что делать: "
             f"{'да' if '--set-address' in вывод3 else 'НЕТ'}", differ=True)

        # ④ «держишь» про чужую карточку
        код4, вывод4 = зови(инструмент, db, "--role", "PROTO", "--to", "COORD", "--kind", "держишь",
                            "--card", str(карточка))
        нет_текста = "SendMessage(" not in вывод4
        case("④ «держишь» про карточку ЧУЖОГО держателя → отказ, текст не печатается",
             код4 == 2 and нет_текста and "CHROME" in вывод4,
             f"код {код4} · вызов не напечатан: {'да' if нет_текста else 'НЕТ — ушла бы неправда'}",
             differ=True)

        # ⑤ старый адрес
        код5, вывод5 = зови(инструмент, db, "--role", "PROTO", "--to", "STUD", "--kind", "записка")
        case("⑤ адрес старше суток → отказ с часом записи и доводом",
             код5 == 2 and "СТАР" in вывод5 and "признака недоставки" in вывод5,
             f"код {код5} · назван час записи и почему это важно: "
             f"{'да' if 'признака недоставки' in вывод5 else 'НЕТ'}", differ=True)

        # ⑥ истёкшее объявление о правке в текст не входит
        код6, вывод6 = зови(инструмент, db, "--role", "PROTO", "--to", "COORD", "--kind", "держишь",
                            "--card", str(карточка))
        case("⑥ истёкшее объявление о правке не считается «держит»",
             "объявление о правке #" not in вывод6.split("👉")[0].replace("ни незакрытого объявления", ""),
             "вчерашнее объявление в текст сигнала не попало", differ=True)

        # ⑦ контроль: печатник не отправляет.
        # ⚡ Разбором ТОКЕНОВ, а не образцом по строке: первый вариант этого случая искал
        # «SendMessage(» регулярным выражением и покраснел на строке, которая его ПЕЧАТАЕТ.
        # Печать вызова и вызов выглядят одинаково ровно до того часа, когда код разобран.
        текст_кода = живой.read_text(encoding="utf-8")
        код_без_текстов = []
        with io.open(живой, "rb") as fh:
            for т in tokenize.tokenize(fh.readline):
                # 🪤 f-строка с версии 3.12 разбирается НА ЧАСТИ (FSTRING_START/MIDDLE/END),
                # и её текст выходит из-под фильтра «STRING». Первый вариант этого случая
                # честно отбрасывал STRING и всё равно видел печатаемую строку как код.
                if т.type not in (tokenize.STRING, tokenize.COMMENT,
                                  getattr(tokenize, "FSTRING_START", -1),
                                  getattr(tokenize, "FSTRING_MIDDLE", -1),
                                  getattr(tokenize, "FSTRING_END", -1)):
                    код_без_текстов.append(т.string)
        исполняемое = " ".join(код_без_текстов)
        зовёт_отправку = "SendMessage" in исполняемое
        печатает = "SendMessage(to=" in текст_кода
        case("⑦ контроль: печатник только ПЕЧАТАЕТ вызов, отправки в исполняемом коде нет",
             печатает and not зовёт_отправку,
             f"вызов есть в тексте для человека: {'да' if печатает else 'НЕТ'} · "
             f"в исполняемом коде: {'ЕСТЬ — отправка мимо руки роли' if зовёт_отправку else 'нет'}")

        # ⑧ адрес без различителя в скобках (находка COORD: одно имя носят ДВА разговора)
        код8, вывод8 = зови(инструмент, db, "--role", "CORE", "--set-address", "atlas-17")
        case("⑧ адрес без различителя в скобках не принимается",
             код8 == 2 and "РАЗЛИЧИТЕЛ" in вывод8,
             f"код {код8} · сказано, что имя указывает на несколько разговоров: "
             f"{"да" if "НЕСКОЛЬКО" in вывод8 else "НЕТ"}", differ=True)

        # ⑨ свежая записка отправителя, НЕ числящаяся адресату → сказано вслух
        con2.execute("INSERT INTO messages (writer_role, timestamp, body_md) "
                     "VALUES ('PROTO', datetime('now'), 'записка без адресатов полями')")
        con2.commit()
        свежая = con2.execute("SELECT max(id) FROM messages WHERE writer_role='PROTO'").fetchone()[0]
        код9, вывод9 = зови(инструмент, db, "--role", "PROTO", "--to", "COORD", "--kind", "записка")
        case("⑨ есть записка новее, но не числящаяся адресату → сказано вслух, не подставлено молча",
             код9 == 0 and f"#{свежая}" in вывод9 and "НОВЕЕ" in вывод9,
             f"код {код9} · про записку #{свежая} сказано: "
             f"{'да' if 'НОВЕЕ' in вывод9 else 'НЕТ — подставлена старая молча'}", differ=True)
        con2.close()

        print("")
        print(f"ИТОГ: {ЗЕЛЁНЫХ} из {CASES} · различающих {DIFFER}")
        return 0 if ЗЕЛЁНЫХ == CASES else 1
    finally:
        shutil.rmtree(стенд, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
