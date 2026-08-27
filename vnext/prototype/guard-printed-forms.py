# -*- coding: utf-8 -*-
# SURFACES: canon rules tasks printed vitrina
"""
guard-printed-forms.py — УЧАЩАЯ ПОВЕРХНОСТЬ ШИРЕ ПАМЯТИ.

Заведён 2026-07-27 по находке канарейки @STUD (#2861) и её замеру остатка (#2864),
врезка @COORD `83e8882`. Повод дословно: `read-messages.py` печатал команду ack как
`python read-messages.py --db <путь>` — то есть РАБОЧИЙ ВЫВОД, который роль читает КАЖДЫЙ
цикл ленты (чаще, чем шапку `read-phoenix`!), учил сразу двум ОТОЗВАННЫМ формам:
относительному вызову (F20: при уехавшем CWD молча пишет в чужую БД) и снятому `--db` (R15a).

📌 Класс: **ВЕРШИНА УЧАЩИХ ПОВЕРХНОСТЕЙ БЫЛА НЕ ОДНА.** Гард соответствия
(`guard-role-standard.py`) ищет форму в СЛЕПКАХ ролей и по регекспу `.mezosync/scripts` —
поэтому не видел ни голого `python read-messages.py`, ни строк, которые скрипты ПЕЧАТАЮТ,
ни ГЕНЕРАТОРА витрин (`export-channels.py`), плодящего отозванную форму в артефакты
(замер @STUD: 20 вхождений в 8 файлах `coordination/generated/`).
Ранжир @STUD принят как норма: **рабочий вывод > docstring > шапка памяти.**

ЧТО ЭТОТ ГАРД ВИДИТ
  · строковые литералы и f-строки в .py (то, что скрипт может НАПЕЧАТАТЬ или показать),
    включая docstring — их читают так же, как вывод;
  · готовые артефакты (.md витрины) — там форма уже вычислена генератором;
  · СВОД ПРАВИЛ — rules.body живой БД, только active (с 27.08, заход 1 пула): правило
    свода учило формой, отменённой каноном месяц назад, и ни один сторож этого не видел;
  · НАКАЗЫ-ФАЙЛЫ планировщика (<задача>/SKILL.md, с 27.08): наказ роль слушается РАНЬШЕ
    памяти, а стерёг его никто (живой случай 27.08: наказ победил верную память роли);
  · приметы: вызов не абсолютным путём · `--db` · команда, РАЗОРВАННАЯ переносом (швы
    склеиваются предпроходом seams и судятся как строка, которой они были) ·
    относительная форма БЕЗ имени файла (признак G, случай file-map:3).

ЧЕГО НЕ ВИДИТ (называю сам, чтобы зелёное не читалось шире, чем оно есть)
  · форму, собранную из кусков в рантайме (`" ".join([...])`) — литерала нет, увидеть нечем;
  · комментарии в коде: их роль не читает как инструкцию (и AST их не отдаёт);
  · ПАМЯТЬ РОЛЕЙ — зона guard-launcher-forms.py; ЛЕНТУ и историю сообщений — это история,
    её не переписывают; ПРОЧИЕ столбцы rules (basis и др. — там форма не инструкция);
  · наказы, живущие В СТЕНОГРАММАХ сессий (.jsonl) — файлом не правятся, суду недоступны;
  · СМЫСЛ: строку «⛔ так больше не зовут» отличаю от инструкции только по приметам отзыва
    В ТОЙ ЖЕ СТРОКЕ (REVOKED_MARK). Это приблизительный детектор, и его ЕДИНИЦА — строка.

Живой субстрат ТОЛЬКО ЧИТАЕТСЯ. Ничего не правит и не предлагает автопочинку.

    python <абсолютный путь>/guard-printed-forms.py            # живые скрипты + витрины
    python <абсолютный путь>/guard-printed-forms.py --selftest # доказать, что умеет краснеть
"""
import argparse
import ast
import re
import sqlite3
import subprocess
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

SELF = Path(__file__).resolve()
LIVE_SCRIPTS = mezo_paths.live_scripts()
LIVE_ARTIFACTS = mezo_paths.container_root() / "atlas.archs" / ".mezosync" / "coordination" / "generated"

# Вызов скрипта: «python <что-то до имени><имя>.py». Голое имя без `python` — это ссылка
# в прозе («см. read-messages.py:310»), а не форма вызова: такие НЕ трогаем.
CALL = re.compile(r"(?P<lead>python3?\s+)(?P<path>[^\s`'\"]{0,200}?)(?P<name>[\w.\-]+\.py)")
# Путь ВЫЧИСЛЕН, а не написан: `{Path(__file__).resolve()}`, `{SELF}`, `{S}` и т.п.
COMPUTED = re.compile(r"\{[^}]*(__file__|resolve\(\)|SELF|SCRIPTS|HERE|_DIR)[^}]*\}", re.I)
ABS_LITERAL = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/])")
DB_FLAG = re.compile(r"--db\b")
# «Пометка при --db»: строка сама говорит, что флаг необязателен/для не-дефолтной БД.
DB_OK = re.compile(r"необязателен|не обязателен|только для|не-дефолтн|песочниц|sandbox", re.I)
# Отзыв/надгробие: строка учит НЕ звать так. Калибровка взята у гарда памятей —
# там первый прогон краснел на честном надгробии @TAXO, и это стоило доверия к гарду.
#
# ⛔ ЕДИНИЦА ГАШЕНИЯ — ТА ЖЕ СТРОКА, А НЕ ОКРЕСТНОСТЬ. Переучено 09.08 (карточка #151,
# цена — живая находка): прежде примета искалась по −4/+2 строкам ИСХОДНИКА вокруг, и
# надгробие, отменяющее СОСЕДНЮЮ, ДРУГУЮ вещь, гасило настоящую находку. guard-all:596
# печатал мёртвую в bash команду, а строкой ниже стояло «…признак БОЛЬШЕ НЕ ГАСИТ» —
# про совсем другой признак. Гард узнал строку и промолчал.
# 🎯 Класс: у соседства не спрашивают, О ЧЁМ оно ⇒ чем лучше документирован код, тем
#    слепее сторож — объяснения отмен пишутся ровно рядом с формами вызова.
# ⚖️ Обратный перегиб тоже оплачен (карточка #152): для КОДА той же строки мало — выражение
#    разнесено синтаксисом. Общий различитель: единица суждения — СТРОКА ПРОЗЫ или
#    ЗАКОНЧЕННОЕ ВЫРАЖЕНИЕ кода. Здесь судится напечатанная ПРОЗА ⇒ единица — строка.
# ⚡ ОБЩЕЕ — ИЗ ОБЩЕГО РАЗЛИЧИТЕЛЯ (mention.py, #57). Здесь остаётся только ПРЕДМЕТНОЕ:
# знаки-запрещалки и слова, осмысленные лишь для ПЕЧАТАЕМОЙ ФОРМЫ ВЫЗОВА («не зови»,
# «вместо», имена наших же правил). Роды cancel/history/quote — общие, и словарь под них
# я писал здесь пятый раз за двое суток; каждая своя редакция ошибалась по-своему.
import mention  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

