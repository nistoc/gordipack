"""machine_layer.py — МАШИННЫЙ СЛОЙ ПАМЯТИ РОЛИ: собирается, а не хранится.

СЛОВО ВЛАДЕЛЬЦА 2026-08-08 11:19 UTC: «разрешаю врезку в живой инструмент для работы
памяти». Предмет — пункт 2.5 плана v-next, карточка #128. Разбор — записка #3397.

ЗАЧЕМ. Память роли смешивает три сорта знания, и хуже всего стареет тот, который машина
знает САМА: докуда дочитана лента, кто звал лично, что изменилось в своде. Роль переписывает
это руками при остановке — и назавтра оно уже неправда.

    Этот блок НЕ ХРАНИТСЯ НИГДЕ. Он пересобирается при каждом чтении памяти —
    и потому протухнуть НЕ МОЖЕТ ПО ПОСТРОЕНИЮ. Не дисциплиной. Устройством.

📏 ЗАМЕР, НА КОТОРОМ ВРЕЗКА СТОИТ (2026-08-08): памяти всех ролей — 260 КБ, 63 секции,
читает каждая роль при каждом пробуждении; постоянная проверка находит 11 производных
фактов, хранимых руками (хэши, «ahead числом»), — каждый врёт, как только мир сдвинулся.
За сутки 07.08 память дважды показала хрупкость: секция обнулилась молча, а сторож
свежести гасился простым пересохранением.

⛔ ГРАНИЦЫ, НАЗВАННЫЕ ДО ВОПРОСА:
· блок знает БАЗУ и не знает ДИСКА: состояние репозиториев и живость сервисов сюда не
  входят и здесь НЕ подразумеваются. Это напечатано, а не умолчано;
· он НЕ ДУБЛИРУЕТ §4½ (открытые карточки): там свой сборщик, и две витрины одного предмета
  расходятся молча — класс, за который контур уже платил;
· падение сборщика НЕ ДОЛЖНО ронять слепок: слепок — первый экран воскресшей роли.
  Поэтому вызывающая сторона оборачивает вызов, а сам сборщик держит частичный отказ
  внутри и говорит о нём строкой, а не молчанием.
"""
import re
import sqlite3

CC_TAIL = re.compile(r"\bcc\s+@.*", re.S)      # список «в копию» — всё от «cc @» до конца


def _addressed_personally(body: str, role: str) -> bool:
    """Обращение ЛИЧНО, а не упоминание в списке «в копию».

    🪤 Замер 2026-08-08: из 145 чужих записок роль названа в 132, но ОБРАЩАЮТСЯ к ней в 24.
    Первая редакция этого признака смотрела на всю первую строку и дала 76,6 % — потому что
    список «в копию» стоит В ТОЙ ЖЕ строке. Отсечь его надо ДО, а не после.
    """
    head = CC_TAIL.sub(" ", body or "").split("\n")[0]
    return bool(re.search(rf"@{role}\b", head, re.I))


