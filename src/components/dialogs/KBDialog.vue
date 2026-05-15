<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Database, FileText, Pen, Folder, FolderOpen } from 'lucide-vue-next'
import { ElMessageBox } from 'element-plus'
import type { KBProject, KBFolder, KBDocumentV2, KBStats, KBBackup, KBSearchResult } from '@/types'

const visible = defineModel<boolean>('visible', { default: false })

const props = defineProps<{
  projects: KBProject[]
  activeProjectId: string
  folders: KBFolder[]
  documents: KBDocumentV2[]
  kbStats: KBStats
  searchResults: KBSearchResult[]
  backups: KBBackup[]
  vocabList: string[]

  isUploadingKB: boolean
  searchLoading: boolean
  loading: boolean
}>()

const emit = defineEmits<{
  // 项目
  loadProjects: []
  switchProject: [id: string]
  createProject: [name: string, description?: string, model?: string]
  deleteProject: [id: string]
  renameProject: [id: string, name: string]

  // 文件夹
  loadFolders: []
  createFolder: [name: string]
  renameFolder: [id: string, name: string]
  deleteFolder: [id: string]

  // 文档
  loadDocuments: [folderId?: string]
  uploadFile: [file: File, folderId?: string]
  updateDocument: [docId: string, updates: Record<string, any>]
  deleteDocument: [docId: string]

  // 检索
  search: [query: string, topK?: number]
  fuzzySearch: [keyword: string]

  // 备份
  loadBackups: []
  createBackup: []
  restoreBackup: [filename: string]

  // 词库
  loadVocab: []
  addVocab: [word: string]
  removeVocab: [word: string]

  // 子对话框
  openProjectDialog: []
  openNoteDialog: [docId: string]
  openBackupDialog: []
  openVocabDialog: []
  openChunkSizeDialog: []
  openBatchImportDialog: []
}>()

const activeFolder = ref('')
const searchQuery = ref('')

const currentProjectName = computed(() => {
  const p = props.projects.find(p => p.id === props.activeProjectId)
  return p ? p.name : ''
})

const activeFolderName = computed(() => {
  const f = props.folders.find(f => f.id === activeFolder.value)
  return f ? f.name : ''
})

watch(() => props.activeProjectId, () => {
  activeFolder.value = ''
  searchQuery.value = ''
})

const formatSize = (bytes: number) => {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

const onFolderChange = (tabName: string) => {
  emit('loadDocuments', tabName || undefined)
}

const onNewFolder = async () => {
  try {
    const { value } = await ElMessageBox.prompt('请输入文件夹名称', '新建文件夹')
    if (value) emit('createFolder', value)
  } catch { /* cancelled */ }
}

const onDrop = (e: DragEvent) => {
  const files = e.dataTransfer?.files
  if (!files) return
  for (let i = 0; i < files.length; i++) {
    const ext = files[i].name.split('.').pop()?.toLowerCase()
    if (!['docx', 'md', 'txt'].includes(ext || '')) continue
    emit('uploadFile', files[i], activeFolder.value || undefined)
  }
}

const onUpload = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.docx,.md,.txt'
  input.multiple = true
  input.onchange = (e: any) => {
    for (let i = 0; i < e.target.files.length; i++) {
      emit('uploadFile', e.target.files[i], activeFolder.value || undefined)
    }
  }
  input.click()
}

const onProjectContextMenu = async (e: MouseEvent, project: KBProject) => {
  e.preventDefault()
  if (props.projects.length <= 1) {
    ElMessageBox.alert('只有一个项目，无法删除', '提示', { confirmButtonText: '关闭' })
    return
  }
  const action = await ElMessageBox.prompt(
    `项目: ${project.name}\n模型: ${project.embedding_model}\n文档: ${project.doc_count || 0}\n\n输入 "delete" 确认删除此项目，或留空取消：`,
    '项目操作',
    { confirmButtonText: '删除', cancelButtonText: '取消', inputPlaceholder: '输入 delete 确认删除' }
  ).then(({ value }) => value?.trim().toLowerCase() === 'delete' ? 'delete' : null)
   .catch(() => null)
  if (action === 'delete') {
    emit('deleteProject', project.id)
  }
}

const onFolderContextMenu = async (e: MouseEvent, folder: KBFolder) => {
  e.preventDefault()
  closeContextMenu()
  contextMenuTarget.value = folder
  contextMenuPos.value = { x: e.clientX, y: e.clientY }
  showContextMenu.value = true
}

