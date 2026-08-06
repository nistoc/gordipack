import { useEffect, useState } from 'react';
import { api } from '../api';
import { usePolling } from '../usePolling';
import type { Message, MessagePage } from '../types';
import { fmtUtc } from '../format';

const PAGE = 50;

/**
 * Лента записок. ЗАГОТОВКА: показывает страницу с фильтрами и разворотом тела.
 * Чего осознанно НЕТ (см. README): разметки markdown, тредов, адресатов —
 * тред и адресат в живой базе пока пусты (замер 2026-08-06 16:39 UTC:
 * message_thread — 0 строк, таблицы message_addressee нет вовсе),
 * рисовать под них интерфейс рано.
 */
export function FeedPage({ refreshMs }: { refreshMs: number }) {
  const [role, setRole] = useState('all');
  const [priority, setPriority] = useState('all');
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<number | null>(null);
  const [writers, setWriters] = useState<string[]>([]);

  useEffect(() => {
    api.writers().then(setWriters).catch(() => setWriters([]));
  }, []);

  // Поиск применяется по кнопке/Enter, а не на каждое нажатие: иначе каждый
  // символ — это LIKE-скан по 3 тысячам тел.
  useEffect(() => setOffset(0), [role, priority, query]);

  const page = usePolling<MessagePage>(
    () => api.messages({ limit: PAGE, offset, role, priority, search: query || undefined }),
    refreshMs,
    [role, priority, query, offset],
  );

  const body = usePolling<Message | null>(
    () => (openId === null ? Promise.resolve(null) : api.message(openId)),
    0,
    [openId],
  );

  const total = page.data?.total ?? 0;

  return (
    <div className="page">
      <div className="filters">
        <label>
          Автор
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="all">все</option>
            {writers.map((w) => <option key={w} value={w}>{w}</option>)}
          </select>
        </label>

        <label>
          Важность
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="all">любая</option>
            <option value="critical">critical</option>
            <option value="high">high</option>
            <option value="normal">normal</option>
          </select>
        </label>

        <label>
          Поиск по телу
          <input
            type="search"
            value={search}
            placeholder="подстрока"
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') setQuery(search); }}
          />
        </label>
        <button className="btn" onClick={() => setQuery(search)}>искать</button>

        <span className="muted">
          найдено: {total}
          {page.data ? ` · читаем из ${page.data.sourceObject}` : ''}
        </span>
      </div>

      {page.error && <div className="banner banner--error">{page.error}</div>}

      <ul className="feed">
        {(page.data?.items ?? []).map((m) => (
          <li
            key={`${m.source ?? 'live'}-${m.id}`}
            className={`note note--${m.priority ?? 'normal'}`}
            onClick={() => setOpenId(openId === m.id ? null : m.id)}
          >
            <div className="note__head">
              <span className="note__role">{m.writerRole}</span>
              <span className="mono muted">
                #{m.id} · {fmtUtc(m.timestamp, true)}
                {m.source ? ` · ${m.source}` : ''}
                {m.broadcast ? ' · всем' : ''}
              </span>
            </div>
            <div className="note__body">
              {openId === m.id && body.data ? body.data.bodyMd : m.bodyPreview}
            </div>
            {m.bodyLength > m.bodyPreview.length && openId !== m.id && (
              <div className="muted note__more">…ещё {m.bodyLength - m.bodyPreview.length} символов — нажми, чтобы развернуть</div>
            )}
            {m.tags.length > 0 && (
              <div className="tags">{m.tags.map((t) => <span key={t} className="tag">{t}</span>)}</div>
            )}
          </li>
        ))}
        {(page.data?.items.length ?? 0) === 0 && !page.loading && (
          <li className="muted">под фильтр ничего не попало</li>
        )}
      </ul>

      <div className="pager">
        <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
          ← новее
        </button>
        <span className="muted">
          {total === 0 ? '0' : `${offset + 1}–${Math.min(offset + PAGE, total)} из ${total}`}
        </span>
        <button className="btn" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
          старее →
        </button>
      </div>
    </div>
  );
}
