<template>
  <el-drawer
    :model-value="visible"
    title="文件管理"
    size="540px"
    :destroy-on-close="false"
    @update:model-value="onVisibleChange"
    @open="init"
  >
    <!-- 工具栏：面包屑 + 操作 -->
    <div class="fm-toolbar">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item v-for="(seg, i) in crumbPath" :key="i">
          <span :class="['fm-crumb', { 'fm-crumb-current': i === crumbPath.length - 1 }]" @click="navTo(seg.folder_id)">
            {{ seg.name }}
          </span>
        </el-breadcrumb-item>
      </el-breadcrumb>
      <div class="fm-actions">
        <el-button size="small" type="primary" plain @click="openCreateFolder">
          <el-icon><FolderAdd /></el-icon> 新建文件夹
        </el-button>
        <el-button size="small" type="primary" @click="pickUpload">
          <el-icon><Upload /></el-icon> 上传
        </el-button>
      </div>
    </div>

    <div class="fm-body">
      <!-- 文件夹树 -->
      <div class="fm-tree">
        <div class="fm-tree-title">文件夹</div>
        <el-scrollbar class="fm-tree-scroll">
          <el-tree
            :data="treeData"
            node-key="id"
            :props="{ label: 'name', children: 'children' }"
            :default-expand-all="true"
            :expand-on-click-node="false"
            :highlight-current="true"
            :current-node-key="currentFolderId ?? 'ROOT'"
            @node-click="onTreeClick"
          >
            <template #default="{ data }">
              <span class="fm-tree-node">
                <el-icon v-if="data.isRoot" style="margin-right:4px"><Folder /></el-icon>
                <el-icon v-else style="margin-right:4px" :color="data.children?.length ? '#E6A23C' : '#909399'"><Folder /></el-icon>
                <span>{{ data.name }}</span>
              </span>
            </template>
          </el-tree>
        </el-scrollbar>
      </div>

      <!-- 文件列表 -->
      <div class="fm-files">
        <el-scrollbar class="fm-file-scroll">
          <div v-if="currentFiles.length" class="fm-file-list">
            <div
              v-for="f in currentFiles"
              :key="f.id"
              :class="['fm-file-row', { 'fm-file-row-highlight': highlightId === f.id }]"
            >
              <el-icon class="fm-file-icon" :style="{ color: fileIconColor(f.mime_type, f.original_filename) }">
                <Document v-if="!isImageFile(f)" />
                <Picture v-else />
              </el-icon>
              <div class="fm-file-main">
                <a href="javascript:void(0)" class="fm-file-name" :title="f.original_filename" @click="preview(f)">
                  {{ f.original_filename }}
                </a>
                <div class="fm-file-meta">
                  <span v-if="f.source === 'comm'" class="fm-badge fm-badge-comm">沟通 #{{ f.source_comm_id }}</span>
                  <span v-else class="fm-badge fm-badge-manual">独立</span>
                  <span v-if="f.linked_count" class="fm-badge fm-badge-link">被引用 {{ f.linked_count }} 处</span>
                  <span class="fm-file-size">{{ formatSize(f.file_size) }}</span>
                </div>
              </div>
              <div class="fm-file-ops">
                <el-tooltip content="预览" placement="top"><el-button size="small" text @click="preview(f)"><el-icon><View /></el-icon></el-button></el-tooltip>
                <el-tooltip content="下载" placement="top"><el-button size="small" text @click="download(f)"><el-icon><Download /></el-icon></el-button></el-tooltip>
                <el-tooltip content="重命名" placement="top"><el-button size="small" text @click="openRenameFile(f)"><el-icon><Edit /></el-icon></el-button></el-tooltip>
                <el-tooltip content="移动" placement="top"><el-button size="small" text @click="openMoveFile(f)"><el-icon><Switch /></el-icon></el-button></el-tooltip>
                <el-tooltip content="删除" placement="top"><el-button size="small" text type="danger" @click="removeFile(f)"><el-icon><Delete /></el-icon></el-button></el-tooltip>
              </div>
            </div>
          </div>
          <el-empty v-else :description="currentFolderId === null ? '暂无文件，点击右上角上传' : '该文件夹为空'" :image-size="60" />
        </el-scrollbar>
      </div>
    </div>

    <input type="file" ref="fileInput" multiple style="display:none" @change="onFilesPicked" />

    <!-- 新建文件夹 -->
    <el-dialog v-model="createFolderVisible" title="新建文件夹" width="380px" append-to-body>
      <el-input v-model="newFolderName" placeholder="文件夹名称" maxlength="100" @keyup.enter="submitCreateFolder" />
      <template #footer>
        <el-button @click="createFolderVisible = false">取消</el-button>
        <el-button type="primary" :loading="creatingFolder" @click="submitCreateFolder">创建</el-button>
      </template>
    </el-dialog>

    <!-- 重命名 -->
    <el-dialog v-model="renameVisible" :title="renameTarget?.type === 'folder' ? '重命名文件夹' : '重命名文件'" width="380px" append-to-body>
      <el-input v-model="renameValue" maxlength="200" @keyup.enter="submitRename" />
      <template #footer>
        <el-button @click="renameVisible = false">取消</el-button>
        <el-button type="primary" :loading="renaming" @click="submitRename">保存</el-button>
      </template>
    </el-dialog>

    <!-- 移动（文件/文件夹） -->
    <el-dialog v-model="moveVisible" title="移动到文件夹" width="400px" append-to-body>
      <el-tree
        :data="moveTreeData"
        node-key="id"
        :props="{ label: 'name', children: 'children' }"
        :default-expand-all="true"
        :expand-on-click-node="false"
        :highlight-current="true"
        :current-node-key="moveTargetId ?? 'ROOT'"
        @node-click="onMoveTargetClick"
      >
        <template #default="{ data }">
          <span class="fm-tree-node">
            <el-icon style="margin-right:4px"><Folder /></el-icon>
            <span>{{ data.name }}</span>
          </span>
        </template>
      </el-tree>
      <div class="fm-move-hint">选择目标文件夹（根目录 = 不放入任何文件夹）</div>
      <template #footer>
        <el-button @click="moveVisible = false">取消</el-button>
        <el-button type="primary" :loading="moving" @click="submitMove">移动</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getTaskFiles, createTaskFolder, updateTaskFolder, deleteTaskFolder,
  uploadTaskFile, moveTaskFile, renameAttachment, deleteAttachment,
} from '../api'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projectId: { type: String, required: true },
  taskId: { type: String, required: true },
  locateId: { type: Number, default: null },
})
const emit = defineEmits(['update:visible'])

