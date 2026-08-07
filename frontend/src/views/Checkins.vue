<template>
  <div>
    <div class="page-header">
      <div>
        <h1 class="page-title">工作记录</h1>
        <p class="page-sub">每日签到与工作记录</p>
      </div>
      <div style="display:flex;gap:8px">
        <el-button :type="deleteBatchMode ? 'danger' : 'default'" @click="toggleDeleteBatchMode">
          <el-icon><Delete /></el-icon> {{ deleteBatchMode ? '退出删除' : '批量删除' }}
        </el-button>
        <el-button :type="batchMode ? 'warning' : 'default'" @click="toggleBatchMode">
          <el-icon><Select /></el-icon> {{ batchMode ? '退出批量' : '批量签到' }}
        </el-button>
        <el-button type="success" :disabled="isCheckinDisabled(selectedDate || todayStr)" @click="openCheckinDialog">
          <el-icon><Select /></el-icon> 签到
        </el-button>
        <el-button type="warning" :disabled="isLeaveDisabled(selectedDate || todayStr)" @click="openLeaveDialog()">请假</el-button>
      </div>
    </div>

    <div class="calendar-layout">
      <!-- 日历 -->
      <div class="cal-panel" :class="{ 'batch-mode': batchMode, 'delete-batch-mode': deleteBatchMode }">
          <div class="cal-nav">
            <el-button size="small" text @click="prevMonth"><el-icon><ArrowLeft /></el-icon></el-button>
            <el-popover :visible="showMonthPicker" placement="bottom-start" :width="240" trigger="click" @update:visible="onPickerVisible">
              <template #reference>
                <span class="cal-month-title cal-month-clickable">{{ calYear }}年{{ calMonth }}月</span>
              </template>
              <div class="month-picker">
                <div class="mp-year-row">
                  <el-button size="small" text @click="changeMpYear(-1)"><el-icon><ArrowLeft /></el-icon></el-button>
                  <span class="mp-year">{{ mpYear }}年</span>
                  <el-button size="small" text @click="changeMpYear(1)"><el-icon><ArrowRight /></el-icon></el-button>
                </div>
                <div class="mp-month-grid">
                  <button
                    v-for="m in 12"
                    :key="m"
                    class="mp-month"
                    :class="{ active: m === calMonth && mpYear === calYear }"
                    @click="pickMonth(m)"
                  >{{ m }}月</button>
                </div>
              </div>
            </el-popover>
            <el-button size="small" text @click="nextMonth"><el-icon><ArrowRight /></el-icon></el-button>
            <el-button size="small" text style="margin-left:8px" @click="goToday">今天</el-button>
            <el-button size="small" text style="margin-left:auto" @click="showHolidaySettings = true">
              <el-icon><Setting /></el-icon>
            </el-button>
          </div>
          <div class="cal-weekdays">
            <div v-for="w in weekDays" :key="w" class="cal-weekday">{{ w }}</div>
          </div>
          <div v-if="holidayVersion" class="cal-grid">
            <div
              v-for="(day, i) in calendarDays"
              :key="i"
              class="cal-cell"
              :class="{
                'cal-cell-empty': day.empty,
                today: day.isToday,
                active: !batchMode && !deleteBatchMode && day.date === selectedDate,
                'has-checkin': checkinsByDate[day.date],
                'batch-selected': batchMode && batchDates.includes(day.date),
                'batch-disabled': (batchMode && checkinsByDate[day.date]),
                'delete-selected': deleteBatchMode && deleteDates.includes(day.date),
                'delete-disabled': (deleteBatchMode && !checkinsByDate[day.date] && (!day.leaveTypes || !day.leaveTypes.length)),
                'cal-cell-disabled': (batchMode && (day.beforeEntry || day.isFuture)),
              }"
              @click="onCellClick(day)"
            >
              <template v-if="!day.empty">
                <span class="cal-cell-num">{{ day.num }}</span>
                <span v-if="day.holiday && day.holiday.badge" class="cal-cell-badge" :class="'cb-' + day.holiday.badgeType">{{ day.holiday.badge }}</span>
                <span v-if="day.status === 'attendance' && !batchMode && !deleteBatchMode" class="cal-cell-dot"></span>
                <span v-if="day.status === 'overtime' && !batchMode && !deleteBatchMode" class="cal-cell-label cal-cell-overtime">加</span>
                <span v-if="day.status === 'leave' && !batchMode && !deleteBatchMode" class="cal-cell-label cal-cell-absence">缺</span>
                <template v-for="lt in day.leaveTypes" :key="lt">
                  <span
                    v-if="!batchMode && !deleteBatchMode"
                    class="cal-cell-label"
                    :class="'cal-cell-leave-' + lt"
                  >{{ leaveTypeShort(lt) }}</span>
                </template>
                <span v-if="mandayByDate[day.date] > 1 && !batchMode && !deleteBatchMode" class="cal-cell-manday">{{ mandayByDate[day.date] }}</span>
                <span v-if="batchMode && checkinsByDate[day.date]" class="cal-cell-checked">已签</span>
                <span v-if="deleteBatchMode && (checkinsByDate[day.date] || (day.leaveTypes && day.leaveTypes.length))" class="cal-cell-has-data">有记录</span>
              </template>
            </div>
          </div>
          <!-- 数据加载中 -> 骨架占位 -->
          <div v-else class="cal-grid cal-grid-loading">
            <div v-for="i in 42" :key="i" class="cal-cell cal-cell-empty">&nbsp;</div>
          </div>

          <!-- 批量签到底部栏 -->
          <div v-if="batchMode" class="batch-bar">
            <span>已选 {{ batchDates.length }} 天</span>
            <el-button size="small" type="primary" :disabled="!batchDates.length" @click="openBatchDialog">
              确定签到
            </el-button>
          </div>

          <!-- 批量删除底部栏 -->
          <div v-if="deleteBatchMode" class="delete-batch-bar">
            <span>已选 <strong>{{ deleteDates.length }}</strong> 天</span>
            <el-button size="small" type="danger" :disabled="!deleteDates.length" @click="confirmBatchDelete">
              <el-icon><Delete /></el-icon> 删除选中
            </el-button>
          </div>
        </div>

        <!-- 月份出勤统计卡片 -->
        <div class="cal-stats-card">
          <div class="cal-stats-title">{{ calYear }}年{{ calMonth }}月出勤</div>
          <div class="cal-stats-row">
            <span class="cal-stats-item">应出勤 <strong>{{ monthStats.requiredWorkDays }}</strong></span>
            <span class="cal-stats-divider"></span>
            <span class="cal-stats-item">上班 <strong>{{ monthStats.workDays }}</strong></span>
            <span class="cal-stats-divider"></span>
            <span class="cal-stats-item">加班 <strong>{{ monthStats.overtimeDays }}</strong></span>
            <span class="cal-stats-divider"></span>
            <span class="cal-stats-item">人天 <strong class="cal-manday-num">{{ monthStats.manDays }}</strong></span>
          </div>
          <div class="cal-stats-overtime">
            缺勤 <strong>{{ monthStats.absenceDays }}</strong> ·
            年假 <strong class="cal-leave-annual">{{ monthStats.annualDays }}</strong> ·
            调休 <strong class="cal-leave-comp">{{ monthStats.compensatoryDays }}</strong> ·
            请假 <strong class="cal-leave-personal">{{ monthStats.personalDays }}</strong>
          </div>
        </div>

      <!-- 右侧详情 -->
      <div class="cal-detail">
        <template v-if="selectedDate && !batchMode && !deleteBatchMode">
          <div class="cal-detail-header"><h3>{{ formatDateFull(selectedDate) }}</h3></div>
          <div v-if="checkinsByDate[selectedDate]?.length" class="cal-checkins">
            <div v-for="chk in checkinsByDate[selectedDate]" :key="chk.id" class="cal-checkin-card">
              <div class="cal-cc-top">
                <template v-for="p in chk.projects" :key="p.id">
                  <span class="cal-cc-project">{{ p.name }}</span>
                </template>
                <span class="cal-cc-manday-badge">{{ chk.man_days }} 人天</span>
                <span v-if="chk.man_day_reason" class="cal-cc-manday-reason">{{ chk.man_day_reason }}</span>
                <span class="cal-cc-time">{{ dayjs.utc(chk.created_at).utcOffset(8).format('HH:mm') }}</span>
                <el-button size="small" text type="danger" @click="removeCheckin(chk)"><el-icon><Delete /></el-icon></el-button>
              </div>
              <div v-if="chk.tasks?.length" class="cal-cc-tasks">
                <span v-for="t in chk.tasks" :key="t.id" class="cal-cc-task">{{ t.title }}</span>
              </div>
              <div class="cal-cc-content">{{ chk.content || '已签到' }}</div>
            </div>
          </div>
          <div v-if="leavesByDate[selectedDate]?.length" class="cal-leaves">
            <div v-for="lv in leavesByDate[selectedDate]" :key="lv.id" class="cal-leave-card">
              <span class="cal-leave-type" :class="'clt-' + lv.leave_type">{{ leaveTypeLabel(lv.leave_type) }}</span>
              <span v-if="lv.subtype" class="cal-leave-sub">{{ lv.subtype }}</span>
              <span class="cal-leave-days">{{ lv.days }} 天</span>
              <span class="cal-leave-actions">
                <el-button size="small" text type="primary" @click="openLeaveDialog(lv)">编辑</el-button>
                <el-button size="small" text type="danger" @click="removeLeave(lv)"><el-icon><Delete /></el-icon></el-button>
              </span>
              <div v-if="lv.reason" class="cal-leave-reason">{{ lv.reason }}</div>
            </div>
          </div>
          <el-empty v-if="!checkinsByDate[selectedDate]?.length && !leavesByDate[selectedDate]?.length" description="该日无记录" :image-size="60" />
        </template>
        <template v-else-if="deleteBatchMode">
          <div class="cal-detail-header"><h3>批量删除记录</h3></div>
          <p style="font-size:13px;color:#888;line-height:1.6">
            请在左侧日历中点击<span style="color:#f56c6c;font-weight:500">已有记录</span>的日期进行选择，
            选完后点击「删除选中」按钮批量删除签到和请假记录。
          </p>
          <div v-if="deleteDates.length" style="margin-top:16px">
            <p style="font-size:13px;font-weight:500;color:#f56c6c;margin-bottom:8px">已选 {{ deleteDates.length }} 天：</p>
            <div v-for="d in deleteDates" :key="d" class="delete-date-item">
              <span>{{ d }}</span>
              <span style="color:#999;font-size:12px">{{ (checkinsByDate[d]?.length || 0) + (leavesByDate[d]?.length || 0) }} 条记录</span>
            </div>
          </div>
        </template>
        <el-empty v-else-if="!batchMode" description="点击日期查看签到记录" :image-size="60" />
        </div>

        <!-- 工具 -->
        <div class="cal-tools-card">
          <div class="cal-tools-title">工具</div>
          <el-button text class="cal-tools-btn" @click="showCalcDlg = true">
            <el-icon><DataAnalysis /></el-icon> 出勤计算器
          </el-button>
        </div>
    </div>

    <!-- 单次签到对话框 -->
    <el-dialog v-model="showCheckinDlg" :title="editingCheckinId ? '编辑签到' : '签到'" width="580px" @close="resetCheckinForm">
      <div style="font-size:13px;color:#534ab7;margin-bottom:12px;font-weight:500">签到日期：{{ checkinForm.date }}</div>
      <el-form :model="checkinForm" label-width="90px">
        <el-form-item label="多项目">
          <el-switch v-model="checkinForm.multi_project" @change="onMultiChange" />
          <span style="margin-left:8px;font-size:12px;color:#888">开启后可选择多个项目</span>
        </el-form-item>
        <el-form-item :label="checkinForm.multi_project ? '项目' : '项目'" required>
          <el-select v-model="projectSelectModel" :multiple="checkinForm.multi_project" placeholder="选择项目" style="width:100%" @change="onProjectChange">
            <el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name">
              <span class="status-dot" :class="hasProjectUpdateToday(p.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ p.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="相关任务">
          <el-select v-model="checkinForm.task_ids" multiple placeholder="可选，可多选" style="width:100%">
            <el-option v-for="t in tasksForSelected" :key="t.id" :value="t.id" :label="t.title">
              <span class="status-dot" :class="hasTaskUpdateToday(t.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ t.title }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="工作记录">
          <el-input v-model="checkinForm.content" type="textarea" :rows="4" placeholder="今天做了什么？" />
        </el-form-item>
        <el-form-item v-if="!checkinForm.multi_project" label="人天">
          <el-input-number v-model="checkinForm.man_days" :min="0" :step="0.5" :precision="2" controls-position="right" style="width:160px" />
          <span style="margin-left:8px;font-size:12px;color:#888">默认 1 人天，加班等可 &gt;1</span>
        </el-form-item>
        <el-form-item v-else label="项目分配">
          <div class="pmd-block">
            <div v-for="pid in checkinForm.project_ids" :key="pid" class="pmd-row">
              <span class="pmd-name">{{ projectNameById(pid) }}</span>
              <el-input-number v-model="projectManDays[pid]" :min="0" :step="0.5" :precision="2" controls-position="right" style="width:120px" />
              <span class="pmd-unit">人天</span>
              <el-input-number v-model="projectDays[pid]" :min="0" :step="0.5" :precision="2" controls-position="right" style="width:110px" />
              <span class="pmd-unit">天</span>
            </div>
            <div class="pmd-foot">
              <span>合计 <strong class="pmd-sum-num">{{ multiManDaySum }}</strong> 人天 · <strong class="pmd-sum-num">{{ multiDaySum }}</strong> 天</span>
              <el-button text size="small" type="primary" @click="splitSingleEvenly">均分</el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="人天说明">
          <el-input v-model="checkinForm.man_day_reason" placeholder="如：加班、并行多项目、调休补班等（可选）" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCheckinDlg = false">取消</el-button>
        <el-button type="primary" :loading="checkinLoading" @click="submitCheckin">{{ editingCheckinId ? '保存' : '签到' }}</el-button>
      </template>
    </el-dialog>

    <!-- 批量签到对话框 -->
    <el-dialog v-model="showBatchDlg" title="批量签到" width="580px" @close="resetBatchForm">
      <div style="font-size:13px;color:#534ab7;margin-bottom:12px;font-weight:500">签到日期：共 {{ batchDates.length }} 天（{{ batchDates[0] }} ~ {{ batchDates[batchDates.length-1] }}）</div>
      <el-form :model="batchForm" label-width="90px">
        <el-form-item label="多项目">
          <el-switch v-model="batchForm.multi_project" @change="onBatchMultiChange" />
        </el-form-item>
        <el-form-item label="项目" required>
          <el-select v-model="batchProjectModel" :multiple="batchForm.multi_project" placeholder="选择项目" style="width:100%" @change="onBatchProjectChange">
            <el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name">
              <span class="status-dot" :class="hasProjectUpdateToday(p.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ p.name }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="相关任务">
          <el-select v-model="batchForm.task_ids" multiple placeholder="可选" style="width:100%">
            <el-option v-for="t in batchTasks" :key="t.id" :value="t.id" :label="t.title">
              <span class="status-dot" :class="hasTaskUpdateToday(t.id) ? 'dot-green' : 'dot-gray'"></span>
              {{ t.title }}
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="工作记录">
          <el-input v-model="batchForm.content" type="textarea" :rows="4" placeholder="所有选中日期共用此记录" />
        </el-form-item>
        <el-form-item v-if="!batchForm.multi_project" label="人天">
          <el-input-number v-model="batchForm.man_days" :min="0" :step="0.5" :precision="2" controls-position="right" style="width:160px" />
          <span style="margin-left:8px;font-size:12px;color:#888">默认 1 人天，加班等可 &gt;1</span>
        </el-form-item>
        <el-form-item v-else label="项目分配">
          <div class="pmd-block">
            <div v-for="pid in batchForm.project_ids" :key="pid" class="pmd-row">
              <span class="pmd-name">{{ projectNameById(pid) }}</span>
              <el-input-number v-model="batchProjectManDays[pid]" :min="0" :step="0.5" :precision="2" controls-position="right" style="width:120px" />
              <span class="pmd-unit">人天</span>
              <el-input-number v-model="batchProjectDays[pid]" :min="0" :step="0.5" :precision="2" controls-position="right" style="width:110px" />
              <span class="pmd-unit">天</span>
            </div>
            <div class="pmd-foot">
              <span>合计 <strong class="pmd-sum-num">{{ batchManDaySum }}</strong> 人天 · <strong class="pmd-sum-num">{{ batchDaySum }}</strong> 天</span>
              <el-button text size="small" type="primary" @click="splitBatchEvenly">均分</el-button>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="人天说明">
          <el-input v-model="batchForm.man_day_reason" placeholder="如：加班、并行多项目、调休补班等（可选）" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showBatchDlg = false">取消</el-button>
        <el-button type="primary" :loading="batchLoading" @click="submitBatch">确定（{{ batchDates.length }} 天）</el-button>
      </template>
    </el-dialog>

    <!-- 新增/编辑请假 -->
    <el-dialog v-model="showLeaveDlg" :title="editingLeaveId ? '编辑请假' : '新增请假'" width="480px" @close="resetLeaveForm">
      <el-form :model="leaveForm" label-width="80px">
        <el-form-item label="类型" required>
          <el-select v-model="leaveForm.leave_type" style="width:100%">
            <el-option v-for="t in LEAVE_TYPES" :key="t.value" :value="t.value" :label="t.label" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="leaveForm.leave_type === 'personal'" label="子类">
          <el-select v-model="leaveForm.subtype" placeholder="可选" style="width:100%" filterable allow-create default-first-option>
            <el-option v-for="s in LEAVE_SUBTYPES" :key="s" :value="s" :label="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="日期" required>
          <el-date-picker v-model="leaveForm.date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width:100%" @change="computeLeaveWorkdays" />
        </el-form-item>
        <el-form-item v-if="!editingLeaveId" label="结束日期（留空=单日）">
          <el-date-picker v-model="leaveForm.date_end" type="date" value-format="YYYY-MM-DD" placeholder="选范围=批量按工作日逐日生成" style="width:100%" :disabled-date="disabledEndDate" @change="computeLeaveWorkdays" />
        </el-form-item>
        <el-form-item v-if="!editingLeaveId" label="工作日">
          <span v-if="leaveWorkdaysLoading" style="font-size:13px;color:#888">
            <el-icon class="is-loading"><Loading /></el-icon> 计算中…
          </span>
          <span v-else>
            <strong style="font-size:16px;color:#e67e22">{{ leaveWorkdays }}</strong> 天
            <span style="margin-left:8px;font-size:12px;color:#888">将生成 {{ leaveWorkdays }} 条请假记录（自动排除周末/法定假，仅含应上班的工作日）</span>
          </span>
        </el-form-item>
        <el-form-item label="事由">
          <el-input v-model="leaveForm.reason" type="textarea" :rows="3" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showLeaveDlg = false">取消</el-button>
        <el-button type="primary" :loading="leaveLoading" @click="submitLeave">{{ editingLeaveId ? '保存' : '确定' }}</el-button>
      </template>
    </el-dialog>

    <!-- 出勤计算器 -->
    <el-dialog v-model="showCalcDlg" title="出勤计算器" width="680px" top="5vh">
      <div class="calc-range">
        <span style="font-size:13px;color:#888;margin-right:8px">统计范围</span>
        <el-date-picker
          v-model="calcStart"
          type="date"
          placeholder="开始日期"
          value-format="YYYY-MM-DD"
          style="width:150px"
          :disabled-date="disabledCalcStart"
          @change="onCalcDateChange"
        />
        <span style="margin:0 8px;color:#888">至</span>
        <el-date-picker
          v-model="calcEnd"
          type="date"
          placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width:150px"
          :disabled-date="disabledCalcEnd"
          @change="onCalcDateChange"
        />
        <el-button size="small" type="primary" style="margin-left:8px" @click="runCalc">计算</el-button>
        <el-button size="small" type="success" plain style="margin-left:8px" :disabled="!calcResult" @click="exportDetailXLSX">
          <el-icon><Download /></el-icon> 导出明细
        </el-button>
      </div>

      <template v-if="calcResult">
        <!-- 总统计 -->
        <div class="calc-summary">
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#2f54eb">{{ calcResult.total.requiredWorkDays }}</span>
            <span class="calc-summary-label">应出勤</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#534ab7">{{ calcResult.total.workDays }}</span>
            <span class="calc-summary-label">上班</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#8c8c8c">{{ calcResult.total.absenceDays }}</span>
            <span class="calc-summary-label">缺勤</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#185fa5">{{ calcResult.total.annualDays }}</span>
            <span class="calc-summary-label">年假</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#3b6d11">{{ calcResult.total.compensatoryDays }}</span>
            <span class="calc-summary-label">调休</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#e67e22">{{ calcResult.total.personalDays }}</span>
            <span class="calc-summary-label">请假</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#d48806">{{ calcResult.total.overtimeDays }}</span>
            <span class="calc-summary-label">加班</span>
          </div>
          <div class="calc-summary-item">
            <span class="calc-summary-num" style="color:#0f6e56">{{ calcResult.total.manDays }}</span>
            <span class="calc-summary-label">人天</span>
          </div>
        </div>
        <div v-if="calcResult.total.estimatedDays > 0" class="calc-estimated-note">
          其中 <strong>{{ calcResult.total.estimatedDays }}</strong> 天为未来日期默认预估
        </div>

        <!-- 按月详情 -->
        <div v-if="calcResult.monthly.length" class="calc-section">
          <div class="calc-section-title">按月统计</div>
          <table class="calc-month-table">
            <thead>
              <tr>
                <th class="calc-month-th-name">月份</th>
                <th>应出勤</th>
                <th>上班</th>
                <th>缺勤</th>
                <th>年假</th>
                <th>调休</th>
                <th>请假</th>
                <th>加班</th>
                <th>人天</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in calcResult.monthly" :key="m.month">
                <td class="calc-month-td-name">
                  {{ m.month }}
                  <span v-if="m.estimatedDays" class="calc-estimated-tag">预估 {{ m.estimatedDays }} 天</span>
                </td>
                <td style="color:#2f54eb;font-weight:600">{{ m.requiredWorkDays }}</td>
                <td style="color:#534ab7;font-weight:600">{{ m.workDays }}</td>
                <td style="color:#8c8c8c;font-weight:600">{{ m.absenceDays }}</td>
                <td style="color:#185fa5;font-weight:600">{{ m.annualDays }}</td>
                <td style="color:#3b6d11;font-weight:600">{{ m.compensatoryDays }}</td>
                <td style="color:#e67e22;font-weight:600">{{ m.personalDays }}</td>
                <td style="color:#d48806;font-weight:600">{{ m.overtimeDays }}</td>
                <td style="color:#0f6e56;font-weight:600">{{ m.manDays }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 按项目统计 -->
        <div v-if="calcResult.byProject.length" class="calc-section">
          <div class="calc-section-title">按项目统计</div>
          <div class="calc-proj-grid">
            <div v-for="p in calcResult.byProject" :key="p.projectId" class="calc-proj-card">
              <span class="calc-proj-name">{{ p.projectName }}</span>
              <span class="calc-proj-days"><strong>{{ p.days }}</strong> 天 · <strong style="color:#0f6e56">{{ p.manDays }}</strong> 人天</span>
            </div>
          </div>
        </div>

        <!-- 多项目签到提醒 -->
        <div v-if="calcResult.multiProjectDays?.length" class="calc-section">
          <div class="calc-section-title calc-section-title-warn">
            <el-icon style="margin-right:4px"><WarningFilled /></el-icon> 多项目签到提醒
          </div>
          <div class="calc-warn-grid">
            <div v-for="item in calcResult.multiProjectDays" :key="item.date" class="calc-warn-item">
              <div class="calc-warn-top">
                <span class="calc-warn-date">{{ item.dateLabel }}</span>
                <span class="calc-warn-weekday">周{{ item.weekday }}</span>
              </div>
              <div class="calc-warn-projs">
                <span v-for="(name, idx) in item.projectNames" :key="idx" class="calc-warn-proj">{{ name }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>

      <template v-else>
        <el-empty description="选择日期范围后点击「计算」" :image-size="50" style="padding:30px 0" />
      </template>
    </el-dialog>

    <!-- 日历设置 -->
    <el-dialog v-model="showHolidaySettings" title="日历设置" width="580px" top="5vh" @opened="initHolidaySettings">

      <div class="hs-tabs">
        <span class="hs-tab" :class="{ active: hsActiveTab === 'general' }" @click="hsActiveTab = 'general'">通用</span>
        <span class="hs-tab" :class="{ active: hsActiveTab === 'holiday' }" @click="hsActiveTab = 'holiday'">节假日</span>
      </div>

      <template v-if="hsActiveTab === 'general'">
        <!-- 通用设置 -->
        <div class="hs-entry">
          <span class="hs-entry-label">入职日期</span>
          <el-date-picker v-model="entryDateVal" type="date" placeholder="不设置则显示全部" value-format="YYYY-MM-DD" style="width:150px" @change="onEntryDateChange" />
          <el-button v-if="entryDateVal" size="small" text @click="clearEntryDate">清除</el-button>
        </div>
      </template>

      <template v-if="hsActiveTab === 'holiday'">
        <!-- 日历 -->
        <div class="hs-header">
          <div class="hs-nav">
            <el-button size="small" text @click="hsPrev"><el-icon><ArrowLeft /></el-icon></el-button>
            <span class="hs-month">{{ hsYear }}年{{ hsMonth }}月</span>
            <el-button size="small" text @click="hsNext"><el-icon><ArrowRight /></el-icon></el-button>
          </div>
          <div class="hs-legend">
            <span class="hs-tag hs-tag-normal">工作日</span>
            <span class="hs-tag hs-tag-holiday">法定假</span>
            <span class="hs-tag hs-tag-workday">调休班</span>
            <span class="hs-tag hs-tag-off">休息日</span>
            <span class="hs-override-hint">⬤ 已手动设置</span>
          </div>
        </div>
        <div class="hs-weekdays">
          <div v-for="w in weekDays" :key="w" class="hs-weekday">{{ w }}</div>
        </div>
        <div class="hs-grid">
          <div
            v-for="(cell, i) in hsDays"
            :key="i"
            class="hs-cell"
            :class="{
              'hs-cell-empty': cell.empty,
              'hs-cell-override': cell.overridden,
            }"
            @click="cycleHoliday(cell)"
          >
            <template v-if="!cell.empty">
              <span class="hs-num">{{ cell.day }}</span>
              <span class="hs-tag-sm" :class="'hs-ts-' + cell.effective">{{ hsTypeLabel(cell.effective) }}</span>
              <span v-if="cell.overridden" class="hs-override-dot"></span>
            </template>
          </div>
        </div>
      </template>

      <template #footer>
        <span class="hs-auto-save">自动保存 · 关闭后实时更新</span>
        <el-button v-if="hsActiveTab === 'holiday'" size="small" @click="hsResetMonth">重置本月</el-button>
        <el-button type="primary" @click="showHolidaySettings = false">完成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DataAnalysis, WarningFilled, Setting, Download } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import utc from 'dayjs/plugin/utc'
