import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/projects' },
    { path: '/projects', component: () => import('../views/ProjectList.vue'), name: 'projects' },
    { path: '/projects/:projectId', component: () => import('../views/TaskList.vue'), name: 'task-list' },
    { path: '/projects/:projectId/tasks/:taskId', component: () => import('../views/TaskDetail.vue'), name: 'task-detail' },
    { path: '/projects/:projectId/requirements', component: () => import('../views/RequirementList.vue'), name: 'requirements' },
    { path: '/projects/:projectId/dashboard', component: () => import('../views/Dashboard.vue'), name: 'dashboard' },
    { path: '/projects/:projectId/settings', component: () => import('../views/ProjectSettings.vue'), name: 'project-settings' },
    { path: '/projects/:projectId/requirements/settings', component: () => import('../views/RequirementSettings.vue'), name: 'requirement-settings' },
    { path: '/checkins', component: () => import('../views/Checkins.vue'), name: 'checkins' },
    { path: '/process', component: () => import('../views/ProcessManagement.vue'), name: 'process' },
  ]
})

export default router
