# -*- coding: utf-8 -*-
r"""ПРИЁМКА обзора пробуждения (--wake) — карточка #258, вторая половина.

🩸 ЧЕМ ОПЛАЧЕНО (замер 26.08): пробуждение роли читало ТЕЛА всего долга. У @RCC это
4942 КБ ≈ 1.2 млн токенов — БОЛЬШЕ ЛЮБОГО ОКНА: пробуждение было невыполнимо, и роль
узнавала об этом, уже начав читать.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① обзор показывает ОБЕ половины: тела обращённого лично И указатель остального  РАЗЛИЧАЮЩИЙ
  ② отметка прочитанного НЕ двинута — обзор не есть чтение ленты                   РАЗЛИЧАЮЩИЙ
  ③ ключа подтверждения НЕ выдано: нечем случайно объявить ленту прочитанной        РАЗЛИЧАЮЩИЙ
  ④ обзор ДЕШЕВЛЕ тел на роли с долгом — числом, а не обещанием                     РАЗЛИЧАЮЩИЙ
  ⑤ ОБРАТНЫЙ ХОД: выключить вторую половину → указателя в выводе НЕТ                РАЗЛИЧАЮЩИЙ
  ⑥ КОНТРОЛЬ: обычное чтение телами ключ ВЫДАЁТ — значит ③ говорит о режиме,
    а не о том, что ключей не бывает вовсе                                          КОНТРОЛЬ

⛔ Живой базы НЕ ПИШЕТ: работает на ПОДСТАВНОЙ базе (схема живой без строк — этап Э6, карточка #680).
Долг ленты сажает сам (seed_debt): до Э6 роль с долгом и сам долг брались из ленты ЭТОГО контура.
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

HERE = pathlib.Path(__file__).resolve().parent
READER = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "read-messages.py"
LIVE = mezo_paths.live_db()
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def run_tool(script, *argv):
    r = subprocess.run([sys.executable, str(script), *argv], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def mark(db, role):
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    row = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?", (role,)).fetchone()
    con.close()
    return row[0] if row else None


def with_debt(db):
    """Роль, у которой долг больше сотни: на пустом долге мерить экономию нечего."""
    con = sqlite3.connect(f"file:{pathlib.Path(db).as_posix()}?mode=ro", uri=True)
    lines = con.execute(
        "SELECT c.reader_role, (SELECT COUNT(*) FROM messages m"
        " WHERE m.id > c.last_read_id"
        "  AND m.writer_role <> c.reader_role) AS n"
        " FROM read_cursors c ORDER BY n DESC LIMIT 1").fetchall()
    con.close()
    return lines[0] if lines else (None, 0)


# Свой долг ленты (Э6, карточка #680): роль-читатель ZZWAKE, писатель COORD. Записок 60 по ≈2 КБ —
# телами больше 50 000 байт (порог ④); лично ZZWAKE обращены 4 (первая половина обзора), прочие —
# без адресата (указатель второй половины).
WAKE_READER, WAKE_WRITER = "ZZWAKE", "COORD"
WAKE_NOTES, WAKE_PERSONAL = 60, (5, 20, 35, 50)


def seed_debt(db) -> None:
    mezo_stand.seed_roles(db, [WAKE_READER, WAKE_WRITER])
    con = sqlite3.connect(str(db))
    with con:
        for n in range(1, WAKE_NOTES + 1):
            body = (f"# записка подставной базы {n} — долг ленты для обзора пробуждения\n\n"
                    + "тело записки приёмки обзора пробуждения, строка для объёма. " * 18)
            mid = con.execute("INSERT INTO messages (writer_role, timestamp, body_md, tags, priority)"
                              " VALUES (?, datetime('2026-10-01 00:00:00', ?), ?, '[]', 'normal')",
                              (WAKE_WRITER, f"+{n} minutes", body)).lastrowid
            if n in WAKE_PERSONAL:
                con.execute("INSERT INTO message_addressee (message_id, role, kind, linked_by)"
                            " VALUES (?, ?, 'to', 'field')", (mid, WAKE_READER))
    con.close()


def main() -> int:
    ok = True
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-wake-"))
    try:
        db = d / "sand.db"
        mezo_stand.empty_db(LIVE, db)
        seed_debt(db)
        role, debt = with_debt(db)
        if not role or debt < 20:
            print(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: в подставной базе нет роли с долгом ≥20 (лучшая: "
                  f"{role} с {debt}). Молчать об этом нельзя — вышло бы зелёное")
            return 2

        before = mark(db, role)
        code, output = run_tool(READER, "--db", str(db), "--role", role, "--wake")
        after = mark(db, role)

        ok &= case("① обзор показывает ОБЕ половины: тела личного И указатель остального",
                   code == 0 and "ТЕЛА ОБРАЩЁННОГО ЛИЧНО" in output
                   and "УКАЗАТЕЛЬ ПО ВСЕМУ ОСТАЛЬНОМУ" in output and "📇 УКАЗАТЕЛЬ" in output,
                   f"код {code}; роль {role}, долг {debt}. Одна половина без другой — "
                   f"это не обзор: либо тела без охвата, либо охват без важного", differ=True)

        ok &= case("② отметка прочитанного НЕ двинута",
                   before == after,
                   f"было {before}, стало {after} — обзор не есть чтение ленты, и механизм "
                   f"не должен позволять спутать одно с другим", differ=True)

        ok &= case("③ ключа подтверждения НЕ выдано",
                   "--ack" not in output and "Токен разрезан" not in output,
                   "иначе роль погасила бы долг, увидев ЗАГОЛОВКИ: писавшим было бы "
                   "сказано «дошло» про тела, которых никто не читал", differ=True)

        _, bodies = run_tool(READER, "--db", str(db), "--role", role, "--limit", "500")
        a, b = len(bodies.encode("utf-8")), len(output.encode("utf-8"))
        ok &= case("④ обзор ДЕШЕВЛЕ тел на роли с долгом — числом",
                   b < a and a > 50000,
                   f"телами {a} байт, обзором {b} байт — экономия {100 * (1 - b / a):.0f} %. "
                   f"⚖️ на ПУСТОМ долге обзор дороже, и это названо в его замере", differ=True)

        # ⑤ ОБРАТНЫЙ ХОД: выключаем ВТОРУЮ половину обзора.
        intact = READER.read_text(encoding="utf-8")
        CHUNK = '("УКАЗАТЕЛЬ ПО ВСЕМУ ОСТАЛЬНОМУ ДОЛГУ", ["--index"])'
        if intact.count(CHUNK) != 1:
            ok &= case("⑤ ОБРАТНЫЙ ХОД: выключить вторую половину", False,
                       f"⛔ якорь второй половины найден {intact.count(CHUNK)} раз — "
                       f"ослабление НЕ состоялось, а молчание тут читалось бы как успех",
                       differ=True)
        else:
            weak = d / "читатель-слабый.py"
            weak.write_text(intact.replace(CHUNK, '("ВТОРАЯ ПОЛОВИНА ВЫКЛЮЧЕНА ПРИЁМКОЙ", [])'),
                              encoding="utf-8")
            import os
            env = dict(os.environ, PYTHONPATH=str(READER.parent))
            r5 = subprocess.run([sys.executable, str(weak), "--db", str(db),
                                 "--role", role, "--wake"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=300, env=env)
            weak_output = (r5.stdout or "") + (r5.stderr or "")
            tail = weak_output.strip().splitlines()
            ok &= case("⑤ ОБРАТНЫЙ ХОД: вторая половина выключена → указателя в выводе НЕТ",
                       "📇 УКАЗАТЕЛЬ" not in weak_output and "📇 УКАЗАТЕЛЬ" in output,
                       f"у ослабленного указателя нет, у целого есть — разница и есть "
                       f"вторая половина. Слабый сказал: "
                       f"{(tail[0][:70] if tail else '(молча)')}", differ=True)

        code6, output6 = run_tool(READER, "--db", str(db), "--role", role, "--limit", "3")
        ok &= case("⑥ КОНТРОЛЬ: обычное чтение телами ключ ВЫДАЁТ",
                   "--ack" in output6,
                   "без этого случая ③ мог бы зеленеть просто оттого, что ключей "
                   "не бывает вовсе — а он про РЕЖИМ, а не про механизм")
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print()
    print(f"{'✅ ОБЗОР ПРОБУЖДЕНИЯ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
