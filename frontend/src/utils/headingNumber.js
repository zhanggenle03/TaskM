// 标题多级编号工具（任务沟通编辑器/只读展示用，与任务导出内容标题编号一致）
// 一级「1」、二级「1.1」、三级「(1)」，编号后统一空格
// 注意：需求编辑器（RequirementDetail.vue）仍用「一、/1.1/(1)」，为其私有逻辑，不在此处。
// 仅用于显示，不随 HTML 入库；每次渲染后传入容器重算即可。

// 遍历容器内 h1/h2/h3，写入 data-heading-num（仅显示）
export const updateHeadingNumbers = (container) => {
  container = container || document.querySelector('.w-e-text-container [data-slate-editor]')
  if (!container) return
  const hs = container.querySelectorAll('h1, h2, h3')
  let c1 = 0, c2 = 0, c3 = 0
  hs.forEach((el) => {
    const lv = Number(el.tagName[1])
    if (lv === 1) { c1 += 1; c2 = 0; c3 = 0; el.dataset.headingNum = `${c1} ` }
    else if (lv === 2) { c2 += 1; c3 = 0; el.dataset.headingNum = `${c1}.${c2} ` }
    else { c3 += 1; el.dataset.headingNum = `(${c3}) ` }
  })
}
