#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""ПРИЁМКА сверки живого с образцом: обезличенное имя репозитория — не расхождение
(карточка #244).

🎯 КЛАСС. Образец обезличивает «<КОНТУР>\<репозиторий>», сверка знала только заглушку
корня — и файл, отличавшийся РОВНО правильным обезличиванием имени репозитория, больше
суток висел «расходится». Постоянный жёлтый, который нельзя погасить работой, учит
пролистывать сверку целиком — и настоящее расхождение в ней потом не заметят.
Вторая половина: «46753б ≠ 46767б» не говорит, правка это или окончания строк; разбор
одного безобидного различия занял 15 минут руками.

Случаи (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① контроль: настоящая правка одной строки → «РАСХОДЯТСЯ»
  ② отличие ТОЛЬКО обезличенным именем репозитория → «обезличено», НЕ расходится   РАЗЛИЧАЮЩИЙ
  ③ ВСТРЕЧНЫЙ к ②: имя, которого НЕТ на диске, → остаётся расходящимся            РАЗЛИЧАЮЩИЙ
  ④ при расхождении названо ЧИСЛО строк по существу, а не только байты             РАЗЛИЧАЮЩИЙ
  ⑤ разные окончания строк при том же тексте → НЕ «расходятся»                     РАЗЛИЧАЮЩИЙ
  ⑥ КАРТОЧКА #625: вставка 1 строки + 2 замены → «по существу: 5», а не число      РАЗЛИЧАЮЩИЙ
    строк сдвинутого хвоста (построчный zip даёт на этом же файле 25 — счёт «по
    ПОЛОЖЕНИЮ» вместо «по СОДЕРЖИМОМУ», см. https://backlog #625)
  ⑥б НАРОЧНАЯ ПОЛОМКА к ⑥: возврат счёта «по положению» роняет РОВНО случай ⑥,      РАЗЛИЧАЮЩИЙ
    остальные (①⑤ считают 0/1/обезличено) позиционного сдвига не видят вовсе
  ⑦ ВОЗВРАТ ПО G7: копия ВНЕ контура (mezo_paths.py рядом, .mezosync/mezosync.db     РАЗЛИЧАЮЩИЙ
    нигде вверх по дереву, MEZO_CONTAINER не задан) — без падения SystemExit'ом
    (карточка #677: зеркало и образец читаются из файла путей, чтение само не падает;
    ловушка SystemExit остаётся как вторая страховка, а поломка ⑦б возвращает ПРЕЖНИЙ
    источник падения — вызов container_root() без указания файла — вместе с узким except)
  ⑧ КАРТОЧКА #639: первая пара сличалась на каталогах СТЕНДА — строки «рантайм:» и    РАЗЛИЧАЮЩИЙ
    «репо   :» сверки называют каталоги внутри стенда, а не контура
  ⑧б НАРОЧНАЯ ПОЛОМКА к ⑧: первая пара не названа (как до карточки #667), копия        РАЗЛИЧАЮЩИЙ
    сверки стоит в контуре-стенде БЕЗ зеркала — роняет РОВНО ⑧: признаки ①–⑤ на том
    же выводе держатся (issue #39 пакета, «а»: без зеркала две другие пары сверяются)
  ⑨ ВСТРЕЧНЫЙ к ⑧ (карточка #639 ②): дерево С зеркалом (непустые совпадающие каталоги)
    и дерево БЕЗ зеркала (каталога зеркала нет) — признаки ①–⑤ те же, ложных провалов нет

═══ КАРТОЧКА #625 (2026-09-14) ═══
guard-scripts-drift.py считал «строк по существу» построчным zip(a, b) — сравнением
ПО ПОЗИЦИИ. Одна вставленная в начало файла строка сдвигает весь хвост, и каждая
следующая строка сравнивается не с той, с которой должна: на живом примере карточки
(bite-addressee-dictionary.py после правки #505) число раздулось до 297 при факте
в 5 строк (1 вставка import + 2 замены). Починка — difflib.SequenceMatcher по
СОДЕРЖИМОМУ (_line_diff_count в guard-scripts-drift.py). Случай ⑥ здесь — на файле,
где позиционный счёт заведомо НЕ может случайно совпасть со счётом по содержимому
(24 «хвостовых» строки после вставки), поэтому расхождение гарантированно видно.

⛔ Живого контура не касается: контейнер, репозитории и обе копии — во временном каталоге
(сверке контейнер называется переменной MEZO_CONTAINER — тем же входом, что у всех путей).

═══ КАРТОЧКА #667: ПЕРВАЯ ПАРА СВЕРКИ — ТОЖЕ СВОЯ ═══
Сверка сперва сличает СВОЮ пару «рабочий каталог ↔ зеркало-репозиторий» и лишь потом —
предмет этой приёмки, пару «vnext-tools ↔ образец» (--vnext-runtime/--vnext-template). Прежде
приёмка первой пары не называла, и сверка брала её из ЖИВОГО контура: свои инструменты и
своё зеркало-репозиторий. У нового контура зеркала нет — сверка честно говорит «зеркало не
заведено» и выходит ДО второй пары; случаи ①–④ ⑤б ⑥ краснели от того, что предмет вовсе не
сличался. На живом контуре та же зависимость подмешивала в вывод чужие строки: «РАСХОДЯТСЯ»
первой пары (живые инструменты против их зеркала) лежал в том же тексте, по которому судят
① ② ⑤. Теперь первая пара — два пустых каталога стенда (mirror_pair: «рантайм и зеркало
совпадают»), и сверка всегда доходит до предмета.

═══ КАРТОЧКА #639: ЧЕМ ДОКАЗАНО, ЧТО ПАРА — СВОЯ ═══
Правка карточки #667 держалась только кодом: ни один случай не смотрел, ОТКУДА сверка взяла
первую пару, и возврат к «пара контура» прошёл бы ①–⑤ на живом Atlas (там зеркало есть).
Случай ⑧ читает это прямо в выводе, поломка ⑧б возвращает прежний вызов на стенде без
зеркала, встречный ⑨ прогоняет предмет на двух деревьях. Признаки ①–⑤ определены одной
функцией (subject_checks): встречный обязан сверять ТЕ ЖЕ признаки, а не свою их копию.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины выводятся, не впечатаны (#153)

import mezo_stand  # временный каталог убирается при успехе, сохраняется при провале

GUARD_TOOL = mezo_paths.live_scripts() / "guard-scripts-drift.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def mirror_pair(stand: pathlib.Path) -> list[str]:
    """Аргументы ПЕРВОЙ пары сверки — два пустых каталога стенда (карточка #667, см. шапку).
    Пустые и потому совпадающие: сверка печатает «совпадает» и идёт дальше, ко второй паре —
    предмету приёмки, — не заглядывая ни в инструменты, ни в зеркало-репозиторий контура."""
    runtime, repo = stand / "mirror-runtime", stand / "mirror-repo"
    runtime.mkdir(exist_ok=True)
    repo.mkdir(exist_ok=True)
    return ["--runtime", str(runtime), "--repo", str(repo)]


def subject_checks(out: str) -> dict:
    """Признаки предмета ①–⑤ — одним местом для основного прогона и встречного ⑨ (карточка
    #639): копия признаков во встречном разошлась бы с основными при первой же правке."""
    return {
        "①": "РАСХОДЯТСЯ" in out and "edited.py" in out,
        "②": "sanitized.py" not in out.split("РАСХОДЯТСЯ")[-1] and "обезличено" in out,
        "③": "ghost.py" in out,
        "④": "строк по существу: 2" in out,
        # Имя целым словом: подстрока «crlf.py» сидит и в «edited-crlf.py» фикстуры ⑤б — после
        # неё признак ⑤ ложно падал бы на любом следующем прогоне (поймано первым прогоном ⑨).
        "⑤": re.search(r"(?<![\w.-])crlf\.py", out.split("РАСХОДЯТСЯ")[-1]) is None,
    }


def first_pair_from_stand(out: str, stand: pathlib.Path) -> bool:
    """Первая пара сличалась на каталогах СТЕНДА (карточка #639): ровно одна строка «рантайм:»
    и одна «репо   :», и обе называют каталог внутри стенда. Пара контура называет его
    каталоги либо печатает «зеркало не объявлено» / «НЕ ЗАВЕДЁН» без этих строк."""
    lines = out.splitlines()
    rt_lines = [s for s in lines if s.startswith("рантайм:")]
    rp_lines = [s for s in lines if s.startswith("репо   :")]
    return (len(rt_lines) == 1 and len(rp_lines) == 1
            and str(stand) in rt_lines[0] and str(stand) in rp_lines[0])


def not_held(checks: dict) -> str:
    """Перечень несработавших признаков словами — для строки случая."""
    bad = [k for k, v in checks.items() if not v]
    return "все держатся" if not bad else "НЕ держатся: " + " ".join(bad)


def main() -> int:
    ok = True
    tmp = mezo_stand.new("bite-drift-sanitize-")
    try:
        container = tmp / "container"
        (container / "alpha-repo" / ".git").mkdir(parents=True)   # репозиторий НА ДИСКЕ
        (container / ".mezosync").mkdir(parents=True)
        rt, tpl = tmp / "rt", tmp / "tpl"
        rt.mkdir(), tpl.mkdir()

        container_str = str(container)

        # ① настоящая правка — обязана остаться расхождением
        (rt / "edited.py").write_text("a = 1\nb = 2\n", encoding="utf-8")
        (tpl / "edited.py").write_text("a = 1\nb = 3\n", encoding="utf-8")
        # ② отличие только обезличенным именем репозитория, ЛЕЖАЩЕГО на диске
        (rt / "sanitized.py").write_text(
            f"# пример: git -C {container_str}\\alpha-repo log\n", encoding="utf-8")
        (tpl / "sanitized.py").write_text(
            "# пример: git -C <КОНТУР>\\<репозиторий> log\n", encoding="utf-8")
        # ③ имя, которого на диске НЕТ, — заглушкой не считается
        (rt / "ghost.py").write_text(
            f"# пример: git -C {container_str}\\beta-repo log\n", encoding="utf-8")
        (tpl / "ghost.py").write_text(
            "# пример: git -C <КОНТУР>\\<репозиторий> log\n", encoding="utf-8")
        # ⑤ тот же текст, другие окончания строк (rt — CRLF-двойник образца, через
        # общий помощник mezo_stand.crlf_twin, карточка #626, а не свой литерал)
        crlf_case_text = "x = 1\ny = 2\n"
        (rt / "crlf.py").write_bytes(mezo_stand.crlf_twin(crlf_case_text).encode("utf-8"))
        (tpl / "crlf.py").write_bytes(crlf_case_text.encode("utf-8"))

        env = dict(os.environ, MEZO_CONTAINER=str(container))
        first_pair = mirror_pair(tmp)
        r = subprocess.run(
            [sys.executable, str(GUARD_TOOL), *first_pair, "--vnext-runtime", str(rt),
             "--vnext-template", str(tpl)],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        chk = subject_checks(out)

        ok &= case("① контроль: настоящая правка — «РАСХОДЯТСЯ», и файл назван",
                   chk["①"],
                   "без него всё дальнейшее могло бы означать ослепшую сверку")
        ok &= case("② обезличенное имя репозитория С ДИСКА — не расхождение",
                   chk["②"],
                   "постоянный жёлтый, который нельзя погасить работой, учит пролистывать "
                   "сверку целиком", differ=True)
        ok &= case("③ ВСТРЕЧНЫЙ: имени нет на диске — файл ОСТАЁТСЯ расходящимся",
                   chk["③"],
                   "иначе заглушка «съедала» бы любое имя, и настоящая правка примера "
                   "прошла бы как обезличивание", differ=True)
        ok &= case("④ при расхождении названо число строк по существу",
                   chk["④"],
                   "«46753б ≠ 46767б» не говорит, правка это или окончания строк; "
                   "различий больше, чем строк в файле, — признак кривой сверки. "
                   "⚠️ КАРТОЧКА #625: число — 2 (удалено 1 + добавлено 1), не 1 — "
                   "критерий карточки считает УДАЛЕНО+ДОБАВЛЕНО, а не число несовпавших "
                   "позиций; тем же основанием на bite-addressee-field.py (без вставки) "
                   "«на деле» было 2, а не 1 (сама карточка #625, живой замер PROTO)",
                   differ=True)
        ok &= case("⑤ разные окончания строк при том же тексте — не «расходятся»",
                   chk["⑤"],
                   "сверка байтов — не сверка содержимого (правило bytes-are-not-content)",
                   differ=True)

        # ⑤б КАРТОЧКА #626: тот же опыт, что ① (настоящая правка), но ОБА файла явно
        # лежат в форме CRLF (mezo_stand.crlf_twin), а не платформенной случайностью
        # write_text — правка обязана остаться «РАСХОДЯТСЯ», даже когда весь мир опыта
        # в форме Windows-чекаута (встречный к ⑤: там CRLF НЕ создаёт расхождения из
        # ничего, здесь CRLF не должен ЗАМАЗЫВАТЬ настоящее расхождение).
        edited_rt_text = "a = 1\nb = 2\n"
        edited_tpl_text = "a = 1\nb = 3\n"
        edited_rt_crlf = mezo_stand.crlf_twin(edited_rt_text).encode("utf-8")
        edited_tpl_crlf = mezo_stand.crlf_twin(edited_tpl_text).encode("utf-8")
        (rt / "edited-crlf.py").write_bytes(edited_rt_crlf)
        (tpl / "edited-crlf.py").write_bytes(edited_tpl_crlf)

        env5b = mezo_stand.stand_env(container)  # карточка #613: среда закреплённого стенда
        r5b = subprocess.run(
            [sys.executable, str(GUARD_TOOL), *first_pair, "--vnext-runtime", str(rt),
             "--vnext-template", str(tpl)],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=env5b)
        out5b = (r5b.stdout or "") + (r5b.stderr or "")
        both_crlf = b"\r\n" in edited_rt_crlf and b"\r\n" in edited_tpl_crlf
        both_named = "РАСХОДЯТСЯ" in out5b and "edited-crlf.py" in out5b
        ok &= case("⑤б тот же опыт: правка остаётся «РАСХОДЯТСЯ», даже когда ОБА файла "
                   "явно в форме CRLF (crlf_twin)",
                   both_crlf and both_named,
                   f"фикстуры явно в форме CRLF: {both_crlf} · вывод несёт «РАСХОДЯТСЯ» "
                   f"и edited-crlf.py: {both_named}",
                   differ=True)

        # ⑧ КАРТОЧКА #639: первая пара — каталоги стенда. Читается по выводу основного прогона.
        own_pair = first_pair_from_stand(out, tmp)
        ok &= case("⑧ карточка #639: первая пара сличалась на каталогах СТЕНДА, не контура",
                   own_pair,
                   "строки «рантайм:» и «репо   :» называют каталоги стенда; иначе сверка взяла "
                   "пару контура — и его зеркало или его отсутствие решают исход ①–⑤",
                   differ=True)

        # ⑧б НАРОЧНАЯ ПОЛОМКА: первая пара не названа — так приёмка звала сверку до карточки
        # #667. Копия сверки стоит в контуре-стенде без зеркала (файла путей нет), то есть её
        # «своя пара» — пара контура без зеркала, условие самой карточки #639.
        # ⑧б и ⑨ идут в среде закреплённого стенда (env5b, карточка #613) — новых вызовов
        # без неё проверка check-acceptance-env.py не получает.
        own_scripts = mezo_stand.copy_tool(GUARD_TOOL, container / ".mezosync" / "scripts")
        r8b = subprocess.run(
            [sys.executable, str(own_scripts), "--vnext-runtime", str(rt),
             "--vnext-template", str(tpl)],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=env5b)
        out8b = (r8b.stdout or "") + (r8b.stderr or "")
        no_mirror_seen = "зеркало не объявлено" in out8b
        dropped = not first_pair_from_stand(out8b, tmp)
        chk8b = subject_checks(out8b)
        ok &= case("⑧б НАРОЧНАЯ ПОЛОМКА (пара контура без зеркала) роняет РОВНО случай ⑧",
                   no_mirror_seen and dropped and all(chk8b.values()),
                   f"стенд без зеркала: {no_mirror_seen} · признак ⑧ пропал: {dropped} · "
                   f"признаки ①–⑤ на том же выводе: {not_held(chk8b)}"
                   + ("" if all(chk8b.values()) else
                      " — без своей пары предмет снова не сличается: issue #39 пакета, «а», "
                      "отменена?"),
                   differ=True)

        # ⑨ ВСТРЕЧНЫЙ (карточка #639 ②): тот же предмет на двух деревьях — С зеркалом
        # (непустые совпадающие каталоги) и БЕЗ зеркала (каталога зеркала нет).
        runtime9, repo9 = tmp / "mirror9-runtime", tmp / "mirror9-repo"
        runtime9.mkdir(), repo9.mkdir()
        (runtime9 / "mirror-tool.py").write_text("x = 1\n", encoding="utf-8")
        (repo9 / "mirror-tool.py").write_text("x = 1\n", encoding="utf-8")
        outs9 = {}
        for tree, repo_arg in (("с зеркалом", repo9), ("без зеркала", tmp / "mirror9-absent")):
            r9 = subprocess.run(
                [sys.executable, str(GUARD_TOOL), "--runtime", str(runtime9),
                 "--repo", str(repo_arg), "--vnext-runtime", str(rt), "--vnext-template", str(tpl)],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env5b)
            outs9[tree] = (r9.stdout or "") + (r9.stderr or "")
        with_ok = ("СОВПАДАЕТ" in outs9["с зеркалом"]
                   and first_pair_from_stand(outs9["с зеркалом"], tmp))
        without_ok = "ЗЕРКАЛО-РЕПОЗИТОРИЙ НЕ ЗАВЕДЁН" in outs9["без зеркала"]
        chk9 = {tree: subject_checks(o) for tree, o in outs9.items()}
        ok &= case("⑨ ВСТРЕЧНЫЙ: дерево с зеркалом и дерево без зеркала — признаки ①–⑤ те же",
                   with_ok and without_ok and all(all(c.values()) for c in chk9.values()),
                   f"с зеркалом: «совпадает» на каталогах стенда {with_ok}, признаки "
                   f"{not_held(chk9['с зеркалом'])} · без зеркала: «не заведён» {without_ok}, "
                   f"признаки {not_held(chk9['без зеркала'])}")
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    # ══ ⑥ КАРТОЧКА #625: «строк по существу» — по СОДЕРЖИМОМУ, не по ПОЗИЦИИ ══════════
    # Отдельный стенд: файл нужен длиннее (позиционный сдвиг обязан быть виден заведомо,
    # а не случайно), и здесь же нарочная поломка — ей нужна СВОЯ копия инструмента.
    tmp6 = mezo_stand.new("bite-drift-sanitize-insert-")
    try:
        container6 = tmp6 / "container"
        (container6 / ".mezosync").mkdir(parents=True)
        rt6, tpl6 = tmp6 / "rt", tmp6 / "tpl"
        rt6.mkdir(), tpl6.mkdir()

        # 24 «хвостовых» строки. Правка: вставка 1 строки в начало + 2 замены —
        # 5 изменений ПО СОДЕРЖИМОМУ. Построчный zip(a, b) после вставки сравнивает
        # КАЖДУЮ из 24 хвостовых строк не с той — даёт как минимум 24: с этим числом
        # 5 не спутать НИ ПРИ КАКОМ содержимом файла, то есть случай различает наверняка.
        base_lines = [f"line_{i} = {i}" for i in range(1, 25)]
        before_lines = list(base_lines)
        after_lines = ["import extra_module"] + base_lines
        after_lines[1 + 4] = "line_5 = 999"     # замена 1
        after_lines[1 + 14] = "line_15 = 888"   # замена 2
        (rt6 / "drifted.py").write_text("\n".join(before_lines) + "\n", encoding="utf-8")
        (tpl6 / "drifted.py").write_text("\n".join(after_lines) + "\n", encoding="utf-8")

        env6 = dict(os.environ, MEZO_CONTAINER=str(container6))
        first_pair6 = mirror_pair(tmp6)
        r6 = subprocess.run(
            [sys.executable, str(GUARD_TOOL), *first_pair6, "--vnext-runtime", str(rt6),
             "--vnext-template", str(tpl6)],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=env6)
        out6 = (r6.stdout or "") + (r6.stderr or "")

        ok &= case("⑥ карточка #625: вставка 1 строки + 2 замены — «по существу: 5»",
                   "строк по существу: 5" in out6 and "drifted.py" in out6,
                   "1 вставка + 2 замены = 5 строк по СОДЕРЖИМОМУ (difflib); построчный "
                   "zip дал бы здесь ≥24 — весь сдвинутый вставкой хвост файла",
                   differ=True)

        # ⑥б НАРОЧНАЯ ПОЛОМКА (счёт по положению) — на КОПИИ копии (mezo_stand.copy_tool
        # копирует инструмент вместе с mezo_paths.py, иначе копия не запустится вовсе).
        # Обязана провалить РОВНО случай ⑥: у ①-⑤ считается 0/1/«обезличено», позиционный
        # сдвиг там взяться неоткуда — не тот текст и не та длина файла.
        broken_copy6 = mezo_stand.copy_tool(GUARD_TOOL, tmp6 / "broken")
        text6 = broken_copy6.read_text(encoding="utf-8")
        anchor = "        changed_lines = _line_diff_count(a_lines, b_lines)"
        anchor_found = anchor in text6
        ok &= case("⑥ якорь поломки найден в живом тексте сверки",
                   anchor_found,
                   "не найден — переименование/рефакторинг увели поломку от настоящего "
                   "места; тогда ⑥б пройдёт без причины — ничего не докажет, не находка)")
        if anchor_found:
            broken_text = text6.replace(
                anchor,
                "        changed_lines = (sum(1 for x, y in zip(a_lines, b_lines) if x != y)"
                " + abs(len(a_lines) - len(b_lines)))",
                1)
            broken_copy6.write_text(broken_text, encoding="utf-8")
            r6b = subprocess.run(
                [sys.executable, str(broken_copy6), *first_pair6, "--vnext-runtime", str(rt6),
                 "--vnext-template", str(tpl6)],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env6)
            out6b = (r6b.stdout or "") + (r6b.stderr or "")
            regressed = "строк по существу: 5" not in out6b
            ok &= case("⑥б НАРОЧНАЯ ПОЛОМКА (счёт по позиции) роняет РОВНО случай ⑥",
                       regressed,
                       "поломка вернула построчный zip — «по существу: 5» обязано пропасть"
                       if regressed else
                       "🔴 поломка НЕ изменила число — случай ⑥ ничего не различает",
                       differ=True)
    finally:
        mezo_stand.release(tmp6)  # уборка отложена до исхода прогона

    # ══ ⑦ ВОЗВРАТ ПО G7: асимметрия try/except у резолва контура ══════════════════════
    # mezo_paths.live_db() (её зовут И _resolve_mirror_repo, И блок VNEXT_TEMPLATE) сама
    # умеет sys.exit()'ом, если контур не найден, — а это SystemExit, не Exception. Копия
    # сверки ВНЕ контура (mezo_stand.copy_tool тащит и mezo_paths.py рядом), без
    # .mezosync/mezosync.db вверх по дереву и без MEZO_CONTAINER, обязана отработать
    # ТИХО (напечатать совет и продолжить), а не падать трассировкой на самом импорте.
    tmp7 = mezo_stand.new("bite-drift-sanitize-outside-")
    try:
        outside = tmp7 / "far" / "away" / "place"
        outside.mkdir(parents=True)
        copy7 = mezo_stand.copy_tool(GUARD_TOOL, outside)
        env7 = {k: v for k, v in os.environ.items() if k != "MEZO_CONTAINER"}
        r7 = subprocess.run([sys.executable, str(copy7), "--help"],
                            capture_output=True, text=True, encoding="utf-8",
                            timeout=300, env=env7)
        out7 = (r7.stdout or "") + (r7.stderr or "")
        ok &= case("⑦ копия ВНЕ контура — без падения SystemExit'ом на резолве",
                   r7.returncode == 0 and "Traceback" not in out7
                   and "ERR: контейнер группы" not in out7,
                   f"код {r7.returncode}; резолв REPO и VNEXT_TEMPLATE обязан ловить "
                   "(SystemExit, Exception), как сосед-блок _own_container — иначе "
                   "падает на первом же импорте, до argparse", differ=True)

        # ⑦б НАРОЧНАЯ ПОЛОМКА: вернуть узкий «except Exception» на ОБОИХ местах —
        # случай ⑦ обязан провалиться (падение возвращается).
        broken_copy7 = mezo_stand.copy_tool(GUARD_TOOL, tmp7 / "broken7")
        text7 = broken_copy7.read_text(encoding="utf-8")
        anchor7a = ("    except (SystemExit, Exception):                    # noqa: BLE001"
                    "\n        path = None")
        anchor7c = ("        path = _MIRROR.path if _MIRROR.outcome == \"declared\" else None")
        anchor7b = ("except (SystemExit, Exception):                        # noqa: BLE001"
                    "\n    VNEXT_TEMPLATE = None")
        anchors7_found = (text7.count(anchor7a) == 1 and text7.count(anchor7b) == 1
                          and text7.count(anchor7c) == 1)
        ok &= case("⑦ якоря поломки (оба места) найдены в живом тексте сверки",
                   anchors7_found,
                   "не найдены — переименование/рефакторинг увели поломку от настоящего "
                   "места; тогда ⑦б пройдёт без причины — ничего не докажет, не находка")
        if anchors7_found:
            # Прежний источник падения возвращён вместе с узким except: чтение ключа само не
            # бросает, и без возвращённого вызова поломка ничего бы не меняла.
            broken_text7 = text7.replace(anchor7c, anchor7c + "\n        _mp.container_root()", 1)
            broken_text7 = broken_text7.replace(
                anchor7a, "    except Exception:                               # noqa: BLE001"
                          "\n        path = None", 1)
            broken_text7 = broken_text7.replace(
                anchor7b, "except Exception:                                      # noqa: BLE001"
                          "\n    VNEXT_TEMPLATE = None", 1)
            broken_copy7.write_text(broken_text7, encoding="utf-8")
            r7b = subprocess.run([sys.executable, str(broken_copy7), "--help"],
                                 capture_output=True, text=True, encoding="utf-8",
                                 timeout=300, env=env7)
            out7b = (r7b.stdout or "") + (r7b.stderr or "")
            regressed7 = r7b.returncode != 0 or "ERR: контейнер группы" in out7b
            ok &= case("⑦б НАРОЧНАЯ ПОЛОМКА (узкий except Exception) роняет РОВНО случай ⑦",
                       regressed7,
                       "поломка вернула падение SystemExit'ом на резолве"
                       if regressed7 else
                       "🔴 поломка НЕ вернула падение — случай ⑦ ничего не различает",
                       differ=True)
    finally:
        mezo_stand.release(tmp7)  # уборка отложена до исхода прогона

    print()
    print(f"{'✅ СВЕРКА С ОБРАЗЦОМ ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, "
          f"различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
