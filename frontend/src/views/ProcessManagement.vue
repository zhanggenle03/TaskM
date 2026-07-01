<template>
  <div class="settings-page">
    <h1 class="page-title">通用设置</h1>

    <div class="cards-row">

      <!-- ── 卡片：服务 ── -->
      <div class="card">
        <div class="card-title">服务</div>

        <!-- 运行状态 -->
        <div class="setting-item">
          <span class="label">运行状态</span>
          <div class="control">
            <div class="status-group">
              <template v-if="isStandalone">
                <span class="status-item">
                  <span class="status-dot" :class="dotClass(status.backend)"></span>
                  TaskM <span class="status-port">{{ backendPort }}</span>
                  <span v-if="status.backend === null" class="status-text-loading">检测中</span>
                </span>
              </template>
              <template v-else>
                <span class="status-item">
                  <span class="status-dot" :class="dotClass(status.backend)"></span>
                  后端 <span class="status-port">{{ backendPort }}</span>
                  <span v-if="status.backend === null" class="status-text-loading">检测中</span>
                </span>
                <span class="status-item">
                  <span class="status-dot" :class="dotClass(status.frontend)"></span>
                  前端 <span class="status-port">{{ frontendPort }}</span>
                  <span v-if="status.frontend === null" class="status-text-loading">检测中</span>
                </span>
              </template>
            </div>
            <div class="btn-group">
              <button class="btn" @click="portDialogVisible = true">修改端口</button>
              <button class="btn btn-danger" @click="shutdownService" :disabled="shuttingDown || !status.backend">关闭服务</button>
            </div>
          </div>
        </div>

        <!-- 端口配置对话框 -->
        <el-dialog v-model="portDialogVisible" title="端口配置" width="420px" :close-on-click-modal="false">
          <div class="port-dialog-body">
            <template v-if="isStandalone">
              <div class="port-field">
                <span class="port-field-label">服务端口</span>
                <input class="port-input" v-model.number="editBackendPort" type="number" min="1024" max="65535" />
              </div>
            </template>
            <template v-else>
              <div class="port-field">
                <span class="port-field-label">后端端口</span>
                <input class="port-input" v-model.number="editBackendPort" type="number" min="1024" max="65535" />
              </div>
              <div class="port-field">
                <span class="port-field-label">前端端口</span>
                <input class="port-input" v-model.number="editFrontendPort" type="number" min="1024" max="65535" />
              </div>
            </template>
            <div class="port-hint">修改后需重启服务生效</div>
          </div>
          <template #footer>
            <button class="btn" @click="portDialogVisible = false">取消</button>
            <button class="btn btn-primary" @click="savePorts" :disabled="portSaving">{{ portSaving ? '保存中...' : '保存' }}</button>
          </template>
        </el-dialog>

        <!-- 开机自启动 -->
        <div class="setting-item">
          <span class="label">开机自启动</span>
          <div class="control">
            <el-switch v-model="autostartEnabled" @change="onAutostartToggle" :loading="saving" />
            <span class="toggle-status">状态：<span :class="autostartEnabled ? 'on' : 'off'">{{ autostartEnabled ? '已开启' : '已关闭' }}</span></span>
          </div>
          <div class="hint">开机自动启动，图标最小化到系统托盘</div>
        </div>
      </div>

      <!-- ── 卡片：工作区 ── -->
      <div class="card">
        <div class="card-title">工作区</div>

        <!-- 工作文件夹 -->
        <div class="setting-item">
          <span class="label">工作文件夹</span>
          <div class="control">
            <span class="workspace-path" :title="workspacePath"><span class="ws-text">{{ workspacePath }}</span></span>
            <button class="btn" @click="openWorkspace" :disabled="openingWorkspace">打开</button>
          </div>
        </div>

        <!-- 附件大小限制 -->
        <div class="setting-item">
          <span class="label">附件限制 <span class="sub">1-500MB</span></span>
          <div class="control">
            <el-slider v-model="maxFileSizeMB" :min="1" :max="500" :disabled="settingsSaving" style="flex:1;min-width:100px" />
            <span class="slider-value">{{ maxFileSizeMB }}<small>MB</small></span>
            <button class="btn" @click="saveFileSize" :disabled="settingsSaving">保存</button>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import http from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const refreshing = ref(false)
const saving = ref(false)
const status = ref({ backend: null, frontend: null })
const isStandalone = ref(false)
const autostartEnabled = ref(false)

// ── 端口配置 ──
const backendPort = ref(8000)
const frontendPort = ref(5173)
const editBackendPort = ref(8000)
const editFrontendPort = ref(5173)
const portSaving = ref(false)
const portDialogVisible = ref(false)

// ── 附件大小限制 ──
const maxFileSizeMB = ref(50)
const settingsSaving = ref(false)

// ── 工作文件夹 ──
const openingWorkspace = ref(false)
const workspacePath = ref('')

// ── 关闭服务 ──
const shuttingDown = ref(false)

