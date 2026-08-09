#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ЗАМЕР: через сколько часов срочная записка перестаёт менять поведение читающих.

Зачем. @COORD (#3291) предложил ход Г: срочность не хранить и не гасить, а ВЫЧИСЛЯТЬ —
показывать пометку, пока записка молода и без ответа. Порог «молода» он отказался брать
из головы и попросил у меня число замером. Эта программа его считает.

Как измеряется «поведение читающих». Единственный наблюдаемый отклик на записку — то, что
кто-то на неё ОТВЕТИЛ. Ответ виден двумя путями:
  ① явная связь reply_to в message_thread (жест новый, связей мало)
  ② упоминание «#N» в теле более поздней записки (жест старый, живёт с самого начала)
Берём ОБА и говорим, сколько дал каждый: если вывод держится только на одном, это надо видеть.

⚖️ ПОТОЛОК ЗАМЕРА, он же главный его недостаток — печатается при каждом прогоне.
Ответ, данный ПРОЗОЙ («принято, беру»), без ссылки и без reply_to, этой программе НЕ ВИДЕН.
Такие записки попадут в «ответа не было» и потянут порог ВВЕРХ (мы решим, что ждать надо
дольше, чем на самом деле). ⇒ Число, которое здесь выходит, — это ВЕРХНЯЯ оценка порога.

⛔ Живую базу открываем ТОЛЬКО на чтение: Mode=ReadOnly + PRAGMA query_only + один SELECT.
"""
import argparse
import re
import sqlite3
import sys
from datetime import datetime

DEFAULT_DB = r"C:\guts\.atlas\.mezosync\mezosync.db"
REF = re.compile(r"#(\d{3,5})")
URGENT = ("high", "critical")


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")


def load(db: str):
    con = sqlite3.connect(f"file:{db.replace(chr(92), '/')}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    msgs = con.execute(
        "SELECT id, writer_role, timestamp, priority, body_md FROM messages ORDER BY id"
    ).fetchall()
    links = con.execute(
        "SELECT message_id, reply_to FROM message_thread WHERE reply_to IS NOT NULL"
    ).fetchall()
    con.close()
    return msgs, links


QUOTED = re.compile(r"«[^»]{0,200}»|`[^`]{0,200}`|^>.*$", re.M)


def strip_quotes(text: str) -> str:
    """Убрать цитаты: ссылка внутри «кавычек», `апострофов` или строки-цитаты — упоминание."""
    return QUOTED.sub(" ", text or "")


def build_answers(msgs, links):
    """Для каждой записки — самый ранний отклик и то, каким путём он найден.

    ТРИ СИЛЫ ОТКЛИКА, и они не равны. @COORD (записка #3316) верно сказал, что мы с ним
    спорили, имея под словом «ответ» разные предметы, и что правда лежит между 10% и 79%.
    Здесь она сужается — не догадкой, а различением:
      жест ....... проставлена связь «в ответ на». Сомнений нет
      обращение .. ссылка «#N» ВНЕ цитаты, и отвечающий назвал автора вопроса (@РОЛЬ).
                   Это разговор с ним, а не упоминание при третьих
      упоминание . всё прочее: «как в записке #N», ссылка внутри «кавычек» или цитаты
    Средняя оценка = жест + обращение. Она и есть ответ на «точнее сказать нельзя».
    """
    ts = {m[0]: parse_ts(m[2]) for m in msgs}
    role = {m[0]: m[1] for m in msgs}
    first = {}          # id → (задержка в часах, путь, id ответа)
    by_kind = {}        # id → {сила отклика: самая ранняя задержка}

    def offer(target, answer, how):
        if target not in ts or answer not in ts:
            return
        if role.get(answer) == role.get(target):   # сам себе не отвечает
            return
        delay = (ts[answer] - ts[target]).total_seconds() / 3600.0
        # 🪤 Сверяем ВРЕМЯ, а не номер. Первая редакция гнала `if answer <= target`
        # и подписывала это «ответ не может быть раньше вопроса» — но номер и метка
        # времени расходятся, и записка с бо́льшим номером входила с ОТРИЦАТЕЛЬНОЙ
        # задержкой, занижая порог. Приёмка поймала (случай ②).
        if delay <= 0:
            return
        prev = first.get(target)
        if prev is None or delay < prev[0]:
            first[target] = (delay, how, answer)
        seen = by_kind.setdefault(target, {})
        if how not in seen or delay < seen[how]:
            seen[how] = delay

    for mid, reply_to in links:
        offer(reply_to, mid, "жест")

    for mid, _r, _t, _p, body in msgs:
        bare = strip_quotes(body)
        outside = set(int(x) for x in REF.findall(bare))          # ссылки ВНЕ цитат
        inside = set(int(x) for x in REF.findall(body or "")) - outside
        for ref in outside:
            author = role.get(ref, "")
            # Назван ли автор вопроса в теле ответа — «@COORD», «[COORD]», «COORD —»
            addressed = bool(author) and re.search(
                rf"@{author}\b|\[{author}\]|\b{author}\s*[—:-]", bare, re.I)
            offer(ref, mid, "обращение" if addressed else "упоминание")
        for ref in inside:
            offer(ref, mid, "упоминание")

    return first, ts, by_kind


def percentile(values, p):
    """Доля p приходит НЕ ПОЗЖЕ возвращённого часа. Ближайший ранг, без сглаживания.

    🪤 Сглаженная форма (среднее между соседями) выдумывает час, которого в данных нет,
    и на разрыве «плотное тело + длинный хвост» уезжает далеко: на 19 ответах по 1 ч
    и одном по 40 ч она давала 3 ч — значение, не случившееся ни разу. Порог обязан
    быть НАБЛЮДЁННЫМ временем, иначе решение принимается по выдуманному числу.
    """
    if not values:
        return None
    v = sorted(values)
    import math
    k = max(1, math.ceil(len(v) * p / 100.0))
    return v[min(k, len(v)) - 1]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Замер порога для вычисляемой срочности (ход Г, записка #3291)")
    ap.add_argument("--db", default=DEFAULT_DB, help="база мезосинка (по умолчанию живая, ТОЛЬКО чтение)")
    ap.add_argument("--cover", type=float, default=95.0,
                    help="какую долю всех состоявшихся ответов порог обязан накрыть, %% (по умолчанию 95)")
    args = ap.parse_args()

    msgs, links = load(args.db)
    first, ts, by_kind = build_answers(msgs, links)
    newest = max(ts.values())

    urgent, plain = [], []          # задержки до первого ответа, часы
    by_how = {"жест": 0, "обращение": 0, "упоминание": 0}
    silent_urgent = silent_plain = 0
    young_cut = 6.0                 # записки моложе этого не судим: ответ мог не успеть прийти
    skipped_young = 0

    for mid, _role, t, prio, _b in msgs:
        age = (newest - ts[mid]).total_seconds() / 3600.0
        u = (prio or "").lower() in URGENT
        hit = first.get(mid)
        if hit:
            (urgent if u else plain).append(hit[0])
            by_how[hit[1]] += 1
        else:
            if age < young_cut:
                skipped_young += 1
                continue
            if u:
                silent_urgent += 1
            else:
                silent_plain += 1

    print("=" * 78)
    print("ЗАМЕР ПОРОГА ДЛЯ ВЫЧИСЛЯЕМОЙ СРОЧНОСТИ — ход Г из записки #3291")
    print("=" * 78)
    print(f"записок всего .............. {len(msgs)}")
    print(f"из них срочных ............. {sum(1 for m in msgs if (m[3] or '').lower() in URGENT)}")
    print(f"откликов найдено ........... {len(first)}"
          f"   (жест: {by_how['жест']} · обращение: {by_how['обращение']}"
          f" · упоминание: {by_how['упоминание']})")
    print(f"без отклика, срочных ....... {silent_urgent}")
    print(f"без отклика, обычных ....... {silent_plain}")
    print(f"моложе {young_cut:.0f} ч — не судим ....... {skipped_young}"
          "   (ответ мог просто не успеть прийти)")

    if not urgent:
        print("\n⛔ Срочных записок с найденным откликом НЕТ — порог назвать не из чего.")
        return 1

    # ── ТРИ ПОЛОСЫ: узкая (жест) · средняя (жест+обращение) · широкая (любое) ──
    urg_ids = [m[0] for m in msgs if (m[3] or "").lower() in URGENT]
    band = {"узкая": 0, "средняя": 0, "широкая": 0}
    for mid in urg_ids:
        kinds = by_kind.get(mid, {})
        if "жест" in kinds:
            band["узкая"] += 1
        if "жест" in kinds or "обращение" in kinds:
            band["средняя"] += 1
        if kinds:
            band["широкая"] += 1
    tot = len(urg_ids) or 1
    print()
    print("-" * 78)
    print("СКОЛЬКО СРОЧНЫХ ВООБЩЕ ПОЛУЧИЛИ ОТКЛИК — по трём определениям слова «ответ»")
    print("-" * 78)
    print(f"узкая  (только проставленная связь) ....... {band['узкая']:4}"
          f"  {100.0*band['узкая']/tot:5.1f}%   нижняя граница, сомнений нет")
    print(f"средняя (связь + ссылка ВНЕ цитаты,")
    print(f"         и автор вопроса назван в ответе) . {band['средняя']:4}"
          f"  {100.0*band['средняя']/tot:5.1f}%   👈 это разговор, а не упоминание")
    print(f"широкая (любое «#N», включая цитаты) ...... {band['широкая']:4}"
          f"  {100.0*band['широкая']/tot:5.1f}%   верхняя граница, завышает")
    print(f"без отклика даже по широкой ............... {tot - band['широкая']:4}"
          f"  {100.0*(tot-band['широкая'])/tot:5.1f}%")

    print()
    print("-" * 78)
    print("КОГДА ПРИХОДИТ ПЕРВЫЙ ОТВЕТ (часы от записки), доля состоявшихся ответов")
    print("-" * 78)
    print(f"{'доля':>6} | {'срочные':>12} | {'обычные':>12}")
    for p in (50, 75, 90, 95, 99, 100):
        a, b = percentile(urgent, p), percentile(plain, p)
        bs = f"{b:10.1f} ч" if b is not None else "         —"
        print(f"{p:5}% | {a:10.1f} ч | {bs}")

    thr = percentile(urgent, args.cover)
    print()
    print("-" * 78)
    print(f"ПОРОГ: {thr:.1f} ч — за это время приходит {args.cover:.0f}% всех ответов,")
    print("       которые срочная записка вообще получает.")
    print("-" * 78)

    late = [d for d in urgent if d > thr]
    print(f"цена порога: {len(late)} ответов из {len(urgent)} пришли ПОЗЖЕ него")
    print("             — эти записки к моменту ответа уже показывались бы обычными")
    if late:
        print(f"             самый поздний из них: {max(late):.0f} ч ({max(late)/24:.1f} сут)")

    # Округление до делений, которыми человек мыслит.
    for human in (6, 12, 24, 48, 72):
        if human >= thr:
            covered = 100.0 * sum(1 for d in urgent if d <= human) / len(urgent)
            print(f"\n👉 ближайшее человеческое деление: {human} ч — накрывает {covered:.1f}% ответов")
            break

    print()
    print("-" * 78)
    print("МЕНЯЕТ ЛИ ПОМЕТКА ПОВЕДЕНИЕ ВООБЩЕ (проверка предпосылки хода Г)")
    print("-" * 78)
    mu, mp = percentile(urgent, 50), percentile(plain, 50)
    print(f"половина ответов приходит: срочные {mu:.1f} ч · обычные "
          f"{mp:.1f} ч" if mp is not None else "обычные —")
    if mp is not None:
        diff = abs(mu - mp)
        print(f"разница .................... {diff:.2f} ч")
        if diff < 0.5:
            print("⚠️  Разницы НЕТ ⇒ пометка сегодня не ускоряет ответ НИ В КАКОМ возрасте.")
            print("    Порог выше — это НЕ «когда срочность перестаёт работать» (она не начинала),")
            print("    а «когда ответа уже можно не ждать». Называть его надо именно так.")

    print()
    print("⚖️ ПОТОЛОК: ответ прозой, без ссылки «#N» и без reply_to, этой программе не виден.")
    print("   Такие записки посчитаны как «без отклика» ⇒ порог выше показывает ВЕРХНЮЮ оценку.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
