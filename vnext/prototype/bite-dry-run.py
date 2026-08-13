#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: у пишущих инструментов есть ХОЛОСТОЙ ПРОГОН, и он действительно ничего не пишет.

ПОВОД (промах @PROTO 2026-08-13 10:29 UTC). Проверяя, что отказ `--md` объясняет причину,
я позвал `write-message.py` НА ЖИВОЙ БАЗЕ с настоящим телом. Отказ касался только md-половины —
записка ушла в ленту, мусор пришлось отменять.

🪤 И ПЕРВЫЙ РАЗБОР БЫЛ НЕВЕРЕН, что здесь важнее самой починки. Я объявил урок «испытывая
отказ, проверь, что отказ покрывает ВСЁ действие» — то есть обвинил механизм в частичном
отказе. Перемер показал: инструмент напечатал «✅ Твоя нота ЗАПИСАНА В БАЗУ — отклонена только
md-половина», и строка была в том самом выводе, который я читал. **Механизм сказал правду;
не дочитал я.** Обвинение механизма в собственной невнимательности — отдельный класс, и он
опаснее промаха: он ведёт чинить исправное.
⇒ Настоящий дефект другой и он механизируем: **увидеть поведение можно было только СОВЕРШИВ
его.** Вот это свойство и проверяется здесь.

⚖️ ЧТО ЭТА ПРИЁМКА НЕ ДОКАЗЫВАЕТ: что роль вспомнит про флаг. Не вспомнит — как не вспомнил
я. Холостой прогон убирает не ошибку, а НЕОБХОДИМОСТЬ ПИСАТЬ, ЧТОБЫ ПОСМОТРЕТЬ.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: испытывается КОПИЯ.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths
import mezo_target

LIVE_DB = mezo_paths.live_db()
ROLE = "ЗОНДХОЛОСТОЙ"
МЕТКА = "ЗОНД-ХОЛОСТОГО-ПРОГОНА"

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(tool: str, *args: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(mezo_target.script(tool)), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def count(db: Path, sql: str) -> int:
    con = sqlite3.connect(db)
    n = con.execute(sql).fetchone()[0]
    con.close()
    return n


def seed(db: Path) -> None:
    con = sqlite3.connect(db)
    con.execute("INSERT OR IGNORE INTO roles (role, lifecycle, lifecycle_by, zone, in_roster,"
                " created_at) VALUES (?,'alive','проба','приёмка',0,datetime('now'))", (ROLE,))
    con.execute("INSERT OR REPLACE INTO read_cursors (reader_role, last_read_id, updated_at)"
                " VALUES (?,(SELECT COALESCE(MAX(id),0) FROM messages),datetime('now'))", (ROLE,))
    con.commit()
    con.close()


def main() -> int:
    if not LIVE_DB.exists():
        print(f"🔴 НЕ ЗАПУСТИЛАСЬ: нет базы {LIVE_DB}")
        return 2
    for tool in ("write-message.py", "save-phoenix.py", "backlog.py", "dryrun.py"):
        if not mezo_target.script(tool).exists():
            print(f"🔴 НЕ ЗАПУСТИЛАСЬ: нет инструмента {tool}")
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.db"
        shutil.copy2(LIVE_DB, db)
        seed(db)
        нот = f"SELECT COUNT(*) FROM messages WHERE body_md LIKE '%{МЕТКА}%'"

        # ① ЗАПИСКА ВХОЛОСТУЮ — в ленте ноль. Главный случай: именно здесь я насорил.
        code, out = run("write-message.py", "--role", ROLE, "--db", str(db),
                        "--body", f"{МЕТКА} записка", "--dry-run")
        case("① записка вхолостую в ленту НЕ попала",
             count(db, нот) == 0, f"нот с меткой в базе: {count(db, нот)}")

        # ② ПОДПИСЬ ПЕЧАТАЕТСЯ ДВАЖДЫ — в начале и на выходе. Один раз мало: вывод длинный,
        #    шапка уезжает, читают хвост. Мой промах случился ровно на чтении хвоста.
        case("② подпись холостого прогона видна и в начале, и в конце",
             out.count("ХОЛОСТОЙ ПРОГОН") >= 2 and "НИЧЕГО НЕ ЗАПИСАНО" in out,
             f"вхождений подписи: {out.count('ХОЛОСТОЙ ПРОГОН')}")

        # ③ КОНТРОЛЬНАЯ ПАРА — БЕЗ ФЛАГА ЗАПИСЬ ПРОИСХОДИТ. Без этого случая приёмку прошёл бы
        #    инструмент, сломанный НАСОВСЕМ: «ничего не пишется» — тоже «ничего не пишется».
        run("write-message.py", "--role", ROLE, "--db", str(db), "--body", f"{МЕТКА} боевая")
        case("③ без флага записка ПИШЕТСЯ (иначе это не холостой ход, а поломка)",
             count(db, нот) == 1, f"нот с меткой: {count(db, нот)}")

        # ④ ПАМЯТЬ ВХОЛОСТУЮ — секция не тронута.
        было = count(db, f"SELECT COALESCE(LENGTH(body),0) FROM phoenix "
                         f"WHERE role='PROTO' AND section='state'")
        f = Path(tmp) / "s.md"
        f.write_text(f"{МЕТКА} подмена секции", encoding="utf-8")
        run("save-phoenix.py", "--role", "PROTO", "--section", "state",
            "--file", str(f), "--db", str(db), "--dry-run")
        стало = count(db, f"SELECT COALESCE(LENGTH(body),0) FROM phoenix "
                          f"WHERE role='PROTO' AND section='state'")
        case("④ память вхолостую не переписана", было == стало and было > 0,
             f"длина секции {было} → {стало}")

        # ⑤ КАРТОЧКА ВХОЛОСТУЮ — события не прибавилось.
        соб = "SELECT COUNT(*) FROM backlog_events"
        до = count(db, соб)
        run("backlog.py", "comment", "193", "--actor", "PROTO",
            "--body", f"{МЕТКА} комментарий", "--db", str(db), "--dry-run")
        case("⑤ комментарий вхолостую в историю карточки не попал",
             count(db, соб) == до, f"событий {до} → {count(db, соб)}")

        # ⑥ У ЧИТАЮЩИХ ПОДКОМАНД ФЛАГА НЕТ — И ЭТО НАМЕРЕННО. Флаг там, где нечего сохранять,
        #    учил бы, что он иногда бесполезен; а дубль на двух уровнях разбора аргументов
        #    МОЛЧА погасил бы защиту (подпарсер перезаписал бы значение верхнего на False).
        code, out = run("backlog.py", "list", "--role", "PROTO", "--db", str(db), "--dry-run")
        case("⑥ у читающей подкоманды флага нет, и отказ ГРОМКИЙ",
             code != 0 and "unrecognized" in out.lower(), f"код {code}")

    # ⑦ ЖИВАЯ БАЗА ЦЕЛА.
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    leaked = con.execute(f"SELECT COUNT(*) FROM messages WHERE body_md LIKE '%{МЕТКА}%'").fetchone()[0]
    con.close()
    case("⑦ живая база не тронута", leaked == 0, f"следов зонда в живой базе: {leaked}")

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 5 (①③④⑤⑥)")
    print("⚖️ ГРАНИЦА: проверено, что холостой ход ЕСТЬ и что он ЧЕСТЕН. Что роль про него")
    print("   вспомнит — не проверяется ничем: это не свойство инструмента. Он убирает")
    print("   не ошибку, а необходимость писать, чтобы посмотреть.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
