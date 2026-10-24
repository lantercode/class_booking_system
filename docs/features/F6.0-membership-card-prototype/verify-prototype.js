#!/usr/bin/env node
/*
 * F6.0 会员卡原型验证脚手架
 * ---------------------------------------------------------------
 * 用途：对 prototype/index.html 做"可执行"验证，而非静态截图比对。
 *   1) 提取内嵌 <script> 做语法检查（等价于浏览器能否解析）
 *   2) 在 DOM stub 下真实调用页面函数，逐条断言数据副作用
 *   3) 结构对齐断言（G 组）：校验原型 DOM 与真实 miniapp 页面同构，
 *      依据 docs/features/F6.0-membership-card-prototype/ui-visual-spec.md 第 6 节
 *
 * 运行：node verify-prototype.js            # 默认验证同目录 prototype/index.html
 *       node verify-prototype.js <path>    # 指定其它原型文件
 *
 * 退出码：全部通过 0；存在 FAIL 或语法错误 1（可直接接入 CI）
 *
 * 注意：本脚本验证的是"原型行为逻辑 + DOM 结构"，不覆盖真实浏览器渲染效果；
 *       视觉最终效果仍建议人工走查一次。
 */
const fs = require('fs');
const path = require('path');

const file = process.argv[2] || path.join(__dirname, 'prototype', 'index.html');
const src = fs.readFileSync(file, 'utf8');

const m = src.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.log('FAIL: no <script> block'); process.exit(1); }
const code = m[1];

/* ---- 1. 语法检查 ---- */
try { new Function(code); console.log('[1] SYNTAX OK'); }
catch (e) { console.log('[1] SYNTAX FAIL:', e.message); process.exit(1); }

/* ---- DOM stub ---- */
class El {
  constructor() { this.innerHTML = ''; this.textContent = ''; this.value = ''; this._cls = new Set(); this.className = ''; }
  get classList() {
    const s = this._cls;
    return { add: x => s.add(x), remove: x => s.delete(x), toggle: (x, f) => { f ? s.add(x) : s.delete(x); }, contains: x => s.has(x) };
  }
}
const els = {};
global.document = { getElementById: id => els[id] || (els[id] = new El()) };
global.window = {};

const api = new Function(code + `
;return {resetData,renderAll,setView,goAdmin,goStu,selectSched,pickBookCard,submitBooking,doBooking,
  openCancelModal,doCancel,tchCheckIn,tchComplete,renderTeacher,renderAdminPage,renderStuPage,
  stuTabSwitch,stuBookTab,stuSchedCat,stuSchedDate,openCardSel,closeCardSel,confirmCardSel,
  stuTab,renderTabBar,aiAsk,aiSend,aiResolve,aiClear,
  openModal,closeModal,openProductModal,openIssueModal,openCardDetail,openBatchDeleteProducts,
  openBatchCancelCards,openFreezeModal,openRenewalModal,openConflictModal,
  adminActivate,adminUnfreeze,adminFreezeConfirm,adminCancel,adminUnfreezeDo,doBatchCancelCards,
  issueDo,issueProdChange,doConflictAction,toggleCardSel,toggleAllCardSel,toggleCardStatusFilter,
  adminA1,adminA2,dg,adminCardBadge,adminStatusTag,ctTagCard,ctTagProduct,courseTypeTag,
  get CARDS(){return CARDS}, get BOOKINGS(){return BOOKINGS}, get TXNS(){return TXNS},
  get SCHEDULES(){return SCHEDULES}, get PRODUCTS(){return PRODUCTS},
  get S1R(){return S1R}, get S3R(){return S3R}, STATE, cardById, bookingById, addDays};`)();

const $ = id => els[id] || (els[id] = new El());
const html = id => $(id).innerHTML;
const text = id => $(id).textContent;
let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  PASS :: ' + name); } else { fail++; console.log('  FAIL :: ' + name + (extra ? ' -> ' + extra : '')); } }

/* ---- 流程 A 跨端预约(管理端查看 → 学员端我的卡) ---- */
console.log('[A] 跨端预约');
api.resetData(); api.setView('dual'); api.goAdmin('P-A2'); api.goStu('P-M1');
ok('A1 admin 侧边栏含 logo 与约课管理', html('admin-side').includes('logo') && html('admin-side').includes('约课管理'));
ok('A2 admin 侧边栏含图标类 .ni', html('admin-side').includes('class="ni"'));
ok('A3 admin 会员卡列表已渲染', html('admin-main').length > 200 && html('admin-main').includes('会员卡'));
ok('A4 学员卡列表使用 miniapp 圆点徽标 card-status-badge', html('stu-content').includes('card-status-badge') && html('stu-content').includes('badge-dot'));
ok('A5 C2 初始剩余 7', api.cardById('C2').remaining === 7, 'got ' + api.cardById('C2').remaining);
ok('A6 学员卡面含金色大数字 .credits-display', html('stu-content').includes('credits-display') && html('stu-content').includes('credits-remaining'));

