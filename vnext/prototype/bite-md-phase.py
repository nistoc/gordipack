# -*- coding: utf-8 -*-
"""bite-md-phase.py — приёмка: шапка read-phoenix.py говорит о md-файлах по ФАЗЕ перехода
(признак meta.md_phase), а не по одному наличию правила (issue #37 пакета, от контура-потребителя).

ЗАЧЕМ. Шапка выбирала блок «md ЗАМОРОЖЕНЫ» по наличию правила md-to-sqlite-phased-cutover и всегда
печатала «источник правды — БД» и «при расхождении верь БД». Контур с этим правилом на Фазе 1
(двойная запись, md главный) получал в одном выводе состояние Фазы 4 — противоположное своему.

Случаи (фаза кладётся в базу запросом, а не через md-phase.py: ①–⑧ и ⑪ судят только шапку):
  ① правила нет — прежний вид без md: «ИСТОЧНИК ПРАВДЫ БД», «ВЕРЬ БД», строк о фазе нет
  ② правило действует, фазы нет — «ФАЗА НЕ ЗАПИСАНА», «признака meta.md_phase в базе нет»;
     ни «ВЕРЬ БД», ни «ВЕРЬ md», ни «ЗАМОРОЖЕНЫ», ни «ИСТОЧНИК ПРАВДЫ БД»: шапка не знает и так говорит
  ③ фаза 1 — «ФАЗА 1», «ВЕРЬ md», «ГЛАВНЫЙ источник в фазе 1 — md-файлы»; ни «ВЕРЬ БД»,
     ни «ЗАМОРОЖЕНЫ», ни «ИСТОЧНИК ПРАВДЫ БД»
  ④ фаза 2 — то же с цифрой 2
  ⑤ фаза 3 — «ФАЗА 3», «база ГЛАВНАЯ», «ВЕРЬ БД»; ни «ЗАМОРОЖЕНЫ», ни «ВЕРЬ md»
  ⑥ фаза 4 — «md ЗАМОРОЖЕНЫ», «фаза 4», «ВЕРЬ БД», «ИСТОЧНИК ПРАВДЫ БД»; ни «ВЕРЬ md», ни «НЕ ЗАПИСАНА»
  ⑦ ВСТРЕЧНЫЙ: meta.md_phase = «5» — «ФАЗА НЕ ЗАПИСАНА» и «не понято», а не «ЗАМОРОЖЕНЫ»
  ⑧ ВСТРЕЧНЫЙ: правило снято (status revoked) при фазе 4 — вид без md, как ①
  ⑨ md-phase.py: показ называет правило и признак; отказы кодом 2 и база не тронута — без руки,
     фаза «7», правила нет; показ при правиле без фазы даёт строку «👉 записать»
  ⑩ md-phase.py: --set 4 пишет meta и строку журнала правок «— → 4» (md_phase_set, рука в верхнем
     регистре); повтор — «уже записано», журнал тот же; --set 1 — «4 → 1»; --dry-run --set 2 —
     ни признака, ни журнала; --clear — признака нет, журнал +1 (md_phase_clear)
  ⑪ подсказка показывается один раз, но смена фазы показывает шапку заново: второе чтение при
     фазе 4 без --full — строка-ссылка; после смены на 1 — шапка целиком с «ФАЗА 1»
  ⑫ ни в одной шапке нет неподставленных мест ({s} {n} {why} {source} {md} {trust} {role})
  ⑬ подсказка write-message.py (заявка называет и её): в --help нет безусловного «единственный
     источник правды», есть md-phase.py; отказ --md (холостой прогон) говорит, что на фазе 1–2
     md-половину пишет роль своей рукой, и называет md-phase.py
  ⑭ показ md-phase.py берёт строки шапки у read-phoenix.py, а не держит свою копию: метка, вписанная
     в блок «md ЗАМОРОЖЕНЫ» копии read-phoenix.py, видна в строке «шапка read-phoenix.py печатает»
  ⑮ ВСТРЕЧНЫЙ: meta.md_phase = «abc» — показ md-phase.py даёт «👉 записать», как и шапка в том же
     состоянии («ФАЗА НЕ ЗАПИСАНА» с командой записи)
  🪤 ⑭ и ⑮ — по замечаниям приёмки PR 55 (2026-10-28): у показа был свой словарь строк шапки,
     а «👉 записать» молчал на значении не из 1–4.

Нарочные поломки (--break), каждая на своей копии read-phoenix.py, md-phase.py или write-message.py:
  rule-presence-only ... фаза 4 при любом действующем правиле (прежнее поведение) → ② ③ ④ ⑤ ⑦ ⑨ ⑪ ⑮
                         (⑨ и ⑮: показ md-phase.py судит фазу тем же разбором, что шапка, — при
                         «фаза 4 всегда» он команды записи не даёт)
  source-always-db ..... первая строка всегда «ИСТОЧНИК ПРАВДЫ БД»               → ③ ④
  trust-always-db ...... строка о расхождении всегда «ВЕРЬ БД»                     → ③ ④
  unknown-trusts-db .... при неизвестной фазе — «ВЕРЬ БД»                         → ② ⑦
  any-digit-phase ...... любое число — фаза                                       → ⑦
  revoked-counts ....... снятое правило считается действующим                     → ⑧
  set-without-rule ..... md-phase.py пишет фазу и без правила                     → ⑨
  actor-default ........ у руки md-phase.py есть умолчание                        → ⑨
  no-audit ............. --set не пишет строку журнала правок                      → ⑩
  repeat-writes ........ повтор той же фазы пишет журнал заново                   → ⑩
  wm-sole-truth ........ в --help write-message.py прежнее «единственный источник правды» → ⑬
  wm-no-phase-hint ..... отказ --md без строки о фазе 1–2                          → ⑬
  header-says-copy ..... показ md-phase.py печатает свою копию строк шапки        → ⑭
  hint-on-value-only ... «👉 записать» — по самому значению, а не по разбору фазы  → ⑮

Живой базы не касается: подставная база (схема живой без строк, mezo_stand.empty_db) и своя роль.
Испытуемые read-phoenix.py и md-phase.py — по MEZO_SCRIPTS_ROOT (mezo_target), по умолчанию —
установленные. Запуск:  python <каталог приёмок>/bite-md-phase.py [--break <имя>]
"""
import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

