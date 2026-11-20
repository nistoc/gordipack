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

Карточка 781 (договор 2.0.0, этап Э2) добавила раздел «карточка 781»: варианты вызова (один вызов — несколько тел по значению
типизированного аргумента) и объявленная передача значения аргумента в переменную среды тела (exec.env); через них в договор
вошли поиск по памяти, сжатие слоя памяти, запись слова владельца и заведение карточки при прежних ДВЕНАДЦАТИ вызовах.
Случаи: В1 состав · В2 разбор договора отвергает кривые варианты · В3 выбор варианта (заглушки; служба и режим run) ·
В4 рука тела (среда службы к телу не протекает; объявленный env доходит) · В5 поиск по трём слоям (критерий ⑥) ·
В6 сжатие слоя (критерий ④) · В7 завести карточку · В8 записать слово владельца (настоящий искатель, подставной домашний каталог) ·
В9 читающие вызовы пишут только объявленное. Случаи В5–В9 идут на МАЛОЙ КОПИИ установленного контура в рабочем каталоге
(<out>/e2/c): инструменты ветки (scripts → .mezosync/scripts, vnext/prototype → vnext-tools) и копия учебной базы с шагом схемы
слоёв, применённым к КОПИИ; живая и учебная базы не трогаются. Три нарочные поломки (П1–П3) делаются копиями договора, и каждая
обязана уронить РОВНО свои случаи и названным механизмом (список и прямой признак названы в BREAKS_781). Новые вызовы на живом контуре приёмка не зовёт вовсе.

Карточка 814 (этап Э3, предмет П1) добавила раздел «Э3-П1»: справка службы строится из того же файла договора. Случаи С1–С8:
С1 общая справка · С2 справка по каждому вызову · С3 незнакомый вызов (код 4) · С4 --help и -h без режима (предел 20 с на процесс,
закрытый ввод) и run <вызов> --help без запуска тела · С5 без манифеста контуров · С6 копия договора с тринадцатым вызовом и
переименованным аргументом, без пересборки · С7 перечень режимов в отказе и в справке · С8 таблица «исход → код выхода» против режима run
на заглушках. Проверяющие С1–С3 и С6–С8 чистые (текст справки + договор + код выхода → исход); нарочные поломки Л1–Л3 портят ТЕКСТ,
Л4 подаёт справку от целого договора в случай С6. Ключ --only-e3p1 судит один этот раздел (в том числе на сборке без справки: прогон «до»).

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
# (часть II). Новых ВЫЗОВОВ нет: число прежнее — 12. Если число или отпечаток когда-нибудь сменятся, это решение
# человека, а не пересчёт приёмки.
# Карточка 781: договор 2.0.0 — варианты вызова. Число вызовов по-прежнему 12, но имена и умения другие, а формула отпечатка
# теперь учитывает ещё аргумент выбора и ключи вариантов: снятый вариант меняет отпечаток. Значение ниже изменено РУКОЙ,
# по решению PROTO на карточке 781 (17.11.2026 01:55 UTC), а не пересчитано приёмкой.
EXPECTED_TOOL_COUNT = 12
EXPECTED_TOOLS_FINGERPRINT = "8903ca5bd7e9"
TOOL_COUNT_RANGE = (8, 12)

CONTOUR_LIVE = "atlas"
CONTOUR_STAND = "atlas-stand"


class LiveContourRefusal(Exception):
    """Приёмка отказалась звать на живом контуре вызов, который не измерен как не пишущий."""


# На живом контуре приёмка вправе звать ТОЛЬКО измеренное как не пишущее (случай К8 меряет на копии стенда):
# contour_info и rules_get не меняют ничего; memory_read не меняет ничего ТОЛЬКО при непустом section —
# без раздела он отмечает подсказку в живой базе (таблица hint_seen). cards_read и feed_read пишут служебные таблицы (hint_seen, read_batches).
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


def run_mode(exe, contract, contours, argv, env_extra=None):
    """Однократный вызов мимо службы. Отдаёт код выхода, вывод и поток ошибок целиком.
    Защита живого контура срабатывает ДО запуска процесса. env_extra — переменные среды самой службы (случай В4)."""
    if argv:
        guard_live_call(argv[0], argv[1:])
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    if env_extra:
        env.update(env_extra)
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


def table_digests(db_path, only=None):
    """По каждой таблице базы: (число строк, sha256 по содержимому). Читается только на чтение.
    only — перечень имён, если нужны не все таблицы."""
    import hashlib
    import sqlite3
    conn = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    out = {}
    try:
        names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1")]
        if only is not None:
            names = [n for n in names if n in only]
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
    # договор 2.0.0: вызовы с вариантами пробуются по варианту — каждый обязан укладываться в service_writes вызова
    "memory_read": [("", {"role": "PROTO"}, None), (" view=edit", {"role": "PROTO", "view": "edit", "section": "state"}, None)],
    "memory_find": {"role": "PROTO", "query": "слово"},
    # два варианта: обычное чтение и отбор to_me. Каждый обязан задеть свою таблицу — иначе замер её не видел:
    # обычное чтение — read_batches (запись о показанной партии; у роли без непрочитанного её нет, и цикл по ролям идёт дальше),
    # отбор to_me — cursor_segments
    "feed_read": [("", {"role": "COORD"}, "read_batches"), (" to_me", {"role": "COORD", "to_me": True}, "cursor_segments")],
    "cards_read": [("", {"role": "PROTO"}, None), (" view=card", {"view": "card", "card": 1}, None)],
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
                set_script_all(t, mapping[t["name"]])
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
    mismatch_marks = [t for t in contract_doc["tools"] if t["name"] == "memory_write"][0]["variants"]["save"]["exec"].get("mismatch_when") or []
    mismatch_mark = mismatch_marks[0] if mismatch_marks else None
    put_stub("stub-k9-mismatch.py", "import sys\nsys.stdout.write(%r + '\\n')\nsys.exit(1)\n" % (mismatch_mark or ""))
    put_stub("stub-k9-sleep.py", "import time\ntime.sleep(60)\n")
    k9_contract = stub_contract("k9", {"rules_get": "stub-k9-stderr.py", "owner_words_find": "stub-k9-stdout3.py",
                                        "memory_write": "stub-k9-mismatch.py"})
    w9k = Wall(args.exe, k9_contract, m_stub_path)
    k9a, _ = w9k.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    k9b, _ = w9k.call("owner_words_find", {carg: CONTOUR_STAND, "text": "x"})
    k9c, _ = w9k.call("memory_write", {carg: CONTOUR_STAND, "action": "save", "role": "PROTO", "section": "state", "body": "заглушка", "expect_version": 1})
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
                                          "cards_read": "stub-k11-trace.py"})
    w11 = Wall(args.exe, k11_contract, m_stub_path)
    k11a, _ = w11.call("owner_words_find", {carg: CONTOUR_STAND, "text": "X"})
    k11b, _ = w11.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    k11c, _ = w11.call("cards_read", {carg: CONTOUR_STAND, "role": "PROTO"})
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
                                          "cards_read": "stub-k12-summary.py"})
    k12w_contract = stub_contract("k12w", {"owner_words_find": "stub-k12-word.py"})
    w12 = Wall(args.exe, k12_contract, m_stub_path)
    k12a, _ = w12.call("owner_words_find", {carg: CONTOUR_STAND, "text": "X"})
    k12b, _ = w12.call("rules_get", {carg: CONTOUR_STAND, "list": True})
    k12c, _ = w12.call("cards_read", {carg: CONTOUR_STAND, "role": "PROTO"})
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
        ("memory_read view=edit с section на живом (карточка 781: разрешён в обоих вариантах)", "memory_read",
         {carg: CONTOUR_LIVE, "role": "PROTO", "view": "edit", "section": "state"}, False),
        ("memory_read view=edit без section на живом", "memory_read", {carg: CONTOUR_LIVE, "role": "PROTO", "view": "edit"}, True),
        ("memory_find на живом", "memory_find", {carg: CONTOUR_LIVE, "role": "PROTO", "query": "память"}, True),
        ("memory_write на живом", "memory_write", {carg: CONTOUR_LIVE, "action": "compact", "role": "PROTO", "actor": "PROTO"}, True),
        ("cards_read на живом", "cards_read", {carg: CONTOUR_LIVE, "role": "PROTO"}, True),
        ("cards_write на живом", "cards_write", {carg: CONTOUR_LIVE, "action": "add", "role": "PROTO"}, True),
        ("owner_words_add на живом", "owner_words_add", {carg: CONTOUR_LIVE, "said_at": "x", "chat": "x", "text": "x", "heard_by": "x"}, True),
        ("feed_read на живом", "feed_read", {carg: CONTOUR_LIVE, "role": "PROTO"}, True),
        ("feed_write на живом", "feed_write", {carg: CONTOUR_LIVE, "role": "PROTO", "to": "COORD", "body": "x"}, True),
        ("contour_info на живом", "contour_info", {carg: CONTOUR_LIVE}, False),
        ("rules_get на живом", "rules_get", {carg: CONTOUR_LIVE, "list": True}, False),
        ("memory_read без section при ДРУГОМ имени аргумента контура", "memory_read", {"where": CONTOUR_LIVE, "role": "PROTO"}, True),
        ("memory_read без section на стенде", "memory_read", {carg: CONTOUR_STAND, "role": "PROTO"}, False),
        ("cards_read на стенде", "cards_read", {carg: CONTOUR_STAND, "role": "PROTO"}, False),
        ("feed_read на стенде", "feed_read", {carg: CONTOUR_STAND, "role": "PROTO"}, False),
        ("feed_read с выдуманным контуром", "feed_read", {carg: "atlas-typo", "role": "PROTO"}, False),
        ("feed_read без контура", "feed_read", {"role": "PROTO"}, False),
        # те же вызовы в форме argv режима run (без имени вызова)
        ("argv: memory_read без --section на живом", "memory_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO"], True),
        ("argv: memory_read с --section без значения на живом", "memory_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO", "--section"], True),
        ("argv: memory_read с --section identity на живом", "memory_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO", "--section", "identity"], False),
        ("argv: memory_read --view edit с --section на живом", "memory_read",
         ["--" + carg, CONTOUR_LIVE, "--role", "PROTO", "--view", "edit", "--section", "state"], False),
        ("argv: cards_read на живом", "cards_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO"], True),
        ("argv: feed_read на живом", "feed_read", ["--" + carg, CONTOUR_LIVE, "--role", "PROTO"], True),
        ("argv: contour_info на живом", "contour_info", ["--" + carg, CONTOUR_LIVE], False),
        ("argv: cards_read на стенде", "cards_read", ["--" + carg, CONTOUR_STAND, "--role", "PROTO"], False),
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
           "защита живого контура: на живом приёмке разрешены только contour_info, rules_get и memory_read с непустым section (в обоих вариантах); cards_read, feed_read, memory_read без раздела и новые вызовы карточки 781 — отказ с названием вызова; на стенде, без контура и с выдуманным контуром — не трогает",
           "проверено случаев %d (процессы не запускались), не так: %d\n%s"
           % (len(k10_cases), len(k10_bad), "\n".join(k10_rows)))


# ═══════════════════════════════════════ карточка 781: варианты вызова, передача в среду тела, память слоями, карточки и слова владельца

# Двенадцать вызовов договора 2.0.0 — РУКОЙ, не из договора: иначе «лишний или пропавший вызов» нечем увидеть.
EXPECTED_TOOL_NAMES = ["memory_read", "memory_find", "memory_write", "feed_read", "feed_ack", "feed_write",
                       "cards_read", "cards_write", "rules_get", "owner_words_find", "owner_words_add", "contour_info"]
# вызовы с вариантами: аргумент выбора и ключи вариантов — тоже рукой
EXPECTED_VARIANTS = {
    "memory_read": ("view", ["wake", "edit"]),
    "memory_write": ("action", ["save", "compact"]),
    "cards_read": ("view", ["list", "card"]),
    "cards_write": ("action", ["comment", "add"]),
}
STUB_ECHO = "stub-781-echo.py"
OUTCOME_BY_CODE = {0: "passed", 1: "mismatch", 2: "not_started", 3: "cannot_verify", 4: "refused", 5: "partial", 6: "tool_failed"}
DAY_781 = "2026-11-13"

