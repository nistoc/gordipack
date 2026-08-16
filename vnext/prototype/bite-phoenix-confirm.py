#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bite-phoenix-confirm — приёмка отметки «секцию перечитал, правок нет» (карточка #160).

    python C:/guts/.atlas/vnext-tools/bite-phoenix-confirm.py

ЧТО ИСПЫТЫВАЕТСЯ. Механизм обязан РАЗЛИЧАТЬ снаружи три состояния секции памяти:
    · правили ..................... текст новый, взгляда после него не было
    · перечитали и признали верной . текст прежний, взгляд свежее текста
    · не смотрели вовсе ........... взгляда нет и не было
и краснеть на паре «подтверждение СТАРШЕ текста» — она означает, что текст меняли
мимо инструмента, и отметке верить нельзя.

⚖️ ГРАНИЦА С СОСЕДНЕЙ ПРИЁМКОЙ, НАЗВАННАЯ ВСЛУХ: bite-phoenix-confirmed судит МЕРУ ③
   ВАРИАНТА А (слово владельца 08.08 16:19 UTC) — что запись ставит ОБЕ даты, а
   пересохранение того же текста двигает только взгляд. Эта приёмка судит ДРУГОЕ:
   что три состояния РАЗЛИЧИМЫ СНАРУЖИ и что есть способ отметить взгляд, не передавая
   тело. Две приёмки об одном поле — и это намеренно: они отвечают на разные вопросы.
🪤 ОПЛАЧЕНО 16.08 МНОЙ ЖЕ: чиня карточку #160, я поставил при записи «взгляд ПУСТО» —
   и молча отменил меру, принятую по слову владельца. Поймала не моя аккуратность,
   а общий прогон приёмок. ⇒ Правя поле, сперва спроси, чьё решение в нём живёт.

