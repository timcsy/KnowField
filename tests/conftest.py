"""測試 session 起點的隔離設定。

守衛：測試**不讀開發者本機 `.env`**（否則會撈到真實設定——例如填好的 Google 登入 auth——
汙染測試、啟用門鎖、擋掉 web 測）。並清掉任何從 shell/.env 洩入的 auth／DB 環境變數，讓測試從乾淨開始。
"""

import os

os.environ["KNOWFIELD_NO_DOTENV"] = "1"

# 保險：若這些變數已從 shell 洩入，清掉（各測試會自己設需要的）。
for _k in (
    "KNOWFIELD_DATABASE_URL",
    "KNOWFIELD_AUTH_ALLOWLIST",
    "KNOWFIELD_GOOGLE_CLIENT_ID",
    "KNOWFIELD_GOOGLE_CLIENT_SECRET",
    "KNOWFIELD_SESSION_SECRET",
    "KNOWFIELD_AUTH_DISABLED",
):
    os.environ.pop(_k, None)
