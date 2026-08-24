#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА защиты памяти роли в save-phoenix.py.

Случай @RCC 2026-08-07 16:56 UTC: секция слепка обнулилась при записи, инструмент принял
пустоту и отчитался «OK … (0 chars)». Проверка живости смотрит на ВРЕМЯ сохранения, а не на
РАЗМЕР ⇒ обнулённая секция выглядит свежайшей. Пустой слепок неотличим от идеально свежего.

ШЕСТЬ случаев, ЧЕТЫРЕ различающих. У каждого различающего — КОНТРОЛЬ: рядом стоит заведомо
законное сохранение, которое обязано пройти. Иначе «отказал» ничего не доказывает: инструмент
мог падать на чём угодно.
> Отказ засчитывается за верное поведение ТОЛЬКО когда доказано, что тот же прогон пропускает
> законное. Иначе мы проверили не различение, а поломку.

  ① пустое тело ................................. ОТКАЗ, тело в базе ЦЕЛО
  ② тело из пробелов и переводов строки ......... ОТКАЗ (пустота бывает невидимой)
  ③ обвал в разы без слова ...................... ОТКАЗ
  ④ обвал в разы СО словом --allow-shrink ....... проходит
  ⑤ короткая секция впервые (launcher, 1 строка)  проходит — порога «не меньше 200» тут НЕТ
  ⑥ обычное сохранение .......................... проходит, печатает ДВА числа

⬆️ ДОПИСАНО 2026-08-24 (заявка @OPSSRE, записки #3756 и #3776 — применяла @PROTO).
Прежний затвор «сокращение в 4 раза» не срабатывал НИ РАЗУ за 15 дней зрелого периода,
включая сам инцидент 21.08 (18808 → 7455 знаков, потеря 60.4 % — а требовалось 75 %).
Порог откалиброван замером: 40 % даёт ~0.9 отказа в сутки; 30 % — 1.5, и защита,
останавливающая роль по четыре раза в день, обучает обходить её не глядя.

  ⑦ потеря 61 % ................................. ОТКАЗ, исчезающие блоки НАЗВАНЫ
  ⑧ КОНТРОЛЬ к ⑦: потеря 18 % ................... проходит
  ⑨ секция БЕЗ разметки, потеря 65 % ............ отчёт НЕ молчит и признаётся в этом
  ⑩ прежнее тело легло в историю ................ ДОСЛОВНО
  ⑪ возврат из истории .......................... тело побайтно, прежние версии целы
  ⑫ чистка ...................................... 10 свежих ПЛЮС самая длинная
  ⑬ база БЕЗ таблицы истории .................... проходит, но предупреждает и метит журнал
  ⑭ второй путь вызова, отказ ................... код 4, а не «успех»
  ⑮ ВСТРЕЧНЫЙ к ⑭: второй путь, законное ........ код 0
  ⑯ ОБРАТНЫЙ ХОД: порог ослаблен ................ инцидент ПРОСКАКИВАЕТ
  ⑰ ОБРАТНЫЙ ХОД: чистка без «самой длинной» .... длинная версия ТЕРЯЕТСЯ

🎯 ⑯ и ⑰ — главные: без них зелень ⑦–⑫ означала бы «сегодня не болит», а не «работает».
🩸 И урок @OPSSRE, оплаченный его же прогоном: КАЖДЫЙ случай строит СВОЁ состояние.
   Его первая поломка оставила в базе урезанное тело, и следующая проверка мерила уже
   РОСТ, а не потерю, — то есть зеленела, ничего не проверив.

⛔ Живой базы не касается: своя временная база в песочнице.
"""
import os
import re
import sqlite3
import subprocess
import sys

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

HERE = os.path.dirname(os.path.abspath(__file__))
# ⚠️ Путь ищется СНАЧАЛА рядом с приёмкой. Копия, положенная в другой каталог, целила
# в несуществующий файл и давала код 2 на ВСЕХ случаях — «красное по ложной причине»,
# зеркало того зелёного, за которое @PROTO поправил себя же сегодня в 16:40.
SAVE = os.path.join(HERE, "save-phoenix.py")
if not os.path.exists(SAVE):
    SAVE = os.path.normpath(os.path.join(HERE, "..", "..", "scripts", "save-phoenix.py"))
assert os.path.exists(SAVE), f"инструмент не найден: {SAVE} — приёмка НЕ выполнена"
LONG = "живой слепок роли. " * 40          # ~800 знаков


def build(path: str, seed=(), история=True):
    """⚡ ИСТОРИЯ ЗАВОДИТСЯ ПО УМОЛЧАНИЮ — как в живой базе после шага схемы.

    🩸 Без неё стенд испытывал бы инструмент в режиме «истории нет», то есть ПОЛОВИНУ:
    все шесть прежних случаев шли по ветке предупреждения и не касались ни записи версий,
    ни чистки, ни возврата. Стенд, не воспроизводящий раскладку, проверяет не тот предмет —
    класс, за который контур платил трижды.
    ⚖️ Режим «истории нет» остаётся законным (база до шага схемы, свежий контур) и
    проверяется отдельным случаем ⑬, а не молчаливо всеми.
    """
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT,
                   PRIMARY KEY (role, section))""")
    con.execute("""CREATE TABLE audit_log (id INTEGER PRIMARY KEY, timestamp TEXT
                   DEFAULT (datetime('now')), actor_role TEXT, action TEXT, target TEXT,
                   diff_md TEXT)""")
    if история:
        con.execute("""CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, role TEXT NOT NULL,
                       section TEXT NOT NULL, body TEXT NOT NULL, body_chars INTEGER NOT NULL,
                       saved_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
                       prev_chars INTEGER)""")
    for role, section, body in seed:
        con.execute("INSERT INTO phoenix VALUES (?,?,?,datetime('now'))", (role, section, body))
        if история:
            con.execute("""INSERT INTO phoenix_history (role, section, body, body_chars,
                           saved_at, actor, reason, prev_chars)
                           VALUES (?,?,?,?,datetime('now'),'migration','seed',NULL)""",
                        (role, section, body, len(body)))
    con.commit()
    con.close()


