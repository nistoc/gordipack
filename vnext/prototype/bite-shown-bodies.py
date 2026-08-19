#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-shown-bodies — приёмка: показанное тело записывается и вычитается из «не дошло».

ЗАЧЕМ. 19.08 12:52 UTC, найдено на себе. Роль PROTO прочитала ТЕЛАМИ все 11 записок,
где к ней обращались полем (отбор --to-me), и следующей командой прошла хвост заголовками.
Механизм объявил те же 11 непрочитанными и пообещал сказать об этом писавшим. Обе строки
честны по отдельности: отбор действительно не двигает отметку прочитанного, проход
действительно не читал тел. Ложным был ПРОБЕЛ МЕЖДУ НИМИ — показ тела нигде не записывался
и потому для второй команды не существовал.

⚖️ Дороже всего здесь не сама ошибка, а её адресат: неправда говорится ТРЕТЬЕМУ лицу
(писавшему), которое проверить её не может и переспросит по уже разобранному.

    python <КОНТУР>/vnext-tools/bite-shown-bodies.py
"""
from __future__ import annotations

import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def main() -> int:
    ok = True
    # Каталог группы ищется ПОДЪЁМОМ ПО ПРИЗНАКУ, а не угадыванием глубины:
    # у копии в публичном образце «два уровня вверх» указывают в пустоту,
    # и приёмка падала ещё до первого случая (замер 2026-08-19 16:34 UTC).
    live = mezo_paths.container_root(__file__) / ".mezosync"
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bite-shown-"))
    try:
        scripts = tmp / "scripts"
        shutil.copytree(live / "scripts", scripts)
        db = tmp / "mezosync.db"
        shutil.copy(live / "mezosync.db", db)
        reader = scripts / "read-messages.py"
        env = {**os.environ, "MEZO_ROLE": "PROTO"}

        def call(*args):
            r = subprocess.run([sys.executable, str(reader), "--db", str(db), "--role", "PROTO",
                                *args], capture_output=True, text=True, encoding="utf-8",
                               timeout=300, env=env)
            return r.returncode, (r.stdout or "") + (r.stderr or "")

        con = sqlite3.connect(db)
        # Чистый лист: отметки живого контура сюда не тянем — иначе испытывался бы
        # не механизм, а сегодняшняя история чтения роли.
        con.execute("DELETE FROM cursor_segments WHERE from_id = to_id")
        # Отматываем отметку прочитанного назад, чтобы в долге ОКАЗАЛИСЬ личные обращения.
        head = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
        first_personal = con.execute(
            "SELECT MIN(message_id) FROM message_addressee WHERE role='PROTO' AND kind='to'"
            " AND message_id > ?", (head - 80,)).fetchone()[0]
        con.execute("UPDATE read_cursors SET last_read_id = ? WHERE reader_role = 'PROTO'",
                    (first_personal - 1,))
        con.commit()
        было = con.execute("SELECT COUNT(*) FROM cursor_segments WHERE kind='read' AND from_id=to_id"
                           ).fetchone()[0]
        курсор_до = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role='PROTO'"
                                ).fetchone()[0]
        con.close()

        rc, out = call("--to-me")
        con = sqlite3.connect(db)
        стало = con.execute("SELECT COUNT(*) FROM cursor_segments WHERE kind='read' AND from_id=to_id"
                            ).fetchone()[0]
        курсор_после = con.execute(
            "SELECT last_read_id FROM read_cursors WHERE reader_role='PROTO'").fetchone()[0]
        con.close()
        ok &= case("① показ тела ЗАПИСЫВАЕТСЯ, а не исчезает вместе с выводом на экран",
                   стало > было and "ЗАПИСАНО" in out,
                   f"отметок было {было}, стало {стало}. До починки не записывалось НИЧЕГО, "
                   f"и вторая команда не могла узнать о первой", differ=True)
        ok &= case("② КОНТРОЛЬ: отбор по-прежнему НЕ двигает отметку прочитанного",
                   курсор_после == курсор_до,
                   f"отметка {курсор_до} → {курсор_после}. Это главный риск починки: сделай "
                   f"запись подтверждением чтения — и роль перескочит через всё, что "
                   f"в подмножество не попало, будучи уверенной, что дочитала", differ=True)

        rc, out2 = call("--to-me")
        con = sqlite3.connect(db)
        снова = con.execute("SELECT COUNT(*) FROM cursor_segments WHERE kind='read' AND from_id=to_id"
                            ).fetchone()[0]
        con.close()
        ok &= case("③ повторный показ не плодит отметок",
                   снова == стало,
                   f"{стало} → {снова}: иначе счёт «прочитано телами» рос бы от каждого "
                   f"взгляда и перегнал бы число записок", differ=True)

        rc, out3 = call("--index", "--pass-by-index", "--basis",
                        "проба приёмки: личные прочитаны телами, остальное чужих зон")
        ok &= case("④ проход заголовками ВЫЧИТАЕТ прочитанные телами",
                   "ТЕЛАМИ ранее" in out3 and "разрезан вокруг них" in out3,
                   "именно этой строки не было 19.08: механизм обещал сказать писавшим "
                   "«не дошло» про 11 записок, разобранных десятью минутами раньше",
                   differ=True)

        # ⑤ РАЗЛИЧАЮЩИЙ: записка, обращённая к роли и НЕ показанная телом, обязана остаться
        # в «не дошло». Иначе починка превратилась бы в глушение строки.
        con = sqlite3.connect(db)
        cur = con.execute("SELECT last_read_id FROM read_cursors WHERE reader_role='PROTO'"
                          ).fetchone()[0]
        mid = con.execute("SELECT MAX(id) FROM messages").fetchone()[0] + 1
        con.execute("INSERT INTO messages (id, writer_role, body_md, timestamp)"
                    " VALUES (?, 'CORE', 'проба: тело не показывалось', datetime('now'))", (mid,))
        con.execute("INSERT INTO message_addressee (message_id, role, kind)"
                    " VALUES (?, 'PROTO', 'to')", (mid,))
        con.commit()
        con.close()
        rc, out4 = call("--index", "--pass-by-index", "--basis",
                        "проба приёмки: контроль непоказанного тела")
        ok &= case("⑤ КОНТРОЛЬ: непоказанное тело остаётся объявленным как «не дошло»",
                   "их тела ты не читала" in out4,
                   f"добавлена записка #{mid} к роли, телом не показанная. Если бы починка "
                   f"гасила строку всегда, писавшие потеряли бы единственный признак того, "
                   f"что их работа не доехала", differ=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print((f"✅ ПОКАЗАННОЕ ТЕЛО — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}" if ok
           else f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
