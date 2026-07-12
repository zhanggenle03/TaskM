<template>
  <div>
    <!-- 页面头部：标题 + 统计 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">项目列表</h1>
        <p class="page-sub">共 {{ displayProjects.length }} 个项目</p>
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
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon> 新建项目
        </el-button>
      </div>
    </div>

    <!-- 书签式分类标签栏 -->
    <div class="bookmark-tabs">
      <div
        class="bookmark-tab"
        :class="{ active: activeCategory === 'all' }"
        @click="selectCategory('all')"
      >
        <span class="bookmark-tab-name">全部项目</span>
        <span class="bookmark-count">{{ allProjects.length }}</span>
      </div>

      <div
        v-for="cat in categories"
        :key="cat.key"
        class="bookmark-tab"
        :class="{ active: activeCategory === cat.key, dragging: dragKey === cat.key, dragover: dragOverKey === cat.key }"
        draggable="true"
        @click="selectCategory(cat.key)"
        @dragstart="onDragStart($event, cat)"
        @dragover.prevent="onDragOver(cat)"
        @dragleave="onDragLeave(cat)"
        @drop="onDrop($event, cat)"
        @dragend="onDragEnd"
      >
        <span v-if="defaultKey === cat.key" class="bookmark-star" title="默认书签">
          <el-icon><StarFilled /></el-icon>
        </span>
        <span class="bookmark-tab-name">{{ cat.name }}</span>
        <span class="bookmark-count">{{ countFor(cat.key) }}</span>
        <el-dropdown trigger="click" @command="cmd => onBookmarkCmd(cmd, cat)" @click.stop>
          <button class="bookmark-menu-btn" title="书签操作" @click.stop>
            <el-icon><MoreFilled /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="default">
                {{ defaultKey === cat.key ? '取消默认' : '设为默认' }}
              </el-dropdown-item>
              <el-dropdown-item command="rename">重命名</el-dropdown-item>
              <el-dropdown-item command="delete" style="color:#e24b4a">删除</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <!-- 添加书签 -->
      <button class="bookmark-add" title="添加书签" @click="addBookmark">
        <el-icon><Plus /></el-icon>
      </button>
    </div>

    <!-- 项目卡片 -->
    <el-row :gutter="16" v-if="displayProjects.length">
      <el-col
        :xs="24" :sm="12" :md="8"
        v-for="p in displayProjects"
        :key="p.id"
        style="margin-bottom:16px"
      >
        <div class="proj-card" :class="{ 'proj-card-pinned': p.pinned }" @click="$router.push(`/projects/${p.display_id}`)">
          <div class="proj-card-header">
            <div class="proj-icon">{{ p.name[0] }}</div>
            <div class="proj-info">
              <div class="proj-info-top">
                <el-tag v-if="p.display_id" size="small" type="info" effect="plain" style="font-size:10px;padding:0 3px;height:16px;line-height:16px;margin-bottom:1px;border-width:0">{{ p.display_id }}</el-tag>
                <el-tag v-if="p.pinned" class="pinned-tag" size="small" effect="dark">置顶</el-tag>
                <el-tag v-if="categoryNameOf(p)" size="small" effect="plain" class="cat-tag">{{ categoryNameOf(p) }}</el-tag>
              </div>
              <div class="proj-name">{{ p.name }}</div>
            </div>
            <el-dropdown trigger="click" @command="cmd => onCmd(cmd, p)">
              <el-button size="small" @click.stop>
                <el-icon><MoreFilled /></el-icon> 操作
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="pin">{{ p.pinned ? '取消置顶' : '置顶' }}</el-dropdown-item>
                  <el-dropdown-item command="category">设置分类</el-dropdown-item>
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

    <!-- 当前分类下无项目 -->
    <el-empty v-else-if="loaded && !searchText && activeCategory !== 'all' && !apiError" :description="`「${activeCategoryName}」分类下还没有项目`">
      <el-button @click="selectCategory('all')">查看全部项目</el-button>
    </el-empty>

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
        <el-form-item label="分类">
          <el-select v-model="form.category" placeholder="选择书签分类" style="width:100%">
            <el-option label="未分类" value="" />
            <el-option v-for="cat in categories" :key="cat.key" :label="cat.name" :value="cat.key" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
        <el-form-item label="开始时间">
          <el-date-picker v-model="form.start_date" type="date" value-format="YYYY-MM-DD" placeholder="选择开始日期" style="width:100%" />
        </el-form-item>
        <el-form-item v-if="!editTarget" label="显示前缀">
          <el-input v-model="form.custom_prefix" maxlength="3" placeholder="3个大写字母，留空随机生成" @input="v => form.custom_prefix = v.toUpperCase()" />
          <div style="font-size:12px;color:#999;margin-top:4px">前缀创建后不可更改</div>
        </el-form-item>
        <el-form-item v-else label="显示前缀">
          <el-input :model-value="editTarget.custom_prefix" disabled />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" :loading="loading" @click="submit">确定</el-button>
      </template>
    </el-dialog>

    <!-- 设置分类弹窗 -->
    <el-dialog v-model="showCategory" title="设置分类" width="360px" @close="categoryTarget = null">
      <el-form label-width="70px">
        <el-form-item label="项目">
          <span style="color:#555">{{ categoryTarget?.name }}</span>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="categoryValue" placeholder="选择书签分类" style="width:100%">
            <el-option label="未分类" value="" />
            <el-option v-for="cat in categories" :key="cat.key" :label="cat.name" :value="cat.key" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCategory = false">取消</el-button>
        <el-button type="primary" @click="submitCategory">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { getProjects, createProject, updateProject, deleteProject, getCategories, createCategory, renameCategory, deleteCategory, reorderCategories, getDefaultCategory, setDefaultCategory } from '../api'

