import api from './index'

export function getPlans() {
  return api.get('/payments/plans')
}

export function createOrder(planId, method = 'usdt') {
  return api.post('/payments/order', { plan_id: planId, method })
}

export function getOrderStatus(orderId) {
  return api.get(`/payments/order/${orderId}`)
}

export function capturePaypal(orderId) {
  return api.post('/payments/paypal/capture', { order_id: orderId })
}

export function getMyOrders() {
  return api.get('/payments/my')
}
