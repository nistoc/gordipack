#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-viewer-readonly — приёмка ② просмотрщика: служба доказанно НЕ ПИШЕТ в базу.

    python <КОНТУР>/vnext-tools/check-viewer-readonly.py [--api http://127.0.0.1:5177]

Что делает (всё — прогоном, не чтением кода):
  1. PRAGMA integrity_check по базе, которую служба объявила активной, — ДО;
  2. отпечаток файлов базы (.db/-wal/-shm: размер + sha256) — ДО;
  3. перечень маршрутов службы (см. ниже) — прогон ВСЕХ, дважды (второй раз — после
     паузы, чтобы захватить и фоновый пересчёт);
  4. integrity_check и отпечаток — ПОСЛЕ: байт в байт совпали;
  5. /api/health.readOnly — ЗАМЕР самой службы по живому соединению (три замка:
     Mode, query_only, канарейка записи). false = КРАСНЫЙ.

⚖️ ГРАНИЦА: пункт 5 верит замеру службы. Что замер не подделан константой,
   доказывается НАРОЧНОЙ ПОЛОМКОЙ (подменить Mode в ReadOnlyDb.cs → этот скрипт обязан
   покраснеть на копии) — прогон поломки входит в приёмку, не в этот скрипт.

⬆️ ДОПИСАНО 26.08 (карточка #247, найдено контуром tapas, воспроизведено @COORD):
  0. ОЖИДАЕМАЯ БАЗА СВЕРЯЕТСЯ МАШИНОЙ, а не глазом. 🩸 Оплачено соседями: их служба
     не поднялась («порт занят»), запрос здоровья ответила НАША служба на том же порту,
     и проверка честно доказала read-only ЧУЖОЙ базы. Путь при этом ПЕЧАТАЛСЯ первой
     строкой — его видели и всё равно ошиблись: решение принимает читающий, а читающий
     читает ВЕРДИКТ. Напечатать ≠ проверить.
     Ожидание: --expect-db <путь>; без довода — живая база ЭТОГО контура (от
     расположения скрипта). Совпадение — по нормализованному пути.
  0б. ТРИ ИСХОДА, НЕ ДВА: 0 «доказано» · 1 «ОПРОВЕРГНУТО» (настоящая находка) ·
     2 «НЕ СМОГЛА ПРОВЕРИТЬ» (служба молчит · открыта не та база · база недоступна).
     🩸 Прежде «службы нет» падало трассировкой в 40 строк с тем же кодом 1, что
     настоящая находка, — «не смогла проверить» было слито с «опровергнуто».

⬆️ ДОПИСАНО 15.09 (карточка #646, находка tapas @COORD, подтверждено @PROTO):
  0в. ПЕРЕЧЕНЬ МАРШРУТОВ — ИЗ САМОЙ СЛУЖБЫ, А НЕ РУКОЙ. 🩸 Рукописный список держал
     9 адресов, у службы их 15 (`ApiEndpoints.cs`); вывод «эндпоинтов отвечено 200:
     18 из 18» читался как «всё обойдено», а составом это было 9 из 15 — pool · tracks ·
     tasks/grouped · tasks/history · tasks/{id} · messages/{id} не обходились вовсе,
     и находка об этом молчала. Теперь перечень разбирается из `ApiEndpoints.cs`
     (MapGet) — от расположения ЭТОГО файла (в пакете: vnext/prototype → корень
     пакета → src/…) либо через явный `--api-source <путь>`. Маршрут с параметром
     (`{id:...}`) разворачивается ЖИВЫМ id — первым из ответа маршрута-списка
     (tasks → /api/tasks, messages → /api/messages); списка нет или он пуст —
     маршрут называется поимённо как необойдённый, а не молчит.
  0г. ИСХОДНИК НЕДОСТИЖИМ (например: эта копия — в контуре, а служба — в другом
     репозитории) → строка «перечень маршрутов службы недоступен — покрытие не
     судится», НЕ молча и НЕ «всё обойдено»: приёмка read-only по-прежнему прогоняется
     (на резервном коротком списке 26.08), но заявлять о покрытии тут нечем.
  0д. Попутно поймано прогоном: `fetch()` не ловил `HTTPError` — маршрут, отвечающий
     НЕ 2xx (например, ещё не задеплоенный), ронял скрипт необработанной трассировкой
     вместо того, чтобы назвать маршрут необойдённым. Без этой правки перечень из
     `ApiEndpoints.cs` был бы бесполезен: ЛЮБОЙ временно недоступный маршрут убивал
     бы весь прогон, а не просто помечался.

⬆️ ДОПИСАНО 15.09, возврат владельца по карточке #646:
  0е. ВТОРАЯ РАСКЛАДКА ПОИСКА ИСХОДНИКА — через mezo_paths. Раскладка «в пакете»
     (0в) не покрывала копию контура (atlas/vnext-tools): служба лежит в ДРУГОМ
     репозитории, а не рядом. Вместо второго угадывания путём руками — вопрос
     `mezo_paths.template_root(script_file)`: он уже знает корень образца
     (MEZO_TEMPLATE или `template=<путь>` в local.paths рядом с mezo_paths.py —
     механизм существовал ДО этой правки, просто не был спрошен). Образца нет —
     `template_root()` завершает процесс словами; здесь это перехватывается и
     превращается в None: копии, которой образец не нужен всегда, финал инструмента
     не должен становиться её собственным отказом. Раскладка ① (в пакете) пробуется
     ПЕРВОЙ — она не требует local.paths вовсе и самодостаточна.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — ожидание по умолчанию выводится, не впечатано


def normalized_path(p) -> str:
    """Пути сравниваются нормализованными: регистр Windows и наклон косой не должны
    превращать ту же базу в «другую»."""
    return str(Path(p).resolve()).replace("\\", "/").lower()


# Резервный список — только когда перечень маршрутов службы разобрать не удалось
# (карточка #646, см. 0в/0г в шапке). Держать РУКОЙ полный список запрещено этой же
# находкой: он и был причиной беды. Состав — те же 9 адресов, что были ДО правки.
FALLBACK_ROUTES = ["/health", "/sources", "/overview", "/schema", "/roles", "/rules",
                    "/tasks", "/messages", "/writers"]
DEFAULT_PREFIX = "/api"

GROUP_RE = re.compile(r'MapGroup\(\s*"([^"]+)"')
ROUTE_RE = re.compile(r'\bMapGet\(\s*"([^"]+)"')
PARAM_RE = re.compile(r'\{(\w+)(?::[^}]*)?\}')


def locate_api_source(explicit: str | None, script_file: Path) -> Path | None:
    """Путь к ApiEndpoints.cs. Явный довод — как есть (не найден на диске — None,
    не гадаем).

    Без довода — ДВЕ раскладки, по очереди:
      ① служба лежит в том же пакете, что и эта копия проверки: vnext/prototype →
         корень пакета → src/… (карточка #646);
      ② эта копия живёт в контуре (например, atlas/vnext-tools), а служба — в
         отдельном репозитории пакета-образца. Путь к образцу здесь НЕ угадывается
         руками — его знает mezo_paths (MEZO_TEMPLATE или `template=<путь>` в
         local.paths рядом с mezo_paths.py, непубликуемый файл конкретной копии
         контура — возврат владельца по карточке #646). template_root() при
         отсутствии образца ЗАВЕРШАЕТ ПРОЦЕСС (это его штатный способ отказа для
         инструментов, которым образец нужен всегда) — здесь он не всегда нужен,
         поэтому отказ перехватывается и превращается в None, а не в падение
         проверки: раскладка ① уже была испытана, и «образца нет» здесь равносильно
         «источника нет» — исход 0г, не трассировка."""
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    try:
        candidate = (Path(script_file).resolve().parents[2] / "src" /
                     "Gordi.Periscope.Api" / "Endpoints" / "ApiEndpoints.cs")
        if candidate.exists():
            return candidate
    except IndexError:
        pass
    try:
        template = mezo_paths.template_root(script_file)
    except SystemExit:
        return None
    candidate = template / "src" / "Gordi.Periscope.Api" / "Endpoints" / "ApiEndpoints.cs"
    return candidate if candidate.exists() else None


def parse_routes(text: str) -> tuple[str, list[str]]:
    """Префикс группы (MapGroup) и отсортированный список ШАБЛОНОВ маршрутов (MapGet),
    разобранные из исходника службы. Разбор текстовый (регулярным выражением), не
    компилятором C# — этого достаточно: строка вызова MapGet — единственное, что нужно
    знать проверке, а не семантика обработчика."""
    prefix_match = GROUP_RE.search(text)
    prefix = prefix_match.group(1) if prefix_match else DEFAULT_PREFIX
    routes = sorted(set(ROUTE_RE.findall(text)))
    return prefix, routes


def route_plan(template: str) -> dict:
    """Разряд шаблона: 'static' (нет параметра — обходится прямо), 'param' (ровно один
    параметр, и он — последний сегмент шаблона: id разворачивается из ответа
    маршрута-родителя) или 'unsupported' (форма параметра, которую эта проверка не умеет
    разворачивать — маршрут называется необойдённым, а не пропускается молча)."""
    matches = list(PARAM_RE.finditer(template))
    if not matches:
        return {"template": template, "kind": "static"}
    if len(matches) != 1 or not template.endswith(matches[0].group(0)):
        return {"template": template, "kind": "unsupported"}
    parent = template[:matches[0].start()].rstrip("/") or "/"
    return {"template": template, "kind": "param", "parent": parent}


def extract_first_id(payload):
    """Первый id из ответа маршрута-списка — раскрывает и голый массив (`/api/tasks`),
    и страницу вида {"items": [...]} (`/api/messages`). Списка нет или в нём нет
    элементов с id — None (маршрут с параметром называется «нет данных», не падает)."""
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = next((v for v in payload.values() if isinstance(v, list)), None)
        if items is None:
            return None
    else:
        return None
    for item in items:
        if isinstance(item, dict) and "id" in item:
            return item["id"]
    return None


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.read()


def fetch_status(url: str):
    """Код ответа ИЛИ None, если службы не было на связи вовсе. Ответ НЕ 2xx — тоже
    код (несёт его HTTPError), не исключение: маршрут службы, ответивший 404/500,
    обязан быть НАЗВАН необойдённым, а не уронить весь прогон трассировкой."""
    try:
        return fetch(url)
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except (urllib.error.URLError, OSError, TimeoutError):
        return None, b""


def probe_round(api: str, prefix: str, plan: list) -> dict:
    """Один проход по плану маршрутов → {шаблон: код|"unsupported"|"no-data"}."""
    status: dict = {}
    listing: dict = {}
    for item in plan:
        if item["kind"] != "static":
            continue
        code, raw = fetch_status(f"{api}{prefix}{item['template']}")
        status[item["template"]] = code
        if code == 200:
            try:
                listing[item["template"]] = json.loads(raw)
            except json.JSONDecodeError:
                pass
    for item in plan:
        if item["kind"] == "unsupported":
            status[item["template"]] = "unsupported"
            continue
        if item["kind"] != "param":
            continue
        payload = listing.get(item["parent"])
        ident = extract_first_id(payload) if payload is not None else None
        if ident is None:
            status[item["template"]] = "no-data"
            continue
        filled = PARAM_RE.sub(str(ident), item["template"], count=1)
        code, _ = fetch_status(f"{api}{prefix}{filled}")
        status[item["template"]] = code
    return status


def fingerprint(db: Path) -> str:
    parts = []
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db) + suffix)
        if p.exists():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            parts.append(f"{p.name}:{p.stat().st_size}:{h}")
        else:
            parts.append(f"{p.name}:-")
    return " | ".join(parts)


def integrity(db: Path) -> str:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://127.0.0.1:5177")
    ap.add_argument("--expect-db", default=None,
                    help="какую базу служба ОБЯЗАНА держать открытой; без довода — "
                         "живая база этого контура. Несовпадение = код 2, не «зелёный»")
    ap.add_argument("--api-source", default=None,
                    help="путь к ApiEndpoints.cs (карточка #646); без довода — "
                         "попытка достать его от расположения этой копии проверки "
                         "(в пакете: vnext/prototype → корень пакета → src/…), а не "
                         "вышло — через mezo_paths.template_root (MEZO_TEMPLATE или "
                         "local.paths рядом с mezo_paths.py)")
    a = ap.parse_args()
    expected = Path(a.expect_db) if a.expect_db else mezo_paths.live_db()

    # ИСХОД 2 «не смогла проверить» — служба молчит. Человеческой строкой, не трассировкой:
    # прежде 40 строк Python с кодом 1 были неотличимы от настоящей находки.
    try:
        code, raw = fetch(f"{a.api}/api/health")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        print(f"⚪ НЕ СМОГЛА ПРОВЕРИТЬ: служба не ответила по адресу {a.api}")
        print(f"   причина: {exc.__class__.__name__}: {getattr(exc, 'reason', exc)}")
        print("   это НЕ «read-only нарушен» и НЕ «доказан» — проверять было нечего")
        return 2
    health = json.loads(raw)
    db = Path(health["activeDbPath"])
    print(f"служба: {a.api} · база: {db}")

    # ИСХОД 2 — открыта НЕ ТА база. 🩸 Ровно здесь соседи «доказали» read-only чужой
    # службы: порт был занят нашей, их службы не существовало. Сверка машиной, обе
    # стороны названы; «путь и так печатается» — запрещённый способ пройти (карточка #247).
    if normalized_path(db) != normalized_path(expected):
        print(f"⚪ НЕ СМОГЛА ПРОВЕРИТЬ: служба держит НЕ ТУ базу.")
        print(f"   открыта:   {db}")
        print(f"   ожидалась: {expected}")
        print("   Обычная причина: порт занят ЧУЖОЙ службой (свой просмотрщик не поднялся"
              " «address already in use», а health ответил сосед). Проверять её read-only"
              " — доказывать не тот предмет")
        return 2
    if not db.exists():
        print(f"⚪ НЕ СМОГЛА ПРОВЕРИТЬ: служба назвала базу, которой нет на диске: {db}")
        return 2

    before_ic, before_fp = integrity(db), fingerprint(db)
    print(f"integrity ДО:  {before_ic}")
    print(f"отпечаток ДО:  {before_fp}")

    # Перечень маршрутов — из самой службы (карточка #646), не рукой. Источник
    # недостижим → работаем на резервном списке, но заявлять о покрытии нечем — 0г.
    source = locate_api_source(a.api_source, Path(__file__))
    if source is not None:
        prefix, routes = parse_routes(source.read_text(encoding="utf-8"))
        plan = [route_plan(t) for t in routes]
        print(f"маршруты службы: {len(routes)} (разобрано из {source})")
    else:
        prefix, plan = DEFAULT_PREFIX, [route_plan(t) for t in FALLBACK_ROUTES]
        print("⚪ перечень маршрутов службы недоступен — покрытие не судится")
        print(f"   искал: {a.api_source or '(относительно расположения этой копии)'}")
        print(f"   работаю на резервном списке из {len(FALLBACK_ROUTES)} адресов "
              "(read-only проверяется, полнота — нет)")

    round_statuses = []
    for round_ in (1, 2):
        round_statuses.append(probe_round(a.api, prefix, plan))
        if round_ == 1:
            time.sleep(2)

    ok = attempted = 0
    for st in round_statuses:
        for code in st.values():
            if code in ("unsupported", "no-data"):
                continue
            attempted += 1
            ok += (code == 200)
    print(f"эндпоинтов отвечено 200: {ok} из {attempted} (два прохода)")

    after_ic, after_fp = integrity(db), fingerprint(db)
    print(f"integrity ПОСЛЕ: {after_ic}")
    print(f"отпечаток ПОСЛЕ: {after_fp}")

    red = []
    if before_ic != "ok" or after_ic != "ok":
        red.append("integrity_check не ok")
    if before_fp != after_fp:
        red.append("ОТПЕЧАТОК БАЗЫ ИЗМЕНИЛСЯ за время прогона — кто-то писал")
    if ok != attempted:
        red.append(f"эндпоинты: {ok} из {attempted}")
    if health.get("readOnly") is not True:
        red.append(f"health.readOnly = {health.get('readOnly')!r} — ЗАМОК СНЯТ или замер сломан")

    if source is not None:
        templates = [item["template"] for item in plan]
        covered = {t for st in round_statuses for t, c in st.items() if c == 200}
        uncovered = [t for t in templates if t not in covered]
        print(f"обойдено {len(covered)} из {len(templates)} маршрутов")
        for t in uncovered:
            codes = {st.get(t) for st in round_statuses}
            if "unsupported" in codes:
                reason = "неизвестная форма параметра — проверка не умеет её разворачивать"
            elif codes <= {"no-data"}:
                reason = "нет данных"
            else:
                seen = sorted(str(c) for c in codes if c not in (None, "no-data"))
                reason = "нет данных" if not seen else f"код ответа {', '.join(seen)}"
            print(f"   не обойдён: {prefix}{t} — {reason}")
        if uncovered:
            red.append(f"маршруты не обойдены: {len(uncovered)} из {len(templates)}")

    if red:
        print("⛔ КРАСНЫЙ: " + " · ".join(red))
        return 1
    print("✅ read-only доказан: integrity ok до/после · отпечаток не изменился · "
          "health.readOnly=true (замер трёх замков живым соединением)"
          + (" · покрытие маршрутов полное" if source is not None else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
