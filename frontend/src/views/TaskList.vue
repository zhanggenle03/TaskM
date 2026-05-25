<template>
  <div>
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item>{{ project?.name }}</el-breadcrumb-item>
    </el-breadcrumb>

    <div class="page-header">
      <div>
        <h1 class="page-title">{{ project?.name }}</h1>
        <p class="page-sub">{{ project?.description }}</p>
      </div>
      <div style="display:flex;gap:8px">
        <el-button @click="removeProject">
          <el-icon><Delete /></el-icon> 删除项目
        </el-button>
        <el-button @click="$router.push(`/projects/${projectId}/settings`)">
          <el-icon><Setting /></el-icon> 设置
        </el-button>
        <el-button type="primary" @click="showCreate = true">
          <el-icon><Plus /></el-icon> 新建任务
        </el-button>
      </div>
    </div>

    <!-- 状态筛选 -->
    <div class="filter-bar">
      <span class="filter-label">状态筛选：</span>
      <el-button
        v-for="s in [{ id: null, name: '全部', color: '#888' }, ...statuses]"
        :key="s.id"
        size="small"
        :type="activeStatus === s.id ? 'primary' : ''"
        :style="activeStatus !== s.id ? { borderColor: s.color, color: s.color } : {}"
        @click="activeStatus = s.id; loadTasks()"
        round
      >{{ s.name }}</el-button>
    </div>

    <!-- 任务列表 -->
    <div class="task-list" v-if="tasks.length">
      <div
        v-for="t in tasks" :key="t.id"
        class="task-row"
        @click="$router.push(`/projects/${projectId}/tasks/${t.id}`)"
      >
        <div class="task-status-dot" :style="{ background: statusColor(t.status_id) }"></div>
        <div class="task-info">
          <div class="task-title">{{ t.title }}</div>
          <div class="task-meta">
            <el-tag v-if="t.priority" :type="priorityType(t.priority)" size="small">{{ priorityLabel(t.priority) }}</el-tag>
            <span v-if="t.due_date" class="task-date">截止 {{ t.due_date }}</span>
            <span class="task-contacts" v-if="t.contacts?.length">
              <el-icon><User /></el-icon> {{ t.contacts.map(c => c.name).join('、') }}
            </span>
          </div>
        </div>
        <div class="task-status-tag">
          <el-tag :color="statusColor(t.status_id)" effect="plain" size="small" style="border:none;background:transparent">
            {{ statusName(t.status_id) }}
          </el-tag>
        </div>
        <div class="task-actions" @click.stop>
          <el-button size="small" text @click="openEdit(t)"><el-icon><Edit /></el-icon></el-button>
          <el-button size="small" text type="danger" @click="removeTask(t)"><el-icon><Delete /></el-icon></el-button>
        </div>
      </div>
    </div>
    <el-empty v-else description="暂无任务" />

    <!-- 新建/编辑任务 -->
    <el-dialog v-model="showCreate" :title="editTarget ? '编辑任务' : '新建任务'" width="480px" @close="resetForm">
      <el-form :model="form" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="form.title" placeholder="输入任务标题" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status_id" placeholder="选择状态" clearable>
            <el-option v-for="s in statuses" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <el-option label="低" value="low" />
            <el-option label="普通" value="normal" />
            <el-option label="高" value="high" />
            <el-option label="紧急" value="urgent" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="form.due_date" type="date" value-format="YYYY-MM-DD" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter, onBeforeRouteUpdate } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import {
  getTasks, createTask, updateTask, deleteTask, getStatuses, getProjects, deleteProject,
} from '../api'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)
const project = ref(null)
const tasks = ref([])
const statuses = ref([])
const activeStatus = ref(null)
const showCreate = ref(false)
const loading = ref(false)
const editTarget = ref(null)
const form = ref({ title: '', description: '', status_id: null, priority: 'normal', due_date: null })

const load = async () => {
  const [all, s] = await Promise.all([getProjects(), getStatuses(projectId)])
  project.value = all.find(p => p.id === projectId)
  statuses.value = s
  await loadTasks()
}
const loadTasks = async () => {
  const params = activeStatus.value !== null ? { status_id: activeStatus.value } : {}
  tasks.value = await getTasks(projectId, params)
}

onMounted(load)
onBeforeRouteUpdate(() => { load() })

const statusColor = (id) => statuses.value.find(s => s.id === id)?.color || '#aaa'
const statusName = (id) => statuses.value.find(s => s.id === id)?.name || '无状态'
const priorityLabel = (p) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[p] || p)
const priorityType = (p) => ({ low: 'info', normal: '', high: 'warning', urgent: 'danger' }[p] || '')

const resetForm = () => { form.value = { title: '', description: '', status_id: null, priority: 'normal', due_date: null }; editTarget.value = null }

const openEdit = (t) => {
  editTarget.value = t
  form.value = { title: t.title, description: t.description, status_id: t.status_id, priority: t.priority, due_date: t.due_date }
  showCreate.value = true
}

const submit = async () => {
  if (!form.value.title.trim()) { ElMessage.warning('标题不能为空'); return }
  loading.value = true
  try {
    if (editTarget.value) {
      await updateTask(projectId, editTarget.value.id, form.value)
      ElMessage.success('已更新')
    } else {
      await createTask(projectId, form.value)
      ElMessage.success('创建成功')
    }
    showCreate.value = false
    await loadTasks()
  } finally { loading.value = false }
}

const removeTask = async (t) => {
  await ElMessageBox.confirm(`确定删除任务「${t.title}」吗？`, '警告', { type: 'warning' })
  await deleteTask(projectId, t.id)
  ElMessage.success('已删除')
  await loadTasks()
}

const removeProject = async () => {
  await ElMessageBox.confirm(`确定删除项目「${project.value?.name}」及其所有任务？`, '警告', { type: 'warning' })
  await deleteProject(projectId)
  ElMessage.success('项目已删除')
  router.push('/projects')
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-title { font-size: 20px; font-weight: 600; }
.page-sub { font-size: 13px; color: #888; margin-top: 4px; }
.filter-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filter-label { font-size: 13px; color: #888; }
.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-row { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 18px; display: flex; align-items: center; gap: 14px; cursor: pointer; transition: border-color .15s; }
.task-row:hover { border-color: #534ab7; }
.task-status-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.task-info { flex: 1; min-width: 0; }
.task-title { font-size: 14px; font-weight: 500; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.task-meta { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #888; }
.task-date { color: #e24b4a; }
.task-contacts { display: flex; align-items: center; gap: 3px; }
.task-status-tag { flex-shrink: 0; }
.task-actions { display: flex; gap: 4px; flex-shrink: 0; }

.checkin-section { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 18px; margin-bottom: 16px; }
.checkin-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.checkin-title { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; color: #444; }
.checkin-input-row { display: flex; gap: 8px; margin-bottom: 10px; }
.checkin-list { display: flex; flex-direction: column; gap: 6px; }
.checkin-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #555; }
.checkin-date { font-weight: 500; color: #534ab7; min-width: 36px; }
.checkin-dot { width: 6px; height: 6px; border-radius: 50%; background: #534ab7; flex-shrink: 0; }
.checkin-content { flex: 1; color: #333; }
</style>
