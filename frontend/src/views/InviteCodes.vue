<template>
  <div class="invite-page">
    <div class="top">
      <h2>{{ t('invite.title') }}</h2>
    </div>
    <p class="hint">{{ t('invite.hint') }}</p>

    <el-card>
      <template #header><span class="ch">{{ t('invite.generate') }}</span></template>
      <div class="gen-form">
        <el-input-number v-model="count" :min="1" :max="100" controls-position="right" />
        <el-input v-model="note" :placeholder="t('invite.notePh')" clearable style="max-width:260px" />
        <el-input-number
          v-model="expiresDays"
          :min="0"
          :max="3650"
          controls-position="right"
          :placeholder="t('invite.expiresPh')"
        />
        <span class="note">{{ t('invite.expiresHint') }}</span>
        <el-button type="primary" :loading="genBusy" @click="doGenerate">{{ t('invite.genBtn') }}</el-button>
      </div>
      <div v-if="lastGenerated.length" class="last-gen">
        <div class="last-title">{{ t('invite.lastBatch') }}</div>
        <div class="code-chips">
          <el-tag
            v-for="c in lastGenerated"
            :key="c.id"
            class="code-chip"
            effect="dark"
            @click="copyOne(c.code)"
          >{{ c.code }}</el-tag>
        </div>
        <el-button size="small" @click="copyAll(lastGenerated)">{{ t('invite.copyAll') }}</el-button>
      </div>
    </el-card>

    <el-card style="margin-top:16px">
      <template #header>
        <div class="list-head">
          <span class="ch">{{ t('invite.list') }}</span>
          <el-radio-group v-model="status" size="small" @change="load(1)">
            <el-radio-button value="all">{{ t('invite.statusAll') }}</el-radio-button>
            <el-radio-button value="unused">{{ t('invite.statusUnused') }}</el-radio-button>
            <el-radio-button value="used">{{ t('invite.statusUsed') }}</el-radio-button>
            <el-radio-button value="revoked">{{ t('invite.statusRevoked') }}</el-radio-button>
            <el-radio-button value="expired">{{ t('invite.statusExpired') }}</el-radio-button>
          </el-radio-group>
        </div>
      </template>
      <el-table :data="items" stripe v-loading="loading" size="small">
        <el-table-column :label="t('invite.code')" min-width="160">
          <template #default="{ row }">
            <code class="mono" @click="copyOne(row.code)">{{ row.code }}</code>
          </template>
        </el-table-column>
        <el-table-column :label="t('invite.status')" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('invite.note')" min-width="100" show-overflow-tooltip>
          <template #default="{ row }">{{ row.note || '-' }}</template>
        </el-table-column>
        <el-table-column :label="t('invite.created')" width="160">
          <template #default="{ row }">
            <span class="muted">{{ fmt(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('invite.usedBy')" width="90">
          <template #default="{ row }">
            <span class="muted">{{ row.used_by != null ? '#' + row.used_by : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('invite.expires')" width="160">
          <template #default="{ row }">
            <span class="muted">{{ row.expires_at ? fmt(row.expires_at) : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="t('invite.actions')" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="copyOne(row.code)">{{ t('invite.copy') }}</el-button>
            <el-button
              v-if="row.status === 'unused'"
              size="small"
              text
              type="danger"
              @click="doRevoke(row)"
            >{{ t('invite.revoke') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="total > 0" style="display:flex;justify-content:center;margin-top:16px">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total,prev,pager,next"
          background
          small
          @current-change="p => load(p)"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { generateInviteCodes, listInviteCodes, revokeInviteCode } from '@/api/inviteCodes'
import { ElMessage, ElMessageBox } from 'element-plus'

const { t, locale } = useI18n()
const count = ref(1)
const note = ref('')
const expiresDays = ref(0)
const genBusy = ref(false)
const lastGenerated = ref([])
const items = ref([])
const loading = ref(false)
const status = ref('all')
const page = ref(1)
const pageSize = 20
const total = ref(0)

function statusType(s) {
  return ({ unused: 'success', used: 'info', revoked: 'danger', expired: 'warning' })[s] || 'info'
}
function statusLabel(s) {
  return ({
    unused: t('invite.statusUnused'),
    used: t('invite.statusUsed'),
    revoked: t('invite.statusRevoked'),
    expired: t('invite.statusExpired'),
  })[s] || s
}
function fmt(iso) {
  if (!iso) return '-'
  try { return new Date(iso).toLocaleString(locale.value) } catch { return iso }
}

async function copyOne(code) {
  try {
    await navigator.clipboard.writeText(code)
    ElMessage.success(t('invite.copied'))
  } catch {
    ElMessage.info(code)
  }
}
async function copyAll(list) {
  const text = list.map(c => c.code).join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success(t('invite.copied'))
  } catch {
    ElMessage.info(text)
  }
}

async function doGenerate() {
  genBusy.value = true
  try {
    const body = { count: count.value, note: note.value || undefined }
    if (expiresDays.value > 0) body.expires_days = expiresDays.value
    const res = await generateInviteCodes(body)
    lastGenerated.value = res.data || []
    ElMessage.success(t('invite.genOk', { n: lastGenerated.value.length }))
    await load(1)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('invite.genFail'))
  } finally {
    genBusy.value = false
  }
}

async function load(p = page.value) {
  page.value = p
  loading.value = true
  try {
    const res = await listInviteCodes({ page: page.value, page_size: pageSize, status: status.value })
    items.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('invite.loadFail'))
  } finally {
    loading.value = false
  }
}

async function doRevoke(row) {
  try {
    await ElMessageBox.confirm(t('invite.confirmRevoke', { code: row.code }), t('invite.confirm'), { type: 'warning' })
    await revokeInviteCode(row.id)
    ElMessage.success(t('invite.revoked'))
    await load(page.value)
  } catch {}
}

onMounted(() => load(1))
</script>

<style scoped>
.invite-page { max-width: 1100px; display: flex; flex-direction: column; gap: 12px; }
.top h2 { font-size: 22px; }
.hint { color: var(--text-muted); font-size: 13px; margin: 0; }
.ch { font-weight: 600; }
.gen-form { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.note { font-size: 12px; color: var(--text-muted); }
.last-gen { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); }
.last-title { font-size: 13px; margin-bottom: 8px; color: var(--text-dim); }
.code-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
.code-chip { cursor: pointer; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 0.04em; }
.list-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; cursor: pointer; color: var(--accent); }
.muted { font-size: 12px; color: var(--text-muted); }
</style>
