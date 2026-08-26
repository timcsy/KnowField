// 長按（spec 058）：觸控上的「右鍵」。
//
// ⚠️ **長按與拖曳共用 `pointerdown`**，所以必須互相排除：
//    移動超過門檻 → 那是拖曳，取消長按；長按已觸發 → 那不是拖曳。
//    沒有這條互斥，使用者想拖的時候會跳出選單，想開選單的時候手一抖就變成拖。
//
// ⚠️ 也不要用 `setTimeout` 之外的花招（如 `contextmenu` 事件）——
//    iOS Safari 的 `contextmenu` 行為跟桌機不一致，而不一致的地方不會報錯。
export const LONG_PRESS_MS = 450
export const MOVE_TOLERANCE = 8

export type LongPressHandle = { cancel: () => void; movedFar: (x: number, y: number) => boolean }

/** 在 pointerdown 時呼叫；回一個把手，讓拖曳邏輯可以取消它。 */
export function armLongPress(
  x: number, y: number, fire: () => void,
  opts: { ms?: number; tolerance?: number } = {},
): LongPressHandle {
  const ms = opts.ms ?? LONG_PRESS_MS
  const tol = opts.tolerance ?? MOVE_TOLERANCE
  let timer: number | null = window.setTimeout(() => { timer = null; fire() }, ms)
  const cancel = () => { if (timer !== null) { clearTimeout(timer); timer = null } }
  return {
    cancel,
    movedFar: (nx: number, ny: number) => {
      const far = Math.hypot(nx - x, ny - y) > tol
      if (far) cancel()
      return far
    },
  }
}
