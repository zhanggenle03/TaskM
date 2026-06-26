<template>
  <div class="requirement-page">
    <div class="req-top-section">
      <!-- 面包屑 -->
      <el-breadcrumb separator="/" style="margin-bottom: 20px;">
        <el-breadcrumb-item :to="{ name: 'projects' }">项目列表</el-breadcrumb-item>
        <el-breadcrumb-item>{{ projectName }}</el-breadcrumb-item>
        <el-breadcrumb-item>需求列表</el-breadcrumb-item>
      </el-breadcrumb>
      <!-- 页面头部 -->
      <div class="page-header">
        <h2>需求管理</h2>
        <div class="header-actions">
          <el-button @click="$router.push(`/projects/${projectId}/requirements/settings`)" size="small">
            <el-icon><Setting /></el-icon> 设置
          </el-button>
          <el-dropdown size="small" trigger="click" :disabled="!selectedReqs.length">
            <el-button size="small" :disabled="!selectedReqs.length">
              批量操作<el-icon><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-item @click="batchDeleteReq">
                <el-icon><Delete /></el-icon> 批量删除 ({{ selectedReqs.length }})
              </el-dropdown-item>
            </template>
          </el-dropdown>
          <el-dropdown split-button type="primary" size="small" @click="openCreate" trigger="hover">
            新建
            <template #dropdown>
              <el-dropdown-item @click="openExcelImport('append')">
                <el-icon><Upload /></el-icon> 追加导入
              </el-dropdown-item>
              <el-dropdown-item @click="openExcelImport('update')">
                <el-icon><Edit /></el-icon> 更新导入
              </el-dropdown-item>
              <el-dropdown-item @click="openExcelImport('overwrite')">
                <el-icon><Refresh /></el-icon> 覆盖导入
              </el-dropdown-item>
            </template>
          </el-dropdown>
        </div>
      </div>

    </div>

    <!-- 筛选条件展示 -->
    <div v-if="activeFilters.length || fuzzyFilterChips.length" class="filter-chips-bar">
      <span
        v-for="f in activeFilters"
        :key="f.col + ':' + f.value"
        class="filter-chip"
        @click="removeFilterValue(f.col, f.value)"
      >
        <span class="filter-chip-label">{{ f.label }}</span>
        <span class="filter-chip-sep">:</span>
        <span class="filter-chip-value">{{ f.value }}</span>
        <el-icon class="filter-chip-close"><Close /></el-icon>
      </span>
      <span
        v-for="f in fuzzyFilterChips"
        :key="'fuzzy_' + f.col"
        class="filter-chip fuzzy-chip"
        @click="removeFuzzyFilter(f.col)"
      >
        <span class="filter-chip-label">{{ f.label }}</span>
        <span class="filter-chip-sep">:</span>
        <span class="filter-chip-value">{{ f.mode === 'exclude' ? '排除 ' : '' }}{{ f.text }}</span>
        <el-icon class="filter-chip-close"><Close /></el-icon>
      </span>
      <el-button text size="small" type="danger" @click="clearAllFilters" class="filter-clear-all">
        清除全部筛选
      </el-button>
    </div>

    <!-- 需求明细表（仅数据区滚动） -->
    <div v-loading="loading" element-loading-text="加载中…" class="req-table-wrap" style="flex:1;min-height:0;display:flex;flex-direction:column">
      <template v-if="requirements.length">
      <div class="req-table-inner" ref="tableInnerRef" style="flex:1;min-height:0">
      <el-table
        ref="tableRef"
        :key="tableKey"
        :data="requirements"
        :max-height="tableMaxHeight"
        stripe
        border
        style="width:100%"
        size="small"
        :cell-class-name="cellClassName"
        @cell-click="onCellClick"
        @cell-dblclick="onCellDblClick"
        @cell-contextmenu="onCellContextMenu"
        @header-dragend="onColumnResize"
        class="req-table"
      >
      <el-table-column width="42" align="center">
        <template #header>
          <el-checkbox
            :model-value="headerChecked"
            :indeterminate="headerIndeterminate"
            @change="onHeaderSelectChange"
            size="small"
          />
        </template>
        <template #default="{ row }">
          <el-checkbox
            :model-value="selectedReqs.some(r => r.id === row.id)"
            @change="(v) => toggleRowSelection(row, v)"
            size="small"
          />
        </template>
      </el-table-column>
      <el-table-column prop="display_id" label="显示ID" :width="mergedColWidth('display_id', columnWidths.display_id || 160)" align="center">
        <template #header>
          <span class="th-with-filter">
            <span class="sortable-header" @click.stop="toggleSort('display_id')" style="flex:1">
              显示ID
              <span class="sort-indicator">
                <el-icon v-if="getSortOrder('display_id') === 'asc'" class="sort-icon active"><SortUp /></el-icon>
                <el-icon v-else-if="getSortOrder('display_id') === 'desc'" class="sort-icon active"><SortDown /></el-icon>
                <el-icon v-else class="sort-icon"><SortUp /></el-icon>
                <span v-if="getSortOrder('display_id')" class="sort-rank">{{ getSortRank('display_id') }}</span>
              </span>
            </span>
            <el-icon
              class="filter-icon"
              :class="{ active: hasFilter('display_id') }"
              @click.stop="toggleFilterCol('display_id', $event)"
            ><Filter /></el-icon>
          </span>
        </template>
        <template #default="{ row }">
          <router-link :to="`/projects/${projectId}/requirements/${row.display_id}`" class="id-link" :title="row.display_id">{{ row.display_id || '—' }}</router-link>
        </template>
      </el-table-column>
      <el-table-column prop="title" :width="mergedColWidth('title', columnWidths.title || 240)">
        <template #header>
          <span class="th-with-filter">
            <span class="sortable-header" @click.stop="toggleSort('title')" style="flex:1">
              标题
              <span class="sort-indicator">
                <el-icon v-if="getSortOrder('title') === 'asc'" class="sort-icon active"><SortUp /></el-icon>
                <el-icon v-else-if="getSortOrder('title') === 'desc'" class="sort-icon active"><SortDown /></el-icon>
                <el-icon v-else class="sort-icon"><SortUp /></el-icon>
                <span v-if="getSortOrder('title')" class="sort-rank">{{ getSortRank('title') }}</span>
              </span>
            </span>
            <el-icon
              class="filter-icon"
              :class="{ active: hasFilter('title') }"
              @click.stop="toggleFilterCol('title', $event)"
            ><Filter /></el-icon>
          </span>
        </template>
        <template #default="{ row }">
          <span class="req-title-cell" :title="row.title">{{ row.title }}</span>
        </template>
      </el-table-column>
      <el-table-column v-if="isBuiltinActive('status')" prop="status" :width="mergedColWidth('status', columnWidths.status ?? 80)" align="center">
        <template #header>
          <span class="th-with-filter">
            <span class="sortable-header" @click.stop="toggleSort('status')" style="flex:1">
              状态
              <span class="sort-indicator">
                <el-icon v-if="getSortOrder('status') === 'asc'" class="sort-icon active"><SortUp /></el-icon>
                <el-icon v-else-if="getSortOrder('status') === 'desc'" class="sort-icon active"><SortDown /></el-icon>
                <el-icon v-else class="sort-icon"><SortUp /></el-icon>
                <span v-if="getSortOrder('status')" class="sort-rank">{{ getSortRank('status') }}</span>
              </span>
            </span>
            <el-icon
              class="filter-icon"
              :class="{ active: hasFilter('status') }"
              @click.stop="toggleFilterCol('status', $event)"
            ><Filter /></el-icon>
          </span>
        </template>
        <template #default="{ row }">
          <el-tag
            size="small"
            class="pool-tag-plain"
            :style="{ borderColor: statusPoolColor(row.status), color: statusPoolColor(row.status) }"
          >
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="isBuiltinActive('priority')" prop="priority" :width="mergedColWidth('priority', columnWidths.priority ?? 80)" align="center">
        <template #header>
          <span class="th-with-filter">
            <span class="sortable-header" @click.stop="toggleSort('priority')" style="flex:1">
              优先级
              <span class="sort-indicator">
                <el-icon v-if="getSortOrder('priority') === 'asc'" class="sort-icon active"><SortUp /></el-icon>
                <el-icon v-else-if="getSortOrder('priority') === 'desc'" class="sort-icon active"><SortDown /></el-icon>
                <el-icon v-else class="sort-icon"><SortUp /></el-icon>
                <span v-if="getSortOrder('priority')" class="sort-rank">{{ getSortRank('priority') }}</span>
              </span>
            </span>
            <el-icon
              class="filter-icon"
              :class="{ active: hasFilter('priority') }"
              @click.stop="toggleFilterCol('priority', $event)"
            ><Filter /></el-icon>
          </span>
        </template>
        <template #default="{ row }">
          <el-tag
            size="small"
            class="pool-tag-plain"
            :style="{ borderColor: priorityPoolColor(row.priority), color: priorityPoolColor(row.priority) }"
          >
            {{ priorityLabel(row.priority) }}
          </el-tag>
        </template>
      </el-table-column>
      <!-- 创建时间 -->
      <el-table-column v-if="isBuiltinActive('created_at')" prop="created_at" :width="mergedColWidth('created_at', 150)" align="center">
        <template #header>
          <span class="th-with-filter">
            <span class="sortable-header" @click.stop="toggleSort('created_at')" style="flex:1">
              创建时间
              <span class="sort-indicator">
                <el-icon v-if="getSortOrder('created_at') === 'asc'" class="sort-icon active"><SortUp /></el-icon>
                <el-icon v-else-if="getSortOrder('created_at') === 'desc'" class="sort-icon active"><SortDown /></el-icon>
                <el-icon v-else class="sort-icon"><SortUp /></el-icon>
                <span v-if="getSortOrder('created_at')" class="sort-rank">{{ getSortRank('created_at') }}</span>
              </span>
            </span>
            <el-icon class="filter-icon" :class="{ active: hasFilter('created_at') }" @click.stop="toggleFilterCol('created_at', $event)"><Filter /></el-icon>
          </span>
        </template>
        <template #default="{ row }">
          <span class="date-cell">{{ formatDateTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <!-- 更新时间 -->
      <el-table-column v-if="isBuiltinActive('updated_at')" prop="updated_at" :width="mergedColWidth('updated_at', 150)" align="center">
        <template #header>
          <span class="th-with-filter">
            <span class="sortable-header" @click.stop="toggleSort('updated_at')" style="flex:1">
              更新时间
              <span class="sort-indicator">
                <el-icon v-if="getSortOrder('updated_at') === 'asc'" class="sort-icon active"><SortUp /></el-icon>
                <el-icon v-else-if="getSortOrder('updated_at') === 'desc'" class="sort-icon active"><SortDown /></el-icon>
                <el-icon v-else class="sort-icon"><SortUp /></el-icon>
                <span v-if="getSortOrder('updated_at')" class="sort-rank">{{ getSortRank('updated_at') }}</span>
              </span>
            </span>
            <el-icon class="filter-icon" :class="{ active: hasFilter('updated_at') }" @click.stop="toggleFilterCol('updated_at', $event)"><Filter /></el-icon>
          </span>
        </template>
        <template #default="{ row }">
          <span class="date-cell">{{ formatDateTime(row.updated_at) }}</span>
        </template>
      </el-table-column>
      <!-- 自定义字段列（动态） -->
      <el-table-column
        v-for="cf in customFields.filter(f => !f.is_builtin)"
        :key="'cf_' + cf.id"
        :prop="'cf_' + cf.id"
        :label="cf.field_name"
        :width="mergedColWidth('cf_' + cf.id, columnWidths['cf_' + cf.id] || 120)"
        :align="cf.field_type === 'number' ? 'right' : 'center'"
      >
        <template #header>
          <span class="th-with-filter">
            <span class="sortable-header" @click.stop="toggleSort('cf_' + cf.id)" style="flex:1">
              {{ cf.field_name }}
              <span class="sort-indicator">
                <el-icon v-if="getSortOrder('cf_' + cf.id) === 'asc'" class="sort-icon active"><SortUp /></el-icon>
                <el-icon v-else-if="getSortOrder('cf_' + cf.id) === 'desc'" class="sort-icon active"><SortDown /></el-icon>
                <el-icon v-else class="sort-icon"><SortUp /></el-icon>
                <span v-if="getSortOrder('cf_' + cf.id)" class="sort-rank">{{ getSortRank('cf_' + cf.id) }}</span>
              </span>
            </span>
            <el-icon
              class="filter-icon"
              :class="{ active: hasFilter('cf_' + cf.id) }"
              @click.stop="toggleFilterCol('cf_' + cf.id, $event)"
            ><Filter /></el-icon>
          </span>
        </template>
        <template #default="{ row }">
          <span v-if="cf.field_type === 'multi_dropdown'" class="cf-value multi-dropdown-value">
            <el-tag
              v-for="opt in splitMultiValue(getCustomValue(row.custom_values, cf.id))"
              :key="opt"
              size="small"
              class="multi-tag"
              :style="optionTagStyle(cf.field_options, opt)"
            >{{ opt }}</el-tag>
          </span>
          <span v-else-if="cf.field_type === 'dropdown'" class="cf-value">
            <el-tag
              v-if="getCustomValue(row.custom_values, cf.id)"
              size="small"
              :style="optionTagStyle(cf.field_options, getCustomValue(row.custom_values, cf.id))"
            >{{ getCustomValue(row.custom_values, cf.id) }}</el-tag>
          </span>
          <span v-else-if="cf.field_type === 'text'" class="cf-value cf-text-cell" :title="getCustomValue(row.custom_values, cf.id)">{{ getCustomValue(row.custom_values, cf.id) }}</span>
          <span v-else-if="cf.field_type === 'datetime'" class="cf-value">{{ formatDateTime(getCustomValue(row.custom_values, cf.id)) }}</span>
          <span v-else-if="cf.field_type === 'date'" class="cf-value">{{ formatDate(getCustomValue(row.custom_values, cf.id)) }}</span>
          <span v-else-if="cf.field_type === 'link'" class="cf-value">
            <a v-if="getCustomValue(row.custom_values, cf.id)" :href="getCustomValue(row.custom_values, cf.id)" target="_blank" class="cf-link" :title="getCustomValue(row.custom_values, cf.id)">{{ getCustomValue(row.custom_values, cf.id) }}</a>
          </span>
    <span v-else class="cf-value">{{ getCustomValue(row.custom_values, cf.id) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" :width="mergedColWidth('操作', 70)" align="center" fixed="right">
        <template #default="{ row }">
          <el-button text size="small" type="danger" @click.stop="removeReq(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <!-- 列筛选面板 -->
    <div v-if="filterOpen" class="filter-overlay" @click="closeFilter" />
    <div v-if="filterOpen" class="filter-panel-wrap" :style="filterPanelStyle" @click.stop>
      <div class="filter-search-wrap">
        <el-input v-model="filterSearch" size="small" placeholder="搜索… 空格分隔多关键词" clearable class="filter-search-input" @keyup.enter="toggleFuzzyMode" />
        <el-button
          size="small"
          :class="['filter-mode-btn', { active: filterMode !== '' }]"
          @click="toggleFuzzyMode"
        >
          {{ filterMode === 'include' ? '包含' : filterMode === 'exclude' ? '排除' : '搜索' }}
        </el-button>
      </div>
      <div class="filter-options">
        <!-- 日期/时间列：分级树（扁平渲染） -->
        <template v-if="isDateFilter">
          <div
            v-for="node in flattenedDateNodes"
            :key="node.value"
            class="filter-opt-row dt-row"
            :style="{ paddingLeft: (8 + node.depth * 16) + 'px' }"
            @click.stop="node.hasChildren && toggleDateNode(node)"
          >
            <span v-if="node.hasChildren" class="dt-toggle">{{ dtExpanded.has(node.value) ? '▼' : '▶' }}</span>
            <span v-else style="width:14px;flex-shrink:0" />
            <el-checkbox
              :model-value="isFilterSelected(node.value)"
              size="small"
              @change="toggleFilterVal(node.value)"
              @click.stop
            />
            <span class="filter-opt-text">{{ node.label }}</span>
            <span class="filter-opt-count">{{ node.count }}</span>
          </div>
        </template>
        <!-- 普通列：平铺列表 -->
        <template v-else>
        <label v-for="opt in filteredColOptions" :key="opt.value" class="filter-opt-row">
          <el-checkbox
            :model-value="isFilterSelected(opt.value)"
            size="small"
            @change="toggleFilterVal(opt.value)"
          />
          <span class="filter-opt-text">{{ opt.value }}</span>
          <span class="filter-opt-count">{{ opt.count }}</span>
        </label>
        </template>
        <div v-if="(isDateFilter && !flattenedDateNodes.length) || (!isDateFilter && !filteredColOptions.length)" class="filter-empty">
          {{ filterSearch ? '无匹配结果' : '暂无数据' }}
        </div>
      </div>
      <div class="filter-actions-bar">
        <el-checkbox
          :model-value="filterSelectAllChecked"
          :indeterminate="filterSelectAllIndeterminate"
          size="small"
          @change="filterSelectAll"
        >全选</el-checkbox>
        <div class="filter-btn-group">
          <el-button text size="small" @click.stop="filterInvert">反选</el-button>
          <el-button v-if="hasFilter(filterCol)" text size="small" type="danger" @click.stop="filterClear">清除筛选</el-button>
        </div>
      </div>
      </div>
      </div>
    </template>
    </div>
    <div v-if="requirements.length" class="pagination-bar">
      <span v-if="total !== totalAll && totalAll" class="filter-total-tip">已筛选 {{ total }} 条 / 共 {{ totalAll }} 条</span>
      <span v-else class="filter-total-tip">共 {{ total }} 条</span>
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[25, 50, 75, 100]"
        :total="total"
        layout="sizes, prev, pager, next, jumper"
        background
        small
        @current-change="loadRequirements"
        @size-change="loadRequirements"
      />
    </div>
    <el-empty v-if="!loading && !requirements.length" description="暂无需求" />

    <!-- 批量操作悬浮进度条 -->
    <div v-if="batchDeleting" class="batch-progress-overlay">
      <div class="batch-progress-card">
        <el-progress
          :percentage="Math.round(deleteProgress.current / deleteProgress.total * 100)"
          :stroke-width="10"
          :show-text="false"
          :stroke-linecap="'round'"
          style="width: 200px"
        />
        <span class="batch-progress-text">
          {{ deleteProgress.current }} / {{ deleteProgress.total }}
        </span>
      </div>
    </div>

    <!-- 新建需求对话框 -->
    <el-dialog
      v-model="dialogVisible"
      title="新建需求"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="需求标题" />
        </el-form-item>
        <el-form-item v-if="isBuiltinActive('status')" label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option
              v-for="s in statusPools"
              :key="s.id"
              :label="s.name"
              :value="statusNameToValue(s.name)"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isBuiltinActive('priority')" label="优先级">
          <el-select v-model="form.priority" style="width: 100%">
            <el-option
              v-for="p in priorityPools"
              :key="p.id"
              :label="p.name"
              :value="priorityNameToValue(p.name)"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 单元格编辑对话框 -->
    <el-dialog
      v-model="cellEditVisible"
      :title="cellEditTitle"
      width="420px"
      :close-on-click-modal="false"
      class="cell-edit-dialog"
    >
      <el-form label-position="top" class="cell-edit-form">
        <el-form-item label="标题" v-if="cellEditField === 'title'">
          <el-input v-model="cellEditValue" placeholder="输入需求标题" clearable @keyup.enter="saveCellEdit" />
        </el-form-item>
        <el-form-item label="状态" v-if="cellEditField === 'status' && isBuiltinActive('status')">
          <el-select v-model="cellEditValue" placeholder="选择状态" style="width: 100%">
            <el-option
              v-for="s in statusPools"
              :key="s.id"
              :label="s.name"
              :value="statusNameToValue(s.name)"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" v-if="cellEditField === 'priority' && isBuiltinActive('priority')">
          <el-select v-model="cellEditValue" placeholder="选择优先级" style="width: 100%">
            <el-option
              v-for="p in priorityPools"
              :key="p.id"
              :label="p.name"
              :value="priorityNameToValue(p.name)"
            />
          </el-select>
        </el-form-item>
        <!-- 自定义字段编辑 -->
        <el-form-item
          v-if="cellEditField.startsWith('cf_')"
          :label="(cellEditFieldDef && cellEditFieldDef.field_name) || '自定义字段'"
        >
          <el-input
            v-if="cellEditFieldDef && cellEditFieldDef.field_type === 'text'"
            v-model="cellEditValue"
            placeholder="输入值"
            clearable
          />
          <el-select
            v-else-if="cellEditFieldDef && cellEditFieldDef.field_type === 'dropdown'"
            v-model="cellEditValue"
            placeholder="请选择"
            style="width: 100%"
          >
            <el-option
              v-for="opt in parseOptions(cellEditFieldDef.field_options)"
              :key="opt"
              :label="opt"
              :value="opt"
            >
              <span class="option-label">
                <span v-if="getOptionColor(cellEditFieldDef.field_options, opt)" class="option-dot" :style="{ backgroundColor: getOptionColor(cellEditFieldDef.field_options, opt) }"></span>
                {{ opt }}
              </span>
            </el-option>
          </el-select>
          <el-select
            v-else-if="cellEditFieldDef && cellEditFieldDef.field_type === 'multi_dropdown'"
            v-model="cellEditValue"
            multiple
            placeholder="请选择（可多选）"
            style="width: 100%"
          >
            <el-option
              v-for="opt in parseOptions(cellEditFieldDef.field_options)"
              :key="opt"
              :label="opt"
              :value="opt"
            >
              <span class="option-label">
                <span v-if="getOptionColor(cellEditFieldDef.field_options, opt)" class="option-dot" :style="{ backgroundColor: getOptionColor(cellEditFieldDef.field_options, opt) }"></span>
                {{ opt }}
              </span>
            </el-option>
          </el-select>
          <el-date-picker
            v-else-if="cellEditFieldDef && cellEditFieldDef.field_type === 'date'"
            v-model="cellEditValue"
            type="date"
            placeholder="选择日期"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
          <el-date-picker
            v-else-if="cellEditFieldDef && cellEditFieldDef.field_type === 'datetime'"
            v-model="cellEditValue"
            type="datetime"
            placeholder="选择时间"
            style="width: 100%"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
          <el-input-number
            v-else-if="cellEditFieldDef && cellEditFieldDef.field_type === 'number'"
            v-model="cellEditValue"
            :controls="false"
            style="width: 100%"
          />
          <el-input
            v-else-if="cellEditFieldDef && cellEditFieldDef.field_type === 'link'"
            v-model="cellEditValue"
            placeholder="输入链接地址（URL）"
            clearable
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cellEditVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCellEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- Excel 导入对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      :title="'Excel 导入需求 - ' + (importMode === 'overwrite' ? '覆盖模式' : importMode === 'update' ? '更新模式' : '追加模式')"
      width="700px"
      :close-on-click-modal="false"
      :before-close="resetImport"
    >
      <!-- 步骤1: 上传文件 -->
      <template v-if="importStep === 'upload'">
        <div class="import-upload-area">
          <input
            type="file"
            ref="importFileInputRef"
            accept=".xlsx,.xls"
            @change="onImportFileSelected"
            style="display:none"
          />
          <el-button type="primary" @click="$refs.importFileInputRef.click()">
            <el-icon><Upload /></el-icon> 选择 Excel 文件
          </el-button>
          <div v-if="importFile" style="margin-top:8px;font-size:13px;color:#888">
            已选择：<strong>{{ importFile.name }}</strong>
          </div>
          <div class="el-upload__tip">支持 .xlsx / .xls 格式，第一行为表头</div>
        </div>
        <div style="margin-top: 16px">
          <el-button type="primary" :disabled="!importFile" :loading="importPreviewLoading" @click="loadImportPreview">
            预览数据
          </el-button>
        </div>
        <div v-if="importPreview" style="margin-top: 12px">
          <p style="margin:0 0 8px;font-size:13px;color:#888">
            识别到 <strong>{{ importPreview.headers.length }}</strong> 列，<strong>{{ importPreview.total_rows }}</strong> 行数据
          </p>
        </div>
      </template>

      <!-- 步骤2: 列映射 -->
      <template v-if="importStep === 'mapping'">
        <p style="margin:0 0 12px;font-size:13px;color:#555">将 Excel 列映射到需求字段，未映射的列将被忽略</p>
        <div v-for="(h, i) in importPreview.headers" :key="i" class="import-mapping-row">
          <span class="import-mapping-label">{{ h }}</span>
          <el-icon style="margin:0 8px"><ArrowRight /></el-icon>
          <el-select v-model="importMapping[h].target" style="width:160px" @change="onMappingTargetChange(h)">
            <el-option label="— 忽略 —" value="" />
            <el-option label="标题" value="title" />
            <el-option label="状态" value="status" />
            <el-option label="优先级" value="priority" />
            <el-option-group v-if="importMode !== 'overwrite'" label="自定义字段">
              <el-option
                v-for="cf in customFields.filter(f => !f.is_builtin)"
                :key="cf.id"
                :label="cf.field_name"
                :value="'field:' + cf.id"
              />
            </el-option-group>
            <el-option label="+ 新建列" value="new" />
          </el-select>
          <!-- 新建字段配置 -->
          <span v-if="importMapping[h].target === 'new'" class="import-new-field">
            <el-input v-model="importMapping[h].field_name" placeholder="字段名" size="small" style="width:120px" />
            <el-select v-model="importMapping[h].field_type" size="small" style="width:100px">
              <el-option label="文本" value="text" />
              <el-option label="单选" value="dropdown" />
              <el-option label="多选" value="multi_dropdown" />
              <el-option label="时间" value="datetime" />
              <el-option label="日期" value="date" />
              <el-option label="数字" value="number" />
              <el-option label="链接" value="link" />
            </el-select>
          </span>
        </div>
        <div style="margin-top:16px;display:flex;gap:8px">
          <el-button @click="importStep = 'upload'">上一步</el-button>
          <el-button type="primary" @click="doImport()" :loading="importLoading">确认导入</el-button>
        </div>
        <div v-if="importResult" style="margin-top:12px">
          <el-alert :title="importResult.message" type="success" show-icon :closable="false" />
        </div>
      </template>
    </el-dialog>

    <!-- 重复标题对话框 -->
    <el-dialog
      v-model="dupDialogVisible"
      title="发现重复标题"
      width="500px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <p style="margin:0 0 12px">{{ dupMessage }}</p>
      <div v-if="dupDuplicates.length" style="margin-bottom:8px">
        <div v-for="d in dupDuplicates" :key="d.title" style="font-size:13px;margin:2px 0">
          「{{ d.title }}」— 第 {{ d.rows.join('、') }} 行
        </div>
      </div>
      <template #footer>
        <template v-if="dupDialogType === 'choice'">
          <el-button @click="onDupConfirm('cancel')">放弃导入</el-button>
          <el-button type="primary" @click="onDupConfirm('add_sequence')">添加序号导入</el-button>
        </template>
        <template v-else-if="dupDialogType === 'abandon_only'">
          <el-button type="primary" @click="onDupConfirm('cancel')">取消导入</el-button>
        </template>
        <template v-else-if="dupDialogType === 'info_only'">
          <el-button type="primary" @click="onDupConfirm('ok')">知道了</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, watch, shallowRef, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import {
  getRequirements, createRequirement, updateRequirement, deleteRequirement,
  getReqCustomFields, getProject,
  getReqStatusPools, getReqPriorityPools, getReqFilterStats,
  importRequirementsPreview, importRequirements,
  getReqColWidths, saveReqColWidths, deleteReqColWidths,
  getReqViewState, saveReqViewState,
} from '../api/index.js'

const route = useRoute()
const router = useRouter()
const projectId = route.params.projectId

// 状态
const requirements = shallowRef([])
const loading = ref(false)
const customFields = ref([])

// 检查内置字段是否启用（从 customFields 中判断，customFields 只含活跃字段）
function isBuiltinActive(name) {
  const fieldNameMap = { status: '状态', priority: '优先级', title: '标题', created_at: '创建时间', updated_at: '更新时间' }
  const cn = fieldNameMap[name] || name
  return customFields.value.some(f => f.field_name === cn && f.is_builtin)
}
const statusPools = ref([])
const priorityPools = ref([])
const projectName = ref('')
// 分页
const currentPage = ref(1)
const pageSize = ref(50)
const total = ref(0)
const totalAll = ref(0)     // 未筛选时的总条数
// 表格高度（仅数据区滚动）
const tableRef = ref(null)
const tableInnerRef = ref(null)
const tableMaxHeight = ref(600)
let resizeObserver = null

function calcTableHeight() {
  if (tableInnerRef.value) {
    const h = tableInnerRef.value.clientHeight
    if (h > 0) tableMaxHeight.value = h
  }
}
// 多列排序状态：使用有序数组保持点击顺序，sortKeys[0]=主排序
const sortKeys = reactive([])

// 表格 key：自定义字段变化时强制重绘（不含列宽，避免破坏拖拽状态）
const tableKey = computed(() => {
  return 'req-table-' + customFields.value.map(cf => cf.id).join(',')
})

// ── 列宽计算：基于字符权重 + 随机采样 ──
const SAMPLE_SIZE = 200
const CHAR_WEIGHT_CN = 2
const CHAR_WEIGHT_EN = 1
const WEIGHT_BUFFER = 1.25  // 乘以 1.25 获得 20% 缓冲
const COL_MIN = 80
const COL_MAX = 400
const COL_OVERFLOW = 350   // 推荐宽度超过此值 → 固定 280px
const COL_OVERFLOW_FIX = 280
// 表头在列名字之外占用的固定开销：排序图标(14) + 筛选图标(14) + 间距(8) + 单元格内边距(20) ≈ 56
// 无排序的列（显示ID）少一个图标：56 - 14 - 4 ≈ 38
const HEADER_EXTRA_SORT = 56
const HEADER_EXTRA_NOSORT = 38

/** 字符权重：中文=2，英文/数字/标点=1 */
function charWeight(s) {
  let w = 0
  for (const ch of String(s || '')) {
    w += ch.charCodeAt(0) > 127 ? CHAR_WEIGHT_CN : CHAR_WEIGHT_EN
  }
  return w
}

/** 列名总宽度 = MAX(80, 列名字符权重×1.25) + 表头图标开销 */
function labelMinWidth(label, hasSort = true) {
  const overhead = hasSort ? HEADER_EXTRA_SORT : HEADER_EXTRA_NOSORT
  return Math.max(charWeight(label) * WEIGHT_BUFFER, COL_MIN) + overhead
}

/**
 * 基于采样数据计算列宽 (px)
 * - 随机采样 200 行，不足则全量
 * - 每列取最大字符权重 × 1.25
 * - 超过 COL_OVERFLOW 的列固定为 COL_OVERFLOW_FIX
 * - 限制 [COL_MIN, COL_MAX]
 */
function calcWidths(rows, fields) {
  // 随机采样
  const sampled = rows.length > SAMPLE_SIZE
    ? [...rows].sort(() => Math.random() - 0.5).slice(0, SAMPLE_SIZE)
    : rows

  const widths = {}

  // 基础列：标题 / 状态 / 优先级 / 显示ID
  const baseCols = { title: '标题', status: '状态', priority: '优先级', display_id: '显示ID' }
  for (const [key, label] of Object.entries(baseCols)) {
    let maxW = 0
    for (const row of sampled) {
      maxW = Math.max(maxW, charWeight(row[key]))
    }
    let w = Math.round(maxW * WEIGHT_BUFFER)
    // display_id 无排序图标，其他列有排序+筛选图标
    w = Math.max(w, key === 'display_id' ? labelMinWidth(label, false) : labelMinWidth(label))
    if (w > COL_OVERFLOW) w = COL_OVERFLOW_FIX
    w = Math.min(w, COL_MAX)
    widths[key] = w
  }

  // 自定义字段列
  for (const cf of fields) {
    let maxW = 0
    for (const row of sampled) {
      const val = getCustomValue(row.custom_values, cf.id)
      maxW = Math.max(maxW, charWeight(val))
    }
    let w = Math.round(maxW * WEIGHT_BUFFER)
    w = Math.max(w, labelMinWidth(cf.field_name))
    if (w > COL_OVERFLOW) w = COL_OVERFLOW_FIX
    w = Math.min(w, COL_MAX)
    widths['cf_' + cf.id] = w
  }

  return widths
}

/** 基于当前数据重算列宽并持久化 */
/** 基于当前数据重算列宽并持久化（导入操作后触发，会覆盖用户拖拽值） */
function recalcAndSaveWidths() {
  const newWidths = calcWidths(requirements.value, customFields.value)
  savedWidths.value = { ...newWidths }
  saveWidths(newWidths)
  // 导入后删除服务端配置文件，下次打开从 localStorage 恢复算法值
  deleteReqColWidths(projectId).catch(() => {})
}

const columnWidths = ref({})

// 基于当前数据计算列宽（仅在无筛选的全量加载时重算）
function computeColumnWidths() {
  columnWidths.value = calcWidths(requirements.value, customFields.value)
}

// ── 列筛选 ──
const columnFilters = ref({})  // { prop: string[] }
const fuzzyFilters = ref({})   // { prop: { text: string, mode: 'include'|'exclude' } }
const filterOpen = ref(false)
const filterCol = ref('')       // 当前筛选列 prop
const filterRect = ref(null)    // 触发元素 DOMRect
const filterSearch = ref('')    // 筛选面板内搜索词
const filterMode = ref('include')  // 'include' | 'exclude'
const filterStats = ref({})     // 全量数据统计 { prop: [{value, count}] }
const dtExpanded = ref(new Set()) // 日期树展开节点

// ---- 筛选条件展示 ----
const filterColLabels = {
  display_id: '显示ID',
  title: '标题',
  status: '状态',
  priority: '优先级',
  created_at: '创建时间',
  updated_at: '更新时间',
}

function getFilterLabel(col) {
  if (filterColLabels[col]) return filterColLabels[col]
  if (col.startsWith('cf_')) {
    const fid = parseInt(col.slice(3))
    const cf = customFields.value.find(f => f.id === fid)
    return cf ? cf.field_name : col
  }
  return col
}

const activeFilters = computed(() => {
  const result = []
  for (const [col, values] of Object.entries(columnFilters.value)) {
    if (!values || !values.length) continue
    const label = getFilterLabel(col)
    for (const val of values) {
      result.push({ col, label, value: val })
    }
  }
  return result
})

const fuzzyFilterChips = computed(() => {
  const result = []
  for (const [col, f] of Object.entries(fuzzyFilters.value)) {
    if (!f.text) continue
    result.push({ col, label: getFilterLabel(col), text: f.text, mode: f.mode })
  }
  return result
})

function removeFilterValue(col, val) {
  const cur = (columnFilters.value[col] || []).filter(v => v !== val)
  if (cur.length) {
    columnFilters.value = { ...columnFilters.value, [col]: cur }
  } else {
    const copy = { ...columnFilters.value }
    delete copy[col]
    columnFilters.value = copy
  }
}

function clearAllFilters() {
  columnFilters.value = {}
  fuzzyFilters.value = {}
}

const filterPanelStyle = computed(() => {
  const r = filterRect.value
  if (!r) return { display: 'none' }
  const w = 240  // 面板宽度
  const h = 340  // 面板最大高度
  const vw = window.innerWidth
  const vh = window.innerHeight
  // 水平方向：不超出右边界
  let left = Math.max(4, r.left)
  if (left + w > vw - 4) left = vw - w - 4
  // 垂直方向：距离底部不够则翻到上方
  let top
  if (r.bottom + h + 12 > vh) {
    top = Math.max(4, r.top - h - 4)
  } else {
    top = r.bottom + 4
  }
  return { position: 'fixed', left: left + 'px', top: top + 'px', zIndex: 9999 }
})

function toggleFilterCol(colProp, event) {
  event.stopPropagation()
  const target = event.currentTarget || event.target
  if (target) {
    filterRect.value = target.getBoundingClientRect()
  } else {
    // 后备：鼠标位置附近
    filterRect.value = {
      left: event.clientX || 100,
      top: event.clientY || 100,
      right: (event.clientX || 100) + 240,
      bottom: (event.clientY || 100) + 20,
      width: 240,
      height: 20,
      x: event.clientX || 100,
      y: event.clientY || 100,
    }
  }
  filterCol.value = colProp
  // 恢复该列已有的模糊筛选状态
  const existing = fuzzyFilters.value[colProp]
  if (existing && existing.text) {
    filterSearch.value = existing.text
    filterMode.value = existing.mode
  } else {
    filterSearch.value = ''
    filterMode.value = ''
  }
  filterOpen.value = true
  // 获取跨列联动后的筛选统计数据（排除当前列自己的筛选）
  const otherFilters = Object.fromEntries(
    Object.entries(columnFilters.value).filter(([k, v]) => k !== colProp && v && v.length)
  )
  const params = {}
  if (Object.keys(otherFilters).length) {
    // status/priority 转回英文
    if (otherFilters.status) otherFilters.status = otherFilters.status.map(s => statusNameToValue(s))
    if (otherFilters.priority) otherFilters.priority = otherFilters.priority.map(p => priorityNameToValue(p))
    params.column_filters = JSON.stringify(otherFilters)
  }
  getReqFilterStats(projectId, params).then(stats => { filterStats.value = stats }).catch(() => {})
}

function closeFilter() {
  filterOpen.value = false
}

function hasFilter(colProp) {
  if (columnFilters.value[colProp]?.length > 0) return true
  if (fuzzyFilters.value[colProp]?.text) return true
  return false
}

function getCellValue(row, colProp) {
  if (!row) return ''
  if (colProp.startsWith('cf_')) {
    const fieldId = parseInt(colProp.replace('cf_', ''), 10)
    const raw = getCustomValue(row.custom_values, fieldId) || ''
    // 日期/时间列：格式化为标准形式以支持前缀匹配
    const cf = customFields.value.find(c => c.id === fieldId)
    if (cf && raw) {
      if (cf.field_type === 'date') {
        const d = parseDate(raw)
        if (d) return d.format('YYYY-MM-DD')
      }
      if (cf.field_type === 'datetime') {
        const d = parseDate(raw)
        if (d) return d.format('YYYY-MM-DD HH:mm:ss')
      }
    }
    return raw
  }
  if (colProp === 'status') return statusLabel(row.status)
  if (colProp === 'priority') return priorityLabel(row.priority)
  if (colProp === 'created_at' || colProp === 'updated_at') return formatDateTime(row[colProp])
  const v = row[colProp]
  return v !== null && v !== undefined ? String(v) : ''
}

function getFilterOptions(colProp) {
  if (!colProp) return []
  const stats = filterStats.value[colProp]
  if (stats && stats.length) {
    return [...stats].sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
  }
  // 后备：客户端计算
  const counter = {}
  const rows = requirements.value || []
  for (const row of rows) {
    if (!row) continue
    const val = getCellValue(row, colProp) || '(空)'
    counter[val] = (counter[val] || 0) + 1
  }
  return Object.entries(counter)
    .map(([value, count]) => ({ value, count }))
    .sort((a, b) => b.count - a.count || a.value.localeCompare(b.value))
}

// 不再需要 getDataWithoutCol，筛选面板始终显示全量数据选项
function getDataWithoutCol(colProp) {
  let data = requirements.value
  if (!data) return []
  const filters = columnFilters.value
  for (const [prop, selected] of Object.entries(filters)) {
    if (prop === colProp) continue
    if (!selected || selected.length === 0) continue
    const selSet = new Set(selected)
    data = data.filter(row => row && selSet.has(getCellValue(row, prop)))
  }
  return data
}

const displayedRequirements = computed(() => {
  try {
    let data = requirements.value
    const filters = columnFilters.value
    for (const [prop, selected] of Object.entries(filters)) {
      if (!selected || selected.length === 0) continue
      if (prop.startsWith('cf_') && isDateFilterByProp(prop)) {
        // 日期列：前缀匹配
        data = data.filter(row => {
          const val = getCellValue(row, prop)
          return selected.some(prefix => val.startsWith(prefix))
        })
      } else {
        // 普通列：精确匹配
        const selSet = new Set(selected)
        data = data.filter(row => row && selSet.has(getCellValue(row, prop)))
      }
    }
    return data
  } catch (e) {
    console.error('displayedRequirements error:', e)
    return requirements.value || []
  }
})

function isDateFilterByProp(prop) {
  if (prop === 'created_at' || prop === 'updated_at') return true
  if (!prop || !prop.startsWith('cf_')) return false
  const fid = parseInt(prop.replace('cf_', ''), 10)
  const cf = customFields.value.find(c => c.id === fid)
  return cf && (cf.field_type === 'date' || cf.field_type === 'datetime')
}

// 筛选面板内的筛选后选项（按搜索词过滤）
const filteredColOptions = computed(() => {
  if (!filterCol.value) return []
  const all = getFilterOptions(filterCol.value)
  const kw = filterSearch.value.trim().split(/\s+/).filter(Boolean)
  if (!kw.length) return all
  return all.filter(opt => kw.some(k => opt.value.includes(k)))
})

// ── 日期/时间列分级树 ──
const isDateFilter = computed(() => {
  if (!filterCol.value) return false
  if (filterCol.value === 'created_at' || filterCol.value === 'updated_at') return true
  if (!filterCol.value.startsWith('cf_')) return false
  const fid = parseInt(filterCol.value.replace('cf_', ''), 10)
  const cf = customFields.value.find(c => c.id === fid)
  return cf && (cf.field_type === 'date' || cf.field_type === 'datetime')
})

const dateTreeDepth = computed(() => {
  if (!filterCol.value) return 0
  if (filterCol.value === 'created_at' || filterCol.value === 'updated_at') return 6
  if (!filterCol.value.startsWith('cf_')) return 0
  const fid = parseInt(filterCol.value.replace('cf_', ''), 10)
  const cf = customFields.value.find(c => c.id === fid)
  return cf?.field_type === 'datetime' ? 6 : 3
})

const dateFilterTree = computed(() => {
  if (!isDateFilter.value) return { roots: [] }
  const stats = filterStats.value[filterCol.value] || getFilterOptions(filterCol.value)
  const depth = dateTreeDepth.value  // 3=date, 6=datetime
  // 分离空值
  let emptyNode = null
  const prefixMap = {}
  for (const { value, count } of stats) {
    if (value === '(空)') {
      emptyNode = { value: '(空)', count, level: 0, label: '(空)', children: {} }
      continue
    }
    const segments = value.match(/\d+/g) || []
    if (!segments.length) continue
    for (let i = 1; i <= depth; i++) {
      const prefix = buildPrefix(segments, i)
      if (!prefixMap[prefix]) prefixMap[prefix] = { value: prefix, count: 0, level: i, children: {} }
      prefixMap[prefix].count += count
    }
  }
  // 构建树形结构
  const roots = []
  const nodeCache = {}
  for (const [path, node] of Object.entries(prefixMap)) {
    if (node.level === 1) {
      node.label = formatNodeLabel(path, node.level, depth)
      roots.push(node)
      nodeCache[path] = node
    } else {
      const segments = path.match(/\d+/g) || []
      const parentPath = buildPrefix(segments, node.level - 1)
      const parent = nodeCache[parentPath]
      if (parent) {
        node.label = formatNodeLabel(path, node.level, depth)
        parent.children[path] = node
        nodeCache[path] = node
      }
    }
  }
  roots.sort((a, b) => a.value.localeCompare(b.value))
  // 空值节点追加到末尾
  if (emptyNode) roots.push(emptyNode)
  // 为每个节点排序子节点
  for (const n of Object.values(nodeCache)) {
    const keys = Object.keys(n.children).sort()
    const sorted = {}
    for (const k of keys) sorted[k] = n.children[k]
    n.children = sorted
  }
  return { roots }
})

// 扁平化日期树为渲染列表
const flattenedDateNodes = computed(() => {
  if (!isDateFilter.value) return []
  const result = []
  function walk(nodes, depth, parentExpanded) {
    if (!parentExpanded) return
    for (const node of nodes) {
      result.push({ ...node, depth, hasChildren: Object.keys(node.children).length > 0 })
      walk(Object.values(node.children), depth + 1, dtExpanded.value.has(node.value))
    }
  }
  for (const r of dateFilterTree.value.roots) {
    walk([r], 0, true)
  }
  // 应用搜索过滤
  const kw = filterSearch.value.trim().split(/\s+/).filter(Boolean)
  if (!kw.length) return result
  return result.filter(n => kw.some(k => n.value.includes(k) || (n.label || '').includes(k)))
})

function toggleDateNode(node) {
  const s = new Set(dtExpanded.value)
  if (s.has(node.value)) { s.delete(node.value) } else { s.add(node.value) }
  dtExpanded.value = s
}

function buildPrefix(segments, level) {
  // 日期部分用 - 分隔，时间部分用空格+冒号分隔
  if (level <= 3) return segments.slice(0, level).join('-')
  return segments.slice(0, 3).join('-') + ' ' + segments.slice(3, level).join(':')
}

function formatNodeLabel(path, level, depth) {
  // path: "2026-01-27" (date) or "2026-01-27 17:39:08" (datetime prefixes)
  if (depth <= 3) {
    // date only
    if (level === 1) return extractSeg(path, 0) + '年'
    if (level === 2) return extractSeg(path, 1) + '月'
    if (level === 3) return extractSeg(path, 2) + '日'
  } else {
    if (level === 1) return extractSeg(path, 0) + '年'
    if (level === 2) return extractSeg(path, 1) + '月'
    if (level === 3) return extractSeg(path, 2) + '日'
    if (level === 4) return extractSeg(path, 3) + '时'
    if (level === 5) return extractSeg(path, 4) + '分'
    if (level === 6) return extractSeg(path, 5) + '秒'
  }
  return path
}

function extractSeg(path, idx) {
  const m = path.match(/\d+/g)
  return m && m[idx] ? m[idx] : '?'
}

const filterSelectAllChecked = computed(() => {
  if (!filterCol.value) return false
  const all = getFilterOptions(filterCol.value)
  const sel = columnFilters.value[filterCol.value] || []
  return all.length > 0 && sel.length === all.length
})

const filterSelectAllIndeterminate = computed(() => {
  if (!filterCol.value) return false
  const sel = columnFilters.value[filterCol.value] || []
  const all = getFilterOptions(filterCol.value)
  return sel.length > 0 && sel.length < all.length
})

function isFilterSelected(val) {
  const sel = columnFilters.value[filterCol.value]
  return sel ? sel.includes(val) : false
}

function toggleFilterVal(val) {
  const col = filterCol.value
  const cur = [...(columnFilters.value[col] || [])]
  const idx = cur.indexOf(val)
  if (idx === -1) { cur.push(val) } else { cur.splice(idx, 1) }
  columnFilters.value = { ...columnFilters.value, [col]: cur }
}

function filterSelectAll() {
  const col = filterCol.value
  const all = getFilterOptions(col).map(o => o.value)
  const cur = columnFilters.value[col] || []
  columnFilters.value = { ...columnFilters.value, [col]: cur.length === all.length ? [] : all }
}

function filterInvert() {
  const col = filterCol.value
  const all = getFilterOptions(col).map(o => o.value)
  const cur = columnFilters.value[col] || []
  columnFilters.value = { ...columnFilters.value, [col]: all.filter(v => !cur.includes(v)) }
}

function filterClear() {
  const col = filterCol.value
  const copy = { ...columnFilters.value }
  delete copy[col]
  columnFilters.value = copy
  clearFuzzy()
  filterMode.value = ''
  closeFilter()
}

function toggleFuzzyMode() {
  // 三态循环：'' → 'include' → 'exclude' → ''
  if (filterMode.value === '') {
    filterMode.value = 'include'
  } else if (filterMode.value === 'include') {
    filterMode.value = 'exclude'
  } else {
    filterMode.value = ''
  }
}

// 监听模糊搜索模式变化，自动应用/清除模糊筛选
watch(filterMode, (mode) => {
  if (!filterCol.value) return
  if (mode) {
    const text = filterSearch.value.trim()
    if (text) {
      applyFuzzy()
    }
  } else {
    clearFuzzy()
  }
})

// 在包含/排除模式下，搜索文字变化时自动更新
watch(filterSearch, (text) => {
  if (!filterCol.value || !filterMode.value) return
  const t = text.trim()
  if (t) {
    applyFuzzy()
  } else {
    clearFuzzy()
  }
})

function applyFuzzy() {
  const text = filterSearch.value.trim()
  if (text) {
    fuzzyFilters.value = { ...fuzzyFilters.value, [filterCol.value]: { text, mode: filterMode.value } }
    if (columnFilters.value[filterCol.value]) {
      const copy = { ...columnFilters.value }
      delete copy[filterCol.value]
      columnFilters.value = copy
    }
  }
}

function clearFuzzy() {
  const copy = { ...fuzzyFilters.value }
  delete copy[filterCol.value]
  fuzzyFilters.value = copy
}

function removeFuzzyFilter(col) {
  const copy = { ...fuzzyFilters.value }
  delete copy[col]
  fuzzyFilters.value = copy
}

// 手动调整列宽持久化（后端 + localStorage 双重持久化）
const STORAGE_KEY = `taskm_req_col_widths_${projectId}`

function loadWidthsFromLocal() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function saveWidths(widths) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widths))
  } catch {}
}

