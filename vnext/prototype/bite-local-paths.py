# -*- coding: utf-8 -*-
"""bite-local-paths.py — приёмка файла путей контура (карточка #677, этап Э3, работы Р4 и Р5).

РЕШЕНИЕ ВЛАДЕЛЬЦА В3 а′ (2026-10-05 10:53 UTC, чат COORD): пути контура лежат в ОДНОМ файле
.mezosync/local/paths.json (JSON «ключ → путь», относительный путь считается от контейнера);
он заменил строки local.paths и ключи meta mirror_repo · template_checkout · disk_layer_tool.
Нет файла или ключа — инструмент отказывает или пропускает работу СЛОВАМИ, а не берёт литерал.

ЧТО ПРОВЕРЯЕТСЯ — по местам, где поведение сменилось (каждое место — свои случаи и своя поломка):
  чтение файла (mezo_paths.local_path)   R1–R8  четыре разных исхода · прежние источники не читаются
                                                  как значение · подсказка с готовой командой переноса
  поиск корня (mezo_root/container_root) M1–M7  файл путей — третий источник · MEZO_CONTAINER без базы —
                                                  громкий отказ · стенд со своей базой не уходит в чужую
  приложения правил (annex_dir)          A1–A3  ключ annex_dir · стандартная раскладка без литерала
  шаг переноса (20261005-local-paths-file.py)
                                         S1–S6  холостой прогон не пишет · из meta · из local.paths ·
                                                  раскладка автора только при каталоге на диске ·
                                                  повтор не переписывает · прежние источники целы
  backup-db.py                           B1–B6  зеркало из файла · файл путей едет в копию · строка,
                                                  когда его нет · литерала нет · восстановление названо
  guard-scripts-drift.py                 D1–D5  «зеркало не объявлено» без литерала · объявленное
                                                  сверяется · битый файл — не молчание · образец из файла
  rules-from-pack.py                     P1–P2  template_checkout из файла · прежняя запись meta не читается
  девять инструментов, читавших впечатанный путь (карточка #677, Э3-Р4, заявка №29 пакета, часть 2) —
  у каждого два случая: L<n> «контур с другой раскладкой / без ключа / без файла путей, а на диске лежит
  приманка — раскладка автора» и L<n>w «слова: нет файла · нет ключа · объявлено, а на диске нет · файл
  не читается — РАЗНЫЕ»:
  check-rules-mirror.py (обе копии)      L1 L1w  каталог координации: ключ coordination_dir
  export-rules.py                        L2 L2w  куда пишется файл правил: ключ coordination_dir
  export-channels.py                     L3 L3w  готовые файлы каналов: ключ generated_dir
  write-message.py                       L4 L4w  каталог каналов (default_md_dir): ключ coordination_dir
  guard-command-targets.py               L5 L5w  каталог промптов: ключ prompts_dir
  guard-stub-expectations.py             L6 L6w  исходники портала: ключ spa_src (стандартного места нет)
  read-phoenix.py                        L7 L7w  сборщик слоя диска: ключ disk_layer_tool
  guard-printed-forms.py                 L8 L8w  каталог готовых файлов каналов: ключ generated_dir
  measure-rhythm.py                      L9 L9w  каталог записей разговоров: ключ chat_records (иначе выводится)
  режим «--break all» (обвязка самой приёмки)
                                         E      среда дочерних вызовов позволяет им найти испытуемый
                                                  каталог (05.10: с пустым стендом вместо контура все 37
                                                  поломок разом отвечали «в испытуемом каталоге нет
                                                  mezo_paths.py», а режим целиком ни разу не гоняли)
  K  контроль: приёмке было что запускать (не различающий случай)

⚖️ ПОЧЕМУ mezo_root ОСТАВЛЕН «ПРИЗНАК ПЕРВЫМ» (случай M4 держит это нарочной поломкой). Записанный
порядок поиска корня — среда · признак · файл путей · отказ — выполняется у container_root. У mezo_root
признак (база рядом по дереву каталогов) стоит ПЕРВЫМ: инструмент, лежащий на стенде, берёт базу стенда,
даже если вызывающий унаследовал MEZO_CONTAINER живого контура (урок 13.09: копия приёмки записала в
живую базу). Замер 2026-10-05: через mezo_root без --db ходят 45 файлов (resolve_db) и ещё 4 боевых
инструмента; приёмки, не закрепляющие среду за стендом, — 139 вызовов в 87 файлах (реестр
acceptance-env-debt.txt). Порядок «среда первой» там увёл бы стенд в живую базу.

Живой контур не трогается: каждый случай — свой временный каталог (mezo_stand.new), база в нём —
маленькая подставная, инструменты — копии, среда — mezo_stand.stand_env. Рабочий каталог вызова — стенд.

Нарочная поломка (--break ИМЯ; --porcha — синоним; --break all — все подряд) вкладывается в КОПИЮ
испытуемого файла в стенде; ожидание — провал РОВНО названных случаев, не больше и не меньше.
Поломка «вернуть литерал / прежний источник» у каждого места своя. Единственная поломка, живущая в самой
приёмке, а не в копии испытуемого файла, — all-env-empty-stand: испытуемое место там — обвязка режима
all (all_breaks_container), её и возвращают к прежнему виду. Случаи, зависящие от того же
кода, что и чужая поломка, нарочно строятся так, чтобы её не замечать (абсолютные пути у потребителей,
не-объект вместо битого JSON), иначе одна поломка краснила бы несколько случаев разом.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402,F401 — вызывающий должен найтись так же, как у соседей
import mezo_stand  # noqa: E402
import mezo_target  # noqa: E402

STEP_NAME = "20261005-local-paths-file.py"
DECLARED, NOT_DECLARED, NO_FILE, UNREADABLE = "declared", "not_declared", "no_file", "unreadable"
MIRROR_LITERAL = "atlas.agents-sync.db"     # имя из прежнего кода: в приёмке — только как ловушка


class NotRun(Exception):
    """Приёмка не смогла начаться (поломку некуда вложить и т. п.) — не «сломано» и не «зелено»."""


# ── НАРОЧНЫЕ ПОЛОМКИ: имя → (файл-цель, [(образец, замена)…], {случаи, что обязаны провалиться}, что ломаем) ──
# Образец обязан встретиться в файле РОВНО раз — иначе приёмка отказывается начинаться.
_NL = "\\n"      # в исходнике испытуемого файла стоит сочетание «обратная косая + n» — два знака
BREAKS = {
    # ── чтение файла ──────────────────────────────────────────────────────────────────────────────
    "rel-from-cwd": ("mezo_paths.py", [(
        "            p = found.parent.parent.parent / p     # <контейнер> = над каталогом .mezosync",
        "            p = Path.cwd() / p")], {"R1"},
        "относительный путь считается от текущего каталога, а не от контейнера"),
    "exists-always-true": ("mezo_paths.py", [(
        "        there = p.exists()", "        there = True")], {"R2"},
        "«на диске есть» говорится всегда"),
    "not-declared-as-no-file": ("mezo_paths.py", [(
        "            return LocalPath(LOCAL_NOT_DECLARED, key, None, None, found,",
        "            return LocalPath(LOCAL_NO_FILE, key, None, None, found,")], {"R3"},
        "«ключа нет» отвечается как «файла нет»"),
    "no-file-as-not-declared": ("mezo_paths.py", [(
        "            return LocalPath(LOCAL_NO_FILE, key, None, None, first,",
        "            return LocalPath(LOCAL_NOT_DECLARED, key, None, None, first,")], {"R4"},
        "«файла нет» отвечается как «ключа нет»"),
    "unreadable-as-not-declared": ("mezo_paths.py", [(
        "            return LocalPath(LOCAL_UNREADABLE, key, None, None, found," + "\n"
        '                             f"файл путей не читается: {found.as_posix()} — "' + "\n"
        '                             f"{e.__class__.__name__}: {e}", None)',
        "            return LocalPath(LOCAL_NOT_DECLARED, key, None, None, found, 'x', None)")], {"R5"},
        "битый JSON отвечается как «ключа нет»"),
    "legacy-meta-as-value": ("mezo_paths.py", [(
        "            return LocalPath(LOCAL_NO_FILE, key, None, None, first," + "\n"
        '                             f"файла путей нет: {first.as_posix()}{tail}",' + "\n"
        "                             _legacy_hint(key, cands))",
        "            _hint = _legacy_hint(key, cands)" + "\n"
        "            _val = _break_meta_value(key, cands)" + "\n"
        "            if _val:" + "\n"
        "                return LocalPath(LOCAL_DECLARED, key, Path(_val), Path(_val).exists(), first," + "\n"
        '                                 "объявлено: " + _val, _hint)' + "\n"
        "            return LocalPath(LOCAL_NO_FILE, key, None, None, first," + "\n"
        '                             f"файла путей нет: {first.as_posix()}{tail}", _hint)'),
        ("def local_path(key: str, script_file=None, mezo_dir=None) -> LocalPath:",
         "def _break_meta_value(key, cands):" + "\n"
         "    if key != 'mirror_repo':" + "\n"
         "        return None" + "\n"
         "    for c in cands:" + "\n"
         "        d = c.parent.parent / DB_NAME" + "\n"
         "        if d.is_file():" + "\n"
         "            con = sqlite3.connect(str(d))" + "\n"
         "            r = con.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()" + "\n"
         "            con.close()" + "\n"
         "            return r[0] if r else None" + "\n"
         "    return None" + "\n\n\n"
         "def local_path(key: str, script_file=None, mezo_dir=None) -> LocalPath:")], {"R6"},
        "ключ mirror_repo таблицы meta принимается за значение, когда файла путей нет"),
    "hint-dropped": ("mezo_paths.py", [(
        '                             f"файла путей нет: {first.as_posix()}{tail}",' + "\n"
        "                             _legacy_hint(key, cands))",
        '                             f"файла путей нет: {first.as_posix()}{tail}",' + "\n"
        "                             None)")], {"R7"},
        "подсказка с командой переноса не печатается"),
    "legacy-file-as-value": ("mezo_paths.py", [(
        "            return LocalPath(LOCAL_NO_FILE, key, None, None, first," + "\n"
        '                             f"файла путей нет: {first.as_posix()}{tail}",' + "\n"
        "                             _legacy_hint(key, cands))",
        "            _lv = _break_legacy_file_value(key)" + "\n"
        "            if _lv:" + "\n"
        "                return LocalPath(LOCAL_DECLARED, key, Path(_lv), Path(_lv).exists(), first," + "\n"
        '                                 "объявлено: " + _lv, None)' + "\n"
        "            return LocalPath(LOCAL_NO_FILE, key, None, None, first," + "\n"
        '                             f"файла путей нет: {first.as_posix()}{tail}",' + "\n"
        "                             _legacy_hint(key, cands))"),
        ("def local_path(key: str, script_file=None, mezo_dir=None) -> LocalPath:",
         "def _break_legacy_file_value(key):" + "\n"
         "    old = Path(__file__).resolve().parent / 'local.paths'" + "\n"
         "    if old.is_file():" + "\n"
         "        for line in old.read_text(encoding='utf-8').splitlines():" + "\n"
         "            if line.startswith(key + '='):" + "\n"
         "                return line.split('=', 1)[1].strip()" + "\n"
         "    return None" + "\n\n\n"
         "def local_path(key: str, script_file=None, mezo_dir=None) -> LocalPath:")], {"R8"},
        "строка container= прежнего local.paths принимается за значение"),
    # ── поиск корня ───────────────────────────────────────────────────────────────────────────────
    "container-file-ignored": ("mezo_paths.py", [(
        '    if loc_dir and _is_db_file(loc_dir / ".mezosync" / DB_NAME):' + "\n"
        "        return loc_dir",
        "    if False:" + "\n"
        "        return loc_dir")], {"M1"},
        "container_root не смотрит в файл путей"),
    "mezo-root-file-ignored": ("mezo_paths.py", [(
        "    for src in (Path(env) if env else None, loc_dir):",
        "    for src in (Path(env) if env else None,):")], {"M2"},
        "mezo_root не смотрит в файл путей"),
    "env-without-base-quiet": ("mezo_paths.py", [(
        "    paths_file = _paths_file_for_advice(loc, script_file)" + "\n"
        "    sys.exit(" + "\n"
        '        f"ERR: корень мезосинка НЕ НАЙДЕН',
        "    if env:" + "\n"
        "        return Path(env)" + "\n"
        "    paths_file = _paths_file_for_advice(loc, script_file)" + "\n"
        "    sys.exit(" + "\n"
        '        f"ERR: корень мезосинка НЕ НАЙДЕН')], {"M3"},
        "MEZO_CONTAINER без базы тихо возвращается как корень (так и рождается пустая база)"),
    "env-first-in-mezo-root": ("mezo_paths.py", [(
        "    p = Path(script_file).resolve().parent" + "\n"
        "    for cand in (p, *p.parents):" + "\n"
        "        if _is_db_file(cand / DB_NAME):" + "\n"
        "            return cand" + "\n"
        "    # ⛔ ГРОМКО",
        '    _e = os.environ.get("MEZO_CONTAINER")' + "\n"
        "    if _e:" + "\n"
        '        for _c in (Path(_e) / ".mezosync", Path(_e)):' + "\n"
        "            if _is_db_file(_c / DB_NAME):" + "\n"
        "                return _c" + "\n"
        "    p = Path(script_file).resolve().parent" + "\n"
        "    for cand in (p, *p.parents):" + "\n"
        "        if _is_db_file(cand / DB_NAME):" + "\n"
        "            return cand" + "\n"
        "    # ⛔ ГРОМКО")], {"M4"},
        "mezo_root слушает среду раньше признака: стенд уходит в базу, названную средой"),
    "mezo-root-words-dropped": ("mezo_paths.py", [(
        "\n        + (f\"     {loc.words}" + _NL + "\" if loc.outcome == LOCAL_UNREADABLE else \"\")",
        "\n        + \"\"")], {"M5"},
        "отказ mezo_root не называет, что файл путей не читается"),
    "container-root-words-dropped": ("mezo_paths.py", [(
        "\n             + (f\"     {loc.words}" + _NL + "\" if loc.outcome == LOCAL_UNREADABLE else \"\")",
        "\n             + \"\"")], {"M6"},
        "отказ container_root не называет, что файл путей не читается"),
    "container-env-ignored": ("mezo_paths.py", [(
        "    if env:" + "\n"
        "        return Path(env)" + "\n"
        "    start = Path(script_file or __file__).resolve().parent" + "\n"
        "    for cand in (start, *start.parents):" + "\n"
        '        if _is_db_file(cand / ".mezosync" / DB_NAME):',
        "    if False:" + "\n"
        "        return Path(env)" + "\n"
        "    start = Path(script_file or __file__).resolve().parent" + "\n"
        "    for cand in (start, *start.parents):" + "\n"
        '        if _is_db_file(cand / ".mezosync" / DB_NAME):')], {"M7"},
        "container_root не слушает MEZO_CONTAINER первым"),
    # ── приложения правил ─────────────────────────────────────────────────────────────────────────
    "annex-file-ignored": ("mezo_paths.py", [(
        "    if res.outcome == LOCAL_DECLARED:" + "\n"
        "        return res.path" + "\n"
        "    if res.outcome == LOCAL_UNREADABLE:",
        "    if False:" + "\n"
        "        return res.path" + "\n"
        "    if res.outcome == LOCAL_UNREADABLE:")], {"A1"},
        "annex_dir не читает ключ из файла путей"),
    "annex-author-literal": ("mezo_paths.py", [(
        '    return root / "rules-annex"',
        '    return root.parent / "atlas.archs" / ".mezosync" / "rules-annex"')], {"A2"},
        "без ключа возвращается каталог раскладки автора, а не стандартный"),
    "annex-unreadable-quiet": ("mezo_paths.py", [(
        "    if res.outcome == LOCAL_UNREADABLE:" + "\n"
        '        sys.exit(f"ERR: место приложений правил не определено — {res.words}")',
        "    if False:" + "\n"
        '        sys.exit(f"ERR: место приложений правил не определено — {res.words}")')], {"A3"},
        "битый файл путей молча даёт стандартное место приложений"),
    # ── шаг переноса ──────────────────────────────────────────────────────────────────────────────
    "step-dry-writes": (STEP_NAME, [(
        "    if not a.apply:" + "\n"
        '        print("' + _NL + "🔍 ХОЛОСТОЙ",
        "    if False:" + "\n"
        '        print("' + _NL + "🔍 ХОЛОСТОЙ")], {"S1"},
        "холостой прогон пишет файл"),
    "step-skip-meta": (STEP_NAME, [(
        "        for key in META_KEYS:" + "\n"
        "            try:" + "\n"
        '                row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()',
        "        for key in ():" + "\n"
        "            try:" + "\n"
        '                row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()')],
        {"S2"}, "ключи таблицы meta не переносятся"),
    "step-skip-local-paths": (STEP_NAME, [(
        "    for path, label in old_files:" + "\n"
        "        if not path.is_file():",
        "    for path, label in []:" + "\n"
        "        if not path.is_file():")], {"S3"},
        "строки прежнего local.paths не переносятся"),
    "step-layout-without-disk": (STEP_NAME, [(
        "        if (container / rel).is_dir():" + "\n"
        "            entries[key] = rel",
        "        if True:" + "\n"
        "            entries[key] = rel")], {"S4"},
        "каталоги раскладки автора вписываются, даже когда их на диске нет"),
    "step-rewrites": (STEP_NAME, [(
        "    if target.exists():" + "\n"
        "        try:" + "\n"
        "            have = json.loads(",
        "    if False:" + "\n"
        "        try:" + "\n"
        "            have = json.loads(")], {"S5"},
        "повтор переписывает файл вместо «уже перенесено»"),
    "step-deletes-old": (STEP_NAME, [(
        '    print(f"' + _NL + "✅ ЗАПИСАНО: {target.as_posix()}",
        "    for _p, _l in old_files:" + "\n"
        "        if _p.is_file():" + "\n"
        "            _p.unlink()" + "\n"
        '    print(f"' + _NL + "✅ ЗАПИСАНО: {target.as_posix()}")], {"S6"},
        "шаг удаляет прежний local.paths"),
    # ── backup-db.py ──────────────────────────────────────────────────────────────────────────────
    "backup-mirror-ignored": ("backup-db.py", [(
        "    if res.outcome == mezo_paths.LOCAL_DECLARED and res.exists:" + "\n"
        '        return res.path / "mezosync.dump.sql", f"зеркало из файла путей: {res.path.as_posix()}"',
        "    if False:" + "\n"
        '        return res.path / "mezosync.dump.sql", f"зеркало из файла путей: {res.path.as_posix()}"')],
        {"B1"}, "объявленное зеркало игнорируется"),
    "backup-no-paths-copy": ("backup-db.py", [(
        '    tmp = dst.with_name(dst.name + ".tmp")' + "\n"
        "    tmp.write_bytes(res.file.read_bytes())" + "\n"
        "    os.replace(tmp, dst)" + "\n",
        "    pass" + "\n")], {"B2"},
        "файл путей в копию не кладётся"),
    "backup-absent-refuses": ("backup-db.py", [(
        '        return "файла путей нет — в копию не попал"',
        '        raise SystemExit("⛔ файла путей нет")')], {"B3"},
        "нет файла путей — отказ вместо строки"),
    "backup-literal-name": ("backup-db.py", [(
        '    fallback = db_path.parent / "backups" / "mezosync.dump.sql"',
        '    fallback = db_path.parent.parent / "atlas.agents-sync.db" / "mezosync.dump.sql"')], {"B4"},
        "без объявленного зеркала выгрузка уходит в каталог с литералом"),
    "backup-restore-unnamed": ("backup-db.py", [(
        "    и положить <зеркало>/local-paths.json как <контейнер>/.mezosync/local/paths.json —",
        "    и всё —")], {"B5"},
        "шапка не называет, как восстановить файл путей"),
    "backup-dry-copies": ("backup-db.py", [(
        "    if not apply:" + "\n"
        '        return f"файл путей {res.file.as_posix()} попадёт',
        "    if False:" + "\n"
        '        return f"файл путей {res.file.as_posix()} попадёт')], {"B6"},
        "без --apply файл путей всё равно копируется"),
    # ── guard-scripts-drift.py ────────────────────────────────────────────────────────────────────
    "drift-literal-default": ("guard-scripts-drift.py", [(
        '    return (path / "scripts") if path is not None else None',
        '    return (path / "scripts") if path is not None else (' + "\n"
        '        RUNTIME.parent.parent / "atlas.agents-sync.db" / "scripts"' + "\n"
        '        if (_MIRROR is None or _MIRROR.outcome != "unreadable") else None)')], {"D1"},
        "без объявленного зеркала берётся каталог с литералом"),
    "drift-declaration-ignored": ("guard-scripts-drift.py", [(
        '        path = _MIRROR.path if _MIRROR.outcome == "declared" else None',
        "        path = None")], {"D2"},
        "объявленное зеркало игнорируется"),
    "drift-unreadable-quiet": ("guard-scripts-drift.py", [(
        '        if _MIRROR is not None and _MIRROR.outcome == "unreadable":' + "\n"
        '            print("⚠️ зеркало не определено',
        "        if False:" + "\n"
        '            print("⚠️ зеркало не определено')], {"D3"},
        "битый файл путей выдаётся за «не объявлено»"),
    "drift-template-words-meta": ("guard-scripts-drift.py", [(
        '"не объявлена (ключ `template_checkout` в файле путей).")',
        '"не объявлена (запись `template_checkout` в meta).")')], {"D4"},
        "текст про образец снова отсылает к таблице meta"),
    "drift-template-ignored": ("guard-scripts-drift.py", [(
        '    VNEXT_TEMPLATE = (_TEMPLATE.path / "vnext" / "prototype"' + "\n"
        '                      if _TEMPLATE.outcome == "declared" else None)',
        "    VNEXT_TEMPLATE = None")], {"D5"},
        "объявленный образец игнорируется"),
    # ── rules-from-pack.py ────────────────────────────────────────────────────────────────────────
    "pack-file-ignored": ("rules-from-pack.py", [(
        "    if checkout.outcome == mezo_paths.LOCAL_DECLARED and checkout.exists:" + "\n"
        "        return checkout.path",
        "    if False:" + "\n"
        "        return checkout.path")], {"P1"},
        "template_checkout из файла путей не читается"),
    "pack-meta-fallback": ("rules-from-pack.py", [(
        "    src_row = conn.execute(\"SELECT value FROM meta WHERE key='template_source'\").fetchone()",
        "    _old = conn.execute(\"SELECT value FROM meta WHERE key='template_checkout'\").fetchone()" + "\n"
        "    if _old and _old[0] and Path(_old[0]).is_dir():" + "\n"
        "        return Path(_old[0])" + "\n"
        "    src_row = conn.execute(\"SELECT value FROM meta WHERE key='template_source'\").fetchone()")],
        {"P2"}, "прежняя запись meta берётся запасным значением"),
    # ── L: инструменты, читавшие впечатанный путь (карточка #677, Э3-Р4; заявка №29 пакета) ───────────
    # У каждого места: «вернуть литерал» (валит L<n> — случай с приманкой) и «слить исходы»
    # (валит L<n>w — случай со словами). Образец вложен в КОПИЮ инструмента в стенде.
    # ── check-rules-mirror.py (обе копии: рядом со скриптами и в vnext-tools) ─────────────────────
    "mirror-literal": ("check-rules-mirror.py", [(
        '    if place.outcome == mezo_paths.LOCAL_DECLARED:' + "\n"
        '        found.append(place.path / "sync.rules.md")' + "\n",
        '    found.append(mezo.parent / "atlas.archs" / ".mezosync" / "coordination" / "sync.rules.md")' + "\n")],
        {"L1"}, "файл-зеркало ищется в раскладке автора, а не в каталоге из файла путей"),
    "mirror-unreadable-quiet": ("check-rules-mirror.py", [(
        '    if not args.file and place.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '    if False:' + "\n")], {"L1w"},
        "файл путей, который не читается, не останавливает поиск зеркала"),
    "mirror-words-fixed": ("check-rules-mirror.py", [(
        '        print(f"   каталог координации: {place.words}")' + "\n",
        '        print("   каталог координации: не объявлено")' + "\n")], {"L1w"},
        "отказ называет каталог координации одной и той же фразой при любом исходе"),
    # ── export-rules.py ───────────────────────────────────────────────────────────────────────────
    "export-rules-literal": ("export-rules.py", [(
        '    res = mezo_paths.local_path("coordination_dir", mezo_dir=root)' + "\n",
        '    legacy = root.parent / "atlas.archs" / ".mezosync" / "coordination"' + "\n"
        '    if legacy.is_dir():' + "\n"
        '        return legacy / "sync.rules.md"' + "\n"
        '    res = mezo_paths.local_path("coordination_dir", mezo_dir=root)' + "\n")], {"L2"},
        "файл правил пишется в раскладку автора, когда её каталог есть на диске"),
    "export-rules-unreadable-quiet": ("export-rules.py", [(
        '    if res.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '    if False:' + "\n")], {"L2w"},
        "файл путей, который не читается, молча заменяется стандартным местом"),
    "export-rules-declared-silent": ("export-rules.py", [(
        '            print(f"ℹ️ {_place.words} — каталог будет создан")' + "\n",
        '            pass' + "\n")], {"L2w"},
        "«объявлено, а каталога на диске нет» не говорится вслух"),
    # ── export-channels.py ────────────────────────────────────────────────────────────────────────
    "channels-literal": ("export-channels.py", [(
        '    res = mezo_paths.local_path("generated_dir", mezo_dir=mezo)' + "\n",
        '    _archs = mezo.parent / "atlas.archs" / ".mezosync" / "coordination" / "generated"' + "\n"
        '    if _archs.parent.parent.is_dir():' + "\n"
        '        return _archs, None' + "\n"
        '    res = mezo_paths.local_path("generated_dir", mezo_dir=mezo)' + "\n")], {"L3"},
        "готовые файлы каналов уходят в раскладку автора, когда её каталог есть на диске"),
    "channels-unreadable-quiet": ("export-channels.py", [(
        '    if res.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '    if False:' + "\n")], {"L3w"},
        "файл путей, который не читается, молча заменяется стандартным местом"),
    "channels-declared-silent": ("export-channels.py", [(
        '        return res.path, (None if res.exists else f"{res.words} — каталог будет создан")' + "\n",
        '        return res.path, None' + "\n")], {"L3w"},
        "«объявлено, а каталога на диске нет» не говорится вслух"),
    # ── write-message.py ──────────────────────────────────────────────────────────────────────────
    "message-literal": ("write-message.py", [(
        '    res = mezo_paths.local_path("coordination_dir", mezo_dir=mezo)' + "\n",
        '    _lit = mezo.parent.joinpath("atlas.archs", ".mezosync", "coordination")' + "\n"
        '    if _lit.is_dir():' + "\n"
        '        return _lit' + "\n"
        '    res = mezo_paths.local_path("coordination_dir", mezo_dir=mezo)' + "\n")], {"L4"},
        "каталог каналов — раскладка автора, когда её каталог есть на диске"),
    "message-unreadable-quiet": ("write-message.py", [(
        '    if res.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '    if False:' + "\n")], {"L4w"},
        "файл путей, который не читается, молча заменяется стандартным местом"),
    # ── guard-command-targets.py ──────────────────────────────────────────────────────────────────
    "targets-literal": ("guard-command-targets.py", [(
        '    res = mezo_paths.local_path("prompts_dir", mezo_dir=mezo)' + "\n",
        '    _guess = mezo.parent / "atlas.archs" / ".mezosync" / "prompts"' + "\n"
        '    if _guess.is_dir():' + "\n"
        '        return _guess, None, False' + "\n"
        '    res = mezo_paths.local_path("prompts_dir", mezo_dir=mezo)' + "\n")], {"L5"},
        "промпты берутся из раскладки автора, когда её каталог есть на диске"),
    "targets-unreadable-quiet": ("guard-command-targets.py", [(
        '    if res.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '    if False:' + "\n")], {"L5w"},
        "файл путей, который не читается, не останавливает проверку"),
    "targets-declared-silent": ("guard-command-targets.py", [(
        '        return None, f"⚠️ каталог промптов: {res.words} — промпты не сверялись", False' + "\n",
        '        return None, None, False' + "\n")], {"L5w"},
        "«объявлено, а каталога на диске нет» не говорится вслух"),
    "targets-not-declared-silent": ("guard-command-targets.py", [(
        '    return None, (f"ℹ️ каталог промптов: {res.words}; стандартного каталога "' + "\n"
        '                  f"{standard.as_posix()} на диске нет — промпты не сверялись "' + "\n"
        '                  f"(свойство контура, не долг)"), False' + "\n",
        '    return None, None, False' + "\n")], {"L5w"},
        "«не объявлено» молчит: промпты не сверены, а об этом ни слова"),
    # ── guard-stub-expectations.py ────────────────────────────────────────────────────────────────
    "stub-literal": ("guard-stub-expectations.py", [(
        '    SPA_PLACE = mezo_paths.local_path("spa_src", __file__)' + "\n"
        '    if SPA_PLACE.outcome != mezo_paths.LOCAL_DECLARED or not SPA_PLACE.exists:' + "\n"
        '        return None, []' + "\n"
        '    SPA_SRC = SPA_PLACE.path' + "\n",
        '    SPA_PLACE = mezo_paths.local_path("spa_src", __file__)' + "\n"
        '    SPA_SRC = (Path(__file__).resolve().parent.parent.parent / "atlas.studio" / "Src"' + "\n"
        '               / "Atlas.Studio.Spa" / "src")' + "\n"
        '    if not SPA_SRC.exists():' + "\n"
        '        return None, []' + "\n")], {"L6"},
        "исходники портала берутся из раскладки автора, а не из файла путей"),
    "stub-unreadable-quiet": ("guard-stub-expectations.py", [(
        '        if place.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '        if False:' + "\n")], {"L6w"},
        "файл путей, который не читается, выдаётся за «портала нет»"),
    "stub-declared-as-property": ("guard-stub-expectations.py", [(
        '        if place.outcome == mezo_paths.LOCAL_DECLARED:' + "\n",
        '        if False:' + "\n")], {"L6w"},
        "«объявлено, а каталога нет» говорится как «свойство контура»"),
    "stub-not-declared-silent": ("guard-stub-expectations.py", [(
        '            print(f"⏭️ исходники портала: {place.words} — свойство контура (портала у него "' + "\n"
        '                  f"нет), а не долг; проверка пропущена, НЕ зелёная")' + "\n",
        '            pass' + "\n")], {"L6w"},
        "«не объявлено» молчит: проверка пропущена, а об этом ни слова"),
    # ── read-phoenix.py ───────────────────────────────────────────────────────────────────────────
    "phoenix-literal": ("read-phoenix.py", [(
        '            _disk = str(_loc.path) if _loc.outcome == mezo_paths.LOCAL_DECLARED else None' + "\n",
        '            _disk = str(mezo_paths.container_root(__file__) / (str(_loc.path) if'
        ' _loc.outcome == mezo_paths.LOCAL_DECLARED else'
        ' "atlas.archs/step04_opssre/tools/disk_layer.py"))' + "\n")], {"L7"},
        "сборщик слоя диска берётся из раскладки автора, когда ключа нет"),
    "phoenix-unreadable-quiet": ("read-phoenix.py", [(
        '                elif _loc.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '                elif False:' + "\n")], {"L7w"},
        "файл путей, который не читается, выдаётся за «слой диска не объявлен»"),
    "phoenix-declared-as-not": ("read-phoenix.py", [(
        '                if _loc.outcome == mezo_paths.LOCAL_DECLARED:' + "\n",
        '                if False:' + "\n")], {"L7w"},
        "«путь объявлен, а файла нет» говорится как «слой диска не объявлен»"),
    "phoenix-hint-dropped": ("read-phoenix.py", [(
        '                    if _loc.hint:' + "\n",
        '                    if False:' + "\n")], {"L7w"},
        "подсказка о прежнем источнике (запись в meta) не печатается"),
    # ── guard-printed-forms.py ────────────────────────────────────────────────────────────────────
    "forms-literal": ("guard-printed-forms.py", [(
        '    res = mezo_paths.local_path("generated_dir", mezo_dir=mezo)' + "\n",
        '    return (mezo.parent / "atlas.archs" / ".mezosync" / "coordination" / "generated",' + "\n"
        '            mezo_paths.local_path("generated_dir", mezo_dir=mezo))' + "\n"
        '    res = mezo_paths.local_path("generated_dir", mezo_dir=mezo)' + "\n")], {"L8"},
        "готовые файлы каналов ищутся в раскладке автора при любом файле путей"),
    "forms-unreadable-quiet": ("guard-printed-forms.py", [(
        '        if art_place.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '        if False:' + "\n")], {"L8w"},
        "файл путей, который не читается, не останавливает суд"),
    "forms-declared-silent": ("guard-printed-forms.py", [(
        '            print(f"⚠️ каталог готовых файлов каналов: {art_place.words} — файлы из базы НЕ проверены")' + "\n",
        '            pass' + "\n")], {"L8w"},
        "«объявлено, а каталога на диске нет» не говорится вслух"),
    "forms-not-declared-silent": ("guard-printed-forms.py", [(
        '            print(f"ℹ️ каталог готовых файлов каналов: {art_place.words}; стандартного каталога "' + "\n"
        '                  f"{art_dir.as_posix()} на диске нет — файлы из базы НЕ проверены "' + "\n"
        '                  f"(свойство контура, не долг)")' + "\n",
        '            pass' + "\n")], {"L8w"},
        "«не объявлено» молчит: файлы из базы не проверены, а об этом ни слова"),
    # ── measure-rhythm.py ─────────────────────────────────────────────────────────────────────────
    "rhythm-literal": ("measure-rhythm.py", [(
        '    return (ПАПКА_ПРОЕКТОВ / имя,' + "\n",
        '    return (ПАПКА_ПРОЕКТОВ / "C--guts--atlas",' + "\n")], {"L9"},
        "каталог записей — имя папки контура-автора, а не выведенное из пути контейнера"),
    "rhythm-unreadable-quiet": ("measure-rhythm.py", [(
        '    if res.outcome == mezo_paths.LOCAL_UNREADABLE:' + "\n",
        '    if False:' + "\n")], {"L9w"},
        "файл путей, который не читается, выдаётся за «ключа нет» и мерка идёт по выведенному"),
    "rhythm-derived-silent": ("measure-rhythm.py", [(
        '        print(f"ℹ️ {пояснение}")' + "\n",
        '        pass' + "\n")], {"L9w"},
        "вывод каталога записей из пути контейнера делается молча"),
    # ── обвязка самой приёмки: файла-цели нет (пустая строка), поломка — переключатель SELF_BREAK ────
    "all-env-empty-stand": ("", [], {"E"},
                            "дочерним вызовам режима all вместо контура отдаётся пустой стенд"),
}

OK = FAIL = 0
FAILED = []
SELF_BREAK = None       # имя поломки, живущей в самой приёмке (у неё нет файла-цели); см. all_breaks_container


def case(mark, name, cond, detail="", differ=True):
    global OK, FAIL
    print(("✅" if cond else "🔴"), mark, name)
    if detail and not cond:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1
        if differ:
            FAILED.append(mark)


def marker_db(path: Path) -> None:
    """База-признак стенда: НАСТОЯЩИЙ файл SQLite (заголовок 4096 байт), а не пустышка 0 байт.

    С 06.10 (починка (б), карточка #678) пустой mezosync.db признаком контура не служит: голое
    sqlite3.connect(...).close() оставляет ровно такую пустышку, и поиск корня проходит мимо неё.
    Так приёмка провалила M1 M2, а M4 прошёл бы и на своей поломке: пустая «чужая» база
    пропускалась, и поиск возвращался к своей. Запись user_version пишет заголовок файла."""
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA user_version = 1")
    con.close()


def same(a, b) -> bool:
    """Два пути — один и тот же (короткие имена Windows и регистр не мешают)."""
    try:
        return Path(a).resolve() == Path(b).resolve()
    except (OSError, ValueError, TypeError):
        return False


class Run:
    """Один прогон: корень стенда, испытуемые копии, нарочная поломка (если задана)."""

    def __init__(self, break_name):
        self.box = mezo_stand.new("bite-local-paths-")
        self.brk = BREAKS[break_name] if break_name else None
        # у поломки без файла-цели (обвязка самой приёмки) вкладывать нечего — она «легла» сразу
        self.patched = bool(self.brk) and not self.brk[0]
        self.scripts = self.box / "base" / ".mezosync" / "scripts"
        self.counter = 0
        self.src = {
            "mezo_paths.py": mezo_target.script("mezo_paths.py"),
            "backup-db.py": mezo_target.script("backup-db.py"),
            "guard-scripts-drift.py": mezo_target.script("guard-scripts-drift.py"),
            "rules-from-pack.py": mezo_target.script("rules-from-pack.py"),
        }
        self.step_src = mezo_target.migration(STEP_NAME)

    def patch(self, folder: Path):
        """Вложить нарочную поломку в копию файла-цели, если она лежит в этом каталоге."""
        if not self.brk or not self.brk[0]:
            return
        target, edits = self.brk[0], self.brk[1]
        f = folder / target
        if not f.exists():
            return
        text = f.read_text(encoding="utf-8")
        for old, new in edits:
            found = text.count(old)
            if found != 1:
                raise NotRun(f"⛔ НЕ ПРОВЕРЕНО: поломка вложена некуда — образец найден {found} раз в "
                             f"{target} (ждали ровно один): {old[:70]!r}")
            text = text.replace(old, new)
        f.write_text(text, encoding="utf-8")
        self.patched = True

    def build_base(self):
        """Общие копии: mezo_paths, backup-db, rules-from-pack (с соседями) и шаг переноса."""
        # Общие копии лежат В контейнере (у него своя база-признак, настоящий файл — marker_db): иначе
        # поломка порядка поиска корня краснила бы заодно всё, что запускается из этих копий, — не одну свою причину.
        self.scripts.mkdir(parents=True, exist_ok=True)
        marker_db(self.scripts.parent / "mezosync.db")
        for name in ("mezo_paths.py", "backup-db.py", "rules-from-pack.py"):
            mezo_stand.copy_tool(self.src[name], self.scripts)
        steps = self.scripts / "migrations"
        steps.mkdir(parents=True, exist_ok=True)
        mezo_stand.copy_tool(self.step_src, steps)
        self.patch(self.scripts)
        self.patch(steps)

    def tool_src(self, name: str, origin="scripts") -> Path:
        """Исходник испытуемого инструмента группы L. scripts — каталог скриптов испытуемого контура
        (MEZO_SCRIPTS_ROOT); vnext — каталог рядом с этой приёмкой (там живут инструменты второй группы)."""
        if origin == "scripts":
            return mezo_target.script(name)
        p = Path(__file__).resolve().parent / name
        if not p.is_file():
            raise NotRun(f"⛔ НЕ ПРОВЕРЕНО: рядом с приёмкой нет {name}")
        return p

    def case_dir(self, tag, meta=None, paths=None, raw=None, dirs=()):
        """Каталог случая: контейнер с .mezosync, маленькая подставная база с таблицей meta,
        файл путей (paths — словарь, raw — сырой текст) и пустые каталоги dirs."""
        self.counter += 1
        c = self.box / f"{self.counter:02d}-{tag}"
        mz = c / ".mezosync"
        mz.mkdir(parents=True)
        db = mz / "mezosync.db"
        con = sqlite3.connect(str(db))
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        for k, v in (meta or {}).items():
            con.execute("INSERT INTO meta (key, value) VALUES (?, ?)", (k, str(v)))
        con.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, body TEXT)")
        con.execute("INSERT INTO notes (body) VALUES ('проба')")
        con.commit()
        con.close()
        if paths is not None:
            (mz / "local").mkdir()
            (mz / "local" / "paths.json").write_text(
                json.dumps(paths, ensure_ascii=False, indent=2), encoding="utf-8")
        if raw is not None:
            (mz / "local").mkdir(exist_ok=True)
            (mz / "local" / "paths.json").write_text(raw, encoding="utf-8")
        for d in dirs:
            (c / d).mkdir(parents=True, exist_ok=True)
        return c, db

    def outside_dir(self, tag, paths=None, raw=None):
        """Каталог случая БЕЗ базы и без .mezosync: копия вне контейнера. Файл путей — рядом с
        каталогом скриптов (<скрипты>/../local/paths.json); сама «копия» — outside/x.py."""
        self.counter += 1
        c = self.box / f"{self.counter:02d}-{tag}"
        (c / "outside").mkdir(parents=True)
        if paths is not None or raw is not None:
            (c / "local").mkdir()
            body = raw if raw is not None else json.dumps(paths, ensure_ascii=False)
            (c / "local" / "paths.json").write_text(body, encoding="utf-8")
        return c, c / "outside" / "x.py"

    def py(self, container, args, drop_container=False, cwd=None, **extra):
        """Запуск интерпретатора со средой СТЕНДА; drop_container — как у копии вне контейнера."""
        env = mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                                   **extra)
        env.pop("MEZO_TEMPLATE", None)
        if drop_container:
            env.pop("MEZO_CONTAINER", None)
        p = subprocess.run([sys.executable, *[str(x) for x in args]], capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           cwd=str(cwd or container), env=env, timeout=240)
        return p.returncode, (p.stdout or "") + (p.stderr or "")

    def probe(self, container, body, drop_container=True, scripts=None, **extra):
        """Короткая программа поверх КОПИИ mezo_paths (импортируется как m)."""
        head = ("import sys, json, os\n"
                f"sys.path.insert(0, {str(scripts or self.scripts)!r})\n"
                "import mezo_paths as m\n")
        return self.py(container, ["-c", head + body], drop_container=drop_container, **extra)

    def local(self, container, key, script_rel=".mezosync/scripts/probe.py", scripts=None):
        """Исход чтения ключа файла путей — словарём (поля LocalPath)."""
        body = (f"r = m.local_path({key!r}, {str(container / script_rel)!r})\n"
                "print(json.dumps({'outcome': r.outcome, 'path': str(r.path) if r.path else None,"
                " 'exists': r.exists, 'words': r.words, 'hint': r.hint}, ensure_ascii=False))\n")
        # рабочий каталог — корень стенда, а не контейнер случая: относительный путь, посчитанный от
        # текущего каталога, не совпадёт с посчитанным от контейнера (на этом держится случай R1)
        rc, out = self.probe(container, body, scripts=scripts, cwd=self.box)
        try:
            return rc, json.loads(out.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return rc, {"outcome": None, "raw": out}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def pfile(c: Path) -> Path:
    return c / ".mezosync" / "local" / "paths.json"


# ═══ ГРУППА R: чтение файла путей ═════════════════════════════════════════════════════════════════
def group_reader(run: Run):
    abs_mirror = None
    # R1 объявлено, каталог есть: относительный путь считается ОТ КОНТЕЙНЕРА, не от текущего каталога
    c, _ = run.case_dir("r1", paths={"mirror_repo": "mirror"}, dirs=["mirror"])
    rc, r = run.local(c, "mirror_repo")
    case("R1", "объявлено, каталог есть: относительный путь — от контейнера",
         r["outcome"] == DECLARED and r.get("exists") is True and same(r.get("path"), c / "mirror"),
         f"код {rc} · {r}")
    # R2 объявлено, каталога нет
    c, _ = run.case_dir("r2", paths={"mirror_repo": "no-such-dir"})
    rc, r = run.local(c, "mirror_repo")
    case("R2", "объявлено, каталога на диске нет: исход «объявлено», слово «на диске НЕТ»",
         r["outcome"] == DECLARED and r.get("exists") is False and "на диске НЕТ" in (r.get("words") or ""),
         f"код {rc} · {r}")
    # R3 файл есть, ключа нет (и пустое значение — то же)
    c, _ = run.case_dir("r3", paths={"template": "x"})
    rc, r = run.local(c, "mirror_repo")
    c2, _ = run.case_dir("r3b", paths={"mirror_repo": ""})
    rc2, r2 = run.local(c2, "mirror_repo")
    case("R3", "файл есть, ключа нет (или значение пусто): «не объявлено»",
         r["outcome"] == NOT_DECLARED and "не объявлено" in (r.get("words") or "")
         and r2["outcome"] == NOT_DECLARED,
         f"{r} · пустое значение: {r2}")
    # R4 файла нет вовсе (в базе чисто — прежних источников нет)
    c, _ = run.case_dir("r4")
    rc, r = run.local(c, "mirror_repo")
    case("R4", "файла путей нет: исход «файла нет», подсказки нет",
         r["outcome"] == NO_FILE and "файла путей нет" in (r.get("words") or "") and not r.get("hint"),
         f"код {rc} · {r}")
    # R5 файл не читается: битый JSON и не-объект; наружу ничего не бросается (код 0)
    c, _ = run.case_dir("r5", raw="{oops")
    rc, r = run.local(c, "mirror_repo")
    c2, _ = run.case_dir("r5b", raw="[1, 2]")
    rc2, r2 = run.local(c2, "mirror_repo")
    case("R5", "файл не читается (битый JSON · не объект): исход «не читается», без исключения",
         rc == 0 and rc2 == 0 and r["outcome"] == UNREADABLE and "не читается" in (r.get("words") or "")
         and r2["outcome"] == UNREADABLE,
         f"битый JSON: код {rc} {r} · не объект: код {rc2} {r2}")
    # R6/R7 прежний источник (запись meta) несёт ключ, файла нет: значением не служит, подсказка есть
    abs_mirror = run.box / "old-mirror"
    abs_mirror.mkdir(exist_ok=True)
    c, _ = run.case_dir("r6", meta={"mirror_repo": str(abs_mirror)})
    rc, r = run.local(c, "mirror_repo")
    case("R6", "прежний источник (запись meta) значением НЕ служит: ключ не объявлен, пути нет",
         r["outcome"] not in (DECLARED, None) and r.get("path") is None,
         f"код {rc} · {r}")
    hint = r.get("hint") or ""
    case("R7", "прежний источник замечен: подсказка несёт готовую команду шага переноса",
         STEP_NAME in hint and "--apply" in hint and "mirror_repo" in hint and "больше не читается" in hint,
         f"подсказка: {hint!r}")
    # R8 прежний local.paths рядом с копией mezo_paths: значением не служит (своя копия, свои соседи)
    c, _ = run.case_dir("r8")
    own = c / ".mezosync" / "scripts"
    mezo_stand.copy_tool(run.src["mezo_paths.py"], own)
    run.patch(own)
    target = run.box / "old-container"
    (target / ".mezosync").mkdir(parents=True, exist_ok=True)
    (own / "local.paths").write_text(f"container={target}\n", encoding="utf-8")
    rc, r = run.local(c, "container", scripts=own)
    case("R8", "прежний local.paths (container=) значением НЕ служит: ключ не объявлен, пути нет",
         r["outcome"] not in (DECLARED, None) and r.get("path") is None,
         f"код {rc} · {r}")


# ═══ ГРУППА M: поиск корня ════════════════════════════════════════════════════════════════════════
def group_root(run: Run):
    # живой-подобный контейнер с базой: туда указывает файл путей / среда
    real = run.box / "real"
    (real / ".mezosync").mkdir(parents=True)
    marker_db(real / ".mezosync" / "mezosync.db")
    # M1 container_root, копия ВНЕ контейнера: файл путей рядом (третий источник) работает
    c, x = run.outside_dir("m1", paths={"container": str(real)})
    rc, out = run.probe(c, f"print(m.container_root({str(x)!r}))")
    case("M1", "container_root: ключ container файла путей работает (копия вне контейнера)",
         rc == 0 and same(out.strip().splitlines()[-1] if out.strip() else "", real), f"код {rc} · {out.strip()[-200:]}")
    # M2 mezo_root — то же
    rc, out = run.probe(c, f"print(m.mezo_root({str(x)!r}))")
    case("M2", "mezo_root: ключ container файла путей работает (копия вне контейнера)",
         rc == 0 and same(out.strip().splitlines()[-1] if out.strip() else "", real / ".mezosync"),
         f"код {rc} · {out.strip()[-200:]}")
    # M3 ВСТРЕЧНЫЙ: MEZO_CONTAINER указывает на каталог БЕЗ базы — громкий отказ, пустая база не рождается
    c, x = run.outside_dir("m3")
    bad = c / "empty-place"
    bad.mkdir()
    rc, out = run.probe(c, f"print(m.mezo_root({str(x)!r}))",
                        drop_container=False, MEZO_CONTAINER=str(bad))
    strays = list(c.rglob("mezosync.db"))
    case("M3", "встречный: MEZO_CONTAINER без базы — громкий отказ, пустая база не создана",
         rc != 0 and "задана, но" in out and "корень мезосинка НЕ НАЙДЕН" in out and not strays,
         f"код {rc} · {out.strip()[-240:]} · найденные базы: {strays}")
    # M4 стенд со СВОЕЙ базой не уходит в чужую, даже когда среда названа (урок 13.09)
    c, _ = run.case_dir("m4")
    other = run.box / "other-circuit"
    (other / ".mezosync").mkdir(parents=True, exist_ok=True)
    marker_db(other / ".mezosync" / "mezosync.db")
    rc, out = run.probe(c, f"print(m.mezo_root({str(c / '.mezosync' / 'scripts' / 'x.py')!r}))",
                        drop_container=False, MEZO_CONTAINER=str(other))
    got = out.strip().splitlines()[-1] if out.strip() else ""
    case("M4", "стенд со своей базой берёт СВОЮ, даже если среда называет чужой контур (признак первым)",
         rc == 0 and same(got, c / ".mezosync"), f"код {rc} · взято {got!r}, своё {c / '.mezosync'}")
    # M5 mezo_root: файл путей не читается — отказ называет это (не-объект, а не битый JSON: см. шапку)
    c, x = run.outside_dir("m5", raw="[1, 2]")
    rc, out = run.probe(c, f"print(m.mezo_root({str(x)!r}))")
    case("M5", "mezo_root: файл путей не читается — отказ называет причину словами",
         rc != 0 and "корень мезосинка НЕ НАЙДЕН" in out and "не читается" in out, f"код {rc} · {out.strip()[-300:]}")
    # M6 container_root — то же
    rc, out = run.probe(c, f"print(m.container_root({str(x)!r}))")
    case("M6", "container_root: файл путей не читается — отказ называет причину словами",
         rc != 0 and "контейнер группы НЕ НАЙДЕН" in out and "не читается" in out,
         f"код {rc} · {out.strip()[-300:]}")
    # M7 container_root: среда по-прежнему ПЕРВАЯ (норма не ослаблена)
    c, _ = run.case_dir("m7")
    rc, out = run.probe(c, f"print(m.container_root({str(c / '.mezosync' / 'scripts' / 'x.py')!r}))",
                        drop_container=False, MEZO_CONTAINER=str(other))
    got = out.strip().splitlines()[-1] if out.strip() else ""
    case("M7", "container_root: среда MEZO_CONTAINER по-прежнему первая (норма не ослаблена)",
         rc == 0 and same(got, other), f"код {rc} · взято {got!r}, ждали {other}")


# ═══ ГРУППА A: приложения правил ══════════════════════════════════════════════════════════════════
def group_annex(run: Run):
    c, db = run.case_dir("a1")
    mine = c / "my-annex"
    pfile(c).parent.mkdir(exist_ok=True)
    pfile(c).write_text(json.dumps({"annex_dir": str(mine)}), encoding="utf-8")
    rc, out = run.probe(c, f"print(m.annex_dir({str(db)!r}))")
    case("A1", "annex_dir: ключ annex_dir файла путей этой базы",
         rc == 0 and same(out.strip().splitlines()[-1] if out.strip() else "", mine), f"код {rc} · {out.strip()[-200:]}")
    c, db = run.case_dir("a2", paths={"template": "x"}, dirs=["atlas.archs/.mezosync/rules-annex"])
    rc, out = run.probe(c, f"print(m.annex_dir({str(db)!r}))")
    case("A2", "annex_dir: ключа нет — стандартное место рядом с базой, раскладка автора не подставляется",
         rc == 0 and same(out.strip().splitlines()[-1] if out.strip() else "", c / ".mezosync" / "rules-annex"),
         f"код {rc} · {out.strip()[-200:]}")
    c, db = run.case_dir("a3", raw="[1, 2]")
    rc, out = run.probe(c, f"print(m.annex_dir({str(db)!r}))")
    case("A3", "annex_dir: файл путей не читается — отказ словами, а не молчаливое стандартное место",
         rc != 0 and "место приложений правил не определено" in out, f"код {rc} · {out.strip()[-240:]}")


# ═══ ГРУППА S: шаг переноса ═══════════════════════════════════════════════════════════════════════
def readj(path: Path) -> dict:
    """Файл путей словарём; нет файла или не читается — пусто (случай тогда проваливается, а не падает)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def step(run: Run, c: Path, db: Path, apply: bool):
    args = [run.scripts / "migrations" / STEP_NAME, "--db", db] + (["--apply"] if apply else [])
    return run.py(c, args)


def old_local_paths(c: Path, text: str) -> Path:
    """Прежний local.paths рядом с инструментами контура случая (<контейнер>/.mezosync/scripts)."""
    folder = c / ".mezosync" / "scripts"
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / "local.paths"
    f.write_text(text, encoding="utf-8")
    return f


def group_step(run: Run):
    meta = {"mirror_repo": "mirror-x", "template_checkout": "tmpl-x", "disk_layer_tool": "tools/dl.py"}
    old_text = "container=/x/container\ntemplate=/x/template\n"
    # У каждого случая — ОБА прежних источника там, где поломка другого источника не должна ему мешать:
    # без этого «не переношу meta» оставило бы холостому прогону нечего показывать и покрасило бы лишнее.
    # S1 холостой прогон: файла нет, база не тронута
    c, db = run.case_dir("s1", meta=meta)
    old_local_paths(c, old_text)
    before = sha(db)
    rc, out = step(run, c, db, apply=False)
    case("S1", "холостой прогон: файла путей нет, база не тронута, сказано «ХОЛОСТОЙ»",
         rc == 0 and not pfile(c).exists() and sha(db) == before and "ХОЛОСТОЙ" in out,
         f"код {rc} · файл есть: {pfile(c).exists()} · {out.strip()[-200:]}")
    # S2 перенос из meta
    c, db = run.case_dir("s2", meta=meta)
    rc, out = step(run, c, db, apply=True)
    got = readj(pfile(c))
    case("S2", "перенос из таблицы meta: три ключа в файле равны записям",
         rc == 0 and all(got.get(k) == v for k, v in meta.items()), f"код {rc} · файл: {got} · {out.strip()[-200:]}")
    # S3 перенос из local.paths рядом с инструментами
    c, db = run.case_dir("s3")
    old_local_paths(c, old_text)
    rc, out = step(run, c, db, apply=True)
    got = readj(pfile(c))
    case("S3", "перенос из local.paths: container и template попали в файл",
         rc == 0 and got.get("container") == "/x/container" and got.get("template") == "/x/template",
         f"код {rc} · файл: {got} · {out.strip()[-200:]}")
    # S4 раскладка автора — только когда каталог ЕСТЬ на диске
    c, db = run.case_dir("s4", meta=meta, dirs=["atlas.archs/.mezosync/coordination"])
    old_local_paths(c, old_text)
    rc, out = step(run, c, db, apply=True)
    got = readj(pfile(c))
    c2, db2 = run.case_dir("s4b")
    rc2, out2 = step(run, c2, db2, apply=True)
    case("S4", "раскладка автора: ключ только при каталоге на диске; без каталогов файла нет вовсе",
         rc == 0 and got.get("coordination_dir") == "atlas.archs/.mezosync/coordination"
         and not any(k in got for k in ("spa_src", "prompts_dir", "generated_dir", "annex_dir"))
         and rc2 == 0 and not pfile(c2).exists(),
         f"код {rc} · файл: {got} · второй стенд: код {rc2}, файл есть: {pfile(c2).exists()}")
    # S5 повтор: «уже перенесено», файл (с допиской человека) не переписан
    c, db = run.case_dir("s5", meta=meta)
    old_local_paths(c, old_text)
    step(run, c, db, apply=True)
    data = readj(pfile(c))
    data["custom"] = "дописано человеком"
    pfile(c).parent.mkdir(exist_ok=True)
    pfile(c).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    kept = pfile(c).read_bytes()
    rc, out = step(run, c, db, apply=True)
    case("S5", "повтор: «уже перенесено», файл не переписан (допись человека цела)",
         rc == 0 and "уже перенесено" in out and pfile(c).read_bytes() == kept,
         f"код {rc} · {out.strip()[-200:]}")
    # S6 прежние источники целы и названы «больше не читаются»
    c, db = run.case_dir("s6", meta=meta)
    old = old_local_paths(c, old_text)
    rc, out = step(run, c, db, apply=True)
    con = sqlite3.connect(str(db))
    left = dict(con.execute("SELECT key, value FROM meta").fetchall())
    con.close()
    case("S6", "прежние источники НЕ удалены (meta и local.paths целы), шаг говорит «больше не читаются»",
         rc == 0 and old.is_file() and all(left.get(k) == v for k, v in meta.items())
         and "больше не читаются" in out, f"код {rc} · local.paths есть: {old.is_file()} · meta: {left}")


# ═══ ГРУППА B: backup-db.py ═══════════════════════════════════════════════════════════════════════
def backup(run: Run, c: Path, db: Path, *flags):
    return run.py(c, [run.scripts / "backup-db.py", "--db", db, *flags])


def group_backup(run: Run):
    # B1 зеркало — из файла путей (абсолютный путь: см. шапку)
    c, db = run.case_dir("b1", dirs=["mirror"])
    pfile(c).parent.mkdir(exist_ok=True)
    pfile(c).write_text(json.dumps({"mirror_repo": str(c / "mirror")}), encoding="utf-8")
    rc, out = backup(run, c, db, "--apply")
    case("B1", "зеркало из файла путей: выгрузка легла в объявленную папку",
         rc == 0 and (c / "mirror" / "mezosync.dump.sql").is_file(), f"код {rc} · {out.strip()[-300:]}")
    # B2 файл путей едет в копию рядом с выгрузкой
    c, db = run.case_dir("b2", paths={"mirror_repo": "somewhere"}, dirs=["o"])
    rc, out = backup(run, c, db, "--out", c / "o" / "dump.sql", "--apply")
    copy = c / "o" / "local-paths.json"
    case("B2", "файл путей скопирован рядом с выгрузкой под именем local-paths.json (байт в байт)",
         rc == 0 and (c / "o" / "dump.sql").is_file() and copy.is_file()
         and copy.read_bytes() == pfile(c).read_bytes(), f"код {rc} · {out.strip()[-300:]}")
    # B3 файла путей нет — строка, а не отказ
    c, db = run.case_dir("b3", dirs=["o"])
    rc, out = backup(run, c, db, "--out", c / "o" / "dump.sql", "--apply")
    case("B3", "файла путей нет: строка «в копию не попал», выгрузка записана, отказа нет",
         rc == 0 and "файла путей нет — в копию не попал" in out and (c / "o" / "dump.sql").is_file()
         and not (c / "o" / "local-paths.json").exists(), f"код {rc} · {out.strip()[-300:]}")
    # B4 зеркало не объявлено: запасное место рядом с базой, каталог-ловушка с прежним именем не тронут
    c, db = run.case_dir("b4", paths={"template": "x"}, dirs=[MIRROR_LITERAL])
    rc, out = backup(run, c, db, "--apply")
    case("B4", "зеркало не объявлено: выгрузка в <каталог базы>/backups, каталог с прежним именем не тронут",
         rc == 0 and (c / ".mezosync" / "backups" / "mezosync.dump.sql").is_file()
         and not (c / MIRROR_LITERAL / "mezosync.dump.sql").exists() and "не объявлено" in out,
         f"код {rc} · {out.strip()[-300:]}")
    # B5 шапка и справка называют восстановление, включая файл путей
    text = run.scripts.joinpath("backup-db.py").read_text(encoding="utf-8")
    head = text.split("ВОССТАНОВЛЕНИЕ", 1)[-1].split("ЗАПУСК:", 1)[0] if "ВОССТАНОВЛЕНИЕ" in text else ""
    rc, hlp = run.py(run.box, [run.scripts / "backup-db.py", "--help"])
    compact = re.sub(r"\s+", "", hlp)
    case("B5", "восстановление названо: шапка велит положить local-paths.json на место, справка его называет",
         re.search(r"положить<зеркало>/local-paths\.json", re.sub(r"\s+", "", head)) is not None
         and "local-paths.json" in compact and "sqlite3" in compact,
         f"шапка называет: {'local-paths.json' in head} · справка: {'local-paths.json' in compact}")
    # B6 без --apply ничего не пишется, но строка про файл путей есть
    c, db = run.case_dir("b6", paths={"mirror_repo": "somewhere"}, dirs=["o"])
    rc, out = backup(run, c, db, "--out", c / "o" / "dump.sql")
    case("B6", "без --apply: ни выгрузки, ни копии файла путей, строка «попадёт в копию» есть",
         rc == 0 and not (c / "o" / "local-paths.json").exists() and not (c / "o" / "dump.sql").exists()
         and "попадёт в копию" in out, f"код {rc} · {out.strip()[-300:]}")


# ═══ ГРУППА D: guard-scripts-drift.py ═════════════════════════════════════════════════════════════
def drift_stand(run: Run, tag, paths=None, raw=None, with_mirror=None, decoy=False):
    """Контейнер с копией инструмента в .mezosync/scripts; mirror — каталог зеркала (копия скриптов)."""
    c, _ = run.case_dir(tag, paths=paths, raw=raw)
    own = c / ".mezosync" / "scripts"
    mezo_stand.copy_tool(run.src["guard-scripts-drift.py"], own)
    run.patch(own)
    for place in ([with_mirror] if with_mirror else []) + ([MIRROR_LITERAL] if decoy else []):
        dst = c / place / "scripts"
        dst.mkdir(parents=True)
        for f in own.glob("*.py"):
            (dst / f.name).write_bytes(f.read_bytes())
    return c, own / "guard-scripts-drift.py"


def group_drift(run: Run):
    # D1 зеркало не объявлено (ключа нет · файла нет): свойство контура, код 0, имени-литерала нет
    c, tool = drift_stand(run, "d1", paths={"template": "x"}, decoy=True)
    rc, out = run.py(c, [tool])
    c2, tool2 = drift_stand(run, "d1b", decoy=True)
    rc2, out2 = run.py(c2, [tool2])
    line = "зеркало не объявлено — сверка копий пропущена (свойство контура)"
    case("D1", "зеркало не объявлено (ключа нет · файла нет): строка-свойство, код 0, прежнего имени нет",
         rc == 0 and rc2 == 0 and line in out and line in out2
         and MIRROR_LITERAL not in out and MIRROR_LITERAL not in out2,
         f"код {rc} · {out.strip()[-300:]} · без файла: код {rc2} · {out2.strip()[-200:]}")
    # D2 объявленное зеркало сверяется: копии совпадают
    c, tool = drift_stand(run, "d2", with_mirror="mirror")
    pfile(c).parent.mkdir(exist_ok=True)
    pfile(c).write_text(json.dumps({"mirror_repo": str(c / "mirror")}), encoding="utf-8")
    rc, out = run.py(c, [tool])
    case("D2", "объявленное зеркало сверяется: «СОВПАДАЕТ», строки «не объявлено» нет",
         rc == 0 and "СОВПАДАЕТ" in out and "зеркало не объявлено" not in out, f"код {rc} · {out.strip()[-300:]}")
    # D3 файл путей не читается: это не «не объявлено», код 1 (не-объект, см. шапку)
    c, tool = drift_stand(run, "d3", raw="[1, 2]")
    rc, out = run.py(c, [tool])
    case("D3", "файл путей не читается: «зеркало не определено», код 1, а не тихое «не объявлено»",
         rc == 1 and "зеркало не определено" in out and "зеркало не объявлено" not in out,
         f"код {rc} · {out.strip()[-300:]}")
    # D4 образец не объявлен: текст называет файл путей, а не таблицу meta (зеркало — аргументом)
    c, tool = drift_stand(run, "d4", with_mirror="mirror", paths={"template": "x"})
    rc, out = run.py(c, [tool, "--repo", c / "mirror" / "scripts"])
    case("D4", "образец не объявлен: текст называет ключ в файле путей, а не запись в meta",
         "ключ `template_checkout` в файле путей" in out and "в meta" not in out,
         f"код {rc} · {out.strip()[-400:]}")
    # D5 образец объявлен, каталога нет: отдельный текст «ЕСТЬ, но каталога по нему нет»
    c, tool = drift_stand(run, "d5", with_mirror="mirror")
    pfile(c).parent.mkdir(exist_ok=True)
    pfile(c).write_text(json.dumps({"template_checkout": str(c / "no-such-template")}), encoding="utf-8")
    rc, out = run.py(c, [tool, "--repo", c / "mirror" / "scripts"])
    case("D5", "образец объявлен, каталога нет: «ключ в файле путей ЕСТЬ, но каталога по нему нет»",
         "в файле путей ЕСТЬ, но каталога по нему нет" in out and "с общим образцом НЕ сверялось" not in out,
         f"код {rc} · {out.strip()[-400:]}")


# ═══ ГРУППА P: rules-from-pack.py ═════════════════════════════════════════════════════════════════
def pack_probe(run: Run, c: Path, db: Path):
    tool = run.scripts / "rules-from-pack.py"
    body = ("import importlib.util\n"
            "import sqlite3\n"
            f"spec = importlib.util.spec_from_file_location('rfp', {str(tool)!r})\n"
            "mod = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(mod)\n"
            f"conn = sqlite3.connect({str(db)!r})\n"
            "print(mod.find_pack_source(None, conn))\n")
    return run.probe(c, body, drop_container=False)


def group_pack(run: Run):
    # P1 папка клона — из файла путей, прежняя запись meta (ловушка) не берётся
    c, db = run.case_dir("p1", meta={"template_checkout": "decoy-pack"}, dirs=["pack", "decoy-pack"])
    pfile(c).parent.mkdir(exist_ok=True)
    pfile(c).write_text(json.dumps({"template_checkout": str(c / "pack")}), encoding="utf-8")
    rc, out = pack_probe(run, c, db)
    got = out.strip().splitlines()[-1] if out.strip() else ""
    case("P1", "template_checkout из файла путей: взята его папка, а не запись meta",
         rc == 0 and same(got, c / "pack"), f"код {rc} · {out.strip()[-300:]}")
    # P2 файла нет, запись meta есть: НЕ читается — отказ называет файл путей и несёт команду переноса
    c, db = run.case_dir("p2", meta={"template_checkout": "old-pack"}, dirs=["old-pack"])
    con = sqlite3.connect(str(db))
    con.execute("UPDATE meta SET value = ? WHERE key = 'template_checkout'", (str(c / "old-pack"),))
    con.commit()
    con.close()
    rc, out = pack_probe(run, c, db)
    case("P2", "прежняя запись meta не читается: отказ называет файл путей, а не таблицу meta",
         rc != 0 and "источник пакета GORDI неизвестен" in out and "файла путей" in out
         and "meta.template_checkout" not in out,
         f"код {rc} · {out.strip()[-500:]}")


# ═══ ГРУППА L: инструменты, которые читали впечатанный путь (карточка #677, Э3-Р4; заявка №29) ═════
# Каждое место — два случая: L<n> (контур с ДРУГОЙ раскладкой · без ключа · без файла путей, а на диске
# лежит приманка — раскладка автора; инструмент обязан брать объявленное или говорить «не объявлено», а не
# приманку) и L<n>w (слова: нет файла · нет ключа · объявлено, а на диске нет · файл не читается — РАЗНЫЕ).
LIT_ARCHS = "atlas.archs/.mezosync/coordination"        # раскладка автора: в приёмке — только приманка
RULES_SQL = (
    "CREATE TABLE rules (rule_key TEXT, body TEXT, locked_by TEXT, version INTEGER)",
    "INSERT INTO rules VALUES ('rule-a', 'тело правила А', 'coord', 1)",
    "CREATE TABLE invariants (code TEXT, description TEXT)",
)
MIRROR_OK = "### `rule-a` 🔒coord v1\n\nтело правила А\n"           # совпадает с базой
MIRROR_OLD = "### `rule-a` 🔒coord v0\n\nпрежнее тело\n"          # версия старше: выбор файла виден по коду 1


def posix(text) -> str:
    """Вывод инструмента с прямыми слэшами: путь Windows печатается и так, и этак."""
    return str(text).replace("\\", "/")


def seed(db: Path, *sqls):
    con = sqlite3.connect(str(db))
    for s in sqls:
        con.execute(s)
    con.commit()
    con.close()


def put(c: Path, files: dict):
    for rel, text in (files or {}).items():
        f = c / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8")


def tool_stand(run: Run, tag, tool, origin="scripts", paths=None, raw=None, dirs=(), sql=(), meta=None,
               files=None):
    """Каталог случая с КОПИЕЙ испытуемого инструмента в <контейнер>/.mezosync/scripts.
    origin: scripts — копия из испытуемого каталога скриптов · vnext — копия из каталога рядом с приёмкой."""
    c, db = run.case_dir(tag, meta=meta, paths=paths, raw=raw, dirs=dirs)
    seed(db, *sql)
    put(c, files)
    own = c / ".mezosync" / "scripts"
    mezo_stand.copy_tool(run.tool_src(tool, origin), own)
    # Поломка ложится ТОЛЬКО в копию испытуемого инструмента: соседа mezo_paths.py, что приехал с ним,
    # ломают поломки групп R–M (они красят свои случаи, а не эти) — иначе одна поломка краснила бы чужие.
    if run.brk and run.brk[0] == tool:
        run.patch(own)
    return c, db, own / tool


def group_mirror(run: Run):
    """L1 / L1w: check-rules-mirror.py — обе копии (рядом со скриптами и в vnext-tools)."""
    seen, bad = [], []
    for origin in ("scripts", "vnext"):
        # A: контур с другой раскладкой — каталог координации ОБЪЯВЛЕН; в раскладке автора лежит приманка
        c, db, tool = tool_stand(run, f"l1a-{origin}", "check-rules-mirror.py", origin,
                                 paths={"coordination_dir": "my-coord"}, sql=RULES_SQL,
                                 files={"my-coord/sync.rules.md": MIRROR_OK,
                                        f"{LIT_ARCHS}/sync.rules.md": MIRROR_OLD})
        rc, out = run.py(c, [tool, "--db", db])
        seen.append(("A", origin, rc))
        if not (rc == 0 and "СОШЛОСЬ" in out and "my-coord/sync.rules.md" in posix(out)):
            bad.append(f"A/{origin}: код {rc} · {out.strip()[-200:]}")
        # B: ключа нет (файл путей есть) и файла путей нет вовсе; приманка в раскладке автора СОВПАЛА БЫ с базой
        for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
            c, db, tool = tool_stand(run, f"l1{tag}-{origin}", "check-rules-mirror.py", origin, paths=paths,
                                     sql=RULES_SQL, files={f"{LIT_ARCHS}/sync.rules.md": MIRROR_OK})
            rc, out = run.py(c, [tool, "--db", db])
            seen.append((tag, origin, rc))
            if not (rc == 1 and "НЕТ ни в одном известном месте" in out and "atlas.archs" not in posix(out)):
                bad.append(f"{tag}/{origin}: код {rc} · {out.strip()[-200:]}")
    case("L1", "check-rules-mirror: файл-зеркало — из объявленного каталога координации; без ключа и без "
               "файла путей приманка из раскладки автора не берётся (обе копии)",
         not bad and len(seen) == 6, " · ".join(bad) or str(seen))
    # L1w: слова
    problems = []
    for origin in ("scripts", "vnext"):
        c, db, tool = tool_stand(run, f"l1w1-{origin}", "check-rules-mirror.py", origin, sql=RULES_SQL)
        rc, out = run.py(c, [tool, "--db", db])
        if not (rc == 1 and "каталог координации: файла путей нет" in out and "сверить НЕЧЕМ" in out):
            problems.append(f"нет файла/{origin}: код {rc} · {out.strip()[-200:]}")
        c, db, tool = tool_stand(run, f"l1w2-{origin}", "check-rules-mirror.py", origin, paths={"template": "x"},
                                 sql=RULES_SQL)
        rc, out = run.py(c, [tool, "--db", db])
        if not (rc == 1 and "каталог координации: не объявлено" in out and "«coordination_dir»" in out):
            problems.append(f"нет ключа/{origin}: код {rc} · {out.strip()[-200:]}")
        c, db, tool = tool_stand(run, f"l1w3-{origin}", "check-rules-mirror.py", origin,
                                 paths={"coordination_dir": "no-such-dir"}, sql=RULES_SQL)
        rc, out = run.py(c, [tool, "--db", db])
        if not (rc == 1 and "каталог координации: объявлено" in out and "на диске НЕТ" in out
                and "не объявлено" not in out):
            problems.append(f"объявлено, а каталога нет/{origin}: код {rc} · {out.strip()[-200:]}")
        c, db, tool = tool_stand(run, f"l1w4-{origin}", "check-rules-mirror.py", origin, raw="[1, 2]",
                                 sql=RULES_SQL)
        rc, out = run.py(c, [tool, "--db", db])
        if not (rc == 2 and "не смог определить, где лежит файл правил" in out and "не читается" in out):
            problems.append(f"файл не читается/{origin}: код {rc} · {out.strip()[-200:]}")
    case("L1w", "check-rules-mirror: нет файла · нет ключа · объявлено без каталога · файл не читается — "
                "четыре разных ответа словами", not problems, " · ".join(problems))


def group_export_rules(run: Run):
    """L2 / L2w: export-rules.py — куда пишется файл правил."""
    def go(c, db, tool):
        return run.py(c, [tool, "--db", db, "--apply"])

    problems = []
    # A: другая раскладка — каталог объявлен, приманка (каталог раскладки автора) существует
    c, db, tool = tool_stand(run, "l2a", "export-rules.py", paths={"coordination_dir": "my-coord"},
                             sql=RULES_SQL, dirs=[LIT_ARCHS])
    rc, out = go(c, db, tool)
    if not (rc == 0 and (c / "my-coord" / "sync.rules.md").is_file()
            and not (c / LIT_ARCHS / "sync.rules.md").exists()):
        problems.append(f"объявлено: код {rc} · файл в объявленном: {(c / 'my-coord' / 'sync.rules.md').is_file()}"
                        f" · в приманке: {(c / LIT_ARCHS / 'sync.rules.md').exists()} · {out.strip()[-160:]}")
    # B: ключа нет и файла путей нет; приманка существует — файл ложится рядом с базой
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l2{tag}", "export-rules.py", paths=paths, sql=RULES_SQL, dirs=[LIT_ARCHS])
        rc, out = go(c, db, tool)
        if not (rc == 0 and (c / ".mezosync" / "generated" / "sync.rules.md").is_file()
                and not (c / LIT_ARCHS / "sync.rules.md").exists()):
            problems.append(f"{tag}: код {rc} · рядом с базой: "
                            f"{(c / '.mezosync' / 'generated' / 'sync.rules.md').is_file()} · в приманке: "
                            f"{(c / LIT_ARCHS / 'sync.rules.md').exists()} · {out.strip()[-160:]}")
    case("L2", "export-rules: файл правил пишется в объявленный каталог координации, а без ключа — рядом с "
               "базой; раскладка автора не трогается", not problems, " · ".join(problems))
    # L2w: слова
    problems = []
    c, db, tool = tool_stand(run, "l2w1", "export-rules.py", paths={"coordination_dir": "no-such-dir"},
                             sql=RULES_SQL)
    rc, out = go(c, db, tool)
    if not (rc == 0 and "на диске НЕТ" in out and "каталог будет создан" in out
            and (c / "no-such-dir" / "sync.rules.md").is_file()):
        problems.append(f"объявлено, а каталога нет: код {rc} · {out.strip()[-200:]}")
    c, db, tool = tool_stand(run, "l2w2", "export-rules.py", raw="[1, 2]", sql=RULES_SQL)
    rc, out = go(c, db, tool)
    if not (rc != 0 and "место файла правил не определено" in out and "не читается" in out
            and not list(c.rglob("sync.rules.md"))):
        problems.append(f"файл не читается: код {rc} · файлов правил: {list(c.rglob('sync.rules.md'))} · "
                        f"{out.strip()[-200:]}")
    case("L2w", "export-rules: «объявлено, а каталога нет» говорится вслух, а файл путей, который не читается, "
                "останавливает запись", not problems, " · ".join(problems))


CHANNELS_SQL = (
    "CREATE TABLE messages_all (id INTEGER, writer_role TEXT, timestamp TEXT, body_md TEXT, tags TEXT, "
    "priority TEXT, source TEXT)",
    "INSERT INTO messages_all VALUES (1, 'LROLE', '2026-10-05 10:00:00', 'проба', NULL, 'normal', 'live')",
)


def channels_target(out: str):
    """Каталог, названный в строке «Ролей: N · цель: …» (холостой прогон ничего не пишет)."""
    m = re.search(r"цель: (.+)", out)
    return m.group(1).strip() if m else None


def group_export_channels(run: Run):
    """L3 / L3w: export-channels.py — куда ложатся готовые файлы каналов (холостой прогон)."""
    problems = []
    c, db, tool = tool_stand(run, "l3a", "export-channels.py", paths={"generated_dir": "my-gen"},
                             sql=CHANNELS_SQL, dirs=[LIT_ARCHS + "/generated"])
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 0 and same(channels_target(out), c / "my-gen")):
        problems.append(f"объявлено: код {rc} · цель {channels_target(out)!r} · ждали {c / 'my-gen'}")
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l3{tag}", "export-channels.py", paths=paths, sql=CHANNELS_SQL,
                                 dirs=[LIT_ARCHS + "/generated"])
        rc, out = run.py(c, [tool, "--db", db])
        if not (rc == 0 and same(channels_target(out), c / ".mezosync" / "generated")):
            problems.append(f"{tag}: код {rc} · цель {channels_target(out)!r} · ждали "
                            f"{c / '.mezosync' / 'generated'}")
    case("L3", "export-channels: готовые файлы — в объявленный каталог, а без ключа — рядом с базой; "
               "раскладка автора не берётся", not problems, " · ".join(problems))
    problems = []
    c, db, tool = tool_stand(run, "l3w1", "export-channels.py", paths={"generated_dir": "no-such-dir"},
                             sql=CHANNELS_SQL)
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 0 and "на диске НЕТ" in out and "каталог будет создан" in out):
        problems.append(f"объявлено, а каталога нет: код {rc} · {out.strip()[-200:]}")
    c, db, tool = tool_stand(run, "l3w2", "export-channels.py", raw="[1, 2]", sql=CHANNELS_SQL)
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc != 0 and "место готовых файлов не определено" in out and "не читается" in out):
        problems.append(f"файл не читается: код {rc} · {out.strip()[-200:]}")
    case("L3w", "export-channels: «объявлено, а каталога нет» говорится вслух, а файл путей, который не "
                "читается, останавливает работу", not problems, " · ".join(problems))


