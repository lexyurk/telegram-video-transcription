import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: './index.html',
        privacy: './privacy.html',
        support: './support.html',
        terms: './terms.html'
      }
    }
  },
  define: {
    'import.meta.env.VITE_TELEGRAM_BOT_USERNAME': JSON.stringify(process.env.VITE_TELEGRAM_BOT_USERNAME || ''),
    'import.meta.env.VITE_WEBSITE_URL': JSON.stringify(process.env.VITE_WEBSITE_URL || '')
  }
});

