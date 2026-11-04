import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { TanStackRouterVite } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    TanStackRouterVite({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  envDir: path.resolve(import.meta.dirname, ".."),
  server: {
    port: Number(process.env.FRONTEND_PORT),
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: process.env.BACKEND_PROXY_TARGET,
        changeOrigin: true,
      },
    },
  },
});
