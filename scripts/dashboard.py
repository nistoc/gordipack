#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Дашборд состояния контура мезосинка — самодостаточная HTML-страница из mezosync.db.

Запуск:
    python .mezosync/scripts/dashboard.py
    python .mezosync/scripts/dashboard.py --db <путь>/mezosync.db --out <путь>/dashboard.html

Пути по умолчанию выводятся ИЗ РАСПОЛОЖЕНИЯ СКРИПТА (портативный шаблон):
БД — <контур>/.mezosync/mezosync.db, вывод — <контур>/.mezosync/generated/dashboard.html.

Страница СТАТИЧНА — это снимок на момент генерации (время указано в шапке).
Обновление = повторный запуск. Никаких внешних ресурсов: открывается офлайн, файлом.

Все метки времени — UTC с явным суффиксом (правило timestamp-utc-in-sqlite).
"""

import argparse
import html
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Пути по умолчанию — из расположения скрипта: <контур>/.mezosync/scripts/ →
# БД в <контур>/.mezosync/, вывод в <контур>/.mezosync/generated/.
MEZO = Path(__file__).resolve().parent.parent
DEFAULT_DB = str(MEZO / "mezosync.db")
DEFAULT_OUT = str(MEZO / "generated" / "dashboard.html")

ROLES_ORDER = ["COORD", "CORE", "ING", "STUD", "TAXO", "RCC"]
ROLE_TITLES = {
    "COORD": "координатор",
    "CORE": "ядро",
    "ING": "ингест",
    "STUD": "портал",
    "TAXO": "таксономия",
    "RCC": "мост DWH",
}
OWNER_TAGS = ("owner-word", "needs-owner-word", "owner-decision")


# ─────────────────────────────── чтение БД ───────────────────────────────

def parse_ts(value):
    """Метки в БД лежат как 'YYYY-MM-DD HH:MM:SS' (UTC) — иногда с суффиксом."""
    if not value:
        return None
    s = str(value).strip().replace("UTC", "").replace("T", " ").strip()
    s = re.sub(r"[+-]\d{2}:?\d{2}$", "", s).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def humanize_age(then, now):
    if then is None:
        return "—"
    delta = now - then
    mins = int(delta.total_seconds() // 60)
    if mins < 1:
        return "только что"
    if mins < 60:
        return f"{mins} мин назад"
    hours = mins // 60
    if hours < 24:
        return f"{hours} ч назад"
    days = hours // 24
    return f"{days} дн назад"


def collect(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).replace(microsecond=0)
    data = {"now": now, "db": os.path.abspath(db_path)}

    data["max_id"] = con.execute("SELECT COALESCE(MAX(id),0) FROM messages").fetchone()[0]
    data["total_notes"] = con.execute("SELECT COUNT(*) FROM messages_all").fetchone()[0]

    cursors = {r["reader_role"]: r for r in con.execute("SELECT * FROM read_cursors")}
    # role_status может не существовать на старых копиях БД — тогда статусов просто нет
    # (тот же приём, что в export-channels: отсутствие таблицы — не крах дашборда).
    try:
        statuses = {r["role"]: r for r in con.execute("SELECT * FROM role_status")}
    except sqlite3.OperationalError:
        statuses = {}

    last_note = {}
    for r in con.execute(
        "SELECT writer_role, MAX(id) AS id, MAX(timestamp) AS ts FROM messages_all GROUP BY writer_role"
    ):
        last_note[r["writer_role"]] = r

    phoenix_saved = {}
    for r in con.execute("SELECT role, MAX(saved_at) AS saved FROM phoenix GROUP BY role"):
        phoenix_saved[r["role"]] = parse_ts(r["saved"])

    backlog_rows = [dict(r) for r in con.execute(
        "SELECT id, role, title, status, priority, tags, blocked_reason, updated_at "
        "FROM backlog WHERE status='open' ORDER BY "
        "CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, id"
    )]

    roles = []
    for role in ROLES_ORDER:
        note = last_note.get(role)
        note_ts = parse_ts(note["ts"]) if note else None
        cur = cursors.get(role)
        cursor_id = cur["last_read_id"] if cur else 0
        unread = max(0, data["max_id"] - (cursor_id or 0))
        snap = phoenix_saved.get(role)
        st = statuses.get(role)
        open_tasks = [b for b in backlog_rows if b["role"] == role]
        roles.append({
            "role": role,
            "title": ROLE_TITLES.get(role, ""),
            "status_text": (st["status"] if st else None),
            "status_at": parse_ts(st["updated_at"]) if st else None,
            "last_note_id": note["id"] if note else None,
            "last_note_at": note_ts,
            "unread": unread,
            "cursor": cursor_id,
            "snapshot_at": snap,
            "open_tasks": open_tasks,
        })
    data["roles"] = roles
    data["backlog"] = backlog_rows

    # активность ленты по дням (14 суток)
    since = (now - timedelta(days=13)).strftime("%Y-%m-%d")
    per_day = {r["d"]: r["n"] for r in con.execute(
        "SELECT substr(timestamp,1,10) AS d, COUNT(*) AS n FROM messages_all "
        "WHERE substr(timestamp,1,10) >= ? GROUP BY d", (since,)
    )}
    days = []
    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        days.append({"date": d, "count": per_day.get(d, 0)})
    data["days"] = days

    data["recent"] = [dict(r) for r in con.execute(
        "SELECT id, writer_role, timestamp, body_md FROM messages_all ORDER BY id DESC LIMIT 12"
    )]

    data["tracks"] = [dict(r) for r in con.execute(
        "SELECT track_id, title, status, owner_decision, updated_at FROM tracks ORDER BY track_id"
    )]

    data["rules_count"] = con.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    data["invariants"] = [dict(r) for r in con.execute(
        "SELECT code, description FROM invariants ORDER BY code"
    )]
    con.close()
    return data


# ─────────────────────────────── разметка ───────────────────────────────

def esc(s):
    return html.escape(str(s if s is not None else ""))


def first_line(body, limit=150):
    if not body:
        return ""
    for line in str(body).splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line[:limit] + ("…" if len(line) > limit else "")
    return str(body).strip().splitlines()[0][:limit]


def freshness_state(dt, now, warn_h, bad_h):
    """→ (иконка, подпись, класс). Состояние никогда не передаётся одним цветом."""
    if dt is None:
        return ("○", "нет данных", "muted")
    age_h = (now - dt).total_seconds() / 3600
    if age_h >= bad_h:
        return ("▲", "устарело", "bad")
    if age_h >= warn_h:
        return ("◆", "стареет", "warn")
    return ("●", "свежее", "good")


def render_role_card(r, now):
    icon_note, label_note, cls_note = freshness_state(r["last_note_at"], now, 24, 72)
    icon_snap, label_snap, cls_snap = freshness_state(r["snapshot_at"], now, 12, 48)
    unread = r["unread"]
    unread_cls = "bad" if unread > 20 else ("warn" if unread > 0 else "good")
    unread_label = "не дочитал" if unread else "дочитал ленту"
    tasks = r["open_tasks"]
    hi = sum(1 for t in tasks if t["priority"] in ("high", "critical"))
    status_line = r["status_text"] or "статус не сообщался"

    task_items = "".join(
        f'<li><span class="tid">#{t["id"]}</span> '
        f'<span class="prio prio-{esc(t["priority"])}">{esc(t["priority"])}</span> '
        f'{esc(t["title"])}</li>'
        for t in tasks[:5]
    ) or '<li class="muted">открытых задач нет</li>'
    more = f'<li class="muted">…ещё {len(tasks) - 5}</li>' if len(tasks) > 5 else ""

    return f"""
    <article class="card">
      <header class="card-h">
        <h3>{esc(r["role"])} <span class="role-sub">{esc(r["title"])}</span></h3>
        <span class="badge {unread_cls}">{"▲" if unread > 20 else ("◆" if unread else "●")} {unread} непрочитанных · {unread_label}</span>
      </header>
      <p class="status">{esc(status_line)}</p>
      <dl class="facts">
        <div><dt>последняя нота</dt><dd class="{cls_note}">{icon_note} {esc(humanize_age(r["last_note_at"], now))} <span class="muted">· {label_note}</span></dd></div>
        <div><dt>слепок сохранён</dt><dd class="{cls_snap}">{icon_snap} {esc(humanize_age(r["snapshot_at"], now))} <span class="muted">· {label_snap}</span></dd></div>
        <div><dt>открытых задач</dt><dd>{len(tasks)}{f' <span class="muted">· из них важных {hi}</span>' if hi else ''}</dd></div>
      </dl>
      <ul class="tasks">{task_items}{more}</ul>
    </article>"""


def render_activity(days):
    peak = max((d["count"] for d in days), default=0) or 1
    bars = []
    for d in days:
        h = round(d["count"] / peak * 100)
        label = f'{d["date"]} — {d["count"]} нот'
        show = str(d["count"]) if d["count"] and d["count"] >= peak * 0.55 else ""
        bars.append(
            f'<div class="bar-slot" title="{esc(label)}">'
            f'<div class="bar-val">{show}</div>'
            f'<div class="bar" style="height:{max(h, 2)}%"></div>'
            f'<div class="bar-x">{esc(d["date"][8:10])}</div></div>'
        )
    span = f'{days[0]["date"]} → {days[-1]["date"]}' if days else ""
    return f"""
    <section class="panel">
      <h2>Активность ленты <span class="muted">— нот в сутки, {esc(span)} (UTC)</span></h2>
      <div class="chart">{''.join(bars)}</div>
    </section>"""


def render_owner_queue(backlog):
    items = [b for b in backlog if b["tags"] and any(t in b["tags"] for t in OWNER_TAGS)]
    if not items:
        rows = '<li class="muted">задач, ждущих слова владельца, нет</li>'
    else:
        rows = "".join(
            f'<li><span class="tid">#{b["id"]}</span> <span class="owner-role">{esc(b["role"])}</span> '
            f'{esc(b["title"])}</li>' for b in items
        )
    return f"""
    <section class="panel">
      <h2>Ждёт слова владельца <span class="muted">— задачи, которые без решения не двинутся</span></h2>
      <ul class="plain">{rows}</ul>
    </section>"""


def render_recent(recent, now):
    rows = "".join(
        f'<tr><td class="nid">#{r["id"]}</td><td class="who">{esc(r["writer_role"])}</td>'
        f'<td class="when">{esc(humanize_age(parse_ts(r["timestamp"]), now))}</td>'
        f'<td>{esc(first_line(r["body_md"]))}</td></tr>'
        for r in recent
    )
    return f"""
    <section class="panel">
      <h2>Последние ноты</h2>
      <div class="tablewrap"><table>
        <thead><tr><th>№</th><th>кто</th><th>когда</th><th>о чём</th></tr></thead>
        <tbody>{rows}</tbody>
      </table></div>
    </section>"""


def render_tracks(tracks):
    if not tracks:
        return ""
    rows = "".join(
        f'<tr><td class="who">{esc(t["track_id"])}</td><td>{esc(t["title"])}</td>'
        f'<td>{esc(t["status"])}</td><td>{esc(t["owner_decision"] or "—")}</td></tr>'
        for t in tracks
    )
    return f"""
    <section class="panel">
      <h2>Направления работ</h2>
      <div class="tablewrap"><table>
        <thead><tr><th>код</th><th>что</th><th>состояние</th><th>решение владельца</th></tr></thead>
        <tbody>{rows}</tbody>
      </table></div>
    </section>"""


CSS = """
:root{
  --bg:#f7f7f8; --surface:#ffffff; --line:#e3e3e6;
  --ink:#1a1a1c; --ink-2:#4b4b52; --ink-mute:#8a8a93;
  --accent:#3d6fd6; --accent-soft:#dce6fa;
  --good:#1f7a4d; --warn:#8a5a00; --bad:#a32a1f;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#131316; --surface:#1c1c20; --line:#2d2d33;
    --ink:#ececf0; --ink-2:#b6b6c0; --ink-mute:#7e7e8a;
    --accent:#7ba3f0; --accent-soft:#22304d;
    --good:#5fcf95; --warn:#e0b25c; --bad:#f08076;
  }
}
:root[data-theme="dark"]{
  --bg:#131316; --surface:#1c1c20; --line:#2d2d33;
  --ink:#ececf0; --ink-2:#b6b6c0; --ink-mute:#7e7e8a;
  --accent:#7ba3f0; --accent-soft:#22304d;
  --good:#5fcf95; --warn:#e0b25c; --bad:#f08076;
}
:root[data-theme="light"]{
  --bg:#f7f7f8; --surface:#ffffff; --line:#e3e3e6;
  --ink:#1a1a1c; --ink-2:#4b4b52; --ink-mute:#8a8a93;
  --accent:#3d6fd6; --accent-soft:#dce6fa;
  --good:#1f7a4d; --warn:#8a5a00; --bad:#a32a1f;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  padding:28px 20px 60px;}
.wrap{max-width:1180px;margin:0 auto}
h1{font-size:23px;margin:0 0 4px;letter-spacing:-.2px}
h2{font-size:15px;font-weight:650;margin:0 0 14px;letter-spacing:.1px}
h3{font-size:15px;margin:0;font-weight:650}
.sub{color:var(--ink-2);margin:0 0 22px;font-size:13.5px}
.muted{color:var(--ink-mute);font-weight:400}
.good{color:var(--good)} .warn{color:var(--warn)} .bad{color:var(--bad)}
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 22px}
.kpi{background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:11px 15px;min-width:132px}
.kpi b{display:block;font-size:22px;line-height:1.2;letter-spacing:-.4px}
.kpi span{color:var(--ink-mute);font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;margin-bottom:22px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:15px 16px}
.card-h{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:9px}
.role-sub{color:var(--ink-mute);font-weight:400;font-size:12.5px}
.badge{font-size:11.5px;border:1px solid var(--line);border-radius:20px;padding:2.5px 9px;white-space:nowrap}
.badge.good{border-color:color-mix(in srgb,var(--good) 40%,var(--line))}
.badge.warn{border-color:color-mix(in srgb,var(--warn) 45%,var(--line))}
.badge.bad{border-color:color-mix(in srgb,var(--bad) 45%,var(--line))}
.status{margin:0 0 11px;font-size:13px;color:var(--ink-2)}
.facts{margin:0 0 11px;display:grid;gap:4px}
.facts div{display:flex;justify-content:space-between;gap:12px;font-size:12.5px}
.facts dt{color:var(--ink-mute);margin:0}
.facts dd{margin:0;text-align:right}
.tasks{margin:0;padding:0;list-style:none;border-top:1px solid var(--line);padding-top:9px}
.tasks li{font-size:12.5px;padding:2.5px 0;color:var(--ink-2)}
.tid{color:var(--ink-mute);font-variant-numeric:tabular-nums}
.prio{font-size:10.5px;text-transform:uppercase;letter-spacing:.4px;padding:1px 5px;border-radius:4px;border:1px solid var(--line)}
.prio-high,.prio-critical{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 40%,var(--line))}
.panel{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:16px}
.chart{display:flex;align-items:flex-end;gap:5px;height:170px}
.bar-slot{flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%}
.bar{width:100%;background:var(--accent);border-radius:4px 4px 0 0;min-height:2px}
.bar-val{font-size:10.5px;color:var(--ink-mute);height:14px;font-variant-numeric:tabular-nums}
.bar-x{font-size:10.5px;color:var(--ink-mute);margin-top:5px;font-variant-numeric:tabular-nums}
.plain{margin:0;padding:0;list-style:none}
.plain li{padding:4px 0;font-size:13px;border-bottom:1px solid var(--line)}
.plain li:last-child{border-bottom:0}
.owner-role{display:inline-block;min-width:44px;color:var(--accent);font-size:11.5px;font-weight:650}
.tablewrap{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;font-weight:600;color:var(--ink-mute);font-size:11.5px;text-transform:uppercase;
  letter-spacing:.5px;padding:0 10px 7px 0;border-bottom:1px solid var(--line)}
