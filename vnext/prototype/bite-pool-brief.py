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
"""
import os
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


def brief(db, role):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, str(ИСПЫТУЕМЫЙ),
                        "--role", role, "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


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
        ("SELECT COUNT(*) FROM role_skill WHERE skill LIKE '%умение пробы%'", "умения пробы")]:
    n = con.execute(sql).fetchone()[0]
    if n:
        следы.append(f"{имя}: {n}")
con.close()
case("⑧ СВОИХ следов приёмки в живой базе нет (чужие записи не судятся)",
     not следы,
     f"НАЙДЕНО В ЖИВОЙ: {' · '.join(следы)}" if следы else
     "проверены роль/пул/карточка/умения подсадки — живая база чиста ОТ НАШЕГО")

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
