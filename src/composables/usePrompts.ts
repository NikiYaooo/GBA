import { ref } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { apiUrl } from '@/utils/api'
import type { Profession, Role, PromptTemplate } from '@/types'

export function usePrompts() {
  const showPromptDialog = ref(false)
  const professions = ref<Profession[]>([])
  const professionsFull = ref<Profession[]>([])
  const selectedProfession = ref('')
  const selectedRole = ref<Role | null>(null)
  const selectedImitationProfession = ref('game_designer')
  const selectedImitationPrompt = ref<PromptTemplate | null>(null)
  const roles = ref<Role[]>([])
  const showAddRoleForm = ref(false)
  const newRoleName = ref('')
  const newRolePrompt = ref('')
  const editingRole = ref<Role | null>(null)
  const newPromptName = ref('')
  const newPromptContent = ref('')
  const editingProfessionId = ref('')

  const initDefaults = async () => {
    try { await axios.post(apiUrl('/api/prompts/init-defaults')) } catch { /* */ }
  }

  const loadProfessions = async () => {
    try {
      const r = await axios.get(apiUrl('/api/prompts/professions'))
      if (r.data.success) {
        professions.value = r.data.data
        professionsFull.value = r.data.data
        if (professions.value.length && !selectedProfession.value) {
          selectedProfession.value = professions.value[0].id
          await loadRoles(professions.value[0].id)
        }
      }
    } catch { /* */ }
  }

  const loadProfessionsFull = async () => {
    try {
      const r = await axios.get(apiUrl('/api/prompts/professions'))
      if (r.data.success) {
        professionsFull.value = r.data.data
        onProfessionChangeForSettings(selectedImitationProfession.value)
      }
    } catch { /* */ }
  }

  const loadRoles = async (profId: string) => {
    if (!profId) return
    try {
      const r = await axios.get(apiUrl(`/api/prompts/professions/${profId}`))
      if (r.data.success) {
        roles.value = r.data.data
        selectedRole.value = roles.value.length ? roles.value[0] : null
      }
    } catch { /* */ }
  }

  const onProfessionChange = (val: string) => {
    selectedProfession.value = val
    selectedRole.value = null
    loadRoles(val)
  }

  const onProfessionChangeForSettings = (profId: string) => {
    selectedImitationProfession.value = profId
    const pro = professionsFull.value.find((p: any) => p.id === profId)
    const prompts = pro?.prompts || []
    selectedImitationPrompt.value = prompts.length > 0 ? prompts[0] : null
    editingProfessionId.value = profId
  }

  const selectRole = (role: Role) => {
    selectedRole.value = role
    editingRole.value = null
    showAddRoleForm.value = false
  }

  const startAddRole = () => {
    newRoleName.value = ''; newRolePrompt.value = ''
    showAddRoleForm.value = true; editingRole.value = null
  }

  const startEditRole = (role: Role) => {
    editingRole.value = { ...role }
    newRoleName.value = role.name
    newRolePrompt.value = role.prompt
    showAddRoleForm.value = true
    selectedRole.value = null
  }

  const cancelAddRole = () => {
    showAddRoleForm.value = false; editingRole.value = null
    newRoleName.value = ''; newRolePrompt.value = ''
  }

  const saveRole = async () => {
    if (!newRoleName.value.trim() || !newRolePrompt.value.trim()) {
      ElMessage.warning('不能为空'); return
    }
    const roleData = {
      name: newRoleName.value.trim(),
      prompt: newRolePrompt.value.trim(),
      id: editingRole.value?.id || 'custom_' + Date.now().toString(36)
    }
    try {
      await axios.post(apiUrl('/api/prompts/roles'), {
        profession_id: selectedProfession.value, role: roleData
      })
      ElMessage.success(editingRole.value ? '已更新' : '已新增')
      cancelAddRole()
      await loadRoles(selectedProfession.value)
    } catch (e) { ElMessage.error('保存失败') }
  }

  const deleteRole = async (roleId: string) => {
    await axios.delete(apiUrl(`/api/prompts/roles/${roleId}`), {
      params: { profession_id: selectedProfession.value }
    })
    if (selectedRole.value?.id === roleId) selectedRole.value = null
    await loadRoles(selectedProfession.value)
  }

  const resetDefaults = async () => {
    await axios.post(apiUrl('/api/prompts/init-defaults'))
    selectedRole.value = null
    selectedProfession.value = ''
    await loadProfessions()
  }

  const addPromptToProfession = async (profId: string) => {
    if (!newPromptName.value.trim() || !newPromptContent.value.trim()) {
      ElMessage.warning('名称和内容不能为空'); return
    }
    try {
      const r = await axios.put(apiUrl(`/api/prompts/profession/${profId}/add-prompt`), {
        name: newPromptName.value.trim(), content: newPromptContent.value.trim()
      })
      if (r.data.success) {
        newPromptName.value = ''; newPromptContent.value = ''
        await loadProfessionsFull(); ElMessage.success('已添加')
      }
    } catch { ElMessage.error('添加失败') }
  }

  const deletePromptFromProfession = async (profId: string, promptId: string) => {
    await axios.delete(apiUrl(`/api/prompts/profession/${profId}/prompt/${promptId}`))
    await loadProfessionsFull()
    ElMessage.success('已删除')
  }

  const saveProfessionPrompt = async (profId: string) => {
    const pro = professionsFull.value.find((p: any) => p.id === profId)
    if (!pro) return
    await axios.put(apiUrl(`/api/prompts/profession/${profId}`), { prompts: pro.prompts })
    ElMessage.success('已保存')
  }

  const openPromptDialog = async () => {
    showPromptDialog.value = true
    await initDefaults()
    await loadProfessions()
  }

  const getImitationPrompt = (): string => {
    const pro: Profession | undefined = professionsFull.value.find(p => p.id === selectedImitationProfession.value)
    return selectedImitationPrompt.value?.content ||
      pro?.prompts?.[0]?.content ||
      '请根据需求撰写游戏策划案。不说客套废话，直接输出完整文档内容。'
  }

  return {
    showPromptDialog, professions, professionsFull, selectedProfession,
    selectedRole, selectedImitationProfession, selectedImitationPrompt,
    roles, showAddRoleForm, newRoleName, newRolePrompt, editingRole,
    newPromptName, newPromptContent, editingProfessionId,
    initDefaults, loadProfessions, loadProfessionsFull, loadRoles,
    onProfessionChange, onProfessionChangeForSettings, selectRole,
    startAddRole, startEditRole, cancelAddRole, saveRole,
    deleteRole, resetDefaults, addPromptToProfession,
    deletePromptFromProfession, saveProfessionPrompt,
    openPromptDialog, getImitationPrompt
  }
}
