import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { registerSW } from "virtual:pwa-register"
import "./index.css"

// PWA 自動更新：切回 App／每小時檢查新版，有就自動換掉（autoUpdate）——改版不用手動清快取。
registerSW({
  immediate: true,
  onRegisteredSW(_swUrl, reg) {
    if (!reg) return
    const check = () => { if (document.visibilityState === "visible") reg.update() }
    document.addEventListener("visibilitychange", check)
    setInterval(() => reg.update(), 60 * 60 * 1000)
  },
})
import Layout from "./Layout"
import ChatPage from "./ChatPage"
import RootsPage from "./pages/RootsPage"
import ArticlesPage from "./pages/ArticlesPage"
import SourcesPage from "./pages/SourcesPage"
import SourcePage from "./pages/SourcePage"
import ConversationViewPage from "./pages/ConversationViewPage"
import ConversationsPage from "./pages/ConversationsPage"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ChatPage />} />
          <Route path="roots" element={<RootsPage />} />
          <Route path="articles" element={<ArticlesPage />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="source" element={<SourcePage />} />
          <Route path="conversations" element={<ConversationsPage />} />
          <Route path="conversations/:id" element={<ConversationViewPage />} />
          {/* 舊 IA → 新 IA（對話＝聊天＋存檔、來源＝知識庫＋收進） */}
          <Route path="library" element={<Navigate to="/sources" replace />} />
          <Route path="ingest" element={<Navigate to="/sources" replace />} />
          {/* 未知路徑（含舊 /chat、/app/*、手誤）→ 回首頁，不留白 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
