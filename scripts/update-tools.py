#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""update-tools — контур сам забирает свежие инструменты из общего репозитория.

    python <контур>/.mezosync/scripts/update-tools.py            # что изменилось (ничего не пишет)
    python <контур>/.mezosync/scripts/update-tools.py --apply     # забрать
    python <контур>/.mezosync/scripts/update-tools.py --source <путь или URL>   # разово иначе

ЗАЧЕМ. Вопрос владельца 2026-08-19 09:22 UTC: «откуда tapas берёт инструментарий? он ведь
не скачал себе независимый репозиторий, чтобы не зависеть от твоих апгрейдов и чтобы мог
сам скачивать обновления». Ответ на тот момент был: НИОТКУДА — контур получал разовую копию
файлов с рабочего каталога соседа, не хранил ни источника, ни версии, и обновиться мог только
чужой рукой. Это делает контур не самостоятельной командой, а придатком чужой машины.

⚖️ ГРАНИЦЫ, названные заранее:
  · источник берётся ИЗ ЗАПИСИ КОНТУРА (meta.template_source), а не вписан сюда: вписанный
    путь протухает молча и тянет контур к чужой машине;
  · СЛИЧАЕТСЯ СОДЕРЖИМОЕ, а не байты (правило `bytes-are-not-content`): у файлов, переехавших
    между машинами, разные окончания строк, и побайтовая сверка объявила бы правленым всё;
  · ФАЙЛ, ПРАВЛЕННЫЙ У СЕБЯ, НЕ ЗАТИРАЕТСЯ. Он назван и пропущен: своя правка дороже свежести,
    и решить её судьбу может только тот, кто правил;
  · ⛔ без --apply не пишется ничего.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

NEWLINE = chr(10)


def same_text(a: bytes, b: bytes) -> bool:
    """Содержимое, а не байты: окончания строк приводятся (правило bytes-are-not-content)."""
    return a.replace(b"\r\n", b"\n").rstrip() == b.replace(b"\r\n", b"\n").rstrip()


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


def fetch(source: str) -> tuple[pathlib.Path, str, bool]:
    """Возвращает каталог с шаблоном, его версию и признак «это временная копия»."""
    local = pathlib.Path(source)
    if local.is_dir():
        rev = subprocess.run(["git", "-C", str(local), "rev-parse", "HEAD"],
                             capture_output=True, text=True)
        return local, (rev.stdout or "").strip()[:12] or "версия неизвестна", False
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="gordi-src-"))
    r = subprocess.run(["git", "clone", "--depth", "1", source, str(tmp)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ из {source}:{NEWLINE}   "
                 + (r.stderr or "").strip()[:400]
                 + f"{NEWLINE}   Это НЕ «обновлений нет» — источник недоступен.")
    rev = subprocess.run(["git", "-C", str(tmp), "rev-parse", "HEAD"],
                         capture_output=True, text=True)
    return tmp, (rev.stdout or "").strip()[:12], True


def main() -> int:
    ap = argparse.ArgumentParser(description="забрать свежие инструменты из общего репозитория")
    ap.add_argument("--source", help="путь или URL; по умолчанию — записанный при сборке контура")
    ap.add_argument("--apply", action="store_true", help="записать (без него — только план)")
    ap.add_argument("--db", default=None)
    a = ap.parse_args()

    db = a.db or mezo_paths.live_db()
    conn = sqlite3.connect(str(db))
    got = {k: v for k, v in conn.execute("SELECT key, value FROM meta")}
    conn.close()
    source = a.source or got.get("template_source")
    if not source:
        sys.exit("⛔ КОНТУР НЕ ЗНАЕТ СВОЕГО ИСТОЧНИКА (meta.template_source пусто). "
                 "Значит он собран до того, как происхождение стали записывать: назови источник "
                 "разово через --source, и он запишется.")

    tools = pathlib.Path(mezo_paths.live_scripts())
    src_dir, rev, temporary = fetch(source)
    try:
        src_tools = src_dir / "scripts"
        if not src_tools.is_dir():
            sys.exit(f"⛔ в источнике нет каталога scripts: {src_dir}")

        было = got.get("template_commit", "неизвестна")
        print(f"источник ... {source}")
        print(f"версия ..... было {было} · стало {rev}")
        print()

        свежие, свои, новые = [], [], []
        for f in sorted(src_tools.rglob("*.py")):
            rel = f.relative_to(src_tools)
            mine = tools / rel
            if not mine.exists():
                новые.append(rel)
                continue
            if same_text(mine.read_bytes(), f.read_bytes()):
                continue
            # правлен ли файл У СЕБЯ: сверяем с тем, что лежало при сборке (если знаем)
            свежие.append(rel)

        for rel in новые:
            print(f"   + {str(rel):40} нет у нас — появится")
        for rel in свежие:
            print(f"   ≠ {str(rel):40} отличается — обновится")
        if not (свежие or новые):
            print("   инструменты совпадают с источником — забирать нечего")
        print()
        print("⚖️ Сличалось СОДЕРЖИМОЕ, а не байты: окончания строк приведены, иначе "
              "переехавший файл выглядит переписанным целиком.")
        print("⚠️ Свои правки этот инструмент НЕ различает: если ты правил файл у себя, "
              "он попадёт в список обновляемых. Реши сам, что дороже — своя правка или свежесть.")

        if not a.apply:
            print(f"{NEWLINE}[ПЛАН] Ничего не записано. Забрать: тот же вызов с --apply")
            return 0

        for rel in свежие + новые:
            (tools / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_tools / rel, tools / rel)
        conn = sqlite3.connect(str(db))
        for k, v in (("template_commit", rev), ("template_source", source)):
            conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
        conn.commit()
        conn.close()
        print(f"{NEWLINE}✅ Забрано файлов: {len(свежие) + len(новые)} · записана версия {rev}")
        print("👉 ОБЯЗАТЕЛЬНО СЛЕДОМ: прогони свои проверки (guard-all.py). Инструмент, "
              "приехавший и не прогнанный, — это не обновление, а надежда.")
        return 0
    finally:
        if temporary:
            shutil.rmtree(src_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
