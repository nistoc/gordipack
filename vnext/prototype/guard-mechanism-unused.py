"""
guard-mechanism-unused.py — признак «механизм НАЛОЖЕН, но не отвечает на свой вопрос».

═══ ЗАЧЕМ, И ПОЧЕМУ ПРОСТОЙ ВАРИАНТ ЭТОГО СТОРОЖА БЫЛ БЫ ВРЕДНЕЕ ОТСУТСТВИЯ ═══

Повод — замер PROTO #3089: накат внёс в рабочую базу три механизма, и через 2 ч 36 мин
все три стояли пустыми при 90 новых записках. Схема встала — а механизм не работал, и
никто этого не видел, потому что проверяли СХЕМУ.

Первый очевидный вариант сторожа — «считать долю записей, где новое поле заполнено».
Он БЫЛ БЫ ЛОЖЬЮ, и это предсказано заранее, до написания кода, — TAXO #3101:

> «④, которую ты сам просишь, покажет на этом ЗЕЛЁНОЕ»

Речь про флаг `--to`. Он ставит признак «адресат задан полем» — и признак честно
заполняется. А самих имён адресатов в базе НЕТ НИГДЕ: список остаётся прозой в теле
записки. Счётчик заполненности показал бы 100 % там, где ответить на вопрос
«покажи адресованное роли X» по-прежнему нельзя.

⇒ НОРМА, НА КОТОРОЙ ПОСТРОЕН ЭТОТ СТОРОЖ:
      Механизм обязан предъявить ЗАПРОС, отвечающий на его собственный вопрос.
      Нет запроса — это не механизм, а признак, и зелёным он быть не может,
      сколько бы раз ни заполнялся.

Отсюда четыре вердикта, а не два:
    ⛔ СОСУДА НЕТ ......... таблицы/колонки не существует вовсе
    🔴 ПРИЗНАК БЕЗ ОТВЕТА . пометка ставится, но запроса, отвечающего на вопрос, нет
                            (или он есть и не возвращает ничего ни на одном примере)
    ⚠️ НЕ УПОТРЕБЛЯЕТСЯ ... сосуд есть, ответить может, но в окне никто не пользовался
    ✅ ЖИВЁТ .............. и сосуд есть, и ответ даёт, и им пользуются

═══ ПОЧЕМУ ОКНО, А НЕ ВСЯ ТАБЛИЦА ═══
Доля по всей таблице у нового механизма ВСЕГДА близка к нулю: 1681 старая запись против
десятка новых. Такой счётчик краснел бы вечно и научил бы себя игнорировать. Считаем по
ОКНУ последних N записей и печатаем его границы — число без границ окна непроверяемо.

⚠️ Окно НЕ выводится из времени правки файла инструмента. Именно на этом сегодня сгорел
сосед: взял mtime (локальное время) и сравнил с лентой (UTC) — получил ложную тревогу
ровно на величину смещения зоны. Границы окна здесь — идентификаторы записей, у них
зоны нет вовсе.

Читает базу ТОЛЬКО НА ЧТЕНИЕ. Ничего не правит.

Запуск:
    python <абсолютный путь>/guard-mechanism-unused.py
    python <абсолютный путь>/guard-mechanism-unused.py --window 200
    python <абсолютный путь>/guard-mechanism-unused.py --self-test
"""

import argparse
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_DB = mezo_paths.live_db()
DEFAULT_WINDOW = 120

VERDICT_NO_VESSEL = "⛔ СОСУДА НЕТ"
VERDICT_NO_ANSWER = "🔴 ПРИЗНАК БЕЗ ОТВЕТА"
VERDICT_UNUSED = "⚠️ НЕ УПОТРЕБЛЯЕТСЯ"
VERDICT_ALIVE = "✅ ЖИВЁТ"


