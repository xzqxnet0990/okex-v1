<template>
  <el-card class="account-overview">
    <template #header>
      <div class="card-header">
        <span>账户概览</span>
        <span class="update-time">最后更新: {{ formatTime }}</span>
      </div>
    </template>
    <el-row :gutter="20">
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">初始余额</div>
          <div class="value-with-chart">
          <div class="value">{{ overview.initialBalance }} USDT</div>
            <div ref="initialBalanceChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">当前余额</div>
          <div class="value-with-chart">
          <div class="value">{{ overview.currentBalance }} USDT</div>
            <div ref="currentBalanceChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">总资产价值</div>
          <div class="value-with-chart">
          <div class="value">{{ overview.totalAssetValue }} USDT</div>
            <div ref="totalAssetValueChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20" class="mt-20">
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">总收益</div>
          <div class="value-with-chart">
            <div class="value" :class="profitClass">{{ overview.totalProfit }} USDT</div>
            <div ref="totalProfitChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">收益率</div>
          <div class="value-with-chart">
          <div class="value" :class="profitClass">{{ overview.profitRate }}%</div>
            <div ref="profitRateChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">总手续费</div>
          <div class="value-with-chart">
          <el-tooltip
            effect="dark"
            :content="`${overview.totalFees} USDT`"
            placement="top"
          >
              <div class="value negative">{{ formatNumber(parseFloat(overview.totalFees)) }} USDT</div>
          </el-tooltip>
            <div ref="totalFeesChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20" class="mt-20">
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">未对冲持仓价值</div>
          <div class="value-with-chart">
          <div class="value">{{ overview.unhedgedValue }} USDT</div>
            <div ref="unhedgedValueChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">期货空单价值</div>
          <div class="value-with-chart">
          <div class="value">{{ overview.shortPositionValue }} USDT</div>
            <div ref="shortPositionValueChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-item">
          <div class="label">冻结资产</div>
          <div class="value-with-chart">
            <div class="value frozen-value">{{ overview.frozenAssets }} USDT</div>
            <div ref="frozenAssetsChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
    </el-row>
    <el-row :gutter="20" class="mt-20">
      <el-col :span="24">
        <div class="stat-item">
          <div class="label">总持币价值</div>
          <div class="value-with-chart">
            <div class="value">{{ formatNumber(totalCoinValue) }} USDT</div>
            <div ref="totalCoinValueChart" class="mini-chart-container"></div>
          </div>
        </div>
      </el-col>
    </el-row>
  </el-card>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useStore } from 'vuex'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { 
  GridComponent, 
  TooltipComponent 
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

// 注册必要的组件
echarts.use([
  GridComponent, 
  TooltipComponent,
  LineChart, 
  CanvasRenderer
])

export default {
  name: 'AccountOverview',
  setup() {
    const store = useStore()
    
    // 图表容器引用
    const initialBalanceChart = ref(null)
    const currentBalanceChart = ref(null)
    const totalAssetValueChart = ref(null)
    const totalProfitChart = ref(null)
    const profitRateChart = ref(null)
    const totalFeesChart = ref(null)
    const unhedgedValueChart = ref(null)
    const shortPositionValueChart = ref(null)
    const totalCoinValueChart = ref(null)
    const frozenAssetsChart = ref(null)
    
    // 图表实例
    const charts = {
      initialBalance: null,
      currentBalance: null,
      totalAssetValue: null,
      totalProfit: null,
      profitRate: null,
      totalFees: null,
      unhedgedValue: null,
      shortPositionValue: null,
      totalCoinValue: null,
      frozenAssets: null
    }
    
    // 历史数据存储
    const historyData = ref({
      initialBalance: [],
      currentBalance: [],
      totalAssetValue: [],
      totalProfit: [],
      profitRate: [],
      totalFees: [],
      unhedgedValue: [],
      shortPositionValue: [],
      totalCoinValue: [],
      frozenAssets: []
    })
    
    // 最多保存的历史数据点数
    const MAX_HISTORY_POINTS = 20
    
    const overview = computed(() => store.getters.formattedAccountOverview)
    const lastUpdateTime = computed(() => store.state.lastUpdateTime)
    
    const formatTime = computed(() => {
      if (!lastUpdateTime.value) return '未更新'
      const date = new Date(lastUpdateTime.value)
      return date.toLocaleTimeString()
    })
    
    const profitClass = computed(() => {
      const profit = parseFloat(overview.value.totalProfit)
      return profit >= 0 ? 'positive' : 'negative'
    })
    
    // 计算总持币价值
    const totalCoinValue = computed(() => {
      // 从未对冲持仓中获取价值
      const unhedgedValue = store.state.positions.unhedgedPositions.reduce((sum, position) => {
        return sum + (position.value || 0)
      }, 0)
      
      // 从期货空单中获取价值
      const futuresValue = store.state.positions.futuresShortPositions.reduce((sum, position) => {
        return sum + (position.value || 0)
      }, 0)
      
      return unhedgedValue + futuresValue
    })
    
    // 更新历史数据
    const updateHistoryData = () => {
      // 更新各指标的历史数据
      const updateHistory = (key, value) => {
        if (historyData.value[key].length >= MAX_HISTORY_POINTS) {
          historyData.value[key].shift()
        }
        historyData.value[key].push(parseFloat(value))
      }
      
      updateHistory('initialBalance', overview.value.initialBalance)
      updateHistory('currentBalance', overview.value.currentBalance)
      updateHistory('totalAssetValue', overview.value.totalAssetValue)
      updateHistory('totalProfit', overview.value.totalProfit)
      updateHistory('profitRate', overview.value.profitRate)
      updateHistory('totalFees', overview.value.totalFees)
      updateHistory('unhedgedValue', overview.value.unhedgedValue)
      updateHistory('shortPositionValue', overview.value.shortPositionValue)
      updateHistory('totalCoinValue', totalCoinValue.value)
      updateHistory('frozenAssets', overview.value.frozenAssets)
    }
    
    // 初始化所有图表
    const initCharts = () => {
      // 初始化单个图表
      const initChart = (key, container) => {
        if (!container.value) return
        
        charts[key] = echarts.init(container.value)
        updateChart(key)
      }
      
      initChart('initialBalance', initialBalanceChart)
      initChart('currentBalance', currentBalanceChart)
      initChart('totalAssetValue', totalAssetValueChart)
      initChart('totalProfit', totalProfitChart)
      initChart('profitRate', profitRateChart)
      initChart('totalFees', totalFeesChart)
      initChart('unhedgedValue', unhedgedValueChart)
      initChart('shortPositionValue', shortPositionValueChart)
      initChart('totalCoinValue', totalCoinValueChart)
      initChart('frozenAssets', frozenAssetsChart)
    }
    
    // 更新所有图表
    const updateAllCharts = () => {
      Object.keys(charts).forEach(key => {
        if (charts[key]) {
          updateChart(key)
        }
      })
    }
    
    // 更新单个图表
    const updateChart = (key) => {
      const chart = charts[key]
      if (!chart) return
      
      const data = historyData.value[key]
      
      // 如果没有足够的数据，不显示图表
      if (data.length < 2) return
      
      // 计算趋势方向，用于确定颜色
      const trend = data[data.length - 1] - data[0]
      const isPositive = trend >= 0
      
      // 特殊处理手续费，手续费越低越好
      const isSpecialCase = key === 'totalFees'
      const color = isSpecialCase ? 
        (isPositive ? '#F56C6C' : '#67C23A') : 
        (isPositive ? '#67C23A' : '#F56C6C')
      
      // 添加一个零线参考点，确保图表显示正负区域
      const yAxisMin = Math.min(...data)
      const yAxisMax = Math.max(...data)
      const yAxisRange = yAxisMax - yAxisMin
      
      // 设置图表选项
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: (params) => {
            const value = params[0].value
            return key === 'profitRate' ? 
              `${value}%` : 
              `${value.toFixed(2)} USDT`
          },
          position: function (pos) {
            // 固定在顶部，避免遮挡图表
            return [pos[0], '10%']
          }
        },
        grid: {
          left: 0,
          right: 0,
          top: 5,
          bottom: 0
        },
        xAxis: {
          type: 'category',
          show: false,
          data: Array.from({ length: data.length }, (_, i) => i)
        },
        yAxis: {
          type: 'value',
          show: false,
          min: yAxisMin - yAxisRange * 0.1,  // 留出一些空间
          max: yAxisMax + yAxisRange * 0.1   // 留出一些空间
        },
        series: [
          {
            type: 'line',
            data: data,
            showSymbol: false,
            smooth: true,
            lineStyle: {
              width: 2,
              color: color
            },
            areaStyle: {
              opacity: 0.2,
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                {
                  offset: 0,
                  color: isPositive ? 
                    (isSpecialCase ? 'rgba(245, 108, 108, 0.8)' : 'rgba(103, 194, 58, 0.8)') : 
                    (isSpecialCase ? 'rgba(103, 194, 58, 0.8)' : 'rgba(245, 108, 108, 0.8)')
                },
                {
                  offset: 1,
                  color: isPositive ? 
                    (isSpecialCase ? 'rgba(245, 108, 108, 0.1)' : 'rgba(103, 194, 58, 0.1)') : 
                    (isSpecialCase ? 'rgba(103, 194, 58, 0.1)' : 'rgba(245, 108, 108, 0.1)')
                }
              ])
            }
          }
        ]
      })
    }
    
    // 处理窗口大小变化
    const handleResize = () => {
      Object.values(charts).forEach(chart => {
        if (chart) {
          chart.resize()
        }
      })
    }
    
    // 监听账户概览数据变化，更新历史数据和图表
    watch(() => [overview.value, totalCoinValue.value], () => {
      updateHistoryData()
      updateAllCharts()
    })
    
    // 组件挂载时初始化图表
    onMounted(() => {
      // 初始化历史数据
      updateHistoryData()
      
      // 初始化图表
      initCharts()
      
      // 添加窗口大小变化监听
      window.addEventListener('resize', handleResize)
      
      // 设置定时器，模拟数据变化
      const timer = setInterval(() => {
        // 随机波动当前值，用于演示图表效果
        const randomFluctuation = (value, percent = 0.02) => {
          const fluctuation = value * percent * (Math.random() * 2 - 1)
          return value + fluctuation
        }
        
        // 更新历史数据
        const currentData = {
          initialBalance: parseFloat(overview.value.initialBalance),
          currentBalance: randomFluctuation(parseFloat(overview.value.currentBalance)),
          totalAssetValue: randomFluctuation(parseFloat(overview.value.totalAssetValue)),
          totalProfit: randomFluctuation(parseFloat(overview.value.totalProfit)),
          profitRate: randomFluctuation(parseFloat(overview.value.profitRate)),
          totalFees: randomFluctuation(parseFloat(overview.value.totalFees), 0.01),
          unhedgedValue: randomFluctuation(parseFloat(overview.value.unhedgedValue)),
          shortPositionValue: randomFluctuation(parseFloat(overview.value.shortPositionValue)),
          totalCoinValue: randomFluctuation(parseFloat(totalCoinValue.value)),
          frozenAssets: randomFluctuation(parseFloat(overview.value.frozenAssets))
        }
        
        // 更新历史数据
        Object.keys(currentData).forEach(key => {
          if (historyData.value[key].length >= MAX_HISTORY_POINTS) {
            historyData.value[key].shift()
          }
          historyData.value[key].push(currentData[key])
        })
        
        // 更新图表
        updateAllCharts()
      }, 5000) // 每5秒更新一次
      
      // 组件卸载时清除定时器
      onUnmounted(() => {
        clearInterval(timer)
      })
    })
    
    // 组件卸载时销毁图表
    onUnmounted(() => {
      Object.values(charts).forEach(chart => {
        if (chart) {
          chart.dispose()
        }
      })
      
      window.removeEventListener('resize', handleResize)
    })
    
    const formatNumber = (num) => {
      return num.toLocaleString()
    }
    
    const formatPercent = (num) => {
      return (num * 100).toFixed(2) + '%'
    }
    
    return {
      overview,
      formatTime,
      profitClass,
      totalCoinValue,
      formatNumber,
      formatPercent,
      initialBalanceChart,
      currentBalanceChart,
      totalAssetValueChart,
      totalProfitChart,
      profitRateChart,
      totalFeesChart,
      unhedgedValueChart,
      shortPositionValueChart,
      totalCoinValueChart,
      frozenAssetsChart
    }
  }
}
</script>

<style scoped>
.account-overview {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.update-time {
  font-size: 0.9em;
  color: #999;
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
  cursor: default;
}

.value-with-chart {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.mini-chart-container {
  height: 40px;
  width: 100%;
  margin-top: 8px;
  border-radius: 4px;
  overflow: hidden;
}

.positive {
  color: #67C23A;
}

.negative {
  color: #F56C6C;
}

.mt-20 {
  margin-top: 20px;
}

:deep(.el-tooltip__trigger) {
  display: inline-block;
  width: 100%;
}

.statistic-content {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}

.suffix {
  font-size: 0.9em;
  color: #999;
}

.frozen-value {
  color: #E6A23C;
  font-weight: bold;
}
</style> 