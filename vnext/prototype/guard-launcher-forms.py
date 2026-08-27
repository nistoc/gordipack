#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ФОРМЫ ВЫЗОВА ИЗ ПАМЯТИ РОЛЕЙ: отвечает ли КАЖДАЯ из них на самом деле.

ПОВОД (проба-канарейка 2026-08-09). Последняя строка промпта запуска PROTO —
`role-rights.py list --role <РОЛЬ>` — падала у ЛЮБОЙ роли: параметр с именем роли
готовился и терялся по дороге в запрос. Форма БЕЗ имени роли работала, поэтому дефект
жил незамеченным. Приёмка была ЗЕЛЁНОЙ: она звала только рабочую форму.
> 🎯 Зелёная проверка означает ровно то, что она ПОЗВАЛА. Не больше.

ПРЕДМЕТ. Роль при пробуждении зовёт команды, выписанные в её памяти. Если такая команда
падает или её файла нет — роль встречает ошибку в первые же секунды жизни, и это выглядит
её виной. Здесь каждая форма ЗАПУСКАЕТСЯ по-настоящему, на КОПИИ базы.

ФОРМА = скрипт + подкоманда + набор ФЛАГОВ (без значений). Значения берутся свои: в памяти
на их месте стоят заглушки вроде <РОЛЬ>. Именно набор флагов и решает — падение 09.08
случалось ровно при наличии `--role`.

ТРИ ИСХОДА, НИКОГДА НЕ ДВА:
    ✅ отвечает          запустилась, вернула 0 или осмысленный отказ
    🔴 ПАДАЕТ / НЕТ ФАЙЛА  роль получит traceback или «can't open file»
    ⚠️ НЕ ПРОВЕРЕНА      названа причина: вне контура · двигает курсор · нет способа
                          указать копию базы. «Не проверена» — это НЕ «в порядке».

⛔ ЖИВУЮ БАЗУ НЕ ТРОГАЕТ: читает её только на чтение и работает на копии во временной папке.
Формы, гасящие одноразовый ключ (`--ack`), не запускаются вовсе — они СЪЕЛИ БЫ ключ у роли.
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_SCRIPTS = mezo_paths.live_scripts()
VNEXT_TOOLS = Path(__file__).resolve().parent
TEMPLATE_ROOT = mezo_paths.template_root()     # относительные пути вида «vnext/tools/» — сюда
LIVE_DB = LIVE_SCRIPTS.parent / "mezosync.db"
CANON = [Path(str(mezo_paths.container_root() / "CLAUDE.md"))]

# 🩸 ГРУППА «py» ЗАВЕДЕНА 27.08 (заявка @COORD, записка #4011, карточка #332). Слово
# «python» захватывалось совпадением БЕЗЫМЯННО, а признак команды искал его в тексте
# ДО совпадения — то есть в пустоте. Условие «или перед именем есть python» не срабатывало
# НИ РАЗУ: командой признавалось только то, что стои́т внутри блока кода.
# 📏 Замер живой базы 27.08 17:11 UTC: строк «python <путь>.py» ВНЕ блоков кода — 109,
# проверялось из них 0. Каноническая форма записи вызова в прозе не судилась вовсе,
# а прибор при этом честно говорил «упомянуто, но не команда» — и это читалось
# как «там нечего смотреть».
CALL = re.compile(
    r"(?P<py>python\s+)?(?P<path>(?:[A-Za-z]:)?[^\s`'\"|]*[\\/])?(?P<script>[a-z0-9_-]+\.py)",
    re.I)
