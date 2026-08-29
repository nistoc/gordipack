# -*- coding: utf-8 -*-
"""
role-brief.py — СОБИРАЕМЫЙ НАКАЗ РОЛИ + ПАЁК ПУЛА (заход 2.1 + П⑥ плана «Роли
не забывают»). Наказ не пишется рукой и не протухает молча: он СОБИРАЕТСЯ из живых
источников при каждом вызове. Рукописный наказ уже победил верную память роли
(живой случай 27.08) — этот собирается из того, что и так правится по ходу работы.

    python <КОНТУР>/.mezosync/scripts/role-brief.py --role PROTO

ИСТОЧНИКИ (сломанный ИСТОЧНИК НАЗЫВАЕТСЯ, наказ не собирается молча неполным):
  · реестр ролей (зона, жизненный цикл)      · права (role_rights, живые)
  · формы вызова — ВЫЧИСЛЯЮТСЯ от mezo_paths  · пул: карточки + скиллы + объявления
  · умения роли (role_skill, протухшие по expired_at НЕ входят)

ГРАНИЦА ВСЛУХ: пометки «обязательный шаг» у правил свода НЕТ полем — свод в паёк
не режется, печатается счёт активных правил и команда запроса. Резать свод на глаз
значило бы решать за читателя, что ему не понадобится.
"""
import argparse
import sqlite3
import sys
from pathlib import Path

from mezo_paths import resolve_db, live_scripts

S = live_scripts().as_posix()
OPEN = ("open", "in_progress", "blocked", "awaiting_word", "in_review")


def section(title, fn, out):
    """Секция наказа: поломка источника НАЗЫВАЕТСЯ строкой, а не молчит и не роняет
    остальные секции (наказ, собравшийся молча без куска, — ложь о полноте)."""
    try:
        fn(out)
    except Exception as e:                             # noqa: BLE001
        out.append(f"⚠️ {title}: ИСТОЧНИК НЕ ПРОЧИТАН ({type(e).__name__}: {e}) — "
                   f"наказ НЕПОЛОН, это не «пусто»")


