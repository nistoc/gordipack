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
UNKNOWN_VERSION = "версия неизвестна"   # заглушка fetch(), когда у источника нет HEAD вовсе


def same_text(a: bytes, b: bytes) -> bool:
    """Содержимое, а не байты: окончания строк приводятся (правило bytes-are-not-content)."""
    return a.replace(b"\r\n", b"\n").rstrip() == b.replace(b"\r\n", b"\n").rstrip()


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n").rstrip()).hexdigest()[:12]


def git_history_root(path: pathlib.Path) -> tuple[pathlib.Path | None, str]:
    """Есть ли у `path` полноценная git-история — спрошено у git, а не угадано по файлам.

    🩸 ВОЗВРАТ OPSSRE №1 (карточка #604 ③-1): прежняя проверка смотрела `(path / ".git").is_dir()`.
    Она ошибается в ДВЕ стороны разом:
      · выгрузка БЕЗ .git (архив, копия диска) — верно говорит «истории нет»;
      · git WORKTREE — у него `.git` это ФАЙЛ (`gitdir: .../worktrees/<имя>`), не каталог,
        и `.is_dir()` отвечает «не git» ОШИБОЧНО, хотя история там полная и доступна.
    Замер OPSSRE: на выгрузке без .git — 38 ложных находок из 45; на worktree — 44 из 45.
    `git rev-parse --git-dir` понимает ОБЕ формы — он и есть источник правды, не имя файла.

    🩸 ВОЗВРАТ OPSSRE №2 (карточка #604 ③-1в): `git rev-parse --git-dir` идёт ВВЕРХ по дереву
    каталогов, если у `path` нет своего `.git`, и находит .git ЧУЖОГО репозитория — например,
    `path` лежит подкаталогом внутри ДРУГОГО git-проекта (свой пакет скопирован в подпапку
    чужого репо). Прежняя редакция принимала такой найденный git ЗА ИСТОРИЮ ПАКЕТА и искала
    в НЕЙ — то есть не в той истории. Замер OPSSRE: 46 ложных «нет в истории» из 47 (и для
    закоммиченной, и для незакоммиченной внутри чужого репо копии — коммит тут ни при чём,
    беда в том, ЧЕЙ это .git). Различитель — `git rev-parse --show-prefix`: пусто ⇒ `path`
    САМ является корнем рабочего дерева найденного репозитория (историю берём); не пусто ⇒
    `path` — подкаталог ЧУЖОГО репозитория, историю не берём и называем корень чужого явно.

    Возвращает (path, "") — история есть, опрашивай `path` как обычно;
    (None, причина) — истории нет, причина ДЛЯ ЧЕЛОВЕКА, а не код ошибки.
    """
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "--git-dir"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        reason = ("источник не git-репозиторий" if "not a git repository" in err.lower()
                 else (err[:200] or "git rev-parse --git-dir отказал без сообщения"))
        return None, reason
    prefix = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-prefix"],
                            capture_output=True, text=True)
    if (prefix.stdout or "").strip():
        top = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True)
        outer_root = (top.stdout or "").strip() or "корень не определился"
        return None, f"каталог внутри другого репозитория ({outer_root})"
    return path, ""


def is_shallow_clone(repo: pathlib.Path) -> bool:
    """Спрошено у git (`--is-shallow-repository`), а не угадано по файлу `.git/shallow` —
    тот же класс ошибки, что и у git_history_root: у worktree `.git` не каталог, и путь
    `.git/shallow` там не существует НЕЗАВИСИМО от того, мелкий репозиторий или полный."""
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--is-shallow-repository"],
                       capture_output=True, text=True)
    return (r.stdout or "").strip() == "true"


