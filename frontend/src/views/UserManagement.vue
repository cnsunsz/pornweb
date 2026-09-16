<template>
  <div class="users-page">
    <div class="top">
      <h2>{{ t('users.title') }}</h2>
      <el-button type="primary" @click="showAdd">
        <svg viewBox="0 0 24 24" width="16" height="16" style="margin-right:4px"><path d="M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="currentColor"/></svg>
        {{ t('users.add') }}
      </el-button>
    </div>

    <div class="filters">
      <el-radio-group v-model="statusFilter" size="small">
        <el-radio-button value="all">{{ t('users.filterAll') }}</el-radio-button>
        <el-radio-button value="active">{{ t('users.filterActive') }}</el-radio-button>
        <el-radio-button value="expired">{{ t('users.filterExpired') }}</el-radio-button>
        <el-radio-button value="permanent">{{ t('users.filterPermanent') }}</el-radio-button>
      </el-radio-group>
    </div>

    <el-card>
      <el-table :data="filteredUsers" stripe v-loading="loading" size="small">
        <el-table-column :label="t('users.user')" min-width="150">
          <template #default="{row}">
            <div style="display:flex;align-items:center;gap:10px">
              <span class="av" :style="{background:row.is_admin?'var(--danger)':'var(--bg-hover)'}">{{ row.username[0].toUpperCase() }}</span>
              <div>
                <div style="font-weight:600;font-size:14px">{{ row.username }}</div>
                <div style="font-size:12px;color:var(--text-muted)">{{ row.email }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.role')" width="90">
          <template #default="{row}">
            <el-tag :type="row.is_admin?'danger':'info'" size="small">{{ row.is_admin?t('dash.admin'):t('dash.user') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.memberStatus')" width="110">
          <template #default="{row}">
            <el-tag :type="statusTagType(row)" size="small">{{ statusLabel(row) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.expiresAt')" width="160">
          <template #default="{row}">
            <span style="font-size:12px;color:var(--text-muted)">{{ expiresLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.daysLeft')" width="90">
          <template #default="{row}">
            <span style="font-size:12px">{{ daysLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.registered')" width="150">
          <template #default="{row}">
            <span style="font-size:12px;color:var(--text-muted)">{{ new Date(row.created_at).toLocaleString(locale) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.actions')" width="220" fixed="right">
          <template #default="{row}">
            <el-button size="small" text @click="showRenew(row)">{{ t('users.renewBtn') }}</el-button>
            <el-button size="small" text @click="showLibs(row)">{{ t('users.libsBtn') }}</el-button>
            <el-button size="small" text @click="showEdit(row)">{{ t('users.editBtn') }}</el-button>
            <el-button size="small" text @click="showPw(row)">{{ t('users.pwBtn') }}</el-button>
            <el-button v-if="row.id!==myId" size="small" text type="danger" @click="delUser(row)">{{ t('users.delete') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="dlg" :title="isEdit?t('users.edit'):t('users.add')" width="400px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="60px">
        <el-form-item :label="t('auth.username')" prop="username"><el-input v-model="form.username" /></el-form-item>
        <el-form-item :label="t('auth.email')" prop="email"><el-input v-model="form.email" /></el-form-item>
        <el-form-item v-if="!isEdit" :label="t('auth.password')" prop="password"><el-input v-model="form.password" type="password" show-password /></el-form-item>
        <el-form-item :label="t('users.role')"><el-switch v-model="form.is_admin" :active-text="t('dash.admin')" :inactive-text="t('dash.user')" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg=false">{{ t('users.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="doSave">{{ isEdit?t('users.save'):t('users.create') }}</el-button>
      </template>
    </el-dialog>

    <!-- Password Dialog -->
    <el-dialog v-model="pwDlg" :title="t('users.changePw')" width="360px">
      <el-form ref="pwRef" :model="pwForm" :rules="pwRules" label-width="60px">
        <el-form-item :label="t('users.newPw')" prop="password"><el-input v-model="pwForm.password" type="password" show-password /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwDlg=false">{{ t('users.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="doPw">{{ t('users.ok') }}</el-button>
      </template>
    </el-dialog>

    <!-- Renew Dialog -->
    <el-dialog v-model="renewDlg" :title="t('users.renewTitle')" width="400px" :close-on-click-modal="false">
      <p class="hint" v-if="renewUserRow">{{ renewUserRow.username }} — {{ statusLabel(renewUserRow) }}</p>
      <el-form label-width="90px">
        <el-form-item :label="t('users.renewMode')">
          <el-radio-group v-model="renewMode">
            <el-radio value="days">{{ t('users.renewDays') }}</el-radio>
            <el-radio value="permanent">{{ t('users.renewPermanent') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="renewMode==='days'" :label="t('users.durationDays')">
          <el-input-number v-model="renewDays" :min="1" :max="3650" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="renewDlg=false">{{ t('users.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="doRenew">{{ t('users.ok') }}</el-button>
      </template>
    </el-dialog>

    <!-- Libraries ACL Dialog -->
    <el-dialog v-model="libDlg" :title="t('users.libsTitle')" width="440px" :close-on-click-modal="false">
      <p class="hint" v-if="libUserRow">{{ libUserRow.username }}</p>
      <el-alert v-if="libAllLibraries" type="info" :closable="false" show-icon :title="t('users.libsAdminAll')" style="margin-bottom:12px" />
      <el-checkbox-group v-else v-model="libSelected" style="display:flex;flex-direction:column;gap:8px">
        <el-checkbox v-for="lib in allLibs" :key="lib.id" :label="lib.id">
          {{ lib.name }} <span style="color:var(--text-muted);font-size:12px">({{ lib.path }})</span>
        </el-checkbox>
      </el-checkbox-group>
      <p v-if="!libAllLibraries && !allLibs.length" class="hint">{{ t('users.libsEmpty') }}</p>
      <template #footer>
        <el-button @click="libDlg=false">{{ t('users.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" :disabled="libAllLibraries" @click="doLibs">{{ t('users.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUsersStore } from '@/stores/users'
import { useAuthStore } from '@/stores/auth'
import { createUser, updateUser, deleteUser, renewUser, getUserLibraries, putUserLibraries } from '@/api/users'
import { getLibraries } from '@/api/media'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t, locale } = useI18n()
const us = useUsersStore(); const auth = useAuthStore()
const users = computed(() => us.users); const loading = computed(() => us.loading)
const myId = computed(() => auth.user?.id)
const statusFilter = ref('all')

const filteredUsers = computed(() => {
  const list = users.value || []
  const f = statusFilter.value
  if (f === 'all') return list
  return list.filter(u => {
    const st = u.access_status || deriveStatus(u)
    if (f === 'active') return st === 'active'
    if (f === 'expired') return st === 'expired'
    if (f === 'permanent') return st === 'permanent' || st === 'admin'
    return true
  })
})

function deriveStatus(u) {
  if (u.is_admin) return 'admin'
  if (!u.access_expires_at) return 'permanent'
  if (!u.access_active || u.access_days_left === 0) return 'expired'
  return 'active'
}
function statusLabel(u) {
  const st = u.access_status || deriveStatus(u)
  if (st === 'admin') return t('access.statusAdmin')
  if (st === 'expired') return t('access.statusExpired')
  if (st === 'permanent') return t('access.statusPermanent')
  return t('access.statusActive')
}
function statusTagType(u) {
  const st = u.access_status || deriveStatus(u)
  if (st === 'expired') return 'danger'
  if (st === 'admin') return 'success'
  if (st === 'permanent') return 'success'
  return 'success'
}
function expiresLabel(u) {
  if (u.is_admin || !u.access_expires_at) return t('access.permanent')
  try { return new Date(u.access_expires_at).toLocaleString(locale.value) } catch { return String(u.access_expires_at) }
}
function daysLabel(u) {
  if (u.is_admin) return t('access.adminUnlimited')
  if (u.access_days_left === null || u.access_days_left === undefined) return t('access.permanent')
  if (u.access_days_left === 0 || !u.access_active) return t('access.expired')
  return t('access.daysLeftN', { n: u.access_days_left })
}

const dlg = ref(false); const isEdit = ref(false); const editId = ref(null); const saving = ref(false)
const formRef = ref(); const form = ref({username:'',email:'',password:'',is_admin:false})
const rules = computed(() => ({ username:[{required:true,message:t('users.required')}], email:[{required:true,message:t('users.required')},{type:'email',message:t('users.emailBad')}], password:[{required:true,message:t('users.required')},{min:6,message:t('users.passMin')}] }))
const pwDlg = ref(false); const pwRef = ref(); const pwId = ref(null)
const pwForm = ref({password:''}); const pwRules = computed(() => ({password:[{required:true,message:t('users.required')},{min:6,message:t('users.passMin')}]}))

const renewDlg = ref(false); const renewUserRow = ref(null); const renewMode = ref('days'); const renewDays = ref(30)
const libDlg = ref(false); const libUserRow = ref(null); const libSelected = ref([]); const libAllLibraries = ref(false); const allLibs = ref([])

function showAdd() { isEdit.value=false; editId.value=null; form.value={username:'',email:'',password:'',is_admin:false}; dlg.value=true }
function showEdit(u) { isEdit.value=true; editId.value=u.id; form.value={username:u.username,email:u.email,password:'',is_admin:u.is_admin}; dlg.value=true }
function showPw(u) { pwId.value=u.id; pwForm.value={password:''}; pwDlg.value=true }
function showRenew(u) {
  renewUserRow.value = u
  renewMode.value = (!u.access_expires_at || u.is_admin) ? 'permanent' : 'days'
  renewDays.value = 30
  renewDlg.value = true
}
async function showLibs(u) {
  libUserRow.value = u
  libSelected.value = []
  libAllLibraries.value = !!u.is_admin
  libDlg.value = true
  try {
    if (!allLibs.value.length) {
      const r = await getLibraries()
      allLibs.value = r.data || []
    }
    if (!u.is_admin) {
      const r = await getUserLibraries(u.id)
      libSelected.value = [...(r.data?.library_ids || [])]
      libAllLibraries.value = !!r.data?.all_libraries
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('users.fail'))
  }
}

async function doSave() {
  try{await formRef.value.validate()}catch{return}
  saving.value=true
  try {
    if(isEdit.value) { const d={}; if(form.value.username)d.username=form.value.username; if(form.value.email)d.email=form.value.email; if(form.value.password)d.password=form.value.password; d.is_admin=form.value.is_admin; await updateUser(editId.value,d); ElMessage.success(t('users.updated')) }
    else { await createUser(form.value); ElMessage.success(t('users.created')) }
    dlg.value=false; us.fetchUsers()
  } catch(e) { ElMessage.error(e.response?.data?.detail||t('users.fail')) }
  finally { saving.value=false }
}
async function doPw() {
  try{await pwRef.value.validate()}catch{return}
  saving.value=true
  try { await updateUser(pwId.value,{password:pwForm.value.password}); ElMessage.success(t('users.pwOk')); pwDlg.value=false }
  catch(e) { ElMessage.error(e.response?.data?.detail||t('users.pwFail')) }
  finally { saving.value=false }
}
async function doRenew() {
  if (!renewUserRow.value) return
  saving.value = true
  try {
    const body = renewMode.value === 'permanent' ? { permanent: true } : { duration_days: renewDays.value }
    await renewUser(renewUserRow.value.id, body)
    ElMessage.success(t('users.renewOk'))
    renewDlg.value = false
    us.fetchUsers()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('users.fail'))
  } finally {
    saving.value = false
  }
}
async function doLibs() {
  if (!libUserRow.value || libAllLibraries.value) return
  saving.value = true
  try {
    await putUserLibraries(libUserRow.value.id, libSelected.value)
    ElMessage.success(t('users.libsOk'))
    libDlg.value = false
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('users.fail'))
  } finally {
    saving.value = false
  }
}
async function delUser(u) { try { await ElMessageBox.confirm(t('users.confirmDel',{name:u.username}),t('users.confirm'),{type:'warning'}); await deleteUser(u.id); ElMessage.success(t('users.deleted')); us.fetchUsers() } catch{} }
onMounted(async () => {
  us.fetchUsers()
  try {
    const r = await getLibraries()
    allLibs.value = r.data || []
  } catch {}
})
</script>
<style scoped>
.users-page { max-width:1100px; display:flex; flex-direction:column; gap:16px; }
.top { display:flex; align-items:center; justify-content:space-between; }
.top h2 { font-size:22px; }
.filters { display:flex; gap:8px; flex-wrap:wrap; }
.av { width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:600; flex-shrink:0; }
.hint { font-size:13px; color:var(--text-muted); margin:0 0 12px; }
</style>
