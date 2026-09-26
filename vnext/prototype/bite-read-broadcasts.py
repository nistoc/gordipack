# -*- coding: utf-8 -*-
r"""bite-read-broadcasts.py — приёмка ОДНОГО предиката подтверждения и снятых ролей
в read-broadcasts.py (карточка #644, предложение AIA 02).

🩸 ПОВОД (замер AIA на живой базе их контура, пакет d32e621 = нашему коду). В
read-broadcasts.py жили ДВА разных предиката: инбокс и «--ack» судят по пометке ALL
(is_broadcast), «--status» — по пометке CTA (is_cta). Записка с CTA, но БЕЗ ALL, —
законный случай («подтверди, но это личная просьба, не объявление всем») — не попадала
в инбокс ни одной роли, «--ack» отвечал «не объявление — пропуск», а «--status» печатал
«ждём: <все роли>» НАВСЕГДА: счётчик, который не может закрыться.

Второй экземпляр того же класса: круг ожидаемых в «--status» брался из read_cursors
целиком, включая роли, СНЯТЫЕ апоптозом (lifecycle='closed') — их курсор в базе остаётся
навсегда, и «ждём» держало имя роли, которая никогда не ответит.

ПРЕДЛОЖЕНИЕ: is_ackable(tags) = is_broadcast(tags) или is_cta(tags) — им судят инбокс
и «--ack»; «--status» по-прежнему считает призывы своим прежним предикатом (is_cta),
не шире. Источник снятия роли — НАШ: таблица `roles`, lifecycle='closed' (так у нас
сняты EYE и GRF) — модуль реестра ролей AIA не переносится.

СЛУЧАИ (различающий = приёмка обязана ответить ИНАЧЕ ДО и ПОСЛЕ правки):
  ① CTA БЕЗ ALL — инбокс её ПОКАЗЫВАЕТ (адресату, не автору)              РАЗЛИЧАЮЩИЙ
  ② CTA БЕЗ ALL — «--ack» её ПРИНИМАЕТ (не «не объявление — пропуск»)     РАЗЛИЧАЮЩИЙ
  ③ встречный: чистое FYI (ни ALL, ни CTA) — по-прежнему НЕ в инбоксе,
     «--ack» по-прежнему отказывает                                       РАЗЛИЧАЮЩИЙ
  ④ встречный: «--status» СВОЙ предикат не расширяет — FYI без CTA он
     не показывает и после правки (иначе предложение AIA прочитано шире,
     чем сказано)                                                         РАЗЛИЧАЮЩИЙ
  ⑤ снятая роль (roles.lifecycle='closed') ИСКЛЮЧЕНА из круга «ждём»,
     исключение НАЗВАНО словами                                           РАЗЛИЧАЮЩИЙ
  ⑥ встречный: живая роль остаётся в круге «ждём» как прежде               РАЗЛИЧАЮЩИЙ
  ⑦ встречный: базы БЕЗ таблицы roles — круг КАК ПРЕЖДЕ (со снятыми),
     печатается «неоткуда узнать»                                          РАЗЛИЧАЮЩИЙ

НАРОЧНЫЕ ПОЛОМКИ (--porcha):
  predicate    — is_ackable() откатить к одному is_broadcast() (беда AIA целиком назад)
  roles-scope  — круг «--status» вернуть БЕЗ исключения снятых ролей

⛔ Живой базы не касается: собственный временной стенд, база SQLite строится приёмкой.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand   # noqa: E402 — env закреплённый за стендом (карточка #613)
import mezo_target  # noqa: E402 — какую копию испытываем (карточка #148)

print(f"⚖️ испытуется: {mezo_target.label()}")
HERE = Path(__file__).resolve().parent
LIVE_TOOL = mezo_target.script("read-broadcasts.py")

CASES = DIFFER = PASSED = 0


def case(title, ok, detail="", differ=False):
    global CASES, DIFFER, PASSED
    CASES += 1
    DIFFER += bool(differ)
    PASSED += bool(ok)
    print(f"{'✅' if ok else '🔴'} {title}")
    if detail:
        print(f"   {detail}")
    return ok


BREAKS = {
    # 🩸 порча AIA 02 (карточка #644, предложение 02): is_ackable откатывается к
    #    одному is_broadcast — ровно беда AIA целиком (CTA без ALL снова не подтверждаем).
    "predicate": ("    return is_broadcast(tags_json) or is_cta(tags_json)",
                  "    return is_broadcast(tags_json)"),
    # 🩸 порча: круг «--status» возвращён БЕЗ исключения снятых ролей.
    "roles-scope": ("        closed = {r[0].upper() for r in conn.execute(\n"
                     "            \"SELECT role FROM roles WHERE lifecycle='closed'\")}\n"
                     "        roles = roles_all - closed\n",
                     "        closed = set()\n"
                     "        roles = roles_all\n"),
}


def build_stand(tool_dir: Path) -> Path:
    """Копия read-broadcasts.py + сосед mezo_paths.py в отдельном каталоге стенда."""
    tool_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LIVE_TOOL, tool_dir / "read-broadcasts.py")
    mezo_paths = HERE / "mezo_paths.py"
    shutil.copy2(mezo_paths, tool_dir / "mezo_paths.py")
    local_time = mezo_target.scripts_root() / "local_time.py"
    if local_time.exists():
        shutil.copy2(local_time, tool_dir / "local_time.py")
    return tool_dir / "read-broadcasts.py"


def make_db(path: Path, *, with_roles=True):
    con = sqlite3.connect(str(path))
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT,
            timestamp TEXT, body_md TEXT, tags TEXT, priority TEXT);
        CREATE VIEW messages_all AS SELECT * FROM messages;
        CREATE TABLE broadcast_acks (message_id INTEGER NOT NULL, role TEXT NOT NULL,
            acked_at TEXT NOT NULL DEFAULT (datetime('now')), PRIMARY KEY (message_id, role));
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER);
    """)
    if with_roles:
        con.execute("CREATE TABLE roles (role TEXT PRIMARY KEY, lifecycle TEXT)")
    con.commit()
    con.close()
    return con


