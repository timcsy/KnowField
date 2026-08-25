import { useCallback } from "react"
import { useLocation, useNavigate, useSearchParams } from "react-router-dom"

// 當前領域（spec 052）＝**你站在哪**。
// ⚠️ 它住在 **URL**（`?d=<id>`），不是元件狀態——這樣瀏覽器上一頁與手機返回手勢
// 直接就能用（這是 PWA，那個手勢是最順的動作），而不必自己做一份歷史。
// ⚠️ `d` 缺席／`0` ＝ **根領域**（＝整個知識庫），不是「沒有領域」。
export const ROOT_NAME = "知識庫"

export function useCurrentDomain() {
  const [sp] = useSearchParams()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const raw = sp.get("d")
  const did = raw && Number(raw) > 0 ? Number(raw) : null

  const go = useCallback((to: number | null, opts?: { replace?: boolean }) => {
    const next = new URLSearchParams(sp)
    if (to === null) next.delete("d")
    else next.set("d", String(to))
    // push（不是 replace）⇒ 返回鍵回得去上一個領域
    navigate({ pathname, search: next.toString() }, { replace: !!opts?.replace })
  }, [sp, navigate, pathname])

  return { did, go }
}

/** 把當前領域帶到另一條路徑上——換頁 MUST NOT 讓你掉出你站的地方。 */
export function withDomain(path: string, did: number | null): string {
  if (did === null) return path
  return path + (path.includes("?") ? "&" : "?") + "d=" + did
}
