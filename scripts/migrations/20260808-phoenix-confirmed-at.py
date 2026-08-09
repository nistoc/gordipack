#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПАМЯТЬ РОЛИ: РАЗДЕЛИТЬ «КОГДА ТЕКСТ МЕНЯЛСЯ» И «КОГДА РОЛЬ ЕГО ПОДТВЕРДИЛА».

СЛОВО ВЛАДЕЛЬЦА 2026-08-08 16:19 UTC — «вариант А», мера ③: сравнивать СОДЕРЖИМОЕ,
а не время.

🪤 ПОЧЕМУ ОДНОЙ ДАТЫ НЕ ХВАТАЕТ — ДВЕ ОШИБКИ СРАЗУ, И ОНИ ПРОТИВОПОЛОЖНЫ.
Сейчас у секции одна дата `saved_at`, и она отвечает на два РАЗНЫХ вопроса одновременно:

    ① «нажали сохранить, ничего не изменив» → дата обновилась, память выглядит СВЕЖЕЙ,
       хотя не менялась. Ровно так гасился сторож ⑥ (замер 07.08): достаточно было
       пересохранить вслепую;
    ② «текст не менялся, потому что он ВЕРЕН» → дата старая, память выглядит ПРОТУХШЕЙ,
       хотя роль её только что перечитала и подтвердила.

Одна дата не может быть верной в обоих случаях: ① требует не двигать её при пересохранении,
② требует двигать. ⇒ Вопросов два — значит и полей два:

    saved_at ....... когда СОДЕРЖИМОЕ последний раз ИЗМЕНИЛОСЬ (возраст текста)
    confirmed_at ... когда роль последний раз ПОДТВЕРДИЛА, что текст верен (возраст взгляда)

Тогда обе ошибки уходят по построению, а не по дисциплине: пересохранение вслепую не
трогает `saved_at`, а нетронутый верный текст не выглядит брошенным — у него свежий
`confirmed_at`.

⚖️ ГРАНИЦА, НАЗВАННАЯ ВСЛУХ: `confirmed_at` говорит, что роль СОХРАНЯЛА, а не что она
ПОДУМАЛА. Механизм не отличит осмысленное подтверждение от вызова по привычке. Он снимает
ложную свежесть и ложное протухание — но не заменяет чтения.

⛔ ДОБАВЛЯЕТ ТОЛЬКО КОЛОНКУ. Ни одной строки `phoenix` не переписывает по смыслу:
существующим секциям `confirmed_at` ставится равным их же `saved_at` — то есть «подтверждено
тогда же, когда написано», что для прошлого и есть правда.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema_journal import record_step  # noqa: E402

VERSION = "008-phoenix-confirmed-at"


def main() -> int:
    ap = argparse.ArgumentParser(description="phoenix: возраст текста ОТДЕЛЬНО от возраста взгляда")
    # R15a: путь резолвится от РАСПОЛОЖЕНИЯ скрипта, а не от рабочего каталога.
    # migrations/ → scripts/ → .mezosync/ ⇒ три шага вверх, а не два: ошибся на один
    # и получил «базы нет» вместо тихой записи не туда — здесь громко и повезло.
    ap.add_argument("--db", default=str(Path(__file__).resolve().parents[2] / "mezosync.db"))
    ap.add_argument("--apply", action="store_true",
                    help="ЗАПИСАТЬ. Без него — только замер, база не трогается")
    args = ap.parse_args()
    db = Path(args.db)
    if not db.exists():
        sys.exit(f"⛔ базы нет: {db}")

    conn = sqlite3.connect(str(db), timeout=10)
    have = {r[1] for r in conn.execute("PRAGMA table_info(phoenix)")}
    total = conn.execute("SELECT COUNT(*) FROM phoenix").fetchone()[0]

    print("=" * 74)
    print("ПАМЯТЬ РОЛИ: ВОЗРАСТ ТЕКСТА ≠ ВОЗРАСТ ВЗГЛЯДА")
    print("=" * 74)
    print(f"секций в phoenix ............... {total}")
    print(f"колонка confirmed_at .......... {'УЖЕ ЕСТЬ' if 'confirmed_at' in have else 'нет, будет добавлена'}")

    if not args.apply:
        print()
        print("🔍 ЗАМЕР, БАЗА НЕ ТРОНУТА. Записать — тем же вызовом с --apply.")
        conn.close()
        return 0

    # ⚠️ ЯВНЫЙ BEGIN ОБЯЗАТЕЛЕН ПЕРЕД ПРАВКОЙ СХЕМЫ (врезано 2026-08-09 по находке @PROTO,
    # записка #3474). Python-sqlite открывает неявную транзакцию только перед INSERT/UPDATE,
    # а DDL первым действием уходит В АВТОКОММИТ — и тогда «шаг и запись о нём в одной
    # транзакции» перестаёт быть правдой: откат стирал бы ЗАПИСЬ, оставляя изменённую схему.
    # 🎯 Форму чиню во ВСЕХ шагах, а не только в модуле: следующий шаг напишут, скопировав
    # соседний, и «правильный record_step рядом с неправильным вызовом» вернётся сам.
    conn.execute("BEGIN")
    if "confirmed_at" not in have:
        conn.execute("ALTER TABLE phoenix ADD COLUMN confirmed_at TEXT")
    # Для прошлого «подтверждено тогда же, когда написано» — это правда, а не догадка:
    # других сведений о том, когда роль в последний раз смотрела на секцию, у нас нет.
    filled = conn.execute(
        "UPDATE phoenix SET confirmed_at = saved_at WHERE confirmed_at IS NULL").rowcount

    # ⛔ Шаг записывает СЕБЯ, в той же транзакции. Иначе база снова начнёт отвечать
    #    о своём устройстве уверенно и неверно — это чинили 08.08 и повторять не будем.
    fp = record_step(conn, VERSION, "phoenix: confirmed_at — возраст взгляда отдельно от текста")
    conn.commit()

    after = {r[1] for r in conn.execute("PRAGMA table_info(phoenix)")}
    rows_after = conn.execute("SELECT COUNT(*) FROM phoenix").fetchone()[0]
    orphan = conn.execute("SELECT COUNT(*) FROM phoenix WHERE confirmed_at IS NULL").fetchone()[0]
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    steps = conn.execute("SELECT * FROM schema_version").fetchone()
    conn.close()

    print()
    print(f"колонка появилась ............. {'✅' if 'confirmed_at' in after else '🔴 НЕТ'}")
    print(f"секций было → стало ........... {total} → {rows_after}"
          f"   {'✅ НЕ ТРОНУТЫ' if total == rows_after else '🔴 ИЗМЕНИЛИСЬ'}")
    print(f"проставлено из saved_at ....... {filled}")
    print(f"осталось без подтверждения .... {orphan}   {'✅' if orphan == 0 else '🔴'}")
    print(f"целостность ................... {integrity}")
    print(f"журнал схемы .................. шаг {VERSION} записан, отпечаток {fp}")
    print(f"база о себе ................... {steps}")
    ok = total == rows_after and orphan == 0 and integrity == "ok" and "confirmed_at" in after
    print()
    print("✅ ЗАПИСАНО" if ok else "🔴 НЕ ПРОШЛО — откатывай из точки отката")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
