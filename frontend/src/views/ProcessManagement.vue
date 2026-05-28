<template>
  <div class="settings-page">
    <h2 class="page-title">通用设置</h2>

    <!-- ── 服务运行状态 ── -->
    <el-card shadow="never" class="sec-card">
      <template #header>
        <div class="card-head">
          <span>服务运行状态</span>
          <el-button size="small" text @click="refreshStatus" :loading="refreshing">刷新</el-button>
        </div>
      </template>
      <div class="svc-grid">
        <div class="svc-row" :class="{ on: status.backend }">
          <span class="dot" :class="{ on: status.backend }"></span>
          <span class="svc-name">后端服务</span>
          <span class="svc-stat">{{ status.backend ? '运行中 (8000)' : '已停止' }}</span>
          <span style="flex:1"></span>
          <el-button v-if="status.backend" size="small" text type="warning" @click="restartBackend" :loading="restarting.backend">
            <el-icon><Refresh /></el-icon> 重启
          </el-button>
        </div>
        <div class="svc-row" :class="{ on: status.frontend }">
          <span class="dot" :class="{ on: status.frontend }"></span>
          <span class="svc-name">前端页面</span>
          <span class="svc-stat">{{ status.frontend ? '运行中 (5173)' : '已停止' }}</span>
          <span style="flex:1"></span>
          <el-button v-if="status.frontend" size="small" text type="warning" @click="restartFrontend" :loading="restarting.frontend">
            <el-icon><Refresh /></el-icon> 重启
          </el-button>
        </div>
      </div>
      <div class="card-foot">
        <el-button size="small" type="warning" plain @click="restartAll" :loading="restarting.all" :disabled="!status.backend && !status.frontend">
          <el-icon><Refresh /></el-icon> 重启所有服务
        </el-button>
      </div>
    </el-card>

    <!-- ── 开机自启动 ── -->
    <el-card shadow="never" class="sec-card">
      <template #header>
        <div class="card-head">
          <span>开机自启动</span>
          <el-switch v-model="autostartEnabled" @change="onAutostartToggle" :loading="saving" size="small" />
        </div>
      </template>
      <template v-if="autostartEnabled">
        <p class="hint">开机时自动启动 TaskM 后端和前端服务。</p>
        <el-radio-group v-model="autostartMode" @change="onAutostartModeChange" :disabled="saving">
          <el-radio value="backend" class="radio-compact">启动服务 — 开机后在后台静默启动后端和前端，不打开浏览器</el-radio>
          <el-radio value="full" class="radio-compact">启动服务并打开浏览器 — 开机后启动服务，并自动打开浏览器进入主界面</el-radio>
        </el-radio-group>
      </template>
      <p v-else class="hint muted">开机自启动已关闭，开启后可选择启动方式。</p>
    </el-card>

    <!-- ── 文件 & 工作区 ── -->
    <el-card shadow="never" class="sec-card">
      <template #header>
        <div class="card-head">
          <span>文件 & 工作区</span>
        </div>
      </template>
      <div class="file-row">
        <span class="file-lbl">工作文件夹</span>
        <el-button size="small" @click="openWorkspace" :loading="openingWorkspace">
          <el-icon><FolderOpened /></el-icon> 打开
        </el-button>
      </div>
      <div class="file-row">
        <span class="file-lbl">附件大小限制</span>
        <el-input-number v-model="maxFileSizeMB" :min="1" :max="500" :disabled="settingsSaving" controls-position="right" size="small" style="width:110px" />
        <span class="unit">MB</span>
        <el-button size="small" type="primary" @click="saveFileSize" :loading="settingsSaving">保存</el-button>
        <span class="hint" style="margin-left:8px">1~500MB 可调</span>
      </div>
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
const restarting = ref({ backend: false, frontend: false, all: false })
const autostartEnabled = ref(false)
const autostartMode = ref('backend')

// ── 附件大小限制 ──
const maxFileSizeMB = ref(50)
const settingsSaving = ref(false)

