import { Fragment, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { Task } from '../types';
import { Rail, RailStrip } from '../components/Rail';
import { TaskTile } from '../components/TaskTile';
import { compareByGapThenPriority, isCriterionGap } from '../taskModel';

/**
 * ДОСКА ЗАДАЧ: колонка на роль, внутри колонки — плитки сверху вниз.
 *
 * Зачем она рядом с таблицей, а не вместо неё. Таблица отвечает на вопрос «покажи мне
 * все карточки и дай отсортировать» — по одному полю за раз, глазами вдоль столбца.
 * Вопрос «чем сейчас занята роль и где у неё дыры» она не отвечает вовсе: он требует
 * СРАВНЕНИЯ ролей между собой, а сравнивать в плоском списке из сотни строк нечем.
 * Доска отвечает именно на него — и потому добавлена, а не заменила: два вопроса,
 * два инструмента.
 *
 * 🔴 КОЛОНКА — ЭТО РЕЙЛ, СО ВСЕМ КАНОНОМ РЕЙЛА: своя ширина (умолчание/мин/макс), тяга
 *    мышью, ширина переживает перезагрузку, растягиваться на весь экран не умеет. Лишнее
 *    место на широком экране остаётся полем справа. Дешёвая раскладка (`grid` с долями)
 *    выглядела бы так же на моём окне и молча раздавила бы колонки на чужом.
 */
const COLUMN_RAIL = { defaultWidth: 320, minWidth: 240, maxWidth: 620 };

/** Воздух между карточкой задачи и краем окна, когда карточку приходится поджимать. */
const EDGE_GAP = 12;

/**
 * Ниже этой ширины рейлы становятся одним столбцом (см. правило в styles.css), и
 * выравнивание теряет смысл: карточка задачи встаёт отдельной строкой под колонкой,
 * а отступ сверху превратился бы в дыру высотой в половину доски.
 */
const NARROW_PX = 1100;

/**
 * Ниже этого карточку не сжимаем, даже если места в окне меньше. Низкое окно — не повод
 * превратить карточку в щель: пусть лучше её низ уйдёт за край, чем на экране останется
 * рамка с шапкой и без содержимого.
 */
const MIN_DETAIL_H = 320;

export function TasksBoard({
  tasks,
  allTasks,
  selectedId,
  onSelect,
  detailRail,
  detailPhase,
  order = compareByGapThenPriority,
  nowMs,
}: {
  /** Карточки, прошедшие фильтры, — ровно то, что станет плитками. */
  tasks: Task[];
  /** Полный набор: нужен для честного «показано из всего у роли» и для счёта подзадач. */
  allTasks: Task[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
  /** Рейл открытой карточки. Ставится СРАЗУ ЗА колонкой её роли — см. ниже. */
  detailRail?: ReactNode;
  /**
   * Отпечаток СОДЕРЖИМОГО открытой карточки: меняется, когда карточка догрузилась
   * с сервера и её высота стала настоящей.
   *
   * 🔴 ЗАЧЕМ ОТДЕЛЬНАЯ СТРОКА, А НЕ ОДИН `ResizeObserver` ПО РЕЙЛУ. Наблюдатель размера
   *    будит браузер В ХОДЕ ОТРИСОВКИ КАДРА. Пока вкладку не показывают, кадров нет —
   *    и наблюдатель молчит: замер 2026-08-07 15:59 UTC на неотрисовываемой вкладке дал
   *    НОЛЬ срабатываний, выравнивание так и осталось посчитанным по высоте надписи
   *    «читаю карточку…», то есть по пустоте. Наблюдатель оставлен как страховка на
   *    поздние изменения размера, но ГЛАВНЫЙ повод пересчитать приходит сюда явным
   *    значением — оно не зависит ни от кадров, ни от видимости вкладки.
   */
  detailPhase?: string;
  /**
   * Порядок плиток ВНУТРИ колонки. Порядок самих колонок он не трогает: колонки стоят
   * от самой нагруженной роли к самой свободной, и это ответ доски на свой вопрос
   * «у кого сколько» — сортировка плиток на него не влияет.
   */
  order?: (a: Task, b: Task) => number;
  nowMs: number;
}) {
  // Кто чей родитель. Считаем по ПОЛНОМУ набору: подзадача могла не пройти фильтр,
  // но связь от этого не исчезла, и «подзадач: 0» на родителе было бы неправдой.
  const childCounts = useMemo(() => {
    const m = new Map<number, number>();
    for (const t of allTasks) {
      if (t.parentId === null) continue;
      m.set(t.parentId, (m.get(t.parentId) ?? 0) + 1);
    }
    return m;
  }, [allTasks]);

  const roleTotals = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of allTasks) {
      const r = t.role ?? '—';
      m.set(r, (m.get(r) ?? 0) + 1);
    }
    return m;
  }, [allTasks]);

  /**
   * Колонки — от самой нагруженной роли к самой свободной.
   *
   * 📌 Не по алфавиту: доска отвечает на вопрос «у кого сколько», и ответ должен читаться
   *    формой самой доски, слева направо, ещё до того как человек прочтёт хоть одно число.
   *    При равенстве — по имени, чтобы порядок не прыгал случайно между обновлениями.
   */
  const columns = useMemo(() => {
    const byRole = new Map<string, Task[]>();
    for (const t of tasks) {
      const r = t.role ?? '—';
      const list = byRole.get(r);
      if (list) list.push(t);
      else byRole.set(r, [t]);
    }
    return [...byRole.entries()]
      // Сортируется СОДЕРЖИМОЕ колонки; сам порядок колонок ниже — по числу карточек.
      .map(([role, list]) => ({ role, list: [...list].sort(order) }))
      .sort((a, b) => b.list.length - a.list.length || a.role.localeCompare(b.role, 'ru'));
  }, [tasks, order]);

  /**
   * Роли, у которых карточки есть, но под текущий фильтр не попало ни одной.
   * Колонку им не рисуем — но и молчать нельзя: пропавшая колонка иначе читается как
   * «у роли вообще нет задач». Это тот же класс лжи, что ноль вместо «нечем посчитать».
   */
  const rolesFilteredOut = useMemo(() => {
    const shown = new Set(columns.map((c) => c.role));
    return [...roleTotals.keys()].filter((r) => !shown.has(r)).sort();
  }, [columns, roleTotals]);

  const selected = useMemo(
    () => (selectedId === null ? null : allTasks.find((t) => t.id === selectedId) ?? null),
    [allTasks, selectedId],
  );

  /**
   * За какой колонкой встанет рейл открытой карточки.
   *
   * ⚠️ Не «в конец полосы», и это осознанно. Колонок бывает десяток, полоса шире экрана
   *    в полтора-два раза; рейл в конце заставил бы полосу улететь мимо всей доски к
   *    правому краю — человек щёлкнул по плитке слева, а доска показала ему совсем другое
   *    место. Рейл встаёт вплотную к колонке, из которой карточку открыли: «рядом» здесь
   *    буквально, а не фигурально.
   */
  const detailAfterRole = selected && columns.some((c) => c.role === (selected.role ?? '—'))
    ? selected.role ?? '—'
    : columns.length > 0 ? columns[columns.length - 1].role : null;

  const rootRef = useRef<HTMLDivElement | null>(null);
  const hasDetail = detailRail !== null && detailRail !== undefined;

  /**
   * НА КАКОЙ ВЫСОТЕ НАЧИНАЕТСЯ РЕЙЛ ОТКРЫТОЙ КАРТОЧКИ — отступ сверху в точках.
   *
   * 🎯 Требование владельца 2026-08-07 13:46 UTC: «подробную карточку задачи показывай
   *    на той же высоте что и выбранная карточка задачи в колонке». Колонка теперь растёт
   *    без потолка и бывает выше трёх экранов; карточка, всегда начинающаяся у самого
   *    верха доски, при щелчке по плитке в середине колонки открывалась бы ЗА КРАЕМ ЭКРАНА,
   *    и человек видел бы… ничего. Формально «карточка открыта», по сути — пусто.
   *
   * ⚠️ ЧИСЛО ИЗМЕРЯЕТСЯ, А НЕ ВЫЧИСЛЯЕТСЯ ИЗ ЧИСЛА ПЛИТОК. Высота плитки не постоянна:
   *    заголовок бывает в одну строку и в три, критерий приёмки — в ноль строк и в две,
   *    ниже бывают метки и связь с родителем. «Номер плитки × высоту» дало бы верный ответ
   *    ровно на однородных данных и молча мазало бы мимо на живых.
   */
  const [detailBox, setDetailBox] = useState<{ offset: number; maxHeight: number | null }>(
    { offset: 0, maxHeight: null },
  );

  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const reset = () => setDetailBox({ offset: 0, maxHeight: null });
    if (selectedId === null) {
      reset();
      return;
    }

    const align = () => {
      const host = rootRef.current;
      if (!host) return;
      const tile = host.querySelector<HTMLElement>(`[data-item="task-${selectedId}"]`);
      const detail = host.querySelector<HTMLElement>('.rail--detail');
      const strip = host.querySelector<HTMLElement>('.railstrip');
      // Плитка могла не пройти фильтр — тогда выравнивать не по чему, и честнее
      // оставить карточку сверху, чем пристроить её к чужой плитке.
      // Узкое окно — колонки стоят одна под другой, выравнивание бессмысленно.
      if (!tile || !detail || !strip || window.innerWidth <= NARROW_PX) {
        reset();
        return;
      }

      const winH = window.innerHeight;
      const stripTop = strip.getBoundingClientRect().top;  // край полосы В ОКНЕ, с учётом прокрутки
      const tileTop = tile.getBoundingClientRect().top;

      /**
       * ⚠️ ВЫСОТА КАРТОЧКИ БЕРЁТСЯ СОБСТВЕННАЯ, А НЕ ИЗМЕРЕННАЯ ЛИНЕЙКОЙ ПО ЭКРАНУ.
       *    Ниже мы сами ограничиваем высоту рейла — и если бы считали по видимой высоте,
       *    ограничение вошло бы в собственный расчёт: уже, потом ещё уже, потом ещё.
       *    Высота содержимого от ограничения не зависит, и петли поэтому нет.
       */
      const head = detail.querySelector<HTMLElement>('.rail__head');
      const body = detail.querySelector<HTMLElement>('.rail__body');
      const naturalH = (head?.offsetHeight ?? 0) + (body?.scrollHeight ?? 0) + 2;

      /**
       * 🔴 ТРИ ГРАНИЦЫ, МЕЖДУ КОТОРЫМИ ЖИВЁТ ВЕРХ КАРТОЧКИ.
       *   1) не выше начала полосы — отрицательный отступ залез бы на строки фильтров;
       *   2) не выше края окна;
       *   3) не настолько низко, чтобы низ карточки ушёл под нижний край окна.
       * Выравнивание по плитке — ПРЕДПОЧТЕНИЕ внутри этих границ, а не закон: выбери
       * плитку у самого низа длинной колонки — и честно выровненная карточка показала бы
       * одну свою шапку, а всё остальное осталось бы за краем экрана.
       */
      const ceiling = Math.max(EDGE_GAP, stripTop);
      const wanted = Math.max(tileTop, ceiling);

      /**
       * СНАЧАЛА ПРОБУЕМ УДЕРЖАТЬ ТОЧНОЕ СОВПАДЕНИЕ ВЫСОТ, ПЛАТЯ ВЫСОТОЙ САМОЙ КАРТОЧКИ.
       * Карточка не обязана быть во весь свой рост: длинное описание прокручивается
       * внутри неё. Пока под плиткой остаётся сколько-нибудь пригодное место, совпадение
       * сохраняется полностью — глазу не приходится искать, куда уехали подробности.
       */
      let topInWindow = wanted;
      let room = winH - EDGE_GAP - topInWindow;

      /**
       * 🔴 И ТОЛЬКО ЕСЛИ МЕСТА МЕНЬШЕ, ЧЕМ НУЖНО НА ЧИТАЕМУЮ КАРТОЧКУ, — ПОДЖИМАЕМ ВВЕРХ.
       *    Это и есть край из требования владельца: плитка у самого низа длинной колонки.
       *    Замер 2026-08-07 16:09 UTC ДО этой ветки: карточка честно вставала на высоту
       *    плитки (726) и уходила нижним краем на 96 точек ЗА нижнюю границу окна —
       *    видно было три четверти рамки, а низ приходилось искать прокруткой. Совпадение
       *    высот тут уступает: «видно целиком» важнее, чем «ровно напротив».
       */
      if (room < MIN_DETAIL_H) {
        topInWindow = Math.max(ceiling, winH - EDGE_GAP - MIN_DETAIL_H);
        room = winH - EDGE_GAP - topInWindow;
      }

      // Ниже 120 не опускаемся ни при каком окне: рамка без строки текста — не карточка.
      const maxHeight = Math.max(120, Math.round(Math.min(naturalH, room)));

      setDetailBox({ offset: Math.max(0, Math.round(topInWindow - stripTop)), maxHeight });
    };

    align();

    /**
     * Наблюдатель размера — СТРАХОВКА, а не главный повод пересчитать: он срабатывает в
     * ходе отрисовки кадра, а на неотрисовываемой вкладке кадров нет. Главный повод
     * приходит значением `detailPhase` из страницы задач (см. его описание).
     */
    const detail = root.querySelector<HTMLElement>('.rail--detail');
    const observer = new ResizeObserver(align);
    if (detail) observer.observe(detail);
    window.addEventListener('resize', align);
    return () => {
      observer.disconnect();
      window.removeEventListener('resize', align);
    };
    // `order` в списке не ради самой сортировки, а ради выравнивания: сменив порядок,
    // человек двигает плитку, и карточка обязана переехать за ней — иначе она останется
    // «на высоте», где выбранной плитки уже нет.
  }, [selectedId, hasDetail, detailPhase, order]);

  return (
    <div
      className="board"
      data-panel="tasks-board"
      ref={rootRef}
      // Переменной, а не стилем на самом рейле: рейл создаётся страницей задач (он общий
      // с таблицей), и доска не должна лезть в его разметку — она лишь сообщает число,
      // которое правило CSS применит только в режиме доски.
      data-detail-align={detailBox.offset}
      data-detail-maxh={detailBox.maxHeight ?? ''}
      style={{
        '--detail-align': `${detailBox.offset}px`,
        '--detail-maxh': detailBox.maxHeight === null ? 'none' : `${detailBox.maxHeight}px`,
      } as React.CSSProperties}
    >
      {columns.length === 0 && (
        <p className="muted" data-panel="board-empty">под фильтр не попало ни одной карточки</p>
      )}

      {rolesFilteredOut.length > 0 && (
        <p className="muted small board__note" data-group="board-roles-filtered-out">
          под фильтр не попало ни одной карточки у ролей: {rolesFilteredOut.join(', ')} —
          колонки нет не потому, что задач нет, а потому, что их отсеял фильтр
        </p>
      )}

      {/* 'natural' — потолка высоты у колонок нет вовсе, прокручивается страница.
          Требование владельца 2026-08-07 13:46 UTC; подробности — в Rail.tsx. */}
      <RailStrip name="tasks-board" heightMode="natural">
        {columns.map(({ role, list }) => {
          const gaps = list.filter(isCriterionGap).length;
          const total = roleTotals.get(role) ?? list.length;
          return [
            <Rail
              key={`col-${role}`}
              id={`board-${role}`}
              title={role}
              className="rail--column"
              revealOnMount={false}
              {...COLUMN_RAIL}
              toolbar={
                <span className="colcount" data-control={`board-count-${role}`}>
                  <b>{list.length}</b>
                  {list.length !== total && (
                    <span className="muted" title={`всего карточек у роли в базе: ${total}`}>
                      {' '}/ {total}
                    </span>
                  )}
                  {gaps > 0 && (
                    <span
                      className="colcount__gap"
                      title="из них без критерия приёмки"
                      data-control={`board-gaps-${role}`}
                    >
                      ⚠ {gaps}
                    </span>
                  )}
                </span>
              }
            >
              {/* data-count здесь — чтобы число плиток можно было сверить с базой
                  машинально, не считая карточки глазами по снимку экрана. */}
              <div
                className="tiles"
                data-list={`board-tiles-${role}`}
                data-group={`board-column-${role}`}
                data-role={role}
                data-count={list.length}
              >
                {list.map((t) => (
                  <TaskTile
                    key={t.id}
                    task={t}
                    selected={selectedId === t.id}
                    childCount={childCounts.get(t.id) ?? 0}
                    onOpen={() => onSelect(selectedId === t.id ? null : t.id)}
                    onOpenParent={(pid) => onSelect(pid)}
                    nowMs={nowMs}
                  />
                ))}
              </div>
            </Rail>,
            // Обёртка — Fragment, а не div: любой лишний узел между полосой и рейлом
            // стал бы элементом флекса вместо самого рейла, и ширина рейла перестала
            // бы что-либо значить. Ровно так рейлы и «схлопываются» незаметно.
            detailRail && detailAfterRole === role
              ? <Fragment key={`detail-${role}`}>{detailRail}</Fragment>
              : null,
          ];
        })}
      </RailStrip>
    </div>
  );
}
