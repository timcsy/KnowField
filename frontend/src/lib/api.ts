// /api client（re-platform 階段一）：包 FastAPI 的 JSON/SSE 端點。
export type Source = { n: number; url: string; title: string; kind: string }
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
  ): Promise<{ temp_id: number | null; title: string | null }> =>
    fetch("/api/chat/autosave", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, temp_id }),
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
  temporary: boolean
  why_node_id: number | null
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
    s2t_applied: boolean   // spec 037：本次是否套用簡→繁；決定要不要顯示「看原文」切換
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
  conversations: (): Promise<{ permanent: ConvRow[]; temporary: ConvRow[] }> =>
    fetch("/api/conversations").then(json),
  conversation: (id: number, resume = false): Promise<{
    found: boolean; id: number; title: string; messages: Message[]; temporary: boolean; referrers: string[]
  }> => fetch(`/api/conversations/${id}${resume ? "?resume=1" : ""}`).then(json),
  renameConv: (id: number, title: string) => post(`/api/conversations/${id}/rename`, { title }),
  deleteConv: (id: number): Promise<{ deleted: boolean; blocked_by: string[] }> =>
    post(`/api/conversations/${id}/delete`, {}),
  retitleConv: (id: number): Promise<{ ok: boolean; title: string }> =>
    post(`/api/conversations/${id}/retitle`, {}),
  segment: (id: number, refresh = false): Promise<{ found: boolean; chapters: { title: string; start: number; end: number }[] }> =>
    fetch(`/api/conversations/${id}/segment${refresh ? "?refresh=1" : ""}`).then(json),
  promoteConv: (id: number) => post(`/api/conversations/${id}/promote`, {}),
  dedupePreview: (): Promise<{ n_groups: number; n_extra: number; n_roots: number }> =>
    fetch("/api/conversations-dedupe/preview").then(json),
  dedupeApply: (): Promise<{ removed: number; repointed: number }> =>
    post("/api/conversations-dedupe/apply", {}),
  generateArticle: (topic: string, length: string, level: string): Promise<{ title?: string; markdown?: string; length?: string; level?: string; error?: string }> =>
    post("/api/article", { topic, length, level }),
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
) {
  let resp: Response
  try {
    resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, message, bare }),
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
