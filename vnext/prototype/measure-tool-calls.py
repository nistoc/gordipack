# -*- coding: utf-8 -*-
"""measure-tool-calls.py — сколько раз инструменты контура РЕАЛЬНО звали из чатов за период.

ЗАЧЕМ. Экономия «на один вызов» ничего не говорит, пока не помножена на число вызовов.
Число берётся не «примерно», а из записей разговоров всех чатов контура (файлы *.jsonl
в каталоге проекта Claude Code): считаются команды оболочки (tool_use с name=Bash,
поле input.command), в которых встречается образец инструмента. Час записи — поле
timestamp (UTC) самой записи; команды без него считаются отдельно и в период не входят.

ГДЕ ЛЕЖИТ КОМАНДА В ЗАПИСИ (это и была причина провала первого счёта чужой рукой,
записка #4944): не поле «command» верхнего уровня, а
    запись → message → content[] → элемент type="tool_use", name="Bash" → input.command

ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ:
  · считаются только вызовы ИЗ ОБОЛОЧКИ чата; вызовы инструментов друг из друга
    (приёмки зовут общий прогон через subprocess) сюда не попадают — это другой счёт;
  · вызовы помощников (субагентов) в записи того же чата считаются наравне с вызовами
    роли — отделить их этот измеритель не умеет и не притворяется;
  · образцы — регулярные выражения по тексту команды; сколько строк в команде — столько
    и совпадений может быть; «backlog.py list» с --status all и без — два разных образца,
    потому что у них разная цена вывода.

Использование (пути — forward-slash, каталог по умолчанию = каталог записей ЭТОГО контура):
    python <КОНТУР>/vnext-tools/measure-tool-calls.py
    python <КОНТУР>/vnext-tools/measure-tool-calls.py --since 2026-09-01 --until 2026-09-07
    python <КОНТУР>/vnext-tools/measure-tool-calls.py --tool "guard-all\\.py" --per-call guard-all=4641
    python <КОНТУР>/vnext-tools/measure-tool-calls.py --dir <каталог с *.jsonl> --by-file

--per-call ИМЯ=ЗНАКОВ — экономия на один вызов (из сравнения снимков measure-tool-brevity.py);
измеритель умножает её на число вызовов и печатает оценку за период в знаках и токенах
(2,5–3,5 знака на токен — та же мерка, что у measure-tool-brevity.py).

Дата: 2026-09-07 12:25 UTC. Карточка #593 (пункт ⑦ переноса), перенесено из песочницы
по просьбе COORD (записка #4944).
"""
from __future__ import annotations

import argparse
import collections
import glob
import io
import json
import re
from datetime import date, timedelta
from pathlib import Path

ОБРАЗЦЫ_ПО_УМОЛЧАНИЮ = {
    "backlog list --status all": r"backlog\.py\s+list\b[^\n|;&]*--status\s+all",
    "backlog list (прочие)":     r"backlog\.py\s+list\b(?![^\n|;&]*--status\s+all)",
    "guard-all":                 r"guard-all\.py\b",
    "role-brief":                r"role-brief\.py\b",
    "read-phoenix полный":       r"read-phoenix\.py(?![^\n|;&]*--section)",
    "read-messages":             r"read-messages\.py\b",
}
LO, HI = 3.5, 2.5   # знаков на токен: нижняя оценка токенов — делить на 3,5, верхняя — на 2,5


def каталог_записей_по_умолчанию() -> Path:
    """Каталог записей Claude Code для ЭТОГО контура: ~/.claude/projects/<путь контура,
    где каждый не-буквенно-цифровой знак заменён на «-»>. Контур — родитель vnext-tools."""
    контур = Path(__file__).resolve().parent.parent
    имя = re.sub(r"[^A-Za-z0-9]", "-", str(контур))
    return Path.home() / ".claude" / "projects" / имя


def команды_из_файла(path: str):
    """(дата UTC или '', текст команды) для каждого вызова оболочки в записи."""
    with io.open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except Exception:                       # noqa: BLE001 — битая строка записи, не наша беда
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            ts = (rec.get("timestamp") or "")[:10]
            for blk in content:
                if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name") == "Bash":
                    yield ts, (blk.get("input") or {}).get("command", "") or ""


