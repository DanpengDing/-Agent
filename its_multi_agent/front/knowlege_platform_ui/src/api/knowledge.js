import request from './request'

export function uploadFile(data) {
  return request({
    url: '/upload',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function queryKnowledge(data) {
  return request({
    url: '/query',
    method: 'post',
    data
  })
}
