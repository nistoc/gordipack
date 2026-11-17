# -*- coding: utf-8 -*-
r"""ПРИЁМКА адреса источника у слова владельца — карточка #795.

ПОВОД. До карточки #795 у 20 слов из 20 в хранилище не было ни файла записи разговора, ни
номера строки: ключи --source-file и --source-line роль набирала руками, и набирать их было
неоткуда. Искатель находил текст и час, но адреса не печатал. Теперь искатель печатает под
строкой «чат:» строку «файл: <полный путь>:<номер строки>», owner-word.py add берёт адрес
из той же находки, что и час, а owner-word.py source дописывает адрес уже записанным словам.

⛔ ЖИВОЙ БАЗЫ И НАСТОЯЩИХ ЗАПИСЕЙ РАЗГОВОРОВ НЕ КАСАЕТСЯ. База — схема живой БЕЗ строк
(mezo_stand.empty_db) плюс две строки role_sessions, посаженные приёмкой. Записи разговоров —
ДВА подставных файла под подставным домашним каталогом; искатель запускается НАСТОЯЩИЙ
(копия рядом с испытуемым), поэтому печатную форму его находок приёмка не выдумывает.
Перед репликами владельца в файлах лежат строки ответов, чтобы номер строки не совпадал
с порядковым номером реплики.

Какую копию испытываем — тем же рычагом, что у соседних приёмок (карточка #148):
MEZO_SCRIPTS_ROOT (mezo_target.py).

Случаи (различающий = обязан ответить ИНАЧЕ на поломанной копии):
  ① искатель печатает адрес, и адрес верен: под КАЖДОЙ строкой «чат:» стоит строка
    «файл: <путь>:<N>», файл существует, это файл того чата, и N — номер строки ИМЕННО этой
    реплики (строка содержит текст). Текст в двух чатах — два разных адреса; один текст ДВАЖДЫ
    в одном чате с разными часами — тоже два разных адреса (находка TAXO 1)         РАЗЛИЧАЮЩИЙ
  ② add берёт адрес сам: (а) без ключей → код 0, записан адрес из находки искателя;
    (б) искатель без строки «файл:» → код 2, «нет адреса», строк не прибавилось;
    (в) --source-line, расходящийся с находкой → код 2, «РАСХОДИТСЯ», строк не прибавилось;
    (г) ключи, совпадающие с находкой → код 0;
    (д) час ВТОРОЙ реплики того же текста в том же чате → записан адрес второй реплики;
    (е) искатель печатает исход без часа → код 2, «не распознан», строк не прибавилось
        (замечание TAXO: прежде эта ветка писала слово без адреса с кодом 0)         РАЗЛИЧАЮЩИЙ
  ③ source дописывает адрес записанным словам: (а) холостой прогон — база не изменилась
    ни в одной строке, найденный адрес назван; (б) --apply — адрес записан у слова с находкой,
    слово без находки названо с причиной и не тронуто, слово с ДРУГИМ записанным файлом
    названо «РАСХОДИТСЯ» и не перезаписано, код 1 (часть слов без адреса);
    (в) повторный вызов по номеру — «адрес уже есть», код 0;
    (г) слово с часом второй реплики того же текста — записан адрес второй реплики;
    (д) искателя нет по пути — причина «искатель не найден», а не «текст не найден»;
    (е) каталога записей разговоров нет (искатель: код 2) — причина «искать негде»
        (находка TAXO 2)                                                           РАЗЛИЧАЮЩИЙ
  ④ ОБРАТНЫЙ ХОД — семь поломок, каждая обязана провалить РОВНО свои случаи:
    П1 искатель считает строки со сдвигом на одну — ровно ①
    П2 add не берёт адрес из находки — ровно ②
    П3 холостой прогон source пишет в базу — ровно ③
    МА адрес — у первой находки чата, час не смотрим (owner-word.py, sources_of) — ровно ② и ③:
       функция общая у add и source
    МД искатель ключует адрес без часа (find-owner-word.py) — ровно ①
    П4 source называет причину постоянным текстом «текст не найден» — ровно ③
    П5 ветка «час не распознан» пишет слово, как прежде — ровно ②
    МА и МД построены TAXO на её стенде (приёмка pull request 91, 17.11 00:25 UTC); МД здесь
    одним якорем: адрес берётся у первой записи того же файла и текста, ключ прежний.
  У каждой поломки якорь ищется точной строкой и встречается РОВНО ОДИН раз; каждая копия
  обязана запуститься (искатель находит текст, owner-word.py list отвечает кодом 0).

Зовут так (MEZO_LIVE_DB — только источник схемы):
    MEZO_SCRIPTS_ROOT=<каталог испытуемой копии> MEZO_LIVE_DB=<живая база> \
        python vnext/prototype/bite-owner-word-source.py
"""
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand    # noqa: E402
import mezo_target   # noqa: E402

