<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import {
  FileText, FolderOpen, Search, Settings,
  Upload, Copy, Clipboard, CheckCircle2,
  FileEdit, Sparkles, RefreshCw,
  Database, Trash2, Bold, Italic,
  Underline, AlignLeft, AlignCenter, AlignRight,
  Image, Table as TableIcon, List, ListOrdered, Zap,
  Strikethrough, Code, Minus, Undo, Redo,
  Highlighter, LetterText, Save, Plus
} from 'lucide-vue-next'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import ImageExtension from '@tiptap/extension-image'
import { Table, TableRow, TableCell, TableHeader } from '@tiptap/extension-table'
import UnderlineExtension from '@tiptap/extension-underline'
import TextAlign from '@tiptap/extension-text-align'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import Highlight from '@tiptap/extension-highlight'
import { Color } from '@tiptap/extension-color'
import { TextStyle } from '@tiptap/extension-text-style'
import { FontFamily } from '@tiptap/extension-font-family'
import HorizontalRule from '@tiptap/extension-horizontal-rule'

import { apiUrl, getErrMsg } from '@/utils/api'
import type { DocRecord, CategoryDef } from '@/types'
import type { ImageLibRecord } from '@/composables/useImageLibrary'
import type { DocSection } from '@/utils/doc-sections'
import { AIExtension } from '@/extensions/AIIteration'

import { useBackend } from '@/composables/useBackend'
import { useDocuments } from '@/composables/useDocuments'
import { useAI } from '@/composables/useAI'
import { useKnowledgeBase } from '@/composables/useKnowledgeBase'
import { useExcel } from '@/composables/useExcel'
import { useTools } from '@/composables/useTools'
import { useSettings } from '@/composables/useSettings'
import { useTheme } from '@/composables/useTheme'
import { usePrompts } from '@/composables/usePrompts'
import { useImageLibrary } from '@/composables/useImageLibrary'

// 已通知的提醒 ID 集合（防止重复弹窗）
const notifiedReminderIds = new Set<string>()
let reminderPollTimer: ReturnType<typeof setInterval> | null = null

const pollReminders = async () => {
  try {
    const r = await axios.get(apiUrl('/api/reminders/due'))
    if (r.data.success && r.data.data) {
      for (const rem of r.data.data) {
        if (!notifiedReminderIds.has(rem.id)) {
          notifiedReminderIds.add(rem.id)
          // 使用浏览器 Notification API
          if ('Notification' in window) {
            if (Notification.permission === 'granted') {
              new Notification('计划提醒', { body: rem.content })
            } else if (Notification.permission !== 'denied') {
              const perm = await Notification.requestPermission()
              if (perm === 'granted') {
                new Notification('计划提醒', { body: rem.content })
              }
            }
          }
          // 兜底：使用 alert 风格的 ElMessage
          ElMessage.info(`⏰ 计划提醒: ${rem.content}`)
        }
      }
    }
  } catch { /* */ }
}

import NewDraftDialog from '@/components/dialogs/NewDraftDialog.vue'
import ImageDialog from '@/components/dialogs/ImageDialog.vue'
import ImitateDialog from '@/components/dialogs/ImitateDialog.vue'
import PromptDialog from '@/components/dialogs/PromptDialog.vue'
import SettingsDialog from '@/components/dialogs/SettingsDialog.vue'
import KBDialog from '@/components/dialogs/KBDialog.vue'
import KBSearchPanel from '@/components/dialogs/KBSearchPanel.vue'
import KBProjectDialog from '@/components/dialogs/KBProjectDialog.vue'
import KBDocNoteDialog from '@/components/dialogs/KBDocNoteDialog.vue'
import KBBackupDialog from '@/components/dialogs/KBBackupDialog.vue'
import KBVocabDialog from '@/components/dialogs/KBVocabDialog.vue'
import KBChunkSizeDialog from '@/components/dialogs/KBChunkSizeDialog.vue'
import KBBatchImportDialog from '@/components/dialogs/KBBatchImportDialog.vue'
import ToolsDialog from '@/components/dialogs/ToolsDialog.vue'
import ImageToolDialog from '@/components/dialogs/ImageToolDialog.vue'
import QualityCheckDialog from '@/components/dialogs/QualityCheckDialog.vue'
import AIIterationPanel from '@/components/panels/AIIterationPanel.vue'

// --- Composables ---
const activeCategory = ref('doc')
const categories: CategoryDef[] = [
  { id: 'doc', label: '文档库', icon: 'FileText' },
  { id: 'imitation', label: '仿写库', icon: 'Sparkles' },
  { id: 'excel', label: '配置表', icon: 'TableIcon' },
  { id: 'draft', label: '草稿', icon: 'FileEdit' },
  { id: 'image', label: '图片', icon: 'Image' },
]

const backend = useBackend()
const docs = useDocuments(activeCategory)
const ai = useAI()
const kb = useKnowledgeBase()
const excel = useExcel()
const tools = useTools()
const settings = useSettings(ai.models)
const theme = useTheme()
const prompts = usePrompts()
const imageLib = useImageLibrary()

// --- Image search ---
const imageSearchQuery = ref('')
const searchQuery = computed({
  get: () => activeCategory.value === 'image' ? imageSearchQuery.value : docs.searchQuery.value,
  set: (val: string) => {
    if (activeCategory.value === 'image') imageSearchQuery.value = val
    else docs.searchQuery.value = val
  },
})
const filteredImages = computed(() => {
  const q = imageSearchQuery.value.toLowerCase().trim()
  if (!q) return imageLib.images.value
  return imageLib.images.value.filter((img: ImageLibRecord) => img.name.toLowerCase().includes(q))
})

// --- Draft state ---
const showNewDraftDialog = ref(false)
const isDraftEditing = ref(false)
const currentDraftCat = ref('draft')

// --- Image dialog ---
const showImagePrompt = ref(false)

// --- Imitate dialog ---
const showImitateDialog = ref(false)

// KB 检索面板快捷键
const showSearchPanel = ref(false)

// KB 子对话框
const showKBProjectDialog = ref(false)
const showDocNoteDialog = ref(false)
const editingDocId = ref('')
const editingDocNote = ref('')
const showBackupDialog = ref(false)
const showVocabDialog = ref(false)
const showChunkSizeDialog = ref(false)
const showBatchImportDialog = ref(false)
const handleKeydown = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
    // 如果编辑器或输入框在焦点中，不拦截
    const tag = (e.target as HTMLElement)?.tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable) return
    e.preventDefault()
    showSearchPanel.value = !showSearchPanel.value
  }
}

// --- Image tool dialog ---
const showImageToolDialog = ref(false)
const libraryEditImageUri = ref('')

// --- AI iteration state ---
const aiResultTab = ref<'result' | 'chat'>('result')
const currentSectionTitle = ref('')
const currentDocSection = computed<DocSection | null>(() => {
  if (!tiptapEditor.value) return null
  return null  // runtime computed from cursor in handleAIModify
})
const hasSelection = ref(false)
const designPromptTemplate = computed(() => {
  const designer = prompts.professionsFull.value.find((p: any) => p.id === 'designer')
  return designer?.prompts?.[0]?.content || ''
})
watch(showImageToolDialog, (v) => { if (!v) libraryEditImageUri.value = '' })

// 监听编辑器选区变化
watch(() => tiptapEditor.value?.state.selection, () => {
  if (!tiptapEditor.value) return
  const { from, to } = tiptapEditor.value.state.selection
  hasSelection.value = from !== to
}, { deep: true })

// --- Context menu ---
const ctxMenu = ref({ visible: false, x: 0, y: 0, doc: null as DocRecord | null })
const closeCtxMenu = () => { ctxMenu.value.visible = false }
const excelCellBlur = (e: KeyboardEvent) => (e.target as HTMLElement)?.blur()

// --- Quality check dialog ---
const showQualityCheckDialog = ref(false)
const pendingQCDoc = ref<DocRecord | null>(null)

const showCtxMenu = (e: MouseEvent, doc: DocRecord) => {
  ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, doc }
}

// --- Image library context menu ---
const imgCtxMenu = ref({ visible: false, x: 0, y: 0, image: null as any })
const closeImgCtxMenu = () => { imgCtxMenu.value.visible = false }
const showImgCtxMenu = (e: MouseEvent, img: any) => {
  imgCtxMenu.value = { visible: true, x: e.clientX, y: e.clientY, image: img }
}
const handleImageCommand = async (command: string, img: any) => {
  closeImgCtxMenu()
  if (command === 'saveAs') {
    const api = (window as any).electronAPI
    if (api?.saveFileAs) {
      const dataUri = await imageLib.getImageData(img.id)
      if (dataUri) await api.saveFileAs(dataUri, img.name || 'image.png')
      else ElMessage.warning('获取图片失败')
    } else {
      const a = document.createElement('a')
      const dataUri = await imageLib.getImageData(img.id)
      if (dataUri) { a.href = dataUri; a.download = img.name || 'image.png'; a.click() }
    }
  } else if (command === 'delete') {
    await ElMessageBox.confirm(`确定删除图片「${img.name}」吗？`, '提示', { type: 'warning' })
    await imageLib.deleteImage(img.id)
  } else if (command === 'rename') {
    const { value: newName } = await ElMessageBox.prompt('请输入新名称', '重命名', { inputValue: img.name })
    if (newName) await imageLib.renameImage(img.id, newName.trim())
  } else if (command === 'edit') {
    const dataUri = await imageLib.getImageData(img.id)
    if (dataUri) {
      showImageToolDialog.value = true
      libraryEditImageUri.value = dataUri
    } else {
      ElMessage.warning('获取图片失败')
    }
  }
}

const handleImageClick = async (img: any) => {
  const dataUri = await imageLib.getImageData(img.id)
  if (dataUri) {
    showImageToolDialog.value = true
    libraryEditImageUri.value = dataUri
  }
}

// --- Image upload ---
const isUploading = ref(false)
const uploadImage = (file: File) => {
  if (!file.type.startsWith('image/')) { ElMessage.warning('请选择图片文件'); return }
  isUploading.value = true
  const reader = new FileReader()
  reader.onload = async () => {
    const dataUri = reader.result as string
    try {
      await imageLib.saveImage(dataUri, file.name.replace(/\.[^.]+$/, '') || '未命名图片')
      ElMessage.success('已上传')
    } catch (e: any) {
      ElMessage.error('上传失败: ' + getErrMsg(e))
    } finally {
      isUploading.value = false
    }
  }
  reader.onerror = () => { ElMessage.error('读取文件失败'); isUploading.value = false }
  reader.readAsDataURL(file)
}
const dragOverFlag = ref(false)
const onImageDragOver = (e: DragEvent) => { e.preventDefault(); dragOverFlag.value = true }
const onImageDragLeave = () => { dragOverFlag.value = false }
const onImageDrop = (e: DragEvent) => {
  e.preventDefault()
  dragOverFlag.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) uploadImage(file)
}

