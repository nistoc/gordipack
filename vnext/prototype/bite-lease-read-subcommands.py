# -*- coding: utf-8 -*-
r"""ПРИЁМКА границы объявления о правке по ПОДКОМАНДАМ — карточка #391.

🩸 ЧЕМ ОПЛАЧЕНО (@CHROME, записка #4143 §④, 29.08): взяв приёмку в 12:28 UTC, он не смог
прочитать ТЕЛА карточек — backlog.py стоял под чужим объявлением и отказал даже на show.
Судил бы по реконструкции критерия из записок; спасло само гашение объявления в 12:31 —
у карточки оказалось ТРИ половины критерия, а из записки была видна одна.
🎯 Класс: замок шире защищаемого. Объявление о правке защищает от параллельной ЗАПИСИ;
чтение ей не мешает — а отказ читающему отнимает ровно тот способ, которым приёмщик судит.

Случаи:
  ① под чужим объявлением show → работает, тело видно, предупреждение
    несёт номер объявления и роль                                        РАЗЛИЧАЮЩИЙ
  ② под чужим объявлением list → работает с предупреждением              РАЗЛИЧАЮЩИЙ
  ③ встречный: status (пишущая) → отказ, как прежде                      КОНТРОЛЬ
  ④ встречный: comment (пишущая) → отказ, как прежде                     КОНТРОЛЬ
  ⑤ встречный: СВОЁ объявление → и show, и comment работают без
    предупреждения (правящая роль отлаживает своё)                       КОНТРОЛЬ
  ⑥ ОБРАТНЫЙ ХОД (в процессе): lease.check без названного признака
    (readonly=None) → отказ по имени файла; с readonly=True → тишина.
    Разница и есть починка: различает ПРИЗНАК, а не что-то попутное      РАЗЛИЧАЮЩИЙ
  ⑦ граница: объявление ПРОСРОЧЕНО → и show, и status свободны           КОНТРОЛЬ

⛔ Живая база не трогается: копия через mezo_stand, MEZO_LEASE_TEST=1 заставляет
проверку объявлений судить копию (переменная заведена в lease.py ровно для приёмок).
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

СКРИПТЫ = mezo_paths.live_scripts()
BACKLOG = str(СКРИПТЫ / "backlog.py")
LIVE_DB = mezo_paths.live_db()

CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def run(db, role, *args):
    env = dict(os.environ, MEZO_ROLE=role, MEZO_LEASE_TEST="1")
    p = subprocess.run([sys.executable, BACKLOG, "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, p.stdout, p.stderr


def main() -> int:
    ok = True
    stand = mezo_stand.new("bite-lease-read-")
    db = stand / "copy.db"
    shutil.copy2(LIVE_DB, db)

    con = sqlite3.connect(db)
    # Копия живой базы несёт и ЖИВЫЕ объявления этого часа (например, объявление самой
    # правки #391) — они срабатывали бы раньше подсаженного и судили бы не тот замок.
    # Стенд начинается с чистого реестра: гашение в КОПИИ, живую базу это не трогает.
    con.execute("UPDATE tool_leases SET released_at = datetime('now') "
                "WHERE released_at IS NULL")
    con.execute("INSERT INTO tool_leases (role, tools, reason, until_utc) VALUES "
                "('CORE', 'backlog.py', 'стендовое объявление #391', "
                "datetime('now', '+30 minutes'))")
    con.commit()
    card = con.execute("SELECT id FROM backlog ORDER BY id LIMIT 1").fetchone()[0]
    con.close()

    # ① чужое объявление, show — работает, тело видно, предупреждение с номером и ролью.
    rc, out, err = run(db, "CHROME", "show", str(card))
    ok &= case("① чужое объявление: show РАБОТАЕТ, тело видно, предупреждение с адресом",
               rc == 0 and bool(out.strip()) and "В РАБОТЕ" in err
               and "объявление #" in err and "CORE" in err,
               f"код {rc}, тело {len(out)} знаков, в предупреждении номер и роль", differ=True)

    # ② чужое объявление, list — работает с предупреждением.
    rc, out, err = run(db, "CHROME", "list", "--role", "CHROME")
    ok &= case("② чужое объявление: list РАБОТАЕТ с предупреждением",
               rc == 0 and "В РАБОТЕ" in err, f"код {rc}", differ=True)

    # ③ встречный: пишущая подкоманда — отказ, как прежде.
    rc, out, err = run(db, "CHROME", "status", str(card), "in_review", "--actor", "CHROME")
    ok &= case("③ встречный: status (пишущая) → ОТКАЗ",
               rc == 3 and "ПИШУЩ" in err.upper(),
               "правка во время чужой отладки смешала бы две работы")

    # ④ встречный: comment — тоже пишущая, тоже отказ.
    rc, out, err = run(db, "CHROME", "comment", str(card), "--actor", "CHROME",
                       "--body", "проверочный комментарий")
    ok &= case("④ встречный: comment (пишущая) → ОТКАЗ", rc == 3,
               f"код {rc} — запись под чужим объявлением не прошла")

    # ⑤ встречный: своё объявление не мешает ни чтению, ни записи.
    rc1, _, err1 = run(db, "CORE", "show", str(card))
    rc2, _, err2 = run(db, "CORE", "comment", str(card), "--actor", "CORE",
                       "--body", "своя рука во время своей правки")
    ok &= case("⑤ встречный: СВОЁ объявление → show и comment работают без предупреждения",
               rc1 == 0 and rc2 == 0 and "В РАБОТЕ" not in err1 and "В РАБОТЕ" not in err2,
               f"коды {rc1}/{rc2} — правящая роль отлаживает то, о чём объявила")

    # ⑥ ОБРАТНЫЙ ХОД в процессе: тот же файл, тот же замок — решает ПРИЗНАК.
    _sp = importlib.util.spec_from_file_location("lease_live", СКРИПТЫ / "lease.py")
    lease = importlib.util.module_from_spec(_sp)
    _sp.loader.exec_module(lease)
    os.environ["MEZO_LEASE_TEST"] = "1"
    prev_role = os.environ.get("MEZO_ROLE")
    os.environ["MEZO_ROLE"] = "CHROME"
    try:
        import contextlib
        import io
        refused = False
        try:
            # Отказ печатает свою шапку безусловно — на стенде она шум, глушим.
            with contextlib.redirect_stderr(io.StringIO()):
                lease.check(db, BACKLOG, quiet=True, readonly=None)
        except SystemExit as e:
            refused = (e.code == 3)
        passed = True
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                lease.check(db, BACKLOG, quiet=True, readonly=True)
        except SystemExit:
            passed = False
    finally:
        os.environ.pop("MEZO_LEASE_TEST", None)
        if prev_role is None:
            os.environ.pop("MEZO_ROLE", None)
        else:
            os.environ["MEZO_ROLE"] = prev_role
    ok &= case("⑥ ОБРАТНЫЙ ХОД: признак не назван → отказ по имени файла; назван → тишина",
               refused and passed,
               "различие делает именно readonly, а не что-то попутное", differ=True)

    # ⑦ граница: просроченное объявление свободно и читающим, и пишущим.
    con = sqlite3.connect(db)
    con.execute("UPDATE tool_leases SET until_utc = datetime('now', '-5 minutes') "
                "WHERE tools = 'backlog.py' AND reason LIKE 'стендовое%'")
    con.commit()
    con.close()
    rc1, _, err1 = run(db, "CHROME", "show", str(card))
    rc2, _, _ = run(db, "CHROME", "comment", str(card), "--actor", "CHROME",
                    "--body", "после истечения объявления")
    ok &= case("⑦ граница: объявление ПРОСРОЧЕНО → show и comment свободны",
               rc1 == 0 and rc2 == 0 and "В РАБОТЕ" not in err1,
               "объявление гаснет само — вечный замок учил бы обходить замки")

    print()
    print(f"{'✅ ГРАНИЦА ОБЪЯВЛЕНИЯ ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
