<template>
  <div class="comm-editor-wrap">
    <Toolbar
      :editor="editorRef"
      :defaultConfig="toolbarConfig"
      :mode="mode"
      class="comm-editor-toolbar"
    />
    <Editor
      :defaultConfig="editorConfig"
      :mode="mode"
      class="comm-editor-body"
      @onCreated="handleCreated"
      @onChange="onEditorChange"
    />
  </div>
</template>

<script setup>
import '@wangeditor/editor/dist/css/style.css'
import { onBeforeUnmount, nextTick, shallowRef, ref } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'
import { ElMessage } from 'element-plus'
import { uploadCommImage } from '../api'

const props = defineProps({
  initialHtml: { type: String, default: '' },
  projectId: { type: [String, Number], default: '' },
  taskId: { type: [String, Number], default: '' },
  // 编辑已有沟通时传入；新建时为 null（此时图片走 pending，保存时回填）
  commId: { type: Number, default: null },
})
const emit = defineEmits(['change'])

// editor 实例必须用 shallowRef，避免 Vue 的深度响应导致编辑器异常
const editorRef = shallowRef()
const mode = 'default'

// 待上传图片（仅新建沟通、commId 尚未生成时）：保存时由父组件先建沟通再回填真实 URL
// { id: blobUrl, file, blobUrl } — id 复用 blobUrl 以在 HTML 中匹配
const pendingImages = ref([])

// 完整基础格式工具栏（不含需求详情页专属的引用块颜色 / 需求文件关联菜单）
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
    'bulletedList', 'numberedList',
    '|',
    'clearStyle',
    '|',
    'uploadImage', 'insertLink',
  ],
}

const editorConfig = {
  placeholder: '输入沟通内容，支持加粗、列表、图片、链接等…',
  hoverbarKeys: {
    text: { menuKeys: [] },
    link: { menuKeys: ['editLink', 'unLink', 'viewLink'] },
    image: { menuKeys: ['deleteImage', 'editImage', 'viewImage'] },
  },
  MENU_CONF: {
    uploadImage: {
      async customUpload(file, insertFn) {
        if (!file) return
        // 已有沟通 ID：直接上传到图片路径（不创建 Attachment 记录）
        if (props.commId) {
          try {
            const r = await uploadCommImage(props.projectId, props.taskId, props.commId, file)
            if (r?.url) insertFn(r.url)
          } catch {
            ElMessage.error('图片上传失败')
          }
          return
        }
        // 新建沟通：暂存文件，编辑期用 blob 预览，保存时回填真实 URL
        // 注：不能用 data-pending-id 标记，WangEditor 的 Slate 序列化会丢弃自定义属性
        const blobUrl = URL.createObjectURL(file)
        pendingImages.value.push({ id: blobUrl, file, blobUrl })
        insertFn(blobUrl)
      },
    },
  },
}
// ⚠️ 注意：editorConfig.onChange 在此库版本中已废弃，使用会抛异常中断编辑。
// 内容变化同步改为在模板 @onChange 中处理。

const handleCreated = (editor) => {
  editorRef.value = editor
  // 每次创建（外层弹窗 destroy-on-close 会重建）重置待上传队列
  pendingImages.value = []
  // 注入初始内容
  try {
    editor.setHtml(props.initialHtml || '')
  } catch (e) {
    console.error('设置编辑器内容失败', e)
  }
  // 自动聚焦定位光标（等 DOM 稳定后执行）
  nextTick(() => {
    try { editor.focus() } catch (e) {}
  })
}

// 内容变化实时回传父组件（HTML + 待上传图片队列），由父组件在提交时统一落库
const onEditorChange = (editor) => {
  emit('change', editor.getHtml(), pendingImages.value.slice())
}

// 供父组件调用：从外部注入图片文件（粘贴/选择文件），走与工具栏上传相同的 pending 流程
const injectImage = (file) => {
  if (!file || !editorRef.value) return
  const blobUrl = URL.createObjectURL(file)
  pendingImages.value.push({ id: blobUrl, file, blobUrl })
  editorRef.value.dangerouslyInsertHtml(`<img src="${blobUrl}" />`)
}

// 供父组件调用：直接插入已上传的图片 URL（编辑模式使用）
const insertImageUrl = (url) => {
  if (!url || !editorRef.value) return
  editorRef.value.dangerouslyInsertHtml(`<img src="${url}" />`)
}

defineExpose({ injectImage, insertImageUrl })

onBeforeUnmount(() => {
  editorRef.value?.destroy()
})
</script>

<style scoped>
.comm-editor-wrap {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  overflow: visible;
}
.comm-editor-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  border-bottom: 1px solid #e8e8e8;
  background: #fafafa;
}
.comm-editor-body {
  height: 480px;
  overflow-y: hidden;
}
/* 固定编辑区域的高宽，不随内容变化；超出部分垂直滚动 */
.comm-editor-body :deep(.w-e-text-container) {
  min-height: 480px !important;
  max-height: 480px !important;
  overflow-y: auto !important;
}
.comm-editor-body :deep(.w-e-text-container [data-slate-editor]) {
  padding: 14px 20px !important;
  line-height: 1.5 !important;
}
.comm-editor-body :deep(.w-e-text-container [data-slate-editor] p) {
  margin: 0;
  line-height: 1.5;
}
.comm-editor-body :deep(.w-e-text-placeholder) {
  left: 20px;
  top: 14px;
}
</style>
