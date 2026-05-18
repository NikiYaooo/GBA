<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { apiUrl, getErrMsg } from '@/utils/api'
import { Save, Plus, X, Image as ImageIcon } from 'lucide-vue-next'

const visible = defineModel<boolean>('visible', { default: false })

interface ImageLibRecord {
  id: string
  name: string
  filename: string
  created_at: string
}

const props2 = defineProps<{
  libraryImageDataUri?: string
  designPromptTemplate?: string
  libraryImages?: ImageLibRecord[]
}>()

const emit2 = defineEmits<{
  saveToLibrary: [dataUri: string]
}>()

// === 生图模型列表 ===
const imageModels = [
  { name: 'GPT-Image 2', type: 'cloud' },
  { name: 'Qwen-Image 2', type: 'cloud' },
  { name: 'Midjourney', type: 'cloud' },
  { name: 'Google Banana', type: 'cloud' },
  { name: '豆包Seedream', type: 'cloud' },
  { name: 'Stable Diffusion（本地）', type: 'local' },
]

const selectedModel = ref('GPT-Image 2')
const rawPrompt = ref('')
const enhancedPrompt = ref('')
const isEnhancing = ref(false)
const isGenerating = ref(false)

// === 图片列表 ===
interface ImageItem {
  data_uri: string
  revised_prompt?: string
}
const images = ref<ImageItem[]>([])
const currentIndex = ref(0)
// 库图预览（不加入 images 数组，避免产生生成记录）
const libraryPreviewData = ref<string | null>(null)
const currentImage = computed(() => {
  // 库图预览优先
  if (libraryPreviewData.value) return { data_uri: libraryPreviewData.value, revised_prompt: '' }
  if (images.value.length > 0) return images.value[currentIndex.value] || null
  return null
})


// === 修改模式 ===
const isModifyMode = ref(false)
const modifyPrompt = ref('')
const isEditing = ref(false)
const brushSize = ref(20)
const isErasing = ref(false)
const toggleErase = () => { isErasing.value = !isErasing.value }
const paintedVersion = ref(0)

// === 参考图片 ===
const showReferenceStrip = ref(false)
const referenceImages = ref<string[]>([])
const referenceUploadRef = ref<HTMLInputElement | null>(null)
const addReferenceImage = () => { referenceUploadRef.value?.click() }
const onReferenceUpload = (e: Event) => {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) { ElMessage.warning('请选择图片文件'); return }
  const reader = new FileReader()
  reader.onload = () => { referenceImages.value.push(reader.result as string) }
  reader.readAsDataURL(file)
  ;(e.target as HTMLInputElement).value = ''
}
const removeReferenceImage = (index: number) => { referenceImages.value.splice(index, 1) }

// === 图片库 ===
const libraryDataCache = ref<Record<string, string>>({})
const loadingLibraryId = ref('')
const loadLibraryImage = async (id: string) => {
  if (libraryDataCache.value[id]) {
    images.value = []
    libraryPreviewData.value = libraryDataCache.value[id]
    return
  }
  loadingLibraryId.value = id
  try {
    const r = await axios.get(apiUrl(`/api/images/library/${id}/data`))
    if (r.data.success && r.data.data?.data_uri) {
      libraryDataCache.value[id] = r.data.data.data_uri
      images.value = []
      libraryPreviewData.value = r.data.data.data_uri
    } else {
      ElMessage.warning('加载图片失败')
    }
  } catch {
    ElMessage.error('加载图片失败')
  } finally {
    loadingLibraryId.value = ''
  }
}

// Canvas refs
const canvasRef = ref<HTMLCanvasElement | null>(null)
const editCanvasRef = ref<HTMLCanvasElement | null>(null)
let ctx: CanvasRenderingContext2D | null = null
let editCtx: CanvasRenderingContext2D | null = null
let isDrawing = false
const mousePos = ref({ x: -1, y: -1 })
const canvasContainerStyle = ref({ height: '400px' })

// === 提示词增强 ===
const enhancePrompt = async () => {
  if (!rawPrompt.value.trim()) { ElMessage.warning('请输入生图提示'); return }
  isEnhancing.value = true
  try {
    const r = await axios.post(apiUrl('/api/image/enhance-prompt'), { text: rawPrompt.value.trim() })
    if (r.data.success && r.data.data?.enhanced) {
      enhancedPrompt.value = r.data.data.enhanced
    } else {
      enhancedPrompt.value = rawPrompt.value
    }
  } catch (e: any) {
    ElMessage.warning('提示增强失败: ' + getErrMsg(e))
    enhancedPrompt.value = rawPrompt.value
  } finally {
    isEnhancing.value = false
  }
}

