# TickTick MCP Server - Claude Code 專案文件

## 🎯 專案概述

這是一個 **TickTick Model Context Protocol (MCP) 服務器**，讓 Claude 和其他 AI 助手能夠直接與 TickTick 任務管理系統互動。

### 核心功能
- 📋 查看所有 TickTick 項目和任務
- ✏️ 透過自然語言創建新項目和任務
- 🔄 更新任務詳情（標題、內容、日期、優先級）
- 🔔 設定任務提醒
- ✅ 標記任務為完成
- 🗑️ 刪除任務和項目
- 🌏 **完整時區支援**（自動格式標準化）
- 🔐 **雙重 OAuth 認證模式**

### 運行模式
1. **本地模式**：配合 Claude Desktop 使用
2. **遠端模式**：透過 Claude.ai Integrations 使用（支援 SSE）

## 📁 專案結構

```
ticktick_mcp/
├── 📄 CLAUDE.md              # 此文件，供 Claude Code 參考
├── 📄 README.md              # 主要說明文件
├── 📄 README-REMOTE.md       # 遠端部署指南
├── 📄 .env                   # 環境變數配置
├── 📄 Dockerfile             # Docker 容器配置
├── 📄 docker-compose*.yml    # Docker Compose 配置
├── 📄 requirements.txt       # Python 依賴
├── 📄 setup.py              # 包安裝配置
│
├── 🐍 ticktick_mcp/         # 主要 Python 包
│   ├── 📄 __init__.py       
│   ├── 📄 cli.py            # CLI 入口點
│   ├── 📄 authenticate.py   # TickTick OAuth 認證
│   │
│   ├── 📁 src/              # 核心服務器代碼
│   │   ├── 📄 server.py           # 本地 MCP 服務器（Claude Desktop）
│   │   ├── 📄 remote_server.py    # 遠端 SSE 服務器（Claude.ai）
│   │   ├── 📄 ticktick_client.py  # TickTick API 客戶端
│   │   ├── 📄 auth.py            # OAuth 認證邏輯
│   │   ├── 📄 oauth_server.py    # OAuth 認證服務器
│   │   └── 📁 ics_sync/         # ICS 日曆同步功能
│   │
│   └── 📁 web/              # React 前端（OAuth 登入頁面）
│       ├── 📄 package.json  # Node.js 依賴
│       ├── 📄 vite.config.ts # Vite 構建配置
│       └── 📁 src/         # React 組件
│
├── 🧪 test_*.py            # 各種測試腳本
├── 🔧 *.sh                 # 構建和部署腳本
└── 📄 ticktick_mcp_java/   # Java 實現（實驗性）
```

## 🔧 核心組件說明

### 1. **TickTick API 客戶端** (`ticktick_client.py`)
- 處理 TickTick API 的所有呼叫
- **重要修復**：時區格式標準化
  ```python
  def normalize_timezone_format(date_string: str) -> str:
      # 將 "+08:00" 轉換為 "+0800"（TickTick API 要求格式）
  ```
- 支援項目、任務、提醒的 CRUD 操作
- 自動處理 OAuth token 刷新

### 2. **本地 MCP 服務器** (`server.py`)
- 供 Claude Desktop 使用的 stdio 服務器
- 提供完整的 MCP 工具集：
  - `get_projects`: 獲取所有項目
  - `get_tasks`: 獲取任務列表
  - `create_task`: 創建新任務（支援時區）
  - `update_task`: 更新任務詳情
  - `delete_task`: 刪除任務
  - `complete_task`: 完成任務

### 3. **遠端 SSE 服務器** (`remote_server.py`)
- 供 Claude.ai Integrations 使用
- 支援 **雙重 OAuth 認證模式**：
  - **Option A**: Client Credentials Grant（直接認證）
  - **Option B**: Authorization Code Grant（登入重定向）
- 提供 Server-Sent Events (SSE) 端點
- 整合 OAuth 認證服務器

### 4. **OAuth 認證系統**
```python
# 環境變數配置
OAUTH_CLIENT_ID=ticktick-mcp-client
OAUTH_CLIENT_SECRET=TMC_2024_SecureSecret_ForDirectAuth_NoRedirect
OAUTH_USERNAME=admin
OAUTH_PASSWORD=your-secure-password
```

## 🐳 CI/CD 部署流程

### Docker Hub 映像
- **映像名稱**: `audichuang880208/ticktick-mcp:latest`
- **版本標籤**: `audichuang880208/ticktick-mcp:1.0.1`

### 構建與部署腳本

