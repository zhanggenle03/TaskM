/**
 * 中国节假日/调休/农历/传统节日数据工具
 * 数据来源：
 *  - timor.tech 免费 API（https://timor.tech/api/holiday）— 法定节假日 & 调休
 *  - lunar-javascript — 农历日期 & 传统节日
 *  - 用户手动覆盖（localStorage）— 自定义微调
 */

import { Solar } from 'lunar-javascript'

const CACHE_TTL = 24 * 60 * 60 * 1000 // 24 小时
const cache = {} // { year: { 'MM-DD': { holiday, name, ... } } }
const OVERRIDE_KEY = 'taskm_holiday_overrides'
const ENTRY_DATE_KEY = 'taskm_entry_date'

// ------ 入职日期 ------

export function getEntryDate() {
  return localStorage.getItem(ENTRY_DATE_KEY) || null // "YYYY-MM-DD"
}

export function setEntryDate(dateStr) {
  if (dateStr) localStorage.setItem(ENTRY_DATE_KEY, dateStr)
  else localStorage.removeItem(ENTRY_DATE_KEY)
  syncUserSettingsToServer()
}

// ------ 节假日覆盖（localStorage + 服务端同步） ------

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
}

/**
 * 将当前覆盖和入职日期同步到服务端
 */
let _syncTimer = null
export function syncUserSettingsToServer() {
  if (_syncTimer) clearTimeout(_syncTimer)
  _syncTimer = setTimeout(() => {
    _syncTimer = null
    const overrides = getOverrides()
    const entryDate = getEntryDate()
    import('../api/index.js').then(({ updateUserSettings }) => {
      updateUserSettings({ holiday_overrides: overrides, entry_date: entryDate }).catch(() => {})
    })
  }, 500)
}

/**
 * 从服务端加载覆盖和入职日期，合并到 localStorage
 */
export async function loadUserSettingsFromServer() {
  try {
    const { getSettings } = await import('../api/index.js')
    const settings = await getSettings()
    const serverOverrides = settings.holiday_overrides || {}
    const serverEntryDate = settings.entry_date || null
    // 合并覆盖：服务端覆盖优先
    const merged = { ...getOverrides(), ...serverOverrides }
    saveOverrides(merged)
    // 入职日期：服务端有则覆盖
    if (serverEntryDate) setEntryDate(serverEntryDate)
    return { overrides: merged, entryDate: serverEntryDate }
  } catch { return null }
}

/**
 * 设置某天的覆盖状态
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
  syncUserSettingsToServer() // 异步同步到服务端
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
 * 清除指定年份的所有覆盖
 */
export function clearYearOverrides(year) {
  const overrides = getOverrides()
  for (const key of Object.keys(overrides)) {
    if (key.startsWith(year)) delete overrides[key]
  }
  saveOverrides(overrides)
  syncUserSettingsToServer()
}

/**
 * 加载指定年份的法定节假日数据
 */
export async function loadHolidayData(year) {
  if (cache[year]) return cache[year]

  // 尝试从 localStorage 读取
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

  // 从 API 获取
  try {
    const res = await fetch(`https://timor.tech/api/holiday/year/${year}`)
    const json = await res.json()
    if (json.code === 0 && json.holiday) {
      cache[year] = json.holiday
      localStorage.setItem(`taskm_holiday_${year}`, JSON.stringify({
        ts: Date.now(),
        data: json.holiday,
      }))
      return json.holiday
    }
  } catch (e) {
    console.warn('获取节假日数据失败:', e)
  }
  return null
}

/**
 * 获取指定日期的法定节假日信息（含手动覆盖）
 * @param {string} dateStr "YYYY-MM-DD"
 * @returns {{ type: 'holiday'|'workday', label: string, name: string } | null}
 */
export function getHolidayInfo(dateStr) {
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
export function getDayExtraInfo(dateStr) {
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

  return {
    lunarDate,
    lunarMonth,
    lunarDay,
    festivals,
    solarFestivals,
    badge,
    badgeType,
    override, // 'holiday'|'workday'|'normal'|'off'|null
  }
}