# Нарочные поломки карточки 781. «Свои» случаи названы ЗДЕСЬ, до прогона, и под результат не подгоняются.
#   П1  у варианта compact переменная среды названа не тем именем (MEZO_ROLX вместо MEZO_ROLE) → аргумент actor остаётся при
#       варианте, тело ЗАПУСКАЕТСЯ, но не знает, чья рука: ломает В4 (рука тела) и В6 (сжатие настоящим телом).
#       ⚠️ ИСТОРИЯ: до 2026-11-17 поломка СНИМАЛА env целиком. После правила «requires — только из аргументов своего варианта»
#       такая копия роняла В3, В4 и В6 одним отказом ДО тела («аргумент actor не относится к варианту»), то есть соседним
#       механизмом, а не названным — нашла TAXO чужой рукой (карточка 781, её разбор 17.11 09:50 UTC). Список «своих» стал
#       «В4, В6»: В3 больше не падает, потому что actor по-прежнему относится к варианту. Назван здесь ДО прогона.
#   П2  у вариантов cards_read переставлены ТОЛЬКО подкоманды (sub); аргументы и requires на месте → вариант list зовёт показ
#       одной карточки и наоборот, тело запускается ЧУЖОЕ: ломает В3 (выбор варианта на заглушках), В7 (карточка: перечень
#       и показ) и В9 (читающий вызов view=card не ответил «прошло», замер недействителен).
#       ⚠️ ИСТОРИЯ: до 2026-11-17 переставлялся exec целиком вместе с requires — и случаи падали отказом «аргумент не относится
#       к варианту», а не вызовом чужого тела (та же находка TAXO).
#   П3  у варианта add снят requires             → без критерия отказ даёт тело, а не договор: ломает В7
#       ⚠️ ИСТОРИЯ: до возврата 3 (2026-11-17) признак П3 называл строку без исхода — и засчитывал поломку, где отказал
#       ДОГОВОР, только по чужому аргументу (requires done_when → tags; контроль TAXO, её разбор 17.11 12:56 UTC).
#       Теперь признак несёт исход «tool_failed «тело отказало»: названный механизм — отказ ТЕЛА.
# Четвёртое поле — ПРЯМОЙ ПРИЗНАК: случай и кусок строки, которой этот случай обязан объяснить провал. Он держит МЕХАНИЗМ:
# «упали ровно свои» мало, если они упали соседним отказом. Признаки тоже названы до прогона.
BREAKS_781 = [
    ("П1", "у варианта compact переменная среды названа не тем именем", {"В4", "В6"},
     ("В4", "вариант compact с actor=PROTO при role=COORD: тело видит ('-', '-')")),
    ("П2", "у вариантов cards_read переставлены только подкоманды", {"В3", "В7", "В9"},
     ("В3", "вариант list [serve]: исход passed · тело запускалось: True")),
    ("П3", "у варианта add снят requires", {"В7"},
     ("В7", "НЕ ТАК без done_when: исход tool_failed «тело отказало")),
]


def clean_env(extra=None):
    """Среда для прямого вызова тела ветки: ни одной MEZO_* — так же, как у тела за службой."""
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("MEZO_")}
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def run_py(script, argv, env=None, timeout=900):
    p = subprocess.run([sys.executable, "-X", "utf8", script] + [str(x) for x in argv], capture_output=True,
                       encoding="utf-8", errors="replace", env=env or clean_env(), timeout=timeout)
    return p.returncode, p.stdout or "", p.stderr or ""


def db_all(path, sql, params=()):
    import sqlite3
    conn = sqlite3.connect(path, timeout=60)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def db_one(path, sql, params=()):
    rows = db_all(path, sql, params)
    return rows[0][0] if rows else None


def tool_doc(doc, name):
    return [t for t in doc["tools"] if t["name"] == name][0]


def set_script_all(tool, script):
    """Подменяет тело вызова заглушкой: у вызова с вариантами — у каждого варианта."""
    if "variants" in tool:
        for v in tool["variants"].values():
            v["exec"]["script"] = script
    elif tool.get("exec", {}).get("kind") != "builtin":
        tool["exec"]["script"] = script


def parse_hits(text):
    """{номер записи: слой} из вывода поиска по памяти: строки вида «#44 · … · слой hot»."""
    import re
    return dict((int(i), layer) for i, layer in re.findall(r"^#(\d+) · .*слой (\w+)\s*$", text, re.M))


def build_small_copy(work, manifest):
    """Малая копия установленного контура в рабочем каталоге приёмки: инструменты ветки и копия учебной базы с шагом слоёв.

    Живую и учебную базы не трогает: шаг схемы применяется только к КОПИИ. Не вышло — словарь с ключом why."""
    import sqlite3
    c = os.path.join(work, "e2", "c")
    repo = os.path.dirname(os.path.dirname(SERVICE))
    src_scripts = os.path.join(repo, "scripts")
    src_proto = os.path.join(repo, "vnext", "prototype")
    stands = [x for x in manifest["contours"] if x.get("id") == CONTOUR_STAND]
    lives = [x for x in manifest["contours"] if x.get("id") == CONTOUR_LIVE]
    if not stands:
        return {"why": "в манифесте нет учебного контура «%s»" % CONTOUR_STAND}
    stand_db = stands[0]["storage"]
    norm = lambda p: os.path.normcase(os.path.abspath(p))
    if lives and norm(lives[0]["storage"]) == norm(stand_db):
        return {"why": "источник копии — живая база (storage учебного контура совпал с живым): копировать нельзя"}
    if not os.path.exists(stand_db):
        return {"why": "учебной базы нет: %s" % stand_db}
    for d in (src_scripts, src_proto):
        if not os.path.isdir(d):
            return {"why": "в дереве нет каталога инструментов ветки: %s" % d}
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    scripts = os.path.join(c, ".mezosync", "scripts")
    vnext = os.path.join(c, "vnext-tools")
    shutil.copytree(src_scripts, scripts, dirs_exist_ok=True, ignore=ignore)
    shutil.copytree(src_proto, vnext, dirs_exist_ok=True, ignore=ignore)
    base = os.path.join(c, ".mezosync", "mezosync.db")
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(base + suffix):
            os.remove(base + suffix)
        if os.path.exists(stand_db + suffix):
            shutil.copyfile(stand_db + suffix, base + suffix)
    step = os.path.join(scripts, "migrations", "20261115-phoenix-records-layer.py")
    if not os.path.exists(step):
        return {"why": "шага схемы слоёв нет в дереве: %s" % step}
    code, out, err = run_py(step, ["--db", base])
    if code != 0:
        return {"why": "шаг схемы слоёв на копии не применился (код %d): %s" % (code, (out + err).strip()[-300:])}
    conn = sqlite3.connect(base)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        cols = [r[1] for r in conn.execute("PRAGMA table_info(phoenix_records)")]
    finally:
        conn.close()
    if "layer" not in cols:
        return {"why": "после шага схемы у записей памяти нет поля слоя"}
    work_db = os.path.join(c, "work", "mezosync.db")
    if not os.path.isdir(os.path.dirname(work_db)):
        os.makedirs(os.path.dirname(work_db))
    import copy
    m = copy.deepcopy(manifest)
    for x in m["contours"]:
        if x.get("id") == CONTOUR_STAND:
            x["storage"] = work_db
            x["tools"] = {"runtime": scripts, "vnext": vnext}
    mp = os.path.join(c, "contours-c.json")
    write_json(mp, m)
    code_f, out_f, _ = run_py(os.path.join(scripts, "find-phoenix.py"), ["--db", base, "--role", "PROTO", "память"])
    return {"c": c, "scripts": scripts, "vnext": vnext, "base_db": base, "work_db": work_db, "manifest_path": mp,
            "migration": out.strip().splitlines()[-3:], "find_smoke": code_f, "why": None}


def fresh_db(small):
    """Свежая рабочая копия базы малой копии: каждый случай начинает с неё."""
    for suffix in ("-wal", "-shm"):
        if os.path.exists(small["work_db"] + suffix):
            os.remove(small["work_db"] + suffix)
    shutil.copyfile(small["base_db"], small["work_db"])
    return small["work_db"]


def call_serve(w, tool, carg, args):
    s, t = w.call(tool, dict(args, **{carg: CONTOUR_STAND}))
    return s, t


def call_run(ctx, contract, manifest_path, tool, args, env_extra=None):
    """Однократный вызов мимо службы. Возвращает (исход словом, причина, вывод)."""
    argv = ["--" + ctx["carg"], CONTOUR_STAND]
    for k, v in args.items():
        if v is True:
            argv.append("--" + k.replace("_", "-"))
        else:
            argv += ["--" + k.replace("_", "-"), str(v)]
    code, out, err = run_mode(ctx["exe"], contract, manifest_path, [tool] + argv, env_extra=env_extra)
    reason = ""
    for line in out.splitlines():
        if line.startswith("причина: "):
            reason = line[len("причина: "):]
    return OUTCOME_BY_CODE.get(code, "код %s" % code), reason, out


def stub_setup_781(ctx, contract_path, tag):
    """Договор с заглушками на месте тел и манифест, ведущий на каталог заглушек. Заглушка печатает аргументы и среду."""
    import copy
    stubs = os.path.join(ctx["work"], "stubs-781")
    if not os.path.isdir(stubs):
        os.makedirs(stubs)
    log = os.path.join(ctx["work"], "stub-781-calls.log")
    io.open(os.path.join(stubs, STUB_ECHO), "w", encoding="utf-8", newline="\n").write(
        "import json, os, sys\n"
        "with open(%r, 'a', encoding='utf-8') as f:\n"
        "    f.write(json.dumps(sys.argv[1:], ensure_ascii=False) + '\\n')\n"
        "sys.stdout.write('ARGV ' + json.dumps(sys.argv[1:], ensure_ascii=False) + '\\n')\n"
        "sys.stdout.write('ENV MEZO_ROLE=%%s MEZO_CONTAINER=%%s\\n' %% (os.environ.get('MEZO_ROLE', '-'), os.environ.get('MEZO_CONTAINER', '-')))\n"
        % log)
    doc = copy.deepcopy(read_json(contract_path))
    for name in ("memory_read", "memory_write", "cards_read", "cards_write", "rules_get"):
        set_script_all(tool_doc(doc, name), STUB_ECHO)
    cp = os.path.join(ctx["work"], "contract-781-stub-%s.json" % tag)
    write_json(cp, doc)
    m = copy.deepcopy(ctx["manifest"])
    for x in m["contours"]:
        x["tools"] = {"runtime": stubs, "vnext": stubs}
    mp = os.path.join(ctx["work"], "contours-781-stubs.json")
    write_json(mp, m)
    return cp, mp, log


def log_lines(log):
    return io.open(log, encoding="utf-8").read().splitlines() if os.path.exists(log) else []


def stub_argv(text):
    import re
    m = re.search(r"^ARGV (\[.*\])\s*$", text or "", re.M)
    return json.loads(m.group(1)) if m else None


# ───────────── В1 состав

def case_B1(ctx, contract_path):
    doc = read_json(contract_path)
    names = [t["name"] for t in doc["tools"]]
    tools_out = subprocess.run([ctx["exe"], "tools", "--contract", contract_path, "--contours", ctx["contours"]],
                               capture_output=True, encoding="utf-8", errors="replace", timeout=120).stdout
    printed_fp = None
    for line in tools_out.splitlines():
        if line.startswith("отпечаток перечня"):
            printed_fp = line.split()[-1]
    w = Wall(ctx["exe"], contract_path, ctx["contours"])
    listed = w.list_tools()
    w.close()
    problems = []
    if len(names) != 12 or sorted(names) != sorted(EXPECTED_TOOL_NAMES):
        problems.append("состав вызовов: лишние %s, пропавшие %s (всего %d)"
                        % (sorted(set(names) - set(EXPECTED_TOOL_NAMES)), sorted(set(EXPECTED_TOOL_NAMES) - set(names)), len(names)))
    if sorted(t["name"] for t in listed) != sorted(EXPECTED_TOOL_NAMES):
        problems.append("tools/list называет другой состав: %s" % [t["name"] for t in listed])
    if printed_fp != EXPECTED_TOOLS_FINGERPRINT:
        problems.append("отпечаток перечня %s, записан %s" % (printed_fp, EXPECTED_TOOLS_FINGERPRINT))
    rows = []
    for name, (by, keys) in EXPECTED_VARIANTS.items():
        t = tool_doc(doc, name)
        if t.get("variant_by") != by or sorted(t.get("variants", {})) != sorted(keys):
            problems.append("%s: аргумент выбора %r, варианты %s (ждали %s %s)" % (name, t.get("variant_by"), sorted(t.get("variants", {})), by, keys))
            continue
        for key in keys:
            line = [x for x in tools_out.splitlines() if x.strip().startswith("вариант %s=%s" % (by, key))]
            # строка варианта справки должна идти под своим вызовом: проверяем, что она есть и называет его обязательные аргументы
            head = line[0].split(" — ")[0].split(" · ")[0] if line else ""
            required_part = head.split("обязательны", 1)[1].split(";")[0] if "обязательны" in head else ""
            lacking = [r for r in t["variants"][key].get("requires", []) if r not in required_part]
            if not line:
                problems.append("справка tools не печатает вариант %s=%s вызова %s" % (by, key, name))
            elif lacking:
                problems.append("справка: у варианта %s=%s вызова %s в «обязательны» нет %s" % (by, key, name, lacking))
            else:
                rows.append(line[0].strip())
        sch = [x for x in listed if x["name"] == name]
        if not sch:
            continue
        schema = sch[0]["inputSchema"]
        enum = (schema["properties"].get(by) or {}).get("enum")
        if sorted(enum or []) != sorted(keys):
            problems.append("tools/list: у %s аргумент %s несёт enum %s, ждали %s" % (name, by, enum, keys))
        want_required = [carg_name for carg_name in [ctx["carg"]]] + [a["name"] for a in t["args"] if a.get("required")]
        if sorted(schema.get("required") or []) != sorted(want_required):
            problems.append("tools/list: у %s required %s, ждали %s (обязательное на уровне вызова)" % (name, schema.get("required"), want_required))
        if any(("вариант %s=%s" % (by, k)) not in (sch[0].get("description") or "") for k in keys):
            problems.append("tools/list: описание %s не называет все варианты" % name)
    return (not problems,
            "вызовов в договоре %d, в tools/list %d · отпечаток перечня %s (записан %s)\n"
            "строки вариантов справки tools (по четырём вызовам): %d\n%s%s"
            % (len(names), len(listed), printed_fp, EXPECTED_TOOLS_FINGERPRINT, len(rows), "\n".join("  " + r for r in rows[:8]),
               ("\nПРОБЛЕМЫ:\n" + "\n".join(problems)) if problems else ""))


