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


def build(path: str, seed=(), with_history=True):
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
    if with_history:
        con.execute("""CREATE TABLE phoenix_history (id INTEGER PRIMARY KEY, role TEXT NOT NULL,
                       section TEXT NOT NULL, body TEXT NOT NULL, body_chars INTEGER NOT NULL,
                       saved_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT NOT NULL,
                       prev_chars INTEGER)""")
        # 🩸 НАЙДЕНО ПРИ РАЗБОРЕ случаев ⑫/⑰ (задача PROTO, замер 2026-09-13): стенд заводил
        # phoenix_history БЕЗ phoenix_history_archive, а save-phoenix.py с 05.09 чистит
        # историю ТОЛЬКО когда архивная таблица есть (иначе печатает «ИСТОРИЯ НЕ ЧИСТИТСЯ» и
        # ничего не удаляет — молчаливой потери здесь нет по конструкции, см. save-phoenix.py
        # ~655-670). Стенд без архива проверял не чистку, а её ОТСУТСТВИЕ: ⑫ (10 свежих плюс
        # самая длинная) и ⑰ (обратный ход по чистке — длинная обязана потеряться) не могли
        # покраснеть НИ ПРИ КАКОЙ поломке, потому что чистка не запускалась вовсе.
        # ⚖️ Определение — ДОСЛОВНО из миграции schema (единственный источник истины для
        # формы этой таблицы): .mezosync/scripts/migrations/20260905-phoenix-history-archive.py
        con.execute("""CREATE TABLE phoenix_history_archive (
            id          INTEGER PRIMARY KEY,
            role        TEXT NOT NULL,
            section     TEXT NOT NULL,
            body        TEXT NOT NULL,
            body_chars  INTEGER NOT NULL,
            saved_at    TEXT NOT NULL,
            actor       TEXT NOT NULL,
            reason      TEXT NOT NULL,
            prev_chars  INTEGER,
            moved_at    TEXT NOT NULL DEFAULT (datetime('now')),
            moved_by    TEXT NOT NULL,
            rule        TEXT NOT NULL
        )""")
        con.execute("CREATE INDEX idx_phoenix_history_archive_role "
                    "ON phoenix_history_archive(role, section, saved_at)")
    for role, section, body in seed:
        con.execute("INSERT INTO phoenix VALUES (?,?,?,datetime('now'))", (role, section, body))
        if with_history:
            con.execute("""INSERT INTO phoenix_history (role, section, body, body_chars,
                           saved_at, actor, reason, prev_chars)
                           VALUES (?,?,?,?,datetime('now'),'migration','seed',NULL)""",
                        (role, section, body, len(body)))
    con.commit()
    con.close()