function dotClass(val) {
  if (val === null) return 'loading'
  return val ? 'on' : 'off'
}

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
    backendPort.value = res.backend_port ?? 8000
    frontendPort.value = res.frontend_port ?? 5173
    editBackendPort.value = backendPort.value
    editFrontendPort.value = frontendPort.value
  } catch {
    // 默认值
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

async function savePorts() {
  const bp = editBackendPort.value
  const fp = editFrontendPort.value
  if (bp < 1024 || bp > 65535 || fp < 1024 || fp > 65535) {
    ElMessage.warning('端口范围：1024~65535')
    return
  }
  portSaving.value = true
  try {
    const payload = { backend_port: bp }
    if (!isStandalone.value) {
      payload.frontend_port = fp
    }
    await http.put('/process/settings', payload)
    backendPort.value = bp
    frontendPort.value = fp
    portDialogVisible.value = false
    ElMessage.success('端口已保存，重启后生效')
  } catch {
    ElMessage.error('保存失败')
  }
  portSaving.value = false
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

async function refreshWorkspacePath() {
  try {
    const res = await http.get('/process/workspace')
    workspacePath.value = res.path
  } catch {
    workspacePath.value = ''
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
  refreshWorkspacePath()
})
</script>

<style scoped>
.settings-page {
  width: 100%;
}

/* ── 页面标题 ── */
.page-title {
  font-size: 20px; font-weight: 600;
  margin-bottom: 24px;
}

/* ── 两卡片并排 ── */
.cards-row {
  display: flex;
  gap: 20px;
  align-items: stretch;
}

/* ── 独立卡片 ── */
.card {
  flex: 1;
  background: #fff;
  border-radius: 14px;
  padding: 22px 24px 24px;
  border: 1px solid #e9edf2;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.card-title {
  font-size: 13px; font-weight: 600;
  color: #64748b; letter-spacing: 0.5px;
  text-transform: uppercase;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f4f8;
}

/* ── 设置项 ── */
.setting-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.setting-item .label {
  font-size: 14px; font-weight: 500;
  color: #1e293b;
  display: flex; align-items: center; gap: 6px;
}
.setting-item .label .sub {
  font-weight: 400; color: #94a3b8; font-size: 12px;
}
.setting-item .control {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* ── 状态指示 ── */
.status-group {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.status-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #334155;
}
.status-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #ddd;
  flex-shrink: 0;
}
.status-dot.on { background: #22c55e; }
.status-dot.off { background: #ef4444; }
.status-dot.loading { background: #94a3b8; animation: pulse-dot 1.2s ease-in-out infinite; }
@keyframes pulse-dot {
  0%, 100% { opacity: 0.4; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}
.status-text-loading { font-size: 12px; color: #94a3b8; }
.status-port {
  font-family: monospace; font-size: 12px;
  color: #64748b; background: #f1f4f9;
  padding: 0 8px; border-radius: 30px;
}

/* ── 按钮组（修改端口 + 关闭服务） ── */
.btn-group {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

/* ── 通用按钮 ── */
.btn {
  border: 1px solid #d1d9e6;
  background: #fafbfc;
  padding: 2px 14px;
  border-radius: 30px;
  font-size: 12px;
  cursor: pointer;
  transition: 0.15s;
  color: #334155;
  white-space: nowrap;
  line-height: 24px;
  font-family: inherit;
}
.btn:hover { background: #eef2f6; border-color: #b0c0d0; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-danger {
  color: #b91c1c; border-color: #fecaca; background: #fef2f2;
}
.btn-danger:hover { background: #fee2e2; }
.btn-primary {
  color: #fff; border-color: #3b82f6; background: #3b82f6;
}
.btn-primary:hover { background: #2563eb; border-color: #2563eb; }

/* ── 自启动状态文字 ── */
.toggle-status { font-size: 13px; color: #475569; }
.toggle-status .on { color: #16a34a; font-weight: 600; }
.toggle-status .off { color: #dc2626; font-weight: 600; }

/* ── 滑块值 ── */
.slider-value {
  font-size: 16px; font-weight: 600;
  color: #0f172a;
  min-width: 50px;
  text-align: center;
}
.slider-value small {
  font-size: 12px; font-weight: 400; color: #94a3b8;
}

/* ── 提示小字 ── */
.hint { font-size: 12px; color: #94a3b8; line-height: 1.4; margin-top: 2px; }

/* ── 工作目录路径 ── */
.workspace-path {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 2px 12px;
  flex: 1;
  min-width: 0;
  cursor: default;
  transition: border-color 0.15s, background 0.15s;
}
.workspace-path:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}
.ws-text {
  font-size: 12px;
  color: #475569;
  line-height: 24px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  letter-spacing: 0.2px;
}

/* ── 端口对话框 ── */
.port-dialog-body {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 6px 0;
}
.port-field {
  display: flex;
  align-items: center;
  gap: 12px;
}
.port-field-label {
  font-size: 14px;
  color: #334155;
  min-width: 72px;
}
.port-hint {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}
.port-input {
  width: 120px;
  padding: 4px 10px;
  border: 1px solid #d1d9e6;
  border-radius: 6px;
  font-size: 14px;
  font-family: monospace;
  text-align: center;
  color: #1e293b;
  background: #fff;
  outline: none;
  transition: border-color 0.15s;
}
.port-input:focus {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59,130,246,0.15);
}
.port-input::-webkit-inner-spin-button { opacity: 1; }
</style>
