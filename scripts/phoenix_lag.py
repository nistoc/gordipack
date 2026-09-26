# -*- coding: utf-8 -*-
"""НА СКОЛЬКО ПАМЯТЬ РОЛИ ОТСТАЛА ОТ ЕЁ ЖЕ РАБОТЫ — одна функция для всех, кто об этом говорит.

Слово владельца 2026-09-26 10:45 UTC, чат PROTO (карточка #664): первый шаг к автосохранению
памяти — строка «память отстала» в советующем hook. Повод — письмо контура tapas 08:06 UTC
и замер 08.08: память ролей отставала от их работы на 3–20 часов, и ни одной команды
«сохранись» при этом не звучало. Течёт не на остановке — течёт между.

⚖️ ЧТО ИМЕННО МЕРИТСЯ — ОТСТАВАНИЕ ОТ РАБОТЫ, А НЕ ВОЗРАСТ СОХРАНЕНИЯ.
   отставание = последняя своя записка роли − последнее сохранение её раздела state.
   Возраст сохранения («state записан 20 ч назад») кричал бы и про спящую роль, у которой
   ничего не пропало: она не работала. Признак, который горит всегда, перестаёт значить
   что-либо. Здесь роль попадает в строку, только если ПОСЛЕ сохранения она работала
   дольше порога — то есть в базе нет того, что она за это время узнала.
   Записка, написанная в одном действии с сохранением (секунды спустя), отставанием
   не считается по построению: разница меньше порога.

⚖️ ПОЧЕМУ ПО РАЗДЕЛУ state (записка #5197, разбор OPSSRE — записка #5196): запись любого
   мелкого раздела глушила бы строку при устаревшем положении дел. Раздела state нет —
   меряем по самому свежему разделу и говорим это в строке.

🔴 ГРАНИЦА, НАЗВАННАЯ ВСЛУХ: работа видна только по запискам роли. Правки файлов, commit,
   прогоны без записки сюда не попадают — роль, работающая молча, отставания не покажет.
   И это СОВЕТ, а не принуждение: условие отмены правила phoenix-save-on-stop («сохранение
   стало свойством механизма») этим не выполняется.

⛔ Функция не пишет в базу и не бросает наружу: зовущий (hook при каждой реплике человека)
   не имеет права сломать ход из-за неё.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

LAG_HOURS = 3          # порог: тот же, что у совета в write-message.py («память не подтверждалась 3 ч»)


def _ts(text):
    return datetime.fromisoformat(str(text).replace("T", " ").replace(" UTC", "")[:19])


def _has(con, name) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())


def memory_lag(con, role: str):
    """→ словарь отставания роли или None, если отставания нет (или мерить не по чему).

    {role, section, saved, last_note, lag_h, notes_after}. Исключение из запроса к базе
    поднимается наверх: решать, как сказать о сбое, — зовущему.
    """
    cols = {r[1] for r in con.execute("PRAGMA table_info(phoenix)")}
    look = "COALESCE(confirmed_at, saved_at)" if "confirmed_at" in cols else "saved_at"
    row = con.execute(f"SELECT section, {look} FROM phoenix WHERE role=? AND section='state'",
                      (role,)).fetchone()
    if not row or not row[1]:
        row = con.execute(f"SELECT section, {look} AS seen FROM phoenix WHERE role=? "
                          f"ORDER BY seen DESC LIMIT 1", (role,)).fetchone()
    if not row or not row[1]:
        return None
    section, saved = row
    feed = "messages_all" if _has(con, "messages_all") else "messages"
    notes_after, last_note = con.execute(
        f"SELECT COUNT(*), MAX(timestamp) FROM {feed} WHERE writer_role=? AND timestamp > ?",
        (role, saved)).fetchone()
    if not notes_after or not last_note:
        return None
    lag_h = (_ts(last_note) - _ts(saved)).total_seconds() / 3600
    if lag_h <= LAG_HOURS:
        return None
    return {"role": role, "section": section, "saved": saved, "last_note": last_note,
            "lag_h": lag_h, "notes_after": notes_after}


def _roles(con) -> list:
    """Роли, о которых говорить: из реестра, кроме закрытых; реестра нет — все, у кого есть память."""
    if _has(con, "roles"):
        cols = {r[1] for r in con.execute("PRAGMA table_info(roles)")}
        if "lifecycle" in cols:
            return [r[0] for r in con.execute(
                "SELECT role FROM roles WHERE lifecycle <> 'closed' ORDER BY role")]
        return [r[0] for r in con.execute("SELECT role FROM roles ORDER BY role")]
    return [r[0] for r in con.execute("SELECT DISTINCT role FROM phoenix ORDER BY role")]


def lag_line(con):
    """→ строка «память отстала» или None, когда отставших нет. Сбой — строка о сбое, не молчание."""
    try:
        found = [x for x in (memory_lag(con, r) for r in _roles(con)) if x]
    except Exception as exc:                                        # noqa: BLE001
        return (f"   💾 отставание памяти ролей НЕ посчитано ({exc.__class__.__name__}: {exc}) — "
                "это не «все сохранены»")
    if not found:
        return None
    parts = []
    for x in found:
        where = "" if x["section"] == "state" else f", раздела state нет — по {x['section']}"
        parts.append(f"{x['role']} {x['lag_h']:.0f} ч, записок после {x['notes_after']}{where}")
    save = (Path(__file__).resolve().parent / "save-phoenix.py").as_posix()
    return (f"   💾 память отстала от своей работы больше чем на {LAG_HOURS} ч (от сохранения "
            f"раздела state до последней своей записки): {' · '.join(parts)}\n"
            f"      сохранить: python {save} --role <РОЛЬ> --section state --file <файл>")
