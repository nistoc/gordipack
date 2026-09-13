#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure-old-words — сколько прежних слов осталось: в памятях ролей и в пояснениях.

    python <КОНТУР>/vnext-tools/measure-old-words.py           # обе половины
    python <КОНТУР>/vnext-tools/measure-old-words.py --memories  # только памяти
    python <КОНТУР>/vnext-tools/measure-old-words.py --short     # одна строка (для проверок)
    python <КОНТУР>/vnext-tools/measure-old-words.py --unreviewed  # неразобранные места пояснений

ЗАЧЕМ ИНСТРУМЕНТ, А НЕ РАЗОВЫЙ ЗАПРОС: 17–18.08 вывод инструментов переведён на
общепонятные слова (правило `plain-words`). Проверки, ищущие протухшие утверждения,
знают ОБА написания — прежнее и новое; прежнее снимется, когда в памятях его не останется.
Условие снятия названо ЧИСЛОМ, значит число надо уметь получить одной командой, а не
вспоминать «а сколько там было». Замер, который надо помнить, не проводят.

⚖️ ГРАНИЦА: инструмент СЧИТАЕТ, а не судит. Прежнее слово в памяти — не долг сам по себе:
в уроке или надгробии оно уместно («раньше это звалось сторожем»). Красным здесь не светит
ничего; решение о снятии прежних написаний принимает человек, глядя на разбор поимённо.

📋 СПИСОК РАЗОБРАННЫХ МЕСТ (`old-words-kept.txt`, рядом с этим файлом): пояснения делятся
не на один счёт, а на два — «не разобрано» (никто ещё не посмотрел) и «разобрано и
оставлено» (посмотрели и решили, что слово тут законно — цитата, урок, надгробие). Список
дописывает хозяин каталога, где стоит файл; карточка #238, запись COORD 2026-09-13 19:52 UTC.
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import pathlib
import re
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

WORDS = {
    # 🪤 ГРАНИЦА СЛОВА, А НЕ ПОДСТРОКА. Найдено @COORD 18.08 (записка #3635) на своей же
    # памяти: образец ловил «оСТОРОЖности» — обычное русское слово, к жаргону отношения
    # не имеющее. Замер, считающий верный текст долгом, толкает калечить верный текст.
    "сторож": r"(?<![а-яёa-z])сторож\w*",
    "решето": r"решет[оаеу]\w*",
    "градусник": r"градусник\w*",
    "рубеж": r"рубеж\w*",
    "витрина": r"витрин\w*",
    "слепок": r"слеп(?:ок|ка|ки|ке|ком|ков|кам|ках)\w*",
    "курсор": r"курсор\w*",
    "мутант": r"мутант\w*",
    # 🪤 ГЛАГОЛ — НЕ ТЕРМИН (карточка #265 ③). Термин механизма — существительное
    # («приёмка», прежде «укус»); «предел укусил меня» (@COORD) и «меня укусило дважды»
    # (@OPSSRE) — обычная русская речь о полученном уроне, замер считал её жаргоном.
    # Именные окончания перечислены, глагольные формы (укусил/укусило/укусит…) не ловятся.
    "укус": r"(?<![а-яёa-z])укус(?:а|у|ом|е|ы|ов|ам|ами|ах)?(?![а-яёa-z])",
    "прибор": r"прибор\w*",
    "врезка": r"врезк\w*",
    # Слово владельца 2026-08-20 05:34 UTC: добавить «ведро». В наших записках оно означало
    # группу, куда что-то относят («попали в ведро», «запихнёт в неверное ведро»). Норма —
    # группа · разряд · набор. ⚖️ Считаем ТОЛЬКО в переносном смысле: ведро как настоящая
    # ёмкость — обычное русское слово, и запрет на него калечил бы верный текст.
    # Слово владельца 2026-08-20 06:38 UTC: «гейт» и придуманные соседним контуром «ворота» —
    # оба про полный прогон проверок. Замер 19.08: в живых правилах 20 мест в шести правилах,
    # в памяти ролей 51 у пяти. Слово живёт не там, где на него смотрели, а в приказных текстах.
    "гейт": r"гейт\w*",
    "ворота": r"ворот[аыу]\w*",
    "ведро (о группе)": r"(?:в|из)\s+(?:это|то|прочe|друго|невернo|нужнo)?\w*\s*ведр[оеау]\w*|"
                        r"ведр[оеау]\w*(?=[^\n]{0,40}(?:групп|разряд|набор|относ|попад))",
    # 🪤 ДВА СЛОВА СЧИТАЮТСЯ ТОЛЬКО РЯДОМ С ПРИЗНАКОМ ИНСТРУМЕНТА. Найдено @TAXO 18.08
    # (записка #3610) при разборе её же памяти: замер считал прежним словом МЕТАФОРУ
    # («строка запрёт преемницу перед дверью, которую никто не толкал») и ПРЕДМЕТНЫЙ
    # ТЕРМИН БАЗЫ («ревизия арендатора» — это tenant, так говорит вся схема ядра).
    # ⚖️ Признак, ловящий образ речи, заставляет калечить верный текст ради нуля — а
    # «не подгоняй текст под проверку» контур держит принципиально. ⇒ сузили.
    "аренда (инструмента)": r"аренд\w*(?=[^\n]{0,40}(?:\.py|инструмент|объявлен))|"
                            r"(?:\.py|инструмент|объявлен)[^\n]{0,40}аренд\w*",
    "дверь (инструмента)": r"двер[ьи]\w*(?=[^\n]{0,40}(?:\.py|инструмент|запуск))|"
                           r"(?:\.py|инструмент|запуск)[^\n]{0,40}двер[ьи]\w*",
}
# 🪤 СЛОВО С ДВУМЯ ХОЗЯЕВАМИ. Найдено @RCC 18.08 (#3605), решено словом владельца 13:56 UTC:
# «витрина» в механизме со-работы запрещена, а в области хранилища данных это обычный термин
# («витрина данных», слой хранилища). Считать её там прежним словом значит требовать калечить
# верный предметный текст ради нуля в замере — а подгонять текст под проверку контур не даёт.
DOMAIN_OK = {
    # ⚡ 26.08 (#265 ②): признак расширен ЗАМЕРОМ по живой памяти @RCC — «слои BQ+Falcon,
    # витрины/метрики» и «на витрине в миллион … .table_samples» не отпускались: признак
    # знал «BigQuery», а в тексте «BQ»; знал «таблиц», а в тексте латиница table_samples.
    "витрина": re.compile(r"данн|DWH|BigQuery|BQ|Falcon|SQL|хранилищ|таблиц|table_sample"
                          r"|lineage|метрик|млн|витрин\w*\s+данн", re.I),
    # ⚡ 26.08 (#265 ①): «мутант» у @CHROME — предметный термин mutation testing
    # («Выживший мутант ценнее убитого»), не жаргон механизма. Отпускается рядом
    # с языком этой области; жаргонное «мутант приёмки/гарда» признака не несёт.
    "мутант": re.compile(r"mutation|мутацион|выжив|убит|Stryker", re.I),
}
ANY = re.compile("|".join(WORDS.values()), re.I)