/* ---- 流程 B 多卡切换/PENDING 可选/预扣 ---- */
console.log('[B] 多卡切换 + 次卡预扣');
api.resetData(); api.setView('student'); api.goStu('P-M3');
ok('B1 已进入排期页', api.STATE.stuPage === 'P-M3');
api.selectSched('S4'); api.goStu('P-M4'); api.pickBookCard('C2');
ok('B2 预约确认页选卡为底部弹窗(非内联列表)', html('stu-content').includes('card-selector-popup') && html('stu-content').includes('选择会员卡') && !html('stu-content').includes('stu-radio'));
api.submitBooking();
ok('B3 写操作弹二次确认', $('mask').classList.contains('show') && $('modal-box').innerHTML.includes('确认预约'));
api.doBooking();
ok('B4 次卡预扣 remaining 7->6', api.cardById('C2').remaining === 6, 'got ' + api.cardById('C2').remaining);
ok('B5 used 3->4', api.cardById('C2').used === 4, 'got ' + api.cardById('C2').used);
ok('B6 生成 CONSUME 流水', api.TXNS.C2[api.TXNS.C2.length - 1].type === '消费');
ok('B7 新增预约 BOOKED', api.BOOKINGS.length === 6 && api.BOOKINGS[5].status === 'BOOKED', 'len=' + api.BOOKINGS.length);
ok('B8 跳转结果页 P-M5', api.STATE.stuPage === 'P-M5');
ok('B9 期卡 PENDING 可选(角标待激活)', api.CARDS.some(c => c.status === 'PENDING'));

/* ---- 流程 C 取消回补 ---- */
console.log('[C] 取消回补');
api.resetData(); api.setView('student'); api.goStu('P-M6');
api.STATE.cancelBId = 'B1'; api.openCancelModal();
ok('C1 取消弹窗含回补预览 +1', $('modal-box').innerHTML.includes('回补') && $('modal-box').innerHTML.includes('+1'));
api.doCancel();
ok('C2 B1 状态 CANCELLED', api.bookingById('B1').status === 'CANCELLED');
ok('C3 次卡回补 remaining 7->8', api.cardById('C2').remaining === 8, 'got ' + api.cardById('C2').remaining);
ok('C4 生成 RESTORE 回补流水', api.TXNS.C2[api.TXNS.C2.length - 1].type === '回补');

/* ---- 流程 D 签到/完成/重复拒绝/失效卡拦截 ---- */
console.log('[D] 签到完成 + 拦截');
api.resetData(); api.setView('teacher');
ok('D1 教师端为移动风卡片(tch-head/tch-row)', html('tch-body').includes('tch-head') && html('tch-body').includes('tch-row'));
ok('D2 教师端不再使用 el-table', !html('tch-body').includes('<table'));
api.tchCheckIn('B1');
ok('D3 签到成功', api.S1R[0].status === 'CHECKED_IN' && text('toast').includes('签到成功'), text('toast'));
api.tchCheckIn('B1');
ok('D4 重复签到被拒', api.S1R[0].status === 'CHECKED_IN' && text('toast').includes('已签到'), text('toast'));
api.tchComplete('B1');
ok('D5 完成 -> COMPLETED', api.bookingById('B1').status === 'COMPLETED');
api.STATE.teacherSched = 'S3'; api.renderTeacher();
api.tchCheckIn('B3');
ok('D6 计划卡已作废签到被拦截(D9)', api.S3R[0].status === 'BOOKED' && $('mask').classList.contains('show') && $('modal-box').innerHTML.includes('签到拦截'));

/* ---- 流程 E 计划卡已作废警示 ---- */
console.log('[E] 计划卡已作废警示');
api.resetData(); api.setView('student'); api.goStu('P-M6');
ok('E1 警示条展示"计划卡已作废"', html('stu-content').includes('计划卡已作废'));
ok('E2 含换卡占位 + 联系机构', html('stu-content').includes('换卡(占位)') && html('stu-content').includes('联系机构'));
ok('E3 警示条标注"待新增"(真实页面无此条)', html('stu-content').includes('待新增') && html('stu-content').includes('计划卡已作废'));

