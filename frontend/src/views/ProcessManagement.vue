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

      <!-- ── 卡片：备份与恢复 ── -->
      <div class="card card-backup">
        <div class="card-title">备份与恢复</div>

        <!-- 手动备份 -->
        <div class="setting-item">
          <span class="label">手动备份</span>
          <div class="control">
            <select class="bk-select" v-model="manualBackupScope">
              <option value="full">全部（数据库+配置+附件）</option>
              <option value="db_config">数据库+配置</option>
              <option value="db_only">仅数据库</option>
            </select>
            <button class="btn btn-primary" @click="doManualBackup" :disabled="backingUp">
              {{ backingUp ? '备份中...' : '立即备份' }}
            </button>
            <button class="btn" @click="projectBackupDialogVisible = true">备份单个项目</button>
          </div>
        </div>

        <!-- 定时备份 + 备份文件（同一行） -->
        <div class="setting-row">
          <div class="setting-item half">
            <span class="label">定时备份</span>
            <div class="control">
              <el-switch v-model="bkSchedule.enabled" @change="onScheduleToggle" :loading="scheduleSaving" />
              <button class="btn" @click="scheduleDialogVisible = true">设置</button>
            </div>
          </div>
          <div class="setting-item half">
            <span class="label">备份文件</span>
            <div class="control">
              <span class="bk-count" v-if="backups.length">{{ backups.length }} 个</span>
              <span class="bk-count empty" v-else>无</span>
              <button class="btn" @click="openBackupManager">管理</button>
            </div>
          </div>
        </div>

        <!-- 还原备份 -->
        <div class="setting-item">
          <span class="label">还原备份</span>
          <div class="tab-bar">
            <button class="tab-btn" :class="{ active: restoreTab === 'list' }" @click="restoreTab = 'list'">从备份列表</button>
            <button class="tab-btn" :class="{ active: restoreTab === 'upload' }" @click="restoreTab = 'upload'">上传文件</button>
          </div>
          <div class="control" style="margin-top:2px">
            <template v-if="restoreTab === 'list'">
              <select class="bk-select" v-model="restoreSelectedFile" style="flex:1;min-width:140px">
                <option value="">-- 选择备份文件 --</option>
                <optgroup label="系统备份">
                  <option v-for="b in systemBackups" :key="b.filename" :value="b.filename">{{ b.filename }}</option>
                </optgroup>
                <optgroup label="项目备份">
                  <option v-for="b in projectBackups" :key="b.filename" :value="b.filename">{{ b.filename }}</option>
                </optgroup>
              </select>
            </template>
            <template v-else>
              <input ref="restoreInput" type="file" accept=".zip" style="display:none" @change="onRestoreFileChange" />
              <button class="btn" @click="$refs.restoreInput.click()" :disabled="restoring">
                {{ restoreFile ? restoreFile.name : '选择备份文件' }}
              </button>
            </template>
            <template v-if="isProjectBackupSelected">
              <span class="bk-tag">项目</span>
              <select class="bk-select" v-model="projectRestoreMode">
                <option value="overwrite">覆盖</option>
                <option value="new">新建</option>
              </select>
            </template>
            <template v-else>
              <select class="bk-select" v-model="restoreScope">
                <option value="auto">自动</option>
                <option value="full">全部</option>
                <option value="db_config">数据库+配置</option>
                <option value="db_only">仅数据库</option>
              </select>
            </template>
            <button class="btn btn-danger" @click="executeRestore" :disabled="!canRestore || restoring">
              {{ restoring ? '还原中...' : '开始还原' }}
            </button>
          </div>
          <div class="bk-restore-warn" v-if="!isProjectBackupSelected">⚠ 还原将覆盖现有数据，建议先手动备份</div>
        </div>

      </div>
    </div>

    <!-- ═══ 定时备份设置弹窗 ═══ -->
    <el-dialog v-model="scheduleDialogVisible" title="定时备份设置" width="480px" :close-on-click-modal="false" @closed="loadSchedule">
      <div class="bk-dialog-body">
        <div class="bk-dlg-row">
          <span class="bk-dlg-label">启用</span>
          <el-switch v-model="bkSchedule.enabled" />
        </div>
        <div class="bk-dlg-row">
          <span class="bk-dlg-label">频率</span>
          <select class="bk-select" v-model="bkSchedule.frequency" @change="onFrequencyChange">
            <option value="daily">每天（24 小时）</option>
            <option value="weekly">每周（168 小时）</option>
            <option value="monthly">每月（720 小时）</option>
            <option value="manual">手动（不自动）</option>
          </select>
          <span class="bk-dlg-hint">{{ intervalHint }}</span>
        </div>
        <div class="bk-dlg-row">
          <span class="bk-dlg-label">范围</span>
          <select class="bk-select" v-model="bkSchedule.scope">
            <option value="full">全部（数据库+配置+附件）</option>
            <option value="db_config">数据库+配置</option>
            <option value="db_only">仅数据库</option>
          </select>
        </div>
        <div class="bk-dlg-row">
          <span class="bk-dlg-label">保留</span>
          <select class="bk-select" v-model.number="bkSchedule.max_keep">
            <option v-for="n in [3,5,7,10,15,20,30,50]" :key="n" :value="n">{{ n }} 份</option>
          </select>
          <span class="bk-dlg-hint">超出自动清理旧备份</span>
        </div>
      </div>
      <template #footer>
        <button class="btn" @click="scheduleDialogVisible = false">取消</button>
        <button class="btn btn-primary" @click="saveScheduleFromDialog" :disabled="scheduleSaving">
          {{ scheduleSaving ? '保存中...' : '保存' }}
        </button>
      </template>
    </el-dialog>

    <!-- ═══ 备份管理弹窗 ═══ -->
    <el-dialog v-model="backupDialogVisible" title="备份管理" width="600px" :close-on-click-modal="false" @opened="refreshBackups">
      <div class="bk-dialog-body">
        <!-- 备份列表 -->
        <div class="bk-list" v-if="backups.length">
          <div class="bk-list-header">
            <span class="bk-name">文件名</span>
            <span class="bk-size">大小</span>
            <span class="bk-date">创建时间</span>
            <span class="bk-actions-hdr">操作</span>
          </div>
          <div class="bk-list-item" v-for="b in backups" :key="b.filename">
            <span class="bk-name" :title="b.filename">{{ b.filename }}</span>
            <span class="bk-size">{{ formatSize(b.size) }}</span>
            <span class="bk-date">{{ formatDate(b.created_at) }}</span>
            <div class="bk-actions">
              <button class="btn btn-sm" @click="downloadBackupFile(b.filename)">下载</button>
              <button class="btn btn-sm btn-danger" @click="confirmDeleteBackup(b.filename)">删除</button>
            </div>
          </div>
        </div>
        <div v-else class="bk-empty">暂无备份文件</div>
      </div>
    </el-dialog>

    <!-- ═══ 备份单个项目弹窗 ═══ -->
    <el-dialog v-model="projectBackupDialogVisible" title="备份单个项目" width="480px" :close-on-click-modal="false" @opened="refreshProjects">
      <div class="bk-dialog-body">
        <div class="bk-dlg-row">
          <span class="bk-dlg-label">项目</span>
          <select class="bk-select" v-model="exportProjectId" style="flex:1">
            <option value="" disabled>-- 选择项目 --</option>
            <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.display_id }} - {{ p.name }}</option>
          </select>
        </div>
        <div class="bk-dlg-row">
          <span class="bk-dlg-label">选项</span>
          <label class="bk-check-label">
            <input type="checkbox" v-model="exportIncludeUploads" />
            包含附件
          </label>
        </div>
        <div class="bk-dlg-hint">将该项目的所有数据（项目信息、任务、需求、沟通记录、配置、附件）打包为备份文件</div>
      </div>
      <template #footer>
        <button class="btn" @click="projectBackupDialogVisible = false">取消</button>
        <button class="btn btn-primary" @click="doProjectBackup" :disabled="!exportProjectId || exportingProject">
          {{ exportingProject ? '备份中...' : '备份' }}
        </button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed } from 'vue'
