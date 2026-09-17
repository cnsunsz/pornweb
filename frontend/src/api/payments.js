import api from './index'

export function getPlans() {
  return api.get('/payments/plans')
}

export function createOrder(planId) {
  return api.post('/payments/order', { plan_id: planId })
}

export function getOrderStatus(orderId) {
  return api.get(`/payments/order/${orderId}`)
}

export function getMyOrders() {
  return api.get('/payments/my')
}
