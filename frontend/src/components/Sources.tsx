import { type Source } from "@/lib/api"
import { Badge } from "@/components/ui/badge"

// 被回答 [n] 引用的來源——列在底下，錨點對上（原則 3：溯源靠結構）。
// spec 080：專案落成的來源長這樣（`github://owner/repo/path`）。
// ⚠️ 它**不是「你收藏的」**——標錯就是把別人的東西掛上你的名字。
// ⚠️ 而 `github://` 瀏覽器打不開 ⇒ 連到站內的來源詳情頁（那裡讀得到被引用的原文）。
const PROJECT = "github://"
export function projectOf(url: string): string {
  if (!url.startsWith(PROJECT)) return ""
  return url.slice(PROJECT.length).split("/").slice(0, 2).join("/")
}
function Cite({ s }: { s: Source }) {
  const repo = projectOf(s.url)
  if (repo) {
    return (
      <>
        <Badge variant="secondary" className="mr-1">📁 {repo}</Badge>
        <a href={`/source?u=${encodeURIComponent(s.url)}`}
           className="break-all text-primary hover:underline">
          {s.title.replace(/^knowledge\//, "")}
        </a>
      </>
    )
  }
  return (
    <>
      {s.kind === "corpus" && <Badge variant="secondary" className="mr-1">📎 你收藏的</Badge>}
      <a href={s.url} target="_blank" rel="noopener"
         className="break-all text-primary hover:underline">{s.title}</a>
    </>
  )
}

export function Sources({ sources, prefix }: { sources: Source[]; prefix: string }) {
  if (!sources.length) return null
  return (
    <div className="mt-2 space-y-0.5 border-t pt-2 text-xs">
      <div className="font-medium text-muted-foreground">來源</div>
      {sources.map((s) => (
        <div key={s.n} id={`${prefix}-${s.n}`} className="scroll-mt-16">
          <span className="text-muted-foreground">[{s.n}]</span>{" "}
          <Cite s={s} />
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
            <Cite s={s} />
          </div>
        ))}
      </div>
    </details>
  )
}
