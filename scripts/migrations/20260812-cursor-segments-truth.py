# -*- coding: utf-8 -*-
"""20260812-cursor-segments-truth — ЗАСЕЯННЫЕ ОТРЕЗКИ ГОВОРЯТ ПРАВДУ + ДВЕ ВИТРИНЫ (карточка #193).

ПОВОД (замер @PROTO 2026-08-11 20:09 UTC). Шаг `003-cursor-segments` применён к живой базе
06.08: девять строк, по одной на роль, ВСЕ вида `declared` с основанием «перенос плоского
курсора». Пять суток в таблицу не писал ни один инструмент (счёт грепом — ноль), витрин
`cursor_truth`/`cursor_gaps` в живой базе нет вовсе.
🎯 Класс: **сосуд заведён, засеян и не питается.** Пустой заметили бы; засеянный-и-мёртвый
отвечает уверенно данными дня посева. Питание врезано 11.08 (`3c8e970`): подтверждение
чтения дописывает отрезок `read`. Этот шаг чинит ПРОШЛОЕ и даёт ЧЕМ СПРОСИТЬ.

⚖️ ГЛАВНОЕ РАЗЛИЧЕНИЕ, РАДИ КОТОРОГО ШАГ И НУЖЕН: `declared` при переносе значило
«НЕ ДОКАЗАНО, что читано» — честная осторожность, взять доказательства было неоткуда.
Но витрина `cursor_gaps` толкует `declared` как «до роли НЕ ДОШЛО», а это ДРУГОЕ
утверждение. Создать витрины, не разведя эти два смысла, значило бы выдать контуру
громкую ложную тревогу про восемь ролей. Поэтому сначала правда о прошлом, потом витрины —
в одном шаге, чтобы порядок нельзя было нарушить.

📌 ОСНОВАНИЕ ПРАВКИ ПРОШЛОГО — РЕШЕНИЕ ВЛАДЕЛЬЦА 2026-08-12 11:07 UTC, дословно:
   «считать прочитанным, кроме RCC». До 06.08 роли читали ленту и подтверждали прочтение;
   это ближе всего к правде, и мы честно берём на себя, что утверждаем чуть больше,
   чем можем доказать.
   ⚠️ RCC — известное исключение, и оно ЗАДОКУМЕНТИРОВАНО, а не додумано: 05.08 её отметку
   сдвинули словом владельца на 692 записки (её же ноты #2897/#2898, семь недель дормана,
   сводка COORD вместо ленты). Её отрезок разделяется на прочитанное глазами и заявленное.

🪤 ЧЕГО ЭТОТ ШАГ НЕ ДЕЛАЕТ: не трогает `read_cursors` (плоская отметка остаётся источником
   долга), не создаёт сторожа «курсор без сегментов» (он покраснел бы у всех невиновно,
   пока в сегментах нет свежих участков) и не выдумывает границ там, где их нет.
"""
import argparse
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
sys.path.insert(0, SCRIPTS)
from schema_journal import record_step, verify  # noqa: E402

VERSION = "20260812-cursor-segments-truth"

# ⚖️ ГРАНИЦА ЧТЕНИЯ ГЛАЗАМИ У RCC — не вычислена, а ВЗЯТА ИЗ ЗАПИСИ: её ноты #2897/#2898
# (05.08 21:00–21:05 UTC) и разбор `vnext/10-courier-cursor.md`, сданный по слову владельца.
RCC_READ_TO = 2204
RCC_BASIS = ("сводка COORD за 7 недель дормана вместо ленты; 692 ноты НЕ читаны. "
             "Разрешил владелец живым словом 2026-08-05, основание — записка #2898")

OWNER_WORD = ("решение владельца 2026-08-12 11:07 UTC «считать прочитанным, кроме RCC»: "
              "до 06.08 роли читали ленту и подтверждали прочтение")