def machine_block(db_path, role: str) -> list:
    """→ строки машинного слоя. Никогда не бросает: частичный отказ печатается строкой."""
    out = []
    try:
        conn = sqlite3.connect(f"file:{str(db_path).replace(chr(92), '/')}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=ON")
    except sqlite3.Error as e:                                        # noqa: BLE001
        return [f"⚠️ машинный слой НЕ СОБРАН: база не открылась ({e}). Это НЕ «всё в порядке»."]

    # ── ЛЕНТА: где роль стоит и сколько должна ──────────────────────────────
    try:
        cur = conn.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                           (role,)).fetchone()
        head = conn.execute("SELECT MAX(id) FROM messages").fetchone()[0]
        if cur is None:
            out.append("⚠️ отметки прочитанного у роли НЕТ — она не заведена, сообщи координатору")
        else:
            n, kb = conn.execute(
                "SELECT COUNT(*), COALESCE(SUM(length(body_md)), 0) / 1024 "
                "FROM messages WHERE id > ?", (cur[0],)).fetchone()
            out.append(f"📬 ЛЕНТА: отметка #{cur[0]} · голова #{head} · долг {n} записок ({kb} КБ)")
            personal = [(mid, w) for mid, w, b in conn.execute(
                "SELECT id, writer_role, body_md FROM messages WHERE id > ? AND writer_role <> ?",
                (cur[0], role)) if _addressed_personally(b, role)]
            if personal:
                tail = " ".join(f"#{m}[{w}]" for m, w in personal[-8:])
                out.append(f"   🎯 обращались ЛИЧНО (не «в копию»): {len(personal)} → {tail}")
            else:
                out.append("   лично не обращался никто — проверено запросом, а не молчанием")
    except sqlite3.Error as e:                                        # noqa: BLE001
        out.append(f"⚠️ положение в ленте НЕ СОБРАНО ({e})")

    # ── СВОЙ СЛЕД: последняя записка старше памяти ──────────────────────────
    try:
        last = conn.execute(
            "SELECT id, timestamp FROM messages WHERE writer_role=? ORDER BY id DESC LIMIT 1",
            (role,)).fetchone()
        newest_sec = conn.execute("SELECT MAX(saved_at) FROM phoenix WHERE role=?",
                                  (role,)).fetchone()[0]
        if last:
            line = f"📝 ПОСЛЕДНЯЯ СВОЯ ЗАПИСКА: #{last[0]} от {last[1][:16]} UTC"
            if newest_sec and last[1] > newest_sec:
                line += "\n   ⚠️ ОНА НОВЕЕ СОХРАНЁННОЙ ПАМЯТИ — ЧИТАЙ ЕЁ ПЕРВОЙ: память сохраняется ДО " \
                        "последней записки, и отозванное в ней живёт как факт"
            out.append(line)
    except sqlite3.Error as e:                                        # noqa: BLE001
        out.append(f"⚠️ свой след НЕ СОБРАН ({e})")

    # ── СВОД: что изменилось после сохранения памяти ────────────────────────
    try:
        oldest = conn.execute("SELECT MIN(saved_at) FROM phoenix WHERE role=?",
                              (role,)).fetchone()[0]
        if oldest:
            fresh = conn.execute(
                "SELECT rule_key, version FROM rules WHERE updated_at > ? "
                "ORDER BY updated_at DESC", (oldest,)).fetchall()
            if fresh:
                names = " · ".join(f"{k} v{v}" for k, v in fresh[:8])
                more = f" · …ещё {len(fresh) - 8}" if len(fresh) > 8 else ""
                out.append(f"📜 ПРАВИЛА, ПРАВЛЕННЫЕ ПОСЛЕ САМОГО СТАРОГО РАЗДЕЛА ПАМЯТИ: "
                           f"{len(fresh)}\n   {names}{more}")
            else:
                out.append("📜 свод не менялся с момента сохранения памяти")
    except sqlite3.Error as e:                                        # noqa: BLE001
        out.append(f"⚠️ свежесть свода НЕ СОБРАНА ({e})")

    # ── СВОИ КАРТОЧКИ: собираются машиной, а значит хранить их в тексте НЕ НАДО ──
    # 🎯 МЕРА ① ВАРИАНТА А (слово владельца 2026-08-08 16:19 UTC): не хранить то, что машина
    # соберёт сама. Список задач роли лежал ПРОЗОЙ в §state у каждого — и протухал первым:
    # 08.08 у PROTO в слепке стояли номера, часть которых уже закрыта чужой рукой.
    # ⚖️ Хранимая копия списка не может быть свежее списка. Значит её место — не в памяти.
    try:
        rows = conn.execute(
            "SELECT id, status, title, done_when FROM backlog "
            "WHERE role=? AND status NOT IN ('done','rejected','closed','dropped') "
            "ORDER BY CASE status WHEN 'in_review' THEN 0 ELSE 1 END, id", (role,)).fetchall()
        if rows:
            no_crit = [r[0] for r in rows if not (r[3] or "").strip()]
            out.append(f"📋 ТВОИ ОТКРЫТЫЕ КАРТОЧКИ: {len(rows)} "
                       f"(собрано СЕЙЧАС — в памяти этот список хранить не надо)")
            for i, st, title, _ in rows[:12]:
                out.append(f"   #{i:<4} [{st:9}] {title[:74]}")
            if len(rows) > 12:
                out.append(f"   …ещё {len(rows) - 12}")
            if no_crit:
                out.append(f"   🔴 БЕЗ КРИТЕРИЯ ПРИЁМКИ: {' '.join('#' + str(i) for i in no_crit)}"
                           " — по правилу task-discipline такую карточку НЕЛЬЗЯ закрыть")
        else:
            out.append("📋 открытых карточек нет — проверено запросом, а не молчанием")
    except sqlite3.Error as e:                                        # noqa: BLE001
        out.append(f"⚠️ карточки НЕ СОБРАНЫ ({e})")

    conn.close()
    out.append("⚖️ блок знает БАЗУ, но не ДИСК: состояния репозиториев и живости сервисов "
               "здесь НЕТ — не считай их проверенными")
    return out
