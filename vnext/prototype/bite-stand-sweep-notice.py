# -*- coding: utf-8 -*-
"""
bite-stand-sweep-notice.py — приёмка карточки #790: уборка стендов по сроку не молчит, видно, чей это
процесс, и тесты пакета не убирают живую временную папку.

Предмет. mezo_stand.py при первом new() верхнего прогона, не чаще раза в час на временную папку, переносит
в Корзину стенды старше срока (по умолчанию 48 ч). Обход идёт минуты. До правки он молчал, шёл внутри чужой
приёмки или теста, а выключатель MEZO_STAND_MAX_AGE_H=0 до тестов пакета не доходил: tests/conftest.py
выбрасывает из среды потомка все MEZO_*.

Случаи
  ①  строка перед обходом прочитана из потока потомка ДО его завершения: потомок стоит внутри обхода, старый
     стенд ещё на месте; в строке путь временной папки, срок в часах и слова о минутах; идёт она в stderr,
     в stdout её нет (приёмки, разбирающие stdout потомка, не ломаются)
  ①б встречный: срок 0 (уборка выключена) — строки нет, обхода нет
  ①в встречный: отметка свежая (обход не нужен) — строки нет, старый стенд цел
  ②  в той же строке номер процесса = номер потомка (не номер приёмки) и имя верхнего скрипта прогона;
     нет строки — случай не проверяется и это сказано (судить нечего, провал уже записан в ①)
  ②б образец — настоящий кандидат: при сроке 6 ч уходит в каталог вместо Корзины, и остаток носит имя
     «<имя>.removing-<номер>» с номером потомка (а не приёмки); строка, если она есть, называет тот же номер
  ③  тест пакета test_guard_all_green_on_fresh_circuit при истёкшей отметке и старом подставном стенде:
     чистка среды в tests/conftest.py отдаёт потомку выключатель и каталог вместо Корзины; тест прошёл,
     стенд на месте, каталог вместо Корзины пуст, отметка не тронута; время теста — числом

Нарочные поломки (в КОПИЯХ файлов; ключ называет копию, приёмка запускает именно её и пишет ступень
«копия запустилась»):
  --tool <mezo_stand.py>   П1: копия помощника без строки перед обходом — ждём провала РОВНО ①
  --conftest <conftest.py> П2: копия tests/conftest.py, где тест снова берёт срок по умолчанию (выключатель
                           не доходит, каталог вместо Корзины доходит) — ждём провала РОВНО ③
  --expect <номера>        ожидание нарочной поломки; записывается в файл ДО прогона

Безопасность. Приёмка живёт в своём временном каталоге, и каждый потомок получает свои TEMP, TMP, TMPDIR,
HOME, USERPROFILE и MEZO_STAND_TEST_BIN внутри него; каталог снаружи — отказ ДО запуска. Срок для потомков
назначается явно. Живая временная папка и настоящая Корзина не участвуют ни в одном запуске.

Время. Случай ③ идёт минуты: тест зовёт guard-all.py дважды. Запускай приёмку через обёртку прогона с
пределом времени побольше (SANDBOX_LIMIT_S=1500).

    python bite-stand-sweep-notice.py
    python bite-stand-sweep-notice.py --tool <копия mezo_stand.py> --expect ①
    python bite-stand-sweep-notice.py --conftest <копия conftest.py> --expect ③
    python bite-stand-sweep-notice.py --no-test        # только ①–②б (для отладки: ③ не проверяется, код 2)
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK = HERE.parent.parent             # корень пакета: рядом лежат scripts/ и tests/
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402

MARKER = ".mezo_stand_kept"
SWEEP_STAMP = ".mezo_stand_sweep"
HOUR = 3600
NOTICE_HEAD = "уборка стендов по сроку: обхожу"
TEST_ID = "tests/test_tools.py::test_guard_all_green_on_fresh_circuit"
TERM_H = "6"                          # срок для потомков: назначается явно
OLD_NAME = "swnt-old-stand"

RESULTS: list[tuple[str, bool | None]] = []      # (номер случая, True/False; None — не проверялся)
ROOT: Path | None = None


def case(number: str, title: str, ok: bool | None, detail: str) -> None:
    RESULTS.append((number, ok))
    mark = "⚪" if ok is None else ("✅" if ok else "🔴")
    print(f"{mark} {number} {title}\n   {detail}", flush=True)


def inside_root(path) -> bool:
    if ROOT is None or not str(path):
        return False
    root = os.path.normcase(os.path.realpath(ROOT))
    try:
        return os.path.commonpath([os.path.normcase(os.path.realpath(path)), root]) == root
    except ValueError:
        return False


def child_env(tmp: Path, home: Path, bin_dir: Path, extra=None) -> dict:
    """Среда потомка: свои временная и домашняя папка и каталог вместо Корзины — всё внутри каталога приёмки."""
    for folder in (tmp, home, bin_dir):
        if not inside_root(folder):
            sys.exit(f"НЕ ЗАПУСТИЛАСЬ: потомок получил бы каталог ВНЕ каталога приёмки — {folder} (каталог приёмки: {ROOT})")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    for name in ("MEZO_STAND_HOME", "MEZO_STAND_HOME_TEMP", "MEZO_KEEP_STANDS", "MEZO_STAND_MAX_AGE_H",
                 "MEZO_STAND_TEST_BIN_MB", "MEZO_SCRIPTS_ROOT", "PROBE_WAIT"):
        env.pop(name, None)
    for name in ("TMPDIR", "TEMP", "TMP"):
        env[name] = str(tmp)
    for name in ("HOME", "USERPROFILE"):
        env[name] = str(home)
    env["MEZO_STAND_TEST_BIN"] = str(bin_dir)
    env.update(extra or {})
    return env


def real(path) -> str:
    return os.path.normcase(os.path.realpath(path))


def make_old_stand(tmp: Path, hours: float = 72.0, name: str = OLD_NAME) -> Path:
    """Старый стенд-образец: каталог с файлом, меткой «провал» и датой давностью hours часов."""
    d = tmp / name
    d.mkdir(parents=True)
    (d / "data.txt").write_text("x", encoding="utf-8")
    when = time.time() - hours * HOUR
    (d / MARKER).write_text(
        f"script=C:/elsewhere/bite-x.py\nargs=[]\nroot=\nkind=failed\nstand={real(d)}\n"
        f"reason=прогон провалился\nat=2026-10-10T00:00:00Z\nat_ts={when!r}\npid=1\n", encoding="utf-8")
    os.utime(d, (when, when))
    return d


def set_stamp(tmp: Path, hours_ago: float | None) -> Path:
    """Отметка уборки по сроку в корне временной папки: None — нет её, иначе давностью hours_ago часов."""
    stamp = tmp / SWEEP_STAMP
    if hours_ago is not None:
        stamp.write_text("x", encoding="utf-8")
        when = time.time() - hours_ago * HOUR
        os.utime(stamp, (when, when))
    return stamp


def in_bin(bin_dir: Path, stand: Path) -> list[str]:
    """Имена в каталоге вместо Корзины, начатые именем стенда."""
    if not bin_dir.is_dir():
        return []
    return sorted(x.name for x in bin_dir.iterdir() if x.name.startswith(stand.name))


# Подставная проверка. Заводит стенд помощником и ЖДЁТ внутри обхода (подмена _aged_candidates): пока
# приёмка не даст сигнал, потомок стоит на первом шаге обхода — строка перед обходом обязана быть уже в потоке.
PROBE = """# -*- coding: utf-8 -*-
import os
import sys
import tempfile
import time
import mezo_stand
print('TOOL=' + mezo_stand.__file__, flush=True)
print('TEMP=' + tempfile.gettempdir(), flush=True)
print('PID=' + str(os.getpid()), flush=True)
_orig = mezo_stand._aged_candidates


