# -*- coding: utf-8 -*-
"""bite-dryrun-confirmation.py — приёмка: холостой прогон write-message.py НЕ говорит «записана»
(карточка #726).

ЗАЧЕМ. Проба PROTO 2026-10-18 21:29 UTC в свежем контуре: `write-message.py --dry-run` печатал
«⟨ХОЛОСТОЙ ПРОГОН ЗАВЕРШЁН⟩ НИЧЕГО НЕ ЗАПИСАНО», а следом — «Записка ЗАПИСАНА» (адресат недостижим
сигналом) и «OK #1»: номер из копии базы в памяти выглядел номером настоящей записки. Роль зовёт
холостой прогон, чтобы проверить предупреждение без следа в базе, — и получала обратное: «ушло,
на номер можно ссылаться».

Случаи:
  ① холостой, адресат недостижим сигналом — «Записка ЗАПИСАНА» нет, есть «НЕ записана»; записок +0
  ② холостой, адресат давно молчит — «ВСЁ РАВНО ЗАПИСАНА» нет, есть «НЕ записана»; записок +0
  ③ холостой, обычный адресат — строки «OK #» нет, есть «записка НЕ записана — в копии получила бы
     номер»; «НИЧЕГО НЕ ЗАПИСАНО» на месте; записок +0
  ④ ВСТРЕЧНЫЙ к ①: обычная отправка недостижимому — «Записка ЗАПИСАНА» и «OK #», записок +1
  ⑤ ВСТРЕЧНЫЙ к ②: обычная отправка молчащему — «ВСЁ РАВНО ЗАПИСАНА» и «OK #», записок +1
  ⑥ ВСТРЕЧНЫЙ к ③: обычная отправка обычному — «OK #», слов «НЕ записана» нет, записок +1
  ⑦ холостой с --poll и --ack — «heartbeat НЕ обновлён» и «НЕ подтверждён»
  ⑧ ВСТРЕЧНЫЙ к ⑦: обычный с --poll и --ack — «heartbeat обновлён» и «подтверждён ролью»

Нарочные поломки (--break), каждая на своей копии write-message.py:
  unreachable-text ... в холостом прогоне снова «Записка ЗАПИСАНА» у недостижимого → проваливается ①
  sleeping-text ...... снова «ВСЁ РАВНО ЗАПИСАНА» у молчащего                       → проваливается ②
  ok-line ............ строка «OK #» печатается и в холостом прогоне                 → проваливается ③
  dry-off ............ пометки холостого прогона нет вовсе                           → ① ② ③ ⑦

Живой базы и живого хранилища сессий не касается: подставная база (схема живой без строк) и
подложное хранилище. Испытуемый write-message.py — по MEZO_SCRIPTS_ROOT (mezo_target), по
умолчанию — установленный в контуре.
"""
import argparse
import json
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("write-message.py")
print(f"⚖️ испытуется: {mezo_target.label()}")
sys.path.insert(0, str(mezo_paths.live_scripts()))
# mezo_stand — из каталога самой приёмки, той же версии пакета; вставка снимается сразу.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
sys.path.pop(0)

BREAKS = {
    "unreachable-text": (
        [('            print("   Холостой прогон — записка НЕ записана. 👉 Отправив её, скажи '
          'владельцу, чей чат")\n',
          '            print("   Записка ЗАПИСАНА. 👉 Отправив её, скажи владельцу, чей чат")\n')],
        {"①"}),
    "sleeping-text": (
        [('            print("   берётся свежий из двух. Холостой прогон — записка НЕ записана; '
          'отправленную")\n',
          '            print("   берётся свежий из двух. Записка ВСЁ РАВНО ЗАПИСАНА; отправленную")\n')],
        {"②"}),
    "ok-line": ([("    if msg_id is not None and dry:\n", "    if False:\n")], {"③"}),
    "dry-off": ([("    dry = bool(args.dry_run)\n", "    dry = False\n")], {"①", "②", "③", "⑦"}),
}

