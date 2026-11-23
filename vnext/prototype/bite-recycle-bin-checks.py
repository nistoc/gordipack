# -*- coding: utf-8 -*-
"""
bite-recycle-bin-checks.py — приёмка карточки #831: помощник переноса в Корзину (mezo_stand._windows_bin)
засчитывает «перенесено» только тому каталогу, который ПОЯВИЛСЯ в Корзине, и не отдаёт Windows каталог
с путём от 260 знаков внутри.

Предмет. До правки move() засчитывал перенос, если SHFileOperationW вернул 0 и каталога нет на месте.
Опыт карточки #831 (23.11.2026) на дереве из вложенных каталогов (так строит make_tree ниже): с самым
длинным путём 259 знаков UTF-16 каталог уходит в Корзину, с 260 и 300 знаков Windows стирает его насовсем,
вызов возвращает 0, помощник отвечает «перенесено 1». Граница измерена для этой формы дерева, а не для
любой: дерево, где путь 275 знаков у ФАЙЛА прямо в каталоге (путь каталога 188 знаков), Windows в Корзину
взяла (замер COORD 23.11, карточка #832). Отказ помощника от 260 знаков для такой формы строже, чем нужно,
но ошибается в безопасную сторону: лишний отказ, а не потеря каталога. Правка: перенос идёт через
_move_checked. До переноса — отказ на пути от 260 знаков и на нечитаемых записях Корзины; после — сверка
с новой записью $I Корзины по прежнему пути каталога.

Случаи. ①–⑤ — на подставном томе: каталог с $Recycle.Bin внутри и подставной перенос. ⑥ — настоящий
_windows_bin, у которого подменён только сам перенос (SHFileOperationW — счётчик вызовов, ничего не
удаляет и не переносит).
  ①  после переноса в Корзине новая запись $I (формат 2) с прежним путём — засчитан; тут же испытан
     счётчик ⑥: на подставном томе он видит ровно эту одну запись
  ①б то же, когда каталог назван коротким именем 8.3, а запись несёт полное (так пишет Windows) — засчитан;
     на томе без коротких имён случай не различает и назван непроверенным
  ②  самый длинный путь внутри — 260 знаков: отказ ДО переноса, перенос не звался, каталог на месте,
     в строке названо число знаков
  ②б встречный: 259 знаков — до переноса дошло
  ③  каталог исчез, а новой записи нет — «УДАЛЕНО МИМО КОРЗИНЫ», не засчитан; второй каталог тем же
     помощником не тронут (перенос остановлен)
  ③б каталог исчез, новые записи $I есть, но все три ЧУЖИЕ: сосед в том же родителе, путь с общим началом
     («<путь>-other» — так бывает у «<имя>.removing-<номер>» уборки по сроку) и тёзка в другом родителе —
     «УДАЛЕНО МИМО КОРЗИНЫ», не засчитан; второй не тронут. Без него сверку прежнего пути не судил ни один
     случай: поломки «путь не сравнивается», «по началу», «только имя» (К1, К3, К4 COORD; здесь П9–П11)
     проходили все остальные
  ④  новая запись незнакомого формата — «приход в Корзину не проверен», не засчитан; второй не тронут
  ⑤  записи Корзины не читаются до переноса — отказ, перенос не звался, каталог на месте
  ⑥  уборка стендов по сроку (_sweep_aged) через настоящий _windows_bin, без своих правок: старый стенд
     с путём 260 знаков внутри — отказ, стенд на месте под прежним именем, в строке уборки
     «не перенесено: 1», перенос Windows не звался ни разу, и в настоящей Корзине тома не появилось
     ни одной записи с путём внутри каталога приёмки. Только на Windows

Нарочные поломки — в копиях помощника; у каждой записан набор случаев, которые она обязана провалить:
  П1  запись $I разбирается со смещения 24 вместо 28 ......... ① ①б
  П1б сверка только с путём, как он назван (без полной записи) ①б
  П2  отказ с 261 знака вместо 260 ........................... ②
  П3  предел 259 знаков вместо 260 ........................... ②б
  П4  исчезнувший без новых записей засчитан ................. ③
  П5  незнакомая запись читается как «записи нет» ............ ④
  П6  остановка после потери не действует .................... ③ ③б ④
  П7  нечитаемые записи Корзины читаются как «записей нет» ... ⑤
  П8  _windows_bin переносит мимо _move_checked, как до правки ⑥
  П9  прежний путь новой записи не сравнивается (К1 COORD) ... ③б
  П10 прежний путь сравнивается по началу (К3 COORD) ......... ③б
  П11 сравнивается только имя каталога (К4 COORD) ............ ③б
Поломка, которая провалила не ровно свой набор, — провал приёмки: значит, случаи слепы или задевают чужое.
Подставная Корзина берёт номер записи по первому свободному месту в каталоге записей тома: под поломками
П6 и П9 случаи ③б и ④ проваливаются своей проверкой («второй не тронут»), а не падением подставного
переноса на занятом имени (Н1 COORD, карточка #832). Поломка, свои случаи которой провалились падением
(«случай упал»), а не проверкой, считается непойманной: её поймал бы любой сбой подставного тома.
Случай, не проверенный на этой машине, из набора поломки вычитается и называется.

Безопасность. Всё живёт в своём каталоге приёмки (mezo_stand.new). ⑥ идёт потомком со своими TEMP, TMP,
TMPDIR, HOME, USERPROFILE внутри этого каталога и без MEZO_STAND_TEST_BIN. В потомке SHFileOperationW
подменён счётчиком: настоящая Корзина в ⑥ только читается (настройки, занятость, записи), а перенос не
доходит до Windows ни на целом помощнике, ни под любой поломкой. Поломку П8 видно по счётчику: перенос
позвали. До правки (карточка #832) П8 звала настоящий перенос, и Windows положила каталог приёмки в
настоящую Корзину владельца (полный прогон набора ядра 23.11, 344 байта) — дерево ⑥ оказалось той формы, которую
Корзина берёт. Контроль: после каждого прогона ⑥ считаются новые записи настоящей Корзины тома с прежним
путём внутри каталога ⑥; их обязано быть 0, итог по всем прогонам печатается последней строкой.

    python bite-recycle-bin-checks.py
Коды: 0 — всё прошло · 1 — провал · 2 — провалов нет, но часть случаев не проверена (не Windows, нет
коротких имён 8.3).
"""
import contextlib
import importlib.util
import io
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

