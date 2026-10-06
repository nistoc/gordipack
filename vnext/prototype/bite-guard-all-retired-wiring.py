# -*- coding: utf-8 -*-
r"""ПРИЁМКА ВРЕЗКИ: guard-all зовёт признак «источники не учат снятому» ПРАВИЛЬНО.

Приёмка самого признака — bite-retired-mechanism.py (@PROTO) и bite-retired-prescription.py.
Здесь проверяется не признак, а ВРЕЗКА: её собственные способы соврать.

⚠️ ЗАЧЕМ ОТДЕЛЬНО. Обе ошибки, найденные при этой врезке, лежали НЕ в признаке:
  ① признак звался БЕЗ аргументов ⇒ при прогоне всего набора по копии он читал ЖИВУЮ базу.
     Испытываешь одно — отвечает другое, и оба ответа выглядят одинаково уверенно;
  ② исчезновение правила роняло ВЕСЬ прогон (найдено @PROTO нарочной поломкой, записка #3470):
     восемь проверок после не выполнялись, а код 1 читался как обычное «есть красное».
🎯 Общее у них: приёмка компонента зелена, а связка врёт. Компонент и его врезка — разные предметы.

🩹 ПРАВКА (карточка #667, пустой контур pcK). Случаи ① и ② молча полагались на то, что
ЖИВАЯ база сама несёт правило «md-to-sqlite-phased-cutover» версии 5 и его след в
audit_log — это верно для контура Atlas, но НЕ для только что собранного контура:
там этой конкретной истории попросту нет. Отсюда и провал был не о признаке, а о
пустых данных: снятое правило «исчезало» в НИКУДА, а не из прежде-бывшего состояния,
и check-retired-mechanism.py законно отвечал «запись НЕПРИМЕНИМА» вместо «ПЕРЕЧЕНЬ
УСТАРЕЛ». Теперь копии db1/db2 заводят эту запись СВОЕЙ РУКОЙ (seed_rule/seed_audit_trace)
перед мутацией — проверка перестаёт зависеть от того, какой контур её запускает.
"""
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

GUARD = str(mezo_paths.live_scripts() / "guard-all.py")
LIVE = mezo_paths.live_db()
cases, bad = [], 0


def check(name, ok, detail=""):
    global bad
    cases.append((name, ok, detail))
    if not ok:
        bad += 1


