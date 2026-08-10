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

/** Сколько оставить под полосой: подвал плюс воздух. */
const BOTTOM_GAP = 96;

/**
 * ЧЕМ ОГРАНИЧЕНА ВЫСОТА РЕЙЛОВ — и почему это ДВА разных режима, а не настройка.
 *
 *   'fit'     — полоса вписана в окно: рейл упирается в измеренный потолок, и дальше
 *               прокручивается ВНУТРИ себя. Режим для полосы из одного-двух рейлов с
 *               длинным содержимым, где внутренняя прокрутка — единственная на экране.
 *               ⚠️ На 2026-08-10 такой полосы в Перископе нет ни одной: страница задач
 *               с уходом табличного вида осталась только с доской ('natural').
 *
 *   'natural' — потолка НЕТ ВОВСЕ: рейл ровно такой высоты, какого его содержимое,
 *               а прокручивается СТРАНИЦА. Так живёт доска.
 *
 * 🔴 ПОЧЕМУ ДОСКЕ ПОТОЛОК ВРЕДЕН. Колонок девять, и у самой нагруженной роли карточек
 *    вдесятеро больше, чем у самой свободной. С потолком каждая колонка получает СВОЮ
 *    внутреннюю прокрутку: чтобы сравнить две роли — а доска заводилась ровно ради
 *    сравнения — приходится прокручивать их по очереди, и обе разом в глаза не попадают
 *    никогда. Плюс девять полос прокрутки на экране, каждая со своим положением, которое
 *    не восстанавливается. Требование владельца 2026-08-07 13:46 UTC — снять потолок
 *    на доске.
 *
 * ⚠️ БЕЗ ПОТОЛКА ПОЛОСА ОБЯЗАНА ПЕРЕСТАТЬ БЫТЬ КОНТЕЙНЕРОМ ПРОКРУТКИ. Оставь ей
 *    `overflow-x: auto` — и по правилу CSS вторая ось из `visible` станет `auto`: полоса
 *    сделается прокручиваемой и по вертикали. Тогда, во-первых, горизонтальная полоска
 *    прокрутки уедет вниз вместе с концом самой длинной колонки (за три экрана от глаз),
 *    во-вторых, `position: sticky` у карточки задачи начнёт считаться от полосы, а не от
 *    окна, и перестанет работать. Поэтому в 'natural' горизонтальная прокрутка отдаётся
 *    СТРАНИЦЕ: её полоска всегда у нижнего края окна, и она одна на всё.
 */
export type StripHeightMode = 'fit' | 'natural';