// === 生图 ===
const generate = async () => {
  const promptText = rawPrompt.value.trim()
  if (!promptText) { ElMessage.warning('请输入生图提示'); return }
  isGenerating.value = true
  try {
    // Auto-enhance prompt first
    enhancedPrompt.value = ''
    try {
      const r = await axios.post(apiUrl('/api/image/enhance-prompt'), { text: promptText })
      if (r.data.success && r.data.data?.enhanced) {
        enhancedPrompt.value = r.data.data.enhanced
      }
    } catch { /* use raw prompt */ }
    let finalPrompt = enhancedPrompt.value || promptText
    // 如果"设计"职业有生图模板，将增强后的prompt填入模板占位位置
    const template = props2.designPromptTemplate
    if (template) {
      const placeholder = '{{填入原画设定、人设、场景、风格、构图、情绪要求}}'
      if (template.includes(placeholder)) {
        finalPrompt = template.replace(placeholder, finalPrompt)
      }
    }
    const r = await axios.post(apiUrl('/api/image/generate'), {
      prompt: finalPrompt,
      model: selectedModel.value,
      reference_images: referenceImages.value.length > 0 ? referenceImages.value : undefined,
    })
    if (r.data.success && r.data.data?.data_uri) {
      const newImg = { data_uri: r.data.data.data_uri, revised_prompt: r.data.data.revised_prompt }
      images.value = [newImg]
      currentIndex.value = 0
      libraryPreviewData.value = null
      // 自动保存到图片库
      emit2('saveToLibrary', newImg.data_uri)
      ElMessage.success('生图完成')
    } else {
      ElMessage.warning(r.data.message || '生图失败')
    }
  } catch (e: any) {
    ElMessage.error('生图失败: ' + getErrMsg(e))
  } finally {
    isGenerating.value = false
  }
}

// === 保存图片 ===
const saveImage = async () => {
  const img = currentImage.value
  if (!img) return
  const api = (window as any).electronAPI
  if (api?.saveFileAs) {
    const result = await api.saveFileAs(img.data_uri, 'image.png')
    if (result.success) ElMessage.success('已保存')
    else if (!result.error?.includes('Canceled')) ElMessage.warning('保存失败')
  } else {
    // Browser fallback: download link
    const a = document.createElement('a')
    a.href = img.data_uri
    a.download = `generated_${Date.now()}.png`
    a.click()
  }
}

// === 修改模式 ===
const enterModifyMode = async () => {
  if (!currentImage.value) return
  // 如果当前显示的是库图预览，先加入 images 以便编辑
  if (images.value.length === 0 && libraryPreviewData.value) {
    images.value.push({ data_uri: libraryPreviewData.value, revised_prompt: '' })
    currentIndex.value = 0
  }
  isModifyMode.value = true
  modifyPrompt.value = ''
  await nextTick()
  initCanvas()
}

const exitModifyMode = () => {
  isModifyMode.value = false
  modifyPrompt.value = ''
  isDrawing = false
}

// === Canvas: init and draw the image for editing ===
const initCanvas = () => {
  const canvas = canvasRef.value
  if (!canvas || !currentImage.value) return
  const img = new Image()
  img.onload = () => {
    const maxW = 700, maxH = 500
    let w = img.naturalWidth, h = img.naturalHeight
    if (w > maxW) { h = h * maxW / w; w = maxW }
    if (h > maxH) { w = w * maxH / h; h = maxH }
    w = Math.round(w); h = Math.round(h)

    canvas.width = w
    canvas.height = h
    canvas.style.width = w + 'px'
    canvas.style.height = h + 'px'
    ctx = canvas.getContext('2d')
    if (ctx) ctx.drawImage(img, 0, 0, w, h)

    const overlay = editCanvasRef.value
    if (overlay) {
      overlay.width = w
      overlay.height = h
      overlay.style.width = w + 'px'
      overlay.style.height = h + 'px'
      editCtx = overlay.getContext('2d')
    }

    canvasContainerStyle.value = { height: h + 'px' }
  }
  img.src = currentImage.value.data_uri
}

