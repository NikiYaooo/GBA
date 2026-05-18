<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  importFiles: [files: { path: string; folderId?: string }[]]
}>()

interface ScannedFile {
  filename: string
  relative_path: string
  folder_name: string
  full_path: string
  size: number
}

const props = defineProps<{
  activeProjectId: string
  activeFolderId?: string
}>()

const folderPath = ref('')
const scannedFiles = ref<ScannedFile[]>([])
const selectedPaths = ref<Set<string>>(new Set())
const isScanning = ref(false)
const isImporting = ref(false)
const fileTypeFilter = ref<string>('all')

const fileTypes = [
  { key: 'all', label: '全部' },
  { key: 'docx', label: 'docx' },
  { key: 'doc', label: 'doc' },
  { key: 'xlsx', label: 'xlsx' },
  { key: 'xls', label: 'xls' },
]

const filteredFiles = computed(() => {
  if (fileTypeFilter.value === 'all') return scannedFiles.value
  const ext = '.' + fileTypeFilter.value
  return scannedFiles.value.filter(f => f.filename.toLowerCase().endsWith(ext))
})

const selectedCount = computed(() => {
  return filteredFiles.value.filter(f => selectedPaths.value.has(f.full_path)).length
})

const allSelected = computed(() => {
  return filteredFiles.value.length > 0 && filteredFiles.value.every(f => selectedPaths.value.has(f.full_path))
})

const toggleSelectAll = () => {
  if (allSelected.value) {
    for (const f of filteredFiles.value) {
      selectedPaths.value.delete(f.full_path)
    }
  } else {
    for (const f of filteredFiles.value) {
      selectedPaths.value.add(f.full_path)
    }
  }
}

const toggleFile = (path: string) => {
  if (selectedPaths.value.has(path)) {
    selectedPaths.value.delete(path)
  } else {
    selectedPaths.value.add(path)
  }
}

const onSelectFolder = async () => {
  const api = (window as any).electronAPI
  if (api?.selectFolder) {
    const fp = await api.selectFolder()
    if (fp) {
      folderPath.value = typeof fp === 'string' ? fp : (fp.filePath || fp.path || String(fp))
    }
  } else {
    ElMessage.warning('当前环境不支持选择文件夹，请手动输入路径')
  }
}

const onScan = async () => {
  if (!folderPath.value.trim()) { ElMessage.warning('请先选择文件夹'); return }
  isScanning.value = true
  scannedFiles.value = []
  selectedPaths.value = new Set()
  try {
    const r = await axios.post(apiUrl('/api/kb/scan-directory'), { path: folderPath.value.trim() })
    if (r.data.success && r.data.data?.files) {
      scannedFiles.value = r.data.data.files
      ElMessage.success(`扫描完成，共 ${scannedFiles.value.length} 个文件`)
    }
  } catch (e: any) {
    ElMessage.error('扫描失败: ' + getErrMsg(e))
  } finally {
    isScanning.value = false
  }
}

const onImport = async () => {
  const selected = [...filteredFiles.value].filter(f => selectedPaths.value.has(f.full_path))
  if (selected.length === 0) { ElMessage.warning('请先选择要导入的文件'); return }

  try {
    await ElMessageBox.confirm(
      `确定导入选中的 ${selected.length} 个文件？`,
      '批量导入',
      { confirmButtonText: '导入', cancelButtonText: '取消', type: 'info' }
    )
  } catch { return }

  isImporting.value = true
  try {
    const importList: { path: string; folderId?: string }[] = selected.map(f => ({
      path: f.full_path,
      folderId: props.activeFolderId || undefined,
    }))
    emit('importFiles', importList)
    visible.value = false
  } finally {
    isImporting.value = false
  }
}

const totalSize = () => {
  const selected = [...filteredFiles.value].filter(f => selectedPaths.value.has(f.full_path))
  const total = selected.reduce((s, f) => s + f.size, 0)
  if (total >= 1048576) return (total / 1048576).toFixed(1) + ' MB'
  if (total >= 1024) return (total / 1024).toFixed(1) + ' KB'
  return total + ' B'
}

