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

⚠️ ЧЕМ СОЗДАВАТЬ ФАЙЛ ДЛЯ --body-file / --note-file / --text-file (оплачено 27.08 15:05 UTC,
@STUD, записки #3987 и #3991). Файл клади ИНСТРУМЕНТОМ ЗАПИСИ ФАЙЛА, а этот вызов зови
ОТДЕЛЬНОЙ командой. Составной ход «записать файл оболочкой И тем же ходом позвать
инструмент» у @STUD был отклонён средой прогона дословно: «Permission for this action was
denied by the Claude Code auto mode classifier. Reason: Blocked by classifier.»
🪤 Отказ накрыл ВЕСЬ составной ход — и роль прочла его как отказ ЭТОГО инструмента.
Разделив ход, она померила половины по отдельности: холостой прогон карточек прошёл,
отказала только запись файла. То есть здесь не отказывали ни разу.
⚖️ Отказ НЕ всегда, и это не со слов — тело: @PROTO 27.08 15:19 UTC завела карточку #323
ТЕМ ЖЕ инструментом, ТЕМ ЖЕ составным ходом (два heredoc и вызов одной командой) и с таким
же длинным русским текстом — ПРОШЛО. У @STUD за четверть часа до того — отказ.
⇒ Разный исход у одного класса вызова в одних условиях. Значит дело не в длине и не в форме
записи, и подобрать «безопасную форму» перебором нельзя.
🩸 Тем он и опасен: **редкий отказ опаснее постоянного.** Постоянный роль перемеряет,
редкий — объясняет себе догадкой, и догадка садится в записку как факт.
📌 И зелёный перемер тут ничего не снимает: @STUD 27.08 16:05 UTC перемерил и получил
зелёное — но померил ОДИН ход и короткую строку, то есть лёгкий случай вместо тяжёлого.
Он назвал это сам. Замер, подменивший случай, закрывает предмет, которого не касался.
📌 И оттуда же: **текст отказа сохраняй ДОСЛОВНО**, а не смыслом. Пересказ «отказал в праве»
увёл чужой замер искать в этом файле ветку про право, которой тут нет вовсе.
"""

import argparse
import datetime
import json
import re
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
#   frozen — ЗАМОРОЖЕНА (П① пула, 27.08). НЕ то же, что blocked: blocked значит «жду
#     ЧУЖУЮ работу» (дело движется не мной), frozen — «сознательно отложена ВНЕ пула,
#     разбудит НАЗВАННОЕ УСЛОВИЕ». Слить их — повторить оплаченный класс «одно значение
#     на две беды». Условие разморозки ОБЯЗАТЕЛЬНО и живёт в blocked_reason (оно уже
#     на витрине). frozen НЕ входит в открытые: открытый список — то, что живо сейчас.
STATUSES = ["open", "in_progress", "blocked", "awaiting_word", "in_review", "done",
            "failed", "dropped", "frozen"]
OPEN_STATUSES = ["open", "in_progress", "blocked", "awaiting_word", "in_review"]
PRIORITY_ORDER = {"critical": 0, "high": 1, "normal": 2, "low": 3}


def active_pool_tracks(conn):
    """Живые пулы (tracks.status='active'). Новый порядок (слово владельца 27.08 18:33 UTC):
    весь контур работает над ОДНИМ пулом связанных задач за раз, карточки пула — первыми.
    Пустое множество = пула нет, и тогда порядок прежний и никакой «секции пула» не печатается.
    Таблицы tracks может не быть (копия-песочница старой схемы) — это не повод ронять список."""
    try:
        return {r[0] for r in conn.execute("SELECT track_id FROM tracks WHERE status='active'")}
    except sqlite3.OperationalError:
        return set()


def direction_focus(conn):
    """Направление-фокус (карточка #399, слово владельца 29.08 14:39 UTC) → (имя | None).

    Механизм опирается на ЕДИНСТВЕННЫЙ активный набор задач: при нуле или нескольких
    активных возвращает None — ворота фокуса НЕ судятся. Судить «вне направления» при
    двух направлениях значит красить всё; замер 29.08: активных два, и это само по себе
    размывает направление (норма нового порядка — один, судьба лишнего — слово владельца)."""
    pools = active_pool_tracks(conn)
    return next(iter(pools)) if len(pools) == 1 else None


def offpool_share(conn, direction):
    """Живая доля взятий ВНЕ направления за 3 суток → (вне, всего). Не хранится —
    вычисляется при каждом чтении (тот же довод, что у просрочки П②)."""
    row = conn.execute(
        "SELECT COUNT(*), SUM(CASE WHEN COALESCE(b.parent_track,'') <> ? THEN 1 ELSE 0 END) "
        "FROM backlog_events e JOIN backlog b ON b.id = e.backlog_id "
        "WHERE e.event_type='claim' AND e.at > datetime('now','-3 day')",
        (direction,)).fetchone()
    return (row[1] or 0), (row[0] or 0)


def pool_sort_key(pools):
    """Ключ «карточки пула первыми, внутри — прежний порядок (срочность, номер)».
    ЕДИНСТВЕННОЕ место, где живёт этот порядок: его же импортирует витрина пробуждения
    (backlog_view) — вторая копия ключа разошлась бы с этой молча при первой правке.
    Ожидает кортежи, где [4] = priority, [0] = id, ПОСЛЕДНЕЕ поле = parent_track."""
    def key(r):
        return (0 if (pools and r[-1] in pools) else 1,
                PRIORITY_ORDER.get(r[4], 9), r[0])
    return key


def live_and_overdue(conn, card_ids):
    """Живые и ПРОСРОЧЕННЫЕ объявления по карточкам — ЕДИНСТВЕННЫЙ источник предиката
    (П② пула, 27.08): его зовут список карточек, обзор пробуждения, витрина пула
    (track.py) и механизм сна. Предикат НЕ хранится — вычисляется при каждом чтении:
    хранимое поле гашения умерло с нулём вызовов, вычисляемая срочность живёт.
    Просрочено = срок объявления вышел, карточка не закрыта, объявление не снято,
    и ПОСЛЕ срока от роли на карточке ни одного события. Демона нет.
    Возвращает (живые[(id, роль, до, что)], просроченные[(id, роль, до, что, часов)])."""
    alive, overdue = [], []
    now = conn.execute("SELECT datetime('now')").fetchone()[0]
    for bid in card_ids:
        ev = conn.execute(
            "SELECT actor_role, event_type, body_md FROM backlog_events "
            "WHERE backlog_id=? AND event_type IN ('claim','claim_release') "
            "ORDER BY id DESC LIMIT 1", (bid,)).fetchone()
        if not ev or ev[1] == "claim_release":
            continue
        actor, _, body = ev
        m = re.match(r"до (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC · (.*)", body or "")
        if not m:
            continue
        until, note = m.group(1), m.group(2)
        status = conn.execute("SELECT status FROM backlog WHERE id=?", (bid,)).fetchone()[0]
        if status in ("done", "failed", "dropped"):
            continue
        if until >= now:
            alive.append((bid, actor, until, note))
        else:
            later = conn.execute(
                "SELECT 1 FROM backlog_events WHERE backlog_id=? AND actor_role=? AND at>?",
                (bid, actor, until)).fetchone()
            if not later:
                hours = conn.execute(
                    "SELECT CAST((julianday('now')-julianday(?))*24 AS INTEGER)",
                    (until,)).fetchone()[0]
                overdue.append((bid, actor, until, note, hours))
    return alive, overdue


def pool_open_ids(conn, pools):
    """Открытые карточки живых пулов — ВСЕХ ролей: просрочку видит любой читающий."""
    if not pools:
        return []
    ph = ",".join("?" * len(pools))
    st = ",".join("?" * len(OPEN_STATUSES))
    return [r[0] for r in conn.execute(
        f"SELECT id FROM backlog WHERE parent_track IN ({ph}) AND status IN ({st})",
        list(pools) + list(OPEN_STATUSES))]


# карточка #384 (слово владельца 29.08.2026): показ «UTC (местное)» вернулся — но ОДНИМ
# местом, модулем local_time.py (зона host OS на дату записи; хранение — только UTC).
# Прежнее надгробие «конвертации больше нет» снято тем же словом; разбор — в модуле.
try:
    from local_time import utc_to_local
except Exception:  # noqa: BLE001 — без модуля витрина живёт: прежний показ «только UTC»
    def utc_to_local(s, tz=None):
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


def cmd_claim(conn, a):
    """Объявить работу над карточкой. Видно коллегам при пробуждении и в общем прогоне."""
    row = conn.execute("SELECT role, status, title, parent_track FROM backlog WHERE id=?",
                       (a.id,)).fetchone()
    if not row:
        sys.exit(f"⛔ карточки #{a.id} нет")
    owner, status, title, track = row
    in_pool = track and track in active_pool_tracks(conn)
    if a.release:
        # П② (27.08): снятие с ПУСТЫМ «что получилось» — предупреждение, не отказ.
        # Пустой итог у коллеги читается как «бросил молча»; доля пустых замеряется
        # по событиям, принуждать рано.
        # ═══ Карточка #451 (CHROME; замер 6/23 подстановок, 5/7 у нечастых рук):
        # прежде совет печатался, а событие с подстановкой «работа окончена или
        # отложена» ложилось ТЕМ ЖЕ ходом — дописать было нечем, ложный след жил
        # навсегда. Сдвинут МИГ, не строгость: пустой итог НЕ записывается вовсе,
        # объявление гаснет само, ход дописать остаётся за ролью; код 0, не отказ.
        # Текст совета — дословно прежний (условие ③ разбора замысла в карточке).
        if not (a.note or "").strip():
            print("⚠️ снимаешь объявление БЕЗ итога: что получилось? Коллега увидит "
                  "только «работа окончена» — добавь --note")
            print(f"   объявление НЕ снято — оно гаснет само; снять с итогом: "
                  f"backlog.py claim {a.id} --actor {a.actor} --release "
                  f"--note \"что получилось\"")
            return  # 451: пустое снятие не записывается
        _event(conn, a.id, a.actor, "claim_release", a.note)
        conn.commit()
        print(f"🔓 снято объявление о работе над #{a.id} «{title[:50]}»")
        return
    if not a.note.strip():
        sys.exit(f"⛔ скажи, ЧТО делаешь: коллега видит эту строку и по ней решает, ждать "
                 f"ему или браться самому. «Работаю» ему не говорит ничего.")
    # ═══ Карточка #399 ступень ② (слово владельца 29.08 14:39 UTC): взятие карточки ВНЕ
    # ЕДИНСТВЕННОГО активного набора — ПРЕДУПРЕЖДЕНИЕ с живой долей (ступень А; отказ —
    # только отдельным ходом по замеру этой доли: ложный отказ дороже пропуска).
    # Лазейка --off-pool «причина» — для законного вне-направления (срочная починка
    # инструмента, слово владельца): причина ложится СОБЫТИЕМ в журнал карточки и видна
    # поимённо. Пустая причина неотличима от её отсутствия — отказ.
    направление = direction_focus(conn)
    off = getattr(a, "off_pool", None)
    if off is not None and not off.strip():
        # Отказ ЕДИН для всех состояний мира: флаг с пустой причиной — ошибка вызова везде.
        sys.exit("⛔ --off-pool требует ПРИЧИНУ словами: пустая причина "
                 "не отличима от её отсутствия")
    if направление and (track or "") != направление:
        if off is not None:
            _event(conn, a.id, a.actor, "off_pool", off.strip())
            print(f"📝 взято ВНЕ направления {направление} с причиной вслух — "
                  f"она в журнале карточки")
        else:
            вне, всего = offpool_share(conn, направление)
            print(f"⚠️ карточка ВНЕ направления контура ({направление}). За 3 суток "
                  f"так взято {вне} из {всего}. Есть причина — назови её вслух: "
                  f"--off-pool \"<причина>\" (ляжет событием в журнал)")
    elif off is not None:
        # ═══ Карточка #405 (замер @CHROME при приёмке #399): ветка обязана различать
        # ТРИ состояния мира, а не два. Первая редакция отвечала «карточка в направлении»
        # и при направление=None — обе половины сообщения не соответствовали миру,
        # а названная причина ТЕРЯЛАСЬ МОЛЧА: летопись «кто брал вне направления
        # и почему» несла бы дыру за период двух активных наборов, и дыра читалась бы
        # как «никто не брал», а не как «не записывали».
        if направление:
            # Причина при взятии карточки САМОГО направления — не ошибка, но событие
            # не пишем: журнал «вне направления» обязан значить ровно это.
            print("ℹ️ карточка в направлении — причина --off-pool не нужна, "
                  "событие не пишется")
        else:
            _event(conn, a.id, a.actor, "off_pool", off.strip())
            print("📝 направления сейчас НЕТ (активных наборов не один) — причина "
                  "всё равно записана событием в журнал карточки: иначе летопись "
                  "«кто брал вне направления и почему» несла бы дыру за этот период")
    # ═══ Карточка #441 (STUD; два столкновения за 20 минут 29.08): взятие карточки,
    # которую УЖЕ держит другая роль, называет её имя и час — ПРЕДУПРЕЖДЕНИЕ, не отказ
    # (двое на одной карточке иногда законны: сдающий и приёмщик). Живое чужое взятие =
    # последний claim роли без более позднего claim_release, срок которого не истёк;
    # истёкший шаг тихий — иначе роль научится пролистывать.
    сейчас = conn.execute("SELECT datetime('now')").fetchone()[0]
    for кто, тело in conn.execute(
            "SELECT e.actor_role, e.body_md FROM backlog_events e "
            "WHERE e.backlog_id=? AND e.event_type='claim' "
            "AND UPPER(e.actor_role)<>UPPER(?) "
            "AND e.id=(SELECT MAX(e2.id) FROM backlog_events e2 "
            "          WHERE e2.backlog_id=e.backlog_id AND e2.event_type='claim' "
            "          AND UPPER(e2.actor_role)=UPPER(e.actor_role)) "
            "AND NOT EXISTS (SELECT 1 FROM backlog_events r "
            "          WHERE r.backlog_id=e.backlog_id AND r.event_type='claim_release' "
            "          AND UPPER(r.actor_role)=UPPER(e.actor_role) AND r.id>e.id)",
            (a.id, a.actor)):
        m = re.match(r"до (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) UTC", тело or "")
        if m and m.group(1) > сейчас:
            print(f"⚠️ карточку #{a.id} УЖЕ ДЕРЖИТ {кто} — до {m.group(1)[:16]} UTC: "
                  f"«{(тело or '').split('·', 1)[-1].strip()[:100]}»")
            print("   Двое на одной карточке иногда законны (сдающий и приёмщик), чаще — "
                  "столкновение. Твоё взятие всё равно записано ниже, оба видны в журнале.")
    # ═══ П② (27.08): шаг карточки ПУЛА — 60 минут вместо 120; длиннее 90 — предупреждение.
    # Короткая итерация встроена ВОРОТАМИ инструмента, а не попрошена правилом.
    minutes = a.minutes if a.minutes is not None else (60 if in_pool else 120)
    if in_pool and minutes > 90:
        print(f"⚠️ шаг длинный ({minutes} мин) для карточки пула — раздели: "
              f"норма пула 60, потолок без вопросов 90")
    until = conn.execute("SELECT datetime('now', ?)", (f"+{minutes} minutes",)).fetchone()[0]
    _event(conn, a.id, a.actor, "claim", f"до {until} UTC · {a.note}")
    if status == "open":
        conn.execute("UPDATE backlog SET status='in_progress', updated_at=datetime('now')"
                     " WHERE id=?", (a.id,))
    conn.commit()
    чужая = "" if owner.upper() == a.actor.upper() else f" (карточка роли {owner})"
    print(f"🔧 ВЗЯТО В РАБОТУ #{a.id}{чужая} «{title[:50]}» до {until[:16]} UTC")
    print(f"   что делаешь: {a.note}")
    print("   Видно коллегам при пробуждении и в общем прогоне проверок. Гаснет само —")
    print("   снимать не обязательно; досрочно: backlog.py claim {} --actor {} --release"
          .format(a.id, a.actor))
    # Карточка #441, третий встречный (случай TAXO/лента): граница названа ЧЕСТНО —
    # тишина выше не значит «свободна», машина видит только взятия инструментом.
    print("   ⚖️ проверено ТОЛЬКО против взятий ИНСТРУМЕНТОМ: объявление комментарием "
          "или запиской в ленте машина не читает")
    # 2.2 (28.08): claim и есть «чем занята роль» — статус тем же вызовом, кнопки нет.
    try:
        conn.execute(
            "INSERT INTO role_status (role, status, updated_at) "
            "VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(role) DO UPDATE SET status = excluded.status, "
            "updated_at = excluded.updated_at",
            (a.actor.upper(), f"взял в работу карточку #{a.id} (до {until[:16]} UTC): "
                              f"{a.note[:140]}"))
        conn.commit()
    except Exception as e:                            # noqa: BLE001
        print(f"⚠️ статус роли НЕ обновлён ({type(e).__name__}) — объявление записано",
              file=sys.stderr)

# ═══ Карточка #430 ступень ② (правило interview-before-recommend; слово владельца
# 29.08 21:24 UTC, чат PROTO). Разбор замысла — ВОПРОСАМИ, и вопросы РАЗНЫЕ для разных
# видов работы: один набор на всё горит всегда и потому не значит ничего (текст правила).
# Вид угадывается по ТЕГАМ карточки; не угадался — набор «прочее». Это ПОДСКАЗКА
# и ПРЕДУПРЕЖДЕНИЕ, не ворота: блокировка наказывала бы правильное поведение
# (🔴-провал критерия карточки #430). Ответы никуда не вводятся и не проверяются.
ОБЯЗАТЕЛЬНЫЙ_ВОПРОС = "НА ЧЕЙ ВОПРОС ОТВЕЧАЕТ ПРЕДЛАГАЕМОЕ? (умение вещи ≠ нужда спрашивающего)"
ВИДЫ_ВОПРОСОВ = [
    ({"rules", "rule", "skills", "norm"}, "правило/норма", [
        "кому это сказано — зона и адресат (зона рук)?",
        "когда и чем это протухнет — срок годности (порядок)?",
        "чем держится: норма поведения или механизм (режим отказа)?"]),
    ({"security", "secrets", "rotation", "access"}, "секреты/доступ", [
        "что утечёт или сломается при провале (цена ошибки)?",
        "как узнаешь, что защита ОТКАЗАЛА (режим отказа)?",
        "откатывается ли одним ходом (порядок)?"]),
    ({"tools", "tool", "acceptance", "guard", "bite", "mezosync"}, "инструмент/проверка", [
        "какой краевой случай её ослепит (краевой случай)?",
        "у каждого требования есть встречный случай (охват)?",
        "что увидит роль при отказе — молчание или слово (режим отказа)?"]),
]
ВОПРОСЫ_ПРОЧЕЕ = ("прочее", [
    "есть ли путь дешевле (альтернатива)?",
    "боль в числах: сколько раз и почём (боль в числах)?",
    "чьи руки нужны кроме твоих (зона рук)?"])


def вид_и_вопросы(tags_json):
    """Вид работы по тегам карточки → (имя вида, три вопроса разбора)."""
    try:
        теги = {t.strip().lower() for t in json.loads(tags_json or "[]")}
    except Exception:                                  # noqa: BLE001 — кривые теги ≠ отказ
        теги = set()
    for ключи, имя, вопросы in ВИДЫ_ВОПРОСОВ:
        if теги & ключи:
            return имя, вопросы
    return ВОПРОСЫ_ПРОЧЕЕ


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

    # ⚠️ Предупреждение о неразрешимых ссылках — ПОСЛЕ проверок отказа и ДО записи. Порядок важен:
    # проверка отказа говорит «карточка НЕ заведена», предупреждение — «заведена, но читателю
    # со стороны будет трудно». Смешать их значило бы утопить отказ в шуме.
    warn_dangling(body, label="тело карточки")
    warn_dangling(done_when, label="критерий")

    # ═══ П① (27.08): при живом пуле НОВОЕ — В ПУЛ. Предупреждение осталось для случая
    # «активных наборов не один». Встречный держится сам: пула нет — строки нет.
    # ═══ Карточка #399 ступень ③ (слово владельца 29.08 14:39 UTC): при ЕДИНСТВЕННОМ
    # активном наборе новое ВНЕ его рождается ЗАМОРОЖЕННЫМ с условием разморозки —
    # заявка не теряется, но и не становится открытым соблазном взять её мимо
    # направления (замер 29.08: за 3 суток 71% новых карточек — вне наборов).
    # Слово владельца в чате роли всегда выше этих ворот.
    pools = active_pool_tracks(conn)
    направление = next(iter(pools)) if len(pools) == 1 else None
    статус, причина_мороза = "open", None
    if pools and not a.track:
        if направление:
            статус = "frozen"
            причина_мороза = (f"направление-фокус: заведена вне направления {направление} — "
                              f"разморозка после закрытия набора; раньше — слово владельца "
                              f"или status <id> open --note <причина>")
            print(f"🧊 направление контура — {направление}: карточка ВНЕ его заводится "
                  f"ЗАМОРОЖЕННОЙ (заявка не теряется и не соблазняет). Разморозить: "
                  f"после закрытия набора, раньше — слово владельца или причина вслух")
        else:
            print(f"⚠️ активных наборов {len(pools)} — норма ОДИН, фокус не судится; "
                  f"новое — только в пул ({', '.join(sorted(pools))}): назови пул "
                  f"(--track) или причину, почему карточка живёт вне его")

    cur = conn.execute(
        "INSERT INTO backlog (role, title, body_md, status, blocked_reason, priority, tags, parent_id, parent_track, created_by, done_when) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (a.role.upper(), a.title, body, статус, причина_мороза, a.priority, tags, a.parent,
         a.track, (a.actor or a.role).upper(), done_when))
    bid = cur.lastrowid
    _event(conn, bid, a.actor or a.role, "created", f"created: {a.title}", None, статус)
    if done_when:
        _event(conn, bid, a.actor or a.role, "criterion_set", f"критерий: {done_when}")
    conn.commit()
    print(f"✅ backlog #{bid} [{a.role.upper()}] «{a.title}» ({a.priority}, {статус})")
    if done_when:
        print(f"   🎯 критерий: {done_when}")
        # Приём обязан быть так же честен, как отказ — просьба @ING (#3231) с двумя его
        # собственными экземплярами за час: критерий БЫЛ на месте и вёл преемника в ложное
        # место (имя функции вместо имени триггера ⇒ красное по ложной причине; проверка
        # существования вместо тела ⇒ зелёное по ложной причине).
        # ⇒ «критерий есть» — не «карточка в порядке». Наличие ≠ годность, и годность
        # машинно непроверяема. Молчать об этом значило бы выдать зелёный сигнал за приёмку.
        print("   ⚖️ записан — проверяет ли он то, что нужно, машина не знает")

    # ═══ Карточка #430 ступень ②: три вопроса разбора — ПОДСКАЗКОЙ, ПОСЛЕ записи.
    # Пустой ответ ничего не блокирует (встречный③ критерия): карточка уже заведена.
    имя_вида, вопросы = вид_и_вопросы(tags)
    print(f"   💬 разбор замысла — три вопроса к себе (вид: {имя_вида}; подсказка, не ворота):")
    for в in вопросы:
        print(f"      · {в}")


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

    pools = active_pool_tracks(conn)
    rows = conn.execute(
        f"SELECT id, role, title, status, priority, tags, done_when, parent_track FROM backlog "
        f"WHERE {where_role} AND {where_status} AND {where_age}", params).fetchall()
    rows.sort(key=pool_sort_key(pools))

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
    # ═══ ПУЛ ПЕРВЫМ (шаг 0 нового порядка, слово владельца 27.08 18:33 UTC) ═══
    # Карточки активного пула стоят В НАЧАЛЕ списка и помечены 🎯. У роли без карточек
    # пула это сказано СЛОВАМИ: пустая секция неотличима от «пула нет» — класс
    # «молчащий отказ читается как успех», он в контуре уже оплачен.
    if pools:
        in_pool = sum(1 for r in rows if r[7] in pools)
        имя_пула = ", ".join(sorted(pools))
        if len(pools) > 1:
            print(f"⚠️ активных пулов {len(pools)} ({имя_пула}) — норма нового порядка: ОДИН")
        if in_pool:
            print(f"🎯 пул {имя_пула}: твоих карточек {in_pool} — они первыми")
        else:
            print(f"🎯 в пуле ({имя_пула}) твоих карточек нет")
        # ═══ П② (27.08): ПРОСРОЧЕННЫЕ объявления пула — при КАЖДОМ чтении, у ЛЮБОЙ
        # роли (не только виновной): застрявший шаг пула — общая новость. Предикат
        # вычисляется сейчас, не хранится; демона нет. Роль БЕЗ объявления просрочки
        # не имеет: молчание без объявления законно.
        _, overdue = live_and_overdue(conn, pool_open_ids(conn, pools))
        for bid, actor, _until, note, hours in overdue:
            print(f"⏰ {actor} молчит над карточкой #{bid} — шаг истёк {hours} ч назад "
                  f"({note[:60]})")
        print()
    icon = {"open": "○", "in_progress": "◐", "blocked": "⛔", "awaiting_word": "🙋",
            "in_review": "👀", "done": "✅", "failed": "💥", "dropped": "✗", "frozen": "🧊"}
    no_criterion = 0
    for bid, role, title, status, prio, tags, done_when, track in rows:
        pr = {"critical": "‼️", "high": "⬆️", "normal": "·", "low": "⬇️"}.get(prio, "·")
        tg = " ".join(f"#{t}" for t in json.loads(tags or "[]"))
        shared = " (SHARED)" if role == "SHARED" else ""
        # ✎ — подсветка «критерия нет». Слово владельца 06.08 15:26 UTC: подсветить, НЕ блокировать.
        # Стоит ЗДЕСЬ, а не отдельной командой, по замечанию @opssre (#3002): витрину, которую надо
        # позвать, надо помнить — а роль эту строку и так видит каждый раз.
        mark = "  " if done_when else " ✎"
        if not done_when and status in OPEN_STATUSES:
            no_criterion += 1
        pool_mark = "🎯" if (pools and track in pools) else ""
        print(f"  {pool_mark}#{bid} {icon.get(status,'?')} {pr}{mark} {title}{shared}  {tg}")
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
            print(f"        ✗ причина: {why[0][:140] if why else 'НЕ ЗАПИСАНА (карточка закрыта до того, как причину стали требовать, 14.08)'}")
        # Замороженная обязана показывать, ЧТО её разбудит, — условие без витрины
        # умирает как всякое поле «пишется-не-читается» (П① пула, 27.08).
        if status == "frozen":
            cond = conn.execute("SELECT blocked_reason FROM backlog WHERE id=?", (bid,)).fetchone()
            print(f"        🧊 {cond[0][:140] if cond and cond[0] else 'условие разморозки НЕ ЗАПИСАНО — так быть не должно, ворота его требуют'}")
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
    row = conn.execute("SELECT status, done_when, title, role, parent_track, tags FROM backlog WHERE id = ?",
                       (a.id,)).fetchone()
    if not row:
        print(f"ERR: backlog #{a.id} не найден", file=sys.stderr)
        sys.exit(1)
    old, done_when, title, owner, card_track, card_tags = row

    # ═══ Карточка #399 ступень ② (та же, что у claim): перевод В РАБОТУ карточки вне
    # ЕДИНСТВЕННОГО активного набора — предупреждение с живой долей. Только in_progress:
    # закрытия, заморозки и возвраты не судятся — они не «взятие».
    if a.new_status == "in_progress":
        направление = direction_focus(conn)
        if направление and (card_track or "") != направление:
            вне, всего = offpool_share(conn, направление)
            print(f"⚠️ карточка ВНЕ направления контура ({направление}). За 3 суток "
                  f"взятий вне направления {вне} из {всего}. Есть причина — возьми через "
                  f"claim с --off-pool \"<причина>\": она ляжет событием в журнал")

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
    # а сломанную проверку обходят. ⇒ Не запрещаем, а требуем НАЗВАТЬ, и сверяем названное.
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
    # Почему ОТКАЗ, а не подсветка. Замер @PROTO 10:23 UTC: 37 закрытых карточек из 41 — БЕЗ
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

    # ═══ Карточка #430 ступень ②: вынос вопроса/рекомендации владельцу БЕЗ объявленного
    # разбора замысла — ПРЕДУПРЕЖДЕНИЕ С ИМЕНЕМ незаданного вопроса, не отказ (отказ
    # наказывал бы правильное поведение — 🔴-провал критерия). Прошедший разбор говорит
    # это флагом --interviewed и проходит ТИХО: протокол вопросов НЕ требуется и не
    # проверяется — так стоит в самом правиле («роль несёт рекомендацию тихо»).
    # Слово владельца «хватит» тоже останавливает разбор — и эти ворота ничего
    # не запирают: перевод состоится в любом случае.
    if a.new_status == "awaiting_word" and not a.interviewed:
        имя_вида, вопросы = вид_и_вопросы(card_tags)
        print(f"⚠️ вынос владельцу БЕЗ объявленного разбора замысла "
              f"(правило interview-before-recommend). Незаданные вопросы (вид: {имя_вида}):")
        print(f"   · {ОБЯЗАТЕЛЬНЫЙ_ВОПРОС}")
        for в in вопросы[:2]:
            print(f"   · {в}")
        print("   разбор пройден — скажи это флагом --interviewed; перевод НЕ задержан")

    if a.new_status == "dropped" and not note.strip():
        print(f"⛔ backlog #{a.id} «{title}» — ПРИЧИНЫ НЕТ, объявить устаревшей нельзя.",
              file=sys.stderr)
        print("   Почему предмет больше не нужен? Если заменён — назови заменившую карточку.",
              file=sys.stderr)
        print(f'   backlog.py status {a.id} dropped --actor {a.actor} '
              f'--note "причина; заменено: карточка #N"', file=sys.stderr)
        sys.exit(1)

    # ⛔ ВОРОТА: «заморожена» БЕЗ УСЛОВИЯ РАЗМОРОЗКИ не бывает (П① пула, 27.08).
    # Заморозка без условия — это dropped, стесняющийся себя: карточка молчит, ЧТО её
    # разбудит, и лежит вечно. Условие — событие или дата, а не «когда-нибудь».
    if a.new_status == "frozen" and not note.strip():
        print(f"⛔ backlog #{a.id} «{title}» — ЗАМОРОЗИТЬ БЕЗ УСЛОВИЯ РАЗМОРОЗКИ нельзя.",
              file=sys.stderr)
        print("   Что её разбудит? Событие или дата. «Отпала насовсем» — это dropped.",
              file=sys.stderr)
        print(f'   backlog.py status {a.id} frozen --actor {a.actor} '
              f'--note "условие разморозки: <событие или дата>"', file=sys.stderr)
        sys.exit(1)

    # причина стоянки хранится одинаково для «жду чужую работу», «жду слово» и «заморожена»
    blocked_reason = note if a.new_status in ("blocked", "awaiting_word", "frozen") else None
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

    # ═══ П⑤ (27.08): карточка, рождённая каналом issues, при закрытии напоминает
    # закрыть и issue — иначе заявка снаружи висит открытой при сделанной работе,
    # и читатель образца решает, что контур молчит.
    if a.new_status in ("done", "dropped", "failed"):
        try:
            теги = conn.execute("SELECT tags FROM backlog WHERE id=?", (a.id,)).fetchone()[0]
            m = re.search(r"gordi-issue #(\d+)", теги or "")
            if m:
                print(f"📮 карточка несёт тег gordi-issue #{m.group(1)} — закрой и issue "
                      f"ссылкой на коммит: gordi-issue.py close --role COORD "
                      f"--number {m.group(1)} --note \"починено: <коммит>\" (рукой COORD)")
        except Exception:                             # noqa: BLE001
            pass

    # ═══ П② (27.08): взятие карточки ПУЛА в работу требует ЖИВОГО объявления — пока
    # ПРЕДУПРЕЖДЕНИЕМ (доля замеряется по событиям). Объявление говорит коллегам ЧТО
    # и НА СКОЛЬКО; смена статуса без него — молчаливая работа, её не видит витрина пула.
    if a.new_status == "in_progress":
        try:
            pools = active_pool_tracks(conn)
            трек = conn.execute("SELECT parent_track FROM backlog WHERE id=?",
                                (a.id,)).fetchone()[0]
            if трек and трек in pools:
                alive, _ = live_and_overdue(conn, [a.id])
                if not alive:
                    print(f"⚠️ карточка пула взята в работу БЕЗ живого объявления — "
                          f"скажи, что и на сколько: backlog.py claim {a.id} "
                          f"--actor {a.actor} --note \"…\"")
        except Exception as e:                        # noqa: BLE001
            print(f"⚠️ проверка объявления не выполнена ({type(e).__name__})", file=sys.stderr)

    # ═══ СТАТУС РОЛИ — ТЕМ ЖЕ ВЫЗОВОМ (шаг 0 пула, слово владельца 27.08 18:33 UTC) ═══
    # Отдельная кнопка статуса мертва замером 27.08: PROTO не трогал её 22 дня, TAXO 20,
    # STUD 16. Закрытие карточки активного пула и есть событие «чем занята роль» —
    # оно записывается в role_status тем же ходом, кнопку помнить не надо.
    # Только ЗАКРЫВАЮЩИЕ статусы: чтение и промежуточные смены статус не трогают, иначе
    # он перестанет значить. 2.2 (28.08): расширено с карточек ПУЛА на любое закрытие —
    # закрытие и есть событие «чем занята роль». Время в текст не пишется — оно уже
    # в updated_at, вторая шкала родила бы расхождение (класс двух шкал оплачен).
    # Ошибка здесь не вправе отменить уже сделанную смену статуса карточки — только слова.
    if a.new_status in ("done", "failed", "dropped"):
        try:
            pools = active_pool_tracks(conn)
            карточкин_пул = conn.execute(
                "SELECT parent_track FROM backlog WHERE id = ?", (a.id,)).fetchone()[0]
            в_пуле = bool(карточкин_пул) and карточкин_пул in pools
            текст = (f"карточка #{a.id} «{title[:70]}» → {a.new_status}"
                     + (f" — {note[:120]}" if note else "")
                     + (f" (пул {карточкин_пул})" if в_пуле else "")
                     + " [записано закрытием карточки]")
            conn.execute(
                "INSERT INTO role_status (role, status, updated_at) "
                "VALUES (?, ?, datetime('now')) "
                "ON CONFLICT(role) DO UPDATE SET status = excluded.status, "
                "updated_at = excluded.updated_at", (actor, текст))
            conn.commit()
            print(f"📌 статус роли {actor} обновлён ТЕМ ЖЕ вызовом"
                  + (f" (пул {карточкин_пул})" if в_пуле else ""))
        except Exception as e:                    # noqa: BLE001
            print(f"⚠️ статус роли НЕ обновлён ({type(e).__name__}) — карточка закрыта, "
                  f"статус запиши рукой", file=sys.stderr)


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


READ_CMDS = {"show", "list"}
# ═══ Карточка #391: читающее/пишущее — СПИСКОМ подкоманд, не эвристикой ══════════════
# Под чужим объявлением о правке (lease.py) читающие подкоманды получают ПРЕДУПРЕЖДЕНИЕ
# и работают: приёмщик обязан мочь читать ТЕЛА карточек во время чужой правки — замер
# @CHROME (записка #4143 §④): под объявлением show отказал, и он судил бы по пересказу
# критерия из записок (у карточки было ТРИ половины критерия, из записки видна одна).
# Пишущие (add/criterion/status/claim/comment) — отказ, как прежде: правка во время
# чужой отладки смешала бы две работы. Новую подкоманду сюда вносить ТОЛЬКО если она
# не пишет в базу совсем — предупреждение вместо отказа у пишущей молча снимет замок.


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
                    # карточку без критерия можно, ЗАКРЫТЬ как done — нельзя (отказ введён 07.08).
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
    pt.add_argument("--interviewed", action="store_true",
                    help="разбор замысла пройден — предупреждение при «жду слова» молчит "
                         "(карточка #430 ②; протокол вопросов не требуется)")

    # 🪤 «В РАБОТЕ» СТАВИЛИ ТРИ РАЗА ЗА МЕСЯЦ (замер 19.08: 3 перевода против 142 закрытий,
    # последний 07.08). Состояние существовало и было мертво: ставящий не получал НИЧЕГО,
    # а коллеги всё равно не видели, кто чем занят. Владелец назвал класс 19.08 08:30 UTC:
    # роль работает час, никто об этом не знает, и её будят второй раз или берут её же задачу.
    # ⇒ Отдельная команда с ЯВНЫМ СРОКОМ и рассказом, что делаешь. Гаснет сама, как
    # объявление о правке инструмента: забыть снять не страшно, вечный захват — страшно.
    pw = sub.add_parser("claim", help="объявить, что берёшь карточку в работу (видно коллегам)")
    dryrun.add_argument(pw)
    pw.add_argument("id", type=int)
    pw.add_argument("--actor", required=True)
    pw.add_argument("--minutes", type=int, default=None,
                    help="на сколько берёшь (по умолчанию: карточка пула 60 мин — П②, "
                         "прочие 2 ч)")
    pw.add_argument("--note", default="", help="что именно делаешь — это увидят коллеги")
    pw.add_argument("--release", action="store_true", help="снять объявление досрочно")
    pw.add_argument("--off-pool", dest="off_pool", default=None,
                    help="причина взятия карточки ВНЕ направления контура (карточка #399): "
                         "непустая, ложится событием в журнал карточки. Слово владельца "
                         "и срочная починка инструмента — законные причины")

    pc = sub.add_parser("comment")
    dryrun.add_argument(pc)
    pc.add_argument("id", type=int)
    pc.add_argument("--actor", required=True)
    pc.add_argument("--body", default="")
    pc.add_argument("--body-file", dest="body_file")

    a = p.parse_args()
    # R15a: от расположения скрипта, не от CWD · #391: характер вызова назван списком выше
    a.db = str(resolve_db(a.db, __file__, readonly=(a.cmd in READ_CMDS)))
    # ⚠️ getattr, а не a.dry_run: у читающих подкоманд флага НЕТ по замыслу —
    # ставить его туда, где нечего сохранять, значит учить, что он бывает бесполезен.
    conn = _conn(a.db, getattr(a, "dry_run", False))
    {"add": cmd_add, "list": cmd_list, "show": cmd_show,
     "status": cmd_status, "comment": cmd_comment, "criterion": cmd_criterion,
     "claim": cmd_claim}[a.cmd](conn, a)
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