OWN_MARK = re.compile(r"(⛔|⚠️|НЕЛЬЗЯ|нельзя|не зови|вместо|F20|R15a"
                     r"|прежн|раньше|было:)", re.I)
# ⚖️ РОДЫ ВЫБРАНЫ ЗАМЕРОМ, А НЕ ВКУСОМ — три прогона против baseline «до перевода»:
#     cancel+history+quote → цитат 82 (на 6 МЕНЬШЕ: дата и «ёлочки» гасили формы,
#                                      про которые никто ничего не отменял)
#     только cancel ....... → цитат 90 (на 2 БОЛЬШЕ: общий словарь у́же старого)
#     cancel + узкие слова истории В СВОЁМ словаре → 88, ровно как было
# Отсюда граница, названная вслух: «прежде/раньше/было:» — ядро истории, годное для
# ФОРМЫ ВЫЗОВА; общий род history шире (любая дата, любое «было») и для этого предмета
# слеп. Модуль потому и отдаёт роды поимённо — выбор родов принадлежит потребителю.
_MENTION_KINDS = ("cancel",)


class _Revoked:
    """Совместимая обёртка: .search(text) — как у скомпилированного образца."""

    def search(self, text):
        return OWN_MARK.search(text or "") or (
            mention.is_mention(text, kinds=_MENTION_KINDS) or None)


REVOKED_MARK = _Revoked()

# ⭐ ПРИЗНАК F (находка @CORE #3448/#3449 и @opssre #3441, 2026-08-08).
# Прежний образец ловил ТОЛЬКО вызовы наших python-скриптов ⇒ команда ЧУЖОГО инструмента
# с теми же обратными слэшами была ему невидима:
#     git -C C:\guts\.atlas\atlas.core log --oneline -6
# Роль копирует её так же, как нашу, и получает в bash `can't open file`: `\` съедается как
# escape. @CORE нашёл такую строку ГЛАЗАМИ ПОСЛЕ зелёного прогона гарда — то есть зелёное
# давало ложное спокойствие при живой неисполнимой строке рядом.
# 🎯 Класс мой же, вывернутый на меня: **проверка стерегла ПРИЗНАК («это вызов нашего
#    скрипта») вместо СВОЙСТВА («напечатанная команда исполнима у того, кто её скопирует»).**
# ⚖️ ГРАНИЦА ОБРАЗЦА НАЗВАНА, и она не «где стоит инструмент», а ЧТО МЕЖДУ НИМ И ПУТЁМ.
#    Первая редакция требовала инструмент в начале строки — и пропустила собственный
#    грязный образец («смотри: git -C C:\...»), потому что перед ним стояло приглашение.
#    Различитель точнее: у КОМАНДЫ между инструментом и путём идут флаги и подкоманды
#    (` -C `, ` log `), у ПРОЗЫ — слова языка («история git лежит в C:\...»).
#    ⇒ запрещаем кириллицу в промежутке. Встречный образец `clean_prose_tool.py` сторожит
#    именно это: без него признак кричал бы на каждом упоминании инструмента в тексте.
OTHER_TOOL = re.compile(
    r"\b(?P<tool>git|docker|dotnet|curl|npm|node|pwsh|powershell|psql)\b"
    r"(?P<mid>[^\n`'\"\u0400-\u04FF]{0,60}?)(?P<path>[A-Za-z]:\\[^\s`'\"]+)")
# \u041F\u0440\u0438\u0437\u043D\u0430\u043A G: `.mezosync/scripts/` (\u0438\u043B\u0438 \u0441 `\`) \u0411\u0415\u0417 \u0438\u043C\u0435\u043D\u0438 \u0444\u0430\u0439\u043B\u0430 \u0441\u043B\u0435\u0434\u043E\u043C \u2014 \u0444\u043E\u0440\u043C\u0430-\u043E\u0431\u0440\u0443\u0431\u043E\u043A
# \u0432\u0438\u0434\u0430 `python .mezosync\scripts\\u2026`. \u0421 \u0438\u043C\u0435\u043D\u0435\u043C \u0444\u0430\u0439\u043B\u0430 \u0441\u0442\u0440\u043E\u043A\u0443 \u0441\u0443\u0434\u0438\u0442 \u043F\u0440\u0438\u0437\u043D\u0430\u043A A \u2014 \u0437\u0430\u0434\u0432\u043E\u0435\u043D\u0438\u0435
# \u0440\u0435\u0436\u0435\u0442 \u043E\u0442\u0440\u0438\u0446\u0430\u0442\u0435\u043B\u044C\u043D\u044B\u0439 \u043F\u0440\u043E\u0441\u043C\u043E\u0442\u0440 (\u0431\u0435\u0437 \u043D\u0435\u0433\u043E 149 \u043B\u043E\u0436\u043D\u044B\u0445 \u043F\u043E \u043A\u043E\u043D\u0442\u0443\u0440\u0443, \u0437\u0430\u043C\u0435\u0440 27.08 \u0414\u041E \u043A\u043E\u0434\u0430).
REL_NO_NAME = re.compile(r"\.mezosync[\\/]scripts[\\/](?![\w\-]+\.py)")


def materialize(path, name, scripts):
    """Во что превратится напечатанный путь у РОЛИ. Две проекции, потому что роль зовёт
    скрипты двумя разными инструментами:
      · как есть            — PowerShell/cmd примут и обратные слэши;
      · после bash-escape   — Bash-инструмент СЪЕДАЕТ `\\` как экранирование.
    Вторая проекция и есть третий оборот класса у @COORD (#2871): напечатанный
    `C:\\guts\\.atlas\\...` приезжал в Bash как `C:guts.atlas...` — файла нет, команда мертва.
    Возвращает (как_есть, в_bash) или (None, None), если путь не материален."""
    full = (path or "") + name
    if "{" in full:
        # ⚠️ Замена — ЛЯМБДОЙ, а не строкой: `re.sub` читает `\U` в `C:\Users\…` как escape
        # и падает `bad escape \U`. Тот же класс, что ловим (обратный слэш съеден движком),
        # поймал меня в САМОМ детекторе этого класса, через минуту после написания.
        full = re.sub(r"\{[^}]*\}", lambda _: str(scripts), full)
    if not ABS_LITERAL.match(full.strip()):
        return None, None
    as_is = Path(full.strip().replace("\\", "/"))
    in_bash = Path(re.sub(r"\\(.)", r"\1", full.strip()))
    return as_is, in_bash


