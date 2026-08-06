import ChatPage from "./ChatPage"
import { cn } from "@/lib/utils"

// 遷移中：只有「跟知識聊」是 React；其餘先連舊 Jinja 頁（strangler，逐頁遷）。
const nav = [
  { label: "💬 跟知識聊", href: "/app/", active: true },
  { label: "💡 核心理解", href: "/roots" },
  { label: "📚 知識庫", href: "/library" },
  { label: "➕ 收進", href: "/ingest" },
  { label: "🗂 對話存檔", href: "/conversations" },
]

function App() {
  return (
    <div className="flex h-svh bg-background text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col bg-sidebar p-3 md:flex">
        <a href="/app/" className="px-2 py-3 text-lg font-bold">🧠 KnowField</a>
        <nav className="flex flex-col gap-1">
          {nav.map((n) => (
            <a
              key={n.label}
              href={n.href}
              className={cn(
                "rounded-lg px-3 py-2 text-sm text-sidebar-foreground hover:bg-sidebar-accent",
                n.active && "bg-sidebar-accent font-medium",
              )}
            >
              {n.label}
            </a>
          ))}
        </nav>
        <p className="mt-auto px-2 text-[11px] text-muted-foreground">消化到底，隨時可回溯。</p>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto h-full max-w-3xl px-4 py-4 md:px-8">
          <ChatPage />
        </div>
      </main>
    </div>
  )
}

export default App
