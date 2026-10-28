# -*- coding: utf-8 -*-
"""bite-section-lag-change.py — приёмка: раздел памяти «отстал» только от СМЕНЫ СОСТОЯНИЯ роли,
а записка без её признаков даёт предупреждение «не подтверждался» с путём --confirm (issue #38 пакета).

ЗАЧЕМ. guard-section-lag.py считал отставание от ЛЮБОЙ записки роли и от saved_at. Контур-потребитель
после шести дней тишины получил пять провалов: три роли ответили на опрос координатора — и только.
Проверка называла это «секция отстала от того, что роль успела сделать», хотя текста записок не
смотрела, и гасилась пересохранением неизменного текста, а честным --confirm — нет.

Испытуются две вещи: общая функция phoenix_lag.py (признаки смены состояния и обе меры) и
guard-section-lag.py (что печатает и каким кодом). Каждый случай — своя подставная база (схема живой
без строк, mezo_stand.empty_db) и своя роль; раздел state и plan сохранены в 10:00 UTC, записки позже.

Случаи:
  ①  записка «commit a1b2c3d …» — 🔴 «отстал от смены состояния», признак «commit», код 1
  ②  только «принято, прочитала» — код 0, 🟡 «не подтверждался», строка с --confirm, 🔴 нет
  ③  «по слову владельца …» — код 1, признак «слово владельца»
  ④  «закрыла карточку #12» (своей рукой) — код 1, признак «закрытие карточки»
  ⑤  ВСТРЕЧНЫЙ: «по опросу: закрыта карточка #12, не мной» (пересказ) — код 0
  ⑥  ВСТРЕЧНЫЙ: «заявка 1234567 прочитана» (номер без букв — не sha) — код 0
  ⑦  «замер: 13 из 13» — код 1, признак «числа замера»
  ⑧  подтверждение (confirmed_at) позже записки с commit — код 0, ни 🔴, ни 🟡
  ⑨  ВСТРЕЧНЫЙ: подтверждение раньше НОВОЙ записки с commit — код 1: подтверждение не вечно
  ⑩  две роли: у одной commit, у другой «принято» — 🔴 называет только первую, 🟡 — только вторую
  ⑪  строка hook (phoenix_lag.lag_line) на базе случая ② — молчит: ответ на опрос не отставание
  ⑫  тишина: записка с commit раньше сохранения, после — ни одной — код 0, ни 🔴, ни 🟡
     (три случая заявки — тишина ⑫, ответ «принято» ②, записка с commit ①)
  ⑬  рядом с проверкой прежний phoenix_lag.py без section_lag, годного нет нигде — отказ кодом 2
     с перечнем мест и словами «есть, но без section_lag», без трассировки (замечание приёмки PR 56)

Нарочные поломки (--break), каждая на своей копии phoenix_lag.py или guard-section-lag.py:
  any-note-red .......... любая записка — смена состояния (прежнее поведение)  → ② ⑤ ⑥ ⑩ ⑪
  no-confirm ............ мера от saved_at, подтверждение не считается        → ⑧
  sha-any-hex ........... sha — любые 7+ шестнадцатеричных знаков             → ⑥
  closure-report-counts . закрытие — любая форма «закры…», и пересказ тоже    → ⑤
  yellow-silent ......... строки 🟡 нет                                        → ② ⑩
  yellow-as-red ......... «не подтверждался» красится как отставание         → ② ⑤ ⑥ ⑩
  first-found ........... берётся первый найденный phoenix_lag.py, годен ли  → ⑬

Живой базы не касается. Испытуемая phoenix_lag.py — по MEZO_SCRIPTS_ROOT (mezo_target), по умолчанию —
установленная; guard-section-lag.py — из того же каталога, если она там есть (собранный контур), иначе из
каталога этой приёмки (пакет: она в vnext/prototype). Какая взята — в первой строке вывода.
Запуск:  python <каталог приёмок>/bite-section-lag-change.py [--break <имя>]
"""
import argparse
import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

