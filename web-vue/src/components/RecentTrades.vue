<template>
  <el-card class="recent-trades">
    <template #header>
      <div class="card-header">
        <span>交易记录</span>
        <el-button v-if="recentTrades.length > 0" size="small" @click="clearFilters">清除筛选</el-button>
      </div>
    </template>

    <el-table
      :data="paginatedTrades"
      style="width: 100%"
      v-if="recentTrades.length"
      :max-height="tableHeight"
      @sort-change="handleSortChange"
      ref="tradesTable"
      border
    >
      <el-table-column prop="time" label="时间" width="100" sortable="custom" />
      <el-table-column prop="type" label="类型" width="120" sortable="custom" :filters="typeFilters" :filter-method="filterType" />
      <el-table-column prop="coin" label="币种" width="80" sortable="custom" :filters="coinFilters" :filter-method="filterCoin" />
      <el-table-column label="交易所" width="200" sortable="custom">
        <template #default="scope">
          {{ scope.row.buy_exchange }} → {{ scope.row.sell_exchange }}
        </template>
      </el-table-column>
      <el-table-column label="数量/价格" width="200">
        <template #default="scope">
          <div>{{ scope.row.formatted.amount }}</div>
          <div class="price-info">
            {{ scope.row.formatted.buy_price }} → {{ scope.row.formatted.sell_price }}
          </div>
        </template>
      </el-table-column>
      <el-table-column label="价差" width="100" sortable="custom" prop="price_diff_percent">
        <template #default="scope">
          <span :class="getPriceClass(scope.row.formatted.price_diff_percent)">
            {{ scope.row.formatted.price_diff_percent }}
          </span>
        </template>
      </el-table-column>
      <el-table-column label="收益" width="150" sortable="custom" prop="net_profit">
        <template #default="scope">
          <div>
            <el-tooltip effect="dark" placement="top">
              <template #content>
                毛利润: {{ scope.row.formatted.gross_profit }} USDT<br>
                手续费: {{ scope.row.formatted.fees }} USDT
              </template>
              <span :class="getProfitClass(scope.row.formatted.net_profit)">
                {{ scope.row.formatted.net_profit }} USDT
              </span>
            </el-tooltip>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100" :filters="statusFilters" :filter-method="filterStatus">
        <template #default="scope">
          <el-tag
            :type="getStatusType(scope.row.status)"
            size="small"
          >
            {{ scope.row.status }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>
    
    <div class="pagination-container" v-if="recentTrades.length > pageSize">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="filteredTrades.length"
        layout="prev, pager, next, jumper"
        @current-change="handleCurrentChange"
      />
    </div>
    
    <el-empty v-if="!recentTrades.length" description="暂无交易记录" />
  </el-card>
</template>

<script>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useStore } from 'vuex'

