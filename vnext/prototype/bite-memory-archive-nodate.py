#!/usr/bin/env python
# SURFACES: memory
# -*- coding: utf-8 -*-
"""ПРИЁМКА карточки #556: разгрузка памяти называет ПОСЛЕДСТВИЕ у блока без даты.

ПРЕДМЕТ. Блок, в тексте которого нет ДАТЫ, механизм держит от архива и честно говорит
«возраст мерить нечем — смотри сам». Правда — но без последствия: такой приговор
НЕ ИЗМЕНИТСЯ НИКОГДА, потому что дата в тексте сама не появится. Строка читалась как
оговорка осторожного механизма, то есть как «подожди», а означала «чини».
⚡ КЛАСС: честное «я не знаю» и ВЕЧНЫЙ отказ выглядят одинаково. Первое ждут, второе
чинят — а текст один и тот же.

Найдено @OPSSRE 05.09 06:37 UTC на своей памяти (записка #4792), разрешение и приёмка
@PROTO (записка #4794 §④): «Ⓐ+Ⓑ — да, твоей рукой».

⚖️ ЧЕМ СУДИМ. Часть случаев зовёт `advise()` напрямую — там предмет это ОДИН приговор.
Часть строит НАСТОЯЩИЙ раздел памяти во временной базе и зовёт `show()` — там предмет
это ИТОГ ЧИСЛОМ, и проверить его на отдельном приговоре нельзя по построению.
⛔ Живая база только ЧИТАЕТСЯ (случай ⑥), и только чужие разделы — ни одного переноса.
"""
from __future__ import annotations

import datetime
import hashlib
import importlib.util
import io
import pathlib
import re
import sqlite3
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
TOOL = HERE / "memory-archive.py"

spec = importlib.util.spec_from_file_location("memarch", TOOL)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

TODAY = datetime.date(2026, 9, 5)
cases: list[tuple[str, str, str, bool]] = []


def record_case(name: str, expected: str, actual: str) -> None:
    ok = expected == actual
    cases.append((name, expected, actual, ok))
    print(f"  {'✅' if ok else '🔴'} {name}")
    print(f"      ждали: {expected} · вышло: {actual}")


def verdict(text: str) -> tuple[str, str, bool]:
    return m.advise(text, TODAY)


def render_section(body: str) -> str:
    """Настоящий путь показа: временная база + show(). Возвращает весь вывод."""
    with tempfile.TemporaryDirectory(dir=str(HERE)) as tmp:
        db_path = pathlib.Path(tmp) / "t.db"
        c = sqlite3.connect(db_path)
        c.execute("CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT)")
        c.execute("INSERT INTO phoenix VALUES ('X','state',?,'2026-09-05T06:00:00Z')", (body,))
        c.commit()
        saved_stdout, sys.stdout = sys.stdout, io.StringIO()
        try:
            m.show(c, "X", "state")
            return sys.stdout.getvalue()
        finally:
            sys.stdout = saved_stdout
            c.close()


# ── тексты. У «архивной по возрасту» приметы (⚰️ · урок · снято…) возраст ЕСТЬ условие ──
NO_DATE = "## ⚰️ надгробие: правило снято\nурок оплачен, разбор ниже\nтело блока\n"
WITH_DATE = "## ⚰️ надгробие 2026-08-01: правило снято\nурок оплачен\nтело блока\n"
CLOSED_NO_DATE = "## работа закрыт, сделано\nподробности замера\n"
NO_MARKERS = "## просто раздел\nникаких примет тут нет\n"
HOT = "## ⛔ ЗАПРЕТ действует\nправо, слово владельца\n"

print("ПРИЁМКА карточки #556 · разгрузка памяти: последствие у блока без даты")
print(f"инструмент: {TOOL}")
reference_hash = hashlib.md5(TOOL.read_bytes()).hexdigest()
original_bytes = TOOL.read_bytes()          # 🔴 БАЙТЫ, не текст: запись текстом
original_text = original_bytes.decode("utf-8")    #    переводит концы строк, и восстановление
                                         #    вернёт содержимое, но не байты (поймано
                                         #    отпечатком на первом прогоне 05.09 07:47)
print(f"отпечаток эталона: {reference_hash}")
print("-" * 88)

# ⓪ КОНТРОЛЬ ПЕРВЫМ — не зелен контроль, встречные не значат ничего
mark, why, holds = verdict(HOT)
record_case("⓪ контроль: горячий блок судится как раньше", "🔥 · не держится", f"{mark} · {'держится' if holds else 'не держится'}")

# ① Ⓐ ПОСЛЕДСТВИЕ НАЗВАНО В САМОЙ СТРОКЕ
mark, why, holds = verdict(NO_DATE)
has_consequence = "НЕ ИЗМЕНИТСЯ САМ НИКОГДА" in why and "ПРОСТАВЬ ДАТУ" in why
record_case("① Ⓐ приговор несёт ПОСЛЕДСТВИЕ, а не только причину",
       "⚖️ · последствие названо · держится",
       f"{mark} · {'последствие названо' if has_consequence else '🔴 только причина'} · "
       f"{'держится' if holds else 'не держится'}")

# ③ ВСТРЕЧНЫЙ ГЛАВНЫЙ: та же примета, но ДАТА ЕСТЬ ⇒ ни строки, ни счёта
mark, why, holds = verdict(WITH_DATE)
record_case("③ встречный: дата ЕСТЬ ⇒ новой строки нет и в счёт не идёт",
       "последствия нет · не держится",
       f"{'🔴 последствие названо' if 'НЕ ИЗМЕНИТСЯ' in why else 'последствия нет'} · "
       f"{'держится' if holds else 'не держится'}")