dayjs.extend(utc)
dayjs.locale('zh-cn')
import {
  getProjects, getAllCheckins, getTodayCheckinStatus, createCheckin, updateCheckin, deleteCheckin, batchDeleteCheckins, getTasks, exportAttendanceExcel,
  getLeaves, getLeaveWorkdays, createLeave, updateLeave, deleteLeave, batchDeleteLeaves,
} from '../api'
import { loadHolidayData, getDayExtraInfo, setHolidayOverride, getHolidayOverride, getAllOverrides, getEntryDate, setEntryDate, loadUserSettingsFromServer } from '../utils/holiday'

const projects = ref([])
const allCheckins = ref([])
const showCheckinDlg = ref(false)
const checkinLoading = ref(false)
const selectedDate = ref(null)
const tasksForSelected = ref([])
const checkinForm = ref({ project_ids: [], task_ids: [], multi_project: false, date: null, content: '', man_days: 1, man_day_reason: '' })
const editingCheckinId = ref(null) // 编辑已有签到时记录 ID

// 批量签到
const batchMode = ref(false)
const batchDates = ref([])
const showBatchDlg = ref(false)
const batchLoading = ref(false)
const batchForm = ref({ project_ids: [], task_ids: [], multi_project: false, content: '', man_days: 1, man_day_reason: '' })
const batchTasks = ref([])