// 同步初始化：localStorage 持久化，刷新不丢失
// 用户拖拽的宽度优先级最高，仅在导入后重算时清除
const savedWidths = ref(loadWidthsFromLocal())

// 自动持久化：savedWidths 任何变化都同步到 localStorage
watch(savedWidths, (val) => {
  if (Object.keys(val).length) {
    saveWidths(val)
  }
}, { deep: true })

// 旧版 key 映射（显示ID 列原无 prop，存的是中文 label）
const COL_KEY_LEGACY = { 'display_id': '显示ID',  '显示ID': 'display_id' }

// 各列表头最小宽度（保证列名在同一行显示）
const HEADER_MIN_WIDTHS = {
  status: labelMinWidth('状态'),
  priority: labelMinWidth('优先级'),
  display_id: labelMinWidth('显示ID', false),
  title: labelMinWidth('标题'),
}

// 合并计算宽度：用户拖拽值 > 自动计算值 > 硬编码兜底
const mergedColWidth = (colKey, autoWidth) => {
  // 兼容旧 key：先查新 key，再查旧 key
  const userW = savedWidths.value[colKey] ?? savedWidths.value[COL_KEY_LEGACY[colKey]]
  
  // 用户调整值最高优先，完全不受最小宽度限制
  if (userW !== undefined) return Math.max(userW, 20)
  
  // 没有用户值时，用自动计算 + 表头最小宽度保证可读性
  const calcW = columnWidths.value[colKey]
  const auto = calcW ?? autoWidth
  const minW = HEADER_MIN_WIDTHS[colKey] || 80
  return Math.max(auto, minW)
}

