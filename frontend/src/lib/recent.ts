// 最近存取的領域（spec 053）＝**時間軸**，跟側欄那些「位置」是兩個軸。
// ⚠️ 存在 localStorage：這是**每個瀏覽器自己的便利**，不是知識庫的資料
//    ——它不該進 DB，也不該跨裝置同步（換一台機器從零開始是對的行為）。
// ⚠️ 每一次讀寫都包 try/catch：無痕視窗／封鎖站台資料時 accessor 本身會丟。
const KEY = "kf.recentDomains"
const CAP = 8

export type RecentDomain = { id: number; at: number }

export function readRecent(): RecentDomain[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const v = JSON.parse(raw)
    return Array.isArray(v) ? v.filter((x) => typeof x?.id === "number") : []
  } catch { return [] }
}

/** 記一次造訪：**去重**（同一個領域只留一筆，更新時間），新的在前。 */
export function touchRecent(id: number | null): RecentDomain[] {
  if (id === null) return readRecent()      // 根領域一直都在側欄頂端，不必記
  const now = Date.now()
  const next = [{ id, at: now }, ...readRecent().filter((r) => r.id !== id)].slice(0, CAP)
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* 存不了就算了 */ }
  return next
}

/**
 * 過濾掉**已經不存在**的領域。
 * ⚠️ 這一步不能省：列出一個點了會壞的東西，比不列更糟
 * ——使用者會以為是功能壞了，而不是那個領域被刪了。
 */
export function liveRecent(recent: RecentDomain[], existing: Set<number>): RecentDomain[] {
  return recent.filter((r) => existing.has(r.id))
}
