import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Overview, RolesResponse } from '../types';
import { ago, fmtUtc } from '../format';

/**
 * Роли и их состояние. ЗАГОТОВКА.
 *
 * ⚠️ Столбцы собраны из РАЗНЫХ таблиц, и это не косметика: в живой базе
 *    состояние роли лежит в roles.status, свободный текст — в role_status,
 *    курсор — в read_cursors или cursor_segments, память — в phoenix.
 *    Если какого-то источника в базе нет, столбец пуст и об этом сказано
 *    внизу списком, а не молча.
 */
export function RolesPage({ overview, refreshMs }: { overview: Overview | null; refreshMs: number }) {
  const roles = usePolling<RolesResponse>(() => api.roles(), refreshMs);
  const now = overview?.builtAtUtc ?? null;

  return (
    <div className="page">
      {roles.error && <div className="banner banner--error">{roles.error}</div>}

      <table className="table">
        <thead>
          <tr>
            <th style={{ width: '8rem' }}>роль</th>
            <th style={{ width: '8rem' }}>состояние</th>
            <th style={{ width: '6rem' }}>в реестре</th>
            <th style={{ width: '7rem' }}>курсор</th>
            <th style={{ width: '7rem' }}>записок</th>
            <th style={{ width: '13rem' }}>последняя записка</th>
            <th style={{ width: '7rem' }}>секций памяти</th>
            <th>заметка о состоянии</th>
          </tr>
        </thead>
        <tbody>
          {(roles.data?.items ?? []).map((r) => (
            <tr key={r.role}>
              <td className="mono"><strong>{r.role}</strong></td>
              <td>{r.status ?? <span className="muted">—</span>}</td>
              <td>{r.inRoster === null ? <span className="muted">—</span> : r.inRoster ? 'да' : 'нет'}</td>
              <td className="mono">{r.cursorAt ?? <span className="muted">—</span>}</td>
              <td className="mono">{r.messagesWritten ?? 0}</td>
              <td className="mono muted">
                {fmtUtc(r.lastMessageAt)}{' '}
                <span className="muted">{ago(r.lastMessageAt, now)}</span>
              </td>
              <td className="mono">{r.phoenixSections}</td>
              <td className="muted">
                {r.statusNote}
                {r.statusUpdatedAt ? ` (${fmtUtc(r.statusUpdatedAt)})` : ''}
              </td>
            </tr>
          ))}
          {(roles.data?.items.length ?? 0) === 0 && !roles.loading && (
            <tr><td colSpan={8} className="muted">ролей не найдено</td></tr>
          )}
        </tbody>
      </table>

      {(roles.data?.missingFeatures.length ?? 0) > 0 && (
        <p className="muted">
          в этой базе нет: {roles.data?.missingFeatures.join(', ')} — соответствующие столбцы
          пусты потому, что данных негде хранить, а не потому, что их не заполнили
        </p>
      )}
    </div>
  );
}