// 多项目时各项目分配的人天 / 天数（project_id -> 值）
const projectManDays = ref({})
const projectDays = ref({})
const batchProjectManDays = ref({})
const batchProjectDays = ref({})
// 选中项目变化时同步分配表：移除已取消项、补默认值 0.5
const syncProjectAlloc = (ids, mdStore, dayStore) => {
  const nextMd = {}
  const nextDay = {}
  for (const pid of ids) {
    nextMd[pid] = (mdStore[pid] != null ? mdStore[pid] : 0.5)
    nextDay[pid] = (dayStore[pid] != null ? dayStore[pid] : 0.5)
  }
  for (const k of Object.keys(mdStore)) delete mdStore[k]
  for (const k of Object.keys(dayStore)) delete dayStore[k]
  Object.assign(mdStore, nextMd)
  Object.assign(dayStore, nextDay)
}
const projectNameById = (pid) => projects.value.find((p) => p.id === pid)?.name || `#${pid}`
// 多项目当天人天合计（= 各项目分配之和）；单项目直接用 man_days
const multiManDaySum = computed(() => {
  if (!checkinForm.value.multi_project) return checkinForm.value.man_days
  return checkinForm.value.project_ids.reduce((s, pid) => s + (Number(projectManDays.value[pid]) || 0), 0)
})
const multiDaySum = computed(() => {
  if (!checkinForm.value.multi_project) return 1
  return checkinForm.value.project_ids.reduce((s, pid) => s + (Number(projectDays.value[pid]) || 0), 0)
})
const batchManDaySum = computed(() => {
  if (!batchForm.value.multi_project) return batchForm.value.man_days
  return batchForm.value.project_ids.reduce((s, pid) => s + (Number(batchProjectManDays.value[pid]) || 0), 0)
})
const batchDaySum = computed(() => {
  if (!batchForm.value.multi_project) return 1
  return batchForm.value.project_ids.reduce((s, pid) => s + (Number(batchProjectDays.value[pid]) || 0), 0)
})

// 批量删除签到（日历选日期模式）
const deleteBatchMode = ref(false)
const deleteDates = ref([])

const calYear = ref(dayjs().year())
const calMonth = ref(dayjs().month() + 1)
const weekDays = ['一', '二', '三', '四', '五', '六', '日']
const todayStr = dayjs().format('YYYY-MM-DD')

// 节假日数据
// 初始即为 1：日历立即渲染（基于已缓存/周末推断数据），
// 待节假日数据（服务端/本地/接口）到达后再 ++ 刷新徽标，不再卡在骨架占位。
const holidayVersion = ref(1)
// 数据库签到数据就绪标志：网格照常秒开，但"出勤/请假/加班"状态徽标与出勤统计
// 在签到数据返回前保持中性，避免首屏把过去工作日全算成"请假"的一闪假状态。
const dataReady = ref(false)

// 请假记录（年假/调休/请假），与签到独立
const allLeaves = ref([])
const showLeaveDlg = ref(false)
const leaveLoading = ref(false)
const editingLeaveId = ref(null)
const leaveForm = ref({ leave_type: 'personal', subtype: '', date: null, date_end: null, days: 1, reason: '' })
const LEAVE_TYPES = [
  { value: 'annual', label: '年假' },
  { value: 'compensatory', label: '调休' },
  { value: 'personal', label: '请假' },
]
const LEAVE_SUBTYPES = ['事假', '病假', '婚假', '产假', '陪产假', '丧假', '其他']
const LEAVE_LABEL = { annual: '年假', compensatory: '调休', personal: '请假' }
const leaveTypeLabel = (t) => LEAVE_LABEL[t] || '请假'
const leaveTypeShort = (t) => ({ annual: '年', compensatory: '调', personal: '假' }[t] || '假')

const loadHolidayForYear = async (year) => {
  await loadHolidayData(year)
  // 也预加载前后一年，方便月份切换
  await Promise.all([loadHolidayData(year - 1), loadHolidayData(year + 1)].filter(Boolean))
}

// 出勤计算器
const showCalcDlg = ref(false)
const calcStart = ref(null)
const calcEnd = ref(null)
const calcResult = ref(null)

