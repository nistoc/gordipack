# -*- coding: utf-8 -*-
"""НА СКОЛЬКО ПАМЯТЬ РОЛИ ОТСТАЛА ОТ ЕЁ ЖЕ РАБОТЫ — одна функция для всех, кто об этом говорит.

Слово владельца 2026-09-26 10:45 UTC, чат PROTO (карточка #664): первый шаг к автосохранению
памяти — строка «память отстала» в советующем hook. Повод — письмо контура tapas 08:06 UTC
и замер 08.08: память ролей отставала от их работы на 3–20 часов, и ни одной команды
«сохранись» при этом не звучало. Течёт не на остановке — течёт между.

⚖️ ЧТО ИМЕННО МЕРИТСЯ — ОТСТАВАНИЕ ОТ СМЕНЫ СОСТОЯНИЯ, А НЕ ВОЗРАСТ СОХРАНЕНИЯ.
   отставание = последняя своя записка роли СО СМЕНОЙ СОСТОЯНИЯ − последнее сохранение
   или подтверждение (save-phoenix.py --confirm) её раздела state.
   Возраст сохранения («state записан 20 ч назад») кричал бы и про спящую роль, у которой
   ничего не пропало: она не работала. Признак, который горит всегда, перестаёт значить
   что-либо. Записка, написанная в одном действии с сохранением (секунды спустя),
   отставанием не считается по построению: разница меньше порога.

🪤 ВТОРОЙ ОБОРОТ (issue #38 пакета, 2026-10-28). Прежде считалась ЛЮБАЯ записка. Контур-
   потребитель после шести дней тишины получил пять провалов: три роли ответили на опрос
   координатора («что прочитано, что закрыто, что предлагаю») — и только. Устарело ли
   содержание разделов, проверка не знала: текст записок она не смотрела. Красное гасило
   любое пересохранение, в том числе неизменного текста, — и учило гасить, а не перечитывать.
   ⇒ Теперь отставание двигают только записки с ПРИЗНАКАМИ СМЕНЫ СОСТОЯНИЯ (state_change()):
   commit или его sha · «слово владельца» · закрытие карточки своей рукой · числа замера.
   Записки без них («принято», «прочитала», ответ на опрос) — это «раздел не подтверждался
   после записки», а не отставание: о нём говорят только предупреждением (поле unconfirmed_h).

🔴 ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ:
   · работа видна только по запискам роли. Правки файлов, commit, прогоны без записки сюда
     не попадают — роль, работающая молча, отставания не покажет;
   · признаки — образцы слов, а не понимание: записка, сменившая положение дел без этих слов,
     отставания не двигает; записка, упомянувшая чужой sha мимоходом, — двигает;
   · это СОВЕТ, а не принуждение: условие отмены правила phoenix-save-on-stop («сохранение
     стало свойством механизма») этим не выполняется.

⛔ Функции не пишут в базу. lag_line() не бросает наружу: зовущий (hook при каждой реплике
   человека) не имеет права сломать ход из-за неё.
"""
import re
from datetime import datetime
from pathlib import Path

LAG_HOURS = 3          # порог: тот же, что у совета в write-message.py («память не подтверждалась 3 ч»)

# sha: 7–40 строчных шестнадцатеричных знаков, среди них хотя бы одна буква и одна цифра —
# иначе «1234567» (номер) и «deadbee» (слово) считались бы commit. Регистр не сворачивается:
# git печатает sha строчными, а «ABCDEF1» прописными — скорее имя, чем commit.
_SHA = re.compile(r"(?<![0-9A-Za-z])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}(?![0-9A-Za-z])")
_COMMIT_WORD = re.compile(r"\bcommit\w*|\bкоммит\w*", re.IGNORECASE)
# Признаки смены состояния — (имя для человека, проверка текста). Порядок — порядок в печати.
STATE_CHANGE_MARKS = (
    ("commit", lambda t: bool(_SHA.search(t) or _COMMIT_WORD.search(t))),
    ("слово владельца", re.compile(r"\bслов\w*\s+владельца", re.IGNORECASE).search),
    # закрытие СВОЕЙ рукой — глаголом действия рядом с номером; «карточка #12 уже закрыта»
    # в ответе на опрос пересказывает положение дел и состояния роли не меняет
    ("закрытие карточки", re.compile(
        r"\b(?:закрыл\w*|закрываю)\s+(?:карточк\w*\s+|заявк\w*\s+)?#\d+", re.IGNORECASE).search),
    ("числа замера", re.compile(r"\bзамер\w*[^\n]{0,80}?\d", re.IGNORECASE).search),
)
STATE_CHANGE_NAMES = " · ".join(name for name, _ in STATE_CHANGE_MARKS)


