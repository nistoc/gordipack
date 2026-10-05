#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРАВА РОЛИ: выдать · посмотреть · потратить · отозвать.

Слово владельца 2026-08-08 22:33 UTC: «Сделать права роли полями, как у правил: что разрешено,
кто разрешил, когда, разовое или стоячее».

⛔ ОТКАЗ, А НЕ ВОРЧАНИЕ. Право без «кто разрешил · когда · где сказано» не сохраняется вовсе.
Необязательное поле у нас умирало ЧЕТЫРЕ раза подряд (--task 0 из 1724 · parent_id 0 из 84 ·
«какой запиской» 0 из 9 · гашение срочности 1 из 546). Пятого захода не будет.

⚡ РАЗОВОЕ ПРАВО ТРАТИТСЯ И ЭТО ВИДНО: `spend`. Разовое разрешение без следа расхода —
это стоячее разрешение, которым пользуются, пока не постесняются.

⚡ ОШИБКА В ЗАПИСИ ЧИНИТСЯ `amend`, А НЕ «ОТОЗВАТЬ И ВЫДАТЬ ЗАНОВО» (с 2026-08-30):
правятся только поля-СВИДЕТЕЛЬСТВА (когда · где сказано · примечание), действие права
не трогается. Отзыв ради опрятности записал бы в историю прерывание, которого не было.

⚡ КООРДИНАТОР КОНТУРА — ПОМЕТКА В ТАБЛИЦЕ РОЛЕЙ (с 2026-10-05, карточка #677, этап Э3;
решение владельца В3 а′, чат COORD 2026-10-05 10:53 UTC). Кто в этом контуре координатор,
берётся ИЗ ДАННЫХ: слово «координатор» в причине живой роли (roles.lifecycle_reason), поиск —
общая функция mezo_paths.find_coordinator. Имя роли в код не вписано: у другого контура
координатор называется иначе или не назван вовсе. Чужое право отзывает только он; пока он не
определён (никто не помечен или помечено несколько), чужое право не отзывает НИКТО.
Поставить или перенести пометку — подкоманда `coordinator` (одна команда, одна транзакция).

📌 Читать так:
    role-rights.py list                      всё живое, по ролям
    role-rights.py list --role PROTO         только своё
    role-rights.py list --all                вместе с потраченным и отозванным
    role-rights.py coordinator               кто сейчас помечен координатором
    role-rights.py coordinator --help        как назначить (по слову владельца)
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — координатора ищет ОДНА общая функция, своей копии поиска здесь нет

DEFAULT_DB = str(Path(__file__).resolve().parent.parent / "mezosync.db")
# Путь этого файла для примера в справке: ВЫВОДИТСЯ от расположения файла, не вписан в код.
SELF_PATH = Path(__file__).resolve().as_posix()

# Текст пометки, которую получает назначенная роль. Прежний текст причины остаётся ПОСЛЕ неё.
COORDINATOR_MARK = "координатор контура (назначен {hour} UTC рукой {actor})"
# 🪤 ЛОВУШКА КОРНЯ. Текст, которым заменяется снятая пометка, НЕ ДОЛЖЕН содержать корень
# «координатор»: поиск идёт по подстроке без учёта регистра, и «бывший координатор» пометку
# НЕ снимает — прежняя роль осталась бы найденной, и координаторов вышло бы двое. Образец
# безопасного текста — тот же приём, что у COORD_MARK_REMOVED в bite-pool-brief.py.
FORMER_MARK = "прежняя ведущая роль контура; пометка снята {hour} UTC"

MISSING = {
    "authorized_by": "КТО разрешил (owner · coord · имя роли)",
    # ⚰️ ЗДЕСЬ СТОЯЛ ЧАС «2026-08-08 15:56 UTC» — ОБРАЗЦОМ, ДВАЖДЫ. Такого часа НЕ БЫЛО:
    # перемерен пятью независимыми руками 2026-08-30 по записям разговоров (PROTO, RCC,
    # CORE, CHROME, COORD) — разрешений на отправку четыре, первое 11:22:40, последнее
    # и самое полное 15:58:46. 🎯 Образец с НАСТОЯЩИМ часом опаснее выдуманного вдвойне:
    # роль копирует то, что читает, и час расползается дальше. Поэтому здесь его нет вовсе.
    "granted_at": "КОГДА сказано (ГГГГ-ММ-ДД или ГГГГ-ММ-ДД ЧЧ:ММ UTC) — час бери "
                  "ИЗ ЗАПИСИ РАЗГОВОРА, не из памяти о нём",
    "source_ref": "ГДЕ сказано («чат <РОЛЬ> ГГГГ-ММ-ДД ЧЧ:ММ UTC» · «записка #N»)",
}


