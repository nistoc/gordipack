#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""role-prompts.py — ПАРА ПРОМПТОВ ПЕРЕСОЗДАНИЯ РОЛИ: закрытие старого чата + открытие нового.

Слово владельца 2026-08-29 11:16 UTC («заведи role-prompts.py»): пары промптов писались
рукой при каждом пересоздании — рукописный текст с числами протухает, а числа (долг ленты,
раздутые разделы памяти, карточки пула) живут в базе. Инструмент печатает пару ИЗ ЖИВОЙ
базы в момент вызова; владелец копирует блоки в старый и новый чат роли.

    python <КОНТУР>/.mezosync/scripts/role-prompts.py --role STUD

⚖️ ГРАНИЦЫ ВСЛУХ: инструмент ТОЛЬКО ЧИТАЕТ (mode=ro) и печатает текст — ничего не шлёт
и не меняет; период ритма НЕ печатается числом из головы — берётся правило свода
sync-alarm-in-chat (именное слово владельца сильнее, это сказано в самом промпте);
рукописная копия вывода протухает, как любой наказ, — зови в момент пересоздания.
"""
import argparse
import os
import sqlite3
import sys
from glob import glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mezo_paths import resolve_db, live_scripts, container_root  # noqa: E402


def group_label(conn) -> str:
    """Имя контура для промпта (карточка #604 ⑤а): meta.group_name живой базы, запасной
    вариант — имя каталога контейнера без ведущей точки. Раньше здесь стояло впечатанное
    «Atlas» — верно для этого контура, но переносить его как есть в другой контур значило бы
    называть роли чужим именем."""
    row = conn.execute("SELECT value FROM meta WHERE key='group_name'").fetchone()
    name = (row[0] or "").strip() if row else ""
    return name or container_root().name.lstrip(".")

S = live_scripts().as_posix()
# vnext-tools лежит РЯДОМ с .mezosync, не внутри него (раскладка по образцу find-phoenix.py:
# CONTAINER_ROOT / "vnext-tools" / "…") — вычислено от контейнера, а не литералом машины.
V = (container_root() / "vnext-tools").as_posix()


# 🪤 13.09 (перед обновлением tapas): у СОБРАННОГО контура звенья образца лежат РЯДОМ со
# скриптами, у нашего — в vnext-tools; путь только от контейнера печатал бы потребителю
# несуществующий вызов (тот же класс, что находка AIA №6 и tool() в guard-all.py). Ищем в тех
# же четырёх местах; не нашли — называем ожидаемое место и откуда взять, а не молчим.
def _link_path(name):
    scripts = live_scripts()
    candidates = [scripts / name,
                  scripts.parent.parent / "vnext-tools" / name,
                  scripts.parent / "vnext" / "prototype" / name,
                  scripts.parent.parent / "vnext" / "prototype" / name]
    found = next((c for c in candidates if c.exists()), None)
    return (found or candidates[0]).as_posix(), found is not None


SIGNAL_TOOL, SIGNAL_TOOL_FOUND = _link_path("signal-templates.py")
SIGNAL_NOTE = "" if SIGNAL_TOOL_FOUND else (
    "\n   ⚠️ инструмента реестра адресов в этом контуре НЕТ — возьми signal-templates.py из пакета"
    " (vnext/prototype) и положи рядом со скриптами; до того адрес не записывается")
THRESHOLD = 20000


def counts(conn, role):
    cur = conn.execute("SELECT last_read_id FROM read_cursors WHERE reader_role=?",
                       (role,)).fetchone()
    cursor = cur[0] if cur else 0
    backlog_debt = conn.execute("SELECT COUNT(*) FROM messages WHERE id>? AND writer_role<>?",
                        (cursor, role)).fetchone()[0]
    bloated = conn.execute(
        "SELECT section, LENGTH(body) FROM phoenix WHERE role=? AND LENGTH(body)>? "
        "ORDER BY 2 DESC", (role, THRESHOLD)).fetchall()
    pools = [r[0] for r in conn.execute("SELECT track_id FROM tracks WHERE status='active'")]
    cards = []
    if pools:
        ph = ",".join("?" * len(pools))
        cards = conn.execute(
            f"SELECT id, title FROM backlog WHERE role=? AND parent_track IN ({ph}) "
            f"AND status IN ('open','in_progress','blocked','awaiting_word','in_review') "
            f"ORDER BY id", (role, *pools)).fetchall()
    rule_row = conn.execute(
        "SELECT status FROM rules WHERE rule_key='sync-alarm-in-chat'").fetchone()
    return backlog_debt, bloated, cards, (rule_row and rule_row[0] == "active")


# ═══ Карточка #463 (заявка @COORD, слово владельца 30.08 10:06 UTC «починить выбор файла
# до пересоздания ролей»). Прежде файл-поручение выбирался так:
#     sorted(glob(...))[-1]      — ПОСЛЕДНИЙ ПО АЛФАВИТУ
# У трёх ролей совпадал не один каталог, и среди них лежали ПОМЕТКИ О СНЯТИИ — тексты,
# прямо запрещающие себя исполнять. Сегодня побеждал живой файл, но держалось это
# на коде символа: у пары STUD сравниваются «stud-sync-30m\SKILL.md» и
# «stud-sync-30m-stop\SKILL.md», решает символ после «30m» — разделитель пути (92)
# против дефиса (45). Пометка с именем stud-sync-99m победила бы (проверено @COORD
# вычислением), и пересозданная роль получила бы текст, запрещающий себя исполнять.
#
# 🩸 И ЛОВУШКА, НАЙДЕННАЯ ЗАМЕРОМ НА ЖИВЫХ ФАЙЛАХ, а не рассуждением: отбирать по словам
# «СНЯТО» и «⚰️» НЕЛЬЗЯ. Их несут ТРИ ЖИВЫХ наказа (PROTO, ING, OPSSRE) — там снято
# ЗАДАНИЕ ПЛАНИРОВЩИКА, а сам текст живой и исполняется будильником внутри разговора.
# Это ровно класс карточки #398: пометка о снятии, относящаяся к ДРУГОМУ предмету
# в той же строке. Обратная ловушка тоже живая: пометка ing-sync-30m несёт слова
# «Живой наказ — соседний каталог», то есть признак живого — О ЧУЖОМ файле.
# ⇒ Различитель — не слово «снято» и не слово «живой», а то, ГОВОРИТ ЛИ ТЕКСТ О СЕБЕ.
# 🩸 ПЕРВАЯ РЕДАКЦИЯ ЭТОГО СПИСКА БЫЛА «не исполнять» / «не исполняется» — и она назвала
# снятым ЖИВОЙ наказ STUD. Там стои́т «⏳ СРОК ГОДНОСТИ… после этой даты… не исполнять
# текст дальше без его слова» — запрет УСЛОВНЫЙ и БУДУЩИЙ, а не пометка о снятии.
# Слово «надгробие» тоже не годится: живой наказ STUD упоминает надгробие СОСЕДА.
# Поймано формой @RCC (записка #4457): натравить мерку на случай, ответ по которому
# знаешь наизусть, — прогноз «снятых два» не сошёлся, вышло три, и третий был живым.
# ⇒ Годится только САМОРЕФЕРЕНЦИЯ: текст запрещает исполнять ИМЕННО СЕБЯ.
RETIRED_MARKERS = ("не исполнять текст ниже", "этот файл не исполняется",
        "не исполнять текст ниже", "не исполнять — текст ниже")
LIVE_ABOUT_SELF = ("этот текст живой", "этот файл — живой наказ", "этот файл - живой наказ")
HEAD_CHARS = 4000        # знаков от начала: и заголовок описания, и первые абзацы


def _parse_file(path):
    """Живой файл или пометка о снятии. Возвращает (снят, почему)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            head_text = f.read(HEAD_CHARS).lower()
    except OSError as e:
        return None, f"прочитать не удалось: {e}"      # третий исход, не «живой»
    self_alive_marker = next((marker for marker in LIVE_ABOUT_SELF if marker in head_text), None)
    if self_alive_marker:
        return False, f"объявляет себя живым: «{self_alive_marker}»"
    self_retired_marker = next((marker for marker in RETIRED_MARKERS if marker in head_text), None)
    if self_retired_marker:
        return True, f"запрещает себя исполнять: «{self_retired_marker}»"
    return False, "признаков снятия нет"


# Где лежат файлы-поручения. Переменная названа ВСЛУХ, а не спрятана внутри условия:
# приёмка обязана уметь поставить опыт на подставных каталогах — трогать живые чужие
# поручения ради проверки нельзя. Это видимая договорённость, а не тихое исключение.
PROMPTS_ROOT_ENV = "MEZO_PROMPTS_ROOT"


def _prompts_root():
    return os.environ.get(PROMPTS_ROOT_ENV) or os.path.join(
        os.path.expanduser("~"), ".claude", "scheduled-tasks")


def mandate_files(role):
    """ВСЕ совпавшие каталоги с разбором каждого. Выбор — отдельно, чтобы он был виден."""
    paths = sorted(glob(os.path.join(_prompts_root(),
                                    f"*{role.lower()}*", "SKILL.md")))
    found = []
    for path in paths:
        retired, why = _parse_file(path)
        found.append({"path": path.replace("\\", "/"), "retired": retired, "why": why,
                        "mtime": os.path.getmtime(path) if os.path.exists(path) else 0})
    return found


def choose_mandate(found):
    """(выбранный или None, строки отчёта). Отчёт печатается ВСЕГДА при неоднозначности.

    ⛔ Ноль совпадений и «все совпавшие — пометки о снятии» — РАЗНЫЕ исходы, и оба отказ:
    прежде оба выглядели как исправная работа (печаталась заглушка «<путь к наказ-файлу>»).
    """
    report = []
    alive_entries = [entry for entry in found if entry["retired"] is False]
    retired_entries = [entry for entry in found if entry["retired"] is True]
    unreadable_entries = [entry for entry in found if entry["retired"] is None]
    if len(found) > 1 or retired_entries or unreadable_entries:
        report.append(f"📁 совпавших каталогов: {len(found)} — показываю ВСЕ, "
                     f"выбор виден строкой ниже")
        for entry in found:
            marker_icon = ("⚰️ СНЯТ" if entry["retired"]
                          else ("⚠️ НЕЧИТАЕМ" if entry["retired"] is None else "✅ живой"))
            report.append(f"   {marker_icon}  {entry['path']}  ({entry['why']})")
    if not found:
        report.append("⛔ файла-поручения НЕТ НИ ОДНОГО — это ОТКАЗ, а не «пустой наказ». "
                     "Прежде здесь печаталась заглушка, и отсутствие файла было "
                     "неотличимо от исправной работы (замер @COORD, карточка #463)")
        return None, report
    if not alive_entries:
        report.append("⛔ ВСЕ совпавшие каталоги — пометки о снятии: исполнять нечего. "
                     "Это ОТДЕЛЬНЫЙ исход, он не то же, что «файла нет»")
        return None, report
    # 🩸 БОЛЬШЕ ОДНОГО ЖИВОГО — ОТКАЗ, А НЕ ДОГАДКА. Первая редакция брала последний
    # правленый и печатала предупреждение. Живой прогон 30.08 12:17 UTC показал, чего это
    # стои́т: у OPSSRE два живых файла (сверка каждые 30 минут и РАЗОВОЕ напоминание
    # на 31.08), и по времени правки побеждало разовое. То есть догадка сменила ошибку
    # на ошибку: было «выбирает по коду символа», стало «выбирает по времени правки» —
    # а время правки лжёт не реже (копия сохраняет время старого файла).
    # ⇒ Неоднозначность — ИСХОД, а не помеха. Её называют, а не решают за человека.
    if len(alive_entries) > 1:
        report.append(f"⛔ ЖИВЫХ ФАЙЛОВ БОЛЬШЕ ОДНОГО ({len(alive_entries)}) — выбирать за тебя "
                     f"не буду: у них разное назначение, и машине оно не видно")
        for entry in alive_entries:
            report.append(f"   · {entry['path']}")
        report.append("   👉 назови нужный доводом: --prompt-file <путь>")
        return None, report
    chosen = alive_entries[0]
    if len(found) > 1 or retired_entries or unreadable_entries:
        report.append(f"👉 ВЫБРАН: {chosen['path']}")
    return chosen["path"], report


def main():
    ap = argparse.ArgumentParser(description="Пара промптов пересоздания роли из живой базы")
    ap.add_argument("--role", required=True)
    ap.add_argument("--db", default=None)
    ap.add_argument("--prompt-file", default=None,
                    help="путь к файлу-поручению НАЗВАН ЯВНО: нужен, когда живых файлов "
                         "у роли больше одного и машине их назначение не видно")
    ap.add_argument("--no-prompt-file", action="store_true",
                    help="у роли НЕТ файла-поручения, и это сказано НАРОЧНО: пара "
                         "собирается без него. Без этого довода отсутствие файла — отказ")
    a = ap.parse_args()
    role = a.role.upper()
    db = Path(resolve_db(a.db, __file__))
    if not db.exists():
        sys.exit(f"⛔ ПАРА НЕ СОБРАНА: базы нет ({db}) — это не «пустые промпты»")
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    backlog_debt, bloated, cards, rhythm_active = counts(conn, role)
    group_name = group_label(conn)
    conn.close()
    if a.prompt_file:
        # Названный рукой путь сильнее любого отбора — но он ОБЯЗАН существовать:
        # молча принять несуществующий значило бы вернуть ту же заглушку другим путём.
        mandate_file, file_report = a.prompt_file.replace("\\", "/"), [
            f"📌 файл-поручение НАЗВАН ЯВНО доводом: {a.prompt_file}"]
        if not os.path.exists(a.prompt_file):
            sys.exit(f"⛔ ПАРА НЕ СОБРАНА: названного файла нет на диске ({a.prompt_file})")
    else:
        mandate_file, file_report = choose_mandate(mandate_files(role))
    for line in file_report:
        print(line, file=sys.stderr)
    if mandate_file is None:
        if not a.no_prompt_file:
            sys.exit(
                "⛔ ПАРА НЕ СОБРАНА: у роли нет исполнимого файла-поручения (см. выше).\n"
                "   Это отказ НАРОЧНО: заглушка вместо пути выглядела исправной работой,\n"
                "   и пересозданная роль получала текст без поручения — молча.\n"
                "   Если файла и не должно быть (ритм ведёт только разговор), скажи это\n"
                "   явно: повтори вызов с --no-prompt-file.")
        mandate_file = "<файла-поручения у роли НЕТ — сказано явно доводом --no-prompt-file>"

    shrink_block = "".join(
        f"   ⚠️ Раздел {s} раздут: {n} знаков при пороге {THRESHOLD} — СОЖМИ ниже порога\n"
        f"   (история памяти хранит прежнее целиком), сохраняй с --allow-shrink;\n"
        f"   приказы и права сверяй ПОИМЁННО, не глазами по объёму.\n"
        for s, n in bloated) or "   (раздутых разделов нет — сохраняй как есть)\n"
    tasks_block = "".join(f"   карточка #{i} — {t[:70]}\n" for i, t in cards) \
        or "   (карточек пула на роли нет — первое дело возьми из ленты и стартовой сводки)\n"

    # 🪤 КАРТОЧКА #604 ④ (возврат OPSSRE): здесь раньше стояло ЕЩЁ одно предупреждение —
    # «правило sync-alarm-in-chat не активно — блок ритма проверь рукой, стандарту не верь».
    # До ⑤б это было верно (блок печатался БЕЗУСЛОВНО, и его правда стоило перепроверить
    # рукой). После ⑤б блок сам решает — «рукой проверь» рядом с уже решённым шагом читалось
    # бы как «инструмент не доверяет своему же выводу». Строка ниже (rhythm_block) и есть
    # честный ответ — второй, противоречащий ей, не нужен.
    # 🪤 КАРТОЧКА #604 ⑤б: «Шаг 4 — ритм» печатается ТОЛЬКО когда правило sync-alarm-in-chat
    # есть в своде И активно — иначе он зовёт правило, которого промпт открытия не найдёт
    # (`set-rule.py --show` ответит «правила нет»), и роль получает шаг, исполнить который
    # нечем. Вместо шага — честная строка: решать заводить ли сверки, зовёт владельца.
    if rhythm_active:
        rhythm_block = (
            "Шаг 4 — ритм (правило свода sync-alarm-in-chat): заведи будильник ВНУТРИ этого чата\n"
            "   (минуты возьми не :00 и не :30) с промптом «исполни наказ-файл "
            f"{mandate_file}».\n"
            "   Период — именное слово владельца твоей роли; без слова — 30 минут. "
            "Задачу-расписание\n"
            "   вне чата НЕ заводи. Правило целиком:\n"
            f"   python {S}/set-rule.py --key sync-alarm-in-chat --show\n")
    else:
        rhythm_block = ("ритм: правила sync-alarm-in-chat в своде этого контура нет — "
                        "спроси владельца, заводить ли сверки\n")

    print(f"""═══ ПРОМПТ ЗАКРЫТИЯ (вставить в СТАРЫЙ чат {role}) ═══

Финальное задание этого чата — роль {role} пересоздаётся (слово владельца, порядок
открытия пула). НИЧЕГО НОВОГО НЕ НАЧИНАЙ.

1. Сохрани память — все разделы свежими. Сначала перечитай СВОЮ последнюю записку
   в ленте (память отстаёт от неё), затем обнови отставшие разделы:
   python {S}/save-phoenix.py --role {role} --section <раздел> --file <файл>
{shrink_block}2. Прощальная записка в ленту: что сделано, что открыто, где след:
   python {S}/write-message.py --role {role} --file <нота.md>
3. Долг ленты (~{backlog_debt} записок) НЕ разбирай — его примет новый чат.
После записки — стоп: не бери карточки, не правь файлы.

═══ ПРОМПТ ОТКРЫТИЯ (вставить в НОВЫЙ чат {role}) ═══

Ты — роль {role} контура мезосинк {group_name}. Чат свежий после пересоздания.
Пути АБСОЛЮТНЫЕ, все метки времени UTC с суффиксом «UTC».

Шаг 0: python {S}/guard-all.py
Шаг 0-бис — отметить пересоздание (час = рождение этого чата; регламент карточки #538
   хранит последнюю версию памяти ПЕРЕД каждой такой отметкой):
   MEZO_ROLE={role} python {S}/rebirth-mark.py --role {role}
Шаг 1 — собранный наказ (несёт зону, права, карточки, ритм и правило ответов):
   python {S}/role-brief.py --role {role}
Шаг 2 — память: python {S}/read-phoenix.py --role {role}
   ⚠️ Память сохранена ДО последней записки роли — первой прочитай СВОЮ последнюю записку.
Шаг 3 — лента (долг ~{backlog_debt} записок): читай ЦЕЛИКОМ, подтверждай --ack; длинно —
   сужай ЗАПРОС (--limit порциями), не вывод:
   python {S}/read-messages.py --role {role}
{rhythm_block}Шаг 4-бис — адрес сессии, КАЖДОЕ пробуждение (правило rhythm-survives-rebirth п.①: имя
   сессии принадлежит процессу, возобновлённый чат получает НОВОЕ — прежняя запись
   реестра указывает в пустоту). Узнай СТОЙКИЙ идентификатор вызовом приложения
   get_session("self") (поле sessionId вида local_…: он переживает возобновление, в
   отличие от имени) и короткое имя из ListAgents («This session is <имя [код]>»),
   запиши ОБА:
   python {SIGNAL_TOOL} --role {role} --set-address "<имя [код]>" --session-id "<sessionId>"{SIGNAL_NOTE}
Шаг 5 — первое дело (карточки активного пула первыми, взятие — с живым объявлением):
{tasks_block}Правило ответов владельцу — перед КАЖДЫМ ответом:
   python {S}/set-rule.py --key owner-reply-format --show""")


if __name__ == "__main__":
    main()