def classify(text, known, proven=(), scripts=None, observed=False):
    """Приметы в ОДНОЙ печатаемой строке. Возвращает список (вид, фрагмент).

    Гашение отзывом смотрит ТОЛЬКО в эту же строку (см. REVOKED_MARK): окрестность
    исходника сюда больше не передаётся — у неё не спросишь, о чём она.

    `proven` — имена переменных, ДОКАЗАННО вычисленных из `__file__` в этом же файле.
    Без них `python {s}\\read-messages.py` спасался только приметой отзыва рядом — то есть
    зелёное выпадало СЛУЧАЙНО (замер 2026-07-27 на живом `export-channels.py`: строка была
    чиста по существу, а гард этого не знал). Зелёное по случайности — не зелёное.
    """
    out = []
    for m in CALL.finditer(text):
        path, frag = m.group("path"), text[max(0, m.start() - 30):m.end() + 60].strip()
        if m.group("name") not in known:
            # ⚠️ Имя может быть НЕ в списке именно потому, что оно СЛОМАНО: у @COORD escape
            # съел слэш и `scripts\read-messages.py` стал `scriptsead-messages.py`. Гард,
            # ищущий скрипт ПО ИМЕНИ, слеп ровно к тому дефекту, который ломает имя.
            # ⇒ прежде чем отбросить как «чужой скрипт», проверяем путь на диске.
            if scripts is not None and not REVOKED_MARK.search(text):
                as_is, _ = materialize(path, m.group("name"), scripts)
                if as_is is not None and not as_is.exists():
                    out.append(("🔴 E ПУТЬ НЕ СУЩЕСТВУЕТ — команда мертва как напечатана "
                                "(имя, вероятно, СЛОМАНО escape'ом)", frag))
            continue                                   # чужой скрипт — не наша поверхность
        if REVOKED_MARK.search(text):
            continue                                   # надгробие ЭТОЙ строке, не соседней
        var = re.match(r"\{([\w.]+)[^}]*\}", path.strip())
        if COMPUTED.search(path) or (var and var.group(1).split(".")[0] in proven):
            pass                                       # ✅ путь берётся свойством — не разъедется
        elif var:
            # Шаблон: вердикт выносит НАБЛЮДЕНИЕ вывода, а не догадка о значении переменной.
            if not observed:
                out.append(("🟡 D ШАБЛОН — судится только ПРОГОНОМ (запусти без --no-run)",
                            frag))
        elif not path.strip():
            out.append(("🔴 A ГОЛОЕ ИМЯ (F20: CWD уедет — попадёт в чужую БД)", frag))
        elif ABS_LITERAL.match(path.strip()):
            # ⚠️ КАЛИБРОВКА 2026-07-27 09:59 UTC. Было 🟡 «переживёт переезд ложью» — и после
            # врезки @COORD `ae852cf` таких стало 55 из 59 жёлтых. Но АБСОЛЮТНЫЙ ПУТЬ — ровно
            # то, чего требует стандарт (`role-migration-standard` ②, утверждён владельцем).
            # Гард, желтящий предписанную канону форму, за один прогон превращается в фон,
            # который перестают читать, — мой же класс «вечно-жёлтый гард» (153 срабатывания).
            # Оговорка про переезд каталога верна, но это ограничение КАНОНА, и её место —
            # в своде один раз, а не на каждой строке.
            out.append(("🟢 B АБСОЛЮТНЫЙ ЛИТЕРАЛ — норма канона", frag))
        else:
            out.append(("🔴 A ОТНОСИТЕЛЬНЫЙ ПУТЬ (F20)", frag))
        # ⭐ ПРИЗНАК E (заявка @COORD #2871): напечатанную команду ПРОГНАТЬ, а не прочитать.
        # ⚠️ КАЛИБРОВКА 10:21 UTC по замеру @COORD (#2873): здесь E применяется ТОЛЬКО к
        # литеральному пути. Шаблон со `{плейсхолдером}` судит НАБЛЮДЕНИЕ (см. observe): пока
        # гард раскрывал `{s}` СВОИМИ руками, он мерил собственное представление о переменной —
        # и после починки `as_posix()` краснел ×4 на исполнимом коде.
        # 📌 Класс, названный @COORD и принятый: **проверка, ВОСПРОИЗВОДЯЩАЯ поведение вместо
        # НАБЛЮДЕНИЯ его, наследует свои же допущения** — и выносит вердикт о них, а не о коде.
        if scripts is not None and "{" not in (path or ""):
            as_is, in_bash = materialize(path, m.group("name"), scripts)
            if as_is is not None and not as_is.exists():
                out.append(("🔴 E ПУТЬ НЕ СУЩЕСТВУЕТ — команда мертва как напечатана", frag))
            elif in_bash is not None and not in_bash.exists():
                out.append(("🔴 E НЕ ОТКРОЕТСЯ В BASH — `\\` съедается как escape "
                            "(нужен `.as_posix()`)", frag))
        tail = text[m.end():]
        if DB_FLAG.search(tail) and not DB_OK.search(text) and not REVOKED_MARK.search(text):
            out.append(("🔴 C `--db` В ПЕЧАТАЕМОЙ СТРОКЕ (снят R15a — учит отозванному)", frag))

    # ── ПРИЗНАК F: КОМАНДА ЧУЖОГО ИНСТРУМЕНТА С ОБРАТНЫМИ СЛЭШАМИ ─────────────────────
    # ⚖️ Судим то же СВОЙСТВО, что и у своих вызовов («откроется ли у того, кто скопирует»),
    # а не принадлежность инструмента. Надгробия и контрпримеры не трогаем — они учат,
    # как НЕ надо, и «починить» их значило бы стереть предупреждение, оставив вид починки.
    if not REVOKED_MARK.search(text):
        for m in OTHER_TOOL.finditer(text):
            out.append((f"🔴 F ЧУЖОЙ ИНСТРУМЕНТ (`{m.group('tool')}`) С `\\` — НЕ ОТКРОЕТСЯ "
                        f"В BASH, нужен прямой слэш",
                        text[max(0, m.start() - 20):m.end() + 40].strip()))

    # ── ПРИЗНАК G: ОТНОСИТЕЛЬНАЯ ФОРМА БЕЗ ИМЕНИ ФАЙЛА (случай file-map:3, заход 1) ──
    # Правило учило «зови `python .mezosync\scripts\…`» — формой, отменённой каноном 26.07,
    # и НИ ОДИН сторож этого не видел: CALL требует имени `.py`, а тут его нет по построению.
    # ⚖️ Отрицательный просмотр «дальше НЕ имя.py» ОБЯЗАТЕЛЕН: без него признак задваивает
    # находки признака A и даёт 149 ложных по контуру (замерено ДО кода, 27.08). Слово
    # `python` в той же строке отличает УЧЕНИЕ ФОРМЕ от упоминания каталога в прозе.
    # Одна находка на строку: два вхождения в одной строке — один и тот же урок читателю.
    if (not REVOKED_MARK.search(text) and re.search(r"\bpython3?\b", text)
            and REL_NO_NAME.search(text)):
        out.append(("🔴 G ОТНОСИТЕЛЬНАЯ ФОРМА БЕЗ ИМЕНИ ФАЙЛА — учит отозванной F20-форме "
                    "(канон 26.07: относительная форма ЗАПРЕЩЕНА)",
                    text.strip()[:110]))
    return out


