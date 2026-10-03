# -*- coding: utf-8 -*-
"""
bite-stand-keep-last.py — приёмка: mezo_stand.py хранит при провале стенды только ПОСЛЕДНЕГО
прогона того же вызова приёмки (карточка #657, пункт (3); слово владельца «Б1» 02.10.2026 23:47 UTC,
чат OPSSRE; план и два дополнения — комментарии карточки, согласованы с PROTO записками #5422 и #5437;
доделка по возврату PROTO 03.10 01:38 UTC, записка #5452 — случаи ③б ⑤б ⑩б ⑬–㉖).

Проверяет ЗАПУСКОМ: поднимает подставные скрипты, которые заводят стенды помощником и кончаются
как велено, и смотрит, что осталось на диске. Стенды подставных скриптов ложатся в песочницу
этой приёмки (TEMP/TMP подставлены) — живую временную папку и живую базу она не трогает.

Автор — OPSSRE, приёмщик — PROTO (автор не принимает своё).

    python bite-stand-keep-last.py                      # все случаи на помощнике рядом
    python bite-stand-keep-last.py --helper <путь>      # на другом помощнике (прежнем — для сравнения)
    python bite-stand-keep-last.py --break <имя>        # нарочная поломка; ожидаемые провалы — BREAK_FAILS
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402

MARKER = ".mezo_stand_kept"
PREFIX = "keep-last-p-"
PREFIX_2 = "keep-last-q-"

# Строки помощника, которые судит приёмка. Числа ищутся ЦЕЛЫМ словом (см. said).
SAID_FAIL = "стендов прежнего провала этого вызова убрано:"
SAID_OTHER = "стендов прежнего отказа или падения этого вызова убрано:"
SAID_KEPT = "стенды прежних неудачных прогонов этого вызова сохранены:"
SAID_BUSY = "занято, не тронуто:"
SAID_ANY_PRUNE = "этого вызова убрано"

# Нарочные поломки: список замен (что заменить в помощнике, на что). Каждая заменяемая строка
# обязана встретиться ровно один раз — иначе помощник менялся, и приёмку надо править, а не гадать.
BREAKS = {
    "name-key": [("    return os.path.normcase(str(p.resolve()))",
                  "    return os.path.normcase(p.name)")],
    "dir-key": [("    return os.path.normcase(str(p.resolve()))",
                 "    return os.path.normcase(str(p.resolve().parent))")],
    "args-ignored": [('        "args": json.dumps(sys.argv[1:], ensure_ascii=True),',
                      '        "args": "",')],
    "root-ignored": [('        "root": _real(root) if root else "",',
                      '        "root": "",')],
    "cwd-ignored": [('        "cwd": cwd,',
                     '        "cwd": "",')],
    "no-marker-check": [("            marker = _read_marker(Path(entry.path) / KEPT_MARKER)",
                         "            marker = _read_marker(Path(entry.path) / KEPT_MARKER) or "
                         "dict(call, kind=\"failed\", stand=_real(entry.path), at_ts=\"0\")")],
    "keep-env-pruned": [('_KIND_GROUPS = {"failed": "failed", "refused": "other", "undeclared": "other"}',
                         '_KIND_GROUPS = {"failed": "failed", "refused": "other", "undeclared": "other", '
                         '"keep_env": "failed"}')],
    "keepenv-run-prunes": [("    if kind == _KIND_KEEP_ENV:",
                            "    if False:"),
                           ("        group = _KIND_GROUPS[kind]",
                            "        group = _KIND_GROUPS.get(kind, \"failed\")")],
    "no-prune": [("        removed, left = _remove_previous(_previous_kept(_CALL_KEY, kinds, before=_RUN_STARTED))",
                  "        removed, left = 0, []")],
    "kinds-mixed": [("        kinds = {k for k, g in _KIND_GROUPS.items() if g == group}",
                     "        kinds = set(_KIND_GROUPS)")],
    "start-ignored": [('                    if float(marker.get("at_ts", "")) >= before:',
                       "                    if False:")],
    "marker-at-new": [("    _prefixes.add(prefix)\n    return p",
                       "    _prefixes.add(prefix)\n"
                       "    if _CALL_KEY is not None:\n"
                       "        (p / KEPT_MARKER).write_text(\"\".join(f\"{k}={v}\\n\" for k, v in dict(\n"
                       "            _CALL_KEY, kind=\"failed\", stand=_real(p), at_ts=repr(time.time())).items()),\n"
                       "            encoding=\"utf-8\")\n"
                       "    return p")],
    "no-stand-check": [('            if marker.get("stand") != _real(entry.path):',
                        "            if False:")],
    "links-followed": [("                if _is_link(entry) or not entry.is_dir(follow_symlinks=False):",
                        "                if not entry.is_dir(follow_symlinks=False):")],
    "no-rename-probe": [("            os.rename(p, probe)",
                         "            probe = p")],
    "release-no-prefix": [("        _prefixes.add(p.name[:-_MKDTEMP_SUFFIX])",
                           "        pass")],
    "zero-line": [("        if removed or left:",
                   "        if True:")],
    "refuse-as-fail": [('        return "прогон отказался мерить" if _exit_code == 2 else "прогон провалился"',
                        '        return "прогон провалился"')],
    "break-ignored": [("    _expected_break = True",
                       "    _expected_break = False")],
    "break-any-code": [("    return _expected_break and _exit_code == 1",
                        "    return _expected_break")],
    "success-silent": [("        if previous:",
                        "        if False:")],
}
# Какие случаи ОБЯЗАНЫ провалиться при каждой поломке — записано ДО прогона.
BREAK_FAILS = {
    "name-key": ["③"],
    "dir-key": ["③б"],
    "args-ignored": ["⑪", "⑬"],
    "root-ignored": ["⑭"],
    "cwd-ignored": ["⑪", "⑮"],
    "no-marker-check": ["④", "⑲"],
    "keep-env-pruned": ["⑤"],
    "keepenv-run-prunes": ["⑤б"],
    "no-prune": ["①", "②", "⑦", "⑨", "⑬", "⑭", "㉑", "㉒", "㉔"],
    "kinds-mixed": ["⑯", "⑰", "⑱"],
    "start-ignored": ["⑳"],
    "marker-at-new": ["⑲"],
    "no-stand-check": ["㉒"],
    "links-followed": ["㉓"],
    "no-rename-probe": ["㉑"],
    "release-no-prefix": ["㉔"],
    "zero-line": ["③", "④", "㉓"],
    "refuse-as-fail": ["⑨"],
    "break-ignored": ["⑩", "⑩б"],
    "break-any-code": ["㉕"],
    "success-silent": ["⑥"],
}
CASE_IDS = ["①", "②", "③", "③б", "④", "⑤", "⑤б", "⑥", "⑦", "⑧", "⑨", "⑩", "⑩б", "⑪", "⑫",
            "⑬", "⑭", "⑮", "⑯", "⑰", "⑱", "⑲", "⑳", "㉑", "㉒", "㉓", "㉔", "㉕", "㉖"]

OUTCOMES = {
    "ok": ["sys.exit(mezo_stand.finish(0))"],
    "fail": ["sys.exit(mezo_stand.finish(1))"],
    "refuse": ["sys.exit(mezo_stand.finish(2))"],
    "crash": ["raise SystemExit('упало до объявления исхода')"],
    "break_ok": ["mezo_stand.expected_break()", "sys.exit(mezo_stand.finish(1))"],
    "break_refuse": ["mezo_stand.expected_break()", "sys.exit(mezo_stand.finish(2))"],
    "break_then_crash": ["mezo_stand.expected_break()", "raise SystemExit('упало после объявления поломки')"],
    # ждёт файла-сигнала из PROBE_WAIT (не дольше минуты), потом провал — для параллельного случая
    "wait_fail": ["import os, time",
                  "w = os.environ.get('PROBE_WAIT')",
                  "deadline = time.time() + 60",
                  "while w and not os.path.exists(w) and time.time() < deadline: time.sleep(0.05)",
                  "sys.exit(mezo_stand.finish(1))"],
}

RESULTS: list[tuple[str, bool]] = []


def case(number: str, title: str, ok: bool, detail: str) -> None:
    RESULTS.append((number, bool(ok)))
    print(f"{'✅' if ok else '🔴'} {number} {title}\n   {detail}")


def said(out: str, phrase: str, n: int) -> bool:
    """Строка с числом n ЦЕЛЫМ словом: «убрано: 1» не находится в «убрано: 10» (находка PROTO)."""
    return re.search(re.escape(phrase) + rf" {n}(?!\d)", out) is not None


def real(path) -> str:
    return os.path.normcase(os.path.realpath(path))


class Lab:
    """Песочница одного случая: каталог временной папки для стендов и каталоги подставных скриптов."""

    def __init__(self, root: Path, name: str, helper: Path):
        self.base = root / name
        self.tmp = self.base / "tmp"
        self.tmp.mkdir(parents=True)
        self.helper = helper

    def script(self, outcome: str, prefixes=(PREFIX,), host: str = "host-a", name: str = "probe.py",
               use_release: bool = False) -> tuple[Path, str]:
        """Положить подставной скрипт и помощник рядом. Вернуть (путь скрипта, его текст)."""
        host_dir = self.base / host
        host_dir.mkdir(exist_ok=True)
        shutil.copy2(self.helper, host_dir / "mezo_stand.py")
        lines = ["# -*- coding: utf-8 -*-", "import sys", "import tempfile", "from pathlib import Path",
                 "import mezo_stand"]
        for prefix in prefixes:
            if use_release:
                lines.append(f"r = Path(tempfile.mkdtemp(prefix={prefix!r})); mezo_stand.release(r)")
            else:
                lines.append(f"r = mezo_stand.new({prefix!r})")
            lines.append("(r / 'data.txt').write_text('x', encoding='utf-8'); print('STAND=' + str(r), flush=True)")
        lines += OUTCOMES[outcome]
        code = "\n".join(lines) + "\n"
        path = host_dir / name
        path.write_text(code, encoding="utf-8")
        return path, code

    def env(self, env_extra=None) -> dict:
        env = dict(os.environ, PYTHONIOENCODING="utf-8",
                   TMP=str(self.tmp), TEMP=str(self.tmp), TMPDIR=str(self.tmp))
        for name in ("MEZO_KEEP_STANDS", "MEZO_SCRIPTS_ROOT", "PROBE_WAIT"):
            env.pop(name, None)
        env.update(env_extra or {})
        return env

    def run(self, outcome: str, prefixes=(PREFIX,), host: str = "host-a", env_extra=None, via_c=False,
            name: str = "probe.py", args=(), cwd: Path | None = None, use_release=False):
        """Запустить подставной скрипт. Вернуть (стенды, вывод, код выхода).

        cwd не задан — запуск из каталога скрипта коротким именем; задан — из него полным путём.
        """
        path, code = self.script(outcome, prefixes, host, name, use_release)
        if via_c:
            cmd = [sys.executable, "-c", code]
            run_dir = path.parent
        elif cwd is None:
            cmd = [sys.executable, path.name, *args]
            run_dir = path.parent
        else:
            cwd.mkdir(parents=True, exist_ok=True)
            cmd = [sys.executable, str(path), *args]
            run_dir = cwd
        p = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=self.env(env_extra))
        out = (p.stdout or "") + (p.stderr or "")
        return stands_of(out), out, p.returncode


def stands_of(out: str) -> list[Path]:
    return [Path(m.strip()) for m in re.findall(r"STAND=(.+)", out)]


def marker_fields(stand: Path) -> dict | None:
    """Поля метки стенда; None — метки нет."""
    m = stand / MARKER
    if not m.is_file():
        return None
    fields = {}
    for line in m.read_text(encoding="utf-8").splitlines():
        name, sep, value = line.partition("=")
        if sep:
            fields[name] = value
    return fields


def marker_kind(stand: Path) -> str | None:
    """Вид исхода из метки стенда; None — метки нет."""
    fields = marker_fields(stand)
    return None if fields is None else fields.get("kind", "")


def make_link(link: Path, target: Path) -> None:
    """Ссылка на каталог: junction на Windows, symlink в остальных системах."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        os.symlink(target, link, target_is_directory=True)


