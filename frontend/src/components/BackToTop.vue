<template>
  <transition name="btt-fade">
    <el-button
      v-show="visible"
      class="btt-btn"
      circle
      aria-label="返回顶部"
      @click="scrollToTop"
    >
      <el-icon><ArrowUp /></el-icon>
    </el-button>
  </transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

// 返回顶部悬浮按钮：监听指定滚动容器，scrollTop 超过阈值显示，点击平滑滚回顶部。
// targets 传选择器或选择器数组（如 ['.main-content', '.timeline-scroll']），任一容器滚动即触发显示，
// 点击时所有容器一起滚回顶部。
const props = defineProps({
  targets: { type: [String, Array], default: '.main-content' },
  threshold: { type: Number, default: 300 },
})

const visible = ref(false)
let els = []

const collect = () => {
  const list = Array.isArray(props.targets) ? props.targets : [props.targets]
  els = list.map((sel) => document.querySelector(sel)).filter(Boolean)
}

const update = () => {
  visible.value = els.some((el) => el.scrollTop > props.threshold)
}

const onScroll = () => update()

const scrollToTop = () => {
  els.forEach((el) => el.scrollTo({ top: 0, behavior: 'smooth' }))
}

let timer = null
watch(
  () => props.targets,
  () => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      collect()
      update()
    }, 100)
  }
)

onMounted(() => {
  collect()
  els.forEach((el) => el.addEventListener('scroll', onScroll, { passive: true }))
  window.addEventListener('resize', onScroll)
  update()
})

onBeforeUnmount(() => {
  els.forEach((el) => el.removeEventListener('scroll', onScroll))
  window.removeEventListener('resize', onScroll)
  clearTimeout(timer)
})
</script>

<style scoped>
.btt-btn {
  position: fixed;
  right: 28px;
  bottom: 48px;
  z-index: 3000;
  width: 44px;
  height: 44px;
  font-size: 18px;
  background: #534ab7;
  color: #fff;
  border: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
}
.btt-btn:hover {
  background: #453c9e;
  color: #fff;
}
.btt-fade-enter-active,
.btt-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.btt-fade-enter-from,
.btt-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}
</style>