// ---------- 数据 ----------
const allProjects = ref([])
const categories = ref([])
const loading = ref(false)
const apiError = ref('')
const loaded = ref(false) // 标记首次数据是否已加载完成

// ---------- 书签分类 ----------
const activeCategory = ref('all')

const activeCategoryName = computed(() => {
  if (activeCategory.value === 'all') return '全部'
  const c = categories.value.find(x => x.key === activeCategory.value)
  return c ? c.name : '全部'
})

const selectCategory = (key) => {
  activeCategory.value = key
}

const categoryNameOf = (p) => {
  const key = p.category || ''
  if (!key) return ''
  const c = categories.value.find(x => x.key === key)
  return c ? c.name : ''
}

const countFor = (key) => {
  if (key === 'all') return allProjects.value.length
  return allProjects.value.filter(p => (p.category || '') === key).length
}

const displayProjects = computed(() => {
  if (activeCategory.value === 'all') return allProjects.value
  return allProjects.value.filter(p => (p.category || '') === activeCategory.value)
})

const loadCategories = async () => {
  try {
    categories.value = await getCategories()
  } catch (e) {
    // 书签读取失败不阻塞项目列表
  }
}

// ---------- 默认书签（服务端持久化，最多 1 个） ----------
const defaultKey = ref('')

const loadDefaultCategory = async () => {
  try {
    const def = await getDefaultCategory()
    defaultKey.value = def.key || ''
  } catch (e) {
    defaultKey.value = ''
  }
}

// 依据服务端默认书签初始化当前激活项（无默认书签则显示全部）
const initActiveFromDefault = () => {
  const init = defaultKey.value && categories.value.some(c => c.key === defaultKey.value)
    ? defaultKey.value
    : 'all'
  activeCategory.value = init
}

// 切换某书签为默认 / 取消默认
const toggleDefault = async (cat) => {
  try {
    const key = defaultKey.value === cat.key ? '' : cat.key
    const r = await setDefaultCategory(key)
    defaultKey.value = r.key || ''
    ElMessage.success(key ? '已设为默认书签' : '已取消默认书签')
  } catch (e) {
    ElMessage.error(e?.message || '设置失败')
  }
}

// ---------- 书签拖拽排序 ----------
const dragKey = ref(null)      // 正在拖动的书签 key
const dragOverKey = ref(null)  // 当前悬停（作为落点）的书签 key

const onDragStart = (e, cat) => {
  dragKey.value = cat.key
  e.dataTransfer.effectAllowed = 'move'
  // 部分浏览器要求必须调用 setData 才能触发拖拽
  try { e.dataTransfer.setData('text/plain', cat.key) } catch (_) {}
}
const onDragOver = (cat) => {
  if (dragKey.value && dragKey.value !== cat.key) dragOverKey.value = cat.key
}
const onDragLeave = (cat) => {
  if (dragOverKey.value === cat.key) dragOverKey.value = null
}
const onDrop = async (e, cat) => {
  e.preventDefault()
  const from = dragKey.value
  const to = cat.key
  dragOverKey.value = null
  dragKey.value = null
  if (!from || from === to) return
  const list = [...categories.value]
  const fromIdx = list.findIndex(c => c.key === from)
  const toIdx = list.findIndex(c => c.key === to)
  if (fromIdx < 0 || toIdx < 0) return
  const [moved] = list.splice(fromIdx, 1)
  list.splice(toIdx, 0, moved)
  categories.value = list
  try {
    await reorderCategories(list.map(c => c.key))
    ElMessage.success('已调整书签顺序')
  } catch (err) {
    ElMessage.error(err?.message || '排序保存失败')
    loadCategories() // 回滚到服务端真实顺序
  }
}
const onDragEnd = () => {
  dragKey.value = null
  dragOverKey.value = null
}

