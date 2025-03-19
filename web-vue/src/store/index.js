import { createStore } from 'vuex'

export default createStore({
  state: {
    accountOverview: {
      initialBalance: 0,
      currentBalance: 0,
      totalAssetValue: 0,
      totalProfit: 0,
      profitRate: 0,
      unhedgedValue: 0,
      shortPositionValue: 0,
      totalFees: 0,
      frozenAssets: 0
    },
    tradeStats: {
      totalTrades: 0,
      successTrades: 0,
      failedTrades: 0,
      winRate: 0,
      tradeTypes: {},
      tradeStatusStats: {},
      tradeTypeProfitStats: {}
    },
    positions: {
      unhedgedPositions: [],
      futuresShortPositions: []
    },
    recentTrades: [],
    allTrades: [],
    lastUpdateTime: null,
    wsConnected: false,
    depths: {},
    fees: {},
    balances: {},
    frozenBalances: {},
    unhedgedPositions: [],
    pendingOrders: []
  },
  mutations: {
    updateAccountOverview(state, data) {
      state.accountOverview = {
        initialBalance: Number(data.initial_balance || 0),
        currentBalance: Number(data.current_balance || 0),
        totalAssetValue: Number(data.total_asset_value || 0),
        totalProfit: Number(data.total_profit || 0),
        profitRate: Number(data.profit_rate || 0),
        unhedgedValue: Number(data.unhedged_value || 0),
        shortPositionValue: Number(data.short_position_value || 0),
        totalFees: Number(data.total_fees || 0),
        frozenAssets: Number(data.frozen_assets || 0)
      }
      
      // 调试输出
      console.log('Total fees from server:', data.total_fees);
      console.log('Parsed total fees:', state.accountOverview.totalFees);
      console.log('Frozen assets from server:', data.frozen_assets);
    },
    updateTradeStats(state, data) {
      state.tradeStats = {
        totalTrades: Number(data.total_trades || 0),
        successTrades: Number(data.success_trades || 0),
        failedTrades: Number(data.failed_trades || 0),
        winRate: Number(data.win_rate || 0),
        tradeTypes: data.trade_types || {},
        tradeStatusStats: data.trade_status_stats || {},
        tradeTypeProfitStats: data.trade_type_profit_stats || {}
      }
    },
    updatePositions(state, data) {
      const processPositions = (positions) => {
        return (positions || []).map(pos => ({
          ...pos,
          amount: Number(pos.amount || 0),
          price: Number(pos.price || 0),
          value: Number(pos.value || 0)
        }))
      }

      const unhedgedPositions = processPositions(data.unhedged_positions);
      const futuresShortPositions = processPositions(data.futures_short_positions);

      state.positions = {
        unhedgedPositions,
        futuresShortPositions
      }
      
      state.unhedgedPositions = unhedgedPositions;
    },
    updateRecentTrades(state, trades) {
      console.log('Updating recent trades, received:', trades ? trades.length : 0, 'trades');
      
      // 检查交易记录是否为空
      if (!trades || trades.length === 0) {
        console.warn('No trades data received');
        state.allTrades = [];
        state.recentTrades = [];
        return;
      }
      
      // 检查并处理每个交易记录
      const processedTrades = trades.map((trade, index) => {
        // 确保trade是对象
        if (typeof trade !== 'object' || trade === null) {
          console.warn('Invalid trade record:', trade);
          return null;
        }
        
        // 确保time字段存在
        if (!trade.time) {
          trade.time = new Date().toISOString();
        }
        
        // 详细的调试日志
        console.log('Processing trade in store:', {
          index,
          rawNetProfit: trade.net_profit,
          formattedNetProfit: trade.formatted?.net_profit,
          tradeObject: trade
        });
        
        // 处理net_profit值
        let netProfit = 0;
        
        // 首先尝试获取原始的net_profit值
        if (typeof trade.net_profit === 'number') {
          netProfit = trade.net_profit;
        }
        // 如果原始值不是数字，尝试转换
        else if (trade.net_profit !== undefined) {
          netProfit = parseFloat(trade.net_profit);
        }
        // 如果还是无效，尝试从formatted中获取
        else if (trade.formatted && trade.formatted.net_profit !== undefined) {
          netProfit = parseFloat(trade.formatted.net_profit);
        }
        
        // 如果net_profit是NaN或无效，记录警告
        if (isNaN(netProfit)) {
          console.warn('Invalid net_profit value:', trade);
          netProfit = 0;
        }
        
        // 确保formatted对象存在
        if (!trade.formatted) {
          trade.formatted = {};
        }
        
        // 更新net_profit值
        const processedTrade = {
          ...trade,
          net_profit: netProfit,
          formatted: {
            ...trade.formatted,
            net_profit: netProfit.toFixed(4)
          }
        };
        
        // 添加调试日志
        console.log(`处理交易记录 - ID: ${processedTrade.id || index}, net_profit: ${netProfit}, status: ${processedTrade.status || ''}`);
        
        return processedTrade;
      }).filter(trade => trade !== null);  // 过滤掉无效的交易记录
      
      // 按时间排序
      const sortedTrades = processedTrades.sort((a, b) => new Date(a.time) - new Date(b.time));
      
      // 更新状态
      state.allTrades = sortedTrades;
      state.recentTrades = sortedTrades.slice(-100);
      
      // 添加调试日志
      console.log('Updated recent trades, now have:', state.recentTrades.length, 'trades');
      if (state.recentTrades.length > 0) {
        console.log('First trade:', state.recentTrades[0]);
        console.log('Last trade:', state.recentTrades[state.recentTrades.length - 1]);
        
        // 计算总收益
        const totalProfit = state.recentTrades.reduce((sum, trade) => {
          const profit = parseFloat(trade.net_profit || 0);
          return isNaN(profit) ? sum : sum + profit;
        }, 0);
        console.log('Total profit from recent trades:', totalProfit.toFixed(4));
      }
    },
    updateLastUpdateTime(state, timestamp) {
      state.lastUpdateTime = timestamp
    },
    setWsConnected(state, status) {
      state.wsConnected = status
    },
    updateDepths(state, data) {
      state.depths = data || {}
    },
    updateFees(state, data) {
      state.fees = data || {}
    },
    updateBalances(state, data) {
      state.balances = data || {}
    },
    updateFrozenBalances(state, data) {
      state.frozenBalances = data || {}
    },
    updatePendingOrders(state, data) {
      // 处理挂单数据，确保数值类型正确
      state.pendingOrders = (data || []).map(order => ({
        ...order,
        amount: Number(order.amount || 0),
        buy_price: Number(order.buy_price || 0),
        sell_price: Number(order.sell_price || 0),
        buy_fee_rate: Number(order.buy_fee_rate || 0),
        sell_fee_rate: Number(order.sell_fee_rate || 0),
        potential_profit: Number(order.potential_profit || 0),
        price_updates: Number(order.price_updates || 0)
      }))
    }
  },
  actions: {
    initWebSocket({ commit, dispatch }) {
      console.log('Initializing WebSocket connection to ws://localhost:8083/ws')
      const ws = new WebSocket('ws://localhost:8083/ws')
      
      // Store the WebSocket instance in a global variable for access
      window.appWebSocket = ws;
      
      ws.onopen = () => {
        commit('setWsConnected', true)
        console.log('WebSocket connected successfully')
        dispatch('fetchBalances')
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        commit('setWsConnected', false)
      }
      
      ws.onclose = (event) => {
        console.log('WebSocket connection closed:', event.code, event.reason)
        commit('setWsConnected', false)
        
        // Try to reconnect after 5 seconds
        setTimeout(() => {
          console.log('Attempting to reconnect WebSocket...')
          dispatch('initWebSocket')
        }, 5000)
      }
      
      // Add event listener for the custom event
      window.addEventListener('fetch_balances_request', () => {
        if (ws.readyState === WebSocket.OPEN) {
          console.log('Sending fetch_balances request via WebSocket');
          ws.send(JSON.stringify({ action: 'fetch_balances' }));
        } else {
          console.error('WebSocket not in OPEN state, cannot send fetch_balances request');
        }
      });
      
      ws.onmessage = (event) => {
        console.log('WebSocket message received:', event.data.substring(0, 100) + '...')
        try {
          const data = JSON.parse(event.data)
          
          if (data.log) {
            console.log('Log from server:', data.log)
            return
          }
          
          if (!data || typeof data !== 'object') {
            console.error('Invalid data format received:', data)
            return
          }

          const requiredFields = [
            'initial_balance',
            'current_balance',
            'total_asset_value',
            'total_profit',
            'profit_rate',
            'total_trades',
            'success_trades',
            'failed_trades',
            'win_rate'
          ]

          const missingFields = requiredFields.filter(field => !(field in data))
          if (missingFields.length > 0) {
            console.warn('Missing required fields:', missingFields)
          }

          console.log('Received data:', data)
          
          // 添加更多调试日志
          console.log('Trade types:', data.trade_types)
          console.log('Recent trades:', data.recent_trades)
          console.log('Pending orders:', data.pending_orders)
          
          if ('initial_balance' in data) {
            commit('updateAccountOverview', data)
            console.log('Updated account overview')
          }
          if ('total_trades' in data) {
            commit('updateTradeStats', data)
            console.log('Updated trade stats')
          }
          if ('unhedged_positions' in data || 'futures_short_positions' in data) {
            commit('updatePositions', data)
            console.log('Updated positions')
          }
          if (Array.isArray(data.recent_trades)) {
            commit('updateRecentTrades', data.recent_trades)
            console.log('Updated recent trades, count:', data.recent_trades.length)
          }
          if (data.timestamp) {
            commit('updateLastUpdateTime', data.timestamp)
            console.log('Updated timestamp')
          }
          
          if (data.depths) {
            commit('updateDepths', data.depths)
            console.log('Updated depths')
          }
          if (data.fees) {
            commit('updateFees', data.fees)
            console.log('Updated fees')
          }
          if (data.balances) {
            commit('updateBalances', data.balances)
            console.log('Updated balances')
          }
          if (data.frozen_balances) {
            commit('updateFrozenBalances', data.frozen_balances)
            console.log('Updated frozen balances')
          }
          if (data.pending_orders) {
            commit('updatePendingOrders', data.pending_orders)
            console.log('Updated pending orders, count:', data.pending_orders.length)
          }
          
        } catch (error) {
          console.error('Error processing WebSocket message:', error)
          console.error('Raw message:', event.data)
        }
      }
    },
    fetchBalances({ state }) {
      if (state.wsConnected) {
        console.log('Requesting balance update from server');
        window.dispatchEvent(new CustomEvent('fetch_balances_request'));
      } else {
        console.error('WebSocket not connected, cannot fetch balances');
      }
    }
  },
  getters: {
    formattedAccountOverview: state => {
      const overview = state.accountOverview
      return {
        initialBalance: overview.initialBalance.toFixed(2),
        currentBalance: overview.currentBalance.toFixed(2),
        totalAssetValue: overview.totalAssetValue.toFixed(2),
        totalProfit: overview.totalProfit.toFixed(2),
        profitRate: overview.profitRate.toFixed(2),
        unhedgedValue: overview.unhedgedValue.toFixed(2),
        shortPositionValue: overview.shortPositionValue.toFixed(2),
        totalFees: overview.totalFees.toString(),
        frozenAssets: overview.frozenAssets.toFixed(2)
      }
    },
    formattedTradeStats: state => {
      const stats = state.tradeStats
      return {
        totalTrades: stats.totalTrades,
        successTrades: stats.successTrades,
        failedTrades: stats.failedTrades,
        winRate: stats.winRate.toFixed(2),
        tradeTypes: stats.tradeTypes,
        tradeStatusStats: stats.tradeStatusStats,
        tradeTypeProfitStats: stats.tradeTypeProfitStats
      }
    },
    paginatedTrades: state => (page, pageSize) => {
      const start = (page - 1) * pageSize;
      const end = start + pageSize;
      return state.allTrades.slice(start, end);
    },
    totalTradeCount: state => {
      return state.allTrades.length;
    }
  }
}) 