1. **`docker-build-push.sh`** - 完整構建並推送
   ```bash
   #!/bin/bash
   # 構建 Docker 映像
   docker build -t ticktick-mcp:latest .
   # 標籤並推送到 Docker Hub
   docker tag ticktick-mcp:latest audichuang880208/ticktick-mcp:latest
   docker push audichuang880208/ticktick-mcp:latest
   ```

2. **`docker-push-only.sh`** - 僅推送已構建的映像
   ```bash
   # 適用於已構建但需要推送的情況
   docker push audichuang880208/ticktick-mcp:latest
   ```

### Docker Compose 配置
- `docker-compose.yml` - 本地開發
- `docker-compose.prod.yml` - 生產環境（使用 Docker Hub 映像）

## ⚡ 快速開始指南

### 本地開發
```bash
# 安裝依賴
uv sync

# TickTick OAuth 認證
uv run -m ticktick_mcp.cli auth

# 運行本地服務器
uv run -m ticktick_mcp.cli run

# 運行遠端服務器（測試用）
uv run -m ticktick_mcp.cli remote --host 0.0.0.0 --port 8080
```

### Docker 部署
```bash
# 使用預構建映像
docker-compose -f docker-compose.prod.yml up -d

# 本地構建
docker-compose up -d
```

## 🧪 測試腳本說明

| 腳本 | 用途 |
|------|------|
| `test_server.py` | 測試基本 TickTick 功能 |
| `test_client_credentials.py` | 測試 Client Credentials OAuth 流程 |
| `test_timezone_fix.py` | 測試時區格式修復 |
| `test-oauth-client.py` | 測試 OAuth 認證流程 |
| `test-sse-client.py` | 測試 SSE 連接 |

## 🔍 重要修復與功能

### 1. **時區格式標準化**（最近修復）
**問題**：AI 創建的任務使用 `+08:00` 格式時，TickTick 不顯示時間
**解決方案**：自動轉換所有時區格式為 `+0800`
```python
# 支援的輸入格式：
"+08:00" → "+0800"  # 標準 ISO 格式
"+8:00"  → "+0800"  # 單位數小時
"+8"     → "+0800"  # 最簡格式
```

### 2. **雙重 OAuth 模式**
- **Client Credentials**: 適用於個人使用，無需登入重定向
- **Authorization Code**: 適用於多用戶環境，需要登入頁面

### 3. **完整的 MCP 工具集**
每個工具都包含詳細的描述和參數驗證，支援：
- 智能時區推斷
- 彈性的日期格式
- 優先級設定
- 提醒配置

## 🔗 Claude.ai 集成

### 配置方式
1. **直接認證**（推薦）：
   - URL: `https://your-domain.com/sse`
   - OAuth Client ID: `ticktick-mcp-client`
   - OAuth Client Secret: `TMC_2024_SecureSecret_ForDirectAuth_NoRedirect`

2. **傳統登入流程**：
   - URL: `https://your-domain.com/sse`
   - 留空 OAuth 欄位，Claude.ai 會自動處理重定向

## 🛠️ 開發注意事項

### 重要環境變數
```bash
# TickTick API 認證
TICKTICK_CLIENT_ID=your_client_id
TICKTICK_CLIENT_SECRET=your_client_secret
TICKTICK_ACCESS_TOKEN=auto_generated
TICKTICK_REFRESH_TOKEN=auto_generated

# OAuth 服務器設定
OAUTH_USERNAME=admin
OAUTH_PASSWORD=secure-password
OAUTH_CLIENT_ID=ticktick-mcp-client
OAUTH_CLIENT_SECRET=TMC_2024_SecureSecret_ForDirectAuth_NoRedirect
```

### 常用命令
```bash
# 重新認證 TickTick
uv run -m ticktick_mcp.cli auth

# 測試服務器功能
python test_server.py

# 構建並推送 Docker 映像
./docker-build-push.sh

# 僅推送到 Docker Hub
./docker-push-only.sh
```

## 🚨 故障排除

### 常見問題
1. **任務不顯示時間**：檢查時區格式，應自動修復
2. **OAuth 認證失敗**：確認環境變數正確設定
3. **Docker 容器啟動失敗**：檢查 `.env` 文件是否存在
4. **Claude.ai 連接失敗**：驗證 HTTPS 和 OAuth 端點

### 調試技巧
- 查看服務器日誌：`docker-compose logs -f`
- 測試 OAuth 發現：`curl https://your-domain.com/.well-known/oauth-authorization-server`
- 驗證 SSE 端點：使用 `test-sse-client.py`

## 📚 相關文件
- [主要說明文件](README.md)
- [遠端部署指南](README-REMOTE.md)
- [TickTick API 文檔](https://developer.ticktick.com/)
- [MCP 規範](https://modelcontextprotocol.io/)

---
*最後更新：2025-09-03 - 新增時區格式標準化修復*