// --- Editor dirty / auto-save ---
const editorDirty = ref(false)
const saveStatus = ref<'saved' | 'unsaved'>('saved')
let saveTimer: any = null

// 显式保存当前文档
const saveCurrentDoc = async () => {
  if (!docs.currentDoc.value.id) return
  saveStatus.value = 'saved'
  try {
    await axios.post(apiUrl(`/api/documents/save-file/${docs.currentDoc.value.id}`), {
      content: docs.currentDoc.value.content
    })
    editorDirty.value = false
  } catch { /* */ }
}

// --- Tiptap ---
const fontSize = ref('16px')
const fontSizes = ['12px', '14px', '16px', '18px', '20px', '24px', '28px', '36px']
const fontColor = ref('#000000')
const highlightColor = ref('#ffff00')

const tiptapEditor = useEditor({
  extensions: [
    StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
    ImageExtension.configure({ allowBase64: true, inline: false }),
    Table.configure({ resizable: true }),
    TableRow as any, TableCell as any, TableHeader as any,
    UnderlineExtension, TextStyle,
    FontFamily.configure({ types: ['textStyle'] }) as any,
    Color.configure({ types: ['textStyle'] }) as any,
    Highlight.configure({ multicolor: true }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
    Link.configure({ openOnClick: false }),
    HorizontalRule,
    Placeholder.configure({ placeholder: '开始编辑文档内容...' }),
    AIExtension.configure({
      onModifySection: (title: string) => {
        aiResultTab.value = 'chat'
        currentSectionTitle.value = title
      },
    }),
  ],
  editable: true,
  onUpdate: ({ editor }) => {
    editorDirty.value = true
    saveStatus.value = 'unsaved'
    docs.currentDoc.value.content = editor.getHTML()
  },
  editorProps: {
    attributes: {
      class: 'prose prose-zinc max-w-none focus:outline-none min-h-[400px] text-base leading-relaxed'
    }
  }
})

// Watch doc changes → load into editor
watch(() => docs.currentDoc.value.id, async (newId) => {
  if (!tiptapEditor.value) return
  if (!newId) { tiptapEditor.value.commands.setContent('') }
  else {
    // Excel 文件不加载文档内容到编辑器
    const ext = (docs.currentDoc.value.name || '').split('.').pop()?.toLowerCase() || ''
    if (['xlsx', 'xls'].includes(ext) || docs.currentDoc.value.category === 'excel') return
    try {
      const res = await axios.get(apiUrl(`/api/documents/${newId}`))
      if (res.data.success) {
        const c = res.data.data.content || ''
        const isHtml = /<\/?\w+[^>]*>/.test(c)
        docs.currentDoc.value.content = c
        if (isHtml) tiptapEditor.value.commands.setContent(c)
        else tiptapEditor.value.commands.setContent(`<p>${c.replace(/\n/g, '</p><p>')}</p>`)
        saveStatus.value = 'saved'
        editorDirty.value = false
      }
    } catch { /* */ }
  }
})

// Auto-save
watch(editorDirty, (dirty) => {
  if (!dirty || !docs.currentDoc.value.id) return
  clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    try {
      await axios.put(apiUrl(`/api/documents/${docs.currentDoc.value.id}`), {
        content: docs.currentDoc.value.content
      })
      editorDirty.value = false
    } catch { /* */ }
  }, 1500)
})

// --- Toolbar actions ---
const isExcelMode = computed(() => !!excel.excelData.value)
const setHeading = (level: 1 | 2 | 3) => tiptapEditor.value?.chain().focus().toggleHeading({ level }).run()
const toggleBold = () => {
  if (isExcelMode.value) excel.toggleBold()
  else tiptapEditor.value?.chain().focus().toggleBold().run()
}
const toggleItalic = () => {
  if (isExcelMode.value) excel.toggleItalic()
  else tiptapEditor.value?.chain().focus().toggleItalic().run()
}
const toggleUnderline = () => {
  if (isExcelMode.value) excel.toggleUnderline()
  else tiptapEditor.value?.chain().focus().toggleUnderline().run()
}
const toggleStrikethrough = () => {
  if (isExcelMode.value) excel.toggleStrikethrough()
  else tiptapEditor.value?.chain().focus().toggleStrike().run()
}
const toggleCode = () => tiptapEditor.value?.chain().focus().toggleCode().run()
const toggleCodeBlock = () => tiptapEditor.value?.chain().focus().toggleCodeBlock().run()
const toggleBlockquote = () => tiptapEditor.value?.chain().focus().toggleBlockquote().run()
const toggleBullet = () => tiptapEditor.value?.chain().focus().toggleBulletList().run()
const toggleOrdered = () => tiptapEditor.value?.chain().focus().toggleOrderedList().run()
const setAlign = (align: string) => {
  if (isExcelMode.value) excel.setCellTextAlign(align as 'left' | 'center' | 'right')
  else tiptapEditor.value?.chain().focus().setTextAlign(align).run()
}
const setFontSize = (size: string) => {
  if (isExcelMode.value) excel.setCellFontSize(parseInt(size))
  else { fontSize.value = size; tiptapEditor.value?.chain().focus().setMark('textStyle', { fontSize: size }).run() }
}
const setFontFamily = (font: string) => {
  if (isExcelMode.value) excel.setCellFontFamily(font)
  else tiptapEditor.value?.chain().focus().setFontFamily(font).run()
}
const setColor = (color: string) => {
  if (isExcelMode.value) excel.setCellTextColor(color)
  else { fontColor.value = color; tiptapEditor.value?.chain().focus().setColor(color).run() }
}
const setHighlight = (color: string) => {
  if (isExcelMode.value) { excel.excelFillColor.value = color; excel.applyColorToSelection() }
  else { highlightColor.value = color; tiptapEditor.value?.chain().focus().setHighlight({ color }).run() }
}
const clearMarks = () => {
  if (isExcelMode.value) excel.clearCellFormat()
  else tiptapEditor.value?.chain().focus().clearNodes().unsetAllMarks().run()
}
const insertTable = () => tiptapEditor.value?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
const insertHr = () => tiptapEditor.value?.chain().focus().setHorizontalRule().run()
const undoAction = () => {
  if (isExcelMode.value) excel.undo()
  else tiptapEditor.value?.chain().focus().undo().run()
}
const redoAction = () => {
  if (isExcelMode.value) excel.redo()
  else tiptapEditor.value?.chain().focus().redo().run()
}
const isBold = () => tiptapEditor.value?.isActive('bold')
const isItalic = () => tiptapEditor.value?.isActive('italic')
const isUnderline = () => tiptapEditor.value?.isActive('underline')
const isStrike = () => tiptapEditor.value?.isActive('strike')
const isCode = () => tiptapEditor.value?.isActive('code')
const isCodeBlock = () => tiptapEditor.value?.isActive('codeBlock')
const isBlockquote = () => tiptapEditor.value?.isActive('blockquote')
const isH1 = () => tiptapEditor.value?.isActive('heading', { level: 1 })
const isH2 = () => tiptapEditor.value?.isActive('heading', { level: 2 })
const isH3 = () => tiptapEditor.value?.isActive('heading', { level: 3 })
const isBullet = () => tiptapEditor.value?.isActive('bulletList')
const isOrdered = () => tiptapEditor.value?.isActive('orderedList')

const insertImageFromUrl = (url: string) => {
  tiptapEditor.value?.chain().focus().setImage({ src: url, alt: url }).run()
}

// --- Document operations ---
const switchCategory = async (catId: string) => {
  activeCategory.value = catId
  docs.currentDoc.value = { id: '', name: '未选择文档', content: '', type: '', path: '', category: '' }
  ai.aiResult.value = ''
  excel.reset()
  if (catId === 'image') {
    await imageLib.loadImages()
  } else {
    await docs.loadDocuments(catId)
  }
}

const selectDoc = async (doc: DocRecord) => {
  const ext = (doc.name || '').split('.').pop()?.toLowerCase() || ''
  const isExcel = ['xlsx', 'xls'].includes(ext) || doc.category === 'excel'
  if (isExcel) {
    // Excel 文件无需加载文档 HTML 内容，直接设置当前文档
    docs.currentDoc.value = { ...doc, content: '' }
    await excel.loadExcelData(doc)
  } else {
    await docs.selectDoc(doc)
  }
  ai.aiResult.value = ''
}

const handleDocCommand = async (command: string, doc: DocRecord) => {
  closeCtxMenu()
  if (command === 'delete') {
    try {
      await ElMessageBox.confirm(`确定删除文档 ${doc.name} 吗？`, '提示', { type: 'warning' })
      await docs.deleteDocument(doc)
      ai.aiResult.value = ''
      ElMessage.success('已删除')
    } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败') }
  } else if (command === 'saveAs') {
    const isExcel = doc.category === 'excel' || ['xlsx', 'xls'].includes((doc.name || '').split('.').pop()?.toLowerCase() || '')
    const api = (window as any).electronAPI
    if (!api?.saveFileAs) { ElMessage.warning('仅桌面应用可用'); return }
    if (isExcel) {
      try {
        // 确保文档已加载且 Excel 数据就绪
        if (docs.currentDoc.value.id !== doc.id) await selectDoc(doc)
        if (!excel.excelData.value) {
          // selectDoc 可能静默失败，主动尝试加载
          await excel.loadExcelData(doc)
        }
        if (!excel.excelData.value) {
          ElMessage.warning('无法加载表格数据，请先点击该文档打开后再试')
          return
        }
        const dataUri = await excel.saveToFile(doc)
        const defaultName = (doc.name || '表格').replace(/\.[^/.]+$/, '') + '.xlsx'
        const result = await api.saveFileAs(dataUri, defaultName)
        if (result?.success) ElMessage.success('已保存至 ' + (result.filePath || ''))
        else if (result?.error && result.error !== 'Canceled') ElMessage.error('保存失败: ' + result.error)
      } catch (e: any) {
        ElMessage.error('保存失败: ' + (e?.message || String(e)))
      }
      return
    }
    const baseName = (doc.name || '文档').replace(/\.[^/.]+$/, '')
    // 确保文档内容已加载（未左键点击过的文档需要先加载）
    if (docs.currentDoc.value.id !== doc.id) await selectDoc(doc)
    const htmlContent = tiptapEditor.value?.getHTML() || docs.currentDoc.value.content || ''
    if (!htmlContent.trim()) { ElMessage.error('文档内容为空'); return }
    try {
      const genRes = await axios.post(apiUrl('/api/documents/generate-file'), { name: baseName + '.docx', content: htmlContent, type: 'docx' })
      if (genRes.data?.success && genRes.data?.data_uri) {
        const result = await api.saveFileAs(genRes.data.data_uri, baseName + '.docx')
        if (result?.success) ElMessage.success('已保存至 ' + (result.filePath || ''))
        else if (result?.error && result.error !== 'Canceled') ElMessage.error('保存失败: ' + result.error)
      } else { ElMessage.error('文件生成失败') }
    } catch (e: any) { ElMessage.error('生成失败: ' + (e?.message || String(e))) }
  } else if (command === 'rename') {
    try {
      const { value: newName } = await ElMessageBox.prompt('输入新文件名：', '重命名', { inputValue: doc.name })
      if (newName && newName.trim() && newName !== doc.name) {
        await docs.renameDocument(doc, newName.trim())
        ElMessage.success('已重命名')
      }
    } catch { /* */ }
  } else if (command === 'qualityCheck') {
    pendingQCDoc.value = doc
    showQualityCheckDialog.value = true
  }
}