/* ---- 流程 F 失效徽标 + 作废影响面 ---- */
console.log('[F] 失效徽标');
api.resetData(); api.setView('dual'); api.goStu('P-M1'); api.goAdmin('P-A2');
let sc = html('stu-content');
ok('F1 有效Tab含 使用中/已用完/未激活/冻结中 四类徽标', ['mst-active', 'mst-usedup', 'mst-pending', 'mst-frozen'].every(k => sc.includes(k)));
api.stuTabSwitch('invalid');
sc = html('stu-content');
ok('F2 无效Tab含 已过期/已作废 徽标且作废卡可见', sc.includes('mst-expired') && sc.includes('mst-voided') && sc.includes('card-voided'));
ok('F3 用尽样例存在(C3)', api.CARDS.some(c => c.type === 'credits' && c.status === 'ACTIVE' && c.remaining === 0));
ok('F4 admin 作废影响面占位(D3)', html('admin-main').includes('D3'));
ok('F5 admin 表格斑马纹样式已定义', src.includes('nth-child(even)'));

/* ---- 流程 G 结构对齐(ui-visual-spec.md 第 6 节 ground truth) ---- */
console.log('[G] 结构对齐(复刻真实 miniapp 页面 DOM)');
api.resetData(); api.setView('student'); api.goStu('P-M1');
sc = html('stu-content');
ok('G1 P-M1 双胶囊 Tab(有效课卡 N / 无效课卡 N)', sc.includes('filter-tabs') && sc.includes('有效课卡') && sc.includes('无效课卡') && sc.includes('tab-active'));
ok('G2 P-M1 卡面含复制图标 + 竖线分隔', sc.includes('copy-icon-btn') && sc.includes('usage-divider-line'));
ok('G3 P-M1 次卡余额 {remaining}/{total}次 同排', sc.includes('credits-remaining') && sc.includes('credits-separator') && sc.includes('credits-total') && sc.includes('credits-unit'));
ok('G4 P-M1 待激活卡行走行内"立即激活"', sc.includes('usage-with-activate') && sc.includes('activate-btn-inline'));
ok('G5 P-M1 卡片不可点击(无 P-M2 跳转入口)', !sc.includes("goStu('P-M2')"));
api.goStu('P-M3');
sc = html('stu-content');
ok('G6 P-M3 有分类筛选栏 + 日期栏', sc.includes('filter-pill') && sc.includes('date-pill') && sc.includes('pill-day-name') && sc.includes('pill-day-date'));
ok('G7 P-M3 排期卡=左时间竖排区 + 右内容区', sc.includes('schedule-time-section') && sc.includes('time-divider') && sc.includes('schedule-content'));
ok('G8 P-M3 容量口径为 booked/capacity 人', /\d+\/10人/.test(sc), sc.match(/\d+\/10人/));
ok('G9 P-M3 已约排期按钮 booked 态 + 取消时限提示', sc.includes('book-btn booked') && sc.includes('不可取消') && sc.includes('开课前90分钟内不可取消'));
api.resetData(); api.setView('student'); api.selectSched('S4');
sc = html('stu-content');
ok('G10 P-M4 选卡为底部弹窗(标题+选项+确定)', sc.includes('card-selector-popup') && sc.includes('selector-title') && sc.includes('card-option') && sc.includes('selector-footer'));
api.goStu('P-M6');
sc = html('stu-content');
ok('G11 P-M6 四个筛选 Tab(全部/待上课/上课中/已完成)', ['全部', '待上课', '上课中', '已完成'].every(t => sc.includes(t)) && sc.includes('filter-tabs'));
ok('G12 P-M6 取消受限展示"开课前 90 分钟内不可取消"', sc.includes('开课前 90 分钟内不可取消'));
api.goStu('P-M2');
ok('G13 P-M2 标注「待新增 · 真实项目不存在」', html('stu-content').includes('待新增 · 真实项目不存在'));
api.goStu('P-M5'); api.STATE.bookResult = null; api.renderStuPage();
ok('G14 P-M5 标注「待新增 · 真实项目不存在」', html('stu-content').includes('待新增 · 真实项目不存在'));
api.goAdmin('P-A5');
ok('G15 P-A5 标注「待新增」且侧边栏入口灰置', html('admin-main').includes('待新增 · 真实项目不存在') && html('admin-side').includes('nav-added') && html('admin-side').includes('chip-added'));

