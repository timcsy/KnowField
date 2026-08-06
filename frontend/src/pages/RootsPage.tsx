import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { pages, type RootsData, type WhyNode } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export default function RootsPage() {
  const [data, setData] = useState<RootsData | null>(null)
  const load = () => pages.roots().then(setData).catch(() => {})
  useEffect(() => { load() }, [])

  async function anoint(w: WhyNode, claim: string) {
    await pages.whynodeAnoint(w.id, claim)
    load()
  }
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
    <div className="space-y-6 pb-8">
      <div>
        <h1 className="text-2xl font-bold">💡 你的核心理解</h1>
        <p className="text-xs text-muted-foreground">
          AI 幫你整理候選、你精選——精選的，聊天時會最優先參考。
        </p>
      </div>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-muted-foreground">AI 幫你整理的（還沒精選）</h2>
        {data.candidates.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            目前沒有候選。到「跟知識聊」聊一段、按「整理成重點」就會出現。
          </p>
        ) : (
          <div className="space-y-3">
            {data.candidates.map((c) => (
              <CandidateCard key={c.id} w={c} onAnoint={anoint} onRemove={remove} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-sm font-semibold text-muted-foreground">你精選的核心理解</h2>
        {data.anointed.length === 0 ? (
          <p className="text-sm text-muted-foreground">還沒有精選的核心理解。精選後，聊天會最優先參考它。</p>
        ) : (
          <div className="space-y-2">
            {data.anointed.map((w) => {
              const src = data.source_provenance[String(w.id)]
              const convo = data.provenance[String(w.id)]
              return (
                <div key={w.id} className="group rounded-xl bg-card px-5 py-4 shadow-sm">
                  <p className="max-w-[42rem] text-[15px] leading-loose">💡 {w.claim}</p>
                  <div className="mt-1.5 flex items-center gap-4 text-xs text-muted-foreground">
                    {src ? (
                      <Link to={`/source?u=${encodeURIComponent(src)}`} className="hover:text-foreground">📎 由來</Link>
                    ) : convo ? (
                      <span>💬 由來</span>
                    ) : null}
                    <span className="flex items-center gap-4 opacity-0 transition group-hover:opacity-100">
                      <button onClick={() => copyRoot(w.id, "md")} className="hover:text-foreground">📋 複製</button>
                      <button onClick={() => copyRoot(w.id, "urls")} className="hover:text-foreground">🔗 來源</button>
                      <button onClick={() => remove(w.id)} className="hover:text-destructive">退回</button>
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}

function CandidateCard({
  w, onAnoint, onRemove,
}: {
  w: WhyNode
  onAnoint: (w: WhyNode, claim: string) => void
  onRemove: (id: number) => void
}) {
  const [claim, setClaim] = useState(w.claim)
  const [done, setDone] = useState(false)
  return (
    <div className="space-y-2 rounded-xl bg-card p-4 shadow-sm">
      <div className="flex items-center gap-2">
        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">候選</span>
        <Input value={claim} onChange={(e) => setClaim(e.target.value)} className="flex-1 font-medium" />
      </div>
      {w.ladder.length > 0 && (
        <ol className="ml-1 space-y-0.5 border-l-2 pl-3 text-xs text-muted-foreground">
          {w.ladder.map((s, i) => (
            <li key={i}>{i === w.ladder.length - 1 ? <b className="text-foreground">↓ 最底層：</b> : "↓ "}{s}</li>
          ))}
        </ol>
      )}
      {done ? (
        <div className="text-sm text-primary">✅ 已精選</div>
      ) : (
        <div className="flex gap-2">
          <Button size="sm" onClick={() => { onAnoint(w, claim); setDone(true) }}>精選</Button>
          <Button size="sm" variant="ghost" onClick={() => onRemove(w.id)}>退回</Button>
        </div>
      )}
    </div>
  )
}