// 拖拽保存到服务器的防抖函数
let saveColWidthsTimer = null
function debouncedSaveToServer(widths) {
  if (saveColWidthsTimer) clearTimeout(saveColWidthsTimer)
  saveColWidthsTimer = setTimeout(() => {
    saveReqColWidths(projectId, widths).catch(() => {})
    saveColWidthsTimer = null
  }, 500)
}

function onColumnResize(newWidth, _, column) {
  // column.property 对于带 prop 的列有效；无 prop 的列用 label
  const colKey = column.property || column.label
  if (!colKey) return
  savedWidths.value[colKey] = newWidth
  saveWidths(savedWidths.value)
  debouncedSaveToServer(savedWidths.value)
}

const getSortOrder = (prop) => {
  const found = sortKeys.find(s => s.prop === prop)
  return found ? found.order : ''
}

const getSortRank = (prop) => {
  const idx = sortKeys.findIndex(s => s.prop === prop)
  return idx >= 0 ? idx + 1 : 0
}
const isEditing = ref(false)
const editingId = ref(null)
const dialogVisible = ref(false)

// 表单
const form = ref({
  title: '',
  priority: 'normal',
  status: 'todo',
  customValues: {},
})

// 单元格选中与编辑
const selectedCell = reactive({ rowId: null, prop: null })  // 单击选中的单元格
const cellEditVisible = ref(false)  // 编辑对话框显隐
const cellEditField = ref('')       // 当前编辑的字段名
const cellEditRow = ref(null)       // 当前编辑的行
const cellEditValue = ref('')       // 当前编辑的值
let cellEditOrigValue = ''          // 打开对话框时的原始值（用于判空跳过）
const cellEditTitle = computed(() => {
  const titles = { title: '编辑标题', status: '编辑状态', priority: '编辑优先级' }
  const row = cellEditRow.value
  const suffix = row ? ` - ${row.title}` : ''
  let fieldLabel = titles[cellEditField.value]
  if (!fieldLabel && cellEditField.value.startsWith('cf_')) {
    fieldLabel = cellEditFieldDef.value
      ? `编辑${cellEditFieldDef.value.field_name}`
      : '编辑自定义字段'
  }
  return `${fieldLabel || '编辑'}${suffix}`
})