const addBookmark = async () => {
  try {
    const { value } = await ElMessageBox.prompt('输入新书签名称', '添加书签', {
      confirmButtonText: '添加',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '名称不能为空',
    })
    const name = value.trim()
    const cat = await createCategory(name)
    categories.value.push(cat)
    ElMessage.success('已添加书签')
    selectCategory(cat.key)
  } catch (e) {
    if (e !== 'cancel' && e?.message) ElMessage.error(e.message || '添加失败')
  }
}

const onBookmarkCmd = async (cmd, cat) => {
  if (cmd === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('修改书签名称', '重命名书签', {
        confirmButtonText: '保存',
        cancelButtonText: '取消',
        inputValue: cat.name,
        inputPattern: /\S+/,
        inputErrorMessage: '名称不能为空',
      })
      const updated = await renameCategory(cat.key, value.trim())
      const idx = categories.value.findIndex(c => c.key === cat.key)
      if (idx >= 0) categories.value[idx] = updated
      ElMessage.success('已重命名')
    } catch (e) {
      if (e !== 'cancel' && e?.message) ElMessage.error(e.message || '重命名失败')
    }
  } else if (cmd === 'default') {
    await toggleDefault(cat)
  } else if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(
        `删除书签「${cat.name}」后，归入该分类的项目将变为「未分类」。确定继续？`,
        '删除书签',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
      )
      await deleteCategory(cat.key)
      categories.value = categories.value.filter(c => c.key !== cat.key)
      if (activeCategory.value === cat.key) selectCategory('all')
      // 同步默认书签（若删掉的是默认，后端已清除，需刷新）
      await loadDefaultCategory()
      ElMessage.success('已删除')
    } catch (e) {
      if (e !== 'cancel') ElMessage.error(e?.message || '删除失败')
    }
  }
}

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

// ---------- 弹窗 ----------
const showCreate = ref(false)
const editTarget = ref(null)
const form = ref({ name: '', description: '', start_date: null, category: '' })

const openCreate = () => {
  resetForm()
  // 新建时默认归入当前选中的书签（若不是"全部"）
  form.value.category = activeCategory.value !== 'all' ? activeCategory.value : ''
  showCreate.value = true
}

onMounted(async () => {
  await Promise.all([loadCategories(), loadDefaultCategory()])
  initActiveFromDefault()
  load()
})

const resetForm = () => { form.value = { name: '', description: '', start_date: null, custom_prefix: '', category: '' }; editTarget.value = null }

const submit = async () => {
  if (!form.value.name.trim()) { ElMessage.warning('项目名称不能为空'); return }
  loading.value = true
  try {
    if (editTarget.value) {
      await updateProject(editTarget.value.display_id, form.value)
      ElMessage.success('已更新')
    } else {
      await createProject(form.value)
      ElMessage.success('创建成功')
    }
    showCreate.value = false
    await load(searchText.value)
  } finally { loading.value = false }
}

// ---------- 设置分类弹窗 ----------
const showCategory = ref(false)
const categoryTarget = ref(null)
const categoryValue = ref('')

const submitCategory = async () => {
  if (!categoryTarget.value) return
  try {
    await updateProject(categoryTarget.value.display_id, { category: categoryValue.value })
    ElMessage.success('已更新分类')
    showCategory.value = false
    await load(searchText.value)
  } catch (e) {
    ElMessage.error(e?.message || '更新失败')
  }
}

