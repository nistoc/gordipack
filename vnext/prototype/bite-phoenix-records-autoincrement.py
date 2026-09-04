# -*- coding: utf-8 -*-
"""ПРИЁМКА шага схемы 20260904-phoenix-records-autoincrement — карточка #532 (причина).

Всё на КОПИИ живой базы; живая не открывается на запись ни одним случаем.

СЛУЧАИ:
  ① КОНТРОЛЬ на НЕмигрированной копии: удалить последнюю запись → вставить новую →
     номер ПОВТОРИЛСЯ. Это беда карточки, воспроизведённая опытом, а не прочитанная
     в коде. Не воспроизвелась — опыт не различает, и всё ниже не значит ничего.
  ② холостой прогон: отпечаток базы (все таблицы) НЕ изменился.
  ③ применение: каждая строка на месте — число, сумма длин, отпечаток (id·role·section·body).
  ④ AUTOINCREMENT в схеме · счётчик ≥ max(id) · четыре указателя на месте · журнал верен.
  ⑤ ГЛАВНЫЙ: тот же опыт, что ①, на мигрированной копии → номер НЕ повторился.
  ⑥ повторный запуск шага — «уже сведено», база не тронута (отпечаток тот же).
  ⑦ ВСТРЕЧНЫЙ: инструмент памяти на мигрированной копии собирает тело знак в знак
     (пересборка не сломана сменой ключа).
  ⑧ ПОРЧА: подменить в копии шага сверку «до сноса» на ложь → шаг обязан ОТКАТИТЬ
     и оставить базу нетронутой (отпечаток тот же, phoenix_records_new не осталась).
"""
import hashlib
import io
import os
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

ЗДЕСЬ = pathlib.Path(__file__).resolve().parent
КОРЕНЬ = ЗДЕСЬ.parent
ЖИВАЯ = КОРЕНЬ / ".mezosync" / "mezosync.db"
ШАГ = КОРЕНЬ / ".mezosync" / "scripts" / "migrations" / "20260904-phoenix-records-autoincrement.py"
ПАМЯТЬ = ЗДЕСЬ / "memory-records.py"

прошло: list[str] = []
пало: list[str] = []


def случай(имя: str, ок: bool, чем: str = "") -> None:
    (прошло if ок else пало).append(имя)
    print(f"  {'✅' if ок else '🔴'} {имя}")
    if not ок and чем:
        for с in чем.strip().splitlines()[:8]:
            print(f"       {с}")


def зов(*args, env=None):
    p = subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True,
                       encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {})))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def отпечаток_базы(путь) -> str:
    """Хэш ВСЕХ строк всех таблиц — чтобы «база не тронута» было утверждением, а не надеждой."""
    c = sqlite3.connect(путь)
    h = hashlib.sha256()
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        h.update(t.encode())
        for row in c.execute(f"SELECT * FROM {t} ORDER BY 1"):
            h.update(repr(row).encode("utf-8"))
    c.close()
    return h.hexdigest()[:16]


def отпечаток_записей(путь):
    c = sqlite3.connect(путь)
    h = hashlib.sha256(); n = 0; s = 0
    for id_, role, section, body in c.execute(
            "SELECT id, role, section, body FROM phoenix_records ORDER BY id"):
        h.update(f"{id_}\x1f{role}\x1f{section}\x1f{body}\x1e".encode("utf-8")); n += 1; s += len(body)
    c.close()
    return n, s, h.hexdigest()[:16]


def опыт_повтора_номера(путь) -> tuple[int, int]:
    """Удалить запись с наибольшим номером, вставить новую. Вернуть (удалённый, новый)."""
    c = sqlite3.connect(путь)
    mx = c.execute("SELECT MAX(id) FROM phoenix_records").fetchone()[0]
    c.execute("DELETE FROM phoenix_records WHERE id=?", (mx,))
    cur = c.execute("INSERT INTO phoenix_records (role, section, subject, body, body_chars, created_by) "
                    "VALUES ('ПРОБА', 'state', 'разное', 'подсадка приёмки', 16, 'bite')")
    новый = cur.lastrowid
    c.commit(); c.close()
    return mx, новый


