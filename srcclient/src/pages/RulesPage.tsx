import { useMemo, useState } from 'react';
import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Rule } from '../types';
import { fmtUtc } from '../format';
import { groupRules, lockedByLabel, expiryLabel, authorizedLabel } from '../ruleGroups';

/**
 * Свод правил контура — сгруппированный по смыслу.
 *
 * 🎯 Слово владельца 2026-08-09: плоским списком полсотни правил «тяжело воспринимать».
 *    Плоский список требует держать в голове весь свод, чтобы понять, о чём каждая строка;
 *    группа с описанием отвечает на это заранее — до того, как человек начал читать.
 *
 * 🔴 ОТОЗВАННЫЕ ВЫНЕСЕНЫ ОТДЕЛЬНО И СВЁРНУТЫ. Отменённое правило, лежащее вперемешку с
 *    действующими, однажды будет исполнено как приказ — в этом контуре так уже случалось.
 *    Поэтому у них своя группа, своя подпись «больше не действуют» и свой вид карточки.
 *    Счётчик при этом на виду: спрятать их совсем значило бы потерять историю отмен.
 */
export function RulesPage({ refreshMs }: { refreshMs: number }) {
  const rules = usePolling<Rule[]>(() => api.rules(), refreshMs);
  const [openRule, setOpenRule] = useState<string | null>(null);

  const groups = useMemo(() => groupRules(rules.data ?? []), [rules.data]);

  // Свёрнутые группы держим ИМЕНАМИ СВЁРНУТЫХ, а не открытых: тогда группа, появившаяся
  // после следующего опроса базы, открыта по умолчанию, а не спрятана молча.
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set(['revoked']));

  const toggleGroup = (id: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  const total = rules.data?.length ?? 0;
  const revokedCount = (rules.data ?? []).filter((r) => r.revoked).length;
  const noStatusField = (rules.data ?? []).some((r) => r.status === null && r.statusNote);

  // Данных ещё нет и ошибки ещё нет — так и говорим. «Правил нет» в этот момент
  // было бы ложью про базу, которую даже не успели спросить.
  if (!rules.data && rules.loading && !rules.error) {
    return (
      <div className="page" data-panel="rules" data-state="loading">
        <div className="banner" data-item="rules-loading">Читаю свод правил…</div>
      </div>
    );
  }

  if (!rules.data) {
    return (
      <div className="page" data-panel="rules" data-state="error">
        <div className="banner banner--error" data-item="rules-error">
          <strong>Не удалось прочитать правила.</strong>
          <div className="small" style={{ marginTop: 4 }}>
            {rules.error ?? 'сервис не ответил и причины не назвал'}
          </div>
          <div className="small muted" style={{ marginTop: 4 }}>
            Это сообщение о СБОЕ ЧТЕНИЯ, а не о том, что правил нет.
          </div>
        </div>
        <button className="btn btn--ghost" onClick={rules.reload} data-control="rules-retry">
          Прочитать ещё раз
        </button>
      </div>
    );
  }

  return (
    <div className="page" data-panel="rules" data-state="ready">
      {rules.error && (
        <div className="banner banner--error" data-item="rules-stale">
          Последнее обновление не удалось: {rules.error}. Ниже — то, что было прочитано раньше.
        </div>
      )}

      {noStatusField && (
        <div className="banner banner--warn" data-item="rules-no-status-field">
          У правил в этой базе нет отдельного поля «действует / отозвано». Просмотрщик считает
          правило отозванным ТОЛЬКО по явной шапке «⛔ ОТОЗВАНО» в самом начале текста и по
          тексту больше ничего не додумывает. Значит, обратное неверно: правило вне группы
          отозванных — это «признака отмены не нашлось», а не доказательство, что оно в силе.
        </div>
      )}

      {total === 0 ? (
        // Сервис ответил, и ответ пуст. Молчаливая пустота здесь читалась бы как
        // «всё в порядке, правил не нужно» — поэтому сказано словами.
        <div className="banner banner--warn" data-item="rules-empty">
          <strong>В этой базе не заведено ни одного правила.</strong>
          <div className="small" style={{ marginTop: 4 }}>
            Сервис ответил успешно — значит база открыта и прочитана. Пусто в ней самой.
          </div>
        </div>
      ) : (
        <>
          <div className="rulesbar" data-panel="rules-summary">
            <span className="muted" data-item="rules-total">
              правил: <strong>{total}</strong> · групп: {groups.length} ·
              {' '}из них отозвано: <span className="warnnum">{revokedCount}</span>
            </span>
            <span className="rulesbar__spacer" />
            <button
              className="fchip"
              onClick={() => setCollapsed(new Set())}
              data-control="rules-expand-all"
            >
              развернуть все
            </button>
            <button
              className="fchip"
              onClick={() => setCollapsed(new Set(groups.map((g) => g.id)))}
              data-control="rules-collapse-all"
            >
              свернуть все
            </button>
          </div>

          <div className="rulegroups" data-list="rule-groups">
            {groups.map((group) => {
              const isOpen = !collapsed.has(group.id);
              return (
                <section
                  key={group.id}
                  className={`rulegroup ${group.revoked ? 'rulegroup--revoked' : ''}`}
                  data-group="rule-group"
                  data-group-id={group.id}
                  data-state={isOpen ? 'open' : 'collapsed'}
                >
                  {/* Заголовок — КНОПКА, а не подпись с кликом: так он доступен с клавиатуры
                      и объявляет своё состояние вслух через aria-expanded. */}
                  <button
                    type="button"
                    className="rulegroup__head"
                    onClick={() => toggleGroup(group.id)}
                    aria-expanded={isOpen}
                    data-control="rule-group-toggle"
                    data-group-id={group.id}
                  >
                    <span className="rulegroup__caret" aria-hidden="true">{isOpen ? '▾' : '▸'}</span>
                    <span className="rulegroup__title">{group.title}</span>
                    <span className="rulegroup__count" data-item="rule-group-count">
                      {group.rules.length}
                    </span>
                    <span className="rulegroup__state muted small">
                      {isOpen ? 'развёрнуто' : 'свёрнуто'}
                    </span>
                  </button>

                  {/* Описание видно и у свёрнутой группы: оно и есть ответ на вопрос
                      «что там внутри», ради которого группу разворачивают. */}
                  <p className="rulegroup__blurb" data-item="rule-group-blurb">{group.blurb}</p>

                  {isOpen && (
                    <ul className="rules" data-list="rules" data-group-id={group.id}>
                      {group.rules.map((r) => (
                        <RuleCard
                          key={r.ruleKey}
                          rule={r}
                          open={openRule === r.ruleKey}
                          onToggle={() => setOpenRule(openRule === r.ruleKey ? null : r.ruleKey)}
                        />
                      ))}
                    </ul>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function RuleCard({ rule, open, onToggle }: { rule: Rule; open: boolean; onToggle: () => void }) {
  const lock = lockedByLabel(rule.lockedBy);

  return (
    <li
      className={`rule ${rule.revoked ? 'rule--revoked' : ''}`}
      onClick={onToggle}
      data-item="rule"
      data-rule-key={rule.ruleKey}
      data-revoked={rule.revoked ? 'yes' : 'no'}
      data-state={open ? 'open' : 'collapsed'}
    >
      <div className="rule__head">
        <span className="rule__key mono">{rule.ruleKey}</span>

        {rule.revoked && (
          <span className="chip chip--revoked" data-item="rule-revoked-mark">отозвано</span>
        )}

        {/* Замок и срок — подписями словами, а не значками без пояснения: значок
            приходится расшифровывать, и расшифровку каждый раз угадывают заново. */}
        {lock && (
          <span
            className={`chip ${rule.lockedBy === 'owner' ? 'chip--owner' : 'chip--coord'}`}
            data-item="rule-lock"
          >
            {lock}
          </span>
        )}

        {/* У отозванного правила срок стоит в прошедшем времени. Иначе рядом со словом
            «отозвано» читается «бессрочно» — и карточка сама себе противоречит на вид,
            хотя оба факта верны: условие БЫЛО объявлено бессрочным, а отменили правило
            живым словом поверх этого условия. */}
        <span className="chip chip--expiry" data-item="rule-expiry">
          {rule.revoked ? 'объявлялось как ' : ''}
          {expiryLabel(rule.expiryKind, rule.expiryCond)}
        </span>

        <span className="muted small">
          v{rule.version ?? '?'}{rule.updatedAt ? ` · ${fmtUtc(rule.updatedAt)}` : ''}
        </span>
      </div>

      <div className="rule__body">
        {open ? <pre className="pre">{rule.body}</pre> : rule.bodyPreview}
      </div>

      {open && (
        <div className="rule__meta" data-item="rule-meta">
          {rule.revoked && rule.revokedBasis && (
            <div data-item="rule-revoked-basis">
              <span className="muted small">отзыв установлен по: </span>{rule.revokedBasis}
            </div>
          )}
          {rule.basis && (
            <div data-item="rule-basis">
              <span className="muted small">на каком основании: </span>{rule.basis}
            </div>
          )}
          {rule.authorized && (
            <div data-item="rule-authorized">
              <span className="muted small">кто разрешил: </span>{authorizedLabel(rule.authorized)}
            </div>
          )}
          {rule.sourceRef && (
            <div data-item="rule-source">
              <span className="muted small">откуда взято: </span>{rule.sourceRef}
            </div>
          )}
          {!rule.basis && !rule.authorized && !rule.sourceRef && (
            <div className="muted small" data-item="rule-basis-missing">
              Основание полями не записано — почему правило появилось, видно только из текста выше.
            </div>
          )}
        </div>
      )}
    </li>
  );
}