def md_dir(run: Run, c: Path, db: Path, tool: Path):
    """default_md_dir из КОПИИ write-message.py (модуль в подпроцессе): печатает «PATH=…» или «REFUSED=…»."""
    body = ("import importlib.util, pathlib, sys\n"
            f"sys.path.insert(0, {str(tool.parent)!r})\n"
            f"s = importlib.util.spec_from_file_location('wm_copy', {str(tool)!r})\n"
            "m = importlib.util.module_from_spec(s)\n"
            "s.loader.exec_module(m)\n"
            "try:\n"
            f"    print('PATH=' + str(m.default_md_dir(pathlib.Path({str(db)!r}))))\n"
            "except OSError as e:\n"
            "    print('REFUSED=' + str(e))\n")
    rc, out = run.py(c, ["-c", body])
    got = next((ln for ln in reversed(out.splitlines()) if ln.startswith(("PATH=", "REFUSED="))), "")
    return rc, got, out


def group_message(run: Run):
    """L4 / L4w: write-message.py — каталог каналов (default_md_dir)."""
    problems = []
    c, db, tool = tool_stand(run, "l4a", "write-message.py", paths={"coordination_dir": "my-coord"},
                             dirs=[LIT_ARCHS, "my-coord"])
    rc, got, out = md_dir(run, c, db, tool)
    if not (got.startswith("PATH=") and same(got[5:], c / "my-coord")):
        problems.append(f"объявлено: код {rc} · {got!r} · {out.strip()[-160:]}")
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l4{tag}", "write-message.py", paths=paths, dirs=[LIT_ARCHS])
        rc, got, out = md_dir(run, c, db, tool)
        if not (got.startswith("PATH=") and same(got[5:], c / "coordination")):
            problems.append(f"{tag}: код {rc} · {got!r} · ждали {c / 'coordination'} · {out.strip()[-160:]}")
    case("L4", "write-message: каталог каналов — объявленный, а без ключа — <контейнер>/coordination; "
               "раскладка автора не берётся", not problems, " · ".join(problems))
    problems = []
    c, db, tool = tool_stand(run, "l4w1", "write-message.py", paths={"coordination_dir": "no-such-dir"})
    rc, got, out = md_dir(run, c, db, tool)
    if not (got.startswith("PATH=") and same(got[5:], c / "no-such-dir")):
        problems.append(f"объявлено, а каталога нет: код {rc} · {got!r} · {out.strip()[-160:]}")
    c, db, tool = tool_stand(run, "l4w2", "write-message.py", raw="[1, 2]")
    rc, got, out = md_dir(run, c, db, tool)
    if not (got.startswith("REFUSED=") and "каталог каналов не определён" in got and "не читается" in got):
        problems.append(f"файл не читается: код {rc} · {got!r} · {out.strip()[-160:]}")
    case("L4w", "write-message: объявленный каталог отдаётся как есть, а файл путей, который не читается, "
                "отказывает словами", not problems, " · ".join(problems))