import http from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createBackup, listBackups, deleteBackup as apiDeleteBackup,
  getBackupDownloadUrl, restoreBackup,
  exportProjectBackup, getBackupProjects,
  getBackupSchedule, setBackupSchedule, backupSingleProject, restoreProjectBackup, restoreProjectBackupUpload, restoreByName,
} from '../api'

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

// ── 备份与恢复 ──
const manualBackupScope = ref('full')
const backingUp = ref(false)
const backups = ref([])
const scheduleSaving = ref(false)
const scheduleDialogVisible = ref(false)
const backupDialogVisible = ref(false)
const projectBackupDialogVisible = ref(false)
const bkSchedule = reactive({
  enabled: false,
  frequency: 'daily',
  scope: 'full',
  max_keep: 10,
  interval_hours: 24,
  last_backup_at: null,
})
const restoreFile = ref(null)
const restoreScope = ref('auto')
const restoring = ref(false)
const restoreTab = ref('list')
const restoreSelectedFile = ref('')

const systemBackups = computed(() =>
  backups.value.filter(b => !b.filename.startsWith('project_'))
)
const projectBackups = computed(() =>
  backups.value.filter(b => b.filename.startsWith('project_'))
)
const isProjectBackupSelected = computed(() => {
  const fn = restoreTab.value === 'list' ? restoreSelectedFile.value : restoreFile.value?.name
  return fn?.startsWith('project_')
})
const canRestore = computed(() => {
  if (restoreTab.value === 'list') return !!restoreSelectedFile.value
  return !!restoreFile.value
})
const projects = ref([])
const exportProjectId = ref('')
const exportIncludeUploads = ref(true)
const exportingProject = ref(false)
const projectRestoreMode = ref('overwrite')
const projectRestoring = ref(false)

