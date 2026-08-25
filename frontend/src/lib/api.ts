// /api client（re-platform 階段一）：包 FastAPI 的 JSON/SSE 端點。
export type Source = { n: number; url: string; title: string; kind: string }

// 整理台（spec 050）。⚠️ 來源的 ref 是 **url**（一個來源＝多個塊），其餘三種是整數 id
// ——所以 ref 是 number | string，不要在前端窄化成 number。
export type KnowledgeKind = "conversation" | "why_node" | "article" | "source"
export type KnowledgeRef = { kind: KnowledgeKind; ref: number | string }
export type KnowledgeItem = KnowledgeRef & { label: string; domain_id: number | null }
export type Message = {
  role: "user" | "assistant"
  content: string
  sources?: Source[]
  found_extra?: Source[]
  // 這則回答不完整的原因："length"＝撞長度上限被切、"connection"＝中途斷線（空＝正常講完）。
  // 兩種在畫面上長得一樣，不標就分不出來、也修不對（憲章 V）。
  truncated?: string
}
export type Candidate = {
  claim: string
  kind?: string
  ladder: string[]
  evidence_urls: string[]
  already: boolean
  src_from?: number       // 出處對話則數範圍（階段29第2階段）
  src_to?: number
}
export type ChatState = {
  root_count: number
  recent_temp: { id: number; title: string; messages: Message[] } | null
}

// 登入門鎖（spec 035）：session 過期/未登入時 /api 回 401 → 導去 Google 登入（否則 SPA 卡在壞掉的請求）
const json = (r: Response) => {
  if (r.status === 401) { window.location.href = "/auth/login"; return Promise.reject(new Error("未登入")) }
  return r.json()
}

export const api = {
  state: (): Promise<ChatState> => fetch("/api/chat/state").then(json),
  distill: (history: Message[]): Promise<{ candidates?: Candidate[]; error?: string }> =>
    fetch("/api/chat/distill", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history }),
    }).then(json),
  anoint: (p: {
    claim: string
    kind?: string
    ladder?: string
    evidence_urls?: string
    save_convo?: boolean
    history?: Message[]
    temp_id?: number | null
    src_from?: number
    src_to?: number
  }): Promise<{ status: string; claim: string; msg: string | null }> =>
    fetch("/api/chat/anoint", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(p),
    }).then(json),
  autosave: (
    history: Message[],
    temp_id: number | null,
    // spec 044：這段對話的**由來**（帶著哪篇文章／哪份來源開的）。
    // ⚠️ 元資料，不是內容——不進 messages、不影響模型脈絡、介面上不顯示。
    // 只在後端建立那筆時寫入，之後送什麼都不會改到它。
    carried?: { kind: string; ref: string },
    domainId?: number | null,   // spec 048：這段對話開在哪個領域（只在建立那筆時寫）
  ): Promise<{ temp_id: number | null; title: string | null }> =>
    fetch("/api/chat/autosave", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, temp_id,
                            carried_kind: carried?.kind || "", carried_ref: carried?.ref || "",
                            domain_id: domainId ?? null }),
    }).then(json),
  save: (history: Message[], temp_id: number | null): Promise<{ saved: boolean; msg: string }> =>
    fetch("/api/chat/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, temp_id }),
    }).then(json),
}

// ── 其餘頁（re-platform 里程碑二）──
export type WhyNode = {
  id: number
  claim: string
  evidence_urls: string[]
  ladder: string[]
  touchstones: { name: string; passed: boolean }[]
  fog_flag: boolean
  kind: string          // 認識論層次：已證實/推論/類比/猜想
  src_from: number      // 出處對話則數範圍（階段29第2階段）
  src_to: number
  source_quote: string  // 來源 verbatim 錨點（Text Fragment 由來定位到原文段落）
  source_page: number   // PDF 來源出處頁碼（0=非 PDF/未知）→由來翻到那頁
}
export type RootsData = {
  anointed: WhyNode[]
  candidates: WhyNode[]
  provenance: Record<string, number>
  source_provenance: Record<string, string>
}
export type SourceGroup = {
  url: string
  title: string
  count: number
  source_class: string
  note: string
  ingested_at: string
}
export type ConvRow = {
  id: number
  title: string
  created_at: string
  why_node_id: number | null   // ⚠️ 舊欄位，別拿來判斷「聊出了東西」——見 yield_count
  // spec 045：以這段對話為由來的核心理解**條數**（讀事實來源 why_nodes.conversation_id）。
  // 舊做法讀 why_node_id，而那欄只在 save_conversation 那條路才填，冊封路徑不填 ⇒ 漏掉 2/3。
  yield_count: number
  domain_id: number | null     // spec 048：歸屬的領域（null＝未歸屬）
  count: number
}