export default {
  name: 'RecentTrades',
  setup() {
    const store = useStore()
    const tradesTable = ref(null)
    const currentPage = ref(1)
    const pageSize = ref(10)
    const sortBy = ref({ prop: 'time', order: 'descending' })
    const activeTab = ref('all')
    const tableHeight = ref('400px')
    
    const recentTrades = computed(() => {
      console.log('RecentTrades - recentTrades:', store.state.recentTrades)
      return store.state.recentTrades || []
    })
    
    // 创建筛选器选项
    const typeFilters = computed(() => {
      const types = new Set(recentTrades.value.map(trade => trade.type))
      console.log('RecentTrades - typeFilters:', Array.from(types))
      return Array.from(types).map(type => ({ text: type, value: type }))
    })
    
    const coinFilters = computed(() => {
      const coins = new Set(recentTrades.value.map(trade => trade.coin))
      console.log('RecentTrades - coinFilters:', Array.from(coins))
      return Array.from(coins).map(coin => ({ text: coin, value: coin }))
    })
    
    const statusFilters = computed(() => {
      const statuses = new Set(recentTrades.value.map(trade => trade.status))
      console.log('RecentTrades - statusFilters:', Array.from(statuses))
      return Array.from(statuses).map(status => ({ text: status, value: status }))
    })
    
    // 筛选方法
    const filterType = (value, row) => {
      return row.type === value
    }
    
    const filterCoin = (value, row) => {
      return row.coin === value
    }
    
    const filterStatus = (value, row) => {
      return row.status === value
    }
    
    // 排序和筛选后的交易记录
    const filteredTrades = computed(() => {
      if (!tradesTable.value) return recentTrades.value
      
      // 获取当前表格的筛选条件
      let result = [...recentTrades.value]
      
      // 应用排序
      if (sortBy.value.prop) {
        result.sort((a, b) => {
          let valueA, valueB
          
          // 特殊处理某些字段
          if (sortBy.value.prop === 'net_profit') {
            valueA = parseFloat(a.formatted.net_profit)
            valueB = parseFloat(b.formatted.net_profit)
          } else if (sortBy.value.prop === 'price_diff_percent') {
            valueA = parseFloat(a.formatted.price_diff_percent)
            valueB = parseFloat(b.formatted.price_diff_percent)
          } else {
            valueA = a[sortBy.value.prop]
            valueB = b[sortBy.value.prop]
          }
          
          if (sortBy.value.order === 'ascending') {
            return valueA > valueB ? 1 : -1
          } else {
            return valueA < valueB ? 1 : -1
          }
        })
      }
      
      return result
    })
    
    // 分页后的交易记录
    const paginatedTrades = computed(() => {
      const start = (currentPage.value - 1) * pageSize.value
      const end = start + pageSize.value
      return filteredTrades.value.slice(start, end)
    })
    
    // 当交易记录变化时，重置到第一页
    watch(recentTrades, () => {
      currentPage.value = 1
    })
    
    // 处理分页变化
    const handleCurrentChange = (page) => {
      currentPage.value = page
    }
    
    // 处理排序变化
    const handleSortChange = (sort) => {
      sortBy.value = sort
    }
    
    // 清除所有筛选条件
    const clearFilters = () => {
      if (tradesTable.value) {
        tradesTable.value.clearFilter()
      }
    }
    
    const getPriceClass = (diff) => {
      const value = parseFloat(diff)
      return {
        'price-up': value > 0,
        'price-down': value < 0
      }
    }
    
    const getProfitClass = (profit) => {
      const value = parseFloat(profit)
      return {
        'profit-up': value > 0,
        'profit-down': value < 0
      }
    }
    
    const getStatusType = (status) => {
      switch (status) {
        case 'SUCCESS':
          return 'success'
        case 'PENDING':
          return 'warning'
        case 'FAILED':
          return 'danger'
        default:
          return 'info'
      }
    }
    
    // 当切换标签时，重置页码
    watch(activeTab, () => {
      currentPage.value = 1
      // 重新计算表格高度
      nextTick(() => {
        updateTableHeight()
      })
    })
    
    // 更新表格高度
    const updateTableHeight = () => {
      const rows = Math.min(filteredTrades.value.length, pageSize.value)
      // 每行约40px高，加上表头和边距
      tableHeight.value = rows > 0 ? `${rows * 40 + 60}px` : '400px'
    }
    
    // 在组件挂载后设置表格高度
    onMounted(() => {
      // 使用nextTick确保DOM已更新
      nextTick(() => {
        updateTableHeight()
      })
    })
    
    // 监听交易数据变化，更新表格高度
    watch(() => store.state.recentTrades, () => {
      nextTick(() => {
        updateTableHeight()
      })
    })
    
    return {
      recentTrades,
      filteredTrades,
      paginatedTrades,
      currentPage,
      pageSize,
      tradesTable,
      typeFilters,
      coinFilters,
      statusFilters,
      filterType,
      filterCoin,
      filterStatus,
      handleCurrentChange,
      handleSortChange,
      clearFilters,
      getPriceClass,
      getProfitClass,
      getStatusType,
      activeTab,
      tableHeight
    }
  }
}
</script>

<style scoped>
.recent-trades {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.price-info {
  font-size: 12px;
  color: #909399;
}

.price-up {
  color: #67C23A;
}

.price-down {
  color: #F56C6C;
}

.profit-up {
  color: #67C23A;
  font-weight: bold;
}

.profit-down {
  color: #F56C6C;
  font-weight: bold;
}

.pagination-container {
  margin-top: 20px;
  display: flex;
  justify-content: center;
}

:deep(.el-table .cell) {
  text-align: center;
}

:deep(.el-table) {
  overflow: hidden;
}
</style> 