"""
init-group.py — Создаёт новую группу агентов (mezosync.db) по шаблону.

Использование:
    python init-group.py --name "atlas" --path "C:\\guts\\.atlas\\.mezosync" --domain data-platform
    python init-group.py --name "webapp" --path "C:\\projects\\app\\.mezosync" --domain frontend-spa
"""

import argparse
import hashlib
import re
import shutil
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
# v3 (2026-08-08): схема СОБИРАЕТСЯ из живой базы (vnext/tools/gen-schema.py), а не пишется
# рукой. Повод — замер: рукописная v2 отстала от живой на ПЯТЬ сосудов (основание правил
# полями, возраст взгляда у памяти, имена адресатов, права роли, разгон сна), и заметить
# это было нечем. Контур, собранный из v2 в тот день, не получал НИЧЕГО из сделанного
# за смену и выглядел исправным: приёмки шаблона проверяют то, что в шаблоне ЕСТЬ.
# ⚖️ Рукописная схема — вторая копия правды, а вторая копия расходится молча.
# ⚡ 2026-08-10: ФАЙЛ СХЕМЫ ВЫБИРАЕТСЯ ЗАМЕРОМ ПО ДИСКУ — свежайший mezosync_v<N>.sql, —
#    а не впечатан. История класса в этом самом репо, третий заход подряд:
#    init-group-vnext ссылался на v1 при живой v2 (записано в его же шапке) · этот файл
#    держал «v3» в день объявления рубежа v4. Впечатанный номер версии протухает В ДЕНЬ
#    следующего рубежа — по построению, и молча: сборщик продолжает собирать вчерашний
#    контур, а приёмки шаблона проверяют то, что в шаблоне ЕСТЬ.


def _latest_schema() -> Path:
    cands = sorted((REPO_ROOT / "schema").glob("mezosync_v*.sql"),
                   key=lambda p: int("".join(ch for ch in p.stem.split("_v")[-1]
                                             if ch.isdigit()) or 0))
    if not cands:
        raise SystemExit("⛔ НЕ ЗАПУСТИЛАСЬ: в schema/ нет ни одного mezosync_v*.sql — "
                         "собери его из живой базы: python vnext/tools/gen-schema.py")
    return cands[-1]


SCHEMA_FILE = _latest_schema()
UNIVERSAL_RULES = REPO_ROOT / "rules" / "universal.sql"
DOMAIN_RULES_DIR = REPO_ROOT / "rules" / "domain-specific"


