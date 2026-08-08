import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Overview, SchemaReport } from '../types';

/**
 * Что в открытой базе есть на самом деле — и чем она отличается от эталона схемы.
 *
 * Страница существует не ради красоты: живая база и эталон РАСХОДЯТСЯ (замер
 * 2026-08-06 — часть таблиц эталона отсутствует, часть живых таблиц эталон не знает).
 * Пока это видно, «пусто» на других страницах читается правильно.
 *
 * 🔴 ПОЧЕМУ ЗДЕСЬ СТОЛЬКО СЛОВ ВМЕСТО ПУСТЫХ СПИСКОВ. До 2026-08-09 страница молча
 *    гасла целиком, и отличить «сервис не ответил» от «в базе пусто» было нечем:
 *    и то и другое выглядело одинаково — тёмный экран. Поэтому теперь каждое из
 *    четырёх состояний названо словами: жду ответа · ответ не пришёл · ответ пришёл
 *    и он пуст · вот содержимое. Молчание не считается ни одним из них.
 */
export function SchemaPage({ overview, refreshMs }: { overview: Overview | null; refreshMs: number }) {
  const schema = usePolling<SchemaReport>(() => api.schema(), refreshMs);
  const v = overview?.schemaVersion;
  const data = schema.data;

  // Первая загрузка: данных ещё нет и ошибки ещё нет. Показывать в этот момент
  // «объектов: 0» значило бы соврать про базу, которую даже не спросили.
  if (!data && schema.loading && !schema.error) {
    return (
      <div className="page" data-panel="schema" data-state="loading">
        <div className="banner" data-item="schema-loading">Читаю устройство базы…</div>
      </div>
    );
  }

  // Ответа нет вовсе — и это НЕ «пустая база». Разница названа прямо.
  if (!data) {
    return (
      <div className="page" data-panel="schema" data-state="error">
        <div className="banner banner--error" data-item="schema-error">
          <strong>Не удалось прочитать устройство базы.</strong>
          <div className="small" style={{ marginTop: 4 }}>
            {schema.error ?? 'сервис не ответил и причины не назвал'}
          </div>
          <div className="small muted" style={{ marginTop: 4 }}>
            Это сообщение о СБОЕ ЧТЕНИЯ, а не о том, что в базе ничего нет.
          </div>
        </div>
        <button className="btn btn--ghost" onClick={schema.reload} data-control="schema-retry">
          Прочитать ещё раз
        </button>
      </div>
    );
  }

  const present = data.present ?? [];
  const missing = data.expectedButMissing ?? [];
  const unknown = data.presentButUnknownToPeriscope ?? [];

  return (
    <div className="page" data-panel="schema" data-state="ready">
      {/* Ошибка ПОВЕРХ уже показанных данных: прежний ответ на экране остаётся,
          потому что он был — гасить его из-за одной неудачной попытки значит
          сообщать «данных нет», что неправда. */}
      {schema.error && (
        <div className="banner banner--error" data-item="schema-stale">
          Последнее обновление не удалось: {schema.error}. Ниже — то, что было прочитано раньше.
        </div>
      )}

      {v && (
        <div className="card" data-group="schema-version">
          <h4>Версия схемы</h4>
          <p>
            объявлено в <code>meta</code>: <strong>{v.declared ?? '—'}</strong> ·
            {' '}рубеж в журнале миграций: <strong>{v.milestone ?? '—'}</strong> ·
            {' '}шагов всего: {v.stepsTotal ?? '—'} · после рубежа: {v.stepsAfterMilestone ?? '—'}
          </p>
          {v.note && <p className="banner banner--warn">{v.note}</p>}
        </div>
      )}

      {/* База ответила, и в ней действительно нет объектов. Такое бывает
          (пустой или чужой файл) — и должно быть СКАЗАНО, а не показано пустотой. */}
      {present.length === 0 && (
        <div className="banner banner--warn" data-item="schema-empty">
          <strong>В этой базе нет ни одной таблицы и ни одного представления.</strong>
          <div className="small" style={{ marginTop: 4 }}>
            Сервис ответил успешно — значит файл открыт и прочитан. Пусто в нём самом:
            скорее всего выбран не тот файл или база ещё не создана.
          </div>
        </div>
      )}

      <div className="cols">
        <div className="card" data-group="schema-present">
          <h4>Есть в базе ({present.length})</h4>
          <ul className="objects" data-list="schema-present">
            {present.map((o) => (
              <li key={o.name} data-item="schema-object" data-object-name={o.name}>
                <span className="mono">{o.name}</span>{' '}
                <span className="muted">{o.type} · {(o.columns ?? []).length} кол.</span>
                <div className="muted small">{(o.columns ?? []).join(', ')}</div>
              </li>
            ))}
          </ul>
        </div>

        <div className="card" data-group="schema-diff">
          <h4>Есть в эталоне, нет здесь ({missing.length})</h4>
          <ul className="objects" data-list="schema-missing">
            {missing.map((n) => (
              <li key={n} data-item="schema-missing-object" data-object-name={n}>
                <span className="mono">{n}</span>
              </li>
            ))}
            {missing.length === 0 && (
              <li className="muted" data-item="schema-missing-none">
                таких нет — эталон сошёлся с базой полностью
              </li>
            )}
          </ul>

          <h4>Есть здесь, эталон не знает ({unknown.length})</h4>
          <ul className="objects" data-list="schema-unknown">
            {unknown.map((n) => (
              <li key={n} data-item="schema-unknown-object" data-object-name={n}>
                <span className="mono">{n}</span>
              </li>
            ))}
            {unknown.length === 0 && (
              <li className="muted" data-item="schema-unknown-none">
                таких нет — все объекты базы просмотрщику знакомы
              </li>
            )}
          </ul>

          {data.note && <p className="muted small">{data.note}</p>}
        </div>
      </div>
    </div>
  );
}
