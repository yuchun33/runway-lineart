# Runway lineart

下載時裝 Look、透過 OpenAI 與 Gemini 生成線稿，並以靜態網站比較原圖及各模型版本。
<img width="1910" height="967" alt="image" src="https://github.com/user-attachments/assets/d7f0cb5a-63bf-4538-8c27-f378b75900cc" />

支援使用 [instagrapi](https://github.com/subzeroid/instagrapi) 將原圖、線稿與 Look 資訊合成發佈圖，並透過佇列發佈至 Instagram。

## 安裝

使用 Python 3.12+ 與 uv，在專案根目錄執行：

```powershell
uv sync --locked
```

## KEY 與設定位置

本機 API KEY 放在專案根目錄的 `.env`，也可以透過環境變數設定；產圖程式另外支援 `scripts/.env`。
GitHub Actions 使用 repository 的 **Settings → Secrets and variables → Actions → Repository secrets**，名稱與下表完全一致。

| 設定名稱 | 用途 | 本機位置 | GitHub Actions 位置 |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | 使用 OpenAI 生成線稿時需要 | `.env` | 同名 Repository secret；目前排程使用 OpenAI |
| `GEMINI_API_KEY` | 使用 Gemini 生成線稿時需要 | `.env` | 同名 Repository secret；目前排程未執行 Gemini |
| `INSTAGRAM_SESSION_JSON` | Instagram 已登入的 session | 使用 `local/session.json` 檔案，不需設定此環境變數 | 同名 Repository secret，值為 `local/session.json` 的完整 JSON |

本機 `.env` 範例（只需設定要使用的產圖服務）：

```dotenv
OPENAI_API_KEY=your_openai_api_key
GEMINI_API_KEY=your_gemini_api_key
```

Instagram 預設使用 `local/session.json`，已有有效 session 時不需帳密。若要在本機建立 session，可在根目錄 `.env` 設定 `INSTAGRAM_USERNAME`、`INSTAGRAM_PASSWORD`；需要兩步驟驗證時再提供 `INSTAGRAM_VERIFICATION_CODE`。目前 Actions 只使用 session，不使用帳密登入。

下載原圖、合成圖片及瀏覽網站不需要 API KEY。`.env` 與 `local/` 已被 Git 忽略，請勿提交金鑰或 session。Actions workflow 已宣告 `contents: write`，repository 也需允許 workflow 推送 commit。

## 常用操作

```powershell
# 下載前先預覽；移除 --dry-run 才下載
uv run python -m scripts.collectors.chanel --season cruise-2026-27 --dry-run

# 預覽第一張有 Gemini 待辦的照片；移除 --dry-run 才呼叫生成 API
uv run scripts/run_queue.py --provider gemini --dry-run

# 將已存在的素材更新至網站索引
uv run scripts/update_web_data.py

# 以專案根目錄提供網站，瀏覽 http://localhost:8000/web/
uv run python -m http.server 8000
```

網頁維持純 HTML/CSS/JavaScript，不需要 Python 檔案放在 web/。不要僅以 web/ 啟動伺服器，否則讀不到旁邊的 output/image/。

## 目錄與文件

- `scripts/`：下載、生成、佇列與索引工具
- `scripts/queue.json`：工作順序、明確輸入輸出與各模型狀態
- `output/image/品牌/季度/Look/`：original、source.json 與 linearts/模型/版本。
- `web/`：靜態展示與 data.json
- `local/`：本機筆記、設計資料與 snapshots/ 頁面快照，不提交 Git。
- `output/logs/`：執行日誌，不提交 Git。

## GitHub Actions

`generate-lineart.yml` 每天排程或手動觸發一張照片的 queued 模型任務。需將原圖與已完成線稿納入 repository，設定 Actions Secrets，並允許回存 commit。

`checks.yml` 在 push、pull request 或手動觸發時執行測試、JSON/路徑驗證與 JavaScript 語法檢查，不使用金鑰或生成圖片。
