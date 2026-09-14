# -*- coding: utf-8 -*-
r"""bite-rules-mirror-search.py — приёмка ПОИСКА файла-зеркала по раскладкам контура (карточка #618).

🩸 ПОВОД. Копия check-rules-mirror.py в scripts искала sync.rules.md только в
`.mezosync/generated` (раскладка новорождённого контура) и отказывала на Atlas, где файл
лежит в `atlas.archs/.mezosync/coordination`; копия в vnext-tools искала только там и
НЕ ОТ `--db`, а от найденного контейнера. Под одним и тем же контуром одна копия отказывала
«сверить нечем», другая молча проходила. Единая редакция ищет ОБЕ раскладки по порядку
(mirror_candidates/find_mirror в check-rules-mirror.py) — эта приёмка испытывает именно поиск,
а не разбор HEAD (тот испытан отдельно, bite-check-rules-mirror.py) и не разбор тела (тот —
в bite-rules-mirror.py).

СЛУЧАИ (различающий = обязан ответить ИНАЧЕ, а не одинаково):
  ① встречный/контроль: правил нет, файла нет НИГДЕ — «сверять нечего», код 0, не поломка
  ② ГЛАВНЫЙ: раскладка Atlas (atlas.archs/.mezosync/coordination/sync.rules.md) — находит, код 0
  ③ ВСТРЕЧНЫЙ к ②: раскладка контура из пакета (.mezosync/generated/sync.rules.md), файла
     Atlas при этом НЕТ ВООБЩЕ — тоже находит, код 0 (доказывает: ищутся ОБЕ раскладки,
     а не только та, что проверена случаем ②)
  ④ файл НЕ НАЙДЕН ни в одном месте, а правила в базе ЕСТЬ — прежний громкий отказ
     «сверить НЕЧЕМ», код 1 (не тихая догадка, не молчание)
  ⑤ ЧУЖАЯ ФОРМА: то же, что ③ (раскладка пакета), но файл-зеркало записан построчно
     Windows-концами (CRLF) — тоже находит и сходится, код 0

НАРОЧНАЯ ПОЛОМКА (--porcha one-place): mirror_candidates() урезан до ОДНОГО места
(только .mezosync/generated — раскладка, которую раньше знала копия в scripts). Ждём:
провалится РОВНО случай ② (раскладка Atlas более не входит в список кандидатов и не
находится); ①③⑤ остаются зелёными — они про место, которое поломка не трогает.
Поломка кладётся на КОПИЮ копии (сама check-rules-mirror.py в песочнице не портится).

⚖️ У СЛУЧАЯ ⑤ НЕТ СВОЕЙ НАРОЧНОЙ ПОЛОМКИ, И ЭТО НАЗВАНО ПРЯМО (возврат PROTO по #618).
Различение CRLF НЕ ДЕРЖИТСЯ ОДНОЙ СТРОКОЙ КОДА — проверено ОПЫТОМ, не рассуждением:
испытаны ДВЕ независимые правки check-rules-mirror.py разом (from_file читает БЕЗ
universal-newlines перевода — `open(..., newline="")` вместо `Path.read_text(...)`;
И norm() перестаёт считать `\r` пробелом — `[ \t\n]+` вместо `\s+`) — случай всё равно
проходил. Причина: `from_file` режет тело `body.rstrip()`/`"\n".join(lines).strip()`
СТАНДАРТНЫМ `str.strip()`, а он по умолчанию считает `\r` пробелом НЕЗАВИСИМО от
паттерна в norm() — третий, независимый слой. Сломать ЭТОТ случай, не сломав ①②③④,
значило бы одновременно отключить universal-newlines НА ЧТЕНИИ, переписать norm() И
подменить `.rstrip()/.strip()` на свою функцию, не считающую `\r` пробелом — то есть
переписать разбор целиком, а не сломать одну строку. Это не «поломка не нашлась»,
это «устойчивость СТРУКТУРНАЯ, а не строчная»: три независимых механизма Python
(universal newlines при чтении, `\s` в регулярке HEAD, `\s`-класс в default strip())
и norm() — совпадают в том, что `\r` для них всегда пробел. Случай ⑤ поэтому идёт БЕЗ
парной поломки и проверяет фактическое поведение (устойчивость), а не разбор строки.

⛔ Живой базы и живого файла не касается: свой временный каталог на каждый случай,
своя временная БД (только колонки rule_key/body/version), свой временный файл-зеркало.
MEZO_CONTAINER указывает на РЕАЛЬНЫЙ контейнер ТОЛЬКО чтобы модуль mezo_paths успел
импортироваться (check-rules-mirror.py резолвит LIVE на верхнем уровне, до argparse) —
--db ниже перебивает дефолт, и поиск файла-зеркала идёт ОТ --db, а не от MEZO_CONTAINER:
это и проверяет случай ③ (пакетная раскладка лежит НЕ под тем контейнером, что в MEZO_CONTAINER).

ЗАПУСК: python bite-rules-mirror-search.py [--porcha one-place]
ВЫХОД:  0 — все случаи · 1 — есть провал
"""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402

