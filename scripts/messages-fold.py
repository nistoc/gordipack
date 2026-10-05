# -*- coding: utf-8 -*-
"""messages-fold — ПЕРЕНОС СТАРЫХ ЗАПИСОК ЛЕНТЫ В АРХИВ И ОБРАТНО (карточка #538 шаг ③ часть ③).

⛔ НИ ОДИН БАЙТ НЕ УДАЛЯЕТСЯ. Записка переезжает из `messages` в `messages_archive` ПОД ТЕМ ЖЕ
НОМЕРОМ, со всеми полями, плюс «когда, чьей рукой и по какому правилу». Ссылка «#N» после
переноса разрешается через scripts/mezo_refs.py и через вид `messages_all` — там же, где
и раньше. Обратный ход (`--unfold`) возвращает записки в живую ленту.

ОСНОВАНИЕ: правило свода history-compression-policy (редакция v2, замок владельца) и слово
COORD по нему — четыре условия, все исполнены ЗДЕСЬ и проверяются ПЕРЕД переносом:
```
① ссылки разрешаются в архив у ВСЕХ читателей ...... шаг «читатели» ниже: перенос отказывается,
                                                     пока живые инструменты читают номер мимо
                                                     вида и мимо функции разрешения
② проверка ссылок ДО переноса ...................... шаг «ссылки»: каждый номер, упомянутый
                                                     в записках, что ОСТАЮТСЯ живыми, обязан
                                                     разрешаться и после переноса
③ обратимость доказана прогоном .................... --unfold возвращает; приёмка гоняет
                                                     полный круг на копии и сверяет отпечаток
④ не трогать: моложе срока · незакрытые обязательства · речь владельца · НЕПРОЧИТАННОЕ
```

━━ КОГО НЕ ТРОГАЕМ, И ПОЧЕМУ ИМЕННО ТАК (условие ④ разобрано поимённо) ━━
```
моложе 7 суток .............. срок из правила. Свежая записка — рабочая, а не история
метка owner-word ............ РЕЧЬ ВЛАДЕЛЬЦА. Никогда, ни при каком возрасте: его слово
                              ищут сплошным запросом по ленте, и найти его обязано ВСЕГДА
приоритет critical .......... обязательство, которое никто не снимал
приоритет high и не снято ... то же, слабее: снятое (resolved=1) переносится
на неё ссылается свежая ..... разговор ЖИВ. Записка, на которую ссылается что-то моложе
                              срока, остаётся рядом со своим разговором
не прочитана хоть одной ..... номер выше наименьшей отметки прочитанного (read_cursors).
ролью                         Это ДОЛГ читателя, а не история: чтение ленты (read-messages.py)
                              и строка «ЛЕНТА» при пробуждении ищут долг только в messages —
                              унесённое они не покажут никогда, а подтверждение прочтения
                              ключом отметило бы непоказанное прочитанным
```
⚖️ ПОЧЕМУ «незакрытое обязательство» НЕ определяется полем resolved в одиночку: замер 05.09 —
из 2800 записок старше срока поле снято у ТРЁХ. Поле почти не заполняют, и правило, стоящее
на нём одном, не перенесло бы ничего либо перенесло бы всё. Поэтому обязательство узнаётся
по СРОЧНОСТИ, а не по одной отметке.

🩸 ПОЧЕМУ ПОЯВИЛОСЬ «НЕПРОЧИТАННОЕ» (карточка #538, слово владельца 2026-10-03 11:45 UTC, чат PROTO,
вариант «перенос не трогает непрочитанное»). Повторная приёмка карточки #466 на копии сегодняшней
базы: следующий шаг без предела уносил 2836 записок, среди них непрочитанные RCC — 533 (лично
к ней 8), CORE и CHROME — по 48. Разбор шага 05.09 считал читателей «номер выше отметки»
целыми ПО ПОСТРОЕНИЮ, полагая, что унесённое всегда старше любой отметки. Для СПЯЩЕЙ роли
это неверно: её отметка старше срока переноса.
⚡ КЛАСС: «старше N суток» ≠ «уже прочитано». Срок хранения ограничивает самый медленный читатель.
💰 ЦЕНА, названная владельцу до выбора: пока роль спит, всё новее её отметки остаётся в ленте —
архив почти не растёт. Кто держит отметку — инструмент печатает при каждом прогоне.
⚖️ ГРАНИЦЫ, названные проверкой 03.10 12:55 UTC (три независимых взгляда на копиях базы):
```
пройдено указателем ..... отрезки kind='declared' (read-messages.py --pass-by-index) считаются
                          прочитанными: роль объявила их пройденными с основанием. Показ «до роли
                          не дошло» писавшему спрашивать ЧЕРЕЗ messages_all — через messages
                          он после переноса теряет унесённое (готового показа в контуре нет)
закрытая роль ........... строка отметки закрытой роли держала бы перенос вечно: инструмент печатает,
                          кто держит. Сегодня у закрытых EYE и GRF строк отметки нет
новая роль .............. заведённая с отметкой 0, она останавливает перенос, пока не дочитает
неподтверждённые ........ объявления (метка ALL) правило «не прочитано» не держит: подтверждение
объявления                необязательно. Их держит читатель — read-broadcasts.py берёт входящие
                          и «ждём» через messages_all (тем же ходом), а условие ① это проверяет
самопроверка ............ считает по каждой роли ИЗ ТЕХ ЖЕ отметок, что и отбор: ловит поломку
                          отбора, но не порчу самих отметок. Отметок нет вовсе — печатается
                          «не проверено», а не «0»
```

⚠️ ЧЕГО ИНСТРУМЕНТ НЕ ДЕЛАЕТ: не решает, пора ли сжимать (это слово COORD по правилу),
не трогает ретро-импорт `messages_history` (другой предмет), не удаляет и не правит тексты.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mezo_refs  # noqa: E402

RULE = "history-compression-policy v2"
AGE_DAYS = 7
FIELDS = "id, writer_role, timestamp, body_md, tags, priority, resolved, broadcast, addressed_by"
REF_PATTERN = re.compile(r"#(\d{2,6})")
UNREAD = "не прочитано"

# Инструменты, которым ОБЯЗАНО быть всё равно, где лежит записка: они разрешают номер
# или читают всю историю. Пока хоть один читает мимо вида и мимо функции — переноса нет.
# Третье поле — судить ли КАЖДЫЙ запрос файла: у read-broadcasts.py весь показ — история,
# у write-message.py живая таблица законна (он в неё пишет), там достаточно функции разрешения.
NUMBER_READERS = (
    ("read-broadcasts.py", "messages_all", True),
    ("write-message.py", "mezo_refs", False),
    ("check-dangling-refs.py", None, False),      # свой разбор, проверяется отдельно
)
# Прямой запрос к живой таблице, а не к виду (messages_all) и не к messages_archive.
DIRECT_QUERY = re.compile(r"\b(?:FROM|JOIN)\s+messages\b(?!_)", re.I)


def fingerprint(conn) -> str:
    """Отпечаток СОДЕРЖИМОГО ленты — без источника и в порядке номеров.

    🩸 ОПЛАЧЕНО ПЕРВЫМ ЖЕ ПЕРЕНОСОМ НА КОПИИ: первая редакция считала отпечаток по
    «source, id» — то есть включала в мерку ровно то поле, которое перенос МЕНЯЕТ по своему
    назначению («live» → «archive»). Инструмент честно откатил верный перенос и сказал
    «вид отдаёт другое». Откат сработал, мерка — нет.
    ⚡ КЛАСС: мерка неизменности включала в себя предмет изменения. Такая мерка не защищает —
    она запрещает работу, и запрет выглядит как срабатывание защиты.
    ⇒ здесь: что записка лежит в архиве, а не в живой ленте, — это и есть цель; читателю вида
    обязано быть всё равно, поэтому источник в отпечаток не входит, а порядок — по номеру."""
    h = hashlib.sha256()
    for row in conn.execute("SELECT id, writer_role, timestamp, body_md, tags, priority, resolved "
                            "FROM messages_all ORDER BY id"):
        h.update(repr(row).encode("utf-8"))
    return h.hexdigest()[:16]


def parse_tags(value) -> list:
    try:
        return json.loads(value or "[]")
    except Exception:
        return []


def read_marks(conn) -> dict | None:
    """Отметки прочитанного всех ролей: роль → номер последней прочитанной записки.
    None — таблицы отметок нет вовсе: тогда «не прочитано» не проверить, и это говорится словами."""
    try:
        return {role: last for role, last in conn.execute(
            "SELECT reader_role, last_read_id FROM read_cursors")}
    except sqlite3.OperationalError:
        return None


def select_candidates(conn, marks: dict) -> tuple[list, dict]:
    """Кого можно унести. Возвращает список номеров и разбор отказов по причинам."""
    candidates = conn.execute(
        f"SELECT {FIELDS} FROM messages WHERE timestamp < datetime('now', ?)",
        (f"-{AGE_DAYS} days",)).fetchall()

    # На кого ссылается что-то МОЛОЖЕ срока — разговор жив.
    live_refs: set = set()
    for (body,) in conn.execute(
            "SELECT body_md FROM messages WHERE timestamp >= datetime('now', ?)",
            (f"-{AGE_DAYS} days",)):
        live_refs.update(int(n) for n in REF_PATTERN.findall(body or ""))

    # Выше наименьшей отметки — кто-то ещё не читал. Ролей нет — читать некому, предела нет.
    floor = min(marks.values()) if marks else None

    chosen, refused = [], {"речь владельца": 0, "срочное незакрытое": 0, "жив разговор": 0,
                           UNREAD: 0}
    for r in candidates:
        mid, _, _, _, tags, priority, resolved = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        if "owner-word" in parse_tags(tags):
            refused["речь владельца"] += 1
            continue
        if priority == "critical" or (priority == "high" and not resolved):
            refused["срочное незакрытое"] += 1
            continue
        if mid in live_refs:
            refused["жив разговор"] += 1
            continue
        if floor is not None and mid > floor:
            refused[UNREAD] += 1
            continue
        chosen.append(mid)
    return chosen, refused


def unread_in_selection(chosen: list, marks: dict) -> dict:
    """Самопроверка ПО КАЖДОЙ роли отдельно, а не через наименьшую отметку: сколько отобранного
    роль ещё не читала. Обязано быть пусто. Считается иначе, чем отбор, — поэтому ловит поломку
    СРАВНЕНИЯ в отборе (условие COORD, записка #5465: «непрочитанных в отборе: 0» по каждой роли).
    ⚠️ Отметки у неё те же, что у отбора: порчу самих отметок она не видит."""
    return {role: n for role, mark in marks.items()
            if (n := sum(1 for mid in chosen if mid > mark))}


def direct_queries(text: str) -> list:
    """Номера строк, где СТРОКОВАЯ постоянная кода читает живую таблицу мимо вида.
    Комментарии не в счёт — разбор дерева, а не поиск по тексту."""
    import ast
    return sorted({node.lineno for node in ast.walk(ast.parse(text))
                   if isinstance(node, ast.Constant) and isinstance(node.value, str)
                   and DIRECT_QUERY.search(node.value)})


def check_readers() -> list:
    """Условие ①: живые инструменты, разрешающие номер, читают через вид или через функцию.

    🩸 ПЕРВАЯ РЕДАКЦИЯ ИСКАЛА СЛОВО В ФАЙЛЕ — и засчитывала read-broadcasts.py по одной функции
    подтверждения, а входящие и «ждём» читали живую таблицу: после шага 02.10.2026 записки #4 и #49
    ушли из входящих восьми ролей, а условие ① печатало ✅ (проверка переноса 03.10 12:55 UTC).
    ⇒ где показ — вся история, судим КАЖДЫЙ запрос (поле strict)."""
    problems = []
    for name, marker, strict in NUMBER_READERS:
        if marker is None:
            continue
        path = os.path.join(HERE, name)
        if not os.path.isfile(path):
            path = os.path.join(os.path.dirname(HERE), "..", "vnext-tools", name)
        if not os.path.isfile(path):
            problems.append(f"{name}: файла нет — проверить нечем")
            continue
        text = open(path, encoding="utf-8", errors="replace").read()
        if marker not in text:
            problems.append(f"{name}: не видит архив (нет «{marker}») — после переноса "
                            f"перестанет находить старые номера МОЛЧА")
        elif strict and (lines := direct_queries(text)):
            problems.append(f"{name}: читает живую таблицу мимо вида (строки {lines}) — после "
                            f"переноса этот показ потеряет унесённое МОЛЧА")
    return problems


def check_refs(conn, moving: set):
    """Условие ②: перенос НЕ ДОЛЖЕН отнять у остающихся записок ни одной разрешимой ссылки.

    🩸 ЗДЕСЬ БЫЛА ОШИБКА ПЕРВОГО ПРОГОНА, И ОНА ИЗ СЕГОДНЯШНЕГО ЖЕ КЛАССА: проверка сравнивала
    ссылки с тем, что ЕСТЬ в базе, и краснела на номерах, которых не было НИКОГДА (в текстах
    попадаются просто числа: «15803», «263238»). Перенос был ни при чём — красное горело
    по ПОСТОРОННЕЙ причине, а такой отказ учит его обходить.
    ⇒ судим РАЗНИЦУ: что разрешалось ДО и перестало бы разрешаться ПОСЛЕ. Битые и так —
    отдельной строкой как справка, а не как запрет: они битые и без нас."""
    if not moving:
        return [], []
    remaining = [r[0] for r in conn.execute(
        f"SELECT body_md FROM messages WHERE id NOT IN ({','.join('?' * len(moving))})",
        tuple(moving))]
    numbers = set()
    for body in remaining:
        numbers.update(int(n) for n in REF_PATTERN.findall(body or ""))
    visible_before = mezo_refs.existing_ids(conn, numbers)
    # После переноса номер разрешается через архив под ТЕМ ЖЕ номером ⇒ остаётся видимым.
    visible_after = {n for n in numbers if n in moving or n in visible_before}
    return sorted(visible_before - visible_after), sorted(numbers - visible_before)


def move_out(conn, ids, hand: str) -> int:
    n = 0
    for mid in ids:
        r = conn.execute(f"SELECT {FIELDS} FROM messages WHERE id = ?", (mid,)).fetchone()
        if r is None:
            continue
        conn.execute(
            "INSERT INTO messages_archive (id, writer_role, timestamp, body_md, tags, priority, "
            "resolved, broadcast, addressed_by, moved_by, rule) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (*r, hand, RULE))
        conn.execute("DELETE FROM messages WHERE id = ?", (mid,))
        n += 1
    return n


def move_back(conn, ids=None) -> int:
    """Обратный ход: из архива в живую ленту. Без номеров — возвращает ВСЁ."""
    where, args = ("", ())
    if ids:
        where, args = (f" WHERE id IN ({','.join('?' * len(ids))})", tuple(ids))
    n = 0
    for r in conn.execute(f"SELECT {FIELDS} FROM messages_archive{where}", args).fetchall():
        conn.execute(f"INSERT INTO messages ({FIELDS}) VALUES (?,?,?,?,?,?,?,?,?)", r)
        conn.execute("DELETE FROM messages_archive WHERE id = ?", (r[0],))
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Переносит старые записки ленты в архив (и обратно). "
                    "По умолчанию — ВХОЛОСТУЮ: без --apply база не меняется.")
    ap.add_argument("--apply", action="store_true", help="применить (иначе холостой прогон)")
    ap.add_argument("--unfold", action="store_true", help="ОБРАТНЫЙ ход: вернуть всё из архива")
    # ⛔ Умолчания у руки НЕТ: имя роли — данные контура, а не свойство этого файла. Рука
    # берётся из вызова: флаг --role, иначе переменная среды MEZO_ROLE. Для --apply она
    # обязательна (в архив пишется, кто унёс), для холостого прогона и --unfold — нет.
    ap.add_argument("--role", default=None,
                    help="чья рука переносит (иначе — переменная среды MEZO_ROLE); "
                         "для --apply обязательна")
    ap.add_argument("--limit", type=int, help="перенести не больше стольких (для осторожного шага)")
    ap.add_argument("--db")
    a = ap.parse_args()

    hand = (a.role or os.environ.get("MEZO_ROLE") or "").strip().upper() or None
    if a.apply and not a.unfold and hand is None:
        print("⛔ ПЕРЕНОСА НЕТ — не названа рука: в архиве остаётся, чья рука унесла записки.\n"
              "   Назови её флагом --role <РОЛЬ> или переменной среды MEZO_ROLE=<РОЛЬ>.\n"
              "   Пример вызова:\n"
              f"      python {os.path.abspath(__file__).replace(os.sep, '/')} --apply "
              "--role <РОЛЬ>\n"
              "   База не тронута. Холостой прогон (без --apply) руки не требует.")
        return 2

    db = os.path.abspath(a.db or os.path.join(os.path.dirname(HERE), "mezosync.db"))
    if not os.path.isfile(db):
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: базы нет: {db}")
    conn = sqlite3.connect(db)
    if "messages_archive" not in {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}:
        sys.exit("⛔ НЕ ЗАПУСТИЛСЯ: архивной таблицы нет. Сначала шаг схемы "
                 "20260905-messages-archive.py")

    print("=" * 78)
    print(f"ПЕРЕНОС ЗАПИСОК {'⟨ОБРАТНЫЙ ХОД⟩' if a.unfold else ''}"
          f"{'' if a.apply else '  ⟨ВХОЛОСТУЮ — база не меняется⟩'}")
    print(f"📂 БАЗА: {db}")
    if not a.unfold:
        print(f"🖐 рука: {hand}" if hand else
              "🖐 рука не названа — для --apply назови её: --role <РОЛЬ> или MEZO_ROLE=<РОЛЬ>")
    print("=" * 78)
    before = fingerprint(conn)
    live_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    archived_count = conn.execute("SELECT COUNT(*) FROM messages_archive").fetchone()[0]
    print(f"СЕЙЧАС: живых {live_count} · в архиве {archived_count} · отпечаток вида {before}")

    if a.unfold:
        count = archived_count
        if not a.apply:
            print(f"\n⟨ВХОЛОСТУЮ⟩ вернулось бы {count}. Чтобы применить — --unfold --apply")
            return 0
        conn.execute("BEGIN")
        n = move_back(conn)
        after = fingerprint(conn)
        if after != before:
            conn.rollback()
            sys.exit(f"⛔ ОТКАЧЕНО: вид после возврата отдаёт ДРУГОЕ ({before} → {after}). "
                     f"Обратный ход обязан быть точным — разбирать рукой")
        conn.commit()
        print(f"\n✅ ВЕРНУЛОСЬ {n}. Отпечаток вида не изменился: {after}")
        return 0

    # ── условие ①: читатели
    problems = check_readers()
    if problems:
        print("\n⛔ ПЕРЕНОСА НЕТ — условие ① правила не выполнено:")
        for p in problems:
            print(f"   🔴 {p}")
        print("   Пока хоть один читатель ищет номер мимо архива, перенос делает ложь молчаливой.")
        return 2
    print("✅ условие ①: читатели номера видят архив")

    marks = read_marks(conn)
    if marks is None:
        print("\n⛔ ПЕРЕНОСА НЕТ — таблицы отметок прочитанного (read_cursors) нет: «не прочитано» "
              "проверить нечем,\n   а уносить, не зная, кто что читал, правило не велит (карточка #538).")
        return 2
    chosen, refused = select_candidates(conn, marks)
    # Годные считаются ДО предела: иначе отрезанное пределом попадало в «моложе срока»
    # (02.10.2026: 55 настоящих «моложе» печатались как 2864).
    eligible = len(chosen)
    if a.limit:
        chosen = chosen[:a.limit]
    print(f"\nОТОБРАНО К ПЕРЕНОСУ: {len(chosen)} из {live_count}")
    print("НЕ ТРОГАЕМ (условие ④):")
    for reason, n in refused.items():
        print(f"   · {reason:<22} {n}")
    print(f"   · моложе {AGE_DAYS} суток        "
          f"{live_count - eligible - sum(refused.values())}")
    if marks:
        floor = min(marks.values())
        holders = sorted(role for role, mark in marks.items() if mark == floor)
        who = "эта роль не дочитает" if len(holders) == 1 else "эти роли не дочитают"
        print(f"   ⚖️ «{UNREAD}» держит отметка прочитанного #{floor} ({', '.join(holders)}): "
              f"новее неё ничего не уносится,\n      пока {who} ленту. Число «{UNREAD}» — после "
              f"прочих причин: отказанное раньше в нём не считается")
    else:
        print(f"   ⚖️ отметок прочитанного нет ни у одной роли — «{UNREAD}» не ограничивает отбор")
    if eligible > len(chosen):
        print(f"ОТЛОЖЕНО ПРЕДЕЛОМ --limit: {eligible - len(chosen)} годных к переносу — "
              f"следующими шагами")

    # ── самопроверка: в отборе нет непрочитанного ни у одной роли (считается по каждой роли)
    unread = unread_in_selection(chosen, marks)
    if unread:
        print("")
        print(f"⛔ ПЕРЕНОСА НЕТ — в отборе есть НЕПРОЧИТАННОЕ: "
              f"{', '.join(f'{role} {n}' for role, n in sorted(unread.items()))}")
        print("   Унесённое не покажет ни чтение ленты, ни строка «ЛЕНТА» при пробуждении.")
        return 2
    if marks:
        print(f"✅ непрочитанных в отборе: 0 (проверено по отметкам {len(marks)} ролей)")
    else:
        print("⚪ непрочитанных в отборе: не проверено — отметок прочитанного нет ни у одной роли "
              "(читать некому)")

    if not chosen:
        print("\n⚖️ Переносить нечего — и это не ошибка.")
        return 0

    # ── условие ②: ссылки
    lost, broken = check_refs(conn, set(chosen))
    if lost:
        print("")
        print(f"⛔ ПЕРЕНОСА НЕТ — условие ②: {len(lost)} ссылок ПЕРЕСТАЛИ БЫ разрешаться "
              f"именно из-за переноса: {lost[:10]}")
        return 2
    print("✅ условие ②: перенос не отнимает НИ ОДНОЙ разрешимой ссылки")
    if broken:
        print(f"   ⚠️ справка, НЕ запрет: {len(broken)} чисел вида «#N» не разрешаются и СЕЙЧАС "
              f"— {broken[:6]}.")
        print("      Это числа в прозе либо давние опечатки; перенос их не делает хуже. Красить")
        print("      ими перенос значило бы гасить его по посторонней причине.")

    if not a.apply:
        print(f"\n⟨ВХОЛОСТУЮ⟩ база не тронута. Перенеслось бы {len(chosen)}.")
        print("   Чтобы применить: --apply. Обратный ход: --unfold --apply")
        return 0

    conn.execute("BEGIN")
    n = move_out(conn, chosen, hand)
    after = fingerprint(conn)
    if after != before:
        conn.rollback()
        sys.exit(f"⛔ ОТКАЧЕНО: вид после переноса отдаёт ДРУГОЕ ({before} → {after}). "
                 f"Перенос обязан быть незаметен для читателя вида — разбирать рукой")
    conn.commit()
    print(f"\n✅ ПЕРЕНЕСЕНО {n}. Отпечаток вида не изменился: {after}")
    print(f"   живых {conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]} · "
          f"в архиве {conn.execute('SELECT COUNT(*) FROM messages_archive').fetchone()[0]}")
    print("   обратный ход: messages-fold.py --unfold --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