def apply_break(helper: Path, name: str, dest: Path) -> Path:
    src = helper.read_text(encoding="utf-8")
    for old, new in BREAKS[name]:
        if src.count(old) != 1:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: место нарочной поломки «{name}» встречается {src.count(old)} раз "
                  f"вместо одного — помощник менялся, правь приёмку")
            sys.exit(mezo_stand.finish(2))
        src = src.replace(old, new, 1)
    dest.mkdir(parents=True, exist_ok=True)
    broken = dest / "mezo_stand.py"
    broken.write_text(src, encoding="utf-8")
    return broken


def run_cases(root: Path, helper: Path) -> None:
    # ① ВСТРЕЧНЫЙ ИЗ КРИТЕРИЯ КАРТОЧКИ: два провала подряд → остаются стенды только второго
    lab = Lab(root, "c1", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), out2, _ = lab.run("fail")
    case("①", "два провала одного вызова подряд — остаются стенды только второго, у второго метка",
         not s1.exists() and s2.exists() and marker_kind(s2) == "failed" and said(out2, SAID_FAIL, 1),
         f"первый на месте: {s1.exists()} · второй на месте: {s2.exists()} · метка второго: {marker_kind(s2)} · "
         f"строка «убрано: 1»: {said(out2, SAID_FAIL, 1)}")

    # ② два начала имён в одном прогоне — второй провал убирает оба стенда первого
    lab = Lab(root, "c2", helper)
    (a1, b1), _, _ = lab.run("fail", prefixes=(PREFIX, PREFIX_2))
    (a2, b2), out2, _ = lab.run("fail", prefixes=(PREFIX, PREFIX_2))
    case("②", "два начала имён в прогоне — второй провал убрал оба стенда первого",
         not a1.exists() and not b1.exists() and a2.exists() and b2.exists() and said(out2, SAID_FAIL, 2),
         f"первые на месте: {a1.exists()}, {b1.exists()} · вторые на месте: {a2.exists()}, {b2.exists()}")

    # ③ ДРУГОЙ скрипт с тем же именем файла и тем же началом имени (копия пакета у соседа);
    #    оба запущены из ОДНОГО рабочего каталога — иначе различал бы каталог, а не путь скрипта
    lab = Lab(root, "c3", helper)
    common = lab.base / "common-cwd"
    (sb,), _, _ = lab.run("fail", host="host-b", cwd=common)
    (sa,), out_a, _ = lab.run("fail", host="host-a", cwd=common)
    case("③", "чужой скрипт с тем же именем файла и началом имени — его провал цел, строки уборки нет",
         sb.exists() and sa.exists() and SAID_ANY_PRUNE not in out_a,
         f"стенд другого скрипта на месте: {sb.exists()} · свой на месте: {sa.exists()} · "
         f"строка уборки: {'есть' if SAID_ANY_PRUNE in out_a else 'нет'}")

    # ③б ДРУГОЙ скрипт в ТОМ ЖЕ каталоге с тем же началом имени (живая пара: bite-stale-urgency.py
    #     и bite-urgency-threshold.py — обе new("bite-urgency-"); находка PROTO Д2)
    lab = Lab(root, "c3b", helper)
    (so,), _, _ = lab.run("fail", name="probe2.py")
    (sa,), _, _ = lab.run("fail")
    case("③б", "второй скрипт в том же каталоге с тем же началом имени — его провал цел",
         so.exists() and sa.exists(),
         f"стенд соседнего скрипта на месте: {so.exists()} · свой на месте: {sa.exists()}")

    # ④ каталог того же начала имени БЕЗ метки — так выглядит прогон, который идёт сейчас
    lab = Lab(root, "c4", helper)
    running = lab.tmp / (PREFIX + "running1")
    running.mkdir()
    (running / "data.txt").write_text("x", encoding="utf-8")
    (s,), out, _ = lab.run("fail")
    case("④", "каталог без метки (идущий прогон, старое накопленное) — не тронут, строки уборки нет",
         running.exists() and s.exists() and SAID_ANY_PRUNE not in out,
         f"каталог без метки на месте: {running.exists()} · строка уборки: "
         f"{'есть' if SAID_ANY_PRUNE in out else 'нет'}")

    # ⑤ первый прогон сохранён по MEZO_KEEP_STANDS, второй провалился — первый цел
    lab = Lab(root, "c5", helper)
    (s1,), _, _ = lab.run("fail", env_extra={"MEZO_KEEP_STANDS": "1"})
    (s2,), _, _ = lab.run("fail")
    case("⑤", "сохранённое по MEZO_KEEP_STANDS следующий провал не убирает",
         s1.exists() and s2.exists() and marker_kind(s1) == "keep_env",
         f"первый на месте: {s1.exists()} · метка первого: {marker_kind(s1)} · второй на месте: {s2.exists()}")

    # ⑤б провал, затем прогон с MEZO_KEEP_STANDS=1 — прогон по переменной никого не убирает (находка PROTO Д3)
    lab = Lab(root, "c5b", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), _, _ = lab.run("fail", env_extra={"MEZO_KEEP_STANDS": "1"})
    case("⑤б", "провал, затем прогон по MEZO_KEEP_STANDS — прежний провал цел",
         s1.exists() and s2.exists() and marker_kind(s2) == "keep_env",
         f"провал на месте: {s1.exists()} · второй на месте: {s2.exists()} · метка второго: {marker_kind(s2)}")

    # ⑥ провал, потом успех: прежний провал цел и назван; свои стенды успех убрал
    lab = Lab(root, "c6", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), out2, _ = lab.run("ok")
    case("⑥", "провал, потом успех — прежний провал цел и назван строкой, свой стенд успех убрал",
         s1.exists() and not s2.exists() and said(out2, SAID_KEPT, 1),
         f"провал на месте: {s1.exists()} · стенд успеха убран: {not s2.exists()} · строка: "
         f"{'есть' if said(out2, SAID_KEPT, 1) else 'НЕТ'}")

    # ⑦ исход не объявлен (падение) дважды — остался только второй
    lab = Lab(root, "c7", helper)
    (s1,), _, _ = lab.run("crash")
    (s2,), out2, _ = lab.run("crash")
    case("⑦", "падение без объявления исхода дважды — остался только второй",
         not s1.exists() and s2.exists() and marker_kind(s2) == "undeclared" and said(out2, SAID_OTHER, 1),
         f"первый на месте: {s1.exists()} · второй на месте: {s2.exists()} · метка второго: {marker_kind(s2)}")

    # ⑧ python -c: скрипта-файла нет — метки и уборки нет, отказа тоже
    lab = Lab(root, "c8", helper)
    (s,), out, rc = lab.run("fail", via_c=True)
    case("⑧", "python -c без файла скрипта — стенд сохранён без метки, уборки нет, отказа нет",
         s.exists() and marker_kind(s) is None and rc == 1 and "метка не поставлена" in out,
         f"код {rc} · стенд на месте: {s.exists()} · метка: {marker_kind(s)}")

    # ⑨ отказ мерить (код 2) дважды — остался только второй, назван своими словами
    lab = Lab(root, "c9", helper)
    (s1,), _, _ = lab.run("refuse")
    (s2,), out2, rc = lab.run("refuse")
    case("⑨", "отказ мерить (код 2) дважды — остался только второй, назван «отказался мерить»",
         not s1.exists() and s2.exists() and rc == 2 and marker_kind(s2) == "refused"
         and "прогон отказался мерить" in out2 and "прогон провалился" not in out2,
         f"первый на месте: {s1.exists()} · второй на месте: {s2.exists()} · метка: {marker_kind(s2)} · "
         f"слова: {'отказался мерить' if 'прогон отказался мерить' in out2 else 'НЕ те'}")

    # ⑩ нарочная поломка, ожидание подтвердилось — стенд убран, код выхода прежний
    lab = Lab(root, "c10", helper)
    (s,), out, rc = lab.run("break_ok")
    case("⑩", "поломка с подтверждённым ожиданием — стенд убран, код выхода 1 сохранён",
         not s.exists() and rc == 1 and "ожидание нарочной поломки подтвердилось" in out,
         f"код {rc} · стенд убран: {not s.exists()}")

    # ⑩б провал, затем подтверждённая поломка того же вызова — прежний провал цел (находка PROTO)
    lab = Lab(root, "c10b", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), _, rc = lab.run("break_ok")
    case("⑩б", "провал, затем подтверждённая поломка — прежний провал цел, стенд поломки убран",
         s1.exists() and not s2.exists() and rc == 1,
         f"код {rc} · провал на месте: {s1.exists()} · стенд поломки убран: {not s2.exists()}")

    # ⑪ подтверждённая поломка, затем провал: метка провала несёт все поля ключа и свой путь
    lab = Lab(root, "c11", helper)
    (s1,), _, _ = lab.run("break_ok")
    (s2,), _, rc = lab.run("fail")
    f = marker_fields(s2) or {}
    try:
        at_ts_ok = float(f.get("at_ts", "")) > 0
    except ValueError:
        at_ts_ok = False
    fields_ok = (f.get("kind") == "failed" and f.get("reason") == "прогон провалился"
                 and f.get("stand") == real(s2) and f.get("args") == "[]" and "root" in f
                 and f.get("cwd") == real(s2.parent.parent / "host-a") and at_ts_ok)
    case("⑪", "поломка, затем провал — стенд провала сохранён, метка несёт ключ, путь и час",
         not s1.exists() and s2.exists() and rc == 1 and fields_ok,
         f"код {rc} · стенд поломки убран: {not s1.exists()} · провал на месте: {s2.exists()} · "
         f"поля метки: {sorted(f)}")

    # ⑫ объявление поломки без finish(): падение после него — сохраняется всегда
    lab = Lab(root, "c12", helper)
    (s,), _, rc = lab.run("break_then_crash")
    case("⑫", "объявил поломку и упал до finish() — стенд сохранён (падение важнее объявления)",
         s.exists(),
         f"код {rc} · стенд на месте: {s.exists()}")

    # ⑬ П1: чистый провал, затем тот же скрипт с --break (поломка кончилась кодом 1 без объявления)
    lab = Lab(root, "c13", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), _, _ = lab.run("fail", args=("--break", "x"))
    clean_kept = s1.exists()
    (s3,), out3, _ = lab.run("fail", args=("--break", "x"))
    case("⑬", "чистый провал, затем прогон с --break — чистый цел; тот же --break дважды — остался второй",
         clean_kept and s1.exists() and not s2.exists() and s3.exists() and said(out3, SAID_FAIL, 1),
         f"чистый после --break: {clean_kept} · первый --break убран вторым: {not s2.exists()} · "
         f"второй --break на месте: {s3.exists()}")

    # ⑭ П1: тот же скрипт с другим MEZO_SCRIPTS_ROOT — другой вызов; с тем же — тот же
    lab = Lab(root, "c14", helper)
    root_a, root_b = lab.base / "root-a", lab.base / "root-b"
    (s1,), _, _ = lab.run("fail", env_extra={"MEZO_SCRIPTS_ROOT": str(root_a)})
    (s2,), _, _ = lab.run("fail", env_extra={"MEZO_SCRIPTS_ROOT": str(root_b)})
    first_kept = s1.exists()
    (s3,), out3, _ = lab.run("fail", env_extra={"MEZO_SCRIPTS_ROOT": str(root_a)})
    case("⑭", "другой корень MEZO_SCRIPTS_ROOT — прежний провал цел; тот же корень — убран",
         first_kept and not s1.exists() and s2.exists() and s3.exists() and said(out3, SAID_FAIL, 1),
         f"корень A после корня B: {first_kept} · корень A убран вторым A: {not s1.exists()} · "
         f"корень B на месте: {s2.exists()}")

    # ⑮ тот же скрипт из другого рабочего каталога — другой вызов (относительные аргументы)
    lab = Lab(root, "c15", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), _, _ = lab.run("fail", cwd=lab.base / "elsewhere")
    case("⑮", "тот же скрипт из другого рабочего каталога — прежний провал цел",
         s1.exists() and s2.exists(),
         f"первый на месте: {s1.exists()} · второй на месте: {s2.exists()}")

    # ⑯ П2: провал, затем отказ мерить — провал цел (отказ доказывает меньше провала)
    lab = Lab(root, "c16", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), _, rc = lab.run("refuse")
    case("⑯", "провал, затем отказ мерить (код 2) — провал цел",
         s1.exists() and s2.exists() and rc == 2,
         f"провал на месте: {s1.exists()} · отказ на месте: {s2.exists()}")

    # ⑰ П2: провал, затем падение — провал цел
    lab = Lab(root, "c17", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), _, _ = lab.run("crash")
    case("⑰", "провал, затем падение без объявления исхода — провал цел",
         s1.exists() and s2.exists() and marker_kind(s2) == "undeclared",
         f"провал на месте: {s1.exists()} · падение на месте: {s2.exists()}")

    # ⑱ П2 обратно: отказ мерить, затем провал — провал отказ не убирает
    lab = Lab(root, "c18", helper)
    (s1,), _, _ = lab.run("refuse")
    (s2,), _, _ = lab.run("fail")
    case("⑱", "отказ мерить, затем провал — отказ цел (провал убирает только прежний провал)",
         s1.exists() and s2.exists(),
         f"отказ на месте: {s1.exists()} · провал на месте: {s2.exists()}")

    # ⑲ ⑳ П3 и Д1 — НАСТОЯЩИЕ параллельные прогоны одного вызова. A начат раньше и ждёт сигнала;
    #     B начат позже и кончается первым; потом кончается A.
    lab = Lab(root, "c19", helper)
    path, _ = lab.script("wait_fail")
    go = lab.base / "go.signal"
    log_a = lab.base / "a.log"
    with open(log_a, "w", encoding="utf-8") as fa:
        proc_a = subprocess.Popen([sys.executable, path.name], cwd=path.parent, stdout=fa, stderr=subprocess.STDOUT,
                                  env=lab.env({"PROBE_WAIT": str(go)}))
    try:
        deadline = time.time() + 30
        sa = None
        while time.time() < deadline and sa is None:
            found = stands_of(log_a.read_text(encoding="utf-8", errors="replace"))
            sa = found[0] if found else None
            if sa is None:
                time.sleep(0.05)
        time.sleep(0.05)   # час начала B строго позже часа начала A
        (sb,), _, _ = lab.run("fail")
        a_alive_kept = sa is not None and sa.exists()
    finally:
        go.write_text("go", encoding="utf-8")
        proc_a.wait(timeout=90)
    a_final = sa is not None and sa.exists() and marker_kind(sa) == "failed"
    case("⑲", "идущий прогон A не тронут прогоном B того же вызова, кончившимся раньше (метка только на выходе)",
         a_alive_kept and a_final,
         f"стенд A во время работы A после провала B на месте: {a_alive_kept} · "
         f"после конца A на месте с меткой провала: {a_final}")
    case("⑳", "A начат раньше, кончил позже — стенд B, начатого позже, цел",
         sb.exists(),
         f"стенд B после конца A: {sb.exists()} · код A: {proc_a.returncode}")

    # ㉑ занятый стенд прежнего провала (в нём открыт файл) не трогается вовсе, а не по частям
    lab = Lab(root, "c21", helper)
    (s1,), _, _ = lab.run("fail")
    held = open(s1 / "data.txt", encoding="utf-8")
    try:
        (s2,), out2, _ = lab.run("fail")
    finally:
        held.close()
    case("㉑", "занятый стенд прежнего провала — цел ЦЕЛИКОМ (метка и файлы), назван «занято»",
         s1.exists() and (s1 / MARKER).is_file() and (s1 / "data.txt").is_file() and s2.exists()
         and said(out2, SAID_FAIL, 0) and said(out2, SAID_BUSY, 1),
         f"стенд на месте: {s1.exists()} · метка: {(s1 / MARKER).is_file()} · файл: {(s1 / 'data.txt').is_file()} · "
         f"строка «занято, не тронуто: 1»: {said(out2, SAID_BUSY, 1)}")

    # ㉒ копия стенда рядом («<стенд> - Copy» из Проводника) — метка указывает не на неё
    lab = Lab(root, "c22", helper)
    (s1,), _, _ = lab.run("fail")
    copy = s1.with_name(s1.name + " - Copy")
    shutil.copytree(s1, copy)
    (s2,), out2, _ = lab.run("fail")
    case("㉒", "копия стенда с той же меткой — копия цела, сам прежний провал убран",
         not s1.exists() and copy.exists() and s2.exists() and said(out2, SAID_FAIL, 1),
         f"прежний убран: {not s1.exists()} · копия на месте: {copy.exists()}")

    # ㉓ ссылка (junction) с началом имени стенда на каталог с подходящей меткой — не трогается и не считается
    lab = Lab(root, "c23", helper)
    (s1,), _, _ = lab.run("fail")
    target = lab.base / "link-target"
    os.rename(s1, target)
    marker = target / MARKER
    if not marker.is_file():
        # помощник метку не ставит (редакция до карточки #657) — случай не собрать, это провал, а не падение
        case("㉓", "ссылка на каталог вместо стенда — ссылка и цель целы, строки уборки нет",
             False, "провал не помечен — случай не собран: помощник метку не ставит")
    else:
        marker.write_text(re.sub(r"(?m)^stand=.*$", lambda _m: "stand=" + real(target),
                                 marker.read_text(encoding="utf-8")), encoding="utf-8")
        link = lab.tmp / (PREFIX + "junction1")
        make_link(link, target)
        (s2,), out2, _ = lab.run("fail")
        case("㉓", "ссылка на каталог вместо стенда — ссылка и цель целы, строки уборки нет",
             os.path.lexists(link) and (target / "data.txt").is_file() and s2.exists()
             and SAID_ANY_PRUNE not in out2,
             f"ссылка на месте: {os.path.lexists(link)} · цель цела: {(target / 'data.txt').is_file()} · "
             f"строка уборки: {'есть' if SAID_ANY_PRUNE in out2 else 'нет'}")

    # ㉔ стенд, отданный release() без new() — начало имени выводится, уборка работает
    lab = Lab(root, "c24", helper)
    (s1,), _, _ = lab.run("fail", use_release=True)
    (s2,), out2, _ = lab.run("fail", use_release=True)
    case("㉔", "release() без new() дважды с провалом — остался только второй",
         not s1.exists() and s2.exists() and marker_kind(s2) == "failed" and said(out2, SAID_FAIL, 1),
         f"первый на месте: {s1.exists()} · второй на месте: {s2.exists()} · метка второго: {marker_kind(s2)}")

    # ㉕ expected_break() при коде 2 не действует — отказ мерить сохраняется
    lab = Lab(root, "c25", helper)
    (s,), _, rc = lab.run("break_refuse")
    case("㉕", "объявил поломку, но кончил кодом 2 — стенд сохранён как отказ",
         s.exists() and rc == 2 and marker_kind(s) == "refused",
         f"код {rc} · стенд на месте: {s.exists()} · метка: {marker_kind(s)}")

    # ㉖ метка прежней редакции (без аргументов, корня и часа) — не трогается, её уберёт janitor-stands.py
    lab = Lab(root, "c26", helper)
    (s1,), _, _ = lab.run("fail")
    f = marker_fields(s1) or {}
    (s1 / MARKER).write_text(f"script={f.get('script', '')}\nkind=failed\nreason=прогон провалился\n"
                             f"at=2026-10-02T23:00:00Z\npid=1\n", encoding="utf-8")
    (s2,), _, _ = lab.run("fail")
    case("㉖", "стенд с меткой прежней редакции — не тронут",
         s1.exists() and s2.exists(),
         f"стенд с прежней меткой на месте: {s1.exists()}")