import mezo_stand

HERE = Path(__file__).resolve().parent
HELPER = HERE / "mezo_stand.py"
SID = "S-1-5-21-831"                       # каталог записей подставного тома
HOUR = 3600
CASES = ("①", "①б", "②", "②б", "③", "③б", "④", "⑤", "⑥")
SAME_LINE = "            if any(o is not None and os.path.normcase(o.rstrip(\"\\\\/\")) in forms for o in originals):\n"

BREAKS = [
    # (метка, что сломано, место в помощнике, замена, набор провалов)
    ("П1", "запись $I разбирается со смещения 24 вместо 28",
     "        raw = data[28:28 + 2 * size]\n", "        raw = data[24:24 + 2 * size]\n", {"①", "①б"}),
    ("П1б", "сверка только с путём, как он назван",
     "        forms = {os.path.normcase(full), os.path.normcase(os.path.realpath(full))}\n",
     "        forms = {os.path.normcase(full)}\n", {"①б"}),
    ("П2", "отказ с 261 знака вместо 260",
     "        if why is None and longest >= LONG_PATH:\n", "        if why is None and longest > LONG_PATH:\n", {"②"}),
    ("П3", "предел 259 знаков вместо 260",
     "LONG_PATH = 260   #", "LONG_PATH = 259   #", {"②б"}),
    ("П4", "исчезнувший без новых записей засчитан",
     SAME_LINE,
     "            if not originals or any(o is not None and os.path.normcase(o.rstrip(\"\\\\/\")) in forms "
     "for o in originals):\n", {"③"}),
    ("П5", "незнакомая запись читается как «записи нет»",
     "            if None in originals:\n", "            if False:\n", {"④"}),
    ("П6", "остановка после потери не действует",
     "        if state.get(\"stop\"):\n", "        if False:\n", {"③", "③б", "④"}),
    ("П7", "нечитаемые записи Корзины читаются как «записей нет»",
     "        return None, f\"записи Корзины не читаются: {root} ({type(e).__name__})\"\n",
     "        return found, None\n", {"⑤"}),
    ("П8", "_windows_bin переносит мимо _move_checked, как до правки",
     "        return _move_checked(paths, delete_one, root.value, state)\n",
     "        for p in paths:\n"
     "            delete_one(os.path.abspath(p))\n"
     "        return sum(1 for p in paths if not os.path.lexists(p)), [p for p in paths if os.path.lexists(p)]\n",
     {"⑥"}),
    ("П9", "прежний путь новой записи не сравнивается (К1 COORD)",
     SAME_LINE,
     "            if any(o is not None for o in originals):\n", {"③б"}),
    ("П10", "прежний путь сравнивается по началу, а не на равенство (К3 COORD)",
     SAME_LINE,
     "            if any(o is not None and any(os.path.normcase(o.rstrip(\"\\\\/\")).startswith(f) for f in forms) "
     "for o in originals):\n", {"③б"}),
    ("П11", "сравнивается только имя каталога, без родителя (К4 COORD)",
     SAME_LINE,
     "            if any(o is not None and os.path.basename(os.path.normcase(o.rstrip(\"\\\\/\"))) in "
     "{os.path.basename(f) for f in forms} for o in originals):\n", {"③б"}),
]