const handleQualityCheckSubmit = async (referenceContent: string, configDescription: string) => {
  const doc = pendingQCDoc.value
  if (!doc) return
  pendingQCDoc.value = null

  let targetContent = docs.currentDoc.value?.id === doc.id
    ? (tiptapEditor.value?.getText() || docs.currentDoc.value.content || '')
    : (doc.content || '')

  // 如果内容为空，主动从后端拉取完整文档内容
  if (!targetContent) {
    try {
      const r = await axios.get(apiUrl(`/api/documents/${doc.id}`))
      targetContent = r.data?.data?.content || ''
    } catch { /* */ }
  }

  if (!targetContent) {
    ElMessage.warning('该文档内容为空，请先在编辑器中写入内容后再进行质检')
    ai.isProcessing.value = false
    return
  }

  const pro = prompts.professionsFull.value.find(p => p.id === prompts.selectedImitationProfession.value)
  const qcPrompt = pro?.qualityCheckPrompt || ''

  ai.aiResult.value = ''
  ai.isProcessing.value = true

  try {
    // 构建显示标题
    let title = `【质检文档：${doc.name}】`
    if (pro) title += `\n【质检职业：${pro.name}】`
    if (referenceContent) title += `\n【参考文档：已上传】`
    if (configDescription) title += `\n【配置表说明：${configDescription.slice(0, 50)}${configDescription.length > 50 ? '...' : ''}】`

    const result = await ai.runQualityCheck(targetContent, qcPrompt, referenceContent, configDescription)
    if (result) {
      ai.aiResult.value = `${title}\n\n${result}`
      aiResultTab.value = 'result'
    } else {
      ElMessage.error('质检失败')
    }
  } catch (e: any) {
    ElMessage.error('质检请求失败: ' + (getErrMsg(e) || e.message || '未知错误'))
  } finally {
    ai.isProcessing.value = false
  }
}

// --- File upload / drop ---
const handleDrop = async (e: DragEvent) => {
  const file = e.dataTransfer?.files[0]
  if (!file) return
  const ext = file.name.split('.').pop()?.toLowerCase()
  const imageExts = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp']
  if (imageExts.includes(ext || '') || file.type.startsWith('image/')) {
    const reader = new FileReader()
    reader.onload = async () => {
      const dataUri = reader.result as string
      try {
        await imageLib.saveImage(dataUri, file.name.replace(/\.[^.]+$/, '') || '未命名图片')
        ElMessage.success('图片已上传')
        await switchCategory('image')
      } catch (e: any) {
        ElMessage.error('上传失败: ' + getErrMsg(e))
      }
    }
    reader.readAsDataURL(file)
    return
  }
  if (!['docx', 'md', 'txt', 'xlsx', 'xls'].includes(ext || '')) {
    ElMessage.warning('仅支持 docx, md, txt, xlsx 及图片格式'); return
  }
  await uploadFile(file)
}

const uploadFile = async (file: File) => {
  const result = await docs.uploadFile(file, activeCategory.value)
  if (result) {
    const targetCat = result.category
    if (targetCat !== activeCategory.value) {
      await switchCategory(targetCat)
    }
    await selectDoc(result)
    ElMessage.success('上传成功')
  } else {
    ElMessage.warning('上传失败')
  }
}

const handleUpload = () => {
  const input = document.createElement('input')
  input.type = 'file'
  if (activeCategory.value === 'image') {
    input.accept = 'image/*'
    input.onchange = async (e: any) => {
      const file = e.target.files[0]
      if (!file) return
      const reader = new FileReader()
      reader.onload = async () => {
        const dataUri = reader.result as string
        try {
          await imageLib.saveImage(dataUri, file.name.replace(/\.[^.]+$/, '') || '未命名图片')
          ElMessage.success('已上传')
        } catch (e: any) {
          ElMessage.error('上传失败: ' + getErrMsg(e))
        }
      }
      reader.readAsDataURL(file)
    }
  } else {
    input.accept = '.docx,.md,.txt,.xlsx,.xls'
    input.onchange = async (e: any) => { if (e.target.files[0]) await uploadFile(e.target.files[0]) }
  }
  input.click()
}

// --- Draft ---
const createNewDraft = async (name: string, type: string) => {
  const fileName = name + (type === 'excel' ? '.xlsx' : '.docx')
  const doc = await docs.createDocument(fileName, '', 'draft')
  if (doc) {
    await selectDoc(doc)
    isDraftEditing.value = true
    currentDraftCat.value = 'draft'
    if (type === 'excel') excel.initEmpty()
    ElMessage.success('已创建草稿，编辑后点击右上角「保存到分类」')
  }
}

const saveDraftToCategory = async () => {
  if (!docs.currentDoc.value.id || docs.currentDoc.value.category !== 'draft') {
    ElMessage.warning('请先选择草稿文档'); return
  }
  const isExcelDraft = excel.excelData.value !== null
  const targetCat = isExcelDraft ? 'excel' : 'doc'

  if (isExcelDraft) {
    const dataUri = await excel.saveToFile(docs.currentDoc.value)
    if (!dataUri) { ElMessage.error('保存失败'); return }
    await docs.updateDocument(docs.currentDoc.value.id, { content: dataUri, category: targetCat, name: docs.currentDoc.value.name })
  } else {
    const htmlContent = tiptapEditor.value?.getHTML() || docs.currentDoc.value.content || ''
    await docs.updateDocument(docs.currentDoc.value.id, { content: htmlContent, category: targetCat, name: docs.currentDoc.value.name })
  }

  docs.currentDoc.value.category = targetCat
  await docs.loadDocuments()
  await switchCategory(targetCat)
  ElMessage.success(`已保存到${isExcelDraft ? '配置表' : '文档库'}分类`)
}

// --- AI Operations ---
const openQualityCheckDialog = async () => {
  if (!docs.currentDoc.value.content || !docs.currentDoc.value.id) {
    ElMessage.warning('请先选择或上传一个文档'); return
  }
  await prompts.openPromptDialog()
}

const startQualityCheckWithPrompt = async () => {
  if (!prompts.selectedRole.value) { ElMessage.warning('请选择质检角色'); return }
  prompts.showPromptDialog.value = false
  ai.isProcessing.value = true
  ai.aiResult.value = ''

  const content = tiptapEditor.value?.getText() || docs.currentDoc.value.content || ''
  const result = await ai.runQualityCheck(content, prompts.selectedRole.value.prompt)
  if (result) ai.aiResult.value = `【质检角色：${prompts.selectedRole.value.name}】\n\n${result}`

  ai.isProcessing.value = false
}

const editingQualityCheckPrompt = ref('')
const selectedProfessionQualityCheckPrompt = computed(() => {
  const pro = prompts.professionsFull.value.find(p => p.id === prompts.selectedImitationProfession.value)
  return pro?.qualityCheckPrompt || ''
})
// Sync editing state when profession changes or data loads
watch(selectedProfessionQualityCheckPrompt, (val) => {
  editingQualityCheckPrompt.value = val
}, { immediate: true })

const saveQualityCheckPrompt = async (val: string) => {
  try {
    await axios.put(apiUrl(`/api/prompts/profession/${prompts.selectedImitationProfession.value}`), {
      qualityCheckPrompt: val
    })
    await prompts.loadProfessionsFull()
  } catch { /* */ }
}

const runImitateAndCreate = async (requirements: string, mindmapContent: string, templateContent: string, images: string[] = [], projectId = '', kbOnly = false, citeSources = false) => {
  showImitateDialog.value = false
  ai.isProcessing.value = true

  try {
    const content = await ai.runImitation(requirements, mindmapContent, true, 'html', templateContent, images, projectId, kbOnly, citeSources)
    if (!content) { ElMessage.warning('生成失败'); return }

    const title = ai.generateDocTitle(requirements)
    const doc = await docs.createDocument(title, content, 'imitation')
    if (doc) {
      selectDoc(doc)
      ai.aiResult.value = ''
      ElMessage.success('仿写完成，文档已创建，已通过自动质检')
    }
  } catch (e: any) { ElMessage.error('生成失败: ' + getErrMsg(e)) }
  finally { ai.isProcessing.value = false }
}

const runIteration = async () => {
  if (!ai.iterativePrompt.value.trim() || !ai.aiResult.value) return
  ai.isProcessing.value = true
  const prompt = ai.iterativePrompt.value
  ai.iterativePrompt.value = ''
  await ai.iterate(prompt)
  ai.isProcessing.value = false
}

