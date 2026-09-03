<template>
  <div class="users-page">
    <div class="top"><h2>{{ t('users.title') }}</h2><el-button type="primary" @click="showAdd"><svg viewBox="0 0 24 24" width="16" height="16" style="margin-right:4px"><path d="M15 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm-9-2V7H4v3H1v2h3v3h2v-3h3v-2H6zm9 4c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" fill="currentColor"/></svg>{{ t('users.add') }}</el-button></div>
    <el-card>
      <el-table :data="users" stripe v-loading="loading" size="small">
        <el-table-column :label="t('users.user')" min-width="150">
          <template #default="{row}">
            <div style="display:flex;align-items:center;gap:10px">
              <span class="av" :style="{background:row.is_admin?'var(--danger)':'var(--bg-hover)'}">{{ row.username[0].toUpperCase() }}</span>
              <div><div style="font-weight:600;font-size:14px">{{ row.username }}</div><div style="font-size:12px;color:var(--text-muted)">{{ row.email }}</div></div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('users.role')" width="100">
          <template #default="{row}"><el-tag :type="row.is_admin?'danger':'info'" size="small">{{ row.is_admin?t('dash.admin'):t('dash.user') }}</el-tag></template>
        </el-table-column>
        <el-table-column :label="t('users.registered')" width="160">
          <template #default="{row}"><span style="font-size:12px;color:var(--text-muted)">{{ new Date(row.created_at).toLocaleString(locale) }}</span></template>
        </el-table-column>
        <el-table-column :label="t('users.actions')" width="140" fixed="right">
          <template #default="{row}">
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
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUsersStore } from '@/stores/users'
import { useAuthStore } from '@/stores/auth'
import { createUser, updateUser, deleteUser } from '@/api/users'
import { ElMessage, ElMessageBox } from 'element-plus'
const { t, locale } = useI18n()
const us = useUsersStore(); const auth = useAuthStore()
const users = computed(() => us.users); const loading = computed(() => us.loading)
const myId = computed(() => auth.user?.id)
const dlg = ref(false); const isEdit = ref(false); const editId = ref(null); const saving = ref(false)
const formRef = ref(); const form = ref({username:'',email:'',password:'',is_admin:false})
const rules = computed(() => ({ username:[{required:true,message:t('users.required')}], email:[{required:true,message:t('users.required')},{type:'email',message:t('users.emailBad')}], password:[{required:true,message:t('users.required')},{min:6,message:t('users.passMin')}] }))
const pwDlg = ref(false); const pwRef = ref(); const pwId = ref(null)
const pwForm = ref({password:''}); const pwRules = computed(() => ({password:[{required:true,message:t('users.required')},{min:6,message:t('users.passMin')}]}))

function showAdd() { isEdit.value=false; editId.value=null; form.value={username:'',email:'',password:'',is_admin:false}; dlg.value=true }
function showEdit(u) { isEdit.value=true; editId.value=u.id; form.value={username:u.username,email:u.email,password:'',is_admin:u.is_admin}; dlg.value=true }
function showPw(u) { pwId.value=u.id; pwForm.value={password:''}; pwDlg.value=true }

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
async function delUser(u) { try { await ElMessageBox.confirm(t('users.confirmDel',{name:u.username}),t('users.confirm'),{type:'warning'}); await deleteUser(u.id); ElMessage.success(t('users.deleted')); us.fetchUsers() } catch{} }
onMounted(() => us.fetchUsers())
</script>
<style scoped>
.users-page { max-width:900px; display:flex; flex-direction:column; gap:20px; }
.top { display:flex; align-items:center; justify-content:space-between; }
.top h2 { font-size:22px; }
.av { width:30px; height:30px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:13px; font-weight:600; flex-shrink:0; }
</style>
