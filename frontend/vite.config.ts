import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // dev 時把 /api 打到 v5 後端
      "/api": "http://127.0.0.1:8765",
    },
  },
  build: {
    outDir: "dist",
  },
});
