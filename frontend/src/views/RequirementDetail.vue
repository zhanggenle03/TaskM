<template>
  <div>
    <!-- 面包屑 -->
    <el-breadcrumb separator="/" style="margin-bottom:20px">
      <el-breadcrumb-item :to="{ path: '/projects' }">项目列表</el-breadcrumb-item>
      <el-breadcrumb-item :to="{ path: `/projects/${projectId}/requirements` }">需求列表</el-breadcrumb-item>
      <el-breadcrumb-item>{{ req?.title || '需求详情' }}</el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 加载状态 -->
    <div v-if="loading" style="display:flex;justify-content:center;padding:100px 0">
      <div class="loading-spinner" />
    </div>

    <!-- 错误状态 -->
    <div v-if="!loading && !req" style="display:flex;justify-content:center;padding:80px 0">
      <el-empty description="需求加载失败或不存在">
        <el-button type="primary" @click="load(route.params.requirementId)">重新加载</el-button>
      </el-empty>
    </div>

    <!-- 内容 -->
    <div v-if="req" class="page-body">
      <!-- 左侧主内容 -->
      <div class="body-main">
        <!-- 标题行 -->
        <div class="title-row">
          <div class="title-left">
            <el-button @click="router.back()" class="back-btn">
              <el-icon><ArrowLeft /></el-icon> 返回
            </el-button>
            <h1 class="page-title">{{ req.title }}</h1>
            <el-button size="small" text @click="startEditTitle" class="title-edit-btn">
              <el-icon><Edit /></el-icon>
            </el-button>
          </div>
          <div style="display:flex;gap:6px">
            <span v-if="saveStatus" class="save-indicator" :class="'save--' + saveStatus">
              {{ saveStatus === 'saving' ? '保存中…' : saveStatus === 'saved' ? '已保存' : '保存失败' }}
            </span>
            <el-button
              size="small" @click="doExportRequirement" :loading="exportLoading"
            >
              <el-icon><Download /></el-icon> 导出文档
            </el-button>
            <el-button
              v-if="isEditing"
              size="small" type="warning" plain
              @click="exitEdit"
            >
              <el-icon><Close /></el-icon> 退出编辑
            </el-button>
            <el-button
              v-else
              size="small" type="primary" plain
              @click="enterEdit"
            >
              <el-icon><Edit /></el-icon> 编辑
            </el-button>
            <el-button size="small" type="primary" @click="doSaveDesc" :loading="saveStatus === 'saving'">
              <el-icon><Check /></el-icon> 保存描述
            </el-button>
          </div>
        </div>

        <!-- 显示ID -->
        <p v-if="req.display_id" class="req-display-id">{{ req.display_id }}</p>

        <!-- 富文本编辑器 -->
        <div class="section-title">
          <span class="st-title"><el-icon><EditPen /></el-icon> 详细描述</span>
          <el-button size="small" text type="primary" @click="tocVisible = !tocVisible">
            <el-icon><List /></el-icon> 目录
          </el-button>
        </div>
        <div class="editor-wrapper" :class="{ 'editor-readonly': !isEditing }">
          <Toolbar
            v-show="isEditing"
            :editor="editorRef"
            :defaultConfig="toolbarConfig"
            mode="simple"
            class="editor-toolbar"
          />
          <Editor
            v-model="descDraft"
            :defaultConfig="editorConfig"
            mode="default"
            class="editor-body"
            @onCreated="onEditorCreated"
            @onChange="onEditorChange"
          />
        </div>

        <!-- 目录大纲面板 -->
        <transition name="el-fade-in">
          <div v-if="tocVisible && tocItems.length" class="toc-panel">
            <div class="toc-header">
              <span>目录</span>
              <el-button text size="small" @click="tocVisible = false">收起</el-button>
            </div>
            <div class="toc-list">
              <div
                v-for="(t, i) in tocItems"
                :key="i"
                class="toc-item"
                :class="'lv' + t.level"
                @click="scrollToHeading(i)"
              ><span class="toc-label">{{ t.label }}</span>{{ t.text }}</div>
            </div>
          </div>
        </transition>
      </div>

      <!-- 右侧信息栏 -->
      <div class="detail-side">
        <div class="side-card side-card-fields">
          <!-- 状态 -->
          <div class="side-field">
            <span class="side-field-label">状态</span>
            <el-select v-model="req.status" placeholder="设置状态" size="small" style="flex:1" @change="quickUpdateStatus">
              <el-option
                v-for="s in statusPools"
                :key="s.name"
                :label="s.name"
                :value="s.name"
              >
                <span :style="{ color: s.color, marginRight: '6px' }">●</span>{{ s.name }}
              </el-option>
            </el-select>
          </div>

          <!-- 优先级 -->
          <div class="side-field">
            <span class="side-field-label">优先级</span>
            <el-select v-model="req.priority" placeholder="选择优先级" size="small" style="flex:1" @change="quickUpdatePriority">
              <el-option
                v-for="p in priorityPools"
                :key="p.name"
                :label="p.name"
                :value="p.name"
              >
                <span :style="{ color: p.color, marginRight: '6px' }">●</span>{{ p.name }}
              </el-option>
            </el-select>
          </div>

          <!-- 自定义字段 -->
          <div v-if="customFields.length" class="side-field-section">
            <div class="side-field-section-title">自定义字段</div>
            <div v-for="f in customFields" :key="f.id" class="side-field">
              <span class="side-field-label" :title="f.field_name">{{ f.field_name }}</span>
              <span class="side-field-value">
                <template v-if="f.field_type === 'link'">
                  <a v-if="getFieldValue(f.id)" :href="getFieldValue(f.id)" target="_blank" class="cf-detail-link">{{ getFieldValue(f.id) }}</a>
                </template>
                <template v-else>{{ getFieldValue(f.id) || '—' }}</template>
              </span>
            </div>
          </div>
        </div>

        <!-- 时间信息 -->
        <div class="side-card">
          <div class="side-info-row">
            <span class="side-info-label">创建时间</span>
            <span class="side-info-value">{{ formatTime(req.created_at) }}</span>
          </div>
          <div class="side-info-row">
            <span class="side-info-label">更新时间</span>
            <span class="side-info-value">{{ formatTime(req.updated_at) }}</span>
          </div>
        </div>

        <!-- 操作 -->
        <div class="side-card">
          <el-button type="danger" size="small" style="width:100%" @click="removeReq">
            <el-icon><Delete /></el-icon> 删除需求
          </el-button>
        </div>
      </div>
    </div>

    <!-- 标题编辑对话框 -->
    <el-dialog v-model="editTitleDialog" title="编辑标题" width="500px" :close-on-click-modal="false">
      <el-input v-model="editTitleVal" autofocus @keyup.enter="doSaveTitle" />
      <template #footer>
        <el-button @click="editTitleDialog = false">取消</el-button>
        <el-button type="primary" @click="doSaveTitle">保存</el-button>
      </template>
    </el-dialog>

    <!-- 退出编辑确认对话框 -->
    <el-dialog v-model="exitConfirmVisible" title="未保存的改动" width="420px" :close-on-click-modal="false" :show-close="false">
      <p style="margin:0;color:#555">当前修改未保存，是否保存？</p>
      <template #footer>
        <el-button @click="onExitChoice('continue')">继续编辑</el-button>
        <el-button @click="onExitChoice('discard')" type="danger" plain>不保存退出</el-button>
        <el-button @click="onExitChoice('save')" type="primary">保存退出</el-button>
      </template>
    </el-dialog>

    <!-- 统一预览弹窗（图片+附件） -->
    <el-dialog v-model="previewDialog" width="80%" top="5vh" destroy-on-close>
      <template #header>
        <div class="preview-header">
          <span class="preview-title">{{ previewTitle }}</span>
          <span v-if="previewList.length > 1" class="preview-counter">{{ previewIndex + 1 }} / {{ previewList.length }}</span>
        </div>
      </template>

      <!-- 图片预览 -->
      <div v-if="!previewIsFile" class="preview-img-wrap" @wheel.prevent="onImgWheel">
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

      <!-- 附件预览（iframe） -->
      <div v-else style="height:75vh;background:#f5f5f5;border-radius:4px">
        <iframe :src="previewSrc"
          style="width:100%;height:100%;border:none;border-radius:4px;background:#fff"
        />
      </div>

      <!-- 工具栏：切换 + 重置 -->
      <div v-if="previewList.length > 1 || (!previewIsFile && imgState.scale !== 1)" class="preview-toolbar">
        <template v-if="previewList.length > 1">
          <el-button size="small" :disabled="previewIndex <= 0" @click="previewPrev"><el-icon><ArrowLeft /></el-icon></el-button>
          <span class="preview-counter">{{ previewIndex + 1 }} / {{ previewList.length }}</span>
          <el-button size="small" :disabled="previewIndex >= previewList.length - 1" @click="previewNext"><el-icon><ArrowRight /></el-icon></el-button>
        </template>
        <span v-if="previewList.length > 1 && !previewIsFile && imgState.scale !== 1" class="tb-sep"></span>
        <el-button v-if="!previewIsFile && imgState.scale !== 1" size="small" text @click="resetImageZoom">重置</el-button>
      </div>

      <template #footer>
        <el-button @click="previewDialog = false">关闭</el-button>
        <el-button type="primary" @click="downloadPreview">下载</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, shallowRef, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, ArrowRight, List } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import '@wangeditor/editor/dist/css/style.css'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import { Boot, SlateEditor, SlateTransforms, SlateRange } from '@wangeditor/editor'
import {
  getRequirement, updateRequirement, deleteRequirement, deleteRequirementImage,
  getReqCustomFields, getReqStatusPools, getReqPriorityPools,
  exportRequirementDoc, uploadRequirementImage, uploadRequirementFile, deleteRequirementFile,
} from '../api/index.js'

