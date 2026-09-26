#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# plain-words: файл ОБСУЖДАЕТ прежние слова — их упоминания здесь ЗАКОННЫ.
# ⚖️ Пометка поставлена @PROTO 2026-09-13 (карточка #238): «сторож» и «прибор» стоят тут
# ПРЕДМЕТОМ проверки — это подопытные слова в строках стенда и в названиях случаев.
# Без них нечего считать «разобранным» и «неразобранным». ⛔ Разрешает упоминание, не жаргон.
"""bite-old-words-kept — приёмка разбора списка «разобрано и оставлено» в measure-old-words.py.

    python <КОНТУР>/vnext-tools/bite-old-words-kept.py

ПРЕДМЕТ: measure-old-words.py больше не считает прежние слова в пояснениях ОДНИМ числом —
он делит их на «не разобрано» (никто не смотрел) и «разобрано и оставлено» (посмотрели и
решили, что слово тут законно) по списку `old-words-kept.txt` (файл · «фраза» · причина).
Эта приёмка проверяет: разбор списка (в т.ч. кривую строку), сверку покрытия найденного
слова фразой (по имени файла И по месту в строке), отсутствующий список, и то, что старая
мерка (--short, отпечаток признака) не сдвинулась.

Стенды — во временных каталогах (tempfile); реальные файлы контура не читаются нигде,
кроме случая ⑧ (живой прогон на настоящих каталогах — он только ЧИТАЕТ). В конце убираются
ТОЛЬКО свои временные каталоги.

Нарочные поломки (а/б/в) применяются К ТЕКСТУ измерителя В ПАМЯТИ (compile+exec с
настоящим __file__) — на диск ничего не пишется.
"""
from __future__ import annotations

import importlib.util
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
MOW_PATH = HERE / "measure-old-words.py"

CASES = DIFFER = 0


def case(title, verdict, detail, differ=True):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def load_mow(patch=None, name="mow_bite_owk"):
    """Гружает measure-old-words.py как модуль. `patch(src) -> (новый_текст, число_замен)`
    правит ИСХОДНИК В ПАМЯТИ (нарочная поломка) — на диск ничего не пишется. __file__
    остаётся настоящим путём, иначе old-words-kept.txt и mezo_paths рядом не найдутся."""
    src = MOW_PATH.read_text(encoding="utf-8")
    if patch is not None:
        new_src, n = patch(src)
        if n != 1:
            raise AssertionError(f"поломка не нашла ровно одну строку-цель (нашла {n}) — "
                                 f"измеритель мог измениться, поломку надо пересмотреть")
        src = new_src
    spec = importlib.util.spec_from_file_location(name, str(MOW_PATH))
    mod = importlib.util.module_from_spec(spec)
    code = compile(src, str(MOW_PATH), "exec")
    # dataclasses с отложенными подсказками типов (список из строкового имени класса)
    # разбираются через sys.modules[cls.__module__] — модуль обязан быть зарегистрирован
    # ДО exec, иначе разбор падает на первом же @dataclasses.dataclass.
    sys.modules[name] = mod
    exec(code, mod.__dict__)
    return mod


def patch_a(src: str):
    """(а) сверка только по имени файла — фраза не нужна: покрытие ставится БЕЗУСЛОВНО,
    как только у файла есть хоть одна запись, без проверки, что фраза покрывает СЛОВО."""
    old = "                        if phrase_covers(rec.phrase, line, abs_start, abs_end):\n"
    new = "                        if True:  # ПОЛОМКА (а): сверка только по имени файла\n"
    return src.replace(old, new), src.count(old)


def patch_b(src: str):
    """(б) протухшая запись засчитывается: итоговое «не разобрано» занижается на число
    записей, которые не покрыли НИ ОДНОГО слова, — как будто они всё-таки что-то разобрали."""
    old = "    unreviewed = sum(s.unreviewed for s in per_dir.values())\n"
    new = ("    unreviewed = sum(s.unreviewed for s in per_dir.values()) - "
           "len([r for r in records if not r.matched])  # ПОЛОМКА (б)\n")
    return src.replace(old, new), src.count(old)


