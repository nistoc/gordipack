# -*- coding: utf-8 -*-
r"""ПРИЁМКА линии «шаги по карточкам» вкладки «Динамика задач» — карточка #672, пункт ④ (вторая половина).

🩸 ЧЕМ ОПЛАЧЕНО. Шаг по карточке — любое её событие, КРОМЕ рождения: рождение уже считает
линия «новых карточек», и попади оно в шаги, один факт лёг бы в две линии разом. Исключение
стоит ОДНИМ условием в запросе службы (MezosyncReader.ReadTaskHistory):
    WHERE event_type IS NULL OR event_type <> 'created'
Замер живой службы дал «рождений среди шагов: 0» — но это был ОДИН замер, а не постоянная
проверка: уберёт кто-нибудь условие — число молча станет «сколько карточек родилось», и линия
шагов удвоит линию «новых», а ничто не покраснеет.

Приёмка поднимает СЛУЖБУ на КОПИИ базы (стенд mezo_stand, свой свободный порт, только чтение)
и считает по ОТВЕТУ /api/tasks/history, а не по замыслу.

Случаи (различающий = обязан ответить ИНАЧЕ у поломанной службы):
  ① среди шагов в ответе службы событий вида `created` — ноль, а шаги вообще есть     РАЗЛИЧАЮЩИЙ
  ② ВСТРЕЧНЫЙ: рождения в базе ЕСТЬ (число > 0), и линия «новых» их видит — каждая
     рождённая карточка лежит в списке карточек ответа с датой создания. Без этого
     случай ① прошёл бы и на базе без рождений, где смотреть не на что                 РАЗЛИЧАЮЩИЙ

  ③ шаг с ПУСТЫМ видом события В ШАГИ ВХОДИТ: в копию вставлена строка backlog_events с
     event_type = NULL — шагов в ответе стало на один больше, и строка с пустым видом
     в ответе есть. Ловит поломку «убрали из условия `event_type IS NULL OR`»: сравнение
     NULL с текстом даёт NULL, и такая строка молча выпала бы из линии               РАЗЛИЧАЮЩИЙ
     ⚠️ В живой схеме event_type объявлен NOT NULL — вставить NULL можно только после
     пересборки таблицы В КОПИИ без этого запрета (relax_event_type_and_insert); живая база
     не затрагивается. Пересборка не вышла — «НЕЧЕМ ПРОВЕРИТЬ».
     ⚠️ У случая ③ ДВЕ половины, и его строка называет их ПОРОЗНЬ: «строка с пустым видом
     НА МЕСТЕ» и «счёт шагов сошёлся». При поломке «условие убрано ЦЕЛИКОМ» краснеют и ①,
     и ③: строка остаётся на месте, а счёт расходится на число рождений. Подпись, говорящая
     только «не выпал молча», послала бы читателя искать пропавшую строку — а пропала не она.

Три исхода (код выхода у каждого СВОЙ — зовущий в связке их различает):
  0 — проверка прошла: все три случая верны
  1 — проверка провалилась: линия шагов берёт рождение (или линия «новых» не видит рождений)
  2 — НЕЧЕМ ПРОВЕРИТЬ: сборка не прошла · служба не поднялась · служба держит НЕ ТУ базу ·
      замок «только чтение» не подтверждён · в копии нет backlog_events · рождений в базе
      нет (случай ① был бы пустым) · шагов в ответе нет. Печатается явной строкой «НЕЧЕМ
      ПРОВЕРИТЬ» с причиной; молчаливый ноль под видом успеха запрещён.

⛔ Живую базу не меняет: из неё снимается копия (mezo_stand.snapshot_db открывает источник
   строго на чтение), служба смотрит ТОЛЬКО на копию. Живую службу 5177 и порты стенда
   контура не касается: своя служба — на свободном порту, гасится по своему объекту процесса.

Запуск:
    python <КОНТУР-или-ПАКЕТ>/vnext/prototype/bite-periscope-steps-births.py
Переменная PERISCOPE_PROJECT направляет приёмку на другую копию проекта службы (так
доказывается, что приёмка краснеет на нарочной поломке, а рабочий проект не трогается).
"""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

PROJECT = Path(os.environ.get("PERISCOPE_PROJECT")
               or mezo_paths.template_root() / "src" / "Gordi.Periscope.Api")
LIVE_DB = mezo_paths.live_db()
CASES = DIFFER = 0
REFUSED = "НЕЧЕМ ПРОВЕРИТЬ"


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def refuse(reason: str) -> int:
    """Третий исход: приёмка отказалась судить. Код 2, строка с причиной — не ноль и не провал."""
    print(f"⚪ {REFUSED}: {reason}")
    print()
    print(f"⚪ {REFUSED} — случаев {CASES}; это не «прошла» и не «провалилась»")
    return 2


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def get(port: int, path: str):
    """(код, тело). Отказ службы — тоже ответ, а не исключение."""
    url = f"http://127.0.0.1:{port}/api{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001 — службы нет: скажем словом, не следом стека
        return 0, str(e)


