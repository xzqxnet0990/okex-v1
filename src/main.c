#include <stdio.h>
#include <stdlib.h>
#include <signal.h>
#include "exchange.h"
#include "strategy.h"
#include "webserver.h"

// 全局变量
static int g_running = 1;
static strategy_interface_t* g_strategy = NULL;
static exchange_interface_t* g_exchange = NULL;
static webserver_interface_t* g_webserver = NULL;

// 信号处理函数
static void handle_signal(int sig) {
    Logf("Received signal %d, shutting down...\n", sig);
    g_running = 0;
}

// 初始化框架
static int init_framework(void) {
    // 创建交易所实例
    exchange_config_t ex_config = {
        .type = EXCHANGE_OKEX,
        .maker_fee = 0.001,
        .taker_fee = 0.002
    };
    
    g_exchange = create_exchange(EXCHANGE_OKEX);
    if (!g_exchange || g_exchange->init(g_exchange, &ex_config) != 0) {
        Logf("Failed to initialize exchange\n");
        return -1;
    }
    
    // 创建策略实例
    strategy_config_t st_config = {
        .name = "ArbitrageStrategy",
        .version = "1.0.0",
        .initial_balance = 10000.0,
        .risk_limit = 1000.0,
        .max_position = 100.0,
        .min_profit = 0.001
    };
    
    g_strategy = create_strategy("arbitrage");
    if (!g_strategy || g_strategy->init(g_strategy, &st_config) != 0) {
        Logf("Failed to initialize strategy\n");
        return -1;
    }
    
    // 创建Web服务实例
    webserver_config_t web_config = {
        .port = 8080,
        .host = "0.0.0.0",
        .max_connections = 100,
        .enable_ssl = 0
    };
    
    g_webserver = create_webserver();
    if (!g_webserver || g_webserver->init(g_webserver, &web_config) != 0) {
        Logf("Failed to initialize web server\n");
        return -1;
    }
    
    // 注册策略到Web服务
    g_webserver->register_strategy(g_webserver, g_strategy);
    
    return 0;
}

// 清理资源
static void cleanup(void) {
    if (g_webserver) {
        g_webserver->cleanup(g_webserver);
        destroy_webserver(g_webserver);
    }
    
    if (g_strategy) {
        g_strategy->cleanup(g_strategy);
        destroy_strategy(g_strategy);
    }
    
    if (g_exchange) {
        g_exchange->cleanup(g_exchange);
        destroy_exchange(g_exchange);
    }
}

// 主循环
static void main_loop(void) {
    depth_info_t depth;
    account_info_t account;
    
    while (g_running) {
        // 获取市场深度数据
        if (g_exchange->get_depth(g_exchange, "BTC_USDT", &depth) == 0) {
            g_strategy->on_tick(g_strategy, &depth, 1);
        }
        
        // 获取账户信息
        if (g_exchange->get_account(g_exchange, &account) == 0) {
            g_strategy->on_account(g_strategy, &account);
        }
        
        // 更新策略统计
        strategy_stats_t stats;
        g_strategy->get_stats(g_strategy, &stats);
        
        // 通过WebSocket广播状态更新
        char status[256];
        snLogf(status, sizeof(status),
                "{\"total_profit\":%.2f,\"daily_profit\":%.2f,\"trades\":%d}",
                stats.total_profit, stats.daily_profit, stats.total_trades);
        g_webserver->broadcast(g_webserver, status);
        
        // 休眠一段时间
        usleep(100000);  // 100ms
    }
}

int main(void) {
    // 设置信号处理
    signal(SIGINT, handle_signal);
    signal(SIGTERM, handle_signal);
    
    // 初始化框架
    if (init_framework() != 0) {
        Logf("Framework initialization failed\n");
        cleanup();
        return 1;
    }
    
    // 启动Web服务
    if (g_webserver->start(g_webserver) != 0) {
        Logf("Failed to start web server\n");
        cleanup();
        return 1;
    }
    
    // 启动策略
    if (g_strategy->start(g_strategy) != 0) {
        Logf("Failed to start strategy\n");
        cleanup();
        return 1;
    }
    
    Logf("Quantitative trading framework started\n");
    
    // 运行主循环
    main_loop();
    
    // 清理资源
    cleanup();
    
    return 0;
} 