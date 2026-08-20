# -*- coding: utf-8 -*-
r"""ПРИЁМКА ПРИЗНАКА «МЕХАНИЗМ ПЕЧАТАЕТ ИМЯ, КОТОРОГО У НЕГО НЕТ» (карточка #87).

Критерий карточки требует ловить ИЗВЕСТНОЕ на КОПИЯХ ВЕРСИЙ ДО ПОЧИНОК — не по памяти.
Копии берутся из git-истории зеркала живых скриптов (atlas.agents-sync.db):
    ② справка --to обещала сосуд ПРОЗОЙ («признак «адресат задан полем»») — правило А;
    ⑥ help «критерий … (обязателен по слову владельца)» без required — правило Б;
    ①-семья: канон «--db НЕОБЯЗАТЕЛЕН» против required=True у инструмента — правило В.
⚖️ ОТСТУПЛЕНИЕ ОТ КАРТОЧКИ, НАЗВАННОЕ ВСЛУХ: экземпляр ① («справка --db „обязателен"»)
дословно в истории НЕ НАЙДЕН (замер по git: слова «обязателен» о --db в help-строках нет
ни в одной ревизии зеркала). Его класс — обязательность --db, которой код не держит, —
пойман правилом В на ИСТОРИЧЕСКОЙ копии backup-db (required=True при каноне
«необязателен», ревизия до R15a). Три пойманных есть; подмена названа, а не спрятана.

⛔ Живой базы не касается: git-копии во временном каталоге, сверка имён — по живой БД
   только чтением.
⛔ Число случаев печатает прогон.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # пути машины ВЫВОДЯТСЯ, не впечатаны (карточка #208)

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKER = HERE / "check-false-signature.py"
MIRROR = mezo_paths.container_root() / "atlas.agents-sync.db"
if not CHECKER.exists():
    print(f"⛔ ИСПЫТУЕМОГО НЕТ: {CHECKER} — отказ мерить, не «чисто»")
    sys.exit(2)
if not (MIRROR / ".git").exists():
    print(f"⛔ ЗЕРКАЛА ИСТОРИИ НЕТ: {MIRROR} — исторические копии взять неоткуда."
          " Это отказ мерить, не «чисто»")
    sys.exit(2)

CASES = 0
DIFFER = 0


def case(title, verdict, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


def git_show(rev_path: str) -> str:
    r = subprocess.run(["git", "-C", str(MIRROR), "show", rev_path],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        return ""
    return r.stdout


def run_checker(*args):
    r = subprocess.run([sys.executable, str(CHECKER), *args],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="bite-sig-"))

    # ── ② ИСТОРИЧЕСКАЯ КОПИЯ write-message ДО починки справки --to (правило А) ──
    old_wm = git_show("0c19a23^:scripts/write-message.py")
    if not old_wm:
        print("⛔ ревизия 0c19a23^ недоступна — исторический случай ② НЕ ПРОВЕРЕН")
        return 2
    p2 = tmp / "wm_old.py"
    p2.write_text(old_wm, encoding="utf-8")
    code, out = run_checker("--file", str(p2))
    ok &= case("② ИСТОРИЯ: справка --to обещала сосуд ПРОЗОЙ — правило А ловит",
               code == 1 and "[А]" in out and "--to" in out and "ПРОЗОЙ" in out,
               "«признак «адресат задан полем»» — ни поля, ни таблицы; проверить нечем."
               " После починки имя названо (addressed_by=) и проверяемо", differ=True)

    # ── ⑥ ИСТОРИЧЕСКАЯ КОПИЯ backlog с «обязателен по слову владельца» (правило Б) ──
    old_bl = git_show("86e106b:scripts/backlog.py")
    if not old_bl:
        print("⛔ ревизия 86e106b недоступна — исторический случай ⑥ НЕ ПРОВЕРЕН")
        return 2
    p6 = tmp / "bl_old.py"
    p6.write_text(old_bl, encoding="utf-8")
    code, out = run_checker("--file", str(p6))
    ok &= case("⑥ ИСТОРИЯ: help «обязателен по слову владельца» без required — правило Б",
               code == 1 and "[Б]" in out and "done-when" in out,
               "слово держало обязательность, код молча принимал без критерия", differ=True)

    # ── ①-семья ИСТОРИЕЙ: канон против backup-db (required=True) — правило В ──
    root1 = tmp / "hist_root"
    root1.mkdir()
    for name, rev in (("read-phoenix.py", "ae852cf^:scripts/read-phoenix.py"),
                      ("backup-db.py", "ae852cf^:scripts/backup-db.py")):
        src = git_show(rev)
        if not src:
            print(f"⛔ ревизия {rev} недоступна — случай ①-семьи НЕ ПРОВЕРЕН")
            return 2
        (root1 / name).write_text(src, encoding="utf-8")
    code, out = run_checker("--root", str(root1))
    ok &= case("①-семья ИСТОРИЕЙ: канон «--db необязателен» против required=True — правило В",
               code == 1 and "[В]" in out and "backup-db.py" in out,
               "роль, поверившая канону, получала отказ инструмента (до R15a-волны)",
               differ=True)

    # ── РАЗЛИЧАЮЩИЙ: на ПОЧИНЕННЫХ современных версиях ТЕХ ЖЕ файлов — молчит ──
    root2 = tmp / "now_root"
    root2.mkdir()
    live = mezo_paths.live_scripts()
    for name in ("write-message.py", "backlog.py", "read-phoenix.py", "backup-db.py"):
        (root2 / name).write_text((live / name).read_text(encoding="utf-8"),
                                  encoding="utf-8")
    code, out = run_checker("--root", str(root2))
    ok &= case("④ на ПОЧИНЕННЫХ версиях тех же файлов признак МОЛЧИТ (различающий)",
               code == 0,
               f"код {code}; без этого случая он зелен и когда исправен, и когда"
               " не смотрит вовсе", differ=True)

    # ── ЖИВОЙ ПРОГОН: ноль ложных на здоровом контуре (критерий ⑤) ──
    code, out = run_checker()
    n_found = out.count("🔴 [")
    ok &= case("⑤ живой контур: ложных срабатываний НОЛЬ",
               code == 0 and n_found == 0,
               f"находок {n_found}; каждое сработавшее место до готовности смотрено глазами"
               " (см. закрытие карточки — список отсеянных)", differ=True)

    # ── ГРАНИЦА ПЕЧАТАЕТСЯ САМИМ ПРИЗНАКОМ (критерий ④ карточки) ──
    ok &= case("⑥б признак называет СВОЮ границу прямым текстом каждым прогоном",
               "ГРАНИЦА" in out and "ложная ПРИЧИНА" in out and "СРОК" in out,
               "молчание признака не должно читаться как «ложных строк нет»")

    print()
    print(f"{'✅ ПРИЗНАК ПРИНЯТ' if ok else '🔴 ПРИЗНАК НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}; исторические копии ИЗ GIT, не по памяти")
    print("⚖️ ГРАНИЦА ПРИЁМКИ: судит признак и три известных экземпляра; полноту шести"
          " экземпляров карточки не судит — три из шести не ловятся ПО ПОСТРОЕНИЮ"
          " (причина · срок · пересказчик), и признак говорит это о себе сам.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