const loading = ref(false)
const folders = ref([])
const files = ref([])
const currentFolderId = ref(null) // null = 根层级
const highlightId = ref(null)

const fileInput = ref(null)
const uploadBusy = ref(false)

// ---- 数据加载 ----
const load = async () => {
  loading.value = true
  try {
    const data = await getTaskFiles(props.projectId, props.taskId)
    folders.value = data.folders || []
    files.value = data.files || []
  } finally {
    loading.value = false
  }
}

const init = () => {
  load()
}

// ---- 面包屑 ----
const crumbPath = computed(() => {
  const chain = []
  const fmap = {}
  const collect = (list) => list.forEach((n) => { fmap[n.id] = n; collect(n.children || []) })
  collect(folders.value)
  let cur = currentFolderId.value
  const seen = new Set()
  while (cur !== null && cur !== undefined && !seen.has(cur)) {
    seen.add(cur)
    const node = fmap[cur]
    if (!node) break
    chain.unshift({ name: node.name, folder_id: node.id })
    cur = node.parent_id
  }
  return [{ name: '全部文件', folder_id: null }, ...chain]
})

const navTo = (folderId) => {
  currentFolderId.value = folderId ?? null
  highlightId.value = null
}

// ---- 树 ----
const treeData = computed(() => [
  { id: 'ROOT', name: '全部文件', isRoot: true, children: folders.value },
])

const onTreeClick = (node) => {
  if (node.id === 'ROOT') currentFolderId.value = null
  else currentFolderId.value = node.id
  highlightId.value = null
}

const currentFiles = computed(() =>
  files.value.filter((f) => (f.folder_id ?? null) === currentFolderId.value)
)

