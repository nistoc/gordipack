#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ПРИЁМКА: пустой ОТБОР ленты никогда не выдаётся за дочитанную ЛЕНТУ.

ПОВОД (карточка #171, 2026-08-10 18:28 UTC). Собирая факты о @STUD, позвал
`read-messages.py --role STUD --limit 0` и получил «Нет непрочитанных сообщений»
при 85 непрочитанных: в SQLite `LIMIT 0` отдаёт ноль строк, а ветка «пусто» читала
пустоту как дочитанную ленту.

🪤 ГЛАВНОЕ В ЭТОЙ КАРТОЧКЕ — НЕ САМ `0`, А ТО, ЧТО ЭТО ОСТАТОК УЖЕ ЛЕЧЁННОГО.
Над той же веткой стоит надгробие находки @opssre (#3442, 08.08): витрина `--to-me`
печатала ту же ложь, и комментарий называет класс дословно — «витрина отвечает про своё
подмножество, а не про ленту». Лечение применили ТОЧЕЧНО, к одному сужению. Второе
(`--limit`) и третье (`--tag`) остались лгать и выглядели зелёными двое суток.

🎯 ПОЭТОМУ ЗДЕСЬ ПРОВЕРЯЕТСЯ СВОЙСТВО, А НЕ ТРИ ФОРМЫ: пока долг по ленте не ноль,
НИ ОДНА ветка не вправе сказать «непрочитанного нет». Новое сужение, добавленное завтра,
наследует правду даром — если только кто-нибудь снова не заведёт своё вычисление рядом.
Случай ⑤ стережёт именно это: число берётся ОДИН раз, до разбора вида пустоты.

⚠️ ЖИВАЯ БАЗА НЕ МУТИРУЕТСЯ: испытывается КОПИЯ, отметка прочитанного двигается в ней.
"""
from __future__ import annotations

import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import mezo_paths    # пути машины ВЫВОДЯТСЯ, не впечатаны (#153 · #157 · #168)
import mezo_target   # какую копию испытываем: живую или шаблон (#146 · #148)

# ⛔ ПУТИ ЗДЕСЬ НЕ ВПЕЧАТАНЫ, и на то две оплаченные причины:
#  ① впечатанный абсолют делает приёмку слепой к выбору испытуемой копии — она судила бы
#    ОРИГИНАЛ, чем бы ни был натравлен прогон. Это карточка #168, закрытая в тот же день;
#  ② этот каталог ПУБЛИЧЕН и обезличен: путь машины автора здесь — утечка, а не удобство.
READER = mezo_target.script("read-messages.py")
LIVE_DB = mezo_paths.live_db()
ROLE = "ЗОНДЧТЕНИЯ"

CASES: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str = "") -> None:
    CASES.append((name, ok, detail))
    print(("✅ " if ok else "🔴 ") + name + (f"\n     {detail}" if detail else ""))


def run(db: Path, *extra: str) -> tuple[int, str]:
    r = subprocess.run([sys.executable, str(READER), "--role", ROLE, "--db", str(db), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def claims_all_read(out: str) -> bool:
    """Утверждение про ЛЕНТУ, а не про отбор. Ищем именно его, а не слово «нет».

    ⚖️ Судим ПОСТРОЧНО и по началу строки: правдивый вывод тоже содержит слово
    «непрочитанных» («В ЛЕНТЕ непрочитанных: 85»), и поиск подстроки по всему выводу
    смешал бы правду с ложью. Этот способ уже давал ложно-зелёный случай в приёмке
    карточки #168 — там метку печатал соседний признак.
    """
    return any(re.search(r"Нет непрочитанных сообщений", ln) for ln in out.splitlines())


def seed(db: Path, unread: int) -> None:
    """Завести роль с ДОЛГОМ: курсор позади головы ровно на `unread` записок."""
    con = sqlite3.connect(db)
    head = con.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]
    for i in range(1, unread + 1):
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body_md, tags, priority,"
                    " resolved, broadcast, addressed_by) VALUES (?,?,datetime('now'),?,?,?,0,1,?)",
                    (head + i, ROLE, f"проба честности пустого отбора {i}", "[]", "normal", "field"))
    con.execute("INSERT OR REPLACE INTO read_cursors (reader_role, last_read_id, updated_at)"
                " VALUES (?,?,datetime('now'))", (ROLE, head))
    con.commit()
    con.close()


def cursor_to_head(db: Path) -> None:
    con = sqlite3.connect(db)
    head = con.execute("SELECT MAX(id) FROM messages").fetchone()[0]
    con.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role=?", (head, ROLE))
    con.commit()
    con.close()


def main() -> int:
    for p in (READER, LIVE_DB):
        if not p.exists():
            print(f"🔴 НЕ ЗАПУСТИЛАСЬ: нет по пути {p}")
            return 2

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "probe.db"
        shutil.copy2(LIVE_DB, db)
        seed(db, unread=7)

        # ① ФОРМА ИЗ ЗАЯВКИ: `--limit 0`. Отклоняется, и отказ виден КОДОМ ВОЗВРАТА.
        #    Код проверяется отдельно: `main()` зовётся без sys.exit, и `return 2` там
        #    дал бы ноль — отказ, выглядящий успехом. Эта грабля поймана при самой починке.
        code, out = run(db, "--limit", "0")
        case("① --limit 0 отклонён и НЕ выдан за дочитанную ленту",
             code == 2 and not claims_all_read(out), f"код {code} (ждали 2)")

        # ② ВТОРОЕ СУЖЕНИЕ — ТЕГ. О нём никто не заявлял; лгал он ровно так же.
        code, out = run(db, "--tag", "ЗАВЕДОМОНЕТТАКОГО", "--limit", "5")
        case("② пустой отбор по тегу называет долг, а не тишину",
             not claims_all_read(out) and "7" in out,
             "в выводе должно стоять число непрочитанных по ЛЕНТЕ")

        # ③ ВИТРИНА `--to-me` — плечо, ради которого починку когда-то и делали.
        #    Стережём от РЕГРЕССА: обобщение не должно было его сломать.
        code, out = run(db, "--to-me")
        case("③ отбор «только моё» по-прежнему честен",
             not claims_all_read(out) and "7" in out)

        # ④ КОНТРОЛЬНАЯ ПАРА: законная пустота НЕ оболгана. Без этого случая приёмку
        #    прошёл бы инструмент, который кричит ВСЕГДА, — и это была бы не починка.
        cursor_to_head(db)
        code, out = run(db, "--limit", "5")
        case("④ отметка прочитанного у головы — «непрочитанного нет» звучит и это правда",
             claims_all_read(out) and code == 0)

        # ⑤ ОБОБЩЕНИЕ, А НЕ ТРЕТЬЯ ЗАПЛАТА: долг считается ОДНИМ запросом до разбора
        #    вида пустоты. Два вычисления рядом — та самая точечность, из-за которой
        #    дефект и дожил: следующее сужение снова окажется без правды.
        # 🪤 ПЕРВАЯ РЕДАКЦИЯ ЭТОГО СЛУЧАЯ БЫЛА КРАСНОЙ ПО СВОЕЙ ВИНЕ: она резала файл от
        #    ПЕРВОГО `if not rows:` — а он в ветке `--index` (строка 325) и печатает «пусто».
        #    Судила один блок, чинили другой. Разбор границ переписан на признак, который
        #    не зависит от того, сколько в файле похожих веток.
        src = READER.read_text(encoding="utf-8")
        counts = len(re.findall(r"SELECT COUNT\(\*\) FROM messages WHERE id > \?", src))
        # ⚠️ И ВТОРАЯ ГРАБЛЯ ТОГО ЖЕ РОДА: фраза «Нет непрочитанных сообщений» стои́т в файле
        #    ДВАЖДЫ — в надгробии @opssre (комментарий) и в самой печати. Поиск по фразе брал
        #    комментарий, и признак судил о порядке строк в ПРОЗЕ. Цепляемся за форму КОДА.
        claim = src.index('print(f"[{role}] Нет непрочитанных')
        calc = src.index("SELECT COUNT(*) FROM messages WHERE id > ?")
        case("⑤ долг по ленте считается ОДИН раз и ДО разбора вида пустоты",
             counts == 1 and calc < claim,
             f"вычислений во всём файле: {counts} (ждали 1); "
             f"считается раньше утверждения: {calc < claim}")

    # ⑥ ЖИВАЯ БАЗА ЦЕЛА: зонд остался в копии.
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    leaked = con.execute("SELECT COUNT(*) FROM messages WHERE writer_role=?", (ROLE,)).fetchone()[0]
    con.close()
    case("⑥ живая база не тронута", leaked == 0, f"записей зонда в живой базе: {leaked}")

    bad = [n for n, ok, _ in CASES if not ok]
    print("-" * 78)
    if bad:
        print(f"🔴 НЕ ПРИНЯТО — не держатся: {', '.join(bad)}")
        return 1
    print(f"✅ ПРИНЯТО — случаев {len(CASES)}, из них различающих 4 (①②③⑤)")
    print("⚖️ ГРАНИЦА: проверены ТРИ известных сужения. Что четвёртое, добавленное завтра,")
    print("   унаследует правду, стережёт случай ⑤ — но лишь пока число считается одним")
    print("   запросом. Заведёт кто-то своё вычисление рядом — ⑤ покраснеет, и это его дело.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
