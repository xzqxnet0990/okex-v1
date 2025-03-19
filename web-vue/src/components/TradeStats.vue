<template>
  <el-card class="trade-stats">
    <template #header>
      <div class="card-header">
        <span>交易统计</span>
      </div>
    </template>

    <el-row :gutter="20">
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">总交易次数</div>
          <div class="value">{{ stats.totalTrades }}</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">成功交易</div>
          <div class="value success">{{ stats.successTrades }}</div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">失败交易</div>
          <div class="value failed">{{ stats.failedTrades }}</div>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <div class="stat-item">
          <div class="label">胜率</div>
          <div class="value" :class="winRateClass">{{ stats.winRate }}%</div>
        </div>
      </el-col>
    </el-row>

    <div class="trade-types mt-20">
      <h3>交易类型统计</h3>
      <el-table :data="tradeTypesList" style="width: 100%">
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="count" label="总次数" width="80" />
        <el-table-column prop="success" label="成功" width="80">
          <template #default="scope">
            <span class="success">{{ scope.row.success }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failed" label="失败" width="80">
          <template #default="scope">
            <span class="failed">{{ scope.row.failed }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="winRate" label="胜率" width="100">
          <template #default="scope">
            <span :class="getWinRateClass(scope.row.winRate)">{{ scope.row.winRate }}</span>
          </template>
        </el-table-column>
        <el-table-column label="交易量/收益" min-width="200">
          <template #default="scope">
            <div>{{ scope.row.volume }}</div>
            <div :class="getProfitClass(scope.row.profit)">{{ scope.row.profit }}</div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="trade-status-stats mt-20">
      <h3>交易状态统计</h3>
      <el-table :data="tradeStatusList" style="width: 100%">
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="total" label="总次数" width="80" />
        <el-table-column prop="success" label="成功" width="80">
          <template #default="scope">
            <span class="success">{{ scope.row.success }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failed" label="失败" width="80">
          <template #default="scope">
            <span class="failed">{{ scope.row.failed }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误" width="80">
          <template #default="scope">
            <span class="failed">{{ scope.row.error }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="cancelled" label="取消" width="80">
          <template #default="scope">
            <span class="warning">{{ scope.row.cancelled }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="pending" label="挂单中" width="80">
          <template #default="scope">
            <span class="warning">{{ scope.row.pending }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="successRate" label="成功率" width="100">
          <template #default="scope">
            <span :class="getWinRateClass(scope.row.successRate)">{{ scope.row.successRate }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="trade-profit-stats mt-20">
      <h3>交易盈亏统计</h3>
      <el-table :data="tradeProfitList" style="width: 100%">
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="totalProfit" label="总盈亏" width="120">
          <template #default="scope">
            <span :class="getProfitClass(scope.row.totalProfit)">{{ scope.row.totalProfit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="avgProfit" label="平均盈亏" width="120">
          <template #default="scope">
            <span :class="getProfitClass(scope.row.avgProfit)">{{ scope.row.avgProfit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="successProfit" label="成功盈亏" width="120">
          <template #default="scope">
            <span :class="getProfitClass(scope.row.successProfit)">{{ scope.row.successProfit }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failedProfit" label="失败盈亏" width="120">
          <template #default="scope">
            <span :class="getProfitClass(scope.row.failedProfit)">{{ scope.row.failedProfit }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </el-card>
</template>

<script>
import { computed } from 'vue'
import { useStore } from 'vuex'

export default {
  name: 'TradeStats',
  setup() {
    const store = useStore()
    
    const stats = computed(() => {
      console.log('TradeStats - formattedTradeStats:', store.getters.formattedTradeStats)
      return store.getters.formattedTradeStats
    })
    
    const winRateClass = computed(() => {
      const rate = parseFloat(stats.value.winRate)
      if (rate >= 60) return 'success'
      if (rate >= 40) return 'warning'
      return 'failed'
    })
    
    const tradeTypesList = computed(() => {
      const types = stats.value.tradeTypes || {}
      console.log('TradeStats - tradeTypes:', types)
      return Object.entries(types).map(([type, data]) => {
        console.log('TradeStats - type:', type, 'data:', data)
        return {
          type: getTradeTypeName(type),
          count: data.count || 0,
          success: data.success || 0,
          failed: data.failed || 0,
          winRate: data.formatted?.win_rate || '0.00%',
          volume: data.formatted?.total_volume || '0.0000',
          profit: data.formatted?.total_profit || '0.0000'
        }
      })
    })
    
    const tradeStatusList = computed(() => {
      const statusStats = stats.value.tradeStatusStats || {}
      console.log('TradeStats - tradeStatusStats:', statusStats)
      return Object.entries(statusStats).map(([type, data]) => {
        return {
          type: getTradeTypeName(type),
          total: data.total || 0,
          success: data.SUCCESS || 0,
          failed: data.FAILED || 0,
          error: data.ERROR || 0,
          cancelled: data.CANCELLED || 0,
          pending: data.PENDING || 0,
          executed: data.EXECUTED || 0,
          successRate: data.formatted?.success_rate || '0.00%'
        }
      })
    })
    
    const tradeProfitList = computed(() => {
      const statusStats = stats.value.tradeStatusStats || {}
      console.log('TradeStats - tradeProfitStats:', statusStats)
      return Object.entries(statusStats).map(([type, data]) => {
        return {
          type: getTradeTypeName(type),
          totalProfit: data.profit_stats?.total_profit ? data.profit_stats.total_profit.toFixed(4) : '0.0000',
          avgProfit: data.profit_stats?.avg_profit ? data.profit_stats.avg_profit.toFixed(4) : '0.0000',
          successProfit: data.profit_stats?.avg_success_profit ? data.profit_stats.avg_success_profit.toFixed(4) : '0.0000',
          failedProfit: data.profit_stats?.avg_failed_profit ? data.profit_stats.avg_failed_profit.toFixed(4) : '0.0000'
        }
      })
    })
    
    const getTradeTypeName = (type) => {
      const typeMap = {
        'arbitrage': '套利',
        'hedge_buy': '对冲买入',
        'hedge_sell': '对冲卖出',
        'hedge': '对冲',
        'pending_trade': '挂单',
        'pending': '挂单',
        'balance': '平衡',
        'migrate': '迁移',
        '套利(原)': '套利',
        '对冲买入(吃)': '对冲买入',
        '对冲卖出(吃)': '对冲卖出',
        '正向挂单': '正向挂单',
        '反向挂单': '反向挂单',
        '均衡': '均衡'
      }
      return typeMap[type.toLowerCase()] || type
    }
    
    const getWinRateClass = (rate) => {
      const value = parseFloat(rate)
      if (value >= 60) return 'success'
      if (value >= 40) return 'warning'
      return 'failed'
    }
    
    const getProfitClass = (profit) => {
      const value = parseFloat(profit)
      return value >= 0 ? 'success' : 'failed'
    }
    
    return {
      stats,
      winRateClass,
      tradeTypesList,
      tradeStatusList,
      tradeProfitList,
      getWinRateClass,
      getProfitClass
    }
  }
}
</script>

<style scoped>
.trade-stats {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-item {
  text-align: center;
  padding: 10px;
  background: #f5f7fa;
  border-radius: 4px;
}

.label {
  font-size: 14px;
  color: #606266;
  margin-bottom: 5px;
}

.value {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.success {
  color: #67C23A;
}

.warning {
  color: #E6A23C;
}

.failed {
  color: #F56C6C;
}

.mt-20 {
  margin-top: 20px;
}

.trade-types h3 {
  font-size: 16px;
  color: #303133;
  margin-bottom: 10px;
}

:deep(.el-table .cell) {
  text-align: center;
}

.trade-types .el-table {
  margin-top: 10px;
}

.trade-types .success {
  color: #67C23A;
  font-weight: bold;
}

.trade-types .warning {
  color: #E6A23C;
  font-weight: bold;
}

.trade-types .failed {
  color: #F56C6C;
  font-weight: bold;
}
</style> 