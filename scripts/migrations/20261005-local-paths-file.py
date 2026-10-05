#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
20261005-local-paths-file — перенос путей контура в ОДИН файл (карточка #677, этап Э3, работа Р4).

РЕШЕНИЕ ВЛАДЕЛЬЦА В3 а′ (2026-10-05 10:53 UTC, чат COORD): пути контура — в файле в отдельной
местной папке; файл заменяет строки local.paths и ключи таблицы meta mirror_repo,
template_checkout, disk_layer_tool: одно место для путей вместо трёх.

ЧТО ДЕЛАЕТ ШАГ. Пишет <контейнер>/.mezosync/local/paths.json — JSON-объект «ключ → путь»
(относительный путь считается от контейнера) — из того, что контур хранил раньше:
  · ключи meta: mirror_repo · template_checkout · disk_layer_tool;
  · строки container= и template= из файла local.paths рядом с инструментами контура
    (.mezosync/scripts/local.paths) и — в раскладке контура-автора — из vnext-tools/local.paths;
  · ПРЕЖНЯЯ РАСКЛАДКА АВТОРА (контур Atlas): каталоги, имена которых раньше были впечатаны в
    инструменты, — вписываются ТОЛЬКО если такой каталог ЕСТЬ на диске этого контура:
      coordination_dir  atlas.archs/.mezosync/coordination
      generated_dir     atlas.archs/.mezosync/coordination/generated
      prompts_dir       atlas.archs/.mezosync/prompts
      spa_src           atlas.studio/Src/Atlas.Studio.Spa/src
      annex_dir         atlas.archs/.mezosync/rules-annex
    Литералы этого списка допустимы ТОЛЬКО здесь: это правило «прежняя раскладка автора»,
    а не знание инструментов. У контура без таких каталогов ключи не вписываются, и
    инструменты читают СТАНДАРТНУЮ раскладку пакета (то, что создаёт сборка нового контура):
    <контейнер>/coordination, <контейнер>/bridges, .mezosync/generated, .mezosync/templates,
    .mezosync/rules-annex.
  Ключ meta template_source (адрес пакета) в файл НЕ переносится: он остаётся в meta.

РЕЖИМ. По умолчанию — ХОЛОСТОЙ прогон: показывает, что будет записано, и ничего не пишет.
Запись — с флагом --apply. Повтор после записи отвечает «уже перенесено» и файл НЕ
переписывает. Прежние источники (ключи meta, local.paths) НЕ удаляются: шаг только
печатает, что они больше не читаются.

СХЕМУ БАЗЫ ШАГ НЕ МЕНЯЕТ и в журнал схемы не пишет вовсе — как соседние шаги без изменения
схемы (20260808-backfill-addressee и другие): журнал отмечает перемены схемы, а здесь она
не меняется. База открывается только на чтение.
Поэтому шага нет в schema_step_order.STEPS: он назван там в перечне NOT_SCHEMA_STEPS, сборка
нового контура его не применяет (у нового контура нечего переносить), а у живого контура
его зовут рукой по документу выпуска.

    python <скрипты>/migrations/20261005-local-paths-file.py            # холостой прогон
    python <скрипты>/migrations/20261005-local-paths-file.py --apply    # записать файл
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import mezo_paths  # noqa: E402

FILE_PARTS = ("local", "paths.json")                    # внутри каталога .mezosync
META_KEYS = ("mirror_repo", "template_checkout", "disk_layer_tool")
OLD_FILE_KEYS = ("container", "template")
# ПРЕЖНЯЯ РАСКЛАДКА АВТОРА — единственное место, где эти имена допустимы (см. шапку).
AUTHOR_LAYOUT = (
    ("coordination_dir", "atlas.archs/.mezosync/coordination"),
    ("generated_dir", "atlas.archs/.mezosync/coordination/generated"),
    ("prompts_dir", "atlas.archs/.mezosync/prompts"),
    ("spa_src", "atlas.studio/Src/Atlas.Studio.Spa/src"),
    ("annex_dir", "atlas.archs/.mezosync/rules-annex"),
)
KEY_ORDER = ("mirror_repo", "template_checkout", "disk_layer_tool", "container", "template",
             "coordination_dir", "generated_dir", "prompts_dir", "spa_src", "annex_dir")


def read_old_local_paths(path: Path) -> dict:
    """Строки key=value прежнего local.paths — только нужные ключи, пустые отброшены."""
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        for key in OLD_FILE_KEYS:
            if line.startswith(key + "="):
                value = line.split("=", 1)[1].strip()
                if value:
                    found[key] = value
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description="перенос путей контура в один файл .mezosync/local/paths.json: по умолчанию "
                    "холостой прогон (показ), запись — с --apply; повтор файл не переписывает")
    ap.add_argument("--db", default=None, help="путь к базе; без него — живая база контура")
    ap.add_argument("--apply", action="store_true", help="ЗАПИСАТЬ файл (без флага — только показ)")
    a = ap.parse_args()
    db = mezo_paths.resolve_db(a.db, __file__, readonly=not a.apply)
    mezo_dir = db.parent                               # каталог .mezosync этой базы
    container = mezo_dir.parent
    target = mezo_dir / FILE_PARTS[0] / FILE_PARTS[1]
    print(f"📂 БАЗА: {db}")
    print(f"📄 ФАЙЛ ПУТЕЙ: {target.as_posix()}")

    # ── Файл уже есть: «уже перенесено», ничего не переписываем ───────────────────────────
    if target.exists():
        try:
            have = json.loads(target.read_text(encoding="utf-8-sig"))
            if not isinstance(have, dict):
                raise ValueError("верхний уровень не объект «ключ → путь»")
        except (OSError, ValueError) as e:
            print(f"⛔ файл путей есть, но не читается: {e.__class__.__name__}: {e}")
            print("   Не переписываю: починить его должен человек — перенос молча затёр бы "
                  "то, что в нём было.")
            return 1
        print(f"✅ уже перенесено: файл путей есть ({len(have)} ключей: "
              f"{', '.join(sorted(have)) or 'пусто'}). Файл не переписываю.")
        _report_missing_old_keys(db, mezo_dir, container, set(have))
        _print_old_sources_note()
        return 0

    # ── Собираем из прежних источников ────────────────────────────────────────────────────
    entries = {}
    where = {}
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=10)
    try:
        for key in META_KEYS:
            try:
                row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
            except sqlite3.Error:
                row = None
            if row and (row[0] or "").strip():
                entries[key] = row[0].strip()
                where[key] = "из таблицы meta"
    finally:
        con.close()
    old_files = [(mezo_dir / "scripts" / "local.paths", "из local.paths рядом с инструментами"),
                 (container / "vnext-tools" / "local.paths",
                  "из vnext-tools/local.paths (раскладка контура-автора)")]
    for path, label in old_files:
        if not path.is_file():
            continue
        for key, value in read_old_local_paths(path).items():
            if key not in entries:
                entries[key] = value
                where[key] = label
    print("ℹ️ прежняя раскладка автора (контур Atlas): каталоги ниже вписываются ТОЛЬКО если "
          "они есть на диске этого контура; остальные ключи читаются по стандартной раскладке пакета")
    for key, rel in AUTHOR_LAYOUT:
        if (container / rel).is_dir():
            entries[key] = rel
            where[key] = "раскладка автора: каталог есть на диске"
        else:
            print(f"   · {key}: каталога {rel} на диске нет — ключ не вписываю")
    ordered = {k: entries[k] for k in KEY_ORDER if k in entries}

    if not ordered:
        print("✅ нечего переносить: в meta нет ключей путей, local.paths нет, каталогов "
              "раскладки автора на диске нет. Файл не создаю — инструменты читают стандартную "
              "раскладку пакета.")
        _print_journal_note()
        return 0

    print(f"К ЗАПИСИ — {len(ordered)} ключей:")
    for key, value in ordered.items():
        print(f"   {key} = {value}   ({where[key]})")
    body = json.dumps(ordered, ensure_ascii=False, indent=2) + "\n"

    if not a.apply:
        print("\n🔍 ХОЛОСТОЙ ПРОГОН: файл НЕ записан, база не тронута. Записать — тем же вызовом "
              "с --apply.")
        _print_old_sources_note()
        _print_journal_note()
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(body.encode("utf-8"))
    os.replace(tmp, target)
    back = json.loads(target.read_text(encoding="utf-8"))
    if back != ordered:
        print("⛔ файл записан, но при чтении назад не совпал с задуманным — проверь его глазами.")
        return 1
    print(f"\n✅ ЗАПИСАНО: {target.as_posix()} ({len(back)} ключей), прочитано назад — совпало.")
    _print_old_sources_note()
    _print_journal_note()
    return 0