// ---- 新建文件夹 ----
const createFolderVisible = ref(false)
const newFolderName = ref('')
const creatingFolder = ref(false)
const openCreateFolder = () => {
  newFolderName.value = ''
  createFolderVisible.value = true
}
const submitCreateFolder = async () => {
  const name = newFolderName.value.trim()
  if (!name) return ElMessage.warning('请输入文件夹名称')
  creatingFolder.value = true
  try {
    await createTaskFolder(props.projectId, props.taskId, {
      name,
      parent_id: currentFolderId.value,
    })
    ElMessage.success('文件夹已创建')
    createFolderVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    creatingFolder.value = false
  }
}

// ---- 上传 ----
const pickUpload = () => fileInput.value?.click()
const onFilesPicked = async (e) => {
  const filesSel = Array.from(e.target.files || [])
  if (!filesSel.length) return
  uploadBusy.value = true
  try {
    for (const f of filesSel) {
      await uploadTaskFile(props.projectId, props.taskId, f, currentFolderId.value)
    }
    ElMessage.success(`已上传 ${filesSel.length} 个文件`)
    await load()
  } catch (err) {
    ElMessage.error(err.response?.data?.detail || '上传失败')
  } finally {
    uploadBusy.value = false
    e.target.value = ''
  }
}

// ---- 重命名 ----
const renameVisible = ref(false)
const renameTarget = ref(null)
const renameValue = ref('')
const renaming = ref(false)
const openRenameFile = (f) => {
  renameTarget.value = { type: 'file', id: f.id, name: f.original_filename }
  renameValue.value = f.original_filename
  renameVisible.value = true
}
const openRenameFolder = (node) => {
  renameTarget.value = { type: 'folder', id: node.id, name: node.name }
  renameValue.value = node.name
  renameVisible.value = true
}
const submitRename = async () => {
  const name = renameValue.value.trim()
  if (!name) return ElMessage.warning('名称不能为空')
  renaming.value = true
  try {
    if (renameTarget.value.type === 'file') {
      await renameAttachment(renameTarget.value.id, name)
    } else {
      await updateTaskFolder(props.projectId, props.taskId, renameTarget.value.id, { name })
    }
    ElMessage.success('已重命名')
    renameVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '重命名失败')
  } finally {
    renaming.value = false
  }
}

// ---- 移动 ----
const moveVisible = ref(false)
const moveTarget = ref(null) // {type, id}
const moveTargetId = ref(null)
const moving = ref(false)
const moveTreeData = computed(() => [
  { id: 'ROOT', name: '根目录（全部文件）', isRoot: true, children: folders.value },
])
const onMoveTargetClick = (node) => {
  moveTargetId.value = node.id
}
const openMoveFile = (f) => {
  moveTarget.value = { type: 'file', id: f.id }
  moveTargetId.value = f.folder_id ?? 'ROOT'
  moveVisible.value = true
}
const openMoveFolder = (node) => {
  moveTarget.value = { type: 'folder', id: node.id }
  moveTargetId.value = node.parent_id ?? 'ROOT'
  moveVisible.value = true
}
const submitMove = async () => {
  moving.value = true
  try {
    const targetId = moveTargetId.value === 'ROOT' ? null : moveTargetId.value
    if (moveTarget.value.type === 'file') {
      await moveTaskFile(props.projectId, props.taskId, moveTarget.value.id, targetId)
    } else {
      await updateTaskFolder(props.projectId, props.taskId, moveTarget.value.id, { parent_id: targetId })
    }
    ElMessage.success('已移动')
    moveVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '移动失败')
  } finally {
    moving.value = false
  }
}