// 处理 AI 修改请求（AIIterationPanel 提交）
const handleAIModify = async (instruction: string) => {
  if (!tiptapEditor.value || !instruction.trim()) return
  const fullDoc = tiptapEditor.value.getHTML()
  const { from, to } = tiptapEditor.value.state.selection
  const isSelection = from !== to

  let mode: 'section' | 'selection' | 'full' = 'full'
  let targetSection = ''
  let selectionContext = undefined

  if (isSelection) {
    mode = 'selection'
    const selected = tiptapEditor.value.state.doc.textBetween(from, to)
    const before = tiptapEditor.value.state.doc.textBetween(Math.max(0, from - 200), from)
    const after = tiptapEditor.value.state.doc.textBetween(to, Math.min(tiptapEditor.value.state.doc.content.size, to + 200))
    selectionContext = { selected, before, after }
  } else if (currentSectionTitle.value) {
    mode = 'section'
    targetSection = currentSectionTitle.value
  }

  const result = await ai.runIteration(fullDoc, instruction, mode, targetSection, selectionContext, kb.activeProjectId.value)
  if (result) {
    if (mode === 'selection' && selectionContext) {
      tiptapEditor.value.chain().focus().deleteSelection().insertContent(result).run()
    } else if (mode === 'section' && targetSection) {
      const { parseHtmlSections, replaceSectionInEditor } = await import('@/utils/doc-sections')
      const sections = parseHtmlSections(fullDoc)
      const sec = sections.find(s => s.title === targetSection)
      if (sec) replaceSectionInEditor(tiptapEditor.value, sec, result)
    } else {
      tiptapEditor.value.commands.setContent(result)
    }
    ElMessage.success('修改完成')
  } else {
    ElMessage.warning('修改失败，请重试')
  }
  currentSectionTitle.value = ''
}

const runLogicCompletion = async () => {
  if (!docs.currentDoc.value.content || !docs.currentDoc.value.id) {
    ElMessage.warning('请先选择草稿文档'); return
  }
  ai.isProcessing.value = true
  ai.aiResult.value = ''
  const content = tiptapEditor.value?.getText() || docs.currentDoc.value.content || ''
  const result = await ai.runLogicCompletion(content)
  if (result) ai.aiResult.value = result
  ai.isProcessing.value = false
}

const copyResult = () => {
  if (ai.aiResult.value) {
    navigator.clipboard.writeText(ai.aiResult.value)
    ElMessage.success('已复制')
  }
}

const clearResult = async () => {
  if (!ai.aiResult.value) return
  try {
    await ElMessageBox.confirm('确定清除AI分析结果？', '确认', { type: 'warning' })
    ai.aiResult.value = ''
    ai.iterativePrompt.value = ''
  } catch { /* */ }
}

// --- KB handlers ---
const handleKBUpload = async (file: File, folderId?: string, fileIndex?: number, totalFiles?: number) => {
  const ok = await kb.uploadFile(file, folderId, fileIndex, totalFiles)
  if (ok) ElMessage.success('入库成功')
  else ElMessage.warning('入库失败')
}

const handleKBUploadFiles = async (files: File[]) => {
  const total = files.length
  for (let i = 0; i < total; i++) {
    const ok = await kb.uploadFile(files[i], kb.activeFolderFilter.value || undefined, i, total)
    if (ok && i === total - 1) ElMessage.success(`全部入库完成（${total} 个）`)
  }
}

const handleKBClear = async (folderId?: string) => {
  try {
    await ElMessageBox.confirm('是否清除该目录下文档？', '确认清除', {
      confirmButtonText: '确定删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await kb.clearAll(folderId || undefined)
    ElMessage.success('已清除')
  } catch { /* cancelled */ }
}

const handleKBDelete = async (docId: string) => {
  try {
    await ElMessageBox.confirm('确定删除？', '提示', { type: 'warning' })
    await kb.deleteDocument(docId)
    ElMessage.success('已删除')
  } catch { /* */ }
}

const handleOpenNoteDialog = (docId: string) => {
  const doc = kb.documents.value.find(d => d.id === docId)
  editingDocId.value = docId
  editingDocNote.value = doc?.note || ''
  showDocNoteDialog.value = true
}

const handleSaveNote = async (docId: string, note: string) => {
  await kb.updateDocument(docId, { note })
  showDocNoteDialog.value = false
}

const handleBatchImport = async (files: { path: string; folderId?: string }[]) => {
  const r = await axios.post(apiUrl(`/api/kb/project/${kb.activeProjectId.value}/import-files`), { files })
  if (r.data.success) {
    const d = r.data.data
    ElMessage.success(`导入完成: ${d.succeeded || 0}/${d.total} 个成功`)
    await Promise.all([kb.loadDocuments(), kb.loadStats()])
  } else {
    ElMessage.warning(r.data.message || '批量导入失败')
  }
}

// --- Tools handlers ---
const handleAddSvn = async () => {
  const folderPath = await tools.selectFolder()
  if (folderPath) {
    tools.newSvnPath.value = folderPath
    await tools.addSvn(folderPath)
  }
}

const handleRunSvnUpdate = async (item: { id: string; name: string; path: string }) => {
  await tools.runSvnUpdate(item, settings.tortoiseSvnPath.value)
}

// --- Init ---
onMounted(async () => {
  document.addEventListener('click', closeCtxMenu)
  document.addEventListener('keydown', handleKeydown)
  await backend.waitForReady()
  const api = (window as any).electronAPI
  if (api?.getAutoStartStatus) settings.autoStart.value = await api.getAutoStartStatus()
  await docs.loadDocuments()
  await settings.loadConfig()
  await theme.loadFromConfig()
  try {
    const r = await axios.get(apiUrl('/api/tools/config'))
    if (r.data.success) {
      tools.svnConfigs.value = r.data.data.svn || []
      tools.navConfigs.value = r.data.data.nav || []
    }
  } catch { /* */ }
  // 启动提醒轮询（每30秒检查一次）
  reminderPollTimer = setInterval(pollReminders, 30000)
  pollReminders()
  // 请求通知权限
  if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission()
  }
})

onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  if (reminderPollTimer) clearInterval(reminderPollTimer)
  tiptapEditor.value?.destroy()
  document.removeEventListener('click', closeCtxMenu)
  document.removeEventListener('keydown', handleKeydown)
})

const formatDate = (ts: number) => new Date(ts * 1000).toLocaleString()

const openSettings = () => settings.openSettings(() => prompts.loadProfessionsFull())
</script>

