# DuskRain Dashboard

独立 Vue3 子应用，计划挂载到 `https://duskrain.cn/dashboard/`。

## 当前定位

- 只读展示层
- 不直接暴露交易控制
- 后续通过受保护的聚合 API 接 Freqtrade / OpenClaw 状态

## 本地开发

```powershell
npm install
npm run dev
```

## 构建

```powershell
npm run build
```

构建产物位于 `dist/`，当前 `vite.config.ts` 已设置：

- `base: '/dashboard/'`

这意味着静态文件默认按子路径部署，可直接对接 Nginx 的 `/dashboard/` location。

## 建议接入方式

1. 保留 `duskrain.cn` 现有静态首页。
2. 将 `dist/` 发布到服务器的独立目录。
3. 在 Nginx 上增加 `/dashboard/` 指向该目录。
4. 第一阶段只接只读接口，不让前端直接控制交易。
