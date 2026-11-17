# -*- coding: utf-8 -*-
r"""ПРИЁМКА вопроса о ЧАСЕ ФАЙЛА при сохранении памяти — карточка #763 (заявка STUD).

ПОВОД. У STUD раздел памяти откатился на 29 минут, и инструмент напечатал «OK»
(записка #6358 §③, 2026-11-13 22:02 UTC): сборщик упал, файла не создал, а
сохранение взяло ОДНОИМЁННЫЙ файл ПРОШЛОГО хода. Признака не было никакого;
поймал он это ЧИСЛОМ в том же выводе — «было 19980 → стало 20701».
И второй класс, названный им же: проверка целостности у инструмента ЕСТЬ и
промолчала ПО ПОСТРОЕНИЮ — возврат старого тела выглядит для неё дописыванием,
а не потерей. Она охраняет от ПОТЕРИ и слепа к ВОЗВРАТУ СТАРОГО.

🩸 ПОЧЕМУ ЭТА ПРИЁМКА ОТДЕЛЬНА ОТ СВЕРКИ ВЕРСИИ, ХОТЯ НА ВИД ОНИ ПРО ОДНО.
Я (PROTO) свела два механизма в один ПО РАССУЖДЕНИЮ и записала вывод в критерий
этапа — то есть в то, по чему потом принимают работу. Замер на копии базы
2026-11-15 17:16 UTC опроверг: файл на 29 минут старше раздела, номер версии
ВЕРНЫЙ ⇒ прежний код печатал «OK … было 18657 → стало 18226» и не спрашивал.
    ожидаемая версия ... лжёт БАЗА: чужая запись легла между чтением и записью
    час файла .......... лжёт ФАЙЛ: база в порядке, версия верна, тело старое
Случай ⑨ ниже — доказательство, что механизмы РАЗНЫЕ: поломка часа файла
не задевает сверку версии.

⛔ ЖИВОЙ БАЗЫ НЕ КАСАЕТСЯ. Работает на ПОДСТАВНОЙ базе — схема живого контура
БЕЗ его строк (mezo_stand.empty_db), роль посажена seed_roles. Копия живой базы
здесь не нужна и не берётся: она весит ≈70–96 МБ на стенд, а судить по строкам
ЭТОГО контура значило бы получать у разных контуров разные итоги (урок Э6,
карточка #680). Отпечаток подставной базы сверяется в случае ④.

Какую копию испытываем — тем же рычагом, что у соседних приёмок (карточка #148):
переменная MEZO_SCRIPTS_ROOT (mezo_target.py).

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① файл на 29 минут СТАРШЕ последней записи раздела → ВОПРОС, код 4,
    названы ОБА часа, тело НЕ записано (число знаков не изменилось)   РАЗЛИЧАЮЩИЙ
  ② ВСТРЕЧНЫЙ: файл НОВЕЕ последней записи → вопроса нет, код 0,
    тело записано. Законный порядок «собрал — перечитал — сохранил»
    не сломан                                                        РАЗЛИЧАЮЩИЙ
  ③ СОГЛАСИЕ: тот же старый файл с --allow-older-file → код 0, тело
    записано, и в истории раздела стои́т СЛЕД согласия                РАЗЛИЧАЮЩИЙ
  ④ ХОЛОСТОЙ ПРОГОН: старый файл с --dry-run → тот же вопрос, код 4,
    и отпечаток базы ДО и ПОСЛЕ совпадает знак в знак                РАЗЛИЧАЮЩИЙ
  ⑤ ПРИЗНАК БЕЗ ФАЙЛА: --allow-older-file вместе с --body → отказ
    кодом 1 и причина вслух. Признак, который молча ничего не делает,
    учит роль, что защита работает, — а её там нет вовсе             КОНТРОЛЬ
  ⑥ ПОРОГ: файл старше на ОДНУ секунду (запас на грубость времени
    файловой системы) → вопроса нет. Ложная тревога учит роль
    передавать согласие не думая                                     КОНТРОЛЬ
  ⑦ ОБРАТНЫЙ ХОД, ПРЕДВАРИТЕЛЬНЫЙ: поломанная копия ЗАПУСТИЛАСЬ —
    есть числа, а не падение. 🩸 Урок карточки #784 той же смены: там
    поломанная копия не запустилась вовсе, случай провалился НЕ по
    своей причине, а соседний прошёл спуроно                          КОНТРОЛЬ
  ⑧ ОБРАТНЫЙ ХОД: в копии сверка часа файла выключена → случай ①
    становится кодом 0 и ЗАПИСЫВАЕТ, случай ② не задет. Поломка
    красит РОВНО свой случай                                         РАЗЛИЧАЮЩИЙ
  ⑨ ОБРАТНЫЙ ХОД, ГРАНИЦА: на той же поломанной копии сверка ВЕРСИИ
    по-прежнему ОТКАЗЫВАЕТ (код 1) ⇒ механизмы разные, и выключение
    одного не выключает другой                                       РАЗЛИЧАЮЩИЙ
  ⑩ ЧАС ЗАПИСИ РАЗДЕЛА В БУДУЩЕМ: не вопрос об откате, а сказанное
    вслух расхождение часов, и запись ИДЁТ                           РАЗЛИЧАЮЩИЙ
  ⑪ ТО ЖЕ ТЕЛО ИЗ СТАРОГО ФАЙЛА: вопроса нет — откатывать нечего,
    вызов кончается словами «содержимое не изменилось»                КОНТРОЛЬ

🩸 СЛУЧАИ ⑩ И ⑪ НАШЛА ЧУЖАЯ ПРИЁМКА, А НЕ Я. Первая редакция правки спрашивала
про КАЖДЫЙ свежий файл, если час записи раздела лежал в будущем: соседняя приёмка
bite-phoenix-confirm.py нарочно ставит saved_at на час вперёд (её случай ⑥), и мой
вопрос обрушил её случай ⑨ — «контроль: здоровая пара НЕ красная».
⚡ Класс: мерка «старше, чем X» молчаливо считает X прошлым; когда X приходит ИЗ ДАННЫХ,
он может лежать в будущем — и мерка начинает кричать на всё подряд. Своей рукой я этого
не нашла бы: мой собственный набор случаев строил saved_at только «сейчас».
"""
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand    # noqa: E402
import mezo_target   # noqa: E402