def main() -> int:
    ap = argparse.ArgumentParser(description="приёмка: стенды только последнего провала приёмки")
    ap.add_argument("--helper", default=str(HERE / "mezo_stand.py"), help="помощник под испытанием")
    ap.add_argument("--break", dest="break_name", choices=sorted(BREAKS), help="нарочная поломка")
    a = ap.parse_args()

    root = mezo_stand.new("bite-stand-keep-last-")
    helper = Path(a.helper).resolve()
    if a.break_name:
        helper = apply_break(helper, a.break_name, root / "broken")
        print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{a.break_name}»: ждём провала РОВНО {' '.join(BREAK_FAILS[a.break_name])} "
              f"(записано в BREAK_FAILS до прогона)\n")
    print(f"помощник под испытанием: {helper}\n")
    run_cases(root, helper)

    failed = [n for n, ok in RESULTS if not ok]
    passed = len(RESULTS) - len(failed)
    covered = sorted(set().union(*(set(v) for v in BREAK_FAILS.values())), key=CASE_IDS.index)
    uncovered = [n for n in CASE_IDS if n not in covered]
    print("")
    mismatch = False
    if a.break_name:
        expected = set(BREAK_FAILS[a.break_name])
        if expected == set(failed):
            print(f"🧪 ожидание поломки «{a.break_name}» ПОДТВЕРДИЛОСЬ: провалены ровно {' '.join(failed)}")
            mezo_stand.expected_break()
        else:
            mismatch = True
            print(f"⚠️ ожидание поломки «{a.break_name}» НЕ ПОДТВЕРДИЛОСЬ: ждали "
                  f"{' '.join(n for n in CASE_IDS if n in expected)}, провалены {' '.join(failed) or 'ничего'}")
    print(f"ИТОГ: {passed} из {len(RESULTS)} · покрыто нарочными поломками {len(covered)}: {' '.join(covered)} · "
          f"без поломки (контрольные): {' '.join(uncovered) or 'нет'}")
    return 0 if not failed and not mismatch else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