# Хвост команды заканчивается там, где начинается ЧУЖОЕ: разделитель перечня « · »,
# бэктик/труба (как раньше) — а начало СЛЕДУЮЩЕЙ команды в той же строке режется
# позицией её головы (см. collect). Пока хвост тянулся до конца строки, флаги второй
# команды прилипали к первой и рождали форму, которой нет ни в одной памяти:
# «list --role X (закрыть: status <id> done --actor X)» читалось как «list --actor --role»
# и красило ВЕРНУЮ строку (карточка #203, замер 15.08 — три ложных красных).
SEG_END = re.compile(r"\s+·\s+|[`|]")
FLAG = re.compile(r"--[a-z][a-z0-9-]*")
SUB = re.compile(r"^\s+(?!-)([a-z][a-z0-9-]*)\b")

# Долгие ПО СВОЕЙ ПРИРОДЕ команды: честный прогон занимает минуты, и порог на «висит»
# для них лжёт («работает дольше порога» ≠ «висит» — вторая половина карточки #203).
# Форма сверяется по --help (разборщик аргументов тот же), о чём говорится вслух.
LONG_BY_NATURE = {"bite-all.py": "полный прогон всех приёмок — минуты по своей природе"}

# ⚠️ ЗНАЧЕНИЯ ПОДСТАВЛЯЕМ СВОИ. В памяти на их месте заглушки (<РОЛЬ>, <нота.md>):
# запуск с ними доказывал бы только то, что заглушка не является ролью.
def values(flag, ctx):
    return {
        "--role": ["PROTO"], "--limit": ["1"], "--section": ["state"],
        "--file": [ctx["file"]], "--body-file": [ctx["file"]], "--done-when-file": [ctx["file"]],
        "--save-state": [ctx["file"]], "--save-plan": [ctx["file"]],
        "--key": ["rule8-destructive"], "--to": ["CORE"], "--cc": ["COORD"],
        "--root": [ctx["dir"]], "--poll": ["проверка формы вызова"],
        "--actor": ["PROTO"], "--title": ["проверка формы"], "--id": ["1"],
        "--tag": ["проба"], "--track": ["проба"], "--priority": ["normal"],
        "--why": ["проверка формы"], "--on": ["проверка формы"], "--remote": [],
    }.get(flag, [])

# запускать НЕЛЬЗЯ: последствие необратимо для роли или выходит за копию базы
FORBIDDEN = {
    "--ack": "гасит ОДНОРАЗОВЫЙ ключ и двигает отметку чтения — роль потеряла бы свой батч",
    "--apply": "применяет изменение, а не мерит",
    "--sync": "переписывает вторую копию",
    "--register": "заводит новую роль",
    "--md": "пишет в ЗАМОРОЖЕННЫЕ md-каналы — они вне копии базы",
}
NO_DB_FLAG = {"gen-schema.py", "sync-to-template.py", "bite-all.py"}  # свой источник, --db не берут

# ⚖️ ЭВРИДИКА, НАЗВАННАЯ ВСЛУХ: по имени видно, читает механизм или пишет. Читающий можно
# запустить и на живой базе, пишущий — только на копии. Ошибись эта догадка — она разрешила бы
# запись в живой контур, поэтому имена перечислены явно, а не угаданы по глаголу.
READING = re.compile(
    r"^(guard-|check-|measure-|read-|stats\.|feed\.|unsaved\.|dashboard\.|export-|bite-|refs_check|"
    r"[a-z_]+_layer\.)", re.I)


