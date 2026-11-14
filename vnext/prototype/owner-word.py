# -*- coding: utf-8 -*-
"""ХРАНИЛИЩЕ СЛОВ ВЛАДЕЛЬЦА: запись, чтение по номеру, поиск по тексту
(карточка #554, часть ② «ИНСТРУМЕНТ»).

ЗАЧЕМ. Правило `history-compression-policy` велит перед сносом файла записи разговора
выжать из него дословную речь владельца, а адреса у выжимки не было. Теперь он есть:
у каждого слова владельца свой НОМЕР, и на него можно ссылаться — «слово #7».

🔑 ГЛАВНОЕ УСТРОЙСТВО, РАДИ КОТОРОГО ИНСТРУМЕНТ И НУЖЕН: ДОСЛОВНОСТЬ ПРОВЕРЯЕТ МАШИНА,
А НЕ ОБЕЩАНИЕ РОЛИ. Записывая слово, инструмент САМ ищет этот текст в записях разговоров
прогоном `find-owner-word.py` — и без находки запись НЕ ДЕЛАЕТ. Пересказ не проходит
не потому, что роль честная, а потому, что пересказа в записи разговора нет.
⚖️ Почему это не «лишняя строгость»: роль, записывающая слово по памяти, искренне уверена,
что цитирует. Контур уже платил за это трижды за одни сутки (четыре вида строки,
неотличимой от замера — правило `remeasure-before-ask`). Обещание «я записал дословно»
не отличимо от правды НИЧЕМ, а прогон отличим.

⛔ ЛАЗЕЙКИ «записать без сверки» НЕТ, И ЭТО НАМЕРЕННО. Цена названа вслух: слово,
сказанное в чате, запись которого уже сжата, записать НЕЛЬЗЯ. Так и должно быть —
критерий карточки говорит прямо: «то, что уже утрачено из записей разговоров,
восстановлению не подлежит, поэтому берётся живое». Флаг «я сверил рукой» убил бы
единственное несущее свойство хранилища в первый же час спешки.

КАК СВЕРЯЕТСЯ МНОГОСТРОЧНЫЙ ТЕКСТ. `find-owner-word.py` ищет КУСОК текста, а речь
владельца бывает в несколько строк. Инструмент сверяет КАЖДУЮ непустую строку отдельно
и требует, чтобы нашлись ВСЕ. Это строже, чем искать одну строку подлиннее, и строже
намеренно: сверка по одному куску объявляла бы дословным текст, у которого верна только
середина.

⚖️ ЗАВИСИМОСТЬ МЕЖДУ КАТАЛОГАМИ, НАЗВАННАЯ ВСЛУХ: инструмент живёт рядом с базой
координации (`.mezosync/scripts`), а зовёт `find-owner-word.py` из `vnext-tools`. Путь
берётся умолчанием от расположения контейнера и переопределяется ключом `--finder`:
жёсткая строка здесь сломала бы свежий контур, собранный из образца по другому пути.

ИСХОДЫ (коды выхода):
  0 — сделано (слово записано · прочитано · найдено)
  1 — не найдено (нет такого номера · поиск пуст)
  2 — ОТКАЗ записать: сверка дословности не прошла. Запись НЕ сделана
  3 — ошибка вызова (нет обязательного ключа, не найден искатель, база недоступна)
"""
import argparse
import io
import os
import re
import sqlite3
import subprocess
import sys
import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
CONTAINER = os.path.dirname(os.path.dirname(HERE))
DEFAULT_DB = os.path.join(os.path.dirname(HERE), 'mezosync.db')
DEFAULT_FINDER = os.path.join(CONTAINER, 'vnext-tools', 'find-owner-word.py')


def now_utc():
    """Час берётся ЗАПРОСОМ к системе, а не из подсказки хода: подсказка даёт местное
    время без сдвига, и роль, взявшая час оттуда, подписывает местное буквами UTC
    (оплаченный класс, записка #6413)."""
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')


