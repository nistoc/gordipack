"""
backlog.py — durable per-role backlog (переживает перезапуск агента). Фаза B1: базовый CRUD.

Первое на пробуждении роли:
    python <КОНТУР>/.mezosync/scripts/backlog.py list --role CORE        # мои открытые задачи + SHARED

Создание / работа:
    python <КОНТУР>/.mezosync/scripts/backlog.py add --role CORE --title "prov-reject-events" \
        --body-file note.md --priority high --tags "prov,F"
    python <КОНТУР>/.mezosync/scripts/backlog.py show   3
    python <КОНТУР>/.mezosync/scripts/backlog.py status 3 in_progress --actor CORE --note "взял в работу"
    python <КОНТУР>/.mezosync/scripts/backlog.py comment 3 --actor CORE --body-file update.md
    python <КОНТУР>/.mezosync/scripts/backlog.py list --role CORE --status all   # включая закрытые

Rich-md подаётся через --body/--body-file и --note/--note-file.
Тесты (test-add/test-run/test-result) — фаза B2, здесь нет.
"""

import argparse
import datetime
import json
import sqlite3
import sys
import time
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD
import dryrun          # холостой прогон (13.08)
# ⚠️ Импорт ОБЁРНУТ намеренно — правка @TAXO (её замер живой эксплуатации 13:18:06 UTC):
# она поймала этот файл в 15-секундном окне между записью вызова и записью модуля и получила
# NameError. Её довод, и он мой же собственный: правило владельца велит ПРЕДУПРЕЖДАТЬ,
# а не отказывать ⇒ отсутствие предупреждалки не вправе отказывать сильнее, чем она сама.
# 📌 И класс, который она назвала точнее меня: правка общего инструмента НЕ АТОМАРНА —
# между записью двух файлов есть окно, в котором инструмент синтаксически цел и функционально
# мёртв. Объявить его нельзя: оно короче объявления. Лечится формой, а не дисциплиной.
try:
    from refs_check import warn_dangling   # предупреждение о «#N» вне чата (правило v3)
except Exception:                          # noqa: BLE001 — любая поломка модуля дешевле потерянной ноты
    def warn_dangling(*_a, **_k):
        print("⚠️ проверка ссылок НЕ ВЫПОЛНЕНА: модуль refs_check недоступен", file=__import__("sys").stderr)

# ⚖️ ДВА СОСТОЯНИЯ ВЗЯТЫ ИЗ ЧУЖОГО СЛОВАРЯ (протокол A2A, слово владельца 18.08 13:56 UTC:
# «возьми терминологию, на сам протокол пока не переходим»). Оба закрывают потерю правды,
# которую мы терпели:
#   awaiting_word — ждёт СЛОВА ЧЕЛОВЕКА. Раньше это писалось как blocked и было неотличимо
#     от «жду чужую работу»: в первом случае дело стоит из-за меня и молчит об этом владельцу.
#   failed — ПРОБОВАЛИ, НЕ ВЫШЛО. Раньше писалось как dropped, то есть «передумали делать»;
#     неудача, записанная отменой, стирает сам факт попытки и её причину.
STATUSES = ["open", "in_progress", "blocked", "awaiting_word", "in_review", "done",
            "failed", "dropped"]
OPEN_STATUSES = ["open", "in_progress", "blocked", "awaiting_word", "in_review"]
PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def utc_to_local(s):
    """UTC → UTC. Оставлено имя ради совместимости вызовов; конвертации БОЛЬШЕ НЕТ.
    Правило timestamp-utc-in-sqlite v2 (владелец 2026-07-16): контур живёт в ОДНОЙ
    шкале — UTC. Две шкалы брали налог вниманием и породили фантом «синк умер 2 часа
    назад» (разница ровно 2ч была ЗОНОЙ, не лагом). Конвертация, которой нет, не может
    быть забыта. Суффикс UTC печатаем явно: метка без зоны неотличима от локальной."""
    return f"{s} UTC" if s else "—"

def _text(inline, file_arg):
    if file_arg:
        return Path(file_arg).read_text(encoding="utf-8")
    return inline or ""