ROLE = "PROTO"
SECTION = "plan"
ANCHOR = ("    if args.file:\n"
          "        verdict = file_time_question(args.file, conn, role, args.section, body)")
BROKEN = ("    if False:\n"
          "        verdict = file_time_question(args.file, conn, role, args.section, body)")

print(f"⚖️ испытуется: {mezo_target.label()}")
tool = mezo_target.script("save-phoenix.py")

failures = []


def check(num, ok, said):
    """Записать исход случая. Печатает ВСЕГДА — и когда прошёл, и когда нет."""
    print(f"{'✅' if ok else '🔴'} {num} {said}")
    if not ok:
        failures.append(f"{num} {said}")
    return ok


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def run(tool_path, db, container, *args):
    """Запуск испытуемого инструмента на стенде. Возвращает (код, весь вывод)."""
    r = subprocess.run([sys.executable, "-X", "utf8", str(tool_path), "--db", str(db),
                        "--role", ROLE, "--section", SECTION, *args],
                       capture_output=True, text=True, encoding="utf-8",
                       env=mezo_stand.stand_env(container, MEZO_ROLE=ROLE,
                                                PYTHONIOENCODING="utf-8"))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def chars(db):
    """Сколько знаков в разделе СЕЙЧАС — и час последней записи."""
    import sqlite3
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        row = conn.execute("SELECT length(body), saved_at FROM phoenix WHERE role=? AND section=?",
                           (ROLE, SECTION)).fetchone()
        return (row[0], row[1]) if row else (None, None)
    finally:
        conn.close()


def history_reasons(db):
    import sqlite3
    conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    try:
        return [r[0] for r in conn.execute(
            "SELECT reason FROM phoenix_history WHERE role=? AND section=? ORDER BY id",
            (ROLE, SECTION)).fetchall()]
    finally:
        conn.close()


