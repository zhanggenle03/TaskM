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
</style>