# ═══════════════════════════════════════════════════════════════════════════
# ОПИСАНИЕ МЕХАНИЗМОВ
#
# vessel_sql  — чем доказывается, что сосуд ЕСТЬ (возвращает строку → есть).
# answer_sql  — ЗАПРОС, ОТВЕЧАЮЩИЙ НА ВОПРОС МЕХАНИЗМА. None означает: такого
#               запроса написать нельзя, потому что содержимого в базе нет.
#               Это НЕ придирка — это и есть проверяемое определение механизма.
# usage_sql   — сколько записей окна им воспользовались (:lo/:hi — границы окна).
# ═══════════════════════════════════════════════════════════════════════════
MECHANISMS = [
    dict(
        key="thread",
        title="ответ связан с вопросом",
        question="покажи ветку обсуждения: кто кому отвечал",
        vessel_sql="SELECT 1 FROM sqlite_master WHERE type='table' AND name='message_thread'",
        answer_sql="SELECT message_id, reply_to FROM message_thread WHERE reply_to IS NOT NULL LIMIT 5",
        usage_sql="SELECT COUNT(*) FROM message_thread WHERE message_id BETWEEN :lo AND :hi",
    ),
    dict(
        key="addressee",
        title="адресат назван полем",
        question="покажи всё, что адресовано лично роли X",
        vessel_sql="SELECT 1 FROM pragma_table_info('messages') WHERE name='addressed_by'",
        # ⚠️ ЗДЕСЬ ГЛАВНОЕ МЕСТО ЭТОГО ФАЙЛА. Признак addressed_by='field' заполняется —
        # но имён адресатов в базе нет ни в одной таблице, они остаются прозой в теле.
        # Запроса «адресованное роли X» написать НЕЛЬЗЯ ⇒ answer_sql=None, и вердикт
        # будет красным, хотя колонка заполнена. Ровно то, что предсказала TAXO #3101.
        # Когда появится хранилище имён — сюда встанет настоящий запрос, и не раньше.
        answer_sql=None,
        answer_missing_why="имена адресатов не хранятся ни в одной таблице — только "
                           "признак «адресация задана»; сам список остаётся прозой в теле",
        usage_sql="SELECT COUNT(*) FROM messages WHERE id BETWEEN :lo AND :hi "
                  "AND addressed_by='field'",
    ),
    dict(
        key="task_link",
        title="записка связана с карточкой",
        question="покажи записки, относящиеся к карточке N",
        vessel_sql="SELECT 1 FROM sqlite_master WHERE type='table' AND name='message_task'",
        answer_sql="SELECT message_id, task_id FROM message_task LIMIT 5",
        usage_sql="SELECT COUNT(*) FROM message_task WHERE message_id BETWEEN :lo AND :hi",
    ),
    dict(
        key="revoked",
        title="утверждение отменено",
        question="покажи записки, чьё утверждение снято более поздним",
        vessel_sql="SELECT 1 FROM pragma_table_info('messages') WHERE name='resolved'",
        answer_sql="SELECT id FROM messages WHERE resolved=1 LIMIT 5",
        usage_sql="SELECT COUNT(*) FROM messages WHERE id BETWEEN :lo AND :hi AND resolved=1",
    ),
]


def _plural(n: int, one: str, few: str, many: str) -> str:
    """«1 примеров» в отчёте читается как небрежность, а небрежности в отчёте не верят."""
    tail100, tail10 = n % 100, n % 10
    if 11 <= tail100 <= 14:
        word = many
    elif tail10 == 1:
        word = one
    elif 2 <= tail10 <= 4:
        word = few
    else:
        word = many
    return f"{n} {word}"


