# Patch: Mem0 OpenAI Embedder — 移除對第三方端點不相容的 `dimensions` 參數

## 問題描述

執行系統後，在 terminal 觀察到每次使用者送出訊息時，Mem0 記憶體操作都會失敗並拋出 HTTP 400 Bad Request：

```
INFO     HTTP Request: POST https://api.voyageai.com/v1/embeddings "HTTP/1.1 400 Bad Request"
```

此錯誤導致 Mem0 無法儲存或搜尋對話記憶，造成跨輪次的情境記憶功能完全失效。

## 根本原因

問題出在 Mem0 套件本身的 OpenAI embedder 實作：

**檔案：** `.venv/lib/python3.12/site-packages/mem0/embeddings/openai.py`

**問題程式碼（修改前，第 44–49 行）：**

```python
text = text.replace("\n", " ")
return (
    self.client.embeddings.create(
        input=[text],
        model=self.config.model,
        dimensions=self.config.embedding_dims   # ← 問題所在
    )
    .data[0]
    .embedding
)
```

`dimensions` 是 OpenAI 在 `text-embedding-3` 系列才引入的參數，允許截斷輸出向量的維度。Mem0 的 openai embedder 無論使用哪個後端，都會無條件帶上這個參數，且預設值為 1536（即使設定了 `embedding_dims`，也至少會帶上設定值）。

VoyageAI 的 OpenAI 相容端點（`https://api.voyageai.com/v1`）**不支援** `dimensions` 參數，收到此參數時直接回傳 400 Bad Request。

此問題不僅限於 VoyageAI，任何不支援 OpenAI `dimensions` 擴充的第三方 OpenAI 相容端點（例如部分 vLLM 部署、Together AI embedding models 等）都會受到影響。

## 我們期望的行為

- 使用官方 OpenAI endpoint（`https://api.openai.com/v1`）時：正常帶上 `dimensions` 參數，支援向量截斷功能
- 使用第三方 OpenAI 相容端點時：**不**帶 `dimensions` 參數，以維持相容性
- Mem0 能正常與 VoyageAI (`voyage-4-lite`) 協作，完成記憶的新增、搜尋、更新操作

## 修改內容

**修改檔案：** `.venv/lib/python3.12/site-packages/mem0/embeddings/openai.py`

**修改後的 `embed()` 方法（第 44–60 行）：**

```python
text = text.replace("\n", " ")
# Only pass `dimensions` for the official OpenAI endpoint.
# Third-party OpenAI-compatible endpoints (e.g. VoyageAI) do not support
# this parameter and return 400 Bad Request when it is present.
is_official_openai = (
    self.config.openai_base_url is None
    and not os.getenv("OPENAI_API_BASE")
    and not os.getenv("OPENAI_BASE_URL")
)
kwargs = {"input": [text], "model": self.config.model}
if is_official_openai:
    kwargs["dimensions"] = self.config.embedding_dims
return (
    self.client.embeddings.create(**kwargs)
    .data[0]
    .embedding
)
```

判斷邏輯：若 `openai_base_url` 設定為自訂 URL（包括環境變數 `OPENAI_API_BASE` / `OPENAI_BASE_URL`），則判定為第三方端點，不帶 `dimensions` 參數。

同時，也從 `src/main.py` 的 Mem0 config 字典中移除了 `"embedding_dims"` 欄位（原第 238 行），原因是：
1. 帶不帶這個值對修補後的程式行為不再有影響
2. 減少誤導性設定，VoyageAI 的 `voyage-4-lite` 預設輸出維度本就是 1024

## 修改後的行為

- Mem0 呼叫 VoyageAI embedding endpoint 時，請求中不再包含 `dimensions` 參數
- VoyageAI 正常處理請求，回傳 1024 維向量（`voyage-4-lite` 預設）
- Mem0 記憶新增、搜尋、更新功能恢復正常運作
- ChromaDB 中的 `cocai` collection（Mem0 記憶庫）可正常讀寫

## 預期效果

| 功能 | 修改前 | 修改後 |
|------|--------|--------|
| Mem0 記憶儲存 | 失敗（400） | 正常 |
| Mem0 記憶搜尋 | 失敗（400） | 正常 |
| 跨輪次情境記憶 | 無效 | 有效 |
| Background history update | embedding 失敗後靜默跳過 | 正常執行 |
| Background scene update | embedding 失敗後靜默跳過 | 正常執行 |

## 注意事項與後續維護

### Patch 的脆弱性
此修改直接修改了 `.venv/` 內的套件檔案。以下操作會導致 patch 遺失，需重新套用：

- `uv sync`
- `uv pip install --upgrade mem0ai`
- 刪除並重建 `.venv/`

### 重新套用 patch 的方式
重新執行本文件中「修改內容」一節中對 `embed()` 方法的替換，或參考此 patch 的 git 歷史記錄。

### 長期解決方案建議
1. **向 Mem0 上游回報此問題**，建議他們在使用自訂 base_url 時跳過 `dimensions` 參數，或提供設定項目讓使用者明確控制
2. **等待 Mem0 新版本**，確認 bug 是否已在新版中修復後，移除此 patch
3. 若 Mem0 釋出原生 VoyageAI embedder provider，可直接切換使用

### 相關設定
- `config.toml` `[embedding]` 段：`model = "voyage-4-lite"`、`api_base = "https://api.voyageai.com/v1"`
- `src/main.py` `__prepare_memory()` 函式：Mem0 本地配置字典
- Mem0 記憶的 ChromaDB collection：`.data/chroma/`，collection 名稱為 `cocai`（由 `config.toml` `[vector_store] mem_collection` 設定）