def connect(db):
    if not Path(db).exists():
        sys.exit(f"⛔ базы нет: {db}")
    return sqlite3.connect(db, timeout=10)


def coordinator_state_words(lookup) -> str:
    """Что нашёл поиск координатора — словами. Для отказа при отзыве и для показа пометки.

    Три разных беды названы РАЗНЫМИ словами (класс «одно ничего на две беды»): «никто не
    помечен», «помечено несколько» и «таблицу ролей не прочитать» читаются по-разному.
    """
    if lookup.error:
        return f"таблицу ролей прочитать не удалось ({lookup.error})"
    if not lookup.found:
        return "ни у одной живой роли в причине нет слова «координатор»"
    if len(lookup.found) == 1:
        return f"координатор — {lookup.found[0]}"
    return "слово «координатор» стоит у нескольких живых ролей: " + ", ".join(lookup.found)


def cmd_grant(a):
    miss = [f"  --{k.replace('_', '-')}    {v}" for k, v in MISSING.items() if not getattr(a, k)]
    if miss:
        print(f"⛔ ПРАВО «{a.right}» НЕ ЗАПИСАНО: право без источника — это слух.\n")
        print("  Не хватает:")
        print("\n".join(miss))
        print("\n  ⚠️ Задним числом по памяти НЕ восстанавливай: источник, вспомненный спустя")
        print("     время, выглядит доказательством, не будучи им. Не помнишь — так и напиши")
        print("     («source_ref: источник неизвестен»): это честный факт, и он тоже читается.")
        return 2
    conn = connect(a.db)
    dup = conn.execute(
        "SELECT id, kind FROM role_rights_live WHERE role=? AND right_key=? "
        "AND COALESCE(scope,'') = COALESCE(?,'')",
        (a.role.upper(), a.right, a.scope)).fetchone()
    if dup and not a.force:
        conn.close()
        print(f"⚠️ У роли {a.role.upper()} УЖЕ ЕСТЬ живое право «{a.right}»"
              f"{' в области ' + a.scope if a.scope else ''} — запись #{dup[0]} ({dup[1]}).")
        print("   Второе такое же право не усилит первое, а раздвоит ответ на вопрос «а можно ли».")
        print("   Если это НОВОЕ слово владельца поверх старого — повтори с --force.")
        return 1
    conn.execute(
        "INSERT INTO role_rights (role, right_key, scope, kind, authorized_by, granted_at, "
        "source_ref, declared_by, note) VALUES (?,?,?,?,?,?,?,?,?)",
        (a.role.upper(), a.right, a.scope, a.kind, a.authorized_by, a.granted_at,
         a.source_ref, a.declared_by, a.note))
    conn.commit()
    conn.close()
    print(f"✅ {a.role.upper()} · {a.right}"
          f"{' · область ' + a.scope if a.scope else ' · область НЕ НАЗВАНА'} · "
          f"{'СТОЯЧЕЕ' if a.kind == 'standing' else 'РАЗОВОЕ'} · разрешил {a.authorized_by} "
          f"{a.granted_at}")
    if not a.scope:
        print("   ⚠️ Область не названа. Право без области расползается — сегодня этот класс "
              "поймали трижды на разных правилах.")
    return 0


def cmd_spend(a):
    conn = connect(a.db)
    row = conn.execute("SELECT id, kind, spent_at FROM role_rights WHERE id=?", (a.id,)).fetchone()
    if not row:
        conn.close()
        sys.exit(f"⛔ права #{a.id} нет")
    if row[1] != "once":
        conn.close()
        sys.exit(f"⛔ право #{a.id} СТОЯЧЕЕ — его нельзя потратить. Тратятся только разовые.")
    if row[2]:
        conn.close()
        sys.exit(f"⛔ право #{a.id} УЖЕ потрачено {row[2]} — второй раз им пользоваться нельзя.")
    conn.execute("UPDATE role_rights SET spent_at = datetime('now'), "
                 "note = COALESCE(note || ' | ', '') || ? WHERE id=?", (a.on or "", a.id))
    conn.commit()
    conn.close()
    print(f"✅ право #{a.id} ПОТРАЧЕНО. Больше оно не действует — и это видно запросом, "
          "а не по памяти.")
    return 0