# Потомок ⑥: настоящий _windows_bin, но SHFileOperationW — счётчик. Перенос до Windows не доходит ни на
# целом помощнике (он отказывает раньше), ни под поломкой П8 — её видно по числу вызовов.
CHILD = (
    "import ctypes, importlib.util, sys\n"
    "calls = []\n"
    "class _Op:\n"
    "    argtypes = None\n"
    "    restype = None\n"
    "    def __call__(self, *args):\n"
    "        calls.append(1)\n"
    "        return 0\n"
    "class _Shell:\n"
    "    def __init__(self, real):\n"
    "        self._real = real\n"
    "        self.SHFileOperationW = _Op()\n"
    "    def __getattr__(self, name):\n"
    "        return getattr(self._real, name)\n"
    "_real_dll = ctypes.WinDLL\n"
    "def _dll(name, *args, **kwargs):\n"
    "    real = _real_dll(name, *args, **kwargs)\n"
    "    return _Shell(real) if str(name).lower().startswith('shell32') else real\n"
    "ctypes.WinDLL = _dll\n"
    "spec = importlib.util.spec_from_file_location('mezo_stand', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "sys.modules['mezo_stand'] = m\n"
    "spec.loader.exec_module(m)\n"
    "m._sweep_aged()\n"
    "print(f'🧪 перенос Windows звался: {len(calls)}')\n"
)
IN_REAL_BIN = []   # по прогону ⑥: записей настоящей Корзины с путём внутри каталога ⑥

ROOT: Path | None = None
_seq = [0]


def ext(path) -> str:
    """Путь с приставкой \\\\?\\ на Windows: деревья приёмки длиннее 259 знаков."""
    s = str(path)
    return "\\\\?\\" + s if os.name == "nt" and not s.startswith("\\\\") else s


def u16(s: str) -> int:
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def fresh(name: str) -> Path:
    _seq[0] += 1
    return ROOT / f"{_seq[0]:03d}-{name}"


def make_tree(top: Path, target: int | None = None) -> Path:
    """Каталог top с одним файлом в 3 байта; target — полная длина пути файла в знаках UTF-16, как назван top."""
    os.makedirs(ext(top))
    cur = top
    if target is None:
        f = cur / "f.txt"
    else:
        while target - u16(str(cur)) - 1 > 100:
            cur = cur / ("d" * 90)
            os.mkdir(ext(cur))
        f = cur / ("f" * (target - u16(str(cur)) - 1))
    with open(ext(f), "w", encoding="utf-8") as fh:
        fh.write("abc")
    if target is not None and u16(str(f)) != target:
        raise RuntimeError(f"дерево построено неверно: {u16(str(f))} знаков вместо {target}")
    return f


def drop(path) -> None:
    """Убрать дерево приёмки (оно внутри её каталога); не вышло — remove_tree скажет это сам."""
    if os.path.lexists(ext(path)):
        mezo_stand.remove_tree(ext(path))


