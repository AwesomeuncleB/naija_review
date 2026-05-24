import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/task-a": "http://localhost:8000",
      "/task-b": "http://localhost:8000",
      "/users":  "http://localhost:8000",
      "/businesses": "http://localhost:8000",
      "/health": "http://localhost:8000",
      "/demo":   "http://localhost:8000",
    },
  },
});
