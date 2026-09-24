# -*- coding: utf-8 -*-
"""СКОЛЬКО СПАТЬ ДО СЛЕДУЮЩЕГО СИНКА — ОДНО МЕСТО ДЛЯ ВСЕГО КОНТУРА.

Слово владельца 2026-08-08 19:06 UTC: «если при синке тишина, то увеличивать время сна
на 5 минут от предыдущего опроса, пока время не достигнет 50 минут. Сформируй для этого
функцию: куда все будут отправлять предыдущее время, чтобы получить следующее время сна…
должно работать как код/скрипт, а не только как правило, про которое могут забыть».

🎯 ЗАМЫСЕЛ ВЛАДЕЛЬЦА ВЗЯТ ЦЕЛИКОМ, НО ТРИ ВЕЩИ СДЕЛАНЫ ИНАЧЕ — И ВОТ ПОЧЕМУ.

① ФУНКЦИЯ САМА МЕРИТ ТИШИНУ, А НЕ ВЕРИТ ВЫЗЫВАЮЩЕМУ.
   Если «была ли тишина» решает роль, то признак становится её мнением: усталая роль
   объявит тишину, не посмотрев. Здесь тишина = «в ленте нет НИ ОДНОЙ чужой записки новее
   той, что видел прошлый опрос». Это факт из базы, и соврать о нём нельзя.

② СОСТОЯНИЕ ХРАНИТСЯ ЗДЕСЬ, А НЕ У КАЖДОГО СВОЁ.
   Владелец просил «отправлять предыдущее время». Тогда прошлое время хранит вызывающий —
   у восьми ролей восемь хранилищ, и первый же перезапуск чата обнуляет разгон молча.
   ⇒ Прошлое время помнит ЭТА функция, в общей базе, по роли. Аргумент `prev_sec` принимается
   для совместимости, но база сильнее: она переживает перезапуск, а память чата — нет.

③ СБРОС НАЗВАН ЯВНО, потому что владелец упомянул его («или сброса»), но не определил.
   Неопределённый сброс каждый понял бы по-своему — а это ровно тот класс, который мы сегодня
   чинили в правилах: условие без области расползается.
   СБРОС = появилась ХОТЬ ОДНА чужая записка. Тогда сон возвращается к началу.
   ⚖️ Почему любая, а не только адресованная лично: свод требует читать ленту ЦЕЛИКОМ
   (`full-scan-every-tick`, подтверждено владельцем 16:39 UTC). Спать долго при новых
   записках значило бы поощрять ровно то, что правило запрещает.

⚠️ ЦЕНА, КОТОРУЮ НАЗЫВАЮ ВСЛУХ: на потолке срочная записка ждёт до 50 минут. Это осознанный
   размен — разгон и заводят ради тишины. Именно поэтому сброс сделан по ЛЮБОЙ чужой записке:
   первая же строка в ленте возвращает роль к частому опросу.

📌 24.09: будильники сверок убираются (записка #5312). Чтение ленты печатает строку сна,
   только пока правило sync-sleep-backoff действует; иначе — счёт нового (news_line).

⛔ ПАРАМЕТРЫ ЖИВУТ ТОЛЬКО ЗДЕСЬ. Менять шаг, начало и потолок — правкой этих трёх строк,
   и они меняются СРАЗУ У ВСЕХ. Ради этого всё и затевалось.
"""
import sqlite3
from pathlib import Path

START_SEC = 5 * 60          # с чего начинаем и куда возвращаемся при сбросе
STEP_SEC = 5 * 60           # на сколько прибавляем за каждую тишину подряд
MAX_SEC = 50 * 60           # потолок: дальше не растём
# П② пула (27.08): пока в АКТИВНОМ пуле есть живые объявления, потолок сна УЧАСТНИЦЫ
# пула ниже — коллеги работают прямо сейчас, спать 50 минут рядом с живой работой
# значит вернуть девять параллельных списков. Участница = роль с открытой карточкой
# в активном пуле. Не участницы и мёртвый пул живут прежним потолком.
POOL_MAX_SEC = 15 * 60


