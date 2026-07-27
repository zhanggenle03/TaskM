/**
 * 中国节假日/调休/农历/传统节日数据工具
 * 数据来源：
 *  - timor.tech 免费 API（https://timor.tech/api/holiday）— 法定节假日 & 调休
 *  - lunar-javascript — 农历日期 & 传统节日
 *  - 用户手动覆盖（DB + localStorage 缓存）— 自定义微调
 *
 * 覆盖数据流向：
 *   写: 前端 → localStorage（即时） + DB（异步同步）
 *   读: localStorage（同步，快速） → 回退 DB 加载
 *   首次加载: DB → localStorage
 */

import { Solar } from 'lunar-javascript'

const CACHE_TTL = 30 * 24 * 60 * 60 * 1000 // 30 天（节假日数据每年只变几次）
const cache = {} // { year: { 'MM-DD': { holiday, name, ... } } }
const OVERRIDE_KEY = 'taskm_holiday_overrides'
const ENTRY_DATE_KEY = 'taskm_entry_date'

// 模块加载时同步预热：将 localStorage 中仍有效的年份缓存一次性载入内存，
// 使日历首次渲染（远早于服务端响应）即可显示正确的法定节假日徽标。
;(function primeHolidayCache() {
  for (let y = 2000; y <= 2100; y++) {
    const key = `taskm_holiday_${y}`
    const stored = localStorage.getItem(key)
    if (!stored) continue
    try {
      const parsed = JSON.parse(stored)
      if (parsed && parsed.data && Date.now() - (parsed.ts || 0) < CACHE_TTL) {
        cache[y] = parsed.data
      }
    } catch { /* ignore */ }
  }
})()

// 缓存：一次解析后的覆盖数据（按年份分组），避免重复 JSON.parse
let _parsedOverrides = null
let _parsedOverridesYear = null

// ------ 入职日期 ------

export function getEntryDate() {
  return localStorage.getItem(ENTRY_DATE_KEY) || null // "YYYY-MM-DD"
}

export function setEntryDate(dateStr) {
  if (dateStr) localStorage.setItem(ENTRY_DATE_KEY, dateStr)
  else localStorage.removeItem(ENTRY_DATE_KEY)
  syncUserSettingsToServer()
}

// ------ 节假日覆盖（localStorage + 数据库同步） ------

/**
 * 获取所有用户手动覆盖的日期
 * @returns {Record<string, 'holiday'|'workday'|'normal'|'off'>}
 */
function getOverrides() {
  try {
    return JSON.parse(localStorage.getItem(OVERRIDE_KEY) || '{}')
  } catch { return {} }
}

function saveOverrides(overrides) {
  localStorage.setItem(OVERRIDE_KEY, JSON.stringify(overrides))
  _parsedOverrides = null // 清空解析缓存
}

/**
 * 从数据库加载指定年份的覆盖，合并到 localStorage（内部使用）
 */
async function loadOverridesFromDb(year) {
  try {
    const { getHolidayOverrides } = await import('../api/index.js')
    const rows = await getHolidayOverrides(year)
    if (!rows || !rows.length) return
    const overrides = getOverrides()
    let changed = false
    for (const row of rows) {
      const dateStr = row.date ? row.date.slice(0, 10) : null
      if (dateStr) {
        overrides[dateStr] = row.override_type
        changed = true
      }
    }
    if (changed) saveOverrides(overrides)
  } catch { /* 静默失败，保留 localStorage 已有数据 */ }
}

/**
 * 从数据库加载所有覆盖（跨年），合并到 localStorage
 */
export async function loadAllOverridesFromDb() {
  try {
    const { getHolidayOverrides } = await import('../api/index.js')
    const rows = await getHolidayOverrides()
    if (!rows || !rows.length) return
    const overrides = getOverrides()
    let changed = false
    for (const row of rows) {
      const dateStr = row.date ? row.date.slice(0, 10) : null
      if (dateStr) {
        overrides[dateStr] = row.override_type
        changed = true
      }
    }
    if (changed) saveOverrides(overrides)
    return rows
  } catch { return null }
}


/**
 * 将入职日期同步到服务端（settings.json）
 */
