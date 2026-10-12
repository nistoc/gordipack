# -*- coding: utf-8 -*-
r"""ПРИЁМКА второго ВИДА предмета в check-retired-mechanism.py — снятое ПРЕДПИСАНИЕ.

Механизм @PROTO ловил снятый МЕХАНИЗМ по имени (`--md`). Запись, добавленная @COORD
2026-08-09, ловит снятое ПРЕДПИСАНИЕ («push только по слову владельца») — у него имени нет,
оно живёт разными словами, и ищется набором ФОРМ.

⚠️ Отдельная приёмка, а не случаи в чужой: у нового вида свои способы соврать, и главный —
СТЕРЕТЬ ДЕЙСТВУЮЩЕЕ. Запрет на отправку снят, запрет на РАЗРУШАЮЩЕЕ (force push, drop,
reset --hard) НЕ снят — а формы у них соседние. Признак, не различающий их, вычистит
живую защиту, и выглядеть это будет как успешная уборка.

КАРТОЧКА #715 (находки контура .onto 2026-10-12 12:53 UTC, замечания 1 и 3):
  · запись включалась по НОМЕРУ версии правила; у .onto правило стало v4 с текстом пакета
    (запрет действует), и проверка провалилась на верной строке. Теперь снятие читается полем
    статуса правила, а без поля — пометкой о снятии в начале текста; номер не сравнивается.
    Прежний случай ⑥ («версия выросла — ПЕРЕЧЕНЬ УСТАРЕЛ») снят НАМЕРЕННО: рост номера у
    снятого правила больше не значит, что перечень отстал. На его месте ⑥а–⑥в.
  · час и чат наследника печатались словом владельца контура-автора, впечатанным в запись;
    теперь — из строки правила в базе испытуемого контура (⑨-бис), и час снятия в красной
    строке — тоже (⑥в).
  Нарочные поломки — в копии испытуемого на стенде (на диск рядом с испытуемым ничего не
  пишется): П1 «снятие снова не спрашивает базу» красит ровно ⑥а/⑥б · П2 «час наследника
  снова впечатан» — ровно ⑨-бис · П3 «час снятия снова из записи» — ровно ⑥в.
"""
import os
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
RULE_FREEZE = "gitlab-push-frozen"   # наследник: запрет отправки вернулся 2026-09-25

# ⚖️ НОМЕР ВЕРСИИ В ПЕСОЧНИЦЕ — ПРОСТО ДАННЫЕ (карточка #715). До неё здесь стояла функция,
# читавшая «версия_сверки» записи о push из перечня испытуемого: проверка сравнивала номер
# правила с этим числом, и два впечатанных числа, сверяемые друг с другом, давали зелёное
# навсегда (оплачено 2026-09-04 15:26 UTC). Теперь испытуемый номер у этой записи не
# сравнивает вовсе — снятие читается полем статуса либо пометкой о снятии в начале текста.
# 4 — номер, на котором споткнулся контур .onto: тот же, что у эталона, а текст другой.
PUSH_VERSION = 4
TOMBSTONE_BODY = ("⛔ ОТОЗВАНО 2026-08-08 15:58 UTC · решил: owner\n"
                  "Текст ниже оставлен как след прежнего решения, а НЕ как приказ.\n"
                  "push только по слову владельца")
PACK_BODY = "отправка — по слову владельца; владелец вправе снять умолчание"  # текст пакета, запрет жив
STAND_REVOKED_AT = "2026-10-01 09:00 UTC"          # час снятия в базе СТЕНДА, не эталона
STAND_HEIR_SOURCE = "чат стенда 2026-10-04 17:58 UTC"  # слово о наследнике в базе СТЕНДА
DONOR_HOURS = ("2026-08-08 15:58:46", "2026-09-25 11:02:36")  # часы эталона в записи перечня
cases, bad, differ = [], 0, 0