def cmd_revoke(a):
    """Отозвать право — только роль-владелец записи либо координатор контура ЯВНО (--foreign).

    ⚡ ГРАНИЦА ЗАВЕДЕНА 2026-09-13 (найдено контуром AIA, подтверждено в нашем коде):
    ДО этой правки отозвать чужое право могла ЛЮБАЯ роль, назвав чужой --id, — отзыв не
    проверял ни владельца записи, ни чью руку он несёт. Тот же класс, что у amend: правка
    (здесь — отзыв) без руки неотличима от того, что её не было вовсе. `--by` обязателен
    ТОЙ ЖЕ фразой отказа, что у amend — довод один и тот же для обеих подкоманд.

    ⚡ КООРДИНАТОР — ИЗ ДАННЫХ (2026-10-05, карточка #677, этап Э3). Прежде имя координатора
    было вписано в код, и у контура с другим именем координатора чужое право не отзывал бы
    никто. Теперь координатор — тот, кого называет таблица ролей (см. подкоманду
    `coordinator`). Не определён (никто или несколько) — чужое право НЕ отзывается вовсе.
    """
    if not a.why:
        sys.exit("⛔ отзыв без причины — это пропажа. Нужен --why: отозванное право спрашивают "
                 "именно тогда, когда что-то пошло не так.")
    if not a.by:
        sys.exit("⛔ нужен --by: кто правит. Правка без руки неотличима от того, что запись "
                 "всегда была такой.")
    conn = connect(a.db)
    row = conn.execute("SELECT role, revoked_at FROM role_rights WHERE id=?", (a.id,)).fetchone()
    if not row:
        conn.close()
        sys.exit(f"⛔ права #{a.id} нет. Ничего не изменено.")
    owner_role, revoked_at = row
    by = a.by.upper()
    # ⛔ ОТЗЫВАТЬ ВПРАВЕ РОЛЬ-ВЛАДЕЛЕЦ ЗАПИСИ ЛИБО КООРДИНАТОР КОНТУРА ЯВНО (--foreign).
    # Владелец («ALL» включительно — общее право тоже не гасит первая попавшаяся роль)
    # отзывает СВОЁ без вопросов; координатор — чужое, но только назвав это явно, а не
    # молча по факту его роли: молчаливое право гасить что угодно — ровно та дыра, которую
    # находка AIA и назвала.
    if owner_role.upper() != by:
        coordinator = mezo_paths.find_coordinator(conn)
        if coordinator.name is None:
            conn.close()
            sys.exit(f"⛔ ОТКАЗ: право #{a.id} принадлежит роли {owner_role}, а отозвать "
                     f"просит {by}. Координатор контура не определён: "
                     f"{coordinator_state_words(coordinator)}. Пока он не определён, чужое "
                     f"право не отзывается вовсе — его отзывает только роль-владелец записи. "
                     f"Посмотреть пометку: подкоманда coordinator без флагов.")
        if by != coordinator.name:
            conn.close()
            sys.exit(f"⛔ ОТКАЗ: право #{a.id} принадлежит роли {owner_role}, а отозвать "
                     f"просит {by}. Отзывать вправе роль-владелец записи либо координатор "
                     f"контура ({coordinator.name}) ЯВНО (--foreign). Чужое право не гасят молча.")
        if not a.foreign:
            conn.close()
            sys.exit(f"⛔ ОТКАЗ: право #{a.id} принадлежит роли {owner_role}, не координатору. "
                     f"Координатор отзывает ЧУЖОЕ право только ЯВНО — с флагом --foreign. "
                     f"Без него отзыв неотличим от ошибки в --id.")
    n = conn.execute("UPDATE role_rights SET revoked_at = datetime('now'), revoked_why = ?, "
                     "revoked_by = ? WHERE id=? AND revoked_at IS NULL",
                     (a.why, by, a.id)).rowcount
    conn.commit()
    conn.close()
    print(f"✅ право #{a.id} отозвано ролью {by}" if n
          else f"⚠️ право #{a.id} не найдено или уже отозвано")
    return 0 if n else 1


def plan_coordinator(conn, role):
    """Что изменится при назначении роли координатором — БЕЗ записи.

    → (problem, plan). problem — слова отказа или None. plan — словарь: прежний текст причины
    роли, итог поиска ДО правки, список прочих помеченных ролей с их прежними текстами и
    признак «роль уже единственный координатор» (тогда менять нечего).
    """
    row = conn.execute("SELECT lifecycle, lifecycle_reason FROM roles WHERE role = ?",
                       (role,)).fetchone()
    if row is None:
        alive = [r[0] for r in conn.execute(
            "SELECT role FROM roles WHERE lifecycle = 'alive' ORDER BY role")]
        return (f"роли {role} в таблице ролей нет — пометку ставить некому. "
                f"Живые роли: {', '.join(alive) or 'нет ни одной'}.", None)
    if row[0] != "alive":
        return (f"роль {role} не живая (состояние: {row[0]}) — координатором может быть "
                f"только живая роль: поиск закрытых и спящих ролей не смотрит.", None)
    lookup = mezo_paths.find_coordinator(conn)
    if lookup.error:
        return (coordinator_state_words(lookup), None)
    others = []
    for name in lookup.found:
        if name != role:
            reason = conn.execute("SELECT lifecycle_reason FROM roles WHERE role = ?",
                                  (name,)).fetchone()[0]
            others.append((name, reason))
    return None, {"old_reason": row[1], "lookup": lookup, "others": others,
                  "already": lookup.found == [role]}


