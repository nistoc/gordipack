# -*- coding: utf-8 -*-
"""diff-schema-sample.py — РАСХОЖДЕНИЕ ОБРАЗЦА СХЕМЫ v-next С ЖИВОЙ БАЗОЙ (карточка #89).

⚠️ ПРЕДМЕТ НАЗВАН УЗКО И ЯВНО: roles · rules · schema_migrations — и только они.
   Образец объявляет себя ФУНДАМЕНТОМ схемы v-next, а не зеркалом всей базы
   (шапка schema_vnext.sql). Расхождение по остальным таблицам расхождением НЕ
   является: на широком предмете я уже ошибся 2026-08-06 и получил ложное число.

⚠️ ЖИВАЯ БАЗА ОТКРЫВАЕТСЯ ТОЛЬКО НА ЧТЕНИЕ (mode=ro) — сверка ничего не меняет.

🧪 --selftest — РАЗЛИЧАЮЩИЙ СЛУЧАЙ + КОНТРОЛЬНАЯ ПАРА (критерий ⑤ карточки #89):
   в копию образца вносится искусственное расхождение, и прогон ОБЯЗАН его увидеть.
   Без этого «ноль расхождений» неотличимо от «сверка не смотрит».
   Контрольная пара — нетронутая копия обязана дать РОВНО исходное число.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # пути машины ВЫВОДЯТСЯ, не впечатаны (карточка #208)

import argparse, io, os, sqlite3, sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
# Приёмник выводится от расположения скрипта, а не впечатан: впечатанный путь —
# заряженное ружьё в каждой копии (грабля ② памяти PROTO, оплачена 10.08).
SAMPLE = os.path.normpath(os.path.join(HERE, '..', 'prototype', 'schema_vnext.sql'))
LIVE_DEFAULT = str(mezo_paths.live_db())
SUBJECT = ('roles', 'rules', 'schema_migrations')


def load_sample(text):
    con = sqlite3.connect(':memory:')
    con.executescript(text)
    return con


def table_exists(con, t):
    return con.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (t,)
    ).fetchone()[0] > 0


def cols(con, t):
    return {r[1]: dict(type=(r[2] or '').upper(), notnull=r[3], pk=r[5])
            for r in con.execute(f'PRAGMA table_info({t})')}


def compare(live, smp, verbose=True):
    """Возвращает (нет_в_живой, нет_в_образце, разошлись_типом, таблиц_не_сошлось).

    🪤 ЧЕТВЁРТОЕ ЧИСЛО ПОЯВИЛОСЬ ОТ НАРОЧНОЙ ПОЛОМКИ 2026-08-10, И БЕЗ НЕГО СВЕРКА ЛГАЛА.
       Пока таблица расходилась, её пропажа двигала числа и различающий случай проходил.
       Как только `schema_migrations` СОШЛАСЬ (0/0), отнятие таблицы перестало менять что
       бы то ни было: «сведено полностью» и «таблицы нет вовсе» стали давать ОДИН ответ.
       То есть проверка слепла ровно в тот момент, когда предмет доводили до нуля, —
       а это самый момент, когда на неё и опираются. Отсутствие таблицы считается
       расхождением ОТДЕЛЬНЫМ числом, которое ноль колонок обнулить не может.
    """
    miss = extra = diff = absent = 0
    for t in SUBJECT:
        le, se = table_exists(live, t), table_exists(smp, t)
        if verbose:
            print(f'\n── {t} ── живая: {"есть" if le else "НЕТ"} · '
                  f'образец: {"есть" if se else "НЕТ"}')
        if not (le and se):
            absent += 1
            if verbose:
                print('   ⛔ таблицы нет с одной из сторон — это РАСХОЖДЕНИЕ, '
                      'а не «нечего сравнивать»')
            continue
        lc, sc = cols(live, t), cols(smp, t)
        m = [c for c in sc if c not in lc]
        e = [c for c in lc if c not in sc]
        d = [(c, sc[c], lc[c]) for c in sc if c in lc
             and (lc[c]['type'] != sc[c]['type'] or lc[c]['notnull'] != sc[c]['notnull'])]
        miss += len(m); extra += len(e); diff += len(d)
        if verbose:
            n = live.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
            print(f'   строк в живой: {n} · колонок живая {len(lc)} / образец {len(sc)}')
            print(f'   🔴 в образце есть, в живой нет ({len(m)}): {", ".join(m) or "—"}')
            print(f'   🟡 в живой есть, в образце нет ({len(e)}): {", ".join(e) or "—"}')
            for c, s, l in d:
                print(f'   🟠 {c}: образец {s["type"]}/notnull={s["notnull"]} · '
                      f'живая {l["type"]}/notnull={l["notnull"]}')
    return miss, extra, diff, absent


def selftest(live_path):
    src = open(SAMPLE, encoding='utf-8').read()
    live = sqlite3.connect(f'file:{live_path}?mode=ro', uri=True)
    base = compare(live, load_sample(src), verbose=False)
    print(f'исходное расхождение: нет в живой {base[0]} · нет в образце {base[1]} · '
          f'разошлись типом {base[2]} · таблиц не сошлось {base[3]}')

    print('\n① КОНТРОЛЬНАЯ ПАРА — нетронутая копия образца')
    same = compare(live, load_sample(src), verbose=False)
    ok_pair = same == base
    print(f'   {"✅" if ok_pair else "🔴"} копия дала {same}, ожидалось {base}')

    print('\n② РАЗЛИЧАЮЩИЙ СЛУЧАЙ — в копию образца внесена ЛИШНЯЯ колонка roles.injected_probe')
    broken = src.replace('    zone        TEXT,',
                         '    zone        TEXT,\n    injected_probe TEXT,', 1)
    assert broken != src, 'опора самопроверки не найдена в образце — тест недействителен'
    got = compare(live, load_sample(broken), verbose=False)
    ok_inj = got[0] == base[0] + 1
    print(f'   {"✅" if ok_inj else "🔴"} нет в живой стало {got[0]}, ожидалось {base[0] + 1}')

    print('\n③ РАЗЛИЧАЮЩИЙ СЛУЧАЙ — у копии образца ОТНЯТА таблица schema_migrations')
    cut = src.replace('CREATE TABLE schema_migrations (', 'CREATE TABLE sm_renamed_probe (', 1)
    con = load_sample(cut.replace('INSERT INTO schema_migrations', 'INSERT INTO sm_renamed_probe'))
    got3 = compare(live, con, verbose=False)
    # ⚠️ сверяем ИМЕННО четвёртое число: раньше здесь стояло got3 != base, и оно
    #    молча перестало различать, когда таблица сошлась в ноль (см. шапку compare).
    ok_cut = got3[3] == base[3] + 1
    print(f'   {"✅" if ok_cut else "🔴"} пропажа таблицы замечена отдельным числом: '
          f'{got3[3]} против {base[3]}')

    all_ok = ok_pair and ok_inj and ok_cut
    print('\n' + ('✅ САМОПРОВЕРКА ДЕРЖИТСЯ — сверка действительно смотрит'
                  if all_ok else '🔴 САМОПРОВЕРКА СЛОМАНА — числам прогона верить нельзя'))
    return 0 if all_ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--live', default=LIVE_DEFAULT)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest(a.live))
    live = sqlite3.connect(f'file:{a.live}?mode=ro', uri=True)
    smp = load_sample(open(SAMPLE, encoding='utf-8').read())
    print('=' * 78)
    print('РАСХОЖДЕНИЕ ОБРАЗЦА С ЖИВОЙ БАЗОЙ · предмет: ' + ' · '.join(SUBJECT))
    print(f'образец: {SAMPLE}\nживая:   {a.live} (только чтение)')
    print('=' * 78)
    m, e, d, absent = compare(live, smp)
    print('\n' + '=' * 78)
    print(f'ИТОГО: нет в живой {m} · нет в образце {e} · разошлись типом {d} · '
          f'таблиц не сошлось {absent}')
    print('⚖️ ГРАНИЦА: сравниваются ТОЛЬКО три таблицы и только состав/тип колонок.')
    print('   CHECK-контракты, FK, витрины и триггеры сюда НЕ входят — они называются словами.')
    print('=' * 78)


if __name__ == '__main__':
    main()
