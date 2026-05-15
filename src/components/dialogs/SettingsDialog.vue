<script setup lang="ts">
import type { ModelConfig, Profession, PromptTemplate } from '@/types'
import { Trash2, Plus, Image } from 'lucide-vue-next'

const visible = defineModel<boolean>('visible', { default: false })

const imageModels = [
  { name: 'GPT-Image 2', type: 'cloud' as const },
  { name: 'Midjourney', type: 'cloud' as const },
  { name: 'Google Banana', type: 'cloud' as const },
  { name: '豆包Seedream', type: 'cloud' as const },
  { name: 'Stable Diffusion（本地）', type: 'local' as const },
]

const props = defineProps<{
  autoStart: boolean
  tortoiseSvnPath: string
  models: { name: string; type: 'cloud' | 'local' }[]
  modelConfigs: Record<string, ModelConfig>
  testingModel: string
  testingImageModel: string
  professionsFull: Profession[]
  selectedImitationProfession: string
  editingProfessionId: string
  isDark: boolean
  newPromptName: string
  newPromptContent: string
  qualityCheckPrompt: string
  dataPath: string
}>()

const emit = defineEmits<{
  'update:autoStart': [val: boolean]
  'update:tortoiseSvnPath': [val: string]
  saveConfig: []
  testModel: [modelName: string]
  testImageModel: [modelName: string]
  onProfessionChange: [profId: string]
  'update:isDark': [val: boolean]
  'update:newPromptName': [val: string]
  'update:newPromptContent': [val: string]
  'update:qualityCheckPrompt': [val: string]
  'update:dataPath': [val: string]
  saveQualityCheckPrompt: []
  saveDataPath: []
  addPrompt: []
  deletePrompt: [promptId: string]
}>()

const isDefaultPrompt = (prompt: PromptTemplate) => prompt.id === 'default'

const currentProfession = () => props.professionsFull.find(p => p.id === props.selectedImitationProfession)
const customPrompts = () => (currentProfession()?.prompts || []).filter(p => !isDefaultPrompt(p))

const getImageModelConfig = (name: string) => {
  return props.modelConfigs[name] || { modelId: '', apiKey: '' }
}
const setImageModelConfig = (name: string, key: string, value: string) => {
  if (!props.modelConfigs[name]) {
    props.modelConfigs[name] = { modelId: '', apiKey: '' }
  }
  ;(props.modelConfigs[name] as any)[key] = value
}
</script>

