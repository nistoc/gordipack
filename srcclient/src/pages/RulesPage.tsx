import { useState } from 'react';
import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Rule } from '../types';
import { fmtUtc } from '../format';

/** Правила контура. ЗАГОТОВКА: список + разворот тела. */
export function RulesPage({ refreshMs }: { refreshMs: number }) {
  const rules = usePolling<Rule[]>(() => api.rules(), refreshMs);
  const [open, setOpen] = useState<string | null>(null);

  const noStatusField = (rules.data ?? []).some((r) => r.status === null && r.statusNote);

  return (
    <div className="page">
      {rules.error && <div className="banner banner--error">{rules.error}</div>}

      {noStatusField && (
        <div className="banner banner--warn">
          У правил в этой базе нет поля статуса: отозвано правило или нет — написано прозой
          в теле. Просмотрщик НЕ угадывает это по тексту и показывает все правила подряд.
        </div>
      )}

      <ul className="rules">
        {(rules.data ?? []).map((r) => (
          <li key={r.ruleKey} className="rule" onClick={() => setOpen(open === r.ruleKey ? null : r.ruleKey)}>
            <div className="rule__head">
              <span className="rule__key mono">{r.ruleKey}</span>
              {r.status && <span className={`chip chip--${r.status}`}>{r.status}</span>}
              <span className="muted">
                v{r.version ?? '?'}{r.lockedBy ? ` · закреплено: ${r.lockedBy}` : ''}
                {r.updatedAt ? ` · ${fmtUtc(r.updatedAt)}` : ''}
              </span>
            </div>
            <div className="rule__body">
              {open === r.ruleKey ? <pre className="pre">{r.body}</pre> : r.bodyPreview}
            </div>
          </li>
        ))}
        {(rules.data?.length ?? 0) === 0 && !rules.loading && <li className="muted">правил не найдено</li>}
      </ul>
    </div>
  );
}
