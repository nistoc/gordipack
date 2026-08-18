# -*- coding: utf-8 -*-
r"""ПРИЁМКА СБОРКИ КОНТУРА ИЗ ШАБЛОНА (карточка #145).

КЛАСС: шаблон проверяли ЧТЕНИЕМ ФАЙЛОВ и прогоном СВОИХ приёмок по свежей базе — то есть
не тем, что получает потребитель. Первая же честная сборка (10.08 01:07–01:22 UTC) дала
СЕМЬ красных, и все были невидимы:
```
① контур — это ОДИН mezosync.db: ни одного скрипта. Роль не может вызвать ничего
② курсоры заведены в нижнем регистре ⇒ первая команда падает «роль COORD не в реестре»
③ версия схемы пуста: sсhema_version → (None,0,0) — контур не знает себя
④ сторожа читают базу РАЗРАБОТЧИКА ШАБЛОНА: путь машины впечатан в код
⑤ звенья ищутся в каталоге, которого у потребителя нет и не будет
⑥ звено приезжает без модуля, который зовёт ⇒ падает при первом запуске
⑦ зеркала правил нет, памяти ролей нет ⇒ три красных на пустом месте у первого читателя
```
⚖️ ЧТО ЭТА ПРИЁМКА СТЕРЕЖЁТ: контур, собранный ИЗ ШАБЛОНА, обязан быть РАБОЧИМ —
не «файлы на месте», а инструменты отвечают и сторожа судят СВОЮ базу.

⛔ Живой базы не касается: собирает контур во временном каталоге.
⛔ Число случаев печатает прогон.
"""
import os
import shutil
import subprocess
import pathlib
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
# шаблон ищем по известным раскладкам — тот же приём, что у звеньев (#145)
CANDIDATES = [Path("C:/github/gordipack"), HERE.parent.parent / "gordipack",
              HERE.parent / "gordipack"]
PACK = next((p for p in CANDIDATES if (p / "scripts" / "init-group.py").exists()), None)
if PACK is None:
    print(f"⛔ ШАБЛОНА НЕТ ни в одном из мест: {[str(c) for c in CANDIDATES]}"
          " — отказ мерить, не «чисто»")
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


