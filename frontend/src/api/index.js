import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000
})

http.interceptors.response.use(
  res => res.data,
  err => {
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(err)
  }
)

export default http

// --- Projects ---
export const getProjects = (params) => http.get('/projects', { params })
export const createProject = (data) => http.post('/projects', data)
export const updateProject = (id, data) => http.put(`/projects/${id}`, data)
export const deleteProject = (id) => http.delete(`/projects/${id}`)

// --- Statuses ---
export const getStatuses = (projectId) => http.get(`/projects/${projectId}/statuses`)
export const createStatus = (projectId, data) => http.post(`/projects/${projectId}/statuses`, data)
export const updateStatus = (projectId, id, data) => http.put(`/projects/${projectId}/statuses/${id}`, data)
export const deleteStatus = (projectId, id) => http.delete(`/projects/${projectId}/statuses/${id}`)

// --- Comm Types ---
export const getCommTypes = (projectId) => http.get(`/projects/${projectId}/comm-types`)
export const createCommType = (projectId, data) => http.post(`/projects/${projectId}/comm-types`, data)
export const updateCommType = (projectId, id, data) => http.put(`/projects/${projectId}/comm-types/${id}`, data)
export const deleteCommType = (projectId, id) => http.delete(`/projects/${projectId}/comm-types/${id}`)

// --- Checkins ---
export const getAllCheckins = () => http.get('/projects/checkins')
export const getCheckins = (projectId) => http.get(`/projects/${projectId}/checkins`)
export const createCheckin = (data) => http.post('/projects/checkins', data)
export const updateCheckin = (id, data) => http.put(`/projects/checkins/${id}`, data)
export const deleteCheckin = (projectId, id) => http.delete(`/projects/${projectId}/checkins/${id}`)
export const batchDeleteCheckins = (ids) => http.post('/projects/checkins/batch-delete', { ids })

// --- Tasks ---
export const getTasks = (projectId, params) => http.get(`/projects/${projectId}/tasks`, { params })
export const createTask = (projectId, data) => http.post(`/projects/${projectId}/tasks`, data)
export const getTask = (projectId, taskId) => http.get(`/projects/${projectId}/tasks/${taskId}`)
export const updateTask = (projectId, taskId, data) => http.put(`/projects/${projectId}/tasks/${taskId}`, data)
export const deleteTask = (projectId, taskId) => http.delete(`/projects/${projectId}/tasks/${taskId}`)

// --- Contacts ---
export const addContact = (projectId, taskId, data) => http.post(`/projects/${projectId}/tasks/${taskId}/contacts`, data)
export const updateContact = (projectId, taskId, contactId, data) => http.put(`/projects/${projectId}/tasks/${taskId}/contacts/${contactId}`, data)
export const deleteContact = (projectId, taskId, contactId) => http.delete(`/projects/${projectId}/tasks/${taskId}/contacts/${contactId}`)

// --- Project Contacts ---
export const getProjectContacts = (projectId, params) => http.get(`/projects/${projectId}/contacts`, { params })
export const addProjectContact = (projectId, data) => http.post(`/projects/${projectId}/contacts`, data)
export const updateProjectContact = (projectId, contactId, data) => http.put(`/projects/${projectId}/contacts/${contactId}`, data)
export const deleteProjectContact = (projectId, contactId) => http.delete(`/projects/${projectId}/contacts/${contactId}`)

// --- Communications ---
export const addCommunication = (projectId, taskId, data) => http.post(`/projects/${projectId}/tasks/${taskId}/communications`, data)
export const updateCommunication = (projectId, taskId, commId, data) => http.put(`/projects/${projectId}/tasks/${taskId}/communications/${commId}`, data)
export const deleteCommunication = (projectId, taskId, commId) => http.delete(`/projects/${projectId}/tasks/${taskId}/communications/${commId}`)

// --- Attachments ---
export const uploadCommAttachment = (projectId, taskId, commId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(`/projects/${projectId}/tasks/${taskId}/communications/${commId}/attachments`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}
export const downloadAttachment = (id) => `/api/attachments/${id}/download`
export const deleteAttachment = (id) => http.delete(`/attachments/${id}`)
export const renameAttachment = (id, name) => http.put(`/attachments/${id}`, { original_filename: name })

// --- Settings ---
export const getSettings = () => http.get('/process/settings')
export const updateSettings = (data) => http.put('/process/settings', data)
