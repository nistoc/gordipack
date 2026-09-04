# -*- coding: utf-8 -*-
r"""ПРИЁМКА второго ВИДА предмета в check-retired-mechanism.py — снятое ПРЕДПИСАНИЕ.

Механизм @PROTO ловил снятый МЕХАНИЗМ по имени (`--md`). Запись, добавленная @COORD
2026-08-09, ловит снятое ПРЕДПИСАНИЕ («push только по слову владельца») — у него имени нет,
оно живёт разными словами, и ищется набором ФОРМ.

⚠️ Отдельная приёмка, а не случаи в чужой: у нового вида свои способы соврать, и главный —
СТЕРЕТЬ ДЕЙСТВУЮЩЕЕ. Запрет на отправку снят, запрет на РАЗРУШАЮЩЕЕ (force push, drop,
reset --hard) НЕ снят — а формы у них соседние. Признак, не различающий их, вычистит
живую защиту, и выглядеть это будет как успешная уборка.
"""
import os
import re
import shutil
import sqlite3
import subprocess
import sys

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

HERE = os.path.dirname(os.path.abspath(__file__))
# Испытуемый: --check → РЯДОМ → тулкит. «Рядом» добавлено @PROTO 09.08: приёмка живёт
# в ДВУХ каталогах (рабочий и шаблон), а искала только от рабочего — из шаблона печатала
# «ИСПЫТУЕМОГО НЕТ» при живом соседе в том же каталоге. Соседняя приёмка того же признака
# уже искала рядом; два искателя одного предмета разошлись молча.
CHECK = os.path.join(HERE, "check-retired-mechanism.py")
if not os.path.exists(CHECK):
    CHECK = os.path.abspath(os.path.join(HERE, "..", ".mezosync", "scripts",
                                         "check-retired-mechanism.py"))
    if not os.path.exists(CHECK):
        CHECK = os.path.abspath(os.path.join(HERE, "..", "..", "scripts",
                                             "check-retired-mechanism.py"))
for i, a in enumerate(sys.argv):
    if a == "--check" and i + 1 < len(sys.argv):
        CHECK = sys.argv[i + 1]
if not os.path.exists(CHECK):
    print(f"⛔ ИСПЫТУЕМОГО НЕТ: {CHECK} — это отказ мерить, а не «чисто»")
    sys.exit(2)

RULE_MD = "md-to-sqlite-phased-cutover"
RULE_PUSH = "no-push-without-owner"

# ⚡ ВЕРСИЯ ПРАВИЛА ДЛЯ ПЕСОЧНИЦЫ БЕРЁТСЯ ИЗ ИСПЫТУЕМОГО, А НЕ ВПЕЧАТЫВАЕТСЯ ЗДЕСЬ.
# 🩸 Оплачено 2026-09-04 15:26 UTC. Здесь стояло `push_version=2` — ровно та версия,
# что была впечатана в перечень испытуемого. Пока оба числа совпадали, приёмка давала
# 9/9. Стои́ло поднять сверку в перечне до v4 (правило в базе давно v4) — и приёмка
# упала до 6/9, объявив мою ВЕРНУЮ правку поломкой.
# ⚖️ И хуже того, в обратную сторону: пока перечень отставал от свода, испытуемый на
# ЖИВОЙ базе всегда отвечал «перечень устарел» (код 2), а приёмка ждала кода 1 и... тоже
# зеленела — потому что в ЕЁ песочнице стояла старая версия. Оба конца были согласованы
# друг с другом и оба разошлись с жизнью.
# ⇒ КЛАСС: ДВА ВПЕЧАТАННЫХ ЧИСЛА, СВЕРЯЕМЫЕ ДРУГ С ДРУГОМ, ДАЮТ ЗЕЛЁНОЕ НАВСЕГДА —
#   и перестают говорить о предмете вовсе. Число теперь ОДНО, и живёт в перечне.
def _версия_сверки_из_испытуемого() -> int:
    """Прочитать «версия_сверки» правила о push прямо из перечня испытуемого."""
    try:
        текст = open(CHECK, encoding="utf-8").read()
        # берём блок записи про push и число из него: перечень — обычный литерал
        кусок = текст.split(f'"правило": "{RULE_PUSH}"', 1)
        if len(кусок) > 1:
            m = re.search(r'"версия_сверки":\s*(\d+)', кусок[1])
            if m:
                return int(m.group(1))
    except OSError:
        pass
    # ⛔ Не молчим и не подставляем «разумное»: неизвестная версия — отказ мерить.
    print("⛔ НЕ ПРОЧЛА «версия_сверки» из перечня испытуемого — это отказ мерить, "
          "а не «возьму двойку». Подставленное число вернуло бы ту самую пару\n"
          "   впечатанных чисел, ради которой эта функция и написана.")
    sys.exit(2)


