import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { useScope } from "@/lib/scope"
import { pages } from "@/lib/api"

// 文章庫＝場的輸出面（與地基「理解」分離）：版面對齊「來源」頁，點進去＝獨立詳情頁 /articles/:id。
// 文章＝輸出物、不回灌場（原則 6）——這裡只列/刪，生成留在理解頁（貼原料）。
const LEN: Record<string, string> = { short: "短", medium: "中", long: "長" }
const LVL: Record<string, string> = { intro: "入門", intermediate: "進階", expert: "專家" }

export default function ArticlesPage() {
  const [all, setAll] = useState<{ id: number; topic: string; title: string; length: string; level: string; created_at: string }[] | null>(null)
  const { inScope, banner } = useScope("article")
  const list = all === null ? null : all.filter((a) => inScope(a.id))
  const load = () => pages.listArticles().then((r) => setAll(r.articles)).catch(() => setAll([]))
  useEffect(() => { load() }, [])

  async function del(id: number) {
    if (!confirm("封存這份應用？\n\n它會離開活的知識庫，但不會消失——可以在「領域」頁復原。")) return
    await pages.deleteArticle(id); load()
  }

  return (
    <div className="space-y-5 pb-8">
      {banner}
      <div className="flex items-center gap-2">
        <h1 className="text-2xl font-bold">🧩 應用</h1>
        <span className="hidden text-sm text-muted-foreground sm:inline">
          從理解長出來的東西——把地基用出去的地方。⚠️ 輸出物，不回灌場。
        </span>
        <Link to="/roots" className="ml-auto rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90">
          ✍️ 生成新的
        </Link>
      </div>

      {list === null ? (
        <p className="text-sm text-muted-foreground">載入中…</p>
      ) : list.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          還沒有保存的應用。到「💡 理解」給一個主題生成，再按「💾 保存」收進這裡。
        </p>
      ) : (
        <div className="space-y-2">
          {list.map((a) => (
            <div key={a.id} className="group flex items-start justify-between gap-3 rounded-xl bg-card px-4 py-3 shadow-sm">
              <div className="min-w-0">
                <div className="font-medium">
                  <Link to={`/articles/${a.id}`} className="hover:underline">{a.title || a.topic}</Link>
                  {LEN[a.length] && <span className="ml-2 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">長度：{LEN[a.length]}</span>}
                  {LVL[a.level] && <span className="ml-1 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">難度：{LVL[a.level]}</span>}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {a.created_at && <span className="mr-2">🗓 {a.created_at.slice(0, 10)}</span>}
                  {a.topic && <span className="opacity-60">主題：{a.topic}</span>}
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-3 text-xs text-muted-foreground opacity-0 transition group-hover:opacity-100">
                <Link to={`/articles/${a.id}`} className="hover:text-foreground">檢視</Link>
                <button onClick={() => del(a.id)} className="hover:text-destructive">📦 封存</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
