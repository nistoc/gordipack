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

📌 Читать так:
    role-rights.py list                      всё живое, по ролям
    role-rights.py list --role PROTO         только своё
    role-rights.py list --all                вместе с потраченным и отозванным
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
DEFAULT_DB = str(Path(__file__).resolve().parent.parent / "mezosync.db")

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
    if not a.why:
        sys.exit("⛔ отзыв без причины — это пропажа. Нужен --why: отозванное право спрашивают "
                 "именно тогда, когда что-то пошло не так.")
    conn = connect(a.db)
    n = conn.execute("UPDATE role_rights SET revoked_at = datetime('now'), revoked_why = ? "
                     "WHERE id=? AND revoked_at IS NULL", (a.why, a.id)).rowcount
    conn.commit()
    conn.close()
    print(f"✅ право #{a.id} отозвано" if n else f"⚠️ право #{a.id} не найдено или уже отозвано")
    return 0 if n else 1



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
    r.add_argument("--why")
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

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
