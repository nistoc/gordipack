# -*- coding: utf-8 -*-
"""measure-tool-brevity.py — сколько СИМВОЛОВ И ОЦЕНОЧНЫХ ТОКЕНОВ печатает ФИКСИРОВАННЫЙ
набор вызовов инструментов координации, от имени ОДНОЙ роли (PROTO).

ЗАЧЕМ. measure-context-cost.py меряет цену ЛЕНТЫ и памяти роли. Этот файл меряет ДРУГОЕ:
многословность САМИХ ИНСТРУМЕНТОВ — сколько текста они печатают в ответ на обычные вызовы
(объявление, критика, отказ, лекция про формы). Метод счёта токенов — тот же, что в
measure-context-cost.py: токенизатор не запускается, считаются СИМВОЛЫ и переводятся в
токены коэффициентом LO/HI (диапазон, не число — единственное число здесь легко принять
за замер, каким он не является).

ЧТО ЭТО МЕРИТ.
  Один прогон ФИКСИРОВАННОГО списка вызовов (см. CALLS ниже), от имени роли PROTO:
  печатный вывод каждого вызова (stdout+stderr вместе) — в символах, строках и оценке
  токенов; код возврата; час UTC. Часть вызовов идёт по ЖИВОЙ базе (только чтение:
  read-phoenix, backlog list, guard-all), часть — на ВРЕМЕННОЙ КОПИИ базы (песочница
  mezo_stand: add/claim/lease/save-phoenix — эти пишут, и живого хозяйства касаться нельзя).

ЧЕГО ЭТО НЕ МЕРИТ (границы названы вслух, чтобы число не приняли за больше, чем оно есть):
  - НЕ все инструменты контура — только фиксированный список ниже. Другие инструменты
    (init-group, migrate-md-to-sqlite, ...) в замер не входят.
  - НЕ разные роли — вызовы идут от PROTO. У другой роли другой долг ленты и другая
    сохранённая память ⇒ цифры этого файла на другую роль не переносятся.
  - НЕ холодный/тёплый кэш — один прогон, случайный шум по времени диска/ОС не усреднён.
  - Песочница НЕ РАВНА живой базе ПО ДАННЫМ: живые вызовы (a, b, f ниже) видят настоящий
    объём ленты и бэклога на момент прогона; вызовы на песочнице (c, d, e) видят КОПИЮ
    живой базы, снятую В НАЧАЛЕ прогона, — совпадение с живым состоянием разовое, в
    момент копирования, дальше копия своей жизнью не живёт.
  - Это НЕ приёмка: различающих случаев, нарочной поломки и встречных здесь нет — только
    замер. Провал вызова (ненулевой код) — тоже ДАННЫЕ измерения, а не сбой этого файла:
    записывается в JSON как есть, включая полный текст вывода.

Дата: 2026-09-07.

    python measure-tool-brevity.py --list
    python measure-tool-brevity.py --out <КОНТУР>/vnext-tools/measurements/brevity-before.json
    python measure-tool-brevity.py --compare до.json после.json
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

ROLE = "PROTO"
LIVE_SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
LO, HI = 3.5, 2.5          # симв/токен — тот же метод и те же числа, что в measure-context-cost.py

TITLE = "проба замера"
BODY_PLAIN = ("тело пробы замера объёма вывода координационных инструментов; "
              "безопасно для приёмок, карточку можно закрыть или оставить как след замера.")
BODY_BARE_REF = ("хвост пробы: см. #123 — голая ссылка для замера предупреждения о "
                 "неразличимости номера; #123 не существует, это не настоящая карточка.")
DONE_WHEN = "вывод вызова сохранён измерителем в JSON и сверен глазами (--compare/--out)"
SAVE_BODY_TEXT = (
    "Проба замера объёма вывода (measure-tool-brevity.py, роль PROTO).\n"
    "Вторая строка — техническая, без сведений о реальной работе роли.\n"
    "Третья строка: этот файл безопасно перезаписывать при следующем прогоне.\n"
)

# ── ФИКСИРОВАННЫЙ НАБОР ВЫЗОВОВ ──────────────────────────────────────────────
# where: 'live' — только чтение по живой базе; 'stand' — временная копия базы (mezo_stand),
# живого хозяйства не касается. args — ШАБЛОН (id/пути карточек и объявлений неизвестны
# заранее и подставляются во время прогона placeholder'ами вида "{ИМЯ}" — см. _resolve()).
CALLS: list[dict] = [
    dict(id="rp_full_1", where="live", tool="read-phoenix.py",
         label="read-phoenix.py полный, повтор #1",
         args=["--role", ROLE]),
    dict(id="rp_full_2", where="live", tool="read-phoenix.py",
         label="read-phoenix.py полный, повтор #2",
         args=["--role", ROLE]),
    dict(id="rp_state_1", where="live", tool="read-phoenix.py",
         label="read-phoenix.py --section state, повтор #1",
         args=["--role", ROLE, "--section", "state"]),
    dict(id="rp_state_2", where="live", tool="read-phoenix.py",
         label="read-phoenix.py --section state, повтор #2",
         args=["--role", ROLE, "--section", "state"]),
    dict(id="backlog_list", where="live", tool="backlog.py",
         label="backlog.py list --status all (самый широкий разумный вид)",
         args=["list", "--role", ROLE, "--status", "all"]),
    dict(id="add_1", where="stand", tool="backlog.py",
         label="backlog.py add «проба замера» #1",
         args=["add", "--role", ROLE, "--title", TITLE, "--body", BODY_PLAIN,
               "--done-when", DONE_WHEN]),
    dict(id="add_2", where="stand", tool="backlog.py",
         label="backlog.py add «проба замера» #2",
         args=["add", "--role", ROLE, "--title", TITLE, "--body", BODY_PLAIN,
               "--done-when", DONE_WHEN]),
    dict(id="claim_1", where="stand", tool="backlog.py",
         label="backlog.py claim <только что созданной> #1",
         args=["claim", "{ADD_2_ID}", "--actor", ROLE, "--note", "проба замера"]),
    dict(id="claim_2", where="stand", tool="backlog.py",
         label="backlog.py claim <только что созданной> #2 (может отказать)",
         args=["claim", "{ADD_2_ID}", "--actor", ROLE, "--note", "проба замера"]),
    dict(id="lease_take_1", where="stand", tool="lease.py",
         label="lease.py take backlog.py #1",
         args=["take", "--role", ROLE, "--tools", "backlog.py",
               "--reason", "проба замера", "--minutes", "5"]),
    dict(id="lease_release_1", where="stand", tool="lease.py",
         label="lease.py release #1",
         args=["release", "--role", ROLE, "--id", "{LEASE_TAKE_1_ID}"]),
    dict(id="lease_take_2", where="stand", tool="lease.py",
         label="lease.py take backlog.py #2",
         args=["take", "--role", ROLE, "--tools", "backlog.py",
               "--reason", "проба замера", "--minutes", "5"]),
    dict(id="lease_release_2", where="stand", tool="lease.py",
         label="lease.py release #2",
         args=["release", "--role", ROLE, "--id", "{LEASE_TAKE_2_ID}"]),
    dict(id="add_bare_ref_1", where="stand", tool="backlog.py",
         label="backlog.py add с голой ссылкой «см. #123» #1",
         args=["add", "--role", ROLE, "--title", TITLE, "--body", BODY_BARE_REF,
               "--done-when", DONE_WHEN]),
    dict(id="add_bare_ref_2", where="stand", tool="backlog.py",
         label="backlog.py add с голой ссылкой «см. #123» #2",
         args=["add", "--role", ROLE, "--title", TITLE, "--body", BODY_BARE_REF,
               "--done-when", DONE_WHEN]),
    dict(id="save_phoenix", where="stand", tool="save-phoenix.py",
         label="save-phoenix.py --section state, тело из 3 строк (без --allow-shrink)",
         args=["--role", ROLE, "--section", "state", "--file", "{SAVE_BODY_FILE}"]),
    dict(id="guard_all", where="live", tool="guard-all.py",
         label="guard-all.py — полный прогон проверок (только чтение)",
         args=[]),
]


def tok_range(chars: int) -> tuple[int, int]:
    """Диапазон токенов из символов — LO даёт МЕНЬШЕ (оптимистично), HI — БОЛЬШЕ (пессимистично)."""
    return (round(chars / LO), round(chars / HI))


def _resolve(arg: str, ctx: dict) -> str:
    if len(arg) > 2 and arg.startswith("{") and arg.endswith("}"):
        key = arg[1:-1]
        return ctx.get(key, "0")
    return arg


def run_one(call: dict, ctx: dict, stand_db: Path) -> dict:
    tool_path = LIVE_SCRIPTS / call["tool"]
    db = LIVE_DB if call["where"] == "live" else stand_db
    resolved_args = [_resolve(a, ctx) for a in call["args"]]
    argv = [sys.executable, str(tool_path), "--db", str(db), *resolved_args]
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    try:
        r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        out, err, code = r.stdout or "", r.stderr or "", r.returncode
    except subprocess.TimeoutExpired:
        out, err, code = "", "[измеритель] ПРЕВЫШЕН ТАЙМАУТ 180 с — вызов не завершился", 124
    output = out + err
    chars = len(output)
    lines = len(output.splitlines())
    lo, hi = tok_range(chars)
    return dict(
        id=call["id"], label=call["label"], tool=call["tool"], args=call["args"],
        resolved_args=resolved_args, role=ROLE, where=call["where"],
        chars=chars, lines=lines, tokens_lo=lo, tokens_hi=hi,
        exit_code=code, ts_utc=ts, output=output,
    )


def make_stand() -> tuple[Path, Path]:
    d = mezo_stand.new("measure-tool-brevity-")
    db = d / "mezosync.db"
    shutil.copyfile(LIVE_DB, db)
    return d, db


def run_all(out_path: str | None) -> int:
    stand_dir, stand_db = make_stand()
    save_body = stand_dir / "state-proba.md"
    save_body.write_text(SAVE_BODY_TEXT, encoding="utf-8")
    ctx = {"SAVE_BODY_FILE": str(save_body)}

    records: list[dict] = []
    for call in CALLS:
        rec = run_one(call, ctx, stand_db)
        records.append(rec)
        if call["id"] == "add_2":
            m = re.search(r"backlog #(\d+)", rec["output"])
            if m:
                ctx["ADD_2_ID"] = m.group(1)
        elif call["id"] == "lease_take_1":
            m = re.search(r"ОБЪЯВЛЕНО #(\d+)", rec["output"])
            if m:
                ctx["LEASE_TAKE_1_ID"] = m.group(1)
        elif call["id"] == "lease_take_2":
            m = re.search(r"ОБЪЯВЛЕНО #(\d+)", rec["output"])
            if m:
                ctx["LEASE_TAKE_2_ID"] = m.group(1)

    print_table(records)

    if out_path:
        outp = Path(out_path)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n💾 сохранено: {outp}")

    failed = [r for r in records if r["exit_code"] != 0]
    if failed:
        print(f"\n⚠️ вызовов с ненулевым кодом возврата: {len(failed)} — это ДАННЫЕ замера, "
              f"не сбой измерителя: {', '.join(r['id'] for r in failed)}")

    return 0


def print_table(records: list[dict]) -> None:
    print("=" * 104)
    print(f"ЗАМЕР МНОГОСЛОВНОСТИ ИНСТРУМЕНТОВ КООРДИНАЦИИ — роль {ROLE}, {len(records)} "
          f"вызовов ({LO}-{HI} симв/токен, диапазон — оценка, не точное число)")
    print("=" * 104)
    print(f"{'где':5} {'инструмент':14} {'вызов':52} {'симв':>7} {'строк':>6} "
          f"{'токенов (оценка)':>18} {'код':>4}")
    total_chars = total_lo = total_hi = 0
    per_tool: dict[str, list[int]] = {}
    for r in records:
        total_chars += r["chars"]
        total_lo += r["tokens_lo"]
        total_hi += r["tokens_hi"]
        pt = per_tool.setdefault(r["tool"], [0, 0, 0])
        pt[0] += r["chars"]; pt[1] += r["tokens_lo"]; pt[2] += r["tokens_hi"]
        tok = f"{r['tokens_lo']}-{r['tokens_hi']}"
        print(f"{r['where']:5} {r['tool']:14} {r['label'][:52]:52} {r['chars']:>7} "
              f"{r['lines']:>6} {tok:>18} {r['exit_code']:>4}")
    print("-" * 104)
    for tool in sorted(per_tool):
        c, lo, hi = per_tool[tool]
        print(f"  итог {tool:14} {c:>7} симв   ≈ {lo}-{hi} токенов")
    print("=" * 104)
    print(f"ВСЕГО: {total_chars} симв ≈ {total_lo}-{total_hi} токенов за {len(records)} вызовов")


def print_list() -> None:
    print(f"ФИКСИРОВАННЫЙ НАБОР ВЫЗОВОВ, роль {ROLE} — {len(CALLS)} штук (шаблон, id/пути "
          f"подставляются во время прогона):\n")
    for i, call in enumerate(CALLS, 1):
        print(f"{i:>2}. [{call['where']:5}] {call['tool']} {' '.join(call['args'])}")
        print(f"      {call['label']}")


def _sig(rec: dict) -> tuple:
    return (rec["tool"], json.dumps(rec["args"], ensure_ascii=False, sort_keys=False))


def _index(records: list[dict]) -> dict:
    seen: dict[tuple, int] = {}
    idx: dict[tuple, dict] = {}
    for rec in records:
        s = _sig(rec)
        seen[s] = seen.get(s, 0) + 1
        idx[(*s, seen[s])] = rec
    return idx


def cmd_compare(before_path: str, after_path: str) -> int:
    before = json.loads(Path(before_path).read_text(encoding="utf-8"))
    after = json.loads(Path(after_path).read_text(encoding="utf-8"))
    bidx, aidx = _index(before), _index(after)
    keys = sorted(set(bidx) | set(aidx), key=lambda k: (k[0], k[2]))

    print("=" * 104)
    print(f"СРАВНЕНИЕ: {before_path}  →  {after_path}")
    print("=" * 104)
    print(f"{'инструмент':14} {'вызов':46} {'было':>8} {'стало':>8} {'разница':>10}")

    per_tool_before: dict[str, int] = {}
    per_tool_after: dict[str, int] = {}
    only_before, only_after = [], []
    tot_b = tot_a = 0
    for k in keys:
        tool = k[0]
        if k in bidx and k in aidx:
            b, a = bidx[k], aidx[k]
            per_tool_before[tool] = per_tool_before.get(tool, 0) + b["chars"]
            per_tool_after[tool] = per_tool_after.get(tool, 0) + a["chars"]
            tot_b += b["chars"]; tot_a += a["chars"]
            if b["chars"]:
                pct = f"{(a['chars'] - b['chars']) / b['chars'] * 100:+.0f}%"
            else:
                pct = "н/д (было 0)"
            print(f"{tool:14} {a['label'][:46]:46} {b['chars']:>8} {a['chars']:>8} {pct:>10}")
        elif k in bidx:
            only_before.append(bidx[k])
        else:
            only_after.append(aidx[k])

    print("-" * 104)
    for tool in sorted(set(per_tool_before) | set(per_tool_after)):
        b = per_tool_before.get(tool, 0)
        a = per_tool_after.get(tool, 0)
        pct = f"{(a - b) / b * 100:+.0f}%" if b else "н/д (было 0)"
        print(f"  итог {tool:14} было {b:>8} симв   стало {a:>8} симв   {pct}")
    print("=" * 104)
    pct_total = f"{(tot_a - tot_b) / tot_b * 100:+.0f}%" if tot_b else "н/д (было 0)"
    print(f"ИТОГ ПО СОВПАВШИМ ВЫЗОВАМ: было {tot_b} симв, стало {tot_a} симв, разница {pct_total}")

    if only_before:
        print(f"\n⚠️ есть только в «ДО» ({len(only_before)}): "
              + ", ".join(r["id"] for r in only_before))
    if only_after:
        print(f"⚠️ есть только в «ПОСЛЕ» ({len(only_after)}): "
              + ", ".join(r["id"] for r in only_after))
    if not only_before and not only_after:
        print("\nнаборы вызовов совпадают полностью — сравнение честное, ничего не потеряно")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Замер многословности инструментов координации: символы/строки/"
                     "оценка токенов по фиксированному набору вызовов (роль PROTO).")
    ap.add_argument("--out", help="куда сохранить снимок JSON")
    ap.add_argument("--compare", nargs=2, metavar=("ДО.JSON", "ПОСЛЕ.JSON"),
                    help="сравнить два снимка по (инструмент, аргументы, порядковый номер)")
    ap.add_argument("--list", action="store_true", help="печатает набор вызовов и выходит")
    a = ap.parse_args()

    if a.compare:
        return cmd_compare(*a.compare)
    if a.list:
        print_list()
        return 0
    return run_all(a.out)


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
