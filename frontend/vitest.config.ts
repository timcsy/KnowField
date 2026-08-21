/// <reference types="vitest/config" />
import path from "path"

import { defineConfig } from "vitest/config"

// ⚠️ 測試設定獨立成檔，不塞進 vite.config.ts——那裡的 `defineConfig` 來自 "vite"，
// 型別中沒有 `test` 欄位，`npm run build`（tsc -b）會直接紅。
// 而 build 才是 Dockerfile／CI 真正跑的那條，本機用 --noEmit 驗不出來（教訓：驗證要走正式路徑）。
export default defineConfig({
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: { environment: "jsdom", include: ["src/**/*.test.ts"] },
})
