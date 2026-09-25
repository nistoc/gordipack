# -*- coding: utf-8 -*-
"""СТАТУС ПРАВИЛА — ОДИН МЕХАНИЗМ НА ВЕСЬ КОНТУР (карточка #89, шаг 3).

🔴 ПОВОД — ЗАМЕР 2026-08-10 08:28 UTC, А НЕ ОПАСЕНИЕ. Отзыв правила разбирали ТРИ места,
   и каждое СВОИМ признаком:
       set-rule.py     body.lstrip().upper().startswith(("⛔ ОТОЗВАН", "ОТОЗВАН"))
       export-rules.py body.lstrip().startswith("⛔ ОТОЗВАНО")        ← без регистра, со значком
       Перископ (C#)   ^\\s*(?:⛔\\s*)?(ОТОЗВАНО|ОТМЕНЕНО|ОТМЕНЁНО)\\b
   На сегодняшнем своде все трое отвечают «10» — и это СОВПАДЕНИЕ ДАННЫХ, а не свойство:
   все десять надгробий написаны одинаково. Проверка различающими написаниями:

       написание                  set-rule  export-rules  Перископ
       «ОТОЗВАНО владельцем»        да          НЕТ          да
       «⛔ ОТМЕНЁНО владельцем»     НЕТ         НЕТ          да
       «отозвано владельцем»        да          НЕТ          НЕТ
       «⛔ ОТОЗВАН приказ»          да          НЕТ          НЕТ

   Четыре из четырёх расходятся. Первое же надгробие, написанное иначе, развело бы свод,
   зеркало и просмотрщик — молча и каждый со своим уверенным ответом.

🎯 ЧТО ЗДЕСЬ ЕСТЬ
   ① ОДИН признак надгробия на всех — правится в одном месте;
   ② поддержка ПОЛЯ `status`, которого в базе ЕЩЁ НЕТ: есть поле — оно сильнее текста;
      нет — читается текст, и об этом говорится вслух. Порядок взят у Перископа: он этот
      приём уже носит и проверен временем.

⚖️ ПОЧЕМУ ЧИТАТЕЛИ УЧАТСЯ ДО ТОГО, КАК ПОЛЕ ПОЯВИТСЯ. Если завести поле раньше, между
   его применением и переучиванием останется окно, в котором отозванное правило читается приказом.
   Это уже случалось: 2026-07-16 зеркало правил пять часов держало отозванное как приказ.
"""
import re
import sqlite3

# ⚠️ ПРИЗНАК НАРОЧНО УЗКИЙ — якорь в начале тела плюс закрытый список слов.
#    Свободный поиск «ОТОЗВАНО» где угодно объявил бы отозванным ДЕЙСТВУЮЩЕЕ правило,
#    которое лишь упоминает отмену соседнего: замер 2026-08-10 — широкий поиск даёт 14
#    против 10 узких, то есть 4 ложных, 28 %. Ошибка в эту сторону опаснее: приказ
#    пропадает с глаз. Обратная ошибка оставляет правило среди действующих — не хуже,
#    чем было до появления признака вообще.
# ⚠️ РЕГИСТР ЗНАЧИМ И ЭТО РЕШЕНИЕ, А НЕ НЕДОСМОТР: надгробие пишется прописными как знак
#    намеренности. «отозвано» строчными — обычное слово в обычной фразе.
TOMBSTONE = re.compile(r'^\s*(?:⛔\s*)?(ОТОЗВАН[ОА]?|ОТМЕН[ЕЁ]НО)\b')

REVOKED_VALUES = ('revoked', 'cancelled', 'canceled', 'отозвано')


def has_status_field(conn):
    """Есть ли у правил поле статуса. Спрашивается у БАЗЫ, а не помнится."""
    return 'status' in {r[1] for r in conn.execute("PRAGMA table_info(rules)")}


def is_revoked_body(body):
    """Отзыв, прочитанный из ТЕКСТА. Единственный признак на весь контур."""
    return bool(TOMBSTONE.match(body or ''))


