r"""
bite-rules-mirror.py — приёмка переноса «зеркало правил пересобирается само» В ШАБЛОН.

⚠️ ГЛАВНОЕ ПРО СПОСОБ ПРОВЕРКИ. Всё ниже гоняется на СВЕЖЕМ контуре, собранном
`init-group.py` из этого репозитория, а НЕ на контуре-родителе. У родителя болезнь уже
вылечена рукой — прогон там показал бы наше лекарство, а не свойство шаблона.
Это тот же класс, что «проверка перехода не проверяет жизнь после него»: зелёное получается,
но отвечает не на тот вопрос.

СЕМЬ СЛУЧАЕВ, ТРИ ИЗ НИХ ВСТРЕЧНЫЕ (без них «зелено» ничего не стоит):
    ① dry-run ................ файл НЕ ТРОГАЕТСЯ                        [встречный]
    ② запись правила ......... файл пересобран САМ, новое правило в нём
    ③ повторная запись того же файл НЕ ТРОГАЕТСЯ (текст не изменился)   [встречный]
    ④ правило вырезано из файла проверка КРАСНЕЕТ и НАЗЫВАЕТ ключ
    ⑤ файл цел ............... проверка МОЛЧИТ                          [встречный]
    ⑥ файла нет, правила есть  «сверить НЕЧЕМ» — красное, а не «чисто»
    ⑦ генератор сломан ....... правило ЗАПИСАНО, провал ГРОМКИЙ

⚠️ ПРИВЕДЕНА К НАСТОЯЩЕМУ МЕХАНИЗМУ 09.08 19:31 UTC: приёмка была написана
ВПЕРЁД механизма и отстала от него на три сдвига — обязательные поля основания
(отказ 08.08), формулировки вывода («🪞 Записано» вместо ожидавшейся, «не
изменились»), адрес проверяльщика (vnext/prototype, не scripts контура).
Приёмка, ждущая механизм, стареет так же молча, как копия без строителя.

ЗАПУСК: python bite-rules-mirror.py
ВЫХОД:  0 — все семь · 1 — есть провал
"""

import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
import mezo_paths  # пути машины выводятся, не впечатаны (#153)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

# Шаблон ищется ПРИЗНАКОМ (scripts/init-group.py вверх по дереву), а не позицией файла:
# приёмка живёт в ДВУХ каталогах (рабочий и шаблон), и parents[2] из рабочего указывал
# мимо репозитория — тот же класс, что у искателя испытуемого днём (09.08).
def _find_repo():
    for base in Path(__file__).resolve().parents:
        if (base / "scripts" / "init-group.py").exists():
            return base
    return mezo_paths.template_root()
REPO = _find_repo()
TPL_SCRIPTS = REPO / "scripts"
KEY = "проба-зеркала"
BODY1 = "ПЕРВАЯ РЕДАКЦИЯ правила для приёмки переноса."
BODY2 = "ВТОРАЯ РЕДАКЦИЯ — текст изменён, версия обязана подняться."


def run(*cmd, cwd=None):
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=cwd)


def build_contour(root: Path) -> tuple:
    """Свежий контур ПО ШАБЛОНУ: init-group.py + копия скриптов рядом с базой."""
    mezo = root / ".mezosync"
    r = run(sys.executable, TPL_SCRIPTS / "init-group.py",
            "--name", "проба", "--path", mezo)
    if r.returncode != 0:
        print("⛔ не смог собрать контур по шаблону:")
        print((r.stderr or r.stdout).strip()[:900])
        return None, None, None
    scripts = mezo / "scripts"
    scripts.mkdir(exist_ok=True)
    for p in TPL_SCRIPTS.glob("*.py"):
        shutil.copy2(p, scripts / p.name)
    return mezo, mezo / "mezosync.db", scripts


def state(mirror: Path):
    """Снимок файла: чего нет — того нет, и это тоже состояние."""
    return (mirror.read_text(encoding="utf-8") if mirror.exists() else None,
            mirror.stat().st_mtime_ns if mirror.exists() else None)


