import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages, type ExtBase, type ExtItem } from "@/lib/api"
import { FileTree } from "@/components/FileTree"
import { Markdown } from "@/components/Markdown"
import { cn } from "@/lib/utils"

// spec 074：開發模式的主區＝**檔案樹｜預覽**（側欄是專案，那是 IDE 的最左段）。
// ⚠️ 手機上三欄不可能 ⇒ **master-detail**：沒選檔＝樹滿版，選了＝預覽滿版＋「← 檔案」。
//    而它不需要任何新狀態——「有沒有選檔」本來就在網址裡（`?doc=`）。

export default function DevPage() {
  const [sp, setSp] = useSearchParams()
  const [bases, setBases] = useState<ExtBase[] | null>(null)
  const [items, setItems] = useState<{ id: number; path: string }[]>([])
  const [doc, setDoc] = useState<ExtItem | null>(null)
  const bid = Number(sp.get("base") || 0)
  const iid = Number(sp.get("doc") || 0)

  useEffect(() => { pages.bases().then((d) => setBases(d.bases)).catch(() => setBases([])) }, [])
  useEffect(() => {
    if (!bid) { setItems([]); return }
    pages.baseTree(bid).then((d) => setItems(d.items)).catch(() => setItems([]))
  }, [bid])
  useEffect(() => {
    if (!iid) { setDoc(null); return }
    setDoc(null); pages.extItem(iid).then(setDoc).catch(() => setDoc(null))
  }, [iid])

  const go = (patch: Record<string, string>) => {
    const s = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(patch)) v ? s.set(k, v) : s.delete(k)
    setSp(s)
  }
  const base = bases?.find((b) => b.id === bid)

  if (bases && bases.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p className="max-w-sm text-sm text-muted-foreground">
          這裡讀的是你其他專案的知識庫。還沒有任何一個——
          到 <Link to="/bases" className="text-primary hover:underline">⚙ 管理專案</Link> 加一個進來。
        </p>
      </div>
    )
  }
  return (
    <div className="flex h-full min-h-0">
      {/* ── 檔案樹（手機：選了檔就讓位給預覽）── */}
      <div className={cn("flex min-h-0 w-full flex-col md:w-56 md:border-r lg:w-64",
                         iid && "hidden md:flex")}>
        {base && (
          <p className="truncate border-b px-3 py-1.5 text-xs text-muted-foreground">
            📁 {base.name || base.repo} · {base.branch}
          </p>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto p-1">
          <FileTree items={items} sel={iid} onPick={(id) => go({ doc: String(id) })} />
        </div>
      </div>

      {/* ── 預覽：吃掉剩下的整片寬度；⚠️ min-w-0，少了它長行會把樹擠爛 ── */}
      <div className={cn("min-w-0 flex-1 overflow-y-auto", !iid && "hidden md:block")}>
        {doc ? (
          <>
            <div className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background/95 px-4 py-2 backdrop-blur md:px-6">
              <button onClick={() => go({ doc: "" })}
                      className="shrink-0 text-xs text-muted-foreground hover:text-foreground md:hidden">
                ← 檔案
              </button>
              {/* ⚠️ 每一份都標它來自哪個 repo——看不出是誰的，就等於冒充你自己的知識 */}
              <p className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                <span className="rounded bg-muted px-1.5 py-0.5">{doc.repo}</span>
                <span className="mx-2">/</span>{doc.path.replace(/^knowledge\//, "")}
              </p>
            </div>
            <div className="mx-auto max-w-4xl px-4 py-5 md:px-8 md:py-6">
              <Markdown text={doc.body} prefix={`ext${doc.id}`} />
            </div>
          </>
        ) : (
          <div className="hidden h-full items-center justify-center px-6 text-center md:flex">
            <p className="max-w-sm text-sm text-muted-foreground">
              左邊挑一份來看。{base && `（${base.name || base.repo}）`}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