const intervalHint = computed(() => {
  if (bkSchedule.frequency === 'manual') return '仅手动触发'
  const h = bkSchedule.interval_hours || 24
  if (h >= 24) return `距上次备份 ≥ ${h / 24} 天时自动执行`
  return `距上次备份 ≥ ${h} 小时时自动执行`
})

function onFrequencyChange() {
  const map = { daily: 24, weekly: 168, monthly: 720, manual: 0 }
  bkSchedule.interval_hours = map[bkSchedule.frequency] || 24
}

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

// ── 备份相关 ──

async function doManualBackup() {
  backingUp.value = true
  try {
    const res = await createBackup(manualBackupScope.value)
    ElMessage.success(`备份完成：${res.filename}`)
    await refreshBackups()
  } catch {
    ElMessage.error('备份失败')
  }
  backingUp.value = false
}

async function refreshBackups() {
  try {
    backups.value = await listBackups()
  } catch {
    backups.value = []
  }
}

async function onScheduleToggle(val) {
  scheduleSaving.value = true
  try {
    await setBackupSchedule({ enabled: val })
  } catch {
    bkSchedule.enabled = !val
    ElMessage.error('切换失败')
  }
  scheduleSaving.value = false
}

function openBackupManager() {
  backupDialogVisible.value = true
  refreshBackups()
  // 清空 restore file
  restoreFile.value = null
  if (restoreInput.value) restoreInput.value.value = ''
}

async function loadSchedule() {
  try {
    const s = await getBackupSchedule()
    Object.assign(bkSchedule, s)
  } catch {
    // ignore
  }
}

async function saveScheduleFromDialog() {
  scheduleSaving.value = true
  try {
    await setBackupSchedule({
      enabled: bkSchedule.enabled,
      frequency: bkSchedule.frequency,
      scope: bkSchedule.scope,
      max_keep: bkSchedule.max_keep,
      interval_hours: bkSchedule.interval_hours,
    })
    scheduleDialogVisible.value = false
    ElMessage.success('定时备份设置已保存')
  } catch {
    ElMessage.error('保存失败')
  }
  scheduleSaving.value = false
}

