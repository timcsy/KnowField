import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { api, pages, streamChat, type Candidate, type Message } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Sources, FoundExtra } from "@/components/Sources"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"

// 通知側欄（Layout 內）重載對話歷史
const notifyConversations = () => window.dispatchEvent(new Event("kf-conversations-changed"))

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [brainstorm, setBrainstorm] = useState(false)
  const [stage, setStage] = useState<string | null>(null)
  const [streaming, setStreaming] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [rootCount, setRootCount] = useState(0)
  const [candidates, setCandidates] = useState<Candidate[] | null>(null)
  const [candDone, setCandDone] = useState<Record<number, string>>({})
  const [saveConvo, setSaveConvo] = useState(false)
  const tempId = useRef<number | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const [sp, setSp] = useSearchParams()

  useEffect(() => {
    api.state().then((s) => setRootCount(s.root_count)).catch(() => {})
  }, [])

  async function loadConversation(id: number) {
    const c = await pages.conversation(id, true)
    if (!c.found) return
    setMessages(c.messages)
    tempId.current = c.temporary ? c.id : null
    setCandidates(null); setStreaming(null); setStage(null)
  }
  function newChat() {
    setMessages([]); tempId.current = null
    setCandidates(null); setCandDone({}); setStreaming(null); setStage(null); setInput("")
  }

  // 側欄用 URL 溝通：?new=… 開新對話、?resume=id 接回存下的對話
  useEffect(() => {
    if (sp.get("new")) { newChat(); sp.delete("new"); setSp(sp, { replace: true }); return }
    const rid = Number(sp.get("resume") || 0)
    if (rid) loadConversation(rid).finally(() => { sp.delete("resume"); setSp(sp, { replace: true }) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp, setSp])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streaming, stage])

  async function send() {
    const msg = input.trim()
    if (!msg || busy) return
    setBusy(true)
    setInput("")
    setStage("思考中…")
    setStreaming("")
    const hist = messages
    let full = ""
    await streamChat(hist, msg, brainstorm, {
      onStage: (t) => setStage(t),
      onToken: (t) => { full += t; setStage(null); setStreaming(full) },
      onError: (t) => {
        setStreaming(null); setStage(null)
        setMessages([...hist, { role: "user", content: msg },
          { role: "assistant", content: "⚠ " + t }])
      },
      onDone: (text, sources, extra) => {
        const next: Message[] = [...hist, { role: "user", content: msg },
          { role: "assistant", content: text || full, sources, found_extra: extra }]
        setMessages(next); setStreaming(null); setStage(null)
        api.autosave(next, tempId.current).then((r) => {
          tempId.current = r.temp_id; notifyConversations()
        }).catch(() => {})
      },
    })
    setBusy(false)
  }

  async function distill() {
    if (!messages.length || busy) return
    setBusy(true)
    const r = await api.distill(messages)
    setBusy(false)
    if (r.error) return
    setCandidates(r.candidates || [])
    setCandDone({})
  }

  async function anointOne(i: number, c: Candidate) {
    const r = await api.anoint({
      claim: c.claim, ladder: c.ladder.join("\n"),
      evidence_urls: c.evidence_urls.join(", "),
      save_convo: saveConvo, history: messages, temp_id: tempId.current,
    })
    setCandDone((d) => ({ ...d, [i]: r.status === "exists" ? "➖ 已收過（沒重複收）" : "✅ 已精選" }))
    if (r.status === "created") setRootCount((n) => n + 1)
    if (saveConvo) notifyConversations()   // 連同存對話→歷史更新
  }

  const [flash, setFlash] = useState<string | null>(null)
  function toast(t: string) { setFlash(t); setTimeout(() => setFlash(null), 2200) }

  async function saveConversation() {
    const r = await api.save(messages, tempId.current)
    if (r.saved) { tempId.current = null; notifyConversations() }
    toast(r.msg)
  }

  async function copyChat(as: "md" | "urls") {
    const r = await fetch("/api/chat/export", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ history: messages, as }),
    })
    const text = await r.text()
    if (!text.trim()) { toast(as === "urls" ? "這段沒有被引用的來源網址" : "對話還是空的"); return }
    try { await navigator.clipboard.writeText(text); toast("已複製，可貼進 NotebookLM") }
    catch { toast("這個瀏覽器不允許自動複製") }
  }
  function editMessage(i: number) {
    setInput(messages[i]?.content || "")
    setMessages(messages.slice(0, i))   // 從這句重問（這串會改）
  }

  const empty = messages.length === 0 && streaming === null && stage === null
  const freshCands = (candidates || []).filter((c) => !c.already)

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col px-4 py-3 md:px-8">
      <div className="shrink-0 pb-2">
        <h1 className="text-lg font-bold">🧠 跟你的知識庫聊</h1>
        <p className="text-xs text-muted-foreground">
          從你存下的 {rootCount} 條核心理解出發，有話直說、不順著你講好聽話。
        </p>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto py-2">
        {empty && (
          <div className="flex flex-col items-center gap-3 pt-16 text-center text-muted-foreground">
            <div className="text-5xl">🧠</div>
            <p className="max-w-sm text-sm">
              丟一個想法、一個「為什麼 X 要這樣」，或接著上一句往下問。
              <br />它有話直說，不順著你講好聽話。
            </p>
          </div>
        )}

        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="group flex items-start justify-end gap-1">
              <button onClick={() => editMessage(i)} title="從這句重問（這串會改）"
                      className="mt-1 text-xs opacity-0 transition hover:text-foreground group-hover:opacity-100">✏️</button>
              <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-muted px-4 py-2">
                {m.content}
              </div>
            </div>
          ) : (
            <div key={i} className="rounded-xl bg-card px-4 py-3 shadow-sm">
              <Markdown text={m.content} prefix={`m${i}`} />
              <Sources sources={m.sources || []} prefix={`m${i}`} />
              <FoundExtra extra={m.found_extra || []} />
            </div>
          ),
        )}

        {streaming !== null && (
          <div className="rounded-xl bg-card px-4 py-3 shadow-sm">
            <div className="whitespace-pre-wrap text-[15px] leading-relaxed">{streaming || "…"}</div>
          </div>
        )}
        {stage && <div className="animate-pulse text-sm text-muted-foreground">{stage}</div>}

        {candidates && (
          <div className="space-y-3 rounded-xl border bg-card p-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold">整理出這幾條——挑要精選的（你決定）</h2>
              <button onClick={() => setCandidates(null)}
                      className="text-xs text-muted-foreground hover:underline">收起</button>
            </div>
            {freshCands.length > 0 && (
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input type="checkbox" checked={saveConvo}
                       onChange={(e) => setSaveConvo(e.target.checked)} />
                連同這段對話存成「由來」
              </label>
            )}
            {freshCands.length === 0 && (
              <p className="text-sm text-muted-foreground">這段沒整理出值得長期留的重點。</p>
            )}
            {candidates.map((c, i) =>
              c.already ? (
                <div key={i} className="text-xs text-muted-foreground">✓ 已在核心理解：{c.claim}</div>
              ) : (
                <div key={i} className="space-y-2 rounded-lg border p-3">
                  <div className="font-medium">💡 {c.claim}</div>
                  {candDone[i] ? (
                    <div className="text-sm text-primary">{candDone[i]}</div>
                  ) : (
                    <Button size="sm" onClick={() => anointOne(i, c)}>精選這條</Button>
                  )}
                </div>
              ),
            )}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 pt-2">
        <div className="flex items-end gap-2 rounded-2xl bg-muted px-3 py-2 focus-within:ring-1 focus-within:ring-ring">
          <Textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() }
            }}
            placeholder="丟一個想法、一個「為什麼 X 要這樣」、或接著上一句往下問…"
            className="max-h-40 min-h-0 resize-none border-0 bg-transparent p-1 shadow-none focus-visible:ring-0"
          />
          <Button size="icon" className="shrink-0 rounded-full" disabled={busy} onClick={send}
                  aria-label="送出">↑</Button>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1">
          <label className="flex items-center gap-1 text-xs text-muted-foreground">
            <input type="checkbox" checked={brainstorm}
                   onChange={(e) => setBrainstorm(e.target.checked)} />
            🧠 腦力激盪（這輪純聊、不找資料）
          </label>
          {messages.length > 0 && (
            <>
              <button onClick={distill} disabled={busy}
                      className="text-xs text-muted-foreground hover:underline">🧵 整理成重點</button>
              <button onClick={saveConversation} disabled={busy}
                      className="text-xs text-muted-foreground hover:underline">💾 存下這段</button>
              <button onClick={() => copyChat("md")}
                      className="text-xs text-muted-foreground hover:underline">📋 複製 Markdown</button>
              <button onClick={() => copyChat("urls")}
                      className="text-xs text-muted-foreground hover:underline">🔗 複製來源</button>
            </>
          )}
        </div>
      </div>

      {flash && (
        <div className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-foreground px-4 py-2 text-sm text-background shadow-lg">
          {flash}
        </div>
      )}
    </div>
  )
}
