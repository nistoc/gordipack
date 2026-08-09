# -*- coding: utf-8 -*-
r"""ПРИЁМКА журнала изменений схемы (schema_journal.py) — карточка #135.

Механизм починен @COORD 08.08 в запрошенном порядке (шаг пишет себя САМ в той же
транзакции · у записи отпечаток структуры · сторож сверяет обе стороны), но приёмки
с нарочной поломкой у него НЕ БЫЛО — а критерий писал я, и принимать по рапорту нельзя.
Сторож в guard-all зелёный, да зелёное означает ровно то, что он позвал: без поломки
не доказано, что он умеет краснеть на ЭТОМ механизме.

Главные свойства под защитой:
  · шаг, применённый МИМО журнала, виден («уверенный и неверный ответ о версии»);
  · «та же транзакция» — не слова: откат стирает шаг И запись ВМЕСТЕ;
  · «сверять нечем» звучит отказом, а не чистотой (два разных пустых ответа);
  · ГРАНИЦА признака (данные не двигают отпечаток) названа в самом модуле — иначе
    зелёное читается шире себя.

⛔ Живой базы не касается: стенд — временная БД в песочнице.
⛔ Число случаев словом не пишется — его печатает прогон.
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом


def load_module():
    path = mezo_target.script("schema_journal.py")
    spec = importlib.util.spec_from_file_location("schema_journal_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, str(path)


SJ, SJ_PATH = load_module()
CASES = 0
DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def fresh():
    db = os.path.join(tempfile.mkdtemp(prefix="bite-sj-"), "m.db")
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY,"
                " applied_at TEXT DEFAULT CURRENT_TIMESTAMP, note TEXT, fingerprint TEXT)")
    con.execute("CREATE TABLE t0 (id INTEGER PRIMARY KEY, x TEXT)")
    con.execute("INSERT INTO t0 (x) VALUES ('данные')")
    # опорный шаг: журнал знает исходную структуру.
    # ⚠️ BEGIN здесь появился 2026-08-09 вместе с починкой @COORD по находке ⑧ этой же
    # приёмки: record_step теперь ОТКАЗЫВАЕТСЯ вне транзакции. Стенд обязан следовать
    # тому же правилу, что и живые шаги, — иначе приёмка проверяла бы поведение,
    # которого в бою больше нет.
    if not con.in_transaction:
        con.execute("BEGIN")
    SJ.record_step(con, "000-base", "опорный шаг стенда")
    con.commit()
    return con


def main() -> int:
    ok = True

    # ① ЗДОРОВЫЙ ПУТЬ [контроль]: правка схемы + запись в той же транзакции → сходится.
    #    Без него краснота остальных случаев ничего не доказывает.
    con = fresh()
    con.execute("BEGIN")          # явная транзакция — теперь это требование record_step
    con.execute("CREATE TABLE t1 (id INTEGER PRIMARY KEY)")
    SJ.record_step(con, "001-t1", "новая таблица")
    con.commit()
    good, why = SJ.verify(con)
    ok &= case("① шаг с записью в той же транзакции — журнал сходится со схемой",
               good, why)

    # ② НАРОЧНАЯ ПОЛОМКА: шаг применён МИМО журнала → красный с внятной причиной.
    con2 = fresh()
    con2.execute("CREATE TABLE tx (id INTEGER PRIMARY KEY)")   # запись НЕ делаем
    con2.commit()
    good, why = SJ.verify(con2)
    ok &= case("② шаг МИМО журнала — сторож краснеет и называет причину",
               (not good) and "МИМО ЖУРНАЛА" in why,
               f"ответ: {why[:100]}", differ=True)

    # ③ «ТА ЖЕ ТРАНЗАКЦИЯ» ДОКАЗЫВАЕТСЯ ОТКАТОМ, а не чтением докстринга:
    #    шаг + запись при ЯВНОМ BEGIN, затем ROLLBACK — исчезнуть обязаны ОБА.
    #    Если бы запись жила в своей транзакции, журнал знал бы шаг, которого не было.
    con3 = fresh()
    con3.execute("BEGIN")
    con3.execute("CREATE TABLE t3 (id INTEGER PRIMARY KEY)")
    SJ.record_step(con3, "003-t3", "будет откачен")
    con3.rollback()
    good, why = SJ.verify(con3)
    known = [v for (v,) in con3.execute("SELECT version FROM schema_migrations")]
    ok &= case("③ при ЯВНОЙ транзакции откат стирает шаг И запись вместе",
               good and "003-t3" not in known,
               f"после отката журнал знает {known}, сверка: {why[:70]}", differ=True)

    # ⑧ 🔴 НАХОДКА ЭТОЙ ПРИЁМКИ (第一 прогон, 19:25 UTC) — ОБЕЩАНИЕ ЛОМАЕТСЯ МОЛЧА
    #    БЕЗ ЯВНОГО BEGIN. Python-sqlite открывает неявную транзакцию только перед
    #    INSERT/UPDATE; DDL первым действием уходит В АВТОКОММИТ. Тогда откат стирает
    #    ТОЛЬКО запись журнала, а таблица остаётся — схема изменена, журнал молчит,
    #    и это тот самый «уверенный неверный ответ», от которого журнал заводили.
    #    Живые шаги миграций подключаются ИМЕННО ТАК (без BEGIN) ⇒ упади шаг на середине —
    #    ровно этот случай. record_step ОБЯЗАН отказаться, если транзакции нет:
    #    молча записать «в той же транзакции», которой не существует, — ложь построением.
    con8 = fresh()
    con8.execute("CREATE TABLE t8 (id INTEGER PRIMARY KEY)")   # DDL first ⇒ автокоммит
    refused = False
    try:
        SJ.record_step(con8, "008-t8", "запись вне транзакции")
    except Exception as e:
        refused = "транзакц" in str(e).lower()
    ok &= case("⑧ record_step БЕЗ открытой транзакции отказывается ГРОМКО (встречный к ③)",
               refused,
               "иначе «та же транзакция» — слова: откат стирает запись, оставляя схему; "
               "живые шаги миграций зовут ровно так", differ=True)

    # ④ ЗАПИСЬ ЗАДНИМ ЧИСЛОМ несёт пометку в самом тексте — честность ретро-записей.
    #    Живой журнал так и записан: 4 строки 08.08 помечены. Пометку ставит МЕХАНИЗМ.
    con4 = fresh()
    SJ.record_step(con4, "004-retro", "восстановлено", backdated=True)
    con4.commit()
    note = con4.execute("SELECT note FROM schema_migrations WHERE version='004-retro'"
                        ).fetchone()[0]
    ok &= case("④ ретро-запись помечена «задним числом» рукой МЕХАНИЗМА, не автора",
               "ЗАДНИМ ЧИСЛОМ" in note,
               f"note: …{note[-60:]}", differ=True)

    # ⑤ НЕТ КОЛОНКИ ОТПЕЧАТКА — «сверять нечем», а не «чисто».
    db5 = os.path.join(tempfile.mkdtemp(prefix="bite-sj5-"), "m.db")
    con5 = sqlite3.connect(db5)
    con5.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, note TEXT)")
    good, why = SJ.verify(con5)
    ok &= case("⑤ колонки отпечатка нет — отказ мерить, названо вслух",
               (not good) and "нечем" in why,
               f"ответ: {why[:80]}", differ=True)

    # ⑥ КОЛОНКА ЕСТЬ, ОТПЕЧАТКОВ НЕТ — второй, ДРУГОЙ пустой ответ. Оба обязаны звучать
    #    отказом: «у тебя нет» и «никто не заполнял» — разные случаи.
    con6 = sqlite3.connect(os.path.join(tempfile.mkdtemp(prefix="bite-sj6-"), "m.db"))
    con6.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY,"
                 " note TEXT, fingerprint TEXT)")
    con6.execute("INSERT INTO schema_migrations (version, note) VALUES ('x','без отпечатка')")
    good, why = SJ.verify(con6)
    ok &= case("⑥ записи есть, отпечатков нет — «не с чем», а не «чисто» (встречный к ⑤)",
               (not good) and "НЕ С ЧЕМ" in why,
               f"ответ: {why[:80]}", differ=True)

    # ⑦ ГРАНИЦА ПРИЗНАКА: шаг только по ДАННЫМ отпечаток не двигает — verify ЗЕЛЁНЫЙ,
    #    и это ЗАКОННО (предел признака, не дыра). Незаконно — молчать о пределе:
    #    он обязан быть назван в самом модуле, где его прочтёт применяющий.
    con7 = fresh()
    con7.execute("UPDATE t0 SET x='переписали данные'")       # записи в журнал НЕТ
    con7.commit()
    good, _ = SJ.verify(con7)
    src = open(SJ_PATH, encoding="utf-8").read()
    ok &= case("⑦ данные без записи не ловятся — ЗАКОННО, и предел НАЗВАН в модуле",
               good and "ГРАНИЦА" in src and "не данные" in src.replace("а не данные", "не данные"),
               "зелёное здесь — предел признака; непроизнесённый предел читался бы как охват",
               differ=True)

    print()
    print((f"✅ ЖУРНАЛ ПРИНЯТ — случаев {CASES}, различающих {DIFFER}, "
           f"испытан {mezo_target.label()}") if ok
          else f"🔴 ЖУРНАЛ НЕ ПРИНЯТ — испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
