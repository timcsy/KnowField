import { useEffect, useRef, useState } from "react"
import { Link, useParams, useSearchParams } from "react-router-dom"
import { pages, type Message } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Sources, FoundExtra } from "@/components/Sources"
import { cn } from "@/lib/utils"

type Chapter = { title: string; start: number; end: number }

export default function ConversationViewPage() {
  const { id } = useParams()
  const cid = Number(id)
  const [sp] = useSearchParams()
  const focusFrom = Number(sp.get("from") || 0)          // 由來帶來的出處則數範圍→定位
  const focusTo = Number(sp.get("to") || focusFrom)
  const [conv, setConv] = useState<{ title: string; messages: Message[] } | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [chapters, setChapters] = useState<Chapter[] | null>(null)   // null=切分中
  const [segBusy, setSegBusy] = useState(false)
  const focusRef = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    pages.conversation(cid).then((c) =>
      c.found ? setConv({ title: c.title, messages: c.messages }) : setNotFound(true),
    ).catch(() => setNotFound(true))
    pages.segment(cid).then((r) => setChapters(r.found ? r.chapters : [])).catch(() => setChapters([]))
  }, [cid])

  // 出處章節：展開它、捲到它（由來精準定位，不再丟到頂端）
  useEffect(() => {
    if (focusFrom && focusRef.current) {
      focusRef.current.open = true
      focusRef.current.scrollIntoView({ behavior: "smooth", block: "start" })
    }
  }, [chapters, focusFrom])

  async function retitle() {
    const r = await pages.retitleConv(cid)
    if (r.title && conv) setConv({ ...conv, title: r.title })
  }
  async function reslice() {
    setSegBusy(true); setChapters(null)
    const r = await pages.segment(cid, true)
    setChapters(r.found ? r.chapters : [])
    setSegBusy(false)
  }

  if (notFound)
    return (
      <p className="text-sm text-muted-foreground">
        找不到這段對話。<Link to="/" className="text-primary hover:underline">← 對話</Link>
      </p>
    )
  if (!conv) return <p className="text-sm text-muted-foreground">載入中…</p>

  const renderMsg = (m: Message, i: number) => {
    const focused = focusFrom > 0 && i + 1 >= focusFrom && i + 1 <= focusTo   // 出處範圍→高亮
    if (m.role === "user")
      return (
        <div key={i} className="flex justify-end">
          <div className={cn("max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-muted px-4 py-2",
            focused && "ring-2 ring-primary/40")}>{m.content}</div>
        </div>
      )
    return (
      <div key={i} className={cn("rounded-xl bg-card px-4 py-3 shadow-sm", focused && "ring-2 ring-primary/40")}>
        <Markdown text={m.content} prefix={`c${i}`} />
        <Sources sources={m.sources || []} prefix={`c${i}`} />
        <FoundExtra extra={m.found_extra || []} />
      </div>
    )
  }

  const useChapters = chapters && chapters.length > 1

  return (
    <div className="space-y-4 pb-8">
      <div>
        <Link to="/" className="text-sm text-muted-foreground hover:underline">← 對話</Link>
        <h1 className="mt-1 text-2xl font-bold">{conv.title || "（未命名對話）"}</h1>
        <p className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>唯讀的參考（不進地基）。</span>
          <Link to={`/?resume=${cid}`} className="text-primary hover:underline">接著聊</Link>
          <button onClick={retitle} className="hover:text-foreground">重生標題</button>
          <button onClick={reslice} disabled={segBusy} className="hover:text-foreground">重新分章</button>
          <a href={`/conversations/${cid}/export?as=md`} target="_blank" rel="noopener"
             className="hover:text-foreground">匯出 Markdown</a>
        </p>
      </div>

      {chapters === null ? (
        <p className="text-sm text-muted-foreground">整理章節中…（第一次會慢一點，之後就記住了）</p>
      ) : useChapters ? (
        <div className="space-y-2">
          <div className="text-xs text-muted-foreground">🔖 共 {chapters.length} 章——點章節標題展開（預設收起，好找）</div>
          {chapters.map((ch, i) => {
            const isFocus = focusFrom > 0 && ch.start <= focusFrom && ch.end >= focusFrom   // 涵蓋出處起點
            return (
              <details key={i} ref={isFocus ? focusRef : undefined}
                       className={cn("group rounded-xl bg-card shadow-sm", isFocus && "ring-2 ring-primary/50")}>
                <summary className="cursor-pointer list-none px-4 py-3 font-medium hover:bg-muted/40">
                  <span className="mr-1 text-muted-foreground group-open:hidden">▸</span>
                  <span className="mr-1 hidden text-muted-foreground group-open:inline">▾</span>
                  {ch.title}
                  <span className="ml-2 text-xs font-normal text-muted-foreground">第 {ch.start}–{ch.end} 則</span>
                  {isFocus && <span className="ml-2 text-xs font-normal text-primary">← 這條核心理解的出處</span>}
                </summary>
                <div className="space-y-3 border-t px-4 py-3">
                  {conv.messages.slice(ch.start - 1, ch.end).map((m, j) => renderMsg(m, ch.start - 1 + j))}
                </div>
              </details>
            )
          })}
        </div>
      ) : (
        <div className="space-y-4">{conv.messages.map(renderMsg)}</div>
      )}
    </div>
  )
}
