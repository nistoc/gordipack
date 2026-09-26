#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""bite-rules-from-pack — приёмка rules-from-pack.py (карточка #608).

    python <КОНТУР>/vnext-tools/bite-rules-from-pack.py

ПРЕДМЕТ: сверка правил контура с правилами пакета GORDI — десять состояний (same ·
pack-changed · local-changed · both-changed · no-base · new · removed · retired-here ·
skipped · только-у-вас), опора по meta и по истории пакета, показ трёх текстов, запись
через set-rule.py (--adopt/--merge), отказ (--skip) и тело предложения (--propose).

ПОВТОРНЫЙ ВОЗВРАТ PROTO (карточка #608, 2026-09-14): «--summary» на живой базе разводит
«снято» по сторонам — «снято в пакете» (removed, прежнее значение) и «снято у вас»
(retired-here: контур сам отключил правило, status≠'active', пакет его по-прежнему
держит). Раньше такой ключ падал в «new» и подталкивал вернуть осознанно снятое — случаи
㊸/㊹.

ТРЕТЬЯ ПРИЁМКА, ВОЗВРАТЫ COORD/PROTO (карточка #608, 2026-09-14): В1 (㊺/поломка) —
--propose по retired-here-ключу пишет письмо «снять в пакете» (статус · основание снятия
из полей rules · текст пакета · цена), а не отказывает «предлагать нечего». В2 (㊻/
поломка) — подсказка на gordi-issue.py берёт путь от СВОЕГО расположения, не впечатанный
<КОНТУР>: из контура-песочницы вне этого пути подсказка раньше вела в пустоту.

ПОВТОРНАЯ ПРИЁМКА Н1, ЗАМЕЧАНИЯ COORD (карточка #608, 2026-09-14, возврат PROTO 10:08
UTC): ㊼/поломка — --show на «изменено с обеих сторон» печатает текст пакета и ваш текст
ОДИН раз, а не дважды (блок трёх текстов теперь говорит только про опору, тексты — выше
по выводу). ㊽/поломка — холостой --merge в подсказке set-rule.py печатает САМ путь из
--file, а не подпись-заглушку «<сведённый текст из --file>».

ИЗОЛЯЦИЯ ОТ ЖИВОГО (правило «acceptance-isolated-from-live», свод контура, 2026-09-14):
  ① СРЕДА — каждый подпроцесс на своём временном стенде идёт со средой этого стенда
     (`mezo_stand.stand_env`), а не со средой вызывающего: живой MEZO_CONTAINER сюда
     попасть не должен НИКАК.
  ② ДАННЫЕ — ожидание берётся из ТОГО, что сама приёмка построила (фиктивные пакет и
     контур), а не из того, что сегодня лежит в живой базе.
Все рабочие каталоги — через `mezo_stand.new()` (временный, полностью на диске, не
живой контур; в клон пакета GORDI ничего не пишется — фиктивный пакет строится в
своей папке). ПОСЛЕДНИМ случаем — контроль: живая база контура НЕ изменилась. Полное
побайтное сравнение живой базы здесь не годится (её параллельно пишут другие роли —
класс «испытываем не то, что чиним»): контроль ищет СВОИ, заведомо придуманные ключи
(`zzz-bite-rfp-...`) в живой таблице `rules` и в meta до и после — их там не должно
быть НИ РАЗУ, независимо от того, что за это время сделали соседние роли.

Нарочные поломки (А/Б/В) — правят ТЕКСТ rules-from-pack.py В ПАМЯТИ (compile+exec,
`__file__` настоящий) — на диск ничего не пишется; см. `load_rfp`.

ПЕРЕЕЗД ИСПЫТУЕМОГО (карточка #608, шаг 3): rules-from-pack.py теперь живёт среди
инструментов контура (.mezosync/scripts), а эта приёмка осталась в vnext-tools и находит
его через mezo_target.py (тот же образец, что у bite-update-tools-rev.py) — по умолчанию
живой контур, через MEZO_SCRIPTS_ROOT — любая копия.

НАХОДКА PROTO (24.09.2026, случай ⑰б): gordi-issue.py судит писателя РАНЬШЕ тела письма
(карточка #645) — на общем стенде без mezosync.db это OperationalError, не отказ по
телу. ⑰б получил свой подстенд с согласованным снимком живой базы
(mezo_stand.snapshot_db); общий root снимка не получает. Встречный случай — поломка (С)
сразу после ⑰б: пустой раздел под заголовком письма ловит РОВНО ⑰б, не ⑰а.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

sys.path.insert(0, str(HERE))
import mezo_paths  # noqa: E402
import mezo_stand  # noqa: E402 — временный каталог убирается при успехе, сохраняется при провале
import mezo_target  # noqa: E402 — какую копию испытываем (образец: bite-update-tools-rev.py)

# Карточка #608, шаг 3: испытуемый переехал в .mezosync/scripts — приёмка находит его
# ТАМ ЖЕ, где его находят соседние контуры (через update-tools.py), а не по старому
# соседству в vnext-tools. mezo_target уважает MEZO_SCRIPTS_ROOT — приёмку можно
# направить и на копию, не только на живой контур.
RFP_PATH = mezo_target.script("rules-from-pack.py")
# gordi-issue.py — СОСЕД rules-from-pack.py в том же .mezosync/scripts (карточка #645,
# случай ⑰б): переехал ТУДА ЖЕ переездом #608 шаг 3, но здесь до сих пор искался по
# старому соседству в vnext-tools — найдено при починке приёмки (долг пакета #659).
GORDI_ISSUE_PY = mezo_target.script("gordi-issue.py")
print(f"⚖️ испытуется: {mezo_target.label()}")

# Корень СВОЕГО контура — выводится, а не пишется литералом: случай ㊻ ищет его в выводе
# инструмента, запущенного из песочницы ВНЕ этого корня. Литерал пути машины автора перенос
# в пакет отклоняет (заглушка в проверяемом значении сломала бы случай у потребителя), а у
# чужого контура он и проверял бы не то — чужой корень, а не свой.
OWN_ROOT = str(mezo_paths.container_root()).replace("\\", "/")
OWN_ROOT_BS = OWN_ROOT.replace("/", "\\")

# ВОЗВРАТ COORD (карточка #614, ветка «а», 2026-09-14 17:58 UTC): адрес в meta ЕСТЬ, но не
# читается — отказ обязан нести готовую команду словами ПРО ПРАВИЛА (что делает роль ЭТОГО
# инструмента), не только диагноз update-tools.py. Одна константа — и в случаях ниже, и в
# поломке (Р): разведённые литералы разошлись бы однажды незаметно.
READY_SOURCE_COMMAND = "--source <папка с клоном пакета GORDI>"

CASES = DIFFER = 0


def case(title, verdict, detail, differ=True):
    global CASES, DIFFER
    CASES += 1
    DIFFER += bool(differ)
    print(f"{'✅' if verdict else '🔴'} {title}")
    print(f"   {detail}")
    return verdict


# ── ЗАГРУЗКА ИСПЫТУЕМОГО (нарочные поломки — в памяти) ──────────────────────────────

def load_rfp(patch=None, name="rfp_bite"):
    """Гружает rules-from-pack.py как модуль. patch(src) -> (новый_текст, число_замен),
    правит ИСХОДНИК В ПАМЯТИ — на диск ничего не пишется. __file__ остаётся настоящим
    путём, иначе set-rule.py рядом и mezo_paths не найдутся."""
    src = RFP_PATH.read_text(encoding="utf-8")
    if patch is not None:
        new_src, n = patch(src)
        if n != 1:
            raise AssertionError(f"поломка не нашла ровно одну строку-цель (нашла {n}) — "
                                 f"испытуемое могло измениться, поломку надо пересмотреть")
        src = new_src
    spec = importlib.util.spec_from_file_location(name, str(RFP_PATH))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    exec(compile(src, str(RFP_PATH), "exec"), mod.__dict__)
    return mod


def patch_a(src: str):
    """(А) опора не используется вовсе: сравнение В и П без неё — должны провалиться
    состояния «изменено в пакете» (pack-changed) и «уточнено у вас» (local-changed)."""
    old = ('    """Состояние правила, у которого В (ваш текст) и П (текст пакета) '
           'УЖЕ разные."""\n    if base_sha is None:\n')
    new = old.replace(
        '    if base_sha is None:\n',
        '    base_sha = None  # ПОЛОМКА (А): опора не используется вовсе\n'
        '    if base_sha is None:\n')
    return src.replace(old, new), src.count(old)


def patch_b(src: str):
    """(Б) при взятии опора обновляется у ВСЕХ ключей пакета, а не только у взятого —
    должен провалиться случай «опора обновляется только у взятого»."""
    old = 'adopted_pairs = [(row["rule_set"], key, row["text_sha"]) for key, row in plan]\n'
    new = ('adopted_pairs = [(r["rule_set"], r["rule_key"], r["text_sha"]) '
           'for r in load_pack_rows(pack_conn)]  # ПОЛОМКА (Б): опора всем ключам пакета\n')
    return src.replace(old, new), src.count(old)


def patch_v(src: str):
    """(В) --apply перестаёт быть нужен: apply_gate всегда «можно писать» — должен
    провалиться случай «без --apply ничего не пишет»."""
    old = '    return not apply\n'
    new = '    return False  # ПОЛОМКА (В): --apply перестаёт быть нужен\n'
    return src.replace(old, new), src.count(old)


# ── ПОЛОМКИ карточки #608 (возврат PROTO) ──────────────────────────────────────────────

def patch_scope_off(src: str):
    """(Г) governing_rows перестаёт уважать contour_sets — сравнивает со ВСЕМИ наборами
    пакета разом (старое поведение). Должны провалиться случаи ㊱ (сплошной ноль с
    доменом — набор frontend-spa снова читается как «новое») и ㊲ (без домена — ключи
    ЧУЖИХ наборов снова видны в строках)."""
    old = (
        '    taken = set(contour_sets)\n'
        '    rows_by_set: dict = {}\n'
        '    for row in pack_rows:\n'
        '        if row["rule_set"] in taken:\n'
        '            rows_by_set.setdefault(row["rule_set"], {})[row["rule_key"]] = row\n'
        '    governing: dict = {}\n'
        '    for rs in contour_sets:\n'
        '        governing.update(rows_by_set.get(rs, {}))\n'
        '    return governing\n'
    )
    new = (
        '    # ПОЛОМКА (Г): contour_sets полностью игнорируется — берутся ВСЕ наборы пакета\n'
        '    governing: dict = {}\n'
        '    for row in pack_rows:\n'
        '        governing[row["rule_key"]] = row\n'
        '    return governing\n'
    )
    return src.replace(old, new), src.count(old)


def patch_winner_first(src: str):
    """(Д) при повторении ключа в нескольких взятых наборах побеждает ПЕРВЫЙ встреченный,
    а не последний (домен грузится ПОСЛЕ universal и обязан побеждать). Должен провалиться
    случай ㊳: правка доменного описания перекрытого ключа перестанет быть видна, а правка
    его universal-описания — ложно станет видна."""
    old = (
        '    governing: dict = {}\n'
        '    for rs in contour_sets:\n'
        '        governing.update(rows_by_set.get(rs, {}))\n'
        '    return governing\n'
    )
    new = (
        '    governing: dict = {}\n'
        '    for rs in contour_sets:\n'
        '        for k, v in rows_by_set.get(rs, {}).items():\n'
        '            governing.setdefault(k, v)  # ПОЛОМКА (Д): первый встреченный побеждает\n'
        '    return governing\n'
    )
    return src.replace(old, new), src.count(old)


def patch_infer_off(src: str):
    """(Е) вывод наборов по наличию перестаёт находить доменный набор — всегда отвечает
    «только universal», даже когда у контура есть ключ, которого в universal нет. Должен
    провалиться случай ㊴: контур без meta.pack_rule_sets теряет доменный набор из вывода."""
    old = '    return taken, False\n'
    new = '    return ["universal"], False  # ПОЛОМКА (Е): доменный набор никогда не выводится\n'
    return src.replace(old, new), src.count(old)


def patch_status_blind(src: str):
    """(Ж) карточка #608, повторный возврат PROTO: статус контура не читается вовсе —
    load_circuit_retired_keys() всегда пустой набор. Правило, которое контур сам снял
    (status≠'active'), снова классифицируется как «new», как в живом случае, который
    PROTO нашла: «--state new» звало вернуть осознанно отключённое правило."""
    old = (
        '    active = {k for (k,) in conn.execute("SELECT rule_key FROM rules WHERE '
        'status=\'active\'")}\n'
        '    any_row = {k for (k,) in conn.execute("SELECT DISTINCT rule_key FROM rules")}\n'
        '    return any_row - active\n'
    )
    new = '    return set()  # ПОЛОМКА (Ж): статус контура не читается вовсе\n'
    return src.replace(old, new), src.count(old)


def patch_propose_retire_off(src: str):
    """(З) карточка #608, повторная приёмка, возврат PROTO В1: --propose по ключу,
    который контур сам снял (retired-here), снова отказывает «предлагать нечего» —
    снята ветка, различающая «ключа нет вовсе» от «контур его сам снял». Должен
    провалиться случай ㊺."""
    old = (
        '    v_body = load_circuit_rules(conn).get(key)\n'
        '    if v_body is None:\n'
        '        if circuit_is_retired(conn, key):\n'
        '            return propose_retire(conn, pack_conn, source, key, why, out_path, rule_set_hint)\n'
        '        sys.exit(f"⛔ у контура нет действующего правила «{key}» — предлагать нечего")\n'
    )
    new = (
        '    v_body = load_circuit_rules(conn).get(key)\n'
        '    if v_body is None:\n'
        '        sys.exit(f"⛔ у контура нет действующего правила «{key}» — предлагать нечего")'
        '  # ПОЛОМКА (З): ветка retired-here снята\n'
    )
    return src.replace(old, new), src.count(old)


def patch_show_duplicate_pack_text(src: str):
    """ПОЛОМКА (К) карточка #608, повторная приёмка Н1, замечание COORD (3): возвращает
    старый дефект — в --show на «изменено с обеих сторон» текст пакета печатается ЕЩЁ
    РАЗ (когда-то печатался в начале show_one для ЛЮБОГО состояния и повторно в блоке
    трёх текстов). Место вставки ищем СТРОКОЙ КОММЕНТАРИЯ (не многострочным f-string
    якорем — там перенос строки внутри «\\n» хрупок к посимвольному совпадению) и берём
    ЕЁ ОТСТУП — комментарий стоит на уровне самого print(), а не уровне продолжения
    f-строки на следующей физической строке (тот отступ у Python не значащий)."""
    lines = src.splitlines(keepends=True)
    idx = [i for i, ln in enumerate(lines) if 'УЖЕ напечатаны выше (в начале show_one' in ln]
    if len(idx) != 1:
        return src, len(idx)
    i = idx[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    dup = [indent + 'print("\\n— текст пакета сейчас:")\n', indent + 'print(row["body"])\n']
    return "".join(lines[:i + 1] + dup + lines[i + 1:]), 1


# ── ПОЛОМКИ карточки #614 (G3, PROTO) ───────────────────────────────────────────────

def patch_no_remote_clone(src: str):
    """(М) карточка #614 п.1: meta.template_source (адрес удалёнки) больше не читается —
    find_pack_source() снова отказывает без --source, как ДО правки. Должен провалиться
    случай ㊾ (новый контур из пакета, template_source = адрес удалёнки, без --source)."""
    old = (
        "    src_row = conn.execute(\"SELECT value FROM meta WHERE key='template_source'\").fetchone()\n"
        '    source = ((src_row[0] if src_row else "") or "").strip()\n'
        "    if source:\n"
    )
    new = (
        "    src_row = conn.execute(\"SELECT value FROM meta WHERE key='template_source'\").fetchone()\n"
        '    source = ((src_row[0] if src_row else "") or "").strip()\n'
        "    if False:  # ПОЛОМКА (М): template_source больше не читается\n"
    )
    return src.replace(old, new), src.count(old)


def patch_removed_advice_empty(src: str):
    """(Н) карточка #614 п.2: совет у разряда «снято в пакете» — снова пустой "—",
    как ДО правки. Должен провалиться случай ㊿а (совет несёт оба пути)."""
    old = (
        '    "removed": "пакет его больше не несёт — снять у себя (set-rule.py, см. готовую команду "\n'
        '              "ниже) или остаться и записать отказ (--skip); по умолчанию не трогаем",\n'
    )
    new = '    "removed": "—",  # ПОЛОМКА (Н): совет снова пуст\n'
    return src.replace(old, new), src.count(old)


def patch_removed_skip_broken(src: str):
    """(О) карточка #614 п.2: --skip снова отказывает у разряда «снято в пакете» — ветка,
    принимающая СНЯТУЮ строку, снята (старое поведение skip_key). Должен провалиться
    случай ㊿б (--skip у removed-ключа пишет и отпускает)."""
    old = (
        '    active_rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key and not r["removed_at"]]\n'
        "    if active_rows:\n"
        "        row = pick_rule_set(active_rows, key, rule_set_hint)\n"
        "    else:\n"
        '        removed_rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key and r["removed_at"]]\n'
        "        if not removed_rows:\n"
        '            sys.exit(f"⛔ ключа «{key}» нет в пакете вовсе — отказываться не от чего")\n'
        "        row = pick_removed_rule_set(removed_rows, key, rule_set_hint)\n"
    )
    new = (
        '    rows = [r for r in load_pack_rows(pack_conn) if r["rule_key"] == key and not r["removed_at"]]\n'
        "    if not rows:\n"
        '        sys.exit(f"⛔ у пакета нет действующего текста «{key}», чтобы от него отказаться")'
        "  # ПОЛОМКА (О)\n"
        "    row = pick_rule_set(rows, key, rule_set_hint)\n"
    )
    return src.replace(old, new), src.count(old)


def patch_removed_state_ignores_skip(src: str):
    """(П) карточка #614 п.2: build_rows() снова не смотрит skip_map у снятых строк —
    записанный --skip не отпускает нагара, ключ навсегда «removed». Должен провалиться
    случай ㊿в (после --skip строка становится «skipped», не «removed»)."""
    old = (
        "        elif row[\"removed_at\"]:\n"
        "            # КАРТОЧКА #614 ②: --skip годится и здесь («пакет его больше не несёт, а я\n"
        "            # держу и дальше») — тот же отпечаток-ключ, что и у живого текста пакета\n"
        "            # (skip_map хранит sha ПОСЛЕДНЕЙ версии пакета перед снятием); отпустится\n"
        "            # само, если этот отпечаток когда-нибудь перестанет совпадать (симметрично\n"
        "            # обычному «skipped» ниже).\n"
        "            if skip_map.get(f\"{rule_set}/{key}\") == row[\"text_sha\"]:\n"
        "                state = \"skipped\"\n"
        "            else:\n"
        "                state = \"removed\"\n"
    )
    new = (
        "        elif row[\"removed_at\"]:\n"
        "            state = \"removed\"  # ПОЛОМКА (П): skip_map больше не смотрим\n"
    )
    return src.replace(old, new), src.count(old)

def patch_no_ready_command(src: str):
    """(Р) карточка #614, возврат COORD (ветка «а», 2026-09-14 17:58 UTC): готовая
    команда «--source <папка с клоном пакета GORDI>» в отказе find_pack_source() при
    НЕЧИТАЕМОМ адресе убрана — снова только диагноз update-tools.py, без совета, что
    делать роли ИМЕННО ЭТОГО инструмента. Должны провалиться случаи ㊾в′ и ㊾г (готовую
    команду ждут оба).
    """
    old = (
        '            reason = e.code if isinstance(e.code, str) else str(e.code)\n'
        '            sys.exit(\n'
        '                f"{reason}\\n"\n'
        '                "   rules-from-pack.py: источник в meta.template_source не читается — "\n'
        '                "укажи явно: --source <папка с клоном пакета GORDI>"\n'
        '            )\n'
    )
    new = (
        '            reason = e.code if isinstance(e.code, str) else str(e.code)\n'
        '            sys.exit(reason)  # ПОЛОМКА (Р): готовая команда убрана\n'
    )
    return src.replace(old, new), src.count(old)


def patch_merge_dry_run_label(src: str):
    """ПОЛОМКА (Л) карточка #608, повторная приёмка Н1, замечание COORD (4): холостой
    --merge снова показывает подпись-заглушку «<сведённый текст из --file>» вместо
    настоящего пути из --file — тот самый прежний дефект (роль не видела, какой именно
    файл set-rule.py возьмёт)."""
    old = 'body_file_label=str(file_path)))\n'
    new = 'body_file_label="<сведённый текст из --file>"))  # ПОЛОМКА (Л)\n'
    return src.replace(old, new), src.count(old)


def patch_propose_section_empty(src: str):
    """(С) НАХОДКА PROTO 24.09.2026, случай ⑰б: раздел «## ПРЕДЛОЖЕНИЕ» письма остаётся
    ЗАГОЛОВКОМ, но текст под ним пропадает. Ищет её РОВНО ⑰б: случай ⑰а смотрит на
    заголовок подстрокой («## ПРЕДЛОЖЕНИЕ» в тексте есть — и остаётся), а gordi-issue.py
    смотрит текст ПОД заголовком (её же проверка непустоты разделов) и на пустом теле
    отказывает — что и доказывает: ⑰б судит ТЕЛО, а не только наличие базы координатора."""
    old = (
        '        f"## ПРЕДЛОЖЕНИЕ\\n"\n'
        '        f"заменить текст правила «{key}» в наборе «{row[\'rule_set\']}» на текст контура. "\n'
        '        f"Цена: строк добавится {added}, уберётся {removed_n} (по построчному различию).\\n"\n'
    )
    new = (
        '        f"## ПРЕДЛОЖЕНИЕ\\n"\n'
        '        f""  # ПОЛОМКА (С): текст раздела пропал, заголовок остался\n'
    )
    return src.replace(old, new), src.count(old)


# ── СХЕМА (та же, что у живой mezosync.db, — только то, что нужно испытуемому) ──────

CIRCUIT_SCHEMA = """
CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT, rule_key TEXT NOT NULL UNIQUE, body TEXT NOT NULL,
    locked_by TEXT NOT NULL DEFAULT 'coord', version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')), updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    basis TEXT, authorized TEXT, source_ref TEXT, expiry_kind TEXT, expiry_cond TEXT,
    status TEXT NOT NULL DEFAULT 'active', revoked_at TEXT, revoked_by TEXT, revoked_reason TEXT,
    superseded_by INTEGER, skill_delivery TEXT
);
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')), actor_role TEXT NOT NULL,
    action TEXT NOT NULL, target TEXT NOT NULL, diff_md TEXT);
CREATE TABLE roles (role TEXT PRIMARY KEY, lifecycle TEXT, lifecycle_reason TEXT);
"""

PACK_SCHEMA = """
CREATE TABLE pack_rules (rule_set TEXT, rule_key TEXT, body TEXT, locked_by TEXT, text_sha TEXT,
    pack_updated_at TEXT, pack_commit TEXT, removed_at TEXT, PRIMARY KEY (rule_set, rule_key));
CREATE TABLE pack_rules_history (rule_set TEXT, rule_key TEXT, text_sha TEXT, body TEXT,
    locked_by TEXT, first_commit TEXT, first_seen_at TEXT, replaced_at TEXT,
    PRIMARY KEY (rule_set, rule_key, text_sha));
CREATE TABLE pack_rules_meta (key TEXT PRIMARY KEY, value TEXT);
"""

PREFIX = "zzz-bite-rfp-"   # приметный ключ фикстур — чтобы отличить от настоящих правил
RULE_SET = "universal"


def make_circuit_db(path: Path, rules=(), meta=None, roles=()) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(CIRCUIT_SCHEMA)
    for r in rules:
        conn.execute(
            "INSERT INTO rules(rule_key, body, locked_by, expiry_kind, expiry_cond, "
            "basis, authorized, source_ref, status) VALUES (?,?,?,?,?,?,?,?,?)",
            (r["rule_key"], r["body"], r.get("locked_by", "coord"), r.get("expiry_kind"),
             r.get("expiry_cond"), r.get("basis"), r.get("authorized"), r.get("source_ref"),
             r.get("status", "active")))
    for k, v in (meta or {}).items():
        conn.execute("INSERT INTO meta(key, value) VALUES (?,?)", (k, v))
    for role, lifecycle, reason in roles:
        conn.execute("INSERT INTO roles(role, lifecycle, lifecycle_reason) VALUES (?,?,?)",
                     (role, lifecycle, reason))
    conn.commit()
    conn.close()


def make_pack_db(path: Path, rows=(), history=(), meta=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.executescript(PACK_SCHEMA)
    for r in rows:
        conn.execute("INSERT INTO pack_rules VALUES (?,?,?,?,?,?,?,?)",
                     (r["rule_set"], r["rule_key"], r["body"], r.get("locked_by", "coord"),
                      r["text_sha"], r.get("pack_updated_at", "2026-09-14 00:00:00 UTC"),
                      r.get("pack_commit", "c000000"), r.get("removed_at")))
    for h in history:
        conn.execute("INSERT INTO pack_rules_history VALUES (?,?,?,?,?,?,?,?)", h)
    for k, v in (meta or {"schema_version": "1"}).items():
        conn.execute("INSERT INTO pack_rules_meta VALUES (?,?)", (k, v))
    conn.commit()
    conn.close()


# ── ФИКСТУРА: НАБОРЫ ПРАВИЛ ПАКЕТА (карточка #608, возврат PROTO) ─────────────────────
# Контур из ДВУХ взятых наборов (universal + data-platform, с тремя перекрывающимися
# ключами — доменное описание побеждает, ровно как в живой сборке) плюс НЕВЗЯТЫЙ третий
# набор (frontend-spa) — чтобы отличить «контур это знает» от «контур этого не брал».
RS_PREFIX = "zzz-bite-rfp-rs-"


def build_rule_sets_fixture(root: Path, text_sha, with_domain: bool, record_meta: bool = True):
    """Возвращает (circuit_db, pack_dir, keys) — keys: короткое имя -> полный rule_key."""
    keys = {short: RS_PREFIX + short for short in ("u1", "ov1", "ov2", "ov3", "d1", "f1")}
    u1, ov1, ov2, ov3, d1, f1 = (keys[s] for s in ("u1", "ov1", "ov2", "ov3", "d1", "f1"))

    universal_text = {u1: "universal U1\n",
                      ov1: "universal OV1 (перекрыто доменом)\n",
                      ov2: "universal OV2 (перекрыто доменом)\n",
                      ov3: "universal OV3 (перекрыто доменом)\n"}
    domain_text = {ov1: "domain OV1\n", ov2: "domain OV2\n", ov3: "domain OV3\n",
                   d1: "domain D1\n"}
    frontend_text = {f1: "frontend F1\n"}

    pack_rows = []
    for rule_set, texts in ((RULE_SET, universal_text), ("data-platform", domain_text),
                            ("frontend-spa", frontend_text)):
        for key, body in texts.items():
            pack_rows.append({"rule_set": rule_set, "rule_key": key, "body": body,
                             "text_sha": text_sha(body)})

    circuit_rules = [{"rule_key": u1, "body": universal_text[u1]}]
    base_map = {f"{RULE_SET}/{u1}": text_sha(universal_text[u1])}
    if with_domain:
        for k in (ov1, ov2, ov3):
            circuit_rules.append({"rule_key": k, "body": domain_text[k]})
            base_map[f"data-platform/{k}"] = text_sha(domain_text[k])
        circuit_rules.append({"rule_key": d1, "body": domain_text[d1]})
        base_map[f"data-platform/{d1}"] = text_sha(domain_text[d1])
        pack_rule_sets = ["universal", "data-platform"]
    else:
        # БЕЗ ДОМЕНА: universal.sql грузится ВСЕГДА и в одиночку, поэтому у контура есть
        # свои universal-версии OV1..OV3 (не доменные) — d1 и f1 не грузит никто.
        for k in (ov1, ov2, ov3):
            circuit_rules.append({"rule_key": k, "body": universal_text[k]})
            base_map[f"{RULE_SET}/{k}"] = text_sha(universal_text[k])
        pack_rule_sets = ["universal"]

    circuit_db = root / "circuit.db"
    pack_dir = root / "pack"
    meta = {"template_checkout": str(pack_dir), "pack_rules_base": json.dumps(base_map),
            "pack_rules_skipped": "{}"}
    if record_meta:
        meta["pack_rule_sets"] = json.dumps(pack_rule_sets)
    make_circuit_db(circuit_db, rules=circuit_rules, meta=meta,
                    roles=[("COORD", "alive", "координатор контура; в живом реестре")])
    make_pack_db(pack_dir / "rules" / "pack-rules.db", rows=pack_rows)
    return circuit_db, pack_dir, keys


# ── ФИКСТУРА: КОНТУР САМ СНЯЛ ПРАВИЛО (карточка #608, возврат PROTO) ──────────────────
# ПОВОД: «--state new» на живом контуре звал вернуть правило, которое контур сам отключил
# (status≠'active') — инструмент судил его по ТЕКСТУ пакета, статус контура не спрашивал.
RETIRED_PREFIX = "zzz-bite-rfp-retired-"


def build_retired_fixture(root: Path, text_sha):
    """Один ключ, изолированная фикстура: у контура он ЕСТЬ, но status='revoked'; у пакета
    он ЖИВОЙ (не снят). Тексты РАЗНЫЕ нарочно — состояние обязано быть «снято у вас» при
    ЛЮБОМ соотношении текстов, не только при совпадении. Возвращает (circuit_db, pack_dir, key)."""
    key = RETIRED_PREFIX + "k1"
    circuit_body = "текст контура, до отключения\n"
    pack_body = "текст пакета сейчас — контур его не увидит, пока сам не решит вернуть\n"
    circuit_db = root / "circuit.db"
    pack_dir = root / "pack"
    make_circuit_db(
        circuit_db,
        rules=[{"rule_key": key, "body": circuit_body, "status": "revoked"}],
        meta={"template_checkout": str(pack_dir), "pack_rule_sets": json.dumps(["universal"])},
        roles=[("COORD", "alive", "координатор контура; в живом реестре")])
    make_pack_db(pack_dir / "rules" / "pack-rules.db",
                rows=[{"rule_set": RULE_SET, "rule_key": key, "body": pack_body,
                       "text_sha": text_sha(pack_body)}])
    return circuit_db, pack_dir, key


# ── ФИКСТУРА: «СНЯТО В ПАКЕТЕ» (карточка #614 ②, G3/PROTO) ─────────────────────────────
REMOVED614_PREFIX = "zzz-bite-rfp-removed614-"


def build_removed_fixture(root: Path, text_sha):
    """Один ключ: пакет СНЯЛ его (removed_at непуст), контур держит ДЕЙСТВУЮЩИЙ текст —
    состояние «removed» («снято в пакете»). Возвращает (circuit_db, pack_dir, key)."""
    key = REMOVED614_PREFIX + "k1"
    circuit_body = "текст у нас, живой\n"
    pack_body = "текст пакета — последняя версия перед снятием\n"
    circuit_db = root / "circuit.db"
    pack_dir = root / "pack"
    make_circuit_db(
        circuit_db,
        rules=[{"rule_key": key, "body": circuit_body}],
        meta={"template_checkout": str(pack_dir), "pack_rules_base": "{}",
              "pack_rules_skipped": "{}", "pack_rule_sets": json.dumps(["universal"])},
        roles=[("COORD", "alive", "координатор контура; в живом реестре")])
    make_pack_db(pack_dir / "rules" / "pack-rules.db",
                rows=[{"rule_set": RULE_SET, "rule_key": key, "body": pack_body,
                       "text_sha": text_sha(pack_body), "pack_commit": "removed0614",
                       "removed_at": "2026-09-13 00:00:00 UTC"}])
    return circuit_db, pack_dir, key


# ── ФИКСТУРА: «АДРЕС УДАЛЁНКИ» В meta.template_source (карточка #614 ①, G3/PROTO) ──────
# Реальный git-репозиторий, построенный ЛОКАЛЬНО (никакой сети) — task-g3-614.md п.3:
# «адрес — локальный file://-адрес или путь к голому клону в песочнице, НЕ сеть».
REMOTE614_PREFIX = "zzz-bite-rfp-remote614-"


def build_remote_pack_fixture(root: Path, text_sha):
    """Пакет-репозиторий (git init + commit, локально) + контур, у которого
    meta.template_source — file://-адрес ЭТОГО репозитория, а meta.template_checkout
    отсутствует вовсе (ровно то, что пишет init-group.py настоящему новому контуру:
    `git remote get-url origin`, а не папка клона). Возвращает (circuit_db, file_url, key)."""
    pack_repo = root / "pack-origin"
    pack_repo.mkdir(parents=True)
    git_env = dict(os.environ, GIT_AUTHOR_NAME="bite614", GIT_AUTHOR_EMAIL="bite@614",
                  GIT_COMMITTER_NAME="bite614", GIT_COMMITTER_EMAIL="bite@614")
    subprocess.run(["git", "init", "-q"], cwd=str(pack_repo), check=True, env=git_env)
    (pack_repo / "rules").mkdir()
    key = REMOTE614_PREFIX + "k1"
    body = "universal текст, пришедший клоном\n"
    make_pack_db(pack_repo / "rules" / "pack-rules.db",
                rows=[{"rule_set": RULE_SET, "rule_key": key, "body": body,
                       "text_sha": text_sha(body), "pack_commit": "remote0614"}])
    subprocess.run(["git", "add", "-A"], cwd=str(pack_repo), check=True, env=git_env)
    subprocess.run(["git", "commit", "-q", "-m", "bite #614 fixture"],
                   cwd=str(pack_repo), check=True, env=git_env)

    circuit_db = root / "circuit.db"
    file_url = "file:///" + str(pack_repo.resolve()).replace("\\", "/")
    make_circuit_db(circuit_db, rules=[], meta={"template_source": file_url},
                    roles=[("COORD", "alive", "координатор контура; в живом реестре")])
    return circuit_db, file_url, key


def build_sandboxed_tool(dest_dir: Path) -> Path:
    """Копия испытуемого инструмента (и mezo_paths.py/mezo_stand.py — прямых соседей по
    импорту, без них не запустится) в каталог ЗАВЕДОМО вне <КОНТУР> — карточка #608,
    возврат PROTO В2: путь к gordi-issue.py обязан резолвиться от РАСПОЛОЖЕНИЯ ЭТОЙ КОПИИ,
    а не быть впечатанным путём автора.
    ⚡ КАРТОЧКА #614: rules-from-pack.py теперь безусловно зовёт `import mezo_stand`
    (временный клон источника убирается тем же приёмом, что у update-tools.py) — сосед
    добавлен сюда следом, иначе копия падает `ModuleNotFoundError` ДО того, как дело
    доходит до --propose, который вообще этот путь не трогает (--source задан явно)."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    tool_copy = dest_dir / "rules-from-pack.py"
    tool_copy.write_text(RFP_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    (dest_dir / "mezo_paths.py").write_text(
        (RFP_PATH.parent / "mezo_paths.py").read_text(encoding="utf-8"), encoding="utf-8")
    mezo_stand_src = RFP_PATH.parent / "mezo_stand.py"
    if mezo_stand_src.exists():
        (dest_dir / "mezo_stand.py").write_text(
            mezo_stand_src.read_text(encoding="utf-8"), encoding="utf-8")
    return tool_copy


def snapshot(circuit_db: Path):
    conn = sqlite3.connect(f"file:{circuit_db.as_posix()}?mode=ro", uri=True)
    rules = conn.execute("SELECT rule_key, body, locked_by, version, status FROM rules "
                         "ORDER BY rule_key").fetchall()
    meta = dict(conn.execute("SELECT key, value FROM meta ORDER BY key").fetchall())
    conn.close()
    return rules, meta


# ── СТРОИТЕЛЬ ФИКСТУРЫ: ДЕВЯТЬ СОСТОЯНИЙ + ОПОРА ПО ИСТОРИИ ─────────────────────────

def build_state_fixture(root: Path, text_sha):
    """Один пакет + один контур, целиком покрывающие девять состояний плюс опору,
    найденную по истории пакета (а не по meta). Возвращает:
        circuit_db, pack_dir, expected (ключ -> состояние), only_yours_keys (set)
    """
    circuit_rules, pack_rows, history_rows = [], [], []
    base_map, skip_map, expected = {}, {}, {}
    only_yours = set()

    def key_of(short):
        return PREFIX + short

    def add(short, state, v_body, p_body, o_body=None, removed=False, skip_current=False,
            base_via_history=False):
        k = key_of(short)
        if v_body is not None:
            circuit_rules.append({"rule_key": k, "body": v_body})
        if p_body is not None:
            pack_rows.append({
                "rule_set": RULE_SET, "rule_key": k, "body": p_body, "text_sha": text_sha(p_body),
                "pack_updated_at": f"2026-09-{10 + len(pack_rows):02d} 00:00:00 UTC",
                "pack_commit": f"c{len(pack_rows):06d}", "removed_at": ("2026-09-13 00:00:00 UTC"
                                                                        if removed else None),
            })
        if o_body is not None:
            if base_via_history:
                history_rows.append((RULE_SET, k, text_sha(o_body), o_body, "coord",
                                     "cold000", "2026-01-01 00:00:00 UTC",
                                     "2026-02-01 00:00:00 UTC"))
            else:
                base_map[f"{RULE_SET}/{k}"] = text_sha(o_body)
        if skip_current:
            skip_map[f"{RULE_SET}/{k}"] = text_sha(p_body)
        if state is None:
            only_yours.add(k)
        else:
            expected[k] = state

    add("same", "same", "text A\n", "text A\n")
    add("pack-changed", "pack-changed", "old text\n", "new pack text\n", o_body="old text\n")
    add("local-changed", "local-changed", "my edit\n", "orig text\n", o_body="orig text\n")
    add("both-changed", "both-changed", "my edit\n", "their edit\n", o_body="orig base\n")
    add("no-base", "no-base", "my lone edit\n", "their lone edit\n")
    add("removed", "removed", "still have it\n", "was here\n", removed=True)
    add("skipped", "skipped", "my edit\n", "current pack text\n", skip_current=True)
    add("new", "new", None, "brand new pack text\n")
    add("only-yours", None, "mine, pack never heard of this\n", None)
    add("history-base", "pack-changed", "old text v2\n", "new pack text v2\n",
        o_body="old text v2\n", base_via_history=True)

    circuit_db = root / "circuit.db"
    pack_dir = root / "pack"
    make_circuit_db(circuit_db,
                    rules=circuit_rules,
                    meta={"template_checkout": str(pack_dir),
                          "pack_rules_base": json.dumps(base_map),
                          "pack_rules_skipped": json.dumps(skip_map)},
                    roles=[("COORD", "alive", "координатор контура; в живом реестре")])
    make_pack_db(pack_dir / "rules" / "pack-rules.db", rows=pack_rows, history=history_rows)
    return circuit_db, pack_dir, expected, only_yours


# ── ГЛАВНЫЙ ПРОГОН ───────────────────────────────────────────────────────────────────

def main() -> int:
    ok = True
    live_db = mezo_paths.live_db(__file__)

    def fake_key_count_live():
        conn = sqlite3.connect(f"file:{live_db.as_posix()}?mode=ro", uri=True)
        try:
            n_rules = conn.execute(
                "SELECT COUNT(*) FROM rules WHERE rule_key LIKE ?", (PREFIX + "%",)).fetchone()[0]
            meta_rows = conn.execute(
                "SELECT value FROM meta WHERE key IN ('pack_rules_base','pack_rules_skipped')"
            ).fetchall()
            n_meta = sum(1 for (v,) in meta_rows if PREFIX in (v or ""))
            return n_rules, n_meta
        finally:
            conn.close()

    before_live = fake_key_count_live()

    root = mezo_stand.new("bite-rfp-")
    mod = load_rfp()

    # ── ①–⑩ девять состояний + опора по истории ────────────────────────────────
    circuit_db, pack_dir, expected, only_yours = build_state_fixture(root / "states", mod.text_sha)
    conn = sqlite3.connect(f"file:{circuit_db.as_posix()}?mode=ro", uri=True)
    pack_conn = mod.open_pack_db(pack_dir)
    circuit_rules = mod.load_circuit_rules(conn)
    pack_rows_loaded = mod.load_pack_rows(pack_conn)
    base_map_loaded = mod.load_meta_map(conn, "pack_rules_base")
    skip_map_loaded = mod.load_meta_map(conn, "pack_rules_skipped")
    history_has = mod.make_history_has(pack_conn)
    contour_sets_1, _ = mod.resolve_contour_rule_sets(conn, circuit_rules, pack_rows_loaded)
    rows, only_yours_got = mod.build_rows(circuit_rules, pack_rows_loaded, base_map_loaded,
                                          skip_map_loaded, history_has, contour_sets_1,
                                          mod.load_circuit_retired_keys(conn))
    got_state = {r["rule_key"]: r["state"] for r in rows}
    got_base_source = {r["rule_key"]: r["base_source"] for r in rows}

    NAMES = {"same": "① совпадает (same)", "pack-changed": "② изменено в пакете (pack-changed)",
             "local-changed": "③ уточнено у вас (local-changed)",
             "both-changed": "④ изменено с обеих сторон (both-changed)",
             "no-base": "⑤ расходится, опоры нет (no-base)", "removed": "⑥ снято в пакете (removed)",
             "skipped": "⑦ отказались (skipped)", "new": "⑧ новое в пакете (new)"}
    for short, title in NAMES.items():
        key = PREFIX + short
        ok &= case(title, got_state.get(key) == expected[key],
                  f"ключ {key}: ждали «{expected[key]}», получили «{got_state.get(key)}»")

    ok &= case("⑨ только у вас — не входит в строки списка, входит в итог",
              PREFIX + "only-yours" not in got_state and PREFIX + "only-yours" in only_yours_got,
              f"в строках {PREFIX + 'only-yours' in got_state} (ждём False), "
              f"в «только у вас» {PREFIX + 'only-yours' in only_yours_got} (ждём True)")

    key_h = PREFIX + "history-base"
    ok &= case("⑩ опора найдена по истории пакета (meta без записи для этого ключа)",
              got_state.get(key_h) == "pack-changed" and got_base_source.get(key_h) == "history",
              f"состояние «{got_state.get(key_h)}» (ждём pack-changed), "
              f"опора взята из «{got_base_source.get(key_h)}» (ждём history)")

    # ── ⑪ --show: три текста и «опора найдена по истории» строкой ─────────────────
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        mod.cmd_show(conn, pack_conn, key_h, base_map_loaded, None)
    shown = buf.getvalue()
    ok &= case("⑪ --show печатает опору, пакет и ваш текст, и находку опоры по истории строкой",
              "old text v2" in shown and "new pack text v2" in shown
              and "опора найдена по истории пакета" in shown,
              f"длина вывода {len(shown)}; есть опора {'old text v2' in shown}, "
              f"пакет {'new pack text v2' in shown}, находка {'опора найдена по истории' in shown}")
    conn.close()
    pack_conn.close()

    # ── ⑫ --adopt БЕЗ --apply ничего не пишет ──────────────────────────────────────
    circuit_db2, pack_dir2, expected2, _ = build_state_fixture(root / "adopt-dry", mod.text_sha)
    before2 = snapshot(circuit_db2)
    conn2 = sqlite3.connect(f"file:{circuit_db2.as_posix()}?mode=ro", uri=True)
    pack_conn2 = mod.open_pack_db(pack_dir2)
    base2 = mod.load_meta_map(conn2, "pack_rules_base")
    mod.adopt_keys(conn2, circuit_db2, pack_conn2, base2, [PREFIX + "pack-changed"], None,
                   None, False, "bite")
    conn2.close(); pack_conn2.close()
    after2 = snapshot(circuit_db2)
    ok &= case("⑫ --adopt БЕЗ --apply ничего не пишет", before2 == after2,
              "снимок таблиц rules/meta до и после холостого прогона совпал" if before2 == after2
              else "снимок ИЗМЕНИЛСЯ на холостом прогоне — это и есть беда")

    # ── ⑬ --adopt С --apply: пишет через set-rule.py, опора — ТОЛЬКО у взятого ──────
    circuit_db3, pack_dir3, expected3, _ = build_state_fixture(root / "adopt-apply", mod.text_sha)
    conn3 = sqlite3.connect(f"file:{circuit_db3.as_posix()}?mode=rw", uri=True)
    pack_conn3 = mod.open_pack_db(pack_dir3)
    base3 = mod.load_meta_map(conn3, "pack_rules_base")
    target_key = PREFIX + "pack-changed"
    rc13 = mod.adopt_keys(conn3, circuit_db3, pack_conn3, base3, [target_key], None,
                          "владелец, приёмка bite-rules-from-pack, тест ⑬", True, "bite")
    new_body = conn3.execute("SELECT body FROM rules WHERE rule_key=?", (target_key,)).fetchone()
    base_after = mod.load_meta_map(conn3, "pack_rules_base")
    other_key = f"{RULE_SET}/{PREFIX}both-changed"   # O≠П у этого ключа — годится ловить чужую правку
    ok &= case("⑬а --adopt --apply переносит ИМЕННО текст пакета в правило контура",
              # set-rule.py сам обрезает края текста (.strip()) — это его штатное
              # поведение, не наша беда; сверяем с тем же обрезанием.
              rc13 == 0 and new_body and new_body[0] == "new pack text\n".strip(),
              f"код {rc13}, тело контура теперь: {new_body[0] if new_body else None!r}")
    ok &= case("⑬б опора обновилась ТОЛЬКО у взятого ключа, соседей не тронула",
              base_after.get(f"{RULE_SET}/{target_key}") == mod.text_sha("new pack text\n")
              and base_after.get(other_key) == base3.get(other_key),
              f"опора взятого = {base_after.get(f'{RULE_SET}/{target_key}')!r}; "
              f"опора соседа не изменилась: {base_after.get(other_key) == base3.get(other_key)}")
    conn3.close(); pack_conn3.close()

    # ── ⑭ правило, залоченное владельцем, без --word отказывает ────────────────────
    circuit_db4, pack_dir4, _, _ = build_state_fixture(root / "owner-lock", mod.text_sha)
    # долочим соответствующее правило ПАКЕТА владельцем прямой записью в фикстуру
    lock_key = PREFIX + "pack-changed"
    pconn = sqlite3.connect(str(pack_dir4 / "rules" / "pack-rules.db"))
    pconn.execute("UPDATE pack_rules SET locked_by='owner' WHERE rule_key=?", (lock_key,))
    pconn.commit(); pconn.close()
    before4 = snapshot(circuit_db4)
    conn4 = sqlite3.connect(f"file:{circuit_db4.as_posix()}?mode=rw", uri=True)
    pack_conn4 = mod.open_pack_db(pack_dir4)
    base4 = mod.load_meta_map(conn4, "pack_rules_base")
    refused = False
    try:
        mod.adopt_keys(conn4, circuit_db4, pack_conn4, base4, [lock_key], None, None, True, "bite")
    except SystemExit:
        refused = True
    conn4.close(); pack_conn4.close()
    after4 = snapshot(circuit_db4)
    ok &= case("⑭ правило, залоченное владельцем в пакете, без --word отказывает и не пишет",
              refused and before4 == after4,
              f"отказ выброшен: {refused}; база не изменилась: {before4 == after4}")

    # ── ⑮ --merge --apply: тело = файл, опора = текущая версия пакета ───────────────
    circuit_db5, pack_dir5, _, _ = build_state_fixture(root / "merge-apply", mod.text_sha)
    conn5 = sqlite3.connect(f"file:{circuit_db5.as_posix()}?mode=rw", uri=True)
    pack_conn5 = mod.open_pack_db(pack_dir5)
    base5 = mod.load_meta_map(conn5, "pack_rules_base")
    merge_key_name = PREFIX + "both-changed"
    merged_file = root / "merged-both-changed.txt"
    merged_file.write_text("сведённый вручную текст\n", encoding="utf-8")
    rc15 = mod.merge_key(conn5, circuit_db5, pack_conn5, base5, merge_key_name, None,
                         str(merged_file), "координатор, приёмка, тест ⑮", True, "bite")
    merged_body = conn5.execute("SELECT body FROM rules WHERE rule_key=?",
                                (merge_key_name,)).fetchone()
    pack_sha_now = mod.text_sha("their edit\n")   # текст пакета этого ключа в фикстуре
    base_after5 = mod.load_meta_map(conn5, "pack_rules_base")
    ok &= case("⑮ --merge --apply пишет файл-текст в правило и ставит опору = версии пакета",
              # set-rule.py сам обрезает края текста (.strip()) — сверяем с тем же обрезанием
              rc15 == 0 and merged_body and merged_body[0] == "сведённый вручную текст\n".strip()
              and base_after5.get(f"{RULE_SET}/{merge_key_name}") == pack_sha_now,
              f"код {rc15}, тело {merged_body[0] if merged_body else None!r}, "
              f"опора обновлена: {base_after5.get(f'{RULE_SET}/{merge_key_name}') == pack_sha_now}")
    conn5.close(); pack_conn5.close()

    # ── ⑯ --skip --apply: отказ записан, и снимается сам при смене текста пакета ────
    circuit_db6, pack_dir6, _, _ = build_state_fixture(root / "skip-apply", mod.text_sha)
    skip_key_name = PREFIX + "no-base"
    conn6 = sqlite3.connect(f"file:{circuit_db6.as_posix()}?mode=rw", uri=True)
    pack_conn6 = mod.open_pack_db(pack_dir6)
    skip6 = mod.load_meta_map(conn6, "pack_rules_skipped")
    rc16 = mod.skip_key(conn6, pack_conn6, skip6, skip_key_name, None,
                        "владелец, приёмка, тест ⑯", True)
    conn6.close(); pack_conn6.close()

    conn6b = sqlite3.connect(f"file:{circuit_db6.as_posix()}?mode=ro", uri=True)
    pack_conn6b = mod.open_pack_db(pack_dir6)
    circuit6 = mod.load_circuit_rules(conn6b)
    pack6 = mod.load_pack_rows(pack_conn6b)
    base6 = mod.load_meta_map(conn6b, "pack_rules_base")
    skip6b = mod.load_meta_map(conn6b, "pack_rules_skipped")
    cs6b, _ = mod.resolve_contour_rule_sets(conn6b, circuit6, pack6)
    rows6, _ = mod.build_rows(circuit6, pack6, base6, skip6b, mod.make_history_has(pack_conn6b), cs6b,
                              mod.load_circuit_retired_keys(conn6b))
    state_after_skip = next(r["state"] for r in rows6 if r["rule_key"] == skip_key_name)
    conn6b.close(); pack_conn6b.close()

    # пакет меняет текст — отказ должен «отпустить» ключ обратно к обычному сравнению
    pconn6 = sqlite3.connect(str(pack_dir6 / "rules" / "pack-rules.db"))
    new_pack_text = "their lone edit v2\n"
    pconn6.execute("UPDATE pack_rules SET body=?, text_sha=? WHERE rule_key=?",
                   (new_pack_text, mod.text_sha(new_pack_text), skip_key_name))
    pconn6.commit(); pconn6.close()
    conn6c = sqlite3.connect(f"file:{circuit_db6.as_posix()}?mode=ro", uri=True)
    pack_conn6c = mod.open_pack_db(pack_dir6)
    circuit6c = mod.load_circuit_rules(conn6c)
    pack6c = mod.load_pack_rows(pack_conn6c)
    base6c = mod.load_meta_map(conn6c, "pack_rules_base")
    skip6c = mod.load_meta_map(conn6c, "pack_rules_skipped")
    cs6c, _ = mod.resolve_contour_rule_sets(conn6c, circuit6c, pack6c)
    rows6c, _ = mod.build_rows(circuit6c, pack6c, base6c, skip6c, mod.make_history_has(pack_conn6c), cs6c,
                               mod.load_circuit_retired_keys(conn6c))
    state_after_pack_moved = next(r["state"] for r in rows6c if r["rule_key"] == skip_key_name)
    conn6c.close(); pack_conn6c.close()

    ok &= case("⑯ --skip --apply: состояние «skipped», затем пакет меняет текст — отказ отпускает",
              rc16 == 0 and state_after_skip == "skipped" and state_after_pack_moved != "skipped",
              f"код {rc16}; сразу после отказа: «{state_after_skip}» (ждём skipped); "
              f"после смены текста пакета: «{state_after_pack_moved}» (ждём НЕ skipped)")

    # ── ⑰ --propose: три непустых раздела, без путей машины, и gordi-issue.py --dry-run ─
    circuit_db7, pack_dir7, _, _ = build_state_fixture(root / "propose", mod.text_sha)
    conn7 = sqlite3.connect(f"file:{circuit_db7.as_posix()}?mode=ro", uri=True)
    pack_conn7 = mod.open_pack_db(pack_dir7)
    out_file = root / "proposal.md"
    mod.propose(conn7, pack_conn7, pack_dir7, PREFIX + "local-changed",
               "у нас переписано понятнее", str(out_file), None)
    proposal_text = out_file.read_text(encoding="utf-8")
    sections_ok = all(f"## {s}" in proposal_text for s in ("ЗАМЕР", "КЛАСС", "ПРЕДЛОЖЕНИЕ"))
    no_machine_paths = not mod.MACHINE_PATH.search(proposal_text)
    ok &= case("⑰а --propose пишет файл с тремя непустыми разделами, без путей машины",
              sections_ok and no_machine_paths,
              f"разделы есть: {sections_ok}; путей машины нет: {no_machine_paths}")

    # ⚠️ НАХОДКА PROTO (24.09.2026): gordi-issue.py судит ПИСАТЕЛЯ раньше тела письма
    # (_writer_gate → _find_coordinator, карточка #645) — на стенде БЕЗ mezosync.db это
    # не отказ по телу, а OperationalError «база координатора недоступна», и ⑰б красил
    # бы по ЧУЖОЙ причине, не по той, ради которой написан («испытываем не то, что
    # чиним»). Свой ПОДСТЕНД с согласованным снимком живой базы (mezo_stand.snapshot_db —
    # резервное копирование sqlite, не голый файл: карточка #505, WAL честно перенесён)
    # даёт координатора найтись, писатель — настоящий, а дальше судит уже ТЕЛО (поломка
    # (С) ниже — встречный случай на это). Общему root снимок НЕ достаётся: случаи ⑱ и
    # далее идут по нему как раньше, без базы вовсе.
    gordi_stand = mezo_stand.new("bite-rfp-gordi-")
    (gordi_stand / ".mezosync").mkdir(parents=True, exist_ok=True)
    mezo_stand.snapshot_db(live_db, gordi_stand / ".mezosync" / "mezosync.db")
    dry = subprocess.run(
        [sys.executable, str(GORDI_ISSUE_PY), "create", "--role", "COORD",
         "--title", "тест приёмки bite-rules-from-pack", "--body-file", str(out_file),
         "--dry-run"],
        cwd=str(gordi_stand), env=mezo_stand.stand_env(gordi_stand), capture_output=True,
        text=True, encoding="utf-8")
    ok &= case("⑰б тело предложения принимает холостой прогон gordi-issue.py (свои "
              "разделы он находит настоящими, не выдуманными)",
              dry.returncode == 0 and "разделы полны" in dry.stdout,
              f"код {dry.returncode}; вывод: {(dry.stdout or dry.stderr).strip()[:200]}")
    conn7.close(); pack_conn7.close()

    # ── ⑰б ПОЛОМКА (С): раздел «ПРЕДЛОЖЕНИЕ» пуст ПОД заголовком ────────────────────────
    # Встречный случай: доказывает, что ⑰б судит именно ТЕЛО письма, а не только наличие
    # базы координатора. ⑰а эту поломку не видит (её проверка ищет заголовок подстрокой),
    # gordi-issue.py — ловит (её проверка смотрит текст под заголовком).
    mod_c = load_rfp(patch=patch_propose_section_empty, name="rfp_bite_17b_c")
    conn7c = sqlite3.connect(f"file:{circuit_db7.as_posix()}?mode=ro", uri=True)
    pack_conn7c = mod_c.open_pack_db(pack_dir7)
    out_file_c = root / "proposal-break-c.md"
    mod_c.propose(conn7c, pack_conn7c, pack_dir7, PREFIX + "local-changed",
                  "у нас переписано понятнее", str(out_file_c), None)
    proposal_text_c = out_file_c.read_text(encoding="utf-8")
    sections_ok_c = all(f"## {s}" in proposal_text_c for s in ("ЗАМЕР", "КЛАСС", "ПРЕДЛОЖЕНИЕ"))
    dry_c = subprocess.run(
        [sys.executable, str(GORDI_ISSUE_PY), "create", "--role", "COORD",
         "--title", "тест приёмки bite-rules-from-pack, поломка (С)", "--body-file",
         str(out_file_c), "--dry-run"],
        cwd=str(gordi_stand), env=mezo_stand.stand_env(gordi_stand), capture_output=True,
        text=True, encoding="utf-8")
    # ⚖️ Ненулевого кода МАЛО: отказ по посторонней причине (координатор не найден, нет
    # файла тела) тоже ненулевой — и случай прошёл бы, ничего не доказав. Требуется отказ
    # ИМЕННО по пустому разделу, названному по имени (правка PROTO при установке, 24.09).
    refusal_c = dry_c.stderr or ""
    empty_refusal_c = "пустые разделы" in refusal_c and "ПРЕДЛОЖЕНИЕ" in refusal_c
    ok &= case("⑰б ПОЛОМКА (С) «раздел ПРЕДЛОЖЕНИЕ пуст под заголовком» ловит только ⑰б: "
              "⑰а (заголовок подстрокой) её не видит, gordi-issue.py отказывает по пустому разделу",
              sections_ok_c and dry_c.returncode != 0 and empty_refusal_c,
              f"⑰а-проверка под поломкой (ждём не тронута — заголовки есть): {sections_ok_c}; "
              f"код холостого прогона {dry_c.returncode} (под верным кодом ⑰б — 0; поломка "
              f"обязана его сдвинуть); отказ по пустому разделу ПРЕДЛОЖЕНИЕ: {empty_refusal_c}; "
              f"вывод: {refusal_c.strip()[:160]}")
    conn7c.close(); pack_conn7c.close()

    # ── ㉒ возврат приёмщика: --apply без --actor у --adopt отказывает ДО связи с базой ──
    circuit_db8, pack_dir8, _, _ = build_state_fixture(root / "actor-gate", mod.text_sha)
    before8 = snapshot(circuit_db8)
    cp8 = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_db8), "--source", str(pack_dir8),
         "--adopt", PREFIX + "pack-changed", "--word", "владелец, тест ㉒", "--apply"],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    after8 = snapshot(circuit_db8)
    ok &= case("㉒ --apply без --actor у --adopt отказывает ДО открытия базы, база не изменилась",
              cp8.returncode != 0 and before8 == after8,
              f"код {cp8.returncode} (ждём не 0); снимок rules/meta не изменился: "
              f"{before8 == after8}; отказ: {(cp8.stdout or cp8.stderr).strip()[:150]}")

    # ── ㉓ --state отбирает РОВНО названное состояние (не соседние) ─────────────────────
    cp_state = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_db), "--source", str(pack_dir),
         "--state", "pack-changed"],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    out_state = cp_state.stdout
    expect_present = (PREFIX + "pack-changed", PREFIX + "history-base")  # оба состояния pack-changed
    expect_absent = (PREFIX + "same", PREFIX + "removed", PREFIX + "skipped", PREFIX + "no-base")
    ok &= case("㉓ --state pack-changed отбирает РОВНО это состояние, соседние — нет",
              cp_state.returncode == 0 and all(k in out_state for k in expect_present)
              and not any(k in out_state for k in expect_absent),
              f"код {cp_state.returncode}; ожидаемые ключи есть: "
              f"{all(k in out_state for k in expect_present)}; посторонние отсутствуют: "
              f"{not any(k in out_state for k in expect_absent)}")

    # ── ㉔ --state с неизвестным именем отказывает (argparse choices) ───────────────────
    cp_bad_state = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_db), "--source", str(pack_dir),
         "--state", "bogus-state"],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    ok &= case("㉔ --state с неизвестным именем состояния отказывает",
              cp_bad_state.returncode != 0 and "invalid choice" in (cp_bad_state.stderr or ""),
              f"код {cp_bad_state.returncode}; отказ назвал «invalid choice»: "
              f"{'invalid choice' in (cp_bad_state.stderr or '')}")

    # ── ㉕/㉖ ключ в ДВУХ наборах пакета с РАЗНЫМ текстом ────────────────────────────────
    def build_two_sets_fixture(sub_root: Path):
        k = PREFIX + "two-sets"
        cdb = sub_root / "circuit.db"
        pdir = sub_root / "pack"
        make_circuit_db(cdb, rules=[{"rule_key": k, "body": "circuit text\n"}],
                        meta={"template_checkout": str(pdir), "pack_rules_base": "{}",
                              "pack_rules_skipped": "{}"},
                        roles=[("COORD", "alive", "координатор контура; в живом реестре")])
        make_pack_db(pdir / "rules" / "pack-rules.db", rows=[
            {"rule_set": "universal", "rule_key": k, "body": "universal text\n",
             "text_sha": mod.text_sha("universal text\n"), "pack_commit": "u1"},
            {"rule_set": "data-platform", "rule_key": k, "body": "dp text\n",
             "text_sha": mod.text_sha("dp text\n"), "pack_commit": "d1"},
        ])
        return cdb, pdir, k

    circuit_db9, pack_dir9, key9 = build_two_sets_fixture(root / "two-sets")
    before9 = snapshot(circuit_db9)
    cp9 = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_db9), "--source", str(pack_dir9),
         "--adopt", key9, "--word", "владелец, тест ㉕", "--actor", "BITE", "--apply"],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    after9 = snapshot(circuit_db9)
    out9 = (cp9.stdout or "") + (cp9.stderr or "")
    ok &= case("㉕ ключ в двух наборах с разным текстом: без --rule-set запись отказывает "
              "и называет ОБА набора",
              cp9.returncode != 0 and "universal" in out9 and "data-platform" in out9
              and before9 == after9,
              f"код {cp9.returncode}; названы оба набора: "
              f"{'universal' in out9 and 'data-platform' in out9}; база не изменилась: "
              f"{before9 == after9}")

    cp10 = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_db9), "--source", str(pack_dir9),
         "--adopt", key9, "--rule-set", "data-platform", "--word", "владелец, тест ㉖",
         "--actor", "BITE", "--apply"],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    body10 = sqlite3.connect(str(circuit_db9)).execute(
        "SELECT body FROM rules WHERE rule_key=?", (key9,)).fetchone()
    ok &= case("㉖ ключ в двух наборах: с --rule-set берёт ИМЕННО названный набор",
              cp10.returncode == 0 and body10 and body10[0] == "dp text\n".strip(),
              f"код {cp10.returncode}; тело теперь {body10[0] if body10 else None!r} "
              f"(ждём текст набора data-platform, не universal)")

    # ── ㉗–㉙ --record-base: пишет только совпавшим, соседей не трогает, повтор — «ничего» ──
    circuit_dbR, pack_dirR, _, _ = build_state_fixture(root / "record-base", mod.text_sha)
    connR = sqlite3.connect(f"file:{circuit_dbR.as_posix()}?mode=rw", uri=True)
    pack_connR = mod.open_pack_db(pack_dirR)
    baseR_before = mod.load_meta_map(connR, "pack_rules_base")
    # существующая (возможно устаревшая) опора у НЕсовпавшего ключа — должна остаться как есть
    stale_key = f"{RULE_SET}/{PREFIX}no-base"
    baseR_before[stale_key] = "0000000000000000"
    mod.save_meta_map(connR, "pack_rules_base", baseR_before)
    connR.commit()
    pack_rowsR = mod.load_pack_rows(pack_connR)
    baseR = mod.load_meta_map(connR, "pack_rules_base")
    csR, _ = mod.resolve_contour_rule_sets(connR, mod.load_circuit_rules(connR), pack_rowsR)
    rcR = mod.record_base(connR, pack_rowsR, baseR, True, "BITE", csR)
    baseR_after = mod.load_meta_map(connR, "pack_rules_base")
    same_key = f"{RULE_SET}/{PREFIX}same"
    ok &= case("㉗ --record-base --apply пишет опору РОВНО совпадающим ключам (по отпечатку)",
              rcR == 0 and baseR_after.get(same_key) == mod.text_sha("text A\n"),
              f"код {rcR}; опора совпавшего ключа «same» = "
              f"{baseR_after.get(same_key)!r} (ждём отпечаток «text A\\n»)")
    ok &= case("㉘ --record-base НЕ трогает опору у НЕсовпавшего ключа, даже устаревшую",
              baseR_after.get(stale_key) == "0000000000000000",
              f"опора несовпавшего ключа «no-base» осталась «{baseR_after.get(stale_key)}» "
              f"(ждём нетронутой «0000000000000000»)")
    rcR2 = mod.record_base(connR, mod.load_pack_rows(pack_connR),
                           mod.load_meta_map(connR, "pack_rules_base"), True, "BITE", csR)
    baseR_after2 = mod.load_meta_map(connR, "pack_rules_base")
    ok &= case("㉙ повторный --record-base --apply ничего не меняет (идемпотентно)",
              rcR2 == 0 and baseR_after2 == baseR_after,
              f"код {rcR2}; опора до и после повтора совпадает: {baseR_after2 == baseR_after}")
    connR.close(); pack_connR.close()

    # ── ㉚/㉛ --summary: строка сходится с полным списком, отказ — код 2 и слова причины ──
    cp_sum = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_db), "--source", str(pack_dir),
         "--summary"],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    counts_full = mod.summarize(rows, only_yours_got)
    summary_line = (
        f"правила пакета: новых {counts_full['new']} · "
        f"изменено в пакете {counts_full['pack-changed']} · "
        f"уточнено у вас {counts_full['local-changed']} · "
        f"с обеих сторон {counts_full['both-changed']} · опоры нет {counts_full['no-base']} · "
        f"снято в пакете {counts_full['removed']} · снято у вас {counts_full['retired-here']} "
        f"— подробно: rules-from-pack.py"
    )
    # ⚖️ ВОЗВРАТ PROTO: фикстура несёт один набор ("universal") и не пишет meta.pack_rule_sets
    # — значит наборы ВСЕГДА выводятся по наличию, и строка об этом идёт ПЕРЕД строкой счёта.
    note_1 = mod.rule_sets_note(contour_sets_1, False)
    expected_line = (note_1 + "\n" + summary_line) if note_1 else summary_line
    ok &= case("㉚ --summary: строка о наборах (фикстура их не записывает) и строка счёта "
              "сходятся с полным списком",
              cp_sum.returncode == 0 and cp_sum.stdout.strip() == expected_line,
              f"код {cp_sum.returncode}; строка сошлась: "
              f"{cp_sum.stdout.strip() == expected_line}; получили "
              f"{cp_sum.stdout.strip()!r}")

    # папка пакета ЕСТЬ (иначе сработал бы другой отказ — «пакет не найден» у
    # find_pack_source), а вот rules/pack-rules.db внутри неё нет — именно этот случай
    # обязан назвать словами «в пакете нет базы правил» (требование возврата)
    empty_pack_dir = root / "empty-pack-no-db"
    empty_pack_dir.mkdir(parents=True, exist_ok=True)
    cp_sum_missing = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_db), "--source",
         str(empty_pack_dir), "--summary"],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    ok &= case("㉛ --summary при отсутствии базы пакета — код 2 и слова «в пакете нет базы "
              "правил», не молчание",
              cp_sum_missing.returncode == 2
              and "в пакете нет базы правил" in (cp_sum_missing.stderr or ""),
              f"код {cp_sum_missing.returncode} (ждём 2); причина в stderr: "
              f"{(cp_sum_missing.stderr or '').strip()[:150]!r}")

    # ── ㉜ ПОЛОМКА (А) красит именно pack-changed и local-changed, не остальные ──────
    mod_a = load_rfp(patch=patch_a, name="rfp_bite_a")
    circuit_dbA, pack_dirA, expectedA, _ = build_state_fixture(root / "break-a", mod_a.text_sha)
    connA = sqlite3.connect(f"file:{circuit_dbA.as_posix()}?mode=ro", uri=True)
    pack_connA = mod_a.open_pack_db(pack_dirA)
    circuit_rulesA_ = mod_a.load_circuit_rules(connA)
    pack_rowsA_ = mod_a.load_pack_rows(pack_connA)
    csA_, _ = mod_a.resolve_contour_rule_sets(connA, circuit_rulesA_, pack_rowsA_)
    rowsA, _ = mod_a.build_rows(circuit_rulesA_, pack_rowsA_,
                                mod_a.load_meta_map(connA, "pack_rules_base"),
                                mod_a.load_meta_map(connA, "pack_rules_skipped"),
                                mod_a.make_history_has(pack_connA), csA_,
                                mod_a.load_circuit_retired_keys(connA))
    stateA = {r["rule_key"]: r["state"] for r in rowsA}
    connA.close(); pack_connA.close()
    ok &= case("㉜ ПОЛОМКА (А) «опора не используется» красит pack-changed и local-changed "
              "в no-base, а same/removed/new/skipped не трогает",
              stateA[PREFIX + "pack-changed"] == "no-base"
              and stateA[PREFIX + "local-changed"] == "no-base"
              and stateA[PREFIX + "same"] == "same" and stateA[PREFIX + "removed"] == "removed"
              and stateA[PREFIX + "new"] == "new" and stateA[PREFIX + "skipped"] == "skipped",
              f"под поломкой (А): pack-changed→{stateA[PREFIX+'pack-changed']}, "
              f"local-changed→{stateA[PREFIX+'local-changed']} (оба ждём no-base); "
              f"соседи не задеты: same={stateA[PREFIX+'same']}, removed={stateA[PREFIX+'removed']}")

    # ── ㉝ ПОЛОМКА (Б) красит «опора только у взятого» ───────────────────────────────
    mod_b = load_rfp(patch=patch_b, name="rfp_bite_b")
    circuit_dbB, pack_dirB, _, _ = build_state_fixture(root / "break-b", mod_b.text_sha)
    connB = sqlite3.connect(f"file:{circuit_dbB.as_posix()}?mode=rw", uri=True)
    pack_connB = mod_b.open_pack_db(pack_dirB)
    baseB = mod_b.load_meta_map(connB, "pack_rules_base")
    # both-changed: у него О≠П в фикстуре, так что ошибочная запись П туда ОБЯЗАНА
    # сдвинуть значение — соседа с О=П для этого не годится, там подмена НЕОТЛИЧИМА
    other_keyB = f"{RULE_SET}/{PREFIX}both-changed"
    before_other = baseB.get(other_keyB)
    mod_b.adopt_keys(connB, circuit_dbB, pack_connB, baseB, [PREFIX + "pack-changed"], None,
                     "владелец, приёмка, тест ⑲", True, "bite")
    base_afterB = mod_b.load_meta_map(connB, "pack_rules_base")
    connB.close(); pack_connB.close()
    ok &= case("㉝ ПОЛОМКА (Б) «опора всем ключам пакета» красит проверку «только у взятого»",
              base_afterB.get(other_keyB) != before_other,
              f"опора соседа ДО {before_other!r}, ПОСЛЕ {base_afterB.get(other_keyB)!r} — "
              f"под верным кодом они обязаны совпасть, поломка обязана их развести")

    # ── ㉞ ПОЛОМКА (В) красит «без --apply ничего не пишет» ──────────────────────────
    mod_v = load_rfp(patch=patch_v, name="rfp_bite_v")
    circuit_dbV, pack_dirV, _, _ = build_state_fixture(root / "break-v", mod_v.text_sha)
    before_v = snapshot(circuit_dbV)
    connV = sqlite3.connect(f"file:{circuit_dbV.as_posix()}?mode=rw", uri=True)
    pack_connV = mod_v.open_pack_db(pack_dirV)
    skipV = mod_v.load_meta_map(connV, "pack_rules_skipped")
    # ⚠️ --word ЗДЕСЬ ДАН НАРОЧНО, хотя apply=False: под ВЕРНЫМ кодом --word в холостом
    # прогоне не смотрят вовсе (гейт срабатывает раньше и возвращает раньше, чем дело
    # доходит до --word) — поэтому снимок не сдвинется. Под ПОЛОМКОЙ (В) гейт молчит,
    # проверка --word проходит (он дан), и код добирается до настоящей записи — вот
    # тогда снимок и обязан сдвинуться. Без --word поломка споткнулась бы о ДРУГОЙ
    # отказ (require_word) и её было бы не отличить от исправного холостого прогона.
    try:
        mod_v.skip_key(connV, pack_connV, skipV, PREFIX + "no-base", None,
                       "владелец, приёмка, тест ⑳", False)
    except SystemExit:
        pass
    connV.close(); pack_connV.close()
    after_v = snapshot(circuit_dbV)
    ok &= case("㉞ ПОЛОМКА (В) «--apply не нужен» красит проверку «без --apply ничего не пишет»",
              before_v != after_v,
              "под верным кодом снимок не менялся (случай ⑫); поломка обязана его сдвинуть"
              + (" — сдвинула" if before_v != after_v else " — НЕ сдвинула, поломка не поймана"))

    # ═══ ㊱–㊴ КАРТОЧКА #608, ВОЗВРАТ PROTO: контур сверяется ТОЛЬКО с наборами пакета,
    # которые он реально взял — иначе КАЖДОЕ обновление печатает шум («новых 3 · опоры
    # нет 3» на пустом месте: чужой набор пакета читался как «новое», а universal-описание
    # ключа, перекрытого доменом, — как расхождение с законно другим текстом).

    # ── ㊱ новорождённый контур С ДОМЕНОМ: сплошной ноль ──────────────────────────────
    rsA_db, rsA_pack, rsA_keys = build_rule_sets_fixture(root / "rs-with-domain", mod.text_sha,
                                                         with_domain=True)
    connA_ = sqlite3.connect(f"file:{rsA_db.as_posix()}?mode=ro", uri=True)
    pconnA_ = mod.open_pack_db(rsA_pack)
    circA_ = mod.load_circuit_rules(connA_)
    packA_ = mod.load_pack_rows(pconnA_)
    csA_r, viaA_r = mod.resolve_contour_rule_sets(connA_, circA_, packA_)
    rowsA_r, onlyA_r = mod.build_rows(circA_, packA_, mod.load_meta_map(connA_, "pack_rules_base"),
                                      mod.load_meta_map(connA_, "pack_rules_skipped"),
                                      mod.make_history_has(pconnA_), csA_r,
                                      mod.load_circuit_retired_keys(connA_))
    countsA_r = mod.summarize(rowsA_r, onlyA_r)
    connA_.close(); pconnA_.close()
    ZERO_KEYS = ("new", "pack-changed", "local-changed", "both-changed", "no-base", "removed",
                "retired-here")
    ok &= case("㊱ новорождённый контур С ДОМЕНОМ: сплошной ноль (новое · оба изменения · "
              "без опоры · снято в пакете · снято у вас)",
              viaA_r is True and all(countsA_r[k] == 0 for k in ZERO_KEYS),
              f"наборы контура: {csA_r} (из meta: {viaA_r}); счёт: "
              + " · ".join(f"{k} {countsA_r[k]}" for k in ZERO_KEYS))

    # ── ㊲ новорождённый контур БЕЗ ДОМЕНА: чужие наборы не «новые» — их вовсе нет ──────
    rsB_db, rsB_pack, rsB_keys = build_rule_sets_fixture(root / "rs-no-domain", mod.text_sha,
                                                         with_domain=False)
    connB_ = sqlite3.connect(f"file:{rsB_db.as_posix()}?mode=ro", uri=True)
    pconnB_ = mod.open_pack_db(rsB_pack)
    circB_ = mod.load_circuit_rules(connB_)
    packB_ = mod.load_pack_rows(pconnB_)
    csB_r, _ = mod.resolve_contour_rule_sets(connB_, circB_, packB_)
    rowsB_r, onlyB_r = mod.build_rows(circB_, packB_, mod.load_meta_map(connB_, "pack_rules_base"),
                                      mod.load_meta_map(connB_, "pack_rules_skipped"),
                                      mod.make_history_has(pconnB_), csB_r,
                                      mod.load_circuit_retired_keys(connB_))
    stateB_r = {r["rule_key"]: r["state"] for r in rowsB_r}
    connB_.close(); pconnB_.close()
    ok &= case("㊲ новорождённый контур БЕЗ ДОМЕНА: ключи набора data-platform (d1) и "
              "frontend-spa (f1) не «новые» — их нет в строках вовсе",
              rsB_keys["d1"] not in stateB_r and rsB_keys["f1"] not in stateB_r,
              f"d1 в строках: {rsB_keys['d1'] in stateB_r} (ждём False); "
              f"f1 в строках: {rsB_keys['f1'] in stateB_r} (ждём False)")

    # ── ㊳ перекрытый ключ сверяется с ДОМЕННЫМ описанием, не с universal ────────────────
    rsC_db, rsC_pack, rsC_keys = build_rule_sets_fixture(root / "rs-shadow-domain", mod.text_sha,
                                                         with_domain=True)
    ov1 = rsC_keys["ov1"]
    pconnC_w = sqlite3.connect(str(rsC_pack / "rules" / "pack-rules.db"))
    new_domain_text = "domain OV1, версия 2\n"
    pconnC_w.execute("UPDATE pack_rules SET body=?, text_sha=? WHERE rule_key=? AND rule_set=?",
                     (new_domain_text, mod.text_sha(new_domain_text), ov1, "data-platform"))
    pconnC_w.commit(); pconnC_w.close()
    connC_ = sqlite3.connect(f"file:{rsC_db.as_posix()}?mode=ro", uri=True)
    pconnC_ = mod.open_pack_db(rsC_pack)
    circC_ = mod.load_circuit_rules(connC_)
    packC_ = mod.load_pack_rows(pconnC_)
    csC_r, _ = mod.resolve_contour_rule_sets(connC_, circC_, packC_)
    rowsC_r, _ = mod.build_rows(circC_, packC_, mod.load_meta_map(connC_, "pack_rules_base"),
                                mod.load_meta_map(connC_, "pack_rules_skipped"),
                                mod.make_history_has(pconnC_), csC_r,
                                mod.load_circuit_retired_keys(connC_))
    stateC_r = {r["rule_key"]: r["state"] for r in rowsC_r}
    connC_.close(); pconnC_.close()
    ok &= case("㊳ правка ДОМЕННОГО описания перекрытого ключа в пакете видна («изменено в "
              "пакете»)",
              stateC_r.get(ov1) == "pack-changed",
              f"состояние ov1 после правки доменного текста: «{stateC_r.get(ov1)}» "
              f"(ждём pack-changed)")

    rsD_db, rsD_pack, rsD_keys = build_rule_sets_fixture(root / "rs-shadow-universal",
                                                         mod.text_sha, with_domain=True)
    ov2 = rsD_keys["ov2"]
    pconnD_w = sqlite3.connect(str(rsD_pack / "rules" / "pack-rules.db"))
    new_universal_text = "universal OV2, версия 2 (перекрыто — контура не касается)\n"
    pconnD_w.execute("UPDATE pack_rules SET body=?, text_sha=? WHERE rule_key=? AND rule_set=?",
                     (new_universal_text, mod.text_sha(new_universal_text), ov2, "universal"))
    pconnD_w.commit(); pconnD_w.close()
    connD_ = sqlite3.connect(f"file:{rsD_db.as_posix()}?mode=ro", uri=True)
    pconnD_ = mod.open_pack_db(rsD_pack)
    circD_ = mod.load_circuit_rules(connD_)
    packD_ = mod.load_pack_rows(pconnD_)
    csD_r, _ = mod.resolve_contour_rule_sets(connD_, circD_, packD_)
    rowsD_r, _ = mod.build_rows(circD_, packD_, mod.load_meta_map(connD_, "pack_rules_base"),
                                mod.load_meta_map(connD_, "pack_rules_skipped"),
                                mod.make_history_has(pconnD_), csD_r,
                                mod.load_circuit_retired_keys(connD_))
    stateD_r = {r["rule_key"]: r["state"] for r in rowsD_r}
    connD_.close(); pconnD_.close()
    ok &= case("㊳-встречный: правка UNIVERSAL-описания ключа, перекрытого доменом, не видна "
              "вовсе — расходится законно, это не долг контура",
              stateD_r.get(ov2) == "same",
              f"состояние ov2 после правки перекрытого universal-текста: «{stateD_r.get(ov2)}» "
              f"(ждём same)")

    # ── ㊴ контур без meta.pack_rule_sets — вывод по наличию, и строка об этом ──────────
    rsE_db, rsE_pack, rsE_keys = build_rule_sets_fixture(root / "rs-inferred", mod.text_sha,
                                                         with_domain=True, record_meta=False)
    connE_ = sqlite3.connect(f"file:{rsE_db.as_posix()}?mode=ro", uri=True)
    pconnE_ = mod.open_pack_db(rsE_pack)
    circE_ = mod.load_circuit_rules(connE_)
    packE_ = mod.load_pack_rows(pconnE_)
    csE_r, viaE_r = mod.resolve_contour_rule_sets(connE_, circE_, packE_)
    noteE_r = mod.rule_sets_note(csE_r, viaE_r)
    connE_.close(); pconnE_.close()
    ok &= case("㊴ контур без meta.pack_rule_sets: доменный набор выведен ПО НАЛИЧИЮ (у "
              "контура есть ключ, которого нет в universal), и строка об этом не пустая",
              viaE_r is False and "data-platform" in csE_r and noteE_r is not None
              and "наборы контура не записаны" in noteE_r,
              f"наборы: {csE_r} (из meta: {viaE_r}); строка: {noteE_r!r}")

    # ── ㊵ КОНТРОЛЬ нарочной поломкой (Г): scope снова игнорируется — красит ㊱ и ㊲ ──────
    mod_g = load_rfp(patch=patch_scope_off, name="rfp_bite_scope_off")
    rsAg_db, rsAg_pack, rsAg_keys = build_rule_sets_fixture(root / "rs-break-g-a", mod_g.text_sha,
                                                            with_domain=True)
    connAg = sqlite3.connect(f"file:{rsAg_db.as_posix()}?mode=ro", uri=True)
    pconnAg = mod_g.open_pack_db(rsAg_pack)
    circAg = mod_g.load_circuit_rules(connAg)
    packAg = mod_g.load_pack_rows(pconnAg)
    csAg, _ = mod_g.resolve_contour_rule_sets(connAg, circAg, packAg)
    rowsAg, onlyAg = mod_g.build_rows(circAg, packAg, mod_g.load_meta_map(connAg, "pack_rules_base"),
                                      mod_g.load_meta_map(connAg, "pack_rules_skipped"),
                                      mod_g.make_history_has(pconnAg), csAg,
                                      mod_g.load_circuit_retired_keys(connAg))
    countsAg = mod_g.summarize(rowsAg, onlyAg)
    connAg.close(); pconnAg.close()
    ok &= case("㊵ ПОЛОМКА (Г) «contour_sets игнорируется» красит ㊱: сплошной ноль пропадает "
              "(frontend-spa снова «новое»)",
              not all(countsAg[k] == 0 for k in ZERO_KEYS),
              "счёт под поломкой: " + " · ".join(f"{k} {countsAg[k]}" for k in ZERO_KEYS)
              + " (под верным кодом — case ㊱ — все нули)")

    rsBg_db, rsBg_pack, rsBg_keys = build_rule_sets_fixture(root / "rs-break-g-b", mod_g.text_sha,
                                                            with_domain=False)
    connBg = sqlite3.connect(f"file:{rsBg_db.as_posix()}?mode=ro", uri=True)
    pconnBg = mod_g.open_pack_db(rsBg_pack)
    circBg = mod_g.load_circuit_rules(connBg)
    packBg = mod_g.load_pack_rows(pconnBg)
    csBg, _ = mod_g.resolve_contour_rule_sets(connBg, circBg, packBg)
    rowsBg, _ = mod_g.build_rows(circBg, packBg, mod_g.load_meta_map(connBg, "pack_rules_base"),
                                 mod_g.load_meta_map(connBg, "pack_rules_skipped"),
                                 mod_g.make_history_has(pconnBg), csBg,
                                 mod_g.load_circuit_retired_keys(connBg))
    stateBg = {r["rule_key"]: r["state"] for r in rowsBg}
    connBg.close(); pconnBg.close()
    ok &= case("㊵ та же поломка (Г) красит ㊲: ключи ЧУЖИХ наборов (d1/f1) снова видны",
              rsBg_keys["d1"] in stateBg or rsBg_keys["f1"] in stateBg,
              f"d1 в строках: {rsBg_keys['d1'] in stateBg}; f1 в строках: "
              f"{rsBg_keys['f1'] in stateBg} (под верным кодом — case ㊲ — оба False)")

    # ── ㊶ КОНТРОЛЬ нарочной поломкой (Д): первый встреченный побеждает — красит ㊳ ──────
    mod_d = load_rfp(patch=patch_winner_first, name="rfp_bite_winner_first")
    rsCd_db, rsCd_pack, rsCd_keys = build_rule_sets_fixture(root / "rs-break-d", mod_d.text_sha,
                                                            with_domain=True)
    ov1d = rsCd_keys["ov1"]
    pconnCd_w = sqlite3.connect(str(rsCd_pack / "rules" / "pack-rules.db"))
    pconnCd_w.execute("UPDATE pack_rules SET body=?, text_sha=? WHERE rule_key=? AND rule_set=?",
                      (new_domain_text, mod_d.text_sha(new_domain_text), ov1d, "data-platform"))
    pconnCd_w.commit(); pconnCd_w.close()
    connCd = sqlite3.connect(f"file:{rsCd_db.as_posix()}?mode=ro", uri=True)
    pconnCd = mod_d.open_pack_db(rsCd_pack)
    circCd = mod_d.load_circuit_rules(connCd)
    packCd = mod_d.load_pack_rows(pconnCd)
    csCd, _ = mod_d.resolve_contour_rule_sets(connCd, circCd, packCd)
    rowsCd, _ = mod_d.build_rows(circCd, packCd, mod_d.load_meta_map(connCd, "pack_rules_base"),
                                 mod_d.load_meta_map(connCd, "pack_rules_skipped"),
                                 mod_d.make_history_has(pconnCd), csCd,
                                 mod_d.load_circuit_retired_keys(connCd))
    stateCd = {r["rule_key"]: r["state"] for r in rowsCd}
    connCd.close(); pconnCd.close()
    ok &= case("㊶ ПОЛОМКА (Д) «первый набор побеждает» красит ㊳: правка доменного описания "
              "перестаёт быть видна",
              stateCd.get(ov1d) != "pack-changed",
              f"состояние ov1 под поломкой: «{stateCd.get(ov1d)}» (под верным кодом — case "
              f"㊳ — pack-changed)")

    # ── ㊷ КОНТРОЛЬ нарочной поломкой (Е): доменный набор никогда не выводится — красит ㊴ ──
    mod_e = load_rfp(patch=patch_infer_off, name="rfp_bite_infer_off")
    rsEe_db, rsEe_pack, rsEe_keys = build_rule_sets_fixture(root / "rs-break-e", mod_e.text_sha,
                                                            with_domain=True, record_meta=False)
    connEe = sqlite3.connect(f"file:{rsEe_db.as_posix()}?mode=ro", uri=True)
    pconnEe = mod_e.open_pack_db(rsEe_pack)
    circEe = mod_e.load_circuit_rules(connEe)
    packEe = mod_e.load_pack_rows(pconnEe)
    csEe, viaEe = mod_e.resolve_contour_rule_sets(connEe, circEe, packEe)
    connEe.close(); pconnEe.close()
    ok &= case("㊷ ПОЛОМКА (Е) «доменный набор не выводится» красит ㊴: data-platform "
              "пропадает из вывода по наличию",
              "data-platform" not in csEe,
              f"наборы под поломкой: {csEe} (под верным кодом — case ㊴ — несёт data-platform)")

    # ═══ ㊸ КАРТОЧКА #608, ПОВТОРНЫЙ ВОЗВРАТ PROTO: контур сам снял правило (status≠'active')
    # — инструмент обязан читать СТАТУС КОНТУРА раньше сравнения текстов и не звать «new»
    # то, что контур осознанно отключил. Живой случай: «--state new» на живой базе называл
    # no-push-without-owner и timestamp-in-replies — оба у контура ЕСТЬ, оба status='revoked'.
    ret_db, ret_pack, ret_key = build_retired_fixture(root / "retired", mod.text_sha)
    connRet = sqlite3.connect(f"file:{ret_db.as_posix()}?mode=ro", uri=True)
    pconnRet = mod.open_pack_db(ret_pack)
    circRet = mod.load_circuit_rules(connRet)
    packRet = mod.load_pack_rows(pconnRet)
    csRet, _ = mod.resolve_contour_rule_sets(connRet, circRet, packRet)
    rowsRet, onlyRet = mod.build_rows(circRet, packRet, mod.load_meta_map(connRet, "pack_rules_base"),
                                      mod.load_meta_map(connRet, "pack_rules_skipped"),
                                      mod.make_history_has(pconnRet), csRet,
                                      mod.load_circuit_retired_keys(connRet))
    countsRet = mod.summarize(rowsRet, onlyRet)
    stateRet = {r["rule_key"]: r["state"] for r in rowsRet}
    connRet.close(); pconnRet.close()
    ok &= case("㊸ контур со снятым правилом, живым в пакете — состояние «retired-here», "
              "не «new»",
              stateRet.get(ret_key) == "retired-here",
              f"состояние ключа: «{stateRet.get(ret_key)}» (ждём retired-here) — тексты "
              f"контура и пакета РАЗНЫЕ нарочно, состояние от текста не зависит")
    ok &= case("㊸ --summary фикстуры даёт РОВНО «снято у вас 1 · новых 0»",
              countsRet["retired-here"] == 1 and countsRet["new"] == 0,
              f"снято у вас {countsRet['retired-here']} (ждём 1); новых {countsRet['new']} "
              f"(ждём 0)")

    # ── ㊹ ПОЛОМКА (Ж): статус контура не читается — правило уходит обратно в «new» ────
    mod_ret = load_rfp(patch=patch_status_blind, name="rfp_bite_status_blind")
    ret_db2, ret_pack2, ret_key2 = build_retired_fixture(root / "retired-break", mod_ret.text_sha)
    connRet2 = sqlite3.connect(f"file:{ret_db2.as_posix()}?mode=ro", uri=True)
    pconnRet2 = mod_ret.open_pack_db(ret_pack2)
    circRet2 = mod_ret.load_circuit_rules(connRet2)
    packRet2 = mod_ret.load_pack_rows(pconnRet2)
    csRet2, _ = mod_ret.resolve_contour_rule_sets(connRet2, circRet2, packRet2)
    rowsRet2, onlyRet2 = mod_ret.build_rows(
        circRet2, packRet2, mod_ret.load_meta_map(connRet2, "pack_rules_base"),
        mod_ret.load_meta_map(connRet2, "pack_rules_skipped"),
        mod_ret.make_history_has(pconnRet2), csRet2, mod_ret.load_circuit_retired_keys(connRet2))
    stateRet2 = {r["rule_key"]: r["state"] for r in rowsRet2}
    connRet2.close(); pconnRet2.close()
    ok &= case("㊹ ПОЛОМКА (Ж) «статус не читается» красит ровно ㊸: правило уходит в «new»",
              stateRet2.get(ret_key2) == "new",
              f"состояние под поломкой: «{stateRet2.get(ret_key2)}» (под верным кодом — "
              f"case ㊸ — retired-here; поломка обязана вернуть старую ложь «new»)")

    # ═══ ㊺ КАРТОЧКА #608, ПОВТОРНАЯ ПРИЁМКА, ВОЗВРАТ PROTO (В1): --propose по ключу,
    # который контур сам снял (retired-here), пишет письмо «снять в пакете», а не
    # отказывает «предлагать нечего» — раньше отказывал, хотя предложить есть что.
    retP_db, retP_pack, retP_key = build_retired_fixture(root / "propose-retired", mod.text_sha)
    connP = sqlite3.connect(f"file:{retP_db.as_posix()}?mode=ro", uri=True)
    pconnP = mod.open_pack_db(retP_pack)
    letterP = root / "propose-retired" / "letter.md"
    rcP = mod.propose(connP, pconnP, retP_pack, retP_key,
                      "контур больше не несёт это правило", str(letterP), None)
    connP.close(); pconnP.close()
    letter_textP = letterP.read_text(encoding="utf-8") if letterP.exists() else ""
    ok &= case("㊺ --propose по ключу, снятому У ВАС, пишет письмо «снять в пакете», не "
              "отказывает",
              rcP == 0 and letterP.exists() and "СНЯТ" in letter_textP
              and "статус: revoked" in letter_textP and "(не заполнено)" in letter_textP
              and "Цена: строк уберётся" in letter_textP,
              f"код {rcP}; письмо создано: {letterP.exists()}; статус найден: "
              f"{'статус: revoked' in letter_textP}; цена найдена: "
              f"{'Цена: строк уберётся' in letter_textP}")

    # ── ㊺ ПОЛОМКА (З): ветка retired-here снята — --propose снова отказывает ─────────
    mod_z = load_rfp(patch=patch_propose_retire_off, name="rfp_bite_propose_retire_off")
    retPz_db, retPz_pack, retPz_key = build_retired_fixture(root / "propose-retired-break",
                                                             mod_z.text_sha)
    connPz = sqlite3.connect(f"file:{retPz_db.as_posix()}?mode=ro", uri=True)
    pconnPz = mod_z.open_pack_db(retPz_pack)
    refusedPz = False
    try:
        mod_z.propose(connPz, pconnPz, retPz_pack, retPz_key,
                      "контур больше не несёт это правило",
                      str(root / "propose-retired-break" / "letter.md"), None)
    except SystemExit:
        refusedPz = True
    connPz.close(); pconnPz.close()
    ok &= case("㊺ ПОЛОМКА (З) «ветка retired-here снята» красит ровно ㊺: --propose снова "
              "отказывает",
              refusedPz,
              f"отказ выброшен: {refusedPz} (под верным кодом случай ㊺ пишет письмо, "
              f"а не отказывает)")

    # ═══ ㊻ КАРТОЧКА #608, ПОВТОРНАЯ ПРИЁМКА, ВОЗВРАТ PROTO (В2): подсказка на
    # gordi-issue.py — путь от СВОЕГО расположения, не впечатанный <КОНТУР> —
    # иначе из чужого контура (песочница в другом месте) подсказка ведёт в пустоту.
    elsewhere = root / "elsewhere-not-guts-atlas"
    tool_elsewhere = build_sandboxed_tool(elsewhere)
    retW_db, retW_pack, retW_key = build_retired_fixture(root / "propose-elsewhere", mod.text_sha)
    letterW = root / "propose-elsewhere" / "letter.md"
    rcW = subprocess.run(
        [sys.executable, str(tool_elsewhere), "--db", str(retW_db), "--source", str(retW_pack),
         "--propose", retW_key, "--why", "проверка пути В2", "--out", str(letterW)],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    letter_textW = letterW.read_text(encoding="utf-8") if letterW.exists() else ""
    out_and_letterW = rcW.stdout + letter_textW
    has_hardcoded = OWN_ROOT in out_and_letterW or OWN_ROOT_BS in out_and_letterW
    # ⚖️ Path.resolve() внутри испытуемого может развернуть короткое имя каталога (8.3,
    # напр. ИМЯ~1 в пути временного каталога) в длинное — сравниваем с РЕЗОЛВНУТЫМ путём песочницы, а не с
    # его сырым написанием, иначе случай ложно краснеет от несовпадения написаний ОДНОГО
    # и того же каталога, а не от впечатанного пути.
    sandbox_path_shown = str(elsewhere.resolve()) in rcW.stdout
    ok &= case("㊻ подсказка на gordi-issue.py — путь от СВОЕГО расположения: "
              "контур-песочница вне корня этого контура не показывает этот корень",
              rcW.returncode == 0 and not has_hardcoded and sandbox_path_shown,
              f"код {rcW.returncode}; впечатанный путь найден: {has_hardcoded}; "
              f"путь песочницы в выводе: {sandbox_path_shown}")

    # ── ㊻ ПОЛОМКА (И): путь снова впечатан ────────────────────────────────────────────
    elsewhere_broken = root / "elsewhere-broken"
    tool_broken = build_sandboxed_tool(elsewhere_broken)
    broken_src = tool_broken.read_text(encoding="utf-8")
    anchor = 'GORDI_ISSUE_PY = HERE / "gordi-issue.py"\n'
    if broken_src.count(anchor) != 1:
        sys.exit(f"⛔ НЕ ЗАПУСТИЛАСЬ: якорь GORDI_ISSUE_PY найден {broken_src.count(anchor)} "
                 f"раз (ждали 1) — испытуемое изменилось, поломка бьёт мимо")
    tool_broken.write_text(broken_src.replace(
        anchor,
        f'GORDI_ISSUE_PY = Path(r"{OWN_ROOT}/.mezosync/scripts/gordi-issue.py")  '
        '# ПОЛОМКА (И): путь снова впечатан\n'), encoding="utf-8")
    retX_db, retX_pack, retX_key = build_retired_fixture(root / "propose-elsewhere-break",
                                                          mod.text_sha)
    letterX = root / "propose-elsewhere-break" / "letter.md"
    rcX = subprocess.run(
        [sys.executable, str(tool_broken), "--db", str(retX_db), "--source", str(retX_pack),
         "--propose", retX_key, "--why", "проверка пути В2 поломка", "--out", str(letterX)],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    has_hardcoded_x = OWN_ROOT in rcX.stdout or OWN_ROOT_BS in rcX.stdout
    ok &= case("㊻ ПОЛОМКА (И) «путь впечатан» красит ровно ㊻: корень этого контура снова в выводе",
              rcX.returncode == 0 and has_hardcoded_x,
              f"код {rcX.returncode}; впечатанный путь в выводе: {has_hardcoded_x}")

    # ═══ ㊼ КАРТОЧКА #608, ПОВТОРНАЯ ПРИЁМКА Н1, ЗАМЕЧАНИЕ COORD (3): --show на
    # «изменено с обеих сторон» печатает текст пакета РОВНО ОДИН раз — раньше печатал
    # дважды (в начале show_one, для ЛЮБОГО состояния, и повторно в блоке трёх текстов).
    # Считаем не сырой текст (он же попадает в diff-вывод «- ...» и дал бы ложное «2» на
    # исправном коде), а САМУ ПОДПИСЬ «— текст пакета сейчас» — она печатается только там,
    # где текст пакета показывается целиком, и diff её не несёт.
    circuit_db7, pack_dir7, _, _ = build_state_fixture(root / "show-once", mod.text_sha)
    conn7 = sqlite3.connect(f"file:{circuit_db7.as_posix()}?mode=ro", uri=True)
    pack_conn7 = mod.open_pack_db(pack_dir7)
    base7 = mod.load_meta_map(conn7, "pack_rules_base")
    key_bc = PREFIX + "both-changed"
    buf7 = io.StringIO()
    with contextlib.redirect_stdout(buf7):
        mod.cmd_show(conn7, pack_conn7, key_bc, base7, None)
    shown7 = buf7.getvalue()
    conn7.close(); pack_conn7.close()
    ok &= case("㊼ --show на «изменено с обеих сторон» печатает текст пакета РОВНО ОДИН "
              "раз (подпись «— текст пакета сейчас» не задвоена)",
              shown7.count("— текст пакета сейчас") == 1,
              f"подпись встретилась {shown7.count('— текст пакета сейчас')} раз (ждём 1)")

    # ── ㊼ ПОЛОМКА (К): печать текста пакета задвоена — тот самый прежний дефект ────────
    mod_k = load_rfp(patch=patch_show_duplicate_pack_text, name="rfp_bite_show_dup")
    conn7k = sqlite3.connect(f"file:{circuit_db7.as_posix()}?mode=ro", uri=True)
    pack_conn7k = mod_k.open_pack_db(pack_dir7)
    base7k = mod_k.load_meta_map(conn7k, "pack_rules_base")
    buf7k = io.StringIO()
    with contextlib.redirect_stdout(buf7k):
        mod_k.cmd_show(conn7k, pack_conn7k, key_bc, base7k, None)
    shown7k = buf7k.getvalue()
    conn7k.close(); pack_conn7k.close()
    ok &= case("㊼ ПОЛОМКА (К) «текст пакета задвоен» красит ровно ㊼: подпись «— текст "
              "пакета сейчас» снова встречается больше одного раза",
              shown7k.count("— текст пакета сейчас") > 1,
              f"подпись встретилась {shown7k.count('— текст пакета сейчас')} раз (ждём > 1 — "
              f"поломка обязана вернуть старый дефект)")

    # ═══ ㊽ КАРТОЧКА #608, ПОВТОРНАЯ ПРИЁМКА Н1, ЗАМЕЧАНИЕ COORD (4): холостой --merge в
    # подсказке set-rule.py печатает САМ путь из --file, а не подпись-заглушку «<сведённый
    # текст из --file>» (заглушка была сама заплаткой за ДРУГУЮ беду — раньше показывала
    # «тело правила пакета», что для --merge вообще неверно; теперь роль видит настоящий
    # --body-file, который получит НАСТОЯЩИЙ вызов set-rule.py).
    circuit_db8, pack_dir8, _, _ = build_state_fixture(root / "merge-dry", mod.text_sha)
    conn8 = sqlite3.connect(f"file:{circuit_db8.as_posix()}?mode=ro", uri=True)
    pack_conn8 = mod.open_pack_db(pack_dir8)
    base8 = mod.load_meta_map(conn8, "pack_rules_base")
    merge_key8 = PREFIX + "both-changed"
    merged_file8 = root / "merge-dry" / "merged.txt"
    merged_file8.write_text("сведённый текст для холостого --merge\n", encoding="utf-8")
    buf8 = io.StringIO()
    with contextlib.redirect_stdout(buf8):
        mod.merge_key(conn8, circuit_db8, pack_conn8, base8, merge_key8, None,
                      str(merged_file8), None, False, "bite")
    shown8 = buf8.getvalue()
    conn8.close(); pack_conn8.close()
    ok &= case("㊽ холостой --merge печатает САМ путь из --file, а не подпись-заглушку",
              str(merged_file8) in shown8 and "<сведённый текст из --file>" not in shown8,
              f"путь файла в выводе: {str(merged_file8) in shown8}; старая заглушка в "
              f"выводе: {'<сведённый текст из --file>' in shown8}")

    # ── ㊽ ПОЛОМКА (Л): подпись-заглушка возвращена ─────────────────────────────────────
    mod_l = load_rfp(patch=patch_merge_dry_run_label, name="rfp_bite_merge_label")
    conn8l = sqlite3.connect(f"file:{circuit_db8.as_posix()}?mode=ro", uri=True)
    pack_conn8l = mod_l.open_pack_db(pack_dir8)
    base8l = mod_l.load_meta_map(conn8l, "pack_rules_base")
    buf8l = io.StringIO()
    with contextlib.redirect_stdout(buf8l):
        mod_l.merge_key(conn8l, circuit_db8, pack_conn8l, base8l, merge_key8, None,
                        str(merged_file8), None, False, "bite")
    shown8l = buf8l.getvalue()
    conn8l.close(); pack_conn8l.close()
    ok &= case("㊽ ПОЛОМКА (Л) «заглушка возвращена» красит ровно ㊽: путь из --file "
              "пропал, заглушка снова в выводе",
              "<сведённый текст из --file>" in shown8l and str(merged_file8) not in shown8l,
              f"заглушка в выводе: {'<сведённый текст из --file>' in shown8l}; путь "
              f"файла в выводе: {str(merged_file8) in shown8l} (ждём False)")

    # ═══ ㊾ КАРТОЧКА #614 п.1 (G3/PROTO): новый контур из пакета — meta.template_source
    # несёт АДРЕС УДАЛЁНКИ (как его пишет init-group.py: `git remote get-url origin`),
    # а НЕ папку клона; rules-from-pack.py без --source и без meta.template_checkout
    # обязан взять базу правил ТЕМ ЖЕ ходом, что update-tools.py (временный клон, только
    # чтение, убирается штатно) — а не отказывать. Адрес — ЛОКАЛЬНЫЙ file://, сеть не
    # участвует (task-g3-614.md п.3).
    remote_root = root / "remote-614"
    remote_root.mkdir()
    circuit_dbM, file_url, remote_key = build_remote_pack_fixture(remote_root, mod.text_sha)
    connM = sqlite3.connect(f"file:{circuit_dbM.as_posix()}?mode=ro", uri=True)
    # ⚖️ Тот же приём, что у случая ⑭ (владелец без --word): SystemExit ловим САМИ, а не
    # даём ему уронить весь прогон — на коде ДО правки find_pack_source() без --source
    # отказывает именно так, и это ОБЯЗАНО читаться как «случай не прошёл», не как крах.
    cloned = None
    try:
        cloned = mod.find_pack_source(None, connM)
        clone_ok = (cloned.is_dir() and (cloned / "rules" / "pack-rules.db").exists()
                   and str(cloned.resolve()) != str((remote_root / "pack-origin").resolve()))
    except SystemExit as e:
        clone_ok = False
        print(f"   (SystemExit: {e})")
    connM.close()
    ok &= case("㊾а find_pack_source() без --source берёт meta.template_source (адрес "
              "удалёнки) временным клоном — папка есть, в ней читается база правил",
              clone_ok,
              f"клон: {cloned} · это папка с rules/pack-rules.db внутри, ≠ самому "
              f"исходнику: {clone_ok}")

    cpM = subprocess.run(
        [sys.executable, str(RFP_PATH), "--db", str(circuit_dbM)],
        env=mezo_stand.stand_env(root), capture_output=True, text=True, encoding="utf-8")
    ok &= case("㊾б тот же случай — ПОЛНЫЙ прогон CLI без --source: код 0, ключ пакета "
              "виден («new»)",
              cpM.returncode == 0 and remote_key in cpM.stdout and "new" in cpM.stdout,
              f"код {cpM.returncode}; вывод: {cpM.stdout.strip()[:200]!r}")

    # ── ㊾в ГРАНИЦА task-g3-614.md п.1: «источника нет» ≠ «источник не читается» ─────────
    unreadable_root = root / "remote-614-unreadable"
    unreadable_root.mkdir()
    circuit_dbU = unreadable_root / "circuit.db"
    make_circuit_db(circuit_dbU, rules=[], meta={
        "template_source": "file:///C:/zzz-bite-614-there-is-definitely-no-repo-here"})
    cpU = subprocess.run([sys.executable, str(RFP_PATH), "--db", str(circuit_dbU)],
                        env=mezo_stand.stand_env(root), capture_output=True, text=True,
                        encoding="utf-8")
    no_source_root = root / "remote-614-no-source"
    no_source_root.mkdir()
    circuit_dbN = no_source_root / "circuit.db"
    make_circuit_db(circuit_dbN, rules=[], meta={})
    cpN = subprocess.run([sys.executable, str(RFP_PATH), "--db", str(circuit_dbN)],
                        env=mezo_stand.stand_env(root), capture_output=True, text=True,
                        encoding="utf-8")
    ok &= case("㊾в отказ различает «источника нет» (нет ни --source, ни template_checkout, "
              "ни template_source) и «источник не читается» (template_source есть, клон не "
              "удался) — РАЗНЫЕ слова, не один и тот же текст",
              cpU.returncode != 0 and cpN.returncode != 0
              and "источник пакета GORDI неизвестен" in cpN.stderr
              and "источник пакета GORDI неизвестен" not in cpU.stderr
              and "НЕ ЗАБРАЛОСЬ" in cpU.stderr and "источник недоступен" in cpU.stderr,
              f"нет источника: {cpN.stderr.strip()[:120]!r}; источник не читается: "
              f"{cpU.stderr.strip()[:120]!r}")

    # ── ㊾в′ ВОЗВРАТ COORD (карточка #614, ветка «а»): в отказе «источник не читается» —
    # готовая команда СЛОВАМИ ПРО ПРАВИЛА (--source <папка с клоном>), а не только диагноз
    # update-tools.py. Тот же прогон cpU выше — новая проверка ДОБАВЛЕНА, старая (㊾в) не тронута.
    ok &= case("㊾в′ ВОЗВРАТ COORD: в отказе «источник не читается» — готовая команда «"
              + READY_SOURCE_COMMAND + "» словами ПРО ПРАВИЛА, не только слова update-tools.py",
              READY_SOURCE_COMMAND in cpU.stderr and "rules-from-pack.py" in cpU.stderr,
              f"готовая команда в отказе: {READY_SOURCE_COMMAND in cpU.stderr}; "
              f"хвост отказа: {cpU.stderr.strip()[-160:]!r}")

    # ── ㊾г ВСТРЕЧНЫЙ БЕЗ СЕТИ (карточка #614, ветка «б»): template_source — АДРЕС В
    # ФОРМЕ SSH (git@host:repo.git), заведомо НЕДОСТУПНЫЙ. Приёмка НЕ идёт в сеть и НЕ
    # спрашивает учётных данных: GIT_SSH_COMMAND подменён на команду, падающую МГНОВЕННО
    # и БЕЗ единого сетевого вызова (сильнее, чем просто BatchMode=yes — тот всё равно
    # стучится в сеть и может ждать таймаут); GIT_TERMINAL_PROMPT=0 — на случай, если сам
    # git попробует спросить пароль в терминале, а не через ssh.
    ssh_root = root / "remote-614-ssh"
    ssh_root.mkdir()
    circuit_dbS = ssh_root / "circuit.db"
    make_circuit_db(circuit_dbS, rules=[], meta={
        "template_source": "git@zzz-bite-614-unreachable-host.invalid:gordi/pack.git"})
    no_network_env = dict(mezo_stand.stand_env(root),
                          GIT_TERMINAL_PROMPT="0",
                          GIT_SSH_COMMAND=f'"{sys.executable}" -c "import sys; sys.exit(1)"')
    cpS = subprocess.run([sys.executable, str(RFP_PATH), "--db", str(circuit_dbS)],
                        env=no_network_env, capture_output=True, text=True, encoding="utf-8",
                        timeout=30)
    ok &= case("㊾г ВСТРЕЧНЫЙ без сети: template_source — ssh-форма, недоступная (git clone "
              "падает МГНОВЕННО, ни один байт в сеть не уходит) — готовая команда «"
              + READY_SOURCE_COMMAND + "» тоже в выводе",
              cpS.returncode != 0 and READY_SOURCE_COMMAND in cpS.stderr,
              f"код {cpS.returncode}; готовая команда в отказе: "
              f"{READY_SOURCE_COMMAND in cpS.stderr}; хвост: {cpS.stderr.strip()[-160:]!r}")

    # ═══ ㊿ КАРТОЧКА #614 п.2 (G3/PROTO): разряд «снято в пакете» (removed) — совет несёт
    # ДВА пути вместо пустого "—", и --skip теперь принимает такую строку (и отпускает,
    # если пакет когда-нибудь сменит отпечаток снова — симметрично обычному «skipped»).
    circuit_dbR2, pack_dirR2, removed_key = build_removed_fixture(root / "removed-614", mod.text_sha)
    connR2 = sqlite3.connect(f"file:{circuit_dbR2.as_posix()}?mode=ro", uri=True)
    pconnR2 = mod.open_pack_db(pack_dirR2)
    circR2 = mod.load_circuit_rules(connR2)
    packR2 = mod.load_pack_rows(pconnR2)
    csR2, _ = mod.resolve_contour_rule_sets(connR2, circR2, packR2)
    rowsR2, onlyR2 = mod.build_rows(circR2, packR2, mod.load_meta_map(connR2, "pack_rules_base"),
                                    mod.load_meta_map(connR2, "pack_rules_skipped"),
                                    mod.make_history_has(pconnR2), csR2,
                                    mod.load_circuit_retired_keys(connR2))
    row_removed = next(r for r in rowsR2 if r["rule_key"] == removed_key)
    buf_removed = io.StringIO()
    # ⚖️ Тот же приём, что у ㊾а/㊿б: на коде ДО правки print_listing() ещё не берёт
    # db_path четвёртым параметром — TypeError ловим сами, случай читается как «не
    # прошёл» (нет готовой команды в пустом выводе), а не роняет весь прогон.
    try:
        with contextlib.redirect_stdout(buf_removed):
            mod.print_listing(rowsR2, onlyR2, None, circuit_dbR2)
    except TypeError as e:
        print(f"   (TypeError: {e})")
    listing_removed = buf_removed.getvalue()
    connR2.close(); pconnR2.close()
    ok &= case("㊿а совет у «снято в пакете» несёт ДВА пути (снять у себя / --skip), а не "
              "пустой «—»; список печатает готовую команду",
              row_removed["move"] != "—" and "снять у себя" in row_removed["move"]
              and "--skip" in row_removed["move"]
              and "снято в пакете, коммит" in listing_removed
              and "--skip" in listing_removed,
              f"совет: {row_removed['move']!r}; готовая команда в списке: "
              f"{'снято в пакете, коммит' in listing_removed}")

    # ── ㊿б --skip у removed-ключа: холостой прогон ничего не пишет, --apply пишет ──────
    circuit_dbR3, pack_dirR3, removed_key3 = build_removed_fixture(root / "removed-614-skip",
                                                                    mod.text_sha)
    conn3 = sqlite3.connect(f"file:{circuit_dbR3.as_posix()}?mode=rw", uri=True)
    pconn3 = mod.open_pack_db(pack_dirR3)
    skip3 = mod.load_meta_map(conn3, "pack_rules_skipped")
    before3 = snapshot(circuit_dbR3)
    # ⚖️ Тот же приём, что у ㊾а выше: на коде ДО правки skip_key() отказывает (нет
    # действующего текста пакета у removed-ключа) — SystemExit ловим сами, случай читается
    # как «не прошёл», а не роняет весь прогон.
    rc_dry = rc_apply = None
    try:
        rc_dry = mod.skip_key(conn3, pconn3, dict(skip3), removed_key3, None, None, False)
        after_dry = snapshot(circuit_dbR3)
        rc_apply = mod.skip_key(conn3, pconn3, skip3, removed_key3, None,
                                "владелец, приёмка bite, тест ㊿б", True)
    except SystemExit as e:
        after_dry = snapshot(circuit_dbR3)
        print(f"   (SystemExit: {e})")
    conn3.close(); pconn3.close()

    conn3b = sqlite3.connect(f"file:{circuit_dbR3.as_posix()}?mode=ro", uri=True)
    pconn3b = mod.open_pack_db(pack_dirR3)
    circ3b = mod.load_circuit_rules(conn3b)
    pack3b = mod.load_pack_rows(pconn3b)
    cs3b, _ = mod.resolve_contour_rule_sets(conn3b, circ3b, pack3b)
    rows3b, _ = mod.build_rows(circ3b, pack3b, mod.load_meta_map(conn3b, "pack_rules_base"),
                               mod.load_meta_map(conn3b, "pack_rules_skipped"),
                               mod.make_history_has(pconn3b), cs3b,
                               mod.load_circuit_retired_keys(conn3b))
    state_after_skip3 = next(r["state"] for r in rows3b if r["rule_key"] == removed_key3)
    conn3b.close(); pconn3b.close()
    ok &= case("㊿б --skip годится для removed-ключа: холостой прогон не пишет, --apply "
              "пишет, состояние становится «skipped»",
              rc_dry == 0 and before3 == after_dry and rc_apply == 0
              and state_after_skip3 == "skipped",
              f"холостой не изменил снимок: {before3 == after_dry}; после --apply "
              f"состояние: «{state_after_skip3}» (ждём skipped)")

    # ── ㊿в пакет меняет снятый текст СНОВА — отказ отпускает (симметрично случаю ⑯) ────
    pconn3c = sqlite3.connect(str(pack_dirR3 / "rules" / "pack-rules.db"))
    new_removed_text = "текст пакета — другая версия перед снятием\n"
    pconn3c.execute("UPDATE pack_rules SET body=?, text_sha=? WHERE rule_key=?",
                    (new_removed_text, mod.text_sha(new_removed_text), removed_key3))
    pconn3c.commit(); pconn3c.close()
    conn3c = sqlite3.connect(f"file:{circuit_dbR3.as_posix()}?mode=ro", uri=True)
    pconn3d = mod.open_pack_db(pack_dirR3)
    circ3c = mod.load_circuit_rules(conn3c)
    pack3c = mod.load_pack_rows(pconn3d)
    cs3c, _ = mod.resolve_contour_rule_sets(conn3c, circ3c, pack3c)
    rows3c, _ = mod.build_rows(circ3c, pack3c, mod.load_meta_map(conn3c, "pack_rules_base"),
                               mod.load_meta_map(conn3c, "pack_rules_skipped"),
                               mod.make_history_has(pconn3d), cs3c,
                               mod.load_circuit_retired_keys(conn3c))
    state_after_move3 = next(r["state"] for r in rows3c if r["rule_key"] == removed_key3)
    conn3c.close(); pconn3d.close()
    ok &= case("㊿в отказ отпускает: пакет сменил снятый текст СНОВА — состояние снова "
              "«removed», не «skipped»",
              state_after_move3 == "removed",
              f"состояние после смены текста пакета: «{state_after_move3}» (ждём removed)")

    # ── ПОЛОМКИ (М/Н/О/П) карточки #614 — по одной на новую ветку. Собраны ЗДЕСЬ, ПОСЛЕ
    # ВСЕХ новых позитивных случаев (㊾а-в, ㊿а-в): поломки бьют по коду, которого на
    # версии ДО правки нет вовсе — прогон на ней обязан сперва честно провалить каждый
    # новый случай (см. их try/except SystemExit/TypeError) и только потом встать на
    # попытке применить первую же поломку (load_rfp сама откажет: «поломка не нашла
    # ровно одну строку-цель») — а не наоборот.
    mod_m = load_rfp(patch=patch_no_remote_clone, name="rfp_bite_no_remote_clone")
    connMb = sqlite3.connect(f"file:{circuit_dbM.as_posix()}?mode=ro", uri=True)
    refused_m = False
    try:
        mod_m.find_pack_source(None, connMb)
    except SystemExit:
        refused_m = True
    connMb.close()
    ok &= case("㊾ ПОЛОМКА (М) «template_source не читается» красит ровно ㊾а: снова отказ",
              refused_m,
              f"отказ выброшен: {refused_m} (под верным кодом случай ㊾а клонирует и не падает)")

    # ── ПОЛОМКА (Р) карточка #614, возврат COORD (ветка «а»): готовая команда «--source
    # <папка с клоном пакета GORDI>» в отказе «источник не читается» убрана — должны
    # провалиться случаи ㊾в′ и ㊾г (оба бьют по ОДНОМУ И ТОМУ ЖЕ except-блоку в
    # find_pack_source(); фикстура из ㊾в переиспользуется — второй такой же беды из ㊾г
    # искать не нужно, поломка одна на весь блок).
    mod_r = load_rfp(patch=patch_no_ready_command, name="rfp_bite_no_ready_command")
    connRb = sqlite3.connect(f"file:{circuit_dbU.as_posix()}?mode=ro", uri=True)
    caught_r = None
    try:
        mod_r.find_pack_source(None, connRb)
    except SystemExit as e:
        caught_r = str(e)
    connRb.close()
    ready_missing = caught_r is not None and READY_SOURCE_COMMAND not in caught_r
    ok &= case("㊾ ПОЛОМКА (Р) «готовая команда убрана» красит ровно ㊾в′ и ㊾г: готовой "
              "команды в отказе больше нет",
              ready_missing,
              f"отказ: {caught_r!r} (под верным кодом готовая команда «{READY_SOURCE_COMMAND}» "
              f"обязана в нём быть)")

    mod_n = load_rfp(patch=patch_removed_advice_empty, name="rfp_bite_removed_advice_empty")
    move_n = mod_n.MOVE_BY_STATE["removed"]
    ok &= case("㊿ ПОЛОМКА (Н) «совет снова пуст» красит ровно ㊿а",
              move_n == "—",
              f"MOVE_BY_STATE['removed'] под поломкой: {move_n!r} (ждём «—»)")

    mod_o = load_rfp(patch=patch_removed_skip_broken, name="rfp_bite_removed_skip_broken")
    circuit_dbO, pack_dirO, removed_keyO = build_removed_fixture(root / "removed-614-break-o",
                                                                  mod_o.text_sha)
    connO = sqlite3.connect(f"file:{circuit_dbO.as_posix()}?mode=rw", uri=True)
    pconnO = mod_o.open_pack_db(pack_dirO)
    skipO = mod_o.load_meta_map(connO, "pack_rules_skipped")
    refused_o = False
    try:
        mod_o.skip_key(connO, pconnO, skipO, removed_keyO, None,
                       "владелец, приёмка, тест ㊿-О", True)
    except SystemExit:
        refused_o = True
    connO.close(); pconnO.close()
    ok &= case("㊿ ПОЛОМКА (О) «--skip у removed снова отказывает» красит ровно ㊿б",
              refused_o,
              f"отказ выброшен: {refused_o} (под верным кодом случай ㊿б пишет и не падает)")

    mod_p = load_rfp(patch=patch_removed_state_ignores_skip, name="rfp_bite_removed_ignores_skip")
    circuit_dbP, pack_dirP, removed_keyP = build_removed_fixture(root / "removed-614-break-p",
                                                                  mod_p.text_sha)
    connP2 = sqlite3.connect(f"file:{circuit_dbP.as_posix()}?mode=rw", uri=True)
    pconnP2 = mod_p.open_pack_db(pack_dirP)
    skipP = mod_p.load_meta_map(connP2, "pack_rules_skipped")
    mod_p.skip_key(connP2, pconnP2, skipP, removed_keyP, None,
                   "владелец, приёмка, тест ㊿-П", True)
    connP2.close(); pconnP2.close()
    connP3 = sqlite3.connect(f"file:{circuit_dbP.as_posix()}?mode=ro", uri=True)
    pconnP3 = mod_p.open_pack_db(pack_dirP)
    circP3 = mod_p.load_circuit_rules(connP3)
    packP3 = mod_p.load_pack_rows(pconnP3)
    csP3, _ = mod_p.resolve_contour_rule_sets(connP3, circP3, packP3)
    rowsP3, _ = mod_p.build_rows(circP3, packP3, mod_p.load_meta_map(connP3, "pack_rules_base"),
                                 mod_p.load_meta_map(connP3, "pack_rules_skipped"),
                                 mod_p.make_history_has(pconnP3), csP3,
                                 mod_p.load_circuit_retired_keys(connP3))
    state_p = next(r["state"] for r in rowsP3 if r["rule_key"] == removed_keyP)
    connP3.close(); pconnP3.close()
    ok &= case("㊿ ПОЛОМКА (П) «build_rows не смотрит skip_map у removed» красит ровно "
              "㊿б/в: после --apply состояние остаётся «removed», не «skipped»",
              state_p == "removed",
              f"состояние под поломкой после --skip --apply: «{state_p}» (под верным "
              f"кодом — «skipped»)")

    # ── ㉟ контроль: живая база контура не изменилась ────────────────────────────────
    after_live = fake_key_count_live()
    ok &= case("㉟ живая база контура: заведомо придуманных ключей приёмки в ней как не было, "
              "так и нет (полного побайтного сравнения здесь НЕ делаем — её параллельно "
              "пишут другие роли, см. шапку файла)",
              before_live == (0, 0) and after_live == (0, 0),
              f"до прогона: {before_live}, после: {after_live} (оба ждём (0, 0) — "
              f"ни одной строки/упоминания с приметой «{PREFIX}»)")

    print()
    print(f"{'✅ ПРИНЯТО' if ok else '🔴 НЕ ПРИНЯТО'} — случаев {CASES}, различающих {DIFFER}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(mezo_stand.finish(main()))