const onCalcDateChange = () => { calcResult.value = null }
// 入职日之前的日期不可选
const entryBefore = (date) => {
  const entryDateStr = getEntryDate()
  return entryDateStr ? dayjs(date).isBefore(dayjs(entryDateStr)) : false
}
// 开始日期：不早于入职日、不晚于结束日期
const disabledCalcStart = (date) => {
  if (entryBefore(date)) return true
  if (calcEnd.value && dayjs(date).isAfter(dayjs(calcEnd.value))) return true
  return false
}
// 结束日期：不早于入职日、不早于开始日期
const disabledCalcEnd = (date) => {
  if (entryBefore(date)) return true
  if (calcStart.value && dayjs(date).isBefore(dayjs(calcStart.value))) return true
  return false
}
const runCalc = async () => {
  if (!calcStart.value || !calcEnd.value) {
    ElMessage.warning('请选择开始和结束日期')
    return
  }
  const startStr = calcStart.value
  const endStr = calcEnd.value
  const start = dayjs(startStr)
  const end = dayjs(endStr)
  if (end.isBefore(start)) { ElMessage.warning('结束日期不能早于开始日期'); return }

  // 拉取整个日期范围的签到数据
  const rangeCheckins = await getAllCheckins({ start_date: startStr, end_date: endStr })
  // 按日期建索引
  const rangeCheckinsByDate = {}
  for (const c of rangeCheckins) {
    const d = dayjs(c.date).format('YYYY-MM-DD')
    if (!rangeCheckinsByDate[d]) rangeCheckinsByDate[d] = []
    rangeCheckinsByDate[d].push(c)
  }
  // 拉取整个日期范围的请假数据（年假/调休/请假），多日请假展开到覆盖的每一天
  const rangeLeavesRaw = await getLeaves({ start_date: startStr, end_date: endStr })
  const rangeLeavesByDate = {}
  for (const lv of rangeLeavesRaw) {
    const ls = dayjs(lv.date)
    const le = dayjs(lv.date_end || lv.date)
    for (let dd = ls; dd.isBefore(le) || dd.isSame(le); dd = dd.add(1, 'day')) {
      const ds = dd.format('YYYY-MM-DD')
      if (!rangeLeavesByDate[ds]) rangeLeavesByDate[ds] = []
      rangeLeavesByDate[ds].push(lv)
    }
  }

  const byMonth = {}
  const byProject = {}
  const multiProjectDays = [] // 多项目签到的日期列表
  const days = [] // 逐日明细
  let totalWork = 0, totalAbsence = 0, totalOvertime = 0, totalEstimated = 0, totalManDays = 0, totalRequired = 0
  const totalType = { annual: 0, compensatory: 0, personal: 0 } // 真实请假按类型计数（覆盖天数）
  const today = dayjs().startOf('day')

  for (let d = start; d.isBefore(end) || d.isSame(end); d = d.add(1, 'day')) {
    const dateStr = d.format('YYYY-MM-DD')
    const weekday = d.day()
    const extra = getDayExtraInfo(dateStr)
    const dayCheckins = rangeCheckinsByDate[dateStr] || []
    const hasCheckin = dayCheckins.length > 0
    let dayManDays = 0 // 当天人天
    const dayProjectNames = []
    for (const chk of dayCheckins) {
      for (const p of chk.projects || []) {
        if (!dayProjectNames.includes(p.name)) dayProjectNames.push(p.name)
      }
    }
    const isFuture = d.isAfter(today)
    const monthKey = d.format('YYYY年M月')
    const entryDateStr = getEntryDate()
    const beforeEntry = entryDateStr && dateStr < entryDateStr

    if (beforeEntry) continue

    if (!byMonth[monthKey]) byMonth[monthKey] = { workDays: 0, absenceDays: 0, overtimeDays: 0, estimatedDays: 0, manDays: 0, requiredWorkDays: 0, annualDays: 0, compensatoryDays: 0, personalDays: 0 }

    if (hasCheckin) {
      totalWork++
      byMonth[monthKey].workDays++

      // 当天人天合计（该日所有签到记录 man_days 之和，0 人天按 0 计）
      dayManDays = dayCheckins.reduce((s, c) => s + (c.man_days == null ? 1 : c.man_days), 0)
      totalManDays += dayManDays
      byMonth[monthKey].manDays += dayManDays

      // 多项目提醒仍基于界面可见项目（chk.projects）
      const dayProjects = new Set()
      for (const chk of dayCheckins) {
        for (const p of chk.projects || []) dayProjects.add(p.id)
      }
      // 按项目统计：遍历 project_man_days（含已删除/孤儿项目的分配明细），
      // 保证按项目人天合计 == 顶部总人天；无法归属的部分归入“未关联项目”。
      for (const chk of dayCheckins) {
        const pmd = chk.project_man_days || {}
        const pdays = chk.project_days || {}
        const totalMD = chk.man_days == null ? 1 : chk.man_days
        const pmdKeys = Object.keys(pmd)
        // 无分配明细但有可见项目时，按旧逻辑均分（数据异常兜底）
        if (pmdKeys.length === 0 && (chk.projects || []).length) {
          const projCount = chk.projects.length
          for (const p of chk.projects) {
            const alloc = totalMD / projCount
            if (!byProject[p.id]) byProject[p.id] = { projectId: p.id, projectName: p.name, days: 0, manDays: 0 }
            byProject[p.id].manDays += alloc
            // 天数：优先用用户填的天数；缺失时人天>0按比例分配、人天≤0按项目数均分（单项目=1天）
            const pd = pdays[p.id]
            byProject[p.id].days += pd != null ? pd : (totalMD > 0 ? alloc / totalMD : 1 / projCount)
          }
          continue
        }
        let accounted = 0
        for (const pidStr of pmdKeys) {
          const pid = Number(pidStr)
          const alloc = pmd[pidStr]
          accounted += alloc
          const rawName = projectNameById(pid)
          const name = rawName && rawName.startsWith('#') ? '已删除项目' : rawName
          if (!byProject[pid]) byProject[pid] = { projectId: pid, projectName: name, days: 0, manDays: 0 }
          byProject[pid].manDays += alloc
          // 天数：优先用用户填的天数；缺失时人天>0按人天比例分配；人天≤0按项目均分（单项目=1天，多项目各1/N）
          const pd = pdays[pidStr]
          byProject[pid].days += pd != null ? pd : (totalMD > 0 ? alloc / totalMD : 1 / pmdKeys.length)
        }
        // 当天有人天但未分配到任何项目（关联已删且无保留分配）→ 归入“未关联项目”
        const remainder = totalMD - accounted
        if (remainder > 1e-9) {
          if (!byProject.__unassigned__) byProject.__unassigned__ = { projectId: '__unassigned__', projectName: '未关联项目', days: 0, manDays: 0 }
          byProject.__unassigned__.manDays += remainder
          byProject.__unassigned__.days += totalMD > 0 ? remainder / totalMD : 0
        }
      }
      // 检查当天是否涉及多个项目
      if (dayProjects.size >= 2) {
        const projectNames = []
        for (const chk of dayCheckins) {
          for (const p of chk.projects || []) {
            if (!projectNames.includes(p.name)) projectNames.push(p.name)
          }
        }
        multiProjectDays.push({
          date: dateStr,
          dateLabel: d.format('M月D日'),
          weekday: ['日','一','二','三','四','五','六'][weekday],
          projectCount: dayProjects.size,
          projectNames,
        })
      }
    } else if (isFuture) {
      // 未来日期：默认工作日已上班
      // 判断当日有效类型
      let effIsRest
      if (extra.override === 'off') effIsRest = true
      else if (extra.override === 'normal') effIsRest = false
      else if (extra.badgeType === 'workday') effIsRest = false
      else if (extra.badgeType === 'holiday') effIsRest = true
      else if (weekday === 0 || weekday === 6) effIsRest = true
      else effIsRest = false

      if (!effIsRest) {
        totalWork++
        totalEstimated++
        byMonth[monthKey].workDays++
        byMonth[monthKey].estimatedDays++
        dayManDays = 1 // 未来预估工作日按 1 人天计
        totalManDays += 1
        byMonth[monthKey].manDays += 1
      }
    }

    // 请假与加班统计
    let effIsRest
    if (extra.override === 'off') effIsRest = true
    else if (extra.override === 'normal') effIsRest = false
    else if (extra.badgeType === 'workday') effIsRest = false
    else if (extra.badgeType === 'holiday') effIsRest = true
    else if (weekday === 0 || weekday === 6) effIsRest = true
    else effIsRest = false

    const dayLeaves = rangeLeavesByDate[dateStr] || []
    const dayLeaveTypes = [...new Set(dayLeaves.map((l) => l.leave_type))]
    if (effIsRest) {
      if (hasCheckin) { totalOvertime++; byMonth[monthKey].overtimeDays++ }
    } else {
      // 工作日、无签到、且无真实请假记录 → 缺口（漏签到）
      if (!hasCheckin && !isFuture && !dayLeaveTypes.length) { totalAbsence++; byMonth[monthKey].absenceDays++ }
    }
    // 真实请假按类型统计（仅工作日计入，休息日请假不占用出勤缺口）
    if (!effIsRest && dayLeaveTypes.length) {
      for (const lt of dayLeaveTypes) {
        totalType[lt] = (totalType[lt] || 0) + 1
        byMonth[monthKey][lt + 'Days'] = (byMonth[monthKey][lt + 'Days'] || 0) + 1
      }
    }

    // 应出勤：所有非休息日（排除周末/法定假/手动假日，且入职后）计入应上班天数
    if (!effIsRest) {
      totalRequired++
      byMonth[monthKey].requiredWorkDays++
    }

    // 逐日明细
    let dayType
    if (hasCheckin) dayType = effIsRest ? '加班' : '上班'
    else if (effIsRest) dayType = '休息'
    else if (isFuture) dayType = '预估上班'
    else if (dayLeaveTypes.length) dayType = leaveTypeLabel(dayLeaveTypes[0]) + (dayLeaveTypes.length > 1 ? '等' : '')
    else dayType = '缺勤'
    // 当天工作记录与人天说明（多签到记录用换行拼接）
    const dayContents = dayCheckins.map(c => (c.content && c.content.trim()) ? c.content.trim() : '已签到')
    const dayReasons = dayCheckins.map(c => (c.man_day_reason && c.man_day_reason.trim()) ? c.man_day_reason.trim() : '').filter(Boolean)
    const dayLeaveReasons = dayLeaves.map(lv => (lv.reason && lv.reason.trim()) ? lv.reason.trim() : '').filter(Boolean)
    const parts = [...dayContents]
    if (dayLeaveReasons.length) parts.push(...dayLeaveReasons.map(r => `请假: ${r}`))
    const dayContent = parts.length ? parts.join('\n') : (dayLeaves.length ? '' : '已签到')
    const dayManDayReason = dayReasons.join('\n')
    days.push({
      date: dateStr,
      weekday: ['日', '一', '二', '三', '四', '五', '六'][weekday],
      type: dayType,
      projectNames: dayProjectNames,
      manDays: dayManDays,
      manDayReason: dayManDayReason,
      content: dayContent,
      estimated: dayType === '预估上班',
    })
  }

  calcResult.value = {
    total: {
      workDays: totalWork,
      absenceDays: totalAbsence,
      annualDays: totalType.annual,
      compensatoryDays: totalType.compensatory,
      personalDays: totalType.personal,
      overtimeDays: totalOvertime,
      estimatedDays: totalEstimated,
      manDays: totalManDays,
      requiredWorkDays: totalRequired,
    },
    monthly: Object.entries(byMonth).map(([month, data]) => ({ month, ...data })),
    byProject: Object.values(byProject)
      .map((p) => ({ ...p, days: Math.round(p.days * 100) / 100, manDays: Math.round(p.manDays * 100) / 100 }))
      .sort((a, b) => b.days - a.days),
    multiProjectDays,
    days,
  }
}

