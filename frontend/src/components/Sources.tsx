import { type Source } from "@/lib/api"
import { Badge } from "@/components/ui/badge"

// 被回答 [n] 引用的來源——列在底下，錨點對上（原則 3：溯源靠結構）。
export function Sources({ sources, prefix }: { sources: Source[]; prefix: string }) {
  if (!sources.length) return null
  return (
    <div className="mt-2 space-y-0.5 border-t pt-2 text-xs">
      <div className="font-medium text-muted-foreground">來源</div>
      {sources.map((s) => (
        <div key={s.n} id={`${prefix}-${s.n}`} className="scroll-mt-16">
          <span className="text-muted-foreground">[{s.n}]</span>{" "}
          {s.kind === "corpus" && <Badge variant="secondary" className="mr-1">📎 你收藏的</Badge>}
          <a href={s.url} target="_blank" rel="noopener"
             className="break-all text-primary hover:underline">{s.title}</a>
        </div>
      ))}
    </div>
  )
}

// 撒到、但回答沒直接引用（[n]）的來源——折疊在底下，不當佐證但可查。
export function FoundExtra({ extra }: { extra: Source[] }) {
  if (!extra.length) return null
  return (
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer text-muted-foreground hover:text-foreground">
        也找到（未直接引用，{extra.length}）
      </summary>
      <div className="mt-1 space-y-0.5 pl-1">
        {extra.map((s) => (
          <div key={s.n}>
            {s.kind === "corpus" && <Badge variant="secondary" className="mr-1">📎 你收藏的</Badge>}
            <a href={s.url} target="_blank" rel="noopener"
               className="break-all text-primary hover:underline">{s.title}</a>
          </div>
        ))}
      </div>
    </details>
  )
}
