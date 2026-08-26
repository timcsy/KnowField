// 「這是點選，還是滑動？」（spec 059）
//
// ⚠️ 觸控上，捲動與點選**開頭一模一樣**：都是 pointerdown。
// 瀏覽器多數時候會在捲動後抑制 click，但**不是每次**——慢速小幅的滑動仍會送出 click，
// 於是使用者只是想捲清單，卻被當成點開一列。
//
// ⇒ 判準：**點選是「按下與放開幾乎在同一個位置」**，不是「有沒有收到 click」。
export const TAP_SLOP = 10   // px；比長按的 8 稍寬——捲動的手指本來就會滑得比按住多

/** 從按下到現在，移動得夠遠就不算點選。 */
export function isTap(start: { x: number; y: number } | null,
                      end: { x: number; y: number }, slop = TAP_SLOP): boolean {
  if (!start) return true          // 沒記到起點（例如鍵盤觸發）→ 當成點選，不要吃掉它
  return Math.hypot(end.x - start.x, end.y - start.y) <= slop
}
