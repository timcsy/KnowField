import { Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"

// spec 074：互動／開發。那個軸分的是**線性的、當下的來回** vs
// **有狀態、有產物、會回頭看的工作**。
// ⚠️ **分層不並列**：模式在 logo 那一列，persona 在下面那一層——
//    那三個參考工具的切換都在最頂端，而那正是 persona 切換器現在的位置，兩個搶同一格會爆。
export function ModeSwitch({ onNavigate }: { onNavigate?: () => void }) {
  const { pathname } = useLocation()
  const dev = pathname.startsWith("/dev")
  return (
    <div className="flex shrink-0 overflow-hidden rounded-lg border text-xs">
      {[["互動", "/", !dev], ["開發", "/dev", dev]].map(([label, to, on]) => (
        <Link key={to as string} to={to as string} onClick={onNavigate}
          className={cn("px-2 py-1",
            on ? "bg-sidebar-accent font-medium" : "text-muted-foreground hover:text-foreground")}>
          {label as string}
        </Link>
      ))}
    </div>
  )
}
