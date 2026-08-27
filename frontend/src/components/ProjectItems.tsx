import { Link } from "react-router-dom"
import type { KnowledgeItem, KnowledgeKind } from "@/lib/api"

// spec 080 收尾：開發模式的四格（互動／理解／應用）＋領域。
// ⚠️ 使用者：「在開發模式，仍然是領域、來源、互動、理解、應用」——
//    五格是**同一組鏡頭**，換的是被照的東西（這個專案的），不是鏡頭本身。
// ⚠️ **唯讀**：這裡不冊封、不搬動、不編輯。要動它，那是思考模式的事
//    （而那道閘門正是原則 6 那道膜）。

const TO: Record<string, (ref: number | string) => string> = {
  conversation: (r) => `/?resume=${r}`,
  why_node: () => "/roots",
  article: (r) => `/articles/${r}`,
}

const EMPTY: Record<string, string> = {
  conversation: "還沒有跟這個專案聊過。到「來源」那一格問它一句。",
  why_node: "還沒有從這個專案借過判準——跨庫比對算出來的會落進收件匣。",
  article: "還沒有從這個專案生出應用。",
}

export function ProjectItems({ kind, items, name }: {
  kind: KnowledgeKind; items: KnowledgeItem[]; name: string
}) {
  const mine = items.filter((i) => i.kind === kind)
  if (mine.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p className="max-w-sm text-sm text-muted-foreground">{EMPTY[kind]}</p>
      </div>
    )
  }
  return (
    <div className="mx-auto max-w-3xl space-y-1 px-4 py-5 md:px-8">
      <p className="pb-2 text-xs text-muted-foreground">📁 {name}：{mine.length} 件</p>
      {mine.map((i) => (
        <Link key={`${i.kind}:${i.ref}`} to={TO[kind]?.(i.ref) ?? "/"}
              className="block truncate rounded-lg px-3 py-1.5 text-sm hover:bg-muted">
          {i.label}
        </Link>
      ))}
    </div>
  )
}

/** 這個專案底下的子領域。⚠️ 一個專案 ＝ 一個領域，所以多半只有它自己。 */
export function ProjectDomains({ children, name }: {
  children: { id: number; name: string; count: number }[]; name: string
}) {
  if (children.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p className="max-w-sm text-sm text-muted-foreground">
          📁 {name} 底下還沒有分出子領域——它整個就是一個領域。
        </p>
      </div>
    )
  }
  return (
    <div className="mx-auto max-w-3xl space-y-1 px-4 py-5 md:px-8">
      {children.map((c) => (
        <div key={c.id} className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm">
          <span className="min-w-0 flex-1 truncate">🗂 {c.name}</span>
          <span className="shrink-0 text-xs text-muted-foreground">{c.count}</span>
        </div>
      ))}
    </div>
  )
}
