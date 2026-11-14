#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА прибора «бьётся ли ритм роли».

Прибор судит ЖИВОСТЬ РИТМА по тишине, и цена его ошибки несимметрична: ложное
«держится» никто не проверяет (всё же хорошо), а ложное «не бьётся» проверяют сразу.
Значит испытывать надо прежде всего ту сторону, где он МОЛЧИТ.

Случаи (различающий = прибор обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: ровный ритм, тишина внутри допуска — 🟢, и видно, что мерил
  ② ОДИНОЧНАЯ ПАУЗА в конце ряда: допуск НЕ растёт от неё                 РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ к ②: удлинение ПОВТОРИЛОСЬ (настоящая смена шага) —
     допуск растёт, ложного «не бьётся» нет                               ВСТРЕЧНЫЙ
  ④ ВСТРЕЧНЫЙ к ②: последний промежуток КОРОЧЕ шага — основой не берётся  ВСТРЕЧНЫЙ
  ⑤ причина решения НАЗВАНА в выводе, а не подразумевается                РАЗЛИЧАЮЩИЙ
  ⑭ ВСТРЕЧНЫЙ: база не прочиталась, токен «--роль COORD-A» — роль COORD-A, а не COORD
                                                                          РАЗЛИЧАЮЩИЙ
  ⑭-бис нарочная поломка «вернуть литерал» ([A-Z]{2,16}) проваливает ⑭    РАЗЛИЧАЮЩИЙ
  ⑮ прежние русские флаги --роль --каталог --на — ТОТ ЖЕ ответ, что у английских
                                                                          РАЗЛИЧАЮЩИЙ
  (⑭ — карточка #686, место 5, 2026-10-17; ⑮ — карточка #719; прочие ⑥–⑬ — ниже по коду)

⚖️ Живых записей разговоров не касается: каждый случай строит СВОЙ каталог с одним
   рукотворным файлом и зовёт прибор с --каталог и --на (час судится рукой).
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

TOOL = pathlib.Path(__file__).resolve().parent / "measure-rhythm.py"
ROLE = "TAXO"                      # любой известный прибору токен: стенд свой, живого не трогает
START = dt.datetime(2026, 9, 1, 0, 0, tzinfo=dt.timezone.utc)
CASES = DIFFERING = 0


def case(name, ok, detail, differing=False):
    global CASES, DIFFERING
    CASES += 1
    DIFFERING += bool(differing)
    print(f"{'✅' if ok else '🔴'} {name}")
    print(f"   {detail}")
    return ok


def record(moment: dt.datetime, text: str = "исполни наказ-файл", origin=None, isMeta=True) -> str:
    """Одна запись разговора. По умолчанию — НАСТОЯЩИЙ удар: подана механизмом, без происхождения."""
    d = {"type": "user", "promptSource": "sdk",
         "timestamp": moment.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
         "message": {"role": "user", "content": [{"type": "text", "text": text}]}}
    if origin is not None:
        d["origin"] = {"kind": origin}
    if isMeta is not None:
        d["isMeta"] = isMeta
    return json.dumps(d, ensure_ascii=False)


def stand(gaps_min: list[float], extras=()) -> tuple[pathlib.Path, dt.datetime]:
    """Каталог с одним чатом: удары через заданные промежутки. → (каталог, час последнего).

    `лишние` — записи, которые ударами НЕ являются: список (сдвиг_минут, текст, origin, isMeta).
    Кладутся в тот же файл; прибор обязан их не считать.
    """
    d = mezo_stand.new("bite-rhythm-")
    lines = [json.dumps({"type": "assistant", "message": {"content":
              [{"type": "text", "text": f"python read-messages.py --роль {ROLE}"}]}}, ensure_ascii=False)]
    moment = START
    times = [moment]
    for step in gaps_min:
        moment = moment + dt.timedelta(minutes=step)
        times.append(moment)
    for moment in times:
        lines.append(record(moment))
    for shift, text, origin, isMeta in extras:
        lines.append(record(times[-1] + dt.timedelta(minutes=shift), text, origin, isMeta))
    (d / "chat0001.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d, times[-1]


def run_tool(records_dir: pathlib.Path, at: dt.datetime) -> tuple[str, int]:
    return _call(records_dir, at, ["--role", ROLE])


def run_tool_all(records_dir: pathlib.Path, at: dt.datetime) -> tuple[str, int]:
    """Без --роль: судятся ВСЕ роли каталога, и код сводится по контуру."""
    return _call(records_dir, at, [])


_ROLES_DB: pathlib.Path | None = None


def roles_db() -> pathlib.Path:
    """База стенда с таблицей roles: имена ролей прибор берёт из данных контура.

    ⚡ Найдено 2026-10-05 полным прогоном на свежем контуре (карточка #677, этап Э3):
    без своей базы прибор читал таблицу roles контура, где запущен, — на свежем контуре
    там одна роль, TAXO и CORE не опознавались, и 11 случаев из 13 отвечали отказом
    мерить. На живом контуре приёмка проходила, потому что эти роли в нём есть.
    """
    global _ROLES_DB
    if _ROLES_DB is None:
        path = mezo_stand.new("bite-rhythm-роли-") / "roles.db"
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE roles (role TEXT PRIMARY KEY)")
        con.executemany("INSERT INTO roles (role) VALUES (?)", [(ROLE,), ("CORE",)])
        con.commit()
        con.close()
        _ROLES_DB = path
    return _ROLES_DB


def _call(records_dir: pathlib.Path, at: dt.datetime, extra: list[str], db: pathlib.Path | None = None,
         tool: pathlib.Path = TOOL) -> tuple[str, int]:
    r = subprocess.run([sys.executable, str(tool), *extra, "--db", str(db or roles_db()),
                        "--dir", str(records_dir), "--at", at.strftime("%Y-%m-%dT%H:%M:%S")],
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


# ⑭ Карточка #686, место 5: роль чужого контура с дефисом в имени, когда база не прочиталась.
# Новые имена — по-английски (слово владельца 07.09); прежние русские имена файла не тронуты.
FOREIGN_ROLE = "COORD-A"
# Нарочная поломка «вернуть литерал»: прежний запасной образец, обрубавший имя на дефисе.
PATTERN_FIXED = r'ROLE_TOKEN_PATTERN = re.compile(r"--(?:role|роль)\s+([A-Z][A-Z0-9_-]{1,15})(?![A-Za-z0-9_-])")' + "\n"
PATTERN_OLD = r'ROLE_TOKEN_PATTERN = re.compile(r"--(?:role|роль)\s+([A-Z]{2,16})")' + "\n"


def foreign_role_stand() -> pathlib.Path:
    """Каталог с одним чатом роли COORD-A: ровный ряд 30 мин из пяти ударов."""
    stand = mezo_stand.new("bite-rhythm-foreign-")
    lines = [json.dumps({"type": "assistant", "message": {"content":
             [{"type": "text", "text": f"python read-messages.py --роль {FOREIGN_ROLE}"}]}},
                        ensure_ascii=False)]
    for step in range(5):
        lines.append(record(START + dt.timedelta(minutes=30 * step)))
    (stand / "chat0001.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stand


def copy_with_old_pattern() -> tuple[pathlib.Path | None, str]:
    """Копия прибора с нарочной поломкой «вернуть литерал»; не легла — (None, причина)."""
    text = TOOL.read_text(encoding="utf-8")
    if text.count(PATTERN_FIXED) != 1:
        return None, f"поломка не легла: верный образец найден {text.count(PATTERN_FIXED)} раз"
    stand = mezo_stand.new("bite-rhythm-literal-")
    (stand / TOOL.name).write_text(text.replace(PATTERN_FIXED, PATTERN_OLD), encoding="utf-8")
    (stand / "mezo_paths.py").write_text((TOOL.parent / "mezo_paths.py").read_text(encoding="utf-8"),
                                         encoding="utf-8")
    return stand / TOOL.name, ""


def _call_old_flags(records_dir: pathlib.Path, at: dt.datetime) -> tuple:
    """Тот же вызов ПРЕЖНИМИ русскими флагами (--роль --каталог --на) — карточка #719.

    Отдельная функция, а не довод к общей: случай ⑮ обязан предъявить прежнюю форму
    ДОСЛОВНО, иначе он проверял бы не синонимы, а себя же.
    """
    r = subprocess.run([sys.executable, str(TOOL), "--роль", ROLE,
                        "--db", str(roles_db()), "--каталог", str(records_dir),
                        "--на", at.strftime("%Y-%m-%dT%H:%M:%S")],
                       capture_output=True, text=True, encoding="utf-8", timeout=300)
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def main() -> int:
    ok = True
    if not TOOL.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: инструмента нет — {TOOL}")

    # ① КОНТРОЛЬ. Без него краснота остальных случаев ничего не значит: прибор мог бы
    #    краснеть всегда, и все «различающие» проходили бы даром.
    st1, last1 = stand([30, 30, 30, 30, 30])
    out1, code1 = run_tool(st1, last1 + dt.timedelta(minutes=20))
    ok &= case("① контроль: ровный ритм 30 мин, тишина 20 мин — 🟢 и шаг измерен",
                 code1 == 0 and "ДЕРЖИТСЯ" in out1 and "шаг ИЗМЕРЕН ..... 30 мин" in out1,
                 f"код {code1}; «ничего не нашёл» и «всё в порядке» обязаны различаться")

    # ② 🎯 ПРЕДМЕТ КАРТОЧКИ #550. Ряд 30 мин, затем ОДИНОЧНАЯ пауза 4 ч и удар.
    #    Тишина 5 ч. Прежний прибор брал паузу за основу (допуск 6 ч 05) и отвечал 🟢 —
    #    то есть снятый ритм выглядел живым тем дольше, чем дольше была пауза.
    st2, last2 = stand([30, 30, 30, 30, 240])
    out2, code2 = run_tool(st2, last2 + dt.timedelta(hours=5))
    ok &= case("② одиночная пауза 4 ч в конце ряда — допуск от ШАГА, не от паузы",
                 code2 == 1 and "НЕ БЬЁТСЯ" in out2 and "допуск свежести .. 50 мин" in out2,
                 f"код {code2}; окно слепоты не растёт от паузы, которой ритм и снимали",
                 differing=True)

    # ③ ВСТРЕЧНЫЙ к ②: удлинение ПОВТОРИЛОСЬ — это настоящая смена шага (случай @OPSSRE
    #    2 ч → 4 ч). Допуск обязан вырасти, иначе один случай вылечен ценой другого.
    st3, last3 = stand([30, 30, 30, 240, 240])
    out3, code3 = run_tool(st3, last3 + dt.timedelta(hours=5))
    ok &= case("③ ВСТРЕЧНЫЙ: удлинение ПОВТОРИЛОСЬ (смена шага) — допуск растёт, 🟢",
                 code3 == 0 and "ДЕРЖИТСЯ" in out3 and "ПОСЛЕДНИЙ промежуток" in out3,
                 f"код {code3}; иначе починка ② вернула бы ложное «не бьётся» живому ритму",
                 differing=True)

    # ④ ВСТРЕЧНЫЙ к ②: последний промежуток КОРОЧЕ шага (живой случай @PROTO: ряд
    #    1 ч 07 с последней парой в 15 мин). Основой он не берётся — иначе допуск
    #    сжимается ниже настоящего шага и живой ритм краснеет каждый цикл.
    st4, last4 = stand([120, 120, 15, 120, 15])
    out4, code4 = run_tool(st4, last4 + dt.timedelta(hours=2))
    ok &= case("④ ВСТРЕЧНЫЙ: последний промежуток КОРОЧЕ шага — основой не берётся, 🟢",
                 code4 == 0 and "ДЕРЖИТСЯ" in out4,
                 f"код {code4}; допуск ниже настоящего шага краснел бы на живом ритме",
                 differing=True)

    # ⑤ ПРИЧИНА НАЗВАНА. Верный ответ без причины нельзя проверить чужой рукой:
    #    читающий не отличит решения от совпадения.
    ok &= case("⑤ причина решения названа словами, а не подразумевается",
                 "удлинение ОДИНОЧНО" in out2 and "ПАУЗА" in out2,
                 "вывод обязан говорить, ПОЧЕМУ последний промежуток не взят за основу",
                 differing=True)

    # ═══ КАРТОЧКА #551: КОД ВОЗВРАТА ═══════════════════════════════════════════════
    # Роль читает вывод глазами и видит правду; машина читает КОД и видит зелёное.
    # Ниже — три пути, на которых код прежде говорил «всё в порядке».

    # ⑥ каталог есть, записей НОЛЬ. Прежде: «0 файлов», исхода нет, код 0.
    empty = mezo_stand.new("bite-rhythm-пусто-")
    out6, code6 = run_tool(empty, START)
    ok &= case("⑥ каталог есть, записей НОЛЬ — отказ мерить, код не 0",
                 code6 != 0 and "ОТКАЗ МЕРИТЬ" in out6 and "НЕТ ВОВСЕ" in out6,
                 f"код {code6}; «мерить было нечего» и «всё держится» — разные ответы",
                 differing=True)

    # ⑦ записи ЕСТЬ, роль не опознана ни в одной. Тот же вход, другая дверь —
    #    и чинится ОДНОЙ правкой (критерий ⑥ карточки: два блока разошлись бы молча).
    unnamed = mezo_stand.new("bite-rhythm-безымянный-")
    (unnamed / "chat0001.jsonl").write_text(json.dumps({
        "type": "user", "promptSource": "sdk",
        "timestamp": START.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "message": {"role": "user", "content": [{"type": "text", "text": "без токена роли"}]},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    out7, code7 = run_tool(unnamed, START + dt.timedelta(hours=1))
    ok &= case("⑦ записи есть, роль не опознана НИ В ОДНОЙ — тот же отказ, код не 0",
                 code7 != 0 and "ОТКАЗ МЕРИТЬ" in out7 and "не установлена НИ В ОДНОЙ" in out7,
                 f"код {code7}; два входа в одну беду отвечают одинаково — и одной правкой",
                 differing=True)

    # ⑧ СВЕДЕНИЕ ПО КОНТУРУ: у одной роли 🔴 поломка, у другой ⚖️ мерить нечем.
    #    Прежде брали максимум ПО КОДУ (НЕЧЕМ=3 > НЕ_БЬЁТСЯ=1) — и поломка пряталась.
    mix = mezo_stand.new("bite-rhythm-смесь-")
    moment = START
    lines_alive = [json.dumps({"type": "assistant", "message": {"content":
                     [{"type": "text", "text": "python read-messages.py --роль TAXO"}]}}, ensure_ascii=False)]
    for step in (0, 30, 60, 90):
        lines_alive.append(record(moment + dt.timedelta(minutes=step), "удар"))
    (mix / "chat_a.jsonl").write_text("\n".join(lines_alive) + "\n", encoding="utf-8")
    lines_no_step = [json.dumps({"type": "assistant", "message": {"content":
                    [{"type": "text", "text": "python read-messages.py --роль CORE"}]}}, ensure_ascii=False),
                    record(moment, "единственный удар")]
    (mix / "chat_b.jsonl").write_text("\n".join(lines_no_step) + "\n", encoding="utf-8")
    out8, code8 = run_tool_all(mix, moment + dt.timedelta(hours=6))
    ok &= case("⑧ контур: у одной роли 🔴 поломка, у другой ⚖️ нечем — код называет ПОЛОМКУ",
                 code8 == 1 and "НЕ БЬЁТСЯ" in out8 and "НЕЧЕМ" in out8,
                 f"код {code8}; тяжесть исхода — не величина его кода, и поломка не прячется "
                 f"за отказом мерить", differing=True)

    # ═══ ЧТО СЧИТАЕТСЯ УДАРОМ ══════════════════════════════════════════════════════
    # 🎯 Находка @COORD 05.09 (записка #4833): поле подачи одно НЕ отличает удар от слова
    #    владельца. Прибор судит ДВУМЯ полями, и оба обязаны сторожиться СВОИМ случаем —
    #    иначе «починка» по одному полю пройдёт незамеченной.

    # ⑩ СЛОВО ВЛАДЕЛЬЦА, НАБРАННОЕ В ЭТОМ ЖЕ ПРИЛОЖЕНИИ: подача та же (sdk), но есть
    #    происхождение «человек». Ударом быть не должно.
    st10, last10 = stand([30, 30, 30, 30], extras=[(20, "Бери задачу сейчас", "human", None)])
    out10, code10 = run_tool(st10, last10 + dt.timedelta(minutes=25))
    # ⚖️ ГРАНИЦА ЭТОГО СЛУЧАЯ, названа по замеру порчами 05.09 11:46 UTC: слово владельца
    #    отсеивается ЛЮБЫМ из двух полей, и потому ⑩ НЕ РАЗЛИЧАЕТ ни одно из них
    #    по отдельности — он краснеет только когда сняты ОБА. Он доказывает СВОЙСТВО
    #    («слово владельца не удар»), а не работу конкретного поля; поля сторожат ⑪ и ⑫.
    #    Форма @TAXO (записка #4832): у каждого встречного случая назвать, КАКАЯ порча
    #    обязана его покрасить. Здесь такой порчи по одному полю НЕТ, и это сказано вслух,
    #    а не оставлено зелёным без объяснения.
    ok &= case("⑩ слово владельца (происхождение «человек») — НЕ удар "
                 "[держится ОБОИМИ полями, порчи по одному нет]",
                 "шаг ИЗМЕРЕН ..... 30 мин" in out10 and "медиана по 5 ударам" in out10,
                 "иначе роль, которую владелец теребит вручную, выглядит самой здоровой")

    # ⑪ СООБЩЕНИЕ СОСЕДНЕЙ СЕССИИ: помечено как поданное механизмом (isMeta=true), но
    #    происхождение «peer». Ударом быть не должно — иначе чужой ритм считается своим.
    st11, last11 = stand([30, 30, 30, 30],
                     extras=[(20, "Another Claude session sent a message", "peer", True)])
    out11, code11 = run_tool(st11, last11 + dt.timedelta(minutes=25))
    ok &= case("⑪ сообщение соседней сессии (помечено механизмом, но origin=peer) — НЕ удар",
                 "медиана по 5 ударам" in out11,
                 "признак isMeta в одиночку пропускает соседа: на живом материале 2 записи",
                 differing=True)

    # ⑫ ПОДАЧА БЕЗ ПОМЕТКИ МЕХАНИЗМА и без происхождения — так выглядит слово человека
    #    в старых записях. Ударом быть не должно (на живом материале такая запись одна).
    st12, last12 = stand([30, 30, 30, 30],
                     extras=[(20, "можешь собрать список терминов", None, None)])
    out12, code12 = run_tool(st12, last12 + dt.timedelta(minutes=25))
    ok &= case("⑫ подача без пометки механизма и без происхождения — НЕ удар",
                 "медиана по 5 ударам" in out12,
                 "признак origin в одиночку пропускал ровно её — поймано находкой @COORD",
                 differing=True)

    # ⑬ ВСТРЕЧНЫЙ к ⑩⑪⑫: СТАРАЯ ОБЁРТКА будильника 27–31.08 несёт ЛОЖНОЕ происхождение
    #    «человек» — и всё-таки это настоящий удар. На живом материале их 44.
    st13, last13 = stand([30, 30, 30],
                     extras=[(30, "<scheduled-task name=\"chrome-sync\" file=\"…\">", "human", None)])
    out13, code13 = run_tool(st13, last13 + dt.timedelta(minutes=55))
    ok &= case("⑬ ВСТРЕЧНЫЙ: старая обёртка будильника с ЛОЖНЫМ «человеком» — УДАР",
                 "медиана по 5 ударам" in out13,
                 "иначе ужесточение по полям съело бы 44 настоящих удара 27–31.08",
                 differing=True)

    # ⑨ ВСТРЕЧНЫЙ к ⑥⑦⑧: там, где всё держится, код остаётся 0 — иначе зелёного
    #    не останется вовсе и код перестанут читать.
    ok &= case("⑨ ВСТРЕЧНЫЙ: там, где ритм держится, код по-прежнему 0",
                 code1 == 0 and code3 == 0 and code4 == 0,
                 f"коды {code1}/{code3}/{code4}; отказ, накрывающий всё, читать перестают",
                 differing=True)

    # ⑭ КАРТОЧКА #686, МЕСТО 5: база не прочиталась (её нет по пути) — имена берёт запасной
    #    образец. Прежний ([A-Z]{2,16}) у «--роль COORD-A» брал «COORD»: роль чужого контура
    #    судилась под чужим именем. Контроль — строка «взяты ОБРАЗЦОМ»: без неё случай мерил бы
    #    путь через данные, где дефекта нет вовсе.
    no_db = mezo_stand.new("bite-rhythm-no-db-") / "no-such-db.db"
    stand14 = foreign_role_stand()
    at14 = START + dt.timedelta(hours=2, minutes=20)
    out14, code14 = _call(stand14, at14, [], db=no_db)
    via_pattern = "взяты ОБРАЗЦОМ" in out14
    named14 = f"━━ {FOREIGN_ROLE} · чат" in out14
    ok &= case("⑭ ВСТРЕЧНЫЙ: база не прочиталась, «--роль COORD-A» — роль COORD-A, а не COORD",
                 via_pattern and named14 and "━━ COORD · чат" not in out14,
                 f"код {code14}; запасной образец {'взят' if via_pattern else 'НЕ взят — случай не зачитывается'};"
                 f" роль чата названа: {'COORD-A' if named14 else 'НЕ COORD-A'}",
                 differing=True)

    broken, why = copy_with_old_pattern()
    if broken is None:
        ok &= case("⑭-бис поломка «вернуть литерал» проваливает ⑭", False,
                     f"⛔ НЕ ЗАПУСТИЛАСЬ: {why}", differing=True)
    else:
        out14b, _ = _call(stand14, at14, [], db=no_db, tool=broken)
        cut = "━━ COORD · чат" in out14b
        ok &= case("⑭-бис поломка «вернуть литерал» ([A-Z]{2,16}) проваливает ⑭",
                     cut and f"━━ {FOREIGN_ROLE} · чат" not in out14b,
                     "под поломкой роль чата названа "
                     + ("COORD — обрубок имени, как до карточки #686" if cut
                        else "не COORD — поломка случаем НЕ поймана"),
                     differing=True)

    # ⑮ КАРТОЧКА #719: имена кода переведены на английский, флаги получили английские
    #    имена — а прежние русские обязаны продолжать работать. Случай сравнивает ОТВЕТ
    #    ЦЕЛИКОМ, а не код возврата: синоним, дающий другой ответ, — это не синоним.
    out15, code15 = _call_old_flags(st1, last1 + dt.timedelta(minutes=20))
    mismatch = next((f"{a} ≠ {b}" for a, b in zip(out1.splitlines(), out15.splitlines())
                     if a != b), "" if out1 == out15 else "длина вывода разная")
    ok &= case("⑮ прежние флаги --роль --каталог --на дают ТОТ ЖЕ ответ, что --role --dir --at",
                 code15 == code1 and out15 == out1,
                 f"коды {code1}/{code15}; "
                 + (f"первое расхождение: {mismatch[:120]}" if mismatch
                    else "вывод совпадает знак в знак — переходный синоним держится"),
                 differing=True)

    print()
    if ok:
        print(f"✅ ЗАМЕР РИТМА ПРИНЯТ — случаев {CASES}, различающих {DIFFERING}")
    else:
        print(f"🔴 ПРИЁМКА НЕ ПРОЙДЕНА — смотри красные случаи выше (всего {CASES})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