# Знаки, которыми искатель называет ПРОИСХОЖДЕНИЕ найденного текста.
# ⚡ ПОЧЕМУ ИСХОД ИЩЕТСЯ ПО ЗНАКУ, А НЕ БЕРЁТСЯ ПОСЛЕДНЕЙ СТРОКОЙ ВЫВОДА. Первая редакция
# брала `tail[-1]` — и записала в поле «чем сверено» обрывок справочного текста искателя
# («…выдумана. Ровно этот случай и завёл карточку #521»), потому что у этого инструмента
# итог стои́т НЕ в последней строке. Поймал прогон, а не внимательность. Класс тот же, что
# в правиле `no-pipe-tool-output`: «последняя строка» — догадка о чужой печатной форме,
# и она врёт молча, оставляя поле заполненным и правдоподобным.
OUTCOME_MARKS = ('📝', '🔘', '✍', '⚪')

# Час события в записи разговора: ISO с «Z» на конце — «2026-11-14T16:09:31.578Z».
STAMP = re.compile(r'(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.\d+)?Z')


def stamp_from(line):
    """Час найденного события из строки исхода искателя, в нашей форме «… UTC»."""
    m = STAMP.search(line or '')
    return f'{m.group(1)} {m.group(2)} UTC' if m else None


def outcome_line(stdout, code):
    """Строка исхода из вывода искателя — по ЗНАКУ исхода, а не по положению в выводе."""
    for line in (stdout or '').splitlines():
        if any(mark in line for mark in OUTCOME_MARKS):
            return ' '.join(line.split())
    return f'(исход в выводе искателя не распознан, код {code})'


def verify_verbatim(text, said_at, finder):
    """Сверка дословности прогоном искателя по записям разговоров.

    Возвращает (прошло, отчёт, исходы). Прошло только когда КАЖДАЯ непустая строка
    текста найдена с исходом «сказал владелец» (код 0 искателя).
    """
    if not os.path.isfile(finder):
        return False, f'искатель не найден по пути {finder} — сверить дословность нечем', []

    day = said_at[:10]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False, 'текст пуст — сверять нечего', []

    report, marks = [], []
    for line in lines:
        probe = line if len(line) <= 200 else line[:200]
        run = subprocess.run(
            [sys.executable, finder, '--слово', probe, '--за', day],
            capture_output=True, text=True, encoding='utf-8', errors='replace')
        mark = outcome_line(run.stdout, run.returncode)
        marks.append(mark)
        report.append(f'   · «{probe[:60]}…» → код {run.returncode} · {mark[:120]}')
        if run.returncode != 0:
            report.append(f'   🔴 ЭТА СТРОКА НЕ ПОДТВЕРЖДЕНА (код {run.returncode}): '
                          '0 — сказал владелец · 1 — не найдено · 2 — искать негде · '
                          '3 — найдено, но происхождение машинное или неизвестное')
            return False, '\n'.join(report), marks
    return True, '\n'.join(report), marks


