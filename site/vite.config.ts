import { defineConfig } from "vite";

// Relative base so the build works from any static host or sub-path (e.g. GitHub Pages).
export default defineConfig({
  base: "./",
  server: { proxy: { "/api": "http://127.0.0.1:8080" } },
  preview: { proxy: { "/api": "http://127.0.0.1:8080" } },
  build: { target: "es2022", chunkSizeWarningLimit: 900 },
});
