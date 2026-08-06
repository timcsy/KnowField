import { useEffect } from "react"
import { Link, Outlet, useLocation } from "react-router-dom"
import { installMathCopy } from "@/components/Markdown"
import { cn } from "@/lib/utils"

const nav = [
  { label: "💬 跟知識聊", to: "/" },
  { label: "💡 核心理解", to: "/roots" },
  { label: "📚 知識庫", to: "/library" },
  { label: "➕ 收進", to: "/ingest" },
  { label: "🗂 對話存檔", to: "/conversations" },
]

export default function Layout() {
  const { pathname } = useLocation()
  useEffect(() => installMathCopy(), [])   // 選取數學→Ctrl/⌘+C 得 LaTeX，全站生效
  const isActive = (to: string) =>
    to === "/" ? pathname === "/" : pathname.startsWith(to)
  return (
    <div className="flex h-svh bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col bg-sidebar p-3 md:flex">
        <Link to="/" className="px-2 py-3 text-lg font-bold">🧠 KnowField</Link>
        <nav className="flex flex-col gap-1">
          {nav.map((n) => (
            <Link
              key={n.to}
              to={n.to}
              className={cn(
                "rounded-lg px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
                isActive(n.to) && "bg-sidebar-accent font-medium",
              )}
            >
              {n.label}
            </Link>
          ))}
        </nav>
        <p className="mt-auto px-2 text-[11px] text-muted-foreground">消化到底，隨時可回溯。</p>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto h-full max-w-3xl px-4 py-4 md:px-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
