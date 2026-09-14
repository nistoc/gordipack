# -*- coding: utf-8 -*-
r"""remove-rows.py — единственный путь ручного снятия строк из таблицы общей базы,
который оставляет след в audit_log — карточка #612.

БЕДА (карточка #612). Строки из общей базы можно снять рукой (например, обычным
sqlite3 CLI) так, что в audit_log не остаётся ничего: законная убыль (снятие по
слову владельца) становится неотличима от пропажи. 07.09 COORD сняла восемь строк
bridge_reviewed по слову владельца — в журнале ни строки. 14.09 backup-db.py на
годной выгрузке упала кодом 1 «bridge_reviewed −7 строк»: причину пришлось собирать
по ленте вручную, и «семь против восьми» закрылось только сличением с текстом
записки. Этот инструмент — единственное место, которое снимает строки И пишет,
КТО · КОГДА · ЧТО БЫЛО · ПО ЧЬЕМУ СЛОВУ, ОДНОЙ транзакцией со снятием: снятие без
записи в audit_log здесь попросту невозможно — это не два шага, а один.

⛔ РАЗРУШАЮЩЕЕ. Снимать строки этим инструментом на ЖИВОЙ базе — по-прежнему
только по живому слову владельца (rule8-destructive не отменяет этот инструмент,
он только даёт СЛЕД тому снятию, которое и так разрешено). На копиях (учебных,
проверочных) можно свободно — это и есть штатное место его прогона в приёмках.

ЧТО ПИШЕТ В audit_log (действие remove_rows, target = имя таблицы, diff_md):
    снято строк: <N>
    условие: <--where> [<--param>, ...]
    основание: <--basis>

    --- БЫЛО (JSON) ---
    [{"колонка": значение, ...}, ...]                 — ВСЕ снятые строки целиком

Разбирает диапазон "снято строк: N" в backup-db.py (проверка убыли, карточка #612 ②) —
меняя это словосочетание, правь там же (поиск «снято строк:» в backup-db.py).

--table — только существующая таблица (сверяется со sqlite_master, имя в SQL нельзя
параметризовать — потому список белый, а не текстовая склейка). --where — условие
БЕЗ слова WHERE, значения — ТОЛЬКО через --param (плейсхолдеры ?), не текстом внутри
условия: инструмент зовут роли, а не внешние пользователи, но подстановка текстом
в SQL — работа для параметра, а не для f-строки, даже здесь.

🔁 ЗАМЕЧАНИЕ OPSSRE Н2 (приёмка карточки #612, 2026-09-14): «значения только через --param»
было словами, а не проверкой — «--where 1=1 --apply» сняло бы всю таблицу. Теперь:
  · значение текстом в --where (число или строка в кавычках) — отказ ДО соединения;
  · число «?» в --where обязано равняться числу --param — отказ словами, а не ошибкой SQLite;
  · условие подходит под ВСЕ строки непустой таблицы — снятие только с --all-rows
    (показ предупреждает об этом отдельной строкой, последняя строка показа прежняя).

--basis ОБЯЗАТЕЛЕН и не проверяется на смысл (это текст на суждение роли) — но
инструмент отказывает на пустой/пробельной строке: пустое основание неотличимо от
забытого флага.

⚖️ ПО УМОЛЧАНИЮ — ТОЛЬКО ПОКАЗ, НИЧЕГО НЕ СНИМАЕТСЯ (возврат COORD по карточке #612,
разбор границ, 2026-09-14). Инструмент разрушающий, и его настоящее место — живая
база по слову владельца; но снятие не должно быть тем, что случается САМО, стоит
только позвать инструмент с правильными --table/--where. БЕЗ --apply инструмент
только СЧИТАЕТ и ПЕЧАТАЕТ (таблицу, число подходящих строк, первые из них, основание)
и выходит кодом 0 — ни DELETE, ни запись в audit_log не исполняются вовсе (не «выполнено
и откачено» — этот путь их просто не зовёт). Последняя строка показа всегда:
    ничего не снято: для снятия добавь --apply
Снятие — ТОЛЬКО с --apply. --dry-run (флаг заведён модулем dryrun.py — тем же, что
у track.py/save-phoenix.py, для единого вида CLI контура) оставлен СИНОНИМОМ
показа: --apply --dry-run вместе — всё равно показ, --dry-run сильнее (см.
write_mode в main()). ⚠️ Показ НЕ идёт через dryrun.connect(dry=True): у того
своя печать банера ДВАЖДЫ, включая atexit ПОСЛЕ возврата из main — последней
строкой оказался бы чужой банер, а не «ничего не снято…». Показ — отдельное,
заведомо ТОЛЬКО ЧИТАЮЩЕЕ соединение (mode=ro): писать физически некуда, это не
«выполнено и откачено».

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/remove-rows.py \
        --table bridge_reviewed --where "message_id IN (?,?,?)" \
        --param 4901 --param 4902 --param 4903 \
        --actor COORD --basis "слово владельца, чат COORD 2026-09-07 09:12 UTC: «снять восемь отметок»"
        # ↑ покажет, что снимется. Добавь --apply, чтобы снять по-настоящему.
"""
import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dryrun                         # noqa: E402
from mezo_paths import resolve_db     # noqa: E402  R15a: путь к БД — от расположения скрипта


