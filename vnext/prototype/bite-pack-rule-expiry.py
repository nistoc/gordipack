# -*- coding: utf-8 -*-
"""bite-pack-rule-expiry.py — приёмка карточки #650: срок правила (вид и условие) доезжает
из пакета до контура — при сборке нового контура и при rules-from-pack.py --adopt.

ЗАЧЕМ. Замер 25.09: у контура, собранного из пакета, условный срок не совпал со сводом
контура-донора ни у одного из 17 правил, а вид «бессрочно» не дошёл ни до одного из 40 —
посев вставлял правила без срока, и заготовка сборки ставила всем «до пересмотра
владельцем нового контура». --adopt срока не переносил вовсе: новому ключу — «бессрочно»,
у старого оставалась заготовка. Теперь срок едет в строке правила посева
(rules/universal.sql), а --adopt берёт его оттуда же.

Случаи (стенд — копии пакета и контуры, собранные из них в стенде; в копию посева вписаны
две подставные строки правил приёмки, поэтому ни живые роли, ни живой свод Atlas не
нужны — приёмка идёт и в свежем контуре из пакета):
  ①  свежий контур из копии пакета: срок каждого правила, объявленный в строке посева,
      дошёл дословно (вид и условие); в посеве объявлен хотя бы один условный срок
  ③  подставное правило со сроком «до события» (until_event) дошло с этим сроком; при
      потере приёмка называет его
  ②в контур прежней версии (собран из той же копии, но строки посева — без срока): список
      и --summary называют правила, чей срок пакета можно взять, и правило со своим сроком
  ②а --adopt всех правил с текстом как в пакете (--rule-set universal) кладёт срок пакета;
      текст и версия не меняются; где срок в посеве не объявлен — срок прежний
  ②б тот же --adopt не заменяет срок, который контур поставил сам, и называет его
  ②г --adopt --expiry-from-pack кладёт срок пакета и поверх своего

Нарочные поломки (--break; --porcha — синоним):
  insert-drops-expiry ....... строки посева без срока: срок не переносится  → ① ③
  seed-fills-forever-cond ... заготовка условия ставится и «бессрочным»      → ①
  adopt-ignores-expiry ...... --adopt не читает срок пакета                  → ②а ②б ②г
  adopt-overwrites-own ...... --adopt заменяет и свой срок контура           → ②б
  from-pack-ignored ......... --expiry-from-pack не действует                → ②г
  hint-silent ............... список молчит о сроке                          → ②в
Первые две портят копию посева, из которой собирается свежий контур; остальные — копию
испытуемого rules-from-pack.py в контуре прежней версии.

    python bite-pack-rule-expiry.py [--break <имя>]
    MEZO_PACK_ROOT=<корень пакета> — испытать копию пакета (по умолчанию — пакет контура);
    MEZO_SCRIPTS_ROOT=<каталог> — испытать другую копию rules-from-pack.py (mezo_target).

Живого не касается: пакет — копией (файлы, отслеживаемые git, содержимое рабочей копии;
без git — каталоги целиком), контуры собираются в стенде, испытуемый rules-from-pack.py
(mezo_target) — копией в контуре стенда (mezo_stand.copy_tool), среда каждого подпроцесса —
mezo_stand.stand_env. Полный вывод каждого запуска — файлами в стенде.
⚖ Чего НЕ проверяет: доменные наборы (rules/domain-specific) срока не объявляют — их правила
получают заготовку сборки; сличение срока с живым сводом Atlas — дело замера, а не приёмки
(приёмка обязана идти в контуре без Atlas).
"""
import argparse
import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

TARGET = mezo_target.script("rules-from-pack.py")
print(f"⚖ испытуется rules-from-pack.py: {mezo_target.label()}")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(mezo_paths.live_scripts()))
import mezo_stand  # noqa: E402