def main() -> int:
    ok = True
    tmp = Path(tempfile.mkdtemp(prefix="bite-fresh-"))
    try:
        mez = tmp / ".mezosync"
        r = subprocess.run([sys.executable, str(PACK / "scripts" / "init-group.py"),
                            "--name", "bite", "--path", str(mez), "--roles", "coord"],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        out = (r.stdout or "") + (r.stderr or "")

        # ① СБОРКА ВООБЩЕ ПРОХОДИТ И НЕ ГОВОРИТ ДВУМЯ ГОЛОСАМИ
        ok &= case("① сборка завершается успехом и без «готово» поверх «не цел»",
                   r.returncode == 0 and not ("⛔ СБОРКА НЕ ПРИНЯТА" in out),
                   f"код {r.returncode}; два голоса про один исход — класс, уже оплаченный"
                   " аварийным выходом 09.08", differ=True)

        # ② ИНСТРУМЕНТЫ ДОЕХАЛИ. Без них «контур» — это файл базы.
        tools = sorted((mez / "scripts").glob("*.py")) if (mez / "scripts").is_dir() else []
        ok &= case("② инструменты доехали в контур",
                   len(tools) > 20,
                   f"скриптов {len(tools)} (ждём >20); до 10.08 сборка клала ОДИН .db",
                   differ=True)

        # ③ КОНТУР ЗНАЕТ СВОЮ ВЕРСИЮ — иначе его нечем ни проверить, ни обновить
        con = sqlite3.connect(str(mez / "mezosync.db"))
        ver = con.execute("SELECT version, steps_total FROM schema_version").fetchone()
        con.close()
        ok &= case("③ контур знает свою версию (журнал не пуст)",
                   bool(ver and ver[0]),
                   f"schema_version → {ver}; пустая версия = контур не знает себя", differ=True)

        # ④ ПЕРВАЯ КОМАНДА ПЕРВОЙ РОЛИ РАБОТАЕТ. Регистр имени роли — живой дефект.
        rd = subprocess.run([sys.executable, str(mez / "scripts" / "read-messages.py"),
                             "--role", "COORD"],
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
        ok &= case("④ первая команда первой роли отвечает (регистр имени)",
                   "не в реестре" not in (rd.stdout or "") + (rd.stderr or ""),
                   "сборка заводила курсор «coord», читалка ждёт «COORD» — контур рождался"
                   " сломанным", differ=True)

        # ⑤ СТОРОЖА СУДЯТ СВОЮ БАЗУ, А НЕ БАЗУ РАЗРАБОТЧИКА ШАБЛОНА.
        #    Различающий признак: в выводе не должно быть имён НАШИХ ролей.
        g = subprocess.run([sys.executable, str(mez / "scripts" / "guard-all.py")],
                           capture_output=True, text=True, encoding="utf-8", timeout=300)
        gout = (g.stdout or "") + (g.stderr or "")
        foreign = [n for n in ("RCC", "TAXO", "OPSSRE", "STUD", "CHROME") if n in gout]
        ok &= case("⑤ сторожа судят СВОЮ базу, а не базу автора шаблона",
                   not foreign,
                   f"чужие имена в выводе: {foreign or 'нет'}; путь машины был впечатан"
                   " в код — потребитель читал бы чужие данные", differ=True)

        # ⑥ ЗВЕНЬЯ ЗАПУСКАЮТСЯ (замыкание перенесено целиком, а не наполовину)
        broke = [ln for ln in gout.splitlines() if "Traceback" in ln or "ModuleNotFound" in ln]
        ok &= case("⑥ звенья запускаются: замыкание перенесено целиком",
                   not broke,
                   f"падений {len(broke)}; звено без своего модуля выглядит доехавшим",
                   differ=True)

        # ⑦ У НОВОРОЖДЁННОГО КОНТУРА КРАСНЫХ НЕТ ВОВСЕ.
        #    ⚰️ Прежняя редакция допускала одно («источники учат снятому») — 10.08 06:33
        #    оно вылечено с двух сторон: правило шаблона поднято до v5 без «--md», а запись
        #    реестра про push объявляет себя НЕПРИМЕНИМОЙ там, где решение не принималось.
        #    Послабления в приёмке больше нет: красное новорождённого = дефект шаблона.
        reds = [ln for ln in gout.splitlines() if ln.startswith("⛔") and "КРАСНЫХ" not in ln]
        ok &= case("⑦ у новорождённого контура НЕТ красных вовсе",
                   not reds,
                   f"красные: {reds or 'нет'}; красное на пустом месте учит пролистывать"
                   " красное вообще", differ=True)

        # ⑧ НЕПРИМЕНИМОСТЬ ЧУЖОГО РЕШЕНИЯ СКАЗАНА СТРОКОЙ, А НЕ ПРОМОЛЧАНА.
        #    Реестр снятого несёт решения ВЛАДЕЛЬЦА КОНТУРА-АВТОРА (у нас push снят);
        #    у новой команды это решение не принималось, и её правило живо. Молчаливый
        #    пропуск записи был бы неотличим от «проверено и чисто» — третий исход обязан
        #    называть себя (класс, оплаченный трижды за смену).
        #    ⚠️ Мерится ПРЯМЫМ вызовом проверки, не выводом сторожа-агрегатора: тот на
        #    зелёном печатает одну итоговую строку, и ⚖️-строка в ней не живёт (замер
        #    10.08 06:34 — первая редакция случая искала её не там и краснела на исправном).
        rm = subprocess.run([sys.executable, str(mez / "scripts" / "check-retired-mechanism.py"),
                             "--db", str(mez / "mezosync.db"), "--root", str(mez / "scripts")],
                            capture_output=True, text=True, encoding="utf-8", timeout=120)
        rmout = (rm.stdout or "") + (rm.stderr or "")
        # ⑩ ПОСЛЕДНЯЯ СТРОКА СБОРКИ НАЗЫВАЕТ СУЩЕСТВУЮЩИЙ ФАЙЛ.
        #    Она говорила «запусти COORD промптом из templates/coord.md» — файла с таким
        #    именем нет (заготовка зовётся coordinator.md), и в собранный контур заготовки
        #    не клались вовсе. Владелец пошёл бы по указанному пути и не нашёл ничего.
        #    Класс: подсказка пересказывает устройство вместо того, чтобы спросить диск.
        named = [tok for line in out.splitlines() if "Следующий шаг" in line
                 for tok in line.split() if tok.endswith(".md")]
        ok &= case("⑩ подсказка сборки называет ФАЙЛ, который на диске есть",
                   bool(named) and pathlib.Path(named[-1]).exists(),
                   f"названо {named[-1] if named else None!r} — подсказка, ведущая в пустоту,"
                   f" тратит первый шаг новой команды и учит не верить подсказкам", differ=True)

        # ⑨ КОНТУР ЗНАЕТ СВОЁ ИМЯ.
        #    Сборка писала имя обновлением строки, которой в свежей базе НЕТ (схема заводит
        #    пустую таблицу meta). Обновление нуля строк проходит без ошибки — контур рождался
        #    БЕЗЫМЯННЫМ, а сборка отчитывалась об успехе. Вскрылось 18.08 только при связывании
        #    со вторым проектом: связь записалась как «atlas ↔ unknown». До того дефект жил
        #    незаметно, потому что своё имя контуру самому не нужно — оно нужно СОСЕДЯМ.
        con = sqlite3.connect(str(mez / "mezosync.db"))
        row = con.execute("SELECT value FROM meta WHERE key = 'group_name'").fetchone()
        con.close()
        ok &= case("⑨ новорождённый контур знает своё имя (его спросят соседи)",
                   bool(row) and bool(row[0]),
                   f"в базе {(row[0] if row else None)!r} · ждали имя контура — безымянный контур"
                   f" выглядит исправным, пока к нему не пришли связываться", differ=True)

        ok &= case("⑧ запись реестра про чужое решение говорит «НЕПРИМЕНИМА», а не молчит",
                   "НЕПРИМЕНИМА" in rmout,
                   "строка есть — запись судилась и назвала исход; нет строки = пропуск"
                   " неотличим от проверки", differ=True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{'✅ СБОРКА КОНТУРА ПРИНЯТА' if ok else '🔴 СБОРКА НЕ ПРИНЯТА'} — случаев {CASES},"
          f" различающих {DIFFER}; каждый случай — ЖИВОЙ дефект первой честной сборки")
    print("⚖️ ГРАНИЦА: приёмка судит СБОРКУ и стартовые правила НА МЕХАНИЗМ (не учат ли"
          " снятому — с 10.08 это её случаи ⑦⑧). СМЫСЛОВУЮ полноту правил шаблона она"
          " НЕ судит — это кураторская работа (#125), там приватность.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