def volume(readable: bool = True) -> Path:
    """Подставной том: каталог с $Recycle.Bin\\<SID>; readable=False — на месте $Recycle.Bin лежит файл."""
    vol = fresh("vol")
    vol.mkdir()
    if readable:
        (vol / "$Recycle.Bin" / SID).mkdir(parents=True)
    else:
        (vol / "$Recycle.Bin").write_text("не каталог", encoding="utf-8")
    return vol


def record_bytes(original: str, version: int = 2) -> bytes:
    name = (original + "\0").encode("utf-16-le")
    head = struct.pack("<qqq", version, 3, 133_000_000_000_000_000)
    if version == 2:
        return head + struct.pack("<i", len(original) + 1) + name
    return head + name


class Fake:
    """Подставной перенос: как Windows кладёт в Корзину (или как стирает мимо неё) — и счёт вызовов."""

    def __init__(self, vol: Path, how: str):
        self.vol, self.how, self.calls = vol, how, []

    def __call__(self, full: str) -> None:
        self.calls.append(full)
        if self.how == "noop":
            return
        if self.how == "past":
            mezo_stand.remove_tree(ext(full))
            return
        owner = self.vol / "$Recycle.Bin" / SID
        original = os.path.realpath(full)                 # Windows пишет полную запись пути
        originals = [original]
        if self.how == "foreign":                         # записи есть, но ни одна не о нём
            parent, name = os.path.dirname(original), os.path.basename(original)
            originals = [os.path.join(parent, "other-" + name),      # сосед в том же родителе (П9)
                         original + "-other",                         # общее начало пути (П10, К3 COORD)
                         os.path.join(parent + "-elsewhere", name)]   # тёзка в другом родителе (П11, К4 COORD)
        # Номер — первый свободный в каталоге записей тома, а не счёт вызовов этого Fake: в ③б и ④ на одном
        # томе работают два Fake, и под поломкой второй брал занятое $R00001 — случай падал, не дойдя до
        # своей проверки (Н1 COORD, карточка #832)
        k = self._free(owner)
        os.rename(ext(full), ext(owner / f"$R{k:05d}"))
        version = 9 if self.how == "unknown" else 2
        for o in originals:
            k = self._free(owner)
            (owner / f"$I{k:05d}").write_bytes(record_bytes(o, version))

    @staticmethod
    def _free(owner: Path) -> int:
        k = 1
        while (owner / f"$I{k:05d}").exists() or (owner / f"$R{k:05d}").exists():
            k += 1
        return k


def run_move(m, paths, fake: Fake, vol: Path, state: dict):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        moved, left = m._move_checked([str(p) for p in paths], fake, str(vol), state)
    return moved, left, buf.getvalue()


def short_form(path: Path) -> str | None:
    """Короткая запись 8.3 пути или None — на этом томе её нет."""
    if os.name != "nt":
        return None
    import ctypes
    buf = ctypes.create_unicode_buffer(2048)
    n = ctypes.windll.kernel32.GetShortPathNameW(str(path), buf, 2048)
    if n == 0 or n > 2048 or os.path.normcase(buf.value) == os.path.normcase(str(path)):
        return None
    return buf.value


# ── случаи: каждый → (True/False/None, слова) ──

def c1(m):
    vol = volume()
    top = fresh("c1")
    make_tree(top)
    fake = Fake(vol, "bin")
    moved, left, out = run_move(m, [top], fake, vol, {})
    # счётчик ⑥ испытан здесь: на подставном томе ровно одна запись с путём внутри каталога приёмки —
    # иначе его 0 в ⑥ значил бы «не умеет считать», а не «ничего не легло»
    counted = own_in_real_bin(str(vol), str(ROOT))
    ok = moved == 1 and not left and not os.path.lexists(top) and len(fake.calls) == 1 and counted == 1
    return ok, (f"перенесено {moved}, не перенесено {len(left)} · счётчик записей из каталога приёмки на "
                f"подставном томе: {counted} · вывод: {out.strip() or 'пусто'}")


