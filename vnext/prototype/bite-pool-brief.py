# -*- coding: utf-8 -*-
r"""
bite-pool-brief.py — приёмка захода 2.1 + П⑥: собираемый наказ (role-brief.py) и паёк
пула. На КОПИИ живой базы (mezo_stand); живая база только читается.

Случаи:
  ① целые источники → наказ несёт зону, права, формы, свод — БЕЗ предупреждений
  ② участница активного пула → паёк несёт ВСЕ ТРИ блока: наказ + выжимка пула
     (карточки) + скиллы (пула и роли)
  ③ ВСТРЕЧНЫЙ: роль вне пула → блока пула нет, «твоих карточек нет» СЛОВАМИ
  ④ пустое поле скиллов пула → «НЕ НАЗВАНЫ» словами, не молчание
  ⑤ умение с expired_at в паёк НЕ попадает; живое — попадает; скрытое посчитано вслух
  ⑥ ИСТОЧНИКИ ЛОМАЮТСЯ ПОРОЗНЬ (DROP TABLE) → наказ НАЗЫВАЕТ, чего не хватает,
     и НЕ молчит; остальные секции живут (по одному прогону на источник)
  ⑦ базы нет вовсе → отказ «НЕ СОБРАН», не пустой наказ
  ⑧ контроль: СВОИХ следов приёмки в живой базе нет — судим свои следы, а не время
     правки общей базы (карточка #444: чужие записи красили цвет по занятости соседей)
  ⑧-бис контроль ПОРЧИ (карточка #455): число активных наборов живой базы ДО и
     ПОСЛЕ прогона совпадает — собственная подсадка приёмки (правит чужие строки
     на КОПИИ, вставочных следов не оставляет) не утекла в живую базу; судится
     РАЗНИЦЕЙ числа, не абсолютным «активных 0» — иначе контур без единого
     активного набора красил бы ложно при каждом прогоне (карточка #667, см. ниже
     у самого случая: сверено чтением, что role-brief.py тут ни при чём)
  ⑨ строка о службе просмотра базы (слово владельца 2026-10-04 07:38 UTC, чат PROTO):
     правило periscope-viewer действует → ОДНА строка «ПЕРИСКОП» со ссылкой
     «set-rule.py --key periscope-viewer --show»
  ⑨-бис ВСТРЕЧНЫЙ: правила в своде НЕТ → строка ведёт в ПАКЕТ («rules-from-pack.py
     --show periscope-viewer»), ссылки на set-rule.py нет — она отдала бы отказ
  ⑨-тер правило СНЯТО → строка «снято» с пометкой о снятии, ссылки на пакет нет
  Р1 нарочная поломка (копия role-brief.py в стенде): раздел не спрашивает свод и всегда
     печатает ссылку на правило → ⑨-бис на копии обязан провалиться ПО СВОЕЙ причине
     (строка есть и зовёт set-rule.py к отсутствующему ключу)
  Р2 нарочная поломка: раздел «просмотр базы» не вызывается → ⑨ на копии обязан
     провалиться (строки нет)
"""
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

