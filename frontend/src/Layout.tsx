import { useEffect } from "react"
import { Link, Outlet, useLocation } from "react-router-dom"
import { installMathCopy } from "@/components/Markdown"
import { cn } from "@/lib/utils"

const nav = [
  { label: "💬 對話", to: "/" },
  { label: "💡 核心理解", to: "/roots" },
  { label: "📚 來源", to: "/sources" },
]

export default function Layout() {
  const { pathname } = useLocation()
  useEffect(() => installMathCopy(), [])   // 選取數學→Ctrl/⌘+C 得 LaTeX，全站生效
  const isActive = (to: string) =>
    to === "/" ? pathname === "/" || pathname.startsWith("/conversations")
      : to === "/sources" ? pathname.startsWith("/source")   // /source（詳情）＋/sources
      : pathname.startsWith(to)
  const isChat = pathname === "/"

  return (
    <div className="flex h-svh flex-col bg-background text-foreground md:flex-row">
      {/* 桌面：主導覽側欄 */}
      <aside className="hidden w-60 shrink-0 flex-col bg-sidebar p-3 md:flex">
        <Link to="/" className="px-2 py-3 text-lg font-bold">🧠 KnowField</Link>
        <nav className="flex flex-col gap-1">
          {nav.map((n) => (
            <Link key={n.to} to={n.to}
              className={cn(
                "rounded-lg px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
                isActive(n.to) && "bg-sidebar-accent font-medium",
              )}>
              {n.label}
            </Link>
          ))}
        </nav>
        <p className="mt-auto px-2 text-[11px] text-muted-foreground">消化到底，隨時可回溯。</p>
      </aside>

      {/* 手機：頂部導覽 bar */}
      <header className="flex shrink-0 items-center gap-1 border-b bg-sidebar px-2 py-1.5 md:hidden">
        <Link to="/" className="px-1 text-base font-bold">🧠</Link>
        {nav.map((n) => (
          <Link key={n.to} to={n.to}
            className={cn(
              "rounded-md px-2 py-1 text-sm text-sidebar-foreground",
              isActive(n.to) && "bg-sidebar-accent font-medium",
            )}>
            {n.label}
          </Link>
        ))}
      </header>

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
