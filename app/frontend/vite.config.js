import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "localhost",
    port: 5173,
    strictPort: true,
    proxy: {
      "/me": "http://127.0.0.1:8000",
      "/promotion-requests": "http://127.0.0.1:8000",
    },
  },
});
