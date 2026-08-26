# -*- coding: utf-8 -*-
"""
write-message-vnext.py — ПРОТОТИП записи ноты в v-next: адресат полем + словарь имён (Э-Б).

Доказывает свойства (все — из оплаченных фрикций, ни одно не из головы):
  · R15a — путь к БД не зависит от CWD (было: роль звала из чужого каталога и молча
           попадала в другую живую БД — F20);
  · R3/Э-Б — адресат ПОЛЕМ при записи (`--to`/`--cc`), а не прозой в теле;
  · Э-Б/Р1 — разделители: запятая И пробел. Живой писатель делит только по запятой,
           и 26.08 в живом поле лежали 8 склеек «CHROME CORE STUD» одной строкой —
           отбор «только моё» такие записки не показывал НИКОМУ из склеенных;
  · Э-Б/Р2-Р3 — словарь имён ЗАПРОСОМ к таблице ролей (+спец-имена), нераспознанное
           имя — ОТКАЗ ДО ЗАПИСИ с названным словарём: адресат опечаткой = нота-призрак;
  · Э-Б/Р4 — «всем» — СВОЙСТВО ЗАПИСКИ (колонка broadcast), не роль-адресат:
           роли «ВСЕ» не существует, строка о ней лгала бы о реестре.

⚰️ Прежняя редакция (05.08) писала в песочницу СВОЕЙ формы (addressed_by,
message_closure) — форма разошлась и со схемой Э-В, и с живой (замер 26.08,
08-addressee-dictionary.md Р4½). Теперь прототип пишет в КОПИЮ ЖИВОЙ схемы после
migrate-addressee-vnext.py; `--closes` уехал в Э-Г вместе со своей таблицей.

⛔ Живую БД не открывает: прототип пишет только в песочницу.
"""
import argparse
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # хелпер лежит рядом со скриптом
from mezo_paths import resolve_db                           # noqa: E402
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

LIVE_DB = mezo_paths.live_db()
СПЕЦ = {"ВЛАДЕЛЕЦ"}                       # адресуемо, но роли в реестре нет
СИНОНИМЫ = {"OWNER": "ВЛАДЕЛЕЦ", "ALL": "ВСЕ"}   # канон — русские имена контура


def разбор_имён(s: str) -> list:
    """Запятая И пробел — оба разделители; @ и регистр не значимы; синонимы к канону."""
    имена = []
    for x in re.split(r"[,\s]+", s or ""):
        x = x.strip().upper().lstrip("@")
        if x:
            имена.append(СИНОНИМЫ.get(x, x))
    return имена


def write(con, role, body, tags, priority, to, cc):
    """→ (ok, message). Все отказы — ДО записи: частичная нота хуже ненаписанной."""
    словарь = {r for r, in con.execute("SELECT role FROM roles")} | СПЕЦ
    всем = "ВСЕ" in to or "ВСЕ" in cc
    to = [r for r in to if r != "ВСЕ"]
    cc = [r for r in cc if r != "ВСЕ"]
    for r in to + cc:
        if r not in словарь:
            return False, (f"⛔ ОТКАЗ: имени «{r}» нет в словаре адресатов.\n"
                           f"   Словарь: {', '.join(sorted(словарь))} + «все» (широковещательно).\n"
                           f"   Адресат опечаткой = нота-призрак: отправлена и не дошла никому.")
    if всем and not (to or cc) and not body:
        return False, "⛔ ОТКАЗ: пустая нота."

    cols = {r[1] for r in con.execute("PRAGMA table_info(messages)")}
    if "broadcast" not in cols:
        return False, ("⛔ ОТКАЗ: в этой песочнице нет колонки broadcast — прогони"
                       " migrate-addressee-vnext.py. Писать «всем» строкой-адресатом"
                       " не стану: роль «ВСЕ» — ложь о реестре.")

    # Защита ДВОЙНАЯ: словарь выше + контракт схемы (PK/FK/CHECK). Второй слой не
    # избыточность: проверку в CLI обходит любой второй писатель.
    try:
        cur = con.execute(
            "INSERT INTO messages (writer_role, body_md, tags, priority, timestamp, broadcast)"
            " VALUES (?,?,?,?,datetime('now'),?)",
            (role, body, tags, priority, int(всем)))
        mid = cur.lastrowid
        for kind, names in (("to", to), ("cc", cc)):
            for r in names:
                con.execute(
                    "INSERT OR REPLACE INTO message_addressee (message_id, role, kind, linked_by)"
                    " VALUES (?,?,?,'field')", (mid, r, kind))
        con.commit()
    except sqlite3.IntegrityError as e:
        con.rollback()
        return False, (f"⛔ ОТКАЗ СХЕМЫ (второй слой защиты сработал, значит проверка выше"
                       f" была обойдена или неполна): {e}")
    addr = (f"to={sorted(to) or '—'} cc={sorted(cc) or '—'}{' ВСЕМ' if всем else ''}")
    return True, f"OK #{mid} [{role}] {addr} priority={priority}"


