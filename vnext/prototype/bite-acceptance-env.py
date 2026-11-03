#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА check-acceptance-env.py (карточка #613 ②).

Предмет: check-acceptance-env.py обязан находить subprocess-вызов инструмента контура
БЕЗ env= закреплённого стенда — и НЕ находить: правильно закреплённый вызов, вызов
с разрешающим комментарием на строке, вызов к инструменту, который контур не читает.

Случаи (различающий = проверка обязана ответить ИНАЧЕ, а не одинаково):
  ① вызов БЕЗ env= к инструменту контура ......... НАХОДКА              РАЗЛИЧАЮЩИЙ
  ② env=mezo_stand.stand_env(d) .................. НЕ находка (контроль)
  ③ env=dict(os.environ) (протекает) .............. НАХОДКА              РАЗЛИЧАЮЩИЙ
  ④ БЕЗ env=, но со строкой-разрешением `# env: caller — …` .. ПРОЩЕНО, не находка
  ⑤ цель — инструмент, контур НЕ читающий ......... НЕ находка (само не сканируется)
  Р1 обратный ход: строка-разрешение ОСЛЕПЛЕНА в копии проверки — ④ становится находкой
     (доказывает, что механизм комментария-разрешения — не украшение, а часть проверки)

Доработка PROTO (реестр известного долга acceptance-env-debt.txt, тот же приход #613):
  а) записанная в реестре находка .................. НЕ провал, считается в долге     РАЗЛИЧАЮЩИЙ
  б) новый вызов В ТОЙ ЖЕ файле, но в ДРУГОЙ функции — не в реестре ...... ПРОВАЛ      РАЗЛИЧАЮЩИЙ
  в) в реестре записано 2, живых стало 1 ........... «долг уменьшился», код 0          РАЗЛИЧАЮЩИЙ
  г) НАРОЧНАЯ ПОЛОМКА (в копии проверки): сверка с реестром — только по имени файла,
     без функции/инструмента — случай (б) на такой копии ПРОХОДИТ (не находит новый
     вызов) ⇒ доказывает, что точность ключа реестра — не украшение
  з) вызов записан реестром разрядом «законно» ....... НЕ провал и НЕ долг           РАЗЛИЧАЮЩИЙ
  и) НАРОЧНАЯ ПОЛОМКА (в копии проверки): реестр покрывает только «долг» — (з) снова
     провал ⇒ законное, записанное реестром вместо комментария, держится именно этим

Реестра рядом нет (контур, собранный из пакета GORDI — доработка PROTO 2026-09-14):
  д) реестра по умолчанию нет ......................... «⚠️» с числом находок, код 0    РАЗЛИЧАЮЩИЙ
  е) --debt-list указывает на несуществующий файл ...... отказ, код 2                   РАЗЛИЧАЮЩИЙ
  ж) НАРОЧНАЯ ПОЛОМКА (в копии проверки): ветка «реестра нет» отключена — (д) на такой
     копии снова даёт провал (код 1) ⇒ общий прогон в новом контуре держит именно она
  Случаи ①–⑤ и Р1 судят РАЗБОР, а не реестр, — поэтому зовут проверку с --no-debt-list:
  без реестра по умолчанию она теперь не провалилась бы.

Интерпретатор в переменной (возврат COORD по карточке #613, записка #5267):
  к) PY = sys.executable → subprocess.run([PY, TOOL, …]) ........ НАХОДКА              РАЗЛИЧАЮЩИЙ
  л) cmd = [sys.executable, TOOL, …] → subprocess.run(cmd) ...... НАХОДКА              РАЗЛИЧАЮЩИЙ
  м) своя обёртка run(cmd, d) с env стенда внутри, снаружи cmd с интерпретатором — НЕ находка
  Поломки (в копии проверки), у каждой приманки своя: «имя внутри списка не прослеживается»
  — (к) пропадает, (л) остаётся; «голое имя-аргумент не прослеживается» — (л) пропадает,
  (к) остаётся; «обёртка run(…) прослеживается как subprocess» — (м) становится находкой.

Корень стенда, ведущий в живой контур (карточка #613, слово владельца 2026-11-02 14:21:16 UTC,
просьба COORD — записка #6232). Случай (с) — НЕ поломка m1c из записки #6235, как было написано
здесь до PR 74: та была корнем строкой-путём к живому контуру, это форма q01 ниже:
  с) env=mezo_stand.stand_env(mezo_paths.container_root()) .............. НАХОДКА, причина названа   РАЗЛИЧАЮЩИЙ
  т) корень — предок __file__ через два имени (HERE → root → env) ....... НАХОДКА                     РАЗЛИЧАЮЩИЙ
  у) поверх stand_env(d) — env.update(MEZO_CONTAINER=os.environ.get(…)) .. НАХОДКА                     РАЗЛИЧАЮЩИЙ
  ф) встречный: подкаталог рядом с приёмкой (`… / "sandbox"`) и стенд mezo_stand.new — НЕ находка
  ш) поверх stand_env(d) — env["MEZO_CONTAINER"] = os.environ["MEZO_CONTAINER"] ...... НАХОДКА   РАЗЛИЧАЮЩИЙ
  щ) поверх stand_env(d) — env.update({"MEZO_CONTAINER": str(container_root())}) .... НАХОДКА   РАЗЛИЧАЮЩИЙ
  Поломки (в копии проверки), у каждой приманки своя: «корень стенда не судится» — (с)(т)(у)(ш)(щ),
  а с PR 74 и q01–q07 со встречными z07-бис и z07-тер пропадают, (ф) не меняется; «имя не прослеживается» — (т) пропадает, (с) остаётся;
  «подкаталог не обрывает цепочку предков» — (ф) становится находкой.
  По поломке на каждое основание (просьба COORD, записка #6239):
  «помощники mezo_paths не судятся» — (с)(щ) пропадают, (т)(у)(ш) остаются;
  «__file__ не судится» — (т) пропадает, (с)(у) остаются;
  «имя MEZO_CONTAINER не узнаётся» — (у)(ш)(щ) пропадают, (с)(т) остаются.
  И на каждый путь поверх готовой среды: «ключ env["MEZO_CONTAINER"] не прослеживается» — (ш)
  пропадает, (у)(щ) остаются; «словарь в .update() не прослеживается» — (щ) пропадает, (у)(ш) остаются.

Семь форм q01–q07 и ложная находка z07 (слово владельца 2026-11-03 09:14:10 UTC в чате COORD
«Судить все семь», записка #6243; формы — из проб COORD к PR 72):
  q01 корень строкой-путём к живому контуру (так сделана поломка m1c) ............ НАХОДКА   РАЗЛИЧАЮЩИЙ
  q02 from mezo_paths import container_root as croot → stand_env(croot()) .......... НАХОДКА   РАЗЛИЧАЮЩИЙ
  q03 env={**stand_env(d), "MEZO_CONTAINER": …} ..................................... НАХОДКА   РАЗЛИЧАЮЩИЙ
  q04 env=dict(stand_env(d), MEZO_CONTAINER=…) ...................................... НАХОДКА   РАЗЛИЧАЮЩИЙ
  q05 env = stand_env(d); env = {**env, "MEZO_CONTAINER": …} ........................ НАХОДКА   РАЗЛИЧАЮЩИЙ
  q06 env = stand_env(d); env |= {"MEZO_CONTAINER": …} .............................. НАХОДКА   РАЗЛИЧАЮЩИЙ
  q07 корень — рабочий каталог: Path.cwd() · os.getcwd() · Path() ................... НАХОДКИ   РАЗЛИЧАЮЩИЙ
  z07 root = container_root(); root = mezo_stand.new(…); stand_env(root) ............ НЕ находка (снята)   РАЗЛИЧАЮЩИЙ
  встречные: z07-бис — вложенное присваивание после прямого, z07-тер — имя через само себя:
  НАХОДКИ; z08 — вставка стенда поверх стенда, z09 — пустая строка: НЕ находки.
  Поломки (в копии проверки), по одной на форму, у каждой пропадает своя, а соседняя остаётся:
  «строка-путь не судится» — q01, остаются (с) и q07; «псевдоним не узнаётся» — q02, остаётся (с);
  «словарь {…} не судится» — q03 q05 q06, остаются q04 и (щ); «dict(…) не судится» — q04, остаётся q03;
  «судится только первое env = …» — q05, остаются q06 (т) (у); «env |= не судится» — q06, остаётся q05;
  «cwd() и getcwd() не судятся» — они, остаются Path() и (с); «Path() не судится» — Path(), остаются
  cwd() и getcwd(); «судится любое присваивание имени» (как в PR 72) — z07 снова находка, z07-бис
  и z07-тер остаются; «вложенное после прямого не судится» — z07-бис пропадает, z07-тер остаётся.
  У z07-тер своей поломки нет: ни одна поломка разбора доходящих присваиваний его не роняет.
  Он держит только одно — что снятие z07 не ослепило проверку на имени, переприсвоенном через себя.

Команда из возврата функции q11 (слово владельца 2026-11-03 13:40:44 UTC в чате COORD «Все три одним
PR 75», записка #6247; живой образец — direct_answers в bite-launcher-forms.py, команду ему собирает
build_argv из guard-launcher-forms.py):
  q11 свой помощник: argv = make_cmd(…) → subprocess.run(argv), make_cmd возвращает argv ...... НАХОДКА   РАЗЛИЧАЮЩИЙ
  q11 помощник соседнего файла: subprocess.run(helper.build_cmd(…)) ............................ НАХОДКА   РАЗЛИЧАЮЩИЙ
  встречные — НЕ находки: помощник возвращает git · env стенда на месте · своё одноимённое
  определение возвращает git (соседнее build_cmd — интерпретатор) · помощник возвращает итог прогона.
  Поломки (в копии проверки), у каждой приманки своя: «команда из возврата не судится» — обе находки
  пропадают, (к)(л) остаются; «своё определение не главнее чужого» — встречный с git становится находкой;
  «имя в return не прослеживается» — свой помощник пропадает, соседний остаётся; «итог прогона
  считается командой» — встречный out = run_tool(…).stdout → git становится находкой.

Нулевой день контура (заявка 29 пакета): реестра рядом нет у свежесобранного контура — это свойство
нового контура, «ℹ️», а не «⚠️». Контур для этих случаев СОБИРАЕТСЯ из пакета сборщиком init-group.py
(так же, как у bite-fresh-circuit.py), а не рисуется рукой: признак читается из ленты настоящей базы.
  н) свежий контур (в ленте нет записок), реестра нет ... «ℹ️ … свойство нового контура», ни одного «⚠️»  РАЗЛИЧАЮЩИЙ
  о) ТОТ ЖЕ контур, но в ленте одна записка ................ «⚠️», как было, ни одного «ℹ️»                  РАЗЛИЧАЮЩИЙ
  п) НАРОЧНАЯ ПОЛОМКА (в копии проверки): нулевой день не различается — (н) на такой копии
     краснеет, а (о) остаётся зелёным ⇒ красит РОВНО (н). Копия с поломкой кладётся в каталог
     из переменной MEZO_BREAKS_DIR (если задана), иначе — в стенд, который убирается при успехе.
  р) встречный к месту: та же копия, но с реестром РЯДОМ (как у живого контура) — строки
     «реестра рядом нет» нет вовсе. Проверка ищет реестр рядом с СОБОЙ, поэтому (н)(о) судят
     КОПИЮ без реестра рядом, а не файл рядом с приёмкой: в живом контуре реестр лежит рядом
     с проверкой, и ветка нулевого дня там не наступает (замер 2026-10-06 12:48 UTC в Atlas:
     (н)(о) провалились на исправной проверке — судили место, а не нулевой день).