// === Canvas: mouse events for drawing the mask ===
const onMouseDown = (e: MouseEvent) => {
  if (e.button === 2) e.preventDefault()
  if (!editCtx || !editCanvasRef.value) return
  isDrawing = true
  const rect = editCanvasRef.value.getBoundingClientRect()
  const scaleX = editCanvasRef.value.width / rect.width
  const scaleY = editCanvasRef.value.height / rect.height
  mousePos.value = {
    x: (e.clientX - rect.left) * scaleX,
    y: (e.clientY - rect.top) * scaleY,
  }
  drawBrush(e)
}

const onMouseMove = (e: MouseEvent) => {
  if (!editCanvasRef.value) return
  const rect = editCanvasRef.value.getBoundingClientRect()
  const x = e.clientX - rect.left
  const y = e.clientY - rect.top
  // Scale mouse coords to canvas coords if CSS size differs from canvas size
  const scaleX = editCanvasRef.value.width / rect.width
  const scaleY = editCanvasRef.value.height / rect.height
  mousePos.value = { x: x * scaleX, y: y * scaleY }
  if (isDrawing && editCtx) drawBrush(e)
}

const onMouseUp = () => { isDrawing = false }
const onMouseLeave = () => { isDrawing = false; mousePos.value = { x: -1, y: -1 } }

const drawBrush = (e: MouseEvent) => {
  if (!editCtx || !editCanvasRef.value) return
  const rect = editCanvasRef.value.getBoundingClientRect()
  const scaleX = editCanvasRef.value.width / rect.width
  const scaleY = editCanvasRef.value.height / rect.height
  const x = (e.clientX - rect.left) * scaleX
  const y = (e.clientY - rect.top) * scaleY

  const erasing = isErasing.value || e.ctrlKey || e.button === 2
  if (erasing) {
    editCtx.globalCompositeOperation = 'destination-out'
    editCtx.fillStyle = 'rgba(0, 0, 0, 1)'
  } else {
    editCtx.globalCompositeOperation = 'source-over'
    editCtx.fillStyle = 'rgba(255, 0, 0, 0.5)'
  }
  editCtx.beginPath()
  editCtx.arc(x, y, brushSize.value, 0, Math.PI * 2)
  editCtx.fill()
  paintedVersion.value++
}

// Watch for library edit: load image and enter modify mode
watch(() => props2.libraryImageDataUri, (uri) => {
  if (uri) {
    images.value = [{ data_uri: uri, revised_prompt: '' }]
    currentIndex.value = 0
    if (visible.value) {
      nextTick(() => enterModifyMode())
    }
  }
})
watch(visible, (v) => {
  if (!v) {
    isModifyMode.value = false
    enhancedPrompt.value = ''
    images.value = []
    libraryPreviewData.value = null
    currentIndex.value = 0
  }
})

const clearMask = () => {
  if (!editCtx || !editCanvasRef.value) return
  editCtx.clearRect(0, 0, editCanvasRef.value.width, editCanvasRef.value.height)
}

// Generate mask in the correct format for the edit API:

const paintedPercent = computed(() => {
  void paintedVersion.value  // trigger reactivity on canvas changes
  const canvas = editCanvasRef.value
  if (!canvas) return 0
  const ctx = canvas.getContext('2d')
  if (!ctx) return 0
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data
  let painted = 0
  for (let i = 3; i < data.length; i += 4) {
    if (data[i] > 10) painted++
  }
  const total = data.length / 4
  return Math.round((painted / total) * 1000) / 10
})

const hasMask = computed(() => paintedPercent.value > 0)

// Generate mask in the correct format for the edit API:
// opaque white = keep, transparent = modify (inverse of display canvas)
const generateMaskDataUrl = (): string => {
  const src = editCanvasRef.value
  if (!src) return ''
  const w = src.width, h = src.height
  const mc = document.createElement('canvas')
  mc.width = w; mc.height = h
  const mtx = mc.getContext('2d')!
  // Fill with opaque white (keep everything by default)
  mtx.fillStyle = '#ffffff'
  mtx.fillRect(0, 0, w, h)
  // Get painted pixels from the display canvas (where alpha > 0 = user painted)
  const srcCtx = src.getContext('2d')!
  const srcData = srcCtx.getImageData(0, 0, w, h)
  const dstData = mtx.getImageData(0, 0, w, h)
  // Wherever the user painted (alpha > 10), set mask to transparent (= modify)
  for (let i = 3; i < srcData.data.length; i += 4) {
    if (srcData.data[i] > 10) {
      dstData.data[i] = 0 // alpha = 0 → transparent → modify this area
    }
  }
  mtx.putImageData(dstData, 0, 0)
  return mc.toDataURL('image/png')
}

