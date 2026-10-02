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
④ не трогать: моложе срока · незакрытые обязательства · речь владельца
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
```
⚖️ ПОЧЕМУ «незакрытое обязательство» НЕ определяется полем resolved в одиночку: замер 05.09 —
из 2800 записок старше срока поле снято у ТРЁХ. Поле почти не заполняют, и правило, стоящее
на нём одном, не перенесло бы ничего либо перенесло бы всё. Поэтому обязательство узнаётся
по СРОЧНОСТИ, а не по одной отметке.

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

ПРАВИЛО = "history-compression-policy v2"
СРОК_СУТОК = 7
ПОЛЯ = "id, writer_role, timestamp, body_md, tags, priority, resolved, broadcast, addressed_by"
ССЫЛКА = re.compile(r"#(\d{2,6})")

# Инструменты, которым ОБЯЗАНО быть всё равно, где лежит записка: они разрешают номер
# или читают всю историю. Пока хоть один читает мимо вида и мимо функции — переноса нет.
ЧИТАТЕЛИ_НОМЕРА = (
    ("read-broadcasts.py", "messages_all"),
    ("write-message.py", "mezo_refs"),
    ("check-dangling-refs.py", None),      # свой разбор, проверяется отдельно
)


def отпечаток(conn) -> str:
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


def метки(строка) -> list:
    try:
        return json.loads(строка or "[]")
    except Exception:
        return []


def отобрать(conn) -> tuple[list, dict]:
    """Кого можно унести. Возвращает список номеров и разбор отказов по причинам."""
    кандидаты = conn.execute(
        f"SELECT {ПОЛЯ} FROM messages WHERE timestamp < datetime('now', ?)",
        (f"-{СРОК_СУТОК} days",)).fetchall()

    # На кого ссылается что-то МОЛОЖЕ срока — разговор жив.
    живые_ссылки: set = set()
    for (тело,) in conn.execute(
            "SELECT body_md FROM messages WHERE timestamp >= datetime('now', ?)",
            (f"-{СРОК_СУТОК} days",)):
        живые_ссылки.update(int(n) for n in ССЫЛКА.findall(тело or ""))

    берём, отказ = [], {"речь владельца": 0, "срочное незакрытое": 0, "жив разговор": 0}
    for r in кандидаты:
        mid, _, _, _, tags, priority, resolved = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        if "owner-word" in метки(tags):
            отказ["речь владельца"] += 1
            continue
        if priority == "critical" or (priority == "high" and not resolved):
            отказ["срочное незакрытое"] += 1
            continue
        if mid in живые_ссылки:
            отказ["жив разговор"] += 1
            continue
        берём.append(mid)
    return берём, отказ


def проверить_читателей() -> list:
    """Условие ①: живые инструменты, разрешающие номер, читают через вид или через функцию."""
    беды = []
    for имя, признак in ЧИТАТЕЛИ_НОМЕРА:
        if признак is None:
            continue
        путь = os.path.join(HERE, имя)
        if not os.path.isfile(путь):
            путь = os.path.join(os.path.dirname(HERE), "..", "vnext-tools", имя)
        if not os.path.isfile(путь):
            беды.append(f"{имя}: файла нет — проверить нечем")
            continue
        текст = open(путь, encoding="utf-8", errors="replace").read()
        if признак not in текст:
            беды.append(f"{имя}: не видит архив (нет «{признак}») — после переноса "
                        f"перестанет находить старые номера МОЛЧА")
    return беды


def проверить_ссылки(conn, уносим: set):
    """Условие ②: перенос НЕ ДОЛЖЕН отнять у остающихся записок ни одной разрешимой ссылки.

    🩸 ЗДЕСЬ БЫЛА ОШИБКА ПЕРВОГО ПРОГОНА, И ОНА ИЗ СЕГОДНЯШНЕГО ЖЕ КЛАССА: проверка сравнивала
    ссылки с тем, что ЕСТЬ в базе, и краснела на номерах, которых не было НИКОГДА (в текстах
    попадаются просто числа: «15803», «263238»). Перенос был ни при чём — красное горело
    по ПОСТОРОННЕЙ причине, а такой отказ учит его обходить.
    ⇒ судим РАЗНИЦУ: что разрешалось ДО и перестало бы разрешаться ПОСЛЕ. Битые и так —
    отдельной строкой как справка, а не как запрет: они битые и без нас."""
    if not уносим:
        return [], []
    остаются = [r[0] for r in conn.execute(
        f"SELECT body_md FROM messages WHERE id NOT IN ({','.join('?' * len(уносим))})",
        tuple(уносим))]
    номера = set()
    for тело in остаются:
        номера.update(int(n) for n in ССЫЛКА.findall(тело or ""))
    было_видно = mezo_refs.existing_ids(conn, номера)
    # После переноса номер разрешается через архив под ТЕМ ЖЕ номером ⇒ остаётся видимым.
    будет_видно = {n for n in номера if n in уносим or n in было_видно}
    return sorted(было_видно - будет_видно), sorted(номера - было_видно)


def перенести(conn, номера, рука: str) -> int:
    n = 0
    for mid in номера:
        r = conn.execute(f"SELECT {ПОЛЯ} FROM messages WHERE id = ?", (mid,)).fetchone()
        if r is None:
            continue
        conn.execute(
            "INSERT INTO messages_archive (id, writer_role, timestamp, body_md, tags, priority, "
            "resolved, broadcast, addressed_by, moved_by, rule) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (*r, рука, ПРАВИЛО))
        conn.execute("DELETE FROM messages WHERE id = ?", (mid,))
        n += 1
    return n


def вернуть(conn, номера=None) -> int:
    """Обратный ход: из архива в живую ленту. Без номеров — возвращает ВСЁ."""
    where, args = ("", ())
    if номера:
        where, args = (f" WHERE id IN ({','.join('?' * len(номера))})", tuple(номера))
    n = 0
    for r in conn.execute(f"SELECT {ПОЛЯ} FROM messages_archive{where}", args).fetchall():
        conn.execute(f"INSERT INTO messages ({ПОЛЯ}) VALUES (?,?,?,?,?,?,?,?,?)", r)
        conn.execute("DELETE FROM messages_archive WHERE id = ?", (r[0],))
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Переносит старые записки ленты в архив (и обратно). "
                    "По умолчанию — ВХОЛОСТУЮ: без --apply база не меняется.")
    ap.add_argument("--apply", action="store_true", help="применить (иначе холостой прогон)")
    ap.add_argument("--unfold", action="store_true", help="ОБРАТНЫЙ ход: вернуть всё из архива")
    ap.add_argument("--role", default="PROTO", help="чья рука переносит")
    ap.add_argument("--limit", type=int, help="перенести не больше стольких (для осторожного шага)")
    ap.add_argument("--db")
    a = ap.parse_args()

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
    print("=" * 78)
    было = отпечаток(conn)
    живых = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    в_архиве = conn.execute("SELECT COUNT(*) FROM messages_archive").fetchone()[0]
    print(f"СЕЙЧАС: живых {живых} · в архиве {в_архиве} · отпечаток вида {было}")

    if a.unfold:
        сколько = в_архиве
        if not a.apply:
            print(f"\n⟨ВХОЛОСТУЮ⟩ вернулось бы {сколько}. Чтобы применить — --unfold --apply")
            return 0
        conn.execute("BEGIN")
        n = вернуть(conn)
        стало = отпечаток(conn)
        if стало != было:
            conn.rollback()
            sys.exit(f"⛔ ОТКАЧЕНО: вид после возврата отдаёт ДРУГОЕ ({было} → {стало}). "
                     f"Обратный ход обязан быть точным — разбирать рукой")
        conn.commit()
        print(f"\n✅ ВЕРНУЛОСЬ {n}. Отпечаток вида не изменился: {стало}")
        return 0

    # ── условие ①: читатели
    беды = проверить_читателей()
    if беды:
        print("\n⛔ ПЕРЕНОСА НЕТ — условие ① правила не выполнено:")
        for б in беды:
            print(f"   🔴 {б}")
        print("   Пока хоть один читатель ищет номер мимо архива, перенос делает ложь молчаливой.")
        return 2
    print("✅ условие ①: читатели номера видят архив")

    берём, отказ = отобрать(conn)
    # Годные считаются ДО предела: иначе отрезанное пределом попадало в «моложе срока»
    # (02.10.2026: 55 настоящих «моложе» печатались как 2864).
    годных = len(берём)
    if a.limit:
        берём = берём[:a.limit]
    print(f"\nОТОБРАНО К ПЕРЕНОСУ: {len(берём)} из {живых}")
    print("НЕ ТРОГАЕМ (условие ④):")
    for причина, n in отказ.items():
        print(f"   · {причина:<22} {n}")
    print(f"   · моложе {СРОК_СУТОК} суток        "
          f"{живых - годных - sum(отказ.values())}")
    if годных > len(берём):
        print(f"ОТЛОЖЕНО ПРЕДЕЛОМ --limit: {годных - len(берём)} годных к переносу — "
              f"следующими шагами")

    if not берём:
        print("\n⚖️ Переносить нечего — и это не ошибка.")
        return 0

    # ── условие ②: ссылки
    потеряно, битые = проверить_ссылки(conn, set(берём))
    if потеряно:
        print("")
        print(f"⛔ ПЕРЕНОСА НЕТ — условие ②: {len(потеряно)} ссылок ПЕРЕСТАЛИ БЫ разрешаться "
              f"именно из-за переноса: {потеряно[:10]}")
        return 2
    print("✅ условие ②: перенос не отнимает НИ ОДНОЙ разрешимой ссылки")
    if битые:
        print(f"   ⚠️ справка, НЕ запрет: {len(битые)} чисел вида «#N» не разрешаются и СЕЙЧАС "
              f"— {битые[:6]}.")
        print("      Это числа в прозе либо давние опечатки; перенос их не делает хуже. Красить")
        print("      ими перенос значило бы гасить его по посторонней причине.")

    if not a.apply:
        print(f"\n⟨ВХОЛОСТУЮ⟩ база не тронута. Перенеслось бы {len(берём)}.")
        print("   Чтобы применить: --apply. Обратный ход: --unfold --apply")
        return 0

    conn.execute("BEGIN")
    n = перенести(conn, берём, a.role.upper())
    стало = отпечаток(conn)
    if стало != было:
        conn.rollback()
        sys.exit(f"⛔ ОТКАЧЕНО: вид после переноса отдаёт ДРУГОЕ ({было} → {стало}). "
                 f"Перенос обязан быть незаметен для читателя вида — разбирать рукой")
    conn.commit()
    print(f"\n✅ ПЕРЕНЕСЕНО {n}. Отпечаток вида не изменился: {стало}")
    print(f"   живых {conn.execute('SELECT COUNT(*) FROM messages').fetchone()[0]} · "
          f"в архиве {conn.execute('SELECT COUNT(*) FROM messages_archive').fetchone()[0]}")
    print("   обратный ход: messages-fold.py --unfold --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())
