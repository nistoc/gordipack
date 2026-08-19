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
  · ФАЙЛ, ПРАВЛЕННЫЙ У СЕБЯ, НЕ ЗАТИРАЕТСЯ — и теперь это ПРАВДА, а не обещание.
    🪤 До 19.08 эта строка стояла здесь при коде, который её не исполнял: список правленых
    собирался безусловно, а рядом печаталось честное «свои правки НЕ различает». Правда была
    в предупреждении, ложь — в шапке, а шапку роль читает ПЕРВОЙ. Нашёл сосед (контур tapas,
    ответ 19.08 10:46 UTC) и отказался брать инструменты, пока противоречие не снято, —
    справедливо: без честной цены решение принять нельзя.
    КАК РАЗЛИЧАЕТСЯ: при установке и при каждом обновлении записываются отпечатки положенных
    файлов. Свой правленый = отличается И от источника, И от отпечатка установки.
  · ⛔ ОТПЕЧАТКОВ НЕТ (контур собран раньше, чем их стали писать) — различить нечем, и это
    ГОВОРИТСЯ ВСЛУХ. Такие файлы не обновляются молча: нужен явный --overwrite-unknown;
  · ⛔ без --apply не пишется ничего.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
    # 🪤 КОНТУР-АВТОР ШАБЛОНА НЕ МОЖЕТ ЗАБИРАТЬ ИЗ НЕГО ФАЙЛЫ: его живые инструменты — ИСТОЧНИК
    # правок, а не отставшая копия, и «обновление» затёрло бы работу в обратную сторону.
    # Но происхождение записать ему всё равно нужно: 19.08 выяснилось, что мы сами не можем
    # ответить, на какой версии шаблона живём. ⇒ отдельный режим: записать и ничего не трогать.
    ap.add_argument("--record-only", action="store_true",
                    help="только записать источник и версию в контур, файлы НЕ трогать")
    ap.add_argument("--overwrite-unknown", action="store_true",
                    help="перезаписать и те файлы, у которых нет отпечатка установки "
                         "(различить свою правку нечем — согласие называется явно)")
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

    if a.record_only:
        src_dir, rev, temporary = fetch(source)
        try:
            # ⚖️ ОТПЕЧАТКИ ПИШУТСЯ И ЗДЕСЬ — иначе контур, собранный до появления этой записи,
            # так и остался бы без «до чего он был правлен», и первое же обновление не смогло бы
            # отличить его правку от свежести источника. Отпечаток снимается с ТОГО, ЧТО ЛЕЖИТ
            # СЕЙЧАС: он говорит «вот с чем сравнивать дальше», а не «это пришло из источника».
            tools_now = pathlib.Path(mezo_paths.live_scripts())
            имена = {f.name for f in (src_dir / "scripts").glob("*.py")}
            звенья = src_dir / "vnext" / "prototype"
            if звенья.is_dir():
                имена |= {f.name for f in звенья.glob("*.py")}
            печати = {f.name: digest(f.read_bytes())
                      for f in sorted(tools_now.glob("*.py")) if f.name in имена}
            conn = sqlite3.connect(str(db))
            for k, v in (("template_source", source), ("template_commit", rev),
                         ("template_files_sha", json.dumps(печати, ensure_ascii=False)),
                         ("template_recorded_at",
                          conn.execute("SELECT strftime('%Y-%m-%d %H:%M', 'now')")
                          .fetchone()[0] + " UTC")):
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                             "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
            conn.commit()
            conn.close()
            print(f"✅ Записано происхождение: {source} · версия {rev} · "
                  f"отпечатков установки {len(печати)}")
            print("   Файлы НЕ тронуты: это режим записи, а не обновления.")
        finally:
            if temporary:
                shutil.rmtree(src_dir, ignore_errors=True)
        return 0

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

        # 🪤 ИСТОЧНИК — ДВА КАТАЛОГА, А НЕ ОДИН. Обновлятор обходил только scripts/, а семь
        # звеньев, которые зовёт общий прогон, лежат в источнике в vnext/prototype/ и при
        # сборке кладутся потребителю РЯДОМ со скриптами. Они не обновлялись НИКОГДА, и
        # инструмент об этом молчал: частичный охват, читаемый как полный. Нашёл сосед
        # (контур tapas, 19.08 10:46 UTC) — у него два таких звена уже разошлись.
        источник = {}
        for f in sorted(src_tools.rglob("*.py")):
            источник[f.relative_to(src_tools)] = f
        звенья = src_dir / "vnext" / "prototype"
        вне_охвата = []
        if звенья.is_dir():
            for f in sorted(звенья.glob("*.py")):
                rel = pathlib.Path(f.name)
                if rel in источник:
                    continue
                if (tools / rel).exists():
                    источник[rel] = f          # звено уже стои́т у нас — обновляем его
                else:
                    вне_охвата.append(rel)     # звена у нас нет: сборка его не клала

        отпечатки = json.loads(got.get("template_files_sha") or "{}")
        свежие, свои, новые, неизвестные = [], [], [], []
        for rel, f in sorted(источник.items()):
            mine = tools / rel
            if not mine.exists():
                новые.append(rel)
                continue
            моё = mine.read_bytes()
            if same_text(моё, f.read_bytes()):
                continue
            печать = отпечатки.get(str(rel).replace(chr(92), "/"))
            if печать is None:
                неизвестные.append(rel)
            elif digest(моё) != печать:
                свои.append(rel)               # правлен У СЕБЯ — не трогаем
            else:
                свежие.append(rel)

        for rel in новые:
            print(f"   + {str(rel):40} нет у нас — появится")
        for rel in свежие:
            print(f"   ≠ {str(rel):40} отличается — обновится")
        for rel in свои:
            print(f"   ✋ {str(rel):40} ПРАВЛЕН У ТЕБЯ — НЕ трогаем")
        for rel in неизвестные:
            print(f"   ❓ {str(rel):40} отличается, но отпечатка установки нет")
        if not (свежие or новые or свои or неизвестные):
            print("   инструменты совпадают с источником — забирать нечего")
        print()
        print("⚖️ Сличалось СОДЕРЖИМОЕ, а не байты: окончания строк приведены, иначе "
              "переехавший файл выглядит переписанным целиком.")
        if свои:
            print(f"✋ Своих правок: {len(свои)} — они НЕ будут затёрты. Хочешь взять свежее — "
                  f"перенеси свою правку сам или удали файл.")
        if неизвестные:
            print(f"❓ Отпечатков установки нет у {len(неизвестные)} файлов: контур собран "
                  f"раньше, чем их стали писать.{NEWLINE}   Различить «правил ты» и «правил "
                  f"источник» НЕЧЕМ. Молча они не обновятся — нужен --overwrite-unknown, "
                  f"и тогда{NEWLINE}   свои правки в этих файлах будут потеряны. Это цена, "
                  f"названная ДО действия.")
        if вне_охвата:
            print(f"ℹ️ Вне обновления: {len(вне_охвата)} звеньев источника, которых у тебя нет "
                  f"({', '.join(str(x) for x in вне_охвата[:4])}"
                  f"{'…' if len(вне_охвата) > 4 else ''}).{NEWLINE}   Их кладёт сборка контура "
                  f"по тому, что зовут скрипты, — обновление их не приносит и не выдумывает.")

        if not a.apply:
            print(f"{NEWLINE}[ПЛАН] Ничего не записано. Забрать: тот же вызов с --apply")
            return 0

        берём = свежие + новые + (неизвестные if a.overwrite_unknown else [])
        for rel in берём:
            (tools / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(источник[rel], tools / rel)
        # 🪤 ОТПЕЧАТОК ОБНОВЛЯЕТСЯ ТОЛЬКО У ТОГО, ЧТО МЫ ПОЛОЖИЛИ САМИ. Первая редакция
        # переписывала отпечатки ВСЕХ файлов подряд — в том числе тех, что роль правила
        # у себя и которые мы честно не тронули. Их правка становилась «тем, что мы
        # установили», и следующее обновление затёрло бы её МОЛЧА, считая неправленой.
        # ⇒ Обещание сохранности держалось бы ровно один заход. Поймано приёмкой (⑧),
        # а не рассуждением: контроль без отпечатков проходил, потому что отпечатки
        # тут же появлялись заново.
        новые_отпечатки = dict(отпечатки)
        for rel in берём:
            mine = tools / rel
            if mine.exists():
                новые_отпечатки[str(rel).replace(chr(92), "/")] = digest(mine.read_bytes())
        conn = sqlite3.connect(str(db))
        for k, v in (("template_commit", rev), ("template_source", source),
                     ("template_files_sha", json.dumps(новые_отпечатки, ensure_ascii=False))):
            conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
        conn.commit()
        conn.close()
        print(f"{NEWLINE}✅ Забрано файлов: {len(берём)} · записана версия {rev} · "
              f"отпечатков установки записано {len(новые_отпечатки)}")
        if свои:
            print(f"✋ НЕ тронуто твоих правок: {len(свои)} — " + " · ".join(str(x) for x in свои))
        if неизвестные and not a.overwrite_unknown:
            print(f"❓ НЕ тронуто без отпечатка: {len(неизвестные)} — теперь отпечатки есть, "
                  f"и следующий заход скажет про них определённо.")
        print("👉 ОБЯЗАТЕЛЬНО СЛЕДОМ: прогони свои проверки (guard-all.py). Инструмент, "
              "приехавший и не прогнанный, — это не обновление, а надежда.")
        return 0
    finally:
        if temporary:
            shutil.rmtree(src_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