<template>
  <div class="flex h-screen bg-app overflow-hidden font-sans text-app">
    <!-- Left Sidebar -->
    <div class="w-80 border-r border-app bg-surface flex flex-col shrink-0">
      <div class="p-4 border-b border-app-light">
        <div class="flex items-center gap-1 mb-3">
          <h2 class="font-bold text-lg flex items-center gap-2 flex-1"><FolderOpen class="w-5 h-5 text-app-primary" />文档</h2>
          <el-button type="primary" size="small" plain @click="handleUpload"><template #icon><Upload class="w-4 h-4" /></template>上传</el-button>
          <el-button v-if="activeCategory !== 'image'" link @click="kb.openKB()"><Database class="w-4 h-4 text-app-muted" /></el-button>
          <el-button link @click="openSettings"><Settings class="w-4 h-4 text-app-muted" /></el-button>
        </div>
        <el-input v-model="searchQuery" placeholder="搜索..." :prefix-icon="Search" size="small" clearable />
      </div>
      <div class="px-2 pt-2 pb-2 flex-1 overflow-y-auto" @click="closeCtxMenu(), closeImgCtxMenu()">
        <div class="flex gap-1 mb-3 border-b border-app-light pb-2">
          <button
            v-for="cat in categories" :key="cat.id" @click="switchCategory(cat.id)"
            :class="['flex-1 text-xs font-medium py-1.5 px-1 rounded transition-colors', activeCategory === cat.id ? 'bg-primary-light text-app-primary' : 'text-app-muted hover:text-app-secondary']"
          >{{ cat.label }}</button>
        </div>

        <!-- 文档列表 -->
        <template v-if="activeCategory !== 'image'">
          <div v-if="activeCategory === 'draft'" class="mb-2">
            <el-button size="small" plain class="w-full text-xs" @click="showNewDraftDialog = true">+ 新建草稿</el-button>
          </div>
          <div class="space-y-0.5">
            <div
              v-for="doc in docs.filteredDocList.value" :key="doc.id"
              @click="selectDoc(doc)"
              @contextmenu.prevent.stop="showCtxMenu($event, doc)"
              :class="['flex items-center gap-2 p-2 rounded-md cursor-pointer transition-colors text-sm w-full', docs.currentDoc.value.id === doc.id ? 'bg-primary-light text-app-primary' : 'hover:bg-app-hover text-app-secondary']"
            >
              <span class="w-4 h-4 shrink-0 flex items-center justify-center">
                <template v-if="(doc.category||'doc')==='imitation'"><Sparkles class="w-3.5 h-3.5 text-purple-500" /></template>
                <template v-else-if="(doc.category||'doc')==='excel'"><TableIcon class="w-3.5 h-3.5 text-green-500" /></template>
                <template v-else-if="(doc.category||'doc')==='draft'"><FileEdit class="w-3.5 h-3.5 text-orange-400" /></template>
                <template v-else><FileText class="w-3.5 h-3.5 text-blue-500" /></template>
              </span>
              <span class="truncate flex-1 text-left">{{ doc.name }}</span>
            </div>
            <div v-if="docs.filteredDocList.value.length === 0" class="text-center text-app-muted py-6 text-sm">
              {{ docs.searchQuery.value ? '无匹配文档' : (activeCategory === 'draft' ? '暂无草稿，点击上方新建' : '暂无文档') }}
            </div>
          </div>
        </template>

        <!-- 图片库 -->
        <template v-else>
          <div
            class="space-y-1 min-h-[100px]"
            :class="dragOverFlag ? 'ring-2 ring-primary rounded-lg ring-inset bg-primary/5' : ''"
            @dragover="onImageDragOver"
            @dragleave="onImageDragLeave"
            @drop="onImageDrop"
          >
            <div v-if="dragOverFlag" class="flex items-center justify-center h-20 text-sm text-primary">
              释放以上传图片
            </div>
            <div
              v-for="img in filteredImages" :key="img.id"
              @click="handleImageClick(img)"
              @contextmenu.prevent.stop="showImgCtxMenu($event, img)"
              class="flex items-center gap-2 p-1.5 rounded-md cursor-pointer transition-colors text-sm hover:bg-app-hover text-app-secondary"
            >
              <span class="w-8 h-8 shrink-0 rounded overflow-hidden bg-gray-100 flex items-center justify-center text-xs text-app-muted">
                <Image class="w-4 h-4" />
              </span>
              <span class="truncate flex-1 text-left">{{ img.name }}</span>
            </div>
            <div v-if="filteredImages.length === 0 && imageSearchQuery" class="text-center text-app-muted py-6 text-sm">
              无匹配图片
            </div>
            <div v-else-if="imageLib.images.value.length === 0" class="text-center text-app-muted py-6 text-sm">
              暂无图片，可上传图片或使用图片工具生成
            </div>
          </div>
        </template>

        <!-- Doc context menu -->
        <Teleport to="body">
          <div v-if="ctxMenu.visible"
            class="fixed z-[9999] bg-surface rounded-lg shadow-xl border border-app py-1 min-w-[160px]"
            :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
            @click.stop
          >
            <button class="w-full px-3 py-2 text-sm text-left hover:bg-app-hover flex items-center gap-2" @click="handleDocCommand('saveAs', ctxMenu.doc!)"><Save class="w-3.5 h-3.5" />另存为...</button>
            <button class="w-full px-3 py-2 text-sm text-left hover:bg-app-hover flex items-center gap-2" @click="handleDocCommand('qualityCheck', ctxMenu.doc!)"><CheckCircle2 class="w-3.5 h-3.5 text-green-600" />文档质检</button>
            <button class="w-full px-3 py-2 text-sm text-left hover:bg-app-hover flex items-center gap-2" @click="handleDocCommand('rename', ctxMenu.doc!)"><FileEdit class="w-3.5 h-3.5 text-orange-500" />重命名</button>
            <div class="border-t border-app-light my-1" />
            <button class="w-full px-3 py-2 text-sm text-left text-red-500 hover:bg-red-50 flex items-center gap-2" @click="handleDocCommand('delete', ctxMenu.doc!)"><Trash2 class="w-3.5 h-3.5" />删除文档</button>
          </div>
        </Teleport>

        <!-- Image context menu -->
        <Teleport to="body">
          <div v-if="imgCtxMenu.visible"
            class="fixed z-[9999] bg-surface rounded-lg shadow-xl border border-app py-1 min-w-[160px]"
            :style="{ left: imgCtxMenu.x + 'px', top: imgCtxMenu.y + 'px' }"
            @click.stop
          >
            <button class="w-full px-3 py-2 text-sm text-left hover:bg-app-hover flex items-center gap-2" @click="handleImageCommand('saveAs', imgCtxMenu.image)"><Save class="w-3.5 h-3.5" />另存为...</button>
            <button class="w-full px-3 py-2 text-sm text-left hover:bg-app-hover flex items-center gap-2" @click="handleImageCommand('edit', imgCtxMenu.image)"><FileEdit class="w-3.5 h-3.5 text-orange-500" />修改</button>
            <button class="w-full px-3 py-2 text-sm text-left hover:bg-app-hover flex items-center gap-2" @click="handleImageCommand('rename', imgCtxMenu.image)"><FileEdit class="w-3.5 h-3.5" />重命名</button>
            <div class="border-t border-app-light my-1" />
            <button class="w-full px-3 py-2 text-sm text-left text-red-500 hover:bg-red-50 flex items-center gap-2" @click="handleImageCommand('delete', imgCtxMenu.image)"><Trash2 class="w-3.5 h-3.5" />删除</button>
          </div>
        </Teleport>
      </div>
      <!-- Backend status -->
      <div class="mt-auto p-4 border-t border-app-light">
        <div class="flex items-center gap-2 text-xs text-app-muted">
          <div :class="['w-2 h-2 rounded-full shrink-0', backend.connected.value ? 'bg-green-500' : 'bg-yellow-500']"></div>
          <span class="truncate">{{ backend.statusText.value }}</span>
          <el-button link size="small" class="ml-auto shrink-0" title="重启后端" @click="backend.restart(); ElMessage.success('已重启')"><RefreshCw class="w-3 h-3" /></el-button>
          <el-button v-if="!backend.connected.value" link size="small" class="shrink-0" title="诊断" @click="backend.showDiagnostics()"><span class="text-xs">诊断</span></el-button>
        </div>
      </div>
    </div>

    <!-- Main Editor Area -->
    <div class="flex-1 flex flex-col min-w-0 bg-surface" @dragover.prevent @drop.prevent="handleDrop">
      <div class="h-12 border-b border-app-light flex items-center justify-between px-6 shrink-0">
        <div class="flex items-center gap-3 min-w-0">
          <FileEdit class="w-5 h-5 text-app-muted shrink-0" />
          <h1 class="font-semibold truncate">{{ docs.currentDoc.value.name }}</h1>
          <span v-if="saveStatus === 'unsaved'" class="text-xs text-orange-400 shrink-0">● 未保存</span>
          <span v-if="saveStatus === 'saved' && editorDirty === false && docs.currentDoc.value.id" class="text-xs text-green-500 shrink-0">● 已保存</span>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <el-button v-if="docs.currentDoc.value.id && docs.currentDoc.value.category !== 'excel'" size="small" :disabled="saveStatus === 'saved' && !editorDirty" @click="saveCurrentDoc"><Save class="w-3.5 h-3.5 inline mr-1" />保存</el-button>
          <el-button v-if="docs.currentDoc.value.category === 'draft'" size="small" type="primary" @click="saveDraftToCategory"><Save class="w-3.5 h-3.5 inline mr-1" />保存到分类</el-button>
        </div>
      </div>

      <!-- Toolbar -->
      <div v-if="docs.currentDoc.value.id" class="border-b border-app bg-surface shrink-0">
        <div class="px-4 py-1 flex items-center gap-0.5 flex-wrap border-b border-zinc-50">
          <button class="p-1.5 rounded hover:bg-app-hover" @click="undoAction" title="撤销"><Undo class="w-3.5 h-3.5" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="redoAction" :disabled="isExcelMode && excel.redoStack.value.length === 0" title="重做"><Redo class="w-3.5 h-3.5" /></button>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <select class="text-xs border border-app rounded px-1 py-1 bg-surface min-w-[80px]" @change="(e: any) => setFontFamily(e.target.value)">
            <option value="">字体</option>
            <option value="SimSun, serif">宋体</option><option value="SimHei, sans-serif">黑体</option>
            <option value="KaiTi, serif">楷体</option><option value="FangSong, serif">仿宋</option>
            <option value="Microsoft YaHei, sans-serif">微软雅黑</option>
          </select>
          <select class="text-xs border border-app rounded px-1 py-1 bg-surface" :value="fontSize" @change="(e: any) => setFontSize(e.target.value)">
            <option v-for="s in fontSizes" :key="s" :value="s">{{ s }}</option>
          </select>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <button class="px-2 py-1 rounded hover:bg-app-hover" :class="{ 'bg-app-hover': isBold() }" @click="toggleBold" title="加粗"><Bold class="w-4 h-4" /></button>
          <button class="px-2 py-1 rounded hover:bg-app-hover" :class="{ 'bg-app-hover': isItalic() }" @click="toggleItalic" title="斜体"><Italic class="w-4 h-4" /></button>
          <button class="px-2 py-1 rounded hover:bg-app-hover" :class="{ 'bg-app-hover': isUnderline() }" @click="toggleUnderline" title="下划线"><Underline class="w-4 h-4" /></button>
          <button class="px-2 py-1 rounded hover:bg-app-hover" :class="{ 'bg-app-hover': isStrike() }" @click="toggleStrikethrough" title="删除线"><Strikethrough class="w-4 h-4" /></button>
          <button class="px-2 py-1 rounded hover:bg-app-hover" :class="{ 'bg-app-hover': isCode() }" @click="toggleCode" title="代码"><Code class="w-4 h-4" /></button>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <div class="relative" title="文字颜色">
            <label class="cursor-pointer px-2 py-1 rounded hover:bg-app-hover flex items-center"><LetterText class="w-4 h-4" /><span class="w-3 h-0.5 ml-0.5" :style="{ background: fontColor }"></span></label>
            <input type="color" :value="fontColor" class="absolute inset-0 opacity-0 cursor-pointer w-full" @change="(e: any) => setColor(e.target.value)" />
          </div>
          <div v-if="!isExcelMode" class="relative" title="高亮">
            <label class="cursor-pointer px-2 py-1 rounded hover:bg-app-hover flex items-center"><Highlighter class="w-4 h-4" /></label>
            <input type="color" :value="highlightColor" class="absolute inset-0 opacity-0 cursor-pointer w-full" @change="(e: any) => setHighlight(e.target.value)" />
          </div>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <button class="px-2 py-1 rounded hover:bg-app-hover text-xs" @click="clearMarks" title="清除格式"><span class="underline italic">Tx</span></button>
        </div>
        <div v-if="!isExcelMode" class="px-4 py-1 flex items-center gap-0.5 flex-wrap">
          <button class="px-2 py-1 rounded hover:bg-app-hover text-sm font-bold" :class="{ 'bg-app-hover': isH1() }" @click="setHeading(1)">H1</button>
          <button class="px-2 py-1 rounded hover:bg-app-hover text-sm font-bold" :class="{ 'bg-app-hover': isH2() }" @click="setHeading(2)">H2</button>
          <button class="px-2 py-1 rounded hover:bg-app-hover text-sm font-bold" :class="{ 'bg-app-hover': isH3() }" @click="setHeading(3)">H3</button>
          <button class="px-2 py-1 rounded hover:bg-app-hover text-sm" :class="{ 'bg-app-hover': isBlockquote() }" @click="toggleBlockquote" title="引用">"</button>
          <button class="px-2 py-1 rounded hover:bg-app-hover text-sm" :class="{ 'bg-app-hover': isCodeBlock() }" @click="toggleCodeBlock" title="代码块"><Code class="w-3.5 h-3.5" /></button>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <button class="p-1.5 rounded hover:bg-app-hover" :class="{ 'bg-app-hover': isBullet() }" @click="toggleBullet" title="无序列表"><List class="w-4 h-4" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" :class="{ 'bg-app-hover': isOrdered() }" @click="toggleOrdered" title="有序列表"><ListOrdered class="w-4 h-4" /></button>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('left')" title="左对齐"><AlignLeft class="w-4 h-4" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('center')" title="居中"><AlignCenter class="w-4 h-4" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('right')" title="右对齐"><AlignRight class="w-4 h-4" /></button>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <button class="p-1.5 rounded hover:bg-app-hover" @click="showImagePrompt = true" title="插入图片"><Image class="w-4 h-4" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="insertTable" title="插入表格"><TableIcon class="w-4 h-4" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="insertHr" title="分割线"><Minus class="w-4 h-4 rotate-90" /></button>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <button
            class="p-1.5 rounded hover:bg-app-hover text-purple-600"
            :class="{ 'bg-purple-100': aiResultTab === 'chat' }"
            @click="aiResultTab = aiResultTab === 'chat' ? 'result' : 'chat'"
            title="AI 修改"
          >
            <Sparkles class="w-4 h-4" />
          </button>
          <button
            class="px-2 py-1 rounded hover:bg-app-hover text-xs text-purple-600"
            @click="handleAIModify('扩写这段内容')"
            :disabled="!hasSelection"
            title="扩写选中内容"
          >
            扩写
          </button>
          <button
            class="px-2 py-1 rounded hover:bg-app-hover text-xs text-purple-600"
            @click="handleAIModify('缩写这段内容')"
            :disabled="!hasSelection"
            title="缩写选中内容"
          >
            缩写
          </button>
        </div>
        <div v-else class="px-4 py-1 flex items-center gap-0.5 flex-wrap">
          <!-- Excel 模式第二行：仅对齐按钮和颜色 -->
          <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('left')" title="左对齐"><AlignLeft class="w-4 h-4" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('center')" title="居中"><AlignCenter class="w-4 h-4" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="setAlign('right')" title="右对齐"><AlignRight class="w-4 h-4" /></button>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <div class="relative" title="填充颜色">
            <label class="cursor-pointer px-2 py-1 rounded hover:bg-app-hover flex items-center">
              <span class="w-3 h-3 rounded border inline-block" :style="{background: excel.excelFillColor.value}"></span>
              <input type="color" :value="excel.excelFillColor.value" class="absolute inset-0 opacity-0 cursor-pointer w-full" @change="(e: any) => { excel.excelFillColor.value = e.target.value; excel.applyColorToSelection() }" />
            </label>
          </div>
          <div class="relative" title="文字颜色">
            <label class="cursor-pointer px-2 py-1 rounded hover:bg-app-hover flex items-center"><LetterText class="w-4 h-4" /><span class="w-3 h-0.5 ml-0.5" :style="{ background: excel.excelTextColor.value || '#000000' }"></span></label>
            <input type="color" :value="excel.excelTextColor.value || '#000000'" class="absolute inset-0 opacity-0 cursor-pointer w-full" @change="(e: any) => { excel.excelTextColor.value = e.target.value; excel.setCellTextColor(e.target.value) }" />
          </div>
        </div>
      </div>

      <!-- Editor content area -->
      <div class="flex-1 overflow-y-auto p-10 max-w-4xl mx-auto w-full">
        <div v-if="!docs.currentDoc.value.id" class="h-full flex flex-col items-center justify-center text-app-muted border-2 border-dashed border-app rounded-xl">
          <Upload class="w-12 h-12 mb-4 opacity-20" />
          <p>拖拽文件到此处，或点击左上角「上传」按钮</p>
          <p class="text-xs mt-2">支持 docx, md, txt, xlsx</p>
        </div>

        <!-- Excel loading -->
        <div v-else-if="excel.excelLoading.value" class="h-full flex flex-col items-center justify-center text-app-muted">
          <RefreshCw class="w-8 h-8 mb-3" style="animation: spin 1.5s linear infinite" />
          <p class="text-sm">正在加载表格...</p>
        </div>

        <!-- Excel viewer -->
        <div v-else-if="excel.excelData.value" class="flex-1 min-h-0 flex flex-col">
          <!-- Sheet tabs -->
          <div class="mb-1 flex items-center justify-between shrink-0">
            <div class="flex gap-1 overflow-x-auto">
              <button
                v-for="(sh, idx) in excel.excelData.value.sheets" :key="idx"
                @click="excel.switchSheet(idx)"
                :class="['px-3 py-1 text-xs rounded-t border-b-2 transition-colors', excel.excelData.value.activeSheet === idx ? 'border-blue-500 bg-primary-light text-app-primary font-medium' : 'border-transparent hover:bg-app text-app-secondary']"
              >{{ sh.name }}</button>
            </div>
          </div>
          <!-- Enhanced toolbar -->
          <div class="mb-1 flex items-center gap-1 flex-wrap shrink-0">
            <el-button size="small" plain @click="excel.addRow()" title="末尾追加行"><Plus class="w-3 h-3" /><span class="ml-0.5">行</span></el-button>
            <el-button size="small" plain @click="excel.addCol()" title="末尾追加列"><Plus class="w-3 h-3" /><span class="ml-0.5">列</span></el-button>
            <div class="w-px h-4 bg-app-hover mx-0.5" />
            <el-button size="small" plain @click="excel.insertRowAbove()" title="上方插入行" :disabled="!(excel.selectedCell.value || excel.editCell.value)"><span class="text-xs">↑行</span></el-button>
            <el-button size="small" plain @click="excel.insertRowBelow()" title="下方插入行" :disabled="!(excel.selectedCell.value || excel.editCell.value)"><span class="text-xs">↓行</span></el-button>
            <el-button size="small" plain @click="excel.insertColLeft()" title="左侧插入列" :disabled="!(excel.selectedCell.value || excel.editCell.value)"><span class="text-xs">←列</span></el-button>
            <el-button size="small" plain @click="excel.insertColRight()" title="右侧插入列" :disabled="!(excel.selectedCell.value || excel.editCell.value)"><span class="text-xs">→列</span></el-button>
            <div class="w-px h-4 bg-app-hover mx-0.5" />
            <el-button size="small" plain @click="excel.deleteRow()" title="删除行" :disabled="!(excel.selectedCell.value || excel.editCell.value)"><Trash2 class="w-3 h-3 text-red-500" /><span class="ml-0.5">行</span></el-button>
            <el-button size="small" plain @click="excel.deleteCol()" title="删除列" :disabled="!(excel.selectedCell.value || excel.editCell.value)"><Trash2 class="w-3 h-3 text-red-500" /><span class="ml-0.5">列</span></el-button>
            <div class="w-px h-4 bg-app-hover mx-0.5" />
            <el-button size="small" plain @click="excel.copySelection()" title="复制单元格" :disabled="!(excel.selectedCell.value || excel.editCell.value)"><Copy class="w-3 h-3" /></el-button>
            <el-button size="small" plain @click="excel.pasteToSelection()" title="粘贴单元格" :disabled="!(excel.selectedCell.value || excel.editCell.value) || !excel.copiedData.value"><Clipboard class="w-3 h-3" /></el-button>
            <div class="flex-1" />
          </div>
          <!-- Formula bar -->
          <div v-if="excel.selectedCell.value || excel.editCell.value" class="mb-1 flex items-center gap-1 shrink-0 text-xs">
            <span class="font-mono text-app-muted w-10 text-right shrink-0">{{ (excel.selectedCell.value || excel.editCell.value) ? String.fromCharCode(65 + ((excel.selectedCell.value || excel.editCell.value)!).ci) + (((excel.selectedCell.value || excel.editCell.value)!).ri + 1) : '' }}</span>
            <input
              class="flex-1 border border-app rounded px-2 py-1 font-mono text-xs outline-none focus:border-blue-400 bg-transparent text-app"
              v-model="excel.editingFormula.value"
              @keydown.enter.stop="excel.commitFormula()"
              @keydown.escape.stop="excel.cancelEdit()"
              @blur="excel.commitFormula()"
              placeholder="值或公式（以 = 开头）"
            />
          </div>
          <!-- Table -->
          <div class="overflow-auto border border-app rounded-lg flex-1" @click.self="excel.closeContextMenu()" @keydown="excel.handleCellKeydown($event)" @mouseup="excel.endDragSelect()" @mouseleave="excel.endDragSelect()">
            <table class="w-full text-xs border-collapse" style="table-layout:fixed">
              <colgroup>
                <col style="width:30px" />
                <col v-for="ci in (excel.excelData.value.sheets[excel.excelData.value.activeSheet]?.max_col || 1)" :key="ci"
                  :style="{ width: (excel.colWidths.value[ci - 1] || 70) + 'px' }" />
              </colgroup>
              <thead>
                <tr>
                  <th class="border border-app bg-app p-1 sticky left-0 z-10 min-w-[30px] text-app-muted font-normal"></th>
                  <th v-for="ci in (excel.excelData.value.sheets[excel.excelData.value.activeSheet]?.max_col || 1)" :key="ci" class="border border-app bg-app p-1 text-app-secondary font-medium text-center select-none relative" @click="excel.selectCell(-1, ci - 1)">
                    {{ String.fromCharCode(64 + ci) }}
                    <div class="absolute right-0 top-0 bottom-0 w-1.5 cursor-col-resize z-20 hover:bg-blue-400/50" @mousedown="excel.startColResize(ci - 1, $event)"></div>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in (excel.excelData.value.sheets[excel.excelData.value.activeSheet]?.rows || [])" :key="ri">
                  <td class="border border-app bg-app p-1 text-center text-app-muted text-xs sticky left-0 z-10 select-none" @mousedown.prevent="excel.startDragSelect(ri, 0, $event)" @mouseenter="excel.updateDragSelect(ri, 0)" @click="excel.selectCell(ri, 0)">{{ ri + 1 }}</td>
                  <td v-for="(cell, ci) in row" :key="ci"
                    :class="['border border-app p-0 relative group cursor-default transition-shadow',
                      excel.selectedCell.value?.ri === ri && excel.selectedCell.value?.ci === ci ? 'ring-2 ring-blue-400 ring-inset bg-blue-50/30' : '',
                      excel.isEditing(ri, ci) ? 'ring-2 ring-green-400 ring-inset' : '']"
                    :style="cell.color ? {background: cell.color} : {}"
                    @mousedown.prevent="excel.startDragSelect(ri, ci, $event)"
                    @mouseenter="excel.updateDragSelect(ri, ci)"
                    @click="excel.selectCell(ri, ci)"
                    @dblclick="excel.startEdit(ri, ci)"
                    @contextmenu.prevent="excel.showContextMenu($event, ri, ci)"
                  >
                    <!-- 编辑模式 -->
                    <div v-if="excel.isEditing(ri, ci)" :contenteditable="true"
                      :data-cell-edit="`${ri}-${ci}`"
                      class="outline-none p-1 min-h-[26px] text-xs"
                      @focus="(e:any) => { e.target.textContent = cell.f || cell.v }"
                      @blur="(e:any) => { if (excel.isEditing(ri, ci)) { excel.editingFormula.value = e.target.textContent; excel.endEdit(true) } }"
                      @keydown.tab.prevent.stop="excelCellBlur($event); excel.moveSelection(0, $event.shiftKey ? -1 : 1)"
                      @keydown.enter.prevent.stop="excelCellBlur($event); excel.moveSelection($event.shiftKey ? -1 : 1, 0)"
                      @keydown.ctrl.a.prevent.stop="excel.handleCellKeydown($event)"
                      @keydown.ctrl.c.prevent.stop="excel.copySelection()"
                      @keydown.ctrl.v.prevent.stop="excel.pasteToSelection()"
                    ><span v-if="cell.f" class="text-blue-500 font-mono" :title="'公式: '+cell.f">{{ cell.v }}</span>
                      <span v-else>{{ cell.v }}</span></div>
                    <!-- 显示模式 -->
                    <div v-else :data-cell-display="`${ri}-${ci}`" class="p-1 min-h-[26px] text-xs select-none"
                      :style="{
                        fontWeight: cell.bold ? 'bold' : undefined,
                        fontStyle: cell.italic ? 'italic' : undefined,
                        textDecoration: [cell.underline ? 'underline' : '', cell.strikethrough ? 'line-through' : ''].filter(Boolean).join(' ') || undefined,
                        fontSize: cell.fontSize ? cell.fontSize + 'px' : undefined,
                        fontFamily: cell.fontFamily || undefined,
                        color: cell.textColor || undefined,
                        textAlign: cell.textAlign || undefined,
                        background: cell.color || undefined
                      }"
                    >
                      <span v-if="cell.f" class="text-blue-500 font-mono" :title="'公式: '+cell.f">{{ cell.v }}</span>
                      <span v-else>{{ cell.v || ' ' }}</span>
                    </div>
                  </td>
                  <td v-for="ci in Math.max(0, (excel.excelData.value.sheets[excel.excelData.value.activeSheet]?.max_col || 1) - (row.length || 0))" :key="'e'+ci" class="border border-app p-0.5"></td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- Cell info bar -->
          <div class="mt-1 flex items-center gap-2 text-xs text-app-muted shrink-0">
            <span v-if="excel.selectedCell.value || excel.editCell.value">单元格：{{ String.fromCharCode(65 + ((excel.selectedCell.value || excel.editCell.value)!).ci) }}{{ ((excel.selectedCell.value || excel.editCell.value)!).ri + 1 }}{{ excel.editCell.value ? ' ✎ 编辑中' : '' }}</span>
            <span v-else>单击选中 — 双击或 F2 编辑 — Tab/Enter 切换单元格 — Ctrl+C/V 复制粘贴</span>
            <span v-if="excel.copiedData.value" class="ml-auto flex items-center gap-1"><Copy class="w-3 h-3" />已复制</span>
          </div>
          <!-- Context menu -->
          <Teleport to="body">
            <div v-if="excel.contextMenu.value.show"
              class="fixed z-[9999] bg-surface rounded-lg shadow-xl border border-app py-1 min-w-[170px]"
              :style="{ left: excel.contextMenu.value.x + 'px', top: excel.contextMenu.value.y + 'px' }"
              @click.stop
            >
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" @click="excel.copySelection()"><Copy class="w-3.5 h-3.5" />复制</button>
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" :disabled="!excel.copiedData.value" @click="excel.pasteToSelection()"><Clipboard class="w-3.5 h-3.5" />粘贴</button>
              <div class="border-t border-app-light my-1" />
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" @click="excel.insertRowAbove()">↑ 上方插入行</button>
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" @click="excel.insertRowBelow()">↓ 下方插入行</button>
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" @click="excel.insertColLeft()">← 左侧插入列</button>
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" @click="excel.insertColRight()">→ 右侧插入列</button>
              <div class="border-t border-app-light my-1" />
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" @click="excel.clearCell()">清空单元格</button>
              <button class="w-full px-3 py-1.5 text-xs text-left text-red-500 hover:bg-red-50 flex items-center gap-2" @click="excel.deleteRow()"><Trash2 class="w-3 h-3" />删除行</button>
              <button class="w-full px-3 py-1.5 text-xs text-left text-red-500 hover:bg-red-50 flex items-center gap-2" @click="excel.deleteCol()"><Trash2 class="w-3 h-3" />删除列</button>
            </div>
          </Teleport>
        </div>

        <!-- Tiptap editor -->
        <EditorContent v-else :editor="tiptapEditor" class="min-h-[500px]" />
      </div>
    </div>

    <!-- Right AI Panel -->
    <div class="w-80 border-l border-app bg-app flex flex-col shrink-0">
      <div class="p-4 border-b border-app">
        <label class="text-xs font-bold text-app-muted uppercase tracking-wider mb-2 block">AI 模型选择</label>
        <el-select v-model="ai.activeModel.value" size="default" class="w-full">
          <el-option v-for="item in ai.models.value" :key="item.name" :label="item.name" :value="item.name">
            <div class="flex items-center justify-between"><span>{{ item.name }}</span><el-tag v-if="item.type === 'local'" size="small" type="info">本地</el-tag></div>
          </el-option>
        </el-select>
      </div>
      <div class="p-4 space-y-4">
        <label class="text-xs font-bold text-app-muted uppercase tracking-wider block">核心功能</label>
        <div class="grid grid-cols-2 gap-2">
          <el-button class="!m-0 h-20 flex flex-col gap-2" @click="tools.openTools()"><CheckCircle2 class="w-5 h-5 text-green-600" /><span>快捷工具</span></el-button>
          <el-button class="!m-0 h-20 flex flex-col gap-2" @click="showImitateDialog = true" :loading="ai.isProcessing.value"><Sparkles class="w-5 h-5 text-purple-600" /><span>智能PRD</span></el-button>
          <el-button class="!m-0 h-20 flex flex-col gap-2" @click="showImageToolDialog = true"><Image class="w-5 h-5 text-blue-500" /><span>图片工具</span></el-button>
          <el-button class="!m-0 h-20 flex flex-col gap-2" @click="runLogicCompletion" :loading="ai.isProcessing.value"><Zap class="w-5 h-5 text-orange-600" /><span>逻辑补完</span></el-button>
        </div>
      </div>
      <div class="flex-1 p-4 flex flex-col min-h-0 overflow-hidden">
        <!-- Tab bar -->
        <div class="flex items-center border-b border-app mb-2 shrink-0">
          <button
            @click="aiResultTab = 'result'"
            :class="['text-xs font-bold uppercase tracking-wider px-3 py-1.5 -mb-px border-b-2 transition-colors', aiResultTab === 'result' ? 'border-blue-500 text-blue-600' : 'border-transparent text-app-muted hover:text-app']"
          >质检结果</button>
          <button
            v-if="ai.iterationHistory.value.length > 0"
            @click="aiResultTab = 'chat'"
            :class="['text-xs font-bold uppercase tracking-wider px-3 py-1.5 -mb-px border-b-2 transition-colors', aiResultTab === 'chat' ? 'border-blue-500 text-blue-600' : 'border-transparent text-app-muted hover:text-app']"
          >对话</button>
          <div class="flex-1" />
          <el-button v-if="aiResultTab === 'result'" link @click="copyResult" :disabled="!ai.aiResult.value"><Copy class="w-3.5 h-3.5" /></el-button>
          <el-button v-if="ai.aiResult.value && aiResultTab === 'result'" link @click="clearResult"><Trash2 class="w-3.5 h-3.5 text-red-400" /></el-button>
        </div>

        <!-- 质检结果 tab -->
        <div v-if="aiResultTab === 'result'" class="flex-1 flex flex-col min-h-0">
          <div class="flex-1 bg-surface border border-app rounded-lg p-3 overflow-y-auto text-sm text-app-secondary leading-relaxed shadow-sm">
            <div v-if="!ai.aiResult.value && !ai.isProcessing.value" class="h-full flex items-center justify-center text-zinc-300 italic">等待功能触发...</div>
            <div v-else class="whitespace-pre-wrap">{{ ai.aiResult.value }}</div>
            <div v-if="ai.isProcessing.value" class="flex items-center gap-2 mt-2 text-blue-500"><el-icon class="is-loading"><RefreshCw /></el-icon>AI 正在思考中...</div>
          </div>
          <div v-if="ai.aiResult.value && !ai.isProcessing.value" class="mt-2 pt-2 border-t border-app">
            <div class="flex gap-2">
              <el-input v-model="ai.iterativePrompt.value" placeholder="输入修改指令，继续优化" size="small" @keyup.enter="runIteration" />
              <el-button type="primary" size="small" @click="runIteration" :disabled="!ai.iterativePrompt.value.trim()">继续修改</el-button>
            </div>
          </div>
        </div>

        <!-- 对话 tab -->
        <div v-else-if="aiResultTab === 'chat'" class="flex-1 flex flex-col min-h-0">
          <AIIterationPanel
            :embedded="true"
            :current-section="currentDocSection"
            :history="ai.iterationHistory.value"
            :is-iterating="ai.isIterating.value"
            @submit="handleAIModify"
          />
        </div>
      </div>
    </div>

    <!-- Dialogs -->
    <NewDraftDialog v-model:visible="showNewDraftDialog" @create="createNewDraft" />

    <ImageDialog v-model:visible="showImagePrompt" @insert="insertImageFromUrl" />

    <ImitateDialog
      v-model:visible="showImitateDialog"
      :projects="kb.projects.value"
      :search-results="kb.searchResults.value"
      :search-loading="kb.searchLoading.value"
      @search="kb.search"
      @submit="runImitateAndCreate"
    />

    <ImageToolDialog
      v-model:visible="showImageToolDialog"
      :library-image-data-uri="libraryEditImageUri"
      :design-prompt-template="designPromptTemplate"
      :library-images="imageLib.images.value"
      :library-loading="imageLib.loading.value"
      @save-to-library="(uri: string) => { imageLib.saveImage(uri, '未命名图片') }"
    />

    <PromptDialog
      v-model:visible="prompts.showPromptDialog.value"
      :professions="prompts.professions.value"
      :selected-profession="prompts.selectedProfession.value"
      :roles="prompts.roles.value"
      :selected-role="prompts.selectedRole.value"
      :show-add-role-form="prompts.showAddRoleForm.value"
      :new-role-name="prompts.newRoleName.value"
      :new-role-prompt="prompts.newRolePrompt.value"
      :editing-role="prompts.editingRole.value"
      @update:selected-profession="prompts.onProfessionChange"
      @update:new-role-name="(v:string) => prompts.newRoleName.value = v"
      @update:new-role-prompt="(v:string) => prompts.newRolePrompt.value = v"
      @select-role="prompts.selectRole"
      @start-add-role="prompts.startAddRole"
      @start-edit-role="prompts.startEditRole"
      @delete-role="prompts.deleteRole"
      @save-role="prompts.saveRole"
      @cancel-add-role="prompts.cancelAddRole"
      @reset-defaults="async () => { await ElMessageBox.confirm('重置恢复默认Prompt', '确认', { type: 'warning' }); await prompts.resetDefaults() }"
      @start-check="startQualityCheckWithPrompt"
    />

    <SettingsDialog
      v-model:visible="settings.showSettings.value"
      :auto-start="settings.autoStart.value"
      :tortoise-svn-path="settings.tortoiseSvnPath.value"
      :models="ai.models.value"
      :model-configs="settings.modelConfigs.value"
      :testing-model="settings.testingModel.value"
      :testing-image-model="settings.testingImageModel.value"
      :professions-full="prompts.professionsFull.value"
      :selected-imitation-profession="prompts.selectedImitationProfession.value"
      :editing-profession-id="prompts.editingProfessionId.value"
      :is-dark="theme.isDark.value"
      :new-prompt-name="prompts.newPromptName.value"
      :new-prompt-content="prompts.newPromptContent.value"
      :quality-check-prompt="editingQualityCheckPrompt"
      :data-path="settings.dataPath.value"
      @update:is-dark="theme.toggle"
      @update:auto-start="settings.handleAutoStartChange"
      @update:tortoise-svn-path="(v:string) => settings.tortoiseSvnPath.value = v"
      @save-config="settings.saveConfig"
      @test-model="settings.testModel"
      @test-image-model="settings.testImageModel"
      @on-profession-change="prompts.onProfessionChangeForSettings"
      @update:new-prompt-name="(v:string) => prompts.newPromptName.value = v"
      @update:new-prompt-content="(v:string) => prompts.newPromptContent.value = v"
      @update:quality-check-prompt="(v:string) => editingQualityCheckPrompt = v"
      @save-quality-check-prompt="() => saveQualityCheckPrompt(editingQualityCheckPrompt)"
      @update:data-path="(v:string) => settings.dataPath.value = v"
      @save-data-path="settings.saveDataPath"
      @add-prompt="() => prompts.addPromptToProfession(prompts.selectedImitationProfession.value)"
      @delete-prompt="(promptId: string) => prompts.deletePromptFromProfession(prompts.selectedImitationProfession.value, promptId)"
    />

    <KBDialog
      v-model:visible="kb.showKB.value"
      :projects="kb.projects.value"
      :active-project-id="kb.activeProjectId.value"
      :folders="kb.folders.value"
      :documents="kb.documents.value"
      :kb-stats="kb.kbStats.value"
      :search-results="kb.searchResults.value"
      :backups="kb.backups.value"
      :vocab-list="kb.vocabList.value"
      :is-uploading-k-b="kb.isUploadingKB.value"
      :upload-progress="kb.uploadProgress.value"
      :upload-file-name="kb.uploadFileName.value"
      :upload-total-files="kb.uploadTotalFiles.value"
      :upload-current-file="kb.uploadCurrentFile.value"
      :search-loading="kb.searchLoading.value"
      :loading="kb.loading.value"
      @load-projects="kb.loadProjects"
      @switch-project="kb.switchProject"
      @create-project="kb.createProject"
      @delete-project="kb.deleteProject"
      @load-folders="kb.loadFolders"
      @create-folder="kb.createFolder"
      @rename-folder="kb.renameFolder"
      @delete-folder="kb.deleteFolder"
      @load-documents="kb.loadDocuments"
      @upload-file="handleKBUpload"
      @upload-files="handleKBUploadFiles"
      @update-document="kb.updateDocument"
      @delete-document="handleKBDelete"
      @search="kb.search"
      @fuzzy-search="kb.fuzzySearch"
      @load-backups="kb.loadBackups"
      @create-backup="kb.createBackup"
      @restore-backup="kb.restoreBackup"
      @load-vocab="kb.loadVocab"
      @add-vocab="kb.addVocab"
      @remove-vocab="kb.removeVocab"
      @open-project-dialog="showKBProjectDialog = true"
      @open-note-dialog="handleOpenNoteDialog"
      @open-backup-dialog="showBackupDialog = true"
      @open-vocab-dialog="showVocabDialog = true"
      @open-chunk-size-dialog="showChunkSizeDialog = true"
      @open-batch-import-dialog="showBatchImportDialog = true"
      @rename-project="kb.renameProject"
      @clear-all="handleKBClear"
    />

    <KBSearchPanel
      v-model:visible="showSearchPanel"
      :projects="kb.projects.value"
      :active-project-id="kb.activeProjectId.value"
      :folders="kb.folders.value"
      :search-results="kb.searchResults.value"
      :search-loading="kb.searchLoading.value"
      @search="kb.search"
      @fuzzy-search="kb.fuzzySearch"
    />

    <KBProjectDialog
      v-model:visible="showKBProjectDialog"
      :loading="kb.loading.value"
      @create-project="async (name, description, model) => { await kb.createProject(name, description, model); showKBProjectDialog = false }"
    />

    <KBDocNoteDialog
      v-model:visible="showDocNoteDialog"
      :doc-id="editingDocId"
      :current-note="editingDocNote"
      @save="handleSaveNote"
    />

    <KBBackupDialog
      v-model:visible="showBackupDialog"
      :backups="kb.backups.value"
      :loading="kb.loading.value"
      @load-backups="kb.loadBackups"
      @create-backup="kb.createBackup"
      @restore-backup="kb.restoreBackup"
      @delete-backup="kb.deleteBackup"
    />

    <KBVocabDialog
      v-model:visible="showVocabDialog"
      :vocab-list="kb.vocabList.value"
      :loading="kb.loading.value"
      @load-vocab="kb.loadVocab"
      @add-vocab="kb.addVocab"
      @remove-vocab="kb.removeVocab"
    />

    <KBChunkSizeDialog
      v-model:visible="showChunkSizeDialog"
      :chunk-size-min="kb.chunkSizeMin.value"
      :chunk-size-max="kb.chunkSizeMax.value"
      :loading="kb.loading.value"
      @save="kb.saveChunkSize"
      @rechunk="kb.rechunk"
    />

    <KBBatchImportDialog
      v-model:visible="showBatchImportDialog"
      :active-project-id="kb.activeProjectId.value"
      :active-folder-id="kb.activeFolderFilter.value || undefined"
      @import-files="handleBatchImport"
    />

    <ToolsDialog
      v-model:visible="tools.showToolsDialog.value"
      :svn-configs="tools.svnConfigs.value"
      :nav-configs="tools.navConfigs.value"
      :svn-updating="tools.svnUpdating.value"
      :show-add-svn-dialog="tools.showAddSvnDialog.value"
      :show-add-nav-dialog="tools.showAddNavDialog.value"
      :new-svn-name="tools.newSvnName.value"
      :new-svn-path="tools.newSvnPath.value"
      :new-nav-name="tools.newNavName.value"
      :new-nav-path="tools.newNavPath.value"
      :svn-open-after-update="tools.svnOpenAfterUpdate.value"
      :reminders="tools.reminders.value"
      :show-reminder-dialog="tools.showReminderDialog.value"
      :editing-reminder="tools.editingReminder.value"
      @update:new-svn-name="(v:string) => tools.newSvnName.value = v"
      @update:new-svn-path="(v:string) => tools.newSvnPath.value = v"
      @update:new-nav-name="(v:string) => tools.newNavName.value = v"
      @update:new-nav-path="(v:string) => tools.newNavPath.value = v"
      @update:show-add-svn-dialog="(v:boolean) => tools.showAddSvnDialog.value = v"
      @update:show-add-nav-dialog="(v:boolean) => tools.showAddNavDialog.value = v"
      @update:svn-open-after-update="(v:boolean) => tools.svnOpenAfterUpdate.value = v"
      @update:show-reminder-dialog="(v:boolean) => tools.showReminderDialog.value = v"
      @add-svn="handleAddSvn"
      @remove-svn="tools.removeSvn"
      @run-svn-update="handleRunSvnUpdate"
      @add-nav="tools.addNav"
      @remove-nav="tools.removeNav"
      @open-nav-item="tools.openNavItem"
      @open-reminder-dialog="tools.openReminderDialog"
      @save-reminder="tools.saveReminder"
      @delete-reminder="tools.deleteReminder"
    />

    <QualityCheckDialog v-model:visible="showQualityCheckDialog" @submit="handleQualityCheckSubmit" />

  </div>
