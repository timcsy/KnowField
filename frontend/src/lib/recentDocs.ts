// 最近開過的專案檔（開發模式）＝**時間軸**，跟側欄上半的「位置」是兩個軸。
// ⚠️ 跟 `recent.ts` 同一條理由：存 localStorage，是**每個瀏覽器自己的便利**，
//    不是知識庫的資料——不進 DB、不跨裝置同步。
// ⚠️ 每一次讀寫都包 try/catch：無痕視窗／封鎖站台資料時 accessor 本身會丟。
const KEY = "kf.recentDocs"
const CAP = 8

export type RecentDoc = { base: number; path: string; at: number }

export function readRecentDocs(): RecentDoc[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const v = JSON.parse(raw)
    return Array.isArray(v)
      ? v.filter((x) => typeof x?.base === "number" && typeof x?.path === "string")
      : []
  } catch { return [] }
}

/** 記一次開檔：**去重**（同一份只留一筆，更新時間），新的在前。 */
export function touchRecentDoc(base: number, path: string): RecentDoc[] {
  if (!base || !path) return readRecentDocs()
  const next = [{ base, path, at: Date.now() },
                ...readRecentDocs().filter((r) => !(r.base === base && r.path === path))].slice(0, CAP)
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* 存不了就算了 */ }
  return next
}
