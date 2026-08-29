# -*- coding: utf-8 -*-
# SURFACES: rules
"""
guard-rule-expiry.py — НАСТУПЛЕНИЕ СРОКОВ ГОДНОСТИ ЗНАНИЯ (заход 2.3 плана «Роли
не забывают»). Поле условий у правил ЕСТЬ (expiry_kind/expiry_cond), а наступление
до 28.08 не спрашивал НИКТО: проверка ОСНОВАНИЙ зелёная, проверки НАСТУПЛЕНИЯ не было.
Предупреждение обязано нести срок годности — иначе «не верь X» учит не верить правде.

ЧТО СУДИТ (только active-правила):
  · until_event, условие несёт «карточка #N» → судьба карточки спрашивается У БАЗЫ:
    закрыта (done/dropped/failed) → 🔴 СОБЫТИЕ НАСТУПИЛО, правило пережило условие;
  · until_event / while_measured, условие несёт дату YYYY-MM-DD → дата прошла → 🔴;
  · условие НЕ машинное → 🟡 «не проверялось N дней» по возрасту последнего касания
    (rules.updated_at), N ≥ порога (по умолчанию 30);
  · while_measured без даты → тот же 🟡-возраст: замер, который не перемеряют, — не замер.
ЧЕГО НЕ СУДИТ (вслух): СМЫСЛ условия; forever и пустые условия (счёт печатается);
отозванные — история.

    python <КОНТУР>/vnext-tools/guard-rule-expiry.py [--days 30] [--db ...]
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

CARD = re.compile(r"(?:карточк|задач)\w*\s*#(\d+)", re.I)
# ⚠️ ГОЛАЯ ДАТА — НЕ ПРИЗНАК. Первый прогон судил любую дату как срок и дал 4 ложных
# красных из 4: в условиях даты стоят как ПРОИСХОЖДЕНИЕ замера («На 2026-08-08 доля …»),
# а не как срок. Судить по виду, а не по происхождению — оплаченный класс (20.08:
# 60 ложных у гарда путей; ложная находка дороже пропуска — перестают верить целиком).
DEADLINE = re.compile(r"(?:до|не позже)\s+(\d{4}-\d{2}-\d{2})", re.I)
MEASURED = re.compile(r"на\s+(\d{4}-\d{2}-\d{2})", re.I)
CLOSED = ("done", "dropped", "failed")


def judge(conn, days):
    red, yellow, skipped = [], [], {"forever": 0, "пусто": 0}
    rows = conn.execute(
        "SELECT rule_key, expiry_kind, expiry_cond, "
        "CAST(julianday('now') - julianday(updated_at) AS INTEGER) "
        "FROM rules WHERE status='active' ORDER BY rule_key").fetchall()
    for key, kind, cond, age in rows:
        if kind in (None, "", "forever"):
            skipped["forever" if kind == "forever" else "пусто"] += 1
            continue
        cond = cond or ""
        m = CARD.search(cond)
        if m:
            card = conn.execute("SELECT status FROM backlog WHERE id=?",
                                (int(m.group(1)),)).fetchone()
            if card is None:
                yellow.append((key, f"условие ссылается на карточку #{m.group(1)}, "
                                    f"которой НЕТ — условие не проверить"))
            elif card[0] in CLOSED:
                red.append((key, f"СОБЫТИЕ НАСТУПИЛО: карточка #{m.group(1)} → {card[0]}, "
                                 f"а правило живёт ({kind})"))
            continue
        m = DEADLINE.search(cond)
        if m:
            прошла = conn.execute("SELECT date('now') > ?", (m.group(1),)).fetchone()[0]
            if прошла:
                red.append((key, f"СРОК ПРОШЁЛ: «до {m.group(1)}» позади, "
                                 f"а правило живёт ({kind})"))
            continue
        m = MEASURED.search(cond)
        if m:
            зам_age = conn.execute("SELECT CAST(julianday('now') - julianday(?) AS INTEGER)",
                                   (m.group(1),)).fetchone()[0]
            if зам_age is not None and зам_age >= days:
                yellow.append((key, f"замер в условии от {m.group(1)} — ему {зам_age} дн, "
                                    f"перемерь ({kind})"))
            continue
        if age is not None and age >= days:
            yellow.append((key, f"условие не машинное и не проверялось {age} дн "
                                f"({kind}: {cond[:60]}) — перечитай рукой"))
    return red, yellow, skipped, len(rows)


def main():
    ap = argparse.ArgumentParser(description="Наступление сроков годности правил (2.3)")
    ap.add_argument("--db", default=None)
    ap.add_argument("--days", type=int, default=30,
                    help="порог «давно не проверялось» для немашинных условий")
    a = ap.parse_args()
    # live_db(), не resolve_db: скрипт живёт в vnext-tools, и корень «от расположения»
    # указал бы мимо базы (поймано первым же прогоном).
    db = Path(a.db) if a.db else mezo_paths.live_db()
    if not db.exists():
        sys.exit(f"⛔ СРОКИ НЕ ПРОВЕРЕНЫ: базы нет ({db}) — это не «чисто»")
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    red, yellow, skipped, total = judge(conn, a.days)
    conn.close()
    for key, why in red:
        print(f"🔴 {key}: {why}")
    if any("СОБЫТИЕ НАСТУПИЛО" in why or "которой НЕТ" in why for _, why in red + yellow):
        # ═══ Карточка #438 (второй живой случай, COORD 22:50 UTC): образец «карточка #N»
        # ловит номер и в тексте, ОБЪЯСНЯЮЩЕМ прежнюю ошибку, — цитата неотличима
        # от утверждения. Граница печатается В ВЫВОДЕ, а не живёт в карточке.
        print("   ⚖️ ГРАНИЦА: образец ловит «карточка #N» и в тексте-ЦИТАТЕ, объясняющем "
              "прежнюю ошибку условия. Упоминание без суда пишется «номер N», без решётки "
              "— сложившаяся форма контура")
    for key, why in yellow:
        print(f"🟡 {key}: {why}")
    print(f"{'🔴' if red else '✅'} сроки годности: 🔴 наступило {len(red)} · "
          f"🟡 давно не проверялось {len(yellow)} · судилось active {total} "
          f"(вечных {skipped['forever']}, без условия {skipped['пусто']} — их наступление "
          f"не определено по построению)")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