def run_on(db):
    r = subprocess.run([sys.executable, GUARD, "--full", "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


RULE_KEY = "md-to-sqlite-phased-cutover"


def verified_version():
    """Отметка сверки записи RULE_KEY — из перечня check-retired-mechanism.py рядом с
    guard-all.py, а не числом здесь (2026-10-06: число 5 стояло рукой и отстало, когда
    перечень сверили против v6). Не прочли — отказ мерить, а не «есть красное»."""
    import importlib.util
    path = pathlib.Path(GUARD).parent / "check-retired-mechanism.py"
    spec = importlib.util.spec_from_file_location("check_retired_mechanism", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for item in module.RETIRED:
        if item.get("правило") == RULE_KEY:
            return item["версия_сверки"]
    print(f"⛔ В ПЕРЕЧНЕ {path} НЕТ ЗАПИСИ «{RULE_KEY}» — это отказ мерить, а не «чисто»")
    sys.exit(2)


VERIFIED = verified_version()


def seed_rule(db, version):
    """Гарантировать в КОПИИ запись правила RULE_KEY с заданной версией — своя подставная
    запись (карточка #667, Предпочтение 1), а не надежда на то, что её принёс контур сам.
    На пустом контуре такой истории может не быть вовсе; UPSERT работает одинаково и
    когда запись уже есть (живой контур), и когда её нет совсем (pcK)."""
    c = sqlite3.connect(db)
    c.execute(
        "INSERT INTO rules (rule_key, body, version) VALUES (?, ?, ?) "
        "ON CONFLICT(rule_key) DO UPDATE SET version=excluded.version",
        (RULE_KEY, "подставное тело правила для приёмки врезки guard-all "
                   "(bite-guard-all-retired-wiring.py)", version),
    )
    c.commit()
    c.close()


def seed_audit_trace(db, rule_key):
    """Гарантировать в audit_log КОПИИ след по правилу — иначе check-retired-mechanism.py
    не отличит «правило ИСЧЕЗЛО» от «правила здесь не было вовсе» и промолчит (та же беда
    #667: пустые данные свежего контура, а не поломка признака)."""
    c = sqlite3.connect(db)
    c.execute(
        "INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?, ?, ?, ?)",
        ("PROTO", "update_rule", rule_key, "подставной след для приёмки врезки guard-all"),
    )
    c.commit()
    c.close()


tmp = mezo_stand.new("wiring-")

# ── ① ПРАВИЛО ИСЧЕЗЛО: набор обязан доработать до конца и назвать отказ отказом
db1 = tmp / "no-rule.db"
mezo_stand.snapshot_db(LIVE, db1)
seed_rule(db1, VERIFIED)             # своя запись: правило БЫЛО версии сверки — прежде чем исчезнуть
seed_audit_trace(db1, RULE_KEY)      # и его исчезновение обязано иметь след, а не выглядеть «не было вовсе»
c = sqlite3.connect(db1)
c.execute("DELETE FROM rules WHERE rule_key='md-to-sqlite-phased-cutover'")
c.commit()
c.close()
out1, code1 = run_on(db1)

check("① исчезновение правила НЕ роняет прогон трассировкой", "Traceback" not in out1,
      out1.strip()[-200:])
check("① сказано «ПЕРЕЧЕНЬ УСТАРЕЛ» — отказ мерить, а не «есть красное»",
      "ПЕРЕЧЕНЬ УСТАРЕЛ" in out1 or "устарел" in out1.lower(), out1.strip()[-200:])
check("① источники НЕ названы виновными (чинить проверку, а не их)",
      "read-phoenix.py:" not in out1, "")
check("① проверки ПОСЛЕ этой выполнились",
      "журнал схемы" in out1 and "зеркало правил" in out1, "")
check("① вердиктов много — набор не оборвался",
      len(re.findall(r"^[✅⛔⚠️⏭️]", out1, re.M)) >= 15, "")

# ── ② ПРОГОН ПО КОПИИ ДОЛЖЕН МЕРИТЬ КОПИЮ. Правило переписываем ТОЛЬКО в копии:
#    если признак читает живую базу, он этой подмены не заметит и промолчит.
db2 = tmp / "bumped.db"
mezo_stand.snapshot_db(LIVE, db2)
seed_rule(db2, VERIFIED)             # базовая версия ДО правки — та же, что в RETIRED["версия_сверки"]
c = sqlite3.connect(db2)
c.execute("UPDATE rules SET version = version + 7 "
          "WHERE rule_key='md-to-sqlite-phased-cutover'")
c.commit()
c.close()
out2, code2 = run_on(db2)
check("② прогон по КОПИИ мерит копию, а не живую базу (версия правила изменена только в ней)",
      "УСТАРЕЛ" in out2 or "переписано" in out2,
      "признак промолчал ⇒ он прочитал ЖИВУЮ базу вместо заказанной")

# ── ③ ВСТРЕЧНЫЙ к ②: на нетронутой копии — тихо. Без него ② зеленел бы от общей паники.
db3 = tmp / "clean.db"
mezo_stand.snapshot_db(LIVE, db3)
out3, code3 = run_on(db3)
check("③ на нетронутой копии признак ЗЕЛЁН (встречный к ②)",
      "источники не учат снятому" in out3 and "УСТАРЕЛ" not in out3,
      out3.strip()[-200:])

print("🔬 ПРИЁМКА ПРОВЕРКИ: «источники не учат снятому» в guard-all")
for name, ok, detail in cases:
    print(f"   {'✅' if ok else '🔴'} {name}" + (f"   ← {detail}" if detail and not ok else ""))
print(f"   ИТОГ: {len(cases) - bad}/{len(cases)}")
mezo_stand.release(tmp)  # уборка отложена до исхода прогона
sys.exit(mezo_stand.finish(1 if bad else 0))