const cellEditFieldDef = computed(() => {
  if (!cellEditField.value || !cellEditField.value.startsWith('cf_')) return null
  const fieldId = parseInt(cellEditField.value.replace('cf_', ''), 10)
  return customFields.value.find(cf => cf.id === fieldId) || null
})

// 工具函数
const statusLabel = (s) => ({ todo: '待处理', in_progress: '进行中', done: '已完成', cancelled: '已取消' }[s] || s)
const statusTagType = (s) => ({ todo: 'warning', in_progress: 'primary', done: 'success', cancelled: 'info' }[s] || 'info')
const priorityLabel = (p) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[p] || p)
const priorityTagType = (p) => ({ low: 'info', normal: 'info', high: 'warning', urgent: 'danger' }[p] || 'info')
const statusPoolColor = (s) => {
  const name = statusLabel(s)
  const pool = statusPools.value.find(p => p.name === name)
  return pool ? pool.color : '#909399'
}
const priorityPoolColor = (p) => {
  const name = priorityLabel(p)
  const pool = priorityPools.value.find(p => p.name === name)
  return pool ? pool.color : '#909399'
}
const parseOptions = (opts) => {
  if (!opts) return []
  if (opts.startsWith('[')) {
    try { return JSON.parse(opts).map(o => o.label) } catch { return [] }
  }
  return opts.split('\n').filter(Boolean)
}
const getOptionColor = (opts, label) => {
  if (!opts || !opts.startsWith('[')) return ''
  try {
    const items = JSON.parse(opts)
    const found = items.find(o => o.label === label)
    return found ? found.color : ''
  } catch { return '' }
}
const optionTagStyle = (opts, label) => {
  const c = getOptionColor(opts, label)
  return c
    ? { borderColor: c, color: c, backgroundColor: '#fff' }
    : { borderColor: '#dcdfe6', color: '#606266', backgroundColor: '#fff' }
}
const splitMultiValue = (val) => val ? val.split(',').filter(Boolean) : []