/* ---- 流程 H 底部导航(复刻 components/HomeTabBar.vue) + 首页/我的两页 ---- */
console.log('[H] 底部导航 + 首页/我的');
api.resetData(); api.setView('student'); api.goStu('P-M8');
let tb = html('stu-tabbar');
ok('H1 TabBar 四 Tab 文案 首页/排期/AI 助手/我的 且顺序正确', /首页[\s\S]*排期[\s\S]*AI 助手[\s\S]*我的/.test(tb) && (tb.match(/tab-text/g) || []).length === 4);
ok('H2 激活项文案 active(色 #8b7355) + 底部指示条', tb.includes('tab-text active') && tb.includes('#8b7355') && tb.includes('tab-indicator'));
ok('H3 TabBar 用真实线性图标(tab-home/tab-booking/tab-profile + ai-robot 的 path/circle)', tb.includes('<path') && tb.includes('<circle') && tb.includes('viewBox="0 0 24 24"'));
ok('H4 TabBar 在首页/排期/AI 助手/我的四页显示', !$('stu-tabbar').classList.contains('hidden'));
api.stuTab('P-M3');
ok('H5 点击排期 Tab 切页且激活态转移', api.STATE.stuPage === 'P-M3' && html('stu-tabbar').includes('tab-text active'));
api.stuTab('P-M9');
ok('H6 点击我的 Tab 切页', api.STATE.stuPage === 'P-M9' && !$('stu-tabbar').classList.contains('hidden'));
ok('H7 会员卡/预约等 pushed 页不显示 TabBar(对齐真实)', (api.goStu('P-M1'), $('stu-tabbar').classList.contains('hidden')) && (api.goStu('P-M6'), $('stu-tabbar').classList.contains('hidden')));

api.resetData(); api.setView('student'); api.goStu('P-M8');
sc = html('stu-content');
ok('H8 P-M8 首页含 navbar(地点)+Banner+师资+推荐课程+视频', sc.includes('home-navbar') && sc.includes('home-banner') && sc.includes('banner-title') && sc.includes('teachers-list') && sc.includes('course-list') && sc.includes('video-list'));
ok('H9 P-M8 推荐课程带「全部课程」入口', sc.includes('sec-more') && sc.includes('全部课程'));
api.goStu('P-M9');
sc = html('stu-content');
ok('H10 P-M9 我的含 navbar+个人信息(头像/昵称/角色/会员徽章)', sc.includes('profile-navbar') && sc.includes('profile-header') && sc.includes('avatar-ph') && sc.includes('user-name') && sc.includes('user-role-row') && sc.includes('membership-badge'));
ok('H11 P-M9 含「我的会员卡」入口→P-M1 + 「预约记录」入口→P-M6', sc.includes("goStu('P-M1')") && sc.includes("goStu('P-M6')") && sc.includes('我的会员卡') && sc.includes('预约记录'));
api.goStu('P-M1');
ok('H12 pushed 页(会员卡/预约)含返回条可回到「我的」', html('stu-content').includes('stu-backbar') && html('stu-content').includes("goStu('P-M9')"));

