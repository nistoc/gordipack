# -*- coding: utf-8 -*-
# PLANTS: phoenix
"""ПРИЁМКА сторожа объёма памяти (guard-phoenix-volume.py, заход 4 ⑨).

Порог назван ЧИСЛОМ здесь же: 20 000 знаков на раздел. Судим по ПОДСАЖЕННОМУ
разделу в песочной базе, не по живому жиру: живой замер меняется чужими руками.
"""
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "guard-phoenix-volume.py"
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402 — среда запуска проверки (карточка #613)
LIMIT = 20_000

CASES, OK = 0, True


def case(title, verdict, detail=""):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    if detail:
        print(f"   {detail}")


# 786: тела правила memory-hot-and-archive для стенда. Образец числа роли — «роль около <число>»,
# как в живом теле правила; остальной текст нарочно похож на настоящий (раздел «около 4 000»
# рядом с ролью — образец не должен принять число раздела за число роли).
RULE_28 = ("Цель по размеру (цель, не запрет): раздел около 4 000 знаков, роль около 28 000. "
           "Не вышло — назови поимённо, что не влезло и почему; по этому числу никого не красят.")
RULE_31 = ("Цель по размеру (цель, не запрет): раздел около 4 000 знаков, роль около 31 500. "
           "Не вышло — назови поимённо, что не влезло и почему; по этому числу никого не красят.")
RULE_NONUM = ("Цель по размеру (цель, не запрет): раздел около 4 000 знаков, роль — около семи "
              "разделов на ту же норму. Не вышло — назови поимённо, что не влезло и почему.")
NO_ROW = False            # таблица правил есть, нужной строки в ней нет


def stand(tmp, name, sections, rule=None):
    """rule: None — таблицы правил нет вовсе · NO_ROW — таблица есть, правила memory-hot-and-archive нет ·
    строка — тело правила (действующее)."""
    db = Path(tmp) / f"{name}.db"
    con = sqlite3.connect(str(db))
    if rule is not None:
        con.execute("CREATE TABLE rules (rule_key TEXT, body TEXT, status TEXT)")
        if rule is not NO_ROW:
            con.execute("INSERT INTO rules VALUES ('memory-hot-and-archive', ?, 'active')", (rule,))
    con.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, "
                "saved_at TEXT, confirmed_at TEXT)")
    con.execute("CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, role TEXT, "
                "section TEXT, body TEXT, body_chars INT, saved_at TEXT, actor TEXT, "
                "reason TEXT, prev_chars INT)")
    for role, sec, n in sections:
        con.execute("INSERT INTO phoenix VALUES (?,?,?,datetime('now'),NULL)",
                    (role, sec, "ж" * n))
    con.commit()
    con.close()
    return db


