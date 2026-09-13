#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""update-tools — контур сам забирает свежие инструменты из общего репозитория.

    python <контур>/.mezosync/scripts/update-tools.py            # что изменилось (ничего не пишет)
    python <контур>/.mezosync/scripts/update-tools.py --apply     # забрать
    python <контур>/.mezosync/scripts/update-tools.py --source <путь или URL>   # разово иначе
    python <контур>/.mezosync/scripts/update-tools.py --source <...> --rev <коммит>  # РОВНО эта версия
    python <контур>/.mezosync/scripts/update-tools.py --source <...> --record-source  # ЗАПОМНИТЬ этот источник

ЗАЧЕМ. Вопрос владельца 2026-08-19 09:22 UTC: «откуда tapas берёт инструментарий? он ведь
не скачал себе независимый репозиторий, чтобы не зависеть от твоих апгрейдов и чтобы мог
сам скачивать обновления». Ответ на тот момент был: НИОТКУДА — контур получал разовую копию
файлов с рабочего каталога соседа, не хранил ни источника, ни версии, и обновиться мог только
чужой рукой. Это делает контур не самостоятельной командой, а придатком чужой машины.

⚖️ ГРАНИЦЫ, названные заранее:
  · источник берётся ИЗ ЗАПИСИ КОНТУРА (meta.template_source), а не вписан сюда: вписанный
    путь протухает молча и тянет контур к чужой машине;
  · 🪤 --source НА ОДИН РАЗ НЕ СТАНОВИТСЯ ЗАПИСЬЮ МОЛЧА (карточка #604 ②). До этой правки
    любой --source, даже разовый, тут же перезаписывал meta.template_source — сосед (tapas)
    один раз дал --source локальной папки, чтобы взять ПРОВЕРЕННУЮ версию, и запись контура
    молча стала указывать на чужую машину. Теперь meta.template_source трогается только
    когда он ещё пуст (первая запись) ИЛИ по явному --record-source; --rev так же не
    записывается в источник — только в template_commit, тем коммитом, который реально взят;
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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

NEWLINE = chr(10)


def same_text(a: bytes, b: bytes) -> bool:
    """Содержимое, а не байты: окончания строк приводятся (правило bytes-are-not-content)."""
    return a.replace(b"\r\n", b"\n").rstrip() == b.replace(b"\r\n", b"\n").rstrip()


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


def find_last_match(repo: pathlib.Path, git_rel: str, target: bytes) -> tuple[str, str] | tuple[None, None]:
    """Карточка #604 ③: последний коммит истории source, где файл совпадал (same_text) с этим.

    Сравнение — ТО ЖЕ same_text, что и везде в инструменте: окончания строк приведены,
    иначе переехавший файл выглядит переписанным целиком. `repo` обязан быть git-репозиторием
    С ИСТОРИЕЙ (не архивной распаковкой без .git) — вызывающий отвечает за это сам.
    Ничего не находит — возвращает (None, None): «в истории пакета такого содержимого нет»
    ЭТО ОТДЕЛЬНЫЙ ответ, не то же самое, что ошибка git.
    """
    log = subprocess.run(["git", "-C", str(repo), "log", "--format=%H|%as", "--", git_rel],
                         capture_output=True, text=True)
    for line in (log.stdout or "").splitlines():
        if "|" not in line:
            continue
        commit_hash, date = line.split("|", 1)
        show = subprocess.run(["git", "-C", str(repo), "show", f"{commit_hash}:{git_rel}"],
                              capture_output=True)
        if show.returncode == 0 and same_text(target, show.stdout):
            return date, commit_hash[:12]
    return None, None


def fetch(source: str, rev: str | None = None) -> tuple[pathlib.Path, str, bool]:
    """Возвращает каталог с шаблоном, его версию и признак «это временная копия».

    🩸 УБОРКА ЗДЕСЬ БЫЛА — И МОЛЧА НЕ РАБОТАЛА (замер PROTO 2026-08-24 16:39 UTC).
    Стояло `shutil.rmtree(..., ignore_errors=True)` в двух блоках finally, то есть
    на всех путях выхода. И всё равно во временном каталоге машины лежало 245 копий
    репозитория образца.
    ```
    опыт на КОПИИ одного из остатков:
      rmtree(ignore_errors=True) .............. каталог ОСТАЛСЯ
      rmtree со снятием метки только-чтения ... каталог удалён
    ```
    ⇒ `git clone` помечает файлы внутри `.git` только для чтения; Windows не даёт их
    удалить, а `ignore_errors=True` ГЛОТАЕТ этот отказ. Уборка выполнялась, ничего
    не убирала и ни разу об этом не сказала.
    🎯 Класс наш же и записанный: **молчащий отказ читается как успех.** Здесь он
    прожил дольше обычного именно потому, что уборка была НАПИСАНА — её наличие
    закрывало вопрос, а проверял ли кто-нибудь её действие, никто не спрашивал.
    ⚖️ И заявка называла причину иначе — «уборка стои́т не на всех путях выхода».
    Пути были все; ложным было не место, а действие.
    """
    local = pathlib.Path(source)
    if local.is_dir():
        if rev:
            # 🪤 --rev У ЛОКАЛЬНОЙ ПАПКИ (карточка #604 ②а): рабочую копию источника НЕ
            # трогаем — ни checkout, ни ветку. Нужную версию достаём git archive во
            # ВРЕМЕННЫЙ каталог; local остаётся ровно тем, чем был до вызова.
            resolved = subprocess.run(["git", "-C", str(local), "rev-parse", rev],
                                      capture_output=True, text=True)
            if resolved.returncode != 0:
                sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: версии {rev} нет в {source} "
                         f"(рабочая копия источника НЕ ТРОНУТА):{NEWLINE}   "
                         + (resolved.stderr or "").strip()[:400])
            commit = (resolved.stdout or "").strip()
            archive = subprocess.run(["git", "-C", str(local), "archive", "--format=tar", commit],
                                     capture_output=True)
            if archive.returncode != 0:
                sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: git archive версии {rev} из {source} не удался:"
                         f"{NEWLINE}   "
                         + (archive.stderr or b"").decode("utf-8", "replace").strip()[:400])
            tmp = mezo_stand.new("gordi-src-")
            untar = subprocess.run(["tar", "-x", "-C", str(tmp)], input=archive.stdout)
            if untar.returncode != 0:
                mezo_stand.release(tmp)  # уборка отложена до исхода прогона
                sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: распаковка версии {rev} из {source} не удалась.")
            return tmp, commit[:12], True
        rev_out = subprocess.run(["git", "-C", str(local), "rev-parse", "HEAD"],
                             capture_output=True, text=True)
        return local, (rev_out.stdout or "").strip()[:12] or "версия неизвестна", False
    tmp = mezo_stand.new("gordi-src-")
    # 🪤 --rev У URL-ИСТОЧНИКА (карточка #604 ②а): --depth 1 везёт только последний коммит,
    # а нужный может быть в истории. Клонируем ПОЛНОСТЬЮ и берём коммит из неё, а не гадаем.
    clone_cmd = (["git", "clone", source, str(tmp)] if rev else
                ["git", "clone", "--depth", "1", source, str(tmp)])
    r = subprocess.run(clone_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона
        sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ из {source}:{NEWLINE}   "
                 + (r.stderr or "").strip()[:400]
                 + f"{NEWLINE}   Это НЕ «обновлений нет» — источник недоступен.")
    if rev:
        co = subprocess.run(["git", "-C", str(tmp), "checkout", "--detach", rev],
                            capture_output=True, text=True)
        if co.returncode != 0:
            mezo_stand.release(tmp)
            sys.exit(f"⛔ НЕ ЗАБРАЛОСЬ: версии {rev} нет в {source}:{NEWLINE}   "
                     + (co.stderr or "").strip()[:400])
    rev_out = subprocess.run(["git", "-C", str(tmp), "rev-parse", "HEAD"],
                         capture_output=True, text=True)
    return tmp, (rev_out.stdout or "").strip()[:12], True


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
    ap.add_argument("--rev", default=None,
                    help="взять из источника РОВНО этот коммит, а не HEAD/latest "
                         "(карточка #604 ②а)")
    ap.add_argument("--record-source", action="store_true",
                    help="ЗАПИСАТЬ meta.template_source этим --source, даже если источник "
                         "уже записан. Без флага источник в meta трогается только при первой "
                         "записи (карточка #604 ②б) — разовый --source в постоянную запись "
                         "не превращается")
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
        # ⚖️ --record-only ЯВНО ОЗНАЧАЕТ «записать источник» — это его единственный смысл,
        # поэтому охрана ②б (писать источник только по --record-source/первой записи) сюда
        # не распространяется: слово уже дано самим выбором этого режима.
        src_dir, rev, temporary = fetch(source, rev=a.rev)
        try:
            # ⚖️ ОТПЕЧАТКИ ПИШУТСЯ И ЗДЕСЬ — иначе контур, собранный до появления этой записи,
            # так и остался бы без «до чего он был правлен», и первое же обновление не смогло бы
            # отличить его правку от свежести источника. Отпечаток снимается с ТОГО, ЧТО ЛЕЖИТ
            # СЕЙЧАС: он говорит «вот с чем сравнивать дальше», а не «это пришло из источника».
            tools_now = pathlib.Path(mezo_paths.live_scripts())
            names = {f.name for f in (src_dir / "scripts").glob("*.py")}
            linked_dir = src_dir / "vnext" / "prototype"
            if linked_dir.is_dir():
                names |= {f.name for f in linked_dir.glob("*.py")}
            fingerprints = {f.name: digest(f.read_bytes())
                      for f in sorted(tools_now.glob("*.py")) if f.name in names}
            conn = sqlite3.connect(str(db))
            for k, v in (("template_source", source), ("template_commit", rev),
                         ("template_files_sha", json.dumps(fingerprints, ensure_ascii=False)),
                         ("template_recorded_at",
                          conn.execute("SELECT strftime('%Y-%m-%d %H:%M', 'now')")
                          .fetchone()[0] + " UTC")):
                conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                             "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
            conn.commit()
            conn.close()
            print(f"✅ Записано происхождение: {source} · версия {rev} · "
                  f"отпечатков установки {len(fingerprints)}")
            print("   Файлы НЕ тронуты: это режим записи, а не обновления.")
        finally:
            if temporary:
                mezo_stand.release(src_dir)   # 🩸 было `rmtree(ignore_errors=True)`
        return 0

    tools = pathlib.Path(mezo_paths.live_scripts())
    src_dir, rev, temporary = fetch(source, rev=a.rev)
    try:
        src_tools = src_dir / "scripts"
        if not src_tools.is_dir():
            sys.exit(f"⛔ в источнике нет каталога scripts: {src_dir}")

        previous_commit = got.get("template_commit", "неизвестна")
        print(f"источник ... {source}" + (f"  (--rev {a.rev})" if a.rev else ""))
        print(f"версия ..... было {previous_commit} · стало {rev}")
        print()

        # 🪤 ИСТОЧНИК — ДВА КАТАЛОГА, А НЕ ОДИН. Обновлятор обходил только scripts/, а семь
        # звеньев, которые зовёт общий прогон, лежат в источнике в vnext/prototype/ и при
        # сборке кладутся потребителю РЯДОМ со скриптами. Они не обновлялись НИКОГДА, и
        # инструмент об этом молчал: частичный охват, читаемый как полный. Нашёл сосед
        # (контур tapas, 19.08 10:46 UTC) — у него два таких звена уже разошлись.
        src_index = {}          # rel -> абсолютный путь у источника (что копировать)
        git_rel_of = {}         # rel -> путь ВНУТРИ git-репозитория источника (для истории, ③)
        for f in sorted(src_tools.rglob("*.py")):
            rel = f.relative_to(src_tools)
            src_index[rel] = f
            git_rel_of[rel] = "scripts/" + rel.as_posix()
        linked_dir = src_dir / "vnext" / "prototype"
        out_of_scope = []
        if linked_dir.is_dir():
            for f in sorted(linked_dir.glob("*.py")):
                rel = pathlib.Path(f.name)
                if rel in src_index:
                    continue
                if (tools / rel).exists():
                    src_index[rel] = f          # звено уже стои́т у нас — обновляем его
                    git_rel_of[rel] = "vnext/prototype/" + f.name
                else:
                    out_of_scope.append(rel)    # звена у нас нет: сборка его не клала

        fingerprints = json.loads(got.get("template_files_sha") or "{}")
        fresh, own_edits, new_files, unknown = [], [], [], []
        for rel, f in sorted(src_index.items()):
            mine = tools / rel
            if not mine.exists():
                new_files.append(rel)
                continue
            mine_bytes = mine.read_bytes()
            if same_text(mine_bytes, f.read_bytes()):
                continue
            installed_fp = fingerprints.get(str(rel).replace(chr(92), "/"))
            if installed_fp is None:
                unknown.append(rel)
            elif digest(mine_bytes) != installed_fp:
                own_edits.append(rel)          # правлен У СЕБЯ — не трогаем
            else:
                fresh.append(rel)

        for rel in new_files:
            print(f"   + {str(rel):40} нет у нас — появится")
        for rel in fresh:
            print(f"   ≠ {str(rel):40} отличается — обновится")
        for rel in own_edits:
            print(f"   ✋ {str(rel):40} ПРАВЛЕН У ТЕБЯ — НЕ трогаем")

        # 🪤 КАРТОЧКА #604 ③: у «❓» датой и коммитом называем ПОСЛЕДНЕЕ совпадение с историей
        # источника — иначе «❓» читается как «не смотрели», а не «застряли месяц назад»
        # (шесть таких файлов у tapas стояли на пакете 20.08 почти месяц, никто не заметил).
        # История нужна только когда есть хоть один «❓» — иначе это лишний git-вызов впустую.
        history = {}
        if unknown:
            source_as_dir = pathlib.Path(source)
            history_repo = source_as_dir if source_as_dir.is_dir() else src_dir
            if (history_repo / ".git").is_dir():
                if (history_repo / ".git" / "shallow").exists():
                    # клон был --depth 1 — истории в нём нет, догружаем ПОЛНОСТЬЮ
                    subprocess.run(["git", "-C", str(history_repo), "fetch", "--unshallow"],
                                   capture_output=True, text=True)
                for rel in unknown:
                    git_rel = git_rel_of.get(rel)
                    history[rel] = (find_last_match(history_repo, git_rel,
                                                     (tools / rel).read_bytes())
                                    if git_rel else (None, None))
            else:
                # источник — не git (или архивная распаковка без истории): сказать честно,
                # а не выдумать дату
                history = {rel: (None, None) for rel in unknown}
        for rel in unknown:
            date, found_commit = history.get(rel, (None, None))
            tail = (f" — последний раз совпадал с пакетом: {date}, коммит {found_commit}"
                   if date else " — в истории пакета такого содержимого нет")
            print(f"   ❓ {str(rel):40} отличается, но отпечатка установки нет{tail}")
        if not (fresh or new_files or own_edits or unknown):
            print("   инструменты совпадают с источником — забирать нечего")
        print()
        print("⚖️ Сличалось СОДЕРЖИМОЕ, а не байты: окончания строк приведены, иначе "
              "переехавший файл выглядит переписанным целиком.")
        if own_edits:
            print(f"✋ Своих правок: {len(own_edits)} — они НЕ будут затёрты. Хочешь взять свежее — "
                  f"перенеси свою правку сам или удали файл.")
        if unknown:
            print(f"❓ Отпечатков установки нет у {len(unknown)} файлов: контур собран "
                  f"раньше, чем их стали писать.{NEWLINE}   Различить «правил ты» и «правил "
                  f"источник» НЕЧЕМ. Молча они не обновятся — нужен --overwrite-unknown, "
                  f"и тогда{NEWLINE}   свои правки в этих файлах будут потеряны. Это цена, "
                  f"названная ДО действия.")
        if out_of_scope:
            print(f"ℹ️ Вне обновления: {len(out_of_scope)} звеньев источника, которых у тебя нет "
                  f"({', '.join(str(x) for x in out_of_scope[:4])}"
                  f"{'…' if len(out_of_scope) > 4 else ''}).{NEWLINE}   Их кладёт сборка контура "
                  f"по тому, что зовут скрипты, — обновление их не приносит и не выдумывает.")

        # 🪤 КАРТОЧКА #604 ②б: --source НА ОДИН РАЗ НЕ СТАНОВИТСЯ ЗАПИСЬЮ МОЛЧА. Источник
        # в meta трогается только когда он ещё пуст (первая запись) или по явному
        # --record-source; иначе он остаётся тем, что уже записано. template_commit
        # пишется ВСЕГДА — тем коммитом, который реально взят (a.rev или HEAD).
        recorded_source = got.get("template_source")
        write_source = bool(a.record_source) or not recorded_source

        if not a.apply:
            print(f"{NEWLINE}[ПЛАН] Ничего не записано. Забрать: тот же вызов с --apply")
            return 0

        taking = fresh + new_files + (unknown if a.overwrite_unknown else [])
        for rel in taking:
            (tools / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_index[rel], tools / rel)
        # 🪤 ОТПЕЧАТОК ОБНОВЛЯЕТСЯ ТОЛЬКО У ТОГО, ЧТО МЫ ПОЛОЖИЛИ САМИ. Первая редакция
        # переписывала отпечатки ВСЕХ файлов подряд — в том числе тех, что роль правила
        # у себя и которые мы честно не тронули. Их правка становилась «тем, что мы
        # установили», и следующее обновление затёрло бы её МОЛЧА, считая неправленой.
        # ⇒ Обещание сохранности держалось бы ровно один заход. Поймано приёмкой (⑧),
        # а не рассуждением: контроль без отпечатков проходил, потому что отпечатки
        # тут же появлялись заново.
        updated_fingerprints = dict(fingerprints)
        for rel in taking:
            mine = tools / rel
            if mine.exists():
                updated_fingerprints[str(rel).replace(chr(92), "/")] = digest(mine.read_bytes())
        meta_updates = [("template_commit", rev),
                        ("template_files_sha", json.dumps(updated_fingerprints, ensure_ascii=False))]
        if write_source:
            meta_updates.append(("template_source", source))
        conn = sqlite3.connect(str(db))
        for k, v in meta_updates:
            conn.execute("INSERT INTO meta (key, value) VALUES (?, ?) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (k, v))
        conn.commit()
        conn.close()
        print(f"{NEWLINE}✅ Забрано файлов: {len(taking)} · записана версия {rev} · "
              f"отпечатков установки записано {len(updated_fingerprints)}")
        print("источник в meta: " + (f"записан {source}" if write_source
                                     else f"оставлен {recorded_source}"))
        if own_edits:
            print(f"✋ НЕ тронуто твоих правок: {len(own_edits)} — "
                  + " · ".join(str(x) for x in own_edits))
        if unknown and not a.overwrite_unknown:
            print(f"❓ НЕ тронуто без отпечатка: {len(unknown)} — теперь отпечатки есть, "
                  f"и следующий прогон скажет про них определённо.")
        print("👉 ОБЯЗАТЕЛЬНО СЛЕДОМ: прогони свои проверки (guard-all.py). Инструмент, "
              "приехавший и не прогнанный, — это не обновление, а надежда.")
        return 0
    finally:
        if temporary:
            mezo_stand.release(src_dir)   # 🩸 было `rmtree(ignore_errors=True)` — см. шапку fetch()


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
