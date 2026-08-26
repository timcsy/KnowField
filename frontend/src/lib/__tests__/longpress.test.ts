import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { armLongPress, LONG_PRESS_MS, MOVE_TOLERANCE } from "../longpress"

beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())

describe("長按＝觸控上的右鍵（spec 058）", () => {
  it("按住夠久就觸發", () => {
    const fire = vi.fn()
    armLongPress(0, 0, fire)
    vi.advanceTimersByTime(LONG_PRESS_MS + 1)
    expect(fire).toHaveBeenCalledOnce()
  })

  it("放太早不觸發", () => {
    const fire = vi.fn()
    const h = armLongPress(0, 0, fire)
    vi.advanceTimersByTime(LONG_PRESS_MS - 50)
    h.cancel()
    vi.advanceTimersByTime(200)
    expect(fire).not.toHaveBeenCalled()
  })

  it("⚠️ 手指移動超過門檻＝那是拖曳，長按 MUST NOT 觸發", () => {
    const fire = vi.fn()
    const h = armLongPress(0, 0, fire)
    expect(h.movedFar(MOVE_TOLERANCE + 1, 0)).toBe(true)
    vi.advanceTimersByTime(LONG_PRESS_MS + 1)
    expect(fire).not.toHaveBeenCalled()
  })

  it("小幅抖動不算移動——手指按著本來就會抖", () => {
    const fire = vi.fn()
    const h = armLongPress(0, 0, fire)
    expect(h.movedFar(MOVE_TOLERANCE - 1, 0)).toBe(false)
    vi.advanceTimersByTime(LONG_PRESS_MS + 1)
    expect(fire).toHaveBeenCalledOnce()
  })

  it("取消兩次不會炸", () => {
    const h = armLongPress(0, 0, vi.fn())
    h.cancel(); h.cancel()
  })
})
