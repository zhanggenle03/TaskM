/**
 * 富文本编辑器「链接」菜单共享模块
 *
 * 需求详情（RequirementDetail.vue）与任务沟通（CommRichEditor.vue）共用同一套
 * 自定义菜单：插入链接 / 编辑链接 / 取消链接 / 查看链接。
 * 对话框样式、交互逻辑天然对齐，后续改样式/交互只需动这一处。
 *
 * 用法：
 *   import { registerLinkMenus } from '../utils/linkMenus'
 *   const keys = registerLinkMenus('comm', {
 *     onAfterInsert() {},  // 插入链接后回调（需求：标记 hasUnsaved）
 *     onAfterEdit() {},    // 编辑链接后回调
 *     isFileLink(url) {},  // 判断链接是否为附件文件链接（需求专用；任务不传）
 *     uploadFile(file) {}, // 文件链接编辑时选择文件上传，返回 { url, filename } | null
 *     onViewFileLink(editor, href) {}, // 查看文件链接的自定义处理，返回 true 表示已拦截
 *   })
 *   // toolbarKeys:    [..., keys.insertLink]
 *   // hoverbarKeys:   link: [keys.editLink, keys.unLink, keys.viewLink]
 */
import { Boot, SlateEditor, SlateTransforms } from '@wangeditor/editor'

// ── 菜单图标（与需求编辑器原有图标一致）──
const LINK_ICON_SVG = '<svg viewBox="0 0 1024 1024"><path d="M574 665.4a8.03 8.03 0 0 0-11.3 0L446.5 781.6c-53.8 53.8-144.6 59.5-204 0-59.5-59.5-53.8-150.2 0-204l116.2-116.2c3.1-3.1 3.1-8.2 0-11.3l-39.8-39.8a8.03 8.03 0 0 0-11.3 0L191.4 526.5c-84.6 84.6-84.6 221.5 0 306s221.5 84.6 306 0l116.2-116.2c3.1-3.1 3.1-8.2 0-11.3L574 665.4zm258.6-474c-84.6-84.6-221.5-84.6-306 0L410.3 307.6a8.03 8.03 0 0 0 0 11.3l39.7 39.7c3.1 3.1 8.2 3.1 11.3 0l116.2-116.2c53.8-53.8 144.6-59.5 204 0 59.5 59.5 53.8 150.2 0 204L665.3 562.6a8.03 8.03 0 0 0 0 11.3l39.8 39.8c3.1 3.1 8.2 3.1 11.3 0l116.2-116.2c84.5-84.6 84.5-221.5 0-306.1z"/></svg>'
const EDIT_ICON_SVG = '<svg viewBox="0 0 1024 1024"><path d="M257.7 752c2 0 4-.2 6-.5L431.9 722c2-.4 3.9-1.3 5.3-2.8l423.9-423.9a9.96 9.96 0 0 0 0-14.1L694.9 114.9c-1.9-1.9-4.4-2.9-7.1-2.9s-5.2 1-7.1 2.9L256.8 538.8c-1.5 1.5-2.4 3.3-2.8 5.3l-29.5 168.2a33.5 33.5 0 0 0 9.4 29.8c6.6 6.4 14.9 9.9 23.8 9.9z"/></svg>'
const VIEW_ICON_SVG = '<svg viewBox="0 0 1024 1024"><path d="M942.2 486.2C847.4 286.5 704.1 186 512 186c-192.2 0-335.4 100.5-430.2 300.3-7.7 16.2-7.7 35.4 0 51.6C176.6 737.5 319.9 838 512 838c192.2 0 335.4-100.5 430.2-300.3 7.7-16.2 7.7-35.4 0-51.5zM512 766c-161.3 0-279.4-81.8-362.7-254C232.6 339.8 350.7 258 512 258c161.3 0 279.4 81.8 362.7 254C791.5 684.2 673.4 766 512 766z"/><path d="M508 330c-62.6 0-113.4 50.8-113.4 113.4S445.4 556.8 508 556.8s113.4-50.8 113.4-113.4S570.6 330 508 330z"/></svg>'
const UNLINK_ICON_SVG = '<svg viewBox="0 0 1024 1024"><path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64z m192 484H320c-17.7 0-32-14.3-32-32v-8c0-17.7 14.3-32 32-32h384c17.7 0 32 14.3 32 32v8c0 17.7-14.3 32-32 32z"/></svg>'

