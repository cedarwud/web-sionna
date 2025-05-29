# =============================================================================
# Sionna RT 無線電模擬系統 - Makefile
# =============================================================================
# 這個 Makefile 提供了便捷的開發和部署指令
# 使用方式: make <command>
# 獲取幫助: make help
# =============================================================================

# 顏色定義 (用於美化輸出)
RED=\033[0;31m
GREEN=\033[0;32m
YELLOW=\033[1;33m
BLUE=\033[0;34m
PURPLE=\033[0;35m
CYAN=\033[0;36m
WHITE=\033[1;37m
NC=\033[0m # No Color

# 專案配置
PROJECT_NAME=sionna-rt
COMPOSE_FILE=docker-compose.yml
ENV_FILE=.env

# Docker Compose 指令別名
DC=docker compose
DCE=docker compose exec

# =============================================================================
# 預設目標
# =============================================================================

.DEFAULT_GOAL := help
.PHONY: help

# =============================================================================
# 幫助和資訊指令
# =============================================================================

help: ## 📋 顯示所有可用指令
	@echo "$(CYAN)========================================$(NC)"
	@echo "$(WHITE)  Sionna RT 無線電模擬系統 - Make 指令  $(NC)"
	@echo "$(CYAN)========================================$(NC)"
	@echo ""
	@echo "$(YELLOW)🚀 基本操作:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## .*🚀/ {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)🛠️ 開發指令:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## .*🛠️/ {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)🗄️ 資料庫指令:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## .*🗄️/ {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)📊 監控和日誌:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## .*📊/ {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(YELLOW)🧹 清理指令:$(NC)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## .*🧹/ {printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(GREEN)使用範例: make up, make logs, make shell-backend$(NC)"

status: ## 📊 檢查所有服務狀態
	@echo "$(YELLOW)📊 檢查服務狀態...$(NC)"
	$(DC) ps

version: ## 📋 顯示系統版本資訊
	@echo "$(CYAN)🔧 系統版本資訊:$(NC)"
	@echo "Docker: $$(docker --version)"
	@echo "Docker Compose: $$(docker compose version)"
	@echo "Make: $$(make --version | head -n1)"

# =============================================================================
# 基本服務管理
# =============================================================================

up: build ## 🚀 建構並啟動所有服務
	@echo "$(GREEN)🚀 啟動 Sionna RT 系統...$(NC)"
	$(DC) up -d
	@echo "$(GREEN)✅ 系統啟動完成!$(NC)"
	@echo "$(CYAN)📱 前端: http://localhost:5174$(NC)"
	@echo "$(CYAN)🔧 後端: http://localhost:8889$(NC)"
	@echo "$(CYAN)📚 API文檔: http://localhost:8889/docs$(NC)"

down: ## 🚀 停止所有服務
	@echo "$(YELLOW)⏹️ 停止所有服務...$(NC)"
	$(DC) down
	docker network prune -f
	@echo "$(GREEN)✅ 服務已停止$(NC)"

restart: down up ## 🚀 重啟所有服務
	@echo "$(GREEN)🔄 重啟完成$(NC)"

dev: up ## 🛠️ 啟動開發環境（別名）
	@echo "$(GREEN)🛠️ 開發環境已就緒$(NC)"

# =============================================================================
# 建構相關指令
# =============================================================================

build: ## 🚀 建構所有容器映像
	@echo "$(YELLOW)🔨 建構容器映像...$(NC)"
	$(DC) build

build-no-cache: ## 🛠️ 無快取建構所有容器映像
	@echo "$(YELLOW)🔨 無快取建構容器映像...$(NC)"
	$(DC) build --no-cache

build-backend: ## 🛠️ 僅建構後端映像
	@echo "$(YELLOW)🔨 建構後端映像...$(NC)"
	$(DC) build backend

build-frontend: ## 🛠️ 僅建構前端映像
	@echo "$(YELLOW)🔨 建構前端映像...$(NC)"
	$(DC) build frontend

rebuild: down build-no-cache up ## 🛠️ 完全重建並重啟
	@echo "$(GREEN)🔄 完全重建完成$(NC)"

# =============================================================================
# 個別服務管理
# =============================================================================

restart-backend: ## 🛠️ 重啟後端服務
	@echo "$(YELLOW)🔄 重啟後端服務...$(NC)"
	$(DC) restart backend
	@echo "$(GREEN)✅ 後端重啟完成$(NC)"

restart-frontend: ## 🛠️ 重啟前端服務
	@echo "$(YELLOW)🔄 重啟前端服務...$(NC)"
	$(DC) restart frontend
	@echo "$(GREEN)✅ 前端重啟完成$(NC)"

restart-db: ## 🗄️ 重啟資料庫服務
	@echo "$(YELLOW)🔄 重啟資料庫服務...$(NC)"
	$(DC) restart postgis
	@echo "$(GREEN)✅ 資料庫重啟完成$(NC)"

# =============================================================================
# 容器 Shell 訪問
# =============================================================================

shell-backend: ## 🛠️ 進入後端容器 shell
	@echo "$(CYAN)🐚 進入後端容器...$(NC)"
	$(DCE) backend bash

shell-frontend: ## 🛠️ 進入前端容器 shell
	@echo "$(CYAN)🐚 進入前端容器...$(NC)"
	$(DCE) frontend sh

shell-db: ## 🗄️ 進入資料庫容器 shell
	@echo "$(CYAN)🐚 進入資料庫容器...$(NC)"
	$(DCE) postgis bash

psql: ## 🗄️ 連接到 PostgreSQL 資料庫
	@echo "$(CYAN)🗄️ 連接資料庫...$(NC)"
	$(DCE) postgis psql -U sionna_user -d sionna_db

# =============================================================================
# 日誌和監控
# =============================================================================

logs: ## 📊 查看所有服務日誌
	$(DC) logs --tail=50

logs-follow: ## 📊 即時跟蹤所有服務日誌
	$(DC) logs -f

logs-backend: ## 📊 查看後端日誌
	$(DC) logs backend --tail=50

logs-frontend: ## 📊 查看前端日誌
	$(DC) logs frontend --tail=50

logs-db: ## 📊 查看資料庫日誌
	$(DC) logs postgis --tail=50

health: ## 📊 檢查服務健康狀態
	@echo "$(YELLOW)🏥 檢查服務健康狀態...$(NC)"
	@echo "$(CYAN)後端健康檢查:$(NC)"
	@curl -f http://localhost:8889/ping 2>/dev/null && echo "$(GREEN)✅ 後端正常$(NC)" || echo "$(RED)❌ 後端異常$(NC)"
	@echo "$(CYAN)前端健康檢查:$(NC)"
	@curl -f http://localhost:5174 2>/dev/null >/dev/null && echo "$(GREEN)✅ 前端正常$(NC)" || echo "$(RED)❌ 前端異常$(NC)"
	@echo "$(CYAN)資料庫健康檢查:$(NC)"
	@$(DCE) postgis pg_isready -U sionna_user -d sionna_db 2>/dev/null && echo "$(GREEN)✅ 資料庫正常$(NC)" || echo "$(RED)❌ 資料庫異常$(NC)"

# =============================================================================
# 資料庫管理
# =============================================================================

db-status: ## 🗄️ 檢查資料庫狀態
	@echo "$(YELLOW)🗄️ 檢查資料庫狀態...$(NC)"
	$(DCE) postgis pg_isready -U sionna_user -d sionna_db

db-reset: ## 🗄️ 重置資料庫（清除所有數據）
	@echo "$(RED)⚠️ 這將刪除所有資料庫數據！$(NC)"
	@echo "按 Ctrl+C 取消，或按 Enter 繼續..."
	@read
	@echo "$(YELLOW)🗄️ 重置資料庫...$(NC)"
	$(DC) down
	docker volume rm web-sionna_postgres_data 2>/dev/null || true
	$(DC) up -d postgis
	@echo "$(GREEN)✅ 資料庫重置完成$(NC)"

db-backup: ## 🗄️ 備份資料庫
	@echo "$(YELLOW)💾 備份資料庫...$(NC)"
	@mkdir -p ./backups
	$(DCE) postgis pg_dump -U sionna_user sionna_db > ./backups/backup_$$(date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✅ 資料庫備份完成$(NC)"

db-restore: ## 🗄️ 還原資料庫（需要指定備份文件）
	@echo "$(YELLOW)📂 可用備份文件:$(NC)"
	@ls -la ./backups/*.sql 2>/dev/null || echo "沒有找到備份文件"
	@echo "請輸入備份文件路徑:"
	@read BACKUP_FILE && \
	echo "$(YELLOW)🔄 還原資料庫...$(NC)" && \
	$(DCE) postgis psql -U sionna_user -d sionna_db < $$BACKUP_FILE && \
	echo "$(GREEN)✅ 資料庫還原完成$(NC)"

# =============================================================================
# 開發和測試
# =============================================================================

lint-frontend: ## 🛠️ 執行前端代碼檢查
	@echo "$(YELLOW)🔍 執行前端 linting...$(NC)"
	$(DCE) frontend npm run lint

lint-fix-frontend: ## 🛠️ 修復前端代碼格式問題
	@echo "$(YELLOW)🔧 修復前端代碼格式...$(NC)"
	$(DCE) frontend npm run lint -- --fix

test-backend: ## 🛠️ 執行後端測試
	@echo "$(YELLOW)🧪 執行後端測試...$(NC)"
	$(DCE) backend python -m pytest

test-frontend: ## 🛠️ 執行前端測試
	@echo "$(YELLOW)🧪 執行前端測試...$(NC)"
	$(DCE) frontend npm test

install-deps-frontend: ## 🛠️ 安裝前端依賴
	@echo "$(YELLOW)📦 安裝前端依賴...$(NC)"
	$(DCE) frontend npm install

install-deps-backend: ## 🛠️ 安裝後端依賴
	@echo "$(YELLOW)📦 安裝後端依賴...$(NC)"
	$(DCE) backend pip install -r requirements.txt

# =============================================================================
# 系統信息和診斷
# =============================================================================

system-info: ## 📊 顯示系統資源使用情況
	@echo "$(CYAN)💻 系統資源使用情況:$(NC)"
	@echo "$(YELLOW)Docker 容器:$(NC)"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" | grep sionna || echo "沒有運行的容器"
	@echo ""
	@echo "$(YELLOW)磁盤使用:$(NC)"
	@df -h | grep -E "(Filesystem|/$)" || true
	@echo ""
	@echo "$(YELLOW)記憶體使用:$(NC)"
	@free -h

ports: ## 📊 檢查端口使用情況
	@echo "$(CYAN)🔌 端口使用情況:$(NC)"
	@echo "$(YELLOW)專案相關端口:$(NC)"
	@netstat -tlpn 2>/dev/null | grep -E "(5174|8889|5433)" || echo "沒有發現專案端口被占用"

env-check: ## 📊 檢查環境配置
	@echo "$(CYAN)🔧 環境配置檢查:$(NC)"
	@test -f $(ENV_FILE) && echo "$(GREEN)✅ .env 文件存在$(NC)" || echo "$(RED)❌ .env 文件不存在$(NC)"
	@test -f $(COMPOSE_FILE) && echo "$(GREEN)✅ docker-compose.yml 存在$(NC)" || echo "$(RED)❌ docker-compose.yml 不存在$(NC)"

# =============================================================================
# 清理指令
# =============================================================================

clean: ## 🧹 清理所有 Docker 資源（保留資料）
	@echo "$(YELLOW)🧹 清理 Docker 資源...$(NC)"
	$(DC) down --rmi all --volumes --remove-orphans
	docker volume prune -f
	docker network prune -f
	@echo "$(GREEN)✅ 清理完成$(NC)"

clean-all: ## 🧹 深度清理（包含所有數據）
	@echo "$(RED)⚠️ 這將刪除所有容器、映像、卷和網路！$(NC)"
	@echo "按 Ctrl+C 取消，或按 Enter 繼續..."
	@read
	@echo "$(YELLOW)🧹 執行深度清理...$(NC)"
	$(DC) down --rmi all --volumes --remove-orphans
	docker system prune -af --volumes
	@echo "$(GREEN)✅ 深度清理完成$(NC)"

docker-clean: ## 🧹 清理未使用的 Docker 資源
	@echo "$(YELLOW)🧹 清理未使用的 Docker 資源...$(NC)"
	docker system prune -f
	docker volume prune -f
	docker network prune -f
	@echo "$(GREEN)✅ Docker 清理完成$(NC)"

# =============================================================================
# 生產環境相關
# =============================================================================

build-prod: ## 🛠️ 建構生產版本
	@echo "$(YELLOW)🏭 建構生產版本...$(NC)"
	$(DCE) frontend npm run build
	@echo "$(GREEN)✅ 生產版本建構完成$(NC)"

deploy-check: ## 📊 部署前檢查
	@echo "$(CYAN)🔍 部署前檢查...$(NC)"
	@echo "$(YELLOW)1. 環境檢查:$(NC)"
	@make env-check
	@echo "$(YELLOW)2. 服務健康檢查:$(NC)"
	@make health
	@echo "$(YELLOW)3. 端口檢查:$(NC)"
	@make ports
	@echo "$(GREEN)✅ 部署檢查完成$(NC)"

# =============================================================================
# API 測試
# =============================================================================

api-test: ## 📊 快速 API 測試
	@echo "$(CYAN)🧪 API 功能測試:$(NC)"
	@echo "$(YELLOW)測試後端健康狀態:$(NC)"
	@curl -s http://localhost:8889/ping && echo " $(GREEN)✅$(NC)" || echo " $(RED)❌$(NC)"
	@echo "$(YELLOW)測試設備 API:$(NC)"
	@curl -s http://localhost:8889/api/v1/devices/ | jq . > /dev/null 2>&1 && echo "設備列表 $(GREEN)✅$(NC)" || echo "設備列表 $(RED)❌$(NC)"
	@echo "$(YELLOW)測試場景 API:$(NC)"
	@curl -s http://localhost:8889/api/v1/simulations/scenes | jq . > /dev/null 2>&1 && echo "場景列表 $(GREEN)✅$(NC)" || echo "場景列表 $(RED)❌$(NC)"

# =============================================================================
# 特殊維護指令
# =============================================================================

fix-permissions: ## 🛠️ 修復檔案權限問題
	@echo "$(YELLOW)🔧 修復檔案權限...$(NC)"
	sudo chown -R $$USER:$$USER ./frontend/node_modules 2>/dev/null || true
	sudo chown -R $$USER:$$USER ./backend 2>/dev/null || true
	@echo "$(GREEN)✅ 權限修復完成$(NC)"

update-deps: ## 🛠️ 更新所有依賴
	@echo "$(YELLOW)📦 更新依賴套件...$(NC)"
	@echo "更新前端依賴..."
	$(DCE) frontend npm update
	@echo "更新後端依賴..."
	$(DCE) backend pip install --upgrade -r requirements.txt
	@echo "$(GREEN)✅ 依賴更新完成$(NC)"

# =============================================================================
# 別名和便捷指令
# =============================================================================

start: up ## 🚀 啟動系統（up 的別名）
stop: down ## 🚀 停止系統（down 的別名）
re: restart ## 🚀 重啟系統（restart 的別名）
l: logs ## 📊 查看日誌（logs 的別名）
s: status ## �� 查看狀態（status 的別名）
