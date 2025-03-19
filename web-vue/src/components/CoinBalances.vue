<template>
  <el-card class="coin-balances">
    <template #header>
      <div class="card-header">
        <span>币种持仓</span>
        <el-button size="small" @click="refreshData">刷新</el-button>
      </div>
    </template>
    
    <el-tabs v-model="activeTab" type="card">
      <el-tab-pane 
        v-for="coin in coins" 
        :key="coin" 
        :label="coin.toUpperCase()" 
        :name="coin"
      >
        <el-table 
          :data="paginatedExchangeData" 
          style="width: 100%" 
          :max-height="tableHeight"
          border
        >
          <el-table-column prop="exchange" label="交易所" width="120" />
          <el-table-column prop="pair" label="交易对" width="120" />
          <el-table-column prop="fee" label="费率" width="100">
            <template #default="scope">
              {{ scope.row.fee }}%
            </template>
          </el-table-column>
          <el-table-column prop="usdtBalance" label="USDT余额" width="120">
            <template #default="scope">
              {{ scope.row.usdtBalance }} USDT
            </template>
          </el-table-column>
          <el-table-column prop="coinBalance" :label="activeTab.toUpperCase() + '余额'" width="120">
            <template #default="scope">
              {{ scope.row.coinBalance }} {{ activeTab.toUpperCase() }}
            </template>
          </el-table-column>
          <el-table-column prop="frozenBalance" label="冻结余额" width="120">
            <template #default="scope">
              <span v-if="scope.row.frozenBalance && parseFloat(scope.row.frozenBalance) > 0" class="frozen-balance">
                {{ scope.row.frozenBalance }} {{ activeTab === 'usdt' ? 'USDT' : activeTab.toUpperCase() }}
              </span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="coinValue" label="币值" width="120">
            <template #default="scope">
              {{ scope.row.coinValue }} USDT
            </template>
          </el-table-column>
          <el-table-column label="买一/卖一" width="180">
            <template #default="scope">
              <div class="price-container">
                <div class="buy-price">买: {{ scope.row.buyPrice }}</div>
                <div class="sell-price">卖: {{ scope.row.sellPrice }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="价差" width="100">
            <template #default="scope">
              <span :class="getPriceClass(scope.row.priceDiff)">
                {{ scope.row.priceDiff }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 添加总持币价值显示 -->
        <div class="total-value-container" v-if="currentExchangeData.length > 0">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="总持币数量">
              <span class="value-highlight">{{ totalCoinAmount }} {{ activeTab.toUpperCase() }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="总冻结数量">
              <span class="value-highlight frozen-balance">{{ totalFrozenAmount }} {{ activeTab.toUpperCase() }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="总持币价值">
              <span class="value-highlight">{{ totalCoinValue }} USDT</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        
        <div class="pagination-container" v-if="currentExchangeData.length > pageSize">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="currentExchangeData.length"
            layout="prev, pager, next, jumper"
            @current-change="handlePageChange"
          />
        </div>
        
        <div v-if="currentExchangeData.length === 0" class="no-data">
          <el-empty description="暂无数据" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useStore } from 'vuex'

export default {
  name: 'CoinBalances',
  setup() {
    const store = useStore()
    const activeTab = ref('')
    const pageSize = ref(10) // 每页显示10条数据
    const currentPage = ref(1)
    const tableHeight = ref('400px')
    
    // 获取所有币种列表
    const coins = computed(() => {
      try {
        const allCoins = new Set()
        
        // 从未对冲持仓中获取币种
        const unhedgedPositions = store.state.unhedgedPositions || []
        unhedgedPositions.forEach(position => {
          if (position && position.coin) {
            allCoins.add(position.coin.toLowerCase())
          }
        })
        
        // 从交易记录中获取币种
        const trades = store.state.recentTrades || []
        trades.forEach(trade => {
          if (trade && trade.coin) {
            allCoins.add(trade.coin.toLowerCase())
          }
        })
        
        // 从深度数据中获取币种
        const depths = store.state.depths || {}
        Object.keys(depths).forEach(coin => {
          if (coin) {
            allCoins.add(coin.toLowerCase())
          }
        })
        
        // 从余额数据中获取币种
        const balances = store.state.balances || {}
        Object.keys(balances).forEach(exchange => {
          const exchangeBalance = balances[exchange] || {}
          Object.keys(exchangeBalance).forEach(coin => {
            if (coin && coin !== 'usdt' && exchangeBalance[coin] > 0) {
              allCoins.add(coin.toLowerCase())
            }
          })
        })
        
        // 从冻结余额数据中获取币种
        const frozenBalances = store.state.frozenBalances || {}
        Object.keys(frozenBalances).forEach(exchange => {
          const exchangeFrozen = frozenBalances[exchange] || {}
          Object.keys(exchangeFrozen).forEach(coin => {
            if (coin && exchangeFrozen[coin] > 0) {
              allCoins.add(coin.toLowerCase())
            }
          })
        })
        
        // 确保USDT始终在列表中
        allCoins.add('usdt')
        
        return Array.from(allCoins).sort()
      } catch (error) {
        console.error('Error computing coins list:', error)
        return []
      }
    })
    
    // 设置默认活动标签
    onMounted(() => {
      if (coins.value.length > 0) {
        activeTab.value = coins.value[0]
        // 使用nextTick确保DOM已更新
        nextTick(() => {
          updateTableHeight()
        })
      }
    })
    
    // 当切换标签时，重置页码
    watch(activeTab, () => {
      currentPage.value = 1
      // 重新计算表格高度
      nextTick(() => {
        updateTableHeight()
      })
    })
    
    // 获取指定币种的交易所数据
    const getExchangeDataForCoin = (coin) => {
      const result = []
      const unhedgedPositions = store.state.unhedgedPositions || []
      const depths = store.state.depths || {}
      const balances = store.state.balances || {}
      const frozenBalances = store.state.frozenBalances || {}
      
      // 获取该币种的所有交易所
      const exchanges = new Set()
      
      // 从持仓中获取交易所
      unhedgedPositions.forEach(position => {
        if (position.coin && position.coin.toLowerCase() === coin.toLowerCase()) {
          exchanges.add(position.exchange)
        }
      })
      
      // 从深度数据中获取交易所
      if (depths[coin]) {
        Object.keys(depths[coin]).forEach(exchange => {
          exchanges.add(exchange)
        })
      }
      
      // 从余额数据中获取交易所
      Object.keys(balances).forEach(exchange => {
        const exchangeBalance = balances[exchange] || {};
        Object.keys(exchangeBalance).forEach(c => {
          if (c.toLowerCase() === coin.toLowerCase() && exchangeBalance[c] > 0) {
            exchanges.add(exchange);
          }
        });
      });
      
      // 从冻结余额数据中获取交易所
      Object.keys(frozenBalances).forEach(exchange => {
        const exchangeFrozen = frozenBalances[exchange] || {};
        Object.keys(exchangeFrozen).forEach(c => {
          if (c.toLowerCase() === coin.toLowerCase() && exchangeFrozen[c] > 0) {
            exchanges.add(exchange);
          }
        });
      });
      
      // 为每个交易所创建数据行
      exchanges.forEach(exchange => {
        try {
          // 获取该交易所该币种的持仓
          const position = unhedgedPositions.find(p => 
            p && p.coin && p.coin.toLowerCase() === coin.toLowerCase() && 
            p.exchange === exchange
          );
          
          // 获取深度数据
          const coinDepths = depths[coin] || {};
          const depth = coinDepths[exchange];
          const buyPrice = depth && depth.asks && depth.asks.length > 0 ? depth.asks[0][0] : '-';
          const sellPrice = depth && depth.bids && depth.bids.length > 0 ? depth.bids[0][0] : '-';
          
          // 计算价差百分比
          let priceDiff = '-';
          if (buyPrice !== '-' && sellPrice !== '-') {
            priceDiff = ((sellPrice - buyPrice) / buyPrice * 100).toFixed(2);
          }
          
          // 获取账户余额
          const exchangeBalances = balances[exchange] || {};
          const usdtBalance = exchangeBalances.usdt || 0;
          const coinBalance = exchangeBalances[coin] || 0;
          
          // 获取冻结余额
          const exchangeFrozen = frozenBalances[exchange] || {};
          const frozenBalance = exchangeFrozen[coin] || 0;
          
          // 获取费率
          const fees = store.state.fees || {};
          const exchangeFees = fees[exchange] || {};
          const fee = exchangeFees[coin] || 0.1; // 默认0.1%
          
          // 计算币值
          let coinValue = 0;
          if (position && typeof position.value === 'number') {
            coinValue = position.value;
          } else if (coinBalance > 0 && buyPrice !== '-') {
            coinValue = coinBalance * parseFloat(buyPrice);
          }
          
          result.push({
            exchange,
            pair: `${coin.toUpperCase()}/USDT`,
            fee: (fee * 100).toFixed(2),
            usdtBalance: typeof usdtBalance === 'number' ? usdtBalance.toFixed(2) : '0.00',
            coinBalance: position && typeof position.amount === 'number' ? 
              position.amount.toFixed(6) : 
              (typeof coinBalance === 'number' ? coinBalance.toFixed(6) : '0.000000'),
            frozenBalance: typeof frozenBalance === 'number' && frozenBalance > 0 ? 
              frozenBalance.toFixed(6) : 
              null,
            coinValue: typeof coinValue === 'number' ? coinValue.toFixed(2) : '0.00',
            buyPrice: buyPrice !== '-' ? (typeof buyPrice === 'number' ? buyPrice.toFixed(6) : buyPrice) : '-',
            sellPrice: sellPrice !== '-' ? (typeof sellPrice === 'number' ? sellPrice.toFixed(6) : sellPrice) : '-',
            priceDiff
          });
        } catch (error) {
          console.error(`Error processing exchange ${exchange} for coin ${coin}:`, error);
        }
      });
      
      return result
    }
    
    // 当前标签页的交易所数据
    const currentExchangeData = computed(() => {
      if (!activeTab.value) return []
      return getExchangeDataForCoin(activeTab.value)
    })
    
    // 计算当前币种的总持币数量
    const totalCoinAmount = computed(() => {
      if (!currentExchangeData.value.length) return '0.000000'
      
      const total = currentExchangeData.value.reduce((sum, item) => {
        const amount = parseFloat(item.coinBalance) || 0
        return sum + amount
      }, 0)
      
      return total.toFixed(6)
    })
    
    // 计算当前币种的总冻结数量
    const totalFrozenAmount = computed(() => {
      if (!currentExchangeData.value.length) return '0.000000'
      
      const total = currentExchangeData.value.reduce((sum, item) => {
        const amount = item.frozenBalance ? parseFloat(item.frozenBalance) : 0
        return sum + amount
      }, 0)
      
      return total.toFixed(6)
    })
    
    // 计算当前币种的总持币价值
    const totalCoinValue = computed(() => {
      if (!currentExchangeData.value.length) return '0.00'
      
      const total = currentExchangeData.value.reduce((sum, item) => {
        const value = parseFloat(item.coinValue) || 0
        return sum + value
      }, 0)
      
      return total.toFixed(2)
    })
    
    // 分页后的交易所数据
    const paginatedExchangeData = computed(() => {
      const start = (currentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return currentExchangeData.value.slice(start, end)
    })
    
    // 更新表格高度
    const updateTableHeight = () => {
      const rows = Math.min(currentExchangeData.value.length, pageSize.value)
      // 每行约40px高，加上表头和边距
      tableHeight.value = rows > 0 ? `${rows * 40 + 60}px` : '400px'
    }
    
    // 处理分页变化
    const handlePageChange = (page) => {
      currentPage.value = page
    }
    
    // 刷新数据
    const refreshData = () => {
      store.dispatch('fetchBalances')
      // 刷新后重新计算表格高度
      nextTick(() => {
        updateTableHeight()
      })
    }
    
    // 获取价差的样式类
    const getPriceClass = (diff) => {
      if (diff === '-') return ''
      const value = parseFloat(diff)
      return {
        'price-up': value > 0,
        'price-down': value < 0
      }
    }
    
    return {
      activeTab,
      coins,
      pageSize,
      currentPage,
      currentExchangeData,
      paginatedExchangeData,
      totalCoinAmount,
      totalFrozenAmount,
      totalCoinValue,
      getExchangeDataForCoin,
      handlePageChange,
      refreshData,
      getPriceClass,
      tableHeight
    }
  }
}
</script>

<style scoped>
.coin-balances {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.price-container {
  display: flex;
  flex-direction: column;
}

.buy-price {
  color: #67C23A;
}

.sell-price {
  color: #F56C6C;
  margin-top: 4px;
}

.price-up {
  color: #67C23A;
}

.price-down {
  color: #F56C6C;
}

.frozen-balance {
  color: #E6A23C;  /* 使用橙色表示冻结余额 */
  font-weight: bold;
}

.no-data {
  padding: 20px 0;
}

.pagination-container {
  margin-top: 10px;
  text-align: center;
}

.total-value-container {
  margin: 15px 0;
  border-radius: 4px;
}

.value-highlight {
  font-weight: bold;
  font-size: 16px;
  color: #409EFF;
}

:deep(.el-table) {
  overflow: hidden;
}
</style> 