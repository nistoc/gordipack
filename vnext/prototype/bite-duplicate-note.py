#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-duplicate-note — приёмка отказа от одинаковых записок.

ЗАЧЕМ. Замер COORD 18.08 (записка #3635 ②): за один день ТРИ пары одинаковых записок
у ТРЁХ разных ролей — тела совпадали целиком, различалась только минута в подписи, которую
ставит сам механизм. Третья пара случилась через ТРИ МИНУТЫ после того, как против этого
завели правило: роль не помнит, отправила ли она уже, а ответ приходит не сразу. Правилом
класс не лечится — поэтому механизм.

    python <КОНТУР>/vnext-tools/bite-duplicate-note.py
    python <КОНТУР>/vnext-tools/bite-duplicate-note.py --source-db <база>   # копия снимается с неё

ТРИ ИСХОДА (карточка #623): 0 — принято · 1 — не принято · 4 — НЕ СУЖУ: write-message.py
в копии базы закрыт действующим объявлением о правке у ДРУГОЙ роли. Приёмка шлёт записки
с MEZO_LEASE_TEST=1 (механизм объявлений судит и копию), и чужое объявление, приехавшее
с живой базой, давало отказ «В РАБОТЕ» (код 3) — провал читался как «отказ от дублей
сломан», а сломано не это: инструмент в руках у другой роли. Своё объявление (роль
отправителя PROTO) механизм пропускает — оно судится как прежде.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
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

# ВОЗВРАТ ПО КАРТОЧКЕ #623 (PROTO): отправитель записок в копию — одна константа на отправку
# и на отбор «своё/чужое объявление»; разведённые литералы разошлись бы молча.
SENDER_ROLE = "PROTO"
WATCHED_TOOL = "write-message.py"
# Код «не сужу» — не 0 (принято), не 1 (не принято), не 2 (ошибка вызова у argparse) и не 3
# (отказ самого механизма объявлений): каждый исход читается по коду без разбора текста.
NOT_JUDGED_EXIT = 4
# Дочерний прогон случая ⑥ зовёт эту же приёмку; без запрета он звал бы ⑥ снова и снова.
NO_SELFTEST_ENV = "BITE_DUP_NO_SELFTEST"


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def send(scripts: pathlib.Path, db: pathlib.Path, body_file: pathlib.Path, *extra):
    r = subprocess.run([sys.executable, str(scripts / "write-message.py"), "--role", SENDER_ROLE,
                        "--db", str(db), "--file", str(body_file), *extra],
                       capture_output=True, text=True, encoding="utf-8", timeout=120,
                       env={**os.environ, "MEZO_ROLE": SENDER_ROLE,
                            "MEZO_LEASE_TEST": "1"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def foreign_lease(scripts: pathlib.Path, db: pathlib.Path):
    """Действующее объявление о правке write-message.py у ДРУГОЙ роли в копии базы — или None.

    Отбор берётся у САМОГО механизма объявлений (lease._live из скопированных скриптов), а не
    своим запросом: приёмка и механизм обязаны одинаково понимать «действующее» (не снято,
    срок не вышел). И тем же порядком, что lease.check: есть своё объявление — отказа не будет,
    значит и «не сужу» не нужно, даже если рядом держится чужое.
    """
    spec = importlib.util.spec_from_file_location("lease_for_bite_dup", scripts / "lease.py")
    lease = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lease)
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        live = lease._live(con, WATCHED_TOOL)
    finally:
        con.close()
    if any((r[1] or "").upper() == SENDER_ROLE for r in live):
        return None
    return live[0] if live else None


def run_self(source_db: pathlib.Path):
    """Дочерний прогон этой же приёмки на копии, снятой с source_db (для случая ⑥)."""
    r = subprocess.run([sys.executable, str(pathlib.Path(__file__).resolve()),
                        "--source-db", str(source_db)],
                       capture_output=True, text=True, encoding="utf-8", timeout=300,
                       env={**os.environ, NO_SELFTEST_ENV: "1"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def with_lease(src: pathlib.Path, dst: pathlib.Path, role: str) -> pathlib.Path:
    """Копия src с ОДНИМ действующим объявлением о правке write-message.py у роли role;
    прочие действующие объявления в копии сняты — случай судит ровно подложенное."""
    mezo_stand.snapshot_db(src, dst)
    con = sqlite3.connect(dst)
    con.execute("UPDATE tool_leases SET released_at = datetime('now') WHERE released_at IS NULL")
    con.execute("INSERT INTO tool_leases (role, tools, reason, until_utc) "
                "VALUES (?, ?, ?, datetime('now', '+1 hour'))",
                (role, WATCHED_TOOL, "приёмка bite-duplicate-note.py, случай ⑥"))
    con.commit()
    con.close()
    return dst


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="приёмка отказа от одинаковых записок")
    ap.add_argument("--source-db", help="база, с которой снимается копия (по умолчанию — живая)")
    args = ap.parse_args(argv)
    ok = True
    # Каталог группы ищется ПОДЪЁМОМ ПО ПРИЗНАКУ, а не угадыванием глубины:
    # у копии в публичном образце «два уровня вверх» указывают в пустоту,
    # и приёмка падала ещё до первого случая (замер 2026-08-19 16:34 UTC).
    live = mezo_paths.container_root(__file__) / ".mezosync"
    source_db = pathlib.Path(args.source_db) if args.source_db else live / "mezosync.db"
    tmp = mezo_stand.new("bite-dup-")
    try:
        scripts = tmp / "scripts"
        shutil.copytree(live / "scripts", scripts)
        db = tmp / "mezosync.db"
        mezo_stand.snapshot_db(source_db, db)

        # ВОЗВРАТ ПО КАРТОЧКЕ #623: write-message.py в руках у другой роли — «не сужу»,
        # отдельным исходом, до первого случая. Судить чужую незаконченную правку значило бы
        # покрасить её автора (он гоняет приёмки под своим объявлением) или соседа — за чужое.
        holder = foreign_lease(scripts, db)
        if holder:
            lease_id, role, tools, reason, taken_at, until = holder
            print(f"⚪ НЕ СУЖУ: {WATCHED_TOOL} в работе у роли {role} (объявление #{lease_id}) "
                  f"до {until} UTC")
            print(f"   причина объявления: {reason}")
            print(f"   приёмка шлёт записки от имени {SENDER_ROLE}; под чужим объявлением "
                  f"механизм отказывает («В РАБОТЕ», код 3) — это занятость, а не поломка "
                  f"отказа от дублей")
            print(f"   повтори после снятия объявления: python "
                  f"{(live / 'scripts' / 'lease.py').as_posix()} status")
            print()
            print(f"⚪ ОТКАЗ ОТ ДУБЛЕЙ — НЕ СУЖУ (код {NOT_JUDGED_EXIT}) — ни один случай не судился")
            return NOT_JUDGED_EXIT

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
        spec = importlib.util.spec_from_file_location("wm", scripts / "write-message.py")
        wm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(wm)
        a = "текст записки" + NL + NL + "— PROTO 2026-08-18 12:52 UTC" + NL
        b = "текст записки" + NL + NL + "— PROTO 2026-08-18 12:53 UTC" + NL
        ok &= case("⑤ подпись времени не делает копию «другой запиской»",
                   wm._strip_signature(a) == wm._strip_signature(b),
                   "все три пары дублей за день различались ТОЛЬКО минутой подписи: сличение "
                   "с подписью пропустило бы каждую из них", differ=True)

        # ⑥ ВОЗВРАТ ПО КАРТОЧКЕ #623: ветка «не сужу» проверяется ЗДЕСЬ, на каждом прогоне, а не
        # только тем, у кого сейчас случилось чужое объявление. Две копии с ОДНИМ подложенным
        # объявлением: у чужой роли — дочерний прогон обязан сказать «не сужу» кодом 4 и не судить
        # ни одного случая; у своей роли (SENDER_ROLE) — судить как прежде и принять.
        if not os.environ.get(NO_SELFTEST_ENV):
            foreign_db = with_lease(source_db, tmp / "lease-foreign.db", "ZZLEASE")
            rc6f, out6f = run_self(foreign_db)
            ok &= case("⑥ под ЧУЖИМ действующим объявлением о правке write-message.py — «не сужу» "
                       "отдельным исходом, ни один случай не судился",
                       rc6f == NOT_JUDGED_EXIT and "НЕ СУЖУ" in out6f and "ZZLEASE" in out6f
                       and "①" not in out6f,
                       f"код {rc6f} (ждём {NOT_JUDGED_EXIT}); до карточки #623 здесь было 🔴 ①–④ "
                       f"с кодом 1 — занятость читалась как поломка", differ=True)
            own_db = with_lease(source_db, tmp / "lease-own.db", SENDER_ROLE)
            rc6o, out6o = run_self(own_db)
            ok &= case("⑥ под СВОИМ объявлением (роль отправителя) — судится как прежде и принято",
                       rc6o == 0 and "ПРИНЯТО" in out6o and "НЕ СУЖУ" not in out6o,
                       f"код {rc6o} (ждём 0); своё объявление механизм пропускает — «не сужу» "
                       f"здесь было бы ложным молчанием", differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print((f"✅ ОТКАЗ ОТ ДУБЛЕЙ — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}" if ok
           else f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    code = main()
    # «Не сужу» — не провал: осматривать во временном каталоге нечего, он убирается как
    # при успехе; сам исход несёт код NOT_JUDGED_EXIT.
    mezo_stand.finish(0 if code == NOT_JUDGED_EXIT else code)
    sys.exit(code)
