import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Overview, SchemaReport } from '../types';

/**
 * Что в открытой базе есть на самом деле — и чем она отличается от эталона схемы.
 *
 * Страница существует не ради красоты: живая база и эталон РАСХОДЯТСЯ (замер
 * 2026-08-06 — часть таблиц эталона отсутствует, часть живых таблиц эталон не знает).
 * Пока это видно, «пусто» на других страницах читается правильно.
 */
export function SchemaPage({ overview, refreshMs }: { overview: Overview | null; refreshMs: number }) {
  const schema = usePolling<SchemaReport>(() => api.schema(), refreshMs);
  const v = overview?.schemaVersion;

  return (
    <div className="page">
      {schema.error && <div className="banner banner--error">{schema.error}</div>}

      {v && (
        <div className="card">
          <h4>Версия схемы</h4>
          <p>
            объявлено в <code>meta</code>: <strong>{v.declared ?? '—'}</strong> ·
            {' '}рубеж в журнале миграций: <strong>{v.milestone ?? '—'}</strong> ·
            {' '}шагов всего: {v.stepsTotal ?? '—'} · после рубежа: {v.stepsAfterMilestone ?? '—'}
          </p>
          {v.note && <p className="banner banner--warn">{v.note}</p>}
        </div>
      )}

      <div className="cols">
        <div className="card">
          <h4>Есть в базе ({schema.data?.present.length ?? 0})</h4>
          <ul className="objects">
            {(schema.data?.present ?? []).map((o) => (
              <li key={o.name}>
                <span className="mono">{o.name}</span>{' '}
                <span className="muted">{o.type} · {o.columns.length} кол.</span>
                <div className="muted small">{o.columns.join(', ')}</div>
              </li>
            ))}
          </ul>
        </div>

        <div className="card">
          <h4>Есть в эталоне, нет здесь ({schema.data?.expectedButMissing.length ?? 0})</h4>
          <ul className="objects">
            {(schema.data?.expectedButMissing ?? []).map((n) => (
              <li key={n}><span className="mono">{n}</span></li>
            ))}
          </ul>

          <h4>Есть здесь, эталон не знает ({schema.data?.presentButUnknownToViewer.length ?? 0})</h4>
          <ul className="objects">
            {(schema.data?.presentButUnknownToViewer ?? []).map((n) => (
              <li key={n}><span className="mono">{n}</span></li>
            ))}
          </ul>

          {schema.data?.note && <p className="muted small">{schema.data.note}</p>}
        </div>
      </div>
    </div>
  );
}
