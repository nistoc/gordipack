# -*- coding: utf-8 -*-
r"""bite-prompt-file-choice.py — приёмка карточки #463 (заявка @COORD): выбор файла-поручения
роли при пересоздании держался на КОДЕ СИМВОЛА, а не на замысле.

ПОВОД. Файл выбирался как `sorted(glob(...))[-1]` — последний по алфавиту. У трёх ролей
совпадал не один каталог, и среди них лежали пометки о снятии — тексты, прямо запрещающие
себя исполнять. Побеждал живой файл только потому, что у пары STUD решает символ после
«30m»: разделитель пути (код 92) против дефиса (45). Пометка с именем `stud-sync-99m`
победила бы (проверено @COORD вычислением), и пересозданная роль получила бы текст,
запрещающий себя исполнять, — БЕЗ единого отказа.

⚖️ ГЛАВНЫЙ ВСТРЕЧНЫЙ — случай ①, его потребовала сама заявка: пометка о снятии с именем,
СТАРШИМ по алфавиту, не должна побеждать живой файл. Без него проверка зелена по везению.

🩸 И ДВА СЛУЧАЯ, КОТОРЫЕ ЕДВА НЕ УБИЛИ ЖИВЫЕ НАКАЗЫ (⑥⑦⑧): отбор по словам «снято»,
«⚰️», «не исполнять» их и убивал. Три живых наказа несут «СНЯТО» — про задание
планировщика, а не про себя; живой наказ STUD несёт УСЛОВНЫЙ БУДУЩИЙ запрет («после
12.09 не исполнять без слова владельца») и упоминает НАДГРОБИЕ СОСЕДА. Первая редакция
различителя назвала его снятым. Поймано формой @RCC: мерку натравили на случай, ответ
по которому известен наизусть.

Опыты на ПОДСТАВНЫХ каталогах (MEZO_PROMPTS_ROOT); живые файлы-поручения только читаются.

Случаи:
  ① ВСТРЕЧНЫЙ (главный): пометка о снятии СТАРШЕ по алфавиту — берётся всё равно живой
  ② совпало больше одного: печатаются ВСЕ найденные и назван выбранный
  ③ ноль совпадений — ОТКАЗ, а не заглушка
  ④ ВСЕ совпавшие сняты — ОТДЕЛЬНЫЙ отказ, не тот же, что «файла нет»
  ⑤ ТРЕТИЙ ИСХОД словом: --no-prompt-file собирает пару без файла, отказа нет
  ⑥ живой наказ со словом «СНЯТО» о ДРУГОМ предмете остаётся ЖИВЫМ
  ⑦ живой наказ с УСЛОВНЫМ БУДУЩИМ запретом остаётся ЖИВЫМ
  ⑧ живой наказ, упоминающий надгробие СОСЕДА, остаётся ЖИВЫМ
  ⑨ нечитаемый файл — ТРЕТИЙ исход, не «живой» и не «снят»
  ⑩ ВСТРЕЧНЫЙ: единственный файл — отчёта о выборе НЕТ (признак, горящий всегда, пуст)
  ⑫ ДВА ЖИВЫХ файла — ОТКАЗ с именами обоих, а не догадка по времени правки
  ⑬ ВСТРЕЧНЫЙ: путь, названный рукой, снимает отказ
  ⑪ контроль: живой каталог поручений не тронут, своих следов там нет

📌 24.09 (план «убрать будильники», выбор владельца «Весь план», записка #5312): файл-поручение
ищется только пока правило ритма sync-alarm-in-chat действует. Поэтому случаи ①–⑬ идут на
КОПИИ базы, где правило ЗАКРЕПЛЕНО действующим, — иначе снятие правила в живом своде молча
перевернуло бы отказы ③④ в «пара собрана», и приёмка краснела бы не от поломки, а от решения.
Новые случаи — на копиях, где правило снято и где его нет:
  ⑭ правило СНЯТО, файлов ноль — пара собирается, отказа нет, шага «заведи будильник» нет
  ⑮ правило СНЯТО, все файлы — пометки о снятии — тоже не отказ: файл не ищется вовсе
  ⑯ правила в своде НЕТ — пара собирается, строка «спроси владельца, заводить ли сверки»
  ⑰ стартовая сводка при СНЯТОМ правиле — «будильника сверок нет», без «спроси владельца»
  ⑱ стартовая сводка, когда правила НЕТ — «спроси владельца» остаётся
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # noqa: E402
import mezo_target  # noqa: E402

# Имена в коде — по-английски (слово владельца 07.09: правишь файл — переводишь его имена
# тем же ходом); комментарии и печать — по-русски.
TARGET = mezo_target.script("role-prompts.py")
BRIEF_TOOL = mezo_target.script("role-brief.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

SCRIPTS = mezo_paths.live_scripts()
sys.path.insert(0, str(SCRIPTS))
import mezo_stand  # noqa: E402

OK = FAIL = 0
LIVE_PROMPTS = Path(os.path.expanduser("~")) / ".claude" / "scheduled-tasks"
RHYTHM_RULE = "sync-alarm-in-chat"


def case(name, cond, detail=""):
    global OK, FAIL
    print(("✅" if cond else "🔴"), name)
    if detail:
        print(f"   {detail}")
    OK, FAIL = OK + (1 if cond else 0), FAIL + (0 if cond else 1)


def make_container(stand, name, status):
    """Копия живой базы в своём контейнере; правило ритма закреплено статусом
    (None — правила в своде нет вовсе)."""
    root = Path(stand) / name
    (root / ".mezosync").mkdir(parents=True)
    db = mezo_stand.snapshot_db(mezo_paths.live_db(), root / ".mezosync" / "mezosync.db")
    con = sqlite3.connect(str(db))
    # Контур без этого правила (сосед, свежий контур) — на копии правило подставляется,
    # иначе закрепить нечего; роль PROTO — для случаев ⑰⑱ стартовой сводки.
    if status is not None and con.execute("SELECT 1 FROM rules WHERE rule_key=?",
                                          (RHYTHM_RULE,)).fetchone() is None:
        con.execute("INSERT INTO rules (rule_key, body) VALUES (?, 'подставное правило приёмки')",
                    (RHYTHM_RULE,))
    con.execute("INSERT INTO roles (role, lifecycle) SELECT 'PROTO', 'alive' "
                "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE role='PROTO')")
    if status is None:
        con.execute("DELETE FROM rules WHERE rule_key=?", (RHYTHM_RULE,))
    elif status == "revoked":
        # Схема требует у снятого правила час, автора и причину — как у настоящего снятия.
        con.execute("UPDATE rules SET status='revoked', revoked_at=datetime('now'), "
                    "revoked_by='bite-prompt-file-choice', revoked_reason='копия приёмки' "
                    "WHERE rule_key=?", (RHYTHM_RULE,))
    else:
        con.execute("UPDATE rules SET status=?, revoked_at=NULL, revoked_by=NULL, "
                    "revoked_reason=NULL WHERE rule_key=?", (status, RHYTHM_RULE))
    con.commit()
    row = con.execute("SELECT status FROM rules WHERE rule_key=?", (RHYTHM_RULE,)).fetchone()
    con.close()
    if (row[0] if row else None) != status:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: на копии «{name}» правило ритма не закрепилось ({row!r})")
    return SimpleNamespace(root=root, db=db)


def run_prompts(prompts_root, role, extra=(), where=None):
    where = where or RULE_ACTIVE
    p = subprocess.run(
        [sys.executable, str(TARGET), "--role", role, "--db", str(where.db), *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=mezo_stand.stand_env(where.root, PYTHONIOENCODING="utf-8",
                                 MEZO_PROMPTS_ROOT=str(prompts_root)))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_brief(role, where):
    p = subprocess.run(
        [sys.executable, str(BRIEF_TOOL), "--role", role, "--db", str(where.db)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=mezo_stand.stand_env(where.root, PYTHONIOENCODING="utf-8"))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def put_prompt(prompts_root, name, text):
    d = Path(prompts_root) / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")
    return d / "SKILL.md"


LIVE_PLAIN = "---\nname: {n}\n---\n\nТы — роль. Порядок сверки: читай ленту.\n"
RETIRED_MARK = (
    "---\nname: {n}\ndescription: \"⚰️ НАДГРОБИЕ: задание снято. НЕ ИСПОЛНЯТЬ\"\n---\n\n"
    "# ⚰️ ЗАДАНИЕ СНЯТО — ЭТОТ ФАЙЛ НЕ ИСПОЛНЯЕТСЯ\n\nТекст оставлен как след.\n")
LIVE_WITH_WORD_RETIRED = (
    "---\nname: {n}\n---\n\n⚰️ 2026-08-29 09:49 UTC: задание планировщика СНЯТО по правилу "
    "sync-alarm-in-chat; этот файл — ЖИВОЙ наказ, будильник исполняет его целиком.\n\n"
    "Порядок сверки: читай ленту.\n")
LIVE_ABOUT_NEIGHBOUR = (
    "---\nname: {n}\n---\n\n⚰️ Имя каталога осталось от прежнего ритма; НАДГРОБИЕ "
    "соседнего каталога к этому файлу не относится — там задание снято, здесь нет.\n\n"
    "Порядок сверки: читай ленту.\n")
LIVE_WITH_FUTURE_BAN = (
    "---\nname: {n}\n---\n\n⏳ СРОК ГОДНОСТИ ЭТОГО НАКАЗА — 2026-09-12. После этой даты "
    "первым делом спроси владельца, нужна ли сверка ещё, и не исполнять текст дальше "
    "без его слова.\n⚰️ Имя каталога осталось от прежнего ритма; надгробие соседнего "
    "каталога к этому файлу не относится.\n\nПорядок сверки: читай ленту.\n")

stand = mezo_stand.new("prompt-choice-")
RULE_ACTIVE = make_container(stand, "rule-active", "active")
RULE_RETIRED = make_container(stand, "rule-retired", "revoked")
RULE_ABSENT = make_container(stand, "rule-absent", None)

# ═══ ① ГЛАВНЫЙ ВСТРЕЧНЫЙ: пометка о снятии СТАРШЕ по алфавиту
dir1 = Path(stand) / "к1"
put_prompt(dir1, "zzs-sync-30m", LIVE_PLAIN.format(n="zzs-sync-30m"))
put_prompt(dir1, "zzs-sync-99m", RETIRED_MARK.format(n="zzs-sync-99m"))
rc1, out1 = run_prompts(dir1, "ZZS")
case("① ВСТРЕЧНЫЙ (главный): пометка о снятии СТАРШЕ по алфавиту — взят всё равно ЖИВОЙ",
     rc1 == 0 and "zzs-sync-30m/SKILL.md" in out1.replace("\\", "/")
     and "zzs-sync-99m/SKILL.md" not in out1.replace("\\", "/").split("ВЫБРАН:")[-1],
     f"код {rc1}")

# ═══ ② совпало больше одного — показаны ВСЕ и назван выбранный
case("② совпало больше одного: печатаются ВСЕ найденные и назван выбранный",
     "совпавших каталогов: 2" in out1 and "⚰️ СНЯТ" in out1 and "✅ живой" in out1
     and "👉 ВЫБРАН:" in out1)

# ═══ ③ ноль совпадений — ОТКАЗ
dir2 = Path(stand) / "к2"
dir2.mkdir(parents=True, exist_ok=True)
rc2, out2 = run_prompts(dir2, "ZZS")
case("③ ноль совпадений — ОТКАЗ, а не заглушка",
     rc2 != 0 and "НЕТ НИ ОДНОГО" in out2 and "<путь к наказ-файлу роли>" not in out2,
     f"код {rc2}")

# ═══ ④ ВСЕ совпавшие сняты — ОТДЕЛЬНЫЙ отказ
dir3 = Path(stand) / "к3"
put_prompt(dir3, "zzs-sync-30m", RETIRED_MARK.format(n="zzs-sync-30m"))
put_prompt(dir3, "zzs-old", RETIRED_MARK.format(n="zzs-old"))
rc3, out3 = run_prompts(dir3, "ZZS")
case("④ ВСЕ совпавшие — пометки о снятии: отказ ОТДЕЛЬНЫЙ, не «файла нет»",
     rc3 != 0 and "ВСЕ совпавшие каталоги — пометки о снятии" in out3
     and "НЕТ НИ ОДНОГО" not in out3, f"код {rc3}")

# ═══ ⑤ ТРЕТИЙ ИСХОД словом
rc4, out4 = run_prompts(dir2, "ZZS", extra=("--no-prompt-file",))
case("⑤ ТРЕТИЙ ИСХОД словом: --no-prompt-file собирает пару, отказа нет",
     rc4 == 0 and "ПРОМПТ ЗАКРЫТИЯ" in out4, f"код {rc4}")

# ═══ ⑥⑦⑧ живые, которых убил бы отбор по словам
dir4 = Path(stand) / "к4"
put_prompt(dir4, "zzt-sync-30m", LIVE_WITH_WORD_RETIRED.format(n="zzt-sync-30m"))
rc5, out5 = run_prompts(dir4, "ZZT")
case("⑥ живой наказ со словом «СНЯТО» о ДРУГОМ предмете остаётся ЖИВЫМ",
     rc5 == 0 and "ПРОМПТ ЗАКРЫТИЯ" in out5, f"код {rc5}")

dir5 = Path(stand) / "к5"
put_prompt(dir5, "zzu-sync-30m", LIVE_WITH_FUTURE_BAN.format(n="zzu-sync-30m"))
rc6, out6 = run_prompts(dir5, "ZZU")
case("⑦ живой наказ с УСЛОВНЫМ БУДУЩИМ запретом остаётся ЖИВЫМ",
     rc6 == 0 and "ПРОМПТ ЗАКРЫТИЯ" in out6, f"код {rc6}")
# ⚖️ У ⑧ СВОЙ прогон и своя подсадка. В первой редакции он делил вызов с ⑦ и краснел
# от ЧУЖОЙ поломки — то есть не различал ничего своего. Поймано нарочной поломкой
# «широкое слово»: предсказала 10 из 11, вышло 9, и лишняя красная оказалась находкой.
dir5b = Path(stand) / "к5b"
put_prompt(dir5b, "zzz-sync-30m", LIVE_ABOUT_NEIGHBOUR.format(n="zzz-sync-30m"))
rc6b, out6b = run_prompts(dir5b, "ZZZ")
case("⑧ живой наказ, упоминающий надгробие СОСЕДА, остаётся ЖИВЫМ",
     rc6b == 0 and "ПРОМПТ ЗАКРЫТИЯ" in out6b, f"код {rc6b}")

# ═══ ⑨ нечитаемый файл — третий исход
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location("rp", str(TARGET))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
retired, why = rp._parse_file(str(Path(stand) / "нет-такого-файла.md"))
case("⑨ нечитаемый файл — ТРЕТИЙ исход, не «живой» и не «снят»",
     retired is None and "прочитать не удалось" in why, f"ответ: {retired!r} · {why[:60]}")

# ═══ ⑩ ВСТРЕЧНЫЙ: единственный файл — отчёта НЕТ
dir6 = Path(stand) / "к6"
put_prompt(dir6, "zzv-sync-30m", LIVE_PLAIN.format(n="zzv-sync-30m"))
rc7, out7 = run_prompts(dir6, "ZZV")
case("⑩ ВСТРЕЧНЫЙ: единственный файл — отчёта о выборе НЕТ (не горит всегда)",
     rc7 == 0 and "совпавших каталогов" not in out7 and "👉 ВЫБРАН:" not in out7,
     f"код {rc7}")

# ═══ ⑫ ДВА ЖИВЫХ — ОТКАЗ С ИМЕНАМИ, а не догадка
# 🩸 Случай заведён живым прогоном 30.08 12:17 UTC: у OPSSRE два живых файла — сверка
# каждые полчаса и РАЗОВОЕ напоминание на 31.08. Первая редакция брала последний
# правленый и брала РАЗОВОЕ. Догадка по времени правки сменила бы ошибку на ошибку.
dir7 = Path(stand) / "к7"
put_prompt(dir7, "zzy-sync-30m", LIVE_PLAIN.format(n="zzy-sync-30m"))
put_prompt(dir7, "zzy-разовое-31aug", LIVE_PLAIN.format(n="zzy-razovoe"))
rc8, out8 = run_prompts(dir7, "ZZY")
case("⑫ ДВА ЖИВЫХ файла — ОТКАЗ с именами обоих, а не догадка по времени правки",
     rc8 != 0 and "ЖИВЫХ ФАЙЛОВ БОЛЬШЕ ОДНОГО" in out8
     and "zzy-sync-30m" in out8 and "zzy-разовое-31aug" in out8, f"код {rc8}")

# ═══ ⑬ ВСТРЕЧНЫЙ к ⑫: названный рукой путь снимает отказ
named = str(Path(dir7) / "zzy-sync-30m" / "SKILL.md")
rc9, out9 = run_prompts(dir7, "ZZY", extra=("--prompt-file", named))
case("⑬ ВСТРЕЧНЫЙ: путь, названный рукой, снимает отказ — пара собирается",
     rc9 == 0 and "ПРОМПТ ЗАКРЫТИЯ" in out9 and "НАЗВАН ЯВНО" in out9, f"код {rc9}")

# ═══ ⑭ правило ритма СНЯТО, файлов ноль — пара собирается без отказа и без будильника
# ⚖️ Различает ровно новое поведение: на копии с ДЕЙСТВУЮЩИМ правилом тот же каталог
# даёт отказ ③. Поломка «файл ищется всегда» вернула бы здесь отказ.
rc14, out14 = run_prompts(dir2, "ZZS", where=RULE_RETIRED)
case("⑭ правило ритма СНЯТО, файлов ноль — пара собрана, отказа и шага «заведи будильник» нет",
     rc14 == 0 and "ПРОМПТ ОТКРЫТИЯ" in out14 and "не ищется" in out14
     and "будильник сверок НЕ заводи" in out14 and "заведи будильник ВНУТРИ" not in out14
     and "НЕТ НИ ОДНОГО" not in out14, f"код {rc14}")

# ═══ ⑮ правило СНЯТО, все файлы — пометки о снятии — тоже не отказ
rc15, out15 = run_prompts(dir3, "ZZS", where=RULE_RETIRED)
case("⑮ правило СНЯТО, все файлы — пометки о снятии: не отказ, файл не ищется вовсе",
     rc15 == 0 and "ПРОМПТ ОТКРЫТИЯ" in out15
     and "ВСЕ совпавшие каталоги" not in out15, f"код {rc15}")

# ═══ ⑯ правила в своде НЕТ — пара собирается, решать зовут владельца
# ⚖️ «Снято» и «нет» — разные ответы: первое решено, второе — нет. Поломка, сводящая
# их в одно, покрасит либо ⑭, либо этот случай.
rc16, out16 = run_prompts(dir2, "ZZS", where=RULE_ABSENT)
case("⑯ правила ритма в своде НЕТ — пара собрана, «спроси владельца, заводить ли сверки»",
     rc16 == 0 and "в своде нет" in out16
     and "спроси владельца, заводить ли сверки" in out16
     and "будильник сверок НЕ заводи" not in out16, f"код {rc16}")

# ═══ ⑰⑱ стартовая сводка роли — та же развилка «снято» против «нет»
rc17, out17 = run_brief("PROTO", RULE_RETIRED)
case("⑰ стартовая сводка при СНЯТОМ правиле: «будильника сверок нет», владельца не зовёт",
     rc17 == 0 and "будильника сверок нет" in out17 and "ритм спроси" not in out17,
     f"код {rc17}")
rc18, out18 = run_brief("PROTO", RULE_ABSENT)
case("⑱ стартовая сводка, когда правила НЕТ: «ритм спроси у владельца» остаётся",
     rc18 == 0 and "ритм спроси у владельца" in out18
     and "будильника сверок нет" not in out18, f"код {rc18}")

# ═══ ⑪ контроль: живые поручения не тронуты
neighbours = sorted(p.name for p in LIVE_PROMPTS.iterdir()) if LIVE_PROMPTS.exists() else []
own = [n for n in neighbours if n.lower().startswith(("zzs", "zzt", "zzu", "zzv"))]
case("⑪ контроль: в живом каталоге поручений своих следов нет", not own,
     f"каталогов у соседей: {len(neighbours)} · моих: {len(own)}")

print(f"\n{'✅' if FAIL == 0 else '🔴'} ИТОГ: {OK} из {OK + FAIL}")
sys.exit(mezo_stand.finish(0 if FAIL == 0 else 1))
