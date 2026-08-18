#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""share-rules — отдать соседнему контуру свежие тексты названных правил.

    python C:/guts/.atlas/.mezosync/scripts/share-rules.py --to tapas --keys note-format,ack-deadline
    python C:/guts/.atlas/.mezosync/scripts/share-rules.py --to tapas --keys ... --apply
    python C:/guts/.atlas/.mezosync/scripts/share-rules.py --to tapas --diff       # что у нас свежее

ЗАЧЕМ ИНСТРУМЕНТ, А НЕ РУКА. 18.08 перенос десяти правил соседу делался руками: пути к
инструментам приводились к его контуру, сверху ставилась расписка о происхождении, версия
поднималась. Работа воспроизводимая и потому обязана быть командой — рука повторит её иначе
и не вспомнит, что именно поменяла.

⚖️ ГРАНИЦЫ, названные заранее:
  · СОСЕД БЕРЁТСЯ ИЗ ЗАПИСИ О СВЯЗИ (cross_links), а не из аргумента-пути: вписанный путь
    протухает молча, а запись о связи — единственное место, где сосед объявлен;
  · переносятся ТОЛЬКО названные правила. Массовой отдачи «всё, что у нас есть» здесь нет
    намеренно: чужой свод — не наша зона, и перенос без запроса это не порядок, а захват;
  · без --apply ничего не пишется: печатается план и разница версий;
  · ⛔ правила, снятые у нас, НЕ переносятся: соседу нельзя отдавать то, чем мы сами
    не пользуемся. Он получит их как приказ, а у нас на них надгробие.