Остальная часть — своя песочница: копия check-acceptance-env.py + синтетический стенд. Живой контур
не трогает — все файлы синтетические, живая база не открывается вовсе (контур нулевого дня — свой,
во временном каталоге).
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
import mezo_paths  # noqa: E402

REAL_CHECK = Path(__file__).resolve().parent / "check-acceptance-env.py"
CASES = DIFFER = 0


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


FAKE_CONTAINER_TOOL = '''# -*- coding: utf-8 -*-
"""fake-container-tool.py — синтетика приёмки #613, притворяется читающим контур."""
import mezo_paths  # noqa: F401 — этого хватает, чтобы reads_container() ответил True
'''

FAKE_EXTERNAL_TOOL = '''# -*- coding: utf-8 -*-
"""fake-external-tool.py — синтетика приёмки #613: контур НЕ читает."""
print("я контур не читаю")
'''

BITE_CASE1_NO_ENV = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True)
'''

BITE_CASE2_PINNED = '''import subprocess, sys
from pathlib import Path
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call(d):
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True,
                   env=mezo_stand.stand_env(d))
'''

BITE_CASE3_LEAK_DICT = '''import os, subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    env = dict(os.environ)
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True, env=env)
'''

BITE_CASE4_EXCUSED = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True)  # env: caller — тестовая причина случая 4
'''

BITE_CASE5_INDIFFERENT = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-external-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--x"], capture_output=True)
'''

# ── синтетика случаев (к)(л)(м): интерпретатор в переменной (возврат COORD, записка #5267) ──
BITE_CASE9_PY_VAR = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")
PY = sys.executable


def call():
    subprocess.run([PY, TOOL, "--db", "x"], capture_output=True)
'''

BITE_CASE10_CMD_VAR = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    cmd = [sys.executable, TOOL, "--db", "x"]
    subprocess.run(cmd, capture_output=True)
'''

BITE_CASE11_WRAPPER = '''import subprocess, sys
from pathlib import Path
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def run(cmd, d):
    return subprocess.run(cmd, capture_output=True, env=mezo_stand.stand_env(d))


def call(d):
    cmd = [sys.executable, TOOL, "--db", "x"]
    run(cmd, d)
'''

# ── синтетика случаев (с)(т)(у)(ф): корень стенда ведёт в живой контур (карточка #613) ──
BITE_CASE12_LIVE_ROOT = '''import subprocess, sys
from pathlib import Path
import mezo_paths
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True,
                   env=mezo_stand.stand_env(mezo_paths.container_root()))
'''

BITE_CASE13_FILE_ANCESTOR = '''import subprocess, sys
from pathlib import Path
import mezo_stand
HERE = Path(__file__).resolve().parent
TOOL = str(HERE / "fake-container-tool.py")


def call():
    root = HERE.parent
    env = mezo_stand.stand_env(root, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True, env=env)
'''

BITE_CASE14_ENV_OVERRIDE = '''import os, subprocess, sys
from pathlib import Path
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call(d):
    env = mezo_stand.stand_env(d)
    env.update(MEZO_CONTAINER=os.environ.get("MEZO_CONTAINER", ""))
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True, env=env)
'''

BITE_CASE15_NOT_LIVE = '''import subprocess, sys
from pathlib import Path
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call_sandbox():
    sandbox = Path(__file__).resolve().parent / "sandbox"
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True,
                   env=mezo_stand.stand_env(sandbox))


def call_new():
    root = mezo_stand.new("bite-case15-")
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True,
                   env=mezo_stand.stand_env(root))
