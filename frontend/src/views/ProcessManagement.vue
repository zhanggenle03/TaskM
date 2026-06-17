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
        <!-- 打包版：统一显示 -->
        <template v-if="isStandalone">
          <div class="svc-row" :class="{ on: status.backend }">
            <span class="dot" :class="{ on: status.backend }"></span>
            <span class="svc-name">TaskM 服务</span>
            <span class="svc-stat">{{ status.backend ? '运行中 (8000)' : '已停止' }}</span>
          </div>
        </template>
        <!-- 开发版：分开显示 -->
        <template v-else>
          <div class="svc-row" :class="{ on: status.backend }">
            <span class="dot" :class="{ on: status.backend }"></span>
            <span class="svc-name">后端服务</span>
            <span class="svc-stat">{{ status.backend ? '运行中 (8000)' : '已停止' }}</span>
          </div>
          <div class="svc-row" :class="{ on: status.frontend }">
            <span class="dot" :class="{ on: status.frontend }"></span>
            <span class="svc-name">前端页面</span>
            <span class="svc-stat">{{ status.frontend ? '运行中 (5173)' : '已停止' }}</span>
          </div>
        </template>
      </div>
      <div class="card-foot">
        <el-button size="small" type="danger" plain @click="shutdownService" :loading="shuttingDown" :disabled="!status.backend">
          关闭服务
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
      <p class="hint">开启后，开机时自动启动 TaskM 后台服务，图标最小化到系统托盘。</p>
      <p class="hint muted">右键托盘图标可打开浏览器或退出服务。</p>
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
const isStandalone = ref(false)
const autostartEnabled = ref(false)

// ── 附件大小限制 ──
const maxFileSizeMB = ref(50)
const settingsSaving = ref(false)

// ── 工作文件夹 ──
const openingWorkspace = ref(false)

// ── 关闭服务 ──
const shuttingDown = ref(false)

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

async function shutdownService() {
  try {
    await ElMessageBox.confirm('确认关闭 TaskM 服务？', '确认操作', {
      confirmButtonText: '确认关闭',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch {
    return
  }
  shuttingDown.value = true
  try {
    await http.post('/process/shutdown')
    ElMessage.success('服务已关闭')
    status.value.backend = false
    status.value.frontend = false
    // 等待提示显示后关闭标签页
    setTimeout(() => { window.close() }, 800)
  } catch {
    status.value.backend = false
    status.value.frontend = false
  }
  shuttingDown.value = false
}

async function refreshStatus() {
  refreshing.value = true
  try {
    const res = await http.get('/process/status')
    status.value = res
    isStandalone.value = res.standalone || false
  } catch {
    status.value = { backend: false, frontend: false }
  }
  refreshing.value = false
}

async function refreshAutostart() {
  try {
    const res = await http.get('/process/autostart')
    autostartEnabled.value = res.enabled
  } catch {
    autostartEnabled.value = false
  }
}

async function onAutostartToggle(val) {
  saving.value = true
  try {
    await http.put('/process/autostart', { mode: val ? 'on' : 'off' })
  } catch {
    autostartEnabled.value = !val
  }
  saving.value = false
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