def main() -> int:
    ap = argparse.ArgumentParser(description="число вызовов инструментов контура из чатов за период")
    ap.add_argument("--dir", default=None, help="каталог с *.jsonl (по умолчанию — записи этого контура)")
    ap.add_argument("--since", default=None, help="с даты (UTC, YYYY-MM-DD); по умолчанию — 6 дней назад")
    ap.add_argument("--until", default=None, help="по дату включительно (UTC); по умолчанию — сегодня")
    ap.add_argument("--tool", action="append", default=[],
                    help="образец (регулярное выражение по тексту команды); можно несколько; "
                         "без него — набор по умолчанию (list · guard-all · role-brief · read-phoenix · read-messages)")
    ap.add_argument("--per-call", action="append", default=[],
                    help="ИМЯ=ЗНАКОВ — экономия на вызов для оценки за период (имя — как в таблице)")
    ap.add_argument("--by-file", action="store_true", help="печатать счёт по каждому файлу записи")
    a = ap.parse_args()

    каталог = Path(a.dir) if a.dir else каталог_записей_по_умолчанию()
    файлы = sorted(glob.glob(str(каталог / "*.jsonl")))
    if not файлы:
        print(f"⛔ записей не найдено: {каталог} — каталог пуст или не тот; укажи --dir")
        return 2
    until = a.until or date.today().isoformat()
    since = a.since or (date.fromisoformat(until) - timedelta(days=6)).isoformat()
    образцы = ({p: p for p in a.tool} if a.tool else ОБРАЗЦЫ_ПО_УМОЛЧАНИЮ)
    рег = {k: re.compile(v) for k, v in образцы.items()}

    итого = collections.Counter(); по_файлам = {}; по_дням = collections.Counter()
    команд = 0; без_даты = 0; вне_периода = 0
    for f in файлы:
        cnt = collections.Counter()
        for ts, cmd in команды_из_файла(f):
            if not ts:
                без_даты += 1
                continue
            if not (since <= ts <= until):
                вне_периода += 1
                continue
            команд += 1
            for k, p in рег.items():
                n = len(p.findall(cmd))
                if n:
                    cnt[k] += n
                    по_дням[(k, ts)] += n
        if cnt:
            по_файлам[Path(f).name[:8]] = cnt
            итого.update(cnt)

    print(f"записи: {каталог}")
    print(f"файлов {len(файлы)} · период {since}…{until} (UTC, по полю timestamp записи) · "
          f"команд оболочки в периоде {команд} · вне периода {вне_периода} · без даты (не считаны) {без_даты}")
    print("\nвызовов за период:")
    for k in образцы:
        print(f"  {k:28s} {итого[k]}")
    print("\nпо дням:")
    for d in sorted({d for _, d in по_дням}):
        print(f"  {d}  " + " · ".join(f"{k}={по_дням[(k, d)]}" for k in образцы if по_дням[(k, d)]))
    if a.by_file:
        print("\nпо файлам записей (первые 8 знаков имени):")
        for f, c in sorted(по_файлам.items(), key=lambda kv: -sum(kv[1].values())):
            print(f"  {f}  " + " · ".join(f"{k}={c[k]}" for k in образцы if c[k]))
    if a.per_call:
        s = 0
        print("\nоценка экономии за период (знаков на вызов × вызовов):")
        for item in a.per_call:
            имя, _, знаков = item.partition("=")
            имя = имя.strip()
            ключ = next((k for k in образцы if k == имя or k.startswith(имя)), None)
            if ключ is None or not знаков.strip().isdigit():
                print(f"  ⚠️ «{item}» — имя не из таблицы или число не целое, пропущено")
                continue
            n = итого[ключ]; e = int(знаков); s += n * e
            print(f"  {ключ:28s} {n:5d} × {e:6d} = {n*e}")
        print(f"  ИТОГО {s} знаков ≈ {int(s/LO)}–{int(s/HI)} токенов")
    print("\n⚖️ границы: считаны только вызовы из оболочки чатов (вызовы инструментов друг из друга — нет); "
          "вызовы помощников не отделены от вызовов роли; образец совпадает по тексту команды, а не по факту запуска")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
