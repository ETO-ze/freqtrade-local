import { defineStore } from 'pinia'

export const useSystemStore = defineStore('system', {
  state: () => ({
    publicSiteMode: '静态首页保留',
    tradeAccess: '独立认证域名',
    apiMode: '只读聚合 JSON',
    services: [
      {
        name: 'Public Site',
        status: 'online',
        note: 'duskrain.cn 静态展示层',
      },
      {
        name: 'Dashboard',
        status: 'online',
        note: 'duskrain.cn/dashboard 只读看板',
      },
      {
        name: 'Freqtrade Panel',
        status: 'protected',
        note: 'www.duskrain.cn 认证后访问',
      },
    ],
  }),
})
