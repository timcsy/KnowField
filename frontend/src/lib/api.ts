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
    ladder?: string
    evidence_urls?: string
    save_convo?: boolean
    history?: Message[]
    temp_id?: number | null
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
