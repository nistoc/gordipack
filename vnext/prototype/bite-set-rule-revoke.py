# -*- coding: utf-8 -*-
"""bite-set-rule-revoke.py — приёмка флагов set-rule.py --revoke и --annex.

ЗАЧЕМ.
  --revoke — слово владельца «Б», чат COORD 2026-09-24 10:35 UTC (записка #5330): «PROTO делает
  в инструменте правил флаг «снять правило», потом я снимаю правила штатно». До флага «снято»
  писалось только прямой записью в базу — без журнала правок, без зеркала, и поле статуса
  с текстом правила могли разойтись молча.
  --annex — этап 1 глобальной задачи (карточка #652; слово владельца 2026-09-24 10:31:14 UTC,
  чат PROTO): норма остаётся в тексте правила, разбор случаев — в приложении-файле.

Случаи (у каждого свой вызов и своё подставное правило — чужая поломка его не валит):
  ①  без --apply — холостой прогон: база не тронута, журнал не тронут
  ②  снятие: статус, час, кто, причина; пометка «⛔ ОТОЗВАНО» первой строкой, прежний текст ниже, версия +1
  ③  поле и текст отвечают одинаково общим признаком rule_status.py; вывод говорит «совпадают»
  ④  журнал правок: запись revoke_rule с прежним текстом целиком
  ⑤  зеркало пересобрано тем же вызовом и показывает правило снятым
  ⑥  без --reason — отказ, правило действует
  ⑦  без --revoked-by — отказ, правило действует
  ⑧  час не в форме «ГГГГ-ММ-ДД ЧЧ:ММ UTC» — отказ, правило действует
  ⑨  повторное снятие — «уже снято», ни версия, ни журнал не меняются
  ⑩  неизвестный ключ — код 1, «нет»
  ⑪  текст уже несёт пометку, поле — нет: вторая пометка не ставится, поле сводится с текстом
  ⑫  --revoke вместе с --body — отказ, правило действует
  ⑬  --annex при приложении — код 0, текст приложения напечатан
  ⑭  --annex без приложения — код 3 и «приложения нет» (не то же, что «правила нет»)
  ⑮  --annex неизвестного ключа — код 1
  ⑯  --show называет приложение, когда оно есть
  ⑰  встречный к ⑯: без приложения строки о нём нет
  ⑱  --show снятого правила говорит «СНЯТО»
  ⑲  правило под замком владельца, пишет не владелец — предупреждение
  ⑳  база без поля статуса — отказ со ссылкой на шаг схемы
  ㉑  обычная правка текста по-прежнему пересобирает зеркало (общая функция не сломала старый путь)
  ㉒  раскладка контура-автора: приложение ищется в atlas.archs/.mezosync/rules-annex
  ㉓  без --revoked-at час ставится текущий UTC в нужной форме
  ㉔  --revoked-at записывается как дан

Нарочные поломки (--break; --porcha — прежний синоним), каждая на своей копии set-rule.py:
  skip-audit ............ снятие не пишет журнал                       → ④
  no-mirror ............. снятие не пересобирает зеркало                → ⑤
  no-reason-check ....... снятие без причины проходит                   → ⑥
  double-mark ........... пометка ставится поверх уже стоящей           → ⑪
  annex-missing-silent .. нет приложения — молчаливый код 0             → ⑭
  no-annex-hint ......... --show не называет приложение                 → ⑯
  legacy-ignored ........ раскладка контура-автора не учитывается       → ㉒

Живой базы не касается: копия базы (mezo_stand.snapshot_db), подставные правила zz-*,
инструменты — копиями в стенде, среда — mezo_stand.stand_env.
"""
import argparse
import importlib.util
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("set-rule.py")
print(f"⚖️ испытуется: {mezo_target.label()}")
sys.path.insert(0, str(mezo_paths.live_scripts()))
import mezo_stand  # noqa: E402