CASES = DIFFER = PASSED = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER, PASSED
    CASES += 1
    DIFFER += bool(differ)
    PASSED += bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def build_db(path: Path, rules: dict) -> None:
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE rules (rule_key TEXT, body TEXT, version INTEGER)")
    for key, (body, ver) in rules.items():
        con.execute("INSERT INTO rules (rule_key, body, version) VALUES (?,?,?)",
                    (key, body, ver))
    con.commit()
    con.close()


def write_mirror(path: Path, entries: list, crlf: bool = False) -> None:
    """entries: [(key, lock, ver, body)] — форма заголовка ТА ЖЕ, что печатает export-rules.py.

    crlf=True — чужая форма (случай ⑤): пишем БАЙТАМИ с Windows-концами строк (\\r\\n),
    а не полагаемся на текстовый режим (который сам привёл бы \\n к \\r\\n на записи —
    здесь нужен именно ПРОВЕРЯЕМЫЙ файл, а не то, что удобно писателю)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    parts = []
    for key, lock, ver, body in entries:
        parts.append(f"### `{key}` 🔒{lock} v{ver}\n\n{body.strip()}\n")
    text = "\n".join(parts)
    if crlf:
        path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))
    else:
        path.write_text(text, encoding="utf-8")


def _bootstrap_container(tool: Path) -> str:
    """MEZO_CONTAINER — ТОЛЬКО чтобы check-rules-mirror.py успел ИМПОРТИРОВАТЬСЯ (он
    резолвит LIVE на верхнем уровне, до argparse); --db ниже перебивает дефолт, а поиск
    файла-зеркала идёт от --db (mirror_candidates(db_path.resolve().parent)), не отсюда.
    В живом дереве (приёмка рядом со скриптами) хватило бы своего __file__ — как делает
    bite-check-rules-mirror.py. Эта приёмка может быть позвана и ИЗ ПЕСОЧНИЦЫ, где её
    __file__ не под контейнером — тогда берём каталог стенда: при заданной MEZO_CONTAINER
    mezo_paths маркер не проверяет, а базу и файл-зеркало всё равно называет --db.
    ⛔ Литерала пути машины здесь быть не может: перенос в образец его отвергает — у
    потребителя такая строка исполнялась бы с чужим путём (отказ --to-template 14.09)."""
    try:
        return str(mezo_paths.container_root(__file__))
    except SystemExit:
        return str(tool.parent)


def call_tool(tool: Path, db: Path):
    """Зовёт check-rules-mirror.py БЕЗ --file — испытывается САМ ПОИСК."""
    # ⚖️ Поиск файла-зеркала идёт от --db, а не от MEZO_CONTAINER — иначе случай ③
    # (пакетная раскладка вне реального контейнера) не отличался бы от случая ①.
    env = dict(os.environ, MEZO_CONTAINER=_bootstrap_container(tool))
    r = subprocess.run([sys.executable, "-B", str(tool), "--db", str(db)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--break", "--porcha", dest="porcha", choices=["one-place"],
                    help="нарочная поломка: mirror_candidates() урезан до .mezosync/generated")
    a = ap.parse_args()

    # Испытываем ту редакцию, что готовится лечь в ОБЕ копии (scripts и vnext-tools) —
    # в песочнице это один и тот же файл, испытывать дважды нет смысла: копии байт-в-байт
    # совпадают (проверено sha256 при сборке), различий, которые бы разошлись при копировании,
    # здесь нет.
    live_tool = Path(__file__).resolve().parent / "check-rules-mirror.py"
    if not live_tool.is_file():
        sys.exit(f"⛔ НЕ ЗАПУСТИЛСЯ: check-rules-mirror.py нет рядом: {live_tool}")
    print(f"━━ испытуется единая редакция: {live_tool}")
    run_cases(live_tool, a.porcha)
    print(f"\nИТОГ: {PASSED} из {CASES} · различающих {DIFFER}")
    return 0 if PASSED == CASES else 1


def run_cases(live_tool: Path, porcha) -> None:
    stand = Path(tempfile.mkdtemp(prefix="bite-rules-mirror-search-"))
    try:
        tool = stand / "check-rules-mirror.py"
        shutil.copy2(live_tool, tool)
        shutil.copy2(Path(__file__).resolve().parent / "mezo_paths.py", stand / "mezo_paths.py")

        if porcha == "one-place":
            text = tool.read_text(encoding="utf-8")
            old = ('return [\n        mezo.parent / "atlas.archs" / ".mezosync" / '
                   '"coordination" / "sync.rules.md",\n        mezo / "generated" / '
                   '"sync.rules.md",\n    ]')
            new = 'return [\n        mezo / "generated" / "sync.rules.md",\n    ]'
            assert text.count(old) == 1, f"поломка НЕ ЛЕГЛА: найдено {text.count(old)}"
            tool.write_text(text.replace(old, new), encoding="utf-8")
            print("🧪 НАРОЧНАЯ ПОЛОМКА «one-place»: mirror_candidates() урезан до "
                  ".mezosync/generated (раскладка Atlas выпала из списка). "
                  "Ждём: ровно случай ② провалится; ①③⑤ по-прежнему пройдут.\n")

        # ── ① ВСТРЕЧНЫЙ/контроль: правил нет, файла нет НИГДЕ — «сверять нечего» ───
        root1 = stand / "root1"
        (root1 / ".mezosync").mkdir(parents=True)
        db1 = root1 / ".mezosync" / "mezosync.db"
        build_db(db1, {})
        code1, out1 = call_tool(tool, db1)
        case("① ВСТРЕЧНЫЙ: правил нет и файла нет нигде — сверять нечего, код 0",
             code1 == 0 and ("пропущ" in out1.lower()),
             f"код {code1}")

        # ── ② ГЛАВНЫЙ: раскладка Atlas ────────────────────────────────────────────
        root2 = stand / "root2"
        (root2 / ".mezosync").mkdir(parents=True)
        db2 = root2 / ".mezosync" / "mezosync.db"
        build_db(db2, {"test-atlas": ("тело правила раскладки Atlas", 1)})
        mirror2 = root2 / "atlas.archs" / ".mezosync" / "coordination" / "sync.rules.md"
        write_mirror(mirror2, [("test-atlas", "coord", 1, "тело правила раскладки Atlas")])
        code2, out2 = call_tool(tool, db2)
        case("② ГЛАВНЫЙ: раскладка Atlas (atlas.archs/.mezosync/coordination) — находит, "
             "код 0, без литерала пути",
             code2 == 0 and "сошл" in out2.lower() and "coordination" in out2,
             f"код {code2}", differ=True)

        # ── ③ ВСТРЕЧНЫЙ к ②: раскладка контура из пакета, Atlas-пути нет ВООБЩЕ ────
        root3 = stand / "root3"
        (root3 / ".mezosync").mkdir(parents=True)
        db3 = root3 / ".mezosync" / "mezosync.db"
        build_db(db3, {"test-pack": ("тело правила раскладки пакета", 1)})
        mirror3 = root3 / ".mezosync" / "generated" / "sync.rules.md"
        write_mirror(mirror3, [("test-pack", "coord", 1, "тело правила раскладки пакета")])
        assert not (root3 / "atlas.archs").exists(), "стенд ③ не должен нести Atlas-путь"
        code3, out3 = call_tool(tool, db3)
        case("③ ВСТРЕЧНЫЙ к ②: раскладка контура из пакета (.mezosync/generated), Atlas-пути "
             "нет вовсе — тоже находит, код 0 (доказывает: ищутся ОБЕ раскладки)",
             code3 == 0 and "сошл" in out3.lower() and "generated" in out3,
             f"код {code3}", differ=True)

        # ── ④ файла нет НИГДЕ, правила ЕСТЬ — прежний громкий отказ «сверить нечем» ─
        root4 = stand / "root4"
        (root4 / ".mezosync").mkdir(parents=True)
        db4 = root4 / ".mezosync" / "mezosync.db"
        build_db(db4, {"test-nowhere": ("тело правила без зеркала", 1)})
        code4, out4 = call_tool(tool, db4)
        case("④ файла нет ни в одном известном месте, правила ЕСТЬ — «сверить НЕЧЕМ», код 1",
             code4 == 1 and "сверить" in out4.lower() and "нечем" in out4.lower(),
             f"код {code4}", differ=True)

        # ── ⑤ ЧУЖАЯ ФОРМА: раскладка пакета, файл-зеркало в CRLF ────────────────────
        # Без своей парной поломки — см. разбор в докстринге ВЫШЕ (устойчивость к \r
        # структурная, держится сразу на трёх независимых механизмах, а не на одной
        # строке; ломать её значило бы переписывать разбор целиком, а не портить строку).
        root5 = stand / "root5"
        (root5 / ".mezosync").mkdir(parents=True)
        db5 = root5 / ".mezosync" / "mezosync.db"
        build_db(db5, {"test-crlf": ("тело правила с CRLF-зеркалом", 1)})
        mirror5 = root5 / ".mezosync" / "generated" / "sync.rules.md"
        write_mirror(mirror5, [("test-crlf", "coord", 1, "тело правила с CRLF-зеркалом")],
                     crlf=True)
        assert b"\r\n" in mirror5.read_bytes(), "стенд ⑤ обязан нести реальный CRLF"
        code5, out5 = call_tool(tool, db5)
        case("⑤ ЧУЖАЯ ФОРМА: раскладка пакета, файл-зеркало в CRLF — тоже находит и сходится",
             code5 == 0 and "сошл" in out5.lower(),
             f"код {code5}")
    finally:
        shutil.rmtree(stand, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
