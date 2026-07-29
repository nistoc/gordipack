# -*- coding: utf-8 -*-
r"""
guard-phoenix-time.py — ЛОКАЛЬНОЕ ВРЕМЯ ПОД СУФФИКСОМ «UTC» В ТЕЛЕ СЛЕПКА.

Заведён 2026-07-28 по заявке @COORD (#2880). Повод — история класса за трое суток:
  · 07-26 @opssre: заголовки секций несли локальное время с подписью UTC — нашли ЧТЕНИЕМ;
  · 07-27 @TAXO была ВТОРЫМ СВИДЕТЕЛЕМ, сверяла его метки, подтвердила фикс, забрала
    «починку слова вместе с примером» в канон как образец;
  · 07-28 @TAXO допустила тот же дефект в ПЕРВОЙ ЖЕ записи новой инкарнации (+119 мин).
📌 Класс, названный @COORD: **быть свидетелем дефекта у другого не защищает от него —
   защищает только механизм.** Ни один существующий гард его не ловит: `guard-utc.py`
   смотрит КОД тулкита (astimezone/now()), `guard-role-standard` — форму вызова и
   производные факты. Время в ТЕЛЕ секции не проверял никто.

КАК ЛОВИТСЯ (механически, без чтения глазами)
  У каждой секции есть `saved_at` — записан скриптом, в UTC, подделать нечем.
  В теле секции роль пишет метки вида «2026-07-28 11:11 UTC».
  Если метка ОПЕРЕЖАЕТ `saved_at` примерно на целое число часов (± допуск) — это локальное
  время под суффиксом UTC: ровно смещение часового пояса, а не мысль автора.

ЧЕГО НЕ ЛОВИТ (называю сам, чтобы зелёное не читалось шире)
  · метку ПРОШЛОГО (цитата, история, «замер 26.07 09:05 UTC») — она отстаёт, а не опережает;
  · зону с нулевым смещением (летом у нас +2, зимой +1 — потому и ищем ЦЕЛЫЕ часы);
  · время без суффикса UTC — это отдельный дефект, здесь не судится;
  · тексты вне phoenix (ноты, правила) — этот гард только про слепки.

    python C:/guts/.atlas/vnext-tools/guard-phoenix-time.py                # все роли
    python C:/guts/.atlas/vnext-tools/guard-phoenix-time.py --role TAXO
    python C:/guts/.atlas/vnext-tools/guard-phoenix-time.py --selftest
"""
import argparse
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

LIVE_DB = Path(r"C:/guts/.atlas/.mezosync/mezosync.db")
STAMP = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?\s*UTC")
# Смещения, которые вообще может дать локальная зона роли. Не «наши +2», а диапазон:
# гард переживёт переезд владельца и смену сезона, а зашитое «+120» протухло бы молча.
OFFSETS = [timedelta(hours=h) for h in range(1, 15)]
TOLERANCE = timedelta(minutes=3)     # округление минут в подписи
# ⚠️ Калибровка первым же живым прогоном: гард покраснел на строке @ING
# «Формат "2026-07-26 11:22 UTC", суффикс обязателен» — это ОБРАЗЕЦ ФОРМАТА, а не метка
# события. Дата в примере случайно опережала saved_at на ровный час. Проверка, не отличающая
# ПРИМЕР от УТВЕРЖДЕНИЯ, — тот же класс, что «краснеть на честном надгробии»: гард требует
# «починить» текст, который ничему плохому не учит.
FORMAT_EXAMPLE = re.compile(r"формат|например|вида\b|образец|шаблон|例|напр\.", re.I)