PHOENIX_SQL = (
    "CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT, confirmed_at TEXT, "
    "PRIMARY KEY(role, section))",
    "INSERT INTO phoenix VALUES ('LROLE', 'state', 'тело состояния', '2026-10-05 10:00:00', NULL)",
)
CMD_BAIT = "запусти C:/stand-nowhere/{}-script.py\n"        # команда в пустоту: приметой служит имя файла


def group_targets(run: Run):
    """L5 / L5w: guard-command-targets.py — каталог промптов."""
    problems = []
    c, db, tool = tool_stand(run, "l5a", "guard-command-targets.py", paths={"prompts_dir": "my-prompts"},
                             sql=PHOENIX_SQL,
                             files={"my-prompts/own.md": CMD_BAIT.format("own"),
                                    "atlas.archs/.mezosync/prompts/decoy.md": CMD_BAIT.format("decoy")})
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 1 and "[prompts/own.md]" in out and "decoy" not in out):
        problems.append(f"объявлено: код {rc} · {out.strip()[-260:]}")
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l5{tag}", "guard-command-targets.py", paths=paths, sql=PHOENIX_SQL,
                                 files={"atlas.archs/.mezosync/prompts/decoy.md": CMD_BAIT.format("decoy")})
        rc, out = run.py(c, [tool, "--db", db])
        if not (rc == 0 and "decoy" not in out):
            problems.append(f"{tag}: код {rc} · {out.strip()[-260:]}")
    case("L5", "guard-command-targets: промпты — из объявленного каталога; без ключа и без файла путей "
               "приманка из раскладки автора не сверяется", not problems, " · ".join(problems))
    problems = []
    # нет файла путей: слова «файла путей нет», код 0
    c, db, tool = tool_stand(run, "l5w1", "guard-command-targets.py", sql=PHOENIX_SQL)
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 0 and "каталог промптов: файла путей нет" in out and "свойство контура, не долг" in out):
        problems.append(f"нет файла: код {rc} · {out.strip()[-260:]}")
    # нет ключа: «не объявлено»
    c, db, tool = tool_stand(run, "l5w2", "guard-command-targets.py", paths={"template": "x"}, sql=PHOENIX_SQL)
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 0 and "каталог промптов: не объявлено" in out and "«prompts_dir»" in out):
        problems.append(f"нет ключа: код {rc} · {out.strip()[-260:]}")
    # объявлено, а каталога нет: другое слово и другой знак
    c, db, tool = tool_stand(run, "l5w3", "guard-command-targets.py", paths={"prompts_dir": "no-such-dir"},
                             sql=PHOENIX_SQL)
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 0 and "⚠️ каталог промптов: объявлено" in out and "на диске НЕТ" in out
            and "промпты не сверялись" in out and "свойство контура" not in out):
        problems.append(f"объявлено, а каталога нет: код {rc} · {out.strip()[-260:]}")
    # файл не читается: отказ, а не пропуск
    c, db, tool = tool_stand(run, "l5w4", "guard-command-targets.py", raw="[1, 2]", sql=PHOENIX_SQL)
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 2 and "НЕ ЗАПУСТИЛСЯ: каталог промптов не определён" in out and "не читается" in out):
        problems.append(f"файл не читается: код {rc} · {out.strip()[-260:]}")
    # стандартное место пакета (<каталог базы>/templates) работает без ключа
    c, db, tool = tool_stand(run, "l5w5", "guard-command-targets.py", paths={"template": "x"}, sql=PHOENIX_SQL,
                             files={".mezosync/templates/std.md": CMD_BAIT.format("std")})
    rc, out = run.py(c, [tool, "--db", db])
    if not (rc == 1 and "[prompts/std.md]" in out):
        problems.append(f"стандартное место: код {rc} · {out.strip()[-260:]}")
    case("L5w", "guard-command-targets: нет файла · нет ключа · объявлено без каталога · файл не читается · "
                "стандартное место — разные ответы словами", not problems, " · ".join(problems))