SUBDIRS = ("rules", "schema", "scripts", "templates", "vnext")
PLACEHOLDER = ("until_event", "до пересмотра владельцем нового контура")
CONDITIONAL = ("until_date", "until_event", "while_measured")
PROBE_EVENT = "zz-bite-expiry-until-event"
PROBE_OWN = "zz-bite-expiry-own"
PROBES = {
    PROBE_EVENT: ("ПРОБА приёмки срока правил: правило со сроком «до события».",
                  "until_event", "до конца пробы приёмки срока правил"),
    PROBE_OWN: ("ПРОБА приёмки срока правил: у контура прежней версии будет свой срок.",
                "until_event", "до конца второй пробы приёмки срока правил"),
}
OWN_EXPIRY = ("while_measured", "пока проба приёмки меряет свой срок контура")
WORD = "проба приёмки bite-pack-rule-expiry на копии в стенде"
ACTOR = "BITE650"

HEADER_FULL = ("INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version, expiry_kind, "
               "expiry_cond) VALUES")
HEADER_BARE = "INSERT OR REPLACE INTO rules (rule_key, body, locked_by, version) VALUES"
LITERAL = r"(?:NULL|'(?:[^']|'')*')"
ROW_START = re.compile(r"^\('([^']+)',[ \t]*$")
ROW_END = re.compile(r"^ '(?:owner|coord)', \d+(?:, (" + LITERAL + r"), (" + LITERAL
                     + r"))?\)[,;][ \t]*$")
ROW_END_FULL = re.compile(r"^( '(?:owner|coord)', \d+), " + LITERAL + ", " + LITERAL
                          + r"(\)[,;][ \t]*)$", re.M)
SEED_CASE = ("  expiry_cond = CASE WHEN expiry_kind IS NULL\n"
             "                     THEN COALESCE(expiry_cond, 'до пересмотра владельцем нового контура')\n"
             "                     ELSE expiry_cond END\n")
SEED_OLD = "  expiry_cond = COALESCE(expiry_cond, 'до пересмотра владельцем нового контура')\n"

TAKE_LINE = re.compile(r"⏳ срок пакета можно взять у (\d+) правил[^:]*: (.*)$", re.M)
OWN_LINE = re.compile(r"📌 срок у вас свой у (\d+) правил[^:]*: (.*)$", re.M)
SUMMARY_LINE = re.compile(r"срок правил пакета: взять можно у (\d+) · у вас свой у (\d+)")

# имя → (что портим, (образец, замена) либо None, какие случаи обязаны провалиться)
BREAKS = {
    "insert-drops-expiry": ("pack", None, {"①", "③"}),
    "seed-fills-forever-cond": ("pack", (SEED_CASE, SEED_OLD), {"①"}),
    "adopt-ignores-expiry": ("tool", ("    pack, seed, reason = pack_expiry_for(source, row)\n",
                                      "    pack, seed, reason = None, None, None\n"),
                             {"②а", "②б", "②г"}),
    "adopt-overwrites-own": ("tool", ("        if expiry_is_seed(mine, seed):\n"
                                      "            return take, ",
                                      "        if True:\n"
                                      "            return take, "), {"②б"}),
    "from-pack-ignored": ("tool", ("take_pack=expiry_from_pack)", "take_pack=False)"), {"②г"}),
    "hint-silent": ("tool", ("        print_expiry_differences(take, own, db_path)\n",
                             "        pass\n"), {"②в"}),
}

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


def text_sha(body):
    """Отпечаток текста правила — та же формула, что у rules-from-pack.py и сборщика базы."""
    return hashlib.sha256((body or "").replace("\r\n", "\n").rstrip().encode("utf-8")).hexdigest()[:16]


def norm(value):
    value = (value or "").strip()
    return value or None


def show(expiry):
    if expiry is None or not expiry[0]:
        return "пусто"
    return expiry[0] + (f" — «{expiry[1]}»" if expiry[1] else "")


def names(keys, limit=6):
    keys = list(keys)
    if not keys:
        return "нет"
    return ", ".join(keys[:limit]) + (f" … ещё {len(keys) - limit}" if len(keys) > limit else "")


def find_pack():
    """Корень пакета: MEZO_PACK_ROOT (как у bite-rules-annex.py — испытать копию пакета до
    публикации), иначе тем же поиском, что у соседних приёмок (bite-fresh-circuit.py)."""
    candidates = [Path(os.environ["MEZO_PACK_ROOT"])] if os.environ.get("MEZO_PACK_ROOT") else []
    try:
        candidates.append(mezo_paths.template_root())
    except SystemExit:
        pass
    candidates += [HERE.parent.parent / "gordipack", HERE.parent / "gordipack"]
    for cand in candidates:
        if (cand / "scripts" / "init-group.py").exists() and (cand / "rules" / "universal.sql").exists():
            return cand
    sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: пакета нет ни в одном из мест: "
             + ", ".join(str(c) for c in candidates))


