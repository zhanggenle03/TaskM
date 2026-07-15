<template>
  <el-dialog
    :model-value="modelValue"
    title="编辑沟通内容"
    width="760px"
    top="5vh"
    append-to-body
    destroy-on-close
    @update:model-value="onClose"
  >
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
      />
    </div>
    <template #footer>
      <span style="color:#999;font-size:12px;margin-right:auto">支持加粗、列表、链接等基础格式</span>
      <el-button @click="onClose">取消</el-button>
      <el-button type="primary" @click="onSave">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import '@wangeditor/editor/dist/css/style.css'
import { onBeforeUnmount, shallowRef } from 'vue'
import { Editor, Toolbar } from '@wangeditor/editor-for-vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialHtml: { type: String, default: '' }
})
const emit = defineEmits(['update:modelValue', 'save'])

// editor 实例必须用 shallowRef，避免 Vue 的深度响应导致编辑器异常
const editorRef = shallowRef()
const mode = 'default'

// 精简工具栏：只保留沟通场景需要的格式，去掉图片/视频/表格/代码块等重型功能
const toolbarConfig = {
  excludeKeys: [
    'header1', 'header2', 'fontSize', 'fontFamily', 'lineHeight',
    'indent', 'delIndent', 'justifyLeft', 'justifyRight', 'justifyCenter',
    'insertImage', 'uploadImage', 'insertVideo', 'uploadVideo',
    'insertTable', 'codeBlock', 'emotion', 'divider', 'fullScreen',
    'group-moreStyle', 'group-indent'
  ]
}

const editorConfig = {
  placeholder: '输入沟通内容，支持加粗、列表、链接等…'
}

const handleCreated = (editor) => {
  editorRef.value = editor
  // 弹窗每次打开（destroy-on-close）都会重建编辑器，这里注入初始内容
  try {
    editor.setHtml(props.initialHtml || '')
  } catch (e) {
    console.error('设置编辑器内容失败', e)
  }
}

const onSave = () => {
  const html = editorRef.value ? editorRef.value.getHtml() : ''
  emit('save', html || '')
  emit('update:modelValue', false)
}

const onClose = () => {
  emit('update:modelValue', false)
}

onBeforeUnmount(() => {
  editorRef.value?.destroy()
})
</script>

<style scoped>
.comm-editor-wrap {
  border: 1px solid #dcdfe6;
  border-radius: 6px;
  overflow: hidden;
}
.comm-editor-toolbar {
  border-bottom: 1px solid #dcdfe6;
}
.comm-editor-body {
  height: 360px;
  overflow-y: hidden;
}
</style>
