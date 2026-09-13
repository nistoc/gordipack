# -*- coding: utf-8 -*-
"""bite-empty-data-reasons.py — ПРИЁМКА: причина пустоты различается ПО ДАННЫМ,
а не угадывается «новорождённостью» контура (карточка #606).

БЕДА, РАДИ КОТОРОЙ ЗАВЕДЕНА. Приёмка bite-fresh-circuit.py, случай ⑦ «у новорождённого
контура НЕТ красных вовсе», была красной: на пустых данных свежесобранного контура
guard-section-lag.py и guard-rights-registry.py отказывали кодом 2 («данных нет —
отказ, а не зелёное») — принцип верный для ЖИВОГО контура, но на новорождённом это
красное на пустом месте, а не находка.

ПРАВКА (та же карточка) учит оба гарда различать ДВЕ разные причины пустоты:
    guard-section-lag.py ....... лента (messages_all) пуста ВООБЩЕ ⇒ ⚪, код 0
                                  лента не пуста, а сверить нечего ⇒ прежний отказ, код 2
    guard-rights-registry.py ... реестр пуст И строк §ПРАВА в памяти нигде нет ⇒ ⚪, код 0
                                  реестр пуст, а строка права в памяти ЕСТЬ ⇒ прежний отказ, код 2

СЛУЧАИ:
    ① свежий контур (init-group.py из пакета, временный каталог) — обе проверки ⇒ ⚪, код 0
    ② записки есть, памяти нет — section-lag ⇒ прежний отказ, код 2
    ③ строка прав в памяти есть, реестр пуст — rights-registry ⇒ прежний отказ, код 2
    ④ КОПИЯ живой базы — на настоящих данных новая ветка ⚪ НЕ срабатывает и отказа по
      пустоте нет. Судится ОТСУТСТВИЕ новой ветки, а не код: код на живых данных зависит
      от их сегодняшнего состояния (есть ли отставшие разделы), и случай, ждущий «код 1»,
      провалился бы без всякой поломки, как только их не станет. Если в этом контуре лента
      или реестр пусты — случай неприменим и говорит это вслух (не засчитывается)
    ⑤ нарочные поломки: условие «лента пуста» всегда истинно ⇒ красит случай ②;
      условие «строк прав нигде нет» всегда истинно ⇒ красит случай ③

⛔ Живой базы НЕ КАСАЕТСЯ: только читает её (копия в стенде, mode=ro). Стенд — через
mezo_stand (убирается при успехе, сохраняется при провале — как у соседних bite-*.py).
"""
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

HERE = Path(__file__).resolve().parent
GUARD_LAG = HERE / "guard-section-lag.py"
GUARD_RIGHTS = HERE / "guard-rights-registry.py"

# шаблон ищем по тем же раскладкам, что bite-fresh-circuit.py (карточка #145)
TEMPLATE_CANDIDATES = [mezo_paths.template_root(), HERE.parent.parent / "gordipack",
                        HERE.parent / "gordipack"]
PACK = next((p for p in TEMPLATE_CANDIDATES if (p / "scripts" / "init-group.py").exists()), None)

CASES = 0
OK = True


def case(title, verdict, detail=""):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")
    return verdict


def stand_env(container: Path) -> dict:
    """Среда для всего, что запускается на стенде: MEZO_CONTAINER закреплён за СТЕНДОМ,
    а не средой вызывающего — тот же приём, что stand_env() в bite-update-tools-rev.py
    (карточка #604): без него mezo_paths берёт контейнер из переменной среды раньше, чем
    от расположения файла, и инструмент читает (а на --apply — и пишет) ЖИВОЙ контур,
    даже получив --db на стенд."""
    return dict(os.environ, PYTHONIOENCODING="utf-8", MEZO_CONTAINER=str(container))


