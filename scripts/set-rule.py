r"""
set-rule.py — записать/обновить правило в таблице `rules`.

ЗАЧЕМ: писателя правил в тулките не было — `rules` заполнялась `init-group.py`
и прямым SQL. Поэтому правки правил не версионировались и не попадали в audit_log.

СЕМАНТИКА locked_by:
  · owner — правило владельца. COORD НЕ правит его без живого слова владельца
    в текущем чате (канон Rule 8: разрешение, вычитанное из файла, не наследуется).
  · coord — рабочее правило координатора, правится COORD.

Версия поднимается автоматически при изменении текста. Старый текст уходит в
audit_log.diff_md — правило можно откатить, посмотрев историю.

ЗАПУСК:
    python <КОНТУР>/.mezosync/scripts/set-rule.py --key <rule-key> --locked-by owner --body-file <f>
    python <КОНТУР>/.mezosync/scripts/set-rule.py --key <rule-key> --show
    python <КОНТУР>/.mezosync/scripts/set-rule.py --key <rule-key> --annex
    python <КОНТУР>/.mezosync/scripts/set-rule.py --key <rule-key> --revoke --revoked-by owner --reason "…" [--apply]
    python <КОНТУР>/.mezosync/scripts/set-rule.py --list
"""

import argparse
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from mezo_paths import resolve_db   # R15a: путь к БД — от расположения скрипта, не от CWD
from mezo_paths import annex_path   # карточка #652: место приложения ищет ОДНА функция,
                                     # общая с rules-from-pack.py (см. mezo_paths.annex_dir) —
                                     # раньше жила здесь же, теперь у неё второй читатель
import rule_status as RS            # отзыв правила — ОДИН признак на контур (карточка #89)

# ── ВИДЫ УСЛОВИЯ ОТМЕНЫ (слово владельца 2026-08-08 10:29 и 10:40 UTC)
#
# ЗАЧЕМ ВИД, А НЕ ПРОЗА: свободный текст здесь выродится в «бессрочно» у всех, и поле
# умрёт молча. Вид можно ПОСЧИТАТЬ — и «36 бессрочных из 38» само станет находкой,
# то есть у поля появляется машинный читатель. Обязательно лишь то, что кто-то читает
# на следующем шаге (разбор @PROTO #3385, довод принят).
#
# 🔴 ЧЕМ ОПЛАЧЕНО: шесть правил, отозванных 18.07 ОДНИМ ходом, умерли ЗАРАНЕЕ, и никто
# этого не заметил — timers-always-on («эпоха всегда включённых таймеров кончилась»),
# wip-pulse («канал заморожен, пульс никем не исполнялся»), channel-rotation
# («ротировать нечего»). Они дожили не до потери смысла, а до дня, когда человек сел
# и пересмотрел свод целиком. Условие отмены — срок годности, которого им не хватило.
EXPIRY_KINDS = {
    "forever":       "отменяется только словом. Считается и печатается числом",
    "until_date":    "до даты — проверка механически спросит, не прошла ли",
    "until_event":   "до НАБЛЮДАЕМОГО события («когда портал перестанет звать /v1/labels»),"
                     " а не «когда станет лучше»",
    "while_measured": "пока держится замер: число + чем мерено. Самая сильная форма —"
                     " проверка перемеряет и говорит, держится ли основание",
}

# Поля основания: (имя колонки, имя аргумента, что писать человеческими словами)
BASIS_FIELDS = [
    ("basis",         "--basis",         "на каком ОСНОВАНИИ правило существует "
                                         "(замер с числом · инцидент · довод)"),
    ("authorized", "--authorized-by", "КТО разрешил (owner · coord · имя роли)"),
    ("source_ref",    "--source-ref",    "ГДЕ это сказано («#3385» · «чат COORD 2026-08-08 10:29 UTC»)"),
]


