import { useEffect, useState } from "react"
import { Outlet, useLocation } from "react-router-dom"
import { installMathCopy } from "@/components/Markdown"
import { ConversationSidebar } from "@/components/ConversationSidebar"

export default function Layout() {
  const { pathname } = useLocation()
  const [drawer, setDrawer] = useState(false)
  useEffect(() => installMathCopy(), [])   // 選取數學→Ctrl/⌘+C 得 LaTeX，全站生效
  const isChat = pathname === "/"

  return (
    <div className="flex h-svh flex-col bg-background text-foreground md:flex-row">
      {/* 桌面：單一側欄（導覽＋新對話＋歷史） */}
      <aside className="hidden w-64 shrink-0 bg-sidebar md:block">
        <ConversationSidebar />
      </aside>

      {/* 手機：頂部漢堡 bar */}
      <header className="flex shrink-0 items-center gap-2 border-b bg-sidebar px-2 py-2 md:hidden">
        <button onClick={() => setDrawer(true)} aria-label="選單" className="px-1 text-xl">☰</button>
        <span className="font-bold">🧠 KnowField</span>
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
        {isChat ? (
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