def main() -> int:
    print("=" * 88)
    print("ПРИЁМКА шага 20260904-phoenix-records-autoincrement — карточка #532 (причина)")
    print(f"шаг: {ШАГ}")
    print(f"живая база (только копируется): {ЖИВАЯ}")
    print("=" * 88)
    for f in (ШАГ, ЖИВАЯ, ПАМЯТЬ):
        if not f.is_file():
            sys.exit(f"⛔ ОТКАЗ МЕРИТЬ: нет файла {f}")

    with tempfile.TemporaryDirectory() as tmp:
        песок = pathlib.Path(tmp)
        (песок / "scripts").mkdir()
        # копия базы лежит так, чтобы шаг с --db её нашёл; журнал схемы — рядом со скриптами
        к_контроль = песок / "control.db"
        к_шаг = песок / "step.db"
        shutil.copy2(ЖИВАЯ, к_контроль)
        shutil.copy2(ЖИВАЯ, к_шаг)

        print()
        print("── ① КОНТРОЛЬ: беда воспроизводится на НЕмигрированной копии ─────────")
        уд, нов = опыт_повтора_номера(к_контроль)
        случай("① без счётчика: удалённый номер ВЫДАН ЗАНОВО (беда карточки видна опытом)",
               уд == нов, f"удалён {уд}, новый {нов} — повтора нет, опыт не различает")

        print()
        print("── ②–⑥ ШАГ на копии ──────────────────────────────────────────────────")
        до = отпечаток_базы(к_шаг)
        код, вывод = зов(ШАГ, "--db", к_шаг, "--dry-run")
        случай("② холостой прогон: код 0, база НЕ тронута (отпечаток всех таблиц тот же)",
               код == 0 and "ВХОЛОСТУЮ" in вывод and отпечаток_базы(к_шаг) == до, вывод)

        зап_до = отпечаток_записей(к_шаг)
        код, вывод = зов(ШАГ, "--db", к_шаг)
        зап_после = отпечаток_записей(к_шаг)
        случай("③ применение: каждая запись на месте (число · сумма длин · отпечаток совпали)",
               код == 0 and зап_до == зап_после and "ВРЕЗАНО" in вывод,
               f"код {код} · до {зап_до} · после {зап_после}" + chr(10) + вывод)

        c = sqlite3.connect(к_шаг)
        ddl = c.execute("SELECT sql FROM sqlite_master WHERE name='phoenix_records'").fetchone()[0]
        seq = c.execute("SELECT seq FROM sqlite_sequence WHERE name='phoenix_records'").fetchone()
        mx = c.execute("SELECT MAX(id) FROM phoenix_records").fetchone()[0]
        idx = c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='phoenix_records' "
                        "AND name LIKE 'idx_%'").fetchone()[0]
        хвост = c.execute("SELECT 1 FROM sqlite_master WHERE name='phoenix_records_new'").fetchone()
        c.close()
        случай("④ AUTOINCREMENT в схеме · счётчик ≥ max(id) · 4 указателя · хвоста _new нет · журнал верен",
               "AUTOINCREMENT" in ddl and seq and seq[0] >= mx and idx == 4 and not хвост
               and "✅ проверка журнала" in вывод,
               f"AUTOINCREMENT={'AUTOINCREMENT' in ddl} seq={seq} max={mx} idx={idx} хвост={bool(хвост)}")

        уд, нов = опыт_повтора_номера(к_шаг)
        случай("⑤ ГЛАВНЫЙ: после шага удалённый номер НЕ повторяется",
               нов != уд and нов > уд, f"удалён {уд}, новый {нов}")

        до2 = отпечаток_базы(к_шаг)
        код, вывод = зов(ШАГ, "--db", к_шаг)
        случай("⑥ повторный запуск: «уже сведено», база не тронута",
               код == 0 and "уже сведено" in вывод and отпечаток_базы(к_шаг) == до2, вывод)

        # ⑦ инструмент памяти: исход сборки КАЖДОЙ пары роль·раздел на мигрированной копии
        # обязан быть ТЕМ ЖЕ, что на немигрированной. 🩸 Первая редакция требовала «сходится» —
        # и покраснела на COORD·state, где слои разошлись В ЖИВОЙ базе ещё до шага (роль
        # сохранила память после разбора). Шаг за чужое расхождение не отвечает; отвечает
        # за то, чтобы НИЧЕГО не изменить — и это здесь и судится.
        c = sqlite3.connect(к_контроль)
        пары = c.execute("SELECT role, section FROM phoenix_records WHERE role<>'ПРОБА' "
                         "GROUP BY role, section ORDER BY 1, 2").fetchall()
        c.close()
        def исход(база, роль, разд):
            к, в = зов(ПАМЯТЬ, "--db", база, "--role", роль, "--section", разд, "--собрать")
            строки = [с.strip() for с in в.splitlines() if 'собрано знаков' in с or 'живое тело' in с
                      or 'сходится' in с or 'РАСХОЖДЕНИЕ' in с]
            return (к, tuple(строки))
        разн = [(р, с) for р, с in пары if исход(к_контроль, р, с) != исход(к_шаг, р, с)]
        сходятся = sum(1 for р, с in пары if исход(к_шаг, р, с)[0] == 0)
        случай(f"⑦ ВСТРЕЧНЫЙ: исход сборки всех {len(пары)} пар роль·раздел ОДИНАКОВ до и после шага "
               f"(сходятся {сходятся}, расходятся в живой базе {len(пары)-сходятся} — не предмет шага)",
               not разн, f"исход отличается у: {разн}")

        print()
        print("── ⑧ ПОРЧА копии шага: сверка «до сноса» солгала → обязан откатить ─────")
        к_порча = песок / "porcha.db"
        shutil.copy2(ЖИВАЯ, к_порча)
        исходный = ШАГ.read_text(encoding="utf-8")
        порченый = исходный.replace("        if после != до:", "        if после == до:")
        if порченый == исходный:
            случай("⑧ ПОРЧА: образец не найден — ОПЫТ НЕ ПОСТАВЛЕН", False, "порча не легла")
        else:
            коп = ШАГ.parent / "_porcha_autoincrement_bite.py"   # рядом: шаг ищет журнал от своего места
            try:
                коп.write_text(порченый, encoding="utf-8")
                до3 = отпечаток_базы(к_порча)
                код, вывод = зов(коп, "--db", к_порча)
                c = sqlite3.connect(к_порча)
                хвост = c.execute("SELECT 1 FROM sqlite_master WHERE name='phoenix_records_new'").fetchone()
                c.close()
                случай("⑧ порченый шаг ОТКАТИЛ: код ≠ 0, «откат» в выводе, база нетронута, хвоста нет",
                       код != 0 and "откат" in вывод.lower() and отпечаток_базы(к_порча) == до3 and not хвост,
                       f"код {код} · хвост={bool(хвост)}" + chr(10) + вывод)
            finally:
                if коп.exists():
                    коп.unlink()

    print()
    print("=" * 88)
    print(f"ИТОГ: прошло {len(прошло)} · пало {len(пало)}")
    for и in пало:
        print(f"   🔴 {и}")
    print("=" * 88)
    print("⚖️ ЧЕГО ЭТА ПРИЁМКА НЕ ПРОВЕРЯЕТ: поведение ЖИВОЙ базы под живой нагрузкой —")
    print("   всё здесь на копии. Что копия и живая равносильны, доказывает не совпадение")
    print("   файлов, а прогон инструментов памяти ПОСЛЕ применения к живой (сделать рукой).")
    return 1 if пало else 0


if __name__ == "__main__":
    sys.exit(main())
