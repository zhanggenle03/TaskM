<template>
  <div>
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item :to="{ path: `/projects/${projectId}` }">{{ project?.name || `项目 #${projectId}` }}</el-breadcrumb-item>
      <el-breadcrumb-item :to="{ path: `/projects/${projectId}` }">任务列表</el-breadcrumb-item>
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
            <el-button size="small" @click="showExportDialog = true">
              <el-icon><Document /></el-icon> 导出说明文档
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
          <div class="timeline-actions" v-if="task?.communications?.length">
            <el-input v-model="commSearch" placeholder="搜索内容 / 对接人 / 类型" size="small" clearable style="width:200px" />
            <el-select v-model="commTypeFilter" placeholder="全部类型" size="small" clearable style="width:130px">
              <el-option v-for="ct in commTypes.filter(ct => ct.is_active || ct.name === commTypeFilter)" :key="ct.name" :label="ct.name" :value="ct.name" />
            </el-select>
            <span class="timeline-count">共 {{ filteredComms.length }} 条</span>
          </div>
        </div>

        <!-- 时间线选择工具栏 -->
        <div v-if="showTimelineCheckboxes" class="timeline-select-bar">
          <el-icon><Select /></el-icon>
          <template v-if="timelineSelectedCommIds.size">
            已选中 <b>{{ timelineSelectedCommIds.size }}</b> 条记录
          </template>
          <template v-else>
            请在下方勾选需要导出的沟通记录，完成勾选后点击导出说明文档继续导出操作
          </template>
          <el-button size="small" text style="margin-left:auto" @click="clearTimelineSelection">清除选择</el-button>
        </div>

        <div class="timeline-scroll">
          <el-timeline v-if="displayComms.length">
            <el-timeline-item
              v-for="c in displayComms"
              :key="c.id"
              :timestamp="formatTime(c.comm_at)"
              placement="top"
            >
              <div class="comm-card" :class="{ 'comm-card-selected': timelineSelectedCommIds.has(c.id) }">
                <div class="comm-header">
                  <el-checkbox
                    v-if="showTimelineCheckboxes"
                    :model-value="timelineSelectedCommIds.has(c.id)"
                    @change="(val) => onTimelineCommSelect(c.id, val)"
                    style="margin-right:6px;line-height:1"
                  />
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
                <div v-if="c.subject" class="comm-subject">{{ c.subject }}</div>
                <!-- #1 自动状态变更文本与状态行重复则隐藏；#4 富文本内容经 sanitize 后渲染并加标题多级编号 -->
                <RichContent
                  v-if="c.content && !isAutoStatusContent(c)"
                  :html="renderCommContent(c)"
                  @click="onCommContentClick"
                />
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
              <div v-if="hasMoreComms" class="timeline-more">
                <el-button size="small" text @click="commVisibleCount += COMM_PAGE_SIZE">
                  加载更多（剩 {{ filteredComms.length - commVisibleCount }} 条）
                </el-button>
              </div>
            </el-timeline>
            <el-empty v-else :description="task?.communications?.length ? '无匹配的沟通记录' : '暂无沟通记录'" :image-size="60" />
          </div>
      </div>

      <!-- 右侧信息栏 -->
      <div class="detail-side">
        <div class="side-card side-card-fields">
          <div class="side-field">
            <span class="side-field-label">任务状态</span>
            <el-select v-model="task.status_id" placeholder="设置状态" size="small" style="flex:1" @change="quickUpdateStatus">
              <el-option v-for="s in statuses.filter(s => s.is_active || s.id === task.status_id)" :key="s.id" :label="s.name" :value="s.id">
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

        <!-- 关联项：关联需求 -->
        <div class="side-card side-card-compact">
          <div class="side-title">
            关联项
            <span style="flex:1"></span>
            <el-button size="small" text @click="showReqPicker = true"><el-icon><Plus /></el-icon></el-button>
          </div>
          <div v-if="task.linked_requirements?.length">
            <div v-for="req in task.linked_requirements" :key="req.id" class="contact-item" style="gap:0">
              <div class="contact-info" style="flex:1;min-width:0">
                <div class="contact-name" :title="req.title" @click="goRequirement(req)" style="cursor:pointer;color:#534ab7">{{ req.title }}</div>
                <div class="contact-role" style="display:flex;align-items:center;gap:4px;overflow:hidden;white-space:nowrap" :title="`${reqPriorityLabel(req.priority)} · ${reqStatusLabel(req.status)}`">
                  <span class="req-tag" :style="{ background: reqPrioBg(req.priority), color: reqPrioText(req.priority) }">{{ reqPriorityLabel(req.priority) }}</span>
                  <span class="req-tag" :style="{ background: reqStatBg(req.status), color: reqStatText(req.status) }">{{ reqStatusLabel(req.status) }}</span>
                </div>
              </div>
              <el-button size="small" text type="danger" @click="unlinkReq(req)" style="padding:2px;flex-shrink:0">
                <el-icon><Close /></el-icon>
              </el-button>
            </div>
          </div>
          <div v-else class="side-empty">暂无关联需求</div>
        </div>

        <div class="side-card side-card-compact">
          <div class="side-title">
            对接人
            <span style="flex:1"></span>
            <el-button size="small" text @click="showAddContact = true; resetContactForm()"><el-icon><Plus /></el-icon></el-button>
          </div>
          <div v-if="task.contacts?.length">
            <div v-for="c in task.contacts" :key="c.id" class="contact-item">
              <div class="contact-avatar contact-avatar-sm">{{ c.name[0] }}</div>
              <div class="contact-info">
                <div class="contact-name">{{ c.name }}</div>
                <div class="contact-role">{{ c.role }}</div>
              </div>
              <el-button size="small" text @click="editContact(c)"><el-icon><Edit /></el-icon></el-button>
              <el-button size="small" text type="danger" @click="removeContact(c)"><el-icon><Close /></el-icon></el-button>
            </div>
          </div>
          <div v-else class="side-empty">暂无对接人</div>
        </div>
      </div>
    </div>

    <!-- 添加/编辑沟通记录：左为放大的富文本编辑器，右为其它设置 -->
    <el-dialog v-model="showAddComm" :title="editComm ? '编辑沟通记录' : '添加沟通记录'" width="1140px" top="4vh" class="comm-edit-dialog" destroy-on-close @open="onOpenCommDialog" @opened="commEditorReady = true" @close="onCloseCommDialog">
      <el-form :model="commForm" label-position="top" @paste.capture="onContentPaste">
        <div class="comm-edit-layout">
          <!-- 左：富文本编辑器（直接放大放置，无需再弹窗） -->
          <div class="comm-edit-left">
            <div class="comm-edit-label">沟通内容 <span class="req">*</span></div>
            <CommRichEditor
              v-if="commEditorReady"
              ref="commEditorRef"
              :initial-html="commForm.content"
              :project-id="projectId"
              :task-id="taskId"
              :comm-id="editComm?.id ?? null"
              @change="onCommEditorChange"
            />
            <div class="comm-edit-hint">支持加粗、列表、图片（内联，不进入附件列表）、链接、引用、分隔线等格式；Ctrl+V 可直接粘贴文件作为附件（图片将自动嵌入正文）</div>
          </div>
          <!-- 右：其它设置，一列排下 -->
          <div class="comm-edit-right">
            <el-form-item label="主题">
              <el-input v-model="commForm.subject" placeholder="选填，导出时作为沟通记录标题" clearable style="width:100%" maxlength="100" show-word-limit />
            </el-form-item>
            <el-form-item label="对接人">
              <el-select v-model="commForm.contact_ids" placeholder="选择对接人" multiple clearable style="width:100%">
                <el-option v-for="c in task?.contacts || []" :key="c.id" :value="c.id" :label="c.name">
                  <span>{{ c.name }}</span>
                  <span style="color:#999;margin-left:6px;font-size:12px">{{ c.role }}</span>
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="沟通类型">
              <el-select v-model="commForm.comm_type" style="width:100%">
                <el-option v-for="ct in commTypes.filter(ct => ct.is_active || ct.name === commForm.comm_type)" :key="ct.name" :value="ct.name" :label="ct.name">
                  <span :style="{ color: ct.color, marginRight: '4px' }">●</span>{{ ct.name }}
                </el-option>
              </el-select>
            </el-form-item>
            <el-form-item label="时间">
              <el-date-picker v-model="commForm.comm_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="默认当前时间" style="width:100%" />
            </el-form-item>
            <el-form-item label="状态变更">
              <div style="display:flex;align-items:center;gap:8px;width:100%">
                <el-select v-model="commForm.old_status_id" placeholder="当前" style="flex:1;min-width:0">
                  <el-option v-for="s in statuses.filter(s => s.is_active || s.id === commForm.old_status_id)" :key="s.id" :label="s.name" :value="s.id">
                    <span :style="{ color: s.color, marginRight: '6px' }">●</span>{{ s.name }}
                  </el-option>
                </el-select>
                <el-icon><ArrowRight /></el-icon>
                <el-select v-model="commForm.new_status_id" placeholder="不变更" clearable style="flex:1;min-width:0">
                  <el-option v-for="s in statuses.filter(s => s.is_active || s.id === commForm.new_status_id)" :key="s.id" :label="s.name" :value="s.id" :disabled="s.id === commForm.old_status_id">
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
                    <span style="font-size:12px;color:#999">或 Ctrl+V 粘贴</span>
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
                    <span style="font-size:12px;color:#999">或 Ctrl+V 粘贴</span>
                  </div>
                </div>
              </template>
            </el-form-item>
          </div>
        </div>
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
              v-for="pc in projectContacts.filter(pc => (pc.is_active || pc.name === contactForm.name) && !task?.contacts?.find(c => c.name === pc.name))"
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

    <!-- 关联需求选择弹窗 -->
    <el-dialog v-model="showReqPicker" title="关联需求" width="480px" @open="loadRequirements">
      <div v-loading="reqPickerLoading">
        <el-input v-model="reqSearch" placeholder="搜索需求..." clearable size="small" style="margin-bottom:10px" />
        <div v-if="filteredRequirements.length" class="req-picker-list">
          <div
            v-for="req in filteredRequirements"
            :key="req.id"
            class="req-picker-item"
            :class="{ 'req-picker-item-disabled': task.linked_requirements?.find(r => r.id === req.id) }"
            @click="pickReq(req)"
          >
            <div class="req-picker-info">
              <div class="req-picker-title">{{ req.title }}</div>
              <div class="req-picker-meta">
                <span class="req-picker-badge" :style="{ background: reqPriorityColor(req.priority) }">{{ reqPriorityLabel(req.priority) }}</span>
                <span class="req-picker-badge" :style="{ background: reqStatusColor(req.status) }">{{ reqStatusLabel(req.status) }}</span>
                <span v-if="req.display_id" style="color:#999;font-size:11px">{{ req.display_id }}</span>
              </div>
            </div>
            <el-icon v-if="task.linked_requirements?.find(r => r.id === req.id)" style="color:#67c23a"><CircleCheckFilled /></el-icon>
          </div>
        </div>
        <el-empty v-else description="无可关联的需求" :image-size="40" />
      </div>
    </el-dialog>



    <!-- 编辑任务 -->
    <el-dialog v-model="showEditTask" title="编辑任务" width="480px">
      <el-form :model="taskForm" label-width="80px">
        <el-form-item label="标题"><el-input v-model="taskForm.title" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="taskForm.description" type="textarea" :rows="3" /></el-form-item>
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

    <!-- 导出说明文档弹窗 -->
    <el-dialog v-model="showExportDialog" title="导出说明文档" width="560px" @open="initExportDialog" @close="resetExportDialog">
      <el-form label-width="100px">
        <el-form-item label="时间范围" :disabled="showTimelineCheckboxes && timelineSelectedCommIds.size > 0">
          <div style="width:100%">
            <el-radio-group v-model="exportTimeRange" style="margin-bottom:10px" :disabled="showTimelineCheckboxes && timelineSelectedCommIds.size > 0">
              <el-radio value="all">全部记录</el-radio>
              <el-radio value="today">仅今日</el-radio>
              <el-radio value="custom">自定义范围</el-radio>
            </el-radio-group>
            <el-date-picker
              v-if="exportTimeRange === 'custom'"
              v-model="exportDateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              value-format="YYYY-MM-DD"
              style="width:100%"
              :disabled-date="exportDisabledDate"
              :disabled="showTimelineCheckboxes && timelineSelectedCommIds.size > 0"
            />
          </div>
        </el-form-item>
        <el-form-item label="沟通记录">
          <div style="width:100%;font-size:13px;color:#666">
            <template v-if="showTimelineCheckboxes && timelineSelectedCommIds.size">
              已从时间线选中 <b style="color:#534ab7">{{ timelineSelectedCommIds.size }}</b> 条记录
              <el-button size="small" text style="margin-left:8px" @click="clearTimelineSelection">取消选择</el-button>
            </template>
            <template v-else-if="showTimelineCheckboxes">
              请在时间线上勾选要导出的记录
            </template>
            <template v-else>
              <el-button size="small" @click="startCommSelection">选择沟通记录</el-button>
              <span style="margin-left:8px">选择指定沟通记录导出</span>
            </template>
          </div>
        </el-form-item>
        <el-form-item label="任务属性">
          <div style="width:100%">
            <div style="margin-bottom:6px">
              <el-checkbox
                :indeterminate="exportFieldsIndeterminate"
                v-model="exportFieldsAll"
                @change="handleExportFieldsAllChange"
              >全选</el-checkbox>
            </div>
            <el-checkbox-group v-model="exportFields" @change="handleExportFieldsChange">
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
                <el-checkbox v-for="opt in exportFieldOptions" :key="opt.key" :value="opt.key">
                  {{ opt.label }}
                </el-checkbox>
              </div>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item label="沟通记录">
          <el-checkbox v-model="exportCommMinimal">极简模式</el-checkbox>
          <el-checkbox v-model="exportAttachments">导出附件</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showExportDialog = false">取消</el-button>
        <el-button type="primary" :loading="exportLoading" @click="submitExport">
          <el-icon><Download /></el-icon> 导出
        </el-button>
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
  getProjectContacts, getTags, exportTaskDoc,
  linkRequirement, unlinkRequirement, getRequirements,
  getReqStatusPools, getReqPriorityPools,
  uploadCommImage
} from '../api'
import CommRichEditor from '../components/CommRichEditor.vue'
import RichContent from '../components/RichContent.vue'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId
const taskId = route.params.taskId
const task = ref(null)
const project = ref(null)
const statuses = ref([])
const commTypes = ref([])
// 时间线复选状态（用于导出）
const timelineSelectedCommIds = ref(new Set())
const showTimelineCheckboxes = ref(false)
const projectContacts = ref([])  // 项目对接人库（用于选择）
const tags = ref([])  // 项目标签池
const selectedTagIds = ref([])  // 当前任务的标签 ID 列表
const showTagPicker = ref(false)
const pickerSelected = ref([])  // 弹窗内临时选择的标签 ID
const availableTags = computed(() => tags.value.filter(t => t.is_active && !pickerSelected.value.includes(t.id)))