# ═══ Карточка #454 (TAXO): испытуемый механизм — ЧЕРЕЗ ВЫБОР КОПИИ, не жёстко из
# живого. MEZO_SCRIPTS_ROOT действует; MEZO_FORBID_LIVE=1 без подмены — отказ
# «НЕ ЗАПУСТИЛАСЬ» ЗДЕСЬ, до стенда, а не зелёный прогон по живому.
# ⚖️ ГРАНИЦА, названная вслух: испытуемый — role-brief.py; стендовый инструментарий
# (mezo_stand) и копируемая база — из живого ВСЕГДА: они ставят опыт, их не испытываем.
ИСПЫТУЕМЫЙ = mezo_target.script("role-brief.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
LIVE_DB = mezo_paths.live_db()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402


def live_active_tracks() -> int:
    """Сколько активных наборов СЕЙЧАС в живой базе — строго на чтение, саму базу не трогаем."""
    con = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
    try:
        return con.execute("SELECT COUNT(*) FROM tracks WHERE status='active'").fetchone()[0]
    finally:
        con.close()


# Снимок числа активных наборов ДО любого хода этой приёмки (нужен случаю ⑧-бис
# ниже, карточка #455): мерим РАЗНИЦУ, а не абсолютное число, иначе на контуре без
# единого активного набора (ровно случай свежей сборки, карточка #667) проверка
# красила бы ложно при КАЖДОМ прогоне, хотя живую базу никто не трогал.
active_tracks_before = live_active_tracks()

OK = FAIL = 0


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def brief(db, role, tool=None):
    """tool — копия испытуемого с нарочной поломкой (лежит в стенде): её соседей
    (mezo_paths, mezo_hints) берём из каталога испытуемого через PYTHONPATH."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if tool is not None:
        env["PYTHONPATH"] = str(Path(ИСПЫТУЕМЫЙ).parent)
    p = subprocess.run([sys.executable, str(tool or ИСПЫТУЕМЫЙ),
                        "--role", role, "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def broken_copy(out_dir, name, anchor, replacement):
    """Копия испытуемого с нарочной поломкой. Якорь обязан найтись РОВНО один раз —
    иначе «ПРИЁМКА НЕ СОСТОЯЛАСЬ», а не поломка мимо цели. Окончания строк якоря —
    как у самого файла (копия из клона пакета бывает с CRLF, карточка #667)."""
    text = Path(ИСПЫТУЕМЫЙ).read_bytes().decode("utf-8")
    if "\r\n" in text:
        anchor = anchor.replace("\r\n", "\n").replace("\n", "\r\n")
        replacement = replacement.replace("\r\n", "\n").replace("\n", "\r\n")
    if text.count(anchor) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь поломки {name} найден "
                         f"{text.count(anchor)} раз в role-brief.py (нужен ровно 1)")
    path = Path(out_dir) / f"role-brief-{name}.py"
    path.write_bytes(text.replace(anchor, replacement).encode("utf-8"))
    return path


VIEWER_RULE = "periscope-viewer"
VIEWER_PROBE_BODY = "проба сводки: правило о службе просмотра базы"


def set_viewer_rule(path, state):
    """Состояние правила periscope-viewer на КОПИИ базы стенда:
    'active' · 'revoked' · 'absent'. Тело — подставное, со своей приметой для суда ⑧."""
    con = sqlite3.connect(str(path))
    con.execute("DELETE FROM rules WHERE rule_key=?", (VIEWER_RULE,))
    if state != "absent":
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,1)",
                    (VIEWER_RULE, VIEWER_PROBE_BODY, "coord"))
    if state == "revoked":
        con.execute("UPDATE rules SET status='revoked', revoked_at='2026-10-04 08:00 UTC', "
                    "revoked_by='owner', revoked_reason='проба сводки: снято' "
                    "WHERE rule_key=?", (VIEWER_RULE,))
    con.commit()
    con.close()


def viewer_lines(out):
    return [line for line in out.splitlines() if "ПЕРИСКОП" in line]


stand = mezo_stand.new("pool-brief-")
db = stand / "mezosync.db"
mezo_stand.snapshot_db(LIVE_DB, db)
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET status='paused' WHERE status='active'")
con.execute("INSERT INTO tracks (track_id, title, status, skills) VALUES "
            "('TRACK-ZZBR','пул сводки','active','скилл-до-задачи: чинить предикаты')")
con.execute("INSERT INTO roles (role, lifecycle, zone) VALUES ('ZZB','alive','проба сводки')")
con.execute("INSERT INTO backlog (role, title, body_md, status, priority, tags, parent_track, "
            "created_by, done_when) VALUES ('ZZB','часть сводки','тело','open','normal','[]',"
            "'TRACK-ZZBR','PROTO','критерий')")
con.execute("INSERT INTO role_skill (role, skill, evidence, measured_at, written_by) "
            "VALUES ('ZZB','живое умение пробы','записка-проба','2026-08-27 10:00','ZZB')")
con.execute("INSERT INTO role_skill (role, skill, evidence, measured_at, written_by, "
            "expired_at, expired_why) VALUES ('ZZB','протухшее умение пробы','записка-проба',"
            "'2026-08-01 10:00','ZZB','2026-08-27 09:00','условие наступило пробой')")
con.commit()
con.close()

# ①② участница пула
rc, out = brief(db, "ZZB")
case("① целые источники → зона+права+формы+свод, без «НЕ ПРОЧИТАН»",
     rc == 0 and "проба сводки" in out and "ФОРМЫ ВЫЗОВА" in out and "СВОД" in out
     and "НЕ ПРОЧИТАН" not in out)
case("② стартовая сводка участницы: пул + карточки + скиллы пула",
     "TRACK-ZZBR" in out and "часть сводки" in out and "скилл-до-задачи" in out)

