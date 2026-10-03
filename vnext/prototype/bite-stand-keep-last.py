# -*- coding: utf-8 -*-
"""
bite-stand-keep-last.py — приёмка: mezo_stand.py хранит при провале стенды только ПОСЛЕДНЕГО
прогона приёмки (карточка #657, пункт (3); слово владельца «Б1» 02.10.2026 23:47 UTC, чат OPSSRE;
план и два дополнения — комментарии карточки, согласованы с PROTO записками #5422 и #5437).

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
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mezo_stand  # noqa: E402

MARKER = ".mezo_stand_kept"
PREFIX = "keep-last-p-"
PREFIX_2 = "keep-last-q-"

# Нарочные поломки: (что заменить в помощнике, на что). Заменяемая строка обязана встретиться
# ровно один раз — иначе помощник менялся, и приёмку надо править, а не гадать.
BREAKS = {
    "name-key": ("    return os.path.normcase(str(p.resolve()))",
                 "    return os.path.normcase(p.name)"),
    "no-marker-check": ("                    marker = _read_marker(Path(entry.path) / KEPT_MARKER)",
                        "                    marker = _read_marker(Path(entry.path) / KEPT_MARKER) or {\"script\": key}"),
    "keep-env-pruned": ("                    if marker.get(\"kind\") == _KIND_KEEP_ENV and not include_keep_env:",
                        "                    if False:"),
    "no-prune": ("        removed, left = _remove_all(_previous_kept(_SCRIPT_KEY, include_keep_env=False))",
                 "        removed, left = 0, []"),
    "refuse-as-fail": ("        return \"прогон отказался мерить\" if _exit_code == 2 else \"прогон провалился\"",
                       "        return \"прогон провалился\""),
    "break-ignored": ("    _expected_break = True",
                      "    _expected_break = False"),
    "success-silent": ("        if previous:",
                       "        if False:"),
}
# Какие случаи ОБЯЗАНЫ провалиться при каждой поломке — записано ДО прогона.
BREAK_FAILS = {
    "name-key": ["③"],
    "no-marker-check": ["④"],
    "keep-env-pruned": ["⑤"],
    "no-prune": ["①", "②", "⑦", "⑨"],
    "refuse-as-fail": ["⑨"],
    "break-ignored": ["⑩"],
    "success-silent": ["⑥"],
}
CASE_IDS = ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨", "⑩", "⑪", "⑫"]

OUTCOMES = {
    "ok": ["sys.exit(mezo_stand.finish(0))"],
    "fail": ["sys.exit(mezo_stand.finish(1))"],
    "refuse": ["sys.exit(mezo_stand.finish(2))"],
    "crash": ["raise SystemExit('упало до объявления исхода')"],
    "break_ok": ["mezo_stand.expected_break()", "sys.exit(mezo_stand.finish(1))"],
    "break_then_crash": ["mezo_stand.expected_break()", "raise SystemExit('упало после объявления поломки')"],
}

RESULTS: list[tuple[str, bool]] = []


def case(number: str, title: str, ok: bool, detail: str) -> None:
    RESULTS.append((number, bool(ok)))
    print(f"{'✅' if ok else '🔴'} {number} {title}\n   {detail}")


class Lab:
    """Песочница одного случая: каталог временной папки для стендов и каталоги подставных скриптов."""

    def __init__(self, root: Path, name: str, helper: Path):
        self.base = root / name
        self.tmp = self.base / "tmp"
        self.tmp.mkdir(parents=True)
        self.helper = helper

    def run(self, outcome: str, prefixes=(PREFIX,), host: str = "host-a", env_extra=None, via_c=False):
        """Запустить подставной скрипт. Вернуть (стенды, вывод, код выхода)."""
        host_dir = self.base / host
        host_dir.mkdir(exist_ok=True)
        shutil.copy2(self.helper, host_dir / "mezo_stand.py")
        lines = ["# -*- coding: utf-8 -*-", "import sys", "import mezo_stand"]
        for prefix in prefixes:
            lines.append(f"r = mezo_stand.new({prefix!r}); (r / 'data.txt').write_text('x', encoding='utf-8'); "
                         "print('STAND=' + str(r))")
        lines += OUTCOMES[outcome]
        code = "\n".join(lines) + "\n"
        env = dict(os.environ, PYTHONIOENCODING="utf-8",
                   TMP=str(self.tmp), TEMP=str(self.tmp), TMPDIR=str(self.tmp))
        env.pop("MEZO_KEEP_STANDS", None)
        env.update(env_extra or {})
        if via_c:
            cmd = [sys.executable, "-c", code]
        else:
            (host_dir / "probe.py").write_text(code, encoding="utf-8")
            cmd = [sys.executable, "probe.py"]
        p = subprocess.run(cmd, cwd=host_dir, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env)
        out = (p.stdout or "") + (p.stderr or "")
        stands = [Path(m.strip()) for m in re.findall(r"STAND=(.+)", out)]
        return stands, out, p.returncode


def marker_kind(stand: Path) -> str | None:
    """Вид исхода из метки стенда; None — метки нет."""
    m = stand / MARKER
    if not m.is_file():
        return None
    for line in m.read_text(encoding="utf-8").splitlines():
        if line.startswith("kind="):
            return line[len("kind="):]
    return ""


def apply_break(helper: Path, name: str, dest: Path) -> Path:
    old, new = BREAKS[name]
    src = helper.read_text(encoding="utf-8")
    if src.count(old) != 1:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: место нарочной поломки «{name}» встречается {src.count(old)} раз "
              f"вместо одного — помощник менялся, правь приёмку")
        sys.exit(2)
    dest.mkdir(parents=True, exist_ok=True)
    broken = dest / "mezo_stand.py"
    broken.write_text(src.replace(old, new, 1), encoding="utf-8")
    return broken


def run_cases(root: Path, helper: Path) -> None:
    # ① ВСТРЕЧНЫЙ ИЗ КРИТЕРИЯ КАРТОЧКИ: два провала подряд → остаются стенды только второго
    lab = Lab(root, "c1", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), out2, _ = lab.run("fail")
    case("①", "два провала одной приёмки подряд — остаются стенды только второго, у второго метка",
         not s1.exists() and s2.exists() and marker_kind(s2) == "failed"
         and "стендов прежнего провала этой приёмки убрано: 1" in out2,
         f"первый на месте: {s1.exists()} · второй на месте: {s2.exists()} · метка второго: {marker_kind(s2)}")

    # ② два начала имён в одном прогоне — второй провал убирает оба стенда первого
    lab = Lab(root, "c2", helper)
    (a1, b1), _, _ = lab.run("fail", prefixes=(PREFIX, PREFIX_2))
    (a2, b2), out2, _ = lab.run("fail", prefixes=(PREFIX, PREFIX_2))
    case("②", "два начала имён в прогоне — второй провал убрал оба стенда первого",
         not a1.exists() and not b1.exists() and a2.exists() and b2.exists()
         and "стендов прежнего провала этой приёмки убрано: 2" in out2,
         f"первые на месте: {a1.exists()}, {b1.exists()} · вторые на месте: {a2.exists()}, {b2.exists()}")

    # ③ ДРУГОЙ скрипт с тем же именем файла и тем же началом имени (копия пакета у соседа)
    lab = Lab(root, "c3", helper)
    (sb,), _, _ = lab.run("fail", host="host-b")
    (sa,), out_a, _ = lab.run("fail", host="host-a")
    case("③", "чужой скрипт с тем же именем файла и началом имени — его провал цел",
         sb.exists() and sa.exists() and "стендов прежнего провала этой приёмки убрано: НОЛЬ" in out_a,
         f"стенд другого скрипта на месте: {sb.exists()} · свой на месте: {sa.exists()} — ключ полный путь, не имя")

    # ④ каталог того же начала имени БЕЗ метки — так выглядит прогон, который идёт сейчас
    lab = Lab(root, "c4", helper)
    running = lab.tmp / (PREFIX + "running1")
    running.mkdir()
    (running / "data.txt").write_text("x", encoding="utf-8")
    (s,), out, _ = lab.run("fail")
    case("④", "каталог без метки (идущий прогон, старое накопленное) — не тронут",
         running.exists() and s.exists() and "стендов прежнего провала этой приёмки убрано: НОЛЬ" in out,
         f"каталог без метки на месте: {running.exists()}")

    # ⑤ первый прогон сохранён по MEZO_KEEP_STANDS, второй провалился — первый цел
    lab = Lab(root, "c5", helper)
    (s1,), out1, _ = lab.run("fail", env_extra={"MEZO_KEEP_STANDS": "1"})
    (s2,), _, _ = lab.run("fail")
    case("⑤", "сохранённое по MEZO_KEEP_STANDS следующий провал не убирает",
         s1.exists() and s2.exists() and marker_kind(s1) == "keep_env",
         f"первый на месте: {s1.exists()} · метка первого: {marker_kind(s1)} · второй на месте: {s2.exists()}")

    # ⑥ провал, потом успех: прежний провал цел и назван; свои стенды успех убрал
    lab = Lab(root, "c6", helper)
    (s1,), _, _ = lab.run("fail")
    (s2,), out2, _ = lab.run("ok")
    case("⑥", "провал, потом успех — прежний провал цел и назван строкой, свой стенд успех убрал",
         s1.exists() and not s2.exists() and "прежний провал этого скрипта сохранён: 1" in out2,
         f"провал на месте: {s1.exists()} · стенд успеха убран: {not s2.exists()} · строка: "
         f"{'есть' if 'прежний провал этого скрипта сохранён: 1' in out2 else 'НЕТ'}")

    # ⑦ исход не объявлен (падение) дважды — остался только второй
    lab = Lab(root, "c7", helper)
    (s1,), _, _ = lab.run("crash")
    (s2,), _, _ = lab.run("crash")
    case("⑦", "падение без объявления исхода дважды — остался только второй",
         not s1.exists() and s2.exists() and marker_kind(s2) == "undeclared",
         f"первый на месте: {s1.exists()} · второй на месте: {s2.exists()} · метка второго: {marker_kind(s2)}")

    # ⑧ python -c: скрипта-файла нет — метки и уборки нет, отказа тоже
    lab = Lab(root, "c8", helper)
    (s,), out, rc = lab.run("fail", via_c=True)
    case("⑧", "python -c без файла скрипта — стенд сохранён без метки, уборки нет, отказа нет",
         s.exists() and marker_kind(s) is None and rc == 1 and "метка не поставлена" in out,
         f"код {rc} · стенд на месте: {s.exists()} · метка: {marker_kind(s)}")

    # ⑨ отказ мерить (код 2) дважды — тот же учёт, что провал, но своими словами
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

    # ⑪ ВСТРЕЧНЫЙ к ⑩ (PROTO): ожидание НЕ подтвердилось — стенд сохранён и помечен
    lab = Lab(root, "c11", helper)
    (s,), _, rc = lab.run("fail")
    case("⑪", "поломка с НЕподтверждённым ожиданием — стенд сохранён и помечен",
         s.exists() and marker_kind(s) == "failed" and rc == 1,
         f"код {rc} · стенд на месте: {s.exists()} · метка: {marker_kind(s)}")

    # ⑫ объявление поломки без finish(): падение после него — сохраняется всегда
    lab = Lab(root, "c12", helper)
    (s,), _, rc = lab.run("break_then_crash")
    case("⑫", "объявил поломку и упал до finish() — стенд сохранён (падение важнее объявления)",
         s.exists(),
         f"код {rc} · стенд на месте: {s.exists()}")


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