// 将出勤计算结果发送到后端，由 openpyxl 生成含原生图表的 Excel 并下载
const exportDetailXLSX = async () => {
  if (!calcResult.value) { ElMessage.warning('请先计算'); return }
  try {
    const res = await exportAttendanceExcel({
      start: calcStart.value,
      end: calcEnd.value,
      result: calcResult.value,
    })
    const blob = new Blob([res.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    const rangeStr = (calcStart.value && calcEnd.value) ? `${calcStart.value}_${calcEnd.value}` : dayjs().format('YYYY-MM-DD')
    a.download = `出勤明细_${rangeStr}.xlsx`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success('Excel 已导出')
  } catch (e) {
    console.error(e)
    ElMessage.error('导出失败：' + (e && e.message ? e.message : e))
  }
}

// 当日更新状态指示 — 基于当前签到日期
const todayUpdateStatus = ref({ project_ids: [], task_ids: [] })
const loadStatusForDate = async (date) => {
  try { todayUpdateStatus.value = await getTodayCheckinStatus(date || undefined) } catch {}
}
const hasProjectUpdateToday = (pid) => todayUpdateStatus.value.project_ids?.includes(pid)
const hasTaskUpdateToday = (tid) => todayUpdateStatus.value.task_ids?.includes(tid)

// ---- v-model 代理 ----
const projectSelectModel = computed({
  get: () => checkinForm.value.multi_project ? checkinForm.value.project_ids : (checkinForm.value.project_ids[0] || null),
  set: (val) => { checkinForm.value.project_ids = Array.isArray(val) ? val : (val != null ? [val] : []) },
})
const batchProjectModel = computed({
  get: () => batchForm.value.multi_project ? batchForm.value.project_ids : (batchForm.value.project_ids[0] || null),
  set: (val) => { batchForm.value.project_ids = Array.isArray(val) ? val : (val != null ? [val] : []) },
})

const checkinsByDate = computed(() => {
  const map = {}
  for (const c of allCheckins.value) {
    const d = dayjs(c.date).format('YYYY-MM-DD')
    if (!map[d]) map[d] = []
    map[d].push(c)
  }
  return map
})

// 每天人天合计（该日所有签到记录 man_days 之和）
const mandayByDate = computed(() => {
  const map = {}
  for (const c of allCheckins.value) {
    const d = dayjs(c.date).format('YYYY-MM-DD')
    map[d] = (map[d] || 0) + (c.man_days || 1)
  }
  return map
})

// 每天对应的请假记录（多日请假会展开到覆盖的每个日期）
// 每条请假 = 一天 = 一条独立记录（与签到同构），无需按范围展开
const leavesByDate = computed(() => {
  const map = {}
  for (const lv of allLeaves.value) {
    const ds = lv.date
    if (!map[ds]) map[ds] = []
    map[ds].push(lv)
  }
  return map
})

// 农历/节日信息缓存：整个月的数据预先计算一次，calendarDays 和 monthStats 共享
const monthExtraInfo = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value
  const year = calYear.value
  const month = calMonth.value
  const daysInMonth = dayjs(`${year}-${month}-01`).daysInMonth()
  const cache = {}
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = dayjs(`${year}-${month}-${d}`).format('YYYY-MM-DD')
    cache[d] = getDayExtraInfo(dateStr)
  }
  return cache
})

const calendarDays = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value // 依赖版本号，数据加载后重新计算
  dataReady.value      // 签到数据未就绪时状态徽标保持中性
  const entryDateStr = getEntryDate() // 入职日期
  const firstDay = dayjs(`${calYear.value}-${calMonth.value}-01`)
  const daysInMonth = firstDay.daysInMonth()
  const startWeekday = (firstDay.day() + 6) % 7 // 周一为第一列
  const cells = []
  // 月初空白占位
  for (let i = 0; i < startWeekday; i++) {
    cells.push({ empty: true, isCurrent: false, isToday: false })
  }
  // 当月日期
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = firstDay.date(d).format('YYYY-MM-DD')
    const beforeEntry = entryDateStr && dateStr < entryDateStr
    const weekday = dayjs(dateStr).day()
    const extra = monthExtraInfo.value[d] // 从缓存获取
    const hasCheckin = !!checkinsByDate.value[dateStr]
    const isFuture = dayjs(dateStr).isAfter(dayjs().startOf('day'))
    const dayLeaves = leavesByDate.value[dateStr] || []
    const leaveTypes = [...new Set(dayLeaves.map((l) => l.leave_type))]

    // 判断当日有效类型（覆盖优先于默认）
    let effectiveIsRest
    if (extra.override === 'off') effectiveIsRest = true
    else if (extra.override === 'normal') effectiveIsRest = false
    else if (extra.badgeType === 'workday') effectiveIsRest = false
    else if (extra.badgeType === 'holiday') effectiveIsRest = true
    else if (weekday === 0 || weekday === 6) effectiveIsRest = true
    else effectiveIsRest = false

    let statusType = null
    if (dataReady.value && !isFuture && !beforeEntry) {
      if (dayLeaves.length) {
        statusType = null // 真实请假由 leaveTypes 徽标呈现，不显示"缺口"
      } else if (effectiveIsRest) {
        if (hasCheckin) statusType = 'overtime'
      } else {
        statusType = hasCheckin ? 'attendance' : 'leave'
      }
    }

    cells.push({
      num: d,
      date: dateStr,
      isCurrent: true,
      isToday: dateStr === todayStr,
      holiday: extra,
      status: statusType,
      leaveTypes,
      beforeEntry,
      isFuture,
    })
  }
  // 月末空白占位
  const remaining = 42 - cells.length
  for (let i = 0; i < remaining; i++) {
    cells.push({ empty: true, isCurrent: false, isToday: false })
  }
  return cells
})

// 月份出勤统计
const monthStats = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value // 依赖版本号，自定义覆盖更新后重新计算
  dataReady.value      // 签到数据未就绪时返回中性占位，避免首屏闪现"全缺勤"
  if (!dataReady.value) {
    const daysInMonth = dayjs(`${calYear.value}-${calMonth.value}-01`).daysInMonth()
    return { workDays: 0, absenceDays: 0, overtimeDays: 0, requiredWorkDays: 0, manDays: 0, annualDays: 0, compensatoryDays: 0, personalDays: 0, total: daysInMonth, isCurrent: false, loading: true }
  }
  const year = calYear.value
  const month = calMonth.value
  const daysInMonth = dayjs(`${year}-${month}-01`).daysInMonth()
  const today = dayjs()
  const isCurrent = year === today.year() && month === today.month() + 1
  const monthStart = dayjs(`${year}-${month}-01`)
  const isFutureMonth = monthStart.isAfter(today, 'day') // 月份第一天在今天之后 → 整月未到来
  const lastDay = isCurrent ? today.date() : daysInMonth

  let workDays = 0        // 有签到记录的总天数（含加班）
  let absenceDays = 0      // 工作日无签到且无真实请假（漏签到缺口）
  let overtimeDays = 0
  let requiredWorkDays = 0 // 应上班天数（排除周末/节假日/手动假日）
  let manDays = 0          // 人天合计（该月所有签到记录 man_days 之和）
  const typeDays = { annual: 0, compensatory: 0, personal: 0 } // 真实请假按类型覆盖天数

  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = dayjs(`${year}-${month}-${d}`).format('YYYY-MM-DD')
    const weekday = dayjs(dateStr).day()
    const extra = monthExtraInfo.value[d] // 从缓存获取
    const hasCheckin = !!checkinsByDate.value[dateStr]
    const entryDateStr = getEntryDate()
    const beforeEntry = entryDateStr && dateStr < entryDateStr

    if (beforeEntry) continue // 入职前不统计

    // 判断当日有效类型（覆盖优先于默认）
    let effectiveIsRest
    if (extra.override === 'off') effectiveIsRest = true
    else if (extra.override === 'normal') effectiveIsRest = false
    else if (extra.badgeType === 'workday') effectiveIsRest = false
    else if (extra.badgeType === 'holiday') effectiveIsRest = true
    else if (weekday === 0 || weekday === 6) effectiveIsRest = true
    else effectiveIsRest = false

    if (!effectiveIsRest) requiredWorkDays++

    if (d > lastDay) continue // 今天之后的日期不统计签到/请假/加班

    if (hasCheckin) {
      workDays++
      const dm = (checkinsByDate.value[dateStr] || []).reduce((s, c) => s + (c.man_days == null ? 1 : c.man_days), 0)
      manDays += dm
    }

    const dayLeaves = leavesByDate.value[dateStr] || []
    const dayLeaveTypes = [...new Set(dayLeaves.map((l) => l.leave_type))]
    if (effectiveIsRest) {
      if (hasCheckin) overtimeDays++
    } else {
      // 真实请假按类型统计（仅工作日）；工作日无签到且无真实请假 → 缺口
      if (dayLeaveTypes.length) {
        for (const lt of dayLeaveTypes) typeDays[lt] = (typeDays[lt] || 0) + 1
      } else if (!hasCheckin) {
        absenceDays++
      }
    }
  }

  // 整月未到来时清零签到相关统计，仅保留应出勤
  if (isFutureMonth) {
    workDays = 0
    absenceDays = 0
    overtimeDays = 0
    manDays = 0
  }

  // 缺勤 = 当月日历上"缺少打卡"的天数（工作日、未请假、无签到、且非未来/入职前），
  // 与日历格子 status==='leave' 完全一致；不再使用 应出勤-出勤-请假 的 gap 公式
  return { workDays, overtimeDays, requiredWorkDays, manDays, annualDays: typeDays.annual, compensatoryDays: typeDays.compensatory, personalDays: typeDays.personal, absenceDays, total: lastDay, isCurrent }
})

const load = async () => {
  // 按当前年月过滤签到数据，避免全量加载
  const [p, c, lv] = await Promise.all([
    getProjects(),
    getAllCheckins({ year: calYear.value, month: calMonth.value }),
    getLeaves({ year: calYear.value, month: calMonth.value }),
  ])
  projects.value = p
  allCheckins.value = c
  allLeaves.value = lv
  dataReady.value = true // 签到数据已就绪，状态徽标与出勤统计可正常显示
  selectedDate.value = todayStr
  loadStatusForDate(todayStr)
  // 节假日异步补，不阻塞首屏
  loadHolidayForYear(calYear.value).then(() => { holidayVersion.value++ })
}
onMounted(async () => {
  // 并行：从 settings.json/DB 加载节假日覆盖 + 主数据
  // 注：loadUserSettingsFromServer 已包含全量覆盖加载，无需再调用 loadAllOverridesFromDb（重复 DB 请求）
  await Promise.all([
    loadUserSettingsFromServer(),
    load(),
  ])
  holidayVersion.value++
})

const formatDateFull = (d) => dayjs(d).format('YYYY年M月D日 dddd')

const prevMonth = async () => {
  const newMonth = calMonth.value === 1 ? 12 : calMonth.value - 1
  const newYear  = calMonth.value === 1 ? calYear.value - 1 : calYear.value
  const [newCheckins, newLeaves] = await Promise.all([
    getAllCheckins({ year: newYear, month: newMonth }),
    getLeaves({ year: newYear, month: newMonth }),
  ])
  calYear.value = newYear
  calMonth.value = newMonth
  allCheckins.value = newCheckins
  allLeaves.value = newLeaves
  // 节假日异步补，不阻塞换页
  loadHolidayForYear(newYear).then(() => { holidayVersion.value++ })
}
const nextMonth = async () => {
  const newMonth = calMonth.value === 12 ? 1 : calMonth.value + 1
  const newYear  = calMonth.value === 12 ? calYear.value + 1 : calYear.value
  const [newCheckins, newLeaves] = await Promise.all([
    getAllCheckins({ year: newYear, month: newMonth }),
    getLeaves({ year: newYear, month: newMonth }),
  ])
  calYear.value = newYear
  calMonth.value = newMonth
  allCheckins.value = newCheckins
  allLeaves.value = newLeaves
  loadHolidayForYear(newYear).then(() => { holidayVersion.value++ })
}
const goToday = async () => {
  const targetYear  = dayjs().year()
  const targetMonth = dayjs().month() + 1
  const [newCheckins, newLeaves] = await Promise.all([
    getAllCheckins({ year: targetYear, month: targetMonth }),
    getLeaves({ year: targetYear, month: targetMonth }),
  ])
  calYear.value = targetYear
  calMonth.value = targetMonth
  selectedDate.value = todayStr
  allCheckins.value = newCheckins
  allLeaves.value = newLeaves
  loadHolidayForYear(targetYear).then(() => { holidayVersion.value++ })
}