const getFileExt = (filename: string) => {
  const dot = filename.lastIndexOf('.')
  return dot >= 0 ? filename.slice(dot).toLowerCase() : ''
}

const formatFileSize = (bytes: number) => {
  if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB'
  if (bytes >= 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return bytes + ' B'
}

const reset = () => {
  scannedFiles.value = []
  selectedPaths.value = new Set()
  folderPath.value = ''
  fileTypeFilter.value = 'all'
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="批量导入文档"
    width="800px"
    top="5vh"
    @closed="reset"
  >
    <!-- Folder path input -->
    <div class="flex gap-2 mb-4">
      <el-input v-model="folderPath" placeholder="选择或输入文件夹路径..." />
      <el-button @click="onSelectFolder">选择文件夹</el-button>
      <el-button type="primary" :loading="isScanning" @click="onScan">扫描</el-button>
    </div>

    <!-- Scanning state -->
    <div v-if="isScanning" class="text-center py-8 text-app-muted text-sm">扫描中...</div>

    <!-- File list after scan -->
    <template v-else-if="scannedFiles.length > 0">
      <!-- File type filter -->
      <div class="flex items-center gap-2 mb-3">
        <el-checkbox
          :model-value="allSelected"
          :indeterminate="filteredFiles.length > 0 && filteredFiles.some(f => selectedPaths.has(f.full_path)) && !allSelected"
          @change="toggleSelectAll"
        >
          <span class="text-sm">全选 / 取消全选</span>
        </el-checkbox>
        <div class="flex-1" />
        <div class="flex gap-1">
          <el-button
            v-for="ft in fileTypes" :key="ft.key"
            size="small"
            :type="fileTypeFilter === ft.key ? 'primary' : 'default'"
            @click="fileTypeFilter = ft.key"
          >{{ ft.label }}</el-button>
        </div>
      </div>

      <div class="text-xs text-app-muted mb-2">
        共 {{ filteredFiles.length }} 个文件，已选 {{ [...filteredFiles].filter(f => selectedPaths.has(f.full_path)).length }} 个（{{ totalSize() }}）
      </div>

      <!-- File list -->
      <div class="max-h-[400px] overflow-y-auto border border-app rounded-lg">
        <div
          v-for="(f, i) in filteredFiles" :key="i"
          class="flex items-center gap-3 px-3 py-2 border-b border-app last:border-b-0 hover:bg-app-hover cursor-pointer text-sm"
          @click="toggleFile(f.full_path)"
        >
          <el-checkbox
            :model-value="selectedPaths.has(f.full_path)"
            @click.stop
            @change="() => toggleFile(f.full_path)"
          />
          <span class="flex-1 truncate">{{ f.filename }}</span>
          <span class="text-xs text-app-muted shrink-0">{{ formatFileSize(f.size) }}</span>
          <el-tag size="small" :type="getFileExt(f.filename) === '.docx' || getFileExt(f.filename) === '.doc' ? 'primary' : 'success'">
            {{ getFileExt(f.filename) }}
          </el-tag>
        </div>
      </div>

      <div v-if="filteredFiles.length === 0" class="text-center py-8 text-app-muted text-sm">
        没有匹配的文件类型
      </div>
    </template>

    <!-- Empty state -->
    <div v-else-if="folderPath" class="text-center py-8 text-app-muted text-sm">
      点击"扫描"查看文件夹中的文档
    </div>

    <div v-else class="text-center py-8 text-app-muted text-sm">
      选择文件夹后扫描，支持 .docx / .doc / .xlsx / .xls / .md / .txt / .pdf
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        type="primary"
        :loading="isImporting"
        :disabled="[...filteredFiles].filter(f => selectedPaths.has(f.full_path)).length === 0"
        @click="onImport"
      >
        导入 {{ [...filteredFiles].filter(f => selectedPaths.has(f.full_path)).length }} 个文件
      </el-button>
    </template>
  </el-dialog>
</template>
