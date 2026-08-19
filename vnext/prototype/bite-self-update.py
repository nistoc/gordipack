#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-self-update — приёмка самостоятельности контура: знает источник и умеет обновиться.

ЗАЧЕМ. Вопрос владельца 2026-08-19 09:22 UTC: «откуда tapas берёт инструментарий? он ведь
не скачал себе независимый репозиторий, чтобы не зависеть от твоих апгрейдов и чтобы мог
сам скачивать обновления». Ответ на тот момент: НИОТКУДА. Контур получал разовую копию файлов
с рабочего каталога соседа, не хранил ни источника, ни версии, и обновиться мог только чужой
рукой — то есть был не самостоятельной командой, а придатком чужой машины.

    python <КОНТУР>/vnext-tools/bite-self-update.py
"""
from __future__ import annotations

import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

CASES = DIFFER = 0
NL = chr(10)
INIT = pathlib.Path("<ШАБЛОН>/scripts/init-group.py")
UPDATER = pathlib.Path("<КОНТУР>/.mezosync/scripts/update-tools.py")


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += 1 if differ else 0
    print(("✅ " if ok else "🔴 ") + title)
    print("   " + detail)
    return ok


def main() -> int:
    ok = True
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="bite-selfupd-"))
    try:
        r = subprocess.run([sys.executable, str(INIT), "--name", "biteupd",
                            "--path", str(tmp / ".mezosync"), "--roles", "COORD"],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        db = tmp / ".mezosync" / "mezosync.db"
        ok &= case("① контур вообще собрался", db.exists(),
                   ((r.stdout or "") + (r.stderr or ""))[-160:].strip() or "сборка молчала")
        if not db.exists():
            return 1

        con = sqlite3.connect(db)
        meta = dict(con.execute("SELECT key, value FROM meta"))
        con.close()
        ok &= case("② контур знает, ОТКУДА и из какой версии собран",
                   bool(meta.get("template_source")) and bool(meta.get("template_commit")),
                   f"источник {meta.get('template_source', 'НЕТ')} · версия "
                   f"{meta.get('template_commit', 'НЕТ')}. До 19.08 спросить контур об этом было "
                   f"НЕЧЕМ: ответ жил только в голове того, кто собирал", differ=True)
        ok &= case("③ источник — ОБЩИЙ репозиторий, а не каталог на чьей-то машине",
                   str(meta.get("template_source", "")).startswith(("http", "git@")),
                   f"{meta.get('template_source')} — стой здесь путь на машине соседа, контур "
                   f"зависел бы от чужого диска и не обновился бы вовсе", differ=True)

        victim = tmp / ".mezosync" / "scripts" / "guard-utc.py"
        victim.write_text("# устаревшая копия" + NL, encoding="utf-8")
        upd = tmp / ".mezosync" / "scripts" / "update-tools.py"
        if not upd.exists():
            shutil.copy(UPDATER, upd)

        p = subprocess.run([sys.executable, str(upd)], capture_output=True, text=True,
                           encoding="utf-8", timeout=300)
        план = (p.stdout or "") + (p.stderr or "")
        ok &= case("④ план показывает отставший файл и НИЧЕГО не пишет",
                   "guard-utc.py" in план
                   and "устаревшая копия" in victim.read_text(encoding="utf-8"),
                   "обновление, которое пишет раньше показа, нельзя ни отменить, ни обсудить",
                   differ=True)

        p = subprocess.run([sys.executable, str(upd), "--apply"], capture_output=True,
                           text=True, encoding="utf-8", timeout=300)
        вернулся = "устаревшая копия" not in victim.read_text(encoding="utf-8")
        ok &= case("⑤ с --apply контур забирает свежее САМ, без чужой руки",
                   вернулся and "Забрано" in (p.stdout or ""),
                   "это и есть самостоятельность: обновление не требует того, кто контур собирал",
                   differ=True)

        # ⑥⑦⑧ НАХОДКИ СОСЕДА (контур tapas, ответ 19.08 10:46 UTC). Он отказался брать
        # инструменты, пока шапка обещает сохранность правок, а код перезаписывает.
        своя = tmp / ".mezosync" / "scripts" / "backlog.py"
        было_своё = "# МОЯ ПРАВКА, её терять нельзя" + NL + своя.read_text(encoding="utf-8")
        своя.write_text(было_своё, encoding="utf-8")
        p = subprocess.run([sys.executable, str(upd)], capture_output=True, text=True,
                           encoding="utf-8", timeout=300)
        план = (p.stdout or "") + (p.stderr or "")
        p2 = subprocess.run([sys.executable, str(upd), "--apply"], capture_output=True,
                            text=True, encoding="utf-8", timeout=300)
        цела = "МОЯ ПРАВКА" in своя.read_text(encoding="utf-8")
        ok &= case("⑥ файл, ПРАВЛЕННЫЙ У СЕБЯ, не затирается — обещание шапки исполняется",
                   цела and "ПРАВЛЕН У ТЕБЯ" in план,
                   "до 19.08 шапка это обещала, а код перезаписывал безусловно; сосед отказался "
                   "брать инструменты, пока противоречие не снято — и был прав", differ=True)

        # ⑦ ЗВЕНО ИЗ vnext/prototype: у потребителя лежит рядом со скриптами, в источнике — нет.
        звено = tmp / ".mezosync" / "scripts" / "mention.py"
        if звено.exists():
            звено.write_text("# отставшее звено" + NL, encoding="utf-8")
            subprocess.run([sys.executable, str(upd), "--apply", "--overwrite-unknown"],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
            ok &= case("⑦ звено из соседнего каталога источника ТОЖЕ обновляется",
                       "отставшее звено" not in звено.read_text(encoding="utf-8"),
                       "прежде обновлятор обходил только scripts/, и семь звеньев, которые "
                       "зовёт общий прогон, не обновлялись НИКОГДА — молча", differ=True)
        else:
            ok &= case("⑦ звено из соседнего каталога источника ТОЖЕ обновляется", False,
                       "звена mention.py нет в собранном контуре — проверять нечего", differ=True)

        # ⑧ КОНТРОЛЬ: без отпечатка установки различить свою правку НЕЧЕМ — и это говорится.
        con = sqlite3.connect(db)
        con.execute("DELETE FROM meta WHERE key = 'template_files_sha'")
        con.commit()
        con.close()
        victim.write_text("# снова устарело" + NL, encoding="utf-8")
        p = subprocess.run([sys.executable, str(upd), "--apply"], capture_output=True,
                           text=True, encoding="utf-8", timeout=300)
        не_тронут = "снова устарело" in victim.read_text(encoding="utf-8")
        ok &= case("⑧ КОНТРОЛЬ: без отпечатка установки файл НЕ обновляется молча",
                   не_тронут and "отпечатка установки нет" in (p.stdout or ""),
                   "молчаливое обновление здесь неотличимо от затирания чужой правки; "
                   "цена названа ДО действия и требует явного согласия", differ=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print((f"✅ САМОСТОЯТЕЛЬНОСТЬ КОНТУРА — ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"
           if ok else f"🔴 НЕ ПРИНЯТО — случаев {CASES}, различающих {DIFFER}"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