def versions(path: str, section: str = "state"):
    con = sqlite3.connect(path)
    rows = con.execute("SELECT id, body_chars, reason, body FROM phoenix_history "
                         "WHERE role='RCC' AND section=? ORDER BY id", (section,)).fetchall()
    con.close()
    return rows


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
    _probe_db = os.path.join(tmp, "проба-запуска.db")
    build(_probe_db)
    _output, _code = save(_probe_db, "launcher", "проба запуска инструмента")
    if _code != 0:
        print("⛔ ПРИЁМКА НЕ ЗАПУСТИЛАСЬ: инструмент не отвечает даже на заведомо законном")
        print(f"   сохранении (код {_code}). Это НЕ провал защиты — опыта не было вовсе.")
        for _s in (_output or "").strip().splitlines()[:4]:
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
    BIG = "\n".join(f"## Раздел {i}\nсодержательная строка раздела {i}, довольно длинная\n"
                        f"вторая содержательная строка раздела {i}, тоже длинная"
                        for i in range(20))

    # ⑦ ПОТЕРЯ 61 % — ОТКАЗ, и блоки названы ПОИМЁННО, а не числом.
    p = os.path.join(tmp, "g.db")
    build(p, [("RCC", "state", BIG), ("RCC", "plan", LONG)])
    out, code = save(p, "state", BIG[:int(len(BIG) * 0.39)])
    named = "ИСЧЕЗАЮТ БЛОКИ" in out and "Раздел 1" in out
    ok &= case("⑦ потеря 61 % — ОТКАЗ, исчезающие блоки НАЗВАНЫ поимённо",
               code != 0 and named and body_of(p, "state") == BIG and control_passes(p),
               f"код {code} · блоки {'названы' if named else 'НЕ НАЗВАНЫ'} · "
               "прежний затвор «в 4 раза» здесь молчал: требовалось 75 %", differ=True)

    # ⑧ КОНТРОЛЬ к ⑦: потеря 18 % — законная правка, обязана пройти.
    p = os.path.join(tmp, "h.db")
    build(p, [("RCC", "state", BIG)])
    out, code = save(p, "state", BIG[:int(len(BIG) * 0.82)])
    ok &= case("⑧ КОНТРОЛЬ к ⑦: потеря 18 % — проходит",
               code == 0,
               f"код {code} · без этого случая ⑦ доказывал бы лишь то, что инструмент "
               "умеет отказывать — а не то, что он РАЗЛИЧАЕТ", differ=True)

    # ⑨ СЕКЦИЯ БЕЗ РАЗМЕТКИ. Замер по живой базе: у 16 секций из 63 заголовков «## » нет
    #    вовсе. Отчёт «по блокам» молчал бы на четверти контура, и молчание читалось бы
    #    как «ничего не исчезло».
    # ⚠️ ПЕСОЧНИЦА ЗАДАЧИ G8 #616: якорь «исчезло дословно» сменился на «содержательных
    # строк было» — save-phoenix.py теперь делит исчезнувшие строки на «изменена»/
    # «пропала» (карточка #616 ②) и общий счётчик «исчезло дословно N (P%)» ушёл из
    # печати. Предмет проверки не изменился: она подтверждает, что построчный разбор
    # ПО-ПРЕЖНЕМУ работает, когда признак блоков бессилен — «содержательных строк было»
    # печатается на КАЖДОМ прогоне loss_report(), молчания тут как не было, так и нет.
    FLAT = "\n".join(f"строка номер {i}, достаточно длинная чтобы считаться содержательной"
                        for i in range(60))
    p = os.path.join(tmp, "i.db")
    build(p, [("RCC", "state", FLAT)])
    out, code = save(p, "state", FLAT[:int(len(FLAT) * 0.35)])
    admitted = "НИЧЕГО НЕ ЛОВИТ" in out or "разметки нет" in out
    ok &= case("⑨ секция БЕЗ разметки — отчёт НЕ молчит и признаётся, что признак бессилен",
               code != 0 and admitted and "содержательных строк было" in out,
               f"код {code} · {'признался' if admitted else 'СКАЗАЛ «блоки целы» — успокаивающая ложь'}"
               " · «нечем сравнить» и «всё цело» не имеют права выглядеть одинаково",
               differ=True)

    # ⑩ ПРЕЖНЕЕ ТЕЛО В ИСТОРИИ — дословно, а не «примерно столько же знаков».
    p = os.path.join(tmp, "j.db")
    build(p, [("RCC", "state", BIG)])
    out, code = save(p, "state", BIG + "\n## Раздел 20\nдописанное")
    in_history = [v for v in versions(p) if v[3] == BIG]
    ok &= case("⑩ прежнее тело легло в историю ДОСЛОВНО",
               code == 0 and bool(in_history),
               f"версий {len(versions(p))} · прежнее тело "
               f"{'найдено дословно' if in_history else 'НЕ НАЙДЕНО'} · возврат обязан быть "
               "копированием: сборка по частям добавляет шаг, на котором «не смог собрать» "
               "превращается в «данных нет»", differ=True)

    # ⑪ ВОЗВРАТ ИЗ ИСТОРИИ — побайтно, прежние версии целы, возврат ложится НОВОЙ версией.
    p = os.path.join(tmp, "k.db")
    build(p, [("RCC", "state", BIG)])
    save(p, "state", BIG[:int(len(BIG) * 0.82)])
    versions_before = len(versions(p))
    target_id = versions(p)[0][0]
    r = subprocess.run([sys.executable, SAVE, "--db", p, "--role", "RCC", "--section", "state",
                        "--restore", str(target_id)], capture_output=True, text=True,
                       encoding="utf-8")
    restored = body_of(p, "state") == BIG
    versions_after = len(versions(p))
    ok &= case("⑪ возврат из истории — тело ПОБАЙТНО, прежние версии целы, лёг новой версией",
               r.returncode == 0 and restored and versions_after == versions_before + 1,
               f"код {r.returncode} · тело {'побайтно' if restored else 'РАЗОШЛОСЬ'} · "
               f"версий {versions_before} → {versions_after} · откат отката тоже возможен",
               differ=True)

    # ⑫ ЧИСТКА: последние десять ПЛЮС самая длинная. Окно по свежести прогорает —
    #    замер даёт до 15 сохранений одной секции в сутки.
    p = os.path.join(tmp, "l.db")
    build(p, [("RCC", "state", BIG)])
    mid_text = BIG[:int(len(BIG) * 0.72)]
    codes = []
    for i in range(14):
        _, c = save(p, "state", mid_text + f"\nправка {i}")
        codes.append(c)
    saved_versions = versions(p)
    long_intact = any(v[1] == len(BIG) for v in saved_versions)
    ok &= case("⑫ чистка: осталось 10 свежих ПЛЮС самая длинная",
               set(codes) == {0} and len(saved_versions) == 11 and long_intact,
               f"версий {len(saved_versions)} · самая длинная "
               f"{'сбережена' if long_intact else 'ПОТЕРЯНА'} · по свежести она вылетела бы",
               differ=True)

    # ⑬ БАЗА БЕЗ ТАБЛИЦЫ ИСТОРИИ — сохранение НЕ запрещается, но отсутствие говорится
    #    вслух И ложится в журнал. Один шаг схемы не вправе обездвижить память всех ролей;
    #    тихая деградация была бы худшим исходом.
    p = os.path.join(tmp, "m.db")
    build(p, [("RCC", "state", LONG)], with_history=False)
    out, code = save(p, "state", LONG + " дополнение")
    con = sqlite3.connect(p)
    mark = con.execute("SELECT diff_md FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
    con.close()
    in_journal = bool(mark) and "БЕЗ ИСТОРИИ" in (mark[0] or "")
    ok &= case("⑬ база БЕЗ таблицы истории — проходит, но предупреждает И метит журнал",
               code == 0 and "ИСТОРИИ НЕТ" in out and in_journal,
               f"код {code} · пометка в журнале {'есть' if in_journal else 'ОТСУТСТВУЕТ'} · "
               "иначе потеря снова стала бы необратимой, и никто бы не узнал", differ=True)

    # ⑭⑮ ВТОРОЙ ПУТЬ ВЫЗОВА. Находка @OPSSRE (записка #3776): защита срабатывает верно,
    #     а ИСХОД всей операции объявлялся успехом — роль в конце смены видела код 0
    #     и уходила, память при этом не сохранена.
    #     🔴 Новый порог делает отказы частыми (было 0 за 15 дней, стало ~0.9 в сутки) ⇒
    #     редкий невидимый дефект стал бы частым невидимым.
    WM = os.path.join(HERE, "write-message.py")
    if os.path.exists(WM):
        fake_container = os.path.join(tmp, "контур", ".mezosync")
        os.makedirs(os.path.join(fake_container, "scripts"), exist_ok=True)
        import shutil as _sh
        for fname in os.listdir(HERE):
            if fname.endswith(".py"):
                _sh.copy(os.path.join(HERE, fname), os.path.join(fake_container, "scripts", fname))
        pdb = os.path.join(fake_container, "mezosync.db")
        build(pdb, [("RCC", "state", BIG)])
        con = sqlite3.connect(pdb)
        con.execute("""CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY,
                       writer_role TEXT, timestamp TEXT, body_md TEXT, tags TEXT,
                       priority TEXT, resolved INTEGER, broadcast INTEGER, addressed_by TEXT)""")
        con.commit(); con.close()
        file_path = os.path.join(tmp, "урезанное.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(BIG[:int(len(BIG) * 0.39)])
        r = subprocess.run([sys.executable, os.path.join(fake_container, "scripts", "write-message.py"),
                            "--db", pdb, "--role", "RCC", "--body", "проба второго пути",
                            "--save-state", file_path],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        combined_output = (r.stdout or "") + (r.stderr or "")
        ok &= case("⑭ второй путь вызова, отказ памяти — код 4, а не «успех»",
                   r.returncode == 4 and "ПОВТОРЯТЬ НЕ НАДО" in combined_output,
                   f"код {r.returncode} · из «записку откатывать нельзя» не следует "
                   "«операция удалась» · текст запрещает повтор явным словом, иначе "
                   "красное читается как «не ушло» и рождается дубль", differ=True)

        file_path2 = os.path.join(tmp, "законное.md")
        with open(file_path2, "w", encoding="utf-8") as f:
            f.write(BIG + "\n## Раздел 20\nдописанное")
        r2 = subprocess.run([sys.executable, os.path.join(fake_container, "scripts", "write-message.py"),
                             "--db", pdb, "--role", "RCC", "--body", "проба законного",
                             "--save-state", file_path2],
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
    broken_dir = os.path.join(tmp, "порог-ослаблен")
    os.makedirs(broken_dir, exist_ok=True)
    source_text = open(SAVE, encoding="utf-8").read()
    weakened = source_text.replace("SHRINK_HARD = 0.40", "SHRINK_HARD = 0.99", 1)
    if weakened == source_text:
        ok &= case("⑯ ОБРАТНЫЙ ХОД: порог ослаблен — инцидент ПРОСКАКИВАЕТ", False,
                   "⛔ НЕ ЗАПУСТИЛСЯ: строки порога в инструменте нет — он менялся, "
                   "правь приёмку. Зелёный без опыта здесь недопустим")
    else:
        broken_path = os.path.join(broken_dir, "save-phoenix.py")
        with open(broken_path, "w", encoding="utf-8") as f:
            f.write(weakened)
        import shutil as _sh2
        for neighbor in ("mezo_paths.py", "dryrun.py"):
            neighbor_src = os.path.join(HERE, neighbor)
            if os.path.exists(neighbor_src):
                _sh2.copy(neighbor_src, os.path.join(broken_dir, neighbor))
        p = os.path.join(tmp, "n.db")
        build(p, [("RCC", "state", BIG)])
        r = subprocess.run([sys.executable, broken_path, "--db", p, "--role", "RCC",
                            "--section", "state", "--body", BIG[:int(len(BIG) * 0.39)]],
                           capture_output=True, text=True, encoding="utf-8")
        ok &= case("⑯ ОБРАТНЫЙ ХОД: порог ослаблен — инцидент ПРОСКАКИВАЕТ",
                   r.returncode == 0,
                   f"код ослабленного {r.returncode} против отказа у настоящего — "
                   "разница и есть доказательство, что ловит именно порог", differ=True)

    # ⑰ ОБРАТНЫЙ ХОД ПО ЧИСТКЕ. Меняем «самая длинная» на «самая короткая» — длинная
    #    обязана потеряться. Поломка СИНТАКСИЧЕСКИ ВЕРНА: сломать сам запрос значило бы
    #    испытывать падение, а не предмет (моя же ошибка при первом прогоне поломок).
    broken_cleanup_dir = os.path.join(tmp, "чистка-сломана")
    os.makedirs(broken_cleanup_dir, exist_ok=True)
    corruption = source_text.replace("ORDER BY body_chars DESC, id DESC LIMIT 1",
                             "ORDER BY body_chars ASC, id DESC LIMIT 1", 1)
    if corruption == source_text:
        ok &= case("⑰ ОБРАТНЫЙ ХОД: чистка без «самой длинной» — длинная ТЕРЯЕТСЯ", False,
                   "⛔ НЕ ЗАПУСТИЛСЯ: места чистки в инструменте нет — правь приёмку")
    else:
        corruption_path = os.path.join(broken_cleanup_dir, "save-phoenix.py")
        with open(corruption_path, "w", encoding="utf-8") as f:
            f.write(corruption)
        import shutil as _sh3
        for neighbor in ("mezo_paths.py", "dryrun.py"):
            neighbor_src = os.path.join(HERE, neighbor)
            if os.path.exists(neighbor_src):
                _sh3.copy(neighbor_src, os.path.join(broken_cleanup_dir, neighbor))
        p = os.path.join(tmp, "o.db")
        build(p, [("RCC", "state", BIG)])
        codes2 = []
        for i in range(13):
            r = subprocess.run([sys.executable, corruption_path, "--db", p, "--role", "RCC",
                                "--section", "state", "--body", mid_text + f"\nправка {i}"],
                               capture_output=True, text=True, encoding="utf-8")
            codes2.append(r.returncode)
        remaining = versions(p)
        long_intact2 = any(v[1] == len(BIG) for v in remaining)
        ok &= case("⑰ ОБРАТНЫЙ ХОД: чистка без «самой длинной» — длинная ТЕРЯЕТСЯ",
                   set(codes2) == {0} and not long_intact2,
                   f"записи прошли: {set(codes2) == {0}} · длинная "
                   f"{'ЦЕЛА — поломка не сработала' if long_intact2 else 'потеряна'} · "
                   "поломка обязана быть синтаксически верной, иначе испытывается падение",
                   differ=True)

    print()
    print(f"✅ ЗАЩИТА ПРИНЯТА — случаев {CASES}, различающих {DIFFERENTIATING}, "
          "у каждого различающего контроль" if ok
          else "🔴 ЗАЩИТА НЕ ПРИНЯТА")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