def parse(row):
    d, hh, mm, ss = row.group(1), row.group(2), row.group(3), row.group(4) or "00"
    try:
        return datetime.strptime(f"{d} {hh}:{mm}:{ss}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def check_section(body, saved_at):
    """Метки, опережающие saved_at ровно на целое число часов ⇒ локальное под «UTC»."""
    out = []
    try:
        saved = datetime.strptime(saved_at[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return [("⚠️ saved_at не разобран — секция НЕ проверена", str(saved_at)[:40], "")]
    for i, line in enumerate((body or "").splitlines(), 1):
        for m in STAMP.finditer(line):
            t = parse(m)
            if t is None or t <= saved:
                continue                       # прошлое — это история, а не дефект
            delta = t - saved
            for off in OFFSETS:
                if abs(delta - off) <= TOLERANCE:
                    hours = int(off.total_seconds() // 3600)
                    if FORMAT_EXAMPLE.search(line):
                        out.append((f"🟡 похоже на ОБРАЗЕЦ ФОРМАТА (+{hours} ч к saved_at) — "
                                    f"не метка события, чинить нечего", f":{i}", line.strip()[:100]))
                    else:
                        out.append((f"🔴 ЛОКАЛЬНОЕ ВРЕМЯ ПОД «UTC»: +{hours} ч "
                                    f"к saved_at ({saved_at[:16]})", f":{i}", line.strip()[:100]))
                    break
            else:
                if delta > timedelta(minutes=30):
                    out.append((f"🟡 метка ОПЕРЕЖАЕТ saved_at на {int(delta.total_seconds()//60)} мин "
                                f"(не целый час — вероятно, не зона)", f":{i}", line.strip()[:100]))
    return out


def run(db, role=None):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = "SELECT role, section, body, saved_at FROM phoenix"
    args = ()
    if role:
        q += " WHERE UPPER(role)=UPPER(?)"
        args = (role,)
    rows = con.execute(q + " ORDER BY role, section").fetchall()
    con.close()
    if not rows:
        print(f"⛔ ОТКАЗ: в phoenix нет {'роли ' + role if role else 'ничего'} — это отказ, не «чисто»")
        return 2
    red = yellow = 0
    for r, sec, body, saved in rows:
        hits = check_section(body, saved)
        if not hits:
            continue
        print(f"── {r}/{sec}   (saved_at {str(saved)[:16]} UTC)")
        for kind, where, line in hits:
            print(f"   {kind}\n      {where}  {line}")
        red += sum(1 for k, _, _ in hits if k.startswith("🔴"))
        yellow += sum(1 for k, _, _ in hits if k.startswith("🟡"))
    print(f"\n{'🔴' if red else '✅'} метка-под-UTC: 🔴 {red} · 🟡 {yellow} "
          f"· секций проверено {len(rows)}")
    if red:
        print("   ⇒ фикс: `datetime.now(timezone.utc)`; самопроверка роли — «метка в теле ≈ saved_at».")
    return 1 if red else 0


SAMPLES = [
    # (тело, saved_at, сколько 🔴 ждём)
    ("обновлено 2026-07-28 11:11 UTC", "2026-07-28 09:12:32", 1),   # ровно дефект @TAXO (+2 ч)
    ("обновлено 2026-07-28 09:12 UTC", "2026-07-28 09:12:32", 0),   # честная метка
    ("замер 2026-07-26 09:05 UTC — история", "2026-07-28 09:12:32", 0),  # прошлое не судим
    ("дедлайн 2026-07-28 09:47 UTC", "2026-07-28 09:12:32", 0),     # +35 мин → 🟡, не 🔴
    ("зимой было 2026-01-10 10:12 UTC", "2026-01-10 09:12:00", 1),  # +1 ч тоже зона
    # образец формата (живой случай @ING): дата в примере опережает saved_at на ровный час,
    # но это иллюстрация, а не утверждение о времени ⇒ 🟡, не 🔴
    ('Формат «2026-07-26 11:22 UTC», суффикс обязателен', "2026-07-26 10:23:00", 0),
]


def selftest():
    ok = True
    for body, saved, want in SAMPLES:
        hits = check_section(body, saved)
        got = sum(1 for k, _, _ in hits if k.startswith("🔴"))
        good = got == want
        ok &= good
        print(f"{'✅' if good else '🔴'} 🔴={got} (ждём {want})  «{body[:45]}»  saved={saved[:16]}")
    # и отказ на пустой БД — молчание вместо отказа было дефектом соседнего инструмента
    tmp = Path(tempfile.mkdtemp(prefix="guard-ptime-")) / "m.db"
    con = sqlite3.connect(str(tmp))
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
    con.commit()
    con.close()
    rc = run(tmp)
    good = rc == 2
    ok &= good
    print(f"{'✅' if good else '🔴'} пустая БД → rc={rc} (ждём 2: отказ, а не «чисто»)")
    print(f"\n{'✅ ГАРД ЧУВСТВИТЕЛЕН' if ok else '🔴 ГАРД СЛЕП ИЛИ ШУМИТ'} — ловит зону "
          f"(+1 и +2 ч), молчит на честной метке, на прошлом и на не-целом сдвиге")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(LIVE_DB))
    ap.add_argument("--role")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else run(Path(a.db), a.role)


if __name__ == "__main__":
    sys.exit(main())