def find_table(conn: sqlite3.Connection, table: str):
    """→ True, если имя таблицы есть в sqlite_master. Белый список, не догадка:
    имя таблицы нельзя передать параметром ?, поэтому в SQL оно идёт f-строкой —
    и вставлять туда можно только то, что база сама подтвердила как своё имя."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    return row is not None


def select_rows(conn: sqlite3.Connection, table: str, where: str, params: tuple):
    """→ (имена_колонок, список_словарей) — строки, подходящие под условие, ДО снятия."""
    cur = conn.execute(f'SELECT * FROM "{table}" WHERE {where}', params)
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, row)) for row in cur.fetchall()]
    return cols, rows


def build_diff_md(table: str, where: str, params: tuple, basis: str, old_rows: list) -> str:
    """Тело записи audit_log. Первая строка «снято строк: N» — якорь, по которому
    backup-db.py разбирает названную убыль (карточка #612 ②); менять форму этой
    строки нельзя, не поправив разбор там же."""
    param_note = f" [{', '.join(map(repr, params))}]" if params else ""
    old_json = json.dumps(old_rows, ensure_ascii=False, default=str, indent=None)
    return (f"снято строк: {len(old_rows)}\n"
            f"условие: {where}{param_note}\n"
            f"основание: {basis}\n\n"
            f"--- БЫЛО (JSON) ---\n{old_json}")


PREVIEW_ROWS = 5   # «первые строки» показа — не все: сколько нужно, чтобы узнать условие глазами

# Значение ТЕКСТОМ в условии: строка в кавычках или отдельное число. Имя колонки с цифрой
# внутри («col2») не задевает: граница слова между буквой и цифрой не проходит.
LITERAL_IN_WHERE = re.compile(r"""['"]|\b\d+(?:\.\d+)?\b""")


def where_refusal(where: str, params: list):
    """→ текст отказа или None. Судит ФОРМУ условия до всякого соединения с базой."""
    if LITERAL_IN_WHERE.search(where):
        return ("в --where значение текстом (число или строка в кавычках) — значения только"
                " через плейсхолдер ? и --param")
    if where.count("?") != len(params):
        return (f"в --where плейсхолдеров ? — {where.count('?')}, а --param — {len(params)}:"
                " число должно совпадать")
    return None


def preview(table: str, where: str, params: tuple, basis: str, old_rows: list,
            total: int = 0) -> None:
    """Печать показа (режим без --apply). НЕ пишет никуда — только print(); DELETE
    и INSERT в audit_log этот путь не зовёт вовсе, поэтому проверять тут нечего
    кроме печати."""
    param_note = f" [{', '.join(map(repr, params))}]" if params else ""
    if not old_rows:
        print(f"ℹ️ ни одной строки в «{table}» не подошло под условие «{where}»{param_note}"
              " — снимать нечего")
    else:
        print(f"Показ (без --apply — НИЧЕГО НЕ СНЯТО): «{table}», условие «{where}»{param_note}"
              f" — подходит {len(old_rows)} строк(и)")
        print(f"   основание: {basis}")
        print("   первые строки:")
        for row in old_rows[:PREVIEW_ROWS]:
            print("      " + json.dumps(row, ensure_ascii=False, default=str))
        if len(old_rows) > PREVIEW_ROWS:
            print(f"      … и ещё {len(old_rows) - PREVIEW_ROWS}")
        if total and len(old_rows) == total:
            print(f"⚠️ условие подходит под ВСЕ {total} строк таблицы — для снятия понадобится"
                  " ещё --all-rows")
    print("ничего не снято: для снятия добавь --apply")


def remove_rows(conn: sqlite3.Connection, actor: str, table: str, where: str,
                params: tuple, basis: str, allow_all_rows: bool = False):
    """Снять строки и записать audit_log ОДНОЙ транзакцией. → (число_снятых, diff_md)
    либо (0, None), если снимать было нечего (условию не подошла ни одна строка —
    тогда DELETE и запись в audit_log вовсе не исполняются: убыли не было, и
    журналу нечего называть). Условие под ВСЕ строки непустой таблицы — отказ
    (RuntimeError), если не allow_all_rows: снятие всей таблицы не случается по
    небрежному условию."""
    cols, old_rows = select_rows(conn, table, where, params)
    if not old_rows:
        return 0, None
    total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
    if len(old_rows) == total and not allow_all_rows:
        raise RuntimeError(
            f"условие подходит под ВСЕ {total} строк «{table}» — снятие всей таблицы только"
            f" с --all-rows; ничего не снято")
    cur = conn.execute(f'DELETE FROM "{table}" WHERE {where}', params)
    removed = cur.rowcount
    if removed != len(old_rows):
        # Расхождение внутри ОДНОГО соединения без параллельного писателя не должно
        # случиться никогда; если случилось — останавливаемся, а не пишем неверное
        # число в audit_log. Не commit(), а исключение — верхний уровень откатывает.
        raise RuntimeError(
            f"несовпадение: выбрано для снятия {len(old_rows)}, снято DELETE {removed} — "
            f"остановлено ДО записи в audit_log, ничего не сохранено")
    diff_md = build_diff_md(table, where, params, basis, old_rows)
    conn.execute(
        "INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
        (actor, "remove_rows", table, diff_md))
    return removed, diff_md


def main():
    ap = argparse.ArgumentParser(
        description="Снять строки из таблицы общей базы — со следом в audit_log (карточка #612)."
                    " По умолчанию — только показ; снятие требует --apply")
    dryrun.add_argument(ap)
    ap.add_argument("--apply", action="store_true",
                    help="снять строки по-настоящему. Без этого флага — только показ (что "
                         "снялось бы), код 0, ничего не пишется ни в одну таблицу")
    ap.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    ap.add_argument("--table", required=True, help="имя таблицы, из которой снимаются строки")
    ap.add_argument("--where", required=True,
                    help="условие SQL БЕЗ слова WHERE, значения — плейсхолдерами ? и --param, "
                         "не текстом внутри условия")
    ap.add_argument("--param", action="append", default=[],
                    help="значение плейсхолдера ? из --where, по порядку; можно повторять")
    ap.add_argument("--actor", required=True, help="роль, что снимает строки (пишется в audit_log)")
    ap.add_argument("--basis", required=True,
                    help="основание: чьё слово, где сказано, в какой час — текстом. Обязателен "
                         "даже для показа: показ тоже печатает основание")
    ap.add_argument("--all-rows", action="store_true",
                    help="разрешить снятие, если условие подходит под ВСЕ строки таблицы "
                         "(без флага — отказ)")
    args = ap.parse_args()

    if not args.basis.strip():
        sys.exit("⛔ --basis пуст — снятие без основания этим инструментом не делается")
    refusal = where_refusal(args.where, args.param)
    if refusal:
        sys.exit(f"⛔ {refusal}")

    # 🪤 КАРТОЧКА #612 (возврат COORD). --dry-run — СИНОНИМ показа: он сильнее --apply,
    # а не наоборот, иначе «--apply --dry-run» на боевом флаге --apply тихо снимал бы
    # строки вопреки собственному имени флага холостого прогона. Якорь для обратного
    # хода приёмки (bite-remove-rows-shrink.py, «--apply по умолчанию»): строка ниже
    # должна остаться ЕДИНСТВЕННЫМ местом, где решается, писать ли в базу.
    write_mode = args.apply and not args.dry_run

    args.db = str(resolve_db(args.db, __file__, readonly=False))
    if write_mode:
        conn = dryrun.connect(args.db, False, timeout=5)   # dry=False — банер холостого прогона не печатает
    else:
        # Показ — соединение ТОЛЬКО НА ЧТЕНИЕ (mode=ro): писать физически некуда, а не
        # «выполнено и откачено». Заодно — печать без чужого банера холостого прогона
        # (dryrun.py печатает свой ДВАЖДЫ, включая atexit ПОСЛЕ возврата из main): наша
        # строка «ничего не снято: для снятия добавь --apply» обязана быть ПОСЛЕДНЕЙ.
        conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")

    if not find_table(conn, args.table):
        known = sorted(r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"))
        conn.close()
        sys.exit(f"⛔ таблицы «{args.table}» в базе нет. Есть: {', '.join(known)}")

    if not write_mode:
        # Путь показа НЕ зовёт remove_rows() вовсе — ни DELETE, ни INSERT в audit_log
        # здесь не исполняются ни разу, а не «исполняются и откатываются» (двойная
        # защита: dryrun.connect выше и так откатил бы, но этот путь и не пробует).
        try:
            _, old_rows = select_rows(conn, args.table, args.where, tuple(args.param))
            total = conn.execute(f'SELECT COUNT(*) FROM "{args.table}"').fetchone()[0]
        except sqlite3.Error as exc:
            conn.close()
            sys.exit(f"⛔ условие не выполнилось: {exc}")
        conn.close()
        preview(args.table, args.where, tuple(args.param), args.basis, old_rows, total)
        return 0

    try:
        removed, diff_md = remove_rows(conn, args.actor, args.table, args.where,
                                       tuple(args.param), args.basis, args.all_rows)
    except sqlite3.Error as exc:
        # Сюда приходит и неверное условие, и отказ записи в audit_log: откат снимает
        # ОБА шага разом — строки остаются на месте (приёмка, случай 11).
        conn.rollback()
        conn.close()
        sys.exit(f"⛔ снятие не выполнено — ничего не сохранено: {exc}")
    except RuntimeError as exc:
        conn.rollback()
        conn.close()
        sys.exit(f"⛔ {exc}")

    if removed == 0:
        conn.close()
        print(f"ℹ️ ни одной строки в «{args.table}» не подошло под условие «{args.where}» — "
              "снимать нечего, audit_log не тронут")
        return 0

    conn.commit()
    conn.close()
    print(f"✅ {args.table}: снято {removed} строк(и); действие remove_rows записано в audit_log "
          f"ОДНОЙ транзакцией со снятием")
    print(f"   основание: {args.basis}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