def patch_v(src: str):
    """(в) фраза где угодно в строке — без покрытия слова: как только фраза НАЙДЕНА в
    строке (в любом месте), она засчитывается, хотя бы найденное слово стояло не в ней."""
    old = "        if start >= idx and end <= p_end:\n"
    new = "        if True:  # ПОЛОМКА (в): фраза где угодно в строке, без покрытия слова\n"
    return src.replace(old, new), src.count(old)


def write_file(dir_: pathlib.Path, name: str, text: str) -> pathlib.Path:
    p = dir_ / name
    p.write_text(text, encoding="utf-8")
    return p


def write_kept(dir_: pathlib.Path, name: str, lines: list[str]) -> pathlib.Path:
    return write_file(dir_, name, "\n".join(lines) + "\n")


def build_fixture(tmp: pathlib.Path):
    """Общий стенд для случаев ①–④ и поломок (а/б/в): четыре файла с прежними словами
    и список, разбирающий часть из них. Ни один файл НЕ похож на настоящий контур —
    только слово из WORDS и текст вокруг него, нужный для сверки фразы.

    ⚠️ Стенд — В СВОЁМ подкаталоге, а не прямо в tmp: `roots` сканирует его РЕКУРСИВНО
    (rglob), и любой СОСЕДНИЙ временный стенд (случай ⑥), рождённый ВНУТРИ tmp, попал бы
    в тот же обход и сдвинул бы счёт — поймано прогоном (case4.py читался семью словами
    вместо шести, когда `dir=tmp` у соседнего стенда делало его вложенным подкаталогом)."""
    fixture_dir = tmp / "fixture"
    fixture_dir.mkdir()
    write_file(fixture_dir, "case1.py", '# «редкий сторож у входа» — пример для случая 1\n')
    write_file(fixture_dir, "case2.py",
               '# в этом месте раньше стоял прибор, теперь тут проверка\n')
    write_file(fixture_dir, "case3.py",
               '# «старый сторож стоял тут» — рядом прибор\n')
    write_file(fixture_dir, "case4.py",
               '# «первое место со сторож словом» — тестовая строка A\n'
               'x = 1\n'
               '# здесь тоже есть прибор, но фраза его не описывает\n')
    kept = write_kept(tmp, "kept.txt", [
        "# приёмка bite-old-words-kept.py — тестовый список, реальных файлов не описывает",
        "case1.py · «редкий сторож у входа» · тестовая причина 1",
        "ghost.py · «фраза несуществующего файла» · тестовая причина 2 (протухшая)",
        "case3.py · «старый сторож стоял тут» · тестовая причина 3",
        "case4.py · «первое место со сторож словом» · тестовая причина 4",
    ])
    return fixture_dir, kept


def find_item(report, file_name):
    return [it for it in report.unreviewed_items if it.file == file_name]


def find_stale(report, file_name):
    return [r for r in report.stale_records if r.file == file_name]