def find_version_span(repo: pathlib.Path, git_rel: str, target: bytes,
                      anchor_rev: str | None = None) -> dict:
    """Карточка #604 ③-2 (возврат OPSSRE): подпись несёт ДВЕ даты — появления версии И
    следующей смены, а не одну.

    ⚖️ ЧТО БЫЛО НЕ ТАК — НАЗВАНО ТОЧНО, а не пересказано наоборот. ДЕНЬ прежний код УЖЕ
    печатал верный — коммит, где версия ПОЯВИЛАСЬ (это и есть первое newest-first совпадение
    при обходе истории пути: `git log -- path` перечисляет только коммиты, менявшие путь,
    и одиночное совпадение — всегда коммит появления, второго такого не бывает, пока
    содержимое не встретится ПОВТОРНО после промежуточных правок). НЕВЕРНОЙ была ПОДПИСЬ —
    «последний раз совпадал с пакетом» звучит как «недавно», хотя дата могла быть месячной
    давности, а сколько версия провисела ПОСЛЕ появления, подпись не говорила вовсе. Живой
    пример OPSSRE: mention.py появился в этом виде 09.08 — ЭТУ дату прежний код и печатал
    верно — а пакет держал его так до 05.09; отсутствие второй даты («держали почти месяц»)
    и было находкой. Починка — не смена вычисляемой даты, а ДОБАВЛЕНИЕ второй.

    `anchor_rev`, если дан, ОГРАНИЧИВАЕТ историю ИМ И СТАРШЕ (при --rev не заглядываем ПОСЛЕ
    взятой версии — иначе «пакет сменил её» назвала бы смену, которую этот вызов сознательно
    не брал). Сравнение — ТО ЖЕ same_text, что и везде в инструменте.

    ⚖️ ВОЗВРАТ OPSSRE №2: `anchor_rev` может прийти ЗАГЛУШКОЙ (`UNKNOWN_VERSION` из fetch(),
    когда источник не сумел назвать свой HEAD) — отданная в `git log` как есть, она ломает
    сам вызов (git не понимает такую «версию», история для ВСЕХ файлов молча превращается
    в пустую, и правда «в истории нет» подменяется НЕПРАВДОЙ по той же форме). ВЫБОР — искать
    БЕЗ ГРАНИЦЫ (по всей истории источника), а не отказываться от дат: если версия и правда
    неизвестна, «не заглядывать в будущее после неё» бессмысленно само по себе — там нет
    ничего, после чего заглядывать. Отказ от дат в этом случае убрал бы то немногое верное,
    что мы всё ещё можем сказать (появление и смена внутри ВСЕЙ истории источника), не решив
    ничего взамен. Проверка — на вызывающей стороне (главный ход), не здесь: сюда обязаны
    приходить уже НАСТОЯЩИЙ коммит или None.

    Возвращает {"found": False} — в истории такого содержимого нет вовсе, ЭТО ОТДЕЛЬНЫЙ
    ответ от «истории нет» (git_history_root) — здесь история ЕСТЬ и была просмотрена.
    {"found": True, "date", "commit", "changed_date", "changed_commit"} — появление версии
    и следующая смена; changed_* пусты, если версия держится и сейчас (в границах anchor_rev).
    """
    args = ["git", "-C", str(repo), "log"]
    if anchor_rev:
        args.append(anchor_rev)
    args += ["--format=%H|%as", "--", git_rel]
    log = subprocess.run(args, capture_output=True, text=True)
    commits = [tuple(line.split("|", 1)) for line in (log.stdout or "").splitlines()
              if "|" in line]
    for i, (commit_hash, date) in enumerate(commits):
        show = subprocess.run(["git", "-C", str(repo), "show", f"{commit_hash}:{git_rel}"],
                              capture_output=True)
        if show.returncode == 0 and same_text(target, show.stdout):
            changed = commits[i - 1] if i > 0 else None
            return {"found": True, "date": date, "commit": commit_hash[:12],
                    "changed_date": changed[1] if changed else None,
                    "changed_commit": changed[0][:12] if changed else None}
    return {"found": False}


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
        return local, (rev_out.stdout or "").strip()[:12] or UNKNOWN_VERSION, False
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

        # 🪤 КАРТОЧКА #604 ③: у «❓» называем, КОГДА эта версия появилась и когда пакет её
        # сменил — иначе «❓» читается как «не смотрели», а не «застряли месяц назад» (шесть
        # таких файлов у tapas стояли на пакете 20.08 почти месяц, никто не заметил).
        # История нужна только когда есть хоть один «❓» — иначе это лишний git-вызов впустую.
        # ⚖️ ТРИ РАЗНЫХ ОТВЕТА, и путать их нельзя (возврат OPSSRE ③-1): история НЕ СМОТРЕЛАСЬ
        # (источник не git или worktree распознан неверно) ≠ история ПРОСМОТРЕНА и такого
        # содержимого в ней нет ≠ содержимое найдено — с датой появления и датой смены.
        history: dict = {}
        history_unavailable = None
        if unknown:
            source_as_dir = pathlib.Path(source)
            probe_dir = source_as_dir if source_as_dir.is_dir() else src_dir
            history_repo, reason = git_history_root(probe_dir)
            if history_repo is not None:
                if is_shallow_clone(history_repo):
                    # клон был --depth 1 — истории в нём нет, догружаем ПОЛНОСТЬЮ
                    subprocess.run(["git", "-C", str(history_repo), "fetch", "--unshallow"],
                                   capture_output=True, text=True)
                for rel in unknown:
                    git_rel = git_rel_of.get(rel)
                    # 🪤 ВОЗВРАТ OPSSRE №2: rev может быть ЗАГЛУШКОЙ UNKNOWN_VERSION (у
                    # источника нет HEAD вовсе — см. fetch()). Отданная в git log как есть,
                    # она ломает вызов и подменяет правду «в истории нет» неправдой той же
                    # формы. Выбор — искать БЕЗ ГРАНИЦЫ версии (anchor_rev=None), а не
                    # отказываться от дат: разбор выбора — в докстроке find_version_span.
                    bound = rev if rev != UNKNOWN_VERSION else None
                    history[rel] = (find_version_span(history_repo, git_rel,
                                                       (tools / rel).read_bytes(),
                                                       anchor_rev=bound)
                                    if git_rel else {"found": False})
            else:
                history_unavailable = reason
        for rel in unknown:
            if history_unavailable is not None:
                tail = f" — истории у источника нет — дату назвать нечем ({history_unavailable})"
            else:
                span = history.get(rel) or {"found": False}
                if span.get("found"):
                    tail = f" — версия пакета от {span['date']} (коммит {span['commit']})"
                    tail += (f"; пакет сменил её {span['changed_date']} (коммит "
                            f"{span['changed_commit']})" if span.get("changed_commit")
                            else "; пакет держит её и сейчас")
                else:
                    tail = " — в истории пакета такого содержимого нет"
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
            # 🪤 ВОЗВРАТ OPSSRE (карточка #604 ③-3): здесь стояло ложное обещание — «теперь
            # отпечатки есть, и следующий прогон скажет про них определённо». Неправда:
            # отпечаток пишется ТОЛЬКО взятым файлам (и так и должно быть — см. комментарий
            # у updated_fingerprints выше: отпечаток у НЕвзятого файла сделал бы его правку
            # невидимой). Значит эти файлы отпечатка не получат и на СЛЕДУЮЩЕМ прогоне снова
            # придут «❓» — обещание «скажет определённо» никогда не сбывается само.
            print(f"❓ НЕ тронуто без отпечатка: {len(unknown)} — они останутся «❓» и в "
                  f"следующих прогонах: без отпечатка инструмент не отличит твою правку от "
                  f"старой версии пакета. Взять версию пакета — тот же вызов с "
                  f"--overwrite-unknown; оставить свои — ничего не делать.")
        print("👉 ОБЯЗАТЕЛЬНО СЛЕДОМ: прогони свои проверки (guard-all.py). Инструмент, "
              "приехавший и не прогнанный, — это не обновление, а надежда.")
        return 0
    finally:
        if temporary:
            mezo_stand.release(src_dir)   # 🩸 было `rmtree(ignore_errors=True)` — см. шапку fetch()


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