// 日期/时间解析：支持多种常见格式
function parseDate(val) {
  if (!val) return null
  const s = val.trim()
  // 1) dayjs 直接解析（ISO、YYYY-MM-DD、YYYY/MM/DD 等）
  let d = dayjs(s)
  if (d.isValid()) return d
  // 2) YYYYMMDD
  let m = s.match(/^(\d{4})(\d{2})(\d{2})$/)
  if (m) {
    d = dayjs(`${m[1]}-${m[2]}-${m[3]}`)
    if (d.isValid()) return d
  }
  // 3) YYYYMMDDHHmmss
  m = s.match(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})$/)
  if (m) {
    d = dayjs(`${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}:${m[6]}`)
    if (d.isValid()) return d
  }
  // 4) YYYY年M月D日 [H时m分[s秒]]
  m = s.match(/^(\d{4})年(\d{1,2})月(\d{1,2})日(?:\s+(\d{1,2})时(\d{1,2})分(?:\s*(\d{1,2})秒)?)?$/)
  if (m) {
    let ds = `${m[1]}-${m[2].padStart(2,'0')}-${m[3].padStart(2,'0')}`
    if (m[4]) ds += ` ${m[4].padStart(2,'0')}:${(m[5]||'00').padStart(2,'0')}:${(m[6]||'00').padStart(2,'0')}`
    d = dayjs(ds)
    if (d.isValid()) return d
  }
  return null
}

