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
ПИСАТЕЛЬ = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "write-message.py"
МИГРАЦИЯ = HERE / "migrate-addressee-vnext.py"
ЧИТАТЕЛЬ = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "read-messages.py"
ЖИВАЯ = mezo_paths.live_db()
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def прогон(скрипт, *доводы):
    # PYTHONPATH на каталог инструментов: ослабленная копия миграции (случай ⑦в)
    # живёт во временной папке и без этого умерла бы на импорте mezo_paths —
    # а «упало на импорте» выглядит как «обратный ход показал красное», хотя
    # ослабления никто не проверял.
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [p for p in (str(HERE), env.get("PYTHONPATH", "")) if p])
    r = subprocess.run([sys.executable, str(скрипт), *доводы],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300, env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def адресаты(db, mid):
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    rows = con.execute("SELECT role, kind FROM message_addressee WHERE message_id=?"
                       " ORDER BY role", (mid,)).fetchall()
    con.close()
    return rows


def _есть_broadcast(con):
    return any(r[1] == "broadcast" for r in con.execute("PRAGMA table_info(messages)"))


def посеять(db):
    """Досеять в КОПИЮ то, что случай проверяет: склейку и обе формы «всем».

    ⚠️ Без посева случай зависел от того, мигрирована ли живая база СЕГОДНЯ, —
    то есть проверял не миграцию, а погоду. Сеем в копию: живой не касаемся.
    Ноты берём с broadcast=0 — пометив уже помеченную, прироста не получишь
    и проверка соврёт в зелёную сторону.
    """
    con = sqlite3.connect(db)
    условие = " WHERE COALESCE(broadcast,0)=0" if _есть_broadcast(con) else ""
    ноты = [r[0] for r in con.execute(
        f"SELECT id FROM messages{условие} ORDER BY id DESC LIMIT 3")]
    if len(ноты) < 3:
        con.close()
        raise SystemExit("⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: в копии меньше трёх пригодных записок,"
                         " сеять не на чем. Молчать об этом нельзя — вышло бы зелёное")
    склейка, all_, все_ = ноты
    for mid, роль in ((склейка, "CORE STUD"), (all_, "ALL"), (все_, "ВСЕ")):
        con.execute("INSERT OR REPLACE INTO message_addressee(message_id, role, kind,"
                    " linked_by) VALUES(?,?,?,'field')", (mid, роль, "to"))
    con.commit()
    con.close()
    return {"склейка": склейка, "all": all_, "все": все_}


def снять(db):
    """Величины ДО/ПОСЛЕ одной меркой — чтобы разность имела смысл."""
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    в = {}
    в["склеек"] = con.execute("SELECT COUNT(*) FROM message_addressee"
                              " WHERE role LIKE '% %' OR role IN ('ALL','ВСЕ')").fetchone()[0]
    if _есть_broadcast(con):
        в["всем"] = con.execute("SELECT COUNT(*) FROM messages"
                                " WHERE COALESCE(broadcast,0)=1").fetchone()[0]
        в["all_ноты"] = con.execute(
            "SELECT COUNT(DISTINCT message_id) FROM message_addressee"
            " WHERE role IN ('ALL','ВСЕ') AND message_id IN"
            " (SELECT id FROM messages WHERE COALESCE(broadcast,0)=0)").fetchone()[0]
    else:
        в["всем"] = 0
        в["all_ноты"] = con.execute(
            "SELECT COUNT(DISTINCT message_id) FROM message_addressee"
            " WHERE role IN ('ALL','ВСЕ')").fetchone()[0]
    в["чужие"] = con.execute("SELECT COUNT(*) FROM message_addressee"
                             " WHERE role NOT LIKE '% %'"
                             " AND role NOT IN ('ALL','ВСЕ')").fetchone()[0]
    con.close()
    return в


def main() -> int:
    ok = True
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-addr-"))
    try:
        db = d / "sand.db"
        shutil.copy(ЖИВАЯ, db)
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
        зерно = посеять(db)
        до = снять(db)

        # ⑦а МИГРАЦИЯ — сперва: писатель требует колонку broadcast.
        код, вывод = прогон(МИГРАЦИЯ, "--db", str(db))
        после = снять(db)
        прирост = после["всем"] - до["всем"]
        поимённо = {роль for роль, _ in адресаты(db, зерно["склейка"])}
        ok &= case("⑦а миграция: склейки разведены поимённо, «всем» приросло ровно на число"
                   " нот ALL, чужие строки не убыли",
                   код == 0 and до["склеек"] > 0 and после["склеек"] == 0
                   and прирост == до["all_ноты"] and до["all_ноты"] > 0
                   and {"CORE", "STUD"} <= поимённо
                   and после["чужие"] >= до["чужие"],
                   f"код {код}; склеек {до['склеек']}→{после['склеек']} ·"
                   f" нот ALL было {до['all_ноты']}, «всем» {до['всем']}→{после['всем']}"
                   f" (прирост {прирост}) · чужих {до['чужие']}→{после['чужие']} ·"
                   f" из склейки легли: {sorted(поимённо)}", differ=True)

        # ⑦б идемпотентность: второй прогон ничего не меняет и не падает.
        код2, вывод2 = прогон(МИГРАЦИЯ, "--db", str(db))
        ok &= case("⑦б повторная миграция — идемпотентна",
                   код2 == 0 and "уже есть" in вывод2 and "склеек нет" in вывод2,
                   f"код {код2}; миграция, падающая на втором прогоне, учит бояться прогонов",
                   differ=True)

        # ⑦в ОБРАТНЫЙ ХОД: ослабляем РОВНО ту ветку, которую стережёт ⑦а, — пометку
        # «всем». Без него ⑦а доказывает лишь, что числа сошлись, а не что их что-то
        # держит: прежняя редакция ⑦а сошлась бы и с выключенной пометкой, потому что
        # сравнивала абсолют с абсолютом.
        db2 = d / "sand-reverse.db"
        shutil.copy(ЖИВАЯ, db2)
        посеять(db2)
        до2 = снять(db2)
        текст_миграции = МИГРАЦИЯ.read_text(encoding="utf-8")
        КУСОК = 'con.execute("UPDATE messages SET broadcast=1 WHERE id=?", (mid,))'
        if текст_миграции.count(КУСОК) != 1:
            ok &= case("⑦в ОБРАТНЫЙ ХОД: ослабить пометку «всем»", False,
                       f"⛔ строка пометки найдена {текст_миграции.count(КУСОК)} раз —"
                       " ослабление НЕ состоялось. Молчание тут читалось бы как успех:"
                       " обратный ход, который нельзя заставить сработать, — украшение",
                       differ=True)
        else:
            слабая = d / "migrate-weak.py"
            слабая.write_text(текст_миграции.replace(КУСОК, "pass  # ОСЛАБЛЕНО приёмкой ⑦в"),
                              encoding="utf-8")
            код3, _ = прогон(слабая, "--db", str(db2))
            после2 = снять(db2)
            прирост2 = после2["всем"] - до2["всем"]
            ok &= case("⑦в ОБРАТНЫЙ ХОД: пометка «всем» выключена → ⑦а обязана покраснеть",
                       код3 == 0 and до2["all_ноты"] > 0 and прирост2 != до2["all_ноты"],
                       f"код {код3}; ждали прирост {до2['all_ноты']}, получили {прирост2}"
                       " — эта разница и есть то, что стережёт ⑦а", differ=True)

        # ① пробелы — разделитель.
        код, вывод = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р1", "--to", "COORD CORE STUD")
        mid = int(вывод.split("#")[1].split()[0]) if "OK #" in вывод else 0
        rows = адресаты(db, mid) if mid else []
        ok &= case("① «COORD CORE STUD» через пробел → ТРИ строки поля, склейки нет",
                   код == 0 and len(rows) == 3 and all(" " not in r for r, _ in rows),
                   f"код {код}; строки: {rows} — живой писатель здесь молча клал ОДНУ склейку",
                   differ=True)

        # ② запятая — как раньше.
        код, вывод = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р1-контроль", "--to", "COORD,CORE")
        mid = int(вывод.split("#")[1].split()[0]) if "OK #" in вывод else 0
        ok &= case("② «COORD,CORE» через запятую → две строки",
                   код == 0 and len(адресаты(db, mid)) == 2,
                   f"код {код}; прежняя форма не сломана — иначе починка учит новой беде",
                   differ=True)

        # ③ неизвестное имя — отказ ДО записи.
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        нот_перед = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        con.close()
        код3, вывод3 = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                              "--body", "проба Р3", "--to", "COODR")
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        нот_зaписано = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        con.close()
        ok &= case("③ имя «COODR» (опечатка) → ОТКАЗ до записи, словарь назван, записки НЕТ",
                   код3 == 5 and "ОТКАЗ" in вывод3 and "Словарь:" in вывод3
                   and нот_зaписано == нот_перед,
                   f"код {код3}; нота-призрак не родилась: было {нот_перед} нот, осталось столько же",
                   differ=True)

        # ④ «все» — свойство записки.
        код, вывод = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                            "--body", "проба Р4", "--to", "все", "--cc", "ВЛАДЕЛЕЦ")
        mid = int(вывод.split("#")[1].split()[0]) if "OK #" in вывод else 0
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        bc = con.execute("SELECT broadcast FROM messages WHERE id=?", (mid,)).fetchone()
        все_строкой = con.execute("SELECT COUNT(*) FROM message_addressee WHERE message_id=?"
                                  " AND role IN ('ВСЕ','ALL')", (mid,)).fetchone()[0]
        con.close()
        ok &= case("④ «--to все» → broadcast=1 у записки, строки-адресата «ВСЕ» нет",
                   код == 0 and bc and bc[0] == 1 and все_строкой == 0,
                   f"код {код}; «всем» — свойство ноты; ВЛАДЕЛЕЦ лёг строкой: {адресаты(db, mid)}",
                   differ=True)

        # ⑤ живой читатель на мигрированной песочнице.
        код5, вывод5 = прогон(ЧИТАТЕЛЬ, "--db", str(db), "--role", "CORE", "--to-me")
        ok &= case("⑤ живой read-messages --to-me на песочнице: не падает, «всем»-ноту не выдаёт",
                   код5 == 0 and "проба Р4" not in вывод5,
                   f"код {код5}; новая колонка не ломает читателя, широковещательное"
                   " не выдаётся за личное", differ=True)

        # ⑥ ОБРАТНЫЙ ХОД: словарь отключён → случай ③ зеленеет у сломанной.
        цел = ПИСАТЕЛЬ.read_text(encoding="utf-8")
        поломка = цел.replace("if r not in словарь:", "if False:", 1)
        if поломка == цел:
            ok &= case("⑥ ОБРАТНЫЙ ХОД: словарь отключён", False,
                       "⛔ НЕ ЗАПУСТИЛСЯ: якоря словаря в писателе нет — он менялся, правь приёмку")
        else:
            слаб = d / "прежний.py"
            слаб.write_text(поломка, encoding="utf-8")
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
                       PYTHONPATH=str(ПИСАТЕЛЬ.parent))
            r6 = subprocess.run([sys.executable, str(слаб), "--db", str(db), "--role",
                                 "PROTO", "--body", "проба Р3 слабой", "--to", "COODR"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=300, env=env)
            код6 = r6.returncode
            _хвост = ((r6.stdout or "") + (r6.stderr or "")).strip().splitlines()
            _почему = _хвост[0][:90] if _хвост else "(молча)"
            # ⚠️ Печатаем ПРИЧИНУ отказа слабой копии. Без неё «слабая тоже отказала»
            # читается как работа словаря, хотя копия могла умереть на чём угодно —
            # и тогда обратный ход доказывает не то, ради чего заведён.
            ok &= case("⑥ ОБРАТНЫЙ ХОД: словарь отключён — случай ③ ЗЕЛЕНЕЕТ у сломанной",
                       код6 == 0 and код3 == 5,
                       f"слабая {код6} против настоящей {код3} — различает именно СЛОВАРЬ."
                       f" Слабая сказала: {_почему}",
                       differ=True)
        def сколько_нот(_db):
            _c = sqlite3.connect(f"file:{pathlib.Path(_db).as_posix()}?mode=ro", uri=True)
            n = _c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
            _c.close()
            return n

        # ⑧ Э-Г: critical без основания — отказ ДО записи, нот не прибыло.
        было8 = сколько_нот(db)
        код8, вывод8 = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                              "--body", "проба Э-Г критик", "--priority", "critical")
        ok &= case("⑧ critical БЕЗ --basis → отказ, записки НЕТ, отказ учит (high не требует)",
                   код8 == 4 and сколько_нот(db) == было8
                   and "это high" in вывод8 and "--basis" in вывод8,
                   f"код {код8}; нот было {было8}, стало {сколько_нот(db)}; замер в отказе:"
                   " 86 из 89 живых critical основание уже несли", differ=True)

        # ⑨ Э-Г: critical с основанием — записан, основание первой строкой тела.
        код9, вывод9 = прогон(ПИСАТЕЛЬ, "--db", str(db), "--role", "PROTO",
                              "--body", "проба Э-Г критик два", "--priority", "critical",
                              "--basis", "слово владельца 26.08 13:58 UTC")
        import sqlite3 as _sq
        _c = _sq.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
        тело9 = _c.execute("SELECT body_md FROM messages WHERE writer_role='PROTO'"
                           " ORDER BY id DESC LIMIT 1").fetchone()[0]
        _c.close()
        ok &= case("⑨ critical С --basis → записан, основание ПЕРВОЙ строкой тела",
                   код9 == 0 and тело9.startswith("[основание critical: слово владельца"),
                   f"код {код9}; первая строка: {тело9.splitlines()[0][:70]}", differ=True)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ СЛОВАРЬ АДРЕСАТОВ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES},"
          f" различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
