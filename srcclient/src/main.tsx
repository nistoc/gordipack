import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';
import './styles.css';

const container = document.getElementById('root');
if (!container) throw new Error('не найден элемент #root');

// Внешняя ловушка — на случай, если упадёт то, что лежит ВНЕ страницы (шапка, полоса
// источника, вкладки). Внутренняя, вокруг активной страницы, до такого не достанет,
// а без внешней падение шапки снова дало бы пустой экран без единого слова.
createRoot(container).render(
  <StrictMode>
    <ErrorBoundary where="просмотрщик целиком">
      <App />
    </ErrorBoundary>
  </StrictMode>,
);