def _table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS sync_backoff (
                        role TEXT PRIMARY KEY,
                        sleep_sec INTEGER NOT NULL,
                        quiet_streak INTEGER NOT NULL DEFAULT 0,
                        last_seen_id INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT)""")
    # 🪤 `CREATE TABLE IF NOT EXISTS` НИЧЕГО НЕ ДЕЛАЕТ С СУЩЕСТВУЮЩЕЙ ТАБЛИЦЕЙ. Дописать
    # столбец в текст выше — значит завести его только у тех, кто начинает с чистой базы;
    # у живого контура таблица уже есть, и столбца там не появится никогда. Молча.
    columns = {r[1] for r in conn.execute("PRAGMA table_info(sync_backoff)")}
    if "last_bridge_mtime" not in columns:
        # Без NOT NULL намеренно: пустое значение означает «моста ещё не читали», и оно
        # должно ОТЛИЧАТЬСЯ от нуля, который значил бы «прочитали, там пусто».
        # 🪤 ПЕРВАЯ РЕДАКЦИЯ МЕНЯЛА СХЕМУ МОЛЧА — и сторож журнала схемы закричал «схему
        # меняли мимо журнала» на первой же честной сборке контура. Правка на ходу обязана
        # записывать себя тем же общим модулем, что и шаги схемы: изменение без следа
        # делает ответ о версии схемы уверенным и неверным (правило migrations-under-watch).
        # Канонический шаг — migrations/20260822-sync-backoff-bridge-mtime.py; эта ветка —
        # страховка контура, обновившего инструменты раньше, чем прогнали шаги.
        journal = None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='schema_migrations'").fetchone():
            try:
                import schema_journal as journal
            except ImportError:
                journal = None                      # стенд без журнала — записывать некуда
        if journal is not None and not conn.in_transaction:
            conn.execute("BEGIN")
        conn.execute("ALTER TABLE sync_backoff ADD COLUMN last_bridge_mtime REAL")
        if journal is not None:
            journal.record_step(
                conn, "20260822-sync-backoff-bridge-mtime",
                "отметка последнего виденного чужого файла обмена (карточка #242); "
                "применено правкой на ходу при обращении к ритму")
            conn.commit()


def _foreign_bridge_head(conn, db_path) -> tuple:
    """Самая свежая метка времени ЧУЖОГО файла моста → (метка, исход).

    🎯 РАДИ ЧЕГО. Ритм считал новизну только по ленте — а сосед пишет ФАЙЛОМ в мост.
    Положенный им вопрос не сбрасывал разгон: роль объявляла тишину через три минуты
    после его письма и уходила спать, наращивая сон до потолка в 50 минут. Тишина была
    ложной, и увидеть это изнутри было нечем: лента и правда пуста.

    ⚖️ ЧУЖОЕ — ЭТО ГДЕ, А НЕ ЧЬЁ ИМЯ В ФАЙЛЕ. Разбирать авторство по имени умеет
    `guard-all.py`, и второй его экземпляр здесь разошёлся бы с первым молча. Берём
    признак, который не требует разбора: ⓐ исходящие папки соседей — они в ЧУЖИХ
    репозиториях, там наших файлов не бывает; ⓑ общие папки старого вида у нас —
    туда писали обе стороны. Своя исходящая («<наша группа>-<сосед>») НЕ считается:
    собственная свежая записка — не повод будить себя чаще.

    ИСХОДОВ ТРИ, И ТРЕТИЙ НЕ РАВЕН ВТОРОМУ:
      «прочитано» · «смотреть некуда» (мостов нет — законно) · «не смог» (есть, но
      чтение упало). Свести третий ко второму значило бы объявить тишину оттого, что
      не сумели посмотреть, — правило `read-failure-blocks-write` ровно про это.
    """
    places, mark, failures = [], 0.0, 0
    our_group = ""
    try:
        _r = conn.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
        our_group = (_r[0] if _r else "") or ""
    except sqlite3.OperationalError:
        our_group = ""
    own_root = Path(db_path).parent.parent          # <контур>/.mezosync/mezosync.db
    try:
        for d in own_root.glob("*/.mezosync/bridges/*"):
            if d.is_dir() and not (our_group and d.name.startswith(our_group + "-")):
                places.append(d)
    except OSError:
        failures += 1
    try:
        neighbours = conn.execute("SELECT target_db_path FROM cross_links").fetchall()
    except sqlite3.OperationalError:
        neighbours = []
    for (dbp,) in neighbours:
        container = Path(dbp).parent.parent
        # 🪤 ПУСТОЙ ОБХОД НЕСУЩЕСТВУЮЩЕГО ПУТИ НЕ БРОСАЕТ ОШИБКУ — он молча даёт ноль
        # находок, и «путь соседа протух» выглядит как «у соседа ничего нет». Сосед
        # ЗАПИСАН в cross_links: раз записан, а каталога нет — мы не сумели посмотреть,
        # и это третий исход, а не второй. Поймано случаем ⑦ приёмки.
        if not container.is_dir():
            failures += 1
            continue
        try:
            places += [d for d in container.glob("*/.mezosync/bridges/*") if d.is_dir()]
        except OSError:
            failures += 1
    for d in places:
        try:
            for f in d.glob("*.md"):
                mark = max(mark, f.stat().st_mtime)
        except OSError:
            failures += 1
    if failures and mark == 0.0:
        return 0.0, "не смог"
    if not places:
        return 0.0, "смотреть некуда"
    return mark, "прочитано"


def next_sleep(db_path, role: str, prev_sec: int = None) -> dict:
    """→ сколько спать до следующего синка. Никогда не бросает на пустой базе.

    Возвращает словарь: sleep_sec · minutes · quiet · streak · new_count · reason
    плюс сами параметры, чтобы вызывающий мог их НАПЕЧАТАТЬ, а не пересказать по памяти.
    """
    role = (role or "").upper()
    if not role:
        raise ValueError("роль не названа: разгон сна ведётся ПО РОЛИ, общего быть не может")
    conn = sqlite3.connect(str(db_path), timeout=10)
    _table(conn)
    row = conn.execute("SELECT sleep_sec, quiet_streak, last_seen_id, last_bridge_mtime "
                       "FROM sync_backoff WHERE role=?", (role,)).fetchone()
    # Новизну считаем по ЧУЖИМ запискам: своя свежая записка — не повод будить себя чаще.
    head = conn.execute("SELECT COALESCE(MAX(id), 0) FROM messages WHERE writer_role <> ?",
                        (role,)).fetchone()[0]
    bridge_head, bridge_outcome = _foreign_bridge_head(conn, db_path)

    if row is None:
        # Первый вызов роли — НЕ тишина: мы ещё ничего не наблюдали. Объявить тишину здесь
        # значило бы начать разгон с пустого места, ни разу не посмотрев в ленту.
        sleep, streak, quiet, new_count = START_SEC, 0, False, 0
        bridge_new = 0
        reason = "первый опрос: начинаем с начала, тишина ещё не наблюдалась"
    else:
        prev_sleep, prev_streak, seen, seen_bridge = row
        if prev_sec:                      # совместимость с формой владельца «прислать прошлое»
            prev_sleep = int(prev_sec)
        new_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE id > ? AND writer_role <> ?",
            (seen, role)).fetchone()[0]
        # ⚖️ Мост участвует в признаке тишины НАРАВНЕ с лентой: письмо соседа — такая же
        # новость, как записка коллеги, и молчать на неё до 50 минут нельзя.
        bridge_new = 1 if (bridge_outcome == "прочитано"
                              and bridge_head > (seen_bridge or 0)) else 0
        quiet = new_count == 0 and not bridge_new
        if bridge_outcome == "не смог":
            # ⛔ «НЕ СМОГ ПРОЧИТАТЬ» ≠ «ТАМ ПУСТО». Разогнать сон здесь значило бы объявить
            # тишину оттого, что не сумели посмотреть. Держим прежний сон и говорим вслух.
            sleep, streak, quiet = prev_sleep, prev_streak, False
            reason = ("МОСТ СОСЕДЕЙ НЕ ПРОЧИТАН — сон НЕ разгоняем: тишина не доказана. "
                      f"Лента: {new_count} чужих записок. Проверь пути соседей в cross_links")
        elif quiet:
            sleep = min(prev_sleep + STEP_SEC, MAX_SEC)
            streak = prev_streak + 1
            at_cap = sleep >= MAX_SEC
            reason = (f"тишина {streak}-й раз подряд: {prev_sleep // 60} + {STEP_SEC // 60} = "
                      f"{sleep // 60} мин" + (" — ПОТОЛОК, дальше не растём" if at_cap else ""))
        else:
            sleep, streak = START_SEC, 0
            # ⚖️ Названо, ЧТО именно разбудило: без этого роль, увидев сброс при пустой
            # ленте, решит, что механизм врёт, — и перестанет ему верить.
            sources = []
            if new_count:
                sources.append(f"{new_count} чужих записок в ленте")
            if bridge_new:
                sources.append("новый файл в мосте соседей")
            reason = (f"НЕ тишина: {' и '.join(sources)} с прошлого опроса ⇒ "
                      f"сброс к {START_SEC // 60} мин")

    # ⛔ Отметку моста двигаем ТОЛЬКО когда его прочитали. Иначе неудачное чтение стёрло бы
    # её в ноль, и следующий опрос счёл бы новым весь мост целиком — либо, при обратном
    # порядке, объявил бы разобранным то, чего никто не видел.
    # ═══ П② (27.08): потолок участницы живого пула. Считается ПОСЛЕ основной ветки:
    # сон уже выбран прежним правилом, здесь он только ПРИЖИМАЕТСЯ. Поломка предиката
    # не роняет расчёт сна — но говорит о себе вслух, а не молчит («молчащий отказ
    # читается как успех» — оплаченный класс).
    try:
        from backlog import active_pool_tracks, live_and_overdue, pool_open_ids
        pools = active_pool_tracks(conn)
        if pools and sleep > POOL_MAX_SEC:
            ph = ",".join("?" * len(pools))
            mine = conn.execute(
                f"SELECT 1 FROM backlog WHERE role=? AND parent_track IN ({ph}) "
                f"AND status IN ('open','in_progress','blocked','awaiting_word','in_review') "
                f"LIMIT 1", (role, *pools)).fetchone()
            if mine:
                live_leases, _ = live_and_overdue(conn, pool_open_ids(conn, pools))
                if live_leases:
                    sleep = POOL_MAX_SEC
                    reason += (f" · ПУЛ ЖИВ (объявлений {len(live_leases)}): потолок участницы "
                               f"{POOL_MAX_SEC // 60} мин")
    except Exception as exc:                                       # noqa: BLE001
        reason += f" · ⚠️ пул-потолок НЕ посчитан ({exc.__class__.__name__}) — сон прежний"

    bridge_to_save = bridge_head if bridge_outcome == "прочитано" else None
    conn.execute("INSERT INTO sync_backoff (role, sleep_sec, quiet_streak, last_seen_id, "
                 "last_bridge_mtime, updated_at) VALUES (?,?,?,?,?, datetime('now')) "
                 "ON CONFLICT(role) DO UPDATE SET sleep_sec=excluded.sleep_sec, "
                 "quiet_streak=excluded.quiet_streak, last_seen_id=excluded.last_seen_id, "
                 "last_bridge_mtime=COALESCE(excluded.last_bridge_mtime, "
                 "sync_backoff.last_bridge_mtime), "
                 "updated_at=excluded.updated_at",
                 (role, sleep, streak, head, bridge_to_save))
    conn.commit()
    conn.close()
    return {"sleep_sec": sleep, "minutes": sleep // 60, "quiet": quiet, "streak": streak,
            "new_count": new_count, "reason": reason, "bridge": bridge_outcome,
            "bridge_new": bool(bridge_new),
            "start_min": START_SEC // 60, "step_min": STEP_SEC // 60, "max_min": MAX_SEC // 60}


def line(db_path, role: str) -> str:
    """Одна строка для печати в конце синка. Параметры печатаются ВСЕГДА: правило,
    которое роль пересказывает по памяти, через неделю расходится с кодом."""
    try:
        r = next_sleep(db_path, role)
    except Exception as exc:                                       # noqa: BLE001
        return (f"⚠️ следующий сон НЕ ПОСЧИТАН ({exc.__class__.__name__}: {exc}). "
                "Это НЕ «спи сколько хочешь» — позови sync-backoff.py руками")
    return (f"⏱ СЛЕДУЮЩИЙ СИНК ЧЕРЕЗ {r['minutes']} МИН — {r['reason']}. "
            f"[начало {r['start_min']} · шаг {r['step_min']} · потолок {r['max_min']} мин]")


# ═══ 24.09 (план «убрать будильники», выбор владельца «Весь план», записка #5312) ═══
# Будильников сверок больше нет — роли зовут друг друга напрямую, и «через сколько спать»
# спрашивать некому. Полезная половина остаётся: сколько нового пришло с прошлого чтения
# (чужие записки и письма соседей в мосте). Строка сна печатается, ПОКА правило
# sync-sleep-backoff действует: пакет общий, у соседей правило может жить дальше.
RHYTHM_RULE = "sync-sleep-backoff"


def rhythm_rule_active(db_path) -> bool:
    """Действует ли правило разгона сна в своде этой базы. Нет правила или нет таблицы
    правил — «не действует»: ритма без правила не бывает."""
    try:
        conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            row = conn.execute("SELECT status FROM rules WHERE rule_key=?",
                               (RHYTHM_RULE,)).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return False
    return bool(row) and row[0] == "active"


def news(db_path, role: str) -> dict:
    """Сколько нового с прошлого чтения: чужие записки и чужие письма в мосте. Сон не
    считается и не меняется; отметки прошлого чтения двигаются так же, как в next_sleep."""
    role = (role or "").upper()
    if not role:
        raise ValueError("роль не названа: счёт нового ведётся ПО РОЛИ")
    conn = sqlite3.connect(str(db_path), timeout=10)
    _table(conn)
    row = conn.execute("SELECT last_seen_id, last_bridge_mtime FROM sync_backoff WHERE role=?",
                       (role,)).fetchone()
    head = conn.execute("SELECT COALESCE(MAX(id), 0) FROM messages WHERE writer_role <> ?",
                        (role,)).fetchone()[0]
    bridge_head, bridge_outcome = _foreign_bridge_head(conn, db_path)
    first = row is None
    seen, seen_bridge = (0, None) if first else row
    new_count = 0 if first else conn.execute(
        "SELECT COUNT(*) FROM messages WHERE id > ? AND writer_role <> ?",
        (seen, role)).fetchone()[0]
    bridge_new = (not first and bridge_outcome == "прочитано"
                  and bridge_head > (seen_bridge or 0))
    bridge_to_save = bridge_head if bridge_outcome == "прочитано" else None
    conn.execute("INSERT INTO sync_backoff (role, sleep_sec, quiet_streak, last_seen_id, "
                 "last_bridge_mtime, updated_at) VALUES (?,?,0,?,?, datetime('now')) "
                 "ON CONFLICT(role) DO UPDATE SET last_seen_id=excluded.last_seen_id, "
                 "last_bridge_mtime=COALESCE(excluded.last_bridge_mtime, "
                 "sync_backoff.last_bridge_mtime), updated_at=excluded.updated_at",
                 (role, START_SEC, head, bridge_to_save))
    conn.commit()
    conn.close()
    return {"first": first, "new_count": new_count, "bridge": bridge_outcome,
            "bridge_new": bool(bridge_new)}


def news_line(db_path, role: str) -> str:
    """Одна строка о новом с прошлого чтения — без сна и без «следующей сверки»."""
    try:
        r = news(db_path, role)
    except Exception as exc:                                       # noqa: BLE001
        return f"⚠️ новое с прошлого чтения НЕ ПОСЧИТАНО ({exc.__class__.__name__}: {exc})"
    if r["first"]:
        return "📬 с прошлого чтения: первое чтение — счёт нового начнётся со следующего"
    # ⚖️ Три исхода моста, и «не смог» не равен «нового нет» — как в next_sleep.
    bridge_word = {"прочитано": "есть новое" if r["bridge_new"] else "нового нет",
                   "смотреть некуда": "мостов нет",
                   "не смог": "НЕ ПРОЧИТАН — проверь пути соседей в cross_links"}[r["bridge"]]
    return (f"📬 с прошлого чтения: чужих записок {r['new_count']} · "
            f"письма соседей в мосте: {bridge_word}")


def reader_line(db_path, role: str) -> str:
    """Что печатает чтение ленты в конце: строку сна, пока правило ритма действует,
    иначе — только счёт нового."""
    return line(db_path, role) if rhythm_rule_active(db_path) else news_line(db_path, role)


def reset(db_path, role: str) -> None:
    conn = sqlite3.connect(str(db_path), timeout=10)
    _table(conn)
    conn.execute("UPDATE sync_backoff SET sleep_sec=?, quiet_streak=0, updated_at=datetime('now') "
                 "WHERE role=?", (START_SEC, (role or "").upper()))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="сколько спать до следующей сверки (одно место)")
    ap.add_argument("--db", default=str(Path(__file__).resolve().parent.parent / "mezosync.db"))
    ap.add_argument("--role", required=True)
    ap.add_argument("--prev-min", type=int, default=None,
                    help="прошлое время сна в минутах (форма владельца). Без него берётся из базы")
    ap.add_argument("--reset", action="store_true", help="вернуть к началу вручную")
    a = ap.parse_args()
    if a.reset:
        reset(a.db, a.role)
        print(f"сброшено к {START_SEC // 60} мин")
    else:
        r = next_sleep(a.db, a.role, (a.prev_min or 0) * 60 or None)
        print(f"{r['minutes']}")
        print(f"# {r['reason']}")
        print(f"# начало {r['start_min']} · шаг {r['step_min']} · потолок {r['max_min']} мин")
