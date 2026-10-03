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
  ⑦ адресаты унесённых: живая таблица теряет, вид видит                    РАЗЛИЧАЮЩИЙ
  ⑧ контроль: ни одна запись не пропала — сумма живых и архива постоянна

ПОРЧА (--porcha мерка-с-источником): отпечатку возвращают источник и порядок по нему.
ОЖИДАНИЕ, НАЗВАННОЕ ДО ПРОГОНА (и УТОЧНЁННОЕ после первого прогона — честно, вслух):
краснеют ДВА случая, ② и ⑦.
```
② обратимость ....... перенос откатывается сам, проверять обратимость не на чем
⑦ адресаты .......... стои́т НА СОСТОЯВШЕМСЯ переносе: если унесено ноль, живая таблица
                      и вид дают одно число, и разница исчезает
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["мерка-с-источником"])
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
            print("🧪 ПОРЧА «мерка-с-источником»: ждём красным РОВНО ② (обратимость), остальные целы\n")

        # 🩹 ДОГОН (карточка #667): своя фикстура ДО первого снимка — входит в оба снимка
        # одинаково, случаям ①/⑧ (неизменность/сохранность) всё равно, кто её завёл.
        seed_fixture(db)

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

        case("⑦ адресаты унесённых: живая таблица теряет, вид видит",
             view_join_count > live_join_count,
             f"через живую таблицу {live_join_count} · через вид {view_join_count} "
             f"(разница {view_join_count - live_join_count} — они и потерялись бы у читателя «только моё»)",
             differ=True)

        case("⑧ контроль: ни одна запись не пропала",
             final_snapshot["total"] == before["total"] and final_snapshot["chars"] == before["chars"],
             f"записей {final_snapshot['total']} (было {before['total']}) · "
             f"знаков {final_snapshot['chars']} (было {before['chars']})")

        print("")
        print(f"ИТОГ: {GREENS} из {CASES} · различающих {DIFFER}")
        return 0 if GREENS == CASES else 1
    finally:
        shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
