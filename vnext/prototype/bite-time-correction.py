# -*- coding: utf-8 -*-
r"""ПРИЁМКА гашения меток ПОПРАВКОЙ и видимости того, что уехало за окно (карточка #144).

КЛАСС, РАДИ КОТОРОГО ВСЁ: лента ДОПИСЫВАЕТСЯ — тело записки исправить нельзя. Значит
дефект метки неустраним по построению, и проверка была бы красной вечно. Прежнее лекарство —
окно 24 ч — лечило симптом: 09.08 прогон стал ЗЕЛЁНЫМ без единой починки, просто потому,
что три дефекта уехали за сутки.
> Сигнал, пропавший оттого, что дефект уехал из окна, неотличим от вылеченного.

ДВА СВОЙСТВА ПОД ЗАЩИТОЙ:
  ① гасит ПОПРАВКА, а не время: явная записка про ВРЕМЯ со ссылкой «#N», вышедшая ПОЗЖЕ;
  ② что уехало за окно и НЕ погашено — печатается отдельной строкой, а не молчит.

⛔ Живой базы не касается: стенд — временная БД.
⛔ Число случаев печатает прогон.
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
GUARD = os.path.join(HERE, "guard-phoenix-time.py")
if not os.path.exists(GUARD):
    print(f"⛔ ИСПЫТУЕМОГО НЕТ: {GUARD} — отказ мерить, не «чисто»")
    sys.exit(2)
spec = importlib.util.spec_from_file_location("guard_time_under_test", GUARD)
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)

CASES = 0
DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def build(rows):
    """rows: (id, role, ts, tags, body)."""
    db = os.path.join(tempfile.mkdtemp(prefix="bite-time-corr-"), "m.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT,"
                " timestamp TEXT, body_md TEXT, tags TEXT)")
    con.executemany("INSERT INTO messages (id, writer_role, timestamp, tags, body_md)"
                    " VALUES (?,?,?,?,?)", rows)
    con.commit()
    return db, con


# запись с дефектом: метка в теле на 2 часа впереди timestamp
BAD = ("— PROTO 2026-08-09 12:00 UTC", "2026-08-09 10:00:00")


def quenched(extra_line, mid=100, tags="", ref="#100"):
    db, con = build([
        (mid, "PROTO", BAD[1], "", f"тело записки\n\n{BAD[0]}"),
        (mid + 1, "PROTO", "2026-08-09 11:00:00", tags, extra_line.replace("#REF", ref)),
    ])
    fixed = G.corrected_ids(con)
    con.close()
    return mid in fixed


def main() -> int:
    ok = True

    # ① ПОПРАВКА ПРО ВРЕМЯ СО ССЫЛКОЙ — гасит
    ok &= case("① поправка про метку времени со ссылкой — гасит",
               quenched("🪤 ПОПРАВКА: метки времени в записке #REF на два часа вперёд"),
               "единственный честный способ закрыть дефект в дописываемой ленте", differ=True)

    # ② ВСТРЕЧНЫЙ и ГЛАВНЫЙ: поправка про ДРУГОЕ со ссылкой — НЕ гасит.
    #    Случай не выдуман: живая #2828 («токен-инструкция исправлена по #2809») ошибочно
    #    тушила дефект метки в #2809 при широком правиле. Тот же класс, что #151 (гашение
    #    по соседству), только через номера: у ссылки не спрашивают, О ЧЁМ поправка.
    ok &= case("② поправка про ДРУГОЕ со ссылкой — НЕ гасит (встречный к ①)",
               not quenched("(обход снят живьём, токен-инструкция исправлена по #REF)"),
               "поправка обязана быть ПРО ЭТО: слово поправки И тема времени в одной строке",
               differ=True)

    # ③ ТЕГ correction + тема времени — гасит и без слова «поправка» в строке
    ok &= case("③ тег correction + тема времени — гасит",
               quenched("читайте минус два часа в #REF", tags='["correction"]'),
               "механизм пометки сильнее прозы, но тема всё равно требуется", differ=True)

    # ④ ГОЛАЯ ССЫЛКА — не гасит: записки ссылаются друг на друга постоянно
    ok &= case("④ ссылка без поправки — НЕ гасит (встречный к ③)",
               not quenched("как и договаривались в #REF, продолжаем работу"),
               "иначе любое упоминание номера тушило бы дефект", differ=True)

    # ⑤ ПОПРАВКА РАНЬШЕ ОШИБКИ — не гасит: текст, написанный ДО, её не отменяет
    db, con = build([
        (50, "PROTO", "2026-08-09 09:00:00", "", "ПОПРАВКА: метки времени в #100 неверны"),
        (100, "PROTO", BAD[1], "", f"тело\n\n{BAD[0]}"),
    ])
    fixed_early = G.corrected_ids(con)
    con.close()
    ok &= case("⑤ «поправка» РАНЬШЕ ошибки не гасит (ссылка вперёд — не свидетельство)",
               100 not in fixed_early, "поправка обязана быть позже: id больше", differ=True)

    # ⑥ ВНЕ ОКНА И НЕ ПОГАШЕНО — печатается отдельной строкой, а не молчит.
    #    Это и есть лечение класса: исчезновение сигнала перестаёт быть неотличимым
    #    от починки.
    db, _ = build([(10, "PROTO", "2026-07-01 10:00:00", "", f"старое тело\n\n"
                    f"— PROTO 2026-07-01 12:00 UTC")])
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        G.run_messages(db, since_hours=24)
    out = buf.getvalue()
    ok &= case("⑥ непогашенное ВНЕ ОКНА названо отдельной строкой, а не молчит",
               "ВНЕ ОКНА" in out and "#10" in out,
               "иначе зелёное значит лишь «дефект уехал за сутки»", differ=True)

    # ⑦ ВСТРЕЧНЫЙ к ⑥: старое, ПОГАШЕННОЕ поправкой, за окном не считается долгом
    db, _ = build([
        (10, "PROTO", "2026-07-01 10:00:00", "", "старое\n\n— PROTO 2026-07-01 12:00 UTC"),
        (11, "PROTO", "2026-07-01 11:00:00", "", "ПОПРАВКА: метки времени в #10 на два часа"),
    ])
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        G.run_messages(db, since_hours=24)
    out2 = buf.getvalue()
    ok &= case("⑦ погашенное поправкой за окном долгом НЕ считается (встречный к ⑥)",
               "непогашенных нет" in out2 and "#10" not in out2,
               "поправка гасит НАВСЕГДА — иначе роль наказана за честное признание",
               differ=True)

    print()
    print(f"{'✅ ГАШЕНИЕ ПОПРАВКОЙ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}, у каждого различающего встречный")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
