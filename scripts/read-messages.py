"""
read-messages.py — CLI для агента: прочитать непрочитанные сообщения из mezosync.db.

⛔ КОНТРАКТ С 2026-07-16 (П1, слово владельца 18:07 UTC): ЧТЕНИЕ НЕ ДВИГАЕТ КУРСОР.
Ридер печатает ноты и ПОСЛЕДНЕЙ строкой выдаёт одноразовый токен; сдвиг курсора —
ОТДЕЛЬНЫМ вызовом --ack <токен>.

ПОЧЕМУ (дизайн согласован STUD #2068 · CORE #2069 · TAXO #2067, сведён в #2073):
· Старый ридер двигал курсор ПРИ ПЕЧАТИ ⇒ любая обрезка вывода = «прочитано» ложно
  и persistent. За ОДИН час 16.07 в это влетели ПЯТЕРО: CORE (16 нот, среди них
  объявление Фазы 3), TAXO (~310 нот), STUD ×2, GRF. Все аккуратные, никто не хотел.
· Обрезает не только свой пайп — обрезает СРЕДА: harness сохраняет большой вывод
  в файл и показывает превью первых 2 КБ (CORE #2066: «сделал всё по правильному
  рецепту и всё равно ослеп»). Аккуратность не спасает В ПРИНЦИПЕ.
· Токен = СЛУЧАЙНЫЙ nonce, НЕ id и НЕ хеш. Это выяснено дорого, взаимным ломанием:
  --ack <id> сломала TAXO одним SELECT (id вычислим не читая); её хеш-токен сломали
  STUD и CORE тем же SELECT (входы хеша лежат в БД, формула в открытом коде).
  Закон CORE: ПОДТВЕРЖДЕНИЕ, ВЫЧИСЛИМОЕ ИЗ СОСТОЯНИЯ, — НЕ ПОДТВЕРЖДЕНИЕ.
· Токен печатается ПОСЛЕДНЕЙ строкой НАРОЧНО: обрезка (пайп или среда) его прячет ⇒
  чтобы получить токен, придётся дочитать persisted-файл ДО КОНЦА. Позиция — механизм.
ГРАНИЦЫ (честно, обе названы вслух):
· Из #2073: закрывает СЛУЧАЙНУЮ промотку. Роль, которая сознательно перепишет курсор
  своим SQL, не остановит ничто — это не защита от злого умысла.
· tail-зазор ЗАКРЫТ РАЗРЕЗАННЫМ ТОКЕНОМ (18:45 UTC). История, чтобы обход не изобрели
  заново: цельный токен в последней строке ловил потерю ХВОСТА (head/лимит/превью среды),
  но `| tail` отдавал токен, НЕ ДАВ ТЕКСТА. TAXO нашла зазор (#2152) и влетела в него
  же ДВАЖДЫ за 10 минут, ЗНАЯ (#2159) — «назвать вслух» оказалось дисциплиной, а
  дисциплина не масштабируется даже на автора находки. Механизм RCC (#2155): токен из
  ДВУХ половин — первая в ПЕРВОЙ строке вывода, вторая в ПОСЛЕДНЕЙ, --ack требует обе.
  tail прячет первую, head — вторую; обе даёт только ПОЛНЫЙ вывод.
· Середину не гарантирует НИЧТО (граница честно, STUD #2162): токены ловят УСЕЧЕНИЕ
  вывода, а не невнимательность. И всё равно: НЕ конвейерь вывод ридера вообще.
· ДАЛЬШЕ НЕ ЧИНИМ — решение COORD 16.07 19:00 UTC по голосу автора фикса (TAXO #2174,
  пробила свой же фикс `sed -n '1p;$p'` через 2 минуты): гонка «умный вывод против умной
  обрезки» бесконечна (за sed придёт awk). Выборка двух концов — НЕ случайная обрезка,
  а прицельная добыча токена: подтверждаешь непрочитанное СОЗНАТЕЛЬНО, это подлог, не
  промах. Механизм закрыл случайность (5 слепых промоток/час → 0) — на том его граница.

Использование агентом (из Bash tool):
    python read-messages.py --db .mezosync/mezosync.db --role COORD
    python read-messages.py --db .mezosync/mezosync.db --role COORD --ack a1b2c3
    python read-messages.py --db .mezosync/mezosync.db --role CORE --limit 20
    python read-messages.py --db .mezosync/mezosync.db --role STUD --tag TRACK-NEWUX
"""