SPA_BAIT = ("export const Page = () => (\n  <Button onClick={() => notify('Демо: скоро')} />\n);\n")
SPA_CLEAN = "export const Page = () => <div />;\n"
SPA_DECOY = "atlas.studio/Src/Atlas.Studio.Spa/src"


def group_stub(run: Run):
    """L6 / L6w: guard-stub-expectations.py — исходники портала."""
    problems = []
    # A: объявлено; в нём — обещание без метки (код 1); в приманке — чисто
    c, db, tool = tool_stand(run, "l6a", "guard-stub-expectations.py", paths={"spa_src": "my-spa/src"},
                             files={"my-spa/src/Page.tsx": SPA_BAIT, SPA_DECOY + "/Clean.tsx": SPA_CLEAN})
    rc, out = run.py(c, [tool])
    if not (rc == 1 and "БЕЗ метки" in out and "Page.tsx" in out):
        problems.append(f"объявлено: код {rc} · {out.strip()[-260:]}")
    # B: ключа нет и файла путей нет; приманка несёт обещание без метки — не должна сверяться
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l6{tag}", "guard-stub-expectations.py", paths=paths,
                                 files={SPA_DECOY + "/Page.tsx": SPA_BAIT})
        rc, out = run.py(c, [tool])
        if not (rc == 0 and "БЕЗ метки" not in out):
            problems.append(f"{tag}: код {rc} · {out.strip()[-260:]}")
    case("L6", "guard-stub-expectations: исходники портала — из объявленного каталога; без ключа и без "
               "файла путей приманка не сверяется", not problems, " · ".join(problems))
    problems = []
    c, db, tool = tool_stand(run, "l6w1", "guard-stub-expectations.py")
    rc, out = run.py(c, [tool])
    if not (rc == 0 and "исходники портала: файла путей нет" in out and "свойство контура" in out
            and "НЕ зелёная" in out):
        problems.append(f"нет файла: код {rc} · {out.strip()[-260:]}")
    c, db, tool = tool_stand(run, "l6w2", "guard-stub-expectations.py", paths={"template": "x"})
    rc, out = run.py(c, [tool])
    if not (rc == 0 and "исходники портала: не объявлено" in out and "«spa_src»" in out
            and "свойство контура" in out):
        problems.append(f"нет ключа: код {rc} · {out.strip()[-260:]}")
    c, db, tool = tool_stand(run, "l6w3", "guard-stub-expectations.py", paths={"spa_src": "no-such-dir"})
    rc, out = run.py(c, [tool])
    if not (rc == 0 and "исходники портала: объявлено" in out and "на диске НЕТ" in out
            and "проверка пропущена" in out and "свойство контура" not in out):
        problems.append(f"объявлено, а каталога нет: код {rc} · {out.strip()[-260:]}")
    c, db, tool = tool_stand(run, "l6w4", "guard-stub-expectations.py", raw="[1, 2]")
    rc, out = run.py(c, [tool])
    if not (rc == 1 and "исходники портала не определены" in out and "не читается" in out):
        problems.append(f"файл не читается: код {rc} · {out.strip()[-260:]}")
    case("L6w", "guard-stub-expectations: нет файла · нет ключа · объявлено без каталога · файл не читается — "
                "разные ответы словами (не объявлено — свойство контура, а не долг)", not problems,
         " · ".join(problems))


