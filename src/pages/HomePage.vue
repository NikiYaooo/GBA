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
  Highlighter, LetterText, Brain, Save, Plus
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

import { useBackend } from '@/composables/useBackend'
import { useDocuments } from '@/composables/useDocuments'
import { useAI } from '@/composables/useAI'
import { useKnowledgeBase } from '@/composables/useKnowledgeBase'
import { useExcel } from '@/composables/useExcel'
import { useTools } from '@/composables/useTools'
import { useSettings } from '@/composables/useSettings'
import { useTheme } from '@/composables/useTheme'
import { usePrompts } from '@/composables/usePrompts'

import NewDraftDialog from '@/components/dialogs/NewDraftDialog.vue'
import ImageDialog from '@/components/dialogs/ImageDialog.vue'
import ImitateDialog from '@/components/dialogs/ImitateDialog.vue'
import PromptDialog from '@/components/dialogs/PromptDialog.vue'
import SettingsDialog from '@/components/dialogs/SettingsDialog.vue'
import KBDialog from '@/components/dialogs/KBDialog.vue'
import ToolsDialog from '@/components/dialogs/ToolsDialog.vue'

// --- Composables ---
const activeCategory = ref('doc')
const categories: CategoryDef[] = [
  { id: 'doc', label: '文档库', icon: 'FileText' },
  { id: 'imitation', label: '仿写库', icon: 'Sparkles' },
  { id: 'excel', label: '配置表', icon: 'TableIcon' },
  { id: 'draft', label: '草稿', icon: 'FileEdit' },
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

// --- Draft state ---
const showNewDraftDialog = ref(false)
const isDraftEditing = ref(false)
const currentDraftCat = ref('draft')

// --- Image dialog ---
const showImagePrompt = ref(false)

// --- Imitate dialog ---
const showImitateDialog = ref(false)

// --- Context menu ---
const ctxMenu = ref({ visible: false, x: 0, y: 0, doc: null as DocRecord | null })
const closeCtxMenu = () => { ctxMenu.value.visible = false }
const excelCellBlur = (e: KeyboardEvent) => (e.target as HTMLElement)?.blur()

const showCtxMenu = (e: MouseEvent, doc: DocRecord) => {
  ctxMenu.value = { visible: true, x: e.clientX, y: e.clientY, doc }
}

// --- Editor dirty / auto-save ---
const editorDirty = ref(false)
let saveTimer: any = null

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
  ],
  editable: true,
  onUpdate: ({ editor }) => {
    editorDirty.value = true
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
    try {
      const res = await axios.get(apiUrl(`/api/documents/${newId}`))
      if (res.data.success) {
        const c = res.data.data.content || ''
        const isHtml = /<\/?\w+[^>]*>/.test(c)
        docs.currentDoc.value.content = c
        if (isHtml) tiptapEditor.value.commands.setContent(c)
        else tiptapEditor.value.commands.setContent(`<p>${c.replace(/\n/g, '</p><p>')}</p>`)
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
const setHeading = (level: 1 | 2 | 3) => tiptapEditor.value?.chain().focus().toggleHeading({ level }).run()
const toggleBold = () => tiptapEditor.value?.chain().focus().toggleBold().run()
const toggleItalic = () => tiptapEditor.value?.chain().focus().toggleItalic().run()
const toggleUnderline = () => tiptapEditor.value?.chain().focus().toggleUnderline().run()
const toggleStrikethrough = () => tiptapEditor.value?.chain().focus().toggleStrike().run()
const toggleCode = () => tiptapEditor.value?.chain().focus().toggleCode().run()
const toggleCodeBlock = () => tiptapEditor.value?.chain().focus().toggleCodeBlock().run()
const toggleBlockquote = () => tiptapEditor.value?.chain().focus().toggleBlockquote().run()
const toggleBullet = () => tiptapEditor.value?.chain().focus().toggleBulletList().run()
const toggleOrdered = () => tiptapEditor.value?.chain().focus().toggleOrderedList().run()
const setAlign = (align: string) => tiptapEditor.value?.chain().focus().setTextAlign(align).run()
const setFontSize = (size: string) => { fontSize.value = size; tiptapEditor.value?.chain().focus().setMark('textStyle', { fontSize: size }).run() }
const setFontFamily = (font: string) => { tiptapEditor.value?.chain().focus().setFontFamily(font).run() }
const setColor = (color: string) => { fontColor.value = color; tiptapEditor.value?.chain().focus().setColor(color).run() }
const setHighlight = (color: string) => { highlightColor.value = color; tiptapEditor.value?.chain().focus().setHighlight({ color }).run() }
const clearMarks = () => tiptapEditor.value?.chain().focus().clearNodes().unsetAllMarks().run()
const insertTable = () => tiptapEditor.value?.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()
const insertHr = () => tiptapEditor.value?.chain().focus().setHorizontalRule().run()
const undo = () => tiptapEditor.value?.chain().focus().undo().run()
const redo = () => tiptapEditor.value?.chain().focus().redo().run()
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
  await docs.loadDocuments(catId)
}

const selectDoc = async (doc: DocRecord) => {
  await docs.selectDoc(doc)
  ai.aiResult.value = ''
  const ext = (doc.name || '').split('.').pop()?.toLowerCase() || ''
  if (['xlsx', 'xls'].includes(ext) || doc.category === 'excel') {
    await excel.loadExcelData(doc)
  } else {
    excel.reset()
  }
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
    ai.aiResult.value = ''; ai.isProcessing.value = true
    const text = tiptapEditor.value?.getText() || docs.currentDoc.value.content || ''
    const pro = prompts.professionsFull.value.find(p => p.id === prompts.selectedImitationProfession.value)
    const qcPrompt = pro?.qualityCheckPrompt || ''
    const result = await ai.runQualityCheck(text, qcPrompt)
    if (result) ai.aiResult.value = `【质检职业：${pro?.name || '默认'}】\n\n${result}`
    else ElMessage.error('质检失败')
    ai.isProcessing.value = false
  }
}

// --- File upload / drop ---
const handleDrop = async (e: DragEvent) => {
  const file = e.dataTransfer?.files[0]
  if (!file) return
  const ext = file.name.split('.').pop()?.toLowerCase()
  if (!['docx', 'md', 'txt', 'xlsx', 'xls'].includes(ext || '')) {
    ElMessage.warning('仅支持 docx, md, txt, xlsx'); return
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
  input.accept = '.docx,.md,.txt,.xlsx,.xls'
  input.onchange = async (e: any) => { if (e.target.files[0]) await uploadFile(e.target.files[0]) }
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

const runImitateAndCreate = async (requirements: string, mindmapContent: string) => {
  showImitateDialog.value = false
  ai.isProcessing.value = true

  try {
    let content = await ai.runImitation(requirements, mindmapContent, true)
    if (!content) { ElMessage.warning('生成失败'); return }

    // Auto quality check + fix
    try {
      const qc = await ai.runQualityCheck(content,
        '你是资深游戏策划，请对以下策划案进行快速质检，重点关注逻辑漏洞和内容缺失，给出简洁的修改建议（不超过200字），直接给出建议不要客套。'
      )
      if (qc && !qc.includes('未检测到')) {
        const feedback = qc.length > 300 ? qc.substring(0, 300) : qc
        const revised = await ai.runImitation(
          `根据以下质检建议修改策划案，不说客套废话，直接输出完整文档内容。\n质检建议：${feedback}\n原始文档：${content}`,
          content, false
        )
        if (revised) content = revised
      }
    } catch { /* */ }

    const title = ai.generateDocTitle(requirements)
    const doc = await docs.createDocument(title, content, 'imitation')
    if (doc) {
      docs.docList.value.unshift(doc)
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
const handleKBUpload = async (file: File) => {
  const ok = await kb.uploadFile(file)
  if (ok) ElMessage.success('入库成功')
  else ElMessage.warning('入库失败')
}

const handleKBDelete = async (fileHash: string) => {
  try {
    await ElMessageBox.confirm('确定删除？', '提示', { type: 'warning' })
    await kb.deleteDocument(fileHash)
    ElMessage.success('已删除')
  } catch { /* */ }
}

const handleKBClear = async () => {
  try {
    await ElMessageBox.confirm('确定清空知识库？', '警告', { type: 'error' })
    await kb.clearAll()
    ElMessage.success('已清空')
  } catch { /* */ }
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
})

onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  tiptapEditor.value?.destroy()
  document.removeEventListener('click', closeCtxMenu)
})

const formatDate = (ts: number) => new Date(ts * 1000).toLocaleString()

const openSettings = () => settings.openSettings(() => prompts.loadProfessionsFull())
</script>

<template>
  <div class="flex h-screen bg-app overflow-hidden font-sans text-app">
    <!-- Left Sidebar -->
    <div class="w-64 border-r border-app bg-surface flex flex-col shrink-0">
      <div class="p-4 border-b border-app-light">
        <div class="flex items-center gap-1 mb-3">
          <h2 class="font-bold text-lg flex items-center gap-2 flex-1"><FolderOpen class="w-5 h-5 text-app-primary" />文档</h2>
          <el-button type="primary" size="small" plain @click="handleUpload"><template #icon><Upload class="w-4 h-4" /></template>上传</el-button>
          <el-button link @click="kb.openKB()"><Database class="w-4 h-4 text-app-muted" /></el-button>
          <el-button link @click="openSettings"><Settings class="w-4 h-4 text-app-muted" /></el-button>
        </div>
        <el-input v-model="docs.searchQuery.value" placeholder="搜索..." :prefix-icon="Search" size="small" clearable />
      </div>
      <div class="px-2 pt-2 pb-2 flex-1 overflow-y-auto" @click="closeCtxMenu">
        <div class="flex gap-1 mb-3 border-b border-app-light pb-2">
          <button
            v-for="cat in categories" :key="cat.id" @click="switchCategory(cat.id)"
            :class="['flex-1 text-xs font-medium py-1.5 px-1 rounded transition-colors', activeCategory === cat.id ? 'bg-primary-light text-app-primary' : 'text-app-muted hover:text-app-secondary']"
          >{{ cat.label }}</button>
        </div>
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
        <!-- Context menu -->
        <Teleport to="body">
          <div
            v-if="ctxMenu.visible"
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
      </div>
      <!-- Backend status -->
      <div class="mt-auto p-4 border-t border-app-light">
        <div class="flex items-center gap-2 text-xs text-app-muted">
          <div :class="['w-2 h-2 rounded-full shrink-0', backend.connected.value ? 'bg-green-500' : 'bg-yellow-500']"></div>
          <span class="truncate">{{ backend.statusText.value }}</span>
          <el-button link size="small" class="ml-auto shrink-0" title="重启后端" @click="backend.restart(); ElMessage.success('已重启')"><RefreshCw class="w-3 h-3" /></el-button>
        </div>
      </div>
    </div>

    <!-- Main Editor Area -->
    <div class="flex-1 flex flex-col min-w-0 bg-surface" @dragover.prevent @drop.prevent="handleDrop">
      <div class="h-12 border-b border-app-light flex items-center justify-between px-6 shrink-0">
        <div class="flex items-center gap-3 min-w-0">
          <FileEdit class="w-5 h-5 text-app-muted shrink-0" />
          <h1 class="font-semibold truncate">{{ docs.currentDoc.value.name }}</h1>
          <span v-if="editorDirty" class="text-xs text-orange-400 shrink-0">● 未保存</span>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <el-button v-if="docs.currentDoc.value.category === 'draft'" size="small" type="primary" @click="saveDraftToCategory"><Save class="w-3.5 h-3.5 inline mr-1" />保存到分类</el-button>
        </div>
      </div>

      <!-- Toolbar -->
      <div v-if="docs.currentDoc.value.id" class="border-b border-app bg-surface shrink-0">
        <div class="px-4 py-1 flex items-center gap-0.5 flex-wrap border-b border-zinc-50">
          <button class="p-1.5 rounded hover:bg-app-hover" @click="undo" title="撤销"><Undo class="w-3.5 h-3.5" /></button>
          <button class="p-1.5 rounded hover:bg-app-hover" @click="redo" title="重做"><Redo class="w-3.5 h-3.5" /></button>
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
          <div class="relative" title="高亮">
            <label class="cursor-pointer px-2 py-1 rounded hover:bg-app-hover flex items-center"><Highlighter class="w-4 h-4" /></label>
            <input type="color" :value="highlightColor" class="absolute inset-0 opacity-0 cursor-pointer w-full" @change="(e: any) => setHighlight(e.target.value)" />
          </div>
          <div class="w-px h-5 bg-app-hover mx-1" />
          <button class="px-2 py-1 rounded hover:bg-app-hover text-xs" @click="clearMarks" title="清除格式"><span class="underline italic">Tx</span></button>
        </div>
        <div class="px-4 py-1 flex items-center gap-0.5 flex-wrap">
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
        </div>
      </div>

      <!-- Editor content area -->
      <div class="flex-1 overflow-y-auto p-10 max-w-4xl mx-auto w-full">
        <div v-if="!docs.currentDoc.value.id" class="h-full flex flex-col items-center justify-center text-app-muted border-2 border-dashed border-app rounded-xl">
          <Upload class="w-12 h-12 mb-4 opacity-20" />
          <p>拖拽文件到此处，或点击左上角「上传」按钮</p>
          <p class="text-xs mt-2">支持 docx, md, txt, xlsx</p>
        </div>

        <!-- Excel viewer -->
        <div v-else-if="excel.excelData.value" class="min-h-[400px] flex flex-col">
          <!-- Sheet tabs -->
          <div class="mb-1 flex items-center justify-between shrink-0">
            <div class="flex gap-1 overflow-x-auto">
              <button
                v-for="(sh, idx) in excel.excelData.value.sheets" :key="idx"
                @click="excel.excelData.value.activeSheet = idx"
                :class="['px-3 py-1 text-xs rounded-t border-b-2 transition-colors', excel.excelData.value.activeSheet === idx ? 'border-blue-500 bg-primary-light text-app-primary font-medium' : 'border-transparent hover:bg-app text-app-secondary']"
              >{{ sh.name }}</button>
            </div>
          </div>
          <!-- Enhanced toolbar -->
          <div class="mb-1 flex items-center gap-1 flex-wrap shrink-0">
            <el-button size="small" plain @click="excel.addRow()" title="末尾追加行"><Plus class="w-3 h-3" /><span class="ml-0.5">行</span></el-button>
            <el-button size="small" plain @click="excel.addCol()" title="末尾追加列"><Plus class="w-3 h-3" /><span class="ml-0.5">列</span></el-button>
            <div class="w-px h-4 bg-app-hover mx-0.5" />
            <el-button size="small" plain @click="excel.insertRowAbove()" title="上方插入行" :disabled="!excel.selectedCell.value"><span class="text-xs">↑行</span></el-button>
            <el-button size="small" plain @click="excel.insertRowBelow()" title="下方插入行" :disabled="!excel.selectedCell.value"><span class="text-xs">↓行</span></el-button>
            <el-button size="small" plain @click="excel.insertColLeft()" title="左侧插入列" :disabled="!excel.selectedCell.value"><span class="text-xs">←列</span></el-button>
            <el-button size="small" plain @click="excel.insertColRight()" title="右侧插入列" :disabled="!excel.selectedCell.value"><span class="text-xs">→列</span></el-button>
            <div class="w-px h-4 bg-app-hover mx-0.5" />
            <el-button size="small" plain @click="excel.deleteRow()" title="删除行" :disabled="!excel.selectedCell.value"><Trash2 class="w-3 h-3 text-red-500" /><span class="ml-0.5">行</span></el-button>
            <el-button size="small" plain @click="excel.deleteCol()" title="删除列" :disabled="!excel.selectedCell.value"><Trash2 class="w-3 h-3 text-red-500" /><span class="ml-0.5">列</span></el-button>
            <div class="w-px h-4 bg-app-hover mx-0.5" />
            <el-button size="small" plain @click="excel.copyCell()" title="复制单元格" :disabled="!excel.selectedCell.value"><Copy class="w-3 h-3" /></el-button>
            <el-button size="small" plain @click="excel.pasteCell()" title="粘贴单元格" :disabled="!excel.selectedCell.value || !excel.copiedCell.value"><Clipboard class="w-3 h-3" /></el-button>
            <div class="flex-1" />
            <label class="text-xs text-app-muted flex items-center gap-1 cursor-pointer" title="填充颜色">
              <span class="w-3 h-3 rounded border inline-block" :style="{background: excel.excelFillColor.value}"></span>
              <input type="color" :value="excel.excelFillColor.value" class="w-5 h-5 border-0 p-0 cursor-pointer" @change="(e:any) => excel.excelFillColor.value = e.target.value" />
            </label>
            <el-button size="small" plain @click="handleDocCommand('saveAs', docs.currentDoc.value)"><Save class="w-3.5 h-3.5" /><span class="ml-1">另存为</span></el-button>
          </div>
          <!-- Table -->
          <div class="overflow-auto border border-app rounded-lg flex-1" @click.self="excel.closeContextMenu()">
            <table class="w-full text-xs border-collapse">
              <thead>
                <tr>
                  <th class="border border-app bg-app p-1 sticky left-0 z-10 min-w-[30px] text-app-muted font-normal"></th>
                  <th v-for="ci in (excel.excelData.value.sheets[excel.excelData.value.activeSheet]?.max_col || 1)" :key="ci" class="border border-app bg-app p-1 min-w-[70px] text-app-secondary font-medium text-center select-none" @click="excel.selectCell(-1, ci - 1)">{{ String.fromCharCode(64 + ci) }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, ri) in (excel.excelData.value.sheets[excel.excelData.value.activeSheet]?.rows || [])" :key="ri">
                  <td class="border border-app bg-app p-1 text-center text-app-muted text-xs sticky left-0 z-10 select-none" @click="excel.selectCell(ri, 0)">{{ ri + 1 }}</td>
                  <td v-for="(cell, ci) in row" :key="ci"
                    :class="['border border-app p-0 relative group cursor-cell transition-shadow', excel.selectedCell.value?.ri === ri && excel.selectedCell.value?.ci === ci ? 'ring-2 ring-blue-400 ring-inset bg-blue-50/30' : '']"
                    :style="cell.color ? {background: cell.color} : {}"
                    @click="excel.selectCell(ri, ci)"
                    @contextmenu.prevent="excel.showContextMenu($event, ri, ci)"
                  >
                    <div :contenteditable="true" class="outline-none p-1 min-h-[26px] text-xs"
                      @focus="(e:any) => { excel.selectCell(ri, ci); e.target.textContent = cell.v }"
                      @blur="(e:any) => excel.updateCell(excel.excelData.value!.activeSheet, ri, ci, e.target.textContent || '')"
                      @keydown.tab.prevent="excelCellBlur($event); excel.moveSelection(0, $event.shiftKey ? -1 : 1)"
                      @keydown.enter.prevent="excelCellBlur($event); excel.moveSelection($event.shiftKey ? -1 : 1, 0)"
                      @keydown.ctrl.c.prevent="excel.copyCell()"
                      @keydown.ctrl.v.prevent="excel.pasteCell()">
                      <span v-if="cell.f" class="text-blue-500 font-mono" :title="'公式: '+cell.f">{{ cell.v }}</span>
                      <span v-else>{{ cell.v }}</span>
                    </div>
                    <!-- Color picker on hover -->
                    <div class="absolute right-0.5 top-0.5 opacity-0 group-hover:opacity-100 transition-opacity z-20">
                      <input type="color" :value="cell.color || '#ffffff'" class="w-3.5 h-3.5 border-0 p-0 cursor-pointer rounded" @change="(e:any) => { excel.setCellColor(ri, ci, e.target.value) }" @click.stop />
                    </div>
                  </td>
                  <td v-for="ci in Math.max(0, (excel.excelData.value.sheets[excel.excelData.value.activeSheet]?.max_col || 1) - (row.length || 0))" :key="'e'+ci" class="border border-app p-0.5 min-w-[70px]"></td>
                </tr>
              </tbody>
            </table>
          </div>
          <!-- Cell info bar -->
          <div class="mt-1 flex items-center gap-2 text-xs text-app-muted shrink-0">
            <span v-if="excel.selectedCell.value">单元格：{{ String.fromCharCode(65 + excel.selectedCell.value.ci) }}{{ excel.selectedCell.value.ri + 1 }}</span>
            <span v-else>点击单元格开始编辑 — Tab/Enter 切换单元格，Ctrl+C/V 复制粘贴</span>
            <span v-if="excel.copiedCell.value" class="ml-auto flex items-center gap-1"><Copy class="w-3 h-3" />已复制</span>
          </div>
          <!-- Context menu -->
          <Teleport to="body">
            <div v-if="excel.contextMenu.value.show"
              class="fixed z-[9999] bg-surface rounded-lg shadow-xl border border-app py-1 min-w-[170px]"
              :style="{ left: excel.contextMenu.value.x + 'px', top: excel.contextMenu.value.y + 'px' }"
              @click.stop
            >
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" @click="excel.copyCell()"><Copy class="w-3.5 h-3.5" />复制</button>
              <button class="w-full px-3 py-1.5 text-xs text-left hover:bg-app-hover flex items-center gap-2" :disabled="!excel.copiedCell.value" @click="excel.pasteCell()"><Clipboard class="w-3.5 h-3.5" />粘贴</button>
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
          <el-button class="!m-0 h-20 flex flex-col gap-2" :loading="ai.isProcessing.value" @click="openQualityCheckDialog"><RefreshCw class="w-5 h-5 text-app-primary" /><span>文档质检</span></el-button>
          <el-button class="!m-0 h-20 flex flex-col gap-2" @click="runLogicCompletion" :loading="ai.isProcessing.value"><Zap class="w-5 h-5 text-orange-600" /><span>逻辑补完</span></el-button>
        </div>
      </div>
      <div class="flex-1 p-4 flex flex-col min-h-0">
        <div class="flex items-center justify-between mb-2">
          <label class="text-xs font-bold text-app-muted uppercase tracking-wider">AI 执行结果</label>
          <div class="flex gap-1">
            <el-button link @click="copyResult"><Copy class="w-3.5 h-3.5" /></el-button>
            <el-button v-if="ai.aiResult.value" link @click="clearResult"><Trash2 class="w-3.5 h-3.5 text-red-400" /></el-button>
          </div>
        </div>
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
    </div>

    <!-- Dialogs -->
    <NewDraftDialog v-model:visible="showNewDraftDialog" @create="createNewDraft" />

    <ImageDialog v-model:visible="showImagePrompt" @insert="insertImageFromUrl" />

    <ImitateDialog
      v-model:visible="showImitateDialog"
      @submit="runImitateAndCreate"
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
      :kb-stats="kb.kbStats.value"
      :is-uploading-k-b="kb.isUploadingKB.value"
      :chunk-size-min="kb.chunkSizeMin.value"
      :chunk-size-max="kb.chunkSizeMax.value"
      :show-chunk-size-dialog="kb.showChunkSizeDialog.value"
      :folder-path="kb.folderPath.value"
      :scanned-files="kb.scannedFiles.value"
      :selected-files="kb.selectedFiles.value"
      :is-scanning="kb.isScanning.value"
      :import-progress="kb.importProgress.value"
      :is-importing="kb.isImporting.value"
      :is-paused="kb.isPaused.value"
      @update:chunk-size-min="(v:number) => kb.chunkSizeMin.value = v"
      @update:chunk-size-max="(v:number) => kb.chunkSizeMax.value = v"
      @update:show-chunk-size-dialog="(v:boolean) => kb.showChunkSizeDialog.value = v"
      @update:folder-path="(v:string) => kb.folderPath.value = v"
      @upload-file="handleKBUpload"
      @scan-folder="kb.scanFolder"
      @import-folder="kb.importFolder"
      @toggle-file="kb.toggleFile"
      @select-all-files="kb.selectAllFiles"
      @deselect-all-files="kb.deselectAllFiles"
      @toggle-by-type="kb.toggleFilesByType"
      @delete-document="handleKBDelete"
      @clear-all="handleKBClear"
      @save-chunk-size="kb.saveChunkSize"
      @pause-import="kb.pauseImport"
      @resume-import="kb.resumeImport"
      @stop-import="kb.stopImport"
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
      @update:new-svn-name="(v:string) => tools.newSvnName.value = v"
      @update:new-svn-path="(v:string) => tools.newSvnPath.value = v"
      @update:new-nav-name="(v:string) => tools.newNavName.value = v"
      @update:new-nav-path="(v:string) => tools.newNavPath.value = v"
      @update:show-add-svn-dialog="(v:boolean) => tools.showAddSvnDialog.value = v"
      @update:show-add-nav-dialog="(v:boolean) => tools.showAddNavDialog.value = v"
      @add-svn="handleAddSvn"
      @remove-svn="tools.removeSvn"
      @run-svn-update="handleRunSvnUpdate"
      @add-nav="tools.addNav"
      @remove-nav="tools.removeNav"
      @open-nav-item="tools.openNavItem"
    />
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
</style>
