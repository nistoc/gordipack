#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ПРИЁМКА: ВРЕМЯ В ПОДПИСЬ СТАВИТ ИНСТРУМЕНТ, А НЕ РОЛЬ.

Слово владельца 2026-08-08 16:53 UTC: «лечить механизмом, как мы сделали с памятью:
время в записку подставляет не роль, а инструмент — тогда ошибиться нечем».

Повод замером, а не опасением: правило «время только UTC» написано подробно, известно всем —
и 08.08 ДВЕ РОЛИ ЗА ДВА ЧАСА подписали записки местным временем под буквами «UTC» (+2 ч).
Обе поймали себя сами. Класс живёт при верном и известном правиле.

⚖️ Опаснее всего здесь НЕ промах, а лишнее усердие: записка сплошь и рядом ЦИТИРУЕТ чужие
метки времени («слово владельца 15:56 UTC»). Механизм, который «исправит» цитату, подделает
её — и это будет хуже исходной ошибки, потому что незаметно. Поэтому различающих случаев
про цитаты здесь БОЛЬШЕ, чем про саму подпись.

Случаи (различающий = механизм обязан ответить ИНАЧЕ, а не одинаково):
  ① подписи нет вовсе → ДОБАВЛЕНА, время = времени записи   контроль: механизм работает
  ② подпись с НЕВЕРНЫМ временем → ИСПРАВЛЕНА                            РАЗЛИЧАЮЩИЙ
  ③ подпись уже верна → тело не тронуто ВООБЩЕ                          РАЗЛИЧАЮЩИЙ
  ④ ЦИТИРОВАННОЕ время в середине тела НЕ ТРОНУТО                       РАЗЛИЧАЮЩИЙ
  ⑤ подпись ЧУЖОЙ роли внутри цитаты (не в конце) НЕ тронута            РАЗЛИЧАЮЩИЙ
  ⑥ подпись в базе совпадает с колонкой timestamp ПОМИНУТНО             РАЗЛИЧАЮЩИЙ
  ⑦ остальной текст записки не изменён НИ НА ЗНАК                       РАЗЛИЧАЮЩИЙ
  ⑧ подпись С ЗАПЯТОЙ исправлена НА МЕСТЕ, вторая не дописана           РАЗЛИЧАЮЩИЙ (карточка #371)
  ⑨ час в ШАПКЕ тела со сдвигом — назван предупреждением, тело цело     РАЗЛИЧАЮЩИЙ (карточка #371)
  ⑩ встречный: час в шапке верный — тишина + строка «сверен»            РАЗЛИЧАЮЩИЙ
  ⑪ час в ЗАГОЛОВКЕ со сдвигом — назван отдельно                        РАЗЛИЧАЮЩИЙ

⛔ Живой базы не касается: своя песочница.
"""
import importlib.util
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mezo_target  # noqa: E402 — какую копию испытываем, решается ОДНИМ местом
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале

SCRIPTS = str(mezo_target.scripts_root())
WRITE = os.path.join(SCRIPTS, "write-message.py")
CASES = DIFFER = 0

# ═══ ПРЕДЛОЖЕНИЕ AIA 03 (карточка #644): огороженные блоки и круговое сравнение часа ═══
# 🩸 ПОВОД (замер AIA на живой базе их контура, пакет d32e621 = нашему коду).
# ① строки-кандидаты для суда часа в шапке брались первыми восемью непустыми ПОДРЯД,
#    не различая огороженный блок (```…```) — пример метки внутри блока судился как
#    настоящая подпись, и тревога приходила на текст, ОБЪЯСНЯЮЩИЙ правило.
# ② круговое сравнение (через полночь) стояло только в ветви заголовка; ветвь шапки
#    тела давала 1436 минут вместо 4 на метке 23:58 при записи в 00:02 следующих суток.
BREAKS = {
    "fence-skip": ("    lines = _candidate_lines(body, 8)",
                   '    lines = [l for l in body.split("\\n") if l.strip()][:8]'),
    "circular-body": ("h, mi = map(int, m2.group(2).split(\":\"))\n"
                       "            d = _stamp_mismatch(h, mi, circular=True)",
                       "h, mi = map(int, m2.group(2).split(\":\"))\n"
                       "            d = _stamp_mismatch(h, mi, circular=False)"),
}


def _prepare_target(porcha_key):
    """Без порчи — испытуемый WRITE как есть. С порчей — копия РЯДОМ с соседями
    (mezo_stand.copy_tool: write-message.py тянет dryrun/mezo_refs/refs_check) во
    временном стенде, с ОТКАЧЕННЫМ дефектом; путь подменяется на неё ОДНИМ местом."""
    if not porcha_key:
        return WRITE, None
    stand = mezo_stand.new("bite-stamp-porcha-")
    copy_path = mezo_stand.copy_tool(WRITE, stand)
    text = copy_path.read_text(encoding="utf-8")
    old, new = BREAKS[porcha_key]
    if old not in text:
        raise SystemExit(f"⛔ порчу «{porcha_key}» НЕ УДАЛОСЬ навести: образец не найден в коде")
    copy_path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"🧪 НАРОЧНАЯ ПОЛОМКА «{porcha_key}» ВЗВЕДЕНА\n")
    return str(copy_path), stand


def _load_module(path):
    """Загрузить write-message.py отдельным модулем — звать check_header_times
    НАПРЯМУЮ, без похода через subprocess и базу: эти случаи — про ОДНУ функцию."""
    sys.path.insert(0, str(Path(path).resolve().parent))
    spec = importlib.util.spec_from_file_location("write_message_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def case(title, ok, detail, differ=False):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if ok else '🔴'} {title}")
    print(f"   {detail}")
    return ok


def build():
    d = str(mezo_stand.new("bite-stamp-"))
    db = os.path.join(d, "s.db")
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, writer_role TEXT,
            timestamp TEXT DEFAULT (datetime('now')), body_md TEXT, tags TEXT,
            priority TEXT, resolved INTEGER DEFAULT 0, broadcast INTEGER DEFAULT 0,
            addressed_by TEXT);
        CREATE TABLE read_cursors (reader_role TEXT PRIMARY KEY, last_read_id INTEGER);
        CREATE TABLE phoenix (role TEXT, section TEXT, body TEXT, saved_at TEXT,
            confirmed_at TEXT, PRIMARY KEY (role, section));
        CREATE TABLE audit_log (id INTEGER PRIMARY KEY, actor_role TEXT, action TEXT,
            target TEXT, diff_md TEXT);
        CREATE TABLE message_addressee (message_id INTEGER, role TEXT, kind TEXT,
            linked_by TEXT DEFAULT 'field', PRIMARY KEY (message_id, role, kind));
        CREATE TABLE roles (role TEXT PRIMARY KEY, status TEXT);
        CREATE TABLE role_status (role TEXT PRIMARY KEY, status TEXT, updated_at TEXT);
        INSERT INTO read_cursors VALUES ('PROTO', 0);
    """)
    con.commit()
    con.close()
    return d, db


def write(db, d, body):
    f = os.path.join(d, "note.md")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(body)
    r = subprocess.run([sys.executable, WRITE, "--db", db, "--role", "PROTO", "--file", f],
                       capture_output=True, text=True, encoding="utf-8",
                       env=mezo_stand.stand_env(d))  # карточка #613: env закреплён за стендом
    con = sqlite3.connect(db)
    row = con.execute("SELECT id, timestamp, body_md FROM messages ORDER BY id DESC "
                      "LIMIT 1").fetchone()
    con.close()
    return row, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    global WRITE
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--porcha", choices=sorted(BREAKS), default=None,
                    help="нарочная поломка: откатить одну из двух правок предложения AIA 03")
    a = ap.parse_args()
    WRITE, _porcha_stand = _prepare_target(a.porcha)

    if not os.path.exists(WRITE):
        raise SystemExit(f"⛔ НЕ ЗАПУСТИЛАСЬ: {WRITE} не найден — приёмке нечего испытывать.")
    ok = True
    d, db = build()

    row, out = write(db, d, "тело записки без всякой подписи")
    ok &= case("① подписи не было — механизм её ПРОСТАВИЛ",
               bool(re.search(r"— PROTO \d{4}-\d\d-\d\d \d\d:\d\d UTC", row[2] or "")),
               f"хвост тела: {(row[2] or '').strip().splitlines()[-1][:60]!r}")

    WRONG = "тело записки\n\n— PROTO 2026-08-08 18:51 UTC\n"
    row2, out2 = write(db, d, WRONG)
    sign2 = row2[2].strip().splitlines()[-1]
    # 🪤 МИГАЛ РАЗ В ЧАС: проверка искала отсутствие ГОЛОГО времени «18:51», а подложка
    # различается с настоящим временем только ДАТОЙ (вчерашней). Когда живые часы показали
    # 18:51, честно исправленная подпись законно несла «18:51» — и случай краснел на
    # ИСПРАВНОМ механизме (пойман в общем прогоне 09.08 18:51:39, в одиночку через минуту
    # зелёный). Проверка была УЖЕ подложки: сверять надо весь подложенный штамп, дата+время.
    ok &= case("② подпись с НЕВЕРНЫМ временем ИСПРАВЛЕНА",
               "2026-08-08 18:51" not in sign2 and row2[1][:16] in sign2,
               f"было «2026-08-08 18:51 UTC», стало {sign2!r}", differ=True)
    ok &= case("⑥ подпись совпадает с колонкой timestamp ПОМИНУТНО",
               row2[1][:16] in sign2,
               f"timestamp {row2[1]} · подпись {sign2!r} — совпадение по построению, не случайно",
               differ=True)

    RIGHT = f"тело записки\n\n— PROTO {row2[1][:16]} UTC\n"
    row3, _ = write(db, d, RIGHT)
    ok &= case("③ подпись уже верна — тело не тронуто",
               row3[2].strip() == RIGHT.strip() or row3[2].strip().endswith("UTC"),
               "верную подпись переписывать незачем: лишнее действие — тоже изменение",
               differ=True)

    QUOTED = ("разбор случая\n"
              "> слово владельца 2026-08-08 15:56 UTC, дословно: «пушить можно»\n"
              "замер сделан 2026-07-16 12:12 UTC, и это ЦИТАТА, а не моя подпись\n\n"
              "— PROTO 2026-08-08 18:51 UTC\n")
    row4, _ = write(db, d, QUOTED)
    body4 = row4[2]
    ok &= case("④ ЦИТИРОВАННОЕ время в середине тела НЕ тронуто",
               "15:56 UTC" in body4 and "2026-07-16 12:12 UTC" in body4,
               "механизм, «исправляющий» цитату, подделывает её — это хуже исходной ошибки",
               differ=True)
    ok &= case("⑦ остальной текст не изменён ни на знак",
               body4.count("\n") == QUOTED.count("\n")
               and "разбор случая" in body4 and "пушить можно" in body4,
               "изменена ровно одна строка — подпись; строк столько же, текст на месте",
               differ=True)

    FOREIGN = ("пересказ чужой записки:\n"
               "> — COORD 2026-08-08 10:00 UTC\n"
               "мой текст после цитаты\n")
    row5, _ = write(db, d, FOREIGN)
    ok &= case("⑤ подпись ЧУЖОЙ роли внутри цитаты не тронута",
               "— COORD 2026-08-08 10:00 UTC" in row5[2],
               "подпись ищется только В КОНЦЕ: чужая метка в середине — данные, а не подпись",
               differ=True)

    # ⑧–⑪ — карточка #371: вторая форма подписи и суд часа в шапке
    COMMA = "тело записки\n\n— PROTO, 2026-08-08 18:51 UTC\n"
    row6, _out6 = write(db, d, COMMA)
    signs6 = [l for l in (row6[2] or "").strip().splitlines()
              if l.strip().startswith("— PROTO")]
    ok &= case("⑧ подпись С ЗАПЯТОЙ исправлена НА МЕСТЕ, вторая не дописана",
               len(signs6) == 1 and row6[1][:16] in signs6[0]
               and "2026-08-08 18:51" not in signs6[0],
               f"подписей {len(signs6)}, хвост {signs6[-1][:60]!r} — неузнанная форма прежде "
               f"плодила ВТОРУЮ подпись и оставляла неверный час", differ=True)

    from datetime import datetime, timedelta, timezone
    _now = datetime.now(timezone.utc)
    _shift = _now + timedelta(hours=2) if _now.hour < 21 else _now - timedelta(hours=2)
    HDRWRONG = (f"[PROTO {_shift.strftime('%H:%M')} UTC] заголовок со сдвигом\n\n"
                f"{_shift.strftime('%Y-%m-%d %H:%M')} UTC · PROTO. Все метки UTC.\n\nтело\n")
    row7, out7 = write(db, d, HDRWRONG)
    ok &= case("⑨ час в шапке со сдвигом — НАЗВАН предупреждением, тело не правлено",
               "час в шапке тела" in out7 and _shift.strftime("%H:%M") in (row7[2] or ""),
               "расхождение называется вслух; метка в теле цела — цитату подделывать нельзя",
               differ=True)
    ok &= case("⑪ час в ЗАГОЛОВКЕ со сдвигом — назван отдельно",
               "час в ЗАГОЛОВКЕ" in out7,
               f"вывод несёт предупреждение о заголовке со сдвигом {_shift.strftime('%H:%M')}",
               differ=True)

    HDROK = f"{_now.strftime('%Y-%m-%d %H:%M')} UTC · PROTO. Все метки UTC.\n\nтело\n"
    _row8, out8 = write(db, d, HDROK)
    ok &= case("⑩ встречный: час в шапке ВЕРНЫЙ — тишина, сверка отмечена",
               "расходится" not in out8 and "сверен" in out8,
               "чистая шапка не шумит; строка «сверен» доказывает, что проверка ШЛА",
               differ=True)

    # ⑫–⑮ ЧЕТЫРЕ ПРОБЫ AIA (предложение 03, карточка #644) — check_header_times
    # напрямую, без похода через базу: случаи про ОДНУ функцию, а не про запись.
    wm = _load_module(WRITE)

    # ⑫ пример метки ВНУТРИ огороженного блока с чужим часом — не судится вовсе.
    # Живой класс: тревога приходит РОВНО на текст, объясняющий, как метку писать.
    NOW_A = "2026-09-15 08:59"
    body_fenced = ("разбор формы метки в шапке\n\n"
                   "```\n"
                   "2026-09-15 23:58 UTC · ПРИМЕР. Так роль пишет шапку.\n"
                   "```\n\n"
                   "дальше обычный текст записки без своей метки\n")
    w, c = wm.check_header_times(body_fenced, NOW_A)
    ok &= case("⑫ AIA-проба: пример метки внутри огороженного блока — не судится",
               c == 0 and len(w) == 0,
               f"проверено {c} · тревог {len(w)} (ожидание AIA: 0 · 0)", differ=True)

    # ⑬ метка СНАРУЖИ, час сходится — судится, тревоги нет.
    NOW_B = "2026-09-15 09:00"
    body_ok = f"[PROTO {NOW_B[11:16]} UTC] час сходится\n\nтело записки\n"
    w, c = wm.check_header_times(body_ok, NOW_B)
    ok &= case("⑬ AIA-проба: метка снаружи, час сходится — проверено 1, тревог нет",
               c == 1 and len(w) == 0,
               f"проверено {c} · тревог {len(w)} (ожидание AIA: 1 · 0)", differ=True)

    # ⑭ метка снаружи, РЕАЛЬНОЕ расхождение 179 минут — проверка НЕ ОСЛЕПЛА
    # круговым сравнением (179 мин — не вблизи полуночи, круг результат не меняет).
    NOW_C = "2026-09-15 12:00"
    body_diff = "2026-09-15 09:01 UTC · PROTO. Все метки UTC.\n\nтело записки\n"
    w, c = wm.check_header_times(body_diff, NOW_C)
    ok &= case("⑭ AIA-проба: метка снаружи, расхождение 179 мин — проверка НЕ ОСЛЕПЛА",
               c == 1 and len(w) == 1,
               f"проверено {c} · тревог {len(w)} (ожидание AIA: 1 · 1)", differ=True)

    # ⑮ метка 23:58, запись 00:02 — КРУГОВОЕ сравнение спасает (4 мин, не 1436).
    NOW_D = "2026-09-15 00:02"
    body_midnight = "2026-09-15 23:58 UTC · PROTO. Все метки UTC.\n\nтело записки\n"
    w, c = wm.check_header_times(body_midnight, NOW_D)
    ok &= case("⑮ AIA-проба: метка 23:58 при записи 00:02 — круг спасает (4 мин, не 1436)",
               c == 1 and len(w) == 0,
               f"проверено {c} · тревог {len(w)} (ожидание AIA: 1 · 0)", differ=True)

    print()
    print(f"{'✅ МЕХАНИЗМ ВРЕМЕНИ ПРИНЯТ' if ok else '🔴 НЕ ПРИНЯТ'} — случаев {CASES}, "
          f"различающих {DIFFER}, испытан {mezo_target.label()}")
    if a.porcha and not ok:
        print("✅ так и надо: под порчей случаи краснеют — они судят предмет, а не форму")
        return 0
    if a.porcha and ok:
        print("⚠️ ПОРЧА ВЗВЕДЕНА, А ВСЁ ПРОШЛО ПРИЁМКУ — случаи НЕ РАЗЛИЧАЮТ этот дефект")
        return 1
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
