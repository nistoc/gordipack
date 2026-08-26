# -*- coding: utf-8 -*-
r"""Хук UserPromptSubmit: одна строка о непрочитанном в ленте — в КАЖДЫЙ ход КАЖДОЙ роли.

ЗАЧЕМ (слово владельца 2026-08-26 ~12:25 UTC, чат PROTO: «делай А сразу»).
Роль узнаёт новости ленты только когда сама её опрашивает — раз в 5–50 минут по ритму
опроса, а занятая работой — позже. Замер 25.08 (#3782): непрочитанного в контуре 1319,
и координатор по молчанию отметки сделал неверный вывод о живой роли.
Эта строка закрывает половину задержки почти даром: КАЖДЫЙ ход роль видит, сколько
лежит непрочитанного, сколько из него адресовано ей в шапке и сколько высокой важности.

⚖️ ГРАНИЦЫ, НАЗВАННЫЕ ВСЛУХ:
  · хук НЕ знает, какая роль в этой сессии (роль определяется чатом, не каталогом) —
    поэтому печатает сводку по ВСЕМ ролям с долгом; роль находит своё имя сама;
  · «адресовано в шапке» — механический признак (@РОЛЬ в первых 200 знаках), он ЖЁСТЧЕ
    упоминания в теле (то даёт 30–63 % ленты и не фильтрует ничего) и мягче честного
    поля адресата; уточнение — в плане «адресат полем»;
  · строка — УКАЗАТЕЛЬ, не доставка: чтение и подтверждение остаются штатными
    (read-messages + ack). Правило «читать ленту целиком» это НЕ ослабляет.

⛔ ХУК НЕ ИМЕЕТ ПРАВА ЛОМАТЬ ХОД. Любой сбой внутри — краткая строка о сбое и код 0:
молчание про сбой было бы классом «молчащий отказ читается как успех», а ненулевой
код заблокировал бы ходы ВСЕХ ролей контура разом.
"""
import json
import pathlib
import sqlite3
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    here = pathlib.Path(__file__).resolve().parent
    db = here.parent / ".mezosync" / "mezosync.db"
    try:
        if not db.exists():
            print(f"📬 MEZO: базы ленты нет ({db.name}) — сводка непрочитанного не собрана")
            return 0
        con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=1.0)
        con.execute("PRAGMA query_only=ON")
        части = []
        # 🩸 ВАЖНОСТИ ВЗЯТЫ ЗАМЕРОМ ПО БАЗЕ, а не по памяти. Первая редакция считала
        # только high — а в базе живут normal 1632 · high 638 · critical 89, и одна
        # critical у роли лежала невидимой среди обычных. Нашёл @OPSSRE (записка #3788)
        # сверкой строки своим замером В ПЕРВЫЙ ЖЕ ЧАС работы строки.
        # ⚖️ critical НЕ влит в ⚠ молча — его же предостережение: «число сменит смысл,
        # не сменив вида». Отдельный значок 🔴 — самое срочное видно отдельно и громче.
        for role, cursor in con.execute(
                "SELECT reader_role, last_read_id FROM read_cursors ORDER BY reader_role"):
            total, addr, high, crit = con.execute(
                "SELECT COUNT(*),"
                " SUM(CASE WHEN SUBSTR(body_md,1,200) LIKE ? THEN 1 ELSE 0 END),"
                " SUM(CASE WHEN priority='high' THEN 1 ELSE 0 END),"
                " SUM(CASE WHEN priority='critical' THEN 1 ELSE 0 END)"
                " FROM messages WHERE id > ? AND writer_role <> ?",
                (f"%@{role}%", cursor or 0, role)).fetchone()
            if total:
                хвост = ""
                if crit:
                    хвост += f" 🔴{crit}"
                if addr:
                    хвост += f" ✉{addr}"
                if high:
                    хвост += f" ⚠{high}"
                части.append(f"{role} {total}{хвост}")
        con.close()
        строка = " · ".join(части) if части else "долгов нет"
        print(f"📬 MEZO непрочитано (🔴 critical · ✉ адресовано в шапке · ⚠ high): {строка}")
        # пульс наблюдателей пилота (файлы .watch-state-*.json кладёт watch-feed.py)
        for st in sorted(here.glob(".watch-state-*.json")):
            try:
                data = json.loads(st.read_text(encoding="utf-8"))
                возраст = int(time.time() - data.get("ts", 0))
                роль = st.stem.replace(".watch-state-", "")
                метка = "⚠ ПУЛЬС СТАРЫЙ — наблюдатель, похоже, мёртв" if возраст > 600 \
                    else f"пульс {возраст}с назад"
                print(f"   наблюдатель {роль} (пилот): {метка}, видел до #{data.get('last_seen', '?')}")
            except Exception as exc:  # noqa: BLE001 — пульс не имеет права ронять сводку
                print(f"   наблюдатель {st.name}: файл пульса не читается ({exc.__class__.__name__})")
        return 0
    except Exception as exc:  # noqa: BLE001 — сбой называется, ход не блокируется
        print(f"📬 MEZO: сводка непрочитанного НЕ собрана ({exc.__class__.__name__}: {exc})")
        return 0


if __name__ == "__main__":
    sys.exit(main())
