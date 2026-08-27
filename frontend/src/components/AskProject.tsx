import { useEffect, useRef, useState } from "react"
import { streamChat, type Message } from "@/lib/api"
import { AssistantFlow, Composer, Streaming, UserBubble } from "@/components/ChatShape"

// spec 080：站在某個專案裡聊它的知識庫。
// ⚠️ **跟互動那邊是同一條聊天**（`/api/chat/stream` ＋ `ChatShape`）——
//    專案的知識檔就是**來源**，站在這裡只是把範圍縮到它的領域（spec 079）。
//    在此之前這裡是「第二個場」（另一套語料、另一套門檻）；兩套一定會漂，
//    而漂掉的那一套不會報錯。

export function AskProject({ did, name, files, chunks }:
                           { did: number; name: string; files: number; chunks: number }) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [streaming, setStreaming] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  // 換專案 ⇒ 對話重來（那是另一個專案的脈絡）
  useEffect(() => { setMessages([]); setStreaming(null) }, [did])
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
    }, 0, "", did || null)
    setBusy(false)
  }

  return (
    <div className="flex h-full min-h-0 flex-col px-4 py-3">
      {/* ⚠️ 先講清楚它讀得到什麼——不然「沒有」會被當成「它不知道」。
          ⚠️ 而**沒歸到領域時要說**：那時它翻的是整個場，不是這個專案。 */}
      <p className="shrink-0 pb-2 text-xs text-muted-foreground">
        {did
          ? <>📁 {name} 的知識庫：{files} 份檔<span className="mx-1">·</span>{chunks} 段</>
          : `⚠ ${name} 還沒歸到領域——這裡問到的會是整個場的東西，不只這個專案。`}
      </p>

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto py-2">
        {messages.length === 0 && streaming === null && (
          <p className="text-sm text-muted-foreground">
            問這個專案的知識庫——證言只縮在這個專案自己寫下的東西裡。
          </p>
        )}
        {messages.map((m, i) => (m.role === "user"
          ? <UserBubble key={i} content={m.content} />
          : <AssistantFlow key={i} m={m} prefix={`p${i}`} />))}
        <Streaming text={streaming} stage={stage} />
        <div ref={end} />
      </div>

      <Composer value={input} onChange={setInput} onSend={send} busy={busy}
                placeholder={`問 ${name} 的知識庫…`} />
    </div>
  )
}
