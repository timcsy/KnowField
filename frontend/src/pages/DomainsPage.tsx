import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import { pages, type ConvRow } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

// 領域頁（spec 048，階段 43）：知識庫的樹。
// ⚠️ **領域＝節點、主題 Topic＝從根到節點的路徑**——路徑由後端從 parent_id 導出，這裡只顯示。
// ⚠️ 這一刀只管**對話**的歸屬；核心理解／文章／來源還不掛領域（刻意，spec 048 out of scope）。
// ⚠️ 未歸屬＝沒有值，**不是樹上的一個節點**——所以它另外列，不混進樹裡。
type Domain = { id: number; name: string; parent_id: number | null; path: { id: number; name: string }[] }

export default function DomainsPage() {
  const nav = useNavigate()
  const [domains, setDomains] = useState<Domain[] | null>(null)
  const [convs, setConvs] = useState<ConvRow[]>([])
  const [sel, setSel] = useState<number | null>(null)
  const [name, setName] = useState("")
  const [msg, setMsg] = useState<string | null>(null)

  const load = () => Promise.all([pages.domains(), pages.conversations()])
    .then(([d, c]) => { setDomains(d.domains); setConvs(c.conversations) })
    .catch(() => setDomains([]))
  useEffect(() => { load() }, [])

  async function create() {
    if (!name.trim()) return
    const r = await pages.createDomain(name.trim(), sel)
    if (!r.ok) { setMsg(r.err || "建不起來"); return }
    setName(""); setMsg(null); load()
  }
  async function move(id: number, parent: number | null) {
    const r = await pages.moveDomain(id, parent)
    setMsg(r.ok ? null : (r.err || "搬不動"))   // 成環會被後端擋下並回原因（不靜默照做）
    load()
  }

  const kids = (p: number | null) => (domains || []).filter((d) => d.parent_id === p)
  const inDomain = (id: number | null) => convs.filter((c) => (c.domain_id ?? null) === id)

  const Node = ({ d, depth }: { d: Domain; depth: number }) => (
    <div>
      <div className={cn("flex items-center gap-2 rounded px-2 py-1 hover:bg-muted",
                         sel === d.id && "bg-muted")}
           style={{ paddingLeft: 8 + depth * 16 }}>
        <button onClick={() => setSel(sel === d.id ? null : d.id)} className="text-left text-sm">
          📁 {d.name}
        </button>
        <span className="text-xs text-muted-foreground">{inDomain(d.id).length} 段對話</span>
        {d.parent_id !== null && (
          <button onClick={() => move(d.id, null)}
                  className="ml-auto text-xs text-muted-foreground hover:text-foreground">移到最上層</button>
        )}
      </div>
      {kids(d.id).map((k) => <Node key={k.id} d={k} depth={depth + 1} />)}
    </div>
  )

  const selected = (domains || []).find((d) => d.id === sel)
  const unfiled = inDomain(null)

  return (
    <div className="space-y-5 pb-8">
      <div>
        <h1 className="text-2xl font-bold">🗂 領域</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          知識庫的樹。點一個領域＝選它；在它底下開新對話，那段就屬於它。
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Input value={name} onChange={(e) => setName(e.target.value)}
               onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) create() }}
               placeholder={sel ? "在選取的領域底下新增子領域…" : "新增最上層領域…"}
               className="w-64 max-w-full" />
        <Button size="sm" onClick={create}>＋ 新增</Button>
        {sel && <button onClick={() => setSel(null)} className="text-xs text-muted-foreground hover:underline">取消選取</button>}
      </div>
      {msg && <div className="rounded-md bg-muted px-3 py-2 text-sm">{msg}</div>}

      {domains === null ? (
        <p className="text-sm text-muted-foreground">載入中…</p>
      ) : domains.length === 0 ? (
        <p className="text-sm text-muted-foreground">還沒有領域。上面打一個名字就能建第一個。</p>
      ) : (
        <div className="rounded-xl border bg-card p-2">{kids(null).map((d) => <Node key={d.id} d={d} depth={0} />)}</div>
      )}

      {selected && (
        <section className="space-y-2 rounded-xl border bg-card p-4">
          <div className="flex flex-wrap items-center gap-2">
            {/* 主題 Topic ＝ 路徑。這裡是它唯一該被顯示成一串的地方 */}
            <span className="text-sm font-semibold">
              {selected.path.map((p) => p.name).join(" / ")}
            </span>
            <Button size="sm" className="ml-auto"
                    onClick={() => nav(`/?new=1&domain=${selected.id}`)}>＋ 在這裡開新對話</Button>
          </div>
          {inDomain(selected.id).length === 0 ? (
            <p className="text-sm text-muted-foreground">這個領域還沒有對話。</p>
          ) : inDomain(selected.id).map((c) => (
            <button key={c.id} onClick={() => nav(`/?resume=${c.id}`)}
                    className="block w-full rounded px-2 py-1 text-left text-sm hover:bg-muted">
              💬 {c.title || "未命名"}
              <span className="ml-2 text-xs text-muted-foreground">{c.count} 則</span>
              {c.yield_count > 0 && <span className="ml-2 text-xs text-muted-foreground">💡 {c.yield_count}</span>}
            </button>
          ))}
        </section>
      )}

      {/* ⚠️ 未歸屬另外列——它不是樹上的節點（FR-006） */}
      {unfiled.length > 0 && (
        <section className="space-y-1">
          <h2 className="text-sm font-semibold text-muted-foreground">未歸屬（{unfiled.length}）</h2>
          <p className="text-xs text-muted-foreground">
            既有的對話都還在這裡——⚠️ <b className="text-foreground">刻意不自動分類</b>：猜出來的歸屬會看起來跟真的一樣。
          </p>
        </section>
      )}
    </div>
  )
}
