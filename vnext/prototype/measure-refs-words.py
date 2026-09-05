# -*- coding: utf-8 -*-
"""measure-refs-words.py — у КАЖДОГО слова перечня проверки ссылок есть ли СВОЙ случай в приёмке.

Карточка #529: слово, у которого нет своего случая, можно вынуть из перечня молча — и зелёное
этого не увидит (так было с 19 из 29, замер @CORE записка #4740; воспроизведено @PROTO 05.09).
Для КАЖДОГО слова: убрать его на КОПИИ, прогнать приёмку bite-dangling-refs.py — обязана покраснеть.
Запуск: python C:/guts/.atlas/vnext-tools/measure-refs-words.py [каталог с инструментом] [--show]
Выход: 0 — все слова защищены · 1 — есть слова без случая (названы) · 2 — контроль красен, мерить нечего.

Копия в свежем каталоге + python -B: байткод не пишется и не читается (класс @CORE: кэш судил
не ту редакцию). Контроль на нетронутом перечне — ПЕРВЫМ."""
import io, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else Path(__file__).resolve().parent
tmp = Path(tempfile.mkdtemp(prefix='a529-'))
for f in ('check-dangling-refs.py', 'bite-dangling-refs.py', 'mezo_paths.py'):
    shutil.copy2(SRC / f, tmp / f)
chk = (tmp / 'check-dangling-refs.py').read_text(encoding='utf-8')
m = re.search(r'СЛОВА_ТИПЫ = \((.*?)\n\)', chk, re.S)
block = m.group(0)
inner = ''.join(re.findall(r'r"(.*?)"', m.group(1)))
words = inner.split('|')
print('слов в перечне:', len(words))
print('  ' + ' · '.join(words))


def run(text):
    (tmp / 'check-dangling-refs.py').write_text(text, encoding='utf-8')
    env = dict(os.environ, MEZO_CONTAINER=os.environ.get('MEZO_CONTAINER', str(SRC.parent)))   # копия вне контейнера: путь окружением
    r = subprocess.run([sys.executable, '-B', str(tmp / 'bite-dangling-refs.py')], env=env,
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if '--show' in sys.argv and r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-800:])
    return r.returncode


rc0 = run(chk)
print('③ КОНТРОЛЬ, нетронутый перечень:', '✅ зелёный' if rc0 == 0 else '🔴 КРАСНЫЙ — дальше мерить нечего')
if rc0 != 0:
    shutil.rmtree(tmp); sys.exit(2)
protected, exposed = [], []
for w in words:
    rest = [x for x in words if x != w]
    new_block = 'СЛОВА_ТИПЫ = (\n    r"' + '|'.join(rest) + '"\n)'
    code = chk.replace(block, new_block, 1)
    assert code != chk, w
    rc = run(code)
    (protected if rc != 0 else exposed).append(w)
    print(('   ✅ защищено      ' if rc != 0 else '   🔴 БЕЗ СЛУЧАЯ    ') + w)
print(f'①② ИТОГ: защищено {len(protected)} из {len(words)} · без своего случая {len(exposed)}'
      + (': ' + ', '.join(exposed) if exposed else ''))
shutil.rmtree(tmp)
sys.exit(0 if not exposed else 1)
