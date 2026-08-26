# -*- coding: utf-8 -*-
r"""Наблюдатель ленты (ПИЛОТ, слово владельца 2026-08-26): событие-указатель вместо ожидания опроса.

ЧТО ДЕЛАЕТ. Крутится фоном при живой сессии роли, раз в N секунд смотрит ленту только
на чтение и ПЕЧАТАЕТ СТРОКУ, когда появилась записка, адресованная роли в шапке
(@РОЛЬ в первых 200 знаках) либо высокой важности. Среда доставляет каждую строку
в разговор основного агента как событие — в том числе пока агент ждёт человека.

⚖️ ТРИ РЕШЕНИЯ, ПРИНЯТЫЕ ДО КОДА (разбор для владельца 26.08 12:17 UTC):
  ① фильтр МЕХАНИЧЕСКИЙ, без модели: модельный судья промахивается молча, и промах
    выглядит как «новостей нет» — класс «молчащий отказ читается как успех»;
    упоминание @РОЛЬ в ТЕЛЕ не годится тоже — замер дал 30–63 % ленты (cc и пересказы).
    С 26.08 (Э-Б) «адресовано» = ОБЪЕДИНЕНИЕ: ПОЛЕ адресата (message_addressee,
    kind='to') ИЛИ @РОЛЬ в первых 200 знаках. Поле покрывает 56 % записок и видит
    адресата без @имени; регулярка держит прозу тех, кто поле не заполнил.
    В базе без таблицы поля — регулярка одна, как было;
  ② событие несёт УКАЗАТЕЛЬ, не тело: чтение и подтверждение остаются штатными
    (read-messages + ack), правило «читать ленту целиком» не ослабляется;
  ③ прежний ритм опроса ленты ОСТАЁТСЯ полом: наблюдатель — ускоритель осведомлённости,
    не замена дисциплины. Любой его сбой не должен стоить роли больше, чем возврат
    к сегодняшней задержке.

⛔ ЖИВОЙ БАЗЫ НЕ ПИШЕТ. Состояние (последний просмотренный номер, пульс) — в файле
`.watch-state-<РОЛЬ>.json` рядом со скриптом. Пульс оттуда показывает хук сводки
в каждом ходу — мёртвый наблюдатель ВИДЕН, а не молчит (условие устойчивости ③
из разбора: авто-остановку среды роль обязана замечать).

⚠️ ПЕРВЫЙ ЗАПУСК НЕ ВЫВАЛИВАЕТ ИСТОРИЮ: точка отсчёта — нынешняя голова ленты.
Долг прошлого виден хуком и штатным чтением; наблюдатель отвечает за НОВОЕ.

🔔 ПРОБА ДОСТАВКИ: `New-Item .watch-probe-<РОЛЬ>` рядом со скриптом — на следующем опросе
наблюдатель напечатает пробное событие и удалит файл. Зачем она СУЩЕСТВУЕТ: свои записки
наблюдатель отфильтровывает ПО ПОСТРОЕНИЮ (иначе каждая записка роли будила бы её же эхом),
поэтому роль НЕ МОЖЕТ проверить свой канал доставки, написав в ленту, — а канал, который
нельзя проверить, это молчание, читающееся как «новостей нет». Проба и замер З1 (будит ли
событие сессию, ждущую человека) держатся на ней.

ЗАПУСК:
    python C:/guts/.atlas/vnext-tools/watch-feed.py --role PROTO                 # цикл (для Monitor)
    python C:/guts/.atlas/vnext-tools/watch-feed.py --role PROTO --once          # один опрос (проверка)
    python C:/guts/.atlas/vnext-tools/watch-feed.py --role PROTO --db <копия>    # стенд, не живая
"""
import argparse
import json
import pathlib
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = pathlib.Path(__file__).resolve().parent


def state_path(role: str, stand: bool = False) -> pathlib.Path:
    # стенд держит СВОЁ состояние: проверка не имеет права двигать боевую точку отсчёта
    return HERE / f".watch-state-{role}{'-stand' if stand else ''}.json"


def load_state(role: str, stand: bool = False) -> dict:
    p = state_path(role, stand)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — битый файл = начать заново, но сказать об этом
            print(f"⚠️ наблюдатель {role}: файл состояния битый, начинаю с головы ленты",
                  flush=True)
    return {}


