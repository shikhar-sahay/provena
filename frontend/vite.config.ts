import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev-only proxy so the shell can call the API without CORS setup.
// Production builds call VITE_API_URL (see .env.example).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
