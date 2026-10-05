#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: ПРАВА РОЛИ ПОЛЯМИ (слово владельца 2026-08-08 22:33 UTC).

Предмет. Права ролей жили прозой в их памяти — в том самом виде, из которого утром пришлось
выкапывать основания правил (11 правил объявляли решение владельца, не помня когда).
Цена уже заплачена дважды за одну смену: снятие запрета на push жило в ТРЁХ местах, и разовое
разрешение я сам дважды спутал — потрачено оно или нет.

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① право с полным источником записывается           контроль: механизм вообще работает
  ② без «кто разрешил» → ОТКАЗ, в базу НЕ попало                 РАЗЛИЧАЮЩИЙ
  ③ без «где сказано» → ОТКАЗ (источник — не роскошь)            РАЗЛИЧАЮЩИЙ
  ④ РАЗОВОЕ потрачено → уходит из живых, но ОСТАЁТСЯ в истории   РАЗЛИЧАЮЩИЙ
  ⑤ потратить дважды НЕЛЬЗЯ                                      РАЗЛИЧАЮЩИЙ
  ⑥ СТОЯЧЕЕ потратить нельзя вовсе                               РАЗЛИЧАЮЩИЙ
  ⑦ отзыв БЕЗ причины отвергается: отзыв без причины — пропажа   РАЗЛИЧАЮЩИЙ
  ⑧ отозванное уходит из живых, но НЕ удаляется                  РАЗЛИЧАЮЩИЙ
  ⑨ ДУБЛЬ живого права не заводится молча                        РАЗЛИЧАЮЩИЙ
  ⑩ пустой список говорит «поля никто не заполнял», а не «прав нет»

⚡ ДОБАВЛЕНО 2026-08-09 — ФОРМА «СПРОСИТЬ ПРО СЕБЯ». До этого дня приёмка звала `list` БЕЗ
имени роли, а промпт запуска роли и справка самого механизма зовут `list --role <РОЛЬ>`.
Эта форма падала ВСЕГДА (параметр готовился и терялся), и приёмка была зелёной, не увидев
ничего: она мерила не то место.
  ⑪ `list --role X` вообще отвечает                    контроль: форма из промпта запуска
  ⑫ фильтр не показывает ЧУЖИХ прав                              РАЗЛИЧАЮЩИЙ
  ⑬ ОБЩЕЕ право (role=ALL) ВИДНО спросившему про себя            РАЗЛИЧАЮЩИЙ
     иначе роль слышит «тебе ничего не разрешено» при живом стоячем разрешении на всех
  ⑭ «у ЭТОЙ роли нет» ≠ «полей никто не заполнял»                РАЗЛИЧАЮЩИЙ
     контрольная пара к ⑩: тот же вопрос к ПУСТОЙ базе обязан дать ДРУГОЙ ответ

⚡ ДОБАВЛЕНО 2026-10-05 — КООРДИНАТОР КОНТУРА ИЗ ДАННЫХ (карточка #677, этап Э3, задание rc;
решение владельца В3 а′, чат COORD 2026-10-05 10:53 UTC: «координатор остаётся пометкой в
таблице ролей, плюс ОДНА команда, ставящая пометку»). До этого дня имя координатора было
вписано в код отзыва, а пометка менялась только рукой по базе.
  Место 1 — отзыв чужого права (revoke):
  ⑲ координатор берётся из ДАННЫХ: роль с пометкой отзывает чужое право, роль с ТЕМ ЖЕ именем,
     что прежде было вписано в код, но без пометки — нет                       РАЗЛИЧАЮЩИЙ
  ⑳ координатор НЕ определён (никто · двое · таблицу ролей не прочитать) — чужое право не
     отзывается никем, отказ называет найденных                                РАЗЛИЧАЮЩИЙ
  Место 2 — подкоманда `coordinator`:
  ㉑ показ пометки: один · никто · двое — три РАЗНЫХ ответа словами            РАЗЛИЧАЮЩИЙ
  ㉒ --set без --apply ничего не пишет (таблицы до и после равны)              РАЗЛИЧАЮЩИЙ
  ㉓ --set --apply ставит пометку, прежний текст причины остаётся после неё    РАЗЛИЧАЮЩИЙ
  ㉔ роли нет в таблице ролей — отказ, ничего не записано                      РАЗЛИЧАЮЩИЙ
  ㉕ роль не живая — отказ своими словами, ничего не записано                  РАЗЛИЧАЮЩИЙ
  ㉖ перенос: прежний координатор теряет пометку, а ловушка корня не срабатывает —
     после переноса поиск находит ровно одну роль, и это назначенная           РАЗЛИЧАЮЩИЙ
  ㉗ в журнале изменений (audit_log) появилась запись о назначении             РАЗЛИЧАЮЩИЙ
  ㉘ запись, после которой поиск не вернул бы назначенную роль, откатывается   РАЗЛИЧАЮЩИЙ
  ㉙ без --actor или без слова владельца — отказ, ничего не записано           РАЗЛИЧАЮЩИЙ
  ㉚ справка подкоманды по-русски и с примером вызова                          РАЗЛИЧАЮЩИЙ