def one_line(x):
    """Значение в одну строку: перевод строки внутри значения сбил бы разметку строк подробностей."""
    return " ".join(str(x or "").split())


def marked(detail, flags):
    """Строки подробностей: у каждой с флагом — «ок» или «НЕ ТАК» перед текстом. flags[i] None — строка без суждения.
    Число строк обязано сойтись с числом флагов: иначе пометка встала бы не на ту строку."""
    lines = detail.split("\n")
    assert len(lines) == len(flags), (len(lines), len(flags), detail[:200])
    out = []
    for line, f in zip(lines, flags):
        out.append(line if f is None else ("ок " if f else "НЕ ТАК ") + line)
    return "\n".join(out)


# ───────────── В2 разбор договора

def case_B2(ctx):
    import copy
    base = ctx["contract_doc"]

    def edit(fn):
        d = copy.deepcopy(base)
        fn(d)
        return d

    def mem_read_exec(d):
        return d["tools"][[t["name"] for t in d["tools"]].index("memory_read")]

    def drop(d, name, key):
        tool_doc(d, name).pop(key, None)

    copies = [
        ("правило 1: exec и variants вместе", edit(lambda d: tool_doc(d, "memory_read").__setitem__("exec", copy.deepcopy(tool_doc(d, "memory_read")["variants"]["wake"]["exec"]))),
         ["memory_read", "есть и exec, и variant_by/variants"]),
        ("правило 1: ни exec, ни variants", edit(lambda d: (drop(d, "cards_read", "variant_by"), drop(d, "cards_read", "variants"), drop(d, "cards_read", "default_variant"))),
         ["cards_read", "нет ни exec, ни variant_by"]),
        ("правило 2: variant_by называет необъявленный аргумент", edit(lambda d: tool_doc(d, "memory_read").__setitem__("variant_by", "ghost")),
         ["memory_read", "ghost"]),
        ("правило 2: у аргумента выбора нет enum", edit(lambda d: [a.pop("enum", None) for a in tool_doc(d, "memory_read")["args"] if a["name"] == "view"]),
         ["memory_read", "без enum"]),
        ("правило 2: в enum значение без варианта", edit(lambda d: [a["enum"].append("zzz") for a in tool_doc(d, "memory_read")["args"] if a["name"] == "view"]),
         ["memory_read", "zzz", "расходится"]),
        ("правило 2: вариант без значения в enum", edit(lambda d: tool_doc(d, "cards_write")["variants"].__setitem__("extra", copy.deepcopy(tool_doc(d, "cards_write")["variants"]["comment"]))),
         ["cards_write", "extra", "расходится"]),
        ("правило 3: default_variant вне enum", edit(lambda d: tool_doc(d, "memory_read").__setitem__("default_variant", "zzz")),
         ["memory_read", "zzz", "не входит"]),
        ("правило 3: default_variant у пишущего вызова", edit(lambda d: tool_doc(d, "memory_write").__setitem__("default_variant", "save")),
         ["memory_write", "default_variant", "пишущего"]),
        ("правило 3: нет default_variant, а выбор не обязателен", edit(lambda d: drop(d, "memory_read", "default_variant")),
         ["memory_read", "нет default_variant"]),
        ("правило 4: exec.args ссылается на необъявленный аргумент", edit(lambda d: tool_doc(d, "memory_read")["variants"]["wake"]["exec"]["args"].append({"arg": "ghost", "form": "flag", "flag": "--ghost"})),
         ["memory_read", "ghost", "exec.args"]),
        ("правило 4: requires называет необъявленный аргумент", edit(lambda d: tool_doc(d, "memory_read")["variants"]["edit"]["requires"].append("ghost")),
         ["memory_read", "ghost", "requires"]),
        ("правило 4: exec.env передаёт необъявленный аргумент", edit(lambda d: tool_doc(d, "memory_write")["variants"]["compact"]["exec"]["env"].__setitem__("MEZO_ROLE", "ghost")),
         ["memory_write", "ghost", "exec.env"]),
        ("правило 5: аргумент не относится ни к одному варианту", edit(lambda d: tool_doc(d, "memory_read")["args"].append({"name": "orphan", "type": "string", "required": False})),
         ["memory_read", "orphan", "не относится ни к одному"]),
        ("правило 6: required на вызове у аргумента одного варианта", edit(lambda d: [a.__setitem__("required", True) for a in tool_doc(d, "cards_read")["args"] if a["name"] == "card"]),
         ["cards_read", "card", "required=true"]),
        ("правило 7: имя переменной среды по образцу не проходит", edit(lambda d: tool_doc(d, "memory_write")["variants"]["compact"]["exec"].__setitem__("env", {"mezo_role": "actor"})),
         ["memory_write", "mezo_role", "не по образцу"]),
        # возврат 1: requires — только аргументы СВОЕГО варианта; вид полей; имя переменной среды только из MEZO_*
        ("возврат 1 а: requires называет аргумент, который использует только ДРУГОЙ вариант", edit(lambda d: tool_doc(d, "cards_read")["variants"]["list"]["requires"].append("card")),
         ["cards_read", "list", "card", "не использует"]),
        ("возврат 1 б: requires — строка, не массив", edit(lambda d: tool_doc(d, "memory_read")["variants"]["edit"].__setitem__("requires", "section")),
         ["memory_read", "edit", "requires", "не массив"]),
        ("возврат 1 б: requires — объект, не массив", edit(lambda d: tool_doc(d, "memory_read")["variants"]["edit"].__setitem__("requires", {"section": True})),
         ["memory_read", "edit", "requires", "не массив"]),
        ("возврат 1 в: в requires стоит число", edit(lambda d: tool_doc(d, "memory_read")["variants"]["edit"].__setitem__("requires", [5])),
         ["memory_read", "edit", "requires", "Number"]),
        ("возврат 1 г: значение в exec.env — число", edit(lambda d: tool_doc(d, "memory_write")["variants"]["compact"]["exec"].__setitem__("env", {"MEZO_ROLE": 5})),
         ["exec.env", "MEZO_ROLE", "Number"]),
        ("возврат 1 д: имя переменной среды PATH", edit(lambda d: tool_doc(d, "memory_write")["variants"]["compact"]["exec"].__setitem__("env", {"PATH": "actor"})),
         ["memory_write", "PATH", "не по образцу"]),
        ("возврат 1 е: имя переменной среды GORDI_ROLE", edit(lambda d: tool_doc(d, "memory_write")["variants"]["compact"]["exec"].__setitem__("env", {"GORDI_ROLE": "actor"})),
         ["memory_write", "GORDI_ROLE", "не по образцу"]),
        ("возврат 1 ж: в enum аргумента стоит число", edit(lambda d: [a["enum"].append(5) for a in tool_doc(d, "memory_read")["args"] if a["name"] == "view"]),
         ["enum аргумента", "Number"]),
    ]
    rows, bad = [], []
    for i, (label, doc, must) in enumerate(copies):
        p = os.path.join(ctx["work"], "contract-781-b2-%02d.json" % i)
        write_json(p, doc)
        code, err = load_refusal(ctx["exe"], p, ctx["contours"])
        # в потоке ошибок не должно быть трассировки необработанного исключения: кривой договор — отказ с причиной, не падение
        trace = ("Unhandled exception" in err) or ("   at " in err) or ("InvalidOperationException" in err)
        ok = code == 4 and "договор не читается" in err and all(m in err for m in must) and not trace
        rows.append("%s %s: код %s — %s%s" % ("ок" if ok else "НЕ ТАК", label, code, one_line(err)[:170], " · ТРАССИРОВКА В STDERR" if trace else ""))
        if not ok:
            bad.append(label)
    code_ok, _ = load_refusal(ctx["exe"], ctx["contract"], ctx["contours"])
    if code_ok != 0:
        bad.append("встречный: целый договор не загрузился")
    return (not bad, "кривых копий договора %d, загрузилось или отказ без причины: %d · целый договор: код %s\n%s"
            % (len(copies), len(bad), code_ok, "\n".join(rows)))


# ───────────── В3 выбор варианта на заглушках

def case_B3(ctx, contract_path):
    cp, mp, log = stub_setup_781(ctx, contract_path, "b3")
    carg = ctx["carg"]
    # (подпись, вызов, аргументы, ждём исход, подстроки причины, проверка argv, пишущий?)
    cases = [
        ("а memory_read без view → вариант wake", "memory_read", {"role": "PROTO", "section": "identity"}, "passed", [],
         lambda a: a is not None and "--role" in a and "--section" in a and "--read" not in a, False),
        ("б memory_read view=edit с section → есть --read", "memory_read", {"view": "edit", "role": "PROTO", "section": "state"}, "passed", [],
         lambda a: a is not None and "--read" in a, False),
        ("в memory_read view=edit без section → отказ с вариантом и аргументом", "memory_read", {"view": "edit", "role": "PROTO"}, "refused",
         ["view=edit", "section"], None, False),
        ("г cards_read view=card с role → отказ «не относится к варианту»", "cards_read", {"view": "card", "card": 1, "role": "PROTO"}, "refused",
         ["role", "не относится к варианту", "view=card", "view=list"], None, False),
        ("д cards_read без view → вариант list", "cards_read", {"role": "PROTO"}, "passed", [],
         lambda a: a is not None and "list" in a and "show" not in a, False),
        ("е cards_read view=card с card → вариант card", "cards_read", {"view": "card", "card": 1}, "passed", [],
         lambda a: a is not None and "show" in a and "list" not in a, False),
        ("ж cards_write без action → отказ", "cards_write", {"actor": "PROTO", "card": 1, "body": "x"}, "refused",
         ["action"], None, True),
        ("з memory_write action=compact с body → отказ", "memory_write", {"action": "compact", "role": "PROTO", "actor": "PROTO", "body": "x"}, "refused",
         ["body", "action=compact"], None, True),
        ("и memory_write action=compact верный → есть --compact", "memory_write", {"action": "compact", "role": "PROTO", "actor": "PROTO"}, "passed", [],
         lambda a: a is not None and "--compact" in a and "--expect-version" not in a, True),
        ("к memory_write action=save верный → есть --expect-version", "memory_write", {"action": "save", "role": "PROTO", "section": "state", "body": "x", "expect_version": 1}, "passed", [],
         lambda a: a is not None and "--expect-version" in a and "--compact" not in a, True),
    ]
    rows, bad = [], []
    w = Wall(ctx["exe"], cp, mp)
    for label, tool, args, want, must, argv_ok, writes in cases:
        for mode in ("serve", "run"):
            if mode == "run" and writes:
                # режим run всегда только-чтение: пишущий вызов отвергнут ДО разбора вариантов — по своей причине; тело не запускается
                before = len(log_lines(log))
                outcome, reason, out = call_run(ctx, cp, mp, tool, args)
                ok = outcome == "refused" and "только-чтение" in out and len(log_lines(log)) == before
                rows.append("%s %s [run]: %s — отказ режима только-чтение, тело не запускалось: %s" % ("ок" if ok else "НЕ ТАК", label, outcome, len(log_lines(log)) == before))
                if not ok:
                    bad.append(label + " [run]")
                continue
            before = len(log_lines(log))
            if mode == "serve":
                s, t = call_serve(w, tool, carg, args)
                outcome, reason, text = s.get("outcome"), s.get("error") or "", t
            else:
                outcome, reason, text = call_run(ctx, cp, mp, tool, args)
            ran = len(log_lines(log)) > before
            a = stub_argv(text)
            ok = outcome == want and all(m in reason for m in must) and (ran == (want == "passed"))
            if argv_ok is not None:
                ok = ok and argv_ok(a)
            rows.append("%s %s [%s]: исход %s · тело запускалось: %s · %s"
                        % ("ок" if ok else "НЕ ТАК", label, mode, outcome, ran, ("argv %s" % a) if want == "passed" else reason[:150]))
            if not ok:
                bad.append("%s [%s]" % (label, mode))
    w.close()
    return (not bad, "проверено половин %d (служба и режим run), не так: %d\n%s" % (len(rows), len(bad), "\n".join(rows)))


# ───────────── В4 рука тела

