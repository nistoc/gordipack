#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА хода Г — вычисляемой срочности (модуль urgency.py в живых скриптах).

Обещана координатору (его записка #3390): своя приёмка у него зелёная, но за смену 07.08
ни один дефект в его семи правках не нашёл он сам — все нашли соседи. Эта проверка и есть
сосед: она ИМПОРТИРУЕТ ЖИВОЙ модуль (не копию — копия проверяет копию) и гоняет его
на подложенных случаях с заранее известным ответом.

Свойства, каждое с контролем в том же прогоне:
  ① свежая срочная без отклика ................. ГОРИТ (это и есть контроль машины: если
                                                 не горит ничего — прогон не зачитывается)
  ② срочная старше окна ........................ не горит, причина НАЗЫВАЕТ возраст
  ③ отклик от ДРУГОЙ роли (@автор, вне цитаты) . не горит, причина НАЗЫВАЕТ записку
  ④ отклик от ТОЙ ЖЕ роли ...................... ГОРИТ — сторож против возврата дефекта
                                                 самогашения (найден витриной 08.08 10:53)
  ⑤ ссылка в ЦИТАТЕ («> …#N») .................. ГОРИТ — цитата не отклик
  ⑥ ссылка без названного @автора .............. ГОРИТ — строгий признак, не гасим зря
  ⑦ своя нота автору не горит, ЧУЖОМУ читателю горит — витрина персональная
  ⑧ обычная записка не горит и причины не несёт

⛔ Живой базы не касается: своя песочница. Живой МОДУЛЬ только импортируется.
"""
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом

SCRIPTS = str(mezo_target.scripts_root())
NOW = datetime(2026, 8, 8, 12, 0, 0)          # фиксированное «сейчас»: приёмка не зависит от часов


def load_live_module():
    """Импорт ЖИВОГО urgency.py. Нет файла → «не запустилась», а не красное свойство."""
    path = os.path.join(SCRIPTS, "urgency.py")
    if not os.path.exists(path):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {path} не найден — приёмке нечего испытывать.")
    spec = importlib.util.spec_from_file_location("urgency_live", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(rows):
    """Песочница: та же форма messages, что в живой базе."""
    path = os.path.join(tempfile.mkdtemp(prefix="bite-urgency-display-"), "s.db")
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT,
                   timestamp TEXT, body_md TEXT, tags TEXT, priority TEXT,
                   resolved INTEGER, broadcast INTEGER, addressed_by TEXT)""")
    for mid, role, hours_ago, prio, body in rows:
        ts = (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
        con.execute("INSERT INTO messages (id, writer_role, timestamp, priority, body_md)"
                    " VALUES (?,?,?,?,?)", (mid, role, ts, prio, body))
    con.commit()
    return con


CASES = 0
def case(title, verdict, detail):
    global CASES
    CASES += 1
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def main() -> int:
    u = load_live_module()
    ok = True

    con = build([
        # ① свежая срочная, отклика нет
        (1001, "CORE", 1.0, "high", "срочный вопрос без ответа"),
        # ② срочная старше окна
        (1002, "CORE", 30.0, "critical", "старый срочный вопрос"),
        # ③ свежая срочная + НАСТОЯЩИЙ отклик от другой роли
        (1003, "CORE", 2.0, "high", "вопрос с ответом"),
        (1004, "STUD", 1.0, "normal", "@CORE — отвечаю на #1003 по существу"),
        # ④ свежая срочная + отклик от ТОЙ ЖЕ роли
        (1005, "TAXO", 2.0, "high", "вопрос без чужого ответа"),
        (1006, "TAXO", 1.0, "normal", "@TAXO дополняю свою же #1005"),
        # ⑤ свежая срочная + ссылка ТОЛЬКО в цитате
        (1007, "ING", 2.0, "high", "вопрос, который лишь цитируют"),
        (1008, "STUD", 1.0, "normal", "напоминаю контекст:\n> как сказано в #1007 (@ING)\nсвой текст"),
        # ⑥ свежая срочная + ссылка вне цитаты, но автор НЕ назван
        (1009, "OPSSRE", 2.0, "high", "вопрос, упомянутый без обращения"),
        (1010, "STUD", 1.0, "normal", "смотрите также #1009, там подробности"),
        # ⑧ обычная записка
        (1011, "CORE", 1.0, "normal", "обычная записка"),
    ])

    def state(mid, reader="PROTO"):
        r = con.execute("SELECT id, writer_role, timestamp, priority FROM messages WHERE id=?",
                        (mid,)).fetchone()
        return u.urgency_state(con, r[0], r[1], r[2], r[3], NOW, reader)

    burn, why = state(1001)
    ok &= case("① свежая срочная без отклика ГОРИТ (контроль: машина не молчит)",
               burn is True, f"горит={burn}, причина={why!r}")

    burn, why = state(1002)
    ok &= case("② старше окна: не горит, причина называет ВОЗРАСТ",
               burn is False and why and "старше" in why, f"горит={burn}, причина={why!r}")

    burn, why = state(1003)
    ok &= case("③ отклик от другой роли: не горит, причина называет ЗАПИСКУ",
               burn is False and why and "#1004" in (why or ""), f"горит={burn}, причина={why!r}")

    burn, why = state(1005)
    ok &= case("④ отклик от ТОЙ ЖЕ роли НЕ гасит — сторож против самогашения",
               burn is True, f"горит={burn}, причина={why!r} — своей рукой отклик не изобразить")

    burn, why = state(1007)
    ok &= case("⑤ ссылка в ЦИТАТЕ не гасит — цитата не отклик",
               burn is True, f"горит={burn}, причина={why!r}")

    burn, why = state(1009)
    ok &= case("⑥ ссылка без названного автора не гасит — строгий признак",
               burn is True, f"горит={burn}, причина={why!r}")

    b_self, w_self = state(1001, reader="CORE")     # автор смотрит на свою же
    b_other, _ = state(1001, reader="STUD")         # чужой читатель
    ok &= case("⑦ своя нота автору не горит, чужому читателю горит",
               b_self is False and "сво" in (w_self or "") and b_other is True,
               f"автору: горит={b_self}, причина={w_self!r} · чужому: горит={b_other}")

    burn, why = state(1011)
    ok &= case("⑧ обычная записка не горит и причины не несёт",
               burn is False and why is None, f"горит={burn}, причина={why!r}")

    print()
    print(f"{'✅ ХОД Г ПРИНЯТ' if ok else '🔴 ХОД Г НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
