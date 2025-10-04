# 🔧 OAuth Token 刷新修復說明

## 🎯 修復內容

本次更新解決了以下問題：

### ✅ 問題 1：Token 過期頻繁要求重新登入
- **原因**：Access Token 只存活 1-2 小時，過期就必須重新登入
- **解決方案**：
  - 實作 Refresh Token 機制（有效期 30 天）
  - 支援 `grant_type=refresh_token`，讓 Claude Connector 自動刷新
  - Token 過期時自動換新，無需使用者互動

### ✅ 問題 2：服務重啟後 Token 失效
- **原因**：Token 只存在記憶體，容器重啟就全部消失
- **解決方案**：
  - 建立 `OAuthToken` 資料庫表（SQLite）
  - 所有 Token 持久化儲存
  - 服務重啟後 Token 依然有效

### ✅ 問題 3：連線被反向代理切斷
- **原因**：Nginx/ALB 預設 60 秒閒置逾時
- **解決方案**：
  - SSE 連線加上每 30 秒心跳
  - 防止被反向代理意外切斷

---

## 📋 更新的檔案

1. **`ticktick_mcp/src/ics_sync/models.py`**
   - 新增 `OAuthToken` 資料庫模型

2. **`ticktick_mcp/src/remote_server.py`**
   - 實作 Refresh Token 生成與驗證
   - 加入 `grant_type=refresh_token` 支援
   - 所有 Token 操作改為資料庫存取
   - 加上 SSE 心跳保活（30 秒）

---

## 🚀 如何使用

### 1. 重新啟動服務

```bash
# 如果用 Docker Compose
docker-compose down
docker-compose up -d

# 如果用 uv 本地執行
uv run -m ticktick_mcp.cli remote --host 0.0.0.0 --port 8080
```

### 2. 重新連接 Claude.ai

1. 進入 Claude.ai Integrations
2. 如果之前已連接，**先刪除舊的連接**
3. 重新新增 MCP Server：
   - URL: `https://your-domain.com/sse`
   - OAuth Client ID: `ticktick-mcp-client`
   - OAuth Client Secret: `TMC_2024_SecureSecret_ForDirectAuth_NoRedirect`
4. 完成授權後，**Token 現在會自動刷新！**

### 3. 驗證修復

測試方式：
- 等待 1 小時後，Claude 應該還能正常使用（之前會被踢出）
- 重啟服務後，Claude 應該不需要重新登入

---

## 🔧 Nginx 反向代理配置（選配）

如果你有使用 Nginx 反向代理，建議調整 timeout 設定：

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;

    # SSL 配置
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # SSE 端點特殊配置
    location /sse {
        proxy_pass http://localhost:8080;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # 重要：延長 timeout（原本 60 秒）
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_connect_timeout 75s;

        # 禁用緩衝（SSE 需要）
        proxy_buffering off;
        proxy_cache off;
    }

    # OAuth 端點
    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

重新載入 Nginx：
```bash
sudo nginx -t
sudo nginx -s reload
```

---

## 🐛 故障排除

### 問題：還是要重新登入

**檢查事項**：
1. 確認 `.env` 檔案存在，且有 TickTick 憑證
2. 檢查服務日誌：`docker-compose logs -f`
3. 確認資料庫檔案已建立：`ls ticktick_mcp/src/ics_sync/ics_sync.db`
4. Claude.ai 需要**刪除舊連接**並重新新增

### 問題：連線還是會斷

**檢查事項**：
1. 查看日誌是否有 `SSE heartbeat sent`（應該每 30 秒一次）
2. 如果用 Nginx，確認已調整 `proxy_read_timeout`
3. 如果用 Cloudflare，可能需要調整 WebSocket timeout

### 問題：資料庫錯誤

```bash
# 如果出現資料庫表格不存在
# 刪除舊資料庫並重新初始化
rm ticktick_mcp/src/ics_sync/ics_sync.db
docker-compose restart
```

---

## 📊 技術細節

### Token 類型與有效期

| Token 類型 | 有效期 | 用途 |
|-----------|--------|------|
| Access Token | 1 小時 | API 呼叫認證 |
| Refresh Token | 30 天 | 換取新的 Access Token |
| Authorization Code | 10 分鐘 | OAuth 流程中介碼（記憶體） |

### 資料庫架構

```sql
CREATE TABLE oauth_tokens (
    id INTEGER PRIMARY KEY,
    token VARCHAR(200) UNIQUE NOT NULL,
    token_type VARCHAR(20) NOT NULL,  -- 'access' or 'refresh'
    client_id VARCHAR(100) NOT NULL,
    username VARCHAR(100),
    scope VARCHAR(200),
    grant_type VARCHAR(50),
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    parent_token VARCHAR(200)  -- refresh token 對應的 access token
);
```

### OAuth 流程

1. **首次登入**：
   - 使用者授權 → 取得 Authorization Code
   - 交換 Code → 同時獲得 Access Token + Refresh Token
   - 兩者都存入資料庫

2. **Token 刷新**（自動）：
   - Access Token 快到期時，Claude 自動發送 `grant_type=refresh_token`
   - 驗證 Refresh Token → 核發新 Access Token
   - 舊 Access Token 刪除，新 Token 存入資料庫

3. **服務重啟**：
   - Token 從資料庫讀取
   - 只要 Token 未過期，使用者無需重新登入

---

## 🎉 預期效果

- ✅ **不再頻繁要求登入**：Token 自動刷新，30 天內都有效
- ✅ **服務重啟不影響使用**：Token 持久化儲存
- ✅ **連線更穩定**：心跳機制防止被切斷
- ✅ **更好的使用者體驗**：無感 Token 刷新

---

## 📝 版本資訊

- **修復日期**：2025-10-01
- **影響版本**：3.18 及之前版本
- **修復版本**：3.19+

---

## 💬 需要協助？

如果遇到問題，請提供：
1. 服務日誌（`docker-compose logs -f`）
2. Nginx 配置（如果有用）
3. Claude.ai 的錯誤訊息截圖

建議開 GitHub Issue 或聯繫開發者。
