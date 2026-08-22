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

⛔ ПАРАМЕТРЫ ЖИВУТ ТОЛЬКО ЗДЕСЬ. Менять шаг, начало и потолок — правкой этих трёх строк,
   и они меняются СРАЗУ У ВСЕХ. Ради этого всё и затевалось.
"""
import sqlite3
from pathlib import Path

START_SEC = 5 * 60          # с чего начинаем и куда возвращаемся при сбросе
STEP_SEC = 5 * 60           # на сколько прибавляем за каждую тишину подряд
MAX_SEC = 50 * 60           # потолок: дальше не растём


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
    столбцы = {r[1] for r in conn.execute("PRAGMA table_info(sync_backoff)")}
    if "last_bridge_mtime" not in столбцы:
        # Без NOT NULL намеренно: пустое значение означает «моста ещё не читали», и оно
        # должно ОТЛИЧАТЬСЯ от нуля, который значил бы «прочитали, там пусто».
        conn.execute("ALTER TABLE sync_backoff ADD COLUMN last_bridge_mtime REAL")


def _чужое_в_мосте(conn, db_path) -> tuple:
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
    места, метка, сбоев = [], 0.0, 0
    наша = ""
    try:
        _r = conn.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
        наша = (_r[0] if _r else "") or ""
    except sqlite3.OperationalError:
        наша = ""
    свои = Path(db_path).parent.parent          # <контур>/.mezosync/mezosync.db
    try:
        for d in свои.glob("*/.mezosync/bridges/*"):
            if d.is_dir() and not (наша and d.name.startswith(наша + "-")):
                места.append(d)
    except OSError:
        сбоев += 1
    try:
        соседи = conn.execute("SELECT target_db_path FROM cross_links").fetchall()
    except sqlite3.OperationalError:
        соседи = []
    for (dbp,) in соседи:
        контейнер = Path(dbp).parent.parent
        # 🪤 ПУСТОЙ ОБХОД НЕСУЩЕСТВУЮЩЕГО ПУТИ НЕ БРОСАЕТ ОШИБКУ — он молча даёт ноль
        # находок, и «путь соседа протух» выглядит как «у соседа ничего нет». Сосед
        # ЗАПИСАН в cross_links: раз записан, а каталога нет — мы не сумели посмотреть,
        # и это третий исход, а не второй. Поймано случаем ⑦ приёмки.
        if not контейнер.is_dir():
            сбоев += 1
            continue
        try:
            места += [d for d in контейнер.glob("*/.mezosync/bridges/*") if d.is_dir()]
        except OSError:
            сбоев += 1
    for d in места:
        try:
            for f in d.glob("*.md"):
                метка = max(метка, f.stat().st_mtime)
        except OSError:
            сбоев += 1
    if сбоев and метка == 0.0:
        return 0.0, "не смог"
    if not места:
        return 0.0, "смотреть некуда"
    return метка, "прочитано"


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
    bridge_head, мост_исход = _чужое_в_мосте(conn, db_path)

    if row is None:
        # Первый вызов роли — НЕ тишина: мы ещё ничего не наблюдали. Объявить тишину здесь
        # значило бы начать разгон с пустого места, ни разу не посмотрев в ленту.
        sleep, streak, quiet, new_count = START_SEC, 0, False, 0
        новое_в_мосте = 0
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
        новое_в_мосте = 1 if (мост_исход == "прочитано"
                              and bridge_head > (seen_bridge or 0)) else 0
        quiet = new_count == 0 and not новое_в_мосте
        if мост_исход == "не смог":
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
            откуда = []
            if new_count:
                откуда.append(f"{new_count} чужих записок в ленте")
            if новое_в_мосте:
                откуда.append("новый файл в мосте соседей")
            reason = (f"НЕ тишина: {' и '.join(откуда)} с прошлого опроса ⇒ "
                      f"сброс к {START_SEC // 60} мин")

    # ⛔ Отметку моста двигаем ТОЛЬКО когда его прочитали. Иначе неудачное чтение стёрло бы
    # её в ноль, и следующий опрос счёл бы новым весь мост целиком — либо, при обратном
    # порядке, объявил бы разобранным то, чего никто не видел.
    bridge_to_save = bridge_head if мост_исход == "прочитано" else None
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
            "new_count": new_count, "reason": reason, "bridge": мост_исход,
            "bridge_new": bool(новое_в_мосте),
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


def reset(db_path, role: str) -> None:
    conn = sqlite3.connect(str(db_path), timeout=10)
    _table(conn)
    conn.execute("UPDATE sync_backoff SET sleep_sec=?, quiet_streak=0, updated_at=datetime('now') "
                 "WHERE role=?", (START_SEC, (role or "").upper()))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="сколько спать до следующего синка (одно место)")
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