def версии(path: str, section: str = "state"):
    con = sqlite3.connect(path)
    строки = con.execute("SELECT id, body_chars, reason, body FROM phoenix_history "
                         "WHERE role='RCC' AND section=? ORDER BY id", (section,)).fetchall()
    con.close()
    return строки


def save(path: str, section: str, body: str, extra=()):
    r = subprocess.run([sys.executable, SAVE, "--db", path, "--role", "RCC",
                        "--section", section, "--body", body, *extra],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def body_of(path: str, section: str) -> str:
    con = sqlite3.connect(path)
    row = con.execute("SELECT body FROM phoenix WHERE role='RCC' AND section=?",
                      (section,)).fetchone()
    con.close()
    return row[0] if row else ""


CASES = 0
DIFFERENTIATING = 0


def case(title: str, verdict: bool, detail: str, differ: bool = False) -> bool:
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def fresh(tmp: str, name: str) -> str:
    """База с ДВУМЯ секциями: испытуемая state и контрольная plan."""
    path = os.path.join(tmp, f"{name}.db")
    build(path, [("RCC", "state", LONG), ("RCC", "plan", LONG)])
    return path


def control_passes(path: str) -> bool:
    """Контроль: законное сохранение в соседнюю секцию обязано пройти в том же прогоне."""
    out, code = save(path, "plan", LONG + " и ещё немного")
    return code == 0 and "OK" in out


def main() -> int:
    tmp = str(mezo_stand.new("bite-phoenix-empty-"))
    ok = True

    # ⛔ «НЕ ЗАПУСТИЛАСЬ» — ОТДЕЛЬНЫЙ ИСХОД, А НЕ СЕМНАДЦАТЬ КРАСНЫХ.
    # 🩸 Замер 2026-08-24 23:35 UTC: эта же приёмка, положенная в образец и позванная
    # НА МЕСТЕ, дала 17 красных из 17 — не потому, что защита сломана, а потому, что
    # образец не является контуром: инструмент ищет контейнер вверх по дереву и не находит.
    # ⚖️ Разница не косметическая. Семнадцать красных читаются как «защита развалилась»
    # и учат не верить красному вообще; «не запускалась» говорит правду — опыта не было.
    # ⇒ Пробуем инструмент ОДИН раз на заведомо законном сохранении. Не работает —
    #   выходим кодом 2, тем же, каким контур метит отказ мерить.
    _проба = os.path.join(tmp, "проба-запуска.db")
    build(_проба)
    _вывод, _код = save(_проба, "launcher", "проба запуска инструмента")
    if _код != 0:
        print("⛔ ПРИЁМКА НЕ ЗАПУСТИЛАСЬ: инструмент не отвечает даже на заведомо законном")
        print(f"   сохранении (код {_код}). Это НЕ провал защиты — опыта не было вовсе.")
        for _s in (_вывод or "").strip().splitlines()[:4]:
            print(f"   | {_s}")
        print(f"   👉 Инструмент: {SAVE}")
        print("   👉 Обычная причина: приёмку позвали В ОБРАЗЦЕ, а не в контуре. Образец")
        print("      разворачивают (init-group.py), и там она работает — проверено прогоном.")
        return 2

    # ① пустое тело
    p = fresh(tmp, "a")
    out, code = save(p, "state", "")
    kept = body_of(p, "state") == LONG
    ok &= case("① пустое тело: ОТКАЗ, прежний текст цел",
               code != 0 and kept and control_passes(p),
               f"код возврата {code} · тело в базе {'цело' if kept else 'ПОТЕРЯНО'} · "
               f"контрольное сохранение прошло", differ=True)

    # ② невидимая пустота
    p = fresh(tmp, "b")
    out, code = save(p, "state", "   \n\n\t  \n")
    kept = body_of(p, "state") == LONG
    ok &= case("② пробелы и переводы строки — та же пустота",
               code != 0 and kept and control_passes(p),
               f"код возврата {code} · тело {'цело' if kept else 'ПОТЕРЯНО'} · "
               "пустота бывает невидимой глазом", differ=True)

    # ③ обвал в разы без слова
    p = fresh(tmp, "c")
    out, code = save(p, "state", "коротко")
    kept = body_of(p, "state") == LONG
    ok &= case("③ обвал в разы без слова: ОТКАЗ",
               code != 0 and kept and "allow-shrink" in out and control_passes(p),
               f"800 знаков → 7 · код {code} · инструмент НАЗВАЛ ручку, которой это разрешить",
               differ=True)

    # ④ обвал СО словом — проходит
    p = fresh(tmp, "d")
    out, code = save(p, "state", "коротко", extra=["--allow-shrink"])
    ok &= case("④ то же самое СО словом --allow-shrink: проходит",
               code == 0 and body_of(p, "state") == "коротко",
               f"код {code} · сознательная чистка не запрещена, она НАЗВАНА")

    # ⑤ короткая секция впервые — порога длины нет
    p = os.path.join(tmp, "e.db")
    build(p)
    out, code = save(p, "launcher", "Прочитай слепок роли RCC и работай по нему.")
    ok &= case("⑤ короткая секция ВПЕРВЫЕ проходит (launcher — законно одна строка)",
               code == 0 and body_of(p, "launcher").startswith("Прочитай"),
               f"код {code} · глухой порог «не меньше 200 знаков» убил бы эту секцию",
               differ=True)

    # ⑥ обычное сохранение печатает ДВА числа
    p = fresh(tmp, "f")
    out, code = save(p, "state", LONG + " дополнение")
    two = bool(re.search(r"было \d+ → стало \d+", out))
    ok &= case("⑥ обычное сохранение печатает «было → стало»",
               code == 0 and two,
               f"код {code} · два числа спорят сами: «10489 → 0» не прочитаешь как успех "
               f"{'' if two else '— НО ИХ НЕТ В ВЫВОДЕ'}")

    # ═══════════════════════════════════════════════════════════════════════════
    # ДОПИСАНО 2026-08-24 — порог по доле, отчёт содержимым, история версий
    # ═══════════════════════════════════════════════════════════════════════════
    БОЛЬШОЕ = "\n".join(f"## Раздел {i}\nсодержательная строка раздела {i}, довольно длинная\n"
                        f"вторая содержательная строка раздела {i}, тоже длинная"
                        for i in range(20))

    # ⑦ ПОТЕРЯ 61 % — ОТКАЗ, и блоки названы ПОИМЁННО, а не числом.
    p = os.path.join(tmp, "g.db")
    build(p, [("RCC", "state", БОЛЬШОЕ), ("RCC", "plan", LONG)])
    out, code = save(p, "state", БОЛЬШОЕ[:int(len(БОЛЬШОЕ) * 0.39)])
    названы = "ИСЧЕЗАЮТ БЛОКИ" in out and "Раздел 1" in out
    ok &= case("⑦ потеря 61 % — ОТКАЗ, исчезающие блоки НАЗВАНЫ поимённо",
               code != 0 and названы and body_of(p, "state") == БОЛЬШОЕ and control_passes(p),
               f"код {code} · блоки {'названы' if названы else 'НЕ НАЗВАНЫ'} · "
               "прежний затвор «в 4 раза» здесь молчал: требовалось 75 %", differ=True)

    # ⑧ КОНТРОЛЬ к ⑦: потеря 18 % — законная правка, обязана пройти.
    p = os.path.join(tmp, "h.db")
    build(p, [("RCC", "state", БОЛЬШОЕ)])
    out, code = save(p, "state", БОЛЬШОЕ[:int(len(БОЛЬШОЕ) * 0.82)])
    ok &= case("⑧ КОНТРОЛЬ к ⑦: потеря 18 % — проходит",
               code == 0,
               f"код {code} · без этого случая ⑦ доказывал бы лишь то, что инструмент "
               "умеет отказывать — а не то, что он РАЗЛИЧАЕТ", differ=True)

    # ⑨ СЕКЦИЯ БЕЗ РАЗМЕТКИ. Замер по живой базе: у 16 секций из 63 заголовков «## » нет
    #    вовсе. Отчёт «по блокам» молчал бы на четверти контура, и молчание читалось бы
    #    как «ничего не исчезло».
    ПЛОСКОЕ = "\n".join(f"строка номер {i}, достаточно длинная чтобы считаться содержательной"
                        for i in range(60))
    p = os.path.join(tmp, "i.db")
    build(p, [("RCC", "state", ПЛОСКОЕ)])
    out, code = save(p, "state", ПЛОСКОЕ[:int(len(ПЛОСКОЕ) * 0.35)])
    признался = "НИЧЕГО НЕ ЛОВИТ" in out or "разметки нет" in out
    ok &= case("⑨ секция БЕЗ разметки — отчёт НЕ молчит и признаётся, что признак бессилен",
               code != 0 and признался and "исчезло дословно" in out,
               f"код {code} · {'признался' if признался else 'СКАЗАЛ «блоки целы» — успокаивающая ложь'}"
               " · «нечем сравнить» и «всё цело» не имеют права выглядеть одинаково",
               differ=True)

    # ⑩ ПРЕЖНЕЕ ТЕЛО В ИСТОРИИ — дословно, а не «примерно столько же знаков».
    p = os.path.join(tmp, "j.db")
    build(p, [("RCC", "state", БОЛЬШОЕ)])
    out, code = save(p, "state", БОЛЬШОЕ + "\n## Раздел 20\nдописанное")
    в_истории = [v for v in версии(p) if v[3] == БОЛЬШОЕ]
    ok &= case("⑩ прежнее тело легло в историю ДОСЛОВНО",
               code == 0 and bool(в_истории),
               f"версий {len(версии(p))} · прежнее тело "
               f"{'найдено дословно' if в_истории else 'НЕ НАЙДЕНО'} · возврат обязан быть "
               "копированием: сборка по частям добавляет шаг, на котором «не смог собрать» "
               "превращается в «данных нет»", differ=True)

    # ⑪ ВОЗВРАТ ИЗ ИСТОРИИ — побайтно, прежние версии целы, возврат ложится НОВОЙ версией.
    p = os.path.join(tmp, "k.db")
    build(p, [("RCC", "state", БОЛЬШОЕ)])
    save(p, "state", БОЛЬШОЕ[:int(len(БОЛЬШОЕ) * 0.82)])
    было_версий = len(версии(p))
    цель = версии(p)[0][0]
    r = subprocess.run([sys.executable, SAVE, "--db", p, "--role", "RCC", "--section", "state",
                        "--restore", str(цель)], capture_output=True, text=True,
                       encoding="utf-8")
    вернулось = body_of(p, "state") == БОЛЬШОЕ
    стало_версий = len(версии(p))
    ok &= case("⑪ возврат из истории — тело ПОБАЙТНО, прежние версии целы, лёг новой версией",
               r.returncode == 0 and вернулось and стало_версий == было_версий + 1,
               f"код {r.returncode} · тело {'побайтно' if вернулось else 'РАЗОШЛОСЬ'} · "
               f"версий {было_версий} → {стало_версий} · откат отката тоже возможен",
               differ=True)

    # ⑫ ЧИСТКА: последние десять ПЛЮС самая длинная. Окно по свежести прогорает —
    #    замер даёт до 15 сохранений одной секции в сутки.
    p = os.path.join(tmp, "l.db")
    build(p, [("RCC", "state", БОЛЬШОЕ)])
    среднее = БОЛЬШОЕ[:int(len(БОЛЬШОЕ) * 0.72)]
    коды = []
    for i in range(14):
        _, c = save(p, "state", среднее + f"\nправка {i}")
        коды.append(c)
    сохранённые = версии(p)
    длинная_цела = any(v[1] == len(БОЛЬШОЕ) for v in сохранённые)
    ok &= case("⑫ чистка: осталось 10 свежих ПЛЮС самая длинная",
               set(коды) == {0} and len(сохранённые) == 11 and длинная_цела,
               f"версий {len(сохранённые)} · самая длинная "
               f"{'сбережена' if длинная_цела else 'ПОТЕРЯНА'} · по свежести она вылетела бы",
               differ=True)

    # ⑬ БАЗА БЕЗ ТАБЛИЦЫ ИСТОРИИ — сохранение НЕ запрещается, но отсутствие говорится
    #    вслух И ложится в журнал. Один шаг схемы не вправе обездвижить память всех ролей;
    #    тихая деградация была бы худшим исходом.
    p = os.path.join(tmp, "m.db")
    build(p, [("RCC", "state", LONG)], история=False)
    out, code = save(p, "state", LONG + " дополнение")
    con = sqlite3.connect(p)
    метка = con.execute("SELECT diff_md FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    в_журнале = bool(метка) and "БЕЗ ИСТОРИИ" in (метка[0] or "")
    ok &= case("⑬ база БЕЗ таблицы истории — проходит, но предупреждает И метит журнал",
               code == 0 and "ИСТОРИИ НЕТ" in out and в_журнале,
               f"код {code} · пометка в журнале {'есть' if в_журнале else 'ОТСУТСТВУЕТ'} · "
               "иначе потеря снова стала бы необратимой, и никто бы не узнал", differ=True)

    # ⑭⑮ ВТОРОЙ ПУТЬ ВЫЗОВА. Находка @OPSSRE (записка #3776): защита срабатывает верно,
    #     а ИСХОД всей операции объявлялся успехом — роль в конце смены видела код 0
    #     и уходила, память при этом не сохранена.
    #     🔴 Новый порог делает отказы частыми (было 0 за 15 дней, стало ~0.9 в сутки) ⇒
    #     редкий невидимый дефект стал бы частым невидимым.
    WM = os.path.join(HERE, "write-message.py")
    if os.path.exists(WM):
        контур = os.path.join(tmp, "контур", ".mezosync")
        os.makedirs(os.path.join(контур, "scripts"), exist_ok=True)
        import shutil as _sh
        for имя in os.listdir(HERE):
            if имя.endswith(".py"):
                _sh.copy(os.path.join(HERE, имя), os.path.join(контур, "scripts", имя))
        pdb = os.path.join(контур, "mezosync.db")
        build(pdb, [("RCC", "state", БОЛЬШОЕ)])
        con = sqlite3.connect(pdb)
        con.execute("""CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY,
                       writer_role TEXT, timestamp TEXT, body_md TEXT, tags TEXT,
                       priority TEXT, resolved INTEGER, broadcast INTEGER, addressed_by TEXT)""")
        con.commit(); con.close()
        файл = os.path.join(tmp, "урезанное.md")
        with open(файл, "w", encoding="utf-8") as f:
            f.write(БОЛЬШОЕ[:int(len(БОЛЬШОЕ) * 0.39)])
        r = subprocess.run([sys.executable, os.path.join(контур, "scripts", "write-message.py"),
                            "--db", pdb, "--role", "RCC", "--body", "проба второго пути",
                            "--save-state", файл],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        весь = (r.stdout or "") + (r.stderr or "")
        ok &= case("⑭ второй путь вызова, отказ памяти — код 4, а не «успех»",
                   r.returncode == 4 and "ПОВТОРЯТЬ НЕ НАДО" in весь,
                   f"код {r.returncode} · из «записку откатывать нельзя» не следует "
                   "«операция удалась» · текст запрещает повтор явным словом, иначе "
                   "красное читается как «не ушло» и рождается дубль", differ=True)

        файл2 = os.path.join(tmp, "законное.md")
        with open(файл2, "w", encoding="utf-8") as f:
            f.write(БОЛЬШОЕ + "\n## Раздел 20\nдописанное")
        r2 = subprocess.run([sys.executable, os.path.join(контур, "scripts", "write-message.py"),
                             "--db", pdb, "--role", "RCC", "--body", "проба законного",
                             "--save-state", файл2],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok &= case("⑮ ВСТРЕЧНЫЙ к ⑭: второй путь, законное сохранение — код 0",
                   r2.returncode == 0,
                   f"код {r2.returncode} · без встречного ⑭ доказывал бы лишь, что путь "
                   "умеет краснеть", differ=True)
    else:
        ok &= case("⑭⑮ второй путь вызова", False,
                   f"⛔ НЕ ЗАПУЩЕНЫ: не найден {WM}. Молча пропустить нельзя — "
                   "это был бы зелёный без опыта")

    # ⑯ ОБРАТНЫЙ ХОД ПО ПОРОГУ. Ослабляем порог и требуем, чтобы инцидент ПРОСКОЧИЛ.
    #    Без этого случая ⑦ означал бы «сегодня отказало», а не «отказало из-за порога».
    сломанный_каталог = os.path.join(tmp, "порог-ослаблен")
    os.makedirs(сломанный_каталог, exist_ok=True)
    исходник = open(SAVE, encoding="utf-8").read()
    ослаблен = исходник.replace("SHRINK_HARD = 0.40", "SHRINK_HARD = 0.99", 1)
    if ослаблен == исходник:
        ok &= case("⑯ ОБРАТНЫЙ ХОД: порог ослаблен — инцидент ПРОСКАКИВАЕТ", False,
                   "⛔ НЕ ЗАПУСТИЛСЯ: строки порога в инструменте нет — он менялся, "
                   "правь приёмку. Зелёный без опыта здесь недопустим")
    else:
        путь_сломанного = os.path.join(сломанный_каталог, "save-phoenix.py")
        with open(путь_сломанного, "w", encoding="utf-8") as f:
            f.write(ослаблен)
        import shutil as _sh2
        for сосед in ("mezo_paths.py", "dryrun.py"):
            если_есть = os.path.join(HERE, сосед)
            if os.path.exists(если_есть):
                _sh2.copy(если_есть, os.path.join(сломанный_каталог, сосед))
        p = os.path.join(tmp, "n.db")
        build(p, [("RCC", "state", БОЛЬШОЕ)])
        r = subprocess.run([sys.executable, путь_сломанного, "--db", p, "--role", "RCC",
                            "--section", "state", "--body", БОЛЬШОЕ[:int(len(БОЛЬШОЕ) * 0.39)]],
                           capture_output=True, text=True, encoding="utf-8")
        ok &= case("⑯ ОБРАТНЫЙ ХОД: порог ослаблен — инцидент ПРОСКАКИВАЕТ",
                   r.returncode == 0,
                   f"код ослабленного {r.returncode} против отказа у настоящего — "
                   "разница и есть доказательство, что ловит именно порог", differ=True)

    # ⑰ ОБРАТНЫЙ ХОД ПО ЧИСТКЕ. Меняем «самая длинная» на «самая короткая» — длинная
    #    обязана потеряться. Поломка СИНТАКСИЧЕСКИ ВЕРНА: сломать сам запрос значило бы
    #    испытывать падение, а не предмет (моя же ошибка при первом прогоне поломок).
    сломанная_чистка = os.path.join(tmp, "чистка-сломана")
    os.makedirs(сломанная_чистка, exist_ok=True)
    порча = исходник.replace("ORDER BY body_chars DESC, id DESC LIMIT 1",
                             "ORDER BY body_chars ASC, id DESC LIMIT 1", 1)
    if порча == исходник:
        ok &= case("⑰ ОБРАТНЫЙ ХОД: чистка без «самой длинной» — длинная ТЕРЯЕТСЯ", False,
                   "⛔ НЕ ЗАПУСТИЛСЯ: места чистки в инструменте нет — правь приёмку")
    else:
        путь_порчи = os.path.join(сломанная_чистка, "save-phoenix.py")
        with open(путь_порчи, "w", encoding="utf-8") as f:
            f.write(порча)
        import shutil as _sh3
        for сосед in ("mezo_paths.py", "dryrun.py"):
            если_есть = os.path.join(HERE, сосед)
            if os.path.exists(если_есть):
                _sh3.copy(если_есть, os.path.join(сломанная_чистка, сосед))
        p = os.path.join(tmp, "o.db")
        build(p, [("RCC", "state", БОЛЬШОЕ)])
        коды2 = []
        for i in range(13):
            r = subprocess.run([sys.executable, путь_порчи, "--db", p, "--role", "RCC",
                                "--section", "state", "--body", среднее + f"\nправка {i}"],
                               capture_output=True, text=True, encoding="utf-8")
            коды2.append(r.returncode)
        осталось = версии(p)
        длинная_цела2 = any(v[1] == len(БОЛЬШОЕ) for v in осталось)
        ok &= case("⑰ ОБРАТНЫЙ ХОД: чистка без «самой длинной» — длинная ТЕРЯЕТСЯ",
                   set(коды2) == {0} and not длинная_цела2,
                   f"записи прошли: {set(коды2) == {0}} · длинная "
                   f"{'ЦЕЛА — поломка не сработала' if длинная_цела2 else 'потеряна'} · "
                   "поломка обязана быть синтаксически верной, иначе испытывается падение",
                   differ=True)

    print()
    print(f"✅ ЗАЩИТА ПРИНЯТА — случаев {CASES}, различающих {DIFFERENTIATING}, "
          "у каждого различающего контроль" if ok
          else "🔴 ЗАЩИТА НЕ ПРИНЯТА")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