⛔ Живого контура НЕ касается: всё на копии базы во временном каталоге.
"""
from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402  (пути выводятся, не впечатаны)

LIVE_DB = mezo_paths.live_db()
SCRIPTS = mezo_paths.live_scripts()
SAVE = SCRIPTS / "save-phoenix.py"
READ = SCRIPTS / "read-phoenix.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def run(*argv):
    r = subprocess.run([sys.executable, *argv], capture_output=True, text=True,
                       encoding="utf-8", timeout=120)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def stamps(db, role="PROTO", section="state"):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute("SELECT saved_at, confirmed_at, LENGTH(body) FROM phoenix "
                           "WHERE role=? AND section=?", (role, section)).fetchone()
    finally:
        con.close()


def main() -> int:
    if not SAVE.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: инструмента нет — {SAVE}")

    ok = True
    d = Path(tempfile.mkdtemp(prefix="bite-confirm-"))
    db = d / "copy.db"
    shutil.copyfile(LIVE_DB, db)
    body1 = d / "b1.md"
    body1.write_text("тело пробы, редакция один\n" + "x" * 500, encoding="utf-8")

    # ── ① ЗАПИСЬ ТЕЛА СТАВИТ ОБЕ ДАТЫ, И ОНИ РАВНЫ (мера ③ варианта А) ────────
    out, code = run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "state",
                    "--file", str(body1), "--allow-shrink")
    saved1, conf1, _ = stamps(db)
    ok &= case("① запись тела ставит ОБЕ даты, и они РАВНЫ (мера ③ варианта А)",
               code == 0 and conf1 == saved1,
               f"после записи: текст {saved1}, взгляд {conf1} — РАВЕНСТВО и есть отпечаток "
               f"состояния «записан, с тех пор не перечитывался»", differ=True)

    # ── ② ОТМЕТКА СТАВИТСЯ И НЕ ТРОГАЕТ НИ ТЕЛО, НИ ЕГО ВОЗРАСТ ──────────────
    # ⏱ Пауза обязательна: у времени в базе разрешение СЕКУНДА, и без неё «взгляд
    # свежее записи» совпал бы с «взгляд равен записи» — оба состояния стали бы
    # неразличимы по построению, а приёмка — зелёной вслепую.
    time.sleep(1.1)
    out, code = run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "state",
                    "--confirm")
    saved2, conf2, len2 = stamps(db)
    ok &= case("② --confirm ставит взгляд, не трогая тело и его возраст",
               code == 0 and conf2 is not None and saved2 == saved1 and len2 == len(
                   body1.read_text(encoding="utf-8")),
               f"текст {saved2} (не сдвинут), взгляд {conf2}, длина {len2} — иначе отметка "
               f"подменяла бы возраст текста возрастом взгляда", differ=True)

    # ── ③ РАЗЛИЧАЮЩИЙ, ГЛАВНЫЙ: ДВА СОСТОЯНИЯ — ДВА РАЗНЫХ ОТПЕЧАТКА ────────
    #     «правили» после «признали верной» обязано снова дать пустой взгляд.
    body2 = d / "b2.md"
    body2.write_text("тело пробы, редакция ДВА\n" + "y" * 500, encoding="utf-8")
    run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "state",
        "--file", str(body2), "--allow-shrink")
    saved3, conf3, _ = stamps(db)
    ok &= case("③ «правил» и «признал верной» НЕ дают один отпечаток",
               conf3 == saved3 and saved3 > saved2 and conf2 > saved2,
               f"после правки взгляд снова РАВЕН записи ({conf3}), а до неё был СТАРШЕ "
               f"({conf2} > {saved2}) — два состояния, два разных отношения дат", differ=True)

    # ── ④ ЧТЕНИЕ ПАМЯТИ НАЗЫВАЕТ СОСТОЯНИЕ СЛОВАМИ ──────────────────────────
    out, _ = run(str(READ), "--db", str(db), "--role", "PROTO", "--section", "state")
    ok &= case("④ чтение памяти говорит «после записи НЕ перечитывалось»",
               "после записи НЕ перечитывалось" in out,
               "до 16.08 витрина читала равенство дат как «признано верным» — выдавала факт "
               "НАПИСАНИЯ за факт ПЕРЕЧИТЫВАНИЯ", differ=True)

    time.sleep(1.1)
    run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "state", "--confirm")
    out, _ = run(str(READ), "--db", str(db), "--role", "PROTO", "--section", "state")
    ok &= case("⑤ после подтверждения чтение говорит «перечитано и признано верным»",
               "перечитано и признано верным" in out,
               "две ветки витрины различаются — контрольная половина к случаю ④", differ=True)

    # ── ⑥ КРАСНОЕ: ПОДТВЕРЖДЕНИЕ СТАРШЕ ТЕКСТА (правка мимо инструмента) ────
    con = sqlite3.connect(db)
    con.execute("UPDATE phoenix SET saved_at = datetime('now', '+1 hour') "
                "WHERE role='PROTO' AND section='state'")
    con.commit()
    con.close()
    out, _ = run(str(READ), "--db", str(db), "--role", "PROTO", "--section", "state")
    ok &= case("⑥ подтверждение СТАРШЕ текста — витрина КРАСНЕЕТ и называет причину",
               "СТАРШЕ текста" in out,
               "пара возникает только при правке мимо инструмента; молчать о ней значит "
               "выдавать протухшую отметку за свежую", differ=True)

    # ── ⑦ ОТКАЗЫ, КОТОРЫЕ ОБЯЗАНЫ БЫТЬ ──────────────────────────────────────
    out, code = run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "state",
                    "--confirm", "--body", "текст")
    ok &= case("⑦ --confirm вместе с телом ОТКЛОНЁН",
               code != 0 and "НЕ принимает тело" in out,
               "иначе «отметил взгляд» тихо переписало бы секцию — два действия под одним "
               "именем", differ=True)

    # ⚠️ Секцию СНАЧАЛА УБИРАЕМ из копии: без этого случай «неприменим» и молча
    # засчитывается зелёным — ровно тот ложный зелёный, ради которого пишутся приёмки.
    con = sqlite3.connect(db)
    con.execute("DELETE FROM phoenix WHERE role='PROTO' AND section='history'")
    con.commit()
    con.close()
    out, code = run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "history",
                    "--confirm")
    ok &= case("⑧ подтверждение НЕСУЩЕСТВУЮЩЕЙ секции отклонено",
               code != 0 and "подтверждать нечего" in out,
               "секция удалена из копии перед проверкой: «смотрел» о несуществующем тексте — "
               "утверждение ни о чём, и отметка легла бы в пустоту", differ=True)

    # ── ⑨ КОНТРОЛЬ: ПРИБОР НЕ МОЛЧИТ ВООБЩЕ ─────────────────────────────────
    #     Здоровая пара «текст свежий, взгляд свежее» обязана читаться как норма.
    fresh = d / "b3.md"
    fresh.write_text("редакция ТРИ\n" + "z" * 500, encoding="utf-8")
    run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "state",
        "--file", str(fresh), "--allow-shrink")
    time.sleep(1.1)
    run(str(SAVE), "--db", str(db), "--role", "PROTO", "--section", "state", "--confirm")
    out, _ = run(str(READ), "--db", str(db), "--role", "PROTO", "--section", "state")
    ok &= case("⑨ контроль: здоровая пара НЕ красная",
               "СТАРШЕ текста" not in out and "перечитано и признано верным" in out,
               "без этого случая краснота ⑥ ничего не доказывала бы: прибор, красящий всё, "
               "не различает")

    shutil.rmtree(d, ignore_errors=True)
    print()
    if ok:
        print(f"✅ ОТМЕТКА ВЗГЛЯДА ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
        return 0
    print(f"🔴 НЕ ПРИНЯТА — случаев {CASES}, различающих {DIFFER}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
