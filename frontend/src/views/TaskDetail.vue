<template>
  <div>
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item :to="{ path: `/projects/${projectId}` }">{{ project?.name || `项目 #${projectId}` }}</el-breadcrumb-item>
      <el-breadcrumb-item>{{ task?.title || '任务详情' }}</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 隐藏的文件选择器 -->
    <input type="file" ref="hiddenFileInput" style="display:none" @change="onFileInputChange" />

    <div v-if="task" class="page-body">
      <!-- 左侧列 -->
      <div class="body-main">
        <!-- 标题 + 删除按钮 -->
        <div class="title-row">
          <div class="title-left">
            <el-button @click="router.back()" class="back-btn">
              <el-icon><ArrowLeft /></el-icon> 返回
            </el-button>
            <h1 class="page-title">{{ task.title }}</h1>
            <el-button size="small" text @click="openEditTask" class="title-edit-btn">
              <el-icon><Edit /></el-icon>
            </el-button>
          </div>
          <div style="display:flex;gap:6px">
            <el-button size="small" @click="timelineAsc = !timelineAsc">
              <el-icon><Sort /></el-icon> {{ timelineAsc ? '最早优先' : '最新优先' }}
            </el-button>
            <el-button size="small" type="danger" @click="removeTask">
              <el-icon><Delete /></el-icon> 删除
            </el-button>
          </div>
        </div>
        <p v-if="task.description" class="task-desc">{{ task.description }}</p>
        <p v-else class="task-desc task-desc-empty">暂无描述</p>

        <!-- 沟通时间线 -->
        <div class="section-title">
          <el-icon><ChatDotRound /></el-icon> 沟通时间线
          <el-button size="small" type="primary" text @click="showAddComm = true">+ 添加记录</el-button>
        </div>

        <div class="timeline-scroll">
          <el-timeline v-if="task.communications?.length">
            <el-timeline-item
              v-for="c in (timelineAsc ? task.communications : [...task.communications].reverse())"
              :key="c.id"
              :timestamp="formatTime(c.comm_at)"
              placement="top"
            >
              <div class="comm-card">
                <div class="comm-header">
                  <span class="comm-type-badge" :style="{ background: commTypeColor(c.comm_type) + '22', color: commTypeColor(c.comm_type) }">{{ commTypeLabel(c.comm_type) }}</span>
                  <span class="comm-user">{{ (c.contacts?.length ? c.contacts.map(cn => cn.name).join('、') : c.contact?.name) || '我' }}</span>
                  <span v-if="c.old_status_id || c.new_status_id" class="comm-status">
                    <template v-if="c.old_status_id">
                      <span class="status-dot-mini" :style="{ background: statusColor(c.old_status_id) }"></span>
                      {{ statusLabel(c.old_status_id) }}
                    </template>
                    <span v-if="c.old_status_id && c.new_status_id" class="comm-arrow">→</span>
                    <template v-if="c.new_status_id">
                      <span class="status-dot-mini" :style="{ background: statusColor(c.new_status_id) }"></span>
                      {{ statusLabel(c.new_status_id) }}
                    </template>
                  </span>
                  <div style="flex:1"></div>
                  <el-button size="small" text @click="openEditComm(c)"><el-icon><Edit /></el-icon></el-button>
                  <el-button size="small" text type="danger" @click="removeComm(c)"><el-icon><Delete /></el-icon></el-button>
                </div>
                <div class="comm-content">{{ c.content }}</div>
                <!-- 沟通附件 -->
                <div v-if="c.attachments?.length" class="att-list">
                  <div v-for="a in c.attachments" :key="a.id" class="att-item">
                    <el-icon><Paperclip /></el-icon>
                    <a href="javascript:void(0)" class="att-name" @click="openPreview(a, c.attachments)">{{ a.original_filename }}</a>
                    <span class="att-size">{{ formatSize(a.file_size) }}</span>
                    <a :href="downloadUrl(a.id)" class="att-download-btn" title="下载">
                      <el-icon><Download /></el-icon>
                    </a>
                    <el-button size="small" text @click="renameAtt(a)"><el-icon><Edit /></el-icon></el-button>
                    <el-button size="small" text type="danger" @click="removeAtt(a)"><el-icon><Close /></el-icon></el-button>
                  </div>
                </div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无沟通记录" :image-size="60" />
        </div>
      </div>

      <!-- 右侧信息栏 -->
      <div class="detail-side">
        <div class="side-card side-card-fields">
          <div class="side-field">
            <span class="side-field-label">任务状态</span>
            <el-select v-model="task.status_id" placeholder="设置状态" size="small" style="flex:1" @change="quickUpdateStatus">
              <el-option v-for="s in statuses" :key="s.id" :label="s.name" :value="s.id">
                <span :style="{ color: s.color, marginRight: '6px' }">●</span>{{ s.name }}
              </el-option>
            </el-select>
          </div>
          <div class="side-field">
            <span class="side-field-label">优先级</span>
            <el-select v-model="task.priority" placeholder="选择优先级" size="small" style="flex:1" @change="quickUpdatePriority">
              <el-option label="低" value="low" />
              <el-option label="普通" value="normal" />
              <el-option label="高" value="high" />
              <el-option label="紧急" value="urgent" />
            </el-select>
          </div>
          <div class="side-field">
            <span class="side-field-label">截止日期</span>
            <el-date-picker
              v-model="task.due_date" type="date" value-format="YYYY-MM-DD"
              placeholder="无截止日期" size="small" style="flex:1"
              @change="quickUpdateDue"
            />
          </div>
          <div class="side-field side-field-tags">
            <span class="side-field-label">
              标签
              <el-button size="small" text @click="showTagPicker = true" style="padding:2px;height:auto;margin-left:2px">
                <el-icon><CollectionTag /></el-icon>
              </el-button>
            </span>
            <div class="side-tag-inline">
              <div class="side-tag-chips" v-if="selectedTagIds.length">
                <span v-for="id in selectedTagIds" :key="id" class="tag-chip-detail" :style="{ background: tagColor(id) + '22', color: tagColor(id), borderColor: tagColor(id) }">{{ tagLabel(id) }}</span>
              </div>
              <span v-else style="color:#bbb;font-size:12px">无</span>
            </div>
          </div>
        </div>

        <div class="side-card">
          <div class="side-title">
            对接人
            <span style="flex:1"></span>
            <el-button size="small" text @click="showAddContact = true; resetContactForm()"><el-icon><Plus /></el-icon></el-button>
          </div>
          <div v-if="task.contacts?.length">
            <div v-for="c in task.contacts" :key="c.id" class="contact-item">
              <div class="contact-avatar">{{ c.name[0] }}</div>
              <div class="contact-info">
                <div class="contact-name">{{ c.name }}</div>
                <div class="contact-role">{{ c.role }}</div>
                <div class="contact-detail">{{ c.contact_info }}</div>
              </div>
              <el-button size="small" text @click="editContact(c)"><el-icon><Edit /></el-icon></el-button>
              <el-button size="small" text type="danger" @click="removeContact(c)"><el-icon><Close /></el-icon></el-button>
            </div>
          </div>
          <el-empty v-else description="暂无对接人" :image-size="40" />
        </div>
      </div>
    </div>

    <!-- 添加/编辑沟通记录（含对接人选择+附件上传） -->
    <el-dialog v-model="showAddComm" :title="editComm ? '编辑沟通记录' : '添加沟通记录'" width="520px" @close="resetCommForm" @open="onOpenCommDialog">
      <el-form :model="commForm" label-width="80px">
        <el-form-item label="对接人">
          <el-select v-model="commForm.contact_ids" placeholder="选择对接人" multiple clearable style="width:100%">
            <el-option v-for="c in task?.contacts || []" :key="c.id" :value="c.id" :label="c.name">
              <span>{{ c.name }}</span>
              <span style="color:#999;margin-left:6px;font-size:12px">{{ c.role }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="沟通内容" required>
          <div @paste.capture="onContentPaste" style="width:100%">
            <el-input v-model="commForm.content" type="textarea" :rows="4" placeholder="描述本次沟通内容..." />
          </div>
        </el-form-item>
        <el-form-item label="沟通类型">
          <el-select v-model="commForm.comm_type">
            <el-option v-for="ct in commTypes" :key="ct.name" :value="ct.name" :label="ct.name">
              <span :style="{ color: ct.color, marginRight: '4px' }">●</span>{{ ct.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="时间">
          <el-date-picker v-model="commForm.comm_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="默认当前时间" />
        </el-form-item>
        <el-form-item label="状态变更">
          <div style="display:flex;align-items:center;gap:8px;width:100%">
            <el-select v-model="commForm.old_status_id" placeholder="当前" style="width:160px">
              <el-option v-for="s in statuses" :key="s.id" :label="s.name" :value="s.id">
                <span :style="{ color: s.color, marginRight: '6px' }">●</span>{{ s.name }}
              </el-option>
            </el-select>
            <el-icon><ArrowRight /></el-icon>
            <el-select v-model="commForm.new_status_id" placeholder="不变更" clearable style="width:160px">
              <el-option v-for="s in statuses" :key="s.id" :label="s.name" :value="s.id" :disabled="s.id === commForm.old_status_id">
                <span :style="{ color: s.color, marginRight: '6px' }">●</span>{{ s.name }}
              </el-option>
            </el-select>
          </div>
        </el-form-item>
        <el-form-item label="附件">
          <!-- 新建沟通：简洁附件上传 -->
          <template v-if="!editComm">
            <div style="width:100%">
              <div style="display:flex;align-items:center;gap:8px">
                <el-button size="small" text @click="triggerAddUpload">
                  <el-icon><Paperclip /></el-icon> 选择文件
                </el-button>
                <span style="font-size:12px;color:#999">或 Ctrl+V 粘贴文件</span>
              </div>
              <div v-if="pastedFiles.length" class="dialog-att-list" style="margin-top:4px">
                <div v-for="(f, i) in pastedFiles" :key="i" class="dialog-att-item">
                  <el-icon><Paperclip /></el-icon>
                  <span class="dialog-att-name">{{ f.name }}</span>
                  <span class="att-size">{{ formatSize(f.size) }}</span>
                  <el-button size="small" text @click="renamePastedFile(i)"><el-icon><Edit /></el-icon></el-button>
                  <el-button size="small" text type="danger" @click="pastedFiles.splice(i, 1)"><el-icon><Close /></el-icon></el-button>
                </div>
              </div>
            </div>
          </template>
          <!-- 编辑沟通：已有附件 + 回形针上传 -->
          <template v-else>
            <div style="width:100%">
              <div class="dialog-att-list" v-if="editComm.attachments?.length">
                <div v-for="a in editComm.attachments" :key="a.id" class="dialog-att-item">
                  <el-icon><Paperclip /></el-icon>
                  <a :href="downloadUrl(a.id)" target="_blank" class="dialog-att-name" :title="a.original_filename">{{ a.original_filename }}</a>
                  <span class="att-size">{{ formatSize(a.file_size) }}</span>
                  <el-button size="small" text @click="renameAtt(a)"><el-icon><Edit /></el-icon></el-button>
                  <el-button size="small" text type="danger" @click="removeAtt(a)"><el-icon><Close /></el-icon></el-button>
                </div>
              </div>
              <div style="display:flex;align-items:center;gap:8px;margin-top:4px">
                <el-button size="small" text @click="triggerEditUpload">
                  <el-icon><Paperclip /></el-icon> 选择文件
                </el-button>
                <span style="font-size:12px;color:#999">或 Ctrl+V 粘贴文件</span>
              </div>
            </div>
          </template>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddComm = false">取消</el-button>
        <el-button type="primary" :loading="commLoading" @click="submitComm">确定</el-button>
      </template>
    </el-dialog>

    <!-- 添加/编辑对接人 -->
    <el-dialog v-model="showAddContact" :title="editContactRef ? '编辑对接人' : '添加对接人'" width="400px" @close="resetContactForm">
      <el-form :model="contactForm" label-width="80px">
        <el-form-item label="姓名" required>
          <el-select
            v-model="contactForm.name"
            filterable
            allow-create
            default-first-option
            placeholder="选择或输入对接人"
            style="width:100%"
          >
            <el-option
              v-for="pc in projectContacts.filter(pc => !task?.contacts?.find(c => c.name === pc.name))"
              :key="pc.id"
              :label="pc.name"
              :value="pc.name"
            >
              <span>{{ pc.name }}</span>
              <span style="color:#999;margin-left:6px;font-size:12px">{{ pc.role }}</span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-input v-model="contactForm.role" placeholder="如：项目经理、开发负责人" />
        </el-form-item>
        <el-form-item label="联系方式">
          <el-input v-model="contactForm.contact_info" placeholder="手机/邮件/微信" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddContact = false">取消</el-button>
        <el-button type="primary" :loading="contactLoading" @click="submitContact">确定</el-button>
      </template>
    </el-dialog>



    <!-- 编辑任务 -->
    <el-dialog v-model="showEditTask" title="编辑任务" width="480px">
      <el-form :model="taskForm" label-width="80px">
        <el-form-item label="标题"><el-input v-model="taskForm.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="taskForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="标签">
          <el-select v-model="taskForm.tag_ids" multiple placeholder="选择标签" style="width:100%">
            <el-option v-for="t in tags" :key="t.id" :value="t.id" :label="t.name">
              <span :style="{ color: t.color, marginRight: '6px' }">●</span>{{ t.name }}
            </el-option>
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditTask = false">取消</el-button>
        <el-button type="primary" @click="submitEditTask">确定</el-button>
      </template>
    </el-dialog>

    <!-- 标签选择弹窗 -->
    <el-dialog v-model="showTagPicker" title="选择标签" width="450px" @open="pickerSelected = [...selectedTagIds]" @close="resetTagPicker">
      <div class="tag-picker-body">
        <div class="tag-picker-section">
          <div class="tag-picker-section-title">待选</div>
          <div class="tag-picker-capsules" v-if="availableTags.length">
            <div v-for="t in availableTags" :key="t.id" class="tag-capsule" :style="{ borderColor: t.color, color: t.color }" @click="selectTag(t.id)">
              <span class="tag-dot" :style="{ background: t.color }"></span>
              <span>{{ t.name }}</span>
              <el-icon style="margin-left:3px;font-size:13px"><Plus /></el-icon>
            </div>
          </div>
          <div v-else class="tag-picker-empty">所有标签已选择</div>
        </div>
        <div class="tag-picker-divider"></div>
        <div class="tag-picker-section">
          <div class="tag-picker-section-title">已选</div>
          <div class="tag-picker-capsules" v-if="pickerSelected.length">
            <div v-for="id in pickerSelected" :key="id" class="tag-capsule tag-capsule-selected" :style="{ background: tagColor(id), borderColor: tagColor(id) }" @click="unselectTag(id)">
              <span>{{ tagLabel(id) }}</span>
              <el-icon style="margin-left:3px;font-size:13px"><Close /></el-icon>
            </div>
          </div>
          <div v-else class="tag-picker-empty">暂无已选标签</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="showTagPicker = false">取消</el-button>
        <el-button type="primary" @click="submitTagPicker">确定</el-button>
      </template>
    </el-dialog>

    <!-- 附件预览弹窗 -->
    <el-dialog v-model="previewDialog" width="80%" top="5vh" destroy-on-close>
      <template #header>
        <div class="preview-header">
          <span class="preview-title">{{ previewTitle }}</span>
          <span v-if="previewList.length > 1" class="preview-counter">{{ previewIndex + 1 }} / {{ previewList.length }}</span>
        </div>
      </template>

      <!-- 图片预览 -->
      <div v-if="previewIsImage" class="preview-img-wrap" @wheel.prevent="onImgWheel">
        <div class="preview-img-container">
          <img :src="previewSrc" class="preview-img" draggable="false"
            :style="{
              transform: `translate(${imgState.x}px, ${imgState.y}px) scale(${imgState.scale})`,
              transformOrigin: '0 0',
              cursor: isDragging ? 'grabbing' : imgState.scale !== 1 ? 'grab' : 'default'
            }"
            @mousedown="onImgMouseDown"
            @mousemove="onImgMouseMove"
            @mouseup="onImgMouseUp"
            @mouseleave="onImgMouseUp"
          />
        </div>
      </div>

      <!-- 非图片预览（iframe） -->
      <div v-else class="preview-other-wrap" @wheel.prevent="onOtherWheel">
        <iframe :src="previewSrc"
          :style="{
            width: `${100 * imgState.scale}%`,
            height: `${70 * imgState.scale}vh`,
            border: 'none',
            borderRadius: '4px',
            background: '#fff',
            transformOrigin: 'top left',
            display: 'block'
          }"
        />
      </div>

      <!-- 工具栏：左右切换 + 重置 -->
      <div v-if="previewList.length > 1 || imgState.scale !== 1" class="preview-toolbar">
        <template v-if="previewList.length > 1">
          <el-button size="small" :disabled="previewIndex <= 0" @click="previewPrev"><el-icon><ArrowLeft /></el-icon></el-button>
          <span class="preview-counter">{{ previewIndex + 1 }} / {{ previewList.length }}</span>
          <el-button size="small" :disabled="previewIndex >= previewList.length - 1" @click="previewNext"><el-icon><ArrowRight /></el-icon></el-button>
        </template>
        <span v-if="previewList.length > 1 && imgState.scale !== 1" class="tb-sep"></span>
        <el-button v-if="imgState.scale !== 1" size="small" text @click="resetImageZoom">重置</el-button>
      </div>

      <template #footer>
        <el-button @click="previewDialog = false">关闭</el-button>
        <el-button type="primary" @click="downloadPreview">下载</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import {
  getTask, getProjects, getCommTypes, updateTask, getStatuses, deleteTask,
  addContact, updateContact, deleteContact,
  addCommunication, updateCommunication, deleteCommunication,
  uploadCommAttachment, deleteAttachment, renameAttachment, downloadAttachment,
  getProjectContacts, getTags
} from '../api'

const route = useRoute()
const router = useRouter()
const projectId = Number(route.params.projectId)
const taskId = Number(route.params.taskId)
const task = ref(null)
const project = ref(null)
const statuses = ref([])
const commTypes = ref([])
const projectContacts = ref([])  // 项目对接人库（用于选择）
const tags = ref([])  // 项目标签池
const selectedTagIds = ref([])  // 当前任务的标签 ID 列表
const showTagPicker = ref(false)
const pickerSelected = ref([])  // 弹窗内临时选择的标签 ID
const availableTags = computed(() => tags.value.filter(t => !pickerSelected.value.includes(t.id)))

const showAddComm = ref(false)
const commLoading = ref(false)
const editComm = ref(null)
const commForm = ref({ content: '', contact_ids: [], comm_type: '', comm_at: null, files: [], old_status_id: null, new_status_id: null })
const pastedFiles = ref([])  // 粘贴或选择的临时文件，提交时一起上传

const hiddenFileInput = ref(null)
const uploadTargetComm = ref(null)

const showAddContact = ref(false)
const contactLoading = ref(false)
const editContactRef = ref(null)  // 编辑中的对接人，null=新增模式
const contactForm = ref({ name: '', role: '', contact_info: '' })

const showEditTask = ref(false)
const taskForm = ref({ title: '', description: '', priority: 'normal', tag_ids: [] })

// 附件预览
const previewDialog = ref(false)
const previewSrc = ref('')
const previewTitle = ref('')
const previewAttId = ref(null)
const previewIsImage = ref(false)
const previewList = ref([])
const previewIndex = ref(0)
const imageExts = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.svg', '.ico']

const timelineAsc = ref(false)  // 时间线排序：false=最新的在前面，true=最早的在前

const imgState = ref({ x: 0, y: 0, scale: 1 })
const isDragging = ref(false)
const dragStart = { x: 0, y: 0 }
const dragImgState = { x: 0, y: 0 }

const openPreview = (a, list) => {
  previewList.value = list || []
  previewIndex.value = previewList.value.findIndex(item => item.id === a.id)
  applyPreview(a)
  previewDialog.value = true
}

const applyPreview = (a) => {
  previewAttId.value = a.id
  previewTitle.value = a.original_filename
  previewSrc.value = previewUrl(a.id)
  const ext = (a.original_filename?.split('.').pop() || '').toLowerCase()
  previewIsImage.value = imageExts.includes('.' + ext)
  imgState.value = { x: 0, y: 0, scale: 1 }
}

const previewPrev = () => {
  if (previewIndex.value <= 0) return
  previewIndex.value--
  applyPreview(previewList.value[previewIndex.value])
}

const previewNext = () => {
  if (previewIndex.value >= previewList.value.length - 1) return
  previewIndex.value++
  applyPreview(previewList.value[previewIndex.value])
}

const onImgWheel = (e) => {
  const step = e.deltaY > 0 ? -0.05 : 0.05
  const newScale = Math.round((imgState.value.scale + step) * 100) / 100
  if (newScale < 0.01) { imgState.value = { x: 0, y: 0, scale: 0.01 }; return }
  // 居中状态（未拖拽过）只调大小不移动位置，保证第一次缩放无跳动
  if (imgState.value.x === 0 && imgState.value.y === 0) {
    imgState.value = { x: 0, y: 0, scale: newScale }
    return
  }
  const wrap = e.currentTarget
  const rect = wrap.getBoundingClientRect()
  const mx = rect.width / 2
  const my = rect.height / 2
  const ratio = newScale / imgState.value.scale
  imgState.value = {
    x: Math.round((imgState.value.x + mx * (1 - ratio)) * 10) / 10,
    y: Math.round((imgState.value.y + my * (1 - ratio)) * 10) / 10,
    scale: newScale,
  }
}

const onImgMouseDown = (e) => {
  if (e.button !== 0 || imgState.value.scale === 1) return
  isDragging.value = true
  dragStart.x = e.clientX
  dragStart.y = e.clientY
  dragImgState.x = imgState.value.x
  dragImgState.y = imgState.value.y
  e.preventDefault()
}

const onImgMouseMove = (e) => {
  if (!isDragging.value) return
  imgState.value = {
    ...imgState.value,
    x: +(dragImgState.x + e.clientX - dragStart.x).toFixed(1),
    y: +(dragImgState.y + e.clientY - dragStart.y).toFixed(1),
  }
}

const onImgMouseUp = () => {
  isDragging.value = false
}

const onOtherWheel = (e) => {
  const step = e.deltaY > 0 ? -0.05 : 0.05
  const newScale = Math.round((imgState.value.scale + step) * 100) / 100
  if (newScale < 0.01) { imgState.value = { x: 0, y: 0, scale: 0.01 }; return }
  imgState.value = { x: 0, y: 0, scale: newScale }
}

const resetImageZoom = () => {
  imgState.value = { x: 0, y: 0, scale: 1 }
}

const downloadPreview = () => {
  if (previewAttId.value) {
    window.open(downloadUrl(previewAttId.value), '_blank')
  }
}

// 选择对接人时自动填充角色和联系方式
watch(() => contactForm.value.name, (newName) => {
  if (!newName || editContactRef.value) return  // 编辑模式不自动填充
  const matched = projectContacts.value.find(pc => pc.name === newName)
  if (matched) {
    contactForm.value.role = matched.role
    contactForm.value.contact_info = matched.contact_info
  }
})

const load = async () => {
  const [t, s, ct, allProjects, tg] = await Promise.all([getTask(projectId, taskId), getStatuses(projectId), getCommTypes(projectId), getProjects(), getTags(projectId)])
  // 后端已从沟通记录推导出最终 status_id，直接使用
  task.value = t
  statuses.value = s
  commTypes.value = ct
  project.value = allProjects.find((p) => p.id === projectId) || null
  tags.value = tg
  selectedTagIds.value = (t.tags || []).map(tag => tag.id)
  // 加载项目对接人库
  try {
    projectContacts.value = await getProjectContacts(projectId, {})
  } catch (e) {
    console.error('加载项目对接人库失败', e)
  }
}
onMounted(() => {
  load()
})

onUnmounted(() => {})

const formatTime = (t) => dayjs(t).format('YYYY-MM-DD HH:mm')
const formatSize = (bytes) => bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)}MB` : `${Math.round(bytes / 1024)}KB`
const downloadUrl = (id) => `/api/attachments/${id}/download`
const previewUrl = (id) => `/api/attachments/${id}/preview`
const priorityLabel = (p) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[p] || p)
const priorityType = (p) => ({ low: 'info', normal: '', high: 'warning', urgent: 'danger' }[p] || '')
const commTypeLabel = (name) => commTypes.value.find((ct) => ct.name === name)?.name || name
const commTypeColor = (name) => commTypes.value.find((ct) => ct.name === name)?.color || '#888'
const statusLabel = (id) => statuses.value.find(s => s.id === id)?.name || ''
const statusColor = (id) => statuses.value.find(s => s.id === id)?.color || '#888'
const tagColor = (id) => tags.value.find(t => t.id === id)?.color || '#5F5E5A'
const tagLabel = (id) => tags.value.find(t => t.id === id)?.name || ''

const quickUpdateStatus = async (newStatusId) => {
  if (!task.value) return
  try {
    const res = await updateTask(projectId, taskId, { status_id: newStatusId })
    // 后端返回的 status_id 已是推导后的值，直接覆盖
    if (res) {
      task.value = { ...task.value, ...res }
    }
    // 再完整加载一次（包含新生成的沟通记录）
    await load()
    ElMessage.success('状态已更新')
  } catch {
    // 失败时回退到旧值
    await load()
  }
}
const quickUpdateDue = async (val) => {
  await updateTask(projectId, taskId, { due_date: val || null })
}
const quickUpdatePriority = async (val) => {
  await updateTask(projectId, taskId, { priority: val })
  ElMessage.success('优先级已更新')
}
const quickUpdateTags = async (ids) => {
  if (!task.value) return
  await updateTask(projectId, taskId, { tag_ids: ids })
  // 同步更新本地 task.tags，让标签显示及时刷新
  task.value.tags = tags.value.filter(t => ids.includes(t.id))
}

const onOpenCommDialog = () => {
  // 设置默认沟通类型
  if (!editComm.value) {
    const defaultType = commTypes.value.find((ct) => ct.is_default) || commTypes.value[0]
    if (defaultType) {
      commForm.value.comm_type = defaultType.name
    }
    // 固定当前状态为变更前状态（不会随后续任务状态变化）
    commForm.value.old_status_id = task.value?.status_id || null
    // 默认当前时间
    commForm.value.comm_at = dayjs().format('YYYY-MM-DDTHH:mm:ss')
    // 新增时默认使用上次沟通的所有对接人
    if (task.value?.communications?.length) {
      const last = task.value.communications[task.value.communications.length - 1]
      const lastIds = (last?.contacts || []).map(cn => cn.id)
      if (lastIds.length) {
        commForm.value.contact_ids = lastIds
      }
    }
  }
}

const triggerUpload = (comm) => {
  uploadTargetComm.value = comm
  hiddenFileInput.value?.click()
}

const triggerEditUpload = () => {
  if (editComm.value) {
    uploadTargetComm.value = editComm.value
    hiddenFileInput.value?.click()
  }
}

// 新增沟通时选择文件：存入 pastedFiles，提交时统一上传
const triggerAddUpload = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = () => {
    if (input.files) {
      for (const f of input.files) {
        pastedFiles.value.push(f)
      }
    }
    input.remove()
  }
  input.click()
}

// 重命名待上传文件（File 对象只读，需创建新对象替换）
const renamePastedFile = async (index) => {
  const f = pastedFiles.value[index]
  if (!f) return
  // 提取扩展名
  const dotIdx = f.name.lastIndexOf('.')
  const ext = dotIdx > 0 ? f.name.slice(dotIdx) : ''
  const { value: newName } = await ElMessageBox.prompt('输入新文件名' + (ext ? `（将保留扩展名 ${ext}）` : ''), '重命名文件', {
    inputValue: dotIdx > 0 ? f.name.slice(0, dotIdx) : f.name,
    inputPattern: /\S/,
    inputErrorMessage: '文件名不能为空'
  }).catch(() => ({ value: null }))
  if (!newName) return
  const finalName = ext && !newName.endsWith(ext) ? newName + ext : newName
  if (finalName === f.name) return
  // 创建新的 File 对象替换
  pastedFiles.value[index] = new File([f], finalName, { type: f.type })
}

const onFileInputChange = async (e) => {
  const file = e.target.files?.[0]
  if (!file || !uploadTargetComm.value) return
  uploadTargetComm.value.uploading = true
  try {
    const res = await uploadCommAttachment(projectId, taskId, uploadTargetComm.value.id, file)
    uploadTargetComm.value.attachments.push(res)
    ElMessage.success('上传成功')
  } catch (err) {
    ElMessage.error('上传失败')
  } finally {
    uploadTargetComm.value.uploading = false
    uploadTargetComm.value = null
    e.target.value = '' // 重置 input，允许重复选择同一文件
  }
}

// 捕获阶段粘贴处理：沟通对话框打开时，文件/图片粘贴直接上传
const onContentPaste = (e) => {
  // 只处理沟通对话框打开时的粘贴
  if (!showAddComm.value) return
  const items = e.clipboardData?.items
  if (!items) return
  // 检测剪贴板中是否有文件类型内容（非纯文字）
  let hasFile = false
  for (const item of items) {
    if (item.kind === 'file') {
      hasFile = true
      break
    }
  }
  if (!hasFile) return  // 纯文字粘贴，不做拦截
  e.stopPropagation()
  e.preventDefault()
  // 处理第一个文件
  for (const item of items) {
    if (item.kind !== 'file') continue
    const file = item.getAsFile()
    if (!file) break
    if (editComm.value) {
      // 编辑模式：直接上传
      editComm.value.uploading = true
      ;(async () => {
        try {
          const res = await uploadCommAttachment(projectId, taskId, editComm.value.id, file)
          editComm.value.attachments.push(res)
          ElMessage.success(`"${file.name}" 已上传`)
        } catch {
          ElMessage.error('粘贴上传失败')
        } finally {
          editComm.value.uploading = false
        }
      })()
    } else {
      // 新增模式：添加到待上传列表
      pastedFiles.value.push(file)
    }
    break
  }
}

const openEditTask = () => {
  taskForm.value = {
    title: task.value.title,
    description: task.value.description,
    priority: task.value.priority,
    tag_ids: (task.value.tags || []).map(t => t.id)
  }
  showEditTask.value = true
}
const submitEditTask = async () => {
  await updateTask(projectId, taskId, taskForm.value)
  ElMessage.success('已更新')
  showEditTask.value = false
  await load()
}

// ---- 标签选择弹窗 ----
const resetTagPicker = () => {
  // 关闭时丢弃未保存的选择
}
const selectTag = (id) => {
  if (!pickerSelected.value.includes(id)) {
    pickerSelected.value.push(id)
  }
}
const unselectTag = (id) => {
  pickerSelected.value = pickerSelected.value.filter(v => v !== id)
}
const submitTagPicker = async () => {
  await updateTask(projectId, taskId, { tag_ids: pickerSelected.value })
  selectedTagIds.value = [...pickerSelected.value]
  task.value.tags = tags.value.filter(t => pickerSelected.value.includes(t.id))
  showTagPicker.value = false
}

const removeTask = async () => {
  await ElMessageBox.confirm(`确定删除任务「${task.value.title}」及其所有沟通记录和附件？`, '警告', { type: 'warning' })
  await deleteTask(projectId, taskId)
  ElMessage.success('已删除')
  router.push(`/projects/${projectId}`)
}

const resetCommForm = () => {
  commForm.value = { content: '', contact_ids: [], comm_type: '', comm_at: null, files: [], old_status_id: null, new_status_id: null }
  pastedFiles.value = []
  editComm.value = null
}
const openEditComm = (c) => {
  editComm.value = c
  commForm.value = {
    content: c.content,
    contact_ids: (c.contacts || []).map(cn => cn.id),
    comm_type: c.comm_type,
    comm_at: c.comm_at,
    files: [],
    old_status_id: c.old_status_id ?? null,
    new_status_id: c.new_status_id ?? null
  }
  showAddComm.value = true
}
const submitComm = async () => {
  if (!commForm.value.content.trim()) { ElMessage.warning('内容不能为空'); return }
  commLoading.value = true
  try {
    if (editComm.value) {
      await updateCommunication(projectId, taskId, editComm.value.id, {
        content: commForm.value.content,
        contact_ids: commForm.value.contact_ids,
        comm_type: commForm.value.comm_type,
        comm_at: commForm.value.comm_at,
        old_status_id: commForm.value.old_status_id,
        new_status_id: commForm.value.new_status_id
      })
    } else {
      const comm = await addCommunication(projectId, taskId, {
        content: commForm.value.content,
        contact_ids: commForm.value.contact_ids,
        comm_type: commForm.value.comm_type,
        comm_at: commForm.value.comm_at,
        old_status_id: commForm.value.old_status_id,
        new_status_id: commForm.value.new_status_id
      })
      // 上传附件到刚创建的沟通记录
      for (const f of pastedFiles.value) {
        try {
          const res = await uploadCommAttachment(projectId, taskId, comm.id, f)
          comm.attachments.push(res)
        } catch (e) {
          console.error('附件上传失败', e)
        }
      }
    }
    showAddComm.value = false
    await load()
  } finally { commLoading.value = false }
}
const removeComm = async (c) => {
  await ElMessageBox.confirm('确定删除这条沟通记录及其所有附件？', '提示', { type: 'warning' })
  await deleteCommunication(projectId, taskId, c.id)
  await load()
}

const editContact = (c) => {
  editContactRef.value = c
  contactForm.value = { name: c.name, role: c.role, contact_info: c.contact_info }
  showAddContact.value = true
}
const resetContactForm = () => {
  contactForm.value = { name: '', role: '', contact_info: '' }
  editContactRef.value = null
}
const submitContact = async () => {
  if (!contactForm.value.name.trim()) { ElMessage.warning('姓名不能为空'); return }
  contactLoading.value = true
  try {
    if (editContactRef.value) {
      await updateContact(projectId, taskId, editContactRef.value.id, contactForm.value)
    } else {
      await addContact(projectId, taskId, contactForm.value)
    }
    showAddContact.value = false
    await load()
  } finally {
    contactLoading.value = false
    resetContactForm()
  }
}
const removeContact = async (c) => {
  await deleteContact(projectId, taskId, c.id)
  await load()
}

const renameAtt = async (a) => {
  // 提取原文件扩展名
  const dotIdx = a.original_filename.lastIndexOf('.')
  const ext = dotIdx > 0 ? a.original_filename.slice(dotIdx) : ''

  const { value: newName } = await ElMessageBox.prompt('输入新文件名' + (ext ? `（将保留扩展名 ${ext}）` : ''), '重命名附件', {
    inputValue: dotIdx > 0 ? a.original_filename.slice(0, dotIdx) : a.original_filename,
    inputPattern: /\S/,
    inputErrorMessage: '文件名不能为空'
  }).catch(() => ({ value: null }))
  if (!newName) return

  // 自动补全扩展名
  const finalName = ext && !newName.endsWith(ext) ? newName + ext : newName
  if (finalName === a.original_filename) return

  try {
    const res = await renameAttachment(a.id, finalName)
    a.original_filename = res.original_filename
    // 同步更新 timeline 中的附件对象
    if (task.value?.communications) {
      for (const c of task.value.communications) {
        const att = c.attachments?.find((at) => at.id === a.id)
        if (att) att.original_filename = res.original_filename
      }
    }
    ElMessage.success('重命名成功')
  } catch {
    ElMessage.error('重命名失败')
  }
}
const removeAtt = async (a) => {
  await ElMessageBox.confirm('确定删除附件？', '提示', { type: 'warning' })
  await deleteAttachment(a.id)
  // 从对话框编辑对象中立即移除（防止界面仍显示已删附件）
  if (editComm.value) {
    const idx = editComm.value.attachments.findIndex((att) => att.id === a.id)
    if (idx !== -1) editComm.value.attachments.splice(idx, 1)
  }
  await load()
}
</script>

<style scoped>
.page-body { display: flex; gap: 24px; align-items: flex-start; max-height: calc(100vh - 60px); }
.body-main { flex: 1; min-width: 0; display: flex; flex-direction: column; min-height: 0; }
.detail-side { width: 260px; flex-shrink: 0; display: flex; flex-direction: column; gap: 12px; }
.title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.title-left { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.title-left .title-edit-btn { flex-shrink: 0; color: #999; }
.title-left .title-edit-btn:hover { color: #409eff; }
.title-left .back-btn { flex-shrink: 0; }
.title-left .back-btn:hover { color: #534ab7; border-color: #d0cff0; background: #f5f4ff; }
.page-title { font-size: 22px; font-weight: 600; color: #222; margin: 0; }
.task-desc { color: #555; font-size: 14px; line-height: 1.6; white-space: pre-wrap; margin-bottom: 20px; }
.task-desc-empty { color: #bbb; }
.section-title { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; margin-bottom: 12px; margin-top: 20px; color: #444; }
.preview-toolbar { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 10px; }
.preview-toolbar .tb-sep { display: inline-block; width: 1px; height: 18px; background: #e0e0e0; flex-shrink: 0; }
.timeline-scroll { flex: 1; min-height: 0; overflow-y: auto; }
.timeline-scroll::-webkit-scrollbar { width: 6px; }
.timeline-scroll::-webkit-scrollbar-track { background: transparent; }
.timeline-scroll::-webkit-scrollbar-thumb { background: #d0d0d0; border-radius: 3px; transition: background 0.2s; }
.timeline-scroll::-webkit-scrollbar-thumb:hover { background: #b0b0b0; }
.comm-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 16px; }
.comm-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.comm-type-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.comm-user { font-size: 13px; color: #888; }
.comm-status { font-size: 12px; color: #666; display: inline-flex; align-items: center; gap: 3px; margin-left: 8px; }
.comm-arrow { color: #bbb; font-size: 12px; margin: 0 2px; }
.status-dot-mini { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.comm-content { font-size: 14px; line-height: 1.6; color: #333; white-space: pre-wrap; }
.att-list { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
.att-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #555; background: #f7f7f5; border-radius: 4px; padding: 4px 8px; }
.att-name { color: #185fa5; text-decoration: none; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer; }
.att-name:hover { text-decoration: underline; }
.preview-img-wrap { overflow: auto; height: 70vh; background: #f5f5f5; border-radius: 4px; position: relative; user-select: none; }
.preview-img-container { min-height: 100%; text-align: center; padding: 16px; }
.preview-img { max-width: 100%; max-height: calc(70vh - 80px); display: inline-block; vertical-align: top; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.preview-other-wrap { overflow: auto; height: 70vh; background: #f5f5f5; border-radius: 4px; }
.preview-header { display: flex; align-items: center; gap: 10px; }
.preview-title { font-size: 15px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-counter { font-size: 12px; color: #999; flex-shrink: 0; }
.att-download-btn { display: inline-flex; align-items: center; color: #888; text-decoration: none; padding: 2px; border-radius: 3px; }
.att-download-btn:hover { color: #185fa5; background: #e8e8e4; }
.att-size { color: #aaa; flex-shrink: 0; }
.dialog-att-list { display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px; }
.dialog-att-item { display: flex; align-items: center; gap: 8px; font-size: 13px; padding: 6px 8px; background: #f7f7f5; border-radius: 6px; }
.dialog-att-name { color: #185fa5; text-decoration: none; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.side-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 16px; }
.side-card-fields { padding: 8px 14px; }
.side-field { display: flex; align-items: center; gap: 8px; padding: 7px 0; }
.side-field + .side-field { border-top: 1px solid #f0f0ee; }
.side-field-label { font-size: 13px; color: #555; width: 60px; flex-shrink: 0; }
.side-field-tags { align-items: flex-start; padding-top: 10px; padding-bottom: 10px; }
.side-tag-inline { display: flex; align-items: center; flex-wrap: wrap; gap: 3px; flex: 1; min-width: 0; }
.side-tag-chips { display: flex; flex-wrap: wrap; gap: 3px; }
.tag-chip-detail { font-size: 11px; padding: 1px 7px; border-radius: 10px; border: 1px solid; line-height: 1.5; }
.side-title { font-size: 13px; font-weight: 500; color: #555; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between; }

/* 标签选择弹窗 */
.tag-picker-body { max-height: 460px; }
.tag-picker-section { margin-bottom: 4px; }
.tag-picker-section-title { font-size: 13px; font-weight: 500; color: #888; margin-bottom: 8px; }
.tag-picker-capsules { display: flex; flex-wrap: wrap; gap: 8px; max-height: 200px; overflow-y: auto; padding: 2px 0; }
.tag-capsule { display: inline-flex; align-items: center; gap: 3px; padding: 4px 10px; border-radius: 20px; border: 1px solid; font-size: 12px; cursor: pointer; transition: all .15s; user-select: none; }
.tag-capsule:hover { opacity: .8; }
.tag-capsule-selected { color: #fff; }
.tag-capsule-selected:hover { opacity: .85; }
.tag-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.tag-picker-empty { font-size: 12px; color: #bbb; padding: 8px 0; text-align: center; }
.tag-picker-divider { height: 1px; background: #eee; margin: 12px 0; }
.contact-item { display: flex; align-items: flex-start; gap: 10px; padding: 8px 0; border-top: 1px solid #f0f0ee; }
.contact-avatar { width: 32px; height: 32px; border-radius: 50%; background: #eeedfe; color: #534ab7; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 13px; flex-shrink: 0; }
.contact-info { flex: 1; min-width: 0; }
.contact-name { font-size: 13px; font-weight: 500; }
.contact-role { font-size: 12px; color: #888; }
.contact-detail { font-size: 12px; color: #aaa; }
</style>