/* ---- 流程 I AI 助手一级 Tab 页(独立完整聊天页,非悬浮窗/弹窗) ---- */
console.log('[I] AI 助手一级 Tab 页');
api.resetData(); api.setView('student'); api.goStu('P-M10');
sc = html('stu-content');
ok('I1 含顶部区域(标题「AI 助手」+ 简洁会话状态)', sc.includes('ai-page') && sc.includes('ai-header') && sc.includes('ai-hname') && sc.includes('AI 助手') && sc.includes('ai-hsub'));
ok('I2 如实标注模拟对话、未接入真实 AI(不伪造已接入)', sc.includes('模拟对话') && sc.includes('未接入真实 AI'));
ok('I3 含独立滚动对话区 + 底部固定输入区(输入框/发送按钮)', sc.includes('class="ai-msgs"') && sc.includes('ai-input-area') && sc.includes('ai-input') && sc.includes('ai-send'));
ok('I4 内容区切换为 ai-mode(内部两段式:对话区滚动+输入区固定)', $('stu-content').classList.contains('ai-mode'));
ok('I5 空状态展示欢迎语 + 4 个常用问题入口卡片', sc.includes('ai-welcome') && sc.includes('ai-wbadge') && (sc.match(/ai-qcard/g) || []).length === 4);
ok('I6 4 个常用问题文案与要求一致', ['如何预约课程？', '我的课卡还剩多少次？', '如何取消或改约课程？', '我最近预约了哪些课程？'].every(q => sc.includes(q)));
tb = html('stu-tabbar');
ok('I7 从首页进入 AI 助手:四 Tab 且「AI 助手」项激活高亮 + 指示条', (tb.match(/tab-text/g) || []).length === 4 && /tab-text active">AI 助手/.test(tb) && tb.includes('tab-indicator'));

/* 点击常用问题 → 真实产生对话(非装饰按钮) */
api.aiAsk('如何预约课程？');
sc = html('stu-content');
ok('I8 常用问题触发用户消息气泡 + 进入加载中(ai-dots)', sc.includes('ai-msg user') && sc.includes('ai-bubble') && api.STATE.aiLoading === true && sc.includes('ai-dots'));
api.aiResolve();
sc = html('stu-content');
ok('I9 模拟回复给出预约步骤(引用真实预约流程)', sc.includes('ai-msg ai') && sc.includes('立即预约') && api.STATE.aiLoading === false);

api.aiAsk('我的课卡还剩多少次？'); api.aiResolve();
sc = html('stu-content');
ok('I10 余额类回复引用原型真实会员卡剩余次数', /次卡剩余 \d+ 次/.test(sc) && sc.includes('ai-msg ai'));

api.aiAsk('如何取消或改约课程？'); api.aiResolve();
sc = html('stu-content');
ok('I11 取消规则回复引用真实不可取消时限 + 回补', sc.includes('不可取消') && sc.includes('回补'));

api.aiAsk('我最近预约了哪些课程？'); api.aiResolve();
sc = html('stu-content');
ok('I12 我的预约回复引用真实预约记录列表', sc.includes('您最近的预约') && sc.includes('1.') && sc.includes('ai-msg ai'));
let msgCnt = (sc.match(/class="ai-msg /g) || []).length;
ok('I13 多轮消息持续累积(对话区容器支持独立滚动)', msgCnt === 8 && sc.includes('class="ai-msgs"'), 'msgCnt=' + msgCnt);

/* 错误态 */
api.aiAsk('错误'); api.aiResolve();
sc = html('stu-content');
ok('I14 输入异常触发错误态气泡(ai-bubble err 纯文本，无 ⚠️ 前缀)', sc.includes('ai-bubble err') && !sc.includes('⚠️') && api.STATE.aiErr === true);

/* 输入框发送 */
api.aiClear();
$('ai-input').value = '测试消息';
api.aiSend();
sc = html('stu-content');
ok('I15 输入文字并发送后用户消息正确显示', sc.includes('测试消息') && sc.includes('ai-msg user'));
api.aiResolve();

/* 清空 → 回到空状态 */
api.aiClear();
sc = html('stu-content');
ok('I16 清空后回到空状态欢迎语(aiMsgs 归零)', sc.includes('ai-welcome') && api.STATE.aiMsgs.length === 0);

/* Tab 切换与返回逻辑 */
api.goStu('P-M8');
ok('I17 从 AI 切回首页:ai-mode 移除 + TabBar 显示 + 首页内容恢复', !$('stu-content').classList.contains('ai-mode') && !$('stu-tabbar').classList.contains('hidden') && html('stu-content').includes('home-navbar'));
api.goStu('P-M3');
tb = html('stu-tabbar');
ok('I18 切到排期:导航高亮转移至「排期」', /tab-text active">排期/.test(tb) && api.STATE.stuPage === 'P-M3');
api.goStu('P-M9');
tb = html('stu-tabbar');
ok('I19 切到我的:导航高亮转移至「我的」', /tab-text active">我的/.test(tb) && api.STATE.stuPage === 'P-M9');
api.goStu('P-M10');
tb = html('stu-tabbar');
ok('I20 从我的切回 AI 助手:导航高亮正确 + 页面恢复', /tab-text active">AI 助手/.test(tb) && html('stu-content').includes('ai-page'));
api.goStu('P-M1');
ok('I21 AI 为一级 Tab 页;会员卡等 pushed 页仍不显示 TabBar(未被破坏)', (api.goStu('P-M10'), !$('stu-tabbar').classList.contains('hidden')) && (api.goStu('P-M1'), $('stu-tabbar').classList.contains('hidden')));

/* ---- 流程 J 决策固化(D1/D3/D4/D5/D9 已确认 2026-10-16) ---- */
console.log('[J] 决策固化(D1/D3/D4/D5/D9 已确认)');
ok('J1 源码移除 conflictSim 模拟开关(改由真实重叠期卡驱动)', !src.includes('conflictSim'));
api.resetData(); api.setView('student'); api.selectSched('S1'); api.goStu('P-M4');
sc = html('stu-content');
ok('J2 P-M4 D9 便签为绿色「已确认」(cnote),不再为黄色「决策占位」且无模拟复选框',
  sc.includes('class="cnote"') && sc.includes('已确认') && !sc.includes('决策占位') && !sc.includes('模拟已有一张生效期卡'));
ok('J3 演示重叠期卡 C8(ACTIVE 期卡)存在且与 C1 同产品(P2)同课程类型',
  api.CARDS.some(c => c.id === 'C8' && c.type === 'period' && c.status === 'ACTIVE' && c.productId === 'P2'));
ok('J4 P-M4 期卡 C1 因预期有效期与 C8 区间重叠被拦截(card-disabled + 有效期重叠)', sc.includes('有效期重叠') && sc.includes('card-disabled'));
ok('J5 addDays 改 UTC 基准(2026-10-10 +30 天 = 2026-11-09,不受本地时区偏移)', api.addDays('2026-10-10', 30) === '2026-11-09', api.addDays('2026-10-10', 30));
api.resetData(); api.setView('dual'); api.goAdmin('P-A2');
let jam = html('admin-main');
ok('J6 P-A2 D3 便签为绿色「已确认」, 无黄色「决策占位」', jam.includes('class="cnote"') && !jam.includes('决策占位'));
api.resetData(); api.setView('student'); api.goStu('P-M3'); api.selectSched('S4'); api.goStu('P-M4');
api.pickBookCard('C2'); api.submitBooking(); api.doBooking();
ok('J7 预约成功后 P-M5 渲染真实结果(doBooking 补 schedId/cardId, 非「无预约结果」)',
  api.STATE.stuPage === 'P-M5' && html('stu-content').includes('预约成功') && html('stu-content').includes('已预扣 1 次') && !html('stu-content').includes('无预约结果'));
api.resetData(); api.setView('dual'); api.goAdmin('P-A1');
ok('J8 未确认决策(D2)仍保留黄色「决策占位」', html('admin-main').includes('决策占位'));

/* ---- 流程 K 管理端对齐(卡产品 P-A1 / 会员卡 P-A2 对齐真实 admin-web) ---- */
console.log('[K] 管理端结构对齐(admin-web views/card-types + views/membership)');
api.resetData(); api.setView('dual'); api.goAdmin('P-A1');
let am = html('admin-main');
ok('K1 P-A1 工具栏含「新增」与「批量删除」(未勾选禁用)', am.includes('>新增<') && am.includes('批量删除') && am.includes('disabled'));
ok('K2 P-A1 表头列对齐真实(序号/产品名称/计费方式/包含次数/有效天数/价格(元)/适用课程类型/状态)', ['序号', '产品名称', '计费方式', '包含次数', '有效天数', '价格(元)', '适用课程类型', '状态'].every(h => am.includes(h)));
ok('K3 P-A1 计费方式 tag 色: 次卡=success / 期卡=warning', am.includes('tag tag-success') && am.includes('tag tag-warning'));
ok('K3b 无限卡计费方式 tag=info 且文案「无限卡」', api.ctTagProduct('unlimited').includes('tag-info') && api.ctTagProduct('unlimited').includes('无限卡'));
ok('K4 P-A1 适用课程类型 tag: 常规=primary/私教=warning/特色=success, 空=不限', am.includes('tag tag-primary') && am.includes('tag tag-warning') && api.courseTypeTag('special').includes('tag-success') && api.courseTypeTag('').includes('不限'));
ok('K6 P-A1 保留 D2 决策占位', am.includes('D2'));
api.PRODUCTS.find(p => p.id === 'P2').status = '下架'; api.renderAdminPage(); am = html('admin-main');
ok('K5 P-A1 行内操作: 编辑/下架·上架/删除(仅下架行有删除)', am.includes('编辑') && am.includes('上架') && am.includes('下架') && am.includes('>删除<'));
api.resetData(); api.goAdmin('P-A1'); am = html('admin-main');
ok('K5b P-A1 上架行不显示删除按钮(仅 status=下架可删)', !am.includes('>删除<'));

api.openProductModal('P1');
let mb = $('modal-box').innerHTML;
ok('K7 P-A1 新建/编辑弹窗字段对齐(产品名称/计费方式/包含次数/有效天数/价格/适用课程类型/描述)', ['产品名称', '计费方式', '包含次数', '有效天数', '价格(元)', '适用课程类型', '描述'].every(f => mb.includes(f)) && mb.includes('textarea'));
ok('K8 P-A1 弹窗计费方式仅次卡·期卡且删除原「每周使用上限」/「状态」字段', mb.includes('>次卡<') && mb.includes('>期卡<') && !mb.includes('无限卡</option>') && !mb.includes('每周使用上限') && !mb.includes('状态'));
api.STATE.selProducts = ['P2']; api.PRODUCTS.find(p => p.id === 'P2').status = '下架'; api.openBatchDeleteProducts();
ok('K9 批量删除弹窗文案对齐(仅已下架的卡类型才能删除)', $('modal-box').innerHTML.includes('只有已下架的卡类型才能删除'));

api.resetData(); api.setView('dual'); api.goAdmin('P-A2'); am = html('admin-main');
ok('K10 P-A2 工具栏含「发放会员卡」与「批量作废」(未勾选禁用)', am.includes('发放会员卡') && am.includes('批量作废') && am.includes('disabled'));
ok('K11 P-A2 筛选行搜索框 placeholder「搜索学员或手机号」', am.includes('搜索学员或手机号'));
ok('K12 P-A2 状态多选含 未激活/正常/已过期/已冻结/已作废', ['未激活', '正常', '已过期', '已冻结', '已作废'].every(s => am.includes(s)));
ok('K13 P-A2 表头列对齐真实(序号/会员卡号/产品名称/计费方式/学员/手机号/总次数/已用/剩余/状态/有效期/冻结信息/操作)', ['序号', '会员卡号', '产品名称', '计费方式', '学员', '手机号', '总次数', '已用', '剩余', '状态', '有效期', '冻结信息', '操作'].every(h => am.includes(h)));
ok('K14 P-A2 管理端状态徽标「正常」(区别于学员端「使用中」)', am.includes('正常') && am.includes('badge st-green'));
ok('K15 P-A2 冻结信息列「剩余 X 天解冻」+ 冻结到期-课程冲突标记', /剩余 \d+ 天解冻/.test(am) && am.includes('冻结到期-课程冲突'));
ok('K16 P-A2 计费方式 tag 色: 次卡=primary / 期卡=success', am.includes('tag tag-primary') && am.includes('tag tag-success'));
ok('K16b 无限卡(会员卡页)计费方式 tag=warning', api.ctTagCard('unlimited').includes('tag-warning'));
ok('K17 P-A2 行内含 激活/冻结/强制解冻 操作', am.includes('激活') && am.includes('冻结') && am.includes('强制解冻'));

api.openFreezeModal('C2'); mb = $('modal-box').innerHTML;
ok('K18 冻结弹窗: 冻结天数(1-365天) + 冻结原因(请输入冻结原因)', mb.includes('冻结天数') && mb.includes('1-365天') && mb.includes('请输入冻结原因') && mb.includes('textarea'));

api.openCardDetail('C2'); mb = $('modal-box').innerHTML;
ok('K19 详情弹窗为 el-descriptions 两列 border 网格(desc-grid)且字段完整', mb.includes('desc-grid') && ['会员卡号', '产品名称', '计费方式', '学员', '手机号', '总次数', '已用次数', '剩余次数', '状态', '有效期', '创建时间', '更新时间'].every(f => mb.includes(f)));
ok('K20 详情弹窗含流水原型扩展标注(真实详情弹窗不含流水)', mb.includes('原型扩展') && mb.includes('getTransactions'));
api.openCardDetail('C5'); mb = $('modal-box').innerHTML;
ok('K21 冻结卡详情含 冻结时间/冻结到期/剩余冻结天数/冻结原因', ['冻结时间', '冻结到期', '剩余冻结天数', '冻结原因'].every(f => mb.includes(f)) && mb.includes('span2'));

api.resetData(); api.goAdmin('P-A2'); api.adminCancel('C2'); mb = $('modal-box').innerHTML;
ok('K22 作废弹窗: 作废原因 + placeholder「请输入作废原因」', mb.includes('作废原因') && mb.includes('请输入作废原因') && mb.includes('textarea'));

api.STATE.selCards = ['C2', 'C5']; api.openBatchCancelCards(); mb = $('modal-box').innerHTML;
ok('K23 批量作废弹窗: 已选择 N 张 + 学员/手机号/状态 + 「请输入批量作废原因」', mb.includes('张会员卡进行批量作废') && mb.includes('138****8888') && mb.includes('请输入批量作废原因'));

api.resetData(); api.goAdmin('P-A2'); api.openIssueModal(); mb = $('modal-box').innerHTML;
ok('K24 发放弹窗: 学员/产品/生效时间/备注; 无「允许同产品重复发卡」复选框', ['学员', '产品', '生效时间', '备注', '请输入备注'].every(f => mb.includes(f)) && !mb.includes('允许同产品重复发卡') && !mb.includes('if-dup'));
ok('K25 发放弹窗(次卡)总次数/有效天数只读 disabled + 次数由产品决定', (d => d.includes('次数由产品决定，不可修改') && d.includes('天数由产品决定，不可修改') && d.includes('disabled'))($('if-dynamic').innerHTML));
ok('K26 发放弹窗保留 (P-A3) 标签与 D9 已确认说明', mb.includes('(P-A3)') && mb.includes('D9') && mb.includes('已确认'));
api.issueDo(); mb = $('modal-box').innerHTML;
ok('K27 续卡提示弹窗: 同课程类型有效卡数量 + 续卡规则 + 最早生效日期', mb.includes('同课程类型有效卡') && mb.includes('续卡规则') && mb.includes('最早生效日期') && mb.includes('新卡生效时间必须晚于旧卡到期时间的次日'));

api.resetData(); api.goAdmin('P-A2'); api.adminUnfreeze('C5');
ok('K28 冻结卡解冻: 存在同课程类型冲突时走「冻结到期-课程冲突」弹窗', $('modal-box').innerHTML.includes('冻结到期-课程冲突'));
mb = $('modal-box').innerHTML;
ok('K29 冲突弹窗: 卡信息 + 冲突卡列表 + 两种处理方式 + 操作备注', mb.includes('解冻并作废冲突卡') && mb.includes('解冻并冻结冲突卡') && mb.includes('请输入操作备注'));

/* ---- 流程 L 跨排期时间段重叠冲突(D9 之外的独立校验,2026-10-19 补) ---- */
console.log('[L] 跨排期时间段重叠冲突');
/* 命中冲突:目标排期 S6(今日 19:30-20:30) 与学员进行中预约 B1 所在排期 S1(今日 19:00-20:30)时间重叠 */
api.resetData(); api.setView('student'); api.goStu('P-M3'); api.selectSched('S6'); api.goStu('P-M4');
$('modal-box').innerHTML = ''; api.closeModal();
api.pickBookCard('C2'); api.submitBooking();
ok('L1 冲突排期在确认阶段被拦截(不弹二次确认)', !$('mask').classList.contains('show') && !$('modal-box').innerHTML.includes('确认预约'));
ok('L2 拦截文案含「冲突」+ 冲突课程名《拉丁舞基础》+ 两个时间段',
  text('toast').includes('冲突') && text('toast').includes('拉丁舞基础') &&
  text('toast').includes('19:30-20:30') && text('toast').includes('19:00-20:30'), text('toast'));
ok('L3 未生成新预约/未扣次/既有预约状态不变',
  api.BOOKINGS.length === 5 && api.cardById('C2').remaining === 7 &&
  api.bookingById('B1').status === 'BOOKED' && api.bookingById('B5').status === 'BOOKED',
  'len=' + api.BOOKINGS.length + ' remain=' + api.cardById('C2').remaining);

/* 非冲突排期仍可正常预约 */
api.resetData(); api.setView('student'); api.goStu('P-M3'); api.selectSched('S4'); api.goStu('P-M4'); api.pickBookCard('C2'); api.submitBooking();
ok('L4 非冲突排期仍进入写操作二次确认', $('mask').classList.contains('show') && $('modal-box').innerHTML.includes('确认预约'));
api.doBooking();
ok('L5 非冲突排期可正常预约成功(BOOKINGS 5->6)', api.BOOKINGS.length === 6 && api.STATE.stuPage === 'P-M5', 'len=' + api.BOOKINGS.length);

/* 既有「卡有效期重叠」拦截未被破坏(与时间段冲突解耦) */
api.resetData(); api.setView('student'); api.selectSched('S1'); api.goStu('P-M4');
api.STATE.bookCardId = 'C1'; api.submitBooking();
ok('L6 卡有效期重叠拦截独立存在(C1 于 S1 仍被拦,且非被时间段冲突误拦)', text('toast').includes('预期有效期与已有卡重叠'), text('toast'));
ok('L7 时间段冲突拦截未与卡冲突混淆(S6 目标排期不含期卡冲突提示)', (api.resetData(), api.setView('student'), api.goStu('P-M3'), api.selectSched('S6'), api.goStu('P-M4'), api.pickBookCard('C2'), api.submitBooking(), text('toast').includes('与您已约课程') && !text('toast').includes('预期有效期')), text('toast'));

console.log('\n==== 结果: PASS ' + pass + ' / FAIL ' + fail + ' ====');
process.exit(fail ? 1 : 0);