def _conn(db, dry=False):
    p = Path(db)
    if not p.exists():
        print(f"ERR: БД не найдена: {p}", file=sys.stderr)
        sys.exit(1)
    c = dryrun.connect(str(p), dry, timeout=5)
    c.execute("PRAGMA busy_timeout=5000")
    return c


def _event(conn, bid, actor, etype, body="", frm=None, to=None):
    conn.execute(
        "INSERT INTO backlog_events (backlog_id, actor_role, event_type, from_status, to_status, body_md) "
        "VALUES (?,?,?,?,?,?)", (bid, actor.upper(), etype, frm, to, body))


def cmd_add(conn, a):
    body = _text(a.body, a.body_file)
    tags = json.dumps([t.strip() for t in a.tags.split(",") if t.strip()], ensure_ascii=False)
    done_when = _text(a.done_when, getattr(a, "done_when_file", None)).strip() or None

    # ⛔ ВОРОТА ЗАВЕДЕНИЯ. Слово владельца 2026-08-07 12:56 UTC (через @PROTO #3228, дословно):
    #   «1. критерий приемки - делай обязательным.»
    #   «3. тело - требуем непустым, если подразумевается тело задачи.»
    #
    # Здесь ОТМЕНЯЕТСЯ прежнее решение этого же файла («сначала данные, потом строгость»,
    # 06.08). Оно было верным для своего состояния: запрет раньше пути записи запретил бы
    # работу всем разом. Состояние изменилось, и это ЗАМЕРЕНО @PROTO до раскатки, а не
    # предположено: за сутки заведено 35 карточек, без критерия из них 3 ⇒ 32 из 35 уже
    # соблюдают. Запрет закрывает ЩЕЛЬ, а не ломает привычку.
    # 📌 Прежнее решение не «было ошибкой» — у него истекло условие. Разные болезни.
    missing = []
    if not done_when:
        missing.append("критерий приёмки (--done-when / --done-when-file)")
    if not body.strip():
        missing.append("тело задачи (--body / --body-file)")
    if missing:
        print(f"⛔ карточка НЕ заведена «{a.title}» — не хватает: {' и '.join(missing)}",
              file=sys.stderr)
        # Отказ ОБЯЗАН объяснять. Довод @PROTO: «нельзя» без объяснения роль обойдёт формально —
        # впишет «сделать хорошо», и запрет станет обрядом. Ровно тот исход, ради недопущения
        # которого владелец согласился на ДВА поля вместо семи.
        if not done_when:
            print("   критерий — это ЧЕМ ДОКАЖЕШЬ, что сделано: что прогнать, что увидеть,",
                  file=sys.stderr)
            print("   что засчитать НЕЛЬЗЯ. Не «сделать хорошо».", file=sys.stderr)
        if not body.strip():
            print("   тело — описание предмета. Три карточки контура закрыты с пустым телом,",
                  file=sys.stderr)
            print("   и что в них делали, не восстановимо ничем.", file=sys.stderr)
        print(f'   backlog.py add --role {a.role} --actor {a.actor or a.role} '
              f'--title "{a.title}" --body-file <файл> --done-when-file <файл>', file=sys.stderr)
        sys.exit(1)

    # ⚠️ Предупреждение о неразрешимых ссылках — ПОСЛЕ ворот и ДО записи. Порядок важен:
    # ворота говорят «карточка НЕ заведена», предупреждение — «заведена, но читателю
    # со стороны будет трудно». Смешать их значило бы утопить отказ в шуме.
    warn_dangling(body, label="тело карточки")
    warn_dangling(done_when, label="критерий")

    cur = conn.execute(
        "INSERT INTO backlog (role, title, body_md, priority, tags, parent_id, parent_track, created_by, done_when) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (a.role.upper(), a.title, body, a.priority, tags, a.parent, a.track,
         (a.actor or a.role).upper(), done_when))
    bid = cur.lastrowid
    _event(conn, bid, a.actor or a.role, "created", f"created: {a.title}", None, "open")
    if done_when:
        _event(conn, bid, a.actor or a.role, "criterion_set", f"критерий: {done_when}")
    conn.commit()
    print(f"✅ backlog #{bid} [{a.role.upper()}] «{a.title}» ({a.priority}, open)")
    if done_when:
        print(f"   🎯 критерий: {done_when}")
        # Приём обязан быть так же честен, как отказ — просьба @ING (#3231) с двумя его
        # собственными экземплярами за час: критерий БЫЛ на месте и вёл преемника в ложное
        # место (имя функции вместо имени триггера ⇒ красное по ложной причине; проверка
        # существования вместо тела ⇒ зелёное по ложной причине).
        # ⇒ «критерий есть» — не «карточка в порядке». Наличие ≠ годность, и годность
        # машинно непроверяема. Молчать об этом значило бы выдать зелёный сигнал за приёмку.
        print("   ⚖️ записан — проверяет ли он то, что нужно, машина не знает")


