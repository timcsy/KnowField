import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages } from "@/lib/api"
import { Markdown } from "@/components/Markdown"

// 文章庫＝場的輸出面（與地基「核心理解」分離）：唯讀閱讀＋管理。
// 文章＝輸出物、不回灌場（原則 6）——這裡只讀/刪，生成留在核心理解頁（貼原料）。
const LEN: Record<string, string> = { short: "短", medium: "中", long: "長" }
const LVL: Record<string, string> = { intro: "入門", intermediate: "進階", expert: "專家" }

export default function ArticlesPage() {
  const [list, setList] = useState<{ id: number; topic: string; title: string; length: string; level: string; created_at: string }[] | null>(null)
  const [open, setOpen] = useState<{ id: number; title: string; markdown: string } | null>(null)
  const load = () => pages.listArticles().then((r) => setList(r.articles)).catch(() => setList([]))
  useEffect(() => { load() }, [])

  async function view(id: number) { setOpen(await pages.getArticle(id)) }
  async function del(id: number) {
    if (!confirm("刪除這篇文章？")) return
    await pages.deleteArticle(id); if (open?.id === id) setOpen(null); load()
  }

  if (list === null) return <p className="text-sm text-muted-foreground">載入中…</p>
  return (
    <div className="space-y-4 pb-8">
      <div>
        <h1 className="text-2xl font-bold">📝 你的文章</h1>
        <p className="text-xs text-muted-foreground">
          從核心理解生成、保存下來的高證實文章（只採已證實／推論、引用連回佐證）。文章＝輸出物，不回灌場。
          到 <Link to="/roots" className="underline hover:text-foreground">💡 核心理解</Link> 按「✍️ 生成文章」寫新的。
        </p>
      </div>

      {list.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          還沒有保存的文章。到「💡 核心理解」給一個主題生成，再按「💾 保存」收進這裡。
        </p>
      ) : (
        <ul className="space-y-1.5">
          {list.map((a) => (
            <li key={a.id} className="group flex items-center gap-2 rounded-xl bg-card px-4 py-3 shadow-sm">
              <button onClick={() => view(a.id)} className="min-w-0 flex-1 text-left">
                <div className="truncate text-[15px] font-medium hover:underline">{a.title || a.topic}</div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-muted-foreground">
                  <span>{a.created_at?.slice(0, 10)}</span>
                  {LEN[a.length] && <span>長度：{LEN[a.length]}</span>}
                  {LVL[a.level] && <span>難度：{LVL[a.level]}</span>}
                </div>
              </button>
              <button onClick={() => del(a.id)}
                      className="shrink-0 text-xs text-muted-foreground opacity-0 transition hover:text-destructive group-hover:opacity-100"
                      title="刪除這篇文章">刪</button>
            </li>
          ))}
        </ul>
      )}

      {open && (
        <div className="rounded-lg border bg-background p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs text-muted-foreground">閱讀中</span>
            <div className="flex gap-3">
              <button onClick={async () => { try { await navigator.clipboard.writeText(open.markdown) } catch { /* 無剪貼簿 */ } }}
                      className="text-xs text-muted-foreground hover:text-foreground">📋 複製 Markdown</button>
              <button onClick={() => setOpen(null)} className="text-xs text-muted-foreground hover:text-foreground">✕ 收起</button>
            </div>
          </div>
          <Markdown text={open.markdown} prefix="artv" />
        </div>
      )}
    </div>
  )
}
