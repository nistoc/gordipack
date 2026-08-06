import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Порт бэкенда должен совпадать с Viewer:Port в ../src (по умолчанию 5177).
// Меняешь там — поменяй и здесь, либо задай VITE_API_PORT при запуске.
//
// Объявление process — вручную и в одну строку, чтобы не тащить в черновик
// пакет @types/node ради единственного обращения к переменной среды.
declare const process: { env: Record<string, string | undefined> };
const apiPort = process.env.VITE_API_PORT ?? '5177';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    // Через прокси, а не прямыми запросами на другой порт: тогда в браузере
    // всё живёт на одном источнике и CORS в дев-режиме вообще не участвует.
    proxy: {
      '/api': {
        target: `http://127.0.0.1:${apiPort}`,
        changeOrigin: false,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
});
