import { createRouter, createWebHistory } from 'vue-router'

import AlertsView from '../views/AlertsView.vue'
import BacktestResultsView from '../views/BacktestResultsView.vue'
import DashboardHomeView from '../views/DashboardHomeView.vue'
import FreqtradeStatusView from '../views/FreqtradeStatusView.vue'

const base = import.meta.env.BASE_URL

const router = createRouter({
  history: createWebHistory(base),
  routes: [
    {
      path: '/',
      name: 'dashboard-home',
      component: DashboardHomeView,
      meta: { title: '总览' },
    },
    {
      path: '/freqtrade',
      name: 'freqtrade-status',
      component: FreqtradeStatusView,
      meta: { title: 'Freqtrade 状态' },
    },
    {
      path: '/backtest',
      name: 'backtest-results',
      component: BacktestResultsView,
      meta: { title: '回测结果' },
    },
    {
      path: '/alerts',
      name: 'alerts',
      component: AlertsView,
      meta: { title: '告警中心' },
    },
  ],
})

export default router