// 点击日历标题跳转指定年月
const showMonthPicker = ref(false)
const mpYear = ref(calYear.value)
const onPickerVisible = (v) => {
  if (v) mpYear.value = calYear.value
  showMonthPicker.value = v
}
const changeMpYear = (delta) => { mpYear.value += delta }
const jumpToMonth = async (year, month) => {
  const [newCheckins, newLeaves] = await Promise.all([
    getAllCheckins({ year, month }),
    getLeaves({ year, month }),
  ])
  calYear.value = year
  calMonth.value = month
  allCheckins.value = newCheckins
  allLeaves.value = newLeaves
  loadHolidayForYear(year).then(() => { holidayVersion.value++ })
}
const pickMonth = async (m) => {
  await jumpToMonth(mpYear.value, m)
  showMonthPicker.value = false
}

// 日历设置
const showHolidaySettings = ref(false)
const hsActiveTab = ref('general')
const hsYear = ref(dayjs().year())
const hsMonth = ref(dayjs().month() + 1)
const entryDateVal = ref(getEntryDate())

const initHolidaySettings = () => { hsYear.value = calYear.value; hsMonth.value = calMonth.value; entryDateVal.value = getEntryDate(); hsActiveTab.value = 'general' }
const onEntryDateChange = (val) => { setEntryDate(val || null); holidayVersion.value++ }
const clearEntryDate = () => { entryDateVal.value = null; setEntryDate(null); holidayVersion.value++ }

// 供日历和计算器使用的计算属性
const hsPrev = () => { if (hsMonth.value === 1) { hsYear.value--; hsMonth.value = 12 } else hsMonth.value-- }
const hsNext = () => { if (hsMonth.value === 12) { hsYear.value++; hsMonth.value = 1 } else hsMonth.value++ }

const hsDays = computed(() => {
  // eslint-disable-next-line no-unused-expressions
  holidayVersion.value // 依赖版本号，覆盖数据更新后重新计算
  const firstDay = dayjs(`${hsYear.value}-${hsMonth.value}-01`)
  const daysInMonth = firstDay.daysInMonth()
  const startWeekday = (firstDay.day() + 6) % 7
  const cells = []
  // 提前解析整年节假日数据，避免每单元格重复 JSON.parse
  const yearKey = `taskm_holiday_${hsYear.value}`
  const yearData = (() => {
    try {
      const stored = localStorage.getItem(yearKey)
      return stored ? JSON.parse(stored)?.data : null
    } catch { return null }
  })()
  for (let i = 0; i < startWeekday; i++) cells.push({ empty: true })
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = firstDay.date(d).format('YYYY-MM-DD')
    const mmdd = dateStr.slice(5)
    const defaultInfo = yearData?.[mmdd] || null
    const override = getHolidayOverride(dateStr)
    // 计算生效状态
    let effective
    if (override) {
      effective = override
    } else if (defaultInfo) {
      effective = defaultInfo.holiday ? 'holiday' : 'workday'
    } else {
      effective = (dayjs(dateStr).day() === 0 || dayjs(dateStr).day() === 6) ? 'off' : 'normal'
    }
    cells.push({
      day: d,
      dateStr,
      default: defaultInfo,
      override,
      effective,
      overridden: !!override,
    })
  }
  const remaining = 42 - cells.length
  for (let i = 0; i < remaining; i++) cells.push({ empty: true })
  return cells
})

const cycleHoliday = (cell) => {
  if (cell.empty) return
  const order = ['normal', 'holiday', 'workday', 'off']
  const idx = order.indexOf(cell.effective)
  const next = order[(idx + 1) % order.length]
  // 如果下个状态和默认状态相同，清除覆盖
  const isDefault = (() => {
    if (!cell.default) return false
    if (next === 'holiday') return cell.default.holiday
    if (next === 'workday') return !cell.default.holiday
    return false
  })()
  if (isDefault) {
    setHolidayOverride(cell.dateStr, null)
  } else {
    setHolidayOverride(cell.dateStr, next)
  }
  holidayVersion.value++ // 触发日历重算
}

const hsTypeLabel = (type) => {
  const map = { normal: '工作日', holiday: '法定假', workday: '调休班', off: '休息日' }
  return map[type] || ''
}

const hsResetMonth = () => {
  const prefix = `${hsYear.value}-${String(hsMonth.value).padStart(2, '0')}`
  const all = getAllOverrides()
  for (const key of Object.keys(all)) {
    if (key.startsWith(prefix)) setHolidayOverride(key, null)
  }
  holidayVersion.value++
}

// ---- 单次签到 ----
const resetCheckinForm = () => {
  editingCheckinId.value = null
  const lastPid = localStorage.getItem('taskm_last_project')
  checkinForm.value = { project_ids: lastPid ? [Number(lastPid)] : [], task_ids: [], multi_project: false, date: null, content: '', man_days: 1, man_day_reason: '' }
  projectManDays.value = {}
  projectDays.value = {}
  tasksForSelected.value = []
  if (lastPid) loadTasksForProjects([Number(lastPid)])
}
// 入职日期前或尚未到达（未来）的日期不可签到
const isCheckinDisabled = (dateStr) => {
  const entryDateStr = getEntryDate()
  if (entryDateStr && dateStr < entryDateStr) return true
  if (dayjs(dateStr).isAfter(dayjs().startOf('day'))) return true
  if (leavesByDate.value[dateStr]?.length) return true // 当天已请假，不可签到
  return false
}
const isLeaveDisabled = (dateStr) => {
  if (!dateStr) return true
  const entryDateStr = getEntryDate()
  if (entryDateStr && dateStr < entryDateStr) return true
  if (dayjs(dateStr).isAfter(dayjs().startOf('day'))) return true
  if (checkinsByDate.value[dateStr]?.length) return true // 当天已签到，不可请假
  return false
}
const openCheckinDialog = () => {
  const date = selectedDate.value || todayStr
  if (isCheckinDisabled(date)) return
  resetCheckinForm()
  checkinForm.value.date = date
  loadStatusForDate(date)  // 加载该日期的更新状态
  // 如果该日已有签到记录，预填数据视为编辑
  const existing = checkinsByDate.value[date]?.[0]
  if (existing) {
    editingCheckinId.value = existing.id
    checkinForm.value.project_ids = existing.projects.map((p) => p.id)
    checkinForm.value.task_ids = existing.tasks.map((t) => t.id)
    checkinForm.value.multi_project = existing.multi_project
    checkinForm.value.content = existing.content
    checkinForm.value.man_days = existing.man_days ?? 1
    checkinForm.value.man_day_reason = existing.man_day_reason || ''
    // 多项目：回填各项目分配的人天与天数（天数缺省按人天占比兜底，与统计口径一致）
    projectManDays.value = {}
    projectDays.value = {}
    if (existing.multi_project) {
      const srcMd = existing.project_man_days || {}
      const srcDay = existing.project_days || {}
      for (const p of existing.projects) {
        projectManDays.value[p.id] = srcMd[p.id] != null ? srcMd[p.id] : 0.5
        const md = Number(srcMd[p.id] || 0)
        const totalMD = Number(existing.man_days || 0)
        projectDays.value[p.id] = srcDay[p.id] != null
          ? srcDay[p.id]
          : (totalMD > 0 ? md / totalMD : 1 / existing.projects.length)
      }
    }
    loadTasksForProjects(checkinForm.value.project_ids)
  }
  showCheckinDlg.value = true
}
const onMultiChange = () => { checkinForm.value.project_ids = []; checkinForm.value.task_ids = []; tasksForSelected.value = []; projectManDays.value = {}; projectDays.value = {} }
const onProjectChange = () => {
  const ids = checkinForm.value.project_ids
  checkinForm.value.task_ids = []
  syncProjectAlloc(ids, projectManDays.value, projectDays.value)
  if (ids.length) { localStorage.setItem('taskm_last_project', ids[0]); loadTasksForProjects(ids) }
  else tasksForSelected.value = []
}
const loadTasksForProjects = async (pids) => {
  const results = await Promise.all(pids.map(async (pid) => {
    try {
      const proj = projects.value.find((p) => p.id === pid)
      if (!proj) return []
      const ts = await getTasks(proj.display_id || pid)
      return ts.map((t) => ({ ...t, _projectLabel: proj.name }))
    } catch { return [] }
  }))
  tasksForSelected.value = results.flat()
}
const buildCheckinPayload = (form, mdStore, dayStore) => {
  const payload = {
    project_ids: form.project_ids,
    task_ids: form.task_ids,
    multi_project: form.multi_project,
    date: form.date,
    content: form.content,
    man_days: form.man_days,
    man_day_reason: form.man_day_reason,
    project_man_days: {},
    project_days: {},
  }
  if (form.multi_project) {
    for (const pid of form.project_ids) {
      payload.project_man_days[pid] = Number(mdStore[pid] || 0)
      payload.project_days[pid] = Number(dayStore[pid] || 0)
    }
    payload.man_days = form.project_ids.reduce((s, pid) => s + (Number(mdStore[pid]) || 0), 0)
  } else {
    const pid = form.project_ids[0]
    if (pid != null) {
      payload.project_man_days[pid] = Number(form.man_days || 0)
      payload.project_days[pid] = 1
    }
  }
  return payload
}

const submitCheckin = async () => {
  if (!checkinForm.value.project_ids.length) { ElMessage.warning('请选择项目'); return }
  checkinLoading.value = true
  try {
    const payload = buildCheckinPayload(checkinForm.value, projectManDays.value, projectDays.value)
    if (editingCheckinId.value) {
      await updateCheckin(editingCheckinId.value, payload)
      ElMessage.success('签到已更新')
    } else {
      await createCheckin(payload)
      ElMessage.success('签到成功')
    }
    showCheckinDlg.value = false
    allCheckins.value = await getAllCheckins({ year: calYear.value, month: calMonth.value })
    loadStatusForDate(selectedDate.value)
  } finally { checkinLoading.value = false }
}
const removeCheckin = async (chk) => {
  await deleteCheckin(chk.projects?.[0]?.display_id || chk.projects?.[0]?.id || 0, chk.id)
  allCheckins.value = await getAllCheckins({ year: calYear.value, month: calMonth.value })
  loadStatusForDate(selectedDate.value)
}