// === 提交修改 ===
const submitEdit = async () => {
  if (!modifyPrompt.value.trim()) { ElMessage.warning('请输入修改需求'); return }
  if (!currentImage.value) return
  isEditing.value = true
  try {
    // Get mask data URL (correct format: opaque white bg, transparent = edit area)
    let maskUri = ''
    if (editCanvasRef.value) {
      maskUri = generateMaskDataUrl()
    }
    const r = await axios.post(apiUrl('/api/image/edit'), {
      model: selectedModel.value,
      prompt: modifyPrompt.value.trim(),
      data_uri: currentImage.value.data_uri,
      mask_uri: maskUri,
    })
    if (r.data.success && r.data.data?.data_uri) {
      const editImg = { data_uri: r.data.data.data_uri, revised_prompt: modifyPrompt.value }
      images.value = [editImg]
      currentIndex.value = 0
      libraryPreviewData.value = null
      // 自动保存到图片库
      emit2('saveToLibrary', editImg.data_uri)
      exitModifyMode()
      ElMessage.success('修改完成')
    } else {
      ElMessage.warning(r.data.message || '修改失败')
    }
  } catch (e: any) {
    ElMessage.error('修改失败: ' + getErrMsg(e))
  } finally {
    isEditing.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="isModifyMode ? '图片修改' : '图片工具'"
    width="920px"
    top="3vh"
    class="image-tool-dialog"
  >
    <div class="space-y-3">
      <!-- Top bar: model selector always visible, prompt/ref/gen hidden in modify mode -->
      <div class="flex gap-2 items-center">
        <el-select v-model="selectedModel" size="small" class="!w-32" placeholder="选择生图模型">
          <el-option
            v-for="m in imageModels"
            :key="m.name"
            :label="m.name"
            :value="m.name"
          >
            <span>{{ m.name }}</span>
            <el-tag v-if="m.type === 'local'" size="small" type="info" class="ml-2">本地</el-tag>
            <el-tag v-else size="small" type="primary" class="ml-2">云端</el-tag>
          </el-option>
        </el-select>
        <template v-if="!isModifyMode">
          <el-input
          v-model="rawPrompt"
          size="small"
          placeholder="输入自然语言描述，AI将自动优化..."
          class="flex-1"
          @keyup.ctrl.enter="generate"
        />
        <el-button size="small" @click="showReferenceStrip = !showReferenceStrip" :type="showReferenceStrip ? 'primary' : 'default'">
          参考图片
        </el-button>
        <el-button size="small" type="primary" :loading="isGenerating" @click="generate">生图</el-button>
        </template>
      </div>

      <!-- Reference image strip (toggle) -->
      <div v-if="showReferenceStrip && !isModifyMode" class="flex gap-2 items-center overflow-x-auto py-2 px-1 bg-app-light rounded-lg min-h-[72px]">
        <div
          v-for="(ref, i) in referenceImages" :key="i"
          class="relative shrink-0 w-14 h-14 rounded-lg overflow-hidden border border-app group"
        >
          <img :src="ref" class="w-full h-full object-cover" />
          <button
            @click="removeReferenceImage(i)"
            class="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
          >
            <X class="w-3 h-3" />
          </button>
        </div>
        <div
          v-if="referenceImages.length < 5"
          @click="addReferenceImage"
          class="shrink-0 w-14 h-14 rounded-lg border-2 border-dashed border-app flex items-center justify-center cursor-pointer hover:border-primary hover:text-primary transition-colors"
        >
          <Plus class="w-5 h-5" />
        </div>
        <input ref="referenceUploadRef" type="file" accept="image/*" class="hidden" @change="onReferenceUpload" />
        <div v-if="referenceImages.length === 0" class="text-xs text-app-muted ml-2">点击上方 [+] 上传参考图片（最多5张）</div>
      </div>

      <!-- Main content: split layout -->
      <div class="flex gap-3 min-h-[350px]">
        <!-- Left: image name list (hidden in modify mode) -->
        <div v-if="!isModifyMode" class="w-32 shrink-0 border-r border-app-light pr-2 overflow-y-auto max-h-[420px] space-y-0.5">
          <!-- Library images section -->
          <div v-if="props2.libraryImages && props2.libraryImages.length > 0">
            <div class="text-xs font-medium text-app-muted mb-1 px-1">图片库</div>
            <div
              v-for="libImg in props2.libraryImages" :key="libImg.id"
              @click="loadLibraryImage(libImg.id)"
              :class="['p-2 text-xs rounded cursor-pointer transition-colors truncate flex items-center gap-1', loadingLibraryId === libImg.id ? 'opacity-50' : 'text-app-secondary hover:bg-app-hover']"
            >
              <ImageIcon class="w-3 h-3 shrink-0" />
              <span class="truncate">{{ libImg.name }}</span>
            </div>
          </div>
        </div>

        <!-- Right: image preview or modify mode -->
        <div class="flex-1 min-w-0">
          <!-- ====== Non-modify mode ====== -->
          <div v-if="!isModifyMode" class="flex flex-col items-center gap-3">
            <!-- Preview area -->
            <div v-if="currentImage" class="relative w-full flex justify-center">
              <div class="flex-1 flex justify-center max-w-full">
                <img
                  :src="currentImage?.data_uri"
                  class="max-w-full max-h-[400px] rounded-lg shadow-md object-contain"
                  alt="图片预览"
                />
              </div>
            </div>

            <!-- Empty state -->
            <div v-else class="text-app-muted text-sm py-12">
              输入提示词后点击"生图"开始生成
            </div>

            <!-- Action buttons -->
            <div v-if="currentImage" class="flex gap-2">
              <el-button size="small" @click="saveImage">
                <Save class="w-3.5 h-3.5 mr-1" />导出
              </el-button>
              <el-button size="small" type="primary" @click="enterModifyMode">
                修改
              </el-button>
            </div>
          </div>

          <!-- ====== Modify mode ====== -->
          <div v-else class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-sm font-medium">
                在图片上涂抹要修改的区域（<span class="text-blue-400">左键涂抹</span> / <span class="text-yellow-400">右键/Ctrl 擦除</span>）
              </span>
              <div class="flex items-center gap-2">
                <el-button
                  size="small"
                  :type="isErasing ? 'warning' : 'default'"
                  @click="toggleErase"
                >
                  {{ isErasing ? '擦除中' : '橡皮擦' }}
                </el-button>
                <span class="text-xs text-app-muted">画笔:</span>
                <el-slider v-model="brushSize" :min="5" :max="80" class="!w-20" />
                <span class="text-xs text-app-muted w-8">{{ brushSize }}px</span>
              </div>
            </div>

            <!-- Canvas stack -->
            <div class="relative border rounded-lg overflow-hidden" :style="canvasContainerStyle">
              <canvas ref="canvasRef" class="absolute inset-0" />
              <canvas
                ref="editCanvasRef"
                class="absolute inset-0 cursor-crosshair"
                @mousedown="onMouseDown"
                @mousemove="onMouseMove"
                @mouseup="onMouseUp"
                @mouseleave="onMouseLeave"
                @contextmenu.prevent
              />
              <!-- Brush cursor preview -->
              <div
                v-if="mousePos.x >= 0"
                class="absolute pointer-events-none rounded-full border-2"
                :class="isErasing ? 'border-yellow-400' : 'border-white'"
                :style="{
                  width: brushSize * 2 + 'px',
                  height: brushSize * 2 + 'px',
                  left: mousePos.x - brushSize + 'px',
                  top: mousePos.y - brushSize + 'px',
                }"
              />
            </div>

            <!-- Status bar + inputs -->
            <div class="flex items-center justify-between">
              <div class="flex gap-2 items-center">
                <span class="text-xs" :class="hasMask ? 'text-green-500' : 'text-app-muted'">
                  已涂抹 {{ paintedPercent }}% 区域
                </span>
                <el-button v-if="hasMask" size="small" text @click="clearMask">清除涂抹</el-button>
              </div>
              <div class="flex gap-2 flex-1 ml-4">
                <el-input
                  v-model="modifyPrompt"
                  size="small"
                  placeholder="输入修改需求（如：把背景换成森林）"
                  class="flex-1"
                  @keyup.enter="submitEdit"
                />
                <el-button
                  size="small"
                  type="primary"
                  :loading="isEditing"
                  :disabled="!hasMask || !modifyPrompt.trim()"
                  @click="submitEdit"
                >确认修改</el-button>
                <el-button size="small" @click="exitModifyMode">返回</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.image-tool-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
}
</style>