BREAK_LINE = [   # П1, в искателе
    ("        for lineno, line in enumerate(fh, 1):",
     "        for lineno, line in enumerate(fh, 2):  # поломка: строки считаются со сдвигом")]
BREAK_ADD = [    # П2, в owner-word.py
    ("        src_file, src_line = settle_source(sources_of(per_line, prefixes, a.said_at), a)",
     "        pass  # поломка: add не берёт адрес из находки")]
BREAK_DRY = [    # П3, в owner-word.py
    ("    if a.apply and planned:",
     "    if planned:  # поломка: холостой прогон пишет")]
BREAK_MA = [     # МА, в owner-word.py: адрес у первой находки чата, час не смотрим
    ("            if p in prefixes and s == said_at:",
     "            if p in prefixes:  # поломка МА: адрес первой находки чата, час не смотрим")]
BREAK_MD = [     # МД, в искателе: адрес по файлу и тексту, без часа
    ('            addr.setdefault((ts, f.name, text), (f.resolve().as_posix(), where.get("line")))',
     '            addr.setdefault((ts, f.name, text), next((v for k, v in addr.items() if k[1:] == (f.name, text)),'
     ' (f.resolve().as_posix(), where.get("line"))))  # поломка МД: адрес без часа')]
BREAK_REASON = [  # П4, в owner-word.py: причина постоянным текстом, как до находки TAXO 2
    ("            left.append((n, unverified_reason(report, said_at[:10])))",
     "            left.append((n, f'текст не найден в записях разговоров за {said_at[:10]} '"
     "'(запись могла быть сжата или удалена)'))  # поломка П4")]
BREAK_NOHOUR = [  # П5, в owner-word.py: ветка «час не распознан» пишет слово, как до замечания TAXO
    ("        print(f'   инструментов, а не нехватка данных. Искатель: {a.finder}')\n        sys.exit(2)",
     "        checked, outcome = 'час и чат НЕ сверены: час не распознан', ' | '.join(marks)  # поломка П5")]
OLD_FINDER = [   # искатель, каким он был до карточки #795: строки «файл:» нет
    ('            print(f"   файл: {src[0]}:{src[1]}")',
     '            pass  # старый искатель: строки «файл:» нет')]

PROJECT = "C--guts--atlas"
STUD_T = "5a5a5a5a-1111-2222-3333-444444444444"
CORE_T = "c0c0c0c0-1111-2222-3333-444444444444"
ROLES = [("STUD", STUD_T), ("CORE", CORE_T)]
DAY = "2026-11-13"

