#ifndef STRATEGY_H
#define STRATEGY_H

#include "exchange.h"
#include <time.h>

// 策略状态枚举
typedef enum {
    STRATEGY_INIT,
    STRATEGY_RUNNING,
    STRATEGY_PAUSED,
    STRATEGY_STOPPED,
    STRATEGY_ERROR
} strategy_state_t;

// 策略配置结构
typedef struct {
    char name[64];
    char version[32];
    double initial_balance;
    double risk_limit;
    double max_position;
    double min_profit;
    int max_trades_per_day;
    time_t start_time;
    time_t end_time;
} strategy_config_t;

// 策略统计信息
typedef struct {
    double total_profit;
    double daily_profit;
    int total_trades;
    int successful_trades;
    double max_drawdown;
    double win_rate;
    time_t last_trade_time;
} strategy_stats_t;

// 策略接口结构
typedef struct strategy_interface {
    // 初始化函数
    int (*init)(struct strategy_interface* self, const strategy_config_t* config);
    
    // 策略主循环
    int (*on_tick)(struct strategy_interface* self, const depth_info_t* depths, int depth_count);
    
    // 账户更新回调
    void (*on_account)(struct strategy_interface* self, const account_info_t* account);
    
    // 订单更新回调
    void (*on_order)(struct strategy_interface* self, const char* symbol, 
                     int is_buy, double price, double amount, int is_finished);
    
    // 获取策略状态
    strategy_state_t (*get_state)(struct strategy_interface* self);
    
    // 获取策略统计
    void (*get_stats)(struct strategy_interface* self, strategy_stats_t* stats);
    
    // 启动策略
    int (*start)(struct strategy_interface* self);
    
    // 停止策略
    int (*stop)(struct strategy_interface* self);
    
    // 清理函数
    void (*cleanup)(struct strategy_interface* self);
    
    // 私有数据
    void* private_data;
} strategy_interface_t;

// 创建策略实例
strategy_interface_t* create_strategy(const char* name);

// 销毁策略实例
void destroy_strategy(strategy_interface_t* strategy);

#endif // STRATEGY_H 