def count(name: str, pat: str, text: str) -> int:
    """Сколько раз слово встретилось ПРЕЖНИМ, а не в законном предметном смысле."""
    near = DOMAIN_OK.get(name)
    n = 0
    for m in re.finditer(pat, text or "", re.I):
        if near and near.search(text[max(0, m.start() - 60):m.end() + 60]):
            continue          # рядом стоит признак предметной области — слово законно
        n += 1
    return n


def in_memories(db) -> tuple[int, dict[str, int], dict[str, collections.Counter]]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    alive = {r[0].upper() for r in con.execute("SELECT role FROM roles WHERE lifecycle='alive'")}
    per_role: dict[str, int] = collections.Counter()
    detail: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for role, body in con.execute("SELECT role, body FROM phoenix"):
        if role.upper() not in alive:
            continue
        for name, pat in WORDS.items():
            n = count(name, pat, body or "")
            if n:
                per_role[role] += n
                detail[role][name] += n
    con.close()
    return sum(per_role.values()), dict(per_role), detail


# ────────────────────────────── список разобранных мест ──────────────────────────────
# `old-words-kept.txt` делит пояснения на «никто ещё не смотрел» и «посмотрели и оставили».
# Формат строки: `файл · «фраза» · причина`. Разбор ниже намеренно НЕ роняет инструмент на
# кривой строке — считает её отдельно и называет в выводе, а не молчит и не падает.

@dataclasses.dataclass
class KeptRecord:
    file: str
    phrase: str
    reason: str
    lineno: int
    raw: str
    matched: bool = False   # выставляется True, как только запись покрыла хоть одно слово


@dataclasses.dataclass
class DirStats:
    label: str
    total: int = 0
    unreviewed: int = 0
    kept: int = 0