async function downloadBackupFile(filename) {
  const url = getBackupDownloadUrl(filename)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

async function confirmDeleteBackup(filename) {
  try {
    await ElMessageBox.confirm(
      `确定删除备份文件「${filename}」？`,
      '确认删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await apiDeleteBackup(filename)
    ElMessage.success('已删除')
    await refreshBackups()
  } catch {
    ElMessage.error('删除失败')
  }
}

function onRestoreFileChange(e) {
  restoreFile.value = e.target.files?.[0] || null
}

const restoreInput = ref(null)

async function executeRestore() {
  const isProjectBackup = restoreTab.value === 'list'
    ? restoreSelectedFile.value?.startsWith('project_')
    : restoreFile.value?.name?.startsWith('project_')

  if (isProjectBackup) {
    // ── 项目备份还原 ──
    const filename = restoreTab.value === 'list'
      ? restoreSelectedFile.value
      : restoreFile.value.name
    if (!filename) {
      ElMessage.warning('请先选择备份文件')
      return
    }
    try {
      await ElMessageBox.confirm(
        projectRestoreMode.value === 'overwrite'
          ? '⚠️ 将覆盖现有项目！\n\n覆盖模式会查找同 display_id 的项目并完全替换其所有数据。\n确认要继续吗？'
          : '将新建一个项目导入备份数据。\n确认要继续吗？',
        '还原项目',
        { confirmButtonText: '确认还原', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
    projectRestoring.value = true
    try {
      let res
      if (restoreTab.value === 'list') {
        res = await restoreProjectBackup(filename, projectRestoreMode.value)
      } else {
        res = await restoreProjectBackupUpload(restoreFile.value, projectRestoreMode.value)
      }
      ElMessage.success(res.summary || '项目还原成功')
      refreshBackups()
    } catch (err) {
      const msg = err?.response?.data?.detail || '项目还原失败'
      ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
    projectRestoring.value = false
    restoreSelectedFile.value = ''
    if (restoreTab.value === 'upload') {
      restoreFile.value = null
      if (restoreInput.value) restoreInput.value.value = ''
    }
  } else {
    // ── 系统备份还原 ──
    if (restoreTab.value === 'list') {
      // 从列表还原
      try {
        await ElMessageBox.confirm(
          '⚠️ 还原操作将覆盖当前数据！\n\n建议在还原前先创建一次手动备份。\n确认要继续吗？',
          '危险操作',
          { confirmButtonText: '确认还原', cancelButtonText: '取消', type: 'warning' }
        )
      } catch {
        return
      }
      restoring.value = true
      try {
        const res = await restoreByName(restoreSelectedFile.value, restoreScope.value)
        if (res.success) {
          ElMessage.success(`还原成功！已还原 ${res.restored?.length || 0} 项`)
          if (res.snapshot) {
            ElMessage.info(`还原前快照已保存：${res.snapshot}`)
          }
        } else {
          ElMessage.error(`还原失败：${res.error || '未知错误'}`)
        }
      } catch (err) {
        ElMessage.error('还原请求失败')
      }
      restoring.value = false
      restoreSelectedFile.value = ''
      return
    }
    // 上传文件还原（原有逻辑）
    if (!restoreFile.value) {
      ElMessage.warning('请先选择备份文件')
      return
    }
    try {
      await ElMessageBox.confirm(
        '⚠️ 还原操作将覆盖当前数据！\n\n建议在还原前先创建一次手动备份。\n确认要继续吗？',
        '危险操作',
        { confirmButtonText: '确认还原', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
    restoring.value = true
    try {
      const res = await restoreBackup(restoreFile.value, restoreScope.value)
      if (res.success) {
        ElMessage.success(`还原成功！已还原 ${res.restored?.length || 0} 项`)
        if (res.snapshot) {
          ElMessage.info(`还原前快照已保存：${res.snapshot}`)
        }
      } else {
        ElMessage.error(`还原失败：${res.error || '未知错误'}`)
      }
    } catch (err) {
      ElMessage.error('还原请求失败')
    }
    restoring.value = false
    restoreFile.value = null
    if (restoreInput.value) restoreInput.value.value = ''
  }
}

function isProjectBackup(filename) {
  return filename?.startsWith('project_')
}

async function refreshProjects() {
  try {
    projects.value = await getBackupProjects()
  } catch {
    projects.value = []
  }
}

async function doProjectBackup() {
  if (!exportProjectId.value) return
  exportingProject.value = true
  try {
    const res = await backupSingleProject(exportProjectId.value, exportIncludeUploads.value)
    ElMessage.success(`项目备份完成：${res.filename}`)
    projectBackupDialogVisible.value = false
    refreshBackups()
  } catch {
    ElMessage.error('备份失败')
  }
  exportingProject.value = false
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024; i++
  }
  return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

function formatDate(isoStr) {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(() => {
  refreshStatus()
  refreshAutostart()
  refreshSettings()
  refreshWorkspacePath()
  refreshBackups()
  loadSchedule()
  refreshProjects()
})
</script>

<style scoped>
.settings-page { width: 100%; }

.page-title { font-size: 18px; font-weight: 600; margin-bottom: 16px; }

/* ── 两卡片一行 ── */
.cards-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px 20px 18px;
  border: 1px solid #e9edf2;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-title {
  font-size: 12px; font-weight: 600;
  color: #64748b; letter-spacing: 0.5px;
  text-transform: uppercase;
  padding-bottom: 6px;
  border-bottom: 1px solid #f1f4f8;
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.setting-item .label {
  font-size: 13px; font-weight: 500;
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
.status-group { display: flex; gap: 16px; flex-wrap: wrap; }
.status-item {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: #334155;
}
.status-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: #ddd; flex-shrink: 0;
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
.btn-group { display: flex; align-items: center; gap: 8px; margin-left: auto; }

/* ── 通用按钮 ── */
.btn {
  border: 1px solid #d1d9e6; background: #fafbfc;
  padding: 2px 14px; border-radius: 30px; font-size: 12px;
  cursor: pointer; transition: 0.15s; color: #334155;
  white-space: nowrap; line-height: 24px; font-family: inherit;
}
.btn:hover { background: #eef2f6; border-color: #b0c0d0; }
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-sm { padding: 0 10px; font-size: 11px; line-height: 22px; }
.btn-danger { color: #b91c1c; border-color: #fecaca; background: #fef2f2; }
.btn-danger:hover { background: #fee2e2; }
.btn-primary { color: #fff; border-color: #3b82f6; background: #3b82f6; }
.btn-primary:hover { background: #2563eb; border-color: #2563eb; }

.toggle-status { font-size: 13px; color: #475569; }
.toggle-status .on { color: #16a34a; font-weight: 600; }
.toggle-status .off { color: #dc2626; font-weight: 600; }

.slider-value {
  font-size: 16px; font-weight: 600; color: #0f172a;
  min-width: 50px; text-align: center;
}
.slider-value small { font-size: 12px; font-weight: 400; color: #94a3b8; }

.hint { font-size: 11px; color: #94a3b8; line-height: 1.3; }

/* ── 还原警告 ── */
.bk-restore-warn { font-size: 11px; color: #d97706; margin-top: 2px; }

/* ── 标签切换栏 ── */
.tab-bar { display: flex; gap: 2px; }
.tab-btn {
  border: 1px solid #d1d9e6; background: #fafbfc;
  padding: 0 10px; border-radius: 30px; font-size: 11px;
  cursor: pointer; color: #64748b; line-height: 22px;
  font-family: inherit; transition: 0.15s;
}
.tab-btn:hover { background: #eef2f6; }
.tab-btn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }

/* ── 项目备份标记 ── */
.bk-tag {
  display: inline-block; font-size: 10px; font-weight: 600;
  color: #3b82f6; background: #eff6ff;
  padding: 0 6px; border-radius: 20px; line-height: 20px;
  white-space: nowrap;
}

.workspace-path {
  display: inline-flex; align-items: center; gap: 6px;
  background: #f8fafc; border: 1px solid #e2e8f0;
  border-radius: 6px; padding: 2px 12px; flex: 1; min-width: 0;
  cursor: default; transition: border-color 0.15s, background 0.15s;
}
.workspace-path:hover { background: #f1f5f9; border-color: #cbd5e1; }
.ws-text {
  font-size: 12px; color: #475569; line-height: 24px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  letter-spacing: 0.2px;
}

/* ── 端口对话框 ── */
.port-dialog-body { display: flex; flex-direction: column; gap: 14px; padding: 6px 0; }
.port-field { display: flex; align-items: center; gap: 12px; }
.port-field-label { font-size: 14px; color: #334155; min-width: 72px; }
.port-hint { font-size: 12px; color: #94a3b8; margin-top: 2px; }
.port-input {
  width: 120px; padding: 4px 10px; border: 1px solid #d1d9e6;
  border-radius: 6px; font-size: 14px; font-family: monospace;
  text-align: center; color: #1e293b; background: #fff;
  outline: none; transition: border-color 0.15s;
}
.port-input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }
.port-input::-webkit-inner-spin-button { opacity: 1; }

/* ── 备份卡片特有（紧凑布局） ── */
.card-backup {
  min-width: 360px;
}

.card-backup .setting-row {
  display: flex; gap: 16px;
}
.card-backup .setting-item.half {
  flex: 1; min-width: 0;
}
.card-backup .setting-item.half .control {
  flex-wrap: nowrap;
}

.bk-select {
  border: 1px solid #d1d9e6; border-radius: 30px;
  padding: 2px 10px; font-size: 12px; color: #1e293b;
  background: #fff; line-height: 24px; outline: none;
  font-family: inherit; cursor: pointer;
  box-sizing: border-box; height: 30px;
}
.bk-select:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.1); }

/* ── 备份文件数量标识 ── */
.bk-count {
  font-size: 12px; font-weight: 500; color: #334155;
  min-width: 24px;
}
.bk-count.empty { color: #94a3b8; }

/* ── 备份弹窗 ── */
.bk-dialog-body {
  display: flex; flex-direction: column; gap: 14px;
}
.bk-dlg-row {
  display: flex; align-items: center; gap: 10px;
}
.bk-dlg-label {
  font-size: 13px; color: #475569; min-width: 56px; flex-shrink: 0;
}
.bk-dlg-sep { font-size: 12px; color: #94a3b8; }
.bk-dlg-hint { font-size: 11px; color: #94a3b8; }
.bk-restore-info { font-size: 12px; color: #475569; }
.bk-restore-info code { font-size: 11px; background: #f1f5f9; padding: 1px 6px; border-radius: 4px; }

/* ── 弹窗内备份列表 ── */
.bk-list {
  display: flex; flex-direction: column;
  max-height: 260px; overflow-y: auto;
  border: 1px solid #e2e8f0; border-radius: 6px;
  background: #fafbfc;
}
.bk-list-header {
  display: flex; align-items: center; gap: 6px;
  padding: 5px 10px; font-size: 11px; font-weight: 600;
  color: #64748b; background: #f1f5f9;
  border-bottom: 1px solid #e2e8f0;
  position: sticky; top: 0; z-index: 1;
}
.bk-list-item {
  display: flex; align-items: center; gap: 6px;
  padding: 4px 10px; font-size: 12px;
  border-bottom: 1px solid #f1f4f8;
}
.bk-list-item:last-child { border-bottom: none; }
.bk-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; color: #1e293b;
  font-family: monospace; font-size: 11px;
}
.bk-size { color: #64748b; font-size: 11px; white-space: nowrap; min-width: 60px; text-align: right; }
.bk-date { color: #94a3b8; font-size: 11px; white-space: nowrap; min-width: 110px; }
.bk-actions-hdr { min-width: 88px; text-align: center; }
.bk-empty { font-size: 13px; color: #94a3b8; text-align: center; padding: 20px 0; }

/* ── 单项目导出 ── */
.bk-check-label {
  display: flex; align-items: center; gap: 3px;
  font-size: 11px; color: #475569;
  cursor: pointer; white-space: nowrap;
}
.bk-check-label input { margin: 0; }
</style>
