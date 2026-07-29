# -*- coding: utf-8 -*-
r"""
guard-phoenix-time.py — ЛОКАЛЬНОЕ ВРЕМЯ ПОД СУФФИКСОМ «UTC» В СЛЕПКАХ И НОТАХ.

Заведён 2026-07-28 по заявке @COORD (#2880). Расширен 2026-07-29 по заявке @COORD (#2887) —
двумя пробелами, найденными на авторе гарда (@PROTO), а не на постороннем. Повод — история
класса за ТРОЕ суток, и каждый раз следующей жертвой оказывался автор/свидетель механизма:
  · 07-26 @opssre: заголовки секций несли локальное время с подписью UTC — нашли ЧТЕНИЕМ;
  · 07-27 @TAXO была ВТОРЫМ СВИДЕТЕЛЕМ, сверяла его метки, подтвердила фикс, забрала
    «починку слова вместе с примером» в канон как образец;
  · 07-28 @TAXO допустила тот же дефект в ПЕРВОЙ ЖЕ записи новой инкарнации (+119 мин) —
    гард поймал МЕХАНИЧЕСКИ, впервые без чтения;
  · 07-29 @PROTO (автор гарда) допустил его ДВАЖДЫ разом: нота #2885 несла местное время
    под UTC (+119 мин, форма ловилась бы — но гард не смотрел ноты вообще), а §4 слепка
    нёс ДАТУ без часов «2026-07-29 UTC» при saved_at 07-28 (форма, которую регексп с
    `\d{2}:\d{2}` пропускал по построению). Нашёл @COORD (#2887).
📌 Класс, названный @COORD: **быть свидетелем дефекта у другого не защищает от него —
   защищает только механизм. Механизм защищает только там, куда дотянулся** (07-29,
   #2887) — было замерено ТРИЖДЫ по кускам (скрипты → слепки → ноты), и «класс закрыт»
   каждый раз означало «закрыт замеренный кусок», не весь класс.

КАК ЛОВИТСЯ (механически, без чтения глазами) — ДВЕ проверки, одна reference-точка на запись
  1) ПОЛНАЯ МЕТКА (дата+часы). У каждой секции `phoenix` есть `saved_at`, у каждой ноты
     `messages` — свой `timestamp`; оба пишет скрипт, в UTC, подделать нечем. Если метка в
     ТЕКСТЕ («2026-07-28 11:11 UTC») ОПЕРЕЖАЕТ эту точку на целое число часов (± допуск) —
     локальное время под суффиксом UTC.
  2) ДАТА БЕЗ ЧАСОВ («2026-07-29 UTC», без `HH:MM`). Прежняя проверка её не видела вообще —
     регексп требовал часы. Если календарная дата в тексте ПОЗЖЕ календарной даты reference-
     точки — тот же дефект, просто без времени сузивший форму настолько, что сдвиг на СУТКИ
     (грубее любого часового) проходил мимо. Обе проверки НЕ пересекаются: полная метка не
     подходит под «дата сразу перед UTC», а дата-без-часов не подходит под «дата+часы+UTC».

ГДЕ ИЩЕТСЯ — ДВЕ ПОВЕРХНОСТИ, каждая своей reference-точкой
  · `phoenix` (слепки) — как и раньше;
  · `messages` (ноты) — НОВОЕ (07-29, #2887): нота — ПУБЛИЧНАЯ учащая поверхность, по её
    шапке контур строит хронологию инцидентов; метка, врущая на часы, дороже всего именно
    там. `messages_history` (домиграционный импорт) НЕ смотрим — другой источник, другой шум.

ЧЕГО НЕ ЛОВИТ (называю сам, чтобы зелёное не читалось шире)
  · метку ПРОШЛОГО (цитата, история, «замер 26.07 09:05 UTC») — она отстаёт, а не опережает;
  · зону с нулевым смещением (летом у нас +2, зимой +1 — потому и ищем ЦЕЛЫЕ часы);
  · время без суффикса UTC — это отдельный дефект, здесь не судится;
  · `messages_history`, `rules`, `read_batches` и прочие таблицы — эти две (phoenix+messages)
    покрыты, остальное — следующий кусок, если он вообще нужен (называть, не гнаться заранее).

    python C:/guts/.atlas/vnext-tools/guard-phoenix-time.py                # все роли, обе поверхности
    python C:/guts/.atlas/vnext-tools/guard-phoenix-time.py --role TAXO
    python C:/guts/.atlas/vnext-tools/guard-phoenix-time.py --skip-messages   # только слепки (быстрый прогон)
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
# ДАТА БЕЗ ЧАСОВ — форма, которую STAMP пропускает по построению (\d{2}:\d{2} обязателен).
# Не пересекается со STAMP: между датой и «UTC» здесь ничего, кроме пробела/скобки/тире.
STAMP_DATE_ONLY = re.compile(r"(\d{4}-\d{2}-\d{2})[ \t\)\]—-]*UTC\b")
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


def check_section(body, saved_at, ref_label="saved_at"):
    """Метки, опережающие reference-точку (saved_at секции / timestamp ноты) на целое
    число часов ⇒ локальное под «UTC». Плюс дата-без-часов, опережающая КАЛЕНДАРНО."""
    out = []
    try:
        saved = datetime.strptime(saved_at[:19], "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return [(f"⚠️ {ref_label} не разобран — запись НЕ проверена", str(saved_at)[:40], "")]
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
                        out.append((f"🟡 похоже на ОБРАЗЕЦ ФОРМАТА (+{hours} ч к {ref_label}) — "
                                    f"не метка события, чинить нечего", f":{i}", line.strip()[:100]))
                    else:
                        out.append((f"🔴 ЛОКАЛЬНОЕ ВРЕМЯ ПОД «UTC»: +{hours} ч "
                                    f"к {ref_label} ({saved_at[:16]})", f":{i}", line.strip()[:100]))
                    break
            else:
                if delta > timedelta(minutes=30):
                    out.append((f"🟡 метка ОПЕРЕЖАЕТ {ref_label} на {int(delta.total_seconds()//60)} мин "
                                f"(не целый час — вероятно, не зона)", f":{i}", line.strip()[:100]))
        for m in STAMP_DATE_ONLY.finditer(line):
            try:
                d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                continue
            days = (d - saved.date()).days
            if days <= 0:
                continue                       # сегодня или прошлое reference-точки — не дефект
            tag = "🟡 похоже на ОБРАЗЕЦ ФОРМАТА" if FORMAT_EXAMPLE.search(line) else "🔴 ДАТА БЕЗ ЧАСОВ ОПЕРЕЖАЕТ"
            out.append((f"{tag}: +{days} сут. к {ref_label} ({saved_at[:10]}, без времени "
                        f"сдвиг мельче часа не виден)", f":{i}", line.strip()[:100]))
    return out


def run_phoenix(db, role=None):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = "SELECT role, section, body, saved_at FROM phoenix"
    args = ()
    if role:
        q += " WHERE UPPER(role)=UPPER(?)"
        args = (role,)
    rows = con.execute(q + " ORDER BY role, section", args).fetchall()
    con.close()
    if not rows:
        print(f"⛔ ОТКАЗ (phoenix): в phoenix нет {'роли ' + role if role else 'ничего'} — это отказ, не «чисто»")
        return None
    red = yellow = 0
    for r, sec, body, saved in rows:
        hits = check_section(body, saved, ref_label="saved_at")
        if not hits:
            continue
        print(f"── {r}/{sec}   (saved_at {str(saved)[:16]} UTC)")
        for kind, where, line in hits:
            print(f"   {kind}\n      {where}  {line}")
        red += sum(1 for k, _, _ in hits if k.startswith("🔴"))
        yellow += sum(1 for k, _, _ in hits if k.startswith("🟡"))
    print(f"{'🔴' if red else '✅'} phoenix (слепки): 🔴 {red} · 🟡 {yellow} · секций проверено {len(rows)}")
    return red, yellow, len(rows)


def run_messages(db, role=None):
    """Та же проверка на публичной учащей поверхности — нотах (#2887, @COORD)."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    q = "SELECT id, writer_role, body_md, timestamp FROM messages"
    args = ()
    if role:
        q += " WHERE UPPER(writer_role)=UPPER(?)"
        args = (role,)
    try:
        rows = con.execute(q + " ORDER BY id", args).fetchall()
    except sqlite3.OperationalError as e:
        con.close()
        print(f"⚠️ messages не прочитаны ({e}) — эта поверхность НЕ проверена")
        return None
    con.close()
    red = yellow = 0
    for mid, wrole, body, ts in rows:
        hits = check_section(body, ts, ref_label="timestamp ноты")
        if not hits:
            continue
        print(f"── #{mid} [{wrole}]   (timestamp {str(ts)[:16]} UTC)")
        for kind, where, line in hits:
            print(f"   {kind}\n      {where}  {line}")
        red += sum(1 for k, _, _ in hits if k.startswith("🔴"))
        yellow += sum(1 for k, _, _ in hits if k.startswith("🟡"))
    print(f"{'🔴' if red else '✅'} messages (ноты): 🔴 {red} · 🟡 {yellow} · нот проверено {len(rows)}")
    return red, yellow, len(rows)


def run(db, role=None, skip_messages=False):
    p = run_phoenix(db, role)
    if p is None:
        return 2
    p_red, p_yellow, p_n = p
    m_red = m_yellow = m_n = 0
    if not skip_messages:
        m = run_messages(db, role)
        if m is not None:
            m_red, m_yellow, m_n = m
    red, yellow = p_red + m_red, p_yellow + m_yellow
    print(f"\n{'🔴' if red else '✅'} метка-под-UTC ИТОГО: 🔴 {red} · 🟡 {yellow} "
          f"· записей проверено {p_n + m_n} (phoenix {p_n} + messages {m_n if not skip_messages else 'пропущено'})")
    if red:
        print("   ⇒ фикс: `datetime.now(timezone.utc)`; самопроверка роли — «метка в теле ≈ saved_at/timestamp».")
        print("   ⚠️ Исторические ноты (уже отправленные) не переписываются — правь ПРИВЫЧКУ, не прошлое.")
    return 1 if red else 0


SAMPLES = [
    # (тело, saved_at, сколько 🔴 ждём) — полная метка (дата+часы)
    ("обновлено 2026-07-28 11:11 UTC", "2026-07-28 09:12:32", 1),   # ровно дефект @TAXO (+2 ч)
    ("обновлено 2026-07-28 09:12 UTC", "2026-07-28 09:12:32", 0),   # честная метка
    ("замер 2026-07-26 09:05 UTC — история", "2026-07-28 09:12:32", 0),  # прошлое не судим
    ("дедлайн 2026-07-28 09:47 UTC", "2026-07-28 09:12:32", 0),     # +35 мин → 🟡, не 🔴
    ("зимой было 2026-01-10 10:12 UTC", "2026-01-10 09:12:00", 1),  # +1 ч тоже зона
    # образец формата (живой случай @ING): дата в примере опережает saved_at на ровный час,
    # но это иллюстрация, а не утверждение о времени ⇒ 🟡, не 🔴
    ('Формат «2026-07-26 11:22 UTC», суффикс обязателен', "2026-07-26 10:23:00", 0),
    # ── ДАТА БЕЗ ЧАСОВ (07-29, #2887 — ровно мой собственный §4-дефект) ──
    ("[обновлено 2026-07-29 UTC — НОВАЯ ИНКАРНАЦИЯ]", "2026-07-28 22:12:23", 1),  # +1 сутки
    ("[обновлено 2026-07-28 UTC — НОВАЯ ИНКАРНАЦИЯ]", "2026-07-28 22:12:23", 0),  # честная дата
    ("цитата дня 2026-01-01 UTC (историческая)", "2026-07-28 09:12:32", 0),        # дата в прошлом
    # полная метка НЕ должна давать второй (date-only) хит на той же строке
    ("правлено 2026-07-28 11:11 UTC", "2026-07-28 09:12:32", 1),   # ровно 1, не 2
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
    con.execute("CREATE TABLE messages (id INTEGER, writer_role TEXT, body_md TEXT, timestamp TEXT)")
    con.commit()
    con.close()
    rc = run(tmp)
    good = rc == 2
    ok &= good
    print(f"{'✅' if good else '🔴'} пустая БД (обе таблицы) → rc={rc} (ждём 2: отказ, а не «чисто»)")
    # messages видит СВОЙ класс отдельно от phoenix — не только «пришит к той же функции»
    tmp2 = Path(tempfile.mkdtemp(prefix="guard-ptime-")) / "m2.db"
    con = sqlite3.connect(str(tmp2))
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
    con.execute("CREATE TABLE messages (id INTEGER, writer_role TEXT, body_md TEXT, timestamp TEXT)")
    con.execute("INSERT INTO phoenix VALUES ('X','state','чисто','2026-07-28 09:00:00')")
    con.execute("INSERT INTO messages VALUES (1,'X','местное время 2026-07-28 11:05 UTC','2026-07-28 09:04:50')")
    con.commit()
    con.close()
    red, yellow, n = run_messages(tmp2, role=None)
    good = red == 1 and n == 1
    ok &= good
    print(f"{'✅' if good else '🔴'} messages ловит СВОЙ дефект (не только phoenix) → 🔴{red} нот={n}")
    print(f"\n{'✅ ГАРД ЧУВСТВИТЕЛЕН' if ok else '🔴 ГАРД СЛЕП ИЛИ ШУМИТ'} — ловит зону "
          f"(+1 и +2 ч, дату-без-часов), молчит на честной метке/прошлом/не-целом сдвиге, "
          f"видит phoenix И messages по отдельности")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(LIVE_DB))
    ap.add_argument("--role")
    ap.add_argument("--skip-messages", action="store_true", help="только phoenix, без нот (быстрее)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    return selftest() if a.selftest else run(Path(a.db), a.role, a.skip_messages)


if __name__ == "__main__":
    sys.exit(main())
