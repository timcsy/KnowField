import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { pages, type Message } from "@/lib/api"
import { Markdown } from "@/components/Markdown"
import { Sources, FoundExtra } from "@/components/Sources"

export default function ConversationViewPage() {
  const { id } = useParams()
  const cid = Number(id)
  const [conv, setConv] = useState<{ title: string; messages: Message[] } | null>(null)
  const [notFound, setNotFound] = useState(false)
  const [chapters, setChapters] = useState<{ title: string; start: number; end: number }[] | null>(null)

  useEffect(() => {
    pages.conversation(cid).then((c) =>
      c.found ? setConv({ title: c.title, messages: c.messages }) : setNotFound(true),
    ).catch(() => setNotFound(true))
  }, [cid])

  async function retitle() {
    const r = await pages.retitleConv(cid)
    if (r.title && conv) setConv({ ...conv, title: r.title })
  }
  async function segment() {
    const r = await pages.segment(cid)
    if (r.found) setChapters(r.chapters)
  }

  if (notFound)
    return (
      <p className="text-sm text-muted-foreground">
        找不到這段對話。<Link to="/conversations" className="text-primary hover:underline">← 對話存檔</Link>
      </p>
    )
  if (!conv) return <p className="text-sm text-muted-foreground">載入中…</p>
  return (
    <div className="space-y-4 pb-8">
      <div>
        <Link to="/conversations" className="text-sm text-muted-foreground hover:underline">← 對話存檔</Link>
        <h1 className="mt-1 text-2xl font-bold">{conv.title || "（未命名對話）"}</h1>
        <p className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
          <span>唯讀的參考（不進地基）。</span>
          <Link to={`/?resume=${cid}`} className="text-primary hover:underline">接著聊</Link>
          <button onClick={retitle} className="hover:text-foreground">重生標題</button>
          <button onClick={segment} className="hover:text-foreground">整理成章節</button>
          <a href={`/conversations/${cid}/export?as=md`} target="_blank" rel="noopener"
             className="hover:text-foreground">匯出 Markdown</a>
        </p>
        {chapters && (
          <div className="mt-2 rounded-lg bg-muted p-3 text-sm">
            <div className="mb-1 font-medium">🔖 共 {chapters.length} 章</div>
            <ol className="ml-4 list-decimal space-y-0.5 text-muted-foreground">
              {chapters.map((ch, i) => (
                <li key={i}>{ch.title}<span className="ml-1 text-xs opacity-60">（第 {ch.start}–{ch.end} 則）</span></li>
              ))}
            </ol>
          </div>
        )}
      </div>
      <div className="space-y-4">
        {conv.messages.map((m, i) =>
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
          ),
        )}
      </div>
    </div>
  )
}