const showContextMenu = ref(false)
const contextMenuPos = ref({ x: 0, y: 0 })
const contextMenuTarget = ref<KBFolder | null>(null)

const closeContextMenu = () => {
  showContextMenu.value = false
  contextMenuTarget.value = null
}

const onContextMenuRename = async () => {
  const folder = contextMenuTarget.value
  closeContextMenu()
  if (!folder) return
  try {
    const { value } = await ElMessageBox.prompt('请输入新名称', '重命名文件夹', { inputValue: folder.name })
    if (value && value !== folder.name) emit('renameFolder', folder.id, value)
  } catch { /* cancelled */ }
}

const onContextMenuDelete = async () => {
  const folder = contextMenuTarget.value
  closeContextMenu()
  if (!folder) return
  try {
    await ElMessageBox.confirm(
      `确定删除文件夹 "${folder.name}"？文档不会被删除，仅取消分类。`,
      '删除文件夹',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    emit('deleteFolder', folder.id)
  } catch { /* cancelled */ }
}

const filteredDocuments = computed(() => {
  if (!searchQuery.value) return props.documents
  const q = searchQuery.value.toLowerCase()
  return props.documents.filter(d => d.filename.toLowerCase().includes(q))
})

// 点击其他地方关闭右键菜单
const onContentClick = () => {
  if (showContextMenu.value) closeContextMenu()
}

const onOpen = () => {
  emit('loadProjects')
  emit('loadFolders')
  emit('loadDocuments')
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="知识库管理"
    width="900px"
    top="5vh"
    class="kb-dialog"
    @open="onOpen"
    @click="onContentClick"
  >
    <div class="kb-layout" style="display: flex; gap: 16px; min-height: 420px;">
      <!-- Left: Project panel -->
      <div
        class="kb-project-panel"
        style="width: 180px; flex-shrink: 0; border-right: 1px solid var(--el-border-color-light); padding-right: 12px;"
      >
        <div class="text-sm font-medium mb-2">项目列表</div>
        <div class="space-y-0.5">
          <div
            v-for="p in projects" :key="p.id"
            :class="[
              'flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer text-sm',
              p.id === activeProjectId
                ? 'bg-primary-light text-primary'
                : 'hover:bg-app-hover'
            ]"
            @click="emit('switchProject', p.id)"
            @contextmenu.prevent="onProjectContextMenu($event, p)"
          >
            <Database class="w-4 h-4" />
            <span class="truncate flex-1">{{ p.name }}</span>
            <span class="text-xs text-app-muted">{{ p.doc_count || 0 }}</span>
          </div>
        </div>
        <el-button size="small" class="mt-2 w-full" @click="emit('openProjectDialog')">
          + 新建
        </el-button>
      </div>

      <!-- Right: Content area -->
      <div class="kb-content" style="flex: 1; min-width: 0;">
        <!-- Breadcrumb + new folder button -->
        <div class="flex items-center gap-2 mb-3">
          <span
            class="text-sm font-medium cursor-pointer"
            :class="!activeFolder ? 'text-primary' : 'text-app-muted hover:text-primary'"
            @click="activeFolder=''; onFolderChange('')"
          >全部文档</span>
          <template v-if="activeFolder">
            <span class="text-app-muted text-xs">/</span>
            <span class="text-sm font-medium text-primary">{{ activeFolderName }}</span>
          </template>
          <div class="flex-1" />
          <el-button size="small" @click="onNewFolder">+ 文件夹</el-button>
        </div>

        <!-- Search bar -->
        <div class="flex gap-2 mb-3">
          <el-input
            v-model="searchQuery"
            size="small"
            placeholder="搜索文档名..."
            clearable
            @clear="searchQuery = ''"
          />
        </div>

        <!-- Upload drop zone -->
        <div
          class="border-2 border-dashed rounded-lg p-3 text-center text-xs text-app-muted mb-3"
          @dragover.prevent
          @drop.prevent="onDrop"
        >
          拖拽 .docx / .md / .txt 文件到此处
        </div>

        <!-- Action buttons -->
        <div class="flex gap-2 mb-3">
          <el-button size="small" type="primary" :loading="isUploadingKB" @click="onUpload">
            上传文档
          </el-button>
          <el-button size="small" @click="emit('openBatchImportDialog')">
            批量导入
          </el-button>
          <el-button size="small" @click="emit('openChunkSizeDialog')">
            切片设置
          </el-button>
        </div>

        <!-- Folder + Document list -->
        <div class="max-h-[300px] overflow-y-auto" @click="onContentClick">
          <!-- Back to root when inside a folder -->
          <div
            v-if="activeFolder"
            class="flex items-center gap-3 p-2 border-b text-sm hover:bg-app-hover cursor-pointer"
            @click="activeFolder=''; onFolderChange('')"
          >
            <FolderOpen class="w-4 h-4 text-app-muted shrink-0" />
            <span class="text-app-muted">.. 返回上级</span>
          </div>

          <!-- Folder items (only visible at root level) -->
          <template v-if="!activeFolder">
            <div
              v-for="f in folders" :key="f.id"
              class="flex items-center gap-3 p-2 border-b text-sm hover:bg-app-hover cursor-pointer"
              @click="onFolderChange(f.id); activeFolder = f.id"
              @contextmenu.prevent="onFolderContextMenu($event, f)"
            >
              <Folder class="w-4 h-4 text-yellow-500 shrink-0" />
              <span class="flex-1 truncate">{{ f.name }}</span>
              <span class="text-xs text-app-muted">文件夹</span>
            </div>
          </template>

          <!-- Document items (filtered by search) -->
          <div
            v-for="doc in filteredDocuments" :key="doc.id"
            class="flex items-center gap-3 p-2 border-b text-sm hover:bg-app-hover"
          >
            <FileText class="w-4 h-4 text-app-muted shrink-0" />
            <span class="flex-1 truncate">{{ doc.filename }}</span>
            <el-tooltip v-if="doc.note" :content="doc.note" placement="top">
              <el-icon class="cursor-pointer text-app-primary" @click="emit('openNoteDialog', doc.id)">
                <Pen />
              </el-icon>
            </el-tooltip>
            <el-icon v-else class="cursor-pointer text-app-muted" @click="emit('openNoteDialog', doc.id)">
              <Pen />
            </el-icon>
            <span class="text-xs text-app-muted">{{ doc.chunk_count || 0 }} 块</span>
            <span class="text-xs text-app-muted">{{ formatSize(doc.file_size) }}</span>
            <el-button link size="small" type="danger" @click="emit('deleteDocument', doc.id)">删除</el-button>
          </div>
          <div v-if="!activeFolder && folders.length === 0 && filteredDocuments.length === 0" class="text-center py-8 text-app-muted text-sm">
            {{ searchQuery ? '没有匹配的文档' : '暂无文档' }}
          </div>
          <div v-if="activeFolder && filteredDocuments.length === 0" class="text-center py-8 text-app-muted text-sm">
            此文件夹为空
          </div>
        </div>

        <!-- Context menu for folders -->
        <teleport to="body">
          <!-- Backdrop to catch clicks outside -->
          <div
            v-if="showContextMenu"
            class="fixed inset-0"
            style="z-index: 99998"
            @click="closeContextMenu"
          />
          <div
            v-if="showContextMenu"
            class="fixed"
            :style="{ left: contextMenuPos.x + 'px', top: contextMenuPos.y + 'px', zIndex: 99999 }"
          >
            <div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg border py-1 min-w-[120px]">
              <div
                class="px-4 py-2 text-sm cursor-pointer hover:bg-app-hover"
                @click="onContextMenuRename"
              >重命名</div>
              <div
                class="px-4 py-2 text-sm cursor-pointer hover:bg-app-hover text-red-500"
                @click="onContextMenuDelete"
              >删除</div>
            </div>
          </div>
        </teleport>
      </div>
    </div>

    <!-- Bottom status bar -->
    <div class="flex items-center justify-between pt-3 mt-3 border-t text-xs text-app-muted">
      <div>
        项目: {{ currentProjectName }} | {{ kbStats.total_documents }} 文档 | {{ kbStats.total_chunks }} 块 | 已用 {{ formatSize(kbStats.total_size_bytes) }}
      </div>
      <div class="flex gap-2">
        <el-button link size="small" @click="emit('openVocabDialog')">自定义词库</el-button>
        <el-button link size="small" @click="emit('openBackupDialog')">备份管理</el-button>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.kb-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
}
</style>