# ①-бис КАРТОЧКА #362: уборка памяти названа ПОСЛЕ первого отчёта, и она НЕ новый шаг —
# командных форм в секции ровно 7, как до правки (уборка вынесена, а не добавлена).
формы_блок = out.split("ФОРМЫ ВЫЗОВА")[1].split("🧭")[0] if "ФОРМЫ ВЫЗОВА" in out else ""
# Карточка #440 (второй вход, STUD): пояснение по ФАКТАМ — красное называет
# НЕвыполнившуюся половину условия, а не печатает одно поле при любом исходе.
case("①-бис порядок пробуждения: УБОРКА памяти — ПОСЛЕ первого отчёта, шагов не прибавилось",
     "порядок пробуждения" in формы_блок and "ПОСЛЕ отчёта" in формы_блок
     and формы_блок.count("python ") == 7,
     f"строка порядка: {'есть' if 'порядок пробуждения' in формы_блок else 'НЕТ'} · "
     f"«ПОСЛЕ отчёта»: {'есть' if 'ПОСЛЕ отчёта' in формы_блок else 'НЕТ — уборка не вынесена?'} · "
     f"командных форм: {формы_блок.count('python ')} (ждём 7)")

# ③ роль вне пула
rc3, out3 = brief(db, "CHROME")
case("③ вне пула → «твоих карточек нет» словами, блока пула нет",
     rc3 == 0 and "твоих карточек нет" in out3 and "TRACK-ZZBR:" not in out3)

# ④ пустое поле скиллов пула
con = sqlite3.connect(str(db))
con.execute("UPDATE tracks SET skills=NULL WHERE track_id='TRACK-ZZBR'")
con.commit()
con.close()
_, out4 = brief(db, "ZZB")
case("④ скиллы пула не названы → СЛОВАМИ", "НЕ НАЗВАНЫ" in out4)

# ⑤ протухшее умение скрыто и посчитано
_, out5 = brief(db, "ZZB")
case("⑤ протухшее умение НЕ в сводке, живое — в сводке, скрытое посчитано",
     "живое умение пробы" in out5 and "протухшее умение пробы" not in out5
     and "протухших скрыто 1" in out5)

# ⑥ источники ломаются порознь — наказ называет
for tbl, метка in [("role_rights", "права"), ("role_skill", "умения"),
                   ("tracks", "пул"), ("rules", "свод")]:
    db6 = stand / f"broke-{tbl}.db"
    shutil.copy(db, db6)
    con = sqlite3.connect(str(db6))
    con.execute(f"DROP TABLE {tbl}")
    con.commit()
    con.close()
    rc6, out6 = brief(db6, "ZZB")
    others = ("ФОРМЫ ВЫЗОВА" in out6)
    case(f"⑥ сломан источник «{метка}» ({tbl}) → назван «НЕ ПРОЧИТАН», остальное живёт",
         "НЕ ПРОЧИТАН" in out6 and others,
         [l for l in out6.splitlines() if "НЕ ПРОЧИТАН" in l][:1])

# ⑦ базы нет
rc7, out7 = brief(stand / "нет-такой.db", "ZZB")
case("⑦ базы нет → «НАКАЗ НЕ СОБРАН», не пустой наказ", rc7 != 0 and "НЕ СОБРАН" in out7)

# ═══ ⑨ СТРОКА О СЛУЖБЕ ПРОСМОТРА БАЗЫ (слово владельца 2026-10-04 07:38 UTC, чат PROTO:
# «реализовать правила в своде пакета плюс строка в стартовой сводке»). Три исхода — три
# РАЗНЫЕ строки, и каждый суд требует то, чего у соседнего исхода нет: иначе зелень одного
# ничего не говорит о другом. Правило ставится и снимается в ТОЙ ЖЕ копии стенда (db): суды
# на копии до этого места его не читают, а лишняя копия базы стоила бы стенду ещё ~80 МБ.
# ⚖️ Ссылка обязана вести к правилу, а не к отказу: в ⑨ названная строкой команда ЗАПУСКАЕТСЯ
# на той же копии и обязана напечатать подставное тело (класс карточки #124 — обещанный
# вызов, которого нет; класс карточки #647 — подсказка «--key X --show» к отсутствующему
# ключу). Файл каждой названной команды обязан существовать.
db9 = db


def named_tools_exist(line):
    paths = re.findall(r"python (\S+\.py)", line)
    return bool(paths) and all(Path(p).exists() for p in paths)