READER = mezo_target.script("read-phoenix.py")
WRITER = mezo_target.script("md-phase.py")
MESSAGE = mezo_target.script("write-message.py")
print(f"⚖️ испытуется: {mezo_target.label()}")
sys.path.insert(0, str(mezo_paths.live_scripts()))
# mezo_stand — из каталога самой приёмки, той же версии пакета; вставка снимается сразу.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
sys.path.pop(0)

RULE = "md-to-sqlite-phased-cutover"
ROLE = "ZZMDPHASE"
PLACEHOLDERS = ("{s}", "{n}", "{why}", "{source}", "{md}", "{trust}", "{role}")

# (файл копии, образец, замена) — образец обязан встретиться ровно один раз
RULE_ACTIVE = '    if not row or (row[0] or "active") != "active":\n        return None, ""\n'
BREAKS = {
    "rule-presence-only": (
        [("read-phoenix.py", RULE_ACTIVE, RULE_ACTIVE + '    return 4, ""\n')],
        {"②", "③", "④", "⑤", "⑦", "⑨", "⑪", "⑮"}),
    "source-always-db": (
        [("read-phoenix.py", '"source": SOURCE_MD.replace("{n}", n)', '"source": SOURCE_DB')],
        {"③", "④"}),
    "trust-always-db": (
        [("read-phoenix.py", '"trust": TRUST_MD.replace("{n}", n)', '"trust": TRUST_DB')],
        {"③", "④"}),
    "unknown-trusts-db": (
        [("read-phoenix.py", '                "trust": TRUST_UNKNOWN}', '                "trust": TRUST_DB}')],
        {"②", "⑦"}),
    "any-digit-phase": (
        [("read-phoenix.py", 'if str(value).strip() in {"1", "2", "3", "4"}:',
          'if str(value).strip().isdigit():')],
        {"⑦"}),
    "revoked-counts": (
        [("read-phoenix.py", RULE_ACTIVE, '    if not row:\n        return None, ""\n')],
        {"⑧"}),
    "set-without-rule": (
        [("md-phase.py", '    if state != "active":\n        why =', '    if False:\n        why =')],
        {"⑨"}),
    "actor-default": (
        [("md-phase.py", '(os.environ.get("MEZO_ROLE") or "").strip()\n',
          '(os.environ.get("MEZO_ROLE") or "").strip() or "COORD"\n')],
        {"⑨"}),
    "no-audit": (
        [("md-phase.py", '    row = audit(conn, actor, "md_phase_set", f"{was} → {value}")\n',
          '    row = None\n')],
        {"⑩"}),
    "repeat-writes": (
        [("md-phase.py", '    if old is not None and str(old).strip() == value:\n',
          '    if False:\n')],
        {"⑩"}),
    "wm-sole-truth": (
        [("write-message.py",
          'description="Записать сообщение в ленту mezosync.db. В файлы механизм не пишет ни в какой "\n'
          '                    "фазе перехода md → база: где фаза 1–2 (md главные), md-половину пишет роль своей "\n'
          '                    "рукой; фазу и главную сторону печатает md-phase.py. Аварийного выхода к файлам нет: "\n',
          'description="Записать сообщение в ленту mezosync.db — единственный источник правды; "\n'
          '                    "в файлы механизм не пишет, аварийного выхода к файлам нет: "\n')],
        {"⑬"}),
    "wm-no-phase-hint": (
        [("write-message.py",
          '              "   ℹ️ Где переход md → база на фазе 1–2 (md главные), md-половину пишет роль своей\\n"\n'
          '              "      рукой; фаза контура: python " + Path(__file__).resolve().with_name("md-phase.py")'
          '.as_posix() + "\\n"\n',
          '')],
        {"⑬"}),
    "header-says-copy": (
        [("md-phase.py", '    parts = _read_phoenix.phase_parts(conn)\n',
          '    parts = {"md": "⛔ md ЗАМОРОЖЕНЫ, фаза 4\\n", "trust": "⚠️ ВЕРЬ БД. "}\n')],
        {"⑭"}),
    "hint-on-value-only": (
        [("md-phase.py", '    if state == "active" and phase == "unknown":\n',
          '    if state == "active" and value in (None, False, ""):\n')],
        {"⑮"}),
}
MARK = "ZZ-МЕТКА-ПРИЁМКИ-md-phase"

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
    ap = argparse.ArgumentParser(description="приёмка: шапка read-phoenix.py по фазе перехода md → база")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка: прогнать все случаи по ПОРЧЕНОЙ копии инструмента")
    a = ap.parse_args()

    stand = mezo_stand.new("bite-md-phase-")
    container = stand / "container"
    (container / ".mezosync").mkdir(parents=True)
    db = mezo_stand.empty_db(mezo_paths.live_db(), container / ".mezosync" / "mezosync.db")
    mezo_stand.seed_roles(db, [ROLE])

    tools = stand / "tools"
    reader = mezo_stand.copy_tool(READER, tools)
    # md-phase.py берёт разбор фазы у read-phoenix.py своего каталога (importlib, не import) —
    # копия обязана лечь рядом с копией read-phoenix.py, а не своей отдельной папкой
    writer = mezo_stand.copy_tool(WRITER, tools) if WRITER.exists() else None
    message = mezo_stand.copy_tool(MESSAGE, tools)

    if a.break_name:
        for name, old, new in BREAKS[a.break_name][0]:
            path = tools / name
            text = path.read_bytes().decode("utf-8").replace("\r\n", "\n") if path.exists() else ""
            if text.count(old) != 1:
                print(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда в {name} "
                      f"(образец найден {text.count(old)} раз): {old.strip()[:70]}")
                return mezo_stand.finish(2)
            # байтами: запись текстом на Windows сменила бы окончания строк копии
            path.write_bytes(text.replace(old, new).encode("utf-8"))
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(BREAKS[a.break_name][1]))}")

    env_base = mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8")
    env_base.pop("MEZO_ROLE", None)   # рука md-phase.py — только явным флагом в случаях ниже

    def run(tool, *args, env=None):
        r = subprocess.run([sys.executable, str(tool), "--db", str(db), *args], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", env=env or env_base)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def sql(statement, params=()):
        c = sqlite3.connect(str(db))
        try:
            rows = c.execute(statement, params).fetchall()
            c.commit()
            return rows
        finally:
            c.close()

    sql("INSERT INTO phoenix (role, section, body) VALUES (?, 'state', ?)",
        (ROLE, "память роли приёмки bite-md-phase.py на подставной базе"))

    def set_rule(status):
        sql("DELETE FROM rules WHERE rule_key = ?", (RULE,))
        if status == "active":
            sql("INSERT INTO rules (rule_key, body, status) VALUES (?, ?, 'active')",
                (RULE, "правило перехода md → база, заведено приёмкой"))
        elif status:
            # снятое правило схема держит только с часом, рукой и причиной снятия
            sql("INSERT INTO rules (rule_key, body, status, revoked_at, revoked_by, revoked_reason) "
                "VALUES (?, ?, ?, datetime('now'), ?, ?)",
                (RULE, "правило перехода md → база, заведено приёмкой", status, ROLE,
                 "снято приёмкой bite-md-phase.py"))

    def set_value(value):
        sql("DELETE FROM meta WHERE key = 'md_phase'")
        if value is not None:
            sql("INSERT INTO meta (key, value) VALUES ('md_phase', ?)", (value,))

    headers = []

    def header(rule_status, value):
        set_rule(rule_status)
        set_value(value)
        rc, out = run(reader, "--role", ROLE, "--full")
        headers.append(out)
        if rc != 0:
            print(f"   (read-phoenix.py код {rc}: {out.strip()[-300:]})")
        return out

    def has_all(out, *words):
        return all(w in out for w in words)

    def has_none(out, *words):
        return not any(w in out for w in words)

    def missing(out, need, forbid):
        lost = [w for w in need if w not in out]
        extra = [w for w in forbid if w in out]
        return f"нет: {lost or '—'} · лишнее: {extra or '—'}"

    # ① — правила нет
    out = header(None, None)
    need, forbid = ("ИСТОЧНИК ПРАВДЫ БД", "ВЕРЬ БД"), ("ПЕРЕХОД md", "ЗАМОРОЖЕНЫ", "ВЕРЬ md")
    case("①", "правила нет — прежний вид без md", has_all(out, *need) and has_none(out, *forbid),
         missing(out, need, forbid))

    # ② — правило есть, фазы нет
    out = header("active", None)
    need = ("ФАЗА НЕ ЗАПИСАНА", "признака meta.md_phase в базе нет", "сверься с правилом")
    forbid = ("ВЕРЬ БД", "ВЕРЬ md", "ЗАМОРОЖЕНЫ", "ИСТОЧНИК ПРАВДЫ БД")
    case("②", "правило есть, фазы нет — «ФАЗА НЕ ЗАПИСАНА», кому верить шапка не говорит",
         has_all(out, *need) and has_none(out, *forbid), missing(out, need, forbid))

    # ③ ④ — фазы 1 и 2
    for mark, n in (("③", "1"), ("④", "2")):
        out = header("active", n)
        need = (f"ФАЗА {n}", "ВЕРЬ md", f"ГЛАВНЫЙ источник в фазе {n} — md-файлы")
        forbid = ("ВЕРЬ БД", "ЗАМОРОЖЕНЫ", "ИСТОЧНИК ПРАВДЫ БД", "НЕ ЗАПИСАНА")
        case(mark, f"фаза {n} — md главный, при расхождении верь md",
             has_all(out, *need) and has_none(out, *forbid), missing(out, need, forbid))

    # ⑤ — фаза 3
    out = header("active", "3")
    need, forbid = ("ФАЗА 3", "база ГЛАВНАЯ", "ВЕРЬ БД"), ("ЗАМОРОЖЕНЫ", "ВЕРЬ md", "НЕ ЗАПИСАНА")
    case("⑤", "фаза 3 — база главная, md вторым экземпляром", has_all(out, *need) and has_none(out, *forbid),
         missing(out, need, forbid))

    # ⑥ — фаза 4
    out = header("active", "4")
    need = ("md ЗАМОРОЖЕНЫ", "фаза 4", "ВЕРЬ БД", "ИСТОЧНИК ПРАВДЫ БД")
    forbid = ("ВЕРЬ md", "НЕ ЗАПИСАНА")
    case("⑥", "фаза 4 — «md ЗАМОРОЖЕНЫ», верь БД", has_all(out, *need) and has_none(out, *forbid),
         missing(out, need, forbid))

    # ⑦ — непонятное значение
    out = header("active", "5")
    need, forbid = ("ФАЗА НЕ ЗАПИСАНА", "«5» не понято"), ("ЗАМОРОЖЕНЫ", "ВЕРЬ БД", "ВЕРЬ md")
    case("⑦", "ВСТРЕЧНЫЙ: meta.md_phase = «5» — фаза не понята, а не «ЗАМОРОЖЕНЫ»",
         has_all(out, *need) and has_none(out, *forbid), missing(out, need, forbid))

    # ⑧ — правило снято
    out = header("revoked", "4")
    need, forbid = ("ИСТОЧНИК ПРАВДЫ БД", "ВЕРЬ БД"), ("ПЕРЕХОД md", "ЗАМОРОЖЕНЫ", "НЕ ЗАПИСАНА")
    case("⑧", "ВСТРЕЧНЫЙ: снятое правило при фазе 4 — вид без md", has_all(out, *need) and has_none(out, *forbid),
         missing(out, need, forbid))

    def journal():
        return sql("SELECT action, actor_role, diff_md FROM audit_log WHERE target = 'meta.md_phase' "
                   "ORDER BY id")

    def value_now():
        rows = sql("SELECT value FROM meta WHERE key = 'md_phase'")
        return rows[0][0] if rows else None

    # ⑨ — показ и отказы md-phase.py
    if writer is None:
        case("⑨", "md-phase.py: показ и отказы", False, f"md-phase.py рядом с испытуемым нет: {WRITER}")
        case("⑩", "md-phase.py: запись, повтор, холостой прогон, снятие", False, "md-phase.py нет")
    else:
        set_rule("active")
        set_value(None)
        rc_show, out_show = run(writer)
        show_ok = (rc_show == 0 and f"правило {RULE} ... действует" in out_show
                   and "признак meta.md_phase ... не записан" in out_show and "👉 записать" in out_show)
        before = (value_now(), journal())
        rc_noactor, out_noactor = run(writer, "--set", "4")
        rc_bad, out_bad = run(writer, "--set", "7", "--actor", "zzhand")
        set_rule(None)
        rc_norule, out_norule = run(writer, "--set", "4", "--actor", "zzhand")
        set_rule("active")
        after = (value_now(), journal())
        refusals = [(rc_noactor, "рука" in out_noactor), (rc_bad, "«7» не из" in out_bad),
                    (rc_norule, "в базе нет" in out_norule)]
        case("⑨", "md-phase.py: показ называет правило и признак; без руки, фаза «7», без правила — "
             "код 2, база не тронута",
             show_ok and all(rc == 2 and said for rc, said in refusals) and before == after,
             f"показ: код {rc_show}, строки на месте — {show_ok} · отказы (код, слова): {refusals} · "
             f"база до {before} → после {after}")

        # ⑩ — запись. С чистого листа: поломка, прошедшая отказ в ⑨, оставила бы признак
        # и строку журнала, и ⑩ провалился бы на чужой беде — поломки ⑨ судит только ⑨
        set_value(None)
        sql("DELETE FROM audit_log WHERE target = 'meta.md_phase'")
        rc1, out1 = run(writer, "--set", "4", "--actor", "zzhand")
        j1, v1 = journal(), value_now()
        rc2, out2 = run(writer, "--set", "4", "--actor", "zzhand")
        j2 = journal()
        rc3, _out3 = run(writer, "--set", "1", "--actor", "zzhand")
        j3, v3 = journal(), value_now()
        rc4, _out4 = run(writer, "--set", "2", "--actor", "zzhand", "--dry-run")
        j4, v4 = journal(), value_now()
        rc5, _out5 = run(writer, "--clear", "--actor", "zzhand")
        j5, v5 = journal(), value_now()
        want = [("md_phase_set", "ZZHAND", "— → 4"), ("md_phase_set", "ZZHAND", "4 → 1"),
                ("md_phase_clear", "ZZHAND", "1 → —")]
        case("⑩", "md-phase.py: --set пишет признак и журнал; повтор — «уже записано»; холостой — ничего; "
             "--clear снимает",
             (rc1, rc2, rc3, rc4, rc5) == (0, 0, 0, 0, 0) and v1 == "4" and j1 == want[:1]
             and "уже записано" in out2 and j2 == want[:1] and v3 == "1" and j3 == want[:2]
             and v4 == "1" and j4 == want[:2] and v5 is None and j5 == want,
             f"коды {(rc1, rc2, rc3, rc4, rc5)} · признак 4/1/1/нет — {(v1, v3, v4, v5)} · "
             f"журнал: {j5}")

    # ⑪ — подсказка один раз, смена фазы показывает шапку заново
    env_reader = dict(env_base)
    set_rule("active")
    set_value("4")
    _rc, first = run(reader, "--role", ROLE, "--actor", ROLE, env=env_reader)
    _rc, second = run(reader, "--role", ROLE, "--actor", ROLE, env=env_reader)
    set_value("1")
    _rc, third = run(reader, "--role", ROLE, "--actor", ROLE, env=env_reader)
    headers.extend([first, third])
    case("⑪", "второе чтение при той же фазе — строка-ссылка; смена фазы — шапка целиком с «ФАЗА 1»",
         "md ЗАМОРОЖЕНЫ" in first and "md ЗАМОРОЖЕНЫ" not in second and "показана" in second
         and "ФАЗА 1" in third,
         f"первое — шапка {'да' if 'md ЗАМОРОЖЕНЫ' in first else 'нет'} · второе — ссылка "
         f"{'да' if 'показана' in second else 'нет'} · после смены «ФАЗА 1» {'да' if 'ФАЗА 1' in third else 'нет'}")

    # ⑫ — неподставленные места
    left = sorted({p for out in headers for p in PLACEHOLDERS if p in out})
    case("⑫", "ни в одной шапке нет неподставленных мест", not left, f"остались: {left or '—'}")

    # ⑬ — подсказка write-message.py: справка и отказ --md (холостой прогон — база не меняется)
    rc_help, out_help = run(message, "--help")
    rc_md, out_md = run(message, "--role", ROLE, "--body", "приёмка bite-md-phase.py", "--md", "--dry-run")
    help_ok = rc_help == 0 and "единственный источник правды" not in out_help and "md-phase.py" in out_help
    md_ok = rc_md == 0 and "--md ОТКЛОНЁН" in out_md and "фазе 1–2" in out_md and "md-phase.py" in out_md
    case("⑬", "write-message.py: справка без безусловного «единственный источник правды», отказ --md "
         "называет фазу 1–2 и md-phase.py", help_ok and md_ok,
         f"справка: код {rc_help}, верно — {help_ok} · отказ --md: код {rc_md}, верно — {md_ok}")

    # ⑭ ⑮ — показ md-phase.py против шапки read-phoenix.py
    if writer is None:
        case("⑭", "показ md-phase.py берёт строки шапки у read-phoenix.py", False, "md-phase.py нет")
        case("⑮", "ВСТРЕЧНЫЙ: «abc» — показ md-phase.py даёт «👉 записать»", False, "md-phase.py нет")
    else:
        # ⑭ — своя пара копий: метка в шапке не должна задеть случаи выше. Берутся копии
        # из tools — с поломкой, если она вложена
        tools2 = stand / "tools-mark"
        writer2 = mezo_stand.copy_tool(tools / "md-phase.py", tools2)
        reader2 = mezo_stand.copy_tool(tools / "read-phoenix.py", tools2)
        old = "НЕ читать, НЕ писать, НЕ править."
        text = reader2.read_bytes().decode("utf-8")
        marked = text.count(old) == 1
        if marked:
            reader2.write_bytes(text.replace(old, f"{old} {MARK}").encode("utf-8"))
        set_rule("active")
        set_value("4")
        rc14, out14 = run(writer2)
        shown = [ln for ln in out14.splitlines() if MARK in ln]
        case("⑭", "показ md-phase.py берёт строки шапки у read-phoenix.py, а не держит свою копию",
             marked and rc14 == 0 and bool(shown),
             f"метка вписана — {marked} · код {rc14} · строк с меткой {len(shown)}")

        # ⑮ — значение не из 1–4
        set_value("abc")
        rc15, out15 = run(writer)
        # судит строку признака и «👉 записать», а не строку шапки: её судит ⑭
        value_line = "признак meta.md_phase ... abc"
        case("⑮", "ВСТРЕЧНЫЙ: meta.md_phase = «abc» — показ md-phase.py даёт «👉 записать»",
             rc15 == 0 and value_line in out15 and "👉 записать" in out15,
             f"код {rc15} · строка признака {'да' if value_line in out15 else 'нет'} · "
             f"«👉 записать» {'да' if '👉 записать' in out15 else 'нет'}")

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