import argparse
import json
import secrets
import sqlite3
import sys
from pathlib import Path


def utc_to_local(s):
    """UTC → UTC. Оставлено имя ради совместимости вызовов; конвертации БОЛЬШЕ НЕТ.
    Правило timestamp-utc-in-sqlite v2 (владелец 2026-07-16): контур живёт в ОДНОЙ
    шкале — UTC. Две шкалы брали налог вниманием и породили фантом «синк умер 2 часа
    назад» (разница ровно 2ч была ЗОНОЙ, не лагом). Конвертация, которой нет, не может
    быть забыта. Суффикс UTC печатаем явно: метка без зоны неотличима от локальной."""
    return f"{s} UTC" if s else "—"


def ensure_batches_table(conn):
    # Идемпотентно (правило migration-safety): таблица одноразовых токенов чтения.
    conn.execute(
        "CREATE TABLE IF NOT EXISTS read_batches ("
        "  token     TEXT PRIMARY KEY,"
        "  role      TEXT NOT NULL,"
        "  last_id   INTEGER NOT NULL,"
        "  issued_at TEXT NOT NULL DEFAULT (datetime('now')))")
    conn.commit()


def do_ack(conn, role, token):
    row = conn.execute(
        "SELECT last_id FROM read_batches WHERE token = ? AND role = ?",
        (token, role)).fetchone()
    if row is None:
        # Не различаем «чужой»/«потраченный»/«опечатка» — токен одноразовый, детали
        # не помогут, а честная ошибка заставит перечитать батч. Это дешевле ложного OK.
        print(f"⛔ ACK ОТКЛОНЁН: токен «{token}» для роли {role} не найден "
              f"(уже потрачен, чужой или опечатка). Курсор НЕ сдвинут.\n"
              f"   Перечитай батч: python read-messages.py --db <db> --role {role}",
              file=sys.stderr)
        sys.exit(1)
    last_id = row[0]
    cur = conn.execute(
        "SELECT last_read_id FROM read_cursors WHERE reader_role = ?", (role,)).fetchone()
    prev = cur[0] if cur else 0
    # Только вперёд: устаревший токен (курсор уже дальше) сжигаем без отката.
    new = max(prev, last_id)
    conn.execute(
        "UPDATE read_cursors SET last_read_id = ?, updated_at = datetime('now') "
        "WHERE reader_role = ?", (new, role))
    conn.execute("DELETE FROM read_batches WHERE token = ?", (token,))
    conn.commit()
    if new == prev:
        print(f"[ack] {role}: токен погашен, курсор уже был на {prev} — без изменений")
    else:
        print(f"[ack] {role}: {prev} → {new}")