def literals(src):
    """Все строковые литералы и f-строки файла как (номер строки, текст, РАНГ).
    f-строку собираем с плейсхолдерами — по ним и видно, вычислен путь или написан.

    РАНГ — ранжир @STUD (#2862), принятый контуром как норма: **рабочий вывод > docstring**.
    Роль читает вывод ридера каждый цикл ленты; docstring — когда лезет разбираться.
    Один список без ранга уравнял бы подвал витрины с примером в справке.
      R1 — печатается в работе (внутри `print(...)`)   R2 — docstring и `help=`   R3 — прочее
    """
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return None, e, set()
    # переменные, ДОКАЗАННО вычисленные из `__file__` (S = Path(__file__).resolve().parent)
    proven = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
              for t in n.targets if isinstance(t, ast.Name)
              and "__file__" in ast.unparse(n.value)}
    printed, docs = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "print":
            printed |= {id(x) for x in ast.walk(node)}
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            first = node.body[0] if node.body else None
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docs.add(id(first.value))
        if isinstance(node, ast.keyword) and node.arg == "help":
            docs |= {id(x) for x in ast.walk(node)}
    # ⚠️ ast.walk отдаёт куски f-строки ДВАЖДЫ: как части JoinedStr и как самостоятельные
    # Constant. Первый прогон самопроверки от этого дал по 2 находки вместо 1 — счёт был бы
    # завышен вдвое на всех f-строках. Отсюда: части JoinedStr исключаем поимённо.
    inner = {id(v) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr) for v in n.values}
    rank = lambda n: "R1" if id(n) in printed else "R2" if id(n) in docs else "R3"
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in inner:
            found.append((node.lineno, node.value, rank(node)))  # proven — общий на файл
        elif isinstance(node, ast.JoinedStr):
            parts = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                elif isinstance(v, ast.FormattedValue):
                    parts.append("{" + ast.unparse(v.value) + "}")
            found.append((node.lineno, "".join(parts), rank(node)))
    return found, None, proven


def scan_py(path, known, scripts=None, observed=False):
    src = path.read_text(encoding="utf-8", errors="replace")
    lits, err, proven = literals(src)
    if err:
        return [(0, "R1", "⚠️ НЕ РАЗОБРАН (SyntaxError) — файл НЕ проверен, "
                          "зелёное на него не распространяется", str(err)[:80])]
    hits = []
    for lineno, text, rank in lits:
        # РАЗБИВАЕМ ПО СТРОКАМ ЛИТЕРАЛА: многострочный docstring — один узел, и без этого
        # каждая находка получала :1 (строку начала блока). Номер, по которому нельзя
        # открыть место, — не адрес, а вид адреса.
        for off, piece in enumerate(text.splitlines() or [text]):
            real = lineno + off
            # Окрестность исходника в суждении НЕ участвует (#151): у неё не спросишь,
            # о чём её надгробие. Судится ровно та строка, которую роль прочтёт.
            for kind, frag in classify(piece, known, proven, scripts, observed):
                hits.append((real, rank, kind, frag))
    return hits


def templates_of(generator, known):
    """Формы, которые ПОРОЖДАЕТ генератор витрин, как регекспы: `{выражение}` → джокер.
    Нужны, чтобы отличить подвал, напечатанный генератором (долг, чинится в одном месте),
    от ЦИТАТЫ формы внутри тела ноты (история контура — её не переписывают)."""
    if not generator.exists():
        return []
    lits, err, _pv = literals(generator.read_text(encoding="utf-8", errors="replace"))
    if err:
        return []
    out = []
    for _, text, _ in lits:
        for piece in text.splitlines():
            if not any(n in piece for n in known) or not CALL.search(piece):
                continue
            rx = "".join(".*" if p.startswith("{") else re.escape(p)
                         for p in re.split(r"(\{[^}]*\})", piece) if p)
            out.append(re.compile(rx))
    return out