// ── 对话框公共样式（与需求编辑器完全一致）──
const CSS = {
  overlay: 'position:fixed;inset:0;background:rgba(0,0,0,0.3);z-index:10000;display:flex;align-items:center;justify-content:center',
  dialog: 'background:#fff;border-radius:8px;padding:24px;width:420px;box-shadow:0 4px 24px rgba(0,0,0,0.15);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif',
  title: 'font-size:16px;font-weight:600;margin-bottom:20px;color:#303133',
  label: 'font-size:13px;color:#606266;display:block;margin-bottom:6px',
  input: 'width:100%;padding:8px 12px;border:1px solid #dcdfe6;border-radius:4px;font-size:14px;box-sizing:border-box;outline:none',
  footer: 'display:flex;justify-content:flex-end;gap:10px;margin-top:20px',
  btnCancel: 'padding:8px 20px;border:1px solid #dcdfe6;border-radius:4px;background:#fff;cursor:pointer;font-size:13px;color:#606266',
  btnConfirm: 'padding:8px 20px;border:none;border-radius:4px;background:#534ab7;cursor:pointer;font-size:13px;color:#fff;opacity:0.6',
  pickBtn: 'padding:8px 16px;border:1px solid #dcdfe6;border-radius:4px;background:#f5f7fa;cursor:pointer;font-size:13px;color:#606266',
  fileName: 'font-size:12px;color:#909399;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1',
}

