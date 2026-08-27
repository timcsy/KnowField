import { useEffect, useState } from "react"
import { pages, type DeadRefs, type ExtBase, type GhRepo } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

// spec 072：別的專案的知識庫——場自己去 GitHub 拿回來的。
// ⚠️ 這一頁**不是**你的知識：它是外來的。所以不進側欄那組「當前領域底下的東西」，
//    而且每一塊都要看得出「最後一次抓是什麼時候」——樹一抓下來就開始過期。

function since(iso: string): string {
  if (!iso) return "還沒抓過"
  const d = Math.floor((Date.now() - Date.parse(iso)) / 86400000)
  return d <= 0 ? "今天抓的" : `${d} 天前抓的`
}

const LAYER_LABEL: Record<string, string> = {
  experience: "🧪 經驗", concepts: "🧠 概念", principles: "📖 原則", vision: "📐 路線圖",
  history: "🕰 轉移", episodes: "🎬 場景", draft: "✍️ draft", skills: "🛠 skills", other: "其他",
}

function Dead({ id }: { id: number }) {
  const [d, setD] = useState<DeadRefs | null>(null)
  const [open, setOpen] = useState(false)
  useEffect(() => { if (open && !d) pages.deadRefs(id).then(setD).catch(() => {}) }, [open, d, id])
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(!open)} className="text-xs text-muted-foreground hover:text-foreground hover:underline">
        🔗 來源指標檢查{open ? " ▲" : " ▾"}
      </button>
      {open && (d === null ? <p className="mt-1 text-xs text-muted-foreground">看一下…</p> : (
        <div className="mt-1.5 space-y-1.5 border-t pt-2">
          {/* ⚠️ 一定先講樹多舊、完不完整——否則這份報告會被當成權威 */}
          <p className="text-xs text-muted-foreground">
            依據 {since(d.fetched_at)}的目錄樹（{d.n_paths} 個檔案）
            {d.truncated && <b className="text-destructive"> · 這棵樹被 GitHub 截斷了，下面一定有漏</b>}
          </p>
          {d.dead.length === 0 ? (
            <p className="text-xs text-muted-foreground">每個指到的路徑都還在。</p>
          ) : (
            <ul className="space-y-1">
              {d.dead.map((x, i) => (
                <li key={i} className="text-xs">
                  <span className="text-muted-foreground">{x.file}</span>
                  <span className="mx-1.5">→</span>
                  <code className="rounded bg-muted px-1 text-destructive">{x.ref}</code>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

export default function BasesPage() {
  const [data, setData] = useState<{ bases: ExtBase[]; enabled: boolean } | null>(null)
  const [repos, setRepos] = useState<GhRepo[] | null>(null)
  const [url, setUrl] = useState("")
  const [msg, setMsg] = useState<string | null>(null)
  const load = () => pages.bases().then(setData).catch(() => {})
  useEffect(() => { load() }, [])
  useEffect(() => { pages.ghRepos().then((r) => setRepos(r.repos)).catch(() => setRepos([])) }, [])
  // 抓取在背景跑（實測 17 秒／個）⇒ 有在抓的時候輪詢
  useEffect(() => {
    if (!data?.bases.some((b) => b.status === "pending" || b.status === "fetching")) return
    const t = setTimeout(load, 2000)
    return () => clearTimeout(t)
  }, [data])

  async function add(repo: string) {
    setMsg(null)
    const r = await pages.baseAdd(repo)
    if (r.error) { setMsg(r.error); return }
    setUrl(""); load()
  }

  if (!data) return <p className="text-sm text-muted-foreground">載入中…</p>
  const have = new Set(data.bases.map((b) => b.repo))
  return (
    <div className="space-y-5 pb-8">
      <div>
        <h1 className="text-2xl font-bold">🌍 別的知識庫</h1>
        <p className="text-xs text-muted-foreground">
          你其他專案的 knowledge/——場自己去 GitHub 拿。只拿知識，其餘只拿目錄結構、不拿內容。
        </p>
      </div>

      {!data.enabled ? (
        <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">
          還沒設定 GitHub App。設定好之後這裡就能貼 repo 進來。
        </p>
      ) : (
        <section className="space-y-2 rounded-xl border bg-card p-4">
          <div className="flex flex-wrap gap-2">
            <Input value={url} onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.nativeEvent.isComposing) add(url) }}
              placeholder="貼一個 GitHub 網址，或 owner/name" className="min-w-56 flex-1" />
            <Button disabled={!url.trim()} onClick={() => add(url)}>加進來</Button>
          </div>
          {msg && <p className="text-xs text-destructive">{msg}</p>}
          {repos && repos.length > 0 && (
            <details>
              <summary className="cursor-pointer text-xs text-muted-foreground hover:text-foreground">
                或從清單挑（{repos.length} 個授權過的 repo）
              </summary>
              <div className="mt-2 flex max-h-56 flex-wrap gap-1.5 overflow-y-auto">
                {repos.filter((r) => !have.has(r.repo)).map((r) => (
                  <button key={r.repo} onClick={() => add(r.repo)}
                    className="rounded border px-2 py-0.5 text-xs hover:bg-muted">
                    {r.private && "🔒 "}{r.repo}
                  </button>
                ))}
              </div>
            </details>
          )}
        </section>
      )}

      {data.bases.length === 0 ? (
        <p className="text-sm text-muted-foreground">還沒有。加一個進來，它會把那個專案的 knowledge/ 抓過來。</p>
      ) : (
        <div className="space-y-2">
          {data.bases.map((b) => (
            <div key={b.id} className="rounded-xl bg-card px-5 py-4 shadow-sm">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 className="text-[15px] font-semibold">
                  {b.private ? "🔒 " : ""}{b.repo}
                  {b.branch && <span className="ml-2 text-xs font-normal text-muted-foreground">{b.branch}</span>}
                </h2>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{since(b.fetched_at)}</span>
                  <button onClick={() => pages.baseRefresh(b.id).then(load)} className="hover:text-foreground">重新抓</button>
                </div>
              </div>
              {b.status === "error" ? (
                <p className="mt-1 text-xs text-destructive">抓不到：{b.error}</p>
              ) : b.status !== "ok" ? (
                <p className="mt-1 text-xs text-muted-foreground">抓取中…（一個專案大約 20 秒）</p>
              ) : (
                <>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                    {Object.entries(b.layers).sort((a, c) => c[1] - a[1]).map(([k, n]) => (
                      <span key={k}>{LAYER_LABEL[k] || k} {n}</span>
                    ))}
                    <span>· 目錄樹 {b.n_paths} 個檔案</span>
                    {/* ⚠️ 截斷了要說：不說的話，下面的檢查會靜默漏報 */}
                    {b.tree_truncated === 1 && <b className="text-destructive">· 樹被截斷</b>}
                  </div>
                  <Dead id={b.id} />
                </>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