# ⚠️ СПИСКОМ, А НЕ ОДНОЙ СТРОКОЙ ДЛЯ executescript: он в sqlite3 делает НЕЯВНЫЙ COMMIT
# перед выполнением, то есть закрывает мою транзакцию, и правка схемы уходит в автокоммит.
# Поймал не я, а сторож журнала (`record_step` отказался писать вне транзакции) — тот самый,
# что заведён 09.08 после случая «откат оставил таблицу и стёр запись о ней».
VIEWS = ["""
DROP VIEW IF EXISTS cursor_truth
""", """
DROP VIEW IF EXISTS cursor_gaps
""", """
-- ЧЕМ ПРОЙДЕНА ЛЕНТА У КАЖДОЙ РОЛИ. Не вердикт, а РАЗБОР: сколько записок пройдено
-- глазами, сколько заявлением, сколько пришлось на время до рождения роли.
CREATE VIEW cursor_truth AS
SELECT role,
       SUM(CASE WHEN kind = 'read'     THEN to_id - from_id + 1 ELSE 0 END) AS notes_read,
       SUM(CASE WHEN kind = 'declared' THEN to_id - from_id + 1 ELSE 0 END) AS notes_declared,
       SUM(CASE WHEN kind = 'born'     THEN to_id - from_id + 1 ELSE 0 END) AS notes_before_birth,
       MAX(to_id) AS covered_to
FROM cursor_segments
GROUP BY role
""", """
-- ЧТО ДО РОЛИ НЕ ДОШЛО — витрина ДЛЯ ПИСАВШЕГО, а не приговор роли.
-- ⛔ Сюда попадает ТОЛЬКО 'declared': участок, который роль сознательно прошла без чтения
--    тел, с записанным основанием. 'born' исключён намеренно — небывшее не складывается
--    с пропущенным, повторять новорождённой нечего и некому.
CREATE VIEW cursor_gaps AS
SELECT role, from_id, to_id, to_id - from_id + 1 AS notes, basis, authorized, at
FROM cursor_segments WHERE kind = 'declared'
"""]


def gaps_after_seed(conn):
    """ВСЕ непокрытые участки роли ниже её плоской отметки — включая дыры В СЕРЕДИНЕ.

    🪤 ПЕРВАЯ РЕДАКЦИЯ ИСКАЛА ТОЛЬКО ХВОСТ (от верха отрезков до отметки) — и пропускала
    ровно те две роли, что подтверждали чтение ПОСЛЕ врезки питания 11.08: у них появился
    свежий отрезок наверху, из-за которого «верх» уехал за дыру, и провал 2997..3527
    остался невидимым. Поймано не кодом, а чтением НАПЕЧАТАННЫХ ЧИСЕЛ: «глазами 3000,
    покрыто до #3531» не сходится ни с чем.
    📌 Урок в шаг: **дыра, закрываемая с одного конца, ищется с обоих.**

    ⚠️ ЭТУ ДЫРУ Я ЧУТЬ НЕ ОСТАВИЛ, И ОНА ХУЖЕ ИСХОДНОЙ БЕДЫ: посев кончается 06.08,
    а отметки уехали вперёд на сотни записок. Витрина показала бы «покрыто до 2977»
    при отметке 3107 — то есть необъяснённый провал ровно там, где роль читала честнее
    всего (батчами с подтверждением).
    📏 Основание, что это ПРОЧИТАНО ТЕЛОМ, — замер, а не догадка: плоскую отметку двигает
    РОВНО ОДНО место кода (`do_ack` в read-messages.py), и оно требует обеих половин
    разрезанного токена. Проверено грепом по всем живым скриптам.
    """
    out = []
    for role, cur in conn.execute("SELECT reader_role, last_read_id FROM read_cursors"):
        segs = conn.execute("SELECT from_id, to_id FROM cursor_segments WHERE role = ?"
                            " ORDER BY from_id", (role,)).fetchall()
        pos = 1                       # первая ещё не покрытая записка
        for lo, hi in segs:
            if lo > pos:              # перед этим отрезком — провал
                gap_hi = min(lo - 1, cur)
                if gap_hi >= pos:
                    out.append((role, pos, gap_hi))
            pos = max(pos, hi + 1)
        if cur >= pos:                # и хвост до отметки
            out.append((role, pos, cur))
    return sorted(out)