def insert_msg(db: Path, writer, tags, body="тело"):
    con = sqlite3.connect(str(db))
    cur = con.execute(
        "INSERT INTO messages (writer_role, timestamp, body_md, tags, priority) "
        "VALUES (?, datetime('now'), ?, ?, 'normal')", (writer, body, tags))
    con.commit()
    mid = cur.lastrowid
    con.close()
    return mid


def run_tool(tool: Path, db: Path, stand: Path, *args):
    # env закреплён за стендом (карточка #613): read-broadcasts.py читает mezo_paths,
    # и без своей среды подпроцесс унаследовал бы MEZO_CONTAINER вызывающего целиком.
    r = subprocess.run([sys.executable, str(tool), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=mezo_stand.stand_env(stand))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=sorted(BREAKS), default=None,
                    help="нарочная поломка: откатить одну из двух правок предложения AIA 02")
    a = ap.parse_args()

    if not LIVE_TOOL.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: read-broadcasts.py не найден: {LIVE_TOOL}")

    stand = Path(tempfile.mkdtemp(prefix="bite-read-broadcasts-"))
    try:
        tool = build_stand(stand / "tool")
        if a.porcha:
            old, new = BREAKS[a.porcha]
            text = tool.read_text(encoding="utf-8")
            if old not in text:
                sys.exit(f"⛔ порчу «{a.porcha}» НЕ УДАЛОСЬ навести: образец не найден в коде")
            tool.write_text(text.replace(old, new, 1), encoding="utf-8")
            print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.porcha}» ВЗВЕДЕНА\n")

        # ── ①②: CTA БЕЗ ALL ──────────────────────────────────────────────
        db1 = stand / "s1.db"
        make_db(db1)
        con = sqlite3.connect(str(db1))
        for r in ("COORD", "CORE"):
            con.execute("INSERT INTO read_cursors VALUES (?, 0)", (r,))
        con.commit(); con.close()
        mid = insert_msg(db1, "COORD", '["CTA"]', "нужна сверка ветки перед push")

        code, out = run_tool(tool, db1, stand, "--role", "CORE")
        case("① CTA без ALL — инбокс ПОКАЗЫВАЕТ адресату",
             code == 0 and f"#{mid}" in out and "Нет непрочитанных" not in out,
             out.strip()[:200], differ=True)

        code, out = run_tool(tool, db1, stand, "--role", "CORE", "--ack", str(mid))
        case("② CTA без ALL — «--ack» ПРИНИМАЕТ (не «не объявление — пропуск»)",
             code == 0 and "не broadcast — пропуск" not in out and f"#{mid}" in out and "ACK" in out,
             out.strip()[:200], differ=True)

        # ── ③: встречный, чистое FYI (ни ALL, ни CTA) — по-прежнему НЕ подтверждаемо
        db3 = stand / "s3.db"
        make_db(db3)
        con = sqlite3.connect(str(db3))
        con.execute("INSERT INTO read_cursors VALUES ('CORE', 0)")
        con.commit(); con.close()
        mid3 = insert_msg(db3, "COORD", "[]", "просто заметка, не адресована")
        code, out = run_tool(tool, db3, stand, "--role", "CORE")
        case("③ встречный: чистое FYI (ни ALL, ни CTA) — по-прежнему НЕ в инбоксе",
             code == 0 and "Нет непрочитанных" in out,
             out.strip()[:150])
        code, out = run_tool(tool, db3, stand, "--role", "CORE", "--ack", str(mid3))
        case("③-бис встречный: «--ack» чистого FYI по-прежнему отказывает",
             code == 0 and "не broadcast — пропуск" in out,
             out.strip()[:150])

        # ── ④: встречный — «--status» СВОЙ предикат (is_cta) не расширяет.
        # Записка с ALL, но БЕЗ CTA, — объявление без призыва: «--status» о ней молчит
        # и ДО, и ПОСЛЕ правки (предложение говорит «--status перечисляет призывы
        # прежним предикатом», не «шире»).
        db4 = stand / "s4.db"
        make_db(db4)
        con = sqlite3.connect(str(db4))
        con.execute("INSERT INTO read_cursors VALUES ('CORE', 0)")
        con.commit(); con.close()
        insert_msg(db4, "COORD", '["ALL"]', "объявление без призыва")
        code, out = run_tool(tool, db4, stand, "--status")
        case("④ встречный: «--status» не расширился — ALL без CTA он по-прежнему не считает",
             code == 0 and "Нет CTA" in out,
             out.strip()[:150])

        # ── ⑤⑥: снятая роль исключена из круга «ждём», живая — остаётся ──
        db5 = stand / "s5.db"
        make_db(db5)
        con = sqlite3.connect(str(db5))
        for r in ("COORD", "CORE", "EYE"):
            con.execute("INSERT INTO read_cursors VALUES (?, 0)", (r,))
        con.execute("INSERT INTO roles VALUES ('COORD', 'alive')")
        con.execute("INSERT INTO roles VALUES ('CORE', 'alive')")
        con.execute("INSERT INTO roles VALUES ('EYE', 'closed')")
        con.commit(); con.close()
        insert_msg(db5, "COORD", '["CTA","ALL"]', "подтверди широкий призыв")
        code, out = run_tool(tool, db5, stand, "--status")
        wait_line = next((l for l in out.splitlines() if "ждём:" in l), "")
        excl_line = next((l for l in out.splitlines() if "исключен" in l), "")
        case("⑤ снятая роль EYE ИСКЛЮЧЕНА из «ждём», исключение названо",
             code == 0 and "EYE" not in wait_line and "EYE" in excl_line,
             f"строка ждём: {wait_line!r} · строка исключения: {excl_line!r}", differ=True)
        case("⑥ встречный: живая роль CORE остаётся в круге «ждём»",
             "CORE" in wait_line,
             f"строка ждём: {wait_line!r}")

        # ── ⑦: встречный — базы БЕЗ таблицы roles: круг КАК ПРЕЖДЕ + строка признания
        db7 = stand / "s7.db"
        make_db(db7, with_roles=False)
        con = sqlite3.connect(str(db7))
        for r in ("COORD", "CORE"):
            con.execute("INSERT INTO read_cursors VALUES (?, 0)", (r,))
        con.commit(); con.close()
        insert_msg(db7, "COORD", '["CTA","ALL"]', "подтверди")
        code, out = run_tool(tool, db7, stand, "--status")
        case("⑦ встречный: базы без таблицы roles — круг КАК ПРЕЖДЕ, «неоткуда узнать»",
             code == 0 and "CORE" in out and "неоткуда" in out,
             out.strip()[:250], differ=True)

        print()
        ok = PASSED == CASES
        print(f"{'✅ ПРИЁМКА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, "
              f"пройдено {PASSED}, различающих {DIFFER}")
        if a.porcha and not ok:
            print("✅ так и надо: под порчей случаи краснеют — они судят предмет, а не форму")
            return 0
        if a.porcha and ok:
            print("⚠️ ПОРЧА ВЗВЕДЕНА, А ВСЁ ПРОШЛО ПРИЁМКУ — случаи НЕ РАЗЛИЧАЮТ этот дефект")
            return 1
        return 0 if ok else 1
    finally:
        if a.porcha:
            print(f"📂 стенд сохранён: {stand}")
        else:
            shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