// 关联需求
const showReqPicker = ref(false)
const projectRequirements = ref([])
const reqPickerLoading = ref(false)
const reqSearch = ref('')
const reqStatusPools = ref([])   // 需求状态池
const reqPriorityPools = ref([]) // 需求优先级池
const filteredRequirements = computed(() => {
  const q = reqSearch.value.trim().toLowerCase()
  if (!q) return projectRequirements.value
  return projectRequirements.value.filter(r => r.title.toLowerCase().includes(q) || (r.display_id && r.display_id.toLowerCase().includes(q)))
})
const reqPriorityLabel = (p) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[p] || p)
const reqPriorityColor = (p) => ({ low: '#909399', normal: '#409eff', high: '#e6a23c', urgent: '#f56c6c' }[p] || '#909399')
const reqStatusLabel = (s) => ({ todo: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' }[s] || s)
const reqStatusColor = (s) => ({ todo: '#909399', in_progress: '#409eff', done: '#67c23a', cancelled: '#f56c6c' }[s] || '#909399')
// 从池中取颜色（支持英文key / 中文名 / 中文标签多种匹配），fallback 到 reqPriorityColor / reqStatusColor
const resolveReqPrioColor = (p) => {
  if (!p) return null
  // 1. 直接按英文 key 匹配池中的 name（若池中 name 存的是英文）
  let pool = reqPriorityPools.value.find(x => x.name === p)
  if (pool && pool.color) return pool.color
  // 2. 将英文 key 转成中文标签，按包含关系匹配池中的中文名
  const label = reqPriorityLabel(p)   // "high" -> "高"
  pool = reqPriorityPools.value.find(x => label && x.name && x.name.includes(label))
  if (pool && pool.color) return pool.color
  // 3. fallback：使用 reqPriorityColor 的硬编码映射
  return reqPriorityColor(p)
}
const resolveReqStatColor = (s) => {
  if (!s) return null
  let pool = reqStatusPools.value.find(x => x.name === s)
  if (pool && pool.color) return pool.color
  const label = reqStatusLabel(s)     // "done" -> "已完成"
  pool = reqStatusPools.value.find(x => label && x.name && x.name.includes(label))
  if (pool && pool.color) return pool.color
  return reqStatusColor(s)
}
const reqPrioBg = (p) => (resolveReqPrioColor(p) || '#909399') + '1A'
const reqPrioText = (p) => resolveReqPrioColor(p) || '#909399'
const reqStatBg = (s) => (resolveReqStatColor(s) || '#909399') + '1A'
const reqStatText = (s) => resolveReqStatColor(s) || '#909399'

const loadRequirements = async () => {
  reqPickerLoading.value = true
  try {
    const res = await getRequirements(projectId, { page: 1, page_size: 9999 })
    projectRequirements.value = res.items || []
  } catch (e) {
    console.error('加载需求列表失败', e)
    projectRequirements.value = []
  } finally {
    reqPickerLoading.value = false
  }
}

const unlinkReq = async (req) => {
  try {
    await unlinkRequirement(projectId, taskId, req.id)
    ElMessage.success('已取消关联')
    await load()
  } catch (e) {
    ElMessage.error('取消关联失败')
  }
}

const linkReq = async (req) => {
  try {
    await linkRequirement(projectId, taskId, req.id)
    ElMessage.success('已关联需求')
    showReqPicker.value = false
    await load()
  } catch (e) {
    ElMessage.error('关联失败')
  }
}

const pickReq = (req) => {
  if (task.value?.linked_requirements?.find(r => r.id === req.id)) return
  linkReq(req)
}

const goRequirement = (req) => {
  router.push({ name: 'requirement-detail', params: { projectId, requirementId: req.id } })
}

const showAddComm = ref(false)
const commLoading = ref(false)
const editComm = ref(null)
const commForm = ref({ content: '', contact_ids: [], comm_type: '', comm_at: null, subject: '', files: [], old_status_id: null, new_status_id: null })
const pastedFiles = ref([])  // 粘贴或选择的临时文件，提交时一起上传
// 内联富文本编辑器相关
const commPendingImages = ref([])  // 新建沟通时编辑器内联图片的待上传队列（保存时回填）
// 编辑器仅在弹窗完全展开后挂载：避免在 el-dialog 过渡期间初始化导致工具栏事件绑定失效
const commEditorReady = ref(false)
const commEditorRef = ref(null)

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

// ---- 时间线搜索 / 筛选 / 分页（#5） ----
const commSearch = ref('')
const commTypeFilter = ref('')
const COMM_PAGE_SIZE = 20
const commVisibleCount = ref(COMM_PAGE_SIZE)

const filteredComms = computed(() => {
  if (!task.value?.communications) return []
  let list = [...task.value.communications]
  if (commTypeFilter.value) list = list.filter(c => c.comm_type === commTypeFilter.value)
  const q = (commSearch.value || '').trim().toLowerCase()
  if (q) {
    list = list.filter(c => {
      const content = (c.content || '').toLowerCase()
      const names = (c.contacts || []).map(cn => cn.name).join('、').toLowerCase()
      const type = (c.comm_type || '').toLowerCase()
      return content.includes(q) || names.includes(q) || type.includes(q)
    })
  }
  list.sort((a, b) => {
    const ta = new Date(a.comm_at).getTime() || 0
    const tb = new Date(b.comm_at).getTime() || 0
    return timelineAsc.value ? ta - tb : tb - ta
  })
  return list
})
const displayComms = computed(() => filteredComms.value.slice(0, commVisibleCount.value))
const hasMoreComms = computed(() => commVisibleCount.value < filteredComms.value.length)

// 筛选/排序变化时重置分页
watch([commSearch, commTypeFilter, timelineAsc], () => { commVisibleCount.value = COMM_PAGE_SIZE })

// ---- 沟通内容渲染（#1 隐藏重复状态文本；#4 富文本 sanitize 后渲染） ----
const isAutoStatusContent = (c) => {
  if (!(c.old_status_id || c.new_status_id)) return false
  const t = (c.content || '').trim()
  if (!t) return false
  return t.startsWith('状态变更：') || t.startsWith('状态变更为：') || t.startsWith('状态：')
}

const _looksLikeHtml = (s) => /<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/.test(s || '')
const escapeHtml = (s) => (s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
const sanitizeHtml = (html) => {
  const allowed = new Set(['P', 'DIV', 'SPAN', 'BR', 'B', 'STRONG', 'I', 'EM', 'U', 'UL', 'OL', 'LI', 'A', 'IMG', 'PRE', 'CODE', 'BLOCKQUOTE', 'H1', 'H2', 'H3', 'H4', 'TABLE', 'THEAD', 'TBODY', 'TR', 'TD', 'TH', 'HR', 'SUB', 'SUP', 'FONT', 'SECTION'])
  const tpl = document.createElement('template')
  tpl.innerHTML = html
  const walk = (node) => {
    Array.from(node.childNodes).forEach(n => { if (n.nodeType === 1) walk(n) })
    Array.from(node.children).forEach(child => {
      if (!allowed.has(child.tagName)) {
        const parent = child.parentNode
        while (child.firstChild) parent.insertBefore(child.firstChild, child)
        parent.removeChild(child)
      } else {
        Array.from(child.attributes).forEach(attr => {
          const n = attr.name.toLowerCase()
          if (n.startsWith('on')) child.removeAttribute(attr.name)
          else if ((n === 'href' || n === 'src') && /^\s*(javascript|vbscript|data):/i.test(attr.value)) child.removeAttribute(attr.name)
        })
        if (child.tagName === 'A') { child.setAttribute('target', '_blank'); child.setAttribute('rel', 'noopener noreferrer') }
      }
    })
  }
  walk(tpl.content)
  return tpl.innerHTML
}
const renderCommContent = (c) => {
  const txt = c.content || ''
  if (_looksLikeHtml(txt)) return sanitizeHtml(txt)
  return escapeHtml(txt)
}
// 判断富文本内容是否为"空"（去掉标签与空白后无实际文字）
const isRichEmpty = (html) => {
  if (!html) return true
  const txt = (html || '')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/gi, ' ')
    .replace(/\s+/g, '')
  return txt.length === 0
}

// 编辑器内容变化：实时同步 HTML 与待上传图片队列到表单
const onCommEditorChange = (html, pendingImages) => {
  commForm.value.content = html || ''
  commPendingImages.value = pendingImages || []
}

const imgState = ref({ x: 0, y: 0, scale: 1 })
const isDragging = ref(false)
const dragStart = { x: 0, y: 0 }
const dragImgState = { x: 0, y: 0 }

// 导出说明文档
const showExportDialog = ref(false)
const exportLoading = ref(false)
const exportTimeRange = ref('all')
const exportDateRange = ref(null)
const exportFields = ref([])
const exportCommMinimal = ref(false)
const exportAttachments = ref(true)
const exportFieldsAll = ref(false)
const exportFieldsIndeterminate = ref(false)
const exportFieldOptions = [
  { key: 'title', label: '任务名称' },
  { key: 'display_id', label: '显示ID' },
  { key: 'status', label: '状态' },
  { key: 'priority', label: '优先级' },
  { key: 'due_date', label: '截止日期' },
  { key: 'description', label: '描述' },
  { key: 'contacts', label: '对接人' },
  { key: 'tags', label: '标签' },
  { key: 'linked_requirements', label: '关联需求' },
  { key: 'created_at', label: '创建时间' },
  { key: 'updated_at', label: '更新时间' },
]
const exportMinDate = ref(null)
const exportMaxDate = ref(null)

const openPreview = (a, list) => {
  previewList.value = list || []
  previewIndex.value = previewList.value.findIndex(item => item.id === a.id)
  applyPreview(a)
  previewDialog.value = true
}

const applyPreview = (a) => {
  previewAttId.value = a.id ?? null
  previewTitle.value = a.original_filename || ''
  if (a._isComImage) {
    // 沟通正文内联图片：直接使用 src 作为预览 URL
    previewSrc.value = a.src
    previewIsImage.value = true
  } else {
    previewSrc.value = previewUrl(a.id)
    const ext = (a.original_filename?.split('.').pop() || '').toLowerCase()
    previewIsImage.value = imageExts.includes('.' + ext)
  }
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
  } else if (previewSrc.value) {
    window.open(previewSrc.value, '_blank')
  }
}

// 点击沟通正文中的图片 → 打开预览弹窗，支持同一沟通内所有图片前后翻页
const onCommContentClick = (e) => {
  let target = e.target
  if (target.tagName !== 'IMG') {
    target = target.closest('img')
  }
  if (!target || target.tagName !== 'IMG') return

  const container = target.closest('.comm-content')
  if (!container) return

  // 收集该沟通正文中的所有图片，构建预览列表
  const imgs = container.querySelectorAll('img')
  const list = Array.from(imgs).map((img, i) => ({
    src: img.getAttribute('src') || img.src,
    original_filename: `图${i + 1}`,
    _isComImage: true,
    id: null,
  }))
  if (list.length === 0) return

  const idx = list.findIndex(item => item.src === (target.getAttribute('src') || target.src))
  previewList.value = list
  previewIndex.value = idx >= 0 ? idx : 0
  applyPreview(list[previewIndex.value])
  previewDialog.value = true
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
  const [t, s, ct, allProjects, tg] = await Promise.all([getTask(projectId, taskId), getStatuses(projectId, { show_inactive: true }), getCommTypes(projectId, { show_inactive: true }), getProjects(), getTags(projectId, { show_inactive: true })])
  // 后端已从沟通记录推导出最终 status_id，直接使用
  task.value = t
  timelineSelectedCommIds.value = new Set()
  showTimelineCheckboxes.value = false
  statuses.value = s
  commTypes.value = ct
  project.value = allProjects.find((p) => p.display_id === projectId) || null
  tags.value = tg
  selectedTagIds.value = (t.tags || []).map(tag => tag.id)
  // 加载项目对接人库
  try {
    projectContacts.value = await getProjectContacts(projectId, { show_inactive: true })
  } catch (e) {
    console.error('加载项目对接人库失败', e)
  }
  // 加载需求池
  try {
    reqStatusPools.value = await getReqStatusPools(projectId, { show_inactive: true })
  } catch (e) {
    console.error('加载需求状态池失败', e)
  }
  try {
    reqPriorityPools.value = await getReqPriorityPools(projectId, { show_inactive: true })
  } catch (e) {
    console.error('加载需求优先级池失败', e)
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
  // 编辑模式：图片注入编辑器，非图片上传为附件
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = () => {
    if (input.files) {
      for (const f of input.files) {
        if (imageMimeTypes.includes(f.type)) {
          // 图片：直接上传到沟通图片路径，真实 URL 注入编辑器
          ;(async () => {
            try {
              const r = await uploadCommImage(projectId, taskId, editComm.value.id, f)
              if (r?.url) {
                commEditorRef.value?.insertImageUrl?.(r.url)
              }
            } catch {
              ElMessage.error('图片上传失败')
            }
          })()
        } else {
          // 非图片：上传为附件
          ;(async () => {
            editComm.value.uploading = true
            try {
              const res = await uploadCommAttachment(projectId, taskId, editComm.value.id, f)
              editComm.value.attachments.push(res)
              ElMessage.success('上传成功')
            } catch {
              ElMessage.error('上传失败')
            } finally {
              editComm.value.uploading = false
            }
          })()
        }
      }
    }
    input.remove()
  }
  input.click()
}

// 新增沟通时选择文件：图片注入编辑器（pending 流程），非图片存入 pastedFiles
const triggerAddUpload = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.multiple = true
  input.onchange = () => {
    if (input.files) {
      for (const f of input.files) {
        if (imageMimeTypes.includes(f.type)) {
          // 图片：注入编辑器 pending 流程，不进入附件列表
          commEditorRef.value?.injectImage?.(f)
        } else {
          // 非图片：走附件
          pastedFiles.value.push(f)
        }
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

const imageMimeTypes = ['image/png', 'image/jpeg', 'image/gif', 'image/bmp', 'image/webp', 'image/svg+xml', 'image/ico', 'image/x-icon']

// 捕获阶段粘贴处理：沟通对话框打开时，图片粘贴注入编辑器，非图片文件添加到附件列表
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
    // 图片：注入富文本编辑器（不进入附件列表）
    if (imageMimeTypes.includes(file.type)) {
      if (editComm.value) {
        // 编辑模式：直接上传，真实 URL 插入编辑器
        ;(async () => {
          try {
            const r = await uploadCommImage(projectId, taskId, editComm.value.id, file)
            if (r?.url) {
              commEditorRef.value?.insertImageUrl?.(r.url)
            }
          } catch {
            ElMessage.error('图片粘贴上传失败')
          }
        })()
      } else {
        // 新增模式：注入编辑器 pending 流程（保存时回填）
        commEditorRef.value?.injectImage?.(file)
      }
    } else {
      // 非图片文件：走附件列表
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
  commForm.value = { content: '', contact_ids: [], comm_type: '', comm_at: null, subject: '', files: [], old_status_id: null, new_status_id: null }
  pastedFiles.value = []
  editComm.value = null
  commPendingImages.value = []
}
// 关闭弹窗：先卸载编辑器（避免残留实例），再重置表单
const onCloseCommDialog = () => {
  commEditorReady.value = false
  resetCommForm()
}
const openEditComm = (c) => {
  editComm.value = c
  commForm.value = {
    content: c.content,
    contact_ids: (c.contacts || []).map(cn => cn.id),
    comm_type: c.comm_type,
    comm_at: c.comm_at,
    subject: c.subject || '',
    files: [],
    old_status_id: c.old_status_id ?? null,
    new_status_id: c.new_status_id ?? null
  }
  showAddComm.value = true
}
const submitComm = async () => {
  if (isRichEmpty(commForm.value.content)) { ElMessage.warning('内容不能为空'); return }
  // 变更前后状态相同（如改了"当前"使其与新状态一致）→ 无实际变更，自动转空并提示，
  // 避免后端整链重建将其判为伪变更后清空，造成"改了没反应"
  if (commForm.value.new_status_id != null && commForm.value.new_status_id === commForm.value.old_status_id) {
    ElMessage.info('变更前后状态相同，已按"无状态变更"保存')
    commForm.value.new_status_id = null
  }
  commLoading.value = true
  try {
    if (editComm.value) {
      await updateCommunication(projectId, taskId, editComm.value.id, {
        content: commForm.value.content,
        contact_ids: commForm.value.contact_ids,
        comm_type: commForm.value.comm_type,
        subject: commForm.value.subject,
        comm_at: commForm.value.comm_at,
        old_status_id: commForm.value.old_status_id,
        new_status_id: commForm.value.new_status_id
      })
    } else {
      const comm = await addCommunication(projectId, taskId, {
        content: commForm.value.content,
        contact_ids: commForm.value.contact_ids,
        comm_type: commForm.value.comm_type,
        subject: commForm.value.subject,
        comm_at: commForm.value.comm_at,
        old_status_id: commForm.value.old_status_id,
        new_status_id: commForm.value.new_status_id
      })
      // 回填编辑器内联图片：先建沟通拿到 ID，再上传并替换占位
      // 注：用 blobUrl 字符串匹配而非 data-pending-id（WangEditor Slate 序列化会丢弃自定义属性）
      let finalHtml = commForm.value.content
      for (const p of commPendingImages.value) {
        // 编辑期内被删除的图片（blob URL 已不在 HTML 中）不再上传，避免产生孤儿文件
        if (!finalHtml.includes(p.blobUrl)) continue
        try {
          const res = await uploadCommImage(projectId, taskId, comm.id, p.file)
          if (res?.url) {
            finalHtml = finalHtml.split(p.blobUrl).join(res.url)
          }
        } catch (e) {
          console.error('沟通图片上传失败', e)
        }
      }
      if (finalHtml !== commForm.value.content) {
        await updateCommunication(projectId, taskId, comm.id, { content: finalHtml })
      }
      commPendingImages.value = []
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

// ---- 时间线复选（用于导出） ----
const onTimelineCommSelect = (commId, val) => {
  const set = timelineSelectedCommIds.value
  if (val) {
    set.add(commId)
  } else {
    set.delete(commId)
  }
  // 触发响应式更新（Set 需要重新赋值）
  timelineSelectedCommIds.value = new Set(set)
}

const clearTimelineSelection = () => {
  timelineSelectedCommIds.value = new Set()
  showTimelineCheckboxes.value = false
}

const startCommSelection = () => {
  showTimelineCheckboxes.value = true
  showExportDialog.value = false
}

// ---- 导出说明文档 ----
const initExportDialog = () => {
  // 重置时间范围
  exportTimeRange.value = 'all'
  exportDateRange.value = null
  // 如果已从时间线勾选了记录，不使用时间范围筛选
  if (timelineSelectedCommIds.value.size > 0) {
    exportTimeRange.value = 'all'
  }
  // 如果用户清空了选择，隐藏复选框
  if (timelineSelectedCommIds.value.size === 0) {
    showTimelineCheckboxes.value = false
  }

  // 计算沟通记录的最早和最晚日期（用于自定义范围限制）
  if (task.value?.communications?.length) {
    const comms = task.value.communications
    let minDate = null
    let maxDate = null
    for (const c of comms) {
      if (c.comm_at) {
        const d = new Date(c.comm_at)
        if (!minDate || d < minDate) minDate = d
        if (!maxDate || d > maxDate) maxDate = d
      }
    }
    exportMinDate.value = minDate
    exportMaxDate.value = maxDate
  } else {
    exportMinDate.value = null
    exportMaxDate.value = null
  }

  // 默认勾选有内容的属性
  if (task.value) {
    const t = task.value
    const defaults = []
    if (t.title) defaults.push('title')
    if (t.display_id) defaults.push('display_id')
    if (t.status_id) defaults.push('status')
    if (t.priority) defaults.push('priority')
    if (t.due_date) defaults.push('due_date')
    if (t.description) defaults.push('description')
    if (t.contacts && t.contacts.length) defaults.push('contacts')
    if (t.tags && t.tags.length) defaults.push('tags')
    if (t.linked_requirements && t.linked_requirements.length) defaults.push('linked_requirements')
    if (t.created_at) defaults.push('created_at')
    if (t.updated_at) defaults.push('updated_at')
    exportFields.value = defaults
  } else {
    exportFields.value = []
  }
  handleExportFieldsChange()
  exportCommMinimal.value = false
  exportAttachments.value = true
}

const exportDisabledDate = (time) => {
  // 禁止选择超出沟通记录时间范围外的日期
  if (exportMinDate.value && time < exportMinDate.value) return true
  if (exportMaxDate.value && time > exportMaxDate.value) return true
  return false
}

const resetExportDialog = () => {
  showExportDialog.value = false
  exportLoading.value = false
  exportFieldsAll.value = false
  exportFieldsIndeterminate.value = false
}

// 全选/取消全选任务属性
const handleExportFieldsAllChange = (val) => {
  exportFields.value = val ? exportFieldOptions.map(o => o.key) : []
  exportFieldsAll.value = val
  exportFieldsIndeterminate.value = false
}
const handleExportFieldsChange = () => {
  const len = exportFields.value.length
  exportFieldsAll.value = len === exportFieldOptions.length
  exportFieldsIndeterminate.value = len > 0 && len < exportFieldOptions.length
}

const submitExport = async () => {
  exportLoading.value = true
  try {
    const params = {}
    if (exportTimeRange.value === 'today') {
      const today = new Date()
      const y = today.getFullYear()
      const m = String(today.getMonth() + 1).padStart(2, '0')
      const d = String(today.getDate()).padStart(2, '0')
      params.start_date = `${y}-${m}-${d}`
      params.end_date = `${y}-${m}-${d}`
    } else if (exportTimeRange.value === 'custom' && exportDateRange.value) {
      params.start_date = exportDateRange.value[0]
      params.end_date = exportDateRange.value[1]
    }
    // 'all' → 不传参，后端不筛选
    params.fields = exportFields.value.join(',')
    // 沟通记录复选：使用时间线上勾选的记录
    if (timelineSelectedCommIds.value.size) {
      params.comm_ids = Array.from(timelineSelectedCommIds.value).join(',')
    }
    // 极简模式
    if (exportCommMinimal.value) {
      params.comm_minimal = '1'
    }
    // 是否导出沟通记录附件（默认导出，'0' 时不导出）
    params.export_attachments = exportAttachments.value ? '1' : '0'

    const res = await exportTaskDoc(projectId, taskId, params)
    // res 是完整 response（含 headers），res.data 是 blob
    const disposition = res.headers?.['content-disposition'] || ''
    const pad = (n) => String(n).padStart(2, '0')
    const now2 = new Date()
    const ts2 = `${now2.getFullYear()}${pad(now2.getMonth()+1)}${pad(now2.getDate())}${pad(now2.getHours())}${pad(now2.getMinutes())}${pad(now2.getSeconds())}`
    let filename = task.value?.title ? `${task.value.title}_${ts2}.zip` : 'task_export.zip'
    const match = disposition.match(/filename\*=UTF-8''(.+?)(?:;|$)/)
    if (match) {
      filename = decodeURIComponent(match[1])
    }

    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)

    showExportDialog.value = false
    // #12 读取导出统计头，给出明确反馈
    const stats = res.headers?.['x-export-stats']
    let msg = '导出成功'
    if (stats) {
      const m = stats.match(/comms[:=](\d+)/)
      const at = stats.match(/atts[:=](\d+)/)
      if (m || at) {
        msg = `导出成功：共 ${m ? m[1] : 0} 条沟通记录、${at ? at[1] : 0} 个附件`
      }
    }
    ElMessage.success(msg)
  } catch (err) {
    ElMessage.error('导出失败：' + (err.response?.data?.detail || err.message))
  } finally {
    exportLoading.value = false
  }
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
.section-title { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 6px; margin-bottom: 12px; margin-top: 20px; color: #444; flex-wrap: wrap; }
.timeline-actions { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.preview-toolbar { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 10px; }
.preview-toolbar .tb-sep { display: inline-block; width: 1px; height: 18px; background: #e0e0e0; flex-shrink: 0; }
.timeline-scroll { flex: 1; min-height: 0; overflow-y: auto; }
.timeline-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.timeline-count { font-size: 12px; color: #999; white-space: nowrap; }
.timeline-more { text-align: center; padding: 6px 0 2px; }
.timeline-scroll::-webkit-scrollbar { width: 6px; }
.timeline-scroll::-webkit-scrollbar-track { background: transparent; }
.timeline-scroll::-webkit-scrollbar-thumb { background: #d0d0d0; border-radius: 3px; transition: background 0.2s; }
.timeline-scroll::-webkit-scrollbar-thumb:hover { background: #b0b0b0; }
.comm-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 16px; transition: border-color .2s; }
.comm-card-selected { border-color: #534ab7; background: #f8f7ff; }
.comm-header { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.timeline-select-bar { display: flex; align-items: center; gap: 6px; padding: 8px 14px; background: #f0f0ff; border-radius: 8px; margin-bottom: 12px; font-size: 13px; color: #534ab7; }
.comm-type-badge { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.comm-user { font-size: 13px; color: #888; }
.comm-status { font-size: 12px; color: #666; display: inline-flex; align-items: center; gap: 3px; margin-left: 8px; }
.comm-arrow { color: #bbb; font-size: 12px; margin: 0 2px; }
.status-dot-mini { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.comm-subject { font-size: 15px; font-weight: 600; color: #534ab7; margin: 2px 0 8px; padding-left: 10px; border-left: 3px solid #534ab7; line-height: 1.4; word-break: break-word; }
.comm-content { font-size: 14px; line-height: 1.6; color: #333; white-space: pre-wrap; }
.comm-content :deep(ul), .comm-content :deep(ol) { padding-left: 24px; margin: 6px 0; }
.comm-content :deep(img) { max-width: 100%; max-height: 50vh; height: auto; border-radius: 4px; cursor: zoom-in; }
.comm-content :deep(img:hover) { box-shadow: 0 0 0 2px #534ab7; }
/* 添加/编辑沟通记录：左编辑器 + 右设置两栏布局 */
.comm-edit-layout { display: flex; gap: 20px; align-items: stretch; }
.comm-edit-left { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; }
.comm-edit-label { font-size: 14px; font-weight: 500; color: #333; margin-bottom: 8px; }
.comm-edit-label .req { color: #f56c6c; }
.comm-edit-hint { font-size: 12px; color: #999; margin-top: 6px; line-height: 1.5; }
.comm-edit-right { flex: 0 0 300px; width: 300px; max-height: 520px; overflow-y: auto; padding-right: 4px; }
.comm-edit-right :deep(.el-form-item) { margin-bottom: 16px; }
.comm-edit-right :deep(.el-form-item__label) { padding-bottom: 4px; line-height: 1.2; }
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
.side-title { font-size: 13px; font-weight: 500; color: #555; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; }

/* 紧凑卡片 */
.side-card-compact { padding: 10px 14px; }

/* 空状态文字 */
.side-empty { font-size: 12px; color: #bbb; text-align: center; padding: 6px 0; }

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
.contact-item { display: flex; align-items: center; gap: 8px; padding: 6px 0; border-top: 1px solid #f0f0ee; }
.contact-item:first-child { border-top: none; }
.contact-avatar { width: 32px; height: 32px; border-radius: 50%; background: #eeedfe; color: #534ab7; display: flex; align-items: center; justify-content: center; font-weight: 500; font-size: 13px; flex-shrink: 0; }
.contact-avatar-sm { width: 26px; height: 26px; font-size: 11px; }
.contact-info { flex: 1; min-width: 0; }
.contact-name { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.contact-role { font-size: 12px; color: #888; }
.contact-detail { font-size: 12px; color: #aaa; }

/* 关联项 tag 样式 */
.req-tag { display: inline-block; font-size: 10px; padding: 1px 6px; border-radius: 4px; line-height: 16px; font-weight: 500; flex-shrink: 0; }

/* 关联需求选择弹窗 */
.req-picker-list { max-height: 400px; overflow-y: auto; }
.req-picker-item { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border: 1px solid #f0f0ee; border-radius: 6px; margin-bottom: 6px; cursor: pointer; transition: all .15s; }
.req-picker-item:hover { border-color: #c0c0be; background: #fafafa; }
.req-picker-item-disabled { opacity: .5; cursor: not-allowed; }
.req-picker-item-disabled:hover { border-color: #f0f0ee; background: transparent; }
.req-picker-info { flex: 1; min-width: 0; }
.req-picker-title { font-size: 13px; font-weight: 500; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.req-picker-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.req-picker-badge { font-size: 11px; color: #fff; padding: 1px 6px; border-radius: 3px; }
.req-priority-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; vertical-align: middle; margin-right: 2px; }
</style>
