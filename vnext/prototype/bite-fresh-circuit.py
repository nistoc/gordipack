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

СЛУЧАИ ⑪/⑫ (карточка #608, шаг 3, добавлены позже; ⑪б и «ВСЕ СЕМЬ» — возврат PROTO):
контур, собранный С ДОМЕНОМ (data-platform) из пакета, несущего базу правил
(rules/pack-rules.db), сразу получает опору правил пакета в meta.pack_rules_base и записывает
meta.pack_rule_sets ("universal" + взятый домен), а rules-from-pack.py --summary в нём тут же
показывает ВСЕ СЕМЬ чисел нулями — не три. Возврат PROTO: доменная сборка ловила «новых 3 ·
опоры нет 3» вместо нуля, потому что инструмент сравнивал контур со ВСЕМИ наборами пакета
(включая невзятый frontend-spa), а перекрытое доменом universal-описание читал как расхождение.
Повторный возврат PROTO (то же число дня): строка «снято» разведена по сторонам — «снято в
пакете» (removed) и «снято у вас» (retired-here — контур сам отключил правило); у
свежесобранного контура нечему быть снятым ни с одной стороны, оттого чисел семь, а не шесть.
Настоящий клон пакета сейчас без базы правил (её кладёт PROTO отдельно) — для своей проверки
случай строит ВРЕМЕННУЮ копию пакета и собирает её же строителем базу через --out (клон пакета
при этом НЕ открывается на запись ни разу). Если строитель базы сейчас не работает (его
дорабатывают) — случай печатает «неприменим: в пакете нет базы правил» и не красит остальную
приёмку. Делается ПОСЛЕДНИМ.

СЛУЧАИ ⑬/⑭ (карточка #608, повторная приёмка Н1, возврат PROTO 2026-09-14 10:08 UTC):
⑬ — init-group.py с ОТНОСИТЕЛЬНЫМ --path (процесс запущен с рабочим каталогом-РОДИТЕЛЕМ
стенда, --path — только имя подкаталога) всё равно записывает опору правил пакета и
meta.pack_rule_sets, а последней строкой идёт «🎉», а не «готово» поверх непойманного отказа.
Прежде относительный путь уезжал В rules-from-pack.py НОВОГО (ещё не собранного) контура как
есть, а тот резолвит относительный --db от СВОЕГО корня — путь удваивался, опора не находила
базу. Поломка ⑬ — копия init-group.py БЕЗ резолва --path — живёт РЯДОМ (своим именем файла)
внутри копии пакета, а не поверх него: случаю ⑪ ниже ещё нужен целый init-group.py.
⑭ — если за прогон был хоть один ⛔ (соответствующий шаг — не fatal, сборка не падает),
голосом итога идёт «⚠️ … с отказами», а не «🎉»; код выхода сборки при этом НЕ меняется.
Отказ наводится порчей КОПИИ export-rules.py (зеркало правил, шаг 7в) во ВТОРОЙ временной
копии пакета, отдельной от той, что несёт ⑪/⑫/⑬ (своя копия, чтобы порча зеркала не
красила чужие случаи). Поломка ⑭ — условие «🎉 только без ⛔» отключено в копии
init-group.py, тоже своим именем файла рядом.

СЛУЧАЙ ⑮ (карточка #608, доводка по Н1, возврат PROTO 2026-09-14 10:41 UTC): отказ
rules-from-pack.py КОДОМ на шаге опоры (7б″) раньше шёл МИМО soft_failures — печаталась
строка «⚠️ опора правил пакета: … отказал», а голосом итога всё равно ехала «🎉»; вдобавок,
пока голос итога чинили первый раз, ветка «⚠️ … с отказами» обрывала функцию сразу за собой
и роль теряла подсказки «ПРОВЕРЬ ЗАПУСКОМ»/«следующий шаг» — эта доводка проверяет ОБЕ
починки разом: голос итога честен, а подсказки печатаются при любом исходе. ТРЕТЬЯ временная
копия пакета — export-rules.py в ней цел, портится только rules-from-pack.py. Поломка ⑮ —
soft_failures.append у отказа опоры снят обратно.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_paths  # пути машины ВЫВОДЯТСЯ, не впечатаны (карточка #208)
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

import json
import os
import shutil
import subprocess
import pathlib
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# шаблон ищем по известным раскладкам — тот же приём, что у звеньев (#145)
CANDIDATES = [mezo_paths.template_root(), HERE.parent.parent / "gordipack",
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


def copy_pack_subdir(pack: pathlib.Path, name: str, dest_dir: pathlib.Path,
                     ignore_names=("__pycache__", "pack-rules.db")) -> list[str]:
    """Копия ОДНОГО подкаталога пакета (`rules`/`schema`/`scripts`/`templates`/`vnext`) из
    `pack` в `dest_dir / name` — ЕДИНЫЙ помощник для ВСЕХ мест, где приёмка копирует пакет
    (возврат COORD по приёмке карточки #633, 15.09).

    ⚡ НАХОДКА COORD. Рабочая копия пакета на диске может нести файл, которого НЕТ в git —
    владелец прямо велел его ХРАНИТЬ, не коммитить и не удалять (пример: живой
    `schema/mezosync_v6.sql`). Простой `shutil.copytree` тащит такой файл в копию приёмки,
    и копия перестаёт быть тем, что получает СОСЕД (тот берёт пакет ЧЕРЕЗ git — clone/pull,
    неотслеживаемого файла у него нет и не будет). Живой случай: `mezosync_v6.sql` уже несёт
    таблицы памяти статикой в самой схеме — поломка ⑯ (init-group не применяет шаги схемы)
    переставала краситься: таблицы приехали НЕ ОТ ШАГОВ, а от файла схемы, которого сосед
    не увидит вовсе.
    ⇒ Копия ЛЮБОГО подкаталога пакета берёт ТОЛЬКО файлы, отслеживаемые git (`git ls-files`),
    — КОГДА `pack` является рабочей копией git (есть `.git`). Git недоступен, или `pack` —
    не рабочая копия, — копируем ЦЕЛИКОМ, как раньше, и говорим об этом строкой: молчаливый
    откат к старому поведению был бы неотличим от намеренного решения.

    Возвращает список путей (relative to `pack`, вида `schema/mezosync_v6.sql`), которые НЕ
    поехали в копию из-за фильтра — пусто, если фильтр не применялся или ничего не отсеял.
    """
    src = pack / name
    if not src.is_dir():
        return []
    dest = dest_dir / name
    if not (pack / ".git").exists():
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*ignore_names))
        print(f"ℹ️ копия пакета: {pack} — не рабочая копия git (нет .git), {name}/ скопирован "
              f"ЦЕЛИКОМ, как раньше")
        return []
    r = subprocess.run(["git", "-C", str(pack), "ls-files", name],
                       capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*ignore_names))
        print(f"ℹ️ копия пакета: git ls-files отказал (код {r.returncode}) — {name}/ скопирован "
              f"ЦЕЛИКОМ, как раньше")
        return []
    tracked = {line.strip() for line in r.stdout.splitlines() if line.strip()}
    skipped: list[str] = []
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in ignore_names]
        for fname in files:
            if fname in ignore_names:
                continue
            fp = pathlib.Path(root) / fname
            rel = fp.relative_to(pack).as_posix()
            if rel in tracked:
                target = dest_dir / pathlib.Path(rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(fp, target)
            else:
                skipped.append(rel)
    for rel in skipped:
        print(f"ℹ️ копия пакета: {rel} не отслеживается git — сборка приёмки его не берёт: "
              f"сосед получает пакет из git")
    return skipped


def build_pack_copy_with_rules_db(dest: pathlib.Path) -> tuple[bool, str]:
    """Временная копия пакета (карточка #608, шаг 3) — С БАЗОЙ ПРАВИЛ, даже когда её нет
    в самом клоне (сейчас нет — её кладёт PROTO отдельным ходом; см. отчёт задачи).

    ЗАЧЕМ КОПИЯ, А НЕ ПРЯМО PACK: писать rules/pack-rules.db прямо в клон запрещено
    («rules/pack-rules.db в клоне не создавать») — сборщик пишет ТОЛЬКО в dest (--out),
    а в PACK ходит ИСКЛЮЧИТЕЛЬНО на чтение (git log/show для истории правил). rules-from-
    pack.py и init-group.py в самом PACK — ещё БЕЗ переезда шага 3 (эта поставка его
    отдельно не переносит, см. «ЧЕГО НЕ ДЕЛАТЬ» задачи) — поэтому копия получает СВЕЖИЕ
    копии обоих ОТСЮДА (mezo_paths.live_scripts()), иначе она проверяла бы вчерашнее.

    Возвращает (True, "") при успехе; (False, причина) — сборщик базы правил (в разработке
    параллельно, карточка #608) не смог собрать — это НЕ повод чинить его отсюда.
    """
    builder = PACK / "vnext" / "tools" / "build-pack-rules-db.py"
    if not builder.exists():
        return False, f"в пакете нет сборщика базы правил ({builder})"
    for name in ("rules", "schema", "scripts", "templates", "vnext"):
        copy_pack_subdir(PACK, name, dest)
    if not (dest / "scripts").is_dir():
        return False, "у пакета нет scripts/ — копировать нечего"
    live_scripts = mezo_paths.live_scripts()
    for tool_name in ("rules-from-pack.py", "init-group.py"):
        live_tool = live_scripts / tool_name
        if live_tool.exists():
            shutil.copy2(live_tool, dest / "scripts" / tool_name)
    r = subprocess.run(
        [sys.executable, str(builder), "--pack-root", str(PACK), "--out",
         str(dest / "rules" / "pack-rules.db")],
        capture_output=True, text=True, encoding="utf-8", timeout=300)
    if r.returncode != 0:
        reason = ((r.stderr or "") + (r.stdout or "")).strip().splitlines()
        return False, (reason[-1] if reason else f"код {r.returncode}, без сообщения")
    return True, ""


def main() -> int:
    ok = True
    tmp = mezo_stand.new("bite-fresh-")
    env = mezo_stand.stand_env(tmp)  # среда закреплена за стендом: MEZO_CONTAINER вызывающего сюда не доезжает (записка #5096)
    try:
        mez = tmp / ".mezosync"
        r = subprocess.run([sys.executable, str(PACK / "scripts" / "init-group.py"),
                            "--name", "bite", "--path", str(mez), "--roles", "coord"],
                           capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
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
                            capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
        ok &= case("④ первая команда первой роли отвечает (регистр имени)",
                   "не в реестре" not in (rd.stdout or "") + (rd.stderr or ""),
                   "сборка заводила отметку прочитанного «coord», читалка ждёт «COORD» — контур рождался"
                   " сломанным", differ=True)

        # ⑤ СТОРОЖА СУДЯТ СВОЮ БАЗУ, А НЕ БАЗУ РАЗРАБОТЧИКА ШАБЛОНА.
        #    Различающий признак: в выводе не должно быть имён НАШИХ ролей.
        g = subprocess.run([sys.executable, str(mez / "scripts" / "guard-all.py")],
                           capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
        gout = (g.stdout or "") + (g.stderr or "")
        foreign = [n for n in ("RCC", "TAXO", "OPSSRE", "STUD", "CHROME") if n in gout]
        ok &= case("⑤ проверки судят СВОЮ базу, а не базу автора шаблона",
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
                            capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
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

        # ═══ НОВЫЙ СЛУЧАЙ (карточка #608, шаг 3): у контура, собранного С НУЛЯ, опора
        # правил пакета есть СРАЗУ, без отдельной команды. Сборка берёт ПАКЕТ (не живой
        # контур), а у настоящего клона пакета сейчас НЕТ rules/pack-rules.db (её положит
        # PROTO отдельным ходом) — для СВОЕЙ проверки строится ВРЕМЕННАЯ копия пакета с
        # базой, собранной её строителем (build-pack-rules-db.py, --out ТОЛЬКО в копию —
        # клон пакета на запись не открывается ни разу). ДЕЛАЕТСЯ ПОСЛЕДНИМ: если строитель
        # базы (в разработке параллельно) сейчас не работает — случай говорит «неприменим:
        # в пакете нет базы правил» и НЕ красит остальную приёмку (не участвует в счёте).
        pack_copy = tmp / "pack-with-rules-db"
        pack_copy.mkdir()
        built, why = build_pack_copy_with_rules_db(pack_copy)
        if not built:
            print(f"➖ неприменим: в пакете нет базы правил ({why}) — карточка #608 шаг 3 "
                  f"этим прогоном не проверена, остальные случаи этой приёмки не задеты")
        else:
            # ⚖️ ВОЗВРАТ PROTO: сборка идёт С ДОМЕНОМ (data-platform) — именно на доменной
            # сборке нашёлся шум («новых 3 · опоры нет 3» вместо нуля), потому что инструмент
            # сравнивал контур со ВСЕМИ наборами пакета, а контур взял только часть.
            mez2 = tmp / ".mezosync-608"
            r11 = subprocess.run(
                [sys.executable, str(pack_copy / "scripts" / "init-group.py"),
                 "--name", "bite608", "--path", str(mez2), "--domain", "data-platform",
                 "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            out11 = (r11.stdout or "") + (r11.stderr or "")
            con608 = sqlite3.connect(str(mez2 / "mezosync.db")) if (mez2 / "mezosync.db").exists() \
                else None
            base_map, rule_sets_recorded = {}, None
            if con608 is not None:
                row = con608.execute(
                    "SELECT value FROM meta WHERE key='pack_rules_base'").fetchone()
                row_sets = con608.execute(
                    "SELECT value FROM meta WHERE key='pack_rule_sets'").fetchone()
                con608.close()
                base_map = json.loads(row[0]) if row and row[0] else {}
                rule_sets_recorded = json.loads(row_sets[0]) if row_sets and row_sets[0] else None
            ok &= case("⑪а у контура, собранного с нуля из пакета с базой правил, опора уже "
                      "записана в meta.pack_rules_base",
                      r11.returncode == 0 and len(base_map) > 0,
                      f"код сборки {r11.returncode}; записей опоры {len(base_map)} (ждём > 0)"
                      + ("" if r11.returncode == 0 else f"\n   {out11[-400:]}"), differ=True)
            ok &= case("⑪б контур записал meta.pack_rule_sets — universal И взятый домен",
                      rule_sets_recorded == ["universal", "data-platform"],
                      f"записано: {rule_sets_recorded} (ждём ['universal', 'data-platform'])",
                      differ=True)

            r12 = subprocess.run(
                [sys.executable, str(mez2 / "scripts" / "rules-from-pack.py"),
                 "--db", str(mez2 / "mezosync.db"), "--source", str(pack_copy), "--summary"],
                capture_output=True, text=True, encoding="utf-8", timeout=120, env=env)
            out12 = (r12.stdout or "") + (r12.stderr or "")
            # ⚖️ ВОЗВРАТ PROTO: ждём ВСЕ СЕМЬ чисел строки нулями, а не три — «новых» и
            # «опоры нет» тоже обязаны быть 0 (до правки на доменной сборке было «новых 3 ·
            # опоры нет 3»: чужой набор пакета и перекрытое universal-описание давали шум).
            # ⚖️ ПОВТОРНЫЙ ВОЗВРАТ PROTO: «снято» разведено по сторонам — «снято в пакете» и
            # «снято у вас» (retired-here: контур сам отключил правило) — оба тоже 0 у
            # свежесобранного контура, там нечему быть снятым ни с чьей стороны.
            ok &= case("⑫ rules-from-pack.py --summary в новом контуре: с пакетом, от "
                      "которого контур только что пошёл, расхождений нет — ВСЕ СЕМЬ чисел 0",
                      r12.returncode == 0 and "новых 0" in out12 and "изменено в пакете 0" in out12
                      and "уточнено у вас 0" in out12 and "с обеих сторон 0" in out12
                      and "опоры нет 0" in out12 and "снято в пакете 0" in out12
                      and "снято у вас 0" in out12,
                      f"код {r12.returncode}; строка: {out12.strip()[:220]}", differ=True)

            # ═══ НОВЫЙ СЛУЧАЙ ⑬ (карточка #608, повторная приёмка Н1, возврат PROTO
            # 2026-09-14 10:08 UTC): init-group.py с ОТНОСИТЕЛЬНЫМ --path — процесс запущен
            # с рабочим каталогом-РОДИТЕЛЕМ стенда (cwd), а --path — только имя подкаталога,
            # а не полный путь. Прежде относительный путь уезжал В rules-from-pack.py НОВОГО
            # (ещё не собранного) контура как есть, а тот резолвит относительный --db от
            # СВОЕГО корня — путь удваивался (…\m2\.mezosync\m2\.mezosync\mezosync.db), опора
            # не находила базу. Ждём: опора записана, meta.pack_rule_sets есть, последняя
            # строка — «🎉», а во всём выводе НЕТ ни одного ⛔.
            n1_parent = tmp / "n1-rel-parent"
            n1_parent.mkdir()
            n1_rel_name = ".mezosync-608-rel"
            r14 = subprocess.run(
                [sys.executable, str(pack_copy / "scripts" / "init-group.py"),
                 "--name", "bite608rel", "--path", n1_rel_name, "--domain", "data-platform",
                 "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env,
                cwd=str(n1_parent))
            out14 = (r14.stdout or "") + (r14.stderr or "")
            mez4 = n1_parent / n1_rel_name
            base_map4, rule_sets4 = {}, None
            if (mez4 / "mezosync.db").exists():
                con4 = sqlite3.connect(str(mez4 / "mezosync.db"))
                row4 = con4.execute(
                    "SELECT value FROM meta WHERE key='pack_rules_base'").fetchone()
                row4s = con4.execute(
                    "SELECT value FROM meta WHERE key='pack_rule_sets'").fetchone()
                con4.close()
                base_map4 = json.loads(row4[0]) if row4 and row4[0] else {}
                rule_sets4 = json.loads(row4s[0]) if row4s and row4s[0] else None
            ok &= case("⑬а init-group.py с ОТНОСИТЕЛЬНЫМ --path (запуск из каталога-родителя "
                      "стенда) всё равно записывает опору правил пакета и meta.pack_rule_sets",
                      r14.returncode == 0 and len(base_map4) > 0
                      and rule_sets4 == ["universal", "data-platform"],
                      f"код {r14.returncode}; опоры {len(base_map4)} (ждём > 0); "
                      f"pack_rule_sets {rule_sets4} (ждём ['universal', 'data-platform'])"
                      + ("" if r14.returncode == 0 else f"\n   {out14[-400:]}"), differ=True)
            # ⚖️ «Последняя строка» у PROTO — про ИСХОД (какой из двух взаимоисключающих
            # голосов, «🎉» или «⚠️ … с отказами», прозвучал последним про итог сборки), а
            # не про физически последний байт stdout: «🎉» сама не последняя строка вывода —
            # следом идут подсказки «⚖️ ПРОВЕРЬ ЗАПУСКОМ»/«Следующий шаг» (та же схема, что
            # проверяет случай ⑭ ниже для ветки с отказом, где после «⚠️ …» уже ничего нет,
            # потому что она заканчивается return). Здесь ⛔ нет ни одного — значит, голос
            # «🎉» обязан прозвучать, а «⚠️ … с отказами» — нет.
            ok &= case("⑬б при относительном --path и без ⛔ голос про исход — «🎉», а не "
                      "«⚠️ … с отказами» поверх непойманного отказа",
                      "⛔" not in out14 and "🎉 Группа" in out14
                      and "собрана с отказами" not in out14,
                      f"⛔ в выводе: {'⛔' in out14}; «🎉 Группа» в выводе: "
                      f"{'🎉 Группа' in out14}; «с отказами» в выводе: "
                      f"{'собрана с отказами' in out14}", differ=True)

            # ═══ НОВЫЙ СЛУЧАЙ ⑭ (карточка #608, повторная приёмка Н1, п.2 возврата PROTO):
            # если за прогон был хоть один ⛔ (сейчас единственный НЕ fatal такой источник —
            # незакончившееся зеркало правил, шаг 7в), последней строкой идёт честное «⚠️ …
            # с отказами», а не «🎉» поверх него; код выхода НЕ меняется (сборка не падает).
            # Отказ наводится порчей КОПИИ export-rules.py — во ВТОРОЙ временной копии пакета
            # (своя копия, чтобы порча зеркала не задела случаи ⑪/⑫/⑬ выше).
            pack_soft = tmp / "pack-softfail"
            shutil.copytree(pack_copy, pack_soft, ignore=shutil.ignore_patterns("__pycache__"))
            (pack_soft / "scripts" / "export-rules.py").write_text(
                "import sys\n"
                "sys.exit('⛔ ПОЛОМКА (карточка #608, повторная приёмка Н1, п.2): "
                "export-rules.py нарочно отказывает — проверяем условие «🎉»/«с отказами»')\n",
                encoding="utf-8")
            mez6 = tmp / ".mezosync-608-soft"
            r16 = subprocess.run(
                [sys.executable, str(pack_soft / "scripts" / "init-group.py"),
                 "--name", "bite608soft", "--path", str(mez6), "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            out16 = (r16.stdout or "") + (r16.stderr or "")
            # ВОЗВРАТ PROTO (карточка #608, доводка по Н1, 10:41 UTC): голос итога — «⚠️ …
            # с отказами» вместо «🎉» — но подсказки после него («ПРОВЕРЬ ЗАПУСКОМ» и
            # далее) печатаются в ОБОИХ исходах, поэтому «⚠️ …» — не физически последняя
            # строка вывода; меняется только ПЕРВАЯ строка итога.
            ok &= case("⑭ отказ шага (зеркало правил) не меняет код сборки; голос итога — "
                      "«⚠️ … с отказами», а не «🎉», но подсказки «ПРОВЕРЬ ЗАПУСКОМ» всё равно "
                      "в выводе",
                      r16.returncode == 0 and "⛔ Зеркало правил" in out16
                      and "🎉" not in out16 and "собрана с отказами" in out16
                      and "ПРОВЕРЬ ЗАПУСКОМ" in out16,
                      f"код {r16.returncode} (ждём 0 — отказ не fatal); «с отказами» в выводе: "
                      f"{'собрана с отказами' in out16}; подсказка в выводе: "
                      f"{'ПРОВЕРЬ ЗАПУСКОМ' in out16}", differ=True)

            # ── КОНТРОЛЬ ⑬ нарочной поломкой: копия init-group.py БЕЗ .resolve() у --path —
            # тот самый прежний код, что и дал баг Н1. Живёт РЯДОМ своим именем файла внутри
            # pack_copy/scripts/ (не поверх init-group.py — он ещё целиком нужен случаю ⑪
            # ниже), чтобы SCRIPT_DIR/REPO_ROOT остались верны и падение было по СВОЕЙ причине
            # (удвоенный путь), а не по «не нашёл соседний schema/».
            n1_src = (pack_copy / "scripts" / "init-group.py").read_text(encoding="utf-8")
            n1_anchor = "Path(args.path).resolve()"
            if n1_src.count(n1_anchor) != 1:
                sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка резолва --path не найдена дословно в "
                         "init-group.py — испытуемое изменилось, поломка ⑬ бьёт мимо")
            n1_poisoned = pack_copy / "scripts" / "init-group-no-resolve.py"
            n1_poisoned.write_text(n1_src.replace(n1_anchor, "Path(args.path)"),
                                   encoding="utf-8")
            n1_parent2 = tmp / "n1-rel-parent-poison"
            n1_parent2.mkdir()
            n1_rel_name2 = ".mezosync-608-rel-poison"
            r15 = subprocess.run(
                [sys.executable, str(n1_poisoned), "--name", "bite608relpoison", "--path",
                 n1_rel_name2, "--domain", "data-platform", "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env,
                cwd=str(n1_parent2))
            mez5 = n1_parent2 / n1_rel_name2
            base_map5 = {}
            if (mez5 / "mezosync.db").exists():
                con5 = sqlite3.connect(str(mez5 / "mezosync.db"))
                row5 = con5.execute(
                    "SELECT value FROM meta WHERE key='pack_rules_base'").fetchone()
                con5.close()
                base_map5 = json.loads(row5[0]) if row5 and row5[0] else {}
            ok &= case("⑬ ПОЛОМКА (init-group.py без .resolve() у --path) КРАСИТ случай ⑬ — "
                      "опора не записана при относительном --path",
                      len(base_map5) == 0,
                      f"записей опоры {len(base_map5)} (ждём 0 — воспроизведён баг Н1)",
                      differ=True)

            # ── КОНТРОЛЬ ⑭ нарочной поломкой: условие «🎉 только без ⛔» отключено обратно
            # (условие всегда ложно) — «🎉» обязана появиться ДАЖЕ поверх непустого
            # soft_failures. Копия init-group.py живёт своим именем файла РЯДОМ внутри
            # pack_soft/scripts/ (export-rules.py в этой копии уже испорчен выше).
            gate_src = (pack_soft / "scripts" / "init-group.py").read_text(encoding="utf-8")
            gate_anchor = "if soft_failures:"
            if gate_src.count(gate_anchor) != 1:
                sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка условия «if soft_failures:» не найдена "
                         "дословно в init-group.py — испытуемое изменилось, поломка ⑭ бьёт мимо")
            gate_poisoned = pack_soft / "scripts" / "init-group-no-gate.py"
            gate_poisoned.write_text(gate_src.replace(gate_anchor, "if False:"),
                                     encoding="utf-8")
            mez7 = tmp / ".mezosync-608-soft-poison"
            r17 = subprocess.run(
                [sys.executable, str(gate_poisoned), "--name", "bite608softpoison", "--path",
                 str(mez7), "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            out17 = (r17.stdout or "") + (r17.stderr or "")
            ok &= case("⑭ ПОЛОМКА (условие «🎉 только без ⛔» отключено) КРАСИТ случай ⑭ — "
                      "«🎉» снова едет поверх непойманного отказа",
                      "🎉" in out17,
                      f"«🎉» в выводе поломанной версии: {'🎉' in out17} (ждём True — "
                      f"поломка обязана вернуть старый дефект)", differ=True)

            # ═══ НОВЫЙ СЛУЧАЙ ⑮ (карточка #608, доводка по Н1, возврат PROTO 10:41 UTC):
            # rules-from-pack.py НОВОГО контура отказывает КОДОМ на шаге 7б″ (опора правил
            # пакета) — раньше это шло МИМО soft_failures: печаталось «⚠️ опора правил
            # пакета: rules-from-pack.py отказал», а итог всё равно «🎉». Контур без опоры
            # на КАЖДОМ следующем обновлении напишет «опоры нет» по всем правилам — это
            # отказ шага. Своя ТРЕТЬЯ временная копия пакета (export-rules.py в ней цел —
            # порча другого инструмента не должна путать причины).
            pack_rfpfail = tmp / "pack-rfpfail"
            shutil.copytree(pack_copy, pack_rfpfail, ignore=shutil.ignore_patterns("__pycache__"))
            (pack_rfpfail / "scripts" / "rules-from-pack.py").write_text(
                "import sys\n"
                "sys.exit('⛔ ПОЛОМКА (карточка #608, доводка по Н1): rules-from-pack.py "
                "нарочно отказывает кодом — проверяем, что это тоже отказ шага')\n",
                encoding="utf-8")
            mez8 = tmp / ".mezosync-608-rfpfail"
            r18 = subprocess.run(
                [sys.executable, str(pack_rfpfail / "scripts" / "init-group.py"),
                 "--name", "bite608rfpfail", "--path", str(mez8), "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            out18 = (r18.stdout or "") + (r18.stderr or "")
            ok &= case("⑮ rules-from-pack.py нового контура отказывает КОДОМ (шаг опоры) → "
                      "голос итога — «⚠️ … с отказами», подсказка «ПРОВЕРЬ ЗАПУСКОМ» в "
                      "выводе всё равно есть",
                      r18.returncode == 0 and "🎉" not in out18
                      and "собрана с отказами" in out18
                      and "опора правил пакета не записана" in out18
                      and "ПРОВЕРЬ ЗАПУСКОМ" in out18,
                      f"код {r18.returncode} (ждём 0); «с отказами» в выводе: "
                      f"{'собрана с отказами' in out18}; подсказка в выводе: "
                      f"{'ПРОВЕРЬ ЗАПУСКОМ' in out18}", differ=True)

            # ── КОНТРОЛЬ ⑮ нарочной поломкой: soft_failures.append у отказа опоры снят —
            # «🎉» снова едет поверх отказавшего шага (тот самый прежний дефект доводки).
            # Строка-цель — из ДВУХ физических строк (f-string перенесён): ищем ПЕРВУЮ по
            # уникальной подстроке, ВТОРУЮ — как ближайшую ниже, несущую закрывающую скобку
            # вызова append(...), и убираем обе разом одним pass — тот же приём, что у ㊼.
            na_lines = (pack_rfpfail / "scripts" / "init-group.py").read_text(
                encoding="utf-8").splitlines(keepends=True)
            na_idx = [i for i, ln in enumerate(na_lines)
                     if "опора правил пакета не записана — rules-from-pack.py" in ln]
            if len(na_idx) != 1:
                sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка soft_failures.append (опора) не найдена "
                         "дословно в init-group.py — испытуемое изменилось, поломка ⑮ бьёт мимо")
            na_i = na_idx[0]
            na_j = na_i
            while ")" not in na_lines[na_j]:
                na_j += 1
            na_indent = na_lines[na_i][:len(na_lines[na_i]) - len(na_lines[na_i].lstrip())]
            na_lines = (na_lines[:na_i]
                       + [na_indent + "pass  # ПОЛОМКА: soft_failures.append(опора) снят\n"]
                       + na_lines[na_j + 1:])
            no_append_path = pack_rfpfail / "scripts" / "init-group-no-append.py"
            no_append_path.write_text("".join(na_lines), encoding="utf-8")
            mez9 = tmp / ".mezosync-608-rfpfail-poison"
            r19 = subprocess.run(
                [sys.executable, str(no_append_path), "--name", "bite608rfpfailpoison",
                 "--path", str(mez9), "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            out19 = (r19.stdout or "") + (r19.stderr or "")
            ok &= case("⑮ ПОЛОМКА (append у отказа опоры снят) КРАСИТ ровно ⑮ — «🎉» снова "
                      "едет поверх отказавшего шага",
                      "🎉 Группа" in out19,
                      f"«🎉 Группа» в выводе поломанной версии: {'🎉 Группа' in out19} (ждём "
                      f"True — поломка обязана вернуть старый дефект)", differ=True)

            # ── КОНТРОЛЬ нарочной поломкой (требование задания, п2): init-group.py КОПИИ
            # пакета перестаёт звать --record-base (зовёт --summary вместо него — тоже
            # настоящую команду, чтобы отказ инструмента не спутался с отказом поломки).
            # Случай ⑪ обязан провалиться ИМЕННО по этой причине: опоры не будет, а не
            # сборка упадёт. Патч — в КОПИИ init-group.py внутри уже готовой pack_copy;
            # ни .mezosync/scripts/init-group.py, ни клон пакета не трогаются.
            poisoned_init = pack_copy / "scripts" / "init-group.py"
            poison_src = poisoned_init.read_text(encoding="utf-8")
            poison_anchor = '             "--record-base", "--apply", "--actor", "init-group.py"],\n'
            if poison_src.count(poison_anchor) != 1:
                sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка вызова --record-base не найдена дословно "
                         "в init-group.py — испытуемое изменилось, поломка бьёт мимо")
            poisoned_init.write_text(poison_src.replace(poison_anchor, '             "--summary"],\n'),
                                     encoding="utf-8")

            mez3 = tmp / ".mezosync-608-poison"
            r13 = subprocess.run(
                [sys.executable, str(poisoned_init), "--name", "bite608poison", "--path",
                 str(mez3), "--roles", "coord"],
                capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
            base_map3 = {}
            if (mez3 / "mezosync.db").exists():
                con608p = sqlite3.connect(str(mez3 / "mezosync.db"))
                row3 = con608p.execute(
                    "SELECT value FROM meta WHERE key='pack_rules_base'").fetchone()
                con608p.close()
                base_map3 = json.loads(row3[0]) if row3 and row3[0] else {}
            ok &= case("⑪ ПОЛОМКА (init-group больше не зовёт --record-base) КРАСИТ ровно "
                      "случай ⑪ — своей причиной (опоры нет, а не сборка упала)",
                      r13.returncode == 0 and len(base_map3) == 0,
                      f"код сборки {r13.returncode} (ждём 0 — сборка не обязана упасть); "
                      f"записей опоры {len(base_map3)} (ждём 0)", differ=True)

        # ═══ НОВЫЕ СЛУЧАИ ⑯–⑲ (карточка #633 — накат шагов схемы при сборке; карточка #640 —
        # различитель контура у отметок пересоздания и их перенос соседям). Своя ЛЁГКАЯ копия
        # пакета (без базы правил — она не нужна этим случаям, а строить её тут — цена без
        # пользы), чтобы поломки ниже не задели ⑪..⑮ выше (те уже держат СВОИ копии).
        pack_633 = tmp / "pack-633"
        for name in ("rules", "schema", "scripts", "templates", "vnext"):
            copy_pack_subdir(PACK, name, pack_633)

        # ── ⑯ свежий контур (уже построен ВЫШЕ как `mez`): версия схемы v6, таблицы памяти
        # (архив · записи · индекс поиска · история версий памяти · чужие отметки) на месте;
        # find-phoenix.py отвечает БЕЗ отказа «накати шаг» (карточка #633: до правки init-group
        # не накатывал ни одного шага схемы — контур рождался без этих таблиц вовсе).
        con16 = sqlite3.connect(str(mez / "mezosync.db"))
        ver16 = con16.execute("SELECT version FROM schema_version").fetchone()
        tabs16 = {row[0] for row in con16.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        con16.close()
        want_tables_633 = {"phoenix_archive", "phoenix_records", "phoenix_records_fts",
                           "phoenix_history_archive", "role_rebirths_foreign"}
        fp16 = subprocess.run(
            [sys.executable, str(mez / "scripts" / "find-phoenix.py"),
             "--role", "COORD", "--actor", "COORD", "проверка карточки 633"],
            capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        fpout16 = (fp16.stdout or "") + (fp16.stderr or "")
        ok &= case("⑯ свежий контур: версия схемы v6, таблицы памяти на месте, find-phoenix.py "
                  "отвечает БЕЗ отказа «накати шаг» (карточка #633)",
                  bool(ver16) and ver16[0] == "v6" and want_tables_633 <= tabs16
                  and "накати шаг" not in fpout16 and fp16.returncode in (0, 2),
                  f"версия {ver16}; таблиц не хватает {sorted(want_tables_633 - tabs16)}; "
                  f"find-phoenix код {fp16.returncode}, последняя строка: "
                  f"{fpout16.strip().splitlines()[-1] if fpout16.strip() else ''}", differ=True)

        # ── КОНТРОЛЬ ⑯ нарочной поломкой: init-group.py перестаёт применять список шагов
        # схемы (строка «considered = […]» обнулена) — старый дефект карточки #633
        # (контур без таблиц памяти) обязан вернуться. Поломка — КОПИЯ init-group.py рядом
        # со своим именем файла внутри pack_633/scripts/ (сам pack_633 остаётся исправен —
        # он ещё нужен случаям ⑰/⑱ ниже).
        ig_src = (pack_633 / "scripts" / "init-group.py").read_text(encoding="utf-8")
        ig_anchor = "    considered = [s for s in schema_step_order.STEPS if s in on_disk]\n"
        if ig_src.count(ig_anchor) != 1:
            sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка «considered = […]» не найдена дословно в "
                     "init-group.py — испытуемое изменилось, поломка ⑯ бьёт мимо")
        ig_poisoned = pack_633 / "scripts" / "init-group-no-schema-steps.py"
        ig_poisoned.write_text(
            ig_src.replace(ig_anchor, "    considered = []  # ПОЛОМКА: список шагов не применяется\n"),
            encoding="utf-8")
        mez16p = tmp / ".mezosync-633-poison"
        r16p = subprocess.run(
            [sys.executable, str(ig_poisoned), "--name", "bite633poison", "--path", str(mez16p),
             "--roles", "coord"],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
        tabs16p = set()
        if (mez16p / "mezosync.db").exists():
            con16p = sqlite3.connect(str(mez16p / "mezosync.db"))
            tabs16p = {row[0] for row in con16p.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            con16p.close()
        ok &= case("⑯ ПОЛОМКА (init-group не применяет шаги схемы) КРАСИТ случай ⑯ — таблиц "
                  "памяти снова нет",
                  r16p.returncode == 0 and not (want_tables_633 & tabs16p),
                  f"код сборки {r16p.returncode} (ждём 0 — сборка не обязана упасть); таблицы "
                  f"памяти, ошибочно найденные: {sorted(want_tables_633 & tabs16p)} (ждём "
                  f"пусто — старый дефект #633 обязан вернуться)", differ=True)

        # ── ⑰ свежий контур: отметок Atlas в role_rebirths 0 (карточка #640 — засев только
        # в САМ контур Atlas по meta.group_name, а не в любую базу подряд).
        con17 = sqlite3.connect(str(mez / "mezosync.db"))
        n17 = con17.execute("SELECT count(*) FROM role_rebirths").fetchone()[0]
        con17.close()
        ok &= case("⑰ свежий контур из пакета: отметок пересоздания контура Atlas в "
                  "role_rebirths 0 (карточка #640)",
                  n17 == 0, f"role_rebirths {n17} (ждём 0 — контур не Atlas)", differ=True)

        # ── КОНТРОЛЬ ⑰ нарочной поломкой: различитель контура (`if is_atlas else ()`) снят
        # в КОПИИ шага 20260905 — 18 отметок Atlas обязаны вернуться. Шаг гоним НАПРЯМУЮ на
        # СВОЕЙ синтетической копии базы (как случай ⑲ для шага 20260915), А НЕ через полную
        # сборку контура: полная сборка следом накатывает и шаг 20260915 (карточка #640 ②),
        # а он САМ убирает всё под тем же автором/источником в role_rebirths_foreign —
        # находка этого прогона (не баг: два шага честно делают каждый своё, но ВМЕСТЕ они
        # маскируют поломку ИМЕННО этого шага в role_rebirths). Различитель этого шага
        # проверяем в изоляции, тем же приёмом, что уже показал случай ⑲.
        pack_640 = tmp / "pack-640"
        for name in ("rules", "schema", "scripts", "templates", "vnext"):
            copy_pack_subdir(PACK, name, pack_640)
        step_640_path = pack_640 / "scripts" / "migrations" / "20260905-phoenix-history-archive.py"
        step_640_src = step_640_path.read_text(encoding="utf-8")
        step_640_anchor = "    marks_to_seed = ATLAS_REBIRTH_MARKS if is_atlas else ()\n"
        if step_640_src.count(step_640_anchor) != 1:
            sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка различителя контура не найдена дословно в "
                     "20260905-phoenix-history-archive.py — испытуемое изменилось, поломка "
                     "⑰ бьёт мимо")
        step_640_poisoned = pack_640 / "scripts" / "migrations" / "20260905-phoenix-history-archive-no-guard.py"
        step_640_poisoned.write_text(
            step_640_src.replace(step_640_anchor, "    marks_to_seed = ATLAS_REBIRTH_MARKS  # ПОЛОМКА: различитель снят\n"),
            encoding="utf-8")
        db17p = tmp / "atlas-guard-17-poison.db"
        con17p = sqlite3.connect(str(db17p))
        con17p.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con17p.execute("INSERT INTO meta(key,value) VALUES ('group_name','bite617poison')")
        con17p.execute("""CREATE TABLE phoenix_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, section TEXT, body TEXT,
            body_chars INTEGER, saved_at TEXT, actor TEXT, reason TEXT, prev_chars INTEGER)""")
        con17p.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT, note TEXT)")
        con17p.commit(); con17p.close()
        r17p = subprocess.run([sys.executable, str(step_640_poisoned), "--db", str(db17p)],
                              capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        con17p = sqlite3.connect(str(db17p))
        n17p = con17p.execute("SELECT count(*) FROM role_rebirths").fetchone()[0]
        con17p.close()
        ok &= case("⑰ ПОЛОМКА (различитель контура снят в копии шага 20260905) КРАСИТ случай "
                  "⑰ — контур чужого имени получает все 18 отметок Atlas",
                  r17p.returncode == 0 and n17p == 18,
                  f"код {r17p.returncode} (ждём 0); role_rebirths {n17p} (ждём 18 — старый "
                  f"дефект #640 обязан вернуться)", differ=True)

        # ── ⑱ список порядка (schema_step_order.STEPS) покрывает все файлы migrations/ новее
        # базовой отметки и наоборот (карточка #633) — проверено уже КОСВЕННО случаем ⑯
        # (сборка `mez` наверху отчиталась «🎉» безо всякого ⚠️ о расхождении списка и диска);
        # здесь — ПРЯМАЯ поломка: один шаг убран из СПИСКА (файл на диске остаётся), и сборка
        # обязана и предупредить об этом громко, и не применить убранный шаг.
        # ⚖️ Убираем шаг ПОСЛЕ вехи v6 (20260913-role-rights-revoked-by), не один из шагов
        # ПОД вехой: убрать шаг из окна вехи 20260907-milestone-v6 попутно уронило бы саму
        # веху (её собственная сверка «набор шагов под отметкой» — не то, что тут проверяем)
        # и смешало бы две разные причины отказа в одном случае.
        order_path = pack_633 / "scripts" / "schema_step_order.py"
        order_src = order_path.read_text(encoding="utf-8")
        order_anchor = '    "20260913-role-rights-revoked-by",\n'
        if order_src.count(order_anchor) != 1:
            sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: строка «20260913-role-rights-revoked-by» не найдена "
                     "дословно в schema_step_order.py — испытуемое изменилось, поломка ⑱ бьёт мимо")
        order_path.write_text(order_src.replace(order_anchor, "", 1), encoding="utf-8")
        mez18p = tmp / ".mezosync-633-order-poison"
        r18p = subprocess.run(
            [sys.executable, str(pack_633 / "scripts" / "init-group.py"),
             "--name", "bite633orderpoison", "--path", str(mez18p), "--roles", "coord"],
            capture_output=True, text=True, encoding="utf-8", timeout=300, env=env)
        out18p = (r18p.stdout or "") + (r18p.stderr or "")
        applied18p = False
        if (mez18p / "mezosync.db").exists():
            con18p = sqlite3.connect(str(mez18p / "mezosync.db"))
            applied18p = bool(con18p.execute(
                "SELECT 1 FROM schema_migrations WHERE version='20260913-role-rights-revoked-by'"
            ).fetchone())
            con18p.close()
        ok &= case("⑱ ПОЛОМКА (шаг убран из schema_step_order.STEPS, файл на диске остался) "
                  "КРАСИТ случай ⑱ — громкое предупреждение с именем шага, сборка «с отказами», "
                  "убранный шаг НЕ применён",
                  r18p.returncode == 0 and "20260913-role-rights-revoked-by" in out18p
                  and "НЕТ в schema_step_order.STEPS" in out18p
                  and "собрана с отказами" in out18p and not applied18p,
                  f"код сборки {r18p.returncode} (ждём 0 — отказ не fatal); имя шага в выводе: "
                  f"{'20260913-role-rights-revoked-by' in out18p}; предупреждение в выводе: "
                  f"{'НЕТ в schema_step_order.STEPS' in out18p}; голос «с отказами»: "
                  f"{'собрана с отказами' in out18p}; шаг всё же применился вопреки поломке: "
                  f"{applied18p} (ждём False)", differ=True)

        # ── ⑲ шаг 20260915-foreign-rebirth-marks.py на КОПИИ базы с засеянными чужими
        # отметками (карточка #640 ②): 18 строк с автором tool:20260905-phoenix-history-
        # archive, ОДНА из них под переведённым именем вида COORD-A (случай AIA), плюс одна
        # СВОЯ отметка контура (source='rebirth-mark') — переносит РОВНО чужие 18, своя
        # остаётся, role_rebirths_foreign = 18.
        db19 = tmp / "foreign-marks-19.db"
        con19 = sqlite3.connect(str(db19))
        con19.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con19.execute("INSERT INTO meta(key,value) VALUES ('group_name','bite619')")
        con19.execute("""CREATE TABLE phoenix_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, section TEXT, body TEXT,
            body_chars INTEGER, saved_at TEXT, actor TEXT, reason TEXT, prev_chars INTEGER)""")
        con19.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT, note TEXT)")
        con19.commit(); con19.close()
        step_905 = PACK / "scripts" / "migrations" / "20260905-phoenix-history-archive.py"
        step_915 = PACK / "scripts" / "migrations" / "20260915-foreign-rebirth-marks.py"
        subprocess.run([sys.executable, str(step_905), "--db", str(db19)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        con19 = sqlite3.connect(str(db19))
        foreign_roles_19 = [("CHROME", "2026-08-29 09:39:08"), ("CHROME", "2026-08-29 09:59:21"),
                            ("CHROME", "2026-08-30 21:59:37"), ("COORD-A", "2026-08-30 21:56:08"),
                            ("COORD-A", "2026-08-30 21:58:38"), ("CORE", "2026-08-29 10:43:06"),
                            ("CORE", "2026-08-30 21:59:08"), ("ING", "2026-08-30 22:04:47"),
                            ("OPSSRE", "2026-08-29 09:30:41"), ("OPSSRE", "2026-08-30 22:05:32"),
                            ("PROTO", "2026-08-30 09:54:19"), ("PROTO", "2026-08-30 22:33:19"),
                            ("RCC", "2026-08-30 22:01:49"), ("STUD", "2026-08-29 09:31:50"),
                            ("STUD", "2026-08-30 22:41:00"), ("TAXO", "2026-08-29 09:38:19"),
                            ("TAXO", "2026-08-29 09:50:34"), ("TAXO", "2026-08-30 22:03:26")]
        for role19, at19 in foreign_roles_19:
            con19.execute("INSERT INTO role_rebirths(role, at, source, noted_by) VALUES (?,?,?,?)",
                          (role19, at19, "transcript:seed19", "tool:20260905-phoenix-history-archive"))
        con19.execute("INSERT INTO role_rebirths(role, at, source, noted_by) VALUES (?,?,?,?)",
                      ("BITE619ROLE", "2026-09-10 08:00:00", "rebirth-mark", "BITE619ROLE"))
        con19.commit(); con19.close()
        r19 = subprocess.run([sys.executable, str(step_915), "--db", str(db19)],
                             capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        con19 = sqlite3.connect(str(db19))
        n_foreign19 = con19.execute("SELECT count(*) FROM role_rebirths_foreign").fetchone()[0]
        own_left19 = con19.execute(
            "SELECT count(*) FROM role_rebirths WHERE source='rebirth-mark'").fetchone()[0]
        coord_a_moved19 = con19.execute(
            "SELECT count(*) FROM role_rebirths_foreign WHERE role='COORD-A'").fetchone()[0]
        con19.close()
        ok &= case("⑲ шаг 20260915 на копии базы с чужими отметками: переносит ровно 18 "
                  "(включая переведённое имя COORD-A), своя отметка остаётся",
                  r19.returncode == 0 and n_foreign19 == 18 and own_left19 == 1
                  and coord_a_moved19 == 2,
                  f"код {r19.returncode}; role_rebirths_foreign {n_foreign19} (ждём 18); "
                  f"своя отметка осталась: {own_left19} (ждём 1); COORD-A перенесено "
                  f"{coord_a_moved19} (ждём 2)", differ=True)

        # ── КОНТРОЛЬ ⑲ нарочной поломкой: различитель заменён С «автор + источник» НА «имя
        # роли из перечня ролей Atlas» — переведённая строка (COORD-A) под таким различителем
        # не считается чужой (её имени нет в перечне ролей Atlas) и остаётся на месте: вместо
        # 18 перенесётся только 16.
        db19p = tmp / "foreign-marks-19-poison.db"
        con19p = sqlite3.connect(str(db19p))
        con19p.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con19p.execute("INSERT INTO meta(key,value) VALUES ('group_name','bite619poison')")
        con19p.execute("""CREATE TABLE phoenix_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, section TEXT, body TEXT,
            body_chars INTEGER, saved_at TEXT, actor TEXT, reason TEXT, prev_chars INTEGER)""")
        con19p.execute("CREATE TABLE schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT, note TEXT)")
        con19p.commit(); con19p.close()
        subprocess.run([sys.executable, str(step_905), "--db", str(db19p)],
                       capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        con19p = sqlite3.connect(str(db19p))
        for role19, at19 in foreign_roles_19:
            con19p.execute("INSERT INTO role_rebirths(role, at, source, noted_by) VALUES (?,?,?,?)",
                           (role19, at19, "transcript:seed19", "tool:20260905-phoenix-history-archive"))
        con19p.execute("INSERT INTO role_rebirths(role, at, source, noted_by) VALUES (?,?,?,?)",
                       ("BITE619ROLE", "2026-09-10 08:00:00", "rebirth-mark", "BITE619ROLE"))
        con19p.commit(); con19p.close()
        step_915_src = step_915.read_text(encoding="utf-8")
        step_915_anchor = (
            '    candidates = conn.execute(\n'
            '        "SELECT id, role, at, source, noted_by, noted_at FROM role_rebirths "\n'
            '        "WHERE noted_by = ? AND source LIKE ? ORDER BY role, at",\n'
            '        (FOREIGN_NOTED_BY, FOREIGN_SOURCE_LIKE)).fetchall()\n'
        )
        if step_915_src.count(step_915_anchor) != 1:
            sys.exit("⛔ НЕ ЗАПУСТИЛАСЬ: блок запроса candidates не найден дословно в "
                     "20260915-foreign-rebirth-marks.py — испытуемое изменилось, поломка ⑲ "
                     "бьёт мимо")
        atlas_role_names = ("CHROME", "COORD", "CORE", "ING", "OPSSRE", "PROTO", "RCC", "STUD", "TAXO")
        poisoned_query = (
            '    candidates = conn.execute(\n'
            '        "SELECT id, role, at, source, noted_by, noted_at FROM role_rebirths "\n'
            '        "WHERE role IN (' + ",".join(f"\'{r}\'" for r in atlas_role_names) + ') '
            'ORDER BY role, at").fetchall()  # ПОЛОМКА: различитель по имени роли\n'
        )
        step_915_poisoned = pack_633 / "scripts" / "migrations" / "20260915-foreign-rebirth-marks-by-role-name.py"
        step_915_poisoned.write_text(step_915_src.replace(step_915_anchor, poisoned_query, 1),
                                     encoding="utf-8")
        r19p = subprocess.run([sys.executable, str(step_915_poisoned), "--db", str(db19p)],
                              capture_output=True, text=True, encoding="utf-8", timeout=60, env=env)
        con19p = sqlite3.connect(str(db19p))
        n_foreign19p = con19p.execute("SELECT count(*) FROM role_rebirths_foreign").fetchone()[0]
        coord_a_moved19p = con19p.execute(
            "SELECT count(*) FROM role_rebirths_foreign WHERE role='COORD-A'").fetchone()[0]
        con19p.close()
        ok &= case("⑲ ПОЛОМКА (различитель по имени роли вместо автора/источника) КРАСИТ "
                  "случай ⑲ — переведённая строка COORD-A остаётся, перенесено 16, не 18",
                  r19p.returncode == 0 and n_foreign19p == 16 and coord_a_moved19p == 0,
                  f"код {r19p.returncode}; role_rebirths_foreign {n_foreign19p} (ждём 16 — "
                  f"COORD-A под этим различителем не считается чужой); COORD-A перенесено "
                  f"{coord_a_moved19p} (ждём 0)", differ=True)

    finally:
        mezo_stand.release(tmp)  # уборка отложена до исхода прогона

    print()
    print(f"{'✅ СБОРКА КОНТУРА ПРИНЯТА' if ok else '🔴 СБОРКА НЕ ПРИНЯТА'} — случаев {CASES},"
          f" различающих {DIFFER}; каждый случай — ЖИВОЙ дефект первой честной сборки")
    print("⚖️ ГРАНИЦА: приёмка судит СБОРКУ и стартовые правила НА МЕХАНИЗМ (не учат ли"
          " снятому — с 10.08 это её случаи ⑦⑧). СМЫСЛОВУЮ полноту правил шаблона она"
          " НЕ судит — это кураторская работа (#125), там приватность.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