"""
from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

NEWLINE = chr(10)

HEAD_FMT = (
    "📦 ПЕРЕНЕСЕНО ИЗ КОНТУРА-ДОНОРА `{donor}` {when}.\n"
    "Имена ролей и номера записок внутри — ЕГО: это следы, по которым правило заведено, "
    "а не адреса, куда идти (в его ленту вы не ходите). Пути инструментов приведены "
    "к вашему контуру замером, а не переписаны на глаз.\n"
    "⚖️ Если текст расходится с тем, как устроено У ВАС, — верьте своему устройству и "
    "перепишите правило: перенос даёт опыт, а не власть.\n\n")


def neighbour(conn, name: str) -> pathlib.Path:
    row = conn.execute("SELECT target_db_path FROM cross_links WHERE target_group=?",
                       (name,)).fetchone()
    if not row:
        known = [r[0] for r in conn.execute("SELECT target_group FROM cross_links")]
        sys.exit(f"⛔ соседа «{name}» нет в записях о связи. Известны: {known or 'никого'}. "
                 f"Связь заводится bridge-groups.py, а не этим инструментом")
    p = pathlib.Path(row[0])
    if not p.exists():
        sys.exit(f"⛔ база соседа не найдена: {p}. Запись о связи есть, а базы нет — "
                 f"это НЕ «нечего переносить», это разошедшаяся запись")
    return p


def retarget(body: str, donor_root: pathlib.Path, their_root: pathlib.Path) -> str:
    a, b = str(donor_root), str(their_root)
    for x, y in ((a, b), (a.replace("\\", "/"), b.replace("\\", "/")),
                 (a.lower(), b.lower())):
        body = body.replace(x, y)
    return body


def main() -> int:
    ap = argparse.ArgumentParser(description="отдать соседу свежие тексты названных правил")
    ap.add_argument("--to", required=True, help="имя соседней группы из записи о связи")
    ap.add_argument("--keys", help="ключи правил через запятую")
    ap.add_argument("--diff", action="store_true", help="показать, где наш текст свежее")
    ap.add_argument("--apply", action="store_true", help="записать (без него — только план)")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    db = a.db or mezo_paths.live_db()
    ours = sqlite3.connect(str(db))
    donor = ours.execute("SELECT value FROM meta WHERE key='group_name'").fetchone()
    donor = donor[0] if donor else "неизвестный контур"
    their_db = neighbour(ours, a.to)
    theirs = sqlite3.connect(str(their_db))

    donor_root = mezo_paths.container_root(__file__)
    their_root = their_db.parent.parent

    mine = {r[0]: (r[1], r[2]) for r in ours.execute(
        "SELECT rule_key, body, locked_by FROM rules "
        "WHERE status IS NULL OR status != 'revoked'")}
    hers = {r[0]: r[1] for r in theirs.execute("SELECT rule_key, body FROM rules")}

    # ⚖️ Расписку о переносе при сличении СНИМАЕМ: иначе уже отданное правило вечно числится
    # «разошедшимся» — только потому, что мы сами приписали ему сверху три строки. Замер бы
    # завышал долг и толкал переносить второй раз то же самое.
    def bare(body: str) -> str:
        if body.startswith("📦 ПЕРЕНЕСЕНО ИЗ КОНТУРА-ДОНОРА"):
            head, _, rest = body.partition(NEWLINE * 2)
            return rest.strip()
        return body.strip()

    if a.diff:
        newer = [k for k in sorted(set(mine) & set(hers))
                 if bare(mine[k][0]) != bare(hers[k])]
        absent = sorted(set(mine) - set(hers))
        print(f"у соседа «{a.to}»: правил {len(hers)} · у нас живых {len(mine)}")
        print(f"текст расходится: {len(newer)} · нет вовсе: {len(absent)}")
        for k in newer:
            print(f"   ≠ {k:34} у него {len(hers[k]):6} знаков · у нас {len(mine[k][0]):6}")
        for k in absent:
            print(f"   + {k:34} нет вовсе")
        print("⚖️ Расхождение НЕ значит «у нас лучше»: короткий ранний текст бывает вернее "
              "разросшегося. Отдавать — по запросу и поимённо.")
        return 0

    if not a.keys:
        sys.exit("⛔ назови правила: --keys ключ1,ключ2 (или --diff, чтобы увидеть разницу)")

    when = ours.execute("SELECT strftime('%Y-%m-%d %H:%M', 'now')").fetchone()[0] + " UTC"
    keys = [k.strip() for k in a.keys.split(",") if k.strip()]
    plan, refused = [], []
    for k in keys:
        if k not in mine:
            row = ours.execute("SELECT status FROM rules WHERE rule_key=?", (k,)).fetchone()
            refused.append((k, "снято у нас — отдавать нельзя" if row else "у нас такого нет"))
            continue
        body = HEAD_FMT.format(donor=donor, when=when) + retarget(mine[k][0], donor_root, their_root)
        plan.append((k, body, mine[k][1], "обновится" if k in hers else "появится"))

    for k, why in refused:
        print(f"⛔ {k}: {why}")
    for k, _, _, what in plan:
        print(f"→ {k:34} {what} у «{a.to}»")
    if not a.apply:
        print(f"\n[ПЛАН] Ничего не записано. Для записи — флаг --apply. "
              f"Готово к переносу: {len(plan)}, отказано: {len(refused)}")
        return 0 if not refused else 1

    for k, body, locked, _ in plan:
        theirs.execute(
            "INSERT INTO rules (rule_key, body, locked_by, version, basis, authorized,"
            " source_ref, expiry_kind, status) VALUES (?,?,?,1,?,?,?,'forever','active')"
            " ON CONFLICT(rule_key) DO UPDATE SET body=excluded.body, basis=excluded.basis,"
            " source_ref=excluded.source_ref, version=rules.version+1, updated_at=datetime('now')",
            (k, body, locked, f"перенос из контура-донора {donor}", "owner",
             f"запрос соседа, перенос {when}"))
    theirs.commit()
    # 🪤 ОТКАЗ НЕ ДОЛЖЕН ВЫГЛЯДЕТЬ УСПЕХОМ. Проба 18.08: запрос на одно снятое у нас
    # правило проходил с кодом 0 и строкой «перенесено: 0» — вызывающий узнал бы об
    # отказе только глазами по выводу, а машина считала бы, что перенос состоялся.
    if not plan:
        print("")
        print(f"⛔ НЕ ПЕРЕНЕСЕНО НИЧЕГО: все {len(refused)} названных правил "
              f"отклонены (причины выше). Это НЕ «сосед уже всё имеет».")
        return 1
    print(f"\n✅ Перенесено правил: {len(plan)} → {their_db}")
    print("👉 ОБЯЗАТЕЛЬНЫЙ СЛЕДУЮЩИЙ ШАГ на их стороне: перегенерировать зеркало свода "
          "(export-rules.py --apply), иначе их же проверка покраснеет: в базе есть, в файле нет.")
    print("👉 И скажи им запиской, ЧТО именно приехало: правило, появившееся молча, роль "
          "прочитает как своё давнее и не перепроверит.")
    ours.close()
    theirs.close()
    return 1 if refused else 0


if __name__ == "__main__":
    sys.exit(main())