// ── 工作文件夹 ──
const openingWorkspace = ref(false)

async function openWorkspace() {
  openingWorkspace.value = true
  try {
    await http.post('/process/open-workspace')
    ElMessage.success('已打开工作文件夹')
  } catch {
    ElMessage.error('打开失败')
  }
  openingWorkspace.value = false
}

async function refreshSettings() {
  try {
    const res = await http.get('/process/settings')
    maxFileSizeMB.value = res.max_file_size_mb ?? 50
  } catch {
    // 默认 50MB
  }
}

async function saveFileSize() {
  settingsSaving.value = true
  try {
    await http.put('/process/settings', { max_file_size_mb: maxFileSizeMB.value })
    ElMessage.success('附件大小限制已更新')
  } catch {
    ElMessage.error('保存失败')
  }
  settingsSaving.value = false
}

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

async function confirmRestart(title) {
  try {
    await ElMessageBox.confirm(title, '确认操作', {
      confirmButtonText: '确认重启',
      cancelButtonText: '取消',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}

async function restartBackend() {
  if (!(await confirmRestart('确认重启后端服务？\n重启期间 API 将短暂不可用。'))) return
  restarting.value.backend = true
  try {
    await http.post('/process/restart-backend')
    ElMessage.success('后端服务正在重启...')
  } catch {
    ElMessage.success('后端服务正在重启...')
  }
  status.value.backend = false
  restarting.value.backend = false
}

async function restartFrontend() {
  if (!(await confirmRestart('确认重启前端服务？\n重启期间页面将刷新。'))) return
  restarting.value.frontend = true
  try {
    await http.post('/process/restart-frontend')
    ElMessage.success('前端服务正在重启...')
  } catch {
    ElMessage.success('前端服务正在重启...')
  }
  status.value.frontend = false
  restarting.value.frontend = false
}

async function restartAll() {
  if (!(await confirmRestart('确认重启所有服务？\n重启后页面将自动刷新。'))) return
  restarting.value.all = true
  try {
    await http.post('/process/restart-all')
    ElMessage.success('所有服务正在重启...')
  } catch {
    ElMessage.success('所有服务正在重启...')
  }
  // 后端重启后刷新页面
  setTimeout(() => { window.location.reload() }, 2000)
}

onMounted(() => {
  refreshStatus()
  refreshAutostart()
  refreshSettings()
})
</script>

<style scoped>
.settings-page {
  max-width: 640px;
  margin: 0 auto;
}
.page-title {
  font-size: 20px; font-weight: 600; margin-bottom: 20px; color: #2c2c2a;
}

/* 卡片 */
.sec-card { margin-bottom: 14px; border-radius: 8px; }
.sec-card :deep(.el-card__body) { padding: 10px 16px 14px; }

.card-head {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 14px; font-weight: 600; color: #444;
}

/* 服务状态 */
.svc-grid { display: flex; flex-direction: column; gap: 6px; }
.svc-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 12px; border-radius: 6px; background: #f8f8f6;
}
.svc-row.on { background: #f0faf0; }
.dot {
  width: 10px; height: 10px; border-radius: 50%;
  background: #ccc; flex-shrink: 0;
}
.dot.on { background: #52c41a; }
.svc-name { font-size: 13px; font-weight: 500; color: #2c2c2a; }
.svc-stat { font-size: 12px; color: #888; }
.card-foot { margin-top: 8px; display: flex; justify-content: flex-end; }

/* 自启动 */
.hint { font-size: 12px; color: #666; line-height: 1.5; margin-bottom: 6px; }
.hint.muted { color: #aaa; }
.radio-compact { margin: 0 0 4px !important; font-size: 13px; }

/* 文件 */
.file-row {
  display: flex; align-items: center; gap: 8px;
  padding: 5px 0;
}
.file-row + .file-row { border-top: 1px solid #f0f0ee; }
.file-lbl { font-size: 13px; color: #444; width: 90px; flex-shrink: 0; }
.unit { font-size: 12px; color: #888; }
</style>
