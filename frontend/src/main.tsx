import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Navigate, Route, Routes, useParams, useSearchParams } from "react-router-dom"
import { registerSW } from "virtual:pwa-register"
import "./index.css"

// PWA 自動更新：切回 App／定時檢查新版，新 SW 接管後**自動 reload**（否則手機會跑舊快取碼、看不到更新）。
// 只在「已有舊 controller」時掛 reload（＝這是更新、非首次安裝），避免首安裝多一次 reload。
if ("serviceWorker" in navigator && navigator.serviceWorker.controller) {
  let refreshing = false
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (refreshing) return
    refreshing = true
    window.location.reload()
  })
}
registerSW({
  immediate: true,
  onRegisteredSW(_swUrl, reg) {
    if (!reg) return
    const check = () => { if (document.visibilityState === "visible") reg.update() }
    document.addEventListener("visibilitychange", check)
    setInterval(() => reg.update(), 5 * 60 * 1000)   // 每 5 分鐘查一次（原一小時太久）
  },
})
import Layout from "./Layout"
import ChatPage from "./ChatPage"
import RootsPage from "./pages/RootsPage"
import DomainsPage from "./pages/DomainsPage"
import ArticlesPage from "./pages/ArticlesPage"
import ArticleViewPage from "./pages/ArticleViewPage"
import SourcesPage from "./pages/SourcesPage"
import SourcePage from "./pages/SourcePage"
import ConversationsPage from "./pages/ConversationsPage"

function ResumeRedirect() {
  const { id } = useParams()
  const [sp] = useSearchParams()
  const q = new URLSearchParams({ resume: String(id || "") })
  for (const k of ["from", "to"]) { const v = sp.get(k); if (v) q.set(k, v) }
  return <Navigate to={`/?${q}`} replace />
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ChatPage />} />
          <Route path="domains" element={<DomainsPage />} />
          <Route path="roots" element={<RootsPage />} />
          <Route path="articles" element={<ArticlesPage />} />
          <Route path="articles/:id" element={<ArticleViewPage />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="source" element={<SourcePage />} />
          <Route path="conversations" element={<ConversationsPage />} />
          {/* spec 047：對話不再分「檢視」與「接著聊」——只有聊天頁一個去處。
              ⚠️ 舊網址（書籤、核心理解的由來連結）要導過去而不是 404，
              而且**必須把 from/to 帶著走**——由來定位靠它，斷了就是溯源斷掉（原則 3）。 */}
          <Route path="conversations/:id" element={<ResumeRedirect />} />
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
