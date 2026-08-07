import { useCallback, useEffect, useState } from 'react';

/**
 * Что открыто в рейлах — живёт В АДРЕСЕ СТРАНИЦЫ, а не в состоянии компонента.
 *
 * Зачем именно так, а не проще:
 *   · «назад» в браузере возвращает к прежде открытой карточке, а не выкидывает со страницы;
 *   · перезагрузка восстанавливает набор открытых рейлов;
 *   · ссылку на конкретную карточку можно отдать другому.
 *
 * ⚠️ Значение ВЫВОДИТСЯ из адреса, а не зеркалится в отдельное состояние: две копии одного
 * факта расходятся — это тот же класс, что стоил контуру месяца разошедшихся словарей.
 */
function readParam(key: string): string | null {
  return new URLSearchParams(window.location.search).get(key);
}

/**
 * Как правка адреса ложится в историю браузера.
 *   'push'    — шаг, на который человек ждёт «назад»: открыл карточку, сменил представление.
 *   'replace' — уточнение того же вида: дёрнул фильтр, переключил сортировку.
 *
 * 📌 Различие не косметическое. Если каждое нажатие фильтра пишет шаг истории, то «назад»
 *    после десятка щелчков по фишкам десять раз перебирает фильтры вместо возврата на
 *    прежнюю страницу — то есть кнопка перестаёт делать то, что обещает. Адрес при этом
 *    остаётся единственным источником истины в обоих случаях: меняется только след в истории.
 */
type HistoryMode = 'push' | 'replace';

export function useUrlParam(
  key: string,
  mode: HistoryMode = 'push',
): [string | null, (v: string | null) => void] {
  const [value, setValue] = useState<string | null>(() => readParam(key));

  // Кнопки «назад»/«вперёд» меняют адрес мимо нас — подписываемся, иначе рейлы отстанут.
  useEffect(() => {
    const sync = () => setValue(readParam(key));
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, [key]);

  const set = useCallback((next: string | null) => {
    const url = new URL(window.location.href);
    const current = url.searchParams.get(key);
    if (current === next) return;
    if (next === null) url.searchParams.delete(key);
    else url.searchParams.set(key, next);
    if (mode === 'replace') window.history.replaceState({}, '', url);
    else window.history.pushState({}, '', url);
    setValue(next);
  }, [key, mode]);

  return [value, set];
}

/**
 * Значение из закрытого набора: адрес может содержать что угодно, включая мусор из
 * чужой ссылки. Неизвестное значение падает на умолчание, а не превращает страницу
 * в пустой экран без объяснения.
 */
export function useUrlEnum<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
  mode: HistoryMode = 'push',
): [T, (v: T) => void] {
  const [raw, setRaw] = useUrlParam(key, mode);
  const value = allowed.includes(raw as T) ? (raw as T) : fallback;
  const set = useCallback(
    (v: T) => setRaw(v === fallback ? null : v),
    [setRaw, fallback],
  );
  return [value, set];
}

/** То же для числового идентификатора: «мусор в адресе» не должен ломать страницу. */
export function useUrlNumber(key: string): [number | null, (v: number | null) => void] {
  const [raw, setRaw] = useUrlParam(key);
  const n = raw === null ? null : Number(raw);
  const value = Number.isFinite(n) && n !== null ? (n as number) : null;
  const set = useCallback((v: number | null) => setRaw(v === null ? null : String(v)), [setRaw]);
  return [value, set];
}
