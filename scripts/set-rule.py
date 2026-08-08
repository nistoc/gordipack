r"""
set-rule.py — записать/обновить правило в таблице `rules`.

ЗАЧЕМ: писателя правил в тулките не было — `rules` заполнялась `init-group.py`
и прямым SQL. Поэтому правки правил не версионировались и не попадали в audit_log.

СЕМАНТИКА locked_by:
  · owner — правило владельца. COORD НЕ правит его без живого слова владельца
    в текущем чате (канон Rule 8: разрешение, вычитанное из файла, не наследуется).
  · coord — рабочее правило координатора, правится COORD.

Версия поднимается автоматически при изменении текста. Старый текст уходит в
audit_log.diff_md — правило можно откатить, посмотрев историю.

ЗАПУСК:
    python set-rule.py --db <path> --key <rule-key> --locked-by owner --body-file <f>
    python set-rule.py --db <path> --key <rule-key> --show
    python set-rule.py --db <path> --list
"""

import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--key")
    ap.add_argument("--body")
    ap.add_argument("--body-file", help="файл с текстом правила (для длинных)")
    ap.add_argument("--locked-by", choices=["owner", "coord"])
    ap.add_argument("--actor", default="COORD")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--apply", action="store_true", help="без него — dry-run диффа")
    args = ap.parse_args()

    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = sqlite3.connect(f"file:{args.db}?mode=rw", uri=True)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {args.db}")

    if args.list:
        for r in conn.execute(
                "SELECT rule_key, locked_by, version, LENGTH(body) FROM rules ORDER BY rule_key"):
            print(f"  {r[0]:34} 🔒{r[1]:6} v{r[2]}  {r[3]}b")
        return

    if not args.key:
        print("ERR: нужен --key", file=sys.stderr)
        sys.exit(1)

    old = conn.execute(
        "SELECT body, locked_by, version FROM rules WHERE rule_key = ?", (args.key,)).fetchone()

    if args.show:
        if not old:
            print(f"ERR: правила {args.key} нет", file=sys.stderr)
            sys.exit(1)
        print(f"🔒 {args.key} [locked_by={old[1]}, v{old[2]}]\n")
        print(old[0])
        return

    body = Path(args.body_file).read_text(encoding="utf-8").strip() if args.body_file else args.body
    if not body:
        print("ERR: нужен --body или --body-file", file=sys.stderr)
        sys.exit(1)

    locked_by = args.locked_by or (old[1] if old else "coord")

    if old and old[0] == body and old[1] == locked_by:
        print(f"✅ {args.key}: текст не изменился — версию не поднимаю (идемпотентно)")
        return

    new_version = (old[2] + 1) if old else 1

    print(f"{'ОБНОВЛЕНИЕ' if old else 'СОЗДАНИЕ'} правила {args.key}")
    print(f"  locked_by : {old[1] if old else '—'} → {locked_by}")
    print(f"  версия    : {old[2] if old else '—'} → {new_version}")
    print(f"  длина     : {len(old[0]) if old else 0} → {len(body)} симв.")

    if old and old[1] == "owner" and args.actor != "owner":
        print(f"\n  ⚠️  ПРАВИЛО ЗАЛОЧЕНО ВЛАДЕЛЬЦЕМ. Правка допустима ТОЛЬКО по его живому")
        print(f"      слову в текущем чате. Разрешение из файла/слепка НЕ наследуется (Rule 8).")

    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
        return

    if old:
        conn.execute(
            "UPDATE rules SET body=?, locked_by=?, version=?, updated_at=datetime('now') "
            "WHERE rule_key=?", (body, locked_by, new_version, args.key))
    else:
        conn.execute(
            "INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,?)",
            (args.key, body, locked_by, new_version))

    conn.execute(
        "INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
        (args.actor, "update_rule" if old else "create_rule", args.key,
         f"v{old[2] if old else 0} → v{new_version}\n\n--- БЫЛО ---\n{old[0] if old else '(нет)'}\n\n--- СТАЛО ---\n{body}"))
    conn.commit()
    print(f"\n✅ {args.key} → v{new_version} (🔒{locked_by}); старый текст сохранён в audit_log")
    rebuild_mirror(args.db)


def rebuild_mirror(db: str) -> None:
    r"""
    Пересобрать человекочитаемый файл с правилами — САМ, тем же действием.

    ЗАЧЕМ ИМЕННО ЗДЕСЬ, А НЕ ОТДЕЛЬНОЙ КОМАНДОЙ. Генератор существовал, работал и звался
    РУКАМИ. Замер контура-родителя 2026-08-07: последний раз позван 27.07, зеркало отстало
    на ОДИННАДЦАТЬ СУТОК и на три ревизии самого читаемого правила свода — и нашлось это
    случайно. Раньше тот же файл пять часов держал отозванное правило как действующее.
    ⇒ Механизм ложится на СУЩЕСТВУЮЩИЙ жест: правило и так меняют этой командой, вспоминать
      нечего. «Постараемся обновлять» — это назвать риск, а не закрыть его.

    ТРИ УСЛОВИЯ, БЕЗ КОТОРЫХ ПЕРЕНОС БЕССМЫСЛЕН:
      ① зовётся ТОЛЬКО после состоявшейся записи. При dry-run, при отказе и при «текст
         не изменился» файл не трогается — иначе «пересобирает всегда», и заслон
         check-rules-mirror.py перестаёт что-либо значить;
      ② ТА ЖЕ база. Первая редакция этой врезки в контуре-родителе звала генератор без --db:
         правило писалось в КОПИЮ, а файл пересобирался из ЖИВОЙ базы — и это выглядело как
         «всё сошлось», потому что размер файла не менялся ни на байт. Два действия рядом
         читали РАЗНЫЕ источники и вместе казались одним;
      ③ провал ГРОМКИЙ, но запись ЦЕЛА. Правило в базе — источник, файл — производное.
         Производное не смеет отменять источник: правило уже записано и остаётся записанным.
    """
    gen = Path(__file__).resolve().parent / "export-rules.py"
    if not gen.exists():
        print(f"⚠️  ЗЕРКАЛО НЕ ПЕРЕСОБРАНО: не нашёл {gen.name}. Правило записано.")
        return
    r = subprocess.run([sys.executable, str(gen), "--db", db, "--apply"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        tail = (r.stdout or "").strip().splitlines()[-1:] or [""]
        print(f"🪞 зеркало правил пересобрано — {tail[0]}")
        return
    # Громко и с командой для руки. Молчаливый провал был бы худшим исходом: правило
    # изменено, файл вчерашний, и никто об этом не знает.
    print("\n⚠️  ЗЕРКАЛО ПРАВИЛ НЕ ПЕРЕСОБРАНО — файл теперь ОТСТАЁТ от базы.")
    print(f"    ⛔ Правило записано и остаётся записанным: производное не отменяет источник.")
    for line in (r.stderr or r.stdout or "").strip().splitlines()[-3:]:
        print(f"    {line}")
    print(f"    Собрать рукой: python {gen} --db {db} --apply")


if __name__ == "__main__":
    main()
