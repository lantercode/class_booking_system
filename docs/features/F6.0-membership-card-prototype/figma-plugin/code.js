/* F6.0 会员卡原型生成器 — Figma 开发态插件（纯 vanilla JS，无框架、无依赖）
 * ---------------------------------------------------------------------------
 * 用途：在 Figma 内一次性生成 Pages / Variables / Text&Effect Styles /
 *      带 Variant 的 Component / Screen & Overlay Frame / Prototype 反应 / 灰置占位。
 * 事实源：docs/features/F6.0-membership-card-prototype/figma-spec/*.json
 *         （tokens.json / components.json / frames.json / interactions.json）
 *         与人读版 figma-creation-guide.md §0 / §2 / §3 / §4 / §6 / §7。
 *
 * 硬约束（本插件严格遵守）：
 *  - 只「画」界面，不执行、不模拟任何业务逻辑（无预约/扣次/校验等业务规则）。
 *  - 无任何网络请求（不发起任何 HTTP 读取，无外部 URL）。
 *  - 不写入业务代码目录（apps 下的工程）；插件沙箱不读本地文件，故下方 SPEC 内嵌为常量。
 *  - 紧凑模式：Figma Starter（免费）计划 Page 上限为 3，故原 11 Page 归并为 3 组
 *    （管理端+教师端 / 学员小程序 / 可复用组件），并在文件既有 Page 上「原地重建」
 *    （复用 + 清空既有子节点），不再新建超限 Page。
 *  - Overlay 规范帧 = 9（frames.json 的 9 个）；为承接通用 ConfirmDialog / 联系方式等目标，
 *    在管理端页与小程序页各建 1 个脚手架帧 OV-CONFIRM（共 2 个），保证 reaction 不跨 Page。
 *  - Variables 在 Starter 计划不可用，createVariables 自动降级为 Color/Text/Effect Styles。
 * ---------------------------------------------------------------------------
 */

