import { useEffect, useRef, useState } from "react"
import { api, streamChat, type Candidate, type Message, type Source } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"

// 答案文字 → HTML：math 抽出佔位 → marked 渲染 → 還原成 .mathcopy(帶 data-tex) → [n] 變引用錨點。
// 溯源靠結構、不靠模型自律（原則 3）。marked/MathJax 由 index.html 全域載入。
function renderHtml(text: string, prefix: string): string {
  const marked = (window as unknown as { marked?: { parse(s: string): string } }).marked
  const math: string[] = []
  const t = text.replace(
    /\$\$[\s\S]+?\$\$|\$[^\n$]+?\$|\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]/g,
    (m) => { math.push(m); return `@@M${math.length - 1}@@` },
  )
  let html = marked ? marked.parse(t) : t.replace(/\n/g, "<br>")
  html = html.replace(/@@M(\d+)@@/g, (_m, i) => {
    const tex = math[+i]
    const esc = tex.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    const isBlock = /^\$\$|^\\\[/.test(tex)
    const tag = isBlock ? "div" : "span"
    return `<${tag} class="mathcopy${isBlock ? " mathcopy-block" : ""}" data-tex="${esc.replace(/"/g, "&quot;")}">${esc}</${tag}>`
  })
  return html.replace(/\[(\d+)\]/g, (_m, n) => `<a href="#${prefix}-${n}" class="cite">[${n}]</a>`)
}

function MessageBody({ text, prefix }: { text: string; prefix: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const mj = (window as unknown as { MathJax?: { typesetPromise?(els: Element[]): Promise<void> } }).MathJax
    if (ref.current && mj?.typesetPromise) mj.typesetPromise([ref.current]).catch(() => {})
  }, [text])
  return (
    <div ref={ref} className="answer-md text-[15px] leading-relaxed"
         dangerouslySetInnerHTML={{ __html: renderHtml(text, prefix) }} />
  )
}

// 選取數學 → Ctrl/⌘+C 複製到 LaTeX 原始碼（含 $）。刻意不做「點公式就複製」（使用者要求）。
function installMathCopy(): () => void {
  const mathOf = (n: Node | null): Element | null => {
    if (!n) return null
    const el = n.nodeType === 1 ? (n as Element) : n.parentElement
    return el ? el.closest(".mathcopy") : null
  }
  function onCopy(e: ClipboardEvent) {
    const sel = window.getSelection()
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed || !e.clipboardData) return
    const frag = sel.getRangeAt(0).cloneContents()
    const maths = frag.querySelectorAll(".mathcopy")
    if (maths.length === 0) {
      const a = mathOf(sel.anchorNode)
      if (a && a === mathOf(sel.focusNode)) {   // 選取整個落在單一數學元素內
        e.clipboardData.setData("text/plain", a.getAttribute("data-tex") || "")
        e.preventDefault()
      }
      return
    }
    maths.forEach((m) => {
      const tex = m.getAttribute("data-tex") || ""
      const block = m.classList.contains("mathcopy-block")
      m.replaceWith(document.createTextNode(block ? `\n${tex}\n` : tex))
    })
    e.clipboardData.setData("text/plain", frag.textContent || "")
    e.preventDefault()
  }
  document.addEventListener("copy", onCopy)
  return () => document.removeEventListener("copy", onCopy)
}

function Sources({ sources, prefix }: { sources: Source[]; prefix: string }) {
  if (!sources.length) return null
  return (
    <div className="mt-2 space-y-0.5 border-t pt-2 text-xs">
      <div className="font-medium text-muted-foreground">來源</div>
      {sources.map((s) => (
        <div key={s.n} id={`${prefix}-${s.n}`} className="scroll-mt-16">
          <span className="text-muted-foreground">[{s.n}]</span>{" "}
          {s.kind === "corpus" && <Badge variant="secondary" className="mr-1">📎 你收藏的</Badge>}
          <a href={s.url} target="_blank" rel="noopener"
             className="break-all text-primary hover:underline">{s.title}</a>
        </div>
      ))}
    </div>
  )
}

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

  useEffect(() => {
    api.state().then((s) => setRootCount(s.root_count)).catch(() => {})
  }, [])
  useEffect(() => installMathCopy(), [])   // 選取數學→Ctrl/⌘+C 得 LaTeX（不點公式）
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
      onToken: (t) => {
        full += t
        setStage(null)
        setStreaming(full)
      },
      onError: (t) => {
        setStreaming(null)
        setStage(null)
        setMessages([...hist, { role: "user", content: msg },
          { role: "assistant", content: "⚠ " + t }])
      },
      onDone: (text, sources, extra) => {
        const next: Message[] = [...hist, { role: "user", content: msg },
          { role: "assistant", content: text || full, sources, found_extra: extra }]
        setMessages(next)
        setStreaming(null)
        setStage(null)
        api.autosave(next, tempId.current).then((r) => { tempId.current = r.temp_id }).catch(() => {})
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
      claim: c.claim,
      ladder: c.ladder.join("\n"),
      evidence_urls: c.evidence_urls.join(", "),
      save_convo: saveConvo,
      history: messages,
      temp_id: tempId.current,
    })
    setCandDone((d) => ({ ...d, [i]: r.status === "exists" ? "➖ 已收過（沒重複收）" : "✅ 已精選" }))
    if (r.status === "created") setRootCount((n) => n + 1)
  }

  const empty = messages.length === 0 && streaming === null && stage === null
  const freshCands = (candidates || []).filter((c) => !c.already)

  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 pb-2">
        <h1 className="text-lg font-bold">🧠 跟你的知識庫聊</h1>
        <p className="text-xs text-muted-foreground">
          從你存下的 {rootCount} 條核心理解出發，有話直說、不順著你講好聽話。
        </p>
      </div>

      <div className="flex-1 space-y-4 py-2">
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
            <div key={i} className="flex justify-end">
              <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-muted px-4 py-2">
                {m.content}
              </div>
            </div>
          ) : (
            <div key={i} className="rounded-xl bg-card px-4 py-3 shadow-sm">
              <MessageBody text={m.content} prefix={`m${i}`} />
              <Sources sources={m.sources || []} prefix={`m${i}`} />
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

      <div className="sticky bottom-0 shrink-0 bg-background pt-2 pb-1">
        <div className="flex items-end gap-2 rounded-2xl bg-muted px-3 py-2 focus-within:ring-1 focus-within:ring-ring">
          <Textarea
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            placeholder="丟一個想法、一個「為什麼 X 要這樣」、或接著上一句往下問…"
            className="max-h-40 min-h-0 resize-none border-0 bg-transparent p-1 shadow-none focus-visible:ring-0"
          />
          <Button size="icon" className="shrink-0 rounded-full" disabled={busy} onClick={send}
                  aria-label="送出">↑</Button>
        </div>
        <div className="flex items-center gap-4 pt-1">
          <label className="flex items-center gap-1 text-xs text-muted-foreground">
            <input type="checkbox" checked={brainstorm}
                   onChange={(e) => setBrainstorm(e.target.checked)} />
            🧠 腦力激盪（這輪純聊、不找資料）
          </label>
          {messages.length > 0 && (
            <button onClick={distill} disabled={busy}
                    className="text-xs text-muted-foreground hover:underline">🧵 整理成重點</button>
          )}
        </div>
      </div>
    </div>
  )
}