const onCmd = async (cmd, p) => {
  if (cmd === 'pin') {
    await updateProject(p.display_id, { pinned: !p.pinned })
    ElMessage.success(p.pinned ? '已取消置顶' : '已置顶')
    await load(searchText.value)
  } else if (cmd === 'category') {
    categoryTarget.value = p
    categoryValue.value = p.category || ''
    showCategory.value = true
  } else if (cmd === 'edit') {
    editTarget.value = p
    form.value = { name: p.name, description: p.description, start_date: p.start_date, custom_prefix: p.custom_prefix, category: p.category || '' }
    showCreate.value = true
  } else if (cmd === 'delete') {
    await ElMessageBox.confirm(`确定删除项目「${p.name}」及其所有任务吗？`, '警告', { type: 'warning' })
    await deleteProject(p.display_id)
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
  margin-bottom: 16px;
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

/* ---- 书签式标签栏 ---- */
.bookmark-tabs {
  display: flex;
  align-items: flex-end;
  gap: 2px;
  border-bottom: 1px solid #e5e5ea;
  margin-bottom: 20px;
  padding-left: 4px;
  overflow-x: auto;
  /* 隐藏滚动条（保留滚动能力，书签过多时仍可横向滚动） */
  scrollbar-width: none;       /* Firefox */
  -ms-overflow-style: none;    /* IE/旧 Edge */
}
.bookmark-tabs::-webkit-scrollbar {
  display: none;               /* Chrome / Safari / Edge */
}
.bookmark-tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  font-size: 13px;
  color: #6e6e73;
  cursor: pointer;
  border-radius: 7px 7px 0 0;
  position: relative;
  transition: all .15s ease;
  user-select: none;
  margin-bottom: -1px;
  border: 1px solid transparent;
  border-bottom: none;
  white-space: nowrap;
  flex-shrink: 0;
}
.bookmark-tab:hover {
  color: #534ab7;
  background: rgba(83, 74, 183, .05);
}
.bookmark-tab.active {
  color: #534ab7;
  background: #fff;
  border: 1px solid #e5e5ea;
  border-bottom: 1px solid #fff;
  font-weight: 500;
}
.bookmark-tab.active::after {
  content: "";
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: #534ab7;
  border-radius: 2px 2px 0 0;
}
/* 拖拽中：源书签半透明 */
.bookmark-tab.dragging {
  opacity: .4;
}
/* 拖拽悬停落点：高亮提示 */
.bookmark-tab.dragover {
  background: rgba(83, 74, 183, .12);
  box-shadow: inset 0 0 0 1px #534ab7;
}
.bookmark-tab-name {
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bookmark-count {
  font-size: 11px;
  color: #aeaeb2;
  background: #f0f0f3;
  border-radius: 10px;
  padding: 0 7px;
  line-height: 16px;
  min-width: 18px;
  text-align: center;
}
.bookmark-star {
  display: flex;
  align-items: center;
  color: #f5a623;
  font-size: 12px;
}
.bookmark-tab.active .bookmark-star {
  color: #f5a623;
}
.bookmark-tab.active .bookmark-count {
  color: #534ab7;
  background: rgba(83, 74, 183, .1);
}
.bookmark-menu-btn {
  display: none;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: #86868b;
  cursor: pointer;
  padding: 0;
  font-size: 13px;
  border-radius: 4px;
}
.bookmark-tab:hover .bookmark-menu-btn,
.bookmark-tab.active .bookmark-menu-btn {
  display: flex;
}
.bookmark-menu-btn:hover {
  color: #534ab7;
  background: rgba(83, 74, 183, .1);
}
.bookmark-add {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 0 4px 4px;
  width: 25px;
  height: 25px;
  border: 1px dashed #d2d2d7;
  background: #fff;
  color: #86868b;
  border-radius: 7px;
  cursor: pointer;
  transition: all .15s ease;
  flex-shrink: 0;
}
.bookmark-add:hover {
  color: #534ab7;
  border-color: #534ab7;
  background: rgba(83, 74, 183, .05);
}

/* ---- 项目卡片 ---- */
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
.proj-name { font-weight: 500; font-size: 15px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.proj-info { flex: 1; min-width: 0; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; }
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

/* 置顶 */
.proj-card-pinned {
  border-color: #534ab7;
  box-shadow: 0 1px 6px rgba(83,74,183,.08);
}
.proj-info-top {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.pinned-tag {
  height: 18px;
  line-height: 18px;
  padding: 0 5px;
  font-size: 10px;
  border: 0;
  background: #534ab7;
  color: #fff;
  border-radius: 3px;
  flex-shrink: 0;
}
.cat-tag {
  height: 18px;
  line-height: 18px;
  padding: 0 5px;
  font-size: 10px;
  color: #534ab7;
  background: rgba(83, 74, 183, .08);
  border: 0;
  border-radius: 3px;
  flex-shrink: 0;
}
</style>