@dataclasses.dataclass
class CommentsReport:
    total: int
    unreviewed: int
    kept: int
    per_dir: dict[str, DirStats]
    kept_path: pathlib.Path
    kept_exists: bool
    kept_records_count: int
    stale_records: list[KeptRecord]
    corrupted_lines: list[tuple[int, str]]
    unreviewed_items: list["UnreviewedItem"]


@dataclasses.dataclass
class UnreviewedItem:
    file: str
    lineno: int
    label: str
    line: str
    start: int
    end: int


def parse_kept_list(path: pathlib.Path) -> tuple[list[KeptRecord], list[tuple[int, str]]]:
    """Разбор списка: `#` и пустые строки пропускаются; строка режется по " · " —
    первое поле файл, последнее причина, середина (склеенная обратно тем же " · ") — фраза.
    Фраза обязана начинаться с « и кончаться » (внутри бывают свои « и »); снимается ровно
    по одному знаку с каждого края. Кривая строка не роняет разбор — попадает в отдельный
    список и называется в выводе, а не молчит."""
    records: list[KeptRecord] = []
    corrupted: list[tuple[int, str]] = []
    if not path.exists():
        return records, corrupted
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(" · ")
        if len(parts) < 3:
            corrupted.append((lineno, raw))
            continue
        file_name = parts[0].strip()
        reason = parts[-1].strip()
        phrase_field = " · ".join(parts[1:-1]).strip()
        if not (len(phrase_field) >= 2 and phrase_field.startswith("«")
                and phrase_field.endswith("»")):
            corrupted.append((lineno, raw))
            continue
        phrase = phrase_field[1:-1]   # снять ровно по одному знаку с каждого края
        if not file_name or not phrase or not reason:
            corrupted.append((lineno, raw))
            continue
        records.append(KeptRecord(file=file_name, phrase=phrase, reason=reason,
                                   lineno=lineno, raw=raw))
    return records, corrupted


def phrase_covers(phrase: str, line: str, start: int, end: int) -> bool:
    """Покрывает ли ХОТЬ ОДНО вхождение фразы в строке найденное слово [start:end).

    Ищет фразу в ПОЛНОЙ строке (не в обрезанном по колонке куске) и проверяет ВСЕ её
    вхождения: начало слова обязано быть не левее начала фразы, конец — не правее конца.
    """
    if not phrase:
        return False
    search_from = 0
    while True:
        idx = line.find(phrase, search_from)
        if idx == -1:
            return False
        p_end = idx + len(phrase)
        if start >= idx and end <= p_end:
            return True
        search_from = idx + 1


def default_roots():
    """Два каталога по умолчанию. `.mezosync/scripts` разложен на верхний каталог и
    подкаталоги (`migrations/` и прочие) — их считают порознь, потому что сверяют их порознь.
    Для vnext-tools разбивки нет — там подкаталогов с инструментами не заведено."""
    here = pathlib.Path(__file__).resolve().parent
    return [
        (mezo_paths.live_scripts(),
         "инструменты контура (.mezosync/scripts, верхний каталог)",
         "инструменты контура (.mezosync/scripts, подкаталоги)"),
        (here, "инструменты v-next (vnext-tools)", None),
    ]


def _normalize_root(r):
    if len(r) == 2:
        path, label = r
        return path, label, None
    return r