export function RailStrip({
  children,
  name,
  heightMode = 'fit',
}: {
  children: ReactNode;
  name: string;
  heightMode?: StripHeightMode;
}) {
  const stripRef = useRef<HTMLDivElement | null>(null);
  const rails = useRef(new Map<string, HTMLElement>());
  const natural = heightMode === 'natural';

  /**
   * ВЫСОТА РЕЙЛОВ ИЗМЕРЯЕТСЯ, А НЕ УГАДЫВАЕТСЯ.
   *
   * 🔴 ЗАМЕР 2026-08-07 13:18 UTC, ПОЧЕМУ ЗДЕСЬ ПОЯВИЛСЯ КОД ВМЕСТО ОДНОЙ СТРОКИ CSS.
   *    Прежде высота стояла числом: `max-height: calc(100vh - 230px)`. Число было верным
   *    ровно для той раскладки, в которой его посчитали. Как только над полосой встали
   *    переключатель вида и строки фильтров, полоса начиналась уже на 464-й точке, и
   *    рейлы уходили НА 234 ТОЧКИ НИЖЕ НИЖНЕГО КРАЯ ОКНА: низ каждой колонки — вместе
   *    с концом её собственной прокрутки — оказывался недостижим. Ни ошибки, ни
   *    предупреждения: просто содержимое за краем, то есть ровно тот отказ, ради
   *    которого писан канон рейлов.
   *
   *    Константа не «была неправильной» — она устарела молча, и устареет снова при
   *    любой правке над полосой. Поэтому полоса теперь спрашивает у страницы, где она
   *    начинается, а не помнит, где начиналась когда-то.
   */
  const [maxHeight, setMaxHeight] = useState<number | null>(null);

  useLayoutEffect(() => {
    const el = stripRef.current;
    if (!el) return;
    // В 'natural' потолка нет по определению: мерить его — значит завести переменную,
    // которую никто не читает, и наблюдателя, который просыпается на каждый рост доски.
    if (natural) {
      setMaxHeight(null);
      return;
    }

    let last = 0;
    const measure = () => {
      const top = el.getBoundingClientRect().top;
      const next = Math.max(240, Math.round(window.innerHeight - top - BOTTOM_GAP));
      // Порог в две точки — против дребезга: правка высоты меняет высоту страницы,
      // та будит наблюдателя, и без порога пара близких значений мигала бы вечно.
      if (Math.abs(next - last) < 2) return;
      last = next;
      setMaxHeight(next);
    };

    measure();
    window.addEventListener('resize', measure);
    const observer = new ResizeObserver(measure);
    observer.observe(document.body);
    return () => {
      window.removeEventListener('resize', measure);
      observer.disconnect();
    };
  }, [natural]);

  const register = useCallback((el: HTMLElement | null, id: string) => {
    if (el) rails.current.set(id, el);
    else rails.current.delete(id);
  }, []);

  const revealRail = useCallback((id: string) => {
    const el = rails.current.get(id);
    const strip = stripRef.current;
    if (!el || !strip) return;
    const a = el.getBoundingClientRect();
    /**
     * ⚠️ С ЧЕМ СРАВНИВАТЬ «ВИДЕН ЛИ РЕЙЛ» — ЗАВИСИТ ОТ ТОГО, КТО ПРОКРУЧИВАЕТ.
     * В 'fit' прокручивается полоса, и края видимого — её собственные края. В 'natural'
     * прокручивается страница, а полоса шире окна и НИКОГДА себя не обрезает: сравнение
     * с её краями всегда давало бы «всё видно», и рейл, уехавший за правый край ОКНА,
     * молча не показывался бы. Один и тот же код при этом «работает» в обоих режимах —
     * ровно тот отказ, который видно только глазами.
     */
    const b = natural
      ? { left: 0, right: window.innerWidth }
      : strip.getBoundingClientRect();
    // Обрезан хотя бы с одной стороны — подвинуть минимально, а не «в начало».
    if (a.left < b.left - 1 || a.right > b.right + 1) {
      el.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' });
    }
  }, [natural]);

  /**
   * Колесо над «тихим» местом двигает полосу вбок. Если под курсором есть что
   * прокручивать вертикально — колесо остаётся колесом: перехватывать его там значит
   * отнимать у человека привычное движение.
   */
  const onWheel = useCallback((e: React.WheelEvent) => {
    const strip = stripRef.current;
    if (!strip) return;
    /**
     * 🔴 В 'natural' КОЛЕСО НЕ ТРОГАЕМ ВООБЩЕ. Там полоса не прокручивается — прокручивается
     * страница, и перехват означал бы `preventDefault()` на движении, которое взамен не
     * делает ничего: колесо над доской просто перестало бы листать. Доска при этом выше
     * трёх экранов, то есть листание — единственный способ её увидеть.
     */
    if (natural) return;
    if (e.deltaY === 0 || e.shiftKey) return;
    if (strip.scrollWidth <= strip.clientWidth + 1) return;

    /**
     * 🔴 НАД КАРТОЧКОЙ ЗАДАЧИ КОЛЕСО ВСЕГДА ОСТАЁТСЯ КОЛЕСОМ.
     *
     * У карточки с 2026-08-07 14:24 UTC нет ни потолка высоты, ни собственной прокрутки:
     * она бывает в восемь тысяч точек и листается СТРАНИЦЕЙ. Перебор ниже ищет под
     * курсором что-нибудь прокручиваемое по вертикали и, не найдя, отдаёт колесо
     * горизонтали — то есть ровно над длинной карточкой листание вниз перестало бы
     * работать, а вместо него полоса поехала бы вбок. Отказ тихий вдвойне: и колесо
     * «отвечает», и полоса движется — просто не туда, куда человек смотрит.
     */
    if ((e.target as HTMLElement).closest?.('.rail--detail')) return;

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
  }, [natural]);

  return (
    <Ctx.Provider value={{ register, revealRail }}>
      <div
        ref={stripRef}
        className={`railstrip ${natural ? 'railstrip--natural' : ''}`}
        data-panel={`railstrip-${name}`}
        data-height-mode={heightMode}
        onWheel={onWheel}
        // Переменной, а не прямой высотой на рейле: инлайновый стиль победил бы правило
        // узкого экрана, где рейлы намеренно тянутся во всю высоту.
        style={maxHeight === null ? undefined : ({ '--rail-max-h': `${maxHeight}px` } as React.CSSProperties)}
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
  className,
  revealOnMount = true,
  children,
}: {
  id: string;
  title: string;
  defaultWidth: number;
  minWidth: number;
  maxWidth: number;
  onClose?: () => void;
  toolbar?: ReactNode;
  className?: string;
  /**
   * Показать рейл целиком сразу после появления.
   *
   * ⚠️ ВЫКЛЮЧАТЬ, КОГДА РЕЙЛОВ ПОЯВЛЯЕТСЯ СРАЗУ МНОГО. Уместно это ровно для рейла,
   *    который человек ТОЛЬКО ЧТО открыл: он показал, куда смотрит. Когда одним махом
   *    встают десять колонок доски, каждая просит показать себя, побеждает последняя —
   *    и доска открывается прокрученной к самой правой роли, мимо начала. Умолчание
   *    оставлено прежним, чтобы поведение карточки не поменялось молча.
   */
  revealOnMount?: boolean;
  children: ReactNode;
}) {
  const ctx = useContext(Ctx);
  const ref = useRef<HTMLElement | null>(null);
  const [width, setWidth] = useState(() => loadWidth(id, defaultWidth, minWidth, maxWidth));
  /**
   * Состояние перетаскивания. `last` — последняя ПОСЧИТАННАЯ ширина, и она здесь
   * не для удобства.
   *
   * 🔴 ЗАМЕР 2026-08-07 13:26 UTC. Прежде отпускание кнопки сохраняло `width` из
   *    состояния — то есть значение ТОГО кадра, в котором обработчик был создан.
   *    Если последнее движение и отпускание попадали в одну порцию обновлений (быстрый
   *    рывок мышью — обычное дело), кадр между ними не успевал случиться, и в память
   *    ложилась ширина ДО перетаскивания: на экране колонка 440, в памяти 320, после
   *    перезагрузки снова 320. Проверено прямой посылкой событий: сохранилось 320 при
   *    показанных 440. Ошибка тихая — она видна только через перезагрузку, а на неё
   *    списывают «не сохранилось, ну ладно».
   *
   *    Значение в ссылке не зависит от кадров вовсе, поэтому гонки больше нет.
   */
  const drag = useRef<{ x: number; w: number; last: number } | null>(null);

  useLayoutEffect(() => {
    ctx?.register(ref.current, id);
    return () => ctx?.register(null, id);
  }, [ctx, id]);

  // Новый рейл показываем целиком: прежние уезжают влево, но НЕ сжимаются.
  useEffect(() => {
    if (!revealOnMount) return;
    const t = setTimeout(() => ctx?.revealRail(id), 30);
    return () => clearTimeout(t);
  }, [ctx, id, revealOnMount]);

  const onPointerDown = (e: ReactPointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { x: e.clientX, w: width, last: width };
  };

  const onPointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    const next = Math.min(maxWidth, Math.max(minWidth, drag.current.w + (e.clientX - drag.current.x)));
    drag.current.last = next;
    setWidth(next);
  };

  const onPointerUp = (e: ReactPointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    drag.current = null;
    try { (e.target as HTMLElement).releasePointerCapture(e.pointerId); } catch { /* уже отпущен */ }
    // Из ссылки, а не из состояния — см. объявление drag.
    saveWidth(id, d.last);
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
      className={`rail ${className ?? ''}`}
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
