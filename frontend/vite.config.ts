import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// Local dev: set VITE_PROXY_TARGET in .env.local to proxy the API to another
// engine (for example a shared test server). Defaults to a backend on :8000.
export default defineConfig(({ mode }) => {
  const target = loadEnv(mode, __dirname, "").VITE_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
  server: {
    port: 8080,
    proxy: {
      "/api": {
        target,
        changeOrigin: true,
      },
      "/version": {
        target,
        changeOrigin: true,
      },
      "/health": {
        target,
        changeOrigin: true,
      },
      "/readiness": {
        target,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    target: "es2022",
  },
};
});