def revoked_of(body, status=None, has_field=False):
    """→ (отозвано: bool, чем доказано: str|None).

    ПОРЯДОК ИСТОЧНИКОВ: поле сильнее текста — иначе инструмент спорил бы с самой базой.
    Текст читается ТОЛЬКО когда поля нет вовсе.

    ⚠️ Когда поля нет, «не отозвано» НЕ означает 'active': в такой базе статус живёт
       прозой, и объявить правило действующим за неё — соврать ровно тем способом,
       ради которого статус и переносят в поле.
    """
    if has_field:
        rev = (status or '').strip().lower() in REVOKED_VALUES
        return rev, (f"поле статуса: '{status}'" if rev else None)
    if is_revoked_body(body):
        return True, 'шапка надгробия в начале текста (поля статуса в этой базе нет)'
    return False, None


def rule_in_force(conn, key):
    """Действует ли правило `key` в своде ЭТОЙ базы: строка есть и не отозвана (поле
    статуса, а без поля — шапка надгробия, тем же revoked_of). Нет строки или таблицы —
    не действует."""
    try:
        has_field = has_status_field(conn)
        row = conn.execute(
            f"SELECT body{', status' if has_field else ''} FROM rules WHERE rule_key=?",
            (key,)).fetchone()
    except sqlite3.Error:
        return False
    if row is None:
        return False
    return not revoked_of(row[0], row[1] if has_field else None, has_field)[0]


# ── СОВЕТ ОБ ОТПРАВКЕ КОДА — ПО СВОДУ ЭТОГО КОНТУРА, А НЕ ВПЕЧАТАННЫМ СЛОВОМ ──────────────
# 🩸 2026-09-25: отправка в GitLab снова только по слову владельца (11:02:36 UTC, чат PROTO,
# правило gitlab-push-frozen), а четыре инструмента печатали «отправка разрешена без
# отдельного слова (08.08)» и считали строки «только по слову» пережитком. Впечатанный
# в инструмент текст переживает решение, на котором стоял, и уезжает с пакетом к соседям,
# у которых этого решения не было вовсе. Поэтому совет спрашивает СВОД той базы, где идёт.
SEND_FREEZE_RULE = 'gitlab-push-frozen'


def send_advice(conn, scripts_dir):
    """ОДНА строка совета об отправке коммитов по своду `conn` (None — свода не видно)."""
    rights = f"python {scripts_dir}/role-rights.py list"
    if conn is not None and rule_in_force(conn, SEND_FREEZE_RULE):
        return (f"отправка в GitLab заморожена словом владельца (правило {SEND_FREEZE_RULE}):"
                f" копим на машине до переезда; GitHub — по праву роли ({rights})")
    return f"отправка — по праву роли ({rights}); перед отправкой сверь состав ВЕТКИ"


def send_advice_for(script_file, db=None):
    """Совет об отправке для инструмента `script_file`: база — `db` либо база его контура.
    Базы не нашлось (копия вне контура) — совет без свода, и он говорит это словом."""
    from pathlib import Path
    scripts_dir = Path(script_file).resolve().parent.as_posix()
    try:
        if db is None:
            import mezo_paths
            db = mezo_paths.default_db(script_file)
        conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    except (SystemExit, Exception):   # noqa: BLE001 — default_db зовёт sys.exit вне контура
        return send_advice(None, scripts_dir) + " (свода не видно: база контура не найдена)"
    try:
        return send_advice(conn, scripts_dir)
    finally:
        conn.close()


def read_rules(conn, order='rule_key'):
    """Правила со сведённым статусом. → список словарей.

    Отдаёт `revoked` и `revoked_basis` — чтобы КАЖДЫЙ читатель показывал одно и то же
    и одинаково объяснял, откуда он это взял.
    """
    has_field = has_status_field(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(rules)")]
    rows = conn.execute(f"SELECT * FROM rules ORDER BY {order}").fetchall()
    out = []
    for row in rows:
        d = dict(zip(cols, row))
        rev, basis = revoked_of(d.get('body'), d.get('status'), has_field)
        d['revoked'] = rev
        d['revoked_basis'] = basis
        d['status_source'] = 'field' if has_field else 'text'
        out.append(d)
    return out