# ③b ВСТРЕЧНЫЙ: примета архивная, но ВНЕ возрастной группы — возраст ей не нужен
mark, why, holds = verdict(CLOSED_NO_DATE)
record_case("③b встречный: закрытая работа без даты ⇒ её никто не держит",
       "📦 · не держится", f"{mark} · {'держится' if holds else 'не держится'}")

# ③c ВСТРЕЧНЫЙ: примет нет вовсе — «дат нет» тут не беда, а обычное дело
mark, why, holds = verdict(NO_MARKERS)
record_case("③c встречный: примет нет ⇒ в счёт не идёт (иначе признак горел бы всегда)",
       "⚪ · не держится", f"{mark} · {'держится' if holds else 'не держится'}")

# ② Ⓑ ИТОГ ЧИСЛОМ — на НАСТОЯЩЕМ пути показа, два таких блока в разделе
output = render_section(NO_DATE + "\n" + NO_DATE.replace("надгробие", "надгробие второе")
                       + "\n" + WITH_DATE + "\n" + HOT)
match = re.search(r"БЛОКОВ БЕЗ ДАТЫ: (\d+) · суммарно (\d+) знаков", output)
record_case("② Ⓑ итог числом: два таких блока сосчитаны, третий и четвёртый — нет",
       "число 2 · размер больше нуля",
       (f"число {match.group(1)} · размер {'больше нуля' if int(match.group(2)) > 0 else '0'}")
       if match else "🔴 строки итога НЕТ ВОВСЕ")

# ④ ВТОРОЙ ВСТРЕЧНЫЙ: таких блоков НЕТ ⇒ итоговой строки быть НЕ ДОЛЖНО
clean_output = render_section(HOT + "\n" + WITH_DATE + "\n" + CLOSED_NO_DATE)
record_case("④ встречный: таких блоков нет ⇒ итоговой строки НЕТ (ноль не горит)",
       "строки итога нет",
       "🔴 строка итога напечатана" if "БЛОКОВ БЕЗ ДАТЫ" in clean_output else "строки итога нет")

# ⑤ ПОРЧА В САМОМ ИНСТРУМЕНТЕ — обезврежен признак «дат в блоке нет»
print("  … ставлю порчу: обезвреживаю признак «дат в блоке нет» в самом инструменте")
target_line = "if archive_by_age and age_days is None:"
corrupted_text = original_text.replace(target_line, "if archive_by_age and False:")
print(f"  … порча изменила текст: {corrupted_text != original_text}")
if corrupted_text == original_text:
    print("  🔴 ОТКАЗ: порча НЕ применилась — прогон ничего не докажет")
    sys.exit(2)
failed_under_corruption: list[str] = []
try:
    TOOL.write_bytes(corrupted_text.encode("utf-8"))
    spec2 = importlib.util.spec_from_file_location("memarch_b", TOOL)
    mb = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(mb)
    mark2, why2, holds2 = mb.advise(NO_DATE, TODAY)
    if "НЕ ИЗМЕНИТСЯ САМ НИКОГДА" not in why2:
        failed_under_corruption.append("①")
    if not holds2:
        failed_under_corruption.append("②")
    _, _, holds3 = mb.advise(WITH_DATE, TODAY)          # встречный обязан УСТОЯТЬ
    counter_intact = not holds3
finally:
    TOOL.write_bytes(original_bytes)                  # ⛔ БЕЗУСЛОВНО и ПОБАЙТНО
    intact = hashlib.md5(TOOL.read_bytes()).hexdigest() == reference_hash
    print(f"  ♻️ инструмент восстановлен: отпечаток {'СОВПАЛ ✅' if intact else '🔴 РАЗОШЁЛСЯ'}")
record_case("⑤ ПОРЧА: без признака ① и ② краснеют, встречный ③ цел",
       "пали ①②, встречный цел",
       f"пали {''.join(failed_under_corruption) or 'никто'}, встречный "
       f"{'цел' if counter_intact else '🔴 тоже упал'}")

# ⑥ ЖИВАЯ ПАМЯТЬ НЕСКОЛЬКИХ РОЛЕЙ — только чтение, ни одного переноса
conn = sqlite3.connect(f"file:{m.mezo_paths.live_db()}?mode=ro", uri=True)
rows = conn.execute("SELECT role, section, body FROM phoenix ORDER BY role, section").fetchall()
by_role: dict[str, int] = {}
failed = []
for role, section, body in rows:
    try:
        chunks, _ = m.blocks(body or "")
        n = sum(1 for chunk in chunks if m.advise(chunk["тело"], TODAY)[2])
        by_role[role] = by_role.get(role, 0) + n
    except Exception as e:
        failed.append(f"{role}/{section}: {e.__class__.__name__}")
conn.close()
record_case("⑥ живая память всех ролей: считается у каждой, ни одна не падает",
       f"ролей {len(by_role)} · падений 0",
       f"ролей {len(by_role)} · падений {len(failed)}" + (f" ({'; '.join(failed[:2])})" if failed else ""))
print("      блоков без даты по ролям: " +
      " · ".join(f"{r} {n}" for r, n in sorted(by_role.items()) if n) or "      ни у кого")

print("-" * 88)
matched = sum(1 for *_, ok in cases if ok)
print(f"сошлось {matched} из {len(cases)}")
if matched != len(cases):
    for name, expected, actual, ok in cases:
        if not ok:
            print(f"  🔴 {name}: ждали «{expected}», вышло «{actual}»")
    sys.exit(1)
print("⚖️ ГРАНИЦА: судится ТОЛЬКО тот случай, где блок держат ЗА отсутствие даты.")
print("   Блоки без даты с ДРУГИМ приговором (закрытая работа · примет нет) в счёт")
print("   НЕ идут намеренно: их никто не держит, и счёт с ними горел бы почти всегда.")
sys.exit(0)
