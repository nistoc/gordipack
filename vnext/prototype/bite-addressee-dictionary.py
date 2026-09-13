# -*- coding: utf-8 -*-
r"""ПРИЁМКА словаря адресатов Э-Б (писатель-прототип + миграция) — карточка #258.

🩸 ЧЕМ ОПЛАЧЕНО (замер живого поля 26.08): писатель делит имена только по запятой —
8 склеек «CHROME CORE STUD» одной строкой лежат в живом поле, и отбор «только моё»
эти записки не показывает НИКОМУ из склеенных; 25 строк «ALL» — самодельный обход
отсутствующего «всем», невидимый для --to-me. Молчащий отказ читался как успех.

Песочница = КОПИЯ ЖИВОЙ базы (см. 08-addressee-dictionary.md Р4½: схема Э-В адресата
не знает, прототип обязан жить в форме, в которой дефект существует).

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① «A B C» через ПРОБЕЛ → три строки поля, склейки нет                 РАЗЛИЧАЮЩИЙ
  ② «A,B» через запятую → две строки                                    КОНТРОЛЬ
  ③ неизвестное имя → ОТКАЗ ДО записи, словарь назван, записки НЕТ      РАЗЛИЧАЮЩИЙ
  ④ «все» → свойство записки (broadcast=1), строки-адресата нет         РАЗЛИЧАЮЩИЙ
  ⑤ живой ЧИТАТЕЛЬ на мигрированной песочнице: --to-me широковещательную
    НЕ показывает и НЕ падает от новой колонки                          РАЗЛИЧАЮЩИЙ
  ⑥ ОБРАТНЫЙ ХОД: словарь отключён → случай ③ зеленеет у сломанной      РАЗЛИЧАЮЩИЙ
  ⑦а МИГРАЦИЯ на копии живой С ПОСЕВОМ: склейки разведены поимённо,
    «всем» ПРИРОСЛО ровно на число нот ALL, чужие строки не убыли       РАЗЛИЧАЮЩИЙ
  ⑦б повторный прогон миграции идемпотентен                             РАЗЛИЧАЮЩИЙ
  ⑦в ОБРАТНЫЙ ХОД: пометка «всем» выключена → ⑦а краснеет               РАЗЛИЧАЮЩИЙ
  ⑧ Э-Г (карточка #260): critical БЕЗ основания → отказ, записки НЕТ    РАЗЛИЧАЮЩИЙ
  ⑨ Э-Г: critical С основанием → записан, основание ПЕРВОЙ строкой      КОНТРОЛЬ

⛔ Живой базы не пишет: всё — на копии.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
# ⚡ ПЕРЕНАЦЕЛЕНО НА ЖИВОГО ПИСАТЕЛЯ 2026-08-27 (карточка #258, вторая половина сдана):
# словарь адресатов перенесён из прототипа в живой инструмент, и приёмка обязана
# испытывать ТО, ЧТО РАБОТАЕТ, а не то, что было черновиком. Прототип остаётся в дереве
# как история решения; гонять его дальше значило бы проверять копию вместо продукта.
WRITER = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "write-message.py"
MIGRATION = HERE / "migrate-addressee-vnext.py"
READER = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "read-messages.py"
LIVE_DB = mezo_paths.live_db()
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def run_tool(script, *args):
    # PYTHONPATH на каталог инструментов: ослабленная копия миграции (случай ⑦в)
    # живёт во временной папке и без этого умерла бы на импорте mezo_paths —
    # а «упало на импорте» выглядит как «обратный ход показал красное», хотя
    # ослабления никто не проверял.
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [p for p in (str(HERE), env.get("PYTHONPATH", "")) if p])
    r = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def addressees(db, mid):
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    rows = con.execute("SELECT role, kind FROM message_addressee WHERE message_id=?"
                       " ORDER BY role", (mid,)).fetchall()
    con.close()
    return rows


def _has_broadcast(con):
    return any(r[1] == "broadcast" for r in con.execute("PRAGMA table_info(messages)"))


def seed_rows(db):
    """Досеять в КОПИЮ то, что случай проверяет: склейку и обе формы «всем».

    ⚠️ Без посева случай зависел от того, мигрирована ли живая база СЕГОДНЯ, —
    то есть проверял не миграцию, а погоду. Сеем в копию: живой не касаемся.
    Ноты берём с broadcast=0 — пометив уже помеченную, прироста не получишь
    и проверка соврёт в зелёную сторону.
    """
    con = sqlite3.connect(db)
    condition = " WHERE COALESCE(broadcast,0)=0" if _has_broadcast(con) else ""
    notes = [r[0] for r in con.execute(
        f"SELECT id FROM messages{condition} ORDER BY id DESC LIMIT 3")]
    if len(notes) < 3:
        con.close()
        raise SystemExit("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: в копии меньше трёх пригодных записок,"
                         " сеять не на чем. Молчать об этом нельзя — вышло бы зелёное")
    glued_note, all_, vse_note = notes
    for mid, role in ((glued_note, "CORE STUD"), (all_, "ALL"), (vse_note, "ВСЕ")):
        con.execute("INSERT OR REPLACE INTO message_addressee(message_id, role, kind,"
                    " linked_by) VALUES(?,?,?,'field')", (mid, role, "to"))
    con.commit()
    con.close()
    return {"glued": glued_note, "all": all_, "vse": vse_note}


def measure(db):
    """Величины ДО/ПОСЛЕ одной меркой — чтобы разность имела смысл."""
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    values = {}
    values["склеек"] = con.execute("SELECT COUNT(*) FROM message_addressee"
                              " WHERE role LIKE '% %' OR role IN ('ALL','ВСЕ')").fetchone()[0]
    if _has_broadcast(con):
        values["всем"] = con.execute("SELECT COUNT(*) FROM messages"
                                " WHERE COALESCE(broadcast,0)=1").fetchone()[0]
        values["all_ноты"] = con.execute(
            "SELECT COUNT(DISTINCT message_id) FROM message_addressee"
            " WHERE role IN ('ALL','ВСЕ') AND message_id IN"
            " (SELECT id FROM messages WHERE COALESCE(broadcast,0)=0)").fetchone()[0]
    else:
        values["всем"] = 0
        values["all_ноты"] = con.execute(
            "SELECT COUNT(DISTINCT message_id) FROM message_addressee"
            " WHERE role IN ('ALL','ВСЕ')").fetchone()[0]
    values["чужие"] = con.execute("SELECT COUNT(*) FROM message_addressee"
                             " WHERE role NOT LIKE '% %'"
                             " AND role NOT IN ('ALL','ВСЕ')").fetchone()[0]
    con.close()
    return values


def main() -> int:
    ok = True
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-addr-"))
    try:
        db = d / "sand.db"
        shutil.copy(LIVE_DB, db)
        # 🩸 ПОЧИНЕНО 2026-08-27 09:02 UTC (замер @COORD, записка #3926 §③⑥). Прежняя
        # редакция ⑦а НАДЕЯЛАСЬ на состояние живой базы: ждала «склеек до > 0» и
        # «всем ПОСЛЕ = числу нот ALL ДО». Оба ожидания были верны ровно до того часа,
        # когда живую МИГРИРОВАЛИ моей же рукой (26.08 21:22 UTC): в копии склеек стало 0,
        # а «всем» пришло уже равным 28 — и случай покраснел НАВСЕГДА, при исправной
        # миграции. Сторож, кричащий на исправном, учит не слышать крик.
        # Починка тройная, и третье нашлось попутно:
        #   ① случай СЕЕТ сам то, что проверяет, вместо надежды на чужое состояние;
        #   ② «всем» меряется ПРИРОСТОМ, а не абсолютом — прирост не зависит от того,
        #      мигрирована живая или нет, и потому переживает собственную починку;
        #   ③ подпись обещала «чужого не убыло», а величины чужие_до/чужие_после
        #      СНИМАЛИСЬ И НЕ СРАВНИВАЛИСЬ НИ РАЗУ — обещание без проверки читается
        #      как проверка, причём снятая величина рядом делает вид, что она сверена.
        seed = seed_rows(db)
        before = measure(db)

        # ⑦а МИГРАЦИЯ — сперва: писатель требует колонку broadcast.
        code, output = run_tool(MIGRATION, "--db", str(db))
        after = measure(db)
        growth = after["всем"] - before["всем"]
        by_name = {role for role, _ in addressees(db, seed["glued"])}
        ok &= case("⑦а миграция: склейки разведены поимённо, «всем» приросло ровно на число"
                   " нот ALL, чужие строки не убыли",
                   code == 0 and before["склеек"] > 0 and after["склеек"] == 0
                   and growth == before["all_ноты"] and before["all_ноты"] > 0
                   and {"CORE", "STUD"} <= by_name
                   and after["чужие"] >= before["чужие"],
                   f"код {code}; склеек {before['склеек']}→{after['склеек']} ·"
                   f" нот ALL было {before['all_ноты']}, «всем» {before['всем']}→{after['всем']}"
                   f" (прирост {growth}) · чужих {before['чужие']}→{after['чужие']} ·"
                   f" из склейки легли: {sorted(by_name)}", differ=True)

        # ⑦б идемпотентность: второй прогон ничего не меняет и не падает.
        code2, output2 = run_tool(MIGRATION, "--db", str(db))
        ok &= case("⑦б повторная миграция — идемпотентна",
                   code2 == 0 and "уже есть" in output2 and "склеек нет" in output2,
                   f"код {code2}; миграция, падающая на втором прогоне, учит бояться прогонов",
                   differ=True)

        # ⑦в ОБРАТНЫЙ ХОД: ослабляем РОВНО ту ветку, которую стережёт ⑦а, — пометку
        # «всем». Без него ⑦а доказывает лишь, что числа сошлись, а не что их что-то
        # держит: прежняя редакция ⑦а сошлась бы и с выключенной пометкой, потому что
        # сравнивала абсолют с абсолютом.
        db2 = d / "sand-reverse.db"
        shutil.copy(LIVE_DB, db2)
        seed_rows(db2)
        before2 = measure(db2)
        migration_text = MIGRATION.read_text(encoding="utf-8")
        CHUNK = 'con.execute("UPDATE messages SET broadcast=1 WHERE id=?", (mid,))'
        if migration_text.count(CHUNK) != 1:
            ok &= case("⑦в ОБРАТНЫЙ ХОД: ослабить пометку «всем»", False,
                       f"⛔ строка пометки найдена {migration_text.count(CHUNK)} раз —"
                       " ослабление НЕ состоялось. Молчание тут читалось бы как успех:"
                       " обратный ход, который нельзя заставить сработать, — украшение",
                       differ=True)
        else:
            weak_copy = d / "migrate-weak.py"
            weak_copy.write_text(migration_text.replace(CHUNK, "pass  # ОСЛАБЛЕНО приёмкой ⑦в"),
                              encoding="utf-8")
            code3, _ = run_tool(weak_copy, "--db", str(db2))
            after2 = measure(db2)
            growth2 = after2["всем"] - before2["всем"]
            ok &= case("⑦в ОБРАТНЫЙ ХОД: пометка «всем» выключена → ⑦а обязана покраснеть",
                       code3 == 0 and before2["all_ноты"] > 0 and growth2 != before2["all_ноты"],
                       f"код {code3}; ждали прирост {before2['all_ноты']}, получили {growth2}"
                       " — эта разница и есть то, что стережёт ⑦а", differ=True)

        # ① пробелы — разделитель.
        code, output = run_tool(WRITER, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р1", "--to", "COORD CORE STUD")
        mid = int(output.split("#")[1].split()[0]) if "OK #" in output else 0
        rows = addressees(db, mid) if mid else []
        ok &= case("① «COORD CORE STUD» через пробел → ТРИ строки поля, склейки нет",
                   code == 0 and len(rows) == 3 and all(" " not in r for r, _ in rows),
                   f"код {code}; строки: {rows} — живой писатель здесь молча клал ОДНУ склейку",
                   differ=True)

        # ② запятая — как раньше.
        code, output = run_tool(WRITER, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р1-контроль", "--to", "COORD,CORE")
        mid = int(output.split("#")[1].split()[0]) if "OK #" in output else 0
        ok &= case("② «COORD,CORE» через запятую → две строки",
                   code == 0 and len(addressees(db, mid)) == 2,
                   f"код {code}; прежняя форма не сломана — иначе починка учит новой беде",
                   differ=True)

        # ③ неизвестное имя — отказ ДО записи.
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        notes_before = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        con.close()
        code3, output3 = run_tool(WRITER, "--db", str(db), "--role", "PROTO",
                              "--body", "проба Р3", "--to", "COODR")
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        notes_written = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        con.close()
        ok &= case("③ имя «COODR» (опечатка) → ОТКАЗ до записи, словарь назван, записки НЕТ",
                   code3 == 5 and "ОТКАЗ" in output3 and "Словарь:" in output3
                   and notes_written == notes_before,
                   f"код {code3}; нота-призрак не родилась: было {notes_before} нот, осталось столько же",
                   differ=True)

        # ④ «все» — свойство записки.
        code, output = run_tool(WRITER, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р4", "--to", "все", "--cc", "ВЛАДЕЛЕЦ")
        mid = int(output.split("#")[1].split()[0]) if "OK #" in output else 0
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        bc = con.execute("SELECT broadcast FROM messages WHERE id=?", (mid,)).fetchone()
        broadcast_rows = con.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id=?"
                                  " AND role IN ('ВСЕ','ALL')", (mid,)).fetchone()[0]
        con.close()
        ok &= case("④ «--to все» → broadcast=1 у записки, строки-адресата «ВСЕ» нет",
                   code == 0 and bc and bc[0] == 1 and broadcast_rows == 0,
                   f"код {code}; «всем» — свойство ноты; ВЛАДЕЛЕЦ лёг строкой: {addressees(db, mid)}",
                   differ=True)

        # ⑤ живой читатель на мигрированной песочнице.
        code5, output5 = run_tool(READER, "--db", str(db), "--role", "CORE", "--to-me")
        ok &= case("⑤ живой read-messages --to-me на песочнице: не падает, «всем»-ноту не выдаёт",
                   code5 == 0 and "проба Р4" not in output5,
                   f"код {code5}; новая колонка не ломает читателя, широковещательное"
                   " не выдаётся за личное", differ=True)

        # ⑥ ОБРАТНЫЙ ХОД: словарь отключён → случай ③ зеленеет у сломанной.
        original_text = WRITER.read_text(encoding="utf-8")
        # ⚠️ ЯКОРЬ ОБНОВЛЁН 27.08 (работа по карточке #330): в писателе появилось различение
        # живых и ЗАКРЫТЫХ ролей, и переменная «словарь» стала «живые». Приёмка сказала об
        # этом вслух — «якоря нет, он менялся, правь приёмку» — вместо того чтобы зазеленеть
        # на непроверенной ветке. Ровно так обратный ход и обязан себя вести.
        break_patch = original_text.replace("if r not in alive_roles:", "if False:", 1)
        if break_patch == original_text:
            ok &= case("⑥ ОБРАТНЫЙ ХОД: словарь отключён", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря словаря в писателе нет — он менялся, правь приёмку")
        else:
            weak_path = d / "прежний.py"
            weak_path.write_text(break_patch, encoding="utf-8")
            shutil.copy(HERE / "mezo_paths.py", d / "mezo_paths.py")
            # копия живёт вне контейнера ⇒ live_db() в её заголовке не найдёт маркера;
            # контейнер отдаём средой — иначе копия падает НА ИМПОРТЕ, и «красный»
            # у сломанной был бы смертью копии, а не работой словаря (поймано прогоном)
            # PYTHONPATH на каталог ЖИВОГО писателя: он импортирует соседей (dryrun,
            # urgency, refs_check…), которых во временном каталоге нет. Без этого копия
            # умирает НА ИМПОРТЕ — и её ненулевой код читался бы как «словарь сработал».
            # 🩸 Ровно это и вышло при первом прогоне после переноса: обратный ход был
            # зелёным по виду и пустым по существу, пока случай не начал печатать ПРИЧИНУ.
            env = dict(os.environ, MEZO_CONTAINER=str(mezo_paths.container_root(__file__)),
                       PYTHONPATH=str(WRITER.parent))
            r6 = subprocess.run([sys.executable, str(weak_path), "--db", str(db), "--role",
                                 "PROTO", "--body", "проба Р3 слабой", "--to", "COODR"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=300, env=env)
            code6 = r6.returncode
            _tail = ((r6.stdout or "") + (r6.stderr or "")).strip().splitlines()
            _why = _tail[0][:90] if _tail else "(молча)"
            # ⚠️ Печатаем ПРИЧИНУ отказа слабой копии. Без неё «слабая тоже отказала»
            # читается как работа словаря, хотя копия могла умереть на чём угодно —
            # и тогда обратный ход доказывает не то, ради чего заведён.
            ok &= case("⑥ ОБРАТНЫЙ ХОД: словарь отключён — случай ③ ЗЕЛЕНЕЕТ у сломанной",
                       code6 == 0 and code3 == 5,
                       f"слабая {code6} против настоящей {code3} — различает именно СЛОВАРЬ."
                       f" Слабая сказала: {_why}",
                       differ=True)
        def notes_count(_db):
            _c = sqlite3.connect(f"file:{pathlib.Path(_db).as_posix()}?mode=ro", uri=True)
            n = _c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            _c.close()
            return n

        # ⑧ Э-Г: critical без основания — отказ ДО записи, нот не прибыло.
        before8 = notes_count(db)
        code8, output8 = run_tool(WRITER, "--db", str(db), "--role", "PROTO",
                              "--body", "проба Э-Г критик", "--priority", "critical")
        ok &= case("⑧ critical БЕЗ --basis → отказ, записки НЕТ, отказ учит (high не требует)",
                   code8 == 4 and notes_count(db) == before8
                   and "это high" in output8 and "--basis" in output8,
                   f"код {code8}; нот было {before8}, стало {notes_count(db)}; замер в отказе:"
                   " 86 из 89 живых critical основание уже несли", differ=True)

        # ⑨ Э-Г: critical с основанием — записан, основание первой строкой тела.
        code9, output9 = run_tool(WRITER, "--db", str(db), "--role", "PROTO",
                              "--body", "проба Э-Г критик два", "--priority", "critical",
                              "--basis", "слово владельца 26.08 13:58 UTC")
        import sqlite3 as _sq
        _c = _sq.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
        body9 = _c.execute("SELECT body_md FROM messages WHERE writer_role='PROTO'"
                           " ORDER BY id DESC LIMIT 1").fetchone()[0]
        _c.close()
        ok &= case("⑨ critical С --basis → записан, основание ПЕРВОЙ строкой тела",
                   code9 == 0 and body9.startswith("[основание critical: слово владельца"),
                   f"код {code9}; первая строка: {body9.splitlines()[0][:70]}", differ=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ СЛОВАРЬ АДРЕСАТОВ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