'''

BITE_CASE16_ENV_KEY = '''import os, subprocess, sys
from pathlib import Path
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call(d):
    env = mezo_stand.stand_env(d)
    env["MEZO_CONTAINER"] = os.environ["MEZO_CONTAINER"]
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True, env=env)
'''

BITE_CASE17_UPDATE_DICT = '''import subprocess, sys
from pathlib import Path
import mezo_paths
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call(d):
    env = mezo_stand.stand_env(d)
    env.update({"MEZO_CONTAINER": str(mezo_paths.container_root())})
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True, env=env)
'''

# ── синтетика семи форм q01–q07 и снятой ложной находки z07 (слово владельца 2026-11-03
#    09:14:10 UTC в чате COORD «Судить все семь», записка #6243; формы — из проб COORD) ──
SEVEN_HEAD = '''import os, subprocess, sys
from pathlib import Path
import mezo_paths
import mezo_stand
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")
'''
SEVEN_RUN = 'subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True, env={env})'
SEVEN_CASES = {
    # q01 — так была сделана поломка m1c из записки #6235: корень строкой-путём к живому контуру
    "bite-case18-str-path.py": "\ndef call():\n    " + SEVEN_RUN.format(
        env='mezo_stand.stand_env(r"C:\\guts\\.atlas")') + "\n",
    "bite-case19-alias.py": "from mezo_paths import container_root as croot\n\ndef call():\n    "
        + SEVEN_RUN.format(env="mezo_stand.stand_env(croot())") + "\n",
    "bite-case20-dict-literal.py": "\ndef call(d):\n    " + SEVEN_RUN.format(
        env='{**mezo_stand.stand_env(d), "MEZO_CONTAINER": str(mezo_paths.container_root())}') + "\n",
    "bite-case21-dict-call.py": "\ndef call(d):\n    " + SEVEN_RUN.format(
        env="dict(mezo_stand.stand_env(d), MEZO_CONTAINER=str(mezo_paths.container_root()))") + "\n",
    "bite-case22-reassign-merge.py": "\ndef call(d):\n    env = mezo_stand.stand_env(d)\n"
        '    env = {**env, "MEZO_CONTAINER": str(mezo_paths.container_root())}\n    '
        + SEVEN_RUN.format(env="env") + "\n",
    "bite-case23-ior.py": "\ndef call(d):\n    env = mezo_stand.stand_env(d)\n"
        '    env |= {"MEZO_CONTAINER": str(mezo_paths.container_root())}\n    '
        + SEVEN_RUN.format(env="env") + "\n",
    "bite-case24-cwd.py": "\ndef call():\n    " + SEVEN_RUN.format(env="mezo_stand.stand_env(Path.cwd())") + "\n",
    "bite-case25-getcwd.py": "\ndef call():\n    " + SEVEN_RUN.format(env="mezo_stand.stand_env(os.getcwd())") + "\n",
    "bite-case26-path-noargs.py": "\ndef call():\n    " + SEVEN_RUN.format(env="mezo_stand.stand_env(Path())") + "\n",
    # z07 — ложная находка PR 72: имя переприсвоено стенду прямо перед вызовом
    "bite-case27-reassigned.py": "\ndef call():\n    root = mezo_paths.container_root()\n"
        "    root = mezo_stand.new('bite-case27-')\n    " + SEVEN_RUN.format(env="mezo_stand.stand_env(root)") + "\n",
    # встречные к снятию z07: вложенное присваивание после прямого и имя через само себя
    "bite-case28-nested-after.py": "\ndef call(flag):\n    root = mezo_stand.new('bite-case28-')\n"
        "    if flag:\n        root = mezo_paths.container_root()\n    "
        + SEVEN_RUN.format(env="mezo_stand.stand_env(root)") + "\n",
    "bite-case29-self-ref.py": "\ndef call():\n    root = mezo_paths.container_root()\n"
        "    root = Path(root).parent\n    " + SEVEN_RUN.format(env="mezo_stand.stand_env(root)") + "\n",
    # встречные к суду вставок и строк: вставка стенда поверх стенда и пустая строка
    "bite-case30-dict-stand.py": "\ndef call(d):\n    st = mezo_stand.new('bite-case30-')\n    "
        + SEVEN_RUN.format(env='{**mezo_stand.stand_env(d), "MEZO_CONTAINER": str(st)}') + "\n",
    "bite-case31-empty-str.py": "\ndef call(d):\n    env = mezo_stand.stand_env(d)\n"
        '    env.update(MEZO_CONTAINER="")\n    ' + SEVEN_RUN.format(env="env") + "\n",
}

# ── синтетика q11: команда пришла возвратом функции (слово владельца 2026-11-03 13:40:44 UTC
#    в чате COORD «Все три одним PR 75», записка #6247; живой образец — direct_answers
#    в bite-launcher-forms.py, команду ему собирает build_argv из guard-launcher-forms.py) ──
FAKE_CMD_HELPER = '''# -*- coding: utf-8 -*-
"""fake-cmd-helper.py — синтетика приёмки #613 (q11): соседний инструмент, чей помощник
возвращает команду с интерпретатором — как build_argv у guard-launcher-forms.py."""
import sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def build_cmd(db):
    return [sys.executable, TOOL, "--db", db]
'''
Q11_CASES = {
    # свой помощник, команда в возврате — именем, собранным в два шага (как у build_argv).
    # Имя у вызывающего НАРОЧНО другое: прежний след по именам ходит и в тела соседних функций
    # (модульный список операторов включает их), и при общем имени argv случай ловился бы
    # без суда q11 — поломки «команда из возврата не судится» его не роняли (прогон 14:10 UTC)
    "bite-case32-ret-local.py": "\ndef make_cmd(db):\n    argv = [sys.executable, TOOL]\n"
        '    argv += ["--db", db]\n    return argv\n\n\ndef call():\n    cmd = make_cmd("x")\n'
        "    subprocess.run(cmd, capture_output=True)\n",
    # помощник соседнего файла, вызов прямо в аргументе (как _glf().build_argv(…) у direct_answers)
    "bite-case33-ret-neighbour.py": '\ndef call(helper):\n    subprocess.run(helper.build_cmd("x"), capture_output=True)\n',
    # встречные: помощник возвращает git · команда из возврата, но env стенда на месте ·
    # своё одноимённое определение возвращает git (чужое build_cmd — интерпретатор) ·
    # помощник возвращает ИТОГ прогона, а не команду
    "bite-case34-ret-git.py": '\ndef git_cmd():\n    return ["git", "status", "--short"]\n\n\n'
        "def call():\n    subprocess.run(git_cmd(), capture_output=True)\n",
    "bite-case35-ret-pinned.py": '\ndef make_cmd(db):\n    return [sys.executable, TOOL, "--db", db]\n\n\n'
        'def call(d):\n    subprocess.run(make_cmd("x"), capture_output=True, env=mezo_stand.stand_env(d))\n',
    "bite-case36-ret-shadow.py": '\ndef build_cmd(db):\n    return ["git", "log", "--", db]\n\n\n'
        'def call():\n    subprocess.run(build_cmd("x"), capture_output=True)\n',
    "bite-case37-ret-run.py": '\ndef run_tool(db):\n    return subprocess.run([sys.executable, TOOL, "--db", db], '
        "capture_output=True,\n                          env=mezo_stand.stand_env(Path(db).parent))\n\n\n"
        'def call():\n    out = run_tool("x").stdout\n'
        '    subprocess.run(["git", "commit", "-m", out], capture_output=True)\n',
}

# ── синтетика случаев (а)-(г): реестр известного долга ──────────────────────────────
BITE_CASE6_RECORDED = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call1():
    subprocess.run([sys.executable, TOOL, "--db", "x"], capture_output=True)


def call2():
    subprocess.run([sys.executable, TOOL, "--db", "y"], capture_output=True)
'''

BITE_CASE7_SHRUNK = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "z"], capture_output=True)
'''

BITE_CASE8_LEGIT = '''import subprocess, sys
from pathlib import Path
TOOL = str(Path(__file__).resolve().parent / "fake-container-tool.py")


def call():
    subprocess.run([sys.executable, TOOL, "--db", "w"], capture_output=True)
