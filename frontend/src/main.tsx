import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import "./index.css"
import Layout from "./Layout"
import ChatPage from "./ChatPage"
import RootsPage from "./pages/RootsPage"
import SourcesPage from "./pages/SourcesPage"
import SourcePage from "./pages/SourcePage"
import ConversationViewPage from "./pages/ConversationViewPage"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename="/app">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ChatPage />} />
          <Route path="roots" element={<RootsPage />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="source" element={<SourcePage />} />
          <Route path="conversations/:id" element={<ConversationViewPage />} />
          {/* 舊 IA → 新 IA（對話＝聊天＋存檔、來源＝知識庫＋收進） */}
          <Route path="library" element={<Navigate to="/sources" replace />} />
          <Route path="ingest" element={<Navigate to="/sources" replace />} />
          <Route path="conversations" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