def open_ro(db: Path) -> sqlite3.Connection:
    """Три замка на чтение: режим соединения, запрет записи, и ни одного не-SELECT ниже."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only = ON")
    return con


def window_bounds(con: sqlite3.Connection, size: int):
    """Границы окна — идентификаторы, а не время: у идентификатора нет часового пояса."""
    hi = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
    return max(1, hi - size + 1), hi


def probe(con: sqlite3.Connection, mech: dict, lo: int, hi: int) -> dict:
    """Один механизм → вердикт. Порядок проверок важен: сосуд → ответ → употребление."""
    has_vessel = con.execute(mech["vessel_sql"]).fetchone() is not None
    if not has_vessel:
        return dict(verdict=VERDICT_NO_VESSEL, used=0, note="ни таблицы, ни колонки")

    # Ответ проверяется ДО употребления. Механизм, который не может ответить на свой
    # вопрос, красен независимо от того, насколько бодро заполняется его пометка.
    if mech["answer_sql"] is None:
        used = con.execute(mech["usage_sql"], dict(lo=lo, hi=hi)).fetchone()[0]
        return dict(verdict=VERDICT_NO_ANSWER, used=used,
                    note=mech.get("answer_missing_why", "запрос-ответ не предъявлен"))

    answer_rows = con.execute(mech["answer_sql"]).fetchall()
    used = con.execute(mech["usage_sql"], dict(lo=lo, hi=hi)).fetchone()[0]
    if not answer_rows:
        # Запрос есть, но пуст на всех примерах — ответить он тоже не может.
        # Отдельный случай от «не употребляется»: там сосуд рабочий и просто ждёт,
        # здесь — заявленный ответ не существует ни для одной записи.
        return dict(verdict=VERDICT_NO_ANSWER, used=used,
                    note="запрос-ответ предъявлен, но пуст на всей базе")
    if used == 0:
        return dict(verdict=VERDICT_UNUSED, used=0,
                    note=f"ответить может ({_plural(len(answer_rows), 'пример', 'примера', 'примеров')}),"
                         f" но в окне 0")
    return dict(verdict=VERDICT_ALIVE, used=used,
                note=f"{_plural(len(answer_rows), 'пример', 'примера', 'примеров')} ответа, "
                     f"{_plural(used, 'употребление', 'употребления', 'употреблений')} в окне")


def run(db: Path, size: int) -> int:
    con = open_ro(db)
    lo, hi = window_bounds(con, size)
    total = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

    print(f"База ........... {db}")
    print(f"Записок всего .. {total}")
    print(f"Окно ........... записки #{lo}–#{hi} ({hi - lo + 1} шт.)")
    print(f"Механизмов ..... {len(MECHANISMS)}")
    print()

    results = []
    for mech in MECHANISMS:
        r = probe(con, mech, lo, hi)
        results.append((mech, r))
        print(f"{r['verdict']}  {mech['title']}")
        print(f"    вопрос: «{mech['question']}»")
        print(f"    {r['note']}")
        print()
    con.close()

    bad = [m for m, r in results if r["verdict"] != VERDICT_ALIVE]
    alive = len(results) - len(bad)
    print(f"ИТОГ: проверено {len(results)} · живут {alive} · требуют внимания {len(bad)}")
    for m, r in results:
        if r["verdict"] != VERDICT_ALIVE:
            print(f"   {r['verdict']}  {m['title']}")
    return 1 if bad else 0


# ═══════════════════════════════════════════════════════════════════════════
# САМОПРОВЕРКА. Случаи + мутанты.
# Мутант — намеренно испорченная версия проверки. Не упавший мутант означает,
# что проверка на этом месте НИЧЕГО НЕ РАЗЛИЧАЕТ, и это её дефект, а не успех.
# ═══════════════════════════════════════════════════════════════════════════
def _fixture(vessel=True, answerable=True, used_in_window=True, used_before_window=False):
    """База-скелет под один механизм «связь ответа с вопросом»."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, addressed_by TEXT DEFAULT 'backfill', resolved INT DEFAULT 0)")
    con.executemany("INSERT INTO messages (id) VALUES (?)", [(i,) for i in range(1, 201)])
    if vessel:
        con.execute("CREATE TABLE message_thread (message_id INTEGER PRIMARY KEY, reply_to INTEGER)")
        if answerable:
            if used_in_window:
                con.execute("INSERT INTO message_thread VALUES (195, 100)")
            if used_before_window:
                con.execute("INSERT INTO message_thread VALUES (10, 5)")
        else:
            # сосуд есть, но reply_to везде пуст — заявленный ответ не существует
            con.execute("INSERT INTO message_thread VALUES (195, NULL)")
    con.commit()
    return con


THREAD = MECHANISMS[0]


