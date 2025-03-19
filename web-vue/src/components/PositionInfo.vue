<template>
  <el-card class="position-info">
    <template #header>
      <div class="card-header">
        <span>持仓信息</span>
      </div>
    </template>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="未对冲持仓" name="unhedged">
        <el-table
          :data="paginatedUnhedgedPositions"
          style="width: 100%"
          v-if="positions.unhedgedPositions.length"
          :height="tableHeight"
        >
          <el-table-column prop="coin" label="币种" width="100" />
          <el-table-column prop="exchange" label="交易所" width="120" />
          <el-table-column prop="amount" label="数量">
            <template #default="scope">
              {{ formatNumber(scope.row.amount) }}
            </template>
          </el-table-column>
          <el-table-column prop="price" label="当前价格">
            <template #default="scope">
              {{ formatNumber(scope.row.price) }} USDT
            </template>
          </el-table-column>
          <el-table-column prop="value" label="价值">
            <template #default="scope">
              {{ formatNumber(scope.row.value) }} USDT
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 添加总持仓价值显示 -->
        <div class="total-value-container" v-if="positions.unhedgedPositions.length > 0">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="总持仓数量">
              <span class="value-highlight">{{ totalUnhedgedPositionsCount }} 个</span>
            </el-descriptions-item>
            <el-descriptions-item label="总持仓币种">
              <span class="value-highlight">{{ unhedgedCoinTypes }} 种</span>
            </el-descriptions-item>
            <el-descriptions-item label="总持仓价值">
              <span class="value-highlight">{{ totalUnhedgedValue }} USDT</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        
        <div class="pagination-container" v-if="positions.unhedgedPositions.length > pageSize">
          <el-pagination
            v-model:current-page="unhedgedCurrentPage"
            :page-size="pageSize"
            :total="positions.unhedgedPositions.length"
            layout="prev, pager, next, jumper"
            @current-change="handleUnhedgedPageChange"
          />
        </div>
        <el-empty v-if="!positions.unhedgedPositions.length" description="暂无未对冲持仓" />
      </el-tab-pane>

      <el-tab-pane label="期货空单" name="futures">
        <el-table
          :data="paginatedFuturesPositions"
          style="width: 100%"
          v-if="positions.futuresShortPositions.length"
          :height="tableHeight"
        >
          <el-table-column prop="coin" label="币种" width="100" />
          <el-table-column prop="exchange" label="交易所" width="120" />
          <el-table-column prop="size" label="数量">
            <template #default="scope">
              {{ formatNumber(scope.row.size) }}
            </template>
          </el-table-column>
          <el-table-column prop="price" label="当前价格">
            <template #default="scope">
              {{ formatNumber(scope.row.price) }} USDT
            </template>
          </el-table-column>
          <el-table-column prop="value" label="价值">
            <template #default="scope">
              {{ formatNumber(scope.row.value) }} USDT
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 添加总期货空单价值显示 -->
        <div class="total-value-container" v-if="positions.futuresShortPositions.length > 0">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="总空单数量">
              <span class="value-highlight">{{ totalFuturesPositionsCount }} 个</span>
            </el-descriptions-item>
            <el-descriptions-item label="总空单币种">
              <span class="value-highlight">{{ futuresCoinTypes }} 种</span>
            </el-descriptions-item>
            <el-descriptions-item label="总空单价值">
              <span class="value-highlight">{{ totalFuturesValue }} USDT</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        
        <div class="pagination-container" v-if="positions.futuresShortPositions.length > pageSize">
          <el-pagination
            v-model:current-page="futuresCurrentPage"
            :page-size="pageSize"
            :total="positions.futuresShortPositions.length"
            layout="prev, pager, next, jumper"
            @current-change="handleFuturesPageChange"
          />
        </div>
        <el-empty v-if="!positions.futuresShortPositions.length" description="暂无期货空单" />
      </el-tab-pane>
      
      <el-tab-pane label="挂单信息" name="pending">
        <el-table
          :data="paginatedPendingOrders"
          style="width: 100%"
          v-if="pendingOrders.length"
          :height="tableHeight"
        >
          <el-table-column prop="coin" label="币种" width="100" />
          <el-table-column prop="buy_exchange" label="买入交易所" width="120" />
          <el-table-column prop="sell_exchange" label="卖出交易所" width="120" />
          <el-table-column prop="amount" label="数量">
            <template #default="scope">
              {{ formatNumber(scope.row.amount) }}
            </template>
          </el-table-column>
          <el-table-column prop="buy_price" label="买入价格">
            <template #default="scope">
              {{ formatNumber(scope.row.buy_price) }} USDT
            </template>
          </el-table-column>
          <el-table-column prop="sell_price" label="卖出价格">
            <template #default="scope">
              {{ formatNumber(scope.row.sell_price) }} USDT
            </template>
          </el-table-column>
          <el-table-column prop="potential_profit" label="潜在利润">
            <template #default="scope">
              <span :class="{'profit-positive': scope.row.potential_profit > 0, 'profit-negative': scope.row.potential_profit < 0}">
                {{ formatNumber(scope.row.potential_profit) }} USDT
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="frozen_amount" label="冻结资金">
            <template #default="scope">
              <span class="frozen-amount">
                {{ calculateFrozenAmount(scope.row) }} USDT
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100">
            <template #default="scope">
              <el-tag :type="getStatusType(scope.row.status)">{{ getStatusText(scope.row.status) }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        
        <!-- 添加总挂单信息显示 -->
        <div class="total-value-container" v-if="pendingOrders.length > 0">
          <el-descriptions :column="3" border>
            <el-descriptions-item label="总挂单数量">
              <span class="value-highlight">{{ pendingOrders.length }} 个</span>
            </el-descriptions-item>
            <el-descriptions-item label="总挂单币种">
              <span class="value-highlight">{{ pendingCoinTypes }} 种</span>
            </el-descriptions-item>
            <el-descriptions-item label="总冻结资金">
              <span class="value-highlight frozen-value">{{ totalFrozenValue }} USDT</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>
        
        <div class="pagination-container" v-if="pendingOrders.length > pageSize">
          <el-pagination
            v-model:current-page="pendingCurrentPage"
            :page-size="pageSize"
            :total="pendingOrders.length"
            layout="prev, pager, next, jumper"
            @current-change="handlePendingPageChange"
          />
        </div>
        <el-empty v-if="!pendingOrders.length" description="暂无挂单" />
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>

<script>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useStore } from 'vuex'