LAG = mezo_target.script("phoenix_lag.py")
# У собранного контура проверка лежит рядом с phoenix_lag.py в .mezosync/scripts — испытуем эту пару;
# в пакете её там нет (она в vnext/prototype) — тогда копия из каталога приёмки.
_installed = mezo_target.scripts_root() / "guard-section-lag.py"
GUARD = _installed if _installed.exists() else HERE / "guard-section-lag.py"
print(f"⚖️ испытуется: {mezo_target.label()} · проверка {GUARD.as_posix()}")

SAVED = "2026-10-20 10:00:00"
WORK = "commit a1b2c3d — правка инструмента"
ACK = "принято, прочитала"

# (файл копии, образец, замена) — образец обязан встретиться ровно один раз
BREAKS = {
    "any-note-red": (
        [("phoenix_lag.py", "    changed = [(ts, marks) for ts, marks in every if marks]\n",
          '    changed = [(ts, marks or ["запись"]) for ts, marks in every]\n')],
        {"②", "⑤", "⑥", "⑩", "⑪"}),
    "no-confirm": (
        [("phoenix_lag.py",
          '    return "COALESCE(confirmed_at, saved_at)" if "confirmed_at" in cols else "saved_at"\n',
          '    return "saved_at"\n')],
        {"⑧"}),
    "sha-any-hex": (
        [("phoenix_lag.py",
          r'_SHA = re.compile(r"(?<![0-9A-Za-z])(?=[0-9a-f]*[a-f])(?=[0-9a-f]*[0-9])[0-9a-f]{7,40}(?![0-9A-Za-z])")',
          r'_SHA = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,40}(?![0-9A-Za-z])")')],
        {"⑥"}),
    "closure-report-counts": (
        [("phoenix_lag.py", r'r"\b(?:закрыл\w*|закрываю)\s+', r'r"\b(?:закры\w*)\s+')],
        {"⑤"}),
    "yellow-silent": (
        [("guard-section-lag.py", "    if unconfirmed:\n", "    if False:\n")],
        {"②", "⑩"}),
    "yellow-as-red": (
        [("guard-section-lag.py",
          'x[2]["change_lag_h"] is not None\n               and x[2]["change_lag_h"] > limit]',
          'x[2]["unconfirmed_h"] is not None\n               and x[2]["unconfirmed_h"] > limit]')],
        {"②", "⑤", "⑥", "⑩"}),
    "first-found": (
        [("guard-section-lag.py",
          "        absent = [name for name in LAG_NAMES if not hasattr(module, name)]\n",
          "        absent = []\n")],
        {"⑬"}),
}

# Прежний phoenix_lag.py (до issue #38) — без section_lag: им проверяется ⑬
OLD_LAG = "LAG_HOURS = 3\n\n\ndef memory_lag(con, role):\n    return None\n"

OK = FAIL = 0
RED = []


