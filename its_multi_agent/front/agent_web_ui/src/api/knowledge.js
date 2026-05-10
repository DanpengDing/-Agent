import request from './request'

export function uploadFile(data) {
  return request({
    url: '/upload',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