def coordinator_texts(plan, hour, actor):
    """Новые тексты причин: (текст назначенной роли, текст снятой пометки)."""
    mark = COORDINATOR_MARK.format(hour=hour, actor=actor)
    new_reason = mark
    if plan["old_reason"]:
        new_reason = f"{mark}; {plan['old_reason']}"
    return new_reason, FORMER_MARK.format(hour=hour)


def write_coordinator_audit(conn, actor, role, diff):
    """След назначения — в журнал изменений, ТЕМ ЖЕ видом записи, что у set-rule.py."""
    conn.execute("INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
                 (actor, "set_coordinator", role, diff))


def show_coordinator(conn):
    """Без флагов: кто сейчас помечен — словами (один · никто · несколько)."""
    try:
        lookup = mezo_paths.find_coordinator(conn)
    except Exception as e:  # noqa: BLE001 — показ не должен ронять трассировкой
        print(f"⛔ не удалось определить координатора: {e.__class__.__name__}")
        return 2
    if lookup.error:
        print(f"⛔ {coordinator_state_words(lookup)}. Пометку показать нечем.")
        return 2
    print("=" * 78)
    if lookup.name:
        reason = conn.execute("SELECT lifecycle_reason FROM roles WHERE role = ?",
                              (lookup.name,)).fetchone()[0]
        print(f"Координатор контура — {lookup.name}")
        print(f"   пометка в таблице ролей: «{reason}»")
    elif not lookup.found:
        print("Координатор контура НЕ НАЗНАЧЕН: " + coordinator_state_words(lookup) + ".")
        print("   Пока так, чужое право не отзывает никто — только роль-владелец записи.")
    else:
        print("Координатор контура НЕ ОПРЕДЕЛЁН: " + coordinator_state_words(lookup) + ".")
        print("   Пока так, чужое право не отзывает никто — только роль-владелец записи.")
    print("=" * 78)
    print("Назначить или перенести пометку (только по слову владельца): подкоманда "
          "coordinator с флагами --set · --actor · --word, подробности — coordinator --help.")
    return 0


