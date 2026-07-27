import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api',
  timeout: 30000
})

http.interceptors.response.use(
  res => res.config.rawResponse ? res : res.data,
  err => {
    // 携带 _silentError 标记的请求不自动弹错误提示（如彻底删除的 409）
    if (err.config?._silentError) return Promise.reject(err)
    const msg = err.response?.data?.detail || err.message || '请求失败'
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(err)
  }
)

export default http

// --- Projects ---
export const getProjects = (params) => http.get('/projects', { params })
export const getProject = (id) => http.get(`/projects/${id}`)
export const createProject = (data) => http.post('/projects', data)
export const updateProject = (id, data) => http.put(`/projects/${id}`, data)
export const deleteProject = (id) => http.delete(`/projects/${id}`)

// --- Project Categories (书签式分类) ---
export const getCategories = () => http.get('/categories')
export const createCategory = (name) => http.post('/categories', { name })
export const renameCategory = (key, name) => http.put(`/categories/${key}`, { name })
export const deleteCategory = (key) => http.delete(`/categories/${key}`)
export const reorderCategories = (order) => http.put('/categories/reorder', { order })
export const getDefaultCategory = () => http.get('/categories/default')
export const setDefaultCategory = (key) => http.put('/categories/default', { key })

// --- Statuses ---
export const getStatuses = (projectId, params) => http.get(`/projects/${projectId}/statuses`, { params })
export const createStatus = (projectId, data) => http.post(`/projects/${projectId}/statuses`, data)
export const updateStatus = (projectId, id, data) => http.put(`/projects/${projectId}/statuses/${id}`, data)
export const deleteStatus = (projectId, id, config) => http.delete(`/projects/${projectId}/statuses/${id}`, config)

// --- Comm Types ---
export const getCommTypes = (projectId, params) => http.get(`/projects/${projectId}/comm-types`, { params })
export const createCommType = (projectId, data) => http.post(`/projects/${projectId}/comm-types`, data)
export const updateCommType = (projectId, id, data) => http.put(`/projects/${projectId}/comm-types/${id}`, data)
export const deleteCommType = (projectId, id, config) => http.delete(`/projects/${projectId}/comm-types/${id}`, config)

// --- Tags ---
export const getTags = (projectId, params) => http.get(`/projects/${projectId}/tags`, { params })
export const createTag = (projectId, data) => http.post(`/projects/${projectId}/tags`, data)
export const updateTag = (projectId, id, data) => http.put(`/projects/${projectId}/tags/${id}`, data)
export const deleteTag = (projectId, id, config) => http.delete(`/projects/${projectId}/tags/${id}`, config)

// --- Checkins ---
export const getAllCheckins = (params) => http.get('/projects/checkins', { params })
export const getTodayCheckinStatus = (date) => http.get('/projects/checkins/today-update-status', { params: date ? { date } : {} })
export const createCheckin = (data) => http.post('/projects/checkins', data)
export const updateCheckin = (id, data) => http.put(`/projects/checkins/${id}`, data)
export const deleteCheckin = (projectId, id) => http.delete(`/projects/${projectId}/checkins/${id}`)
export const batchDeleteCheckins = (ids) => http.post('/projects/checkins/batch-delete', { ids })

// --- Leaves（请假：年假/调休/请假） ---
export const getLeaves = (params) => http.get('/leave', { params })
export const getLeaveWorkdays = (params) => http.get('/leave/workdays', { params })
export const createLeave = (data) => http.post('/leave', data)
export const updateLeave = (id, data) => http.put(`/leave/${id}`, data)
export const deleteLeave = (id) => http.delete(`/leave/${id}`)
export const batchDeleteLeaves = (ids) => http.post('/leave/batch-delete', { ids })

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

// --- Task Requirements ---
export const linkRequirement = (projectId, taskId, requirementId) =>
  http.post(`/projects/${projectId}/tasks/${taskId}/requirements`, { requirement_id: requirementId })
export const unlinkRequirement = (projectId, taskId, requirementId) =>
  http.delete(`/projects/${projectId}/tasks/${taskId}/requirements/${requirementId}`)

// --- Project Contacts ---
export const getProjectContacts = (projectId, params) => http.get(`/projects/${projectId}/contacts`, { params })
export const addProjectContact = (projectId, data) => http.post(`/projects/${projectId}/contacts`, data)
export const updateProjectContact = (projectId, contactId, data) => http.put(`/projects/${projectId}/contacts/${contactId}`, data)
export const deleteProjectContact = (projectId, contactId, config) => http.delete(`/projects/${projectId}/contacts/${contactId}`, config)

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

// --- Communication Images (内联图片，不创建 Attachment 记录) ---
export const uploadCommImage = (projectId, taskId, commId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(`/projects/${projectId}/tasks/${taskId}/communications/${commId}/images`, fd)
}

// --- Settings ---
export const getSettings = () => http.get('/process/settings')
export const updateUserSettings = (data) => http.put('/process/settings/user', data)

