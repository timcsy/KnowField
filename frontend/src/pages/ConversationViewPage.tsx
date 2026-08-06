import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { pages, type Message } from "@/lib/api"
import { Markdown } from "@/components/Markdown"

export default function ConversationViewPage() {
  const { id } = useParams()
  const cid = Number(id)
  const [conv, setConv] = useState<{ title: string; messages: Message[] } | null>(null)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    pages.conversation(cid).then((c) =>
      c.found ? setConv({ title: c.title, messages: c.messages }) : setNotFound(true),
    ).catch(() => setNotFound(true))
  }, [cid])

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
        <p className="mt-1 text-xs text-muted-foreground">
          唯讀的參考（不進地基）。
          <Link to={`/?resume=${cid}`} className="ml-2 text-primary hover:underline">接著聊</Link>
          <a href={`/conversations/${cid}/export?as=md`} target="_blank" rel="noopener"
             className="ml-2 hover:underline">匯出 Markdown</a>
        </p>
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
            </div>
          ),
        )}
      </div>
    </div>
  )
}
