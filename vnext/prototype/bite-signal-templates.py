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
  ⑦ печатник ничего не отправляет — в исполняемом коде нет средства отправки     РАЗЛИЧАЮЩИЙ
  ⑧ адрес без различителя в скобках не принимается                              РАЗЛИЧАЮЩИЙ
  ⑨ записка новее, но не числящаяся адресату → сказано вслух                     РАЗЛИЧАЮЩИЙ

🌉 КАРТОЧКА #570 — УСЛОВИЕ РЕДАКЦИИ 2 ПРАВИЛА signal-not-carrier (слово владельца
2026-09-06 05:38 UTC): «ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ; ПОЯВИТСЯ ОБЩЕЕ МЕСТО —
ПОЕДЕТ ЗВОНОК.» Случаи идут ПАРАМИ, и это не оформление: без встречного ⑪ случай ⑩
зелен и у печатника, который называет условие ВСЕМ ПОДРЯД — в том числе там, где общая
лента есть и тело обязано ехать запиской.
  ⑩ адресат ЗА пределами контура → условие НАЗВАНО, печатается письмо              РАЗЛИЧАЮЩИЙ
  ⑪ ВСТРЕЧНЫЙ: адресат ВНУТРИ контура → условия НЕТ, прежний вывод цел             РАЗЛИЧАЮЩИЙ
  ⑫ ВСТРЕЧНЫЙ: тело в сообщении адресату ВНУТРИ контура → по-прежнему ОТКАЗ        РАЗЛИЧАЮЩИЙ
  ⑬ ВСТРЕЧНЫЙ к ⑫: то же тело ЗА пределы контура ВХОДИТ в письмо                   РАЗЛИЧАЮЩИЙ
  ⑭ второй источник признака: каталог обмена НА ДИСКЕ опознаёт соседа,
     о котором в базе связи нет                                                   РАЗЛИЧАЮЩИЙ

НАРОЧНЫЕ ПОЛОМКИ (--porcha …), ожидание каждой названо В КОДЕ ДО ПРОГОНА и печатается
перед случаями:
  впечатанное-имя ....... подстановка отправителя заменена впечатанным именем
  ослеплённая-связь ..... первый источник признака (запись связи с соседом в базе)
  ослеплённый-каталог ... второй источник признака (каталоги обмена на диске)
  условие-всем .......... обратная слепота: КАЖДЫЙ адресат считается соседним контуром

⛔ ЧЕГО ЭТА ПРИЁМКА НЕ ПОКРЫВАЕТ — названо прямо, чтобы молчание не читалось как «проверено»:
  · запись адреса на ИМЯ СОСЕДНЕГО КОНТУРА (--set-address --role TAPAS) не проверяется:
    печатник её примет и заведёт в перечне адресов строку на имя, которое ролью не является;
  · каталог обмена с именем НЕ по образцу «<наш контур>-<сосед>» встречным случаем не покрыт;
  · форма имени файла письма (ask · answer · status) взята из договора моста и против
    КАЖДОГО моста не сверяется — у мостов она может отличаться;
  · письмо соседу здесь только ПЕЧАТАЕТСЯ; ни один случай ничего не кладёт в каталоги
    обмена и ничего не отправляет — это внешнее действие, и приёмка его не делает.

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

