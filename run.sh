#!/bin/bash

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 输出带颜色的消息
info() {
    echo -e "${GREEN}[INFO] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
}

# 检查npm是否安装
check_npm() {
    if ! command -v npm &> /dev/null; then
        error "未找到 npm，请安装 npm"
        return 1
    fi
    return 0
}

# 设置虚拟环境
setup_venv() {
    info "正在设置 Python 虚拟环境..."
    if [ -d "venv" ]; then
        info "虚拟环境已存在，跳过创建"
    else
        info "创建虚拟环境..."
        python3 -m venv venv
        if [ $? -ne 0 ]; then
            error "创建虚拟环境失败"
            return 1
        fi
    fi
    
    info "激活虚拟环境..."
    source venv/bin/activate
    if [ $? -ne 0 ]; then
        error "激活虚拟环境失败"
        return 1
    fi
    
    info "安装后端依赖..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        error "安装后端依赖失败"
        return 1
    fi
    
    return 0
}

# 安装前端依赖
setup_frontend() {
    info "正在设置前端环境..."
    cd web-vue
    
    info "安装前端依赖..."
    npm install
    if [ $? -ne 0 ]; then
        error "安装前端依赖失败"
        cd ..
        return 1
    fi
    
    info "构建前端..."
    npm run build
    if [ $? -ne 0 ]; then
        error "构建前端失败"
        cd ..
        return 1
    fi
    
    cd ..
    return 0
}

# 运行应用
run_app() {
    info "正在启动应用..."
    
    # 确保虚拟环境已激活
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        source venv/bin/activate
    fi
    
    # 运行后端
    info "启动后端服务..."
    python examples/simulate_okex_strategy.py
}

# 主函数
main() {
    info "okex-v1 启动脚本"
    
    # 检查环境
    check_npm || exit 1
    
    # 设置后端环境
    setup_venv || exit 1
    
    # 设置前端环境
    setup_frontend || exit 1
    
    # 运行应用
    run_app
}

# 执行主函数
main 