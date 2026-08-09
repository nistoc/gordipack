# -*- coding: utf-8 -*-
r"""ПРИЁМКА признака «источник учит СНЯТОМУ механизму» (check-retired-mechanism.py).

Проверяется главное свойство, ради которого признак и написан: ДВА ОТКАЗА ЗВУЧАТ ПО-РАЗНОМУ.
Прежняя живая проверка «фаза в шапке CANON» смешивала их и на смерть своего предмета
отвечала обвинением невиновной стороны.

⛔ ЧИСЛО СЛУЧАЕВ СЛОВОМ ЗДЕСЬ НЕ ПИШЕТСЯ — его печатает прогон (урок соседних приёмок:
подпись «шесть случаев» пережила добавление седьмого и соврала в ЗЕЛЁНОМ выводе).

У каждого различающего случая — ВСТРЕЧНЫЙ. Без встречного починка «не шуметь на истории»
делает признак беззубым, а починка «ловить строже» — шумным; шумного перестают читать.

⛔ Живой базы и живых источников не касается: своя временная база и свой временный каталог.
"""
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHECK = os.path.join(HERE, "check-retired-mechanism.py")

RULE = "md-to-sqlite-phased-cutover"
CASES = 0
DIFFERENTIATING = 0


def build_db(path: str, version, key=RULE):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE rules (id INTEGER PRIMARY KEY, rule_key TEXT, body TEXT,"
                " locked_by TEXT, version INTEGER)")
    if version is not None:
        con.execute("INSERT INTO rules (rule_key, body, locked_by, version) VALUES (?,?,?,?)",
                    (key, "Тело правила. Аварийный выход снят.", "owner", version))
    con.commit()
    con.close()


def build_src(root: str, phoenix_lines, write_lines):
    os.makedirs(root, exist_ok=True)
    for name, lines in (("read-phoenix.py", phoenix_lines),
                        ("write-message.py", write_lines)):
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


def run(db: str, root: str):
    r = subprocess.run([sys.executable, CHECK, "--db", db, "--root", root],
                       capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or ""), r.returncode


def case(title: str, verdict: bool, detail: str, differ: bool = False) -> bool:
    global CASES, DIFFERENTIATING
    CASES += 1
    DIFFERENTIATING += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