def main():
    parser = argparse.ArgumentParser(description="Инициализация новой группы агентов Горди")
    parser.add_argument("--name", required=True, help="Имя группы (например: atlas, webapp)")
    parser.add_argument("--path", required=True, help="Путь к директории .mezosync")
    parser.add_argument("--domain", default=None,
                        help="Доменный пресет правил (data-platform, frontend-spa)")
    parser.add_argument("--roles", nargs="+", default=["coord"],
                        help="Роли, которым завести отметку прочитанного (по умолчанию: coord)")
    args = parser.parse_args()

    mezosync_dir = Path(args.path)
    mezosync_dir.mkdir(parents=True, exist_ok=True)
    db_path = mezosync_dir / "mezosync.db"

    if db_path.exists():
        print(f"⚠️  БД уже существует: {db_path}")
        resp = input("Перезаписать? (y/N): ").strip().lower()
        if resp != "y":
            print("Отмена.")
            sys.exit(0)
        db_path.unlink()

    print(f"📦 Создаю {db_path}...")
    conn = sqlite3.connect(str(db_path))

    # 1. Схема
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    # 🪤 Здесь стояло «Схема v2 применена» — ВПЕЧАТАННЫМ ЧИСЛОМ. 2026-08-08 сборку перевели
    # на v3, и надпись стала врать: она печатала имя, которого у механизма больше нет,
    # и печатала уверенно. Поймано в первую же минуту — но только потому, что я не поверил
    # надписи и спросил базу.
    # ⇒ Имя берётся из ФАЙЛА, а не пишется рядом: пересказ имени — это вторая копия.
    print(f"  ✅ Схема применена: {SCHEMA_FILE.name}")

    # 2. Имя группы
    # 🪤 БЫЛО «UPDATE … WHERE key='group_name'» — а строки в свежей базе НЕТ: схема заводит
    # пустую таблицу meta. Обновление нуля строк проходит без ошибки, и контур рождался
    # БЕЗЫМЯННЫМ. Вскрылось 18.08 при связывании со вторым проектом: связь записалась как
    # «atlas ↔ unknown», хотя сборка отчиталась об успехе — имени просто негде было взяться.
    # ⚖️ Поэтому не только вставка, но и ЧТЕНИЕ ОБРАТНО: успех сборки судится по базе.
    conn.execute("INSERT INTO meta (key, value) VALUES ('group_name', ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (args.name,))
    got = conn.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
    if not got or got[0] != args.name:
        sys.exit(f"⛔ СБОРКА ОСТАНОВЛЕНА: имя группы не записалось (в базе {got}). "
                 f"Безымянный контур выглядит исправным, но всякая связь с ним "
                 f"и всякий отчёт назовут его «unknown».")
    print(f"  ✅ Имя группы: {got[0]} (спрошено У БАЗЫ, не по факту вставки)")

    # 3. Универсальные правила
    rules_sql = UNIVERSAL_RULES.read_text(encoding="utf-8")
    conn.executescript(rules_sql)
    print("  ✅ Универсальные правила загружены")

    # 4. Доменные правила
    if args.domain:
        domain_file = DOMAIN_RULES_DIR / f"{args.domain}.sql"
        if domain_file.exists():
            domain_sql = domain_file.read_text(encoding="utf-8")
            conn.executescript(domain_sql)
            print(f"  ✅ Доменные правила [{args.domain}] загружены")
        else:
            print(f"  ⚠️  Доменный пресет '{args.domain}' не найден, пропускаю")

    # 5. Курсоры для ролей — ИМЯ РОЛИ В ВЕРХНЕМ РЕГИСТРЕ.
    # 🪤 НАЙДЕНО ЗАПУСКОМ СВЕЖЕГО КОНТУРА 10.08 01:09 UTC (#145): сборка заводила курсор
    # «coord», а читалка регистрозависима и отвечала «роль COORD не в реестре (есть:
    # coord, proto)». То есть контур из шаблона рождался СЛОМАННЫМ: первая же команда
    # первой роли падала, и падала с подсказкой «заведи явно --register» — то есть звала
    # завести ВТОРУЮ роль-двойника поверх существующей.
    # ⚖️ Класс тот же, что у нас с токенами ролей: одно имя, два регистра, две правды.
    roles = [r.upper() for r in args.roles]
    for role in roles:
        conn.execute(
            "INSERT OR IGNORE INTO read_cursors (reader_role, last_read_id) VALUES (?, 0)",
            (role,)
        )
    print(f"  ✅ Отметки прочитанного: {', '.join(roles)}")

    # 6. ЖУРНАЛ ШАГОВ — контур обязан знать СВОЮ версию (#145, замер 10.08 01:07 UTC).
    # 🪤 Свежесобранный контур отвечал `schema_version → (None, 0, 0)`: сосуды на месте,
    # а истории нет. Версия у нас ВЫЧИСЛЯЕТСЯ из журнала (шаг 006, ровно потому, что
    # хранимый номер врал две версии подряд) — и сборка молча оставляла её пустой.
    # ⇒ Контур, не знающий своей версии, нечем ни проверить, ни обновить: шаг схемы не
    # знает, накатывать ли ему себя. Отпечаток берётся от ФАЙЛА схемы, а не пишется рукой.
    # 🪤 ПЕРВАЯ РЕДАКЦИЯ ПИСАЛА В КОЛОНКУ `step`, КОТОРОЙ НЕТ (колонка зовётся `version`).
    # INSERT прошёл, надпись «Журнал шагов ✅» напечаталась — а версия осталась пустой,
    # и контур по-прежнему не знал себя. Имена колонок я УГАДАЛ вместо того, чтобы
    # спросить схему: ровно тот класс, что мы лечим у чисел, только про имена.
    # 🪤 ВТОРАЯ ОШИБКА ЗДЕСЬ ЖЕ: я считал отпечаток от ТЕКСТА ФАЙЛА схемы, а сторож
    # журнала считает его от СТРУКТУРЫ БАЗЫ. Свежесобранный контур немедленно краснел
    # «схему меняли мимо журнала» — сторож был прав, врал мой отпечаток.
    # ⇒ Беру ГОТОВУЮ функцию журнала, а не пишу вторую: две меры одного — две правды,
    # и расходятся они молча (ровно то, чем занята вся эта карточка).
    sys.path.insert(0, str(SCRIPT_DIR))
    from schema_journal import fingerprint as _fp
    fp = _fp(conn)
    # версия берётся ИЗ ИМЕНИ ФАЙЛА схемы (mezosync_v3.sql → v3), а не пишется рядом;
    # VIEW schema_version ищет вехи по образцу 'v[0-9]*' — форма обязана совпасть
    milestone = "v" + "".join(ch for ch in SCHEMA_FILE.stem.split("_v")[-1] if ch.isdigit())
    conn.execute("INSERT OR IGNORE INTO schema_migrations (version, applied_at, note,"
                 " fingerprint) VALUES (?, datetime('now'), ?, ?)",
                 (milestone, f"сборка из шаблона gordipack ({SCHEMA_FILE.name})", fp))
    got = conn.execute("SELECT version, steps_total FROM schema_version").fetchone()
    if not got or not got[0]:
        print("  ⛔ ЖУРНАЛ НЕ ПРИНЯЛ ВЕХУ: контур не знает своей версии — это НЕ «готово»")
        sys.exit(2)
    print(f"  ✅ Журнал шагов: веха {got[0]} · отпечаток {fp} (спрошено У БАЗЫ, не по факту вставки)")

    conn.commit()
    conn.close()

    # 7. ИНСТРУМЕНТЫ — БЕЗ НИХ КОНТУР НЕ КОНТУР, А ФАЙЛ БАЗЫ (#145).
    # 🪤 До 10.08 сборка клала ОДИН mezosync.db и печатала «группа готова». Роль в таком
    # контуре не могла вызвать НИЧЕГО: ни прочесть ленту, ни сохранить память. Приёмки
    # шаблона этого не видели, потому что гоняли скрипты ИЗ ШАБЛОНА по свежей базе — то
    # есть проверяли не то, что получает потребитель. Третий оборот класса «испытываем
    # не то, что чиним» за двое суток, и самый дорогой: он про ПЕРВЫЙ ЧАС чужой команды.
    tools_dir = mezosync_dir / "scripts"
    tools_dir.mkdir(exist_ok=True)
    copied = 0
    for src in sorted(SCRIPT_DIR.glob("*.py")):
        if src.name == "init-group.py":       # сборщик живёт в шаблоне, а не в контуре
            continue
        (tools_dir / src.name).write_bytes(src.read_bytes())
        copied += 1
    migr_src = SCRIPT_DIR / "migrations"
    if migr_src.is_dir():
        (tools_dir / "migrations").mkdir(exist_ok=True)
        for m in sorted(migr_src.glob("*.py")):
            (tools_dir / "migrations" / m.name).write_bytes(m.read_bytes())

    # 7б. ЗВЕНЬЯ ИЗ vnext/prototype, КОТОРЫЕ СКРИПТЫ ЗОВУТ ПО ИМЕНИ — СПИСОК БЕРЁТСЯ
    # ЗАМЕРОМ ПО КОДУ, А НЕ ПИШЕТСЯ РУКОЙ. Рукописный список устаревает молча: механизм
    # добавят, имя дописать забудут — и он останется невидим для сборки, выглядя готовым
    # (этим контур уже платил, находка @COORD 10.08).
    # 🪤 Найдено запуском свежего контура: write-message честно печатал «проверка ссылок
    # НЕ ВЫПОЛНЕНА» — механизм деградировал ГРОМКО и тем спас; кладём звено, чтобы
    # деградации не было вовсе.
    # ⚡ ЕДИНИЦА ПЕРЕНОСА — ЗАМЫКАНИЕ, А НЕ ФАЙЛ. Звено тянет то, что зовёт и импортирует;
    # иначе потребитель получает половину связки. 🪤 Найдено запуском: звено проверки меток
    # приехало и упало `ModuleNotFoundError: mention` — его модуль-различитель не назван
    # ни в одном скрипте, поэтому в список замером не попал. Список, замкнутый наполовину,
    # хуже пустого: он выглядит собранным.
    proto_dir = REPO_ROOT / "vnext" / "prototype"
    linked = 0
    if proto_dir.is_dir():
        want = set()
        for s in SCRIPT_DIR.glob("*.py"):
            want |= set(re.findall(r'"([a-z0-9_.-]+\.py)"',
                                   s.read_text(encoding="utf-8", errors="replace")))
        seen = set()
        while want:
            name = want.pop()
            if name in seen:
                continue
            seen.add(name)
            src = proto_dir / name
            if not src.exists():
                continue
            if not (tools_dir / name).exists():
                (tools_dir / name).write_bytes(src.read_bytes())
                linked += 1
            body = src.read_text(encoding="utf-8", errors="replace")
            want |= set(re.findall(r'"([a-z0-9_.-]+\.py)"', body))
            want |= {m + ".py" for m in re.findall(r"^\s*import\s+([a-z_][a-z0-9_]*)",
                                                   body, re.M)}
    print(f"  ✅ Инструменты: {copied} скриптов + {linked} звеньев (замером) → {tools_dir}")

    # 7в. ЗЕРКАЛО ПРАВИЛ — собирается СРАЗУ, а не при первой правке (#145).
    # 🪤 Свежий контур краснел «правил в базе 35, а файла НЕТ»: механизм пересборки есть
    # (#108/#110), но у нового контура ему нечего было пересобирать — первый читатель
    # видел красное там, где ничего не сломано. Красное на пустом месте учит пролистывать.
    import subprocess as _sp
    exporter = tools_dir / "export-rules.py"
    if exporter.exists():
        gen = mezosync_dir / "generated"
        gen.mkdir(exist_ok=True)
        r = _sp.run([sys.executable, str(exporter), "--db", str(db_path),
                     "--out", str(gen / "sync.rules.md"), "--apply"],
                    capture_output=True, text=True, timeout=60)
        made = (gen / "sync.rules.md").exists()
        print(f"  {'✅' if made else '⛔'} Зеркало правил: "
              + (str(gen / 'sync.rules.md') if made
                 else f"НЕ СОБРАНО — {(r.stderr or r.stdout).strip().splitlines()[-1][:80]}"))

    # 7г. ЗАГОТОВКА ПАМЯТИ РОЛИ — контур рождается С ПАМЯТЬЮ, а не пустым (#145).
    # 🪤 Свежий контур краснел трижды об одном: «в phoenix нет ничего», «курсор без
    # слепка — воскресший мертвец/фантом». Сторожа правы: курсор без памяти в ЖИВОМ
    # контуре и правда призрак. Но у НОВОРОЖДЁННОГО контура это норма — и первый экран
    # первой роли встречал её тремя красными, ни одно из которых она не создавала.
    # ⇒ Кладём заготовку из templates/: роль получает launcher и §identity, сторожа молчат
    # по делу, а не по слепоте. Текст заготовки — из ФАЙЛА шаблона, не сочиняется здесь.
    tpl_dir = REPO_ROOT / "templates"
    # Заготовки едут В КОНТУР целиком: роль и владелец читают их у себя, а не в чужом
    # каталоге автора шаблона — того может не быть на машине вовсе.
    if tpl_dir.is_dir():
        dest = mezosync_dir / "templates"
        dest.mkdir(parents=True, exist_ok=True)
        for src in tpl_dir.glob("*.md"):
            shutil.copy2(src, dest / src.name)
        print(f"  ✅ Заготовки запуска: {len(list(dest.glob('*.md')))} файлов → {dest}")
    seeded = 0
    if tpl_dir.is_dir():
        conn2 = sqlite3.connect(str(db_path))
        cols = [c[1] for c in conn2.execute("PRAGMA table_info(phoenix)")]
        for role in roles:
            tpl = tpl_dir / ("coordinator.md" if role == "COORD" else "repo-dev.md")
            if not tpl.exists():
                continue
            head = [
                f"# {role} — ЗАГОТОВКА, положена сборкой из шаблона",
                "",
                "⚠️ Это НЕ память роли, а её ПУСТАЯ ФОРМА: роль обязана заменить её",
                "собственным словом при первом же сохранении. Пока текст ниже — общий",
                "шаблон роли, а не то, что знает именно эта роль в этом контуре.",
                "",
            ]
            body = "\n".join(head) + tpl.read_text(encoding="utf-8")[:4000]
            row = {"role": role, "section": "identity", "body": body}
            use = [c for c in cols if c in row]
            conn2.execute(f"INSERT OR IGNORE INTO phoenix ({', '.join(use)})"
                          f" VALUES ({', '.join('?' * len(use))})", [row[c] for c in use])
            seeded += 1
        conn2.commit()
        conn2.close()
    print(f"  ✅ Заготовка памяти: {seeded} ролям (§identity из templates/)")

    # 8. ПРОБА СОБРАННОГО — «ГОТОВА» ГОВОРИТ ЗАПУСК, А НЕ СБОРЩИК (#145).
    # 🪤 Три дефекта подряд нашлись ТОЛЬКО потому, что я вызвал инструменты свежего
    # контура руками: курсор в нижнем регистре (первая же команда падала), пустая версия
    # схемы, звено, зовущее mezo_paths.live_db — метода, которого в ШАБЛОННОМ mezo_paths
    # нет (два файла с одним именем и разной начинкой: 145 строк против 81).
    # ⇒ Сборка, которая не пробует собранное, печатает «готово» про непроверенное.
    import subprocess
    probes = [("read-messages.py", ["--role", roles[0]]),
              ("read-phoenix.py", ["--role", roles[0]]),
              ("backlog.py", ["list", "--role", roles[0]])]
    broken = []
    for name, argv in probes:
        p = tools_dir / name
        if not p.exists():
            broken.append(f"{name} — НЕ ПОЛОЖЕН вовсе")
            continue
        r = subprocess.run([sys.executable, str(p), *argv],
                           capture_output=True, text=True, timeout=60)
        err = (r.stderr or "")
        if r.returncode not in (0, 1) or "Traceback" in err or "Error" in err:
            first = next((ln for ln in err.splitlines()[::-1] if ln.strip()), "")
            broken.append(f"{name} — {first[:90]}")
    # звенья: падение при импорте видно только запуском, и оно тихое
    for name in sorted(p.name for p in tools_dir.glob("check-*.py")):
        r = subprocess.run([sys.executable, str(tools_dir / name), "--help"],
                           capture_output=True, text=True, timeout=60)
        if "AttributeError" in (r.stderr or "") or "ImportError" in (r.stderr or ""):
            first = next((ln for ln in r.stderr.splitlines()[::-1] if ln.strip()), "")
            broken.append(f"{name} — {first[:90]}")
    if broken:
        # ⚖️ ОДИН ГОЛОС, А НЕ ДВА. Первая редакция печатала «⛔ НЕ ЦЕЛ», а следом всё
        # равно «🎉 Группа готова» — ровно тот дефект, что контур лечил 09.08 у аварийного
        # выхода: три источника говорили разное, и читатель верил последнему.
        print(f"\n⛔ СБОРКА НЕ ПРИНЯТА: собранный контур НЕ ЦЕЛ — не работают {len(broken)}:")
        for b in broken:
            print(f"     · {b}")
        print(f"   База и инструменты лежат в {mezosync_dir} — но потребитель получил бы")
        print("   падение на первой команде. Это НЕ «готово»; чини шаблон и собери заново.")
        sys.exit(1)
    print(f"  ✅ Проба запуском: {len(probes)} главных инструментов отвечают")

    print(f"\n🎉 Группа «{args.name}» готова: {db_path}")
    print("   ⚖️ ПРОВЕРЬ ЗАПУСКОМ, А НЕ ГЛАЗАМИ:")
    print(f"     python {tools_dir / 'read-messages.py'} --role {args.roles[0].upper()}")
    # 🪤 ПОСЛЕДНЯЯ СТРОКА СБОРКИ НАЗЫВАЛА ФАЙЛ, КОТОРОГО НЕТ: «templates/coord.md» —
    # при том, что заготовка зовётся coordinator.md и лежала ТОЛЬКО в шаблоне, а не в
    # собранном контуре. Найдено 18.08 при запуске второго проекта: владелец пошёл бы
    # по указанному пути и не нашёл ничего. ⇒ заготовки кладутся В КОНТУР, а имя файла
    # в подсказке БЕРЁТСЯ ЗАМЕРОМ ПО ДИСКУ. Нет файла — так и сказано, без выдумки.
    first = args.roles[0].upper()
    wanted = "coordinator.md" if first == "COORD" else "repo-dev.md"
    landed = mezosync_dir / "templates" / wanted
    if landed.exists():
        print(f"   Следующий шаг: запустить {first} текстом заготовки {landed}")
    else:
        print(f"   ⚠️ Заготовки запуска в контуре НЕТ (ждали {landed}) — роль придётся"
              f" заводить своим текстом; это не «готово по умолчанию».")


if __name__ == "__main__":
    main()
