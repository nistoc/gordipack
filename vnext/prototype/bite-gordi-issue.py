# -*- coding: utf-8 -*-
r"""bite-gordi-issue.py — приёмка гейта писателя канала «process → issues» (gordi-issue.py).

🩸 ПОВОД (найдено контуром AIA, подтверждено в нашем коде, 2026-09-13): `_writer_gate`
принимал ТОЛЬКО литерал «COORD» — координатор контура был константой кода, а не фактом
контура. Смени владелец координатора словом (как уже переходили зоны CHROME/OPSSRE/PROTO
по `migrations/roster.json`), литерал остался бы верен вчера и молча ошибался бы сегодня:
отказывал бы НАСТОЯЩЕМУ координатору и пропускал бы самозванца с именем «COORD», если оно
освободится. Правка: координатор ищется в данных контура (`roles.lifecycle_reason`),
литерал «COORD» остаётся ТОЛЬКО запасным путём — и печатает, откуда взять верное.

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ⓪ СТЕНД (gordipack issue #40, карточка #699): исходная копия ставится в три раскладки —
     «Atlas» (слово «координатор» у COORD) · «dominal» (слово у 3P, у COORD его нет) ·
     «никто не назван»; после посева во всех назван РОВНО COORD, и COORD пишет.
     «Atlas» — контроль, «dominal» и «никто не назван» — РАЗЛИЧАЮЩИЕ
  ① координатор из данных пишет — гейт пропускает                              контроль
  ② НЕ координатор (по данным) отказан, отказ НАЗЫВАЕТ настоящего координатора  РАЗЛИЧАЮЩИЙ
  ③ данные не называют РОВНО ОДНУ роль-координатора → запасной литерал «COORD»,
     печатается ПРЕДУПРЕЖДЕНИЕ, откуда брать верное                            РАЗЛИЧАЮЩИЙ
  ④ ГЛАВНЫЙ ВСТРЕЧНЫЙ: координатор в данных — ДРУГАЯ роль (не «COORD») → эта
     роль пишет, а буквальный «COORD» — уже НЕТ (доказывает, что источник данных
     ДЕЙСТВУЕТ, а не разбор данных ради проформы поверх старого литерала)          РАЗЛИЧАЮЩИЙ
  ⑤ ⑤-бис РЕГИСТР КИРИЛЛИЦЫ: причина роли написана с заглавной и прописными —
     слово всё равно найдено (возврат COORD 2026-09-15: запрос LIKE сворачивает
     регистр только у латиницы и такую причину не видел вовсе)                   РАЗЛИЧАЮЩИЙ

НАРОЧНАЯ ПОЛОМКА (--porcha revert-to-literal): при не ровно одной роли-координаторе снова
подставляется литерал «COORD» без отказа — ждём красным РОВНО ③ и ③-бис; остальные целы.
⚰️ Здесь стояло «ждём красным РОВНО ④» — разошлось с кодом и с прогоном (замер PROTO
2026-10-17 10:48 UTC: под этой поломкой красны ③ и ③-бис, ④ цел); поправлено при правке #699.
ВТОРАЯ НАРОЧНАЯ ПОЛОМКА (--porcha revert-to-like): ОБЩАЯ функция поиска координатора
(mezo_paths.find_coordinator — с карточки #677, этап Э3, отбор живёт там, а не в gordi-issue.py)
ищет слово запросом LIKE вместо casefold(). Портится копия mezo_paths.py В СТЕНДЕ, а не
gordi-issue.py: поломка, оставшаяся в старом месте, молча перестала бы что-либо ломать.
Ждём красным РОВНО ⑤ и ⑤-бис; ①–④ целы (там причина записана строчными).
ТРЕТЬЯ (--porcha common-first): при двух ролях общая функция берёт первую — ждём красным
РОВНО ③-бис. ЧЕТВЁРТАЯ (--porcha common-literal): общая функция отвечает литералом «COORD» —
ждём красным ③-бис и ④ (координатор TAXO перестаёт писать).
ПЯТАЯ (--porcha seed-without-clear, карточка #699): портится САМ СТЕНД, а не инструмент —
посев прежний: слово «координатор» у ролей копии не снимается, строки, уже бывшие в копии,
не трогаются (ON CONFLICT DO NOTHING). Ждём красным ⓪ в раскладках «dominal» и «никто не
назван»; «Atlas» цела. ①–⑤ на копии живого Atlas целы (там слово стоит у COORD — прежний
посев его и не трогал); на копии контура, где слово у другой роли (у dominal — 3P), под
этой поломкой краснеют и они — это и была беда issue #40.

⛔ Живой базы не касается: работает на КОПИИ (backup API) в своём временном контейнере
(структура `<конт>/.mezosync/mezosync.db`, опознаётся `MEZO_CONTAINER`). Сеть (`gh`) не
зовётся — все прогоны с `--dry-run`.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402 — испытуемый берётся ЧЕРЕЗ общий помощник (MEZO_SCRIPTS_ROOT),
                    # а не жёстким подъёмом на два каталога (карточка #659, группа F)

CASES = DIFFER = PASSED = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, PASSED
    CASES += 1
    DIFFER += bool(differ)
    PASSED += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


BODY = "## ЗАМЕР\nтест\n## КЛАСС\nтест\n## ПРЕДЛОЖЕНИЕ\nтест\n"

# Нарочные поломки ОБЩЕЙ функции mezo_paths.find_coordinator (карточка #677, этап Э3):
# (якорь — строка самой функции, порча, что печатаем). Якорь обязан найтись РОВНО один раз.
LIKE_ANCHOR = "\"WHERE lifecycle='alive' AND lifecycle_reason IS NOT NULL\")"
LIKE_BROKEN = "\"WHERE lifecycle='alive' AND lifecycle_reason LIKE '%координатор%'\")"
PICK_ANCHOR = "    name = found[0] if len(found) == 1 else None"
COMMON_BREAKS = {
    "revert-to-like": (
        LIKE_ANCHOR, LIKE_BROKEN,
        "🧪 НАРОЧНАЯ ПОЛОМКА «revert-to-like»: ОБЩАЯ функция поиска координатора ищет слово "
        "запросом LIKE (слеп к заглавной кириллице), портится копия mezo_paths.py в стенде. "
        "Ждём красным РОВНО ⑤ и ⑤-бис; ①–④ целы"),
    "common-first": (
        PICK_ANCHOR, "    name = found[0] if found else None",
        "🧪 НАРОЧНАЯ ПОЛОМКА «common-first»: при двух ролях общая функция берёт первую. "
        "Ждём красным РОВНО ③-бис; остальные целы"),
    "common-literal": (
        PICK_ANCHOR, '    name = "COORD" if found else None',
        "🧪 НАРОЧНАЯ ПОЛОМКА «common-literal»: общая функция отвечает литералом «COORD». "
        "Ждём красным ③-бис и ④ (координатор TAXO перестаёт писать); ①②③⑤ целы"),
}

# ═══ ПОСЕВ РОЛЕЙ СТЕНДА (gordipack issue #40, карточка #699) ═══════════════════════════════════
# 🪤 БЕДА. Стенд строится из копии ЖИВОЙ базы испытуемого контура и досевал пять ролей случаев
# через ON CONFLICT DO NOTHING, не снимая слово «координатор» у ролей копии. У Atlas слово стоит
# у COORD — посев с ним совпадал, и беда не видна. У dominal координатор — 3P: на копии названы
# двое (COORD и 3P), и приёмка проваливала 0 из 7 при исправном инструменте.
# ⚖️ ЛЕЧЕНИЕ. Перед посевом слово снимается у ВСЕХ ролей копии (поиск — тем же casefold(), что у
# mezo_paths.find_coordinator, и тем же словом COORDINATOR_WORD), а посев ставит пять ролей
# целиком (ON CONFLICT DO UPDATE): на копии назван ровно COORD, как бы ни был устроен контур.
SEEDED_ROLES = (("COORD", "координатор контура; в живом реестре"),
                ("PROTO", "в живом реестре"), ("TAXO", "в живом реестре"),
                ("CORE", "в живом реестре"), ("STUD", "в живом реестре"))
# 🪤 Тексты снятой пометки НЕ несут корня «координатор» ни в каком виде: «бывший координатор»
# пометку не снимает (поиск смотрит на буквы, а не на смысл).
SEED_REMOVED = "пометка снята стендом приёмки bite-gordi-issue"
LAYOUT_REMOVED = "пометка снята раскладкой стенда bite-gordi-issue"
LAYOUT_MARK = "координатор контура (раскладка стенда bite-gordi-issue)"
# Раскладки исходной копии: кто назван ДО посева. Ставятся целиком на отдельной копии каждая.
STAND_LAYOUTS = (
    ("Atlas", ("COORD",), "слово у COORD"),
    ("dominal", ("3P",), "слово у 3P, у COORD его нет; роль 3P заводится на копии"),
    ("никто не назван", (), "слова нет ни у кого"),
)


def clear_coordinator_word(con, removed_text):
    """Снимает слово «координатор» у ВСЕХ ролей копии (живых и нет) — заменой причины целиком."""
    rows = con.execute("SELECT role, lifecycle_reason FROM roles "
                       "WHERE lifecycle_reason IS NOT NULL").fetchall()
    for role, reason in rows:
        if mezo_paths.COORDINATOR_WORD in reason.casefold():
            con.execute("UPDATE roles SET lifecycle_reason=? WHERE role=?", (removed_text, role))


def seed_roles(db, clear=True):
    """Посев пяти ролей случаев. clear=False — прежний посев (нарочная поломка seed-without-clear):
    слово у ролей копии не снимается, бывшие в копии строки не трогаются."""
    con = sqlite3.connect(str(db))
    try:
        if clear:
            clear_coordinator_word(con, SEED_REMOVED)
            conflict = ("ON CONFLICT(role) DO UPDATE SET lifecycle='alive', "
                        "lifecycle_reason=excluded.lifecycle_reason")
        else:
            conflict = "ON CONFLICT(role) DO NOTHING"
        for role, reason in SEEDED_ROLES:
            con.execute("INSERT INTO roles (role, lifecycle, lifecycle_reason) "
                        f"VALUES (?, 'alive', ?) {conflict}", (role, reason))
        con.commit()
    finally:
        con.close()


def make_layout_container(stand: Path, label: str, source_db: Path, named) -> Path:
    """Отдельный контейнер с копией исходной базы в раскладке «названы ровно named».
    Раскладка сверяется поиском контура; не встала — None (приёмка не состоялась)."""
    container = stand / f"layout-{label}"
    (container / ".mezosync").mkdir(parents=True, exist_ok=True)
    db = container / ".mezosync" / "mezosync.db"
    src = sqlite3.connect(str(source_db))
    dst = sqlite3.connect(str(db))
    src.backup(dst)
    src.close()
    try:
        clear_coordinator_word(dst, LAYOUT_REMOVED)
        for role in named:
            dst.execute("INSERT INTO roles (role, lifecycle, lifecycle_reason) VALUES (?, 'alive', ?) "
                        "ON CONFLICT(role) DO UPDATE SET lifecycle='alive', "
                        "lifecycle_reason=excluded.lifecycle_reason", (role, LAYOUT_MARK))
        dst.commit()
    finally:
        dst.close()
    got = mezo_paths.find_coordinator(db)
    return container if not got.error and got.found == sorted(named) else None


def call_tool(tool: Path, container: Path, *args):
    r = subprocess.run(
        [sys.executable, "-B", str(tool), "create", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env={**os.environ, "MEZO_CONTAINER": str(container)})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=["revert-to-literal", *COMMON_BREAKS, "seed-without-clear"],
                    help="нарочная поломка: revert-to-literal — вернуть проверку писателя "
                         "к литералу «COORD»; revert-to-like — общая функция поиска координатора "
                         "ищет слово запросом LIKE, слепым к заглавной кириллице; common-first — "
                         "при двух ролях берёт первую; common-literal — отвечает литералом «COORD»; "
                         "seed-without-clear — стенд сеет роли, не сняв слово «координатор» "
                         "у ролей копии")
    a = ap.parse_args()

    # было: live_tool = Path(__file__).resolve().parent.parent / ".mezosync" / "scripts" / "gordi-issue.py"
    # — жёсткий подъём на два каталога верен ТОЛЬКО для живого контура (vnext/prototype
    # лежит внутри контейнера), а в пакете рядом с vnext нет .mezosync вовсе: приёмка
    # игнорировала --target/MEZO_SCRIPTS_ROOT и не находила инструмент никогда (карточка #659).
    live_tool = mezo_target.script("gordi-issue.py")

    stand = Path(tempfile.mkdtemp(prefix="bite-gordi-issue-"))
    try:
        container = stand / "container"
        (container / ".mezosync" / "scripts").mkdir(parents=True, exist_ok=True)
        db = container / ".mezosync" / "mezosync.db"
        src = sqlite3.connect(str(mezo_paths.live_db(__file__)))
        dst = sqlite3.connect(str(db))
        src.backup(dst)
        dst.close()
        src.close()

        # ГРУППА F, карточка #659: контур, собранный ЧЕРЕЗ init-group.py пакета, не несёт
        # roster.json — он живёт РЯДОМ с живой базой, не в пакете (см. комментарий шага
        # migrations/20260810-role-lifecycle.py: «реестр ролей живёт рядом с базой, а не
        # в коде шага... нет файла — состояния не выдумываем»). У свежего контура таблица
        # roles потому пуста НЕ ПО ОШИБКЕ продукта — шаг сам честно отказывается выдумать
        # историю без файла (доказано чтением файла шага и PRAGMA table_info на pc-F: 0 строк,
        # тогда как та же таблица живого Atlas несёт 11 строк с roster.json рядом).
        # ⚠️ С 26.09 (пакет 1e4d7c7) init-group.py сам пишет роли из --roles в реестр —
        # но ТОЛЬКО их (обычно одну, координатора), а случаям ниже нужны пять имён.
        # Приёмке нужна СВОЯ раскладка ролей для случаев ①–⑤ — досеваем РОВНО те роли, которых
        # случаи касаются, той же формы, что и у живого roster.json (COORD — координатор,
        # остальные — рядовые).
        # ⚰️ Было: ON CONFLICT DO NOTHING без снятия слова — «если строки уже настоящие, не
        # трогаем». Верно только там, где настоящий координатор и есть COORD; у dominal (3P)
        # на копии оказывались двое (gordipack issue #40, карточка #699). Теперь — seed_roles().
        pristine = stand / "pristine.db"   # исходная копия ДО посева — для раскладок случая ⓪
        src = sqlite3.connect(str(db))
        dst = sqlite3.connect(str(pristine))
        src.backup(dst)
        dst.close()
        src.close()
        seed_roles(db, clear=a.porcha != "seed-without-clear")

        # копия скриптов рядом — gordi-issue.py лениво импортирует mezo_paths из своего
        # каталога через sys.path.insert(parent); кладём инструмент и mezo_paths РЯДОМ
        scripts_dir = stand
        tool = scripts_dir / "gordi-issue.py"
        shutil.copy2(live_tool, tool)
        shutil.copy2(mezo_paths.__file__, scripts_dir / "mezo_paths.py")

        body_file = stand / "issue.md"
        body_file.write_text(BODY, encoding="utf-8")

        if a.porcha == "revert-to-literal":
            # 🎯 Порча возвращает ИМЕННО литерал карточки #645: отказ при неоднозначном
            # координаторе заменён на безусловный запасной «COORD» — сам поиск в данных
            # (roles.lifecycle_reason) остаётся исправным. ①②④ целы: там ровно ОДНА
            # живая роль-координатор, путь через None не задействован вовсе.
            # ③ и ③-бис — единственные, где найдено НЕ РОВНО ОДНА роль: под порчей
            # они молча получают «COORD» вместо отказа — вот они и краснеют.
            text = tool.read_text(encoding="utf-8")
            old = ('    if coordinator is None:\n'
                   '        sys.exit(f"⛔ координатор контура НЕ ОПРЕДЕЛЁН ОДНОЗНАЧНО: {source}")')
            new = '    if coordinator is None:\n        coordinator = "COORD"  # литерал (поломка карточки #645)'
            assert text.count(old) == 1, f"поломка НЕ ЛЕГЛА: найдено {text.count(old)}"
            tool.write_text(text.replace(old, new), encoding="utf-8")
            print("🧪 НАРОЧНАЯ ПОЛОМКА «revert-to-literal»: без ровно одной роли-координатора "
                  "снова подставляется литерал «COORD» БЕЗ отказа. Ждём красным РОВНО ③ и "
                  "③-бис; ①②④ целы (там всегда ровно одна роль, путь через литерал не "
                  "задействован)\n")

        if a.porcha in COMMON_BREAKS:
            # 🎯 Порча кладётся в КОПИЮ ОБЩЕЙ ФУНКЦИИ (mezo_paths.py рядом с копией инструмента:
            # инструмент берёт модуль из своего каталога), а не в gordi-issue.py. С карточки #677
            # (этап Э3) отбор координатора живёт в mezo_paths.find_coordinator, и прежняя
            # поломка «регистр не сворачивается», оставленная в gordi-issue.py, молча
            # перестала бы что-либо ломать: искать там стало бы нечего.
            # revert-to-like возвращает ВТОРУЮ половину карточки #645 — запрос LIKE (в SQLite
            # он сворачивает регистр только у латиницы): краснеют РОВНО ⑤ и ⑤-бис (причина с
            # заглавной кириллицы); ①–④ целы, там причина записана строчными.
            anchor, broken, said = COMMON_BREAKS[a.porcha]
            shared_copy = scripts_dir / "mezo_paths.py"
            shared_text = shared_copy.read_text(encoding="utf-8")
            assert shared_text.count(anchor) == 1, (
                f"поломка НЕ ЛЕГЛА: найдено {shared_text.count(anchor)}")
            shared_copy.write_text(shared_text.replace(anchor, broken), encoding="utf-8")
            print(said + "\n")

        if a.porcha == "seed-without-clear":
            print("🧪 НАРОЧНАЯ ПОЛОМКА «seed-without-clear»: стенд сеет роли прежним посевом — слово "
                  "«координатор» у ролей копии не снимается, бывшие строки не трогаются. Ждём провала "
                  "⓪ в раскладках «dominal» и «никто не назван»; «Atlas» цела. ①–⑤ на копии живого "
                  "Atlas целы; на копии контура, где слово у другой роли, проваливаются и они\n")

        # ⓪ СТЕНД: три раскладки исходной копии — после посева назван РОВНО COORD, и COORD пишет
        for label, named, words in STAND_LAYOUTS:
            layout_container = make_layout_container(stand, label, pristine, named)
            if layout_container is None:
                print(f"⛔ ПРИЁМКА НЕ СОСТОЯЛАСЬ: раскладка «{label}» ({words}) не встала на копии "
                      f"базы — мерить нечем")
                return 2
            layout_db = layout_container / ".mezosync" / "mezosync.db"
            seed_roles(layout_db, clear=a.porcha != "seed-without-clear")
            seeded = mezo_paths.find_coordinator(layout_db)
            code0, out0 = call_tool(tool, layout_container, "--role", "COORD", "--title", "t",
                                    "--body-file", str(body_file), "--dry-run")
            case(f"⓪ стенд, раскладка «{label}» ({words}): после посева назван ровно COORD, "
                 f"и COORD пишет" + (" (контроль)" if label == "Atlas" else ""),
                 seeded.found == ["COORD"] and code0 == 0 and "⟨ВХОЛОСТУЮ⟩" in out0,
                 f"после посева названо: {', '.join(seeded.found) or 'никого'} (ждём COORD) · "
                 f"код {code0}" + ("" if code0 == 0 else f" · отказ: {out0.strip()[:160]}"),
                 differ=label != "Atlas")

        # ① координатор из данных (сейчас — COORD) пишет
        code1, out1 = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                "--body-file", str(body_file), "--dry-run")
        case("① координатор из данных (COORD) пишет — проверка писателя пропускает (контроль)",
             code1 == 0 and "⟨ВХОЛОСТУЮ⟩" in out1,
             f"код {code1}")

        # ② НЕ координатор отказан, отказ называет НАСТОЯЩЕГО координатора
        code2, out2 = call_tool(tool, container, "--role", "PROTO", "--title", "t",
                                "--body-file", str(body_file), "--dry-run")
        case("② не координатор отказан, отказ НАЗЫВАЕТ настоящего координатора",
             code2 != 0 and "координатор COORD" in out2,
             f"код {code2} · координатор назван: {'да' if 'координатор COORD' in out2 else 'НЕТ'}",
             differ=True)

        # ③ данные НЕ НАЗЫВАЮТ НИ ОДНОЙ роли-координатора (карточка #645, критерий ①):
        # НЕ подставляем литерал — ОТКАЗ словами, называющий, что найдено (0 ролей),
        # и как назвать координатора в контуре (готовая команда/запрос).
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='в живом реестре' WHERE role='COORD'")
        con.commit()
        con.close()
        code3, out3 = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                "--body-file", str(body_file), "--dry-run")
        case("③ данные не называют НИ ОДНОЙ роли-координатора → ОТКАЗ (не литерал), "
             "названо «найдено 0» и готовая команда проверки",
             code3 != 0 and "найдено 0" in out3 and "set-rule.py" in out3
             and "COORD" not in out3.split("⛔")[-1].split("найдено")[0],
             f"код {code3} · вывод: {out3.strip()[:250]}", differ=True)

        # ③-бис данные называют ДВЕ роли-координатора разом → ОТКАЗ, названы ОБЕ
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='координатор (проба множественности)' "
                    "WHERE role IN ('CORE', 'STUD')")
        con.commit()
        con.close()
        code3b, out3b = call_tool(tool, container, "--role", "CORE", "--title", "t",
                                  "--body-file", str(body_file), "--dry-run")
        case("③-бис данные называют ДВЕ роли-координатора разом → ОТКАЗ, названы ОБЕ",
             code3b != 0 and "найдено 2" in out3b and "CORE" in out3b and "STUD" in out3b,
             f"код {code3b} · вывод: {out3b.strip()[:250]}", differ=True)

        # снять пробу множественности перед случаем ④ — иначе у него окажется НЕ ОДНА роль.
        # ⚠️ Текст сброса НЕ ДОЛЖЕН нести подстроку «координатор» ни в каком виде (даже
        # отрицанием) — LIKE '%координатор%' слеп к смыслу слова, судит только буквы.
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='рядовая зона контура' "
                    "WHERE role IN ('CORE', 'STUD')")
        con.commit()
        con.close()

        # ④ ГЛАВНЫЙ ВСТРЕЧНЫЙ: координатор данных — ДРУГАЯ роль (TAXO), не «COORD».
        # Без этого случая правка неотличима от разбора данных «для галочки»: если бы
        # источник данных не влиял на решение, ①②③ остались бы теми же, а этот — нет.
        con = sqlite3.connect(str(db))
        con.execute("UPDATE roles SET lifecycle_reason='координатор контура; проба' "
                    "WHERE role='TAXO'")
        con.commit()
        con.close()
        code4a, out4a = call_tool(tool, container, "--role", "TAXO", "--title", "t",
                                  "--body-file", str(body_file), "--dry-run")
        code4b, out4b = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                  "--body-file", str(body_file), "--dry-run")
        case("④ ГЛАВНЫЙ ВСТРЕЧНЫЙ: координатор в данных — TAXO → TAXO пишет, буквальный "
             "«COORD» — уже НЕТ",
             code4a == 0 and code4b != 0 and "координатор TAXO" in out4b,
             f"TAXO код {code4a} · COORD код {code4b} · координатор назван TAXO в отказе: "
             f"{'да' if 'координатор TAXO' in out4b else 'НЕТ'}", differ=True)

        # ⑤ и ⑤-бис РЕГИСТР КИРИЛЛИЦЫ (возврат COORD по карточке #645, 2026-09-15):
        # причина роли начинается с заглавной — обычное начало фразы. Запрос LIKE такую
        # причину НЕ находил, и координатор становился «не найден» на ровном месте.
        for mark, reason in (("⑤", "Координатор контура; проба заглавной"),
                             ("⑤-бис", "КООРДИНАТОР КОНТУРА; ПРОБА ПРОПИСНЫХ")):
            con = sqlite3.connect(str(db))
            con.execute("UPDATE roles SET lifecycle_reason='рядовая зона контура' "
                        "WHERE role='TAXO'")
            con.execute("UPDATE roles SET lifecycle_reason=? WHERE role='COORD'", (reason,))
            con.commit()
            con.close()
            code5, out5 = call_tool(tool, container, "--role", "COORD", "--title", "t",
                                    "--body-file", str(body_file), "--dry-run")
            case(f"{mark} причина «{reason[:28]}…» — слово найдено, писатель пропущен",
                 code5 == 0 and "⟨ВХОЛОСТУЮ⟩" in out5,
                 f"код {code5} · отказ: {'нет' if code5 == 0 else out5.strip()[:120]}",
                 differ=True)

        print("")
        print(f"ИТОГ: {PASSED} из {CASES} · различающих {DIFFER}")
        return 0 if PASSED == CASES else 1
    finally:
        shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
