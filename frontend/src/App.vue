<template>
  <el-container class="app-layout">
    <!-- 主侧边栏 -->
    <el-aside v-if="showMainSidebar" width="180px" class="sidebar">
      <div class="logo">
        <el-icon size="22" color="#534AB7"><Grid /></el-icon>
        <span>TaskM</span>
      </div>
      <el-menu :router="true" :default-active="$route.path" class="side-menu">
        <el-menu-item index="/projects">
          <el-icon><FolderOpened /></el-icon>
          <span>所有项目</span>
        </el-menu-item>
        <el-menu-item index="/checkins">
          <el-icon><Timer /></el-icon>
          <span>工作记录</span>
        </el-menu-item>
        <el-menu-item index="/salary">
          <el-icon><Money /></el-icon>
          <span>薪资记录</span>
        </el-menu-item>
        <el-menu-item index="/process">
          <el-icon><Setting /></el-icon>
          <span>通用设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 项目内小型导航栏（仅项目内部页面显示） -->
    <el-aside v-if="showProjectNav" width="76px" class="project-nav">
      <div class="project-nav-title" @click="$router.push('/projects')" style="cursor:pointer;">
        <el-icon :size="16" style="vertical-align:-2px;margin-right:2px"><HomeFilled /></el-icon>
        <span>首页</span>
      </div>
      <el-menu :router="true" :default-active="projectNavActive" class="project-nav-menu">
        <el-menu-item :index="`/projects/${projectId}`" class="nav-vertical-item">
          <el-icon :size="20"><List /></el-icon>
          <span>任务</span>
        </el-menu-item>
        <el-menu-item :index="`/projects/${projectId}/requirements`" class="nav-vertical-item">
          <el-icon :size="20"><Document /></el-icon>
          <span>需求</span>
        </el-menu-item>
        <el-menu-item :index="`/projects/${projectId}/dashboard`" class="nav-vertical-item">
          <el-icon :size="20"><DataAnalysis /></el-icon>
          <span>总览</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

// 判断是否在项目内部页面
const projectId = computed(() => route.params.projectId)
const showProjectNav = computed(() => !!projectId.value)
const showMainSidebar = computed(() => !projectId.value)

// 项目内导航高亮：精确匹配路由前缀
const projectNavActive = computed(() => {
  const path = route.path
  const base = `/projects/${projectId.value}`
  if (!projectId.value) return ''
  // 精确匹配项目内页面路径
  if (path === base) return base
  if (path.startsWith(base + '/tasks/')) return base  // 任务详情 → 高亮任务列表
  if (path.startsWith(base + '/requirements')) return base + '/requirements'
  if (path.startsWith(base + '/dashboard')) return base + '/dashboard'
  return base  // 默认高亮任务列表
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f7f7f5; color: #2c2c2a; }
.app-layout { width: 100%; height: 100vh; }
.sidebar { background: #fff; border-right: 1px solid #e8e8e4; display: flex; flex-direction: column; }
.logo { display: flex; align-items: center; gap: 10px; padding: 18px 20px; font-size: 17px; font-weight: 600; color: #3c3489; border-bottom: 1px solid #e8e8e4; }
.side-menu { border-right: none; flex: 1; }
.project-nav { background: #fafafa; border-right: 1px solid #e8e8e4; display: flex; flex-direction: column; overflow: hidden; }
.project-nav-title { padding: 20px 14px; font-size: 12px; font-weight: 600; color: #999; text-align: center; border-bottom: 1px solid #e8e8e4; }
.project-nav-menu { border-right: none; background: transparent; --el-menu-item-height: auto; }
.project-nav-menu .nav-vertical-item { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 70px; padding: 0 4px !important; gap: 4px; }
.project-nav-menu .nav-vertical-item .el-icon { margin-right: 0 !important; }
.project-nav-menu .nav-vertical-item span { font-size: 11px; line-height: 1.2; }
.project-nav-menu .nav-vertical-item.is-active { color: #534ab7 !important; background: #eeedfe !important; border-right: 3px solid #534ab7; }
.main-content { padding: 28px 32px 0 32px; overflow-y: auto; background: #f7f7f5; display: flex; flex-direction: column; }
.el-menu-item.is-active { color: #534ab7 !important; background: #eeedfe !important; }
</style>