def body_of(size, mark):
    """Тело опыта. Ниже SHRINK_FLOOR=400 знаков НАМЕРЕННО: иначе первым заговорил бы
    страж сокращения, и случай ① прошёл бы НЕ ПО СВОЕЙ причине."""
    head = f"# раздел опыта {mark}\n"
    return head + ("строка опыта\n" * max(1, (size - len(head)) // 13))


def older(path, seconds):
    """Отодвинуть время изменения файла назад — так выглядит файл прошлого хода."""
    t = time.time() - seconds
    os.utime(path, (t, t))


stand = mezo_stand.new("bite-file-time")
try:
    container = stand / "contour"
    (container / ".mezosync").mkdir(parents=True)
    db = container / ".mezosync" / "mezosync.db"
    live = mezo_target.scripts_root().parent / "mezosync.db"
    if not live.exists():
        live = Path(os.environ.get("MEZO_LIVE_DB", "")) if os.environ.get("MEZO_LIVE_DB") else live
    if not live.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: схему подставной базы брать неоткуда — нет {live}")
        print("   Это НЕ «сломано» и НЕ «в порядке»: испытывать нечего.")
        sys.exit(mezo_stand.finish(2))
    mezo_stand.empty_db(live, db)
    mezo_stand.seed_roles(db, [ROLE])

    # ── основание: раздел существует, его час записи — «сейчас»
    first = stand / "first.md"
    first.write_text(body_of(260, "основание"), encoding="utf-8")
    code, out = run(tool, db, container, "--file", str(first), "--actor", ROLE)
    if code != 0:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: основание не записалось, код {code}\n{out}")
        sys.exit(mezo_stand.finish(2))
    was, saved_at = chars(db)
    print(f"   основание: раздел {ROLE}/{SECTION} — {was} знаков, записан {saved_at} UTC")

    # ── ① файл на 29 минут СТАРШЕ записи раздела
    stale = stand / "stale.md"
    stale.write_text(body_of(200, "откат"), encoding="utf-8")
    older(stale, 29 * 60)
    code, out = run(tool, db, container, "--file", str(stale), "--actor", ROLE)
    after, _ = chars(db)
    named_both = ("файл изменён" in out) and ("раздел сохранён" in out)
    check("①", code == 4 and named_both and after == was,
          f"старый файл: код {code} (ждали 4) · оба часа названы: {'да' if named_both else 'НЕТ'} "
          f"· знаков было {was} → стало {after} (запись не прошла: {'да' if after == was else 'НЕТ'})")

    # ── ② ВСТРЕЧНЫЙ: файл НОВЕЕ записи
    fresh = stand / "fresh.md"
    fresh.write_text(body_of(300, "свежий"), encoding="utf-8")
    code, out = run(tool, db, container, "--file", str(fresh), "--actor", ROLE)
    after2, _ = chars(db)
    check("②", code == 0 and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" not in out and after2 != was,
          f"свежий файл: код {code} (ждали 0) · вопроса нет: "
          f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' not in out else 'НЕТ'} · знаков было {was} → стало {after2}")

    # ── ③ СОГЛАСИЕ признаком вызова
    stale2 = stand / "stale2.md"
    stale2.write_text(body_of(240, "согласие"), encoding="utf-8")
    older(stale2, 29 * 60)
    code, out = run(tool, db, container, "--file", str(stale2), "--actor", ROLE,
                    "--allow-older-file")
    after3, _ = chars(db)
    trace = any("--allow-older-file" in r for r in history_reasons(db))
    check("③", code == 0 and after3 != after2 and trace,
          f"согласие: код {code} (ждали 0) · знаков было {after2} → стало {after3} "
          f"· след согласия в истории: {'да' if trace else 'НЕТ'}")

    # ── ④ ХОЛОСТОЙ ПРОГОН ведёт себя так же и не пишет
    before_fp = fingerprint(db)
    stale3 = stand / "stale3.md"
    stale3.write_text(body_of(210, "холостой"), encoding="utf-8")
    older(stale3, 29 * 60)
    code, out = run(tool, db, container, "--file", str(stale3), "--actor", ROLE, "--dry-run")
    after_fp = fingerprint(db)
    check("④", code == 4 and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" in out and before_fp == after_fp,
          f"холостой прогон: код {code} (ждали 4) · вопрос напечатан: "
          f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' in out else 'НЕТ'} "
          f"· отпечаток базы {before_fp} → {after_fp}")

    # ── ⑤ ПРИЗНАК БЕЗ ФАЙЛА — молчащего пропуска быть не должно
    code, out = run(tool, db, container, "--body", body_of(250, "без файла"),
                    "--actor", ROLE, "--allow-older-file")
    check("⑤", code == 1 and "файла в этом вызове нет" in out,
          f"признак без файла: код {code} (ждали 1) · причина названа: "
          f"{'да' if 'файла в этом вызове нет' in out else 'НЕТ'}")

    # ── ⑥ ПОРОГ: старше на ОДНУ секунду — вопроса нет
    edge = stand / "edge.md"
    edge.write_text(body_of(320, "порог"), encoding="utf-8")
    older(edge, 1)
    code, out = run(tool, db, container, "--file", str(edge), "--actor", ROLE)
    check("⑥", code == 0 and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" not in out,
          f"старше на секунду: код {code} (ждали 0) · вопроса нет: "
          f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' not in out else 'НЕТ'}")

    # ── ⑩ ЧАС ЗАПИСИ РАЗДЕЛА В БУДУЩЕМ — это НЕ откат (нашла чужая приёмка)
    import sqlite3 as _s
    _c = _s.connect(str(db))
    _c.execute("UPDATE phoenix SET saved_at = datetime('now', '+1 hour') "
               "WHERE role=? AND section=?", (ROLE, SECTION))
    _c.commit()
    _c.close()
    future_was, _ = chars(db)
    future_file = stand / "future.md"
    future_file.write_text(body_of(360, "час в будущем"), encoding="utf-8")
    code, out = run(tool, db, container, "--file", str(future_file), "--actor", ROLE)
    after10, _ = chars(db)
    check("⑩", code == 0 and "в БУДУЩЕМ" in out and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" not in out
          and after10 != future_was,
          f"час записи в будущем: код {code} (ждали 0) · сказано вслух: "
          f"{'да' if 'в БУДУЩЕМ' in out else 'НЕТ'} · вопроса об откате нет: "
          f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' not in out else 'НЕТ'} "
          f"· знаков было {future_was} → стало {after10}")

    # ── ⑪ ТО ЖЕ ТЕЛО ИЗ СТАРОГО ФАЙЛА — откатывать нечего, вопроса нет
    same = stand / "same.md"
    same.write_text(Path(future_file).read_text(encoding="utf-8"), encoding="utf-8")
    older(same, 29 * 60)
    code, out = run(tool, db, container, "--file", str(same), "--actor", ROLE)
    # ⚠️ Слово инструмента здесь ПРОЧИТАНО в его исходнике, а не припомнено: первая
    # редакция ждала «не изменилось» строчными и провалила случай, который по сути прошёл.
    SAME = "СОДЕРЖИМОЕ НЕ ИЗМЕНИЛОСЬ"
    check("⑪", code == 0 and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" not in out and SAME in out,
          f"то же тело из старого файла: код {code} (ждали 0) · вопроса нет: "
          f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' not in out else 'НЕТ'} · сказано «{SAME}»: "
          f"{'да' if SAME in out else 'НЕТ'}")

    # ══ ОБРАТНЫЙ ХОД: приёмка САМА строит поломку рядом с соседями инструмента
    broken_dir = stand / "broken"
    broken_dir.mkdir()
    broken = mezo_stand.copy_tool(tool, broken_dir)
    text = broken.read_text(encoding="utf-8")
    hits = text.count(ANCHOR)
    if hits != 1:
        print(f"🔴 ⑦–⑨ ЯКОРЬ НЕ НАЙДЕН РОВНО ОДИН РАЗ (нашлось {hits}) — поломка не построена.")
        print(f"   якорь: {ANCHOR.strip()}")
        print("   Это НЕ «защита цела»: без поломки обратный ход ничего не доказывает.")
        failures.append("⑦–⑨ якорь поломки не найден ровно один раз")
    else:
        broken.write_text(text.replace(ANCHOR, BROKEN), encoding="utf-8")

        # вторая подставная база: поломку судим НА СВОЕЙ базе, чтобы её записи
        # не путались с числами случаев ①–⑥
        container_b = stand / "contour-broken"
        (container_b / ".mezosync").mkdir(parents=True)
        db_b = container_b / ".mezosync" / "mezosync.db"
        mezo_stand.empty_db(live, db_b)
        mezo_stand.seed_roles(db_b, [ROLE])
        base_b = stand / "base-b.md"
        base_b.write_text(body_of(260, "основание поломки"), encoding="utf-8")
        code, out = run(broken, db_b, container_b, "--file", str(base_b), "--actor", ROLE)
        was_b, _ = chars(db_b)
        # ⑦ поломанная копия ЗАПУСТИЛАСЬ: есть числа, а не падение
        check("⑦", code == 0 and was_b is not None and "OK phoenix/" in out,
              f"поломанная копия запустилась: код {code} (ждали 0) · знаков в разделе {was_b} "
              f"· строка записи есть: {'да' if 'OK phoenix/' in out else 'НЕТ'}")

        # ⑧ случай ① на поломанной копии ЗАПИСЫВАЕТ молча
        stale_b = stand / "stale-b.md"
        stale_b.write_text(body_of(200, "откат на поломке"), encoding="utf-8")
        older(stale_b, 29 * 60)
        code, out = run(broken, db_b, container_b, "--file", str(stale_b), "--actor", ROLE)
        after_b, _ = chars(db_b)
        check("⑧", code == 0 and "ВОПРОС ПЕРЕД ЗАПИСЬЮ" not in out and after_b != was_b,
              f"поломка валит случай ①: код {code} (ждали 0) · вопроса нет: "
              f"{'да' if 'ВОПРОС ПЕРЕД ЗАПИСЬЮ' not in out else 'НЕТ'} "
              f"· знаков было {was_b} → стало {after_b}")

        # ⑧-бис встречный случай ② на поломке НЕ задет
        fresh_b = stand / "fresh-b.md"
        fresh_b.write_text(body_of(330, "свежий на поломке"), encoding="utf-8")
        code, out = run(broken, db_b, container_b, "--file", str(fresh_b), "--actor", ROLE)
        after_b2, _ = chars(db_b)
        check("⑧-бис", code == 0 and after_b2 != after_b,
              f"встречный случай ② поломкой не задет: код {code} (ждали 0) "
              f"· знаков было {after_b} → стало {after_b2}")

        # ⑨ ГРАНИЦА: сверка ВЕРСИИ на той же поломке по-прежнему отказывает
        ver = stand / "ver.md"
        ver.write_text(body_of(340, "версия"), encoding="utf-8")
        code, out = run(broken, db_b, container_b, "--file", str(ver), "--actor", ROLE,
                        "--expect-version", "1")
        refused = code == 1 and "ОТКАЗ" in out
        check("⑨", refused,
              f"сверка версии поломкой часа файла не задета: код {code} (ждали 1) "
              f"· отказ напечатан: {'да' if 'ОТКАЗ' in out else 'НЕТ'}")

    print()
    if failures:
        print(f"🔴 ПРОВАЛИЛОСЬ случаев: {len(failures)}")
        for f in failures:
            print(f"   · {f}")
        sys.exit(mezo_stand.finish(1))
    print("✅ ВСЕ СЛУЧАИ ПРОШЛИ — вопрос о часе файла стои́т, согласие работает, "
          "поломка валит ровно свой случай.")
    print("⛔ Чего приёмка НЕ доказывает: она не судит СОДЕРЖИМОЕ файла (свежий файл "
          "со старым текстом пройдёт молча) и ничего не говорит о пути --body, "
          "где времени изменения не существует вовсе.")
    sys.exit(mezo_stand.finish(0))
finally:
    mezo_stand.release(stand)
