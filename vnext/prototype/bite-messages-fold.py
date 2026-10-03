# -*- coding: utf-8 -*-
r"""ПРИЁМКА переноса записок в архив — карточка #538 шаг ③ часть ③.

🩸 ЧЕМ ОПЛАЧЕНЫ СЛУЧАИ (оба дефекта поймал первый прогон на копии, до всякой живой базы):
```
① проверка ссылок краснела на числах, которых в базе НЕ БЫЛО НИКОГДА («15803», «263238»
   в текстах — просто числа). Перенос был ни при чём: красное горело по ПОСТОРОННЕЙ причине,
   а такой отказ учат обходить ⇒ судим РАЗНИЦУ «разрешалось до / после», не факт
② мерка неизменности включала В СЕБЯ предмет изменения: отпечаток считался по «источник, номер»,
   а перенос источник и меняет («живая лента» → «архив»). Инструмент честно откатил ВЕРНЫЙ
   перенос. Откат сработал, мерка — нет
```
⚡ КЛАСС второго: защита, запрещающая работу, выглядит как сработавшая защита. Отличить можно
только спросив, ЧТО именно мерка обязана считать неизменным.

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① холостой прогон НИЧЕГО не меняет: счёт и отпечаток до = после          РАЗЛИЧАЮЩИЙ
  ② перенос → возврат возвращает ленту в исходное состояние (обратимость)  РАЗЛИЧАЮЩИЙ
  ③ речь владельца не уносится ни при каком возрасте                       РАЗЛИЧАЮЩИЙ
  ④ срочное незакрытое не уносится                                        РАЗЛИЧАЮЩИЙ
  ⑤ записка, на которую ссылается свежая, остаётся (разговор жив)          РАЗЛИЧАЮЩИЙ
  ⑥ читатель, не видящий архив ⇒ ОТКАЗ переносить (условие ① правила)      РАЗЛИЧАЮЩИЙ
  ⑥б читатель видит архив ЧАСТЬЮ запросов ⇒ тоже отказ; слово в комментарии — не в счёт РАЗЛИЧАЮЩИЙ
  ⑦ адресаты унесённых: живая таблица теряет, вид видит                    РАЗЛИЧАЮЩИЙ
  ⑧ контроль: ни одна запись не пропала — сумма живых и архива постоянна
  ⑨ непрочитанное хоть одной ролью не уносится; прочитанное ниже — уносится РАЗЛИЧАЮЩИЙ
  ⑩ самопроверка по каждой роли ловит непрочитанное, даже если отбор сломан РАЗЛИЧАЮЩИЙ
  ⑪ контроль: холостой прогон печатает «непрочитанных в отборе: 0» и кто держит отметку

━━ ⑨–⑪: ПОЧЕМУ (карточка #538, слово владельца 2026-10-03 11:45 UTC, чат PROTO — «перенос не
трогает непрочитанное») ━━
Повторная приёмка карточки #466 нашла: следующий шаг уносил непрочитанное спящих ролей (RCC 533,
CORE и CHROME по 48), а чтение ленты архив не видит. Отметки прочитанного в копии сначала
ставятся ВСЕМ ролям на последнюю записку: случаи ①–⑧ мерят СВОИ условия, и спящая роль живой
базы не должна решать, будет ли им что переносить (на свежем контуре из пакета отметки нулевые —
без этого не перенеслось бы ничего). Непрочитанное мерят ⑨ и ⑩ на своей паре подставных записок
A < B и своём проверочном читателе, дочитавшем ровно до A.

ПОРЧИ (--porcha). ОЖИДАНИЯ, НАЗВАННЫЕ ДО ПРОГОНА:
```
мерка-с-источником .. отпечатку возвращают источник и порядок по нему ⇒ проваливаются ② ⑦ ⑨
                      (все три стоят НА СОСТОЯВШЕМСЯ переносе — см. ниже)
без-отметки ......... отбор не смотрит на отметки ⇒ проваливается РОВНО ⑨: самопроверка
                      отказывает кодом 2, и прочитанное A тоже не уносится
без-самопроверки .... самопроверка выключена ⇒ проваливается РОВНО ⑩: при сломанном отборе
                      непрочитанное уносится молча
условие-по-слову .... условие ① снова судит наличие слова в файле ⇒ проваливается РОВНО ⑥б
```
━━ ⑥б: ПОЧЕМУ (проверка переноса 03.10 12:55 UTC) ━━ Случай ⑥ портил ВСЕ упоминания вида в копии
read-broadcasts.py — случай своего автора. Живой был другим: подтверждение шло через вид, а входящие
и «ждём» — мимо, и условие ① засчитывало файл по одному слову; после шага 02.10 записки #4 и #49
ушли из входящих восьми ролей. ⑥б портит ОДИН запрос и отдельно кладёт «FROM messages» в комментарий.
Почему у «мерки-с-источником» краснеют ② и ⑦ (уточнено после первого прогона — честно, вслух):
```
② обратимость ....... перенос откатывается сам, проверять обратимость не на чем
⑦ адресаты .......... стои́т НА СОСТОЯВШЕМСЯ переносе: если унесено ноль, живая таблица
                      и вид дают одно число, и разница исчезает
⑨ непрочитанное ..... та же зависимость: A обязано уехать, а перенос откатывается
```
🩸 Первая редакция ожидания говорила «краснеет РОВНО ②», и прогон её опроверг. Записано
как есть, а не подогнано: ожидание было неточным, потому что автор держал в голове предмет
случая ⑦ («адресаты теряются») и забыл, что у случая есть УСЛОВИЕ — перенос должен произойти.
⚡ КЛАСС: случай, стоящий на результате другого случая, краснеет вместе с ним — и это не шум,
а зависимость, которую надо назвать. Не назвав её, автор объявляет порчу «не сошедшейся»
и идёт чинить исправное.

═══ ДОГОН (карточка #667, приёмка пакета на пустом новом контуре) ═══
Свежесобранный из пакета контур несёт ПУСТУЮ ленту — кандидатов на перенос в ней нет
по построению, и случаи ②/⑦ стоят НА СОСТОЯВШЕМСЯ переносе (см. выше, то же условие,
каким уже объяснена порча). seed_fixture() заводит в копии ОДНУ свою старую обычную
записку с адресатом — ровно то немногое, чего не хватает, чтобы перенос состоялся и было
что мерить. На живом контуре, где кандидатов и так хватает, эта одна строка ничего не
меняет по существу: она добавляется ДО снимка "before", значит входит в оба снимка
одинаково, и ни одно из существующих равенств/неравенств не грубеет.
Тул переноса (`messages-fold.py` в `.mezosync/scripts`) сам может отсутствовать в свежей
выгрузке пакета — она собрана до его появления. Это — честный «не проверено» (смысл
правила acceptance-isolated-from-live), не поломка: инструмента переноса нет, и мерить
нечем совсем, ДО какой-либо фикстуры.

⛔ Живой базы не касается: работает на КОПИИ во временном каталоге.
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

CASES = DIFFER = GREENS = 0

FIXTURE_MARKER = "[приёмка#538 bite-messages-fold: подставная старая записка]"
UNREAD_MARKER = "[приёмка#538 bite-messages-fold: пара для непрочитанного]"
TEST_READER = "BITE-FOLD-READER"
UNREAD_WORD = "не прочитано"
FILTER_LINE = "        if floor is not None and mid > floor:"
SELF_CHECK_LINE = "    unread = unread_in_selection(chosen, marks)"
STRICT_LINE = "        elif strict and (lines := direct_queries(text)):"


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, GREENS
    CASES += 1
    DIFFER += bool(differ)
    GREENS += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def call_tool(tool, db, *args):
    r = subprocess.run([sys.executable, "-B", str(tool), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def exact_tags(value) -> list:
    """Метки записки СПИСКОМ, а не подстрокой: «WAITING-OWNER-WORD» и «owner-word» — разные метки."""
    import json
    try:
        return json.loads(value or "[]")
    except Exception:
        return []


def snapshot(db):
    con = sqlite3.connect(str(db))
    live = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    archive = con.execute("SELECT COUNT(*) FROM messages_archive").fetchone()[0]
    totals = con.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(body_md)),0) FROM messages_all").fetchone()
    con.close()
    return {"live": live, "archive": archive, "total": totals[0], "chars": totals[1]}


def seed_fixture(db) -> None:
    """Подкладывает в копию СВОЮ старую обычную записку с адресатом — единственное, чего
    пустой свежий контур (карточка #667) не несёт по построению, а без чего случаям ②/⑦
    не на чём измерить перенос (см. заголовок файла, раздел «ДОГОН»). Обычная метка/
    приоритет — чтобы запись сама по себе не задела случаи ③④⑤, которые считают СВОЙ
    собственный материал запросом, а не по имени."""
    con = sqlite3.connect(str(db))
    con.execute(
        "INSERT INTO messages (writer_role, timestamp, body_md, tags, priority, resolved) "
        "VALUES ('PROTO', datetime('now','-30 days'), ?, '[]', 'normal', 0)",
        (f"{FIXTURE_MARKER} — обычная старая записка, кандидат на перенос",))
    fixture_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
    con.execute("INSERT INTO message_addressee (message_id, role, kind, linked_by) "
                "VALUES (?, 'COORD', 'to', 'field')", (fixture_id,))
    con.commit()
    con.close()


def seed_unread_pair(db) -> tuple[int, int]:
    """Две старые обычные записки A < B для ⑨/⑩: проверочный читатель дочитает ровно до A,
    значит A прочитана всеми, а B — нет. Свои, а не живые: на свежем контуре живых нет."""
    con = sqlite3.connect(str(db))
    ids = []
    for label in ("A — прочитана всеми", "B — НЕ прочитана проверочным читателем"):
        con.execute(
            "INSERT INTO messages (writer_role, timestamp, body_md, tags, priority, resolved) "
            "VALUES ('PROTO', datetime('now','-30 days'), ?, '[]', 'normal', 0)",
            (f"{UNREAD_MARKER} {label}",))
        ids.append(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    con.commit()
    con.close()
    return ids[0], ids[1]


def mark_everything_read(db) -> None:
    """Всем ролям копии — отметку на последнюю записку (см. заголовок, раздел ⑨–⑪)."""
    con = sqlite3.connect(str(db))
    con.execute("UPDATE read_cursors SET last_read_id = (SELECT MAX(id) FROM messages_all)")
    con.commit()
    con.close()


def set_test_reader(db, last_read_id) -> None:
    """Проверочный читатель: поставить отметку (номер) или убрать строку (None)."""
    con = sqlite3.connect(str(db))
    if last_read_id is None:
        con.execute("DELETE FROM read_cursors WHERE reader_role = ?", (TEST_READER,))
    else:
        con.execute("INSERT OR REPLACE INTO read_cursors (reader_role, last_read_id) VALUES (?, ?)",
                    (TEST_READER, last_read_id))
    con.commit()
    con.close()


def archive_ids_of(db) -> set:
    con = sqlite3.connect(str(db))
    ids = {r[0] for r in con.execute("SELECT id FROM messages_archive")}
    con.close()
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["мерка-с-источником", "без-отметки", "без-самопроверки",
                                         "условие-по-слову"])
    a = ap.parse_args()

    live_tool = mezo_paths.live_scripts(__file__) / "messages-fold.py"
    if not live_tool.is_file():
        print(f"⚪ не проверено: инструмента переноса записок messages-fold.py нет в контуре "
              f"(ожидался в {live_tool}) — свежая выгрузка пакета собрана до его появления "
              f"в .mezosync/scripts, механизм мерить нечем")
        return 2

    stand = pathlib.Path(tempfile.mkdtemp(prefix="bite-fold-"))
    try:
        db = stand / "copy.db"
        src = sqlite3.connect(str(mezo_paths.live_db(__file__)))
        dst = sqlite3.connect(str(db))
        src.backup(dst)
        dst.close()
        src.close()

        # копия инструмента и его соседей рядом (он читает mezo_refs из своего каталога)
        tool = stand / "messages-fold.py"
        shutil.copy2(live_tool, tool)
        shutil.copy2(mezo_paths.live_scripts(__file__) / "mezo_refs.py", stand / "mezo_refs.py")
        for name in ("read-broadcasts.py", "write-message.py"):
            src_file = mezo_paths.live_scripts(__file__) / name
            if src_file.is_file():
                shutil.copy2(src_file, stand / name)

        # 🩹 ДОГОН 03.10.2026 (записка #5456 OPSSRE): живая база несёт архив — 100 записок с
        # 02.10.2026 22:08 UTC (карточка #538, первый настоящий шаг переноса). --unfold по замыслу
        # возвращает ВСЁ из архива, поэтому «перенос → возврат» в копии с непустым архивом
        # возвращал и эти 100, и ② не проходил на ВЕРНОМ инструменте («4027/0, ждали 3927/100»).
        # ⚡ Приёмка мерила случай своего автора: когда её писали, архив был пуст.
        # ⇒ копию приводим к пустому архиву тем же обратным ходом ДО порчи (порча ломает мерку
        # инструмента, и приведение откатилось бы само) и ДО снимка; приведение без потерь —
        # условие, без которого мерить нечем: не вышло — отказ кодом 2, а не провал случаев.
        pre = snapshot(db)
        if pre["archive"]:
            code0, output0 = call_tool(tool, db, "--unfold", "--apply")
            post = snapshot(db)
            if not (code0 == 0 and post["archive"] == 0
                    and post["live"] == pre["live"] + pre["archive"]
                    and post["total"] == pre["total"] and post["chars"] == pre["chars"]):
                print(f"⚪ не проверено: копию не удалось привести к пустому архиву обратным ходом — "
                      f"код {code0} · было {pre['live']}/{pre['archive']} · стало "
                      f"{post['live']}/{post['archive']} (записей {pre['total']} → {post['total']})")
                print(output0)
                return 2
            print(f"🩹 копия приведена к пустому архиву обратным ходом: вернулось {pre['archive']} "
                  f"(живых/архив {pre['live']}/{pre['archive']} → {post['live']}/0, записей и знаков "
                  f"столько же)\n")

        if a.porcha == "мерка-с-источником":
            text = tool.read_text(encoding="utf-8")
            before_text = text
            text = text.replace('"FROM messages_all ORDER BY id"',
                                 '"FROM messages_all ORDER BY source, id"')
            text = text.replace('"SELECT id, writer_role, timestamp, body_md, tags, priority, resolved "',
                                 '"SELECT id, writer_role, timestamp, body_md, tags, priority, resolved, source "')
            assert text != before_text, "порча не легла — строка мерки изменилась, поправь приёмку"
            tool.write_text(text, encoding="utf-8")
            print("🧪 ПОРЧА «мерка-с-источником»: ждём провала ② ⑦ ⑨ (стоят на состоявшемся переносе), "
                  "остальные целы\n")
        elif a.porcha in ("без-отметки", "без-самопроверки", "условие-по-слову"):
            line, broken, expect = {
                "без-отметки": (FILTER_LINE, "        if False:", "⑨"),
                "без-самопроверки": (SELF_CHECK_LINE, "    unread = {}", "⑩"),
                "условие-по-слову": (STRICT_LINE, "        elif False:", "⑥б"),
            }[a.porcha]
            text = tool.read_text(encoding="utf-8")
            assert line in text, f"порча не легла — строки «{line.strip()}» нет, поправь приёмку"
            tool.write_text(text.replace(line, broken), encoding="utf-8")
            print(f"🧪 ПОРЧА «{a.porcha}»: ждём провала РОВНО {expect}, остальные целы\n")

        # 🩹 ДОГОН (карточка #667): своя фикстура ДО первого снимка — входит в оба снимка
        # одинаково, случаям ①/⑧ (неизменность/сохранность) всё равно, кто её завёл.
        seed_fixture(db)
        a_id, b_id = seed_unread_pair(db)
        mark_everything_read(db)

        before = snapshot(db)

        # ── ① холостой прогон ничего не меняет
        code1, output1 = call_tool(tool, db)
        after_dry_run = snapshot(db)
        case("① холостой прогон НИЧЕГО не меняет",
             code1 == 0 and after_dry_run == before,
             f"код {code1} · до {before['live']}/{before['archive']} · "
             f"после {after_dry_run['live']}/{after_dry_run['archive']}", differ=True)

        # ── что инструмент собирался унести (для случаев ③④⑤)
        con = sqlite3.connect(str(db))
        # 🪤 МЕТКУ СРАВНИВАЕМ ТОЧНО, А НЕ ПОДСТРОКОЙ — оплачено первым прогоном этой приёмки.
        # Подстрока «owner-word» ловит метку «WAITING-OWNER-WORD» («ждём слова владельца»),
        # а это не речь владельца, а ожидание её. Приёмка покраснела на ВЕРНОМ инструменте.
        # ⚡ КЛАСС: приёмка и инструмент определяли предмет РАЗНЫМИ мерками, и грубее оказалась
        # мерка приёмки. Свойство, которое мы судим, — «среди точных меток есть owner-word».
        owner_count = len([1 for (t,) in con.execute(
            "SELECT tags FROM messages WHERE timestamp < datetime('now','-7 days')")
            if "owner-word" in exact_tags(t)])
        urgent_count = con.execute(
            "SELECT COUNT(*) FROM messages WHERE timestamp < datetime('now','-7 days') "
            "AND (priority = 'critical' OR (priority = 'high' AND COALESCE(resolved,0) = 0))"
        ).fetchone()[0]
        con.close()

        # ── ② перенос и возврат
        code2, output2 = call_tool(tool, db, "--apply")
        after_fold = snapshot(db)
        code3, output3 = call_tool(tool, db, "--unfold", "--apply")
        after_unfold = snapshot(db)
        case("② перенос → возврат возвращает ленту в исходное состояние",
             code2 == 0 and code3 == 0 and after_fold["archive"] > 0
             and after_unfold == before,
             f"перенесено {after_fold['archive']} · после возврата "
             f"{after_unfold['live']}/{after_unfold['archive']} "
             f"(ждали {before['live']}/{before['archive']})", differ=True)

        # ── повторный перенос для проверок содержимого архива
        call_tool(tool, db, "--apply")
        con = sqlite3.connect(str(db))
        archived_owner_count = len([1 for (t,) in con.execute(
            "SELECT tags FROM messages_archive") if "owner-word" in exact_tags(t)])
        archived_urgent_count = con.execute(
            "SELECT COUNT(*) FROM messages_archive WHERE priority = 'critical' "
            "OR (priority = 'high' AND COALESCE(resolved,0) = 0)").fetchone()[0]
        # ⑤ на кого ссылается свежая записка
        fresh_refs = set()
        import re as _re
        for (body,) in con.execute("SELECT body_md FROM messages_all "
                                   "WHERE timestamp >= datetime('now','-7 days')"):
            fresh_refs.update(int(n) for n in _re.findall(r"#(\d{2,6})", body or ""))
        archived_ids = {r[0] for r in con.execute("SELECT id FROM messages_archive")}
        affected_live = fresh_refs & archived_ids
        # ⑦ адресаты
        live_join_count = con.execute("SELECT COUNT(*) FROM message_addressee a "
                                 "JOIN messages m ON m.id = a.message_id").fetchone()[0]
        view_join_count = con.execute("SELECT COUNT(*) FROM message_addressee a "
                               "JOIN messages_all m ON m.id = a.message_id").fetchone()[0]
        final_snapshot = snapshot(db)
        con.close()

        case("③ речь владельца не уносится ни при каком возрасте",
             archived_owner_count == 0,
             f"старше срока с меткой владельца было {owner_count}, в архиве {archived_owner_count}",
             differ=True)
        case("④ срочное незакрытое не уносится",
             archived_urgent_count == 0,
             f"старше срока срочных незакрытых {urgent_count}, в архиве {archived_urgent_count}", differ=True)
        case("⑤ записка, на которую ссылается свежая, остаётся (разговор жив)",
             not affected_live,
             f"унесённых, на которые ссылается свежее: {len(affected_live)}", differ=True)

        # ── ⑥ читатель, не видящий архив ⇒ отказ
        call_tool(tool, db, "--unfold", "--apply")
        blind_copy = stand / "read-broadcasts.py"
        saved_text = blind_copy.read_text(encoding="utf-8") if blind_copy.is_file() else None
        if saved_text is not None:
            blind_copy.write_text(saved_text.replace("messages_all", "messages"), encoding="utf-8")
        code6, output6 = call_tool(tool, db, "--apply")
        if saved_text is not None:
            blind_copy.write_text(saved_text, encoding="utf-8")
        case("⑥ читатель, не видящий архив ⇒ ОТКАЗ переносить (условие ① правила)",
             code6 == 2 and "условие ①" in output6,
             f"код {code6} · отказ назван условием: {'да' if 'условие ①' in output6 else 'НЕТ'}",
             differ=True)

        # ── ⑥б ОДИН запрос мимо вида ⇒ отказ; «FROM messages» в комментарии ⇒ не отказ
        partial_ok = control_ok = False
        detail6b = "копии read-broadcasts.py в стенде нет — проверить нечем"
        if saved_text is not None and "FROM messages_all" in saved_text:
            blind_copy.write_text(saved_text.replace("FROM messages_all", "FROM messages", 1),
                                  encoding="utf-8")
            archive6b = len(archive_ids_of(db))
            code6b, output6b = call_tool(tool, db, "--apply")
            moved6b = len(archive_ids_of(db)) - archive6b
            if moved6b:   # проверка не сработала и перенос прошёл — вернуть, иначе ⑨ мерит не то
                call_tool(tool, db, "--unfold", "--apply")
            blind_copy.write_text(saved_text + "\n# FROM messages — только в комментарии, не запрос\n",
                                  encoding="utf-8")
            code6c, output6c = call_tool(tool, db)
            blind_copy.write_text(saved_text, encoding="utf-8")
            partial_ok = (code6b == 2 and "мимо вида" in output6b and moved6b == 0)
            control_ok = (code6c == 0 and "✅ условие ①" in output6c)
            detail6b = (f"один запрос мимо вида: код {code6b}, отказ «мимо вида» "
                        f"{'назван' if 'мимо вида' in output6b else 'НЕ назван'}, унесено {moved6b} · "
                        f"слово в комментарии: код {code6c}, условие ① "
                        f"{'пройдено' if '✅ условие ①' in output6c else 'НЕ пройдено'}")
        case("⑥б читатель видит архив ЧАСТЬЮ запросов ⇒ отказ; слово в комментарии — не в счёт",
             partial_ok and control_ok, detail6b, differ=True)

        case("⑦ адресаты унесённых: живая таблица теряет, вид видит",
             view_join_count > live_join_count,
             f"через живую таблицу {live_join_count} · через вид {view_join_count} "
             f"(разница {view_join_count - live_join_count} — они и потерялись бы у читателя «только моё»)",
             differ=True)

        case("⑧ контроль: ни одна запись не пропала",
             final_snapshot["total"] == before["total"] and final_snapshot["chars"] == before["chars"],
             f"записей {final_snapshot['total']} (было {before['total']}) · "
             f"знаков {final_snapshot['chars']} (было {before['chars']})")

        # ── ⑨ непрочитанное не уносится. После ⑥ архив пуст (возврат выше).
        set_test_reader(db, a_id)
        code9, output9 = call_tool(tool, db, "--apply")
        moved9 = archive_ids_of(db)
        above9 = sorted(i for i in moved9 if i > a_id)
        call_tool(tool, db, "--unfold", "--apply")
        case("⑨ непрочитанное хоть одной ролью не уносится; прочитанное ниже — уносится",
             code9 == 0 and a_id in moved9 and b_id not in moved9 and not above9
             and UNREAD_WORD in output9 and TEST_READER in output9,
             f"код {code9} · проверочный читатель дочитал до #{a_id}: A #{a_id} "
             f"{'унесена' if a_id in moved9 else 'НЕ унесена'} · B #{b_id} "
             f"{'УНЕСЕНА' if b_id in moved9 else 'на месте'} · унесено выше отметки: {len(above9)} · "
             f"«{UNREAD_WORD}» и держащий отметку названы: "
             f"{'да' if UNREAD_WORD in output9 and TEST_READER in output9 else 'НЕТ'}", differ=True)

        # ── ⑩ самопроверка: копия инструмента со сломанным отбором обязана отказать сама
        nofilter = stand / "messages-fold-nofilter.py"
        tool_text = tool.read_text(encoding="utf-8")
        filter_present = FILTER_LINE in tool_text
        nofilter.write_text(tool_text.replace(FILTER_LINE, "        if False:"), encoding="utf-8")
        archive_before10 = len(archive_ids_of(db))
        code10, output10 = call_tool(nofilter, db, "--apply")
        moved10 = archive_ids_of(db)
        if moved10:
            call_tool(tool, db, "--unfold", "--apply")
        set_test_reader(db, None)
        case("⑩ самопроверка по каждой роли ловит непрочитанное, даже если отбор сломан",
             code10 == 2 and "в отборе есть НЕПРОЧИТАННОЕ" in output10 and TEST_READER in output10
             and len(moved10) == archive_before10,
             f"код {code10} · отказ назван: "
             f"{'да' if 'в отборе есть НЕПРОЧИТАННОЕ' in output10 else 'НЕТ'} · унесено "
             f"{len(moved10) - archive_before10} (ждали 0)"
             f"{'' if filter_present or a.porcha == 'без-отметки' else ' · строка отбора не найдена ДОСЛОВНО: если её переписали равносильно — поправь FILTER_LINE в приёмке, инструмент может быть исправен'}"
             f"{' · отбор в инструменте уже без отметки (порча)' if a.porcha == 'без-отметки' else ''}",
             differ=True)

        # ── ⑪ контроль: строка самопроверки в холостом прогоне ① (две честные формы)
        with_marks = "непрочитанных в отборе: 0" in output1 and "держит отметка прочитанного" in output1
        no_marks = ("отметок прочитанного нет ни у одной роли" in output1
                    and "непрочитанных в отборе: не проверено" in output1)
        case("⑪ контроль: холостой прогон печатает самопроверку и кто держит отметку",
             with_marks or no_marks,
             f"строка самопроверки: {'есть' if 'непрочитанных в отборе' in output1 else 'НЕТ'} · "
             f"{'держащий отметку назван' if with_marks else 'отметок нет — сказано «не проверено»' if no_marks else 'держащий отметку НЕ назван'}")

        print("")
        print(f"ИТОГ: {GREENS} из {CASES} · различающих {DIFFER}")
        return 0 if GREENS == CASES else 1
    finally:
        shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