def collect(db):
    """Формы + где встречены. Источник — память ролей и файл-канон.

    🪤 УПОТРЕБЛЕНИЕ ≠ УПОМИНАНИЕ. Первая редакция сочла командой строку из ПОЯСНЕНИЯ
    у ING: «относительный префикс перед именем скрипта (.mezosync\\scripts\\x.py…)» — и
    объявила красным несуществующий `x.py`. Текст там объяснял ОПАСНОСТЬ такой формы,
    то есть говорил ровно обратное тому, что услышал прибор.
    ⇒ Командой считаем только то, что роль реально СКОПИРУЕТ: строку в блоке кода
    или строку со словом `python` перед путём. Остальное — упоминание, оно считается
    отдельно и НЕ обвиняется.
    """
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute("SELECT role, section, body FROM phoenix").fetchall()
    conn.close()
    texts = [(f"{r}·{s}", b or "") for r, s, b in rows]
    texts += [(p.name, p.read_text(encoding="utf-8")) for p in CANON if p.exists()]

    forms = defaultdict(lambda: {"where": set(), "paths": set(), "short": False})
    mentions = defaultdict(set)
    for where, body in texts:
        in_code = False
        for line in body.splitlines():
            if line.lstrip().startswith("```"):
                in_code = not in_code
                continue
            quoted = line.lstrip().startswith(">")
            heads = list(CALL.finditer(line))
            for i, m in enumerate(heads):
                script = m.group("script")
                # хвост — ТОЛЬКО этой команды: до головы следующей в той же строке,
                # и не дальше разделителя « · »/бэктика/трубы (#203: склейка флагов)
                tail = line[m.end():heads[i + 1].start() if i + 1 < len(heads) else len(line)]
                tail = SEG_END.split(tail, 1)[0]
                before = line[:m.start()]
                # 🪤 ОПИСЬ ФАЙЛОВ ВНУТРИ БЛОКА КОДА выглядит как команды:
                #    «sync_backoff.py .......... разгон сна между синками»
                # Это перечень предметов, а не то, что роль скопирует в оболочку. Отличается
                # заполнителем из точек сразу за именем. Пока прибор считал такие строки
                # командами, он молча пропускал поломку механизма — поймала сплошная поломка.
                # 🪤 ВТОРАЯ ФОРМА ОПИСИ — БЕЗ ТОЧЕК-ЗАПОЛНИТЕЛЯ, найдена 27.08 тем же
                # разбором (@COORD, записка #4011: «судится то, что командой не является»).
                # «vnext/tools/diff-schema-sample.py  расхождение ОБРАЗЦА схемы с живой базой»
                # — перечень предметов внутри блока кода. Прибор запускал его и краснел
                # на исправном: обвинял МОЮ память за строку, которая командой не была.
                # ⚖️ Признак — кириллица сразу за именем: описания у нас по-русски,
                # команды латиницей. Двух пробелов требуем, чтобы не задеть команду,
                # у которой русское значение стои́т за латинским ключом.
                listing = re.match(r"\s*\.{3,}|\s{2,}[А-Яа-яЁё]", tail) is not None
                # ⚡ ПРИЗНАК КОМАНДЫ ВНЕ БЛОКА КОДА — само слово «python» ВНУТРИ совпадения
                # (группа py), а не текст до него: до него пусто по построению образца.
                # ⚖️ Почему именно «python», а не любое имя файла: строка «зови python
                # <путь>/x.py --flag» — это то, что роль СКОПИРУЕТ; а «относительный
                # префикс перед именем скрипта (.mezosync\scripts\x.py…)» — пояснение
                # об опасности, и обвинять его нельзя. Слово «python» отделяет одно
                # от другого лучше любого другого признака: в пояснениях его не пишут.
                is_command = (in_code or bool(m.group("py"))) and not quoted and not listing
                if not is_command:
                    mentions[script].add(where)
                    continue
                sub_m = SUB.match(tail)
                sub = sub_m.group(1) if sub_m else ""
                flags = tuple(sorted(set(FLAG.findall(tail))))
                key = (script, sub, flags)
                forms[key]["where"].add(where)
                # «backlog.py … status <id> done» — запись СОКРАЩЕНА, роль дополнит её сама.
                # Обвинять сокращение нельзя: прибор проверял бы не ту команду, что зовут
                if "…" in tail or "..." in tail:
                    forms[key]["short"] = True
                if m.group("path"):
                    # скобка/кавычка из прозы прилипает к пути и делает его несуществующим:
                    # «(vnext/tools/gen-schema.py)» — путь тут vnext/tools/, а не «(vnext/tools/»
                    forms[key]["paths"].add(m.group("path").lstrip("([{«\"'"))
    return forms, len(texts), mentions