def build_db(path, push_version=PUSH_VERSION, trace=True, frozen=None, push="tombstone"):
    """trace — есть ли у правила след в журнале решений этого контура.

    🪤 РАЗЛИЧЕНИЕ, ВВЕДЁННОЕ 18.08 ПРИ ЧИСТКЕ ПОСЕВА. «Правила нет» бывает ДВУХ родов:
    правило ИСЧЕЗЛО (было и пропало — перечень отстал, это отказ мерить) либо ЕГО ЗДЕСЬ
    НЕ БЫЛО ВОВСЕ (новая команда не наследует чужую историю перехода — сверять нечего).
    Различаются следом в журнале. Приёмка обязана держать оба рода, иначе она требует
    красного у любого свежего контура — ровно то, что мы тогда и чинили.

    push — как правило о push записано в базе стенда (карточка #715):
      tombstone .... снято пометкой о снятии в начале текста; поле статуса — по frozen
      pack-active .. текст пакета, запрет ДЕЙСТВУЕТ (как у .onto); поле статуса — по frozen
      field ........ снято ПОЛЕМ статуса (с часом и рукой), текст без пометки; поле есть всегда
    frozen — правило-наследник (2026-09-25) и поле статуса у всех правил: 'active' либо
    'revoked'; None — поля статуса нет (кроме push="field").
    """
    with_field = frozen is not None or push == "field"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT, body TEXT,"
                " locked_by TEXT, version INTEGER"
                + (", status TEXT, revoked_at TEXT, revoked_by TEXT, updated_at TEXT,"
                   " authorized TEXT, source_ref TEXT" if with_field else "") + ")")
    con.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY, target TEXT)")
    con.execute("INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,?)",
                (RULE_MD, "тело", "owner", 5))
    if push_version is not None:
        body = {"tombstone": TOMBSTONE_BODY, "pack-active": PACK_BODY,
                "field": "push только по слову владельца"}[push]
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,?)",
                    (RULE_PUSH, body, "owner", push_version))
        if with_field:
            revoked = push in ("tombstone", "field")
            con.execute("UPDATE rules SET status=?, revoked_at=?, revoked_by=? WHERE rule_key=?",
                        ("revoked" if revoked else "active",
                         STAND_REVOKED_AT if revoked else None,
                         "owner" if revoked else None, RULE_PUSH))
    if trace:
        con.execute("INSERT INTO audit_log (target) VALUES (?)", (RULE_PUSH,))
    if frozen is not None:
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version, status, updated_at,"
                    " authorized, source_ref) VALUES (?,?,?,?,?,?,?,?)",
                    (RULE_FREEZE, "запрет отправки в GitLab", "owner", 2, frozen,
                     "2026-10-04 18:00:00", "владелец стенда", STAND_HEIR_SOURCE))
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