def state_change(text) -> list:
    """→ имена признаков смены состояния в тексте записки; пустой список — признаков нет."""
    text = text or ""
    return [name for name, found in STATE_CHANGE_MARKS if found(text)]


def _ts(text):
    return datetime.fromisoformat(str(text).replace("T", " ").replace(" UTC", "")[:19])


def _has(con, name) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone())


def _look(con) -> str:
    cols = {r[1] for r in con.execute("PRAGMA table_info(phoenix)")}
    return "COALESCE(confirmed_at, saved_at)" if "confirmed_at" in cols else "saved_at"


def seen_at(con, role: str, section: str):
    """Час, когда роль последний раз сохранила или подтвердила раздел; None — раздела нет."""
    row = con.execute(f"SELECT {_look(con)} FROM phoenix WHERE role=? AND section=?",
                      (role, section)).fetchone()
    return row[0] if row and row[0] else None


def notes_after(con, role: str, since) -> list:
    """→ записки роли позже since, по времени: список (час, признаки смены состояния)."""
    feed = "messages_all" if _has(con, "messages_all") else "messages"
    cols = {r[1] for r in con.execute(f"PRAGMA table_info({feed})")}
    tags = "COALESCE(tags, '')" if "tags" in cols else "''"
    rows = con.execute(f"SELECT timestamp, COALESCE(body_md, ''), {tags} FROM {feed} "
                       f"WHERE UPPER(writer_role)=UPPER(?) AND timestamp > ? ORDER BY timestamp",
                       (role, since)).fetchall()
    return [(ts, state_change(f"{body}\n{tg}")) for ts, body, tg in rows]


def section_lag(con, role: str, section: str):
    """Отставание одного раздела → словарь; None — раздела нет. Порог зовущий применяет сам.

    change_lag_h — от сохранения или подтверждения до последней записки СО СМЕНОЙ СОСТОЯНИЯ
    (None — таких записок не было), с полями last_change · changes · reasons;
    unconfirmed_h — до последней записки ЛЮБОЙ (None — записок после не было), с полями
    last_note · notes.
    """
    saved = seen_at(con, role, section)
    if not saved:
        return None
    every = notes_after(con, role, saved)
    changed = [(ts, marks) for ts, marks in every if marks]
    reasons = []
    for _when, marks in changed:
        reasons += [m for m in marks if m not in reasons]
    last_change = changed[-1][0] if changed else None
    last_note = every[-1][0] if every else None
    return {"saved": saved,
            "change_lag_h": (_ts(last_change) - _ts(saved)).total_seconds() / 3600 if last_change else None,
            "last_change": last_change, "changes": len(changed), "reasons": reasons,
            "unconfirmed_h": (_ts(last_note) - _ts(saved)).total_seconds() / 3600 if last_note else None,
            "last_note": last_note, "notes": len(every)}


def memory_lag(con, role: str):
    """→ словарь отставания роли или None, если отставания нет (или мерить не по чему).

    {role, section, saved, last_note, lag_h, notes_after, reasons, notes_any}: last_note, lag_h
    и notes_after — по запискам СО СМЕНОЙ СОСТОЯНИЯ, notes_any — всех записок после. Раздела
    state нет — мерим по самому свежему разделу. Исключение из запроса к базе поднимается
    наверх: решать, как сказать о сбое, — зовущему.
    """
    section = "state"
    if not seen_at(con, role, section):
        row = con.execute(f"SELECT section, {_look(con)} AS seen FROM phoenix WHERE role=? "
                          f"ORDER BY seen DESC LIMIT 1", (role,)).fetchone()
        if not row or not row[1]:
            return None
        section = row[0]
    lag = section_lag(con, role, section)
    if not lag or lag["change_lag_h"] is None or lag["change_lag_h"] <= LAG_HOURS:
        return None
    return {"role": role, "section": section, "saved": lag["saved"], "last_note": lag["last_change"],
            "lag_h": lag["change_lag_h"], "notes_after": lag["changes"], "reasons": lag["reasons"],
            "notes_any": lag["notes"]}


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
        parts.append(f"{x['role']} {x['lag_h']:.0f} ч, записок со сменой состояния после "
                     f"{x['notes_after']} ({', '.join(x['reasons'])}){where}")
    save = (Path(__file__).resolve().parent / "save-phoenix.py").as_posix()
    return (f"   💾 память отстала от своей работы больше чем на {LAG_HOURS} ч (от сохранения или "
            f"подтверждения раздела state до последней своей записки со сменой состояния: "
            f"{STATE_CHANGE_NAMES}): {' · '.join(parts)}\n"
            f"      сохранить: python {save} --role <РОЛЬ> --section state --file <файл> · "
            f"перечитал, правок нет: python {save} --role <РОЛЬ> --section state --confirm")