def case_B4(ctx, contract_path):
    import re
    cp, mp, log = stub_setup_781(ctx, contract_path, "b4")
    carg = ctx["carg"]
    evil = {"MEZO_ROLE": "EVIL", "MEZO_CONTAINER": "X"}
    w = Wall(ctx["exe"], cp, mp, env_extra=evil)

    def seen(text):
        m = re.search(r"ENV MEZO_ROLE=(\S*) MEZO_CONTAINER=(\S*)", text or "")
        return (m.group(1), m.group(2)) if m else None

    s_a, t_a = call_serve(w, "rules_get", carg, {"list": True})
    s_b, t_b = call_serve(w, "memory_write", carg, {"action": "save", "role": "PROTO", "section": "state", "body": "x", "expect_version": 1})
    # role и actor НАМЕРЕННО разные: при равных подмена «в MEZO_ROLE уходит role, а не actor» прошла бы молча
    # (заметка TAXO, её разбор 17.11 12:56 UTC). Тело здесь — заглушка, чужую память она не трогает.
    s_c, t_c = call_serve(w, "memory_write", carg, {"action": "compact", "role": "COORD", "actor": "PROTO"})
    before = len(log_lines(log))
    s_d, t_d = call_serve(w, "memory_write", carg, {"action": "compact", "role": "PROTO"})
    ran_d = len(log_lines(log)) > before
    w.close()
    o_a, _, out_a = call_run(ctx, cp, mp, "rules_get", {"list": True}, env_extra=evil)
    ok_a = seen(t_a) == ("-", "-") and s_a.get("outcome") == "passed"
    ok_a_run = seen(out_a) == ("-", "-") and o_a == "passed"
    ok_b = seen(t_b) == ("-", "-") and s_b.get("outcome") == "passed"
    ok_c = seen(t_c) == ("PROTO", "-") and s_c.get("outcome") == "passed"
    ok_d = s_d.get("outcome") == "refused" and "actor" in (s_d.get("error") or "") and not ran_d
    return (ok_a and ok_a_run and ok_b and ok_c and ok_d, marked(
            "служба поднята с MEZO_ROLE=EVIL и MEZO_CONTAINER=X в СВОЕЙ среде\n"
            "вызов без env в договоре (rules_get): тело видит (MEZO_ROLE, MEZO_CONTAINER) = %s · режим run: %s (ждали обе «-»)\n"
            "вариант save без env (memory_write): тело видит %s (ждали обе «-»)\n"
            "вариант compact с actor=PROTO при role=COORD: тело видит %s (ждали PROTO и «-»)\n"
            "compact без actor: исход %s, причина «%s», тело запускалось: %s (ждали отказ до тела)"
            % (seen(t_a), seen(out_a), seen(t_b), seen(t_c), s_d.get("outcome"), one_line(s_d.get("error"))[:110], ran_d),
            [None, ok_a and ok_a_run, ok_b, ok_c, ok_d]))


# ───────────── В5 поиск по трём слоям, критерий ⑥

def case_B5(ctx, contract_path):
    import re
    small = ctx["small"]
    if small.get("why"):
        return False, "ПРОВЕРЯТЬ НЕЧЕМ: %s" % small["why"]
    db = fresh_db(small)
    find = os.path.join(small["scripts"], "find-phoenix.py")
    mover = os.path.join(small["vnext"], "memory-records.py")
    rows = db_all(db, "SELECT role, id, body FROM phoenix_records WHERE alive='active' ORDER BY role, id")
    by_role = {}
    for role, rid, body in rows:
        for tok in set(re.findall(r"[а-яё]{7,}", (body or "").casefold())):
            by_role.setdefault(role, {}).setdefault(tok, set()).add(rid)
    cands = [(r, t, ids) for r in sorted(by_role) for t, ids in sorted(by_role[r].items()) if 3 <= len(ids) <= 10]
    picked = None
    for role, word, ids in cands[:60]:
        code, out, _ = run_py(find, ["--db", db, "--role", role, "--limit", 50, word])
        hits = parse_hits(out)
        if code == 0 and 3 <= len(hits) <= 20 and set(hits.values()) == {"hot"}:
            picked = (role, word, hits)
            break
    if not picked:
        return False, "ПРОВЕРЯТЬ НЕЧЕМ: в копии нет слова, которое встречается в трёх и более записях одной роли (проверено кандидатов: %d)" % min(len(cands), 60)
    role, word, hits = picked
    ids = sorted(hits)
    warm_id, perm_id = ids[0], ids[1]
    prep = []
    for rid, layer in ((warm_id, "warm"), (perm_id, "permanent")):
        code, out, err = run_py(mover, ["--db", db, "--role", role, "--move", rid, "--layer", layer], env=clean_env({"MEZO_ROLE": role}))
        prep.append("перенос #%d в %s: код %d" % (rid, layer, code))
        if code != 0:
            return False, "ПРОВЕРЯТЬ НЕЧЕМ: подготовка не удалась — %s: %s" % (prep[-1], (out + err).strip()[-200:])
    # номер карточки из записей копии
    num_pick = None
    for r, rid, body in rows:
        for m in re.findall(r"#(\d{3,4})\b", body or ""):
            q = "#" + m
            code, out, _ = run_py(find, ["--db", db, "--role", r, "--limit", 50, q])
            hits_n = parse_hits(out)
            if code == 0 and hits_n:
                num_pick = (r, q, hits_n)
                break
        if num_pick:
            break
    carg = ctx["carg"]
    w = Wall(ctx["exe"], contract_path, small["manifest_path"])
    s1, t1 = call_serve(w, "memory_find", carg, {"role": role, "query": word, "limit": 50})
    s2, t2 = call_serve(w, "memory_find", carg, {"role": role, "query": word, "limit": 50, "layer": "warm"})
    s3, t3 = call_serve(w, "memory_find", carg, {"role": role, "query": word.upper(), "limit": 50})
    s4, t4 = call_serve(w, "memory_find", carg, {"role": role, "query": word.lower(), "limit": 50})
    sn = tn = None
    if num_pick:
        sn, tn = call_serve(w, "memory_find", carg, {"role": num_pick[0], "query": num_pick[1], "limit": 50})
    w.close()
    r1 = call_run(ctx, contract_path, small["manifest_path"], "memory_find", {"role": role, "query": word, "limit": 50})
    r2 = call_run(ctx, contract_path, small["manifest_path"], "memory_find", {"role": role, "query": word, "limit": 50, "layer": "warm"})
    r3 = call_run(ctx, contract_path, small["manifest_path"], "memory_find", {"role": role, "query": word.upper(), "limit": 50})
    r4 = call_run(ctx, contract_path, small["manifest_path"], "memory_find", {"role": role, "query": word.lower(), "limit": 50})
    h1, h2, h3, h4 = parse_hits(t1), parse_hits(t2), parse_hits(t3), parse_hits(t4)
    rh1, rh2, rh3, rh4 = parse_hits(r1[2]), parse_hits(r2[2]), parse_hits(r3[2]), parse_hits(r4[2])
    ok_layers = (s1.get("outcome") == "passed" and h1.get(warm_id) == "warm" and h1.get(perm_id) == "permanent"
                 and set(h1.values()) == {"hot", "warm", "permanent"} and set(h1) == set(hits))
    ok_warm = s2.get("outcome") == "passed" and set(h2) == {warm_id} and set(h2.values()) == {"warm"}
    ok_case = s3.get("outcome") == "passed" and s4.get("outcome") == "passed" and set(h3) == set(h4) == set(hits)
    ok_run = (r1[0] == "passed" and set(rh1) == set(hits) and set(rh1.values()) == {"hot", "warm", "permanent"}
              and r2[0] == "passed" and set(rh2) == {warm_id}
              and r3[0] == "passed" and r4[0] == "passed" and set(rh3) == set(rh4) == set(hits))
    ok_num = bool(num_pick) and sn is not None and sn.get("outcome") == "passed" and set(parse_hits(tn)) == set(num_pick[2]) and bool(parse_hits(tn))
    return (ok_layers and ok_warm and ok_case and ok_run and ok_num, marked(
            "роль %s, слово «%s»; записи до переноса %s; перенесены: #%d → warm, #%d → permanent (%s)\n"
            "служба, без layer: исход %s · записи %s · слои %s\n"
            "служба, layer=warm: исход %s · записи %s (ждали только #%d)\n"
            "служба, запрос ЗАГЛАВНЫМИ: %s · строчными: %s · равны прежнему множеству: %s\n"
            "режим run: без layer %s %s · warm %s %s · ЗАГЛАВНЫМИ/строчными равны: %s\n"
            "номер карточки: %s → служба: исход %s · записи %s (прямой вызов тела дал %s)"
            % (role, word, ids, warm_id, perm_id, "; ".join(prep),
               s1.get("outcome"), sorted(h1), sorted(set(h1.values())),
               s2.get("outcome"), sorted(h2), warm_id,
               sorted(h3), sorted(h4), set(h3) == set(h4) == set(hits),
               r1[0], sorted(rh1), r2[0], sorted(rh2), set(rh3) == set(rh4) == set(hits),
               ("%s у роли %s" % (num_pick[1], num_pick[0])) if num_pick else "ПРОВЕРЯТЬ НЕЧЕМ: номера карточки в записях копии нет",
               sn.get("outcome") if sn else None, sorted(parse_hits(tn)) if tn else None, sorted(num_pick[2]) if num_pick else None),
            [None, ok_layers, ok_warm, ok_case, ok_run, ok_num]))


# ───────────── В6 сжатие, критерий ④

def case_B6(ctx, contract_path):
    import re
    small = ctx["small"]
    if small.get("why"):
        return False, "ПРОВЕРЯТЬ НЕЧЕМ: %s" % small["why"]
    db = fresh_db(small)
    mover = os.path.join(small["vnext"], "memory-records.py")
    cands = db_all(db, "SELECT role, section, SUM(body_chars) AS c FROM phoenix_records WHERE layer='hot' "
                       "GROUP BY role, section ORDER BY c DESC LIMIT 25")
    picked = None
    for role, section, chars in cands:
        code, out, _ = run_py(mover, ["--db", db, "--compact", "--role", role, "--section", section, "--dry-run"], env=clean_env({"MEZO_ROLE": role}))
        m = re.search(r"унесено (\d+) записей", out)
        if code == 0 and m and int(m.group(1)) >= 1:
            picked = (role, section, int(chars))
            break
    if not picked:
        return False, "ПРОВЕРЯТЬ НЕЧЕМ: в копии нет роли и раздела, где слой hot длиннее порога (проверено кандидатов: %d)" % len(cands)
    role, section, chars = picked
    other = "COORD" if role != "COORD" else "PROTO"
    carg = ctx["carg"]
    tabs = ["phoenix_records"]

    def digest():
        return table_digests(db, tabs)["phoenix_records"]

    d0 = digest()
    w = Wall(ctx["exe"], contract_path, small["manifest_path"])
    s_dry, t_dry = call_serve(w, "memory_write", carg, {"action": "compact", "role": role, "section": section, "actor": role, "dry_run": True})
    d1 = digest()
    s_bad, t_bad = call_serve(w, "memory_write", carg, {"action": "compact", "role": role, "section": section, "actor": other})
    d2 = digest()
    s_th, _ = call_serve(w, "memory_write", carg, {"action": "compact", "role": role, "section": section, "actor": role, "threshold": 100})
    s_li, _ = call_serve(w, "memory_write", carg, {"action": "compact", "role": role, "section": section, "actor": role, "limit": 1})
    d3 = digest()
    s_real, t_real = call_serve(w, "memory_write", carg, {"action": "compact", "role": role, "section": section, "actor": role})
    w.close()
    d4 = digest()
    ids_dry = [int(x) for x in re.findall(r"^\s*#(\d+) · .*hot → warm", t_dry, re.M)]
    ids_real = [int(x) for x in re.findall(r"^\s*#(\d+) · .*hot → warm", t_real, re.M)]
    m_chars = re.search(r"слой hot было (\d+) знаков в (\d+) записях → стало (\d+) в (\d+)", t_real)
    layers = dict(db_all(db, "SELECT id, layer FROM phoenix_records WHERE id IN (%s)" % ",".join(str(i) for i in ids_real or [0])))
    hot_after = db_one(db, "SELECT COALESCE(SUM(body_chars),0) FROM phoenix_records WHERE role=? AND section=? AND layer='hot'", (role, section))
    ok_dry = s_dry.get("outcome") == "passed" and bool(ids_dry) and "hot → warm" in t_dry and d1 == d0
    ok_bad = s_bad.get("outcome") == "tool_failed" and "правит память роли" in (s_bad.get("error") or "") and d2 == d1
    ok_th = (s_th.get("outcome") == "refused" and "threshold" in (s_th.get("error") or "")
             and s_li.get("outcome") == "refused" and "limit" in (s_li.get("error") or "") and d3 == d2)
    ok_real = (s_real.get("outcome") == "passed" and ids_real == ids_dry and bool(ids_real) and m_chars is not None
               and int(m_chars.group(3)) < int(m_chars.group(1)) and int(m_chars.group(3)) == int(hot_after)
               and all(layers.get(i) == "warm" for i in ids_real) and d4 != d3)
    return (ok_dry and ok_bad and ok_th and ok_real, marked(
            "роль %s, раздел %s: слой hot %d знаков (порог читает тело, в вызове его нет)\n"
            "холостой прогон: исход %s · записи %s · «hot → warm» в тексте: %s · таблица записей не изменилась: %s\n"
            "actor=%s при role=%s: исход %s, причина «%s» · таблица не изменилась: %s\n"
            "аргумент threshold: исход %s «%s» · аргумент limit: исход %s «%s» · таблица не изменилась: %s\n"
            "настоящий вызов: исход %s · унесено записей %s (равны холостому: %s) · знаков до %s после %s (в базе hot теперь %s) · "
            "в копии все они в слое warm: %s · таблица изменилась: %s"
            % (role, section, chars,
               s_dry.get("outcome"), ids_dry, "hot → warm" in t_dry, d1 == d0,
               other, role, s_bad.get("outcome"), one_line(s_bad.get("error"))[:100], d2 == d1,
               s_th.get("outcome"), one_line(s_th.get("error"))[:80], s_li.get("outcome"), one_line(s_li.get("error"))[:80], d3 == d2,
               s_real.get("outcome"), ids_real, ids_real == ids_dry,
               m_chars.group(1) if m_chars else None, m_chars.group(3) if m_chars else None, hot_after,
               all(layers.get(i) == "warm" for i in ids_real), d4 != d3),
            [None, ok_dry, ok_bad, ok_th, ok_real]))


