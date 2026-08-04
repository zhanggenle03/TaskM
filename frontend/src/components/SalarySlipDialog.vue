<template>
  <el-dialog
    v-model="visible"
    :title="`工资条 · ${record?.period || ''}`"
    width="960px"
    top="6vh"
    class="slip-dialog"
    :close-on-click-modal="false"
    :style="{ height: '640px', maxHeight: '640px', display: 'flex', flexDirection: 'column' }"
    @opened="onOpened"
    @closed="onClosed"
  >
    <div class="slip-body">
      <!-- 左侧：图片预览（滚轮缩放 / 拖拽平移 / 双击切换） -->
      <div class="slip-preview">
        <div class="preview-toolbar">
          <div class="zoom-group">
            <el-button size="small" :disabled="scale <= MIN_SCALE" @click="zoomOut"><el-icon><ZoomOut /></el-icon></el-button>
            <span class="scale-pct">{{ Math.round(scale * 100) }}%</span>
            <el-button size="small" :disabled="scale >= MAX_SCALE" @click="zoomIn"><el-icon><ZoomIn /></el-icon></el-button>
            <el-button size="small" @click="fitView">适合宽度</el-button>
          </div>
        </div>
        <div
          ref="stageEl"
          class="preview-stage"
          @wheel.prevent="onWheel"
          @mousedown="onMouseDown"
          @dblclick="toggleZoom"
        >
          <img
            v-if="imgSrc"
            :src="imgSrc"
            class="preview-img"
            :style="imgStyle"
            draggable="false"
            @load="onImgLoad"
            @dragstart.prevent
          />
          <div v-else class="preview-empty">
            <el-icon :size="36"><Picture /></el-icon>
            <p>暂无工资条</p>
            <span>请在右侧上传本月工资条图片</span>
          </div>
        </div>
      </div>

      <!-- 右侧：附件列表与操作 -->
      <div class="slip-side">
        <div class="side-title">
          附件操作
          <span class="cnt" v-if="slips.length">{{ slips.length }}</span>
        </div>

        <!-- 附件列表（上传按钮上方，可多张） -->
        <div class="slip-list" v-if="slips.length">
          <div
            v-for="s in slips"
            :key="s.id"
            class="slip-item"
            :class="{ active: s.id === selectedId }"
            @click="selectSlip(s)"
          >
            <img class="item-thumb" :src="s.url" alt="" draggable="false" />
            <div class="item-main">
              <el-input
                v-if="editingId === s.id"
                ref="renameInput"
                v-model="editingName"
                size="small"
                class="rename-input"
                @keyup.enter="confirmRename"
                @keyup.esc="cancelRename"
                @blur="confirmRename"
              />
              <template v-else>
                <div class="item-name" :title="s.original_filename">{{ s.original_filename }}</div>
                <div class="item-meta">{{ formatSize(s.file_size) }} · {{ formatTime(s.uploaded_at) }}</div>
              </template>
            </div>
            <div class="item-actions" @click.stop>
              <el-tooltip content="重命名" placement="top" :show-after="400">
                <span class="act" @click="startRename(s)"><el-icon><EditPen /></el-icon></span>
              </el-tooltip>
              <el-tooltip content="下载" placement="top" :show-after="400">
                <span class="act" @click="download(s)"><el-icon><Download /></el-icon></span>
              </el-tooltip>
              <el-tooltip content="删除" placement="top" :show-after="400">
                <span class="act danger" @click="removeSlip(s)"><el-icon><Delete /></el-icon></span>
              </el-tooltip>
            </div>
          </div>
        </div>

        <!-- 上传区（点击或拖拽文件到此处） -->
        <div
          class="upload-zone"
          :class="{ uploading }"
          @click="fileInput?.click()"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <el-icon :size="20" class="uz-icon"><UploadFilled /></el-icon>
          <span class="uz-title">{{ uploading ? '上传中…' : '上传工资条' }}</span>
          <span class="uz-sub">支持 jpg / png / webp / gif / bmp</span>
        </div>

        <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileChange" />

        <p class="side-hint">每月可上传多张，点击列表项切换预览。</p>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { uploadSalarySlip, deleteSalarySlip, renameSalarySlip } from '../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  record: { type: Object, default: null }, // SalaryRecordOut（含 slips 字段）
})
const emit = defineEmits(['update:modelValue', 'changed'])

const MIN_SCALE = 0.25
const MAX_SCALE = 4

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// ── 附件列表（每月可多张） ──
const slips = ref([])
const selectedId = ref(null)
const editingId = ref(null)
const editingName = ref('')
const renameInput = ref(null)
const currentSlip = computed(() => slips.value.find(s => s.id === selectedId.value) || slips.value[0] || null)
const imgSrc = computed(() => currentSlip.value?.url || '')

