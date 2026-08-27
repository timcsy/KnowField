import { type ReactNode } from "react"
import { Markdown } from "@/components/Markdown"
import { Sources, FoundExtra } from "@/components/Sources"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { type Message } from "@/lib/api"
import { cn } from "@/lib/utils"

// spec 078：聊天的**形狀**——兩個場共用同一份。
// ⚠️ 這個檔案存在的理由是 `history/112` 那條：「**兩套介面是我自己造的**」。
//    開發模式要「跟互動那邊幾乎一樣」，而做第二套的話，兩邊會從第一天開始漂。
//    ⇒ 把會漂的東西（訊息的樣子、輸入框的樣子）收成一份，各自的專屬功能留在各自那邊。

/** 你說的那句：右對齊、圓角泡泡。`extra` 給各自的專屬動作（例如編輯重問）。 */
export function UserBubble({ content, marked, extra }: {
  content: string; marked?: boolean; extra?: ReactNode
}) {
  return (
    <div className="group flex flex-col items-end gap-0.5">
      <div className={cn("max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-muted px-4 py-2",
                         marked && "border-l-2 border-primary/40")}>{content}</div>
      {extra}
    </div>
  )
}

/** AI 回覆：**全寬無框**的文字流（不裝卡片）——用留白與對齊區分你我，不用框。 */
export function AssistantFlow({ m, prefix, marked, extra }: {
  m: Message; prefix: string; marked?: boolean; extra?: ReactNode
}) {
  return (
    <div className={cn("group", marked && "border-l-2 border-primary/40 pl-3")}>
      <Markdown text={m.content} prefix={prefix} />
      {/* ⚠️ 不完整就明說是哪一種——靜默半句看起來像講完了（憲章 V） */}
      {m.truncated && (
        <div className="mt-2 text-xs text-amber-600 dark:text-amber-500">
          {m.truncated === "length"
            ? "⚠ 這則回答到長度上限被截斷了（沒講完）。可以請它「接著上面繼續」。"
            : "⚠ 這則回答中途斷線，只收到一半。可以重新生成。"}
        </div>
      )}
      <Sources sources={m.sources || []} prefix={prefix} />
      <FoundExtra extra={m.found_extra || []} />
      {extra}
    </div>
  )
}

/** 輸入框：圓角、灰底、Enter 送出（⚠️ 組字中的 Enter 是選字，不是送出）。 */
export function Composer({ value, onChange, onSend, busy, placeholder, extra }: {
  value: string; onChange: (v: string) => void; onSend: () => void
  busy?: boolean; placeholder?: string; extra?: ReactNode
}) {
  return (
    <div className="shrink-0 pt-2">
      <div className="flex items-end gap-2 rounded-2xl bg-muted px-3 py-2 focus-within:ring-1 focus-within:ring-ring">
        <Textarea
          rows={1} value={value} onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            // 輸入法組字中的 Enter＝選字確認，不是送出（isComposing / keyCode 229）
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
              e.preventDefault(); onSend()
            }
          }}
          placeholder={placeholder}
          className="max-h-40 min-h-0 resize-none border-0 bg-transparent p-1 shadow-none focus-visible:ring-0" />
        <Button size="icon" className="shrink-0 rounded-full" disabled={busy} onClick={onSend}
                aria-label="送出">↑</Button>
      </div>
      {extra}
    </div>
  )
}

/** 串流中的那一則：⚠️ 跟完成的回覆**同一條呈現路徑**，否則寫完的瞬間畫面會跳。 */
export function Streaming({ text, stage }: { text: string | null; stage: string | null }) {
  if (text === null) return null
  return (
    <div className="group">
      {text ? <Markdown text={text} prefix="stream" />
            : <div className="text-[15px] text-muted-foreground">{stage || "…"}</div>}
    </div>
  )
}
