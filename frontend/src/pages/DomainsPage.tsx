import { useEffect, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { pages, type KnowledgeItem, type KnowledgeKind, type KnowledgeRef } from "@/lib/api"
import { keyOf, pickedRefs as pickRefs, inDomain as inDom, KIND_ORDER } from "@/lib/knowledge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"

// 整理台（spec 050，階段 45）＝領域樹 ＋ 待整理清冊。
// ⚠️ **領域＝節點、主題 Topic＝從根到節點的路徑**——路徑由後端從 parent_id 導出，這裡只顯示。
// ⚠️ 未歸屬＝沒有值，**不是樹上的一個節點**——所以它另外列，不混進樹裡（但它是合法的放置目標）。
// ⚠️ 階段 44 只做了「已歸屬的對話能搬」，而正式庫那樣的東西是 0 件
//    ——整理的**起點動作**（把未歸屬的搬進去）當時在介面上不存在。這一頁就是補那個。
type Domain = { id: number; name: string; parent_id: number | null; path: { id: number; name: string }[] }

const KIND_LABEL: Record<KnowledgeKind, string> = {
  source: "📚 來源", conversation: "💬 對話", why_node: "💡 核心理解", article: "📝 文章",
}

export default function DomainsPage() {
  const nav = useNavigate()
  const [domains, setDomains] = useState<Domain[] | null>(null)
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [sel, setSel] = useState<number | null>(null)
  const [name, setName] = useState("")
  const [msg, setMsg] = useState<string | null>(null)
  const [picked, setPicked] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState<KnowledgeKind | "all">("all")
  const [dropOn, setDropOn] = useState<number | null | "none">("none")
  // 搬東西時若有糾纏，先問。⚠️ 糾纏不是我們建的，是**既有連結被樹拆散**。
  const [ask, setAsk] = useState<{ items: KnowledgeRef[]; to: number | null
                                   tangles: { label: string }[] } | null>(null)

  const load = () => Promise.all([pages.domains(), pages.inventory()])
    .then(([d, inv]) => { setDomains(d.domains); setItems(inv.items) })
    .catch(() => setDomains([]))
  useEffect(() => { load() }, [])

  async function create() {
    if (!name.trim()) return
    const r = await pages.createDomain(name.trim(), sel)
    if (!r.ok) { setMsg(r.err || "建不起來"); return }
    setName(""); setMsg(null); load()
  }
  async function moveDomain(id: number, parent: number | null) {
    const r = await pages.moveDomain(id, parent)
    setMsg(r.ok ? null : (r.err || "搬不動"))   // 成環會被後端擋下並回原因（不靜默照做）
    load()
  }

  // ── 搬動：一律走批次（單件＝一個元素的清單，不留第二條路）─────────────
  async function startMove(refs: KnowledgeRef[], to: number | null) {
    if (refs.length === 0) return
    const r = await pages.tangles(refs, to)
    if (r.tangles.length === 0) { await doMove(refs, to, false); return }   // 沒糾纏就直接搬
    setAsk({ items: refs, to, tangles: r.tangles })
  }
  async function doMove(refs: KnowledgeRef[], to: number | null, bring: boolean) {
    const r = await pages.moveKnowledge(refs, to, bring)
    setAsk(null); setPicked(new Set())
    setMsg(r.tangles && !bring
      ? `搬好 ${r.moved} 件——留下 ${r.tangles} 條糾纏`
      : `搬好 ${r.moved} 件`)
    load()
  }

  const kids = (p: number | null) => (domains || []).filter((d) => d.parent_id === p)
  const inDomain = (id: number | null) => inDom(items, id)
  const unfiled = useMemo(() => inDomain(null), [items])

  const pickedRefs = (): KnowledgeRef[] => pickRefs(items, picked)

  function toggle(i: KnowledgeItem) {
    const k = keyOf(i)
    setPicked((p) => { const n = new Set(p); n.has(k) ? n.delete(k) : n.add(k); return n })
  }

  // ── 拖放（Pointer Events，不是 HTML5 DnD）────────────────────────────
  // ⚠️ **HTML5 drag-and-drop 在觸控裝置上根本不會觸發**，而這是個 PWA
  //    ——用 draggable/onDrop 的話手機上會安靜地不能拖，什麼錯都不報。
  //    Pointer Events 滑鼠與觸控同一條路，而且合成事件驅得動 ⇒ 驗得到。
  // 拖的是**目前選取的那批**；拖一個沒被選取的，就當成只拖它自己。
  function beginDrag(e: React.PointerEvent, i: KnowledgeItem) {
    if (e.button !== 0 && e.pointerType === "mouse") return
    const key = keyOf(i)
    const batch = picked.has(key) ? picked : new Set([key])
    if (batch !== picked) setPicked(batch)
    const start = { x: e.clientX, y: e.clientY }
    let armed = false

    const targetAt = (x: number, y: number): { to: number | null } | null => {
      const el = document.elementFromPoint(x, y)?.closest("[data-drop]") as HTMLElement | null
      if (!el) return null
      const v = el.dataset.drop!
      return { to: v === "unfiled" ? null : Number(v) }
    }
    const onMove = (ev: PointerEvent) => {
      if (!armed && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) < 6) return
      armed = true                       // 門檻：小於 6px 當成點擊，不當拖曳
      const t = targetAt(ev.clientX, ev.clientY)
      const next = t ? t.to : "none"
      // ⚠️ 只在**真的變了**才 setState——pointermove 一秒幾十次，
      // 每次都 setState 等於把整份清冊重畫幾十次。
      setDropOn((d) => (d === next ? d : next))
    }
    const onUp = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
      setDropOn("none")
      if (!armed) return                 // 只是點一下，不是拖
      const t = targetAt(ev.clientX, ev.clientY)
      if (!t) return
      const refs = items.filter((x) => batch.has(keyOf(x))).map((x) => ({ kind: x.kind, ref: x.ref }))
      if (refs.length) startMove(refs, t.to)
    }
    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
  }
  const dropProps = (to: number | null) => ({ "data-drop": to === null ? "unfiled" : String(to) })

  // ⚠️ 這兩個是**函式**不是元件：定義在元件內部的 JSX 元件每次 render 都是新型別，
  // React 會把整棵子樹卸載重掛——拖曳時一秒幾十次 render，105 列就這樣卡死頁面。
  const renderRow = (i: KnowledgeItem) => (
    <label key={keyOf(i)} onPointerDown={(e) => beginDrag(e, i)}
           className="flex cursor-grab select-none items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted">
      <input type="checkbox" checked={picked.has(keyOf(i))} onChange={() => toggle(i)} />
      <span className="shrink-0 text-xs text-muted-foreground">{KIND_LABEL[i.kind].slice(0, 2)}</span>
      <span className="min-w-0 flex-1 truncate">{i.label}</span>
      {i.kind === "conversation" && (
        <button onClick={(e) => { e.preventDefault(); nav(`/?resume=${i.ref}`) }}
                className="shrink-0 text-xs text-muted-foreground hover:underline">開啟</button>
      )}
    </label>
  )

  const renderNode = (d: Domain, depth: number) => (
    <div key={d.id}>
      <div className={cn("flex items-center gap-2 rounded px-2 py-1 hover:bg-muted",
                         sel === d.id && "bg-muted",
                         dropOn === d.id && "outline outline-2 outline-primary")}
           style={{ paddingLeft: 8 + depth * 16 }} {...dropProps(d.id)}>
        <button onClick={() => setSel(sel === d.id ? null : d.id)} className="text-left text-sm">
          📁 {d.name}
        </button>
        <span className="text-xs text-muted-foreground">{inDomain(d.id).length}</span>
        {d.parent_id !== null && (
          <button onClick={() => moveDomain(d.id, null)}
                  className="ml-auto text-xs text-muted-foreground hover:text-foreground">移到最上層</button>
        )}
      </div>
      {kids(d.id).map((k) => renderNode(k, depth + 1))}
    </div>
  )

  const selected = (domains || []).find((d) => d.id === sel)
  const shown = (list: KnowledgeItem[]) => filter === "all" ? list : list.filter((i) => i.kind === filter)
  const byKind = (list: KnowledgeItem[], k: KnowledgeKind) => list.filter((i) => i.kind === k)

  return (
    <div className="space-y-5 pb-8">
      <div>
        <h1 className="text-2xl font-bold">🗂 領域</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          知識庫的樹。勾選右邊的知識，拖到左邊的領域上放開——或按「搬到…」。
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

      {ask && (
        <div className="space-y-3 rounded-xl border border-amber-300 bg-amber-50/40 p-4 dark:bg-amber-950/20">
          <p className="text-sm">
            搬這 <b>{ask.items.length}</b> 件過去，會跟這 {ask.tangles.length} 個分開：
          </p>
          <ul className="ml-4 max-h-40 list-disc overflow-y-auto text-sm text-muted-foreground">
            {ask.tangles.map((t, i) => <li key={i}>{t.label}</li>)}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => doMove(ask.items, ask.to, true)}>連帶一起搬</Button>
            <Button size="sm" variant="secondary" onClick={() => doMove(ask.items, ask.to, false)}>
              留一條糾纏
            </Button>
            <button onClick={() => setAsk(null)} className="text-sm text-muted-foreground hover:underline">
              取消
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            ⚠️ 「連帶」只走<b className="text-foreground">一層</b>——它們自己連著的東西不會跟著搬（知識的連結是網不是樹）。
          </p>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-[minmax(0,280px)_minmax(0,1fr)]">
        {/* ── 左：領域樹（放置目標）────────────────────────────── */}
        <div className="space-y-2">
          {domains === null ? (
            <p className="text-sm text-muted-foreground">載入中…</p>
          ) : domains.length === 0 ? (
            <p className="text-sm text-muted-foreground">還沒有領域。上面打一個名字就能建第一個。</p>
          ) : (
            <div className="rounded-xl border bg-card p-2">{kids(null).map((d) => renderNode(d, 0))}</div>
          )}
          {/* ⚠️ 未歸屬不是樹上的節點，但**是**合法的放置目標（搬回去） */}
          <div className={cn("rounded-xl border border-dashed px-3 py-2 text-sm text-muted-foreground",
                             dropOn === null && "outline outline-2 outline-primary")}
               {...dropProps(null)}>
            未歸屬（{unfiled.length}）
          </div>
        </div>

        {/* ── 右：待整理清冊 ──────────────────────────────────── */}
        <div className="space-y-2 rounded-xl border bg-card p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">
              {selected ? selected.path.map((p) => p.name).join(" / ") : "未歸屬"}
            </span>
            <div className="ml-auto flex flex-wrap items-center gap-1">
              {(["all", ...KIND_ORDER] as const).map((k) => (
                <button key={k} onClick={() => setFilter(k as KnowledgeKind | "all")}
                        className={cn("rounded px-2 py-0.5 text-xs",
                                      filter === k ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted")}>
                  {k === "all" ? "全部" : KIND_LABEL[k as KnowledgeKind]}
                </button>
              ))}
            </div>
          </div>

          {selected && (
            <div className="flex flex-wrap items-center gap-2 border-b pb-2">
              <Button size="sm" variant="secondary" onClick={() => nav(`/?new=1&domain=${selected.id}`)}>
                ＋ 在這裡開新對話
              </Button>
              {kids(selected.id).length > 0 && (
                <span className="text-xs text-muted-foreground">
                  子領域：{kids(selected.id).map((k) => k.name).join("、")}
                </span>
              )}
            </div>
          )}

          {(() => {
            const list = shown(inDomain(sel))
            if (list.length === 0) {
              return <p className="py-4 text-sm text-muted-foreground">
                {sel === null ? "沒有未歸屬的知識了。" : "這個領域底下還沒有這類知識。"}
              </p>
            }
            // 每個領域都有自己的「子領域、來源、對話、核心理解、文章」——分段列
            return KIND_ORDER.filter((k) => byKind(list, k).length > 0).map((k) => (
              <section key={k} className="space-y-0.5">
                <h3 className="px-2 pt-2 text-xs font-semibold text-muted-foreground">
                  {KIND_LABEL[k]}（{byKind(list, k).length}）
                </h3>
                {byKind(list, k).map(renderRow)}
              </section>
            ))
          })()}

          {picked.size > 0 && (
            <div className="sticky bottom-0 flex flex-wrap items-center gap-2 border-t bg-card pt-2">
              <span className="text-sm">已選 <b>{picked.size}</b> 件</span>
              <button onClick={() => setPicked(new Set())}
                      className="text-xs text-muted-foreground hover:underline">清除</button>
              <select value="" className="ml-auto rounded border bg-background px-2 py-1 text-sm"
                      onChange={(e) => { if (e.target.value !== "")
                        startMove(pickedRefs(), e.target.value === "0" ? null : Number(e.target.value)) }}>
                <option value="">搬到…</option>
                <option value="0">未歸屬</option>
                {(domains || []).filter((d) => d.id !== sel).map((d) => (
                  <option key={d.id} value={d.id}>{d.path.map((p) => p.name).join(" / ")}</option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>

      {sel === null && unfiled.length > 0 && (
        <p className="text-xs text-muted-foreground">
          既有的知識都還在未歸屬——⚠️ <b className="text-foreground">刻意不自動分類</b>：猜出來的歸屬會看起來跟真的一樣。
        </p>
      )}
    </div>
  )
}
