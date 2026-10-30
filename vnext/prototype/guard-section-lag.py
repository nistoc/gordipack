# -*- coding: utf-8 -*-
"""guard-section-lag.py — признак «секция слепка отстала от собственной работы роли».

ОТКУДА ВЗЯЛСЯ. Предложен @opssre (#3043) после того, как контур за час поймал троих подряд:
у одной роли работа лежала на диске без записи, у второй — девять правок безопасности мимо
слепка, у третьей план не правился ДЕСЯТЬ СУТОК. Цепочка сработала на трёх случайностях,
а не на механизме.

🔴 ГЛАВНОЕ, И ЭТО ЗАМЕР, А НЕ ПРЕДПОЛОЖЕНИЕ (2026-08-06 17:01 UTC):
   Признак свежести слепков в общем прогоне УЖЕ ЕСТЬ — и он слеп к этому случаю по построению.
   Он берёт `MAX(saved_at)` ПО ВСЕЙ РОЛИ, поэтому сохранение ОДНОЙ секции гасит его для ВСЕХ:
       гард показывает +0 ч ....... у четырёх ролей
       план на самом деле ......... +18 ч · +247 ч · +228 ч · +19 ч
   ⇒ Это не «признака нет», а **признак, ослепший через агрегацию**: он отработал и честно
     вернул «чисто» по той величине, которую видел. Родня класса «проверка, ослепшая на части
     входа, зелена так же, как ничего не нашедшая» (свод §7.5).

⚠️ ПОЧЕМУ НЕ ВСЕ СЕКЦИИ РАВНЫ — иначе признак станет фоном за сутки.
   Секции живут в РАЗНОМ темпе по своей природе, и мерить их одной меркой значит красить
   вечно. Замер по себе 17:03: state и plan свежие, а identity/history/launcher/rebirth/sources —
   246–270 часов, и это НОРМА: они меняются при смене устройства работы, а не при каждой смене.
       state · plan ........ БЫСТРЫЕ. Обязаны следовать за работой ⇒ проверяются здесь
       rebirth · launcher .. ИСПОЛНЯЕМЫЕ. Их протухание ловит другой признак —
                             guard-stale-commands (команда старше правки инструмента)
       identity · history .. МЕДЛЕННЫЕ по природе. По времени не проверяются вовсе

⚪ ПУСТОТА — ПО ПРИЧИНЕ, А НЕ УГАДЫВАНИЕМ «НОВОРОЖДЁННОСТИ» (карточка #606, 2026-09-13).
   Нечего сверить бывает по ДВУМ разным причинам, и красить их одним отказом — ложная тревога
   на КАЖДОМ свежесобранном контуре (bite-fresh-circuit.py, случай ⑦: два красных на пустом
   месте учат пролистывать красное вообще).
       лента (messages_all) ПУСТА ВООБЩЕ ..... ⚪ ни одна роль ещё не писала — отставать
                                                нечему, это честный свежий контур, код 0
       лента НЕ пуста, а сверить нечего ....... прежний отказ ДОСЛОВНО — это пропажа
                                                памяти, а не рождение контура, код 2

🪤 МЕРИЛ РИТУАЛ, А НАЗЫВАЛ РЕЗУЛЬТАТ (issue #38 пакета, 2026-10-28). Отставание считалось от
   ЛЮБОЙ записки роли и от saved_at. Контур-потребитель после шести дней тишины получил пять
   провалов: три роли ответили на опрос координатора — и только. Содержание разделов проверка
   не смотрит, а называла это «секция отстала от того, что роль успела сделать». Красное гасило
   пересохранение неизменного текста, а честное «перечитал, правок нет» (--confirm) — не гасило.
   ⇒ Теперь две меры, обе из общей функции phoenix_lag.section_lag() рабочего каталога:
       🔴 раздел отстал от СМЕНЫ СОСТОЯНИЯ — записки с commit (или sha), «словом владельца»,
          закрытием карточки своей рукой, числами замера позже сохранения или подтверждения
          раздела. Только это даёт код 1
       🟡 раздел не подтверждался после записки — записки без этих признаков. Код не меняет;
          строка несёт путь «перечитал, правок нет»: save-phoenix.py --confirm
   Обе меры считаются от COALESCE(confirmed_at, saved_at): подтверждение — честный взгляд.
   🟡 печатается не со знаком ⚠️ нарочно: общий прогон пробрасывает строки ⚠️ и ℹ️, а у него
   есть своя строка-предупреждение «память ПО РАЗДЕЛАМ» о том же — дважды одно и то же было бы шумом.

    python guard-section-lag.py                 # весь контур
    python guard-section-lag.py --role PROTO
    python guard-section-lag.py --selftest
"""
import argparse
import contextlib
import importlib.util
import io
import os
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