// --- Salary（薪资记录） ---
export const getSalaryRecords = (params) => http.get('/salary/records', { params })
export const getSalaryYears = () => http.get('/salary/years')
export const getSalaryRecord = (id) => http.get(`/salary/records/${id}`)
export const createSalaryRecord = (data) => http.post('/salary/records', data)
export const updateSalaryRecord = (id, data) => http.put(`/salary/records/${id}`, data)
export const deleteSalaryRecord = (id) => http.delete(`/salary/records/${id}`)
export const getSalarySummary = (params) => http.get('/salary/summary', { params })
export const getSalaryConfig = () => http.get('/salary/config')
export const updateSalaryConfig = (data) => http.put('/salary/config', data)
export const getSalaryTaxSummary = (params) => http.get('/salary/tax-summary', { params })
export const calcSalaryTax = (data) => http.post('/salary/calc-tax', data)
export const exportSalary = (params) =>
  http.get('/salary/export', {
    params,
    responseType: 'blob',
    rawResponse: true,
    _silentError: true,
  })

// --- Tax Adjustments（个税汇算调整项） ---
export const getTaxAdjustments = (params) => http.get('/salary/tax-adjustments', { params })
export const createTaxAdjustment = (data) => http.post('/salary/tax-adjustments', data)
export const updateTaxAdjustment = (id, data) => http.put(`/salary/tax-adjustments/${id}`, data)
export const deleteTaxAdjustment = (id) => http.delete(`/salary/tax-adjustments/${id}`)

// --- Holiday Overrides ---
export const getHolidayOverrides = (year) => http.get('/projects/holiday-overrides', { params: { year } })
export const getHolidays = (year) => http.get('/projects/holidays', { params: { year }, _silentError: true, timeout: 5000 })
export const setHolidayOverride = (data) => http.put('/projects/holiday-overrides', data)
export const deleteHolidayOverrides = (dates) => http.delete('/projects/holiday-overrides', { params: { dates }, _silentError: true })

// --- Export ---
export const exportTaskDoc = (projectId, taskId, params) =>
  http.get(`/projects/${projectId}/tasks/${taskId}/export`, {
    params,
    responseType: 'blob',
    rawResponse: true,
    _silentError: true,
  })

// --- Requirements ---
export const getRequirements = (projectId, params) => http.get(`/projects/${projectId}/requirements`, { params })
export const getReqFilterStats = (projectId, params) => http.get(`/projects/${projectId}/requirements/filter-stats`, { params })
export const createRequirement = (projectId, data) => http.post(`/projects/${projectId}/requirements`, data)
export const getRequirement = (projectId, reqId) => http.get(`/projects/${projectId}/requirements/${reqId}`)
export const updateRequirement = (projectId, reqId, data) => http.put(`/projects/${projectId}/requirements/${reqId}`, data)
export const deleteRequirement = (projectId, reqId) => http.delete(`/projects/${projectId}/requirements/${reqId}`)
export const exportRequirementDoc = (projectId, reqId) =>
  http.get(`/projects/${projectId}/requirements/${reqId}/export`, {
    responseType: 'blob',
    rawResponse: true,
    _silentError: true,
  })
export const deleteRequirementImage = (projectId, reqId, filename) => http.delete(`/projects/${projectId}/requirements/${reqId}/images/${encodeURIComponent(filename)}`)
export const uploadRequirementImage = (projectId, reqId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(`/projects/${projectId}/requirements/${reqId}/images`, fd)
}

// --- Requirement Files ---
export const uploadRequirementFile = (projectId, reqId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(`/projects/${projectId}/requirements/${reqId}/files`, fd)
}
export const deleteRequirementFile = (projectId, reqId, filename) => http.delete(`/projects/${projectId}/requirements/${reqId}/files/${encodeURIComponent(filename)}`)

// --- Requirement Custom Fields ---
export const getReqCustomFields = (projectId, params) => http.get(`/projects/${projectId}/requirements/fields`, { params })
export const createReqCustomField = (projectId, data) => http.post(`/projects/${projectId}/requirements/fields`, data)
export const updateReqCustomField = (projectId, fieldId, data) => http.put(`/projects/${projectId}/requirements/fields/${fieldId}`, data)
export const deleteReqCustomField = (projectId, fieldId, config) => http.delete(`/projects/${projectId}/requirements/fields/${fieldId}`, config)
export const getReqCustomFieldValues = (projectId, fieldId) => http.get(`/projects/${projectId}/requirements/fields/${fieldId}/existing-values`)

