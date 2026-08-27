import { useEffect, useState } from "react"
import { Outlet, useLocation } from "react-router-dom"
import { installMathCopy } from "@/components/Markdown"
import { ConversationSidebar } from "@/components/ConversationSidebar"
import { ModeSwitch } from "@/components/ModeSwitch"
import { CommandPalette } from "@/components/CommandPalette"

export default function Layout() {
  const { pathname } = useLocation()
  const [drawer, setDrawer] = useState(false)
  useEffect(() => installMathCopy(), [])   // 選取數學→Ctrl/⌘+C 得 LaTeX，全站生效
  // 滿版頁：自己管捲動與版面。⚠️ `max-w-3xl` 的置中容器對「兩欄檔案總管」是致命的
  //    ——樹被擠成一小格、清單只剩半個螢幕（2026-08-26 使用者指出）。
  // spec 074：開發模式是 IDE 的形狀——側欄是檔案樹，主區是**那一份檔案**，要全寬
  const isFull = pathname === "/" || pathname.startsWith("/domains") || pathname.startsWith("/dev")

  return (
    <div className="flex h-svh flex-col bg-background text-foreground md:flex-row">
      {/* spec 066：全域搜尋。掛在 Layout ＝ 每一頁都按得到（它是全域的，不是某頁的功能）。 */}
      <CommandPalette />
      {/* 桌面：單一側欄（導覽＋新對話＋歷史） */}
      <aside className="hidden w-64 shrink-0 bg-sidebar md:block">
        <ConversationSidebar />
      </aside>

      {/* 手機：頂部漢堡 bar */}
      <header className="flex shrink-0 items-center gap-2 border-b bg-sidebar px-2 py-2 md:hidden">
        <button onClick={() => setDrawer(true)} aria-label="選單" className="px-1 text-xl">☰</button>
        <span className="min-w-0 flex-1 truncate font-bold">🧠 KnowField</span>
        {/* 手機上不用開抽屜就切得了模式 */}
        <ModeSwitch />
      </header>
      {/* 手機：側欄抽屜 */}
      {drawer && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div className="absolute inset-0 bg-black/30" onClick={() => setDrawer(false)} />
          <aside className="relative z-10 w-72 max-w-[80%] bg-sidebar shadow-xl">
            <ConversationSidebar onNavigate={() => setDrawer(false)} />
          </aside>
        </div>
      )}

      <main className="min-h-0 flex-1 overflow-hidden">
        {isFull ? (
          <Outlet />
        ) : (
          <div className="h-full overflow-y-auto">
            <div className="mx-auto max-w-3xl px-4 py-4 md:px-8">
              <Outlet />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
