# -*- coding: utf-8 -*-
r"""bite-tool-brevity.py — приёмка карточки #586: «подсказка печатается роли один раз,
дальше — строка-ссылка» (общий помощник `mezo_hints.py`, таблица `hint_seen`).

═══ ЧТО ПРОВЕРЯЕТ ═══
Инструменты координации печатали общие пояснения (хвост про неразрешимые ссылки,
разбор замысла новой карточки, порядок снятия объявления о взятии в работу, канон
сохранённой памяти) ЦЕЛИКОМ при КАЖДОМ вызове — той же роли, тем же текстом. Теперь
первый показ паре (роль, ключ подсказки) — целиком; тот же текст той же роли, срок
ещё не истёк, — ОДНА строка-ссылка; смена текста, истёкший срок, отсутствие роли или
`--full` — снова целиком. Эта приёмка гоняет РЕАЛЬНЫЕ места применения (backlog.py,
check-dangling-refs.py, write-message.py, read-messages.py как встречный) на КОПИИ
живой базы координации — живая база не открывается на запись НИ РАЗУ.

═══ СЛУЧАИ (22: ⓪ предпосылка + ①…⑯, ⑱ + поломка ⑱-бис, ⑲, ⑳, ㉑) ═══
  ⓪ предпосылка: таблица hint_seen в копии базы ЕСТЬ — иначе ②③ не проверяют ничего
     (помощник без таблицы печатает ВСЕГДА целиком — сказано вслух, не скрыто)
  ① backlog.py add — первый показ роли паре (роль, ключ) → ПОЛНЫЙ текст блока
     «разбор замысла»
  ② тот же текст той же роли → ОДНА строка-ссылка, полного блока нет
  ③ --full → полный текст ЗАНОВО, независимо от истории показов
  ④ check-dangling-refs.py БЕЗ --role (дважды) → полный текст оба раза, hint_seen
     копии не тронута
  ⑤ ВСТРЕЧНЫЙ (вне механизма подсказок): read-messages.py — разрезанный токен
     подтверждения ленты (первая половина в ПЕРВОЙ строке, вторая — в ПОСЛЕДНЕЙ)
     остался цел; read-messages.py mezo_hints не зовёт, это контроль изоляции
  ⑥ write-message.py: позиция строки «OK #NNNN» от КОНЦА вывода ОДИНАКОВА и при
     полной лекции о неразрешимых ссылках, и при строке-ссылке — сокращение
     хвоста не сдвигает то, что печатается ПОСЛЕ него
  ⑦ backlog.py claim — «🔧 ВЗЯТО В РАБОТУ» присутствует дословно и при первом
     (полном) показе хвоста, и при втором (строке-ссылке)
  ⑧ mezo_hints.подсказка() напрямую: текст сменился при живом сроке → печатается
     ПОЛНОСТЬЮ
  ⑨ срок (TTL) истёк (shown_at подменён на позавчера) → печатается ПОЛНОСТЬЮ
  ⑩ mezo_hints.забыть(conn, role, key) → следующий показ снова ПОЛНЫЙ
  ⑪ НАРОЧНАЯ ПОЛОМКА: в КОПИИ каталога инструментов (не в живом!) из backlog.py
     вырезана строка «🔧 ВЗЯТО В РАБОТУ» — случай ⑦ на этой копии ОБЯЗАН
     покраснеть (приёмка умеет падать); на настоящем инструменте той же командой —
     снова зелёный
  ⑫ ДВЕ РОЛИ с ОДНИМ ключом подсказки — обе видят ПОЛНЫЙ текст при СВОЁМ первом
     показе (чужая история роли не касается)
  ⑬ параметр db_path помощника mezo_hints.подсказка(): соединение mode=ro БЕЗ db_path
     → первый и второй показ ОБА полные (откат, не молчание), таблица hint_seen
     копии не тронута — как было ДО добавления db_path (карточка #586, продолжение)
  ⑭ mode=ro С db_path → первый показ полный, второй — строка-ссылка: запись отметки
     через отдельное короткое соединение по db_path состоялась, conn (ro) не тронут
  ⑮ conn=None, db_path задан → то же поведение, что ⑭ (своё соединение обслуживает
     и чтение, и запись само, без conn вызывающего вовсе)
  ⑯ mode=ro + db_path на несуществующий/непригодный путь → ПОЛНЫЙ текст оба раза,
     БЕЗ падения (запасной путь тоже не удался — откат остаётся в сторону полноты)

  ═══ карточка #593, находка COORD (записка #4930): «читатель ≠ хозяин предмета» ═══
  ⑱ backlog.py add — показ засчитывается РУКЕ (--actor), а не владельцу карточки
     (--role): --actor COORD дважды (полный, потом ссылка), затем --actor PROTO —
     снова полный (свой первый показ, чужая история не мешает)
  ⑱-бис НАРОЧНАЯ ПОЛОМКА: в копии backlog.py возвращена старая строка
     role=(a.role or "").upper() (без mezo_hints.кто_читает) — сценарий ⑱ на этой
     копии ОБЯЗАН покраснеть (приёмка умеет ловить именно эту беду); на настоящем
     инструменте тем же сценарием — снова зелёный (проверено случаем ⑱ выше)
  ⑲ то же для backlog.py list (ключ «backlog-list-full»): --actor COORD дважды,
     затем --role PROTO БЕЗ --actor и БЕЗ MEZO_ROLE в окружении подпроцесса —
     показ засчитан себе (PROTO), не унаследован от чужого --actor
  ⑳ то же для read-phoenix.py (ключ «read-phoenix-canon»): --actor COORD дважды,
     затем --role PROTO без --actor — канон целиком, засчитан себе
  ㉑ переменная среды MEZO_ROLE: list --role PROTO БЕЗ --actor, в окружении
     подпроцесса MEZO_ROLE=COORD → показ в hint_seen копии засчитан COORD

═══ ГРАНИЦЫ — чего эта приёмка НЕ проверяет (сказано вслух, а не скрыто) ═══
  · конкурентную запись в hint_seen (два процесса, одна пара роль+ключ одновременно);
  · поведение при ЗАБЛОКИРОВАННОЙ базе (файл занят другим соединением) — код
    mezo_hints.подсказка() откатывается в сторону полноты любой бедой БД, но
    отдельного стенда с занятой базой здесь нет;
  · экономию в символах/строках — это меряет ОТДЕЛЬНЫЙ инструмент,
    measure-tool-brevity.py (числа, не механизм).

⛔ Живая база (<КОНТУР>/.mezosync/mezosync.db) НЕ изменяется: все прогоны —
на копии (mezo_stand.new + shutil.copy2). Копия каталога инструментов для случая ⑪ —
через mezo_stand.copy_tool (инструмент со всеми соседями, иначе падение «нет модуля»
неотличимо от настоящей поломки).

Флаг --keep — не убирать временные рабочие каталоги (для разбора вручную).
Без аргументов — полный прогон.

Дата: 2026-09-07 07:57 UTC. Карточка #586, #593.
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --keep должен попасть в окружение ДО импорта mezo_stand: тот читает
# MEZO_KEEP_STANDS в момент импорта (см. его же шапку).
if "--keep" in sys.argv:
    os.environ.setdefault("MEZO_KEEP_STANDS", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

SCRIPTS = mezo_paths.live_scripts(__file__)          # .mezosync/scripts (живой, только на чтение)
CONTAINER = mezo_paths.container_root(__file__)      # <КОНТУР>
LIVE_DB = mezo_paths.live_db(__file__)

BACKLOG = str(SCRIPTS / "backlog.py")
READ_MESSAGES = str(SCRIPTS / "read-messages.py")
WRITE_MESSAGE = str(SCRIPTS / "write-message.py")
READ_PHOENIX = str(SCRIPTS / "read-phoenix.py")                    # случай ⑳
REFS = str(CONTAINER / "vnext-tools" / "check-dangling-refs.py")   # зона @PROTO, вызов ПО ПУТИ

sys.path.insert(0, str(SCRIPTS))
import mezo_hints  # noqa: E402 — помощник карточки #586, для случаев ⑧⑨⑩ зовём напрямую

итог: list[tuple[str, bool]] = []


def случай(имя: str, ок: bool, слово: str) -> None:
    итог.append((имя, ок))
    print(f"{'✅' if ок else '🔴'} {имя}")
    print(f"   {слово}")


def run(tool: str, db: Path, *args: str) -> tuple[int, str]:
    """Позвать инструмент с --db КОПИИ. Порядок «--db, затем подкоманда» — как у backlog.py."""
    p = subprocess.run([sys.executable, tool, "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_слитно(tool: str, db: Path, *args: str) -> tuple[int, str]:
    """Как run(), но stdout и stderr МЕРЖАТСЯ в ОДИН поток в реальном порядке записи
    (stderr=subprocess.STDOUT), а не склеиваются как две отдельные строки задним числом.
    Нужен ТОЛЬКО случаю ⑥: там важно, что стои́т ПОСЛЕ строки «OK #NNNN» в реальном
    времени вывода, а склейка «stdout потом stderr» это порядок стирает."""
    p = subprocess.run([sys.executable, tool, "--db", str(db), *args],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or ""


def run_env(tool: str, db: Path, env: dict, *args: str) -> tuple[int, str]:
    """Как run(), но с ЯВНЫМ окружением подпроцесса — нужен случаям ⑲/㉑, где важно,
    видит ли подпроцесс переменную среды MEZO_ROLE (карточка #593, находка COORD #4930:
    показ подсказки обязан читаться по руке — --actor → MEZO_ROLE → --role, см. mezo_hints.кто_читает)."""
    p = subprocess.run([sys.executable, tool, "--db", str(db), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def id_карточки(вывод: str) -> str | None:
    return вывод.split("backlog #")[1].split(" ")[0] if "backlog #" in вывод else None


def забыть_ключи(db: Path, role: str, keys: list[str]) -> None:
    c = sqlite3.connect(str(db))
    for k in keys:
        c.execute("DELETE FROM hint_seen WHERE role=? AND hint_key=?", (role, k))
    c.commit()
    c.close()


def строка_ok_с_конца(текст: str) -> int | None:
    """Номер строки, содержащей «OK #», СЧИТАЯ С КОНЦА (0 — последняя непустая строка)."""
    строки = [л for л in текст.splitlines() if л.strip()]
    for i, л in enumerate(reversed(строки)):
        if "OK #" in л:
            return i
    return None