td{padding:6px 10px 6px 0;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:0}
.nid,.when{color:var(--ink-mute);white-space:nowrap;font-variant-numeric:tabular-nums}
.who{font-weight:650;white-space:nowrap}
footer{color:var(--ink-mute);font-size:12px;margin-top:26px;line-height:1.7}
"""


def render(d):
    now = d["now"]
    stamp = now.strftime("%Y-%m-%d %H:%M UTC")
    roles = d["roles"]
    awake = [r for r in roles if r["last_note_at"] and (now - r["last_note_at"]).total_seconds() < 6 * 3600]
    unread_total = sum(r["unread"] for r in roles)
    open_total = len(d["backlog"])
    owner_waiting = len([b for b in d["backlog"] if b["tags"] and any(t in b["tags"] for t in OWNER_TAGS)])

    cards = "".join(render_role_card(r, now) for r in roles)

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Мезосинк — состояние контура Atlas</title>
<style>{CSS}</style></head>
<body><div class="wrap">
  <h1>Состояние контура Atlas</h1>
  <p class="sub">Снимок на <strong>{esc(stamp)}</strong> · источник — mezosync.db ·
     страница статична, обновление = повторный запуск генератора</p>

  <div class="kpis">
    <div class="kpi"><b>{len(awake)} / {len(roles)}</b><span>ролей писали за 6 часов</span></div>
    <div class="kpi"><b>{d["max_id"]}</b><span>нот в ленте всего</span></div>
    <div class="kpi"><b>{unread_total}</b><span>непрочитанных суммарно</span></div>
    <div class="kpi"><b>{open_total}</b><span>открытых задач</span></div>
    <div class="kpi"><b>{owner_waiting}</b><span>ждут слова владельца</span></div>
    <div class="kpi"><b>{d["rules_count"]}</b><span>правил протокола</span></div>
  </div>

  <div class="grid">{cards}</div>

  {render_owner_queue(d["backlog"])}
  {render_activity(d["days"])}
  {render_recent(d["recent"], now)}
  {render_tracks(d["tracks"])}

  <footer>
    Состояние показано значком и подписью, не только цветом: ● свежее · ◆ стареет · ▲ устарело · ○ нет данных.<br>
    «Непрочитанные» = разница между концом ленты и курсором роли; у спящей роли это норма, а не тревога.<br>
    База: {esc(d["db"])} · всего записей ленты с историей: {d["total_notes"]}.
  </footer>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description="Дашборд состояния контура мезосинка (HTML-снимок).")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"БД не найдена: {args.db}")

    # messages_all — VIEW модели мезосинка (live+history), из неё строится вся лента дашборда.
    # В свежей схеме её может не быть: сообщаем и выходим, а не падаем опакой ошибкой.
    _c = sqlite3.connect(args.db)
    has_view = _c.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='messages_all'").fetchone()[0]
    _c.close()
    if not has_view:
        raise SystemExit("VIEW messages_all в схеме нет — дашборд строить не из чего "
                         "(докати схему до messages_all live+history).")

    data = collect(args.db)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(data))
    print(f"OK → {os.path.abspath(args.out)}  (снимок {data['now'].strftime('%Y-%m-%d %H:%M UTC')})")


if __name__ == "__main__":
    main()