def run(db):
    # Среда стенда (карточка #613): MEZO_CONTAINER — корень стенда (каталог базы), номер чата
    # не передаётся. Прежде проверка получала среду вызывающего. Базы стенда — голые файлы
    # *.db в его корне, без .mezosync — живой базой ни одна из них не становится.
    r = subprocess.run([sys.executable, str(GUARD), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8",
                       env=mezo_stand.stand_env(Path(db).parent))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-pvol-")

    db = stand(tmp, "fat", [("ZZFAT", "state", LIMIT + 5000), ("ZZOK", "state", 900)])
    out, code = run(db)
    case("① раздел толще порога (20000) → красное ПОИМЁННО (роль · раздел · размер)",
         code == 1 and "ZZFAT" in out and "state" in out and str(LIMIT + 5000) in out)
    case("② встречный: тонкий раздел соседа НЕ обвинён",
         "ZZOK" not in out.split("🔴")[-1] if "🔴" in out else False,
         "долг поимённый, не облавой")

    db = stand(tmp, "thin", [("ZZAA", "state", 900), ("ZZBB", "plan", 1500)])
    out, code = run(db)
    case("③ встречный: все разделы под порогом → 0 долга, код 0",
         code == 0 and "раздутых: 0" in out)

    db = stand(tmp, "empty", [])
    out, code = run(db)
    case("④ свежая база БЕЗ разделов → «мерить нечего» кодом 2, не «чисто»",
         code == 2 and "НОЛЬ разделов" in out,
         "пустота — не раздутость, но и не зелёное")

    db = stand(tmp, "hint", [("ZZFAT", "state", LIMIT + 1)])
    out, code = run(db)
    case("⑤ красное несёт ПУТЬ СЖАТИЯ, не «сотри»: allow-shrink + phoenix_history",
         "allow-shrink" in out and "phoenix_history" in out,
         "вынесенное не теряется — прежнее тело кладёт в историю сам save-phoenix "
         "(его механизм, его приёмка)")

    out, code = run(Path(tmp) / "нет-такой.db")
    case("⑥ базы нет → «НЕ ПРОВЕРЕНО» кодом 2, а не «чисто»", code == 2)

    # ── 786: СУММА ПО РОЛИ с порогом ИЗ ПРАВИЛА (карточка 786, замер @STUD записка #6481) ──
    # Роль с семью разделами по 17 000 знаков: ни один раздел порога (20 000) не превысил, а окно
    # чтения платится за роль целиком — 119 000 при цели правила около 28 000.
    sec7 = ["identity", "state", "plan", "history", "launcher", "rebirth", "sources"]
    db = stand(tmp, "role28", [("ZZBIG", s, 17000) for s in sec7]
               + [("ZZEDG", "state", 14001), ("ZZEDG", "plan", 14000)], rule=RULE_28)
    out, code = run(db)
    sum_lines = [l for l in out.splitlines() if "сумма по роли" in l]
    big = [l for l in sum_lines if "[ZZBIG]" in l]
    edg = [l for l in sum_lines if "[ZZEDG]" in l]
    case("786-① роль без единого раздутого раздела, но с суммой выше порога роли (из правила) → "
         "строка с суммой и порогом роли; код выхода прежний (0)",
         code == 0 and "раздутых: 0" in out and len(big) == 1 and "119000" in big[0]
         and "28000" in big[0] and len(edg) == 1 and "28001" in edg[0] and "🔴" not in out,
         f"строка роли ZZBIG: {big[0] if big else '— нет'} · на самой границе (28001 > 28000): "
         f"{'названа' if edg else 'НЕ названа'}")

    db = stand(tmp, "rolelow", [("ZZLOW", "state", 900), ("ZZLOW", "plan", 900), ("ZZLOW", "history", 900),
                                ("ZZAT", "state", 14000), ("ZZAT", "plan", 14000)], rule=RULE_28)
    out, code = run(db)
    sum_lines = [l for l in out.splitlines() if "сумма по роли" in l]
    case("786-② встречный: роли с суммой ниже порога роли (и ровно на пороге, 28000) строкой суммы НЕ отмечены",
         code == 0 and not sum_lines and "ролей выше него: 0 из 2" in out,
         "«говорит всем» неотличимо от «говорит по делу» — строка обязана быть только у превысившей")

    # ③ порог — из правила: подмена тела меняет вывод; нет числа или нет правила — третий исход словами
    sections_mid = [("ZZMID", "state", 15000), ("ZZMID", "plan", 15000)]      # 30 000: выше 28 000, ниже 31 500
    o28, c28 = run(stand(tmp, "mid28", sections_mid, rule=RULE_28))
    o31, c31 = run(stand(tmp, "mid31", sections_mid, rule=RULE_31))
    third = "порог роли в правиле не найден — сумма по роли НЕ судится"
    o_nn, c_nn = run(stand(tmp, "midnn", sections_mid, rule=RULE_NONUM))
    o_nr, c_nr = run(stand(tmp, "midnr", sections_mid, rule=NO_ROW))
    o_nt, c_nt = run(stand(tmp, "midnt", sections_mid))
    # судим по ЗАГОЛОВКУ с порогом, а не по строке роли: строку роли судит случай 786-①, и порча
    # «сумма не считается» обязана ронять ровно его, а не этот
    ok_a = ("порог роли из правила" in o28 and "28000" in o28 and
            "порог роли из правила" in o31 and "31500" in o31 and "28000" not in o31)
    ok_b = all(third in o and "сумма по роли 30000" not in o and "28000" not in o and c == 0
               for o, c in ((o_nn, c_nn), (o_nr, c_nr), (o_nt, c_nt)))
    case("786-③ порог роли берётся из правила запросом: подмена тела правила меняет вывод; "
         "числа нет / правила нет / таблицы правил нет → третий исход словами, число по умолчанию не подставлено",
         ok_a and ok_b,
        f"правило 28 000 → порог в выводе 28000 (роль 30000 названа: {'да' if '[ZZMID]' in o28 else 'нет'}); "
         f"правило 31 500 → порог в выводе 31500 (роль названа: {'да' if '[ZZMID]' in o31 else 'нет'}); "
         f"третий исход (нет числа · нет строки правила · нет таблицы): "
         f"{[third in o for o in (o_nn, o_nr, o_nt)]}")

    db = stand(tmp, "fatrole", [("ZZFAT", "state", LIMIT + 5000), ("ZZFAT", "plan", 5000)], rule=RULE_28)
    out, code = run(db)
    case("786-код класс исхода не строже: раздутый раздел + сумма по роли → код 1, как у раздутого раздела; "
         "красное — по разделу поимённо",
         code == 1 and "🔴 [ZZFAT · state]" in out,
         "строка суммы — ℹ️ (цель правила, не запрет): общий прогон краснеет ровно как и прежде")

    print()
    print(f"{'✅ ПРОВЕРКА ОБЪЁМА ПРИНЯТА' if OK else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}")
    if OK:
        import shutil
        mezo_stand.remove_tree(tmp)
    else:
        print(f"📂 стенд сохранён: {tmp}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
