"""
bite-printed-names.py — укус на признак `guard-printed-names.py`.

Признак ищет ложь в надписях. Кто проверяет его самого? Без этого он —
седьмой экземпляр собственного класса: печатает «находок нет» и не смотрит.

═══ ДВА ВОПРОСА, И ВТОРОЙ ВАЖНЕЕ ═══
   ① ЛОВИТ ЛИ ИЗВЕСТНОЕ. На заведомо больном коде обязан назвать КАЖДЫЙ экземпляр.
      Больные образцы — не выдумка: это ТЕ САМЫЕ надписи, что врали в наших инструментах.
      Две из трёх уже починены в живом коде ⇒ поймать их на нём нельзя, и образец здесь
      честно объявлен ОБРАЗЦОМ, а не найденной в природе уликой.
   ② МОЛЧИТ ЛИ НА ЗДОРОВОМ. Тот же код, где надпись приведена к поведению, обязан дать НОЛЬ.
      Без этого «ловит» ничего не стоит: признак, кричащий всегда, неотличим от сломанного,
      а привыкнув к его красному, роль перестанет читать и настоящее.

Запуск:  python <абсолютный путь>/bite-printed-names.py
Выход:   0 — оба вопроса отвечены · 1 — не ловит известное · 2 — шумит на здоровом
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).with_name("guard-printed-names.py")

# ── БОЛЬНЫЕ ОБРАЗЦЫ: подлинные надписи, которые врали ────────────────────────
SICK = {
    # ① 06.08: справка обещала обязательность, которой в коде не было
    "sick_db.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", help="путь к базе mezosync.db (обязателен)")
    a = p.parse_args()
    print(a.db)
''',
    # ⑥ 07.08, ЖИВОЙ на момент написания: «обязателен по слову владельца», required нет
    "sick_criterion.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--done-when",
                   help="критерий приёмки: чем докажешь, что сделано (обязателен)")
    a = p.parse_args()
    print(a.done_when)
''',
    # ② 07.08: флаг просит значение, а код смотрит только «задан или нет»
    "sick_to.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--to", help="адресат задан ПОЛЕМ, а не пересказан прозой")
    a = p.parse_args()
    mark = "field" if a.to else None
    print(mark)
''',
    # А: текст зовёт флагом, которого нет ни у кого
    "sick_ghost.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--role")
    a = p.parse_args()
    print("подтверди прочтение: --acknowledge-batch", a.role)
''',
}

# ── ЗДОРОВЫЕ: то же самое, но надпись приведена к поведению ──────────────────
HEALTHY = {
    "ok_db.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", help="путь к базе; если не задан — рядом со скриптом")
    a = p.parse_args()
    print(a.db)
''',
    "ok_criterion.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--done-when", required=True,
                   help="критерий приёмки: чем докажешь, что сделано (обязателен)")
    a = p.parse_args()
    print(a.done_when)
''',
    "ok_to.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--to", help="кому адресовано; имя кладётся в поле")
    a = p.parse_args()
    print("адресат:", a.to)
''',
    "ok_ghost.py": '''
import argparse
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--role")
    p.add_argument("--ack", help="подтверждение батча")
    a = p.parse_args()
    print("подтверди прочтение: --ack", a.role)
''',
}

EXPECTED = {"sick_db.py": "Б", "sick_criterion.py": "Б",
            "sick_to.py": "Г", "sick_ghost.py": "А"}


def lay_out(where: Path, files: dict) -> None:
    where.mkdir(parents=True, exist_ok=True)
    for name, src in files.items():
        (where / name).write_text(src, encoding="utf-8")


def run_guard(where: Path) -> str:
    out = subprocess.run([sys.executable, str(GUARD), "--dir", str(where), "--quiet"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace")
    return out.stdout


def rules_hit(text: str, fname: str) -> set:
    """Какими правилами признак назвал этот файл."""
    hit, rule = set(), None
    for line in text.splitlines():
        if line.startswith("🔴 ПРАВИЛО "):
            rule = line.split()[2]
        elif fname in line and rule:
            hit.add(rule)
    return hit


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="bite-printed-"))
    try:
        sick_dir, ok_dir = tmp / "sick", tmp / "healthy"
        lay_out(sick_dir, SICK)
        lay_out(ok_dir, HEALTHY)

        print("УКУС: проверяет ли признак ложных надписей сам себя")
        print(f"образцы ........ {tmp}\n")

        # ── ① ловит ли известное ────────────────────────────────────────────
        print("① БОЛЬНЫЕ ОБРАЗЦЫ — каждый обязан быть назван")
        sick_out = run_guard(sick_dir)
        missed = []
        for fname, rule in EXPECTED.items():
            hit = rules_hit(sick_out, fname)
            ok = rule in hit
            got = ",".join(sorted(hit)) or "—"
            print(f"   {fname:20} ждём правило {rule} · получено "
                  f"{got:16} {'✅' if ok else '🔴 ПРОПУЩЕН'}")
            if not ok:
                missed.append(fname)

        # ── ② молчит ли на здоровом ─────────────────────────────────────────
        print("\n② ЗДОРОВЫЕ ОБРАЗЦЫ — признак обязан МОЛЧАТЬ")
        ok_out = run_guard(ok_dir)
        noisy = [f for f in HEALTHY if rules_hit(ok_out, f)]
        for fname in HEALTHY:
            hit = rules_hit(ok_out, fname)
            print(f"   {fname:20} {'🔴 ЛОЖНОЕ СРАБАТЫВАНИЕ: ' + str(sorted(hit)) if hit else '✅ молчит'}")

        # ── ИТОГ ────────────────────────────────────────────────────────────
        print(f"\nСВОЙСТВА: ① называет все {len(EXPECTED)} больных образца")
        print(f"          ② на здоровых даёт ноль находок")
        if missed:
            print(f"\nИТОГ: 🔴 НЕ ЛОВИТ ИЗВЕСТНОЕ — пропущены: {', '.join(missed)}")
            return 1
        if noisy:
            print(f"\nИТОГ: 🔴 ШУМИТ НА ЗДОРОВОМ — {', '.join(noisy)}."
                  "\n      Это хуже пропуска: к вечно красному привыкают и перестают читать.")
            return 2
        print("\nИТОГ: ✅ ЛОВИТ ВСЕ ЧЕТЫРЕ И МОЛЧИТ НА ЗДОРОВЫХ — признак смотрит, а не спит")
        print("⚖️ И это НЕ значит «ложных строк в контуре нет»: признак закрывает 3 экземпляра")
        print("   из 6. Ложная причина, ложный срок и подмена источника ловятся только глазами.")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
