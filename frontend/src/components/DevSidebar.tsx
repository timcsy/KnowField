import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages, type ExtBase } from "@/lib/api"
import { cn } from "@/lib/utils"

// spec 074：開發模式的側欄＝**專案清單**，就這樣。
// ⚠️ 檔案樹**不在這裡**——它在主區的左半（IDE：最左是工作區／專案，接著才是檔案樹、編輯器）。
// ⚠️ 互動那套（領域／對話歷史／身分）一個都不進來——硬把兩套導覽疊在一起，
//    就是雙模式介面的第一個坑（「我寫在哪一邊？」）。
export function DevSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const [sp, setSp] = useSearchParams()
  const [bases, setBases] = useState<ExtBase[] | null>(null)
  const bid = Number(sp.get("base") || 0)

  useEffect(() => {
    pages.bases().then((d) => setBases(d.bases.filter((b) => b.status === "ok")))
      .catch(() => setBases([]))
  }, [])
  useEffect(() => {
    if (bases?.length && !bid) {
      const s = new URLSearchParams(sp); s.set("base", String(bases[0].id))
      setSp(s, { replace: true })
    }
  }, [bases, bid, sp, setSp])

  const pick = (id: number) => {
    // 換專案就放掉層與檔案——那是**另一個專案**的位置，留著只會指到空的
    const s = new URLSearchParams(sp)
    s.set("base", String(id)); s.delete("layer"); s.delete("doc")
    setSp(s); onNavigate?.()
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-1">
      <p className="px-2 pt-1 text-xs font-medium text-muted-foreground">專案</p>
      {bases === null ? (
        <p className="px-2 text-xs text-muted-foreground">載入中…</p>
      ) : bases.length === 0 ? (
        <p className="px-2 text-xs text-muted-foreground">
          還沒有專案。到{" "}
          <Link to="/bases" onClick={onNavigate} className="text-primary hover:underline">⚙ 管理專案</Link>
          {" "}加一個進來。
        </p>
      ) : (
        <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto">
          {bases.map((b) => (
            <li key={b.id}>
              <button onClick={() => pick(b.id)} title={`${b.repo} · ${b.branch}`}
                className={cn("flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-sm hover:bg-sidebar-accent",
                  bid === b.id && "bg-sidebar-accent font-medium")}>
                <span className="min-w-0 flex-1 truncate text-left">📁 {b.name || b.repo}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{b.n_items}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <Link to="/bases" onClick={onNavigate}
        className="rounded-lg px-3 py-1 text-xs text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">
        ⚙ 管理專案
      </Link>
    </div>
  )
}
