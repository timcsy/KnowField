import { useEffect, useState } from "react"
import { pages, type KnowledgeKind } from "@/lib/api"
import { ROOT_NAME, useCurrentDomain } from "@/lib/domain"

// 領域視野的過濾器（spec 052）：清單頁只顯示**你站的地方底下**的東西。
//
// ⚠️ **FR-007 是這支檔案存在的主要理由**：一旦視野被縮過，**必須說出來**，
// 並且永遠附一條回到整個知識庫的路。因為「找不到」和「這裡沒有」長得一模一樣
// ——而這個專案已經被沉默的縮減咬過好幾次。
// ⇒ 所以 `banner` 不是選配的裝飾：`inScope` 只要可能過濾掉東西，就一定要把它畫出來。
export function useScope(kind: KnowledgeKind) {
  const { did, go } = useCurrentDomain()
  const [refs, setRefs] = useState<Set<string> | null>(null)

  useEffect(() => {
    if (did === null) { setRefs(null); return }        // 站在根＝看到全部，不過濾
    let alive = true
    pages.domainView(did)
      .then((v) => { if (alive) setRefs(new Set(v.items.filter((i) => i.kind === kind).map((i) => String(i.ref)))) })
      // ⚠️ 拿不到視野時**不過濾**（顯示全部），而不是顯示空的
      //    ——把「查詢失敗」畫成「這裡沒有東西」正是沉默失敗。
      .catch(() => { if (alive) setRefs(null) })
    return () => { alive = false }
  }, [did, kind])

  const scoped = did !== null && refs !== null
  return {
    did,
    scoped,
    inScope: (ref: number | string) => !scoped || refs!.has(String(ref)),
    /** ⚠️ 視野被縮過就一定要畫這一條。 */
    banner: scoped ? (
      <div className="rounded-md border border-dashed px-3 py-1.5 text-xs text-muted-foreground">
        只顯示你目前所在領域底下的。
        <button onClick={() => go(null)} className="ml-1 underline hover:text-foreground">
          在整個{ROOT_NAME}找
        </button>
      </div>
    ) : null,
  }
}
