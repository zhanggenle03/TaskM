<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="sidebar">
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
        <el-menu-item index="/process">
          <el-icon><Setting /></el-icon>
          <span>通用设置</span>
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
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f7f7f5; color: #2c2c2a; }
.app-layout { height: 100vh; }
.sidebar { background: #fff; border-right: 1px solid #e8e8e4; display: flex; flex-direction: column; }
.logo { display: flex; align-items: center; gap: 10px; padding: 18px 20px; font-size: 17px; font-weight: 600; color: #3c3489; border-bottom: 1px solid #e8e8e4; }
.side-menu { border-right: none; flex: 1; }
.main-content { padding: 28px 32px; overflow-y: auto; background: #f7f7f5; }
.el-menu-item.is-active { color: #534ab7 !important; background: #eeedfe !important; }
</style>
