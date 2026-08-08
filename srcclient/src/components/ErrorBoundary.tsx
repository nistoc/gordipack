import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';

/**
 * ЛОВУШКА ОШИБОК ОТРИСОВКИ — чтобы поломка НИКОГДА не выглядела как пустая страница.
 *
 * 🔴 ЗАЧЕМ ЭТО ЗДЕСЬ (замер, а не предосторожность вообще). 2026-08-08 23:26 UTC
 *    страница «Схема» показывала пустой тёмный экран: ноль элементов в #root, ноль
 *    символов текста. Причина — одно неверное имя поля в описании ответа сервиса
 *    (`presentButUnknownToViewer` вместо `presentButUnknownToPeriscope`), из-за чего
 *    `undefined.length` бросал исключение прямо во время отрисовки. React в таком
 *    случае СНИМАЕТ ВСЁ ДЕРЕВО с экрана — не только сломанную страницу, а вкладки,
 *    шапку и подвал вместе с ней. Сообщение остаётся только в консоли браузера,
 *    куда владелец не смотрит и смотреть не обязан.
 *
 * ⚠️ Само имя поля починено отдельно — это лечение ПРИЧИНЫ. Ловушка лечит другое и
 *    не менее важное: КЛАСС отказа. Пустой экран неотличим от «данных нет», и пока
 *    он молчит, любая следующая такая опечатка снова будет выглядеть как норма.
 *    Здесь она выглядит как ошибка — с текстом, местом и кнопкой перезагрузки.
 *
 * 📌 Границ две, и это не дублирование: внешняя (вокруг всего приложения) спасает от
 *    падения шапки или полосы источника, внутренняя (вокруг активной страницы) даёт
 *    упавшей странице упасть ОДНОЙ — вкладки остаются на месте, и человек может уйти
 *    на соседнюю страницу, а не перезагружать браузер.
 */
interface Props {
  /** Что упало — словами человека, для заголовка сообщения. */
  where: string;
  children: ReactNode;
}

interface State {
  error: Error | null;
  stack: string | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, stack: null };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Консоль остаётся — она нужна тому, кто чинит. Экран получает то же самое,
    // потому что он нужен тому, кто пользуется.
    console.error(`[Перископ] отрисовка не удалась: ${this.props.where}`, error, info);
    this.setState({ stack: info.componentStack ?? null });
  }

  private reset = () => this.setState({ error: null, stack: null });

  render() {
    const { error, stack } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="banner banner--error" data-panel="render-error">
        <strong>Не удалось отрисовать: {this.props.where}.</strong>
        <div className="small" style={{ marginTop: 6 }}>
          Это ошибка самого просмотрщика, а не признак того, что в базе пусто.
          Данные могли прийти в форме, которой интерфейс не ожидал.
        </div>
        <pre className="pre pre--inline" style={{ marginTop: 8 }} data-item="render-error-text">
          {error.message}
          {stack ? `\n${stack.trim()}` : ''}
        </pre>
        <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
          <button className="btn btn--ghost" onClick={this.reset} data-control="render-error-retry">
            Попробовать снова
          </button>
          <button
            className="btn btn--ghost"
            onClick={() => window.location.reload()}
            data-control="render-error-reload"
          >
            Перезагрузить страницу
          </button>
        </div>
      </div>
    );
  }
}