# строки-заготовки
ORDER = "🚨 АВАРИЙНЫЙ ВЫХОД: сломается БД — пиши `write-message.py … --md` и зови COORD."
HISTORY = "# --md СНЯТ решением владельца 2026-08-08: страховки больше нет."
CLEAN = "🚨 База недоступна — скажи владельцу живым словом и ОСТАНОВИСЬ."
NEAR_TOMB = ["# Ниже — форма аварийной записи:", ORDER,
             "# ⛔ ОТМЕНЕНО: речь о СОВСЕМ ДРУГОМ признаке — цитата не разбор."]


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="bite-retired-")
    ok = True

    def stand(name, phx, wrt, version=5, key=RULE):
        db = os.path.join(tmp, f"{name}.db")
        root = os.path.join(tmp, name)
        build_db(db, version, key)
        build_src(root, phx, wrt)
        return run(db, root)

    # ① ПРИКАЗ СНЯТОМУ — найти, назвать ИСТОЧНИК и строку
    out, code = stand("a", ["# шапка", ORDER], ["# код"])
    ok &= case("① источник предписывает снятый механизм — красное, назван источник",
               code == 1 and "УЧАТ СНЯТОМУ" in out and "read-phoenix.py:2" in out,
               f"код {code}, в выводе указана строка-виновник", differ=True)

    # ② ВСТРЕЧНЫЙ к ①: чисто — зелёное. Контроль: тот же прогон обязан УМЕТЬ краснеть (①).
    out, code = stand("b", ["# шапка", CLEAN], ["# код"])
    ok &= case("② предписаний нет — зелёное (встречный к ①)",
               code == 0 and "УЧАТ СНЯТОМУ" not in out,
               f"код {code}; контроль умения краснеть — случай ① выше", differ=True)

    # ③ УПОМИНАНИЕ С ПОМЕТКОЙ В ТОЙ ЖЕ СТРОКЕ — не приказ, историю писать можно
    out, code = stand("c", ["# шапка", HISTORY], ["# код"])
    ok &= case("③ упоминание с пометкой снятия В ТОЙ ЖЕ строке предписанием не считается",
               code == 0 and "помеченных упоминаний 1" in out,
               "иначе признак запретил бы писать историю отмен и стал бы шумным", differ=True)

    # ④ ВСТРЕЧНЫЙ к ③ и ПРЯМОЙ УРОК #151: пометка СТРОКОЙ НИЖЕ и про ДРУГОЕ — не гасит.
    out, code = stand("d", ["# шапка"] + NEAR_TOMB, ["# код"])
    ok &= case("④ пометка по СОСЕДСТВУ находку НЕ гасит (встречный к ③, урок #151)",
               code == 1 and "УЧАТ СНЯТОМУ" in out,
               "надгробие рядом отменяет ДРУГОЕ; гасить по соседству — слепнуть тем сильнее, "
               "чем лучше документирован код", differ=True)

    # ⑤ ПРЕДМЕТ УМЕР: правило переписано. Источники НЕ обвиняются — иначе пошлём чинить
    #    исправное. Ровно этот случай и был живым красным 09.08.
    out, code = stand("e", ["# шапка", ORDER], ["# код"], version=6)
    ok &= case("⑤ правило переписано — «ПЕРЕЧЕНЬ УСТАРЕЛ», источник НЕ назван виновным",
               code == 2 and "ПЕРЕЧЕНЬ УСТАРЕЛ" in out and "УЧАТ СНЯТОМУ" not in out,
               f"код {code} (не 1 и не 0); отказ отделён и от красного, и от зелёного",
               differ=True)

    # ⑥ ВСТРЕЧНЫЙ к ⑤: правила нет вовсе — тот же отказ, но НЕ «чисто»
    out, code = stand("f", ["# шапка", CLEAN], ["# код"], version=None)
    ok &= case("⑥ правила нет вовсе — тоже «устарел», а не «чисто» (встречный к ⑤)",
               code == 2 and "ИСЧЕЗЛО" in out,
               "исчезнувший предмет обязан звучать отказом мерить, а не зелёным", differ=True)

    # ⑦ ИСТОЧНИК ПРОПАЛ — молчать нельзя: ненайденный файл ничем не отличим от чистого
    db = os.path.join(tmp, "g.db")
    root = os.path.join(tmp, "g")
    build_db(db, 5)
    os.makedirs(root, exist_ok=True)
    with open(os.path.join(root, "read-phoenix.py"), "w", encoding="utf-8") as f:
        f.write("# шапка\n" + CLEAN + "\n")          # write-message.py НЕ создан
    out, code = run(db, root)
    ok &= case("⑦ источник не найден — сказано вслух, а не зачтено как чистый",
               code == 2 and "не найден" in out,
               "отсутствующий файл даёт ноль совпадений — неотличимо от исправного, "
               "если про это молчать", differ=True)

    # ⑧-А СОСЕДНИЙ ФЛАГ С ТЕМ ЖЕ НАЧАЛОМ. Случай пришёл НЕ из головы: первый же прогон
    #     по живому обвинил `--md-dir` — флаг, которого никто не снимал. Подстрока входит
    #     в имя соседа, и признак назвал виновной невиновную строку. Ровно тот класс,
    #     ради которого он и написан, — только внутри него самого.
    out, code = stand("i", ["# шапка", CLEAN],
                      ['    parser.add_argument("--md-dir", default=None,  # каталог'])
    ok &= case("⑧ соседний флаг `--md-dir` за упоминание `--md` НЕ считается",
               code == 0 and "УЧАТ СНЯТОМУ" not in out,
               "имя механизма совпадает ЦЕЛИКОМ; иначе признак обвиняет однокоренного соседа",
               differ=True)

    # ⑩ ПОМЕТКА В ПРОДОЛЖЕНИИ ОДНОГО ВЫРАЖЕНИЯ засчитывается. Случай пришёл из живого:
    #    @COORD починил флаг образцово, а признак обвинил его код. Вписать пометку в строку
    #    `parser.add_argument("--md",` НЕКУДА — её место в `help=`, и это СИНТАКСИС, а не
    #    небрежность. Требование «та же физическая строка» объявляло неправдой честную запись.
    out, code = stand("j", ["# шапка", CLEAN],
                      ['parser.add_argument("--md", action="store_true",',
                       '                    help="⛔ СНЯТ владельцем 08.08: вызов отклонён.")'])
    ok &= case("⑩ пометка в продолжении ТОГО ЖЕ выражения гасит (единица — выражение)",
               code == 0 and "УЧАТ СНЯТОМУ" not in out,
               "незакрытая скобка означает, что инструкция не кончилась — это одна единица",
               differ=True)

    # ⑪ ВСТРЕЧНЫЙ к ⑩ и защита урока #151: САМОСТОЯТЕЛЬНАЯ соседняя строка НЕ гасит.
    #    Послабление ⑩ обязано быть узким, иначе оно возвращает ровно тот дефект,
    #    ради которого всё затевалось: гашение по окрестности.
    out, code = stand("k", ["# шапка", CLEAN],
                      ['print("сломается база — пиши --md")',
                       '# ⛔ СНЯТО: речь о СОВСЕМ ДРУГОМ механизме.'])
    ok &= case("⑪ законченное выражение соседней пометкой НЕ гасится (встречный к ⑩, урок #151)",
               code == 1 and "УЧАТ СНЯТОМУ" in out,
               "скобки закрыты ⇒ инструкция кончилась ⇒ следующая строка — уже не она",
               differ=True)

    # ⑨ ОБА источника предписывают — счёт не теряется на первом
    out, code = stand("h", ["# шапка", ORDER], ["# код", ORDER])
    ok &= case("⑨ предписания в ОБОИХ источниках названы, счёт не обрывается на первом",
               code == 1 and "read-phoenix.py:2" in out and "write-message.py:2" in out,
               "проверка, показывающая только первое совпадение, учит, что остальных нет")

    print()
    print(f"✅ ПРИЗНАК ПРИНЯТ — случаев {CASES}, различающих {DIFFERENTIATING}, "
          f"у каждого различающего встречный" if ok
          else "🔴 ПРИЗНАК НЕ ПРИНЯТ — числа из него нести нельзя")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
