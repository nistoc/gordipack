#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ПРИЁМКА: исправление ФАКТИЧЕСКОЙ ошибки в записи реестра прав (`role-rights.py amend`).

Предмет заведён по слову владельца 2026-08-30 23:25 UTC: убрать выдуманный час
«2026-08-08 15:56 UTC» из реестра прав. До правки инструмент умел выдать · потратить ·
отозвать · показать — и НЕ УМЕЛ исправить ошибку в собственной записи, а обход
«отозвать и выдать заново» записал бы в историю прерывание права, которого не было.

⚖️ ЧТО ИСПЫТУЕТСЯ: КОПИЯ базы во временном каталоге. Живая база только читается —
из неё берётся схема таблицы, чтобы опыт шёл по НАСТОЯЩЕЙ форме записи, а не по моему
представлению о ней (правило свода `contract-shape-from-live-call`).

🔬 Случаи ①–⑪ ниже (⑩ и ⑪ — на поле «причина отзыва», карточка #776); у каждого сказано, ЧТО он различает. Случай, который нельзя
заставить покраснеть, засчитывать нельзя — поэтому набор рассчитан на прогон
и по испорченной копии инструмента (см. --tool).
"""
import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402 — испытуемое через общий выбор копии (карточка #682)

# 🪤 Здесь стояли пути ЭТОЙ машины прямо в константах, и перенос в публичный образец
# честно отказывался: обезличить исполняемую строку значит сломать инструмент у того,
# кто его возьмёт. ⇒ путь ВЫВОДИТСЯ от расположения файла (норма R15a), а не вписывается.
LIVE_DB = mezo_paths.live_db(__file__)
DEFAULT_TOOL = Path(mezo_target.scripts_root()) / "role-rights.py"
ВЫДУМАННЫЙ_ЧАС = "2026-08-08 15:56"


def таблица_из_живой() -> str:
    """Схему берём у живой базы: приёмка на своей выдумке проверяет выдумку."""
    conn = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE name='role_rights'").fetchone()
    finally:
        conn.close()
    if not sql:
        sys.exit("⛔ НЕ ЗАПУСТИЛОСЬ: в живой базе нет таблицы role_rights — "
                 "это третий исход, а не зелёный.")
    return sql[0]


def песочница(tmp: Path) -> Path:
    db = tmp / "rights.db"
    conn = sqlite3.connect(db)
    conn.execute(таблица_из_живой())
    conn.execute("CREATE VIEW role_rights_live AS SELECT * FROM role_rights "
                 "WHERE revoked_at IS NULL AND spent_at IS NULL")
    conn.execute(
        "INSERT INTO role_rights (id, role, right_key, scope, kind, authorized_by, "
        "granted_at, source_ref, declared_by, note) VALUES "
        "(1,'ALL','push','любой наш репозиторий','standing','owner',?,?,'field','живое')",
        (f"{ВЫДУМАННЫЙ_ЧАС} UTC", f"чат владельца {ВЫДУМАННЫЙ_ЧАС} UTC"))
    conn.execute(
        "INSERT INTO role_rights (id, role, right_key, scope, kind, authorized_by, "
        "granted_at, source_ref, declared_by, note, revoked_at, revoked_why) VALUES "
        "(2,'ALL','push',NULL,'standing','owner',?,'старое','field','отозванное',"
        "'2026-08-11 11:32:08','заменено именной областью')",
        (f"{ВЫДУМАННЫЙ_ЧАС} UTC",))
    conn.commit()
    conn.close()
    return db


def зов(tool: Path, db: Path, *args):
    p = subprocess.run([sys.executable, str(tool), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def поле(db: Path, id_: int, col: str):
    conn = sqlite3.connect(db)
    try:
        r = conn.execute(f"SELECT {col} FROM role_rights WHERE id=?", (id_,)).fetchone()
    finally:
        conn.close()
    return r[0] if r else None


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка: исправление записи реестра прав")
    ap.add_argument("--tool", default=str(DEFAULT_TOOL),
                    help="какой инструмент испытывать (для порчи — копия)")
    a = ap.parse_args()
    tool = Path(a.tool)
    if not tool.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛОСЬ: инструмента нет: {tool}")
    print(f"⚖️ испытуется: {tool.name}"
          f"{' (ЖИВОЙ)' if tool == DEFAULT_TOOL else ' — КОПИЯ, живой не тронут'}")

    ok, bad = 0, []
    tmp = Path(tempfile.mkdtemp(prefix="rights-amend-"))
    try:
        db = песочница(tmp)

        # ① правка часа проходит и МЕНЯЕТ значение
        code, out = зов(tool, db, "amend", "--id", "1", "--by", "CORE",
                        "--why", "часа нет в записях разговоров, перемерено пятью руками",
                        "--granted-at", "2026-08-08 11:22:40 UTC")
        стало = поле(db, 1, "granted_at")
        if code == 0 and стало == "2026-08-08 11:22:40 UTC":
            ok += 1
            print("✅ ① час исправлен, значение в базе сменилось")
        else:
            bad.append(f"① час НЕ исправлен: код {code}, в базе «{стало}»")

        # ② след правки записан: видно И старое, И новое, И кто правил
        note = поле(db, 1, "note") or ""
        if ВЫДУМАННЫЙ_ЧАС in note and "11:22:40" in note and "CORE" in note:
            ok += 1
            print("✅ ② след записан: старое значение, новое и рука правившего")
        else:
            bad.append(f"② след неполон: «{note[:120]}»")

        # ③ ВСТРЕЧНЫЙ: те же значения ⇒ «ничего не изменено», НОВОГО следа нет
        было = поле(db, 1, "note")
        code, out = зов(tool, db, "amend", "--id", "1", "--by", "CORE", "--why", "повтор",
                        "--granted-at", "2026-08-08 11:22:40 UTC")
        if code == 1 and поле(db, 1, "note") == было and "НИЧЕГО НЕ ИЗМЕНЕНО" in out:
            ok += 1
            print("✅ ③ ВСТРЕЧНЫЙ: повтор той же правки ничего не пишет и говорит об этом")
        else:
            bad.append(f"③ повтор правки не различён: код {code}, след менялся: "
                       f"{поле(db, 1, 'note') != было}")

        # ④ отказ без причины — правка без «чем опровергнуто» неотличима от подмены
        code, out = зов(tool, db, "amend", "--id", "1", "--by", "CORE",
                        "--granted-at", "2026-01-01 00:00 UTC")
        # ⚠️ мало «код не ноль»: отказ разбора аргументов («нет такой подкоманды») тоже
        # не ноль. Случай обязан краснеть ПО СВОЕЙ причине ⇒ ищем в ответе слово о причине.
        свой_отказ = "--why" in out or "причин" in out
        поле_цело = поле(db, 1, "granted_at") == "2026-08-08 11:22:40 UTC"
        if code != 0 and свой_отказ and поле_цело:
            ok += 1
            print("✅ ④ без причины — отказ ПО СВОЕЙ причине, запись НЕ тронута")
        elif code != 0 and not свой_отказ:
            bad.append("④ отказ пришёл НЕ от проверки причины (разбор аргументов?) — "
                       f"случай не различает своё: «{out.strip()[:80]}»")
        elif code != 0:
            # ⚖️ ТРЕТИЙ ГОЛОС: отказ пришёл СВОЙ, но поле уже не то — значит его сдвинул
            # предыдущий случай по общей песочнице. Сказать «правка прошла» было бы ложью
            # о причине и послало бы чинить целый сторож.
            bad.append(f"④ НЕ ПРОВЕРЕНО: проверка причины отказала СВОИМИ словами (код {code}), "
                       f"но поле уже «{поле(db, 1, 'granted_at')}» — его сдвинул случай ДО меня")
        else:
            bad.append(f"④ правка без причины ПРОШЛА: код {code}")

        # ⑤ отказ без руки правившего
        code, out = зов(tool, db, "amend", "--id", "1", "--why", "почему",
                        "--granted-at", "2026-01-01 00:00 UTC")
        свой_отказ = "--by" in out or "рук" in out
        поле_цело = поле(db, 1, "granted_at") == "2026-08-08 11:22:40 UTC"
        if code != 0 and свой_отказ and поле_цело:
            ok += 1
            print("✅ ⑤ без руки правившего — отказ ПО СВОЕЙ причине, запись НЕ тронута")
        elif code != 0 and not свой_отказ:
            bad.append("⑤ отказ пришёл НЕ от проверки руки — случай не различает своё: "
                       f"«{out.strip()[:80]}»")
        elif code != 0:
            # ⚖️ ТРЕТИЙ ГОЛОС (найдено @ING, приёмка карточки #503, записка #4611 §②):
            # прежде здесь печаталось «правка без руки прошла: код 1» — строка, спорящая
            # сама с собой. Отказ БЫЛ, сторож цел, а поле сдвинул сосед ④ по общей
            # песочнице. Красное обязано называть СВОЮ причину, иначе чинить пойдут целое.
            bad.append(f"⑤ НЕ ПРОВЕРЕНО: проверка руки отказала СВОИМИ словами (код {code}), "
                       f"но поле уже «{поле(db, 1, 'granted_at')}» — его сдвинул случай ДО меня")
        else:
            bad.append(f"⑤ правка без руки ПРОШЛА: код {code}")

        # ⑥ несуществующая запись — ОТКАЗ, а не тихий успех
        code, out = зов(tool, db, "amend", "--id", "999", "--by", "CORE", "--why", "п",
                        "--granted-at", "2026-01-01 00:00 UTC")
        if code != 0 and "#999" in out:
            ok += 1
            print("✅ ⑥ правка несуществующей записи — отказ С НОМЕРОМ, а не тихий успех")
        elif code != 0:
            bad.append("⑥ отказ есть, но он не называет запись — значит пришёл не отсюда: "
                       f"«{out.strip()[:80]}»")
        else:
            bad.append(f"⑥ правка несуществующей записи не отказала: код {code}")

        # ⑦ ДЕЙСТВИЕ ПРАВА НЕ ТРОНУТО: отозванное остаётся отозванным, живое живым
        code, out = зов(tool, db, "amend", "--id", "2", "--by", "CORE",
                        "--why", "тот же выдуманный час в исторической записи",
                        "--granted-at", "2026-08-08 11:22:40 UTC")
        отозв2 = поле(db, 2, "revoked_at")
        живое1 = поле(db, 1, "revoked_at")
        if code == 0 and отозв2 == "2026-08-11 11:32:08" and живое1 is None:
            ok += 1
            print("✅ ⑦ действие права не сдвинуто: отозванное отозвано, живое живо")
        elif code != 0:
            # ⚖️ ЧЕСТНЫЙ ГОЛОС: правка не прошла вовсе ⇒ про действие права этот прогон
            # не знает НИЧЕГО. Сказать «действие сдвинулось» значило бы послать чинить не то.
            bad.append(f"⑦ НЕ ПРОВЕРЕНО: правка не прошла (код {code}) — о действии права "
                       "случай молчит, и это не то же, что «сдвинулось»")
        else:
            bad.append(f"⑦ действие права СДВИНУЛОСЬ: отозвано={отозв2}, живое={живое1}")

        # ⑧ ОБРАЗЕЦ В ПОДСКАЗКЕ НЕ НЕСЁТ ВЫДУМАННОГО ЧАСА — роль копирует то, что читает
        code, out = зов(tool, db, "grant", "--role", "TEST", "--right", "проба",
                        "--kind", "standing")
        if ВЫДУМАННЫЙ_ЧАС not in out:
            ok += 1
            print("✅ ⑧ образец в подсказке не учит выдуманному часу")
        else:
            bad.append("⑧ подсказка всё ещё показывает выдуманный час образцом")

        # ⑨ контроль: своих следов в ЖИВОЙ базе нет
        conn = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
        try:
            следов = conn.execute(
                "SELECT COUNT(*) FROM role_rights WHERE role='TEST' OR right_key='проба'"
            ).fetchone()[0]
        finally:
            conn.close()
        if следов == 0:
            ok += 1
            print("✅ ⑨ контроль: своих следов в живой базе нет")
        else:
            bad.append(f"⑨ в живой базе {следов} следов опыта")

        # ⑩ ПРАВКА ПРИЧИНЫ ОТЗЫВА У ОТОЗВАННОЙ ЗАПИСИ ПРОХОДИТ (карточка #776).
        # Патч карточки #503 перенёс границу с ИМЕНИ поля на его ПРИРОДУ: причина отзыва —
        # свидетельство, а действие несёт revoked_at. Возврат прежнего поведения («в имени
        # есть revoked — править нельзя») девять прежних случаев не замечали: они правили
        # только granted_at. Случай различает: значение СМЕНИЛОСЬ, след назвал старое,
        # новое и руку, а отзыв остался прежним.
        old_reason = поле(db, 2, "revoked_why")
        # ⚖️ Новое значение НАРОЧНО не содержит старого подстрокой (находка проверяющего пачки, 18.11.2026):
        # прежнее «заменено именной областью; …» начиналось со старого значения, и след, записавший
        # ТОЛЬКО новое, проходил проверку «след назвал старое».
        new_reason = "область названа в записи #3; прежняя запись причины была неполной"
        revoked_before = поле(db, 2, "revoked_at")
        spent_before = поле(db, 2, "spent_at")
        code, out = зов(tool, db, "amend", "--id", "2", "--by", "COORD",
                        "--why", "причина отзыва неполна: не названа сама область",
                        "--revoked-why", new_reason)
        reason_now = поле(db, 2, "revoked_why")
        trail = поле(db, 2, "note") or ""
        if not old_reason or old_reason in new_reason:
            # старого значения нет или оно входит в новое ⇒ о следе случай сказать не может ничего
            bad.append("⑩ НЕ ПРОВЕРЕНО: старая причина отзыва пуста или входит в новую подстрокой — "
                       "след без старого значения был бы неотличим от полного")
        elif code != 0:
            bad.append("⑩ правка причины отзыва у ОТОЗВАННОЙ записи НЕ прошла: "
                       f"код {code}, «{out.strip()[:100]}»")
        elif reason_now != new_reason:
            bad.append(f"⑩ код 0, но причина отзыва не сменилась: в базе «{reason_now}»")
        elif not (old_reason in trail and new_reason in trail and "COORD" in trail):
            bad.append(f"⑩ значение сменилось, но след неполон: «{trail[-160:]}»")
        elif (поле(db, 2, "revoked_at") != revoked_before
              or поле(db, 2, "spent_at") != spent_before):
            bad.append("⑩ причина сменилась, но ДЕЙСТВИЕ права сдвинулось: "
                       f"отозвано {revoked_before} → {поле(db, 2, 'revoked_at')}")
        else:
            ok += 1
            print("✅ ⑩ правка причины отзыва у ОТОЗВАННОЙ записи проходит: значение сменилось, "
                  "след записан, действие права не сдвинулось")

        # ⑪ ВСТРЕЧНЫЙ к ⑩: у ЖИВОГО права причины отзыва нет и быть не должно. Без этого
        # случая ⑩ краснел бы на чём угодно, а разрешение править «всё подряд» прошло бы.
        # Мало «код не ноль»: отказ разбора аргументов тоже не ноль ⇒ ищем СВОИ слова
        # инструмента («НЕ ОТОЗВАНА»), как в ④ и ⑤.
        live_reason_before = поле(db, 1, "revoked_why")
        live_trail_before = поле(db, 1, "note")
        live_revoked_before = поле(db, 1, "revoked_at")
        code, out = зов(tool, db, "amend", "--id", "1", "--by", "COORD",
                        "--why", "проба: причина отзыва у живого права",
                        "--revoked-why", "причина отзыва, которого не было")
        own_refusal = "НЕ ОТОЗВАНА" in out
        untouched = (поле(db, 1, "revoked_why") == live_reason_before
                      and поле(db, 1, "note") == live_trail_before
                      and поле(db, 1, "revoked_at") == live_revoked_before)
        if code != 0 and own_refusal and untouched:
            ok += 1
            print("✅ ⑪ ВСТРЕЧНЫЙ: правка причины отзыва у ЖИВОГО права — отказ СВОИМИ словами "
                  "инструмента, запись не тронута")
        elif code != 0 and not own_refusal:
            bad.append("⑪ отказ пришёл НЕ от проверки «право не отозвано» (разбор аргументов?) — "
                       f"случай не различает своё: «{out.strip()[:80]}»")
        elif code != 0:
            bad.append("⑪ отказ СВОИМИ словами был, но запись живого права всё равно сдвинулась")
        else:
            bad.append(f"⑪ правка причины отзыва у ЖИВОГО права ПРОШЛА: код {code}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    for b in bad:
        print("🔴 " + b)
    итог = f"{ok} из 11"
    print(("✅ ИТОГ: " if not bad else "🔴 ИТОГ: ") + итог)
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