DISK_OK = "print('МАРКЕР-СЛОЯ-ДИСКА-СТЕНД')\n"
DISK_META = "print('МАРКЕР-ИЗ-ТАБЛИЦЫ-META')\n"
DISK_DECOY = "print('МАРКЕР-ПРИМАНКИ-РАСКЛАДКИ-АВТОРА')\n"
DECOY_TOOL = "atlas.archs/step04_opssre/tools/disk_layer.py"


def phoenix_call(run: Run, c: Path, db: Path, tool: Path):
    return run.py(c, [tool, "--db", db, "--role", "LROLE", "--section", "state"])


def group_phoenix(run: Run):
    """L7 / L7w: read-phoenix.py — сборщик слоя диска."""
    problems = []
    # A: объявлен в файле путей; в таблице meta — прежняя запись на ДРУГОЙ сборщик, в раскладке автора — приманка
    c, db, tool = tool_stand(run, "l7a", "read-phoenix.py", paths={"disk_layer_tool": "tools/dl.py"},
                             sql=PHOENIX_SQL, meta={"disk_layer_tool": "tools/meta-dl.py"},
                             files={"tools/dl.py": DISK_OK, "tools/meta-dl.py": DISK_META,
                                    DECOY_TOOL: DISK_DECOY})
    rc, out = phoenix_call(run, c, db, tool)
    if not (rc == 0 and "МАРКЕР-СЛОЯ-ДИСКА-СТЕНД" in out and "МАРКЕР-ИЗ-ТАБЛИЦЫ-META" not in out
            and "МАРКЕР-ПРИМАНКИ" not in out):
        problems.append(f"объявлено: код {rc} · {out.strip()[-300:]}")
    # B: ключа нет и файла путей нет; приманка есть на диске, но не берётся
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l7{tag}", "read-phoenix.py", paths=paths, sql=PHOENIX_SQL,
                                 meta={"disk_layer_tool": "tools/meta-dl.py"},
                                 files={"tools/meta-dl.py": DISK_META, DECOY_TOOL: DISK_DECOY})
        rc, out = phoenix_call(run, c, db, tool)
        if not (rc == 0 and "СЛОЙ ДИСКА В ЭТОМ КОНТУРЕ НЕ ОБЪЯВЛЕН" in out and "МАРКЕР-" not in out):
            problems.append(f"{tag}: код {rc} · {out.strip()[-300:]}")
    case("L7", "read-phoenix: сборщик слоя диска — из файла путей; без ключа и без файла путей ни приманка "
               "раскладки автора, ни прежняя запись meta не запускаются", not problems, " · ".join(problems))
    problems = []
    c, db, tool = tool_stand(run, "l7w1", "read-phoenix.py", sql=PHOENIX_SQL)
    rc, out = phoenix_call(run, c, db, tool)
    if not (rc == 0 and "файла путей нет" in out and '{"disk_layer_tool": "<путь от корня контейнера>"}' in out
            and "для нового контура это его свойство" in out.lower().replace("  ", " ")):
        problems.append(f"нет файла: код {rc} · {out.strip()[-300:]}")
    c, db, tool = tool_stand(run, "l7w2", "read-phoenix.py", paths={"template": "x"}, sql=PHOENIX_SQL)
    rc, out = phoenix_call(run, c, db, tool)
    if not (rc == 0 and "не объявлено: в файле путей" in out and '"disk_layer_tool": "<путь от корня контейнера>"'
            in out and "{\"disk_layer_tool\"" not in out):
        problems.append(f"нет ключа: код {rc} · {out.strip()[-300:]}")
    c, db, tool = tool_stand(run, "l7w3", "read-phoenix.py", paths={"disk_layer_tool": "tools/absent.py"},
                             sql=PHOENIX_SQL)
    rc, out = phoenix_call(run, c, db, tool)
    if not (rc == 0 and "СЛОЙ ДИСКА НЕ СОБРАН — путь объявлен, а файла по нему нет" in out
            and "НЕ ОБЪЯВЛЕН" not in out):
        problems.append(f"объявлено, а файла нет: код {rc} · {out.strip()[-300:]}")
    c, db, tool = tool_stand(run, "l7w4", "read-phoenix.py", raw="[1, 2]", sql=PHOENIX_SQL)
    rc, out = phoenix_call(run, c, db, tool)
    if not (rc == 0 and "СЛОЙ ДИСКА НЕ СОБРАН — файл путей не читается" in out and "НЕ ОБЪЯВЛЕН" not in out):
        problems.append(f"файл не читается: код {rc} · {out.strip()[-300:]}")
    # прежняя запись meta несёт ключ, файла путей нет: значением не служит, но подсказка с командой переноса есть
    c, db, tool = tool_stand(run, "l7w5", "read-phoenix.py", sql=PHOENIX_SQL,
                             meta={"disk_layer_tool": "tools/meta-dl.py"}, files={"tools/meta-dl.py": DISK_META})
    rc, out = phoenix_call(run, c, db, tool)
    if not (rc == 0 and STEP_NAME in out and "disk_layer_tool" in out and "МАРКЕР-" not in out):
        problems.append(f"подсказка о прежнем источнике: код {rc} · {out.strip()[-300:]}")
    case("L7w", "read-phoenix: нет файла · нет ключа · объявлено без файла · файл не читается · подсказка о "
                "прежней записи meta — разные ответы словами", not problems, " · ".join(problems))


