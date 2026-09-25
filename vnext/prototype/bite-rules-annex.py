#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-rules-annex — приёмка доставки приложений правил соседям (карточка #652 этап 2,
задача #651, записка #5337).

    python bite-rules-annex.py

ПРЕДМЕТ. 13 правил свода сократили текст и вынесли разбор случаев в
`<пакет>/rules/annex/<ключ>.md`; сам текст правила кончается строкой «…— приложение:
set-rule.py --key X --annex». У СОСЕДЕЙ (контур из init-group.py, контур, ни разу не
бравший --adopt по этим ключам) файла с приложением нет — ссылка вела в пустоту. Три
места несут починку:
  · scripts/init-group.py — кладёт rules/annex/*.md свежему контуру (шаг 7е);
  · scripts/rules-from-pack.py — кладёт приложение ключа при --adopt/--merge/--annexes
    (place_annex, cmd_annexes), одной функцией места с set-rule.py (mezo_paths.annex_dir);
  · scripts/set-rule.py — --annex/--show читают то же место (не тронуто по существу,
    само место переехало в mezo_paths.py).

ИЗОЛЯЦИЯ ОТ ЖИВОГО (тот же довод, что у bite-rules-from-pack.py): рабочие каталоги —
через `mezo_stand.new()`, подпроцессы — со средой стенда (`mezo_stand.stand_env`).
Эта приёмка НИКОГДА не открывает живую БД и не пишет вне своих временных каталогов.

ИСПЫТУЕМОЕ. rules-from-pack.py — через mezo_target (по умолчанию — инструменты контура,
на который указывает MEZO_CONTAINER, иначе своего). init-group.py и rules/annex/*.md —
из ПАКЕТА: его корень называет MEZO_PACK_ROOT, по умолчанию — mezo_paths.template_root(),
тот же пакет, что берут guard-seed-rules.py и соседние проверки. Пакет только читается:
свежий контур случая ① собирается во временном каталоге стенда.

Нарочные поломки (А/Б) правят ТЕКСТ rules-from-pack.py В ПАМЯТИ (compile+exec) — на
диск ничего не пишется; см. `load_rfp`. Обе бьют РОВНО в place_annex() — целятся в
СЦЕНАРИЙ конкретного случая напрямую (тот же приём, что patch_* у bite-rules-from-
pack.py), не гоняя весь список случаев заново: остальные случаи (① показ, приём приложе-
ний свежим контуром, --show) этот код не проходят вовсе — поломке внутри place_annex()
их не тронуть.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале
import mezo_target  # noqa: E402 — какую копию контура испытуем (образец: bite-rules-from-pack.py)

RFP_PATH = mezo_target.script("rules-from-pack.py")
print(f"⚖️ испытуется rules-from-pack.py: {mezo_target.label()}")

# Корень ПАКЕТА (rules/annex/*.md, scripts/init-group.py): MEZO_PACK_ROOT — чтобы испытать
# копию пакета до публикации; по умолчанию — пакет, на который смотрит контур.
PACK_ROOT = Path(os.environ.get("MEZO_PACK_ROOT") or mezo_paths.template_root()).resolve()
if not (PACK_ROOT / "rules" / "annex").is_dir():
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {PACK_ROOT} нет rules/annex — пакет старее доставки "
             f"приложений правил. Копию пакета можно указать явно: MEZO_PACK_ROOT=<путь>")
print(f"⚖️ копия пакета: {PACK_ROOT}")

# Ключ для ①/② — маленький файл приложения (7,5 КБ), чтобы прогон реального init-group.py
# оставался быстрым; для остальных случаев берём ФИКТИВНЫЕ ключи (не путать с настоящими
# 13 — приёмка не вправе зависеть от того, какие правила и тексты лежат в пакете СЕГОДНЯ:
# rules/universal.sql меняется своим ходом, независимо от доставки приложений).
SMALL_REAL_KEY = "no-pipe-tool-output"
PREFIX = "zzz-bite-annex-"

CASES = 0


def case(title, verdict, detail) -> bool:
    global CASES
    CASES += 1
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


# ── ЗАГРУЗКА ИСПЫТУЕМОГО (нарочные поломки — в памяти, тем же приёмом, что у
#    bite-rules-from-pack.py: load_rfp) ───────────────────────────────────────────────

def load_rfp(patch=None, name="rfp_annex_bite"):
    src = RFP_PATH.read_text(encoding="utf-8")
    if patch is not None:
        new_src, n = patch(src)
        if n != 1:
            raise AssertionError(f"поломка не нашла ровно одну строку-цель (нашла {n}) — "
                                 f"испытуемое могло измениться, поломку надо пересмотреть")
        src = new_src
    spec = importlib.util.spec_from_file_location(name, str(RFP_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    exec(compile(src, str(RFP_PATH), "exec"), mod.__dict__)
    return mod


def patch_force_disabled(src: str):
    """ПОЛОМКА (А): страж согласия у ДРУГОГО содержимого отключён — place_annex()
    переписывает чужой текст, даже когда force=False. Целится РОВНО в случай ⑥."""
    old = "        if not force:\n"
    new = "        if False:  # ПОЛОМКА (А) БИТА: страж согласия отключён нарочно\n"
    return src.replace(old, new, 1), src.count(old)


def patch_write_disabled(src: str):
    """ПОЛОМКА (Б): запись файла — не операция, а немая заглушка. place_annex() отчитывается
    об успехе, но диска не касается. Целится РОВНО в случаи ③/⑧ (успешная запись)."""
    old = '    dst.write_text(want, encoding="utf-8")\n'
    new = ('    pass  # ПОЛОМКА (Б) БИТА: dst.write_text(want, encoding="utf-8") — не позвано\n')
    return src.replace(old, new, 1), src.count(old)


# ── ФИКСТУРЫ ─────────────────────────────────────────────────────────────────────────

CIRCUIT_SCHEMA = """
CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rule_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL,
    locked_by TEXT NOT NULL DEFAULT 'coord', version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    basis TEXT, authorized TEXT, source_ref TEXT, expiry_kind TEXT, expiry_cond TEXT,
    status TEXT NOT NULL DEFAULT 'active', revoked_at TEXT, revoked_by TEXT, revoked_reason TEXT,
    superseded_by INTEGER, skill_delivery TEXT
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')), actor_role TEXT NOT NULL,
    action TEXT NOT NULL, target TEXT NOT NULL, diff_md TEXT);
CREATE TABLE roles (role TEXT PRIMARY KEY, lifecycle TEXT, lifecycle_reason TEXT);
"""

PACK_SCHEMA = """
CREATE TABLE pack_rules (rule_set TEXT, rule_key TEXT, body TEXT, locked_by TEXT, text_sha TEXT,
    pack_updated_at TEXT, pack_commit TEXT, removed_at TEXT, PRIMARY KEY (rule_set, rule_key));
CREATE TABLE pack_rules_history (rule_set TEXT, rule_key TEXT, text_sha TEXT, body TEXT,
    locked_by TEXT, first_commit TEXT, first_seen_at TEXT, replaced_at TEXT,
    PRIMARY KEY (rule_set, rule_key, text_sha));
CREATE TABLE pack_rules_meta (key TEXT PRIMARY KEY, value TEXT);
"""


def make_circuit_db(path: Path, rules=(), meta=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(CIRCUIT_SCHEMA)
    for r in rules:
        conn.execute(
            "INSERT INTO rules(rule_key, body, locked_by, status) VALUES (?,?,?,?)",
            (r["rule_key"], r["body"], r.get("locked_by", "coord"), r.get("status", "active")))
    for k, v in (meta or {}).items():
        conn.execute("INSERT INTO meta(key, value) VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()


def make_pack_db(path: Path, rows=(), meta=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(PACK_SCHEMA)
    for r in rows:
        conn.execute("INSERT INTO pack_rules VALUES (?,?,?,?,?,?,?,?)",
                     (r["rule_set"], r["rule_key"], r["body"], r.get("locked_by", "coord"),
                      r["text_sha"], r.get("pack_updated_at", "2026-09-24 00:00:00 UTC"),
                      r.get("pack_commit", "c000000"), r.get("removed_at")))
    for k, v in (meta or {"schema_version": "1"}).items():
        conn.execute("INSERT INTO pack_rules_meta VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()


def make_fixture_pack(root: Path, keys_with_annex: dict, keys_without_annex=()):
    """Фиктивный пакет: rules/pack-rules.db + rules/annex/<ключ>.md. keys_with_annex —
    {ключ: (текст_правила, текст_приложения)}; keys_without_annex — ключи БЕЗ файла
    приложения (проверка «нет — молчим», случай ⑩)."""
    pack_dir = root / "pack"
    rows = []
    for key, (body, _annex) in keys_with_annex.items():
        rows.append({"rule_set": "universal", "rule_key": key, "body": body,
                     "text_sha": rfp_mod.text_sha(body)})
    for key in keys_without_annex:
        body = f"тело без приложения {key}\n"
        rows.append({"rule_set": "universal", "rule_key": key, "body": body,
                     "text_sha": rfp_mod.text_sha(body)})
    make_pack_db(pack_dir / "rules" / "pack-rules.db", rows=rows)
    annex_dir = pack_dir / "rules" / "annex"
    annex_dir.mkdir(parents=True, exist_ok=True)
    for key, (_body, annex_text) in keys_with_annex.items():
        (annex_dir / f"{key}.md").write_text(annex_text, encoding="utf-8")
    return pack_dir


# ── main ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    ok = True
    global rfp_mod
    rfp_mod = load_rfp()   # немодифицированная копия — считает text_sha() фикстурам ниже

    root = mezo_stand.new("bite-rules-annex-")

    # ── ① СВЕЖИЙ КОНТУР: init-group.py кладёт rules/annex/*.md, set-rule.py --annex
    #     печатает приложение маленького реального ключа (код 0) ──────────────────────
    fresh_path = root / "fresh1" / ".mezosync"
    init_group_py = PACK_ROOT / "scripts" / "init-group.py"
    r1 = subprocess.run(
        [sys.executable, str(init_group_py), "--name", "bitefresh1", "--path", str(fresh_path)],
        cwd=str(PACK_ROOT), capture_output=True, text=True, timeout=180,
        env=mezo_stand.stand_env(fresh_path.parent))
    annex_file_1 = fresh_path / "rules-annex" / f"{SMALL_REAL_KEY}.md"
    ok &= case("① init-group.py (свежий контур) кладёт rules-annex/",
              r1.returncode == 0 and annex_file_1.is_file(),
              f"код {r1.returncode} · файл {annex_file_1}: "
              f"{'есть' if annex_file_1.is_file() else 'НЕТ'}"
              + ("" if r1.returncode == 0 else f"\n   хвост вывода: {r1.stdout[-400:]}"))

    set_rule_py = fresh_path / "scripts" / "set-rule.py"
    r1b = subprocess.run(
        [sys.executable, str(set_rule_py), "--key", SMALL_REAL_KEY, "--annex"],
        capture_output=True, text=True, timeout=60, env=mezo_stand.stand_env(fresh_path.parent))
    expect_text = (PACK_ROOT / "rules" / "annex" / f"{SMALL_REAL_KEY}.md").read_text(encoding="utf-8")
    ok &= case("①б set-rule.py --key … --annex печатает приложение (код 0)",
              r1b.returncode == 0 and expect_text in r1b.stdout,
              f"код {r1b.returncode} · текст приложения пакета найден в выводе: "
              f"{expect_text in r1b.stdout}")

    # ── ② --show: одна строка «приложение в пакете» — есть/нет ─────────────────────────
    key_yes, key_no = PREFIX + "has-annex", PREFIX + "no-annex"
    body_yes, annex_yes = "тело правила С приложением\n", "# приложение\nразбор случаев\n"
    fx_root = root / "fx-show"
    pack_dir2 = make_fixture_pack(fx_root, {key_yes: (body_yes, annex_yes)}, keys_without_annex=[key_no])
    circuit_db2 = fx_root / "circuit.db"
    make_circuit_db(circuit_db2, rules=[{"rule_key": key_yes, "body": body_yes}])
    conn2 = sqlite3.connect(f"file:{circuit_db2.as_posix()}?mode=ro", uri=True)
    pconn2 = rfp_mod.open_pack_db(pack_dir2)
    out2 = io_capture(lambda: rfp_mod.cmd_show(conn2, pconn2, key_yes,
                                               rfp_mod.load_meta_map(conn2, "pack_rules_base"),
                                               None, source=pack_dir2))
    conn2.close(); pconn2.close()
    ok &= case("② --show: «приложение в пакете: есть» для ключа с annex-файлом",
              "приложение в пакете: есть" in out2, f"строка вывода: "
              f"{[l for l in out2.splitlines() if 'приложение в пакете' in l]}")

    conn2n = sqlite3.connect(f"file:{circuit_db2.as_posix()}?mode=ro", uri=True)
    pconn2n = rfp_mod.open_pack_db(pack_dir2)
    out2n = io_capture(lambda: rfp_mod.cmd_show(conn2n, pconn2n, key_no,
                                                rfp_mod.load_meta_map(conn2n, "pack_rules_base"),
                                                None, source=pack_dir2))
    conn2n.close(); pconn2n.close()
    ok &= case("②б --show: «приложение в пакете: нет» для ключа БЕЗ annex-файла",
              "приложение в пакете: нет" in out2n, f"строка вывода: "
              f"{[l for l in out2n.splitlines() if 'приложение в пакете' in l]}")

    # ── ③ --adopt --apply кладёт приложение ключа ───────────────────────────────────
    key3 = PREFIX + "adopt"
    body3, annex3 = "тело правила ДЛЯ ВЗЯТИЯ\n", "# приложение к adopt\nслучаи…\n"
    fx3 = root / "fx-adopt"
    pack_dir3 = make_fixture_pack(fx3, {key3: (body3, annex3)})
    circuit_db3 = fx3 / "circuit.db"
    make_circuit_db(circuit_db3, rules=[], meta={"template_checkout": str(pack_dir3)})
    conn3 = sqlite3.connect(f"file:{circuit_db3.as_posix()}?mode=rw", uri=True)
    pconn3 = rfp_mod.open_pack_db(pack_dir3)
    rfp_mod.adopt_keys(conn3, circuit_db3, pconn3, {}, [key3], None,
                       "владелец, приёмка ③", True, "BITE", source=pack_dir3, annex_force=False)
    conn3.close(); pconn3.close()
    dst3 = mezo_paths.annex_path(circuit_db3, key3)
    ok &= case("③ --adopt --apply кладёт приложение ключа в контур",
              dst3.is_file() and dst3.read_text(encoding="utf-8") == annex3,
              f"файл {dst3}: {'совпадает с пакетом' if dst3.is_file() and dst3.read_text(encoding='utf-8') == annex3 else 'НЕ совпадает/нет'}")

    # ── ④ --adopt БЕЗ --apply — только говорит, куда положил бы; ничего не пишет ────
    key4 = PREFIX + "adopt-dry"
    body4, annex4 = "тело холостого adopt\n", "# приложение холостого adopt\n"
    fx4 = root / "fx-adopt-dry"
    pack_dir4 = make_fixture_pack(fx4, {key4: (body4, annex4)})
    circuit_db4 = fx4 / "circuit.db"
    make_circuit_db(circuit_db4, rules=[])
    conn4 = sqlite3.connect(f"file:{circuit_db4.as_posix()}?mode=rw", uri=True)
    pconn4 = rfp_mod.open_pack_db(pack_dir4)
    out4 = io_capture(lambda: rfp_mod.adopt_keys(conn4, circuit_db4, pconn4, {}, [key4], None,
                                                 None, False, None, source=pack_dir4))
    conn4.close(); pconn4.close()
    dst4 = mezo_paths.annex_path(circuit_db4, key4)
    ok &= case("④ --adopt БЕЗ --apply: «положил бы» напечатано, файл НЕ создан",
              ("положил бы" in out4) and not dst4.is_file(),
              f"«положил бы» в выводе: {'положил бы' in out4} · файл создан: {dst4.is_file()}")

    # ── ⑤ --merge --apply кладёт приложение ключа ───────────────────────────────────
    key5 = PREFIX + "merge"
    body5, annex5 = "тело до сведения\n", "# приложение к merge\n"
    merged5 = "тело ПОСЛЕ сведения\n"
    fx5 = root / "fx-merge"
    pack_dir5 = make_fixture_pack(fx5, {key5: (body5, annex5)})
    circuit_db5 = fx5 / "circuit.db"
    make_circuit_db(circuit_db5, rules=[{"rule_key": key5, "body": "старое тело\n"}])
    merged_file5 = fx5 / "merged.txt"
    merged_file5.write_text(merged5, encoding="utf-8")
    conn5 = sqlite3.connect(f"file:{circuit_db5.as_posix()}?mode=rw", uri=True)
    pconn5 = rfp_mod.open_pack_db(pack_dir5)
    rfp_mod.merge_key(conn5, circuit_db5, pconn5, {}, key5, None, str(merged_file5),
                      "владелец, приёмка ⑤", True, "BITE", source=pack_dir5, annex_force=False)
    conn5.close(); pconn5.close()
    dst5 = mezo_paths.annex_path(circuit_db5, key5)
    ok &= case("⑤ --merge --apply кладёт приложение ключа в контур",
              dst5.is_file() and dst5.read_text(encoding="utf-8") == annex5,
              f"файл {dst5}: {'совпадает' if dst5.is_file() and dst5.read_text(encoding='utf-8') == annex5 else 'НЕ совпадает/нет'}")

    # ── ⑥ Чужое ДРУГОЕ приложение НЕ перезаписано молча (force=False по умолчанию) ──
    key6 = PREFIX + "keep-foreign"
    body6, annex6 = "тело ⑥\n", "# приложение пакета ⑥\n"
    foreign6 = "# ЧУЖОЙ текст приложения, написанный рукой роли в контуре\n"
    fx6 = root / "fx-keep-foreign"
    pack_dir6 = make_fixture_pack(fx6, {key6: (body6, annex6)})
    circuit_db6 = fx6 / "circuit.db"
    make_circuit_db(circuit_db6, rules=[])
    dst6 = mezo_paths.annex_path(circuit_db6, key6)
    dst6.parent.mkdir(parents=True, exist_ok=True)
    dst6.write_text(foreign6, encoding="utf-8")
    msg6 = rfp_mod.place_annex(pack_dir6, circuit_db6, key6, apply=True, force=False)
    ok &= case("⑥ чужое ДРУГОЕ приложение НЕ переписано молча (без --annex-force)",
              dst6.read_text(encoding="utf-8") == foreign6 and "НЕ ПЕРЕЗАПИСАНО" in (msg6 or "")
              and "--annex-force" in (msg6 or ""),
              f"файл после вызова: {'ЧУЖОЙ текст цел' if dst6.read_text(encoding='utf-8') == foreign6 else 'ПЕРЕЗАПИСАН'}"
              f" · сообщение называет --annex-force: {'--annex-force' in (msg6 or '')}")

    # ── ⑦ --annex-force ПЕРЕЗАПИСЫВАЕТ чужое другое содержимое ──────────────────────
    key7 = PREFIX + "force"
    body7, annex7 = "тело ⑦\n", "# приложение пакета ⑦ (новое)\n"
    foreign7 = "# чужой старый текст ⑦\n"
    fx7 = root / "fx-force"
    pack_dir7 = make_fixture_pack(fx7, {key7: (body7, annex7)})
    circuit_db7 = fx7 / "circuit.db"
    make_circuit_db(circuit_db7, rules=[])
    dst7 = mezo_paths.annex_path(circuit_db7, key7)
    dst7.parent.mkdir(parents=True, exist_ok=True)
    dst7.write_text(foreign7, encoding="utf-8")
    rfp_mod.place_annex(pack_dir7, circuit_db7, key7, apply=True, force=True)
    ok &= case("⑦ --annex-force переписывает чужое другое содержимое",
              dst7.read_text(encoding="utf-8") == annex7,
              f"файл после вызова: "
              f"{'текст пакета' if dst7.read_text(encoding='utf-8') == annex7 else 'НЕ обновлён'}")

    # ── ⑧ --annexes --apply кладёт недостающие приложения ключам state=same ─────────
    key8 = PREFIX + "same"
    body8, annex8 = "тело ⑧, УЖЕ совпадает с пакетом\n", "# приложение ⑧\n"
    fx8 = root / "fx-annexes"
    pack_dir8 = make_fixture_pack(fx8, {key8: (body8, annex8)})
    circuit_db8 = fx8 / "circuit.db"
    make_circuit_db(circuit_db8, rules=[{"rule_key": key8, "body": body8}])  # текст = пакету ⇒ same
    conn8 = sqlite3.connect(f"file:{circuit_db8.as_posix()}?mode=rw", uri=True)
    pconn8 = rfp_mod.open_pack_db(pack_dir8)
    rfp_mod.cmd_annexes(conn8, circuit_db8, pconn8, pack_dir8, {}, {}, ["universal"], set(),
                        True, "BITE", False)
    conn8.close(); pconn8.close()
    dst8 = mezo_paths.annex_path(circuit_db8, key8)
    ok &= case("⑧ --annexes --apply кладёт приложение ключу «same» без --adopt",
              dst8.is_file() and dst8.read_text(encoding="utf-8") == annex8,
              f"файл {dst8}: {'совпадает' if dst8.is_file() and dst8.read_text(encoding='utf-8') == annex8 else 'НЕ совпадает/нет'}")

    # ── ⑨ --annexes БЕЗ --apply — ничего не пишет ────────────────────────────────────
    key9 = PREFIX + "same-dry"
    body9, annex9 = "тело ⑨, УЖЕ совпадает\n", "# приложение ⑨\n"
    fx9 = root / "fx-annexes-dry"
    pack_dir9 = make_fixture_pack(fx9, {key9: (body9, annex9)})
    circuit_db9 = fx9 / "circuit.db"
    make_circuit_db(circuit_db9, rules=[{"rule_key": key9, "body": body9}])
    conn9 = sqlite3.connect(f"file:{circuit_db9.as_posix()}?mode=rw", uri=True)
    pconn9 = rfp_mod.open_pack_db(pack_dir9)
    out9 = io_capture(lambda: rfp_mod.cmd_annexes(conn9, circuit_db9, pconn9, pack_dir9, {}, {},
                                                  ["universal"], set(), False, None, False))
    conn9.close(); pconn9.close()
    dst9 = mezo_paths.annex_path(circuit_db9, key9)
    ok &= case("⑨ --annexes БЕЗ --apply: холостой прогон ничего не пишет",
              ("положил бы" in out9) and not dst9.is_file(),
              f"«положил бы» в выводе: {'положил бы' in out9} · файл создан: {dst9.is_file()}")

    # ── ⑩ ключ без приложения в пакете — place_annex молчит (None), --adopt/--annexes
    #     не печатают о нём НИ СЛОВА (тишина на пустом месте — не шум) ────────────────
    key10 = PREFIX + "no-annex-at-all"
    fx10 = root / "fx-no-annex"
    pack_dir10 = make_fixture_pack(fx10, {}, keys_without_annex=[key10])
    circuit_db10 = fx10 / "circuit.db"
    make_circuit_db(circuit_db10, rules=[])
    r10 = rfp_mod.place_annex(pack_dir10, circuit_db10, key10, apply=True, force=False)
    ok &= case("⑩ ключ БЕЗ приложения в пакете: place_annex молчит (None), диска не касается",
              r10 is None and not mezo_paths.annex_path(circuit_db10, key10).is_file(),
              f"возврат: {r10!r} · файл создан: {mezo_paths.annex_path(circuit_db10, key10).is_file()}")

    # ── ⑪ ПОЛОМКА (А): страж согласия отключён — красит РОВНО случай ⑥ ──────────────
    mod_a = load_rfp(patch=patch_force_disabled, name="rfp_annex_bite_a")
    fxA = root / "fx-break-a"
    pack_dirA = make_fixture_pack(fxA, {key6: (body6, annex6)})
    dstA = mezo_paths.annex_path(fxA / "circuit.db", key6)
    dstA.parent.mkdir(parents=True, exist_ok=True)
    dstA.write_text(foreign6, encoding="utf-8")
    mod_a.place_annex(pack_dirA, fxA / "circuit.db", key6, apply=True, force=False)
    broke_six = dstA.read_text(encoding="utf-8") == annex6   # под поломкой — ПЕРЕЗАПИСАЛО
    ok &= case("⑪ ПОЛОМКА (А) «страж согласия отключён» красит ровно случай ⑥: "
              "чужой текст теперь переписан БЕЗ --annex-force",
              broke_six, f"файл под поломкой: "
              f"{'ПЕРЕЗАПИСАН (поломка поймана бы случаем ⑥)' if broke_six else 'цел — поломка не сработала'}")

    # ── ⑫ ПОЛОМКА (Б): запись отключена — красит РОВНО случай ③ (и ⑧, тем же кодом) ──
    mod_b = load_rfp(patch=patch_write_disabled, name="rfp_annex_bite_b")
    fxB = root / "fx-break-b"
    pack_dirB = make_fixture_pack(fxB, {key3: (body3, annex3)})
    circuit_dbB = fxB / "circuit.db"
    dstB = mezo_paths.annex_path(circuit_dbB, key3)
    mod_b.place_annex(pack_dirB, circuit_dbB, key3, apply=True, force=False)
    broke_three = not dstB.is_file()   # под поломкой — НЕ записало вовсе
    ok &= case("⑫ ПОЛОМКА (Б) «запись — заглушка» красит ровно случай ③/⑧: "
              "apply=True больше не кладёт файл на диск",
              broke_three, f"файл под поломкой: "
              f"{'НЕ создан (поломка поймана бы случаем ③/⑧)' if broke_three else 'создан — поломка не сработала'}")

    print()
    print(f"{'✅ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}")
    return 0 if ok else 1


def io_capture(fn) -> str:
    """Ловит stdout вызова fn() и возвращает его строкой — для проверки печатаемых строк
    без переписывания испытуемых функций (они печатают через print, не возвращают текст)."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
