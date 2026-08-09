#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРАВИЛО ВЕРНО ≠ ПРАВИЛО ПОЗВАНО ВЕРНО: обязательный довод потерян в вызове.

ПРЕДМЕТ. Общий предикат может быть безупречен и всё равно врать половине потребителей —
если один из них зовёт его БЕЗ довода, от которого зависит ответ. Пример, оплаченный
контуром 2026-08-08: витрина срочности зовётся с именем читателя, и «своя нота» гаснет
только автору. Забудь довод у ОДНОГО из двух вызовов — предикат честен, а витрины
разъезжаются МОЛЧА: у одной своя нота горит, у другой нет.

🎯 Класс по другой оси, чем «сдано у автора ≠ доступно потребителю»:
   там расходились КОПИИ, здесь расходятся ВЫЗОВЫ одной и той же копии.
📌 Цена уже известна: механизм гашения срочности жил в базе и не был позван НИ РАЗУ —
   0 из 546. Правильный механизм, мимо которого проходит дорога, неотличим от отсутствующего.

ЧТО ПРОВЕРЯЕТСЯ. Для названной пары «функция → обязательный довод»: каждый ВЫЗОВ этой
функции во всех разобранных файлах передаёт довод — по имени либо позиционно.

⚖️ ПОТОЛОК, ПЕЧАТАЕТСЯ ВСЕГДА: разбирается СТАТИКА (дерево кода). Вызов через словарь,
getattr или строку проверка не увидит и об этом говорит. «Чисто» здесь значит «в прямых
вызовах чисто», а не «нигде нет».
"""
import argparse
import ast
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

# Пары «функция · обязательный довод · почему он обязателен».
# Заводить сюда стоит ТОЛЬКО довод, от которого меняется ОТВЕТ, а не оформление:
# иначе проверка станет ворчливой и её перестанут читать.
WATCHED = {
    ("annotate", "reader"): "витрина персональна: без читателя «своя нота» не отличима",
    ("urgency_state", "reader"): "тот же предикат: ответ зависит от того, КТО смотрит",
    ("machine_block", "role"): "машинный слой собирается ДЛЯ РОЛИ, без неё он бессмыслен",
}


def calls_in(path: Path):
    """→ ([(имя, узел вызова, строка)], {имя функции: [имена её доводов]}, ошибка)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), str(path))
    except SyntaxError as e:
        return [], {}, f"{path.name}: не разобрался ({e.lineno}) — НЕ проверен"
    out, sigs = [], {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            sigs[node.name] = [a.arg for a in node.args.args]
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
        if name:
            out.append((name, node, node.lineno))
    return out, sigs, None


def check(paths, verbose=False):
    findings, skipped, checked_calls = [], [], 0
    all_calls, sigs = [], {}
    for p in paths:                      # первый проход — собрать СИГНАТУРЫ отовсюду
        calls, s, err = calls_in(p)
        if err:
            skipped.append(err)
            continue
        # 🪤 ЗАГЛУШКА НЕ ДОЛЖНА ПЕРЕКРЫВАТЬ НАСТОЯЩУЮ СИГНАТУРУ. Рядом с живой функцией
        # часто стоит запасная — `def f(*_a, **_k)` в ветке except, чтобы падение модуля
        # не роняло инструмент. У неё доводов НЕТ, и первая редакция мерила вызовы по ней:
        # обвинила пять ВЕРНЫХ вызовов, включая свой же образцовый.
        # ⇒ Из нескольких определений одного имени берём САМОЕ ПОДРОБНОЕ: оно и есть контракт,
        # а заглушка — лишь способ пережить его отсутствие.
        for name, params in s.items():
            if len(params) > len(sigs.get(name, [])):
                sigs[name] = params
        all_calls.append((p, calls))

    for p, calls in all_calls:
        for name, node, line in calls:
            for (fn, arg), why in WATCHED.items():
                if name != fn:
                    continue
                checked_calls += 1
                by_name = any(k.arg == arg for k in node.keywords)
                by_star = any(k.arg is None for k in node.keywords)   # **kwargs — не судим
                # 🪤 ПОЗИЦИЮ ДОВОДА БЕРЁМ ИЗ СИГНАТУРЫ, А НЕ ИЗ ГОЛОВЫ. Первая редакция
                # считала «позиционных ≥ 4» — магическое число — и объявила НЕВЕРНЫМ верный
                # вызов machine_block(db, role), где довод стоит вторым. То есть проверка
                # обвинила исправное, будучи заведена ровно против такого класса.
                # ⇒ Если сигнатура известна, довод передан позиционно, когда позиционных
                # аргументов хватает до его места. Сигнатура неизвестна — НЕ СУДИМ и
                # говорим об этом: обвинение вслепую хуже пропуска.
                params = sigs.get(fn)
                if params is None:
                    if verbose:
                        print(f"   ⚠️ {p.name}:{line} {fn}(…) — сигнатура не найдена, не сужу")
                    continue
                idx = params.index(arg) if arg in params else None
                positional_enough = idx is not None and len(node.args) > idx
                if not (by_name or by_star or positional_enough):
                    findings.append((p, line, fn, arg, why))
                elif verbose:
                    print(f"   ✅ {p.name}:{line} {fn}(… {arg} передан)")
    return findings, skipped, checked_calls


def main() -> int:
    ap = argparse.ArgumentParser(description="обязательный довод потерян в вызове")
    ap.add_argument("--dir", action="append", default=None,
                    help="каталог с кодом; можно несколько. По умолчанию — живые скрипты")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--strict", action="store_true", help="вернуть 1 при находках")
    args = ap.parse_args()

    dirs = [Path(d) for d in (args.dir or [str(mezo_paths.live_scripts())])]
    paths = sorted({p for d in dirs if d.exists() for p in d.glob("*.py")})
    if not paths:
        print("⛔ файлов не найдено — проверять НЕЧЕГО. Это НЕ «чисто».")
        return 1

    findings, skipped, n = check(paths, args.verbose)

    print("=" * 74)
    print("ОБЯЗАТЕЛЬНЫЙ ДОВОД, ПОТЕРЯННЫЙ В ВЫЗОВЕ")
    print("=" * 74)
    print(f"файлов разобрано ......... {len(paths)}")
    print(f"вызовов под надзором ..... {n}   (пар «функция · довод»: {len(WATCHED)})")
    print(f"не разобрались ........... {len(skipped)}")
    for s in skipped:
        print(f"   ⚠️ {s}")
    print()
    if findings:
        print(f"🔴 ДОВОД НЕ ПЕРЕДАН — {len(findings)}:")
        for p, line, fn, arg, why in findings:
            print(f"   {p.name}:{line}  {fn}(…) без «{arg}»")
            print(f"      почему важно: {why}")
    else:
        print("✅ во всех прямых вызовах довод передан")

    print()
    print("⚖️ ПОТОЛОК: разбирается СТАТИКА. Вызов через словарь, getattr или строку эта")
    print("   проверка НЕ ВИДИТ. «Чисто» значит «в прямых вызовах чисто», а не «нигде нет».")
    if n == 0:
        print("🔴 И ГЛАВНОЕ: под надзором НЕ ОКАЗАЛОСЬ НИ ОДНОГО ВЫЗОВА — значит проверка")
        print("   не подтвердила ничего. Ложный ноль опаснее находки.")
        return 1
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
