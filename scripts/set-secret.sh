#!/usr/bin/env bash
# 安全地往 knowfield-env 加／改幾個 key——**不動其他 key**。
#
# ⚠️ 為什麼需要這支——實測過的，不是憑印象（2026-08-27）：
#     kubectl create secret ... --dry-run=client -o yaml | kubectl apply -f -
#    會不會刪掉沒列到的 key，**取決於這個 secret 是怎麼建的**：
#      · `kubectl create` 建的（＝knowfield-env 現況）→ 沒有 last-applied 註記 → 合併，**不會刪**
#      · `kubectl apply` 建過的            → 有 last-applied → **會刪，而且零錯誤訊息**
#    ⇒ 所以「第一次完整 apply」就是把陷阱裝上的那一刻。這支一律用 merge patch，
#      並在最後**明著比對改前改後的 key**——那一行才是它存在的理由。
#
# ⓘ 順帶查證：`knowfield-env` 沒有 Helm 標記（release 用 existingSecret 指過去）
#    ⇒ `helm upgrade` **不會**蓋掉你在這裡加的 key。
#
# 用法：
#   scripts/set-secret.sh KEY=值 KEY=@檔案路徑 KEY
#     KEY=值      直接給（⚠️ 會進 shell history——秘密別這樣給）
#     KEY=@路徑   從檔案讀（給 .pem 這種多行的用這個）
#     KEY         **不給值 ⇒ 安靜地問你**，不回顯、不進 history ← 秘密用這個
#
#   FROM_ENV=1  bare KEY 改成**從 .env 讀**（填完 .env 之後生 secret 用這個）
#     ⚠️ **只推你點名的 key，永遠不整份同步**——.env 裡有只該留在本機的東西，
#        其中 KNOWFIELD_AUTH_DISABLED=1 推上正式會**把登入牆整個關掉**。
#        底下有一份拒絕清單，硬擋。
#     ⓘ 點名 KNOWFIELD_GITHUB_PRIVATE_KEY 而 .env 只有 ..._PATH 時，
#        會去讀那個檔案、把**內容**推上去（容器裡沒有那個檔案）。
#
#   環境變數：NS（預設 knowfield）· SECRET（預設 knowfield-env）· LOCAL=1 同時寫 .env
set -euo pipefail
NS="${NS:-knowfield}"; SECRET="${SECRET:-knowfield-env}"
[ $# -gt 0 ] || { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }

# ⚠️ 只該留在本機的 key——推上正式會出事，硬擋
DENY="KNOWFIELD_AUTH_DISABLED:KNOWFIELD_DATABASE_URL:KNOWFIELD_GITHUB_PRIVATE_KEY_PATH"

PATCH=$(mktemp); ENVTMP=$(mktemp); chmod 600 "$PATCH" "$ENVTMP"
cleanup(){ rm -f "$PATCH" "$ENVTMP"; }; trap cleanup EXIT

echo "── 現在有的 key（改之前）──"
BEFORE=$(kubectl -n "$NS" get secret "$SECRET" -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}' | sort)
echo "$BEFORE" | sed 's/^/    /'

# 收集 key=value 進一個暫存檔（NUL 分隔），值不經過 argv ⇒ ps 看不到
: > "$ENVTMP"
KEYS=(); FROMENV=()
for arg in "$@"; do
  case "$arg" in
    *=@*) k="${arg%%=*}"; f="${arg#*=@}"; f="${f/#\~/$HOME}"
          [ -r "$f" ] || { echo "讀不到檔案：$f" >&2; exit 1; }
          printf '%s\0' "$k" >> "$ENVTMP"; cat "$f" >> "$ENVTMP"; printf '\0' >> "$ENVTMP" ;;
    *=*)  k="${arg%%=*}"; v="${arg#*=}"
          printf '%s\0%s\0' "$k" "$v" >> "$ENVTMP" ;;
    *)    k="$arg"
          case ":$DENY:" in *":$arg:"*)
            echo "⚠️ 拒絕：$arg 只該留在本機，推上正式會出事" >&2; exit 1 ;; esac
          if [ "${FROM_ENV:-}" = "1" ]; then
            FROMENV+=("$arg")            # ⓘ 集中到最後一次讀，別在迴圈裡開 heredoc
          else
            printf '  %s = ' "$arg" >&2; read -rs v; echo >&2
            [ -n "$v" ] || { echo "  （空的，跳過）" >&2; continue; }
            printf '%s\0%s\0' "$arg" "$v" >> "$ENVTMP"
          fi ;;
  esac
  KEYS+=("$k")
