import { useEffect, useState } from "react"
import { Link, useParams } from "react-router-dom"
import { pages } from "@/lib/api"
import { Markdown } from "@/components/Markdown"

// 文章詳情＝獨立閱讀頁（對齊來源頁 /source）：頂部「← 文章」上一頁、右上「✍️ 生成新的」。
// 文章＝輸出物、唯讀（原則 6）。
export default function ArticleViewPage() {
  const { id } = useParams()
  const [art, setArt] = useState<{ id: number; title: string; markdown: string } | null | "missing">(null)
  const [msg, setMsg] = useState<string | null>(null)
  useEffect(() => {
    pages.getArticle(Number(id))
      .then((a) => setArt(a && a.markdown ? a : "missing"))
      .catch(() => setArt("missing"))
  }, [id])

  async function copy() {
    if (art && art !== "missing") { try { await navigator.clipboard.writeText(art.markdown); setMsg("已複製") } catch { /* 無剪貼簿 */ } }
  }

  return (
    <div className="space-y-4 pb-8">
      <div className="flex items-center gap-3">
        <Link to="/articles" className="text-sm text-muted-foreground hover:underline">← 應用</Link>
        <div className="ml-auto flex items-center gap-3 text-sm text-muted-foreground">
          {art && art !== "missing" && (
            <button onClick={copy} className="hover:text-foreground">📋 複製 Markdown</button>
          )}
          {/* spec 041：讀完想接著想 → 帶著這篇開一輪對話（人明確按，非自動注入） */}
          {art && art !== "missing" && (
            <Link to={`/?article=${art.id}&atitle=${encodeURIComponent(art.title || "應用")}`}
                  className="rounded-md border px-3 py-1.5 font-medium hover:bg-accent"
                  title="讀完有想法？帶著這篇接著想——它會進這輪的脈絡，但不會蓋過你的理解">
              💬 帶著這篇聊
            </Link>
          )}
          <Link to="/roots" className="rounded-md bg-primary px-3 py-1.5 font-medium text-primary-foreground hover:opacity-90">
            ✍️ 生成新的
          </Link>
        </div>
      </div>
      {msg && <div className="text-xs text-muted-foreground">{msg}</div>}

      {art === null ? (
        <p className="text-sm text-muted-foreground">載入中…</p>
      ) : art === "missing" ? (
        <p className="text-sm text-muted-foreground">找不到這份應用。<Link to="/articles" className="text-primary hover:underline">← 回應用</Link></p>
      ) : (
        // 文章正文＝閱讀內容→全寬無框（像讀文章，不裝卡片）
        <article>
          <Markdown text={art.markdown} prefix="artv" />
        </article>
      )}
    </div>
  )
}