ВЕРСИЯ_СВЕРКИ = _версия_сверки_из_испытуемого()
cases, bad, differ = [], 0, 0


def build_db(path, push_version=ВЕРСИЯ_СВЕРКИ, trace=True):
    """trace — есть ли у правила след в журнале решений этого контура.

    🪤 РАЗЛИЧЕНИЕ, ВВЕДЁННОЕ 18.08 ПРИ ЧИСТКЕ ПОСЕВА. «Правила нет» бывает ДВУХ родов:
    правило ИСЧЕЗЛО (было и пропало — перечень отстал, это отказ мерить) либо ЕГО ЗДЕСЬ
    НЕ БЫЛО ВОВСЕ (новая команда не наследует чужую историю перехода — сверять нечего).
    Различаются следом в журнале. Приёмка обязана держать оба рода, иначе она требует
    красного у любого свежего контура — ровно то, что мы тогда и чинили.
    """
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT, body TEXT,"
                " locked_by TEXT, version INTEGER)")
    con.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, target TEXT)")
    con.execute("INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,?)",
                (RULE_MD, "тело", "owner", 5))
    if push_version is not None:
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,?)",
                    (RULE_PUSH, "надгробие: запрет снят", "owner", push_version))
    if trace:
        con.execute("INSERT INTO audit_log (target) VALUES (?)", (RULE_PUSH,))
    con.commit()
    con.close()


SOURCES = ["read-phoenix.py", "write-message.py", "unsaved.py", "backup-db.py",
           "export-channels.py", "guard-scripts-drift.py", "guard-all.py",
           "read-messages.py", "save-phoenix.py"]


def build_src(root, unsaved_lines):
    os.makedirs(root, exist_ok=True)
    for name in SOURCES:
        body = unsaved_lines if name == "unsaved.py" else ["# пусто"]
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            f.write("\n".join(body) + "\n")