done

# .env 的部分集中在一次呼叫（PRIVATE_KEY 會把 ..._PATH 指的檔案讀成內容）
if [ ${#FROMENV[@]} -gt 0 ]; then
  python3 "$(dirname "$0")/_env_to_pairs.py" "$ENVTMP" .env "${FROMENV[@]}"
fi

# ⚠️ 用 stringData 做 **merge patch**：只碰列到的 key，其餘原封不動。
python3 - "$ENVTMP" "$PATCH" <<'PY'
import json, sys
raw = open(sys.argv[1], 'rb').read().split(b'\0')
pairs = {}
for i in range(0, len(raw) - 1, 2):
    k = raw[i].decode()
    if k:
        pairs[k] = raw[i + 1].decode()
json.dump({"stringData": pairs}, open(sys.argv[2], 'w'))
PY

echo "── 要寫入 ${#KEYS[@]} 個 key：${KEYS[*]} ──"
kubectl -n "$NS" patch secret "$SECRET" --type=merge --patch-file "$PATCH" >/dev/null
echo "── 改之後 ──"
AFTER=$(kubectl -n "$NS" get secret "$SECRET" -o go-template='{{range $k,$v := .data}}{{$k}}{{"\n"}}{{end}}' | sort)
echo "$AFTER" | sed 's/^/    /'

# ⚠️ 明著檢查「有沒有弄丟東西」——這支存在的全部理由就是這一行
LOST=$(comm -23 <(echo "$BEFORE") <(echo "$AFTER"))
[ -z "$LOST" ] || { echo "⚠️ 有 key 不見了：$LOST" >&2; exit 1; }
echo "✅ 沒有弄丟任何既有的 key（$(echo "$BEFORE"|wc -l|tr -d ' ') → $(echo "$AFTER"|wc -l|tr -d ' ')）"

if [ "${LOCAL:-}" = "1" ]; then
  python3 - "$ENVTMP" .env <<'PY'
import pathlib, sys
raw = open(sys.argv[1], 'rb').read().split(b'\0')
p = pathlib.Path(sys.argv[2]); lines = p.read_text(encoding='utf-8').splitlines() if p.exists() else []
for i in range(0, len(raw) - 1, 2):
    k = raw[i].decode()
    if not k: continue
    v = raw[i + 1].decode()
    entry = f"{k}={v!r}" if "\n" in v else f"{k}={v}"   # 多行的用 repr（.env 讀得動單行）
    lines = [l for l in lines if not l.startswith(k + "=")] + [entry]
p.write_text("\n".join(lines) + "\n", encoding='utf-8')
PY
  echo "✅ 也寫進 .env（在 .gitignore 裡）"
fi

printf '\n重啟讓它生效？[y/N] '; read -r yn
if [ "$yn" = "y" ] || [ "$yn" = "Y" ]; then
  kubectl -n "$NS" rollout restart deploy/knowfield-knowfield
  kubectl -n "$NS" rollout status deploy/knowfield-knowfield --timeout=180s
else
  echo "ⓘ 還沒生效——envFrom 是 pod 啟動時注入的。之後跑："
  echo "    kubectl -n $NS rollout restart deploy/knowfield-knowfield"
fi
