import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import "./index.css"
import Layout from "./Layout"
import ChatPage from "./ChatPage"
import RootsPage from "./pages/RootsPage"
import LibraryPage from "./pages/LibraryPage"
import SourcePage from "./pages/SourcePage"
import IngestPage from "./pages/IngestPage"
import ConversationsPage from "./pages/ConversationsPage"
import ConversationViewPage from "./pages/ConversationViewPage"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter basename="/app">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<ChatPage />} />
          <Route path="roots" element={<RootsPage />} />
          <Route path="library" element={<LibraryPage />} />
          <Route path="source" element={<SourcePage />} />
          <Route path="ingest" element={<IngestPage />} />
          <Route path="conversations" element={<ConversationsPage />} />
          <Route path="conversations/:id" element={<ConversationViewPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
