r"""
guard-write-without-read.py — ловит роль, которая ПИШЕТ, но НЕ ЧИТАЕТ ленту.

ЗАЧЕМ (оплачено 2026-07-23). ING трижды звал CORE и STUD по делу, которое стоило им одной строки
ответа, и стоял три цикла без кода. Обе роли признались одинаково и независимо:
  · STUD #2488: «у меня НЕ БЫЛ ПОДНЯТ ТАЙМЕР СИНКА… пинг пришёл от ВЛАДЕЛЬЦА, а не от механизма»;
  · CORE #2490: «я не читал ленту — у меня НЕ БЫЛ ПОДНЯТ ТАЙМЕР СИНКА… твои сутки ожидания —
    моя цена, не твоя».
Класс: **ритм не переживает пробуждение**. Роль просыпается, работает, пишет ноты — и не читает
чужие, потому что таймер снят прошлой сессией, а слепок не заставил его поднять. Дисциплина
не масштабируется — механизм масштабируется; но механизма ровно на это у нас не было.

ЧТО ПРОВЕРЯЕТ (данные есть в БД, догадок не требуется):
роль считается АКТИВНОЙ, если писала ноту за последние ACTIVE_MIN минут. Активная роль обязана
читать: её курсор не должен отставать от конца ленты больше чем на LAG_NOTES нот, а время последнего
чтения — быть не старше её собственной последней ноты более чем на LAG_MIN минут.
⇒ «Пишет свежее, чем читает» — это и есть подпись невзведённого таймера.

ЧЕГО НЕ ТРОГАЕТ: спящие и дормантные роли (RCC). Их отставание законно — они не участвуют,
и красное на них было бы шумом, после которого гард перестают читать.

ГРАНИЦА ЧЕСТНОСТИ: гард видит КУРСОР, а не понимание. Роль может подтвердить прочтение и не
осмыслить — этого не измерить ничем. Он ловит ровно один класс: молчание из-за неработающего
механизма, а не из-за решения.

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/guard-write-without-read.py
    python <КОНТУР>/.mezosync/scripts/guard-write-without-read.py --json     # для встраивания
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import mezo_paths  # noqa: E402  — путь к базе ВЫВОДИТСЯ, а не впечатывается

# ⚰️ Здесь стоял впечатанный абсолютный путь машины автора:
#     DB = Path(r"<КОНТУР>\.mezosync\mezosync.db")
# 🪤 ЧЕМ ОН ОБОШЁЛСЯ (карточка #168, 2026-08-10). Этот признак зовётся из `guard-all`, а тот
# запускается в том числе НА КОПИИ — приёмкой новорождённого контура. Копию проверяли,
# а признак читал ЖИВУЮ базу и приносил оттуда чужое красное. 10.08 приёмка объявила
# «СБОРКА НЕ ПРИНЯТА» из-за долга ленты у PROTO в живом контуре; я дочитал ленту, ничего
# в шаблоне не тронув, — и сборка стала «принята».
# ⚠️ Обе стороны ошибки равно опасны: сегодня оболгана чистая сборка, завтра при чистой
# живой базе тот же признак ПРОМОЛЧИТ о настоящем дефекте шаблона. Второе хуже: молчание
# читается как проверка.
# 📌 Последний впечатанный путь машины среди исполняемых строк тулкита: работа #157 вычистила
# шесть файлов, этот остался — и ровно он дал утечку. Проверка «ноль впечатанных путей»
# считалась закрытой, а набор был неполон.

ACTIVE_MIN = 90     # роль активна, если писала за последние N минут
LAG_NOTES = 8       # допустимое отставание курсора от конца ленты
LAG_MIN = 45        # допустимый разрыв «пишу сейчас — читал давно», минуты


def parse(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts)[:19]).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser(description="Гард: пишет, но не читает ленту.")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--db", default=None, help="по умолчанию — база рядом со скриптом")
    args = ap.parse_args()

    db = mezo_paths.resolve_db(args.db, __file__)
    conn = sqlite3.connect(db)
    now = datetime.now(timezone.utc)
    max_id = conn.execute("SELECT COALESCE(MAX(id),0) FROM messages").fetchone()[0]

    offenders, active = [], []
    for role, cursor, read_at in conn.execute(
            "SELECT reader_role, last_read_id, updated_at FROM read_cursors"):
        last_note = parse(conn.execute(
            "SELECT MAX(timestamp) FROM messages_all WHERE writer_role = ?", (role,)).fetchone()[0])
        if last_note is None or (now - last_note).total_seconds() > ACTIVE_MIN * 60:
            continue                                    # спящая роль — отставание законно
        active.append(role)

        # Отставание считаем по ЧУЖИМ нотам. Своя нота роль не зовёт — а гард предупреждает
        # именно о том, что «зовущие её ноты не дойдут» (см. текст ниже).
        # 🪤 Оплачено 2026-08-06 замером @PROTO (#2952) на случае @CHROME: непрочитанных 10,
        #    из них СВОИХ 2 — и ровно они перевели через порог 8. Прежняя формула
        #    `max_id - cursor` считала своё и чужое одинаково ⇒ чем активнее роль пишет, тем ниже
        #    для неё фактический порог: гард был строже всего к тому, кто больше работает.
        #    Плюс цикл «прочитал → ack → написал» ПО ПОСТРОЕНИЮ оставляет свою свежую ноту
        #    непрочитанной — у всех и всегда. Наказывать за форму работы значит учить обходить гард.
        # ⚠️ Строгость от этого НЕ падает: у @CHROME чужих было ровно 8, то есть дочитывать было
        #    надо и так. Изменился ПРЕДМЕТ счёта, а не порог.
        lag_notes = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE id > ? AND writer_role <> ?",
            (cursor or 0, role)).fetchone()[0]
        read_dt = parse(read_at)
        gap_min = ((last_note - read_dt).total_seconds() / 60) if read_dt else 9999

        if lag_notes > LAG_NOTES or gap_min > LAG_MIN:
            offenders.append({
                "role": role,
                "lag_notes": lag_notes,
                "gap_min": round(gap_min),
                "last_note": last_note.strftime("%H:%M UTC"),
                "read_at": read_dt.strftime("%H:%M UTC") if read_dt else "—",
            })
    conn.close()

    if args.json:
        print(json.dumps(offenders, ensure_ascii=False))
        sys.exit(1 if offenders else 0)

    if offenders:
        print(f"⛔ пишут, но не читают: {len(offenders)} из {len(active)} активных")
        for o in offenders:
            print(f"   {o['role']}: непрочитанных {o['lag_notes']}, "
                  f"писал в {o['last_note']}, читал в {o['read_at']} "
                  f"(разрыв {o['gap_min']} мин)")
        print("   Подпись невзведённого таймера синка. Роль пишет свежее, чем читает —")
        print("   значит зовущие её ноты не дойдут, и пинг придёт от владельца, а не от механизма.")
        sys.exit(1)

    print(f"✅ активных ролей {len(active)}, все читают ленту")
    sys.exit(0)


if __name__ == "__main__":
    main()
