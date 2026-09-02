// ── 全局显示缩放（等价于浏览器页面缩放）──
// 数值存于后端 settings.json 的 ui_zoom（百分比，100 = 不缩放），
// 前端启动时读取并应用；同一后端的所有电脑/浏览器共用一份。
export const UI_ZOOM_MIN = 25
export const UI_ZOOM_MAX = 500

export function normalizeUiZoom(v) {
  const n = Number(v)
  if (!Number.isFinite(n)) return 100
  return Math.min(UI_ZOOM_MAX, Math.max(UI_ZOOM_MIN, Math.round(n)))
}

// 把百分比应用为整站缩放。CSS zoom 是渲染级缩放，不改变 layout viewport——
// 视口单位（vh）仍按未缩放视口解析，会导致 height:100vh 的元素在 zoom≠1 时
// 视觉溢出或不足一屏。因此用 --ui-zoom-comp 把 100vh 换算为 100vh/zoom，
// 绘制放大后恰好等于一屏（布局高度/遮罩需引用该变量）。
export function applyUiZoom(percent) {
  const p = normalizeUiZoom(percent)
  const root = document.documentElement
  if (p === 100) {
    root.style.zoom = ''
    root.style.removeProperty('--ui-zoom-comp')
    return
  }
  root.style.zoom = String(p / 100)
  root.style.setProperty('--ui-zoom-comp', `calc(100vh / ${p / 100})`)
}
