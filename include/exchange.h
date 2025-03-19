// exchange.h
#ifndef EXCHANGE_H
#define EXCHANGE_H

#include <stdint.h>

// 交易所类型枚举
typedef enum {
    EXCHANGE_OKEX,
    EXCHANGE_BINANCE,
    EXCHANGE_HUOBI,
    EXCHANGE_MEXC,
    EXCHANGE_BYBIT,
    // ... 其他交易所
} exchange_type_t;

// 账户信息结构
typedef struct {
    double balance;       // USDT余额
    double stocks;        // 币种数量
    double frozen_balance;// 冻结USDT
    double frozen_stocks; // 冻结币种
} account_info_t;

// 深度数据结构
typedef struct {
    struct {
        double price;
        double amount;
    } asks[10];  // 卖单深度
    struct {
        double price;
        double amount;
    } bids[10];  // 买单深度
    int ask_count;
    int bid_count;
} depth_info_t;

// 交易所配置结构
typedef struct {
    exchange_type_t type;
    char api_key[128];
    char api_secret[128];
    char passphrase[64];  // 某些交易所需要
    char endpoint[256];   // REST API endpoint
    char ws_endpoint[256];// WebSocket endpoint
    double maker_fee;     // maker费率
    double taker_fee;     // taker费率
} exchange_config_t;

// 交易所接口结构
typedef struct exchange_interface {
    // 初始化函数
    int (*init)(struct exchange_interface* self, const exchange_config_t* config);
    
    // 账户相关
    int (*get_account)(struct exchange_interface* self, account_info_t* account);
    
    // 市场数据
    int (*get_depth)(struct exchange_interface* self, const char* symbol, depth_info_t* depth);
    
    // 交易接口
    int (*place_order)(struct exchange_interface* self, const char* symbol, 
                      int is_buy, double price, double amount);
    
    // 清理函数
    void (*cleanup)(struct exchange_interface* self);
    
    // 私有数据
    void* private_data;
} exchange_interface_t;

// 创建交易所接口实例
exchange_interface_t* create_exchange(exchange_type_t type);

// 销毁交易所接口实例
void destroy_exchange(exchange_interface_t* exchange);

#endif // EXCHANGE_H 