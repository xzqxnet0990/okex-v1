<template>
  <div class="app-container">
    <el-container>
      <el-header>
        <h1>OKEX 策略监控</h1>
        <div class="connection-status" :class="{ connected: wsConnected }">
          {{ wsConnected ? '已连接' : '未连接' }}
        </div>
      </el-header>
      <el-main>
        <AccountOverview />
        <el-row :gutter="20">
          <el-col :span="24">
            <ProfitChart />
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <TradeStats />
          </el-col>
          <el-col :span="12">
            <PositionInfo />
          </el-col>
        </el-row>
        <CoinBalances />
        <RecentTrades />
      </el-main>
    </el-container>
  </div>
</template>

<script>
import { computed, onMounted } from 'vue'
import { useStore } from 'vuex'
import AccountOverview from './components/AccountOverview.vue'
import TradeStats from './components/TradeStats.vue'
import PositionInfo from './components/PositionInfo.vue'
import RecentTrades from './components/RecentTrades.vue'
import ProfitChart from './components/ProfitChart.vue'
import CoinBalances from './components/CoinBalances.vue'

export default {
  name: 'App',
  components: {
    AccountOverview,
    TradeStats,
    PositionInfo,
    RecentTrades,
    ProfitChart,
    CoinBalances
  },
  setup() {
    const store = useStore()
    const wsConnected = computed(() => store.state.wsConnected)

    onMounted(() => {
      store.dispatch('initWebSocket')
    })

    return {
      wsConnected
    }
  }
}
</script>

<style>
.app-container {
  min-height: 100vh;
  background-color: #f0f2f5;
}

.el-header {
  background-color: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.el-header h1 {
  margin: 0;
  font-size: 20px;
  color: #303133;
}

.el-main {
  padding: 20px;
}

.connection-status {
  padding: 4px 12px;
  border-radius: 4px;
  font-size: 14px;
  background-color: #f56c6c;
  color: #fff;
}

.connection-status.connected {
  background-color: #67c23a;
}

.el-row {
  margin-bottom: 20px;
}
</style> 