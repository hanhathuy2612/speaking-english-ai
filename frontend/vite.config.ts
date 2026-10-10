import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies the API and the WebSocket to the FastAPI backend.
// BACKEND_URL lets agents point it at their test server (port 8001).
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": backend,
      "/ws": { target: backend.replace(/^http/, "ws"), ws: true },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