// ===== SPEC：由 figma-spec/*.json 生成（tokens.json / components.json / frames.json / interactions.json）=====
var SPEC = {
  meta: {
    feature: 'F6.0-membership-card-prototype',
    generatedFrom: 'figma-spec/*.json',
    note: '以下数据由 figma-spec/tokens.json、components.json、frames.json、interactions.json 内嵌生成'
  },

  // ---- 紧凑模式分组（Starter 免费计划 Page 上限 = 3）----
  // 原 frames.json 的 11 Page 归并为 3 组。原 00/07/08/09 四个 Page 在插件中本就不产出任何
  // Frame（F-00-* / F-Flow-* 仅在 frames.json 的 pages[].frames 列表中登记，无尺寸规格），
  // 故紧凑模式下不再占用独立 Page；组件独占 1 页，避免与 Screen/Overlay 混排。
  pageGroups: [
    { id: '01', name: '01-管理端与教师端' },
    { id: '02', name: '02-学员小程序' },
    { id: '10', name: '03-可复用组件' }
  ],
  // 原 frames.json 的 page id → 紧凑模式 page id 映射
  pageRemap: { '01': '01', '02': '01', '03': '01', '04': '02', '05': '02', '06': '01' },

  // ---- frames.json: screen_frames（19 个 Screen Frame）----
  // 19 = 原 14 + 补画「原型有但插件未画」的状态屏：
  //   P-M1c 无效课卡、P-M1d 空状态、P-M5b 预约失败、P-M6b 预约空状态、P-M10b AI 对话态
  screenFrames: [
    { id: 'P-A1', name: 'P-A1 卡产品管理', page: '01', size: '1440x900', end: 'admin-web' },
    { id: 'P-A2', name: 'P-A2 会员卡管理列表', page: '01', size: '1440x900', end: 'admin-web' },
    { id: 'P-A5', name: 'P-A5 预约管理列表', page: '03', size: '1440x900', end: 'admin-web' },
    { id: 'P-A6', name: 'P-A6 排期签到点名', page: '03', size: '1440x900', end: 'admin-web' },
    { id: 'P-M8', name: 'P-M8 首页·课程列表', page: '04', size: '375x812', end: 'miniapp' },
    { id: 'P-M9', name: 'P-M9 我的·个人中心', page: '04', size: '375x812', end: 'miniapp' },
    { id: 'P-M1', name: 'P-M1 我的会员卡列表', page: '04', size: '375x812', end: 'miniapp' },
    { id: 'P-M1c', name: 'P-M1c 我的会员卡·无效课卡', page: '04', size: '375x812', end: 'miniapp' },
    { id: 'P-M1d', name: 'P-M1d 我的会员卡·空状态', page: '04', size: '375x812', end: 'miniapp' },
    { id: 'P-M2', name: 'P-M2 卡详情+使用记录', page: '04', size: '375x812', end: 'miniapp' },
    { id: 'P-M3', name: 'P-M3 课程排期选择', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-M4', name: 'P-M4 预约确认选卡', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-M5', name: 'P-M5 预约结果页', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-M5b', name: 'P-M5b 预约失败（名额已满）', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-M6', name: 'P-M6 我的预约', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-M6b', name: 'P-M6b 我的预约·空状态', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-M10', name: 'P-M10 AI 助手', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-M10b', name: 'P-M10b AI 助手·对话态', page: '05', size: '375x812', end: 'miniapp' },
    { id: 'P-T1', name: 'P-T1 教师排期名单签到', page: '06', size: '1440x900', end: 'teacher-web' }
  ],

  // ---- frames.json: overlay_frames（10 个 Overlay Frame；尺寸已把 "auto" 落为具体值）----
  overlayFrames: [
    // 尺寸按「内容自适应」（frames.json 口径）：高度按已绘制内容 + 底部按钮区实测取值
    { id: 'P-A3', name: 'P-A3 发卡弹窗', page: '01', size: '420x340' },
    { id: 'P-A4', name: 'P-A4 卡详情弹窗', page: '02', size: '660x520' },
    { id: 'OV-PRODUCT', name: '产品新建/编辑弹窗', page: '02', size: '420x620' },
    { id: 'OV-BATCH-DELETE', name: '批量删除弹窗', page: '02', size: '420x260' },
    { id: 'OV-FREEZE', name: '冻结弹窗', page: '02', size: '420x300' },
    { id: 'OV-RENEWAL', name: '续卡提示弹窗', page: '02', size: '420x300' },
    { id: 'OV-CONFLICT', name: '冻结到期-课程冲突弹窗', page: '02', size: '480x360' },
    { id: 'OV-BATCH-CANCEL', name: '批量作废弹窗', page: '02', size: '420x320' },
    { id: 'P-M7', name: 'P-M7 取消确认弹窗', page: '05', size: '320x320' },
    { id: 'OV-CARDSEL', name: 'OV-CARDSEL 选择会员卡底部弹窗', page: '05', size: '375x460' }
  ],

  // ---- tokens.json: color（全部 color/ 键；渐变项不适用于 Figma 颜色变量，单列于 gradientNote）----
  colors: {
    'color/primary-admin': '#409EFF',
    'color/primary-miniapp': '#C9A66B',
    'color/gold-dark': '#B8956A',
    'color/gold-light': '#DBC18A',
    'color/tab-active': '#8b7355',
    'color/sidebar-admin': '#1a1a2e',
    'color/primary-teacher': '#667eea',
    'color/success': '#67C23A',
    'color/success-bg': '#F0F9EB',
    'color/warning': '#E6A23C',
    'color/warning-bg': '#FDF6EC',
    'color/danger': '#F56C6C',
    'color/danger-bg': '#FEF0F0',
    'color/info': '#909399',
    'color/info-bg': '#F4F4F5',
    'color/frozen': '#409EFF',
    'color/frozen-bg': '#ECF5FF',
    'color/bg-page': '#F5F7FA',
    'color/bg-card': '#FFFFFF',
    'color/border-base': '#DCDFE6',
    'color/border-light': '#E4E7ED',
    'color/text-primary': '#303133',
    'color/text-regular': '#606266',
    'color/text-secondary': '#909399',
    'color/text-placeholder': '#C0C4CC',
    'color/sticker-pending-bg': '#fffbe6',
    'color/sticker-pending-border': '#faad14',
    'color/sticker-pending-text': '#86592b',
    'color/sticker-confirmed-bg': '#f0f9eb',
    'color/sticker-confirmed-border': '#67c23a',
    'color/sticker-confirmed-text': '#4e7a35'
  },
  // 渐变 token（Figma 颜色变量不支持渐变，此处仅登记）
  gradientNote: {
    'color/bg-page-miniapp': 'linear-gradient(180deg,#faf6f0,#f5ede3)'
  },

  // ---- tokens.json: text ----
  textStyles: {
    'text/title': { size: 16, lineHeight: 24, weight: 600 },
    'text/body': { size: 14, lineHeight: 22, weight: 400 },
    'text/body-strong': { size: 14, lineHeight: 22, weight: 600 },
    'text/aux': { size: 12, lineHeight: 18, weight: 400 },
    'text/aux-strong': { size: 12, lineHeight: 18, weight: 500 },
    'text/number': { size: 14, lineHeight: 22, weight: 600 },
    'text/sticker-id': { size: 24, lineHeight: 28, weight: 700 },
    'text/sticker-desc': { size: 11, lineHeight: 14, weight: 400 }
  },

  // ---- tokens.json: effect ----
  effects: {
    'shadow/card': '0 2 8 rgba(0,0,0,0.06)',
    'shadow/dialog': '0 4 16 rgba(0,0,0,0.08)'
  },

  // ---- components.json: StatusBadge status_map（ACTIVE 文案分端）----
  statusMap: [
    { status: 'PENDING', label: '未激活', text: '#909399', bg: '#F4F4F5', border: '#E4E7ED' },
    { status: 'ACTIVE', label: '使用中', labelAdmin: '正常', labelMiniapp: '使用中', text: '#67C23A', bg: '#F0F9EB', border: '#E1F3D8' },
    { status: 'EXPIRED', label: '已过期', text: '#909399', bg: '#F4F4F5', border: '#E4E7ED' },
    { status: 'FROZEN', label: '已冻结', text: '#409EFF', bg: '#ECF5FF', border: '#D9ECFF' },
    { status: 'CANCELLED', label: '已作废', text: '#F56C6C', bg: '#FEF0F0', border: '#FDE2E2' },
    { status: 'EXHAUSTED', label: '已用尽', text: '#E6A23C', bg: '#FDF6EC', border: '#FAECD8', note: 'D2 占位（黄）' }
  ],

  // ---- components.json: BookingStatusBadge status_map ----
  bookingMap: [
    { status: 'BOOKED', label: '已预约', text: '#409EFF', bg: '#ECF5FF', border: '#D9ECFF' },
    { status: 'CHECKED_IN', label: '已签到', text: '#67C23A', bg: '#F0F9EB', border: '#E1F3D8' },
    { status: 'COMPLETED', label: '已完成', text: '#909399', bg: '#F4F4F5', border: '#E4E7ED' },
    { status: 'CANCELLED', label: '已取消', text: '#F56C6C', bg: '#FEF0F0', border: '#FDE2E2' }
  ],

  // ---- components.json + tokens.json: DecisionSticker 两档 tone ----
  stickers: [
    { tone: 'pending', id: 'D2', desc: '未确认 · 占位', bg: '#fffbe6', border: '#faad14', text: '#86592b', dashed: true },
    { tone: 'confirmed', id: 'D1', desc: '已确认 · 定论', bg: '#f0f9eb', border: '#67c23a', text: '#4e7a35', dashed: false }
  ],

  // ---- components.json: TabBar ----
  // ---- TabBar（唯一基准：prototype/index.html 的 TAB_DEFS / renderTabBar）----
  // 学员端底部导航 = 4 个同级 Tab：首页 / 排期 / AI 助手 / 我的。
  // AI 助手是第 3 个一级 Tab（原型如此，非悬浮入口）；图标取自 index.html 的 TAB_ICONS（SVG 矢量）。
  //   $tabbar-height: 100rpx = 50px；选中 #8b7355、未选中 #999；label 22rpx = 11px；
  //   .tab-indicator: 40rpx × 4rpx（=20px × 2px），背景 linear-gradient(90deg,#c9a66b,#d9a7b0)
  tabbar: {
    size: { w: 375, h: 50 },
    activeColor: '#8b7355',
    inactiveColor: '#999',
    indicator: '#c9a66b',
    indicator2: '#d9a7b0',
    border: '#f5f5f5',
    tabs: [
      { key: 'home', icon: 'home', label: '首页', route: '/pages/student/courses/index' },
      { key: 'schedule', icon: 'booking', label: '排期', route: '/pages/student/schedule/index' },
      { key: 'ai', icon: 'ai', label: 'AI 助手', route: '/pages/student/ai/index' },
      { key: 'profile', icon: 'profile', label: '我的', route: '/pages/student/profile/index' }
    ],
    realSource: 'prototype/index.html TAB_DEFS / TAB_ICONS（严格基准）',
    aiEntry: 'AI 助手 = 第 3 个一级 Tab（无悬浮 FAB）'
  },

  // TabBar 显示范围：P-M10/P-M10b（AI 助手整页）同样显示 TabBar 且自身选中（index.html TAB_PAGES）
  tabBarPages: { 'P-M8': 'home', 'P-M3': 'schedule', 'P-M10': 'ai', 'P-M10b': 'ai', 'P-M9': 'profile' },

  // ---- 长页拆帧（用户决策：小程序超过一屏的页面拆为「上半屏 + 滚动续帧」----
  // 首页实测内容高 1300px（含 2 个视频卡）> 可视窗口 738px（812 帧高 − 24 状态栏 − 50 TabBar），
  // 续帧 offset = 738：不重叠，承接折叠线以下的剩余内容，两帧均保留 TabBar。
  scrollSplit: {
    'P-M8': { id: 'P-M8b', name: 'P-M8b 首页·课程列表（滚动续）', page: '04', size: '375x812', offset: 738, contentH: 1300 },
    // P-M1 有效课卡 6 张：内容高 1016（原生导航栏 68 + 筛选 50 + 6 卡 + 便签）
    // offset = 678（第 5 张卡开始处）→ 续帧从第 5 张卡开始，避免卡片被折叠线切断
    'P-M1': { id: 'P-M1b', name: 'P-M1b 我的会员卡列表（滚动续）', page: '04', size: '375x812', offset: 678, contentH: 1016 }
  },

  // ---- interactions.json: connections（type=none 为禁用项，须灰置占位）----
  connections: [
    { from: 'P-A1', trigger: '行点击', to: '编辑弹窗(Overlay)', type: 'Overlay' },
    { from: 'P-A1', trigger: '「删除」按钮', to: 'ConfirmDialog', type: 'Overlay' },
    { from: 'P-A2', trigger: '「发放会员卡」按钮', to: 'P-A3', type: 'Overlay' },
    { from: 'P-A2', trigger: '卡号点击', to: 'P-A4', type: 'Overlay' },
    { from: 'P-A2', trigger: '「冻结」按钮', to: '冻结弹窗(Overlay)', type: 'Overlay' },
    { from: 'P-A2', trigger: '「解冻」按钮(无冲突)', to: 'ConfirmDialog', type: 'Overlay' },
    { from: 'P-A2', trigger: '「解冻」按钮(有冲突)', to: '冻结到期-课程冲突弹窗', type: 'Overlay' },
    { from: 'P-A2', trigger: '「作废」按钮', to: 'ConfirmDialog(danger)', type: 'Overlay' },
    { from: 'P-A2', trigger: 'D3 影响面提示', to: null, type: 'none', reason: '依赖待开发的受影响预约查询，灰置' },
    { from: 'P-A3', trigger: '「确认」按钮', to: 'P-A2', type: 'Back', note: '新卡入列，状态 PENDING' },
    { from: 'P-A3', trigger: '重复发卡', to: '续卡提示弹窗', type: 'Overlay' },
    { from: 'P-A3', trigger: '「取消」按钮', to: 'P-A2', type: 'Back' },
    { from: 'P-A4', trigger: '「查看关联预约」按钮', to: 'P-A5', type: 'Navigate To' },
    { from: 'P-A4', trigger: '「申请退款」按钮', to: null, type: 'none', reason: '依赖 F6.1，灰置(D8)' },
    { from: 'P-A5', trigger: '「点名」按钮', to: 'P-A6', type: 'Navigate To' },
    { from: 'P-A5', trigger: '「代取消」按钮', to: 'ConfirmDialog', type: 'Overlay' },
    { from: 'P-A5', trigger: '「改期/改派」按钮', to: null, type: 'none', reason: '待开发原子端点，灰置(D7)' },
    { from: 'P-A5', trigger: 'D3 警示条', to: null, type: 'none', reason: '灰置' },
    { from: 'P-A6', trigger: '「代签到」按钮', to: 'ConfirmDialog', type: 'Overlay + Change To', note: '→ CHECKED_IN；计划卡非 ACTIVE 拦截(D9)' },
    { from: 'P-A6', trigger: '「完成」按钮', to: null, type: 'Change To', note: '同 Frame → COMPLETED' },
    { from: 'P-A6', trigger: '「标记缺席」按钮', to: null, type: 'none', reason: '灰置(D5)' },
    { from: 'P-M1', trigger: '卡点击', to: 'P-M2', type: 'Navigate To' },
    { from: 'P-M1', trigger: 'PENDING 卡「立即激活」', to: null, type: 'Change To', note: '同 Frame → ACTIVE' },
    { from: 'P-M1', trigger: '「解冻」按钮', to: null, type: 'Change To', note: '同 Frame → ACTIVE / 冲突则 Overlay 提示' },
    { from: 'P-M1', trigger: '下拉刷新', to: null, type: 'Change To', note: 'loading → success' },
    { from: 'P-M2', trigger: '「去预约」按钮', to: 'P-M3', type: 'Navigate To' },
    { from: 'P-M2', trigger: '滚动到底', to: null, type: 'Change To', note: '加载更多' },
    { from: 'P-M3', trigger: '排期行点击', to: 'P-M4', type: 'Navigate To' },
    { from: 'P-M3', trigger: '满员排期按钮', to: null, type: 'none', reason: '灰置' },
    { from: 'P-M4', trigger: '点击「使用会员卡」', to: 'OV-CARDSEL', type: 'Overlay', note: '打开选卡底部弹窗' },
    { from: 'P-M4', trigger: '切卡单选', to: null, type: 'Change To', note: '余额预览联动' },
    { from: 'P-M4', trigger: '「确认预约」按钮', to: 'P-M5', type: 'Overlay + Navigate', note: 'ConfirmDialog → P-M5' },
    { from: 'P-M4', trigger: '无可用卡', to: 'EmptyState', type: 'Change To' },
    { from: 'P-M5', trigger: '「查看我的预约」按钮', to: 'P-M6', type: 'Navigate To' },
    { from: 'P-M5', trigger: '「返回首页」按钮', to: 'P-M3', type: 'Navigate To' },
    { from: 'P-M6', trigger: '「取消预约」按钮', to: 'P-M7', type: 'Overlay' },
    { from: 'P-M6', trigger: '「换卡」按钮', to: null, type: 'none', reason: '待开发原子端点，灰置(D7)' },
    { from: 'P-M6', trigger: '「联系机构」按钮', to: '联系方式弹窗', type: 'Overlay' },
    { from: 'P-M6', trigger: '「改期」按钮', to: null, type: 'none', reason: '灰置(D7)' },
    { from: 'P-M7', trigger: '「确认取消」按钮', to: 'P-M6', type: 'Back', note: '行刷新为已取消；次卡回补 +1' },
    { from: 'P-M7', trigger: '「再想想」按钮', to: 'P-M6', type: 'Back' },
    { from: 'P-T1', trigger: '「签到」按钮', to: 'ConfirmDialog', type: 'Overlay + Change To', note: '→ CHECKED_IN；计划卡非 ACTIVE 拦截(D9)' },
    { from: 'P-T1', trigger: '「完成」按钮', to: null, type: 'Change To', note: '同 Frame → COMPLETED' },
    { from: 'P-T1', trigger: '「缺席」按钮', to: null, type: 'none', reason: '灰置(D5)' },
    { from: 'P-M8', trigger: 'TabBar 项', to: 'P-M8/P-M3/P-M10/P-M9', type: 'Navigate To', note: 'Tab 切换（4 Tab：首页/排期/AI 助手/我的；多目标取首个可达 P-M8）' },
    { from: 'P-M8', trigger: '「全部课程」/课程卡/视频卡', to: null, type: 'none', reason: '真实页面存在，原型未复刻' },
    { from: 'P-M9', trigger: '「我的会员卡」入口', to: 'P-M1', type: 'Navigate To' },
    { from: 'P-M9', trigger: '「预约记录」入口', to: 'P-M6', type: 'Navigate To' },
    { from: 'P-M9', trigger: '「解绑微信」/「退出登录」', to: null, type: 'none', reason: '真实功能，原型未复刻' },
    { from: 'P-M10', trigger: '常用问题卡 / 「发送」', to: null, type: 'Change To', note: '同 Frame：加载中（三点）→ 模拟回复（本页为模拟对话，未接入真实 AI）' },
    { from: 'P-M10', trigger: '「清空」', to: null, type: 'Change To', note: '复位欢迎态（原型 aiClear 清空消息）' }
  ]
};

// ===========================================================================
// 字体：先 listAvailableFontsAsync，按候选顺序挑一个 CJK 字体，只加载 Regular/Medium/Bold
// ===========================================================================
var FONT = {
  regular: { family: 'Inter', style: 'Regular' },
  medium: { family: 'Inter', style: 'Regular' },
  bold: { family: 'Inter', style: 'Regular' }
};

async function setupFonts() {
  var list = [];
  try { list = await figma.listAvailableFontsAsync(); } catch (e) { list = []; }
  var stylesByFamily = {};
  for (var i = 0; i < list.length; i++) {
    var fam = list[i].fontName.family;
    var st = list[i].fontName.style;
    if (!stylesByFamily[fam]) stylesByFamily[fam] = [];
    if (stylesByFamily[fam].indexOf(st) < 0) stylesByFamily[fam].push(st);
  }
  var candidates = ['Noto Sans SC', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', 'Inter'];
  var family = null;
  for (var k = 0; k < candidates.length; k++) {
    if (stylesByFamily[candidates[k]] && stylesByFamily[candidates[k]].length) { family = candidates[k]; break; }
  }
  if (!family) family = 'Inter';
  if (!stylesByFamily[family]) stylesByFamily[family] = ['Regular'];
  var styles = stylesByFamily[family];

  async function loadByCandidates(cands) {
    for (var a = 0; a < cands.length; a++) {
      for (var b = 0; b < styles.length; b++) {
        if (styles[b].toLowerCase() === cands[a].toLowerCase()) {
          try { await figma.loadFontAsync({ family: family, style: styles[b] }); return { family: family, style: styles[b] }; } catch (e) { /* try next */ }
        }
      }
    }
    return null;
  }

  var regular = await loadByCandidates(['Regular', 'Book', 'Normal', 'Medium']);
  if (!regular) {
    try { await figma.loadFontAsync({ family: family, style: styles[0] }); regular = { family: family, style: styles[0] }; } catch (e2) { regular = null; }
  }
  if (!regular) {
    try { await figma.loadFontAsync({ family: 'Inter', style: 'Regular' }); regular = { family: 'Inter', style: 'Regular' }; family = 'Inter'; } catch (e3) { regular = { family: 'Inter', style: 'Regular' }; }
  }
  var medium = await loadByCandidates(['Medium', 'Semi Bold', 'SemiBold', 'Demi Bold', 'DemiBold', 'Regular']);
  if (!medium) medium = regular;
  var bold = await loadByCandidates(['Bold', 'Heavy', 'Black', 'Medium', 'Regular']);
  if (!bold) bold = regular;

  FONT = { regular: regular, medium: medium, bold: bold };
  console.log('字体：家族 = ' + regular.family + '（regular=' + regular.style + ' / medium=' + medium.style + ' / bold=' + bold.style + '）');
}

function fontNameForWeight(w) {
  if (w >= 700) return FONT.bold;
  if (w >= 500) return FONT.medium;
  return FONT.regular;
}

// ===========================================================================
// 通用工具
// ===========================================================================
// 解析颜色：支持 #rgb / #rgba / #rrggbb / #rrggbbaa / rgb() / rgba() / transparent。
// 返回 { r, g, b, a }（各通道 0..1）。
// 关键：Figma 会在写入 fills/strokes 时校验颜色通道，含 NaN 会抛错 → 整个 drawScreen 中途中断、
// 该帧只剩中断前已画的元素（表现为「原型只有标题、大片空白」）。因此 rgba()/transparent 必须解析成合法值。
function hexToRgb(hex) {
  var s = String(hex == null ? '#000000' : hex).trim().toLowerCase();
  var r = 0, g = 0, b = 0, a = 1;
  if (s === 'transparent') {
    a = 0;
  } else if (s.indexOf('rgba(') === 0 || s.indexOf('rgb(') === 0) {
    var inner = s.substring(s.indexOf('(') + 1, s.indexOf(')'));
    var parts = inner.split(',');
    r = parseFloat(parts[0]) / 255;
    g = parseFloat(parts[1]) / 255;
    b = parseFloat(parts[2]) / 255;
    if (parts.length > 3) a = parseFloat(parts[3]);
  } else {
    var h = s.replace('#', '');
    if (h.length === 3 || h.length === 4) {
      h = h.charAt(0) + h.charAt(0) + h.charAt(1) + h.charAt(1) + h.charAt(2) + h.charAt(2)
        + (h.length === 4 ? h.charAt(3) + h.charAt(3) : '');
    }
    r = parseInt(h.substring(0, 2), 16) / 255;
    g = parseInt(h.substring(2, 4), 16) / 255;
    b = parseInt(h.substring(4, 6), 16) / 255;
    if (h.length >= 8) a = parseInt(h.substring(6, 8), 16) / 255;
  }
  if (!isFinite(r)) r = 0;
  if (!isFinite(g)) g = 0;
  if (!isFinite(b)) b = 0;
  if (!isFinite(a)) a = 1;
  return { r: r, g: g, b: b, a: a };
}

function solid(hex, opacity) {
  var c = hexToRgb(hex);
  var p = { type: 'SOLID', color: { r: c.r, g: c.g, b: c.b } };
  var op = c.a * (opacity === undefined ? 1 : opacity);
  if (op < 1) p.opacity = op;
  return p;
}

// ---- 渐变工具：把 CSS linear-gradient 转成 Figma GRADIENT_LINEAR ----
// stops: [{ color:'#hex', at:0..1, a?:0..1 }]；angleDeg 采用 CSS 角度（0=向上, 90=向右, 135=右下）
function gradStop(hex, a, pos) {
  var c = hexToRgb(hex);
  return { position: pos, color: { r: c.r, g: c.g, b: c.b, a: a === undefined ? c.a : a } };
}
function cssLinearGradient(angleDeg, stops, w, h) {
  var rad = (angleDeg % 360) * Math.PI / 180;
  var vx = Math.sin(rad), vy = -Math.cos(rad);
  var L = Math.abs(w * vx) + Math.abs(h * vy);
  var sxn = (w / 2 - vx * L / 2) / w, syn = (h / 2 - vy * L / 2) / h;
  var exn = (w / 2 + vx * L / 2) / w, eyn = (h / 2 + vy * L / 2) / h;
  var a = exn - sxn, d = eyn - syn;
  var gs = [];
  for (var i = 0; i < stops.length; i++) {
    var s = stops[i];
    var at = s.at === undefined ? (stops.length > 1 ? i / (stops.length - 1) : 0) : s.at;
    gs.push(gradStop(s.color, s.a, at));
  }
  return { type: 'GRADIENT_LINEAR', gradientTransform: [[a, -d, sxn], [d, a, syn]], gradientStops: gs };
}
// 填充派发：字符串=纯色；{gradient:{angle,stops}}=线性渐变；数组=多填充叠加
function fillPaints(fill, w, h, opacity) {
  if (fill == null) return [];
  if (Array.isArray(fill)) {
    var out = [];
    for (var i = 0; i < fill.length; i++) out = out.concat(fillPaints(fill[i], w, h, opacity));
    return out;
  }
  if (typeof fill === 'string') return [solid(fill, opacity)];
  if (fill.gradient) {
    var g = cssLinearGradient(fill.gradient.angle, fill.gradient.stops, Math.max(1, w), Math.max(1, h));
    if (opacity !== undefined && opacity !== 1) {
      for (var k = 0; k < g.gradientStops.length; k++) g.gradientStops[k].color.a *= opacity;
    }
    return [g];
  }
  return [];
}

// ---- 原型渐变常量（严格取自 prototype/index.html 的 CSS linear-gradient）----
// 用法：把原本传 16 进制字符串的 fill 改成对应的 GRAD 常量对象即可（如 { fill: GRAD.goldBtn }）。
var GRAD = {
  goldBtn:       { gradient: { angle: 135, stops: [{ color: '#d4b896', at: 0 }, { color: '#c9a66b', at: 1 }] } }, // --gold-grad-btn #d4b896->#c9a66b
  goldBtnSoft:   { gradient: { angle: 135, stops: [{ color: '#e8d5b7', at: 0 }, { color: '#d4b896', at: 1 }] } }, // .pill-active/.book-btn.booked
  tabIndicator:  { gradient: { angle: 90,  stops: [{ color: '#c9a66b', at: 0 }, { color: '#d9a7b0', at: 1 }] } }, // .tab-indicator
  goldCard:      { gradient: { angle: 135, stops: [{ color: '#fdf6e9', at: 0 }, { color: '#f9edda', at: 0.3 }, { color: '#f5e6c8', at: 0.6 }, { color: '#f0d9a8', at: 1 }] } }, // .card-active
  cardGrey:      { gradient: { angle: 135, stops: [{ color: '#faf8f5', at: 0 }, { color: '#f7f3ed', at: 1 }] } }, // .card-pending/.card-used-up
  cardFrozenBg:  { gradient: { angle: 135, stops: [{ color: '#f5f7fa', at: 0 }, { color: '#eef1f5', at: 1 }] } }, // .card-frozen
  cardVoidBg:    { gradient: { angle: 135, stops: [{ color: '#f8f6f3', at: 0 }, { color: '#f3f0eb', at: 1 }] } }, // .card-expired/.card-voided
  card3d:        { gradient: { angle: 135, stops: [{ color: '#f3d9a4', at: 0 }, { color: '#e2c184', at: 0.55 }, { color: '#c9a66b', at: 1 }] } }, // .card-3d
  avatarGold:    { gradient: { angle: 135, stops: [{ color: '#c9a66b', at: 0 }, { color: '#d9a7b0', at: 1 }] } }, // .avatar-ph
  memCard:       { gradient: { angle: 135, stops: [{ color: '#fef6f0', at: 0 }, { color: '#faf0e6', at: 1 }] } }, // .mem-card
  memIc:         { gradient: { angle: 135, stops: [{ color: '#c9a66b', at: 0, a: 0.2 }, { color: '#d9a7b0', at: 1, a: 0.15 }] } }, // .mem-card .mem-ic
  menuIc:        { gradient: { angle: 135, stops: [{ color: '#fef6f0', at: 0, a: 0.8 }, { color: '#faf0e6', at: 1, a: 0.6 }] } }, // .menu-ic
  logoutIc:      { gradient: { angle: 135, stops: [{ color: '#e74c3c', at: 0, a: 0.1 }, { color: '#e74c3c', at: 1, a: 0.05 }] } }, // .menu-ic.logout-icon
  memberBadge:   { gradient: { angle: 135, stops: [{ color: '#c9a66b', at: 0, a: 0.15 }, { color: '#d9a7b0', at: 1, a: 0.12 }] } }, // .membership-badge
  bannerBg:      { gradient: { angle: 135, stops: [{ color: '#2d2418', at: 0 }, { color: '#6b5138', at: 0.55 }, { color: '#3a2c1e', at: 1 }] } }, // BASE_BANNERS[0].bg
  bannerOverlay: { gradient: { angle: 135, stops: [{ color: '#1e1610', at: 0, a: 0.75 }, { color: '#1e1610', at: 0.5, a: 0.4 }, { color: '#1e1610', at: 1, a: 0.1 }] } }, // .banner-overlay
  teacherAvatar: { gradient: { angle: 135, stops: [{ color: '#f5e6d3', at: 0 }, { color: '#e8d5c4', at: 1 }] } }, // .teacher-avatar
  courseImage:   { gradient: { angle: 135, stops: [{ color: '#2d2418', at: 0 }, { color: '#5a4632', at: 1 }] } }, // .course-image
  videoCover:    { gradient: { angle: 135, stops: [{ color: '#1a1612', at: 0 }, { color: '#2d2418', at: 1 }] } }, // .video-cover
  videoOverlay:  { gradient: { angle: 180, stops: [{ color: '#000000', at: 0, a: 0.1 }, { color: '#000000', at: 1, a: 0.4 }] } }, // .video-overlay
  pageBg:        { gradient: { angle: 180, stops: [{ color: '#faf6f0', at: 0 }, { color: '#f5ede3', at: 1 }] } }, // .stu-frame/.ai-page
  profileBg:     { gradient: { angle: 180, stops: [{ color: '#fef6f0', at: 0 }, { color: '#faf5f0', at: 0.5 }, { color: '#f8f2ed', at: 1 }] } }, // .profile-page
  timeSection:   { gradient: { angle: 180, stops: [{ color: '#e8d5b7', at: 0, a: 0.3 }, { color: '#d4b896', at: 1, a: 0.15 }] } }, // .schedule-time-section
  timeDivider:   { gradient: { angle: 180, stops: [{ color: '#c9a66b', at: 0 }, { color: '#c9a66b', at: 1, a: 0.3 }] } }, // .time-divider
  tagRegular:    { gradient: { angle: 135, stops: [{ color: '#c8b4dc', at: 0, a: 0.4 }, { color: '#b4a0c8', at: 1, a: 0.2 }] } }, // .course-type-tag
  tagPrivate:    { gradient: { angle: 135, stops: [{ color: '#e8d5b7', at: 0, a: 0.5 }, { color: '#d4b896', at: 1, a: 0.3 }] } }, // .tag-private
  tagSpecial:    { gradient: { angle: 135, stops: [{ color: '#b4dcc8', at: 0, a: 0.4 }, { color: '#a0c8b4', at: 1, a: 0.2 }] } }, // .tag-special
  headerLine:    { gradient: { angle: 90,  stops: [{ color: '#c9a66b', at: 0, a: 0.35 }, { color: '#c9a66b', at: 1, a: 0 }] } }, // .header-line
  tchHead:       { gradient: { angle: 135, stops: [{ color: '#667eea', at: 0 }, { color: '#764ba2', at: 1 }] } }, // teacher .tch-head / admin .logo .ic
  tchBody:       { gradient: { angle: 180, stops: [{ color: '#fef5f9', at: 0 }, { color: '#f0f2ff', at: 0.3 }, { color: '#f5f7fa', at: 1 }] } }, // teacher .tch-body
  adminBtn:      { gradient: { angle: 135, stops: [{ color: '#409eff', at: 0 }, { color: '#3a8ee6', at: 1 }] } } // admin .btn-primary
};

function makeText(chars, size, weight, colorHex) {
  var t = figma.createText();
  t.fontName = fontNameForWeight(weight);
  t.characters = String(chars);
  t.fontSize = size;
  if (colorHex) t.fills = [solid(colorHex)];
  return t;
}

function sizeW(s) { return parseFloat(String(s).split('x')[0]) || 400; }
function sizeH(s) { return parseFloat(String(s).split('x')[1]) || 300; }

// ===========================================================================
// 1) 紧凑模式：Page 数 ≤ 3（Starter 上限）
//    策略：优先「复用」文件既有 Page（原地清空重建），仅在既有页不足 3 个时才 createPage，
//    因此绝不会触发 "The Starter plan only comes with 3 pages" 报错。
// ===========================================================================
function preparePages() {
  var defs = SPEC.pageGroups;
  var pageById = {};
  var stage = 'init'; // 出错时用于定位具体阶段（随错误一并抛出）
  try {
    stage = 'read-pages';
    var existing = figma.root.children.slice(); // PageNode[]

    stage = 'rename-loop';
    for (var i = 0; i < defs.length; i++) {
      var pg;
      if (i < existing.length) {
        pg = existing[i]; // 复用既有 Page
        // 原地重建：清空该 Page 上次运行遗留的子节点，避免脏数据叠加
        var kids = pg.children.slice();
        for (var k = 0; k < kids.length; k++) {
          try { kids[k].remove(); } catch (e) { /* 忽略个别节点删除失败 */ }
        }
      } else {
        pg = figma.createPage(); // 仅在既有 Page 不足时才新建
      }
      pg.name = defs[i].name;
      pageById[defs[i].id] = pg;
    }

    // 既有 Page 多于 3 个时（正常 Starter 不会发生）尝试移除多余页
    stage = 'remove-extra';
    for (var x = defs.length; x < existing.length; x++) {
      try { existing[x].remove(); } catch (e) { console.warn('多余 Page 移除失败（可忽略）：' + (e && e.message ? e.message : e)); }
    }

    // 切换当前页：非关键步骤。部分版本/受限场景可能不允许赋值，
    // 失败不影响后续（所有节点均通过 appendChild 显式落到目标 Page），故此处吞掉异常。
    stage = 'set-current';
    try { figma.currentPage = pageById[defs[0].id]; }
    catch (e) { console.warn('currentPage 切换失败（可忽略，不影响产出）：' + (e && e.message ? e.message : e)); }

    stage = 'log';
    console.log('紧凑模式：Page 数 = ' + defs.length + '（既有 ' + existing.length + '，新建 ' + Math.max(0, defs.length - existing.length) + '）≤ Starter 上限 3。');
    return pageById;
  } catch (e) {
    // 抛错时带上阶段标签，让上层 toast 直接显示真正原因
    throw new Error('[preparePages@' + stage + '] ' + (e && e.message ? e.message : String(e)));
  }
}

// ===========================================================================
// 2) Variables（color/*）；不可用时降级为 Color Styles
// ===========================================================================
function createVariables(colors) {
  var names = Object.keys(colors);
  var canUseVariables = !!(figma.variables && figma.variables.createVariableCollection && figma.variables.createVariable);
  if (canUseVariables) {
    try {
      var coll = figma.variables.createVariableCollection('F6.0 Design Tokens');
      var modeId = coll.modes[0].modeId;
      for (var i = 0; i < names.length; i++) {
        var v = figma.variables.createVariable(names[i], coll, 'COLOR');
        v.setValueForMode(modeId, hexToRgb(colors[names[i]]));
      }
      console.log('Variables 创建成功：' + names.length + ' 个 color/ 变量。');
      return { degraded: false, count: names.length };
    } catch (e) {
      console.warn('Variables 创建失败，降级为 Color Styles：' + (e && e.message ? e.message : e));
    }
  } else {
    console.warn('figma.variables 不可用（可能无付费席位）→ 降级为 Color Styles。');
  }
  // 降级路径：Color Styles
  for (var j = 0; j < names.length; j++) {
    var style = figma.createPaintStyle();
    style.name = names[j];
    style.paints = [solid(colors[names[j]])];
  }
  console.log('【降级】已用 Color Styles 落地 ' + names.length + ' 个颜色（Variables 不可用）。');
  return { degraded: true, count: names.length };
}

// ===========================================================================
// 3) Text Styles + Effect Styles
// ===========================================================================
function createTextStyles() {
  var names = Object.keys(SPEC.textStyles);
  for (var i = 0; i < names.length; i++) {
    var cfg = SPEC.textStyles[names[i]];
    var ts = figma.createTextStyle();
    ts.name = names[i];
    ts.fontName = fontNameForWeight(cfg.weight);
    ts.fontSize = cfg.size;
    ts.lineHeight = { unit: 'PIXELS', value: cfg.lineHeight };
  }
  return names.length;
}

function parseShadowEffect(v) {
  var before = String(v).split('rgba')[0];
  var nums = before.trim().split(/\s+/).map(Number);
  var inner = String(v).substring(String(v).indexOf('rgba(') + 5, String(v).indexOf(')'));
  var rgba = inner.split(',').map(Number);
  return {
    type: 'DROP_SHADOW',
    color: { r: rgba[0] / 255, g: rgba[1] / 255, b: rgba[2] / 255, a: alphaOf(rgba) },
    offset: { x: nums[0] || 0, y: nums[1] || 0 },
    radius: nums[2] || 0,
    spread: 0,
    visible: true,
    blendMode: 'NORMAL'
  };
}
function alphaOf(rgba) { return rgba[3] === undefined ? 1 : rgba[3]; }
function shadowDialogEffect() { return parseShadowEffect(SPEC.effects['shadow/dialog']); }

function createEffectStyles() {
  var names = Object.keys(SPEC.effects);
  for (var i = 0; i < names.length; i++) {
    var es = figma.createEffectStyle();
    es.name = names[i];
    es.effects = [parseShadowEffect(SPEC.effects[names[i]])];
  }
  return names.length;
}

// ===========================================================================
// 4) 组件与变体（全部建在 Page 10）
// ===========================================================================
function createBadge(compName, w, h, radius, label, textHex, bgHex, borderHex) {
  var comp = figma.createComponent();
  comp.name = compName;
  comp.resize(w, h);
  comp.fills = [solid(bgHex)];
  comp.cornerRadius = radius;
  if (borderHex) { comp.strokes = [solid(borderHex)]; comp.strokeWeight = 1; }
  var t = makeText(label, 12, 500, textHex);
  comp.appendChild(t);
  t.x = Math.max(0, Math.round((w - t.width) / 2));
  t.y = Math.max(0, Math.round((h - t.height) / 2));
  return comp;
}

function createSticker(compName, st) {
  var comp = figma.createComponent();
  comp.name = compName;
  comp.resize(120, 80);
  comp.fills = [solid(st.bg)];
  comp.cornerRadius = 4;
  comp.strokes = [solid(st.border)];
  comp.strokeWeight = 1;
  if (st.dashed) comp.dashPattern = [4, 4];
  var idT = makeText(st.id, 24, 700, st.text);
  comp.appendChild(idT);
  idT.x = 10; idT.y = 6;
  var descT = makeText(st.desc, 11, 400, st.text);
  comp.appendChild(descT);
  descT.x = 10; descT.y = 44;
  return comp;
}

function createTabBar(compName, activeKey) {
  var comp = figma.createComponent();
  comp.name = compName;
  comp.resize(SPEC.tabbar.size.w, SPEC.tabbar.size.h);
  comp.fills = [solid('#FFFFFF')];
  // .tab-bar: border-top 1rpx solid #f5f5f5
  comp.strokes = [solid(SPEC.tabbar.border)];
  comp.strokeWeight = 1;
  var tabs = SPEC.tabbar.tabs;
  var slot = SPEC.tabbar.size.w / tabs.length;
  for (var i = 0; i < tabs.length; i++) {
    var isActive = tabs[i].key === activeKey;
    var color = isActive ? SPEC.tabbar.activeColor : SPEC.tabbar.inactiveColor;
    // 图标：严格取自 prototype/index.html 的 TAB_ICONS（SVG 矢量线性图标，24×24）
    var cx = Math.round(i * slot + slot / 2);
    uiIconSvg(comp, cx - 11, 6, 22, tabs[i].icon, color);
    // .tab-text: 22rpx = 11px，active 加粗
    var label = makeText(tabs[i].label, 11, isActive ? 500 : 400, color);
    comp.appendChild(label);
    label.x = Math.max(0, Math.round(cx - label.width / 2));
    label.y = 32;
    if (isActive) {
      // .tab-indicator: 40rpx × 4rpx = 20px × 2px，真实渐变 linear-gradient(90deg,#c9a66b,#d9a7b0)
      var ind = figma.createRectangle();
      ind.resize(20, 2);
      ind.fills = [cssLinearGradient(90, [{ color: SPEC.tabbar.indicator, at: 0 }, { color: SPEC.tabbar.indicator2, at: 1 }], 20, 2)];
      ind.cornerRadius = 1;
      comp.appendChild(ind);
      ind.x = cx - 10;
      ind.y = SPEC.tabbar.size.h - 2;
    }
  }
  return comp;
}

function createButtonNode(label, w, h, bgHex, textHex) {
  var f = figma.createFrame();
  f.resize(w, h);
  f.fills = [solid(bgHex)];
  f.cornerRadius = 4;
  var t = makeText(label, 14, 500, textHex);
  f.appendChild(t);
  t.x = Math.max(0, Math.round((w - t.width) / 2));
  t.y = Math.max(0, Math.round((h - t.height) / 2));
  return f;
}

function createConfirmDialog(compName, tone, platform) {
  var w = platform === 'miniapp' ? 320 : 420;
  var comp = figma.createComponent();
  comp.name = compName;
  comp.resize(w, 180);
  comp.fills = [solid('#FFFFFF')];
  comp.cornerRadius = platform === 'miniapp' ? 12 : 8;
  comp.effects = [shadowDialogEffect()];
  var title = makeText('确认操作', 16, 600, '#303133');
  comp.appendChild(title);
  title.x = 20; title.y = 20;
  var body = makeText('确定要执行该操作吗？此操作不可撤销。', 14, 400, '#606266');
  comp.appendChild(body);
  body.x = 20; body.y = 56;
  var confirmBg = tone === 'danger' ? '#F56C6C' : '#409EFF';
  var cancelBtn = createButtonNode('取消', 100, 36, '#F4F4F5', '#606266');
  comp.appendChild(cancelBtn);
  cancelBtn.x = w - 240; cancelBtn.y = 124;
  var confirmBtn = createButtonNode('确认', 100, 36, confirmBg, '#FFFFFF');
  comp.appendChild(confirmBtn);
  confirmBtn.x = w - 128; confirmBtn.y = 124;
  return comp;
}

var EMPTY_SCENE_LABELS = { no_card: '暂无会员卡', no_booking: '暂无预约', no_transaction: '暂无使用记录', no_result: '没有找到结果' };
var ERROR_CODE_LABELS = { '403': '无权限访问', '409': '数据冲突', '500': '服务异常', 'business': '业务错误' };

function createStateComponent(kind, compName, label) {
  var comp = figma.createComponent();
  comp.name = compName;
  comp.resize(200, 200);
  comp.fills = [solid('#FFFFFF')];
  var circle = figma.createEllipse();
  circle.resize(kind === 'error' ? 120 : 110, kind === 'error' ? 120 : 110);
  circle.fills = [solid(kind === 'error' ? '#F56C6C' : '#C0C4CC', kind === 'error' ? 0.15 : 1)];
  comp.appendChild(circle);
  circle.x = Math.round((200 - circle.width) / 2); circle.y = 30;
  var title = makeText(label, 14, 400, '#909399');
  comp.appendChild(title);
  title.x = Math.max(0, Math.round((200 - title.width) / 2)); title.y = 160;
  var cta = makeText(kind === 'error' ? '重试' : '去逛逛', 12, 400, '#409EFF');
  comp.appendChild(cta);
  cta.x = Math.max(0, Math.round((200 - cta.width) / 2)); cta.y = 184;
  return comp;
}

function createListItemComponent(compName, w, h, radius, lines) {
  var comp = figma.createComponent();
  comp.name = compName;
  comp.resize(w, h);
  comp.fills = [solid('#FFFFFF')];
  comp.cornerRadius = radius || 0;
  comp.strokes = [solid('#EBEEF5')];
  comp.strokeWeight = 1;
  var y = 12;
  for (var i = 0; i < lines.length; i++) {
    var t = makeText(lines[i].text, lines[i].size, lines[i].weight, lines[i].color);
    comp.appendChild(t);
    t.x = 16; t.y = y;
    y += t.height + 6;
  }
  return comp;
}

function createComponents(page) {
  var variantComponents = {};
  var sets = {};

  function finishSet(setName, comps) {
    var set = figma.combineAsVariants(comps, page);
    set.name = setName;
    sets[setName] = set;
    return set;
  }

  // ---- StatusBadge：platform(admin|miniapp) × status(6) = 12 ----
  var sbComps = [];
  var plats = ['admin', 'miniapp'];
  for (var i = 0; i < SPEC.statusMap.length; i++) {
    var s = SPEC.statusMap[i];
    for (var j = 0; j < plats.length; j++) {
      var plat = plats[j];
      // ACTIVE 文案分端：admin「正常」/ miniapp「使用中」
      var label = s.status === 'ACTIVE' ? (plat === 'admin' ? '正常' : '使用中') : s.label;
      var compName = 'platform=' + plat + ', status=' + s.status;
      var comp = createBadge(compName, 64, 24, 12, label, s.text, s.bg, s.border);
      page.appendChild(comp);
      sbComps.push(comp);
      variantComponents['StatusBadge|' + compName] = comp;
    }
  }
  finishSet('StatusBadge', sbComps);

  // ---- BookingStatusBadge：status(4) ----
  var bbComps = [];
  for (var b = 0; b < SPEC.bookingMap.length; b++) {
    var bm = SPEC.bookingMap[b];
    var bName = 'status=' + bm.status;
    var bComp = createBadge(bName, 64, 24, 12, bm.label, bm.text, bm.bg, bm.border);
    page.appendChild(bComp);
    bbComps.push(bComp);
    variantComponents['BookingStatusBadge|' + bName] = bComp;
  }
  finishSet('BookingStatusBadge', bbComps);

  // ---- DecisionSticker：tone(pending 黄 | confirmed 绿) = 2 ----
  var dsComps = [];
  for (var d = 0; d < SPEC.stickers.length; d++) {
    var st = SPEC.stickers[d];
    var dName = 'tone=' + st.tone;
    var dComp = createSticker(dName, st);
    page.appendChild(dComp);
    dComp.rotation = -2; // 轻微旋转 -2°，贴近原型
    dsComps.push(dComp);
    variantComponents['DecisionSticker|' + dName] = dComp;
  }
  finishSet('DecisionSticker', dsComps);

  // ---- TabBar：active(home|schedule|ai|profile) = 4 ----
  // 原型 prototype/index.html 的 4 个同级 Tab：首页 / 排期 / AI 助手 / 我的（AI 助手为一级 Tab，非悬浮入口）
  var tbKeys = SPEC.tabbar.tabs.map(function (x) { return x.key; });
  var tbComps = [];
  for (var t = 0; t < tbKeys.length; t++) {
    var key = tbKeys[t];
    var tName = 'active=' + key;
    var tComp = createTabBar(tName, key);
    page.appendChild(tComp);
    tbComps.push(tComp);
    variantComponents['TabBar|' + tName] = tComp;
  }
  finishSet('TabBar', tbComps);

  // ---- ConfirmDialog：tone(default|danger) = 2 ----
  var cdComps = [];
  var tones = ['default', 'danger'];
  for (var c = 0; c < tones.length; c++) {
    var cName = 'tone=' + tones[c];
    var cComp = createConfirmDialog(cName, tones[c], 'admin');
    page.appendChild(cComp);
    cdComps.push(cComp);
    variantComponents['ConfirmDialog|' + cName] = cComp;
  }
  finishSet('ConfirmDialog', cdComps);

  // ---- EmptyState：scene(4) ----
  var esComps = [];
  var scenes = Object.keys(EMPTY_SCENE_LABELS);
  for (var e = 0; e < scenes.length; e++) {
    var eName = 'scene=' + scenes[e];
    var eComp = createStateComponent('empty', eName, EMPTY_SCENE_LABELS[scenes[e]]);
    page.appendChild(eComp);
    esComps.push(eComp);
    variantComponents['EmptyState|' + eName] = eComp;
  }
  finishSet('EmptyState', esComps);

  // ---- ErrorState：code(4) ----
  var errComps = [];
  var codes = Object.keys(ERROR_CODE_LABELS);
  for (var r = 0; r < codes.length; r++) {
    var rName = 'code=' + codes[r];
    var rComp = createStateComponent('error', rName, ERROR_CODE_LABELS[codes[r]]);
    page.appendChild(rComp);
    errComps.push(rComp);
    variantComponents['ErrorState|' + rName] = rComp;
  }
  finishSet('ErrorState', errComps);

  // ---- CardListItem：platform(admin|miniapp) = 2 ----
  var clComps = [];
  var clAdmin = createListItemComponent('platform=admin', 1200, 72, 0, [
    { text: '卡号 MC-0001 · 次卡 · 学员 张三', size: 14, weight: 600, color: '#303133' },
    { text: '总 10 / 已用 3 / 剩余 7 · 有效期 2026-12-31 · 状态 正常', size: 12, weight: 400, color: '#909399' }
  ]);
  page.appendChild(clAdmin); clComps.push(clAdmin);
  variantComponents['CardListItem|platform=admin'] = clAdmin;
  var clMini = createListItemComponent('platform=miniapp', 343, 96, 8, [
    { text: '月度次卡 · 次卡', size: 14, weight: 600, color: '#303133' },
    { text: '剩余 7 / 10 次 · 有效至 2026-12-31', size: 12, weight: 400, color: '#909399' },
    { text: '状态 使用中', size: 12, weight: 500, color: '#67C23A' }
  ]);
  page.appendChild(clMini); clComps.push(clMini);
  variantComponents['CardListItem|platform=miniapp'] = clMini;
  finishSet('CardListItem', clComps);

  // ---- TransactionRow：platform(admin|miniapp) = 2 ----
  var trComps = [];
  var trAdmin = createListItemComponent('platform=admin', 1200, 48, 0, [
    { text: '2026-10-17 10:30 · CONSUME · 变动 -1 · 变动后 6 · 关联预约 BK-123 · 操作人 admin', size: 12, weight: 400, color: '#606266' }
  ]);
  page.appendChild(trAdmin); trComps.push(trAdmin);
  variantComponents['TransactionRow|platform=admin'] = trAdmin;
  var trMini = createListItemComponent('platform=miniapp', 343, 64, 8, [
    { text: '2026-10-17 · 消费', size: 12, weight: 400, color: '#909399' },
    { text: '课程 街舞基础 · 变动 -1 · 剩余 6', size: 14, weight: 600, color: '#303133' }
  ]);
  page.appendChild(trMini); trComps.push(trMini);
  variantComponents['TransactionRow|platform=miniapp'] = trMini;
  finishSet('TransactionRow', trComps);

  // ---- BookingListItem：单组件（platform=miniapp）----
  var bl = createListItemComponent('BookingListItem', 343, 88, 8, [
    { text: '街舞基础 · 2026-10-20 19:00', size: 14, weight: 600, color: '#303133' },
    { text: '已预约 · 计划卡 MC-0001', size: 12, weight: 400, color: '#909399' }
  ]);
  page.appendChild(bl);
  variantComponents['BookingListItem'] = bl;

  return { variantComponents: variantComponents, sets: sets };
}

// ===========================================================================
// 4b) 界面绘制引擎（UI primitives + 两端 Shell）
//     目标：让 19 个 Screen Frame / 12 个 Overlay Frame 呈现「中高保真」界面，
//           与 prototype/index.html 在结构、文案、配色上一致（非像素级还原）。
//     约束：只用已验证可用的 Plugin API 子集 + 绝对定位；
//           不使用 auto-layout / layoutMode / constraints；
//           所有节点显式 appendChild 到目标 Frame，坐标均为容器局部坐标。
// ===========================================================================

var UI = {
  C: {
    adminPri: '#409EFF', gold: '#C9A66B', goldD: '#B8956A', goldL: '#DBC18A',
    tabActive: '#8b7355', sidebar: '#1a1a2e', teacher: '#667eea', teacher2: '#764ba2',
    ok: '#67C23A', okBg: '#F0F9EB', okBorder: '#E1F3D8',
    warn: '#E6A23C', warnBg: '#FDF6EC', warnBorder: '#FAECD8',
    danger: '#F56C6C', dangerBg: '#FEF0F0', dangerBorder: '#FDE2E2',
    info: '#909399', infoBg: '#F4F4F5', infoBorder: '#E4E7ED',
    frozen: '#409EFF', frozenBg: '#ECF5FF', frozenBorder: '#D9ECFF',
    bgPage: '#F5F7FA', bgCard: '#FFFFFF', border: '#DCDFE6', borderL: '#EBEEF5',
    t1: '#303133', t2: '#606266', t3: '#909399', t4: '#C0C4CC',
    // 学员小程序背景对齐真实主题令牌（$bg-primary / $bg-secondary）
    goldBg: '#FAF8F5', goldBg2: '#F5F2ED'
  },
  // 学员小程序真实主题令牌（apps/miniapp/src/styles/theme/_variables.scss）
  // 与 UI.C（管理端 Element Plus 口径）分开维护，避免管理端配色被小程序口径污染
  M: {
    gold: '#C9A66B', goldD: '#B8956A', goldL: '#DBC18A',
    accent: '#D9A7B0',
    ok: '#7CB986', warn: '#D4A76A', danger: '#D4847A', info: '#8BA4B8',
    bg: '#FAF8F5', bg2: '#F5F2ED', bg3: '#EDE9E3', card: '#FFFFFF',
    t1: '#1A1A1A', t2: '#5A5248', t3: '#8E8579', t4: '#B8B0A5',
    border: 'rgba(26,26,26,0.10)', divider: 'rgba(26,26,26,0.08)',
    tabActive: '#8b7355', tabInactive: '#999', indFrom: '#c9a66b', indTo: '#d9a7b0',
    ai: '#667eea',
    source: 'apps/miniapp/src/styles/theme/_variables.scss'
  }
};

// ===========================================================================
// 图标库（SVG 矢量，stroke 占位以 "CLR" 标记，渲染时替换为实际颜色）
// 来源：prototype/index.html 的 TAB_ICONS / AI_ICONS；其余按原型 emoji 语义等价自绘。
// 用 figma.createNodeFromSvg 渲染，替代「单字圆角方块」占位，避免图标像未完成。
// ===========================================================================
var TAB_ICONS = {
  home: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 9L12 2L21 9V20C21 20.5304 20.7893 21.0391 20.4142 21.4142C20.0391 21.7893 19.5304 22 19 22H5C4.46957 22 3.96086 21.7893 3.58579 21.4142C3.21071 21.0391 3 20.5304 3 20V9Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 22V12H15V22" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  booking: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="CLR" stroke-width="1.5"/><path d="M16 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="CLR" stroke-width="1.5"/><path d="M8 14H8.01" stroke="CLR" stroke-width="2" stroke-linecap="round"/><path d="M12 14H12.01" stroke="CLR" stroke-width="2" stroke-linecap="round"/><path d="M16 14H16.01" stroke="CLR" stroke-width="2" stroke-linecap="round"/><path d="M8 18H8.01" stroke="CLR" stroke-width="2" stroke-linecap="round"/><path d="M12 18H12.01" stroke="CLR" stroke-width="2" stroke-linecap="round"/></svg>',
  ai: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="8" width="16" height="12" rx="3" stroke="CLR" stroke-width="1.5"/><circle cx="9" cy="14" r="1.5" fill="CLR"/><circle cx="15" cy="14" r="1.5" fill="CLR"/><path d="M12 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="2" r="1" fill="CLR"/><path d="M2 14H4" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M20 14H22" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M9 18H15" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  profile: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="8" r="4" stroke="CLR" stroke-width="1.5"/><path d="M20 21C20 17.134 16.4183 14 12 14C7.58172 14 4 17.134 4 21" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>'
};
var AI_ICONS = {
  robot: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="8" width="16" height="12" rx="3" stroke="CLR" stroke-width="1.5"/><circle cx="9" cy="14" r="1.5" fill="CLR"/><circle cx="15" cy="14" r="1.5" fill="CLR"/><path d="M12 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="2" r="1" fill="CLR"/><path d="M2 14H4" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M20 14H22" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M9 18H15" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  message: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 11.5C21 16.7467 16.9706 21 12 21C10.3126 21 8.73256 20.5701 7.37103 19.8127L3 21L4.18732 16.629C3.42989 15.2674 3 13.6874 3 12C3 6.75329 7.02944 2.5 12 2.5C16.9706 2.5 21 6.75329 21 11.5Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M22 2L11 13" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  lightbulb: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 21H15" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M12 3C9.23858 3 7 5.23858 7 8C7 10.0409 8.20898 11.7967 9.92901 12.6378C10.3495 12.8433 10.6458 13.2365 10.7398 13.7012L10.9289 14.6396C11.0235 15.1088 11.4364 15.4444 11.9142 15.4444H12.0858C12.5636 15.4444 12.9765 15.1088 13.0711 14.6396L13.2602 13.7012C13.3542 13.2365 13.6505 12.8433 14.071 12.6378C15.791 11.7967 17 10.0409 17 8C17 5.23858 14.7614 3 12 3Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  calendar: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="CLR" stroke-width="1.5"/><path d="M16 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M8 14H8.01" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M12 14H12.01" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M16 14H16.01" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M8 18H8.01" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M12 18H12.01" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  card: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="5" width="20" height="14" rx="2" stroke="CLR" stroke-width="1.5"/><path d="M2 10H22" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M6 15H10" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M18.5 2.50001C18.8978 2.10219 19.4374 1.87869 20 1.87869C20.5626 1.87869 21.1022 2.10219 21.5 2.50001C21.8978 2.89784 22.1213 3.4374 22.1213 4.00001C22.1213 4.56262 21.8978 5.10219 21.5 5.50001L12 15L8 16L9 12L18.5 2.50001Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  clipboard: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M16 4H18C19.1046 4 20 4.89543 20 6V20C20 21.1046 19.1046 22 18 22H6C4.89543 22 4 21.1046 4 20V6C4 4.89543 4.89543 4 6 4H8" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><rect x="8" y="2" width="8" height="5" rx="1" stroke="CLR" stroke-width="1.5"/><path d="M9 12H15" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M9 16H15" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M9 8H10" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>'
};
// 其余图标：逐条取自真实小程序 static/icons/icon-map.ts（线条 SVG）与首页 courses/index.vue 内联 SVG（实心）
var MISC_ICONS = {
  location: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 5.13 5 9C5 14.25 12 22 12 22C12 22 19 14.25 19 9C19 5.13 15.87 2 12 2Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="9" r="2.5" stroke="CLR" stroke-width="1.5"/></svg>',
  user: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="7" r="4" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  people: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="9" cy="7" r="3" stroke="CLR" stroke-width="1.5"/><path d="M3 21V19C3 16.7909 4.79086 15 7 15H11C13.2091 15 15 16.7909 15 19V21" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><circle cx="17" cy="7" r="2.5" stroke="CLR" stroke-width="1.5"/><path d="M21 21V19.5C21 17.567 19.433 16 17.5 16H16" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  homePin: '<svg viewBox="0 0 24 24" fill="CLR" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>',
  homePeople: '<svg viewBox="0 0 24 24" fill="CLR" xmlns="http://www.w3.org/2000/svg"><path d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z"/></svg>',
  homeStar: '<svg viewBox="0 0 24 24" fill="CLR" xmlns="http://www.w3.org/2000/svg"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>',
  homePlay: '<svg viewBox="0 0 24 24" fill="CLR" xmlns="http://www.w3.org/2000/svg"><path d="M8 5v14l11-7z"/></svg>',
  book: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M4 19.5C4 18.837 4.26339 18.2011 4.73223 17.7322C5.20107 17.2634 5.83696 17 6.5 17H20" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M6.5 2H20V22H6.5C5.83696 22 5.20107 21.7366 4.73223 21.2678C4.26339 20.7989 4 20.163 4 19.5V4.5C4 3.83696 4.26339 3.20107 4.73223 2.73223C5.20107 2.26339 5.83696 2 6.5 2Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="CLR" stroke-width="1.5"/><path d="M12 7V12L15 15" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  wallet: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 12V7C21 5.89543 20.1046 5 19 5H5C3.89543 5 3 5.89543 3 7V17C3 18.1046 3.89543 19 5 19H19C20.1046 19 21 18.1046 21 17V12Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M3 10H21" stroke="CLR" stroke-width="1.5"/><path d="M16 14H18" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  crown: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3L4 8L6 17H18L20 8L12 3Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 17H18" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  tag: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20.59 13.41L13.42 20.58C13.05 20.95 12.55 21.16 12.02 21.16H4C3.47 21.16 2.96 20.95 2.59 20.58C2.22 20.21 2.01 19.71 2.01 19.18V11.15C2.01 10.62 2.22 10.12 2.59 9.75L9.76 2.58C10.13 2.21 10.63 2 11.16 2H19.19C19.72 2 20.22 2.21 20.59 2.58C20.96 2.95 21.17 3.45 21.17 3.98V12.01C21.17 12.54 20.96 13.04 20.59 13.41Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7.5" cy="7.5" r="1.5" fill="CLR"/></svg>',
  'calendar-check': '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="CLR" stroke-width="1.5"/><path d="M16 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="CLR" stroke-width="1.5"/><path d="M9 16L11 18L15 14" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  heart: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20.84 4.61C20.33 4.1 19.72 3.7 19.05 3.43C18.38 3.16 17.66 3.02 16.94 3.02C16.22 3.02 15.5 3.16 14.83 3.43C14.16 3.7 13.55 4.1 13.04 4.61L12 5.65L10.96 4.61C9.93 3.58 8.53 3 7.07 3C5.61 3 4.21 3.58 3.18 4.61C2.15 5.64 1.57 7.04 1.57 8.5C1.57 9.96 2.15 11.36 3.18 12.39L4.22 13.43L12 21.21L19.78 13.43L20.82 12.39C21.33 11.88 21.73 11.27 22 10.6C22.27 9.93 22.41 9.21 22.41 8.49C22.41 7.77 22.27 7.05 22 6.38C21.73 5.71 21.33 5.1 20.84 4.61Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  'check-circle': '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="CLR" stroke-width="1.5"/><path d="M8 12L11 15L16 9" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  'calendar-empty': '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="CLR" stroke-width="1.5"/><path d="M16 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="CLR" stroke-width="1.5"/><path d="M8 14H16" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M8 18H12" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  'card-invalid': '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="5" width="20" height="14" rx="2" stroke="CLR" stroke-width="1.5"/><path d="M2 10H22" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M6 15H10" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M4 4L20 20" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  warning: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2L2 22H22L12 2Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 9V13" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M12 17H12.01" stroke="CLR" stroke-width="2" stroke-linecap="round"/></svg>',
  alert: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="10" stroke="CLR" stroke-width="1.5"/><path d="M12 8V12" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M12 16H12.01" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  wechat: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8.5 11C9.32843 11 10 10.3284 10 9.5C10 8.67157 9.32843 8 8.5 8C7.67157 8 7 8.67157 7 9.5C7 10.3284 7.67157 11 8.5 11Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15.5 11C16.3284 11 17 10.3284 17 9.5C17 8.67157 16.3284 8 15.5 8C14.6716 8 14 8.67157 14 9.5C14 10.3284 14.6716 11 15.5 11Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 13C5.68629 13 3 15.2386 3 18C3 18.5523 3.44772 19 4 19H14C14.5523 19 15 18.5523 15 18C15 15.2386 12.3137 13 9 13Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15 13C17.2091 13 19 14.7909 19 17C19 17.3682 18.9467 17.7246 18.847 18.0623" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  logout: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H9" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="16 17 21 12 16 7" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><line x1="21" y1="12" x2="9" y2="12" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  'arrow-right': '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 18L15 12L9 6" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="8" y="8" width="12" height="12" rx="2" stroke="CLR" stroke-width="1.5"/><path d="M16 8V6C16 4.89543 15.1046 4 14 4H6C4.89543 4 4 4.89543 4 6V14C4 15.1046 4.89543 16 6 16H8" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 6H5H21" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="CLR" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M10 11V17" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/><path d="M14 11V17" stroke="CLR" stroke-width="1.5" stroke-linecap="round"/></svg>'
};
// 统一图标查找：tab 图标 / AI 图标 / 通用图标
var ICONS = {};
(function () {
  var k;
  for (k in TAB_ICONS) if (TAB_ICONS.hasOwnProperty(k)) ICONS[k] = TAB_ICONS[k];
  for (k in AI_ICONS) if (AI_ICONS.hasOwnProperty(k)) ICONS[k] = AI_ICONS[k];
  for (k in MISC_ICONS) if (MISC_ICONS.hasOwnProperty(k)) ICONS[k] = MISC_ICONS[k];
})();
function iconSvg(key, color) {
  var s = ICONS[key] || ICONS.profile;
  return String(s).split('CLR').join(color || UI.C.t2);
}

// 管理端侧栏（严格对齐 prototype renderAdminSide 的四项导航；P-A5 为「待新增」灰置）
var ADMIN_NAV = [
  { id: 'P-A1', t: '卡产品管理', s: '产品模板·软删除' },
  { id: 'P-A2', t: '会员卡管理', s: '卡实例·状态·操作' },
  { id: 'P-A5', t: '预约管理', s: '待新增 · 真实项目不存在', added: true },
  { id: 'P-A6', t: '排期签到点名', s: '代签到·完成' }
];

// ---- 基元：面板 / 矩形 / 圆 / 文本 / 标签 / 徽标 / 按钮 ----
function uiPanel(parent, x, y, w, h, o) {
  o = o || {};
  var f = figma.createFrame();
  f.resize(Math.max(1, w), Math.max(1, h));
  f.fills = fillPaints(o.fill, w, h, o.fillOpacity);
  f.cornerRadius = o.radius || 0;
  try { f.clipsContent = true; } catch (e) { /* 旧版本无该属性，忽略 */ }
  if (o.stroke) { f.strokes = [solid(o.stroke)]; f.strokeWeight = o.strokeW || 1; }
  if (o.shadow) { try { f.effects = [parseShadowEffect(SPEC.effects[o.shadow])]; } catch (e2) { /* 忽略 */ } }
  if (o.name) f.name = o.name;
  if (o.opacity !== undefined) f.opacity = o.opacity;
  parent.appendChild(f);
  f.x = x; f.y = y;
  return f;
}

function uiRect(parent, x, y, w, h, o) {
  o = o || {};
  var r = figma.createRectangle();
  r.resize(Math.max(1, w), Math.max(1, h));
  r.fills = fillPaints(o.fill, w, h, o.fillOpacity);
  if (o.stroke) { r.strokes = [solid(o.stroke)]; r.strokeWeight = o.strokeW || 1; }
  if (o.radius) r.cornerRadius = o.radius;
  if (o.dashed) r.dashPattern = [4, 4];
  if (o.opacity !== undefined) r.opacity = o.opacity;
  if (o.name) r.name = o.name;
  parent.appendChild(r);
  r.x = x; r.y = y;
  return r;
}

function uiCircle(parent, x, y, d, fill, opacity) {
  var e = figma.createEllipse();
  e.resize(d, d);
  e.fills = fillPaints(fill, d, d, opacity);
  parent.appendChild(e);
  e.x = x; e.y = y;
  return e;
}

// 文本基元：o.w 给定则固定宽度自动换行（失败时降级为单行，不中断绘制）
function uiText(parent, x, y, chars, o) {
  o = o || {};
  var t = makeText(chars == null ? '' : chars, o.size || 13, o.weight || 400, o.color || UI.C.t1);
  if (o.w) {
    try { t.textAutoResize = 'HEIGHT'; t.resize(o.w, t.height); } catch (e) { /* 忽略 */ }
  }
  if (o.opacity !== undefined) t.opacity = o.opacity;
  if (o.name) t.name = o.name;
  parent.appendChild(t);
  t.x = x; t.y = y;
  return t;
}

function uiDivider(parent, x, y, w, color) {
  return uiRect(parent, x, y, w, 1, { fill: color || UI.C.borderL });
}

// 图标占位：圆角方块 + 首字（管理端沿用；学员端已改用 uiIconSvg/uiIconChip 矢量图标）
function uiIconBox(parent, x, y, s, label, o) {
  o = o || {};
  var f = uiPanel(parent, x, y, s, s, { fill: o.bg || UI.C.infoBg, radius: o.radius || 6, opacity: o.opacity });
  var t = makeText(label, o.size || Math.round(s * 0.42), 600, o.fg || '#FFFFFF');
  f.appendChild(t);
  t.x = Math.max(0, Math.round((s - t.width) / 2));
  t.y = Math.max(0, Math.round((s - t.height) / 2));
  return f;
}

// SVG 矢量图标：figma.createNodeFromSvg 渲染（替代「单字方块」占位）
function uiIconSvg(parent, x, y, size, key, color) {
  try {
    var node = figma.createNodeFromSvg(iconSvg(key, color));
    try { node.resize(size, size); } catch (eR) { /* 允许个别节点不可 resize */ }
    try { node.clipsContent = false; } catch (eC) { /* 旧版本忽略 */ }
    parent.appendChild(node);
    node.x = x; node.y = y;
    return node;
  } catch (e) {
    console.warn('图标渲染失败，降级为空白占位：' + (e && e.message ? e.message : e));
    var fb = figma.createFrame();
    try { fb.resize(Math.max(1, size), Math.max(1, size)); } catch (e2) { /* 忽略 */ }
    fb.fills = [];
    parent.appendChild(fb);
    fb.x = x; fb.y = y;
    return fb;
  }
}

// 图标胶囊：圆角底色 + 居中矢量图标（uiIconBox 的矢量版，学员端逐帧替换用）
function uiIconChip(parent, x, y, s, key, o) {
  o = o || {};
  var f = uiPanel(parent, x, y, s, s, { fill: o.bg || UI.C.infoBg, radius: o.radius || 6, opacity: o.opacity });
  var inner = o.iconSize || Math.round(s * 0.62);
  uiIconSvg(f, Math.round((s - inner) / 2), Math.round((s - inner) / 2), inner, key, o.fg || '#FFFFFF');
  return f;
}

// 标签（el-tag 风格）
function uiTag(parent, x, y, text, o) {
  o = o || {};
  var t = makeText(text, o.size || 11, 500, o.color || UI.C.t2);
  var h = o.h || 20;
  var w = Math.round(t.width) + (o.pad === undefined ? 14 : o.pad * 2);
  var f = uiPanel(parent, x, y, w, h, { fill: o.bg || UI.C.infoBg, stroke: o.border, strokeW: 1, radius: o.radius === undefined ? 4 : o.radius });
  f.appendChild(t);
  t.x = Math.round((w - t.width) / 2);
  t.y = Math.max(0, Math.round((h - t.height) / 2));
  return f;
}

// 状态徽标（带圆点，对齐 .badge / .card-status-badge）
function uiBadge(parent, x, y, text, color, bg, border) {
  var t = makeText(text, 11, 500, color);
  var h = 22;
  var w = Math.round(t.width) + 28;
  var f = uiPanel(parent, x, y, w, h, { fill: bg, stroke: border, strokeW: 1, radius: 11 });
  uiCircle(f, 9, Math.round((h - 6) / 2), 6, color);
  f.appendChild(t);
  t.x = 19; t.y = Math.round((h - t.height) / 2);
  return f;
}

// 按钮（圆角矩形 + 居中文字）
function uiBtn(parent, x, y, w, h, text, o) {
  o = o || {};
  var f = uiPanel(parent, x, y, w, h, {
    fill: o.bg || '#FFFFFF',
    stroke: o.border === undefined ? UI.C.border : o.border,
    strokeW: 1,
    radius: o.radius === undefined ? 4 : o.radius,
    opacity: o.opacity
  });
  var t = makeText(text, o.size || 12, o.weight || 500, o.fg || UI.C.t2);
  f.appendChild(t);
  t.x = Math.max(0, Math.round((w - t.width) / 2));
  t.y = Math.max(0, Math.round((h - t.height) / 2));
  return f;
}

// ---- 管理端 Shell：侧栏 200 + 页头 48 + 内容区 ----
function drawAdminShell(frame, o) {
  o = o || {};
  var W = frame.width, H = frame.height;
  var side = uiPanel(frame, 0, 0, 200, H, { fill: UI.C.sidebar, name: 'AdminSide' });
  uiIconBox(side, 18, 14, 34, '约', { bg: GRAD.tchHead, fg: '#FFFFFF', radius: 10, size: 15 });
  uiText(side, 60, 25, '约课管理', { size: 15, weight: 700, color: '#FFFFFF' });
  uiDivider(side, 0, 60, 200, '#2a2a44');
  uiText(side, 18, 74, '管理后台', { size: 11, color: '#6b6b85' });
  var y = 96;
  for (var i = 0; i < ADMIN_NAV.length; i++) {
    var it = ADMIN_NAV[i];
    var on = it.id === o.active;
    var ih = 56;
    if (on) {
      uiRect(side, 0, y, 200, ih, { fill: '#252540' });
      uiRect(side, 0, y, 3, ih, { fill: UI.C.teacher });
    }
    uiIconBox(side, 18, y + 19, 18, it.t.charAt(0), {
      bg: on ? UI.C.teacher : '#3a3a55', fg: '#FFFFFF', radius: 4, size: 11,
      opacity: it.added ? 0.5 : 1
    });
    uiText(side, 44, y + 13, it.t, { size: 13, weight: on ? 600 : 400, color: it.added ? '#8a8aa5' : (on ? '#FFFFFF' : '#a0a0b8') });
    uiText(side, 44, y + 32, it.s, { size: 10, color: '#6b6b85' });
    if (it.added) uiTag(side, 132, y + 13, '待新增', { size: 9, color: '#d0a35c', bg: '#2e2b24', border: '#5a4a2e', h: 16 });
    y += ih;
  }
  uiText(side, 18, y + 14, '弹窗 / 详情', { size: 11, color: '#6b6b85' });
  uiText(side, 18, y + 34, '发卡弹窗 P-A3 · 卡详情 P-A4', { size: 10, color: '#6b6b85' });

  var main = uiPanel(frame, 200, 0, W - 200, H, { fill: UI.C.bgPage, name: 'AdminMain' });
  uiPanel(main, 0, 0, W - 200, 48, { fill: '#FFFFFF', name: 'AdminHeader' });
  uiDivider(main, 0, 47, W - 200);
  uiText(main, 24, 15, o.title || '', { size: 15, weight: 600, color: UI.C.t1 });
  uiText(main, W - 260, 17, '桌面端 · Element Plus 风格', { size: 11, color: UI.C.t3 });
  return main; // 内容区容器：原点 = (200,48) 全局
}

// ---- 教师端 Shell：无侧栏，浅紫渐变底 + 居中 560 卡片流 ----
function drawTeacherShell(frame, o) {
  o = o || {};
  var W = frame.width, H = frame.height;
  uiRect(frame, 0, 0, W, H, { fill: GRAD.tchBody });
  uiRect(frame, 0, Math.round(H * 0.28), W, Math.round(H * 0.72), { fill: '#F5F7FA', fillOpacity: 0.85 });
  uiPanel(frame, 0, 0, W, 48, { fill: '#FFFFFF' });
  uiDivider(frame, 0, 47, W);
  uiText(frame, 24, 15, o.title || '学员列表 / 签到点名', { size: 15, weight: 600, color: UI.C.t1 });
  uiText(frame, W - 300, 17, '教师端 · 移动风卡片列表', { size: 11, color: UI.C.t3 });
  // 内容容器：居中 560
  var wrap = uiPanel(frame, Math.round((W - 560) / 2), 64, 560, H - 80, { fill: '#00000000', name: 'TeacherWrap' });
  wrap.fills = [];
  return wrap;
}

// ---- 小程序 Shell：状态栏 24 + 可选导航栏 44 + 内容区 ----
function drawMobileShell(frame, o) {
  o = o || {};
  var W = frame.width, H = frame.height;
  uiPanel(frame, 0, 0, W, H, { fill: o.bg || GRAD.pageBg, name: 'MiniBg' });
  if (o.bg2) uiPanel(frame, 0, Math.round(H / 2), W, H - Math.round(H / 2), { fill: o.bg2, opacity: 1, name: 'MiniBg2' });
  uiPanel(frame, 0, 0, W, 24, { fill: '#1f2937', name: 'StatusBar' });
  uiText(frame, 14, 5, '9:41', { size: 11, color: '#FFFFFF' });
  uiText(frame, W - 64, 5, '•• 5G ▮', { size: 11, color: '#FFFFFF' });
  var top = 24;
  if (o.nav) {
    uiPanel(frame, 0, 24, W, 44, { fill: '#FFFFFF', name: 'MiniNav' });
    uiDivider(frame, 0, 67, W, '#F2ECE4');
    if (o.back) {
      uiText(frame, 14, 38, '‹ 返回', { size: 13, color: UI.C.tabActive });
      var t = makeText(o.nav, 15, 600, '#2c1810');
      frame.appendChild(t);
      t.x = Math.round((W - t.width) / 2);
      t.y = 37;
    } else {
      uiText(frame, 16, 37, o.nav, { size: 16, weight: 600, color: '#2c1810' });
    }
    top = 68;
  }
  // 内容窗口：o.reserve 预留底部安全区（TabBar 页 = 50），避免内容被 TabBar 压住
  var win = uiPanel(frame, 0, top, W, H - top - (o.reserve || 0), { fill: '#00000000', name: 'MiniScrollWin' });
  win.fills = [];
  // 滚动层：o.offset > 0 时把整页内容整体上移，窗口只露出折叠线以下部分（"滚动续帧"）
  var content = uiPanel(win, 0, -(o.offset || 0), W, o.contentH || (H - top), { fill: '#00000000', name: 'MiniContent' });
  content.fills = [];
  return content;
}

// ===========================================================================
// 4c) 屏幕内容数据（与 prototype/index.html 的 BASE_* mock 一致，仅用于绘制）
// ===========================================================================
var D = {
  products: [
    { n: '拉丁舞次卡', ct: '次卡', ctag: 'tag-success', credits: '10', days: '90', price: '980', app: '常规课', status: '上架', scls: 'tag-success' },
    { n: '拉丁舞期限卡', ct: '期卡', ctag: 'tag-warning', credits: '-', days: '30', price: '1280', app: '常规课', status: '上架', scls: 'tag-success' },
    { n: '私教课期限卡', ct: '期卡', ctag: 'tag-warning', credits: '-', days: '30', price: '1980', app: '私教课', status: '上架', scls: 'tag-success' }
  ],
  cards: [
    { no: 'MC20261010001', prod: '拉丁舞期限卡', ct: '期卡', ctcls: 'tag-success', stu: '张小明', phone: '138****8888', total: '-', used: '-', left: '-', st: 'PENDING', range: '-', frozen: '' },
    { no: 'MC20260910002', prod: '拉丁舞次卡', ct: '次卡', ctcls: 'tag-primary', stu: '张小明', phone: '138****8888', total: '10', used: '3', left: '7', st: 'ACTIVE', range: '2026-09-10 ~ 2026-12-09', frozen: '' },
    { no: 'MC20260701003', prod: '拉丁舞次卡', ct: '次卡', ctcls: 'tag-primary', stu: '张小明', phone: '138****8888', total: '10', used: '10', left: '0', st: 'ACTIVE', range: '2026-07-01 ~ 2026-09-29', frozen: '' },
    { no: 'MC20260810004', prod: '拉丁舞期限卡', ct: '期卡', ctcls: 'tag-success', stu: '张小明', phone: '138****8888', total: '-', used: '-', left: '-', st: 'EXPIRED', range: '2026-08-10 ~ 2026-09-09', frozen: '' },
    { no: 'MC20260920005', prod: '拉丁舞次卡', ct: '次卡', ctcls: 'tag-primary', stu: '张小明', phone: '138****8888', total: '10', used: '2', left: '8', st: 'FROZEN', range: '2026-09-20 ~ 2026-12-19', frozen: '剩余 8 天解冻' },
    { no: 'MC20260901006', prod: '拉丁舞期限卡', ct: '期卡', ctcls: 'tag-success', stu: '张小明', phone: '138****8888', total: '-', used: '-', left: '-', st: 'CANCELLED', range: '2026-09-01 ~ 2026-09-30', frozen: '' }
  ],
  bookings: [
    { id: 'B1', stu: '张小明', course: '拉丁舞基础', when: '2026-10-10 19:00-20:30', st: 'BOOKED', stl: '已预约', cardNo: 'MC20260910002', cardSt: 'ACTIVE', cardStl: '正常', src: '本人', cancel: '—', act: '代取消 / 点名 / 改期' },
    { id: 'B2', stu: '张小明', course: '拉丁舞进阶', when: '2026-10-11 19:00-20:30', st: 'CANCELLED_B', stl: '已取消', cardNo: 'MC20260701003', cardSt: 'EXHAUSTED', cardStl: '已用尽', src: '本人', cancel: '临时有事', act: '点名' },
    { id: 'B3', stu: '张小明', course: '拉丁舞基础', when: '2026-10-12 10:00-11:30', st: 'BOOKED', stl: '已预约', cardNo: 'MC20260901006', cardSt: 'CANCELLED', cardStl: '已作废', src: '本人', cancel: '—', act: '人工处理 / 代取消 / 点名 / 改期' },
    { id: 'B4', stu: '张小明', course: '拉丁舞基础', when: '2026-10-08 19:00-20:30', st: 'COMPLETED', stl: '已完成', cardNo: 'MC20260910002', cardSt: 'ACTIVE', cardStl: '正常', src: '本人', cancel: '—', act: '点名' },
    { id: 'B5', stu: '张小明', course: '拉丁舞进阶', when: '2026-10-11 19:00-20:30', st: 'BOOKED', stl: '已预约', cardNo: 'MC20260910002', cardSt: 'ACTIVE', cardStl: '正常', src: '本人', cancel: '—', act: '代取消 / 点名 / 改期' }
  ],
  rosterS1: [
    { name: '张小明', st: '已预约', stc: UI.C.adminPri, stbg: UI.C.frozenBg, stbd: UI.C.frozenBorder, cardNo: 'MC20260910002', cs: '正常', csc: UI.C.ok, csbg: UI.C.okBg, time: '—', ops: '代签到 / 标记缺席' },
    { name: '陈晨', st: '已预约', stc: UI.C.adminPri, stbg: UI.C.frozenBg, stbd: UI.C.frozenBorder, cardNo: 'MC20261008008', cs: '正常', csc: UI.C.ok, csbg: UI.C.okBg, time: '—', ops: '代签到 / 标记缺席' },
    { name: '林芳', st: '已签到', stc: UI.C.ok, stbg: UI.C.okBg, stbd: UI.C.okBorder, cardNo: 'MC20261007009', cs: '正常', csc: UI.C.ok, csbg: UI.C.okBg, time: '19:02', ops: '完成 / 标记缺席' }
  ],
  rosterS3: [
    { name: '张小明', st: '已预约', stc: UI.C.adminPri, stbg: UI.C.frozenBg, stbd: UI.C.frozenBorder, cardNo: 'MC20260901006', cs: '已作废', csc: UI.C.danger, csbg: UI.C.dangerBg, time: '—', ops: '代签到 / 标记缺席' },
    { name: '周杰', st: '已完成', stc: UI.C.info, stbg: UI.C.infoBg, stbd: UI.C.infoBorder, cardNo: 'MC20261001010', cs: '正常', csc: UI.C.ok, csbg: UI.C.okBg, time: '10:05', ops: '已完成' }
  ],
  schedules: [
    { id: 'S1', course: '拉丁舞基础', ct: '常规课', date: '2026-10-10', time: '19:00-20:30', teacher: '刘老师', room: '1号厅', cap: 10, booked: 8 },
    { id: 'S2', course: '拉丁舞进阶', ct: '常规课', date: '2026-10-11', time: '19:00-20:30', teacher: '刘老师', room: '1号厅', cap: 10, booked: 5 },
    { id: 'S3', course: '拉丁舞基础', ct: '常规课', date: '2026-10-12', time: '10:00-11:30', teacher: '陈老师', room: '2号厅', cap: 10, booked: 10 },
    { id: 'S4', course: '拉丁舞基础', ct: '私教课', date: '2026-10-11', time: '10:00-11:30', teacher: '陈老师', room: '2号厅', cap: 10, booked: 2 },
    { id: 'S5', course: '拉丁舞进阶', ct: '特色课', date: '2026-10-12', time: '19:00-20:30', teacher: '刘老师', room: '1号厅', cap: 10, booked: 10 }
  ],
  // 学员端「我的会员卡」完整数据（对齐 prototype BASE_CARDS 的 U1 8 张卡）：
  //   有效区 = ACTIVE 使用中 + USED_UP 已用完 + PENDING 未激活 + FROZEN 冻结中（6 张）
  //   无效区 = EXPIRED 已过期 + CANCELLED 已作废（2 张）
  miniCards: [
    { name: '拉丁舞期限卡', no: 'MC20261010001', kind: 'PENDING', cls: 'card-pending', badge: '未激活', bc: UI.C.warn, bbg: 'rgba(255,183,77,.15)', usage: 'period-days', days: '30', begin: '首次上课后起算', range: '有效期 · 首次上课后起算', extra: 'activate', frozen: '' },
    { name: '拉丁舞次卡', no: 'MC20260910002', kind: 'ACTIVE', cls: 'card-active', badge: '使用中', bc: UI.C.ok, bbg: 'rgba(76,175,80,.12)', usage: 'credits', left: '7', total: '10', range: '有效期至 2026-12-09', extra: '', frozen: '' },
    { name: '拉丁舞次卡', no: 'MC20260701003', kind: 'USED_UP', cls: 'card-used-up', badge: '已用完', bc: '#757575', bbg: 'rgba(158,158,158,.1)', usage: 'credits', left: '0', total: '10', range: '有效期至 2026-09-29', extra: '', frozen: '' },
    { name: '拉丁舞次卡', no: 'MC20260920005', kind: 'FROZEN', cls: 'card-frozen', badge: '冻结中', bc: UI.C.frozen, bbg: 'rgba(64,158,255,.12)', usage: 'credits', left: '8', total: '10', range: '有效期至 2026-12-19', extra: 'unfreeze', frozen: '冻结至 2026-10-12 · 学员请假外出' },
    { name: '私教课期限卡', no: 'MC20261012007', kind: 'PENDING', cls: 'card-pending', badge: '未激活', bc: UI.C.warn, bbg: 'rgba(255,183,77,.15)', usage: 'period-days', days: '30', begin: '首次上课后起算', range: '有效期 · 首次上课后起算', extra: 'activate', frozen: '' },
    { name: '拉丁舞期限卡', no: 'MC20261005008', kind: 'ACTIVE', cls: 'card-active', badge: '使用中', bc: UI.C.ok, bbg: 'rgba(76,175,80,.12)', usage: 'period-days', days: '30', begin: '2026-10-05 ~ 2026-11-04', range: '有效期至 2026-11-04', extra: '', frozen: '' }
  ],
  miniCardsInvalid: [
    { name: '拉丁舞期限卡', no: 'MC20260810004', kind: 'EXPIRED', cls: 'card-expired', badge: '已过期', bc: UI.C.t3, bbg: 'rgba(144,147,153,.12)', usage: 'period-range', range: '2026-08-10 ~ 2026-09-09', extra: '', frozen: '' },
    { name: '拉丁舞期限卡', no: 'MC20260901006', kind: 'CANCELLED', cls: 'card-voided', badge: '已作废', bc: UI.C.danger, bbg: 'rgba(245,108,108,.10)', usage: 'period-range', range: '2026-09-01 ~ 2026-09-30', extra: '', frozen: '' }
  ],
  teachers: [{ n: '林老师', s: '古典舞 · 8年教龄' }, { n: '苏老师', s: '拉丁舞 · 6年教龄' }, { n: '陈老师', s: '街舞 · 5年教龄' }],
  homeCourses: [
    { n: '拉丁舞基础', d: '能力素质训练，新手小白的入门必修课' },
    { n: '中国古典舞', d: '身韵与基本功，感受东方美学韵味' },
    { n: '现代舞进阶', d: '身体开发与编舞，进阶提升表现力' }
  ],
  videos: [
    { t: '中国古典舞《身韵》基础教学', d: '学习古典舞核心身韵技巧，感受东方美学韵味', dur: '03:28' },
    { t: '拉丁舞恰恰基本步示范', d: '恰恰舞基本步分解，零基础也能跟上', dur: '05:12' }
  ]
};

// ---- 表格单元格 / 表格 ----
function uiCell(parent, x, y, w, cell) {
  if (cell == null) return;
  // 复选框：用矢量方框表达，避免 U+2610「☐」在部分中文字体中缺字（显示为豆腐块）
  if (cell.checkbox) { uiRect(parent, x, y + 1, 14, 14, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 2 }); return; }
  if (typeof cell === 'string') { uiText(parent, x, y, cell, { size: 12, color: UI.C.t1, w: w }); return; }
  if (cell.tag) { uiTag(parent, x, y - 4, cell.tag.t, { size: 10, color: cell.tag.c, bg: cell.tag.bg, border: cell.tag.bd, h: 20 }); return; }
  if (cell.badge) { uiBadge(parent, x, y - 5, cell.badge.t, cell.badge.c, cell.badge.bg, cell.badge.bd); return; }
  if (cell.stack) {
    for (var i = 0; i < cell.stack.length; i++) {
      var s = cell.stack[i];
      if (s.tag) { uiTag(parent, x, y + i * 18 - 2, s.tag.t, { size: 10, color: s.tag.c, bg: s.tag.bg, border: s.tag.bd, h: 18 }); }
      else if (s.badge) { uiBadge(parent, x, y + i * 18 - 3, s.badge.t, s.badge.c, s.badge.bg, s.badge.bd); }
      else { uiText(parent, x, y + i * 18, s.t, { size: s.size || 11, color: s.color || UI.C.t1, weight: s.weight || 400, w: w }); }
    }
    return;
  }
  uiText(parent, x, y, cell.t, { size: cell.size || 12, color: cell.color || UI.C.t1, weight: cell.weight || 400, w: w });
}

function uiTable(parent, x, y, w, cols, rows, o) {
  o = o || {};
  var headH = o.headH || 40, rowH = o.rowH || 46;
  var h = headH + rows.length * rowH;
  var panel = uiPanel(parent, x, y, w, h, { fill: UI.C.bgCard, stroke: UI.C.borderL, strokeW: 1, radius: 8, name: o.name || 'Table' });
  uiRect(panel, 0, 0, w, headH, { fill: '#F5F7FA' });
  uiDivider(panel, 0, headH - 1, w);
  var cx = 0;
  for (var i = 0; i < cols.length; i++) {
    uiText(panel, cx + 8, Math.round((headH - 14) / 2), cols[i].t, { size: 12, weight: 600, color: UI.C.t1, w: Math.max(10, cols[i].w - 16) });
    cx += cols[i].w;
  }
  for (var r = 0; r < rows.length; r++) {
    var ry = headH + r * rowH;
    if (r % 2 === 1) uiRect(panel, 0, ry, w, rowH, { fill: '#FAFAFA' });
    uiDivider(panel, 0, ry + rowH - 1, w);
    var x2 = 0;
    for (var k = 0; k < rows[r].length; k++) {
      var cw = cols[k] ? cols[k].w : 80;
      uiCell(panel, x2 + 8, ry + Math.round((rowH - 16) / 2) - (rows[r][k] && rows[r][k].stack ? 4 : 0), Math.max(10, cw - 16), rows[r][k]);
      x2 += cw;
    }
  }
  return panel;
}

// ---- 决策便签（黄=待确认 / 绿=已确认）----
function uiSticker(parent, x, y, d, text, tone) {
  // 宽度收敛到父容器可用宽度（375 宽小程序帧上不再横向溢出）；高度按估算行数自适应
  var pw = parent && typeof parent.width === 'number' ? parent.width : 560;
  var w = Math.max(240, Math.min(560, pw - x * 2));
  var cpl = Math.max(8, Math.floor((w - 96) / 11));
  var lines = Math.max(1, Math.ceil(String(text == null ? '' : text).length / cpl));
  var h = Math.max(46, 14 + lines * 16);
  var conf = tone === 'confirmed';
  var bg = conf ? '#f0f9eb' : '#fffbe6';
  var bd = conf ? '#c2e7b0' : '#ffe58f';
  var bar = conf ? '#67c23a' : '#faad14';
  var tx = conf ? '#4e7a35' : '#86592b';
  var f = uiPanel(parent, x, y, w, h, { fill: bg, stroke: bd, strokeW: 1, radius: 4, name: 'DecisionSticker D' + d });
  uiRect(f, 0, 0, 4, h, { fill: bar });
  uiText(f, 12, 7, 'D' + d, { size: 10, weight: 700, color: conf ? '#3d6b26' : '#d48806' });
  uiText(f, 36, 7, conf ? '已确认' : '决策占位', { size: 11, weight: 700, color: conf ? '#3d6b26' : '#d48806' });
  uiText(f, 84, 7, text, { size: 11, color: tx, w: w - 96 });
  return f;
}

// ---- 通用二次确认弹窗骨架 ----
function drawModal(frame, o) {
  o = o || {};
  var W = frame.width, H = frame.height;
  var headH = 50, footH = o.footH || 52;
  uiPanel(frame, 0, 0, W, H, { fill: '#FFFFFF', radius: o.radius || 8, name: 'ModalBox' });
  uiText(frame, 18, 16, o.title, { size: 16, weight: 600, color: UI.C.t1 });
  if (o.tag) uiText(frame, 18 + (o.title.length * 16) + 10, 19, o.tag, { size: 11, color: UI.C.t3 });
  uiText(frame, W - 30, 15, '✕', { size: 13, color: UI.C.t3 });
  uiDivider(frame, 0, headH - 1, W);
  uiDivider(frame, 0, H - footH, W);
  return { headH: headH, footH: footH, body: headH + 16, W: W, H: H };
}
function modalFoot(frame, m, leftBtn, rightBtn, o) {
  o = o || {};
  var y = m.H - m.footH + 12;
  if (leftBtn) uiBtn(frame, m.W - 210, y, 90, 30, leftBtn, {});
  if (rightBtn) uiBtn(frame, m.W - 110, y, 90, 30, rightBtn, { bg: o.danger ? UI.C.danger : GRAD.adminBtn, border: null, fg: '#FFFFFF' });
}
function formRow(frame, x, y, w, label, value, o) {
  o = o || {};
  uiText(frame, x, y, label + (o.req ? ' *' : ''), { size: 13, color: UI.C.t2 });
  var iy = y + 20;
  var box = uiPanel(frame, x, iy, w, 34, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
  uiText(box, 10, 9, value || '', { size: 13, color: o.placeholder ? UI.C.t4 : UI.C.t1 });
  if (o.hint) uiText(frame, x, iy + 38, o.hint, { size: 11, color: UI.C.t3, w: w });
  return iy + 34 + (o.hint ? 20 : 0) + 14;
}

// ===========================================================================
// 4d) Screen 绘制：P-A1 / P-A2 / P-A5 / P-A6 / P-T1 / P-M1…P-M10
// ===========================================================================
function tblCols(W, defs) {
  // defs: [[title,width|null]]，最后一列 width=null 时自动吃满剩余
  var total = W, fixed = 0, i;
  for (i = 0; i < defs.length - 1; i++) fixed += defs[i][1];
  var out = [];
  for (i = 0; i < defs.length - 1; i++) out.push({ t: defs[i][0], w: defs[i][1] });
  out.push({ t: defs[defs.length - 1][0], w: total - fixed });
  return out;
}

// ---- P-A1 卡产品管理 ----
function drawPA1(frame) {
  var main = drawAdminShell(frame, { active: 'P-A1', title: '卡产品管理' });
  var W = frame.width - 200, x = 14, y = 62;
  uiBtn(main, x, y, 72, 30, '新增', { bg: GRAD.adminBtn, border: null, fg: '#FFFFFF' });
  uiBtn(main, x + 80, y, 92, 30, '批量删除', { bg: UI.C.danger, border: null, fg: '#FFFFFF', opacity: 0.5 });
  uiText(main, x + 186, y + 8, '产品=模板，卡=实例 (R-B1)', { size: 12, color: UI.C.t3 });
  y += 44;
  var cols = tblCols(W - 28, [['', 40], ['序号', 60], ['产品名称', 200], ['计费方式', 110], ['包含次数', 110], ['有效天数', 110], ['价格(元)', 110], ['适用课程类型', 140], ['状态', 100], ['操作', null]]);
  var rows = [];
  for (var i = 0; i < D.products.length; i++) {
    var p = D.products[i];
    rows.push([
      { checkbox: true }, String(i + 1), p.n,
      { tag: { t: p.ct, c: p.ct === '次卡' ? UI.C.ok : UI.C.warn, bg: p.ct === '次卡' ? UI.C.okBg : UI.C.warnBg, bd: p.ct === '次卡' ? '#c2e7b0' : '#f5dab1' } },
      p.credits, p.days, p.price,
      { tag: { t: p.app, c: UI.C.adminPri, bg: UI.C.frozenBg, bd: '#b3d8ff' } },
      { tag: { t: p.status, c: UI.C.ok, bg: UI.C.okBg, bd: '#c2e7b0' } },
      { text: '编辑 · 下架', color: UI.C.adminPri, size: 12 }
    ]);
  }
  uiTable(main, x, y, W - 28, cols, rows, { name: 'P-A1 Table' });
  y += 40 + rows.length * 46 + 16;
  uiSticker(main, x, y, 2, '次卡用尽是否独立状态：现状无 EXHAUSTED，remaining=0 仍 ACTIVE，"已用尽"仅以余额徽标表达（本原型采用）', 'pending');
  y += 62;
  uiText(main, x, y, '软删除+回收站恢复为原型扩展（真实页面无回收站按钮）；删除后新建同名产品不冲突', { size: 11, color: UI.C.t3 });
}

// ---- P-A2 会员卡管理列表 ----
function drawPA2(frame) {
  var main = drawAdminShell(frame, { active: 'P-A2', title: '会员卡管理列表' });
  var W = frame.width - 200, x = 14, y = 62;
  uiBtn(main, x, y, 132, 30, '发放会员卡 (P-A3)', { bg: GRAD.adminBtn, border: null, fg: '#FFFFFF' });
  uiBtn(main, x + 140, y, 92, 30, '批量作废', { bg: UI.C.danger, border: null, fg: '#FFFFFF', opacity: 0.5 });
  uiText(main, x + 246, y + 8, 'D9: 期卡发卡即 PENDING，有效期待首次上课激活', { size: 12, color: UI.C.t3 });
  y += 44;
  // 筛选行
  var sbox = uiPanel(main, x, y, 240, 34, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
  uiText(sbox, 10, 9, '搜索学员或手机号', { size: 13, color: UI.C.t4 });
  var fx = x + 256;
  var msBox = uiPanel(main, fx, y, 452, 34, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
  uiText(msBox, 10, 10, '状态筛选', { size: 12, color: UI.C.t3 });
  var chips = ['未激活', '正常', '已过期', '已冻结', '已作废'];
  var cxp = 70;
  for (var c = 0; c < chips.length; c++) {
    // 不为测宽而创建游离文本节点（游离节点 remove() 存在兼容风险）：按 11px 中文 ≈ 12px/字估算步进
    var wChip = chips[c].length * 12 + 18;
    uiTag(msBox, cxp, 7, chips[c], { size: 11, color: c === 0 ? UI.C.adminPri : UI.C.t2, bg: c === 0 ? UI.C.frozenBg : UI.C.infoBg, border: c === 0 ? '#b3d8ff' : null, radius: 12, h: 20 });
    cxp += wChip + 6;
  }
  y += 50;
  var cols = tblCols(W - 28, [['', 36], ['序号', 44], ['会员卡号', 126], ['产品名称', 126], ['计费方式', 74], ['学员', 70], ['手机号', 100], ['总次数', 60], ['已用', 50], ['剩余', 50], ['状态', 74], ['有效期', 180], ['冻结信息', 130], ['操作', null]]);
  var rows = [];
  for (var i = 0; i < D.cards.length; i++) {
    var cd = D.cards[i];
    var stColor = cd.st === 'ACTIVE' ? UI.C.ok : cd.st === 'PENDING' ? UI.C.info : cd.st === 'EXPIRED' ? UI.C.warn : cd.st === 'FROZEN' ? UI.C.danger : UI.C.info;
    var stBg = cd.st === 'ACTIVE' ? UI.C.okBg : cd.st === 'PENDING' ? UI.C.infoBg : cd.st === 'EXPIRED' ? UI.C.warnBg : cd.st === 'FROZEN' ? UI.C.dangerBg : UI.C.infoBg;
    var stBd = cd.st === 'ACTIVE' ? UI.C.okBorder : cd.st === 'PENDING' ? UI.C.infoBorder : cd.st === 'EXPIRED' ? UI.C.warnBorder : cd.st === 'FROZEN' ? UI.C.dangerBorder : UI.C.infoBorder;
    var stTxt = cd.st === 'ACTIVE' ? '正常' : cd.st === 'PENDING' ? '未激活' : cd.st === 'EXPIRED' ? '已过期' : cd.st === 'FROZEN' ? '已冻结' : '已作废';
    var ops = cd.st === 'PENDING' ? '激活 · 作废' : cd.st === 'ACTIVE' ? '冻结 · 作废' : cd.st === 'FROZEN' ? '提前解冻 · 作废' : '—';
    rows.push([
      { checkbox: true }, String(i + 1), { t: cd.no, color: UI.C.adminPri, size: 12 }, cd.prod,
      { tag: { t: cd.ct, c: cd.ct === '次卡' ? UI.C.adminPri : UI.C.ok, bg: cd.ct === '次卡' ? UI.C.frozenBg : UI.C.okBg, bd: cd.ct === '次卡' ? '#b3d8ff' : '#c2e7b0' } },
      cd.stu, cd.phone, cd.total, cd.used, cd.left,
      { badge: { t: stTxt, c: stColor, bg: stBg, bd: stBd } },
      cd.range,
      cd.frozen ? { text: cd.frozen, color: UI.C.ok, size: 12, weight: 500 } : '-',
      { text: ops, color: UI.C.adminPri, size: 12 }
    ]);
  }
  uiTable(main, x, y, W - 28, cols, rows, { name: 'P-A2 Table', rowH: 44 });
  y += 40 + rows.length * 44 + 16;
  uiSticker(main, x, y, 3, '冻结/作废前应显示"该卡 N 个有效预约受影响"（依赖待开发的受影响预约查询）；此处为占位', 'confirmed');
  y += 62;
  uiText(main, x, y, '流程 A 入口：点击"演示流程 A"可跳转学员端查看课卡', { size: 11, color: UI.C.t3 });
}

// ---- P-A5 预约管理列表 ----
function drawPA5(frame) {
  var main = drawAdminShell(frame, { active: 'P-A5', title: '预约管理列表' });
  var W = frame.width - 200, x = 14, y = 62;
  // 待新增 banner
  var ban = uiPanel(main, x, y, W - 28, 44, { fill: '#FFF8EC', stroke: '#E0B070', strokeW: 1, radius: 10, name: 'PendingBanner' });
  try { ban.dashPattern = [4, 4]; } catch (e) { /* 忽略 */ }
  uiText(ban, 12, 8, '待新增 · 真实项目不存在', { size: 12, weight: 700, color: '#B8792A' });
  uiText(ban, 12, 24, '管理后台预约管理页：真实 admin 菜单无此页（会员卡管理/排期管理之外未实现预约管理列表）', { size: 11, color: '#A9702A', w: W - 60 });
  y += 56;
  var sbox = uiPanel(main, x, y, 140, 32, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
  uiText(sbox, 10, 8, '全部状态  ▾', { size: 12, color: UI.C.t2 });
  var sbox2 = uiPanel(main, x + 148, y, 240, 32, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
  uiText(sbox2, 10, 8, '学员/排期筛选', { size: 12, color: UI.C.t4 });
  uiText(main, x + 400, y + 8, '计划卡失效行高亮警示 (D3)', { size: 12, color: UI.C.t3 });
  y += 46;
  var cols = tblCols(W - 28, [['预约ID', 90], ['学员', 90], ['课程/排期', 210], ['状态', 100], ['计划卡', 330], ['来源', 90], ['取消原因', 150], ['操作', null]]);
  var rows = [];
  for (var i = 0; i < D.bookings.length; i++) {
    var b = D.bookings[i];
    var bst = b.st === 'BOOKED' ? { c: UI.C.adminPri, bg: UI.C.frozenBg, bd: UI.C.frozenBorder } : b.st === 'COMPLETED' ? { c: UI.C.info, bg: UI.C.infoBg, bd: UI.C.infoBorder } : { c: UI.C.danger, bg: UI.C.dangerBg, bd: UI.C.dangerBorder };
    var cst = b.cardSt === 'ACTIVE' ? { c: UI.C.ok, bg: UI.C.okBg, bd: UI.C.okBorder } : b.cardSt === 'EXHAUSTED' ? { c: UI.C.warn, bg: UI.C.warnBg, bd: UI.C.warnBorder } : { c: UI.C.danger, bg: UI.C.dangerBg, bd: UI.C.dangerBorder };
    rows.push([
      b.id, b.stu,
      { stack: [{ t: b.course, size: 12, color: UI.C.t1 }, { t: b.when, size: 11, color: UI.C.t3 }] },
      { badge: { t: b.stl, c: bst.c, bg: bst.bg, bd: bst.bd } },
      { stack: [{ t: b.cardNo, size: 12, color: UI.C.t1 }, { badge: { t: b.cardStl, c: cst.c, bg: cst.bg, bd: cst.bd } }] },
      b.src, b.cancel,
      { text: b.act, color: UI.C.adminPri, size: 11 }
    ]);
  }
  uiTable(main, x, y, W - 28, cols, rows, { name: 'P-A5 Table', rowH: 56 });
  y += 40 + rows.length * 56 + 16;
  uiSticker(main, x, y, 7, '改期/改派为"待开发"原子端点，本版仅占位', 'pending');
  y += 62;
  uiText(main, x, y, '可找出"计划卡已作废的有效预约"演示场景 (B3)', { size: 11, color: UI.C.t3 });
}

// ---- P-A6 排期签到点名 ----
function drawPA6(frame) {
  var main = drawAdminShell(frame, { active: 'P-A6', title: '排期签到点名' });
  var W = frame.width - 200, x = 14, y = 62;
  var sbox = uiPanel(main, x, y, 460, 32, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
  uiText(sbox, 10, 8, '拉丁舞基础 2026-10-10 19:00-20:30 (今日可签到)  ▾', { size: 12, color: UI.C.t2 });
  uiText(main, x + 472, y + 8, 'D9: 签到校验计划卡状态，非 ACTIVE 拦截', { size: 12, color: UI.C.t3 });
  y += 46;
  var cols = tblCols(W - 28, [['学员', 160], ['预约状态', 140], ['计划卡', 400], ['签到时间', 160], ['操作', null]]);
  var rows = [];
  for (var i = 0; i < D.rosterS1.length; i++) {
    var r = D.rosterS1[i];
    rows.push([
      r.name,
      { badge: { t: r.st, c: r.stc, bg: r.stbg, bd: r.stbd } },
      { stack: [{ t: r.cardNo, size: 12, color: UI.C.t1 }, { badge: { t: r.cs, c: r.csc, bg: r.csbg, bd: 'transparent' } }] },
      r.time,
      { text: r.ops, color: UI.C.adminPri, size: 11 }
    ]);
  }
  uiTable(main, x, y, W - 28, cols, rows, { name: 'P-A6 Table', rowH: 56 });
  y += 40 + rows.length * 56 + 16;
  uiSticker(main, x, y, 5, '缺席(NO_SHOW)自动消解：排期 COMPLETED 即扣，是否到场不影响扣次；"标记缺席"仅记录，不触发回补（灰置）', 'confirmed');
  y += 62;
  uiSticker(main, x, y, 1, '签到/完成不再扣次，扣次在预约时已发生（预扣）；此处签到仅推进预约状态', 'confirmed');
}

// ---- P-T1 教师排期名单签到 ----
function drawPT1(frame) {
  var wrap = drawTeacherShell(frame, {});
  var W = 560, x = 0, y = 0;
  // 排期选择
  var sbox = uiPanel(wrap, x, y, 420, 32, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
  uiText(sbox, 10, 8, '排期：拉丁舞基础 2026-10-10 19:00-20:30  ▾', { size: 12, color: UI.C.t2 });
  uiText(wrap, x + 430, y + 8, 'D9: 签到校验计划卡状态', { size: 11, color: UI.C.t3 });
  y += 44;
  // 渐变头卡
  var head = uiPanel(wrap, x, y, W, 118, { fill: GRAD.tchHead, radius: 12, name: 'TchHead' });
  uiRect(head, 0, 0, W, 118, { fill: UI.C.teacher2, fillOpacity: 0.35, radius: 12 });
  uiText(head, 18, 16, '拉丁舞基础', { size: 17, weight: 600, color: '#FFFFFF' });
  uiText(head, 18, 44, '2026-10-10 19:00-20:30 · 1号厅 · 刘老师', { size: 12, color: '#FFFFFF', opacity: 0.92 });
  uiTag(head, 18, 70, '排期 S1', { size: 11, color: '#FFFFFF', bg: '#FFFFFF', border: null, radius: 6, pad: 8, h: 22 });
  try { head.children[head.children.length - 1].opacity = 0.18; } catch (e) { /* 忽略 */ }
  uiTag(head, 108, 70, '容量 10', { size: 11, color: '#FFFFFF', bg: '#FFFFFF', border: null, radius: 6, pad: 8, h: 22 });
  try { head.children[head.children.length - 1].opacity = 0.18; } catch (e2) { /* 忽略 */ }
  y += 130;
  // 统计卡
  var stat = uiPanel(wrap, x, y, W, 72, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card', name: 'TchStat' });
  var stats = [['3', '已预约'], ['1', '已签到'], ['2', '未签到']];
  for (var i = 0; i < stats.length; i++) {
    var sx = Math.round(W / 3) * i;
    uiText(stat, sx, 16, stats[i][0], { size: 20, weight: 700, color: '#1a1a2e' });
    uiText(stat, sx, 44, stats[i][1], { size: 11, color: UI.C.t3 });
    stat.children[stat.children.length - 2].x = sx + Math.round((W / 3 - stat.children[stat.children.length - 2].width) / 2);
    stat.children[stat.children.length - 1].x = sx + Math.round((W / 3 - stat.children[stat.children.length - 1].width) / 2);
    if (i < 2) uiRect(stat, sx + W / 3, 12, 1, 48, { fill: '#F0F2F5' });
  }
  y += 84;
  // 学员行
  for (var r = 0; r < D.rosterS1.length; r++) {
    var rr = D.rosterS1[r];
    var row = uiPanel(wrap, x, y, W, 76, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card', name: 'TchRow' });
    uiIconBox(row, 14, 17, 42, rr.name.charAt(0), { bg: GRAD.tchHead, fg: '#FFFFFF', radius: 21, size: 15 });
    uiText(row, 70, 16, rr.name, { size: 14, weight: 600, color: UI.C.t1 });
    uiText(row, 70, 38, rr.cardNo, { size: 11, color: UI.C.t3 });
    uiTag(row, 170, 36, rr.cs, { size: 10, color: rr.csc, bg: rr.csbg, border: 'transparent', h: 18 });
    uiBadge(row, 70, 52, rr.st, rr.stc, rr.stbg, rr.stbd);
    if (rr.time !== '—') uiText(row, 148, 55, '签到 ' + rr.time, { size: 11, color: UI.C.t3 });
    var btn = rr.st === '已签到' ? { t: '完成', bg: UI.C.ok, fg: '#FFFFFF', bd: null } : rr.st === '已完成' ? null : { t: '签到', bg: GRAD.adminBtn, fg: '#FFFFFF', bd: null };
    var ops = [];
    if (btn) ops.push(btn);
    if (rr.st !== '已完成') ops.push({ t: '缺席', bg: '#FFFFFF', fg: UI.C.t2, bd: UI.C.border, op: 0.5 });
    var opx = W - 16;
    for (var oi = ops.length - 1; oi >= 0; oi--) {
      var ow = 62;
      var ob = uiBtn(row, opx - ow, 24, ow, 28, ops[oi].t, { bg: ops[oi].bg, border: ops[oi].bd, fg: ops[oi].fg, opacity: ops[oi].op });
      opx -= ow + 8;
    }
    if (!btn) uiText(row, W - 90, 30, '已完成', { size: 12, color: UI.C.t3 });
    y += 88;
  }
  uiSticker(wrap, x, y + 4, 5, '"标记缺席"灰置：缺席自动消解，排期 COMPLETED 即扣，不触发回补', 'confirmed');
  y += 66;
  uiSticker(wrap, x, y, 1, '签到/完成不扣次，扣次在预约时已发生（预扣）', 'confirmed');
}

// ---- 小程序：卡片条目 ----
function drawMiniCardItem(parent, x, y, W, c) {
  var clsFill = (c.kind === 'ACTIVE' || c.cls === 'card-active') ? GRAD.goldCard : c.cls === 'card-frozen' ? GRAD.cardFrozenBg : (c.cls === 'card-expired' || c.cls === 'card-voided') ? GRAD.cardVoidBg : GRAD.cardGrey;
  // 冻结卡需在用量区下方补「提前解冻」按钮 → 高度自适应
  var h = 132 + (c.extra === 'unfreeze' ? 40 : 0);
  var card = uiPanel(parent, x, y, W, h, { fill: clsFill, stroke: 'rgba(201,166,107,.2)', strokeW: 1, radius: 10, name: 'CardItem ' + c.kind });
  uiText(card, 14, 16, c.name, { size: 15, weight: 700, color: '#333333' });
  uiBadge(card, W - 90, 14, c.badge, c.bc, c.bbg, 'transparent');
  uiText(card, 14, 42, '卡号', { size: 11, color: '#8A7A6A' });
  uiText(card, 44, 42, c.no, { size: 11, color: '#999999' });
  // 复制卡号按钮（真实 membership/index.vue .copy-icon-btn / AppIcon copy）；用真实 copy 矢量图标
  var cpX = 44 + c.no.length * 7 + 8;
  uiIconSvg(card, cpX, 40, 13, 'copy', '#b8956a');
  // 用量区
  drawMiniUsage(card, 14, 74, W - 28, c);
  // 冻结信息 + 提前解冻（原型 stuCardItem FROZEN 分支）
  if (c.frozen) uiText(card, 14, 108, c.frozen, { size: 10, color: '#8A7A6A', w: W - 120 });
  if (c.extra === 'unfreeze') uiBtn(card, W - 108, h - 34, 92, 26, '提前解冻', { bg: '#FFFFFF', border: 'rgba(100,149,237,.5)', fg: UI.C.frozen, radius: 14, size: 11 });
  return h + 12;
}

function drawMiniUsage(card, x, y, w, c) {
  // 次卡（ACTIVE / USED_UP / FROZEN）：剩余/总次数 + 有效期至
  if (c.usage === 'credits') {
    var zero = c.left === '0';
    var numColor = zero ? '#EF5350' : (c.kind === 'FROZEN' ? UI.C.frozen : UI.C.gold);
    uiText(card, x, y, c.left, { size: 26, weight: 700, color: numColor });
    uiText(card, x + 22, y + 14, '/ ' + c.total + ' 次', { size: 13, color: '#999999' });
    uiRect(card, x + 96, y + 6, 1, 24, { fill: 'rgba(201,166,107,.28)' });
    uiText(card, x + 106, y + 8, '有效期至', { size: 10, color: '#A89B8A' });
    uiText(card, x + 106, y + 22, String(c.range).replace('有效期至 ', ''), { size: 11, color: '#8A7A6A' });
    return;
  }
  // 期卡（PENDING / ACTIVE）：剩余天数 + 有效期起算说明 / 区间
  if (c.usage === 'period-days') {
    uiText(card, x, y, '剩余', { size: 12, color: '#8A7A6A' });
    uiText(card, x + 34, y, c.days, { size: 26, weight: 700, color: UI.C.gold });
    uiText(card, x + 66, y + 14, '天', { size: 12, color: '#999999' });
    uiRect(card, x + 96, y + 6, 1, 24, { fill: 'rgba(201,166,107,.28)' });
    uiText(card, x + 106, y + 8, '有效期', { size: 10, color: '#A89B8A' });
    uiText(card, x + 106, y + 22, c.begin, { size: 11, color: '#8A7A6A', w: 150 });
    if (c.extra === 'activate') uiBtn(card, w - 96, y - 2, 96, 32, '立即激活', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 20, size: 12, weight: 600 });
    return;
  }
  // 无效卡（EXPIRED / CANCELLED）：直接展示有效期区间
  uiText(card, x, y + 6, '有效期', { size: 11, color: '#8A7A6A' });
  uiText(card, x + 46, y + 4, c.range, { size: 13, color: '#8A7A6A' });
}

// ---- P-M1 我的会员卡（有效课卡 Tab；6 张卡 → 拆帧，offset = 678）----
function drawPM1(frame, offset) {
  var c = drawMobileShell(frame, { offset: offset || 0, contentH: 1016, nav: '我的会员卡', back: true });
  var W = frame.width;
  // 双胶囊筛选（真实 membership/index.vue .filter-tabs；计数对齐原型：有效 6 / 无效 2）
  uiBtn(c, 12, 12, 171, 36, '有效课卡 6', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 18, size: 13, weight: 600 });
  uiBtn(c, 192, 12, 171, 36, '无效课卡 2', { bg: '#FFFFFF', border: null, fg: '#B8A088', radius: 18, size: 13, opacity: 0.7 });
  var y = 62;
  for (var i = 0; i < D.miniCards.length; i++) {
    y += drawMiniCardItem(c, 12, y, W - 24, D.miniCards[i]);
  }
  uiSticker(c, 12, y + 4, 2, '用尽徽标：次卡 remaining_credits=0 时 status 仍为「正常」，"已用完"仅以灰色徽标表达，不新增状态', 'pending');
}

// ---- P-M1c 我的会员卡·无效课卡 Tab（EXPIRED / CANCELLED）----
function drawPM1c(frame) {
  var c = drawMobileShell(frame, { nav: '我的会员卡', back: true });
  var W = frame.width;
  uiBtn(c, 12, 12, 171, 36, '有效课卡 6', { bg: '#FFFFFF', border: null, fg: '#B8A088', radius: 18, size: 13, opacity: 0.7 });
  uiBtn(c, 192, 12, 171, 36, '无效课卡 2', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 18, size: 13, weight: 600 });
  var y = 62;
  for (var i = 0; i < D.miniCardsInvalid.length; i++) {
    y += drawMiniCardItem(c, 12, y, W - 24, D.miniCardsInvalid[i]);
  }
  uiSticker(c, 12, y + 4, 2, '无效区仅收录 EXPIRED 已过期 / CANCELLED 已作废；「已用完」(remaining=0) 仍属有效区，仅以灰色徽标表达，不新增状态', 'pending');
}

// ---- P-M1d 我的会员卡·空状态（无有效会员卡）----
function drawPM1d(frame) {
  var c = drawMobileShell(frame, { nav: '我的会员卡', back: true });
  var W = frame.width;
  uiBtn(c, 12, 12, 171, 36, '有效课卡 0', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 18, size: 13, weight: 600 });
  uiBtn(c, 192, 12, 171, 36, '无效课卡 0', { bg: '#FFFFFF', border: null, fg: '#B8A088', radius: 18, size: 13, opacity: 0.7 });
  var y = 82;
  // 3D 金卡插画（矢量近似，避免 emoji 缺字）
  var ill = uiPanel(c, Math.round((W - 180) / 2), y, 180, 112, { fill: GRAD.card3d, radius: 14, shadow: 'shadow/card', name: 'EmptyCard3D' });
  uiIconChip(ill, 66, 26, 48, 'crown', { bg: 'rgba(255,255,255,.28)', fg: '#FFFFFF', radius: 24, iconSize: 28 });
  y += 128;
  uiText(c, 0, y, '暂无有效会员卡', { size: 16, weight: 600, color: '#333333' }).x = Math.round((W - 128) / 2);
  uiText(c, 0, y + 28, '您还没有领取或激活会员卡', { size: 12, color: UI.C.t3 }).x = Math.round((W - 156) / 2);
  y += 66;
  uiBtn(c, Math.round((W - 200) / 2), y, 200, 44, '前往办理 ›', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 22, size: 14, weight: 600 });
  y += 70;
  var bs = uiPanel(c, 12, y, W - 24, 168, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card', name: 'BenefitsGrid' });
  uiText(bs, 14, 14, '会员卡可以为您带来', { size: 13, weight: 600, color: '#5A4A3A' });
  var items = [['crown', '专属课程优惠'], ['tag', '更多会员权益'], ['calendar-check', '优先预约课程'], ['heart', '享受专属服务']];
  for (var i = 0; i < items.length; i++) {
    var bx = 14 + (i % 2) * (Math.round((W - 24 - 28) / 2) + 8);
    var by = 46 + Math.floor(i / 2) * 56;
    uiIconChip(bs, bx, by, 26, items[i][0], { bg: 'rgba(201,166,107,.16)', fg: UI.C.gold, radius: 8, iconSize: 16 });
    uiText(bs, bx + 34, by + 6, items[i][1], { size: 12, color: '#5A4A3A', w: 110 });
  }
  y += 182;
  uiSticker(c, 12, y, 2, '空态＝有效区无卡（首次进入或卡全部过期/作废）；"前往办理"指向线下发卡流程，本原型不画办卡入口', 'pending');
}

// ---- P-M2 卡详情 + 使用记录 ----
function drawPM2(frame) {
  var c = drawMobileShell(frame, {});
  var W = frame.width, x = 12, y = 12;
  var ban = uiPanel(c, x, y, W - 24, 44, { fill: '#FFF8EC', stroke: '#E0B070', strokeW: 1, radius: 10 });
  try { ban.dashPattern = [4, 4]; } catch (e) { /* 忽略 */ }
  uiText(ban, 10, 6, '待新增 · 真实项目不存在', { size: 11, weight: 700, color: '#B8792A' });
  uiText(ban, 10, 22, '真实小程序我的会员卡页无此页，卡片也不可点击', { size: 10, color: '#A9702A', w: W - 50 });
  y += 54;
  uiText(c, x, y, '‹ 返回', { size: 13, color: UI.C.gold });
  y += 26;
  var card = uiPanel(c, x, y, W - 24, 196, { fill: GRAD.goldCard, stroke: 'rgba(201,166,107,.2)', strokeW: 1, radius: 10 });
  uiText(card, 14, 14, '拉丁舞次卡', { size: 15, weight: 700, color: '#5A4A3A' });
  uiText(card, 14, 36, '卡号 MC20260910002', { size: 11, color: '#999999' });
  uiBadge(card, W - 24 - 90, 12, '使用中', UI.C.ok, 'rgba(76,175,80,.12)', 'transparent');
  uiDivider(card, 0, 60, W - 24, '#F5F2EC');
  var lines = [['类型', '次卡'], ['余额', '7/10'], ['有效期', '2026-09-10 ~ 2026-12-09'], ['发卡日', '2026-09-10']];
  for (var i = 0; i < lines.length; i++) {
    uiText(card, 14, 74 + i * 28, lines[i][0], { size: 12, color: '#8A7A6A' });
    uiText(card, 76, 74 + i * 28, lines[i][1], { size: 12, color: '#5A4A3A' });
  }
  y += 208;
  uiText(c, x, y, '使用记录（只显示业务字段）', { size: 13, weight: 500, color: '#8A7A6A' });
  y += 26;
  // 原型 BASE_TXNS.C2：发放 / 消费 / 消费 / 消费（含余额列），覆盖多类型流水
  var recs = [
    ['发放', '2026-09-10 10:02 · 线下发卡 ISSUE', '+0', '10'],
    ['消费', '2026-10-07 19:30 · 拉丁舞基础 10-05', '-1', '9'],
    ['消费', '2026-10-08 20:00 · 拉丁舞基础 10-08', '-1', '8'],
    ['消费', '2026-10-10 09:00 · 拉丁舞基础 10-10', '-1', '7']
  ];
  for (var r = 0; r < recs.length; r++) {
    var row = uiPanel(c, x, y, W - 24, 60, { fill: '#FFFFFF', radius: 8, shadow: 'shadow/card' });
    uiText(row, 14, 12, recs[r][0], { size: 13, weight: 600, color: recs[r][0] === '发放' ? UI.C.ok : UI.C.t1 });
    uiText(row, 14, 34, recs[r][1], { size: 11, color: UI.C.t3, w: W - 90 });
    uiText(row, W - 72, 20, recs[r][2], { size: 14, weight: 600, color: recs[r][2] === '+0' ? UI.C.t3 : '#5A4A3A' });
    uiText(row, W - 44, 20, '余 ' + recs[r][3], { size: 10, color: '#A89B8A' });
    y += 70;
  }
  uiBtn(c, x, y + 6, W - 24, 44, '去预约', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 24, size: 15, weight: 600 });
  y += 60;
  uiText(c, x, y, '「冻结原因 / 作废原因」行按卡状态条件展示：本卡为正常态，故不显示（冻结卡显示冻结原因，作废卡显示作废原因）', { size: 10, color: UI.C.t3, w: W - 24 });
}

// ---- P-M3 课程排期选择 ----
function drawPM3(frame) {
  var c = drawMobileShell(frame, { reserve: 50 });
  var W = frame.width, x = 12, y = 12;
  var nav = uiPanel(c, x, y, W - 24, 34, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card' });
  uiText(nav, 14, 9, '排期列表', { size: 15, weight: 600, color: '#1A1A1A' });
  y += 44;
  // 分类胶囊
  var cats = ['全部', '常规课', '私教课', '特色课'];
  var px = x;
  for (var i = 0; i < cats.length; i++) {
    var wI = i === 0 ? 62 : 78;
    uiBtn(c, px, y, wI, 36, cats[i], { bg: i === 0 ? GRAD.goldBtnSoft : '#FFFFFF', border: i === 0 ? null : 'rgba(201,166,107,.2)', fg: i === 0 ? '#5C4A32' : UI.C.tabActive, radius: 18, size: 12, weight: i === 0 ? 600 : 400 });
    px += wI + 6;
  }
  y += 46;
  // 日期胶囊（严格对齐原型 stuDateList()：今日前后滚动窗口 i=-1..+3，选中项 = 今日）
  var dates = [['周五', '10-09'], ['今日', '10-10'], ['明日', '10-11'], ['周一', '10-12'], ['周二', '10-13']];
  var dx = x;
  for (var d = 0; d < dates.length; d++) {
    var on = d === 1;   // index 1 = 今日（当日），与原型 date===TODAY 选中一致
    uiBtn(c, dx, y, 60, 46, '', { bg: on ? GRAD.goldBtn : '#FFFFFF', border: on ? null : 'rgba(201,166,107,.15)', radius: 20 });
    uiText(c, dx, y + 6, dates[d][0], { size: 10, color: on ? '#FFFFFF' : '#8E8579' }).x = dx + Math.round((60 - 20) / 2);
    uiText(c, dx, y + 24, dates[d][1], { size: 12, weight: 500, color: on ? '#FFFFFF' : '#1A1A1A' }).x = dx + Math.round((60 - 34) / 2);
    if (on) uiCircle(c, dx + 28, y + 36, 4, '#FFFFFF');
    dx += 66;
  }
  y += 58;
  // 排期卡：三类状态（预约 / 已满 / 已预约-取消），对齐原型 schedView 的文案与类名
  var cardStates = [
    { s: D.schedules[0], text: '预约', cls: 'book', hint: '' },
    { s: D.schedules[2], text: '已满', cls: 'full', hint: '' },
    { s: D.schedules[1], text: '取消', cls: 'cancel', hint: '开课前 90 分钟内不可取消' }
  ];
  for (var k = 0; k < cardStates.length; k++) {
    var s = cardStates[k].s, bt = cardStates[k];
    var card = uiPanel(c, x, y, W - 24, 132, { fill: '#FFFFFF', stroke: 'rgba(201,166,107,.12)', strokeW: 1, radius: 12, shadow: 'shadow/card' });
    // 左侧时间竖排
    var ts = uiPanel(card, 12, 14, 50, 104, { fill: GRAD.timeSection, radius: 8 });
    uiText(ts, 0, 22, s.time.split('-')[0], { size: 14, weight: 600, color: UI.C.tabActive }).x = Math.round((50 - 40) / 2);
    uiRect(ts, 24, 44, 1, 12, { fill: GRAD.timeDivider });
    uiText(ts, 0, 62, s.time.split('-')[1], { size: 14, weight: 600, color: UI.C.tabActive }).x = Math.round((50 - 40) / 2);
    // 右内容区：类型标签 + 课程名 + 「›」
    uiTag(card, 74, 14, s.ct, { size: 10, color: '#7B6B8A', bg: GRAD.tagRegular, border: null, radius: 10, h: 20 });
    uiText(card, 130, 16, s.course, { size: 16, weight: 600, color: '#4A3728', w: W - 24 - 150 });
    uiIconSvg(card, W - 24 - 18, 17, 16, 'arrow-right', '#c9a66b');
    // 教室 / 教师 / 容量 行（📍 room · 👤 teacher / 👥 人，矢量图标）
    uiIconSvg(card, 74, 44, 14, 'location', UI.C.gold);
    uiText(card, 92, 45, s.room + ' · ' + s.teacher, { size: 12, color: UI.C.tabActive });
    uiIconSvg(card, 74, 68, 14, 'people', UI.C.gold);
    uiText(card, 92, 69, s.booked + '/' + s.cap + ' 人', { size: 11, color: '#A89880' });
    // 按钮三态：预约 / 已满（禁用）/ 取消（含时限提示）
    var btnX = W - 24 - 82, btnY = 84;
    if (bt.cls === 'book') uiBtn(card, btnX, btnY, 68, 28, '预约', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 16, size: 12 });
    else if (bt.cls === 'full') uiBtn(card, btnX, btnY, 68, 28, '已满', { bg: '#EFEFEF', border: null, fg: '#B0B0B0', radius: 16, size: 12 });
    else uiBtn(card, btnX, btnY, 68, 28, '取消', { bg: '#FFFFFF', border: 'rgba(245,108,108,.5)', fg: UI.C.danger, radius: 16, size: 12 });
    if (bt.hint) uiText(card, 74, 112, bt.hint, { size: 10, color: UI.C.danger, w: W - 24 - 94 });
    y += 144;
  }
  uiSticker(c, x, y, 9, '进入确认页前预检查卡可用性：按"排期日 + validity_days"计算预期有效期', 'confirmed');
  y += 62;
  uiText(c, x, y, '按钮状态覆盖 schedView 全集：已满 / 无会员卡 / 不可取消（含「开课前 N 分钟内不可取消」提示，N = 租户配置 booking_cancel_minutes，默认 90）；无会员卡时提示"您需要先办理会员卡才能预约课程"', { size: 10, color: UI.C.t3, w: W - 24 });
}

// ---- P-M4 预约确认选卡 ----
function drawPM4(frame) {
  var c = drawMobileShell(frame, { nav: '预约确认', back: true });
  var W = frame.width, x = 12, y = 12;
  // 课程信息卡（原型 .info-card：📖 header + 课程名 + 📅/🕐/📍/👤/👥 info-row）
  var card1 = uiPanel(c, x, y, W - 24, 172, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card' });
  uiIconChip(card1, 14, 14, 26, 'book', { bg: GRAD.goldBtn, fg: '#FFFFFF', radius: 8, iconSize: 16 });
  uiText(card1, 48, 18, '课程信息', { size: 14, weight: 600, color: '#5A4A3A' });
  uiRect(card1, 110, 26, W - 24 - 124, 1, { fill: GRAD.headerLine });
  uiText(card1, 14, 50, '拉丁舞基础', { size: 16, weight: 700, color: '#333333' });
  var rows1 = [['calendar', '2026-10-10'], ['clock', '19:00-20:30'], ['location', '1号厅'], ['user', '刘老师'], ['people', '剩余 2/10 人']];
  for (var i = 0; i < rows1.length; i++) {
    uiIconSvg(card1, 14, 77 + i * 19, 13, rows1[i][0], UI.C.gold);
    uiText(card1, 33, 78 + i * 19, rows1[i][1], { size: 12, color: '#5A4A3A' });
  }
  y += 184;
  // 使用会员卡卡（原型 .use-card-card：💳 header + .selected-card-info → 点击打开选卡底部弹窗）
  var card2 = uiPanel(c, x, y, W - 24, 116, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card' });
  uiIconChip(card2, 14, 14, 26, 'card', { bg: GRAD.goldBtn, fg: '#FFFFFF', radius: 8, iconSize: 16 });
  uiText(card2, 48, 18, '使用会员卡', { size: 14, weight: 600, color: '#5A4A3A' });
  uiRect(card2, 124, 26, W - 24 - 138, 1, { fill: GRAD.headerLine });
  var sel = uiPanel(card2, 14, 50, W - 52, 52, { fill: 'rgba(201,166,107,.07)', radius: 10, name: 'SelectedCardInfo' });
  uiText(sel, 12, 8, '拉丁舞次卡', { size: 14, weight: 600, color: '#333333' });
  uiText(sel, 12, 28, '剩余 7/10 次 · 卡号 MC20260910002', { size: 11, color: '#8A7A6A' });
  uiTag(sel, W - 52 - 66, 12, '次卡', { size: 10, color: UI.C.warn, bg: 'rgba(230,162,60,.16)', border: null, radius: 8, h: 20 });
  uiIconSvg(sel, W - 52 - 22, 16, 16, 'arrow-right', '#b8956a');
  uiText(card2, 14, 104, '点击「使用会员卡」打开选卡底部弹窗（OV-CARDSEL）', { size: 9, color: UI.C.t4, w: W - 52 });
  y += 128;
  // 注意事项卡（原型 .notice-card：📋 header + ◆ notice-item）
  var card3 = uiPanel(c, x, y, W - 24, 112, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card' });
  uiIconChip(card3, 14, 14, 26, 'clipboard', { bg: GRAD.goldBtn, fg: '#FFFFFF', radius: 8, iconSize: 16 });
  uiText(card3, 48, 18, '注意事项', { size: 14, weight: 600, color: '#5A4A3A' });
  uiRect(card3, 124, 26, W - 24 - 138, 1, { fill: GRAD.headerLine });
  var notes = ['开课前 90 分钟内不可取消预约', '请准时到达教室，迟到可能影响上课', '如需取消请提前在"我的预约"中操作'];
  for (var n = 0; n < notes.length; n++) {
    uiText(card3, 14, 48 + n * 20, '◆', { size: 8, color: UI.C.gold });
    uiText(card3, 30, 48 + n * 20, notes[n], { size: 11, color: '#8A7A6A', w: W - 70 });
  }
  y += 124;
  // 底部操作栏
  uiBtn(c, x, y, (W - 24 - 12) / 2, 44, '取消', { bg: '#FFFFFF', border: '#E5DDD0', fg: '#8A7A6A', radius: 24, size: 15, weight: 600 });
  uiBtn(c, x + (W - 24 - 12) / 2 + 12, y, (W - 24 - 12) / 2, 44, '确认预约', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 24, size: 15, weight: 600 });
  y += 56;
  uiSticker(c, x, y, 9, 'PENDING 期卡正常可选；期卡按"排期日+有效天数"预算预期有效期，与已有同产品期卡区间重叠则不可选', 'confirmed');
}

// ---- P-M5 预约结果页 ----
function drawPM5(frame) {
  var c = drawMobileShell(frame, {});
  var W = frame.width, x = 12, y = 12;
  var ban = uiPanel(c, x, y, W - 24, 44, { fill: '#FFF8EC', stroke: '#E0B070', strokeW: 1, radius: 10 });
  try { ban.dashPattern = [4, 4]; } catch (e) { /* 忽略 */ }
  uiText(ban, 10, 6, '待新增 · 真实项目不存在', { size: 11, weight: 700, color: '#B8792A' });
  uiText(ban, 10, 22, '预约结果页：真实小程序无独立结果页，预约成功直接进入我的预约', { size: 10, color: '#A9702A', w: W - 50 });
  y += 58;
  uiCircle(c, Math.round((W - 64) / 2), y, 64, UI.C.ok, 0.15);
  uiIconSvg(c, Math.round((W - 42) / 2), y + 11, 42, 'check-circle', UI.C.ok);
  y += 78;
  uiText(c, 0, y, '预约成功 · 已预扣 1 次', { size: 17, weight: 700, color: '#333333' }).x = Math.round((W - 150) / 2);
  y += 28;
  uiText(c, 0, y, '排期完成后确认扣次，取消将回补', { size: 11, color: UI.C.t3, w: W }).x = 0;
  y += 28;
  var info = uiPanel(c, x, y, W - 24, 128, { fill: '#FFFFFF', radius: 8 });
  var li = [['课程', '拉丁舞基础'], ['时间', '2026-10-10 19:00-20:30'], ['已预扣', '1 次'], ['剩余', '6 次']];
  for (var i = 0; i < li.length; i++) {
    uiText(info, 14, 14 + i * 28, li[i][0], { size: 12, color: UI.C.t3 });
    uiText(info, 90, 14 + i * 28, li[i][1], { size: 12, color: '#333333' });
  }
  y += 140;
  // 期卡分支：原型 r.kind === 'period' 的另一结果态（期卡不扣次 + 预期有效期）
  uiText(c, x, y, '期卡结果（另一分支：原型 r.kind = period）', { size: 12, weight: 700, color: '#5A4A3A' });
  y += 22;
  var pinfo = uiPanel(c, x, y, W - 24, 96, { fill: '#FFFFFF', radius: 8, stroke: 'rgba(201,166,107,.2)', strokeW: 1 });
  var pli = [['课程', '拉丁舞基础'], ['时间', '2026-10-10 19:00-20:30'], ['期卡', '不扣次'], ['预期有效期', '2026-10-10 ~ 2026-11-09']];
  for (var pj = 0; pj < pli.length; pj++) {
    uiText(pinfo, 14, 12 + pj * 22, pli[pj][0], { size: 12, color: UI.C.t3 });
    uiText(pinfo, 96, 12 + pj * 22, pli[pj][1], { size: 12, color: '#333333' });
  }
  y += 108;
  uiSticker(c, x, y, 9, '期卡 PENDING：首次排期 COMPLETED 才激活，在此之前不消耗有效期', 'confirmed');
  y += 64;
  uiBtn(c, x, y, W - 24, 46, '查看我的预约', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 24, size: 15, weight: 600 });
  y += 56;
  uiBtn(c, x, y, W - 24, 46, '返回首页', { bg: '#FFFFFF', border: UI.C.gold, fg: UI.C.gold, radius: 24, size: 15, weight: 600 });
}

// ---- P-M5b 预约失败（名额已满）----
function drawPM5b(frame) {
  var c = drawMobileShell(frame, {});
  var W = frame.width, x = 12, y = 12;
  var ban = uiPanel(c, x, y, W - 24, 44, { fill: '#FFF8EC', stroke: '#E0B070', strokeW: 1, radius: 10 });
  try { ban.dashPattern = [4, 4]; } catch (e) { /* 忽略 */ }
  uiText(ban, 10, 6, '待新增 · 真实项目不存在', { size: 11, weight: 700, color: '#B8792A' });
  uiText(ban, 10, 22, '预约结果页失败态：真实小程序无独立结果页', { size: 10, color: '#A9702A', w: W - 50 });
  y += 58;
  uiCircle(c, Math.round((W - 64) / 2), y, 64, UI.C.danger, 0.12);
  uiText(c, 0, y + 16, '✕', { size: 30, weight: 700, color: UI.C.danger }).x = Math.round((W - 26) / 2);
  y += 78;
  uiText(c, 0, y, '预约失败 · 名额已满', { size: 17, weight: 700, color: '#333333' }).x = Math.round((W - 170) / 2);
  y += 28;
  uiText(c, 0, y, '该排期名额已满，无法预约', { size: 11, color: UI.C.t3, w: W }).x = 0;
  y += 28;
  var info = uiPanel(c, x, y, W - 24, 92, { fill: '#FFFFFF', radius: 8 });
  var li5 = [['课程', '拉丁舞基础'], ['时间', '2026-10-12 10:00-11:30'], ['名额', '已满 10/10 人']];
  for (var i5 = 0; i5 < li5.length; i5++) {
    uiText(info, 14, 14 + i5 * 26, li5[i5][0], { size: 12, color: UI.C.t3 });
    uiText(info, 90, 14 + i5 * 26, li5[i5][1], { size: 12, color: '#333333' });
  }
  y += 104;
  uiBtn(c, x, y, W - 24, 46, '重新选择', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 24, size: 15, weight: 600 });
  y += 56;
  uiBtn(c, x, y, W - 24, 46, '返回首页', { bg: '#FFFFFF', border: UI.C.gold, fg: UI.C.gold, radius: 24, size: 15, weight: 600 });
}

// ---- P-M6 我的预约 ----
function drawPM6(frame) {
  var c = drawMobileShell(frame, { nav: '预约记录', back: true });
  var W = frame.width, x = 12, y = 12;
  var tabs = ['全部', '待上课', '上课中', '已完成'];
  var tw = Math.round((W - 24 - 24) / 4);
  for (var i = 0; i < tabs.length; i++) {
    uiBtn(c, x + i * (tw + 8), y, tw, 34, tabs[i], { bg: i === 0 ? GRAD.goldBtn : '#FFFFFF', border: i === 0 ? null : null, fg: i === 0 ? '#FFFFFF' : '#B8A088', radius: 17, size: 12, weight: i === 0 ? 600 : 400, opacity: i === 0 ? 1 : 0.75 });
  }
  y += 44;
  // 记录类型覆盖原型 bookingCardItem 的全部状态：可取消 / 计划卡失效警示 / 取消时限灰态 / 已取消含原因
  var list = [
    { course: '拉丁舞基础', when: '2026-10-10 19:00-20:30', st: '待上课', room: '1号厅', teacher: '刘老师', warn: false, action: '取消预约' },
    { course: '拉丁舞基础', when: '2026-10-12 10:00-11:30', st: '待上课', room: '2号厅', teacher: '陈老师', warn: true, action: '' },
    { course: '拉丁舞进阶', when: '2026-10-11 19:00-20:30', st: '待上课', room: '1号厅', teacher: '刘老师', warn: false, action: 'blocked' },
    { course: '拉丁舞进阶', when: '2026-10-11 19:00-20:30', st: '已取消', room: '1号厅', teacher: '刘老师', warn: false, action: '', cancelReason: '临时有事' }
  ];
  for (var k = 0; k < list.length; k++) {
    var b = list[k];
    var hasFoot = !!(b.warn || b.action || b.cancelReason);
    var h = b.warn ? 176 : (hasFoot ? 120 : 100);
    var card = uiPanel(c, x, y, W - 24, h, { fill: '#FFFFFF', radius: 12, shadow: 'shadow/card' });
    uiText(card, 14, 10, b.course, { size: 15, weight: 700, color: '#333333' });
    uiBadge(card, W - 24 - 76, 8, b.st, UI.C.goldD, 'rgba(201,166,107,.1)', 'transparent');
    var rows = [['时间', b.when], ['教室', b.room], ['教师', b.teacher]];
    for (var r = 0; r < rows.length; r++) {
      uiText(card, 14, 34 + r * 18, rows[r][0], { size: 11, color: '#8A7A6A' });
      uiText(card, 50, 34 + r * 18, rows[r][1], { size: 12, color: '#8A7A6A' });
    }
    if (b.warn) {
      var wb = uiPanel(card, 12, 88, W - 48, 78, { fill: UI.C.dangerBg, stroke: '#FBC4C4', strokeW: 1, radius: 6 });
      uiIconSvg(wb, 10, 9, 14, 'alert', '#a33');
      uiText(wb, 28, 8, '待新增 · 计划卡已作废', { size: 11, weight: 700, color: '#A33' });
      uiText(wb, 10, 26, '该预约的会员卡当前不可用，请换卡或联系机构', { size: 10, color: '#A33', w: W - 80 });
      uiBtn(wb, 10, 44, 78, 26, '换卡(占位)', { bg: '#FFFFFF', border: 'rgba(245,108,108,.5)', fg: UI.C.danger, radius: 20, size: 11 });
      uiBtn(wb, 96, 44, 78, 26, '联系机构', { bg: '#FFFFFF', border: 'rgba(245,108,108,.5)', fg: UI.C.danger, radius: 20, size: 11 });
    } else if (b.action === 'blocked') {
      uiText(card, 14, 84, '开课前 90 分钟内不可取消', { size: 11, color: UI.C.t3 });
    } else if (b.action) {
      uiBtn(card, W - 24 - 86, h - 36, 74, 28, b.action, { bg: '#FFFFFF', border: 'rgba(245,108,108,.5)', fg: UI.C.danger, radius: 20, size: 11, weight: 600 });
    } else if (b.cancelReason) {
      uiText(card, 14, 84, '取消原因：' + b.cancelReason, { size: 11, color: UI.C.t3 });
    }
    y += h + 8;
  }
  uiSticker(c, x, y, 7, '取消时限由租户配置 booking_cancel_minutes（默认 90 分钟）驱动；进入时限后"取消预约"替换为不可点击提示', 'pending');
  y += 62;
  uiSticker(c, x, y, 3, '计划卡失效警示条（红色条）为新增占位：真实页面暂无该条，需待 D7 接口落地；换卡为待开发原子端点', 'confirmed');
}

// ---- P-M6b 我的预约·空状态 ----
function drawPM6b(frame) {
  var c = drawMobileShell(frame, { nav: '预约记录', back: true });
  var W = frame.width, x = 12, y = 12;
  var tabs = ['全部', '待上课', '上课中', '已完成'];
  var tw = Math.round((W - 24 - 24) / 4);
  for (var i = 0; i < tabs.length; i++) {
    uiBtn(c, x + i * (tw + 8), y, tw, 34, tabs[i], { bg: i === 0 ? GRAD.goldBtn : '#FFFFFF', border: null, fg: i === 0 ? '#FFFFFF' : '#B8A088', radius: 17, size: 12, weight: i === 0 ? 600 : 400, opacity: i === 0 ? 1 : 0.75 });
  }
  y += 60;
  var emp = uiPanel(c, x, y, W - 24, 260, { fill: '#FFFFFF', stroke: 'rgba(201,166,107,.12)', strokeW: 1, radius: 12 });
  uiIconChip(emp, Math.round((emp.width - 64) / 2), 66, 64, 'calendar-empty', { bg: 'rgba(201,166,107,.14)', fg: UI.C.gold, radius: 32, iconSize: 32 });
  var t6 = uiText(emp, 12, 152, '暂无预约记录', { size: 14, weight: 600, color: '#8A7A6A' });
  t6.x = Math.round((emp.width - t6.width) / 2);
  uiText(emp, 12, 178, '去「排期」选择课程开始预约', { size: 11, color: UI.C.t3, w: emp.width - 24 }).x = 12;
  uiBtn(c, x, y + 260 + 16, W - 24, 44, '去选排期', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 22, size: 14, weight: 600 });
  var t6b = uiText(c, 12, y + 260 + 76, '空态：原型 stuM6() 在 list.length === 0 时直接返回 empty-state（含筛选 Tab，无便签）', { size: 10, color: UI.C.t3, w: W - 24 });
  t6b.x = 12;
}

// ---- P-M8 首页·课程列表 ----
function drawPM8(frame, offset) {
  var c = drawMobileShell(frame, { reserve: 50, offset: offset || 0, contentH: 1300 });
  var W = frame.width, y = 0;
  // navbar：📍 地点 + 门店名 + ▾（对齐原型 home-navbar）
  uiIconSvg(c, 16, 13, 14, 'homePin', UI.C.tabActive);
  uiText(c, 36, 12, '舞蹈艺术培训中心', { size: 14, weight: 500, color: '#3D2E1F' });
  uiText(c, 160, 14, '▾', { size: 12, color: UI.C.tabActive });
  y = 40;
  // Banner
  var banner = uiPanel(c, 0, y, W, 180, { fill: GRAD.bannerBg, name: 'Banner' });
  uiRect(banner, 0, 0, W, 180, { fill: GRAD.bannerOverlay });
  uiText(banner, 24, 56, '让舞蹈成为生活的一部分', { size: 22, weight: 700, color: '#FFFFFF' });
  uiText(banner, 24, 92, '遇见更好的自己 · 从一堂舞蹈课开始', { size: 13, color: '#FFFFFF', opacity: 0.9 });
  for (var d = 0; d < 3; d++) uiCircle(banner, Math.round(W / 2) - 12 + d * 10, 162, 5, d === 0 ? UI.C.gold : '#FFFFFF', d === 0 ? 1 : 0.4);
  y += 180;
  // 师资团队（👥 t-ic）
  uiIconSvg(c, 16, y + 18, 16, 'homePeople', '#c9a66b');
  uiText(c, 40, y + 18, '师资团队', { size: 16, weight: 600, color: '#3D2E1F' });
  y += 46;
  for (var i = 0; i < D.teachers.length; i++) {
    var tx = 16 + i * 90;
    uiCircle(c, tx + 5, y, 60, GRAD.teacherAvatar);
    uiText(c, tx + 5, y + 20, D.teachers[i].n.charAt(0), { size: 18, weight: 600, color: UI.C.tabActive }).x = tx + 5 + Math.round((60 - 18) / 2);
    uiText(c, tx, y + 68, D.teachers[i].n, { size: 13, weight: 500, color: '#3D2E1F' }).x = tx + Math.round((70 - 40) / 2);
    uiText(c, tx, y + 86, D.teachers[i].s, { size: 11, color: UI.C.tabActive, w: 70 }).x = tx;
  }
  y += 108;
  // 推荐课程（⭐ t-ic）
  uiIconSvg(c, 16, y + 12, 16, 'homeStar', '#c9a66b');
  uiText(c, 40, y + 12, '推荐课程', { size: 16, weight: 600, color: '#3D2E1F' });
  uiText(c, W - 80, y + 16, '全部课程 ›', { size: 12, color: UI.C.tabActive });
  y += 40;
  for (var c2 = 0; c2 < D.homeCourses.length; c2++) {
    var item = uiPanel(c, 16, y, W - 32, 96, { fill: '#FFFFFF', stroke: 'rgba(201,166,107,.12)', strokeW: 1, radius: 10 });
    uiRect(item, 10, 8, 80, 80, { fill: GRAD.courseImage, radius: 8 });
    uiText(item, 102, 26, D.homeCourses[c2].n, { size: 15, weight: 600, color: '#3D2E1F', w: W - 150 });
    uiText(item, 102, 52, D.homeCourses[c2].d, { size: 12, color: UI.C.tabActive, w: W - 150 });
    y += 108;
  }
  // 舞蹈视频（🎬 t-ic）
  uiIconSvg(c, 16, y + 12, 16, 'homePlay', '#c9a66b');
  uiText(c, 40, y + 12, '舞动 · 让生活更美好', { size: 16, weight: 600, color: '#3D2E1F' });
  y += 40;
  var vid = uiPanel(c, 16, y, W - 32, 240, { fill: '#FFFFFF', stroke: 'rgba(201,166,107,.12)', strokeW: 1, radius: 10 });
  uiRect(vid, 0, 0, W - 32, 140, { fill: GRAD.videoCover });
  uiRect(vid, 0, 0, W - 32, 140, { fill: GRAD.videoOverlay });   // .video-overlay 暗化渐变（压在封面之上、播放按钮之下）
  uiCircle(vid, Math.round((W - 32 - 50) / 2), 45, 50, UI.C.gold, 0.9);
  uiIconSvg(vid, Math.round((W - 32) / 2) - 11, 59, 22, 'homePlay', '#FFFFFF');
  uiTag(vid, Math.round((W - 32) / 2) + 20, 104, D.videos[0].dur, { size: 11, color: '#FFFFFF', bg: '#000000', border: null, radius: 10, h: 20 });
  try { vid.children[vid.children.length - 1].opacity = 0.5; } catch (e) { /* 忽略 */ }
  uiText(vid, 16, 156, D.videos[0].t, { size: 15, weight: 600, color: '#3D2E1F', w: W - 64 });
  uiText(vid, 16, 182, D.videos[0].d, { size: 12, color: UI.C.tabActive, w: W - 64 });
  y += 256;
  // 第 2 个舞蹈视频卡（原型 stuM8 遍历 VIDEOS 全量渲染）
  var vid2 = uiPanel(c, 16, y, W - 32, 240, { fill: '#FFFFFF', stroke: 'rgba(201,166,107,.12)', strokeW: 1, radius: 10 });
  uiRect(vid2, 0, 0, W - 32, 140, { fill: GRAD.videoCover });
  uiRect(vid2, 0, 0, W - 32, 140, { fill: GRAD.videoOverlay });   // .video-overlay 暗化渐变
  uiCircle(vid2, Math.round((W - 32 - 50) / 2), 45, 50, UI.C.gold, 0.9);
  uiIconSvg(vid2, Math.round((W - 32) / 2) - 11, 59, 22, 'homePlay', '#FFFFFF');
  uiTag(vid2, Math.round((W - 32) / 2) + 20, 104, D.videos[1].dur, { size: 11, color: '#FFFFFF', bg: '#000000', border: null, radius: 10, h: 20 });
  try { vid2.children[vid2.children.length - 1].opacity = 0.5; } catch (e) { /* 忽略 */ }
  uiText(vid2, 16, 156, D.videos[1].t, { size: 15, weight: 600, color: '#3D2E1F', w: W - 64 });
  uiText(vid2, 16, 182, D.videos[1].d, { size: 12, color: UI.C.tabActive, w: W - 64 });
  y += 256;
}

// ---- 我的·菜单行（真实 profile/index.vue .menu-item：左图标 + 标题 + 描述 + 右箭头）----
function drawMenuRow(parent, W, iconKey, title, desc, glyphColor, danger, y0) {
  var y = y0 || 0;
  uiIconChip(parent, 12, y + 16, 32, iconKey, { bg: danger ? GRAD.logoutIc : GRAD.menuIc, fg: glyphColor, radius: 8, iconSize: 18 });
  uiText(parent, 56, y + 16, title, { size: 14, weight: 500, color: danger ? '#E74C3C' : '#2C1810' });
  uiText(parent, 56, y + 38, desc, { size: 11, color: '#A89279', w: W - 100 });
  uiIconSvg(parent, W - 26, y + 28, 16, 'arrow-right', '#C9A66B');
  return 72;
}

// ---- P-M9 我的·个人中心 ----
function drawPM9(frame) {
  var c = drawMobileShell(frame, { reserve: 50, bg: GRAD.profileBg });   // .profile-page 专属背景渐变
  var W = frame.width, x = 12, y = 14;
  uiText(c, 16, y, '我的', { size: 18, weight: 600, color: '#2C1810' });
  y += 40;
  // 个人信息区（真实 profile-header：头像 + 昵称 + 「学员 · 手机号」+ 会员等级徽标）
  uiCircle(c, 16, y, 70, GRAD.avatarGold);
  uiText(c, 16, y + 22, '张', { size: 28, weight: 600, color: '#FFFFFF' }).x = 16 + Math.round((70 - 28) / 2);
  uiText(c, 100, y + 4, '张小明', { size: 18, weight: 600, color: '#2C1810' });
  uiText(c, 100, y + 30, '学员 · 138****8888', { size: 13, color: UI.C.tabActive });
  // membership-badge：👑 普通会员（矢量 crown）
  var mb = uiPanel(c, 100, y + 50, 92, 24, { fill: GRAD.memberBadge, radius: 12 });
  uiIconSvg(mb, 8, 4, 16, 'crown', UI.C.gold);
  uiText(mb, 28, 5, '普通会员', { size: 11, color: UI.C.gold });
  y += 96;
  // 我的会员卡入口（真实 .membership-card 突出卡片；👑 图标）
  var mem = uiPanel(c, x, y, W - 24, 80, { fill: GRAD.memCard, stroke: 'rgba(201,166,107,.2)', strokeW: 1, radius: 12, shadow: 'shadow/card' });
  uiIconChip(mem, 16, 18, 44, 'crown', { bg: GRAD.memIc, fg: UI.C.gold, radius: 22, iconSize: 24 });
  uiText(mem, 72, 22, '我的会员卡', { size: 16, weight: 600, color: '#2C1810' });
  uiText(mem, 72, 46, '查看会员权益 · 课程信息 · 剩余课时', { size: 12, color: UI.C.tabActive, w: W - 140 });
  uiIconSvg(mem, W - 24 - 22, 32, 16, 'arrow-right', UI.C.gold);
  y += 92;
  // 功能菜单组：预约记录（📅 calendar）
  var g1 = uiPanel(c, x, y, W - 24, 72, { fill: '#FFFFFF', radius: 10, stroke: 'rgba(201,166,107,.1)', strokeW: 1 });
  drawMenuRow(g1, W - 24, 'calendar', '预约记录', '查看我的课程预约与历史记录', UI.C.tabActive, false, 0);
  y += 84;
  // 账号设置组：解绑微信（💬 message） / 退出登录（⏻ power）
  var g2 = uiPanel(c, x, y, W - 24, 144, { fill: '#FFFFFF', radius: 10, stroke: 'rgba(201,166,107,.1)', strokeW: 1 });
  drawMenuRow(g2, W - 24, 'wechat', '解绑微信', '已绑定微信账号', UI.C.tabActive, false, 0);
  uiDivider(g2, 12, 72, W - 48);
  drawMenuRow(g2, W - 24, 'logout', '退出登录', '安全退出当前账号', '#E74C3C', true, 72);
}

// ---- P-M10 AI 助手（一级 Tab，完整聊天页；严格对齐原型 stuM10 / stuAiWelcome）----
function drawPM10(frame) {
  var c = drawMobileShell(frame, { reserve: 50 });
  var W = frame.width, H = frame.height;
  // 顶部信息区（原型 ai-header：robot 图标 + 「AI 助手 / ● 智能课程助手 · 模拟对话（未接入真实 AI）」+ 清空）
  var head = uiPanel(c, 0, 0, W, 48, { fill: '#FFFFFF', name: 'AiHeader' });
  uiDivider(c, 0, 47, W, '#F2ECE4');
  uiIconChip(head, 14, 9, 30, 'robot', { bg: GRAD.goldBtn, fg: '#FFFFFF', radius: 15, iconSize: 20 });
  uiText(head, 52, 8, 'AI 助手', { size: 14, weight: 600, color: '#3A2C1E' });
  uiCircle(head, 55, 31, 5, '#7bbf8a');   // ai-dot（会话状态点）
  uiText(head, 65, 26, '智能课程助手 · 模拟对话（未接入真实 AI）', { size: 10, color: '#B8A088', w: W - 130 });
  uiTag(head, W - 62, 12, '清空', { size: 11, color: '#8b7355', bg: '#FFFFFF', border: '#E6DCCD', radius: 999, h: 22 });
  // 欢迎态：ai-wbadge（lightbulb + 「您可以问我：」）+ AI_QUICK 4 条常用问题卡（仅问题文案）
  var bw = 118, bx = Math.round((W - bw) / 2);
  var badge = uiPanel(c, bx, 60, bw, 26, { fill: 'rgba(201,166,107,.14)', radius: 13 });
  uiIconSvg(badge, 10, 6, 14, 'lightbulb', '#8b7355');
  uiText(badge, 30, 6, '您可以问我：', { size: 11, weight: 600, color: '#8b7355' });
  var qa = [
    { ic: 'calendar', q: '如何预约课程？' },
    { ic: 'wallet', q: '我的课卡还剩多少次？' },
    { ic: 'edit', q: '如何取消或改约课程？' },
    { ic: 'clipboard', q: '我最近预约了哪些课程？' }
  ];
  var y = 98;
  for (var i = 0; i < qa.length; i++) {
    var q = uiPanel(c, 12, y, W - 24, 48, { fill: '#FFFFFF', stroke: '#EFE6D8', strokeW: 1, radius: 10 });
    uiIconSvg(q, 14, 15, 18, qa[i].ic, '#c9a66b');
    uiText(q, 44, 15, qa[i].q, { size: 12, color: '#2C1810' });
    uiIconSvg(q, W - 24 - 22, 16, 16, 'arrow-right', '#c9a66b');
    y += 56;
  }
  // 输入区（固定底部，TabBar 之上；message 图标 + placeholder + send 图标）
  var inp = uiPanel(c, 0, H - 24 - 50 - 58, W, 58, { fill: '#FFFFFF', name: 'AiInputArea' });
  uiDivider(c, 0, H - 24 - 50 - 59, W, '#F2ECE4');
  var wrap = uiPanel(inp, 12, 12, W - 24 - 48, 34, { fill: '#FAF7F2', stroke: '#EEE3D5', strokeW: 1, radius: 17 });
  uiIconSvg(wrap, 10, 9, 16, 'message', '#9a8b78');
  uiText(wrap, 34, 9, '输入您的问题...', { size: 12, color: '#B8A088' });
  uiCircle(inp, W - 46, 12, 34, '#EFE6D8');
  uiIconSvg(inp, W - 46 + 9, 21, 16, 'send', '#FFFFFF');
}

// ---- P-M10b AI 助手·对话态（与 P-M10 同结构，展示用户/AI 气泡 + 加载中 + 错误态）----
function drawPM10b(frame) {
  var c = drawMobileShell(frame, { reserve: 50 });
  var W = frame.width, H = frame.height;
  // 顶部信息区（与 P-M10 一致）
  var head = uiPanel(c, 0, 0, W, 48, { fill: '#FFFFFF', name: 'AiHeader' });
  uiDivider(c, 0, 47, W, '#F2ECE4');
  uiIconChip(head, 14, 9, 30, 'robot', { bg: GRAD.goldBtn, fg: '#FFFFFF', radius: 15, iconSize: 20 });
  uiText(head, 52, 8, 'AI 助手', { size: 14, weight: 600, color: '#3A2C1E' });
  uiCircle(head, 55, 31, 5, '#7bbf8a');
  uiText(head, 65, 26, '智能课程助手 · 模拟对话（未接入真实 AI）', { size: 10, color: '#B8A088', w: W - 130 });
  uiTag(head, W - 62, 12, '清空', { size: 11, color: '#8b7355', bg: '#FFFFFF', border: '#E6DCCD', radius: 999, h: 22 });

  var y = 62;
  // 用户消息（右对齐气泡，原型 .ai-msg.user .ai-bubble 金色渐变）
  uiPanel(c, W - 12 - 216, y, 216, 44, { fill: GRAD.goldBtn, radius: 14 });
  uiText(c, W - 12 - 204, y + 13, '我的课卡还剩多少次？', { size: 12, color: '#FFFFFF' });
  y += 56;
  // AI 回复（左对齐气泡 + ai-av robot 头像，金色渐变底）
  uiIconChip(c, 12, y + 6, 26, 'robot', { bg: GRAD.goldBtn, fg: '#FFFFFF', radius: 13, iconSize: 17 });
  uiPanel(c, 46, y, W - 58, 84, { fill: '#FFFFFF', stroke: '#EFE6D8', strokeW: 1, radius: 14 });
  uiText(c, 60, y + 14, '您当前使用的次卡剩余 7 次（共 10 次）。\n可在「我的 → 我的会员卡」查看有效期与使用记录。', { size: 12, color: '#5A4A38', w: W - 86 });
  y += 96;
  // 用户消息 2（触发演示错误态：输入以「错误/异常/error/报错」开头）
  uiPanel(c, W - 12 - 140, y, 140, 44, { fill: GRAD.goldBtn, radius: 14 });
  uiText(c, W - 12 - 128, y + 13, '报错测试', { size: 12, color: '#FFFFFF' });
  y += 56;
  // AI 错误气泡（原型 aiResolve 错误分支文案，err 类气泡为纯文本）
  uiIconChip(c, 12, y + 6, 26, 'robot', { bg: GRAD.goldBtn, fg: '#FFFFFF', radius: 13, iconSize: 17 });
  uiPanel(c, 46, y, W - 58, 62, { fill: '#fdf1f0', stroke: '#f3d6d3', strokeW: 1, radius: 14 });
  uiText(c, 60, y + 14, '抱歉，本次请求出现异常（演示用错误状态）。请稍后重试。', { size: 12, color: '#c0392b', w: W - 86 });
  y += 74;
  // 加载中（三点，原型 .ai-dots）
  uiPanel(c, 46, y, 74, 32, { fill: '#FFFFFF', stroke: '#EFE6D8', strokeW: 1, radius: 16 });
  uiText(c, 60, y + 10, '· · ·', { size: 14, weight: 700, color: '#c9a66b' });
  y += 44;
  uiText(c, 12, y, '错误态演示：原型 aiResolve 在输入以「错误/异常/error/报错」开头时追加 err 气泡；本页展示对话 + 加载中 + 错误态三种消息样式。', { size: 10, color: UI.C.t3, w: W - 24 });
  // 底部固定输入区（TabBar 之上；message 图标 + placeholder + send 图标）
  var inp = uiPanel(c, 0, H - 24 - 50 - 58, W, 58, { fill: '#FFFFFF', name: 'AiInputArea' });
  uiDivider(c, 0, H - 24 - 50 - 59, W, '#F2ECE4');
  var wrap = uiPanel(inp, 12, 12, W - 24 - 48, 34, { fill: '#FAF7F2', stroke: '#EEE3D5', strokeW: 1, radius: 17 });
  uiIconSvg(wrap, 10, 9, 16, 'message', '#9a8b78');
  uiText(wrap, 34, 9, '输入您的问题...', { size: 12, color: '#B8A088' });
  uiCircle(inp, W - 46, 12, 34, GRAD.goldBtn);
  uiIconSvg(inp, W - 46 + 9, 21, 16, 'send', '#FFFFFF');
}

// ===========================================================================
// 4e) Overlay 绘制（10 个规范弹窗 + 2 个脚手架帧）
// ===========================================================================
function drawOverlay(frame, id) {
  var W = frame.width, H = frame.height;
  if (id === 'P-A3') {
    var m = drawModal(frame, { title: '发放会员卡', tag: 'P-A3' });
    var y = m.body;
    y = formRow(frame, 18, y, W - 36, '学员', '张小明', { req: true });
    y = formRow(frame, 18, y, W - 36, '会员卡产品', '拉丁舞期限卡  ▾', { req: true });
    y = formRow(frame, 18, y, W - 36, '卡号', 'MC20261010001（自动生成）', {});
    uiText(frame, 18, y, '备注', { size: 13, color: UI.C.t2 });
    uiPanel(frame, 18, y + 20, W - 36, 46, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
    modalFoot(frame, m, '取消', '确定');
    return;
  }
  if (id === 'P-A4') {
    var m4 = drawModal(frame, { title: '详情', tag: 'P-A4' });
    var gy = m4.body - 4;
    var items = [['会员卡号', 'MC20260910002', true], ['产品名称', '拉丁舞次卡', false], ['计费方式', '次卡', false], ['学员', '张小明', false], ['总次数', '10', false], ['已用次数', '3', false], ['剩余次数', '7', false], ['状态', '正常', false], ['有效期', '2026-09-10 ~ 2026-12-09', true], ['创建时间', '2026-09-10 10:02:00', true], ['更新时间', '2026-10-10 09:00:00', true]];
    var gw = W - 36, gw2 = Math.round(gw / 2), itemH = 34, rowIdx = 0, colIdx = 0;
    var grid = uiPanel(frame, 18, gy, gw, 0, {});
    grid.resize(gw, 1);
    var rowsCount = 0, kk;
    // 逐项布局（span2 独占一行）
    var yy = gy;
    var i2 = 0;
    var usedCols = 0;
    var rowTop = gy, rowH = itemH;
    while (i2 < items.length) {
      var it = items[i2];
      var span = it[2] ? 2 : 1;
      if (usedCols + span > 2) { yy += rowH; rowTop = yy; usedCols = 0; rowH = itemH; }
      var bx = 18 + usedCols * gw2;
      var bw = span === 2 ? gw : gw2;
      uiRect(frame, bx, rowTop, bw, itemH, { fill: '#FAFAFA', stroke: UI.C.borderL, strokeW: 1 });
      uiText(frame, bx + 12, rowTop + 10, it[0], { size: 12, color: UI.C.t3 });
      uiText(frame, bx + 96, rowTop + 10, it[1], { size: 12, color: UI.C.t1, w: bw - 108 });
      usedCols += span;
      if (usedCols >= 2) { yy += rowH; rowTop = yy; usedCols = 0; }
      i2++;
    }
    yy += itemH + 12;
    uiText(frame, 18, yy, '原型扩展 · 真实详情弹窗不含流水（真实有 getTransactions 端点未接入）', { size: 11, color: UI.C.t3 });
    yy += 22;
    var rows = [['2026-10-10 09:00', '消费', '-1', '7', '拉丁舞基础 10-10'], ['2026-10-08 20:00', '消费', '-1', '8', '拉丁舞基础 10-08']];
    uiTable(frame, 18, yy, W - 36, [{ t: '时间', w: 150 }, { t: '类型', w: 80 }, { t: '变动', w: 70 }, { t: '余额', w: 70 }, { t: '关联课程', w: W - 36 - 370 }], rows, { name: 'P-A4 Txn', rowH: 32, headH: 34 });
    uiText(frame, 18, H - 40, '申请退款（灰置 · 依赖 F6.1）', { size: 11, color: UI.C.t4 });
    modalFoot(frame, m4, '关闭', '查看关联预约');
    return;
  }
  if (id === 'OV-PRODUCT') {
    var mp = drawModal(frame, { title: '新增卡产品', tag: 'P-A1' });
    var yp = mp.body;
    yp = formRow(frame, 18, yp, W - 36, '产品名称', '请输入产品名称', { req: true, placeholder: true });
    yp = formRow(frame, 18, yp, W - 36, '计费方式', '次卡  ▾', { req: true });
    yp = formRow(frame, 18, yp, W - 36, '包含次数', '10', { req: true });
    yp = formRow(frame, 18, yp, W - 36, '有效天数', '90', { req: true });
    yp = formRow(frame, 18, yp, W - 36, '价格(元)', '980', { req: true });
    yp = formRow(frame, 18, yp, W - 36, '适用课程类型', '常规课  ▾', { req: true, hint: '必填项：选择后学员只能预约该课程类型的课程' });
    uiText(frame, 18, yp, '描述', { size: 13, color: UI.C.t2 });
    uiPanel(frame, 18, yp + 20, W - 36, 40, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
    modalFoot(frame, mp, '取消', '确定');
    return;
  }
  if (id === 'OV-BATCH-DELETE' || id === 'OV-BATCH-CANCEL') {
    var isDel = id === 'OV-BATCH-DELETE';
    var mb = drawModal(frame, { title: isDel ? '批量删除' : '批量作废', tag: 'P-A1' });
    var yb = mb.body;
    uiText(frame, 18, yb, (isDel ? '确定要删除以下 ' : '确定要作废以下 ') + '2 个' + (isDel ? '卡类型' : '会员卡') + '吗？', { size: 13, color: UI.C.t1 });
    yb += 30;
    var listItems = isDel ? ['拉丁舞次卡（次卡）', '拉丁舞期限卡（期卡）'] : ['MC20261010001 · 张小明', 'MC20260910002 · 张小明'];
    for (var li2 = 0; li2 < listItems.length; li2++) {
      uiText(frame, 28, yb + li2 * 24, '· ' + listItems[li2], { size: 12, color: UI.C.t2 });
    }
    yb += 24 * listItems.length + 8;
    uiText(frame, 18, yb, isDel ? '注意：只有已下架的卡类型才能删除，删除后将移入回收站。' : '注意：作废后不可恢复，冻结/作废前应提示受影响预约。', { size: 11, color: UI.C.danger, w: W - 36 });
    yb += 34;
    if (!isDel) {
      uiText(frame, 18, yb, '作废原因', { size: 13, color: UI.C.t2 });
      uiPanel(frame, 18, yb + 20, W - 36, 40, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
    }
    modalFoot(frame, mb, '取消', '确定', { danger: !isDel });
    return;
  }
  if (id === 'OV-FREEZE') {
    var mf = drawModal(frame, { title: '冻结会员卡', tag: 'P-A2' });
    var yf = mf.body;
    yf = formRow(frame, 18, yf, W - 36, '冻结天数（1-365）', '7', { req: true, hint: '默认 7 天；冻结期间有效期暂停计算' });
    uiText(frame, 18, yf, '冻结原因', { size: 13, color: UI.C.t2 });
    uiPanel(frame, 18, yf + 20, W - 36, 60, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
    modalFoot(frame, mf, '取消', '确定冻结');
    return;
  }
  if (id === 'OV-RENEWAL') {
    var mr = drawModal(frame, { title: '续卡提示', tag: '后端 409' });
    var yr = mr.body;
    uiText(frame, 18, yr, '检测到学员已存在同课程类型的有效会员卡，无法重复发卡。', { size: 13, color: UI.C.t1, w: W - 36 });
    yr += 44;
    var cb = uiPanel(frame, 18, yr, W - 36, 84, { fill: UI.C.bgPage, radius: 6 });
    var rows3 = [['已有卡号', 'MC20261005008'], ['状态', '正常 (ACTIVE)'], ['到期日', '2026-11-04']];
    for (var ri = 0; ri < rows3.length; ri++) {
      uiText(cb, 12, 10 + ri * 24, rows3[ri][0], { size: 12, color: UI.C.t3 });
      uiText(cb, W - 36 - 140, 10 + ri * 24, rows3[ri][1], { size: 12, color: UI.C.t1 });
    }
    yr += 96;
    uiText(frame, 18, yr, '新卡生效时间须晚于旧卡到期次日，系统自动设为最早可行生效日。', { size: 11, color: '#A9702A', w: W - 36 });
    modalFoot(frame, mr, '取消', '继续续卡');
    return;
  }
  if (id === 'OV-CONFLICT') {
    var mc = drawModal(frame, { title: '冻结到期 · 课程冲突', tag: 'P-A2' });
    var yc = mc.body;
    var wb2 = uiPanel(frame, 18, yc, W - 36, 52, { fill: UI.C.warnBg, stroke: '#E0B070', strokeW: 1, radius: 6 });
    uiText(wb2, 12, 8, '该卡冻结期内已安排课程，解冻将产生冲突', { size: 12, weight: 700, color: '#A9702A' });
    uiText(wb2, 12, 28, '请选择处理方式：作废冲突卡 或 继续冻结冲突卡 365 天', { size: 11, color: '#A9702A', w: W - 72 });
    yc += 64;
    var opts2 = ['解冻并作废冲突卡', '解冻并冻结冲突卡（365 天）'];
    for (var oi2 = 0; oi2 < opts2.length; oi2++) {
      uiCircle(frame, 20, yc + oi2 * 30, 16, '#FFFFFF', 1);
      uiCircle(frame, 20, yc + oi2 * 30, 16, oi2 === 0 ? UI.C.adminPri : '#FFFFFF', oi2 === 0 ? 1 : 1);
      if (oi2 === 0) uiCircle_ring(frame, 20, yc + oi2 * 30, 16);
      uiText(frame, 46, yc + oi2 * 30 + 1, opts2[oi2], { size: 12, color: UI.C.t1 });
    }
    yc += 68;
    uiText(frame, 18, yc, '备注', { size: 13, color: UI.C.t2 });
    uiPanel(frame, 18, yc + 20, W - 36, 60, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
    modalFoot(frame, mc, '取消', '确定');
    return;
  }
  if (id === 'P-M7') {
    var width = W;
    uiPanel(frame, 0, 0, W, H, { fill: '#FFFFFF', radius: 12, name: 'ModalBox' });
    uiText(frame, 16, 14, '取消预约确认', { size: 15, weight: 600, color: '#333333' });
    uiText(frame, W - 28, 14, '✕', { size: 13, color: UI.C.t3 });
    uiDivider(frame, 0, 42, W);
    var cb2 = uiPanel(frame, 14, 54, W - 28, 120, { fill: UI.C.bgPage, radius: 6 });
    var rows4 = [['排期', '拉丁舞基础 2026-10-10'], ['原卡', 'MC20260910002'], ['当前剩余', '7 次'], ['取消后回补', '+1 次 → 8 次']];
    for (var r4 = 0; r4 < rows4.length; r4++) {
      uiText(cb2, 12, 10 + r4 * 26, rows4[r4][0], { size: 12, color: UI.C.t3 });
      uiText(cb2, 100, 10 + r4 * 26, rows4[r4][1], { size: 12, color: r4 === 3 ? UI.C.ok : UI.C.t1, w: W - 130 });
    }
    uiText(frame, 14, 186, '取消原因', { size: 12, color: UI.C.t2 });
    uiPanel(frame, 14, 204, W - 28, 52, { fill: '#FFFFFF', stroke: UI.C.border, strokeW: 1, radius: 4 });
    uiBtn(frame, W - 194, H - 44, 84, 30, '再想想', {});
    uiBtn(frame, W - 100, H - 44, 84, 30, '确认取消', { bg: UI.C.danger, border: null, fg: '#FFFFFF' });
    return;
  }
  if (id === 'OV-CARDSEL') {
    // P-M4 选卡底部弹窗（严格对齐原型 .card-selector-popup：header + card-option 列表 + footer「确定」）
    uiPanel(frame, 0, 0, W, H, { fill: '#FFFFFF', radius: 16, name: 'CardSelectorPopup' });
    uiText(frame, 16, 14, '选择会员卡', { size: 15, weight: 600, color: '#3A2C1E' });
    uiText(frame, W - 30, 14, '✕', { size: 13, color: UI.C.t3 });
    uiDivider(frame, 0, 44, W);
    // opts = bookCardOptions()：可用（选中）/ 已用完 / 冻结中 / 有效期重叠，reason 直接来自原型
    var csel = [
      { name: '拉丁舞次卡', remain: '剩余 7/10 次', no: 'MC20260910002', type: '次卡', sel: true, disabled: false, reason: '' },
      { name: '拉丁舞次卡', remain: '剩余 0/10 次', no: 'MC20260701003', type: '次卡', sel: false, disabled: true, reason: '已用完' },
      { name: '拉丁舞次卡', remain: '剩余 8/10 次', no: 'MC20260920005', type: '次卡', sel: false, disabled: true, reason: '冻结中' }
    ];
    var ry = 52;
    for (var ck = 0; ck < csel.length; ck++) {
      var o = csel[ck];
      uiPanel(frame, 12, ry, W - 24, 60, { fill: o.sel ? 'rgba(201,166,107,.10)' : '#FFFFFF', stroke: o.sel ? UI.C.gold : '#EFE6D8', strokeW: 1, radius: 10, opacity: o.disabled ? 0.55 : 1 });
      // card-radio：圆形单选（选中=radio-checked 金色实心圆）
      uiRect(frame, 22, ry + 22, 16, 16, { fill: '#FFFFFF', stroke: o.sel ? UI.C.gold : '#D9D0C2', strokeW: 1, radius: 8 });
      if (o.sel) uiRect(frame, 26, ry + 26, 8, 8, { fill: UI.C.gold, radius: 4 });
      uiText(frame, 46, ry + 10, o.name, { size: 13, weight: 600, color: '#333333' });
      uiText(frame, 46, ry + 27, o.remain + (o.reason ? ' · ' + o.reason : ''), { size: 10, color: o.disabled ? UI.C.danger : UI.C.t3, w: W - 160 });
      uiText(frame, 46, ry + 41, '卡号 ' + o.no, { size: 10, color: UI.C.t4 });
      uiTag(frame, W - 24 - 56, ry + 20, o.type, { size: 10, color: UI.C.warn, bg: 'rgba(230,162,60,.16)', border: null, radius: 8, h: 18 });
      ry += 68;
    }
    uiText(frame, 16, ry + 8, '不可用行灰置（reason 来自原型 bookCardOptions：已过期/已作废/冻结中/已用完/有效期重叠），选中行显示金色单选与描边', { size: 10, color: UI.C.t3, w: W - 32 });
    uiDivider(frame, 0, H - 60, W);
    uiBtn(frame, 16, H - 48, W - 32, 36, '确定', { bg: GRAD.goldBtn, border: null, fg: '#FFFFFF', radius: 18, size: 13, weight: 600 });
    return;
  }
  // 脚手架帧：通用二次确认
  var mg = drawModal(frame, { title: '确认操作', tag: '通用' });
  uiText(frame, 18, mg.body, '确定要执行该操作吗？此操作不可撤销。', { size: 13, color: UI.C.t2, w: W - 36 });
  uiBtn(frame, W - 210, H - mg.footH + 12, 90, 30, '取消', {});
  uiBtn(frame, W - 110, H - mg.footH + 12, 90, 30, '确认', { bg: GRAD.adminBtn, border: null, fg: '#FFFFFF' });
}

function uiCircle_ring(parent, x, y, d) {
  var e = figma.createEllipse();
  e.resize(d - 8, d - 8);
  e.fills = [];
  e.strokes = [solid('#FFFFFF')];
  e.strokeWeight = 3;
  parent.appendChild(e);
  e.x = x + 4; e.y = y + 4;
  return e;
}

// ===========================================================================
// 4f) 决策便签挂载表（仅放可确信位置：D2/D7/D8 黄占位；D1/D3/D4/D5/D9 绿已确认）
// ===========================================================================
function drawScreen(frame, id) {
  var map = {
    'P-A1': drawPA1, 'P-A2': drawPA2, 'P-A5': drawPA5, 'P-A6': drawPA6, 'P-T1': drawPT1,
    'P-M1': drawPM1, 'P-M2': drawPM2, 'P-M3': drawPM3, 'P-M4': drawPM4, 'P-M5': drawPM5,
    'P-M6': drawPM6, 'P-M8': drawPM8, 'P-M9': drawPM9, 'P-M10': drawPM10,
    // 状态屏（原型有但首版插件未画）：无效课卡 / 空状态 / 预约失败 / 预约空态 / AI 对话态
    'P-M1c': drawPM1c, 'P-M1d': drawPM1d, 'P-M5b': drawPM5b, 'P-M6b': drawPM6b, 'P-M10b': drawPM10b,
    // 长页「滚动续帧」：同一绘制器 + 垂直偏移（offset = 折叠线位置）
    'P-M8b': function (f) { drawPM8(f, SPEC.scrollSplit['P-M8'].offset); },
    'P-M1b': function (f) { drawPM1(f, SPEC.scrollSplit['P-M1'].offset); }
  };
  var fn = map[id];
  if (!fn) { console.warn('无绘制器：' + id); return; }
  fn(frame);
}


function createFrames(pageById) {
  var frameNodes = {};
  var nameNodes = {};
  var framePage = {}; // frame id -> 紧凑模式 page id（用于把 reaction 目标锚定到同页）
  var cursors = {};   // pageId -> {x,y,rowH}

  function groupOf(pageId) { return SPEC.pageRemap[pageId] || pageId; }

  function placeFrame(id, name, pageId, w, h) {
    var page = pageById[pageId];
    if (!page) { console.warn('找不到 Page：' + pageId + '，Frame ' + id + ' 跳过。'); return null; }
    var f = figma.createFrame();
    f.name = name;
    f.resize(w, h);
    page.appendChild(f);
    // 网格排布，避免同页 Frame 重叠
    var c = cursors[pageId] || (cursors[pageId] = { x: 0, y: 0, rowH: 0 });
    // 网格排布：GAP 340 同时充当右侧「交互热点面板」槽位（面板宽 300 + 20 边距），避免面板压到相邻 Frame
    var GAP = 340, MAXROW = 6200;
    if (c.x > 0 && c.x + w > MAXROW) { c.x = 0; c.y += c.rowH + GAP; c.rowH = 0; }
    f.x = c.x; f.y = c.y;
    c.x += w + GAP;
    if (h > c.rowH) c.rowH = h;
    // 不再在 Frame 内画「标题标签」：Frame 名由 Figma 画布自身显示，内嵌标题会与真实 UI 重叠
    frameNodes[id] = f;
    framePage[id] = pageId;
    nameNodes[name] = f;
    nameNodes[id] = f;
    return f;
  }

  // 逐帧绘制：单帧失败只记录，不中断其余帧（`frames` 步骤整体不再因一屏报错而全灭）
  function paint(node, id, kind) {
    if (!node) return node;
    try {
      if (kind === 'overlay') drawOverlay(node, id); else drawScreen(node, id);
    } catch (e) {
      console.warn('UI 绘制失败（' + id + '）：' + (e && e.message ? e.message : e));
    }
    return node;
  }

  for (var i = 0; i < SPEC.screenFrames.length; i++) {
    var sf = SPEC.screenFrames[i];
    paint(placeFrame(sf.id, sf.name, groupOf(sf.page), sizeW(sf.size), sizeH(sf.size)), sf.id, 'screen');
  }
  // 长页「滚动续帧」：超出可视窗口的小程序页补一帧承接折叠线以下内容（同页、同设备尺寸、带 TabBar）
  var splitIds = Object.keys(SPEC.scrollSplit || {});
  for (var s = 0; s < splitIds.length; s++) {
    var sp = SPEC.scrollSplit[splitIds[s]];
    paint(placeFrame(sp.id, sp.name, groupOf(sp.page), sizeW(sp.size), sizeH(sp.size)), sp.id, 'screen');
  }

  for (var j = 0; j < SPEC.overlayFrames.length; j++) {
    var of = SPEC.overlayFrames[j];
    paint(placeFrame(of.id, of.name, groupOf(of.page), sizeW(of.size), sizeH(of.size)), of.id, 'overlay');
  }

  // 脚手架帧：OV-CONFIRM（通用二次确认 / 联系方式弹窗宿主）
  // 说明：规范 Overlay Frame = 10；各端页各建 1 个脚手架帧承接「ConfirmDialog / 联系方式弹窗」
  //       等通用目标，确保 reaction 目标与源 Frame 同 Page。该帧不属于 frames.json 的 10 个规范 Overlay。
  var ovConfirmByPage = {};
  var adminConfirm = placeFrame('OV-CONFIRM', 'OV-CONFIRM 通用二次确认（管理端·脚手架帧）', '01', 420, 220);
  if (adminConfirm) { ovConfirmByPage['01'] = adminConfirm; paint(adminConfirm, 'OV-CONFIRM', 'overlay'); }
  var miniConfirm = placeFrame('OV-CONFIRM-MINI', 'OV-CONFIRM 通用二次确认（小程序·脚手架帧）', '02', 320, 200);
  if (miniConfirm) { ovConfirmByPage['02'] = miniConfirm; paint(miniConfirm, 'OV-CONFIRM-MINI', 'overlay'); }
  console.log('规范 Overlay = 10；另建 2 个脚手架帧 OV-CONFIRM（管理端/小程序各 1），合计 12 个 Overlay。');

  return { frameNodes: frameNodes, nameNodes: nameNodes, framePage: framePage, ovConfirmByPage: ovConfirmByPage, pages: pageById };
}

// ===========================================================================
// 5b) 底部导航：原型 index.html 的 4 个同级 Tab（首页/排期/AI 助手/我的）各自选中
// ===========================================================================
function addTabBars(api, components) {
  var map = SPEC.tabBarPages; // { 'P-M8':'home', 'P-M3':'schedule', 'P-M10':'ai', 'P-M10b':'ai', 'P-M9':'profile' }
  var ids = Object.keys(map);
  for (var i = 0; i < ids.length; i++) {
    var fid = ids[i];
    var frame = api.frameNodes[fid];
    var comp = components.variantComponents['TabBar|active=' + map[fid]];
    if (!frame || !comp) { console.warn('TabBar 跳过：' + fid); continue; }
    var inst = comp.createInstance();
    frame.appendChild(inst);
    inst.x = 0;
    inst.y = frame.height - SPEC.tabbar.size.h;
  }

  // 长页「滚动续帧」同样保留 TabBar（active 取源页同值），保证续帧仍是完整设备屏
  var splitIds = Object.keys(SPEC.scrollSplit || {});
  for (var s = 0; s < splitIds.length; s++) {
    var srcId = splitIds[s];
    var splitFrame = api.frameNodes[SPEC.scrollSplit[srcId].id];
    var splitComp = components.variantComponents['TabBar|active=' + map[srcId]];
    // 源页不是 TabBar 页（如 P-M1）→ 其续帧同样无 TabBar，静默跳过而非告警
    if (!map[srcId]) continue;
    if (!splitFrame || !splitComp) { console.warn('TabBar 跳过（续帧）：' + SPEC.scrollSplit[srcId].id); continue; }
    var splitInst = splitComp.createInstance();
    splitFrame.appendChild(splitInst);
    splitInst.x = 0;
    splitInst.y = splitFrame.height - SPEC.tabbar.size.h;
  }
}

// ===========================================================================
// 6) Prototype reaction（挂在源 Frame 内的小按钮上）+ type=none 灰置占位
// ===========================================================================
function navFor(type) {
  if (type === 'Overlay') return 'OVERLAY';
  if (type === 'Navigate To') return 'NAVIGATE';
  if (type === 'Overlay + Navigate') return 'OVERLAY';   // 先弹确认，本插件以 Overlay 起步
  if (type === 'Overlay + Change To') return 'OVERLAY';
  if (type === 'Change To') return 'CHANGE_TO';
  if (type === 'Back') return 'BACK';
  return 'NAVIGATE';
}

function defaultTransition() {
  return { type: 'DISSOLVE', easing: { type: 'EASE_OUT' }, duration: 0.2 };
}

function resolveTarget(to, frameNodes, nameNodes, ovConfirmByPage, srcPage) {
  if (!to) return null;
  if (frameNodes[to]) return frameNodes[to];       // to 为 Frame id
  if (nameNodes[to]) return nameNodes[to];         // to 为 Frame 名称
  // 通用二次确认宿主：取与源 Frame 同 Page 的脚手架帧（保证 reaction 不跨 Page）
  var confirm = ovConfirmByPage[srcPage] || ovConfirmByPage['01'] || null;
  if (String(to).indexOf('/') >= 0) {              // 多目标，如 "P-M8/P-M3/P-M10/P-M9"
    var parts = String(to).split('/');
    for (var i = 0; i < parts.length; i++) { if (frameNodes[parts[i]]) return frameNodes[parts[i]]; }
  }
  if (String(to).indexOf('ConfirmDialog') >= 0) return confirm;
  if (String(to).indexOf('联系方式') >= 0) return confirm;
  if (String(to).indexOf('EmptyState') >= 0) return confirm; // Change To 已在上面拦为指向自身
  if (String(to).indexOf('编辑') >= 0) return frameNodes['OV-PRODUCT'];
  if (String(to).indexOf('冻结到期') >= 0 || String(to).indexOf('冲突') >= 0) return frameNodes['OV-CONFLICT'];
  if (String(to).indexOf('续卡') >= 0) return frameNodes['OV-RENEWAL'];
  if (String(to).indexOf('冻结') >= 0) return frameNodes['OV-FREEZE'];
  return confirm;
}

function buildReaction(c, frameNodes, nameNodes, ovConfirmByPage, srcPage, srcNode) {
  var nav = navFor(c.type);
  if (nav === 'BACK') {
    return { trigger: { type: 'ON_CLICK' }, actions: [{ type: 'BACK' }] };
  }
  if (nav === 'CHANGE_TO') {
    // Change To：destinationId 指向自身 Frame
    return { trigger: { type: 'ON_CLICK' }, actions: [{ type: 'NODE', destinationId: srcNode.id, navigation: 'CHANGE_TO', transition: defaultTransition() }] };
  }
  if (!c.to) {
    // 兜底：无目标的非 none 连接 → CHANGE_TO 自身，保证每条非 none 连接都有可达反应
    return { trigger: { type: 'ON_CLICK' }, actions: [{ type: 'NODE', destinationId: srcNode.id, navigation: 'CHANGE_TO', transition: defaultTransition() }] };
  }
  var target = resolveTarget(c.to, frameNodes, nameNodes, ovConfirmByPage, srcPage);
  if (!target) return null;
  var action = { type: 'NODE', destinationId: target.id, navigation: nav, transition: defaultTransition() };
  if (nav === 'OVERLAY') action.overlayRelativePosition = { x: 0, y: 0 };
  return { trigger: { type: 'ON_CLICK' }, actions: [action] };
}

function createTriggerButton(label) {
  var btn = figma.createFrame();
  btn.name = 'trigger: ' + label;
  btn.fills = [solid('#F5F7FA')];
  btn.cornerRadius = 4;
  btn.strokes = [solid('#DCDFE6')];
  btn.strokeWeight = 1;
  var t = makeText(label, 12, 400, '#606266');
  btn.appendChild(t);
  var w = Math.max(120, Math.min(360, Math.round(t.width) + 16));
  btn.resize(w, 28);
  t.x = 8;
  t.y = Math.max(0, Math.round((28 - t.height) / 2));
  return btn;
}

// 灰置占位：interactions.json 中 type=none 的禁用项（AC6）——真实存在于此代码路径
function createDisabledPlaceholder(label) {
  var box = figma.createFrame();
  box.name = 'disabled: ' + label;
  box.fills = [solid('#F0F0F0')];
  box.cornerRadius = 4;
  box.strokes = [solid('#E4E7ED')];
  box.strokeWeight = 1;
  box.resize(200, 44);
  var l1 = makeText(label, 11, 400, '#909399');
  box.appendChild(l1);
  l1.x = 8; l1.y = 6;
  var l2 = makeText('待开发 · 不可用', 12, 500, '#b0b3b8');
  box.appendChild(l2);
  l2.x = 8; l2.y = 24;
  return box;
}

async function addReactions(api) {
  var frameNodes = api.frameNodes;
  var nameNodes = api.nameNodes;
  var ovConfirmByPage = api.ovConfirmByPage;
  var framePage = api.framePage;
  var panels = {};    // 源 Frame id -> 独立「交互热点」面板
  var counters = {};
  var reactionCount = 0;
  var disabledCount = 0;

  // 热点面板：放在源 Frame 右侧槽位（createFrames 已按 GAP=340 预留），绝不覆盖已绘制 UI
  function panelFor(srcId) {
    if (panels[srcId]) return panels[srcId];
    var src = frameNodes[srcId];
    var p = figma.createFrame();
    p.name = '交互热点 · ' + srcId;
    p.resize(300, 1);
    p.fills = [solid('#FFFFFF')];
    p.strokes = [solid('#DCDFE6')];
    p.strokeWeight = 1;
    p.cornerRadius = 6;
    try { p.clipsContent = false; } catch (e) { /* 忽略 */ }
    (src.parent || figma.currentPage).appendChild(p);
    p.x = src.x + src.width + 20;
    p.y = src.y;
    var hd = makeText('交互热点 · 点击跳转', 11, 600, '#909399');
    p.appendChild(hd);
    hd.x = 10; hd.y = 8;
    panels[srcId] = p;
    return p;
  }

  for (var i = 0; i < SPEC.connections.length; i++) {
    var c = SPEC.connections[i];
    var src = frameNodes[c.from];
    if (!src) { console.warn('跳过：找不到源 Frame ' + c.from); continue; }
    var srcPage = framePage[c.from];
    var n = counters[c.from] || 0;
    counters[c.from] = n + 1;
    var panel = panelFor(c.from);
    var y = 30 + n * 50;

    // 放宽规则：所有 type !== 'none' 的连接都生成按钮 + reaction
    // （其中 to 为 null 的 'Change To' 连接由 buildReaction 落到 CHANGE_TO → 自身 Frame）
    if (c.type !== 'none') {
      var btn = createTriggerButton(c.trigger);
      panel.appendChild(btn);
      btn.x = 10;
      btn.y = y;
      var reaction = buildReaction(c, frameNodes, nameNodes, ovConfirmByPage, srcPage, src);
      if (reaction) {
        try {
          await btn.setReactionsAsync([reaction]);
          reactionCount++;
        } catch (e) {
          console.warn('reaction 设置失败（' + c.from + ' / ' + c.trigger + '）：' + (e && e.message ? e.message : e));
        }
      }
    } else if (c.type === 'none') {
      var ph = createDisabledPlaceholder(c.trigger);
      panel.appendChild(ph);
      ph.x = 10;
      ph.y = y;
      disabledCount++;
    }
  }

  // 按实际条目数收紧面板高度（30 头部 + 每行 50 + 10 底部留白）
  var ids = Object.keys(panels);
  for (var k = 0; k < ids.length; k++) {
    panels[ids[k]].resize(300, 30 + (counters[ids[k]] || 0) * 50 + 10);
  }

  console.log('Prototype reaction 条数 = ' + reactionCount + '；灰置占位（type=none）条数 = ' + disabledCount
    + '；热点面板数 = ' + ids.length + '（每源 Frame 一个，置于 Frame 右侧，不覆盖 UI）。');
  return { reactionCount: reactionCount, disabledCount: disabledCount, hotspots: ids.length };
}

// ===========================================================================
// 主流程：async IIFE；每段 try/catch 独立续跑，单段失败不再整体中断
// ===========================================================================
(async function main() {
  var summary = null;
  var failures = [];

  // 分段执行器：任一段抛错只记录并继续后续段（Page 准备段除外，失败则无 Page 可继续）
  async function step(label, fn) {
    try { return await fn(); }
    catch (e) {
      var m = (e && e.message ? e.message : String(e));
      failures.push(label + ' → ' + m);
      console.warn('步骤失败（已续跑后续步骤）：' + label + ' → ' + m);
      return null;
    }
  }

  try {
    await figma.loadAllPagesAsync();

    await setupFonts();

    // Page 准备失败则无法继续（后续所有节点都依赖 Page）；把真实原因带进 toast
    var pageById = await step('pages', function () { return preparePages(); });
    if (!pageById) throw new Error('Page 准备失败，无法继续：' + (failures[0] || '原因未知'));

    var varResult = (await step('variables', function () { return createVariables(SPEC.colors); })) || { degraded: true, count: 0 };
    var textCount = (await step('textStyles', function () { return createTextStyles(); })) || 0;
    var effectCount = (await step('effectStyles', function () { return createEffectStyles(); })) || 0;
    var components = (await step('components', function () { return createComponents(pageById['10']); })) || { variantComponents: {}, sets: {} };
    var api = await step('frames', function () { return createFrames(pageById); });
    if (api) addTabBars(api, components);
    var reactionResult = api ? ((await step('reactions', function () { return addReactions(api); })) || { reactionCount: 0, disabledCount: 0 })
                             : { reactionCount: 0, disabledCount: 0 };

    summary = {
      pages: SPEC.pageGroups.length,
      screenFrames: SPEC.screenFrames.length,
      overlayFrames: SPEC.overlayFrames.length, // 10 规范 Overlay
      overlayScaffolds: 2,                      // OV-CONFIRM 各端 1
      componentSets: Object.keys(components.sets).length,
      textStyles: textCount,
      effectStyles: effectCount,
      variablesOrStyles: varResult.count,
      variablesDegraded: varResult.degraded,
      reactions: reactionResult.reactionCount,
      disabledPlaceholders: reactionResult.disabledCount,
      failures: failures
    };
    console.log('生成完成：' + JSON.stringify(summary));

    var msg = 'F6.0 原型已生成（紧凑模式）：' + summary.pages + ' Page / ' + summary.screenFrames + ' Screen + '
      + (summary.overlayFrames + summary.overlayScaffolds) + ' Overlay / 组件集 ' + summary.componentSets
      + ' / reaction ' + summary.reactions + ' 条'
      + (failures.length ? '；' + failures.length + ' 项降级/失败，详见 console' : '');
    figma.notify(msg, { error: failures.length > 0 });
    figma.closePlugin();
  } catch (err) {
    figma.notify('生成失败：' + (err && err.message ? err.message : String(err)), { error: true });
    console.error('生成失败：', err);
  } finally {
    // 无需清理；Figma 无外部资源句柄
    if (summary) console.log('done.', summary);
  }
})();