// --- Dashboard ---
export const getDashboardStats = (projectId) => http.get(`/projects/${projectId}/requirements/stats/dashboard`)
export const getKanbanTasks = (projectId) => http.get(`/projects/${projectId}/tasks/kanban`)
export const getKanbanConfig = (projectId) => http.get(`/projects/${projectId}/tasks/kanban-config`, { _silentError: true })
export const putKanbanConfig = (projectId, data) => http.put(`/projects/${projectId}/tasks/kanban-config`, data)
export const getTaskSortConfig = (projectId) => http.get(`/projects/${projectId}/tasks/sort-config`, { _silentError: true })
export const putTaskSortConfig = (projectId, data) => http.put(`/projects/${projectId}/tasks/sort-config`, data)
// --- Dashboard 需求字段选择配置 ---
export const getReqKanbanConfig = (projectId) => http.get(`/projects/${projectId}/requirements/kanban-config`, { _silentError: true })
export const putReqKanbanConfig = (projectId, data) => http.put(`/projects/${projectId}/requirements/kanban-config`, data)

// --- Requirement Status Pools ---
export const getReqStatusPools = (projectId, params) => http.get(`/projects/${projectId}/requirements/status-pools`, { params })
export const createReqStatusPool = (projectId, data) => http.post(`/projects/${projectId}/requirements/status-pools`, data)
export const updateReqStatusPool = (projectId, id, data) => http.put(`/projects/${projectId}/requirements/status-pools/${id}`, data)
export const deleteReqStatusPool = (projectId, id, config) => http.delete(`/projects/${projectId}/requirements/status-pools/${id}`, config)

// --- Requirement Priority Pools ---
export const getReqPriorityPools = (projectId, params) => http.get(`/projects/${projectId}/requirements/priority-pools`, { params })
export const createReqPriorityPool = (projectId, data) => http.post(`/projects/${projectId}/requirements/priority-pools`, data)
export const updateReqPriorityPool = (projectId, id, data) => http.put(`/projects/${projectId}/requirements/priority-pools/${id}`, data)
export const deleteReqPriorityPool = (projectId, id, config) => http.delete(`/projects/${projectId}/requirements/priority-pools/${id}`, config)

export const importRequirementsPreview = (projectId, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return http.post(`/projects/${projectId}/requirements/import/preview`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000,
  })
}

export const importRequirements = (projectId, file, mapping, mode = 'append', force = false, dupStrategy = 'cancel') => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('mapping', JSON.stringify(mapping))
  fd.append('mode', mode)
  fd.append('force', String(force))
  fd.append('dup_strategy', dupStrategy)
  return http.post(`/projects/${projectId}/requirements/import`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

// --- Column Widths ---
export const getReqColWidths = (projectId) =>
  http.get(`/projects/${projectId}/requirements/column-widths`)

export const saveReqColWidths = (projectId, data) =>
  http.put(`/projects/${projectId}/requirements/column-widths`, data, { _silentError: true })

export const deleteReqColWidths = (projectId) =>
  http.delete(`/projects/${projectId}/requirements/column-widths`)

// --- View State ---
export const getReqViewState = (projectId) =>
  http.get(`/projects/${projectId}/requirements/view-state`)

export const saveReqViewState = (projectId, data) =>
  http.put(`/projects/${projectId}/requirements/view-state`, data, { _silentError: true })

// --- Attendance Export (后端 openpyxl 生成含原生图表的 xlsx) ---
export const exportAttendanceExcel = (data) =>
  http.post('/attendance/export-excel', data, {
    responseType: 'blob',
    rawResponse: true,
    _silentError: true,
  })

// --- Backup & Restore ---
export const createBackup = (scope) => http.post('/backup/create', { scope })

export const listBackups = () => http.get('/backup/list')

export const downloadBackup = (filename) =>
  http.get(`/backup/download/${encodeURIComponent(filename)}`, {
    responseType: 'blob',
    rawResponse: true,
  })
export const getBackupDownloadUrl = (filename) => `/api/backup/download/${encodeURIComponent(filename)}`

export const deleteBackup = (filename) =>
  http.delete(`/backup/delete/${encodeURIComponent(filename)}`)

export const restoreBackup = (file, restoreScope) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('restore_scope', restoreScope)
  fd.append('confirm', 'true')
  return http.post('/backup/restore', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export const exportProjectBackup = (projectId, includeUploads = true) =>
  http.post('/backup/export-project', { project_id: projectId, include_uploads: includeUploads }, {
    responseType: 'blob',
    rawResponse: true,
    timeout: 120000,
  })

export const getBackupProjects = () => http.get('/backup/projects')

export const getBackupSchedule = () => http.get('/backup/schedule')

export const setBackupSchedule = (data) => http.put('/backup/schedule', data)

export const backupSingleProject = (projectId, includeUploads = true) =>
  http.post('/backup/backup-project', { project_id: projectId, include_uploads: includeUploads })

export const restoreProjectBackup = (filename, mode) =>
  http.post('/backup/restore-project', { filename, mode })

export const restoreProjectBackupUpload = (file, mode) => {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('mode', mode)
  return http.post('/backup/restore-project-upload', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
}

export const restoreByName = (filename, restoreScope) =>
  http.post('/backup/restore-by-name', { filename, restore_scope: restoreScope })