def _slow(temp, limit_s):
    print('SWEEP_STARTED', flush=True)
    wait = os.environ.get('PROBE_WAIT')
    deadline = time.time() + 60
    while wait and not os.path.exists(wait) and time.time() < deadline:
        time.sleep(0.05)
    return _orig(temp, limit_s)


mezo_stand._aged_candidates = _slow
r = mezo_stand.new('swnt-probe-')
print('STAND=' + str(r), flush=True)
sys.exit(mezo_stand.finish(0))
"""


class Child:
    """Запущенный потомок: потоки stdout и stderr читаются построчно по мере появления."""

    def __init__(self, argv, cwd, env):
        self.proc = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
                                     bufsize=1)
        self.out: list[str] = []
        self.err: list[str] = []
        self._threads = [threading.Thread(target=self._pump, args=(self.proc.stdout, self.out), daemon=True),
                         threading.Thread(target=self._pump, args=(self.proc.stderr, self.err), daemon=True)]
        for t in self._threads:
            t.start()

    @staticmethod
    def _pump(stream, sink):
        for line in stream:
            sink.append(line.rstrip("\r\n"))

    def seen(self, stream: str, needle: str) -> bool:
        return any(needle in ln for ln in list(self.out if stream == "out" else self.err))

    def wait_for(self, stream: str, needle: str, seconds: float) -> bool:
        end = time.time() + seconds
        while time.time() < end:
            if self.seen(stream, needle):
                return True
            if self.proc.poll() is not None:
                time.sleep(0.2)
                return self.seen(stream, needle)
            time.sleep(0.05)
        return self.seen(stream, needle)

    def finish(self, seconds: float = 90) -> int:
        try:
            self.proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait()
        for t in self._threads:
            t.join(timeout=10)
        return self.proc.returncode

    def tagged(self, tag: str) -> str | None:
        for ln in self.out:
            if ln.startswith(tag + "="):
                return ln[len(tag) + 1:].strip()
        return None


class Lab:
    """Песочница одного случая: свои временная папка, дом и каталог вместо Корзины; рядом — подставная проверка."""

    def __init__(self, name: str, tool: Path):
        self.base = ROOT / name
        self.tmp, self.home, self.bin, self.host = (self.base / n for n in ("t", "h", "b", "x"))
        for d in (self.tmp, self.home, self.bin, self.host):
            d.mkdir(parents=True)
        shutil.copy2(tool, self.host / "mezo_stand.py")
        (self.host / "probe.py").write_text(PROBE, encoding="utf-8")
        self.go = self.base / "go.signal"

    def start(self, max_age: str, hold: bool) -> Child:
        """Запустить потомка со сроком max_age. hold — он ждёт внутри обхода сигнала self.go; иначе сигнал уже дан."""
        if not hold:
            self.go.write_text("go", encoding="utf-8")
        env = child_env(self.tmp, self.home, self.bin, {"MEZO_STAND_MAX_AGE_H": max_age, "PROBE_WAIT": str(self.go)})
        return Child([sys.executable, "-X", "utf8", "probe.py"], self.host, env)


def notice_of(child: Child) -> str | None:
    return next((ln for ln in child.err if NOTICE_HEAD in ln), None)


def sweep_cases(tool: Path) -> None:
    # ① строка перед обходом, прочитанная из потока живого потомка, пока он стоит внутри обхода
    lab = Lab("c1", tool)
    old = make_old_stand(lab.tmp)
    stamp = set_stamp(lab.tmp, None)
    child = lab.start(TERM_H, hold=True)
    in_sweep = child.wait_for("out", "SWEEP_STARTED", 40)
    got = child.wait_for("err", NOTICE_HEAD, 4) if in_sweep else False
    alive = child.proc.poll() is None
    old_there = old.exists() and not in_bin(lab.bin, old)
    line = notice_of(child)
    child_temp = child.tagged("TEMP")
    tool_seen = child.tagged("TOOL")
    lab.go.write_text("go", encoding="utf-8")
    rc = child.finish()
    print(f"   СТУПЕНЬ копия запустилась: потомок загрузил помощника из {tool_seen} · "
          f"{'это' if tool_seen and real(tool_seen) == real(lab.host / 'mezo_stand.py') else 'НЕ ЭТО'} "
          f"копия, данная приёмкой ({tool}) · код потомка {rc}", flush=True)
    ok_line = bool(line and child_temp and child_temp in line and f"срок {TERM_H} ч" in line and "минуты" in line)
    stdout_clean = not child.seen("out", NOTICE_HEAD)
    case("①", "строка перед обходом прочитана из потока потомка ДО его завершения: потомок стоит внутри "
              "обхода, старый стенд на месте; в строке путь, срок в часах и слова о минутах; идёт она в stderr",
         in_sweep and got and alive and old_there and ok_line and stdout_clean and rc == 0,
         f"потомок дошёл до обхода: {in_sweep} · строка в потоке: {got} · потомок жив: {alive} · старый стенд "
         f"на месте: {old_there} · путь и срок и «минуты» в строке: {ok_line} · в stdout строки нет: {stdout_clean} · "
         f"код потомка: {rc} · строка: {line or 'НЕТ'}")

    # ②б образец ушёл в каталог вместо Корзины, остаток несёт номер потомка (а не приёмки)
    pid = child.proc.pid
    left = in_bin(lab.bin, old)
    tails = [n.rpartition(".removing-")[2] for n in left]
    ok_rest = len(left) == 1 and tails == [str(pid)] and str(pid) != str(os.getpid()) and not old.exists()
    detail_rest = (f"в каталоге вместо Корзины: {left or 'пусто'} · номер потомка: {pid} · номер приёмки: "
                   f"{os.getpid()} · стенд из временной папки ушёл: {not old.exists()} · каталог вместо Корзины: {lab.bin}")

    # ② номер процесса и имя скрипта в той же строке
    if line is None:
        case("②", "в строке номер процесса = номер потомка и имя верхнего скрипта", None,
             "не проверялся: строки перед обходом нет — судить нечего (провал записан в ①)")
    else:
        m_pid = re.search(r"pid=(\d+)", line)
        m_name = re.search(r"верхний скрипт прогона: (\S+)", line)
        line_pid = m_pid.group(1) if m_pid else None
        printed = child.tagged("PID")
        ok2 = (line_pid == str(pid) and line_pid != str(os.getpid()) and m_name is not None
               and m_name.group(1) == "probe.py" and (not tails or tails == [line_pid]))
        case("②", "в строке номер процесса = номер потомка (не приёмки), названо имя верхнего скрипта прогона, "
                  "тот же номер у остатка «.removing-<номер>»",
             ok2,
             f"номер в строке: {line_pid} · номер потомка: {pid} (сам потомок назвал {printed}) · номер приёмки: "
             f"{os.getpid()} · скрипт в строке: {m_name.group(1) if m_name else 'НЕТ'} (запущен probe.py) · "
             f"номер у остатка: {tails[0] if tails else 'нет остатка'}")
    case("②б", "образец — настоящий кандидат: при сроке 6 ч уходит в каталог вместо Корзины; остаток носит "
               "«<имя>.removing-<номер>» с номером потомка, а не приёмки", ok_rest, detail_rest)

    # ①б встречный: срок 0 — строки нет, обхода нет, отметка не ставится
    lab = Lab("c1b", tool)
    old = make_old_stand(lab.tmp)
    stamp = set_stamp(lab.tmp, None)
    child = lab.start("0", hold=False)
    rc = child.finish()
    case("①б", "встречный: срок 0 (уборка выключена) — строки нет, обхода нет, отметки нет, старый стенд цел",
         rc == 0 and notice_of(child) is None and not child.seen("out", "SWEEP_STARTED") and old.exists()
         and not stamp.exists(),
         f"код потомка: {rc} · строки нет: {notice_of(child) is None} · обхода нет: "
         f"{not child.seen('out', 'SWEEP_STARTED')} · старый стенд цел: {old.exists()} · отметки нет: {not stamp.exists()}")

    # ①в встречный: отметка свежая — обход не нужен, строки нет
    lab = Lab("c1c", tool)
    old = make_old_stand(lab.tmp)
    stamp = set_stamp(lab.tmp, 0.2)
    before = stamp.stat().st_mtime
    child = lab.start(TERM_H, hold=False)
    rc = child.finish()
    case("①в", "встречный: отметка свежая (обход не нужен) — строки нет, обхода нет, старый стенд цел",
         rc == 0 and notice_of(child) is None and not child.seen("out", "SWEEP_STARTED") and old.exists()
         and stamp.stat().st_mtime == before,
         f"код потомка: {rc} · строки нет: {notice_of(child) is None} · обхода нет: "
         f"{not child.seen('out', 'SWEEP_STARTED')} · старый стенд цел: {old.exists()} · отметка не тронута: "
         f"{stamp.stat().st_mtime == before}")


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def build_kit(kit: Path, conftest: Path) -> None:
    """Копия пакета (без истории и кэшей) с подставленным tests/conftest.py: тест идёт НА КОПИИ, рабочее дерево чисто."""
    ignore = shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", "graphify-out", "node_modules")
    shutil.copytree(PACK, kit, ignore=ignore)
    shutil.copyfile(conftest, kit / "tests" / "conftest.py")


def test_case(conftest: Path) -> None:
    """③: тест свежего контура при истёкшей отметке и старом стенде во временной папке приёмки."""
    lab_base = ROOT / "c3"
    tmp, home, bin_dir, kit, basetemp = (lab_base / n for n in ("t", "h", "b", "k", "p"))
    for d in (tmp, home, bin_dir):
        d.mkdir(parents=True)
    build_kit(kit, conftest)
    old = make_old_stand(tmp)
    stamp = set_stamp(tmp, 3.0)
    stamp_before = stamp.stat().st_mtime
    # срок для самого pytest не назначается: выключатель обязан дойти до потомков через чистку среды conftest
    env = child_env(tmp, home, bin_dir)
    argv = [sys.executable, "-X", "utf8", "-m", "pytest", "-p", "no:cacheprovider", "-q", "--trace-config",
            f"--basetemp={basetemp}", TEST_ID]
    t0 = time.time()
    try:
        p = subprocess.run(argv, cwd=kit, env=env, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=1300, stdin=subprocess.DEVNULL)
        rc, text = p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired as e:
        rc, text = -1, (e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
    wall = time.time() - t0
    (lab_base / "pytest-output.txt").write_text(text, encoding="utf-8")
    # ступень «копия запустилась»: pytest зарегистрировал conftest из копии пакета, и он байт в байт равен данному
    loaded = re.findall(r"conftest' from '([^']*)'", text) or re.findall(r"conftest[^\n]*from '([^']*)'", text)
    kit_conftest = kit / "tests" / "conftest.py"
    loaded = [x.replace("\\\\", "\\") for x in loaded]        # repr модуля удваивает обратные косые черты
    registered = any(real(x) == real(kit_conftest) for x in loaded)
    print(f"   СТУПЕНЬ копия запустилась: pytest зарегистрировал conftest из {loaded[:1] or 'НИОТКУДА'} · "
          f"{'это' if registered else 'НЕ ЭТО'} файл копии пакета · хэш копии {sha(kit_conftest)} · "
          f"хэш данного файла {sha(conftest)} · путь: {conftest}", flush=True)
    m = re.search(r"(\d+) passed in ([\d.]+)s", text)
    passed = bool(m) and m.group(1) == "1" and "failed" not in (m.group(0) if m else "")
    seconds = m.group(2) if m else "нет"
    stand_there = old.exists() and not in_bin(bin_dir, old)
    bin_names = sorted(x.name for x in bin_dir.iterdir()) if bin_dir.is_dir() else []
    stamp_same = stamp.exists() and stamp.stat().st_mtime == stamp_before
    # проба самой чистки среды: тот же clean_env из файла копии — срок 0 и каталог вместо Корзины стоят в среде потомка
    probe = subprocess.run(
        [sys.executable, "-X", "utf8", "-c",
         "import sys; sys.path.insert(0, 'tests'); import conftest; e = conftest.clean_env(sys.argv[1]); "
         "print('AGE=' + e.get('MEZO_STAND_MAX_AGE_H', 'НЕТ')); print('BIN=' + e.get('MEZO_STAND_TEST_BIN', 'НЕТ'))",
         str(home / "probe-home")],
        cwd=kit, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    age = re.search(r"AGE=(.*)", probe.stdout or "")
    bin_env = re.search(r"BIN=(.*)", probe.stdout or "")
    age_ok = bool(age and age.group(1).strip() == "0")
    bin_ok = bool(bin_env and real(bin_env.group(1).strip()) == real(bin_dir))
    env_ok = age_ok and bin_ok
    case("③", "тест пакета test_guard_all_green_on_fresh_circuit при истёкшей отметке и старом стенде: чистка среды "
              "отдаёт потомку выключатель и каталог вместо Корзины; тест прошёл, стенд на месте, каталог вместо "
              "Корзины пуст, отметка не тронута; время теста числом",
         rc == 0 and registered and passed and stand_there and not bin_names and stamp_same and env_ok,
         f"код pytest: {rc} · итог pytest: {m.group(0) if m else 'нет строки «1 passed»'} · время теста: {seconds} с "
         f"(стена приёмки {wall:.0f} с) · старый стенд на месте: {stand_there} · каталог вместо Корзины "
         f"({bin_dir}): {bin_names or 'пуст'} · отметка не тронута: {stamp_same} · clean_env отдаёт срок "
         f"{age.group(1).strip() if age else 'НЕТ'} (выключатель доходит: {age_ok}) и каталог вместо Корзины "
         f"(доходит: {bin_ok}) · вывод pytest: "
         f"{lab_base / 'pytest-output.txt'}")


def main() -> int:
    global ROOT
    ap = argparse.ArgumentParser(description="приёмка карточки #790: строка перед обходом уборки и тесты без живой уборки")
    ap.add_argument("--tool", default=str(HERE / "mezo_stand.py"), help="помощник под испытанием (копия с поломкой П1)")
    ap.add_argument("--conftest", default=str(PACK / "tests" / "conftest.py"),
                    help="tests/conftest.py под испытанием (копия с поломкой П2)")
    ap.add_argument("--expect", default="", help="нарочная поломка: номера случаев, которые обязаны провалиться (через пробел)")
    ap.add_argument("--no-test", action="store_true", help="отладка: случай ③ не выполнять (код 2)")
    a = ap.parse_args()
    tool, conftest = Path(a.tool).resolve(), Path(a.conftest).resolve()
    for need in (tool, conftest):
        if not need.is_file():
            sys.exit(f"НЕ ЗАПУСТИЛАСЬ: файла нет — {need}")
    ROOT = Path(os.path.realpath(mezo_stand.new("swnt-")))
    print(f"каталог приёмки: {ROOT}\nпомощник под испытанием: {tool}\nconftest под испытанием: {conftest}\n", flush=True)
    expect = a.expect.split()
    if expect:
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА: ждём провала РОВНО {' '.join(expect)} (записано до прогона)\n", flush=True)
    sweep_cases(tool)
    skipped_pytest = a.no_test or not (PACK / "tests" / "test_tools.py").is_file()
    if skipped_pytest:
        why = "ключ --no-test" if a.no_test else f"тестов пакета рядом нет ({PACK / 'tests'})"
        case("③", "тест пакета при истёкшей отметке и старом стенде", None, f"не проверялся: {why}")
        mezo_stand.accepted_with_skips()
    else:
        test_case(conftest)

    failed = [n for n, ok in RESULTS if ok is False]
    skipped = [n for n, ok in RESULTS if ok is None]
    passed = [n for n, ok in RESULTS if ok]
    print("")
    code = 0 if not failed else 1
    if expect:
        if set(expect) == set(failed):
            print(f"🧪 ожидание поломки подтвердилось: → не проходит РОВНО {' '.join(failed)} · остальные случаи "
                  f"прошли или названы непроверенными: {' '.join(skipped) or 'нет'}")
            mezo_stand.expected_break()
        else:
            code = 1
            print(f"⚠️ ожидание поломки НЕ подтвердилось: ждали {' '.join(expect)}, провалены {' '.join(failed) or 'ничего'}")
    elif skipped_pytest and not failed:
        code = 2
    print(f"ИТОГ: прошло {len(passed)} из {len(RESULTS)} · провалено: {' '.join(failed) or 'нет'} · "
          f"не проверено: {' '.join(skipped) or 'нет'} · случаи: {' '.join(n for n, _ in RESULTS)}")
    return code


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
