r"""
check-stale-urgency.py — СРОЧНОСТЬ ГОРИТ, А ВОПРОС УЖЕ ЗАКРЫТ.

ЗАЧЕМ. Пометка «срочно» ставится и не снимается никогда.
```
записок срочных ................ 547
из них ГОРЯТ ................... 546
старше недели и горят .......... 402
реакция на «срочно» и на обычное  8,1 и 8,8 минуты — пометка уже ничего не сортирует
```
⇒ Срочность, которая никогда не гаснет, перестаёт быть срочностью. Она не «немного шумит» —
она **ровно так же информативна, как её отсутствие**, и это замерено, а не предположено.

Слово владельца 2026-08-07 14:15 UTC: «даю добро на проверки для "гашение срочности"».
⛔ Гашение по КАЛЕНДАРЮ владелец отклонил ещё 06.08, и верно: чаты останавливаются на сутки,
срок погасил бы всё разом во время общей паузы. Гаснуть должно ПО ОТВЕТУ.

═══ 🪤 ПОПРАВКА ПРОТИВ СЕБЯ, БЕЗ КОТОРОЙ ЭТОТ ИНСТРУМЕНТ НЕ ПОНЯТЬ ═══
Утром я записал в план: «механизм внесён, ручка есть, погашена 1 записка из 537 — четвёртый
случай „сосуд есть, никто не зовёт"». **Это неверно.** Поле `resolved` и ручка `--resolves`
служат ДРУГОМУ: они помечают, что УТВЕРЖДЕНИЕ ОТМЕНЕНО (класс «отменённое живёт в ленте
наравне с действующим»). К срочности они отношения не имеют.
> **Я принял соседний сосуд за нужный, потому что имя подошло.**
Тот же класс, что и другая моя сегодняшняя ошибка: совпадение формы приняло себя за
совпадение смысла. ⇒ Механизма гашения срочности НЕ СУЩЕСТВУЕТ, и это не «не зовут»,
а «не построено». Диагноз другой — и лечение поэтому тоже другое.

═══ ЧТО ДЕЛАЕТ ЭТА ПРОВЕРКА ═══
Находит записки, помеченные срочными, у которых В ТРЕДЕ УЖЕ ЕСТЬ ОТВЕТ. На них механизм
«гаснет по ответу» сработал бы прямо сейчас. Это не гашение — проверка НИЧЕГО НЕ МЕНЯЕТ
в базе; она показывает размер и адресность беды, чтобы лечение строилось на числе.

═══ ⚖️ СВОЙ ПОТОЛОК ПЕЧАТАЕТСЯ ПРИ КАЖДОМ ПРОГОНЕ ═══
Проверка видит только те записки, у которых связь ответа с вопросом ПРОСТАВЛЕНА полем.
Ответы, оставшиеся прозой, ей не видны. Сегодня это 49 записок из 546 горящих.
⛔ Молчание по остальным 497 НЕ означает, что там всё в порядке, — означает, что сказать
нечего. Проверка, не называющая свой потолок, читается как полное покрытие.

ЗАПУСК: python check-stale-urgency.py [--days N] [--quiet]
ВЫХОД:  0 — горящих с ответом нет · 1 — есть
"""

import argparse
import sqlite3
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE = mezo_paths.live_db()
URGENT = ("high", "critical")


def connect(db: Path):
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    con.execute("PRAGMA query_only=ON")
    con.row_factory = sqlite3.Row
    return con


def find_answered(con, days: int):
    """Срочные, у которых в треде есть ответ, а пометка всё ещё горит."""
    return con.execute(
        "SELECT m.id, m.writer_role, m.timestamp, m.priority,"
        "       COUNT(t.message_id) AS answers,"
        "       MAX(a.timestamp) AS last_answer,"
        "       substr(m.body_md, 1, 120) AS head "
        # ⚡ Вид, а не живая таблица: срочная записка без ответа не перестаёт быть
        # долгом оттого, что ей исполнилось семь суток (карточка #538 шаг ③).
        "FROM messages_all m "
        "JOIN message_thread t ON t.reply_to = m.id "
        "JOIN messages_all a ON a.id = t.message_id "
        "WHERE m.priority IN (?, ?) AND (m.resolved IS NULL OR m.resolved = 0) "
        "  AND m.timestamp < datetime('now', ?) "
        "GROUP BY m.id ORDER BY answers DESC, m.id",
        (*URGENT, f"-{days} days")).fetchall()