def cmd_add(conn, a):
    text = a.text
    if a.text_file:
        # ⚡ Длинный текст — только файлом: речь владельца несёт переносы строк и кавычки,
        # которые командная строка искажает молча (оплаченный класс этой смены).
        with open(a.text_file, encoding='utf-8') as fh:
            text = fh.read()
    if not text or not text.strip():
        sys.exit('⛔ нужен дословный текст: --text «…» или --text-file <файл>')

    print('🔎 СВЕРКА ДОСЛОВНОСТИ — ищу этот текст в записях разговоров:')
    ok, report, marks = verify_verbatim(text, a.said_at, a.finder)
    print(report)
    if not ok:
        print()
        print('⛔ ОТКАЗ: дословность НЕ подтверждена, слово НЕ записано.')
        print('   Хранилище о дословности, а не о смысле: пересказ здесь не хранится.')
        print('   Если запись разговора уже сжата — слово восстановлению не подлежит,')
        print('   и это сказано в самой карточке #554. Бери ЖИВОЕ слово, не прошлое.')
        sys.exit(2)
    print('✅ сверка прошла: каждая строка найдена в записях с исходом «сказал владелец»')

    # 🔑 ВТОРАЯ ПОЛОВИНА СВЕРКИ — ЧАС, И БЕЗ НЕЁ ПЕРВАЯ НЕПОЛНА. Искатель сверяет только
    # ДЕНЬ (`--за ГГГГ-ММ-ДД`), поэтому текст, найденный в правильный день, подтверждает
    # день — а не час. Первая редакция этого инструмента так и записала слово с часом
    # 15:52, когда запись разговора говорит 16:09:31: 15:52 был час, когда роль ЗАДАЛА
    # вопрос, а не когда владелец ОТВЕТИЛ. Сверка молчала, поле said_at осталось
    # заполненным и правдоподобным.
    # ⚖️ Почему это не мелочь: час — несущее свойство слова. По нему слово находят,
    # по нему судят, какое из двух слов новее, и по нему строятся встречные случаи
    # приёмок (оплаченный класс: граница «новее 07:51» находила файл 07:51:41 —
    # записка #6408 §⑤). Час, объявленный ролью, ничем не отличим от часа измеренного.
    found = sorted(s for s in (stamp_from(m) for m in marks) if s)
    if not found:
        print('⚠️ час события в выводе искателя не распознан — сверить said_at не с чем.')
        print('   Записываю с часом, названным ролью, и говорю об этом вслух: в поле')
        print('   «чем сверено» это будет видно следующему читателю.')
    elif found[0] != a.said_at:
        print()
        print(f'⛔ ОТКАЗ: час НЕ СОВПАЛ. Слово НЕ записано.')
        print(f'   роль назвала ... {a.said_at}')
        print(f'   запись говорит . {found[0]}' + (f' (и ещё: {", ".join(found[1:])})'
                                                   if len(found) > 1 else ''))
        print('   Текст дословен, но час — отдельное свойство, и угадывать его за роль')
        print('   инструмент не станет: подставленный молча час неотличим от измеренного.')
        print(f'   Верный вызов: --said-at "{found[0]}"')
        sys.exit(2)
    else:
        print(f'✅ час сверен с записью разговора знак в знак: {found[0]}')

    try:
        cur = conn.execute(
            "INSERT INTO owner_words (said_at, chat, text_verbatim, source_file, source_line,"
            " verified_by, heard_by, noted_at, note) VALUES (?,?,?,?,?,?,?,?,?)",
            (a.said_at, a.chat, text, a.source_file, a.source_line,
             f'find-owner-word.py, прогон {now_utc()}, строк сверено '
             f'{len([l for l in text.splitlines() if l.strip()])}, все с кодом 0; '
             f'исход искателя: {" | ".join(marks)}',
             a.heard_by, now_utc(), a.note))
        conn.commit()
    except sqlite3.IntegrityError as e:
        # ⚖️ Повтор — не беда и не порча: то же слово того же часа в том же чате уже лежит.
        row = conn.execute("SELECT id FROM owner_words WHERE chat=? AND said_at=? "
                           "AND text_verbatim=?", (a.chat, a.said_at, text)).fetchone()
        if row:
            print(f'📌 это слово уже записано — слово #{row[0]}. Ничего не добавлено, '
                  'дубля нет')
            return 0
        sys.exit(f'⛔ база отказала: {e}')

    print(f'\n✅ ЗАПИСАНО: слово #{cur.lastrowid}')
    print(f'   ссылаться на него так: «слово #{cur.lastrowid}»')
    return 0


def show_row(row, full=True):
    print(f'слово #{row["id"]}')
    print(f'  сказано ....... {row["said_at"]} · чат {row["chat"]}')
    print(f'  услышала ...... {row["heard_by"]} · записано {row["noted_at"]}')
    src = row['source_file'] or '—'
    if row['source_line']:
        src = f'{src}:{row["source_line"]}'
    print(f'  источник ...... {src}')
    print(f'  чем сверено ... {row["verified_by"]}')
    if row['note']:
        print(f'  пояснение ..... {row["note"]}')
        print('                  ⚖️ это ПОЯСНЕНИЕ роли, НЕ речь владельца')
    print('  ДОСЛОВНО:')
    body = row['text_verbatim'] if full else row['text_verbatim'][:200]
    for line in body.splitlines() or ['']:
        print(f'    {line}')
    if not full and len(row['text_verbatim']) > 200:
        print('    …(полностью — show по номеру)')