CASES = DIFFER = GREENS = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, GREENS
    CASES += 1
    DIFFER += bool(differ)
    GREENS += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def call_tool(tool: pathlib.Path, db: pathlib.Path, *args, extra_env=None):
    """Позвать печатника. `среда` дополняет переменные окружения — ею случай ⑭ показывает
    печатнику ДРУГОЙ контейнер контура, чтобы проверить поиск каталогов обмена на диске."""
    full_env = None
    if extra_env:
        full_env = dict(os.environ)
        full_env.update(extra_env)
    r = subprocess.run([sys.executable, "-B", str(tool), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=full_env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["впечатанное-имя", "ослеплённая-связь",
                                        "ослеплённый-каталог", "условие-всем",
                                        "session-id-order"],
                    help="нарочная поломка: чем ослепить печатника перед прогоном")
    a = ap.parse_args()

    live_tool = pathlib.Path(__file__).resolve().parent / "signal-templates.py"
    schema_step = mezo_paths.live_scripts(__file__) / "migrations" / "20260905-role-sessions.py"
    if not live_tool.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: печатника нет: {live_tool}")

    sandbox = pathlib.Path(tempfile.mkdtemp(prefix="bite-signal-"))
    try:
        # копия базы (backup API — согласованный снимок, не копия файла на ходу)
        db = sandbox / "copy.db"
        src = sqlite3.connect(str(mezo_paths.live_db(__file__)))
        dst = sqlite3.connect(str(db))
        src.backup(dst)
        dst.close()
        src.close()

        tool = sandbox / "signal-templates.py"
        shutil.copy2(live_tool, tool)
        shutil.copy2(pathlib.Path(__file__).resolve().parent / "mezo_paths.py", sandbox / "mezo_paths.py")
        # 🧪 НАРОЧНЫЕ ПОЛОМКИ. Ожидание каждой стои́т ЗДЕСЬ, в коде, и печатается ДО
        # случаев — чтобы исход сверяли с названным заранее, а не подгоняли объяснение
        # под увиденное. Неподтвердившееся ожидание — находка, и записывается как было.
        BREAKS = {
            "впечатанное-имя": (
                '"текст": ("{from} → {role}: в ленте записка #{last_note} к тебе. ',
                '"текст": ("PROTO → {role}: в ленте записка #{last_note} к тебе. ',
                "ждём красным РОВНО ② (имя отправителя), остальные целы — ② единственный, "
                "кто спрашивает про отправителя"),
            "ослеплённая-связь": (
                '"WHERE lower(source_group) = ?"',
                '"WHERE 0 AND lower(source_group) = ?"',
                "ослеплён ПЕРВЫЙ источник признака — запись связи с соседом в базе. Ждём "
                "красным ⑩ и ⑬ (сосед по базе больше не опознаётся); ⑭ ЗЕЛЁНЫМ — он стои́т "
                "на втором источнике, каталоге обмена; остальные целы"),
            "ослеплённый-каталог": (
                '.glob("*/.mezosync/bridges/*")',
                '.glob("*/.mezosync/каталогов-обмена-нет/*")',
                "ослеплён ВТОРОЙ источник — поиск каталогов обмена на диске. Ждём красным "
                "РОВНО ⑭; ⑩ и ⑬ зелёными (их сосед записан в базе); остальные целы"),
            "условие-всем": (
                'neighbor = neighbor_groups(conn, our, db_path).get(to_role.lower())',
                'neighbor = neighbor_groups(conn, our, db_path).get(to_role.lower()) '
                'or {"откуда": [], "каталог": None}',
                "обратная слепота: КАЖДЫЙ адресат считается соседним контуром. Ждём красным "
                "①②③④⑤⑥⑨ ⑪ ⑫ ⑮ ⑯ — всё, что судит поведение ВНУТРИ контура, включая "
                "случаи session_id ⑮⑯ (роль своего контура попадёт под отказ «имя значится и "
                "там и там», и до печати формы дело не доходит); целыми ⑦ ⑧ (судят исходники и "
                "запись адреса) и ⑩ ⑬ ⑭ (их адресат и так за пределами)"),
            # ⚡ AIA-A (карточка A из пятёрки правок 2026-09-13): session_id перестаёт
            # учитываться при печати самой формы вызова — как если бы правку откатили.
            "session-id-order": (
                'if target.get("session_id"):',
                'if False and target.get("session_id"):',
                "session_id перестаёт учитываться при печати формы вызова (откат правки A). "
                "Ждём красным РОВНО ⑮ (форма по идентификатору не появляется вовсе); ⑯ остаётся "
                "зелёным — он и так проверяет случай БЕЗ session_id и поломки не касается; "
                "⑰ ⑱ не про эту ветку кода и тоже целы"),
        }
        if a.porcha:
            before_text, after_text, expectation = BREAKS[a.porcha]
            patch_text = tool.read_text(encoding="utf-8")
            assert patch_text.count(before_text) == 1, (
                f"поломка «{a.porcha}» НЕ ЛЕГЛА: искомое место встречается "
                f"{patch_text.count(before_text)} раз — поправь приёмку, а не инструмент")
            tool.write_text(patch_text.replace(before_text, after_text), encoding="utf-8")
            print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.porcha}»: {expectation}\n")

        con = sqlite3.connect(str(db))
        if "role_sessions" not in {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            con.close()
            code, output = call_tool(schema_step, db)
            if code != 0:
                sys.exit(f"⛔ шаг схемы на копии не прошёл:\n{output}")
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
        note_id = con.execute("SELECT max(id) FROM messages WHERE writer_role='PROTO'").fetchone()[0]
        # карточка с ЧУЖИМ держателем: взятие от CHROME
        card = con.execute("SELECT max(id) FROM backlog").fetchone()[0]
        con.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type, body_md) "
                    "VALUES (?, datetime('now'), 'CHROME', 'claim', ?)",
                    (card, "до 2026-09-09 10:00:00 UTC · чужая рука"))
        # истёкшее объявление о правке у COORD
        con.execute("INSERT INTO tool_leases (role, tools, reason, taken_at, until_utc) "
                    "VALUES ('COORD', 'x.py', 'опыт приёмки', datetime('now','-3 hours'), "
                    "datetime('now','-2 hours'))")
        con.commit()
        con.close()
        con2 = sqlite3.connect(str(db))

        # ① сигнал о записке.
        # 🩸 ДВЕ ПРАВКИ, ОБЕ ОТ ЧУЖИХ РУК В ОДИН ЧАС, И ВТОРАЯ ГЛУБЖЕ ПЕРВОЙ.
        # ① COORD: случай ждал «последнюю записку отправителя ВООБЩЕ», а печатник по своей
        #    справке даёт последнюю К АДРЕСАТУ. У автора совпадало — случай был зелен всегда.
        # ② TAXO: повторить запрос печатника — тоже негодно. Контроль, спрашивающий базу ТЕМ ЖЕ
        #    вопросом, не проверяет инструмент, а повторяет его (правило counter-case-own-definition).
        # ⇒ случай судит СВОЙСТВО напечатанного номера, а не СПОСОБ его выбора:
        #      напечатанная записка адресована цели И новее её к цели ничего нет.
        # Свойство проверяемо при любом способе выбора и не зависит от того, кто писал последним.
        code, output = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "записка")
        printed = re.search(r"записка #(\d+) к тебе", output)
        number = int(printed.group(1)) if printed else None
        addressed = newer = None
        if number:
            addressed = con2.execute(
                "SELECT 1 FROM message_addressee WHERE message_id = ? AND upper(role) = 'COORD'",
                (number,)).fetchone() is not None
            newer = con2.execute(
                "SELECT COUNT(*) FROM messages m JOIN message_addressee a ON a.message_id = m.id "
                "WHERE m.writer_role = 'PROTO' AND upper(a.role) = 'COORD' AND m.id > ?",
                (number,)).fetchone()[0]
        case("① номер в сигнале — записка, ДЕЙСТВИТЕЛЬНО адресованная цели, и свежее её нет",
             code == 0 and number is not None and bool(addressed) and newer == 0,
             f"код {code} · напечатан #{number} · адресован COORD: {addressed} · "
             f"новее к COORD: {newer}", differ=True)

        # ② имя отправителя не впечатано
        code2, output2 = call_tool(tool, db, "--role", "COORD", "--to", "PROTO", "--kind", "записка")
        from_coord = "COORD → PROTO:" in output2
        case("② имя отправителя подставляется, а не впечатано",
             code2 == 0 and from_coord,
             f"вызов от COORD даёт «COORD → PROTO»: {'да' if from_coord else 'НЕТ — имя впечатано'}",
             differ=True)

        # ③ адреса нет
        code3, output3 = call_tool(tool, db, "--role", "PROTO", "--to", "CORE", "--kind", "записка")
        case("③ адреса роли в реестре нет → отказ СЛОВАМИ, не пустота",
             code3 == 2 and "АДРЕСА РОЛИ CORE" in output3 and "--set-address" in output3,
             f"код {code3} · сказано, чего не хватает и что делать: "
             f"{'да' if '--set-address' in output3 else 'НЕТ'}", differ=True)

        # ④ «держишь» про чужую карточку
        code4, output4 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "держишь",
                            "--card", str(card))
        no_text = "SendMessage(" not in output4
        case("④ «держишь» про карточку ЧУЖОГО держателя → отказ, текст не печатается",
             code4 == 2 and no_text and "CHROME" in output4,
             f"код {code4} · вызов не напечатан: {'да' if no_text else 'НЕТ — ушла бы неправда'}",
             differ=True)

        # ⑤ старый адрес
        code5, output5 = call_tool(tool, db, "--role", "PROTO", "--to", "STUD", "--kind", "записка")
        case("⑤ адрес старше суток → отказ с часом записи и доводом",
             code5 == 2 and "СТАР" in output5 and "признака недоставки" in output5,
             f"код {code5} · назван час записи и почему это важно: "
             f"{'да' if 'признака недоставки' in output5 else 'НЕТ'}", differ=True)

        # ⑥ истёкшее объявление о правке в текст НЕ входит.
        # 🩸 ЗДЕСЬ БЫЛ СЛЕПОЙ СЛУЧАЙ, НАЙДЕННЫЙ ЧУЖОЙ ПОРЧЕЙ (TAXO, 18:46 UTC): прежняя
        # редакция разбирала вывод ТОГО ЖЕ вызова, что и случай ④ — а там карточку держит
        # ЧУЖОЙ, печатник законно ОТКАЗЫВАЕТ и до объявления о правке не доходит вовсе.
        # Искомых слов в отказе нет ПО ПОСТРОЕНИЮ ⇒ случай был зелен при любом поведении,
        # и живой дефект («ТЫ держишь объявление о правке №175» через два часа после срока)
        # поймал побочно СОСЕДНИЙ случай.
        # ⚡ КЛАСС: раньше проверка зеленела от совпадения ДАННЫХ, теперь — от ОТКАЗА соседа.
        # Второе тише: данные меняются каждый час, а отказ соседа стои́т всегда.
        # ⇒ раскладка своя: карточку держит САМ адресат, объявление у него истёкшее (рецепт
        # TAXO, проверенный ею на обоих состояниях печатника).
        con3 = sqlite3.connect(str(db))
        # ⚠️ Раскладка обязана оставить у адресата ТОЛЬКО истёкшее объявление: первый прогон
        # покраснел честно — у роли нашлось ещё и ЖИВОЕ, и печатник верно его напечатал.
        # Опыт судил бы тогда не то, что обещает.
        con3.execute("UPDATE tool_leases SET until_utc = datetime('now','-2 hours') "
                     "WHERE role = 'COORD' AND released_at IS NULL")
        own_card = con3.execute("SELECT max(backlog_id) FROM backlog_events").fetchone()[0]
        con3.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type, body_md) "
                     "VALUES (?, datetime('now'), 'COORD', 'claim', ?)",
                     (own_card, "до 2026-09-09 10:00:00 UTC · держит сам адресат"))
        con3.commit()
        con3.close()
        code6, output6 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "держишь",
                            "--card", str(own_card))
        printed = "SendMessage(" in output6
        # 🪤 Смотрим ТОЛЬКО текст сообщения, а не весь вывод: ниже печатается справка
        # «когда слать: чужое взятие ИЛИ ОБЪЯВЛЕНИЕ О ПРАВКЕ держит твою работу» — и первая
        # редакция случая красила её, то есть краснела по посторонней причине (третий такой
        # случай за смену). Судим то, что уедет соседу, а не то, что видит отправитель.
        body_text = re.search(r'message="([^"]*)"', output6)
        has_lease_text = bool(body_text) and "объявление о правке" in body_text.group(1)
        case("⑥ истёкшее объявление о правке не считается «держит» (текст напечатан, его там нет)",
             code6 == 0 and printed and not has_lease_text,
             f"код {code6} · текст напечатан: {printed} · объявление в тексте: "
             f"{'ЕСТЬ — сигнал о том, чего давно нет' if has_lease_text else 'нет'}", differ=True)

        # ⑦ контроль: печатник не отправляет.
        # ⚡ Разбором ТОКЕНОВ, а не образцом по строке: первый вариант этого случая искал
        # «SendMessage(» регулярным выражением и покраснел на строке, которая его ПЕЧАТАЕТ.
        # Печать вызова и вызов выглядят одинаково ровно до того часа, когда код разобран.
        source_text = live_tool.read_text(encoding="utf-8")
        code_without_text = []
        with io.open(live_tool, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                # 🪤 f-строка с версии 3.12 разбирается НА ЧАСТИ (FSTRING_START/MIDDLE/END),
                # и её текст выходит из-под фильтра «STRING». Первый вариант этого случая
                # честно отбрасывал STRING и всё равно видел печатаемую строку как код.
                if tok.type not in (tokenize.STRING, tokenize.COMMENT,
                                  getattr(tokenize, "FSTRING_START", -1),
                                  getattr(tokenize, "FSTRING_MIDDLE", -1),
                                  getattr(tokenize, "FSTRING_END", -1)):
                    code_without_text.append(tok.string)
        executable_text = " ".join(code_without_text)
        calls_send = "SendMessage" in executable_text
        prints_call = "SendMessage(to=" in source_text
        case("⑦ печатник только ПЕЧАТАЕТ вызов, отправки в исполняемом коде нет",
             prints_call and not calls_send,
             f"вызов есть в тексте для человека: {'да' if prints_call else 'НЕТ'} · "
             f"в исполняемом коде: {'ЕСТЬ — отправка мимо руки роли' if calls_send else 'нет'}",
             differ=True)  # 🔑 РАЗЛИЧАЮЩИЙ, а не «контроль»: доказано чужой порчей (TAXO 18:57 UTC —
        # вызов настоящей отправки внутри незовомой функции ⇒ случай покраснел первым же прогоном).
        # Пометка «контроль» была РАЗМЕТКОЙ автора, а не свойством случая.

        # ⑧ адрес без различителя в скобках (находка COORD: одно имя носят ДВА разговора)
        code8, output8 = call_tool(tool, db, "--role", "CORE", "--set-address", "atlas-17")
        case("⑧ адрес без различителя в скобках не принимается",
             code8 == 2 and "РАЗЛИЧИТЕЛ" in output8,
             f"код {code8} · сказано, что имя указывает на несколько разговоров: "
             f"{"да" if "НЕСКОЛЬКО" in output8 else "НЕТ"}", differ=True)

        # ⑨ свежая записка отправителя, НЕ числящаяся адресату → сказано вслух
        con2.execute("INSERT INTO messages (writer_role, timestamp, body_md) "
                     "VALUES ('PROTO', datetime('now'), 'записка без адресатов полями')")
        con2.commit()
        latest = con2.execute("SELECT max(id) FROM messages WHERE writer_role='PROTO'").fetchone()[0]
        code9, output9 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "записка")
        case("⑨ есть записка новее, но не числящаяся адресату → сказано вслух, не подставлено молча",
             code9 == 0 and f"#{latest}" in output9 and "НОВЕЕ" in output9,
             f"код {code9} · про записку #{latest} сказано: "
             f"{'да' if 'НОВЕЕ' in output9 else 'НЕТ — подставлена старая молча'}", differ=True)
        con2.close()

        # ═══ 🌉 УСЛОВИЕ РЕДАКЦИИ 2 ПРАВИЛА signal-not-carrier (карточка #570) ═══
        # «ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ; ПОЯВИТСЯ ОБЩЕЕ МЕСТО — ПОЕДЕТ ЗВОНОК.»
        # Имя соседа и имя своего контура берутся ИЗ БАЗЫ, а не впечатаны: впечатанное
        # «tapas» пережило бы закрытие моста и судило бы несуществующее.
        con4 = sqlite3.connect(str(db))
        our_group = con4.execute(
            "SELECT lower(value) FROM meta WHERE key = 'group_name'").fetchone()
        neighbor_row = con4.execute(
            "SELECT target_group FROM cross_links WHERE lower(source_group) = "
            "(SELECT lower(value) FROM meta WHERE key = 'group_name') LIMIT 1").fetchone()
        if not our_group or not neighbor_row:
            con4.close()
            sys.exit("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: в базе нет имени своего контура либо ни одной "
                     "связи с соседом — случаям ⑩–⑬ судить нечего, и зелёный тут был бы ложью")
        our_group, neighbor_name = our_group[0], neighbor_row[0].strip().lower()

        # ⑩ адресат ЗА пределами контура: условие НАЗВАНО словами правила
        code10, output10 = call_tool(tool, db, "--role", "PROTO", "--to", neighbor_name.upper())
        condition_shown = "ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ" in output10
        letter = "ПИСЬМО СОСЕДНЕМУ КОНТУРУ" in output10
        no_call = "SendMessage(" not in output10
        case("⑩ адресат ЗА пределами контура → условие НАЗВАНО словами правила, печатается "
             "письмо, а не строка с номером записки",
             code10 == 0 and condition_shown and letter and no_call,
             f"код {code10} · условие названо: "
             f"{'да' if condition_shown else 'НЕТ — печатник молчит там, где обязан говорить'} · "
             f"форма письма: {letter} · номер записки соседу НЕ послан: {no_call}",
             differ=True)

        # ⑪ ВСТРЕЧНЫЙ. Без него ⑩ зелен и у печатника, который называет условие ВСЕМ:
        # такой печатник учит роль возить тело мимо ленты внутри контура — то есть
        # ровно тому, что правило запрещает, и учит с полной уверенностью.
        code11, output11 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD",
                              "--kind", "записка")
        silent = "ТЕЛО ЕДЕТ ТАМ" not in output11 and "ПИСЬМО СОСЕДНЕМУ" not in output11
        previous_output = "SendMessage(" in output11 and "СИГНАЛ — НЕ НОСИТЕЛЬ" in output11
        case("⑪ ВСТРЕЧНЫЙ: адресат ВНУТРИ контура → условие НЕ печатается, прежний вывод цел",
             code11 == 0 and silent and previous_output,
             f"код {code11} · условие не названо: "
             f"{'да' if silent else 'НЕТ — печатник называет его всем подряд'} · "
             f"прежний короткий сигнал на месте: {previous_output}", differ=True)

        # ⑫ ВСТРЕЧНЫЙ: тело в сообщении внутри контура — по-прежнему отказ
        body_file_path = sandbox / "body.md"
        body_file_path.write_text("разбор на две строки\nвторая строка тела", encoding="utf-8")
        code12, output12 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD",
                              "--body-file", str(body_file_path))
        body_stayed = "разбор на две строки" not in output12 and "SendMessage(" not in output12
        case("⑫ ВСТРЕЧНЫЙ: попытка вложить тело адресату ВНУТРИ контура → по-прежнему ОТКАЗ",
             code12 == 2 and "ВНУТРИ КОНТУРА" in output12 and body_stayed,
             f"код {code12} · тело в вывод не попало: "
             f"{'да' if body_stayed else 'НЕТ — условие растянули на свой контур'}",
             differ=True)

        # ⑬ ВСТРЕЧНЫЙ к ⑫: то же тело за пределы контура ВХОДИТ в письмо. Без него ⑫
        # зелен и у печатника, который отклоняет --body-file вообще всем, — а тогда на
        # мосту он снова предписывает неисполнимое, ради чего условие и вносили.
        code13, output13 = call_tool(tool, db, "--role", "PROTO", "--to", neighbor_name.upper(),
                              "--body-file", str(body_file_path))
        included = "разбор на две строки" in output13 and "вторая строка тела" in output13
        case("⑬ ВСТРЕЧНЫЙ к ⑫: то же тело адресату ЗА пределами контура ВХОДИТ в письмо "
             "(отказ ⑫ — про сторону, а не про сам ключ вызова)",
             code13 == 0 and included,
             f"код {code13} · тело в письме: "
             f"{'да' if included else 'НЕТ — ключ отклонён всем подряд'}", differ=True)

        # ⑭ ВТОРОЙ ИСТОЧНИК ПРИЗНАКА — каталог обмена НА ДИСКЕ, без записи связи в базе.
        # Заводится СВОЙ контейнер во временном каталоге и показывается печатнику
        # переменной среды: так проверяется, что сосед опознаётся по каталогу, а не
        # только по базе. Имя соседа выбрано заведомо отсутствующим в базе — это
        # проверено тут же, иначе случай зеленел бы по посторонней причине.
        new_neighbor = "neigh"
        already_in_db = con4.execute("SELECT 1 FROM cross_links WHERE lower(target_group) = ?",
                                   (new_neighbor,)).fetchone()
        assert not already_in_db, "имя нового соседа уже есть в базе — случай ⑭ судил бы не то"
        con4.close()
        container = sandbox / "чужой-контейнер"
        (container / ".mezosync").mkdir(parents=True, exist_ok=True)
        (container / ".mezosync" / "mezosync.db").write_bytes(b"")
        (container / "repo" / ".mezosync" / "bridges" /
         f"{our_group}-{new_neighbor}").mkdir(parents=True, exist_ok=True)
        code14, output14 = call_tool(tool, db, "--role", "PROTO", "--to", new_neighbor.upper(),
                              extra_env={"MEZO_CONTAINER": str(container)})
        recognized = f"ПИСЬМО СОСЕДНЕМУ КОНТУРУ «{new_neighbor}»" in output14
        by_directory = "каталог обмена" in output14
        case("⑭ сосед, о котором в базе связи НЕТ, опознаётся по каталогу обмена на диске",
             code14 == 0 and recognized and by_directory,
             f"код {code14} · опознан как соседний контур: "
             f"{'да' if recognized else 'НЕТ — второй источник признака не работает'} · "
             f"путь назван: {by_directory}", differ=True)

        # ═══ AIA-A (карточка A из пятёрки правок 2026-09-13): role_sessions.session_id ═══
        # Стойкий идентификатор сессии — переживает возобновление чата, в отличие от
        # короткого адреса «имя [код]». Шаг схемы накатывается ЗДЕСЬ, на ту же копию:
        # он идёт ПОСЛЕ 20260905-role-sessions.py и ничего не портит поверх него.
        session_id_step = mezo_paths.live_scripts(__file__) / "migrations" / \
            "20260913-role-sessions-session-id.py"
        code_session_id_step, output_session_id_step = call_tool(session_id_step, db)
        if code_session_id_step != 0:
            sys.exit(f"⛔ шаг схемы session_id на копии не прошёл:\n{output_session_id_step}")
        con5 = sqlite3.connect(str(db))
        con5.execute("INSERT INTO role_sessions (role, address, session_id, noted_at, "
                     "noted_by, source) VALUES ('SIDROLE', 'atlas-sid [abc123]', "
                     "'local_deadbeef00', datetime('now'), 'SIDROLE', 'self')")
        con5.commit()
        con5.close()

        # ⑮ session_id есть → форма ПО ИДЕНТИФИКАТОРУ печатается ПЕРВОЙ
        code15, output15 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDROLE",
                              "--kind", "записка")
        by_id = 'mcp__ccd_session_mgmt__send_message(session_id="local_deadbeef00"' in output15
        by_id_first = (by_id and output15.find("mcp__ccd_session_mgmt__send_message")
                        < output15.find('SendMessage(to="atlas-sid'))
        case("⑮ session_id есть → форма по идентификатору печатается ПЕРВОЙ, форма по имени — второй",
             code15 == 0 and by_id and by_id_first and "переживает возобновление" in output15,
             f"код {code15} · форма по id есть: {by_id} · идёт раньше формы по имени: "
             f"{by_id_first}", differ=True)

        # ⑯ ВСТРЕЧНЫЙ: session_id НЕ записан → формы по идентификатору нет вовсе
        code16, output16 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD",
                              "--kind", "записка")
        case("⑯ ВСТРЕЧНЫЙ: session_id не записан → формы по идентификатору НЕТ, только по имени",
             code16 == 0 and "mcp__ccd_session_mgmt__send_message" not in output16
             and 'SendMessage(to="' in output16,
             f"код {code16} · форма по id отсутствует: "
             f"{'да' if 'mcp__ccd_session_mgmt__send_message' not in output16 else 'НЕТ'}",
             differ=True)

        # ⑰ --list не выдаёт свежий адрес за «жив»: ✅ убран, граница названа словами
        code17, output17 = call_tool(tool, db, "--list")
        case("⑰ --list не печатает «✅» как «жив»: возраст + явная граница вместо галочки",
             code17 == 0 and "✅" not in output17 and "живость не проверялась" in output17
             and "≠ «жива»" in output17 and "≠ «мертва»" in output17,
             f"код {code17} · «✅» в выводе: "
             f"{'ЕСТЬ — читается как живость' if '✅' in output17 else 'нет'} · "
             f"граница названа: {'да' if '≠ «мертва»' in output17 else 'НЕТ'}", differ=True)

        # ⑱ перезапись адреса печатает «ПЕРЕЗАПИСАН: было …», прежняя строка уходит в историю
        con6 = sqlite3.connect(str(db))
        history_before = con6.execute("SELECT COUNT(*) FROM role_sessions_history "
                                  "WHERE role='SIDROLE'").fetchone()[0]
        con6.close()
        code18, output18 = call_tool(tool, db, "--role", "SIDROLE", "--set-address",
                              "atlas-sid2 [fedcba]")
        con6 = sqlite3.connect(str(db))
        history_after = con6.execute("SELECT COUNT(*) FROM role_sessions_history "
                                     "WHERE role='SIDROLE'").fetchone()[0]
        con6.close()
        case("⑱ перезапись адреса печатает «ПЕРЕЗАПИСАН: было …» и уводит прежнюю строку в историю",
             code18 == 0 and "ПЕРЕЗАПИСАН: было" in output18 and "local_deadbeef00" in output18
             and history_after == history_before + 1,
             f"код {code18} · «ПЕРЕЗАПИСАН» напечатан: {'ПЕРЕЗАПИСАН: было' in output18} · "
             f"история {history_before} → {history_after}", differ=True)

        print("")
        print(f"ИТОГ: {GREENS} из {CASES} · различающих {DIFFER}, "
              f"из них ДОКАЗАНО нарочной поломкой 15 (14 прежних + ⑮ поломкой "
              f"«session-id-order»)")
        # ⚖️ Форма TAXO (приёмка 05.09): число различающих растёт вместе с числом случаев
        # и перестаёт что-либо значить, если не сказано, сколько из них ПОДТВЕРЖДЕНО поломкой.
        # Доказаны поломкой ВСЕ ЧЕТЫРНАДЦАТЬ: ① ② ④ ⑨ (автор) · ③ ⑤ ⑦ ⑧ (чужая рука,
        # TAXO 18:57 UTC) · ⑥ (её же рецепт после починки 18:51) · ⑩ ⑬ (ослеплённая-связь,
        # 06.09) · ⑭ (ослеплённый-каталог, 06.09) · ⑪ ⑫ (условие-всем, 06.09 — обратная
        # слепота: печатник, называющий условие каждому, красит оба встречных случая). 🔑 Её находка, ради которой это и считается:
        # строка «различающих 8» была верна ЧИСЛОМ и неверна СОСТАВОМ — в неё был зачтён ⑥,
        # который тогда краснеть не мог, и НЕ зачтён ⑦, который мог. Две ошибки взаимно
        # погасились, и число вышло верным ПО ПОСТОРОННЕЙ ПРИЧИНЕ. Сверив только итог,
        # не нашли бы ни одной.
        return 0 if GREENS == CASES else 1
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