let _syncTimer = null
export function syncUserSettingsToServer() {
  if (_syncTimer) clearTimeout(_syncTimer)
  _syncTimer = setTimeout(() => {
    _syncTimer = null
    const entryDate = getEntryDate()
    import('../api/index.js').then(({ updateUserSettings }) => {
      updateUserSettings({ entry_date: entryDate }).catch(() => {})
    })
  }, 500)
}

/**
 * 从服务端加载覆盖和入职日期，合并到 localStorage
 * 同时也会从数据库加载覆盖数据（增量合并）
 */
export async function loadUserSettingsFromServer() {
  try {
    const { getSettings, getHolidayOverrides } = await import('../api/index.js')
    // 并行：从 settings.json 和 DB 同时加载
    const [settings, dbRows] = await Promise.all([
      getSettings(),
      getHolidayOverrides().catch(() => null),
    ]).catch(() => [null, null])

    let merged

    // 从 settings.json 合并
    if (settings) {
      const serverOverrides = settings.holiday_overrides || {}
      const serverEntryDate = settings.entry_date || null
      merged = { ...getOverrides(), ...serverOverrides }
      if (serverEntryDate) setEntryDate(serverEntryDate)
    } else {
      merged = getOverrides()
    }

    // 从数据库合并（DB 数据优先于 settings.json）
    if (dbRows && dbRows.length) {
      for (const row of dbRows) {
        const dateStr = row.date ? row.date.slice(0, 10) : null
        if (dateStr) {
          merged[dateStr] = row.override_type
        }
      }
    }

    saveOverrides(merged)
    return { overrides: merged, entryDate: settings?.entry_date || null }
  } catch { return null }
}

/**
 * 设置某天的覆盖状态（同步：localStorage + 异步：DB）
 * @param {string} dateStr "YYYY-MM-DD"
 * @param {'holiday'|'workday'|'normal'|'off'|null} type — null 表示清除覆盖
 */
export function setHolidayOverride(dateStr, type) {
  const overrides = getOverrides()
  if (type === null || type === undefined) {
    delete overrides[dateStr]
  } else {
    overrides[dateStr] = type
  }
  saveOverrides(overrides)
  // 同步到数据库
  import('../api/index.js').then(({ setHolidayOverride: setDb, deleteHolidayOverrides: delDb }) => {
    if (type === null) {
      delDb([dateStr]).catch(() => {})
    } else {
      setDb({ date: dateStr, override_type: type }).catch(() => {})
    }
  })
}

/**
 * 获取某天的覆盖状态
 * @param {string} dateStr "YYYY-MM-DD"
 * @returns {'holiday'|'workday'|'normal'|'off'|null}
 */
export function getHolidayOverride(dateStr) {
  const overrides = getOverrides()
  return overrides[dateStr] || null
}

/**
 * 获取所有覆盖数据，供设置页使用
 * @returns {Record<string, 'holiday'|'workday'|'normal'|'off'>}
 */
export function getAllOverrides() {
  return getOverrides()
}

/**
 * 获取指定年份的解析后覆盖数据（按MM-DD索引），避免重复 JSON.parse
 */
function getYearOverridesIndexed(year) {
  if (_parsedOverrides && _parsedOverridesYear === year) {
    return _parsedOverrides
  }
  const all = getOverrides()
  const indexed = {}
  for (const [dateStr, type] of Object.entries(all)) {
    if (dateStr.startsWith(year)) {
      indexed[dateStr.slice(5)] = type
    }
  }
  _parsedOverrides = indexed
  _parsedOverridesYear = year
  return indexed
}

/**
 * 从服务端缓存加载某年法定节假日数据（应用启动即已预取）
 */
async function loadHolidayFromServer(year) {
  try {
    const { getHolidays } = await import('../api/index.js')
    const res = await getHolidays(year)
    return res && res.holiday ? res.holiday : null
  } catch {
    return null
  }
}

/**
 * 持久化某年数据到 localStorage（便于离线 / 下次秒开）
 */
function persistHoliday(year, data) {
  try {
    localStorage.setItem(`taskm_holiday_${year}`, JSON.stringify({ ts: Date.now(), data }))
  } catch { /* ignore */ }
}

/**
 * 加载指定年份的法定节假日数据
 * 取数顺序：内存缓存 → 服务端缓存（应用启动即预取）→ localStorage → 直连 timor.tech（带超时兜底）
 * 任何外部请求都设置了超时，绝不永久卡住 UI。
 */