T_A = "проба адреса источника сосна"
T_B = "проба адреса в двух чатах дуб"
T_C = "проба дописывания адреса липа"
T_D = "проба расхождения адреса рябина"
T_NONE = "этого текста нет ни в одной записи пихта"
FAR_FILE = "C:/нет-такого/другой-файл.jsonl"
# (час, текст) реплик владельца; None — строка ответа, только чтобы сдвинуть номера строк
RECORDS = {
    STUD_T: [None, None, ("12:10:00", T_A), ("12:15:00", T_B), None, ("12:20:00", T_C),
             ("12:25:00", T_D), None, ("12:30:00", T_A)],   # T_A дважды в одном чате (находка TAXO 1)
    CORE_T: [None, ("12:15:30", T_B)],
}
# Искатель чужой формы: исход без часа (для случая ②(е)). Строки «чат:» и «файл:» на месте —
# чтобы отказ шёл именно от часа, а не от пропажи чата или адреса.
STUB_NOHOUR = ('print("📝 НАБРАНО ЧЕЛОВЕКОМ · час не указан")\n'
               'print("   чат: C--guts--atlas / 5a5a5a5a…")\n'
               'print("   файл: C:/нет-такого/запись.jsonl:3")\n')

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


def record(item, n):
    if item is None:
        return json.dumps({"type": "assistant", "timestamp": f"{DAY}T11:00:{n:02d}.000Z",
                           "message": {"content": "строка ответа"}}, ensure_ascii=False)
    hm, text = item
    return json.dumps({"type": "user", "timestamp": f"{DAY}T{hm}.123Z", "message": {"content": text},
                       "origin": {"kind": "human"}}, ensure_ascii=False)


def rows(db):
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        return conn.execute("SELECT id, said_at, chat, text_verbatim, source_file, source_line, "
                            "verified_by FROM owner_words ORDER BY id").fetchall()
    finally:
        conn.close()


def same_file(x, y):
    try:
        return bool(x) and bool(y) and os.path.samefile(x, y)
    except OSError:
        return False