def scan_md(path, known, templates=None, scripts=None):
    """В витрине долгом считается ТОЛЬКО то, что напечатал генератор. Первый прогон
    2026-07-27 дал 141 🔴 на 33 файлах — и это было ЛОЖНО: большинство вхождений сидело
    в ТЕЛАХ НОТ, экспортированных в витрину. Требовать «починить» цитату 2026-07-10 —
    значит требовать переписать историю. Гард, который считает историю долгом, шумит."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    hits, quoted = [], 0
    for i, line in enumerate(lines, 1):
        found = classify(line, known, (), scripts)
        if not found:
            continue
        if templates is not None and not any(t.search(line) for t in templates):
            quoted += len(found)          # цитата в теле ноты — не долг, но считаем вслух
            continue
        hits += [(i, "R1", kind, frag) for kind, frag in found]
    scan_md.quoted = getattr(scan_md, "quoted", 0) + quoted
    return hits


def scan_canon(path, known, scripts):
    """КАНОН (CLAUDE.md контейнера) — самая читаемая учащая поверхность, и до 09.08 её
    не читала НИ ОДНА проверка (карточка #56). Цена уже заплачена: 08.08 в каноне почти
    сутки жил ОТМЕНЁННЫЙ запрет, и нашли его глазами, а не проверкой.

    🎯 Канон учит формам через СОКРАЩЕНИЕ, объявленное в нём же (`<s>` = путь). Судить
    такую строку как написанную — красить исполнимое; не судить вовсе — слепнуть.
    ⇒ Сокращения РАСКРЫВАЮТСЯ ПЕРЕД судом, и дальше работает общий classify:
      · объявлено и ведёт в живое место → чисто (как вычисленный путь);
      · НЕ объявлено → красное: читатель без определения получает мёртвую команду;
      · объявлено, но место НЕ существует → красное признаком E — определение протухло,
        и это хуже отсутствия: форма выглядит снабжённой ключом.
    """
    if not path.exists():
        return None                                    # отсутствие канона — сказать вслух
    hits = []
    defs = canon_defs(path)
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        for kind, frag in classify(expand_abbrev(line, defs), known, (), scripts):
            hits.append((i, "R1", kind, frag))         # канон читается КАЖДЫМ — ранг рабочего вывода
    return hits


def canon_defs(path):
    """Словарь сокращений канона (`<s>` = путь) — ровно прежний разбор scan_canon,
    вынесен: с 27.08 сокращениями пользуются и СВОД ПРАВИЛ, и наказы-файлы, а вторая
    копия разбора разошлась бы с этой молча. Канона нет → None: судить свод без словаря
    значит выдать ложные красные за находки (замерено 27.08: 2 ложных)."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    defs = {}
    for m in re.finditer(r"`?<([\w-]+)>`?\s*=\s*`?([A-Za-z]:[/\\][^\s`'\"]+)`?", text):
        defs[m.group(1)] = m.group(2).rstrip("/\\")
    return defs


def expand_abbrev(line, defs):
    """Раскрыть сокращения канона ПЕРЕД судом — ровно прежние замены scan_canon, плюс
    ГОЛОЕ `<s>` (без разделителя следом): склейка разорванной переносом команды даёт
    `python <s>ead-messages.py`, и без голого раскрытия сторож на ней молчит; с ним
    имя не находится в списке и срабатывает УЖЕ НАПИСАННАЯ ветка «имя, вероятно,
    сломано». Вердикт выносит старое правило — здесь только собирается кандидат.
    Цена замерена 27.08: прогон свода с голым раскрытием и без — побайтно одинаков.
    Порядок замен важен: формы с разделителем — раньше голой, иначе голая съест их
    и удвоит разделитель."""
    for name, root in (defs or {}).items():
        line = (line.replace(f"<{name}>/", root + "/")
                    .replace(f"<{name}>\\", root + "\\")
                    .replace(f"<{name}>", root + "/"))
    return line


def seams(lines):
    """Предпроход «КОМАНДА РАЗОРВАНА ПЕРЕНОСОМ» (заход 1 п.1.3). НЕ внутри classify:
    её единица — одна строка (оплачено карточками #151/#152), а шов живёт в ДВУХ.
    Восстанавливает строку, какой она была до разрыва, и отдаёт её обычному суду.

    Шесть условий, все обязательны, у каждого свой встречный (приёмка ослабляет порознь):
      голова: ① «python + один довод + конец строки» ② довод путь-подобен и не флаг
              ③ в голове нет `.py` ④ голова НЕ кончается на `\\` (законный перенос)
      хвост:  ⑤ с НУЛЕВОЙ колонки «имя.py» и дальше пробел/конец ⑥ не новая команда
    ③ и ④ — две независимые ветки под ОДИН встречный (tool-edit-announce:7 кончается
    на `\\` И содержит lease.py): срезать их в одну — одна умрёт незамеченной.
    Возвращает [(номер головы, склеенная строка, «СКЛЕЙКА N+N+1»), …]."""
    out = []
    for i in range(len(lines) - 1):
        head, tail = lines[i], lines[i + 1]
        m = re.match(r"^\s*python3?\s+(?P<arg>\S+)\s*$", head)
        if not m:
            continue                                   # ① голова: python + ровно один довод
        arg = m.group("arg")
        if arg.startswith("-") or not ("/" in arg or "\\" in arg or arg.startswith("<")):
            continue                                   # ② довод путь-подобен, не флаг
        if ".py" in head:
            continue                                   # ③ имени в голове нет — иначе цела
        if head.rstrip().endswith("\\"):
            continue                                   # ④ явный перенос длинной команды
        if not re.match(r"^[\w\-]+\.py(\s|$)", tail):
            continue                                   # ⑤ хвост: имя.py с нулевой колонки
        if re.match(r"^\s*python3?\b", tail):
            continue                                   # ⑥ хвост — новая команда, не обломок
        out.append((i + 1, head.strip() + tail.strip(), f"СКЛЕЙКА {i + 1}+{i + 2}"))
    return out


def judged_lines(lines, known, scripts, defs):
    """Общий суд строк источника из БД или файла-наказа: построчный classify после
    раскрытия сокращений + швы предпроходом. Склейка ИСПОЛНИМА → 🟡 (жёлтое не роняет
    код возврата: роль всё равно копирует по строке — предупреждаем, не запрещаем);
    склейка мертва → красные признаки старых правил с припиской происхождения."""
    out = []
    seam_list = seams(lines)
    seam_heads = {lineno for lineno, _, _ in seam_list}
    for i, line in enumerate(lines, 1):
        for kind, frag in classify(expand_abbrev(line, defs), known, (), scripts):
            # Голова шва (`python <s>` без имени) после голого раскрытия выглядит для
            # признака G формой-обрубком — но её дефект ШОВ, и его судит склейка ниже
            # с происхождением. Две находки об одном дефекте — спор сторожей об одном
            # источнике, шум плотностью; G здесь гасится ПОИМЁННО, не окрестностью.
            if i in seam_heads and " G " in kind:
                continue
            out.append((i, kind, frag))
    for lineno, joined, origin in seam_list:
        # 🟢 «норма канона» находкой шва НЕ считается: исполнимая склейка — это ровно
        # случай «склеенное исполнимо, но роль копирует ПО СТРОКЕ», ему положено 🟡.
        found = [x for x in classify(expand_abbrev(joined, defs), known, (), scripts)
                 if not x[0].startswith("🟢")]
        if found:
            out += [(lineno, f"{kind} [{origin}]", frag) for kind, frag in found]
        else:
            out.append((lineno, f"🟡 РАЗОРВАНА ПЕРЕНОСОМ [{origin}] — склеенное исполнимо, "
                                f"но роль копирует ПО СТРОКЕ", joined.strip()[:110]))
    return out


def scan_rules(db, known, scripts, defs):
    """СВОД ПРАВИЛ (rules.body) — учащая поверхность, которую до 27.08 не читал НИ ОДИН
    сторож: правило file-map учило относительной формой, отменённой каноном 26.07, месяц.
    Судятся только active: отозванное — история (как цитаты в телах нот у витрин),
    надгробий не переписывают; счёт отозванных говорится ВСЛУХ, а не молчит.
    Возвращает (находки, отозванных, ошибка): база недоступна → (None, 0, текст) —
    «НЕ ПРОВЕРЕН» не равно «чисто»."""
    try:
        conn = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
        rows = conn.execute("SELECT rule_key, body, status FROM rules ORDER BY rule_key").fetchall()
        conn.close()
    except sqlite3.Error as e:
        return None, 0, 0, f"{type(e).__name__}: {e}"
    hits, inactive, tombstoned = [], 0, 0
    for key, body, status in rows:
        if status != "active":                         # revoked И superseded — история
            inactive += 1
            continue
        lines = (body or "").splitlines()
        for line in lines:
            el = expand_abbrev(line, defs)
            # «Погашено надгробием» считается ВСЛУХ: молчание о гашении неотличимо
            # от «форм не было» (класс #151 — надгробие обязано быть видно, не только
            # действовать). Счёт, не находка: надгробие — норма, а не долг.
            if REVOKED_MARK.search(el) and (CALL.search(el) or REL_NO_NAME.search(el)):
                tombstoned += 1
        for lineno, kind, frag in judged_lines(lines, known, scripts, defs):
            hits.append((f"{key}:{lineno}", kind, frag))
    return hits, inactive, tombstoned, None


def scan_tasks(tasks_dir, known, scripts, defs):
    """НАКАЗЫ-ФАЙЛЫ планировщика (<задача>/SKILL.md) — наказ роль слушается РАНЬШЕ своей
    памяти, а не стерёг его никто (живой случай 27.08: общий наказ синка победил верную
    запись в памяти роли). Наказы в СТЕНОГРАММАХ сессий сюда не входят — файлом
    не правятся, граница названа в шапке. Каталога нет → None: «НЕ ПРОВЕРЕНЫ» вслух."""
    if not tasks_dir.exists():
        return None
    hits = []
    for p in sorted(tasks_dir.glob("*/SKILL.md")):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, kind, frag in judged_lines(lines, known, scripts, defs):
            hits.append((f"{p.parent.name}:{lineno}", kind, frag))
    return hits


def observe(scripts, role="PROTO", timeout=25):
    """НАБЛЮДЕНИЕ: запустить скрипты и разобрать то, что они РЕАЛЬНО печатают.

    Это вторая половина признака E и главная его часть (@COORD #2873): гард обязан читать
    ВЫВОД, а не догадываться, во что развернётся `{s}` в шаблоне. Пока он раскрывал
    плейсхолдер сам, он выносил вердикт о собственном допущении.

    ⚠️ ГРАНИЦА БЕЗОПАСНОСТИ: запускаем ТОЛЬКО `--help` (argparse печатает и выходит) и
    read-only `read-phoenix --role`. Скрипт без argparse НЕ запускаем вовсе — у него `--help`
    может уйти в основное действие, а гард не имеет права мутировать живое.
    Возвращает (находки, сколько прогнано, сколько пропущено).
    """
    cmds, skipped = [], []
    for p in sorted(scripts.glob("*.py")):
        if "import argparse" not in p.read_text(encoding="utf-8", errors="replace"):
            skipped.append(p.name)
            continue
        cmds.append((p.name + " --help", [sys.executable, str(p), "--help"]))
    rp = scripts / "read-phoenix.py"
    if rp.exists():                       # шапка воскресшего — печатается только так
        cmds.append((f"read-phoenix.py --role {role}",
                     [sys.executable, str(rp), "--role", role]))
    hits = []
    for label, argv in cmds:
        try:
            r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=timeout)
        except (subprocess.TimeoutExpired, OSError) as e:
            hits.append((label, f"⚠️ НЕ ПРОГНАН ({type(e).__name__}) — вывод НЕ наблюдался", ""))
            continue
        for line in ((r.stdout or "") + (r.returncode and (r.stderr or "") or "")).splitlines():
            for m in CALL.finditer(line):
                full = (m.group("path") or "") + m.group("name")
                if "{" in full or not ABS_LITERAL.match(full.strip()):
                    continue              # относительное/шаблонное ловит статика
                as_is = Path(full.strip().replace("\\", "/"))
                in_bash = Path(re.sub(r"\\(.)", r"\1", full.strip()))
                if not as_is.exists():
                    hits.append((label, "🔴 E НАПЕЧАТАННЫЙ ПУТЬ НЕ СУЩЕСТВУЕТ", line.strip()[:110]))
                elif not in_bash.exists():
                    hits.append((label, "🔴 E НАПЕЧАТАННОЕ НЕ ОТКРОЕТСЯ В BASH (`\\` = escape)",
                                 line.strip()[:110]))
    return hits, len(cmds), skipped