def copy_pack(pack, dest):
    """Копия пакета: только файлы, отслеживаемые git (сосед берёт пакет через git), содержимое —
    рабочей копии; без git — каталоги целиком, и это говорится строкой."""
    tracked = None
    if (pack / ".git").exists():
        r = subprocess.run(["git", "-C", str(pack), "ls-files", *SUBDIRS], capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
        if r.returncode == 0:
            tracked = [line.strip() for line in r.stdout.splitlines() if line.strip()]
    if tracked is None:
        print(f"   копия пакета: {pack} — без git, каталоги скопированы целиком")
        for name in SUBDIRS:
            if (pack / name).is_dir():
                shutil.copytree(pack / name, dest / name,
                                ignore=shutil.ignore_patterns("__pycache__"))
        return
    for rel in tracked:
        src = pack / rel
        if "__pycache__" in rel or not src.is_file():
            continue
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def read_sql(path):
    """Текст посева с переводами строк LF и признак, были ли они CRLF (запись — тем же видом)."""
    raw = path.read_bytes().decode("utf-8")
    return raw.replace("\r\n", "\n"), "\r\n" in raw


def write_sql(path, text, crlf):
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))


def sql_value(token):
    return None if token is None or token == "NULL" else token[1:-1].replace("''", "'")


def declared_expiry(text):
    """Срок из строк посева: {ключ: (вид, условие)}; последнее описание ключа побеждает, как
    при исполнении файла; (None, None) — в строке срока нет. Разбор по тексту, а не
    исполнением: он не зависит от блоков, которые при сборке срок заполняют или теряют."""
    out, key = {}, None
    for line in text.split("\n"):
        if key is None:
            m = ROW_START.match(line)
            if m:
                key = m.group(1)
            continue
        m = ROW_END.match(line)
        if m:
            out[key] = (norm(sql_value(m.group(1))), norm(sql_value(m.group(2))))
            key = None
    return out


def strip_expiry(text):
    """Строки посева без срока — как до карточки #650. → (текст, заголовков, строк)."""
    heads = text.count(HEADER_FULL)
    text = text.replace(HEADER_FULL, HEADER_BARE)
    text, rows = ROW_END_FULL.subn(r"\1\2", text)
    return text, heads, rows


def add_probes(pack_dir):
    """Две подставные строки правил — в копию посева (последним INSERT перед блоком
    «происхождение при посеве») и в копию базы правил пакета."""
    sql = pack_dir / "rules" / "universal.sql"
    text, crlf = read_sql(sql)
    last_insert = text.rfind("INSERT OR REPLACE INTO rules")
    pos = text.find("\nUPDATE rules SET", last_insert) if last_insert >= 0 else -1
    if pos < 0:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: в копии посева нет места для подставных правил "
                 "(за последним INSERT OR REPLACE не найден UPDATE rules SET)")
    rows = [f"('{key}',\n '{body}',\n 'coord', 1, '{kind}', '{cond}')"
            for key, (body, kind, cond) in PROBES.items()]
    block = ("-- подставные правила приёмки bite-pack-rule-expiry.py (только в копии пакета)\n"
             + HEADER_FULL + "\n" + ",\n".join(rows) + ";\n\n")
    write_sql(sql, text[:pos + 1] + block + text[pos + 1:], crlf)
    db = pack_dir / "rules" / "pack-rules.db"
    if not db.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в копии пакета нет базы правил ({db})")
    con = sqlite3.connect(str(db))
    cols = {r[1] for r in con.execute("PRAGMA table_info(pack_rules)")}
    if not {"rule_set", "rule_key", "body", "text_sha"} <= cols:
        con.close()
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в базе правил пакета нет таблицы pack_rules нужного вида ({db})")
    for key, (body, _kind, _cond) in PROBES.items():
        row = {"rule_set": "universal", "rule_key": key, "body": body, "locked_by": "coord",
               "text_sha": text_sha(body), "pack_updated_at": "2026-09-25 00:00:00 UTC",
               "pack_commit": "c650000", "removed_at": None}
        row = {k: v for k, v in row.items() if k in cols}
        con.execute(f"INSERT OR REPLACE INTO pack_rules ({', '.join(row)}) "
                    f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()))
    con.commit()
    con.close()


