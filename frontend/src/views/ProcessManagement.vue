<template>
  <div class="process-page">
    <h2 class="page-title">进程管理</h2>

    <!-- ── 服务状态 ── -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>服务运行状态</span>
          <el-button size="small" @click="refreshStatus" :loading="refreshing">
            刷新
          </el-button>
        </div>
      </template>
      <div class="status-grid">
        <div class="status-item" :class="{ running: status.backend }">
          <span class="status-dot" :class="{ running: status.backend }"></span>
          <div>
            <div class="svc-name">后端服务</div>
            <div class="svc-detail">
              <template v-if="status.backend">运行中 (端口 8000)</template>
              <template v-else>已停止</template>
            </div>
          </div>
          <el-button
            v-if="status.backend"
            size="small"
            type="danger"
            plain
            @click="stopBackend"
            :loading="stopping.backend"
            class="stop-btn"
          >
            停止
          </el-button>
        </div>
        <div class="status-item" :class="{ running: status.frontend }">
          <span class="status-dot" :class="{ running: status.frontend }"></span>
          <div>
            <div class="svc-name">前端页面</div>
            <div class="svc-detail">
              <template v-if="status.frontend">运行中 (端口 5173)</template>
              <template v-else>已停止</template>
            </div>
          </div>
          <el-button
            v-if="status.frontend"
            size="small"
            type="danger"
            plain
            @click="stopFrontend"
            :loading="stopping.frontend"
            class="stop-btn"
          >
            停止
          </el-button>
        </div>
      </div>

      <div class="action-bar">
        <el-button
          type="danger"
          @click="stopAll"
          :loading="stopping.all"
          :disabled="!status.backend && !status.frontend"
        >
          一键关闭所有服务
        </el-button>
      </div>
    </el-card>

    <!-- ── 开机自启动 ── -->
    <el-card shadow="never" class="section-card">
      <template #header>
        <div class="section-header">
          <span>开机自启动</span>
          <el-switch
            v-model="autostartEnabled"
            @change="onAutostartToggle"
            :loading="saving"
          />
        </div>
      </template>

      <template v-if="autostartEnabled">
        <p class="desc-text">
          开机时自动启动 TaskM 后端服务。选择「完整模式」还会在启动后自动打开浏览器。
        </p>
        <el-radio-group
          v-model="autostartMode"
          @change="onAutostartModeChange"
          :disabled="saving"
          class="mode-group"
        >
          <el-radio value="backend">
            <div class="radio-option">
              <div class="radio-title">仅后端服务</div>
              <div class="radio-desc">开机后在后台静默启动后端，不打开浏览器</div>
            </div>
          </el-radio>
          <el-radio value="full">
            <div class="radio-option">
              <div class="radio-title">完整模式</div>
              <div class="radio-desc">开机后启动后端，并自动打开浏览器进入主界面</div>
            </div>
          </el-radio>
        </el-radio-group>
      </template>
      <p v-else class="desc-text muted">
        开机自启动已关闭。开启后可选择启动方式。
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import http from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const refreshing = ref(false)
const saving = ref(false)
const status = ref({ backend: false, frontend: false })
const stopping = ref({ backend: false, frontend: false, all: false })
const autostartEnabled = ref(false)
const autostartMode = ref('backend')

async function refreshStatus() {
  refreshing.value = true
  try {
    const res = await http.get('/process/status')
    status.value = res
  } catch {
    status.value = { backend: false, frontend: false }
  }
  refreshing.value = false
}

async function refreshAutostart() {
  try {
    const res = await http.get('/process/autostart')
    autostartEnabled.value = res.enabled
    autostartMode.value = res.mode === 'off' ? 'backend' : res.mode
  } catch {
    autostartEnabled.value = false
    autostartMode.value = 'backend'
  }
}

async function onAutostartToggle(val) {
  saving.value = true
  try {
    await http.put('/process/autostart', { mode: val ? autostartMode.value : 'off' })
  } catch {
    autostartEnabled.value = !val
  }
  saving.value = false
}

async function onAutostartModeChange(val) {
  saving.value = true
  try {
    await http.put('/process/autostart', { mode: val })
  } catch {
    autostartMode.value = autostartMode.value
  }
  saving.value = false
}

async function confirmStop(title) {
  try {
    await ElMessageBox.confirm(title, '确认操作', {
      confirmButtonText: '确认关闭',
      cancelButtonText: '取消',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}

async function stopBackend() {
  if (!(await confirmStop('确认关闭后端服务？\n关闭后 API 将不可用。'))) return
  stopping.value.backend = true
  try {
    await http.post('/process/stop-backend')
    status.value.backend = false
    ElMessage.success('后端服务已关闭')
  } catch {
    status.value.backend = false
    ElMessage.success('后端服务已关闭')
  }
  stopping.value.backend = false
}

async function stopFrontend() {
  if (!(await confirmStop('确认关闭前端服务？\n关闭后页面将无法刷新。'))) return
  stopping.value.frontend = true
  try {
    await http.post('/process/stop-frontend')
    status.value.frontend = false
    ElMessage.success('前端服务已关闭')
  } catch {
    status.value.frontend = false
    ElMessage.success('前端服务已关闭')
  }
  stopping.value.frontend = false
}

async function stopAll() {
  if (!(await confirmStop('确认关闭所有服务？\n关闭后本页面将不可用。'))) return
  stopping.value.all = true
  try {
    await http.post('/process/stop-all')
    ElMessage.success('所有服务已关闭')
  } catch {
    ElMessage.success('所有服务已关闭')
  }
  status.value = { backend: false, frontend: false }
  stopping.value.all = false
  // 跳转到关闭提示页
  window.location.href = '/closed.html'
}

onMounted(() => {
  refreshStatus()
  refreshAutostart()
})
</script>

<style scoped>
.process-page {
  max-width: 700px;
  margin: 0 auto;
}
.page-title {
  font-size: 22px; font-weight: 600; margin-bottom: 24px; color: #2c2c2a;
}
.section-card {
  margin-bottom: 20px; border-radius: 10px;
}
.section-header {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 15px; font-weight: 600;
}

/* 状态卡片 */
.status-grid {
  display: flex; gap: 24px;
}
.status-item {
  display: flex; align-items: center; gap: 12px;
  flex: 1; padding: 16px; background: #f8f8f6; border-radius: 8px;
}
.status-dot {
  width: 12px; height: 12px; border-radius: 50%;
  background: #ccc; flex-shrink: 0;
  transition: background 0.3s, box-shadow 0.3s;
}
.status-dot.running {
  background: #52c41a;
  box-shadow: 0 0 8px rgba(82,196,26,0.4);
}
.svc-name { font-size: 14px; font-weight: 600; color: #2c2c2a; }
.svc-detail { font-size: 12px; color: #999; margin-top: 2px; }
.stop-btn { margin-left: auto; flex-shrink: 0; }
.status-item.running { background: #f0faf0; }

.action-bar {
  margin-top: 16px;
  display: flex; justify-content: flex-end;
}

/* 自启动 */
.desc-text {
  font-size: 13px; color: #666; line-height: 1.6; margin-bottom: 20px;
}
.desc-text.muted { color: #aaa; }
.mode-group {
  display: flex; flex-direction: column; gap: 12px;
}
.radio-option { padding: 4px 0; }
.radio-title { font-size: 14px; font-weight: 500; color: #2c2c2a; }
.radio-desc { font-size: 12px; color: #999; margin-top: 2px; }
</style>
