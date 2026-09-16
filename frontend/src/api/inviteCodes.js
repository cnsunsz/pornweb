import api from './index'

/** Admin: batch generate invite/activation codes */
export function generateInviteCodes(body) {
  return api.post('/admin/invite-codes', body)
}

/** Admin: list codes. status=unused|used|revoked|expired|all */
export function listInviteCodes(params = {}) {
  return api.get('/admin/invite-codes', { params })
}

/** Admin: revoke unused code */
export function revokeInviteCode(id) {
  return api.post(`/admin/invite-codes/${id}/revoke`)
}

/** Admin: delete one code (any status) */
export function deleteInviteCode(id) {
  return api.delete(`/admin/invite-codes/${id}`)
}

/** Admin: bulk cleanup. body: { status: 'used' } or { statuses: ['used','revoked','expired'] } */
export function cleanupInviteCodes(body = { status: 'used' }) {
  return api.post('/admin/invite-codes/cleanup', body)
}
