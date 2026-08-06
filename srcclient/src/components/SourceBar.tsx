import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Health, SourceInfo } from '../types';
import { ago, fmtBytes, fmtUtc } from '../format';

/**
 * Выбор источника и состояние обновления.
 * Список источников — только то, что нашёл бэкенд под корнем обхода;
 * поля «введи путь руками» здесь нет намеренно (см. SourceRegistry в ../src).
 */
export function SourceBar({ health, onChanged }: { health: Health | null; onChanged: () => void }) {
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sources().then(setSources).catch((e) => setError(String(e.message ?? e)));
  }, [health?.activeDbPath]);

  const select = async (path: string) => {
    if (!path || path === health?.activeDbPath) return;
    setBusy(true);
    setError(null);
    try {
      await api.selectSource(path);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const refresh = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.refresh();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="sourcebar">
      <div className="sourcebar__row">
        <label className="sourcebar__label" htmlFor="source-select">База</label>
        <select
          id="source-select"
          className="sourcebar__select"
          value={health?.activeDbPath ?? ''}
          disabled={busy || sources.length === 0}
          onChange={(e) => void select(e.target.value)}
        >
          {sources.length === 0 && <option value="">источников не найдено</option>}
          {sources.map((s) => (
            <option key={s.path} value={s.path}>
              {s.name} — {fmtBytes(s.sizeBytes)} — {s.path}
            </option>
          ))}
        </select>

        <button className="btn" onClick={() => void refresh()} disabled={busy}>
          Обновить сейчас
        </button>
      </div>

      <div className="sourcebar__row sourcebar__row--meta">
        <span className="pill pill--ro" title="Сервис открывает базу только на чтение">
          только чтение
        </span>
        {health && (
          <>
            <span className="muted">
              обновление каждые {health.refreshSeconds} с · последнее{' '}
              {fmtUtc(health.lastRefreshUtc, true)} ({ago(health.lastRefreshUtc, health.nowUtc)})
            </span>
            {health.lastChangeDetectedUtc && (
              <span className="muted">
                · изменение замечено {fmtUtc(health.lastChangeDetectedUtc, true)}
              </span>
            )}
            {health.scanRoot && <span className="muted">· корень обхода: {health.scanRoot}</span>}
          </>
        )}
      </div>

      {health?.status === 'no-source' && (
        <div className="banner banner--warn">
          Источник не задан. Запусти бэкенд с <code>--db &lt;файл.db&gt;</code> или
          <code> --dir &lt;каталог&gt;</code>.
        </div>
      )}
      {health?.lastError && <div className="banner banner--error">Ошибка чтения: {health.lastError}</div>}
      {error && <div className="banner banner--error">{error}</div>}
    </div>
  );
}