def main() -> int:
    ok = True
    if not MOW_PATH.exists():
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: испытуемого нет — {MOW_PATH}")
        return 2

    tmp_root = pathlib.Path(tempfile.mkdtemp(prefix="bite-owk-"))
    try:
        fixture_dir, kept_path = build_fixture(tmp_root)
        mow = load_mow()
        roots = [(fixture_dir, "тест-каталог")]
        report = mow.in_comments(roots=roots, kept_path=kept_path)

        # ① слово, покрытое фразой своей записи, — «разобрано и оставлено»
        c1 = find_item(report, "case1.py")
        ok &= case("① слово, покрытое фразой своей записи, — «разобрано и оставлено»",
                   len(c1) == 0,
                   f"case1.py в списке «не разобрано»: {len(c1)} мест (ждём 0) — фраза "
                   f"записи 1 покрывает найденное «сторож»")

        # ② запись на несуществующий файл — «не нашла своей строки», и это НЕ уменьшает
        #    «не разобрано» у настоящего слова в другом файле
        c2 = find_item(report, "case2.py")
        stale_ghost = find_stale(report, "ghost.py")
        ok &= case("② запись на несуществующий файл — «не нашла своей строки», "
                   "случай case2.py остаётся «не разобрано»",
                   len(c2) == 1 and len(stale_ghost) == 1,
                   f"case2.py «не разобрано»: {len(c2)} (ждём 1 — записи на case2.py вообще "
                   f"нет в списке); протухших записей на ghost.py: {len(stale_ghost)} (ждём 1)")

        # ③ одна строка, два прежних слова, фраза покрывает только «сторож»
        c3 = find_item(report, "case3.py")
        ok &= case("③ в строке два прежних слова, фраза покрывает только «сторож» — "
                   "«прибор» остаётся «не разобрано»",
                   len(c3) == 1 and c3[0].line.find("прибор") == c3[0].start,
                   f"case3.py «не разобрано»: {len(c3)} место(а) (ждём 1 — позицию слова "
                   f"«прибор»); совпадение позиции: "
                   f"{c3[0].line.find('прибор') == c3[0].start if c3 else 'нет данных'}")

        # ④ фраза покрывает СВОЁ место в файле, но не покрывает слово на другой строке
        #    того же файла — запись при этом НЕ протухшая (она что-то покрыла)
        c4 = find_item(report, "case4.py")
        stale_case4 = find_stale(report, "case4.py")
        ok &= case("④ фраза покрывает своё место в файле, но НЕ покрывает слово на другой "
                   "строке того же файла — там остаётся «не разобрано» (ключ — файл И фраза)",
                   len(c4) == 1 and len(stale_case4) == 0,
                   f"case4.py «не разобрано»: {len(c4)} (ждём 1 — «прибор» на 3-й строке); "
                   f"запись case4.py протухшей НЕ считается (покрыла «сторож» на 1-й строке): "
                   f"{len(stale_case4)} протухших (ждём 0)")

        # ⑤ файла списка нет — все места неразобраны, и это сказано вслух
        missing_kept = tmp_root / "нет-такого-списка.txt"
        report5 = mow.in_comments(roots=roots, kept_path=missing_kept)
        text5 = "\n".join(mow.render_comments_report(report5))
        ok &= case("⑤ списка нет — все места неразобраны, и это сказано вслух",
                   (not report5.kept_exists) and report5.unreviewed == report5.total
                   and report5.kept == 0 and "считаются неразобранными" in text5,
                   f"kept_exists={report5.kept_exists}, не разобрано {report5.unreviewed} "
                   f"из {report5.total}, разобрано и оставлено {report5.kept}; фраза "
                   f"«считаются неразобранными» в выводе: "
                   f"{'считаются неразобранными' in text5}")

        # ⑥ испорченная строка списка (нет «фразы» в кавычках) не роняет разбор — названа
        broken_dir = pathlib.Path(tempfile.mkdtemp(prefix="bite-owk-broken-", dir=tmp_root))
        write_file(broken_dir, "onlyword.py", '# тут раньше стоял прибор\n')
        broken_kept = write_kept(broken_dir, "kept.txt", [
            "onlyword.py · «тут раньше стоял прибор» · норм. запись",
            "onlyword.py · это без кавычек вокруг фразы · испорченная строка",
        ])
        report6 = mow.in_comments(roots=[(broken_dir, "тест-каталог-порча")],
                                  kept_path=broken_kept)
        ok &= case("⑥ строка списка без «фразы» в кавычках — названа, разбор не падает",
                   len(report6.corrupted_lines) == 1 and report6.kept_records_count == 1
                   and report6.unreviewed == 0 and report6.kept == 1,
                   f"испорченных строк {len(report6.corrupted_lines)} (ждём 1), валидных "
                   f"записей {report6.kept_records_count} (ждём 1); слово всё равно "
                   f"разобрано: не разобрано {report6.unreviewed} · оставлено {report6.kept}")

        # ⑦ мерка прежняя: отпечаток признака, --short как до правки (кроме живых чисел
        #    памяти ролей — по слову задания сверяем без них)
        # ⚰️ Здесь стоял отпечаток 4409d115. 2026-09-14 карточка #611 дала образцам «гейт»
        #    и «ворота» левую границу (не находить внутри «разворота»/«поворота») — словарь
        #    сменился НАМЕРЕННО, отпечаток перенесён тем же ходом (PROTO). Замер памяти ролей:
        #    165 → 164 прежних слова, разница — «ворота» внутри «разворота» в памяти PROTO.
        MEASURE_FINGERPRINT = "3259d38f"
        MEASURE_WORDS_COUNT = 16
        # ⚡ ПРАВКА (карточка #659, приёмка отстала от продукта — не продукт сломан).
        # Версия правила plain-words — ЖИВОЕ число: растёт при КАЖДОЙ правке ТЕКСТА
        # правила, не только при смене словаря признака (см. докстринг yardstick() в
        # measure-old-words.py, карточка #265 — «версия правила без числа слов признака
        # сказала бы неправду»: версия и отпечаток НАМЕРЕННО разведены и МОГУТ разойтись
        # законно). 24.09.2026 текст правила сократили словом владельца (карточка #652,
        # этап 1 карточки #651; rules/annex/plain-words.md называет час и цитату) — версия
        # ушла v6 → v7, а словарь признака НЕ ТРОНУТ: отпечаток остался 3259d38f, слов
        # в признаке — те же 16. Пришить номер версии литералом — растить приёмку, которая
        # протухает при каждой правке ТЕКСТА правила, даже когда словарь не менялся ни на
        # слово. Сверяем версию НЕ литералом, а СОВПАДЕНИЕМ с тем же измерением yardstick()
        # внутри процесса (та же живая база, что видит --short-подпроцесс) — так случай
        # ловит НАСТОЯЩЕЕ расхождение (CLI разошёлся с библиотечной функцией, тот самый
        # класс «число без своей мерки лжёт»), а не безобидный законный рост номера.
        expected_tail = (f"{mow.yardstick(mow.mezo_paths.live_db())} (цитаты и уроки среди них "
                         "законны — разбор поимённо)")
        r7 = subprocess.run([sys.executable, str(MOW_PATH), "--short"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
        out7 = (r7.stdout or "").strip()
        m7 = re.match(r"^прежних слов в памятях: \d+ у \d+ ролей, (.*)$", out7)
        tail7 = m7.group(1) if m7 else out7
        ok &= case(f"⑦ мерка прежняя (отпечаток {MEASURE_FINGERPRINT}, слов в признаке "
                   f"{MEASURE_WORDS_COUNT}) и --short совпадает с yardstick() библиотеки",
                   r7.returncode == 0 and MEASURE_FINGERPRINT in out7
                   and f"слов в признаке {MEASURE_WORDS_COUNT}" in out7
                   and tail7 == expected_tail,
                   f"код {r7.returncode}; хвост строки без чисел памяти ролей: {tail7!r} "
                   f"(ждём {expected_tail!r})")

        # ⑧ живой прогон: все записи настоящего списка нашли свою строку.
        # 🩸 13.09 первая редакция ждала РОВНО 45 записей — и провалилась, как только хозяин
        #    каталога законно дописал список до 94 (находка COORD, записка #5144): приёмка судила
        #    сегодняшние данные, а не поведение. Число записей берём из самого файла списка.
        real_report = mow.in_comments()
        kept_file = pathlib.Path(mow.__file__).resolve().parent / "old-words-kept.txt"
        listed = sum(1 for raw in (kept_file.read_text(encoding="utf-8").splitlines()
                                   if kept_file.exists() else [])
                     if raw.strip() and not raw.strip().startswith("#"))
        ok &= case("⑧ живой прогон на настоящих каталогах и настоящем списке: все записи "
                   "нашли свою строку",
                   real_report.kept_exists and listed > 0
                   and real_report.kept_records_count == listed
                   and not real_report.corrupted_lines
                   # протухшие О ФАЙЛАХ ЭТОГО КОНТУРА — ноль; записи о файлах, которых здесь нет
                   # вовсе (absent_records ⊂ stale_records), проверить негде — вычитаем
                   and len(real_report.stale_records) - len(getattr(real_report, 'absent_records', [])) == 0
                   # …и покрыть они ничего не могут — из ожидания «оставлено» их тоже вычитаем
                   # (карточка #659, 26.09)
                   and real_report.kept >= real_report.kept_records_count
                   - len(getattr(real_report, 'absent_records', [])),
                   f"строк данных в файле {listed}, разобрано записей {real_report.kept_records_count} "
                   f"(ждём столько же); кривых {len(real_report.corrupted_lines)} (ждём 0); не нашли "
                   f"своей строки {len(real_report.stale_records)}, из них о файлах, которых здесь нет: "
                   f"{len(getattr(real_report, 'absent_records', []))} (ждём разницу 0); разобрано и оставлено "
                   f"{real_report.kept} (ждём не меньше числа записей — каждая покрывает хоть одно слово)")

        # ⑨ ПОЛОМКА (а) обязана покрасить случаи ③ и ④
        mow_a = load_mow(patch=patch_a, name="mow_bite_owk_a")
        report_a = mow_a.in_comments(roots=roots, kept_path=kept_path)
        c3a, c4a = find_item(report_a, "case3.py"), find_item(report_a, "case4.py")
        ok &= case("⑨ ПОЛОМКА (а) «сверка только по имени файла, фраза не нужна» "
                   "красит случаи ③ и ④",
                   len(c3a) == 0 and len(c4a) == 0,
                   f"под поломкой (а): case3.py «не разобрано» {len(c3a)} (было {len(c3)} — "
                   f"«прибор» ушёл в «разобрано» по ошибке), case4.py «не разобрано» "
                   f"{len(c4a)} (было {len(c4)})")

        # ⑩ ПОЛОМКА (б) обязана покрасить случай ②
        mow_b = load_mow(patch=patch_b, name="mow_bite_owk_b")
        report_b = mow_b.in_comments(roots=roots, kept_path=kept_path)
        ok &= case("⑩ ПОЛОМКА (б) «протухшая запись засчитывается» красит случай ②: "
                   "общее «не разобрано» занижено на число протухших",
                   report_b.unreviewed == report.unreviewed - len(report.stale_records)
                   and report_b.unreviewed != report.unreviewed,
                   f"верно «не разобрано» {report.unreviewed}, под поломкой (б) "
                   f"{report_b.unreviewed} — разница {report.unreviewed - report_b.unreviewed} "
                   f"равна числу протухших ({len(report.stale_records)})")

        # ⑪ ПОЛОМКА (в) обязана покрасить случай ③, но НЕ случай ④
        mow_v = load_mow(patch=patch_v, name="mow_bite_owk_v")
        report_v = mow_v.in_comments(roots=roots, kept_path=kept_path)
        c3v, c4v = find_item(report_v, "case3.py"), find_item(report_v, "case4.py")
        ok &= case("⑪ ПОЛОМКА (в) «фраза где угодно в строке, без покрытия слова» "
                   "красит случай ③, но НЕ случай ④ (там фразы нет на самой строке)",
                   len(c3v) == 0 and len(c4v) == 1,
                   f"под поломкой (в): case3.py «не разобрано» {len(c3v)} (было {len(c3)} — "
                   f"ушло в «разобрано» по ошибке), case4.py «не разобрано» {len(c4v)} "
                   f"(осталось {len(c4)}, как и верно — поломка (в) тут не при чём)")
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print()
    print(f"{'✅ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