const formatDateTime = (val) => {
  if (!val) return ''
  const d = parseDate(val)
  return d ? d.format('YYYY-MM-DD HH:mm:ss') : `(格式错误) ${val}`
}

const formatDate = (val) => {
  if (!val) return ''
  const d = parseDate(val)
  return d ? d.format('YYYY-MM-DD') : `(格式错误) ${val}`
}
// 按下拉选项的顺序对多选值排序
const sortByOptionOrder = (selected, fieldDef) => {
  if (!fieldDef || !fieldDef.field_options) return selected.join(',')
  const order = parseOptions(fieldDef.field_options)
  const orderMap = {}
  order.forEach((opt, i) => { orderMap[opt] = i })
  return selected
    .filter(v => v)
    .sort((a, b) => (orderMap[a] ?? 999) - (orderMap[b] ?? 999))
    .join(',')
}

const statusCount = (s) => requirements.value.filter(r => r.status === s).length

const getCustomValue = (values, fieldId) => {
  const found = values.find(v => v.field_id === fieldId)
  return found ? found.value : ''
}

const toggleSort = (prop) => {
  const idx = sortKeys.findIndex(s => s.prop === prop)
  if (idx === -1) {
    // 未排序：追加到末尾（次要排序）
    sortKeys.push({ prop, order: 'asc' })
  } else {
    const cur = sortKeys[idx].order
    if (cur === 'asc') {
      sortKeys[idx].order = 'desc'
    } else {
      // desc → 移除排序
      sortKeys.splice(idx, 1)
    }
  }
  currentPage.value = 1
  loadRequirements()
}

// 单元格事件
const isEditableProp = (prop) => {
  return ['title', 'status', 'priority'].includes(prop) || (prop && prop.startsWith('cf_'))
}

const cellClassName = ({ row, column }) => {
  if (selectedCell.rowId === row.id && selectedCell.prop === column.property) {
    return 'selected-cell'
  }
  return ''
}

const onCellClick = (row, column, cell) => {
  const prop = column.property
  if (!isEditableProp(prop)) return
  // 通过 DOM 直接切换选中状态，避免 Vue 响应式延迟
  document.querySelectorAll('.el-table .selected-cell').forEach(el => {
    el.classList.remove('selected-cell')
  })
  if (cell) cell.classList.add('selected-cell')
  selectedCell.rowId = row.id
  selectedCell.prop = prop
}

// 右键复制单元格内容
function onCellContextMenu(row, column, cell, event) {
  event?.preventDefault()
  let val = ''
  const prop = column.property
  if (prop) {
    if (prop.startsWith('cf_')) {
      const fieldId = parseInt(prop.replace('cf_', ''), 10)
      val = getCustomValue(row.custom_values, fieldId)
    } else {
      val = row[prop] || ''
    }
  } else {
    // 无 prop 的列（如显示ID）：从 cell DOM 取文本
    val = cell?.textContent?.trim() || ''
  }
  if (val) {
    navigator.clipboard.writeText(val).then(() => {
      ElMessage({ message: '已复制', type: 'success', duration: 1200 })
    }).catch(() => {})
  }
}

const onCellDblClick = (row, column) => {
  const prop = column.property
  if (!isEditableProp(prop)) return
  cellEditField.value = prop
  cellEditRow.value = row
  if (prop.startsWith('cf_')) {
    const fieldId = parseInt(prop.replace('cf_', ''), 10)
    cellEditOrigValue = getCustomValue(row.custom_values, fieldId)
    // 多选下拉：逗号分隔值转数组
    if (cellEditFieldDef.value && cellEditFieldDef.value.field_type === 'multi_dropdown') {
      cellEditValue.value = cellEditOrigValue ? cellEditOrigValue.split(',').filter(Boolean) : []
    } else if (cellEditFieldDef.value && cellEditFieldDef.value.field_type === 'date') {
      const parsed = parseDate(cellEditOrigValue)
      cellEditValue.value = parsed ? parsed.format('YYYY-MM-DD') : ''
    } else if (cellEditFieldDef.value && cellEditFieldDef.value.field_type === 'datetime') {
      const parsed = parseDate(cellEditOrigValue)
      cellEditValue.value = parsed ? parsed.format('YYYY-MM-DD HH:mm:ss') : ''
    } else {
      cellEditValue.value = cellEditOrigValue
    }
  } else {
    cellEditOrigValue = row[prop]
    cellEditValue.value = cellEditOrigValue
  }
  cellEditVisible.value = true
}

const saveCellEdit = async () => {
  if (!cellEditRow.value || !cellEditField.value) return
  const prop = cellEditField.value

  if (prop.startsWith('cf_')) {
    const fieldId = parseInt(prop.replace('cf_', ''), 10)
    const rawNew = cellEditValue.value
    // 多选下拉：按选项顺序排序，再转逗号分隔字符串
    const newVal = Array.isArray(rawNew) ? sortByOptionOrder(rawNew, cellEditFieldDef.value) : rawNew
    if (newVal === cellEditOrigValue) {
      cellEditVisible.value = false
      return
    }
    try {
      await updateRequirement(projectId, cellEditRow.value.id, {
        custom_values: { [fieldId]: newVal },
      })
      // 更新本地 custom_values 数组
      const existing = cellEditRow.value.custom_values.find(v => v.field_id === fieldId)
      if (existing) {
        existing.value = newVal
      } else {
        cellEditRow.value.custom_values.push({ field_id: fieldId, value: newVal })
      }
      cellEditVisible.value = false
    } catch { return }
    return
  }

  const newVal = cellEditValue.value
  if (newVal === cellEditOrigValue) {
    cellEditVisible.value = false
    return
  }
  try {
    await updateRequirement(projectId, cellEditRow.value.id, { [prop]: newVal })
    cellEditRow.value[prop] = newVal
    cellEditVisible.value = false
  } catch {
    // 错误由拦截器处理
  }
}