def main() -> int:
    print("=" * 78)
    print("ПРИЁМКА КАРТОЧКИ #586 — mezo_hints: подсказка один раз, дальше строка-ссылка")
    print("живая база (только чтение, копируется): " + str(LIVE_DB))
    print("=" * 78)

    стенд = mezo_stand.new("bite-tool-brevity-")
    db = стенд / "copy.db"
    import shutil
    shutil.copy2(LIVE_DB, db)

    # ═══ ⓪ ГЕЙТ: таблица hint_seen в копии есть ═══════════════════════════════════
    conn0 = sqlite3.connect(str(db))
    таблицы = {r[0] for r in conn0.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    есть_таблица = "hint_seen" in таблицы
    conn0.close()
    случай("⓪ предпосылка: таблица hint_seen в копии базы ЕСТЬ",
           есть_таблица,
           "таблица на месте — есть на чём различать ①…⑯" if есть_таблица else
           "🔴 ТАБЛИЦЫ НЕТ: без неё помощник печатает ВСЕГДА целиком (откат в сторону "
           "полноты), и случаи ②③ дальше не проверяют НИЧЕГО — сказано здесь вслух, "
           "не скрыто зелёным")

    # ═══ ①②③ backlog.py add — ключ «backlog-add-три-вопроса» ═══════════════════════
    забыть_ключи(db, "PROTO", ["backlog-add-три-вопроса"])
    rc1, out1 = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
                    "--title", "приёмка 586 случай один: первый показ",
                    "--body", "тело стендовой заявки приёмки карточки пятьсот восемьдесят шесть, случай один",
                    "--done-when", "стендовый критерий приёмки: не судится")
    bid1 = id_карточки(out1)
    ТРИ_ВОПРОСА_ПРОЧЕЕ = (
        "есть ли путь дешевле (альтернатива)?",
        "боль в числах: сколько раз и почём (боль в числах)?",
        "чьи руки нужны кроме твоих (зона рук)?",
    )
    блок1 = "💬 разбор замысла" in out1 and all(в in out1 for в in ТРИ_ВОПРОСА_ПРОЧЕЕ)
    случай("① первый показ роли паре (роль, ключ) → ПОЛНЫЙ текст блока «разбор замысла»",
           rc1 == 0 and bool(bid1) and блок1,
           f"backlog #{bid1}: все три вопроса на месте" if блок1 else "блок неполон или отсутствует")

    rc2, out2 = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
                    "--title", "приёмка 586 случай два: второй показ",
                    "--body", "тело стендовой заявки приёмки карточки пятьсот восемьдесят шесть, случай два",
                    "--done-when", "стендовый критерий приёмки: не судится")
    bid2 = id_карточки(out2)
    ссылка2 = "ℹ️ подсказка «backlog-add-три-вопроса» показана" in out2
    полный2_отсутствует = "чьи руки нужны кроме твоих (зона рук)?" not in out2
    случай("② тот же текст той же роли, срок жив → ОДНА строка-ссылка, полного блока нет",
           rc2 == 0 and bool(bid2) and ссылка2 and полный2_отсутствует,
           f"backlog #{bid2}: строка-ссылка есть — {ссылка2}, полного блока нет — {полный2_отсутствует}")

    rc3, out3 = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO", "--full",
                    "--title", "приёмка 586 случай три: --full",
                    "--body", "тело стендовой заявки приёмки карточки пятьсот восемьдесят шесть, случай три",
                    "--done-when", "стендовый критерий приёмки: не судится")
    bid3 = id_карточки(out3)
    блок3 = all(в in out3 for в in ТРИ_ВОПРОСА_ПРОЧЕЕ)
    случай("③ --full → полный текст ЗАНОВО, независимо от истории показов",
           rc3 == 0 and bool(bid3) and блок3,
           f"backlog #{bid3}: полный блок при --full — {блок3}")

    # ═══ ④ check-dangling-refs.py БЕЗ --role, дважды ═══════════════════════════════
    tmp4 = стенд / "случай4.md"
    tmp4.write_text("стендовый текст без пояснения, просто #205 без слова-типа рядом",
                    encoding="utf-8")
    conn4 = sqlite3.connect(str(db))
    строк_до4 = conn4.execute("SELECT COUNT(*) FROM hint_seen").fetchone()[0]
    conn4.close()
    rc4a, out4a = run(REFS, db, "--file", str(tmp4))
    rc4b, out4b = run(REFS, db, "--file", str(tmp4))
    conn4 = sqlite3.connect(str(db))
    строк_после4 = conn4.execute("SELECT COUNT(*) FROM hint_seen").fetchone()[0]
    conn4.close()

    def полный_хвост_refs(вывод: str) -> bool:
        return ("📌 Это ПРЕДУПРЕЖДЕНИЕ" in вывод
                and "📖 СЛОВА, КОТОРЫЕ ПРОВЕРКА СЧИТАЕТ ПОЯСНЯЮЩИМИ" in вывод)

    случай("④ роль не задана (дважды) → ПОЛНЫЙ текст оба раза, hint_seen копии не тронута",
           rc4a == 1 and rc4b == 1 and полный_хвост_refs(out4a) and полный_хвост_refs(out4b)
           and строк_до4 == строк_после4,
           f"полный текст: {полный_хвост_refs(out4a)}/{полный_хвост_refs(out4b)}, "
           f"строк в hint_seen: {строк_до4} → {строк_после4}")

    # ═══ ⑤ ВСТРЕЧНЫЙ: read-messages.py вне механизма подсказок ═════════════════════
    # mezo_hints этот файл не зовёт вовсе — случай подтверждает, что работа над #586
    # не задела СОСЕДНИЙ механизм (разрезанный токен подтверждения ленты).
    conn5 = sqlite3.connect(str(db))
    max_id5 = conn5.execute("SELECT MAX(id) FROM messages").fetchone()[0] or 0
    conn5.execute("UPDATE read_cursors SET last_read_id=? WHERE reader_role='PROTO'",
                  (max(0, max_id5 - 15),))
    if conn5.execute("SELECT changes()").fetchone()[0] == 0:
        conn5.execute("INSERT INTO read_cursors (reader_role, last_read_id) VALUES ('PROTO', ?)",
                      (max(0, max_id5 - 15),))
    conn5.commit()
    conn5.close()
    rc5, out5 = run(READ_MESSAGES, db, "--role", "PROTO", "--limit", "5")
    строки5 = [л for л in out5.splitlines() if л.strip()]
    первая5 = строки5[0] if строки5 else ""
    последняя5 = строки5[-1] if строки5 else ""
    ок5 = ("Токен разрезан: ПЕРВАЯ половина" in первая5) and ("--ack <первая>-" in последняя5)
    случай("⑤ ВСТРЕЧНЫЙ: read-messages.py (mezo_hints не зовёт) — разрезанный токен цел",
           rc5 == 0 and ок5,
           "первая строка несёт первую половину, последняя — вторую" if ок5
           else f"🔴 нарушен контракт токена; первая={первая5[:70]!r} последняя={последняя5[:70]!r}")

    # ═══ ⑥ write-message.py: позиция «OK #NNNN» от конца ═══════════════════════════
    забыть_ключи(db, "PROTO", ["refs-предупреждение-не-отказ", "refs-слова-пояснения"])
    rc6a, out6a = run_слитно(WRITE_MESSAGE, db, "--role", "PROTO",
                             "--body", "стендовая проверка приёмки 586: без пояснения ссылка "
                                       "#601, попытка первая")
    rc6b, out6b = run_слитно(WRITE_MESSAGE, db, "--role", "PROTO",
                             "--body", "стендовая проверка приёмки 586: без пояснения ссылка "
                                       "#601, попытка вторая")
    поз_а6 = строка_ok_с_конца(out6a)
    поз_б6 = строка_ok_с_конца(out6b)
    лекция6 = "📌 Это ПРЕДУПРЕЖДЕНИЕ" in out6a
    ссылка6 = "ℹ️ подсказка «refs-предупреждение-не-отказ» показана" in out6b
    случай("⑥ «OK #NNNN» — позиция от конца ОДИНАКОВА при полной лекции и при строке-ссылке",
           rc6a == 0 and rc6b == 0 and поз_а6 is not None and поз_б6 is not None
           and поз_а6 == поз_б6 and лекция6 and ссылка6,
           f"позиция от конца: первый прогон {поз_а6} (полная лекция={лекция6}), "
           f"второй {поз_б6} (строка-ссылка={ссылка6})")

    # ═══ ⑦ backlog.py claim — «🔧 ВЗЯТО В РАБОТУ» в обоих показах ═══════════════════
    rc7add, out7add = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
                          "--title", "приёмка 586 случай семь: карточка для claim",
                          "--body", "тело карточки для проверки claim и хвоста снятия",
                          "--done-when", "стендовый критерий приёмки: не судится")
    bid7 = id_карточки(out7add)
    забыть_ключи(db, "PROTO", ["backlog-claim-как-снять"])
    rc7a, out7a = run(BACKLOG, db, "claim", bid7, "--actor", "PROTO",
                      "--note", "стендовое взятие, первый показ")
    rc7b, out7b = run(BACKLOG, db, "claim", bid7, "--actor", "PROTO",
                      "--note", "стендовое взятие, второй показ")
    маркер_хвоста = "Видно коллегам при пробуждении"
    случай("⑦ «🔧 ВЗЯТО В РАБОТУ» присутствует и при полном хвосте, и при строке-ссылке",
           rc7a == 0 and rc7b == 0
           and "🔧 ВЗЯТО В РАБОТУ" in out7a and "🔧 ВЗЯТО В РАБОТУ" in out7b
           and маркер_хвоста in out7a and маркер_хвоста not in out7b,
           f"backlog #{bid7}: первый показ полный — {маркер_хвоста in out7a}, "
           f"второй сокращён — {маркер_хвоста not in out7b}")

    # ═══ ⑧⑨⑩ mezo_hints.подсказка()/забыть() напрямую ═══════════════════════════════
    conn89 = sqlite3.connect(str(db))

    ключ8 = "bite-586-текст-меняется"
    mezo_hints.забыть(conn89, "PROTO", ключ8)
    п1 = mezo_hints.подсказка(conn89, "PROTO", ключ8, "текст версии один", ttl_hours=24)
    п2 = mezo_hints.подсказка(conn89, "PROTO", ключ8, "текст версии один", ttl_hours=24)
    п3 = mezo_hints.подсказка(conn89, "PROTO", ключ8, "текст версии ДВА, он изменился", ttl_hours=24)
    случай("⑧ текст сменился при живом сроке → печатается ПОЛНОСТЬЮ",
           п1 is True and п2 is False and п3 is True,
           f"первый показ={п1}, повтор тем же текстом={п2}, после смены текста={п3}")

    ключ9 = "bite-586-срок-истёк"
    mezo_hints.забыть(conn89, "PROTO", ключ9)
    mezo_hints.подсказка(conn89, "PROTO", ключ9, "текст с истекающим сроком", ttl_hours=24)
    позавчера = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        tzinfo=None, microsecond=0).isoformat()
    conn89.execute("UPDATE hint_seen SET shown_at=? WHERE role='PROTO' AND hint_key=?",
                  (позавчера, ключ9))
    conn89.commit()
    п9 = mezo_hints.подсказка(conn89, "PROTO", ключ9, "текст с истекающим сроком", ttl_hours=24)
    случай("⑨ срок (TTL) истёк (shown_at подменён на позавчера) → печатается ПОЛНОСТЬЮ",
           п9 is True, f"показ после истечения TTL: {п9}")

    ключ10 = "bite-586-забыть"
    mezo_hints.забыть(conn89, "PROTO", ключ10)
    п10_первый = mezo_hints.подсказка(conn89, "PROTO", ключ10, "текст для забыть()", ttl_hours=24)
    п10_короткий = mezo_hints.подсказка(conn89, "PROTO", ключ10, "текст для забыть()", ttl_hours=24)
    удалено10 = mezo_hints.забыть(conn89, "PROTO", ключ10)
    п10_снова = mezo_hints.подсказка(conn89, "PROTO", ключ10, "текст для забыть()", ttl_hours=24)
    случай("⑩ забыть(conn, role, key) → следующий показ снова ПОЛНЫЙ",
           п10_первый is True and п10_короткий is False and удалено10 == 1 and п10_снова is True,
           f"первый={п10_первый}, до забыть={п10_короткий}, удалено строк={удалено10}, "
           f"после забыть={п10_снова}")
    conn89.close()

    # ═══ ⑪ НАРОЧНАЯ ПОЛОМКА в КОПИИ каталога инструментов ═══════════════════════════
    сломанный_стенд = mezo_stand.new("bite-tool-brevity-broken-")
    сломанный = mezo_stand.copy_tool(Path(BACKLOG), сломанный_стенд)
    текст11 = сломанный.read_text(encoding="utf-8")
    МАРКЕР11 = 'print(f"🔧 ВЗЯТО В РАБОТУ #{a.id}{чужая} «{title[:50]}» до {until[:16]} UTC")'
    if МАРКЕР11 not in текст11:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь строки «ВЗЯТО В РАБОТУ» не найден "
                         "в backlog.py — обратный ход ⑪ ставить не на чем")
    испорченный11 = текст11.replace(
        МАРКЕР11, 'print(f"🔧 нечто иное #{a.id}{чужая} «{title[:50]}» до {until[:16]} UTC")', 1)
    if испорченный11 == текст11:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена ⑪ не сработала — обратный ход "
                         "не поставлен, зелёное было бы ложным")
    сломанный.write_text(испорченный11, encoding="utf-8")

    rc11add, out11add = run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
                            "--title", "приёмка 586 случай одиннадцать: нарочная поломка",
                            "--body", "тело карточки для проверки нарочной поломки claim",
                            "--done-when", "стендовый критерий приёмки: не судится")
    bid11 = id_карточки(out11add)
    rc11a, out11a = run(str(сломанный), db, "claim", bid11, "--actor", "PROTO",
                        "--note", "взятие на СЛОМАННОЙ копии инструментов")
    красное_поймано = "🔧 ВЗЯТО В РАБОТУ" not in out11a
    rc11b, out11b = run(BACKLOG, db, "claim", bid11, "--actor", "PROTO",
                        "--note", "взятие на настоящем инструменте после поломки")
    снова_зелёное = "🔧 ВЗЯТО В РАБОТУ" in out11b
    случай("⑪ НАРОЧНАЯ ПОЛОМКА в копии каталога инструментов → приёмка ловит красное, "
           "на настоящем инструменте — снова зелёное",
           красное_поймано and снова_зелёное,
           ("ждём красное — получено красное" if красное_поймано
            else "🔴 поломка НЕ поймана — красное ожидалось, а его нет")
           + "; " + ("на настоящем инструменте снова зелено" if снова_зелёное
                     else "🔴 настоящий инструмент тоже красен — приёмка отравлена своей же подсадкой"))
    mezo_stand.release(сломанный_стенд)

    # ═══ ⑫ ДВЕ РОЛИ с ОДНИМ ключом ══════════════════════════════════════════════════
    забыть_ключи(db, "PROTO", ["refs-предупреждение-не-отказ", "refs-слова-пояснения"])
    забыть_ключи(db, "CORE", ["refs-предупреждение-не-отказ", "refs-слова-пояснения"])
    tmp12 = стенд / "случай12.md"
    tmp12.write_text("вторая стендовая проверка: голая #712 без слова-типа рядом",
                     encoding="utf-8")
    rc12a, out12a = run(REFS, db, "--file", str(tmp12), "--role", "PROTO")
    rc12b, out12b = run(REFS, db, "--file", str(tmp12), "--role", "CORE")
    случай("⑫ ДВЕ РОЛИ с ОДНИМ ключом — обе видят ПОЛНЫЙ текст при СВОЁМ первом показе",
           rc12a == 1 and rc12b == 1 and полный_хвост_refs(out12a) and полный_хвост_refs(out12b),
           f"PROTO полный={полный_хвост_refs(out12a)}, CORE полный={полный_хвост_refs(out12b)} "
           "— чужая история роли не заслоняет собственный первый показ")

    # ═══ ⑬⑭⑮⑯ mezo_hints.подсказка(..., db_path=...) — отметка через mode=ro ═══════════
    # Отдельные короткие mode=ro-соединения к ТОЙ ЖЕ копии базы — как открывает её
    # role-brief.py (resolve_db(..., readonly=True) + sqlite3.connect("file:...?mode=ro",
    # uri=True), см. .mezosync/scripts/role-brief.py:355-362). mezo_hints зовём напрямую,
    # как в случаях ⑧⑨⑩ — здесь проверяется сам помощник, а не инструмент вокруг него.
    def ro_conn():
        return sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)

    забыть_ключи(db, "PROTO", ["bite-586-ro-без-db-path", "bite-586-ro-с-db-path",
                               "bite-586-conn-none-db-path", "bite-586-ro-db-path-негодный"])

    ключ13 = "bite-586-ro-без-db-path"
    conn13a = ro_conn()
    п13_1 = mezo_hints.подсказка(conn13a, "PROTO", ключ13, "текст случая тринадцать",
                                 ttl_hours=24)
    conn13a.close()
    conn13b = ro_conn()
    п13_2 = mezo_hints.подсказка(conn13b, "PROTO", ключ13, "текст случая тринадцать",
                                 ttl_hours=24)
    conn13b.close()
    conn13_check = sqlite3.connect(str(db))
    строк13 = conn13_check.execute(
        "SELECT COUNT(*) FROM hint_seen WHERE role=? AND hint_key=?",
        ("PROTO", ключ13)).fetchone()[0]
    conn13_check.close()
    случай("⑬ mode=ro БЕЗ db_path → первый и второй показ ОБА полные (откат, не молчание), "
           "таблица не тронута",
           п13_1 is True and п13_2 is True and строк13 == 0,
           f"первый показ полный={п13_1}, второй показ полный={п13_2}, "
           f"строк в hint_seen для ключа={строк13} (ожидание: 0)")

    ключ14 = "bite-586-ro-с-db-path"
    conn14a = ro_conn()
    п14_1 = mezo_hints.подсказка(conn14a, "PROTO", ключ14, "текст случая четырнадцать",
                                 ttl_hours=24, db_path=str(db))
    conn14a.close()
    conn14b = ro_conn()
    п14_2 = mezo_hints.подсказка(conn14b, "PROTO", ключ14, "текст случая четырнадцать",
                                 ttl_hours=24, db_path=str(db))
    conn14b.close()
    случай("⑭ mode=ro С db_path → первый показ ПОЛНЫЙ, второй — строка-ссылка, "
           "отметка записана через отдельное соединение",
           п14_1 is True and п14_2 is False,
           f"первый показ полный={п14_1}, второй показ полный={п14_2} (False — строка-ссылка, "
           "значит отметка от первого показа прижилась в hint_seen копии через db_path)")

    ключ15 = "bite-586-conn-none-db-path"
    п15_1 = mezo_hints.подсказка(None, "PROTO", ключ15, "текст случая пятнадцать",
                                 ttl_hours=24, db_path=str(db))
    п15_2 = mezo_hints.подсказка(None, "PROTO", ключ15, "текст случая пятнадцать",
                                 ttl_hours=24, db_path=str(db))
    случай("⑮ conn=None, db_path задан → то же, что ⑭ (своё соединение читает и пишет само)",
           п15_1 is True and п15_2 is False,
           f"первый показ полный={п15_1}, второй показ полный={п15_2} (False — строка-ссылка)")

    ключ16 = "bite-586-ro-db-path-негодный"
    негодный_путь = str(стенд / "нет-такого-каталога" / "bad.db")
    conn16a = ro_conn()
    п16_1 = mezo_hints.подсказка(conn16a, "PROTO", ключ16, "текст случая шестнадцать",
                                 ttl_hours=24, db_path=негодный_путь)
    conn16a.close()
    conn16b = ro_conn()
    п16_2 = mezo_hints.подсказка(conn16b, "PROTO", ключ16, "текст случая шестнадцать",
                                 ttl_hours=24, db_path=негодный_путь)
    conn16b.close()
    случай("⑯ mode=ro + db_path на несуществующий/непригодный путь → ПОЛНЫЙ текст оба раза, "
           "БЕЗ падения",
           п16_1 is True and п16_2 is True,
           f"первый показ полный={п16_1}, второй показ полный={п16_2} — запасной путь тоже "
           "не удался, но помощник не упал и подсказка не промолчала")

    # ═══ ⑱ + ⑱-бис — «читатель ≠ хозяин карточки» (карточка #593, находка COORD #4930) ═══
    # backlog.py add ЗАПИСЫВАЛ показ подсказки на ВЛАДЕЛЬЦА карточки (--role), а не на
    # РУКУ, что её завела (--actor): чужая роль в зоне PROTO списывала показ на PROTO,
    # и настоящий читатель подсказку своей рукой уже не видел. Функция ниже гоняет один
    # и тот же сценарий на НАСТОЯЩЕМ инструменте (случай ⑱, обязан быть зелёным) и на ЕГО
    # СЛОМАННОЙ копии (случай ⑱-бис, обязан быть красным — иначе эта приёмка не умеет
    # ловить именно тот класс беды, ради которого заведена).
    def сценарий_18(add_tool: str, env: dict | None = None) -> tuple[bool, str]:
        """env=None — настоящий инструмент, зовём через run() как везде. env задан —
        КОПИЯ на временном стенде ВНЕ каталога-контейнера (mezo_stand кладёт её во
        %TEMP%): её собственный mezo_paths.py (уехавший туда же СОСЕДОМ, см.
        mezo_stand.copy_tool) не находит .mezosync/mezosync.db подъёмом по дереву —
        это ДРУГАЯ, известная беда («второй замок», mezo_paths.py:309-319), не та,
        что проверяет этот случай. MEZO_CONTAINER в окружении подпроцесса снимает
        её явно, и красное ⑱-бис остаётся ЗА СЧЁТ вырезанного mezo_hints.кто_читает,
        а не за счёт побочного падения на чужом замке (тот же принцип, что у измерения
        «check-fires-for-the-wrong-reason» — красное обязано красить по СВОЕЙ причине)."""
        вызов = (lambda *args: run_env(add_tool, db, env, *args)) if env is not None \
            else (lambda *args: run(add_tool, db, *args))
        забыть_ключи(db, "COORD", ["backlog-add-три-вопроса"])
        забыть_ключи(db, "PROTO", ["backlog-add-три-вопроса"])
        rc18a, out18a = вызов("add", "--role", "PROTO", "--actor", "COORD",
                         "--title", "приёмка 593 случай восемнадцать: читатель COORD, показ первый",
                         "--body", "тело стендовой заявки приёмки случая восемнадцать, показ первый",
                         "--done-when", "стендовый критерий приёмки: не судится")
        rc18b, out18b = вызов("add", "--role", "PROTO", "--actor", "COORD",
                             "--title", "приёмка 593 случай восемнадцать: читатель COORD, показ второй",
                             "--body", "тело стендовой заявки приёмки случая восемнадцать, показ второй",
                             "--done-when", "стендовый критерий приёмки: не судится")
        ссылка18 = "ℹ️ подсказка «backlog-add-три-вопроса» показана" in out18b
        rc18c, out18c = вызов("add", "--role", "PROTO", "--actor", "PROTO",
                             "--title", "приёмка 593 случай восемнадцать: читатель PROTO, показ третий",
                             "--body", "тело стендовой заявки приёмки случая восемнадцать, показ третий",
                             "--done-when", "стендовый критерий приёмки: не судится")
        полный18 = ("💬 разбор замысла" in out18c
                    and "чьи руки нужны кроме твоих (зона рук)?" in out18c)
        conn18 = sqlite3.connect(str(db))
        coord18 = conn18.execute("SELECT COUNT(*) FROM hint_seen WHERE role=? AND hint_key=?",
                                 ("COORD", "backlog-add-три-вопроса")).fetchone()[0]
        proto18 = conn18.execute("SELECT COUNT(*) FROM hint_seen WHERE role=? AND hint_key=?",
                                 ("PROTO", "backlog-add-три-вопроса")).fetchone()[0]
        conn18.close()
        ок = (rc18a == 0 and rc18b == 0 and rc18c == 0 and ссылка18 and полный18
              and coord18 == 1 and proto18 == 1)
        return ок, (f"коды возврата {rc18a}/{rc18b}/{rc18c}, второй показ (--actor COORD) дал "
                    f"строку-ссылку={ссылка18}, третий показ (--actor PROTO) дал ПОЛНЫЙ "
                    f"текст={полный18}, hint_seen копии: COORD={coord18} PROTO={proto18}")

    ок18, слово18 = сценарий_18(BACKLOG)
    случай("⑱ читатель ≠ хозяин карточки — backlog add: показ засчитывается --actor, "
           "не --role", ок18, слово18)

    сломанный_стенд18 = mezo_stand.new("bite-tool-brevity-broken-actor-")
    сломанный18 = mezo_stand.copy_tool(Path(BACKLOG), сломанный_стенд18)
    текст18 = сломанный18.read_text(encoding="utf-8")
    СТАРАЯ_СТРОКА18 = (
        'mezo_hints.подсказка(conn, mezo_hints.кто_читает(a.actor, a.role), '
        '"backlog-add-три-вопроса",\n'
        '                         ТЕКСТ_ВОПРОСОВ, full=a.full)'
    )
    if СТАРАЯ_СТРОКА18 not in текст18:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь вызова кто_читает() не найден "
                         "в backlog.py — обратный ход ⑱-бис ставить не на чем")
    испорченный18 = текст18.replace(
        СТАРАЯ_СТРОКА18,
        'mezo_hints.подсказка(conn, (a.role or "").upper(), "backlog-add-три-вопроса",\n'
        '                         ТЕКСТ_ВОПРОСОВ, full=a.full)', 1)
    if испорченный18 == текст18:
        raise SystemExit("ПРИЁМКА НЕ СОСТОЯЛАСЬ: замена ⑱-бис не сработала — обратный ход "
                         "не поставлен, зелёное было бы ложным")
    сломанный18.write_text(испорченный18, encoding="utf-8")

    env18бис = os.environ.copy()
    env18бис["MEZO_CONTAINER"] = str(CONTAINER)   # см. докстринг сценарий_18: снимаем «второй
    # замок» (mezo_paths.py:309-319) явно, чтобы краснело ИМЕННО от вырезанного кто_читает
    ок18бис, слово18бис = сценарий_18(str(сломанный18), env=env18бис)
    случай("⑱-бис НАРОЧНАЯ ПОЛОМКА (вернули role=(a.role or \"\").upper()) → случай ⑱ "
           "на СЛОМАННОЙ копии ОБЯЗАН покраснеть",
           (not ок18бис),
           ("ждём красное — получено красное: " + слово18бис) if not ок18бис
           else "🔴 поломка НЕ поймана — эта приёмка не умеет ловить класс беды #4930: " + слово18бис)
    mezo_stand.release(сломанный_стенд18)

    # ═══ ⑲ то же для backlog.py list — ключ «backlog-list-full» ═══════════════════
    # digest_hidden (хвост про срез критерия) печатается, только когда в списке есть
    # хоть одна открытая карточка с критерием и БЕЗ --full — заводим её явно, чтобы
    # случай не зависел от того, что уже накопилось в копии живой базы до него.
    run(BACKLOG, db, "add", "--role", "PROTO", "--actor", "PROTO",
        "--title", "приёмка 593 случай девятнадцать: карточка с критерием для digest_hidden",
        "--body", "тело стендовой заявки приёмки случая девятнадцать",
        "--done-when", "стендовый критерий приёмки: не судится")
    забыть_ключи(db, "COORD", ["backlog-list-full"])
    забыть_ключи(db, "PROTO", ["backlog-list-full"])
    ПОЛНЫЙ_ХВОСТ_LIST = "ℹ️ срез критерия у карточек скрыт"
    rc19a, out19a = run(BACKLOG, db, "list", "--role", "PROTO", "--actor", "COORD")
    rc19b, out19b = run(BACKLOG, db, "list", "--role", "PROTO", "--actor", "COORD")
    ссылка19 = "ℹ️ подсказка «backlog-list-full» показана" in out19b
    полный19a = ПОЛНЫЙ_ХВОСТ_LIST in out19a
    env19 = os.environ.copy()
    env19.pop("MEZO_ROLE", None)   # окружение подпроцесса БЕЗ MEZO_ROLE — падать некуда, кроме --role
    rc19c, out19c = run_env(BACKLOG, db, env19, "list", "--role", "PROTO")
    полный19c = ПОЛНЫЙ_ХВОСТ_LIST in out19c   # PROTO своей рукой видит это ВПЕРВЫЕ — не COORD'ом
    случай("⑲ backlog list — читатель ≠ хозяин, второй показ ссылкой, PROTO без --actor "
           "видит целиком (засчитан себе, не COORD)",
           rc19a == 0 and rc19b == 0 and rc19c == 0 and полный19a and ссылка19 and полный19c,
           f"первый показ (--actor COORD) полный={полный19a}, второй — ссылка={ссылка19}, "
           f"третий (--role PROTO, без --actor, без MEZO_ROLE в среде) полный={полный19c}")

    # ═══ ⑳ то же для read-phoenix.py — ключ «read-phoenix-canon» ══════════════════
    забыть_ключи(db, "COORD", ["read-phoenix-canon"])
    забыть_ключи(db, "PROTO", ["read-phoenix-canon"])
    МАРКЕР_КАНОНА = "📌 КАНОН — ИСТОЧНИК ПРАВДЫ БД"
    rc20a, out20a = run(READ_PHOENIX, db, "--role", "PROTO", "--actor", "COORD")
    rc20b, out20b = run(READ_PHOENIX, db, "--role", "PROTO", "--actor", "COORD")
    ссылка20 = "ℹ️ подсказка «read-phoenix-canon» показана" in out20b
    полный20a = МАРКЕР_КАНОНА in out20a
    rc20c, out20c = run(READ_PHOENIX, db, "--role", "PROTO")
    полный20c = МАРКЕР_КАНОНА in out20c
    случай("⑳ read-phoenix.py — читатель ≠ хозяин памяти: --actor COORD дважды (полный, "
           "потом ссылка), --role PROTO без --actor видит канон целиком (засчитан себе)",
           rc20a == 0 and rc20b == 0 and rc20c == 0 and полный20a and ссылка20 and полный20c,
           f"первый показ (--actor COORD) полный={полный20a}, второй — ссылка={ссылка20}, "
           f"третий (--role PROTO без --actor) полный={полный20c}")

    # ═══ ㉑ окружение MEZO_ROLE — засчитывается, когда --actor не передан ══════════
    забыть_ключи(db, "COORD", ["backlog-list-full"])
    забыть_ключи(db, "PROTO", ["backlog-list-full"])
    env21 = os.environ.copy()
    env21["MEZO_ROLE"] = "COORD"
    rc21, out21 = run_env(BACKLOG, db, env21, "list", "--role", "PROTO")
    conn21 = sqlite3.connect(str(db))
    coord21 = conn21.execute("SELECT COUNT(*) FROM hint_seen WHERE role=? AND hint_key=?",
                             ("COORD", "backlog-list-full")).fetchone()[0]
    proto21 = conn21.execute("SELECT COUNT(*) FROM hint_seen WHERE role=? AND hint_key=?",
                             ("PROTO", "backlog-list-full")).fetchone()[0]
    conn21.close()
    полный21 = ПОЛНЫЙ_ХВОСТ_LIST in out21
    случай("㉑ переменная среды MEZO_ROLE=COORD, list --role PROTO БЕЗ --actor → показ "
           "в hint_seen копии засчитан COORD, а не PROTO",
           rc21 == 0 and полный21 and coord21 == 1 and proto21 == 0,
           f"полный текст={полный21}, hint_seen копии: COORD={coord21}, PROTO={proto21} "
           "(ожидание: PROTO=0 — среда победила владельца предмета)")

    mezo_stand.release(стенд)

    print("")
    print("=" * 78)
    красных = [и for и, ок in итог if not ок]
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(итог)} (⓪ предпосылка + ①…⑯, ⑱+⑱-бис, ⑲, ⑳, ㉑)")
    print("⚖️ ГРАНИЦА: конкурентная запись в hint_seen, заблокированная база и экономия")
    print("   в символах этой приёмкой НЕ проверяются (последнее — measure-tool-brevity.py).")
    if красных:
        print(f"🔴 ПРОВАЛЕНО {len(красных)}: {' · '.join(красных)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
