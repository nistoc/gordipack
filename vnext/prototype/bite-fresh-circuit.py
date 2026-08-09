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

        # ⑦ КРАСНЫХ У НОВОРОЖДЁННОГО КОНТУРА — НЕ БОЛЬШЕ ОДНОГО, И ОНО НАЗВАНО.
        #    ⚖️ ГРАНИЦА, НАЗВАННАЯ ВСЛУХ: единственное допустимое красное — «источники
        #    учат снятому» (перечень правил шаблона отстал от механизма, v2 против v5).
        #    Это ЧЕСТНОЕ красное шаблона о самом себе, и оно ждёт отдельной работы;
        #    молчать о нём нельзя, поэтому приёмка допускает ровно его, а не «сколько-то».
        reds = [ln for ln in gout.splitlines() if ln.startswith("⛔") and "КРАСНЫХ" not in ln]
        others = [ln for ln in reds if "учат снятому" not in ln]
        ok &= case("⑦ у новорождённого контура нет красных, кроме названного",
                   not others,
                   f"лишние красные: {others or 'нет'}; красное на пустом месте учит"
                   " пролистывать красное вообще", differ=True)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    print(f"{'✅ СБОРКА КОНТУРА ПРИНЯТА' if ok else '🔴 СБОРКА НЕ ПРИНЯТА'} — случаев {CASES},"
          f" различающих {DIFFER}; каждый случай — ЖИВОЙ дефект первой честной сборки")
    print("⚖️ ГРАНИЦА: приёмка судит СБОРКУ, а не полноту шаблона. Отставание ПРАВИЛ"
          " шаблона от живых она НЕ проверяет — это отдельная работа (приватность).")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