def plan_for(conn):
    """Что станет с каждым засеянным отрезком. Возвращает список действий, а не делает их."""
    rows = conn.execute(
        "SELECT id, role, from_id, to_id, kind, basis FROM cursor_segments ORDER BY role, from_id"
    ).fetchall()
    acts = []
    for sid, role, a, b, kind, basis in rows:
        if kind != 'declared' or not (basis or '').startswith('перенос плоского курсора'):
            acts.append((role, f"{a}..{b} {kind}", "не трогаем", "не посевной отрезок"))
            continue
        if role == 'RCC':
            acts.append((role, f"{a}..{b} declared", f"РАЗДЕЛИТЬ: {a}..{RCC_READ_TO} read + "
                                                     f"{RCC_READ_TO+1}..{b} declared",
                         "исключение владельца, основание записано"))
        else:
            acts.append((role, f"{a}..{b} declared", f"{a}..{b} read", OWNER_WORD[:52] + "…"))
    return rows, acts


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', default=os.path.join(os.path.dirname(SCRIPTS), 'mezosync.db'))
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    if not os.path.exists(a.db):
        sys.exit(f'⛔ НЕ ЗАПУСТИЛАСЬ: базы нет по пути {a.db}')
    conn = sqlite3.connect(a.db)

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'cursor_segments' not in tables:
        sys.exit('⛔ НЕ ЗАПУСТИЛАСЬ: в базе нет cursor_segments — это не та база, '
                 'которую описывает шаг (нужен шаг 003-cursor-segments)')

    print('=' * 78)
    print(f'{VERSION}{"  ⟨ВХОЛОСТУЮ — база не меняется⟩" if a.dry_run else ""}')
    print(f'база: {a.db}')
    print('=' * 78)

    rows, acts = plan_for(conn)
    print(f'отрезков сейчас: {len(rows)}\n')
    print(f'{"РОЛЬ":9} {"БЫЛО":22} {"СТАНЕТ":38} ОСНОВАНИЕ')
    print('─' * 110)
    for role, was, will, why in acts:
        print(f'{role:9} {was:22} {will:38} {why[:40]}')
    print('─' * 110)
    gaps = gaps_after_seed(conn)
    print(f'\nДЫРА МЕЖДУ ПОСЕВОМ И ПЛОСКОЙ ОТМЕТКОЙ — дописывается видом read '
          f'(отметку двигает только подтверждение чтения):')
    if gaps:
        # ⚠️ Имена НЕ `a`/`b`: `a` — это разбор аргументов, и цикл его затирал.
        # Вылет случился на `a.dry_run` уже ПОСЛЕ печати плана, то есть выглядел бы
        # как сбой врезки, а был сбоем печати. Поймано первым же прогоном по копии.
        for role, lo, hi in gaps:
            print(f'  {role:9} {lo}..{hi}  ({hi - lo + 1} записок)')
    else:
        print('  дыр нет — отрезки покрывают отметки у всех ролей')
    print('─' * 110)
    touched = sum(1 for _, _, w, _ in acts if w != 'не трогаем')
    views_now = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='view'")}
    have = [v for v in ('cursor_truth', 'cursor_gaps') if v in views_now]
    print(f'меняем отрезков: {touched} из {len(acts)} · витрины cursor_truth и cursor_gaps — '
          f'{"пересоздаются (уже есть: " + ", ".join(have) + ")" if have else "создаются впервые"}')

    if a.dry_run:
        print('\n⟨ВХОЛОСТУЮ⟩ база не тронута. Для врезки прогони без --dry-run.')
        return

    conn.execute("BEGIN")
    for sid, role, aa, bb, kind, basis in rows:
        if kind != 'declared' or not (basis or '').startswith('перенос плоского курсора'):
            continue
        if role == 'RCC':
            conn.execute("UPDATE cursor_segments SET to_id = ?, kind = 'read', basis = NULL,"
                         " authorized = NULL WHERE id = ?", (RCC_READ_TO, sid))
            conn.execute("INSERT INTO cursor_segments (role, from_id, to_id, kind, basis,"
                         " authorized, note_id, at) VALUES (?,?,?, 'declared', ?, 'owner', 2898, ?)",
                         (role, RCC_READ_TO + 1, bb, RCC_BASIS, '2026-08-05 21:05:00'))
        else:
            # 'read' основания не требует и не терпит: оно и ЕСТЬ основание.
            conn.execute("UPDATE cursor_segments SET kind = 'read', basis = NULL,"
                         " authorized = NULL WHERE id = ?", (sid,))
    # Дыру закрываем ПОСЛЕ правки посева: иначе верх отрезков считался бы по старым данным.
    for role, aa, bb in gaps_after_seed(conn):
        conn.execute("INSERT INTO cursor_segments (role, from_id, to_id, kind, at)"
                     " VALUES (?, ?, ?, 'read', datetime('now'))", (role, aa, bb))
    for stmt in VIEWS:
        conn.execute(stmt)
    fp = record_step(conn, VERSION,
                     "засеянные отрезки говорят правду (слово владельца 12.08: «считать "
                     "прочитанным, кроме RCC») + витрины cursor_truth и cursor_gaps; "
                     "gaps показывает ТОЛЬКО declared — 'born' исключён намеренно", by='PROTO')
    conn.commit()
    print(f'\n✅ ВРЕЗАНО. отпечаток схемы: {fp}')
    ok, why = verify(conn)
    print(f'{"✅" if ok else "🔴"} сторож журнала: {why}')
    print('целостность:', conn.execute("PRAGMA integrity_check").fetchone()[0])
    print('\nЧЕМ ПРОЙДЕНА ЛЕНТА (витрина cursor_truth):')
    for r in conn.execute("SELECT role, notes_read, notes_declared, notes_before_birth,"
                          " covered_to FROM cursor_truth ORDER BY role"):
        print(f'  {r[0]:8} глазами {r[1]:>5} · заявлением {r[2]:>4} · до рождения {r[3]:>4}'
              f' · покрыто до #{r[4]}')


if __name__ == '__main__':
    main()
