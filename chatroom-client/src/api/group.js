import request from './request'

export function createGroup(data) {
  return request.post('/groups', data)
}

export function getMyGroups() {
  return request.get('/groups')
}

export function getGroupDetail(id) {
  return request.get(`/groups/${id}`)
}

export function inviteMember(groupId, userId) {
  return request.post(`/groups/${groupId}/members`, { userId })
}

export function removeMember(groupId, userId) {
  return request.delete(`/groups/${groupId}/members/${userId}`)
}

export function quitGroup(groupId) {
  return request.post(`/groups/${groupId}/quit`)
}