def cmd_show(conn, a):
    row = conn.execute("SELECT * FROM owner_words WHERE id=?", (a.number,)).fetchone()
    if row is None:
        n = conn.execute("SELECT COUNT(*) FROM owner_words").fetchone()[0]
        print(f'🔴 слова #{a.number} нет. Слов в хранилище: {n}')
        return 1
    show_row(row)
    return 0


def cmd_find(conn, a):
    rows = conn.execute(
        "SELECT * FROM owner_words WHERE text_verbatim LIKE ? OR note LIKE ?"
        " ORDER BY said_at DESC", (f'%{a.word}%', f'%{a.word}%')).fetchall()
    if not rows:
        print(f'🔴 по куску «{a.word}» ничего. Слов в хранилище: '
              f'{conn.execute("SELECT COUNT(*) FROM owner_words").fetchone()[0]}')
        print('⚠️ пустой ответ НЕ доказывает, что слова не было: он доказывает, что слово')
        print('   не ЗАПИСАНО. Поиск по самим записям разговоров — find-owner-word.py')
        return 1
    print(f'найдено слов: {len(rows)}')
    for row in rows:
        print('-' * 70)
        show_row(row, full=False)
    return 0


def cmd_list(conn, a):
    rows = conn.execute("SELECT * FROM owner_words ORDER BY said_at DESC LIMIT ?",
                        (a.limit,)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM owner_words").fetchone()[0]
    print(f'слов владельца в хранилище: {total}'
          + (f' · показаны последние {len(rows)}' if total > len(rows) else ''))
    for row in rows:
        print('-' * 70)
        show_row(row, full=False)
    if total > len(rows):
        print('-' * 70)
        print(f'⚠️ УПЁРЛОСЬ В ПРЕДЕЛ --limit {a.limit}: за показанными ещё '
              f'{total - len(rows)}. Это НЕ «всё» — это «упёрлось»')
    return 0


def main():
    ap = argparse.ArgumentParser(
        description='Хранилище слов владельца: запись со сверкой дословности, '
                    'чтение по номеру, поиск по куску текста (карточка #554)')
    ap.add_argument('--db', default=DEFAULT_DB)
    ap.add_argument('--finder', default=DEFAULT_FINDER,
                    help='путь к find-owner-word.py — им сверяется дословность')
    sub = ap.add_subparsers(dest='cmd', required=True)

    ad = sub.add_parser('add', help='записать слово владельца (со сверкой по записям)')
    ad.add_argument('--said-at', dest='said_at', required=True,
                    help='час, когда сказано: «ГГГГ-ММ-ДД ЧЧ:ММ:СС UTC»')
    ad.add_argument('--chat', required=True, help='чат, где сказано (например COORD)')
    ad.add_argument('--text', help='ДОСЛОВНЫЙ текст (короткий)')
    ad.add_argument('--text-file', dest='text_file',
                    help='файл с дословным текстом — для длинного и многострочного')
    ad.add_argument('--heard-by', dest='heard_by', required=True, help='роль, услышавшая слово')
    ad.add_argument('--source-file', dest='source_file', help='файл-источник')
    ad.add_argument('--source-line', dest='source_line', type=int, help='номер строки в нём')
    ad.add_argument('--note', help='ПОЯСНЕНИЕ роли — не речь владельца')

    sh = sub.add_parser('show', help='прочесть слово по номеру')
    sh.add_argument('number', type=int)

    fd = sub.add_parser('find', help='поиск по куску текста')
    fd.add_argument('word')

    ls = sub.add_parser('list', help='перечень последних слов')
    ls.add_argument('--limit', type=int, default=10)

    a = ap.parse_args()
    if not os.path.isfile(a.db):
        sys.exit(f'⛔ базы нет: {a.db}')
    conn = sqlite3.connect(a.db)
    conn.row_factory = sqlite3.Row
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if 'owner_words' not in tables:
        sys.exit('⛔ таблицы owner_words нет — сначала шаг схемы '
                 'migrations/20261114-owner-words.py (карточка #554, часть ①)')

    sys.exit({'add': cmd_add, 'show': cmd_show, 'find': cmd_find,
              'list': cmd_list}[a.cmd](conn, a))


if __name__ == '__main__':
    main()