def group_forms(run: Run):
    """L8 / L8w: guard-printed-forms.py — каталог готовых файлов каналов (vnext-tools)."""
    def go(c, db, tool, *more):
        scr = c / "scr"
        scr.mkdir(exist_ok=True)
        (scr / "clean.py").write_text("print('чисто')\n", encoding="utf-8")
        return run.py(c, [tool, "--scripts", scr, "--db", db, "--role", "LROLE", "--no-run", "--no-rules",
                          "--canon", c / "none.md", "--tasks-dir", c / "tasks", *more])

    problems = []
    c, db, tool = tool_stand(run, "l8a", "guard-printed-forms.py", "vnext", paths={"generated_dir": "my-gen"},
                             files={"my-gen/sync.x.md": "текст\n",
                                    LIT_ARCHS + "/generated/sync.decoy.md": "текст\n"})
    rc, out = go(c, db, tool)
    line = next((ln for ln in posix(out).splitlines() if "файлы из базы:" in ln), "")
    shown = line.split("файлы из базы:", 1)[-1].strip()
    if not (same(shown, c / "my-gen") and "atlas.archs" not in posix(out)):
        problems.append(f"объявлено: код {rc} · строка {line!r}")
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l8{tag}", "guard-printed-forms.py", "vnext", paths=paths,
                                 files={LIT_ARCHS + "/generated/sync.decoy.md": "текст\n"})
        rc, out = go(c, db, tool)
        line = next((ln for ln in posix(out).splitlines() if "файлы из базы:" in ln), "")
        if not ("нет каталога, файлы из базы НЕ проверены" in line and "atlas.archs" not in posix(out)):
            problems.append(f"{tag}: код {rc} · строка {line!r}")
    case("L8", "guard-printed-forms: каталог готовых файлов — объявленный; без ключа и без файла путей "
               "приманка из раскладки автора не сверяется", not problems, " · ".join(problems))
    problems = []
    c, db, tool = tool_stand(run, "l8w1", "guard-printed-forms.py", "vnext")
    rc, out = go(c, db, tool)
    if not ("каталог готовых файлов каналов: файла путей нет" in out and "свойство контура, не долг" in out):
        problems.append(f"нет файла: код {rc} · {out.strip()[-260:]}")
    c, db, tool = tool_stand(run, "l8w2", "guard-printed-forms.py", "vnext", paths={"template": "x"})
    rc, out = go(c, db, tool)
    if not ("каталог готовых файлов каналов: не объявлено" in out and "«generated_dir»" in out
            and "свойство контура, не долг" in out):
        problems.append(f"нет ключа: код {rc} · {out.strip()[-260:]}")
    c, db, tool = tool_stand(run, "l8w3", "guard-printed-forms.py", "vnext", paths={"generated_dir": "no-such-dir"})
    rc, out = go(c, db, tool)
    if not ("⚠️ каталог готовых файлов каналов: объявлено" in out and "на диске НЕТ" in out
            and "свойство контура" not in out):
        problems.append(f"объявлено, а каталога нет: код {rc} · {out.strip()[-260:]}")
    c, db, tool = tool_stand(run, "l8w4", "guard-printed-forms.py", "vnext", raw="[1, 2]")
    rc, out = go(c, db, tool)
    if not (rc == 2 and "СУД НЕ СОСТОЯЛСЯ: каталог готовых файлов каналов не определён" in out
            and "не читается" in out):
        problems.append(f"файл не читается: код {rc} · {out.strip()[-260:]}")
    case("L8w", "guard-printed-forms: нет файла · нет ключа · объявлено без каталога · файл не читается — "
                "разные ответы словами", not problems, " · ".join(problems))