// ── 预览视图状态 ──
const stageEl = ref(null)
const fileInput = ref(null)
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const naturalW = ref(0)
const dragging = ref(false)
const uploading = ref(false)
const dragOver = ref(false)
let dragStart = { x: 0, y: 0, ox: 0, oy: 0 }

const imgStyle = computed(() => ({
  transform: `translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`,
}))

const clampScale = (v) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, v))
const round2 = (n) => Math.round(n * 100) / 100

function fitView() {
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
}
function resetView() {
  const w = stageEl.value?.offsetWidth || 0
  if (!w || !naturalW.value) { scale.value = 1; offsetX.value = 0; offsetY.value = 0; return }
  scale.value = clampScale(naturalW.value / w)
  offsetX.value = 0
  offsetY.value = 0
}
function zoomIn() { scale.value = clampScale(round2(scale.value * 1.25)) }
function zoomOut() { scale.value = clampScale(round2(scale.value / 1.25)) }
function onWheel(e) {
  const delta = e.deltaY < 0 ? 1.1 : 1 / 1.1
  scale.value = clampScale(round2(scale.value * delta))
}
function toggleZoom() {
  if (scale.value === 1) resetView()
  else fitView()
}
function onImgLoad(e) {
  naturalW.value = e.target.naturalWidth || 0
}
function onOpened() {
  nextTick(() => { if (imgSrc.value) fitView() })
}
function onClosed() {
  fitView()
  naturalW.value = 0
}

// ── 拖拽平移 ──
function onMouseDown(e) {
  if (!imgSrc.value || e.button !== 0) return
  dragging.value = true
  dragStart = { x: e.clientX, y: e.clientY, ox: offsetX.value, oy: offsetY.value }
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}
function onMouseMove(e) {
  if (!dragging.value) return
  offsetX.value = dragStart.ox + (e.clientX - dragStart.x)
  offsetY.value = dragStart.oy + (e.clientY - dragStart.y)
}
function onMouseUp() {
  dragging.value = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
}

// ── 附件操作 ──
watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      slips.value = (props.record?.slips || []).map(s => ({ ...s }))
      selectedId.value = slips.value[0]?.id ?? null
      naturalW.value = 0
      fitView()
    }
  }
)

function selectSlip(s) {
  selectedId.value = s.id
  naturalW.value = 0
  nextTick(() => fitView())
}

// ── 重命名 ──
function startRename(s) {
  editingId.value = s.id
  editingName.value = s.original_filename
  nextTick(() => renameInput.value?.focus())
}
function cancelRename() {
  editingId.value = null
}
async function confirmRename() {
  const id = editingId.value
  if (id == null) return
  editingId.value = null
  const name = (editingName.value || '').trim()
  if (!name) return
  if (!/\.(jpg|jpeg|png|webp|gif|bmp)$/i.test(name)) {
    ElMessage.warning('请保留图片扩展名（.jpg / .png / .webp / .gif / .bmp）')
    return
  }
  try {
    const updated = await renameSalarySlip(props.record.id, id, name)
    const idx = slips.value.findIndex(x => x.id === id)
    if (idx >= 0) slips.value[idx] = updated
    ElMessage.success('已重命名')
    emit('changed')
  } catch { /* 拦截器已提示 */ }
}

function onFileChange(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (file) uploadFile(file)
}

function onDrop(e) {
  dragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) uploadFile(file)
}

function uploadFile(file) {
  if (!/^image\//.test(file.type)) {
    ElMessage.warning('仅支持图片文件（jpg / png / webp / gif / bmp）')
    return
  }
  uploading.value = true
  uploadSalarySlip(props.record.id, file)
    .then((res) => {
      slips.value.push(res)
      selectedId.value = res.id
      naturalW.value = 0
      ElMessage.success('工资条已上传')
      emit('changed')
      nextTick(() => { if (stageEl.value) fitView() })
    })
    .catch(() => { /* 拦截器已提示 */ })
    .finally(() => { uploading.value = false })
}

