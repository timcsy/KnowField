import { useEffect, useRef, useState } from "react"
import { useSearchParams } from "react-router-dom"
import { api, pages, streamChat, type Candidate, type Message } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Sources, FoundExtra } from "@/components/Sources"
import { KindBadge } from "@/components/KindBadge"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
import { Copy, GitBranch, Pencil } from "lucide-react"

type Chapter = { title: string; start: number; end: number }

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
  const [convTitle, setConvTitle] = useState("")   // 本對話落點標題（抬頭顯示）
  const tempId = useRef<number | null>(null)
  const [chapters, setChapters] = useState<Chapter[] | null>(null)   // resume 舊訊息的章節（折疊）
  const baseCount = useRef(0)                                         // resume 載入的訊息數（章節涵蓋到此）
  const [focusFrom, setFocusFrom] = useState(0)                      // 核心理解定位進來的出處起點則
  const [nudgeDismissed, setNudgeDismissed] = useState(false)        // 分章提醒關掉了
  const chapterRefs = useRef<(HTMLDetailsElement | null)[]>([])   // 各章 <details>，供大綱跳章＋預設展開
  const bottomRef = useRef<HTMLDivElement>(null)
  const [sp, setSp] = useSearchParams()

  useEffect(() => {
    api.state().then((s) => setRootCount(s.root_count)).catch(() => {})
  }, [])

  async function loadConversation(id: number, from = 0) {
    const c = await pages.conversation(id, true)
    if (!c.found) return
    setMessages(c.messages)
    setConvTitle(c.title || "")
    baseCount.current = c.messages.length
    setFocusFrom(from); setNudgeDismissed(false)
    tempId.current = c.temporary ? c.id : null
    setCandidates(null); setStreaming(null); setStage(null)
    // 載章節（持久化）：多章才折疊
    pages.segment(id).then((r) =>
      setChapters(r.found && r.chapters.length > 1 ? r.chapters : null)).catch(() => setChapters(null))
  }
  function newChat() {
    setMessages([]); tempId.current = null; setChapters(null); baseCount.current = 0; setFocusFrom(0)
    setConvTitle(""); setNudgeDismissed(false)
    setCandidates(null); setCandDone({}); setStreaming(null); setStage(null); setInput("")
  }

  // 側欄用 URL 溝通：?new=… 開新對話、?resume=id 接回（?from&to＝核心理解定位）
  useEffect(() => {
    if (sp.get("new")) { newChat(); sp.delete("new"); setSp(sp, { replace: true }); return }
    const rid = Number(sp.get("resume") || 0)
    if (rid) {
      const from = Number(sp.get("from") || 0)
      loadConversation(rid, from).finally(() => {
        sp.delete("resume"); sp.delete("from"); sp.delete("to"); setSp(sp, { replace: true })
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sp, setSp])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, streaming, stage])

  // 預設展開「該開的章」（出處章 or 最後章）；定位進來時還捲到它
  useEffect(() => {
    const d = chapterRefs.current[openIdx]
    if (d) {
      d.open = true
      if (focusFrom) d.scrollIntoView({ behavior: "smooth", block: "start" })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chapters, focusFrom])

  // 大綱點章：展開那章＋捲到它
  function jumpToChapter(ci: number) {
    const d = chapterRefs.current[ci]
    if (d) { d.open = true; d.scrollIntoView({ behavior: "smooth", block: "start" }) }
  }

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
          tempId.current = r.temp_id
          if (r.title) setConvTitle(r.title)
          notifyConversations()
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
      claim: c.claim, kind: c.kind, ladder: c.ladder.join("\n"),
      evidence_urls: c.evidence_urls.join(", "),
      save_convo: saveConvo, history: messages, temp_id: tempId.current,
      src_from: c.src_from, src_to: c.src_to,
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
  // 從某章末開分支：載入前綴當新對話（原對話不動），接著聊會存成新暫存
  function branchFrom(upToMsg: number) {
    setMessages(messages.slice(0, upToMsg))
    tempId.current = null; baseCount.current = 0
    setChapters(null); setFocusFrom(0); setConvTitle("")
    setCandidates(null); setStreaming(null); setStage(null)
    toast("已從這裡開分支——接著聊會存成新對話，原對話不動")
  }
  async function copyMsg(text: string) {
    try { await navigator.clipboard.writeText(text); toast("已複製這則") }
    catch { toast("這個瀏覽器不允許自動複製") }
  }
  // 整理成章節（把續聊的新訊息也切進章節）——分章提醒觸發
  async function reslice() {
    if (!tempId.current) { toast("先聊一句讓它存下、才能整理章節"); return }
    setBusy(true)
    const r = await pages.segment(tempId.current, true)
    setBusy(false)
    setNudgeDismissed(true)
    if (r.found && r.chapters.length > 1) {
      setChapters(r.chapters); baseCount.current = messages.length; setFocusFrom(0)
      toast(`整理成 ${r.chapters.length} 章了`)
    }
  }

  const empty = messages.length === 0 && streaming === null && stage === null
  const freshCands = (candidates || []).filter((c) => !c.already)

  const renderMsg = (m: Message, i: number) =>
    m.role === "user" ? (
      <div key={i} className="group flex flex-col items-end gap-0.5">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-muted px-4 py-2">{m.content}</div>
        <button onClick={() => editMessage(i)} title="編輯這句重問（改這串）"
                className="pr-1 text-muted-foreground opacity-0 transition hover:text-foreground group-hover:opacity-100">
          <Pencil className="size-3.5" />
        </button>
      </div>
    ) : (
      <div key={i} className="group">
        <div className="rounded-xl bg-card px-4 py-3 shadow-sm">
          <Markdown text={m.content} prefix={`m${i}`} />
          <Sources sources={m.sources || []} prefix={`m${i}`} />
          <FoundExtra extra={m.found_extra || []} />
        </div>
        {/* 回覆下方操作列（一般 AI 聊天慣例）：複製、分支 */}
        <div className="mt-1 flex gap-3 pl-1 text-muted-foreground opacity-0 transition group-hover:opacity-100">
          <button onClick={() => copyMsg(m.content)} title="複製這則回覆" className="hover:text-foreground"><Copy className="size-3.5" /></button>
          <button onClick={() => branchFrom(i + 1)} title="從這裡開分支（原對話不動、另開一串接著聊）" className="hover:text-primary"><GitBranch className="size-3.5" /></button>
        </div>
      </div>
    )
  const hasChapters = !!(chapters && chapters.length > 1)
  // 該預設展開的章 index：定位進來→出處章；否則→最後章
  let openIdx = -1
  if (hasChapters && chapters) {
    openIdx = focusFrom > 0
      ? chapters.findIndex((ch) => ch.start <= focusFrom && ch.end >= focusFrom)
      : chapters.length - 1
    if (openIdx < 0) openIdx = chapters.length - 1
  }
  const lastEnd = hasChapters && chapters ? chapters[chapters.length - 1].end : 0
  const uncharted = messages.length - lastEnd   // 還沒切進章節的訊息數（續聊累積）
  const showNudge = uncharted >= 8 && !nudgeDismissed && !busy && streaming === null

  return (
    <div className="relative flex h-full px-4 py-3">
      {/* 章節大綱：釘在主內容區最左邊（靠導覽側欄）；聊天欄仍置中。大螢幕、有多章才出現 */}
      {hasChapters && chapters && (
        <aside className="absolute left-1 top-14 hidden w-48 xl:block">
          <div className="space-y-0.5">
            <div className="mb-1 px-2 text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">本對話章節</div>
            {chapters.map((ch, ci) => (
              <button key={ci} onClick={() => jumpToChapter(ci)} title={ch.title}
                      className={cn("block w-full truncate rounded px-2 py-1 text-left text-xs hover:bg-muted",
                        ci === openIdx ? "font-medium text-foreground" : "text-muted-foreground")}>
                🔖 {ch.title}
              </button>
            ))}
          </div>
        </aside>
      )}

      <div className="mx-auto flex h-full w-full max-w-3xl flex-col">
      <div className="shrink-0 pb-2">
        <h1 className="truncate text-lg font-bold" title={convTitle || undefined}>
          {convTitle ? `💬 ${convTitle}` : "🧠 跟你的知識庫聊"}
        </h1>
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

        {hasChapters && chapters ? (
          chapters.map((ch, ci) => {
            const isLast = ci === chapters.length - 1
            const isFocus = focusFrom > 0 && ch.start <= focusFrom && ch.end >= focusFrom
            // 最後一章的範圍含本次續聊的新訊息（都在這章的折疊區內）
            const msgs = isLast ? messages.slice(ch.start - 1) : messages.slice(ch.start - 1, ch.end)
            const endLabel = isLast ? messages.length : ch.end
            return (
              <details key={`ch${ci}`} ref={(el) => { chapterRefs.current[ci] = el }}
                       className={cn("group rounded-xl bg-card shadow-sm", isFocus && "ring-2 ring-primary/50")}>
                <summary className="cursor-pointer list-none px-4 py-2.5 text-sm font-medium hover:bg-muted/40">
                  <span className="mr-1 text-muted-foreground group-open:hidden">▸</span>
                  <span className="mr-1 hidden text-muted-foreground group-open:inline">▾</span>
                  {ch.title}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">第 {ch.start}–{endLabel} 則</span>
                  {isFocus && <span className="ml-2 text-xs font-normal text-primary">← 出處</span>}
                  {isLast && <span className="ml-2 text-xs font-normal text-muted-foreground">（最新，接著聊）</span>}
                </summary>
                <div className="space-y-3 border-t px-4 py-3">
                  {msgs.map((m, j) => renderMsg(m, ch.start - 1 + j))}
                </div>
              </details>
            )
          })
        ) : (
          messages.map(renderMsg)
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
                  <div className="flex items-start gap-2 font-medium"><KindBadge kind={c.kind} /><span>💡 {c.claim}</span></div>
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

      {showNudge && (
        <div className="mb-2 flex shrink-0 items-center gap-2 rounded-lg border bg-muted px-3 py-2 text-xs text-muted-foreground">
          <span>聊了一大段（{uncharted} 則還沒整理）——整理成章節、方便回頭找？</span>
          <button onClick={reslice} disabled={busy} className="ml-auto font-medium text-primary hover:underline">🔖 整理成章節</button>
          <button onClick={() => setNudgeDismissed(true)} title="先不要" className="hover:text-foreground">✕</button>
        </div>
      )}

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
    </div>
  )
}