def run(scripts, artifacts, quiet=False, do_run=True, role="PROTO"):
    if not scripts.exists():
        print(f"⛔ ГАРД НЕ ПОСТАВЛЕН: нет каталога скриптов {scripts}")
        return 2
    # ⚠️ Список имён ВЫЧИСЛЯЕТСЯ из каталога, а не пишется здесь: перечень скриптов —
    # производный факт, а зашитый перечень протухает молча (мой же класс ④).
    known = {p.name for p in scripts.glob("*.py")}
    if not quiet:
        print(f"[проверка печатаемых форм] скрипты: {scripts} ({len(known)} шт) · файлы из базы: "
              f"{artifacts if artifacts.exists() else '— нет каталога, файлы из базы НЕ проверены'}")
        print("   вижу: литералы/f-строки .py + строки .md + свод правил (rules.body, active) "
              "+ наказы-файлы · приметы: не-абсолютный вызов · --db · шов переноса · форма без имени")
        print("   НЕ вижу: форму, собранную в рантайме · комментарии · память ролей "
              "(guard-launcher-forms) · ленту и историю · наказы в стенограммах\n")
    obs_hits, obs_n, obs_skip = ([], 0, []) if not do_run else observe(scripts, role)
    if do_run and not quiet:
        print(f"── НАБЛЮДЕНИЕ: прогнано {obs_n} команд (--help + read-phoenix --role {role})"
              + (f" · НЕ запускались (нет argparse): {', '.join(obs_skip)}" if obs_skip else ""))
        for label, kind, line in obs_hits:
            print(f"   {kind}\n      {label}:  {line}")
        print(f"   {'🔴 ' + str(len(obs_hits)) + ' в НАПЕЧАТАННОМ' if obs_hits else '✅ напечатанное исполнимо'}\n")
    tpl = templates_of(scripts / "export-channels.py", known)
    scan_md.quoted = 0
    targets = [(p, lambda p_, k, s=scripts, o=do_run: scan_py(p_, k, s, o))
               for p in sorted(scripts.glob("*.py"))]
    if artifacts.exists():
        targets += [(p, lambda p_, k, t=tpl, s=scripts: scan_md(p_, k, t, s))
                    for p in sorted(artifacts.rglob("*.md"))]
    per_file, by_rank = [], {"R1": 0, "R2": 0, "R3": 0}
    red = yellow = green = 0
    for path, fn in targets:
        all_hits = fn(path, known)
        green += sum(1 for _, _, k, _ in all_hits if k.startswith("🟢"))
        hits = [h for h in all_hits if not h[2].startswith("🟢")]   # соответствие не печатаем
        if not hits:
            continue
        per_file.append((path, hits))
        for _, rank, kind, _ in hits:
            by_rank[rank] = by_rank.get(rank, 0) + (1 if kind.startswith("🔴") else 0)
        red += sum(1 for _, _, k, _ in hits if k.startswith("🔴"))
        yellow += sum(1 for _, _, k, _ in hits if k.startswith("🟡"))
    for path, hits in per_file:
        try:
            shown = path.relative_to(path.parents[1])
        except (ValueError, IndexError):
            shown = path.name
        print(f"── {shown}  ({len(hits)})")
        for lineno, rank, kind, frag in hits:
            print(f"   [{rank}] {kind}\n      :{lineno}  {frag[:110]}")
    print(f"\n{'🔴' if red else '✅'} печатаемых форм: 🔴 {red} · 🟡 {yellow} "
          f"· 🟢 {green} абсолютных (норма канона; при ПЕРЕЕЗДЕ каталога правятся руками — "
          f"ограничение канона, не долг строки) · файлов затронуто {len(per_file)} из {len(targets)}")
    print(f"   по рангу (ранжир @STUD): R1 рабочий вывод {by_rank['R1']} · "
          f"R2 docstring/--help {by_rank['R2']} · R3 прочее {by_rank['R3']}"
          + (f"\n   цитат формы в ТЕЛАХ НОТ этих файлов: {scan_md.quoted} — это ИСТОРИЯ, "
             f"НЕ долг (переписывать нечего)" if scan_md.quoted else ""))
    if red or obs_hits:
        print("   ⇒ чинить у ИСТОЧНИКА: строку печатает скрипт ⇒ правится скрипт; "
              "файл из базы печатает генератор ⇒ правится ГЕНЕРАТОР, а не N файлов на диске.")
    return 1 if (red or obs_hits) else 0