// ── 引用块颜色选择器 ──
const BQ_PRESETS = [
  { value: '#f8f8f8', label: '灰', border: '#ccc' },
  { value: '#e8f4fd', label: '蓝', border: '#9fc5e8' },
  { value: '#e8f8e8', label: '绿', border: '#9fc89f' },
  { value: '#fef9e7', label: '黄', border: '#e6d88a' },
  { value: '#fde8e8', label: '红', border: '#e89f9f' },
]

/** 从 DOM 节点向上查找最近的 blockquote */
const findParentBlockquote = (startEl) => {
  let el = startEl
  while (el) {
    if (el.nodeName === 'BLOCKQUOTE') return el
    el = el.parentElement
  }
  return null
}

/**
 * 在编辑器内查找当前光标所在的 blockquote DOM（多路径 fallback）
 */
const findCurrentBlockquote = () => {
  try {
    const sel = window.getSelection()
    if (sel && sel.rangeCount > 0 && sel.anchorNode) {
      const bq = findParentBlockquote(sel.anchorNode)
      if (bq) return bq
    }
  } catch {}
  if (editorRef.value) {
    try {
      const container =
        editorRef.value.getEditableContainer?.() ||
        document.querySelector('.w-e-text-container [data-slate-editor]') ||
        document.querySelector('.w-e-text-container')
      if (container) {
        const allBq = container.querySelectorAll('blockquote')
        if (allBq.length === 1) return allBq[0]
        for (let i = allBq.length - 1; i >= 0; i--) {
          if (allBq[i].getAttribute('data-bq-active') === 'true') return allBq[i]
        }
      }
    } catch {}
  }
  return null
}

/** 最后一次鼠标点击落入的 blockquote DOM */
let lastTouchedBlockquote = null

// ── 引用颜色选择器菜单 ──

class BqColorMenu {
  constructor() {
    this.title = '引用颜色'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"/></svg>'
    this.tag = 'select'
    this.width = 48
  }
  getOptions() { return BQ_PRESETS.map(c => ({ value: c.value, text: c.label })) }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor, color) {
    // 定位目标 blockquote DOM 元素
    let bqEl = findCurrentBlockquote()
    if (!bqEl) bqEl = lastTouchedBlockquote
    if (!bqEl || bqEl.nodeName !== 'BLOCKQUOTE') {
      console.warn('[BqColor] 未找到目标引用块，请先将光标放入引用块内再选择颜色')
      return
    }

    const border = bqBorderColorMap[color] || color
    const text = (bqEl.textContent || '').trim()

    // 写入持久化存储（JS 变量，Slate 不干涉）
    bqColorStore[_bqKey(text)] = { color, border }

    // 同时设置 DOM 属性（CSS 属性选择器驱动即时视觉反馈）
    bqEl.setAttribute('data-bq-color', color)
    bqEl.setAttribute('data-bq-border', border)

    hasUnsaved.value = true
  }
}

// 用 try/catch 保护 registerMenu：首次注册成功，后续组件复用时不因
// "Duplicated key" 异常导致整个 setup() 崩溃（watch/ref 等全部无法初始化）
try {
  Boot.registerMenu({
    key: 'bqColorSelect',
    factory() { return new BqColorMenu() }
  })
} catch (e) {
  // 预期：第二次注册时抛 "Duplicated key" — 忽略即可，无需重新注册
  if (e.message && !e.message.includes('Duplicated key')) throw e
}

// ── 插入链接菜单（自定义对话框，与插入文件风格统一）──

class ReqLinkMenu {
  constructor() {
    this.title = '插入链接'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M574 665.4a8.03 8.03 0 0 0-11.3 0L446.5 781.6c-53.8 53.8-144.6 59.5-204 0-59.5-59.5-53.8-150.2 0-204l116.2-116.2c3.1-3.1 3.1-8.2 0-11.3l-39.8-39.8a8.03 8.03 0 0 0-11.3 0L191.4 526.5c-84.6 84.6-84.6 221.5 0 306s221.5 84.6 306 0l116.2-116.2c3.1-3.1 3.1-8.2 0-11.3L574 665.4zm258.6-474c-84.6-84.6-221.5-84.6-306 0L410.3 307.6a8.03 8.03 0 0 0 0 11.3l39.7 39.7c3.1 3.1 8.2 3.1 11.3 0l116.2-116.2c53.8-53.8 144.6-59.5 204 0 59.5 59.5 53.8 150.2 0 204L665.3 562.6a8.03 8.03 0 0 0 0 11.3l39.8 39.8c3.1 3.1 8.2 3.1 11.3 0l116.2-116.2c84.5-84.6 84.5-221.5 0-306.1z"/></svg>'
    this.tag = 'button'
  }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor, value) {
    // 复用与插入文件相同的对话框布局，包含文本和链接两个字段
    const overlay = document.createElement('div')
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:10000;display:flex;align-items:center;justify-content:center'
    const dialog = document.createElement('div')
    dialog.style.cssText = 'background:#fff;border-radius:8px;padding:24px;width:420px;box-shadow:0 4px 24px rgba(0,0,0,0.15);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
    dialog.innerHTML = `
      <div style="font-size:16px;font-weight:600;margin-bottom:20px;color:#303133">插入链接</div>
      <div style="margin-bottom:12px">
        <label style="font-size:13px;color:#606266;display:block;margin-bottom:6px">显示文本</label>
        <input id="req-link-text" type="text" placeholder="链接显示的文字" style="width:100%;padding:8px 12px;border:1px solid #dcdfe6;border-radius:4px;font-size:14px;box-sizing:border-box;outline:none" />
      </div>
      <div style="margin-bottom:4px">
        <label style="font-size:13px;color:#606266;display:block;margin-bottom:6px">链接地址</label>
        <input id="req-link-url" type="text" placeholder="https:// 或 www.example.com" style="width:100%;padding:8px 12px;border:1px solid #dcdfe6;border-radius:4px;font-size:14px;box-sizing:border-box;outline:none" />
      </div>
      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px">
        <button id="req-link-cancel" type="button" style="padding:8px 20px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;cursor:pointer;font-size:13px;color:#606266">取消</button>
        <button id="req-link-confirm" type="button" style="padding:8px 20px;border:none;border-radius:4px;background:#534ab7;cursor:pointer;font-size:13px;color:#fff;opacity:0.6" disabled>确定</button>
      </div>`
    overlay.appendChild(dialog)
    document.body.appendChild(overlay)

    const textInput = dialog.querySelector('#req-link-text')
    const urlInput = dialog.querySelector('#req-link-url')
    const btnConfirm = dialog.querySelector('#req-link-confirm')
    const btnCancel = dialog.querySelector('#req-link-cancel')

    // 与插入文件一致的交互：URL 非空时激活确定按钮
    const setBtnState = () => {
      if (urlInput.value.trim()) {
        btnConfirm.disabled = false
        btnConfirm.style.opacity = '1'
      } else {
        btnConfirm.disabled = true
        btnConfirm.style.opacity = '0.6'
      }
    }
    urlInput.addEventListener('input', setBtnState)

    const close = () => { document.body.removeChild(overlay) }
    btnCancel.onclick = close

    btnConfirm.onclick = () => {
      let url = urlInput.value.trim()
      let text = textInput.value.trim()
      if (!url) return
      // 复用 parseLinkUrl 逻辑：自动补协议
      if (!/^[\/\.#\?]/.test(url) && !/^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(url)) {
        url = 'https://' + url
      }
      if (!text) text = url
      close()
      editor.restoreSelection()
      editor.insertNode({
        type: 'link',
        url: url,
        target: '_blank',
        children: [{ text: text }]
      })
      try { editor.move(1) } catch (e) {}
      hasUnsaved.value = true
    }

    // 回车确认
    urlInput.onkeydown = (e) => { if (e.key === 'Enter') btnConfirm.click() }
    textInput.onkeydown = (e) => { if (e.key === 'Enter') btnConfirm.click() }
  }
}

// ── 插入文件菜单（自定义对话框）──

class ReqFileMenu {
  constructor() {
    this.title = '插入文件'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M854.6 288.6L639.4 73.4c-6-6-14.1-9.4-22.6-9.4H192c-17.7 0-32 14.3-32 32v832c0 17.7 14.3 32 32 32h640c17.7 0 32-14.3 32-32V311.3c0-8.5-3.4-16.7-9.4-22.7zM790.2 326H602V137.8L790.2 326z m1.8 562H232V136h302v216c0 23.2 18.8 42 42 42h216v494z"/></svg>'
    this.tag = 'button'
  }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor, value) {
    if (!req.value?.id) return
    let selectedFile = null

    // 构建自定义对话框
    const overlay = document.createElement('div')
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:10000;display:flex;align-items:center;justify-content:center'
    const dialog = document.createElement('div')
    dialog.style.cssText = 'background:#fff;border-radius:8px;padding:24px;width:420px;box-shadow:0 4px 24px rgba(0,0,0,0.15);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
    dialog.innerHTML = `
      <div style="font-size:16px;font-weight:600;margin-bottom:20px;color:#303133">插入文件</div>
      <div style="margin-bottom:12px">
        <label style="font-size:13px;color:#606266;display:block;margin-bottom:6px">显示文本</label>
        <input id="req-file-text" type="text" placeholder="留空则使用文件名" style="width:100%;padding:8px 12px;border:1px solid #dcdfe6;border-radius:4px;font-size:14px;box-sizing:border-box;outline:none" />
      </div>
      <div style="margin-bottom:4px">
        <label style="font-size:13px;color:#606266;display:block;margin-bottom:6px">选择文件</label>
        <div style="display:flex;gap:8px;align-items:center">
          <button id="req-file-pick" type="button" style="padding:8px 16px;border:1px solid #dcdfe6;border-radius:4px;background:#f5f7fa;cursor:pointer;font-size:13px;color:#606266">选择文件</button>
          <span id="req-file-name" style="font-size:12px;color:#909399;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">未选择</span>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px">
        <button id="req-file-cancel" type="button" style="padding:8px 20px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;cursor:pointer;font-size:13px;color:#606266">取消</button>
        <button id="req-file-confirm" type="button" style="padding:8px 20px;border:none;border-radius:4px;background:#534ab7;cursor:pointer;font-size:13px;color:#fff;opacity:0.6" disabled>确定</button>
      </div>`
    overlay.appendChild(dialog)
    document.body.appendChild(overlay)

    const textInput = dialog.querySelector('#req-file-text')
    const filePick = dialog.querySelector('#req-file-pick')
    const fileName = dialog.querySelector('#req-file-name')
    const btnConfirm = dialog.querySelector('#req-file-confirm')
    const btnCancel = dialog.querySelector('#req-file-cancel')

    // 文件选择
    filePick.onclick = () => {
      const input = document.createElement('input')
      input.type = 'file'
      input.onchange = () => {
        selectedFile = input.files?.[0] || null
        if (selectedFile) {
          fileName.textContent = selectedFile.name
          fileName.style.color = '#303133'
          btnConfirm.disabled = false
          btnConfirm.style.opacity = '1'
        } else {
          fileName.textContent = '未选择'
          fileName.style.color = '#909399'
          btnConfirm.disabled = true
          btnConfirm.style.opacity = '0.6'
        }
      }
      input.click()
    }

    const close = () => { document.body.removeChild(overlay) }

    btnCancel.onclick = close

    // 点击遮罩关闭
    overlay.onclick = (e) => { if (e.target === overlay) close() }

    // 确认上传
    btnConfirm.onclick = async () => {
      if (!selectedFile) return
      close()
      try {
        const result = await uploadRequirementFile(projectId.value, req.value.id, selectedFile)
        if (result.url) {
          const linkText = textInput.value.trim() || result.original_filename || selectedFile.name
          editor.restoreSelection()
          editor.insertNode({
            type: 'link',
            url: result.url,
            target: '_blank',
            children: [{ text: linkText }]
          })
          try { editor.move(1) } catch (e) {}
          hasUnsaved.value = true
        }
      } catch {
        ElMessage.error('文件上传失败')
      }
    }
  }
}