def resolve(script, paths, root):
    """Где лежит файл. Сначала — путь, НАЗВАННЫЙ В ПАМЯТИ: роль пойдёт именно по нему.

    ⚠️ Три РАЗНЫХ случая, и мешать их нельзя (первая редакция мешала и обвиняла зря):
      · путь назван и файл там есть ....... роль дойдёт
      · путь назван, а файла там НЕТ ...... роль получит «can't open file» — это КРАСНОЕ
      · путь не назван вовсе (проза) ...... ищем рядом; ненайденное здесь НЕ обвиняем
    """
    named = [p for p in paths if p.strip()]
    # ⚡ ИСПЫТУЕМОСТЬ. Когда назван НЕ живой каталог, он и считается живым — ЦЕЛИКОМ, включая
    # случай «файла там нет». Первая редакция подменяла каталог только пока файл в копии ЕСТЬ,
    # а иначе тихо уходила по абсолютному пути в живой контур: удали скрипт из копии — прибор
    # оставался зелёным, потому что смотрел на оригинал. Приёмка это и поймала.
    if root.resolve() != LIVE_SCRIPTS.resolve():
        inside = [p for p in named
                  if (".mezosync" in p and "scripts" in p) or "vnext-tools" in p]
        if inside or not named:
            return ((root / script), "по пути из памяти") if (root / script).exists() \
                else (None, "НЕТ ПО НАЗВАННОМУ ПУТИ")
    for p in named:
        cand = Path(p.replace("/", os.sep)) / script
        if not cand.is_absolute():                       # «vnext/tools/» — это шаблон
            cand = TEMPLATE_ROOT / cand
        if cand.exists():
            return cand, "по пути из памяти"
    for base in (root, VNEXT_TOOLS):
        if (base / script).exists():
            return base / script, ("память зовёт ДРУГОЙ путь" if named else "путь не назван, лежит рядом")
    return None, ("НЕТ ПО НАЗВАННОМУ ПУТИ" if named else "ПУТЬ НЕ НАЗВАН И РЯДОМ НЕТ")


def build_argv(exe, sub, flags, ctx, db_copy):
    """⚠️ --db идёт ДО подкоманды: у backlog.py и role-rights.py он объявлен в ОБЩЕМ разборщике,
    и в хвосте команда его не узнаёт. Первая редакция ставила его в конец и объявляла
    «не умеет брать другую базу» ровно те механизмы, которые умеют."""
    argv = [sys.executable, str(exe)]
    if exe.name not in NO_DB_FLAG:
        argv += ["--db", str(db_copy)]
    if sub:
        argv.append(sub)
    for f in flags:
        if f == "--db":
            continue
        argv.append(f)
        argv += values(f, ctx)
    return argv