// 加载数据
async function loadRequirements() {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
    }
    // 多列排序：按点击顺序逗号拼接，全部交给后端 SQL 排序
    if (sortKeys.length) {
      params.sort_by = sortKeys.map(s => s.prop).join(',')
      params.sort_order = sortKeys.map(s => s.order).join(',')
      // 按池顺序传递状态/优先级的顺序，用于后端 CASE 表达式
      if (sortKeys.some(s => s.prop === 'status') && statusPools.value.length) {
        params.status_order = statusPools.value.map(s => statusNameToValue(s.name)).join(',')
      }
      if (sortKeys.some(s => s.prop === 'priority') && priorityPools.value.length) {
        params.priority_order = priorityPools.value.map(p => priorityNameToValue(p.name)).join(',')
      }
    }
    // 列筛选传递到后端（状态/优先级转回英文）
    const activeFilters = Object.entries(columnFilters.value).filter(([, v]) => v && v.length)
    if (activeFilters.length) {
      const raw = Object.fromEntries(activeFilters)
      if (raw.status) raw.status = raw.status.map(s => statusNameToValue(s))
      if (raw.priority) raw.priority = raw.priority.map(p => priorityNameToValue(p))
      params.column_filters = JSON.stringify(raw)
    }
    // 模糊筛选传递到后端
    if (Object.keys(fuzzyFilters.value).length) {
      const fuzzy = {}
      for (const [col, f] of Object.entries(fuzzyFilters.value)) {
        if (f.text) fuzzy[col] = { text: f.text, mode: f.mode }
      }
      if (Object.keys(fuzzy).length) {
        params.fuzzy_filters = JSON.stringify(fuzzy)
      }
    }
    const res = await getRequirements(projectId, params)
    requirements.value = res.items || res
    total.value = res.total ?? 0
    // 首次加载记录全量总数
    if (!activeFilters.length) {
      totalAll.value = total.value
    }
    await nextTick()
    calcTableHeight() // 数据加载后重新计算表格高度
  } finally {
    loading.value = false
  }
}

// 自动保存排序和筛选状态到服务端
let saveViewTimer = null
function saveViewState() {
  clearTimeout(saveViewTimer)
  saveViewTimer = setTimeout(() => {
    const data = {
      sortKeys: [...sortKeys],
      columnFilters: { ...columnFilters.value },
      fuzzyFilters: { ...fuzzyFilters.value },
    }
    saveReqViewState(projectId, data)
  }, 500)
}
watch(sortKeys, saveViewState, { deep: true })
watch(columnFilters, () => {
  saveViewState()
  currentPage.value = 1
  loadRequirements()
}, { deep: true })

watch(fuzzyFilters, () => {
  saveViewState()
  currentPage.value = 1
  loadRequirements()
}, { deep: true })

async function loadCustomFields() {
  customFields.value = await getReqCustomFields(projectId)
}

async function loadPools() {
  statusPools.value = await getReqStatusPools(projectId)
  priorityPools.value = await getReqPriorityPools(projectId)
}

async function loadProject() {
  try {
    const proj = await getProject(projectId)
    projectName.value = proj.name
  } catch {
    projectName.value = '项目'
  }
}

// CRUD
function openCreate() {
  isEditing.value = false
  editingId.value = null
  // 从池中获取默认值，无默认则取第一个
  const defaultStatus = statusPools.value.find(s => s.is_default)
    || statusPools.value[0]
  const defaultPriority = priorityPools.value.find(p => p.is_default)
    || priorityPools.value[0]
  form.value = {
    title: '',
    priority: defaultPriority ? priorityNameToValue(defaultPriority.name) : '',
    status: defaultStatus ? statusNameToValue(defaultStatus.name) : '',
    customValues: {},
  }
  dialogVisible.value = true
}

async function submit() {
  if (!form.value.title.trim()) {
    ElMessage.warning('请输入需求标题')
    return
  }
  try {
    const payload = { title: form.value.title }
    if (statusPools.value.length) payload.status = form.value.status
    if (priorityPools.value.length) payload.priority = form.value.priority
    await createRequirement(projectId, payload)
    ElMessage.success('需求已创建')
    dialogVisible.value = false
    currentPage.value = 1
    loadRequirements()
  } catch (e) {
    // error handled by interceptor
  }
}

const selectedReqs = ref([])
const selectAllStep = ref(0) // 0=未选 1=本页全选 2=全部全选
const batchDeleting = ref(false)

// 表头复选框状态
const headerChecked = computed(() => selectAllStep.value === 2)
const headerIndeterminate = computed(() => {
  if (selectAllStep.value === 2) return false
  if (selectAllStep.value === 1) return true
  // 部分选中时也显示横线
  return selectedReqs.value.length > 0 && selectedReqs.value.length < total.value
})

function toggleRowSelection(row, checked) {
  if (checked) {
    selectedReqs.value.push(row)
  } else {
    selectedReqs.value = selectedReqs.value.filter(r => r.id !== row.id)
  }
  // 手动选择部分行时重置全选状态
  selectAllStep.value = 0
}

async function onHeaderSelectChange() {
  if (selectAllStep.value === 2) {
    // 已全部选中 → 取消全选
    selectAllStep.value = 0
    selectedReqs.value = []
    return
  }
  if (selectAllStep.value === 1) {
    // 已选本页 → 扩展到全部
    selectAllStep.value = 2
    try {
      const res = await getRequirements(projectId, {
        page: 1, page_size: Math.max(total.value, 1),
      })
      selectedReqs.value = res.items || res
    } catch {}
    return
  }
  // 未选 → 全选本页
  selectAllStep.value = 1
  // 确保当前页所有行都被选中
  selectedReqs.value = [...requirements.value]
}
const deleteProgress = ref({ current: 0, total: 0 })

async function batchDeleteReq() {
  const ids = selectedReqs.value.map(r => r.id)
  try {
    await ElMessageBox.confirm(
      `确定删除已选择的 ${ids.length} 条需求？删除后不可恢复。`,
      '批量删除',
      { type: 'warning', confirmButtonText: '确定删除', confirmButtonClass: 'el-button--danger' }
    )
  } catch { return } // 取消
  batchDeleting.value = true
  deleteProgress.value = { current: 0, total: ids.length }
  let success = 0
  for (const id of ids) {
    try {
      await deleteRequirement(projectId, id)
      success++
    } catch { /* 跳过失败项 */ }
    deleteProgress.value.current = success
  }
  batchDeleting.value = false
  selectedReqs.value = []
  ElMessage.success(`成功删除 ${success} 条需求`)
  currentPage.value = 1
  loadRequirements()
}

async function removeReq(req) {
  try {
    await ElMessageBox.confirm(`确定删除需求「${req.title}」？`, '确认删除', { type: 'warning' })
    await deleteRequirement(projectId, req.id)
    ElMessage.success('已删除')
    currentPage.value = 1
    loadRequirements()
  } catch {}
}

// ── Excel 导入 ──
const importDialogVisible = ref(false)
const importStep = ref('upload')
const importFile = ref(null)
const importPreviewLoading = ref(false)
const importPreview = ref(null)
const importMapping = reactive({})
const importLoading = ref(false)
const importResult = ref(null)

const importMode = ref('append')

function openExcelImport(mode) {
  importMode.value = mode || 'append'
  importDialogVisible.value = true
  importStep.value = 'upload'
  importFile.value = null
  importPreview.value = null
  importResult.value = null
  // 初始化映射：所有列默认忽略
  const m = {}
  if (importPreview.value) {
    importPreview.value.headers.forEach(h => { m[h] = { target: '' } })
  }
  Object.assign(importMapping, m)
}

function resetImport() {
  importDialogVisible.value = false
  importStep.value = 'upload'
  importFile.value = null
  importPreview.value = null
  importResult.value = null
}

function onImportFileSelected(e) {
  const files = e.target.files || []
  importFile.value = files[0] || null
}

async function loadImportPreview() {
  if (!importFile.value) return
  importPreviewLoading.value = true
  try {
    const res = await importRequirementsPreview(projectId, importFile.value)
    importPreview.value = res
    // 初始化映射：先全部忽略，然后按名称自动匹配
    const m = {}
    res.headers.forEach(h => { m[h] = { target: '' } })

    // 基础字段名称映射
    const baseFieldMap = {
      '标题': 'title', '名称': 'title', '需求名称': 'title',
      '状态': 'status',
      '优先级': 'priority', '优先': 'priority',
    }

    // 自定义字段名称→ID 映射
    const cfMap = {}
    customFields.value.forEach(cf => {
      cfMap[cf.field_name] = 'field:' + cf.id
    })

    for (const h of res.headers) {
      const trimH = h.trim()
      // 先匹配基础字段
      if (baseFieldMap[trimH]) {
        m[h].target = baseFieldMap[trimH]
        continue
      }
      // 更新模式：自动匹配自定义字段
      if (importMode.value !== 'overwrite' && cfMap[trimH]) {
        m[h].target = cfMap[trimH]
      }
    }

    Object.assign(importMapping, m)
    importStep.value = 'mapping'
  } catch {}
  importPreviewLoading.value = false
}

function onMappingTargetChange(header) {
  if (importMapping[header].target === 'new') {
    importMapping[header].field_name = header
    importMapping[header].field_type = 'text'
    importMapping[header].field_options = ''
  }
}

function getImportMapping() {
  const mapping = {}
  for (const h of importPreview.value.headers) {
    const m = importMapping[h]
    if (m && m.target) {
      mapping[h] = {
        target: m.target,
        field_name: m.field_name || undefined,
        field_type: m.field_type || undefined,
        field_options: m.field_options || undefined,
      }
    }
  }
  return mapping
}

// ── 重复标题处理 ──
const dupDialogVisible = ref(false)
const dupDialogType = ref('choice')   // choice | abandon_only | info_only
const dupMessage = ref('')
const dupDuplicates = ref([])
const dupActions = ref([])            // 后端返回的可选操作

async function doImport(force = false, dupStrategy = 'cancel') {
  if (!importFile.value || !importPreview.value) return
  importLoading.value = true
  importResult.value = null
  try {
    const mapping = getImportMapping()
    const res = await importRequirements(
      projectId, importFile.value, mapping, importMode.value, force, dupStrategy
    )

    // 重复检测警告
    if (res.warning) {
      importLoading.value = false
      dupDialogType.value = res.dialog_type || 'choice'
      dupMessage.value = res.message || ''
      dupDuplicates.value = res.file_duplicates || []
      dupActions.value = res.actions || ['cancel']
      dupDialogVisible.value = true
      return
    }

    // 正常导入结果
    ElMessage.success(res.message)
    currentPage.value = 1
    importDialogVisible.value = false
    resetImport()
    loadRequirements()
    recalcAndSaveWidths()
  } catch {}
  importLoading.value = false
}

function onDupConfirm(action) {
  dupDialogVisible.value = false
  if (action === 'cancel' || action === 'ok') return  // 什么都不做
  if (action === 'add_sequence') {
    doImport(true, 'add_sequence')
  }
}

