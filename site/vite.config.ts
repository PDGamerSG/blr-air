import { defineConfig } from "vite";
import { LINKS } from "./src/config.ts";

// Relative base so the build works from any static host or sub-path (e.g. GitHub Pages).
export default defineConfig({
  base: "./",
  plugins: [{
    name: "agent-profile-links",
    transformIndexHtml(html) {
      return html
        .replaceAll("%ASI_AGENT_URL%", LINKS.asiOne)
        .replaceAll("%AGENTVERSE_PROFILE_URL%", LINKS.agentverse);
    },
  }],
  server: { proxy: { "/api": "http://127.0.0.1:8080" } },
  preview: { proxy: { "/api": "http://127.0.0.1:8080" } },
  build: { target: "es2022", chunkSizeWarningLimit: 900 },
});
