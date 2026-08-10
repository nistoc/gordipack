import { Fragment, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import type { Task } from '../types';
import { Rail, RailStrip } from '../components/Rail';
import { TaskTile } from '../components/TaskTile';
import { compareByGapThenPriority, isCriterionGap } from '../taskModel';

/**
 * ДОСКА ЗАДАЧ: колонка на роль, внутри колонки — плитки сверху вниз. ЕДИНСТВЕННОЕ
 * представление задач с 2026-08-10 (плоская таблица убрана по слову владельца).
 *
 * На какой вопрос она отвечает: «чем сейчас занята роль и где у неё дыры». Он требует
 * СРАВНЕНИЯ ролей между собой, а сравнивать в плоском списке из сотни строк нечем —
 * потому и форма такая, колонками, а не столбцом строк.
 *
 * 🔴 КОЛОНКА — ЭТО РЕЙЛ, СО ВСЕМ КАНОНОМ РЕЙЛА: своя ширина (умолчание/мин/макс), тяга
 *    мышью, ширина переживает перезагрузку, растягиваться на весь экран не умеет. Лишнее
 *    место на широком экране остаётся полем справа. Дешёвая раскладка (`grid` с долями)
 *    выглядела бы так же на моём окне и молча раздавила бы колонки на чужом.
 */
const COLUMN_RAIL = { defaultWidth: 320, minWidth: 240, maxWidth: 620 };

/**
 * Ниже этой ширины рейлы становятся одним столбцом (см. правило в styles.css), и
 * выравнивание теряет смысл: карточка задачи встаёт отдельной строкой под колонкой,
 * а отступ сверху превратился бы в дыру высотой в половину доски.
 */
const NARROW_PX = 1100;

export function TasksBoard({
  tasks,
  allTasks,
  selectedId,
  onSelect,
  detailRail,
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
  const [detailOffset, setDetailOffset] = useState(0);

  /**
   * ⚠️ БЕЗ СПИСКА ЗАВИСИМОСТЕЙ — СЧИТАЕМ ПОСЛЕ КАЖДОЙ ОТРИСОВКИ, И ЭТО ЧЕСТНЕЕ СПИСКА.
   *    Плитка уезжает по слишком многим поводам, чтобы перечислить их и не забыть ни один:
   *    сменили порядок в колонках, дёрнули фильтр, доска перечиталась опросом и над
   *    выбранной плиткой встала новая карточка, у соседней плитки заголовок перенёсся на
   *    строку больше. Забытый повод не ломает экран заметно — карточка просто стоит «на
   *    высоте», где выбранной плитки уже нет, и это читается как небрежная вёрстка, а не
   *    как ошибка, то есть не чинится годами. Здесь два замера и сравнение числа: React
   *    не перерисовывает, когда значение прежнее, а зависит оно только от плитки и полосы —
   *    не от самой карточки, — поэтому схождение наступает сразу и петли не возникает.
   */
  useLayoutEffect(() => {
    const align = () => {
      const host = rootRef.current;
      if (!host) return;
      // Узкое окно — колонки стоят одна под другой, отступ превратился бы в дыру.
      if (selectedId === null || window.innerWidth <= NARROW_PX) {
        setDetailOffset(0);
        return;
      }
      const tile = host.querySelector<HTMLElement>(`[data-item="task-${selectedId}"]`);
      const strip = host.querySelector<HTMLElement>('.railstrip');
      // Плитка могла не пройти фильтр — тогда выравнивать не по чему, и честнее
      // оставить карточку сверху, чем пристроить её к чужой плитке.
      if (!tile || !strip) {
        setDetailOffset(0);
        return;
      }

      /**
       * 🎯 ВЕСЬ РАСЧЁТ — ОДНА РАЗНОСТЬ: насколько верх плитки ниже верха полосы.
       *
       * 🔴 ОН НАМЕРЕННО НЕ СМОТРИТ НИ НА ОКНО, НИ НА ПРОКРУТКУ, НИ НА ВЫСОТУ КАРТОЧКИ.
       *    Смотрел до 2026-08-07 14:24 UTC: карточка ограничивалась по высоте и
       *    поджималась вверх, чтобы влезть в окно целиком. Владелец это отменил — внутри
       *    карточки не должно быть полос прокрутки, а без них «влезть в окно» недостижимо
       *    в принципе, сколько ни поджимай. Вместе с потолком ушла и зависимость от
       *    прокрутки: отступ теперь чисто геометрический и верен при любом положении
       *    страницы, а не только в тот миг, когда по плитке щёлкнули.
       */
      const offset = tile.getBoundingClientRect().top - strip.getBoundingClientRect().top;
      setDetailOffset(Math.max(0, Math.round(offset)));
    };

    align();
    window.addEventListener('resize', align);
    return () => window.removeEventListener('resize', align);
  });

  return (
    <div
      className="board"
      data-panel="tasks-board"
      ref={rootRef}
      // Переменной, а не стилем на самом рейле: рейл создаётся страницей задач (он общий
      // с таблицей), и доска не должна лезть в его разметку — она лишь сообщает число,
      // которое правило CSS применит только в режиме доски.
      data-detail-align={detailOffset}
      style={{ '--detail-align': `${detailOffset}px` } as React.CSSProperties}
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
