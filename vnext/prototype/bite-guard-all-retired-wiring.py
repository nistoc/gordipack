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
"""
import pathlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

GUARD = str(mezo_paths.live_scripts() / "guard-all.py")
LIVE = mezo_paths.live_db()
cases, bad = [], 0


def check(name, ok, detail=""):
    global bad
    cases.append((name, ok, detail))
    if not ok:
        bad += 1


def run_on(db):
    r = subprocess.run([sys.executable, GUARD, "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


tmp = pathlib.Path(tempfile.mkdtemp(prefix="wiring-"))

# ── ① ПРАВИЛО ИСЧЕЗЛО: набор обязан доработать до конца и назвать отказ отказом
db1 = tmp / "no-rule.db"
shutil.copy2(LIVE, db1)
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
shutil.copy2(LIVE, db2)
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
shutil.copy2(LIVE, db3)
out3, code3 = run_on(db3)
check("③ на нетронутой копии признак ЗЕЛЁН (встречный к ②)",
      "источники не учат снятому" in out3 and "УСТАРЕЛ" not in out3,
      out3.strip()[-200:])

print("🔬 ПРИЁМКА ПРОВЕРКИ: «источники не учат снятому» в guard-all")
for name, ok, detail in cases:
    print(f"   {'✅' if ok else '🔴'} {name}" + (f"   ← {detail}" if detail and not ok else ""))
print(f"   ИТОГ: {len(cases) - bad}/{len(cases)}")
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(1 if bad else 0)
