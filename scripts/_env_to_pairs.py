"""從 .env 讀指定的 key，附加成 NUL 分隔的 key/value 對。

⚠️ `KNOWFIELD_GITHUB_PRIVATE_KEY` 特別處理：.env 放的是**路徑**（那個 .env 讀取器
是逐行的，多行 PEM 貼進去會被截斷，而且 base64 那幾行含 `=` 會污染環境變數
——實測 2026-08-27）。而容器裡沒有那個檔案 ⇒ 推上去的必須是**內容**。
"""
import os
import pathlib
import sys

out_path, env_path, *keys = sys.argv[1:]
env: dict[str, str] = {}
p = pathlib.Path(env_path)
if p.exists():
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")

pairs, missing = [], []
for k in keys:
    v = env.get(k, "")
    if not v and k.endswith("_PRIVATE_KEY"):
        fp = env.get(k + "_PATH", "")
        if fp:
            fp = os.path.expanduser(fp)
            if not os.path.isfile(fp):
                sys.exit(f"讀不到 {k}_PATH 指的檔案：{fp}")
            v = pathlib.Path(fp).read_text(encoding="utf-8")
            print(f"  ← {fp}  {k}（{len(v)} bytes）", file=sys.stderr)
    if not v:
        missing.append(k)
        continue
    if not k.endswith("_PRIVATE_KEY"):
        print(f"  ← {env_path}  {k}", file=sys.stderr)
    pairs.append(k)
    pairs.append(v)

if missing:
    sys.exit(f"⚠️ .env 裡找不到：{', '.join(missing)}（PRIVATE_KEY 也可用 ..._PATH 給）")

with open(out_path, "ab") as f:
    for x in pairs:
        f.write(x.encode() + b"\0")
print("\0".join(""), end="")
