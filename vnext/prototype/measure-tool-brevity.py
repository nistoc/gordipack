# -*- coding: utf-8 -*-
"""measure-tool-brevity.py — сколько СИМВОЛОВ И ОЦЕНОЧНЫХ ТОКЕНОВ печатает ФИКСИРОВАННЫЙ
набор вызовов инструментов координации, от имени ОДНОЙ роли — той, что названа флагом
--role (без него — переменная среды MEZO_ROLE; не названа нигде — отказ словами, код 2).
Роли в файл не зашито (карточка #677, этап Э3, работа Р2): прежде замер молча шёл от
чужого имени, если его звала другая роль.

ЗАЧЕМ. measure-context-cost.py меряет цену ЛЕНТЫ и памяти роли. Этот файл меряет ДРУГОЕ:
многословность САМИХ ИНСТРУМЕНТОВ — сколько текста они печатают в ответ на обычные вызовы
(объявление, критика, отказ, лекция про формы). Метод счёта токенов — тот же, что в
measure-context-cost.py: токенизатор не запускается, считаются СИМВОЛЫ и переводятся в
токены коэффициентом LO/HI (диапазон, не число — единственное число здесь легко принять
за замер, каким он не является).

ЧТО ЭТО МЕРИТ.
  Один прогон ФИКСИРОВАННОГО списка вызовов (см. build_calls ниже), от имени названной роли:
  печатный вывод каждого вызова (stdout+stderr вместе) — в символах, строках и оценке
  токенов; код возврата; час UTC. Часть вызовов идёт по ЖИВОЙ базе (только чтение:
  read-phoenix, backlog list, guard-all), часть — на ВРЕМЕННОЙ КОПИИ базы (песочница
  mezo_stand: add/claim/lease/save-phoenix — эти пишут, и живого хозяйства касаться нельзя).

ЧЕГО ЭТО НЕ МЕРИТ (границы названы вслух, чтобы число не приняли за больше, чем оно есть):
  - НЕ все инструменты контура — только фиксированный список ниже. Другие инструменты
    (init-group, migrate-md-to-sqlite, ...) в замер не входят.
  - НЕ разные роли — вызовы идут от ОДНОЙ роли за прогон. У другой роли другой долг ленты
    и другая сохранённая память ⇒ цифры одного прогона на другую роль не переносятся, а
    снимки двух разных ролей --compare не сводит (роль входит в аргументы вызова).
  - НЕ холодный/тёплый кэш — один прогон, случайный шум по времени диска/ОС не усреднён.
  - Песочница НЕ РАВНА живой базе ПО ДАННЫМ: живые вызовы (a, b, f ниже) видят настоящий
    объём ленты и бэклога на момент прогона; вызовы на песочнице (c, d, e) видят КОПИЮ
    живой базы, снятую В НАЧАЛЕ прогона, — совпадение с живым состоянием разовое, в
    момент копирования, дальше копия своей жизнью не живёт.
  - Это НЕ приёмка: различающих случаев, нарочной поломки и встречных здесь нет — только
    замер. Провал вызова (ненулевой код) — тоже ДАННЫЕ измерения, а не сбой этого файла:
    записывается в JSON как есть, включая полный текст вывода.

Дата: 2026-09-07.

    python measure-tool-brevity.py --role <РОЛЬ> --list
    python measure-tool-brevity.py --role <РОЛЬ> --out <КОНТУР>/vnext-tools/measurements/brevity-before.json
    python measure-tool-brevity.py --compare до.json после.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

LIVE_SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
LO, HI = 3.5, 2.5          # симв/токен — тот же метод и те же числа, что в measure-context-cost.py

TITLE = "проба замера"
BODY_PLAIN = ("тело пробы замера объёма вывода координационных инструментов; "
              "безопасно для приёмок, карточку можно закрыть или оставить как след замера.")
BODY_BARE_REF = ("хвост пробы: см. #123 — голая ссылка для замера предупреждения о "
                 "неразличимости номера; #123 не существует, это не настоящая карточка.")
DONE_WHEN = "вывод вызова сохранён измерителем в JSON и сверен глазами (--compare/--out)"

def save_body_text(role: str) -> str:
    """Тело пробы сохранения памяти. Для роли PROTO побайтно то же, что до карточки #677:
    длина тела входит в печать save-phoenix, и снимки «до/после» обязаны сойтись."""
    return (
        f"Проба замера объёма вывода (measure-tool-brevity.py, роль {role}).\n"
        "Вторая строка — техническая, без сведений о реальной работе роли.\n"
        "Третья строка: этот файл безопасно перезаписывать при следующем прогоне.\n"
    )


def pick_role(flag: str | None) -> str | None:
    """От чьего имени идут вызовы: флаг --role, иначе переменная среды MEZO_ROLE.

    Нигде не названа → None, и замер отказывает словами. Литерала с именем роли здесь нет:
    замер от чужого имени читал бы не ту память и не тот долг ленты."""
    role = (flag or os.environ.get("MEZO_ROLE") or "").strip().upper()
    return role or None


# ── ФИКСИРОВАННЫЙ НАБОР ВЫЗОВОВ ──────────────────────────────────────────────
# where: 'live' — только чтение по живой базе; 'stand' — временная копия базы (mezo_stand),
# живого хозяйства не касается. args — ШАБЛОН (id/пути карточек и объявлений неизвестны
# заранее и подставляются во время прогона placeholder'ами вида "{ИМЯ}" — см. _resolve()).
# Набор строится ПОД НАЗВАННУЮ РОЛЬ: сам набор прежний, роль в нём — параметр.
def build_calls(role: str) -> list[dict]:
    return [
        dict(id="rp_full_1", where="live", tool="read-phoenix.py",
             label="read-phoenix.py полный, повтор #1",
             args=["--role", role]),
        dict(id="rp_full_2", where="live", tool="read-phoenix.py",
             label="read-phoenix.py полный, повтор #2",
             args=["--role", role]),
        dict(id="rp_state_1", where="live", tool="read-phoenix.py",
             label="read-phoenix.py --section state, повтор #1",
             args=["--role", role, "--section", "state"]),
        dict(id="rp_state_2", where="live", tool="read-phoenix.py",
             label="read-phoenix.py --section state, повтор #2",
             args=["--role", role, "--section", "state"]),
        dict(id="backlog_list", where="live", tool="backlog.py",
             label="backlog.py list --status all (самый широкий разумный вид)",
             args=["list", "--role", role, "--status", "all"]),
        dict(id="add_1", where="stand", tool="backlog.py",
             label="backlog.py add «проба замера» #1",
             args=["add", "--role", role, "--title", TITLE, "--body", BODY_PLAIN,
                   "--done-when", DONE_WHEN]),
        dict(id="add_2", where="stand", tool="backlog.py",
             label="backlog.py add «проба замера» #2",
             args=["add", "--role", role, "--title", TITLE, "--body", BODY_PLAIN,
                   "--done-when", DONE_WHEN]),
        dict(id="claim_1", where="stand", tool="backlog.py",
             label="backlog.py claim <только что созданной> #1",
             args=["claim", "{ADD_2_ID}", "--actor", role, "--note", "проба замера"]),
        dict(id="claim_2", where="stand", tool="backlog.py",
             label="backlog.py claim <только что созданной> #2 (может отказать)",
             args=["claim", "{ADD_2_ID}", "--actor", role, "--note", "проба замера"]),
        dict(id="lease_take_1", where="stand", tool="lease.py",
             label="lease.py take backlog.py #1",
             args=["take", "--role", role, "--tools", "backlog.py",
                   "--reason", "проба замера", "--minutes", "5"]),
        dict(id="lease_release_1", where="stand", tool="lease.py",
             label="lease.py release #1",
             args=["release", "--role", role, "--id", "{LEASE_TAKE_1_ID}"]),
        dict(id="lease_take_2", where="stand", tool="lease.py",
             label="lease.py take backlog.py #2",
             args=["take", "--role", role, "--tools", "backlog.py",
                   "--reason", "проба замера", "--minutes", "5"]),
        dict(id="lease_release_2", where="stand", tool="lease.py",
             label="lease.py release #2",
             args=["release", "--role", role, "--id", "{LEASE_TAKE_2_ID}"]),
        dict(id="add_bare_ref_1", where="stand", tool="backlog.py",
             label="backlog.py add с голой ссылкой «см. #123» #1",
             args=["add", "--role", role, "--title", TITLE, "--body", BODY_BARE_REF,
                   "--done-when", DONE_WHEN]),
        dict(id="add_bare_ref_2", where="stand", tool="backlog.py",
             label="backlog.py add с голой ссылкой «см. #123» #2",
             args=["add", "--role", role, "--title", TITLE, "--body", BODY_BARE_REF,
                   "--done-when", DONE_WHEN]),
        dict(id="save_phoenix", where="stand", tool="save-phoenix.py",
             label="save-phoenix.py --section state, тело из 3 строк (без --allow-shrink)",
             args=["--role", role, "--section", "state", "--file", "{SAVE_BODY_FILE}"]),
        dict(id="guard_all", where="live", tool="guard-all.py",
             label="guard-all.py — полный прогон проверок (только чтение)",
             args=[]),
        dict(id="backlog_list_open", where="live", tool="backlog.py",
             label=f"backlog.py list --role {role} (открытые, по умолчанию)",
             args=["list", "--role", role]),
        dict(id="role_brief_1", where="live", tool="role-brief.py",
             label="role-brief.py повтор #1",
             args=["--role", role]),
        dict(id="role_brief_2", where="live", tool="role-brief.py",
             label="role-brief.py повтор #2",
             args=["--role", role]),
    ]


def tok_range(chars: int) -> tuple[int, int]:
    """Диапазон токенов из символов — LO даёт МЕНЬШЕ (оптимистично), HI — БОЛЬШЕ (пессимистично)."""
    return (round(chars / LO), round(chars / HI))


def _resolve(arg: str, ctx: dict) -> str:
    if len(arg) > 2 and arg.startswith("{") and arg.endswith("}"):
        key = arg[1:-1]
        return ctx.get(key, "0")
    return arg


def run_one(call: dict, ctx: dict, stand_db: Path, role: str) -> dict:
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
        resolved_args=resolved_args, role=role, where=call["where"],
        chars=chars, lines=lines, tokens_lo=lo, tokens_hi=hi,
        exit_code=code, ts_utc=ts, output=output,
    )


def make_stand() -> tuple[Path, Path]:
    d = mezo_stand.new("measure-tool-brevity-")
    db = d / "mezosync.db"
    mezo_stand.snapshot_db(LIVE_DB, db)
    return d, db


def run_all(out_path: str | None, role: str) -> int:
    stand_dir, stand_db = make_stand()
    save_body = stand_dir / "state-proba.md"
    save_body.write_text(save_body_text(role), encoding="utf-8")
    ctx = {"SAVE_BODY_FILE": str(save_body)}

    records: list[dict] = []
    for call in build_calls(role):
        rec = run_one(call, ctx, stand_db, role)
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

    print_table(records, role)

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


def print_table(records: list[dict], role: str) -> None:
    print("=" * 104)
    print(f"ЗАМЕР МНОГОСЛОВНОСТИ ИНСТРУМЕНТОВ КООРДИНАЦИИ — роль {role}, {len(records)} "
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


def print_list(role: str) -> None:
    calls = build_calls(role)
    print(f"ФИКСИРОВАННЫЙ НАБОР ВЫЗОВОВ, роль {role} — {len(calls)} штук (шаблон, id/пути "
          f"подставляются во время прогона):\n")
    for i, call in enumerate(calls, 1):
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
                     "оценка токенов по фиксированному набору вызовов (от имени одной "
                     "роли, названной флагом --role).")
    ap.add_argument("--role", default=None,
                    help="от чьего имени идут вызовы; без флага — переменная среды "
                         "MEZO_ROLE; не названа нигде — отказ (для --compare роль не нужна)")
    ap.add_argument("--out", help="куда сохранить снимок JSON")
    ap.add_argument("--compare", nargs=2, metavar=("ДО.JSON", "ПОСЛЕ.JSON"),
                    help="сравнить два снимка по (инструмент, аргументы, порядковый номер)")
    ap.add_argument("--list", action="store_true", help="печатает набор вызовов и выходит")
    a = ap.parse_args()

    if a.compare:
        return cmd_compare(*a.compare)
    role = pick_role(a.role)
    if role is None:
        print("⛔ ЗАМЕР НЕ СОСТОЯЛСЯ: не названа роль, от имени которой идут вызовы.\n"
              "   Задай её флагом --role <РОЛЬ> или переменной среды MEZO_ROLE. Роль не\n"
              "   подставляется сама: замер от чужого имени читал бы не ту память и не тот\n"
              "   долг ленты. Ни один вызов не запускался.\n"
              "   Пример вызова:\n"
              f"      python {Path(__file__).resolve().as_posix()} --role <РОЛЬ> --out <файл.json>")
        return 2
    if a.list:
        print_list(role)
        return 0
    return run_all(a.out, role)


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