def port_listens(port: int) -> bool:
    s = socket.socket()
    s.settimeout(1)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def serve(db_path: Path, dll: Path):
    """Поднять службу НА КОПИИ базы. Прямой запуск dll (не `dotnet run`): процесс один,
    гасится по своему объекту, и дочернего, пережившего родителя, нет."""
    port = free_port()
    env = dict(os.environ, ASPNETCORE_ENVIRONMENT="Development")
    proc = subprocess.Popen(
        ["dotnet", str(dll), "--db", str(db_path), "--port", str(port), "--refresh", "3"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    body = None
    for _ in range(60):
        if proc.poll() is not None:
            return proc, port, False, f"процесс службы завершился кодом {proc.returncode}"
        code, body = get(port, "/health")
        if code == 200 and isinstance(body, dict) and body.get("status") == "ok":
            return proc, port, True, body
        time.sleep(1)
    return proc, port, False, body


def stop(proc, port: int) -> str:
    """Погасить свою службу и ПРОВЕРИТЬ, что порт закрыт."""
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=15)
    for _ in range(10):
        if not port_listens(port):
            return f"служба погашена: процесс завершён кодом {proc.returncode}, порт {port} закрыт"
        time.sleep(0.5)
    return f"⚠️ процесс завершён, но порт {port} всё ещё отвечает — проверь вручную"


NULL_KIND_AT = "2026-01-01 00:00:00"


def relax_event_type_and_insert(db: Path) -> tuple[int, str]:
    """В КОПИИ: снять NOT NULL с backlog_events.event_type (пересборкой таблицы) и вставить
    одну строку с event_type = NULL по существующей карточке. Возвращает (id карточки, пояснение).
    Любая неудача — исключение, приёмка превращает его в «НЕЧЕМ ПРОВЕРИТЬ»."""
    con = sqlite3.connect(str(db))
    try:
        row = con.execute("SELECT id FROM backlog ORDER BY id LIMIT 1").fetchone()
        if row is None:
            raise RuntimeError("в копии нет ни одной карточки, по которой вставить строку")
        card_id = row[0]
        con.execute("PRAGMA legacy_alter_table = ON")
        info = con.execute("PRAGMA table_info(backlog_events)").fetchall()
        cols = {r[1]: r for r in info}
        if "event_type" not in cols:
            raise RuntimeError("в backlog_events нет колонки event_type")
        note = "event_type уже допускал NULL"
        if cols["event_type"][3]:  # notnull
            defs = []
            for _cid, name, ctype, notnull, dflt, pk in info:
                d = f'"{name}" {ctype}'
                if pk:
                    d += " PRIMARY KEY AUTOINCREMENT"
                elif notnull and name != "event_type":
                    d += " NOT NULL"
                if dflt is not None:
                    d += f" DEFAULT ({dflt})"
                defs.append(d)
            names = ", ".join(f'"{c}"' for c in cols)
            con.execute("BEGIN")
            con.execute(f"CREATE TABLE backlog_events_relaxed ({', '.join(defs)})")
            con.execute(f"INSERT INTO backlog_events_relaxed ({names}) SELECT {names} FROM backlog_events")
            con.execute("DROP TABLE backlog_events")
            con.execute("ALTER TABLE backlog_events_relaxed RENAME TO backlog_events")
            con.execute("COMMIT")
            note = "NOT NULL с event_type снят пересборкой таблицы в копии"
        con.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type) VALUES (?, ?, 'BITE', NULL)",
                    (card_id, NULL_KIND_AT))
        con.commit()
        return card_id, note
    finally:
        con.close()


