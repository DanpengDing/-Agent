import request from './request'

export function getLongTermMemories(userId, limit = 20) {
  return request({
    url: '/memories/long-term',
    method: 'get',
    params: { user_id: userId, limit }
  })
}

export function getUserPreferences(userId, limit = 20) {
  return request({
    url: '/memories/preferences',
    method: 'get',
    params: { user_id: userId, limit }
  })
}

export function upsertUserPreference(data) {
  return request({
    url: '/memories/preferences',
    method: 'put',
    data
  })
}

export function deleteUserPreference(userId, preferenceKey) {
  return request({
    url: `/memories/preferences/${encodeURIComponent(preferenceKey)}`,
    method: 'delete',
    params: { user_id: userId }
  })
}

export function getTaskMemories(userId, sessionId = '', limit = 20) {
  return request({
    url: '/memories/tasks',
    method: 'get',
    params: { user_id: userId, session_id: sessionId, limit }
  })
}

export function getActiveTask(userId, sessionId = '') {
  return request({
    url: '/memories/tasks/active',
    method: 'get',
    params: { user_id: userId, session_id: sessionId }
  })
}