def cmd_criterion(conn, a):
    """Путь записи критерия для СУЩЕСТВУЮЩИХ карточек — то, чего не было и из-за чего
    поле done_when рисковало повторить судьбу `resolved` (1 запись из 1483: ставить было нечем)."""
    row = conn.execute("SELECT title, done_when FROM backlog WHERE id = ?", (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    title, old = row
    text = _text(a.text, a.text_file).strip()
    if not text:
        print("ERR: пустой критерий. Пустое поле неотличимо от «не заполняли» — это и лечим.",
              file=sys.stderr)
        sys.exit(1)
    conn.execute("UPDATE backlog SET done_when = ?, updated_at = datetime('now') WHERE id = ?",
                 (text, a.id))
    _event(conn, a.id, a.actor, "criterion_set",
           (f"критерий изменён: {old} → {text}" if old else f"критерий: {text}"))
    conn.commit()
    if old:
        print(f"✅ backlog #{a.id} критерий ИЗМЕНЁН (прежний сохранён в истории)\n   было: {old}\n   стало: {text}")
    else:
        print(f"✅ backlog #{a.id} «{title}» — критерий записан:\n   🎯 {text}")


def _criterion_digest(text, width=64):
    """Срез критерия для СПИСКА.

    🪤 Оплачено 2026-08-06: @CORE (#3013) работал по списку и едва не закрыл карточку #35 —
       три пункта из четырёх были сделаны, четвёртый (пароли не в файле на диске) НЕ сделан.
       Спасла привычка открыть тело, а не механизм. Формула @opssre (#3011):
       «тот, кто позовёт show, и так осторожен; опасен тот, кто работает по списку».

    📌 Показываем НЕ начало, а ЗАПРЕЩЁННЫЙ СПОСОБ пройти приёмку, если он назван (довод @CORE):
       начало обычно «работает то-то» — а запрет это то, чего в голове читающего нет.
       Требуемый результат говорит, куда идти; запрещённый способ — где не считается.
    """
    if not text:
        return None
    # Режем и по строкам, и по предложениям: критерий, написанный аргументом (до появления
    # --done-when-file), приходит ОДНОЙ строкой — у @CORE она 950 знаков. Разбиение только
    # по строкам на таком тексте бессильно, и я это увидел на его же карточке, а не предположил.
    import re as _re
    parts = [p.strip(" -•\t") for chunk in text.splitlines()
             for p in _re.split(r"(?<=[.;])\s+", chunk) if p.strip()]
    # ⚠️ Маркеры УЗКИЕ намеренно. Первая редакция ловила «НЕ » — и на #35 показала обычное
    #    «не ходит под суперпользователем» вместо запрета. Широкий маркер даёт срез, который
    #    выглядит осмысленным и выбран случайно: хуже, чем никакого.
    ban_markers = ("⛔", "не считается", "нельзя", "запрещ", "задним числом",
                   "не засчит", "не закрыв", "не подмен")
    for part in parts:
        low = part.lower()
        if any(m in part or m in low for m in ban_markers):
            head = part
            break
    else:
        head = parts[0] if parts else text
    head = " ".join(head.split())
    return head if len(head) <= width else head[:width - 1] + "…"


def cmd_list(conn, a):
    if a.status == "all":
        where_status, params = "1=1", []
    elif a.status == "open":
        where_status = f"status IN ({','.join('?' * len(OPEN_STATUSES))})"
        params = list(OPEN_STATUSES)
    else:
        where_status, params = "status = ?", [a.status]

    roles = [a.role.upper()]
    if not a.only_mine:
        roles.append("SHARED")
    where_role = f"role IN ({','.join('?' * len(roles))})"
    params = roles + params

    # Отбор «старше N суток» (карточка #86 ⑧): напоминание о залежавшемся не должно тонуть
    # в свежем — свежие тут НЕ показываются, и подпись ниже говорит об этом сама.
    where_age, age_note = "1=1", ""
    if getattr(a, "older_than_days", None) is not None:
        where_age = f"created_at <= datetime('now', '-{int(a.older_than_days)} days')"
        age_note = f" · старше {a.older_than_days} сут (свежие скрыты)"

    rows = conn.execute(
        f"SELECT id, role, title, status, priority, tags, done_when FROM backlog "
        f"WHERE {where_role} AND {where_status} AND {where_age}", params).fetchall()
    rows.sort(key=lambda r: (PRIORITY_ORDER.get(r[4], 9), r[0]))

    if not rows:
        print(f"📭 [{a.role.upper()}] backlog пуст (status={a.status}{age_note}).")
        return
    # Подпись называет ФАКТИЧЕСКИЙ состав (карточка #188): отбор «open» — это ГРУППА статусов,
    # и число из подписи уходит в записки и промпты. «status=open» при blocked внутри — ложь
    # на одну карточку, уже уехавшая в промпт как «открытых 11» при фактических 10.
    from collections import Counter
    состав = Counter(r[3] for r in rows)
    if len(состав) > 1:
        подпись = " · ".join(f"{s} {n}" for s, n in состав.most_common())
    else:
        подпись = f"status={next(iter(состав))}"
    print(f"📋 backlog [{a.role.upper()}{'' if a.only_mine else ' + SHARED'}] — {len(rows)} задач ({подпись}{age_note})\n")
    icon = {"open": "○", "in_progress": "◐", "blocked": "⛔", "awaiting_word": "🙋",
            "in_review": "👀", "done": "✅", "failed": "💥", "dropped": "✗"}
    no_criterion = 0
    for bid, role, title, status, prio, tags, done_when in rows:
        pr = {"critical": "‼️", "high": "⬆️", "normal": "·", "low": "⬇️"}.get(prio, "·")
        tg = " ".join(f"#{t}" for t in json.loads(tags or "[]"))
        shared = " (SHARED)" if role == "SHARED" else ""
        # ✎ — подсветка «критерия нет». Слово владельца 06.08 15:26 UTC: подсветить, НЕ блокировать.
        # Стоит ЗДЕСЬ, а не отдельной командой, по замечанию @opssre (#3002): витрину, которую надо
        # позвать, надо помнить — а роль эту строку и так видит каждый раз.
        mark = "  " if done_when else " ✎"
        if not done_when and status in OPEN_STATUSES:
            no_criterion += 1
        print(f"  #{bid} {icon.get(status,'?')} {pr}{mark} {title}{shared}  {tg}")
        digest = _criterion_digest(done_when)
        if digest:
            print(f"        🎯 {digest}")
        # Причина устаревания — В СПИСКЕ, не только в истории (карточка #86 ⑥). Старые
        # dropped без причины говорят это ЧЕСТНО, а не молчат как «нечего показать».
        if status == "dropped":
            why = conn.execute(
                "SELECT body_md FROM backlog_events WHERE backlog_id=? "
                "AND event_type='status_change' AND to_status='dropped' "
                "AND body_md IS NOT NULL AND TRIM(body_md) != '' "
                "ORDER BY id DESC LIMIT 1", (bid,)).fetchone()
            print(f"        ✗ причина: {why[0][:140] if why else 'НЕ ЗАПИСАНА (устарела до ворот 14.08)'}")
    if no_criterion:
        print(f"\n✎ без критерия готовности: {no_criterion} из {len(rows)} "
              f"— чем докажешь, что сделано?")
        # Строка описывает ФАКТИЧЕСКОЕ поведение, а не намерение. С 07.08 их стало два разных:
        # пока карточка открыта — подсветка; в момент закрытия — отказ. Написать одним словом
        # («обязателен» или «подсветка») значило бы соврать про одну из половин.
        print("   пока открыта — подсветка. Закрыть как done без критерия НЕЛЬЗЯ (07.08).")
        print("   записать: backlog.py criterion <id> --actor <РОЛЬ> --text \"...\"")


def cmd_show(conn, a):
    row = conn.execute(
        "SELECT id, role, title, body_md, status, priority, tags, parent_id, parent_track, "
        "blocked_reason, created_by, created_at, updated_at, done_when FROM backlog WHERE id = ?",
        (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    (bid, role, title, body, status, prio, tags, parent, track, blocked, cby, cat, uat, done_when) = row
    print(f"# backlog #{bid} — {title}")
    print(f"роль: {role} · статус: {status} · приоритет: {prio} · теги: {', '.join(json.loads(tags or '[]')) or '—'}")
    # Цепочка ПРЕДКОВ целиком, не только ближайший родитель (карточка #86 ⑤: «связи читаются
    # одним запросом»). Гард на цикл в данных: повтор номера обрывает подъём, а не вешает show.
    if parent:
        chain, p = [], parent
        while p and p not in chain:
            chain.append(p)
            nxt = conn.execute("SELECT parent_id FROM backlog WHERE id = ?", (p,)).fetchone()
            p = nxt[0] if nxt else None
        print("родитель: " + " → ".join(f"#{c}" for c in chain))
    children = [r[0] for r in conn.execute(
        "SELECT id FROM backlog WHERE parent_id = ? ORDER BY id", (a.id,))]
    if children:
        print("потомки: " + " ".join(f"#{c}" for c in children))
    if track: print(f"трек: {track}")
    if blocked: print(f"⛔ причина блокировки: {blocked}")
    # Критерий печатается ВСЕГДА — и когда он есть, и когда его нет. Молчание о пустом поле
    # неотличимо от «поля не существует»: ровно так поле `resolved` дожило до 1 записи из 1483.
    if done_when:
        print(f"🎯 критерий готовности: {done_when}")
    else:
        print("✎ критерий готовности: НЕ ЗАДАН — чем докажешь, что сделано?")
        print(f"   записать: backlog.py criterion {bid} --actor <РОЛЬ> --text \"...\"")
    print(f"создал: {cby} @ {utc_to_local(cat)} · обновлён: {utc_to_local(uat)}")
    print(f"\n{body or '(нет описания)'}\n")

    tests = conn.execute(
        "SELECT id, title, method, status FROM backlog_tests WHERE backlog_id = ? ORDER BY id", (a.id,)).fetchall()
    if tests:
        print("## Тесты")
        for tid, tt, method, tstatus in tests:
            print(f"  [{tstatus}] ({method}) {tt}  (test #{tid})")
        print()

    print("## История")
    for at, actor, etype, frm, to, ebody in conn.execute(
            "SELECT at, actor_role, event_type, from_status, to_status, body_md "
            "FROM backlog_events WHERE backlog_id = ? ORDER BY id", (a.id,)):
        arrow = f" {frm}→{to}" if etype == "status_change" else ""
        extra = f" — {ebody}" if ebody else ""
        print(f"  {utc_to_local(at)} [{actor}] {etype}{arrow}{extra}")


def cmd_status(conn, a):
    if a.new_status not in STATUSES:
        print(f"ERR: статус должен быть из {STATUSES}", file=sys.stderr)
        sys.exit(1)
    row = conn.execute("SELECT status, done_when, title, role FROM backlog WHERE id = ?",
                       (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    old, done_when, title, owner = row

    # ⛔ ВОРОТА: чужую карточку двигаешь — НАЗОВИ её владельца, инструмент сверит имя с базой.
    #
    # Полевой факт 07.08 10:51 UTC (@STUD #3170): он завёл карточку и ТЕМ ЖЕ вызовом закрыл
    # «свою» по номеру 92 — номер он ВЫВЕЛ («сосед завёл 91 минуту назад, значит моя 92»),
    # а не прочитал. 92 оказалась чужой, и она ушла open → done с его текстом внутри.
    # Его формулировка: «идентификатор, полученный рассуждением, неотличим по виду от
    # полученного ответом инструмента — и ровно поэтому опасен».
    #
    # Почему НЕ запрет чужих правок. Замер: из 56 смен статуса 21 — чужие карточки, и 17 из них
    # мои же, COORD (координатор двигает чужое по работе). Запрет сломал бы законный поток,
    # а сломанные ворота обходят. ⇒ Не запрещаем, а требуем НАЗВАТЬ, и сверяем названное.
    #
    # Почему это ловит именно тот случай. Угаданный номер приходит вместе с уверенностью
    # «карточка моя» ⇒ роль не передаст --foreign вовсе и получит отказ. А кто и правда
    # двигает чужое — тот карточку видел, и имя владельца у него перед глазами.
    # Сверка ИМЕНИ, а не флаг «я знаю, что делаю»: голый флаг подтверждает намерение,
    # а нужно подтвердить ЗНАНИЕ — их различает только то, что можно не угадать.
    actor = (a.actor or "").upper()
    owner_u = (owner or "").upper()
    if actor != owner_u:
        named = (a.foreign or "").upper()
        if named != owner_u:
            print(f"⛔ backlog #{a.id} «{title}» принадлежит роли {owner}, а ты {a.actor}.",
                  file=sys.stderr)
            if named:
                print(f"   Ты назвал владельцем {a.foreign} — не совпало с базой. "
                      "Возможно, это НЕ та карточка.", file=sys.stderr)
            else:
                print("   Чужую карточку двигать можно, но её владельца надо НАЗВАТЬ:",
                      file=sys.stderr)
            print(f"   backlog.py status {a.id} {a.new_status} --actor {a.actor} "
                  f"--foreign {owner}", file=sys.stderr)
            print(f"   ⚠️ Если ты ждал СВОЮ карточку — номер получен рассуждением, а не ответом "
                  f"инструмента. Посмотри: backlog.py show {a.id}", file=sys.stderr)
            sys.exit(1)

    # ⛔ ВОРОТА: `done` без критерия приёмки. Слово владельца 07.08 10:31 UTC (Р3, через @PROTO):
    # «37 закрытых НЕ ТРОГАТЬ, требовать при СЛЕДУЮЩЕМ касании». Закрытие и есть касание.
    #
    # Почему ворота, а не подсветка. Замер @PROTO 10:23 UTC: 37 закрытых карточек из 41 — БЕЗ
    # критерия, при том что справка этого же скрипта год говорит «обязателен». Обязательность
    # была ОБЪЯВЛЕНА и не исполнена ⇒ шестой за двое суток экземпляр класса «врёт не код,
    # а текст, который код печатает», и он в моей зоне. Подсветка тут уже испытана: она
    # проиграла 37:4. Теперь строка справки становится правдой.
    #
    # Только `done`. `dropped` (отменена) критерия не требует по построению: доказывать нечего,
    # и требовать его значило бы толкать роль закрывать отменённое как сделанное.
    if a.new_status == "done" and not (done_when or "").strip():
        print(f"⛔ backlog #{a.id} «{title}» — КРИТЕРИЯ ПРИЁМКИ НЕТ, закрыть как done нельзя.",
              file=sys.stderr)
        print("   Чем докажешь, что сделано? Критерий пишется ДО закрытия — написанный после,",
              file=sys.stderr)
        print("   он описывает уже полученный результат, а не проверяет его.", file=sys.stderr)
        print(f'   backlog.py criterion {a.id} --actor {a.actor} --text "..."', file=sys.stderr)
        print("   ⚠️ Отменяешь, а не сделал? Это `dropped` — критерий там не нужен, "
              "но ПРИЧИНА обязательна (--note).", file=sys.stderr)
        sys.exit(1)

    note = _text(a.note, a.note_file)

    # ⛔ ВОРОТА: `dropped` без причины. Слово владельца 07.08 10:20 UTC (карточка #86 ⑥):
    # объявлять устаревшими — С ОБЪЯСНЕНИЕМ. Замер 14.08: dropped проходил МОЛЧА, а подсказка
    # отказа `done` выше сама направляла в эту дверь. Причина — не критерий (доказывать
    # нечего), но без «почему» отменённая карточка молчит, жив ли предмет и чем заменён.
    # ⛔ ВОРОТА: «не вышло» без рассказа, ЧТО пробовали, — это не запись неудачи, а её сокрытие.
    if a.new_status == "failed" and not note.strip():
        print(f"⛔ backlog #{a.id} «{title}» — НЕ ВЫШЛО, но не сказано ЧТО ПРОБОВАЛИ.",
              file=sys.stderr)
        print("   Следующий возьмётся за то же и потратит то же время. Назови попытку и на чём встала.",
              file=sys.stderr)
        print(f'   backlog.py status {a.id} failed --actor {a.actor} '
              f'--note "пробовал так-то; встало на том-то"', file=sys.stderr)
        sys.exit(1)

    # ⛔ ВОРОТА: «жду слова» без вопроса — владелец не узнает, чего от него хотят.
    if a.new_status == "awaiting_word" and not note.strip():
        print(f"⛔ backlog #{a.id} «{title}» — ЖДЁТ СЛОВА, но вопрос не назван.", file=sys.stderr)
        print("   Напиши сам вопрос: его увидит владелец, а не тот, кто ставил состояние.",
              file=sys.stderr)
        sys.exit(1)

    if a.new_status == "dropped" and not note.strip():
        print(f"⛔ backlog #{a.id} «{title}» — ПРИЧИНЫ НЕТ, объявить устаревшей нельзя.",
              file=sys.stderr)
        print("   Почему предмет больше не нужен? Если заменён — назови заменившую карточку.",
              file=sys.stderr)
        print(f'   backlog.py status {a.id} dropped --actor {a.actor} '
              f'--note "причина; заменено: карточка #N"', file=sys.stderr)
        sys.exit(1)

    # причина стоянки хранится одна и та же и для «жду чужую работу», и для «жду слово»
    blocked_reason = note if a.new_status in ("blocked", "awaiting_word") else None
    conn.execute(
        "UPDATE backlog SET status = ?, blocked_reason = ?, updated_at = datetime('now') WHERE id = ?",
        (a.new_status, blocked_reason, a.id))
    _event(conn, a.id, a.actor, "status_change", note, old, a.new_status)
    conn.commit()
    # Заголовок и владелец печатаются В ПОДТВЕРЖДЕНИИ, а не только в отказе: строка
    # «✅ backlog #92: open → done» одинаково выглядит для верной и для ошибочной карточки.
    чьё = "" if actor == owner_u else f" [карточка {owner}]"
    print(f"✅ backlog #{a.id}{чьё} «{title}»: {old} → {a.new_status}"
          + (f" ({note})" if note else ""))


def cmd_comment(conn, a):
    row = conn.execute("SELECT id FROM backlog WHERE id = ?", (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    body = _text(a.body, a.body_file)
    if not body.strip():
        print("ERR: пустой комментарий", file=sys.stderr)
        sys.exit(1)
    warn_dangling(body, label="комментарий")
    _event(conn, a.id, a.actor, "comment", body)
    conn.execute("UPDATE backlog SET updated_at = datetime('now') WHERE id = ?", (a.id,))
    conn.commit()
    print(f"✅ комментарий добавлен к backlog #{a.id}")


def main():
    p = argparse.ArgumentParser(description="Durable per-role backlog (B1 CRUD)")
    # R15a: --db не обязателен, резолвится от расположения СКРИПТА (не от CWD).
    p.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add")
    dryrun.add_argument(pa)
    pa.add_argument("--role", required=True)
    pa.add_argument("--title", required=True)
    pa.add_argument("--body", default="")
    pa.add_argument("--body-file", dest="body_file")
    pa.add_argument("--priority", default="normal", choices=["low", "normal", "high", "critical"])
    pa.add_argument("--tags", default="")
    pa.add_argument("--parent", type=int)
    pa.add_argument("--track")
    pa.add_argument("--actor")
    pa.add_argument("--done-when", dest="done_when", default="",
                    # Строка называет МОМЕНТ принуждения, а не просто «обязателен»: завести
                    # карточку без критерия можно, ЗАКРЫТЬ как done — нельзя (ворота 07.08).
                    # Прежняя формулировка «обязателен» была объявлением без механизма и год
                    # держалась при счёте 37 закрытых из 41 без критерия (замер @PROTO #3164).
                    help="критерий приёмки: чем докажешь, что сделано. Можно дописать позже "
                         "(backlog.py criterion), но БЕЗ него карточку не закрыть как done")
    # Парный файл — по замечанию @CORE (#3006), первого потребителя: у --body файл-двойник есть,
    # у критерия не было, и критерий из четырёх пунктов пришлось сплющивать в одну строку.
    # 🪤 Класс, ради которого правка: ФОРМА АРГУМЕНТА ПОДТАЛКИВАЕТ ПИСАТЬ КРИТЕРИЙ КОРОТКО,
    #    а короткий критерий легче сделать неопровержимым. «Работает» помещается в строку,
    #    «укус краснеет, если убрать запись» — уже с трудом. Проверяемость обычно длиннее фразы.
    pa.add_argument("--done-when-file", dest="done_when_file")

    pk = sub.add_parser("criterion", help="записать/изменить критерий приёмки существующей карточки")
    dryrun.add_argument(pk)
    pk.add_argument("id", type=int)
    pk.add_argument("--actor", required=True)
    pk.add_argument("--text", default="")
    pk.add_argument("--text-file", dest="text_file")

    pl = sub.add_parser("list")
    pl.add_argument("--role", required=True)
    pl.add_argument("--status", default="open", help="open|all|<конкретный статус>")
    pl.add_argument("--only-mine", action="store_true", dest="only_mine", help="без SHARED")
    pl.add_argument("--older-than-days", type=int, default=None, dest="older_than_days",
                    help="только карточки СТАРШЕ N суток — напоминание о залежавшемся "
                         "(карточка #86 ⑧): свежие не показываются")

    ps = sub.add_parser("show")
    ps.add_argument("id", type=int)

    pt = sub.add_parser("status")
    dryrun.add_argument(pt)
    pt.add_argument("id", type=int)
    pt.add_argument("new_status")
    pt.add_argument("--actor", required=True)
    pt.add_argument("--foreign", default=None, metavar="РОЛЬ",
                    help="меняешь статус ЧУЖОЙ карточки — назови её владельца. Инструмент "
                         "сверит имя с базой: не совпало — откажет и покажет верное")
    pt.add_argument("--note", default="")
    pt.add_argument("--note-file", dest="note_file")

    pc = sub.add_parser("comment")
    dryrun.add_argument(pc)
    pc.add_argument("id", type=int)
    pc.add_argument("--actor", required=True)
    pc.add_argument("--body", default="")
    pc.add_argument("--body-file", dest="body_file")

    a = p.parse_args()
    a.db = str(resolve_db(a.db, __file__))   # R15a: от расположения скрипта, не от CWD
    # ⚠️ getattr, а не a.dry_run: у читающих подкоманд флага НЕТ по замыслу —
    # ставить его туда, где нечего сохранять, значит учить, что он бывает бесполезен.
    conn = _conn(a.db, getattr(a, "dry_run", False))
    {"add": cmd_add, "list": cmd_list, "show": cmd_show,
     "status": cmd_status, "comment": cmd_comment, "criterion": cmd_criterion}[a.cmd](conn, a)
    conn.close()


if __name__ == "__main__":
    # 🪤 Оплачено @CORE 2026-08-06 15:36 UTC (#3006): его вызов упал трассировкой, потому что
    # инструмент правился ЗА 16 СЕКУНД до этого — тело команды уже читало новый аргумент,
    # а разбор ещё не объявлял его. Поломки не было; была ГОНКА с правкой общего инструмента.
    # Он не побежал звать контур только потому, что сверил время файла руками — то есть спасла
    # привычка, а не механизм. Другая роль честно отчиталась бы о поломке общего инструмента,
    # и контур искал бы несуществующий дефект.
    # ⇒ При падении печатаем возраст самого файла: «свежее твоего вызова» видно без археологии.
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        import traceback
        traceback.print_exc()
        try:
            age = time.time() - Path(__file__).stat().st_mtime
            if age < 120:
                print(f"\n⚠️ ЭТОТ ИНСТРУМЕНТ ПРАВИЛСЯ {age:.0f} с НАЗАД — вероятно, ты попал МЕЖДУ "
                      f"двумя сохранениями.\n   Повтори вызов. Если повторилось — это дефект, "
                      f"и о нём стоит сказать @COORD.", file=sys.stderr)
            else:
                print(f"\n(файл инструмента не менялся {age/60:.0f} мин — на гонку с правкой "
                      f"не похоже, это дефект)", file=sys.stderr)
        except OSError:
            pass
        sys.exit(1)
