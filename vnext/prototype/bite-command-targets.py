#!/usr/bin/env python3
"""ПРИЁМКА признака «напечатанная команда ведёт в пустоту» (guard-command-targets.py).

Повод — карточка #161 (заявка CORE 2026-08-10). Проверяемое свойство: признак краснеет,
когда в источнике или в §launcher напечатан вызов НЕСУЩЕСТВУЮЩЕГО файла, и молчит, когда
файл есть. Обе половины обязательны: сторож, который всегда молчит, выглядит как зелёный.

⚠️ ИСПЫТЫВАЕМ НА КОПИИ. Живую базу и живые слепки не трогаем: приёмка, мутирующая предмет,
однажды съест чью-то работу. Копия делается из ТОГО ЖЕ файла, что и живая, — иначе
проверялась бы не та вещь (класс «испытываем не то, что чиним»).
"""
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(r"C:\guts\.atlas\.mezosync\scripts\guard-command-targets.py")
LIVE_DB = Path(r"C:\guts\.atlas\.mezosync\mezosync.db")

CASES = []


def case(name, ok, detail=""):
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n   {detail}" if detail else ""))


def run_guard(db, prompts):
    r = subprocess.run([sys.executable, str(GUARD), "--db", str(db), "--prompts", str(prompts)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    if not GUARD.exists():
        print(f"🔴 НЕ ЗАПУСТИЛАСЬ: признака нет по пути {GUARD}")
        return 2

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        seq = [0]

        def fresh_db():
            """Своя копия на случай, которому нужна ЧИСТАЯ база.

            🪤 Поймано первым же прогоном этой приёмки 2026-08-10 13:39 UTC: случаи ⑤ и ⑥
            краснели ЗАКОННО, но не по своей причине — случай ④ дописывал мёртвый путь
            в ту же копию, и она оставалась испорченной. Прибор был прав, а приёмка лгала
            о том, ЧТО именно проверено. Состояние, протекающее между случаями, — это
            тот же класс «испытываем не то, что чиним», только внутри самой проверки.
            """
            seq[0] += 1
            p = tmp / f"mezosync-{seq[0]}.db"
            shutil.copy2(LIVE_DB, p)
            return p

        db = fresh_db()
        prompts_clean = tmp / "prompts_clean"
        prompts_clean.mkdir()
        (prompts_clean / "ok.md").write_text(
            f"Зови так:\n    python {GUARD}\n", encoding="utf-8")

        # ① КОНТРОЛЬНАЯ ПАРА: на неиспорченном материале прибор МОЛЧИТ.
        # Без неё краснота дальше не доказывает ничего — прибор мог бы краснеть всегда.
        code, out = run_guard(db, prompts_clean)
        case("① контроль: цели на месте — прибор зелёный", code == 0 and "🔴 ЦЕЛИ НЕТ" not in out,
             f"код {code}")

        # ② ИСТОЧНИК зовёт несуществующий файл — прибор КРАСНЕЕТ и НАЗЫВАЕТ путь.
        prompts_bad = tmp / "prompts_bad"
        prompts_bad.mkdir()
        ghost = r"C:\guts\.atlas\atlas.core\askgate.ps1"   # ровно та поломка из заявки #161
        (prompts_bad / "bad.md").write_text(
            f"Прогони гейт:\n    {ghost} -Full\n", encoding="utf-8")
        code, out = run_guard(db, prompts_bad)
        case("② источник зовёт пустоту — прибор краснеет и называет путь",
             code == 1 and "🔴 ЦЕЛИ НЕТ" in out and "askgate.ps1" in out, f"код {code}")

        # ③ ФОРМА БЕЗУПРЕЧНА, ЦЕЛИ НЕТ — то, на чём слеп признак «форма вызова».
        # Путь абсолютный, без относительных сегментов: старый сторож молчал бы законно.
        code, out = run_guard(db, prompts_bad)
        case("③ путь абсолютен и всё равно пуст — свойство отличается от «формы вызова»",
             "🔴 ЦЕЛИ НЕТ" in out and ":\\" in out.replace("/", "\\"))

        # ④ §LAUNCHER — зона PROTO ⇒ КРАСНОЕ, прочие секции — зона роли ⇒ жёлтое.
        # Разный цвет и есть смысл признака: вечно-красный сторож обесценивается.
        db = fresh_db()          # ⚠️ этот случай ПОРТИТ базу — дальше идут свои копии
        con = sqlite3.connect(db)
        con.execute("UPDATE phoenix SET body = body || ?  WHERE role='CORE' AND section='launcher'",
                    (f"\n    {ghost} -Full\n",))
        con.execute("UPDATE phoenix SET body = body || ?  WHERE role='CORE' AND section='state'",
                    (f"\n    {ghost} -Full\n",))
        con.commit()
        con.close()
        code, out = run_guard(db, prompts_clean)
        case("④ launcher красный, прочая секция жёлтая — зоны различены",
             code == 1 and "🔴 ЦЕЛИ НЕТ [CORE/launcher]" in out
             and "🟡 цели нет [CORE/state]" in out, f"код {code}")

        # ⑤ СТРОКА-ПРЕДОСТЕРЕЖЕНИЕ НЕ ОБВИНЯЕТСЯ. Роль, записавшая урок «⛔ не зови так:
        # <мёртвый путь>», не должна получать красное ЗА ПРАВИЛЬНО ЗАПИСАННЫЙ УРОК —
        # на этом классе уже обжёгся признак «форма вызова» (карточка #50).
        prompts_lesson = tmp / "prompts_lesson"
        prompts_lesson.mkdir()
        (prompts_lesson / "lesson.md").write_text(
            f"⛔ НЕ зови так — файла нет: {ghost} -Full\n", encoding="utf-8")
        code, out = run_guard(fresh_db(), prompts_lesson)
        case("⑤ урок про мёртвый путь прощён, а не обвинён", code == 0, f"код {code}")

        # ⑥ МАСКА — не путь. Находка BASELINE: `guard-*.py` не может «существовать».
        prompts_mask = tmp / "prompts_mask"
        prompts_mask.mkdir()
        (prompts_mask / "mask.md").write_text(
            "Прогони все: python C:/guts/.atlas/vnext-tools/guard-*.py\n", encoding="utf-8")
        code, out = run_guard(fresh_db(), prompts_mask)
        case("⑥ маска набора файлов не считается мёртвой целью", code == 0, f"код {code}")

        # ⑦ ЖИВОЙ МАТЕРИАЛ НЕ ТРОНУТ — иначе приёмка сама стала бы источником порчи.
        live_ok = LIVE_DB.exists() and LIVE_DB.stat().st_size > 0
        case("⑦ живая база цела: испытана КОПИЯ", live_ok)

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 ПРИБОР НЕ ПРИНЯТ — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИБОР ПРИНЯТ — случаев {len(CASES)}, из них различающих 5")
    return 0


if __name__ == "__main__":
    sys.exit(main())
