# -*- coding: utf-8 -*-
r"""bite-to-template.py — приёмка шага Ш3 этапа Э4 (карточка #678): guard-scripts-drift.py --to-template
СНЯТ — отказывает словами и ничего не переносит.

═══ ПОВОД
Перенос --to-template (карточка #576) копировал файлы контура в пакет, заменяя пути машины заглушками.
С Э4 пакет — единственный источник: инструмент правят в клоне пакета, в контур он приходит установкой
update-tools.py. Перенос в обратную сторону затёр бы в пакете чужую правку старой копией. Ключ не удалён:
вызов живёт в памяти ролей, и отказ словами называет новый путь там, где роль его ищет.
Прежние случаи этой приёмки (①–⑥, обезличивание при переносе) судили снятый код — он в истории пакета,
последний commit с ним c4221fa.

═══ СЛУЧАИ (испытуемый — guard-scripts-drift.py из каталога mezo_target, стенд — временный каталог)
  ① --to-template с файлом — код 2 (не 0: вызывающий не должен принять отказ за перенос)
  ② отказ называет путь правки: «СНЯТ», клон пакета, update-tools.py, «Ничего не перенесено»
  ③ каталог пакета на стенде не тронут: файлов в нём столько же, сколько до вызова (контроль — кода
     переноса в инструменте больше нет, поломки на этот случай не бывает)
  ④ голый --to-template (без файлов) — тот же отказ словами, а не справка разбора аргументов
  ⑤ встречный: без --to-template сверка пары работает как прежде — отказ привязан к ключу, а не
     ко всему инструменту

═══ НАРОЧНЫЕ ПОЛОМКИ — гоняются в КАЖДОМ прогоне на копии инструмента (mezo_stand.copy_tool) с одним
местом в прежнем или испорченном виде; якорь не нашёлся ровно один раз — «НЕ ЗАПУСТИЛАСЬ», не молчание.
Под каждой провалиться обязаны РОВНО записанные случаи:
  Р① код отказа 0               → ① ④
  Р② слова «ничего не перенесено» сняты → ②
  Р③ ключ требует файл (nargs "+") → ④
  Р④ отказ без ключа (всегда)     → ⑤
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402
import mezo_target  # noqa: E402

CASES = 0
OK = True


class NotRun(Exception):
    """Приёмка не смогла начаться — не «сломано» и не «в порядке»."""


def case(title, verdict, detail):
    global CASES, OK
    CASES += 1
    OK &= bool(verdict)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")


def run(tool: Path, container: Path, *args) -> tuple:
    r = subprocess.run([sys.executable, str(tool), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=mezo_stand.stand_env(container, PYTHONIOENCODING="utf-8"), timeout=300)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def verdicts(tool: Path, container: Path, root: Path) -> dict:
    """Пять случаев на одном испытуемом. → {номер: (исход, подробность)}."""
    src, pack = root / "контур", root / "пакет"
    rt, repo = root / "рабочий", root / "зеркало"
    for d in (src, pack, rt, repo):
        d.mkdir(parents=True)
    # «мирный.py» в контуре НЕ кладём: отказ стои́т до любого чтения файлов, а лишний файл контура
    # дал бы встречному ⑤ строку «создано мимо пакета» вместо «общих совпадают»
    (pack / "a.py").write_text("print(1)\n", encoding="utf-8")
    (src / "a.py").write_text("print(1)\n", encoding="utf-8")
    for d in (rt, repo):
        (d / "x.py").write_text("# одинаково\n", encoding="utf-8")
    before = sorted(p.name for p in pack.iterdir())

    code1, out1 = run(tool, container, "--to-template", "мирный.py",
                      "--vnext-runtime", str(src), "--vnext-template", str(pack))
    after = sorted(p.name for p in pack.iterdir())
    words = ("СНЯТ" in out1 and "клоне пакета" in out1 and "update-tools.py" in out1
             and "Ничего не перенесено" in out1)
    code4, out4 = run(tool, container, "--to-template")
    code5, out5 = run(tool, container, "--runtime", str(rt), "--repo", str(repo),
                      "--vnext-runtime", str(src), "--vnext-template", str(pack))
    return {
        "①": (code1 == 2, f"код {code1} (ждём 2)"),
        "②": (words, "слова отказа названы" if words else f"слов нет: {out1.strip()[:160]!r}"),
        "③": (before == after, f"в каталоге пакета было {before}, стало {after}"),
        "④": (code4 == 2 and "СНЯТ" in out4 and "usage:" not in out4,
              f"код {code4}; отказ словами: {'СНЯТ' in out4}; справка разбора: {'usage:' in out4}"),
        "⑤": (code5 in (0, 1) and "общих совпадают" in out5 and "СНЯТ" not in out5,
              f"код {code5}; сверка пары: {'общих совпадают' in out5}; отказ напечатан: {'СНЯТ' in out5}"),
    }


TITLES = {
    "①": "① --to-template с файлом — код 2",
    "②": "② отказ называет путь правки через клон пакета и update-tools.py",
    "③": "③ контроль: каталог пакета не тронут",
    "④": "④ голый --to-template — отказ словами, не справка разбора аргументов",
    "⑤": "⑤ встречный: без ключа сверка пары работает как прежде",
}

BREAKS = [
    ("Р①", "код отказа 0", ("①", "④"),
     "TO_TEMPLATE_REFUSAL_CODE = 2", "TO_TEMPLATE_REFUSAL_CODE = 0"),
    ("Р②", "слова «ничего не перенесено» сняты", ("②",),
     "   Ничего не перенесено и ничего не сверено.\n", ""),
    ("Р③", "ключ требует файл", ("④",),
     'ap.add_argument("--to-template", nargs="*"', 'ap.add_argument("--to-template", nargs="+"'),
    ("Р④", "отказ без ключа", ("⑤",),
     "    if args.to_template is not None:\n", "    if True:\n"),
]


def weakened(tool: Path, root: Path, anchor: str, replacement: str) -> Path:
    """Копия инструмента с соседями, одно место заменено. Якорь обязан встретиться ровно раз."""
    copy = mezo_stand.copy_tool(tool, root / ".mezosync" / "scripts")
    text = copy.read_text(encoding="utf-8")
    found = text.count(anchor)
    if found != 1:
        raise NotRun(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку некуда вложить — образец найден {found} раз в {tool.name}:"
                     f" {anchor[:70]!r}")
    copy.write_text(text.replace(anchor, replacement), encoding="utf-8")
    return copy


def main() -> int:
    tool = mezo_target.script("guard-scripts-drift.py")
    print(f"⚖️ испытуется: {tool}")
    stand = mezo_stand.new("bite-to-template-")
    try:
        v = verdicts(tool, stand, stand / "main")
        for key, title in TITLES.items():
            case(title, *v[key])
        if not OK:
            # поломки меряют чувствительность случаев на ИСПРАВНОМ отказе; испытуемый, не прошедший
            # их сам (например, прежняя редакция с переносом), — это «НЕ ПРИНЯТО», а не «не запустилась»
            print("\n⚪ нарочные поломки не гонялись: испытуемый сам не прошёл случаи выше")
            print(f"🔴 ОТКАЗ --to-template — НЕ ПРИНЯТО — случаев {CASES}")
            return 1
        for tag, what, target, anchor, repl in BREAKS:
            root = stand / f"break-{tag[-1]}"
            broken = weakened(tool, root, anchor, repl)
            bv = verdicts(broken, root, root / "run")
            fell = tuple(k for k, (ok, _) in bv.items() if not ok)
            case(f"{tag} {what} — проваливаются ровно {', '.join(target)}", fell == target,
                 f"провалились: {', '.join(fell) or 'ничего'} · {bv[target[0]][1]}")
    except NotRun as exc:
        print(exc)
        return 2
    print()
    print(f"{'✅' if OK else '🔴'} ОТКАЗ --to-template — {'ПРИНЯТО' if OK else 'НЕ ПРИНЯТО'} — случаев {CASES}")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