def c1b(m):
    vol = volume()
    top = fresh("c1b-long-name-for-8dot3")
    make_tree(top)
    short = short_form(top)
    if short is None:
        drop(top)
        return None, "коротких имён 8.3 на этом томе нет — случай не различает"
    fake = Fake(vol, "bin")
    moved, left, out = run_move(m, [short], fake, vol, {})
    ok = moved == 1 and not left and not os.path.lexists(top)
    return ok, f"назван {short} · перенесено {moved}, не перенесено {len(left)} · вывод: {out.strip() or 'пусто'}"


def c2(m):
    vol = volume()
    top = fresh("c2")
    make_tree(top, 260)
    fake = Fake(vol, "noop")
    moved, left, out = run_move(m, [top], fake, vol, {})
    ok = (moved == 0 and len(left) == 1 and not fake.calls and os.path.lexists(ext(top))
          and "каталог не тронут" in out and "260 знаков" in out)
    drop(top)
    return ok, f"перенос звался {len(fake.calls)} раз · не перенесено {len(left)} · вывод: {out.strip()[:200] or 'пусто'}"


def c2b(m):
    vol = volume()
    top = fresh("c2b")
    make_tree(top, 259)
    fake = Fake(vol, "noop")
    moved, left, out = run_move(m, [top], fake, vol, {})
    ok = len(fake.calls) == 1 and "260 знаков" not in out and "259 (самый" not in out
    drop(top)
    return ok, f"перенос звался {len(fake.calls)} раз · вывод: {out.strip()[:200] or 'пусто'}"


def c3(m):
    vol = volume()
    first, second = fresh("c3a"), fresh("c3b")
    make_tree(first)
    make_tree(second)
    state: dict = {}
    m1, l1, out1 = run_move(m, [first], Fake(vol, "past"), vol, state)
    fake2 = Fake(vol, "bin")
    m2, l2, out2 = run_move(m, [second], fake2, vol, state)
    kept = os.path.lexists(second)
    ok = (m1 == 0 and len(l1) == 1 and "УДАЛЕНО МИМО КОРЗИНЫ" in out1
          and m2 == 0 and len(l2) == 1 and not fake2.calls and kept and "остановлен" in out2)
    drop(second)
    return ok, (f"первый: перенесено {m1}, строка «мимо»: {'есть' if 'УДАЛЕНО МИМО КОРЗИНЫ' in out1 else 'НЕТ'} · "
                f"второй: перенос звался {len(fake2.calls)} раз, на месте: {'да' if kept else 'НЕТ'}")


def c3b(m):
    vol = volume()
    first, second = fresh("c3ba"), fresh("c3bb")
    make_tree(first)
    make_tree(second)
    state: dict = {}
    fake1 = Fake(vol, "foreign")
    m1, l1, out1 = run_move(m, [first], fake1, vol, state)
    fake2 = Fake(vol, "bin")
    m2, l2, out2 = run_move(m, [second], fake2, vol, state)
    kept = os.path.lexists(second)
    gone = not os.path.lexists(first) and len(fake1.calls) == 1    # перенос был, каталог ушёл
    ok = (gone and m1 == 0 and len(l1) == 1 and "УДАЛЕНО МИМО КОРЗИНЫ" in out1
          and m2 == 0 and len(l2) == 1 and not fake2.calls and kept and "остановлен" in out2)
    drop(second)
    return ok, (f"первый: перенесено {m1}, строка «мимо»: {'есть' if 'УДАЛЕНО МИМО КОРЗИНЫ' in out1 else 'НЕТ'} "
                f"(три чужие записи Корзины) · второй: перенос звался {len(fake2.calls)} раз, "
                f"на месте: {'да' if kept else 'НЕТ'}")


def own_in_real_bin(volume_root: str, inside: str) -> int | None:
    """Записей настоящей Корзины тома с прежним путём внутри каталога inside; None — записи не читаются."""
    records, why = mezo_stand._bin_records(volume_root)
    if why is not None:
        return None
    prefix = os.path.normcase(inside.rstrip("\\/")) + os.sep
    n = 0
    for r in records:
        o = mezo_stand._bin_original(r)
        if o is not None and os.path.normcase(o).startswith(prefix):
            n += 1
    return n


