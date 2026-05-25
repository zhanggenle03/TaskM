<template>
  <div>
    <!-- 页面头部：标题 + 统计 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">项目列表</h1>
        <p class="page-sub">共 {{ filteredProjects.length }} 个项目</p>
      </div>
      <div class="header-actions">
        <!-- 搜索 -->
        <div class="search-wrapper">
          <el-input
            v-model="searchText"
            placeholder="搜索项目名称/描述…"
            clearable
            prefix-icon="Search"
            size="default"
            style="width:220px"
            @clear="onSearchClear"
          />
        </div>
        <!-- 排序 -->
        <el-select v-model="sortValue" size="default" style="width:150px" @change="onSortChange">
          <el-option
            v-for="opt in sortOptions"
            :key="opt.value"
            :label="opt.label"
            :value="opt.value"
          />
        </el-select>
        <el-button type="primary" @click="showCreate = true">
          <el-icon><Plus /></el-icon> 新建项目
        </el-button>
      </div>
    </div>

    <!-- 项目卡片 -->
    <el-row :gutter="16" v-if="filteredProjects.length">
      <el-col
        :xs="24" :sm="12" :md="8"
        v-for="p in filteredProjects"
        :key="p.id"
        style="margin-bottom:16px"
      >
        <div class="proj-card" @click="$router.push(`/projects/${p.id}`)">
          <div class="proj-card-header">
            <div class="proj-icon">{{ p.name[0] }}</div>
            <div class="proj-name">{{ p.name }}</div>
            <el-dropdown trigger="click" @command="cmd => onCmd(cmd, p)">
              <el-button size="small" @click.stop>
                <el-icon><MoreFilled /></el-icon> 操作
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="delete" style="color:#e24b4a">删除</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
          <p class="proj-desc">{{ p.description || '暂无描述' }}</p>
          <p class="proj-date">
            <span v-if="p.start_date">{{ dayjs(p.start_date).format('YYYY年MM月DD日') }} 开始</span>
            <span v-else style="color:#ccc">未知时间开始</span>
            <span class="date-sep">|</span>
            <span>{{ dayjs(p.updated_at).format('YYYY年MM月DD日 HH:mm:ss') }} 更新</span>
          </p>
        </div>
      </el-col>
    </el-row>

    <!-- 搜索结果为空 -->
    <el-empty v-else-if="loaded && searchText && !apiError" description="没有匹配的项目" />

    <!-- 后端异常 -->
    <div v-else-if="apiError" class="error-card">
      <el-icon :size="48" color="#e24b4a"><WarningFilled /></el-icon>
      <h3>无法连接后端服务</h3>
      <p>{{ apiError }}</p>
      <el-button type="primary" style="margin-top:16px" @click="load">重新连接</el-button>
    </div>

    <!-- 空状态（仅在首次加载完成后显示） -->
    <el-empty v-else-if="loaded" description="还没有项目，点击右上角新建" />

    <!-- 新建/编辑项目弹窗 -->
    <el-dialog v-model="showCreate" :title="editTarget ? '编辑项目' : '新建项目'" width="420px" @close="resetForm">
      <el-form :model="form" label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" placeholder="输入项目名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择开始日期" style="width:100%" />
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
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { getProjects, createProject, updateProject, deleteProject } from '../api'

const router = useRouter()

// ---------- 数据 ----------
const allProjects = ref([])
const loading = ref(false)
const apiError = ref('')
const loaded = ref(false) // 标记首次数据是否已加载完成

// ---------- 搜索 ----------
const searchText = ref('')
let searchTimer = null

const load = async (searchKeyword) => {
  apiError.value = ''
  loading.value = true
  try {
    const params = {
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
    }
    if (searchKeyword) params.search = searchKeyword
    allProjects.value = await getProjects(params)
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '后端服务未响应'
    apiError.value = msg
  } finally {
    loading.value = false
    loaded.value = true
  }
}

// 搜索防抖：用户停止输入 300ms 后发起请求
const doSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    load(searchText.value)
  }, 300)
}

watch(searchText, () => {
  doSearch()
})

const onSearchClear = () => {
  if (searchTimer) clearTimeout(searchTimer)
  load('')
}