def cmd_coordinator(a):
    """Показать пометку координатора или поставить её роли — одной транзакцией."""
    conn = connect(a.db)
    if a.set_role is None:
        if a.actor or a.word or a.apply:
            conn.close()
            sys.exit("⛔ --actor, --word и --apply имеют смысл только вместе с --set РОЛЬ. "
                     "Показать пометку — вызов без флагов.")
        code = show_coordinator(conn)
        conn.close()
        return code

    role = a.set_role.strip().upper()
    actor = (a.actor or "").strip()
    word = (a.word or "").strip()
    if not actor or not word:
        conn.close()
        sys.exit("⛔ ПОМЕТКА НЕ ПОСТАВЛЕНА: нужны оба — --actor (чья рука назначает) и --word "
                 "(слово владельца ДОСЛОВНО, с часом UTC и чатом). Назначение без источника — "
                 "слух; задним числом по памяти его не восстанавливают.")
    if actor.lower() != "owner":
        actor = actor.upper()

    # читаем и строим план (без записи — он нужен и пробному прогону, и записи)
    try:
        problem, plan = plan_coordinator(conn, role)
    except sqlite3.Error as e:
        conn.close()
        sys.exit(f"⛔ ПОМЕТКА НЕ ПОСТАВЛЕНА: таблицу ролей прочитать не удалось "
                 f"({e.__class__.__name__}: {e}).")
    if problem:
        conn.close()
        sys.exit(f"⛔ ПОМЕТКА НЕ ПОСТАВЛЕНА: {problem} Ничего не изменено.")
    if plan["already"]:
        conn.close()
        print(f"⚠️ {role} УЖЕ единственный координатор контура — НИЧЕГО НЕ ИЗМЕНЕНО.")
        print("   Следа в журнал не пишу: запись о перемене, которой не было, лжёт громче "
              "отсутствия записи.")
        return 1
    hour = conn.execute("SELECT strftime('%Y-%m-%d %H:%M', 'now')").fetchone()[0]
    new_reason, former_reason = coordinator_texts(plan, hour, actor)
    disclaimer = ("⚠️ Инструмент подлинность слова владельца НЕ проверяет: слово записывается "
                  "так, как его назвали. Сверять его с записью разговора — дело того, кто назначает.")

    if not a.apply:
        print("КООРДИНАТОР КОНТУРА — ПРОБНЫЙ ПРОГОН: ничего не записано")
        print(f"   сейчас: {coordinator_state_words(plan['lookup'])}")
        print(f"   станет: координатор — {role}")
        print(f"   {role}: «{plan['old_reason'] or '(пусто)'}» → «{new_reason}»")
        for name, reason in plan["others"]:
            print(f"   {name}: «{reason}» → «{former_reason}»  (пометка снята)")
        print(f"   слово владельца (со слов {actor}): «{word}»")
        print(f"   {disclaimer}")
        print("   👉 Записать: тот же вызов с флагом --apply.")
        conn.close()
        return 0

    # ═══ ЗАПИСЬ: одна транзакция, под замком записи с самого начала ═══
    conn.isolation_level = None  # BEGIN / COMMIT / ROLLBACK — руками, а не по умолчанию библиотеки

    def abort(message):
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        conn.close()
        sys.exit(message)

    try:
        conn.execute("BEGIN IMMEDIATE")
        # состояние перечитываем ПОД замком: пока шёл пробный разбор, база могла уйти вперёд
        problem, plan = plan_coordinator(conn, role)
        if problem:
            abort(f"⛔ ПОМЕТКА НЕ ПОСТАВЛЕНА: {problem} Ничего не изменено.")
        if plan["already"]:
            abort(f"⚠️ {role} УЖЕ единственный координатор контура — НИЧЕГО НЕ ИЗМЕНЕНО.")
        hour = conn.execute("SELECT strftime('%Y-%m-%d %H:%M', 'now')").fetchone()[0]
        new_reason, former_reason = coordinator_texts(plan, hour, actor)
        conn.execute("UPDATE roles SET lifecycle_reason = ? WHERE role = ?", (new_reason, role))
        for name, _ in plan["others"]:
            conn.execute("UPDATE roles SET lifecycle_reason = ? WHERE role = ?",
                         (former_reason, name))
        was = "\n".join([f"{role}: {plan['old_reason'] or '(пусто)'}"]
                        + [f"{n}: {r}" for n, r in plan["others"]])
        became = "\n".join([f"{role}: {new_reason}"]
                           + [f"{n}: {former_reason}" for n, _ in plan["others"]])
        diff = (f"координатор контура: {', '.join(plan['lookup'].found) or 'никто'} → {role}\n"
                f"час: {hour} UTC\nназначил: {actor}\n"
                f"слово владельца (записано как сказано, подлинность инструментом не "
                f"проверена): {word}\n\n--- БЫЛО ---\n{was}\n\n--- СТАЛО ---\n{became}")
        write_coordinator_audit(conn, actor, role, diff)
        # ⚖️ ПРОВЕРКА ПОСЛЕ ЗАПИСИ, ещё внутри транзакции: поиск обязан вернуть именно эту роль.
        # Без неё запись, после которой координатором оказался бы кто-то другой или никто
        # (роль закрыта, прежняя пометка не снялась), ушла бы в базу молча.
        after = mezo_paths.find_coordinator(conn)
        if after.name != role:
            abort(f"⛔ ПОМЕТКА НЕ ПОСТАВЛЕНА: после записи поиск координатора назвал не "
                  f"{role}: {coordinator_state_words(after)}. Всё записанное откатано, "
                  f"база не изменена.")
        conn.execute("COMMIT")
    except sqlite3.Error as e:
        abort(f"⛔ ПОМЕТКА НЕ ПОСТАВЛЕНА: сбой записи ({e.__class__.__name__}: {e}). "
              f"Всё записанное откатано, база не изменена.")
    conn.close()
    print(f"✅ КООРДИНАТОР КОНТУРА теперь — {role}")
    print(f"   {role}: причина «{new_reason}»")
    for name, _ in plan["others"]:
        print(f"   {name}: пометка снята, причина «{former_reason}»")
    print("   ⚖️ проверка после записи: поиск координатора вернул именно эту роль")
    print(f"   след записан в журнал изменений (audit_log): назначил {actor}")
    print(f"   {disclaimer}")
    return 0


