# Runway lineart

下載時裝 Look、透過 OpenAI 與 Gemini 生成線稿，並以靜態網站比較原圖及各模型版本。

<img width="1910" height="967" alt="image" src="https://github.com/user-attachments/assets/d7f0cb5a-63bf-4538-8c27-f378b75900cc" />

## 安裝

使用 Python 3.12+ 與 uv，在專案根目錄執行：

```powershell
uv sync --locked
```

需自備 `OPENAI_API_KEY`、`GEMINI_API_KEY`。

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

- `scripts/`：下載、生成、佇列與索引工具，見 [腳本說明](scripts/README.md)。
- `scripts/queue.json`：工作順序、明確輸入輸出與各模型狀態，見 [佇列操作](scripts/README.md)。
- `output/image/品牌/季度/Look/`：original、source.json 與 linearts/模型/版本。
- `web/`：靜態展示與 data.json，見 [網頁說明](web/README.md)。
- `local/`：本機筆記、設計資料與 snapshots/ 頁面快照，不提交 Git。
- `output/logs/`：執行日誌，不提交 Git。

下載細節見 [Collectors](scripts/README.md#collectors)。

## GitHub Actions

`generate-lineart.yml` 每天台北時間 08:00 或手動觸發一張照片的 queued 模型任務。需將原圖與已完成線稿納入 repository，設定 Actions Secrets，並允許回存 commit。

`checks.yml` 在 push、pull request 或手動觸發時執行測試、JSON/路徑驗證與 JavaScript 語法檢查，不使用金鑰或生成圖片。

## 本機驗證

```powershell
uv run python -B -m unittest discover -s scripts/tests -t . -p "test*.py"
uv run python -B -m scripts.check_data
uv run scripts/update_web_data.py --check
```
