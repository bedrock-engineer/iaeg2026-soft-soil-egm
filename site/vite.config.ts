import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Served from GitHub Pages at /<repo>/, so assets need that base path.
export default defineConfig({
  base: "/iaeg2026-soft-soil-egm/",
  plugins: [react(), tailwindcss()],
  // The project geometry is read from the repo's data/ folder
  server: { fs: { allow: [".."] } },
});