DB = mezo_paths.live_db()
FAST_SECTIONS = ("state", "plan")


# Без этих имён phoenix_lag.py — прежний (до issue #38): проверка упала бы трассировкой на первом вызове.
LAG_NAMES = ("section_lag", "LAG_HOURS", "STATE_CHANGE_NAMES")


def _lag_places():
    """Где искать phoenix_lag.py, по порядку: MEZO_SCRIPTS_ROOT (испытуемая копия) · рядом с этим
    файлом (собранный контур) · рабочий каталог контура · scripts/ пакета (vnext/prototype → ../../scripts)."""
    here = Path(__file__).resolve().parent
    places = []
    if os.environ.get("MEZO_SCRIPTS_ROOT"):
        places.append(Path(os.environ["MEZO_SCRIPTS_ROOT"]))
    places.append(here)
    try:
        places.append(mezo_paths.live_scripts())
    except SystemExit:
        pass
    places.append(here.parent.parent / "scripts")
    return places


def _load_lag(places=None):
    """Общая функция отставания — phoenix_lag.py рабочего каталога, а не своя копия разбора:
    две копии признаков смены состояния разъехались бы при первой правке.

    Берётся первое место, где phoenix_lag.py есть И несёт section_lag (LAG_NAMES). Прежний файл
    без неё пропускается, а не берётся: так бывает, когда проверку из клона зовут против контура,
    ещё не обновлённого, или когда установка не тронула phoenix_lag.py, помеченный «✋ правлен у тебя»
    (замечание приёмки PR 56: раньше здесь была трассировка AttributeError с кодом 1).
    → (модуль, путь, [(путь, почему пропущен)…]) или (None, None, [(место, что там)…]).

    Одно место, пришедшее разным написанием (полное имя и короткое 8.3, «x/..» в пути), проверяется
    и называется один раз: места сравниваются по resolve(), печатаются как пришли (замечание приёмки
    PR 56, записка #6086 — у собранного контура «рядом с проверкой» и «рабочий каталог контура»
    стояли в перечне отказа дважды).
    """
    seen = []
    tried = set()
    for place in (_lag_places() if places is None else places):
        try:
            key = os.path.normcase(str(Path(place).resolve()))
        except OSError:   # путь, который система не раскрывает, — сравниваем как написан
            key = os.path.normcase(os.path.abspath(str(place)))
        if key in tried:
            continue
        tried.add(key)
        path = place / "phoenix_lag.py"
        if not path.exists():
            seen.append((place, "нет файла"))
            continue
        try:
            spec = importlib.util.spec_from_file_location("phoenix_lag", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as error:   # чужая поломка файла — тоже «не годится», а не трассировка
            seen.append((path, f"есть, но не загрузился: {type(error).__name__}"))
            continue
        absent = [name for name in LAG_NAMES if not hasattr(module, name)]
        if absent:
            seen.append((path, f"есть, но без {', '.join(absent)} (прежний)"))
            continue
        return module, path, seen
    return None, None, seen


def measure(con, lag, role=None):
    """Список (роль, секция, словарь lag.section_lag() или None — секции нет).

    Сравниваем с ПОСЛЕДНЕЙ НОТОЙ роли, а не с текущим временем: роль в дормане молчит
    по слову владельца, её слепок совпал с её работой и честен. Уснувшую роль будить нечем.
    """
    q = "SELECT DISTINCT role FROM phoenix"
    args = []
    if role:
        q += " WHERE UPPER(role) = UPPER(?)"
        args.append(role)
    out = []
    for (r,) in con.execute(q, args).fetchall():
        note = con.execute(
            # ⚡ Вид: роль, писавшая давно, не должна выглядеть «никогда не писавшей» после переноса.
            "SELECT MAX(timestamp) FROM messages_all WHERE UPPER(writer_role) = UPPER(?)",
            (r,)).fetchone()[0]
        if not note:
            continue
        for sec in FAST_SECTIONS:
            out.append((r, sec, lag.section_lag(con, r, sec)))
    return out


def run(role=None, db_path=DB, places=None):
    p = Path(db_path)
    if not p.exists():
        print(f"⛔ ОТКАЗ: базы нет — {p}")
        return 2
    lag, where, seen = _load_lag(places)
    if lag is None:
        print("⛔ ОТКАЗ: общей функции отставания (phoenix_lag.py с section_lag) нет ни в одном из мест: "
              + " · ".join(f"{x.as_posix()} — {why}" for x, why in seen)
              + " — без неё отставание не посчитано, и это не «отставших нет»")
        return 2
    for old, why in seen:
        if why != "нет файла":
            print(f"⚠️ phoenix_lag.py пропущен — {why}: {old.as_posix()} · считаю по {where.as_posix()}")
    limit = lag.LAG_HOURS
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    rows = measure(con, lag, role)

    if not rows:
        # ⚪ Различаем ПРИЧИНУ пустоты, а не гадаем «новорождённость» (карточка #606).
        # Отставание считается от ПОСЛЕДНЕЙ ЗАПИСКИ роли (см. measure()) — если в ленте
        # НЕТ ни одной записки вовсе, отставать разделам памяти НЕЧЕГО ОТ ЧЕГО: это честный
        # свежий контур, а не пропавшие данные. Если же лента не пуста, а сверить нечего
        # (роль/секция не нашлись) — прежний отказ остаётся дословно: это настоящая пропажа.
        (message_count,) = con.execute("SELECT COUNT(*) FROM messages_all").fetchone()
        con.close()
        if message_count == 0:
            print("⚪ ни одна роль ещё не писала в ленту — отставать разделам памяти "
                  "не от чего (свежий контур)")
            return 0
        print(f"⛔ ОТКАЗ: сохранённой памяти не найдено ({'роль ' + role if role else 'все роли'}). "
              f"Отсутствие данных — отказ, а не зелёное.")
        return 2
    con.close()

    missing = [x for x in rows if x[2] is None]
    lagging = [x for x in rows if x[2] and x[2]["change_lag_h"] is not None
               and x[2]["change_lag_h"] > limit]
    unconfirmed = [x for x in rows if x[2] and x not in lagging and x[2]["unconfirmed_h"] is not None
                   and x[2]["unconfirmed_h"] > limit]

    print(f"📏 охват: проверено {len(rows)} секций "
          f"({', '.join(FAST_SECTIONS)}) у {len(set(x[0] for x in rows))} ролей · порог {limit} ч")
    print(f"   ⚠️ НЕ проверяются: identity, history — медленные по природе; "
          f"rebirth, launcher — их протухание ловит guard-stale-commands")
    print(f"   отставание считается от сохранения или подтверждения раздела до записки роли со "
          f"сменой состояния ({lag.STATE_CHANGE_NAMES}), а не от текущего времени и не от любой записки")

    if missing:
        print(f"\n🔴 {len(missing)}: секции НЕТ ВООБЩЕ")
        for r, sec, _ in sorted(missing):
            print(f"   {r} · {sec}")

    save = (Path(lag.__file__).resolve().parent / "save-phoenix.py").as_posix()
    if unconfirmed:
        print(f"\n🟡 {len(unconfirmed)}: раздел не подтверждался после записки (записки без признаков "
              f"смены состояния — это не отставание, код не меняется)")
        for r, sec, x in sorted(unconfirmed, key=lambda y: -y[2]["unconfirmed_h"]):
            print(f"   [{r} · {sec}] не подтверждался {x['unconfirmed_h']:.0f} ч после записки "
                  f"(записок после {x['notes']}, последняя {x['last_note']} UTC)")
        print(f"   👉 перечитал, правок нет: python {save} --role <РОЛЬ> --section <раздел> --confirm")

    if not lagging:
        print(f"\n✅ секций, отставших от смены состояния роли, не найдено "
              f"(ВЫПОЛНЕНО {len(rows)} проверок)")
        return 1 if missing else 0

    print(f"\n🔴 {len(lagging)}: раздел отстал от смены состояния — записки роли с признаками "
          f"({lag.STATE_CHANGE_NAMES}) позже его сохранения или подтверждения")
    print("   Это РЕЛЯЦИЯ, а не приговор: признаки — образцы слов, а не понимание. Но секция,")
    print("   отставшая на смену работы, воскресит роль в состояние, которого уже нет.")
    for r, sec, x in sorted(lagging, key=lambda y: -y[2]["change_lag_h"]):
        print(f"\n   [{r} · {sec}]  отставание {x['change_lag_h']:.0f} ч")
        print(f"      раздел сохранён или подтверждён: {x['saved']} UTC")
        print(f"      последняя смена состояния: {x['last_change']} UTC · таких записок {x['changes']} "
              f"({', '.join(x['reasons'])})")
    print(f"\n   👉 правишь — сохрани: python {save} --role <РОЛЬ> --section <раздел> --file <файл>; "
          f"перечитал, правок нет — --confirm вместо --file")
    print(f"\nВЫПОЛНЕНО {len(rows)} проверок, красных {len(lagging) + len(missing)}")
    return 1


# ═════════════════════════════════════════════════════════════════════════════

def selftest():
    """🪤 Счёт случаев — норма @STUD: прогон, не назвавший ЧИСЛО выполненных проверок,
    не считается прогоном. Ноль случаев — красный, замаскированный под зелёный."""
    import tempfile
    ok, cases = True, 0
    work = "commit a1b2c3d — правка инструмента"     # записка со сменой состояния
    ack = "принято, прочитала"                       # записка без признаков

    def db_with(tmp, name, rows_phx, rows_msg):
        """rows_phx: (роль, секция, saved_at[, confirmed_at]) · rows_msg: (роль, час[, тело])."""
        p = Path(tmp) / name
        con = sqlite3.connect(p)
        con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT, "
                    "confirmed_at TEXT)")
        # 🩸 таблица называется messages_all — так же, как ВИД, который читает measure()
        # (карточка #606: самопроверка раньше заводила «messages» и падала на своём же
        # запросе «no such table: messages_all» ДО первого случая — беда пре-существующая,
        # не от этой правки, но раз файл тронут, чинится тем же ходом).
        con.execute("CREATE TABLE messages_all (id INTEGER, writer_role TEXT, body_md TEXT, timestamp TEXT)")
        con.executemany("INSERT INTO phoenix VALUES (?,?,'x',?,?)",
                        [(x[0], x[1], x[2], x[3] if len(x) > 3 else None) for x in rows_phx])
        con.executemany("INSERT INTO messages_all VALUES (1,?,?,?)",
                        [(x[0], x[2] if len(x) > 2 else work, x[1]) for x in rows_msg])
        con.commit(); con.close()
        return p

    with tempfile.TemporaryDirectory() as tmp:
        # ① секция отстала на смену работы — обязано краснеть
        print("── ① план отстал на 18 ч ─────────────────────────────────────")
        cases += 1
        p = db_with(tmp, "a.db",
                    [("X", "state", "2026-08-06 16:00:00"), ("X", "plan", "2026-08-05 22:00:00")],
                    [("X", "2026-08-06 16:30:00")])
        if run("X", p) != 1:
            print("🔴 не покраснел на отставшей секции"); ok = False

        # ② РАЗЛИЧАЮЩИЙ: обе секции свежие — обязано молчать. Без этого признак,
        #    красящий всё подряд, прошёл бы ①.
        print("── ② обе секции свежие ───────────────────────────────────────")
        cases += 1
        p = db_with(tmp, "b.db",
                    [("X", "state", "2026-08-06 16:00:00"), ("X", "plan", "2026-08-06 16:10:00")],
                    [("X", "2026-08-06 16:30:00")])
        if run("X", p) != 0:
            print("🔴 краснеет на свежих секциях — ложная тревога"); ok = False

        # ③ РАЗЛИЧАЮЩИЙ, ГЛАВНЫЙ: свежий state НЕ ДОЛЖЕН гасить отставший plan.
        #    Именно этим слеп существующий гард — он берёт MAX по роли.
        print("── ③ свежий state не гасит отставший plan ────────────────────")
        cases += 1
        p = db_with(tmp, "c.db",
                    [("X", "state", "2026-08-06 16:29:00"), ("X", "plan", "2026-07-27 09:00:00")],
                    [("X", "2026-08-06 16:30:00")])
        if run("X", p) != 1:
            print("🔴 свежая секция погасила отставшую — та же слепота, что у прежнего гарда")
            ok = False

        # ④ РАЗЛИЧАЮЩИЙ: дормантная роль молчит — её слепок честен, красить нельзя
        print("── ④ дормант: память старая, но и работы нет ─────────────────")
        cases += 1
        p = db_with(tmp, "d.db",
                    [("X", "state", "2026-07-01 10:00:00"), ("X", "plan", "2026-07-01 10:00:00")],
                    [("X", "2026-07-01 10:05:00")])
        if run("X", p) != 0:
            print("🔴 покраснел на дормантной роли — будить её нечем"); ok = False

        # ⑤ ПЕРЕСМОТРЕН (карточка #606): пустая выборка И лента пуста ВООБЩЕ — это
        #    свежий контур, а не пропажа. Отставать разделам памяти не от чего.
        print("── ⑤ пустая выборка, лента тоже пуста — свежий контур, не отказ ──")
        cases += 1
        p = db_with(tmp, "e.db", [], [])
        if run("НЕТ_ТАКОЙ", p) != 0:
            print("🔴 свежий контур (ни памяти, ни ленты) не прошёл как ⚪"); ok = False

        # ⑤-бис РАЗЛИЧАЮЩИЙ: лента НЕ пуста (кто-то писал), а сверить нечего — это
        #    настоящая пропажа памяти, прежний отказ остаётся дословно.
        print("── ⑤-бис пустая выборка, а лента НЕ пуста — прежний отказ ────")
        cases += 1
        p = db_with(tmp, "f.db", [], [("Y", "2026-08-06 16:30:00")])
        if run("НЕТ_ТАКОЙ", p) != 2:
            print("🔴 непустая лента при пустой выборке не отказала как раньше"); ok = False

        # ⑥ РАЗЛИЧАЮЩИЙ (issue #38): после сохранения — только ответ «принято» — не провал
        print("── ⑥ после сохранения только «принято» — предупреждение, не провал ─")
        cases += 1
        p = db_with(tmp, "g.db",
                    [("X", "state", "2026-08-06 10:00:00"), ("X", "plan", "2026-08-06 10:00:00")],
                    [("X", "2026-08-06 16:30:00", ack)])
        if run("X", p) != 0:
            print("🔴 ответ без признаков смены состояния покрасил раздел"); ok = False

        # ⑦ РАЗЛИЧАЮЩИЙ: подтверждение (--confirm) позже записки гасит отставание
        print("── ⑦ подтверждение позже записки — не отставание ──────────────")
        cases += 1
        p = db_with(tmp, "h.db",
                    [("X", "state", "2026-08-06 10:00:00", "2026-08-06 17:00:00"),
                     ("X", "plan", "2026-08-06 10:00:00", "2026-08-06 17:00:00")],
                    [("X", "2026-08-06 16:30:00")])
        if run("X", p) != 0:
            print("🔴 честное «перечитал, правок нет» не погасило отставание"); ok = False

        # ⑧ (замечание приёмки PR 56): прежний phoenix_lag.py без section_lag стоит ПЕРВЫМ —
        #    место пропускается с названной причиной, счёт идёт по следующему, трассировки нет
        old = Path(tmp) / "old-scripts"
        old.mkdir()
        (old / "phoenix_lag.py").write_text("LAG_HOURS = 3\n\n\ndef memory_lag(con, role):\n"
                                            "    return None\n", encoding="utf-8")
        print("── ⑧ прежний phoenix_lag.py первым — пропущен, счёт по следующему ─")
        cases += 1
        p = db_with(tmp, "i.db",
                    [("X", "state", "2026-08-06 16:00:00"), ("X", "plan", "2026-08-06 16:10:00")],
                    [("X", "2026-08-06 16:30:00")])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = run("X", p, [old] + _lag_places())
        print(buf.getvalue(), end="")
        if rc != 0 or "без section_lag" not in buf.getvalue() or "пропущен" not in buf.getvalue():
            print(f"🔴 прежний файл не пропущен с причиной (код {rc})"); ok = False

        # ⑨ РАЗЛИЧАЮЩИЙ: годного phoenix_lag.py нет ни в одном месте — отказ кодом 2 с перечнем
        #    мест и словами «есть, но без section_lag», а не AttributeError с кодом 1
        print("── ⑨ годного phoenix_lag.py нет нигде — отказ кодом 2 с перечнем ─")
        cases += 1
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = run("X", p, [old, Path(tmp) / "no-such-place"])
        print(buf.getvalue(), end="")
        if rc != 2 or "есть, но без section_lag" not in buf.getvalue() or "нет файла" not in buf.getvalue():
            print(f"🔴 без годной общей функции нет отказа кодом 2 с перечнем (код {rc})"); ok = False

        # ⑩ РАЗЛИЧАЮЩИЙ (записка #6086): одно место тремя написаниями — как пришло (у временного
        #    каталога Windows это часто короткое имя 8.3), после resolve() и через «x/..» — в перечне
        #    отказа один раз, а не три
        (old / "x").mkdir()
        print("── ⑩ одно место разным написанием — в перечне один раз ─────────")
        cases += 1
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = run("X", p, [old, old.resolve(), old / "x" / ".."])
        print(buf.getvalue(), end="")
        times = buf.getvalue().count("есть, но без section_lag")
        if rc != 2 or times != 1:
            print(f"🔴 одно место названо в перечне {times} раз (код {rc})"); ok = False

    if cases == 0:
        print("\n⛔ ОТКАЗ: ни одного случая не выполнено — это не «чисто»")
        return 2
    print(f"\n{'✅ САМОПРОВЕРКА ПРОЙДЕНА' if ok else '🔴 САМОПРОВЕРКА ПРОВАЛЕНА'} — "
          f"ВЫПОЛНЕНО {cases} случаев")
    print("   краснеет на отставшей секции · молчит на свежих · СВЕЖАЯ НЕ ГАСИТ ОТСТАВШУЮ · "
          "не будит дормант · на пустом контуре (ни памяти, ни ленты) — ⚪, не отказ · "
          "на пропаже памяти при непустой ленте — отказывает по-прежнему · "
          "ответ без признаков смены состояния не красит · подтверждение гасит · "
          "прежний phoenix_lag.py пропускает · без годного — отказ кодом 2 · "
          "одно место разным написанием — в перечне один раз")
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="раздел памяти отстал от смены состояния роли")
    ap.add_argument("--role")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(selftest() if a.selftest else run(a.role, a.db))
