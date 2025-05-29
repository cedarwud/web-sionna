#!/bin/bash

# =============================================================================
# Sionna RT 無線電模擬系統 - 自動化設置腳本
# =============================================================================
# 這個腳本會自動檢查環境、配置系統並啟動所有服務
# 使用方式: bash setup.sh
# =============================================================================

set -e  # 遇到錯誤時停止執行

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# 專案配置
PROJECT_NAME="Sionna RT 無線電模擬系統"
MIN_DOCKER_VERSION="20.10.0"
MIN_COMPOSE_VERSION="2.0.0"

# =============================================================================
# 實用函數
# =============================================================================

# 打印帶顏色的訊息
print_info() {
    echo -e "${CYAN}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_header() {
    echo -e "${PURPLE}========================================${NC}"
    echo -e "${WHITE}  $1${NC}"
    echo -e "${PURPLE}========================================${NC}"
    echo ""
}

# 檢查指令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 版本比較函數
version_compare() {
    if [[ $1 == $2 ]]; then
        return 0
    fi
    local IFS=.
    local i ver1=($1) ver2=($2)
    for ((i=${#ver1[@]}; i<${#ver2[@]}; i++)); do
        ver1[i]=0
    done
    for ((i=0; i<${#ver1[@]}; i++)); do
        if [[ -z ${ver2[i]} ]]; then
            ver2[i]=0
        fi
        if ((10#${ver1[i]} > 10#${ver2[i]})); then
            return 1
        fi
        if ((10#${ver1[i]} < 10#${ver2[i]})); then
            return 2
        fi
    done
    return 0
}

# =============================================================================
# 環境檢查
# =============================================================================

check_system_requirements() {
    print_header "檢查系統需求"
    
    # 檢查作業系統
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        print_success "作業系統: Linux ✓"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        print_success "作業系統: macOS ✓"
    else
        print_warning "未測試的作業系統: $OSTYPE"
    fi
    
    # 檢查記憶體
    if command_exists free; then
        TOTAL_MEM=$(free -m | awk 'NR==2{printf "%d", $2}')
        if [[ $TOTAL_MEM -gt 8000 ]]; then
            print_success "記憶體: ${TOTAL_MEM}MB ✓"
        else
            print_warning "記憶體: ${TOTAL_MEM}MB (建議至少 8GB)"
        fi
    fi
    
    # 檢查磁碟空間
    AVAILABLE_SPACE=$(df . | tail -1 | awk '{print $4}')
    AVAILABLE_GB=$((AVAILABLE_SPACE / 1024 / 1024))
    if [[ $AVAILABLE_GB -gt 10 ]]; then
        print_success "可用磁碟空間: ${AVAILABLE_GB}GB ✓"
    else
        print_warning "可用磁碟空間: ${AVAILABLE_GB}GB (建議至少 10GB)"
    fi
    
    echo ""
}

check_docker() {
    print_header "檢查 Docker 環境"
    
    # 檢查 Docker 是否安裝
    if ! command_exists docker; then
        print_error "Docker 未安裝！"
        print_info "請訪問 https://docs.docker.com/get-docker/ 安裝 Docker"
        exit 1
    fi
    
    # 檢查 Docker 版本
    DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    version_compare $DOCKER_VERSION $MIN_DOCKER_VERSION
    case $? in
        0|1) print_success "Docker 版本: $DOCKER_VERSION ✓" ;;
        2) print_warning "Docker 版本: $DOCKER_VERSION (建議 $MIN_DOCKER_VERSION+)" ;;
    esac
    
    # 檢查 Docker 是否運行
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker 服務未運行！"
        print_info "請執行: sudo systemctl start docker"
        exit 1
    fi
    print_success "Docker 服務運行中 ✓"
    
    # 檢查 Docker Compose
    if ! command_exists "docker compose"; then
        print_error "Docker Compose 未安裝！"
        print_info "請安裝 Docker Compose v2"
        exit 1
    fi
    
    COMPOSE_VERSION=$(docker compose version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    version_compare $COMPOSE_VERSION $MIN_COMPOSE_VERSION
    case $? in
        0|1) print_success "Docker Compose 版本: $COMPOSE_VERSION ✓" ;;
        2) print_warning "Docker Compose 版本: $COMPOSE_VERSION (建議 $MIN_COMPOSE_VERSION+)" ;;
    esac
    
    echo ""
}

check_ports() {
    print_header "檢查端口可用性"
    
    PORTS=(5174 8889 5433)
    PORT_NAMES=("前端" "後端" "資料庫")
    
    for i in "${!PORTS[@]}"; do
        PORT="${PORTS[$i]}"
        NAME="${PORT_NAMES[$i]}"
        
        if netstat -tlpn 2>/dev/null | grep -q ":$PORT "; then
            print_warning "端口 $PORT ($NAME) 已被占用"
        else
            print_success "端口 $PORT ($NAME) 可用 ✓"
        fi
    done
    
    echo ""
}

# =============================================================================
# 環境配置
# =============================================================================

setup_environment() {
    print_header "設置環境配置"
    
    # 檢查並創建 .env 文件
    if [[ ! -f .env ]]; then
        if [[ -f env.example ]]; then
            print_info "從 env.example 創建 .env 文件..."
            cp env.example .env
            print_success ".env 文件已創建 ✓"
        else
            print_info "創建預設 .env 文件..."
            cat > .env << EOF
# Sionna RT 系統配置
POSTGRES_USER=sionna_user
POSTGRES_PASSWORD=sionna_password_2024
POSTGRES_DB=sionna_db
POSTGRES_PORT=5433
BACKEND_PORT=8889
FRONTEND_PORT=5174
APP_ENV=development
DEFAULT_SCENE=nycu
LOG_LEVEL=INFO
ENABLE_DOCS=true
ENABLE_CORS=true
CORS_ORIGINS=http://localhost:5174,http://localhost:3000
EOF
            print_success "預設 .env 文件已創建 ✓"
        fi
    else
        print_success ".env 文件已存在 ✓"
    fi
    
    # 創建必要的目錄
    print_info "創建必要的目錄..."
    mkdir -p ./backups
    mkdir -p ./logs
    print_success "目錄結構已準備 ✓"
    
    echo ""
}

# =============================================================================
# 系統部署
# =============================================================================

deploy_system() {
    print_header "部署 $PROJECT_NAME"
    
    print_info "清理舊容器和映像..."
    docker compose down --remove-orphans 2>/dev/null || true
    
    print_info "建構容器映像..."
    if docker compose build; then
        print_success "容器映像建構完成 ✓"
    else
        print_error "容器映像建構失敗！"
        exit 1
    fi
    
    print_info "啟動服務..."
    if docker compose up -d; then
        print_success "服務啟動完成 ✓"
    else
        print_error "服務啟動失敗！"
        exit 1
    fi
    
    echo ""
}

# =============================================================================
# 健康檢查
# =============================================================================

wait_for_services() {
    print_header "等待服務就緒"
    
    print_info "等待資料庫服務..."
    for i in {1..30}; do
        if docker compose exec -T postgis pg_isready -U sionna_user -d sionna_db >/dev/null 2>&1; then
            print_success "資料庫服務就緒 ✓"
            break
        fi
        if [[ $i -eq 30 ]]; then
            print_error "資料庫服務啟動超時！"
            exit 1
        fi
        echo -n "."
        sleep 2
    done
    
    print_info "等待後端服務..."
    for i in {1..60}; do
        if curl -f http://localhost:8889/ping >/dev/null 2>&1; then
            print_success "後端服務就緒 ✓"
            break
        fi
        if [[ $i -eq 60 ]]; then
            print_error "後端服務啟動超時！"
            exit 1
        fi
        echo -n "."
        sleep 2
    done
    
    print_info "等待前端服務..."
    for i in {1..30}; do
        if curl -f http://localhost:5174 >/dev/null 2>&1; then
            print_success "前端服務就緒 ✓"
            break
        fi
        if [[ $i -eq 30 ]]; then
            print_warning "前端服務可能需要更多時間啟動"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    echo ""
}

verify_deployment() {
    print_header "驗證部署"
    
    # 檢查容器狀態
    print_info "檢查容器狀態..."
    if docker compose ps | grep -q "Up"; then
        print_success "容器運行正常 ✓"
    else
        print_error "部分容器未正常運行！"
        docker compose ps
    fi
    
    # 檢查 API 端點
    print_info "檢查 API 端點..."
    if curl -s http://localhost:8889/ping | grep -q "pong"; then
        print_success "後端 API 正常 ✓"
    else
        print_warning "後端 API 檢查失敗"
    fi
    
    if curl -s http://localhost:8889/api/v1/devices/ | grep -q "\[\]"; then
        print_success "設備 API 正常 ✓"
    else
        print_warning "設備 API 檢查失敗"
    fi
    
    echo ""
}

# =============================================================================
# 完成訊息
# =============================================================================

show_completion_message() {
    print_header "🎉 部署完成！"
    
    echo -e "${GREEN}$PROJECT_NAME 已成功部署並運行！${NC}"
    echo ""
    echo -e "${CYAN}📱 前端介面:${NC} http://localhost:5174"
    echo -e "${CYAN}🔧 後端 API:${NC} http://localhost:8889"
    echo -e "${CYAN}📚 API 文檔:${NC} http://localhost:8889/docs"
    echo -e "${CYAN}🗄️ 資料庫:${NC} localhost:5433"
    echo ""
    echo -e "${YELLOW}常用指令:${NC}"
    echo -e "  ${CYAN}make help${NC}      - 查看所有可用指令"
    echo -e "  ${CYAN}make logs${NC}      - 查看服務日誌"
    echo -e "  ${CYAN}make restart${NC}   - 重啟所有服務"
    echo -e "  ${CYAN}make down${NC}      - 停止所有服務"
    echo -e "  ${CYAN}make shell-backend${NC} - 進入後端容器"
    echo ""
    echo -e "${GREEN}開始使用您的 Sionna RT 模擬系統吧！${NC}"
    echo ""
}

# =============================================================================
# 錯誤處理
# =============================================================================

cleanup_on_error() {
    print_error "安裝過程中發生錯誤！"
    print_info "清理中..."
    docker compose down --remove-orphans 2>/dev/null || true
    exit 1
}

trap cleanup_on_error ERR

# =============================================================================
# 主函數
# =============================================================================

main() {
    clear
    print_header "🚀 $PROJECT_NAME 自動化設置"
    
    print_info "開始自動化設置流程..."
    echo ""
    
    # 執行設置步驟
    check_system_requirements
    check_docker
    check_ports
    setup_environment
    deploy_system
    wait_for_services
    verify_deployment
    show_completion_message
}

# =============================================================================
# 腳本入口點
# =============================================================================

# 檢查是否以 root 身份運行
if [[ $EUID -eq 0 ]]; then
    print_warning "不建議以 root 身份運行此腳本"
    read -p "是否繼續？[y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 確認運行
echo -e "${YELLOW}準備設置 $PROJECT_NAME${NC}"
echo -e "${CYAN}這將會：${NC}"
echo "  1. 檢查系統需求和 Docker 環境"
echo "  2. 設置環境配置文件"
echo "  3. 建構和啟動所有服務"
echo "  4. 驗證部署狀態"
echo ""
read -p "是否繼續？[Y/n] " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    print_info "設置已取消"
    exit 0
fi

# 執行主函數
main 