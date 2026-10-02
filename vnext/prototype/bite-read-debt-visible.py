# -*- coding: utf-8 -*-
r"""ПРИЁМКА проверки «пишет, но не читает» — записка @COORD #3767.

🩸 ЧЕМ ОПЛАЧЕНО. Проверка печатала «✅ активных ролей 1, все читают ленту» в ту минуту,
когда в контуре лежало 1280 непрочитанных записок у восьми ролей из девяти. Она была
права формально (судила тех, кто писал за последние 90 минут) и лгала по существу:
итоговая строка звучала как ответ про весь контур.

⚡ И вот замер, который делает случай неопровержимым: в 17:24 признак был КРАСНЫМ и назвал
роль честно, а в 19:13 стал ЗЕЛЁНЫМ — не потому, что кто-то прочёл, а потому, что та роль
замолчала на 166 минут и вышла из окна. Долг вырос с 93 до 98 и стал невидим.
🎯 Формула та же, что в проверке замороженных файлов: ПУСТОЙ НАБОР НЕ ДОЛЖЕН ПРОХОДИТЬ
ЗЕЛЁНЫМ. Зелёное здесь означало «проверять было некого», а читалось как «долгов нет».

⚖️ ЧЕГО ЭТА ПРИЁМКА НЕ ТРЕБУЕТ: краснеть на спящих. Требовать чтения от закрытого чата
нельзя, и вечно-красный учит не верить красному. Требуется ровно одно — чтобы непроверенное
называлось вслух и не пряталось за словом «все».

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① долг СПЯЩЕЙ роли назван вслух, хотя она не судится                      РАЗЛИЧАЮЩИЙ
  ② итог говорит «активных N из M», а не «все читают ленту»                  РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ: спящая роль НЕ делает прогон красным                         РАЗЛИЧАЮЩИЙ
  ④ активная роль с долгом — КРАСНОЕ, и долг вне окна назван тут же         РАЗЛИЧАЮЩИЙ
  ⑤ активных нет вовсе — сказано «проверять было НЕКОГО», а не «все читают» РАЗЛИЧАЮЩИЙ
  ⑥ машинный ответ несёт непроверенные роли, а не только нарушителей        РАЗЛИЧАЮЩИЙ
  ⑦ ⛔ ЗНАЕМ, ЧТО НЕ ЛОВИМ: подтверждение прочтения ≠ понимание             ПРЕДЕЛ НАЗВАН
  ⑧ жёлтая строка доезжает до ОБЩЕГО прогона, а не только до прямого       РАЗЛИЧАЮЩИЙ
  ⑨ ВСТРЕЧНЫЙ: обычные строки зелёного прогона НЕ выливаются в общий вывод РАЗЛИЧАЮЩИЙ
  ⑩ ОБРАТНЫЙ ХОД: с ПРЕЖНИМ общим прогоном случай ⑧ теряется              РАЗЛИЧАЮЩИЙ

🩸 ОТЧЕГО ПОЯВИЛИСЬ ⑧⑨⑩ — ошибка, найденная при проверке СВОЕЙ ЖЕ починки. Я научила
проверку говорить «вне окна 8 ролей, их долг НЕ ПРОВЕРЯЛСЯ», прогнала её отдельно — строка
есть. Прогнала ОБЩИЙ прогон — строки НЕТ: при коде 0 он печатал одну галочку и глотал всё
сказанное подпроверкой.
```
прямой вызов guard-write-without-read.py .... строка ВИДНА     ← это я и проверила
общий прогон guard-all.py .................... строки НЕТ      ← а заявка была про НЕГО
```
🎯 Заявка @COORD была ровно о том, что в ОБЩЕМ прогоне долг невидим ⇒ починка закрывала
половину, и приёмка из семи случаев её приняла: ни один не звал общий прогон. Класс дня,
третий экземпляр за смену: **находка по следу в своих данных покрывает ту ветку, которая
у тебя исполнилась**, — а дефект живёт и в соседней.

⚖️ ⑨ нужен, чтобы починка не стала шумом: вылить в общий вывод ВСЕ строки подпроверок
значило бы утопить красное в зелёном. Печатаются только помеченные предупреждением.

⛔ Живой базы не касается: каждый случай строит СВОЮ базу с нуля.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны

CHECK = (mezo_paths.container_root(__file__) / ".mezosync" / "scripts"
            / "guard-write-without-read.py")
COMMON = mezo_paths.container_root(__file__) / ".mezosync" / "scripts" / "guard-all.py"

CASES = DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def stand(roles) -> pathlib.Path:
    """Своя база на каждый случай.

    ⚠️ Каждый случай строит СВОЁ состояние — иначе порядок прогона меняет результат,
    и это невидимо (правило, принесённое @OPSSRE 23.08 и оплаченное его же опытом).
    роли: список (имя, минут_назад_писала, сколько_чужих_нот_не_прочла)
    """
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-read-debt-"))
    con = sqlite3.connect(d / "mezosync.db")
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY, writer_role TEXT, timestamp TEXT,
                               body TEXT);
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER,
                                   updated_at TEXT);
        CREATE VIEW messages_all AS SELECT * FROM messages;
    """)
    now_ = datetime.now(timezone.utc)
    note_id = 0
    for name_, minutes_, debt in roles:
        when_ = now_ - timedelta(minutes=minutes_)
        note_id += 1
        con.execute("INSERT INTO messages (id, writer_role, timestamp, body) VALUES (?,?,?,?)",
                    (note_id, name_, when_.strftime("%Y-%m-%d %H:%M:%S"), "нота"))
    # чужие ноты, которые роли не прочли: пишет их отдельный «сосед»
    tail_ = note_id
    for name_, minutes_, debt in roles:
        for _ in range(debt):
            tail_ += 1
            con.execute("INSERT INTO messages (id, writer_role, timestamp, body) VALUES (?,?,?,?)",
                        (tail_, "ЧУЖОЙ", now_.strftime("%Y-%m-%d %H:%M:%S"), "чужая нота"))
    for i, (name_, minutes_, debt) in enumerate(roles, 1):
        # отметка прочитанного ставится так, чтобы непрочитанных чужих было ровно `долг`
        threshold = tail_ - debt
        con.execute("INSERT INTO read_cursors (reader_role, last_read_id, updated_at)"
                    " VALUES (?,?,?)",
                    (name_, threshold, (now_ - timedelta(minutes=minutes_)).strftime("%Y-%m-%d %H:%M:%S")))
    con.commit()
    con.close()
    return d


