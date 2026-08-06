import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { pages, type Message } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Sources, FoundExtra } from "@/components/Sources"

type Chapter = { title: string; start: number; end: number }

export default function ConversationViewPage() {
  const { id } = useParams()
  const cid = Number(id)
  const [conv, setConv] = useState<{ title: string; messages: Message[] } | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [chapters, setChapters] = useState<Chapter[] | null>(null)   // null=切分中
  const [segBusy, setSegBusy] = useState(false)

  useEffect(() => {
    pages.conversation(cid).then((c) =>
      c.found ? setConv({ title: c.title, messages: c.messages }) : setNotFound(true),
    ).catch(() => setNotFound(true))
    // 章節持久化：首次切一次、之後直接讀（後端持久化）
    pages.segment(cid).then((r) => setChapters(r.found ? r.chapters : [])).catch(() => setChapters([]))
  }, [cid])

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

  const renderMsg = (m: Message, i: number) =>
    m.role === "user" ? (
      <div key={i} className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-muted px-4 py-2">{m.content}</div>
      </div>
    ) : (
      <div key={i} className="rounded-xl bg-card px-4 py-3 shadow-sm">
        <Markdown text={m.content} prefix={`c${i}`} />
        <Sources sources={m.sources || []} prefix={`c${i}`} />
        <FoundExtra extra={m.found_extra || []} />
      </div>
    )

  const useChapters = chapters && chapters.length > 1   // 有多章才用折疊目錄

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
          {chapters.map((ch, i) => (
            <details key={i} className="group rounded-xl bg-card shadow-sm">
              <summary className="cursor-pointer list-none px-4 py-3 font-medium hover:bg-muted/40">
                <span className="mr-1 text-muted-foreground group-open:hidden">▸</span>
                <span className="mr-1 hidden text-muted-foreground group-open:inline">▾</span>
                {ch.title}
                <span className="ml-2 text-xs font-normal text-muted-foreground">第 {ch.start}–{ch.end} 則</span>
              </summary>
              <div className="space-y-3 border-t px-4 py-3">
                {conv.messages.slice(ch.start - 1, ch.end).map((m, j) => renderMsg(m, ch.start - 1 + j))}
              </div>
            </details>
          ))}
        </div>
      ) : (
        <div className="space-y-4">{conv.messages.map(renderMsg)}</div>
      )}
    </div>
  )
}
