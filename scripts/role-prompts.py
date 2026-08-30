#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""role-prompts.py — ПАРА ПРОМПТОВ ПЕРЕСОЗДАНИЯ РОЛИ: закрытие старого чата + открытие нового.

Слово владельца 2026-08-29 11:16 UTC («заведи role-prompts.py»): пары промптов писались
рукой при каждом пересоздании — рукописный текст с числами протухает, а числа (долг ленты,
раздутые разделы памяти, карточки пула) живут в базе. Инструмент печатает пару ИЗ ЖИВОЙ
базы в момент вызова; владелец копирует блоки в старый и новый чат роли.

    python <КОНТУР>/.mezosync/scripts/role-prompts.py --role STUD

⚖️ ГРАНИЦЫ ВСЛУХ: инструмент ТОЛЬКО ЧИТАЕТ (mode=ro) и печатает текст — ничего не шлёт
и не меняет; период ритма НЕ печатается числом из головы — берётся правило свода
sync-alarm-in-chat (именное слово владельца сильнее, это сказано в самом промпте);
рукописная копия вывода протухает, как любой наказ, — зови в момент пересоздания.
"""
import argparse
import os
import sqlite3
import sys
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mezo_paths import resolve_db, live_scripts  # noqa: E402

S = live_scripts().as_posix()
ПОРОГ = 20000


def числа(conn, role):
    cur = conn.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                       (role,)).fetchone()
    cursor = cur[0] if cur else 0
    долг = conn.execute("SELECT COUNT(*) FROM messages WHERE id>? AND writer_role<>?",
                        (cursor, role)).fetchone()[0]
    раздуто = conn.execute(
        "SELECT section, LENGTH(body) FROM phoenix WHERE role=? AND LENGTH(body)>? "
        "ORDER BY 2 DESC", (role, ПОРОГ)).fetchall()
    пулы = [r[0] for r in conn.execute("SELECT track_id FROM tracks WHERE status='active'")]
    карточки = []
    if пулы:
        ph = ",".join("?" * len(пулы))
        карточки = conn.execute(
            f"SELECT id, title FROM backlog WHERE role=? AND parent_track IN ({ph}) "
            f"AND status IN ('open','in_progress','blocked','awaiting_word','in_review') "
            f"ORDER BY id", (role, *пулы)).fetchall()
    правило = conn.execute(
        "SELECT status FROM rules WHERE rule_key='sync-alarm-in-chat'").fetchone()
    return долг, раздуто, карточки, (правило and правило[0] == "active")


def наказ_файл(role):
    hits = sorted(glob(os.path.join(os.path.expanduser("~"), ".claude",
                                    "scheduled-tasks", f"*{role.lower()}*", "SKILL.md")))
    return hits[-1].replace("\\", "/") if hits else "<путь к наказ-файлу роли>"


def main():
    ap = argparse.ArgumentParser(description="Пара промптов пересоздания роли из живой базы")
    ap.add_argument("--role", required=True)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    role = a.role.upper()
    db = Path(resolve_db(a.db, __file__))
    if not db.exists():
        sys.exit(f"⛔ ПАРА НЕ СОБРАНА: базы нет ({db}) — это не «пустые промпты»")
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    долг, раздуто, карточки, ритм_жив = числа(conn, role)
    conn.close()
    файл = наказ_файл(role)

    сжать = "".join(
        f"   ⚠️ Раздел {s} раздут: {n} знаков при пороге {ПОРОГ} — СОЖМИ ниже порога\n"
        f"   (история памяти хранит прежнее целиком), сохраняй с --allow-shrink;\n"
        f"   приказы и права сверяй ПОИМЁННО, не глазами по объёму.\n"
        for s, n in раздуто) or "   (раздутых разделов нет — сохраняй как есть)\n"
    дела = "".join(f"   карточка #{i} — {t[:70]}\n" for i, t in карточки) \
        or "   (карточек пула на роли нет — первое дело возьми из ленты и стартовой сводки)\n"
    if not ритм_жив:
        print("⚠️ правило sync-alarm-in-chat не активно — блок ритма в промпте открытия "
              "проверь рукой, стандарту не верь")

    print(f"""═══ ПРОМПТ ЗАКРЫТИЯ (вставить в СТАРЫЙ чат {role}) ═══

Финальное задание этого чата — роль {role} пересоздаётся (слово владельца, порядок
открытия пула). НИЧЕГО НОВОГО НЕ НАЧИНАЙ.

1. Сохрани память — все разделы свежими. Сначала перечитай СВОЮ последнюю записку
   в ленте (память отстаёт от неё), затем обнови отставшие разделы:
   python {S}/save-phoenix.py --role {role} --section <раздел> --file <файл>
{сжать}2. Прощальная записка в ленту: что сделано, что открыто, где след:
   python {S}/write-message.py --role {role} --file <нота.md>
3. Долг ленты (~{долг} записок) НЕ разбирай — его примет новый чат.
После записки — стоп: не бери карточки, не правь файлы.

═══ ПРОМПТ ОТКРЫТИЯ (вставить в НОВЫЙ чат {role}) ═══

Ты — роль {role} контура мезосинк Atlas. Чат свежий после пересоздания.
Пути АБСОЛЮТНЫЕ, все метки времени UTC с суффиксом «UTC».

Шаг 0: python {S}/guard-all.py
Шаг 1 — собранный наказ (несёт зону, права, карточки, ритм и правило ответов):
   python {S}/role-brief.py --role {role}
Шаг 2 — память: python {S}/read-phoenix.py --role {role}
   ⚠️ Память сохранена ДО последней записки роли — первой прочитай СВОЮ последнюю записку.
Шаг 3 — лента (долг ~{долг} записок): читай ЦЕЛИКОМ, подтверждай --ack; длинно —
   сужай ЗАПРОС (--limit порциями), не вывод:
   python {S}/read-messages.py --role {role}
Шаг 4 — ритм (правило свода sync-alarm-in-chat): заведи будильник ВНУТРИ этого чата
   (минуты возьми не :00 и не :30) с промптом «исполни наказ-файл {файл}».
   Период — именное слово владельца твоей роли; без слова — 30 минут. Задачу-расписание
   вне чата НЕ заводи. Правило целиком:
   python {S}/set-rule.py --key sync-alarm-in-chat --show
Шаг 5 — первое дело (карточки активного пула первыми, взятие — с живым объявлением):
{дела}Правило ответов владельцу — перед КАЖДЫМ ответом:
   python {S}/set-rule.py --key owner-reply-format --show""")


if __name__ == "__main__":
    main()
