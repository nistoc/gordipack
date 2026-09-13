#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
СВЕРКА НОМЕРОВ ПРОЦЕССОВ СЛУЖБ СТЕНДА.

Отвечает на один вопрос про каждую службу: номер процесса, записанный в файле
при запуске, — это ТОТ ЖЕ процесс, что слушает порт службы прямо сейчас?

⚠️ ЗАЧЕМ. Гашение службы «по номеру из файла» промахивается МОЛЧА: файл может
хранить номер прежнего запуска, номер вспомогательного процесса или вовсе быть
не один. Ни один из промахов не краснеет сам — отчёт говорит «погашено»
одинаково уверенно во всех случаях.

Замер, из которого выросла проверка: @STUD 2026-09-04 23:07 UTC — лгали ТРИ
файла из четырёх; @OPSSRE 2026-09-05 05:18 UTC — то же плюс две находки сверх
(файлов с одним именем ДВА; в файле ядра стои́т не оболочка запуска,
а НАБЛЮДАЮЩИЙ РЕЖИМ СБОРКИ, который поднимает службу обратно после гашения).
Задача #542.

ИСХОДОВ ПЯТЬ, А НЕ ДВА — в этом весь смысл проверки:
    СОВПАЛ ............ номер в файле = слушатель порта
    ЧУЖОЙ ЖИВОЙ ....... номер в файле принадлежит ДРУГОМУ живому процессу
                        (самый опасный: гашение попадёт в постороннее)
    ФАЙЛ УСТАРЕЛ ...... номера в файле нет в системе вовсе
    ФАЙЛОВ НЕСКОЛЬКО .. файлов с этим именем больше одного, и они разные
    ФАЙЛА НЕТ ......... службу гасить по файлу нечем