export default {
  name: 'PositionInfo',
  setup() {
    const store = useStore()
    const activeTab = ref('unhedged')
    const pageSize = ref(10) // 每页显示10条数据
    const unhedgedCurrentPage = ref(1)
    const futuresCurrentPage = ref(1)
    const pendingCurrentPage = ref(1)
    const tableHeight = ref('300px')
    
    const positions = computed(() => {
      const pos = store.state.positions
      return {
        unhedgedPositions: pos.unhedgedPositions || [],
        futuresShortPositions: pos.futuresShortPositions || []
      }
    })
    
    // 获取挂单信息
    const pendingOrders = computed(() => {
      // 这里假设后端会通过WebSocket发送挂单信息
      // 如果后端没有实现，可以先返回空数组
      return store.state.pendingOrders || []
    })
    
    // 计算未对冲持仓的总数量
    const totalUnhedgedPositionsCount = computed(() => {
      return positions.value.unhedgedPositions.length
    })
    
    // 计算未对冲持仓的币种数量
    const unhedgedCoinTypes = computed(() => {
      const coins = new Set()
      positions.value.unhedgedPositions.forEach(position => {
        if (position.coin) {
          coins.add(position.coin.toLowerCase())
        }
      })
      return coins.size
    })
    
    // 计算未对冲持仓的总价值
    const totalUnhedgedValue = computed(() => {
      const total = positions.value.unhedgedPositions.reduce((sum, position) => {
        return sum + (position.value || 0)
      }, 0)
      return total.toFixed(2)
    })
    
    // 计算期货空单的总数量
    const totalFuturesPositionsCount = computed(() => {
      return positions.value.futuresShortPositions.length
    })
    
    // 计算期货空单的币种数量
    const futuresCoinTypes = computed(() => {
      const coins = new Set()
      positions.value.futuresShortPositions.forEach(position => {
        if (position.coin) {
          coins.add(position.coin.toLowerCase())
        }
      })
      return coins.size
    })
    
    // 计算期货空单的总价值
    const totalFuturesValue = computed(() => {
      const total = positions.value.futuresShortPositions.reduce((sum, position) => {
        return sum + (position.value || 0)
      }, 0)
      return total.toFixed(2)
    })
    
    // 计算挂单的币种数量
    const pendingCoinTypes = computed(() => {
      const coins = new Set()
      pendingOrders.value.forEach(order => {
        if (order.coin) {
          coins.add(order.coin.toLowerCase())
        }
      })
      return coins.size
    })
    
    // 计算总冻结资金
    const totalFrozenValue = computed(() => {
      const total = pendingOrders.value.reduce((sum, order) => {
        // 买入成本 = 数量 * 买入价格 * (1 + 手续费率)
        const buyCost = order.amount * order.buy_price * (1 + (order.buy_fee_rate || 0))
        return sum + buyCost
      }, 0)
      return total.toFixed(2)
    })
    
    // 计算分页后的未对冲持仓数据
    const paginatedUnhedgedPositions = computed(() => {
      const start = (unhedgedCurrentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return positions.value.unhedgedPositions.slice(start, end)
    })
    
    // 计算分页后的期货空单数据
    const paginatedFuturesPositions = computed(() => {
      const start = (futuresCurrentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return positions.value.futuresShortPositions.slice(start, end)
    })
    
    // 计算分页后的挂单数据
    const paginatedPendingOrders = computed(() => {
      const start = (pendingCurrentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return pendingOrders.value.slice(start, end)
    })
    
    // 处理未对冲持仓分页变化
    const handleUnhedgedPageChange = (page) => {
      unhedgedCurrentPage.value = page
    }
    
    // 处理期货空单分页变化
    const handleFuturesPageChange = (page) => {
      futuresCurrentPage.value = page
    }
    
    // 处理挂单分页变化
    const handlePendingPageChange = (page) => {
      pendingCurrentPage.value = page
    }
    
    // 获取挂单状态类型
    const getStatusType = (status) => {
      switch (status) {
        case 'PENDING':
          return 'warning'
        case 'FILLED':
          return 'success'
        case 'CANCELLED':
          return 'info'
        case 'FAILED':
          return 'danger'
        default:
          return 'info'
      }
    }
    
    // 获取挂单状态文本
    const getStatusText = (status) => {
      switch (status) {
        case 'PENDING':
          return '等待中'
        case 'FILLED':
          return '已成交'
        case 'CANCELLED':
          return '已取消'
        case 'FAILED':
          return '失败'
        default:
          return status
      }
    }
    
    const formatNumber = (num) => {
      if (num === undefined || num === null) return '0.0000'
      return Number(num).toFixed(4)
    }
    
    // 计算每个挂单的冻结资金
    const calculateFrozenAmount = (order) => {
      // 根据挂单类型计算冻结资金
      // 如果是正向挂单（先买后卖），冻结的是USDT
      if (order.type === 'PENDING_TRADE' || order.type === '正向挂单') {
        // 买入成本 = 数量 * 买入价格 * (1 + 手续费率)
        const buyCost = order.amount * order.buy_price * (1 + (order.buy_fee_rate || 0))
        return formatNumber(buyCost)
      } 
      // 如果是反向挂单（先卖后买），冻结的是币种
      else if (order.type === 'REVERSE_PENDING' || order.type === '反向挂单') {
        // 显示冻结的币种数量
        return `${formatNumber(order.amount)} ${order.coin}`
      }
      // 默认情况
      else {
        // 买入成本 = 数量 * 买入价格 * (1 + 手续费率)
        const buyCost = order.amount * order.buy_price * (1 + (order.buy_fee_rate || 0))
        return formatNumber(buyCost)
      }
    }
    
    // 在组件挂载后设置表格高度
    onMounted(() => {
      // 使用nextTick确保DOM已更新
      nextTick(() => {
        // 根据数据量动态设置表格高度
        const maxRows = Math.max(
          Math.min(positions.value.unhedgedPositions.length, pageSize.value),
          Math.min(positions.value.futuresShortPositions.length, pageSize.value),
          Math.min(pendingOrders.value.length, pageSize.value)
        )
        // 每行约40px高，加上表头和边距
        tableHeight.value = maxRows > 0 ? `${maxRows * 40 + 60}px` : '300px'
      })
    })
    
    return {
      activeTab,
      positions,
      pendingOrders,
      pageSize,
      unhedgedCurrentPage,
      futuresCurrentPage,
      pendingCurrentPage,
      paginatedUnhedgedPositions,
      paginatedFuturesPositions,
      paginatedPendingOrders,
      totalUnhedgedPositionsCount,
      unhedgedCoinTypes,
      totalUnhedgedValue,
      totalFuturesPositionsCount,
      futuresCoinTypes,
      totalFuturesValue,
      pendingCoinTypes,
      totalFrozenValue,
      handleUnhedgedPageChange,
      handleFuturesPageChange,
      handlePendingPageChange,
      getStatusType,
      getStatusText,
      formatNumber,
      calculateFrozenAmount,
      tableHeight
    }
  }
}
</script>

<style scoped>
.position-info {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

.total-value-container {
  margin-top: 20px;
}

.value-highlight {
  font-weight: bold;
  color: #409EFF;
}

.frozen-value {
  color: #E6A23C !important;
}

.frozen-amount {
  color: #E6A23C;
  font-weight: bold;
}

.profit-positive {
  color: #67C23A;
  font-weight: bold;
}

.profit-negative {
  color: #F56C6C;
  font-weight: bold;
}
</style> 