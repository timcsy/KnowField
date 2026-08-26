import { useEffect, useState } from "react"
import { pages, type DomainContext as Ctx } from "@/lib/api"

// spec 070：領域頁存在的理由。
//
// 判準（spec 066 立的）：**如果這個介面給你的東西，搜尋也給得了，它就不該存在。**
// 清單正是搜尋結果的形狀 ⇒ 這一頁必須給出搜尋給不了的：**你沒在找的東西**。
//
// ⚠️ 所以這三塊**不折疊、不放頁尾**。清單是配角。
export function DomainContextPanel({ did, onGo }: { did: number | null; onGo: (d: number | null) => void }) {
  const [c, setC] = useState<Ctx | null>(null)
  useEffect(() => { pages.domainContext(did).then(setC).catch(() => setC(null)) }, [did])
  if (!c) return null
  const nothing = !c.crossings.length && !c.fringe.length && !c.nearby.length
  if (nothing && c.has_geometry) return null

  return (
    <div className="flex flex-wrap gap-x-8 gap-y-2 border-b px-3 py-2 text-xs">
      <div className="min-w-44">
        <div className="mb-0.5 font-medium text-muted-foreground">⛓ 通往哪裡</div>
        {c.crossings.length ? c.crossings.slice(0, 4).map((x) => (
          <button key={String(x.domain_id)} onClick={() => onGo(x.domain_id)}
                  className="mr-3 hover:underline">
            {x.name} <span className="text-muted-foreground">{x.count}</span>
          </button>
        )) : <span className="text-muted-foreground">沒有連到別區的</span>}
      </div>

      <div className="min-w-52">
        <div className="mb-0.5 font-medium text-muted-foreground">🪂 快掉出去的</div>
        {!c.has_geometry ? (
          // ⚠️ 說「算不出來」，不要顯示空的——後者會被讀成「這一區沒有邊陲」
          <span className="text-muted-foreground">（還沒有向量，算不出來）</span>
        ) : c.fringe.length ? c.fringe.map((f) => (
          <div key={`${f.kind}-${f.ref}`} className="truncate text-muted-foreground">
            {f.label.slice(0, 26)} <span className="opacity-60">{f.dist}</span>
          </div>
        )) : <span className="text-muted-foreground">都很靠攏</span>}
      </div>

      <div className="min-w-40">
        <div className="mb-0.5 font-medium text-muted-foreground">🧭 相鄰的區</div>
        {!c.has_geometry ? (
          <span className="text-muted-foreground">（還沒有向量，算不出來）</span>
        ) : c.nearby.length ? c.nearby.map((n) => (
          <button key={String(n.domain_id)} onClick={() => onGo(n.domain_id)}
                  className="mr-3 hover:underline">{n.name}</button>
        )) : <span className="text-muted-foreground">—</span>}
      </div>
    </div>
  )
}
