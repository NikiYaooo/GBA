<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
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

interface FolderOption {
  id: string
  name: string
}

const props = defineProps<{
  activeProjectId: string
  folders: FolderOption[]
}>()

const folderPath = ref('')
const scannedFiles = ref<ScannedFile[]>([])
const isScanning = ref(false)
const isImporting = ref(false)

// Group files by folder_name, and map to KB folders
const fileGroups = ref<{ folderName: string; files: ScannedFile[]; targetFolderId: string; createNew: boolean }[]>([])

const onSelectFolder = async () => {
  const api = (window as any).electronAPI
  if (api?.selectFolder) {
    const fp = await api.selectFolder()
    if (fp) folderPath.value = fp
  } else {
    ElMessage.warning('当前环境不支持选择文件夹，请手动输入路径')
  }
}

const onScan = async () => {
  if (!folderPath.value.trim()) { ElMessage.warning('请先选择文件夹'); return }
  isScanning.value = true
  try {
    const r = await axios.post(apiUrl('/api/kb/scan-directory'), { path: folderPath.value.trim() })
    if (r.data.success && r.data.data?.files) {
      scannedFiles.value = r.data.data.files
      // Group by folder_name and map to KB folders
      const groups: Record<string, ScannedFile[]> = {}
      for (const f of scannedFiles.value) {
        const key = f.folder_name || ''
        if (!groups[key]) groups[key] = []
        groups[key].push(f)
      }
      fileGroups.value = Object.entries(groups).map(([folderName, files]) => {
        const existing = props.folders.find(f => f.name === folderName)
        return {
          folderName: folderName || '未分类',
          files,
          targetFolderId: existing?.id || '',
          createNew: !existing && !!folderName,
        }
      })
      ElMessage.success(`扫描完成，共 ${scannedFiles.value.length} 个文件`)
    }
  } catch (e: any) {
    ElMessage.error('扫描失败: ' + getErrMsg(e))
  } finally {
    isScanning.value = false
  }
}

const onImport = async () => {
  if (scannedFiles.value.length === 0) { ElMessage.warning('没有可导入的文件'); return }
  isImporting.value = true
  try {
    const importList: { path: string; folderId?: string }[] = []
    for (const group of fileGroups.value) {
      for (const f of group.files) {
        importList.push({ path: f.full_path, folderId: group.targetFolderId || undefined })
      }
    }
    emit('importFiles', importList)
    visible.value = false
  } finally {
    isImporting.value = false
  }
}

const totalSize = () => {
  const total = scannedFiles.value.reduce((s, f) => s + f.size, 0)
  if (total >= 1048576) return (total / 1048576).toFixed(1) + ' MB'
  if (total >= 1024) return (total / 1024).toFixed(1) + ' KB'
  return total + ' B'
}

const reset = () => {
  scannedFiles.value = []
  fileGroups.value = []
  folderPath.value = ''
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="批量导入文档"
    width="750px"
    top="8vh"
    @closed="reset"
  >
    <!-- Folder selection -->
    <div class="flex gap-2 mb-4">
      <el-input v-model="folderPath" placeholder="选择或输入文件夹路径..." />
      <el-button @click="onSelectFolder">选择文件夹</el-button>
      <el-button type="primary" :loading="isScanning" @click="onScan">扫描</el-button>
    </div>

    <!-- Scan results -->
    <div v-if="isScanning" class="text-center py-8 text-app-muted text-sm">扫描中...</div>

    <div v-else-if="scannedFiles.length > 0">
      <div class="text-sm text-app-muted mb-3">
        共 {{ scannedFiles.length }} 个文件（{{ totalSize() }}），按子目录分类：
      </div>

      <div class="space-y-3 max-h-[350px] overflow-y-auto">
        <div v-for="(group, gi) in fileGroups" :key="gi" class="border rounded p-3">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-sm font-medium">{{ group.folderName }}</span>
            <span class="text-xs text-app-muted">({{ group.files.length }} 个文件)</span>
            <span v-if="group.createNew" class="text-xs text-orange-500">将自动创建文件夹</span>
            <el-select
              v-model="group.targetFolderId"
              size="small"
              clearable
              placeholder="选择目标文件夹"
              class="!w-36 ml-auto"
            >
              <el-option v-for="f in folders" :key="f.id" :label="f.name" :value="f.id" />
            </el-select>
          </div>
          <div class="text-xs text-app-muted space-y-0.5 ml-2">
            <div v-for="(f, fi) in group.files" :key="fi" class="truncate">
              {{ f.filename }}
              <span class="ml-2">({{ (f.size / 1024).toFixed(1) }} KB)</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="folderPath" class="text-center py-8 text-app-muted text-sm">
      点击"扫描"查看文件夹中的文档
    </div>

    <div v-else class="text-center py-8 text-app-muted text-sm">
      选择文件夹后扫描，支持 .docx / .md / .txt / .xlsx / .pdf
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        type="primary"
        :loading="isImporting"
        :disabled="scannedFiles.length === 0"
        @click="onImport"
      >
        导入 {{ scannedFiles.length }} 个文件
      </el-button>
    </template>
  </el-dialog>
</template>
