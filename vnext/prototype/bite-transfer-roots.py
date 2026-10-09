# -*- coding: utf-8 -*-
r"""ПРИЁМКА ОТКАЗА ПЕРЕНОСА: vnext/tools/sync-to-template.py СНЯТ этапом Э4 (карточка #678, шаг Ш3).

Была приёмка корней переноса: список механизмов для шаблона считался замером достижимости, а не рукой
(класс назвал @COORD 10.08, записка #3482). С Э4 пакет — единственный источник: инструмент правят
в клоне пакета, в контур он приходит установкой update-tools.py, и переноса «контур → пакет» нет вовсе.
Инструмент оставлен файлом и отказывает словами: вызов живёт в памяти ролей. Прежние случаи ①–⑥ судили
снятый код — он в истории пакета, последний commit с ним c4221fa.

СЛУЧАИ (функция judge — общая: ею же судит отказ sync-vnext-pair.py приёмка bite-sync-vnext-pair.py):
  ① вызов без ключей — код 2 (не 0: вызывающий не должен принять отказ за перенос)
  ② привычный вызов с --apply — тот же код 2
  ③ отказ называет путь правки: «СНЯТ», клон пакета, update-tools.py, «Ничего не перенесено»
  ④ контроль: каталог, куда прежде писал перенос, не тронут (имена и время правки файлов те же)
НАРОЧНЫЕ ПОЛОМКИ — в каждом прогоне, на копии инструмента во временном каталоге:
  Р① код отказа 0                        → ① ②
  Р② слова «ничего не перенесено» сняты  → ③
⛔ Живой базы не касается; пакет только читается. Запускается не файл пакета, а его КОПИЯ в каталоге
стенда (стенд/пакет/<путь инструмента>, рядом — пустой каталог-контроль ④): прежний инструмент переноса
считал пакет от своего расположения и с --apply писал в него. Окажись в пакете старая редакция, эта
приёмка испытала бы её на стенде и провалилась бы, а клон пакета остался бы цел.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402 — пути машины ВЫВОДЯТСЯ, не впечатаны (карточка #208)
import mezo_stand  # noqa: E402

HERE = Path(__file__).resolve().parent
BREAKS = [
    ("Р①", "код отказа 0", ("①", "②"), "REFUSAL_CODE = 2", "REFUSAL_CODE = 0"),
    ("Р②", "слова «ничего не перенесено» сняты", ("③",),
     "   Ничего не перенесено и ничего не сверено.\n", ""),
]
TITLES = {
    "①": "① вызов без ключей — код 2",
    "②": "② привычный вызов с --apply — код 2",
    "③": "③ отказ называет путь правки через клон пакета и update-tools.py",
    "④": "④ контроль: каталог, куда писал перенос, не тронут",
}


def find_pack(tool_rel: str):
    """Клон пакета, где лежит испытуемый: объявленный в файле путей, либо этот же клон."""
    for p in (mezo_paths.template_root(), HERE.parent.parent, HERE.parent.parent / "gordipack"):
        if p is not None and (Path(p) / tool_rel).is_file():
            return Path(p)
    return None


def state(folder: Path) -> list:
    return sorted((p.name, p.stat().st_mtime_ns) for p in folder.iterdir()) if folder.is_dir() else []


def site(stand: Path, name: str, tool_rel: str, watched_rel: str, text: str) -> tuple:
    """Копия инструмента на стенде в раскладке пакета + каталог-контроль с одним файлом."""
    root = stand / name
    tool, watched = root / tool_rel, root / watched_rel
    tool.parent.mkdir(parents=True, exist_ok=True)
    tool.write_text(text, encoding="utf-8")
    watched.mkdir(parents=True, exist_ok=True)
    (watched / "a.py").write_text("print(1)\n", encoding="utf-8")
    return tool, watched


def verdicts(tool: Path, watched: Path, stand: Path) -> dict:
    def go(*args):
        r = subprocess.run([sys.executable, str(tool), *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           env=mezo_stand.stand_env(stand, PYTHONIOENCODING="utf-8"), cwd=str(stand),
                           timeout=120)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    before = state(watched)
    c1, _ = go()
    c2, out2 = go("--apply")
    after = state(watched)
    words = ("СНЯТ" in out2 and "клоне пакета" in out2 and "update-tools.py" in out2
             and "Ничего не перенесено" in out2)
    return {
        "①": (c1 == 2, f"код {c1} (ждём 2)"),
        "②": (c2 == 2, f"код {c2} (ждём 2)"),
        "③": (words, "слова отказа названы" if words else f"слов нет: {out2.strip()[:160]!r}"),
        "④": (before == after, f"файлов в {watched.name}/: до {len(before)}, после {len(after)}, "
                               f"{'не тронуты' if before == after else 'ИЗМЕНИЛИСЬ'}"),
    }


def judge(tool_rel: str, watched_rel: str, label: str) -> int:
    """Судить отказ снятого инструмента переноса. → код выхода приёмки (0 · 1 · 2 — не запустилась)."""
    pack = find_pack(tool_rel)
    if pack is None:
        print(f"⛔ НЕ ЗАПУСТИЛАСЬ: клона пакета с {tool_rel} не нашлось — отказ мерить, не «чисто»")
        return 2
    source = pack / tool_rel
    print(f"⚖️ испытуется: {source} (копией на стенде)")
    text = source.read_text(encoding="utf-8")
    stand = mezo_stand.new("bite-transfer-refusal-")
    ok, cases = True, 0
    v = verdicts(*site(stand, "main", tool_rel, watched_rel, text), stand)
    for key, title in TITLES.items():
        verdict, detail = v[key]
        cases += 1
        ok &= verdict
        print(f"{'✅' if verdict else '🔴'} {title}\n   {detail}")
    if not ok:
        # поломки меряют чувствительность случаев на ИСПРАВНОМ отказе; испытуемый, не прошедший
        # их сам (например, прежний инструмент переноса), — это «НЕ ПРИНЯТО», а не «не запустилась»
        print("\n⚪ нарочные поломки не гонялись: испытуемый сам не прошёл случаи выше")
        print(f"🔴 ОТКАЗ {label} — НЕ ПРИНЯТО — случаев {cases}")
        return 1
    for tag, what, target, anchor, repl in BREAKS:
        if text.count(anchor) != 1:
            print(f"⛔ НЕ ЗАПУСТИЛАСЬ: поломку {tag} некуда вложить — образец найден {text.count(anchor)} раз "
                  f"в {source.name}: {anchor[:60]!r}")
            return 2
        bv = verdicts(*site(stand, f"break-{tag[-1]}", tool_rel, watched_rel, text.replace(anchor, repl)),
                      stand)
        fell = tuple(k for k, (good, _) in bv.items() if not good)
        cases += 1
        ok &= fell == target
        print(f"{'✅' if fell == target else '🔴'} {tag} {what} — проваливаются ровно {', '.join(target)}\n"
              f"   провалились: {', '.join(fell) or 'ничего'}")
    print()
    print(f"{'✅' if ok else '🔴'} ОТКАЗ {label} — {'ПРИНЯТО' if ok else 'НЕ ПРИНЯТО'} — случаев {cases}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(judge("vnext/tools/sync-to-template.py", "scripts", "sync-to-template.py")))