def build(conn, role):
    out = []

    def роль(out):
        r = conn.execute("SELECT lifecycle, zone FROM roles WHERE role=?", (role,)).fetchone()
        if not r:
            out.append(f"⚠️ роли {role} нет в реестре — зона неизвестна, спроси владельца")
            return
        lc, zone = r
        out.append(f"🧭 РОЛЬ {role} [{lc}] · зона: {zone or '— не названа'}")
        if lc != "alive":
            out.append(f"   ⚠️ жизненный цикл «{lc}» — работать без живого слова нельзя")
    section("реестр ролей", роль, out)

    def права(out):
        rows = conn.execute(
            "SELECT role, right_key, scope, kind FROM role_rights "
            "WHERE role IN (?, 'ALL') AND revoked_at IS NULL AND spent_at IS NULL "
            "ORDER BY role DESC, id", (role,)).fetchall()
        if not rows:
            out.append("🔑 ПРАВ ИМЕННЫХ НЕТ — только общие правила свода")
            return
        out.append(f"🔑 ПРАВА (живые, {len(rows)}):")
        for r_, key, scope, kind in rows:
            out.append(f"   · {key} [{kind}{', общее' if r_ == 'ALL' else ''}]: "
                       f"{(scope or '')[:90]}")
    section("права", права, out)

    def формы(out):
        out.append("🛠 ФОРМЫ ВЫЗОВА (вычислены от живого каталога — не переписывай в память "
                   "относительными):")
        for name, tail, что in [
                ("guard-all.py", "", "шаг 0 пробуждения: все гарды"),
                ("read-phoenix.py", f" --role {role}", "сохранённая память"),
                ("read-messages.py", f" --role {role}", "лента; дочитай и --ack"),
                ("backlog.py", f" list --role {role}", "карточки (пул первым)"),
                ("track.py", " view", "витрина пула"),
                ("write-message.py", f" --role {role} --file <нота.md>", "писать (длинное — файлом)"),
                ("save-phoenix.py", f" --role {role} --section state --file <f>", "сохранить память")]:
            out.append(f"   {что:32} python {S}/{name}{tail}")
        # ═══ Карточка #362: уборка памяти — ПОСЛЕ первого отчёта, не внутри старта ═══
        # Замер 29.08: полный старт роли 41 мин, из них ~13 — сжатие раздутых разделов
        # памяти ДО первого отчёта. Владелец ждёт признака жизни, а роль прибирается.
        # Порядок называется ЗДЕСЬ, а не новым шагом: шаги пробуждения не удлиняются.
        out.append("   ⚖️ порядок пробуждения: гарды → наказ → память → лента → ПЕРВЫЙ "
                   "ОТЧЁТ владельцу; УБОРКА памяти (сжатие раздутых разделов) — отдельным "
                   "ходом ПОСЛЕ отчёта: красные общего прогона о раздутых разделах — "
                   "долг дня, не приказ убирать немедленно")
    section("формы вызова", формы, out)

    def пул(out):
        pools = {r[0]: (r[1], r[2]) for r in conn.execute(
            "SELECT track_id, title, skills FROM tracks WHERE status='active'")}
        if not pools:
            out.append("🎯 ПУЛ: активного пула нет")
            return
        ph = ",".join("?" * len(pools))
        mine = conn.execute(
            f"SELECT id, title, status, parent_track FROM backlog WHERE role=? "
            f"AND parent_track IN ({ph}) AND status IN {OPEN!r}".replace("'open'", "'open'"),
            (role, *pools)).fetchall()
        if len(pools) > 1:
            out.append(f"⚠️ активных пулов {len(pools)} — норма ОДИН; судьба лишнего — "
                       f"слово владельца")
        else:
            # Карточка #399 ступень ④ (слово владельца 29.08 14:39 UTC): направление —
            # первой строкой секции. Взятие вне его — предупреждение; причина — вслух.
            out.append(f"🧭 НАПРАВЛЕНИЕ КОНТУРА: {next(iter(pools))} — вне его задач "
                       f"не бери; законная причина — вслух (claim --off-pool)")
        if not mine:
            out.append(f"🎯 в пуле ({', '.join(sorted(pools))}) твоих карточек нет")
            return
        for tid, (title, skills) in pools.items():
            карточки = [m for m in mine if m[3] == tid]
            if not карточки:
                continue
            out.append(f"🎯 ПУЛ {tid}: «{title[:70]}»")
            out.append(f"   🧰 скиллы под задачу: {skills[:150] if skills else 'НЕ НАЗВАНЫ — спроси заводившего пул'}")
            for bid, t, st, _tr in карточки:
                out.append(f"   #{bid} [{st}] {t[:76]}")
        sys.path.insert(0, str(live_scripts()))
        from backlog import live_and_overdue, pool_open_ids
        _, overdue = live_and_overdue(conn, pool_open_ids(conn, set(pools)))
        for bid, actor, _u, note, hours in overdue[:3]:
            out.append(f"   ⏰ {actor} молчит над карточкой #{bid} — шаг истёк {hours} ч")
        out.append(f"   полнее: python {S}/track.py view")
    section("пул", пул, out)

    def умения(out):
        rows = conn.execute(
            "SELECT skill, measured_at, until_cond FROM role_skill "
            "WHERE role=? AND expired_at IS NULL ORDER BY measured_at DESC", (role,)).fetchall()
        expired = conn.execute(
            "SELECT COUNT(*) FROM role_skill WHERE role=? AND expired_at IS NOT NULL",
            (role,)).fetchone()[0]
        if not rows:
            out.append("🧠 УМЕНИЙ В ТАБЛИЦЕ НЕТ — таблица роли пишется её же рукой "
                       + (f"(протухших скрыто: {expired})" if expired else ""))
            return
        out.append(f"🧠 УМЕНИЯ ({len(rows)} живых"
                   + (f"; протухших скрыто {expired} — напоминание о протухшем вреднее "
                      f"отсутствия" if expired else "") + "):")
        for skill, mat, cond in rows[:6]:
            out.append(f"   · {skill[:80]} (замер {mat[:10]}"
                       + (f"; протухнет: {cond[:50]}" if cond else "") + ")")
        if len(rows) > 6:
            out.append(f"   … и ещё {len(rows) - 6}")
    section("умения", умения, out)

    def ритм(out):
        st = conn.execute(
            "SELECT status FROM rules WHERE rule_key='sync-alarm-in-chat'").fetchone()
        if not st or st[0] != "active":
            out.append("⏰ РИТМ: правило sync-alarm-in-chat "
                       + ("ОТОЗВАНО" if st else "НЕ НАЙДЕНО")
                       + " — ритм спроси у владельца, прежнему стандарту не верь")
            return
        out.append("⏰ РИТМ (слово владельца 29.08): будильник ВНУТРИ чата; наказ — ФАЙЛОМ; "
                   "будильник гибнет с чатом — при пересоздании перезаведи ПЕРВЫМ ходом; "
                   "задачу-расписание вне чата для сверок не заводи")
        out.append(f"   период и стандарт целиком: python {S}/set-rule.py "
                   f"--key sync-alarm-in-chat --show")
    section("ритм", ритм, out)

    def свод(out):
        n = conn.execute("SELECT COUNT(*) FROM rules WHERE status='active'").fetchone()[0]
        out.append(f"📜 СВОД: активных правил {n} — в стартовую сводку не режется (граница в шапке); "
                   f"целиком: python {S}/set-rule.py --list")
    section("свод", свод, out)

    def ответы(out):
        st = conn.execute(
            "SELECT status FROM rules WHERE rule_key='owner-reply-format'").fetchone()
        if not st or st[0] != "active":
            out.append("🗣 ОТВЕТЫ ВЛАДЕЛЬЦУ: правило owner-reply-format не активно — "
                       "форму спроси у владельца")
            return
        out.append("🗣 ОТВЕТЫ ВЛАДЕЛЬЦУ: перед КАЖДЫМ ответом владельцу перечитай правило "
                   "(тут ссылка, не тело — две редакции разошлись бы):")
        out.append(f"   python {S}/set-rule.py --key owner-reply-format --show")
    section("ответы владельцу", ответы, out)
    return out


def main():
    ap = argparse.ArgumentParser(description="Собираемый наказ роли + стартовая сводка пула")
    ap.add_argument("--role", required=True)
    ap.add_argument("--db", default=None)
    a = ap.parse_args()
    role = a.role.upper()
    try:
        db = Path(resolve_db(a.db, __file__))
    except SystemExit as e:
        # resolve_db отказывает сам (базы нет / аренда) — наказ обязан сказать СВОИМИ
        # словами, что он НЕ СОБРАН, а не отдать голый отказ нижнего слоя.
        sys.exit(f"⛔ НАКАЗ НЕ СОБРАН: {e} — это не «пустой наказ»")
    if not db.exists():
        sys.exit(f"⛔ НАКАЗ НЕ СОБРАН: базы нет ({db}) — это не «пустой наказ»")
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    print(f"═══ НАКАЗ {role} (собран из живой базы сейчас; рукописной копии НЕ верь "
          f"старше этого вывода)")
    for line in build(conn, role):
        print(line)
    conn.close()


if __name__ == "__main__":
    main()