def context_snippet(line: str, start: int, end: int, width: int = 60) -> str:
    """≈`width` знаков вокруг найденного слова, с многоточием у обрезанных краёв."""
    pad = max(0, (width - (end - start)) // 2)
    left = max(0, start - pad)
    right = min(len(line), end + pad)
    snippet = line[left:right]
    if left > 0:
        snippet = "…" + snippet
    if right < len(line):
        snippet = snippet + "…"
    return snippet


def in_comments(roots=None, kept_path: pathlib.Path | None = None) -> CommentsReport:
    """Прежние слова в пояснениях — по каталогам и по разбору: не разобрано / разобрано
    и оставлено. `roots` и `kept_path` — только для приёмки (свои каталоги и свой список);
    по умолчанию — живые каталоги контура и `old-words-kept.txt` рядом с этим файлом."""
    spec_path = pathlib.Path(__file__).resolve().parent / "plain-words-comments.py"
    import importlib.util
    sp = importlib.util.spec_from_file_location("pwc", spec_path)
    pwc = importlib.util.module_from_spec(sp)
    argv, sys.argv = sys.argv, ["measure"]
    sp.loader.exec_module(pwc)
    sys.argv = argv

    if kept_path is None:
        kept_path = pathlib.Path(__file__).resolve().parent / "old-words-kept.txt"
    kept_path = pathlib.Path(kept_path)
    kept_exists = kept_path.exists()
    records, corrupted = parse_kept_list(kept_path)
    by_file: dict[str, list[KeptRecord]] = collections.defaultdict(list)
    for rec in records:
        by_file[rec.file].append(rec)

    root_specs = [_normalize_root(r) for r in (roots if roots is not None else default_roots())]
    per_dir: dict[str, DirStats] = {}
    unreviewed_items: list[UnreviewedItem] = []

    for root, top_label, sub_label in root_specs:
        root_path = pathlib.Path(root).resolve()
        per_dir.setdefault(top_label, DirStats(label=top_label))
        if sub_label is not None:
            per_dir.setdefault(sub_label, DirStats(label=sub_label))
        for p in root_path.rglob("*.py"):
            label = top_label
            if sub_label is not None and p.resolve().parent != root_path:
                label = sub_label
            stats = per_dir[label]
            src = p.read_text(encoding="utf-8", errors="replace")
            spans = pwc.editable_spans(src)
            lines = src.splitlines()
            file_records = by_file.get(p.name, [])
            for i, line in enumerate(lines, 1):
                if i not in spans:
                    continue
                col = spans[i]
                sub = line[col:]
                for m in ANY.finditer(sub):
                    abs_start = col + m.start()
                    abs_end = col + m.end()
                    stats.total += 1
                    covered = False
                    for rec in file_records:
                        if phrase_covers(rec.phrase, line, abs_start, abs_end):
                            covered = True
                            rec.matched = True
                    if covered:
                        stats.kept += 1
                    else:
                        stats.unreviewed += 1
                        unreviewed_items.append(
                            UnreviewedItem(file=p.name, lineno=i, label=label, line=line,
                                           start=abs_start, end=abs_end))

    total = sum(s.total for s in per_dir.values())
    unreviewed = sum(s.unreviewed for s in per_dir.values())
    kept = sum(s.kept for s in per_dir.values())
    stale = [r for r in records if not r.matched]

    return CommentsReport(
        total=total, unreviewed=unreviewed, kept=kept, per_dir=per_dir,
        kept_path=kept_path, kept_exists=kept_exists, kept_records_count=len(records),
        stale_records=stale, corrupted_lines=corrupted, unreviewed_items=unreviewed_items,
    )


def render_comments_report(report: CommentsReport) -> list[str]:
    """Строки полного вывода раздела ПОЯСНЕНИЯ — отдельно от print(), чтобы приёмка
    могла сверить текст напрямую, не разбирая stdout подпроцесса."""
    out = [f"📊 ПОЯСНЕНИЯ ИНСТРУМЕНТОВ: прежних слов {report.total} — "
           f"не разобрано {report.unreviewed} · разобрано и оставлено {report.kept}"]
    for label, stats in sorted(report.per_dir.items(), key=lambda x: -x[1].total):
        out.append(f"   {stats.total:4}  {label} — не разобрано {stats.unreviewed} · "
                   f"разобрано и оставлено {stats.kept}")
    out.append("   ⚖️ Это места, которые машина отложила как рискованные (согласование) либо")
    out.append("      многозначные. Их правит ВЛАДЕЛЕЦ КАТАЛОГА, а не роль-читатель.")

    if not report.kept_exists:
        out.append(f"📋 СПИСОК РАЗОБРАННЫХ МЕСТ: файла нет ({report.kept_path}) — "
                   f"все {report.total} считаются неразобранными")
        return out

    out.append(f"📋 СПИСОК РАЗОБРАННЫХ МЕСТ: {report.kept_path} · "
               f"записей {report.kept_records_count} · "
               f"не нашли своей строки {len(report.stale_records)}")
    if report.corrupted_lines:
        head = " · ".join(f"строка {ln}" for ln, _ in report.corrupted_lines[:3])
        out.append(f"   ⚠️ строк списка разбор не принял (нет «фразы» между « и »): "
                   f"{len(report.corrupted_lines)} — {head}")
    if report.stale_records:
        out.append("   ⚠️ Запись не нашла своей строки: фразу переписали или файл")
        out.append("      переименовали — запись не засчитана, пересмотрите её:")
        for rec in report.stale_records[:10]:
            out.append(f"      {report.kept_path.name}:{rec.lineno} · {rec.file} · "
                       f"«{rec.phrase[:60]}» · {rec.reason}")
        if len(report.stale_records) > 10:
            out.append(f"      … ещё {len(report.stale_records) - 10}")
    return out


def render_unreviewed(report: CommentsReport) -> list[str]:
    out = [f"📋 НЕ РАЗОБРАНО: мест {report.unreviewed} из {report.total}"]
    for item in report.unreviewed_items:
        out.append(f"   {item.file}:{item.lineno} · "
                   f"{context_snippet(item.line, item.start, item.end)}")
    return out


def yardstick(db) -> str:
    """Чем мерено: версия правила-словаря и число слов в самом признаке.

    🪤 ЗАЯВКА @COORD (записка #3702), поддержанная @CHROME (#3704) своим случаем.
    20.08 его вывод вырос со 131 до 181 за час — и НИ ОДНА роль ничего не ухудшила:
    в 06:39 UTC в словарь добавились «гейт» и «ворота». Число было арифметически верным
    и по существу ложным: читалось как «контур деградировал».
    🎯 Класс: ЧИСЛО БЕЗ СВОЕЙ МЕРКИ ЛЖЁТ, ОСТАВАЯСЬ ПРАВИЛЬНЫМ. Лечится не оговоркой
    в записке (её пишет тот, кто и так помнит), а тем, что мерка печатается САМИМ замером.

    ⚖️ Печатаются ДВЕ величины, а не одна: правило и признак живут порознь, и разойтись
    они могут молча. Версия правила без числа слов признака сказала бы «мерено v4»,
    когда признак ещё не знает новых слов, — то есть соврала бы точнее прежнего.
    """
    version = "?"
    try:
        con = sqlite3.connect(str(db))
        row = con.execute("SELECT version FROM rules WHERE rule_key = 'plain-words'").fetchone()
        con.close()
        if row and row[0] is not None:
            version = f"v{row[0]}"
    except sqlite3.Error:
        version = "правило не прочиталось"
    # ⚡ 26.08 (#265): отпечаток СОДЕРЖИМОГО признака, не только счёт слов. Сужение
    # образца или предметного исключения меняет мерку ПРИ ТОМ ЖЕ числе слов — 172 и 167
    # в тот день были смерены разными мерками и выглядели сравнимыми. Число, у которого
    # мерка сменилась молча, лжёт, оставаясь правильным (класс @COORD #3702, второй заход).
    import hashlib
    fingerprint = hashlib.sha256(
        repr(sorted(WORDS.items()) + sorted((k, v.pattern) for k, v in DOMAIN_OK.items()))
        .encode("utf-8")).hexdigest()[:8]
    return (f"правило plain-words {version} · слов в признаке {len(WORDS)} · "
            f"отпечаток признака {fingerprint}")


def main() -> int:
    ap = argparse.ArgumentParser(description="замер прежних слов: памяти ролей и пояснения")
    ap.add_argument("--db", default=None)
    ap.add_argument("--memories", action="store_true", help="только памяти ролей")
    ap.add_argument("--short", action="store_true", help="одна строка — для встраивания")
    ap.add_argument("--unreviewed", action="store_true",
                    help="печатает неразобранные места пояснений (файл:строка · контекст)")
    a = ap.parse_args()

    if a.unreviewed:
        report = in_comments()
        for line in render_unreviewed(report):
            print(line)
        return 0

    # ⚠️ У копии модуля путей в vnext-tools своя точка входа: live_db() знает живую
    # базу, а resolve_db считает корнем каталог инструмента. Разница поймана прогоном.
    db = a.db or mezo_paths.live_db()

    total_mem, per_role, detail = in_memories(db)
    yardstick_text = yardstick(db)
    if a.short:
        print(f"прежних слов в памятях: {total_mem} у {len(per_role)} ролей, {yardstick_text} "
              f"(цитаты и уроки среди них законны — разбор поимённо)")
        return 0

    print(f"📊 ПАМЯТИ РОЛЕЙ: прежних слов {total_mem} у {len(per_role)} ролей")
    print(f"   📏 МЕРЕНО: {yardstick_text} — два замера РАЗНЫМИ мерками несравнимы")
    for role, n in sorted(per_role.items(), key=lambda x: -x[1]):
        top = " · ".join(f"{w} {c}" for w, c in detail[role].most_common(4))
        print(f"   {role:8} {n:4}   {top}")
    print("   ⚖️ Прежнее слово в памяти — НЕ долг сам по себе: в уроке, надгробии и цитате")
    print("      снятого совета оно уместно и должно остаться. ⇒ УСЛОВИЕ СНЯТИЯ прежних")
    print("      написаний из проверок — не «ноль любой ценой», а ноль ЖИВЫХ приказов")
    print("      старыми словами; это разбирается поимённо, а не счётом (@TAXO #3610).")
    if a.memories:
        return 0

    report = in_comments()
    print()
    for line in render_comments_report(report):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
