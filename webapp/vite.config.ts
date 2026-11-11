import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
    plugins: [react()],
    base: './',          // REQUIRED — palette loads via file:// URLs
    build: {
        outDir: 'dist',
    },
    test: {
        coverage: {
            provider: 'v8',
            include: ['src/**/*.ts'],
            exclude: ['src/**/*.tsx', 'src/**/*.test.ts', 'src/main.tsx'],
            reporter: ['text', 'text-summary'],
        },
    },
})
