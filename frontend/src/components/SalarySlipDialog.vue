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

      <!-- 右侧：附件信息与操作 -->
      <div class="slip-side">
        <div class="side-title">附件操作</div>

        <div class="slip-info" v-if="slip">
          <div class="info-name" :title="slip.original_filename">{{ slip.original_filename }}</div>
          <div class="info-meta">{{ formatSize(slip.file_size) }} · {{ formatTime(slip.uploaded_at) }}</div>
        </div>
        <div class="slip-info empty" v-else>
          <div class="info-name muted">尚未上传工资条</div>
          <div class="info-meta">支持 jpg / png / webp / gif / bmp</div>
        </div>

        <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileChange" />

        <el-button type="primary" class="side-btn" :loading="uploading" @click="fileInput?.click()">
          <el-icon><Upload /></el-icon>{{ slip ? '上传 / 替换' : '上传工资条' }}
        </el-button>
        <el-button class="side-btn" :disabled="!slip" @click="download">
          <el-icon><Download /></el-icon>下载原图
        </el-button>
        <el-button class="side-btn danger" type="danger" plain :disabled="!slip || uploading" @click="removeSlip">
          <el-icon><Delete /></el-icon>删除工资条
        </el-button>

        <p class="side-hint">每月一条；上传新图自动替换旧图，删除后需重新上传。</p>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { uploadSalarySlip, deleteSalarySlip } from '../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  record: { type: Object, default: null }, // SalaryRecordOut（含 slip 字段）
})
const emit = defineEmits(['update:modelValue', 'changed'])

const MIN_SCALE = 0.25
const MAX_SCALE = 4

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// ── 本地附件状态（打开时由 record.slip 初始化，操作后自行更新） ──
const slip = ref(null)
const imgSrc = computed(() => slip.value?.url || '')

// ── 预览视图状态 ──
const stageEl = ref(null)
const fileInput = ref(null)
const scale = ref(1)
const offsetX = ref(0)
const offsetY = ref(0)
const naturalW = ref(0)
const dragging = ref(false)
const uploading = ref(false)
let dragStart = { x: 0, y: 0, ox: 0, oy: 0 }

const imgStyle = computed(() => ({
  transform: `translate(${offsetX.value}px, ${offsetY.value}px) scale(${scale.value})`,
}))

const clampScale = (v) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, v))
const round2 = (n) => Math.round(n * 100) / 100

function resetView() {
  // 「100%」= 原始像素 1:1（视觉宽度 = 图片自然宽度）
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
// 适合宽度：scale=1（图片布局 100% 容器宽，视觉恰好充满容器宽）
function fitView() {
  scale.value = 1
  offsetX.value = 0
  offsetY.value = 0
}
function toggleZoom() {
  if (scale.value === 1) resetView()
  else fitView()
}
function onImgLoad(e) {
  naturalW.value = e.target.naturalWidth || 0
}
function onOpened() {
  nextTick(() => { if (slip.value) fitView() })
}
function onClosed() {
  resetView()
  naturalW.value = 0
}

// ── 拖拽平移 ──
function onMouseDown(e) {
  if (!slip.value || e.button !== 0) return
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
      slip.value = props.record?.slip || null
      naturalW.value = 0
    }
  }
)

function onFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  // 前端兜底校验类型
  if (!/^image\//.test(file.type)) {
    ElMessage.warning('仅支持图片文件（jpg / png / webp / gif / bmp）')
    e.target.value = ''
    return
  }
  uploading.value = true
  uploadSalarySlip(props.record.id, file)
    .then((res) => {
      slip.value = res
      ElMessage.success('工资条已上传')
      emit('changed')
      nextTick(() => { if (stageEl.value) fitView() })
    })
    .catch(() => { /* 拦截器已提示 */ })
    .finally(() => {
      uploading.value = false
      e.target.value = ''
    })
}

async function removeSlip() {
  try {
    await ElMessageBox.confirm('确定删除本月的工资条吗？删除后需重新上传。', '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await deleteSalarySlip(props.record.id)
    slip.value = null
    resetView()
    ElMessage.success('已删除')
    emit('changed')
  } catch { /* 拦截器已提示 */ }
}

function download() {
  if (!slip.value) return
  const a = document.createElement('a')
  a.href = slip.value.url
  a.download = slip.value.original_filename
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
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
</script>

<style scoped>
.slip-body { display: flex; gap: 16px; height: 100%; min-height: 0; }

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
  /* 布局尺寸恒等于容器宽（height 按比例），transform scale 只做视觉缩放——大图不会撑破弹窗 */
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

/* 右侧操作区 */
.slip-side {
  flex: 0 0 230px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.side-title {
  font-size: 13px; font-weight: 600; color: #2c2c2a;
  padding-bottom: 8px; border-bottom: 1px solid #eef0f2;
}
.slip-info {
  background: #f8f9fb;
  border: 1px solid #eef0f2;
  border-radius: 10px;
  padding: 12px 14px;
}
.slip-info.empty { background: #fafafa; }
.info-name {
  font-size: 13px; font-weight: 500; color: #2c2c2a;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.info-name.muted { color: #999; font-weight: 400; }
.info-meta { font-size: 12px; color: #999; margin-top: 4px; font-variant-numeric: tabular-nums; }
.side-btn { width: 100%; margin-left: 0 !important; }
.side-hint { margin: 4px 0 0; font-size: 12px; color: #aaa; line-height: 1.6; }
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
  min-height: 0;
}
</style>
