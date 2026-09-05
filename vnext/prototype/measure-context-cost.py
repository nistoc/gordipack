# -*- coding: utf-8 -*-
"""
measure-context-cost.py — ЦЕНА КООРДИНАЦИИ: сколько мезосинк стоит ролям в контексте и токенах.

Задача владельца 2026-07-26 09:05 UTC (дословно): *насколько размер синков, манера
синхронизации и работа механизмов заставляют коллег держать большой контекст и слать
много текста на инференс, и влияет ли это на скорость сжигания токенов.*

READ-ONLY по живой БД + чтение канона/CLAUDE.md. Ничего не мутирует.

⚠️ ЧЕСТНО ПРО ТОКЕНЫ. Токенизатор здесь не запускается — считаем СИМВОЛЫ и переводим
в токены коэффициентом. Для кириллицы с markdown коэффициент ≈ **2.5–3.5 симв/токен**
(кириллица дороже латиницы: слова режутся на 2–4 куска). Печатаем ДИАПАЗОН, а не одно
число, и называем коэффициент рядом — оценка, выданная за замер, это ровно тот класс,
который контур ловит весь день.

    python measure-context-cost.py
    python measure-context-cost.py --role STUD      # разбор одной роли
"""
import argparse
import re
import sqlite3
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_db()
CLAUDE_MD = Path(str(mezo_paths.container_root() / "CLAUDE.md"))
READ_PHOENIX = mezo_paths.live_scripts() / "read-phoenix.py"
LO, HI = 3.5, 2.5          # симв/токен: LO — оптимистично, HI — пессимистично
SPLIT = re.compile(r"\bcc\b|\bFYI\b|\bcc:", re.IGNORECASE)


def tok(chars):
    return f"{chars / LO:,.0f}–{chars / HI:,.0f}".replace(",", " ")


def head_of(body):
    for line in (body or "").splitlines():
        if line.strip():
            return line
    return ""


def addressed(body, role):
    """Роль в ШАПКЕ до маркера копии = адресовано; после = в копию; иначе — не названа.

    ⚠️ СРАВНЕНИЕ БЕЗ УЧЁТА РЕГИСТРА — и это не мелочь. Первый прогон дал у OPSSRE
    «0 из 1319 адресовано», хотя к нему обращаются в каждой второй ноте: в ленте пишут
    `@opssre` строчными, а роль в реестре — `OPSSRE`. Мерка, чувствительная к регистру,
    показала бы владельцу ЛОЖНЫЙ ноль. Ровно тот же класс расщепления регистра, который
    Э-В④ лечит CHECK'ом в схеме, — здесь он укусил ИЗМЕРИТЕЛЬ."""
    head = head_of(body).lower()
    r = role.lower()
    parts = SPLIT.split(head, maxsplit=1)
    to_part = parts[0]
    if f"@{r}" in to_part or re.search(rf"→[a-z/\s]*\b{re.escape(r)}\b", to_part):
        return "to"
    if f"@{r}" in (body or "").lower():
        return "cc"
    return "none"