def chat_text(start: dt.datetime, gaps_min, role="TAXO"):
    """Один чат: строка с названной ролью и удары механизма (promptSource=sdk) через заданные промежутки."""
    rows = [json.dumps({"type": "assistant", "message": {"content": [
        {"type": "text", "text": f"python read-messages.py --роль {role}"}]}}, ensure_ascii=False)]
    t = start
    stamps = [t]
    for g in gaps_min:
        t = t + dt.timedelta(minutes=g)
        stamps.append(t)
    for t in stamps:
        rows.append(json.dumps({"type": "user", "promptSource": "sdk", "isMeta": True,
                                "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                                "message": {"role": "user",
                                            "content": [{"type": "text", "text": "исполни наказ-файл"}]}},
                               ensure_ascii=False))
    return "\n".join(rows) + "\n", stamps[-1]


def group_rhythm(run: Run):
    """L9 / L9w: measure-rhythm.py — каталог записей разговоров (vnext-tools)."""
    fresh, last = chat_text(dt.datetime(2026, 9, 1, tzinfo=dt.timezone.utc), [30] * 5)
    stale, _ = chat_text(dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc), [30] * 5)
    at = (last + dt.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%S")

    def go(c, db, tool, home, *more):
        return run.py(c, [tool, "--роль", "TAXO", "--на", at, "--db", db, *more],
                      USERPROFILE=str(home), HOME=str(home))

    def home_of(tag):
        h = run.box / f"home-{tag}"
        (h / ".claude" / "projects").mkdir(parents=True, exist_ok=True)
        return h

    def folder_name(c: Path) -> str:
        return re.sub(r"[^A-Za-z0-9]", "-", str(c))

    problems = []
    # A: каталог записей ОБЪЯВЛЕН (другая раскладка); в домашнем каталоге лежит приманка с именем папки автора
    c, db, tool = tool_stand(run, "l9a", "measure-rhythm.py", "vnext", paths={"chat_records": "my-chats"},
                             files={"my-chats/chat1.jsonl": fresh})
    h = home_of("a")
    put(h, {".claude/projects/C--guts--atlas/chat9.jsonl": stale})
    rc, out = go(c, db, tool, h)
    if not (rc == 0 and "ДЕРЖИТСЯ" in out and posix(c / "my-chats") in posix(out)):
        problems.append(f"объявлено: код {rc} · {out.strip()[-300:]}")
    # B: ключа нет / файла путей нет: каталог выводится из пути контейнера; приманка (имя папки автора) не берётся
    for tag, paths in (("b1", {"template": "x"}), ("b2", None)):
        c, db, tool = tool_stand(run, f"l9{tag}", "measure-rhythm.py", "vnext", paths=paths)
        h = home_of(tag)
        name = folder_name(c)
        put(h, {f".claude/projects/{name}/chat1.jsonl": fresh,
                ".claude/projects/C--guts--atlas/chat9.jsonl": stale})
        rc, out = go(c, db, tool, h)
        if not (rc == 0 and "ДЕРЖИТСЯ" in out and posix(h / ".claude" / "projects" / name) in posix(out)):
            problems.append(f"{tag}: код {rc} · ждали папку {name} · {out.strip()[-300:]}")
    case("L9", "measure-rhythm: каталог записей — объявленный, а без ключа выводится из пути контейнера; "
               "имя папки автора не берётся", not problems, " · ".join(problems))
    problems = []
    c, db, tool = tool_stand(run, "l9w1", "measure-rhythm.py", "vnext", paths={"template": "x"})
    h = home_of("w1")
    name = folder_name(c)
    put(h, {f".claude/projects/{name}/chat1.jsonl": fresh})
    rc, out = go(c, db, tool, h)
    if not ("каталог записей не объявлен" in out and "не объявлено: в файле путей" in out
            and "выведен из пути контейнера" in out and f": {name}" in out):
        problems.append(f"нет ключа: код {rc} · {out.strip()[-300:]}")
    c, db, tool = tool_stand(run, "l9w2", "measure-rhythm.py", "vnext", paths={"chat_records": "my-chats"},
                             files={"my-chats/chat1.jsonl": fresh})
    h = home_of("w2")
    rc, out = go(c, db, tool, h)
    if not ("каталог записей: объявлено" in out and "выведен из пути контейнера" not in out):
        problems.append(f"объявлено: код {rc} · {out.strip()[-300:]}")
    c, db, tool = tool_stand(run, "l9w3", "measure-rhythm.py", "vnext", raw="[1, 2]")
    h = home_of("w3")
    name = folder_name(c)
    put(h, {f".claude/projects/{name}/chat1.jsonl": fresh})
    rc, out = go(c, db, tool, h)
    if not (rc == 2 and "ОТКАЗ МЕРИТЬ: каталог записей не определён" in out and "не читается" in out
            and "ДЕРЖИТСЯ" not in out):
        problems.append(f"файл не читается: код {rc} · {out.strip()[-300:]}")
    case("L9w", "measure-rhythm: вывод каталога из пути контейнера говорится вслух; объявленный не выводится; "
                "файл путей, который не читается, — отказ мерить", not problems, " · ".join(problems))


# ═══ ГРУППА E: обвязка режима «--break all» ═══════════════════════════════════════════════════════
def all_breaks_container(root):
    """Контур, который закрепляется в среде дочерних вызовов «--break ИМЯ» режима all.

    Дочерний вызов ищет испытуемый каталог по MEZO_CONTAINER (mezo_target.LIVE_SCRIPTS). Пустой стенд
    для этого не годится: «в испытуемом каталоге нет mezo_paths.py» — так 05.10 ответили все 37 поломок
    разом. Поэтому берётся тот контур, из которого вызывающий нашёл испытуемый каталог; среду же
    каждого случая закрепляет за его стендом сам прогон (Run.py). root — стенд вызывающего: его берёт
    только поломка all-env-empty-stand (прежний вид обвязки). Саму среду собирает место вызова
    (mezo_stand.stand_env прямо у subprocess.run) — так её видит проверка закрепления среды."""
    if SELF_BREAK == "all-env-empty-stand":
        return root
    return mezo_target.LIVE_SCRIPTS.parent.parent


def group_all(run: Run):
    # E среда дочерних вызовов режима all: из неё испытуемый каталог находится (mezo_paths.py на месте)
    env = mezo_stand.stand_env(all_breaks_container(run.box), PYTHONIOENCODING="utf-8")
    probe = "import mezo_target; print(mezo_target.script('mezo_paths.py'))"
    p = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=str(Path(__file__).resolve().parent), env=env, timeout=120)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    got = out.splitlines()[-1] if out else ""
    case("E", "режим --break all: дочерний вызов находит испытуемый каталог (среда — не пустой стенд)",
         p.returncode == 0 and got.endswith("mezo_paths.py") and Path(got).is_file(),
         f"код {p.returncode} · {out[-300:]}")


