# -*- coding: utf-8 -*-
r"""ПРИЁМКА печатника сигналов соседней роли — карточка #564 (реализация В1 карточки #548).

🩸 ЧЕМ ОПЛАЧЕНЫ СЛУЧАИ. Два дефекта поймал первый же прогон печатника 05.09, оба в САМОЙ
СРОЧНОЙ заготовке — той, по которой роль бросает свою работу и идёт разбираться:
```
① «ТЫ держишь карточку #561» ушло роли, которая её НЕ ДЕРЖИТ (держала другая).
   Рядом печаталось предупреждение — но адресат читает ТЕКСТ, а не вывод печатника
② «ТЫ держишь объявление о правке #145 (до 2026-09-04 17:40 UTC)» — сутками позже срока.
   Объявление гаснет САМО, поэтому непроставленная отметка снятия ≠ «держит»
```
⚡ КЛАСС ОБОИХ: сигнал уверенно утверждал неправду, и вся его сила — срочность — работала
на эту неправду. Молчание тут дешевле ошибки, потому и случаи ③④ — про ОТКАЗ печатать.

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① адрес есть, вид «записка» → 0, в тексте номер записки из ЖИВОЙ базы          РАЗЛИЧАЮЩИЙ
  ② имя отправителя не впечатано: тот же вызов от другой роли меняет «X →»       РАЗЛИЧАЮЩИЙ
  ③ адреса роли в реестре НЕТ → 2 и словами, чего не хватает (не пустота)        РАЗЛИЧАЮЩИЙ
  ④ «держишь» про карточку ЧУЖОГО держателя → 2, текст НЕ печатается             РАЗЛИЧАЮЩИЙ
  ⑤ адрес старше суток → 2, назван час записи и почему это важно                 РАЗЛИЧАЮЩИЙ
  ⑥ истёкшее объявление о правке в текст не входит                               РАЗЛИЧАЮЩИЙ
  ⑦ печатник ничего не отправляет — в исполняемом коде нет средства отправки     РАЗЛИЧАЮЩИЙ
  ⑧ адрес без различителя в скобках не принимается                              РАЗЛИЧАЮЩИЙ
  ⑨ записка новее, но не числящаяся адресату → сказано вслух                     РАЗЛИЧАЮЩИЙ

🌉 КАРТОЧКА #570 — УСЛОВИЕ РЕДАКЦИИ 2 ПРАВИЛА signal-not-carrier (слово владельца
2026-09-06 05:38 UTC): «ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ; ПОЯВИТСЯ ОБЩЕЕ МЕСТО —
ПОЕДЕТ ЗВОНОК.» Случаи идут ПАРАМИ, и это не оформление: без встречного ⑪ случай ⑩
зелен и у печатника, который называет условие ВСЕМ ПОДРЯД — в том числе там, где общая
лента есть и тело обязано ехать запиской.
  ⑩ адресат ЗА пределами контура → условие НАЗВАНО, печатается письмо              РАЗЛИЧАЮЩИЙ
  ⑪ ВСТРЕЧНЫЙ: адресат ВНУТРИ контура → условия НЕТ, прежний вывод цел             РАЗЛИЧАЮЩИЙ
  ⑫ ВСТРЕЧНЫЙ: тело в сообщении адресату ВНУТРИ контура → по-прежнему ОТКАЗ        РАЗЛИЧАЮЩИЙ
  ⑬ ВСТРЕЧНЫЙ к ⑫: то же тело ЗА пределы контура ВХОДИТ в письмо                   РАЗЛИЧАЮЩИЙ
  ⑭ второй источник признака: каталог обмена НА ДИСКЕ опознаёт соседа,
     о котором в базе связи нет                                                   РАЗЛИЧАЮЩИЙ
  ⑮–⑱ session_id в форме вызова, --list без ложного «жив», перезапись адреса — в коде.
  ⑲–㉙ годность адреса по живости session_id (записка #5417) — перечень у их блока в коде.

НАРОЧНЫЕ ПОЛОМКИ (--break …; --porcha и прежние русские имена — переходные синонимы).
Перечень — словарь BREAKS; список случаев, которые каждая обязана провалить, записан
ЗАРАНЕЕ в словаре BREAK_FAILS. Прогон с --break печатает ожидание до случаев и сверяет
его с фактом после; строка ИТОГ считает покрытие случаев поломками из того же словаря.

⛔ ЧЕГО ЭТА ПРИЁМКА НЕ ПОКРЫВАЕТ — названо прямо, чтобы молчание не читалось как «проверено»:
  · запись адреса на ИМЯ СОСЕДНЕГО КОНТУРА (--set-address --role TAPAS) не проверяется:
    печатник её примет и заведёт в перечне адресов строку на имя, которое ролью не является;
  · каталог обмена с именем НЕ по образцу «<наш контур>-<сосед>» встречным случаем не покрыт;
  · форма имени файла письма (ask · answer · status) взята из договора моста и против
    КАЖДОГО моста не сверяется — у мостов она может отличаться;
  · письмо соседу здесь только ПЕЧАТАЕТСЯ; ни один случай ничего не кладёт в каталоги
    обмена и ничего не отправляет — это внешнее действие, и приёмка его не делает.

⛔ Живой базы не касается: работает на КОПИИ (mezo_stand.snapshot_db) в своём временном каталоге.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import time
import tokenize

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_sessions  # noqa: E402 — самопроверка подложного хранилища сессий (случаи ⑲–㉕)
import mezo_stand  # noqa: E402

CASES = DIFFER = GREENS = 0
RUN_IDS = []    # номера прогнанных случаев по порядку (первое слово заголовка: ①, ②, …)
FAILED = []     # номера провалившихся — для сверки с заранее названным ожиданием поломки


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, GREENS
    CASES += 1
    DIFFER += bool(differ)
    GREENS += bool(verdict)
    number = title.split()[0]
    RUN_IDS.append(number)
    if not verdict:
        FAILED.append(number)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def call_tool(tool: pathlib.Path, db: pathlib.Path, *args, extra_env=None):
    """Позвать печатника. `среда` дополняет переменные окружения — ею случай ⑭ показывает
    печатнику ДРУГОЙ контейнер контура, чтобы проверить поиск каталогов обмена на диске.

    🩹 ДОГОН (класс ошибок (107)/(127), приёмка для пакета): MEZO_CONTAINER ВЫЗЫВАЮЩЕГО
    (самой приёмки) ЗДЕСЬ ГЛУШИТСЯ намеренно, а не наследуется молча. Рецепт прогона
    приёмки на свежей выгрузке пакета требует звать ЕЁ САМУ с MEZO_CONTAINER=<пакет> —
    без глушения печатник-подпроцесс унаследовал бы эту переменную и решил, что ЕГО
    контейнер — сам пакет (а не временная копия-песочница в --db), и искал бы живые
    сессии/каталоги обмена там, где их нет. Найдено прогоном: случай ⑱ на свежей выгрузке
    красился РОВНО этим — на живом контуре MEZO_CONTAINER у вызывающего просто не был
    выставлен, и то же самое отсутствие подделывается здесь для ОБОИХ контуров разом.
    Чей это принцип — mezo_stand.stand_env(): «направление закрепляет ЗАПУСКАЮЩИЙ, а не
    mezo_paths»; здесь тот же довод, приложенный к точечному вызову без готового стенда.

    🔑 ХРАНИЛИЩЕ СЕССИЙ ТОЖЕ ЗАКРЕПЛЕНО ЗА СТЕНДОМ (записка #5417), тем же доводом:
    MEZO_SESSION_STORE по умолчанию указывает на НЕСУЩЕСТВУЮЩИЙ каталог рядом с копией
    базы. Случаи ①–⑱ судят печатника в мире «хранилища нет» — ровно по прежнему правилу
    24 ч — и не зависят от того, какие сессии открыты на машине прогона. Случаи ⑲–㉕
    подают своё подложное хранилище через extra_env.
    """
    full_env = dict(os.environ)
    full_env.pop("MEZO_CONTAINER", None)
    full_env["MEZO_SESSION_STORE"] = str(pathlib.Path(db).parent / "no-session-store")
    if extra_env:
        full_env.update(extra_env)
    r = subprocess.run([sys.executable, "-B", str(tool), "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=full_env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def store_folder(store: pathlib.Path) -> pathlib.Path:
    """Каталог файлов подложного хранилища: <хранилище>/<a>/<b>/, как у приложения."""
    folder = store / "acc-account" / "acc-org"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def write_session(store: pathlib.Path, session_id: str, title: str, archived: bool,
                  cwd: str = "C:/acc-contour", hours_ago: float = 2.0) -> None:
    """Один файл подложного хранилища сессий — в той форме, что разбирает
    mezo_sessions._parse_one: <хранилище>/<a>/<b>/local_<…>.json с полями sessionId ·
    cliSessionId · title · isArchived · cwd · lastActivityAt (имена полей сверены с живым
    файлом хранилища приложения 02.10; lastActivityAt — миллисекунды эпохи)."""
    (store_folder(store) / f"{session_id}.json").write_text(json.dumps({
        "sessionId": session_id, "cliSessionId": f"cli-{session_id}", "title": title,
        "isArchived": archived, "cwd": cwd,
        "lastActivityAt": int((time.time() - hours_ago * 3600) * 1000),
    }, ensure_ascii=False), encoding="utf-8")


# 🧪 НАРОЧНЫЕ ПОЛОМКИ. Ожидание каждой стои́т ЗДЕСЬ, в коде, и печатается ДО
# случаев — чтобы исход сверяли с названным заранее, а не подгоняли объяснение
# под увиденное. Неподтвердившееся ожидание — находка, и записывается как было.
# ⚡ Сцепка с исходником печатника ДОСЛОВНАЯ и краснеет громко: искомое место обязано
# встретиться ровно один раз, иначе прогон отказывает кодом 2 «поломка не легла».
# Строка печатника, отказывающая адресу по возрасту, — её бьют четыре поломки ниже.
AGE_REFUSAL = '    if session.state != SESSION_LIVE and age is not None and age >= VALID_HOURS:'
BREAKS = {
    "hardcoded-sender": (
        '"text": ("{from} → {role}: в ленте записка #{last_note} к тебе. ',
        '"text": ("PROTO → {role}: в ленте записка #{last_note} к тебе. ',
        "ждём красным РОВНО ② (имя отправителя), остальные целы — ② единственный, "
        "кто спрашивает про отправителя"),
    "blind-link": (
        '"WHERE lower(source_group) = ?"',
        '"WHERE 0 AND lower(source_group) = ?"',
        "ослеплён ПЕРВЫЙ источник признака — запись связи с соседом в базе. Ждём "
        "красным ⑩ и ⑬ (сосед по базе больше не опознаётся); ⑭ ЗЕЛЁНЫМ — он стои́т "
        "на втором источнике, каталоге обмена; остальные целы"),
    "blind-exchange-dir": (
        '.glob("*/.mezosync/bridges/*")',
        '.glob("*/.mezosync/каталогов-обмена-нет/*")',
        "ослеплён ВТОРОЙ источник — поиск каталогов обмена на диске. Ждём красным "
        "РОВНО ⑭; ⑩ и ⑬ зелёными (их сосед записан в базе); остальные целы"),
    "condition-for-all": (
        'neighbor = neighbor_groups(conn, our, db_path).get(to_role.lower())',
        'neighbor = neighbor_groups(conn, our, db_path).get(to_role.lower()) '
        'or {"reasons": [], "directory": None}',
        "обратная слепота: КАЖДЫЙ адресат считается соседним контуром. Ждём красным "
        "①②③④⑤⑥⑨ ⑪ ⑫ ⑮ ⑯ и ⑲⑳㉑㉒㉓㉔㉖㉗㉘㉙ — всё, что судит поведение ВНУТРИ контура, включая "
        "случаи session_id (роль своего контура попадёт под отказ «имя значится и там и "
        "там» либо получит письмо соседу, и до печати формы дело не доходит); целыми ⑦ ⑧ "
        "(судят исходники и запись адреса), ⑩ ⑬ ⑭ (их адресат и так за пределами), "
        "⑰ ⑱ ㉕ (перечень и запись адреса идут раньше различения сторон)"),
    # ⚡ AIA-A (карточка A из пятёрки правок 2026-09-13): session_id перестаёт
    # учитываться при печати самой формы вызова — как если бы правку откатили.
    "session-id-order": (
        'if target.get("session_id"):',
        'if False and target.get("session_id"):',
        "session_id перестаёт учитываться при печати формы вызова (откат правки A). "
        "Ждём красным РОВНО ⑮ (форма по идентификатору не появляется вовсе); ⑯ остаётся "
        "зелёным — он и так проверяет случай БЕЗ session_id и поломки не касается; "
        "⑰ ⑱ не про эту ветку кода и тоже целы; ⑲–㉙ идут своей веткой (живая сессия "
        "печатается раньше этой строки, остальные отказывают до неё; ㉗ проверяет, что вызов "
        "напечатан, а не его форму) и целы"),
    # 🔑 записка #5417: две поломки сверки с хранилищем сессий, каждая бьёт одну опору.
    "sid-liveness-unchecked": (
        '    return SessionCheck(SESSION_LIVE, found, twins, str(store.path))',
        '    return SessionCheck(SESSION_ABSENT, None, (), str(store.path))',
        "живость по session_id не проверяется: живая сессия выглядит отсутствующей. Ждём "
        "красным РОВНО ⑲ (старый адрес живой сессии снова отвергнут по возрасту), ㉔ (то же "
        "у сессии-двойника — до слова о неоднозначности не доходит) и ㉕ (в перечне нет "
        "строки «✅ сессия жива»); ⑳ ㉓ (архив) и ㉑ ㉒ (прежнее правило) целы; ①–⑱ "
        "идут без хранилища и целы"),
    "archive-ignored": (
        '    if found.archived:',
        '    if False and found.archived:',
        "архивная сессия не отличается от живой. Ждём красным РОВНО ⑳ и ㉓ (печатник "
        "напечатает вызов в закрытый чат — и старый, и свежий) и ㉕ (в перечне вместо "
        "«⛔ чат в архиве» стоит «✅»); ⑲ цел — архивный двойник его заголовка отсеивается "
        "отдельно, при поиске двойников, и поломка его не задевает; ㉑ ㉒ ㉔ и ①–⑱ тоже целы"),
    # 🔎 Поломки по находкам двух проверок 02.10 (≈22:10–22:20 UTC): у каждого требования — свой встречный
    # случай и своя поломка. Четыре первые бьют одну строку — условие отказа по возрасту.
    "nostore-sid-trusted": (
        AGE_REFUSAL,
        '    if session.state != SESSION_LIVE and not (session.state == SESSION_UNCHECKED and '
        'target.get("session_id")) and age is not None and age >= VALID_HOURS:',
        "записанный session_id освобождает от правила 24 ч, даже когда сверить его нечем "
        "(хранилища нет или оно не разобрано)"),
    "fresh-absent-refused": (
        AGE_REFUSAL,
        '    if session.state != SESSION_LIVE and age is not None and (age >= VALID_HOURS or '
        'session.state == SESSION_ABSENT):',
        "строже прежнего: сессии нет в хранилище — отказ и свежему адресу"),
    "absent-trusted": (
        AGE_REFUSAL,
        '    if session.state not in (SESSION_LIVE, SESSION_ABSENT) and age is not None and '
        'age >= VALID_HOURS:',
        "сессия, которой нет в хранилище, освобождена от правила 24 ч"),
    "unchecked-trusted": (
        AGE_REFUSAL,
        '    if session.state not in (SESSION_LIVE, SESSION_UNCHECKED) and age is not None and '
        'age >= VALID_HOURS:',
        "исход «сверить нечем» освобождён от правила 24 ч"),
    "absent-collapsed": (
        'return SessionCheck(SESSION_ABSENT, None, (), str(store.path),',
        'return SessionCheck(SESSION_UNCHECKED, None, (), str(store.path),',
        "исход «сессии нет в хранилище» сведён к «сверить нечем»: ни предупреждения у сигнала, "
        "ни пометки в перечне"),
    "absent-warning-dropped": (
        '        absent_warning = absent_words(',
        '        absent_warning = None and absent_words(',
        "предупреждение у сигнала про отсутствующую сессию снято, перечень цел"),
    "deletion-marker-ignored": (
        'deletion_marker(store.path, session_id))',
        'None)',
        "метка удаления в хранилище не читается: удалённый чат назван «другой установкой»"),
    "twins-ignored": (
        'if found_key and not r.archived and r.session_id != found.session_id',
        'if False and found_key and not r.archived and r.session_id != found.session_id',
        "двойники заголовка не ищутся вовсе"),
    "twins-include-archived": (
        'if found_key and not r.archived and r.session_id != found.session_id',
        'if found_key and r.session_id != found.session_id',
        "архивные чаты считаются двойниками (у живой сессии ⑲ есть архивный двойник)"),
    "twins-same-cwd-only": (
        'if found_key and not r.archived and r.session_id != found.session_id',
        'if found_key and r.cwd == found.cwd and not r.archived and r.session_id != found.session_id',
        "двойники ищутся только в своём рабочем каталоге (второй чат ㉔ лежит в другом)"),
    "name-from-registry": (
        "f'SendMessage(to=\"{live.title}\", message=\"{text}\")')",
        "f'SendMessage(to=\"{target[\"address\"]}\", message=\"{text}\")')",
        "вызов по имени собран из записанного адреса с кодом, а не из живого заголовка"),
    "rename-unnamed": (
        'renamed = bool(',
        'renamed = False and bool(',
        "расхождение имени в реестре с живым заголовком не называется (в раскладке ⑲ "
        "имена разные, в ㉔ одинаковые)"),
    "activity-hidden": (
        '    ms = getattr(record, "last_activity", None)',
        '    return ""',
        "час последней активности чата не печатается — «жива» снова читается как «открыт сейчас»"),
    "signal-boundary-dropped": (
        '        print(f"   «жива по хранилищу» ≠ «прочтёт сейчас»: хранилище не знает, открыт '
        'ли чат и занята ли роль")',
        '        pass',
        "граница «жива по хранилищу ≠ прочтёт сейчас» в выводе сигнала снята"),
    "list-absent-note-dropped": (
        '                           if session.state == SESSION_ABSENT else "")',
        '                           if False else "")',
        "пометка «в хранилище этой машины такой сессии нет» в перечне снята"),
    "list-fresh-tick": (
        '                label = ("⚪ живость не проверялась" if age is not None and age < VALID_HOURS',
        '                label = ("✅ живость не проверялась" if age is not None and age < VALID_HOURS',
        "свежая строка без сверки снова получает «✅» по возрасту"),
    "store-unguarded": (
        '    except Exception as store_error:',
        '    except ZeroDivisionError as store_error:',
        "чтение хранилища без защиты: неожиданный файл в нём роняет печатник трассировкой"),
    "overwrite-unannounced": (
        'print(f"🔁 ПЕРЕЗАПИСАН: было',
        'print(f"🔁 было',
        "перезапись адреса не называет себя"),
    "distinguisher-dropped": (
        r'DISTINGUISHER = __import__("re").compile(r"\[[0-9a-f]{6,}\]\s*$")',
        r'DISTINGUISHER = __import__("re").compile(r".*")',
        "адрес без различителя в скобках принимается"),
    "send-in-code": (
        'def query_time() -> str:',
        'def unused_sender():\n    SendMessage(to="x", message="y")\n\n\ndef query_time() -> str:',
        "в исполняемый код печатника вписан вызов отправки (функция нигде не зовётся); "
        "⑦ судит ту же КОПИЮ печатника, что и остальные случаи"),
}

# 📋 СПИСОК ПРОВАЛОВ КАЖДОЙ ПОЛОМКИ — ЗАПИСАН ДО ПРОГОНА. Прогон с --break сверяет с ним
# факт и говорит вслух, совпало ли; строка ИТОГ считает по нему, какие случаи покрыты
# поломкой, а какие нет. Отдельный словарь, а не четвёртое поле BREAKS: так форма
# (до, после, пояснение) остаётся прежней для тех, кто дописывает поломки снаружи.
BREAK_FAILS = {
    "hardcoded-sender": "②",
    "blind-link": "⑩⑬",
    "blind-exchange-dir": "⑭",
    "condition-for-all": "①②③④⑤⑥⑨⑪⑫⑮⑯⑲⑳㉑㉒㉓㉔㉖㉗㉘㉙",
    "session-id-order": "⑮",
    "sid-liveness-unchecked": "⑲㉔㉕",
    "archive-ignored": "⑳㉓㉕",
    "nostore-sid-trusted": "㉖㉘",
    "fresh-absent-refused": "㉗",
    "absent-trusted": "㉑㉙",
    "unchecked-trusted": "⑤㉒㉖㉘",
    "absent-collapsed": "㉑㉕㉗㉙",
    "absent-warning-dropped": "㉑㉗㉙",
    "deletion-marker-ignored": "㉕㉙",
    "twins-ignored": "㉔",
    "twins-include-archived": "⑲",
    "twins-same-cwd-only": "㉔",
    "name-from-registry": "⑲",
    "rename-unnamed": "⑲",
    "activity-hidden": "⑲㉕",
    "signal-boundary-dropped": "⑲",
    "list-absent-note-dropped": "㉕",
    "list-fresh-tick": "⑰㉕",
    "store-unguarded": "㉘",
    "overwrite-unannounced": "⑱",
    "distinguisher-dropped": "⑧",
    "send-in-code": "⑦",
}

# Переходные синонимы: прежние имена поломок жили в записках ленты («--porcha
# впечатанное-имя»), и тот, кто повторит записанную форму вызова, не должен упасть.
BREAK_ALIASES = {
    "впечатанное-имя": "hardcoded-sender",
    "ослеплённая-связь": "blind-link",
    "ослеплённый-каталог": "blind-exchange-dir",
    "условие-всем": "condition-for-all",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", "--porcha", dest="break_name",
                    choices=sorted(BREAKS) + sorted(BREAK_ALIASES),
                    help="нарочная поломка: чем ослепить печатника перед прогоном "
                         "(--porcha и русские имена — переходные синонимы прежних вызовов)")
    a = ap.parse_args()
    break_name = BREAK_ALIASES.get(a.break_name, a.break_name)

    live_tool = pathlib.Path(__file__).resolve().parent / "signal-templates.py"
    schema_step = mezo_paths.live_scripts(__file__) / "migrations" / "20260905-role-sessions.py"
    if not live_tool.is_file():
        print(f"⛔ НЕ ЗАПУСТИЛСЯ: печатника нет: {live_tool}")
        return 2

    sandbox = mezo_stand.new("bite-signal-")
    try:
        # копия базы (backup API — согласованный снимок, не копия файла на ходу;
        # источник открывается строго на чтение)
        db = mezo_stand.snapshot_db(mezo_paths.live_db(__file__), sandbox / "copy.db")

        # 🩹 ДОГОН: печатник с карточки #649 (коммит 5c67fd9) зовёт mezo_sessions при ИМПОРТЕ —
        # без копии рядом в песочнице падает ModuleNotFoundError на КАЖДОМ вызове (код 1 везде,
        # включая случаи ⑰⑱). Раньше соседи копировались здесь поимённо; mezo_stand.copy_tool
        # везёт их сам, транзитивно по импортам, — новый сосед печатника не потеряется молча.
        tool = mezo_stand.copy_tool(live_tool, sandbox)
        if break_name:
            before_text, after_text, expectation = BREAKS[break_name]
            patch_text = tool.read_text(encoding="utf-8")
            if patch_text.count(before_text) != 1:
                print(f"⛔ НЕ ПРОВЕРЕНО: поломка «{break_name}» НЕ ЛЕГЛА — искомое место "
                      f"встречается {patch_text.count(before_text)} раз; поправь приёмку, "
                      f"а не инструмент")
                return 2
            # байтами, а не текстом: запись текстом на Windows сменила бы окончания строк копии
            tool.write_bytes(patch_text.replace(before_text, after_text).encode("utf-8"))
            print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{break_name}»: {expectation}")
            if break_name in BREAK_FAILS:
                print(f"   ждём провала РОВНО: {' '.join(BREAK_FAILS[break_name])} "
                      f"(записано в BREAK_FAILS до прогона)\n")
            else:
                print("   ⚠️ список провалов этой поломки заранее НЕ записан — сверки не будет\n")

        con = sqlite3.connect(str(db))
        if "role_sessions" not in {r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}:
            con.close()
            code, output = call_tool(schema_step, db)
            if code != 0:
                print(f"⛔ НЕ ПРОВЕРЕНО: шаг схемы на копии не прошёл:\n{output}")
                return 2
            con = sqlite3.connect(str(db))

        # ── подготовка: две роли с адресами, одна со СТАРЫМ адресом
        con.execute("DELETE FROM role_sessions")
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source) "
                    "VALUES ('PROTO', 'atlas-dd [245891]', datetime('now'), 'PROTO', 'self')")
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source) "
                    "VALUES ('COORD', 'atlas-17 [08a16e]', datetime('now'), 'COORD', 'self')")
        con.execute("INSERT INTO role_sessions (role, address, noted_at, noted_by, source) "
                    "VALUES ('STUD', 'atlas-old [000000]', datetime('now','-30 hours'), 'STUD', 'self')")
        # 🩹 ДОГОН (класс ошибок (107)/(127), приёмка для пакета — свежая выгрузка несёт
        # ПУСТУЮ ленту и пустой backlog): раньше случай ① молчаливо полагался на то, что
        # в ЖИВОЙ ленте УЖЕ есть записка PROTO к COORD (переменная note_id ниже не звалась
        # нигде — мёртвый след того расчёта на живые данные). На пустой ленте «нечего
        # сигналить» красило бы случай по пустой ленте, а не по свойству, которое он
        # проверяет. Приёмка заводит СВОЮ записку САМА — тем же ходом, что и случаю ②.
        con.execute("INSERT INTO messages (writer_role, body_md) VALUES "
                    "('PROTO', 'фикстура случая ①: записка PROTO к COORD')")
        proto_note_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO message_addressee (message_id, role, kind, linked_by) "
                    "VALUES (?, 'COORD', 'to', 'field')", (proto_note_id,))
        # 🩹 ДОГОН: случаю ② нужна СВОЯ записка ОТ COORD К PROTO — приёмка строит фикстуру
        # сама (как и role_sessions выше), а не берёт «раньше/сейчас» из среды. Без этой
        # строки на пустой от COORD ленте случай ② получает код 2 «НЕЧЕГО СИГНАЛИТЬ» и
        # красится по пустой ленте, а не по имени отправителя — не то, что он проверяет.
        con.execute("INSERT INTO messages (writer_role, body_md) VALUES "
                    "('COORD', 'фикстура случая ②: записка COORD к PROTO')")
        coord_note_id = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        con.execute("INSERT INTO message_addressee (message_id, role, kind, linked_by) "
                    "VALUES (?, 'PROTO', 'to', 'field')", (coord_note_id,))
        # 🩹 ДОГОН (класс ошибок (107)/(127)): карточка с ЧУЖИМ держателем раньше бралась
        # как max(id) ИЗ ЖИВОГО backlog — на свежей выгрузке пакета backlog ПУСТ, max(id)
        # даёт NULL, и вставка ниже падала sqlite3.IntegrityError (backlog_events.backlog_id
        # NOT NULL). Приёмка заводит СВОЮ подставную карточку на копии, явным именем —
        # не полагаясь на то, есть ли в контуре хоть одна настоящая.
        con.execute("INSERT INTO backlog (role, title, body_md, status, created_by) VALUES "
                    "('PROTO', 'приёмка bite-signal-templates: подставная карточка', "
                    "'', 'open', 'PROTO')")
        card = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        # взятие от CHROME — держатель ЧУЖОЙ адресату COORD, которого приёмка сигналит
        con.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type, body_md) "
                    "VALUES (?, datetime('now'), 'CHROME', 'claim', ?)",
                    (card, "до 2026-09-09 10:00:00 UTC · чужая рука"))
        # истёкшее объявление о правке у COORD
        con.execute("INSERT INTO tool_leases (role, tools, reason, taken_at, until_utc) "
                    "VALUES ('COORD', 'x.py', 'опыт приёмки', datetime('now','-3 hours'), "
                    "datetime('now','-2 hours'))")
        con.commit()
        con.close()
        con2 = sqlite3.connect(str(db))

        # ① сигнал о записке.
        # 🩸 ДВЕ ПРАВКИ, ОБЕ ОТ ЧУЖИХ РУК В ОДИН ЧАС, И ВТОРАЯ ГЛУБЖЕ ПЕРВОЙ.
        # ① COORD: случай ждал «последнюю записку отправителя ВООБЩЕ», а печатник по своей
        #    справке даёт последнюю К АДРЕСАТУ. У автора совпадало — случай был зелен всегда.
        # ② TAXO: повторить запрос печатника — тоже негодно. Контроль, спрашивающий базу ТЕМ ЖЕ
        #    вопросом, не проверяет инструмент, а повторяет его (правило counter-case-own-definition).
        # ⇒ случай судит СВОЙСТВО напечатанного номера, а не СПОСОБ его выбора:
        #      напечатанная записка адресована цели И новее её к цели ничего нет.
        # Свойство проверяемо при любом способе выбора и не зависит от того, кто писал последним.
        code, output = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "записка")
        printed = re.search(r"записка #(\d+) к тебе", output)
        number = int(printed.group(1)) if printed else None
        addressed = newer = None
        if number:
            addressed = con2.execute(
                "SELECT 1 FROM message_addressee WHERE message_id = ? AND upper(role) = 'COORD'",
                (number,)).fetchone() is not None
            newer = con2.execute(
                "SELECT COUNT(*) FROM messages m JOIN message_addressee a ON a.message_id = m.id "
                "WHERE m.writer_role = 'PROTO' AND upper(a.role) = 'COORD' AND m.id > ?",
                (number,)).fetchone()[0]
        case("① номер в сигнале — записка, ДЕЙСТВИТЕЛЬНО адресованная цели, и свежее её нет",
             code == 0 and number is not None and bool(addressed) and newer == 0,
             f"код {code} · напечатан #{number} · адресован COORD: {addressed} · "
             f"новее к COORD: {newer}", differ=True)

        # ② имя отправителя не впечатано
        code2, output2 = call_tool(tool, db, "--role", "COORD", "--to", "PROTO", "--kind", "записка")
        from_coord = "COORD → PROTO:" in output2
        case("② имя отправителя подставляется, а не впечатано",
             code2 == 0 and from_coord,
             f"вызов от COORD даёт «COORD → PROTO»: {'да' if from_coord else 'НЕТ — имя впечатано'}",
             differ=True)

        # ③ адреса нет
        code3, output3 = call_tool(tool, db, "--role", "PROTO", "--to", "CORE", "--kind", "записка")
        case("③ адреса роли в реестре нет → отказ СЛОВАМИ, не пустота",
             code3 == 2 and "АДРЕСА РОЛИ CORE" in output3 and "--set-address" in output3,
             f"код {code3} · сказано, чего не хватает и что делать: "
             f"{'да' if '--set-address' in output3 else 'НЕТ'}", differ=True)

        # ④ «держишь» про чужую карточку
        code4, output4 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "держишь",
                            "--card", str(card))
        no_text = "SendMessage(" not in output4
        case("④ «держишь» про карточку ЧУЖОГО держателя → отказ, текст не печатается",
             code4 == 2 and no_text and "CHROME" in output4,
             f"код {code4} · вызов не напечатан: {'да' if no_text else 'НЕТ — ушла бы неправда'}",
             differ=True)

        # ⑤ старый адрес
        code5, output5 = call_tool(tool, db, "--role", "PROTO", "--to", "STUD", "--kind", "записка")
        case("⑤ адрес старше суток → отказ с часом записи и доводом",
             code5 == 2 and "СТАР" in output5 and "признака недоставки" in output5,
             f"код {code5} · назван час записи и почему это важно: "
             f"{'да' if 'признака недоставки' in output5 else 'НЕТ'}", differ=True)

        # ⑥ истёкшее объявление о правке в текст НЕ входит.
        # 🩸 ЗДЕСЬ БЫЛ СЛЕПОЙ СЛУЧАЙ, НАЙДЕННЫЙ ЧУЖОЙ ПОРЧЕЙ (TAXO, 18:46 UTC): прежняя
        # редакция разбирала вывод ТОГО ЖЕ вызова, что и случай ④ — а там карточку держит
        # ЧУЖОЙ, печатник законно ОТКАЗЫВАЕТ и до объявления о правке не доходит вовсе.
        # Искомых слов в отказе нет ПО ПОСТРОЕНИЮ ⇒ случай был зелен при любом поведении,
        # и живой дефект («ТЫ держишь объявление о правке №175» через два часа после срока)
        # поймал побочно СОСЕДНИЙ случай.
        # ⚡ КЛАСС: раньше проверка зеленела от совпадения ДАННЫХ, теперь — от ОТКАЗА соседа.
        # Второе тише: данные меняются каждый час, а отказ соседа стои́т всегда.
        # ⇒ раскладка своя: карточку держит САМ адресат, объявление у него истёкшее (рецепт
        # TAXO, проверенный ею на обоих состояниях печатника).
        con3 = sqlite3.connect(str(db))
        # ⚠️ Раскладка обязана оставить у адресата ТОЛЬКО истёкшее объявление: первый прогон
        # покраснел честно — у роли нашлось ещё и ЖИВОЕ, и печатник верно его напечатал.
        # Опыт судил бы тогда не то, что обещает.
        con3.execute("UPDATE tool_leases SET until_utc = datetime('now','-2 hours') "
                     "WHERE role = 'COORD' AND released_at IS NULL")
        # 🩹 ДОГОН (класс ошибок (107)/(127)): раньше own_card брался запросом
        # max(backlog_id) FROM backlog_events — на живом контуре это случайно совпадало
        # с нашей же подставной карточкой (она и была максимумом), а на пустом backlog_events
        # свежей выгрузки дал бы NULL. own_card — это ТА ЖЕ подставная карточка `card`,
        # заведённая приёмкой выше: раскладка про «второй, СВОЙ держатель ТОЙ ЖЕ карточки»,
        # а не про другую карточку.
        own_card = card
        con3.execute("INSERT INTO backlog_events (backlog_id, at, actor_role, event_type, body_md) "
                     "VALUES (?, datetime('now'), 'COORD', 'claim', ?)",
                     (own_card, "до 2026-09-09 10:00:00 UTC · держит сам адресат"))
        con3.commit()
        con3.close()
        code6, output6 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "держишь",
                            "--card", str(own_card))
        printed = "SendMessage(" in output6
        # 🪤 Смотрим ТОЛЬКО текст сообщения, а не весь вывод: ниже печатается справка
        # «когда слать: чужое взятие ИЛИ ОБЪЯВЛЕНИЕ О ПРАВКЕ держит твою работу» — и первая
        # редакция случая красила её, то есть краснела по посторонней причине (третий такой
        # случай за смену). Судим то, что уедет соседу, а не то, что видит отправитель.
        body_text = re.search(r'message="([^"]*)"', output6)
        has_lease_text = bool(body_text) and "объявление о правке" in body_text.group(1)
        case("⑥ истёкшее объявление о правке не считается «держит» (текст напечатан, его там нет)",
             code6 == 0 and printed and not has_lease_text,
             f"код {code6} · текст напечатан: {printed} · объявление в тексте: "
             f"{'ЕСТЬ — сигнал о том, чего давно нет' if has_lease_text else 'нет'}", differ=True)

        # ⑦ контроль: печатник не отправляет.
        # ⚡ Разбором ТОКЕНОВ, а не образцом по строке: первый вариант этого случая искал
        # «SendMessage(» регулярным выражением и покраснел на строке, которая его ПЕЧАТАЕТ.
        # Печать вызова и вызов выглядят одинаково ровно до того часа, когда код разобран.
        # ⚖️ Судится КОПИЯ печатника — та же, что зовут все остальные случаи. Без поломки она
        # байт в байт равна исходнику; зато нарочная поломка «send-in-code» доходит и сюда,
        # и этот случай доказывается поломкой из словаря, а не только историей (TAXO 05.09).
        source_text = tool.read_text(encoding="utf-8")
        code_without_text = []
        with io.open(tool, "rb") as fh:
            for tok in tokenize.tokenize(fh.readline):
                # 🪤 f-строка с версии 3.12 разбирается НА ЧАСТИ (FSTRING_START/MIDDLE/END),
                # и её текст выходит из-под фильтра «STRING». Первый вариант этого случая
                # честно отбрасывал STRING и всё равно видел печатаемую строку как код.
                if tok.type not in (tokenize.STRING, tokenize.COMMENT,
                                  getattr(tokenize, "FSTRING_START", -1),
                                  getattr(tokenize, "FSTRING_MIDDLE", -1),
                                  getattr(tokenize, "FSTRING_END", -1)):
                    code_without_text.append(tok.string)
        executable_text = " ".join(code_without_text)
        calls_send = "SendMessage" in executable_text
        prints_call = "SendMessage(to=" in source_text
        case("⑦ печатник только ПЕЧАТАЕТ вызов, отправки в исполняемом коде нет",
             prints_call and not calls_send,
             f"вызов есть в тексте для человека: {'да' if prints_call else 'НЕТ'} · "
             f"в исполняемом коде: {'ЕСТЬ — отправка мимо руки роли' if calls_send else 'нет'}",
             differ=True)  # 🔑 РАЗЛИЧАЮЩИЙ, а не «контроль»: доказано чужой порчей (TAXO 18:57 UTC —
        # вызов настоящей отправки внутри незовомой функции ⇒ случай покраснел первым же прогоном).
        # Пометка «контроль» была РАЗМЕТКОЙ автора, а не свойством случая.

        # ⑧ адрес без различителя в скобках (находка COORD: одно имя носят ДВА разговора)
        code8, output8 = call_tool(tool, db, "--role", "CORE", "--set-address", "atlas-17")
        case("⑧ адрес без различителя в скобках не принимается",
             code8 == 2 and "РАЗЛИЧИТЕЛ" in output8,
             f"код {code8} · сказано, что имя указывает на несколько разговоров: "
             f"{"да" if "НЕСКОЛЬКО" in output8 else "НЕТ"}", differ=True)

        # ⑨ свежая записка отправителя, НЕ числящаяся адресату → сказано вслух
        con2.execute("INSERT INTO messages (writer_role, timestamp, body_md) "
                     "VALUES ('PROTO', datetime('now'), 'записка без адресатов полями')")
        con2.commit()
        latest = con2.execute("SELECT max(id) FROM messages WHERE writer_role='PROTO'").fetchone()[0]
        code9, output9 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD", "--kind", "записка")
        case("⑨ есть записка новее, но не числящаяся адресату → сказано вслух, не подставлено молча",
             code9 == 0 and f"#{latest}" in output9 and "НОВЕЕ" in output9,
             f"код {code9} · про записку #{latest} сказано: "
             f"{'да' if 'НОВЕЕ' in output9 else 'НЕТ — подставлена старая молча'}", differ=True)
        con2.close()

        # ═══ 🌉 УСЛОВИЕ РЕДАКЦИИ 2 ПРАВИЛА signal-not-carrier (карточка #570) ═══
        # «ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ; ПОЯВИТСЯ ОБЩЕЕ МЕСТО — ПОЕДЕТ ЗВОНОК.»
        # 🩹 ДОГОН (класс ошибок (107)/(127), приёмка для пакета): раньше случаи ⑩–⑬ судили
        # НАСТОЯЩИЙ мост живого контура (связь atlas→aia/tapas в cross_links) — на свежей
        # выгрузке пакета связей с соседями нет ВООБЩЕ, и приёмка отказывала ДО единого
        # случая. Имя СВОЕГО контура по-прежнему берётся ИЗ БАЗЫ (впечатанное «atlas»
        # пережило бы закрытие моста и судило бы несуществующее) — а вот СОСЕДА приёмка
        # теперь заводит САМА, на своей КОПИИ, явным подставным именем, которое ни с
        # настоящим соседом, ни с ролью контура не спутать.
        con4 = sqlite3.connect(str(db))
        our_group_row = con4.execute(
            "SELECT lower(value) FROM meta WHERE key = 'group_name'").fetchone()
        if not our_group_row or not (our_group_row[0] or "").strip():
            con4.close()
            print("⚠️ НЕ ПРОВЕРЕНО: в базе нет имени своего контура (meta.group_name) — "
                  "случаям ⑩–⑬ и подставному мосту судить не с чем")
            return 2
        our_group = our_group_row[0].strip()
        neighbor_name = "bitebridge"
        already_role = con4.execute(
            "SELECT 1 FROM roles WHERE upper(role) = ?", (neighbor_name.upper(),)).fetchone()
        if already_role:
            con4.close()
            print(f"⛔ НЕ ПРОВЕРЕНО: имя подставного соседа «{neighbor_name}» занято настоящей "
                  f"ролью контура — приёмка судила бы не то")
            return 2
        con4.execute("INSERT OR IGNORE INTO cross_links (source_group, target_group, "
                     "target_db_path, description) VALUES (?, ?, ?, ?)",
                     (our_group, neighbor_name, str(sandbox / "подставная-соседняя-база.db"),
                      "подставная связь приёмки bite-signal-templates — не настоящий мост"))
        con4.commit()

        # ⑩ адресат ЗА пределами контура: условие НАЗВАНО словами правила
        code10, output10 = call_tool(tool, db, "--role", "PROTO", "--to", neighbor_name.upper())
        condition_shown = "ТЕЛО ЕДЕТ ТАМ, ГДЕ ОБЩЕГО МЕСТА НЕТ" in output10
        letter = "ПИСЬМО СОСЕДНЕМУ КОНТУРУ" in output10
        no_call = "SendMessage(" not in output10
        case("⑩ адресат ЗА пределами контура → условие НАЗВАНО словами правила, печатается "
             "письмо, а не строка с номером записки",
             code10 == 0 and condition_shown and letter and no_call,
             f"код {code10} · условие названо: "
             f"{'да' if condition_shown else 'НЕТ — печатник молчит там, где обязан говорить'} · "
             f"форма письма: {letter} · номер записки соседу НЕ послан: {no_call}",
             differ=True)

        # ⑪ ВСТРЕЧНЫЙ. Без него ⑩ зелен и у печатника, который называет условие ВСЕМ:
        # такой печатник учит роль возить тело мимо ленты внутри контура — то есть
        # ровно тому, что правило запрещает, и учит с полной уверенностью.
        code11, output11 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD",
                              "--kind", "записка")
        silent = "ТЕЛО ЕДЕТ ТАМ" not in output11 and "ПИСЬМО СОСЕДНЕМУ" not in output11
        previous_output = "SendMessage(" in output11 and "СИГНАЛ — НЕ НОСИТЕЛЬ" in output11
        case("⑪ ВСТРЕЧНЫЙ: адресат ВНУТРИ контура → условие НЕ печатается, прежний вывод цел",
             code11 == 0 and silent and previous_output,
             f"код {code11} · условие не названо: "
             f"{'да' if silent else 'НЕТ — печатник называет его всем подряд'} · "
             f"прежний короткий сигнал на месте: {previous_output}", differ=True)

        # ⑫ ВСТРЕЧНЫЙ: тело в сообщении внутри контура — по-прежнему отказ
        body_file_path = sandbox / "body.md"
        body_file_path.write_text("разбор на две строки\nвторая строка тела", encoding="utf-8")
        code12, output12 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD",
                              "--body-file", str(body_file_path))
        body_stayed = "разбор на две строки" not in output12 and "SendMessage(" not in output12
        case("⑫ ВСТРЕЧНЫЙ: попытка вложить тело адресату ВНУТРИ контура → по-прежнему ОТКАЗ",
             code12 == 2 and "ВНУТРИ КОНТУРА" in output12 and body_stayed,
             f"код {code12} · тело в вывод не попало: "
             f"{'да' if body_stayed else 'НЕТ — условие растянули на свой контур'}",
             differ=True)

        # ⑬ ВСТРЕЧНЫЙ к ⑫: то же тело за пределы контура ВХОДИТ в письмо. Без него ⑫
        # зелен и у печатника, который отклоняет --body-file вообще всем, — а тогда на
        # мосту он снова предписывает неисполнимое, ради чего условие и вносили.
        code13, output13 = call_tool(tool, db, "--role", "PROTO", "--to", neighbor_name.upper(),
                              "--body-file", str(body_file_path))
        included = "разбор на две строки" in output13 and "вторая строка тела" in output13
        case("⑬ ВСТРЕЧНЫЙ к ⑫: то же тело адресату ЗА пределами контура ВХОДИТ в письмо "
             "(отказ ⑫ — про сторону, а не про сам ключ вызова)",
             code13 == 0 and included,
             f"код {code13} · тело в письме: "
             f"{'да' if included else 'НЕТ — ключ отклонён всем подряд'}", differ=True)

        # ⑭ ВТОРОЙ ИСТОЧНИК ПРИЗНАКА — каталог обмена НА ДИСКЕ, без записи связи в базе.
        # Заводится СВОЙ контейнер во временном каталоге и показывается печатнику
        # переменной среды: так проверяется, что сосед опознаётся по каталогу, а не
        # только по базе. Имя соседа выбрано заведомо отсутствующим в базе — это
        # проверено тут же, иначе случай зеленел бы по посторонней причине.
        new_neighbor = "neigh"
        already_in_db = con4.execute("SELECT 1 FROM cross_links WHERE lower(target_group) = ?",
                                   (new_neighbor,)).fetchone()
        con4.close()
        if already_in_db:
            print("⛔ НЕ ПРОВЕРЕНО: имя нового соседа уже есть в базе — случай ⑭ судил бы не то")
            return 2
        container = sandbox / "чужой-контейнер"
        (container / ".mezosync").mkdir(parents=True, exist_ok=True)
        # база-признак — настоящий файл (заголовок SQLite), не пустышка 0 байт: пустую поиск корня
        # с 06.10 пропускает (починка (б), карточка #678)
        marker = sqlite3.connect(str(container / ".mezosync" / "mezosync.db"))
        marker.execute("PRAGMA user_version = 1")
        marker.close()
        (container / "repo" / ".mezosync" / "bridges" /
         f"{our_group}-{new_neighbor}").mkdir(parents=True, exist_ok=True)
        code14, output14 = call_tool(tool, db, "--role", "PROTO", "--to", new_neighbor.upper(),
                              extra_env={"MEZO_CONTAINER": str(container)})
        recognized = f"ПИСЬМО СОСЕДНЕМУ КОНТУРУ «{new_neighbor}»" in output14
        by_directory = "каталог обмена" in output14
        case("⑭ сосед, о котором в базе связи НЕТ, опознаётся по каталогу обмена на диске",
             code14 == 0 and recognized and by_directory,
             f"код {code14} · опознан как соседний контур: "
             f"{'да' if recognized else 'НЕТ — второй источник признака не работает'} · "
             f"путь назван: {by_directory}", differ=True)

        # ═══ AIA-A (карточка A из пятёрки правок 2026-09-13): role_sessions.session_id ═══
        # Стойкий идентификатор сессии — переживает возобновление чата, в отличие от
        # короткого адреса «имя [код]». Шаг схемы накатывается ЗДЕСЬ, на ту же копию:
        # он идёт ПОСЛЕ 20260905-role-sessions.py и ничего не портит поверх него.
        session_id_step = mezo_paths.live_scripts(__file__) / "migrations" / \
            "20260913-role-sessions-session-id.py"
        code_session_id_step, output_session_id_step = call_tool(session_id_step, db)
        if code_session_id_step != 0:
            print(f"⛔ НЕ ПРОВЕРЕНО: шаг схемы session_id на копии не прошёл:\n"
                  f"{output_session_id_step}")
            return 2
        con5 = sqlite3.connect(str(db))
        con5.execute("INSERT INTO role_sessions (role, address, session_id, noted_at, "
                     "noted_by, source) VALUES ('SIDROLE', 'atlas-sid [abc123]', "
                     "'local_deadbeef00', datetime('now'), 'SIDROLE', 'self')")
        con5.commit()
        con5.close()

        # ⑮ session_id есть → форма ПО ИДЕНТИФИКАТОРУ печатается ПЕРВОЙ
        code15, output15 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDROLE",
                              "--kind", "записка")
        by_id = 'mcp__ccd_session_mgmt__send_message(session_id="local_deadbeef00"' in output15
        by_id_first = (by_id and output15.find("mcp__ccd_session_mgmt__send_message")
                        < output15.find('SendMessage(to="atlas-sid'))
        case("⑮ session_id есть → форма по идентификатору печатается ПЕРВОЙ, форма по имени — второй",
             code15 == 0 and by_id and by_id_first and "переживает возобновление" in output15,
             f"код {code15} · форма по id есть: {by_id} · идёт раньше формы по имени: "
             f"{by_id_first}", differ=True)

        # ⑯ ВСТРЕЧНЫЙ: session_id НЕ записан → формы по идентификатору нет вовсе
        code16, output16 = call_tool(tool, db, "--role", "PROTO", "--to", "COORD",
                              "--kind", "записка")
        case("⑯ ВСТРЕЧНЫЙ: session_id не записан → формы по идентификатору НЕТ, только по имени",
             code16 == 0 and "mcp__ccd_session_mgmt__send_message" not in output16
             and 'SendMessage(to="' in output16,
             f"код {code16} · форма по id отсутствует: "
             f"{'да' if 'mcp__ccd_session_mgmt__send_message' not in output16 else 'НЕТ'}",
             differ=True)

        # ⑰ --list не выдаёт свежий адрес за «жив»: ✅ убран, граница названа словами.
        # ⚖️ Верно только БЕЗ хранилища сессий (call_tool по умолчанию его прячет): с ним «✅»
        # законно стои́т у сессий, живых по session_id, — это судит ㉕.
        code17, output17 = call_tool(tool, db, "--list")
        case("⑰ без хранилища сессий --list не печатает «✅» как «жив»: возраст + явная граница "
             "вместо галочки",
             code17 == 0 and "✅" not in output17 and "живость не проверялась" in output17
             and "≠ «жива»" in output17 and "≠ «мертва»" in output17,
             f"код {code17} · «✅» в выводе: "
             f"{'ЕСТЬ — читается как живость' if '✅' in output17 else 'нет'} · "
             f"граница названа: {'да' if '≠ «мертва»' in output17 else 'НЕТ'}", differ=True)

        # ⑱ перезапись адреса печатает «ПЕРЕЗАПИСАН: было …», прежняя строка уходит в историю
        con6 = sqlite3.connect(str(db))
        history_before = con6.execute("SELECT COUNT(*) FROM role_sessions_history "
                                  "WHERE role='SIDROLE'").fetchone()[0]
        con6.close()
        code18, output18 = call_tool(tool, db, "--role", "SIDROLE", "--set-address",
                              "atlas-sid2 [fedcba]")
        con6 = sqlite3.connect(str(db))
        history_after = con6.execute("SELECT COUNT(*) FROM role_sessions_history "
                                     "WHERE role='SIDROLE'").fetchone()[0]
        con6.close()
        case("⑱ перезапись адреса печатает «ПЕРЕЗАПИСАН: было …» и уводит прежнюю строку в историю",
             code18 == 0 and "ПЕРЕЗАПИСАН: было" in output18 and "local_deadbeef00" in output18
             and history_after == history_before + 1,
             f"код {code18} · «ПЕРЕЗАПИСАН» напечатан: {'ПЕРЕЗАПИСАН: было' in output18} · "
             f"история {history_before} → {history_after}", differ=True)

        # ═══ 🔑 ГОДНОСТЬ АДРЕСА ПО ЖИВОСТИ session_id (предложение OPSSRE ②, записка #5415;
        # решение PROTO, записка #5417) ═══
        # Беда: правило «24 ч с часа записи» с 02.10 отказывало всем раз в сутки, хотя
        # session_id переживает и возобновление чата, и перезапуск приложения. Случаи судят
        # печатника на КОПИИ базы и на ПОДЛОЖНОМ хранилище сессий (MEZO_SESSION_STORE):
        #   ⑲ (а) старше 24 ч + session_id живой → печатает; имя — ЖИВОЙ заголовок     РАЗЛИЧАЮЩИЙ
        #   ⑳ (б) старше 24 ч + session_id в архиве → 2, «в архиве»                    РАЗЛИЧАЮЩИЙ
        #   ㉑ (в) старше 24 ч + сессии нет в хранилище → 2 по старому правилу и
        #        предупреждение про другую установку приложения                          РАЗЛИЧАЮЩИЙ
        #   ㉒ (г) старше 24 ч, session_id не записан → 2 как раньше                     РАЗЛИЧАЮЩИЙ
        #   ㉓ (д) МОЛОЖЕ 24 ч + session_id в архиве → 2: архив важнее возраста          РАЗЛИЧАЮЩИЙ
        #   ㉔ (е) два живых чата с одним заголовком → печатает, неоднозначность вслух   РАЗЛИЧАЮЩИЙ
        #   ㉕ (ж) --list: ✅ жива по session_id · ⛔ чат в архиве · ⌛ СТАР как было     РАЗЛИЧАЮЩИЙ
        # 🔎 Добавлены по находкам двух проверок 02.10 (≈22:10–22:20 UTC) — у каждого требования свой случай:
        #   ㉖ (з) ХРАНИЛИЩА НЕТ + session_id записан + старше 24 ч → 2 как раньше
        #        (вторая половина пункта 4; встречный к ⑲: та же роль, то же session_id) РАЗЛИЧАЮЩИЙ
        #   ㉗ (и) МОЛОЖЕ 24 ч + сессии нет в найденном хранилище → печатает с
        #        предупреждением («не строже прежнего», пункт 3)                         РАЗЛИЧАЮЩИЙ
        #   ㉘ (к) хранилище не разобрано (чужой файл в нём) → прежнее правило, без
        #        трассировки                                                              РАЗЛИЧАЮЩИЙ
        #   ㉙ (л) у отсутствующей сессии есть метка удаления → «похоже, удалён», а не
        #        «другая установка»                                                       РАЗЛИЧАЮЩИЙ
        # ⚖️ Встречный внутри ⑲: у живой сессии есть АРХИВНЫЙ двойник с тем же заголовком —
        # он неоднозначности НЕ создаёт (голое имя выбирает среди живых). Без этой строки
        # ⑲ был бы зелен и у печатника, который считает двойниками и архивные.
        live_sid, live_title = "local_acc-live-0001", "atlas coord 10.02"
        live_old_address = "atlas coord 08.30 [3c476f]"
        archived_twin_sid = "local_acc-archtwin-0005"
        archived_sid, archived_young_sid = "local_acc-arch-0002", "local_acc-arch-0006"
        twin_sid, twin_other_sid, twin_title = ("local_acc-twin-0003", "local_acc-twin-0004",
                                                "atlas twin")
        gone_sid = "local_acc-gone-0007"            # в хранилище нарочно НЕ кладётся
        gone_fresh_sid = "local_acc-gonefresh-0009"  # тоже НЕ кладётся
        deleted_sid = "local_acc-del-0008"          # файла сессии нет, есть метка удаления
        store = sandbox / "session-store"
        write_session(store, live_sid, live_title, archived=False)
        write_session(store, archived_twin_sid, live_title, archived=True)
        write_session(store, archived_sid, "atlas arch old", archived=True)
        write_session(store, archived_young_sid, "atlas arch young", archived=True)
        write_session(store, twin_sid, twin_title, archived=False)
        # второй чат с тем же заголовком — в ДРУГОМ рабочем каталоге: двойники ищутся по
        # всему хранилищу, и поиск только в своём каталоге обязан здесь краснеть
        write_session(store, twin_other_sid, twin_title, archived=False,
                      cwd="C:/acc-other-contour")
        # метка удаления — в той форме, что держит приложение: файл deleted_<uuid>, внутри
        # час удаления в миллисекундах эпохи
        deleted_marker = store_folder(store) / f"deleted_{deleted_sid[len('local_'):]}"
        deleted_marker.write_text(str(int((time.time() - 5 * 3600) * 1000)), encoding="utf-8")
        # 🪤 САМОПРОВЕРКА ПОДЛОЖНОГО ХРАНИЛИЩА: его читает тот же модуль, что и печатник.
        # Подложка не того формата дала бы «сессии нет» всем — и красное случаев (а)(е)(ж)
        # читалось бы как дефект печатника, а не как дефект подложки.
        fake = mezo_sessions.read_store(store)
        parsed = {r.session_id: r.archived for r in fake.sessions}
        expected_store = {live_sid: False, archived_twin_sid: True, archived_sid: True,
                          archived_young_sid: True, twin_sid: False, twin_other_sid: False}
        if not fake.found or parsed != expected_store:
            print(f"⛔ НЕ ПРОВЕРЕНО: подложное хранилище сессий разобрано не так, как задумано: "
                  f"найдено {fake.found}, прочитано {parsed}")
            return 2
        # Негодное хранилище для ㉘: живая сессия ⑲ плюс файл, который роняет чтение модуля
        # (JSON-список вместо объекта). Посылка случая проверяется тут же: если модуль такой
        # файл прочтёт без падения, ㉘ судил бы не то, что обещает.
        bad_store = sandbox / "session-store-bad"
        write_session(bad_store, live_sid, live_title, archived=False)
        (store_folder(bad_store) / "local_zz.json").write_text("[]", encoding="utf-8")
        try:
            mezo_sessions.read_store(bad_store)
            bad_store_falls = False
        except Exception:  # noqa: BLE001 — посылка ㉘ и есть «чтение падает»
            bad_store_falls = True
        if not bad_store_falls:
            print("⛔ НЕ ПРОВЕРЕНО: негодное подложное хранилище читается без падения — "
                  "случаю ㉘ судить не с чем")
            return 2
        store_env = {"MEZO_SESSION_STORE": str(store)}
        con7 = sqlite3.connect(str(db))
        for role, address, sid, hours in (
                ("SIDLIVE", live_old_address, live_sid, 30),
                ("SIDARCH", "atlas arch old [a1a1a1]", archived_sid, 30),
                ("SIDGONE", "atlas gone [b2b2b2]", gone_sid, 30),
                ("NOSIDOLD", "atlas nosid [c3c3c3]", None, 30),
                ("SIDYOUNG", "atlas arch young [d4d4d4]", archived_young_sid, 0),
                ("SIDTWIN", "atlas twin [e5e5e5]", twin_sid, 30),
                ("SIDFRESH", "atlas gone fresh [f6f6f6]", gone_fresh_sid, 0),
                ("SIDDEL", "atlas deleted [a7a7a7]", deleted_sid, 30)):
            con7.execute("INSERT INTO role_sessions (role, address, session_id, noted_at, "
                         "noted_by, source) VALUES (?, ?, ?, datetime('now', ?), ?, 'self')",
                         (role, address, sid, f"-{hours} hours", role))
        con7.commit()
        con7.close()
        note_args = ("--kind", "записка", "--note", str(proto_note_id))

        # ⑲ (а)
        code19, output19 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDLIVE", *note_args,
                                     extra_env=store_env)
        by_sid19 = f'session_id="{live_sid}"' in output19
        by_live_title = f'SendMessage(to="{live_title}"' in output19
        by_old_code = 'SendMessage(to="atlas coord 08.30' in output19
        old_named = live_old_address in output19 and "мог смениться" in output19
        ambiguous19 = "НЕОДНОЗНАЧН" in output19
        # честность вывода: «жива» = «не в архиве», час активности назван, условие доставки
        # по имени названо, граница «≠ прочтёт сейчас» на месте; имена в реестре и в
        # хранилище в этой раскладке РАЗНЫЕ («08.30» и «10.02») — расхождение обязано звучать
        activity19 = "последняя активность" in output19
        reach19 = "ListAgents" in output19
        boundary19 = "≠ «прочтёт сейчас»" in output19
        rename19 = "не совпадает с живым заголовком" in output19
        case("⑲ (а) адрес старше 24 ч, session_id живой → печатает; имя для отправки — ЖИВОЙ "
             "заголовок чата, записанный адрес с кодом — отдельной строкой",
             code19 == 0 and by_sid19 and by_live_title and not by_old_code and old_named
             and not ambiguous19 and "СТАР" not in output19 and activity19 and reach19
             and boundary19 and rename19,
             f"код {code19} · по session_id: {by_sid19} · по живому заголовку «{live_title}»: "
             f"{by_live_title} · вызов по записанному адресу с кодом: "
             f"{'ЕСТЬ — код мог смениться' if by_old_code else 'нет'} · записанный адрес назван "
             f"отдельной строкой: {old_named} · архивный двойник заголовка счёл неоднозначностью: "
             f"{'ДА — архив считается живым' if ambiguous19 else 'нет'} · час последней "
             f"активности: {activity19} · условие доставки по имени (ListAgents): {reach19} · "
             f"граница «≠ прочтёт сейчас»: {boundary19} · расхождение имени названо: {rename19}",
             differ=True)

        # ⑳ (б)
        code20, output20 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDARCH", *note_args,
                                     extra_env=store_env)
        no_call20 = "SendMessage(" not in output20 and "send_message(" not in output20
        case("⑳ (б) адрес старше 24 ч, session_id в архиве → отказ: чат роли закрыт (в архиве)",
             code20 == 2 and "в архиве" in output20 and no_call20 and "--set-address" in output20,
             f"код {code20} · сказано «в архиве»: {'да' if 'в архиве' in output20 else 'НЕТ'} · "
             f"вызов не напечатан: {no_call20} · совет записать новый адрес: "
             f"{'да' if '--set-address' in output20 else 'НЕТ'}", differ=True)

        # ㉑ (в)
        code21, output21 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDGONE", *note_args,
                                     extra_env=store_env)
        other_install = "другой установки" in output21 and "#34" in output21
        case("㉑ (в) адрес старше 24 ч, сессии нет в хранилище → отказ по прежнему правилу и "
             "предупреждение про хранилище другой установки",
             code21 == 2 and "СТАР" in output21 and "признака недоставки" in output21
             and other_install and "SendMessage(" not in output21,
             f"код {code21} · прежний отказ «СТАР»: {'да' if 'СТАР' in output21 else 'НЕТ'} · "
             f"предупреждение про другую установку (заявка пакета #34): {other_install}",
             differ=True)

        # ㉒ (г)
        code22, output22 = call_tool(tool, db, "--role", "PROTO", "--to", "NOSIDOLD", *note_args,
                                     extra_env=store_env)
        case("㉒ (г) адрес старше 24 ч, session_id не записан → отказ как раньше, хотя "
             "хранилище найдено",
             code22 == 2 and "СТАР" in output22 and "признака недоставки" in output22
             and "другой установки" not in output22 and "в архиве" not in output22,
             f"код {code22} · прежний отказ «СТАР»: {'да' if 'СТАР' in output22 else 'НЕТ'} · "
             f"лишних слов о хранилище нет: "
             f"{'другой установки' not in output22 and 'в архиве' not in output22}", differ=True)

        # ㉓ (д)
        code23, output23 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDYOUNG", *note_args,
                                     extra_env=store_env)
        no_call23 = "SendMessage(" not in output23 and "send_message(" not in output23
        case("㉓ (д) адрес МОЛОЖЕ 24 ч, но session_id в архиве → отказ: архив важнее возраста",
             code23 == 2 and "в архиве" in output23 and no_call23,
             f"код {code23} · сказано «в архиве»: {'да' if 'в архиве' in output23 else 'НЕТ'} · "
             f"вызов не напечатан: {no_call23}", differ=True)

        # ㉔ (е) — второй чат с тем же заголовком лежит в ДРУГОМ рабочем каталоге
        code24, output24 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDTWIN", *note_args,
                                     extra_env=store_env)
        by_sid24 = f'session_id="{twin_sid}"' in output24
        bare_call24 = f'SendMessage(to="{twin_title}"' in output24
        # встречный к проверке расхождения имени в ⑲: здесь имя в реестре и заголовок
        # совпадают, и слов о расхождении быть не должно
        rename24 = "не совпадает с живым заголовком" in output24
        case("㉔ (е) два живых чата с одним заголовком (второй — в другом рабочем каталоге) → "
             "печатает по session_id и говорит вслух, что голое имя неоднозначно",
             code24 == 0 and by_sid24 and "НЕОДНОЗНАЧН" in output24 and twin_other_sid in output24
             and not bare_call24 and not rename24,
             f"код {code24} · по session_id: {by_sid24} · неоднозначность названа: "
             f"{'да' if 'НЕОДНОЗНАЧН' in output24 else 'НЕТ'} · второй чат назван: "
             f"{twin_other_sid in output24} · вызов по голому имени: "
             f"{'ЕСТЬ — уйдёт неизвестно куда' if bare_call24 else 'не напечатан'} · ложное "
             f"«имя не совпадает»: {'ЕСТЬ' if rename24 else 'нет'}", differ=True)

        # ㉕ (ж)
        code25, output25 = call_tool(tool, db, "--list", extra_env=store_env)

        def row_of(role):
            # роль в строке перечня дополнена пробелами до 8 знаков — так она не спутается
            # с той же ролью в хвосте «рукой <роль>,»
            return next((line for line in output25.splitlines() if f" {role:<8} " in line), "")

        absent_text = "в хранилище этой машины такой сессии нет"
        kinds = {
            "✅ SIDLIVE": f"✅ сессия жива по session_id (заголовок «{live_title}»)" in row_of("SIDLIVE")
                          and "последняя активность" in row_of("SIDLIVE"),
            "⛔ SIDARCH": "⛔ чат в архиве" in row_of("SIDARCH"),
            "⛔ SIDYOUNG": "⛔ чат в архиве" in row_of("SIDYOUNG"),
            "⌛ NOSIDOLD": "⌛ СТАР" in row_of("NOSIDOLD"),
            "⌛ SIDGONE с пометкой": "⌛ СТАР" in row_of("SIDGONE") and absent_text in row_of("SIDGONE")
                                    and "метка удаления" not in row_of("SIDGONE"),
            "⚪ SIDFRESH не найдена": "⚪ в хранилище не найдена" in row_of("SIDFRESH")
                                     and absent_text in row_of("SIDFRESH"),
            "SIDDEL метка удаления": "метка удаления" in row_of("SIDDEL"),
            "⚪ PROTO": "⚪ живость не проверялась" in row_of("PROTO"),
        }
        ticks = output25.count("✅")
        boundary = "«жива по хранилищу» ≠ «прочтёт сейчас»" in output25
        case("㉕ (ж) --list показывает три вида строк: ✅ жива по session_id · ⛔ чат в архиве · "
             "⌛ СТАР как было; свежая строка без сверки по-прежнему не «жива»",
             code25 == 0 and all(kinds.values()) and ticks == 2 and boundary,
             f"код {code25} · строки: "
             + " · ".join(f"{k} {'да' if v else 'НЕТ'}" for k, v in kinds.items())
             + f" · «✅» ровно у живых по session_id (ждём 2): {ticks} · граница «жива по "
               f"хранилищу ≠ прочтёт сейчас» названа: {'да' if boundary else 'НЕТ'}",
             differ=True)

        # ㉖ (з) — та же роль, что в ⑲, но хранилища НЕТ (call_tool по умолчанию его прячет)
        code26, output26 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDLIVE", *note_args)
        no_call26 = "SendMessage(" not in output26 and "send_message(" not in output26
        why26 = "сверить его нечем" in output26
        case("㉖ (з) хранилища нет, session_id записан, адрес старше 24 ч → отказ по прежнему "
             "правилу (встречный к ⑲: та же роль, то же session_id)",
             code26 == 2 and "СТАР" in output26 and "признака недоставки" in output26 and no_call26
             and why26 and "другой установки" not in output26 and "в архиве" not in output26,
             f"код {code26} · прежний отказ «СТАР»: {'да' if 'СТАР' in output26 else 'НЕТ'} · "
             f"вызов не напечатан: {no_call26} · сказано, что сверить нечем: {why26} · "
             f"лишних слов о хранилище нет: "
             f"{'другой установки' not in output26 and 'в архиве' not in output26}", differ=True)

        # ㉗ (и) — «НЕ строже прежнего»: свежий адрес печатается и без сессии в хранилище
        code27, output27 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDFRESH", *note_args,
                                     extra_env=store_env)
        call27 = "SendMessage(" in output27 or "send_message(" in output27
        warn27 = "другой установки" in output27 and "#34" in output27
        case("㉗ (и) адрес моложе 24 ч, сессии нет в найденном хранилище → печатает, как раньше, "
             "и предупреждает про другую установку (не строже прежнего)",
             code27 == 0 and call27 and warn27 and "СТАР" not in output27,
             f"код {code27} · вызов напечатан: {call27} · предупреждение про другую установку "
             f"(заявка пакета #34): {warn27}", differ=True)

        # ㉘ (к) — негодное хранилище: прежнее правило и внятный ответ, а не трассировка
        code28, output28 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDLIVE", *note_args,
                                     extra_env={"MEZO_SESSION_STORE": str(bad_store)})
        traceback28 = "Traceback" in output28
        case("㉘ (к) хранилище не разобрано (чужой файл в нём) → прежнее правило 24 ч и причина "
             "словами, без трассировки",
             code28 == 2 and "СТАР" in output28 and "не разобрано" in output28 and not traceback28,
             f"код {code28} · прежний отказ «СТАР»: {'да' if 'СТАР' in output28 else 'НЕТ'} · "
             f"причина названа: {'да' if 'не разобрано' in output28 else 'НЕТ'} · трассировка: "
             f"{'ЕСТЬ — печатник упал' if traceback28 else 'нет'}", differ=True)

        # ㉙ (л) — метка удаления меняет СЛОВА, годность — по-прежнему по возрасту
        code29, output29 = call_tool(tool, db, "--role", "PROTO", "--to", "SIDDEL", *note_args,
                                     extra_env=store_env)
        deleted29 = "похоже, чат удалён" in output29 and deleted_marker.name in output29
        case("㉙ (л) сессии нет в хранилище, но есть её метка удаления → «похоже, удалён», а не "
             "«другая установка»; годность по прежнему правилу",
             code29 == 2 and "СТАР" in output29 and deleted29 and "другой установки" not in output29,
             f"код {code29} · прежний отказ «СТАР»: {'да' if 'СТАР' in output29 else 'НЕТ'} · "
             f"метка удаления названа: {deleted29} · ложное «другая установка»: "
             f"{'ЕСТЬ' if 'другой установки' in output29 else 'нет'}", differ=True)

        # ═══ ИТОГ: счёт случаев и покрытие поломками — из словаря, а не числом в тексте ═══
        # ⚖️ Форма TAXO (приёмка 05.09): число различающих растёт вместе с числом случаев
        # и перестаёт что-либо значить, если не сказано, сколько из них ПОДТВЕРЖДЕНО поломкой.
        # 🔑 Её находка, ради которой это и считается: строка «различающих 8» была верна ЧИСЛОМ
        # и неверна СОСТАВОМ — в неё был зачтён ⑥, который тогда краснеть не мог, и НЕ зачтён ⑦,
        # который мог. Две ошибки взаимно погасились, и число вышло верным ПО ПОСТОРОННЕЙ
        # ПРИЧИНЕ. Поэтому покрытие ниже ВЫЧИСЛЯЕТСЯ из BREAK_FAILS, а непокрытые случаи
        # перечисляются поимённо: граница доказанного названа целиком, а не наполовину.
        covered = set().union(*(set(v) for v in BREAK_FAILS.values()))
        covered_run = [n for n in RUN_IDS if n in covered]
        uncovered = [n for n in RUN_IDS if n not in covered]
        unknown = sorted(covered - set(RUN_IDS))
        no_list = sorted(set(BREAKS) - set(BREAK_FAILS))
        print("")
        if break_name in BREAK_FAILS:
            expected_fail = set(BREAK_FAILS[break_name])
            actual_fail = set(FAILED)
            if expected_fail == actual_fail:
                print(f"🧪 ожидание поломки «{break_name}» ПОДТВЕРДИЛОСЬ: провалены ровно "
                      f"{' '.join(n for n in RUN_IDS if n in actual_fail)}")
                # Поломка поймана как записано — стенд с копией живой базы хранить незачем;
                # код выхода прежний (карточка #657, пункт (3), записка #5437)
                mezo_stand.expected_break()
            else:
                print(f"⚠️ ожидание поломки «{break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали "
                      f"{' '.join(n for n in RUN_IDS if n in expected_fail) or 'ничего'}, "
                      f"провалены {' '.join(n for n in RUN_IDS if n in actual_fail) or 'ничего'}")
        print(f"ИТОГ: {GREENS} из {CASES} · различающих {DIFFER}, из них покрыто нарочной "
              f"поломкой из словаря {len(covered_run)} (список провалов каждой поломки записан "
              f"до прогона; совпадение проверяет прогон с --break <имя>) · ни одной поломкой "
              f"не покрыты: {' '.join(uncovered) if uncovered else 'нет'}")
        if unknown or no_list:
            print(f"⚠️ словарь поломок расходится со случаями: номера без случая — "
                  f"{' '.join(unknown) or 'нет'}; поломки без списка провалов — "
                  f"{', '.join(no_list) or 'нет'}")
        mismatch = bool(break_name in BREAK_FAILS and set(BREAK_FAILS[break_name]) != set(FAILED))
        return 0 if GREENS == CASES and not mismatch else 1
    finally:
        mezo_stand.release(sandbox)


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