# Гард, который не умеет краснеть, — украшение (правило гейта TEST-MUST-BE-ABLE-TO-FAIL).
SAMPLES = {
    "dirty_bare.py": 'def f(role):\n    print(f"зови: python read-messages.py --role {role}")\n',
    "dirty_rel_db.py": ('def f(db, role):\n    print(f"подтверди: python .mezosync/scripts/'
                        'read-messages.py --db {db} --role {role} --ack X")\n'),
    "clean_computed.py": ('from pathlib import Path\ndef f(role):\n'
                          '    print(f"зови: python {Path(__file__).resolve()} --role {role}")\n'),
    "tombstone.py": ('def f():\n    print("⛔ ОТОЗВАНО: python .mezosync/scripts/'
                     'read-messages.py --db X — так больше не зовут")\n'),
    # ⭐ САМ СЛУЧАЙ КАРТОЧКИ #151: живая инструкция, а СТРОКОЙ НИЖЕ — надгробие про ДРУГОЕ.
    # Прежний гард (гашение по −4/+2 строкам исходника) на этом молчал: guard-all:596
    # печатал мёртвую команду, соседняя строка несла «…БОЛЬШЕ НЕ ГАСИТ» про другой признак,
    # и находка гасла. Роль копировала команду из вывода сторожа — места наибольшего доверия.
    "dirty_tomb_next_line.py": (
        'def f():\n'
        '    print("подтверди: python .mezosync/scripts/read-messages.py --ack X")\n'
        '    print("⛔ упоминание имени признак БОЛЬШЕ НЕ ГАСИТ: цитата не разбор")\n'),
    # ⚖️ ВСТРЕЧНЫЙ к нему: надгробие В ТОЙ ЖЕ строке, что и форма, гасит по-прежнему —
    # tombstone.py выше. Без пары «соседняя не гасит · своя гасит» починка либо шумит
    # на истории, либо слепнет на соседстве.
    "read-messages.py": "# существует, чтобы имя попало в известные\n",
    # ⭐ образцы под признак E (три оборота класса у @COORD, #2871)
    "dirty_broken_path.py": ('def f():\n    print("зови: python {S}scriptsread-messages.py '
                             '--role X")\n'),          # ② escape съел слэш в шаблоне
    "dirty_backslash.py": ('def f():\n    print("зови: python {CONT_B2}\\\\.mezosync'
                           '\\\\scripts\\\\read-messages.py --role X")\n'),   # ③ Bash съест
    # ⭐ образцы под признак F (@CORE #3448/#3449, @opssre #3441): команда ЧУЖОГО инструмента
    "dirty_other_tool.py": ('def f():\n    print(r"смотри: git -C {CONT_B2}'
                            '\\\\atlas.core log --oneline -6")\n'),
    # ⚖️ ВСТРЕЧНЫЕ (без них признак F стал бы кричать всегда, и его перестали бы читать):
    "clean_other_tool.py": ('def f():\n    print("смотри: git -C {CONT}/atlas.core '
                            'log --oneline -6")\n'),          # прямой слэш — исполнимо у всех
    "clean_prose_tool.py": ('def f():\n    print(r"история git лежит в {CONT_B2} '
                            'и переживёт чат")\n'),           # ПРОЗА о пути, не команда
}
# Путь в фикстурах ВЫВОДИТСЯ от живого контейнера, а не впечатан (карточка #248):
# впечатанный `C:\guts\.atlas` — диск автора в публичном образце. Фикстуре нужен живой
# абсолютный путь ИМЕННО ЭТОЙ машины (признаки судят исполнимость здесь), и у чужого
# контура он свой — с меткой самопроверка одинаково честна на любой машине.
_CONT = mezo_paths.container_root().as_posix()
SAMPLES = {k: v.replace("{CONT_B2}", _CONT.replace("/", "\\\\")).replace("{CONT}", _CONT)
           for k, v in SAMPLES.items()}
EXPECT = {"dirty_bare.py": 1, "dirty_rel_db.py": 2, "clean_computed.py": 0, "tombstone.py": 0,
          "dirty_tomb_next_line.py": 1,          # #151: соседнее надгробие НЕ гасит
          "dirty_broken_path.py": 1, "dirty_backslash.py": 1,
          "dirty_other_tool.py": 1, "clean_other_tool.py": 0, "clean_prose_tool.py": 0}


