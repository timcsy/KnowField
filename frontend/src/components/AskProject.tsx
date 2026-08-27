import { useEffect, useRef, useState } from "react"
import { pages, streamChat, type BaseCorpus, type BaseDraft as BaseDraftT, type Message } from "@/lib/api"
import { AssistantFlow, Composer, Streaming, UserBubble } from "@/components/ChatShape"

// spec 078：站在某個專案裡聊它的 `knowledge/`。
// ⚠️ **跟互動那邊是同一條聊天**（`/api/chat/stream` ＋ `ChatShape`），只是換了場：
//    那一邊不撒網、不注入你的理解，證言只有這個專案的 knowledge/。
//    另做一套的話，多輪會先壞（你問「那第二點呢？」它不記得），而形狀也會從第一天開始漂。

const LABEL: Record<string, string> = {
  experience: "經驗", concepts: "概念", principles: "原則", vision: "路線圖",
}

/** 把這一輪整理成一塊 draft，送回那個專案。⚠️ 只碰 `knowledge/draft/`。 */
function Draft({ bid, messages }: { bid: number; messages: Message[] }) {
  const [d, setD] = useState<BaseDraftT | null>(null)
  const [busy, setBusy] = useState(false)
  const [copied, setCopied] = useState(false)
  const lastQ = [...messages].reverse().find((m) => m.role === "user")?.content || ""
  async function make() {
    setBusy(true)
    try {
      // 你問的那句當小標——draft 是 markdown，標題比粗體更合適
      const body = messages.map((m) => (m.role === "user" ? `### ${m.content}` : m.content)).join("\n\n")
      setD(await pages.baseDraft(bid, lastQ.slice(0, 40), body, []))
    } finally { setBusy(false) }
  }
  if (!messages.length) return null
  if (!d) {
    return (
      <button onClick={make} disabled={busy}
              className="text-xs text-muted-foreground hover:text-foreground hover:underline">
        {busy ? "整理…" : "✍️ 整理成這個專案的 draft"}
      </button>
    )
  }
  return (
    <div className="space-y-1.5 rounded-lg border p-2.5 text-xs">
      <p className="text-muted-foreground">{d.path}</p>
      {d.url ? (
        <a href={d.url} target="_blank" rel="noopener"
           className="inline-block rounded bg-primary px-2.5 py-1 text-primary-foreground">
          在 GitHub 開好新檔 → 你按 commit
        </a>
      ) : (
        // ⚠️ 太長要說**為什麼**退回複製，不是靜默換行為
        <p className="text-destructive">{d.why}</p>
      )}
      <button onClick={() => { navigator.clipboard?.writeText(d.content); setCopied(true) }}
              className="ml-2 text-muted-foreground hover:text-foreground">
        {copied ? "已複製" : "📋 複製內容"}
      </button>
    </div>
  )
}

export function AskProject({ bid, name }: { bid: number; name: string }) {
  const [c, setC] = useState<BaseCorpus | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  // 換專案＝換場 ⇒ 對話重來（那是另一個專案的脈絡）
  useEffect(() => {
    setMessages([]); setStreaming(null); setC(null)
    pages.baseCorpus(bid).then(setC).catch(() => {})
  }, [bid])
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }) }, [messages, streaming])

  async function send() {
    const msg = input.trim()
    if (!msg || busy) return
    const hist = messages
    setInput(""); setBusy(true); setStage("翻這個專案的知識庫…"); setStreaming("")
    setMessages([...hist, { role: "user", content: msg }])
    let full = ""
    await streamChat(hist, msg, false, {
      onStage: (t) => setStage(t),
      onToken: (t) => { full += t; setStage(null); setStreaming(full) },
      onError: (t) => {
        setStreaming(null); setStage(null)
        setMessages([...hist, { role: "user", content: msg },
                     { role: "assistant", content: "⚠ " + t }])
      },
      onDone: (text, sources, extra, truncated) => {
        setMessages([...hist, { role: "user", content: msg },
                     { role: "assistant", content: text || full, sources,
                       found_extra: extra, truncated }])
        setStreaming(null); setStage(null)
      },
    }, 0, "", bid)
    setBusy(false)
  }

  const missing = Object.keys(c?.layers ?? {}).length === 0
  return (
    <div className="flex h-full min-h-0 flex-col px-4 py-3">
      {/* ⚠️ 先講清楚它讀得到什麼——不然「沒有」會被當成「它不知道」 */}
      <p className="shrink-0 pb-2 text-xs text-muted-foreground">
        {c === null ? "…" : missing
          ? `📁 ${name}：還沒建索引——問一次就會自動建（大的專案要一兩分鐘）。`
          : <>📁 {name} 的知識庫：{c.in_corpus.map((k) => `${LABEL[k] || k} ${c.layers[k] ?? 0}`).join("・")}
              <span className="mx-1">·</span>共 {c.n_chunks} 段。轉移／場景／draft 不在裡面。</>}
      </p>

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto py-2">
        {messages.length === 0 && streaming === null && (
          <p className="text-sm text-muted-foreground">
            問這個專案的知識庫——它只用這個專案自己寫下的東西回答，不撒網、也不參考你的理解。
          </p>
        )}
        {messages.map((m, i) => (m.role === "user"
          ? <UserBubble key={i} content={m.content} />
          : <AssistantFlow key={i} m={m} prefix={`p${i}`} />))}
        <Streaming text={streaming} stage={stage} />
        {!busy && messages.length > 0 && <Draft bid={bid} messages={messages} />}
        <div ref={end} />
      </div>

      <Composer value={input} onChange={setInput} onSend={send} busy={busy}
                placeholder={`問 ${name} 的知識庫…`} />
    </div>
  )
}