def main():
    ap = argparse.ArgumentParser(description="Записать ноту (прототип v-next, Э-Б)")
    ap.add_argument("--db", default=None,
                    help="необязателен: по умолчанию — БД рядом со скриптом (см. mezo_paths)")
    ap.add_argument("--role", required=True)
    ap.add_argument("--body", required=True)
    ap.add_argument("--tags", default="")
    ap.add_argument("--priority", default="normal", choices=["normal", "high", "critical"])
    # Э-Г (карточка #260): critical — дефицит, и дефицит держится ОСНОВАНИЕМ, а не квотой.
    # Замер живой ленты 26.08: 86 из 89 critical УЖЕ несут основание в теле (слово
    # владельца · авария · остановка) — требование узаконивает практику, а не вводит новую;
    # под нож попали бы 3 ноты июля, и глазами все три — high, назвавшийся critical.
    # Квота отвергнута тем же замером: 2/роль/сутки срезала бы 82% истории, включая дни,
    # когда владелец сам останавливал работы. Паттерн основания уже в контуре: --again
    # и --pass-by-index --basis живого писателя.
    ap.add_argument("--basis", default="",
                    help="critical: ЧЕМ обосновано (слово владельца с часом · авария · "
                         "что сломано). Без основания critical отклоняется")
    ap.add_argument("--to", default="", help="адресаты: запятая И пробел — оба разделители")
    ap.add_argument("--cc", default="", help="в копию: те же разделители; «все» — всем")
    args = ap.parse_args()

    db = resolve_db(args.db, __file__)
    if Path(db).resolve() == LIVE_DB.resolve():
        sys.exit("⛔ ОТКАЗ: это ЖИВАЯ mezosync.db. Прототип работает только по песочнице.")

    con = sqlite3.connect(f"file:{db}?mode=rw", uri=True, timeout=5)
    con.execute("PRAGMA foreign_keys = ON")
    if args.priority == "critical" and len(args.basis.strip()) < 12:
        print("⛔ CRITICAL БЕЗ ОСНОВАНИЯ ОТКЛОНЁН: нужен --basis «чем обосновано»")
        print("   (не короче 12 знаков — слово владельца с часом · авария · что сломано).")
        print("   Основание уйдёт ПЕРВОЙ строкой тела: читающий critical первым делом")
        print("   спрашивает «почему это срочно», и ответ обязан быть до текста.")
        print("   Если основания нет — это high, и high не требует ничего.")
        sys.exit(4)
    if args.priority == "critical":
        args.body = f"[основание critical: {args.basis.strip()}]\n{args.body}"
    ok, msg = write(con, args.role.upper(), args.body, args.tags, args.priority,
                    разбор_имён(args.to), разбор_имён(args.cc))
    con.close()
    print(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
