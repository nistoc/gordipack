# -*- coding: utf-8 -*-
r"""ПРИЁМКА сверки часа слова владельца с НАЗВАННЫМ чатом — карточка #777.

ПОВОД (замер STUD 13.11, записка #6455 §②). Слово владельца лежало в пяти чатах с пятью
часами. `owner-word.py add` сверял час с ПЕРВОЙ находкой искателя, а чат из --chat в сверке
не участвовал: верный час СВОЕГО чата получал отказ, а ЧУЖОЙ час под своим чатом ложился
в хранилище с подписью «час сверен с записью ЗНАК В ЗНАК».

⛔ ЖИВОЙ БАЗЫ И НАСТОЯЩИХ ЗАПИСЕЙ РАЗГОВОРОВ НЕ КАСАЕТСЯ. База — схема живой БЕЗ строк
(mezo_stand.empty_db) плюс три строки role_sessions, посаженные приёмкой. Записи разговоров —
ДВА подставных файла под подставным домашним каталогом; искатель запускается НАСТОЯЩИЙ
(копия рядом с испытуемым), поэтому печатную форму его находок приёмка не выдумывает.

Какую копию испытываем — тем же рычагом, что у соседних приёмок (карточка #148):
MEZO_SCRIPTS_ROOT (mezo_target.py).

Порядок находок у искателя — по часу, поэтому ПЕРВОЙ стоит находка ЧУЖОГО чата (CORE 12:54:01),
второй — своего (STUD 12:54:24): ровно так было у STUD 13.11.

Случаи (различающий = обязан ответить ИНАЧЕ на поломанной копии):
  ① верный час СВОЕГО чата записывается: --said-at 12:54:24 --chat STUD → код 0, в базе
    said_at 12:54:24 и chat STUD, подпись «сверен … В НАЗВАННОМ ЧАТЕ STUD»          РАЗЛИЧАЮЩИЙ
  ② чужой час при названном чате отказывает: --said-at 12:54:01 --chat STUD → код 2, строк
    не прибавилось, чужой чат назван именем роли (CORE), подписи «сверен» нет        РАЗЛИЧАЮЩИЙ
  ③ несколько совпадений В ОДНОМ чате (12:30 и 13:10 в чате STUD): час мимо обоих → код 2,
    напечатаны ОБА часа и сказано, что выбор за ролью; названный один из них → код 0 и
    записан именно он                                                                РАЗЛИЧАЮЩИЙ
  ④ подпись «сверен» — только после сверки с названным чатом: --chat TAXO (у TAXO записей
    с этим текстом нет) → код 2, «НЕ найден», подписи нет, строк не прибавилось      РАЗЛИЧАЮЩИЙ
  ⑥ многострочный текст своего чата → код 0, подпись есть                           КОНТРОЛЬ
  ⑦ чат, которого база не знает (--chat НИКТО) → код 2 ДО запуска искателя, строк 0  КОНТРОЛЬ
  ⑧ --chat префиксом записи (8 знаков) работает как имя роли: код 0, chat — префикс  РАЗЛИЧАЮЩИЙ
  ⑨ --finder на несуществующий файл → «сверить дословность нечем», код 2, строк 0    КОНТРОЛЬ
  ⑩ ОБРАТНЫЙ ХОД, ПРЕДВАРИТЕЛЬНЫЙ: поломанная копия ЗАПУСТИЛАСЬ (⑥ на ней проходит)
  ⑪ ОБРАТНЫЙ ХОД: в копии сверка возвращена к ПЕРВОМУ совпадению (чат не участвует) —
    провалиться обязаны РОВНО ①, ②, ③, ④, ⑧; целы ⑥, ⑦, ⑨. Якорь поломки ищется точной
    строкой и встречается РОВНО ОДИН раз.

Зовут так (MEZO_LIVE_DB — только источник схемы):
    MEZO_SCRIPTS_ROOT=<каталог испытуемой копии> MEZO_LIVE_DB=<живая база> \
        python vnext/prototype/bite-owner-word-chat.py
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand    # noqa: E402
import mezo_target   # noqa: E402

BREAK_FIRST = [
    ("        mine = [sorted({s for s, p, _ in fl if p in prefixes}) for fl in per_line]",
     "        mine = [sorted({fl[0][0]}) if fl else [] for fl in per_line]  # поломка: первое совпадение")]

PROJECT = "C--guts--atlas"
STUD_T = "5a5a5a5a-1111-2222-3333-444444444444"
CORE_T = "c0c0c0c0-1111-2222-3333-444444444444"
TAXO_T = "7a7a7a7a-1111-2222-3333-444444444444"
ROLES = [("STUD", STUD_T), ("CORE", CORE_T), ("TAXO", TAXO_T)]

T_TWO = "проба часа в двух чатах кедр"
T_SAME = "проба двух ответов в одном чате ольха"
T_MULTI = "первая строка пробы клён\nвторая строка пробы клён"
RECORDS = {
    STUD_T: [("2026-11-13T12:54:24.005Z", T_TWO),
             ("2026-11-13T12:30:00.100Z", T_SAME),
             ("2026-11-13T13:10:00.200Z", T_SAME),
             ("2026-11-13T12:40:00.300Z", T_MULTI)],
    CORE_T: [("2026-11-13T12:54:01.503Z", T_TWO)],
}
UTC = " UTC"

print(f"⚖️ испытуется: {mezo_target.label()}")
tool = mezo_target.script("owner-word.py")
finder = mezo_target.script("find-owner-word.py")

failures = []


def check(num, ok, said):
    """Записать исход случая. Печатает ВСЕГДА — и когда прошёл, и когда нет."""
    print(f"{'✅' if ok else '🔴'} {num} {said}")
    if not ok:
        failures.append(f"{num} {said}")
    return ok


def record(ts, text):
    """Подставная запись разговора: реплика, набранная человеком (поле origin)."""
    return json.dumps({"type": "user", "timestamp": ts, "message": {"content": text},
                       "origin": {"kind": "human"}}, ensure_ascii=False)


def rows(db):
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT said_at, chat, verified_by FROM owner_words").fetchall()
    finally:
        conn.close()


stand = mezo_stand.new("bite-owner-word-chat")
try:
    live = mezo_target.scripts_root().parent / "mezosync.db"
    if os.environ.get("MEZO_LIVE_DB"):
        live = Path(os.environ["MEZO_LIVE_DB"])
    if not live.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: схему подставной базы брать неоткуда — нет {live}")
        print("   Это НЕ «сломано» и НЕ «в порядке»: испытывать нечего. Назови MEZO_LIVE_DB.")
        sys.exit(mezo_stand.finish(2))
    template = stand / "template.db"
    mezo_stand.empty_db(live, template)
    conn = sqlite3.connect(str(template))
    try:
        for role, tid in ROLES:
            conn.execute("INSERT INTO role_sessions (role, address, noted_by, source, transcript_id)"
                         " VALUES (?,?,?,?,?)", (role, f"стенд {role}", "ОПЫТ", "self", tid))
        conn.commit()
    finally:
        conn.close()

    home = stand / "home"
    chats = home / ".claude" / "projects" / PROJECT
    chats.mkdir(parents=True)
    for tid, recs in RECORDS.items():
        (chats / f"{tid}.jsonl").write_text(
            "\n".join(record(ts, text) for ts, text in recs) + "\n", encoding="utf-8")

    seq = [0]

    def fresh_db():
        seq[0] += 1
        d = stand / f"case-{seq[0]}.db"
        shutil.copyfile(template, d)
        return d

    def make_copy(kind, breaks=None):
        d = stand / f"tool-{kind}"
        copy = mezo_stand.copy_tool(tool, d)
        mezo_stand.copy_tool(finder, d)
        if breaks:
            text = copy.read_text(encoding="utf-8")
            for anchor, repl in breaks:
                text = text.replace(anchor, repl)
            copy.write_text(text, encoding="utf-8")
        return copy

    def add(copy, db, text, said, chat, finder_path=None):
        """add на стенде. Возвращает (код, весь вывод, строк до, строк после)."""
        env = mezo_stand.stand_env(stand, PYTHONIOENCODING="utf-8")
        env["USERPROFILE"] = str(home)
        env["HOME"] = str(home)
        before = len(rows(db))
        args = [sys.executable, "-X", "utf8", str(copy), "--db", str(db)]
        if finder_path:
            args += ["--finder", str(finder_path)]
        args += ["add", "--said-at", said + UTC, "--chat", chat, "--text", text,
                 "--heard-by", "ОПЫТ"]
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           cwd=str(stand), env=env)
        return r.returncode, (r.stdout or "") + (r.stderr or ""), before, len(rows(db))

    def case_own(copy):
        db = fresh_db()
        code, out, b, a = add(copy, db, T_TWO, "2026-11-13 12:54:24", "STUD")
        got = rows(db)
        ok = (code == 0 and a == b + 1 and got and got[-1][0] == "2026-11-13 12:54:24 UTC"
              and got[-1][1] == "STUD" and "В НАЗВАННОМ ЧАТЕ STUD" in out and "сверен" in out)
        return ok, (f"верный час своего чата: код {code} (ждали 0) · строк {b}→{a} · "
                    f"записано {got[-1][:2] if got else '—'}")

    def case_foreign(copy):
        db = fresh_db()
        code, out, b, a = add(copy, db, T_TWO, "2026-11-13 12:54:01", "STUD")
        ok = (code == 2 and a == b and "CORE" in out and "НЕ годится" in out
              and "сверен" not in out)
        return ok, (f"чужой час при --chat STUD: код {code} (ждали 2) · строк {b}→{a} · "
                    f"чужой чат назван CORE: {'да' if 'CORE' in out else 'НЕТ'} · подпись «сверен»: "
                    f"{'ЕСТЬ' if 'сверен' in out else 'нет'}")

    def case_choice(copy):
        db = fresh_db()
        c1, out1, b1, a1 = add(copy, db, T_SAME, "2026-11-13 12:45:00", "STUD")
        both = "2026-11-13 12:30:00 UTC" in out1 and "2026-11-13 13:10:00 UTC" in out1
        c2, out2, b2, a2 = add(copy, db, T_SAME, "2026-11-13 13:10:00", "STUD")
        got = rows(db)
        ok = (c1 == 2 and a1 == b1 and both and "ВЫБОР ЗА РОЛЬЮ" in out1
              and c2 == 0 and a2 == b2 + 1 and got and got[-1][0] == "2026-11-13 13:10:00 UTC"
              and "совпадений 2" in out2)
        return ok, (f"два совпадения в одном чате: час мимо → код {c1} (ждали 2), оба часа "
                    f"напечатаны: {'да' if both else 'НЕТ'} · названный 13:10 → код {c2} "
                    f"(ждали 0), записано {got[-1][0] if got else '—'}")

    def case_signature(copy):
        db = fresh_db()
        code, out, b, a = add(copy, db, T_TWO, "2026-11-13 12:54:01", "TAXO")
        ok = code == 2 and a == b and "НЕ найден" in out and "сверен" not in out
        return ok, (f"--chat TAXO, у которого текста нет: код {code} (ждали 2) · строк {b}→{a} · "
                    f"подпись «сверен»: {'ЕСТЬ' if 'сверен' in out else 'нет'}")

    def case_multi(copy):
        db = fresh_db()
        code, out, b, a = add(copy, db, T_MULTI, "2026-11-13 12:40:00", "STUD")
        ok = code == 0 and a == b + 1 and "сверен" in out
        return ok, f"многострочный текст своего чата: код {code} (ждали 0) · строк {b}→{a}"

    def case_unknown(copy):
        db = fresh_db()
        code, out, b, a = add(copy, db, T_TWO, "2026-11-13 12:54:24", "НИКТО")
        ok = (code == 2 and a == b and "базе неизвестен" in out
              and "СВЕРКА ДОСЛОВНОСТИ" not in out)
        return ok, (f"чат НИКТО: код {code} (ждали 2) · строк {b}→{a} · искатель запускался: "
                    f"{'ДА' if 'СВЕРКА ДОСЛОВНОСТИ' in out else 'нет'}")

    def case_prefix(copy):
        db = fresh_db()
        code, out, b, a = add(copy, db, T_TWO, "2026-11-13 12:54:24", STUD_T[:8])
        got = rows(db)
        ok = (code == 0 and a == b + 1 and got and got[-1][1] == STUD_T[:8]
              and got[-1][0] == "2026-11-13 12:54:24 UTC")
        return ok, (f"--chat {STUD_T[:8]}: код {code} (ждали 0) · записано "
                    f"{got[-1][:2] if got else '—'}")

    def case_nofinder(copy):
        db = fresh_db()
        code, out, b, a = add(copy, db, T_TWO, "2026-11-13 12:54:24", "STUD",
                              finder_path=stand / "нет-такого" / "find-owner-word.py")
        ok = code == 2 and a == b and "сверить дословность нечем" in out
        return ok, f"искателя нет: код {code} (ждали 2) · строк {b}→{a}"

    CASES = [("①", case_own), ("②", case_foreign), ("③", case_choice), ("④", case_signature),
             ("⑥", case_multi), ("⑦", case_unknown), ("⑧", case_prefix), ("⑨", case_nofinder)]

    print(f"   стенд: записей разговоров {sum(len(v) for v in RECORDS.values())} в двух чатах; "
          "искатель настоящий; живая база только источник схемы")
    healthy = make_copy("healthy")
    for num, fn in CASES:
        ok, said = fn(healthy)
        check(num, ok, said)

    text = healthy.read_text(encoding="utf-8")
    bad = [(a_, text.count(a_)) for a_, _ in BREAK_FIRST if text.count(a_) != 1]
    if bad:
        print(f"🔴 ОБРАТНЫЙ ХОД: ЯКОРЬ НЕ НАЙДЕН РОВНО ОДИН РАЗ (нашлось {bad[0][1]}) — "
              "поломка не построена. Это НЕ «защита цела».")
        failures.append("обратный ход: якорь не найден ровно один раз")
    else:
        broken = make_copy("first", BREAK_FIRST)
        started, said = case_multi(broken)
        check("⑩", started, f"поломанная копия запустилась: {said}")
        red = []
        for num, fn in CASES:
            ok, said = fn(broken)
            print(f"   · на поломке {num}: {'прошёл' if ok else 'провалился'} — {said}")
            if not ok:
                red.append(num)
        want = ["①", "②", "③", "④", "⑧"]
        check("⑪", started and red == want,
              f"ОБРАТНЫЙ ХОД (сверка по первому совпадению): провалились "
              f"{', '.join(red) or 'никто'} (ждали ровно {', '.join(want)})")

    print()
    total = len(CASES) + 2
    print(f"ИТОГ: {max(total - len(failures), 0)} из {total}")
    if failures:
        print(f"🔴 ПРОВАЛИЛОСЬ случаев: {len(failures)}")
        for f in failures:
            print(f"   · {f}")
        sys.exit(mezo_stand.finish(1))
    print("✅ ВСЕ СЛУЧАИ ПРОШЛИ — час сверяется среди находок названного чата, чужой час под своим "
          "чатом не записывается, несколько совпадений в чате печатаются все, подпись «сверен» "
          "стоит только после сверки с названным чатом; поломка валит ровно свои случаи.")
    print("⛔ Чего приёмка НЕ доказывает: ветку «час в выводе искателя не распознан» (настоящий "
          "искатель час печатает всегда); полноту role_sessions_history — чат роли, чья запись "
          "туда не попала, приёмка не изображает; чаты, продолженные в новый файл записи.")
    sys.exit(mezo_stand.finish(0))
finally:
    mezo_stand.release(stand)