def c4(m):
    vol = volume()
    first, second = fresh("c4a"), fresh("c4b")
    make_tree(first)
    make_tree(second)
    state: dict = {}
    m1, l1, out1 = run_move(m, [first], Fake(vol, "unknown"), vol, state)
    fake2 = Fake(vol, "bin")
    m2, l2, out2 = run_move(m, [second], fake2, vol, state)
    kept = os.path.lexists(second)
    ok = (m1 == 0 and len(l1) == 1 and "приход в Корзину не проверен" in out1 and "МИМО" not in out1
          and m2 == 0 and not fake2.calls and kept)
    drop(second)
    return ok, (f"первый: перенесено {m1} · вывод: {out1.strip()[:160] or 'пусто'} · "
                f"второй: перенос звался {len(fake2.calls)} раз")


def c5(m):
    vol = volume(readable=False)
    top = fresh("c5")
    make_tree(top)
    fake = Fake(vol, "past")
    moved, left, out = run_move(m, [top], fake, vol, {})
    kept = os.path.lexists(top)
    ok = moved == 0 and len(left) == 1 and not fake.calls and kept and "записи Корзины не читаются" in out
    drop(top)
    return ok, f"перенос звался {len(fake.calls)} раз · на месте: {'да' if kept else 'НЕТ'} · вывод: {out.strip()[:200] or 'пусто'}"


def c6(helper: Path):
    if os.name != "nt":
        return None, "не Windows — настоящей Корзины нет"
    base = fresh("c6")
    tmp, home = base / "tmp", base / "home"
    home.mkdir(parents=True)
    tmp.mkdir()
    stand = tmp / "mzs831-old"
    make_tree(stand, 260)
    when = time.time() - 72 * HOUR
    real = os.path.normcase(os.path.realpath(stand))
    (stand / mezo_stand.KEPT_MARKER).write_text(
        f"script=C:/elsewhere/bite-x.py\nargs=[]\nroot=\nkind=failed\nstand={real}\n"
        f"reason=прогон провалился\nat=2026-11-20T00:00:00Z\nat_ts={when!r}\npid=1\n", encoding="utf-8")
    os.utime(stand, (when, when))
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", MEZO_STAND_MAX_AGE_H="1")
    for name in ("MEZO_STAND_HOME", "MEZO_STAND_HOME_TEMP", "MEZO_KEEP_STANDS", "MEZO_STAND_TEST_BIN",
                 "MEZO_STAND_TEST_BIN_MB"):
        env.pop(name, None)
    for name in ("TMPDIR", "TEMP", "TMP"):
        env[name] = str(tmp)
    for name in ("HOME", "USERPROFILE"):
        env[name] = str(home)
    vroot = os.path.splitdrive(os.path.realpath(base))[0] + "\\"
    p = subprocess.run([sys.executable, "-X", "utf8", "-c", CHILD, str(helper)], env=env, capture_output=True,
                       text=True, encoding="utf-8", timeout=300)
    out = p.stdout
    line = next((s.strip() for s in out.splitlines() if s.startswith("🧺")), "строки уборки нет")
    calls = next((s.strip() for s in out.splitlines() if s.startswith("🧪")), "строки счётчика нет")
    on_place = os.path.lexists(ext(stand))
    in_bin = own_in_real_bin(vroot, os.path.realpath(base))
    IN_REAL_BIN.append(in_bin)
    ok = (p.returncode == 0 and on_place and "каталог не тронут" in out and "не перенесено: 1" in line
          and calls == "🧪 перенос Windows звался: 0" and in_bin == 0)
    drop(base)
    detail = (f"стенд на месте: {'да' if on_place else 'НЕТ'} · {line} · {calls} · в настоящей Корзине "
              f"записей из каталога ⑥: {'не прочитано' if in_bin is None else in_bin}")
    if p.returncode != 0:
        detail += f" · код потомка {p.returncode}: {(p.stderr or '').strip()[-300:]}"
    return ok, detail


def run_all(m, helper: Path) -> dict:
    results = {}
    for number, fn in (("①", c1), ("①б", c1b), ("②", c2), ("②б", c2b), ("③", c3), ("③б", c3b), ("④", c4),
                       ("⑤", c5)):
        try:
            results[number] = fn(m)
        except Exception as e:  # noqa: BLE001 — упавший случай есть провал, а не падение приёмки
            results[number] = (False, f"случай упал: {type(e).__name__}: {e}")
    try:
        results["⑥"] = c6(helper)
    except Exception as e:  # noqa: BLE001
        results["⑥"] = (False, f"случай упал: {type(e).__name__}: {e}")
    return results