const esc = (s) => String(s ?? '').replace(/"/g, '&quot;')

/** 补全缺少协议的 URL（与需求编辑器逻辑一致） */
export const ensureProtocol = (url) => {
  if (!url) return url
  // 绝对路径、相对路径、锚点等不处理
  if (/^[\/\.#\?]/.test(url)) return url
  if (!/^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(url)) return 'https://' + url
  return url
}

/** 挂载对话框容器，返回 { overlay, dialog, close, $ } */
function mountDialog(title) {
  const overlay = document.createElement('div')
  overlay.style.cssText = CSS.overlay
  const dialog = document.createElement('div')
  dialog.style.cssText = CSS.dialog
  dialog.innerHTML = `<div style="${CSS.title}">${title}</div>`
  overlay.appendChild(dialog)
  document.body.appendChild(overlay)
  return {
    overlay,
    dialog,
    close: () => { document.body.removeChild(overlay) },
    $: (sel) => dialog.querySelector(sel),
  }
}

/** 页脚：取消 + 确定 */
function footerHtml() {
  return `
    <div style="${CSS.footer}">
      <button data-role="cancel" type="button" style="${CSS.btnCancel}">取消</button>
      <button data-role="confirm" type="button" style="${CSS.btnConfirm}" disabled>确定</button>
    </div>`
}

/** 显示文本字段 */
function textFieldHtml(value = '') {
  return `
    <div style="margin-bottom:12px">
      <label style="${CSS.label}">显示文本</label>
      <input data-role="text" type="text" placeholder="链接显示的文字" value="${esc(value)}" style="${CSS.input}" />
    </div>`
}

/** 链接地址字段 */
function urlFieldHtml(value = '') {
  return `
    <div style="margin-bottom:4px">
      <label style="${CSS.label}">链接地址</label>
      <input data-role="url" type="text" placeholder="https:// 或 www.example.com" value="${esc(value)}" style="${CSS.input}" />
    </div>`
}

/** 选择文件字段（需求附件专用） */
function fileFieldHtml(fileName = '') {
  return `
    <div style="margin-bottom:4px">
      <label style="${CSS.label}">选择文件</label>
      <div style="display:flex;gap:8px;align-items:center">
        <button data-role="pick" type="button" style="${CSS.pickBtn}">选择文件</button>
        <span data-role="file-name" style="${CSS.fileName}">${esc(fileName)}</span>
      </div>
    </div>`
}

/** 绑定回车确认 */
function bindEnter(inputs, fn) {
  for (const el of inputs) {
    if (el) el.onkeydown = (e) => { if (e.key === 'Enter') fn() }
  }
}

/** 激活/禁用确定按钮 */
function setBtnState(btn, active) {
  btn.disabled = !active
  btn.style.opacity = active ? '1' : '0.6'
}

// ── 插入链接菜单（自定义对话框，与需求编辑器风格统一）──

function makeInsertLinkMenu(prefix, opts) {
  const onAfterInsert = opts.onAfterInsert
  return class {
    constructor() {
      this.title = '插入链接'
      this.iconSvg = LINK_ICON_SVG
      this.tag = 'button'
    }
    getValue() { return '' }
    isActive() { return false }
    isDisabled() { return false }
    exec(editor) {
      const d = mountDialog('插入链接')
      d.dialog.insertAdjacentHTML('beforeend', textFieldHtml() + urlFieldHtml() + footerHtml())
      const textInput = d.$('[data-role="text"]')
      const urlInput = d.$('[data-role="url"]')
      const btnConfirm = d.$('[data-role="confirm"]')
      const btnCancel = d.$('[data-role="cancel"]')

      // 与插入文件一致的交互：URL 非空时激活确定按钮
      urlInput.addEventListener('input', () => setBtnState(btnConfirm, !!urlInput.value.trim()))

      btnCancel.onclick = d.close

      btnConfirm.onclick = () => {
        let url = urlInput.value.trim()
        let text = textInput.value.trim()
        if (!url) return
        url = ensureProtocol(url)
        if (!text) text = url
        d.close()
        editor.restoreSelection()
        editor.insertNode({
          type: 'link',
          url,
          target: '_blank',
          children: [{ text }],
        })
        try { editor.move(1) } catch (e) {}
        onAfterInsert?.()
      }

      // 回车确认
      bindEnter([urlInput, textInput], () => btnConfirm.click())
    }
  }
}

// ── 编辑链接菜单（悬浮栏"编辑链接"）──

function makeEditLinkMenu(prefix, opts) {
  const { isFileLink, uploadFile, onAfterEdit } = opts
  return class {
    constructor() {
      this.title = '编辑链接'
      this.iconSvg = EDIT_ICON_SVG
      this.tag = 'button'
    }
    getValue() { return '' }
    isActive() { return false }
    isDisabled() { return false }
    exec(editor) {
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

      const fileMode = !!(isFileLink && isFileLink(linkUrl))
      const d = mountDialog(fileMode ? '编辑文件' : '编辑链接')
      d.dialog.insertAdjacentHTML(
        'beforeend',
        textFieldHtml(linkText) + (fileMode ? fileFieldHtml(linkText) : urlFieldHtml(linkUrl)) + footerHtml()
      )
      const textInput = d.$('[data-role="text"]')
      const btnConfirm = d.$('[data-role="confirm"]')
      const btnCancel = d.$('[data-role="cancel"]')
      let selectedFile = null

      if (fileMode) {
        // 文件已存在，直接激活按钮
        setBtnState(btnConfirm, true)
        const filePick = d.$('[data-role="pick"]')
        const fileNameSpan = d.$('[data-role="file-name"]')
        filePick.onclick = () => {
          const input = document.createElement('input')
          input.type = 'file'
          input.onchange = () => {
            selectedFile = input.files?.[0] || null
            if (selectedFile) {
              fileNameSpan.textContent = selectedFile.name
              fileNameSpan.style.color = '#303133'
              setBtnState(btnConfirm, true)
            }
          }
          input.click()
        }
      } else {
        const urlInput = d.$('[data-role="url"]')
        // 已预填 URL，直接激活按钮
        if (linkUrl.trim()) setBtnState(btnConfirm, true)
        urlInput.addEventListener('input', () => setBtnState(btnConfirm, !!urlInput.value.trim()))
        // 回车确认
        urlInput.onkeydown = (e) => { if (e.key === 'Enter') btnConfirm.click() }
      }

      btnCancel.onclick = d.close

      btnConfirm.onclick = async () => {
        let text = textInput.value.trim()
        let newUrl = linkUrl

        if (fileMode) {
          if (!selectedFile && !linkUrl) return
          if (selectedFile) {
            try {
              const result = uploadFile && await uploadFile(selectedFile)
              if (!result || !result.url) return
              newUrl = result.url
              if (!text) text = result.filename || selectedFile.name
            } catch { return }
          }
          if (!text) text = newUrl.split('/').pop() || newUrl
        } else {
          let url = d.$('[data-role="url"]').value.trim()
          if (!url) return
          url = ensureProtocol(url)
          if (!text) text = url
          newUrl = url
        }

        d.close()
        // 选中整个超链节点后完整替换
        try {
          editor.restoreSelection()
          const linkEntry = SlateEditor.above(editor, {
            match: n => n.type === 'link',
          })
          if (linkEntry) {
            const [, linkPath] = linkEntry
            SlateTransforms.select(editor, {
              anchor: SlateEditor.start(editor, linkPath),
              focus: SlateEditor.end(editor, linkPath),
            })
            editor.deleteFragment()
            editor.insertNode({
              type: 'link',
              url: newUrl,
              children: [{ text }],
            })
            try { editor.move(1) } catch (e) {}
          }
        } catch {}
        onAfterEdit?.()
      }

      // 回车确认
      bindEnter([textInput], () => btnConfirm.click())
    }
  }
}

// ── 查看链接菜单（悬浮栏"查看链接"）──

function makeViewLinkMenu(prefix, opts) {
  const { onViewFileLink } = opts
  return class {
    constructor() {
      this.title = '查看链接'
      this.iconSvg = VIEW_ICON_SVG
      this.tag = 'button'
    }
    getValue() { return '' }
    isActive() { return false }
    isDisabled() { return false }
    exec(editor) {
      try {
        const sel = window.getSelection()
        if (!sel || !sel.anchorNode) return
        let el = sel.anchorNode
        while (el && el.nodeName !== 'A') el = el.parentElement
        if (!el) return
        const href = el.getAttribute('href') || ''
        if (!href) return
        // 文件链接 → 调用方自定义处理（需求：预览弹窗）；普通链接 → 新标签页
        if (onViewFileLink && onViewFileLink(editor, href)) return
        const fixed = ensureProtocol(href)
        window.open(fixed, '_blank', 'noopener')
      } catch {}
    }
  }
}

// ── 取消链接菜单（悬浮栏"取消链接"），替代内置 unLink ──

function makeUnLinkMenu(prefix, opts) {
  return class {
    constructor() {
      this.title = '取消链接'
      this.iconSvg = UNLINK_ICON_SVG
      this.tag = 'button'
    }
    getValue() { return '' }
    isActive() { return false }
    isDisabled() { return false }
    exec(editor) {
      try {
        editor.restoreSelection()
        SlateTransforms.unwrapNodes(editor, {
          match: n => n.type === 'link',
        })
      } catch {}
    }
  }
}

/**
 * 注册一套链接菜单（插入/编辑/查看/取消），返回各菜单键名。
 * 键名 = prefix + 菜单名，prefix 传 'req'（需求）/ 'comm'（任务沟通）等。
 * 重复注册同一键名会被 wangEditor 拒绝（Duplicated key），此处静默忽略，
 * 因此组件每次挂载（弹窗 destroy-on-close 重建）调用是安全的。
 */
export function registerLinkMenus(prefix = 'comm', opts = {}) {
  const defs = [
    { key: `${prefix}InsertLink`, factory: () => new (makeInsertLinkMenu(prefix, opts))() },
    { key: `${prefix}EditLink`, factory: () => new (makeEditLinkMenu(prefix, opts))() },
    { key: `${prefix}ViewLink`, factory: () => new (makeViewLinkMenu(prefix, opts))() },
    { key: `${prefix}UnLink`, factory: () => new (makeUnLinkMenu(prefix, opts))() },
  ]
  for (const def of defs) {
    try {
      Boot.registerMenu(def)
    } catch (e) {
      // 预期：重复注册时抛 "Duplicated key" — 忽略即可，无需重新注册
      if (e.message && !e.message.includes('Duplicated key')) throw e
    }
  }
  return {
    insertLink: `${prefix}InsertLink`,
    editLink: `${prefix}EditLink`,
    viewLink: `${prefix}ViewLink`,
    unLink: `${prefix}UnLink`,
  }
}