async function removeSlip(s) {
  try {
    await ElMessageBox.confirm(`确定删除「${s.original_filename}」吗？`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteSalarySlip(props.record.id, s.id)
    slips.value = slips.value.filter(x => x.id !== s.id)
    if (selectedId.value === s.id) {
      selectedId.value = slips.value[0]?.id ?? null
      naturalW.value = 0
      nextTick(() => fitView())
    }
    ElMessage.success('已删除')
    emit('changed')
  } catch { /* 拦截器已提示 */ }
}

function download(s) {
  const a = document.createElement('a')
  a.href = s.url
  a.download = s.original_filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}
function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  if (isNaN(d)) return ''
  const p = (n) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<style scoped>
.slip-body { display: flex; gap: 16px; height: 100%; min-width: 0; min-height: 0; }

/* 左侧预览区 */
.slip-preview {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.preview-toolbar { display: flex; align-items: center; justify-content: flex-end; flex-shrink: 0; }
.zoom-group { display: flex; align-items: center; gap: 6px; }
.scale-pct { font-size: 13px; color: #888; font-variant-numeric: tabular-nums; min-width: 52px; text-align: center; }

.preview-stage {
  flex: 1 1 0;
  min-height: 0;
  background: #ececea;
  border-radius: 10px;
  overflow: hidden;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: grab;
  user-select: none;
}
.preview-stage:active { cursor: grabbing; }
.preview-img {
  width: 100%;
  height: auto;
  flex-shrink: 0;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.12);
  transform-origin: center center;
  will-change: transform;
  pointer-events: none;
}
.preview-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: #aaa;
  text-align: center;
}
.preview-empty p { margin: 0; font-size: 14px; color: #999; font-weight: 500; }
.preview-empty span { font-size: 12px; }

/* 右侧操作区：严格固定 230px */
.slip-side {
  flex: 0 0 230px;
  width: 230px;
  min-width: 0;
  max-width: 230px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.side-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px; font-weight: 600; color: #2c2c2a;
  padding-bottom: 8px; border-bottom: 1px solid #eef0f2;
}
.side-title .cnt {
  font-size: 11px;
  font-weight: 500;
  color: #534AB7;
  background: #eeedfe;
  border-radius: 10px;
  padding: 1px 8px;
  font-variant-numeric: tabular-nums;
}

/* 附件列表（多张，可滚动） */
.slip-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 250px;
  overflow-y: auto;
  min-height: 0;
  padding: 2px;
  margin: -2px;
}
.slip-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid #ececf0;
  border-radius: 10px;
  cursor: pointer;
  background: #fff;
  min-width: 0;
  transition: border-color .15s, background .15s, box-shadow .15s;
}
.slip-item:hover {
  border-color: #d5d0f2;
  background: #fafaff;
  box-shadow: 0 1px 4px rgba(83,74,183,.08);
}
.slip-item.active {
  border-color: #534AB7;
  background: #f4f1ff;
  box-shadow: 0 1px 6px rgba(83,74,183,.14);
}
.item-thumb {
  width: 36px;
  height: 36px;
  border-radius: 6px;
  object-fit: cover;
  background: #f1f0ee;
  border: 1px solid #e8e8e4;
  flex-shrink: 0;
}
.slip-item:not(.active) .item-thumb { filter: saturate(.85); }
.item-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #2c2c2a;
  line-height: 1.3;
}
.item-meta { font-size: 11px; color: #a0a0a0; font-variant-numeric: tabular-nums; }
.item-actions {
  flex-shrink: 0;
  display: flex;
  gap: 2px;
  color: #b5b5b0;
  opacity: 0;
  transition: opacity .15s;
}
.slip-item:hover .item-actions,
.slip-item.active .item-actions { opacity: 1; }
.item-actions .act {
  cursor: pointer;
  font-size: 14px;
  padding: 3px;
  border-radius: 6px;
  line-height: 1;
  display: inline-flex;
}
.item-actions .act:hover { color: #534AB7; background: #eeedfe; }
.item-actions .act.danger:hover { color: #c45656; background: #fbeef0; }
.rename-input { width: 100%; }
.rename-input :deep(.el-input__wrapper) { padding: 0 6px; box-shadow: 0 0 0 1px #8f88e0 inset; border-radius: 6px; }
.rename-input :deep(.el-input__inner) { font-size: 12px; }

/* 上传区（虚线拖拽框） */
.upload-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 16px 10px;
  border: 1.5px dashed #d8d8e2;
  border-radius: 10px;
  background: #fbfbfd;
  cursor: pointer;
  transition: border-color .15s, background .15s;
  flex-shrink: 0;
}
.upload-zone:hover { border-color: #8f88e0; background: #f7f6ff; }
.upload-zone.uploading { border-color: #534AB7; background: #f4f1ff; cursor: default; }
.uz-icon { color: #9d97e6; }
.upload-zone:hover .uz-icon { color: #534AB7; }
.uz-title { font-size: 13px; font-weight: 500; color: #534AB7; }
.uz-sub { font-size: 11px; color: #a8a8a2; }

.side-hint { margin: 2px 0 0; font-size: 12px; color: #aaa; line-height: 1.6; text-align: center; }
</style>

<!-- el-dialog Teleport 到 body，scoped 不生效，需非 scoped 样式控制布局 -->
<style>
.slip-dialog .el-dialog__header { flex-shrink: 0; }
.slip-dialog .el-dialog__body {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
  display: flex;
}
.slip-dialog .el-dialog__body > .slip-body {
  flex: 1 1 0;
  min-width: 0;
  min-height: 0;
}
</style>
