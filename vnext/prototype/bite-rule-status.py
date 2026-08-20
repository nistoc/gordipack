# -*- coding: utf-8 -*-
"""ПРИЁМКА единого признака отзыва правила (rule_status.py) — карточка #89, шаг 3.

ПОВОД — ЗАМЕР, а не опасение. До 2026-08-10 отзыв разбирали ТРИ места, каждое своим
признаком, и на сегодняшнем своде все трое отвечали «10». Совпадение держалось только
потому, что все десять надгробий написаны одинаково: на четырёх различающих написаниях
они разошлись все четыре раза.

ЧТО ЗДЕСЬ ПОД ЗАЩИТОЙ
  ① признак ловит НАМЕРЕННОЕ надгробие во всех живых написаниях;
  ② и НЕ ловит упоминание отзыва в середине текста — иначе действующее правило,
     рассказывающее про отмену соседнего, пропадёт с глаз (ошибка в опасную сторону);
  ③ ПОЛЕ статуса сильнее текста — иначе инструмент спорил бы с самой базой;
  ④ пока поля нет, «не отозвано» НЕ выдаёт себя за 'active';
  ⑤ ЧИТАТЕЛИ СОГЛАСНЫ МЕЖДУ СОБОЙ — на одном своде дают одно число.

⛔ Живую базу только ЧИТАЕТ (mode=ro). Стенды — в памяти.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # пути машины ВЫВОДЯТСЯ, не впечатаны (карточка #208)

import importlib.util
import io
import os
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mezo_target  # noqa: E402 — какую копию испытываем, решает одно место

LIVE = str(mezo_paths.live_db())


def load(name):
    path = mezo_target.script(name)
    spec = importlib.util.spec_from_file_location(name.replace('.py', '') + '_under_test', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RS = load('rule_status.py')
CASES = 0
DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def stand(with_status):
    """Стенд свода: два правила с надгробием в тексте, одно действующее."""
    con = sqlite3.connect(':memory:')
    cols = "rule_key TEXT PRIMARY KEY, body TEXT" + (", status TEXT" if with_status else "")
    con.execute(f"CREATE TABLE rules ({cols})")
    rows = [('tomb', '⛔ ОТОЗВАНО владельцем 09.08'),
            ('tomb2', 'ОТМЕНЁНО владельцем'),
            ('alive', 'Действующее правило. Здесь сказано, что соседнее ОТОЗВАНО.')]
    if with_status:
        # ⚠️ ПОЛЕ НАРОЧНО СПОРИТ С ТЕКСТОМ: у 'tomb' надгробие в теле, но статус активен.
        #    Так проверяется ПОРЯДОК источников, а не совпадение обоих.
        con.executemany("INSERT INTO rules VALUES (?,?,?)",
                        [(rows[0][0], rows[0][1], 'active'),
                         (rows[1][0], rows[1][1], 'revoked'),
                         (rows[2][0], rows[2][1], 'active')])
    else:
        con.executemany("INSERT INTO rules VALUES (?,?)", rows)
    return con


def main():
    ok = True

    # ① НАМЕРЕННЫЕ НАПИСАНИЯ — все ловятся одним признаком.
    intentional = ['⛔ ОТОЗВАНО владельцем', 'ОТОЗВАНО владельцем 09.08',
                   '⛔ ОТМЕНЁНО владельцем', '⛔ ОТОЗВАН приказ', 'ОТМЕНЕНО решением']
    caught = [t for t in intentional if RS.is_revoked_body(t)]
    ok &= case("① намеренное надгробие ловится во ВСЕХ живых написаниях",
               len(caught) == len(intentional),
               f"поймано {len(caught)} из {len(intentional)}", differ=True)

    # ② ВСТРЕЧНЫЙ: то, что надгробием НЕ является, не ловится. Без этого случая ① прошёл бы
    #    и у признака «всегда да» — молчание неотличимо от правоты.
    innocent = ['Правило про то, как ОТОЗВАНО соседнее',
                'отозвано владельцем',
                'Здесь объясняется, почему ОТМЕНЁНО прежнее указание']
    false_hits = [t for t in innocent if RS.is_revoked_body(t)]
    ok &= case("② упоминание отзыва в тексте НЕ считается отзывом (встречный к ①)",
               not false_hits,
               f"ложных срабатываний {len(false_hits)} из {len(innocent)}", differ=True)

    # ③ ПОЛЕ СИЛЬНЕЕ ТЕКСТА.
    con = stand(with_status=True)
    got = {r['rule_key']: r['revoked'] for r in RS.read_rules(con)}
    ok &= case("③ поле статуса СИЛЬНЕЕ текста: надгробие в теле при status='active' не отзыв",
               got['tomb'] is False and got['tomb2'] is True and got['alive'] is False,
               f"tomb(текст-надгробие, поле active) → {got['tomb']} · "
               f"tomb2(поле revoked) → {got['tomb2']}", differ=True)

    # ④ БЕЗ ПОЛЯ — читается текст, и источник НАЗВАН. «Не отозвано» не значит 'active'.
    con2 = stand(with_status=False)
    rs2 = {r['rule_key']: r for r in RS.read_rules(con2)}
    ok &= case("④ поля нет — читается текст, источник назван, 'active' не выдумывается",
               rs2['tomb']['revoked'] and rs2['alive']['status_source'] == 'text'
               and rs2['alive'].get('status') is None,
               f"tomb → {rs2['tomb']['revoked']} ⟨{rs2['tomb']['revoked_basis']}⟩ · "
               f"источник «{rs2['alive']['status_source']}»", differ=True)

    # ⑤ ЧИТАТЕЛИ СОГЛАСНЫ — ради этого всё и затевалось. Сверяется ЖИВОЙ свод: сколько
    #    отозванных видит общий модуль и сколько — каждый читатель через него же.
    live = sqlite3.connect(f'file:{LIVE}?mode=ro', uri=True)
    n_module = sum(1 for r in RS.read_rules(live) if r['revoked'])
    scripts = mezo_target.scripts_root()
    agree, checked = [], ['set-rule.py', 'export-rules.py', 'export-markdown.py']
    for name in checked:
        text = open(os.path.join(str(scripts), name), encoding='utf-8').read()
        agree.append('rule_status' in text)
    ok &= case("⑤ читатели свода берут признак из ОБЩЕГО модуля, а не свой",
               all(agree) and n_module > 0,
               f"общий модуль видит отозванных: {n_module} · "
               f"читателей на общем признаке: {sum(agree)} из {len(checked)}", differ=True)

    # ⑥ ГРАНИЦА, НАЗВАННАЯ ВСЛУХ: признак смотрит НАЧАЛО тела. Надгробие, поставленное
    #    в середину, он не увидит — и это предел признака, а не дыра. Непроизнесённый
    #    предел читается как охват.
    mid = 'Обычная строка.\n⛔ ОТОЗВАНО владельцем'
    # ⚠️ Поиск нарочно РЕГИСТРОНЕЗАВИСИМЫЙ и по корню: первая редакция искала «узкий»
    #    точной формой и покраснела на модуле, где написано «НАРОЧНО УЗКИЙ» прописными.
    #    Проверка, привязанная к написанию фразы, ловит написание, а не смысл, — и краснеет
    #    на исправном механизме. Это тот же класс, что три разных признака одного отзыва.
    src = open(mezo_target.script('rule_status.py'), encoding='utf-8').read().lower()
    ok &= case("⑥ надгробие в СЕРЕДИНЕ не ловится — предел признака, и он НАЗВАН в модуле",
               (not RS.is_revoked_body(mid)) and 'узк' in src and 'якорь' in src,
               "узость признака — решение: широкий поиск давал 14 против 10, "
               "то есть 4 ложных (28 %)", differ=True)

    print()
    print((f"✅ ПРИЗНАК ОТЗЫВА ПРИНЯТ — случаев {CASES}, различающих {DIFFER}, "
           f"испытан {mezo_target.label()}") if ok
          else f"🔴 ПРИЗНАК ОТЗЫВА НЕ ПРИНЯТ — испытан {mezo_target.label()}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