// ---- 删除 ----
const removeFile = async (f) => {
  const isManual = f.source !== 'comm'
  const extra = isManual && f.linked_count ? `（被 ${f.linked_count} 条沟通记录引用，将同步移除）` : ''
  try {
    await ElMessageBox.confirm(`确定删除文件「${f.original_filename}」？${extra}`, '删除确认', { type: 'warning' })
    await deleteAttachment(f.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

const removeFolder = async (node) => {
  try {
    await ElMessageBox.confirm(
      `确定删除文件夹「${node.name}」？其子文件夹与其中的独立文件将一并删除，沟通附件将移回根目录。`,
      '删除文件夹', { type: 'warning' }
    )
    const r = await deleteTaskFolder(props.projectId, props.taskId, node.id)
    ElMessage.success(`已删除 ${r.deleted_folders} 个文件夹`)
    if (node.id === currentFolderId.value) currentFolderId.value = null
    await load()
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

// ---- 预览 / 下载 ----
const preview = (f) => {
  window.open(`/api/attachments/${f.id}/preview`, '_blank')
}
const download = (f) => {
  const a = document.createElement('a')
  a.href = `/api/attachments/${f.id}/download`
  a.download = f.original_filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// ---- 辅助 ----
const isImageFile = (f) => /\.(png|jpe?g|gif|bmp|webp|svg|ico)$/i.test(f.original_filename)
const fileIconColor = (mime, name) => {
  if (isImageFile({ original_filename: name })) return '#E6A23C'
  if (/\.(docx?|doc)$/i.test(name)) return '#409EFF'
  if (/\.(xlsx?|xls|csv)$/i.test(name)) return '#67C23A'
  if (/\.(pdf)$/i.test(name)) return '#F56C6C'
  if (/\.(zip|rar|7z|tar|gz)$/i.test(name)) return '#909399'
  return '#5F5E5A'
}
const formatSize = (b) => {
  if (!b) return ''
  if (b > 1024 * 1024) return (b / 1024 / 1024).toFixed(1) + 'MB'
  if (b > 1024) return (b / 1024).toFixed(1) + 'KB'
  return b + 'B'
}

// ---- 定位：从沟通记录跳转并高亮 ----
watch(
  () => props.locateId,
  async (val) => {
    if (!val) return
    const target = files.value.find((f) => f.id === val)
    if (target) {
      currentFolderId.value = target.folder_id ?? null
      highlightId.value = val
      await nextTick()
    }
  }
)

const onVisibleChange = (v) => emit('update:visible', v)

defineExpose({ openRenameFolder, openMoveFolder, removeFolder })
</script>

<style scoped>
.fm-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 4px 0 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.fm-crumb {
  cursor: pointer;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.fm-crumb:hover { color: var(--el-color-primary); }
.fm-crumb-current { color: var(--el-text-color-primary); cursor: default; font-weight: 500; }
.fm-actions { display: flex; gap: 8px; }
.fm-body { display: flex; gap: 12px; height: calc(100vh - 150px); min-height: 380px; }
.fm-tree {
  width: 190px;
  flex-shrink: 0;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 8px;
  display: flex;
  flex-direction: column;
}
.fm-tree-title { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 6px; padding-left: 4px; }
.fm-tree-scroll { flex: 1; }
.fm-tree-node { display: inline-flex; align-items: center; font-size: 13px; }
.fm-files {
  flex: 1;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 8px;
  overflow: hidden;
}
.fm-file-scroll { height: 100%; }
.fm-file-list { display: flex; flex-direction: column; }
.fm-file-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  transition: background 0.15s;
}
.fm-file-row:hover { background: var(--el-fill-color-light); }
.fm-file-row-highlight {
  background: var(--el-color-primary-light-9);
  outline: 1px solid var(--el-color-primary-light-5);
}
.fm-file-icon { font-size: 18px; flex-shrink: 0; }
.fm-file-main { flex: 1; min-width: 0; }
.fm-file-name {
  display: block;
  color: var(--el-text-color-primary);
  font-size: 13px;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.fm-file-name:hover { color: var(--el-color-primary); }
.fm-file-meta { display: flex; align-items: center; gap: 6px; margin-top: 2px; flex-wrap: wrap; }
.fm-badge {
  font-size: 11px;
  padding: 0 6px;
  border-radius: 4px;
  line-height: 16px;
}
.fm-badge-comm { background: var(--el-color-primary-light-9); color: var(--el-color-primary); }
.fm-badge-manual { background: var(--el-fill-color); color: var(--el-text-color-secondary); }
.fm-badge-link { background: var(--el-color-warning-light-9); color: var(--el-color-warning); }
.fm-file-size { font-size: 12px; color: var(--el-text-color-secondary); }
.fm-file-ops { display: flex; flex-shrink: 0; opacity: 0.6; transition: opacity 0.15s; }
.fm-file-row:hover .fm-file-ops { opacity: 1; }
.fm-move-hint { margin-top: 8px; font-size: 12px; color: var(--el-text-color-secondary); }
</style>
