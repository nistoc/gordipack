import { useCallback, useEffect, useRef, useState } from 'react';
import type { DependencyList } from 'react';

export interface PollState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/**
 * Периодический опрос бэкенда.
 *
 * Две вещи сделаны нарочно:
 *  1. При ошибке ПРЕЖНИЕ данные остаются на экране — рядом с текстом ошибки.
 *     Гасить экран из-за одного неудачного опроса значит сообщать «данных нет»,
 *     что неправда: они есть, просто последняя попытка не удалась.
 *  2. Ответ, пришедший после размонтирования или после более свежего запроса,
 *     отбрасывается — иначе на экране может оказаться устаревший ответ поверх нового.
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  intervalMs: number,
  deps: DependencyList = [],
): PollState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  const generation = useRef(0);
  // fetcher пересоздаётся на каждый рендер — храним свежий в ref,
  // чтобы он не перезапускал таймер.
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let cancelled = false;
    const mine = ++generation.current;

    const run = async () => {
      try {
        const result = await fetcherRef.current();
        if (cancelled || mine !== generation.current) return;
        setData(result);
        setError(null);
      } catch (e) {
        if (cancelled || mine !== generation.current) return;
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    setLoading(true);
    void run();

    if (intervalMs <= 0) return () => { cancelled = true; };
    const id = window.setInterval(() => void run(), intervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, tick, ...deps]);

  return { data, error, loading, reload };
}