try {
  Boot.registerMenu({
    key: 'reqFileUpload',
    factory() { return new ReqFileMenu() }
  })
} catch (e) {
  if (e.message && !e.message.includes('Duplicated key')) throw e
}

// 注册插入链接菜单（自定义键名，避免与内置 insertLink 模态菜单冲突）
try {
  Boot.registerMenu({
    key: 'reqInsertLink',
    factory() { return new ReqLinkMenu() }
  })
} catch (e) {
  if (e.message && !e.message.includes('Duplicated key')) throw e
}

// 编辑链接菜单（悬浮栏"编辑链接"），自定义键名避免与内置模态菜单冲突
class EditLinkMenu extends ReqLinkMenu {
  constructor() {
    super()
    this.title = '编辑链接'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M257.7 752c2 0 4-.2 6-.5L431.9 722c2-.4 3.9-1.3 5.3-2.8l423.9-423.9a9.96 9.96 0 0 0 0-14.1L694.9 114.9c-1.9-1.9-4.4-2.9-7.1-2.9s-5.2 1-7.1 2.9L256.8 538.8c-1.5 1.5-2.4 3.3-2.8 5.3l-29.5 168.2a33.5 33.5 0 0 0 9.4 29.8c6.6 6.4 14.9 9.9 23.8 9.9z"/></svg>'
  }
  exec(editor, value) {
    // 从 DOM 获取当前链接的文本和 href
    let linkText = '', linkUrl = ''
    try {
      const sel = window.getSelection()
      if (sel && sel.anchorNode) {
        let el = sel.anchorNode
        while (el && el.nodeName !== 'A') el = el.parentElement
        if (el) {
          linkText = (el.textContent || '').trim()
          linkUrl = el.getAttribute('href') || ''
        }
      }
    } catch {}

    const isFileLink = /\/uploads\/.+\/requirements\/.+\/files\//.test(linkUrl)
    if (!req.value?.id && isFileLink) return

    const overlay = document.createElement('div')
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:10000;display:flex;align-items:center;justify-content:center'
    const dialog = document.createElement('div')
    dialog.style.cssText = 'background:#fff;border-radius:8px;padding:24px;width:420px;box-shadow:0 4px 24px rgba(0,0,0,0.15);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif'
    dialog.innerHTML = `
      <div style="font-size:16px;font-weight:600;margin-bottom:20px;color:#303133">${isFileLink ? '编辑文件' : '编辑链接'}</div>
      <div style="margin-bottom:12px">
        <label style="font-size:13px;color:#606266;display:block;margin-bottom:6px">显示文本</label>
        <input id="req-link-text" type="text" value="${linkText.replace(/"/g, '&quot;')}" style="width:100%;padding:8px 12px;border:1px solid #dcdfe6;border-radius:4px;font-size:14px;box-sizing:border-box;outline:none" />
      </div>
      <div style="margin-bottom:4px">
        <label style="font-size:13px;color:#606266;display:block;margin-bottom:6px">${isFileLink ? '选择文件' : '链接地址'}</label>
        ${isFileLink
          ? `<div style="display:flex;gap:8px;align-items:center">
              <button id="req-link-file-pick" type="button" style="padding:8px 16px;border:1px solid #dcdfe6;border-radius:4px;background:#f5f7fa;cursor:pointer;font-size:13px;color:#606266">选择文件</button>
              <span id="req-link-file-name" style="font-size:12px;color:#303133;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1">${linkText.replace(/"/g, '&quot;')}</span>
            </div>`
          : `<input id="req-link-url" type="text" value="${linkUrl.replace(/"/g, '&quot;')}" style="width:100%;padding:8px 12px;border:1px solid #dcdfe6;border-radius:4px;font-size:14px;box-sizing:border-box;outline:none" />`
        }
      </div>
      <div style="display:flex;justify-content:flex-end;gap:10px;margin-top:20px">
        <button id="req-link-cancel" type="button" style="padding:8px 20px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;cursor:pointer;font-size:13px;color:#606266">取消</button>
        <button id="req-link-confirm" type="button" style="padding:8px 20px;border:none;border-radius:4px;background:#534ab7;cursor:pointer;font-size:13px;color:#fff;opacity:0.6" disabled>确定</button>
      </div>`
    overlay.appendChild(dialog)
    document.body.appendChild(overlay)

    const textInput = dialog.querySelector('#req-link-text')
    const btnConfirm = dialog.querySelector('#req-link-confirm')
    const btnCancel = dialog.querySelector('#req-link-cancel')
    let selectedFile = null

    if (isFileLink) {
      const filePick = dialog.querySelector('#req-link-file-pick')
      const fileNameSpan = dialog.querySelector('#req-link-file-name')
      // 文件已存在，直接激活按钮
      btnConfirm.disabled = false
      btnConfirm.style.opacity = '1'
      filePick.onclick = () => {
        const input = document.createElement('input')
        input.type = 'file'
        input.onchange = () => {
          selectedFile = input.files?.[0] || null
          if (selectedFile) {
            fileNameSpan.textContent = selectedFile.name
            fileNameSpan.style.color = '#303133'
            btnConfirm.disabled = false
            btnConfirm.style.opacity = '1'
          }
        }
        input.click()
      }
    } else {
      const urlInput = dialog.querySelector('#req-link-url')
      // 已预填 URL，直接激活按钮
      if (linkUrl.trim()) {
        btnConfirm.disabled = false
        btnConfirm.style.opacity = '1'
      }
      urlInput.addEventListener('input', () => {
        if (urlInput.value.trim()) {
          btnConfirm.disabled = false
          btnConfirm.style.opacity = '1'
        } else {
          btnConfirm.disabled = true
          btnConfirm.style.opacity = '0.6'
        }
      })
      urlInput.onkeydown = (e) => { if (e.key === 'Enter') btnConfirm.click() }
    }

    const close = () => { document.body.removeChild(overlay) }
    btnCancel.onclick = close

    btnConfirm.onclick = isFileLink
      ? async () => {
          let text = textInput.value.trim()
          if (!selectedFile && !linkUrl) return
          close()
          let newUrl = linkUrl
          if (selectedFile) {
            try {
              const result = await uploadRequirementFile(projectId.value, req.value.id, selectedFile)
              if (result.url) newUrl = result.url
              if (!text) text = result.original_filename || selectedFile.name
            } catch { return }
          }
          if (!text) text = newUrl.split('/').pop() || newUrl
          // 选中整个超链节点后完整替换
          try {
            editor.restoreSelection()
            const linkEntry = SlateEditor.above(editor, {
              match: n => n.type === 'link'
            })
            if (linkEntry) {
              const [, linkPath] = linkEntry
              SlateTransforms.select(editor, {
                anchor: SlateEditor.start(editor, linkPath),
                focus: SlateEditor.end(editor, linkPath)
              })
              editor.deleteFragment()
              editor.insertNode({
                type: 'link',
                url: newUrl,
                children: [{ text: text }]
              })
              try { editor.move(1) } catch (e) {}
            }
          } catch {}
          hasUnsaved.value = true
        }
      : () => {
          let url = (dialog.querySelector('#req-link-url')).value.trim()
          let text = textInput.value.trim()
          if (!url) return
          if (!/^[\/\.#\?]/.test(url) && !/^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(url)) {
            url = 'https://' + url
          }
          if (!text) text = url
          close()
          try {
            editor.restoreSelection()
            const linkEntry = SlateEditor.above(editor, {
              match: n => n.type === 'link'
            })
            if (linkEntry) {
              const [, linkPath] = linkEntry
              SlateTransforms.select(editor, {
                anchor: SlateEditor.start(editor, linkPath),
                focus: SlateEditor.end(editor, linkPath)
              })
              editor.deleteFragment()
              editor.insertNode({
                type: 'link',
                url: url,
                children: [{ text: text }]
              })
              try { editor.move(1) } catch (e) {}
            }
          } catch {}
          hasUnsaved.value = true
        }

    textInput.onkeydown = (e) => { if (e.key === 'Enter') btnConfirm.click() }
  }
}

try {
  Boot.registerMenu({
    key: 'reqEditLink',
    factory() { return new EditLinkMenu() }
  })
} catch (e) {
  if (e.message && !e.message.includes('Duplicated key')) throw e
}

// ── 查看链接菜单（悬浮栏"查看链接"），文件链接显示预览弹窗 ──
class ViewLinkMenu {
  constructor() {
    this.title = '查看链接'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M942.2 486.2C847.4 286.5 704.1 186 512 186c-192.2 0-335.4 100.5-430.2 300.3-7.7 16.2-7.7 35.4 0 51.6C176.6 737.5 319.9 838 512 838c192.2 0 335.4-100.5 430.2-300.3 7.7-16.2 7.7-35.4 0-51.5zM512 766c-161.3 0-279.4-81.8-362.7-254C232.6 339.8 350.7 258 512 258c161.3 0 279.4 81.8 362.7 254C791.5 684.2 673.4 766 512 766z"/><path d="M508 330c-62.6 0-113.4 50.8-113.4 113.4S445.4 556.8 508 556.8s113.4-50.8 113.4-113.4S570.6 330 508 330z"/></svg>'
    this.tag = 'button'
  }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor, value) {
    try {
      const sel = window.getSelection()
      if (!sel || !sel.anchorNode) return
      let el = sel.anchorNode
      while (el && el.nodeName !== 'A') el = el.parentElement
      if (!el) return
      const href = el.getAttribute('href') || ''
      if (!href) return
      // 文件链接 → 预览弹窗
      if (/\/uploads\/.+\/requirements\/.+\/files\//.test(href)) {
        const container = editor.getEditableContainer?.() ||
          document.querySelector('.w-e-text-container [data-slate-editor]') ||
          document.querySelector('.w-e-text-container')
        if (container) {
          const list = buildUnifiedPreviewList(container)
          const idx = list.findIndex(item => item.type === 'file' && item.downloadUrl === href)
          openUnifiedPreview(list, idx >= 0 ? idx : 0)
        }
        return
      }
      // 普通链接 → 新标签页
      const fixed = _ensureProtocol(href)
      window.open(fixed, '_blank', 'noopener')
    } catch {}
  }
}

try {
  Boot.registerMenu({
    key: 'reqViewLink',
    factory() { return new ViewLinkMenu() }
  })
} catch (e) {
  if (e.message && !e.message.includes('Duplicated key')) throw e
}

// ── 取消链接菜单（悬浮栏"取消链接"），替代内置 unLink ──
class UnLinkMenu {
  constructor() {
    this.title = '取消链接'
    this.iconSvg = '<svg viewBox="0 0 1024 1024"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z m192 484H320c-17.7 0-32-14.3-32-32v-8c0-17.7 14.3-32 32-32h384c17.7 0 32 14.3 32 32v8c0 17.7-14.3 32-32 32z"/></svg>'
    this.tag = 'button'
  }
  getValue() { return '' }
  isActive() { return false }
  isDisabled() { return false }
  exec(editor, value) {
    try {
      editor.restoreSelection()
      SlateTransforms.unwrapNodes(editor, {
        match: n => n.type === 'link'
      })
    } catch {}
  }
}

try {
  Boot.registerMenu({
    key: 'reqUnLink',
    factory() { return new UnLinkMenu() }
  })
} catch (e) {
  if (e.message && !e.message.includes('Duplicated key')) throw e
}

const route = useRoute()
const router = useRouter()
// 响应式 projectId，确保路由切换时正确更新（修复第二次进入详情页时内容不加载的问题）
const projectId = computed(() => route.params.projectId)

const loading = ref(false)
const req = ref(null)
const customFields = ref([])
const statusPools = ref([])
const priorityPools = ref([])
const descDraft = ref('')
const origImgFilenames = new Set()  // 原始描述中的图片文件名
const origReqFiles = new Set()       // 原始描述中的附件文件
const saveStatus = ref('')  // '' | 'saving' | 'saved' | 'error'

// ── 状态/优先级 英文↔中文 映射（与 RequirementList.vue 保持一致） ──
const statusEnToZh = { todo: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' }
const statusZhToEn = Object.fromEntries(Object.entries(statusEnToZh).map(([k, v]) => [v, k]))
const priorityEnToZh = { low: '低', normal: '普通', high: '高', urgent: '紧急' }
const priorityZhToEn = Object.fromEntries(Object.entries(priorityEnToZh).map(([k, v]) => [v, k]))

const editTitleDialog = ref(false)
const editTitleVal = ref('')
const exitConfirmVisible = ref(false)
let exitResolve = null  // 退出编辑的 Promise resolve

// ── 统一预览（图片+附件） ──
const previewDialog = ref(false)
const previewTitle = ref('')
const previewSrc = ref('')
const previewList = ref([])     // [{ type:'image'|'file', src, title }]
const previewIndex = ref(0)
const previewIsFile = ref(false)
const imgState = ref({ x: 0, y: 0, scale: 1 })
const isDragging = ref(false)
let dragStart = { x: 0, y: 0 }

// ── 富文本编辑器 ──
const editorRef = shallowRef()
const isEditing = ref(false)
const exportLoading = ref(false)
const hasUnsaved = ref(false)

const toolbarConfig = {
  toolbarKeys: [
    'undo', 'redo',
    '|',
    'bold', 'italic', 'underline', 'through', 'code',
    '|',
    'color', 'bgColor',
    '|',
    'header1', 'header2', 'header3',
    '|',
    'bulletedList', 'numberedList', 'blockquote', 'bqColorSelect',
    '|',
    'insertTable',
    '|',
    'divider',
    '|',
    'clearStyle',
    '|',
    'uploadImage', 'reqInsertLink', 'reqFileUpload',
  ],
}

// ── 超链边界检测：光标在超链首/尾时，自动移出链接 ──
/** 检测光标是否在超链边界（首字符位置 0 或尾字符位置），是则移出链接并返回 true */
const escapeLinkBoundary = (editor) => {
  const { selection } = editor
  if (!selection || !SlateRange.isCollapsed(selection)) return false
  try {
    const linkEntry = SlateEditor.above(editor, {
      at: selection,
      match: n => n.type === 'link'
    })
    if (!linkEntry) return false
    const [linkNode, linkPath] = linkEntry
    const { offset } = selection.anchor
    const linkText = linkNode.children?.[0]?.text || ''
    if (offset === 0) {
      const point = SlateEditor.before(editor, linkPath)
      if (point) { SlateTransforms.select(editor, point); return true }
    } else if (linkText.length > 0 && offset >= linkText.length) {
      const point = SlateEditor.after(editor, linkPath)
      if (point) { SlateTransforms.select(editor, point); return true }
    }
  } catch (e) {}
  return false
}

const onEditorCreated = (editor) => {
  editorRef.value = editor

  // 覆盖 insertText：光标在超链首/尾时，先移出链接再插入文本
  const { insertText } = editor
  editor.insertText = (text) => {
    if (escapeLinkBoundary(editor)) {
      // 已移出链接，在外部插入文本
      insertText(text)
      return
    }
    insertText(text)
  }

  // 初始化为只读模式，保留 wangEditor 样式渲染
  editor.disable()

  // 延迟绑定 DOM 事件，追踪当前交互的 blockquote + 图片双击预览
  setTimeout(() => {
    try {
      const container = editor.getEditableContainer?.() ||
        document.querySelector('.w-e-text-container [data-slate-editor]') ||
        document.querySelector('.w-e-text-container')
      if (container) {
        // mousedown：用户点击编辑区时立即记录目标 blockquote（此时选区还在）
        container.addEventListener('mousedown', handleEditorMouseDown)
        // mouseup：点击超链边界时自动移出光标，避免触发悬浮菜单
        container.addEventListener('mouseup', handleLinkBoundaryClick)
        // 双击图片预览（仅只读模式生效，JS 内检查 isEditing）
        container.addEventListener('dblclick', onEditorDblClick)
        // 链接点击：只读模式下拦截，补全协议后新标签页打开
        container.addEventListener('click', handleEditorClick)
        // selectionchange：光标移动后更新
        document.addEventListener('selectionchange', handleSelectionChange)
      }
    } catch {}
  }, 300)
  // 恢复引用块颜色：从数据库 HTML 填充 bqColorStore 并同步到编辑器 DOM
  restoreBqColors()
  // 延迟兜底：WangEditor 可能异步渲染，200ms 后再试一次
  setTimeout(() => restoreBqColors(), 200)
  // 修复链接 href（补全缺少协议的 URL）
  setTimeout(() => fixLinkHrefs(), 220)
}

/** mousedown 时记录点击位置所在的 blockquote */
const handleEditorMouseDown = (e) => {
  const bq = findParentBlockquote(e.target)
  if (bq) {
    lastTouchedBlockquote = bq
    bq.setAttribute('data-bq-active', 'true')
    // 清除其他 blockquote 的 active 标记
    const allBq = bq.parentElement?.querySelectorAll('blockquote')
    if (allBq) { for (const el of allBq) { if (el !== bq) el.removeAttribute('data-bq-active') } }
  } else {
    lastTouchedBlockquote = null
  }
}

/** mouseup 时检测光标是否落在超链边界，若是则自动移出（避免触发悬浮菜单） */
const handleLinkBoundaryClick = () => {
  // 仅编辑模式生效
  if (!isEditing.value) return
  const editor = editorRef.value
  if (!editor) return
  // 延迟一帧确保 Slate 选区已更新
  requestAnimationFrame(() => {
    try { escapeLinkBoundary(editor) } catch (e) {}
  })
}

/** selectionchange 时同步更新 lastTouchedBlockquote */
const handleSelectionChange = () => {
  try {
    const sel = window.getSelection()
    if (!sel || !sel.anchorNode) return
    const bq = findParentBlockquote(sel.anchorNode)
    if (bq) {
      lastTouchedBlockquote = bq
      bq.setAttribute('data-bq-active', 'true')
      const allBq = bq.parentElement?.querySelectorAll('blockquote')
      if (allBq) { for (const el of allBq) { if (el !== bq) el.removeAttribute('data-bq-active') } }
    }
  } catch {}
}

/** 只读模式下点击链接：文件附件用预览弹窗，普通链接用新标签页打开 */
const handleEditorClick = (e) => {
  // 编辑模式下不拦截（WangEditor 自己处理链接交互）
  if (isEditing.value) return

  // 向上查找 <a> 标签
  let target = e.target
  while (target && target.tagName !== 'A') {
    target = target.parentElement
  }
  if (!target || target.tagName !== 'A') return

  e.preventDefault()
  let href = target.getAttribute('href') || ''
  if (!href) return

  // 需求附件文件 → 统一预览弹窗
  if (/\/uploads\/.+\/requirements\/.+\/files\//.test(href)) {
    const container = e.currentTarget
    const list = buildUnifiedPreviewList(container)
    // 按原始 href 匹配（而非标题，因为标题可能是用户自定义文本）
    const idx = list.findIndex(item => item.type === 'file' && item.downloadUrl === href)
    openUnifiedPreview(list, idx >= 0 ? idx : 0)
    return
  }

  // 普通链接 → 新标签页
  href = _ensureProtocol(href)
  window.open(href, '_blank', 'noopener')
}

/** 修复 DOM 中链接 href 属性，由 fixLinkHrefsInHtml 调用更可靠 */
const _ensureProtocol = (href) => {
  if (!href) return href
  // 绝对路径、相对路径、锚点等不处理
  if (/^[\/\.#\?]/.test(href)) return href
  if (!/^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(href)) {
    return 'https://' + href
  }
  return href
}

/** 修复 HTML 字符串中所有 <a> 标签的 href，补全缺少的协议 */
const fixLinkHrefsInHtml = (html) => {
  if (!html) return html
  const tmp = document.createElement('div')
  tmp.innerHTML = html
  const links = tmp.querySelectorAll('a[href]')
  let changed = false
  for (const a of links) {
    const oldHref = a.getAttribute('href')
    const newHref = _ensureProtocol(oldHref)
    if (newHref !== oldHref) {
      a.setAttribute('href', newHref)
      changed = true
    }
  }
  return changed ? tmp.innerHTML : html
}
const fixLinkHrefs = () => {
  if (!editorRef.value) return
  try {
    const container = editorRef.value.getEditableContainer?.() ||
      document.querySelector('.w-e-text-container [data-slate-editor]') ||
      document.querySelector('.w-e-text-container')
    if (!container) return
    const links = container.querySelectorAll('a[href]')
    for (const a of links) {
      const href = a.getAttribute('href')
      const fixed = _ensureProtocol(href)
      if (fixed !== href) a.setAttribute('href', fixed)
    }
  } catch {}
}

const onEditorChange = (editor) => {
  if (isEditing.value) {
    hasUnsaved.value = true
  }
  // Slate 重建 DOM 后恢复引用块颜色（数据源为 bqColorStore，不依赖 DOM 残留属性）
  syncBqColorsToDom()
  // 重新计算标题多级编号（写入 data-heading-num，仅显示）
  updateHeadingNumbers()
  // 自动草稿：防抖暂存到 localStorage（仅编辑态）
  scheduleSaveDraft()
  // 重建目录大纲
  scheduleBuildToc()
  // 编辑态：确保光标不被固定工具栏遮挡，并即时清理已删除的附件文件
  if (isEditing.value) {
    ensureCaretVisible()
    scheduleSyncDeletedFiles()
  }
}

// ── 光标可见性：固定工具栏会遮挡顶部，输入时若光标落在工具栏覆盖区则滚动露出 ──
let _caretRaf = null
const ensureCaretVisible = () => {
  // 下一帧再计算：回车后新段落刚插入，需等浏览器完成布局，光标 rect 才准确
  if (_caretRaf) cancelAnimationFrame(_caretRaf)
  _caretRaf = requestAnimationFrame(() => {
    const wrapper = document.querySelector('.editor-wrapper')
    if (!wrapper) return
    const sel = window.getSelection()
    if (!sel || !sel.rangeCount) return
    const range = sel.getRangeAt(0)
    let rect = range.getBoundingClientRect()
    // 回车后空段落 rect 尺寸可能为 0，改用光标所在块元素兜底
    if (!rect || (rect.height === 0 && rect.width === 0)) {
      const node = range.startContainer
      const el = node && node.nodeType === 3 ? node.parentElement : node
      if (el && el.getBoundingClientRect) rect = el.getBoundingClientRect()
    }
    if (!rect || (rect.height === 0 && rect.width === 0)) return
    const wRect = wrapper.getBoundingClientRect()
    const relTop = rect.top - wRect.top
    const toolbarH = 46
    // 光标顶部被工具栏遮挡 → 上滚使光标露在工具栏下方
    if (relTop < toolbarH + 4) {
      wrapper.scrollTop -= (toolbarH + 4 - relTop)
    } else if (relTop + rect.height > wRect.bottom - 8) {
      // 光标在容器底部外 → 下滚使其可见
      wrapper.scrollTop += (relTop + rect.height - (wRect.bottom - 8))
    }
  })
}

// ── 附件即时清理：编辑中删除图片/附件节点时，防抖删除后端物理文件 ──
// 防抖 1.2s：若用户在删除后立即 Ctrl+Z 撤销，回调时图片已恢复，不会误删（避免破图）
let _delTimer = null
const scheduleSyncDeletedFiles = () => {
  clearTimeout(_delTimer)
  _delTimer = setTimeout(syncDeletedFiles, 1200)
}
const syncDeletedFiles = () => {
  if (!req.value?.id) return
  const curImgs = new Set(extractImgFilenames(descDraft.value))
  for (const fn of origImgFilenames) {
    if (!curImgs.has(fn)) {
      deleteRequirementImage(projectId.value, req.value.id, fn).catch(() => {})
      origImgFilenames.delete(fn)
    }
  }
  const curFiles = new Set(extractReqFilenames(descDraft.value))
  for (const fn of origReqFiles) {
    if (!curFiles.has(fn)) {
      deleteRequirementFile(projectId.value, req.value.id, fn).catch(() => {})
      origReqFiles.delete(fn)
    }
  }
}

// ── 目录大纲（TOC） ──
const tocVisible = ref(false)
const tocItems = ref([])
let _tocEls = []
// 1-99 阿拉伯数字转中文（目录/标题一级编号使用，与后端 _cn 一致）
const cnNum = (n) => {
  const d = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九']
  if (n <= 10) return n === 10 ? '十' : d[n]
  if (n < 20) return '十' + d[n % 10]
  const t = Math.floor(n / 10)
  const o = n % 10
  return d[t] + '十' + (o ? d[o] : '')
}

// ── 标题多级编号：遍历编辑器内的 h1/h2/h3，计算「一、/1.1 /(n)」写入 data-heading-num ──
// 存储的 HTML 来自 Slate model，不携带该属性，故不污染数据库；每次渲染后重算即可（与后端 _heading_label 一致）
const updateHeadingNumbers = (container) => {
  container = container || editorRef.value?.getEditableContainer?.() ||
    document.querySelector('.w-e-text-container [data-slate-editor]')
  if (!container) return
  const hs = container.querySelectorAll('h1, h2, h3')
  let c1 = 0, c2 = 0, c3 = 0
  hs.forEach((el) => {
    const lv = Number(el.tagName[1])
    if (lv === 1) { c1 += 1; c2 = 0; c3 = 0; el.dataset.headingNum = cnNum(c1) + '、' }
    else if (lv === 2) { c2 += 1; c3 = 0; el.dataset.headingNum = `${c1}.${c2} ` }
    else { c3 += 1; el.dataset.headingNum = `(${c3}) ` }
  })
}
const buildToc = () => {
  const container = editorRef.value?.getEditableContainer?.() ||
    document.querySelector('.w-e-text-container [data-slate-editor]')
  if (!container) return
  // 确保编号最新（与编辑器显示共用同一计算）
  updateHeadingNumbers(container)
  const hs = container.querySelectorAll('h1, h2, h3')
  _tocEls = Array.from(hs)
  tocItems.value = _tocEls.map((el, i) => ({
    level: Number(el.tagName[1]),
    label: el.dataset.headingNum || '',
    text: (el.textContent || '').trim() || `（无标题 ${i + 1}）`,
  }))
}
let _tocTimer = null
const scheduleBuildToc = () => {
  clearTimeout(_tocTimer)
  _tocTimer = setTimeout(buildToc, 300)
}
const scrollToHeading = (idx) => {
  const el = _tocEls[idx]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// ── 自动草稿（localStorage 防丢失） ──
const DRAFT_PREFIX = 'taskm_req_draft_'
const _fmtDraftTime = (ts) => {
  const d = new Date(ts)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
const saveDraft = (html) => {
  if (!req.value?.id) return
  try {
    localStorage.setItem(DRAFT_PREFIX + req.value.id, JSON.stringify({ html, ts: Date.now() }))
  } catch {}
}
const loadDraft = (id) => {
  try {
    const raw = localStorage.getItem(DRAFT_PREFIX + id)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}
const clearDraft = (id) => {
  try { localStorage.removeItem(DRAFT_PREFIX + id) } catch {}
}
let _draftTimer = null
const scheduleSaveDraft = () => {
  if (!isEditing.value || !req.value?.id) return
  clearTimeout(_draftTimer)
  _draftTimer = setTimeout(() => saveDraft(descDraft.value), 800)
}

const editorConfig = {
  placeholder: '开始编写需求文档…',
  hoverbarKeys: {
    text: { menuKeys: [] },
    // 编辑模式下悬浮链接显示编辑/取消/查看菜单
    link: { menuKeys: ['reqEditLink', 'reqUnLink', 'reqViewLink'] },
    // 图片悬浮菜单：支持删除/编辑/查看（删除时即时清理后端文件，见 onEditorChange）
    image: { menuKeys: ['deleteImage', 'editImage', 'viewImage'] },
    pre: { menuKeys: [] },
    divider: { menuKeys: [] },
  },
  MENU_CONF: {
    uploadImage: {
      async customUpload(file, insertFn) {
        if (!file) return
        const fd = new FormData()
        fd.append('file', file)
        try {
          const r = await uploadRequirementImage(projectId.value, req.value.id, file)
          if (r?.url) {
            insertFn(r.url)
          }
        } catch { ElMessage.error('图片上传失败') }
      },
    },
  },
}

const enterEdit = () => {
  // 进入编辑前修复链接 href，确保"查看链接"等悬浮菜单行为正确
  descDraft.value = fixLinkHrefsInHtml(descDraft.value)
  editorRef.value?.enable()
  hasUnsaved.value = false
  isEditing.value = true
}

const exitEdit = async () => {
  if (hasUnsaved.value) {
    const choice = await new Promise((resolve) => {
      exitResolve = resolve
      exitConfirmVisible.value = true
    })
    if (choice === 'continue') return
    if (choice === 'save') {
      await doSaveDesc()
    } else {
      // 不保存：重置内容为上次保存的版本
      descDraft.value = req.value.description || ''
      hasUnsaved.value = false
      // 清除本地草稿，避免下次进入又提示恢复
      clearDraft(req.value.id)
      // 恢复引用块颜色（重设 HTML 触发 Slate 反序列化会剥离内联样式）
      setTimeout(() => restoreBqColors(), 400)
    }
  }
  doExitEdit()
}

const onExitChoice = (choice) => {
  exitConfirmVisible.value = false
  exitResolve?.(choice)
}

const doExitEdit = () => {
  isEditing.value = false
  editorRef.value?.blur()
  editorRef.value?.disable()
  // 退出编辑后修复链接 href（编辑器可能重建了 DOM）
  nextTick(fixLinkHrefs)
}

onBeforeUnmount(() => {
  if (editorRef.value) {
    // 清理事件监听器
    try {
      const container = editorRef.value.getEditableContainer?.() ||
        document.querySelector('.w-e-text-container [data-slate-editor]') ||
        document.querySelector('.w-e-text-container')
      if (container) {
        container.removeEventListener('mousedown', handleEditorMouseDown)
        container.removeEventListener('mouseup', handleLinkBoundaryClick)
        container.removeEventListener('dblclick', onEditorDblClick)
        container.removeEventListener('click', handleEditorClick)
      }
    } catch {}
    document.removeEventListener('selectionchange', handleSelectionChange)
    editorRef.value.destroy()
  }
  lastTouchedBlockquote = null
})

// ── 数据加载 ──
const load = async (id) => {
  loading.value = true
  req.value = null
  try {
    const rId = id || route.params.requirementId
    const [reqRes, cfs, sp, pp] = await Promise.all([
      getRequirement(projectId.value, rId),
      getReqCustomFields(projectId.value, { show_inactive: false }),
      getReqStatusPools(projectId.value, { show_inactive: true }),
      getReqPriorityPools(projectId.value, { show_inactive: true }),
    ])
    customFields.value = (cfs || []).filter(f => !f.is_builtin)
    statusPools.value = sp || []
    priorityPools.value = pp || []
    const desc = reqRes.description || ''
    // 检测本地未保存草稿（防丢失）：比已保存内容新则提示恢复
    const draft = loadDraft(rId)
    // 切换需求（组件实例复用）：清空上一需求残留的引用块颜色 store，否则会串色
    Object.keys(bqColorStore).forEach(k => delete bqColorStore[k])
    // 先设 descDraft，再设 req，确保编辑器创建时 v-model 已是目标内容
    descDraft.value = desc
    req.value = reqRes
    // 记录原始图片文件名
    origImgFilenames.clear()
    for (const fn of extractImgFilenames(reqRes.description)) {
      origImgFilenames.add(fn)
    }
    // 记录原始附件文件
    origReqFiles.clear()
    for (const fn of extractReqFilenames(reqRes.description)) {
      origReqFiles.add(fn)
    }
    // 将英文状态/优先级转为中文显示名（匹配池选项）
    req.value = {
      ...reqRes,
      status: statusEnToZh[reqRes.status] || reqRes.status,
      priority: priorityEnToZh[reqRes.priority] || reqRes.priority,
    }
    // 用新需求的 HTML 重建引用块颜色 store 并同步到编辑器 DOM
    // （Slate 反序列化会剥离 data-bq-color，需在内容渲染后重新注入）
    setTimeout(() => {
      restoreBqColors()
      // 编辑内容渲染后（含草稿恢复）重建目录大纲
      buildToc()
    }, 300)
    // 编辑器 DOM 就绪后修复链接 href（补全缺少的协议）
    nextTick(fixLinkHrefs)
    // 若存在比已保存内容更新的本地草稿，提示恢复
    if (draft && draft.html !== desc) {
      ElMessageBox.confirm(
        `检测到该需求有未保存的本地草稿（${_fmtDraftTime(draft.ts)}），是否恢复？恢复后将覆盖当前已保存内容。`,
        '恢复草稿',
        { confirmButtonText: '恢复草稿', cancelButtonText: '丢弃草稿', type: 'warning' }
      ).then(() => {
        descDraft.value = draft.html
        hasUnsaved.value = true
        setTimeout(() => { restoreBqColors(); buildToc() }, 300)
      }).catch(() => {
        clearDraft(rId)
      })
    }
  } catch {
    ElMessage.error('加载需求失败')
  } finally {
    loading.value = false
  }
}

// 唯一入口：监听路由参数，immediate 覆盖首次加载 + 后续同组件跳转
watch(() => route.params.requirementId, (newId) => {
  if (newId) load(newId)
}, { immediate: true })

// 防御性兜底：如果 watcher immediate 未触发（第二次进入同路由时可能发生），
// 在 onMounted 中补加载。通过 req/loading 状态避免重复请求。
onMounted(() => {
  const rId = route.params.requirementId
  if (rId && !req.value && !loading.value) {
    load(rId)
  }
})

// ── 标题编辑 ──
const startEditTitle = () => {
  editTitleVal.value = req.value.title
  editTitleDialog.value = true
}
const doSaveTitle = async () => {
  const t = editTitleVal.value?.trim()
  if (!t) return
  try {
    await updateRequirement(projectId.value, req.value.id, { title: t })
    req.value.title = t
    editTitleDialog.value = false
    ElMessage.success('标题已更新')
  } catch {
    ElMessage.error('标题更新失败')
  }
}

// ── 描述保存 ──

/** 从 BQ_PRESETS 查找背景色对应的边框色 */
const bqBorderColorMap = Object.fromEntries(BQ_PRESETS.map(p => [p.value, p.border]))

/**
 * 引用块颜色持久化存储：以规范化文本为键，记录 {color, border}。
 * 不依赖 DOM 属性（Slate 会重建 DOM 导致属性丢失），
 * 而是作为独立的 JS 数据源驱动保存/加载/显示。
 */
const bqColorStore = reactive({})

/** 规范化文本：去空白 + 零宽字符 + 控制字符，截断为稳定键 */
const _bqKey = (text) => (text || '')
  .replace(/[\s\uFEFF\u200B-\u200D\u2060\u200E\u200F]/g, '')
  .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
  .slice(0, 80)

/** 将 bqColorStore 的颜色同步到编辑器 DOM 中所有 blockquote（Slate 重建 DOM 后恢复） */
const syncBqColorsToDom = () => {
  if (!editorRef.value) return
  try {
    const container =
      editorRef.value.getEditableContainer?.() ||
      document.querySelector('.w-e-text-container [data-slate-editor]') ||
      document.querySelector('.w-e-text-container')
    if (!container) return
    const bqs = container.querySelectorAll('blockquote')
    for (const bq of bqs) {
      const text = (bq.textContent || '').trim()
      // 精确匹配优先（_bqKey 已清洗零宽字符）
      let key = _bqKey(text)
      let entry = bqColorStore[key]
      // 模糊匹配：查找 store 中以 bq 文本开头或 bq 文本以 store key 开头的项
      if (!entry && text.length > 3) {
        for (const [k, v] of Object.entries(bqColorStore)) {
          if (k.startsWith(key) || key.startsWith(k)) { entry = v; break }
        }
      }
      // 兼容兜底：旧版 store key 可能残留零宽字符，用清洗后的 key 再查一遍
      if (!entry) {
        const cleanStoreKey = _bqKey(key)
        for (const [k, v] of Object.entries(bqColorStore)) {
          const cleanK = _bqKey(k)
          if (cleanK === cleanStoreKey || cleanK.startsWith(cleanStoreKey) || cleanStoreKey.startsWith(cleanK)) { entry = v; break }
        }
      }
      if (entry) {
        bq.setAttribute('data-bq-color', entry.color)
        bq.setAttribute('data-bq-border', entry.border)
      }
    }
  } catch {}
}

/**
 * 保存前注入引用块颜色到 HTML 字符串。
 * 数据源是 bqColorStore（JS 变量），不依赖编辑器 DOM。
 * 同时注入 data-bq-border 供后端导出 DOCX 渲染左侧彩色竖线。
 */
const injectBqColorsToHtml = (html) => {
  if (!html || html.indexOf('blockquote') === -1) return html
  const storeKeys = Object.keys(bqColorStore)
  if (!storeKeys.length) return html

  const tmpDiv = document.createElement('div')
  tmpDiv.innerHTML = html
  const parsedBqs = Array.from(tmpDiv.querySelectorAll('blockquote'))
  if (!parsedBqs.length) return html

  for (const bq of parsedBqs) {
    const text = (bq.textContent || '').trim()
    const key = _bqKey(text)
    let entry = bqColorStore[key]
    // 模糊匹配
    if (!entry && text.length > 3) {
      for (const [k, v] of Object.entries(bqColorStore)) {
        if (k.startsWith(key) || key.startsWith(k)) { entry = v; break }
      }
    }
    // 兼容兜底：旧版 store key 可能残留零宽字符
    if (!entry) {
      const cleanStoreKey = _bqKey(key)
      for (const [k, v] of Object.entries(bqColorStore)) {
        const cleanK = _bqKey(k)
        if (cleanK === cleanStoreKey || cleanK.startsWith(cleanStoreKey) || cleanStoreKey.startsWith(cleanK)) { entry = v; break }
      }
    }
    if (entry) {
      bq.setAttribute('data-bq-color', entry.color)
      bq.setAttribute('data-bq-border', entry.border)
    }
  }

  // 传播：未匹配的相邻块继承最近有色块的颜色
  const resultBqs = Array.from(tmpDiv.querySelectorAll('blockquote'))
  for (let i = 0; i < resultBqs.length; i++) {
    if (resultBqs[i].hasAttribute('data-bq-color')) {
      const color = resultBqs[i].getAttribute('data-bq-color')
      const border = resultBqs[i].getAttribute('data-bq-border')
      for (let j = i + 1; j < resultBqs.length; j++) {
        if (resultBqs[j].hasAttribute('data-bq-color')) break
        resultBqs[j].setAttribute('data-bq-color', color)
        if (border) resultBqs[j].setAttribute('data-bq-border', border)
      }
    }
  }
  for (let i = resultBqs.length - 1; i >= 0; i--) {
    if (resultBqs[i].hasAttribute('data-bq-color')) {
      const color = resultBqs[i].getAttribute('data-bq-color')
      const border = resultBqs[i].getAttribute('data-bq-border')
      for (let j = i - 1; j >= 0; j--) {
        if (resultBqs[j].hasAttribute('data-bq-color')) break
        resultBqs[j].setAttribute('data-bq-color', color)
        if (border) resultBqs[j].setAttribute('data-bq-border', border)
      }
    }
  }

  return tmpDiv.innerHTML
}

/**
 * 从已保存 HTML 中提取颜色信息填充 bqColorStore 并同步到编辑器 DOM。
 * 页面加载/内容重置后调用。
 */
const restoreBqColors = () => {
  if (!req.value?.description) return
  const tmpDiv = document.createElement('div')
  tmpDiv.innerHTML = req.value.description
  const rawBqs = Array.from(tmpDiv.querySelectorAll('blockquote'))
  for (const bq of rawBqs) {
    const color = bq.getAttribute('data-bq-color')
    if (!color) continue
    const text = (bq.textContent || '').trim()
    const border = bq.getAttribute('data-bq-border') || bqBorderColorMap[color] || color
    bqColorStore[_bqKey(text)] = { color, border }
  }
  syncBqColorsToDom()
}

const doSaveDesc = async () => {
  if (!req.value) return
  saveStatus.value = 'saving'
  try {
    // 将 DOM 中的引用块颜色注入到 HTML 字符串中再保存
    // 同时修复链接 href 缺少协议的问题
    const finalHtml = fixLinkHrefsInHtml(injectBqColorsToHtml(descDraft.value))
    await updateRequirement(projectId.value, req.value.id, { description: finalHtml })
    req.value.description = finalHtml
    // 保存成功后清除本地草稿
    clearDraft(req.value.id)
    // 不再更新 descDraft，避免触发 WangEditor 重新渲染导致
    // 内联样式（引用块颜色）被 Slate 反序列化时剥离
    hasUnsaved.value = false

    // 清理已删除的图片文件
    const newFilenames = new Set(extractImgFilenames(descDraft.value))
    for (const fn of origImgFilenames) {
      if (!newFilenames.has(fn)) {
        deleteRequirementImage(projectId.value, req.value.id, fn).catch(() => {})
      }
    }
    origImgFilenames.clear()
    for (const fn of newFilenames) origImgFilenames.add(fn)

    // 清理已删除的附件文件
    const newReqFiles = new Set(extractReqFilenames(descDraft.value))
    for (const fn of origReqFiles) {
      if (!newReqFiles.has(fn)) {
        deleteRequirementFile(projectId.value, req.value.id, fn).catch(() => {})
      }
    }
    origReqFiles.clear()
    for (const fn of newReqFiles) origReqFiles.add(fn)

    saveStatus.value = 'saved'
    setTimeout(() => { if (saveStatus.value === 'saved') saveStatus.value = '' }, 1500)
  } catch {
    saveStatus.value = 'error'
    setTimeout(() => { saveStatus.value = '' }, 3000)
  }
}

const doExportRequirement = async () => {
  if (!req.value) return
  exportLoading.value = true
  try {
    const res = await exportRequirementDoc(projectId.value, req.value.id)
    const blob = new Blob([res.data], { type: 'application/zip' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const pad = (n) => String(n).padStart(2, '0')
    const now = new Date()
    const ts = `${now.getFullYear()}${pad(now.getMonth()+1)}${pad(now.getDate())}${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
    a.download = `${req.value.title}_${ts}.zip`
    a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('导出失败')
  } finally {
    exportLoading.value = false
  }
}