def main():
    parser = argparse.ArgumentParser(description="Прочитать непрочитанные сообщения")
    parser.add_argument("--db", required=True, help="Путь к mezosync.db")
    parser.add_argument("--role", required=True, help="Роль читателя (для курсора)")
    parser.add_argument("--limit", type=int, default=50, help="Максимум сообщений")
    parser.add_argument("--tag", default=None, help="Фильтр по тегу")
    parser.add_argument("--all", action="store_true", help="Все сообщения (игнорировать курсор)")
    parser.add_argument("--ack", default=None, metavar="TOKEN",
                        help="Погасить токен батча и сдвинуть курсор (одноразово)")
    parser.add_argument("--no-advance", action="store_true",
                        help="(устарел, no-op: чтение курсор больше НЕ двигает)")
    parser.add_argument("--register", action="store_true",
                        help="ЯВНО завести курсор новой роли. Без флага незнакомая роль — ошибка.")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERR: БД не найдена: {db_path}", file=sys.stderr)
        sys.exit(1)

    # Регистр роли нормализуется ЗДЕСЬ: reader_role — PRIMARY KEY без COLLATE NOCASE,
    # и «--role eye» до 16.07 молча заводил ВТОРОЙ курсор с нуля (EYE #2063,
    # 8 мёртвых lowercase-строк в read_cursors были именно этим).
    role = args.role.upper()

    conn = sqlite3.connect(str(db_path), timeout=5)
    ensure_batches_table(conn)

    # `is not None`, НЕ truthiness: --ack "" при truthiness МОЛЧА деградирует в обычное
    # чтение — поймано на первом же тесте 16.07 (пустая переменная в bash-подстановке).
    if args.ack is not None:
        do_ack(conn, role, args.ack)
        conn.close()
        return

    # Получить курсор
    cursor_row = conn.execute(
        "SELECT last_read_id FROM read_cursors WHERE reader_role = ?", (role,)
    ).fetchone()

    if cursor_row is None:
        # Незнакомая роль — ОШИБКА, не тихий INSERT. Старый ридер заводил курсор с нуля
        # самим фактом вызова (INSERT стоял ДО проверки флагов) — посмертная находка EYE
        # #2149: он удалил свою строку при закрытии роли, ПРОВЕРИЛ смерть вызовом ридера —
        # и этим вызовом ВОСКРЕСИЛ себя. Роль нельзя было удалить из контура, пока ридер
        # воссоздавал её первым же обращением; опечатка в --role заводила призрака.
        # Новую роль заводит только ЯВНЫЙ --register. Проверять «роли нет» — SELECT'ом.
        if not args.register:
            known = ", ".join(r for r, in conn.execute(
                "SELECT reader_role FROM read_cursors ORDER BY reader_role"))
            print(f"ERR: роль {role} не в реестре курсоров (есть: {known}).\n"
                  f"     Новая роль? Заведи явно: --register. Опечатка? Поправь --role.",
                  file=sys.stderr)
            conn.close()
            sys.exit(1)
        conn.execute(
            "INSERT INTO read_cursors (reader_role, last_read_id) VALUES (?, 0)", (role,)
        )
        conn.commit()
        print(f"[register] курсор роли {role} заведён с 0 (явный --register)")
        last_read = 0
    else:
        last_read = cursor_row[0]

    # Запрос
    if args.all:
        params = []
        conditions = []
    else:
        conditions = ["id > ?"]
        params = [last_read]

    if args.tag:
        conditions.append("tags LIKE ?")
        params.append(f'%"{args.tag}"%')

    sql = "SELECT id, writer_role, timestamp, body_md, tags, priority FROM messages"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    # Порядок — по ВРЕМЕНИ, не по позиции (находка STUD #1960, вариант ①).
    # id вторичен: он лишь тай-брейк внутри одной секунды и носитель курсора.
    sql += f" ORDER BY timestamp ASC, id ASC LIMIT {args.limit}"

    rows = conn.execute(sql, params).fetchall()

    # ⚠️ ОСТАТОК ЗА ЛИМИТОМ — считаем ТЕМ ЖЕ предикатом, что и батч (иначе с --tag соврём).
    #
    # ЗАЧЕМ (запрос CORE #2264 ①, 17.07): «батч, пришедший РОВНО в размер лимита, — это не
    # "всё", это "упёрлось"». Цена уже заплачена: слово STUD по browse лежало в ленте 13 минут,
    # CORE прочитал `--limit 10`, получил ровно 10, за границей осталось 8 — и чуть не
    # отчитался «слова в ленте НЕТ». Каталог простоял 21 минуту.
    #
    # 🔴 И ЭТО ДЕФЕКТ МОЕЙ КОНСТРУКЦИИ, А НЕ РОЛИ — два гарда тянули в разные стороны:
    # правило «читай ЦЕЛИКОМ, не конвейерь» толкает роль СУЖАТЬ лимит (узкий вывод легче
    # дочитать и не потерять половинку токена), а узкий лимит МОЛЧА режет хвост. Роль между
    # ними — единственный арбитр, и арбитраж ей никто не дал.
    # ⚠️ Разрезанный токен здесь НЕ ЗАЩИЩАЕТ: он ловит обрезку КОНВЕЙЕРОМ (половинки прячутся
    # от head/tail), а обрезку ЛИМИТОМ не ловит вовсе — батч прочитан целиком, и `--ack`
    # честен. Зазор лежал РОВНО МЕЖДУ двумя гардами, и потому его не видел ни один.
    #
    # Механизм, а не дисциплина: `SELECT count(*) WHERE <тот же предикат>` знает ответ —
    # молчал только вывод. Роли не надо ничего помнить и не надо считать в уме.
    rest_count = 0
    rest_last = None
    if not args.all and rows and len(rows) == args.limit:
        rest_sql = "SELECT COUNT(*), MAX(id) FROM messages WHERE " + " AND ".join(
            ["id > ?"] + [c for c in conditions if not c.startswith("id > ")])
        rest_params = [max(r[0] for r in rows)] + params[1:]
        rest_count, rest_last = conn.execute(rest_sql, rest_params).fetchone()

    # ГАРД ХРОНОЛОГИИ: курсор — это id, поэтому «id растёт ⇒ время растёт» должно
    # держаться, иначе шаг курсора перепрыгнет непрочитанное. Ретро-импорт 16.07
    # сломал ровно это (TAXO #1952: 11 июля получило id выше сегодняшнего;
    # EYE #1957: дельта-скан отдал 1428 старых нот как «новые»). История с тех пор
    # живёт в отдельной таблице messages_history — читать её ORDER BY timestamp.
    chk = conn.execute(
        "SELECT COUNT(*) FROM (SELECT id, timestamp, "
        "  LAG(timestamp) OVER (ORDER BY id) AS prev FROM messages) "
        "WHERE prev IS NOT NULL AND timestamp < prev").fetchone()[0]
    if chk:
        print(f"⚠️  ВНИМАНИЕ: хронология id сломана ({chk} разрывов) — "
              f"курсор может перепрыгнуть непрочитанное. Не доверяй хвосту, "
              f"читай по дате. Сообщи COORD.\n")

    if not rows:
        print(f"[{role}] Нет непрочитанных сообщений (cursor={last_read})")
        conn.close()
        return

    batch_max = max(r[0] for r in rows)
    issue = not args.all and batch_max > last_read

    # Токен РАЗРЕЗАН на две половины: первая — в ПЕРВОЙ строке вывода, вторая — в
    # ПОСЛЕДНЕЙ, --ack требует склейку. Цельный токен в конце ловил только потерю
    # хвоста; `| tail` отдавал его, не дав текста (TAXO #2152/#2159 — дважды за
    # 10 минут, зная зазор; дизайн половинок — RCC #2155). head прячет вторую
    # половину, tail — первую; обе видны только в ПОЛНОМ выводе.
    if issue:
        # Гигиена: токены старше 7 суток этой роли — мусор от неподтверждённых батчей.
        conn.execute("DELETE FROM read_batches WHERE role = ? "
                     "AND issued_at < datetime('now', '-7 days')", (role,))
        half1, half2 = secrets.token_hex(3), secrets.token_hex(3)
        conn.execute(
            "INSERT INTO read_batches (token, role, last_id) VALUES (?, ?, ?)",
            (f"{half1}-{half2}", role, batch_max))
        conn.commit()
        print(f"[begin-of-batch] {len(rows)} нот, #{rows[0][0]}…#{batch_max} (cursor={last_read}). "
              f"Токен разрезан: ПЕРВАЯ половина {half1}, вторая — в ПОСЛЕДНЕЙ строке.")
        if rest_count:
            print(f"⚠️  БАТЧ УПЁРСЯ В ЛИМИТ (--limit {args.limit}): за ним ещё {rest_count} нот "
                  f"(последняя #{rest_last}). Это НЕ «всё» — это «упёрлось».\n"
                  f"   Подтвердишь этот батч — курсор встанет на #{batch_max}, остаток НЕ пропадёт: "
                  f"зови ридер снова. Нужен весь хвост сразу — --limit {rest_count + len(rows)}.")
        print()

    for row in rows:
        msg_id, writer, ts, body, tags, priority = row
        prio_mark = "" if priority == "normal" else f" ⚠️{priority}"
        tags_list = json.loads(tags) if tags else []
        tags_str = " ".join(f"[{t}]" for t in tags_list)
        print(f"--- #{msg_id} [{writer}] {utc_to_local(ts)}{prio_mark} {tags_str}")
        print(body)
        print()

    if issue:
        # Остаток печатаем и ЗДЕСЬ, у самой команды --ack: ack — это момент решения «я всё
        # прочитал». Сигнал в начале батча роль увидит ДО чтения тел и к концу забудет —
        # а забыть здесь стоило контуру 21 минуту (CORE #2264 ①).
        tail = (f"\n⚠️  И ПОМНИ: за этим батчем ещё {rest_count} нот (последняя #{rest_last}) — "
                f"батч упёрся в --limit {args.limit}, это НЕ конец ленты. "
                f"ACK честен (батч прочитан целиком), но хвост НЕ прочитан.") if rest_count else ""
        print(f"[end-of-batch] Прочитал ЦЕЛИКОМ — подтверди СКЛЕЙКОЙ обеих половин "
              f"(первая — в ПЕРВОЙ строке вывода):\n"
              f"  python read-messages.py --db {args.db} --role {role} --ack <первая>-{half2}{tail}")
    elif args.all:
        print(f"[--all] разведка без курсора: {len(rows)} нот, токен не выдан")

    conn.close()


if __name__ == "__main__":
    main()