set_viewer_rule(db9, "active")
rc9, out9 = brief(db9, "ZZB")
l9 = viewer_lines(out9)
show9 = ""
if len(l9) == 1 and named_tools_exist(l9[0]):
    cmd9 = re.findall(r"python (\S+\.py)", l9[0])[0]
    p9 = subprocess.run([sys.executable, cmd9, "--key", VIEWER_RULE, "--show", "--db", str(db9)],
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                        env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    show9 = (p9.stdout or "") + (p9.stderr or "")
case("⑨ правило действует → ОДНА строка «ПЕРИСКОП» со ссылкой на правило, и ссылка ведёт к нему",
     rc9 == 0 and len(l9) == 1 and f"set-rule.py --key {VIEWER_RULE} --show" in l9[0]
     and "только чтение" in l9[0] and "rules-from-pack.py" not in l9[0]
     and named_tools_exist(l9[0]) and VIEWER_PROBE_BODY in show9,
     f"строк «ПЕРИСКОП»: {len(l9)} (ждём 1) · {l9[0][:150] if l9 else 'СТРОКИ НЕТ'} · "
     f"названная команда напечатала тело правила: {VIEWER_PROBE_BODY in show9}")

set_viewer_rule(db9, "absent")
rc9b, out9b = brief(db9, "ZZB")
l9b = viewer_lines(out9b)
case("⑨-бис ВСТРЕЧНЫЙ: правила в своде НЕТ → строка ведёт в пакет, к set-rule.py не зовёт",
     rc9b == 0 and len(l9b) == 1 and f"rules-from-pack.py --show {VIEWER_RULE}" in l9b[0]
     and f"--key {VIEWER_RULE}" not in l9b[0] and named_tools_exist(l9b[0]),
     f"строк «ПЕРИСКОП»: {len(l9b)} (ждём 1) · {l9b[0][:150] if l9b else 'СТРОКИ НЕТ'}")

set_viewer_rule(db9, "revoked")
rc9c, out9c = brief(db9, "ZZB")
l9c = viewer_lines(out9c)
case("⑨-тер правило СНЯТО → строка «снято» с пометкой о снятии, в пакет не зовёт",
     rc9c == 0 and len(l9c) == 1 and "снято" in l9c[0]
     and f"set-rule.py --key {VIEWER_RULE} --show" in l9c[0] and "rules-from-pack.py" not in l9c[0],
     f"строк «ПЕРИСКОП»: {len(l9c)} (ждём 1) · {l9c[0][:150] if l9c else 'СТРОКИ НЕТ'}")

# ── нарочные поломки на КОПИЯХ испытуемого в стенде: каждая обязана уронить РОВНО свой суд ──
# Р1 — поломка, какой она была бы в жизни: раздел перестаёт спрашивать свод и всегда
# печатает ссылку на правило (как соседний раздел ответов владельцу). Суд требует, чтобы
# ⑨-бис пал ПО СВОЕЙ ПРИЧИНЕ — строка есть и зовёт set-rule.py к отсутствующему ключу, — а
# не оттого, что раздел упал и строки нет вовсе (первая редакция поломки роняла раздел
# ошибкой, и суд был зелёным не по своей причине).
tool_r1 = broken_copy(stand, "r1",
                      "        st = conn.execute(\n"
                      "            \"SELECT status FROM rules WHERE rule_key='periscope-viewer'\").fetchone()\n",
                      "        st = (\"active\",)\n")
set_viewer_rule(db9, "absent")
_, out_r1 = brief(db9, "ZZB", tool=tool_r1)
l_r1 = viewer_lines(out_r1)
r1_would_pass = (len(l_r1) == 1 and f"rules-from-pack.py --show {VIEWER_RULE}" in l_r1[0]
                 and f"--key {VIEWER_RULE}" not in l_r1[0])
case("Р1 поломка «раздел не спрашивает свод» поймана: ⑨-бис на копии пал ПО СВОЕЙ причине "
     "(строка зовёт set-rule.py к отсутствующему ключу)",
     not r1_would_pass and len(l_r1) == 1 and f"set-rule.py --key {VIEWER_RULE}" in l_r1[0],
     f"под поломкой строка: {l_r1[0][:150] if l_r1 else 'СТРОКИ НЕТ'}")

tool_r2 = broken_copy(stand, "r2", "    section(\"просмотр базы\", periscope_view, out)\n",
                      "    pass\n")
set_viewer_rule(db9, "active")
rc_r2, out_r2 = brief(db9, "ZZB", tool=tool_r2)
l_r2 = viewer_lines(out_r2)
r2_would_pass = len(l_r2) == 1 and f"set-rule.py --key {VIEWER_RULE} --show" in l_r2[0]
case("Р2 поломка «раздел не вызывается» поймана: суд ⑨ на копии проваливается (строки нет, "
     "сводка при этом собралась без ошибок)",
     rc_r2 == 0 and not r2_would_pass and not l_r2 and "НЕ ПРОЧИТАН" not in out_r2,
     f"код копии {rc_r2} (ждём 0 — сводка собралась, только без строки) · строк «ПЕРИСКОП»: {len(l_r2)}")

# ═══ Карточка #444 (STUD, доказано четырьмя прогонами): прежний случай сравнивал
# размер и время правки ОБЩЕЙ базы — в неё пишут все роли (запись ~раз в 9 секунд),
# и цвет зависел от занятости соседей, а не от инструмента. Приёмщик, дважды
# получивший красное без вины, на третий раз пролистает его не глядя. Путь ①:
# судим СВОИ СЛЕДЫ — подсадных сущностей ЭТОЙ приёмки в живой базе быть не должно.
# Настоящая запись в живую оставит ровно их и покраснеет ПОИМЁННО; чужие записи
# не красят ничего.
con = sqlite3.connect(f"file:{LIVE_DB.as_posix()}?mode=ro", uri=True)
следы = []
for sql, имя in [
        ("SELECT COUNT(*) FROM roles WHERE role='ZZB'", "роль ZZB"),
        ("SELECT COUNT(*) FROM tracks WHERE track_id='TRACK-ZZBR'", "пул TRACK-ZZBR"),
        ("SELECT COUNT(*) FROM backlog WHERE title='часть сводки'", "карточка пробы"),
        ("SELECT COUNT(*) FROM role_skill WHERE skill LIKE '%умение пробы%'", "умения пробы"),
        ("SELECT COUNT(*) FROM rules WHERE body LIKE '%проба сводки: правило о службе%'",
         "правило пробы ⑨")]:
    n = con.execute(sql).fetchone()[0]
    if n:
        следы.append(f"{имя}: {n}")
con.close()
case("⑧ СВОИХ следов приёмки в живой базе нет (чужие записи не судятся)",
     not следы,
     f"НАЙДЕНО В ЖИВОЙ: {' · '.join(следы)}" if следы else
     "проверены роль/пул/карточка/умения/правило подсадки — живая база чиста ОТ НАШЕГО")

# ═══ Карточка #455 (TAXO): суд ⑧ ловил только ВСТАВЛЕННОЕ подсадкой и был слеп
# к её ПЕРВОМУ ходу — массовой ПОРЧЕ чужих строк. ⚠️ Уточнение по чтению кода
# (карточка #667): гасит активные наборы НА КОПИИ собственная строка подсадки
# ЭТОЙ приёмки чуть выше («UPDATE tracks SET status='paused' …», до вставки
# TRACK-ZZBR) — не механизм role-brief.py. Он открывает базу СТРОГО mode=ro и
# к tracks (как и к любой другой таблице) не пишет НИГДЕ в своём коде — сверено
# чтением role-brief.py и его соседа mezo_hints.py (тот пишет только hint_seen,
# и тоже отдельным соединением, когда основное — ro) целиком. Случай здесь судит
# не role-brief.py, а БЕЗОПАСНОСТЬ СОБСТВЕННОЙ подсадки этой приёмки: не утекла
# ли её правка на копии в живую базу.
#
# Судится РАЗНИЦЕЙ числа активных наборов живой базы ДО запуска этой приёмки и
# ПОСЛЕ (снимок — active_tracks_before, взят в самом начале файла), не абсолютным
# числом. Прежняя редакция судила «активных 0 → красное» — но на контуре, где
# активных наборов ЗАКОННО нет с самого начала (свежая сборка, карточка #667),
# это «0» неотличимо от «было N, подсадка погасила» и красит КАЖДЫЙ прогон ложно.
# Разница не путает эти два мира: 0→0 (без порчи) проходит, N→0 (порча) красит.
# ⚖️ ГРАНИЦА вслух (унаследована от карточки #455): редкий чужой ход ролью рядом
# по времени смог бы дать ложную разницу — он ГОВОРИТ ПОИМЁННО (было/стало), и
# приёмщик разберётся; тихая порча наборов девяти ролей дороже одной ложной тревоги.
active_tracks_after = live_active_tracks()
case("⑧-бис ПОРЧА чужих строк: число активных наборов живой базы НЕ изменилось (карточка #455)",
     active_tracks_after == active_tracks_before,
     f"было активных {active_tracks_before}, стало {active_tracks_after} — ход "
     f"подсадки мог исполниться в ЖИВОЙ базе" if active_tracks_after != active_tracks_before
     else f"активных наборов живой базы без изменений: {active_tracks_before} → {active_tracks_after}")

print(f"\nИТОГ: {OK}/{OK + FAIL}")
raise SystemExit(mezo_stand.finish(0 if FAIL == 0 else 1))