def run(lines, push_version=ВЕРСИЯ_СВЕРКИ, trace=True):
    tmp = str(mezo_stand.new("bite-presc-"))
    db = os.path.join(tmp, "c.db")
    root = os.path.join(tmp, "src")
    build_db(db, push_version, trace)
    build_src(root, lines)
    r = subprocess.run([sys.executable, CHECK, "--db", db, "--root", root, "--only", "no-push-without-owner"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    mezo_stand.release(tmp)  # уборка отложена до исхода прогона
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def case(title, ok, why, is_differ=False):
    global bad, differ
    cases.append((title, ok, why))
    if not ok:
        bad += 1
    if is_differ:
        differ += 1


# ① ПРЕДПИСАНИЕ БЕЗ ПОМЕТКИ — краснеет и называет источник
out, code = run(['print("   ② лечит только слово владельца (push) — роль не может")'])
case("① предписание снятому запрету — КРАСНОЕ, источник назван",
     code == 1 and "unsaved.py" in out, f"код {code}", True)

# ② ВСТРЕЧНЫЙ: того же нет — зелёное. Без него ① не доказывает умения РАЗЛИЧАТЬ
out, code = run(['print("   ② лечит роль сама: отправка разрешена без отдельного слова")'])
case("② предписания нет — ЗЕЛЁНОЕ (встречный к ①)", code == 0, f"код {code}", True)

# ③ ПОМЕТКА СНЯТИЯ В ТОЙ ЖЕ СТРОКЕ — история разрешена
out, code = run(['# ⚰️ было «push только по слову» — СНЯТО владельцем 08.08 15:58:46 UTC'])
case("③ помеченная строка предписанием НЕ считается", code == 0, f"код {code}", True)

# ④ 🔴 ГЛАВНЫЙ: ДЕЙСТВУЮЩАЯ ЗАЩИТА НЕ ДОЛЖНА БЫТЬ СТЁРТА.
#    «force push только по живому слову» — правило rule8-destructive НЕ отозвано.
out, code = run(['print("⛔ force push — только по живому слову владельца")'])
case("④ запрет на РАЗРУШАЮЩЕЕ не считается пережитком (rule8 жив)", code == 0,
     f"код {code}: {out.strip()[:120]}", True)

# ⑤ ВСТРЕЧНЫЙ к ④: та же форма, но про обычную отправку — обязана краснеть.
#    Без этой пары ④ мог бы зеленеть просто потому, что признак ослеп на всё сразу.
out, code = run(['print("⛔ push — только по живому слову владельца")'])
case("⑤ обычная отправка в той же форме — КРАСНОЕ (встречный к ④)", code == 1,
     f"код {code}", True)

# ⑥ ПРАВИЛО ПЕРЕПИСАНО — «перечень устарел», источники не обвиняются
# ⑥ версия в песочнице ВЫШЕ той, против которой сверялся перечень — на единицу,
#    чтобы случай оставался про «правило переписали», а не про конкретное число
out, code = run(['print("   ② лечит только слово владельца (push)")'],
                push_version=ВЕРСИЯ_СВЕРКИ + 1)
case("⑥ версия правила выросла — ПЕРЕЧЕНЬ УСТАРЕЛ (код 2), источник не назван виновным",
     code == 2 and "ПЕРЕЧЕНЬ УСТАРЕЛ" in out and "unsaved.py:" not in out,
     f"код {code}", True)

# ⑦ ПРАВИЛО ИСЧЕЗЛО (след в журнале есть) — отказ мерить, а не «чисто» (встречный к ⑥)
out, code = run(['# пусто'], push_version=None)
case("⑦ правило ИСЧЕЗЛО из свода — отказ мерить, а не зелёное (встречный к ⑥)",
     code == 2 and "ПЕРЕЧЕНЬ УСТАРЕЛ" in out, f"код {code}", True)

# ⑦-бис ВСТРЕЧНЫЙ к ⑦ И ОХРАНА РЕШЕНИЯ 18.08: правила здесь НЕ БЫЛО ВОВСЕ.
#      У новой команды нет нашей истории перехода. Зелёное — но НЕ молчаливое: механизм
#      обязан сказать «сверять нечего», иначе роль прочтёт это как проверенную чистоту.
out, code = run(['# пусто'], push_version=None, trace=False)
case("⑦-бис правила здесь НЕ БЫЛО ВОВСЕ — зелёное, но СКАЗАННОЕ вслух",
     code == 0 and "не было вовсе" in out and "сверять нечего" in out,
     f"код {code}; два разных «нет» различаются следом в журнале, а не молчанием", True)

# ⑧ ПРОЗА О ПРОШЛОМ не должна краснеть: замер показал 1 ложное из 4 у первой редакции форм
out, code = run(['# разовое разрешение на push я сам дважды спутал — потрачено или нет'])
case("⑧ проза о прошлом без предписания — ЗЕЛЁНОЕ", code == 0,
     f"код {code}: {out.strip()[:120]}", True)

print("🔬 ПРИЁМКА: снятое ПРЕДПИСАНИЕ (второй вид предмета)")
print(f"   испытуемый: {CHECK}")
for t, ok, why in cases:
    print(f"   {'✅' if ok else '🔴'} {t}" + (f"   ← {why}" if not ok else ""))
print(f"   ИТОГ: {len(cases) - bad}/{len(cases)} · различающих {differ}")
sys.exit(mezo_stand.finish(1 if bad else 0))