def load_copy(tag: str, needle: str, replacement: str):
    """Копия помощника с одной нарочной поломкой: место обязано встретиться ровно один раз."""
    text = HELPER.read_text(encoding="utf-8")
    places = text.count(needle)
    if places != 1:
        return None, None, f"место поломки встречается {places} раз вместо одного — поломка не поставлена"
    folder = ROOT / "copies" / tag
    folder.mkdir(parents=True)
    path = folder / "mezo_stand.py"
    path.write_text(text.replace(needle, replacement), encoding="utf-8")
    spec = importlib.util.spec_from_file_location(f"mezo_stand_{tag}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path, None


def main() -> int:
    global ROOT
    ROOT = Path(os.path.realpath(mezo_stand.new("rbin831-")))
    print(f"каталог приёмки: {ROOT}\nпомощник под испытанием: {HELPER}\n", flush=True)
    intact = run_all(mezo_stand, HELPER)
    failed = [n for n in CASES if intact[n][0] is False]
    skipped = [n for n in CASES if intact[n][0] is None]
    for n in CASES:
        ok, detail = intact[n]
        mark = "⚪" if ok is None else ("✅" if ok else "🔴")
        print(f"{mark} {n} · {detail}", flush=True)

    print("\nНарочные поломки (в копиях помощника):", flush=True)
    blind = []
    for tag, what, needle, replacement, expect in BREAKS:
        module, path, why = load_copy(tag, needle, replacement)
        if module is None:
            blind.append(tag)
            print(f"🔴 {tag} ({what}): {why}", flush=True)
            continue
        got = run_all(module, path)
        fell = {n for n in CASES if got[n][0] is False}
        unknown = {n for n in CASES if got[n][0] is None}
        want = expect - unknown
        if not want:
            print(f"⚪ {tag} ({what}): не проверена — её случаи {' '.join(sorted(expect))} здесь не различают", flush=True)
            continue
        # провал падением случая — не его проверкой: поломку поймал бы любой сбой подставного тома (Н1 COORD)
        crashed = [n for n in CASES if n in fell and got[n][1].startswith("случай упал")]
        if fell == want and not crashed:
            print(f"✅ {tag} ({what}): провалились ровно {' '.join(n for n in CASES if n in fell)}", flush=True)
        elif fell == want:
            blind.append(tag)
            print(f"🔴 {tag} ({what}): провалились ровно свои случаи, но {' '.join(crashed)} — падением случая, "
                  f"а не его проверкой", flush=True)
            for n in crashed:
                print(f"      {n}: {got[n][1]}", flush=True)
        else:
            blind.append(tag)
            print(f"🔴 {tag} ({what}): ждали провала {' '.join(n for n in CASES if n in want)}, "
                  f"провалились {' '.join(n for n in CASES if n in fell) or 'ничего'}", flush=True)
            for n in CASES:
                if (n in fell) != (n in want):
                    print(f"      {n}: {got[n][1]}", flush=True)

    measured = [n for n in IN_REAL_BIN if n is not None]
    touched = sum(measured)
    unread = len(IN_REAL_BIN) - len(measured)
    code = 1 if failed or blind or touched else (2 if skipped else 0)
    if code == 2:
        mezo_stand.accepted_with_skips()
    print(f"\nИТОГ: случаев прошло {sum(1 for n in CASES if intact[n][0])} из {len(CASES)} · провалено: "
          f"{' '.join(failed) or 'нет'} · не проверено: {' '.join(skipped) or 'нет'} · поломок поймано "
          f"{len(BREAKS) - len(blind)} из {len(BREAKS)}" + (f" · слепы: {' '.join(blind)}" if blind else ""))
    if IN_REAL_BIN:
        print(f"Настоящая Корзина: прогонов ⑥ {len(IN_REAL_BIN)} (целый помощник и каждая поломка) · записей с путём "
              f"внутри каталога приёмки: {touched}" + (f" · записи не прочитаны в {unread}" if unread else ""))
    return code


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