# ───────────── В7 завести карточку

def case_B7(ctx, contract_path):
    import uuid
    small = ctx["small"]
    if small.get("why"):
        return False, "ПРОВЕРЯТЬ НЕЧЕМ: %s" % small["why"]
    db = fresh_db(small)
    carg = ctx["carg"]
    title = "Проба приёмки 781 " + uuid.uuid4().hex[:8]
    body = "Тело карточки пробы приёмки.\nВторая строка тела."
    done = "Критерий пробы: строка в таблице есть."
    tags = ["проба781", "приёмка781"]
    n0 = db_one(db, "SELECT COUNT(*) FROM backlog")
    w = Wall(ctx["exe"], contract_path, small["manifest_path"])
    s_add, t_add = call_serve(w, "cards_write", carg, {"action": "add", "role": "PROTO", "actor": "PROTO", "title": title, "body": body,
                                                         "done_when": done, "tags": tags, "priority": "low"})
    n1 = db_one(db, "SELECT COUNT(*) FROM backlog")
    row = db_all(db, "SELECT id, title, body_md, done_when, tags, priority FROM backlog WHERE title=?", (title,))
    new_id = row[0][0] if row else None
    s_no, _ = call_serve(w, "cards_write", carg, {"action": "add", "role": "PROTO", "actor": "PROTO", "title": title + " без критерия", "body": body})
    n2 = db_one(db, "SELECT COUNT(*) FROM backlog")
    comment = "Комментарий пробы приёмки 781."
    s_cm, _ = call_serve(w, "cards_write", carg, {"action": "comment", "card": new_id or 0, "actor": "PROTO", "body": comment})
    ev = db_all(db, "SELECT event_type, body_md FROM backlog_events WHERE backlog_id=? AND event_type='comment'", (new_id,)) if new_id else []
    s_show, t_show = call_serve(w, "cards_read", carg, {"view": "card", "card": new_id or 0})
    s_list, t_list = call_serve(w, "cards_read", carg, {"view": "list", "role": "PROTO"})
    w.close()
    saved_tags = json.loads(row[0][4]) if row and row[0][4] else []
    ok_add = (s_add.get("outcome") == "passed" and n1 == n0 + 1 and len(row) == 1
              and row[0][2].strip() == body and row[0][3].strip() == done and sorted(saved_tags) == sorted(tags) and row[0][5] == "low")
    ok_no = s_no.get("outcome") == "refused" and "done_when" in (s_no.get("error") or "") and n2 == n1
    ok_cm = s_cm.get("outcome") == "passed" and len(ev) == 1 and ev[0][1].strip() == comment
    ok_read = (s_show.get("outcome") == "passed" and title in t_show
               and s_list.get("outcome") in ("passed", "partial") and ("#%s " % new_id) in t_list and title[:18] in t_list)
    return (ok_add and ok_no and ok_cm and ok_read, marked(
            "заведена карточка #%s: исход %s · строк backlog было %s стало %s · заголовок, тело, критерий, метки %s, срочность %s совпали: %s (ждали passed, +1 строка, поля совпали)\n"
            "без done_when: исход %s «%s» (ждали отказ договора, не «тело отказало») · строк backlog %s (было %s)\n"
            "комментарий: исход %s · событий comment у карточки %d, текст совпал: %s (ждали passed, одно событие, текст совпал)\n"
            "cards_read view=card: исход %s · заголовок в ответе: %s · view=list role=PROTO: исход %s · карточка перечислена: %s (ждали passed, True, passed, True)"
            % (new_id, s_add.get("outcome"), n0, n1, saved_tags, row[0][5] if row else None, ok_add,
               s_no.get("outcome"), one_line(s_no.get("error"))[:120], n2, n1,
               s_cm.get("outcome"), len(ev), bool(ev) and ev[0][1].strip() == comment,
               s_show.get("outcome"), title in t_show, s_list.get("outcome"), ("#%s " % new_id) in t_list),
            [ok_add, ok_no, ok_cm, ok_read]))


# ───────────── В8 записать слово владельца: настоящий искатель, подставной домашний каталог