// ── 右侧栏快速编辑 ──
const quickUpdateStatus = async (val) => {
  try {
    // 中文显示名 → 英文存储值
    const enVal = statusZhToEn[val] || val
    await updateRequirement(projectId.value, req.value.id, { status: enVal })
    ElMessage.success('状态已更新')
  } catch {
    ElMessage.error('状态更新失败')
  }
}

const quickUpdatePriority = async (val) => {
  try {
    // 中文显示名 → 英文存储值
    const enVal = priorityZhToEn[val] || val
    await updateRequirement(projectId.value, req.value.id, { priority: enVal })
    ElMessage.success('优先级已更新')
  } catch {
    ElMessage.error('优先级更新失败')
  }
}

// ── 自定义字段 ──
const getFieldValue = (fid) => {
  return req.value?.custom_values?.find(v => v.field_id === fid)?.value || ''
}

// ── 删除 ──
const removeReq = async () => {
  await ElMessageBox.confirm(
    `确定删除需求「${req.value.title}」吗？此操作不可恢复！`,
    '警告',
    { type: 'warning' }
  )
  await deleteRequirement(projectId.value, req.value.id)
  ElMessage.success('已删除')
  router.push(`/projects/${projectId.value}/requirements`)
}

// ── 工具函数 ──
const formatTime = (t) => t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '—'

