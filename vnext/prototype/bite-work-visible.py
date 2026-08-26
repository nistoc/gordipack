#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-work-visible — приёмка видимости чужой работы, идущей прямо сейчас.

ЗАЧЕМ. 19.08 08:30 UTC владелец назвал класс: роль работала час (учебное восстановление
базы), и контур узнал об этом только из её итоговой записки. Никто не мог ни подождать,
ни не браться за то же. Замер подтвердил и заострил: состояние «в работе» ставили ТРИ раза
за месяц (3 перевода против 142 закрытий, последний 07.08) — механизм существовал и был
мёртв, потому что ставящему он не давал ничего, а коллеги всё равно не видели.

    python <КОНТУР>/vnext-tools/bite-work-visible.py
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

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
    tmp = mezo_stand.new("bite-work-")
    try:
        scripts = tmp / "scripts"
        shutil.copytree(live / "scripts", scripts)
        db = tmp / "mezosync.db"
        shutil.copy(live / "mezosync.db", db)
        env = {**os.environ, "MEZO_ROLE": "PROTO", "MEZO_LEASE_TEST": "1"}

        def backlog(*args):
            # ⚠️ --db идёт ДО подкоманды: у argparse общий флаг живёт у корневого
            # разбора, и после подкоманды он «нераспознан». Поймано первым же прогоном.
            r = subprocess.run([sys.executable, str(scripts / "backlog.py"), "--db", str(db),
                                *args], capture_output=True, text=True,
                               encoding="utf-8", timeout=120, env=env)
            return r.returncode, (r.stdout or "") + (r.stderr or "")

        spec = importlib.util.spec_from_file_location("ml", scripts / "machine_layer.py")
        ml = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(scripts))
        spec.loader.exec_module(ml)

        def block(role="CORE"):
            return "\n".join(ml.machine_block(str(db), role))

        import sqlite3
        con = sqlite3.connect(db)
        # Копия несёт объявления ЖИВОГО контура — для случая ① нужен чистый лист,
        # иначе он проверял бы не механизм, а сегодняшнюю занятость коллег.
        con.execute("DELETE FROM backlog_events WHERE event_type IN ('claim','claim_release')")
        con.commit()
        bid = con.execute("SELECT id FROM backlog WHERE status='open' LIMIT 1").fetchone()[0]
        con.close()

        before = block()
        ok &= case("① пока работу не объявили, показывается ЭТО, а не пустота",
                   "объявленной работы у коллег нет" in before,
                   "молчание неотличимо от «никто не работает»: роль решит, что проверено, "
                   "хотя не спрашивали")

        rc, out = backlog("claim", str(bid), "--actor", "OPSSRE")
        ok &= case("② «взял в работу» без рассказа, ЧТО делаешь, — отказ",
                   rc != 0 and "ЧТО делаешь" in out,
                   "коллега по этой строке решает, ждать ему или браться самому; "
                   "«работаю» не говорит ему ничего", differ=True)

        rc, out = backlog("claim", str(bid), "--actor", "OPSSRE", "--minutes", "60",
                          "--note", "готовлю ответ соседям по трём пунктам")
        after = block()
        ok &= case("③ объявленная работа ВИДНА другой роли при пробуждении",
                   rc == 0 and "СЕЙЧАС В РАБОТЕ У КОЛЛЕГ" in after
                   and "готовлю ответ соседям" in after,
                   "это единственное место, куда роль смотрит раньше, чем начинает свою; "
                   "если объявление не видно здесь, механизм бесполезен", differ=True)

        rc, _ = backlog("claim", str(bid), "--actor", "OPSSRE", "--release",
                        "--note", "проба")
        released = block()
        ok &= case("④ снятое объявление исчезает из чужого экрана",
                   rc == 0 and "СЕЙЧАС В РАБОТЕ" not in released,
                   "иначе список работ растёт вечно и его перестают читать", differ=True)

        # ⑤ ИСТЁКШЕЕ ОБЪЯВЛЕНИЕ ГАСНЕТ САМО — без единой команды снятия.
        con = sqlite3.connect(db)
        con.execute("INSERT INTO backlog_events (backlog_id, actor_role, event_type, body_md, at)"
                    " VALUES (?, 'STUD', 'claim', ?, datetime('now', '-3 hours'))",
                    (bid, "до " + con.execute("SELECT datetime('now','-1 hours')").fetchone()[0]
                     + " UTC · старое объявление"))
        con.commit()
        con.close()
        expired = block()
        ok &= case("⑤ объявление с истёкшим сроком гаснет САМО, без команды снятия",
                   "старое объявление" not in expired,
                   "забыть снять — норма человека; вечный захват задачи забытым объявлением "
                   "хуже, чем отсутствие механизма", differ=True)
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print((f"✅ ВИДИМОСТЬ ЧУЖОЙ РАБОТЫ — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}" if ok
           else f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