def run_guard(d: pathlib.Path, *extra) -> tuple[str, int]:
    r = subprocess.run([sys.executable, str(CHECK), "--db", str(d / "mezosync.db"), *extra],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=300, env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def fake_subguard(lines, code_=0) -> pathlib.Path:
    """Подпроверка, печатающая заданные строки и возвращающая заданный код.

    ⚖️ Своя, а не живая: живая зависит от состояния контура, и опыт стал бы гаданием.
    Испытывается при этом НАСТОЯЩИЙ sub_guard из живого общего прогона.
    """
    d = pathlib.Path(tempfile.mkdtemp(prefix="bite-subguard-"))
    f_ = d / "подпроверка.py"
    body_ = chr(10).join(f"print({s!r})" for s in lines)
    f_.write_text("# -*- coding: utf-8 -*-" + chr(10) + body_ + chr(10)
                 + f"raise SystemExit({code_})" + chr(10), encoding="utf-8")
    return f_


def via_common(subcheck: pathlib.Path, common: pathlib.Path = None) -> str:
    """Зовём sub_guard живого общего прогона и ловим ВСЁ, что он напечатал."""
    import importlib.util
    target_ = common or COMMON
    sys.path.insert(0, str(target_.parent))
    spec_ = importlib.util.spec_from_file_location(f"общий_{target_.parent.name}", target_)
    mod_ = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod_)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        mod_.sub_guard("испытуемый", None, set(), script_path=str(subcheck))
    return buffer.getvalue()