def main() -> int:
    tmp = mezo_stand.new("bite-tpl-mirror-")
    fails = []
    try:
        mezo, db, scripts = build_contour(tmp)
        if not mezo:
            return 1
        mirror = mezo / "generated" / "sync.rules.md"
        setrule = scripts / "set-rule.py"
        checker = REPO / "vnext" / "prototype" / "check-rules-mirror.py"
        n_rules = sqlite3.connect(str(db)).execute("SELECT COUNT(*) FROM rules").fetchone()[0]
        print("ПРИЁМКА: зеркало правил в ШАБЛОНЕ")
        print(f"  контур собран init-group.py · правил из шаблона: {n_rules}")
        print(f"  зеркало до первой записи: {'есть' if mirror.exists() else 'нет'}\n")

        def say(n, ok, text):
            print(f"   {'✅' if ok else '🔴'} {n} {text}")
            if not ok:
                fails.append(n)

        # ── ① dry-run НЕ трогает файл ───────────────────────────────────────
        before = state(mirror)
        run(sys.executable, setrule, "--db", db, "--key", KEY, "--body", BODY1,
            "--basis", "проба зеркала (стенд)", "--authorized", "coord", "--source-ref", "стенд приёмки", "--expiry-kind", "forever", "--locked-by", "coord", "--actor", "COORD")
        say("①", state(mirror) == before, "сухой прогон — файл не тронут [встречный]")

        # ── ② запись правила пересобирает файл САМА ─────────────────────────
        r = run(sys.executable, setrule, "--db", db, "--key", KEY, "--body", BODY1,
                "--basis", "проба зеркала (стенд)", "--authorized", "coord", "--source-ref", "стенд приёмки", "--expiry-kind", "forever", "--locked-by", "coord", "--actor", "COORD", "--apply")
        txt, _ = state(mirror)
        ok = mirror.exists() and KEY in (txt or "") and "🪞" in r.stdout and "Записано" in r.stdout
        say("②", ok, "запись правила — файл пересобран сам, правило в нём")

        # ── ③ повтор того же текста файл НЕ трогает ─────────────────────────
        before = state(mirror)
        r = run(sys.executable, setrule, "--db", db, "--key", KEY, "--body", BODY1,
                "--basis", "проба зеркала (стенд)", "--authorized", "coord", "--source-ref", "стенд приёмки", "--expiry-kind", "forever", "--locked-by", "coord", "--actor", "COORD", "--apply")
        say("③", state(mirror) == before and "не изменились" in r.stdout,
            "повтор того же текста — файл не тронут [встречный]")

        # ── ④ ЦЕЛЫЙ ФАЙЛ ПРОВЕРЯЕТСЯ ПЕРВЫМ. Порядок здесь не вкусовой: если проверка
        #    не молчит на целом, то её краснота на вырезанном ничего не доказывает.
        #    Именно так первая редакция этой приёмки и соврала: ключ из кириллицы не
        #    распознавался в файле ВООБЩЕ, случай «вырезано» проходил без вырезания.
        run(sys.executable, setrule, "--db", db, "--key", KEY, "--body", BODY2,
            "--basis", "проба зеркала (стенд)", "--authorized", "coord", "--source-ref", "стенд приёмки", "--expiry-kind", "forever", "--locked-by", "coord", "--actor", "COORD", "--apply")
        full = mirror.read_text(encoding="utf-8")
        r = run(sys.executable, checker, "--db", db, "--file", mirror)
        intact_ok = r.returncode == 0
        say("④", intact_ok, "файл цел — проверка молчит [встречный, идёт ПЕРВЫМ]")

        # ── ⑤ правило вырезано → проверка краснеет и НАЗЫВАЕТ ключ ──────────
        # 🪤 «до следующего заголовка ИЛИ до конца файла»: наше правило оказалось ПОСЛЕДНИМ,
        #    и шаблон без `\Z` не вырезал ничего — приёмка краснела на исправном инструменте.
        #    Подлог, который не состоялся, неотличим от проверки, которая его не заметила,
        #    поэтому вырезание тут же и подтверждается числом.
        cut = re.sub(rf"^###\s+`{re.escape(KEY)}`.*?(?=^###\s|\Z)", "", full,
                     flags=re.S | re.M)
        really_cut = KEY not in cut and len(cut) < len(full)
        mirror.write_text(cut, encoding="utf-8")
        r = run(sys.executable, checker, "--db", db, "--file", mirror)
        say("⑤", intact_ok and really_cut and r.returncode == 1
            and KEY in r.stdout and "НЕТ В ФАЙЛЕ" in r.stdout,
            f"правило вырезано ({'подлог состоялся' if really_cut else '🔴 ПОДЛОГ НЕ УДАЛСЯ'})"
            " — проверка краснеет и называет ключ")
        mirror.write_text(full, encoding="utf-8")

        # ── ⑥ файла нет, а правила есть → «сверить НЕЧЕМ», не «чисто» ───────
        mirror.unlink()
        r = run(sys.executable, checker, "--db", db, "--file", mirror)
        # Проверяльщик отвечает КОДОМ 2 — «отказ мерить», отдельный и от красного, и от
        # зелёного. Приёмка ждала 1: третий исход у механизма ЛУЧШЕ, чем требовал критерий.
        say("⑥", r.returncode == 2 and "не нашёл файл" in r.stdout,
            "файла нет при живых правилах — ОТКАЗ МЕРИТЬ (код 2), а не «чисто»")

        # ── ⑦ генератор сломан → правило ЗАПИСАНО, провал ГРОМКИЙ ───────────
        gen = scripts / "export-rules.py"
        gen.rename(scripts / "export-rules.py.hidden")
        r = run(sys.executable, setrule, "--db", db, "--key", KEY + "-2",
                "--body", "правило при сломанном генераторе", "--basis", "проба зеркала (стенд)", "--authorized", "coord", "--source-ref", "стенд приёмки", "--expiry-kind", "forever", "--locked-by", "coord",
                "--actor", "COORD", "--apply")
        written = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True).execute(
            "SELECT COUNT(*) FROM rules WHERE rule_key = ?", (KEY + "-2",)).fetchone()[0]
        loud = (r.stdout + r.stderr).upper()
        # факт записи сверяется ПО БАЗЕ (written), а не по слову в выводе: требовать
        # от крика ещё и слова «записано» было перестраховкой не по делу
        say("⑦", written == 1 and "НЕ ПЕРЕСОБРАНО" in loud,
            "генератор сломан — правило записано, провал сказан вслух (в stderr — там "
            "ему и место; приёмка смотрела только stdout и глохла на честном крике)")
        (scripts / "export-rules.py.hidden").rename(gen)

        print()
        if fails:
            print(f"ИТОГ: 🔴 ПРОВАЛ по случаям {', '.join(fails)} — перенос НЕ принят")
            return 1
        print("ИТОГ: ✅ ВСЕ СЕМЬ СЛУЧАЕВ. Перенос принят:")
        print("      зеркало пересобирается САМО, при отказе и повторе не трогается,")
        print("      расхождение называется поимённо, провал генератора не отменяет запись.")
        return 0
    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
