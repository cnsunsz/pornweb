<template>
  <div class="renew-page">
    <div class="renew-card">
      <h2 class="title">{{ t('pay.title') }}</h2>
      <p class="sub">{{ t('pay.sub') }}</p>

      <!-- plans -->
      <div v-if="!order" class="plans">
        <div
          v-for="p in plans"
          :key="p.id"
          class="plan"
          :class="{ active: planId === p.id }"
          @click="planId = p.id"
        >
          <div class="plan-days">
            <span class="num">{{ p.days }}</span>
            <span class="unit">{{ t('pay.days') }}</span>
          </div>
          <div class="plan-price">${{ p.amount }} <small>USDT</small></div>
        </div>
      </div>

      <el-button
        v-if="!order"
        type="primary"
        size="large"
        class="pay-btn"
        :loading="creating"
        @click="start"
      >
        {{ t('pay.payBtn') }}
      </el-button>

      <!-- waiting for payment -->
      <div v-if="order && order.status === 'pending'" class="status-box">
        <div class="status-line">
          <span class="dot pulse"></span>
          <span>{{ t('pay.waiting') }}</span>
        </div>
        <div class="amount-line">{{ order.amount }} USDT · {{ order.days }} {{ t('pay.days') }}</div>
        <div class="actions">
          <el-button size="small" @click="reopen">{{ t('pay.reopen') }}</el-button>
          <el-button size="small" type="danger" plain @click="cancelOrder">{{ t('pay.cancel') }}</el-button>
        </div>
        <div class="hint">{{ t('pay.hint') }}</div>
      </div>

      <!-- paid -->
      <div v-if="order && order.status === 'paid'" class="status-box paid">
        <div class="status-line big">
          <span>✓</span>
          <span>{{ t('pay.paidTitle') }}</span>
        </div>
        <div class="amount-line">{{ t('pay.paidMsg', { days: order.days }) }}</div>
        <el-button type="primary" @click="goHome">{{ t('pay.backHome') }}</el-button>
      </div>

      <!-- expired -->
      <div v-if="order && order.status === 'expired'" class="status-box expired">
        <div class="status-line">{{ t('pay.expiredTitle') }}</div>
        <el-button type="primary" plain @click="reset">{{ t('pay.retry') }}</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { getPlans, createOrder, getOrderStatus } from '@/api/payments'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const auth = useAuthStore()

const plans = ref([])
const planId = ref('p30')
const creating = ref(false)
const order = ref(null) // { order_id, pay_url, days, amount, status }
let timer = null

onMounted(async () => {
  try {
    const res = await getPlans()
    plans.value = res.data?.plans || []
  } catch { /* non-fatal */ }
})

onBeforeUnmount(() => {
  stopPolling()
})

function stopPolling() {
  if (timer) { clearInterval(timer); timer = null }
}

async function start() {
  if (!planId.value) return
  creating.value = true
  try {
    const res = await createOrder(planId.value)
    order.value = res.data
    window.open(res.data.pay_url, '_blank')
    startPolling()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || t('pay.createFail'))
  } finally {
    creating.value = false
  }
}

function reopen() {
  if (order.value?.pay_url) window.open(order.value.pay_url, '_blank')
}

function startPolling() {
  stopPolling()
  timer = setInterval(async () => {
    if (!order.value?.order_id) return
    try {
      const res = await getOrderStatus(order.value.order_id)
      order.value.status = res.data.status
      if (res.data.status === 'paid') {
        stopPolling()
        ElMessage.success(t('pay.paidMsg', { days: order.value.days }))
        auth.fetchMe()
      } else if (res.data.status === 'expired') {
        stopPolling()
      }
    } catch { /* retry next tick */ }
  }, 6000)
}

function cancelOrder() {
  stopPolling()
  order.value = null
}

function reset() {
  order.value = null
}

function goHome() {
  auth.fetchMe()
  router.push('/')
}
</script>

<style scoped>
.renew-page { max-width: 720px; margin: 40px auto; padding: 0 16px; }
.renew-card { background: var(--el-bg-color); border: 1px solid var(--el-border-color-light); border-radius: 14px; padding: 28px; }
.title { margin: 0 0 4px; }
.sub { margin: 0 0 20px; color: var(--el-text-color-secondary); font-size: 13px; }
.plans { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 20px; }
.plan { border: 2px solid var(--el-border-color-light); border-radius: 12px; padding: 16px 12px; text-align: center; cursor: pointer; transition: border-color .15s, transform .15s; }
.plan:hover { transform: translateY(-2px); }
.plan.active { border-color: var(--el-color-primary); }
.plan-days .num { font-size: 26px; font-weight: 700; }
.plan-days .unit { margin-left: 4px; color: var(--el-text-color-secondary); }
.plan-price { margin-top: 6px; font-size: 15px; color: var(--el-color-success); font-weight: 600; }
.plan-price small { color: var(--el-text-color-secondary); font-weight: 400; }
.pay-btn { width: 100%; }
.status-box { text-align: center; padding: 12px 0; }
.status-line { display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 15px; }
.status-line.big { font-size: 20px; font-weight: 700; color: var(--el-color-success); }
.status-box.paid .status-line.big span:first-child { font-size: 26px; }
.amount-line { margin: 10px 0 16px; color: var(--el-text-color-secondary); }
.dot { width: 10px; height: 10px; border-radius: 50%; background: var(--el-color-warning); display: inline-block; }
.pulse { animation: pulse 1.4s infinite; }
@keyframes pulse { 0%,100% { opacity: 1 } 50% { opacity: .25 } }
.actions { display: flex; justify-content: center; gap: 8px; margin-bottom: 12px; }
.hint { font-size: 12px; color: var(--el-text-color-secondary); }
.status-box.expired .status-line { color: var(--el-color-danger); }
</style>