const post = (url: string, body: unknown) =>
  fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(json)

export const pages = {
  // 登入身分＋門鎖是否啟用（決定要不要顯示登出）；不走 json（避免 401 導轉），失敗→視為未啟用
  me: (): Promise<{ user: string | null; auth_enabled: boolean }> =>
    fetch("/api/me").then((r) => (r.ok ? r.json() : { user: null, auth_enabled: false }))
      .catch(() => ({ user: null, auth_enabled: false })),
  roots: (): Promise<RootsData> => fetch("/api/roots").then(json),
  whynodeAnoint: (id: number, claim?: string, kind?: string) => post("/api/whynode/anoint", { id, claim, kind }),
  whynodeRemove: (id: number) => post("/api/whynode/remove", { id }),
  library: (): Promise<{ sources: SourceGroup[] }> => fetch("/api/library").then(json),
  source: (u: string, raw = false): Promise<{
    found: boolean; url: string; title: string; markdown: string; note: string; ingested_at: string
    original_url: string; pdf_path: string   // 原文=真相：原站連結／存下的 PDF（防失效＋頁級預覽）
    paper: { title: string; authors: string[]; abstract: string; published: string; source: string } | null
    s2t_applied: boolean   // spec 037：本次是否套用簡→繁；決定要不要顯示「看轉換前」切換
    is_english: boolean    // spec 038：英文來源才提供「翻成繁中」
  }> => fetch(`/api/source?u=${encodeURIComponent(u)}${raw ? "&raw=1" : ""}`).then(json),
  sourceMeta: (u: string, note: string, ingested_at: string) =>
    post("/api/source/meta", { u, note, ingested_at }),
  sourceDistill: (u: string): Promise<{ ok: boolean; err?: string }> =>
    post("/api/source/distill", { u }),
  reclassify: (url: string, source_class: string) =>
    post("/api/library/reclassify", { url, source_class }),
  removeSource: (url: string) => post("/api/library/remove", { url }),
  ingestPaste: (b: {
    text?: string; html?: string; title?: string; clean?: boolean
    source_url?: string; note?: string; ingested_at?: string
  }): Promise<{ status: string; count: number; title?: string; err?: string }> =>
    post("/api/ingest/paste", b),
  ingestUrl: (b: { url: string; title?: string; note?: string; ingested_at?: string }) =>
    post("/api/ingest/url", b),
  ingestYoutube: (b: { url: string; title?: string }): Promise<{ status: string; count: number; err?: string }> =>
    post("/api/ingest/youtube", b),
  conversations: (): Promise<{ conversations: ConvRow[] }> =>
    fetch("/api/conversations").then(json),
  conversation: (id: number, resume = false): Promise<{
    found: boolean; id: number; title: string; messages: Message[]; referrers: string[]
    // spec 046：這段對話已冊封的**範圍**（1-based 則數）。回範圍不回布林陣列——
    // 訊息數會變（接著聊），陣列會過期而錯位。from/to 為 0＝舊資料沒範圍，只算對話層級。
    anointed: { id: number; claim: string; from: number; to: number }[]
  }> => fetch(`/api/conversations/${id}${resume ? "?resume=1" : ""}`).then(json),
  renameConv: (id: number, title: string) => post(`/api/conversations/${id}/rename`, { title }),
  deleteConv: (id: number): Promise<{ deleted: boolean; blocked_by: string[] }> =>
    post(`/api/conversations/${id}/delete`, {}),
  retitleConv: (id: number): Promise<{ ok: boolean; title: string }> =>
    post(`/api/conversations/${id}/retitle`, {}),
  segment: (id: number, refresh = false): Promise<{ found: boolean; chapters: { title: string; start: number; end: number }[] }> =>
    fetch(`/api/conversations/${id}/segment${refresh ? "?refresh=1" : ""}`).then(json),
  dedupePreview: (): Promise<{ n_groups: number; n_extra: number; n_roots: number }> =>
    fetch("/api/conversations-dedupe/preview").then(json),
  dedupeApply: (): Promise<{ removed: number; repointed: number }> =>
    post("/api/conversations-dedupe/apply", {}),
  // ── 領域樹（spec 048）：領域＝節點、主題 Topic＝從根到節點的路徑 ──
  // ⚠️ path 由後端從 parent_id **導出**，前端不要自己拼字串存起來。
  domains: (): Promise<{ domains: { id: number; name: string; parent_id: number | null;
                                    path: { id: number; name: string }[] }[] }> =>
    fetch("/api/domains").then(json),
  createDomain: (name: string, parent_id: number | null = null): Promise<{ ok: boolean; id?: number; err?: string }> =>
    post("/api/domains", { name, parent_id }),
  renameDomain: (id: number, name: string) => post(`/api/domains/${id}/rename`, { name }),
  moveDomain: (id: number, parent_id: number | null): Promise<{ ok: boolean; err?: string }> =>
    post(`/api/domains/${id}/move`, { parent_id }),
  // 糾纏 Tangle（spec 049）＝樹裝不下的那條連結。
  // ⚠️ 預覽**不改任何東西**；搬動才寫。連帶只走一層（後端釘死）。
  // ⚠️ spec 050：**只有批次一條路**——單件操作＝送一個元素的清單。
  //    來源的 ref 是 **url**（一個來源＝多個塊），其餘三種是整數 id。
  inventory: (): Promise<{ ok: boolean; items: KnowledgeItem[] }> =>
    fetch("/api/knowledge/inventory").then(json),
  tangles: (items: KnowledgeRef[], domain_id: number | null): Promise<{
    ok: boolean; tangles: { kind: string; ref: number | string; domain_id: number; label: string }[] }> =>
    post("/api/knowledge/tangles", { items, domain_id }),
  moveKnowledge: (items: KnowledgeRef[], domain_id: number | null, bring_along = false):
    Promise<{ ok: boolean; moved: number; tangles: number }> =>
    post("/api/knowledge/move", { items, domain_id, bring_along }),
  setConvDomain: (cid: number, domain_id: number | null) =>
    post(`/api/conversations/${cid}/domain`, { domain_id }),

  // conversationId（spec 043）：用那段對話冊封出的核心理解當骨幹（0＝不帶，行為與現況相同）
  generateArticle: (topic: string, length: string, level: string, conversationId = 0): Promise<{ title?: string; markdown?: string; length?: string; level?: string; error?: string }> =>
    post("/api/article", { topic, length, level, conversation_id: conversationId }),
  saveArticle: (b: { topic: string; title: string; markdown: string; length: string; level: string }): Promise<{ id: number }> =>
    post("/api/article/save", b),
  listArticles: (): Promise<{ articles: { id: number; topic: string; title: string; length: string; level: string; created_at: string }[] }> =>
    fetch("/api/articles").then(json),
  getArticle: (id: number): Promise<{ id: number; title: string; markdown: string }> =>
    fetch(`/api/article/${id}`).then(json),
  deleteArticle: (id: number) => post(`/api/article/${id}/delete`, {}),
}

