<template>
  <el-card class="profit-chart">
    <template #header>
      <div class="card-header">
        <span>收益趋势</span>
        <el-tooltip content="显示最近交易的累计收益趋势" placement="top">
          <el-icon><QuestionFilled /></el-icon>
        </el-tooltip>
      </div>
    </template>
    <div ref="chartContainer" class="chart-container"></div>
  </el-card>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useStore } from 'vuex'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { 
  TitleComponent, 
  TooltipComponent, 
  GridComponent, 
  LegendComponent,
  ToolboxComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { QuestionFilled } from '@element-plus/icons-vue'

// 注册必要的组件
echarts.use([
  TitleComponent, 
  TooltipComponent, 
  GridComponent, 
  LegendComponent,
  ToolboxComponent,
  LineChart, 
  CanvasRenderer
])

export default {
  name: 'ProfitChart',
  components: {
    QuestionFilled
  },
  setup() {
    const store = useStore()
    const chartContainer = ref(null)
    let chart = null
    
    // 获取交易数据
    const trades = computed(() => {
      console.log('ProfitChart - recentTrades:', store.state.recentTrades)
      return store.state.recentTrades || []
    })
    
    // 计算累计收益数据
    const profitData = computed(() => {
      // 检查交易记录是否为空
      if (!trades.value || trades.value.length === 0) {
        console.log('ProfitChart - No trades data available');
        return [];
      }
      
      // 检查交易记录是否有time字段
      const missingTimeFields = trades.value.filter(trade => !trade.time);
      if (missingTimeFields.length > 0) {
        console.warn(`ProfitChart - ${missingTimeFields.length} trades missing time field`);
        // 为缺少time字段的交易记录添加当前时间
        missingTimeFields.forEach(trade => {
          trade.time = new Date().toISOString();
        });
      }
      
      // 按时间排序交易记录
      const sortedTrades = [...trades.value].sort((a, b) => {
        return new Date(a.time) - new Date(b.time);
      });
      
      console.log('ProfitChart - sortedTrades:', sortedTrades);
      
      // 限制数据点数量，最多显示100个点
      const maxDataPoints = 100;
      let dataPoints = sortedTrades;
      
      // 如果数据点超过100个，进行采样
      if (sortedTrades.length > maxDataPoints) {
        const step = Math.ceil(sortedTrades.length / maxDataPoints);
        dataPoints = sortedTrades.filter((_, index) => index % step === 0 || index === sortedTrades.length - 1);
      }
      
      // 计算累计收益
      let cumulativeProfit = 0;
      
      // 首先打印完整的第一条交易记录，以便了解其结构
      if (dataPoints.length > 0) {
        console.log('First trade record complete structure:', JSON.stringify(dataPoints[0], null, 2));
      }
      
      const result = dataPoints.map((trade, index) => {
        // 获取net_profit值，优先使用直接的net_profit字段
        let profit = 0;
        
        // 详细的调试日志
        console.log('Processing trade:', {
          tradeId: trade.id || index,
          rawNetProfit: trade.net_profit,
          formattedNetProfit: trade.formatted?.net_profit,
          fee: trade.fee,
          formattedFee: trade.formatted?.fee,
          profit: trade.profit,
          formattedProfit: trade.formatted?.profit,
          tradeObject: trade
        });
        
        // 检查所有可能包含收益信息的字段
        // 1. 直接检查profit字段
        if (typeof trade.profit === 'number') {
          profit = trade.profit;
          console.log(`Using direct profit field: ${profit}`);
        } 
        else if (trade.profit !== undefined) {
          profit = parseFloat(trade.profit);
          if (!isNaN(profit)) {
            console.log(`Using parsed profit field: ${profit}`);
          }
        }
        // 2. 检查formatted.profit
        else if (trade.formatted && trade.formatted.profit !== undefined) {
          profit = parseFloat(trade.formatted.profit);
          if (!isNaN(profit)) {
            console.log(`Using formatted profit field: ${profit}`);
          }
        }
        // 3. 检查net_profit字段
        else if (typeof trade.net_profit === 'number') {
          profit = trade.net_profit;
          console.log(`Using direct net_profit field: ${profit}`);
        }
        else if (trade.net_profit !== undefined) {
          profit = parseFloat(trade.net_profit);
          if (!isNaN(profit)) {
            console.log(`Using parsed net_profit field: ${profit}`);
          }
        }
        // 4. 检查formatted.net_profit
        else if (trade.formatted && trade.formatted.net_profit !== undefined) {
          profit = parseFloat(trade.formatted.net_profit);
          if (!isNaN(profit)) {
            console.log(`Using formatted net_profit field: ${profit}`);
          }
        }
        
        // 如果获取到的值是NaN或无效，记录警告并尝试其他方法获取收益
        if (isNaN(profit) || profit === 0) {
          console.warn(`ProfitChart - Invalid or zero profit value at index ${index}, trying alternative methods`);
          
          // 尝试从price_difference获取收益
          if (trade.price_difference !== undefined) {
            profit = parseFloat(trade.price_difference);
            console.log(`Trying to use price_difference: ${profit}`);
          }
          
          // 尝试从amount和price计算收益
          if ((isNaN(profit) || profit === 0) && trade.amount !== undefined && trade.price !== undefined) {
            const amount = parseFloat(trade.amount);
            const price = parseFloat(trade.price);
            if (!isNaN(amount) && !isNaN(price)) {
              profit = amount * price;
              console.log(`Calculated profit from amount*price: ${profit}`);
            }
          }
          
          // 尝试从fee计算收益（假设fee是负收益的一部分）
          if ((isNaN(profit) || profit === 0) && trade.fee !== undefined) {
            let fee = 0;
            if (typeof trade.fee === 'number') {
              fee = trade.fee;
            } else if (trade.fee !== undefined) {
              fee = parseFloat(trade.fee);
            } else if (trade.formatted && trade.formatted.fee !== undefined) {
              fee = parseFloat(trade.formatted.fee);
            }
            
            if (!isNaN(fee) && fee !== 0) {
              // 假设手续费是负收益的一部分，这里我们将其视为收益的一部分
              // 通常手续费是负数，所以我们取反
              profit = -fee;
              console.log(`Using fee as profit (negative): ${profit}`);
            }
          }
          
          // 如果所有尝试都失败，设为0
          if (isNaN(profit)) {
            console.warn('All attempts to get profit failed, setting to 0');
            profit = 0;
          }
        }
        
        // 计算累计收益
        cumulativeProfit += profit;
        
        // 添加调试日志
        console.log(`Trade ${index + 1}: single_profit = ${profit}, cumulative = ${cumulativeProfit}`);
        
        // 使用累计收益而不是总收益
        return {
          time: trade.time,
          profit: cumulativeProfit.toFixed(4),  // 使用累计收益
          tradeIndex: index + 1,
          singleProfit: profit.toFixed(4),  // 单次交易收益
          fee: trade.fee || (trade.formatted?.fee || '0'),  // 添加手续费信息
          status: trade.status || '',
          type: trade.type || ''
        };
      });
      
      console.log('ProfitChart - profitData result:', result);
      return result;
    })
    
    // 初始化图表
    const initChart = () => {
      if (!chartContainer.value) return
      
      // 创建图表实例
      chart = echarts.init(chartContainer.value)
      
      // 更新图表
      updateChart()
      
      // 监听窗口大小变化，调整图表大小
      window.addEventListener('resize', handleResize)
    }
    
    // 更新图表数据
    const updateChart = () => {
      if (!chart) return
      
      const data = profitData.value
      
      // 如果没有数据，显示空状态
      if (data.length === 0) {
        chart.setOption({
          title: {
            text: '暂无交易数据',
            left: 'center',
            top: 'center',
            textStyle: {
              color: '#999',
              fontSize: 16
            }
          }
        })
        return
      }
      
      // 提取数据点
      const times = data.map(item => item.time)
      const profits = data.map(item => item.profit)
      
      // 格式化时间显示
      const formattedTimes = times.map(time => {
        const date = new Date(time);
        // 格式化为 MM-DD HH:MM
        return `${(date.getMonth()+1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}`;
      });
      
      // 计算最大值和最小值，用于设置y轴范围
      const maxProfit = Math.max(...profits.map(p => parseFloat(p)))
      const fixedYAxisMax = Math.max(1000, maxProfit * 1.1) // 设置一个最小值1000，如果最大收益超过这个值则相应增加
      
      // 设置图表选项
      chart.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: function(params) {
            const dataIndex = params[0].dataIndex
            const date = new Date(times[dataIndex]);
            const formattedTime = `${date.getFullYear()}-${(date.getMonth()+1).toString().padStart(2, '0')}-${date.getDate().toString().padStart(2, '0')} ${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`;
            
            // 获取原始数据对象
            const tradeData = data[dataIndex];
            
            return `
              <div style="padding: 5px;">
                <div style="margin-bottom: 5px;"><b>时间:</b> ${formattedTime}</div>
                <div style="margin-bottom: 5px;"><b>累计收益:</b> ${profits[dataIndex]} USDT</div>
                <div style="margin-bottom: 5px;"><b>单次收益:</b> ${tradeData.singleProfit} USDT</div>
                <div style="margin-bottom: 5px;"><b>手续费:</b> ${tradeData.fee} USDT</div>
                ${tradeData.status ? `<div style="margin-bottom: 5px;"><b>状态:</b> ${tradeData.status}</div>` : ''}
                ${tradeData.type ? `<div style="margin-bottom: 5px;"><b>类型:</b> ${tradeData.type}</div>` : ''}
              </div>
            `
          }
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          containLabel: true
        },
        xAxis: {
          type: 'category',
          data: formattedTimes,
          name: '时间',
          nameLocation: 'middle',
          nameGap: 35,
          axisLabel: {
            interval: Math.floor(data.length / 8), // 控制标签显示密度
            rotate: 45, // 旋转标签以避免重叠
            fontSize: 10
          }
        },
        yAxis: {
          type: 'value',
          name: '总收益 (USDT)',
          min: 0,  // 固定从0开始
          max: fixedYAxisMax,  // 使用固定的最大值
          axisLine: {
            show: true,
            lineStyle: {
              color: '#67C23A'
            }
          },
          axisLabel: {
            formatter: '{value} USDT'
          },
          splitLine: {
            show: true,
            lineStyle: {
              type: 'dashed'
            }
          }
        },
        series: [
          {
            name: '总收益',
            type: 'line',
            data: profits,
            smooth: true,
            showSymbol: data.length < 30, // 只在数据点少时显示标记
            symbolSize: 6,
            lineStyle: {
              width: 3,
              color: '#67C23A'
            },
            areaStyle: {
              opacity: 0.2,
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                {
                  offset: 0,
                  color: parseFloat(profits[profits.length - 1]) >= 0 ? 'rgba(103, 194, 58, 0.8)' : 'rgba(245, 108, 108, 0.8)'
                },
                {
                  offset: 1,
                  color: parseFloat(profits[profits.length - 1]) >= 0 ? 'rgba(103, 194, 58, 0.1)' : 'rgba(245, 108, 108, 0.1)'
                }
              ])
            },
            itemStyle: {
              color: function(params) {
                return parseFloat(profits[params.dataIndex]) >= 0 ? '#67C23A' : '#F56C6C';
              }
            },
            markLine: {
              silent: true,
              lineStyle: {
                color: '#999',
                type: 'dashed'
              },
              data: [
                {
                  yAxis: 0,
                  label: {
                    formatter: '盈亏平衡',
                    position: 'start'
                  }
                }
              ]
            }
          }
        ]
      })
    }
    
    // 处理窗口大小变化
    const handleResize = () => {
      if (chart) {
        chart.resize()
      }
    }
    
    // 监听交易数据变化，更新图表
    watch(trades, () => {
      updateChart()
    })
    
    // 组件挂载时初始化图表
    onMounted(() => {
      initChart()
    })
    
    // 组件卸载时销毁图表
    onUnmounted(() => {
      if (chart) {
        chart.dispose()
        chart = null
      }
      window.removeEventListener('resize', handleResize)
    })
    
    return {
      chartContainer
    }
  }
}
</script>

<style scoped>
.profit-chart {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
}

.card-header span {
  margin-right: 8px;
}

.chart-container {
  height: 300px;
  width: 100%;
}
</style> 