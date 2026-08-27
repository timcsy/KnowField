import { Link, useLocation } from "react-router-dom"
import { cn } from "@/lib/utils"

// spec 074／080：思考／開發。
// ⚠️ 這一邊原本叫「互動」，而**「互動」已經是那五格裡的一格**（💬 互動 ＝ 對話）
//    ⇒ 同一個側欄上下兩處，同一個詞指兩件事。改名為「思考」（使用者 2026-08-27）。
//    ⓘ 它也說得出那五格為什麼在一起：來源是原料、互動是消化、理解是地基、
//    應用是輸出——**那整條就是思考**。開發那邊相對地是「看別人怎麼想的」。
// ⚠️ **分層不並列**：模式在 logo 那一列，persona 在下面那一層——
//    那三個參考工具的切換都在最頂端，而那正是 persona 切換器現在的位置，兩個搶同一格會爆。
// ⚠️ **切模式不關抽屜。** 手機上側欄是抽屜，而「選了一個目的地」才該關它——
//    切模式正好相反：你切過去就是**要看新的那份側欄**（開發那邊是專案清單）。
//    關掉等於把你要看的東西收走，然後你得再點一次漢堡。
export function ModeSwitch() {
  const { pathname } = useLocation()
  const dev = pathname.startsWith("/dev")
  return (
    <div className="flex shrink-0 overflow-hidden rounded-lg border text-xs">
      {[["思考", "/", !dev], ["開發", "/dev", dev]].map(([label, to, on]) => (
        <Link key={to as string} to={to as string}
          className={cn("px-2.5 py-1",
            on ? "bg-sidebar-accent font-medium" : "text-muted-foreground hover:text-foreground")}>
          {label as string}
        </Link>
      ))}
    </div>
  )
}
