<template>
  <div ref="root" class="comm-content" v-html="html"></div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { updateHeadingNumbers } from '../utils/headingNumber'

const props = defineProps({
  // 已由父组件 sanitize 后的 HTML（如 TaskDetail 的 renderCommContent）
  html: { type: String, default: '' },
})

const root = ref(null)

// 渲染后给 h1/h2/h3 加多级编号（仅显示，不污染存储的 HTML）
const applyNumbers = () => {
  if (root.value) updateHeadingNumbers(root.value)
}

onMounted(() => nextTick(applyNumbers))
watch(() => props.html, () => nextTick(applyNumbers))
</script>

<style scoped>
/* 标题多级自动编号（数据由 updateHeadingNumbers 写入 data-heading-num） */
.comm-content :deep(h1) {
  font-size: 18px; font-weight: 700; color: #1f1f1f; margin: 18px 0 8px;
}
.comm-content :deep(h2) {
  font-size: 16px; font-weight: 700; color: #1f1f1f; margin: 14px 0 6px;
}
.comm-content :deep(h3) {
  font-size: 14px; font-weight: 600; color: #333; margin: 12px 0 4px;
}
.comm-content :deep(h1)::before,
.comm-content :deep(h2)::before,
.comm-content :deep(h3)::before {
  content: attr(data-heading-num); font-weight: 700; margin-right: 2px;
}
/* ── 行内代码：高辨识度代码配色（等宽 + 玫红字 + 浅粉底 + 细边框） ── */
.comm-content :deep(code) {
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  color: #c7254e;
  background-color: #f9f2f4;
  border: 1px solid #f0d3da;
  border-radius: 4px;
  padding: 1px 5px;
  white-space: pre-wrap;
  word-break: break-all;
}
/* ── 代码块（pre>code）：深色代码块观感（VS Code/GitHub 暗色底 + macOS 圆点），保留换行缩进 ── */
.comm-content :deep(pre) {
  position: relative;
  background: #282c34;
  color: #e6e6e6;
  border: 1px solid #1f2328;
  border-radius: 8px;
  padding: 34px 16px 12px;
  overflow-x: auto;
  font-family: Consolas, Monaco, 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  margin: 10px 0;
}
.comm-content :deep(pre)::before {
  content: '';
  position: absolute;
  top: 12px;
  left: 14px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #ff5f56;
  box-shadow: 16px 0 0 #ffbd2e, 32px 0 0 #27c93f;
}
.comm-content :deep(pre code) {
  background: none;
  padding: 0;
  border-radius: 0;
  font-size: inherit;
  color: inherit;
  white-space: pre;
  word-break: normal;
}
</style>