def refuse_without_basis(key, eff, missing, bad_kind=None, need_detail=False):
    """Печатает ОТКАЗ человеческими словами и выходит с ненулевым кодом.

    ⛔ Отказ, а не просьба — и это не строгость ради строгости, а замер: четыре механизма,
    заведённые «по желанию», не позваны ни разу (--task 0 из 1724 · parent_id 0 из 84 ·
    «какой запиской» 0 из 9 · гашение срочности 0 из 546). А описание приёмки у задач,
    сделанное ОТКАЗОМ, прижилось в тот же день. Граница между живым механизмом
    и мёртвым проходит ровно по «просьба или отказ» (слово владельца 2026-08-08 10:29 UTC).
    """
    print(f"\n⛔ ПРАВИЛО {key} НЕ СОХРАНЕНО: правило свода без объяснения — приказ без причины.",
          file=sys.stderr)
    if bad_kind is not None:
        print(f"\n  Вид условия отмены «{bad_kind}» не из списка. Допустимые:", file=sys.stderr)
        for k, why in EXPIRY_KINDS.items():
            print(f"    --expiry-kind {k:14} {why}", file=sys.stderr)
    if need_detail:
        print(f"\n  Для вида «{eff.get('expiry_kind')}» нужна ДЕТАЛЬ: --expiry-cond «...»",
              file=sys.stderr)
        print("    until_date .... дата · until_event .... наблюдаемое событие ·"
              " while_measured .. число и чем мерено", file=sys.stderr)
    if missing:
        print("\n  Не хватает:", file=sys.stderr)
        for col, arg, human in missing:
            print(f"    {arg:18} {human}", file=sys.stderr)
        print("\n  ⚠️ Задним числом по памяти не восстанавливай: основание, вспомненное"
              " спустя время,\n     выглядит доказательством, не будучи им. Если основания нет —"
              " его и напиши\n     («основания нет, заведено на глаз»): это честный факт,"
              " и он тоже читается.", file=sys.stderr)
    sys.exit(2)


# ── ПРИЛОЖЕНИЕ К ПРАВИЛУ (карточка #652, этап 1 глобальной задачи #651; слово владельца
# 2026-09-24 10:31:14 UTC, чат PROTO: «где применимо часть логики вынесешь в отдельные
# файлы, чтобы сокращение размера не повлияло заметно на ухудшение качества»).
# ⚖️ В ТЕКСТЕ ПРАВИЛА — НОРМА, В ПРИЛОЖЕНИИ — РАЗБОР СЛУЧАЕВ И ПОЛНЫЙ ПЕРЕЧЕНЬ. Текст правила
# читают все роли при каждом касании; разбор нужен, когда норма не отвечает на случай.
# Прежний полный текст правила остаётся и в журнале правок (audit_log «--- БЫЛО ---»).
# 🪤 ПРИЁМНИК ВЫВОДИТСЯ ОТ БАЗЫ ПО ТОЙ ЖЕ РАСКЛАДКЕ, ЧТО И ЗЕРКАЛО (export-rules._default_out):
# у контура-автора — рядом с зеркалом в репозитории документов (там его хранит git),
# у новорождённого — рядом с базой. Путь машины здесь не впечатан — по той же причине,
# по которой его вынули из зеркала: стенд из чужого места писал бы в живое.
# ⚡ САМА ФУНКЦИЯ annex_path() ПЕРЕЕХАЛА В mezo_paths.py (доставка приложений соседям,
# карточка #651 этап 2): rules-from-pack.py кладёт приложение тем же способом при
# --adopt/--merge/--annexes, и месту полагается быть ОДНИМ на обоих читателей, а не
# списанным дважды. Здесь — только импорт (см. шапку файла).
KEY_FORM = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def show_annex(conn, args):
    """Печатает приложение. Два разных «нет» — разными словами и кодами:
    правила нет (1) · правило есть, приложения нет (3)."""
    if not KEY_FORM.match(args.key):
        sys.exit(f"⛔ «{args.key}» не похоже на ключ правила (строчные латинские буквы, цифры, дефис)")
    if conn.execute("SELECT 1 FROM rules WHERE rule_key=?", (args.key,)).fetchone() is None:
        print(f"ERR: правила {args.key} нет", file=sys.stderr)
        sys.exit(1)
    path = annex_path(args.db, args.key)
    if not path.is_file():
        print(f"📎 у правила {args.key} приложения нет в этом контуре (искала: {path.as_posix()})")
        print(f"   Норма целиком — в тексте правила: set-rule.py --key {args.key} --show")
        sys.exit(3)
    text = path.read_text(encoding="utf-8")
    print(f"📎 приложение к правилу {args.key} — {len(text)} знаков · {path.as_posix()}")
    print("   ⚖️ Норма — в тексте правила (--show); здесь разбор случаев и полный перечень.")
    print("      Разошлись — верх у текста правила: приложение его поясняет, а не отменяет.")
    print()
    print(text)


