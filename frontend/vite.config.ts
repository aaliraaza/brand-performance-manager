import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The React app is built into ../app/static so the FastAPI server (server.py) can
// serve it directly. Databricks Apps cannot run `npm` at deploy time, so the built
// assets are committed under app/static.
export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: "../app/static",
    emptyOutDir: true,
  },
  server: {
    // Local dev: proxy API calls to the FastAPI server on :8000.
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