def selftest():
    import tempfile
    tmp = mezo_stand.new("guard-printed-")
    (tmp / "scripts").mkdir()
    for name, body in SAMPLES.items():
        (tmp / "scripts" / name).write_text(body, encoding="utf-8")
    arts = tmp / "generated"
    arts.mkdir()
    (arts / "sync.coord.md").write_text(
        "Актуальный статус — в БД, зови:\n`python .mezosync/scripts/read-messages.py "
        "--db <db> --role COORD`\n", encoding="utf-8")
    known = {p.name for p in (tmp / "scripts").glob("*.py")}
    ok = True
    for name, want in EXPECT.items():
        hits = scan_py(tmp / "scripts" / name, known, tmp / "scripts")
        got = sum(1 for _, _, k, _ in hits if not k.startswith("🟢"))   # 🟢 = норма, не находка
        good = got == want
        ok &= good
        print(f"{'✅' if good else '🔴'} {name:20} находок {got}, ожидалось {want}"
              + ("" if good else "  ⇐ " + "; ".join(k for _, _, k, _ in hits)))
    # витрина БЕЗ шаблонов генератора = «считаем всё» (прежнее поведение);
    # с шаблонами — только порождённое им. Проверяем ОБА, иначе разделение недоказано.
    md_all = scan_md(arts / "sync.coord.md", known)
    good = len(md_all) == 2                        # относительный путь + --db
    ok &= good
    print(f"{'✅' if good else '🔴'} файл .md из базы, без шаблонов  находок {len(md_all)}, ожидалось 2")
    scan_md.quoted = 0
    md_tpl = scan_md(arts / "sync.coord.md", known, [re.compile(r"НИЧЕГО НЕ СОВПАДЁТ")])
    good = len(md_tpl) == 0 and scan_md.quoted == 2
    ok &= good
    print(f"{'✅' if good else '🔴'} файл .md из базы, цитата в теле  долг {len(md_tpl)} (ждём 0), "
          f"цитат {scan_md.quoted} (ждём 2) — история не долг")
    # ── КАНОН (#56): три образца — чистый · без определения · мёртвое определение.
    scripts_dir = tmp / "scripts"
    live_root = str(scripts_dir).replace("\\", "/")
    canon_cases = [
        ("канон: сокращение объявлено и живо — чисто", 0,
         f"Зови так (`<s>` = `{live_root}`):\n    python <s>/read-messages.py --role X\n"),
        ("канон: сокращение НЕ объявлено — красное (читатель получит мёртвую команду)", 1,
         "Зови так:\n    python <s>/read-messages.py --role X\n"),
        ("канон: определение ведёт в НЕСУЩЕСТВУЮЩЕЕ место — красное (протухший ключ)", 1,
         f"Зови так (`<s>` = `{live_root}-нет-такого`):\n    python <s>/read-messages.py --role X\n"),
    ]
    for j, (title, want, body) in enumerate(canon_cases):
        cpath = tmp / f"canon{j}.md"
        cpath.write_text(body, encoding="utf-8")
        chits = scan_canon(cpath, known, scripts_dir)
        got = sum(1 for _, _, k, _ in chits if k.startswith("🔴"))
        good = got == want
        ok &= good
        print(f"{'✅' if good else '🔴'} {title}  находок {got}, ожидалось {want}"
              + ("" if good else "  ⇐ " + "; ".join(k for _, _, k, _ in chits)))

    print(f"\n{'✅ ГАРД ЧУВСТВИТЕЛЕН' if ok else '🔴 ГАРД СЛЕП ИЛИ ШУМИТ'} — краснеет на "
          f"{sum(1 for v in EXPECT.values() if v)} грязных образцах, молчит на чистом и на надгробии")
    print(f"   образцы оставлены: {tmp}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true", help="доказать, что гард умеет краснеть")
    ap.add_argument("--scripts", default=str(LIVE_SCRIPTS))
    ap.add_argument("--artifacts", default=str(LIVE_ARTIFACTS))
    ap.add_argument("--canon", default=str(mezo_paths.container_root() / "CLAUDE.md"),
                    help="канон контейнера — самая читаемая учащая поверхность (#56). "
                         "Глобальный CLAUDE.md пользователя НЕ сканируется — граница вслух")
    ap.add_argument("--no-run", action="store_true",
                    help="не прогонять скрипты (без наблюдения шаблоны судить нечем)")
    ap.add_argument("--role", default="PROTO", help="роль для read-only прогона read-phoenix")
    ap.add_argument("--db", default=str(mezo_paths.live_db()),
                    help="живая БД — источник СВОДА ПРАВИЛ (rules.body, active; с 27.08)")
    ap.add_argument("--no-rules", action="store_true", help="свод правил не судить")
    ap.add_argument("--tasks-dir", default=str(Path.home() / ".claude" / "scheduled-tasks"),
                    help="наказы-файлы планировщика (<задача>/SKILL.md; с 27.08). Наказы "
                         "в стенограммах сессий НЕ судятся — граница вслух")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    rc = run(Path(a.scripts), Path(a.artifacts), do_run=not a.no_run, role=a.role)
    # ── КАНОН: отдельной секцией ПОСЛЕ основного прогона, со своим счётом.
    canon = Path(a.canon)
    known = {p.name for p in Path(a.scripts).glob("*.py")}
    hits = scan_canon(canon, known, Path(a.scripts))
    if hits is None:
        print(f"⚠️ КАНОН НЕ НАЙДЕН: {canon} — НЕ ПРОВЕРЕН (это не «чисто»)")
    else:
        red = [(n, k, f) for n, _, k, f in hits if k.startswith("🔴")]
        for n, k, f in red:
            print(f"── КАНОН {canon.name}:{n}\n   [R1] {k}\n      {f[:110]}")
        print(f"{'🔴' if red else '✅'} канон {canon.name}: 🔴 {len(red)} "
              f"(сокращения, объявленные в файле, раскрыты перед судом; "
              f"глобальный CLAUDE.md пользователя НЕ сканирован)")
        rc = 1 if red else rc

    # ── СВОД ПРАВИЛ: секцией после канона. Без канона НЕ судится — суд без словаря
    # сокращений выдаёт ложные красные за находки (замерено 27.08: 2), а ложная находка
    # дороже пропуска: перестают верить проверке целиком.
    defs = canon_defs(canon)
    if a.no_rules:
        print("⚠️ СВОД ПРАВИЛ ПРОПУЩЕН по --no-rules — НЕ ПРОВЕРЕН (это не «чисто»)")
    elif defs is None:
        print("⛔ СВОД ПРАВИЛ НЕ СУЖДЕН: канона нет, словаря сокращений нет — суд дал бы "
              "ложные красные. НЕ ПРОВЕРЕН ≠ чисто")
        rc = max(rc, 1)
    else:
        rhits, inactive, tombstoned, err = scan_rules(a.db, known, Path(a.scripts), defs)
        if rhits is None:
            print(f"⛔ СВОД ПРАВИЛ НЕ ПРОВЕРЕН: база недоступна ({err}) — это не «чисто»")
            rc = max(rc, 1)
        else:
            rred = [(w, k, f) for w, k, f in rhits if k.startswith("🔴")]
            ryel = [(w, k, f) for w, k, f in rhits if k.startswith("🟡")]
            for w, k, f in rred + ryel:
                print(f"── СВОД {w}\n   [R1] {k}\n      {f[:110]}")
            print(f"{'🔴' if rred else '✅'} свод правил: 🔴 {len(rred)} · 🟡 {len(ryel)} "
                  f"(судились active; отозвано/замещено: {inactive} — история, долг не считается; "
                  f"погашено надгробием в той же строке: {tombstoned})")
            rc = 1 if rred else rc

    # ── НАКАЗЫ-ФАЙЛЫ: судятся ТЕМ ЖЕ судом (сокращения + швы), что и свод.
    tdir = Path(a.tasks_dir)
    thits = scan_tasks(tdir, known, Path(a.scripts), defs)
    if thits is None:
        print(f"⚠️ НАКАЗЫ-ФАЙЛЫ НЕ ПРОВЕРЕНЫ: нет каталога {tdir} (это не «чисто»)")
    else:
        tred = [(w, k, f) for w, k, f in thits if k.startswith("🔴")]
        tyel = [(w, k, f) for w, k, f in thits if k.startswith("🟡")]
        for w, k, f in tred + tyel:
            print(f"── НАКАЗ {w}\n   [R1] {k}\n      {f[:110]}")
        print(f"{'🔴' if tred else '✅'} наказы-файлы: 🔴 {len(tred)} · 🟡 {len(tyel)} "
              f"(наказы в стенограммах сессий НЕ судятся — файлом не правятся)")
        rc = 1 if tred else rc
    return rc


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