def build(pack_dir, container, name, log):
    """Сборка контура init-group.py копии пакета — в стенде, со средой стенда."""
    container.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, str(pack_dir / "scripts" / "init-group.py"),
                        "--name", name, "--path", str(container / ".mezosync"), "--roles", "coord"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900, env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
    log.write_text((r.stdout or "") + (r.stderr or ""), encoding="utf-8")
    db = container / ".mezosync" / "mezosync.db"
    if r.returncode != 0 or not db.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: сборка контура «{name}» из копии пакета — код {r.returncode}; "
                 f"полный вывод: {log}")
    return db


def run_tool(tool, container, args, log):
    """Запуск испытуемой копии rules-from-pack.py; полный вывод — в файл стенда."""
    r = subprocess.run([sys.executable, str(tool), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=900,
                       env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
    out = (r.stdout or "") + (r.stderr or "")
    log.write_text(out, encoding="utf-8")
    return r.returncode, out


def read_contour(db):
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    rows = con.execute("SELECT rule_key, body, version, COALESCE(status, 'active'), expiry_kind, "
                       "expiry_cond FROM rules").fetchall()
    con.close()
    return {k: {"body": b, "version": v, "active": s == "active", "expiry": (norm(ek), norm(ec))}
            for k, b, v, s, ek, ec in rows}


def pack_universal(db):
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    rows = con.execute("SELECT rule_key, text_sha FROM pack_rules WHERE rule_set='universal' "
                       "AND COALESCE(removed_at, '') = ''").fetchall()
    con.close()
    return dict(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", "--porcha", dest="break_name", choices=sorted(BREAKS))
    a = ap.parse_args()
    brk = BREAKS.get(a.break_name)
    pack = find_pack()
    print(f"⚖ пакет: {pack}")
    if brk:
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}» ВЛОЖЕНА. Ждём провала РОВНО: "
              f"{' '.join(sorted(brk[2]))}")

    stand = mezo_stand.new("bite-pack-rule-expiry-")
    base = stand / "pack"
    copy_pack(pack, base)
    add_probes(base)
    base_text, _crlf = read_sql(base / "rules" / "universal.sql")
    declared = declared_expiry(base_text)
    for key, (_body, kind, cond) in PROBES.items():
        if declared.get(key) != (kind, cond):
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: подставное правило {key} не разобрано из копии посева")

    # копия для свежего контура — сюда ложится поломка посева
    fresh_pack = stand / "pack-fresh"
    shutil.copytree(base, fresh_pack)
    if brk and brk[0] == "pack":
        sql = fresh_pack / "rules" / "universal.sql"
        text, crlf = read_sql(sql)
        if brk[1] is None:
            text, heads, rows = strip_expiry(text)
            if not heads or not rows:
                sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                         f"(в строках посева срока нет)")
        else:
            old, new = brk[1]
            if text.count(old) != 1:
                sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                         f"(образец найден {text.count(old)} раз)")
            text = text.replace(old, new)
        write_sql(sql, text, crlf)

    # копия для контура прежней версии — строки посева без срока, как до карточки #650
    old_pack = stand / "pack-old"
    shutil.copytree(base, old_pack)
    text, crlf = read_sql(old_pack / "rules" / "universal.sql")
    text, _heads, _rows = strip_expiry(text)
    left = [k for k, e in declared_expiry(text).items() if e != (None, None)]
    if left or HEADER_FULL in text:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: срок не снят со всех строк посева прежней версии: " + names(left))
    write_sql(old_pack / "rules" / "universal.sql", text, crlf)

    fresh_c, old_c = stand / "fresh", stand / "old"
    fresh_db = build(fresh_pack, fresh_c, "bitexpfresh", stand / "build-fresh.log")
    old_db = build(old_pack, old_c, "bitexpold", stand / "build-old.log")

    # ── ① ③ свежий контур ─────────────────────────────────────────────────────────────
    fresh = read_contour(fresh_db)
    if set(declared) != set(fresh):
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: разбор строк посева и собранный контур расходятся составом: "
                 f"только в разборе — {names(sorted(set(declared) - set(fresh)))}; "
                 f"только в контуре — {names(sorted(set(fresh) - set(declared)))}")
    real = {k: e for k, e in declared.items() if k not in PROBES}
    decl = {k: e for k, e in real.items() if e[0]}
    undecl = sorted(k for k, e in real.items() if not e[0])
    by_kind = {}
    for kind, _cond in decl.values():
        by_kind[kind] = by_kind.get(kind, 0) + 1
    conditional = [k for k, e in decl.items() if e[0] in CONDITIONAL]
    wrong = sorted(k for k, e in decl.items() if fresh[k]["expiry"] != e)
    seeded = sum(1 for k in undecl if fresh[k]["expiry"] == PLACEHOLDER)
    wrong_text = "; ".join(f"{k}: пришло {show(fresh[k]['expiry'])}, объявлено {show(decl[k])}"
                           for k in wrong[:4])
    case("①", "свежий контур из пакета: срок каждого правила, объявленный в строке посева, "
              "дошёл дословно; условный срок в посеве объявлен",
         bool(conditional) and not wrong,
         f"срок объявлен у {len(decl)} правил ("
         + " · ".join(f"{k} {n}" for k, n in sorted(by_kind.items()))
         + f"), условный у {len(conditional)} · дошёл дословно у {len(decl) - len(wrong)} из "
         f"{len(decl)}" + (f" · НЕ дошёл у {len(wrong)}: {wrong_text}"
                           + (f" … ещё {len(wrong) - 4}" if len(wrong) > 4 else "") if wrong else "")
         + f" · не объявлен у {len(undecl)} — заготовка сборки у {seeded} из {len(undecl)}")
    got, want = fresh[PROBE_EVENT]["expiry"], PROBES[PROBE_EVENT][1:]
    case("③", f"правило со сроком until_event в пакете дошло с этим сроком ({PROBE_EVENT})",
         got == want, f"{PROBE_EVENT}: пришло {show(got)} · в пакете {show(want)}")

    # ── ② контур прежней версии ───────────────────────────────────────────────────────
    con = sqlite3.connect(str(old_db))
    con.execute("UPDATE rules SET expiry_kind=?, expiry_cond=? WHERE rule_key=?",
                (*OWN_EXPIRY, PROBE_OWN))
    con.commit()
    con.close()
    before = read_contour(old_db)
    if before.get(PROBE_OWN, {}).get("expiry") != OWN_EXPIRY:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: свой срок контура у {PROBE_OWN} не поставлен")
    tool = mezo_stand.copy_tool(TARGET, old_c / ".mezosync" / "scripts")
    if brk and brk[0] == "tool":
        text = tool.read_text(encoding="utf-8")
        old, new = brk[1]
        if text.count(old) != 1:
            sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку «{a.break_name}» вложить некуда "
                     f"(образец найден {text.count(old)} раз)")
        tool.write_bytes(text.replace(old, new).encode("utf-8"))

    in_pack = pack_universal(base / "rules" / "pack-rules.db")
    keys = sorted(k for k, r in before.items() if r["active"] and in_pack.get(k) == text_sha(r["body"]))
    outside = sorted(k for k, r in before.items() if r["active"] and k not in keys)
    valid = {k: e for k, e in declared.items() if e[0] and not (e[0] in CONDITIONAL and not e[1])}
    want_take = sorted(k for k in keys if k != PROBE_OWN and k in valid
                       and before[k]["expiry"] != valid[k])
    common = ["--db", str(old_db), "--source", str(base)]

    rc_l, out_l = run_tool(tool, old_c, common, stand / "list.log")
    rc_s, out_s = run_tool(tool, old_c, [*common, "--summary"], stand / "summary.log")
    m_take, m_own, m_sum = TAKE_LINE.search(out_l), OWN_LINE.search(out_l), SUMMARY_LINE.search(out_s)
    listed = sorted(m_take.group(2).strip().split(" · ")) if m_take else []
    listed_own = sorted(m_own.group(2).strip().split(" · ")) if m_own else []
    case("②в", "контур прежней версии: список и --summary называют правила, чей срок пакета "
               "можно взять, и правило со своим сроком",
         rc_l == 0 and rc_s == 0 and m_take is not None and int(m_take.group(1)) == len(want_take)
         and listed == want_take and listed_own == [PROBE_OWN] and m_sum is not None
         and int(m_sum.group(1)) == len(want_take) and int(m_sum.group(2)) == 1,
         f"код списка {rc_l}, --summary {rc_s} · взять можно: названо {len(listed)}, ждали "
         f"{len(want_take)} (лишние: {names(sorted(set(listed) - set(want_take)))}; не названы: "
         f"{names(sorted(set(want_take) - set(listed)))}) · свой срок назван у: "
         f"{names(listed_own)} · строка --summary: {m_sum.group(0) if m_sum else 'нет'}")

    rc_a, out_a = run_tool(tool, old_c, [*common, "--adopt", *keys, "--rule-set", "universal",
                                         "--word", WORD, "--actor", ACTOR, "--apply"],
                           stand / "adopt.log")
    after = read_contour(old_db)
    others = [k for k in keys if k != PROBE_OWN]
    not_taken = [k for k in others if k in valid and after[k]["expiry"] != valid[k]]
    touched = [k for k in others if k not in valid and after[k]["expiry"] != before[k]["expiry"]]
    changed = [k for k in keys if after[k]["body"] != before[k]["body"]
               or after[k]["version"] != before[k]["version"]]
    n_valid = sum(1 for k in others if k in valid)
    n_cond = sum(1 for k in others if k in valid and valid[k][0] in CONDITIONAL)
    case("②а", "--adopt кладёт срок пакета всем правилам, где он объявлен; текст и версия те же; "
               "где не объявлен — срок прежний",
         rc_a == 0 and bool(others) and n_valid > 0 and not not_taken and not touched and not changed,
         f"код {rc_a} · взято ключей {len(keys)} · срок объявлен у {n_valid} (условный у {n_cond}), "
         f"лёг у {n_valid - len(not_taken)} · не лёг: {names(not_taken)} · срок тронут у "
         f"необъявленных: {names(touched)} · текст или версия изменились: {names(changed)} · "
         f"вне взятия (текст не как в базе правил пакета): {names(outside)} · полный вывод: "
         f"{stand / 'adopt.log'}")

    lines = out_a.splitlines()
    at = next((i for i, line in enumerate(lines) if line.startswith(f"БЕРУ: {PROBE_OWN} ")), None)
    named = at is not None and at + 1 < len(lines) and "📌 срок: у вас свой" in lines[at + 1]
    case("②б", "--adopt не заменяет срок, который контур поставил сам, и называет его",
         rc_a == 0 and after[PROBE_OWN]["expiry"] == OWN_EXPIRY and named,
         f"{PROBE_OWN}: после --adopt {show(after[PROBE_OWN]['expiry'])} · свой был "
         f"{show(OWN_EXPIRY)} · назван строкой «у вас свой»: {'да' if named else 'нет'}")

    rc_g, _out_g = run_tool(tool, old_c, [*common, "--adopt", PROBE_OWN, "--rule-set", "universal",
                                          "--expiry-from-pack", "--word", WORD, "--actor", ACTOR,
                                          "--apply"], stand / "adopt-from-pack.log")
    got_g, want_g = read_contour(old_db)[PROBE_OWN]["expiry"], PROBES[PROBE_OWN][1:]
    case("②г", "--adopt --expiry-from-pack кладёт срок пакета и поверх своего срока контура",
         rc_g == 0 and got_g == want_g,
         f"код {rc_g} · {PROBE_OWN}: после {show(got_g)} · в пакете {show(want_g)}")

    print(f"\n   полный вывод сборок и запусков — файлами в стенде: {stand}")
    print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
    if brk:
        exact = set(RED) == brk[2]
        print(f"{'✅' if exact else '🔴'} поломка «{a.break_name}»: провалились "
              f"{' '.join(sorted(RED)) or 'никто'} · ждали {' '.join(sorted(brk[2]))}")
        return mezo_stand.finish(0 if exact else 1)
    return mezo_stand.finish(0 if FAIL == 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
