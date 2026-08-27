import { useEffect, useState } from "react"
import { Link, useSearchParams } from "react-router-dom"
import { pages, type ExtBase, type ExtFile, type ExtTreeItem } from "@/lib/api"
import { AskProject } from "@/components/AskProject"
import { FileTree } from "@/components/FileTree"
import { ProjectDomains, ProjectItems } from "@/components/ProjectItems"
import { Markdown } from "@/components/Markdown"
import { touchRecentDoc } from "@/lib/recentDocs"
import { cn } from "@/lib/utils"

// spec 074：開發模式的主區＝**檔案樹｜預覽**（側欄是專案，那是 IDE 的最左段）。
// ⚠️ 手機上三欄不可能 ⇒ **master-detail**：沒選檔＝樹滿版，選了＝預覽滿版＋「← 檔案」。
//    而它不需要任何新狀態——「有沒有選檔」本來就在網址裡（`?doc=`）。

export default function DevPage() {
  const [sp, setSp] = useSearchParams()
  const [bases, setBases] = useState<ExtBase[] | null>(null)
  const [items, setItems] = useState<ExtTreeItem[]>([])
  // spec 080：⚠️ **這個專案聊天時要縮到哪個領域**——沒有它就是不縮，而不縮
  //    跟縮了長得一模一樣（都會回答），你不會發現它其實在翻整個場。
  const [did, setDid] = useState(0)
  // ⚠️ 抓下來幾份 vs 樹上幾份——兩個都要知道才分得出「沒有檔」與「還沒落成來源」
  const [snap, setSnap] = useState(0)
  const [busy, setBusy] = useState(false)
  const [doc, setDoc] = useState<ExtFile | null>(null)
  const bid = Number(sp.get("base") || 0)
  const path = sp.get("doc") || ""
  const open = sp.get("open") || ""
  // ⚠️ 五格＝**同一組鏡頭換被照的東西**；預設是「來源」（那才是專案的本體）
  const view = sp.get("view") || "sources"
  const [dv, setDv] = useState<Awaited<ReturnType<typeof pages.domainView>> | null>(null)

  useEffect(() => { pages.bases().then((d) => setBases(d.bases)).catch(() => setBases([])) }, [])
  useEffect(() => {
    if (!bid) { setItems([]); setDid(0); setSnap(0); return }
    pages.baseTree(bid)
      .then((d) => { setItems(d.items || []); setDid(d.domain_id || 0); setSnap(d.n_snapshot || 0) })
      .catch(() => { setItems([]); setDid(0); setSnap(0) })
  }, [bid])
  useEffect(() => {
    if (!bid || !path) { setDoc(null); return }
    setDoc(null); pages.baseFile(bid, path).then(setDoc).catch(() => setDoc(null))
    touchRecentDoc(bid, path)
  }, [bid, path])
  useEffect(() => {
    if (!did) { setDv(null); return }
    pages.domainView(did).then(setDv).catch(() => setDv(null))
  }, [did, view])

  const go = (patch: Record<string, string>) => {
    const s = new URLSearchParams(sp)
    for (const [k, v] of Object.entries(patch)) v ? s.set(k, v) : s.delete(k)
    setSp(s)
  }
  const base = bases?.find((b) => b.id === bid)

  if (bases && bases.length === 0) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center">
        <p className="max-w-sm text-sm text-muted-foreground">
          這裡讀的是你其他專案的知識庫。還沒有任何一個——
          到 <Link to="/dev/bases" className="text-primary hover:underline">⚙ 管理專案</Link> 加一個進來。
        </p>
      </div>
    )
  }
  const name = base?.name || base?.repo || ""
  // ⚠️ 只有「來源」那一格有檔案樹——其餘四格是清單，樹在那裡沒有意義
  //    （硬留一欄空樹會讓人以為是壞掉了）。
  if (view !== "sources") {
    return (
      <div className="h-full min-h-0 overflow-y-auto">
        {!did ? (
          <div className="flex h-full items-center justify-center px-6 text-center">
            <p className="max-w-sm text-sm text-muted-foreground">
              📁 {name} 還沒歸到領域——重新抓取一次就會。
            </p>
          </div>
        ) : view === "domains" ? (
          <ProjectDomains children={dv?.children || []} name={name} />
        ) : (
          <ProjectItems name={name} items={dv?.items || []}
                        kind={view === "conversations" ? "conversation"
                              : view === "roots" ? "why_node" : "article"} />
        )}
      </div>
    )
  }
  return (
    <div className="flex h-full min-h-0">
      {/* ── 檔案樹（手機：選了檔就讓位給預覽）── */}
      <div className={cn("flex min-h-0 w-full flex-col md:w-64 md:border-r lg:w-72",
                         path && "hidden md:flex")}>
        {base && (
          <p className="truncate border-b px-3 py-2 text-sm text-muted-foreground">
            📁 {base.name || base.repo} · {base.branch}
          </p>
        )}
        <div className="min-h-0 flex-1 overflow-y-auto p-1">
          {/* ⚠️ 有快照、樹是空的 ＝ 這個專案還沒落成來源（spec 080 之前抓的）。
              說「還沒有知識檔」是假話——檔在，只是要重抓一次才會變成來源。
              不自動補：幾百筆新來源湧進來源頁，那一下要由人按。 */}
          {items.length === 0 && snap > 0 ? (
            <div className="space-y-2 px-2 py-3 text-sm text-muted-foreground">
              <p>這個專案抓下來了（{snap} 份檔），但還沒落成來源——重抓一次就會。</p>
              <button
                onClick={() => { setBusy(true); pages.baseRefresh(bid).finally(() => setBusy(false)) }}
                disabled={busy}
                className="rounded bg-primary px-2.5 py-1 text-xs text-primary-foreground disabled:opacity-50">
                {busy ? "重新抓取中…" : "重新抓取"}
              </button>
              <p className="text-xs">抓完之後重新整理這一頁。</p>
            </div>
          ) : (
            <FileTree items={items} sel={path} open={open} onPick={(id) => go({ doc: id })} />
          )}
        </div>
      </div>

      {/* ── 預覽：吃掉剩下的整片寬度；⚠️ min-w-0，少了它長行會把樹擠爛 ── */}
      <div className={cn("flex min-w-0 flex-1 flex-col overflow-hidden", !path && "hidden md:flex")}>
        <div className="min-h-0 flex-1 overflow-y-auto">
        {doc ? (
          <>
            <div className="sticky top-0 z-10 flex items-center gap-2 border-b bg-background/95 px-4 py-2 backdrop-blur md:px-6">
              <button onClick={() => go({ doc: "" })}
                      className="-ml-1 shrink-0 rounded px-2 py-1 text-sm text-muted-foreground hover:bg-muted hover:text-foreground md:hidden">
                ← 檔案
              </button>
              {/* ⚠️ 每一份都標它來自哪個 repo——看不出是誰的，就等於冒充你自己的知識 */}
              <p className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
                <span className="rounded bg-muted px-1.5 py-0.5">{doc.repo}</span>
                <span className="mx-2">/</span>{doc.path.replace(/^knowledge\//, "")}
              </p>
            </div>
            <div className="mx-auto max-w-4xl px-4 py-5 md:px-8 md:py-6">
              <Markdown text={doc.body} prefix={`ext${doc.path}`} />
            </div>
          </>
        ) : (
          // ⚠️ 沒選檔案時，右邊就是**這個專案的聊天**——跟互動那邊
          //    **同一條串流、同一份形狀**，只是縮到這個專案的領域（spec 080）。
          bid > 0 ? <AskProject did={did} name={name}
                                 files={items.length} chunks={items.reduce((s, i) => s + i.chunks, 0)} />
                  : <div className="hidden h-full items-center justify-center px-6 text-center md:flex">
                      <p className="max-w-sm text-sm text-muted-foreground">左邊挑一個專案。</p>
                    </div>
        )}
        </div>
      </div>
    </div>
  )
}