def cmd_amend(a):
    """Исправить ФАКТИЧЕСКУЮ ОШИБКУ в записи права — не трогая его действия.

    ⚡ ЗАЧЕМ ЭТО ЗАВЕДЕНО (слово владельца 2026-08-30 23:25 UTC). До сегодня инструмент умел
    выдать · потратить · отозвать · показать — и НЕ УМЕЛ исправить ошибку в собственной
    записи. Замер 30.08: живая запись права на отправку несла час «08.08 15:56 UTC»,
    которого не существует, и печатала его КАЖДОЙ роли, спросившей «что мне разрешено».
    Обходной путь «отозвать и выдать заново» ЛОЖЕН: в истории появилось бы «право отозвано
    30.08», а оно не прерывалось — то есть ложное ОГРАНИЧЕНИЕ, которое исполнят не проверяя.
    ⇒ ошибка в реестре либо жила вечно, либо чинилась ценой искажения истории. Третьего пути
    инструмент не давал.

    ⛔ ГРАНИЦА, РАДИ КОТОРОЙ ЭТО ОТДЕЛЬНАЯ ПОДКОМАНДА, А НЕ ОБЩИЙ UPDATE: правятся ТОЛЬКО
    поля-СВИДЕТЕЛЬСТВА (когда сказано · где сказано · примечание). Поля ДЕЙСТВИЯ — кому,
    что, стоячее/разовое, кто разрешил, потрачено, отозвано — не трогаются ничем: их правка
    была бы не исправлением записи, а ПОДМЕНОЙ ПРАВА, и выглядела бы одинаково.
    """
    if not a.why:
        sys.exit("⛔ правка без причины — это подмена. Нужен --why: читающий обязан узнать, "
                 "ЧЕМ старое значение опровергнуто, иначе новое ничем не лучше старого.")
    if not a.by:
        sys.exit("⛔ нужен --by: кто правит. Правка без руки неотличима от того, что запись "
                 "всегда была такой.")
    if a.granted_at is None and a.source_ref is None and a.note_append is None:
        sys.exit("⛔ нечего исправлять: назови --granted-at и/или --source-ref "
                 "и/или --note-append.")
    conn = connect(a.db)
    row = conn.execute("SELECT id, role, right_key, granted_at, source_ref, note, "
                       "revoked_at, spent_at FROM role_rights WHERE id=?", (a.id,)).fetchone()
    if not row:
        conn.close()
        # ⛔ отсутствие записи — ОТКАЗ, а не тихий успех: «поправил» при нулевой правке
        # читается как сделанная работа (класс «одно ничего на две разные беды»).
        sys.exit(f"⛔ права #{a.id} нет. Ничего не изменено.")
    _, role, key, old_when, old_src, old_note, revoked, spent = row
    changes = []
    if a.granted_at is not None and a.granted_at != old_when:
        changes.append(("granted_at", old_when, a.granted_at))
    if a.source_ref is not None and a.source_ref != old_src:
        changes.append(("source_ref", old_src, a.source_ref))
    if not changes and a.note_append is None:
        conn.close()
        # ⚖️ ВСТРЕЧНЫЙ СЛУЧАЙ: новое значение равно старому. Молчать нельзя — роль решит,
        # что правка прошла; писать след нельзя — следа о несделанном не бывает.
        print(f"⚠️ запись #{a.id} ({role} · {key}) уже несёт эти значения — НИЧЕГО НЕ ИЗМЕНЕНО.")
        print("   Следа не пишу: запись о правке, которой не было, лжёт громче отсутствия правки.")
        return 1
    stamp = conn.execute("SELECT strftime('%Y-%m-%d %H:%M', 'now')").fetchone()[0]
    trail = "; ".join(f"{f}: «{o}» → «{n}»" for f, o, n in changes) or "примечание дополнено"
    mark = f"⚰️ ИСПРАВЛЕНО {stamp} UTC ({a.by.upper()}): {trail}. Почему: {a.why}"
    if a.note_append:
        mark += f" | {a.note_append}"
    sets, par = [], []
    for f, _, n in changes:
        sets.append(f"{f} = ?")
        par.append(n)
    sets.append("note = COALESCE(note || ' | ', '') || ?")
    par.append(mark)
    par.append(a.id)
    conn.execute(f"UPDATE role_rights SET {', '.join(sets)} WHERE id=?", par)
    conn.commit()
    after = conn.execute("SELECT granted_at, source_ref, revoked_at, spent_at "
                         "FROM role_rights WHERE id=?", (a.id,)).fetchone()
    conn.close()
    print(f"✅ запись #{a.id} ({role} · {key}) ИСПРАВЛЕНА — правка СВИДЕТЕЛЬСТВА, "
          "не действия права.")
    for f, o, n in changes:
        print(f"   {f}: «{o}» → «{n}»")
    print(f"   след записан в примечание: {mark[:96]}…" if len(mark) > 96
          else f"   след записан в примечание: {mark}")
    # ⚖️ доказательство ГРАНИЦЫ печатается САМО, а не обещается словами: читающий видит,
    # что действие права не сдвинулось ни в одну сторону.
    print(f"   ⚖️ действие НЕ тронуто: отозвано={after[2] or '—'} · потрачено={after[3] or '—'} "
          f"(было: отозвано={revoked or '—'} · потрачено={spent or '—'})")
    return 0


