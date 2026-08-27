import { useMemo, useState } from "react"
import { cn } from "@/lib/utils"

// spec 074：真正的檔案樹——資料夾可展開，深度不限（`skills/knowie-pull/SKILL.md`）。
// ⚠️ 之前是「層的籤 ＋ 平面清單」：那個形狀說不出**巢狀**，而 knowledge/ 本來就是巢狀的。
// ⚠️ 展開狀態**刻意不進 URL**：它是當下的視線，不是位置。位置是 `?doc=`。
//    （反過來把它塞進網址，分享出去的連結會帶著別人的展開狀態，那不是他要的東西。）

export type Node = {
  name: string
  path: string
  id?: string                 // 有 id ＝ 檔案（spec 080：id ＝ 完整路徑）
  children?: Node[]
  count?: number              // 資料夾底下的檔案數（含子孫）
}

// spec 080：⚠️ **一份檔的身分是它的路徑**，不是列的 id——重抓會重新落列，
// 而網址裡的 `?doc=` 必須在重抓之後還指到同一份（不然分享出去的連結會失效）。
export function buildTree(items: { path: string }[], strip = "knowledge/"): Node[] {
  const root: Node = { name: "", path: "", children: [] }
  for (const it of items) {
    const rel = it.path.startsWith(strip) ? it.path.slice(strip.length) : it.path
    const parts = rel.split("/").filter(Boolean)
    let cur = root
    parts.forEach((part, i) => {
      const leaf = i === parts.length - 1
      cur.children ??= []
      let next = cur.children.find((c) => c.name === part && !!c.children === !leaf)
      if (!next) {
        next = leaf ? { name: part, path: it.path, id: it.path }
                    : { name: part, path: parts.slice(0, i + 1).join("/"), children: [] }
        cur.children.push(next)
      }
      cur = next
    })
  }
  const sort = (n: Node): Node => {
    if (!n.children) return n
    n.children = n.children.map(sort).sort((a, b) => {
      const fa = a.children ? 0 : 1, fb = b.children ? 0 : 1   // 資料夾在前
      return fa !== fb ? fa - fb : a.name.localeCompare(b.name, "zh-Hant")
    })
    n.count = n.children.reduce((s, c) => s + (c.children ? (c.count ?? 0) : 1), 0)
    return n
  }
  return sort(root).children ?? []
}

function ancestorsOf(nodes: Node[], id: string, acc: string[] = []): string[] | null {
  for (const n of nodes) {
    if (n.id === id) return acc
    if (n.children) {
      const hit = ancestorsOf(n.children, id, [...acc, n.path])
      if (hit) return hit
    }
  }
  return null
}

function Row({ n, depth, sel, open, toggle, pick }: {
  n: Node; depth: number; sel: string
  open: Set<string>; toggle: (p: string) => void; pick: (id: string) => void
}) {
  const isDir = !!n.children
  const shown = isDir && open.has(n.path)
  return (
    <>
      <button
        onClick={() => (isDir ? toggle(n.path) : pick(n.id!))}
        title={n.name}
        style={{ paddingLeft: `${depth * 0.75 + 0.4}rem` }}
        className={cn("flex w-full items-center gap-1.5 rounded py-1 pr-2 text-left text-sm hover:bg-muted",
          !isDir && n.id === sel && "bg-muted font-medium")}>
        <span className="w-3 shrink-0 text-xs text-muted-foreground">{isDir ? (shown ? "▾" : "▸") : ""}</span>
        <span className="min-w-0 flex-1 truncate">{isDir ? `${n.name}/` : n.name}</span>
        {isDir && <span className="shrink-0 text-xs text-muted-foreground">{n.count}</span>}
      </button>
      {shown && n.children!.map((c) => (
        <Row key={c.path + (c.children ? "/" : "")} n={c} depth={depth + 1} sel={sel}
             open={open} toggle={toggle} pick={pick} />
      ))}
    </>
  )
}

export function FileTree({ items, sel, onPick, open: openPath = "" }: {
  items: { path: string }[]
  sel: string
  onPick: (id: string) => void
  /** 側欄點了某一層 ⇒ 那個資料夾要打開（`?open=history`）。 */
  open?: string
}) {
  const tree = useMemo(() => buildTree(items), [items])
  // 選到的那份，它的每一層祖先都要是打開的——否則點搜尋結果過來會看不到它在哪
  const forced = useMemo(() => {
    const s = new Set(ancestorsOf(tree, sel) ?? [])
    if (openPath) s.add(openPath)
    return s
  }, [tree, sel, openPath])
  const [manual, setManual] = useState<Set<string>>(new Set())
  const open = useMemo(() => new Set([...forced, ...manual]), [forced, manual])
  const toggle = (p: string) =>
    setManual((s) => {
      const n = new Set(s)
      n.has(p) || forced.has(p) ? n.delete(p) : n.add(p)
      return n
    })
  if (items.length === 0) return <p className="px-2 py-1 text-sm text-muted-foreground">這個專案還沒有知識檔。</p>
  return (
    <div className="space-y-px">
      {tree.map((n) => (
        <Row key={n.path + (n.children ? "/" : "")} n={n} depth={0} sel={sel}
             open={open} toggle={toggle} pick={onPick} />
      ))}
    </div>
  )
}
