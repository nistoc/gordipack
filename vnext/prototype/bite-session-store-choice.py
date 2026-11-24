# -*- coding: utf-8 -*-
"""bite-session-store-choice.py — приёмка карточки #833 (issue 34 пакета): СВОЁ ли хранилище
сессий приложения читают инструменты сверки адресов.

ЗАЧЕМ. mezo_sessions.py брал хранилище только из MEZO_SESSION_STORE или из %APPDATA%. Приложение,
запущенное ВТОРОЙ копией с отдельным каталогом данных, держит сессии в этом каталоге — и проверка
«session_id ролей жив» либо читала ЧУЖОЕ хранилище (контур AIA: «не найден» у 9 из 9, прогон
проходил), либо не находила никакого (onto и Atlas: «сверить нечем», роли не проверены). Ни один
исход не отличал «наши сессии мертвы» от «прочитано чужое».

МИР ПРИЁМКИ — целиком во временном каталоге, настоящее хранилище приложения не открывается:
    appA/claude-code/2.1.0/b1/claude.exe   копия приложения A; рядом appA/claude-code-sessions —
                                           ТЕКУЩАЯ сессия local_cur и сессии двух ролей
    appB/claude-code/2.1.0/b1/claude.exe   копия B; её хранилище БЕЗ текущей сессии
    appC/claude-code/2.1.0/b1/claude.exe   копия C; хранилища рядом нет вовсе
    roamA/Claude/claude-code-sessions      стандартное место, В НЁМ текущая сессия и роли
    roamF/Claude/claude-code-sessions      стандартное место ЧУЖОЙ копии: текущей сессии нет,
                                           зато есть живая сессия с заголовком роли ZZ-A1
    roamNone                               стандартное место пустое
    half                                   хранилище, где найдена только одна роль из трёх

СЛУЧАИ (каждый — свой вызов со своей средой):
  выбор пути (mezo_sessions.read_store без аргумента)
    М1 переменная сильнее копии приложения — и контрольное слово судит и её (чужое → foreign)
    М2 без переменной: хранилище рядом с копией A, текущая сессия в нём есть
    М3 рядом с копией B текущей сессии нет, в стандартном месте есть → взято стандартное
    М4 копии приложения нет, стандартное место чужое → foreign
    М5 текущая сессия неизвестна, кандидатов два → первый по порядку (рядом с копией)
    М6 номер текущей сессии не вида «local_…» → контрольное слово не судится (не foreign)
    М7 рядом с копией каталога нет, стандартного нет → «не найдено» и слова об этом
  проверка ролей (guard-role-sessions-live.py --soft)
    Г1 своё хранилище: «живы у всех», источник «рядом с копией приложения», «текущая сессия в нём есть»
    Г2 чужое хранилище: отдельный исход «НЕ НАШЕ», код 1 И с --soft, ролей «не найден» нет
    Г3 текущая сессия неизвестна, не найден ни один из 3 → своя строка «НЕ НАЙДЕН НИ ОДИН»
    Г4 встречный к Г3: не найдены двое из трёх → строки «ни один» нет
    Г5 хранилища нет нигде → «СВЕРИТЬ НЕЧЕМ» называет источник пути и что рядом с копией пусто
       (Н3 приёмки COORD: прежде строка была слово в слово как до выпуска)
  записка (write-message.py)
    W1 чужое хранилище → «НЕ сверена» и «НЕ НАШЕ», а не «НЕДОСТИЖИМ» у адресата; записка легла
    W2 своё хранилище рядом с копией → адресат жив, предупреждений нет
  запись адреса и сигнал (signal-templates.py)
    S1 чужое хранилище, только имя → сессия по имени НЕ подобрана (заголовок есть в чужом)
    S2 чужое хранилище, --session-id нашей роли → не отказ «НЕ НАЙДЕН» с перечнем чужих сессий
    S3 своё хранилище → сверка работает: номер записи разговора взят из хранилища сам
    S4 реестр адресов (--list), чужое хранилище → «сверить нечем», а не «такой сессии нет»
       у каждой роли (Н2 приёмки COORD: read_store_guarded() прежде не испытывался ничем)
    S5 печать сигнала, чужое хранилище → нет предупреждения «сессии … нет» об адресате

⚖️ В заголовках случаев и поломок знаков вердикта нет: набор ядра считает «✅» и «🔴» во всём
выводе, и знак в заголовке давал лишнее «✅» (Н1 приёмки COORD: «0 · 24 · 0» при «0 23 0»).
Заголовки, как и подробности, проходят через quiet().

НАРОЧНЫЕ ПОЛОМКИ — в том же прогоне, каждая на своей копии инструментов; ждём провала РОВНО
названных случаев (список — BREAKS ниже, с доводом у каждого).

ОБРАТНЫЙ ХОД: --old-pack <корень пакета> берёт испытуемые инструменты из пакета другой вершины
(его vnext/prototype и scripts) и гонит только случаи — без поломок; печатает, какие провалились.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

WRITE_TARGET = mezo_target.script("write-message.py")
sys.path.insert(0, str(mezo_paths.live_scripts()))
# mezo_stand — из каталога самой приёмки (как у bite-unreachable-addressee.py): stand_env этой
# версии не передаёт стенду CLAUDE_CODE_HOST_SESSION_ID и CLAUDE_CODE_EXECPATH.
sys.path.insert(0, str(TOOLS_DIR))
import mezo_stand  # noqa: E402
sys.path.pop(0)

CUR = "local_cur"
ROLES = (("ZZA1", "local_roleA1"), ("ZZA2", "local_roleA2"), ("ZZWRITER", CUR))
SIGNAL_ROLES = ("ZZS1", "ZZS2", "ZZS3")

MOD = "mezo_sessions.py"
GUARD = "guard-role-sessions-live.py"
SIGNAL = "signal-templates.py"
BREAKS = {
    "П1": ("контрольное слово снято", MOD,
           "        current_found = any(r.session_id == current for r in store.sessions)\n",
           "        current_found = None\n",
           # без него чужое не отличить от своего, и «текущая сессия есть» не говорится
           {"М1", "М2", "М4", "Г1", "Г2", "W1", "S1", "S2", "S4", "S5"}),
    "П2": ("поиск рядом с копией приложения снят", MOD,
           "    if not exe:\n        return []\n",
           "    if True:\n        return []\n",
           # остаётся только стандартное место; М3 стоит на нём и цел
           {"М2", "М5", "Г1", "W2", "S3"}),
    "П3": ("порядок кандидатов перевёрнут", MOD,
           "        candidates.append((fallback, SOURCE_FALLBACK))\n",
           "        candidates.insert(0, (fallback, SOURCE_FALLBACK))\n",
           # при известной текущей сессии выбор идёт по ней и порядок не виден — виден только в М5
           {"М5"}),
    "П4": ("выбор не смотрит на текущую сессию", MOD,
           "            if _holds_session(path, current):\n",
           "            if False:\n",
           # берётся первый кандидат; только в М3 первый — не тот, где текущая сессия
           {"М3"}),
    "П5": ("строка «не найден ни один» снята", GUARD,
           "    if len(rows) >= 2 and missing == len(rows):\n",
           "    if False:\n",
           {"Г3"}),
    "П6": ("чужое хранилище в мягком режиме проходит", GUARD,
           "        return 1\n    where = ",
           "        return 0 if a.soft else 1\n    where = ",
           {"Г2"}),
    "П7": ("реестр адресов и сигнал читают хранилище без контрольного слова", SIGNAL,
           "        return mezo_sessions.trusted(mezo_sessions.read_store())\n",
           "        return mezo_sessions.read_store()\n",
           # запись адреса (S1–S3) судит хранилище своим путём; read_store_guarded() — только эти два
           {"S4", "S5"}),
    "П8": ("«не найдено» не называет, где искали", MOD,
           '        error = f"{error}; путь — {source}" + (f"; {note}" if note else "")\n',
           "        error = error\n",
           # М7 судит заметку выбора в самом модуле, а не слова отказа, — цел
           {"Г5"}),
}

DRIVER = '''import json, sys
sys.path.insert(0, sys.argv[1])
import mezo_sessions as m
s = m.read_store()
print(json.dumps({"found": s.found, "path": str(s.path), "source": getattr(s, "source", None),
                  "note": getattr(s, "choice_note", None),
                  "current_found": getattr(s, "current_found", None),
                  "foreign": getattr(s, "foreign", None)}, ensure_ascii=False))
'''


def session_file(store: Path, sid: str, title: str, cwd: str) -> None:
    leaf = store / "acct" / "proj"
    leaf.mkdir(parents=True, exist_ok=True)
    (leaf / f"{sid}.json").write_text(json.dumps({
        "sessionId": sid, "cliSessionId": f"t-{sid}", "title": title, "cwd": cwd,
        "isArchived": False, "lastActivityAt": 1000}, ensure_ascii=False), encoding="utf-8")


def build_world(w: Path, cwd: str) -> dict:
    """Подложные копии приложения и хранилища — раскладка из шапки."""
    paths = {}
    for copy in ("appA", "appB", "appC"):
        exe = w / copy / "claude-code" / "2.1.0" / "b1" / "claude.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"")
        paths[f"exe{copy[-1]}"] = exe
    own = [(CUR, "ZZ-SELF"), ("local_roleA1", "ZZ-A1"), ("local_roleA2", "ZZ-A2")]
    for sid, title in own:
        session_file(w / "appA" / "claude-code-sessions", sid, title, cwd)
        session_file(w / "roamA" / "Claude" / "claude-code-sessions", sid, title, cwd)
    session_file(w / "appB" / "claude-code-sessions", "local_b1", "ZZ-B1", cwd)
    session_file(w / "roamF" / "Claude" / "claude-code-sessions", "local_f1", "ZZ-A1", cwd)
    session_file(w / "roamF" / "Claude" / "claude-code-sessions", "local_f2", "ZZ-F2", cwd)
    session_file(w / "half", "local_roleA1", "ZZ-A1", cwd)
    (w / "roamNone").mkdir()
    paths.update(
        storeA=w / "appA" / "claude-code-sessions",
        roamA=w / "roamA", roamF=w / "roamF", roamNone=w / "roamNone",
        storeRoamA=w / "roamA" / "Claude" / "claude-code-sessions",
        storeRoamF=w / "roamF" / "Claude" / "claude-code-sessions",
        half=w / "half")
    return paths


def build_db(container: Path) -> Path:
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.empty_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")
    con = sqlite3.connect(str(db))
    for role, sid in ROLES:
        con.execute("INSERT INTO roles (role, lifecycle) SELECT ?, 'alive' "
                    "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role=?)", (role, role))
        con.execute("DELETE FROM role_sessions WHERE role=?", (role,))
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source, "
                    "session_id) VALUES (?,?,datetime('now'),?,?,?)",
                    (role, f"{role} [000000]", "TEST", "self", sid))
    for role in SIGNAL_ROLES:
        con.execute("INSERT INTO roles (role, lifecycle) SELECT ?, 'alive' "
                    "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role=?)", (role, role))
        con.execute("DELETE FROM role_sessions WHERE role=?", (role,))
    con.commit()
    con.close()
    return db


def role_field(db: Path, role: str, field: str):
    con = sqlite3.connect(str(db))
    try:
        row = con.execute(f"SELECT {field} FROM role_sessions WHERE role = ?", (role,)).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def copy_tools(dest: Path, vnext_dir: Path, write_tool: Path) -> dict:
    """Испытуемые копии: проверка ролей и запись адреса — с соседями; записка — в свой каталог,
    помощник чтения хранилища рядом с ней явно (его зовут внутри функции)."""
    tools = dest / "tools"
    wtools = dest / "tools-w"
    guard = mezo_stand.copy_tool(vnext_dir / GUARD, tools)
    signal = mezo_stand.copy_tool(vnext_dir / "signal-templates.py", tools)
    write = mezo_stand.copy_tool(write_tool, wtools)
    shutil.copy2(write_tool.parent / MOD, wtools / MOD)
    return {"tools": tools, "wtools": wtools, "guard": guard, "signal": signal, "write": write,
            "origin": vnext_dir, "worigin": write_tool.parent}


def put_break(t: dict, label: str) -> None:
    _, target, old, new, _ = BREAKS[label]
    files = ([(t["tools"] / MOD, t["origin"]), (t["wtools"] / MOD, t["worigin"])] if target == MOD
             else [(t["tools"] / target, t["origin"])])
    for f, origin in files:
        text = f.read_text(encoding="utf-8")
        if text.count(old) != 1:
            # Чаще всего это копия СТАРШЕ приёмки: набор в режиме контура берёт записку из
            # установленных инструментов, и до установки выпуска там прежний модуль.
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку {label} вложить некуда — в {f.name} (копия из "
                     f"{origin}) образец найден {text.count(old)} раз; испытуемая копия старше "
                     f"этой приёмки — выпуск в этот каталог ещё не установлен?")
        f.write_text(text.replace(old, new), encoding="utf-8")


def run_cases(stand: Path, tag: str, t: dict, w: dict, say: bool) -> dict:
    """Все случаи на одной копии инструментов → {метка: (верно ли, подробность)}."""
    root = stand / tag
    container = root / "container"
    db = build_db(container)
    note = root / "note.md"
    note.write_text("проба приёмки: своё ли хранилище сессий", encoding="utf-8")

    def env(store=None, exe=None, host=None, appdata=None):
        e = mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8")
        e.pop("MEZO_SESSION_STORE", None)
        e["APPDATA"] = str(appdata if appdata is not None else w["roamNone"])
        if store is not None:
            e["MEZO_SESSION_STORE"] = str(store)
        if exe is not None:
            e["CLAUDE_CODE_EXECPATH"] = str(exe)
        if host is not None:
            e["CLAUDE_CODE_HOST_SESSION_ID"] = host
        return e

    def run(cmd, e):
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=e, cwd=str(root))
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    driver = root / "driver.py"
    driver.write_text(DRIVER, encoding="utf-8")

    def module(e):
        code, out = run([sys.executable, "-B", str(driver), str(t["tools"])], e)
        try:
            return json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return {"error": out.strip()[-300:], "code": code}

    def same(a, b) -> bool:
        return Path(str(a)).resolve() == Path(str(b)).resolve()

    out = {}
    m = module(env(store=w["storeRoamF"], exe=w["exeA"], host=CUR, appdata=w["roamA"]))
    out["М1"] = (same(m.get("path"), w["storeRoamF"]) and "переменная" in (m.get("source") or "")
                 and m.get("foreign") is True, m)
    m = module(env(exe=w["exeA"], host=CUR, appdata=w["roamF"]))
    out["М2"] = (same(m.get("path"), w["storeA"]) and "рядом с копией" in (m.get("source") or "")
                 and m.get("current_found") is True, m)
    m = module(env(exe=w["exeB"], host=CUR, appdata=w["roamA"]))
    out["М3"] = (same(m.get("path"), w["storeRoamA"]) and "запасной" in (m.get("source") or ""), m)
    m = module(env(host=CUR, appdata=w["roamF"]))
    out["М4"] = (same(m.get("path"), w["storeRoamF"]) and m.get("foreign") is True, m)
    m = module(env(exe=w["exeA"], appdata=w["roamF"]))
    out["М5"] = (same(m.get("path"), w["storeA"]) and m.get("current_found") is None
                 and "неизвестна" in (m.get("note") or ""), m)
    m = module(env(exe=w["exeA"], host="cloud_xyz", appdata=w["roamA"]))
    out["М6"] = (m.get("found") is True and m.get("current_found") is None
                 and m.get("foreign") is False, m)
    m = module(env(exe=w["exeC"], host=CUR, appdata=w["roamNone"]))
    out["М7"] = (m.get("found") is False and "каталога сессий нет" in (m.get("note") or ""), m)

    guard = [sys.executable, "-B", str(t["guard"]), "--db", str(db), "--soft"]
    code, txt = run(guard, env(exe=w["exeA"], host=CUR, appdata=w["roamF"]))
    out["Г1"] = (code == 0 and "✅" in txt and "рядом с копией приложения" in txt
                 and "текущая сессия в нём есть" in txt, f"код {code} · {txt.strip()[:220]}")
    code, txt = run(guard + ["--session-store", str(w["storeRoamF"])], env(host=CUR))
    out["Г2"] = (code == 1 and "НЕ НАШЕ" in txt and "НЕ НАЙДЕН" not in txt and "✅" not in txt,
                 f"код {code} · {txt.strip()[:220]}")
    code, txt = run(guard + ["--session-store", str(w["storeRoamF"])], env())
    out["Г3"] = (code == 0 and "НЕ НАЙДЕН НИ ОДИН из 3" in txt, f"код {code} · {txt.strip()[-220:]}")
    code, txt = run(guard + ["--session-store", str(w["half"])], env())
    out["Г4"] = (code == 0 and "находок 2 из 3" in txt and "НИ ОДИН" not in txt,
                 f"код {code} · {txt.strip()[-220:]}")
    code, txt = run(guard, env(exe=w["exeC"], host=CUR, appdata=w["roamNone"]))
    out["Г5"] = (code == 0 and "СВЕРИТЬ НЕЧЕМ" in txt and "запасной стандартный путь" in txt
                 and "рядом с копией приложения каталога сессий нет" in txt,
                 f"код {code} · {txt.strip()[-240:]}")

    write = [sys.executable, "-B", str(t["write"]), "--role", "ZZWRITER", "--db", str(db),
             "--to", "ZZA1", "--file", str(note)]
    code, txt = run(write + ["--again", "приёмка W1"], env(store=w["storeRoamF"], host=CUR))
    out["W1"] = (code == 0 and "НЕ сверена" in txt and "НЕ НАШЕ" in txt and "НЕДОСТИЖИМ" not in txt
                 and "OK #" in txt, f"код {code} · {txt.strip()[-260:]}")
    code, txt = run(write + ["--again", "приёмка W2"], env(exe=w["exeA"], host=CUR, appdata=w["roamF"]))
    out["W2"] = (code == 0 and "НЕДОСТИЖИМ" not in txt and "НЕ сверена" not in txt and "OK #" in txt,
                 f"код {code} · {txt.strip()[-260:]}")

    signal = [sys.executable, "-B", str(t["signal"]), "--db", str(db)]
    code, txt = run(signal + ["--role", "ZZS1", "--set-address", "ZZ-A1 [111111]", "--source", "self"],
                    env(store=w["storeRoamF"], host=CUR))
    sid = role_field(db, "ZZS1", "session_id")
    out["S1"] = (sid != "local_f1" and "local_f1" not in txt and "не подбираю" in txt,
                 f"код {code} · session_id={sid} · {txt.strip()[:200]}")
    code, txt = run(signal + ["--role", "ZZS2", "--set-address", "ZZ-A2 [222222]", "--session-id",
                              "local_roleA2", "--source", "self"], env(store=w["storeRoamF"], host=CUR))
    sid = role_field(db, "ZZS2", "session_id")
    out["S2"] = (code == 0 and sid == "local_roleA2" and "local_f1" not in txt and "НЕ НАЙДЕН" not in txt,
                 f"код {code} · session_id={sid} · {txt.strip()[:200]}")
    code, txt = run(signal + ["--role", "ZZS3", "--set-address", "ZZ-A1 [333333]", "--session-id",
                              "local_roleA1", "--source", "self"],
                    env(exe=w["exeA"], host=CUR, appdata=w["roamF"]))
    tid = role_field(db, "ZZS3", "transcript_id")
    out["S3"] = (code == 0 and tid == "t-local_roleA1", f"код {code} · transcript_id={tid}")
    code, txt = run(signal + ["--list"], env(store=w["storeRoamF"], host=CUR))
    head = [ln.strip() for ln in txt.splitlines() if "session_id свер" in ln][:1]
    out["S4"] = (code == 0 and "сверить нечем" in txt and "НЕ НАШЕ" in txt
                 and "такой сессии нет" not in txt,
                 f"код {code} · {(head[0] if head else txt.strip())[:220]}")
    # адресат ZZA1 — записки ему легли в W1 и W2, сигналу есть о чём говорить
    code, txt = run(signal + ["--role", "ZZWRITER", "--to", "ZZA1"], env(store=w["storeRoamF"], host=CUR))
    out["S5"] = (code == 0 and "ZZA1" in txt and "local_roleA1 нет" not in txt,
                 f"код {code} · «сессии … нет» в выводе: {'да' if 'local_roleA1 нет' in txt else 'нет'}")

    if say:
        for label, (verdict, detail) in out.items():
            print(f"{'✅' if verdict else '🔴'} {label} {quiet(TITLES[label])}")
            print(f"   {quiet(detail)}")
    return out


def quiet(detail) -> str:
    """Подробность без знаков вердикта: в ней печатается вывод САМИХ инструментов, и их ✅ и 🔴
    смешались бы со счётом вердиктов приёмки (набор ядра сравнивает число этих знаков)."""
    return str(detail).replace("✅", "[да]").replace("🔴", "[провал]")


TITLES = {
    "М1": "переменная сильнее копии приложения; контрольное слово судит и её",
    "М2": "без переменной — хранилище рядом с копией приложения, текущая сессия в нём",
    "М3": "рядом с копией текущей сессии нет, в стандартном месте есть — взято стандартное",
    "М4": "копии приложения нет, стандартное место чужое — признак «не наше»",
    "М5": "текущая сессия неизвестна, кандидатов два — первый по порядку",
    "М6": "номер текущей сессии не вида «local_…» — контрольное слово не судится",
    "М7": "хранилища нет нигде — «не найдено» и слова о копии приложения",
    "Г1": "проверка ролей, своё хранилище: «живы у всех», источник и контрольное слово названы",
    "Г2": "проверка ролей, чужое хранилище: «НЕ НАШЕ», код 1 и с --soft",
    "Г3": "проверка ролей, не найден ни один из 3 — своя строка",
    "Г4": "встречный к Г3: не найдены двое из трёх — строки «ни один» нет",
    "Г5": "проверка ролей, хранилища нет нигде: «сверить нечем» называет, где искали",
    "W1": "записка, чужое хранилище: «НЕ сверена», а не «НЕДОСТИЖИМ»",
    "W2": "записка, своё хранилище рядом с копией: адресат жив",
    "S1": "запись адреса, чужое хранилище: сессия по имени не подобрана",
    "S2": "запись адреса, чужое хранилище: нет отказа «НЕ НАЙДЕН» с чужим перечнем",
    "S3": "запись адреса, своё хранилище: номер записи разговора взят сам",
    "S4": "реестр адресов, чужое хранилище: «сверить нечем», а не «такой сессии нет»",
    "S5": "печать сигнала, чужое хранилище: нет предупреждения «сессии адресата нет»",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--old-pack", default=None,
                    help="обратный ход: корень пакета другой вершины (каталоги vnext/prototype и "
                         "scripts) — взять испытуемые инструменты оттуда и прогнать только случаи")
    a = ap.parse_args()

    stand = mezo_stand.new("bite-session-store-")
    world_root = stand / "world"
    world_root.mkdir()
    cwd_marker = stand / "clean" / "container"      # cwd сессий = каталог контура стенда
    w = build_world(world_root, str(cwd_marker))

    if a.old_pack:
        src = Path(a.old_pack)
        print(f"⚖️ обратный ход: испытуются инструменты пакета {src}")
        t = copy_tools(stand / "clean", src / "vnext" / "prototype", src / "scripts" / "write-message.py")
        res = run_cases(stand, "clean", t, w, say=True)
        red = [k for k, (v, _) in res.items() if not v]
        print(f"\nОБРАТНЫЙ ХОД: провалились {len(red)} из {len(res)}: {' '.join(red) or 'никто'}")
        return mezo_stand.finish(0)

    print(f"⚖️ испытуется: {mezo_target.label()} (записка) и {TOOLS_DIR} (проверка ролей, запись адреса)")
    t = copy_tools(stand / "clean", TOOLS_DIR, WRITE_TARGET)
    res = run_cases(stand, "clean", t, w, say=True)
    clean_red = {k for k, (v, _) in res.items() if not v}

    print("\nНАРОЧНЫЕ ПОЛОМКИ — каждая на своей копии, ждём провала ровно названных случаев:")
    breaks_ok = 0
    for number, (label, (what, _, _, _, expected)) in enumerate(BREAKS.items(), start=1):
        tag = f"brk-{number}"                       # латиницей: путь уходит в подпроцессы
        tb = copy_tools(stand / tag, TOOLS_DIR, WRITE_TARGET)
        put_break(tb, label)
        # cwd сессий мира — каталог контура ЧИСТОГО прогона; у стенда поломки свой контур,
        # поэтому мир строится заново под его каталог
        wb_root = stand / f"world-{number}"
        wb_root.mkdir()
        wb = build_world(wb_root, str(stand / tag / "container"))
        rb = run_cases(stand, tag, tb, wb, say=False)
        red = {k for k, (v, _) in rb.items() if not v}
        exact = red == expected
        breaks_ok += exact
        print(f"{'✅' if exact else '🔴'} {label} {what}: провалились {' '.join(sorted(red)) or 'никто'}"
              f" · ждали {' '.join(sorted(expected))}")

    total = len(res)
    passed = total - len(clean_red)
    print(f"\n{'✅' if not clean_red and breaks_ok == len(BREAKS) else '🔴'} ИТОГ: случаев {passed} из "
          f"{total} · поломки {breaks_ok} из {len(BREAKS)}")
    return mezo_stand.finish(0 if not clean_red and breaks_ok == len(BREAKS) else 1)


if __name__ == "__main__":
    sys.exit(main())