export type StreamHandlers = {
  onStage?: (t: string) => void
  onToken?: (t: string) => void
  onDone?: (text: string, sources: Source[], found_extra: Source[], truncated: string) => void
  onError?: (t: string) => void
}

// 串流一輪對話：協定同後端（stage/token/done/error），逐字回呼。
export async function streamChat(
  history: Message[],
  message: string,
  bare: boolean,   // 這輪暫時屏蔽知識庫（不注入核心理解、不撒網、不查收藏）
  h: StreamHandlers,
  articleId = 0,   // spec 041：使用者明確帶進來的一篇生成文章（0＝沒帶）
  sourceUrl = "",  // spec 042：使用者明確帶進來的一份收進來源（空＝沒帶）
) {
  let resp: Response
  try {
    resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, message, bare, article_id: articleId, source_url: sourceUrl }),
    })
  } catch {
    h.onError?.("連線中斷，請重試。")
    return
  }
  if (!resp.body) {
    h.onError?.("連線失敗，請重試。")
    return
  }
  const reader = resp.body.getReader()
  const dec = new TextDecoder()
  let buf = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buf += dec.decode(value, { stream: true })
    const parts = buf.split("\n\n")
    buf = parts.pop() || ""
    for (const p of parts) {
      const line = p.trim()
      if (!line.startsWith("data:")) continue
      let d: { type: string; text?: string; sources?: Source[]; found_extra?: Source[]; truncated?: string }
      try {
        d = JSON.parse(line.slice(5).trim())
      } catch {
        continue
      }
      if (d.type === "stage") h.onStage?.(d.text || "")
      else if (d.type === "token") h.onToken?.(d.text || "")
      else if (d.type === "done") h.onDone?.(d.text || "", d.sources || [], d.found_extra || [], d.truncated || "")
      else if (d.type === "error") h.onError?.(d.text || "發生錯誤")
    }
  }
}