def case(mark, name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), mark, name)
    if detail:
        print(f"   {detail}")
    if cond:
        OK += 1
    else:
        FAIL += 1
        RED.append(mark)


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка: отставание раздела памяти — от смены состояния роли")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка: прогнать все случаи по ПОРЧЕНОЙ копии")
    a = ap.parse_args()

    stand = mezo_stand.new("bite-section-lag-change-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    tools = stand / "tools"
    guard = mezo_stand.copy_tool(GUARD, tools)
    # phoenix_lag.py — рядом с копией проверки: она ищет его там, когда MEZO_SCRIPTS_ROOT не задан
    lag_copy = mezo_stand.copy_tool(LAG, tools)

    if a.break_name:
        for name, old, new in BREAKS[a.break_name][0]:
            path = tools / name
            text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
            if text.count(old) != 1:
                print(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда в {name} "
                      f"(образец найден {text.count(old)} раз): {old.strip()[:70]}")
                return mezo_stand.finish(2)
            # байтами: запись текстом на Windows сменила бы окончания строк копии
            path.write_bytes(text.replace(old, new).encode("utf-8"))
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    env = mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8")
    env.pop("MEZO_SCRIPTS_ROOT", None)   # иначе проверка взяла бы phoenix_lag.py испытуемой копии, а не порченой
    env.pop("MEZO_ROLE", None)
    schema = mezo_paths.live_db()
    made = []

    def build(name, roles, phoenix, notes):
        """roles — имена; phoenix — (роль, раздел[, confirmed_at]); notes — (роль, час, тело)."""
        db = mezo_stand.empty_db(schema, stand / f"{name}.db")
        mezo_stand.seed_roles(db, roles)
        con = sqlite3.connect(str(db))
        with con:
            for row in phoenix:
                con.execute("INSERT INTO phoenix (role, section, body, saved_at, confirmed_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (row[0], row[1], f"раздел {row[1]} роли {row[0]} приёмки", SAVED,
                             row[2] if len(row) > 2 else None))
            for who, at, body in notes:
                con.execute("INSERT INTO messages (writer_role, timestamp, body_md) VALUES (?, ?, ?)",
                            (who, at, body))
        con.close()
        made.append(db)
        return db

    def one_role(name, role, body, at="2026-10-20 16:00:00", confirmed=None):
        phoenix = [(role, sec) + ((confirmed,) if confirmed else ()) for sec in ("state", "plan")]
        return build(name, [role], phoenix, [(role, at, body)])

    def run(db):
        r = subprocess.run([sys.executable, str(guard), "--db", str(db)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, timeout=120)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def red_part(out):
        return out.split("\n🔴 ", 1)[1] if "\n🔴 " in out else ""

    def yellow_part(out):
        part = out.split("\n🟡 ", 1)[1] if "\n🟡 " in out else ""
        return part.split("\n\n", 1)[0]

    def short(out):
        lines = [l for l in out.splitlines() if l.startswith(("🔴", "🟡", "✅", "⛔", "⚪"))]
        return " ⏎ ".join(l[:90] for l in lines) or out.strip()[:160]

    rc, out = run(one_role("c1", "ZZLAGA", WORK))
    case("①", "записка с commit — раздел отстал от смены состояния, код 1",
         rc == 1 and "раздел отстал от смены состояния" in out and "(commit)" in out,
         f"код {rc}; {short(out)}")

    db2 = one_role("c2", "ZZLAGB", ACK)
    rc, out = run(db2)
    case("②", "только «принято» — код 0, 🟡 «не подтверждался» с путём --confirm, 🔴 нет",
         rc == 0 and "раздел не подтверждался после записки" in yellow_part(out)
         and "--confirm" in yellow_part(out) and not red_part(out),
         f"код {rc}; {short(out)}")

    rc, out = run(one_role("c3", "ZZLAGC", "по слову владельца 15:50 UTC беру заявку"))
    case("③", "«слово владельца» — смена состояния, код 1",
         rc == 1 and "(слово владельца)" in out, f"код {rc}; {short(out)}")

    rc, out = run(one_role("c4", "ZZLAGD", "закрыла карточку #12 после приёмки"))
    case("④", "закрытие карточки своей рукой — смена состояния, код 1",
         rc == 1 and "(закрытие карточки)" in out, f"код {rc}; {short(out)}")

    rc, out = run(one_role("c5", "ZZLAGE", "по опросу: закрыта карточка #12, не мной"))
    case("⑤", "ВСТРЕЧНЫЙ: пересказ закрытой карточки — не смена состояния, код 0",
         rc == 0 and not red_part(out), f"код {rc}; {short(out)}")

    rc, out = run(one_role("c6", "ZZLAGF", "заявка 1234567 прочитана"))
    case("⑥", "ВСТРЕЧНЫЙ: номер без букв — не sha, код 0",
         rc == 0 and not red_part(out), f"код {rc}; {short(out)}")

    rc, out = run(one_role("c7", "ZZLAGG", "замер: 13 из 13, провалов 0"))
    case("⑦", "числа замера — смена состояния, код 1",
         rc == 1 and "(числа замера)" in out, f"код {rc}; {short(out)}")

    rc, out = run(one_role("c8", "ZZLAGH", WORK, confirmed="2026-10-20 17:00:00"))
    case("⑧", "подтверждение позже записки с commit — код 0, ни 🔴, ни 🟡",
         rc == 0 and not red_part(out) and not yellow_part(out), f"код {rc}; {short(out)}")

    rc, out = run(one_role("c9", "ZZLAGI", WORK, at="2026-10-20 18:00:00", confirmed="2026-10-20 12:00:00"))
    case("⑨", "ВСТРЕЧНЫЙ: подтверждение раньше новой записки с commit — код 1",
         rc == 1 and "раздел отстал от смены состояния" in out, f"код {rc}; {short(out)}")

    db10 = build("c10", ["ZZLAGJ", "ZZLAGK"],
                 [(r, s) for r in ("ZZLAGJ", "ZZLAGK") for s in ("state", "plan")],
                 [("ZZLAGJ", "2026-10-20 16:00:00", WORK), ("ZZLAGK", "2026-10-20 16:00:00", ACK)])
    rc, out = run(db10)
    red, yellow = red_part(out), yellow_part(out)
    case("⑩", "две роли: 🔴 только у роли с commit, 🟡 только у роли с «принято»",
         rc == 1 and "ZZLAGJ" in red and "ZZLAGK" not in red
         and "ZZLAGK" in yellow and "ZZLAGJ" not in yellow,
         f"код {rc}; в 🔴: {sorted(n for n in ('ZZLAGJ', 'ZZLAGK') if n in red)} · "
         f"в 🟡: {sorted(n for n in ('ZZLAGJ', 'ZZLAGK') if n in yellow)}")

    spec = importlib.util.spec_from_file_location("phoenix_lag_copy", lag_copy)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    con = sqlite3.connect(f"file:{db2}?mode=ro", uri=True)
    line = module.lag_line(con)
    con.close()
    case("⑪", "строка hook (lag_line) на базе случая ② молчит",
         line is None, f"строка: {line.strip()[:110] if line else 'нет'}")

    rc, out = run(one_role("c12", "ZZLAGL", WORK, at="2026-10-20 09:00:00"))
    case("⑫", "тишина: записка с commit ДО сохранения, после — ни одной — код 0, ни 🔴, ни 🟡",
         rc == 0 and not red_part(out) and not yellow_part(out), f"код {rc}; {short(out)}")

    # ⑬ копия проверки (с вложенной поломкой, если она есть) в своём каталоге рядом с прежним
    #    phoenix_lag.py; контур стенда своего рабочего каталога не имеет — годного места нет
    tools_old = stand / "tools-old"
    guard_old = mezo_stand.copy_tool(guard, tools_old)
    (tools_old / "phoenix_lag.py").write_bytes(OLD_LAG.encode("utf-8"))
    r = subprocess.run([sys.executable, str(guard_old), "--db", str(db2)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=120)
    out = (r.stdout or "") + (r.stderr or "")
    case("⑬", "прежний phoenix_lag.py без section_lag — отказ кодом 2 с перечнем мест, без трассировки",
         r.returncode == 2 and "есть, но без section_lag" in out and "Traceback" not in out,
         f"код {r.returncode}; {short(out)}")

    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL} · испытан {mezo_target.label()}")
    if a.break_name:
        expected = BREAKS[a.break_name][1]
        exact = set(RED) == expected
        print(f"{'🧪' if exact else '⚠️'} поломка «{a.break_name}»: провалились "
              f"{' '.join(RED) or 'никто'} · ждали {' '.join(sorted(expected))} — "
              f"{'ожидание ПОДТВЕРДИЛОСЬ' if exact else 'ожидание НЕ ПОДТВЕРДИЛОСЬ'}")
        if exact:
            mezo_stand.expected_break()
        return mezo_stand.finish(1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
