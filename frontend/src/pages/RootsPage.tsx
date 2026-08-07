import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages, type RootsData } from "@/lib/api"
import { KindBadge } from "@/components/KindBadge"

// 原文＝唯一真相：由來連結帶 Text Fragment（#:~:text=）→ 瀏覽器原生捲到並高亮原文那段。
// best-effort：匹配失敗（抽取清理過/SPA 渲染）→ 只開頁面、不跳段（無害）。
function withTextFragment(url: string, quote: string): string {
  if (!quote || !/^https?:\/\//.test(url) || url.includes("#")) return url
  return `${url}#:~:text=${encodeURIComponent(quote.trim())}`
}

export default function RootsPage() {
  const [data, setData] = useState<RootsData | null>(null)
  const [openSrc, setOpenSrc] = useState<number | null>(null)   // 展開哪條的佐證網址
  const load = () => pages.roots().then(setData).catch(() => {})
  useEffect(() => { load() }, [])

  async function remove(id: number) {
    if (!confirm("移除這條核心理解？（聊天將不再優先參考它）")) return
    await pages.whynodeRemove(id)
    load()
  }
  async function copyRoot(id: number, as: "md" | "urls") {
    const t = await (await fetch(`/roots/${id}/export?as=${as}`)).text()
    if (t.trim()) { try { await navigator.clipboard.writeText(t) } catch { /* 無剪貼簿權限 */ } }
  }

  if (!data) return <p className="text-sm text-muted-foreground">載入中…</p>
  return (
    <div className="space-y-5 pb-8">
      <div>
        <h1 className="text-2xl font-bold">💡 你的核心理解</h1>
        <p className="text-xs text-muted-foreground">
          你精選收進的——聊天時最優先參考。（在「跟知識聊」按「🧵 整理成重點」，或「來源」按「🧠 整理成核心理解」時精選。）
        </p>
      </div>

      {data.anointed.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          還沒有精選的核心理解。到聊天「🧵 整理成重點」、或「來源」開一份資料按「🧠 整理成核心理解」，挑認同的收進。
        </p>
      ) : (
        <div className="space-y-2">
          {data.anointed.map((w) => {
            const src = data.source_provenance[String(w.id)]
            const convo = data.provenance[String(w.id)]
            // 佐證只列可點的外部連結；內部來源識別碼（paste:/收進來源）由「📎 由來」指向，不重複、不無效
            const evidence = w.evidence_urls.filter((u) => /^https?:\/\//.test(u))
            return (
              <div key={w.id} className="group rounded-xl bg-card px-5 py-4 shadow-sm">
                <p className="max-w-[42rem] text-[15px] leading-loose"><KindBadge kind={w.kind} /> 💡 {w.claim}</p>
                <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  {src ? (
                    <>
                      {/^https?:\/\//.test(src) && (
                        <a href={withTextFragment(src, w.source_quote)} target="_blank" rel="noopener"
                           title="看原文（唯一真相）——跳到它來自的那段並高亮" className="hover:text-foreground hover:underline">🌐 看原文</a>
                      )}
                      <Link to={`/source?u=${encodeURIComponent(src)}`} title="萃取的參考（供檢索、也能看）；準確請看原文" className="hover:text-foreground hover:underline">📎 萃取參考</Link>
                    </>
                  ) : convo ? (
                    <Link to={`/conversations/${convo}${w.src_from ? `?from=${w.src_from}&to=${w.src_to}` : ""}`}
                          title="這條的出處：點開展開它來自的那段對話" className="hover:text-foreground hover:underline">💬 由來</Link>
                  ) : null}
                  {evidence.length > 0 && (
                    <button onClick={() => setOpenSrc(openSrc === w.id ? null : w.id)}
                            title="這條的外部佐證網址（AI 引用的來源）——點開看" className="hover:text-foreground hover:underline">
                      🔗 佐證（{evidence.length}）{openSrc === w.id ? " ▲" : " ▾"}
                    </button>
                  )}
                  <span className="flex items-center gap-4 opacity-0 transition group-hover:opacity-100">
                    <button onClick={() => copyRoot(w.id, "md")} title="複製這條重點（Markdown）" className="hover:text-foreground">📋 複製</button>
                    <button onClick={() => remove(w.id)} title="退回（聊天不再優先參考它）" className="hover:text-destructive">退回</button>
                  </span>
                </div>
                {openSrc === w.id && evidence.length > 0 && (
                  <ul className="mt-2 space-y-1 border-t pt-2">
                    {evidence.map((u, i) => (
                      <li key={i} className="text-xs">
                        <a href={withTextFragment(u, w.source_quote)} target="_blank" rel="noopener" className="break-all text-primary hover:underline">🔗 {u}</a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
