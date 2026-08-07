import path from "path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { VitePWA } from "vite-plugin-pwa"

// https://vite.dev/config/
export default defineConfig({
  // FastAPI 把 SPA 掛在根 /（retire 完成、舊 Jinja 已退役）
  base: "/",
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "icon.svg"],
      // SPA fallback 別攔真實端點：/api、/media（PDF/圖）、匯出、帶副檔名的檔案——否則 iframe/直連拿到 index.html
      workbox: {
        navigateFallbackDenylist: [/^\/api\//, /^\/media\//, /\/export(\?|$)/, /\.[^/]+$/],
      },
      manifest: {
        name: "KnowField — 反逢迎的知識副手",
        short_name: "KnowField",
        description: "站在你的知識場上、幫你挖到底、且不順著你說好聽話的當下副手。",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#faf7f0",
        theme_color: "#1c1917",
        icons: [
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
          { src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "maskable" },
        ],
        // 手機分享網頁進 App（Android Web Share Target）
        share_target: {
          action: "/share-target",
          method: "POST",
          enctype: "multipart/form-data",
          params: { title: "title", text: "text", url: "url" },
        },
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    // 開發時把 /api 轉給 FastAPI（後端 JSON API）
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
})