<template>
  <el-dialog v-model="visible" title="软件设置" width="600px" top="5vh">
    <el-tabs>
      <!-- 通用设置 -->
      <el-tab-pane label="通用设置">
        <div class="py-4 space-y-4">
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium">开机自动启动</span>
            <el-switch
              :model-value="autoStart"
              @change="(val: boolean) => emit('update:autoStart', val)"
            />
          </div>
          <div class="flex items-center justify-between">
            <div>
              <span class="text-sm font-medium">夜间模式</span>
              <p class="text-xs text-app-muted mt-0.5">切换深色/浅色主题</p>
            </div>
            <el-switch
              :model-value="isDark"
              @change="(val: boolean) => emit('update:isDark', val)"
            />
          </div>
          <div>
            <label class="text-sm font-medium block mb-2">TortoiseSVN 路径</label>
            <div class="flex gap-2">
              <el-input
                :model-value="tortoiseSvnPath" size="small"
                placeholder="例如：C:\Program Files\TortoiseSVN\bin\TortoiseProc.exe"
                @update:model-value="(v: string) => emit('update:tortoiseSvnPath', v)"
              />
              <el-button size="small" @click="emit('saveConfig')">保存</el-button>
            </div>
            <p class="text-xs text-app-muted mt-1">配置后 SVN 更新将使用 TortoiseSVN 界面，留空则使用命令行 svn</p>
          </div>
          <div>
            <label class="text-sm font-medium block mb-2">数据保存路径</label>
            <div class="flex gap-2">
              <el-input
                :model-value="dataPath" size="small"
                placeholder="例如：D:\GameBuilderData"
                @update:model-value="(v: string) => emit('update:dataPath', v)"
              />
              <el-button size="small" @click="emit('saveDataPath')">保存</el-button>
            </div>
            <p class="text-xs text-app-muted mt-1">设置后配置、知识库等数据保存在该路径下，重启应用后生效。留空则使用默认路径。</p>
          </div>
        </div>
      </el-tab-pane>

      <!-- AI 模型配置 -->
      <el-tab-pane label="AI 模型配置">
        <div class="py-4 space-y-4 max-h-[400px] overflow-y-auto pr-2">
          <div v-for="model in models" :key="model.name" class="p-4 bg-primary-light border border-app-light rounded-lg">
            <div class="flex items-center justify-between mb-3">
              <span class="font-semibold">{{ model.name }}</span>
              <el-tag size="small" :type="model.type === 'local' ? 'info' : 'primary'">
                {{ model.type === 'local' ? '本地' : '云端' }}
              </el-tag>
            </div>
            <div v-if="modelConfigs[model.name]" class="space-y-3">
              <div v-if="model.type !== 'local'">
                <label class="text-xs text-app-secondary block mb-1">模型 ID</label>
                <el-input
                  v-model="modelConfigs[model.name].modelId" size="small"
                  placeholder="例如：deepseek-chat"
                />
              </div>
              <div v-if="model.type !== 'local'">
                <label class="text-xs text-app-secondary block mb-1">API Key</label>
                <el-input
                  v-model="modelConfigs[model.name].apiKey"
                  type="password" show-password size="small" placeholder="sk-..."
                />
              </div>
              <div v-if="model.type === 'local'">
                <label class="text-xs text-app-secondary block mb-1">本地地址</label>
                <el-input
                  v-model="modelConfigs[model.name].modelId" size="small"
                  placeholder="http://localhost:11434"
                />
              </div>
              <el-button
                v-if="modelConfigs[model.name].apiKey || modelConfigs[model.name].modelId"
                size="small" :loading="testingModel === model.name"
                @click="emit('testModel', model.name)"
              >
                连接测试
              </el-button>
            </div>
          </div>
        </div>
        <div class="mt-4 flex justify-end">
          <el-button type="primary" @click="emit('saveConfig')">保存模型配置</el-button>
        </div>
      </el-tab-pane>

      <!-- 生图配置 -->
      <el-tab-pane label="生图配置">
        <div class="py-4 space-y-4 max-h-[400px] overflow-y-auto pr-2">
          <p class="text-xs text-app-muted mb-2">配置生图AI模型的API信息。GPT-Image 2 使用GPT的API Key，豆包Seedream使用豆包的API Key。</p>
          <div v-for="model in imageModels" :key="model.name" class="p-4 bg-primary-light border border-app-light rounded-lg">
            <div class="flex items-center justify-between mb-3">
              <span class="font-semibold text-sm">{{ model.name }}</span>
              <el-tag size="small" :type="model.type === 'local' ? 'info' : 'primary'">
                {{ model.type === 'local' ? '本地' : '云端' }}
              </el-tag>
            </div>
            <div class="space-y-3">
              <div v-if="model.type !== 'local'">
                <label class="text-xs text-app-secondary block mb-1">API Key</label>
                <el-input
                  :model-value="getImageModelConfig(model.name).apiKey"
                  type="password" show-password size="small" placeholder="sk-..."
                  @update:model-value="(v: string) => setImageModelConfig(model.name, 'apiKey', v)"
                />
              </div>
              <div>
                <label class="text-xs text-app-secondary block mb-1">{{ model.type === 'local' ? '本地地址' : '模型 ID（可选）' }}</label>
                <el-input
                  :model-value="getImageModelConfig(model.name).modelId"
                  size="small"
                  :placeholder="model.type === 'local' ? 'http://127.0.0.1:7860' : '留空使用默认'"
                  @update:model-value="(v: string) => setImageModelConfig(model.name, 'modelId', v)"
                />
              </div>
              <el-button
                v-if="getImageModelConfig(model.name).apiKey || getImageModelConfig(model.name).modelId"
                size="small" :loading="testingImageModel === model.name"
                @click="emit('testImageModel', model.name)"
              >
                连接测试
              </el-button>
            </div>
          </div>
        </div>
        <div class="mt-4 flex justify-end">
          <el-button type="primary" @click="emit('saveConfig')">保存生图配置</el-button>
        </div>
      </el-tab-pane>

      <!-- 职业角色 -->
      <el-tab-pane label="职业角色">
        <div class="py-4 pr-2">
          <div class="mb-6">
            <label class="text-sm font-semibold text-app block mb-2">选择职业</label>
            <el-select
              :model-value="selectedImitationProfession" size="default" class="w-full"
              @change="(val: string) => emit('onProfessionChange', val)"
            >
              <el-option v-for="p in professionsFull" :key="p.id" :label="p.name" :value="p.id" />
            </el-select>
          </div>
          <template v-if="selectedImitationProfession">
            <h3 class="text-sm font-semibold text-app mb-3">
              {{ currentProfession()?.name }} - 仿写指令
            </h3>
            <p class="text-xs text-app-muted mb-3">默认 Prompt 为内置不可编辑。可新增自定义 Prompt，自定义 Prompt 可删除。</p>
            <div v-if="(customPrompts() || []).length > 0" class="space-y-3 max-h-[200px] overflow-y-auto mb-4">
              <div
                v-for="prompt in customPrompts()"
                :key="prompt.id"
                class="border border-app rounded-lg p-3 bg-surface"
              >
                <div class="flex items-center justify-between mb-2">
                  <span class="text-sm font-medium">{{ prompt.name }}</span>
                  <el-button size="small" link type="danger" @click="emit('deletePrompt', prompt.id)">
                    <Trash2 class="w-3.5 h-3.5" />
                  </el-button>
                </div>
                <div class="text-xs text-app-secondary whitespace-pre-wrap leading-relaxed">{{ prompt.content }}</div>
              </div>
            </div>
            <div v-else class="text-xs text-app-muted mb-4">暂无自定义 Prompt，可在此职业下新增。</div>

            <!-- 新增仿写 Prompt -->
            <div class="border border-dashed border-app rounded-lg p-3 mb-4">
              <h4 class="text-sm font-medium text-app mb-2 flex items-center gap-1">
                <Plus class="w-3.5 h-3.5" /> 新增自定义仿写 Prompt
              </h4>
              <div class="space-y-2">
                <el-input
                  :model-value="newPromptName" size="small" placeholder="Prompt 名称"
                  @update:model-value="(v: string) => emit('update:newPromptName', v)"
                />
                <el-input
                  :model-value="newPromptContent" type="textarea" :rows="3" size="small"
                  placeholder="请输入仿写 Prompt 内容"
                  @update:model-value="(v: string) => emit('update:newPromptContent', v)"
                />
                <div class="flex justify-end">
                  <el-button size="small" type="primary" @click="emit('addPrompt')" :disabled="!newPromptName.trim() || !newPromptContent.trim()">
                    添加
                  </el-button>
                </div>
              </div>
            </div>

            <!-- 文档质检 Prompt -->
            <div class="border border-app rounded-lg p-3">
              <h4 class="text-sm font-medium text-app mb-2">文档质检 Prompt</h4>
              <p class="text-xs text-app-muted mb-2">自定义该职业的文档质检提示词，右键文档 →「文档质检」时将使用此 Prompt</p>
              <el-input
                :model-value="qualityCheckPrompt" type="textarea" :rows="5" size="small"
                placeholder="输入质检 Prompt..."
                @update:model-value="(v: string) => emit('update:qualityCheckPrompt', v)"
              />
              <div class="flex justify-end mt-2">
                <el-button size="small" type="primary" @click="emit('saveQualityCheckPrompt')">
                  保存质检 Prompt
                </el-button>
              </div>
            </div>
          </template>
        </div>
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>