export async function loadHolidayData(year) {
  if (cache[year]) return cache[year]

  // 1) 服务端缓存（最快，通常应用启动后已就绪）
  try {
    const fromServer = await loadHolidayFromServer(year)
    if (fromServer) {
      cache[year] = fromServer
      persistHoliday(year, fromServer)
      return fromServer
    }
  } catch (e) {
    console.warn('从服务端加载节假日失败，回退本地缓存:', e)
  }

  // 2) localStorage 缓存
  const stored = localStorage.getItem(`taskm_holiday_${year}`)
  if (stored) {
    try {
      const parsed = JSON.parse(stored)
      if (Date.now() - parsed.ts < CACHE_TTL) {
        cache[year] = parsed.data
        return parsed.data
      }
    } catch { /* ignore */ }
  }

  // 3) 直连 timor.tech（带 6s 超时兜底，失败则放弃，保留周末推断）
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 6000)
    const res = await fetch(`https://timor.tech/api/holiday/year/${year}`, { signal: controller.signal })
    clearTimeout(timer)
    const json = await res.json()
    if (json.code === 0 && json.holiday) {
      cache[year] = json.holiday
      persistHoliday(year, json.holiday)
      return json.holiday
    }
  } catch (e) {
    console.warn('获取节假日数据失败（已超时/放弃）:', e)
  }
  return null
}

/**
 * 获取指定日期的法定节假日信息（含手动覆盖）
 * @param {string} dateStr "YYYY-MM-DD"
 * @returns {{ type: 'holiday'|'workday', label: string, name: string } | null}
 */
function getHolidayInfo(dateStr) {
  // 手动覆盖优先
  const override = getHolidayOverride(dateStr)
  if (override === 'holiday') return { type: 'holiday', label: '假', name: '自定义假日' }
  if (override === 'workday') return { type: 'workday', label: '班', name: '自定义调休' }
  if (override === 'normal') return null // 强制普通工作日
  if (override === 'off') return null    // 强制休息

  // 从 API 数据获取
  const mmdd = dateStr.slice(5)
  const year = dateStr.slice(0, 4)
  const data = cache[year]
  if (!data || !data[mmdd]) return null

  const info = data[mmdd]
  if (info.holiday) {
    return { type: 'holiday', label: '假', name: info.name }
  }
  return { type: 'workday', label: '班', name: info.name }
}

/**
 * 获取指定日期完整的农历+节日信息
 */
// 农历/节日计算记忆化：同一天只算一次（避免切月首次访问某月时同步重算导致卡顿）
const _dayExtraCache = {}
export function getDayExtraInfo(dateStr) {
  if (_dayExtraCache[dateStr]) return _dayExtraCache[dateStr]
  const [y, m, d] = dateStr.split('-').map(Number)
  const solar = Solar.fromYmd(y, m, d)
  const lunar = solar.getLunar()

  const lunarMonth = lunar.getMonthInChinese()
  const lunarDay = lunar.getDayInChinese()
  const lunarDate = `${lunarMonth}月${lunarDay}`

  const festivals = [...(lunar.getFestivals() || [])]
  const solarFestivals = [...(solar.getFestivals() || [])]

  const holidayInfo = getHolidayInfo(dateStr)
  const override = getHolidayOverride(dateStr)

  let badge = null
  let badgeType = null

  if (holidayInfo) {
    if (holidayInfo.type === 'holiday') {
      badge = holidayInfo.name
      badgeType = 'holiday'
    } else {
      badge = '班'
      badgeType = 'workday'
    }
  } else if (festivals.length > 0) {
    badge = festivals[0]
    badgeType = 'festival'
  } else if (override === 'off' || new Date(y, m - 1, d).getDay() === 0 || new Date(y, m - 1, d).getDay() === 6) {
    // 休息日（周末或手动设置的休息）
    badge = '休'
    badgeType = 'off'
  }

  const result = {
    lunarDate,
    lunarMonth,
    lunarDay,
    festivals,
    solarFestivals,
    badge,
    badgeType,
    override, // 'holiday'|'workday'|'normal'|'off'|null
  }
  _dayExtraCache[dateStr] = result
  return result
}