/** 从 HTML 描述中提取已上传图片的文件名 */
const extractImgFilenames = (html) => {
  if (!html) return []
  const names = []
  const re = /\/uploads\/[^\/]+\/requirements\/[^\/]+\/images\/([^"\s)]+)/
  let m
  const g = html.matchAll(new RegExp(re.source, 'g'))
  for (m of g) names.push(m[1])
  return names
}

/** 从 HTML 描述中提取附件文件名 */
const extractReqFilenames = (html) => {
  if (!html) return []
  const names = []
  const re = /\/uploads\/[^\/]+\/requirements\/[^\/]+\/files\/([^"\s)]+)/
  let m
  const g = html.matchAll(new RegExp(re.source, 'g'))
  for (m of g) names.push(m[1])
  return names
}

// ── 统一预览入口 ──

/** 双击：图片 → 统一预览列表 */
const onEditorDblClick = (e) => {
  if (isEditing.value) return
  let target = e.target
  if (target.tagName !== 'IMG') {
    target = target.querySelector('img')
  }
  if (!target || target.tagName !== 'IMG') return

  const container = e.currentTarget
  const list = buildUnifiedPreviewList(container)
  const idx = list.findIndex(item => item.type === 'image' && item.src === target.src)
  if (idx < 0) return
  openUnifiedPreview(list, idx)
}

// ── 统一预览（图片+附件） ──

/** 构建编辑器内所有可预览项的列表（按 DOM 顺序） */
const buildUnifiedPreviewList = (container) => {
  if (!container) return []
  const items = []
  // TreeWalker 按文档顺序遍历所有元素
  const walker = document.createTreeWalker(
    container,
    NodeFilter.SHOW_ELEMENT,
    {
      acceptNode(node) {
        if (node.tagName === 'IMG') return NodeFilter.FILTER_ACCEPT
        if (node.tagName === 'A' && /\/uploads\/.+\/requirements\/.+\/files\//.test(node.getAttribute('href') || '')) return NodeFilter.FILTER_ACCEPT
        return NodeFilter.FILTER_SKIP
      }
    }
  )
  let node, imgIdx = 0
  while (node = walker.nextNode()) {
    if (node.tagName === 'IMG') {
      imgIdx++
      const ext = (node.src.split('.').pop() || '').split('?')[0]
      items.push({ type: 'image', src: node.src, downloadUrl: node.src, title: `图片${imgIdx}`, ext: ext ? '.' + ext : '' })
    } else {
      const href = node.getAttribute('href')
      const urlFilename = href.split('/').pop()
      const linkText = (node.textContent || '').trim() || decodeURIComponent(urlFilename)
      const ext = urlFilename.includes('.') ? urlFilename.slice(urlFilename.lastIndexOf('.')) : ''
      // 如果链接文字已包含相同后缀，不再重复添加
      const finalExt = linkText.toLowerCase().endsWith(ext.toLowerCase()) ? '' : ext
      const previewUrl = `/api/projects/${projectId.value}/requirements/${req.value?.id}/files/${encodeURIComponent(urlFilename)}/preview`
      items.push({ type: 'file', src: previewUrl, downloadUrl: href, title: linkText, ext: finalExt })
    }
  }
  return items
}

/** 应用预览项 */
const applyPreviewItem = (item) => {
  previewSrc.value = item.src
  previewTitle.value = item.title
  previewIsFile.value = item.type === 'file'
  imgState.value = { x: 0, y: 0, scale: 1 }
}

/** 打开统一预览（从给定列表和索引） */
const openUnifiedPreview = (list, idx) => {
  previewList.value = list
  previewIndex.value = idx
  if (idx >= 0 && idx < list.length) {
    applyPreviewItem(list[idx])
  }
  previewDialog.value = true
}

/** 上一项 */
const previewPrev = () => {
  if (previewIndex.value <= 0) return
  previewIndex.value--
  applyPreviewItem(previewList.value[previewIndex.value])
}

/** 下一项 */
const previewNext = () => {
  if (previewIndex.value >= previewList.value.length - 1) return
  previewIndex.value++
  applyPreviewItem(previewList.value[previewIndex.value])
}

/** 重置缩放 */
const resetImageZoom = () => {
  imgState.value = { x: 0, y: 0, scale: 1 }
}

/** 下载当前预览 */
const downloadPreview = async () => {
  const item = previewList.value[previewIndex.value]
  if (!item) return
  const url = item.downloadUrl || item.src
  // 下载文件名：{需求显示ID}_{图片N 或 原文件名}
  const prefix = req.value?.display_id || 'requirement'
  const downloadName = `${prefix}_${item.title}${item.ext || ''}`
  try {
    const res = await fetch(url)
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = downloadName
    a.click()
    URL.revokeObjectURL(a.href)
  } catch {
    window.open(url, '_blank')
  }
}

/** 鼠标滚轮缩放（仅图片） */
const onImgWheel = (e) => {
  if (previewIsFile.value) return
  const step = e.deltaY > 0 ? -0.05 : 0.05
  const newScale = Math.round((imgState.value.scale + step) * 100) / 100
  imgState.value.scale = Math.max(0.2, Math.min(10, newScale))
}

/** 开始拖拽 */
const onImgMouseDown = (e) => {
  isDragging.value = true
  dragStart.x = e.clientX - imgState.value.x
  dragStart.y = e.clientY - imgState.value.y
}

/** 拖拽移动 */
const onImgMouseMove = (e) => {
  if (!isDragging.value) return
  imgState.value.x = e.clientX - dragStart.x
  imgState.value.y = e.clientY - dragStart.y
}

/** 结束拖拽 */
const onImgMouseUp = () => { isDragging.value = false }
</script>

<style scoped>
/* ── 加载 ── */
.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid #e0e0e0; border-top-color: #534ab7;
  border-radius: 50%; animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── 页面布局 ── */
.page-body { display: flex; gap: 24px; align-items: flex-start; }
.body-main { flex: 1; min-width: 0; position: relative; }
.detail-side { width: 260px; flex-shrink: 0; display: flex; flex-direction: column; gap: 12px; }

/* ── 标题行 ── */
.title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.title-left { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.title-left .back-btn { flex-shrink: 0; }
.title-left .back-btn:hover { color: #534ab7; border-color: #d0cff0; background: #f5f4ff; }
.page-title { font-size: 22px; font-weight: 600; color: #222; margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.title-edit-btn { flex-shrink: 0; color: #999; }
.title-edit-btn:hover { color: #409eff; }
.req-display-id { font-size: 12px; color: #aaa; margin: 0 0 16px 0; }

/* ── 描述编辑区 ── */
.section-title {
  font-size: 14px; font-weight: 500;
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 10px; margin-top: 20px; color: #444;
}
.section-title .st-title { display: flex; align-items: center; gap: 6px; }

/* 富文本编辑器外层 */
.editor-wrapper {
  border: 1px solid #d0cff0; border-radius: 8px; overflow: auto;
  box-shadow: 0 2px 16px rgba(83,74,183,0.08);
  background: #fff;
  max-height: calc(100vh - 200px);
  /* TOC 跳转/光标定位时为固定工具栏预留顶部空间 */
  scroll-padding-top: 48px;
}
.editor-readonly :deep(.w-e-text-container) {
  cursor: default;
}
.editor-readonly :deep(.w-e-text-container [data-slate-editor] img) {
  cursor: zoom-in;
}
.editor-readonly :deep(.w-e-text-container [data-slate-editor] img:hover) {
  box-shadow: 0 0 0 2px #534ab7;
  border-radius: 4px;
}
.editor-toolbar {
  position: sticky; top: 0; z-index: 10;
  border-bottom: 1px solid #e8e8e8;
  background: #fafafa;
}
.editor-body {
  min-height: 420px;
}
.editor-body :deep(.w-e-text-container) {
  min-height: 420px !important; padding: 20px 32px !important;
}
.editor-body :deep(.w-e-text-placeholder) { left: 32px; top: 20px; }
/* 正文：单倍行距，段前段后0，统一字号14px */
.editor-body :deep(.w-e-text-container [data-slate-editor]) { padding: 0 !important; font-size: 14px; }
.editor-body :deep(.w-e-text-container [data-slate-editor] p) { line-height: 1.6; margin: 0; }
/* 引用块基础样式 + 按 data-bq-color 属性分色（CSS 属性选择器驱动，无 JS 操作内联样式） */
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote) {
  line-height: 1.6;
  margin: 0;
  padding: 8px 16px;
  border-left: 3px solid #ccc;
  background: #f8f8f8;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#e8f4fd"]) {
  background: #e8f4fd;
  border-left-color: #9fc5e8;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#e8f8e8"]) {
  background: #e8f8e8;
  border-left-color: #9fc89f;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#fef9e7"]) {
  background: #fef9e7;
  border-left-color: #e6d88a;
  color: #555;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] blockquote[data-bq-color="#fde8e8"]) {
  background: #fde8e8;
  border-left-color: #e89f9f;
  color: #555;
}
/* 灰色引用 = 默认值，无需额外规则 */
/* 注释/行内代码样式 */
.editor-body :deep(.w-e-text-container [data-slate-editor] code) {
  font-size: 13px;
  color: #888;
  background: #f5f5f5;
  border-radius: 3px;
  padding: 2px 6px;
  font-family: inherit;
}
/* ── 标题多级自动编号（JS 写入 data-heading-num，仅显示，不影响存储的 HTML） ── */
.editor-body :deep(.w-e-text-container [data-slate-editor] h1) {
  font-size: 18px; font-weight: 700; color: #1f1f1f; margin: 18px 0 8px; scroll-margin-top: 56px;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] h2) {
  font-size: 16px; font-weight: 700; color: #1f1f1f; margin: 14px 0 6px; scroll-margin-top: 56px;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] h3) {
  font-size: 14px; font-weight: 600; color: #333; margin: 12px 0 4px; scroll-margin-top: 56px;
}
.editor-body :deep(.w-e-text-container [data-slate-editor] h1)::before,
.editor-body :deep(.w-e-text-container [data-slate-editor] h2)::before,
.editor-body :deep(.w-e-text-container [data-slate-editor] h3)::before {
  content: attr(data-heading-num); font-weight: 700; margin-right: 2px;
}
/* 图片默认居中 */
.editor-body :deep(.w-e-text-container [data-slate-editor] img) {
  display: block; margin: 8px auto; max-width: 100%;
}
/* 编辑区最小高度（wangEditor v5 的 editorConfig 不支持 minHeight，需用 CSS） */
.editor-body :deep(.w-e-text-container) {
  min-height: 300px;
}
/* ── 目录大纲（TOC） ── */
.toc-panel {
  position: absolute; top: 100px; right: 12px; width: 240px;
  max-height: calc(100vh - 280px); overflow: auto;
  background: #fff; border: 1px solid #e8e8e4; border-radius: 8px;
  box-shadow: 0 6px 24px rgba(0,0,0,0.12); z-index: 50; padding: 6px;
}
.toc-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 2px 8px 6px; font-size: 13px; font-weight: 600; color: #444;
  border-bottom: 1px solid #f0f0f0;
}
.toc-list { padding: 4px 0; max-height: calc(100vh - 340px); overflow: auto; }
.toc-item {
  padding: 4px 8px; font-size: 13px; color: #333; cursor: pointer;
  border-radius: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.toc-item .toc-label { color: #534ab7; font-weight: 600; margin-right: 2px; }
.toc-item.lv3 .toc-label { color: #888; }
.toc-item:hover { background: #f5f4ff; color: #534ab7; }
.toc-item.lv1 { font-weight: 600; padding-left: 8px; }
.toc-item.lv2 { padding-left: 22px; }
.toc-item.lv3 { padding-left: 36px; color: #666; }

/* ── 图片预览弹窗 ── */
.preview-header { display: flex; align-items: center; gap: 10px; }
.preview-title { font-size: 15px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-counter { font-size: 12px; color: #999; flex-shrink: 0; }
.preview-img-wrap { overflow: auto; height: 75vh; background: #f5f5f5; border-radius: 4px; position: relative; user-select: none; }
.preview-img-container { min-height: 100%; text-align: center; padding: 16px; }
.preview-img { max-width: 100%; max-height: calc(70vh - 80px); display: inline-block; vertical-align: top; border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.preview-toolbar { display: flex; align-items: center; justify-content: center; gap: 6px; margin-top: 10px; }
.preview-toolbar .tb-sep { display: inline-block; width: 1px; height: 18px; background: #e0e0e0; flex-shrink: 0; }

/* ── 保存状态 ── */
.save-indicator { font-size: 12px; padding: 1px 10px; border-radius: 10px; line-height: 22px; }
.save--saving { color: #999; }
.save--saved { color: #519839; background: #edf7e6; }
.save--error { color: #d32f2f; background: #fdebea; }

/* ── 右侧栏 ── */
.side-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 16px; }
.side-card-fields { padding: 8px 14px; }
.side-field { display: flex; align-items: center; gap: 8px; padding: 7px 0; }
.side-field + .side-field { border-top: 1px solid #f0f0ee; }
.side-field-label {
  font-size: 13px; color: #555; width: 56px; flex-shrink: 0;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.side-field-value { font-size: 13px; color: #333; flex: 1; min-width: 0; word-break: break-all; }
.cf-detail-link {
  color: #409eff;
  text-decoration: none;
  word-break: break-all;
}
.cf-detail-link:hover {
  color: #66b1ff;
  text-decoration: underline;
}
.side-field-section { margin-top: 4px; }
.side-field-section-title {
  font-size: 12px; font-weight: 500; color: #aaa;
  padding: 6px 0 2px 0; border-top: 1px solid #f0f0ee;
}

.side-info-row { display: flex; justify-content: space-between; align-items: center; padding: 6px 0; }
.side-info-row + .side-info-row { border-top: 1px solid #f0f0ee; }
.side-info-label { font-size: 13px; color: #888; }
.side-info-value { font-size: 13px; color: #555; }
</style>
