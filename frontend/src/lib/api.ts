// /api client（re-platform 階段一）：包 FastAPI 的 JSON/SSE 端點。
export type Source = { n: number; url: string; title: string; kind: string }
export type Message = {
  role: "user" | "assistant"
  content: string
  sources?: Source[]
  found_extra?: Source[]
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

const json = (r: Response) => r.json()

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
  ): Promise<{ temp_id: number | null }> =>
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
  roots: (): Promise<RootsData> => fetch("/api/roots").then(json),
  whynodeAnoint: (id: number, claim?: string, kind?: string) => post("/api/whynode/anoint", { id, claim, kind }),
  whynodeRemove: (id: number) => post("/api/whynode/remove", { id }),
  library: (): Promise<{ sources: SourceGroup[] }> => fetch("/api/library").then(json),
  source: (u: string): Promise<{
    found: boolean; url: string; title: string; markdown: string; note: string; ingested_at: string
  }> => fetch(`/api/source?u=${encodeURIComponent(u)}`).then(json),
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
    found: boolean; id: number; title: string; messages: Message[]; temporary: boolean
  }> => fetch(`/api/conversations/${id}${resume ? "?resume=1" : ""}`).then(json),
  renameConv: (id: number, title: string) => post(`/api/conversations/${id}/rename`, { title }),
  retitleConv: (id: number): Promise<{ ok: boolean; title: string }> =>
    post(`/api/conversations/${id}/retitle`, {}),
  segment: (id: number, refresh = false): Promise<{ found: boolean; chapters: { title: string; start: number; end: number }[] }> =>
    fetch(`/api/conversations/${id}/segment${refresh ? "?refresh=1" : ""}`).then(json),
  promoteConv: (id: number) => post(`/api/conversations/${id}/promote`, {}),
  dedupePreview: (): Promise<{ n_groups: number; n_extra: number; n_roots: number }> =>
    fetch("/api/conversations-dedupe/preview").then(json),
  dedupeApply: (): Promise<{ removed: number; repointed: number }> =>
    post("/api/conversations-dedupe/apply", {}),
}

export type StreamHandlers = {
  onStage?: (t: string) => void
  onToken?: (t: string) => void
  onDone?: (text: string, sources: Source[], found_extra: Source[]) => void
  onError?: (t: string) => void
}

// 串流一輪對話：協定同後端（stage/token/done/error），逐字回呼。
export async function streamChat(
  history: Message[],
  message: string,
  brainstorm: boolean,
  h: StreamHandlers,
) {
  let resp: Response
  try {
    resp = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history, message, brainstorm }),
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
      let d: { type: string; text?: string; sources?: Source[]; found_extra?: Source[] }
      try {
        d = JSON.parse(line.slice(5).trim())
      } catch {
        continue
      }
      if (d.type === "stage") h.onStage?.(d.text || "")
      else if (d.type === "token") h.onToken?.(d.text || "")
      else if (d.type === "done") h.onDone?.(d.text || "", d.sources || [], d.found_extra || [])
      else if (d.type === "error") h.onError?.(d.text || "發生錯誤")
    }
  }
}