def run(lines, push_version=PUSH_VERSION, trace=True, frozen=None, push="tombstone", broken=None):
    """broken — (что заменить, на что) в КОПИИ испытуемого на стенде; соседи испытуемого
    (rule_status.py, mezo_paths.py) берутся из его каталога через PYTHONPATH."""
    tmp = str(mezo_stand.new("bite-presc-"))
    db = os.path.join(tmp, "c.db")
    root = os.path.join(tmp, "src")
    build_db(db, push_version, trace, frozen, push)
    build_src(root, lines)
    target, env = CHECK, mezo_stand.stand_env(tmp)  # карточка #613: env закреплён за стендом
    if broken is not None:
        src = open(CHECK, encoding="utf-8").read()
        old, new = broken
        if src.count(old) != 1:
            # Случай поломки проваливается со словами, а прогон идёт дальше: на прежней версии
            # испытуемого якоря нет — итог обязан показать ВСЕ случаи, а не оборваться на первом.
            mezo_stand.release(tmp)
            return (f"⛔ НЕ ЗАПУСТИЛСЯ: строка-цель поломки найдена {src.count(old)} раз (нужна "
                    f"одна) — испытуемое изменилось, поломку надо пересмотреть: {old[:80]!r}"), None
        target = os.path.join(tmp, "check-retired-mechanism.py")
        with open(target, "w", encoding="utf-8") as f:
            f.write(src.replace(old, new))
        # среда — снова прямо от стенда: проверка check-acceptance-env.py видит stand_env( в
        # присваивании, а пересборку dict(env, …) не прослеживает (нашёл общий прогон эталона 12.10)
        env = mezo_stand.stand_env(tmp, PYTHONPATH=os.path.dirname(os.path.abspath(CHECK)))
    r = subprocess.run([sys.executable, target, "--db", db, "--root", root, "--only", "no-push-without-owner"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
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

# ⑥ (до карточки #715: «версия выросла — ПЕРЕЧЕНЬ УСТАРЕЛ») снят намеренно — см. шапку.
# ⑥а 🔴 НАХОДКА .onto: тот же номер версии, что у эталона, а правило ДЕЙСТВУЕТ (текст пакета,
#     поле статуса «active»). Снятия здесь не было — источники не судятся, строка верна.
TEACH = ['print("   ② лечит только слово владельца (push) — роль не может")']
out, code = run(TEACH, frozen="revoked", push="pack-active")
case("⑥а тот же номер версии, правило действует по полю статуса — НЕПРИМЕНИМА, источник не судится",
     code == 0 and "НЕПРИМЕНИМА" in out and "unsaved.py:" not in out,
     f"код {code}: {out.strip()[:160]}", True)

# ⑥б то же в базе БЕЗ поля статуса: текст без пометки о снятии — правило действует
out, code = run(TEACH, push="pack-active")
case("⑥б тот же номер, поля статуса нет, пометки о снятии нет — НЕПРИМЕНИМА",
     code == 0 and "НЕПРИМЕНИМА" in out and "unsaved.py:" not in out,
     f"код {code}: {out.strip()[:160]}", True)

# ⑥в ВСТРЕЧНЫЙ к ⑥а: правило снято ПОЛЕМ статуса, номер далеко за прежней отметкой (v9),
#     текст без пометки — судится (поле сильнее текста, номер не судья), и час снятия в
#     красной строке — из базы стенда, а не впечатанный час эталона.
out, code = run(TEACH, push_version=9, push="field")
case("⑥в снято полем статуса при v9 — судится, источник назван, час снятия из базы контура",
     code == 1 and "unsaved.py" in out and STAND_REVOKED_AT in out
     and not any(h in out for h in DONOR_HOURS),
     f"код {code}: {out.strip()[:200]}", True)

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

# ⑨ ⏸ ПРЕДПИСАНИЕ ВЕРНУЛОСЬ (слово владельца 2026-09-25 11:02:36 UTC, правило-наследник
#    gitlab-push-frozen): та же строка, что краснеет в ⑤, не судится — и это СКАЗАНО строкой.
#    Без паузы признак учил бы роли стирать действующий запрет владельца.
out, code = run(['print("⛔ push — только по живому слову владельца")'], frozen="active")
case("⑨ наследник действует — признак НЕ СУДИТ и говорит это словом",
     code == 0 and "НЕ СУЖУ" in out and RULE_FREEZE in out and "unsaved.py:" not in out,
     f"код {code}: {out.strip()[:160]}", True)

# ⑨-бис 🔴 НАХОДКА .onto (замечание 3): кто и когда завёл наследника — из строки правила в
#     базе испытуемого контура, а не впечатанное слово владельца контура-автора.
out, code = run(['print("⛔ push — только по живому слову владельца")'], frozen="active")
case("⑨-бис час и источник наследника — из базы контура, часа эталона в выводе нет",
     code == 0 and STAND_HEIR_SOURCE in out and not any(h in out for h in DONOR_HOURS),
     f"код {code}: {out.strip()[:200]}", True)

# ⑩ ВСТРЕЧНЫЙ к ⑨: наследник СНЯТ (поле статуса 'revoked') — признак снова судит.
#    Без этой пары ⑨ зеленел бы и у признака, ослепшего на всё сразу.
out, code = run(['print("⛔ push — только по живому слову владельца")'], frozen="revoked")
case("⑩ наследник снят — признак снова судит, та же строка КРАСНАЯ (встречный к ⑨)",
     code == 1 and "unsaved.py" in out and "НЕ СУЖУ" not in out, f"код {code}", True)

# ── НАРОЧНЫЕ ПОЛОМКИ карточки #715 — в копии испытуемого на стенде. Каждая обязана
#    провалить ровно свой случай: тот же прогон, что у случая, ждёт ответа прежней версии.
P1 = ('            if rule_status.rule_in_force(conn, item["правило"]):\n',
      '            if False:  # ПОЛОМКА П1: снятие снова не спрашивает базу контура\n')
out, code = run(TEACH, frozen="revoked", push="pack-active", broken=P1)
out_b, code_b = run(TEACH, push="pack-active", broken=P1)
case("П1 «снятие не спрашивает базу» красит ровно ⑥а и ⑥б: строка судится, источник назван",
     code == 1 and "unsaved.py" in out and code_b == 1 and "unsaved.py" in out_b,
     f"коды под поломкой: ⑥а {code} · ⑥б {code_b} (под верным кодом — 0 и 0)"
     + (f"; {out.strip()[:160]}" if code is None else ""), True)

P2 = ("({heir_origin(conn, heir)})", "(слово владельца 2026-09-25 11:02:36 UTC, чат PROTO)")
out, code = run(['print("⛔ push — только по живому слову владельца")'], frozen="active",
                broken=P2)
case("П2 «час наследника снова впечатан» красит ровно ⑨-бис: в выводе час эталона",
     code == 0 and "НЕ СУЖУ" in out and STAND_HEIR_SOURCE not in out
     and DONOR_HOURS[1] in out,
     f"код {code}: {out.strip()[:200]}", True)

P3 = ("снято: {revoke_origin(conn, item['правило'])}", "снято: {item['снято']}")
out, code = run(TEACH, push_version=9, push="field", broken=P3)
case("П3 «час снятия снова из записи» красит ровно ⑥в: в красной строке час эталона",
     code == 1 and "unsaved.py" in out and STAND_REVOKED_AT not in out
     and DONOR_HOURS[0] in out,
     f"код {code}: {out.strip()[:200]}", True)

print("🔬 ПРИЁМКА: снятое ПРЕДПИСАНИЕ (второй вид предмета)")
print(f"   испытуемый: {CHECK}")
for t, ok, why in cases:
    print(f"   {'✅' if ok else '🔴'} {t}" + (f"   ← {why}" if not ok else ""))
print(f"   ИТОГ: {len(cases) - bad}/{len(cases)} · различающих {differ}")
sys.exit(mezo_stand.finish(1 if bad else 0))