Коды возврата: 0 — все совпали · 1 — есть расхождения · 2 — измерить не удалось.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 🔤 Имена кода переведены на английский 2026-09-13 (слово владельца 07.09 15:47/15:57 UTC:
#    код — по-английски, комментарии — на прежнем языке, переводить при касании; карточка #601).
#    Значения исходов остались русскими: это ПЕЧАТАЕМЫЙ текст, а не имена.
MATCHED = "СОВПАЛ"
FOREIGN_ALIVE = "ЧУЖОЙ ЖИВОЙ"
FILE_STALE = "ФАЙЛ УСТАРЕЛ"
SEVERAL_FILES = "ФАЙЛОВ НЕСКОЛЬКО"
NO_FILE = "ФАЙЛА НЕТ"
NOT_LISTENING = "СЛУЖБА НЕ СЛУШАЕТ"
NOT_A_NUMBER = "В ФАЙЛЕ НЕ ЧИСЛО"
FOREIGN_SERVICE = "ЧУЖАЯ СЛУЖБА"

GOOD_OUTCOMES = {MATCHED}

# Службы стенда: имя человеку · порт · имя файла с номером · наша ли она.
# ⚠️ Список именной и короткий НАМЕРЕННО: проверка судит СТЕНД, а не всё,
#    что слушает порты на машине. Добавляя службу — добавляй сюда.
#
# 🔴 ЧЕТВЁРТОЕ ПОЛЕ ЗАВЕДЕНО 05.09 06:37 UTC И ВОТ ЗАЧЕМ. Шлюз на :5297 — это
# Aia.LlmGateway из C:\guts\.aia, то есть служба СОСЕДНЕГО контура. Наш файл с её
# номером был остатком тех времён, когда её поднимали мы; он убран по слову
# владельца. Но если оставить строку красной, проверка будет вечно требовать
# починки того, чего чинить НЕЛЬЗЯ: гасить чужую службу мы не вправе, а завести
# ей файл с номером — тем более.
# ⚡ Признак, который горит ВСЕГДА и не может погаснуть, перестаёт что-либо значить —
# и промолчит ровно тогда, когда впервые окажется настоящим. Поэтому чужая служба
# получает СВОЙ исход, а не красный.
SERVICES = [
    ("ядро",                    5300, "core.pid",       True),
    ("приём документов",        5400, "ingestion.pid",  True),
    ("портал",                  5291, "studio.pid",     True),
    ("шлюз к языковой модели",  5297, "llmgateway.pid", False),   # контур AIA
]

# Контейнер — два уровня вверх от этого файла (…/vnext-tools/check-service-pids.py).
# Выводится от расположения, а не пишется литералом: литерал этой машины у потребителя
# образца указал бы в пустоту — перенос в образец 13.09 на нём и отказал (карточка #601).
CONTAINER = Path(__file__).resolve().parent.parent


def run_dirs(root: Path) -> list[Path]:
    """Все каталоги `.run`, где может лежать файл с номером.

    ⚠️ Ищем ВО ВСЕХ, а не в одном: находка @OPSSRE 05.09 — файлов `ingestion.pid`
    оказалось ДВА, в разных каталогах и с разными номерами. Инструмент, знающий
    один каталог, честно измерит не тот файл и не покраснеет.
    """
    found = []
    own = root / ".run"
    if own.is_dir():
        found.append(own)
    try:
        for sub in sorted(root.iterdir()):
            if sub.is_dir() and (sub / ".run").is_dir():
                found.append(sub / ".run")
    except OSError:
        pass
    return found


def service_files(root: Path, file_name: str) -> list[Path]:
    return [d / file_name for d in run_dirs(root) if (d / file_name).is_file()]


def _powershell(command: str) -> str:
    done = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    return done.stdout or ""


def port_listeners(ports: list[int]) -> dict[int, int]:
    """{порт: номер процесса-слушателя}. Порт без слушателя в ответ не попадает."""
    port_list = ",".join(str(p) for p in ports)
    output = _powershell(
        f"Get-NetTCPConnection -State Listen -LocalPort {port_list} -ErrorAction SilentlyContinue |"
        f" Select-Object LocalPort,OwningProcess | ConvertTo-Json -Compress"
    ).strip()
    if not output:
        return {}
    data = json.loads(output)
    if isinstance(data, dict):
        data = [data]
    # Одна служба может слушать порт и по IPv4, и по IPv6 — процесс тот же.
    return {int(r["LocalPort"]): int(r["OwningProcess"]) for r in data}


def live_processes(pids: list[int]) -> dict[int, dict]:
    """{номер: {имя, путь, строка запуска}} — только для тех, кто ЖИВ сейчас.

    ⚡ ЗДЕСЬ СТОИТ ПОДСАДКА, И ОНА ОПЛАЧЕНА ЭТИМ ЖЕ ИНСТРУМЕНТОМ 2026-09-05.
    Условие отбора писалось языком оболочки (`-or`), а система понимает только
    язык запросов к описанию машины (`OR`). Запрос падал, ответ приходил ПУСТОЙ —
    и пустой ответ читался как «таких живых процессов нет», то есть как ЗАМЕР.
    Все чужие живые номера превращались в «файл устарел»: вердикт правдоподобный,
    красный, и потому не вызывающий подозрений.
    ⇒ Поэтому в каждый запрос подсаживается СВОЙ СОБСТВЕННЫЙ номер: он заведомо
    жив. Не вернулся он — спрашивать мы не умеем, и надо ОТКАЗАТЬСЯ МЕРИТЬ,
    а не отвечать «никого нет».
    """
    import os
    own = os.getpid()
    asked = sorted({n for n in pids if n > 0} | {own})
    condition = " OR ".join(f"ProcessId={n}" for n in asked)
    output = _powershell(
        f"Get-CimInstance Win32_Process -Filter \"{condition}\" |"
        f" Select-Object ProcessId,Name,ExecutablePath,CommandLine | ConvertTo-Json -Compress"
    ).strip()
    data = json.loads(output) if output else []
    if isinstance(data, dict):
        data = [data]
    found = {
        int(r["ProcessId"]): {
            "name": r.get("Name") or "",
            "path": r.get("ExecutablePath") or "",
            "command_line": (r.get("CommandLine") or "").strip(),
        }
        for r in data
    }
    if own not in found:
        raise RuntimeError(
            "запрос о живых процессах не вернул даже НАС САМИХ — значит спросить "
            "не удалось, а не «процессов нет». Мерить отказываюсь")
    return found          # свой номер НЕ убираем: он такой же живой чужой процесс


def is_watch_mode(command_line: str) -> bool:
    """Строка запуска говорит, что это сборщик, следящий за исходниками.

    ⚠️ Отдельный признак, а не украшение: такой процесс ПОДНИМАЕТ службу обратно
    после гашения — «погашено» становится правдой на минуту и ложью потом.
    """
    text = command_line.lower()
    return "dotnet" in text and " watch" in f" {text}"


def compare(root: Path, service: tuple, listeners: dict, processes: dict) -> dict:
    name, port, file_name, ours = service
    result = {
        "service": name, "port": port, "file_name": file_name,
        "files": [], "in_file": None, "listener": listeners.get(port),
        "outcome": None, "why": "", "watch": False,
    }

    found = service_files(root, file_name)
    result["files"] = [str(path) for path in found]

    if not ours:
        # Чужую службу мы не гасим и файл с её номером не заводим. Судить её
        # нашей меркой нечестно: у неё свой хозяин и свой порядок.
        result["outcome"] = FOREIGN_SERVICE
        extra = " 🔴 И у нас лежит файл с её номером — он приглашает погасить ЧУЖОЕ" if found else ""
        result["why"] = (f"порт {port} слушает служба СОСЕДНЕГО контура — "
                         f"не наша забота и не наше право её гасить.{extra}")
        return result

    if result["listener"] is None:
        result["outcome"] = NOT_LISTENING
        result["why"] = f"порт {port} никто не слушает — сверять не с чем"
        return result

    if not found:
        result["outcome"] = NO_FILE
        result["why"] = f"файла «{file_name}» нет ни в одном каталоге запуска"
        return result

    read = {}
    for path in found:
        try:
            text = path.read_text(encoding="utf-8").strip()
            read[path] = int(text)
        except ValueError:
            result["outcome"] = NOT_A_NUMBER
            result["why"] = f"в файле {path} не число"
            return result
        except OSError as e:
            result["outcome"] = NOT_A_NUMBER
            result["why"] = f"файл {path} не прочитан ({e.__class__.__name__})"
            return result

    if len(set(read.values())) > 1:
        result["outcome"] = SEVERAL_FILES
        result["why"] = ("файлов с этим именем " + str(len(read)) +
                         ", и номера РАЗНЫЕ: " +
                         " · ".join(f"{path.parent}\\{path.name} → {n}" for path, n in read.items()) +
                         ". Какой из них прочтёт гашение — зависит от порядка поиска")
        return result

    pid = next(iter(read.values()))
    result["in_file"] = pid

    if pid == result["listener"]:
        result["outcome"] = MATCHED
        result["why"] = f"номер в файле = слушатель порта {port}"
        return result

    info = processes.get(pid)
    if info is None:
        result["outcome"] = FILE_STALE
        result["why"] = (f"в файле {pid}, а этого номера в системе НЕТ; "
                         f"порт {port} слушает {result['listener']}. "
                         f"Гашение отчитается «уже погашено» при живой службе")
        return result

    result["outcome"] = FOREIGN_ALIVE
    result["watch"] = is_watch_mode(info["command_line"])
    tail = ""
    if result["watch"]:
        tail = (". 🔴 И это НАБЛЮДАЮЩИЙ РЕЖИМ СБОРКИ: погасив его, службу не остановишь; "
                "погасив службу, получишь её обратно через секунды")
    result["why"] = (f"в файле {pid} — ЖИВОЙ процесс «{info['name']}», "
                     f"но порт {port} слушает {result['listener']}. "
                     f"Гашение по файлу попадёт в постороннее{tail}")
    return result


def print_report(results: list[dict], root: Path) -> int:
    """Печатает разбор и ОТДАЁТ число настоящих расхождений — по нему и код возврата.

    ⚠️ Считать итог в одном месте, а решать в другом — как было минуту назад, —
    значит развести их: код возврата оказался верным ПО ПОСТОРОННЕЙ ПРИЧИНЕ
    (падение с ошибкой тоже даёт 1). Верный цвет по неверному поводу проверяют
    реже всего, и однажды он промолчит при живой беде.
    """
    print(f"СВЕРКА НОМЕРОВ ПРОЦЕССОВ СЛУЖБ · каталог запуска: {root}")
    print("Судим по слушателю порта, а не по чтению файла. Исходов пять, не два.")
    print("-" * 78)
    for item in results:
        mark = ("✅" if item["outcome"] in GOOD_OUTCOMES else
                "⚪" if item["outcome"] == NOT_LISTENING else
                "🏠" if item["outcome"] == FOREIGN_SERVICE else "🔴")
        in_file = item["in_file"] if item["in_file"] is not None else "—"
        listener = item["listener"] if item["listener"] is not None else "—"
        print(f"{mark} {item['service']} (:{item['port']}) — {item['outcome']}")
        print(f"     в файле: {in_file} · слушает порт: {listener}")
        print(f"     {item['why']}")
        if len(item["files"]) > 1:
            for path in item["files"]:
                print(f"       файл: {path}")
    print("-" * 78)
    foreign = [item for item in results if item["outcome"] == FOREIGN_SERVICE]
    unmeasured = [item for item in results if item["outcome"] == NOT_LISTENING]
    bad = [item for item in results if item["outcome"] not in GOOD_OUTCOMES
           and item["outcome"] not in (NOT_LISTENING, FOREIGN_SERVICE)]
    matched = len(results) - len(bad) - len(unmeasured) - len(foreign)
    print(f"совпало: {matched} · расхождений: {len(bad)} · "
          f"не измерено: {len(unmeasured)} · чужих: {len(foreign)}")
    if unmeasured:
        print("⚠️ «не измерено» — это НЕ «в порядке»: служба не поднята, "
              "и её файл ничем не проверен.")
    if foreign:
        print("🏠 «чужая служба» — НЕ беда и НЕ успех: её хозяин в другом контуре, "
              "и наша мерка к ней не применима.")
    return len(bad)


def run(root: Path) -> int:
    ports = [p for _, p, _, _ in SERVICES]
    try:
        listening = port_listeners(ports)
    except Exception as e:
        print(f"⛔ ОТКАЗ МЕРИТЬ: не удалось спросить слушателей портов ({e.__class__.__name__}: {e})")
        return 2
    pids_in_files = []
    for _, _, file_name, _ in SERVICES:
        for path in service_files(root, file_name):
            try:
                pids_in_files.append(int(path.read_text(encoding="utf-8").strip()))
            except (ValueError, OSError):
                pass
    try:
        processes = live_processes(pids_in_files + list(listening.values()))
    except Exception as e:
        print(f"⛔ ОТКАЗ МЕРИТЬ: не удалось спросить о процессах ({e.__class__.__name__}: {e})")
        return 2

    results = [compare(root, service, listening, processes) for service in SERVICES]
    return 1 if print_report(results, root) else 0


# ─────────────────────── самопроверка ───────────────────────

def listener_refusal(port: int, pid: int, trace: dict) -> str | None:
    """ЛЕКАРСТВО САМОПРОВЕРКИ: названный слушатель порта обязан быть ЖИВЫМ процессом.

    Возвращает текст отказа, если живого процесса с таким номером нет, и None, если он жив.
    Каждый вызов оставляет СЛЕД в trace: {порт: (номер, жив ли)}.

    🔧 Вынесено из тела самопроверки 2026-09-13 (карточка #601, находка @STUD при приёмке
    задачи #561). Прежде лекарство стояло строкой внутри самопроверки, и НИ ОДИН случай его
    не испытывал: снятое, оно давало 9 из 9 и код 0, а строка границы продолжала утверждать,
    что слушатель проверяется. Текст о коде не проверялся кодом — и пережил бы исчезновение
    свойства, о котором говорит.
    ⇒ Теперь лекарство испытывает случай ⑩ (выдуманный номер обязан получить отказ) и
       требует случай ⑪ (след исполнения на настоящем слушателе). Строка границы о живости
       слушателя печатается, только если оба прошли.
    """
    alive = pid in live_processes([pid])
    trace[port] = (pid, alive)
    if alive:
        return None
    return (f"⛔ ОТКАЗ ПРОВЕРЯТЬ СЕБЯ: слушателем порта {port} назван номер "
            f"{pid}, а живого процесса с таким номером НЕТ. Значит про "
            f"слушателей спросить не удалось — это не замер, и судить по нему нечего.")


def selftest() -> int:
    """Подсадные файлы в отдельном каталоге против ЖИВЫХ слушателей стенда.

    ⚖️ Почему так, а не на живых файлах: порча обязана ломать ПРОДУКТ — здесь
    продукт это логика сверки, и она читает именно файл. Подсадной файл ломает
    её ровно так же, как испорченный живой, но не трогает чужой стенд.
    """
    import os
    import tempfile

    # След исполнения лекарства (карточка #601). Заведён ЗДЕСЬ, вдали от его вызова:
    # удалишь вызов — след останется пустым, и случай ⑪ это увидит.
    listener_trace = {}

    ports = [p for _, p, _, _ in SERVICES]
    listening = port_listeners(ports)
    if not listening:
        print("⛔ ОТКАЗ ПРОВЕРЯТЬ СЕБЯ: ни одна служба стенда не слушает — "
              "встречные случаи требуют живой службы. Подними стенд и повтори.")
        return 2

    live_port = sorted(listening)[0]
    live_service = next(service for service in SERVICES if service[1] == live_port and service[3])
    live_name, _, live_file, _ = live_service
    real = listening[live_port]

    # 🔑 ПОДСАДКА ЖИВОСТИ ДЛЯ СЛУШАТЕЛЯ — то же лекарство, что у запроса о процессах.
    # ⚠️ Без неё контрольный случай ① сверяет число САМО С СОБОЙ: и подсадной файл,
    # и «слушатель порта» берутся из ОДНОГО вызова, поэтому он сойдётся при любом
    # ответе — хоть при выдуманном. Замер @CHROME 2026-09-05 15:47 UTC (задача #561):
    # с запросом, возвращавшим несуществующий номер, самопроверка давала 9 из 9 и
    # код 0, а в заголовке печатала этот номер как «настоящий».
    # ⇒ спрашиваем то же, что у случая ⑨: если названный слушатель не живой процесс,
    #    значит спросить не удалось — и это НЕ замер. Само лекарство испытывают случаи ⑩ и ⑪.
    refusal = listener_refusal(live_port, real, listener_trace)
    if refusal:
        print(refusal)
        return 2

    own = os.getpid()           # живой процесс, заведомо НЕ служба
    dead = 999_999              # номера такой величины в системе не бывает

    cases = []

    def case(title, expected, plants):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".run").mkdir()
            (root / "под-репо" / ".run").mkdir(parents=True)
            for where, file_name, value in plants:
                (root / where / file_name).write_text(str(value), encoding="utf-8")
            pids = [v for _, _, v in plants] + list(listening.values())
            processes = live_processes(pids)
            result = compare(root, live_service, listening, processes)
            got = result["outcome"]
        ok = got == expected
        cases.append((title, expected, got, ok))
        print(f"  {'✅' if ok else '🔴'} {title}\n"
              f"      ждали: {expected} · вышло: {got}")

    print("САМОПРОВЕРКА · подсадные файлы против ЖИВЫХ слушателей стенда")
    print(f"  служба для опытов: {live_name} (:{live_port}), настоящий номер {real}")
    print("-" * 78)

    # ① контроль ПЕРВЫМ: не зелен контроль — встречные случаи не значат ничего
    case("① контроль: в файле верный номер", MATCHED,
         [(".run", live_file, real)])

    # ② встречный случай критерия ②: чужой ЖИВОЙ номер
    case("② встречный: в файле чужой ЖИВОЙ процесс", FOREIGN_ALIVE,
         [(".run", live_file, own)])

    # ③ встречный случай критерия ③: номера нет в системе — ОТДЕЛЬНЫЙ исход
    case("③ встречный: номера нет в системе", FILE_STALE,
         [(".run", live_file, dead)])

    # ④ находка @OPSSRE 05.09: файлов несколько и они разные
    case("④ встречный: два файла с разными номерами", SEVERAL_FILES,
         [(".run", live_file, real), ("под-репо/.run", live_file, own)])

    # ⑤ два файла с ОДИНАКОВЫМ номером — это НЕ беда, и путать нельзя
    case("⑤ граница: два файла, номер один и тот же ⇒ не беда", MATCHED,
         [(".run", live_file, real), ("под-репо/.run", live_file, real)])

    # ⑥ файла нет вовсе — свой исход, не «совпал» и не «устарел»
    case("⑥ файла нет вовсе", NO_FILE, [])

    # ⑦ в файле не число — отказ мерить, а не молчаливое «совпал»
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / ".run").mkdir()
        (root / ".run" / live_file).write_text("не число", encoding="utf-8")
        result = compare(root, live_service, listening, live_processes(list(listening.values())))
        ok = result["outcome"] == NOT_A_NUMBER
        cases.append(("⑦ в файле не число", NOT_A_NUMBER, result["outcome"], ok))
        print(f"  {'✅' if ok else '🔴'} ⑦ в файле не число\n"
              f"      ждали: {NOT_A_NUMBER} · вышло: {result['outcome']}")

    # ⑧ порча САМОЙ проверки: если исходов оставить два, встречный ③ перестанет
    #    отличаться от ② — и проверка соврёт, не покраснев. Проверяем, что
    #    исходы РАЗНЫЕ, а не только что оба красные.
    two = {c[2] for c in cases if c[0].startswith(("②", "③"))}
    distinct = len(two) == 2
    cases.append(("⑧ исходы ② и ③ РАЗЛИЧНЫ", "два разных", " · ".join(sorted(two)), distinct))
    print(f"  {'✅' if distinct else '🔴'} ⑧ исходы ② и ③ различны (иначе три исхода "
          f"схлопываются в два)\n      вышло: {' · '.join(sorted(two))}")

    # ⑨ ВСТРЕЧНЫЙ СЛУЧАЙ НА ТОТ ДЕФЕКТ, КОТОРЫМ ЭТА ПРОВЕРКА УЖЕ БОЛЕЛА.
    #    Ломаем язык запроса о процессах — ровно как было. Требуем ОТКАЗ мерить,
    #    а не тихое «таких живых нет»: тихий ответ был бы красным, правдоподобным
    #    и неотличимым от честного замера.
    real_call = globals()["_powershell"]

    def broken(command: str) -> str:
        if "Win32_Process" in command:
            return ""           # запрос упал, ответ пуст — как при языке оболочки
        return real_call(command)

    globals()["_powershell"] = broken
    try:
        live_processes([real])
        refused, what_came = False, "вернул ответ как ни в чём не бывало"
    except RuntimeError:
        refused, what_came = True, "ОТКАЗ МЕРИТЬ"
    finally:
        globals()["_powershell"] = real_call
    cases.append(("⑨ порча: запрос о процессах молча пуст ⇒ обязан ОТКАЗАТЬСЯ",
                  "ОТКАЗ МЕРИТЬ", what_came, refused))
    print(f"  {'✅' if refused else '🔴'} ⑨ порча: запрос о процессах молча пуст\n"
          f"      ждали: ОТКАЗ МЕРИТЬ · вышло: {what_came}")

    # ⑩ ВСТРЕЧНЫЙ СЛУЧАЙ НА САМО ЛЕКАРСТВО (карточка #601): слушателем назван номер, которого
    #    в системе нет. Требуем отказ, и отказ ИМЕННО по живости — след говорит «номер
    #    проверен, не жив», — а не по посторонней причине.
    probe = {}
    probe_refusal = listener_refusal(live_port, dead, probe)
    judged_dead = probe_refusal is not None and probe.get(live_port) == (dead, False)
    probe_came = ("ОТКАЗ МЕРИТЬ" if judged_dead else
                  "принял выдуманный номер как живой" if probe_refusal is None else
                  "отказ, но без проверки живости")
    cases.append(("⑩ порча: слушателем назван несуществующий номер ⇒ обязан ОТКАЗАТЬСЯ",
                  "ОТКАЗ МЕРИТЬ", probe_came, judged_dead))
    print(f"  {'✅' if judged_dead else '🔴'} ⑩ порча: слушателем назван несуществующий номер\n"
          f"      ждали: ОТКАЗ МЕРИТЬ · вышло: {probe_came}")

    # ⑪ ЛЕКАРСТВО ИСПОЛНЕНО на настоящем слушателе — по следу, а не по вере. Без него строка
    #    границы не вправе утверждать, что слушатель проверен: удалишь вызов лекарства
    #    выше — здесь покраснеет (карточка #601).
    gate_ran = listener_trace.get(live_port) == (real, True)
    gate_came = "проверен системой, жив" if gate_ran else "лекарство не исполнялось"
    cases.append(("⑪ лекарство исполнено на настоящем слушателе",
                  "проверен системой, жив", gate_came, gate_ran))
    print(f"  {'✅' if gate_ran else '🔴'} ⑪ лекарство исполнено на настоящем слушателе\n"
          f"      ждали: проверен системой, жив · вышло: {gate_came}")

    print("-" * 78)
    passed = sum(1 for _, _, _, c in cases if c)
    print(f"сошлось {passed} из {len(cases)}")
    if passed != len(cases):
        for title, expected, got, c in cases:
            if not c:
                print(f"  🔴 {title}: ждали {expected}, вышло {got}")
        return 1
    print("⚖️ ГРАНИЦА САМОПРОВЕРКИ — что она доказывает и чего НЕ доказывает:")
    # 🔗 Каждое «✅» ниже печатается, только если в ЭТОМ прогоне прошли случаи, которые его
    #    доказывают (карточка #601). Утверждение о себе без доказывающего случая переживает
    #    исчезновение свойства — ровно так строка о живости слушателя пережила снятие лекарства.
    #    Правишь или добавляешь строку «✅» — назови рядом случаи, на которых она стои́т.
    passed_marks = {title.split()[0] for title, _, _, c in cases if c}
    claims = [
        (("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧"), "логика сверки",
         ["   ✅ логику сверки — на подсадных файлах против живых слушателей стенда;"]),
        (("⑩", "⑪"), "живость названного слушателя",
         ["   ✅ что о слушателях СПРОШЕНА СИСТЕМА, а не выдумано число: названный",
          "      слушатель обязан быть живым процессом, иначе отказ мерить (выше);"]),
        (("⑨",), "непустой ответ о процессах",
         ["   ✅ что запрос о процессах не отвечает молча пустым — случай ⑨;"]),
    ]
    for marks, short, lines in claims:
        if set(marks) <= passed_marks:
            for line in lines:
                print(line)
        else:
            missing = " ".join(m for m in marks if m not in passed_marks)
            print(f"   ⛔ НЕ доказано в этом прогоне: {short} — нет прошедшего случая {missing}")
    print("   ⛔ НЕ доказывает, что слушатель порта — именно ЭТА служба: номер живой,")
    print("      но посторонний, здесь прошёл бы. Личность слушателя не проверяется.")
    print("   ⚰️ Прежняя редакция обещала больше: «доказывает случай ①, он сходится")
    print("      только на ЖИВОМ стенде». Он сверял число само с собой и сходился при")
    print("      выдуманном (задача #561). Названная граница опаснее неназванной.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Сверка: номер процесса в файле запуска = слушатель порта службы?")
    # Флаги — английские; прежние русские оставлены синонимами (карточка #601), чтобы
    # старые записи в памяти и записках не стали невыполнимыми строками.
    parser.add_argument("--root", "--корень", dest="root", default=str(CONTAINER),
                        help="где искать каталоги .run с файлами номеров (по умолчанию контейнер)")
    parser.add_argument("--selftest", "--самопроверка", dest="selftest", action="store_true",
                        help="встречные случаи на подсадных файлах против живых служб")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    root = Path(args.root)
    if not root.is_dir():
        print(f"⛔ ОТКАЗ МЕРИТЬ: каталога «{root}» нет")
        return 2
    return run(root)


if __name__ == "__main__":
    sys.exit(main())