def main() -> int:
    root = mezo_stand.new("bite-periscope-steps-births-")
    db = root / "mezosync.db"

    # ── копия базы: источник открывается строго на чтение ────────────────────────
    if not LIVE_DB.exists():
        return refuse(f"базы-источника нет: {LIVE_DB}")
    mezo_stand.snapshot_db(LIVE_DB, db)

    # ── замер по копии прямым запросом: на чём ПРОВЕРЯЕМ ─────────────────────────
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
        if "backlog_events" not in tables or "backlog" not in tables:
            return refuse("в копии базы нет backlog или backlog_events — шагов по карточкам не из чего считать")
        births_db = con.execute("SELECT COUNT(*) FROM backlog_events WHERE event_type = 'created'").fetchone()[0]
        birth_ids = [r[0] for r in con.execute(
            "SELECT DISTINCT backlog_id FROM backlog_events WHERE event_type = 'created'")]
        steps_db = con.execute(
            "SELECT COUNT(*) FROM backlog_events WHERE event_type IS NULL OR event_type <> 'created'").fetchone()[0]
        cards_db = con.execute("SELECT COUNT(*) FROM backlog").fetchone()[0]
    finally:
        con.close()
    print(f"замер копии базы (прямой запрос): карточек {cards_db} · рождений (created) {births_db} "
          f"· событий не-рождений {steps_db}")
    if births_db == 0:
        return refuse("в базе нет ни одного рождения карточки — случай ① прошёл бы и на сломанной службе")
    if steps_db == 0:
        return refuse("в базе нет ни одного шага кроме рождения — смотреть в линии шагов нечего")

    # ── вставка строки с пустым видом в КОПИЮ (для случая ③) ─────────────────────
    try:
        null_card, relax_note = relax_event_type_and_insert(db)
    except Exception as e:  # noqa: BLE001 — любая неудача = третий исход, словом
        return refuse(f"в копию не удалось вставить строку с пустым видом события: {e}")
    print(f"в копию вставлен шаг с пустым видом события по карточке {null_card} ({relax_note})")

    # ── сборка ───────────────────────────────────────────────────────────────────
    build = subprocess.run(["dotnet", "build", "-v", "q", "--nologo"], cwd=str(PROJECT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    if build.returncode != 0:
        print((build.stdout or "")[-2000:])
        return refuse("сборка службы не прошла")
    dll = PROJECT / "bin" / "Debug" / "net10.0" / "Gordi.Viewer.Api.dll"
    if not dll.exists():
        return refuse(f"после сборки нет {dll}")

    # ── служба на копии ──────────────────────────────────────────────────────────
    proc, port, ready, health = serve(db, dll)
    ok = True
    try:
        if not ready:
            return refuse(f"служба не поднялась на копии базы (порт {port}): {health}")
        held = Path(str(health.get("activeDbPath") or "")).resolve()
        if str(held).lower() != str(db.resolve()).lower():
            return refuse(f"служба держит НЕ ТУ базу: ожидалась {db}, держит {held}")
        if health.get("readOnly") is not True:
            return refuse("служба не подтвердила замок «только чтение» (readOnly != true)")
        print(f"служба поднята на копии: порт {port}, база {held.name}, замок «только чтение» подтверждён")

        code, hist = get(port, "/tasks/history")
        if code != 200 or not isinstance(hist, dict):
            return refuse(f"/api/tasks/history ответил {code}: {str(hist)[:200]}")
        if hist.get("stepsSupported") is not True:
            return refuse(f"служба заявила, что шаги не поддержаны: {hist.get('stepsNote')}")
        steps = hist.get("steps") or []
        cards = hist.get("cards") or []
        if not steps:
            return refuse("в ответе службы нет ни одного шага — линия шагов пуста, судить нечего")

        # ① по ОТВЕТУ: среди шагов рождений нет
        born_in_steps = [s for s in steps if s.get("kind") == "created"]
        kinds = sorted({s.get("kind") or "(пусто)" for s in steps})
        ok &= case("① линия шагов не берёт рождение карточки: в ответе службы шагов вида created — ноль",
                   len(born_in_steps) == 0,
                   f"шагов в ответе {len(steps)}; из них created: {len(born_in_steps)}; "
                   f"виды: {', '.join(kinds)}", differ=True)

        # ② встречный: рождения в базе есть, и линия «новых» их видит
        cards_by_id = {c.get("id"): c for c in cards}
        unseen = [i for i in birth_ids if i not in cards_by_id or not cards_by_id[i].get("createdAt")]
        ok &= case("② ВСТРЕЧНЫЙ: рождения в базе есть, и линия «новых карточек» их видит",
                   births_db > 0 and not unseen and len(cards) == cards_db,
                   f"рождений в базе {births_db} (карточек с рождением {len(birth_ids)}); "
                   f"в ответе карточек {len(cards)} из {cards_db}; не найдено среди карточек с датой: "
                   f"{len(unseen)}", differ=True)

        # ③ шаг с пустым видом события входит в шаги
        null_steps = [s for s in steps if not s.get("kind") and s.get("at") == NULL_KIND_AT
                      and s.get("taskId") == null_card]
        # Две половины НАЗВАНЫ ПОРОЗНЬ: при поломке «условие убрано целиком» строка с пустым
        # видом остаётся на месте, а расходится счёт. Подпись обязана говорить, какая именно
        # половина не сошлась (находка приёмщика 2026-11-14 10:57 UTC).
        row_here = len(null_steps) == 1
        count_ok = len(steps) == steps_db + 1
        ok &= case("③ шаг с ПУСТЫМ видом события В ШАГИ ВХОДИТ, и счёт шагов сошёлся",
                   row_here and count_ok,
                   f"строка с пустым видом по карточке {null_card}: "
                   f"{'НА МЕСТЕ' if row_here else 'НЕ НАЙДЕНА'} (найдено {len(null_steps)}); "
                   f"счёт шагов: {'сошёлся' if count_ok else 'РАСХОДИТСЯ'} — в ответе "
                   f"{len(steps)}, ждали {steps_db + 1} (до вставки {steps_db})", differ=True)
    finally:
        print(stop(proc, port))

    print()
    print(f"{'✅ ЛИНИЯ ШАГОВ ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
