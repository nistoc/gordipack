# -*- coding: utf-8 -*-
"""signal-templates — ПЕЧАТАЕТ ГОТОВЫЙ СИГНАЛ СОСЕДНЕЙ РОЛИ (вариант В1 «только сигнал»).

СЛОВО ВЛАДЕЛЬЦА 2026-09-05 17:54 UTC, дословно: «#548 - принима выбор "В1. ТОЛЬКО СИГНАЛ".
Релизовываем его.» Карточка #564 (подзадача исследования #548).

ЧТО ЭТО. Сосед получает в свою сессию ОДНУ строку: от кого · что случилось · где лежит тело ·
куда отвечать. Доставка — секунды против медианы ленты около часа, и она НЕ рвёт чужой ход:
сообщение ложится в очередь занятой роли и вычитывается на ближайшем возврате инструмента.

⛔ СИГНАЛ — НЕ НОСИТЕЛЬ. Тело всегда в ленте. Правило свода signal-not-carrier; довод —
не вкус, а замер карточки #548: тела, ушедшие мимо ленты, не видит НИ ОДНА проверка контура,
у отправки нет признака недоставки, и общий след перестаёт быть общим.

🌉 УСЛОВИЕ РЕДАКЦИИ 2 (слово владельца 2026-09-06 05:38 UTC, карточка #570), дословно:
«ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ; ПОЯВИТСЯ ОБЩЕЕ МЕСТО — ПОЕДЕТ ЗВОНОК.» Оно объясняет
ОБА случая одним доводом, а не заводит исключение:
    внутри контура ...... общая лента ЕСТЬ ⇒ короткий сигнал, тело в ленте. Ничего не меняется
    мост к соседнему ... общей ленты НЕТ ФИЗИЧЕСКИ: у соседа нет доступа к нашей базе, у нас
    контуру              к их. Строка «в ленте записка #N» указала бы туда, куда получатель
                         заглянуть НЕ МОЖЕТ. Там тело едет ЦЕЛИКОМ, и это НЕ нарушение
⛔ Встречное ограничение: ВНУТРИ контура тело в сообщении — по-прежнему нарушение. Печатник
держит это построением: --body-file для роли своего контура он отклоняет.

⛔ ЭТОТ ИНСТРУМЕНТ НИЧЕГО НЕ ОТПРАВЛЯЕТ И НЕ МОЖЕТ. Средство отправки доступно только самой
роли; скрипт печатает ГОТОВЫЙ ВЫЗОВ, роль зовёт его своей рукой. Это не обходится и обходить
не надо: у отправки нет признака недоставки, и подпись под ней должна стоять живая.

ЗАГОТОВКИ ЖИВУТ ЗДЕСЬ, В КОДЕ, а не в таблице (выбор (в), карточка #548, комментарий 13:37 UTC).
Довод: заготовка — это ФОРМА ВЫЗОВА, а не данные; она версионируется вместе с кодом и правится
под объявлением о правке. Единственная существующая таблица заготовок хранит архетипы ролей
(ключ «вид роли», тело «промпт запуска») — строка-сигнал там читалась бы как архетип.

ДЕВЯТЬ ПОЛЕЙ И ИХ ИСТОЧНИКИ (все проверены рукой TAXO, приёмка карточки #548 14:13 UTC):
    {from} ......... кто шлёт — из --role, НЕ впечатано (заготовка с зашитым именем соврёт
                     у любой другой роли, и соврёт правдоподобно)
    {role} ......... кому — из --to
    {session} ...... адрес доставки — role_sessions.address, с часом записи
    {last_note} .... номер записки — из --note либо последняя записка отправителя к адресату
    {card} ......... номер карточки — из --card
    {deadline} ..... 🔴 срок взятия карточки НЕ УГАДЫВАЕТСЯ. Взятие — это событие карточки,
                     а срок лежит в его тексте ПРОЗОЙ. Печатник говорит «срок взятия
                     не разобран, смотри карточку» и не притворяется, что знает
    {lease} ........ номер объявления о правке — tool_leases, последнее незакрытое у адресата
    {lease_until} .. срок этого объявления — tool_leases.until_utc
    {sent_at} ...... час печати — ЗАПРОСОМ к системе (UTC), не из базы и не из подсказки среды

⚖️ ЧЕГО ИНСТРУМЕНТ НЕ ДЕЛАЕТ: не решает, стоит ли слать; не шлёт повторно; не заменяет
эскалацию владельцу (правило ack-deadline: при молчании дольше срока идут к владельцу,
а не шлют второй сигнал).
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import os
import pathlib
import re
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mezo_paths  # noqa: E402
import mezo_sessions  # noqa: E402 — сверка адреса/session_id с хранилищем сессий приложения (карточка #649)

# ⏰ Сколько адрес считается годным. Он умирает вместе с чатом, а строка о нём переживает чат
# и выглядит свежей — поэтому старый адрес печатник называет старым ВСЛУХ и печатать
# отказывается. Сутки — не догадка: чаты контура живут от нескольких часов до нескольких суток,
# и адрес суточной давности чаще жив, чем нет; двухсуточный — чаще мёртв.
VALID_HOURS = 24

# 🔴 АДРЕС БЕЗ РАЗЛИЧИТЕЛЯ В СКОБКАХ УКАЗЫВАЕТ НА НЕСКОЛЬКО РАЗГОВОРОВ СРАЗУ.
# Находка COORD при первом же взгляде на перечень сессий (05.09 18:15 UTC): имя «atlas-17»
# носят ДВА живых разговора — его и чужой. Промах молчалив: сигнал «успешно отправится»
# не туда, и признака недоставки у отправки нет. ⇒ короткое имя не принимаем вовсе.
DISTINGUISHER = __import__("re").compile(r"\[[0-9a-f]{6,}\]\s*$")

TEMPLATES = {
    "записка": {
        "срочность": "низкая",
        "текст": ("{from} → {role}: в ленте записка #{last_note} к тебе. Тело — только в ленте, "
                  "читай лентой, не этим сообщением. Отвечать — в ленту."),
        "когда": "положил записку и она не терпит до ближайшей сверки соседа",
        "повтор": "не повторять: записка никуда не денется, сосед дочитает лентой",
    },
    "приёмка": {
        "срочность": "средняя",
        "текст": ("{from} → {role}: карточка #{card} сдана на приёмку, приёмщик — ты или любая "
                  "рука, кроме моей. Вызовы и критерий — в карточке. Сдано {sent_at} UTC. "
                  "Отвечать — в ленту или комментарием на карточке."),
        "когда": "работа сдана и стои́т, пока её никто не принял",
        "повтор": "не раньше чем через час",
    },
    "держишь": {
        "срочность": "высокая",
        # 🔴 СОБИРАЕТСЯ ИЗ ТОГО, ЧТО ЕСТЬ ЗА АДРЕСАТОМ, а не из всех полей подряд.
        # Оплачено на первом же прогоне 05.09: заготовка со всеми полями напечатала роли
        # «ТЫ держишь карточку #561» — карточку держала ДРУГАЯ роль, а рядом стояло
        # «объявление о правке #— (до — UTC)». Самый срочный сигнал уверенно утверждал
        # неправду, и предупреждение рядом её не отменяло: адресат читает ТЕКСТ, а не
        # вывод печатника. ⇒ упоминается только то, что за адресатом ДЕЙСТВИТЕЛЬНО числится.
        "текст": "{from} → {role}: ТЫ держишь {что}; {from} ждёт. Продли вслух или сними. Отвечать — в ленту.",
        "когда": "чужое взятие или объявление о правке держит твою работу",
        "повтор": ("НЕ ПОВТОРЯТЬ. При молчании дольше срока — к владельцу по правилу "
                   "ack-deadline, а не второй сигнал"),
    },
}

DEFAULT_KIND = "записка"


def query_time() -> str:
    """Час печати — ЗАПРОСОМ к системе в UTC. Подсказки среды местные и без зоны:
    роль, взявшая такую подсказку под буквами UTC, соврёт на величину смещения (оплачено 05.09)."""
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def open_db(path: str | None):
    """Соединение и ПУТЬ к базе. Путь возвращается не для красоты: от него ищется контейнер
    контура, а в нём — каталоги обмена с соседями (см. каталоги_обмена ниже)."""
    db = path or str(mezo_paths.live_db(__file__))
    if not os.path.isfile(db):
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: базы нет: {db}")
    return sqlite3.connect(db), db


def get_address(conn, role: str):
    """Адрес доставки, стойкий session_id (если записан) и час записи. None, если роли
    в реестре нет. session_id может отсутствовать — колонка добавлена шагом
    20260913-role-sessions-session-id.py позже самой таблицы, и не у каждой роли он есть."""
    try:
        r = conn.execute(
            "SELECT address, noted_at, noted_by, source, session_id FROM role_sessions "
            "WHERE role = ?", (role,)).fetchone()
    except sqlite3.OperationalError:
        # ⚖️ копия старше шага 20260913: колонки session_id ещё нет — работаем как раньше
        r = conn.execute("SELECT address, noted_at, noted_by, source FROM role_sessions "
                         "WHERE role = ?", (role,)).fetchone()
        return None if r is None else {"address": r[0], "noted_at": r[1], "noted_by": r[2],
                                        "source": r[3], "session_id": None}
    return None if r is None else {"address": r[0], "noted_at": r[1], "noted_by": r[2],
                                    "source": r[3], "session_id": r[4]}


def age_hours(timestamp: str) -> float | None:
    try:
        t = dt.datetime.strptime(timestamp[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    except (ValueError, TypeError):
        return None
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds() / 3600


def last_note_of(conn, from_role: str, to_role: str):
    """Последняя записка отправителя, числящаяся ЭТОЙ роли полем адресата, и предупреждение.

    🔴 ПОЧЕМУ ВОЗВРАЩАЕТСЯ ЕЩЁ И ПРЕДУПРЕЖДЕНИЕ (находка COORD, приёмка 05.09 18:15 UTC).
    Роль часто называет адресатов В ШАПКЕ текста, а полями передаёт меньше: замер COORD
    по 69 запискам — у 29 (42 %) учтено меньше названного, потеряно 167 адресатов.
    Печатник тогда честно берёт СТАРУЮ записку, числящуюся адресату, и показывает соседу
    номер недельной давности вместо свежего. Молча — а сигнал тем и силён, что ему верят.
    ⇒ если у отправителя есть записка НОВЕЕ найденной, об этом говорится вслух."""
    r = conn.execute(
        "SELECT m.id FROM messages m JOIN message_addressee a ON a.message_id = m.id "
        "WHERE m.writer_role = ? AND upper(a.role) = ? ORDER BY m.id DESC LIMIT 1",
        (from_role, to_role)).fetchone()
    latest = conn.execute("SELECT id FROM messages WHERE writer_role = ? ORDER BY id DESC LIMIT 1",
                          (from_role,)).fetchone()
    if r:
        warning = None
        if latest and latest[0] > r[0]:
            warning = (f"у тебя есть записка #{latest[0]} НОВЕЕ, но она не числится {to_role} "
                       f"полем адресата — в сигнал пошла #{r[0]}. Если хотел сигналить о свежей, "
                       f"проверь, кому она адресована ПОЛЯМИ, а не только в шапке текста")
        return r[0], warning
    if latest:
        return latest[0], (f"ни одна твоя записка не числится {to_role} полем адресата — взята "
                           f"последняя вообще, #{latest[0]}. Проверь, тому ли сигналишь")
    return None, None


def current_lease(conn, role: str):
    """Последнее ЖИВОЕ объявление о правке у роли: незакрытое И НЕ ИСТЁКШЕЕ.

    У таблицы нет столбца «держатель» — есть «роль» (находка TAXO, приёмка #548):
    держателем считается тот, на кого объявление взято.

    🔴 «НЕ ИСТЁКШЕЕ» — НЕ ПРИДИРКА, оплачено на втором прогоне 05.09. Объявление гаснет
    САМО по сроку (так и написано в его собственном выводе: «забыть снять не страшно»),
    поэтому непроставленная отметка снятия НЕ значит «держит». Первый вариант печатника
    взял вчерашнее объявление и напечатал роли «ТЫ держишь …#145 (до 2026-09-04 17:40 UTC)» —
    сутками позже. Срочный сигнал о том, чего давно нет, дороже молчания: по нему бросают
    работу и идут разбираться."""
    r = conn.execute(
        "SELECT id, until_utc FROM tool_leases WHERE role = ? AND released_at IS NULL "
        "AND datetime(until_utc) > datetime('now') ORDER BY id DESC LIMIT 1", (role,)).fetchone()
    return None if r is None else {"id": r[0], "until": r[1]}


def claim_info(conn, card: int):
    """Кто держит карточку и что сказано про срок.

    🔴 СРОК НЕ УГАДЫВАЕТСЯ. Таблицы взятий не существует: взятие — это СОБЫТИЕ карточки,
    а срок лежит в тексте события прозой («до 2026-09-05 12:13:00 UTC», «на два часа»,
    «до конца отрезка»). Разбирать прозу образцом значит однажды напечатать в САМОЙ СРОЧНОЙ
    заготовке уверенный неверный срок — и получить спор о часе вместо работы.
    Поэтому: держателя берём, срок — только если он записан машинной формой, иначе говорим,
    что не разобрали (находка TAXO, приёмка карточки #548 14:13 UTC)."""
    # Последнее событие взятия ИЛИ снятия: если свежее — снятие, карточку никто не держит.
    r = conn.execute(
        "SELECT event_type, actor_role, body_md, at FROM backlog_events "
        "WHERE backlog_id = ? AND event_type IN ('claim', 'claim_release') "
        "ORDER BY id DESC LIMIT 1", (card,)).fetchone()
    if r is None or r[0] == 'claim_release':
        return None
    holder, claim_text, when = r[1], r[2] or "", r[3]
    m = re.search(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)\s*UTC", claim_text)
    deadline_text = f"взятие до {m.group(1)} UTC" if m else "срок взятия не разобран, смотри карточку"
    expired = False
    if m:
        r2 = conn.execute("SELECT datetime(?) < datetime('now')",
                          (m.group(1).replace("T", " "),)).fetchone()
        expired = bool(r2 and r2[0])
    # ⚖️ Истёкшее взятие в сигнал ВХОДИТ — оно и есть повод звать («продли вслух или сними»),
    # в отличие от истёкшего объявления о правке, которое гаснет само и не держит ничего.
    return {"держатель": holder, "срок": deadline_text, "когда": when, "истёк": expired}


# ═══ 🌉 ГРАНИЦА КОНТУРА: КОМУ КОРОТКИЙ СИГНАЛ, А КОМУ ПИСЬМО ЦЕЛИКОМ ═══════════════════
# Врезано 2026-09-06 по редакции 2 правила signal-not-carrier (слово владельца 05:38 UTC),
# карточка #570. До этой правки печатник знал только про короткий сигнал и об условии
# молчал — то есть на мосту с соседним контуром предписывал неисполнимое.
#
# 🔴 ПОЧЕМУ ГРАНИЦА ВЫЧИСЛЯЕТСЯ, А НЕ ВПЕЧАТАНА ПЕРЕЧНЕМ ИМЁН. Тот же довод, что и у поля
# {from}: впечатанный перечень соврёт ПРАВДОПОДОБНО. Состав ролей контура живой — роли
# рождаются, засыпают и закрываются; соседи заводятся словом владельца. Перечень, верный
# сегодня, завтра назовёт нового соседа своей ролью и напечатает ему номер записки, которую
# он не откроет, — молча и уверенно, а признака недоставки у отправки нет.
#
# ДВА ЖИВЫХ ИСТОЧНИКА:
#   свои ... таблица ролей базы координации — перечень контура (кто в нём есть вообще).
#   чужие .. таблица связей с соседями (кто сосед и где его база) ОБЪЕДИНЁННО с каталогами
#            обмена на диске (куда кладут файлы). Объединение, а не пересечение: связь без
#            каталога и каталог без связи одинаково означают «сосед есть». Требовать обоих
#            записей значило бы молча считать соседа своим, пока кто-то не завёл вторую.
# ⚖️ ЦЕНА ОШИБКИ РАЗНАЯ В ДВЕ СТОРОНЫ, и обе молчаливы — поэтому имя, значащееся сразу
# и ролью, и соседним контуром, печатник не берёт вовсе, а отказывается вслух.


def our_group(conn):
    """Имя СВОЕГО контура — из базы, а не впечатанное: этот же код живёт у соседей,
    и впечатанное «atlas» назвало бы там своих чужими."""
    try:
        r = conn.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
        if r and (r[0] or "").strip():
            return r[0].strip().lower()
        # запасной путь: имя, ОТ которого заведены связи с соседями
        r = conn.execute("SELECT source_group FROM cross_links GROUP BY source_group "
                         "ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
        return r[0].strip().lower() if r and r[0] else None
    except sqlite3.Error:
        return None


def group_roles(conn):
    """Перечень ролей своего контура. Таблицы нет — ПУСТОЙ ответ, а не догадка: тогда
    печатник ведёт себя как прежде и никого не объявляет чужим по умолчанию."""
    try:
        return {(r[0] or "").upper() for r in conn.execute("SELECT role FROM roles")}
    except sqlite3.Error:
        return set()


def exchange_dirs(our, db_path):
    """{имя соседа: каталог обмена} — найденное НА ДИСКЕ: <контейнер>/*/.mezosync/bridges/<наш>-<сосед>.

    Имя соседа берётся из ИМЕНИ КАТАЛОГА (вторая половина пары), а не из перечня: каталог
    заводится тем же ходом, что и сам мост, и потому не отстаёт от правды.
    ⛔ ГРАНИЦА НАЗВАНА ПРЯМО: контейнер отсюда виден не всегда — печатника зовут и из копии
    (например, приёмкой). Тогда ответ ПУСТОЙ, и различение держится на второй опоре, на
    записи связи в базе. Ошибка поиска каталога не вправе уронить печатника: у отказа
    в этом месте цена выше, чем у молчания о пути.
    """
    if not our:
        return {}
    roots = []
    try:
        roots.append(mezo_paths.container_root(__file__))
    except SystemExit:
        pass                      # запущен из копии вне контейнера — каталогов отсюда не видно
    except Exception:             # noqa: BLE001 — см. границу в справке выше
        pass
    p = pathlib.Path(db_path).resolve()
    if p.parent.name == ".mezosync":
        roots.append(p.parent.parent)
    found = {}
    for root in roots:
        try:
            for entry in pathlib.Path(root).glob("*/.mezosync/bridges/*"):
                name = entry.name.lower()
                if entry.is_dir() and name.startswith(our + "-"):
                    found.setdefault(name[len(our) + 1:], entry)
        except OSError:
            continue
    return found


def neighbor_groups(conn, our, db_path):
    """{имя соседа: чем опознан и куда ему писать}. Объединение двух живых источников."""
    neighbors = {}
    try:
        rows = conn.execute("SELECT target_group FROM cross_links "
                              "WHERE lower(source_group) = ?", (our or "",)).fetchall()
    except sqlite3.Error:
        rows = []
    for (name,) in rows:
        if name and name.strip():
            entry2 = neighbors.setdefault(name.strip().lower(), {"откуда": [], "каталог": None})
            entry2["откуда"].append("связь с этим соседом записана в базе координации")
    for name, path in exchange_dirs(our, db_path).items():
        entry2 = neighbors.setdefault(name, {"откуда": [], "каталог": None})
        entry2["каталог"] = path
        entry2["откуда"].append(f"на диске есть каталог обмена: {path}")
    return neighbors


def letter_to_neighbor(from_role, our, name, info, body, card, at_time) -> int:
    """Заготовка ПИСЬМА за пределы контура: тело едет целиком, и условие названо словами.

    ⚖️ Печатник и здесь ничего не пишет и не отправляет — он печатает форму, а файл кладёт
    роль своей рукой. Довод тот же, что у короткого сигнала: у отправки нет признака
    недоставки, и подпись под письмом соседу должна стоять живая.
    """
    exchange_dir = info.get("каталог")
    print("=" * 78)
    print(f"ПИСЬМО СОСЕДНЕМУ КОНТУРУ «{name}» · {at_time} UTC")
    print("=" * 78)
    print("🌉 ЗДЕСЬ ТЕЛО ЕДЕТ ЦЕЛИКОМ, И ЭТО НЕ НАРУШЕНИЕ. Условие правила signal-not-carrier")
    print("   (редакция 2, слово владельца 2026-09-06 05:38 UTC), дословно:")
    print("       «ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ; ПОЯВИТСЯ ОБЩЕЕ МЕСТО — ПОЕДЕТ ЗВОНОК.»")
    print(f"   ПОЧЕМУ так, а не поблажка: общей ленты с контуром «{name}» нет ФИЗИЧЕСКИ — у него")
    print("   нет доступа к нашей базе, у нас к его. Короткая строка «в ленте записка #N»")
    print("   указала бы туда, куда получатель заглянуть НЕ МОЖЕТ: номер есть, тела нет.")
    print("⛔ ВСТРЕЧНОЕ ОГРАНИЧЕНИЕ, чтобы условие не растянули: ВНУТРИ контура тело")
    print("   в сообщении — по-прежнему нарушение обеими сторонами. Условие снимает запрет")
    print("   ровно там, где общего места нет, и нигде больше.")
    print("")
    print("КАК РАЗЛИЧЕНО — признак выведен из живых данных, впечатанного перечня имён нет:")
    print(f"   · имя «{name.upper()}» не значится ролью нашего контура (перечень ролей — в базе)")
    for reason in info.get("откуда", []):
        print(f"   · {reason}")
    print("   Ошибись признак — цена РАЗНАЯ, и обе стороны ошибки молчаливы: чужой, названный")
    print("   своим, получит номер записки, которую не откроет; свой, названный чужим,")
    print("   получит тело мимо ленты — а это уже нарушение правила.")
    print("")
    if exchange_dir is None:
        print("⚠️ КАТАЛОГ ОБМЕНА ОТСЮДА НЕ ВИДЕН, и выдумывать путь печатник не станет: письмо,")
        print("   положенное не туда, сосед не найдёт, а признака этого ни у кого не будет.")
        print(f"   👉 путь смотри в договоре моста с «{name}» (README каталога обмена).")
        destination = f"<каталог обмена с «{name}»>"
    else:
        destination = str(exchange_dir)
    print("👉 ПОЛОЖИ ФАЙЛ СВОЕЙ РУКОЙ — печатник ничего не пишет и не отправляет:")
    print(f"   {destination}{os.sep}ask.{name}.<тема>.md")
    print("")
    print("   ─────────── содержимое файла ───────────")
    print(f"   {at_time} UTC · @{from_role}, контур {our or '<наш контур>'} → соседям {name}")
    print("")
    print("   # <тема одной строкой>")
    print("")
    if body is None:
        print("   <ТЕЛО ЦЕЛИКОМ: разбор, замер, решение, вопрос по существу. Написано так,")
        print("    чтобы читалось БЕЗ нашей ленты и БЕЗ наших карточек: их сосед открыть")
        print("    не может. Готовое тело подставляется сюда вызовом --body-file <файл>.>")
    else:
        for line in (body.rstrip().splitlines() or [""]):
            print(f"   {line}")
    print("")
    print(f"   Ответ ждём файлом в вашей исходящей: answer.{our or '<наш контур>'}.<та же тема>.md")
    print("   ─────────── конец файла ───────────")
    print("")
    print("⚖️ ИМЯ ФАЙЛА НЕСЁТ НАЗНАЧЕНИЕ: ask.<кому>.<тема> — вопрос · answer.<кому>.<тема> —")
    print("   ответ · status.<тема> — состояние работы, которую ждут с той стороны. ВТОРОЕ")
    print("   слово — КОМУ файл адресован, поэтому у вопроса и ответа оно разное; совпадать")
    print("   обязана ТЕМА — по ней обе стороны и связывают вопрос с ответом. Форму сверь")
    print("   с договором моста: у разных мостов она своя.")
    print("⛔ ВИДЫ КОРОТКОГО СИГНАЛА (записка · приёмка · держишь) ЧЕРЕЗ МОСТ НЕ ЕДУТ, и это")
    print("   не запрет ради запрета: все три указывают на то, чего у соседа нет, — на нашу")
    print("   ленту, нашу карточку, наше объявление о правке.")
    if card:
        print(f"⚠️ НОМЕР КАРТОЧКИ #{card} В ПИСЬМО НЕ ВСТАВЛЕН: карточка живёт в нашей базе,")
        print("   и по номеру сосед её не откроет. Нужное из неё перескажи телом письма.")
    print("📌 СЛЕД У СЕБЯ ОСТАВЬ ВСЁ РАВНО: положи в ленту записку «ушло файлом <имя файла>,")
    print("   тема такая-то». Довод против переноса тела — «второй источник распоряжений,")
    print("   которого не видит никто, кроме двоих» — на мосту НЕ снят, он там просто")
    print("   неисполним; записка в ленте возвращает контуру то, что мост отнять не может.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Печатает готовый сигнал соседней РОЛИ — или, если адресат за пределами контура, заготовку письма соседнему контуру с телом целиком. НЕ отправляет и не пишет файлов: зовёт и кладёт роль своей рукой.")
    ap.add_argument("--role", help="ТВОЯ роль (отправитель), ВЕРХНИЙ регистр")
    ap.add_argument("--to", help="кому: роль своего контура (ВЕРХНИЙ регистр) ЛИБО имя соседнего контура. Что из двух — печатник выводит из живых данных: перечень ролей в базе и каталоги обмена с соседями")
    ap.add_argument("--kind", choices=sorted(TEMPLATES), default=DEFAULT_KIND,
                    help="вид сигнала: записка · приёмка · держишь")
    ap.add_argument("--note", type=int, help="номер записки (иначе — последняя твоя к адресату)")
    ap.add_argument("--card", type=int, help="номер карточки")
    ap.add_argument("--body-file",
                    help="файл с телом письма. ТОЛЬКО для адресата ЗА пределами контура "
                         "(соседний контур): там общей ленты нет, и тело едет целиком. "
                         "Для роли своего контура тело пишется запиской в ленту, и такой "
                         "вызов печатник отклоняет")
    ap.add_argument("--set-address", help="записать адрес сессии для --role (свой, своей рукой)")
    ap.add_argument("--session-id", dest="session_id",
                    help="СТОЙКИЙ идентификатор сессии («local_…», карточка A/AIA): переживает "
                         "возобновление чата, в отличие от --set-address. Валидатор адреса "
                         "(различитель в скобках) на него не распространяется — форма другая. "
                         "Можно вместе с --set-address или отдельно, если у роли УЖЕ есть строка")
    ap.add_argument("--source", choices=["self", "listing", "owner"], default="self",
                    help="ЧЕМ добыт адрес: self — роль назвала свой сама (надёжно) · "
                         "listing — взят из перечня сессий чужой рукой (роль не подтверждала) · "
                         "owner — сказан владельцем")
    ap.add_argument("--list", action="store_true", help="показать реестр адресов с их возрастом")
    ap.add_argument("--db")
    a = ap.parse_args()

    conn, db_path = open_db(a.db)
    if "role_sessions" not in {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}:
        sys.exit("⛔ НЕ ЗАПУСТИЛСЯ: реестра адресов в базе нет. Сначала шаг схемы "
                 "20260905-role-sessions.py")

    if a.list:
        try:
            rows = conn.execute(
                "SELECT role, address, noted_at, noted_by, source, session_id, transcript_id "
                "FROM role_sessions ORDER BY role").fetchall()
        except sqlite3.OperationalError:
            try:
                # копия старше шага 20260924 — колонки transcript_id ещё нет
                rows = [(*r, None) for r in conn.execute(
                    "SELECT role, address, noted_at, noted_by, source, session_id "
                    "FROM role_sessions ORDER BY role").fetchall()]
            except sqlite3.OperationalError:
                # копия старше шага 20260913 — колонки session_id тоже ещё нет
                rows = [(*r, None, None) for r in conn.execute(
                    "SELECT role, address, noted_at, noted_by, source FROM role_sessions "
                    "ORDER BY role").fetchall()]
        if not rows:
            print("Реестр ПУСТ. Свой адрес каждая роль записывает сама:")
            print('   имя [различитель] — строка «This session is …» из ListAgents; '
                  'session_id — get_session("self") → sessionId:')
            print('   signal-templates.py --role <СВОЯ> --set-address "<имя [различитель]>" '
                  '--session-id "<sessionId>"')
            return 0
        print(f"РЕЕСТР АДРЕСОВ — {len(rows)} · короткий адрес годен {VALID_HOURS} ч с часа записи")
        for role, addr, when, actor, src, sid, tid in rows:
            age = age_hours(when)
            # 🔴 ЗДЕСЬ БЫЛ «✅» — И ОН ЧИТАЛСЯ КАК «ЖИВ». Инструмент не видит перечень живых
            # сессий этой машины: он умеет сказать только «моложе {ГОДЕН_ЧАСОВ} ч» либо
            # «старше». ✅ в словаре контура значит «сделано/верно», и рядом с адресом роль
            # читает его как «сессия жива, шли смело» — а живость тут НЕ ПРОВЕРЕНА никем.
            label = ("⚪ живость не проверялась" if age is not None and age < VALID_HOURS
                     else "⌛ СТАР" if age is not None else "⚪ возраст неизвестен")
            print(f"   {label:<26} {role:<8} {addr:<28} "
                  f"{('sid: ' + sid) if sid else '(session_id не записан)':<28} "
                  f"{('tid: ' + tid) if tid else '(transcript_id не записан)':<28} "
                  f"записан {when} UTC ({'?' if age is None else f'{age:.1f} ч назад'}) "
                  f"рукой {actor}, путь {src}")
        print("⚖️ Адрес умирает вместе с чатом роли. Старый печатник не подставляет — говорит вслух.")
        print(f"⚪ ГРАНИЦА, НАЗВАННАЯ ВСЛУХ: «моложе {VALID_HOURS} ч» ≠ «жива», и «нет в перечне "
              f"живых сессий на этой машине» ≠ «мертва» — инструмент такого перечня не видит "
              f"вовсе. Живость подтверждает только сама роль (или её сосед, получив ответ).")
        print("⚠️ Столбец «рукой» и путь «self» — это то, ЧТО СКАЗАЛ вызывающий, а не")
        print("   доказательство. Инструмент не видит, чья рука его позвала.")
        return 0

    if a.set_address or a.session_id:
        if not a.role:
            sys.exit("⛔ --set-address/--session-id без --role: чей это адрес — неизвестно")
        role = a.role.upper()
        if a.set_address and not DISTINGUISHER.search(a.set_address.strip()):
            print(f"⛔ АДРЕС БЕЗ РАЗЛИЧИТЕЛЯ В СКОБКАХ: «{a.set_address.strip()}»")
            print(f"   Одно имя носят НЕСКОЛЬКО разговоров — короткий адрес указывает на них")
            print(f"   на все сразу, и промах молчалив: отправка скажет «успешно» и уедет")
            print(f"   не туда. Полную форму «имя [различитель]» даёт строка «This session is …» "
                  f"из ListAgents (точный вызов, не перечень наугад).")
            return 2
        # ⚖️ session_id — ДРУГОЙ признак, форма другая («local_…», не «имя [код]»): различитель
        # в скобках к нему не применим. Единственная защита — непустота: пустая строка
        # выглядела бы записанным идентификатором, не будучи им.
        if a.session_id is not None and not a.session_id.strip():
            print("⛔ --session-id ПУСТ: пустая строка выглядела бы записанным идентификатором,")
            print("   не будучи им. Назови настоящий (mcp__ccd_session_mgmt__get_session(\"self\")).")
            return 2
        # ⚖️ Рука пишущего и путь добычи — РАЗНЫЕ вещи. Роль может записать адрес соседа,
        # увидев его в перечне сессий; тогда сосед этого адреса не подтверждал, и путь честно
        # зовётся «listing». Молчаливо выдать такую запись за «сосед назвал сам» значило бы
        # сделать реестр правдоподобнее, чем он есть.
        # 🔴 ЧЬЯ ЭТО РУКА, ИНСТРУМЕНТ ЗНАТЬ НЕ МОЖЕТ, и это сказано вслух ниже.
        # Оплачено 05.09: владелец записал адрес роли из своего окна, а реестр напечатал
        # «рукой STUD, путь self» — то есть выдал ЧУЖУЮ запись за подтверждение самой ролью.
        # ⚡ КЛАСС: поле, которое не может быть неверным по построению, ничего не сообщает —
        # а выглядит доказательством. Здесь «self» значит РОВНО «так сказал вызывающий».
        actor = os.environ.get("MEZO_ROLE", "").upper() or role
        # ⚖️ has_transcript_id — есть ли у ЭТОЙ базы шаг 20260924-role-sessions-transcript-id.py.
        # Копия без него по-прежнему обязана писать адрес/session_id как раньше — новый столбец
        # только ДОБАВЛЯЕТСЯ к записи, его отсутствие не вправе остановить старый путь.
        has_transcript_id = True
        try:
            previous = conn.execute(
                "SELECT address, session_id, noted_at, noted_by, source, note, transcript_id "
                "FROM role_sessions WHERE role = ?", (role,)).fetchone()
        except sqlite3.OperationalError:
            has_transcript_id = False
            try:
                previous = conn.execute(
                    "SELECT address, session_id, noted_at, noted_by, source, note "
                    "FROM role_sessions WHERE role = ?", (role,)).fetchone()
                if previous is not None:
                    previous = (*previous, None)   # transcript_id ещё не заведён — колонки нет
            except sqlite3.OperationalError:
                sys.exit("⛔ НЕ ЗАПУСТИЛСЯ: колонки session_id в базе нет — сначала шаг схемы "
                         "20260913-role-sessions-session-id.py")
        if previous is None and not a.set_address:
            print(f"⛔ У РОЛИ {role} В РЕЕСТРЕ ЕЩЁ НЕТ СТРОКИ — записать ТОЛЬКО session_id "
                  f"некуда: адрес обязателен при ПЕРВОЙ записи (--set-address, столбец address "
                  f"NOT NULL). session_id пишется тем же вызовом или отдельным следующим.")
            print(f'   Пример: signal-templates.py --role {role} --set-address "<адрес>" '
                  f'--session-id "local_…"')
            return 2
        new_address = a.set_address.strip() if a.set_address else previous[0]
        new_sid = a.session_id.strip() if a.session_id is not None else (previous[1] if previous else None)
        new_tid = previous[6] if previous else None   # переносится, пока сверка не даст своего

        # ═══ 🌉 СВЕРКА С ХРАНИЛИЩЕМ СЕССИЙ ПРИЛОЖЕНИЯ (карточка #649) ═══════════════════
        # До этой правки валидатор проверял только ФОРМУ адреса (различитель в скобках) —
        # живую ли сессию он называет, не проверял никто. Два пути, оба обязаны сойтись
        # с хранилищем (mezo_sessions.py):
        #   есть --session-id .... сверяется САМ session_id: архивный/неизвестный — отказ
        #                          с перечнем живых сессий контура; найден и жив —
        #                          transcript_id заполняется САМ, из хранилища, не вводом
        #   только --set-address . сверяется ИМЯ (часть адреса до « [») с заголовками живых
        #                          сессий контура: ровно одно совпадение — её session_id и
        #                          transcript_id берутся сами; иначе — отказ с перечнем
        # Хранилища НЕТ (машина без него, песочница, снятая переменная) — запись ВСЁ РАВНО
        # проходит: отсутствие проверяющего инструмента не повод отказать в старом пути
        # (запись со слов роли, без проверки), просто об этом сказано вслух.
        our_cwd = None
        try:
            our_cwd = str(mezo_paths.container_root(__file__))
        except SystemExit:
            our_cwd = None      # каталог контура отсюда не виден — сверка по cwd невозможна

        store = mezo_sessions.read_store()
        if not store.found:
            print(f"⚠️ СВЕРИТЬ НЕЧЕМ: {store.error} — адрес записан без проверки")
        else:
            name_part = (a.set_address.strip().split(" [", 1)[0] if a.set_address
                        else (previous[0].split(" [", 1)[0] if previous and previous[0] else None))
            if a.session_id is not None:
                sid_clean = a.session_id.strip()
                record = mezo_sessions.find_by_session_id(store, sid_clean)
                if record is None or record.archived:
                    why = "В АРХИВЕ" if record is not None else "НЕ НАЙДЕН"
                    print(f"⛔ SESSION_ID «{sid_clean}» {why} В ХРАНИЛИЩЕ СЕССИЙ ПРИЛОЖЕНИЯ.")
                    if our_cwd is None:
                        print("   каталог контура отсюда не виден — перечень живых сессий той "
                              "же рабочей директории напечатать нечем.")
                    else:
                        live = mezo_sessions.live_sessions_for_cwd(store, our_cwd)
                        if live:
                            print(f"   живые (не архивные) сессии с тем же рабочим каталогом "
                                  f"({our_cwd}):")
                            for r in live:
                                print(f"      session_id {r.session_id} · «{r.title}»")
                        else:
                            print(f"   живых сессий с тем же рабочим каталогом ({our_cwd}) "
                                  f"не найдено")
                    return 2
                if name_part is not None and (record.title or "") != name_part:
                    print(f"⛔ ИМЯ АДРЕСА «{name_part}» НЕ СОВПАДАЕТ С ЗАГОЛОВКОМ ЭТОЙ СЕССИИ: "
                          f"«{record.title}»")
                    print("   заголовок чата — это и есть имя в адресе; печатник не пишет "
                          "строку, расходящуюся с тем, что видно в приложении.")
                    return 2
                new_tid = record.transcript_id
            elif a.set_address:
                if our_cwd is None:
                    print("⚠️ СВЕРИТЬ ИМЯ НЕЧЕМ: каталог контура отсюда не виден — запись "
                          "проходит без сверки с хранилищем сессий приложения.")
                else:
                    live = mezo_sessions.live_sessions_for_cwd(store, our_cwd)
                    matches = [r for r in live if (r.title or "") == name_part]
                    if len(matches) == 1:
                        new_sid = matches[0].session_id
                        new_tid = matches[0].transcript_id
                    else:
                        verdict = "НЕ НАЙДЕНО СРЕДИ" if not matches else "НЕОДНОЗНАЧНО СРЕДИ"
                        print(f"⛔ ИМЯ «{name_part}» {verdict} живых сессий с рабочим "
                              f"каталогом {our_cwd}:")
                        for r in live:
                            print(f"      session_id {r.session_id} · «{r.title}»")
                        if not live:
                            print("      (живых сессий с этим рабочим каталогом не найдено)")
                        return 2
        # ═══ конец сверки ═══════════════════════════════════════════════════════════════

        conn.execute("BEGIN")
        # ⚡ ПЕРЕЗАПИСЬ ПЕЧАТАЕТ, ЧТО БЫЛО — читая прежнюю строку В ТОЙ ЖЕ транзакции, что и
        # запись новой, и откладывая её в role_sessions_history: адрес умирает вместе с чатом,
        # и молчаливая перезапись стёрла бы единственный след того, каким он был.
        if previous is not None:
            if has_transcript_id:
                conn.execute(
                    "INSERT INTO role_sessions_history (role, address, session_id, noted_at, "
                    "noted_by, source, note, transcript_id, superseded_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (role, previous[0], previous[1], previous[2], previous[3], previous[4],
                     previous[5], previous[6], actor))
            else:
                conn.execute(
                    "INSERT INTO role_sessions_history (role, address, session_id, noted_at, "
                    "noted_by, source, note, superseded_by) VALUES (?,?,?,?,?,?,?,?)",
                    (role, previous[0], previous[1], previous[2], previous[3], previous[4],
                     previous[5], actor))
        if has_transcript_id:
            conn.execute(
                "INSERT INTO role_sessions (role, address, session_id, noted_at, noted_by, "
                "source, transcript_id) VALUES (?, ?, ?, datetime('now'), ?, ?, ?) "
                "ON CONFLICT(role) DO UPDATE SET address = excluded.address, "
                "session_id = excluded.session_id, noted_at = datetime('now'), "
                "noted_by = excluded.noted_by, source = excluded.source, "
                "transcript_id = excluded.transcript_id",
                (role, new_address, new_sid, actor, a.source, new_tid))
        else:
            conn.execute(
                "INSERT INTO role_sessions (role, address, session_id, noted_at, noted_by, source) "
                "VALUES (?, ?, ?, datetime('now'), ?, ?) "
                "ON CONFLICT(role) DO UPDATE SET address = excluded.address, "
                "session_id = excluded.session_id, noted_at = datetime('now'), "
                "noted_by = excluded.noted_by, source = excluded.source",
                (role, new_address, new_sid, actor, a.source))
        conn.commit()
        if previous is not None:
            before_text = f"session_id {previous[1]}" if previous[1] else previous[0]
            print(f"🔁 ПЕРЕЗАПИСАН: было {before_text} · {previous[2]} UTC · путь {previous[4]} · "
                  f"записал {previous[3]} (прежняя строка сохранена в role_sessions_history)")
        print(f"✅ роль {role}: адрес {new_address}"
              + (f" · session_id {new_sid}" if new_sid else "")
              + (f" · transcript_id {new_tid}" if new_tid else "") + f" (путь «{a.source}»)")
        print(f"   короткий адрес годен {VALID_HOURS} ч — потом печатник попросит подтвердить, "
              f"что чат тот же")
        if new_sid:
            print(f"   session_id ПЕРЕЖИВАЕТ возобновление чата — подтверждать заново не нужно")
        if new_tid:
            print(f"   transcript_id ЗАПОЛНЕН СВЕРКОЙ с хранилищем сессий приложения — им хук "
                  f"опознаёт роль по записи разговора")
        if a.source != "self":
            print(f"   ⚠️ путь «{a.source}»: сама роль {role} этого адреса НЕ подтверждала — "
                  f"если сигнал не дойдёт, признака недоставки не будет")
        elif not os.environ.get("MEZO_ROLE"):
            print(f"   ⚠️ путь «self» здесь значит РОВНО «так сказал вызывающий»: чья это рука,")
            print(f"      инструмент проверить не может. Если адрес записывала не сама {role} —")
            print(f"      попроси её подтвердить своим вызовом, иначе запись выглядит надёжнее,")
            print(f"      чем есть.")
        return 0

    if not a.role or not a.to:
        sys.exit("⛔ нужны --role (твоя) и --to (адресат). Виды: " + " · ".join(sorted(TEMPLATES)))
    from_role, to_role = a.role.upper(), a.to.upper()
    if from_role == to_role:
        sys.exit("⛔ сигнал самому себе — не сигнал")

    # ── 🌉 ГДЕ АДРЕСАТ: внутри контура или за его пределами (редакция 2 правила) ──
    our = our_group(conn)
    own_roles = group_roles(conn)
    neighbor = neighbor_groups(conn, our, db_path).get(to_role.lower())
    if to_role in own_roles and neighbor is not None:
        print(f"⛔ ИМЯ «{to_role}» ЗНАЧИТСЯ СРАЗУ И РОЛЬЮ НАШЕГО КОНТУРА, И СОСЕДНИМ КОНТУРОМ.")
        print("   Печатник не выбирает за роль, потому что цена ошибки в две стороны разная")
        print("   и обе молчаливы: сочтя чужого своим, ты пошлёшь номер записки, которую он")
        print("   не откроет; сочтя своего чужим — повезёшь ему тело мимо ленты, а внутри")
        print("   контура это нарушение правила signal-not-carrier обеими сторонами.")
        print("   👉 разведи имена: либо роль в перечне контура, либо связь с соседом.")
        return 2

    body = None
    if a.body_file:
        try:
            body = pathlib.Path(a.body_file).read_text(encoding="utf-8")
        except OSError as e:
            print(f"⛔ ФАЙЛ С ТЕЛОМ НЕ ПРОЧИТАН: {a.body_file}")
            print(f"   {e}")
            print("   Письма с пустым телом печатник не печатает: сосед получил бы заголовок")
            print("   без содержимого и потратил ход на переспрос.")
            return 2
        if not body.strip():
            print(f"⛔ ФАЙЛ С ТЕЛОМ ПУСТ: {a.body_file}. Письмо без тела — это переспрос.")
            return 2

    if neighbor is not None:
        return letter_to_neighbor(from_role, our, to_role.lower(), neighbor, body, a.card, query_time())

    # ⛔ ДАЛЬШЕ — АДРЕСАТ ВНУТРИ КОНТУРА. Общая лента ЕСТЬ, значит условие редакции 2
    # здесь НЕ применимо, и о нём не говорится ни слова: правило, названное там, где оно
    # не действует, читается как разрешение. Всё поведение ниже — прежнее.
    if a.body_file:
        print("⛔ ТЕЛО В СООБЩЕНИИ АДРЕСАТУ ВНУТРИ КОНТУРА — ПО-ПРЕЖНЕМУ НАРУШЕНИЕ.")
        print(f"   С ролью {to_role} общая лента ЕСТЬ: положи тело запиской, а сюда позови без")
        print("   --body-file. Условие «тело едет там, где общего места нет» снимает запрет")
        print("   ровно на мосту с соседним контуром — и нигде больше.")
        print("   ПОЧЕМУ это не придирка (замер карточки #548): тело, ушедшее мимо ленты, не")
        print("   видит ни одна проверка контура; у отправки нет признака недоставки; у")
        print("   сообщения нет ни номера, ни поля адресата — на него нельзя сослаться,")
        print("   его нельзя подтвердить прочтением и нельзя найти через сутки.")
        if to_role not in own_roles:
            print(f"   ⚠️ имя {to_role} не значится НИ ролью контура, НИ соседним контуром.")
            print("      Печатник считает такое имя своим намеренно: ошибка в эту сторону")
            print("      громкая и поправимая, а обратная тихо разрешила бы нарушение.")
            print("      Если это правда сосед — заведи связь с ним или каталог обмена.")
        return 2

    target = get_address(conn, to_role)
    if target is None:
        print(f"⛔ АДРЕСА РОЛИ {to_role} В РЕЕСТРЕ НЕТ — печатать нечего.")
        print(f"   Адрес своей сессии знает ТОЛЬКО она сама, и угадать его нельзя: он")
        print(f"   закрепляется при рождении чата и не выводится из имени роли.")
        print(f"   👉 попроси {to_role} в ленте записать его: signal-templates.py --role {to_role} "
              f'--set-address "<её адрес>"')
        return 2
    age = age_hours(target["noted_at"])
    if age is not None and age >= VALID_HOURS:
        print(f"⌛ АДРЕС РОЛИ {to_role} СТАР: записан {target['noted_at']} UTC, {age:.1f} ч назад.")
        print(f"   Адрес умирает вместе с чатом, а строка о нём — нет. Отправив по старому,")
        print(f"   ты получишь «успешно отправлено» и никакой доставки: признака недоставки")
        print(f"   у отправки НЕТ (замер карточки #548).")
        print(f"   👉 попроси {to_role} обновить адрес в ленте — или запиши сам, если видишь")
        print(f"      её строку «This session is …» в ListAgents: signal-templates.py "
              f"--role {to_role} --set-address \"…\"")
        return 2

    template = TEMPLATES[a.kind]
    fields = {
        "from": from_role,
        "role": to_role,
        "session": target["address"],
        "sent_at": query_time(),
        "last_note": a.note,
        "card": a.card if a.card else "—",
        "deadline": "срок взятия не разобран, смотри карточку",
        "lease": "—",
        "lease_until": "—",
    }
    warnings = []
    if not a.note:
        fields["last_note"], warning = last_note_of(conn, from_role, to_role)
        if warning:
            warnings.append(warning)
    if a.kind == "записка" and not fields["last_note"]:
        print(f"⛔ НЕЧЕГО СИГНАЛИТЬ: у роли {from_role} нет ни одной записки в ленте. Сигнал о записке "
              f"без записки — это сигнал о пустоте.")
        return 2
    if a.kind in ("приёмка", "держишь") and not a.card:
        print(f"⛔ вид «{a.kind}» без --card: карточка не названа, а сигнал именно про неё")
        return 2
    if a.kind == "держишь":
        parts = []
        lease = current_lease(conn, to_role)
        if lease:
            fields["lease"], fields["lease_until"] = lease["id"], lease["until"]
            parts.append(f"объявление о правке #{lease['id']} (до {lease['until']} UTC)")
        claim = claim_info(conn, a.card)
        if claim and claim["держатель"] and claim["держатель"].upper() == to_role:
            fields["deadline"] = claim["срок"]
            tail_note = " — СРОК УЖЕ ПРОШЁЛ" if claim.get("истёк") else ""
            parts.append(f"карточку #{a.card} ({claim['срок']}{tail_note})")
        elif claim and claim["держатель"]:
            warnings.append(
                f"карточку #{a.card} по последнему взятию держит {claim['держатель']}, а не {to_role} — "
                f"в текст сигнала она НЕ ВОШЛА: адресат прочтёт текст, а не это предупреждение")
        else:
            warnings.append(f"взятия карточки #{a.card} в базе нет — в текст она не вошла")
        if not parts:
            print(f"⛔ ЗА РОЛЬЮ {to_role} НИЧЕГО НЕ ЧИСЛИТСЯ: ни незакрытого объявления о правке, "
                  f"ни взятия карточки #{a.card} за ней.")
            print(f"   Сигнал «ты держишь чужую работу» тут был бы неправдой, и неправдой")
            print(f"   в САМОЙ СРОЧНОЙ заготовке — той, по которой роль бросает свою работу.")
            for warn in warnings:
                print(f"   ⚠️ {warn}")
            return 2
        fields["что"] = " и ".join(parts)

    text = template["текст"].format(**fields)
    print("=" * 78)
    print(f"СИГНАЛ «{a.kind}» · срочность {template['срочность']} · {fields['sent_at']} UTC")
    print("=" * 78)
    for warn in warnings:
        print(f"⚠️ {warn}")
    print("👉 ПОЗОВИ СВОЕЙ РУКОЙ (инструмент отправки скрипту недоступен):")
    print()
    # ⚡ ПОРЯДОК ФОРМ: СНАЧАЛА ПО ИДЕНТИФИКАТОРУ, ПОТОМ ПО ИМЕНИ. session_id переживает
    # возобновление чата, короткий адрес — нет; печатник ведёт к более стойкому пути первым,
    # но не отбирает второй — записи session_id может ещё не быть.
    if target.get("session_id"):
        print(f'   mcp__ccd_session_mgmt__send_message(session_id="{target["session_id"]}", '
              f'message="{text}")')
        print(f"      ⚖️ по идентификатору сессии — переживает возобновление чата")
        print()
        print(f'   ЛИБО по имени (живёт ДО возобновления): '
              f'SendMessage(to="{target["address"]}", message="{text}")')
    else:
        print(f'   SendMessage(to="{target["address"]}", message="{text}")')
        print(f"      ⚖️ по имени — живёт ДО возобновления чата; session_id у {to_role} ещё не "
              f"записан (--session-id), стойкой формы пока нет")
    print()
    print(f"   адрес записан {target['noted_at']} UTC"
          + (f" ({age:.1f} ч назад)" if age is not None else "") + f", путь «{target['source']}»")
    print(f"⚖️ СИГНАЛ — НЕ НОСИТЕЛЬ: тело лежит в ленте, ответ ждём В ЛЕНТЕ, не сообщением.")
    print(f"   когда слать: {template['когда']}")
    print(f"   повтор: {template['повтор']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