def main() -> int:
    ok = True
    if not CHECK.exists():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: нет проверки — {CHECK}")

    # ① СПЯЩАЯ РОЛЬ С ДОЛГОМ. Здесь и умирала прежняя редакция: роль исчезала бесследно.
    d = stand([("БОДРАЯ", 5, 0), ("СПЯЩАЯ", 600, 40)])
    out, rc = run_guard(d)
    ok &= case("① долг СПЯЩЕЙ роли назван вслух, хотя она не судится",
               "СПЯЩАЯ 40" in out and "НЕ ПРОВЕРЯЛСЯ" in out,
               f"код {rc}; строка: {next((s.strip() for s in out.splitlines() if 'вне окна' in s), '(нет)')[:120]}",
               differ=True)

    # ② ФОРМУЛИРОВКА ИТОГА. «Все читают ленту» — верно формально, ложно по существу.
    ok &= case("② итог говорит «активных N из M», а не «все читают ленту»",
               "активных ролей 1 из 2" in out and "все читают ленту" not in out,
               "прежняя строка отвечала на вопрос про писавших за 90 минут, "
               "а звучала как ответ про весь контур", differ=True)

    # ③ ВСТРЕЧНЫЙ К ①: спящая роль НЕ делает прогон красным. Без этого случая починка
    #    ① могла бы вернуть вечно-красный на дормантных ролях — а он учит не верить красному.
    ok &= case("③ ВСТРЕЧНЫЙ: спящая роль с долгом НЕ делает прогон красным",
               rc == 0,
               f"код {rc} — требовать чтения от закрытого чата нельзя; строка нужна "
               "для видимости, а не для приговора", differ=True)

    # ④ АКТИВНАЯ РОЛЬ С ДОЛГОМ — красное, и долг вне окна назван ТУТ ЖЕ.
    #    🪤 Иначе роль, увидев красное, разберёт своё и не узнает про остальных.
    d4 = stand([("ДОЛЖНИК", 5, 30), ("СПЯЩАЯ", 600, 12)])
    out4, rc4 = run_guard(d4)
    ok &= case("④ активная роль с долгом — КРАСНОЕ, и долг вне окна назван тут же",
               rc4 == 1 and "ДОЛЖНИК" in out4 and "СПЯЩАЯ 12" in out4,
               f"код {rc4}; обе стороны в одном выводе: судимая и непроверенная",
               differ=True)

    # ⑤ АКТИВНЫХ НЕТ ВОВСЕ — самый коварный пустой набор: судить некого.
    d5 = stand([("СПЯЩАЯ", 600, 20), ("ДРУГАЯ", 900, 7)])
    out5, rc5 = run_guard(d5)
    ok &= case("⑤ активных нет вовсе — сказано «проверять было НЕКОГО»",
               "НЕТ" in out5 and "НЕКОГО" in out5 and "читают все" not in out5,
               f"код {rc5}; строка: {next((s.strip() for s in out5.splitlines() if 'активных' in s), '(нет)')[:110]}",
               differ=True)

    # ⑥ МАШИННЫЙ ОТВЕТ. Встраивающий не должен узнавать о непроверенных ролях позже,
    #    чем зовущий глазами: иначе починка чинит только человеческий вывод.
    out6, rc6 = run_guard(d, "--json")
    try:
        answer = json.loads(out6.strip().splitlines()[-1])
    except (ValueError, IndexError):
        answer = {}
    ok &= case("⑥ машинный ответ несёт непроверенные роли, а не только нарушителей",
               isinstance(answer, dict) and answer.get("out_of_window_debt") == 40
               and any(x.get("role") == "СПЯЩАЯ" for x in answer.get("out_of_window", [])),
               f"поля ответа: {sorted(answer) if isinstance(answer, dict) else 'разобрать не вышло'}",
               differ=True)

    # ⑦ ПРЕДЕЛ, НАЗВАННЫЙ ВСЛУХ. Проверка видит ОТМЕТКУ прочитанного, а не понимание.
    #    Случай стои́т в приёмке, чтобы предел был записан, а не забыт: молчание о пределе
    #    читается как охват.
    text_ = CHECK.read_text(encoding="utf-8", errors="replace")
    ok &= case("⑦ ⛔ ЗНАЕМ, ЧТО НЕ ЛОВИМ: подтверждение прочтения ≠ понимание",
               "а не понимание" in text_,
               "предел записан в самом инструменте, где его прочтёт применяющий")

    # ⑧ ЖЁЛТАЯ СТРОКА ДОЕЗЖАЕТ ДО ОБЩЕГО ПРОГОНА. Ровно то, о чём была заявка: роль
    #    зовёт guard-all.py, а не двадцать семь проверок по одной.
    yellow_line = "⚠️ вне окна (90 мин) 8 ролей, их долг НЕ ПРОВЕРЯЛСЯ: 1257 непрочитанных"
    p8 = fake_subguard(["✅ активных ролей 1 из 9 — читают все", yellow_line])
    output8 = via_common(p8)
    ok &= case("⑧ жёлтая строка доезжает до ОБЩЕГО прогона, а не только до прямого вызова",
               "НЕ ПРОВЕРЯЛСЯ" in output8,
               f"общий прогон напечатал: {' ¦ '.join(s.strip() for s in output8.splitlines())[:150]}",
               differ=True)

    # ⑨ ВСТРЕЧНЫЙ: обычные строки НЕ выливаются. Иначе починка утопит красное в зелёном.
    p9 = fake_subguard(["✅ первая", "✅ вторая", "разбор: python что-то.py", "ИТОГ: ✅ сошлось"])
    output9 = via_common(p9)
    ok &= case("⑨ ВСТРЕЧНЫЙ: обычные строки зелёного прогона НЕ выливаются в общий вывод",
               "первая" not in output9 and "разбор:" not in output9,
               f"напечатано строк {len(output9.strip().splitlines())} — только галочка итога; "
               "вылить всё значило бы утопить красное в зелёном", differ=True)

    # ⑩ ОБРАТНЫЙ ХОД. Ломаем общий прогон обратно и требуем, чтобы строка ПОТЕРЯЛАСЬ.
    #    🎯 Без него ⑧ означает «сегодня видно», а не «починка работает».
    d10 = pathlib.Path(tempfile.mkdtemp(prefix="bite-subguard-old-"))
    original_text = COMMON.read_text(encoding="utf-8")
    broken_text = original_text.replace('if l.lstrip().startswith(("⚠️", "ℹ️")):', "if False:", 1)
    if broken_text == original_text:
        ok &= case("⑩ ОБРАТНЫЙ ХОД: с ПРЕЖНИМ общим прогоном случай ⑧ теряется",
                   False,
                   "⛔ НЕ ЗАПУСТИЛСЯ: место переброса в общем прогоне не найдено — он "
                   "менялся, правь приёмку. Молча пропустить нельзя: это зелёный без опыта")
    else:
        (d10 / "guard-all.py").write_text(broken_text, encoding="utf-8")
        shutil.copy(COMMON.with_name("mezo_paths.py"), d10 / "mezo_paths.py")
        # 🩹 ДОГОН (пустой свежий контур пакета, карточка #667): копия guard-all.py лежит
        # ВНЕ контейнера (d10 — голый временный каталог), и её mezo_paths.container_root()
        # не находит .mezosync/mezosync.db подъёмом по дереву — это тот же класс, что уже
        # закрыт в случае ⑥ bite-addressee-dictionary.py: «контейнер отдаём средой». Через
        # importlib загрузка идёт В ЭТОМ ЖЕ процессе (не подпроцессом), поэтому задаём
        # MEZO_CONTAINER переменной окружения на время вызова и возвращаем как было.
        _prev_container = os.environ.get("MEZO_CONTAINER")
        os.environ["MEZO_CONTAINER"] = str(mezo_paths.container_root(__file__))
        try:
            output10 = via_common(p8, common=d10 / "guard-all.py")
        finally:
            if _prev_container is None:
                os.environ.pop("MEZO_CONTAINER", None)
            else:
                os.environ["MEZO_CONTAINER"] = _prev_container
        ok &= case("⑩ ОБРАТНЫЙ ХОД: с ПРЕЖНИМ общим прогоном случай ⑧ теряется",
                   "НЕ ПРОВЕРЯЛСЯ" not in output10,
                   f"прежняя редакция напечатала: {' ¦ '.join(s.strip() for s in output10.splitlines())[:110]} "
                   "— долг восьми ролей пропадал именно здесь", differ=True)
        shutil.rmtree(d10, ignore_errors=True)
    for junk in (p8.parent, p9.parent):
        shutil.rmtree(junk, ignore_errors=True)

    print()
    print(f"{'✅ ВИДИМОСТЬ ДОЛГА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