</template>

<style>
.ProseMirror { min-height: 400px; padding: 0; }
.ProseMirror:focus { outline: none; }
.ProseMirror p.is-editor-empty:first-child::before { color: #adb5bd; content: attr(data-placeholder); float: left; height: 0; pointer-events: none; }
.ProseMirror table { border-collapse: collapse; table-layout: auto; width: 100%; margin: 1em 0; overflow: auto; }
.ProseMirror td, .ProseMirror th { border: 1px solid #d4d4d8; padding: 8px 12px; min-width: 60px; position: relative; vertical-align: top; }
.ProseMirror th { background: #f4f4f5; font-weight: 600; }
.ProseMirror table .selectedCell:after { background: rgba(200,200,255,0.4); content: ''; left: 0; right: 0; top: 0; bottom: 0; pointer-events: none; position: absolute; z-index: 2; }
.ProseMirror img { max-width: 100%; height: auto; border-radius: 4px; margin: 0.5em 0; display: block; }
.ProseMirror img.ProseMirror-selectednode { outline: 2px solid #3b82f6; outline-offset: 2px; }
.ProseMirror ul, .ProseMirror ol { padding-left: 1.5em; margin: 0.3em 0; }
.ProseMirror li { margin: 0.2em 0; }
.ProseMirror h1 { font-size: 1.75rem; font-weight: 700; margin: 1em 0 0.5em; line-height: 1.3; }
.ProseMirror h2 { font-size: 1.4rem; font-weight: 600; margin: 1em 0 0.5em; line-height: 1.4; }
.ProseMirror h3 { font-size: 1.2rem; font-weight: 600; margin: 0.8em 0 0.4em; line-height: 1.5; }
.ProseMirror blockquote { border-left: 3px solid #a1a1aa; padding-left: 16px; color: #71717a; margin: 1em 0; }
.ProseMirror p { margin: 0.5em 0; }
.ProseMirror hr { border: none; border-top: 1px solid #d4d4d8; margin: 1.5em 0; }
.ProseMirror code { background: #f4f4f5; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }
.ProseMirror pre { background: #1e1e2e; color: #cdd6f4; padding: 16px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 0.9em; line-height: 1.6; }
.ProseMirror pre code { background: none; padding: 0; color: inherit; font-size: inherit; }
.ProseMirror mark { padding: 0 2px; border-radius: 2px; }
.ProseMirror s { text-decoration: line-through; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