BREAKS = {
    "skip-audit": ([("    conn.execute(\n        \"INSERT INTO audit_log (actor_role, action, target, diff_md)"
                     " VALUES (?,?,?,?)\",\n        (args.actor, \"revoke_rule\", args.key,",
                     "    (lambda *a: None)(\n        \"INSERT INTO audit_log (actor_role, action, target,"
                     " diff_md) VALUES (?,?,?,?)\",\n        (args.actor, \"revoke_rule\", args.key,")],
                   {"④"}),
    "no-mirror": ([("    rebuild_mirror(args.db)\n    print(\"👉 Если правило",
                    "    print(\"👉 Если правило")], {"⑤"}),
    "no-reason-check": ([("((\"--reason      почему снято\", reason),",
                          "((\"--reason      почему снято\", \"есть\"),")], {"⑥"}),
    "double-mark": ([("    already_marked = RS.is_revoked_body(body)\n",
                      "    already_marked = False\n")], {"⑪"}),
    "annex-missing-silent": ([("        sys.exit(3)\n", "        return\n")], {"⑭"}),
    "no-annex-hint": ([("        if annex.is_file():\n", "        if False:\n")], {"⑯"}),
    "legacy-ignored": ([("    base = (legacy if legacy.is_dir() else root) / \"rules-annex\"",
                         "    base = root / \"rules-annex\"")], {"㉒"}),
}

OK = FAIL = 0
RED = []


def case(mark, name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), mark, name)
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1
        RED.append(mark)