def _self_test() -> int:
    cases = []

    def case(name, con, expect, mech=THREAD, window=50):
        lo, hi = window_bounds(con, window)
        got = probe(con, mech, lo, hi)["verdict"]
        cases.append((name, expect, got, got == expect))

    # ① базовый: всё на месте и употребляется
    case("сосуд есть, ответ есть, употребляется", _fixture(), VERDICT_ALIVE)
    # ② различающий: сосуда нет вовсе — НЕ то же самое, что «не пользуются»
    case("сосуда нет", _fixture(vessel=False), VERDICT_NO_VESSEL)
    # ③ ГЛАВНЫЙ различающий — случай TAXO #3101: пометка ставится, ответа нет
    con = _fixture()
    con.execute("UPDATE messages SET addressed_by='field' WHERE id > 150")
    con.commit()
    case("пометка заполняется, а запроса-ответа нет (случай --to)",
         con, VERDICT_NO_ANSWER, mech=MECHANISMS[1])
    # ④ различающий на ОКНО: механизм РАБОЧИЙ (связи есть вне окна), но в окне 0
    #
    # 🪤 ЗДЕСЬ БЫЛ МОЙ СЛУЧАЙ, КОТОРЫЙ ПРОВАЛИЛСЯ ПРИ ПЕРВОМ ЖЕ ПРОГОНЕ, и прав оказался
    # код, а не моё ожидание. Я завёл отдельный случай «сосуд есть, в окне 0» на базе,
    # где связей не было ВООБЩЕ НИ ОДНОЙ — и ждал мягкого «не употребляется». Но механизм,
    # у которого за всю историю нет ни одной связи, ОТВЕТИТЬ НЕ МОЖЕТ, и красное здесь
    # честнее жёлтого. Случай оказался неотличим от ⑤ ниже и убран как дубль.
    # ⇒ Различие «не пользуются В ОКНЕ» существует только там, где механизм уже доказал,
    #   что отвечать умеет. Ровно поэтому фикстура ниже кладёт связь ВНЕ окна.
    case("механизм рабочий (связь есть вне окна), но в окне 0",
         _fixture(used_in_window=False, used_before_window=True), VERDICT_UNUSED)
    # ⑥ различающий: запрос предъявлен, но пуст на всей базе
    case("запрос-ответ пуст на всей базе", _fixture(answerable=False), VERDICT_NO_ANSWER)

    print("СЛУЧАИ")
    for name, exp, got, ok in cases:
        print(f"  {'✅' if ok else '❌'} {name}\n       ждали {exp} · получили {got}")
    failed = [c for c in cases if not c[3]]

    # ── МУТАНТЫ ──
    print("\nМУТАНТЫ (каждый обязан упасть хотя бы на одном случае)")
    mutants = []

    def mutant(name, fn, what):
        survivors = []
        for cname, con, mech, window, expect in _mutant_bench():
            lo, hi = window_bounds(con, window)
            try:
                if fn(con, mech, lo, hi) == expect:
                    survivors.append(cname)
            except Exception:
                pass
        mutants.append((name, what, len(survivors) < len(_mutant_bench())))

    def m_count_only(con, mech, lo, hi):
        """M1: меряет ЗАПОЛНЕННОСТЬ пометки вместо способности ответить."""
        used = con.execute(mech["usage_sql"], dict(lo=lo, hi=hi)).fetchone()[0]
        return VERDICT_ALIVE if used else VERDICT_UNUSED

    def m_whole_table(con, mech, lo, hi):
        """M2: считает по всей таблице, игнорируя окно."""
        return probe(con, mech, 1, hi)["verdict"]

    def m_vessel_is_enough(con, mech, lo, hi):
        """M3: считает существование сосуда достаточным."""
        has = con.execute(mech["vessel_sql"]).fetchone() is not None
        return VERDICT_ALIVE if has else VERDICT_NO_VESSEL

    def m_empty_is_fine(con, mech, lo, hi):
        """M4: пустой ответ считает нормальным."""
        if con.execute(mech["vessel_sql"]).fetchone() is None:
            return VERDICT_NO_VESSEL
        if mech["answer_sql"] is None:
            return VERDICT_NO_ANSWER
        used = con.execute(mech["usage_sql"], dict(lo=lo, hi=hi)).fetchone()[0]
        return VERDICT_ALIVE if used else VERDICT_UNUSED

    for nm, fn, what in [
        ("M1 меряет заполненность вместо ответа", m_count_only,
         "обязан провалить ③ «пометка без ответа» — ровно предсказание TAXO #3101"),
        ("M2 игнорирует окно", m_whole_table, "обязан провалить ④ «рабочий, но в окне 0»"),
        ("M3 сосуд = достаточно", m_vessel_is_enough, "обязан провалить ③, ④, ⑤"),
        ("M4 пустой ответ = норма", m_empty_is_fine, "обязан провалить ⑤ «ответ пуст»"),
    ]:
        mutant(nm, fn, what)

    for name, what, died in mutants:
        print(f"  {'✅ упал' if died else '❌ ВЫЖИЛ'} {name}\n       {what}")
    survivors = [m for m in mutants if not m[2]]

    print(f"\nИТОГ САМОПРОВЕРКИ: случаев {len(cases)} · провалов {len(failed)} · "
          f"мутантов {len(mutants)} · выживших {len(survivors)}")
    if survivors:
        print("⛔ ВЫЖИВШИЙ МУТАНТ = проверка на этом месте ничего не различает")
    return 1 if (failed or survivors) else 0


def _mutant_bench():
    """Один и тот же стенд для всех мутантов: (имя, база, механизм, окно, верный вердикт)."""
    con_addr = _fixture()
    con_addr.execute("UPDATE messages SET addressed_by='field' WHERE id > 150")
    con_addr.commit()
    return [
        ("① всё на месте", _fixture(), THREAD, 50, VERDICT_ALIVE),
        ("② сосуда нет", _fixture(vessel=False), THREAD, 50, VERDICT_NO_VESSEL),
        ("③ пометка без ответа", con_addr, MECHANISMS[1], 50, VERDICT_NO_ANSWER),
        ("④ рабочий, но в окне 0", _fixture(used_in_window=False, used_before_window=True),
         THREAD, 50, VERDICT_UNUSED),
        ("⑤ ответ пуст на всей базе", _fixture(answerable=False), THREAD, 50, VERDICT_NO_ANSWER),
    ]


def main():
    ap = argparse.ArgumentParser(description="Признак «механизм наложен, но не отвечает»")
    ap.add_argument("--db", default=str(LIVE_DB))
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW,
                    help=f"сколько последних записок считать окном (по умолчанию {DEFAULT_WINDOW})")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        sys.exit(_self_test())

    db = Path(a.db)
    if not db.exists():
        print(f"ERR: базы нет: {db}", file=sys.stderr)
        sys.exit(2)
    sys.exit(run(db, a.window))


if __name__ == "__main__":
    main()
