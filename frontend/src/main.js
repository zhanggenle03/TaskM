import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import router from './router'
import App from './App.vue'
import http from './api'
import { applyUiZoom } from './utils/uiZoom'

const app = createApp(App)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 先应用全局显示缩放（settings.json 的 ui_zoom）再挂载，避免页面闪一下原始比例
async function bootstrap() {
  try {
    const s = await http.get('/process/settings', { _silentError: true })
    applyUiZoom(s?.ui_zoom)
  } catch {
    // 后端未就绪等场景：保持默认 100%，不阻塞渲染
  }
  app.mount('#app')
}

bootstrap()
