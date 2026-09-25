# -*- coding: utf-8 -*-
"""bite-send-ban-pause.py — приёмка паузы формы «запрет отправки» в проверке памяти на
устаревшие утверждения (sieve-role-memory.py), 2026-09-25.

ЗАЧЕМ. Словом владельца 2026-09-25 11:02:36 UTC (чат PROTO) отправка в GitLab снова только
по его слову — правило gitlab-push-frozen. Проверка памяти звала строки «push только по слову»
кандидатами на устаревание (основание формы — снятие запрета 08.08) и учила бы роль стирать
действующий запрет. Теперь форма молчит СЛОВОМ, пока правило действует в своде этой базы,
и судит снова, когда его снимут.

Случаи (стенд — копия базы контура; подставная роль BITESIEVE, в памяти строка
«право: push только по слову владельца»; правило в копии заводится заново для каждого случая,
поэтому приёмка идёт и в контуре, где этого правила не было):
  ①  правило СНЯТО — форма судит: строка названа кандидатом, паузы нет
  ②  правило ДЕЙСТВУЕТ — форма не судит, говорит «НЕ СУЖУ» с именем правила; строка не названа

Нарочная поломка (--break; --porcha — синоним), на своей копии sieve-role-memory.py:
  pause-ignored ... пауза не учитывается → ②

Живой базы не касается: копия (mezo_stand.snapshot_db), инструмент — копией в стенде, среда —
mezo_stand.stand_env; свод о паузе спрашивается у копии.
"""
import argparse
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

HERE = Path(__file__).resolve().parent
TARGET = HERE / "sieve-role-memory.py"
sys.path.insert(0, str(mezo_paths.live_scripts()))
import mezo_stand  # noqa: E402

ROLE = "BITESIEVE"
RULE = "gitlab-push-frozen"
LINE = "право: push только по слову владельца"
FORM = "запрет отправки"
BREAKS = {"pause-ignored": ([("        if label in paused:\n", "        if False:\n")], {"②"})}

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


def build_stand(break_name, revoked):
    """Стенд: копия базы с подставной ролью и правилом в нужном статусе; копия инструмента."""
    stand = mezo_stand.new("bite-send-ban-pause-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.snapshot_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")
    # общий помощник статуса правил — туда, где его ищет проверка памяти (скрипты контура стенда)
    mezo_stand.copy_tool(mezo_paths.live_scripts() / "rule_status.py",
                         container / ".mezosync" / "scripts")
    con = sqlite3.connect(str(db))
    con.execute("DELETE FROM phoenix WHERE role=?", (ROLE,))
    con.execute("INSERT INTO phoenix (role, section, body, saved_at) "
                "VALUES (?,?,?,datetime('now'))", (ROLE, "state", f"# ПРОБА\n{LINE}\n"))
    con.execute("DELETE FROM rules WHERE rule_key=?", (RULE,))
    if revoked:
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version, basis, authorized, "
                    "source_ref, expiry_kind, status, revoked_at, revoked_by, revoked_reason) "
                    "VALUES (?,?,?,1,?,?,?,?,'revoked',?,?,?)",
                    (RULE, "⛔ ОТОЗВАНО: проба", "owner", "проба приёмки", "owner", "приёмка",
                     "forever", "2026-09-25 00:00 UTC", "owner", "проба приёмки"))
    else:
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version, basis, authorized, "
                    "source_ref, expiry_kind, status) VALUES (?,?,?,1,?,?,?,?,'active')",
                    (RULE, "ПРОБА: запрет отправки в GitLab", "owner", "проба приёмки", "owner",
                     "приёмка", "forever"))
    con.commit()
    con.close()
    tool = mezo_stand.copy_tool(TARGET, stand / "tools")
    if break_name:
        text = tool.read_text(encoding="utf-8")
        for old, new in BREAKS[break_name][0]:
            if text.count(old) != 1:
                sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{break_name}» вложить некуда "
                         f"(образец найден {text.count(old)} раз)")
            text = text.replace(old, new)
        tool.write_text(text, encoding="utf-8")
    return container, db, tool


def run(break_name, revoked):
    container, db, tool = build_stand(break_name, revoked)
    r = subprocess.run([sys.executable, str(tool), "--db", str(db), "--role", ROLE],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", "--porcha", dest="break_name", choices=sorted(BREAKS))
    a = ap.parse_args()
    if a.break_name:
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    rc, out = run(a.break_name, revoked=True)
    case("①", "правило СНЯТО — форма судит: строка названа кандидатом",
         rc == 0 and f"── {FORM}" in out and LINE in out and f"⏸ {FORM}" not in out,
         f"код {rc} · пауза={f'⏸ {FORM}' in out} · судила={f'── {FORM}' in out}")
    rc, out = run(a.break_name, revoked=False)
    case("②", "правило ДЕЙСТВУЕТ — форма не судит и говорит «НЕ СУЖУ» с именем правила",
         rc == 0 and f"⏸ {FORM}" in out and RULE in out and f"── {FORM}" not in out
         and LINE not in out,
         f"код {rc} · пауза={f'⏸ {FORM}' in out} · судила={f'── {FORM}' in out}")

    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(RED) == expected
        print(f"{'✅' if exact else '🔴'} поломка «{a.break_name}»: провалились "
              f"{' '.join(sorted(RED)) or 'никто'} · ждали {' '.join(sorted(expected))}")
        return mezo_stand.finish(0 if exact else 1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
