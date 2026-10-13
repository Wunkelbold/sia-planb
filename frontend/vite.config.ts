import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const frontendRoot = fileURLToPath(new URL(".", import.meta.url));
const legalTemplatesRoot = fileURLToPath(new URL("../sia-backend/flask-server/static/templates/", import.meta.url));

const flaskProxy = {
  target: "http://127.0.0.1:5005",
  changeOrigin: true,
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    fs: { allow: [frontendRoot, legalTemplatesRoot] },
    proxy: {
      "/api": flaskProxy,
      "/static": flaskProxy,
      "/events.ics": flaskProxy,
      "/logout": flaskProxy,
      "/calendar": flaskProxy,
      "/verify_mail": flaskProxy,
      "/verify_hs_mail": flaskProxy,
      "/verify_student_membership": flaskProxy,
    },
  },
  preview: {
    host: "127.0.0.1",
    proxy: {
      "/api": flaskProxy,
      "/static": flaskProxy,
      "/events.ics": flaskProxy,
      "/logout": flaskProxy,
      "/calendar": flaskProxy,
      "/verify_mail": flaskProxy,
      "/verify_hs_mail": flaskProxy,
      "/verify_student_membership": flaskProxy,
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    restoreMocks: true,
  },
});
