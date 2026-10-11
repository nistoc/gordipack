#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Проверка блока «КОНЕЦ СМЕНЫ» в разделе state и строки «сверен с state» в plan (карточка #702).

ПРЕДМЕТ. Порядок ① (слово владельца 2026-10-11 10:11 UTC, чат COORD; выжимка — записка #5688):
по команде «сохранись и закрой смену» роль пишет в state блок «КОНЕЦ СМЕНЫ <UTC>» с четырьмя
частями и сохраняет его ДО записки «смена закрыта»; в заголовке plan ставит «сверен с state <UTC>»
(поправка Б). Форма, которую никто не проверяет, держится на дисциплине — проверка делает её
механической.

ЧТО СУДИТ (только у роли, в state которой есть блок; роль без блока не судится):
  ① четыре части блока — по началу строки: последним · не доделано · жду · ошибалась
  ② в части «последним» — номер записки или карточки
  ③ в первых пяти строках plan — «сверен с state <UTC>», и этот час не раньше часа блока;
    при чтении базы — и сам plan сохранён не раньше минуты блока (написанный час — не довод)
  ④ (только при чтении базы) между блоком и записью «смена закрыта» у роли нет записок
  ⑤ строка, похожая на заголовок блока, но не разобранная (нет «#» в начале, дата не через дефис,
    час не UTC) — «блок не узнан» и форма: роль, написавшая блок не по образцу, узнаёт об этом
⚖️ Записки ПОСЛЕ «смена закрыта» — уже новая смена (роль проснулась): они не находка, а строка
  «ℹ️ … блок прошлой смены»; сохранение state и plan тоже не ставит «✅» блоку прошлой смены.

ЗОВУТ ДВА МЕСТА, одной функцией block_findings():
  save-phoenix.py при сохранении state или plan, когда в state есть блок, — строками под «OK»
  (предупреждение, не отказ: это минута закрытия чата);
  guard-all.py — мягко (--soft): код 0, находки строками «⚠️».
🩸 Первая редакция утверждала «живых блоков на 2026-10-11 нет» — замер был сделан ЭТОЙ ЖЕ
  проверкой, и её слепота спрятала живой блок CHROME (заголовок «## 🔇 КОНЕЦ СМЕНЫ …»):
  значок между «##» и словами не проходил. Нашла CORE (записка #5738). Живых блоков на
  2026-10-11 14:30 UTC — один; перевод в провал — отдельным решением после замера.
Решение и доводы — комментарии на карточке #702.

Запуск:
  python guard-shift-end.py                  все роли; код 1, если есть находки
  python guard-shift-end.py --role CORE      одна роль
  python guard-shift-end.py --soft           код 0 всегда, находки строками «⚠️» (для общего прогона)
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

TIME = r"(\d{4}-\d\d-\d\d[ T]\d\d:\d\d(?::\d\d)?)\s*UTC"
# Между знаком заголовка и словами — любые не-буквы: пробел, «**», значок (записка #5738).
HEADING = re.compile(r"^(#{1,6})[^\w\n]*КОНЕЦ\s+СМЕНЫ\b[^\n]*?" + TIME, re.I | re.M)
# Строка, ПОХОЖАЯ на заголовок блока: в начале только не-буквы (кроме кавычек и маркера списка
# «-»), дальше «КОНЕЦ СМЕНЫ» и где-то в строке цифра (дата или час). Прозу без часа
# («- КОНЕЦ СМЕНЫ — в разделе state») не трогает. Замер 2026-10-11 по всем версиям памяти всех
# ролей: строк такого вида 3, все три — настоящие заголовки блока.
LOOKS_LIKE = re.compile(r"^[^\w\n«\"„“'•·-]*КОНЕЦ\s+СМЕНЫ\b[^\n]*\d", re.I | re.M)
ANY_HEADING = re.compile(r"^(#{1,6})\s+\S", re.M)
# Начало строки части — любые не-буквы: «-», «*», «**», «###», значок (подзаголовки — записка #5738).
LINE_START = r"^[^\w\n]*"
# Части узнаются по началу строки: роли разного рода («ошибалась» / «ошибался»), падеж и
# форма глагола не важны — важно, что часть названа.
PARTS = [
    ("последним", re.compile(LINE_START + r"последн\w*", re.I | re.M)),
    ("не доделано", re.compile(LINE_START + r"не\s+(?:доделан|сделан|закончен)\w*", re.I | re.M)),
    ("жду", re.compile(LINE_START + r"(?:жд[уёе]\w*|ожида\w*)", re.I | re.M)),
    ("ошибалась", re.compile(LINE_START + r"ошиб\w*", re.I | re.M)),
]
NUMBER_REF = re.compile(r"(?:записк|карточк)\w*\s+#\d+", re.I)
PLAN_MARK = re.compile(r"сверен\w*\s+с\s+state\s+" + TIME, re.I)
CLOSED = re.compile(r"смена\s+закрыта", re.I)
PLAN_HEAD_LINES = 5
FORM = ["   форма блока (раздел state):",
        "      ## КОНЕЦ СМЕНЫ <YYYY-MM-DD HH:MM> UTC",
        "      - последним: … (записка #N или карточка #N)",
        "      - не доделано: … и почему",
        "      - жду: … от кого",
        "      - ошибалась: …"]


def norm(t):
    """Час к виду «YYYY-MM-DD HH:MM:SS» — так его хранит база, и строки сравнимы."""
    t = t.replace("T", " ")
    return t if len(t) == 19 else t + ":00"


def find_block(state_body):
    """(час блока, текст блока, начало заголовка) — по ПОСЛЕДНЕМУ заголовку «КОНЕЦ СМЕНЫ», или None.

    Блок кончается следующим заголовком того же уровня или выше; заголовок, который сам
    называет часть («### последним»), блок не кончает."""
    if not state_body:
        return None
    found = list(HEADING.finditer(state_body))
    if not found:
        return None
    m = found[-1]
    level = len(m.group(1))
    end = len(state_body)
    for h in ANY_HEADING.finditer(state_body, m.end()):
        if len(h.group(1)) > level:
            continue
        line = state_body[h.start():].split("\n", 1)[0]
        if any(rx.match(line) for _, rx in PARTS):
            continue
        end = h.start()
        break
    return norm(m.group(2)), state_body[m.start():end], m.start()


def unrecognized(state_body):
    """Строки, похожие на заголовок блока, но не разобранные, — после последнего узнанного
    заголовка (или все, если узнанного нет). Каждая — текст строки, до 100 знаков."""
    if not state_body:
        return []
    starts = {m.start() for m in HEADING.finditer(state_body)}
    last = max(starts) if starts else -1
    return [m.group(0).strip()[:100] for m in LOOKS_LIKE.finditer(state_body)
            if m.start() > last and m.start() not in starts]


def plan_mark(plan_body):
    """Час из «сверен с state <UTC>» в первых строках plan, или None."""
    if not plan_body:
        return None
    head = [l for l in plan_body.splitlines() if l.strip()][:PLAN_HEAD_LINES]
    for line in head:
        m = PLAN_MARK.search(line)
        if m:
            return norm(m.group(1))
    return None


def block_findings(state_body, plan_body):
    """(час блока или None, находки по самому блоку, находка по plan или None).

    Без блока — (None, [], None): роль, не закрывавшая смену, не судится.
    ⚖️ Находка по plan отдана ОТДЕЛЬНО: при сохранении state она — следующий шаг
    (plan сохраняют после state), а при сохранении plan и в общем прогоне — недочёт."""
    got = find_block(state_body)
    if not got:
        return None, [], None
    when, block, _ = got
    findings = []
    starts = []
    for name, rx in PARTS:
        m = rx.search(block)
        if m:
            starts.append((m.start(), name))
        else:
            findings.append(f"нет части «{name}»")
    # Текст части «последним» — от её начала до начала следующей части (или конца блока).
    starts.sort()
    for i, (pos, name) in enumerate(starts):
        if name != "последним":
            continue
        end = starts[i + 1][0] if i + 1 < len(starts) else len(block)
        if not NUMBER_REF.search(block[pos:end]):
            findings.append("в части «последним» нет номера: «записка #N» или «карточка #N»")
    plan_finding = None
    if plan_body is None:
        plan_finding = "раздела plan нет — сверять не с чем"
    else:
        mark = plan_mark(plan_body)
        if mark is None:
            plan_finding = (f"в первых {PLAN_HEAD_LINES} строках plan нет «сверен с state <UTC>» "
                            f"(поправка Б); блок конца смены — {when} UTC")
        elif mark < when:
            plan_finding = (f"plan сверен с state {mark} UTC — раньше блока конца смены {when} UTC: "
                            "сохрани plan со свежей строкой «сверен с state <UTC>»")
    return when, findings, plan_finding


def unrecognized_lines(state_body):
    """Строки «⚠️ … блок не узнан» для save_lines() и общего прогона."""
    return [f"строка «{line}» похожа на заголовок блока конца смены, но блок НЕ УЗНАН: заголовок — "
            "«## КОНЕЦ СМЕНЫ YYYY-MM-DD HH:MM UTC» (знак «#» в начале строки, дата через дефис, час UTC)"
            for line in unrecognized(state_body)]


def shift_notes(con, role, when):
    """Записки роли после блока: (до «смена закрыта» — [(номер, час)], первая «смена закрыта» —
    (номер, час) или None, записок после неё — число).

    ⚖️ Час блока — с точностью до минуты, поэтому считаются записки с начала СЛЕДУЮЩЕЙ минуты:
    записка той же минуты могла уйти до сохранения блока. Записки после «смена закрыта» —
    уже новая смена (роль проснулась), находкой они не считаются."""
    rows = con.execute(
        "SELECT id, timestamp, body_md FROM messages WHERE writer_role=? "
        "AND timestamp >= datetime(?, '+60 seconds') ORDER BY timestamp, id", (role, when[:16] + ":00")).fetchall()
    before, closed, later = [], None, 0
    for i, ts, b in rows:
        if closed:
            later += 1
        elif CLOSED.search("\n".join((b or "").splitlines()[:3])):
            closed = (i, ts)
        else:
            before.append((i, ts))
    return before, closed, later


def past_shift_line(con, role, when):
    """«ℹ️ … блок прошлой смены», если после записки «смена закрыта» роль уже писала; иначе None."""
    if con is None or not role:
        return None
    _, closed, later = shift_notes(con, role, when)
    if not closed or not later:
        return None
    return (f"ℹ️ блок «КОНЕЦ СМЕНЫ {when[:16]} UTC» — прошлой смены: после записки «смена закрыта» "
            f"#{closed[0]} ({closed[1]} UTC) роль писала ещё {later}; проверка его как свежий не судит")


def save_lines(state_body, plan_body, section, con=None, role=None):
    """Строки для save-phoenix.py под «OK» (карточка #702, место вызова ①). Без блока — [].

    Предупреждение, не отказ: это минута закрытия чата (правило phoenix-save-on-stop).
    con и role (необязательны) — чтобы узнать блок прошлой смены и не ставить ему «✅»."""
    out = [f"⚠️ {line}" for line in unrecognized_lines(state_body)]
    need_form = bool(out)
    when, findings, plan_finding = block_findings(state_body, plan_body)
    if when is None:
        return out + (FORM if need_form else [])
    past = past_shift_line(con, role, when)
    if past:
        return out + (FORM if need_form else []) + [past]
    head = f"блок «КОНЕЦ СМЕНЫ {when[:16]} UTC»"
    out += [f"⚠️ {head}: {f}" for f in findings]
    if any(f.startswith("нет части") for f in findings):
        need_form = True
    if need_form:
        out += FORM
    if plan_finding and section == "state":
        out.append(f"👉 {head} сохранён; следующим — plan со строкой «сверен с state {when[:16]} UTC» "
                   "в первых строках раздела")
    elif plan_finding:
        out.append(f"⚠️ {head}: {plan_finding}")
    if not out:
        out.append(f"✅ {head}: четыре части на месте, plan сверен")
    return out


def check_role(con, role, soft):
    rows = {s: (b, t) for s, b, t in con.execute(
        "SELECT section, body, saved_at FROM phoenix WHERE role=? AND section IN ('state','plan')", (role,))}
    state_body = rows.get("state", (None, None))[0]
    plan_body, plan_saved = rows.get("plan", (None, None))
    mark = "⚠️ " if soft else "   "
    bad = unrecognized_lines(state_body)
    when, findings, plan_finding = block_findings(state_body, plan_body)
    if when is None and not bad:
        return None
    findings = bad + findings
    missing_parts = bool(bad) or any(f.startswith("нет части") for f in findings)
    title = f"блок «КОНЕЦ СМЕНЫ {when[:16]} UTC»" if when else "блок конца смены"
    if when:
        if plan_finding:
            findings.append(plan_finding)
        elif plan_saved and plan_saved[:16] < when[:16]:
            findings.append(f"plan сохранён {plan_saved[:16]} UTC — раньше блока {when[:16]} UTC: строка "
                            "«сверен с state» написана, а раздел после блока не сохранялся")
        before, closed, later = shift_notes(con, role, when)
        if before:
            shown = " · ".join(f"записка #{i} ({ts} UTC)" for i, ts in before[:5])
            more = f" и ещё {len(before) - 5}" if len(before) > 5 else ""
            findings.append(f"после блока у роли записок: {len(before)} — {shown}{more}; блок конца смены "
                            "должен быть последним, кроме самой записки «смена закрыта»")
    if findings:
        print(f"{mark}{role}: {title} — находок {len(findings)}")
        for f in findings:
            print(f"{mark}   · {f}")
        if missing_parts and not soft:
            print("\n".join(FORM))
    else:
        print(f"✅ {role}: {title} — четыре части на месте, plan сверен, записок между блоком и "
              "«смена закрыта» нет")
    if when:
        past = past_shift_line(con, role, when)
        if past:
            print(f"   {role}: {past}")
    return len(findings)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=None, help="путь к базе (по умолчанию — живая база контура)")
    ap.add_argument("--role", default=None, help="одна роль; без флага — все роли с разделом state")
    ap.add_argument("--soft", action="store_true",
                    help="код 0 всегда, находки строками «⚠️» (для общего прогона guard-all.py)")
    a = ap.parse_args()
    if a.db:
        db = Path(a.db)
    else:
        # ⚖️ Импорт здесь, а не в шапке: save-phoenix.py грузит этот файл ради save_lines(),
        # и соседний модуль путей ему не нужен — его отсутствие не должно ронять сохранение.
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import mezo_paths  # пути машины выводятся, не впечатаны
        db = mezo_paths.live_db()
    try:
        con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
        con.execute("SELECT 1 FROM phoenix LIMIT 1")
    except sqlite3.Error as e:
        print(f"⛔ память не прочитана ({e}) — НЕ ПРОВЕРЕНО, это не «чисто»")
        return 2
    roles = [a.role.upper()] if a.role else [
        r for (r,) in con.execute("SELECT DISTINCT role FROM phoenix WHERE section='state' ORDER BY role")]
    judged, total = 0, 0
    for role in roles:
        n = check_role(con, role, a.soft)
        if n is not None:
            judged += 1
            total += n
    con.close()
    print(f"ИТОГ: ролей смотрено {len(roles)} · с блоком конца смены {judged} · находок {total}"
          + ("" if judged else " — блока нет ни у одной роли, судить нечего"))
    if a.soft:
        return 0
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