'''

DEBT_CONTENT = (
    "# синтетический реестр для приёмки bite-acceptance-env.py — НЕ деталь поставки\n"
    "vnext-tools/bite-case6-recorded.py :: call1 :: fake-container-tool :: 1 :: долг :: "
    "тестовая запись случаев (а)/(б)\n"
    "vnext-tools/bite-case7-shrunk.py :: call :: fake-container-tool :: 2 :: долг :: "
    "тестовая запись случая (в) — записано 2, живых 1\n"
    "vnext-tools/bite-case8-legit.py :: call :: fake-container-tool :: 1 :: законно :: "
    "тестовая запись случая (з) — законный вызов записан реестром, не комментарием\n"
)


def build_stand(checker_source: str):
    """Синтетический стенд: копия проверки (checker_source — возможно, ослеплённая) +
    её сосед mezo_paths.py + выдуманные vnext-tools/.mezosync/scripts с пятью случаями."""
    d = mezo_stand.new("bite-acceptance-env-")
    vt = d / "vnext-tools"
    ms = d / ".mezosync" / "scripts"
    vt.mkdir(parents=True, exist_ok=True)
    ms.mkdir(parents=True, exist_ok=True)
    (vt / "check-acceptance-env.py").write_text(checker_source, encoding="utf-8")
    (vt / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (vt / "mezo_stand.py").write_text(
        Path(mezo_stand.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (vt / "fake-container-tool.py").write_text(FAKE_CONTAINER_TOOL, encoding="utf-8")
    (vt / "fake-external-tool.py").write_text(FAKE_EXTERNAL_TOOL, encoding="utf-8")
    (vt / "bite-case1-no-env.py").write_text(BITE_CASE1_NO_ENV, encoding="utf-8")
    (vt / "bite-case2-pinned.py").write_text(BITE_CASE2_PINNED, encoding="utf-8")
    (vt / "bite-case3-leak-dict.py").write_text(BITE_CASE3_LEAK_DICT, encoding="utf-8")
    (vt / "bite-case4-excused.py").write_text(BITE_CASE4_EXCUSED, encoding="utf-8")
    (vt / "bite-case5-indifferent.py").write_text(BITE_CASE5_INDIFFERENT, encoding="utf-8")
    (vt / "bite-case9-py-var.py").write_text(BITE_CASE9_PY_VAR, encoding="utf-8")
    (vt / "bite-case10-cmd-var.py").write_text(BITE_CASE10_CMD_VAR, encoding="utf-8")
    (vt / "bite-case11-wrapper.py").write_text(BITE_CASE11_WRAPPER, encoding="utf-8")
    (vt / "bite-case12-live-root.py").write_text(BITE_CASE12_LIVE_ROOT, encoding="utf-8")
    (vt / "bite-case13-file-ancestor.py").write_text(BITE_CASE13_FILE_ANCESTOR, encoding="utf-8")
    (vt / "bite-case14-env-override.py").write_text(BITE_CASE14_ENV_OVERRIDE, encoding="utf-8")
    (vt / "bite-case15-not-live.py").write_text(BITE_CASE15_NOT_LIVE, encoding="utf-8")
    (vt / "bite-case16-env-key.py").write_text(BITE_CASE16_ENV_KEY, encoding="utf-8")
    (vt / "bite-case17-update-dict.py").write_text(BITE_CASE17_UPDATE_DICT, encoding="utf-8")
    for fname, body in SEVEN_CASES.items():
        (vt / fname).write_text(SEVEN_HEAD + body, encoding="utf-8")
    (vt / "fake-cmd-helper.py").write_text(FAKE_CMD_HELPER, encoding="utf-8")
    for fname, body in Q11_CASES.items():
        (vt / fname).write_text(SEVEN_HEAD + body, encoding="utf-8")
    return d


def build_debt_stand(checker_source: str, debt_content: str):
    """Стенд для случаев (а)-(г): копия проверки + реестр acceptance-env-debt.txt рядом
    с ней (путь по умолчанию — проверка ищет его САМА, без --debt-list) + два
    синтетических файла (case6 — две функции, одна в реестре; case7 — долг завышен)."""
    d = mezo_stand.new("bite-acceptance-env-debt-")
    vt = d / "vnext-tools"
    vt.mkdir(parents=True, exist_ok=True)
    (vt / "check-acceptance-env.py").write_text(checker_source, encoding="utf-8")
    (vt / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (vt / "fake-container-tool.py").write_text(FAKE_CONTAINER_TOOL, encoding="utf-8")
    (vt / "bite-case6-recorded.py").write_text(BITE_CASE6_RECORDED, encoding="utf-8")
    (vt / "bite-case7-shrunk.py").write_text(BITE_CASE7_SHRUNK, encoding="utf-8")
    (vt / "bite-case8-legit.py").write_text(BITE_CASE8_LEGIT, encoding="utf-8")
    (vt / "acceptance-env-debt.txt").write_text(debt_content, encoding="utf-8")
    return d


def call_checker(stand: Path, *extra):
    checker = stand / "vnext-tools" / "check-acceptance-env.py"
    return subprocess.run([sys.executable, str(checker), *extra],
                          capture_output=True, text=True, encoding="utf-8",
                          env=mezo_stand.stand_env(stand))


def run_checker_text(stand: Path, *extra):
    r = call_checker(stand, *extra)
    return r.stdout + r.stderr, r.returncode


def run_checker(stand: Path, *extra):
    r = call_checker(stand, "--json", *extra)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        data = {"ok": None, "findings": [], "excused": [], "_raw": (r.stdout + r.stderr)[:800]}
    return data, r.returncode


def names(entries, key="file"):
    return {Path(e[key]).name for e in entries}


def new_key_funcs(data, fname):
    """Имена функций из debt.new_keys, чей файл == fname (для случаев (а)/(б))."""
    return {row["function"] for row in data.get("debt", {}).get("new_keys", [])
            if Path(row["file"]).name == fname}


def shrunk_rows(data, fname):
    return [row for row in data.get("debt", {}).get("shrunk", [])
            if Path(row["file"]).name == fname]


# ── нулевой день контура (заявка 29 пакета): свежий контур собирается из пакета ───────────
def find_pack():
    """Корень пакета — теми же местами, что у bite-fresh-circuit.py; не нашёлся — None."""
    candidates = []
    try:
        candidates.append(mezo_paths.template_root())
    except SystemExit:
        pass
    here = Path(__file__).resolve().parent
    candidates += [here.parent.parent / "gordipack", here.parent / "gordipack"]
    return next((p for p in candidates if (p / "scripts" / "init-group.py").exists()), None)


def build_fresh_circuit(pack: Path):
    """Свежий контур — тем же сборщиком init-group.py, что у bite-fresh-circuit.py.

    → (корень контура, база или None, вывод сборщика). В каталог его скриптов кладётся ещё один
    синтетический вызов без env= (случай ① этой приёмки), чтобы находка была при ЛЮБОМ составе пакета:
    без находок проверка не печатает строку про реестр вовсе, и случай судил бы пустоту."""
    root = mezo_stand.new("bite-acceptance-env-fresh-")
    mez = root / ".mezosync"
    r = subprocess.run([sys.executable, str(pack / "scripts" / "init-group.py"), "--name", "bite",
                        "--path", str(mez), "--roles", "coord"],
                       capture_output=True, text=True, encoding="utf-8", timeout=300,
                       env=mezo_stand.stand_env(root))
    db = mez / "mezosync.db"
    if r.returncode == 0 and db.exists() and (mez / "scripts").is_dir():
        (mez / "scripts" / "fake-container-tool.py").write_text(FAKE_CONTAINER_TOOL, encoding="utf-8")
        (mez / "scripts" / "bite-case1-no-env.py").write_text(BITE_CASE1_NO_ENV, encoding="utf-8")
        return root, db, ""
    return root, None, ((r.stdout or "") + (r.stderr or ""))[-600:]


def breaks_dir(stand: Path, name: str) -> Path:
    """Куда класть копию инструмента с нарочной поломкой: <MEZO_BREAKS_DIR>/<имя>, а без переменной —
    внутрь стенда (он убирается при успехе). Так копию поломки можно предъявить глазами."""
    base = os.environ.get("MEZO_BREAKS_DIR")
    d = (Path(base) / name) if base else (stand / "breaks" / name)
    d.mkdir(parents=True, exist_ok=True)
    return d


def zero_day_verdicts(check: Path, container: Path, fresh_db: Path, used_db: Path):
    """Звать проверку НА ДВУХ базах одного контура — без записок в ленте и с одной запиской —
    и вернуть суждения (н) и (о) с подробностью. Звать её прямым вызовом, как зовёт общий прогон
    (без --no-debt-list и без --debt-list): ветка «реестра рядом нет» — именно она."""
    def run(db: Path):
        r = subprocess.run([sys.executable, str(check), "--db", str(db)],
                           capture_output=True, text=True, encoding="utf-8",
                           env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"))
        out = (r.stdout or "") + (r.stderr or "")
        lines = out.splitlines()
        marked = [l for l in lines if "реестра известного долга рядом нет" in l]
        return r.returncode, lines, marked

    rc_n, lines_n, marked_n = run(fresh_db)
    rc_o, lines_o, marked_o = run(used_db)
    fresh_ok = (rc_n == 0 and len(marked_n) == 1 and marked_n[0].startswith("ℹ️")
                and "свойство нового контура" in marked_n[0]
                and not any(l.startswith("⚠️") for l in lines_n))
    used_ok = (rc_o == 0 and len(marked_o) == 1 and marked_o[0].startswith("⚠️")
               and not any(l.startswith("ℹ️") for l in lines_o))
    return (fresh_ok, f"rc={rc_n} · строка про реестр: {marked_n[0][:90] if marked_n else '—'}"
                      f" · «⚠️»: {sum(l.startswith('⚠️') for l in lines_n)}",
            used_ok, f"rc={rc_o} · строка про реестр: {marked_o[0][:90] if marked_o else '—'}"
                     f" · «ℹ️»: {sum(l.startswith('ℹ️') for l in lines_o)}")


def main() -> int:
    if not REAL_CHECK.exists():
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {REAL_CHECK} не найден — приёмке нечего испытывать.")
    ok = True
    real_source = REAL_CHECK.read_text(encoding="utf-8")

    stand = build_stand(real_source)
    data, rc = run_checker(stand, "--no-debt-list")
    found = names(data.get("findings", []))
    excused = names(data.get("excused", []))

    ok &= case("① БЕЗ env= к инструменту контура — НАХОДКА",
               "bite-case1-no-env.py" in found,
               f"находки: {sorted(found)}", differ=True)
    ok &= case("② env=mezo_stand.stand_env(d) — НЕ находка (контроль)",
               "bite-case2-pinned.py" not in found and "bite-case2-pinned.py" not in excused,
               f"находки: {sorted(found)} · прощено: {sorted(excused)}")
    ok &= case("③ env=dict(os.environ) протекает — НАХОДКА",
               "bite-case3-leak-dict.py" in found,
               f"находки: {sorted(found)}", differ=True)
    ok &= case("④ БЕЗ env=, но со строкой-разрешением — ПРОЩЕНО, не находка",
               "bite-case4-excused.py" not in found and "bite-case4-excused.py" in excused,
               f"находки: {sorted(found)} · прощено: {sorted(excused)}", differ=True)
    ok &= case("⑤ цель контур не читает — не находка и не прощение (не сканируется вовсе)",
               "bite-case5-indifferent.py" not in found and "bite-case5-indifferent.py" not in excused,
               f"находки: {sorted(found)} · прощено: {sorted(excused)}", differ=True)
    ok &= case("итог: exit-код совпадает с наличием непрощённых находок",
               (rc != 0) == bool(data.get("findings")),
               f"rc={rc}, findings={len(data.get('findings', []))}")

    # ── (к)(л)(м) интерпретатор в переменной ─────────────────────────────────────────
    ok &= case("(к) PY = sys.executable → subprocess.run([PY, TOOL, …]) — НАХОДКА",
               "bite-case9-py-var.py" in found, f"находки: {sorted(found)}", differ=True)
    ok &= case("(л) cmd = [sys.executable, TOOL, …] → subprocess.run(cmd) — НАХОДКА",
               "bite-case10-cmd-var.py" in found, f"находки: {sorted(found)}", differ=True)
    ok &= case("(м) своя обёртка run(cmd, d) с env стенда внутри — НЕ находка (не считать дважды)",
               "bite-case11-wrapper.py" not in found, f"находки: {sorted(found)}", differ=True)
    anchor_frontier = "    frontier = bare + nested"
    anchor_wrapper = "    if not isinstance(call.func, ast.Attribute):\n        return False"
    for anchor_text, label in ((anchor_frontier, "прослеживание имён"), (anchor_wrapper, "обёртки")):
        if real_source.count(anchor_text) != 1:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь «{label}» найден {real_source.count(anchor_text)} раз")
    broken_k = build_stand(real_source.replace(
        anchor_frontier, "    frontier = bare  # ПОЛОМКА (к): имя внутри списка не прослеживается"))
    found_k = names(run_checker(broken_k, "--no-debt-list")[0].get("findings", []))
    ok &= case("(к) поломка «имя внутри списка не прослеживается»: (к) пропадает, (л) остаётся",
               "bite-case9-py-var.py" not in found_k and "bite-case10-cmd-var.py" in found_k,
               f"находки на копии: {sorted(found_k)}", differ=True)
    broken_l = build_stand(real_source.replace(
        anchor_frontier, "    frontier = nested  # ПОЛОМКА (л): голое имя-аргумент не прослеживается"))
    found_l = names(run_checker(broken_l, "--no-debt-list")[0].get("findings", []))
    ok &= case("(л) поломка «голое имя-аргумент не прослеживается»: (л) пропадает, (к) остаётся",
               "bite-case10-cmd-var.py" not in found_l and "bite-case9-py-var.py" in found_l,
               f"находки на копии: {sorted(found_l)}", differ=True)
    broken_m = build_stand(real_source.replace(
        anchor_wrapper, "    if False:  # ПОЛОМКА (м): обёртка прослеживается как subprocess\n        return False"))
    found_m = names(run_checker(broken_m, "--no-debt-list")[0].get("findings", []))
    ok &= case("(м) поломка «обёртка прослеживается как subprocess»: (м) становится находкой",
               "bite-case11-wrapper.py" in found_m,
               f"находки на копии: {sorted(found_m)}", differ=True)

    # ── (с)(т)(у)(ф) корень стенда ведёт в живой контур (карточка #613, записка #6232) ──────
    live = {Path(e["file"]).name: e.get("reason", "") for e in data.get("live_env", [])}
    ok &= case("(с) env=stand_env(mezo_paths.container_root()) — НАХОДКА, причина названа",
               "bite-case12-live-root.py" in found
               and "container_root" in live.get("bite-case12-live-root.py", ""),
               f"находки: {sorted(found)} · причина: {live.get('bite-case12-live-root.py', '—')}",
               differ=True)
    ok &= case("(т) корень — предок __file__ через два имени (HERE → root → env) — НАХОДКА",
               "bite-case13-file-ancestor.py" in found
               and "__file__" in live.get("bite-case13-file-ancestor.py", ""),
               f"причина: {live.get('bite-case13-file-ancestor.py', '—')}", differ=True)
    ok &= case("(у) поверх stand_env(d) — env.update(MEZO_CONTAINER=os.environ.get(…)) — НАХОДКА",
               "bite-case14-env-override.py" in found
               and "MEZO_CONTAINER" in live.get("bite-case14-env-override.py", ""),
               f"причина: {live.get('bite-case14-env-override.py', '—')}", differ=True)
    ok &= case("(ф) встречный: подкаталог рядом с приёмкой и стенд mezo_stand.new — НЕ находка",
               "bite-case15-not-live.py" not in found and "bite-case15-not-live.py" not in live,
               f"находки: {sorted(found)}")
    ok &= case('(ш) поверх stand_env(d) — env["MEZO_CONTAINER"] = os.environ[…] — НАХОДКА',
               "bite-case16-env-key.py" in found
               and "MEZO_CONTAINER" in live.get("bite-case16-env-key.py", ""),
               f"причина: {live.get('bite-case16-env-key.py', '—')}", differ=True)
    ok &= case('(щ) поверх stand_env(d) — env.update({"MEZO_CONTAINER": str(container_root())}) — НАХОДКА',
               "bite-case17-update-dict.py" in found
               and "container_root" in live.get("bite-case17-update-dict.py", ""),
               f"причина: {live.get('bite-case17-update-dict.py', '—')}", differ=True)
    anchor_judge = "                live_reason = env_live_reason(node, scopes, module_stmts)"
    anchor_links = "            if links <= 0:\n                return None"
    anchor_chain = '        if isinstance(node, ast.Attribute) and node.attr == "parent":'
    anchor_helpers = 'LIVE_PATH_CALLS = {"container_root", "live_db", "live_scripts"}'
    anchor_file = '            if node.id == "__file__":'
    anchor_var = "    return isinstance(node, ast.Constant) and node.value == CONTAINER_VAR"
    anchor_key = "            and target.value.id == env_name and is_container_var(target.slice))"
    anchor_dict = "                    if isinstance(arg, ast.Dict):"
    for anchor_text, label in ((anchor_judge, "суда корня"), (anchor_links, "прослеживания имени"),
                               (anchor_chain, "цепочки предков"), (anchor_helpers, "помощников mezo_paths"),
                               (anchor_file, "__file__"), (anchor_var, "имени MEZO_CONTAINER"),
                               (anchor_key, "ключа среды"), (anchor_dict, "словаря в .update()")):
        if real_source.count(anchor_text) != 1:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь «{label}» найден {real_source.count(anchor_text)} раз")
    c_root, c_file, c_upd = ("bite-case12-live-root.py", "bite-case13-file-ancestor.py",
                             "bite-case14-env-override.py")
    c_key, c_dict = "bite-case16-env-key.py", "bite-case17-update-dict.py"
    q01, q02, q03, q04 = ("bite-case18-str-path.py", "bite-case19-alias.py",
                          "bite-case20-dict-literal.py", "bite-case21-dict-call.py")
    q05, q06 = "bite-case22-reassign-merge.py", "bite-case23-ior.py"
    q07_cwd = ("bite-case24-cwd.py", "bite-case25-getcwd.py")
    q07_empty = "bite-case26-path-noargs.py"
    z07, z07b, z07c = "bite-case27-reassigned.py", "bite-case28-nested-after.py", "bite-case29-self-ref.py"
    z08, z09 = "bite-case30-dict-stand.py", "bite-case31-empty-str.py"
    seven_live = (q01, q02, q03, q04, q05, q06, *q07_cwd, q07_empty, z07b, z07c)
    live_cases = (c_root, c_file, c_upd, c_key, c_dict, *seven_live)
    broken_x = build_stand(real_source.replace(
        anchor_judge, "                live_reason = None  # ПОЛОМКА (х): корень стенда не судится"))
    found_x = names(run_checker(broken_x, "--no-debt-list")[0].get("findings", []))
    ok &= case("(х) поломка «корень стенда не судится»: (с)(т)(у)(ш)(щ), q01–q07 и встречные z07 пропадают, "
               "(ф) не меняется",
               not any(n in found_x for n in live_cases) and "bite-case15-not-live.py" not in found_x,
               f"находки на копии: {sorted(found_x)}", differ=True)
    broken_c = build_stand(real_source.replace(
        anchor_links, "            if True:  # ПОЛОМКА (ц): имя не прослеживается\n                return None"))
    found_c = names(run_checker(broken_c, "--no-debt-list")[0].get("findings", []))
    ok &= case("(ц) поломка «имя не прослеживается»: (т) пропадает, (с) остаётся",
               "bite-case13-file-ancestor.py" not in found_c and "bite-case12-live-root.py" in found_c,
               f"находки на копии: {sorted(found_c)}", differ=True)
    broken_ch = build_stand(real_source.replace(
        anchor_chain, "        if isinstance(node, ast.BinOp):  # ПОЛОМКА (ч): подкаталог не обрывает цепочку\n"
                      "            node = node.left\n            continue\n" + anchor_chain))
    found_ch = names(run_checker(broken_ch, "--no-debt-list")[0].get("findings", []))
    ok &= case("(ч) поломка «подкаталог не обрывает цепочку предков»: (ф) становится находкой",
               "bite-case15-not-live.py" in found_ch,
               f"находки на копии: {sorted(found_ch)}", differ=True)

    def broken_found(anchor_text, replacement):
        return names(run_checker(build_stand(real_source.replace(anchor_text, replacement)),
                                 "--no-debt-list")[0].get("findings", []))

    def gone_kept(found_b, gone, kept):
        return all(n not in found_b for n in gone) and all(n in found_b for n in kept)

    # по поломке на каждое основание «ведёт в живой контур» (просьба COORD, записка #6239)
    found_y = broken_found(anchor_helpers, "LIVE_PATH_CALLS = set()  # ПОЛОМКА (ы): помощники mezo_paths не судятся")
    ok &= case("(ы) поломка «помощники mezo_paths не судятся»: (с)(щ) пропадают, (т)(у)(ш) остаются",
               gone_kept(found_y, (c_root, c_dict), (c_file, c_upd, c_key)),
               f"находки на копии: {sorted(found_y)}", differ=True)
    found_e = broken_found(anchor_file, "            if False:  # ПОЛОМКА (э): __file__ не судится")
    ok &= case("(э) поломка «__file__ не судится»: (т) пропадает, (с)(у) остаются",
               gone_kept(found_e, (c_file,), (c_root, c_upd)),
               f"находки на копии: {sorted(found_e)}", differ=True)
    found_yu = broken_found(anchor_var, "    return False  # ПОЛОМКА (ю): имя MEZO_CONTAINER не узнаётся")
    ok &= case("(ю) поломка «имя MEZO_CONTAINER не узнаётся»: (у)(ш)(щ) пропадают, (с)(т) остаются",
               gone_kept(found_yu, (c_upd, c_key, c_dict), (c_root, c_file)),
               f"находки на копии: {sorted(found_yu)}", differ=True)
    # и по поломке на каждый путь поверх готовой среды
    found_ya = broken_found(anchor_key, "            and False)  # ПОЛОМКА (я): ключ среды не прослеживается")
    ok &= case('(я) поломка «ключ env["MEZO_CONTAINER"] не прослеживается»: (ш) пропадает, (у)(щ) остаются',
               gone_kept(found_ya, (c_key,), (c_upd, c_dict)),
               f"находки на копии: {sorted(found_ya)}", differ=True)
    found_j = broken_found(anchor_dict, "                    if False:  # ПОЛОМКА (й): словарь в .update() не прослеживается")
    ok &= case("(й) поломка «словарь в .update() не прослеживается»: (щ) пропадает, (у)(ш) остаются",
               gone_kept(found_j, (c_dict,), (c_upd, c_key)),
               f"находки на копии: {sorted(found_j)}", differ=True)

    # ── семь форм q01–q07 и ложная находка z07 (слово владельца 2026-11-03 09:14:10 UTC в чате
    #    COORD «Судить все семь», записка #6243; формы — из проб COORD) ─────────────────────────
    def judged(fname, word):
        return fname in found and word in live.get(fname, "")

    def why(*fnames):
        return " · ".join(f"{n}: {live.get(n, 'нет находки' if n not in found else 'находка без причины')}"
                          for n in fnames)

    ok &= case("(q01) корень строкой-путём к живому контуру (так сделана поломка m1c) — НАХОДКА",
               judged(q01, "путь строкой"), why(q01), differ=True)
    ok &= case("(q02) from mezo_paths import container_root as croot → stand_env(croot()) — НАХОДКА",
               judged(q02, "под именем croot"), why(q02), differ=True)
    ok &= case('(q03) env={**stand_env(d), "MEZO_CONTAINER": str(container_root())} — НАХОДКА',
               judged(q03, "container_root"), why(q03), differ=True)
    ok &= case("(q04) env=dict(stand_env(d), MEZO_CONTAINER=str(container_root())) — НАХОДКА",
               judged(q04, "container_root"), why(q04), differ=True)
    ok &= case('(q05) env = stand_env(d); env = {**env, "MEZO_CONTAINER": …} — НАХОДКА',
               judged(q05, "container_root"), why(q05), differ=True)
    ok &= case('(q06) env = stand_env(d); env |= {"MEZO_CONTAINER": …} — НАХОДКА',
               judged(q06, "container_root"), why(q06), differ=True)
    ok &= case("(q07) корень — рабочий каталог: Path.cwd() · os.getcwd() · Path() — три НАХОДКИ",
               all(judged(n, "рабочий каталог") for n in (*q07_cwd, q07_empty)),
               why(*q07_cwd, q07_empty), differ=True)
    ok &= case("(z07) root = container_root(); root = mezo_stand.new(…); stand_env(root) — НЕ находка "
               "(ложная находка PR 72 снята)",
               z07 not in found and z07 not in live, why(z07), differ=True)
    ok &= case("(z07-бис) встречный: root = new(…); if flag: root = container_root() — НАХОДКА "
               "(вложенное присваивание после прямого судится)",
               judged(z07b, "container_root"), why(z07b), differ=True)
    ok &= case("(z07-тер) встречный: root = container_root(); root = Path(root).parent — НАХОДКА "
               "(имя через само себя прослеживается)",
               judged(z07c, "container_root"), why(z07c), differ=True)
    ok &= case('(z08·z09) встречные: {**stand_env(d), "MEZO_CONTAINER": str(стенд)} и '
               'env.update(MEZO_CONTAINER="") — НЕ находки',
               all(n not in found for n in (z08, z09)), why(z08, z09))

    # по поломке на каждую форму: пропадает своя, соседняя остаётся
    anchor_str = "        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value:"
    anchor_alias = "    aliases = mezo_paths_aliases(pools)"
    anchor_dict_lit = "            elif isinstance(node, ast.Dict):"
    anchor_dict_call = '            elif isinstance(node, ast.Call) and call_name(node.func) == "dict":'
    anchor_reassign = "                sources.append(stmt.value)  # env = … — и сама среда, и её перезапись поверх (q05)"
    anchor_ior = "                sources.append(stmt.value)  # env |= {…} (q06)"
    anchor_cwd = 'CWD_CALLS = {"cwd", "getcwd", "getcwdb"}'
    anchor_empty = '                    name in ("Path", "PurePath") and not node.args and not node.keywords):'
    anchor_reach = ('            for value, value_scope in reaching_values(node.id, getattr(node, "lineno", None), '
                    'pools, scope_node):')
    anchor_last = "        own = [s for s in before if s.lineno >= last.lineno]"
    for anchor_text, label in ((anchor_str, "строки-пути"), (anchor_alias, "псевдонима"),
                               (anchor_dict_lit, "словаря в env="), (anchor_dict_call, "dict(…) в env="),
                               (anchor_reassign, "перезаписи env"), (anchor_ior, "env |="),
                               (anchor_cwd, "рабочего каталога"), (anchor_empty, "Path() без аргументов"),
                               (anchor_reach, "доходящих присваиваний"), (anchor_last, "последнего прямого")):
        if real_source.count(anchor_text) != 1:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь «{label}» найден {real_source.count(anchor_text)} раз")
    found_b = broken_found(anchor_str, "        if False:  # ПОЛОМКА (q01): строка-путь не судится")
    ok &= case("(q01) поломка «строка-путь не судится»: q01 пропадает, (с) и q07 остаются",
               gone_kept(found_b, (q01,), (c_root, *q07_cwd)), f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_alias, "    aliases = {}  # ПОЛОМКА (q02): псевдоним импорта не узнаётся")
    ok &= case("(q02) поломка «псевдоним импорта не узнаётся»: q02 пропадает, (с) остаётся",
               gone_kept(found_b, (q02,), (c_root,)), f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_dict_lit, "            elif False:  # ПОЛОМКА (q03): словарь в env= не судится")
    ok &= case("(q03) поломка «словарь {…} не судится»: q03 q05 q06 пропадают, q04 и (щ) остаются",
               gone_kept(found_b, (q03, q05, q06), (q04, c_dict)), f"находки на копии: {sorted(found_b)}",
               differ=True)
    found_b = broken_found(anchor_dict_call, "            elif False:  # ПОЛОМКА (q04): dict(…) в env= не судится")
    ok &= case("(q04) поломка «dict(…) не судится»: q04 пропадает, q03 остаётся",
               gone_kept(found_b, (q04,), (q03,)), f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_reassign, "                sources.append(stmt.value) if not sources else None"
                                            "  # ПОЛОМКА (q05): судится только первое env = …")
    ok &= case("(q05) поломка «судится только первое env = …»: q05 пропадает, q06 (т) (у) остаются",
               gone_kept(found_b, (q05,), (q06, c_file, c_upd)), f"находки на копии: {sorted(found_b)}",
               differ=True)
    found_b = broken_found(anchor_ior, "                pass  # ПОЛОМКА (q06): env |= {…} не судится")
    ok &= case("(q06) поломка «env |= не судится»: q06 пропадает, q05 остаётся",
               gone_kept(found_b, (q06,), (q05,)), f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_cwd, "CWD_CALLS = set()  # ПОЛОМКА (q07): рабочий каталог не судится")
    ok &= case("(q07) поломка «cwd() и getcwd() не судятся»: они пропадают, Path() и (с) остаются",
               gone_kept(found_b, q07_cwd, (q07_empty, c_root)), f"находки на копии: {sorted(found_b)}",
               differ=True)
    found_b = broken_found(anchor_empty, "                    False):  # ПОЛОМКА (q07): Path() без аргументов не судится")
    ok &= case("(q07-бис) поломка «Path() без аргументов не судится»: Path() пропадает, cwd() и getcwd() остаются",
               gone_kept(found_b, (q07_empty,), q07_cwd), f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_reach, "            for value, value_scope in [(v, None) for v in assigned_values("
                                         "node.id, pools)]:  # ПОЛОМКА (z07): судится любое присваивание имени")
    ok &= case("(z07) поломка «судится любое присваивание имени» (как в PR 72): z07 снова находка, "
               "z07-бис и z07-тер остаются",
               z07 in found_b and all(n in found_b for n in (z07b, z07c)), f"находки на копии: {sorted(found_b)}",
               differ=True)
    found_b = broken_found(anchor_last, "        own = [last]  # ПОЛОМКА (z07-бис): вложенное после прямого не судится")
    ok &= case("(z07-бис) поломка «вложенное после прямого не судится»: z07-бис пропадает, z07-тер остаётся, "
               "z07 по-прежнему не находка",
               gone_kept(found_b, (z07b, z07), (z07c,)), f"находки на копии: {sorted(found_b)}", differ=True)

    # ── q11 команда пришла возвратом функции (слово владельца 2026-11-03 13:40:44 UTC в чате
    #    COORD «Все три одним PR 75», записка #6247) ─────────────────────────────────────────
    q11_local, q11_neigh = "bite-case32-ret-local.py", "bite-case33-ret-neighbour.py"
    q11_git, q11_pinned = "bite-case34-ret-git.py", "bite-case35-ret-pinned.py"
    q11_shadow, q11_run = "bite-case36-ret-shadow.py", "bite-case37-ret-run.py"
    q11_counter = (q11_git, q11_pinned, q11_shadow, q11_run)
    ok &= case("(q11) свой помощник возвращает команду с интерпретатором (cmd = make_cmd(…)) — НАХОДКА",
               q11_local in found, f"находки: {sorted(n for n in found if 'ret-' in n)}", differ=True)
    ok &= case("(q11) помощник СОСЕДНЕГО файла: subprocess.run(helper.build_cmd(…)) — НАХОДКА "
               "(так direct_answers берёт build_argv)",
               q11_neigh in found, f"находки: {sorted(n for n in found if 'ret-' in n)}", differ=True)
    ok &= case("(q11) встречные: помощник возвращает git · env стенда на месте · своё одноимённое определение "
               "возвращает git · помощник возвращает итог прогона — НЕ находки",
               all(n not in found for n in q11_counter), f"находки: {sorted(n for n in found if 'ret-' in n)}")
    anchor_index = "        file_returners = (set(returners) - defined) | own_returning  # своё определение — главнее"
    anchor_ret_name = "        frontier += [n.id for n in nodes if isinstance(n, ast.Name)]  # имя в return (q11)"
    anchor_runs = ("        if isinstance(n, ast.Call) and call_name(n.func) in SUBPROCESS_FUNCS:\n"
                   "            continue\n        out.append(n)")
    for anchor_text, label in ((anchor_index, "индекса возврата"), (anchor_ret_name, "имени в return"),
                               (anchor_runs, "итога прогона")):
        if real_source.count(anchor_text) != 1:
            raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь «{label}» найден {real_source.count(anchor_text)} раз")
    py_var, cmd_var = "bite-case9-py-var.py", "bite-case10-cmd-var.py"
    found_b = broken_found(anchor_index, "        file_returners = set()  # ПОЛОМКА (q11): команда из возврата не судится")
    ok &= case("(q11) поломка «команда из возврата не судится»: обе находки q11 пропадают, (к)(л) остаются, "
               "встречные не меняются",
               gone_kept(found_b, (q11_local, q11_neigh, *q11_counter), (py_var, cmd_var)),
               f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_index, "        file_returners = set(returners) | own_returning"
                                         "  # ПОЛОМКА (q11): своё определение не главнее чужого")
    ok &= case("(q11) поломка «своё определение не главнее чужого одноимённого»: встречный с git становится "
               "находкой, обе находки q11 остаются",
               gone_kept(found_b, (), (q11_shadow, q11_local, q11_neigh)),
               f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_ret_name, "        pass  # ПОЛОМКА (q11): имя в return не прослеживается")
    ok &= case("(q11) поломка «имя в return не прослеживается»: свой помощник (return argv) пропадает, "
               "соседний (return [sys.executable, …]) остаётся",
               gone_kept(found_b, (q11_local,), (q11_neigh,)), f"находки на копии: {sorted(found_b)}", differ=True)
    found_b = broken_found(anchor_runs, "        if False:  # ПОЛОМКА (q11): итог прогона считается командой\n"
                                        "            continue\n        out.append(n)")
    ok &= case("(q11) поломка «итог прогона считается командой»: встречный out = run_tool(…).stdout → git "
               "становится находкой",
               gone_kept(found_b, (), (q11_run, q11_local, q11_neigh)), f"находки на копии: {sorted(found_b)}",
               differ=True)

    # ── Р1 обратный ход: строка-разрешение ОСЛЕПЛЕНА в КОПИИ проверки ──────────────
    anchor = "m = ALLOW_RE.search(line_text)"
    if real_source.count(anchor) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь найден {real_source.count(anchor)} раз")
    blinded_source = real_source.replace(anchor, "m = None  # ОСЛЕПЛЕНО ПРИЁМКОЙ bite-acceptance-env.py")
    stand2 = build_stand(blinded_source)
    data2, rc2 = run_checker(stand2, "--no-debt-list")
    found2 = names(data2.get("findings", []))
    ok &= case("Р1 ослеплённая проверка: ④ становится находкой (разрешение — не украшение)",
               "bite-case4-excused.py" in found2,
               f"находки ослеплённой копии: {sorted(found2)}", differ=True)

    # ── (а)(б)(в) реестр известного долга ───────────────────────────────────────────
    stand3 = build_debt_stand(real_source, DEBT_CONTENT)
    data3, rc3 = run_checker(stand3)
    debt3 = data3.get("debt", {})
    new_funcs_case6 = new_key_funcs(data3, "bite-case6-recorded.py")
    shrunk_case7 = shrunk_rows(data3, "bite-case7-shrunk.py")

    ok &= case("(а) записанная в реестре находка — НЕ провал, считается в долге",
               "call1" not in new_funcs_case6 and debt3.get("known_calls", 0) >= 1,
               f"новые функции case6: {sorted(new_funcs_case6)} · known_calls={debt3.get('known_calls')}",
               differ=True)
    ok &= case("(б) новый вызов в ДРУГОЙ функции того же файла — ПРОВАЛ",
               "call2" in new_funcs_case6,
               f"новые функции case6: {sorted(new_funcs_case6)}", differ=True)
    ok &= case("(в) в реестре 2, живых 1 — «долг уменьшился», код 0 у ЭТОЙ строки",
               len(shrunk_case7) == 1 and shrunk_case7[0].get("recorded") == 2
               and shrunk_case7[0].get("live") == 1,
               f"shrunk case7: {shrunk_case7}", differ=True)
    new_funcs_case8 = new_key_funcs(data3, "bite-case8-legit.py")
    ok &= case("(з) вызов, записанный реестром как «законно», — НЕ провал и НЕ долг",
               not new_funcs_case8 and debt3.get("legitimate_calls", 0) == 1
               and debt3.get("known_calls") == 3,
               f"новые функции case8: {sorted(new_funcs_case8)} · законно={debt3.get('legitimate_calls')}"
               f" · долг={debt3.get('known_calls')}", differ=True)

    # ── (и) НАРОЧНАЯ ПОЛОМКА: реестр покрывает только разряд «долг» ─────────────────
    anchor_legit = "    covered = {**dolg, **legit}"
    if real_source.count(anchor_legit) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь покрытия «законно» найден "
                          f"{real_source.count(anchor_legit)} раз")
    debt_only_source = real_source.replace(
        anchor_legit, "    covered = dict(dolg)  # ПОЛОМКА (и): «законно» ничего не прощает")
    stand8 = build_debt_stand(debt_only_source, DEBT_CONTENT)
    data8, _rc8 = run_checker(stand8)
    ok &= case("(и) поломка «прощает только долг»: (з) снова провал",
               "call" in new_key_funcs(data8, "bite-case8-legit.py"),
               f"новые функции case8 на копии: {sorted(new_key_funcs(data8, 'bite-case8-legit.py'))}"
               f" — должно быть ['call']", differ=True)

    # ── (г) НАРОЧНАЯ ПОЛОМКА: сверка с реестром только по имени файла ──────────────
    anchor_covers = "    return key in dolg"
    if real_source.count(anchor_covers) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь key_covers найден "
                          f"{real_source.count(anchor_covers)} раз")
    filename_only_source = real_source.replace(
        anchor_covers,
        "    return any(k[0] == key[0] for k in dolg)  # ПОЛОМКА (г): только по имени файла")
    stand4 = build_debt_stand(filename_only_source, DEBT_CONTENT)
    data4, rc4 = run_checker(stand4)
    new_funcs_case6_broken = new_key_funcs(data4, "bite-case6-recorded.py")
    ok &= case("(г) поломка «сверка только по имени файла»: (б) ПЕРЕСТАЁТ находиться",
               "call2" not in new_funcs_case6_broken,
               f"новые функции case6 на ослеплённой копии: {sorted(new_funcs_case6_broken)} "
               f"— должно быть ПУСТО (поломка прячет call2)", differ=True)

    # ── (д)(е) реестра рядом нет · явный путь неверен — ТЕКСТОВЫЙ вывод, как его видит
    #    общий прогон проверок (он зовёт проверку без аргументов) ──────────────────────
    strict_count = len(data.get("findings", []))
    out5, rc5 = run_checker_text(stand)
    warn5 = [l for l in out5.splitlines()
             if l.startswith("⚠️") and "реестра известного долга рядом нет" in l]
    ok &= case("(д) реестра рядом нет — строка «⚠️» с числом находок, код 0",
               rc5 == 0 and len(warn5) == 1 and f"стенда {strict_count} в" in warn5[0],
               f"rc={rc5} · строгих находок {strict_count} · строка: {warn5[0] if warn5 else '—'}",
               differ=True)
    missing = stand / "vnext-tools" / "нет-такого-реестра.txt"
    out6, rc6 = run_checker_text(stand, "--debt-list", str(missing))
    ok &= case("(е) --debt-list на несуществующий файл — отказ, код 2",
               rc6 == 2 and "реестр долга не найден" in out6,
               f"rc={rc6} · {out6.strip().splitlines()[-1] if out6.strip() else '—'}", differ=True)

    # ── (ж) НАРОЧНАЯ ПОЛОМКА: ветка «реестра нет» отключена в копии проверки ──────────
    anchor_missing = "    if not debt_path.exists():"
    if real_source.count(anchor_missing) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь ветки «реестра нет» найден "
                          f"{real_source.count(anchor_missing)} раз")
    no_branch_source = real_source.replace(
        anchor_missing, "    if False:  # ПОЛОМКА (ж): реестра нет — читается как пустой")
    stand7 = build_stand(no_branch_source)
    out7, rc7 = run_checker_text(stand7)
    ok &= case("(ж) поломка «ветки реестра нет»: (д) снова провал — новый контур упал бы",
               rc7 == 1,
               f"rc={rc7} на копии без ветки — должно быть 1", differ=True)

    # ── (н)(о)(п) НУЛЕВОЙ ДЕНЬ: свежий контур из пакета — «ℹ️ свойство нового контура», не «⚠️» ──
    pack = find_pack()
    if pack is None:
        raise SystemExit("⛔ НЕ ЗАПУСТИЛАСЬ: пакета с scripts/init-group.py не нашлось (ни по mezo_paths."
                         "template_root(), ни рядом) — свежий контур собрать не из чего, случаи (н)(о)(п) "
                         "не состоялись. Это не «зелёное».")
    fresh_root, fresh_db, build_note = build_fresh_circuit(pack)
    if fresh_db is None:
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: сборщик init-group.py не собрал контур: {build_note}")
    used_db = mezo_stand.snapshot_db(fresh_db, fresh_root / ".mezosync" / "mezosync-used.db")
    con = sqlite3.connect(str(used_db))
    con.execute("INSERT INTO messages (writer_role, body_md) VALUES ('COORD', "
                "'проба приёмки: в ленте уже есть записка — день не нулевой')")
    con.commit()
    con.close()
    # Проверка без --debt-list ищет реестр РЯДОМ С СОБОЙ. У живого контура он там лежит, и ветка
    # «реестра рядом нет» не наступает — поэтому судим копию того же текста в каталоге без реестра,
    # как общий прогон зовёт проверку свежего контура (так же лежит и копия поломки (п)).
    real_copy_dir = fresh_root / "check-copy"
    real_copy_dir.mkdir()
    real_copy = real_copy_dir / "check-acceptance-env.py"
    real_copy.write_text(real_source, encoding="utf-8")
    (real_copy_dir / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    real_fresh_ok, real_fresh_note, real_used_ok, real_used_note = zero_day_verdicts(
        real_copy, fresh_root, fresh_db, used_db)
    ok &= case("(н) свежий контур из пакета, реестра нет, в ленте нет записок — «ℹ️ … свойство нового "
               "контура» и ни одного «⚠️»",
               real_fresh_ok, f"копия {real_copy}: {real_fresh_note}", differ=True)
    ok &= case("(о) ТОТ ЖЕ контур, но в ленте одна записка — «⚠️», как было, и ни одного «ℹ️»",
               real_used_ok, real_used_note, differ=True)

    # ── (р) встречный к месту: реестр рядом с копией — ветки «реестра рядом нет» нет вовсе ────
    near_dir = fresh_root / "check-copy-with-debt"
    near_dir.mkdir()
    near_check = near_dir / "check-acceptance-env.py"
    near_check.write_text(real_source, encoding="utf-8")
    (near_dir / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    (near_dir / "acceptance-env-debt.txt").write_text("", encoding="utf-8")
    near_fresh_ok, near_fresh_note, _, _ = zero_day_verdicts(near_check, fresh_root, fresh_db, used_db)
    ok &= case("(р) встречный к месту: реестр рядом с копией (как у живого контура) — строки "
               "«реестра рядом нет» нет, (н) на ней не держится",
               (not near_fresh_ok) and "строка про реестр: —" in near_fresh_note,
               f"копия {near_check}: {near_fresh_note}")

    # ── (п) НАРОЧНАЯ ПОЛОМКА: в копии проверки нулевой день не различается ───────────────────
    anchor_zero_day = "        zero_day = bool(getattr(mezo_paths, \"is_zero_day\", lambda _db: False)(db_path))"
    if real_source.count(anchor_zero_day) != 1:
        raise SystemExit(f"ПРИЁМКА НЕ СОСТОЯЛАСЬ: якорь различителя нулевого дня найден "
                         f"{real_source.count(anchor_zero_day)} раз")
    broken_dir = breaks_dir(fresh_root, "zero-day-check")
    broken_check = broken_dir / "check-acceptance-env.py"
    broken_check.write_text(real_source.replace(
        anchor_zero_day, "        zero_day = False  # ПОЛОМКА (п): нулевой день не различается"),
        encoding="utf-8")
    (broken_dir / "mezo_paths.py").write_text(
        Path(mezo_paths.__file__).read_text(encoding="utf-8"), encoding="utf-8")
    brk_fresh_ok, brk_fresh_note, brk_used_ok, brk_used_note = zero_day_verdicts(
        broken_check, fresh_root, fresh_db, used_db)
    ok &= case("(п) поломка «нулевой день не различается»: красит РОВНО (н), а (о) остаётся зелёным",
               (not brk_fresh_ok) and brk_used_ok,
               f"копия {broken_check}: (н) {'✅' if brk_fresh_ok else '🔴'} — {brk_fresh_note}; "
               f"(о) {'✅' if brk_used_ok else '🔴'} — {brk_used_note}", differ=True)

    print()
    print(f"{'✅ ПРИЁМКА ПРИНЯТА' if ok else '🔴 НЕ ПРИНЯТА'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