def cmd_list(a):
    conn = connect(a.db)
    src = "role_rights" if a.all else "role_rights_live"
    sql = f"SELECT id, role, right_key, scope, kind, authorized_by, granted_at, spent_at, " \
          f"revoked_at FROM {src}"
    par = ()
    if a.role:
        # ⚠️ ОБЩИЕ права (role='ALL') КАСАЮТСЯ спросившего. Фильтр «только своё имя» отвечал бы
        # «тебе ничего не разрешено» при живом стоячем разрешении на ВСЕХ — и роль отказалась бы
        # от разрешённого, будучи уверенной, что соблюдает правило. Замер 2026-08-09: у PROTO
        # своих живых прав 0, а касается его 1.
        sql += " WHERE role IN (?, 'ALL')"
        par = (a.role.upper(),)
    # ⛔ параметры ОБЯЗАНЫ уехать в execute вместе с текстом запроса: до 2026-08-09 они
    # собирались и терялись, и ЛЮБОЙ вызов с --role падал. Приёмка не ловила: она звала
    # только форму без роли.
    rows = conn.execute(sql + " ORDER BY role, right_key", par).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM role_rights").fetchone()[0]
    conn.close()
    # граница НАБОРА называется всегда: «прав нет» без указания, чьих, читается как «свод пуст»
    whose = f" РОЛИ {a.role.upper()} + ОБЩИЕ (ALL)" if a.role else " — ВСЕ РОЛИ"
    print("=" * 78)
    print("ПРАВА" + whose + (" · ВСЕ, включая потраченные и отозванные" if a.all else " · ЖИВЫЕ"))
    print("=" * 78)
    if not rows:
        if a.role and total:
            print(f"⚠️ У РОЛИ {a.role.upper()} НЕТ НИ ОДНОГО {'' if a.all else 'ЖИВОГО '}ПРАВА "
                  "— и общих (ALL) тоже нет.")
            print(f"   Это ответ про ЕЁ набор, а НЕ про свод: всего записей в таблице {total},")
            print("   у других ролей права есть. Весь свод — тем же вызовом без --role.")
        else:
            print("⚠️ ПУСТО. Это НЕ «прав нет» — это «поля ещё никто не заполнял»:")
            print(f"   всего записей в таблице {total}. Права по-прежнему живут прозой в памяти")
            print("   ролей, и запрос «что мне разрешено» отвечает молчанием, а не «ничего».")
        return 0
    for i, role, key, scope, kind, who, when, spent, revoked in rows:
        mark = "🔒СТОЯЧЕЕ" if kind == "standing" else "1️⃣РАЗОВОЕ"
        state = ""
        if revoked:
            state = f"  ⛔ отозвано {revoked[:16]}"
        elif spent:
            state = f"  ✔ потрачено {spent[:16]}"
        common = "🌐" if role == "ALL" else " "
        print(f"{common}#{i:<3} {role:8} {key:24} {mark}  {who:6} {when[:16]}"
              f"{'  · ' + scope if scope else '  · ОБЛАСТЬ НЕ НАЗВАНА'}{state}")
    live_n = len([r for r in rows if not r[7] and not r[8]])
    print()
    if a.role:
        # ⚠️ «живых N · своих M» врало бы, когда M считается по ВСЕМ показанным строкам,
        # а N — только по живым. Каждое число называет свой набор явно.
        own = len([r for r in rows if r[1] != "ALL"])
        print(f"показано {len(rows)} записей (живых {live_n}) · своих {own}, общих {len(rows) - own}"
              f" · в таблице всего {total} записей ПО ВСЕМ РОЛЯМ")
        print(f"🌐 — право выдано на ВСЕХ (role=ALL): касается {a.role.upper()}, "
              "хотя её имени в записи нет")
    else:
        print(f"живых {live_n} из {total} записей всего")
    return 0