def main() -> int:
    ap = argparse.ArgumentParser(description="проверить ЗАПУСКОМ каждую форму вызова из памяти ролей")
    ap.add_argument("--db", default=str(LIVE_DB), help="откуда брать память ролей (только чтение)")
    ap.add_argument("--scripts-root", default=str(LIVE_SCRIPTS),
                    help="какой каталог считать живым. Меняется, чтобы испытать КОПИЮ, а не оригинал")
    ap.add_argument("--only", help="подстрока имени скрипта")
    ap.add_argument("--verbose", action="store_true", help="показывать вывод падений целиком")
    a = ap.parse_args()

    root = Path(a.scripts_root)
    forms, n_src, mentions = collect(a.db)
    work = mezo_stand.new("forms-")
    db_copy = work / "copy.db"
    shutil.copy(a.db, db_copy)
    ctx = {"file": str(work / "text.md"), "dir": str(work)}
    Path(ctx["file"]).write_text("проверка формы вызова\n", encoding="utf-8")

    print("=" * 84)
    print("ФОРМЫ ВЫЗОВА ИЗ ПАМЯТИ РОЛЕЙ — проверяются ЗАПУСКОМ, на копии базы")
    print(f"  каталог скриптов: {root}")
    print(f"  форм {len(forms)} · источников памяти {n_src}")
    if mentions:
        only_talk = sorted(set(mentions) - {s for (s, _, _) in forms})
        print(f"  📎 УПОМЯНУТО, НО НЕ КОМАНДА: имён {len(mentions)}"
              + (f" · только в пояснениях: {', '.join(only_talk[:6])}" if only_talk else ""))
        print("     (строка в пояснении объясняет ОПАСНОСТЬ формы — обвинять её нельзя)")
    print("=" * 84)

    ok_n = red = skip = 0
    reds, skips = [], []
    for (script, sub, flags), info in sorted(forms.items()):
        if a.only and a.only not in script:
            continue
        shown = f"{script} {sub} {' '.join(flags)}".strip()
        where = ", ".join(sorted(info["where"])[:3])

        stop = next((FORBIDDEN[f] for f in flags if f in FORBIDDEN), None)
        if stop:
            skip += 1
            skips.append((shown, stop, where))
            continue

        if info["short"]:
            skip += 1
            skips.append((shown, "запись СОКРАЩЕНА многоточием — роль дополняет её сама, "
                                 "проверять было бы не ту команду", where))
            continue

        exe, how = resolve(script, info["paths"], root)
        if exe is None:
            named = ", ".join(sorted(info["paths"]))
            in_contour = any((".mezosync" in p or "vnext-tools" in p) for p in info["paths"])
            if in_contour:
                # путь контура назван, а файла там нет — роль пойдёт и упрётся
                red += 1
                reds.append((shown, f"⛔ ФАЙЛА НЕТ ПО НАЗВАННОМУ ПУТИ: {named}", where))
            elif named:
                skip += 1
                skips.append((shown, f"путь ведёт ВНЕ каталога скриптов контура ({named}) — "
                                     "шаблон или репозиторий другой роли", where))
            else:
                # имя названо прозой, без пути: где ему быть — из текста не следует,
                # и обвинять тут нечего. Но и «в порядке» сказать нельзя
                skip += 1
                skips.append((shown, "имя без пути и рядом не лежит — где искать, память не говорит",
                              where))
            continue

        if exe.name in LONG_BY_NATURE:
            # «работает минуты» ≠ «висит»: полный прогон здесь лгал бы порогом (#203).
            # Форма сверяется разборщиком аргументов самой команды — --help с теми же флагами
            try:
                h = subprocess.run([sys.executable, str(exe), "--help"], capture_output=True,
                                   text=True, encoding="utf-8", timeout=30)
            except subprocess.TimeoutExpired:
                red += 1
                reds.append((shown, "🔴 даже --help не отвечает за 30 с", where))
                continue
            if h.returncode == 0:
                skip += 1
                skips.append((shown, f"долгая по природе ({LONG_BY_NATURE[exe.name]}) — "
                                     "полный прогон не гонялся, форма сверена по --help", where))
            else:
                red += 1
                reds.append((shown, "🔴 --help отвечает отказом — файл есть, но не команда", where))
            continue

        argv = build_argv(exe, sub, flags, ctx, db_copy)
        try:
            r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", timeout=90)
        except subprocess.TimeoutExpired:
            red += 1
            reds.append((shown, "🔴 ВИСНЕТ дольше 90 с (долгие ПО ПРИРОДЕ — в списке "
                                "LONG_BY_NATURE, эта в него не входит)", where))
            continue
        out = (r.stdout or "") + (r.stderr or "")
        if ("unrecognized arguments: --db" in out or "no such option: --db" in out):
            # механизм не умеет указывать базу. Читающему это не мешает — он ничего не пишет;
            # пишущий на живой базе запускать НЕЛЬЗЯ, и это разные исходы, а не один
            if READING.match(exe.name):
                argv = [x for x in argv if x not in ("--db", str(db_copy))]
                r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                                   timeout=90)
                out = (r.stdout or "") + (r.stderr or "")
                how = "базу не указать — читал ЖИВУЮ (по имени механизм только читает)"
            else:
                skip += 1
                skips.append((shown, "базу не указать, а механизм ПИШЕТ — на живой не запускаю",
                              where))
                continue
        # 🪤 ПАДЕНИЕ — НЕ ЕДИНСТВЕННЫЙ ВИД ОТКАЗА. Если механизм не знает флага, разборщик
        # отвечает «unrecognized arguments» и кодом 2 — БЕЗ traceback. Прибор, ищущий только
        # traceback, назвал бы такую форму отвечающей: память зовёт то, чего у механизма нет
        # (это же класс, что и «механизм печатает имя, которого у него нет»).
        unknown = [f for f in flags if f not in FORBIDDEN and not values(f, ctx)]
        if "Traceback (most recent call last)" in out:
            last = [l for l in out.strip().splitlines() if l.strip()][-1][:110]
            red += 1
            reds.append((shown, f"🔴 ПАДАЕТ: {last}", where))
            if a.verbose:
                print(out)
        elif "unrecognized arguments" in out or "invalid choice" in out:
            bad = re.search(r"unrecognized arguments: (.+)|invalid choice: (.+)", out)
            red += 1
            reds.append((shown, "🔴 МЕХАНИЗМ НЕ ЗНАЕТ ЭТОЙ ФОРМЫ: "
                                f"{(bad.group(0) if bad else '')[:90]}", where))
        elif "expected one argument" in out and unknown:
            skip += 1
            skips.append((shown, f"нечего подставить в {' '.join(unknown)} — прибор, а не механизм",
                          where))
        elif r.returncode != 0 and not out.strip():
            # 🪤 НАЙДЕНО НА СЕБЕ 20.08: механизм, от которого осталась одна строка
            # `raise SystemExit(9)`, проходил как ОТВЕЧАЮЩИЙ — судили только по ТЕКСТУ
            # (traceback, «unrecognized arguments»), а код возврата не смотрели вовсе.
            # ⚖️ Судить по одному коду нельзя: проверки законно отвечают кодом 1, когда
            # нашли расхождения, и отчёт при этом печатают. Отличает их ВЫВОД: молчание
            # при отказе роль прочтёт как сработавший запуск, потому что читать нечего.
            red += 1
            reds.append((shown, f"🔴 МОЛЧА ОТКАЗЫВАЕТ кодом {r.returncode}: ни строки вывода — "
                                "роль решит, что команда отработала", where))
        elif "the following arguments are required" in out:
            skip += 1
            skips.append((shown, "форма в памяти НЕПОЛНА: механизм требует ещё аргументы", where))
        else:
            ok_n += 1
            mark = "" if how in ("по пути из памяти", "путь не назван, лежит рядом") else f"  ⚠️ {how}"
            print(f"✅ {shown:58} {where[:30]}{mark}")

    for shown, why, where in reds:
        print(f"🔴 {shown:58} {where[:30]}")
        print(f"     {why}")
    for shown, why, where in skips:
        print(f"⚠️ {shown:58} {where[:30]}")
        print(f"     НЕ ПРОВЕРЕНА: {why}")

    print("-" * 84)
    print(f"отвечают {ok_n} · 🔴 ПАДАЮТ ИЛИ НЕТ ФАЙЛА {red} · ⚠️ не проверены {skip}")
    if skip:
        print("⚠️ «не проверена» — это НЕ «в порядке»: у каждой названа причина, и её видно.")
    if red:
        print("⛔ Роль встретит это в ПЕРВЫЕ СЕКУНДЫ жизни — и решит, что ошиблась сама.")
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