stand = mezo_stand.new("bite-owner-word-source")
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
    truth = {}   # (текст, префикс чата, час) → (файл, номер строки) — где реплика лежит НА САМОМ ДЕЛЕ
    for tid, recs in RECORDS.items():
        path = chats / f"{tid}.jsonl"
        path.write_text("\n".join(record(r, i) for i, r in enumerate(recs)) + "\n", encoding="utf-8")
        for i, r in enumerate(recs, 1):
            if r is not None:
                truth[(r[1], tid[:8], r[0])] = (path, i)
    stub_nohour = stand / "stub-finder-nohour.py"
    stub_nohour.write_text(STUB_NOHOUR, encoding="utf-8")
    bare_home = stand / "home-without-records"   # для ③(е): каталога записей разговоров нет
    bare_home.mkdir()

    seq = [0]

    def fresh_db(words=()):
        """Копия пустой базы; words — строки owner_words (said_at, chat, текст, файл, строка)."""
        seq[0] += 1
        d = stand / f"case-{seq[0]}.db"
        shutil.copyfile(template, d)
        if words:
            c = sqlite3.connect(str(d))
            try:
                for said, chat, text, sf, sl in words:
                    c.execute("INSERT INTO owner_words (said_at, chat, text_verbatim, source_file, "
                              "source_line, verified_by, heard_by, noted_at) VALUES (?,?,?,?,?,?,?,?)",
                              (said, chat, text, sf, sl, "посажено приёмкой", "ОПЫТ",
                               f"{DAY} 13:00:00 UTC"))
                c.commit()
            finally:
                c.close()
        return d

    def make_copy(kind, tool_breaks=(), finder_breaks=()):
        d = stand / f"tool-{kind}"
        copy = mezo_stand.copy_tool(tool, d)
        fcopy = mezo_stand.copy_tool(finder, d)
        for target, breaks in ((copy, tool_breaks), (fcopy, finder_breaks)):
            if breaks:
                text = target.read_text(encoding="utf-8")
                for anchor, repl in breaks:
                    text = text.replace(anchor, repl)
                target.write_text(text, encoding="utf-8")
        return copy, fcopy

    def env(home_dir=None):
        e = mezo_stand.stand_env(stand, PYTHONIOENCODING="utf-8")
        e["USERPROFILE"] = str(home_dir or home)
        e["HOME"] = str(home_dir or home)
        return e

    def run(args, home_dir=None):
        r = subprocess.run([sys.executable, "-X", "utf8"] + [str(x) for x in args],
                           capture_output=True, text=True, encoding="utf-8", cwd=str(stand),
                           env=env(home_dir))
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def find(fcopy, text):
        return run([fcopy, "--слово", text, "--за", DAY])

    def addresses(out):
        """[(префикс чата, час находки, строка «файл:» под «чат:» или None)] — по каждой строке
        «чат:» вывода. Час — из ближайшей строки выше с ISO-часом (строка исхода находки)."""
        lines, got, hm = out.splitlines(), [], None
        for i, line in enumerate(lines):
            t = re.search(r"T(\d{2}:\d{2}:\d{2})(?:\.\d+)?Z", line)
            if t:
                hm = t.group(1)
            m = re.match(r"^\s*чат: .+? / ([0-9A-Za-z-]{8})…\s*$", line)
            if not m:
                continue
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            f = re.match(r"^\s*файл: (?P<path>.+):(?P<line>\d+)\s*$", nxt)
            got.append((m.group(1).lower(), hm,
                        (f.group("path"), int(f.group("line"))) if f else None))
        return got

    def printed(fcopy, text, prefix, hm):
        """Адрес, который искатель печатает для находки текста в чате prefix с часом hm."""
        _, out = find(fcopy, text)
        for p, h, addr in addresses(out):
            if p == prefix and h == hm and addr:
                return addr
        return None

    def add(copy, db, text, said, chat="STUD", finder_path=None, keys=()):
        before = len(rows(db))
        args = [copy, "--db", db]
        if finder_path:
            args += ["--finder", finder_path]
        args += ["add", "--said-at", f"{DAY} {said} UTC", "--chat", chat, "--text", text,
                 "--heard-by", "ОПЫТ", *keys]
        code, out = run(args)
        return code, out, before, len(rows(db))

    def case_finder(copy, fcopy):
        parts, ok = [], True
        expected = ((T_A, {(STUD_T[:8], "12:10:00"), (STUD_T[:8], "12:30:00")}),   # дважды в одном чате
                    (T_B, {(STUD_T[:8], "12:15:00"), (CORE_T[:8], "12:15:30")}))   # в двух чатах
        for text, want in expected:
            code, out = find(fcopy, text)
            got = addresses(out)
            seen = {(p, h) for p, h, _ in got}
            good = code == 0 and seen == want and len(got) == len(want)
            for p, h, addr in got:
                real = truth.get((text, p, h))
                if not addr or not real:
                    good = False
                    parts.append(f"{p} {h}: строки «файл:» под «чат:» НЕТ" if not addr
                                 else f"{p} {h}: такой реплики в стенде нет")
                    continue
                path, n = addr
                content = Path(path).read_text(encoding="utf-8").splitlines() if Path(path).is_file() else []
                holds = 0 < n <= len(content) and text in content[n - 1]
                good = good and same_file(path, real[0]) and holds and n == real[1]
                parts.append(f"{p} {h}: строка {n} (на самом деле {real[1]}), текст в ней: "
                             f"{'да' if holds else 'НЕТ'}")
            if not got:
                parts.append(f"«{text[:24]}…»: строк «чат:» нет, код {code}")
            ok = ok and good
        return ok, "искатель печатает адрес под каждой строкой «чат:»: " + " · ".join(parts)

    def case_add(copy, fcopy):
        want = printed(fcopy, T_A, STUD_T[:8], "12:10:00")
        db = fresh_db()
        c1, out1, b1, a1 = add(copy, db, T_A, "12:10:00")
        got = rows(db)
        rec = got[-1] if got and a1 == b1 + 1 else None
        g_a = bool(c1 == 0 and rec and want and same_file(rec[4], want[0]) and rec[5] == want[1]
                   and "📍 адрес источника" in out1)
        db2 = fresh_db()
        c2, out2, b2, a2 = add(copy, db2, T_A, "12:10:00", finder_path=old_copy)
        g_b = c2 == 2 and a2 == b2 and "нет адреса" in out2
        db3 = fresh_db()
        c3, out3, b3, a3 = add(copy, db3, T_A, "12:10:00", keys=("--source-line", "999"))
        g_c = c3 == 2 and a3 == b3 and "РАСХОДИТСЯ" in out3
        db4 = fresh_db()
        keys = ("--source-file", want[0], "--source-line", str(want[1])) if want else ()
        c4, out4, b4, a4 = add(copy, db4, T_A, "12:10:00", keys=keys)
        g_d = bool(want) and c4 == 0 and a4 == b4 + 1
        # (д) один текст дважды в одном чате: час второй реплики — её адрес (находка TAXO 1)
        want2 = printed(fcopy, T_A, STUD_T[:8], "12:30:00")
        db5 = fresh_db()
        c5, out5, b5, a5 = add(copy, db5, T_A, "12:30:00")
        got5 = rows(db5)
        rec5 = got5[-1] if got5 and a5 == b5 + 1 else None
        g_e = bool(c5 == 0 and rec5 and want2 and same_file(rec5[4], want2[0]) and rec5[5] == want2[1])
        # (е) искатель чужой формы — исход без часа: отказ, слово не пишется (замечание TAXO)
        db6 = fresh_db()
        c6, out6, b6, a6 = add(copy, db6, T_A, "12:10:00", finder_path=stub_nohour)
        g_f = c6 == 2 and a6 == b6 and "не распознан" in out6
        ok = g_a and g_b and g_c and g_d and g_e and g_f
        return ok, (f"add берёт адрес сам: (а) без ключей код {c1} (ждали 0), записан "
                    f"{(rec[4], rec[5]) if rec else '—'}, искатель печатает {want} — "
                    f"{'совпало' if g_a else 'НЕ совпало'} · (б) искатель без «файл:» код {c2} (ждали 2), "
                    f"строк {b2}→{a2} · (в) --source-line 999 код {c3} (ждали 2), строк {b3}→{a3} · "
                    f"(г) ключи по находке код {c4} (ждали 0) · (д) час второй реплики того же текста: "
                    f"код {c5}, записан {rec5[5] if rec5 else '—'}, искатель печатает для неё "
                    f"{want2[1] if want2 else '—'} — {'совпало' if g_e else 'НЕ совпало'} · "
                    f"(е) исход без часа: код {c6} (ждали 2), строк {b6}→{a6}")

    def case_source(copy, fcopy):
        words = [(f"{DAY} 12:20:00 UTC", "STUD", T_C, None, None),
                 (f"{DAY} 12:00:00 UTC", "STUD", T_NONE, None, None),
                 (f"{DAY} 12:25:00 UTC", "STUD", T_D, FAR_FILE, None)]
        want = printed(fcopy, T_C, STUD_T[:8], "12:20:00")
        db = fresh_db(words)
        before = rows(db)
        c1, out1 = run([copy, "--db", db, "source"])
        same = rows(db) == before
        g_a = (c1 == 1 and same and "ХОЛОСТОЙ ПРОГОН" in out1
               and "будет записано адресов 1" in out1)
        c2, out2 = run([copy, "--db", db, "source", "--apply"])
        after = {r[0]: r for r in rows(db)}
        w1, w2, w3 = (after.get(r[0]) for r in before)
        g_b = bool(c2 == 1 and want and w1 and same_file(w1[4], want[0]) and w1[5] == want[1]
                   and "адрес источника дописан" in (w1[6] or "")
                   and w2 and w2[4] is None and w2[5] is None
                   and w3 and w3[4] == FAR_FILE and w3[5] is None
                   and f"слово #{before[1][0]}:" in out2 and "РАСХОДИТСЯ" in out2
                   and "записано адресов 1 из 1" in out2)
        c3, out3 = run([copy, "--db", db, "source", str(before[0][0])])
        g_c = c3 == 0 and "адрес уже есть" in out3
        # (г) слово с часом второй реплики того же текста в том же чате (находка TAXO 1)
        want2 = printed(fcopy, T_A, STUD_T[:8], "12:30:00")
        dbg = fresh_db([(f"{DAY} 12:30:00 UTC", "STUD", T_A, None, None)])
        c4, _ = run([copy, "--db", dbg, "source", "--apply"])
        wg = rows(dbg)[0]
        g_d = bool(c4 == 0 and want2 and same_file(wg[4], want2[0]) and wg[5] == want2[1])
        # (д)(е) причина — от отчёта сверки, а не постоянным текстом (находка TAXO 2)
        dbr = fresh_db([(f"{DAY} 12:20:00 UTC", "STUD", T_C, None, None)])
        c5, out5 = run([copy, "--db", dbr, "--finder", stand / "нет-искателя.py", "source"])
        g_e = c5 == 1 and "искатель не найден" in out5 and "текст не найден" not in out5
        c6, out6 = run([copy, "--db", dbr, "source"], home_dir=bare_home)
        g_f = c6 == 1 and "искать негде" in out6 and "текст не найден" not in out6
        ok = g_a and g_b and g_c and g_d and g_e and g_f

        def reason(out):
            return next((ln.strip()[:110] for ln in out.splitlines() if "🔴 слово #" in ln), "—")
        return ok, (f"source: (а) холостой код {c1} (ждали 1), строки базы не изменились: "
                    f"{'да' if same else 'НЕТ'}, адрес назван: {'да' if g_a else 'НЕТ'} · (б) --apply код {c2} (ждали 1), слово с находкой "
                    f"{(w1[4], w1[5]) if w1 else '—'} против {want}, без находки "
                    f"{'не тронуто' if w2 and w2[4] is None else 'ТРОНУТО'}, с другим файлом "
                    f"{'не перезаписано' if w3 and w3[4] == FAR_FILE else 'ПЕРЕЗАПИСАНО'} — "
                    f"{'да' if g_b else 'НЕТ'} · (в) по номеру код {c3} (ждали 0) · (г) час второй реплики: "
                    f"код {c4}, записана строка {wg[5]}, искатель печатает {want2[1] if want2 else '—'} — "
                    f"{'совпало' if g_d else 'НЕ совпало'} · (д) искателя нет: код {c5}, «{reason(out5)}» · "
                    f"(е) записей нет: код {c6}, «{reason(out6)}»")

    CASES = [("①", case_finder), ("②", case_add), ("③", case_source)]

    def started(copy, fcopy):
        code_f, out_f = find(fcopy, T_A)
        code_l, _ = run([copy, "--db", fresh_db(), "list"])
        return code_f == 0 and "чат:" in out_f and code_l == 0, (
            f"искатель код {code_f}, находка {'есть' if 'чат:' in out_f else 'НЕТ'} · list код {code_l}")

    print(f"   стенд: записей разговоров {sum(len(v) for v in RECORDS.values())} строк в "
          f"{len(RECORDS)} чатах; искатель настоящий; живая база только источник схемы")
    healthy, hfinder = make_copy("healthy")
    text = hfinder.read_text(encoding="utf-8")
    if text.count(OLD_FINDER[0][0]) != 1:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: строку «файл:» в искателе не найти ровно один раз "
              f"(нашлось {text.count(OLD_FINDER[0][0])}) — искателя без адреса не построить.")
        print("   Это НЕ «сломано» и НЕ «в порядке»: искатель старше карточки #795 или переписан.")
        sys.exit(mezo_stand.finish(2))
    old_copy = mezo_stand.copy_tool(finder, stand / "old-finder")
    old_copy.write_text(text.replace(*OLD_FINDER[0]), encoding="utf-8")

    for num, fn in CASES:
        ok, said = fn(healthy, hfinder)
        check(num, ok, said)

    def reverse(num, kind, label, tool_breaks, finder_breaks, want):
        """Обратный ход: поломка строится по якорю (ровно одно вхождение), копия обязана
        запуститься, и провалиться обязаны РОВНО случаи want."""
        bad = []
        for breaks, path in ((tool_breaks, healthy), (finder_breaks, hfinder)):
            body = path.read_text(encoding="utf-8")
            bad += [(a_, body.count(a_)) for a_, _ in breaks if body.count(a_) != 1]
        if bad:
            check(num, False, f"ОБРАТНЫЙ ХОД ({label}): ЯКОРЬ НЕ НАЙДЕН РОВНО ОДИН РАЗ "
                  f"(нашлось {bad[0][1]}) — поломка не построена. Это НЕ «защита цела».")
            return
        copy, fcopy = make_copy(kind, tool_breaks, finder_breaks)
        up, up_said = started(copy, fcopy)
        red = []
        for n_, fn in CASES:
            ok, said = fn(copy, fcopy)
            print(f"   · {label}, на поломке {n_}: {'прошёл' if ok else 'провалился'} — {said}")
            if not ok:
                red.append(n_)
        check(num, up and red == want,
              f"ОБРАТНЫЙ ХОД ({label}): провалились {', '.join(red) or 'никто'} "
              f"(ждали ровно {', '.join(want)}) · копия запустилась: {'да' if up else 'НЕТ'} ({up_said})")

    REVERSES = [
        ("④П1", "line", "искатель считает строки со сдвигом", (), BREAK_LINE, ["①"]),
        ("④П2", "add", "add не берёт адрес из находки", BREAK_ADD, (), ["②"]),
        ("④П3", "dry", "холостой прогон source пишет", BREAK_DRY, (), ["③"]),
        ("④МА", "ma", "адрес у первой находки чата, час не смотрим", BREAK_MA, (), ["②", "③"]),
        ("④МД", "md", "искатель ключует адрес без часа", (), BREAK_MD, ["①"]),
        ("④П4", "reason", "source называет причину постоянным текстом", BREAK_REASON, (), ["③"]),
        ("④П5", "nohour", "ветка «час не распознан» пишет слово", BREAK_NOHOUR, (), ["②"]),
    ]
    for rev in REVERSES:
        reverse(*rev)

    print()
    total = len(CASES) + len(REVERSES)
    print(f"ИТОГ: {max(total - len(failures), 0)} из {total}")
    if failures:
        print(f"🔴 ПРОВАЛИЛОСЬ случаев: {len(failures)}")
        for f in failures:
            print(f"   · {f}")
        sys.exit(mezo_stand.finish(1))
    print("✅ ВСЕ СЛУЧАИ ПРОШЛИ — искатель печатает под каждой строкой «чат:» адрес именно этой реплики, "
          "и у одного текста дважды в одном чате адреса разные; add берёт адрес из той же находки, что и час, "
          "без адреса, при расхождении с ключами и при исходе без часа отказывает; source в холостом прогоне "
          "базу не меняет, с --apply дописывает адрес, не трогая слов без находки и не перезаписывая другой "
          "записанный файл, а причину называет по отчёту сверки; каждая из семи поломок валит ровно свои случаи.")
    print("⛔ Чего приёмка НЕ доказывает: многострочный текст (адрес — строка записи, где лежит "
          "ПЕРВАЯ строка текста; разнесённость по записям только печатается); записи, сжатые или "
          "удалённые после того, как слово записано (source назовёт их, но адреса не восстановит); "
          "что адрес верен у слов живой базы — это покажет только прогон source на ней; "
          "причину при коде 3 искателя (происхождение машинное) — стенд такой реплики не строит; "
          "вид исхода находки (карточка #778).")
    sys.exit(mezo_stand.finish(0))
finally:
    mezo_stand.release(stand)