// 生命周期
// 按池顺序排序
const statusNameToValue = (name) => {
  const map = { '待处理': 'todo', '进行中': 'in_progress', '已完成': 'done', '已取消': 'cancelled' }
  return map[name] || name
}

const priorityNameToValue = (name) => {
  const map = { '低': 'low', '普通': 'normal', '高': 'high', '紧急': 'urgent' }
  return map[name] || name
}

onMounted(async () => {
  // 从 localStorage 加载本地列宽
  const localWidths = loadWidthsFromLocal()
  if (Object.keys(localWidths).length) {
    savedWidths.value = localWidths
  }

  // 异步从服务器加载列宽（覆盖 localStorage），失败时静默忽略
  try {
    const serverWidths = await getReqColWidths(projectId)
    if (serverWidths && Object.keys(serverWidths).length) {
      savedWidths.value = { ...savedWidths.value, ...serverWidths }
    }
  } catch { /* 服务器无配置时使用 localStorage 值 */ }

  // 从 URL 查询参数恢复筛选（总览页图表点击跳转）
  const query = route.query
  if (query.status || query.priority) {
    const initial = {}
    if (query.status) initial.status = [query.status]
    if (query.priority) initial.priority = [query.priority]
    columnFilters.value = initial
  }

  // 从服务端恢复排序和筛选状态
  try {
    const vs = await getReqViewState(projectId)
    if (vs && Object.keys(vs).length) {
      if (vs.sortKeys?.length) {
        sortKeys.splice(0, sortKeys.length, ...vs.sortKeys)
      }
      if (vs.columnFilters && !Object.keys(columnFilters.value).length) {
        columnFilters.value = vs.columnFilters || {}
      }
      if (vs.fuzzyFilters) {
        fuzzyFilters.value = vs.fuzzyFilters || {}
      }
    }
  } catch { /* 无配置则忽略 */ }

  // 所有数据并行加载
  await Promise.all([
    loadProject(),
    loadCustomFields(),
    loadPools(),
    loadRequirements(),
  ])
  // 首次全量加载时计算列宽
  computeColumnWidths()
  // 异步加载全量筛选统计数据
  getReqFilterStats(projectId).then(stats => { filterStats.value = stats }).catch(() => {})
  // 使用 ResizeObserver 监听表格容器尺寸变化
  if (tableInnerRef.value) {
    resizeObserver = new ResizeObserver(() => {
      requestAnimationFrame(() => calcTableHeight())
    })
    resizeObserver.observe(tableInnerRef.value)
    // 初始计算（下一个 tick 确保 DOM 就绪）
    await nextTick()
    calcTableHeight()
  }
})

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect()
  // 清空防抖定时器，避免组件卸载后写入旧数据
  if (saveColWidthsTimer) {
    clearTimeout(saveColWidthsTimer)
    saveColWidthsTimer = null
  }
})
</script>

<style scoped>
.requirement-page { width: 100%; flex: 1; min-height: 0; display: flex; flex-direction: column; min-width: 0; }
.req-top-section { flex-shrink: 0; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px; }
.page-header h2 { font-size: 20px; font-weight: 600; }
.header-actions { display: flex; gap: 8px; }
.filter-bar { display: flex; gap: 10px; align-items: center; margin-bottom: 16px; flex-wrap: wrap; }
.req-table { cursor: pointer; user-select: none; }
.req-table .el-table__body-wrapper .el-table__body .el-table__row {
  height: 42px !important;
  overflow: hidden;
}
.req-table .el-table__body-wrapper .el-table__body .el-table__row td {
  padding: 0 8px !important;
  height: 42px !important;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.req-table .el-table__row:hover { background: #f5f4fe !important; }
.req-title-cell { font-weight: 500; color: #2c2c2a; display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.id-cell { font-size: 12px; color: #888; font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.id-link { font-size: 12px; font-family: monospace; color: #534ab7; text-decoration: none; cursor: pointer; }
.id-link:hover { color: #7b6fd6; text-decoration: underline; }
.cf-value { font-size: 12px; color: #555; }
.date-cell { font-size: 12px; color: #555; white-space: nowrap; }
.cf-text-cell {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cf-link {
  color: #409eff;
  text-decoration: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
  display: inline-block;
  vertical-align: middle;
}
.cf-link:hover {
  color: #66b1ff;
  text-decoration: underline;
}
.pool-tag-plain {
  background-color: #fff !important;
  border-width: 1px;
  border-style: solid;
}
.multi-dropdown-value { display: inline-flex; gap: 3px; flex-wrap: nowrap; overflow: hidden; max-width: 100%; vertical-align: middle; }
.batch-progress-overlay {
  position: fixed;
  bottom: 60px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2000;
}
.batch-progress-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 24px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.batch-progress-text {
  font-size: 13px;
  color: #555;
  white-space: nowrap;
}
.multi-dropdown-value .multi-tag { margin: 0; }
.option-label { display: inline-flex; align-items: center; gap: 6px; }
.option-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
.text-muted { color: #bbb; }
.pagination-bar {
  flex-shrink: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 16px;
  background: #fff;
  border-top: 1px solid #ebeef5;
  overflow: hidden;
}
.filter-total-tip {
  font-size: 12px;
  color: #909399;
  margin-right: auto;
}

/* 筛选条件标签栏 */
.filter-chips-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}
.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  background: #e8e6fb;
  border: 1px solid #c8c3f0;
  border-radius: 4px;
  padding: 3px 8px;
  font-size: 13px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.filter-chip:hover {
  opacity: 0.75;
}
.filter-chip-label {
  color: #534ab7;
  font-weight: 500;
}
.filter-chip-sep {
  color: #999;
  margin: 0 1px;
}
.filter-chip-value {
  color: #2c2c2a;
}
.filter-chip-close {
  font-size: 12px;
  color: #999;
  margin-left: 2px;
}
.filter-chip-close:hover {
  color: #e24b4a;
}
.filter-clear-all {
  font-size: 12px;
}
.fuzzy-chip {
  background: #fff3e0;
  border-color: #ffcc80;
}
.fuzzy-chip .filter-chip-label {
  color: #e65100;
}

.sortable-header { cursor: pointer; user-select: none; display: inline-flex; align-items: center; gap: 4px; }
.sort-indicator { display: inline-flex; align-items: center; gap: 1px; position: relative; }
.sort-icon { font-size: 13px; color: #bbb; }
.sort-icon.active { color: #534ab7; }
.sort-rank { font-size: 10px; font-weight: 600; color: #534ab7; position: absolute; bottom: -4px; right: -8px; }
:deep(.el-table .selected-cell) { background-color: #e8e6fb !important; }
.cell-edit-dialog .el-dialog__title { font-size: 15px; max-width: 340px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: inline-block; vertical-align: middle; }
.cell-edit-form .el-form-item { margin-bottom: 0; }
.cell-edit-form .el-input-number { width: 100%; }
.cell-edit-form .el-input-number .el-input__inner { text-align: left; }
.import-upload-area { display: flex; flex-direction: column; align-items: center; padding: 24px; border: 2px dashed #dcdfe6; border-radius: 8px; }
.import-mapping-row { display: flex; align-items: center; margin-bottom: 8px; }
.import-mapping-label { min-width: 100px; font-size: 13px; font-weight: 500; color: #2c2c2a; }
.import-new-field { display: inline-flex; gap: 6px; margin-left: 8px; }

/* 列宽拖动滑块：加宽触发区域 + 两列之间可视化 grip 指示 */
:deep(.el-table__column-resize-handle) {
  width: 10px !important;
  cursor: col-resize;
  z-index: 3;
}
:deep(.el-table__header-wrapper .el-table__header th) {
  position: relative;
  white-space: nowrap;
}
:deep(.el-table__header-wrapper .el-table__header th:not(:last-child):hover)::after {
  content: '';
  position: absolute;
  right: -4px;
  top: 50%;
  transform: translateY(-50%);
  width: 5px;
  height: 26px;
  background: #b0b8c4;
  border-radius: 3px;
  pointer-events: none;
  opacity: 0.7;
}

/* ── 列筛选 ── */
.th-with-filter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: 100%;
}
.filter-icon {
  font-size: 14px;
  color: #bbb;
  cursor: pointer;
  flex-shrink: 0;
  transition: color 0.15s;
  line-height: 1;
}
.filter-icon:hover {
  color: #606266;
}
.filter-icon.active {
  color: #409eff;
}
.filter-options-list {
  max-height: 260px;
  overflow-y: auto;
  margin-bottom: 8px;
}
.filter-option-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  cursor: pointer;
  font-size: 13px;
}
.filter-option-row:hover {
  background: #f5f7fa;
}
.filter-opt-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.filter-opt-count {
  color: #aaa;
  font-size: 12px;
  flex-shrink: 0;
}
.filter-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #eee;
  padding-top: 8px;
}
.filter-action-btns {
  display: flex;
  gap: 4px;
}
/* ── 列筛选面板 ── */
.filter-overlay {
  position: fixed;
  inset: 0;
  z-index: 9998;
  background: transparent;
}
.filter-panel-wrap {
  position: fixed;
  z-index: 9999;
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0,0,0,.12);
  width: 240px;
  max-height: 340px;
  display: flex;
  flex-direction: column;
  padding: 8px 0;
  font-size: 13px;
}
.filter-search-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 8px 8px;
  border-bottom: 1px solid #eee;
}
.filter-search-input {
  flex: 1;
  min-width: 0;
}
.filter-mode-btn {
  flex-shrink: 0;
  font-size: 12px;
  padding: 5px 8px;
}
.filter-mode-btn.active {
  color: #fff;
  background-color: #534ab7;
  border-color: #534ab7;
}
.filter-options {
  flex: 1;
  overflow-y: auto;
  min-height: 40px;
}
.filter-opt-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  cursor: pointer;
}
.filter-opt-row:hover {
  background: #f5f7fa;
}
.filter-opt-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.filter-opt-count {
  flex-shrink: 0;
  font-size: 11px;
  color: #aaa;
  min-width: 20px;
  text-align: right;
}
.dt-row { font-size: 12px; }
.dt-toggle {
  width: 14px;
  font-size: 10px;
  color: #888;
  cursor: pointer;
  user-select: none;
  flex-shrink: 0;
  text-align: center;
  line-height: 1;
}
.filter-empty {
  color: #999;
  font-size: 12px;
  text-align: center;
  padding: 16px 0;
}
.filter-actions-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px 0;
  border-top: 1px solid #eee;
}
.filter-btn-group {
  display: flex;
  gap: 4px;
}
</style>
