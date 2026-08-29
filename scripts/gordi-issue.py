# -*- coding: utf-8 -*-
"""
gordi-issue.py — КАНАЛ ПРОБЛЕМ ПРОЦЕССА → issues публичного образца (П⑤ плана
«Роли не забывают»). Сырьё — вердикты вида «process» из закрытия пула (track.py).

    python <КОНТУР>/.mezosync/scripts/gordi-issue.py create --role COORD \
        --title "..." --body-file issue.md [--pool TRACK-X] [--dry-run]
    python <КОНТУР>/.mezosync/scripts/gordi-issue.py poll --role COORD
    python <КОНТУР>/.mezosync/scripts/gordi-issue.py close --role COORD --number N --note "..."

⛔ ПИСАТЕЛЬ ОДИН — КООРДИНАТОР (правило свода «один писатель на канал»). Канал смотрит
НАРУЖУ (публичный репозиторий): двое пишущих — два голоса одного контура, и читатель
не знает, которому верить. Не-координатору инструмент отказывает, а не предупреждает.

ВОРОТА ФОРМАТА (отказ при пустом разделе — пустая секция у читателя со стороны
неотличима от «нечего сказать»):
    ## ЗАМЕР ........ тексты отказов ДОСЛОВНО, пути обезличены
    ## КЛАСС ........ класс ошибки одним предложением
    ## ПРЕДЛОЖЕНИЕ .. предмет и цена
⛔ Пути ЭТОЙ машины в теле — отказ: у чужого читателя они не работают и раскрывают
лишнее. Обезличь (<КОНТУР>, <машина>) и приходи снова.

ГРАНИЦЫ: сеть зовёт ТОЛЬКО gh CLI; --dry-run и --fixture позволяют судить инструмент
БЕЗ сети (приёмка на подсунутом ответе). Жёлтое «issue без карточки >7 суток» живёт
в poll — его зовёт координатор в свой синк; в офлайновый общий прогон сеть не врезана
НАМЕРЕННО (гард, требующий сети, умирает первым же офлайном).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = "nistoc/gordipack"
SECTIONS = ("ЗАМЕР", "КЛАСС", "ПРЕДЛОЖЕНИЕ")
# приметы путей одной машины — те же роды, что у сторожа путей образца
MACHINE = re.compile(r"[A-Za-z]:[\\/](?:guts|github|Users)[\\/]", re.I)


def _gh(*args):
    p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def _writer_gate(role):
    if (role or "").upper() != "COORD":
        sys.exit("⛔ писатель канала ОДИН — координатор (правило «один писатель на канал»; "
                 "канал публичный). Отдай текст COORD запиской — решение и рука его.")


def cmd_create(a):
    _writer_gate(a.role)
    body = Path(a.body_file).read_text(encoding="utf-8")
    missing = []
    for s in SECTIONS:
        # Хвост заголовка — ТОЛЬКО пробелы той же строки: жадный \s* съедал пустую
        # строку и «телом» пустого раздела становился СОСЕДНИЙ раздел целиком —
        # ворота пропускали ровно то, что должны держать (поймано приёмкой ②).
        m = re.search(rf"##[ \t]*{s}[ \t]*\n(.*?)(?=\n##|\Z)", body, re.S)
        if not m or not m.group(1).strip():
            missing.append(s)
    if missing:
        sys.exit("⛔ issue НЕ создана — пустые разделы: " + ", ".join(missing)
                 + ". Формат: ## ЗАМЕР (дословно, обезличено) · ## КЛАСС · ## ПРЕДЛОЖЕНИЕ "
                   "(предмет и цена)")
    dirty = sorted({m.group(0) for m in MACHINE.finditer(body)})
    if dirty:
        sys.exit("⛔ issue НЕ создана — пути ЭТОЙ машины в теле: " + " · ".join(dirty)
                 + " — обезличь (<КОНТУР>/…) и приходи снова: у чужого читателя они мертвы")
    labels = ["process"] + ([f"pool-{a.pool}"] if a.pool else [])
    cmd = ["issue", "create", "--repo", REPO, "--title", a.title,
           "--body-file", str(a.body_file)]
    for lb in labels:
        cmd += ["--label", lb]
    if a.dry_run:
        print("⟨ВХОЛОСТУЮ⟩ разделы полны, отказа нет; команда (не позвана):")
        print("   gh " + " ".join(cmd))
        return
    rc, out, err = _gh(*cmd)
    if rc != 0:
        # метки может не быть в репо — заводим и повторяем один раз, говоря об этом
        if "label" in err.lower():
            for lb in labels:
                _gh("label", "create", lb, "--repo", REPO, "--force")
            rc, out, err = _gh(*cmd)
    if rc != 0:
        sys.exit(f"⛔ gh отказал (код {rc}): {err.strip()[:300]}")
    print(f"✅ issue создана: {out.strip()}")
    print("   цикл: issue → карточка PROTO с тегом «gordi-issue #N» → починка → "
          "закрой issue ссылкой на коммит")


def _issues(a):
    """Открытые process-issues: из --fixture (приёмка, без сети) или через gh."""
    if a.fixture:
        return json.loads(Path(a.fixture).read_text(encoding="utf-8"))
    rc, out, err = _gh("issue", "list", "--repo", REPO, "--label", "process",
                       "--state", "open", "--json",
                       "number,title,createdAt,comments,labels")
    if rc != 0:
        sys.exit(f"⛔ ОПРОС НЕ ВЫПОЛНЕН (gh код {rc}): {err.strip()[:200]} — это не «пусто»")
    return json.loads(out or "[]")


def cmd_poll(a):
    import sqlite3
    from mezo_paths import resolve_db
    issues = _issues(a)
    if not issues:
        print("✅ открытых process-issues нет — канал пуст (это опрошено, а не предположено)")
        return
    conn = sqlite3.connect(f"file:{Path(resolve_db(a.db, __file__)).as_posix()}?mode=ro",
                           uri=True)
    yellow = 0
    for it in issues:
        num, title = it["number"], it["title"]
        card = conn.execute("SELECT id, status FROM backlog WHERE tags LIKE ?",
                            (f'%gordi-issue #{num}%',)).fetchone()
        age = conn.execute("SELECT CAST(julianday('now') - julianday(?) AS INTEGER)",
                           (it.get("createdAt", "")[:19].replace("T", " "),)).fetchone()[0]
        comments = it.get("comments", [])
        n_comments = len(comments) if isinstance(comments, list) else int(comments or 0)
        line = f"#{num} «{title[:60]}» · {age} дн · комментариев {n_comments}"
        if card:
            print(f"   {line} · карточка #{card[0]} ({card[1]})")
        elif age is not None and age > 7:
            yellow += 1
            print(f"🟡 {line} — БЕЗ КАРТОЧКИ больше 7 суток: канал теряет заявку")
            print(f"   завести: python {Path(__file__).resolve().parent.as_posix()}/backlog.py "
                  f"add --role PROTO --title \"gordi-issue #{num}: {title[:50]}\" "
                  f"--tags \"gordi-issue #{num}\" --body \"...\" --done-when \"...\"")
        else:
            print(f"   {line} — карточки ещё нет (в пределах 7 суток)")
    conn.close()
    print(f"\nитог опроса: issues {len(issues)} · 🟡 без карточки >7 суток: {yellow}")


def cmd_close(a):
    _writer_gate(a.role)
    if not (a.note or "").strip():
        sys.exit("⛔ закрытие БЕЗ слов — читатель не узнает, чем кончилось: --note "
                 "«починено: <коммит>» или «отпало: <почему>»")
    if a.dry_run:
        print(f"⟨ВХОЛОСТУЮ⟩ gh issue close {a.number} --repo {REPO} --comment «{a.note}»")
        return
    rc, out, err = _gh("issue", "close", str(a.number), "--repo", REPO,
                       "--comment", a.note)
    if rc != 0:
        sys.exit(f"⛔ gh отказал (код {rc}): {err.strip()[:200]}")
    print(f"✅ issue #{a.number} закрыта: {a.note[:80]}")


def main():
    ap = argparse.ArgumentParser(description="Канал проблем процесса → issues образца (П⑤)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("create")
    p.add_argument("--role", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True)
    p.add_argument("--pool", help="метка pool-N")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("poll")
    p.add_argument("--role", required=True)
    p.add_argument("--db", default=None)
    p.add_argument("--fixture", help="ПРИЁМОЧНЫЙ ввод вместо сети (json списка issues)")
    p = sub.add_parser("close")
    p.add_argument("--role", required=True)
    p.add_argument("--number", required=True, type=int)
    p.add_argument("--note")
    p.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    {"create": cmd_create, "poll": cmd_poll, "close": cmd_close}[a.cmd](a)


if __name__ == "__main__":
    main()
