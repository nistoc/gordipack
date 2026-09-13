# -*- coding: utf-8 -*-
r"""ПРИЁМКА срока годности у метки-долга — записка @COORD #3768.

🩸 ЧЕМ ОПЛАЧЕНО (точнее — чем НЕ оплачено, и в этом весь довод). Метка `STUB-EXPECTED: #N`
объявлена в шапке инструмента «ДОЛГОМ СО СРОКОМ ГОДНОСТИ» — в отличие от вечного признания
честности. Проверялось при этом ровно одно: стои́т ли рядом номер.
```
стои́т ли номер ....... проверялось
жива ли задача ....... НЕТ
существует ли она .... НЕТ. `STUB-EXPECTED: #99999` проходило
```
⇒ Закроют задачу — метка продолжит оправдывать заглушку бессрочно. Срок был ОБЪЯВЛЕН
и ничем не обеспечен.

⚖️ ПОЧЕМУ ЧИНИМ СЕЙЧАС, КОГДА ЭКЗЕМПЛЯРОВ НОЛЬ. Довод соседей, взят целиком:
**в чистом состоянии дыры не видно, а в грязном она уже выглядит законной.**

🩸 И СВОЯ ОШИБКА ПО ДОРОГЕ, названная вслух: первая редакция починки считала закрытыми
статусы `closed`/`cancelled`/`rejected` — которых в базе НЕТ ВОВСЕ, — и не знала про
`dropped`, который есть. То есть проверка срока годности была написана по памяти о чужих
системах. Поймано первым же запросом к базе:
```
done 162 · open 62 · awaiting_word 6 · blocked 6 · in_progress 4 · in_review 4 · dropped 4
```

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① живая задача — долг законен                                            РАЗЛИЧАЮЩИЙ
  ② ЗАКРЫТАЯ задача — «оправдание пережило свою причину»                   РАЗЛИЧАЮЩИЙ
  ③ задачи НЕТ вовсе — отдельный исход, не тот же, что ②                   РАЗЛИЧАЮЩИЙ
  ④ статус НЕЗНАКОМ — «не берусь судить», а не приговор в любую сторону    РАЗЛИЧАЮЩИЙ
  ⑤ статусы сверены со словарём пишущего (backlog.py) и с базой            РАЗЛИЧАЮЩИЙ
  ⑤-бис встречный: статус, которого нет ни в словаре, ни в базе, — ловится  РАЗЛИЧАЮЩИЙ
  ⑤-тер встречный: законный статус, которого сейчас нет у карточек, — не выдуман  РАЗЛИЧАЮЩИЙ
  ⑥ вердикт метки различает три состояния, а не сводит к одному «долг»     РАЗЛИЧАЮЩИЙ

⛔ Живой базы не меняет: читает её только на чтение, стенды строит свои.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sqlite3
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

TOOL = (mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
              / "guard-stub-expectations.py")
DB_PATH = mezo_paths.container_root(__file__) / ".mezosync" / "mezosync.db"
CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def load_tool():
    sys.path.insert(0, str(TOOL.parent))
    spec = importlib.util.spec_from_file_location("метки_под_испытанием", TOOL)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def task_with_status(statuses) -> str | None:
    """Номер живой задачи с одним из статусов — ИЗ БАЗЫ, а не выдуманный."""
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    placeholders = ",".join("?" * len(statuses))
    row = con.execute(f"SELECT id FROM backlog WHERE status IN ({placeholders}) LIMIT 1",
                         statuses).fetchone()
    con.close()
    return str(row[0]) if row else None


def writer_statuses() -> set[str]:
    """Словарь статусов того, кто их ПИШЕТ: константа STATUSES в backlog.py рядом с инструментом.

    Разбирается как текст (ast), а не импортом: backlog.py при импорте тянет свои зависимости,
    а нам нужен только список. Нет файла или константы — отказ, а не пустой словарь: пустой
    словарь объявил бы выдуманными все статусы разом.
    """
    import ast
    source = TOOL.parent / "backlog.py"
    if not source.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет словаря статусов — {source}")
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "STATUSES"):
            return {str(s).strip().lower() for s in ast.literal_eval(node.value)}
    sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: в {source.name} нет константы STATUSES — сверять не с чем")


def legal_statuses(vocabulary: set[str], data_statuses: set[str]) -> set[str]:
    """Законное = словарь пишущего ∪ то, что есть в базе (в базе бывает старое, словарём снятое)."""
    return vocabulary | data_statuses


def invented_statuses(tool_text: str, legal: set[str]) -> list[str]:
    """Статусы из списков инструмента, которых нет среди законных.

    ⚠️ Смотрим ТОЛЬКО списки статусов, а не весь текст: слово "closed" законно живёт
       в коде как ИМЯ ИСХОДА функции (`return "closed", …`). Первая редакция этого
       случая искала по всему файлу и покраснела на исправном коде — признак отвечал
       не на тот вопрос: «встречается ли слово» вместо «числится ли статусом».
    """
    # 🩸 13.09 20:08 UTC у проверки появился третий список (FROZEN_STATUSES, записка #5140) —
    #    образец, знавший два имени, его не видел. Читаем ЛЮБОЙ список с именем …_STATUSES.
    import re
    status_lists = " ".join(re.findall(r"\b[A-Z_]*STATUSES\s*=\s*\(([^)]*)\)", tool_text))
    return sorted(set(re.findall(r'"([a-z_]+)"', status_lists)) - legal)


def main() -> int:
    ok = True
    if not TOOL.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет инструмента — {TOOL}")
    tool = load_tool()

    open_task = task_with_status(["open", "in_progress"])
    closed_task = task_with_status(["done", "dropped"])
    if not open_task or not closed_task:
        sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: в базе нет задач нужных состояний — "
                 "опыт не на чем ставить, и это отказ мерить, а не «чисто»")

    state, reason = tool._task_state(open_task)
    ok &= case("① живая задача — долг законен",
               state == "open",
               f"#{open_task} → {state}: {reason}", differ=True)

    state2, reason2 = tool._task_state(closed_task)
    ok &= case("② ЗАКРЫТАЯ задача — «оправдание пережило свою причину»",
               state2 == "closed",
               f"#{closed_task} → {state2}: {reason2}", differ=True)

    state3, reason3 = tool._task_state("99999999")
    ok &= case("③ задачи НЕТ вовсе — отдельный исход, а не тот же, что у закрытой",
               state3 == "ghost" and state3 != state2,
               f"#99999999 → {state3}: {reason3}. Свести с ② значило бы объявить "
               "несуществующее просроченным", differ=True)

    # ④ НЕЗНАКОМЫЙ СТАТУС. Стенд: своя база с задачей в статусе, которого мы не знаем.
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-debt-"))
    stand_db = d / "mezosync.db"
    con = sqlite3.connect(stand_db)
    con.execute("CREATE TABLE backlog (id INTEGER PRIMARY KEY, status TEXT)")
    con.execute("INSERT INTO backlog (id, status) VALUES (4242, 'какой-то-новый')")
    con.commit()
    con.close()
    previous_live_db = tool.mezo_paths.live_db if hasattr(tool, "mezo_paths") else None
    import mezo_paths as mp
    saved_live_db = mp.live_db
    mp.live_db = lambda *a, **k: str(stand_db)
    try:
        state4, reason4 = tool._task_state("4242")
    finally:
        mp.live_db = saved_live_db
    ok &= case("④ статус НЕЗНАКОМ — «не берусь судить», а не приговор",
               state4 == "unknown",
               f"#4242 (статус «какой-то-новый») → {state4}: {reason4}. Отнести незнакомое "
               "к закрытым — краснеть на каждом новом статусе; к живым — молча пропускать",
               differ=True)

    # ⑤ СПИСКИ СВЕРЕНЫ СО СЛОВАРЁМ. Проверяем, что в коде нет статусов, которых не бывает.
    # 🩸 13.09 случай краснел от ДАННЫХ, а не от кода (находка COORD, записка #5134): законными
    #    считались только статусы, которые СЕЙЧАС есть у карточек. Закрыли последнюю карточку
    #    на проверке — и законный in_review стал «выдуманным»; awaiting_word — так же. Отсутствие
    #    в данных ≠ отсутствие в словаре. Законное = словарь пишущего (backlog.py) ∪ то, что в базе.
    tool_text = TOOL.read_text(encoding="utf-8", errors="replace")
    vocabulary = writer_statuses()
    con = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    data_statuses = {(r[0] or "").strip().lower() for r in con.execute("SELECT DISTINCT status FROM backlog")}
    con.close()
    legal = legal_statuses(vocabulary, data_statuses)
    invented = invented_statuses(tool_text, legal)
    ok &= case("⑤ статусы сверены со словарём пишущего (backlog.py) и с базой, а не перечислены по памяти",
               not invented,
               f"словарь backlog.py: {sorted(vocabulary)}; в базе сверх словаря: "
               f"{sorted(data_statuses - vocabulary) or 'нет'}; выдуманных в коде: {invented or 'нет'} — "
               "первая редакция починки перечисляла три таких и не знала про dropped",
               differ=True)

    # ⑤-бис ВСТРЕЧНЫЙ: без него ⑤ могла бы проходить, не умея ловить вовсе.
    fake_text = ('CLOSED_STATUSES = ("done", "dropped", "closed")\nOPEN_STATUSES = ("open",)\n'
                 'FROZEN_STATUSES = ("frozen", "iced")')
    caught = invented_statuses(fake_text, legal)
    ok &= case("⑤-бис встречный: статус, которого нет ни в словаре, ни в базе, — ловится в любом списке",
               caught == ["closed", "iced"],
               f"«closed» в списке закрытых (так писала первая редакция починки), «iced» в списке "
               f"замороженных → выдуманных: {caught or 'нет'}",
               differ=True)

    # ⑤-тер ВСТРЕЧНЫЙ к находке 13.09: законный статус, которого сейчас нет ни у одной карточки.
    #    Идёт через ту же legal_statuses(), что и ⑤: сверку «только по базе» он обязан покрасить.
    only_open_in_data = {"open"}
    listed = 'OPEN_STATUSES = ("open", "in_review")'
    by_data_only = invented_statuses(listed, only_open_in_data)
    by_rule = invented_statuses(listed, legal_statuses(vocabulary, only_open_in_data))
    ok &= case("⑤-тер встречный: законный статус, которого сейчас нет у карточек, — не выдуман",
               by_data_only == ["in_review"] and by_rule == [],
               f"в базе только open: сверка по одной базе → {by_data_only} (прежняя ложная тревога), "
               f"по правилу приёмки → {by_rule or 'нет'}",
               differ=True)

    # ⑥ ВЕРДИКТ МЕТКИ различает состояния, а не сводит всё к «долгу».
    lines_open = ["// STUB-EXPECTED: #%s — снять вместе с формой" % open_task]
    lines_closed = ["// STUB-EXPECTED: #%s — снять вместе с формой" % closed_task]
    lines_ghost = ["// STUB-EXPECTED: #99999999 — снять вместе с формой"]
    verdicts = (tool.verdict_for(lines_open, 0), tool.verdict_for(lines_closed, 0),
                tool.verdict_for(lines_ghost, 0))
    ok &= case("⑥ вердикт метки различает три состояния, а не сводит к одному «долг»",
               verdicts == ("debt", "debt-dead", "debt-ghost"),
               f"вердикты: {verdicts} — до правки все три были «debt», и метка "
               "оправдывала заглушку бессрочно", differ=True)

    import shutil
    shutil.rmtree(d, ignore_errors=True)
    print()
    print(f"{'✅ СРОК ГОДНОСТИ ДОЛГА ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