def case_B8(ctx, contract_path):
    small = ctx["small"]
    if small.get("why"):
        return False, "ПРОВЕРЯТЬ НЕЧЕМ: %s" % small["why"]
    db = fresh_db(small)
    carg = ctx["carg"]
    home = os.path.join(small["c"], "home8")
    project = "C--guts--atlas"
    chats = os.path.join(home, ".claude", "projects", project)
    if not os.path.isdir(chats):
        os.makedirs(chats)
    tid = "5a5a5a5a-1111-2222-3333-444444444444"
    text_yes = "проба записи слова через службу сосна восемьсот"
    text_no = "этого текста нет ни в одной записи пихта восемьсот"
    lines = []
    records = [None, None, ("12:10:00", text_yes)]
    for i, item in enumerate(records):
        if item is None:
            lines.append(json.dumps({"type": "assistant", "timestamp": "%sT11:00:%02d.000Z" % (DAY_781, i), "message": {"content": "строка ответа"}}, ensure_ascii=False))
        else:
            lines.append(json.dumps({"type": "user", "timestamp": "%sT%s.123Z" % (DAY_781, item[0]), "message": {"content": item[1]},
                                     "origin": {"kind": "human"}}, ensure_ascii=False))
    chat_file = os.path.join(chats, tid + ".jsonl")
    io.open(chat_file, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    real_line = 3
    env_home = {"USERPROFILE": home, "HOME": home}
    n0 = db_one(db, "SELECT COUNT(*) FROM owner_words")
    w = Wall(ctx["exe"], contract_path, small["manifest_path"], env_extra=env_home)
    s_ok, t_ok = call_serve(w, "owner_words_add", carg, {"said_at": "%s 12:10:00 UTC" % DAY_781, "chat": tid[:8], "text": text_yes,
                                                          "heard_by": "ОПЫТ", "note": "проба приёмки 781"})
    n1 = db_one(db, "SELECT COUNT(*) FROM owner_words")
    row = db_all(db, "SELECT said_at, chat, text_verbatim, source_file, source_line FROM owner_words WHERE text_verbatim=?", (text_yes,))
    s_no, t_no = call_serve(w, "owner_words_add", carg, {"said_at": "%s 12:10:00 UTC" % DAY_781, "chat": tid[:8], "text": text_no, "heard_by": "ОПЫТ"})
    n2 = db_one(db, "SELECT COUNT(*) FROM owner_words")
    s_fd, t_fd = call_serve(w, "owner_words_find", carg, {"text": "записи слова через службу"})
    w.close()
    # realpath, а не abspath: каталог пользователя бывает назван и длинным именем, и короткой формой 8.3
    norm = lambda p: os.path.normcase(os.path.realpath(p or ""))
    inside = bool(row) and norm(row[0][3]).startswith(norm(home) + os.sep)
    ok_add = (s_ok.get("outcome") == "passed" and n1 == n0 + 1 and len(row) == 1 and inside
              and row[0][4] == real_line and norm(row[0][3]) == norm(chat_file) and DAY_781 in (row[0][0] or "") and "12:10:00" in (row[0][0] or ""))
    ok_no = s_no.get("outcome") == "tool_failed" and n2 == n1 and "ОТКАЗ" in (s_no.get("error") or "")
    ok_fd = s_fd.get("outcome") == "passed" and text_yes in t_fd
    return (ok_add and ok_no and ok_fd, marked(
            "служба поднята с USERPROFILE и HOME на подставной каталог %s (настоящий искатель из малой копии)\n"
            "запись: исход %s · строк owner_words было %s стало %s · в строке файл %s внутри подставного каталога: %s, номер строки %s (на самом деле %d), час %s (ждали passed, +1 строка, файл внутри подставного каталога)\n"
            "текст, которого в записях нет: исход %s «%s» · строк %s (было %s) (ждали tool_failed с ОТКАЗ, строк не прибавилось)\n"
            "owner_words_find: исход %s · найденное слово в ответе: %s (ждали passed, True)"
            % (home, s_ok.get("outcome"), n0, n1, row[0][3] if row else None, inside, row[0][4] if row else None, real_line,
               row[0][0] if row else None, s_no.get("outcome"), one_line(s_no.get("error"))[:110], n2, n1, s_fd.get("outcome"), text_yes in t_fd),
            [None, ok_add, ok_no, ok_fd]))


# ───────────── В9 читающие вызовы пишут только объявленное

def case_B9(ctx, contract_path):
    small = ctx["small"]
    if small.get("why"):
        return False, "ПРОВЕРЯТЬ НЕЧЕМ: %s" % small["why"]
    carg = ctx["carg"]
    doc = read_json(contract_path)
    probes = [
        ("memory_find", {"query": "память"}, ("PROTO", "COORD", "CORE", "STUD", "ING")),
        ("memory_read", {"view": "edit", "section": "state"}, ("PROTO",)),
        ("cards_read", {"view": "card", "card": 1}, (None,)),
    ]
    rows, problems = [], []
    for name, extra, roles in probes:
        declared = tool_doc(doc, name).get("service_writes")
        if declared is None:
            problems.append("%s: у читающего вызова в договоре нет service_writes" % name)
            declared = []
        changed, used = set(), ""
        for role in roles:
            db = fresh_db(small)
            before = table_digests(db)
            args = dict(extra)
            if role:
                args["role"] = role
                used = role
            w = Wall(ctx["exe"], contract_path, small["manifest_path"])
            s, _ = call_serve(w, name, carg, args)
            w.close()
            after = table_digests(db)
            changed = set(k for k in before if before[k] != after.get(k))
            if s.get("outcome") not in ("passed", "partial"):
                problems.append("%s: пробный вызов дал исход %s — замер недействителен" % (name, s.get("outcome")))
                break
            if name != "memory_find" or changed:
                break
        if name == "memory_find" and not changed:
            problems.append("ПРОВЕРЯТЬ НЕЧЕМ: memory_find ни у одной роли ничего не изменил — значение service_writes по замеру не поставить")
        extra_tables = sorted(changed - set(declared))
        if extra_tables:
            problems.append("%s: изменил таблицы, которых нет в service_writes: %s" % (name, ", ".join(extra_tables)))
        rows.append("%-14s%s изменил: %-22s объявлено: %s" % (name, (" (роль %s)" % used) if used else "", ", ".join(sorted(changed)) or "ничего", ", ".join(declared) or "—"))
    return (not problems, "сводка по ВСЕМ таблицам копии до и после вызова\n%s%s"
            % ("\n".join(rows), ("\nПРОБЛЕМЫ:\n" + "\n".join(problems)) if problems else ""))


# ───────────── нарочные поломки

def apply_break(doc, key):
    import copy
    d = copy.deepcopy(doc)
    if key == "П1":
        v = tool_doc(d, "memory_write")["variants"]["compact"]
        # имя переменной проходит образец ^MEZO_…, аргумент actor остаётся использованным: копия загружается, тело запускается,
        # но получает не ту переменную и не знает, чья рука
        v["exec"]["env"] = {"MEZO_ROLX": "actor"}
    elif key == "П2":
        v = tool_doc(d, "cards_read")["variants"]
        # переставляем только подкоманды: аргументы и requires остаются своими, поэтому отказ «аргумент не относится к варианту»
        # не срабатывает и запускается чужое тело
        v["list"]["exec"]["sub"], v["card"]["exec"]["sub"] = v["card"]["exec"]["sub"], v["list"]["exec"]["sub"]
    elif key == "П3":
        tool_doc(d, "cards_write")["variants"]["add"].pop("requires", None)
    return d


def why_line(detail):
    """Одна строка из подробностей случая: почему он не прошёл. Сперва строка с «НЕ ТАК», затем первая после «ПРОБЛЕМЫ:», иначе последняя."""
    lines = [x.strip() for x in detail.strip().splitlines() if x.strip()]
    for x in lines:
        if x.startswith("НЕ ТАК"):
            return x[:190]
    if "ПРОБЛЕМЫ:" in lines and lines.index("ПРОБЛЕМЫ:") + 1 < len(lines):
        return lines[lines.index("ПРОБЛЕМЫ:") + 1][:190]
    return (lines[-1] if lines else "")[:190]


def cases_781(args, work, manifest, contract_doc, carg, v4):
    """Раздел карточки 781. Случаи В1–В9 идут на настоящем договоре, затем три нарочные поломки: каждая — копией договора."""
    ctx = {"exe": args.exe, "contract": args.contract, "contours": args.contours, "work": work, "manifest": manifest,
           "carg": carg, "contract_doc": contract_doc}
    small = build_small_copy(work, manifest)
    ctx["small"] = small
    runners = [("В1", lambda p: case_B1(ctx, p), "состав: двенадцать вызовов, отпечаток, варианты в справке и в схеме MCP"),
               ("В3", lambda p: case_B3(ctx, p), "выбор варианта на заглушках: умолчание, отказ чужого аргумента и не переданного обязательного, служба и run"),
               ("В4", lambda p: case_B4(ctx, p), "рука тела: среда службы к телу не протекает, объявленный env доходит"),
               ("В5", lambda p: case_B5(ctx, p), "поиск по памяти: три слоя, слой, регистр, номер карточки (малая копия)"),
               ("В6", lambda p: case_B6(ctx, p), "сжатие слоя: холостой прогон, чужая рука, порога в аргументах нет, настоящий (малая копия)"),
               ("В7", lambda p: case_B7(ctx, p), "завести карточку: строка в базе, отказ без критерия от договора, комментарий, показ (малая копия)"),
               ("В8", lambda p: case_B8(ctx, p), "записать слово владельца: настоящий искатель, подставной домашний каталог (малая копия)"),
               ("В9", lambda p: case_B9(ctx, p), "читающие вызовы пишут только объявленное (малая копия)")]
    results = {}
    for key, fn, title in runners:
        ok, detail = fn(args.contract)
        results[key] = ok
        if key == "В1":
            ok2, d2 = case_B2(ctx)
            results["В2"] = ok2
            v4.add("781-В1", ok, title, detail)
            v4.add("781-В2", ok2, "разбор договора отвергает кривые варианты: по копии на правила 1–7 и на «default_variant у пишущего вызова»", d2)
        else:
            v4.add("781-" + key, ok, title, detail)

    # три нарочные поломки: копия договора, те же случаи В1, В3–В9, судим «ровно свои»
    for number, (key, what, own, sign) in enumerate(BREAKS_781, 1):
        broken = apply_break(contract_doc, key)
        p = os.path.join(work, "contract-781-break-p%d.json" % number)
        write_json(p, broken)
        failed = set()
        notes = []
        whys = {}
        for ckey, fn, _title in runners:
            try:
                ok, detail = fn(p)
            except Exception as e:      # поломка вправе уронить случай исключением — это тоже «не прошёл»
                ok, detail = False, "исключение: %s" % e
            if not ok:
                failed.add(ckey)
                whys[ckey] = why_line(detail)
                notes.append("%s: %s" % (ckey, whys[ckey]))
        exact = failed == own
        # прямой признак: названный случай обязан объяснить провал названной строкой — иначе поломка бьёт в соседний механизм
        sign_case, sign_text = sign
        direct = sign_text in whys.get(sign_case, "")
        v4.add("781-" + key, exact and direct, "нарочная поломка: %s — не проходят РОВНО свои случаи, и названным механизмом" % what,
               "свои случаи (названы в коде до прогона): %s\nне прошли на поломанной копии: %s\n"
               "прямой признак (назван в коде до прогона): случай %s объясняет провал строкой с «%s» — %s\n%s"
               % (", ".join(sorted(own)), ", ".join(sorted(failed)) or "ни один",
                  sign_case, sign_text, "найден" if direct else "НЕ НАЙДЕН", "\n".join(notes)))
    return results


# ═══════════════════════════════════════ карточка 814, этап Э3, предмет П1: справка службы из того же файла договора
#
# Восемь случаев (С1–С8) и четыре нарочные поломки (Л1–Л4). Проверяющие функции С1–С3 и С6–С8 ЧИСТЫЕ: на входе текст справки,
# разобранный договор, код выхода — на выходе (прошло, подробности). Поэтому поломки Л1–Л3 делаются над текстом, без пересборки
# службы, а Л4 — подачей справки от ЦЕЛОГО договора в случай по копии договора.
# Живой контур этому разделу не нужен вовсе: справка читает один файл договора, тела инструментов не запускаются
# (кроме заглушек и только на контуре-копии базы).

HELP_LIMIT_S = 20          # предел времени на один процесс справки: служба, ждущая ввода вместо справки, не должна зависнуть
# Режимы названы РУКОЙ: перечня режимов в договоре нет, он живёт в одном месте кода службы (там же берёт его отказ «режима нет»)
HELP_MODES = ["serve", "run", "tools", "help"]
HELP_UNKNOWN_TOOL = "нет-такого-вызова"
HELP_UNKNOWN_MODE = "нет-такого-режима"
HELP_NEW_TOOL = "stand_probe_tool"          # тринадцатый вызов копии договора (случай С6)
HELP_NEW_TITLE = "Нарочный тринадцатый вызов приёмки"
HELP_RENAME = ("owner_words_find", "text", "fragment")   # (вызов, старое имя аргумента, новое имя) в копии договора (С6)
HELP_RUN_STAND_CODES = {0: "passed", 1: "mismatch", 6: "tool_failed"}   # что даёт режим run на заглушках (С8)


def help_flag(name):
    """Имя аргумента как флаг командной строки: next_part → --next-part."""
    return "--" + name.replace("_", "-")


def squash(text):
    """Пробельные последовательности в один пробел: описание в справке вправе перенестись."""
    return " ".join((text or "").split())


def help_section(text, header):
    """Строки раздела справки: после строки, начинающейся с header, и до первой пустой строки. Нет раздела — None."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(header):
            out = []
            for x in lines[i + 1:]:
                if not x.strip():
                    break
                out.append(x)
            return out
    return None


def tools_contract_lines(tools_text):
    """Из вывода режима tools: строки версии и двух отпечатков — их справка обязана повторить буква в букву."""
    got = {}
    for prefix in ("версия", "отпечаток договора", "отпечаток перечня"):
        for line in tools_text.splitlines():
            if line.startswith(prefix):
                got[prefix] = line.strip()
                break
    return got


def tools_variant_lines(tools_text, name):
    """Из вывода режима tools: строки вариантов одного вызова (отступ глубокий, начинаются со слова «вариант»)."""
    import re
    out = []
    inside = False
    for line in tools_text.splitlines():
        m = re.match(r"^  (чтение|запись)\s+(\S+)", line)
        if m:
            inside = (m.group(2) == name)
            continue
        if inside and line.strip().startswith("вариант "):
            out.append(line.strip())
    return out


def arg_block(lines, flag):
    """Блок аргумента в справке по вызову: его строка (отступ 2, начинается с флага) и строки описания (отступ 6)."""
    for i, line in enumerate(lines):
        if line.startswith("  ") and not line.startswith("   ") and line.strip().startswith(flag + " "):
            block = [line]
            for x in lines[i + 1:]:
                if x.startswith("      "):
                    block.append(x)
                else:
                    break
            return block
    return None


def judge_help_general(text, doc, code, tools_text):
    """С1. Общая справка: код 0 · на КАЖДЫЙ вызов договора строка с его именем и заголовком · режимов четыре ·
    версия и отпечатки те же строки, что печатает режим tools · форма вызова run называет аргумент выбора контура из договора."""
    notes = []
    lines = text.splitlines()
    if code != 0:
        notes.append("код выхода %s, ждали 0" % code)
    missing = [t["name"] for t in doc["tools"]
               if not any(t["name"] in l and t["title"] in l for l in lines)]
    if missing:
        notes.append("нет строки с именем и заголовком вызова: %s" % ", ".join(missing))
    mode_lines = help_section(text, "режимы:")
    modes = [l.split()[0] for l in mode_lines if l.split()] if mode_lines else []
    if sorted(modes) != sorted(HELP_MODES):
        notes.append("режимы в справке: %s (ждали %s)" % (", ".join(modes) or "раздела нет", ", ".join(HELP_MODES)))
    shared = tools_contract_lines(tools_text)
    if len(shared) != 3:
        notes.append("режим tools не выдал строки версии и отпечатков: судить не с чем")
    stripped = set(l.strip() for l in lines)
    lacking = [k for k, v in shared.items() if v not in stripped]
    if lacking:
        notes.append("строки, которых нет в справке буква в букву, как в tools: %s" % ", ".join(lacking))
    carg = [a["name"] for a in doc["common_args"] if a.get("selects") == "contour"]
    if not carg or ("run <вызов> " + help_flag(carg[0])) not in text:
        notes.append("форма вызова run не называет аргумент выбора контура из договора")
    detail = ("код %s · вызовов договора %d, строк найдено %d · режимы: %s\n"
              % (code, len(doc["tools"]), len(doc["tools"]) - len(missing), ", ".join(modes) or "—"))
    detail += "\n".join(notes) if notes else "всё названное найдено"
    return not notes, detail


def judge_help_tool(text, tool, common, code, variant_lines):
    """С2. Справка по одному вызову: код 0 · имя, заголовок, описание · КАЖДЫЙ общий и свой аргумент назван флагом
    с типом и пометкой обязательности из договора · перечень значений там, где он есть · строки вариантов те же, что в tools ·
    служебные записи · пример формы."""
    notes = []
    lines = text.splitlines()
    if code != 0:
        notes.append("код выхода %s, ждали 0" % code)
    if not lines or tool["name"] not in lines[0]:
        notes.append("первая строка не называет вызов")
    if not any(l.startswith("заголовок:") and tool["title"] in l for l in lines):
        notes.append("нет строки «заголовок:» с заголовком из договора")
    if tool.get("description") and squash(tool["description"]) not in squash(text):
        notes.append("описание вызова из договора не напечатано")
    for a in list(common) + list(tool.get("args", [])):
        flag = help_flag(a["name"])
        block = arg_block(lines, flag)
        if block is None:
            notes.append("аргумент %s не назван" % flag)
            continue
        head = block[0]
        if ("<%s>" % a.get("type", "string")) not in head:
            notes.append("у %s нет типа <%s>" % (flag, a.get("type", "string")))
        mark = "· обязателен" if a.get("required") else "· не обязателен"
        if mark not in head:
            notes.append("у %s нет пометки «%s»" % (flag, mark[2:]))
        body = "\n".join(block)
        # перечень значений судим по строке самого аргумента, а не по всему блоку: слово из перечня может стоять и в описании
        if a.get("enum") and ("значения: " + " | ".join(a["enum"])) not in head:
            notes.append("у %s нет перечня значений «%s» в строке аргумента" % (flag, " | ".join(a["enum"])))
        if a.get("description") and squash(a["description"]) not in squash(body):
            notes.append("у %s нет описания из договора" % flag)
    stripped = set(l.strip() for l in lines)
    for v in variant_lines:
        if v not in stripped:
            notes.append("нет строки варианта, как в tools: %s" % v[:70])
    writes = tool.get("service_writes")
    if writes:
        wl = [l for l in lines if l.startswith("служебные записи:")]
        if not wl or any(w not in wl[0] for w in writes):
            notes.append("служебные записи не названы: %s" % ", ".join(writes))
    if not any(("run " + tool["name"]) in l and l.startswith("  gordi-wall") for l in lines):
        notes.append("нет примера формы вызова через run")
    n_args = len(common) + len(tool.get("args", []))
    detail = "вызов %s · код %s · аргументов проверено %d · строк вариантов %d\n" % (tool["name"], code, n_args, len(variant_lines))
    detail += "\n".join(notes) if notes else "всё названное найдено"
    return not notes, detail


def judge_help_unknown(stdout, stderr, code, doc):
    """С3. Незнакомый вызов в справке: код 4 · в потоке ошибок названы ВСЕ вызовы договора · стандартный вывод пуст."""
    notes = []
    if code != 4:
        notes.append("код выхода %s, ждали 4" % code)
    lacking = [t["name"] for t in doc["tools"] if t["name"] not in stderr]
    if lacking:
        notes.append("в потоке ошибок не названы вызовы: %s" % ", ".join(lacking))
    if stdout != "":
        notes.append("стандартный вывод не пуст (%d знаков)" % len(stdout))
    detail = "код %s · вызовов названо %d из %d · знаков в стандартном выводе %d\n" % (
        code, len(doc["tools"]) - len(lacking), len(doc["tools"]), len(stdout))
    detail += "\n".join(notes) if notes else "всё названное найдено"
    return not notes, detail


def judge_help_from_copy(general_text, probe_text, renamed_text, spec):
    """С6. Справка по КОПИИ договора (тринадцатый вызов, переименованный аргумент): общая называет новый вызов,
    справка по новому вызову печатается, справка по вызову с переименованным аргументом называет новый флаг, старого — нет."""
    import re
    notes = []
    if not any(spec["new_tool"] in l and spec["new_title"] in l for l in general_text.splitlines()):
        notes.append("общая справка не называет новый вызов %s с его заголовком" % spec["new_tool"])
    first = probe_text.splitlines()[0] if probe_text.strip() else ""
    if spec["new_tool"] not in first:
        notes.append("справка по новому вызову не напечатана")
    if not renamed_text.strip():
        notes.append("справки по вызову с переименованным аргументом нет")
    else:
        if arg_block(renamed_text.splitlines(), spec["new_flag"]) is None:
            notes.append("справка по вызову %s не называет новый флаг %s" % (spec["tool"], spec["new_flag"]))
        if re.search(re.escape(spec["old_flag"]) + r"(?![\w-])", renamed_text):
            notes.append("в справке по вызову %s остался старый флаг %s" % (spec["tool"], spec["old_flag"]))
    detail = "новый вызов %s · флаг %s → %s в вызове %s\n" % (spec["new_tool"], spec["old_flag"], spec["new_flag"], spec["tool"])
    detail += "\n".join(notes) if notes else "новое имя названо, старого нет"
    return not notes, detail


def judge_help_modes(general_text, refusal_stderr, code):
    """С7. Отказ «режима нет» называет те же режимы, что общая справка; код 4."""
    notes = []
    if code != 4:
        notes.append("код выхода %s, ждали 4" % code)
    mode_lines = help_section(general_text, "режимы:")
    in_help = sorted(l.split()[0] for l in mode_lines if l.split()) if mode_lines else []
    named = []
    if "Есть: " in refusal_stderr:
        tail = refusal_stderr.split("Есть: ", 1)[1].strip().splitlines()[0]
        named = sorted(x.strip() for x in tail.split(" · ") if x.strip())
    if not in_help:
        notes.append("в общей справке нет раздела режимов")
    if named != in_help:
        notes.append("отказ называет режимы %s, справка — %s" % (named or "не названы", in_help or "не названы"))
    detail = "код %s · отказ: %s · справка: %s\n" % (code, ", ".join(named) or "—", ", ".join(in_help) or "—")
    detail += "\n".join(notes) if notes else "перечни совпали"
    return not notes, detail


def judge_help_exit_table(general_text, observed):
    """С8. Таблица «исход → код выхода» в общей справке совпадает с тем, что режим run отдал на заглушках.
    observed — список (код выхода, стандартный вывод) для не меньше трёх разных исходов: 0, 1 и 6."""
    import re
    notes = []
    rows = {}
    section = help_section(general_text, "исход вызова и код выхода")
    for line in section or []:
        m = re.match(r"^\s*(\d+)\s+(\w+)\s+(.+?)\s*$", line)
        if m:
            rows[int(m.group(1))] = (m.group(2), m.group(3))
    if not rows:
        notes.append("в общей справке нет таблицы «исход → код выхода»")
    for code, ident in OUTCOME_BY_CODE.items():
        if rows and rows.get(code, ("", ""))[0] != ident:
            notes.append("в таблице у кода %d исход «%s», ждали «%s»" % (code, rows.get(code, ("нет строки",))[0], ident))
    seen = sorted(set(c for c, _ in observed))
    for need in sorted(HELP_RUN_STAND_CODES):
        if need not in seen:
            notes.append("режим run не отдал код %d на заглушках: сверять нечем" % need)
    for code, out in observed:
        title = rows.get(code, ("", ""))[1]
        if not title or ("исход: " + title) not in out:
            notes.append("код %s: в таблице заголовок «%s», а режим run напечатал не его" % (code, title))
    detail = "строк таблицы %d · коды, отданные режимом run на заглушках: %s\n" % (len(rows), ", ".join(str(c) for c in seen) or "—")
    detail += "\n".join(notes) if notes else "таблица совпала с режимом run"
    return not notes, detail


def help_scenario(doc, tools_text, general, per_tool, unknown):
    """Прогоняет чистые проверяющие С1–С3 над набором текстов; отдаёт множество не прошедших случаев.
    general — (код, текст); per_tool — {имя вызова: (код, текст)}; unknown — (код, стандартный вывод, поток ошибок)."""
    failed = set()
    if not judge_help_general(general[1], doc, general[0], tools_text)[0]:
        failed.add("С1")
    for t in doc["tools"]:
        code, text = per_tool.get(t["name"], (None, ""))
        if not judge_help_tool(text, t, doc["common_args"], code, tools_variant_lines(tools_text, t["name"]))[0]:
            failed.add("С2")
            break
    if not judge_help_unknown(unknown[1], unknown[2], unknown[0], doc)[0]:
        failed.add("С3")
    return failed


def break_drop_tool_line(general, name):
    """Л1: из общей справки убраны строки одного вызова."""
    code, text = general
    return code, "\n".join(l for l in text.splitlines() if name not in l) + "\n"


def break_drop_arg_line(per_tool, name, flag):
    """Л2: из справки по вызову убрана строка одного аргумента."""
    out = dict(per_tool)
    code, text = out[name]
    out[name] = (code, "\n".join(l for l in text.splitlines()
                                 if not (l.startswith("  ") and l.strip().startswith(flag + " "))) + "\n")
    return out


def break_unknown_code(unknown):
    """Л3: тот же текст отказа, но код выхода 0."""
    return 0, unknown[1], unknown[2]


def run_cli(exe, argv, env_extra=None, timeout=HELP_LIMIT_S):
    """Одиночный процесс службы со ЗАКРЫТЫМ вводом и пределом времени. Отдаёт (код, вывод, поток ошибок, не уложился ли).
    Служба, вместо справки поднявшаяся ждать ввода, получает конец ввода сразу и всё равно ограничена пределом: зависание = случай не прошёл."""
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    for k in ("GORDI_CONTRACT", "GORDI_CONTOURS"):
        env.pop(k, None)
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run([exe] + list(argv), stdin=subprocess.DEVNULL, capture_output=True, encoding="utf-8",
                           errors="replace", env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "", "", True
    return p.returncode, p.stdout, p.stderr, False


def rename_arg_in_doc(tool, old, new):
    """Переименовывает аргумент вызова в копии договора: объявление, отображение в exec.args, requires и env у вариантов."""
    for a in tool.get("args", []):
        if a["name"] == old:
            a["name"] = new
    execs = [tool["exec"]] if "exec" in tool else [v["exec"] for v in tool.get("variants", {}).values()]
    for ex in execs:
        for m in ex.get("args", []):
            if m.get("arg") == old:
                m["arg"] = new
        for k, v in list((ex.get("env") or {}).items()):
            if v == old:
                ex["env"][k] = new
    for v in tool.get("variants", {}).values():
        v["requires"] = [new if r == old else r for r in v.get("requires", [])]


def cases_e3p1(args, work, manifest, contract_doc, carg, v5):
    """Раздел «Э3-П1»: С1–С8 на настоящем договоре и копиях, затем Л1–Л4."""
    import copy
    d = os.path.join(work, "e3-p1")
    if not os.path.isdir(d):
        os.makedirs(d)
    exe, contract, contours = args.exe, args.contract, args.contours
    doc = contract_doc
    common = doc["common_args"]

    def timed_out_note(label, flag):
        return ("%s: процесс не завершился за %d с — зависание = случай не прошёл" % (label, HELP_LIMIT_S)) if flag else ""

    # перечень tools — эталон строк версии, отпечатков и вариантов
    tc, tools_text, _, tto = run_cli(exe, ["tools", "--contract", contract, "--contours", contours])

    # ───────────── С1 общая справка
    gc, gout, gerr, gto = run_cli(exe, ["help", "--contract", contract])
    if gto:
        ok1, det1 = False, timed_out_note("help", True)
    else:
        ok1, det1 = judge_help_general(gout, doc, gc, tools_text)
        if gc != 0:
            det1 += "\nпоток ошибок: %s" % squash(gerr)[:160]
    v5.add("814-С1", ok1, "общая справка из договора: вызовы с заголовками, четыре режима, версия и отпечатки как в tools", det1)

    # ───────────── С2 справка по КАЖДОМУ вызову
    per_tool = {}
    bad2 = []
    done2 = 0
    for t in doc["tools"]:
        c, o, e, to = run_cli(exe, ["help", t["name"], "--contract", contract])
        per_tool[t["name"]] = (c, o)
        if to:
            bad2.append("%s: %s" % (t["name"], timed_out_note("help", True)))
            continue
        ok, det = judge_help_tool(o, t, common, c, tools_variant_lines(tools_text, t["name"]))
        done2 += 1
        if not ok:
            bad2.append("%s: %s" % (t["name"], squash(det.split("\n", 1)[1])[:200]))
    ok2 = not bad2 and done2 == len(doc["tools"])
    v5.add("814-С2", ok2, "справка по КАЖДОМУ вызову договора: аргументы с типом, обязательностью и перечнем значений, строки вариантов как в tools",
           "вызовов проверено %d из %d\n%s" % (done2, len(doc["tools"]), "\n".join(bad2) if bad2 else "всё названное найдено у каждого"))

    # ───────────── С3 незнакомый вызов
    uc, uout, uerr, uto = run_cli(exe, ["help", HELP_UNKNOWN_TOOL, "--contract", contract])
    uc2, uout2, uerr2, uto2 = run_cli(exe, ["run", HELP_UNKNOWN_TOOL, "--help", "--contract", contract])
    if uto or uto2:
        ok3, det3 = False, timed_out_note("help <вызов>", True)
    else:
        ok3a, det3a = judge_help_unknown(uout, uerr, uc, doc)
        ok3b, det3b = judge_help_unknown(uout2, uerr2, uc2, doc)
        ok3 = ok3a and ok3b
        det3 = "help <вызов>: %s\nrun <вызов> --help: %s" % (squash(det3a), squash(det3b))
    v5.add("814-С3", ok3, "незнакомый вызов в справке: код 4, в потоке ошибок все вызовы договора, стандартный вывод пуст", det3)

    # ───────────── стенд для С4 и С8: заглушки тел и манифест, ведущий на каталог заглушек
    stubs = os.path.join(d, "stubs")
    if not os.path.isdir(stubs):
        os.makedirs(stubs)

    def put_stub(name, source):
        io.open(os.path.join(stubs, name), "w", encoding="utf-8", newline="\n").write(source)

    marker = os.path.join(d, "stub-started.txt")
    if os.path.exists(marker):
        os.remove(marker)
    put_stub("stub-pass.py", "import sys\nsys.stdout.write('pass stub\\n')\n")
    put_stub("stub-mismatch.py", "import sys\nsys.stdout.write('E3-MISMATCH-MARK\\n')\nsys.exit(1)\n")
    put_stub("stub-fail.py", "import sys\nsys.stdout.write('fail stub\\n')\nsys.exit(1)\n")
    put_stub("stub-marker.py", "import sys\nopen(%r, 'w').write('started')\nsys.stdout.write('marker stub ran\\n')\n" % marker)
    m_stub = copy.deepcopy(manifest)
    for c in m_stub["contours"]:
        c["tools"] = {"runtime": stubs, "vnext": stubs}
    m_stub_path = os.path.join(d, "contours-stubs.json")
    write_json(m_stub_path, m_stub)

    def stub_contract(tag, mapping, mismatch=None):
        dd = copy.deepcopy(doc)
        for t in dd["tools"]:
            if t["name"] in mapping:
                set_script_all(t, mapping[t["name"]])
            if mismatch and t["name"] in mismatch:
                t["exec"]["mismatch_when"] = mismatch[t["name"]]
        p = os.path.join(d, "contract-%s.json" % tag)
        write_json(p, dd)
        return p

    probe = "owner_words_find"            # читающий вызов с одним обязательным аргументом: на нём видно, запустилось ли тело
    marker_contract = stub_contract("marker", {probe: "stub-marker.py"})
    cflag = help_flag(carg)

    # ───────────── С4 --help и -h
    notes4 = []
    ref_c, ref_o, _, ref_to = run_cli(exe, ["help", "--contract", contract])
    for flag in ("--help", "-h"):
        c, o, e, to = run_cli(exe, [flag, "--contract", contract])
        if to:
            notes4.append("%s без режима: %s" % (flag, timed_out_note("", True)))
        elif c != 0 or o != ref_o or not o.strip():
            notes4.append("%s без режима: код %s, текст %s общей справке (знаков %d против %d)"
                          % (flag, c, "равен" if o == ref_o else "НЕ равен", len(o), len(ref_o)))
    ref_tc, ref_tool_text, _, _ = run_cli(exe, ["help", probe, "--contract", marker_contract])
    # две формы вызова: голая — справка обязана выйти и без обязательных аргументов; полная — только она
    # способна запустить тело, поэтому лишь на ней «следа запуска нет» что-то различает (находка приёмки чужой рукой)
    help_forms = (("без аргументов", []), ("с полными аргументами", [cflag, CONTOUR_STAND, "--text", "x"]))
    for flag in ("--help", "-h"):
        for form, extra in help_forms:
            c, o, e, to = run_cli(exe, ["run", probe] + extra + [flag, "--contract", marker_contract, "--contours", m_stub_path])
            if to:
                notes4.append("run %s %s (%s): %s" % (probe, flag, form, timed_out_note("", True)))
            elif c != 0 or o != ref_tool_text or not o.strip():
                notes4.append("run %s %s (%s): код %s, текст %s справке по вызову"
                              % (probe, flag, form, c, "равен" if o == ref_tool_text else "НЕ равен"))
    if os.path.exists(marker):
        notes4.append("тело инструмента-заглушки запустилось от --help: файл-отметка есть")
    # встречная проба: тот же вызов без --help тело запускает — иначе «следа нет» ничего бы не доказывало
    run_cli(exe, ["run", probe, cflag, CONTOUR_STAND, "--text", "x", "--contract", marker_contract, "--contours", m_stub_path], timeout=60)
    control = os.path.exists(marker)
    if not control:
        notes4.append("встречная проба: вызов без --help тело заглушки НЕ запустил, отметка не появилась — случай ничего не доказывает")
    v5.add("814-С4", not notes4, "--help и -h без режима дают общую справку и завершаются сами за %d с; run <вызов> --help не запускает тело" % HELP_LIMIT_S,
           "проверено: --help и -h без режима · run %s --help и -h на заглушке, без аргументов и с полными · встречная проба (след запуска без --help есть: %s)\n%s"
           % (probe, control, "\n".join(notes4) if notes4 else "тексты равны справкам, следа запуска от --help нет"))

    # ───────────── С5 справка без манифеста контуров
    notes5 = []
    first_tool = doc["tools"][0]["name"]
    for label, extra in (("манифест не назван", []),
                         ("манифест назван несуществующим файлом", ["--contours", os.path.join(d, "нет-такого-манифеста.json")])):
        for argv in (["help"], ["help", first_tool]):
            c, o, e, to = run_cli(exe, argv + ["--contract", contract] + extra)
            if to:
                notes5.append("%s, %s: %s" % (label, " ".join(argv), timed_out_note("", True)))
            elif c != 0 or not o.strip():
                notes5.append("%s, %s: код %s, стандартный вывод %d знаков, ошибки: %s" % (label, " ".join(argv), c, len(o), squash(e)[:120]))
    v5.add("814-С5", not notes5, "справка и справка по вызову работают без манифеста контуров (не назван и назван несуществующим файлом)",
           "\n".join(notes5) if notes5 else "четыре запуска: код 0, текст есть")

    # ───────────── С6 справка строится из ДОГОВОРА: копия с тринадцатым вызовом и переименованным аргументом, без пересборки
    copy_doc = copy.deepcopy(doc)
    donor = copy.deepcopy(tool_doc(copy_doc, probe))
    donor["name"] = HELP_NEW_TOOL
    donor["title"] = HELP_NEW_TITLE
    copy_doc["tools"].append(donor)
    rename_arg_in_doc(tool_doc(copy_doc, HELP_RENAME[0]), HELP_RENAME[1], HELP_RENAME[2])
    copy_path = os.path.join(d, "contract-copy-13.json")
    write_json(copy_path, copy_doc)
    cc, cgen, _, cto1 = run_cli(exe, ["help", "--contract", copy_path])
    pc, cprobe, _, cto2 = run_cli(exe, ["help", HELP_NEW_TOOL, "--contract", copy_path])
    rc, crenamed, _, cto3 = run_cli(exe, ["help", HELP_RENAME[0], "--contract", copy_path])
    spec = {"new_tool": HELP_NEW_TOOL, "new_title": HELP_NEW_TITLE, "tool": HELP_RENAME[0],
            "old_flag": help_flag(HELP_RENAME[1]), "new_flag": help_flag(HELP_RENAME[2])}
    if cto1 or cto2 or cto3:
        ok6, det6 = False, timed_out_note("help на копии договора", True)
    else:
        ok6, det6 = judge_help_from_copy(cgen, cprobe, crenamed, spec)
        if cc != 0 or pc != 0 or rc != 0:
            ok6 = False
            det6 += "\nкоды выхода трёх справок: %s, %s, %s (ждали 0)" % (cc, pc, rc)
    v5.add("814-С6", ok6, "справка строится из договора: на копии с тринадцатым вызовом и переименованным аргументом — без пересборки службы", det6)

    # ───────────── С7 перечень режимов: справка и отказ «режима нет»
    mc, mout, merr, mto = run_cli(exe, [HELP_UNKNOWN_MODE, "--contract", contract, "--contours", contours])
    if mto or gto:
        ok7, det7 = False, timed_out_note("режим, которого нет", True)
    else:
        ok7, det7 = judge_help_modes(gout, merr, mc)
    v5.add("814-С7", ok7, "отказ «режима нет» называет те же режимы, что общая справка", det7)

    # ───────────── С8 таблица «исход → код выхода» и режим run на заглушках
    codes_contract = stub_contract("codes", {"rules_get": "stub-pass.py", "owner_words_find": "stub-mismatch.py",
                                             "feed_read": "stub-fail.py"},
                                   mismatch={"owner_words_find": ["E3-MISMATCH-MARK"]})
    runs8 = [["rules_get", cflag, CONTOUR_STAND, "--list"],
             ["owner_words_find", cflag, CONTOUR_STAND, "--text", "x"],
             ["feed_read", cflag, CONTOUR_STAND, "--role", "COORD"]]
    observed = []
    for argv in runs8:
        c, o, e = run_mode(exe, codes_contract, m_stub_path, argv)
        observed.append((c, o))
    if gto:
        ok8, det8 = False, timed_out_note("help", True)
    else:
        ok8, det8 = judge_help_exit_table(gout, observed)
    v5.add("814-С8", ok8, "таблица «исход → код выхода» в справке совпадает с режимом run на заглушках (0 прошло · 1 расхождение · 6 тело отказало)", det8)

    # ───────────── нарочные поломки: Л1–Л3 над ТЕКСТОМ без пересборки, Л4 — справка от целого договора в случае по копии
    general = (gc, gout)
    unknown = (uc, uout, uerr)
    base_failed = help_scenario(doc, tools_text, general, per_tool, unknown)
    victim_tool = doc["tools"][-1]["name"]
    victim_arg_tool = "memory_read"
    victim_flag = help_flag(tool_doc(doc, victim_arg_tool)["args"][0]["name"])
    breaks = [
        ("Л1", "С1", "из общей справки убраны строки вызова %s" % victim_tool,
         lambda: help_scenario(doc, tools_text, break_drop_tool_line(general, victim_tool), per_tool, unknown)),
        ("Л2", "С2", "из справки по вызову %s убрана строка аргумента %s" % (victim_arg_tool, victim_flag),
         lambda: help_scenario(doc, tools_text, general, break_drop_arg_line(per_tool, victim_arg_tool, victim_flag), unknown)),
        ("Л3", "С3", "отказу по незнакомому вызову дан код выхода 0 при том же тексте",
         lambda: help_scenario(doc, tools_text, general, per_tool, break_unknown_code(unknown))),
    ]
    for key, own, what, scenario in breaks:
        title = "нарочная поломка: %s — падает РОВНО случай %s" % (what, own)
        if base_failed:
            v5.add("814-" + key, False, title,
                   "СУДИТЬ НЕЧЕМ: до поломки не прошли случаи %s — поломка не на чем видна" % ", ".join(sorted(base_failed)))
        else:
            failed = scenario()
            v5.add("814-" + key, failed == {own}, title,
                   "не прошли после поломки: %s (ждали только %s)" % (", ".join(sorted(failed)) or "ни один", own))
    # Л4: тот же случай С6, но справка взята от ЦЕЛОГО договора — копии в нём нет, случай обязан упасть
    title4 = "нарочная поломка: справка от ЦЕЛОГО договора вместо копии — падает случай С6 (разница двух прогонов — довод)"
    if not ok6:
        v5.add("814-Л4", False, title4, "СУДИТЬ НЕЧЕМ: на самой копии случай С6 не прошёл")
    else:
        whole_probe = run_cli(exe, ["help", HELP_NEW_TOOL, "--contract", contract])[1]
        whole_renamed = per_tool.get(HELP_RENAME[0], (None, ""))[1]
        ok_whole, det_whole = judge_help_from_copy(gout, whole_probe, whole_renamed, spec)
        v5.add("814-Л4", not ok_whole, title4,
               "на копии С6 прошёл; на справке целого договора С6 %s: %s"
               % ("прошёл" if ok_whole else "не прошёл", squash(det_whole.split("\n", 1)[1])[:200]))


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
    ap.add_argument("--only-e3p1", action="store_true",
                    help="судить ТОЛЬКО раздел «Э3-П1» (справка службы); сборку старше исходников в этом режиме судит как СТАРУЮ, "
                         "чтобы получить прогон «до» на сборке без справки; в общий прогон не входит")
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
    if exe_time < src_time and args.only_e3p1:
        print("ℹ️ СБОРКА СТАРШЕ ИСХОДНИКОВ, но задан --only-e3p1: раздел «Э3-П1» судит её как СТАРУЮ сборку (прогон «до»).")
        print("   Это не приёмка новой службы: общий прогон такую сборку по-прежнему не судит.")
    elif exe_time < src_time:
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

    if args.only_e3p1:
        v5 = Verdict()
        cases_e3p1(args, work, manifest, contract_doc, CARG, v5)
        print("── случаи карточки 814 (этап Э3, предмет П1: справка из того же договора) — ТОЛЬКО этот раздел")
        v5.print_all()
        if v5.failed():
            print("🔴 ПРОВАЛИЛОСЬ %d: %s (карточка 814: %d из %d прошло)"
                  % (len(v5.failed()), " · ".join(r[0] for r in v5.failed()), len(v5.rows) - len(v5.failed()), len(v5.rows)))
            return 1
        print("✅ РАЗДЕЛ Э3-П1 ПРОШЁЛ: карточка 814 — %d из %d" % (len(v5.rows), len(v5.rows)))
        return 0

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
    s2a, t2a = w.call("memory_write", {"contour": CONTOUR_STAND, "action": "save", "role": "PROTO", "section": "state",
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
        if t["name"] == "memory_write":
            t["variants"]["save"]["exec"]["mismatch_when"] = []
    path_b = os.path.join(work, "contract-broken-b.json")
    write_json(path_b, broken_b)
    w_b = Wall(args.exe, path_b, args.contours)
    s_b, t_b = w_b.call("memory_write", {"contour": CONTOUR_STAND, "action": "save", "role": "PROTO", "section": "state",
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

    # ═══════════════════════════════════════ карточка 781: варианты вызова · рука тела · память слоями · карточки · слова владельца
    v4 = Verdict()
    cases_781(args, work, manifest, contract_doc, CARG, v4)

    # ═══════════════════════════════════════ карточка 814 (этап Э3, предмет П1): справка службы из того же договора
    v5 = Verdict()
    cases_e3p1(args, work, manifest, contract_doc, CARG, v5)

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
    print("── случаи карточки 781 (варианты вызова · рука тела · поиск и сжатие памяти слоями · завести карточку · слово владельца · три нарочные поломки)")
    v4.print_all()
    print("")
    print("── случаи карточки 814 (этап Э3, предмет П1: справка из того же договора · восемь случаев С1–С8 и четыре нарочные поломки Л1–Л4)")
    v5.print_all()
    print("")
    print("⚖️ ЭТИ ДВА КРИТЕРИЯ МАШИНА НЕ СУДИТ — говорю прямо, чтобы зелёное не прочлось шире:")
    print("   ⑥ полный рабочий отрезок роли через стену — доказывается работой роли (записка · память · карточка),")
    print("      а не этим файлом. Прогон приёмки отрезком НЕ является.")
    print("   ⑨ подпись приёмки ставит роль, которая службу НЕ писала. Свой прогон за чужую руку не считается.")
    print("")
    bad = v.failed() + v2.failed() + v3.failed() + v4.failed() + v5.failed()
    if bad:
        print("🔴 ПРОВАЛИЛОСЬ %d: %s (карточка 779: %d из %d прошло · карточка 787: %d из %d прошло · карточка 791: %d из %d прошло · карточка 781: %d из %d прошло · карточка 814: %d из %d прошло)"
              % (len(bad), " · ".join(r[0] for r in bad),
                 len(v.rows) - len(v.failed()), len(v.rows), len(v2.rows) - len(v2.failed()), len(v2.rows),
                 len(v3.rows) - len(v3.failed()), len(v3.rows), len(v4.rows) - len(v4.failed()), len(v4.rows),
                 len(v5.rows) - len(v5.failed()), len(v5.rows)))
        return 1
    print("✅ ВСЕ МАШИННЫЕ КРИТЕРИИ ПРОШЛИ: карточка 779 — %d из %d · карточка 787 — %d из %d · карточка 791 — %d из %d · карточка 781 — %d из %d · карточка 814 — %d из %d (⑥ и ⑨ карточки 779 — за человеком)"
          % (len(v.rows), len(v.rows), len(v2.rows), len(v2.rows), len(v3.rows), len(v3.rows), len(v4.rows), len(v4.rows), len(v5.rows), len(v5.rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
