// 認識論層次（spec 028）。⚠️ 單一來源——來源頁與對話頁共用，別各寫一份。
export const KINDS = ["已證實", "推論", "類比", "猜想"]

// 認識論層次標籤（vision 階段 28）：AI 整理時看對話上下文判可信度，聊天時據此不把類比/猜想當定論。
const ICON: Record<string, string> = {
  已證實: "🔬",
  推論: "🧩",
  類比: "🌉",
  猜想: "💭",
}

export function KindBadge({ kind }: { kind?: string }) {
  if (!kind) return null
  return (
    <span title="這條的確定性層次——AI 整理時依對話上下文判（類比／猜想別當定論）"
          className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
      {(ICON[kind] ? ICON[kind] + " " : "") + kind}
    </span>
  )
}
