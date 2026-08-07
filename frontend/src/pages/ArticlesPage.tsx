import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages } from "@/lib/api"
import { Markdown } from "@/components/Markdown"

// 文章庫＝場的輸出面（與地基「核心理解」分離）：唯讀閱讀＋管理，版面對齊「來源」頁。
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
    if (!confirm("刪除這篇文章？（不可復原）")) return
    await pages.deleteArticle(id); if (open?.id === id) setOpen(null); load()
  }

  return (
    <div className="space-y-5 pb-8">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold">📝 文章</h1>
        <span className="hidden text-sm text-muted-foreground sm:inline">
          從核心理解生成、保存下來的高證實文章——輸出物，不回灌場。
        </span>
        <Link to="/roots" className="ml-auto rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90">
          ✍️ 生成新文章
        </Link>
      </div>

      {list === null ? (
        <p className="text-sm text-muted-foreground">載入中…</p>
      ) : list.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          還沒有保存的文章。到「💡 核心理解」給一個主題生成，再按「💾 保存」收進這裡。
        </p>
      ) : (
        <div className="space-y-2">
          {list.map((a) => (
            <div key={a.id} className="group flex items-start justify-between gap-3 rounded-xl bg-card px-4 py-3 shadow-sm">
              <div className="min-w-0">
                <div className="font-medium">
                  <button onClick={() => view(a.id)} className="text-left hover:underline">{a.title || a.topic}</button>
                  {LEN[a.length] && <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">長度：{LEN[a.length]}</span>}
                  {LVL[a.level] && <span className="ml-1 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">難度：{LVL[a.level]}</span>}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {a.created_at && <span className="mr-2">🗓 {a.created_at.slice(0, 10)}</span>}
                  {a.topic && <span className="opacity-60">主題：{a.topic}</span>}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground opacity-0 transition group-hover:opacity-100">
                <button onClick={() => view(a.id)} className="hover:text-foreground">檢視</button>
                <button onClick={() => del(a.id)} className="hover:text-destructive">刪除</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {open && (
        <div className="rounded-xl border bg-card p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between border-b pb-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground/60">閱讀中</span>
            <div className="flex gap-3 text-xs text-muted-foreground">
              <button onClick={async () => { try { await navigator.clipboard.writeText(open.markdown) } catch { /* 無剪貼簿 */ } }}
                      className="hover:text-foreground">📋 複製 Markdown</button>
              <button onClick={() => setOpen(null)} className="hover:text-foreground">✕ 收起</button>
            </div>
          </div>
          <Markdown text={open.markdown} prefix="artv" />
        </div>
      )}
    </div>
  )
}
