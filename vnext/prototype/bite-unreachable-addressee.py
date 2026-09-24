# -*- coding: utf-8 -*-
"""bite-unreachable-addressee.py — приёмка предупреждения «адресат недостижим сигналом»
в write-message.py (план «убрать будильники», шаг 5; выбор владельца «Весь план», чат
OPSSRE ~09:44 UTC 24.09, записка #5312).

ЗАЧЕМ. Будильники сверок убраны: записку роли приносит сигнал-указатель в её чат. Сигнал
доходит только туда, где у роли записан живой номер сессии. Пишущий об этом не знал —
записка пролежала бы до ручного пробуждения молча. Теперь write-message.py сверяет номер
сессии каждого адресата с хранилищем сессий приложения (mezo_sessions, карточка #649) и
говорит вслух, до кого сигнал не дойдёт. Это ПРЕДУПРЕЖДЕНИЕ, а не отказ: записка ложится.

Случаи:
  ① живой адресат — предупреждения НЕТ (встречный: признак не горит всегда)
  ② сессия адресата в архиве — предупреждение с именем роли и словами «в архиве»
  ③ сессии адресата нет в хранилище — «не найдена в хранилище»
  ④ номер сессии не записан вовсе — «не записан»
  ⑤ записка ЗАПИСАНА несмотря на предупреждение: код 0, в ленте +1
  ⑥ хранилища нет — «НЕ сверена», а не молчание и не «недостижим»
  ⑦ владелец и сама пишущая роль не сверяются (у них нет чата-адресата сигнала)
  ⑧ подтверждение «OK #» стоит ПОСЛЕ предупреждения — правило чтения вывода не сдвинуто

Нарочные поломки (--break), каждая на своей копии write-message.py:
  drop-archive-check ... архивная сессия считается живой           → проваливается ②
  skip-missing ......... ненайденная сессия молча пропускается        → проваливается ③
  silent-no-store ...... без хранилища — молчание                     → проваливается ⑥

Живой базы и живого хранилища не касается: копия базы и подложное хранилище.
"""
import argparse
import json
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
import mezo_stand  # noqa: E402

BREAKS = {
    "drop-archive-check": ([("        elif record.archived:\n", "        elif False:\n")], {"②"}),
    "skip-missing": ([("        record = mezo_sessions.find_by_session_id(store, session_id)\n",
                       "        record = mezo_sessions.find_by_session_id(store, session_id)\n"
                       "        if record is None:\n            continue\n")], {"③"}),
    "silent-no-store": ([('        print(f"📡 достижимость адресатов сигналом НЕ сверена: {_store_note}")\n',
                          "        pass\n")], {"⑥"}),
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


def build_store(root: Path) -> Path:
    """Подложное хранилище в живом формате: одна живая сессия, одна в архиве."""
    leaf = root / "session-store" / "acct" / "proj"
    leaf.mkdir(parents=True)
    for name, archived in (("local_live", False), ("local_archived", True)):
        (leaf / f"{name}.json").write_text(json.dumps({
            "sessionId": name, "cliSessionId": f"transcript-{name}", "title": name,
            "cwd": str(root), "isArchived": archived, "lastActivityAt": 1000},
            ensure_ascii=False), encoding="utf-8")
    return root / "session-store"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS))
    a = ap.parse_args()

    stand = mezo_stand.new("bite-unreachable-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.snapshot_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")
    con = sqlite3.connect(str(db))
    # Подставные роли: заводятся в реестре КОПИИ (иначе write-message откажет по словарю
    # адресатов) — приёмка не зависит от того, какие роли живут в испытуемом контуре.
    for role, sid in (("ZZLIVE", "local_live"), ("ZZARCH", "local_archived"),
                      ("ZZGONE", "local_gone"), ("ZZNONE", None), ("ZZWRITER", "local_live")):
        con.execute("INSERT INTO roles (role, lifecycle) SELECT ?, 'alive' "
                    "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role=?)", (role, role))
        con.execute("DELETE FROM role_sessions WHERE role=?", (role,))
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source, "
                    "session_id) VALUES (?,?,datetime('now'),?,?,?)",
                    (role, f"{role} [000000]", "TEST", "self", sid))
    con.commit()
    con.close()

    tools = stand / "tools"
    tool = mezo_stand.copy_tool(TARGET, tools)
    # Помощник чтения хранилища едет рядом явно: копия соседей берёт импорты верхнего
    # уровня, а этот зовётся внутри функции.
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
    note.write_text("проба приёмки: адресат недостижим сигналом", encoding="utf-8")

    def write(to, store_path=store):
        r = subprocess.run(
            [sys.executable, str(tool), "--role", "ZZWRITER", "--db", str(db), "--to", to,
             "--file", str(note), "--again", f"приёмка {to}"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8",
                                     MEZO_SESSION_STORE=str(store_path)))
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def count_notes():
        c = sqlite3.connect(str(db))
        n = c.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        c.close()
        return n

    rc1, out1 = write("ZZLIVE")
    case("①", "живой адресат — предупреждения НЕТ",
         rc1 == 0 and "НЕДОСТИЖИМ" not in out1 and "НЕ сверена" not in out1 and "OK #" in out1,
         f"код {rc1}")

    before = count_notes()
    rc2, out2 = write("ZZARCH")
    after = count_notes()
    case("②", "сессия адресата в архиве — предупреждение с именем и «в архиве»",
         "НЕДОСТИЖИМ" in out2 and "ZZARCH" in out2 and "в архиве" in out2, f"код {rc2}")
    case("⑤", "записка ЗАПИСАНА несмотря на предупреждение: код 0, в ленте +1",
         rc2 == 0 and after == before + 1, f"код {rc2} · записок было {before}, стало {after}")
    rc3, out3 = write("ZZGONE")
    case("③", "сессии адресата нет в хранилище — «не найдена в хранилище»",
         rc3 == 0 and "НЕДОСТИЖИМ" in out3 and "не найдена в хранилище" in out3, f"код {rc3}")

    rc4, out4 = write("ZZNONE")
    case("④", "номер сессии не записан — «не записан»",
         rc4 == 0 and "НЕДОСТИЖИМ" in out4 and "не записан" in out4, f"код {rc4}")
    # ⚖️ У ⑧ свой вызов (не делит его со ②): иначе он проваливался бы от чужой поломки
    # и не различал ничего своего — поймано поломкой drop-archive-check.
    rc8, out8 = write("ZZNONE")
    warn_at = out8.find("НЕДОСТИЖИМ")
    ok_at = out8.find("OK #")
    case("⑧", "подтверждение «OK #» стоит ПОСЛЕ предупреждения",
         0 <= warn_at < ok_at, f"предупреждение на знаке {warn_at}, подтверждение на {ok_at}")

    rc6, out6 = write("ZZARCH", store_path=stand / "no-such-store")
    case("⑥", "хранилища нет — «НЕ сверена», а не молчание и не «недостижим»",
         rc6 == 0 and "НЕ сверена" in out6 and "НЕДОСТИЖИМ" not in out6, f"код {rc6}")

    rc7, out7 = write("ВЛАДЕЛЕЦ,ZZWRITER")
    case("⑦", "владелец и сама пишущая роль не сверяются",
         rc7 == 0 and "НЕДОСТИЖИМ" not in out7 and "НЕ сверена" not in out7, f"код {rc7}")

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