WRITER = "ZZWRITER"
PLAIN = "ZZPLAIN"      # обычный адресат: свежая своя записка и свежая отметка прочтения, сессия жива
NOSIG = "ZZNOSIG"      # недостижим сигналом: номер сессии не записан; в остальном как обычный
QUIET = "ZZQUIET"      # давно молчит: ни своих записок, ни отметки прочтения; сессия жива

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


def build_store(root: Path) -> Path:
    """Подложное хранилище сессий в живом формате: одна живая сессия."""
    leaf = root / "session-store" / "acct" / "proj"
    leaf.mkdir(parents=True)
    (leaf / "local_live.json").write_text(json.dumps({
        "sessionId": "local_live", "cliSessionId": "transcript-local_live", "title": "local_live",
        "cwd": str(root), "isArchived": False, "lastActivityAt": 1000},
        ensure_ascii=False), encoding="utf-8")
    return root / "session-store"


def seed(db: Path) -> None:
    """Подставные роли и их следы — в КОПИИ: приёмка не зависит от ролей испытуемого контура."""
    con = sqlite3.connect(str(db))
    for role, sid in ((WRITER, "local_live"), (PLAIN, "local_live"), (NOSIG, None),
                      (QUIET, "local_live")):
        con.execute("INSERT INTO roles (role, lifecycle) SELECT ?, 'alive' "
                    "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role=?)", (role, role))
        con.execute("DELETE FROM role_sessions WHERE role=?", (role,))
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source, "
                    "session_id) VALUES (?,?,datetime('now'),?,?,?)",
                    (role, f"{role} [000000]", "TEST", "self", sid))
    # Свежие следы у обычного и у недостижимого: иначе оба попали бы ещё и в «давно молчит»,
    # и случай ① судил бы чужое предупреждение.
    for role in (PLAIN, NOSIG):
        con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority)"
                    " VALUES (?, datetime('now'), ?, '[]', 'normal')",
                    (role, f"посев приёмки #726: свежая записка роли {role}"))
        con.execute("INSERT INTO read_cursors (reader_role, updated_at) VALUES (?, datetime('now')) "
                    "ON CONFLICT(reader_role) DO UPDATE SET updated_at = excluded.updated_at",
                    (role,))
    con.commit()
    con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS))
    a = ap.parse_args()

    stand = mezo_stand.new("bite-dryrun-confirm-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.empty_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")
    seed(db)

    tools = stand / "tools"
    tool = mezo_stand.copy_tool(TARGET, tools)
    helper = TARGET.parent / "mezo_sessions.py"
    if not helper.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: рядом с испытуемым нет mezo_sessions.py ({helper})")
    shutil.copy2(helper, tools / "mezo_sessions.py")
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

    store = build_store(stand)
    note = stand / "note.md"
    note.write_text("проба приёмки #726: что печатает холостой прогон", encoding="utf-8")

    def write(to, dry, *extra):
        cmd = [sys.executable, str(tool), "--role", WRITER, "--db", str(db), "--to", to,
               "--file", str(note), "--again", f"приёмка #726 {to} {'холостой' if dry else 'обычный'}",
               *extra] + (["--dry-run"] if dry else [])
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8",
                                                    MEZO_SESSION_STORE=str(store)))
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def count_notes():
        c = sqlite3.connect(str(db))
        n = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        c.close()
        return n

    def ok_lines(out):
        return [ln for ln in out.splitlines() if ln.startswith("OK #")]

    # ① холостой, недостижимый
    n0 = count_notes()
    rc1, out1 = write(NOSIG, True)
    n1 = count_notes()
    case("①", "холостой, адресат недостижим сигналом — «Записка ЗАПИСАНА» нет, «НЕ записана» есть",
         rc1 == 0 and "НЕДОСТИЖИМ" in out1 and "Записка ЗАПИСАНА" not in out1
         and "Холостой прогон — записка НЕ записана" in out1 and n1 == n0,
         f"код {rc1} · записок {n0} → {n1}")

    # ② холостой, давно молчит
    rc2, out2 = write(QUIET, True)
    n2 = count_notes()
    case("②", "холостой, адресат давно молчит — «ВСЁ РАВНО ЗАПИСАНА» нет, «НЕ записана» есть",
         rc2 == 0 and "ПРИЗНАКОВ ЖИЗНИ" in out2 and "ВСЁ РАВНО ЗАПИСАНА" not in out2
         and "Холостой прогон — записка НЕ записана" in out2 and n2 == n1,
         f"код {rc2} · записок {n1} → {n2}")

    # ③ холостой, обычный
    rc3, out3 = write(PLAIN, True)
    n3 = count_notes()
    case("③", "холостой, обычный адресат — строки «OK #» нет, номер назван как номер копии",
         rc3 == 0 and not ok_lines(out3) and "НИЧЕГО НЕ ЗАПИСАНО" in out3
         and "записка НЕ записана — в копии получила бы номер" in out3
         and "ПРИЗНАКОВ ЖИЗНИ" not in out3 and "НЕДОСТИЖИМ" not in out3 and n3 == n2,
         f"код {rc3} · строк «OK #» {len(ok_lines(out3))} · записок {n2} → {n3}")

    # ④ обычный, недостижимый
    rc4, out4 = write(NOSIG, False)
    n4 = count_notes()
    case("④", "ВСТРЕЧНЫЙ к ①: обычная отправка недостижимому — «Записка ЗАПИСАНА» и «OK #», +1",
         rc4 == 0 and "Записка ЗАПИСАНА" in out4 and ok_lines(out4) and n4 == n3 + 1,
         f"код {rc4} · записок {n3} → {n4}")

    # ⑤ обычный, давно молчит
    rc5, out5 = write(QUIET, False)
    n5 = count_notes()
    case("⑤", "ВСТРЕЧНЫЙ к ②: обычная отправка молчащему — «ВСЁ РАВНО ЗАПИСАНА» и «OK #», +1",
         rc5 == 0 and "ВСЁ РАВНО ЗАПИСАНА" in out5 and ok_lines(out5) and n5 == n4 + 1,
         f"код {rc5} · записок {n4} → {n5}")

    # ⑥ обычный, обычный
    rc6, out6 = write(PLAIN, False)
    n6 = count_notes()
    m = re.search(r"^OK #(\d+)", out6, re.M)
    case("⑥", "ВСТРЕЧНЫЙ к ③: обычная отправка обычному — «OK #», слов «НЕ записана» нет, +1",
         rc6 == 0 and m is not None and "НЕ записана" not in out6 and n6 == n5 + 1,
         f"код {rc6} · записок {n5} → {n6}")
    ack_id = m.group(1) if m else "1"

    # ⑦ холостой с --poll и --ack
    rc7, out7 = write(PLAIN, True, "--poll", "проба приёмки #726", "--ack", ack_id)
    n7 = count_notes()
    case("⑦", "холостой с --poll и --ack — «heartbeat НЕ обновлён», «НЕ подтверждён»",
         rc7 == 0 and "heartbeat НЕ обновлён" in out7 and "НЕ подтверждён" in out7 and n7 == n6,
         f"код {rc7} · записок {n6} → {n7}")

    # ⑧ обычный с --poll и --ack
    rc8, out8 = write(PLAIN, False, "--poll", "проба приёмки #726", "--ack", ack_id)
    case("⑧", "ВСТРЕЧНЫЙ к ⑦: обычный с --poll и --ack — «heartbeat обновлён», «подтверждён ролью»",
         rc8 == 0 and "heartbeat обновлён" in out8 and f"подтверждён ролью {WRITER}" in out8,
         f"код {rc8}")

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