COORDINATOR_HELP_EPILOG = f"""\
Как это работает:
  без флагов     показать, кто сейчас помечен координатором: слово «координатор» в причине
                 живой роли в таблице ролей (один · никто · несколько — три разных ответа)
  --set РОЛЬ     показать, что изменится. Ничего не пишет, пока нет --apply
  --apply        записать: РОЛЬ получает пометку (прежний текст причины остаётся после неё),
                 у всех прочих помеченных ролей пометка снимается — одной транзакцией;
                 след уходит в журнал изменений; после записи поиск координатора обязан
                 вернуть именно РОЛЬ, иначе всё откатывается

⚠️ Инструмент подлинность слова владельца НЕ проверяет: слово записывается так, как его
   назвали. Назначать — только по живому слову владельца, назвав его дословно.

Пример вызова:
  python {SELF_PATH} coordinator
  python {SELF_PATH} coordinator --set ИМЯ_РОЛИ --actor ИМЯ_РУКИ --word "слово владельца дословно, час UTC, чат"
  то же с --apply — запись
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="права роли полями: что · кто · когда · разовое/стоячее")
    ap.add_argument("--db", default=DEFAULT_DB)
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grant", help="выдать право")
    g.add_argument("--role", required=True)
    g.add_argument("--right", required=True, help="короткий ключ: push · service-start · migrate")
    g.add_argument("--scope", help="ОБЛАСТЬ: репозиторий, база, зона. Без неё право расползается")
    g.add_argument("--kind", choices=["standing", "once"], required=True)
    g.add_argument("--authorized-by", dest="authorized_by")
    g.add_argument("--granted-at", dest="granted_at")
    g.add_argument("--source-ref", dest="source_ref")
    g.add_argument("--declared-by", dest="declared_by", default="field",
                   choices=["field", "backfill"],
                   help="'backfill' — разобрано из прозы, а не сказано человеком. Смешивать нельзя")
    g.add_argument("--note")
    g.add_argument("--force", action="store_true")
    g.set_defaults(fn=cmd_grant)

    s = sub.add_parser("spend", help="потратить РАЗОВОЕ право")
    s.add_argument("--id", type=int, required=True)
    s.add_argument("--on", help="на что именно потрачено")
    s.set_defaults(fn=cmd_spend)

    r = sub.add_parser("revoke", help="отозвать право (не удалить)")
    r.add_argument("--id", type=int, required=True)
    r.add_argument("--by", help="КТО отзывает: роль-владелец записи либо координатор контура")
    r.add_argument("--why")
    r.add_argument("--foreign", action="store_true",
                   help="координатор отзывает ЧУЖОЕ право — явно, не молча по факту роли")
    r.set_defaults(fn=cmd_revoke)

    am = sub.add_parser("amend", help="исправить ФАКТИЧЕСКУЮ ошибку в записи "
                                      "(час · источник · примечание) — не трогая действие права")
    am.add_argument("--id", type=int, required=True)
    am.add_argument("--by", help="КТО правит: роль. Правка без руки неотличима от «так и было»")
    am.add_argument("--why", help="ЧЕМ старое значение опровергнуто (замер, запись разговора)")
    am.add_argument("--granted-at", dest="granted_at", help="верный час — из записи разговора")
    am.add_argument("--source-ref", dest="source_ref", help="верный источник")
    am.add_argument("--note-append", dest="note_append", help="дописать в примечание")
    am.set_defaults(fn=cmd_amend)

    l = sub.add_parser("list", help="показать права")
    l.add_argument("--role")
    l.add_argument("--all", action="store_true", help="вместе с потраченным и отозванным")
    l.set_defaults(fn=cmd_list)

    c = sub.add_parser(
        "coordinator", add_help=False, usage=argparse.SUPPRESS,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        help="показать пометку «координатор» или поставить её роли (по слову владельца)",
        description="КООРДИНАТОР КОНТУРА — пометка в таблице ролей: показать или назначить.",
        epilog=COORDINATOR_HELP_EPILOG)
    c.add_argument("-h", "--help", action="help", help="показать эту справку и выйти")
    c.add_argument("--set", dest="set_role", metavar="РОЛЬ",
                   help="кого назначить координатором (без --apply — только показать, что изменится)")
    c.add_argument("--actor", metavar="КТО",
                   help="чья рука назначает: имя роли (или owner). Обязателен вместе с --set")
    c.add_argument("--word", metavar="СЛОВО",
                   help="слово владельца ДОСЛОВНО, час UTC и чат. Обязателен вместе с --set")
    c.add_argument("--apply", action="store_true",
                   help="записать (без него ничего не пишется)")
    # заголовок группы флагов по-русски: по умолчанию библиотека печатает английское слово
    optionals = getattr(c, "_optionals", None)
    if optionals is not None:
        optionals.title = "флаги"
    c.set_defaults(fn=cmd_coordinator)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
