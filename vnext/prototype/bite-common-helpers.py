# -*- coding: utf-8 -*-
r"""bite-common-helpers.py — приёмка карточки #578: общие по имени помощники ДВУХ рабочих
каталогов контура обязаны быть ОДНОЙ версией, и расхождение обязано краснеть.

═══ ЧТО БЫЛО
У инструментов v-next своя копия разрешателя путей, отставшая на 17 суток. Её зовут
136 инструментов из 192 ⇒ починка, сделанная в каталоге контура, до них не доезжала.
🩸 И это не «просто отставание»: в старой копии жил ровно тот дефект, который в новой
вылечен, — при ненайденном корне она МОЛЧА возвращала «ожидаемое место», а подключение
по этому пути создавало ПУСТУЮ базу вместо отказа.

═══ ПОЧЕМУ НЕ ЛОВИЛОСЬ
Сверки знают пары «рантайм ↔ зеркало» и «v-next ↔ образец». Файл, живущий в ОБЕИХ парах
разными копиями, ни в одной из них не сравнивается сам с собой. Молчание по построению.

═══ ВЕДУЩАЯ СТОРОНА У КАЖДОГО ФАЙЛА СВОЯ — ЭТО ГЛАВНОЕ
📏 Замер 2026-09-06: общих по имени файлов ДВА, и оба расходились.
    mezo_paths.py .... новее в каталоге контура (21994б против 10916б)
    mezo_stand.py .... новее в каталоге v-next (11690б против 7433б: там работа #572)
⇒ «Синхронизировать в одну сторону» стёрло бы одну из двух работ. Поэтому проверка
НЕ сводит сама и не советует направления — говорит, ЧТО разошлось.

═══ ОЖИДАНИЯ ПОЛОМКИ — НАЗВАНЫ ДО ПРОГОНА
    П1 вызов третьей пары убран из инструмента
       ждём: ① перестаёт краснеть, ② остаётся зелёным (он и так про совпадение)

═══ ДОБАВЛЕНО 2026-09-07 (карточка #586)
Случаи ①-⑤ проверяют МЕХАНИЗМ на подставном "helper.py" внутри стенда — они никогда
не читают настоящие рабочие каталоги и потому не могут поймать регресс в КОНКРЕТНОМ
общем помощнике. Случай ⑦ — единственный здесь, что смотрит на настоящую пару
`.mezosync/scripts/mezo_hints.py` ↔ `vnext-tools/mezo_hints.py` (заведена той же
карточкой #586: механизм «подсказка один раз, дальше строка-ссылка»). Зеркало и шаблон
у него по-прежнему подставные — реальный бэкап-репозиторий не должен решать зелёное/
красное ЭТОГО случая, тот же довод, что у случаев ①-⑤.

═══ ВОЗВРАТ ПО G7 (2026-09-14, поправка COORD) — ТРИ НЕЗАВИСИМЫЕ ПОПРАВКИ ═══
① Случай (бывший ⑥, теперь ⑦) «РЕАЛЬНАЯ ПАРА» срабатывал НЕ ПО СВОЕЙ ПРИЧИНЕ: судил
  «"ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ" in output and "mezo_hints.py" in output» — ГДЕ УГОДНО
  в тексте. А имя того же файла печатается ЕЩЁ и в разделе ПЕРВОЙ пары (report_pair,
  vnext-tools↔образец), если там расходится ЧТО-ТО ДРУГОЕ. 14.09 живой замер COORD:
  три копии mezo_hints.py совпадают (sha256 284e6c91…), настоящее расхождение было
  у check-rules-mirror.py (карточка #618) — а случай ⑥ всё равно кричал про mezo_hints.py.
  Чинит diverges_in_shared_helpers_section() — судит ТОЛЬКО раздел после маркера.
② Случай ⑤: `.replace(anchor, "    return 0", 1)` бьёт в ПЕРВОЕ из ТРЁХ текстуально
  одинаковых `return check_shared_helpers()` в guard-scripts-drift.py, а исполняется
  (когда VNEXT_TEMPLATE реально существует, как в этом стенде) ТРЕТЬЕ — патч бьёт мимо
  независимо от имени функции. Живой прогон у COORD ⑤ проходил, у PROTO — нет (другая
  среда). Чинит замена БЕЗ ограничения count (все три сразу) + явная проверка «якорь
  найден» (число вхождений ≥1, иначе случай проваливается словами «якорь не найден»).
③ Имена файла переведены ЦЕЛИКОМ (правило владельца «правишь файл — переводишь его
  имена» действует и здесь, раз файл правится). Печатающая функция случай→case — то же
  имя, что уже в _PRINTING_CALLS guard-scripts-drift.py (карточка #625) и что уже
  использует bite-drift-sanitize.py; трогать _PRINTING_CALLS не понадобилось.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402

TOOL = Path(mezo_paths.live_scripts(__file__)) / "guard-scripts-drift.py"
results: list[tuple[str, bool, str]] = []


def case(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'✅' if ok else '🔴'} {name}: {detail}")


def diverges_in_shared_helpers_section(output: str, name: str) -> bool:
    """Судит расхождение ИМЕННО в разделе «ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ», а не по всему
    выводу целиком (поправка COORD, возврат по G7, п.①).

    ⛔ БЫЛО: `"ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ" in output and name in output` — оба условия
    ищут по ВСЕМУ тексту. Имя того же файла печатается ЕЩЁ и в разделе ПЕРВОЙ пары
    (report_pair, vnext-tools↔образец) — если там расходится ЧТО-ТО ДРУГОЕ, а в разделе
    «ОБЩИЕ ПОМОЩНИКИ» при этом ничего не расходится вовсе, старая проверка всё равно
    отвечала True. Живой случай 14.09: mezo_hints.py упомянут в чужом разделе (там
    настоящее расхождение — check-rules-mirror.py, карточка #618), а случай кричал
    про mezo_hints.py.
    ⇒ СТАЛО: раздел «ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ» печатается guard-scripts-drift.py
    ПОСЛЕДНИМ (check_shared_helpers() зовётся в самом конце check_against_template()),
    поэтому текст ПОСЛЕ маркера и есть весь раздел целиком — до конца вывода.
    """
    marker = "ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ"
    if marker not in output:
        return False
    section = output.split(marker, 1)[1]
    return name in section


def run_guard(stand: Path, tool: Path | None = None):
    """Зову сверку на ПОДСТАВНЫХ каталогах: живого хозяйства приёмка не касается."""
    r = subprocess.run(
        [sys.executable, str(tool or TOOL),
         "--runtime", str(stand / "contour"), "--repo", str(stand / "mirror"),
         "--vnext-runtime", str(stand / "vnext"), "--vnext-template", str(stand / "template")],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
        env=mezo_stand.stand_env(stand))  # карточка #613: env закреплён за стендом
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def run_guard_on_real(stand: Path):
    """Как run_guard(), но --runtime/--vnext-runtime указывают на НАСТОЯЩИЕ рабочие
    каталоги контура (.mezosync/scripts и vnext-tools), а не на подставные. Зеркало и
    шаблон остаются подставным пустым каталогом стенда — реальный бэкап-репозиторий не
    должен решать зелёное/красное случая ⑦ (карточка #586)."""
    r = subprocess.run(
        [sys.executable, str(TOOL),
         "--runtime", str(mezo_paths.live_scripts(__file__)),
         "--repo", str(stand / "repo"),
         "--vnext-runtime", str(mezo_paths.container_root(__file__) / "vnext-tools"),
         "--vnext-template", str(stand / "template")],
        capture_output=True, text=True, encoding="utf-8", timeout=300,
        env=mezo_stand.stand_env(stand))  # карточка #613: env закреплён за стендом
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def build_stand(stand: Path, common_differs: bool, only_in_one: bool = False) -> None:
    for name in ("contour", "mirror", "vnext", "template"):
        (stand / name).mkdir(parents=True, exist_ok=True)
    (stand / "contour" / "helper.py").write_text("VALUE = 1" + chr(10), encoding="utf-8")
    (stand / "vnext" / "helper.py").write_text(
        ("VALUE = 2" if common_differs else "VALUE = 1") + chr(10), encoding="utf-8")
    if only_in_one:
        (stand / "contour" / "lonely.py").write_text("# только здесь" + chr(10),
                                                      encoding="utf-8")
    # зеркало = точная копия каталога контура, чтобы ПЕРВАЯ пара не шумела
    shutil.rmtree(stand / "mirror")
    shutil.copytree(stand / "contour", stand / "mirror")


def main() -> int:
    stand = Path(mezo_stand.new("bite-common-helpers-"))

    build_stand(stand, common_differs=True)
    code, output = run_guard(stand)
    case("① разные копии общего помощника — проверка КРАСНЕЕТ и называет файл",
         "ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ" in output and "helper.py" in output,
         "названо расхождение" if "ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ" in output
         else "молчит — а копии разные")

    case("② красное ВЛИЯЕТ на код возврата, а не только печатается",
         code == 1,
         f"код {code}" + ("" if code == 1 else " — проверка, не меняющая исход, не мешает никому"))

    build_stand(stand, common_differs=False)
    code2, output2 = run_guard(stand)
    case("③ ВСТРЕЧНЫЙ: сведённые копии — зелёное и код 0",
         code2 == 0 and "совпадают байт в байт" in output2,
         f"код {code2}, сказано о совпадении"
         if "совпадают байт в байт" in output2 else "о совпадении не сказано")

    build_stand(stand, common_differs=False, only_in_one=True)
    code3, output3 = run_guard(stand)
    case("④ ВСТРЕЧНЫЙ: файл, который есть ТОЛЬКО в одном каталоге, не краснеет",
         code3 == 0 and "ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ" not in output3,
         f"код {code3} — иначе проверка требовала бы копировать всё подряд из каталога "
         "в каталог, а каталоги разные по назначению")

    # ⑤ ОБРАТНЫЙ ХОД: вызов третьей пары убран — расхождение снова молчит.
    blind_stand = Path(mezo_stand.new("bite-common-helpers-blind-"))
    blind_copy = mezo_stand.copy_tool(TOOL, blind_stand)
    text = blind_copy.read_text(encoding="utf-8")
    # ⚠️ ВОЗВРАТ ПО G7, п.②: якорь есть ТРИ РАЗА в guard-scripts-drift.py (три return
    # внутри check_against_template()) — исполняется не обязательно первый текстуально.
    # Меняем ВСЕ вхождения разом (без ограничения count), а не только первое, и явно
    # проверяем, что якорь вообще нашёлся — иначе «поломка» молча ничего не меняет
    # (та самая ловушка «приёмка держится за строку кода» из общих правил исполнителя).
    anchor5 = "    return check_shared_helpers()"
    anchor5_count = text.count(anchor5)
    anchor5_found = anchor5_count >= 1
    case("⑤а якорь поломки найден в живом тексте сверки",
         anchor5_found,
         f"вхождений: {anchor5_count}" if anchor5_found else "якорь не найден")
    if anchor5_found:
        blind_copy.write_bytes(text.replace(anchor5, "    return 0").encode("utf-8"))
    build_stand(stand, common_differs=True)
    code5, output5 = run_guard(stand, blind_copy)
    case("⑤б ОБРАТНЫЙ ХОД: вызов третьей пары убран → те же копии снова молчат",
         "ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ" not in output5,
         "молчит — значит краснеет ИМЕННО третья пара, а не что-то рядом"
         if "ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ" not in output5
         else "красит и без вызова — красит что-то другое")
    mezo_stand.release(blind_stand)
    mezo_stand.release(stand)

    # ⑥ БЛОК СУЖДЕНИЯ ПО РАЗДЕЛУ (возврат по G7, п.①) — юнит-случаи на ПОДСТАВНОМ
    # выводе (без реального guard-scripts-drift.py): прямой и встречный для
    # diverges_in_shared_helpers_section(), доказывающие, что судится РАЗДЕЛ,
    # а не весь текст целиком.
    fake_output_wrong_section = (
        "⚠️ vnext-tools ↔ образец: РАСХОДЯТСЯ 1 из 5 общих — чинит @PROTO, не этот гард\n"
        "   mezo_hints.py                     1234б ≠   1234б   свежее: образец · строк по существу: 3\n"
        "   👉 роль идёт за инструментом ПО ПУТИ ИЗ СВОЕЙ ПАМЯТИ: сдано у автора ≠ доступно ей\n"
        "\n"
        "⛔ ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ (1 из 3) — инструменты двух каталогов работают "
        "РАЗНЫМ кодом под одним именем:\n"
        "   other_helper.py        контур abc123 (100б) ≠ v-next def456 (120б)\n"
        "   👉 сведи их ОДНОЙ версией...\n"
    )
    case("⑥а ВСТРЕЧНЫЙ: mezo_hints.py упомянут в ЧУЖОМ разделе → не срабатывает",
         diverges_in_shared_helpers_section(fake_output_wrong_section, "mezo_hints.py")
         is False,
         "старая проверка («расходятся» + имя ГДЕ УГОДНО) отвечала бы True здесь — "
         "ровно та беда, найденная COORD 14.09 на живом прогоне")

    fake_output_real_section = (
        "⛔ ОБЩИЕ ПОМОЩНИКИ РАСХОДЯТСЯ (1 из 3) — инструменты двух каталогов работают "
        "РАЗНЫМ кодом под одним именем:\n"
        "   mezo_hints.py           контур abc123 (100б) ≠ v-next def456 (120б)\n"
        "   👉 сведи их ОДНОЙ версией...\n"
    )
    case("⑥б ПРЯМОЙ: mezo_hints.py в разделе «ОБЩИЕ ПОМОЩНИКИ» → срабатывает",
         diverges_in_shared_helpers_section(fake_output_real_section, "mezo_hints.py")
         is True,
         "без него ⑥а мог бы быть зелёным просто потому, что функция всегда лжёт False")

    # ⑦ РЕАЛЬНАЯ ПАРА (карточка #586, было ⑥): .mezosync/scripts/mezo_hints.py ↔
    # vnext-tools/mezo_hints.py — сверка НАСТОЯЩИХ рабочих каталогов, не стенда.
    # ⚖️ Этот случай не про фиксированный ожидаемый исход, как ①-⑥ на подставных данных:
    # он честно отражает состояние ДВУХ РЕАЛЬНЫХ файлов на диске в момент прогона —
    # и теперь судит ТОЛЬКО раздел «ОБЩИЕ ПОМОЩНИКИ» (см. diverges_in_shared_helpers_
    # section выше), а не любое упоминание имени файла по всему выводу.
    real_stand = Path(mezo_stand.new("bite-common-helpers-real-"))
    (real_stand / "repo").mkdir(parents=True, exist_ok=True)
    (real_stand / "template").mkdir(parents=True, exist_ok=True)
    _, output7 = run_guard_on_real(real_stand)
    diverged7 = diverges_in_shared_helpers_section(output7, "mezo_hints.py")
    case("⑦ РЕАЛЬНАЯ ПАРА: .mezosync/scripts/mezo_hints.py ↔ vnext-tools/mezo_hints.py",
         not diverged7,
         "сведены байт в байт" if not diverged7
         else "🔴 РАСХОДЯТСЯ прямо сейчас в разделе «ОБЩИЕ ПОМОЩНИКИ» — копии не совпадают")
    mezo_stand.release(real_stand)

    failed = [name for name, ok, _ in results if not ok]
    print("")
    print("=" * 78)
    print(f"РАЗЛИЧАЮЩИХ СЛУЧАЕВ {len(results)}, из них ВСТРЕЧНЫХ 3 (③, ④ и ⑥а)")
    print("⚖️ ГРАНИЦА: сверяются БАЙТЫ. Совпадение байтов НЕ означает равносильности —")
    print("   инструмент зависит и от того, что лежит рядом с ним. И переименованную")
    print("   копию того же помощника проверка не поймает: её не с чем сравнить.")
    if failed:
        print(f"🔴 ПРОВАЛЕНО {len(failed)}: {' · '.join(failed)}")
        return 1
    print("✅ ВСЕ СЛУЧАИ ПРОЙДЕНЫ")
    return 0


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
