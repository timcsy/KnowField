import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages } from "@/lib/api"
import { KindBadge } from "@/components/KindBadge"

// spec 068：一天三條複習。
//
// 放在聊天頁的空狀態：**你正要開始想事情，脈絡剛好**，而且零額外介面。
//
// ⚠️ 排序在後端，而且**只有時間**（最久沒出現的優先）。
// 任何「熱門度」的訊號都不准進來——那是馬太陷阱：被引用最多的會一直被推到你眼前，
// 而**你最需要重新遇到的正好是你快忘了的那些**。
// ⇒ 所以這裡也不重新排序、不加「熱門」標記。
export function Rehearse() {
  const [items, setItems] = useState<{ id: number; claim: string; kind: string }[]>([])
  useEffect(() => { pages.rehearse().then((r) => setItems(r.items || [])).catch(() => {}) }, [])
  if (!items.length) return null
  return (
    <div className="mx-auto mt-6 w-full max-w-lg space-y-1.5 text-left">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground/60">
        🕘 你以前想過的
      </div>
      {items.map((w) => (
        <Link key={w.id} to="/roots"
              className="block rounded-lg px-3 py-2 text-sm leading-relaxed text-muted-foreground hover:bg-accent hover:text-foreground">
          {/* 複習是**一瞥**，不是重讀——整段展開會把空狀態擠爆，而你就不會看了 */}
          <span className="line-clamp-2">
            <KindBadge kind={w.kind} /> 💡 {w.claim}
          </span>
        </Link>
      ))}
    </div>
  )
}
