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
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале


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
    db = os.path.join(mezo_stand.new("bite-sj-"), "m.db")
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
    ok &= case("② шаг МИМО журнала — проверка краснеет и называет причину",
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
    db5 = os.path.join(mezo_stand.new("bite-sj5-"), "m.db")
    con5 = sqlite3.connect(db5)
    con5.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, note TEXT)")
    good, why = SJ.verify(con5)
    ok &= case("⑤ колонки отпечатка нет — отказ мерить, названо вслух",
               (not good) and "нечем" in why,
               f"ответ: {why[:80]}", differ=True)

    # ⑥ КОЛОНКА ЕСТЬ, ОТПЕЧАТКОВ НЕТ — второй, ДРУГОЙ пустой ответ. Оба обязаны звучать
    #    отказом: «у тебя нет» и «никто не заполнял» — разные случаи.
    con6 = sqlite3.connect(os.path.join(mezo_stand.new("bite-sj6-"), "m.db"))
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

    # ⑨ АВТОР ШАГА ЗАПОЛНЯЕТСЯ ВСЕГДА, И ИСТОЧНИК ВИДЕН В САМОМ ЗНАЧЕНИИ (карточка #89).
    #    Свойство ради того, чтобы поле не повторило судьбу `resolved` (1 запись из 1483):
    #    незаполняемое поле — не лень ролей, а отсутствующий механизм. Поэтому автор
    #    выводится из вызывателя, когда его не назвали, — и остаётся отличим от названного.
    # ⚠️ Убираем MEZO_ROLE из окружения ЯВНО: с карточки #248 он — средняя ступень выбора
    #    автора, и у роли, которая его выставила, «не назван» дало бы её имя, а не «tool:».
    #    Приёмка, зависящая от окружения запускающего, отвечает по-разному у разных ролей —
    #    и первая же расходящаяся пара читается как дефект продукта.
    было_MEZO_ROLE = os.environ.pop("MEZO_ROLE", None)
    con9 = fresh()
    con9.execute("BEGIN")
    con9.execute("CREATE TABLE t9 (id INTEGER PRIMARY KEY)")
    SJ.record_step(con9, "009-auto", "автор не назван")
    con9.execute("CREATE TABLE t9b (id INTEGER PRIMARY KEY)")
    SJ.record_step(con9, "009-named", "автор назван", by="PROTO")
    con9.commit()
    auto = con9.execute("SELECT applied_by FROM schema_migrations WHERE version='009-auto'"
                        ).fetchone()[0]
    named = con9.execute("SELECT applied_by FROM schema_migrations WHERE version='009-named'"
                         ).fetchone()[0]
    empty = con9.execute("SELECT COUNT(*) FROM schema_migrations WHERE applied_by IS NULL "
                         "OR TRIM(applied_by)=''").fetchone()[0]
    # ⚠️ Сравнения нарочно терпимы к пустому значению: при нарочной поломке (автор
    #    перестал выводиться) первая редакция этой проверки ПАДАЛА трассой на None —
    #    то есть выдавала третий исход «НЕ ЗАПУСТИЛАСЬ» там, где обязана была сказать
    #    «свойство нарушено». Проверка, умеющая только падать, не отличает поломку
    #    механизма от поломки себя самой.
    ok &= case("⑨ автор шага НИКОГДА не пуст, и выведенный отличим от названного",
               bool(auto) and str(auto).startswith("tool:") and named == "PROTO" and empty == 0,
               f"не назван → «{auto}» · назван → «{named}» · пустых {empty}", differ=True)

    # ⑩ ВСТРЕЧНЫЙ К ⑨: выведенное значение обязано указывать на ВЫЗЫВАТЕЛЯ, а не на сам
    #    модуль журнала. Иначе «tool:…» стоял бы всегда одинаковый и не значил ничего —
    #    заполненное поле, не несущее сведений, хуже пустого: оно выглядит ответом.
    ok &= case("⑩ выведенный автор указывает на ВЫЗЫВАТЕЛЯ, а не на сам журнал",
               bool(auto) and "schema_journal" not in str(auto),
               f"вызыватель — приёмка, значение «{auto}»", differ=True)

    # ⑪ СРЕДНЯЯ СТУПЕНЬ (карточка #248): роль объявила себя в окружении — пишем ЕЁ.
    #    Это её собственное слово, а не догадка кода и не имя чужого контура.
    os.environ["MEZO_ROLE"] = "neigh"
    con11 = fresh()
    con11.execute("BEGIN")
    con11.execute("CREATE TABLE t11 (id INTEGER PRIMARY KEY)")
    SJ.record_step(con11, "011-env", "автор не назван, но объявлен в окружении")
    con11.commit()
    из_среды = con11.execute("SELECT applied_by FROM schema_migrations WHERE version='011-env'"
                             ).fetchone()[0]
    os.environ.pop("MEZO_ROLE", None)
    if было_MEZO_ROLE is not None:
        os.environ["MEZO_ROLE"] = было_MEZO_ROLE
    ok &= case("⑪ роль объявлена в окружении — пишем ЕЁ, а не «tool:» (карточка #248)",
               из_среды == "NEIGH",
               f"MEZO_ROLE=neigh → «{из_среды}» (регистр приведён: реестр ролей верхний)",
               differ=True)

    # ⑫ ⛔ ГЛАВНОЕ ПО КАРТОЧКЕ #248: НИ В ОДНОМ ШАГЕ СХЕМЫ ИМЯ РОЛИ НЕ ВПЕЧАТАНО.
    #    🩸 Оплачено соседями: прогнав наш шаг у себя, они получили в свой журнал автора
    #    «PROTO» — роль их контура не касавшуюся. Заявка называла ОДИН файл; замер нашёл
    #    имена в СЕМИ, и в двух из них по два места.
    #    ⚖️ Признак берётся ПО КАТАЛОГУ, а не списком известных файлов: список сходится
    #    в день написания и молча расходится с первой же новой миграцией.
    шаги = sorted((mezo_target.scripts_root() / "migrations").glob("*.py"))
    впечатано = []
    for ш in шаги:
        for i, s in enumerate(ш.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"""by\s*=\s*['"](?:PROTO|COORD|CORE|ING|STUD|TAXO|OPSSRE|RCC|CHROME)""", s):
                впечатано.append(f"{ш.name}:{i}")
    ok &= case("⑫ ⛔ ни в одном шаге схемы имя роли НЕ впечатано",
               not впечатано and len(шаги) > 5,
               f"шагов просмотрено {len(шаги)}; впечатано: {впечатано or 'нигде'} — "
               "впечатанное имя отвечает на «кто применил» уверенно и неверно",
               differ=True)

    # ⑬⑭⑮ РАЗБОР ПРАВКИ СХЕМЫ НА ОПЕРАТОРЫ (находка @OPSSRE 23.08, оплачена сломанной
    #      схемой: `incomplete input` при ПРИМЕНЕНИИ шага). Воспроизводим его случай точно.
    из_комментария = SJ.split_statements(
        "-- копия ПРЕЖНЕГО тела; NULL — первая версия\n"
        "CREATE TABLE t13 (id INTEGER PRIMARY KEY, body TEXT);\n")
    ok &= case("⑬ точка с запятой в КОММЕНТАРИИ не разрывает оператор",
               len(из_комментария) == 1,
               f"операторов вышло {len(из_комментария)} (наивный разбор дал бы 2 — "
               "и второй кусок был бы обломком, на котором SQLite падает)", differ=True)

    из_значения = SJ.split_statements("INSERT INTO t (x) VALUES ('точка;с запятой');\n")
    ok &= case("⑭ точка с запятой в СТРОКОВОМ ЗНАЧЕНИИ не разрывает оператор",
               len(из_значения) == 1,
               f"операторов вышло {len(из_значения)} — тот же класс, другая причина",
               differ=True)

    # ⑮ ВСТРЕЧНЫЙ: без него ⑬⑭ прошли бы и у разбора, который ВСЕГДА отдаёт один кусок.
    настоящие = SJ.split_statements(
        "CREATE TABLE a (x TEXT);\nCREATE TABLE b (y TEXT);\n-- одни комментарии\n")
    ok &= case("⑮ ВСТРЕЧНЫЙ: два настоящих оператора остаются двумя, комментарий — не третий",
               len(настоящие) == 2,
               f"операторов вышло {len(настоящие)}: разбор, всегда отдающий одно целое, "
               "прошёл бы ⑬ и ⑭ и молча не применил бы половину правки", differ=True)

    # ⑯ ⛔ НИ ОДИН ШАГ СХЕМЫ НЕ РЕЖЕТ ПРАВКУ НАИВНО. Признак по каталогу, не по списку:
    #    заявка называла ОДИН файл, мест было ДВА.
    наивные = []
    for ш in sorted((mezo_target.scripts_root() / "migrations").glob("*.py")):
        for i, s in enumerate(ш.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r'\.split\(\s*["\'];["\']\s*\)', s) and not s.lstrip().startswith("#"):
                наивные.append(f"{ш.name}:{i}")
    ok &= case("⑯ ⛔ ни один шаг схемы не режет правку по точке с запятой",
               not наивные,
               f"наивный разбор: {наивные or 'нигде'} — знак препинания в пояснении "
               "ломает схему, и ломает в момент применения, а не при чтении кода",
               differ=True)

    print()
    print((f"✅ ЖУРНАЛ ПРИНЯТ — случаев {CASES}, различающих {DIFFER}, "
           f"испытан {mezo_target.label()}") if ok
          else f"🔴 ЖУРНАЛ НЕ ПРИНЯТ — испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