# ── СНЯТИЕ ПРАВИЛА ОДНИМ ВЫЗОВОМ (слово владельца «Б», чат COORD 2026-09-24 10:35 UTC,
# записка #5330: «PROTO делает в инструменте правил флаг «снять правило», потом я снимаю
# правила штатно»).
# 🔴 ЧТО БЫЛО ДО ФЛАГА: у свода не было инструмента снятия — «снято» писалось только прямой
# записью в базу. Такая запись мимо инструмента не оставляет ни журнала правок, ни зеркала,
# и поле с текстом расходятся молча: поле говорит «снято», текст читается как приказ.
# ⚖️ ПОЛЕ И ТЕКСТ ОБЯЗАНЫ ОТВЕЧАТЬ ОДИНАКОВО. Сверка — общим признаком rule_status.py (он
# один на контур и нарочно узкий: «⛔ ОТОЗВАНО» в начале текста). Сверяется ДВАЖДЫ: до записи
# (иначе записали бы расхождение) и после — из базы (иначе сверили бы своё намерение, а не
# то, что легло).
REVOKE_AT_FORM = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})? UTC$")
STATUS_MIGRATION = "20260810-rule-status-field.py"


def revoke_mark(at, by, src, reason):
    """Пометка о снятии — первой строкой текста; прежний текст остаётся ниже как след."""
    head = f"⛔ ОТОЗВАНО {at} · решил: {by}" + (f" · сказано: {src}" if src else "")
    return (f"{head}\nПРИЧИНА: {reason}\n"
            "Текст ниже оставлен как след прежнего решения, а НЕ как приказ — не исполнять.")


def field_and_text(body, status):
    """→ (снято по полю, снято по тексту) — оба ответа общим признаком контура."""
    by_field, _ = RS.revoked_of(body, status, True)
    return by_field, RS.is_revoked_body(body)


def revoke_rule(conn, args):
    mixed = [flag for flag, val in (("--body", args.body), ("--body-file", args.body_file),
                                    ("--show", args.show), ("--annex", args.annex),
                                    ("--skill-delivery", args.skill_delivery),
                                    ("--locked-by", args.locked_by)) if val]
    if mixed:
        print(f"⛔ --revoke не сочетается с {' '.join(mixed)}: снятие меняет только статус и"
              " пометку в начале текста. Правка текста — отдельным вызовом.", file=sys.stderr)
        sys.exit(2)
    if not RS.has_status_field(conn):
        mig = (Path(__file__).resolve().parent / "migrations" / STATUS_MIGRATION).as_posix()
        sys.exit("⛔ В этой базе нет поля статуса правила — снятие было бы только прозой, а её\n"
                 f"   поле не видит. Накати шаг схемы: python {mig}")
    row = conn.execute("SELECT body, locked_by, version, status, revoked_at, revoked_by "
                       "FROM rules WHERE rule_key=?", (args.key,)).fetchone()
    if row is None:
        print(f"ERR: правила {args.key} нет — снимать нечего", file=sys.stderr)
        sys.exit(1)
    body, locked_by, version, status, was_at, was_by = row
    if (status or "").strip().lower() in RS.REVOKED_VALUES:
        print(f"✅ {args.key}: уже снято ({was_at or 'час не записан'}, решил: {was_by or '—'})"
              " — ничего не меняю")
        return

    reason = (args.reason or "").strip()
    by = (args.revoked_by or "").strip()
    at = (args.revoked_at or "").strip() or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    missing = [m for m, v in (("--reason      почему снято", reason),
                              ("--revoked-by  кто решил снять (owner · coord · имя роли)", by)) if not v]
    if missing or not REVOKE_AT_FORM.match(at):
        print(f"\n⛔ ПРАВИЛО {args.key} НЕ СНЯТО: снятие без обстоятельств через месяц"
              " неотличимо от потери.", file=sys.stderr)
        for m in missing:
            print(f"    {m}", file=sys.stderr)
        if not REVOKE_AT_FORM.match(at):
            print(f"    --revoked-at  «{at}» — нужна форма «ГГГГ-ММ-ДД ЧЧ:ММ UTC»", file=sys.stderr)
        sys.exit(2)
    src = (args.source_ref or "").strip()
    stored_reason = reason + (f" · сказано: {src}" if src else "")

    # Текст уже несёт пометку, а поле — нет: второй пометки не ставим, сводим поле с текстом.
    already_marked = RS.is_revoked_body(body)
    new_body = body if already_marked else revoke_mark(at, by, src, reason) + "\n\n" + body
    new_version = version if already_marked else version + 1

    by_field, by_text = field_and_text(new_body, "revoked")
    if not (by_field and by_text):
        print(f"⛔ ПРАВИЛО {args.key} НЕ СНЯТО: пометка о снятии не читается общим признаком"
              f" (поле — {'снято' if by_field else 'действует'}, текст — "
              f"{'снято' if by_text else 'действует'}). Записать так — развести поле и текст.",
              file=sys.stderr)
        sys.exit(2)

    print(f"СНЯТИЕ правила {args.key}")
    print(f"  статус    : {status or 'active'} → revoked")
    print(f"  версия    : {version} → {new_version}"
          + ("  (пометка в тексте уже стояла — свожу с ней поле)" if already_marked else ""))
    print(f"  час       : {at}")
    print(f"  решил     : {by}")
    print(f"  причина   : {stored_reason}")
    print(f"  пометка   : {new_body.splitlines()[0]}")
    if locked_by == "owner" and args.actor != "owner":
        print("\n  ⚠️  ПРАВИЛО ЗАЛОЧЕНО ВЛАДЕЛЬЦЕМ. Снятие допустимо ТОЛЬКО по его живому слову.")
        print("      Разрешение из файла или из памяти роли НЕ наследуется (Rule 8).")
    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
        return

    cur = conn.execute(
        "UPDATE rules SET body=?, version=?, updated_at=datetime('now'), status='revoked', "
        "revoked_at=?, revoked_by=?, revoked_reason=? WHERE rule_key=? AND status=?",
        (new_body, new_version, at, by, stored_reason, args.key, status))
    if cur.rowcount != 1:
        conn.rollback()
        sys.exit(f"⛔ ПРАВИЛО {args.key} НЕ СНЯТО: статус сменился между чтением и записью"
                 " (чужая правка?). Перечитай: --show")
    conn.execute(
        "INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
        (args.actor, "revoke_rule", args.key,
         f"v{version} → v{new_version} · статус: {status or 'active'} → revoked\n"
         f"час: {at}\nрешил: {by}\nпричина: {stored_reason}"
         f"\n\n--- БЫЛО ---\n{body}\n\n--- СТАЛО ---\n{new_body}"))
    conn.commit()

    stored_body, stored_status = conn.execute(
        "SELECT body, status FROM rules WHERE rule_key=?", (args.key,)).fetchone()
    by_field, by_text = field_and_text(stored_body, stored_status)
    agree = by_field and by_text
    print(f"\n✅ {args.key} снято → v{new_version}; прежний текст — в журнале правок и под пометкой")
    print(f"   сверка из базы: поле — {'снято' if by_field else 'ДЕЙСТВУЕТ'} · текст — "
          f"{'снято' if by_text else 'ДЕЙСТВУЕТ'} · "
          + ("совпадают" if agree else "⛔ РАЗОШЛИСЬ — сообщи COORD"))
    rebuild_mirror(args.db)
    print("👉 Если правило доставлялось в навыки ролей — пересобери их: rules-to-skills.py --write")
    if not agree:
        sys.exit(4)