def canon_size():
    """Что роль читает на пробуждении ПОМИМО своего слепка и ленты."""
    out = {}
    if CLAUDE_MD.exists():
        out["CLAUDE.md"] = len(CLAUDE_MD.read_text(encoding="utf-8", errors="replace"))
    if READ_PHOENIX.exists():
        src = READ_PHOENIX.read_text(encoding="utf-8", errors="replace")
        m = re.search(r'CANON\s*=\s*r?"""(.*?)"""', src, re.S)
        out["шапка канона (печатает read-phoenix)"] = len(m.group(1)) if m else 0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(LIVE))
    ap.add_argument("--role", default=None)
    a = ap.parse_args()
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)

    print("=" * 96)
    print("ЦЕНА КООРДИНАЦИИ — замер живого контура. Символы точны, токены — ОЦЕНКА "
          f"({LO}–{HI} симв/токен)")
    print("=" * 96)

    # ── 1. ЛЕНТА: размер и темп
    # ⚡ Вид: замер стоимости чтения ленты обязан видеть ВСЮ ленту, иначе перенос
    # покажет мнимое удешевление (карточка #538 шаг ③).
    notes = con.execute("SELECT id, writer_role, timestamp, body_md FROM messages_all").fetchall()
    sizes = sorted(len(b or "") for _, _, _, b in notes)
    total = sum(sizes)
    days = con.execute(
        "SELECT COUNT(DISTINCT substr(timestamp,1,10)) FROM messages_all").fetchone()[0]
    last24 = con.execute(
        "SELECT COUNT(*), SUM(LENGTH(body_md)) FROM messages "
        "WHERE timestamp > datetime('now','-1 day')").fetchone()
    print(f"\n① ЛЕНТА")
    print(f"   нот всего            {len(notes):>8}   объём {total:>10,} симв  "
          f"≈ {tok(total)} токенов".replace(",", " "))
    print(f"   средняя нота         {total // len(notes):>8} симв   медиана "
          f"{sizes[len(sizes)//2]:>6} симв   максимум {sizes[-1]:>6} симв")
    print(f"   дней жизни контура   {days:>8}   ⇒ в среднем "
          f"{len(notes)//max(days,1)} нот/сутки")
    print(f"   ЗА ПОСЛЕДНИЕ СУТКИ   {last24[0]:>8} нот   {last24[1]:>10,} симв  "
          f"≈ {tok(last24[1] or 0)} токенов".replace(",", " "))
    print(f"   ⇒ это ВХОД, который контур производит в сутки. Каждая роль, читающая ленту "
          f"целиком, платит за него.")

    # ── 2. ЧТО РОЛЬ ГЛОТАЕТ НА ПРОБУЖДЕНИИ
    print(f"\n② ЦЕНА ОДНОГО ПРОБУЖДЕНИЯ (по ролям)")
    canon = canon_size()
    canon_total = sum(canon.values())
    for k, v in canon.items():
        print(f"   {k:44} {v:>7,} симв".replace(",", " "))
    print(f"   {'ИТОГО постоянная часть (одинакова для всех)':44} {canon_total:>7,} симв  "
          f"≈ {tok(canon_total)} токенов".replace(",", " "))
    print()
    print(f"   {'роль':8} {'память':>8} {'долг ленты':>11} {'симв долга':>11} "
          f"{'ВСЕГО симв':>11} {'≈ токенов':>16}")
    rows = []
    for role, cur in con.execute("SELECT reader_role, last_read_id FROM read_cursors ORDER BY 1"):
        snap = con.execute("SELECT COALESCE(SUM(LENGTH(body)),0) FROM phoenix WHERE role=?",
                           (role,)).fetchone()[0]
        n, chars = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(body_md)),0) FROM messages WHERE id>?",
            (cur,)).fetchone()
        tot = snap + chars + canon_total
        rows.append((role, snap, n, chars, tot))
        print(f"   {role:8} {snap:>8,} {n:>11} {chars:>11,} {tot:>11,} {tok(tot):>16}"
              .replace(",", " "))
    worst = max(rows, key=lambda r: r[4])
    print(f"   ⇒ дороже всех пробуждается {worst[0]}: {worst[4]:,} симв ≈ {tok(worst[4])} токенов "
          f"ТОЛЬКО ЧТОБЫ НАЧАТЬ РАБОТАТЬ".replace(",", " "))

    # ── 3. ДОЛЯ ПОЛЕЗНОГО: адресовано лично против «в копию»
    print(f"\n③ ДОЛЯ АДРЕСОВАННОГО (из чего состоит прочитанное)")
    print(f"   {'роль':8} {'нот видит':>10} {'ЕМУ':>6} {'в копию':>8} {'не назван':>10} "
          f"{'доля ЕМУ':>9} {'симв мимо':>12}")
    for role, _ in [(r, 0) for r, in con.execute(
            "SELECT reader_role FROM read_cursors ORDER BY 1")]:
        cnt = {"to": 0, "cc": 0, "none": 0}
        miss = 0
        for _, w, _, b in notes:
            if w == role:
                continue
            k = addressed(b, role)
            cnt[k] += 1
            if k != "to":
                miss += len(b or "")
        seen = sum(cnt.values())
        print(f"   {role:8} {seen:>10} {cnt['to']:>6} {cnt['cc']:>8} {cnt['none']:>10} "
              f"{100*cnt['to']//max(seen,1):>8}% {miss:>12,}".replace(",", " "))
    print("   ⇒ «в копию» и «не назван» роль всё равно читает: правило требует читать ленту ЦЕЛИКОМ,")
    print("     потому что адресат живёт ПРОЗОЙ и отличить важное можно только прочитав.")

    # ── 4. РИТУАЛЬНЫЕ НАКЛАДНЫЕ
    print(f"\n④ НАКЛАДНЫЕ РАСХОДЫ ФОРМЫ")
    quoted = sum(1 for _, _, _, b in notes if re.search(r"#\d{3,4}", b or ""))
    qchars = sum(len(l) for _, _, _, b in notes for l in (b or "").splitlines()
                 if l.lstrip().startswith(">") or re.match(r"^\s*(Ты писал|Ты сказал|Ты в #)", l))
    ccall = sum(1 for _, _, _, b in notes if len(re.findall(r"@[A-Z]{3,6}", head_of(b))) >= 5)
    tables = sum(1 for _, _, _, b in notes if (b or "").count("|---") > 0)
    batches, = con.execute("SELECT COUNT(*) FROM read_batches").fetchone()
    print(f"   нот, ссылающихся на другие ноты   {quoted:>6} ({100*quoted//len(notes)} %) — "
          f"чтобы понять, надо поднять ещё одну")
    print(f"   символов прямого цитирования      {qchars:>6,}  ≈ {tok(qchars)} токенов "
          f"(текст, уже бывший в ленте)".replace(",", " "))
    print(f"   нот «в копию ≥5 ролям»            {ccall:>6} ({100*ccall//len(notes)} %)")
    print(f"   нот с таблицами                   {tables:>6} — плотнее прозы, но дороже в символах")
    print(f"   открытых батчей чтения            {batches:>6} — след разведочных вызовов; "
          f"R16 (26.07) их больше не плодит")

    # ── 5. ИТОГ ДЛЯ ВЛАДЕЛЬЦА
    print(f"\n⑤ ИТОГ")
    wake_avg = sum(r[4] for r in rows) // len(rows)
    day_all = (last24[1] or 0) * len(rows)
    print(f"   среднее пробуждение роли      {wake_avg:>10,} симв ≈ {tok(wake_avg)} токенов"
          .replace(",", " "))
    print(f"   если каждая из {len(rows)} ролей прочтёт суточную ленту целиком: "
          f"{day_all:>10,} симв ≈ {tok(day_all)} токенов/сутки ТОЛЬКО НА ЧТЕНИЕ ДРУГ ДРУГА"
          .replace(",", " "))
    print(f"   ⚠️ и это НИЖНЯЯ оценка: она не считает повторные чтения одного и того же в течение")
    print(f"      смены, вывод инструментов, тела правил и бэклога.")
    con.close()


if __name__ == "__main__":
    main()