TEST_RULES = {
    # ключ: (замок, текст). Текст несёт узнаваемую строку — по ней видно, что прежний текст цел.
    "zz-dry": ("coord", "ПРОБА: холостой прогон"),
    "zz-main": ("coord", "ПРОБА: главное снятие"),
    "zz-agree": ("coord", "ПРОБА: сверка поля и текста"),
    "zz-audit": ("coord", "ПРОБА: журнал правок"),
    "zz-mirror": ("coord", "ПРОБА: зеркало"),
    "zz-noreason": ("coord", "ПРОБА: без причины"),
    "zz-noby": ("coord", "ПРОБА: без решившего"),
    "zz-badtime": ("coord", "ПРОБА: неверный час"),
    "zz-premarked": ("coord", "⛔ ОТОЗВАНО 2026-01-01 00:00 UTC · решил: owner\nПРОБА: пометка уже стоит"),
    "zz-mixed": ("coord", "ПРОБА: вместе с --body"),
    "zz-annex": ("coord", "ПРОБА: есть приложение"),
    "zz-noannex": ("coord", "ПРОБА: нет приложения"),
    "zz-owner": ("owner", "ПРОБА: под замком владельца"),
    "zz-upd": ("coord", "ПРОБА: обычная правка"),
    "zz-time": ("coord", "ПРОБА: час по умолчанию"),
    "zz-at": ("coord", "ПРОБА: час дан"),
}
ANNEX_TEXT = "ПРИЛОЖЕНИЕ-ПРОБА: разбор случая из приёмки"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", "--porcha", dest="break_name", choices=sorted(BREAKS))
    a = ap.parse_args()

    stand = mezo_stand.new("bite-set-rule-revoke-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.snapshot_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")
    con = sqlite3.connect(str(db))
    for key, (lock, body) in TEST_RULES.items():
        con.execute("DELETE FROM rules WHERE rule_key=?", (key,))
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version, basis, authorized, "
                    "source_ref, expiry_kind, status) VALUES (?,?,?,1,?,?,?,?,'active')",
                    (key, body, lock, "проба приёмки", "coord", "приёмка", "forever"))
    con.commit()
    con.close()

    tools = stand / "tools"
    tool = mezo_stand.copy_tool(TARGET, tools)
    exporter = TARGET.parent / "export-rules.py"
    if not exporter.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: рядом с испытуемым нет export-rules.py ({exporter})")
    mezo_stand.copy_tool(exporter, tools)
    if a.break_name:
        text = tool.read_text(encoding="utf-8")
        for old, new in BREAKS[a.break_name][0]:
            if text.count(old) != 1:
                sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                         f"(образец найден {text.count(old)} раз)")
            text = text.replace(old, new)
        tool.write_text(text, encoding="utf-8")
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    def run(*args, db_path=db):
        r = subprocess.run([sys.executable, str(tool), "--db", str(db_path), *args],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def row(key):
        c = sqlite3.connect(str(db))
        r = c.execute("SELECT body, version, status, revoked_at, revoked_by, revoked_reason "
                      "FROM rules WHERE rule_key=?", (key,)).fetchone()
        c.close()
        return r

    def audit(key):
        c = sqlite3.connect(str(db))
        r = c.execute("SELECT action, diff_md FROM audit_log WHERE target=? ORDER BY id",
                      (key,)).fetchall()
        c.close()
        return r

    def revoke(key, *extra):
        return run("--key", key, "--revoke", "--revoked-by", "owner",
                   "--reason", "проба приёмки", *extra, "--apply")

    # Общий признак берётся из КОПИИ, приехавшей с испытуемым: сверяем тем, чем судит он сам.
    spec = importlib.util.spec_from_file_location("rule_status_under_test", tools / "rule_status.py")
    rs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rs)

    # ① холостой прогон
    before, audit_before = row("zz-dry"), len(audit("zz-dry"))
    rc, out = run("--key", "zz-dry", "--revoke", "--revoked-by", "owner", "--reason", "проба")
    case("①", "без --apply — холостой прогон: база и журнал не тронуты",
         rc == 0 and "[DRY-RUN]" in out and row("zz-dry") == before
         and len(audit("zz-dry")) == audit_before, f"код {rc}")

    # ② главное снятие
    rc, out = revoke("zz-main", "--revoked-at", "2026-09-24 10:35 UTC", "--source-ref", "записка #5330")
    r = row("zz-main")
    body = r[0] or ""
    case("②", "снятие: статус · час · кто · причина · пометка первой строкой · прежний текст ниже · версия +1",
         rc == 0 and r[2] == "revoked" and r[3] == "2026-09-24 10:35 UTC" and r[4] == "owner"
         and "проба приёмки" in (r[5] or "") and "записка #5330" in (r[5] or "")
         and body.startswith("⛔ ОТОЗВАНО 2026-09-24 10:35 UTC") and "ПРОБА: главное снятие" in body
         and r[1] == 2, f"код {rc} · статус {r[2]} · версия {r[1]} · первая строка «{body.splitlines()[0] if body else ''}»")

    # ③ сверка поля и текста общим признаком
    rc, out = revoke("zz-agree")
    r = row("zz-agree")
    by_field, _ = rs.revoked_of(r[0], r[2], True)
    by_text = rs.is_revoked_body(r[0])
    case("③", "поле и текст отвечают одинаково общим признаком; вывод говорит «совпадают»",
         rc == 0 and by_field and by_text and "совпадают" in out,
         f"код {rc} · поле {by_field} · текст {by_text}")

    # ④ журнал правок
    rc, out = revoke("zz-audit")
    rows = [x for x in audit("zz-audit") if x[0] == "revoke_rule"]
    case("④", "журнал правок: запись revoke_rule с прежним текстом целиком",
         rc == 0 and len(rows) == 1 and "--- БЫЛО ---\nПРОБА: журнал правок" in rows[0][1],
         f"код {rc} · записей revoke_rule {len(rows)}")

    # ⑤ зеркало
    mirror = container / ".mezosync" / "generated" / "sync.rules.md"
    if mirror.exists():
        mirror.unlink()
    rc, out = revoke("zz-mirror")
    mtext = mirror.read_text(encoding="utf-8") if mirror.exists() else ""
    case("⑤", "зеркало пересобрано тем же вызовом и показывает правило снятым",
         rc == 0 and "### ⛔ **ОТОЗВАНО** `zz-mirror`" in mtext,
         f"код {rc} · зеркало {'есть' if mirror.exists() else 'НЕТ'}")

    # ⑥ ⑦ ⑧ отказы
    rc, out = run("--key", "zz-noreason", "--revoke", "--revoked-by", "owner", "--apply")
    case("⑥", "без --reason — отказ, правило действует",
         rc == 2 and "НЕ СНЯТО" in out and row("zz-noreason")[2] == "active", f"код {rc}")
    rc, out = run("--key", "zz-noby", "--revoke", "--reason", "проба", "--apply")
    case("⑦", "без --revoked-by — отказ, правило действует",
         rc == 2 and "НЕ СНЯТО" in out and row("zz-noby")[2] == "active", f"код {rc}")
    rc, out = revoke("zz-badtime", "--revoked-at", "24.09 10:35")
    case("⑧", "час не в форме «ГГГГ-ММ-ДД ЧЧ:ММ UTC» — отказ, правило действует",
         rc == 2 and "--revoked-at" in out and row("zz-badtime")[2] == "active", f"код {rc}")

    # ⑨ повтор — на zz-main, снятом в ②; если ② провалился, снимаем здесь сами
    if row("zz-main")[2] != "revoked":
        revoke("zz-main")
    before, audit_before = row("zz-main"), len(audit("zz-main"))
    rc, out = revoke("zz-main")
    case("⑨", "повторное снятие — «уже снято», ни версия, ни журнал не меняются",
         rc == 0 and "уже снято" in out and row("zz-main") == before
         and len(audit("zz-main")) == audit_before, f"код {rc}")

    # ⑩ неизвестный ключ
    rc, out = revoke("zz-no-such-rule")
    case("⑩", "неизвестный ключ — код 1, «нет»", rc == 1 and "нет" in out, f"код {rc}")

    # ⑪ пометка уже стоит
    rc, out = revoke("zz-premarked")
    r = row("zz-premarked")
    marks = sum(1 for line in (r[0] or "").splitlines() if line.startswith("⛔ ОТОЗВАНО"))
    case("⑪", "текст уже несёт пометку: вторая не ставится, версия та же, поле сведено",
         rc == 0 and r[2] == "revoked" and marks == 1 and r[1] == 1,
         f"код {rc} · пометок {marks} · версия {r[1]} · статус {r[2]}")

    # ⑫ смешение с правкой текста
    rc, out = run("--key", "zz-mixed", "--revoke", "--revoked-by", "owner", "--reason", "проба",
                  "--body", "новый текст", "--apply")
    case("⑫", "--revoke вместе с --body — отказ, правило действует",
         rc == 2 and "не сочетается" in out and row("zz-mixed")[2] == "active", f"код {rc}")

    # ⑬–⑰ приложение (раскладка новорождённого контура: рядом с базой)
    annex_dir = container / ".mezosync" / "rules-annex"
    annex_dir.mkdir(parents=True, exist_ok=True)
    (annex_dir / "zz-annex.md").write_text(ANNEX_TEXT, encoding="utf-8")
    rc, out = run("--key", "zz-annex", "--annex")
    case("⑬", "--annex при приложении — код 0, текст приложения напечатан",
         rc == 0 and ANNEX_TEXT in out, f"код {rc}")
    rc, out = run("--key", "zz-noannex", "--annex")
    case("⑭", "--annex без приложения — код 3 и «приложения нет»",
         rc == 3 and "приложения нет" in out, f"код {rc}")
    rc, out = run("--key", "zz-no-such-rule", "--annex")
    case("⑮", "--annex неизвестного ключа — код 1", rc == 1 and "нет" in out, f"код {rc}")
    rc, out = run("--key", "zz-annex", "--show")
    case("⑯", "--show называет приложение, когда оно есть",
         rc == 0 and "--key zz-annex --annex" in out, f"код {rc}")
    rc, out = run("--key", "zz-noannex", "--show")
    case("⑰", "встречный к ⑯: без приложения строки о нём нет",
         rc == 0 and "--annex" not in out and "ПРОБА: нет приложения" in out, f"код {rc}")

    # ⑱ --show снятого правила
    if row("zz-agree")[2] != "revoked":
        revoke("zz-agree")
    rc, out = run("--key", "zz-agree", "--show")
    case("⑱", "--show снятого правила говорит «СНЯТО»", rc == 0 and "СНЯТО" in out, f"код {rc}")

    # ⑲ замок владельца
    rc, out = run("--key", "zz-owner", "--revoke", "--revoked-by", "coord", "--reason", "проба")
    case("⑲", "правило под замком владельца, пишет не владелец — предупреждение",
         rc == 0 and "ЗАЛОЧЕНО ВЛАДЕЛЬЦЕМ" in out and row("zz-owner")[2] == "active", f"код {rc}")

    # ⑳ база без поля статуса
    bare = stand / "bare.db"
    c = sqlite3.connect(str(bare))
    c.execute("CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT UNIQUE, body TEXT, "
              "locked_by TEXT, version INTEGER, basis TEXT, authorized TEXT, source_ref TEXT, "
              "expiry_kind TEXT, expiry_cond TEXT)")
    c.execute("INSERT INTO rules (rule_key, body, locked_by, version) VALUES ('zz-bare','ПРОБА','coord',1)")
    c.commit()
    c.close()
    rc, out = run("--key", "zz-bare", "--revoke", "--revoked-by", "owner", "--reason", "проба",
                  "--apply", db_path=bare)
    c = sqlite3.connect(str(bare))
    bare_body = c.execute("SELECT body FROM rules WHERE rule_key='zz-bare'").fetchone()[0]
    c.close()
    case("⑳", "база без поля статуса — отказ со ссылкой на шаг схемы, текст не тронут",
         rc != 0 and "нет поля статуса" in out and "20260810-rule-status-field.py" in out
         and bare_body == "ПРОБА", f"код {rc}")

    # ㉑ старый путь правки текста
    if mirror.exists():
        mirror.unlink()
    rc, out = run("--key", "zz-upd", "--body", "ПРОБА: обычная правка — новый текст", "--apply")
    mtext = mirror.read_text(encoding="utf-8") if mirror.exists() else ""
    case("㉑", "обычная правка текста по-прежнему пересобирает зеркало",
         rc == 0 and "ПРОБА: обычная правка — новый текст" in mtext and "🪞" in out,
         f"код {rc} · зеркало {'есть' if mirror.exists() else 'НЕТ'}")

    # ㉓ час по умолчанию · ㉔ час дан
    rc, out = revoke("zz-time")
    at = row("zz-time")[3] or ""
    fresh = False
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC", at):
        t = datetime.strptime(at, "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        fresh = abs((datetime.now(timezone.utc) - t).total_seconds()) < 300
    case("㉓", "без --revoked-at — текущий час UTC в нужной форме", rc == 0 and fresh,
         f"код {rc} · записано «{at}»")
    rc, out = revoke("zz-at", "--revoked-at", "2026-09-24 10:35:14 UTC")
    case("㉔", "--revoked-at записывается как дан",
         rc == 0 and row("zz-at")[3] == "2026-09-24 10:35:14 UTC", f"код {rc} · «{row('zz-at')[3]}»")

    # ㉒ раскладка контура-автора — последним: меняет, где ищется приложение
    legacy = container / "atlas.archs" / ".mezosync" / "rules-annex"
    legacy.mkdir(parents=True)
    (legacy / "zz-noannex.md").write_text("ПРИЛОЖЕНИЕ-АВТОРА", encoding="utf-8")
    rc, out = run("--key", "zz-noannex", "--annex")
    case("㉒", "раскладка контура-автора: приложение из atlas.archs/.mezosync/rules-annex",
         rc == 0 and "ПРИЛОЖЕНИЕ-АВТОРА" in out, f"код {rc}")

    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(RED) == expected
        print(f"{'✅' if exact else '🔴'} поломка «{a.break_name}»: провалились "
              f"{' '.join(RED) or 'никто'} · ждали {' '.join(sorted(expected))}")
        return mezo_stand.finish(0 if exact else 1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