// ---- 请假（年假/调休/请假） ----
const refreshLeaves = async () => {
  allLeaves.value = await getLeaves({ year: calYear.value, month: calMonth.value })
}
// 选好范围后自动计算「应上班的工作日」天数（后端按周末/法定假/覆盖判定）
const leaveWorkdays = ref(0)
const leaveWorkdaysLoading = ref(false)
const computeLeaveWorkdays = async () => {
  const start = leaveForm.value.date
  const end = leaveForm.value.date_end || leaveForm.value.date
  if (!start) { leaveWorkdays.value = 0; return }
  leaveWorkdaysLoading.value = true
  try {
    const res = await getLeaveWorkdays({ start_date: start, end_date: end })
    leaveWorkdays.value = res.count || 0
  } catch {
    leaveWorkdays.value = 0
  } finally {
    leaveWorkdaysLoading.value = false
  }
}
// 结束日期选择器：不可早于开始日期
const disabledEndDate = (time) => {
  if (!leaveForm.value.date) return false
  return dayjs(time).isBefore(dayjs(leaveForm.value.date), 'day')
}
const resetLeaveForm = () => {
  leaveForm.value = { leave_type: 'personal', subtype: '', date: null, date_end: null, days: 1, reason: '' }
  leaveWorkdays.value = 0
}
const openLeaveDialog = (lv = null) => {
  if (lv) {
    editingLeaveId.value = lv.id
    leaveForm.value = {
      leave_type: lv.leave_type,
      subtype: lv.subtype || '',
      date: lv.date,
      date_end: lv.date_end || null,
      days: lv.days,
      reason: lv.reason || '',
    }
  } else {
    editingLeaveId.value = null
    resetLeaveForm()
    const date = selectedDate.value || todayStr
    if (checkinsByDate.value[date]?.length) {
      ElMessage.warning('当天已有签到记录，不可再请假')
      return
    }
    leaveForm.value.date = date
    computeLeaveWorkdays() // 新增模式：按已选开始日预计算工作日
  }
  showLeaveDlg.value = true
}
const submitLeave = async () => {
  if (!leaveForm.value.leave_type) { ElMessage.warning('请选择类型'); return }
  if (!leaveForm.value.date) { ElMessage.warning('请选择开始日期'); return }
  if (!leaveForm.value.date_end) leaveForm.value.date_end = leaveForm.value.date
  // 多日请假按「应上班的工作日」逐日落库，由后端拆分；此处只传范围与类型
  if (!editingLeaveId.value && leaveWorkdays.value <= 0) {
    ElMessage.warning('所选范围内没有需要上班的工作日（周末/法定假不计入），无法生成请假记录')
    return
  }
  leaveLoading.value = true
  try {
    if (editingLeaveId.value) {
      const payload = {
        leave_type: leaveForm.value.leave_type,
        subtype: leaveForm.value.subtype || null,
        date: leaveForm.value.date,
        reason: leaveForm.value.reason || '',
      }
      await updateLeave(editingLeaveId.value, payload)
      ElMessage.success('请假已更新')
    } else {
      const payload = {
        leave_type: leaveForm.value.leave_type,
        subtype: leaveForm.value.subtype || null,
        date: leaveForm.value.date,
        date_end: leaveForm.value.date_end,
        reason: leaveForm.value.reason || '',
      }
      const res = await createLeave(payload)
      const n = (res && res.count) || 0
      const msg = `已记录 ${n} 天请假（按工作日逐日生成）`
      if (res && res.conflicts?.length) {
        ElMessage.warning(`${msg}，以下日期因已有签到/请假记录已跳过：${res.conflicts.join('、')}`)
      } else {
        ElMessage.success(msg)
      }
    }
    showLeaveDlg.value = false
    await refreshLeaves()
  } finally { leaveLoading.value = false }
}
const removeLeave = async (lv) => {
  try {
    await ElMessageBox.confirm('确定删除该请假记录？', '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
  } catch { return }
  await deleteLeave(lv.id)
  ElMessage.success('已删除')
  await refreshLeaves()
}

// ---- 批量删除签到（日历选日期） ----
const toggleDeleteBatchMode = () => {
  deleteBatchMode.value = !deleteBatchMode.value
  if (!deleteBatchMode.value) deleteDates.value = []
  else if (batchMode.value) { batchMode.value = false; batchDates.value = [] }
}
const confirmBatchDelete = async () => {
  if (!deleteDates.value.length) return
  // 收集所有选中日期的签到和请假 ID
  const checkinIds = []
  const leaveIds = []
  for (const d of deleteDates.value) {
    const crecs = checkinsByDate.value[d] || []
    for (const r of crecs) checkinIds.push(r.id)
    const lrecs = leavesByDate.value[d] || []
    for (const r of lrecs) leaveIds.push(r.id)
  }
  const total = checkinIds.length + leaveIds.length
  if (!total) { ElMessage.warning('未找到可删除的记录'); return }
  const detail = []
  if (checkinIds.length) detail.push(`${checkinIds.length} 条签到`)
  if (leaveIds.length) detail.push(`${leaveIds.length} 条请假`)
  try {
    await ElMessageBox.confirm(
      `确定删除 ${deleteDates.value.length} 天的共 ${total} 条记录（${detail.join('，')}）？此操作不可恢复。`,
      '确认批量删除',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  const calls = []
  if (checkinIds.length) calls.push(batchDeleteCheckins(checkinIds))
  if (leaveIds.length) calls.push(batchDeleteLeaves(leaveIds))
  await Promise.all(calls)
  ElMessage.success(`已删除 ${total} 条记录（${deleteDates.value.length} 天）`)
  deleteDates.value = []
  const [newCheckins, newLeaves] = await Promise.all([
    getAllCheckins({ year: calYear.value, month: calMonth.value }),
    getLeaves({ year: calYear.value, month: calMonth.value }),
  ])
  allCheckins.value = newCheckins
  allLeaves.value = newLeaves
  loadStatusForDate(selectedDate.value)
}

// ---- 批量签到 ----
const toggleBatchMode = () => {
  batchMode.value = !batchMode.value
  if (!batchMode.value) batchDates.value = []
}
const onCellClick = (day) => {
  if (day.empty) return
  if (batchMode.value) {
    // 批量签到模式：不可签到日期（入职前/未来）与已有签到的日期均不可选
    if (day.beforeEntry || day.isFuture || !day.isCurrent || checkinsByDate[day.date]) return
    const idx = batchDates.value.indexOf(day.date)
    if (idx >= 0) batchDates.value.splice(idx, 1)
    else batchDates.value.push(day.date)
    batchDates.value.sort()
  } else if (deleteBatchMode.value) {
    // 批量删除模式：已有签到或请假的日期可选
    const hasAnyRecord = checkinsByDate.value[day.date] || (day.leaveTypes && day.leaveTypes.length)
    if (!day.isCurrent || !hasAnyRecord) return
    const idx = deleteDates.value.indexOf(day.date)
    if (idx >= 0) deleteDates.value.splice(idx, 1)
    else deleteDates.value.push(day.date)
    deleteDates.value.sort()
  } else {
    selectedDate.value = day.date
  }
}
const openBatchDialog = () => {
  if (!batchDates.value.length) return
  const lastPid = localStorage.getItem('taskm_last_project')
  batchForm.value = { project_ids: lastPid ? [Number(lastPid)] : [], task_ids: [], multi_project: false, content: '' }
  batchTasks.value = []
  if (lastPid) loadBatchTasks([Number(lastPid)])
  showBatchDlg.value = true
}
const onBatchMultiChange = () => { batchForm.value.project_ids = []; batchForm.value.task_ids = []; batchTasks.value = []; batchProjectManDays.value = {}; batchProjectDays.value = {} }
const onBatchProjectChange = () => {
  const ids = batchForm.value.project_ids
  batchForm.value.task_ids = []
  syncProjectAlloc(ids, batchProjectManDays.value, batchProjectDays.value)
  if (ids.length) { localStorage.setItem('taskm_last_project', ids[0]); loadBatchTasks(ids) }
  else batchTasks.value = []
}
const loadBatchTasks = async (pids) => {
  const results = await Promise.all(pids.map(async (pid) => {
    try {
      const proj = projects.value.find((p) => p.id === pid)
      if (!proj) return []
      const ts = await getTasks(proj.display_id || pid)
      return ts.map((t) => ({ ...t, _projectLabel: proj.name }))
    } catch { return [] }
  }))
  batchTasks.value = results.flat()
}
const resetBatchForm = () => { batchForm.value = { project_ids: [], task_ids: [], multi_project: false, content: '', man_days: 1, man_day_reason: '' }; batchProjectManDays.value = {}; batchProjectDays.value = {}; batchTasks.value = [] }
// 多项目人天/天数均分（以 1 为基准平摊到各项目，人天、天数同时均分）
const splitEvenly = (ids, mdStore, dayStore) => {
  const n = ids.length
  if (!n) return
  const each = Math.round((1.0 / n) * 100) / 100
  const rem = Math.round((1.0 - each * (n - 1)) * 100) / 100
  ids.forEach((pid, i) => { mdStore[pid] = i === n - 1 ? rem : each; dayStore[pid] = i === n - 1 ? rem : each })
}
const splitSingleEvenly = () => splitEvenly(checkinForm.value.project_ids, projectManDays.value, projectDays.value)
const splitBatchEvenly = () => splitEvenly(batchForm.value.project_ids, batchProjectManDays.value, batchProjectDays.value)
const submitBatch = async () => {
  if (!batchForm.value.project_ids.length) { ElMessage.warning('请选择项目'); return }
  batchLoading.value = true
  try {
    let count = 0
    for (const d of batchDates.value) {
      const payload = buildCheckinPayload({ ...batchForm.value, date: d }, batchProjectManDays.value, batchProjectDays.value)
      await createCheckin(payload)
      count++
    }
    ElMessage.success(`批量签到完成（${count} 天）`)
    showBatchDlg.value = false
    allCheckins.value = await getAllCheckins({ year: calYear.value, month: calMonth.value })
    loadStatusForDate(selectedDate.value)
    toggleBatchMode()
  } finally { batchLoading.value = false }
}
</script>

<style scoped>
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 24px; }
.page-title { font-size: 20px; font-weight: 600; }
.page-sub { font-size: 13px; color: #888; margin-top: 4px; }

.calendar-layout { display: grid; grid-template-columns: 420px minmax(0, 1fr); grid-template-areas: "cal detail" "stats tool"; gap: 16px 24px; align-items: stretch; }

.cal-panel { grid-area: cal; background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; padding: 18px; position: relative; }
.cal-panel.batch-mode { border-color: #e6a23c; }
.cal-panel.delete-batch-mode { border-color: #f56c6c; }
.cal-nav { display: flex; align-items: center; justify-content: center; margin-bottom: 16px; }
.cal-month-title { font-size: 16px; font-weight: 600; min-width: 120px; text-align: center; }
.cal-month-clickable { cursor: pointer; user-select: none; border-radius: 6px; padding: 2px 8px; transition: background 0.15s, color 0.15s; }
.cal-month-clickable:hover { color: #534ab7; background: #eeedfe; }
.month-picker { padding: 4px; }
.mp-year-row { display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 10px; }
.mp-year { font-size: 14px; font-weight: 600; min-width: 56px; text-align: center; }
.mp-month-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.mp-month { border: 1px solid #ebeef5; background: #fff; border-radius: 6px; padding: 8px 0; font-size: 13px; color: #606266; cursor: pointer; transition: all 0.15s; }
.mp-month:hover { border-color: #534ab7; color: #534ab7; }
.mp-month.active { background: #534ab7; border-color: #534ab7; color: #fff; font-weight: 600; }
.cal-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; margin-bottom: 8px; }
.cal-weekday { font-size: 12px; color: #888; padding: 4px 0; }
.cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 2px; }
.cal-grid-loading .cal-cell { background: #f6f6f6; border-radius: 8px; }
.cal-cell { position: relative; aspect-ratio: 1; display: flex; align-items: center; justify-content: center; border-radius: 8px; cursor: pointer; font-size: 13px; transition: background .1s; gap: 2px; }
.cal-cell:hover { background: #f5f4fe; }
.cal-cell-empty { visibility: hidden; pointer-events: none; }
.cal-cell-disabled { cursor: not-allowed; }
.cal-cell-disabled .cal-cell-num { color: #c8c8d0; }
.cal-cell-disabled .cal-cell-badge { opacity: 0.3; }
.cal-cell.batch-disabled { opacity: 0.3; cursor: default; }
.cal-cell.delete-disabled { opacity: 0.3; cursor: default; }
.cal-cell.today .cal-cell-num { color: #534ab7; font-weight: 700; }
.cal-cell.active { background: #eeedfe; }
.cal-cell.active .cal-cell-num { font-weight: 600; }
.cal-cell.batch-selected { background: #fdf6ec; border: 1px solid #e6a23c; }
.cal-cell.delete-selected { background: #fef0f0; border: 1px solid #f56c6c; }
.cal-cell.delete-selected .cal-cell-num { font-weight: 600; color: #f56c6c; }
.cal-cell-dot { width: 5px; height: 5px; border-radius: 50%; background: #534ab7; position: absolute; bottom: 6px; }
.cal-cell-label { position: absolute; bottom: 3px; font-size: 9px; font-weight: 600; line-height: 1; }
.cal-cell-overtime { color: #d48806; }
.cal-cell-leave { color: #e67e22; }
.cal-cell-label.cal-cell-leave-annual { color: #2196f3; }
.cal-cell-label.cal-cell-leave-compensatory { color: #2196f3; }
.cal-cell-label.cal-cell-leave-personal { color: #e53935; }
/* 漏签到缺口：中性灰，与真实请假彩色徽标区分 */
.cal-cell-label.cal-cell-absence { color: #b0b0b0; font-weight: 500; }
.cal-leave-annual { color: #2196f3; }
.cal-leave-comp { color: #2196f3; }
.cal-leave-personal { color: #e53935; }

.cal-leaves { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
.cal-leave-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 10px 14px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.cal-leave-type { font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 500; }
.clt-annual { background: #e3f2fd; color: #2196f3; }
.clt-compensatory { background: #e3f2fd; color: #2196f3; }
.clt-personal { background: #ffebee; color: #e53935; }
.cal-leave-sub { font-size: 12px; color: #666; }
.cal-leave-days { font-size: 12px; color: #333; font-weight: 500; }
.cal-leave-reason { font-size: 12px; color: #999; flex: 1 1 100%; }
.cal-leave-actions { margin-left: auto; display: flex; gap: 4px; }
.cal-cell-badge { position: absolute; top: 1px; right: 2px; font-size: 9px; font-weight: 600; line-height: 1.2; border-radius: 3px; padding: 0 3px; max-width: 52px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cal-cell-badge.cb-holiday { color: #e74c3c; background: #fde8e8; }
.cal-cell-badge.cb-workday { color: #d48806; background: #fff7e6; }
.cal-cell-badge.cb-festival { color: #8b5cf6; background: #f3eefe; }
.cal-cell-badge.cb-off { color: #999; background: #f0f0f0; }
.cal-cell-manday { position: absolute; top: 1px; left: 2px; font-size: 9px; font-weight: 700; line-height: 1.1; color: #0f6e56; background: #e1f5ee; border-radius: 3px; padding: 0 3px; }
.cal-cell-checked { font-size: 10px; color: #999; position: absolute; bottom: 4px; }
.cal-cell-has-data { font-size: 10px; color: #f56c6c; position: absolute; bottom: 4px; }
.cal-cell-num { line-height: 1; }

.cal-stats-card { grid-area: stats; background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; padding: 16px 18px; }
.cal-stats-title { font-size: 12px; color: #888; margin-bottom: 6px; }
.cal-stats-row { display: flex; align-items: center; gap: 12px; }
.cal-stats-item { font-size: 13px; color: #333; }
.cal-stats-item strong { font-size: 18px; color: #534ab7; }
.cal-stats-divider { width: 1px; height: 20px; background: #e0e0e0; }
.cal-stats-overtime { font-size: 12px; color: #d48806; margin-top: 4px; }
.cal-stats-overtime strong { font-size: 14px; color: #534ab7; }
.cal-manday-num { color: #534ab7; }

.batch-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px 0; margin-top: 10px; border-top: 1px solid #eee; font-size: 13px; color: #e6a23c; }

.delete-batch-bar { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px 0; margin-top: 10px; border-top: 1px solid #f56c6c; font-size: 13px; color: #f56c6c; }

.cal-detail { grid-area: detail; min-width: 0; }
.cal-detail-header { margin-bottom: 16px; }
.cal-detail-header h3 { font-size: 16px; font-weight: 600; margin: 0; }
.cal-checkins { display: flex; flex-direction: column; gap: 10px; }
.cal-checkin-card { background: #fff; border-radius: 8px; border: 1px solid #e8e8e4; padding: 14px 18px; }
.cal-cc-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.cal-cc-project { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #eeedfe; color: #534ab7; font-weight: 500; }
.cal-cc-time { font-size: 12px; color: #aaa; margin-left: auto; }
.cal-cc-tasks { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
.cal-cc-task { font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #e1f5ee; color: #0f6e56; font-weight: 500; }
.cal-cc-content { font-size: 14px; line-height: 1.5; color: #333; white-space: pre-wrap; }
.cal-cc-manday-badge { font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 4px; background: #e1f5ee; color: #0f6e56; }
.cal-cc-manday-reason { font-size: 12px; color: #888; }

.delete-date-item { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px; background: #fef0f0; border-radius: 6px; font-size: 13px; margin-bottom: 4px; }

.status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 8px; flex-shrink: 0; vertical-align: middle; }
.dot-green { background: #52c41a; }
.dot-gray { background: #d9d9d9; }

/* 工具卡片 */
.cal-tools-card { grid-area: tool; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; background: #fff; border-radius: 10px; border: 1px solid #e8e8e4; padding: 14px 18px; }
.cal-tools-title { font-size: 12px; color: #888; margin-bottom: 10px; }
.cal-tools-btn { padding: 6px 12px; font-size: 13px; border-radius: 6px; background: #f5f4fe; color: #534ab7; }
.cal-tools-btn:hover { background: #eeedfe; }

/* 出勤计算器 */
.calc-range { display: flex; align-items: center; margin-bottom: 20px; }
.calc-summary { display: flex; justify-content: space-around; padding: 16px 0; background: #f9f9fb; border-radius: 10px; margin-bottom: 20px; }
.calc-summary-item { text-align: center; }
.calc-summary-num { display: block; font-size: 28px; font-weight: 700; line-height: 1.2; }
.calc-summary-label { font-size: 13px; color: #888; margin-top: 2px; display: block; }
.calc-section { margin-top: 16px; }
.calc-section-title { font-size: 14px; font-weight: 600; margin-bottom: 10px; color: #333; }
.calc-month-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.calc-month-table th, .calc-month-table td { padding: 7px 6px; text-align: center; border-bottom: 1px solid #eee; }
.calc-month-table th { background: #f9f9fb; color: #888; font-weight: 600; }
.calc-month-th-name { text-align: center; }
.calc-month-table td.calc-month-td-name { text-align: center; color: #534ab7; font-weight: 600; }
.calc-month-table tr:last-child td { border-bottom: none; }
.calc-proj-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.calc-proj-card { display: flex; align-items: center; gap: 8px; background: #f0f0f5; border-radius: 8px; padding: 8px 14px; }
.calc-proj-name { font-size: 13px; color: #333; }
.calc-proj-days { font-size: 13px; color: #534ab7; }
.calc-proj-days strong { font-size: 16px; }
.calc-estimated-note { text-align: center; font-size: 12px; color: #999; margin-top: -12px; margin-bottom: 8px; }
.calc-estimated-note strong { color: #534ab7; }
.calc-estimated-tag { display: inline-block; font-size: 10px; font-weight: 400; color: #fff; background: #534ab7; border-radius: 3px; padding: 0 5px; margin-left: 4px; vertical-align: middle; }
.calc-section-title-warn { display: flex; align-items: center; color: #e67e22; }
.calc-warn-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.calc-warn-item { background: #fff7e6; border: 1px solid #ffe0a3; border-radius: 6px; padding: 8px 10px; font-size: 12px; min-width: 140px; }
.calc-warn-top { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.calc-warn-date { font-weight: 600; color: #d48806; }
.calc-warn-weekday { color: #999; font-size: 11px; }
.calc-warn-projs { display: flex; flex-wrap: wrap; gap: 4px; }
.calc-warn-proj { font-size: 11px; padding: 1px 6px; border-radius: 3px; background: #eeedfe; color: #534ab7; }

/* 日历设置 */
.hs-tabs { display: flex; gap: 0; margin-bottom: 16px; border-bottom: 1px solid #e8e8e4; }
.hs-tab { padding: 6px 20px; font-size: 13px; cursor: pointer; color: #888; border-bottom: 2px solid transparent; margin-bottom: -1px; transition: all .15s; }
.hs-tab:hover { color: #534ab7; }
.hs-tab.active { color: #534ab7; border-bottom-color: #534ab7; font-weight: 600; }
.hs-entry { display: flex; align-items: center; gap: 10px; padding: 10px 0; }
.hs-entry-label { font-size: 13px; color: #888; white-space: nowrap; }
.hs-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.hs-nav { display: flex; align-items: center; }
.hs-month { font-size: 15px; font-weight: 600; min-width: 120px; text-align: center; }
.hs-legend { display: flex; align-items: center; gap: 6px; }
.hs-tag { display: inline-block; font-size: 11px; padding: 1px 6px; border-radius: 3px; }
.hs-tag-normal { background: #e8f5e9; color: #2e7d32; }
.hs-tag-holiday { background: #fde8e8; color: #e74c3c; }
.hs-tag-workday { background: #fff7e6; color: #d48806; }
.hs-tag-off { background: #f0f0f0; color: #999; }
.hs-override-hint { font-size: 11px; color: #bbb; margin-left: 2px; }
.hs-weekdays { display: grid; grid-template-columns: repeat(7, 1fr); text-align: center; margin-bottom: 6px; }
.hs-weekday { font-size: 11px; color: #888; padding: 2px 0; }
.hs-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; }
.hs-cell { position: relative; aspect-ratio: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; border-radius: 6px; cursor: pointer; font-size: 13px; background: #fafafa; transition: background .1s; gap: 1px; }
.hs-cell:hover { background: #f0f0f5; }
.hs-cell-empty { visibility: hidden; }
.hs-num { line-height: 1; font-weight: 500; }
.hs-tag-sm { font-size: 9px; line-height: 1.2; border-radius: 2px; padding: 0 3px; }
.hs-ts-normal { color: #2e7d32; background: #e8f5e9; }
.hs-ts-holiday { color: #e74c3c; background: #fde8e8; }
.hs-ts-workday { color: #d48806; background: #fff7e6; }
.hs-ts-off { color: #999; background: #f0f0f0; }
.hs-override-dot { width: 4px; height: 4px; border-radius: 50%; background: #534ab7; position: absolute; top: 2px; right: 2px; }
.hs-auto-save { font-size: 12px; color: #bbb; }

/* 多项目按项目分配人天 */
.pmd-block { border: 1px solid #ebeef5; border-radius: 8px; padding: 10px 12px; width: 100%; background: #fafbff; }
.pmd-row { display: flex; align-items: center; gap: 10px; padding: 4px 0; }
.pmd-name { flex: 1; font-size: 13px; color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pmd-unit { font-size: 12px; color: #888; }
.pmd-foot { display: flex; align-items: center; justify-content: space-between; margin-top: 6px; padding-top: 6px; border-top: 1px dashed #ebeef5; font-size: 13px; color: #666; }
.pmd-sum-num { color: #0f6e56; font-size: 15px; }

</style>