🎯 НАРОЧНЫЕ ПОЛОМКИ (--break <имя>). Словарь BREAKS — что именно сломать в КОПИИ инструмента;
BREAK_FAILS — какие случаи каждая обязана провалить, записано ДО прогона. Прогон с --break
печатает ожидание до случаев и сверяет его с фактом после. Копия лежит на стенде вместе с
соседями инструмента; живой файл не трогается.
   literal-coord    вернуть литерал: отзывает роль с вписанным именем, а не названная в данных
   none-passes      координатор не определён — и чужое право всё равно отзывается
   show-literal     показ называет вписанное имя вместо найденного в данных
   dryrun-writes    без --apply команда всё равно пишет
   drops-old-text   прежний текст причины назначенной роли затирается
   no-exist-check   нет проверки «роль есть в таблице ролей»
   no-alive-check   нет проверки «роль живая»
   old-keeps-root   прежнему координатору пишется текст с корнем «координатор» (ловушка)
   no-audit         запись в журнал изменений не делается
   no-postcheck     нет проверки после записи (случай ㉘ идёт по копии с нарочным сбоем:
                    назначенная роль закрывается внутри той же транзакции)
   no-word-check    нет требования --actor и слова владельца
   help-no-example  в справке нет примера вызова

⛔ Живой базы не касается: своя песочница.
"""
import argparse
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402  — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале
import mezo_paths  # noqa: E402 — итог сверяется ТОЙ ЖЕ общей функцией поиска, что и в инструменте

# ⚡ 2026-08-09 (карточка #148): путь больше не вписан в приёмку. Прежде он вёл в живой контур
# всегда, и прогон «по шаблону» на деле испытывал оригинал — а описание таблицы приёмка
# и вовсе брала из живого молча, потому что в шаблоне каталога шагов схемы не было.
CLI = str(mezo_target.script("role-rights.py"))
DDL = mezo_target.migration("20260808-role-rights.py").read_text(encoding="utf-8")
# Таблица ролей — из шага схемы (там она названа roles_new на время переноса данных).
ROLES_STEP = mezo_target.migration("20260810-role-lifecycle.py").read_text(encoding="utf-8")
# Журнал изменений: шага схемы с его описанием в каталоге нет, форма — как у живой базы.
AUDIT_DDL = """CREATE TABLE audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now')),
    actor_role  TEXT NOT NULL,
    action      TEXT NOT NULL,
    target      TEXT NOT NULL,
    diff_md     TEXT
)"""
CASES = DIFFER = 0
RUN_IDS = []      # номера прогнанных случаев по порядку (первое слово заголовка)
FAILED = []       # номера провалившихся — для сверки с заранее названным ожиданием поломки

# Роли песочницы: (роль, состояние, обычная причина БЕЗ корня «координатор»).
ROLES_PLAIN = [
    ("COORD", "alive", "обычная роль пробы без пометки"),
    ("COORD-A", "alive", "запасная роль пробы А"),
    ("COORD-B", "alive", "запасная роль пробы Б"),
    ("ING", "alive", "в живом реестре"),
    ("STUD", "alive", "в живом реестре"),
    ("PROTO", "alive", "заведён по живому слову владельца"),
    ("OLDROLE", "closed", "роль закрыта пробой"),
]
PROBE_MARK = "координатор контура (проба приёмки)"
WORD = "слово владельца: назначить пробную роль, 2026-10-05 12:00 UTC, чат PROTO"


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    RUN_IDS.append(title.split()[0])
    if not ok:
        FAILED.append(title.split()[0])
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def refuse_to_measure(message):
    """Третий исход: приёмка не смогла начаться. Это НЕ «сломано» и НЕ «в порядке»."""
    print(f"⛔ НЕ ПРОВЕРЕНО: {message}")
    sys.exit(2)


def roles_ddl():
    try:
        return ROLES_STEP.split('NEW_TABLE = """')[1].split('"""')[0].replace("roles_new", "roles")
    except IndexError:
        refuse_to_measure("в шаге схемы 20260810-role-lifecycle.py не нашлось описания таблицы "
                          "ролей (NEW_TABLE) — приёмку надо поправить под новую форму шага")


def mark_coordinators(db, names):
    """Кто в песочнице помечен координатором: РОВНО названные, состояние ставится целиком.

    Сверяет себя той же общей функцией поиска, что и инструмент: подсадка, давшая другое
    число помеченных, — отказ мерить (иначе случай судил бы чужую обстановку).
    """
    con = sqlite3.connect(db)
    for role, _state, plain in ROLES_PLAIN:
        reason = f"{PROBE_MARK}; {plain}" if role in names else plain
        con.execute("UPDATE roles SET lifecycle_reason = ? WHERE role = ?", (reason, role))
    con.commit()
    con.close()
    found = mezo_paths.find_coordinator(db).found
    if found != sorted(names):
        refuse_to_measure(f"подсадка помеченных координаторов дала {found}, ждали {sorted(names)}")


def build(coordinators=("COORD",), with_roles=True):
    db = os.path.join(mezo_stand.new("bite-rights-"), "s.db")
    con = sqlite3.connect(db)
    ddl = DDL.split('DDL = """')[1].split('"""')[0]
    con.executescript(ddl)
    # ⚡ AIA-B (карточка B, 2026-09-13): revoke пишет revoked_by — колонка добавлена шагом
    # 20260913-role-rights-revoked-by.py ПОВЕРХ базового DDL 009-role-rights, тем же приёмом,
    # каким сама живая база получает шаг схемы отдельным ходом.
    con.execute("ALTER TABLE role_rights ADD COLUMN revoked_by TEXT")
    if with_roles:
        con.executescript(roles_ddl())
        con.execute(AUDIT_DDL)
        for role, state, plain in ROLES_PLAIN:
            con.execute("INSERT INTO roles (role, lifecycle, lifecycle_reason) VALUES (?,?,?)",
                        (role, state, plain))
    con.commit()
    con.close()
    if with_roles:
        mark_coordinators(db, list(coordinators))
    return db


def run(db, *args, tool=None):
    r = subprocess.run([sys.executable, tool or CLI, "--db", db, *args],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def rows(db, live=True):
    con = sqlite3.connect(db)
    n = con.execute(f"SELECT COUNT(*) FROM {'role_rights_live' if live else 'role_rights'}"
                    ).fetchone()[0]
    con.close()
    return n


def right_field(db, right_id, column):
    con = sqlite3.connect(db)
    value = con.execute(f"SELECT {column} FROM role_rights WHERE id=?", (right_id,)).fetchone()[0]
    con.close()
    return value


def add_right(db, role, key):
    """Завести стоячее право и вернуть его номер (по базе, а не разбором печати)."""
    run(db, "grant", "--role", role, "--right", key, "--kind", "standing", "--scope", "проба", *FULL)
    con = sqlite3.connect(db)
    right_id = con.execute("SELECT MAX(id) FROM role_rights").fetchone()[0]
    con.close()
    return right_id


def reason_of(db, role):
    con = sqlite3.connect(db)
    reason = con.execute("SELECT lifecycle_reason FROM roles WHERE role=?", (role,)).fetchone()[0]
    con.close()
    return reason


def snapshot(db):
    """Всё, что подкоманда могла бы записать: таблица ролей, журнал изменений и права."""
    con = sqlite3.connect(db)
    try:
        return (con.execute("SELECT role, lifecycle, lifecycle_reason FROM roles "
                            "ORDER BY role").fetchall(),
                con.execute("SELECT id, actor_role, action, target, diff_md FROM audit_log "
                            "ORDER BY id").fetchall(),
                con.execute("SELECT * FROM role_rights ORDER BY id").fetchall())
    finally:
        con.close()


FULL = ["--authorized-by", "owner", "--granted-at", "2026-08-08 15:56 UTC",
        "--source-ref", "чат PROTO 2026-08-08 15:56 UTC"]

# ═══ НАРОЧНЫЕ ПОЛОМКИ ═══════════════════════════════════════════════════════════
# Каждая — список пар (было → стало) для КОПИИ инструмента; «было» обязано встретиться в
# копии РОВНО ОДИН раз, иначе прогон отказывает кодом 2 «поломка не легла» (поправь приёмку,
# а не инструмент). Вторая и третья пары — только там, где одной строки мало.
BREAKS = {
    "literal-coord": (
        [('        if by != coordinator.name:\n', '        if by != "COORD":\n')],
        "отзывает роль с вписанным именем, а не та, что названа координатором в данных"),
    "none-passes": (
        [('        if coordinator.name is None:\n', '        if False:\n'),
         ('        if by != coordinator.name:\n',
          '        if coordinator.name is not None and by != coordinator.name:\n')],
        "координатор не определён — и чужое право всё равно отзывается"),
    "show-literal": (
        [('        print(f"Координатор контура — {lookup.name}")\n',
          '        print(f"Координатор контура — COORD")\n')],
        "показ называет вписанное имя вместо найденного в данных"),
    "dryrun-writes": (
        [('    if not a.apply:\n', '    if False:\n')],
        "без --apply команда всё равно пишет"),
    "drops-old-text": (
        [("        new_reason = f\"{mark}; {plan['old_reason']}\"\n", "        new_reason = mark\n")],
        "прежний текст причины назначенной роли затирается"),
    "no-exist-check": (
        [('    if row is None:\n', '    if False:\n')],
        "нет проверки «роль есть в таблице ролей»"),
    "no-alive-check": (
        [('    if row[0] != "alive":\n', '    if False:\n')],
        "нет проверки «роль живая»"),
    "old-keeps-root": (
        [('FORMER_MARK = "прежняя ведущая роль контура; пометка снята {hour} UTC"\n',
          'FORMER_MARK = "бывший координатор контура; пометка снята {hour} UTC"\n')],
        "прежнему координатору пишется текст с корнем «координатор» — ловушка"),
    "no-audit": (
        [('        write_coordinator_audit(conn, actor, role, diff)\n', '        pass\n')],
        "запись в журнал изменений не делается"),
    "no-postcheck": (
        [('        if after.name != role:\n', '        if False:\n')],
        "нет проверки после записи (случай ㉘ идёт по копии с нарочным сбоем)"),
    "no-word-check": (
        [('    if not actor or not word:\n', '    if False:\n')],
        "нет требования --actor и слова владельца"),
    "help-no-example": (
        [('Пример вызова:\n', 'Example:\n')],
        "в справке нет примера вызова"),
}
# 📋 СПИСОК ПРОВАЛОВ КАЖДОЙ ПОЛОМКИ — ЗАПИСАН ДО ПРОГОНА. Прогон с --break сверяет с ним факт
# и говорит вслух, совпало ли; строка ИТОГ считает по нему, какие случаи покрыты поломкой.
BREAK_FAILS = {
    "literal-coord": ["⑲"],
    "none-passes": ["⑳"],
    "show-literal": ["㉑"],
    "dryrun-writes": ["㉒"],
    "drops-old-text": ["㉓"],
    "no-exist-check": ["㉔"],
    "no-alive-check": ["㉕"],
    "old-keeps-root": ["㉖"],
    "no-audit": ["㉗"],
    "no-postcheck": ["㉘"],
    "no-word-check": ["㉙"],
    "help-no-example": ["㉚"],
}
# Нарочный сбой для случая ㉘: назначенная роль закрывается ВНУТРИ той же транзакции, прямо
# перед проверкой после записи. Инструмент с проверкой обязан откатить всё и отказать;
# без неё (поломка no-postcheck) запись ушла бы в базу.
FAULT_ANCHOR = "        after = mezo_paths.find_coordinator(conn)\n"
FAULT_PAIR = (FAULT_ANCHOR,
              "        conn.execute(\"UPDATE roles SET lifecycle = 'closed' WHERE role = ?\", "
              "(role,))\n" + FAULT_ANCHOR)


def tool_copy(base_tool, pairs, label):
    """Копия инструмента на стенде (вместе с соседями) с применёнными парами «было → стало».

    Не легла пара — отказ мерить: поломка, не попавшая в код, не доказывает ничего."""
    folder = mezo_stand.new(f"bite-rights-{label}-")
    tool = mezo_stand.copy_tool(base_tool, folder)
    text = tool.read_text(encoding="utf-8")
    for before, after in pairs:
        if text.count(before) != 1:
            refuse_to_measure(f"поломка «{label}» НЕ ЛЕГЛА — искомое место встречается "
                              f"{text.count(before)} раз (нужен ровно один): {before.strip()[:70]}")
        text = text.replace(before, after)
    # байтами: запись текстом на Windows сменила бы окончания строк копии
    tool.write_bytes(text.encode("utf-8"))
    return str(tool)


def main() -> int:
    global CLI
    ap = argparse.ArgumentParser(description="приёмка: права роли полями")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS),
                    help="нарочная поломка: прогнать все случаи по ПОРЧЕНОЙ копии инструмента")
    a = ap.parse_args()
    break_name = a.break_name
    if break_name:
        pairs, expectation = BREAKS[break_name]
        CLI = tool_copy(Path(CLI), pairs, break_name)
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{break_name}»: {expectation}")
        print(f"   ждём провала РОВНО: {' '.join(BREAK_FAILS[break_name])} "
              f"(записано в BREAK_FAILS до прогона)\n")

    ok = True
    db = build()

    out, code = run(db, "list")
    ok &= case("⑩ пустой список говорит «поля никто не заполнял», а не «прав нет»",
               "ПУСТО" in out and "НЕ «прав нет»" in out,
               "молчание тут прочлось бы как «роли ничего не разрешено»")

    out, code = run(db, "grant", "--role", "PROTO", "--right", "push",
                    "--kind", "standing", "--scope", "gordipack", *FULL)
    ok &= case("① право с полным источником записано (контроль: механизм работает)",
               code == 0 and rows(db) == 1, f"код {code} · живых прав {rows(db)}")

    out, code = run(db, "grant", "--role", "CORE", "--right", "migrate", "--kind", "once",
                    "--granted-at", "2026-08-08", "--source-ref", "чат")
    ok &= case("② без «кто разрешил» — ОТКАЗ, в базу НЕ попало",
               code != 0 and rows(db, live=False) == 1 and "НЕ ЗАПИСАНО" in out,
               f"код {code} · записей всего {rows(db, live=False)} — новых нет", differ=True)

    out, code = run(db, "grant", "--role", "CORE", "--right", "migrate", "--kind", "once",
                    "--authorized-by", "owner", "--granted-at", "2026-08-08")
    ok &= case("③ без «где сказано» — ОТКАЗ: источник не роскошь",
               code != 0 and rows(db, live=False) == 1,
               "право без источника нельзя ни проверить, ни отозвать безопасно", differ=True)

    run(db, "grant", "--role", "CORE", "--right", "migrate", "--kind", "once", *FULL)
    live_before, all_before = rows(db), rows(db, live=False)
    out, code = run(db, "spend", "--id", "2", "--on", "шаг 008")
    ok &= case("④ РАЗОВОЕ потрачено — ушло из живых, но ОСТАЛОСЬ в истории",
               code == 0 and rows(db) == live_before - 1 and rows(db, live=False) == all_before,
               f"живых {live_before} → {rows(db)} · всего {all_before} → "
               f"{rows(db, live=False)}", differ=True)

    out, code = run(db, "spend", "--id", "2")
    ok &= case("⑤ потратить ДВАЖДЫ нельзя",
               code != 0 and "УЖЕ потрачено" in out,
               "иначе разовое право становится стоячим явочным порядком", differ=True)

    out, code = run(db, "spend", "--id", "1")
    ok &= case("⑥ СТОЯЧЕЕ потратить нельзя вовсе",
               code != 0 and "СТОЯЧЕЕ" in out,
               "тратятся только разовые: у стоячего нет расхода по определению", differ=True)

    out, code = run(db, "revoke", "--id", "1")
    ok &= case("⑦ отзыв БЕЗ причины отвергнут",
               code != 0 and "пропажа" in out,
               "отозванное право спрашивают именно тогда, когда что-то пошло не так", differ=True)

    live_before, all_before = rows(db), rows(db, live=False)
    # ⚡ AIA-B: revoke теперь требует --by (владелец записи #1 — PROTO, отзывает сам себя).
    out, code = run(db, "revoke", "--id", "1", "--why", "слово владельца отозвано 09.08",
                    "--by", "PROTO")
    ok &= case("⑧ отозванное ушло из живых, но НЕ удалено",
               code == 0 and rows(db) == live_before - 1 and rows(db, live=False) == all_before,
               f"живых {live_before} → {rows(db)} · всего {all_before} → {rows(db, live=False)}",
               differ=True)

    # ═══ AIA-B (карточка B, слово владельца 2026-09-13 10:07 UTC): revoke — рука ОБЯЗАТЕЛЬНА,
    # отзывает роль-владелец либо координатор ЯВНО (--foreign). Найдено контуром AIA:
    # ДО правки отозвать чужое право могла ЛЮБАЯ роль, назвав чужой --id.
    # ⚡ 2026-10-05 (карточка #677, Э3): координатор песочницы — роль С ПОМЕТКОЙ в таблице
    # ролей (build() помечает COORD), а не роль с вписанным в код именем.
    run(db, "grant", "--role", "ING", "--right", "deploy", "--kind", "standing",
        "--scope", "stage", *FULL)
    row_id = None
    out_list, _ = run(db, "list", "--all")
    for line in out_list.splitlines():
        if "ING" in line and "deploy" in line:
            row_id = int(line.split("#")[1].split()[0])
            break

    live_before_b = rows(db)
    out, code = run(db, "revoke", "--id", str(row_id), "--why", "проба AIA-B")
    ok &= case("⑮ revoke БЕЗ --by — ОТКАЗ той же фразой, что у amend",
               code != 0 and "нужен --by" in out and rows(db) == live_before_b,
               "рука обязательна: отзыв без неё неотличим от того, что запись всегда "
               "была такой (право за ING осталось живым)", differ=True)

    out, code = run(db, "revoke", "--id", str(row_id), "--why", "проба AIA-B", "--by", "STUD")
    ok &= case("⑯ ЧУЖАЯ роль (не владелец, не координатор) не отзывает — ОТКАЗ",
               code != 0 and "принадлежит роли ING" in out and rows(db) == live_before_b,
               "владелец записи — ING, отозвать просит STUD, не координатор", differ=True)

    out, code = run(db, "revoke", "--id", str(row_id), "--why", "проба AIA-B", "--by", "COORD")
    ok &= case("⑰ координатор БЕЗ --foreign не отзывает чужое право молча",
               code != 0 and "--foreign" in out and "не координатору" in out
               and rows(db) == live_before_b,
               "координатор без явного --foreign не гасит чужое право по факту роли",
               differ=True)

    out, code = run(db, "revoke", "--id", str(row_id), "--why", "проба AIA-B", "--by", "COORD",
                    "--foreign")
    # revoked_by в list --all не печатается — сверяем полем напрямую
    con_chk = sqlite3.connect(db)
    revoked_by_val = con_chk.execute("SELECT revoked_by FROM role_rights WHERE id=?",
                                     (row_id,)).fetchone()[0]
    con_chk.close()
    ok &= case("⑱ координатор С --foreign отзывает ЧУЖОЕ право, revoked_by записан",
               code == 0 and revoked_by_val == "COORD",
               f"код {code} · revoked_by = {revoked_by_val!r}", differ=True)

    run(db, "grant", "--role", "TAXO", "--right", "seed", "--kind", "standing",
        "--scope", "phd1", *FULL)
    out, code = run(db, "grant", "--role", "TAXO", "--right", "seed", "--kind", "standing",
                    "--scope", "phd1", *FULL)
    ok &= case("⑨ ДУБЛЬ живого права не заводится молча",
               code != 0 and "УЖЕ ЕСТЬ" in out,
               "два одинаковых права раздваивают ответ на вопрос «а можно ли»", differ=True)

    # ── ФОРМА «СПРОСИТЬ ПРО СЕБЯ» — ровно та, что стоит в промпте запуска роли ──────────
    run(db, "grant", "--role", "ALL", "--right", "push-common", "--kind", "standing",
        "--scope", "любой репозиторий", *FULL)
    run(db, "grant", "--role", "CORE", "--right", "service-start", "--kind", "standing",
        "--scope", ":5300", *FULL)

    out, code = run(db, "list", "--role", "CORE")
    ok &= case("⑪ `list --role CORE` ОТВЕЧАЕТ (контроль: форма из промпта запуска работает)",
               code == 0 and "service-start" in out,
               f"код {code} · своё право роль видит")

    ok &= case("⑫ фильтр по роли НЕ показывает чужого",
               code == 0 and "seed" not in out,
               "право TAXO «seed» живо в базе, но в ответе роли CORE его быть не должно",
               differ=True)

    ok &= case("⑬ ОБЩЕЕ право (role=ALL) ВИДНО спросившему про себя",
               code == 0 and "push-common" in out,
               "иначе роль слышит «мне ничего не разрешено» при живом разрешении на ВСЕХ "
               "и отказывается от разрешённого", differ=True)

    # ⚠️ ТРЕТЬЯ база — БЕЗ общего права. В базе `db` общее право ЕСТЬ, поэтому спросивший
    # про себя никогда не попадёт в ветку «пусто», и случай зеленел бы, ничего не проверив.
    # Так и было при первом заходе 2026-08-09: нарочная поломка это и вскрыла.
    db3 = build()
    run(db3, "grant", "--role", "TAXO", "--right", "seed", "--kind", "standing",
        "--scope", "phd1", *FULL)
    out_none, code_none = run(db3, "list", "--role", "ING")
    out_empty, _ = run(build(), "list", "--role", "ING")
    ok &= case("⑭ «у ЭТОЙ роли нет» ≠ «полей никто не заполнял» (контрольная пара к ⑩)",
               code_none == 0 and "НЕ ПРО СВОД" not in out_none
               and "НЕТ НИ ОДНОГО" in out_none and "никто не заполнял" not in out_none
               and "ПУСТО" in out_empty and "НЕ «прав нет»" in out_empty,
               "у роли ING прав нет, но у TAXO есть ⇒ ответ про ЕЁ набор, а не про свод; "
               "в пустой базе тот же вопрос обязан дать ДРУГОЙ текст", differ=True)

    # ═══ КАРТОЧКА #677, ЭТАП Э3 — КООРДИНАТОР КОНТУРА ИЗ ДАННЫХ ═══════════════════════
    # ── Место 1: отзыв чужого права ────────────────────────────────────────────────
    # ⑲ Координатор песочницы — COORD-A. Роль COORD носит то самое имя, что прежде было
    # вписано в код, но пометки у неё НЕТ: по данным она обычная роль и чужое не отзывает.
    # Порядок важен: отказ идёт первым, иначе право уже будет отозвано и отказ нечем мерить.
    db_a = build(["COORD-A"])
    right_a = add_right(db_a, "ING", "deploy-a")
    live_a = rows(db_a)
    out_plain, code_plain = run(db_a, "revoke", "--id", str(right_a), "--why", "проба Э3",
                                "--by", "COORD", "--foreign")
    live_after_plain = rows(db_a)
    plain_refused = (code_plain != 0 and "принадлежит роли ING" in out_plain
                     and live_after_plain == live_a)
    out_mark, code_mark = run(db_a, "revoke", "--id", str(right_a), "--why", "проба Э3",
                              "--by", "COORD-A", "--foreign")
    by_val = right_field(db_a, right_a, "revoked_by")
    ok &= case("⑲ координатор берётся из ДАННЫХ: COORD-A (с пометкой) отзывает чужое право, "
               "COORD (без пометки) — нет",
               plain_refused and code_mark == 0 and by_val == "COORD-A",
               f"COORD без пометки: код {code_plain}, живых прав {live_a} → {live_after_plain}; "
               f"COORD-A с пометкой: код {code_mark}, revoked_by = {by_val!r}",
               differ=True)

    # ⑳ Координатор не определён — три разные причины, и ни при одной чужое право не
    # отзывается. «Двое» берёт отзывающим одного из них самих: «первый из найденных» не
    # годится в координаторы, пока владелец не назвал одного.
    db_n = build([])
    right_n = add_right(db_n, "ING", "deploy-n")
    out_n, code_n = run(db_n, "revoke", "--id", str(right_n), "--why", "проба Э3",
                        "--by", "COORD", "--foreign")
    part_none = (code_n != 0 and "не определён" in out_n and "ни у одной живой роли" in out_n
                 and right_field(db_n, right_n, "revoked_at") is None)
    db_t = build(["COORD-A", "COORD-B"])
    right_t = add_right(db_t, "ING", "deploy-t")
    out_t, code_t = run(db_t, "revoke", "--id", str(right_t), "--why", "проба Э3",
                        "--by", "COORD-A", "--foreign")
    part_two = (code_t != 0 and "не определён" in out_t and "COORD-A, COORD-B" in out_t
                and right_field(db_t, right_t, "revoked_at") is None)
    db_e = build([], with_roles=False)
    right_e = add_right(db_e, "ING", "deploy-e")
    out_e, code_e = run(db_e, "revoke", "--id", str(right_e), "--why", "проба Э3",
                        "--by", "COORD", "--foreign")
    part_error = (code_e != 0 and "не определён" in out_e and "не удалось" in out_e
                  and "OperationalError" in out_e
                  and right_field(db_e, right_e, "revoked_at") is None)
    ok &= case("⑳ координатор НЕ определён (никто · двое · таблицу ролей не прочитать) — чужое "
               "право не отзывается, отказ называет найденных",
               part_none and part_two and part_error,
               f"никто не помечен: {'отказ, право живо' if part_none else 'НЕ ТАК'} · "
               f"помечены двое: {'отказ с обоими именами' if part_two else 'НЕ ТАК'} · "
               f"таблицы ролей нет: {'отказ с причиной чтения' if part_error else 'НЕ ТАК'}",
               differ=True)

    # ── Место 2: подкоманда coordinator ────────────────────────────────────────────
    # ㉑ Показ: один · никто · двое — три ответа, различимых словами.
    db_1 = build(["COORD-A"])
    out_one, code_one = run(db_1, "coordinator")
    out_zero, code_zero = run(build([]), "coordinator")
    out_dbl, code_dbl = run(build(["COORD-A", "COORD-B"]), "coordinator")
    show_one = (code_one == 0 and "Координатор контура — COORD-A" in out_one
                and "COORD-B" not in out_one and "НЕ НАЗНАЧЕН" not in out_one)
    show_zero = (code_zero == 0 and "НЕ НАЗНАЧЕН" in out_zero and "— COORD" not in out_zero)
    show_two = (code_dbl == 0 and "НЕ ОПРЕДЕЛЁН" in out_dbl and "COORD-A, COORD-B" in out_dbl)
    ok &= case("㉑ показ пометки: один · никто · двое — три РАЗНЫХ ответа словами",
               show_one and show_zero and show_two,
               f"один: {'назван по имени' if show_one else 'НЕ ТАК'} · "
               f"никто: {'«не назначен»' if show_zero else 'НЕ ТАК'} · "
               f"двое: {'«не определён» с обоими именами' if show_two else 'НЕ ТАК'}",
               differ=True)

    # ㉒ --set без --apply — только показ. Сравниваем ВСЁ, что подкоманда могла записать.
    db_d = build(["COORD-A"])
    snap_before = snapshot(db_d)
    out_d, code_d = run(db_d, "coordinator", "--set", "COORD-B", "--actor", "PROTO",
                        "--word", WORD)
    snap_after = snapshot(db_d)
    ok &= case("㉒ --set без --apply ничего не пишет: таблицы до и после равны, а печать говорит, "
               "что изменится и что подлинность слова не проверяется",
               code_d == 0 and snap_before == snap_after and "ничего не записано" in out_d
               and "COORD-B" in out_d and "COORD-A" in out_d
               and "подлинность слова владельца НЕ проверяет" in out_d,
               f"код {code_d} · таблицы {'равны' if snap_before == snap_after else 'РАЗЛИЧАЮТСЯ'}"
               f" · в печати «ничего не записано»: {'ничего не записано' in out_d}",
               differ=True)

    # ㉓ --set --apply там, где координатора нет: назначенная роль получает пометку, а её
    # прежний текст причины остаётся ПОСЛЕ пометки. Прежнего координатора здесь нет нарочно —
    # перенос судит ㉖: эти два случая падают от разных поломок.
    db_s = build([])
    plain_b = reason_of(db_s, "COORD-B")
    snap_s = snapshot(db_s)
    out_s, code_s = run(db_s, "coordinator", "--set", "COORD-B", "--actor", "proto",
                        "--word", WORD, "--apply")
    new_b = reason_of(db_s, "COORD-B")
    lookup_s = mezo_paths.find_coordinator(db_s)
    ok &= case("㉓ --set --apply ставит пометку: «координатор контура (назначен … рукой …)», "
               "прежний текст причины остаётся после неё",
               code_s == 0 and new_b.startswith("координатор контура (назначен ")
               and "UTC рукой PROTO)" in new_b and new_b.endswith(f"; {plain_b}")
               and lookup_s.name == "COORD-B",
               f"код {code_s} · причина стала «{new_b}» · поиск вернул {lookup_s.name!r}",
               differ=True)

    # ㉔ Роли нет в таблице ролей: отказ СВОИМИ словами и ни одной записанной строки.
    db_g = build(["COORD-A"])
    snap_g = snapshot(db_g)
    out_g, code_g = run(db_g, "coordinator", "--set", "GHOST", "--actor", "PROTO",
                        "--word", WORD, "--apply")
    ok &= case("㉔ роли нет в таблице ролей — отказ, ничего не записано",
               code_g != 0 and "роли GHOST в таблице ролей нет" in out_g
               and snapshot(db_g) == snap_g,
               f"код {code_g} · таблицы {'не тронуты' if snapshot(db_g) == snap_g else 'ТРОНУТЫ'}"
               f" · слова отказа: {'свои' if 'роли GHOST в таблице ролей нет' in out_g else 'чужие'}",
               differ=True)

    # ㉕ Роль закрыта: отказ СВОИМИ словами. Мало «ничего не записано» — проверка после записи
    # тоже отвергла бы закрытую роль; случай обязан краснеть именно без проверки «живая».
    db_o = build(["COORD-A"])
    snap_o = snapshot(db_o)
    out_o, code_o = run(db_o, "coordinator", "--set", "OLDROLE", "--actor", "PROTO",
                        "--word", WORD, "--apply")
    ok &= case("㉕ роль не живая — отказ своими словами, ничего не записано",
               code_o != 0 and "роль OLDROLE не живая" in out_o and snapshot(db_o) == snap_o,
               f"код {code_o} · слова отказа: "
               f"{'свои' if 'роль OLDROLE не живая' in out_o else 'чужие'} · таблицы "
               f"{'не тронуты' if snapshot(db_o) == snap_o else 'ТРОНУТЫ'}", differ=True)

    # ㉖ ПЕРЕНОС И ЛОВУШКА КОРНЯ. COORD-A — координатор; назначаем COORD-B. После переноса у
    # прежнего пометка снята (его причина изменилась и корня «координатор» в ней нет), а поиск
    # находит РОВНО одну роль — назначенную. Мало «найдена одна»: при отказе переноса одна
    # осталась бы и без него — прежняя; поэтому сверяется имя, а не число.
    db_x = build(["COORD-A"])
    old_a = reason_of(db_x, "COORD-A")
    out_x, code_x = run(db_x, "coordinator", "--set", "COORD-B", "--actor", "PROTO",
                        "--word", WORD, "--apply")
    lookup_x = mezo_paths.find_coordinator(db_x)
    new_a = reason_of(db_x, "COORD-A")
    ok &= case("㉖ перенос: прежний координатор теряет пометку, ловушка корня не срабатывает — "
               "после переноса поиск находит ровно одну роль, и это назначенная",
               code_x == 0 and lookup_x.name == "COORD-B" and lookup_x.found == ["COORD-B"]
               and new_a != old_a and mezo_paths.COORDINATOR_WORD not in new_a.casefold(),
               f"код {code_x} · найдены {lookup_x.found} · причина прежнего «{new_a}»",
               differ=True)

    # ㉗ След назначения — в журнале изменений (audit_log), по базе ㉓: кто, что, чьё слово.
    con_au = sqlite3.connect(db_s)
    audit_rows = con_au.execute("SELECT actor_role, action, target, diff_md FROM audit_log"
                                ).fetchall()
    con_au.close()
    audit_ok = (len(audit_rows) == 1 and audit_rows[0][0] == "PROTO"
                and audit_rows[0][1] == "set_coordinator" and audit_rows[0][2] == "COORD-B"
                and WORD in audit_rows[0][3] and plain_b in audit_rows[0][3])
    ok &= case("㉗ в журнале изменений (audit_log) появилась запись о назначении: кто · кого · "
               "слово владельца · что было",
               audit_ok,
               f"записей {len(audit_rows)} · "
               f"{(audit_rows[0][0], audit_rows[0][1], audit_rows[0][2]) if audit_rows else '—'}",
               differ=True)

    # ㉘ ОТКАТ. Копия инструмента с нарочным сбоем: назначенная роль закрывается внутри той же
    # транзакции. Поиск после записи не вернёт её — инструмент обязан откатить ВСЁ (таблица
    # ролей, журнал, права равны прежним) и отказать. Копия строится от ИСПЫТУЕМОГО варианта,
    # поэтому поломка no-postcheck доезжает и до неё.
    fault_tool = tool_copy(Path(CLI), [FAULT_PAIR], "fault")
    db_r = build([])
    snap_r = snapshot(db_r)
    out_r, code_r = run(db_r, "coordinator", "--set", "COORD-B", "--actor", "PROTO",
                        "--word", WORD, "--apply", tool=fault_tool)
    ok &= case("㉘ запись, после которой поиск не вернул бы назначенную роль, откатывается — "
               "и таблицы равны прежним",
               code_r != 0 and "ПОМЕТКА НЕ ПОСТАВЛЕНА" in out_r and "откатано" in out_r
               and snapshot(db_r) == snap_r,
               f"код {code_r} · таблицы {'равны прежним' if snapshot(db_r) == snap_r else 'ИЗМЕНЕНЫ'}"
               f" · роль COORD-B после опыта: "
               f"{'как была' if snapshot(db_r) == snap_r else 'другая'}", differ=True)

    # ㉙ Без руки или без слова владельца — отказ: назначение без источника — слух.
    db_m = build([])
    snap_m = snapshot(db_m)
    out_m1, code_m1 = run(db_m, "coordinator", "--set", "COORD-B", "--actor", "PROTO", "--apply")
    out_m2, code_m2 = run(db_m, "coordinator", "--set", "COORD-B", "--word", WORD, "--apply")
    out_m3, code_m3 = run(db_m, "coordinator", "--set", "COORD-B", "--actor", "PROTO",
                          "--word", "   ", "--apply")
    refused_all = all(c != 0 and "ПОМЕТКА НЕ ПОСТАВЛЕНА" in o and "--actor" in o and "--word" in o
                      for o, c in ((out_m1, code_m1), (out_m2, code_m2), (out_m3, code_m3)))
    ok &= case("㉙ без --actor или без слова владельца — отказ, ничего не записано",
               refused_all and snapshot(db_m) == snap_m,
               f"без слова: код {code_m1} · без руки: код {code_m2} · слово из пробелов: "
               f"код {code_m3} · таблицы {'не тронуты' if snapshot(db_m) == snap_m else 'ТРОНУТЫ'}",
               differ=True)

    # ㉚ Справка подкоманды: по-русски и с примером вызова.
    out_h, code_h = run(build([]), "coordinator", "--help")
    ok &= case("㉚ справка подкоманды по-русски и с примером вызова",
               code_h == 0 and "Пример вызова" in out_h and "--set" in out_h and "--apply" in out_h
               and "--word" in out_h and "--actor" in out_h and "show this help" not in out_h
               and "options:" not in out_h and "usage:" not in out_h,
               f"код {code_h} · пример: {'есть' if 'Пример вызова' in out_h else 'НЕТ'} · "
               f"английские заголовки: "
               f"{'есть' if ('options:' in out_h or 'usage:' in out_h) else 'нет'}", differ=True)

    print()
    # ⚠️ Подпись НАЗЫВАЕТ испытанную копию, а не повторяет вчерашнюю правду: до 09.08 здесь
    # стояло «испытан ЖИВОЙ скрипт» всегда — и прогон по шаблону уверенно врал о себе.
    which = "ЖИВОЙ контур" if str(mezo_target.scripts_root()) == str(mezo_target.LIVE_SCRIPTS) \
        else f"копия: {mezo_target.scripts_root()}"
    if break_name:
        which += f" · ПОЛОМКА «{break_name}»"
    print(f"{'✅ ПРАВА ПОЛЯМИ ПРИНЯТЫ' if ok else '🔴 НЕ ПРИНЯТЫ'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {which}")

    # ═══ покрытие поломками — ВЫЧИСЛЯЕТСЯ из словаря, а не числом в тексте ═══
    covered = set().union(*(set(v) for v in BREAK_FAILS.values()))
    covered_run = [n for n in RUN_IDS if n in covered]
    uncovered = [n for n in RUN_IDS if n not in covered]
    unknown = sorted(covered - set(RUN_IDS))
    no_list = sorted(set(BREAKS) - set(BREAK_FAILS))
    if break_name:
        expected_fail = set(BREAK_FAILS[break_name])
        actual_fail = set(FAILED)
        if expected_fail == actual_fail:
            print(f"🧪 ожидание поломки «{break_name}» ПОДТВЕРДИЛОСЬ: провалены ровно "
                  f"{' '.join(n for n in RUN_IDS if n in actual_fail)}")
            # поломка поймана как записано — стенд хранить незачем; код выхода прежний
            mezo_stand.expected_break()
        else:
            print(f"⚠️ ожидание поломки «{break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали "
                  f"{' '.join(n for n in RUN_IDS if n in expected_fail) or 'ничего'}, "
                  f"провалены {' '.join(n for n in RUN_IDS if n in actual_fail) or 'ничего'}")
    print(f"покрытие: нарочной поломкой из словаря покрыто {len(covered_run)} случаев "
          f"({' '.join(covered_run)}; совпадение проверяет прогон с --break <имя>) · ни одной "
          f"поломкой не покрыты: {' '.join(uncovered) if uncovered else 'нет'}")
    if unknown or no_list:
        print(f"⚠️ словарь поломок расходится со случаями: номера без случая — "
              f"{' '.join(unknown) or 'нет'}; поломки без списка провалов — "
              f"{', '.join(no_list) or 'нет'}")
    mismatch = bool(break_name and set(BREAK_FAILS[break_name]) != set(FAILED))
    return 0 if ok and not mismatch and not unknown and not no_list else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