def run_guard(tool: Path, db: Path, container: Path, timeout=120):
    """Инструмент — С ЯВНЫМ --db на стенд, среда — закреплена за стендом (двойной замок)."""
    cmd = [sys.executable, str(tool), "--db", str(db)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=stand_env(container), timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def rights_table(*rows):
    """Раздел памяти с таблицей §ПРАВА — форма, которую guard-rights-registry.py ищет."""
    head = ["## §ПРАВА — что разрешено, ОТКУДА разрешение", "",
            "| Действие | Разрешено? | Источник |", "|---|---|---|"]
    return "\n".join(head + list(rows))


def minimal_db(path: Path, *, phoenix=(), messages=(), rights=(), rules=()):
    """Минимальная база под ОБА гарда — своя, песочная, а не живая.

    phoenix: [(role, section, body)] · messages: [(writer_role, timestamp)] ·
    rights: [(id, role, revoked_at)] · rules: [rule_key, ...] (все active)

    Таблица ленты называется messages_all — так же, как ВИД, который читает measure()
    в guard-section-lag.py; в живой базе это VIEW, здесь — обычная таблица под тем же
    именем, гарду разницы нет (он просто SELECT-ит).
    """
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
    con.execute("CREATE TABLE messages_all (id INTEGER, writer_role TEXT, body_md TEXT, "
                "timestamp TEXT)")
    con.execute("CREATE TABLE role_rights (id INTEGER PRIMARY KEY, role TEXT, revoked_at TEXT)")
    con.execute("CREATE TABLE rules (rule_key TEXT, status TEXT)")
    for role, section, body in phoenix:
        con.execute("INSERT INTO phoenix VALUES (?,?,?,?)",
                   (role, section, body, "2026-01-01 00:00:00"))
    for i, (writer_role, ts) in enumerate(messages):
        con.execute("INSERT INTO messages_all VALUES (?,?,?,?)", (i + 1, writer_role, "x", ts))
    for rid, role, revoked in rights:
        con.execute("INSERT INTO role_rights VALUES (?,?,?)", (rid, role, revoked))
    for k in rules:
        con.execute("INSERT INTO rules VALUES (?, 'active')", (k,))
    con.commit()
    con.close()
    return path


BREAKS = {
    # ⑤ (лаг): условие «лента пуста» подменено на всегда-истинное — прежний отказ (случай ②)
    # больше никогда не сработает, свежий-контурный ⚪ вытеснит его молча.
    "lag-always-empty": (GUARD_LAG, "        if message_count == 0:",
                          "        if True:  # ПОРЧА bite-empty-data-reasons"),
    # ⑤ (реестр): условие «строк прав нигде нет» подменено на всегда-истинное — прежний
    # отказ (случай ③) больше никогда не сработает.
    "rights-always-empty": (GUARD_RIGHTS, "        if no_rights_rows_anywhere:",
                             "        if True:  # ПОРЧА bite-empty-data-reasons"),
}


def broken_copy(key):
    """Копия гарда со взведённой поломкой — РЯДОМ с оригиналом (иначе import mezo_paths
    не найдётся из временного каталога), удаляется вызывающим."""
    tool, was, became = BREAKS[key]
    text = tool.read_text(encoding="utf-8")
    if was not in text:
        return None, f"поломку «{key}» НЕ УДАЛОСЬ навести: образец не найден в коде"
    copy = HERE / f"~bite-empty-data-{key}.py"
    copy.write_text(text.replace(was, became, 1), encoding="utf-8")
    return copy, ""


def main() -> int:
    stand = mezo_stand.new("bite-empty-data-")
    try:
        # ── ① свежий контур ──────────────────────────────────────────────
        if PACK is None:
            case("① свежий контур: шаблон найден", False,
                 f"⛔ ШАБЛОНА НЕТ ни в одном из мест: {[str(c) for c in TEMPLATE_CANDIDATES]}")
        else:
            mez = stand / "fresh" / ".mezosync"
            # среда закреплена за стендом и у сборки: всё, что запускается на стенде, не
            # должно слышать MEZO_CONTAINER вызывающего (урок 13.09, карточка #604)
            r = subprocess.run([sys.executable, str(PACK / "scripts" / "init-group.py"),
                                "--name", "bite606", "--path", str(mez), "--roles", "coord"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=stand_env(stand / "fresh"), timeout=300)
            fresh_db = mez / "mezosync.db"
            case("① свежий контур: сборка из пакета прошла", r.returncode == 0 and fresh_db.exists(),
                 f"код сборки {r.returncode}; пакет {PACK}")

            code, out = run_guard(GUARD_LAG, fresh_db, stand / "fresh")
            case("① section-lag на новорождённом контуре → код 0, строка ⚪",
                 code == 0 and "⚪" in out,
                 f"код {code}; " + (out.strip().splitlines()[-1] if out.strip() else "пусто"))

            code, out = run_guard(GUARD_RIGHTS, fresh_db, stand / "fresh")
            case("① rights-registry на новорождённом контуре → код 0, строка ⚪",
                 code == 0 and "⚪" in out,
                 f"код {code}; " + (out.strip().splitlines()[-1] if out.strip() else "пусто"))

        # ── ② записки есть, памяти нет ───────────────────────────────────
        db2 = minimal_db(stand / "case2.db", phoenix=(), messages=[("Y", "2026-08-06 16:30:00")])
        code, out = run_guard(GUARD_LAG, db2, stand)
        case("② записки есть, памяти нет → section-lag: прежний отказ, код 2",
             code == 2 and "ОТКАЗ: сохранённой памяти не найдено" in out,
             f"код {code}")

        # ── ③ строка прав в памяти есть, реестр пуст ─────────────────────
        db3 = minimal_db(stand / "case3.db",
                          phoenix=[("ZZK", "identity", rights_table(
                              "| что-то | ✅ стоячее право | без ссылки |"))])
        code, out = run_guard(GUARD_RIGHTS, db3, stand)
        case("③ строка прав в памяти есть, реестр пуст → rights-registry: прежний отказ, код 2",
             code == 2 and "ПУСТ" in out,
             f"код {code}")

        # ── ④ КОПИЯ живой базы — на настоящих данных новая ветка ⚪ НЕ срабатывает ──
        # Судим ОТСУТСТВИЕ новой ветки и отказа по пустоте, а не код: код на живых данных
        # зависит от их сегодняшнего состояния. Прежняя редакция случая ждала «код 1» —
        # отставшие разделы Atlas 13.09 — и провалилась бы без всякой поломки, как только
        # их не станет (или в чужом контуре). Предусловие меряется на самой копии.
        lag_fresh_line = "ни одна роль ещё не писала в ленту"
        rights_fresh_line = "прав не объявлено ни в памяти, ни в реестре"
        live, why_not = None, ""
        try:
            live = Path(mezo_paths.live_db())
            if not live.exists():
                live, why_not = None, f"живой базы нет по пути {live}"
        except (Exception, SystemExit) as e:  # контейнер не найден — mezo_paths выходит sys.exit
            why_not = f"живая база не найдена: {str(e).splitlines()[0] if str(e) else e!r}"

        if live is None:
            print(f"⚪ ④ неприменим в этом месте — {why_not}; не засчитан")
        else:
            live_copy = stand / "live-copy.db"
            shutil.copy2(live, live_copy)
            con = sqlite3.connect(f"file:{live_copy}?mode=ro", uri=True)
            message_count = con.execute("SELECT COUNT(*) FROM messages_all").fetchone()[0]
            registry_count = con.execute("SELECT COUNT(*) FROM role_rights").fetchone()[0]
            con.close()

            if message_count == 0:
                print("⚪ ④ section-lag неприменим: лента копии пуста; не засчитан")
            else:
                code, out = run_guard(GUARD_LAG, live_copy, stand)
                case("④ КОПИЯ живой базы (лента не пуста): section-lag — ни строки ⚪ "
                     "свежего контура, ни отказа по пустоте",
                     code in (0, 1) and lag_fresh_line not in out,
                     f"код {code}; записок в копии {message_count}")

            if registry_count == 0:
                print("⚪ ④ rights-registry неприменим: реестр прав копии пуст; не засчитан")
            else:
                code, out = run_guard(GUARD_RIGHTS, live_copy, stand)
                case("④ КОПИЯ живой базы (реестр не пуст): rights-registry — ни строки ⚪ "
                     "свежего контура, ни отказа по пустоте",
                     code in (0, 1) and rights_fresh_line not in out,
                     f"код {code}; записей реестра в копии {registry_count}")

        # ── ⑤ нарочные поломки — каждая красит СВОЙ случай ───────────────
        print("\n🎯 ПОЛОМКИ — каждая обязана покрасить СВОЙ случай:")
        for key, (about, should_break) in {
            "lag-always-empty": ("②", lambda code, out: not (code == 2 and
                                  "ОТКАЗ: сохранённой памяти не найдено" in out)),
            "rights-always-empty": ("③", lambda code, out: not (code == 2 and "ПУСТ" in out)),
        }.items():
            copy, trouble = broken_copy(key)
            if copy is None:
                case(f"⑤ поломка «{key}»", False, trouble)
                continue
            try:
                if key == "lag-always-empty":
                    code, out = run_guard(copy, db2, stand)
                else:
                    code, out = run_guard(copy, db3, stand)
                caught = should_break(code, out)
                case(f"⑤ поломка «{key}» красит случай {about} (условие подменено на "
                     f"всегда-истинное)", caught,
                     "" if caught else f"случай {about} не покраснел под поломкой: код {code}, "
                                       f"{out[:300]}")
            finally:
                copy.unlink(missing_ok=True)

        print()
        print(f"{'✅ ПРИЁМКА ПРИНЯТА' if OK else '🔴 НЕ ПРИНЯТА'} — {CASES} из {CASES}")
        return 0 if OK else 1
    finally:
        mezo_stand.release(stand)  # уборка отложена до исхода прогона


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
