# -*- coding: utf-8 -*-
"""Приёмка стены контура gordi — этап Э1, карточка 779.

Судит ДЕВЯТЬ критериев карточки. Семь из них машина проверяет сама, два остаются
человеку и названы в выводе прямо, а не умолчанием:
  ⑥ полный рабочий отрезок роли через стену — доказывается работой роли, не этим файлом;
  ⑨ приёмку подписывает роль, которая службу НЕ писала.

Две нарочные поломки (критерий ⑧) делаются КОПИЯМИ договора в черновом каталоге:
живые файлы приёмка не трогает.

Вызов:
    python check-wall.py --contours <манифест> [--exe <путь к gordi-wall.exe>] [--out <каталог проб>]

Карточка 787 добавила случаи о том, КТО исполняет требование договора (разбор договора, а не строка кода):
пометка selects=contour, обязательность выбора контура, обязательность второго общего аргумента,
отказ «без контура» по ТОЧНОЙ причине. Они печатаются отдельным перечнем после семи прежних.

Перед судом приёмка печатает час сборки исполнимого файла и час последней правки исходников
(*.cs, *.csproj). Сборку старше исходников она НЕ судит: это не провал и не проход.
Файл договора в этот счёт НЕ входит: служба читает его при каждом запуске, в сборку он не вшит,
и правка договора сборку не старит.

Карточка 791 добавила случаи о форме ответа: длинный вывод выдаётся ЧАСТЯМИ (К1, К7), предупреждения тела — отдельным
полем (К2, К1б), «не запустилось» не выбирается подстрокой (К3), чужая и выдуманная метка продолжения — отказ (К-метка).
Случаи с телом инструмента работают на ЗАГЛУШКАХ в черновом каталоге; случай К7 — на своей копии базы стенда.

Часть II карточки 791: сборка называет свой commit (К4), пустая запись установщика названа прямо (К5), незнакомый
аргумент — отказ (К6), читающий вызов меняет только служебные таблицы, перечисленные в договоре, сводка по ВСЕМ
таблицам до и после (К8); в раздел карточки 787 добавлены случаи TAXO E9 (переименованный общий аргумент выбора
контура) и E10 (перечень значений у общего аргумента).

Находка TAXO F′ расширила это на все вызовы: случай 787-F судит схему MCP КАЖДОГО вызова из tools/list на целом договоре
(аргумент выбора контура есть и в required, и в properties), а E9 теперь тоже судит все вызовы, а не один memory_read.
Находка COORD Н1: обычное чтение ленты в К8 обязано задеть таблицу read_batches (цикл по ролям идёт до роли с непрочитанным;
не задело ни у одной — «ПРОВЕРЯТЬ НЕЧЕМ», случай не проходит).
Новый исход договора 1.3.0 «тело отказало» (tool_failed, код выхода run 6): К3 теперь ждёт его для «фраза в stdout, код 1»,
случай К9 судит его на заглушках (код 1 с причиной в потоке ошибок, код 3 с причиной в stdout, признак расхождения по-прежнему
даёт mismatch, обрыв по времени — cannot_verify с усечением на манифесте с пределом 2 с).
Защита живого контура: функция guard_live_call и исключение LiveContourRefusal. На живом контуре (CONTOUR_LIVE) приёмка САМА
отказывается звать всё, кроме contour_info, rules_get и memory_read с непустым section; отказ — в Wall.call и run_mode ДО отправки,
в main — «ПРИЁМКА ОСТАНОВЛЕНА», код 2. Случай К10 проверяет саму функцию без запуска процессов.
Находка COORD Н2: причина отказа (поле error) — строка тела с признаком ошибки в начале, а не последняя строка вывода.
Случай К11 судит это на трёх заглушках: признак первой строкой stdout перед подсказкой; признак во второй строке потока
ошибок; признака нет — берётся последняя непустая строка (так кончается необработанное исключение).
Два замечания COORD к случаю К11 судит случай К12: причиной становится ПОСЛЕДНЯЯ строка с признаком (предупреждение
с признаком, напечатанное раньше причины, её не подменяет), а признак-слово считается только целым словом
(«ERRORS: 0» — не признак).

Исход: 0 — все машинные критерии прошли; 1 — хоть один провалился; 2 — проверять было нечем;
3 — сборка старше исходников, судить её нельзя (пересобрать и запустить снова).
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.dirname(HERE)
CONTRACT = os.path.join(SERVICE, "contract", "gordi-contract.json")
DEFAULT_EXE = os.path.join(SERVICE, "GordiWall", "bin", "Debug", "net10.0", "gordi-wall.exe")

# Записанный ожидаемый состав договора. Меняется РУКОЙ, когда договор меняют нарочно:
# иначе «перечень вызовов тот же» нечем подтвердить — отпечаток пересчитается вместе с подменой.
# Карточка 791: в договор добавлены общий аргумент next_part (часть I) и поле service_writes у читающих вызовов
# (часть II). Новых ВЫЗОВОВ нет: число прежнее — 12, отпечаток перечня считается по именам и режимам вызовов и поэтому
# тоже прежний. Если число или отпечаток когда-нибудь сменятся, это решение человека, а не пересчёт приёмки.
EXPECTED_TOOL_COUNT = 12
EXPECTED_TOOLS_FINGERPRINT = "247dbfb31eaf"
TOOL_COUNT_RANGE = (8, 12)

CONTOUR_LIVE = "atlas"
CONTOUR_STAND = "atlas-stand"


class LiveContourRefusal(Exception):
    """Приёмка отказалась звать на живом контуре вызов, который не измерен как не пишущий."""


# На живом контуре приёмка вправе звать ТОЛЬКО измеренное как не пишущее (случай К8 меряет на копии стенда):
# contour_info и rules_get не меняют ничего; memory_read не меняет ничего ТОЛЬКО при непустом section —
# без раздела он отмечает подсказку в живой базе (таблица hint_seen). cards_list и feed_read пишут служебные таблицы.
LIVE_ALWAYS_OK = ("contour_info", "rules_get")
LIVE_OK_WITH_SECTION = ("memory_read",)


def guard_live_call(tool, args):
    """Отказывает (LiveContourRefusal), если вызов идёт на живой контур и не входит в измеренное как не пишущее.

    args — словарь аргументов вызова (служба) ИЛИ список argv режима run без имени вызова.
    Контур ищется по значению CONTOUR_LIVE у ЛЮБОГО аргумента: имя аргумента выбора контура договор вправе
    переименовать, а промах здесь стоит записи в живую базу. Вызовы на стенде, без контура и с выдуманным
    контуром защита не трогает: живой базы они не касаются."""
    if isinstance(args, dict):
        on_live = any(isinstance(x, str) and x == CONTOUR_LIVE for x in args.values())
        section = args.get("section")
        has_section = isinstance(section, str) and section.strip() != ""
    else:
        argv = [str(x) for x in args]
        on_live = CONTOUR_LIVE in argv
        has_section = False
        if "--section" in argv:
            i = argv.index("--section")
            has_section = i + 1 < len(argv) and not argv[i + 1].startswith("--") and argv[i + 1].strip() != ""
    if not on_live:
        return
    if tool in LIVE_ALWAYS_OK:
        return
    if tool in LIVE_OK_WITH_SECTION and has_section:
        return
    if tool in LIVE_OK_WITH_SECTION:
        why = "без аргумента section он отметил бы подсказку в живой базе (таблица hint_seen)"
    else:
        why = "он не измерен как не пишущий: такие вызовы пишут служебные таблицы живой базы"
    raise LiveContourRefusal("вызов «%s» на живом контуре «%s» запрещён приёмке: %s. "
                             "На живом контуре разрешены только contour_info, rules_get и memory_read с непустым section."
                             % (tool, CONTOUR_LIVE, why))


class Verdict(object):
    """Итог одного критерия. Исход назван словом, а не кодом: код у приёмки один."""

    def __init__(self):
        self.rows = []

    def add(self, key, ok, title, detail):
        self.rows.append((key, bool(ok), title, detail))

    def failed(self):
        return [r for r in self.rows if not r[1]]

    def print_all(self):
        for key, ok, title, detail in self.rows:
            mark = "✅" if ok else "🔴"
            print("%s %s %s" % (mark, key, title))
            for line in detail.splitlines():
                print("      %s" % line)


class Wall(object):
    """Служба, поднятая по стандартному вводу-выводу. Один разговор — один экземпляр."""

    def __init__(self, exe, contract, contours, env_extra=None, read_only=False):
        env = dict(os.environ)
        env["PYTHONUTF8"] = "1"
        if env_extra:
            env.update(env_extra)
        argv = [exe, "serve", "--contract", contract, "--contours", contours]
        if read_only:
            argv.append("--read-only")
        self.p = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, encoding="utf-8", errors="replace", bufsize=1)
        self.next_id = 1
        self._send({"jsonrpc": "2.0", "id": self._id(), "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "check-wall", "version": "1"}}})
        self.init = self._recv()
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _id(self):
        v = self.next_id
        self.next_id += 1
        return v

    def _send(self, obj):
        self.p.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def _recv(self):
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError("служба закрыла вывод, не ответив. Поток ошибок: %s" % self.stderr_tail())
        return json.loads(line)

    def list_tools(self):
        self._send({"jsonrpc": "2.0", "id": self._id(), "method": "tools/list"})
        return self._recv()["result"]["tools"]

    def call(self, name, args):
        """Возвращает (структурный ответ, текст роли). Отказ службы — тоже ответ, не исключение.
        Отказ самой приёмки звать вызов на живом контуре — исключение LiveContourRefusal, ДО отправки."""
        guard_live_call(name, args)
        self._send({"jsonrpc": "2.0", "id": self._id(), "method": "tools/call",
                    "params": {"name": name, "arguments": args}})
        answer = self._recv()
        if "error" in answer:
            return {"outcome": "ОШИБКА ПРОТОКОЛА", "error": answer["error"].get("message", "")}, ""
        res = answer["result"]
        text = ""
        for item in res.get("content") or []:
            if item.get("type") == "text":
                text += item.get("text") or ""
        return res.get("structuredContent") or {}, text

    def stderr_tail(self):
        try:
            self.p.stderr.flush()
        except Exception:
            pass
        return ""

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.wait(timeout=20)
        except Exception:
            self.p.kill()


def read_json(path):
    return json.loads(io.open(path, encoding="utf-8").read())


def write_json(path, data):
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(data, ensure_ascii=False, indent=2))


def run_mode(exe, contract, contours, argv):
    """Однократный вызов мимо службы. Отдаёт код выхода, вывод и поток ошибок целиком.
    Защита живого контура срабатывает ДО запуска процесса."""
    if argv:
        guard_live_call(argv[0], argv[1:])
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    p = subprocess.run([exe, "run"] + argv + ["--contract", contract, "--contours", contours],
                       capture_output=True, encoding="utf-8", errors="replace", env=env, timeout=180)
    return p.returncode, p.stdout, p.stderr


def utc(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def newest_source():
    """Час последней правки исходников службы: *.cs и *.csproj, кроме bin/obj.

    Договора здесь нет намеренно: он читается при запуске, а не вшивается в сборку."""
    best = (0.0, None)
    for root, dirs, files in os.walk(os.path.join(SERVICE, "GordiWall")):
        dirs[:] = [d for d in dirs if d not in ("bin", "obj")]
        for f in files:
            if f.endswith(".cs") or f.endswith(".csproj"):
                full = os.path.join(root, f)
                m = os.path.getmtime(full)
                if m > best[0]:
                    best = (m, full)
    return best


def load_refusal(exe, contract_path, contours):
    """Служба на этом договоре: код выхода и поток ошибок. Отказ при загрузке виден здесь, без разговора по протоколу."""
    p = subprocess.run([exe, "tools", "--contract", contract_path, "--contours", contours],
                       capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    return p.returncode, p.stderr


# ═══════════════════════════════════════ карточка 791: части вместо обрезки, предупреждения отдельно, честный «не запустилось»

STUB_LIMIT = 2000          # предел знаков в манифесте заглушек и в случае К7
WARNINGS_END = "── конец предупреждений ──\n"


def build_big_text():
    """Вывод заглушки ≈2,5 предела: первая строка HEAD-MARK, длинная строка с MID-MARK, последняя TAIL-MARK."""
    lines = ["HEAD-MARK stub begin"]
    lines += ["filler-a-%02d %s" % (i, "a" * 85) for i in range(14)]
    lines.append("MID-MARK " + "m" * 2300)      # строка длиннее предела: её приходится резать по пределу
    lines += ["filler-b-%02d %s" % (i, "b" * 85) for i in range(14)]
    lines.append("TAIL-MARK stub end")
    return "\n".join(lines) + "\n"


def body_of(out):
    """Из вывода режима run достаёт текст тела: после блока предупреждений или после шапки."""
    i = out.find(WARNINGS_END)
    if i >= 0:
        rest = out[i + len(WARNINGS_END):]
        return rest[1:] if rest.startswith("\n") else rest
    j = out.find("\n\n")
    return out[j + 2:] if j >= 0 else ""


def sha(text):
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def collect_serve(w, tool, args, carg):
    """Идёт по частям через службу до последней. Отдаёт список (структурный ответ, текст роли)."""
    s, t = w.call(tool, args)
    got = [(s, t)]
    while s.get("next_part") and len(got) < 100:
        s, t = w.call(tool, {carg: args[carg], "next_part": s["next_part"]})
        got.append((s, t))
    return got


def collect_run(exe, contract, contours, tool, argv, carg):
    """То же мимо службы: каждая часть — отдельный процесс. Отдаёт список (код выхода, вывод, поток ошибок)."""
    import re
    code, out, err = run_mode(exe, contract, contours, [tool] + argv)
    got = [(code, out, err)]
    while code == 5 and len(got) < 100:
        m = re.search(r"--next-part ([0-9a-f]{32}\.[0-9]+)", out)
        if not m:
            break
        contour_value = argv[argv.index("--" + carg) + 1]
        code, out, err = run_mode(exe, contract, contours,
                                  [tool, "--" + carg, contour_value, "--next-part", m.group(1)])
        got.append((code, out, err))
    return got


# ═══════════════════════════════════════ карточка 791, часть II: отметка сборки · пустая запись установщика ·
#                                          незнакомый аргумент · служебные записи читающих вызовов

def stand_copy(work, manifest, tag):
    """Своя копия базы стенда и копия манифеста с подменённым storage. Общую копию стенда новые случаи не меняют."""
    stand_db = [c for c in manifest["contours"] if c.get("id") == CONTOUR_STAND][0]["storage"]
    d = os.path.join(work, tag)
    if not os.path.isdir(d):
        os.makedirs(d)
    db = os.path.join(d, "mezosync.db")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(db + suffix):
            os.remove(db + suffix)
        if os.path.exists(stand_db + suffix):
            shutil.copyfile(stand_db + suffix, db + suffix)
    import copy
    m = copy.deepcopy(manifest)
    for c in m["contours"]:
        if c.get("id") == CONTOUR_STAND:
            c["storage"] = db
    mp = os.path.join(d, "contours-%s.json" % tag)
    write_json(mp, m)
    return db, mp


def table_digests(db_path):
    """По каждой таблице базы: (число строк, sha256 по содержимому). Читается только на чтение."""
    import hashlib
    import sqlite3
    conn = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    out = {}
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
        for n in names:
            rows = sorted(repr(r) for r in conn.execute('SELECT * FROM "%s"' % n))
            h = hashlib.sha256()
            for r in rows:
                h.update(r.encode("utf-8"))
            out[n] = (len(rows), h.hexdigest()[:12])
    finally:
        conn.close()
    return out


def strip_credentials(url):
    import re
    return re.sub(r"^([a-zA-Z+]+://)[^/@]+@", r"\1", url.strip())


def git_out(cwd, *argv):
    """Вывод git в каталоге или None, если git не ответил."""
    try:
        p = subprocess.run(["git", "-C", cwd] + list(argv), capture_output=True, encoding="utf-8",
                           errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return p.stdout.strip() if p.returncode == 0 else None


def sync_backoff_writers(runtime_dir):
    """Какие функции установленной копии sync_backoff.py пишут в таблицу sync_backoff: (имя, строка def, строка записи)."""
    import ast
    path = os.path.join(runtime_dir, "sync_backoff.py")
    if not os.path.exists(path):
        return path, []
    tree = ast.parse(io.open(path, encoding="utf-8").read())
    found = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value.strip().upper()
                if text.startswith(("INSERT INTO SYNC_BACKOFF", "UPDATE SYNC_BACKOFF", "DELETE FROM SYNC_BACKOFF")):
                    found.append((fn.name, fn.lineno, node.lineno))
    return path, sorted(set(found), key=lambda x: x[2])


# пробный вызов каждого читающего вызова договора на своей копии базы стенда
K8_PROBES = {
    "memory_read": {"role": "PROTO"},
    "memory_read_for_edit": {"role": "PROTO", "section": "state"},
    # два варианта: обычное чтение и отбор to_me. Каждый обязан задеть свою таблицу — иначе замер её не видел:
    # обычное чтение — read_batches (запись о показанной партии; у роли без непрочитанного её нет, и цикл по ролям идёт дальше),
    # отбор to_me — cursor_segments
    "feed_read": [("", {"role": "COORD"}, "read_batches"), (" to_me", {"role": "COORD", "to_me": True}, "cursor_segments")],
    "cards_list": {"role": "PROTO"},
    "cards_show": {"card": 1},
    "rules_get": {"list": True},
    "owner_words_find": {"text": "слово"},
    "contour_info": {},
}
# роли для чтения ленты: берём первую, у которой чтение задело ОБЯЗАТЕЛЬНУЮ таблицу варианта (иначе случай ничего бы не измерил);
# если не задела ни у одной — случай говорит «ПРОВЕРЯТЬ НЕЧЕМ» и не проходит
K8_FEED_ROLES = ("COORD", "CORE", "PROTO", "TAXO", "ING", "STUD")


def cases_791(args, work, manifest, contract_doc, carg, v3, s2c):
    import copy
    import re

    stubs = os.path.join(work, "stubs-791")
    if not os.path.isdir(stubs):
        os.makedirs(stubs)

    def put_stub(name, source):
        io.open(os.path.join(stubs, name), "w", encoding="utf-8", newline="\n").write(source)

    big = build_big_text()
    marker_file = os.path.join(work, "stub-791-started.txt")
    if os.path.exists(marker_file):
        os.remove(marker_file)

    # заглушки: тело пишет байты прямо в поток, чтобы переводы строки не зависели от платформы
    put_stub("stub-big.py", "import sys\nsys.stdout.buffer.write(%r)\nsys.stderr.buffer.write(b'WARN-MARK stub warning\\n')\n"
             % big.encode("utf-8"))
    put_stub("stub-warn.py", "import sys\nsys.stdout.buffer.write(b'short body\\n')\nsys.stderr.buffer.write(b'WARN-MARK stub warning\\n')\n")
    put_stub("stub-k3-stdout.py", "import sys\nsys.stdout.write('No such file or directory\\n')\nsys.exit(1)\n")
    put_stub("stub-k3-stderr.py", "import sys\nsys.stdout.write('some output\\n')\nsys.stderr.write('No such file or directory\\n')\nsys.exit(2)\n")
    put_stub("stub-k3-interpreter.py", "import sys\nsys.stderr.write(\"python.exe: can't open file 'x.py': [Errno 2] No such file or directory\\n\")\nsys.exit(2)\n")
    put_stub("stub-marker.py", "import sys\nopen(%r, 'w').write('started')\nsys.stdout.write('marker stub ran\\n')\n" % marker_file)

    # манифест заглушек: малый предел знаков, оба каталога инструментов — каталог заглушек
    m_stub = copy.deepcopy(manifest)
    m_stub["limits"] = {"timeout_seconds": 120, "max_output_chars": STUB_LIMIT}
    for c in m_stub["contours"]:
        c["tools"] = {"runtime": stubs, "vnext": stubs}
    m_stub_path = os.path.join(work, "contours-stubs-791.json")
    write_json(m_stub_path, m_stub)

    def stub_contract(tag, mapping):
        d = copy.deepcopy(contract_doc)
        for t in d["tools"]:
            if t["name"] in mapping:
                t["exec"]["script"] = mapping[t["name"]]
        p = os.path.join(work, "contract-791-%s.json" % tag)
        write_json(p, d)
        return p

    big_contract = stub_contract("big", {"rules_get": "stub-big.py"})

    # ───────────── К1: длинный вывод выдаётся ЧАСТЯМИ, ничего не режется (находка С1)
    w1 = Wall(args.exe, big_contract, m_stub_path)
    sv = collect_serve(w1, "rules_get", {carg: CONTOUR_STAND, "list": True}, carg)
    w1.close()
    sv_texts = [s.get("text", "") for s, _ in sv]
    sv_join = "".join(sv_texts)
    sv_first, sv_last = sv[0][0], sv[-1][0]
    ok_sv = (len(sv) >= 3
             and sv_first.get("outcome") == "partial" and "HEAD-MARK" in sv_texts[0] and "TAIL-MARK" not in sv_texts[0]
             and sv_last.get("outcome") == "passed" and "TAIL-MARK" in sv_texts[-1] and not sv_last.get("next_part")
             and len(sv_join) == len(big) and sha(sv_join) == sha(big)
             and all(s.get("outcome") == "partial" and s.get("final_outcome") == "passed" for s, _ in sv[:-1])
             and all(s.get("outcome") != "passed" for s, _ in sv[:-1])
             and all(s.get("truncated") is False for s, _ in sv)
             and all(s.get("part") == i + 1 and s.get("parts") == len(sv) for i, (s, _) in enumerate(sv))
             and all(len(x) <= STUB_LIMIT for x in sv_texts))

    rn = collect_run(args.exe, big_contract, m_stub_path, "rules_get", ["--" + carg, CONTOUR_STAND, "--list"], carg)
    rn_bodies = [body_of(o) for _, o, _ in rn]
    rn_join = "".join(rn_bodies)
    ok_rn = (len(rn) >= 3
             and rn[0][0] == 5 and "HEAD-MARK" in rn_bodies[0] and "TAIL-MARK" not in rn_bodies[0]
             and rn[-1][0] == 0 and "TAIL-MARK" in rn_bodies[-1]
             and all(c == 5 for c, _, _ in rn[:-1])
             and "исход: частично" in rn[0][1] and "--next-part" in rn[0][1]
             and len(rn_join) == len(big) and sha(rn_join) == sha(big))
    v3.add("791-К1", ok_sv and ok_rn,
           "длинный вывод тела выдаётся ЧАСТЯМИ: ничего не режется, склейка частей равна выводу знак в знак (служба И режим run)",
           "служба: частей %d · исходы %s · начало HEAD-MARK в первой: %s · TAIL-MARK не в первой: %s · TAIL-MARK в последней: %s\n"
           "служба: длина склейки %d при длине вывода %d · sha256 совпал: %s · усечено нигде: %s\n"
           "режим run: частей %d · коды выхода %s · длина склейки %d · sha256 совпал: %s"
           % (len(sv), [s.get("outcome") for s, _ in sv],
              "HEAD-MARK" in sv_texts[0], "TAIL-MARK" not in sv_texts[0], "TAIL-MARK" in sv_texts[-1],
              len(sv_join), len(big), sha(sv_join) == sha(big), all(s.get("truncated") is False for s, _ in sv),
              len(rn), [c for c, _, _ in rn], len(rn_join), sha(rn_join) == sha(big)))

    # ───────────── К1б: предупреждения тела при выдаче частями — целиком в первой части и повторены в последней
    ok_w_first_last = ("WARN-MARK" in sv_first.get("warnings", "") and "WARN-MARK" in sv_last.get("warnings", ""))
    ok_w_mid = all("WARN-MARK" not in s.get("warnings", "") for s, _ in sv[1:-1])
    v3.add("791-К1б", ok_w_first_last and ok_w_mid,
           "при выдаче частями предупреждения тела — целиком в первой части и повторены в последней",
           "в первой: %s · в последней: %s · в средних нет: %s"
           % ("WARN-MARK" in sv_first.get("warnings", ""), "WARN-MARK" in sv_last.get("warnings", ""), ok_w_mid))

    # ───────────── К2: предупреждения — ОТДЕЛЬНЫМ полем, к тексту не приклеены (находка С2)
    warn_contract = stub_contract("warn", {"rules_get": "stub-warn.py"})
    w2 = Wall(args.exe, warn_contract, m_stub_path)
    s2, t2 = w2.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    w2.close()
    c2, o2, _ = run_mode(args.exe, warn_contract, m_stub_path, ["rules_get", "--" + carg, CONTOUR_STAND, "--list"])
    ok_k2 = ("WARN-MARK" in s2.get("warnings", "") and "WARN-MARK" not in s2.get("text", "")
             and s2.get("outcome") == "passed" and s2.get("part") == 1 and s2.get("parts") == 1
             and s2.get("next_part") is None
             and c2 == 0 and WARNINGS_END in o2 and "WARN-MARK" in o2 and "WARN-MARK" not in body_of(o2)
             and "short body" in body_of(o2))
    v3.add("791-К2", ok_k2, "предупреждения тела — отдельным полем warnings, в тексте вывода тела их нет; режим run печатает блок предупреждений",
           "служба: исход %s · WARN-MARK в warnings: %s · WARN-MARK в тексте тела: %s\n"
           "режим run: код %s · блок предупреждений напечатан: %s · WARN-MARK в тексте тела: %s"
           % (s2.get("outcome"), "WARN-MARK" in s2.get("warnings", ""), "WARN-MARK" in s2.get("text", ""),
              c2, WARNINGS_END in o2, "WARN-MARK" in body_of(o2)))

    # ───────────── К3: «не запустилось» не выбирается подстрокой (находка С3)
    k3_contract = stub_contract("k3", {"rules_get": "stub-k3-stdout.py", "owner_words_find": "stub-k3-stderr.py",
                                        "memory_read": "stub-k3-interpreter.py"})
    w3 = Wall(args.exe, k3_contract, m_stub_path)
    s3a, _ = w3.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    s3b, _ = w3.call("owner_words_find", {carg: CONTOUR_STAND, "text": "x"})
    s3c, _ = w3.call("memory_read", {carg: CONTOUR_STAND, "role": "PROTO"})
    w3.close()
    ok_k3 = (s3a.get("outcome") == "tool_failed" and s3b.get("outcome") != "not_started"
             and s3c.get("outcome") == "not_started" and s2c.get("outcome") == "not_started")
    v3.add("791-К3", ok_k3, "фраза «No such file or directory» в выводе отработавшего тела НЕ даёт «не запустилось»; сообщение интерпретатора и отсутствие тела на месте — дают",
           "фраза в stdout, код 1: исход %s (ждали tool_failed)\n"
           "фраза в stderr, код 2, stdout непуст: исход %s (ждали НЕ not_started)\n"
           "интерпретатор «can't open file», код 2, stdout пуст: исход %s (ждали not_started)\n"
           "тела нет на месте (прежний случай): исход %s (ждали not_started)"
           % (s3a.get("outcome"), s3b.get("outcome"), s3c.get("outcome"), s2c.get("outcome")))

    # ───────────── К-метка: выдуманная метка — отказ, тело не запускалось
    mark_contract = stub_contract("mark", {"rules_get": "stub-big.py", "owner_words_find": "stub-marker.py"})
    wm = Wall(args.exe, mark_contract, m_stub_path)
    fake_a, _ = wm.call("owner_words_find", {carg: CONTOUR_STAND, "text": "x", "next_part": "выдумка"})
    fake_b, _ = wm.call("owner_words_find", {carg: CONTOUR_STAND, "text": "x", "next_part": "0123456789abcdef0123456789abcdef.2"})
    started_after_fakes = os.path.exists(marker_file)
    ok_fake = (fake_a.get("outcome") == "refused" and "метк" in (fake_a.get("error") or "")
               and fake_b.get("outcome") == "refused" and "метк" in (fake_b.get("error") or "")
               and not started_after_fakes)
    v3.add("791-Кметка", ok_fake, "выдуманная или просроченная метка продолжения — отказ с причиной, тело НЕ запускалось",
           "метка-слово: исход %s — %s\nметка нужного вида, которой стена не выдавала: исход %s — %s\nфайл-отметка запуска тела есть: %s (ждали: нет)"
           % (fake_a.get("outcome"), (fake_a.get("error") or "")[:90],
              fake_b.get("outcome"), (fake_b.get("error") or "")[:90], started_after_fakes))

    # ───────────── К-метка-чужая: настоящая метка другого вызова или другого контура — отказ, тело не запускалось
    own, _ = wm.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    label = own.get("next_part")
    if not label:
        v3.add("791-Кметка-чужая", False, "настоящая метка ДРУГОГО вызова или ДРУГОГО контура — отказ, тело не запускалось",
               "ПРОВЕРЯТЬ НЕЧЕМ: первый вызов не выдал метку продолжения (исход %s, частей %s)" % (own.get("outcome"), own.get("parts")))
    else:
        other_tool, _ = wm.call("owner_words_find", {carg: CONTOUR_STAND, "text": "x", "next_part": label})
        started_after_foreign = os.path.exists(marker_file)
        other_contour, _ = wm.call("rules_get", {carg: CONTOUR_LIVE, "list": True, "next_part": label})
        same_ok, _ = wm.call("rules_get", {carg: CONTOUR_STAND, "next_part": label})
        ok_foreign = (other_tool.get("outcome") == "refused" and not started_after_foreign
                      and other_contour.get("outcome") == "refused"
                      and same_ok.get("outcome") in ("partial", "passed"))
        v3.add("791-Кметка-чужая", ok_foreign, "настоящая метка ДРУГОГО вызова или ДРУГОГО контура — отказ, тело не запускалось; своя метка работает",
               "метка вызова rules_get отдана вызову owner_words_find: %s — %s\nфайл-отметка запуска тела есть: %s (ждали: нет)\n"
               "метка контура %s отдана контуру %s: %s — %s\nсвоя метка тем же вызовом и контуром: исход %s"
               % (other_tool.get("outcome"), (other_tool.get("error") or "")[:90], started_after_foreign,
                  CONTOUR_STAND, CONTOUR_LIVE, other_contour.get("outcome"), (other_contour.get("error") or "")[:90],
                  same_ok.get("outcome")))

    # встречный к К-метке: тот же вызов без метки тело ЗАПУСКАЕТ — иначе «отметки нет» ничего не значит
    wm.call("owner_words_find", {carg: CONTOUR_STAND, "text": "x"})
    wm.close()
    marker_works = os.path.exists(marker_file)
    v3.add("791-Кметка-цела", marker_works, "встречный случай к К-метке: вызов без метки тело запускает (заглушка пишет файл-отметку)",
           "файл-отметка после обычного вызова есть: %s" % marker_works)

    # ───────────── К7: чтение ленты через стену на малом пределе — ключ подтверждения собирается из двух половин (находка С7)
    stand_db = [c for c in manifest["contours"] if c.get("id") == CONTOUR_STAND][0]["storage"]
    k7_dir = os.path.join(work, "k7")
    if not os.path.isdir(k7_dir):
        os.makedirs(k7_dir)
    k7_db = os.path.join(k7_dir, "mezosync.db")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(stand_db + suffix):
            shutil.copyfile(stand_db + suffix, k7_db + suffix)
    m7 = copy.deepcopy(manifest)
    m7["limits"] = {"timeout_seconds": 120, "max_output_chars": STUB_LIMIT}
    for c in m7["contours"]:
        if c.get("id") == CONTOUR_STAND:
            c["storage"] = k7_db
    m7_path = os.path.join(k7_dir, "contours-k7.json")
    write_json(m7_path, m7)

    w7 = Wall(args.exe, args.contract, m7_path)     # без --read-only: ключ подтверждения пишет отметку
    picked = None
    for role in ("PROTO", "COORD", "CORE", "ING", "STUD", "TAXO", "OPSSRE", "RCC"):
        s7, t7 = w7.call("feed_read", {carg: CONTOUR_STAND, "role": role})
        if "[begin-of-batch]" in s7.get("text", ""):
            picked = (role, s7)
            break
    if picked is None:
        v3.add("791-К7", False, "лента через стену на малом пределе: ключ подтверждения собирается из двух половин и подтверждается",
               "ПРОВЕРЯТЬ НЕЧЕМ: ни у одной проверенной роли на копии базы нет непрочитанного — случай не может пройти молча")
        w7.close()
    else:
        role, first = picked
        got7 = [(first, "")]
        s = first
        while s.get("next_part") and len(got7) < 200:
            s, _ = w7.call("feed_read", {carg: CONTOUR_STAND, "next_part": s["next_part"]})
            got7.append((s, ""))
        texts7 = [x.get("text", "") for x, _ in got7]
        last7 = got7[-1][0]
        m_first = re.search(r"ПЕРВАЯ половина ([0-9a-f]+)", texts7[0])
        m_second = re.search(r"--ack <первая>-([0-9a-f]+)", texts7[-1])
        key = (m_first.group(1) + "-" + m_second.group(1)) if (m_first and m_second) else None
        ack_outcome = None
        if key:
            ack, _ = w7.call("feed_ack", {carg: CONTOUR_STAND, "role": role, "key": key})
            ack_outcome = ack.get("outcome")
        w7.close()
        ok7 = (len(got7) >= 2 and "[begin-of-batch]" in texts7[0] and "[end-of-batch]" in texts7[-1]
               and "[end-of-batch]" not in texts7[0]
               and all(x.get("outcome") == "partial" for x, _ in got7[:-1])
               and last7.get("outcome") == "passed" and key is not None and ack_outcome == "passed")
        v3.add("791-К7", ok7, "лента через стену на малом пределе: первая часть несёт начало партии, последняя — конец со второй половиной ключа; склеенный ключ подтверждается",
               "роль %s · предел знаков %d · частей %d · исходы первой и последней: %s и %s\n"
               "начало партии в первой части: %s · конец партии в последней: %s · половины ключа найдены: %s\n"
               "подтверждение склеенным ключом на копии базы: %s"
               % (role, STUB_LIMIT, len(got7), got7[0][0].get("outcome"), last7.get("outcome"),
                  "[begin-of-batch]" in texts7[0], "[end-of-batch]" in texts7[-1], key is not None, ack_outcome))

    # ═══════════ часть II карточки 791

    # ───────────── К4: «кто меня судит» называет commit сборки и адрес исходника (находка С4)
    root_dir = SERVICE
    head = git_out(root_dir, "rev-parse", "HEAD")
    origin = git_out(root_dir, "remote", "get-url", "origin")
    code4, out4, _ = run_mode(args.exe, args.contract, args.contours, ["contour_info", "--" + carg, CONTOUR_STAND])
    w4 = Wall(args.exe, args.contract, args.contours)
    server_commit = (w4.init.get("result", {}).get("serverInfo", {}) or {}).get("build_commit")
    w4.close()
    m4 = re.search(r"commit сборки \.+ ([0-9a-f]{40})", out4)
    built = m4.group(1) if m4 else None
    if head is None:
        v3.add("791-К4", False, "contour_info называет commit сборки и адрес исходника",
               "ПРОВЕРЯТЬ НЕЧЕМ: git не ответил в дереве %s — сверить commit не с чем" % root_dir)
    else:
        same = built == head
        ok4 = (same and "vnext/service/GordiWall" in out4
               and (origin is None or strip_credentials(origin) in out4)
               and server_commit == head)
        why = ""
        if not same:
            why = ("\nПЕРЕСОБРАТЬ: сборка сделана из другого commit (или не из git), чем HEAD этого дерева. "
                   "dotnet build %s, затем запустить приёмку снова" % os.path.join(SERVICE, "GordiWall"))
        v3.add("791-К4", ok4, "contour_info называет commit сборки (равен HEAD дерева) и адрес исходника; serverInfo несёт тот же commit",
               "commit в ответе: %s\nHEAD дерева ........ %s\nстрока пути исходника есть: %s · адрес origin в ответе: %s\n"
               "serverInfo.build_commit: %s%s"
               % (built or ("НЕ НАЙДЕН (в ответе: %s)" % [l for l in out4.splitlines() if "commit сборки" in l][:1]), head,
                  "vnext/service/GordiWall" in out4,
                  (strip_credentials(origin) in out4) if origin else "origin не задан",
                  server_commit, why))

    # ───────────── К5: хранилище ответило, записи установщика нет — так и сказано (находка С5)
    db5, mp5 = stand_copy(work, manifest, "k5")
    import sqlite3
    c5 = sqlite3.connect(db5)
    removed5 = c5.execute("DELETE FROM meta WHERE key LIKE 'template_%'").rowcount
    c5.commit()
    c5.close()
    _, out5, _ = run_mode(args.exe, args.contract, mp5, ["contour_info", "--" + carg, CONTOUR_STAND])
    _, out5ok, _ = run_mode(args.exe, args.contract, args.contours, ["contour_info", "--" + carg, CONTOUR_STAND])
    ok5e = (removed5 > 0
            and "записи установщика НЕТ" in out5 and "нечем проверить" in out5
            and "это и есть источник" not in out5
            and "это и есть источник о версии" in out5ok and "записи установщика НЕТ" not in out5ok)
    v3.add("791-К5", ok5e, "пустая запись установщика: блок из хранилища говорит «записи установщика НЕТ — нечем проверить» и не зовёт себя источником о версии",
           "на своей копии удалено строк template_*: %d\n"
           "копия: «записи установщика НЕТ»: %s · «нечем проверить»: %s · «это и есть источник» (ждали: нет): %s\n"
           "встречный, целая запись: «это и есть источник о версии» есть: %s · «записи установщика НЕТ» нет: %s"
           % (removed5, "записи установщика НЕТ" in out5, "нечем проверить" in out5, "это и есть источник" in out5,
              "это и есть источник о версии" in out5ok, "записи установщика НЕТ" not in out5ok))

    # ───────────── К6: незнакомый аргумент — отказ с его именем, тело не запускалось (находка С6)
    k6_marker = os.path.join(work, "stub-791-k6-started.txt")
    if os.path.exists(k6_marker):
        os.remove(k6_marker)
    put_stub("stub-k6-marker.py", "import sys\nopen(%r, 'w').write('started')\nsys.stdout.write('k6 stub ran\\n')\n" % k6_marker)
    k6_contract = stub_contract("k6", {"feed_read": "stub-k6-marker.py"})
    w6 = Wall(args.exe, k6_contract, m_stub_path)
    s6, _ = w6.call("feed_read", {carg: CONTOUR_STAND, "role": "PROTO", "limt": 5})
    started6 = os.path.exists(k6_marker)
    s6ok, _ = w6.call("feed_read", {carg: CONTOUR_STAND, "role": "PROTO", "limit": 5})
    started6ok = os.path.exists(k6_marker)
    schema6 = [t for t in w6.list_tools() if t["name"] == "feed_read"][0]["inputSchema"]
    w6.close()
    if os.path.exists(k6_marker):
        os.remove(k6_marker)
    c6, o6, _ = run_mode(args.exe, k6_contract, m_stub_path, ["feed_read", "--" + carg, CONTOUR_STAND, "--role", "PROTO", "--limt", "5"])
    started6run = os.path.exists(k6_marker)
    ok6 = (s6.get("outcome") == "refused" and "limt" in (s6.get("error") or "") and not started6
           and s6ok.get("outcome") == "passed" and started6ok
           and c6 == 4 and "limt" in o6 and "исход: отказ" in o6 and not started6run
           and schema6.get("additionalProperties") is False)
    v3.add("791-К6", ok6, "незнакомый аргумент (limt вместо limit) — отказ с его именем в службе и в режиме run, тело не запускалось; верный аргумент проходит; в схеме additionalProperties=false",
           "служба: исход %s — %s · тело запускалось: %s (ждали: нет)\n"
           "служба, верный limit: исход %s · тело запускалось: %s (ждали: да)\n"
           "режим run: код %s · «limt» в тексте: %s · тело запускалось: %s (ждали: нет)\n"
           "additionalProperties в схеме вызова: %s"
           % (s6.get("outcome"), (s6.get("error") or "")[:130], started6, s6ok.get("outcome"), started6ok,
              c6, "limt" in o6, started6run, schema6.get("additionalProperties")))

    # ───────────── К8: читающий вызов меняет только перечисленные в договоре служебные таблицы (находка С8)
    read_tools = [t for t in contract_doc["tools"] if t.get("mode") == "read"]
    rows8 = []
    problems8 = []
    any_write = False
    last_db8 = None
    for t in read_tools:
        name = t["name"]
        declared = t.get("service_writes")
        if declared is None:
            problems8.append("%s: у читающего вызова в договоре нет поля service_writes" % name)
            declared = []
        probe = K8_PROBES.get(name)
        if probe is None:
            problems8.append("%s: для читающего вызова нет пробного вызова в приёмке (K8_PROBES)" % name)
            continue
        roles = K8_FEED_ROLES if name == "feed_read" else (None,)
        # вариант пробы: (подпись, аргументы, таблица, которую вариант ОБЯЗАН задеть, или None)
        variants = probe if isinstance(probe, list) else [("", probe, None)]
        for label, variant_args, must_touch in variants:
            changed = set()
            used = ""
            for role in roles:
                db8, mp8 = stand_copy(work, manifest, "k8")
                last_db8 = db8
                before = table_digests(db8)
                call_args = dict(variant_args)
                call_args[carg] = CONTOUR_STAND
                if role:
                    call_args["role"] = role
                    used = role
                w8 = Wall(args.exe, args.contract, mp8)      # без --read-only: так служба поднята у ролей
                s8, _ = w8.call(name, call_args)
                w8.close()
                after = table_digests(db8)
                changed = set(k for k in before if before[k] != after.get(k))
                if s8.get("outcome") not in ("passed", "partial"):
                    problems8.append("%s%s: пробный вызов дал исход %s — замер недействителен"
                                     % (name, label, s8.get("outcome")))
                if not role or (must_touch in changed if must_touch else changed):
                    break
            any_write = any_write or bool(changed)
            if must_touch and must_touch not in changed:
                problems8.append("ПРОВЕРЯТЬ НЕЧЕМ: %s%s ни у одной роли из %s не задел %s — замер этого варианта ничего не видел"
                                 % (name, label, ", ".join(roles), must_touch))
            extra = sorted(changed - set(declared))
            if extra:
                problems8.append("%s%s: изменил таблицы, которых нет в service_writes: %s" % (name, label, ", ".join(extra)))
            rows8.append("%-22s%s изменил: %-34s объявлено: %s"
                         % (name + label, (" (роль %s)" % used) if used else "", ", ".join(sorted(changed)) or "ничего",
                            ", ".join(declared) or "—"))
    if not any_write:
        problems8.append("ПРОВЕРЯТЬ НЕЧЕМ: ни один читающий вызов ничего не изменил на копии — замер, видимо, не работает")
    runtime_dir = [c for c in manifest["contours"] if c.get("id") == CONTOUR_STAND][0]["tools"]["runtime"]
    sb_path, sb_writers = sync_backoff_writers(runtime_dir)
    rule_state = None
    try:
        import sqlite3 as _sq
        _c = _sq.connect("file:%s?mode=ro" % last_db8.replace("\\", "/"), uri=True)
        _r = _c.execute("SELECT status FROM rules WHERE rule_key='sync-sleep-backoff'").fetchone()
        _c.close()
        rule_state = _r[0] if _r else None
    except Exception:
        pass
    writers_text = ", ".join("%s (def :%d, запись :%d)" % w for w in sb_writers) or "не найдены разбором"
    who = ("next_sleep — функция разгона сна (правило sync-sleep-backoff действует)" if rule_state == "active"
           else "news — счёт нового (правило sync-sleep-backoff на копии стенда: %s, строку сна не печатает)" % rule_state)
    v3.add("791-К8", not problems8, "читающий вызов меняет только служебные таблицы, перечисленные у него в service_writes (сводка по ВСЕМ таблицам до и после)",
           "\n".join(rows8) + "\n"
           + "запись в sync_backoff делают функции установленной копии %s: %s\n"
             "цепочка при чтении ленты: read-messages.py → sync_backoff.reader_line → %s\n"
             "отбор to_me чтения ленты измерен отдельной строкой: он записывает в cursor_segments, что тела показаны, отметку прочитанного не двигает"
             % (sb_path, writers_text, who)
           + ("\nПРОБЛЕМЫ:\n" + "\n".join(problems8) if problems8 else ""))


    # ───────────── К9: тело кончилось ненулевым кодом — исход «тело отказало» (tool_failed), а не «не смог проверить»
    put_stub("stub-k9-stderr.py", "import sys\nsys.stderr.write('нет такой роли: ZZZ\\n')\nsys.exit(1)\n")
    put_stub("stub-k9-stdout3.py", "import sys\nsys.stdout.write('причина только в stdout: ключ подтверждения неверен\\n')\nsys.exit(3)\n")
    mismatch_marks = [t for t in contract_doc["tools"] if t["name"] == "memory_save"][0]["exec"].get("mismatch_when") or []
    mismatch_mark = mismatch_marks[0] if mismatch_marks else None
    put_stub("stub-k9-mismatch.py", "import sys\nsys.stdout.write(%r + '\\n')\nsys.exit(1)\n" % (mismatch_mark or ""))
    put_stub("stub-k9-sleep.py", "import time\ntime.sleep(60)\n")
    k9_contract = stub_contract("k9", {"rules_get": "stub-k9-stderr.py", "owner_words_find": "stub-k9-stdout3.py",
                                        "memory_save": "stub-k9-mismatch.py"})
    w9k = Wall(args.exe, k9_contract, m_stub_path)
    k9a, _ = w9k.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    k9b, _ = w9k.call("owner_words_find", {carg: CONTOUR_STAND, "text": "x"})
    k9c, _ = w9k.call("memory_save", {carg: CONTOUR_STAND, "role": "PROTO", "section": "state", "body": "заглушка", "expect_version": 1})
    w9k.close()
    k9a_code, k9a_out, _ = run_mode(args.exe, k9_contract, m_stub_path, ["rules_get", "--" + carg, CONTOUR_STAND, "--list"])
    ok_k9a = (k9a.get("outcome") == "tool_failed" and (k9a.get("error") or "").startswith("тело отказало:")
              and "нет такой роли" in (k9a.get("error") or "") and k9a.get("child_exit") == 1
              and k9a_code == 6 and "исход: тело отказало" in k9a_out)
    ok_k9b = (k9b.get("outcome") == "tool_failed" and (k9b.get("error") or "").startswith("тело отказало:")
              and k9b.get("child_exit") == 3)
    ok_k9c = mismatch_mark is not None and k9c.get("outcome") == "mismatch" and k9c.get("child_exit") == 1
    # (г) обрыв по времени: копия манифеста с пределом 2 с, заглушка спит 60 с
    m_t = copy.deepcopy(m_stub)
    m_t["limits"] = {"timeout_seconds": 2, "max_output_chars": STUB_LIMIT}
    m_t_path = os.path.join(work, "contours-stubs-791-timeout.json")
    write_json(m_t_path, m_t)
    k9t_contract = stub_contract("k9t", {"rules_get": "stub-k9-sleep.py"})
    w9t = Wall(args.exe, k9t_contract, m_t_path)
    k9d, _ = w9t.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    w9t.close()
    ok_k9d = k9d.get("outcome") == "cannot_verify" and k9d.get("truncated") is True
    v3.add("791-К9", ok_k9a and ok_k9b and ok_k9c and ok_k9d,
           "тело кончилось ненулевым кодом — исход «тело отказало» (tool_failed) с причиной и кодом тела; признак расхождения из договора по-прежнему даёт mismatch; обрыв по времени — cannot_verify с усечением",
           "(а) код 1, причина в потоке ошибок: исход %s · error «%s» · код тела %s · режим run: код выхода %s (ждали 6), «исход: тело отказало» в тексте: %s\n"
           "(б) код 3, причина только в stdout: исход %s · error начинается с «тело отказало:»: %s · код тела %s\n"
           "(в) код 1 и признак расхождения «%s» из договора: исход %s · код тела %s (ждали mismatch)\n"
           "(г) обрыв по времени (предел 2 с, заглушка спит 60 с): исход %s · truncated %s (ждали cannot_verify и true)"
           % (k9a.get("outcome"), (k9a.get("error") or "")[:80], k9a.get("child_exit"), k9a_code, "исход: тело отказало" in k9a_out,
              k9b.get("outcome"), (k9b.get("error") or "").startswith("тело отказало:"), k9b.get("child_exit"),
              mismatch_mark, k9c.get("outcome"), k9c.get("child_exit"),
              k9d.get("outcome"), k9d.get("truncated")))

    # ───────────── К11: причина отказа — строка тела С ПРИЗНАКОМ ОШИБКИ, а не хвост вывода (находка COORD Н2)
    # Заглушки пишут байты прямо в поток: текст причины не зависит от кодировки консоли.
    k11_out_text = ("🔴 по куску «X» совпадений нет\n\nподсказка: проверь регистр и букву ё\n"
                    "искать шире — по самим записям разговоров: find-owner-word.py\n\n")
    k11_err_text = ("предупреждение: память роли велика\nERR: нет такой роли: ZZZ\n"
                    "подсказка: перечень ролей — правило role-roster-and-zones\n")
    k11_trace_text = ("Traceback (most recent call last):\n  File \"x.py\", line 1, in <module>\n"
                      "ValueError: плохое значение\n")
    put_stub("stub-k11-stdout-mark.py", "import sys\nsys.stdout.buffer.write(%r)\nsys.exit(1)\n" % k11_out_text.encode("utf-8"))
    put_stub("stub-k11-stderr-mark.py", "import sys\nsys.stdout.buffer.write(b'some output\\n')\nsys.stderr.buffer.write(%r)\nsys.exit(1)\n"
             % k11_err_text.encode("utf-8"))
    put_stub("stub-k11-trace.py", "import sys\nsys.stderr.buffer.write(%r)\nsys.exit(1)\n" % k11_trace_text.encode("utf-8"))
    k11_contract = stub_contract("k11", {"owner_words_find": "stub-k11-stdout-mark.py", "rules_get": "stub-k11-stderr-mark.py",
                                          "cards_list": "stub-k11-trace.py"})
    w11 = Wall(args.exe, k11_contract, m_stub_path)
    k11a, _ = w11.call("owner_words_find", {carg: CONTOUR_STAND, "text": "X"})
    k11b, _ = w11.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    k11c, _ = w11.call("cards_list", {carg: CONTOUR_STAND, "role": "PROTO"})
    w11.close()
    k11_code, k11_run_out, k11_run_err = run_mode(args.exe, k11_contract, m_stub_path,
                                                  ["owner_words_find", "--" + carg, CONTOUR_STAND, "--text", "X"])
    k11_run = (k11_run_out or "") + (k11_run_err or "")
    e11a, e11b, e11c = (k11a.get("error") or ""), (k11b.get("error") or ""), (k11c.get("error") or "")
    ok_k11a = (k11a.get("outcome") == "tool_failed" and k11a.get("child_exit") == 1
               and "совпадений нет" in e11a and "find-owner-word.py" not in e11a and "подсказка" not in e11a
               and k11_code == 6 and "совпадений нет" in k11_run)
    ok_k11b = (k11b.get("outcome") == "tool_failed" and k11b.get("child_exit") == 1
               and "нет такой роли" in e11b and "подсказка" not in e11b and "предупреждение" not in e11b)
    ok_k11c = (k11c.get("outcome") == "tool_failed" and k11c.get("child_exit") == 1
               and "ValueError: плохое значение" in e11c and "Traceback" not in e11c)
    v3.add("791-К11", ok_k11a and ok_k11b and ok_k11c,
           "причина отказа — строка тела с признаком ошибки, а не последняя строка вывода; без признака — последняя непустая",
           "(а) stdout: строка с признаком первой, за ней пустые строки и подсказка: исход %s · код тела %s · error «%s» "
           "(ждали «совпадений нет» без слов подсказки) · режим run: код %s (ждали 6), причина в тексте: %s\n"
           "(б) поток ошибок: признак во ВТОРОЙ строке из трёх: исход %s · код тела %s · error «%s» (ждали «нет такой роли» без подсказки)\n"
           "(в) признака нет, необработанное исключение: исход %s · код тела %s · error «%s» (ждали последнюю строку — само исключение)"
           % (k11a.get("outcome"), k11a.get("child_exit"), e11a[:120], k11_code, "совпадений нет" in k11_run,
              k11b.get("outcome"), k11b.get("child_exit"), e11b[:120],
              k11c.get("outcome"), k11c.get("child_exit"), e11c[:120]))

    # ───────────── К12: КАКАЯ строка с признаком — причина (два замечания COORD к случаю К11, карточка 791)
    # (а)(б) предупреждение с признаком напечатано РАНЬШЕ причины: причиной обязана стать причина;
    # (в) сводка «ERRORS: 0» и строка «ОТКАЗЫ: 0» признаком не считаются — признак-слово только целым словом;
    # (г) контроль: признак-слово с двоеточием остаётся признаком.
    k12_warn_out = ("🔴 предупреждение: память роли велика\n⛔ нет такой роли: ZZZ\n"
                    "подсказка: перечень ролей — правило role-roster-and-zones\n")
    k12_warn_err = "⛔ предупреждение: стенд старше срока\nERR: неверный ключ подтверждения\n"
    k12_summary = "ERRORS: 0\nОТКАЗЫ: 0\nитог: проверка не прошла, смотри строки выше\n"
    k12_word = "ОТКАЗ: нет прав на запись\nподсказка: спроси владельца\n"
    put_stub("stub-k12-warn-stdout.py", "import sys\nsys.stdout.buffer.write(%r)\nsys.exit(1)\n" % k12_warn_out.encode("utf-8"))
    put_stub("stub-k12-warn-stderr.py", "import sys\nsys.stdout.buffer.write(b'some output\\n')\nsys.stderr.buffer.write(%r)\nsys.exit(1)\n"
             % k12_warn_err.encode("utf-8"))
    put_stub("stub-k12-summary.py", "import sys\nsys.stdout.buffer.write(%r)\nsys.exit(1)\n" % k12_summary.encode("utf-8"))
    put_stub("stub-k12-word.py", "import sys\nsys.stdout.buffer.write(%r)\nsys.exit(1)\n" % k12_word.encode("utf-8"))
    k12_contract = stub_contract("k12", {"owner_words_find": "stub-k12-warn-stdout.py", "rules_get": "stub-k12-warn-stderr.py",
                                          "cards_list": "stub-k12-summary.py"})
    k12w_contract = stub_contract("k12w", {"owner_words_find": "stub-k12-word.py"})
    w12 = Wall(args.exe, k12_contract, m_stub_path)
    k12a, _ = w12.call("owner_words_find", {carg: CONTOUR_STAND, "text": "X"})
    k12b, _ = w12.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    k12c, _ = w12.call("cards_list", {carg: CONTOUR_STAND, "role": "PROTO"})
    w12.close()
    w12w = Wall(args.exe, k12w_contract, m_stub_path)
    k12d, _ = w12w.call("owner_words_find", {carg: CONTOUR_STAND, "text": "X"})
    w12w.close()
    e12a, e12b, e12c, e12d = [(x.get("error") or "") for x in (k12a, k12b, k12c, k12d)]
    ok_k12a = (k12a.get("outcome") == "tool_failed" and "нет такой роли" in e12a
               and "память роли велика" not in e12a and "подсказка" not in e12a)
    ok_k12b = (k12b.get("outcome") == "tool_failed" and "неверный ключ подтверждения" in e12b
               and "стенд старше срока" not in e12b)
    ok_k12c = (k12c.get("outcome") == "tool_failed" and "проверка не прошла" in e12c
               and "ERRORS" not in e12c and "ОТКАЗЫ" not in e12c)
    ok_k12d = (k12d.get("outcome") == "tool_failed" and "нет прав на запись" in e12d and "подсказка" not in e12d)
    v3.add("791-К12", ok_k12a and ok_k12b and ok_k12c and ok_k12d,
           "причина отказа — ПОСЛЕДНЯЯ строка с признаком ошибки; признак-слово считается только целым словом",
           "(а) stdout: предупреждение с признаком, за ним причина с признаком и подсказка: исход %s · error «%s» (ждали «нет такой роли»)\n"
           "(б) поток ошибок: предупреждение с признаком, за ним причина: исход %s · error «%s» (ждали «неверный ключ подтверждения»)\n"
           "(в) строки «ERRORS: 0» и «ОТКАЗЫ: 0», признака нет: исход %s · error «%s» (ждали последнюю строку — «проверка не прошла»)\n"
           "(г) контроль, признак-слово с двоеточием: исход %s · error «%s» (ждали «нет прав на запись» без подсказки)"
           % (k12a.get("outcome"), e12a[:120], k12b.get("outcome"), e12b[:120],
              k12c.get("outcome"), e12c[:120], k12d.get("outcome"), e12d[:120]))

    # ───────────── К10: защита живого контура — чистая проверка функции, процессы не запускаются
    def refused_live(tool, a):
        try:
            guard_live_call(tool, a)
        except LiveContourRefusal as e:
            return str(e)
        return None

    k10_cases = [
        # (подпись, вызов, аргументы, ждём отказ?)
        ("memory_read без section на живом", "memory_read", {carg: CONTOUR_LIVE, "role": "PROTO"}, True),
        ("memory_read с пустым section на живом", "memory_read", {carg: CONTOUR_LIVE, "role": "PROTO", "section": ""}, True),
        ("memory_read с section на живом", "memory_read", {carg: CONTOUR_LIVE, "role": "PROTO", "section": "identity"}, False),
        ("cards_list на живом", "cards_list", {carg: CONTOUR_LIVE, "role": "PROTO"}, True),
        ("feed_read на живом", "feed_read", {carg: CONTOUR_LIVE, "role": "PROTO"}, True),
        ("feed_write на живом", "feed_write", {carg: CONTOUR_LIVE, "role": "PROTO", "to": "COORD", "body": "x"}, True),
        ("contour_info на живом", "contour_info", {carg: CONTOUR_LIVE}, False),
        ("rules_get на живом", "rules_get", {carg: CONTOUR_LIVE, "list": True}, False),
        ("memory_read без section при ДРУГОМ имени аргумента контура", "memory_read", {"where": CONTOUR_LIVE, "role": "PROTO"}, True),
        ("memory_read без section на стенде", "memory_read", {carg: CONTOUR_STAND, "role": "PROTO"}, False),
        ("cards_list на стенде", "cards_list", {carg: CONTOUR_STAND, "role": "PROTO"}, False),
        ("feed_read на стенде", "feed_read", {carg: CONTOUR_STAND, "role": "PROTO"}, False),
        ("feed_read с выдуманным контуром", "feed_read", {carg: "atlas-typo", "role": "PROTO"}, False),
        ("feed_read без контура", "feed_read", {"role": "PROTO"}, False),
        # те же вызовы в форме argv режима run (без имени вызова)
        ("argv: memory_read без --section на живом", "memory_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO"], True),
        ("argv: memory_read с --section без значения на живом", "memory_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO", "--section"], True),
        ("argv: memory_read с --section identity на живом", "memory_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO", "--section", "identity"], False),
        ("argv: cards_list на живом", "cards_list", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO"], True),
        ("argv: feed_read на живом", "feed_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO"], True),
        ("argv: contour_info на живом", "contour_info", ["--" + carg, CONTOUR_LIVE], False),
        ("argv: cards_list на стенде", "cards_list", ["--" + carg, CONTOUR_STAND, "--role", "PROTO"], False),
        ("argv: feed_read на стенде", "feed_read", ["--" + carg, CONTOUR_STAND, "--role", "PROTO"], False),
    ]
    k10_bad = []
    k10_rows = []
    for label, tool, a, want_refusal in k10_cases:
        got = refused_live(tool, a)
        good = (got is not None) == want_refusal and (got is None or (tool in got and CONTOUR_LIVE in got))
        k10_rows.append("%s %s: %s" % ("ок" if good else "НЕ ТАК", label, "отказ" if got is not None else "разрешено"))
        if not good:
            k10_bad.append(label)
    v3.add("791-К10", not k10_bad,
           "защита живого контура: на живом приёмке разрешены только contour_info, rules_get и memory_read с непустым section; cards_list, feed_read, memory_read без раздела — отказ с названием вызова; на стенде, без контура и с выдуманным контуром — не трогает",
           "проверено случаев %d (процессы не запускались), не так: %d\n%s"
           % (len(k10_cases), len(k10_bad), "\n".join(k10_rows)))


def main():
    try:
        return run_acceptance()
    except LiveContourRefusal as e:
        print("⛔ ПРИЁМКА ОСТАНОВЛЕНА: %s" % e)
        return 2


def run_acceptance():
    ap = argparse.ArgumentParser(description="приёмка стены контура gordi (этап Э1, карточка 779)")
    ap.add_argument("--contours", required=True, help="боевой манифест контуров этой машины")
    ap.add_argument("--exe", default=DEFAULT_EXE)
    ap.add_argument("--contract", default=CONTRACT)
    ap.add_argument("--out", default=None, help="каталог для копий договора и манифеста (по умолчанию — временный)")
    args = ap.parse_args()

    if not os.path.exists(args.exe):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: сборки нет — %s" % args.exe)
        print("   собрать: dotnet build %s" % os.path.join(SERVICE, "GordiWall"))
        return 2
    if not os.path.exists(args.contract):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: договора нет — %s" % args.contract)
        return 2
    if not os.path.exists(args.contours):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: манифеста нет — %s" % args.contours)
        return 2

    exe_time = os.path.getmtime(args.exe)
    src_time, src_file = newest_source()
    print("── ЧАС СБОРКИ И ИСХОДНИКОВ")
    print("   сборка исполнимого файла ... %s" % utc(exe_time))
    print("   последняя правка исходников  %s (%s)" % (utc(src_time), src_file))
    if exe_time < src_time:
        print("⏸ СБОРКА СТАРШЕ ИСХОДНИКОВ: приёмка её НЕ СУДИТ. Это не провал и не проход —")
        print("   она проверила бы не то, что написано. Пересобрать: dotnet build %s, затем запустить снова."
              % os.path.join(SERVICE, "GordiWall"))
        return 3

    work = args.out or tempfile.mkdtemp(prefix="check-wall-")
    if not os.path.isdir(work):
        os.makedirs(work)

    manifest = read_json(args.contours)
    stand = [c for c in manifest.get("contours", []) if c.get("id") == CONTOUR_STAND]
    if not stand:
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: в манифесте нет контура «%s» — пишущие пробы некуда вести." % CONTOUR_STAND)
        print("   Живую базу приёмка не пишет НАМЕРЕННО.")
        return 2
    if not os.path.exists(stand[0]["storage"]):
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: копии базы нет — %s" % stand[0]["storage"])
        return 2

    v = Verdict()
    contract_doc = read_json(args.contract)
    # Имя аргумента выбора контура приёмка берёт из договора по той же пометке, что и служба
    contour_args = [a["name"] for a in contract_doc["common_args"] if a.get("selects") == "contour"]
    if len(contour_args) != 1:
        print("⛔ ПРОВЕРЯТЬ НЕЧЕМ: в договоре %s пометка selects=contour стоит у %d аргументов, нужен ровно один"
              % (args.contract, len(contour_args)))
        return 2
    CARG = contour_args[0]

    # ─────────────────────────────────────── ① перечень вызовов из ОДНОГО файла
    code, out, err = run_mode(args.exe, args.contract, args.contours, ["contour_info", "--contour", CONTOUR_LIVE])
    tools_out = subprocess.run([args.exe, "tools", "--contract", args.contract, "--contours", args.contours],
                               capture_output=True, encoding="utf-8", errors="replace", timeout=120).stdout
    printed_count = None
    printed_fp = None
    for line in tools_out.splitlines():
        if line.startswith("вызовов "):
            printed_count = int(line.split()[-1])
        if line.startswith("отпечаток перечня"):
            printed_fp = line.split()[-1]

    w = Wall(args.exe, args.contract, args.contours)
    listed = w.list_tools()
    in_contract = len(contract_doc["tools"])
    ok1 = (printed_count == in_contract == len(listed) == EXPECTED_TOOL_COUNT
           and printed_fp == EXPECTED_TOOLS_FINGERPRINT
           and TOOL_COUNT_RANGE[0] <= in_contract <= TOOL_COUNT_RANGE[1])
    v.add("①", ok1, "перечень вызовов берётся из ОДНОГО файла договора",
          "в файле договора %d · служба объявила %d · перечень напечатал %s · ожидалось %d (предел %d–%d)\n"
          "отпечаток перечня %s · ожидался %s"
          % (in_contract, len(listed), printed_count, EXPECTED_TOOL_COUNT,
             TOOL_COUNT_RANGE[0], TOOL_COUNT_RANGE[1], printed_fp, EXPECTED_TOOLS_FINGERPRINT))

    # ─────────────────────────────────────── ⑤ вызов с ВЕРНЫМ контуром обязан пройти
    s5, t5 = w.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    ok5 = s5.get("outcome") == "passed" and len(t5) > 500 and s5.get("truncated") is False
    v.add("⑤", ok5, "встречный случай: вызов с верным контуром ПРОХОДИТ",
          "исход %s · усечено %s · знаков в ответе %d"
          % (s5.get("outcome"), s5.get("truncated"), len(t5)))

    # ─────────────────────────────────────── ③ контур приходит В ВЫЗОВЕ, без него — отказ
    s3a, t3a = w.call("memory_read", {"role": "PROTO", "section": "identity"})
    s3b, t3b = w.call("memory_read", {"contour": "atlas-typo", "role": "PROTO"})
    # Судим по ТОЧНОЙ причине: «не передан обязательный аргумент «<имя>»». Подстрока имени ошибалась бы:
    # она есть и в имени файла манифеста gordi-contours.json.
    reason_3a = "не передан обязательный аргумент «%s»" % CARG
    ok3 = (s3a.get("outcome") == "refused" and (s3a.get("error") or "").startswith(reason_3a)
           and s3b.get("outcome") == "refused" and "atlas-typo" in (s3b.get("error") or ""))
    v.add("③", ok3, "контур передаётся В ВЫЗОВЕ; без него и с неизвестным именем — отказ",
          "без контура: %s — %s (ожидалась причина, начинающаяся с «%s»)\nнеизвестный контур: %s — %s"
          % (s3a.get("outcome"), (s3a.get("error") or "")[:120], reason_3a,
             s3b.get("outcome"), (s3b.get("error") or "")[:120]))

    # ─────────────────────────────────────── ④ подмена переменных среды НЕ меняет поведение
    w_env = Wall(args.exe, args.contract, args.contours, env_extra={
        "MEZO_CONTAINER": "C:/нет-такого-контура",
        "MEZO_DB": "C:/нет-такой-базы/mezosync.db",
        "MEZO_ROLE": "COORD",
    })
    s4, t4 = w_env.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    w_env.close()
    ok4 = s4.get("outcome") == "passed" and t4 == t5
    v.add("④", ok4, "встречный случай: подмена MEZO_* НЕ меняет ответ",
          "исход %s · текст совпал со вызовом без подмены: %s (знаков %d против %d)"
          % (s4.get("outcome"), "ДА" if t4 == t5 else "НЕТ", len(t4), len(t5)))

    # ─────────────────────────────────────── ② типизированный исход и признак усечения
    # (а) расхождение состояния: версия раздела заведомо не та
    s2a, t2a = w.call("memory_save", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "state",
                                      "body": "проба приёмки стены — записана НЕ должна быть",
                                      "expect_version": 1})
    # (б) усечение. С карточки 791 длинный ВЫВОД тела не режется, а выдаётся частями (случаи К1 и К7);
    #     отсекать стена вправе только предупреждения тела длиннее предела — это и есть «настоящее» усечение.
    #     Заглушка печатает 5000 знаков в поток ошибок; манифест с низким пределом знаков ведёт на каталог заглушки.
    stub2 = os.path.join(work, "stub-2b")
    if not os.path.isdir(stub2):
        os.makedirs(stub2)
    io.open(os.path.join(stub2, "stub-warn-long.py"), "w", encoding="utf-8", newline="\n").write(
        "import sys\nsys.stderr.write('WARN-HEAD ' + 'w' * 5000 + ' WARN-TAIL\\n')\n")
    low = json.loads(json.dumps(manifest))
    low["limits"] = {"timeout_seconds": 120, "max_output_chars": 2000}
    for c in low["contours"]:
        c["tools"] = {"runtime": stub2, "vnext": stub2}
    low_path = os.path.join(work, "contours-low-limit.json")
    write_json(low_path, low)
    long_warn = json.loads(json.dumps(contract_doc))
    for t in long_warn["tools"]:
        if t["name"] == "rules_get":
            t["exec"]["script"] = "stub-warn-long.py"
    long_warn_path = os.path.join(work, "contract-long-warnings.json")
    write_json(long_warn_path, long_warn)
    w_low = Wall(args.exe, long_warn_path, low_path)
    s2b, t2b = w_low.call("rules_get", {"contour": CONTOUR_LIVE, "list": True})
    w_low.close()
    # (в) тело не на месте: копия договора с несуществующим файлом инструмента
    gone = json.loads(json.dumps(contract_doc))
    for t in gone["tools"]:
        if t["name"] == "rules_get":
            t["exec"]["script"] = "нет-такого-инструмента.py"
    gone_path = os.path.join(work, "contract-missing-body.json")
    write_json(gone_path, gone)
    w_gone = Wall(args.exe, gone_path, args.contours)
    s2c, t2c = w_gone.call("rules_get", {"contour": CONTOUR_LIVE, "list": True})
    w_gone.close()

    ok2 = (s2a.get("outcome") == "mismatch" and s2a.get("child_exit") not in (None, 0)
           and s2b.get("truncated") is True and "предел знаков" in (s2b.get("truncate_reason") or "")
           and "WARN-HEAD" in s2b.get("warnings", "") and "WARN-TAIL" in s2b.get("warnings", "")
           and "вырезано" in s2b.get("warnings", "") and len(s2b.get("warnings", "")) <= 2000
           and s2c.get("outcome") == "not_started" and s2c.get("child_exit") is None)
    v.add("②", ok2, "исход — из закрытого перечня, усечение названо, код выхода НЕ договор",
          "расхождение состояния: исход %s, код тела %s\n"
          "усечение (предупреждения тела длиннее предела; длинный вывод идёт частями — случаи К1 и К7): признак %s, причина «%s», знаков в ответе %d\n"
          "тела нет на месте: исход %s, код тела %s (кода нет вовсе — судить по нему было бы нечем)"
          % (s2a.get("outcome"), s2a.get("child_exit"),
             s2b.get("truncated"), s2b.get("truncate_reason"), len(t2b),
             s2c.get("outcome"), s2c.get("child_exit")))

    # ─────────────────────────────────────── ⑦ режим только-чтение мимо службы
    code7r, out7r, err7r = run_mode(args.exe, args.contract, args.contours,
                                    ["memory_read", "--contour", CONTOUR_LIVE, "--role", "PROTO", "--section", "identity"])
    code7w, out7w, err7w = run_mode(args.exe, args.contract, args.contours,
                                    ["feed_write", "--contour", CONTOUR_STAND, "--role", "PROTO",
                                     "--to", "COORD", "--body", "проба приёмки"])
    w_ro = Wall(args.exe, args.contract, args.contours, read_only=True)
    s7, t7 = w_ro.call("feed_write", {"contour": CONTOUR_STAND, "role": "PROTO", "to": "COORD", "body": "проба"})
    w_ro.close()
    ok7 = ("МИМО службы" in err7r and code7r == 0 and "исход: прошло" in out7r
           and code7w == 4 and "отказ" in out7w
           and s7.get("outcome") == "refused")
    v.add("⑦", ok7, "мимо службы можно ЧИТАТЬ, и об этом сказано вслух; запись мимо службы — отказ",
          "чтение мимо службы: код %d, предупреждение в потоке ошибок: %s\n"
          "запись мимо службы: код %d, исход в тексте: %s\n"
          "служба в режиме только-чтение на запись: %s"
          % (code7r, "ДА" if "МИМО службы" in err7r else "НЕТ",
             code7w, out7w.splitlines()[0] if out7w else "(пусто)",
             s7.get("outcome")))

    # ─────────────────────────────────────── ⑧ две нарочные поломки
    # Поломка А: из копии договора убран один вызов ⇒ обязан провалиться РОВНО критерий ①
    broken_a = json.loads(json.dumps(contract_doc))
    broken_a["tools"] = [t for t in broken_a["tools"] if t["name"] != "owner_words_find"]
    path_a = os.path.join(work, "contract-broken-a.json")
    write_json(path_a, broken_a)
    tools_a = subprocess.run([args.exe, "tools", "--contract", path_a, "--contours", args.contours],
                             capture_output=True, encoding="utf-8", errors="replace", timeout=120).stdout
    fp_a = None
    count_a = None
    for line in tools_a.splitlines():
        if line.startswith("вызовов "):
            count_a = int(line.split()[-1])
        if line.startswith("отпечаток перечня"):
            fp_a = line.split()[-1]
    w_a = Wall(args.exe, path_a, args.contours)
    s_a, t_a = w_a.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    w_a.close()
    a_breaks_1 = (fp_a != EXPECTED_TOOLS_FINGERPRINT or count_a != EXPECTED_TOOL_COUNT)
    a_keeps_5 = s_a.get("outcome") == "passed"

    # Поломка Б: в копии договора стёрты признаки расхождения ⇒ обязан провалиться РОВНО критерий ②
    broken_b = json.loads(json.dumps(contract_doc))
    for t in broken_b["tools"]:
        if t["name"] == "memory_save":
            t["exec"]["mismatch_when"] = []
    path_b = os.path.join(work, "contract-broken-b.json")
    write_json(path_b, broken_b)
    w_b = Wall(args.exe, path_b, args.contours)
    s_b, t_b = w_b.call("memory_save", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "state",
                                        "body": "проба приёмки стены", "expect_version": 1})
    s_b5, t_b5 = w_b.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    w_b.close()
    b_breaks_2 = s_b.get("outcome") != "mismatch"
    b_keeps_5 = s_b5.get("outcome") == "passed"

    ok8 = a_breaks_1 and a_keeps_5 and b_breaks_2 and b_keeps_5
    v.add("⑧", ok8, "две нарочные поломки валят РОВНО свой критерий",
          "А (из договора убран один вызов): критерий ① провалился: %s (вызовов %s, отпечаток %s) · критерий ⑤ цел: %s\n"
          "Б (стёрты признаки расхождения): критерий ② провалился: %s (исход стал «%s» вместо «mismatch») · критерий ⑤ цел: %s"
          % ("ДА" if a_breaks_1 else "НЕТ", count_a, fp_a, "ДА" if a_keeps_5 else "НЕТ",
             "ДА" if b_breaks_2 else "НЕТ", s_b.get("outcome"), "ДА" if b_keeps_5 else "НЕТ"))

    # ═══════════════════════════════════════ карточка 787: КТО исполняет требование договора
    v2 = Verdict()
    selects_msg = 'selects="contour"'

    # ② пометки нет → отказ при загрузке, названо, чего не хватает
    d2 = json.loads(json.dumps(contract_doc))
    for a in d2["common_args"]:
        a.pop("selects", None)
    p2 = os.path.join(work, "contract-no-selects.json")
    write_json(p2, d2)
    c2a, e2a = load_refusal(args.exe, p2, args.contours)
    # две пометки → тоже отказ
    d2b = json.loads(json.dumps(contract_doc))
    d2b["common_args"].append({"name": "contour_two", "type": "string", "required": True, "selects": "contour",
                               "description": "второй выбор контура — нарочная поломка"})
    p2b = os.path.join(work, "contract-two-selects.json")
    write_json(p2b, d2b)
    c2b, e2b = load_refusal(args.exe, p2b, args.contours)
    # целый договор загружается (встречный случай)
    c2ok, e2ok = load_refusal(args.exe, args.contract, args.contours)
    ok_s2 = (c2a == 4 and "договор не читается" in e2a and selects_msg in e2a and "ни у одного" in e2a
             and c2b == 4 and "договор не читается" in e2b and selects_msg in e2b and CARG in e2b and "contour_two" in e2b
             and c2ok == 0)
    v2.add("787-②", ok_s2, "какой аргумент выбирает контур, служба узнаёт ИЗ ДОГОВОРА; нет пометки или их две — отказ при загрузке",
           "без пометки: код %s — %s\nдве пометки: код %s — %s\nцелый договор: код %s"
           % (c2a, e2a.strip()[:200], c2b, e2b.strip()[:200], c2ok))

    # ③ выбор контура не обязателен → договор не загружается, причина названа
    d3 = json.loads(json.dumps(contract_doc))
    for a in d3["common_args"]:
        if a.get("selects") == "contour":
            a["required"] = False
    p3 = os.path.join(work, "contract-contour-optional.json")
    write_json(p3, d3)
    c3, e3 = load_refusal(args.exe, p3, args.contours)
    ok_s3 = (c3 == 4 and "договор не читается" in e3 and CARG in e3
             and "исполнять вызов без контура не на чем" in e3 and "угадывать" in e3)
    v2.add("787-③", ok_s3, "договор с НЕобязательным выбором контура не загружается; причина названа",
           "код %s — %s" % (c3, e3.strip()[:300]))

    # ④ обязательность читается из договора на ВТОРОМ общем аргументе
    base4 = json.loads(json.dumps(contract_doc))
    base4["common_args"].append({"name": "stand_tag", "type": "string", "required": True,
                                 "description": "нарочный второй общий аргумент приёмки"})
    p4r = os.path.join(work, "contract-second-required.json")
    write_json(p4r, base4)
    w4r = Wall(args.exe, p4r, args.contours)
    s4r_no, _ = w4r.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    s4r_yes, t4r_yes = w4r.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity",
                                                "stand_tag": "x"})
    listed4 = w4r.list_tools()
    w4r.close()
    schema4 = [t for t in listed4 if t["name"] == "memory_read"][0]["inputSchema"]
    base4o = json.loads(json.dumps(base4))
    base4o["common_args"][-1]["required"] = False
    p4o = os.path.join(work, "contract-second-optional.json")
    write_json(p4o, base4o)
    w4o = Wall(args.exe, p4o, args.contours)
    s4o_no, t4o_no = w4o.call("memory_read", {"contour": CONTOUR_LIVE, "role": "PROTO", "section": "identity"})
    listed4o = w4o.list_tools()
    w4o.close()
    schema4o = [t for t in listed4o if t["name"] == "memory_read"][0]["inputSchema"]
    ok_s4 = (s4r_no.get("outcome") == "refused"
             and (s4r_no.get("error") or "").startswith("не передан обязательный аргумент «stand_tag»")
             and s4r_yes.get("outcome") == "passed"
             and "stand_tag" in schema4["required"] and "stand_tag" in schema4["properties"]
             and s4o_no.get("outcome") == "passed" and len(t4o_no) > 500
             and "stand_tag" not in schema4o["required"] and "stand_tag" in schema4o["properties"])
    v2.add("787-④", ok_s4, "обязательность общего аргумента читается из договора: required=true — отказ с его именем, required=false — проходит",
           "required=true, без аргумента: %s — %s\nrequired=true, с аргументом: %s\n"
           "required=false, без аргумента: %s (знаков %d)\n"
           "схема MCP: required=true → в required: %s; required=false → в required: %s (в properties есть: %s)"
           % (s4r_no.get("outcome"), (s4r_no.get("error") or "")[:110], s4r_yes.get("outcome"),
              s4o_no.get("outcome"), len(t4o_no),
              "stand_tag" in schema4["required"], "stand_tag" in schema4o["required"], "stand_tag" in schema4o["properties"]))

    # ⑤ встречный на целом договоре: верный контур проходит
    ok_s5 = ok5 and c2ok == 0
    v2.add("787-⑤", ok_s5, "встречный случай: на ЦЕЛОМ договоре вызов с верным контуром проходит",
           "исход %s · договор с пометкой selects=contour загружается (код %s)" % (s5.get("outcome"), c2ok))

    # ⑨ E9 (TAXO): имя общего аргумента выбора контура берётся из договора, а не из кода
    d9 = json.loads(json.dumps(contract_doc))
    for a in d9["common_args"]:
        if a.get("selects") == "contour":
            a["name"] = "where"
    p9 = os.path.join(work, "contract-where.json")
    write_json(p9, d9)
    w9 = Wall(args.exe, p9, args.contours)
    s9_where, _ = w9.call("memory_read", {"where": CONTOUR_STAND, "role": "PROTO", "section": "identity"})
    s9_old, _ = w9.call("memory_read", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "identity"})
    # Находка TAXO (16.11): служба может отказывать верно, а КЛИЕНТУ объявлять контур необязательным —
    # схему MCP судим отдельно — у ВСЕХ вызовов tools/list: новое имя есть в required и в properties, прежнего имени в properties нет.
    tools9 = w9.list_tools()
    w9.close()
    bad9 = []
    for t9 in tools9:
        sch9 = t9.get("inputSchema") or {}
        r9, pr9 = sch9.get("required") or [], sch9.get("properties") or {}
        if "where" not in r9 or "where" not in pr9 or "contour" in pr9:
            bad9.append(t9["name"])
    req9_all = bool(tools9) and all("where" in ((t9.get("inputSchema") or {}).get("required") or []) for t9 in tools9)
    props9_all = bool(tools9) and all("where" in ((t9.get("inputSchema") or {}).get("properties") or {}) for t9 in tools9)
    old_in_props9 = any("contour" in ((t9.get("inputSchema") or {}).get("properties") or {}) for t9 in tools9)
    c9r, o9r, _ = run_mode(args.exe, p9, args.contours,
                           ["memory_read", "--where", CONTOUR_STAND, "--role", "PROTO", "--section", "identity"])
    ok_e9 = (s9_where.get("outcome") == "passed" and s9_where.get("contour") == CONTOUR_STAND
             and s9_old.get("outcome") == "refused" and "where" in (s9_old.get("error") or "")
             and c9r == 0 and "исход: прошло" in o9r
             and bool(tools9) and not bad9)
    v2.add("787-E9", ok_e9, "общий аргумент выбора контура переименован в договоре в «where»: вызовы с where работают, вызов с contour — отказ с именем where, схема MCP объявляет where обязательным",
           "с where (служба): исход %s, контур в ответе «%s»\nс contour (служба): %s — %s\nс --where (режим run): код %s\n"
           "схема MCP (все %d вызовов tools/list): where в required у всех: %s · where в properties у всех: %s · contour в properties у кого-либо: %s (ждали: нет)\n"
           "вызовы-нарушители: %s"
           % (s9_where.get("outcome"), s9_where.get("contour"), s9_old.get("outcome"), (s9_old.get("error") or "")[:130], c9r,
              len(tools9), req9_all, props9_all, old_in_props9, ", ".join(bad9) or "нет"))

    # F (TAXO, находка F′): на ЦЕЛОМ договоре схема MCP КАЖДОГО вызова объявляет аргумент выбора контура обязательным
    listed_f = listed
    bad_f = []
    for tf in listed_f:
        schf = tf.get("inputSchema") or {}
        if CARG not in (schf.get("required") or []) or CARG not in (schf.get("properties") or {}):
            bad_f.append(tf["name"])
    ok_f = len(listed_f) == EXPECTED_TOOL_COUNT and not bad_f
    v2.add("787-F", ok_f, "на целом договоре схема MCP КАЖДОГО вызова объявляет аргумент выбора контура обязательным (есть и в required, и в properties)",
           "аргумент выбора контура (из договора по пометке selects=contour): «%s»\n"
           "вызовов в tools/list: %d (ждали %d) · объявили его обязательным: %d\n"
           "вызовы-нарушители: %s"
           % (CARG, len(listed_f), EXPECTED_TOOL_COUNT, len(listed_f) - len(bad_f), ", ".join(bad_f) or "нет"))

    # ⑩ E10 (TAXO): перечень значений (enum) общего аргумента читается из договора
    d10 = json.loads(json.dumps(contract_doc))
    d10["common_args"].append({"name": "stand_mode", "type": "string", "required": False, "enum": ["alpha", "beta"],
                               "description": "нарочный второй общий аргумент приёмки с перечнем значений"})
    p10 = os.path.join(work, "contract-second-enum.json")
    write_json(p10, d10)
    w10 = Wall(args.exe, p10, args.contours)
    s10_bad, _ = w10.call("memory_read", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "identity", "stand_mode": "gamma"})
    s10_ok, _ = w10.call("memory_read", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "identity", "stand_mode": "alpha"})
    s10_none, _ = w10.call("memory_read", {"contour": CONTOUR_STAND, "role": "PROTO", "section": "identity"})
    schema10 = [t for t in w10.list_tools() if t["name"] == "memory_read"][0]["inputSchema"]
    w10.close()
    ok_e10 = (s10_bad.get("outcome") == "refused" and "gamma" in (s10_bad.get("error") or "")
              and "stand_mode" in (s10_bad.get("error") or "")
              and s10_ok.get("outcome") == "passed" and s10_none.get("outcome") == "passed"
              and schema10["properties"]["stand_mode"].get("enum") == ["alpha", "beta"])
    v2.add("787-E10", ok_e10, "у второго общего аргумента есть перечень значений: вне перечня — отказ, из перечня — проходит",
           "gamma (вне перечня): %s — %s\nalpha (из перечня): %s\nбез аргумента: %s\nenum в схеме MCP: %s"
           % (s10_bad.get("outcome"), (s10_bad.get("error") or "")[:130], s10_ok.get("outcome"), s10_none.get("outcome"),
              schema10["properties"]["stand_mode"].get("enum")))

    w.close()

    # ═══════════════════════════════════════ карточка 791: части вместо обрезки, предупреждения отдельно, честный «не запустилось»
    v3 = Verdict()
    cases_791(args, work, manifest, contract_doc, CARG, v3, s2c)

    # ─────────────────────────────────────── вывод
    print("── ПРИЁМКА СТЕНЫ КОНТУРА GORDI · этап Э1 · карточка 779")
    print("   сборка ... %s" % args.exe)
    print("   договор .. %s" % args.contract)
    print("   манифест . %s" % args.contours)
    print("   копии для поломок ... %s" % work)
    print("")
    print("── критерии карточки 779 (прежние семь)")
    v.print_all()
    print("")
    print("── случаи карточки 787 (кто исполняет требование договора)")
    v2.print_all()
    print("")
    print("── случаи карточки 791 (части вместо обрезки · предупреждения отдельно · честный «не запустилось» · отметка сборки · пустая запись · незнакомый аргумент · служебные записи)")
    v3.print_all()
    print("")
    print("⚖️ ЭТИ ДВА КРИТЕРИЯ МАШИНА НЕ СУДИТ — говорю прямо, чтобы зелёное не прочлось шире:")
    print("   ⑥ полный рабочий отрезок роли через стену — доказывается работой роли (записка · память · карточка),")
    print("      а не этим файлом. Прогон приёмки отрезком НЕ является.")
    print("   ⑨ подпись приёмки ставит роль, которая службу НЕ писала. Свой прогон за чужую руку не считается.")
    print("")
    bad = v.failed() + v2.failed() + v3.failed()
    if bad:
        print("🔴 ПРОВАЛИЛОСЬ %d: %s (карточка 779: %d из %d прошло · карточка 787: %d из %d прошло · карточка 791: %d из %d прошло)"
              % (len(bad), " · ".join(r[0] for r in bad),
                 len(v.rows) - len(v.failed()), len(v.rows), len(v2.rows) - len(v2.failed()), len(v2.rows),
                 len(v3.rows) - len(v3.failed()), len(v3.rows)))
        return 1
    print("✅ ВСЕ МАШИННЫЕ КРИТЕРИИ ПРОШЛИ: карточка 779 — %d из %d · карточка 787 — %d из %d · карточка 791 — %d из %d (⑥ и ⑨ карточки 779 — за человеком)"
          % (len(v.rows), len(v.rows), len(v2.rows), len(v2.rows), len(v3.rows), len(v3.rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