def rebuild_mirror(db):
    """Пересобирает зеркало правил после записи в ЖИВУЮ базу. Поломка — громко, но запись
    в базе уже состоялась и не откатывается."""
    # ── ЗЕРКАЛО ПЕРЕСОБИРАЕТСЯ ЗДЕСЬ ЖЕ, А НЕ «ПОСТАРАЕМСЯ ПОТОМ»
    # Слово владельца 2026-08-07 13:47 UTC: «файл-зеркало с правилами оставляем как есть,
    # просто постараемся обновлять его при каждом обновлении правил в БД».
    # ⚠️ «Постараемся» — ровно та форма, которая уже подвела: генератор существовал, работал
    # и звался РУКАМИ, а последний раз его позвали 27.07. Зеркало отстало на ОДИННАДЦАТЬ суток
    # и три ревизии реестра ролей — самого читаемого правила канона — и нашлось это случайно.
    # 📌 Класс дня (@STUD): назвать риск и закрыть риск — разные работы, и первая мешает
    # заметить, что второй не было. Намерение владельца исполняется ЗДЕСЬ: правка правила
    # и пересборка зеркала — одно действие, разойтись им нечем.
    # ⛔ Пересборка НЕ смеет отменить уже сделанную запись: правило в БД — источник правды,
    # зеркало — производное. Поломка генератора обязана быть ГРОМКОЙ и не стоить записи.
    # 🔴 НО СНАЧАЛА — ЧЕЙ ЭТО ПРОГОН. Зеркало пишется по ЖЁСТКОМУ пути в atlas.archs
    # (export-rules.py: OUT). Значит правка правила в БД-ПЕСОЧНИЦЕ перезаписала бы ЖИВОЙ
    # файл содержимым песочницы — тестовыми правилами приёмки в том числе.
    # ⚠️ Комментарий ниже утверждал, что явная передача --db это лечит. Она лечит ИСТОЧНИК
    # (собираем из той базы, куда писали) и НЕ лечит ПРИЁМНИК: он один на все базы.
    # Найдено своей же приёмкой 08.08 10:47 UTC — ровно перед тем, как я бы это и сделал.
    live_db = str(resolve_db(None, __file__))
    if Path(db).resolve() != Path(live_db).resolve():
        print(f"🪞 зеркало НЕ пересобрано — БАЗА НЕ ЖИВАЯ: {db}")
        print(f"   живая: {live_db}. Производное живого репо не собирают из песочницы.")
        return

    gen = Path(__file__).resolve().parent / "export-rules.py"
    if not gen.exists():
        print(f"⚠️ зеркало НЕ пересобрано: не найден {gen}", file=sys.stderr)
        return
    # ⚠️ --db ПЕРЕДАЁТСЯ ЯВНО, и это не педантизм: без него генератор резолвит БД
    # по умолчанию (R15a) и пересобрал бы зеркало из ЖИВОЙ базы, пока правило писалось
    # в другую (например, в копию под укус). Поймано укусом сразу: правило легло в копию,
    # зеркало не изменилось ни на байт — и выглядело это как «всё сошлось».
    # 📌 Ровно сегодняшний класс: два действия рядом читают РАЗНЫЕ источники, а вместе
    # выглядят одним. Молчаливая правка живого зеркала во время чужого прогона — цена.
    r = subprocess.run([sys.executable, str(gen), "--db", str(db), "--apply"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode == 0:
        tail = [l for l in (r.stdout or "").splitlines() if l.strip()]
        print("🪞 " + (tail[-1].strip() if tail else "зеркало пересобрано"))
    else:
        print(f"⚠️ ЗЕРКАЛО НЕ ПЕРЕСОБРАНО (код {r.returncode}). Правило в БД ЗАПИСАНО.",
              file=sys.stderr)
        print((r.stdout or "") + (r.stderr or ""), file=sys.stderr)
        print(f"   позови руками: python {gen} --apply", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    # R15a довезён 27.07: set-rule стоит в шапке КАНОНА, где --db уже убран из примеров ⇒
    # без этого канон учил бы падающей команде (найдено запуском, не диффом).
    ap.add_argument("--db", default=None, help="Путь к mezosync.db (по умолчанию — рядом со скриптом)")
    ap.add_argument("--key")
    ap.add_argument("--body")
    ap.add_argument("--body-file", help="файл с текстом правила (для длинных)")
    ap.add_argument("--locked-by", choices=["owner", "coord"])
    ap.add_argument("--actor", default="COORD")
    # ── Три поля основания + вид и деталь условия отмены (миграция 20260808-rule-basis-and-cancel)
    ap.add_argument("--basis", help="на каком основании правило существует (замер · инцидент · довод)")
    ap.add_argument("--authorized-by", dest="authorized", help="кто разрешил")
    ap.add_argument("--source-ref", dest="source_ref", help="где сказано: «#3385» или «чат COORD ... UTC»")
    ap.add_argument("--expiry-kind", dest="expiry_kind", choices=sorted(EXPIRY_KINDS),
                    help="вид условия отмены: " + " · ".join(sorted(EXPIRY_KINDS)))
    ap.add_argument("--expiry-cond", dest="expiry_cond",
                    help="деталь вида: дата · наблюдаемое событие · число и чем мерено")
    ap.add_argument("--skill-delivery", dest="skill_delivery", choices=["yes", "no", "unset"],
                    help="доставлять ли правило до подсказок ролей: yes · no · "
                         "unset (вернуть в «не решено»). Тела правила НЕ трогает")
    ap.add_argument("--annex", action="store_true",
                    help="показать приложение к правилу: разбор случаев и полный перечень, "
                         "вынесенные из текста правила")
    ap.add_argument("--revoke", action="store_true",
                    help="снять правило: статус «снято», час, кто решил, причина, пометка о снятии "
                         "в начале текста, журнал правок и зеркало — одним вызовом")
    ap.add_argument("--reason", help="для --revoke: почему снято (обязательно)")
    ap.add_argument("--revoked-by", dest="revoked_by",
                    help="для --revoke: кто решил снять — owner · coord · имя роли (обязательно)")
    ap.add_argument("--revoked-at", dest="revoked_at",
                    help="для --revoke: час решения «ГГГГ-ММ-ДД ЧЧ:ММ UTC»; без него — текущий час UTC")
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--apply", action="store_true", help="без него — dry-run диффа")
    args = ap.parse_args()
    args.db = str(resolve_db(args.db, __file__))   # R15a: от расположения скрипта, не от CWD

    try:  # mode=rw: connect НЕ создаёт пустую БД-фантом при опечатке пути (П1 16.07)
        conn = sqlite3.connect(f"file:{args.db}?mode=rw", uri=True)
    except sqlite3.OperationalError:
        sys.exit(f"ERR: БД не найдена: {args.db}")

    if args.list:
        # ⚠️ ЧТЕНИЕ НИЧЕГО НЕ ТРЕБУЕТ: отказ живёт на записи. Список обязан работать и тогда,
        # когда основания не заполнены ни у кого, — иначе первым же прогоном он запретил бы
        # смотреть на собственный долг.
        # ⚠️ Поле статуса подставляется в запрос ТОЛЬКО когда оно есть в базе. Иначе вышло бы
        #    хуже прежнего: механизм спрашивал бы про поле, получал пустоту и объявлял всё
        #    действующим — включая десять отозванных. Пустой ответ от несуществующего поля
        #    выглядит спокойнее, чем ошибка, и потому опаснее её.
        has_status = RS.has_status_field(conn)
        rows = conn.execute(
            "SELECT rule_key, locked_by, version, LENGTH(body), basis, expiry_kind, body"
            + (", status" if has_status else ", NULL") +
            " FROM rules ORDER BY rule_key").fetchall()
        # ⚡ ПРИЗНАК ОТЗЫВА ЖИВЁТ В ОДНОМ МЕСТЕ (rule_status.py, карточка #89, шаг 3).
        #    Здесь он стоял свой, в зеркале — свой, в Перископе — третий; на сегодняшнем
        #    своде все трое отвечали «10», но на четырёх различающих написаниях расходились
        #    все четыре раза (замер 2026-08-10 08:28 UTC). Совпадение чисел было свойством
        #    ДАННЫХ, а не механизма, и держалось лишь потому, что надгробия писали одинаково.
        #    Тот же модуль умеет читать ПОЛЕ статуса, когда оно появится, — поле сильнее текста.
        KIND_MARK = {"forever": "∞", "until_date": "📅", "until_event": "👁", "while_measured": "📏"}
        live, tomb, blind, kinds = 0, 0, 0, {}
        for key, lock, ver, blen, basis, ckind, body, status in rows:
            is_tomb, _ = RS.revoked_of(body, status, has_status)
            if is_tomb:
                tomb += 1
            else:
                live += 1
                if not (basis or "").strip():
                    blind += 1
                kinds[ckind or "—"] = kinds.get(ckind or "—", 0) + 1
            mark = "⚰️" if is_tomb else (" " if (basis or "").strip() else "🔴")
            print(f"  {mark}{key:33} 🔒{lock:6} v{ver}  {blen:5}b  {KIND_MARK.get(ckind, ' ')}")
        print(f"\n  живых {live} · надгробий {tomb} · 🔴 без основания {blind} из {live}")
        # Распределение видов печатается ВСЕГДА — это защита самого поля: если все выберут
        # «бессрочно», поле умрёт, и увидеть это можно только числом (риск назван @PROTO
        # до вопроса, #3385). «36 бессрочных из 38» само станет находкой.
        if kinds:
            print("  условие отмены: " + " · ".join(
                f"{KIND_MARK.get(k, '')}{k} {n}" for k, n in sorted(kinds.items(), key=lambda x: -x[1])))
        return

    if not args.key:
        print("ERR: нужен --key", file=sys.stderr)
        sys.exit(1)

    if args.revoke:
        revoke_rule(conn, args)
        return
    if args.annex:
        show_annex(conn, args)
        return

    if args.skill_delivery:
        # ── РЕШЕНИЕ О ДОСТАВКЕ (карточка #526, шаг 20260904-rule-skill-delivery) ──
        # ⚖️ ПОЧЕМУ ЭТО ОТДЕЛЬНАЯ ВЕТКА, А НЕ ЕЩЁ ОДНО ПОЛЕ ОБЩЕГО ПУТИ. Общий путь
        # поднимает редакцию и час правки — то есть говорит «норма изменилась». Здесь
        # норма НЕ менялась: изменилось решение, везти ли её в подсказки. Пойди это
        # общим путём — все навыки, несущие правило, разом покраснели бы как отставшие,
        # и роль пересобирала бы их, ничего не изменив ни в одной букве нормы.
        # ⇒ Час правки и редакция остаются нетронутыми НАМЕРЕННО.
        поля = {r[1] for r in conn.execute("PRAGMA table_info(rules)")}
        if "skill_delivery" not in поля:
            sys.exit("⛔ В этой базе нет поля решения о доставке. Накати шаг:\n"
                     "   python <КОНТУР>/.mezosync/scripts/migrations/"
                     "20260904-rule-skill-delivery.py")
        было = conn.execute("SELECT skill_delivery FROM rules WHERE rule_key=?",
                            (args.key,)).fetchone()
        if было is None:
            sys.exit(f"⛔ Правила «{args.key}» в своде нет — решать нечего о чём.")
        стало = None if args.skill_delivery == "unset" else args.skill_delivery
        print(f"  правило   : {args.key}")
        print(f"  доставка  : {было[0] or 'не решено'} → {стало or 'не решено'}")
        print("  ⚖️ тело правила, редакция и час правки НЕ трогаются — навыки не устареют")
        if not args.apply:
            print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
            return
        conn.execute("UPDATE rules SET skill_delivery=? WHERE rule_key=?", (стало, args.key))
        conn.commit()
        print("✅ ЗАПИСАНО.")
        if стало == "yes":
            print("👉 Дальше ДВА хода, и первый рукой: внеси ключ в нужный пакет "
                  "в vnext-tools/rules-to-skills.py, затем пересобери навыки (--write).\n"
                  "   ⚠️ Одно «да» правило до роли НЕ довозит — проверка будет краснеть "
                  "«обещано и не доехало», пока пакет не назовёт ключ.")
        return

    old = conn.execute(
        "SELECT body, locked_by, version, basis, authorized, source_ref, expiry_kind, "
        "expiry_cond FROM rules WHERE rule_key = ?", (args.key,)).fetchone()

    if args.show:
        if not old:
            print(f"ERR: правила {args.key} нет", file=sys.stderr)
            sys.exit(1)
        print(f"🔒 {args.key} [locked_by={old[1]}, v{old[2]}]")
        # Основание печатается ВМЕСТЕ с телом: правило, прочитанное без него, — приказ
        # без причины, и именно так роль его и исполнит.
        if (old[3] or "").strip():
            print(f"  основание ..... {old[3]}")
            print(f"  разрешил ...... {old[4] or '—'}")
            print(f"  сказано где ... {old[5] or '—'}")
            ck = old[6] or "—"
            print(f"  отменяется .... {ck}" + (f" — {old[7]}" if (old[7] or "").strip() else ""))
        else:
            print("  🔴 ОСНОВАНИЕ НЕ ЗАПОЛНЕНО — правило старше отказа (08.08 10:44 UTC).")
            print("     Задним числом не восстанавливаем: заполнится при следующем касании.")
        if RS.has_status_field(conn):
            st = conn.execute("SELECT status, revoked_at, revoked_by FROM rules WHERE rule_key=?",
                              (args.key,)).fetchone()
            if (st[0] or "").strip().lower() in RS.REVOKED_VALUES:
                print(f"  статус ........ СНЯТО {st[1] or ''} · решил: {st[2] or '—'}")
        annex = annex_path(args.db, args.key)
        if annex.is_file():
            print(f"  приложение .... разбор случаев, {len(annex.read_text(encoding='utf-8'))} знаков:"
                  f" set-rule.py --key {args.key} --annex")
        print()
        print(old[0])
        return

    body = Path(args.body_file).read_text(encoding="utf-8").strip() if args.body_file else args.body
    if not body:
        print("ERR: нужен --body или --body-file", file=sys.stderr)
        sys.exit(1)

    locked_by = args.locked_by or (old[1] if old else "coord")

    # ── ПЯТЬ ПОЛЕЙ: новое значение ИЛИ уже стоящее в базе.
    # ⚠️ Наследование существующего — не послабление: отказ обязан срабатывать там, где ПУСТО,
    # а не там, где роль правит опечатку в тексте давно обоснованного правила. Иначе трение
    # ляжет на добросовестную правку, а обходить его начнут все — и механизм умрёт как просьба.
    prev = {"basis": old[3], "authorized": old[4], "source_ref": old[5],
            "expiry_kind": old[6], "expiry_cond": old[7]} if old else dict.fromkeys(
            ("basis", "authorized", "source_ref", "expiry_kind", "expiry_cond"))
    eff = {col: ((getattr(args, col, None) or prev.get(col) or "").strip() or None)
           for col in prev}

    missing = [(col, arg, human) for col, arg, human in BASIS_FIELDS if not eff[col]]
    bad_kind = None
    if not eff["expiry_kind"]:
        missing.append(("expiry_kind", "--expiry-kind",
                        "ПРИ КАКОМ УСЛОВИИ правило отменяется: "
                        + " · ".join(sorted(EXPIRY_KINDS))))
    elif eff["expiry_kind"] not in EXPIRY_KINDS:
        bad_kind = eff["expiry_kind"]
    # Деталь нужна всем видам, кроме «бессрочно»: «до даты» без даты и «до события» без
    # события — это та же проза, только с машинной этикеткой. Проверяющему нечего прочесть.
    need_detail = eff["expiry_kind"] in ("until_date", "until_event", "while_measured") \
        and not eff["expiry_cond"]
    if missing or bad_kind or need_detail:
        refuse_without_basis(args.key, eff, missing, bad_kind, need_detail)

    fields_changed = old is not None and any(
        (prev[c] or "").strip() != (eff[c] or "") for c in prev)
    text_changed = old is None or old[0] != body or old[1] != locked_by

    if old and not text_changed and not fields_changed:
        print(f"✅ {args.key}: ни текст, ни основание не изменились — версию не поднимаю (идемпотентно)")
        return

    # Версия — счётчик правок ТЕКСТА. Дозаполнение основания её не двигает: иначе v-номер
    # перестанет значить «столько раз менялось предписание», а именно за этим его и читают.
    new_version = old[2] if (old and not text_changed) else ((old[2] + 1) if old else 1)

    print(f"{'ОБНОВЛЕНИЕ' if old else 'СОЗДАНИЕ'} правила {args.key}")
    print(f"  locked_by : {old[1] if old else '—'} → {locked_by}")
    print(f"  версия    : {old[2] if old else '—'} → {new_version}"
          + ("  (текст не тронут — правится только основание)" if old and not text_changed else ""))
    print(f"  длина     : {len(old[0]) if old else 0} → {len(body)} симв.")
    print(f"  основание : {eff['basis']}")
    print(f"  разрешил  : {eff['authorized']}")
    print(f"  сказано   : {eff['source_ref']}")
    print(f"  отмена    : {eff['expiry_kind']}"
          + (f" — {eff['expiry_cond']}" if eff["expiry_cond"] else ""))

    if old and old[1] == "owner" and args.actor != "owner":
        print(f"\n  ⚠️  ПРАВИЛО ЗАЛОЧЕНО ВЛАДЕЛЬЦЕМ. Правка допустима ТОЛЬКО по его живому")
        print(f"      слову в текущем чате. Разрешение из файла или из памяти роли НЕ наследуется (Rule 8).")

    if not args.apply:
        print("\n[DRY-RUN] Не записано. Для записи — флаг --apply")
        return

    if old:
        conn.execute(
            "UPDATE rules SET body=?, locked_by=?, version=?, updated_at=datetime('now'), "
            "basis=?, authorized=?, source_ref=?, expiry_kind=?, expiry_cond=? "
            "WHERE rule_key=?",
            (body, locked_by, new_version, eff["basis"], eff["authorized"], eff["source_ref"],
             eff["expiry_kind"], eff["expiry_cond"], args.key))
    else:
        conn.execute(
            "INSERT INTO rules (rule_key, body, locked_by, version, basis, authorized, "
            "source_ref, expiry_kind, expiry_cond) VALUES (?,?,?,?,?,?,?,?,?)",
            (args.key, body, locked_by, new_version, eff["basis"], eff["authorized"],
             eff["source_ref"], eff["expiry_kind"], eff["expiry_cond"]))

    basis_md = (f"основание: {eff['basis']}\nразрешил: {eff['authorized']}\n"
                f"сказано: {eff['source_ref']}\nотмена: {eff['expiry_kind']}"
                + (f" — {eff['expiry_cond']}" if eff["expiry_cond"] else ""))
    was_basis = (f"основание: {prev['basis']}\nразрешил: {prev['authorized']}\n"
                 f"сказано: {prev['source_ref']}\nотмена: {prev['expiry_kind']}"
                 + (f" — {prev['expiry_cond']}" if (prev["expiry_cond"] or "") else "")) if old else "(нет)"
    conn.execute(
        "INSERT INTO audit_log (actor_role, action, target, diff_md) VALUES (?,?,?,?)",
        (args.actor, "update_rule" if old else "create_rule", args.key,
         f"v{old[2] if old else 0} → v{new_version}\n\n--- БЫЛО ---\n{old[0] if old else '(нет)'}"
         f"\n\n[основание было]\n{was_basis}"
         f"\n\n--- СТАЛО ---\n{body}\n\n[основание стало]\n{basis_md}"))
    conn.commit()
    print(f"\n✅ {args.key} → v{new_version} (🔒{locked_by}); старый текст сохранён в audit_log")

    # Зеркало — тем же действием, что и запись (разбор причин — в rebuild_mirror).
    rebuild_mirror(args.db)


if __name__ == "__main__":
    main()