def save_state(role: str, st: dict, stand: bool = False) -> None:
    st["ts"] = time.time()
    state_path(role, stand).write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")


def опрос(db: pathlib.Path, role: str, st: dict) -> list[str]:
    """→ строки-события. Двигает last_seen по ВСЕМ просмотренным, не только подходящим."""
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=2.0)
    con.execute("PRAGMA query_only=ON")
    if "last_seen" not in st:
        st["last_seen"] = con.execute("SELECT COALESCE(MAX(id),0) FROM messages").fetchone()[0]
        con.close()
        return [f"👁 наблюдатель {role} взведён (пилот): опрос ленты, точка отсчёта — "
                f"записка #{st['last_seen']}. Событие = указатель; читать штатно: "
                f"read-messages + ack"]
    есть_поле = bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table'"
        " AND name='message_addressee'").fetchone())
    if есть_поле:
        # «адресовано» = поле (kind='to') ИЛИ @РОЛЬ в шапке — объединение, см. шапку ①.
        rows = con.execute(
            "SELECT m.id, m.writer_role, m.priority, SUBSTR(m.body_md,1,200), m.timestamp,"
            " EXISTS(SELECT 1 FROM message_addressee a WHERE a.message_id = m.id"
            "        AND a.role = ? AND a.kind = 'to')"
            " FROM messages m WHERE m.id > ? ORDER BY m.id",
            (role, st["last_seen"])).fetchall()
    else:
        rows = [(*r, 0) for r in con.execute(
            "SELECT id, writer_role, priority, SUBSTR(body_md,1,200), timestamp"
            " FROM messages WHERE id > ? ORDER BY id", (st["last_seen"],))]
    con.close()
    события = []
    for mid, writer, prio, шапка, ts, полем in rows:
        st["last_seen"] = mid
        if writer == role:
            continue
        адресовано = bool(полем) or f"@{role}" in (шапка or "")
        # 🩸 high И critical — важности взяты замером по базе (normal·high·critical),
        # первая редакция знала только high: та же щель, что в строке сводки, найденная
        # @OPSSRE (записка #3788). Одно место починки мало — меряй по каталогу.
        важно = (prio or "") in ("high", "critical")
        if not (адресовано or важно):
            continue
        первая = next((l.strip() for l in (шапка or "").splitlines() if l.strip()), "")[:100]
        признак = "адресовано тебе" if адресовано else f"важность {prio}"
        события.append(f"📨 лента: #{mid} от {writer} ({ts[:16]} UTC, {признак}"
                       f"{', high' if важно and адресовано else ''}): {первая} … "
                       f"— читай штатно: read-messages --role {role} + ack")
    return события


def main() -> int:
    ap = argparse.ArgumentParser(description="наблюдатель ленты: событие-указатель для роли")
    ap.add_argument("--role", required=True)
    ap.add_argument("--interval", type=int, default=90)
    ap.add_argument("--once", action="store_true", help="один опрос и выход (проверка/стенд)")
    ap.add_argument("--db", default=None, help="иная база — ТОЛЬКО для стенда")
    a = ap.parse_args()
    role = a.role.upper()
    db = pathlib.Path(a.db) if a.db else HERE.parent / ".mezosync" / "mezosync.db"
    if not db.exists():
        print(f"⛔ наблюдатель {role}: базы нет — {db}. Это отказ, а не «новостей нет»",
              flush=True)
        return 2

    стенд = bool(a.db)
    st = load_state(role, стенд)
    проба = HERE / f".watch-probe-{role}"
    while True:
        try:
            for строка in опрос(db, role, st):
                print(строка, flush=True)
            if проба.exists():
                проба.unlink()
                print(f"🔔 ПРОБА ДОСТАВКИ (замер З1): опрос живой, голова ленты #{st.get('last_seen', '?')}, "
                      f"путь база→событие→разговор пройден. Если ты читаешь это, ожидая человека, — "
                      f"событие БУДИТ. Проба одноразовая, файл-флаг удалён", flush=True)
            save_state(role, st, стенд)
        except Exception as exc:  # noqa: BLE001 — сбой опроса называется, цикл живёт
            print(f"⚠️ наблюдатель {role}: опрос не удался ({exc.__class__.__name__}: {exc}) "
                  f"— следующая попытка через {a.interval}с", flush=True)
        if a.once:
            return 0
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