def main() -> int:
    ap = argparse.ArgumentParser(description="срочность горит, а вопрос закрыт")
    ap.add_argument("--db", default=str(LIVE))
    ap.add_argument("--days", type=int, default=0,
                    help="учитывать записки старше N суток (0 — все)")
    ap.add_argument("--quiet", action="store_true")
    # 🪤 Усечение вывода — не косметика: приёмка читает НАПЕЧАТАННОЕ, и её образец,
    #    попав за двадцатую строку, выглядел как «проверка его не нашла». Находка была,
    #    а её не показали. ⇒ у усечения обязана быть ручка, иначе «показано» и «найдено»
    #    расходятся молча — тот же класс, что стоил контуру двадцати восьми записок.
    ap.add_argument("--all", action="store_true", help="печатать ВСЕ находки, без усечения")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"⛔ не нашёл базу: {db}")
        return 2
    con = connect(db)

    total = con.execute("SELECT COUNT(*) c FROM messages_all WHERE priority IN (?,?)",
                        URGENT).fetchone()["c"]
    burning = con.execute("SELECT COUNT(*) c FROM messages_all WHERE priority IN (?,?)"
                          " AND (resolved IS NULL OR resolved=0)", URGENT).fetchone()["c"]
    week = con.execute("SELECT COUNT(*) c FROM messages WHERE priority IN (?,?)"
                       " AND (resolved IS NULL OR resolved=0)"
                       " AND timestamp < datetime('now','-7 days')", URGENT).fetchone()["c"]
    rows = find_answered(con, args.days)

    if not args.quiet:
        print("ПРОВЕРКА: срочность горит, а вопрос уже закрыт")
        print(f"  срочных всего .......... {total}")
        print(f"  из них ГОРЯТ ........... {burning}")
        print(f"  горят дольше недели .... {week}")
        print(f"  из горящих ИМЕЮТ ОТВЕТ . {len(rows)}   ← на них механизм сработал бы\n")

    if rows:
        print(f"⚠️  ГОРЯЩИЕ СРОЧНЫЕ С ОТВЕТОМ В ТРЕДЕ — {len(rows)}")
        shown = rows if args.all else rows[:20]
        for r in shown:
            head = (r["head"] or "").strip().splitlines()[0][:64]
            print(f"   записка #{r['id']:<5} {r['writer_role']:7} {r['priority']:8}"
                  f" ответов {r['answers']}  ·  {r['timestamp'][:16]}")
            print(f"      {head}")
        if len(shown) < len(rows):
            print(f"   … показано {len(shown)} из {len(rows)} — остальные скрыты усечением,"
                  " а не отсутствуют. Весь список: --all")

    # ── ПОТОЛОК ПЕЧАТАЕТСЯ ВСЕГДА, А НЕ ТОЛЬКО КОГДА УДОБНО ────────────────
    blind = burning - len(rows)
    print(f"\n⚖️ ЧЕГО ЭТА ПРОВЕРКА НЕ ВИДИТ: ответы, оставшиеся ПРОЗОЙ, — {blind} записок"
          f" из {burning} горящих.")
    print("   Связь ответа с вопросом проставлена полем далеко не везде, а по прозе судить")
    print("   механически нельзя. Молчание по этим НЕ означает «там всё в порядке».")
    print("⛔ И проверка НИЧЕГО НЕ ГАСИТ: она читает базу и только. Гашение — изменение")
    print("   живых данных, оно делается отдельным решением и чужой рукой.")

    con.close()
    return 1 if rows else 0


if __name__ == "__main__":
    sys.exit(main())
