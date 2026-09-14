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
· он НЕ ДУБЛИРУЕТ §4½ (открытые карточки): там свой сборщик, и две сводки одного предмета
  расходятся молча — класс, за который контур уже платил;
· падение сборщика НЕ ДОЛЖНО ронять сохранённую память: она — первый экран воскресшей роли.
  Поэтому вызывающая сторона оборачивает вызов, а сам сборщик держит частичный отказ
  внутри и говорит о нём строкой, а не молчанием.
"""
import re
import sqlite3
from pathlib import Path

CC_TAIL = re.compile(r"\bcc\s+@.*", re.S)      # список «в копию» — всё от «cc @» до конца
OWN_NOTES_SHOWN = 10    # своих записок после записи памяти строками; остальные — одной командой


def _addressed_personally(body: str, role: str) -> bool:
    """Обращение ЛИЧНО, а не упоминание в списке «в копию».

    🪤 Замер 2026-08-08: из 145 чужих записок роль названа в 132, но ОБРАЩАЮТСЯ к ней в 24.
    Первая редакция этого признака смотрела на всю первую строку и дала 76,6 % — потому что
    список «в копию» стоит В ТОЙ ЖЕ строке. Отсечь его надо ДО, а не после.
    """
    head = CC_TAIL.sub(" ", body or "").split("\n")[0]
    return bool(re.search(rf"@{role}\b", head, re.I))


def _own_notes_command(db_path, role: str, since: str, total: int) -> str:
    """Команда, печатающая ВСЕ свои записки после записи памяти, — исполнимая как напечатана.

    Путь к db-q.py — от расположения ЭТОГО модуля, а не голым именем: роль копирует строку
    из того, что читает, и голое имя из чужого рабочего каталога не запустится. --db — только
    если база не та, что рядом со скриптами (песочница, стенд): иначе команда молча читала бы
    другую базу. --limit — ровно число записок: предел по умолчанию живёт в db-q.py, здесь его
    не повторяем.
    """
    here = Path(__file__).resolve().parent
    db = Path(str(db_path)).resolve()
    cmd = f"python {(here / 'db-q.py').as_posix()}"
    if db != (here.parent / "mezosync.db").resolve():
        cmd += f" --db {db.as_posix()}"
    who = role.replace("'", "''")
    return (f'{cmd} --limit {total} "SELECT id, timestamp, replace(substr(body_md, 1, 160), '
            f"char(10), ' ') FROM messages_all WHERE writer_role='{who}' AND timestamp > '{since}' "
            f'ORDER BY id"')


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

    last = None     # нужна и блоку «свои записки после записи памяти», даже если запрос упал
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

    # ── СВОИ ЗАПИСКИ ПОСЛЕ ЗАПИСИ ПАМЯТИ: все, а не одна последняя ─────────────
    # 🩸 Карточка #466 ③, разбор OPSSRE (записка #5188), заказ PROTO (записка #5189 ②).
    # Строка выше называет ОДНУ последнюю записку, а 14.09 у COORD после записи раздела state
    # их было 40 — тридцать девять к роли при пробуждении не возвращались ничем.
    # ⚖️ Отсчёт — от раздела state (с отметкой «правок нет», карточка #160), а не от самого
    # нового раздела: положение дел живёт в state, и свежий мелкий раздел не значит, что оно
    # переписано (тот же замер: после самого нового раздела у COORD 16 записок, после state — 40).
    # Источник — messages_all: записка, унесённая в архив по возрасту, своей быть не перестаёт.
    try:
        mark = conn.execute(
            "SELECT COALESCE(confirmed_at, saved_at) FROM phoenix WHERE role=? AND section='state'",
            (role,)).fetchone()
        mark_name = "state"
        if not mark:
            mark = conn.execute("SELECT MAX(COALESCE(confirmed_at, saved_at)) FROM phoenix "
                                "WHERE role=?", (role,)).fetchone()
            mark_name = "самый новый раздел — раздела state нет"
        since = mark[0] if mark else None
        own = conn.execute(
            "SELECT id, timestamp, body_md FROM messages_all WHERE writer_role=? AND timestamp > ? "
            "ORDER BY id", (role, since)).fetchall() if since else []
        if own:
            lead = "   " if last else "📝 "
            out.append(f"{lead}после записи памяти ({mark_name}, {since[:16]} UTC) твоих записок "
                       f"{len(own)} — читай их первыми:")
            for note_id, stamp, body in own[-OWN_NOTES_SHOWN:]:
                first = (body or "").strip().split("\n")[0].lstrip("# ").strip()
                out.append(f"     #{note_id} {stamp[:16]}  {first[:90]}")
            if len(own) > OWN_NOTES_SHOWN:
                out.append(f"     и ещё {len(own) - OWN_NOTES_SHOWN} раньше — все одной командой:")
                out.append(f"     {_own_notes_command(db_path, role, since, len(own))}")
    except (sqlite3.Error, OSError) as e:                             # noqa: BLE001
        out.append(f"⚠️ свои записки после записи памяти НЕ СОБРАНЫ ({e})")

    # ── СВОД: что изменилось после сохранения памяти ────────────────────────
    try:
        oldest = conn.execute("SELECT MIN(saved_at) FROM phoenix WHERE role=?",
                              (role,)).fetchone()[0]
        if oldest:
            # ⚰️ Карточка #517: СНЯТОЕ ПРАВИЛО ПОМЕЧАЕТСЯ ЗДЕСЬ ЖЕ. Найдено TAXO
            # (записка #4619) замером памятей девяти ролей: у ВСЕХ девяти в этой строке
            # стояли три снятых правила вперемешку с живыми, без единого признака.
            # Формально строка была права — снятие тоже правка, — но роль читает её как
            # «вот что изменилось, сходи посмотри», и три имени из восьми вели к надгробиям.
            # ⚡ Класс: УКАЗАТЕЛЬ, НЕ РАЗЛИЧАЮЩИЙ ЖИВОЕ И МЁРТВОЕ, ПОСЫЛАЕТ УЧИТЬСЯ
            # У ОТМЕНЁННОГО — и делает это голосом механизма, то есть убедительно.
            fresh = conn.execute(
                "SELECT rule_key, version, COALESCE(status,'active') FROM rules "
                "WHERE updated_at > ? ORDER BY updated_at DESC", (oldest,)).fetchall()
            if fresh:
                dead_count = sum(1 for _, _, st in fresh if st != "active")
                names = " · ".join(
                    (f"⚰️{k} v{v} ({st})" if st != "active" else f"{k} v{v}")
                    for k, v, st in fresh[:8])
                more = f" · …ещё {len(fresh) - 8}" if len(fresh) > 8 else ""
                dead_note = (f"\n   ⚰️ из них СНЯТЫХ: {dead_count} — идти по ним незачем, там "
                             f"надгробие, а не действующее требование" if dead_count else "")
                out.append(f"📜 ПРАВИЛА, ПРАВЛЕННЫЕ ПОСЛЕ САМОГО СТАРОГО РАЗДЕЛА ПАМЯТИ: "
                           f"{len(fresh)}\n   {names}{more}{dead_note}")
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

    # ── ЧУЖАЯ РАБОТА, ИДУЩАЯ ПРЯМО СЕЙЧАС ───────────────────────────────────
    # 🪤 Найдено владельцем 19.08 08:30 UTC: роль работала час — учебное восстановление
    # базы, — и контур узнал об этом только из её итоговой записки. Никто не мог ни
    # подождать, ни не браться за то же: «в работе» ставили ТРИ раза за месяц (замер:
    # 3 перевода против 142 закрытий), потому что состояние ничего не давало ставящему.
    # ⇒ Объявленная работа показывается КАЖДОМУ при пробуждении, и это единственное место,
    # куда роль смотрит раньше, чем начинает свою.
    try:
        claims = conn.execute(
            "SELECT e.backlog_id, e.actor_role, e.body_md, e.at, b.title FROM backlog_events e"
            " JOIN backlog b ON b.id = e.backlog_id"
            " WHERE e.event_type = 'claim' AND e.at > datetime('now', '-24 hours')"
            " ORDER BY e.at DESC").fetchall()
        live_claims = []
        for bid, who, body, at, title in claims:
            # 🪤 СРАВНИВАТЬ ЧАСОМ НЕЛЬЗЯ: объявление и его снятие ложатся в ОДНУ секунду,
            # если роль передумала сразу, и «снятие позже объявления» тогда не выполняется.
            # Поймано приёмкой на первом же прогоне: снятая работа осталась на чужом экране.
            # ⇒ Берём ПОСЛЕДНЕЕ событие по номеру записи: он растёт всегда.
            released = conn.execute(
                "SELECT event_type FROM backlog_events WHERE backlog_id=?"
                " AND event_type IN ('claim','claim_release')"
                " ORDER BY id DESC LIMIT 1", (bid,)).fetchone()
            released = bool(released) and released[0] == "claim_release"
            deadline = body.split(" UTC")[0].replace("до ", "") if body.startswith("до ") else None
            expired = bool(deadline) and conn.execute("SELECT ? < datetime('now')", (deadline,)).fetchone()[0]
            if released or expired:
                continue
            live_claims.append((bid, who, title, body))
        if live_claims:
            out.append(f"🔧 СЕЙЧАС В РАБОТЕ У КОЛЛЕГ: {len(live_claims)} — не берись за то же, "
                       f"не разбудив их владельца")
            for bid, who, title, body in live_claims[:6]:
                owner_label = "ТВОЯ" if who.upper() == role.upper() else who
                out.append(f"   #{bid:<4} [{owner_label:8}] {title[:52]}")
                out.append(f"        {body[:96]}")
        else:
            out.append("🔧 объявленной работы у коллег нет — проверено запросом, а не молчанием")
    except sqlite3.Error as e:                                        # noqa: BLE001
        out.append(f"⚠️ чужая работа НЕ СОБРАНА ({e})")

    conn.close()
    out.append("⚖️ блок знает БАЗУ, но не ДИСК: состояния репозиториев и живости сервисов "
               "здесь НЕТ — не считай их проверенными")
    return out