def _report_missing_old_keys(db, mezo_dir, container, have_keys):
    """Файл уже есть: назвать ключи, которые прежние источники ещё несут, а в файле их нет."""
    missing = []
    try:
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=10)
        try:
            for key in META_KEYS:
                row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
                if row and (row[0] or "").strip() and key not in have_keys:
                    missing.append(f"{key} (meta)")
        finally:
            con.close()
    except sqlite3.Error:
        pass
    for path in (mezo_dir / "scripts" / "local.paths", container / "vnext-tools" / "local.paths"):
        if path.is_file():
            for key in read_old_local_paths(path):
                if key not in have_keys:
                    missing.append(f"{key} ({path.name})")
    if missing:
        print(f"⚠️ прежние источники несут ключи, которых в файле нет: {', '.join(missing)}. "
              "Файл не трогаю: допиши их руками, если они нужны.")


def _print_old_sources_note():
    print("ℹ️ прежние источники НЕ удалены, но больше не читаются: ключи mirror_repo, "
          "template_checkout, disk_layer_tool в таблице meta и строки container=/template= "
          "в local.paths. Ключ template_source (адрес пакета) остаётся в meta и читается как раньше.")


def _print_journal_note():
    print("ℹ️ шаг не меняет схему базы и в журнал схемы не пишет (как соседние шаги без "
          "изменения схемы); повтор после записи ответит «уже перенесено».")


if __name__ == "__main__":
    sys.exit(main())
