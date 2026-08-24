#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-duplicate-note — приёмка отказа от одинаковых записок.

ЗАЧЕМ. Замер COORD 18.08 (записка #3635 ②): за один день ТРИ пары одинаковых записок
у ТРЁХ разных ролей — тела совпадали целиком, различалась только минута в подписи, которую
ставит сам механизм. Третья пара случилась через ТРИ МИНУТЫ после того, как против этого
завели правило: роль не помнит, отправила ли она уже, а ответ приходит не сразу. Правилом
класс не лечится — поэтому механизм.

    python C:/guts/.atlas/vnext-tools/bite-duplicate-note.py
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

CASES = DIFFER = 0
NL = chr(10)


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def send(scripts: pathlib.Path, db: pathlib.Path, body_file: pathlib.Path, *extra):
    r = subprocess.run([sys.executable, str(scripts / "write-message.py"), "--role", "PROTO",
                        "--db", str(db), "--file", str(body_file), *extra],
                       capture_output=True, text=True, encoding="utf-8", timeout=120,
                       env={**__import__("os").environ, "MEZO_ROLE": "PROTO",
                            "MEZO_LEASE_TEST": "1"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    # Каталог группы ищется ПОДЪЁМОМ ПО ПРИЗНАКУ, а не угадыванием глубины:
    # у копии в публичном образце «два уровня вверх» указывают в пустоту,
    # и приёмка падала ещё до первого случая (замер 2026-08-19 16:34 UTC).
    live = mezo_paths.container_root(__file__) / ".mezosync"
    tmp = mezo_stand.new("bite-dup-")
    try:
        scripts = tmp / "scripts"
        shutil.copytree(live / "scripts", scripts)
        db = tmp / "mezosync.db"
        shutil.copy(live / "mezosync.db", db)

        one = tmp / "one.md"
        one.write_text("тело записки для приёмки: отправляется дважды" + NL, encoding="utf-8")
        two = tmp / "two.md"
        two.write_text("другое тело — механизм мешать не должен" + NL, encoding="utf-8")

        rc1, _ = send(scripts, db, one)
        ok &= case("① первая записка уходит свободно", rc1 == 0,
                   f"код возврата {rc1} — механизм, мешающий ПЕРВОЙ отправке, бесполезен")

        rc2, out2 = send(scripts, db, one)
        ok &= case("② та же записка вторым разом ОТКЛОНЕНА и назван номер первой",
                   rc2 == 3 and "#" in out2 and "ОТМЕНЕНА" in out2,
                   f"код {rc2}; в отказе назван номер уже отправленной — роли нужно не «нельзя», "
                   f"а «вот она, смотри там»", differ=True)

        rc3, _ = send(scripts, db, two)
        ok &= case("③ ДРУГОЕ тело проходит — механизм не глушит ленту целиком", rc3 == 0,
                   f"код {rc3}; иначе лечение было бы хуже болезни", differ=True)

        rc4, _ = send(scripts, db, one, "--again", "проба: осознанный повтор")
        con = sqlite3.connect(db)
        last = con.execute("SELECT body_md FROM messages ORDER BY id DESC LIMIT 1").fetchone()[0]
        con.close()
        ok &= case("④ осознанный повтор проходит и ОБЪЯСНЯЕТ СЕБЯ первой строкой",
                   rc4 == 0 and last.lstrip().startswith("🔁 ПОВТОР"),
                   "повтор бывает нужен, но читающий обязан видеть, зачем ему читать дважды — "
                   "иначе он решит, что механизм сломан", differ=True)

        # ⑤ САМОЕ ВАЖНОЕ: сличение ПО ТЕЛУ БЕЗ ПОДПИСИ. Подпись ставит механизм, и у копий,
        # отправленных в соседние минуты, она разная — сличение «как есть» объявило бы их
        # разными записками, то есть было бы зелёным ровно в том случае, ради которого заведено.
        sys.path.insert(0, str(scripts))
        import importlib.util
        spec = importlib.util.spec_from_file_location("wm", scripts / "write-message.py")
        wm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wm)
        a = "текст записки" + NL + NL + "— PROTO 2026-08-18 12:52 UTC" + NL
        b = "текст записки" + NL + NL + "— PROTO 2026-08-18 12:53 UTC" + NL
        ok &= case("⑤ подпись времени не делает копию «другой запиской»",
                   wm._strip_signature(a) == wm._strip_signature(b),
                   "все три пары дублей за день различались ТОЛЬКО минутой подписи: сличение "
                   "с подписью пропустило бы каждую из них", differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print((f"✅ ОТКАЗ ОТ ДУБЛЕЙ — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}" if ok
           else f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
