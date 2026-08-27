import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages, type ExtItem } from "@/lib/api"
import { Markdown } from "@/components/Markdown"

// spec 074：開發模式的主區＝**那一份檔案**，全寬。
// ⚠️ 選哪個專案／哪一層／哪一份，全部在**側欄**（IDE 的形狀），而狀態走 URL
//    ⇒ 這一頁不持有任何選取狀態，也不用跟側欄溝通。
// ⚠️ **唯讀**：外部知識不編輯、不搬動。「寫在哪就算哪邊」——所以沒有「移動」這個動作，
//    也就沒有「我到底搬過去了沒」那種狀態（雙模式介面第三個坑）。

export default function DevPage() {
  const [sp] = useSearchParams()
  const [doc, setDoc] = useState<ExtItem | null>(null)
  const [miss, setMiss] = useState(false)
  const iid = Number(sp.get("doc") || 0)

  useEffect(() => {
    if (!iid) { setDoc(null); setMiss(false); return }
    setDoc(null); setMiss(false)
    pages.extItem(iid).then(setDoc).catch(() => setMiss(true))
  }, [iid])

  if (!iid) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="max-w-md space-y-2 text-center">
          <p className="text-4xl">🧰</p>
          <p className="text-sm text-muted-foreground">
            左邊選一個專案、一層、一份檔案。這裡讀的是你其他專案的知識庫。
          </p>
          <p className="text-xs text-muted-foreground">
            還沒有專案？到 <Link to="/bases" className="text-primary hover:underline">⚙ 管理專案</Link> 加一個。
          </p>
        </div>
      </div>
    )
  }
  if (miss) return <p className="p-6 text-sm text-muted-foreground">找不到這一份。</p>
  if (!doc) return <p className="p-6 text-sm text-muted-foreground">載入中…</p>
  return (
    <div className="h-full overflow-y-auto">
      {/* ⚠️ 每一份都標它來自哪個 repo——看不出是誰的，就等於冒充你自己的知識 */}
      <div className="sticky top-0 z-10 border-b bg-background/95 px-6 py-2 backdrop-blur">
        <p className="truncate text-xs text-muted-foreground">
          <span className="rounded bg-muted px-1.5 py-0.5">{doc.repo}</span>
          <span className="mx-2">/</span>
          {doc.path.replace(/^knowledge\//, "")}
        </p>
      </div>
      <div className="mx-auto max-w-5xl px-6 py-5">
        <Markdown text={doc.body} prefix={`ext${doc.id}`} />
      </div>
    </div>
  )
}
