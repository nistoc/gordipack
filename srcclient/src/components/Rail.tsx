import {
  createContext, useCallback, useContext, useEffect, useLayoutEffect, useRef, useState,
} from 'react';
import type { ReactNode, PointerEvent as ReactPointerEvent } from 'react';

/**
 * ГОРИЗОНТАЛЬНАЯ ПОЛОСА РЕЙЛОВ — рабочее пространство, а не разовый сплит экрана.
 *
 * 🔴 ГЛАВНОЕ ПРАВИЛО, РАДИ КОТОРОГО ВСЁ ЭТО СУЩЕСТВУЕТ:
 *    новый рейл добавляется РЯДОМ с прежним содержимым, а не ВЫРЕЗАЕТСЯ из него.
 *    Таблица, показывавшая семь колонок, обязана показывать их и после появления рейла.
 *    Дешёвый способ («поделим строку 50/50») компилируется, проходит тесты — и молча
 *    прячет половину колонок за горизонтальной прокруткой. Данные на месте, увидеть их нельзя.
 *
 * Поэтому: каждый рейл несёт СВОЮ ширину (flex: 0 0 <w>), а не долю контейнера;
 * полоса при нехватке места прокручивается по горизонтали; лишнее место остаётся
 * пустым полем справа, а не растягивает рейлы.
 */

type StripCtx = {
  register: (el: HTMLElement | null, id: string) => void;
  revealRail: (id: string) => void;
};

const Ctx = createContext<StripCtx | null>(null);

/** Ширина рейла живёт в localStorage: человек настраивает рабочее место один раз. */
function loadWidth(key: string, fallback: number, min: number, max: number): number {
  try {
    const raw = localStorage.getItem(`rail.w.${key}`);
    if (!raw) return fallback;
    const n = Number(raw);
    if (!Number.isFinite(n)) return fallback;
    return Math.min(max, Math.max(min, n));
  } catch {
    return fallback;
  }
}

function saveWidth(key: string, w: number) {
  try {
    localStorage.setItem(`rail.w.${key}`, String(Math.round(w)));
  } catch {
    /* приватный режим браузера — ширина просто не переживёт перезагрузку */
  }
}

export function RailStrip({ children, name }: { children: ReactNode; name: string }) {
  const stripRef = useRef<HTMLDivElement | null>(null);
  const rails = useRef(new Map<string, HTMLElement>());

  const register = useCallback((el: HTMLElement | null, id: string) => {
    if (el) rails.current.set(id, el);
    else rails.current.delete(id);
  }, []);

  const revealRail = useCallback((id: string) => {
    const el = rails.current.get(id);
    const strip = stripRef.current;
    if (!el || !strip) return;
    const a = el.getBoundingClientRect();
    const b = strip.getBoundingClientRect();
    // Обрезан хотя бы с одной стороны — подвинуть минимально, а не «в начало».
    if (a.left < b.left - 1 || a.right > b.right + 1) {
      el.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' });
    }
  }, []);

  /**
   * Колесо над «тихим» местом двигает полосу вбок. Если под курсором есть что
   * прокручивать вертикально — колесо остаётся колесом: перехватывать его там значит
   * отнимать у человека привычное движение.
   */
  const onWheel = useCallback((e: React.WheelEvent) => {
    const strip = stripRef.current;
    if (!strip) return;
    if (e.deltaY === 0 || e.shiftKey) return;
    if (strip.scrollWidth <= strip.clientWidth + 1) return;

    let node = e.target as HTMLElement | null;
    while (node && node !== strip) {
      const canScrollY = node.scrollHeight > node.clientHeight + 1;
      if (canScrollY) {
        const style = getComputedStyle(node);
        if (/(auto|scroll)/.test(style.overflowY)) {
          const atTop = node.scrollTop <= 0;
          const atBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 1;
          const wantsUp = e.deltaY < 0;
          // Уже упёрлись в край — вертикали больше нет, отдаём горизонтали.
          if (!((wantsUp && atTop) || (!wantsUp && atBottom))) return;
        }
      }
      node = node.parentElement;
    }
    strip.scrollLeft += e.deltaY;
    e.preventDefault();
  }, []);

  return (
    <Ctx.Provider value={{ register, revealRail }}>
      <div
        ref={stripRef}
        className="railstrip"
        data-panel={`railstrip-${name}`}
        onWheel={onWheel}
      >
        {children}
      </div>
    </Ctx.Provider>
  );
}

export function Rail({
  id,
  title,
  defaultWidth,
  minWidth,
  maxWidth,
  onClose,
  toolbar,
  children,
}: {
  id: string;
  title: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  onClose?: () => void;
  toolbar?: ReactNode;
  children: ReactNode;
}) {
  const ctx = useContext(Ctx);
  const ref = useRef<HTMLElement | null>(null);
  const [width, setWidth] = useState(() => loadWidth(id, defaultWidth, minWidth, maxWidth));
  const drag = useRef<{ x: number; w: number } | null>(null);

  useLayoutEffect(() => {
    ctx?.register(ref.current, id);
    return () => ctx?.register(null, id);
  }, [ctx, id]);

  // Новый рейл показываем целиком: прежние уезжают влево, но НЕ сжимаются.
  useEffect(() => {
    const t = setTimeout(() => ctx?.revealRail(id), 30);
    return () => clearTimeout(t);
  }, [ctx, id]);

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, w: width };
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const next = Math.min(maxWidth, Math.max(minWidth, drag.current.w + (e.clientX - drag.current.x)));
    setWidth(next);
  };

  const onPointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    drag.current = null;
    try { (e.target as HTMLElement).releasePointerCapture(e.pointerId); } catch { /* уже отпущен */ }
    saveWidth(id, width);
  };

  // Клик по обрезанному рейлу открывает его целиком: человек показал, где хочет работать.
  // Ручку изменения ширины исключаем — закончить перетаскивание не значит «перейти сюда».
  const onClick = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('[data-control="rail-resize"]')) return;
    ctx?.revealRail(id);
  };

  return (
    <section
      ref={ref as React.RefObject<HTMLElement>}
      className="rail"
      style={{ flex: `0 0 ${width}px`, maxWidth: `${maxWidth}px` }}
      data-panel={`rail-${id}`}
      data-rail-width={Math.round(width)}
      onClick={onClick}
    >
      <header className="rail__head" data-group={`rail-head-${id}`}>
        <h3 className="rail__title">{title}</h3>
        <div className="rail__actions">
          {toolbar}
          {onClose && (
            <button
              className="btn btn--ghost"
              onClick={onClose}
              data-control={`rail-close-${id}`}
              title="закрыть рейл"
            >
              ✕
            </button>
          )}
        </div>
      </header>

      <div className="rail__body" data-group={`rail-body-${id}`}>
        {children}
      </div>

      <div
        className="rail__resize"
        data-control="rail-resize"
        title="потянуть — изменить ширину; ширина запомнится"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
      />
    </section>
  );
}