# ═══ ПРОГОН ═══════════════════════════════════════════════════════════════════════════════════════
def run_cases(break_name):
    global SELF_BREAK
    if break_name and not BREAKS[break_name][0]:
        SELF_BREAK = break_name
    run = Run(break_name)
    if break_name:
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{break_name}»: {run.brk[3]}")
        print(f"   ждём провала РОВНО: {' '.join(sorted(run.brk[2]))}")
    print(f"⚖️ испытываются копии из: {mezo_target.label()}")
    run.build_base()
    # K контроль: у приёмки есть, что запускать (все испытуемые файлы на месте)
    have = all((run.scripts / n).is_file() for n in ("mezo_paths.py", "backup-db.py", "rules-from-pack.py")) \
        and (run.scripts / "migrations" / STEP_NAME).is_file()
    case("K", "контроль: испытуемые копии собраны, у приёмки есть что запускать", have, str(run.scripts),
         differ=False)
    group_reader(run)
    group_root(run)
    group_annex(run)
    group_step(run)
    group_backup(run)
    group_drift(run)
    group_pack(run)
    group_mirror(run)
    group_export_rules(run)
    group_export_channels(run)
    group_message(run)
    group_targets(run)
    group_stub(run)
    group_phoenix(run)
    group_forms(run)
    group_rhythm(run)
    group_all(run)
    if break_name and not run.patched:
        raise NotRun(f"⛔ НЕ ПРОВЕРЕНО: поломка «{break_name}» не легла — файла {run.brk[0]} нет среди копий")
    mezo_stand.release(run.box)
    total = OK + FAIL
    print()
    if break_name:
        expected, actual = set(run.brk[2]), set(FAILED)
        if actual == expected:
            print(f"🧪 ожидание поломки «{break_name}» ПОДТВЕРДИЛОСЬ: провален ровно {' '.join(sorted(actual))}")
            mezo_stand.expected_break()
        else:
            print(f"⚠️ ожидание поломки «{break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали {' '.join(sorted(expected))}, "
                  f"провалено {' '.join(sorted(actual)) or 'ничего'}")
        print(f"🔴 НАРОЧНАЯ ПОЛОМКА — случаев {total}, провалено {FAIL}")
        return 1
    if FAIL:
        print(f"🔴 НЕ ПРИНЯТО — случаев {total}, провалены: {' '.join(FAILED)}")
        return 1
    print(f"✅ ФАЙЛ ПУТЕЙ — ПРИНЯТО — случаев {OK} из {total}")
    return 0


def run_all_breaks():
    root = mezo_stand.new("bite-local-paths-all-")
    env = mezo_stand.stand_env(all_breaks_container(root), PYTHONIOENCODING="utf-8")
    confirmed = 0
    for name in BREAKS:
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--break", name],
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=1800, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        ok = f"ожидание поломки «{name}» ПОДТВЕРДИЛОСЬ" in out
        confirmed += ok
        line = next((ln.strip() for ln in out.splitlines() if "ожидание поломки" in ln), None)
        if line is None:
            # дочерний вызов не дошёл до итога: называем ЕГО причину, а не одну и ту же общую фразу
            lines = [ln.strip() for ln in out.splitlines() if ln.strip()]
            why = next((ln for ln in lines if "НЕ ЗАПУСТИЛАСЬ" in ln or "НЕ ПРОВЕРЕНО" in ln),
                       lines[-1] if lines else "вывода нет")
            line = f"строки об ожидании нет (код {r.returncode}): {why[:200]}"
        print(f"{'✅' if ok else '🔴'} {name}: {line}", flush=True)
    print(f"поломок {len(BREAKS)}, ожидание подтвердилось {confirmed}")
    return 0 if confirmed == len(BREAKS) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка файла путей контура (.mezosync/local/paths.json)")
    ap.add_argument("--break", "--porcha", dest="break_name", default=None, choices=[*BREAKS, "all"],
                    help="нарочная поломка на копии испытуемого файла (all — все подряд)")
    a = ap.parse_args()
    try:
        if a.break_name == "all":
            return run_all_breaks()
        return run_cases(a.break_name)
    except NotRun as e:
        print(e)
        return 2        # отказ мерить: стенд сохраняется, но называется своими словами


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