// ---------- 排序 ----------
const SORT_KEY = 'taskm_sort' // localStorage key

const sortOptions = [
  { label: '按更新时间降序', value: 'updated_at_desc' },
  { label: '按更新时间升序', value: 'updated_at_asc' },
  { label: '按开始时间降序', value: 'start_date_desc' },
  { label: '按开始时间升序', value: 'start_date_asc' },
  { label: '按名称升序', value: 'name_asc' },
  { label: '按名称降序', value: 'name_desc' },
  { label: '按创建时间降序', value: 'created_at_desc' },
  { label: '按创建时间升序', value: 'created_at_asc' },
]

// 从 localStorage 恢复排序偏好，如无则默认为按更新时间降序
const saved = localStorage.getItem(SORT_KEY)
const sortValue = ref(sortOptions.some(o => o.value === saved) ? saved : 'updated_at_desc')

// 将 "updated_at_desc" 拆解为 sort_by + sort_order
const parseSort = (val) => {
  const idx = val.lastIndexOf('_')
  return { sort_by: val.substring(0, idx), sort_order: val.substring(idx + 1) }
}

const { sort_by, sort_order } = parseSort(sortValue.value)
const sortBy = ref(sort_by)
const sortOrder = ref(sort_order)

const onSortChange = (val) => {
  localStorage.setItem(SORT_KEY, val)
  const parsed = parseSort(val)
  sortBy.value = parsed.sort_by
  sortOrder.value = parsed.sort_order
  load(searchText.value)
}

// ---------- 前端过滤：用搜索结果做二次筛选 ----------
// 实际上后端已经搜索过了，但为了搜索时立即响应，保留一份已过滤的数据
// 注意：此处使用 allProjects 直接作为 filteredProjects，因为后端已做过滤
const filteredProjects = allProjects

// ---------- 弹窗 ----------
const showCreate = ref(false)
const editTarget = ref(null)
const form = ref({ name: '', description: '', start_date: null })

onMounted(() => load())

const resetForm = () => { form.value = { name: '', description: '', start_date: null }; editTarget.value = null }

const submit = async () => {
  if (!form.value.name.trim()) { ElMessage.warning('项目名称不能为空'); return }
  loading.value = true
  try {
    if (editTarget.value) {
      await updateProject(editTarget.value.id, form.value)
      ElMessage.success('已更新')
    } else {
      await createProject(form.value)
      ElMessage.success('创建成功')
    }
    showCreate.value = false
    await load(searchText.value)
  } finally { loading.value = false }
}

const onCmd = async (cmd, p) => {
  if (cmd === 'edit') {
    editTarget.value = p
    form.value = { name: p.name, description: p.description, start_date: p.start_date }
    showCreate.value = true
  } else if (cmd === 'delete') {
    await ElMessageBox.confirm(`确定删除项目「${p.name}」及其所有任务吗？`, '警告', { type: 'warning' })
    await deleteProject(p.id)
    ElMessage.success('已删除')
    await load(searchText.value)
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}
.page-title { font-size: 20px; font-weight: 600; }
.page-sub { font-size: 13px; color: #888; margin-top: 4px; }
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.search-wrapper {
  display: flex;
  align-items: center;
}
.proj-card {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e8e8e4;
  padding: 18px 20px;
  cursor: pointer;
  transition: border-color .15s, box-shadow .15s;
}
.proj-card:hover {
  border-color: #534ab7;
  box-shadow: 0 2px 12px rgba(83,74,183,.1);
}
.proj-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.proj-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #eeedfe;
  color: #534ab7;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}
.proj-name { font-weight: 500; font-size: 15px; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.proj-desc {
  font-size: 13px;
  color: #888;
  margin-bottom: 12px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.proj-date { font-size: 12px; color: #bbb; }
.date-sep { margin: 0 6px; color: #ddd; }
.error-card {
  text-align: center;
  padding: 80px 20px;
  background: #fff;
  border-radius: 10px;
  border: 1px solid #f0c0c0;
}
.error-card h3 { margin: 12px 0 8px; color: #2c2c2a; }
.error-card p { color: #888; font-size: 13px; }
</style>
