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

export function useUrlParam(key: string): [string | null, (v: string | null) => void] {
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
    // Именно push, а не replace: открытие карточки — шаг, на который человек ждёт «назад».
    window.history.pushState({}, '', url);
    setValue(next);
  }, [key]);

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
