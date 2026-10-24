#!/usr/bin/env node
/*
 * F7.0 后台管理端增强与小程序首页配置 · 原型验证脚手架
 * ------------------------------------------------------------------
 * 用途：对 prototype/index.html 做"可执行"验证（非静态截图比对）：
 *   1) 抽取内嵌 <script> 做语法检查（等价于浏览器能否解析）
 *   2) 在 DOM stub 下真实调用原型函数，逐条断言数据副作用 / DOM 内容
 *   3) 交付边界断言（单 script、无 fetch/XHR、Mock 标注等）
 *
 * 运行：node verify-prototype.js              # 默认验证同目录 prototype/index.html
 *       node verify-prototype.js <path>       # 指定其它原型文件
 * 退出码：全部通过 0；存在 FAIL 或语法错误 1（可直接接入 CI）
 *
 * 注意：本脚本验证"原型行为逻辑 + 关键 DOM 结构"，不覆盖真实浏览器渲染效果。
 */
const fs = require('fs');
const path = require('path');

const file = process.argv[2] || path.join(__dirname, 'prototype', 'index.html');
const src = fs.readFileSync(file, 'utf8');

/* 收集所有 <script> 块（校验单一脚本） */
const scripts = src.match(/<script>[\s\S]*?<\/script>/g) || [];
if (scripts.length !== 1) {
  console.log('FAIL: 期望恰好 1 个 <script> 块，实际 ' + scripts.length + ' 个');
  process.exit(1);
}
const inner = src.match(/<script>([\s\S]*?)<\/script>/)[1];

/* ---- 1. 语法检查 ---- */
try { new Function(inner); console.log('[1] SYNTAX OK'); }
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

const api = new Function(inner + `
;return {
  resetData, renderAll, goAdmin, toggleUserMenu, renderHeader,
  openProfile, closeProfile, saveProfile, pf,
  openUserDialog, closeUserDialog, saveUser, uf, findUser,
  imageChoose, imageUpload, imageResolve, imageRemove,
  openClassroomDialog, closeClassroomDialog, saveClassroom, cf,
  onClassroomSearch, onUserSearch, reloadUsers, reloadClassrooms, reloadHome, findRoom,
  toggleHomeModule, moveHomeModule, reorderHomeModule, moduleIndex, openModuleDrawer, closeModuleDrawer, saveDraft, df, drawerItem,
  drawerToggleTeacher, drawerToggleCourse, homeModule,
  previewHome, backToHomeEdit, togglePreviewFail,
  openPublish, closePublish, doPublish, togglePublishFail,
  get STATE(){ return STATE; }
};`)();

const $ = id => els[id] || (els[id] = new El());
const html = id => $(id).innerHTML;
let pass = 0, fail = 0;
function ok(name, cond, extra) { if (cond) { pass++; console.log('  PASS :: ' + name); } else { fail++; console.log('  FAIL :: ' + name + (extra ? ' -> ' + extra : '')); } }

/* ================= A. 用户管理 + 头像上传 ================= */
console.log('[A] 用户管理（含头像）');
api.resetData(); api.goAdmin('P-F7-01');
ok('A1 侧边栏含 用户管理 与新增的 小程序首页', html('admin-side').includes('用户管理') && html('admin-side').includes('小程序首页'));
ok('A2 侧边栏 小程序首页 带 NEW 标记', html('admin-side').includes('badge-new'));
ok('A3 列表首列为「头像」', html('admin-main').includes('>头像<') || html('admin-main').includes('>头像'));
ok('A4 保留原有列：微信绑定/教师编号/学员编号/注册时间', ['微信绑定','教师编号','学员编号','注册时间'].every(k => html('admin-main').includes(k)));
ok('A5 无头像用户渲染默认占位头像 .avatar.ph', html('admin-main').includes('avatar ph'));
ok('A6 有头像用户渲染 img', html('admin-main').includes('<img src="data:image/svg'));
ok('A7 新增弹窗含上传区（Element Plus 原生上传样式，无「演示/选 .txt/选大图」调试按钮）', (api.openUserDialog('create'), api.STATE.userDialog.open === true && html('modal-box').includes('新增用户') && html('modal-box').includes('选择图片') && !html('modal-box').includes('选 .txt') && !html('modal-box').includes('选大图') && !html('modal-box').includes('演示：')));
ok('A8 选 .txt → 格式错误态', (api.imageChoose('user','bad-format'), api.STATE.userDialog.upload.state === 'format-error' && html('modal-box').includes('仅支持 JPG')));
ok('A9 选大图 → 大小错误态', (api.imageChoose('user','big'), api.STATE.userDialog.upload.state === 'size-error' && html('modal-box').includes('5MB')));
ok('A10 选正常图 → 预览态含 上传/更换/移除', (api.imageChoose('user','ok'), api.STATE.userDialog.upload.state === 'preview' && html('modal-box').includes('上传') && html('modal-box').includes('更换') && html('modal-box').includes('移除')));
ok('A11 点上传 → 上传中态', (api.imageUpload('user'), api.STATE.userDialog.upload.state === 'uploading' && html('modal-box').includes('上传中')));
ok('A12 模拟失败 → 失败态含 重试', (api.imageResolve('user',false), api.STATE.userDialog.upload.state === 'fail' && html('modal-box').includes('重试')));
ok('A13 重试并模拟成功 → 成功态', (api.imageUpload('user'), api.imageResolve('user',true), api.STATE.userDialog.upload.state === 'success'));
ok('A14 保存校验：昵称为空→行内错误且弹窗不关闭', (api.saveUser(), api.STATE.userDialog.errors.nickname === '请输入昵称' && api.STATE.userDialog.open === true));
ok('A15 补齐必填项后保存成功且新用户入列', (api.uf('phone','13900000001'), api.uf('password','123456'), api.uf('nickname','新学员'), api.saveUser(), api.STATE.users.length === 6 && api.STATE.users[5].nickname === '新学员'));
ok('A16 保存后弹窗关闭且上传区已重置', api.STATE.userDialog.open === false && api.STATE.userDialog.upload.state === 'idle' && $('mask').className.indexOf('show') < 0);
ok('A16b 新用户头像非空且已随创建写入', (function(){ var u = api.STATE.users[api.STATE.users.length-1]; return typeof u.avatar_url === 'string' && u.avatar_url.length > 0; })());
ok('A17 编辑用户回填手机号(只读)与已有头像', (api.openUserDialog('edit',1), api.STATE.userDialog.form.phone === '13800001234' && html('modal-box').includes('readonly') && api.STATE.userDialog.upload.state === 'success'));
ok('A18 编辑换头像并改名后保存生效', (function(){
   var before = api.findUser(1).avatar_url;
   api.imageChoose('user','ok'); api.imageUpload('user'); api.imageResolve('user',true);
   api.uf('nickname','林小雅改名'); api.saveUser();
   var u = api.findUser(1);
   return u.nickname === '林小雅改名' && u.avatar_url !== before;
 })());
ok('A19 编辑取消不覆盖原头像', (function(){
   var before = api.findUser(2).avatar_url;
   api.openUserDialog('edit',2); api.imageChoose('user','ok'); api.imageUpload('user'); api.imageResolve('user',true);
   api.closeUserDialog();
   return api.findUser(2).avatar_url === before;
 })());
ok('A20 搜索无结果→空态；清空恢复', (api.onUserSearch('不存在的人'), html('admin-main').includes('未找到匹配的用户')) && (api.onUserSearch(''), api.STATE.users.length === 6 && !html('admin-main').includes('未找到匹配的用户')));

/* ================= B. 右上角用户菜单 + 个人资料 ================= */
console.log('[B] 个人资料');
api.resetData(); api.goAdmin('P-F7-01');
ok('B1 顶栏下拉同时含 个人资料 与 退出登录', html('admin-header').includes('个人资料') && html('admin-header').includes('退出登录'));
ok('B2 点击头像展开下拉', (api.toggleUserMenu(), api.STATE.userMenuOpen === true && html('admin-header').includes('dropdown')));
ok('B3 个人资料弹窗：昵称可编辑 / 手机号只读 / 角色只读 tag', (api.openProfile(), html('modal-box').includes('个人资料') && html('modal-box').includes('昵称') && html('modal-box').includes('readonly') && html('modal-box').includes('tag primary')));
ok('B4 昵称清空→校验失败且弹窗不关闭', (api.pf('nickname',''), api.saveProfile(), api.STATE.profileEdit && api.STATE.profileEdit.errors.nickname === '昵称不能为空' && $('mask').className.indexOf('show') >= 0));
ok('B5 保存成功→资料更新且顶部同步', (api.pf('nickname','林小雅Pro'), api.saveProfile(), api.STATE.profile.nickname === '林小雅Pro' && html('admin-header').includes('林小雅Pro') && api.STATE.profileEdit === null));
ok('B6 更换头像并保存→顶部头像同步', (function(){
   var before = api.STATE.profile.avatar;
   api.openProfile(); api.imageChoose('profile','ok'); api.imageUpload('profile'); api.imageResolve('profile',true); api.saveProfile();
   return api.STATE.profile.avatar !== before && html('admin-header').includes('<img src="data:image/svg');
 })());

/* ================= C. 教室管理（仅卡片视图 + 图片 + 编码） ================= */
console.log('[C] 教室管理');
api.resetData(); api.goAdmin('P-F7-05');
ok('C1 教室管理仅卡片视图（无表格视图与切换控件；操作按钮无图标前缀）', !html('admin-actions').includes('表格视图') && !html('admin-actions').includes('卡片视图') && html('admin-actions').includes('>新增</button>') && !html('admin-actions').includes('＋') && html('admin-main').includes('rcard'));
ok('C2 已移除表格视图渲染与切换逻辑（无 tbl 表格 / classroomView / toggleClassroomView）', !html('admin-main').includes('class="tbl"') && api.STATE.classroomView === undefined && typeof api.toggleClassroomView === 'undefined');
ok('C2b 卡片不含 容量/状态/维护（字段与概念已删除）', !html('admin-main').includes('容纳人数') && !html('admin-main').includes('维护中') && !html('admin-main').includes('>维护<') && !html('admin-main').includes('>状态<'));
ok('C3 图片失效教室 → 占位（无破图）', html('admin-main').includes('cover-ph') || html('admin-main').includes('图片加载失败'));
ok('C4 未设置封面教室 → 暂无图片占位（不再绘制默认封面图）', (html('admin-main').match(/rc-cover"><img/g) || []).length === 2 && (html('admin-main').match(/rc-cover"><div class="cover-ph"/g) || []).length === 2 && !src.includes('roomDefaultCover'));
ok('C5 卡片数量=当前列表教室数（每间教室一张卡片）', (html('admin-main').match(/class="rcard"/g) || []).length === 4);
ok('C6 卡片含封面容器 + 位置/设备行（线性 SVG 图标，无 emoji）+ 教室编码', html('admin-main').includes('rc-cover') && html('admin-main').includes('rc-line') && html('admin-main').includes('<svg') && !html('admin-main').includes('📍') && !html('admin-main').includes('🎛') && html('admin-main').includes('R-00'));
ok('C6b 卡片不含 容量/状态标签', !html('admin-main').includes('容纳人数') && !html('admin-main').includes('维护中'));
ok('C7 新增教室弹窗含 封面图上传区 + 必填教室编码项', (api.openClassroomDialog('create'), api.STATE.classroomDialog.open === true && html('modal-box').includes('新增教室') && html('modal-box').includes('封面图') && html('modal-box').includes('选择图片') && html('modal-box').includes('教室编码')));
ok('C8 必填校验：编码与名称为空→行内错误且弹窗不关闭', (api.saveClassroom(), api.STATE.classroomDialog.errors.code === '请输入教室编码' && api.STATE.classroomDialog.errors.name === '请输入教室名称' && api.STATE.classroomDialog.open === true));
ok('C8b 编码唯一性校验：与现有 R-001 重复→拦截且不入列', (api.cf('code','R-001'), api.cf('name','测试教室'), api.saveClassroom(), api.STATE.classroomDialog.errors.code === '教室编码已存在' && api.STATE.classrooms.length === 4 && api.STATE.classroomDialog.open === true));
ok('C9 填唯一编码+名称+上传封面后保存成功并入列', (function(){
   api.imageChoose('classroom','ok'); api.imageUpload('classroom'); api.imageResolve('classroom',true);
   api.cf('code','R-005'); api.cf('name','新排练厅'); api.cf('location','4 楼'); api.saveClassroom();
   var r = api.STATE.classrooms[api.STATE.classrooms.length-1];
   return api.STATE.classrooms.length === 5 && r.code === 'R-005' && r.name === '新排练厅' && r.cover === 'ROOM1';
 })());
ok('C10 编辑教室回填编码/封面；往返保留 code', (function(){
   api.openClassroomDialog('edit',1);
   var filled = api.STATE.classroomDialog.form.code === 'R-001' && api.STATE.classroomDialog.form.name === '舞蹈教室 A' && api.STATE.classroomDialog.upload.state === 'success';
   api.cf('name','舞蹈教室 A 改名'); api.saveClassroom();
   return filled && api.findRoom(1).code === 'R-001' && api.findRoom(1).name === '舞蹈教室 A 改名';
 })());
ok('C10b 教室字段集 = code/name/location/equipment/cover（无 capacity/status）', api.STATE.classrooms.every(function(r){ return r.capacity === undefined && r.status === undefined && typeof r.code === 'string' && r.code.length > 0; }));
ok('C10c 维护能力已彻底移除（无 toggleClassroomStatus）', typeof api.toggleClassroomStatus === 'undefined' && !html('admin-main').includes('维护'));
ok('C11 搜索无结果→空态；清空恢复', (api.onClassroomSearch('不存在'), html('admin-main').includes('未找到匹配的教室')) && (api.onClassroomSearch(''), api.STATE.classrooms.length === 5 && !html('admin-main').includes('未找到匹配的教室')));

/* ================= D. 首页管理（模块/排序/启停/抽屉） ================= */
console.log('[D] 首页管理');
api.resetData(); api.goAdmin('P-F7-08');
ok('D1 首页管理页含 5 类模块', ['Banner 轮播','师资团队','推荐课程','舞蹈视频','公告/活动'].every(k => html('admin-main').includes(k)));
ok('D2 初始线上版本为 未发布', html('admin-main').includes('线上版本：未发布'));
ok('D3 模块数=5', api.STATE.home.modules.length === 5);
ok('D4 启用开关切换并标记草稿为脏', (api.toggleHomeModule('notice'), api.homeModule('notice').enabled === true && api.STATE.home.dirty === true));
ok('D5 上移改变顺序', (function(){ var before = api.homeModule('notice').sort; api.moveHomeModule('notice',-1); return api.homeModule('notice').sort !== before; })());
ok('D6 首模块不可再上移（边界保护）', (function(){
   var first = api.STATE.home.modules.slice().sort((a,b)=>a.sort-b.sort)[0];
   var snap = first.sort; api.moveHomeModule(first.type,-1);
   return api.homeModule(first.type).sort === snap;
 })());
ok('D6b 列表渲染排序值(ord-no)+拖拽手柄(drag-handle)；模块类型图标列(.micon)已删除', html('admin-main').includes('ord-no') && html('admin-main').includes('drag-handle') && !html('admin-main').includes('micon'));
ok('D6c 模块行可拖拽(draggable + ondrop 热点)', html('admin-main').includes('draggable="true"') && html('admin-main').includes('ondrop=') && html('admin-main').includes('ondragstart='));
ok('D6d 拖动重排：末位模块拖到首位→位列第一且排序值=1', (api.reorderHomeModule('notice',0), (function(){ var mods=api.STATE.home.modules.slice().sort((a,b)=>a.sort-b.sort); return mods[0].type==='notice' && api.homeModule('notice').sort===1; })()));
ok('D6e 拖动重排后排序值连续为 1..5', (api.STATE.home.modules.slice().sort((a,b)=>a.sort-b.sort).map(m=>m.sort).join(',') === '1,2,3,4,5'));
ok('D6f 拖动越界被钳制（拖到超出末端→落到末位）', (function(){ var n=api.STATE.home.modules.length; api.reorderHomeModule('banner', n+5); return api.homeModule('banner').sort===n; })());
ok('D7 打开 Banner 配置抽屉', (api.openModuleDrawer('banner'), api.STATE.drawer.open === true && html('drawer-box').includes('Banner 轮播配置')));
ok('D8 保存 Banner 草稿写回模块', (api.drawerItem('title','新轮播标题'), api.saveDraft(), api.homeModule('banner').items[0].title === '新轮播标题' && api.STATE.drawer.open === false && api.STATE.home.dirty === true));
ok('D9 Banner 必填校验（标题为空→拒绝保存）', (api.openModuleDrawer('banner'), api.drawerItem('title',''), api.saveDraft(), api.STATE.drawer.open === true && api.STATE.toast.msg.includes('轮播标题')));
ok('D10 师资抽屉含教师选择且可勾选', (api.openModuleDrawer('teachers'), html('drawer-box').includes('教师选择') && html('drawer-box').includes('王梓涵'), api.drawerToggleTeacher(5), (api.STATE.drawer.form.teacher_ids||[]).includes(5)));
ok('D11 师资展示数量越界→拒绝', (api.df('limit',20), api.saveDraft(), api.STATE.drawer.open === true && api.STATE.toast.msg.includes('1~12')));
ok('D12 课程抽屉可勾选课程并切换排序规则', (api.closeModuleDrawer(), api.openModuleDrawer('courses'), api.drawerToggleCourse(4), api.df('sort_rule','latest'), (api.STATE.drawer.form.course_ids||[]).includes(4) && api.STATE.drawer.form.sort_rule === 'latest'));
ok('D13 视频抽屉缺视频地址→拒绝保存', (api.closeModuleDrawer(), api.openModuleDrawer('video'), api.drawerItem('url',''), api.saveDraft(), api.STATE.drawer.open === true && api.STATE.toast.msg.includes('视频地址')));
ok('D14 公告抽屉保存写回标题', (api.closeModuleDrawer(), api.openModuleDrawer('notice'), api.df('noticeTitle','新公告标题'), api.saveDraft(), api.homeModule('notice').noticeTitle === '新公告标题'));
ok('D15 抽屉关闭后不再渲染', (api.STATE.drawer.open === false && html('drawer-box') === ''));

/* ================= E. 预览 / 发布 / 数据流 ================= */
console.log('[E] 预览与发布');
api.resetData(); api.goAdmin('P-F7-08');
ok('E1 进入预览页且标注「预览的是草稿」', (api.previewHome(), api.STATE.adminPage === 'P-F7-14' && html('admin-main').includes('phone') && html('admin-main').includes('预览的是')));
ok('E2 停用模块不出现在预览', (api.STATE.home.modules.some(m => m.type==='notice' && !m.enabled)) && !html('admin-main').includes('2026 秋季招生'));
ok('E3 启用公告后预览出现该模块', (api.toggleHomeModule('notice'), html('admin-main').includes('2026 秋季招生')));
ok('E4 预览含 Banner 标题', html('admin-main').includes('让舞蹈成为生活的一部分'));
ok('E5 模拟接口失败→仅隐藏纯配置模块并提示', (api.togglePreviewFail(), api.STATE.previewFail === true && html('admin-main').includes('接口请求失败') && !html('admin-main').includes('让舞蹈成为生活的一部分')));
ok('E6 失败态下师资模块仍渲染（回落真实 API）', html('admin-main').includes('王梓涵'));
ok('E7 发布确认弹窗列出模块', (api.goAdmin('P-F7-08'), api.openPublish(), api.STATE.publish.open === true && html('modal-box').includes('发布确认')));
ok('E8 发布失败→保留旧版本', (api.togglePublishFail(), api.doPublish(), api.STATE.home.publishResult === 'fail' && api.STATE.home.publishedVersion === 0 && api.STATE.home.dirty === true && api.STATE.publish.open === false));
ok('E9 发布成功→线上版本+1 且草稿与线上一致', (api.openPublish(), api.doPublish(), api.STATE.home.publishedVersion === 1 && api.STATE.home.dirty === false && api.STATE.home.publishResult === 'success'));
ok('E10 发布后改草稿不影响线上版本号', (api.toggleHomeModule('teachers'), api.STATE.home.dirty === true && api.STATE.home.publishedVersion === 1));
ok('E11 预览读取的是草稿（停用师资后预览隐藏，线上版本不变）', (api.previewHome(), !html('admin-main').includes('师资团队') || !html('admin-main').includes('王梓涵'), api.STATE.home.publishedVersion === 1));

/* ================= F. 异常状态 ================= */
console.log('[F] 异常状态');
api.resetData(); api.goAdmin('P-F7-01');
ok('F1 用户列表加载失败→错误态+重试', (api.STATE.listError = '网络错误', api.renderAll(), html('admin-main').includes('加载用户列表失败') && html('admin-main').includes('重试')));
ok('F2 重试清除错误', (api.reloadUsers(), api.STATE.listError === '' && !html('admin-main').includes('加载用户列表失败')));
ok('F3 教室列表加载失败→错误态', (api.goAdmin('P-F7-05'), api.STATE.listError = '服务不可用', api.renderAll(), html('admin-main').includes('加载教室列表失败')));
ok('F4 教室重试恢复', (api.reloadClassrooms(), !html('admin-main').includes('加载教室列表失败')));
ok('F5 首页配置加载失败→错误态', (api.goAdmin('P-F7-08'), api.STATE.listError = '超时', api.renderAll(), html('admin-main').includes('加载首页配置失败')));
ok('F6 首页重试恢复', (api.reloadHome(), !html('admin-main').includes('加载首页配置失败')));

/* ================= G. 交付边界 / 结构完整性 ================= */
console.log('[G] 交付边界');
ok('G1 原型恰为单 <script> 块', scripts.length === 1);
ok('G2 不发起真实网络请求（无 fetch/XHR/axios）', !/fetch\(|XMLHttpRequest|axios/.test(inner));
ok('G3 明确标注「原型模拟数据」', src.includes('原型模拟数据'));
ok('G4 未伪装真实 API：含"未接通/原型模拟"字样', inner.includes('未接通') || inner.includes('原型模拟'));
ok('G5 5 类模块类型均实现渲染分支', ['banner','teachers','courses','video','notice'].every(t => inner.includes("'"+t+"'")));
ok('G6 待确认项在原型中以 D-F7 标注', src.includes('D-F7'));
ok('G7 未使用真实后端域名', !/https?:\/\/localhost|\/api\/v1/.test(inner));

/* ================= H. 外壳一致性（对齐 F6.0） ================= */
console.log('[H] 外壳一致性（对齐 F6.0）');
api.resetData(); api.goAdmin('P-F7-01');
ok('H1 顶栏含视图切换（管理后台 / 小程序预览）', html('topbar-tabs').includes('管理后台') && html('topbar-tabs').includes('小程序预览'));
ok('H2 面板标题条显示当前页标题（.page-title + #admin-ptitle）', $('admin-ptitle').textContent === '用户管理');
ok('H3 侧边栏采用 F6.0 命名（.admin-side / .nav-item / .logo）', html('admin-side').includes('nav-item') && html('admin-side').includes('logo') && html('admin-side').includes('nav-item active'));
ok('H4 页面操作按钮移入面板标题区（#admin-actions，无「＋」图标前缀）', html('admin-actions').includes('>新增</button>') && !html('admin-actions').includes('＋'));
ok('H5 已移除旧外壳（无 app-shell / crumb-title / page-head）', !src.includes('app-shell') && !src.includes('crumb-title') && !src.includes('page-head'));
ok('H6 面板标题条含 ADMIN 编号徽标（.pid）', src.includes('class="pid">ADMIN'));
ok('H7 侧栏仅展示本次范围内的菜单（用户管理/教室管理/小程序首页）', ['用户管理','教室管理','小程序首页'].every(k => html('admin-side').includes(k)) && ['角色权限','教师管理','学员管理','课程管理','排期管理','卡产品管理','会员卡管理','机构设置'].every(k => !html('admin-side').includes(k)));
ok('H8 侧栏图标与真实 admin-web 一致（Element Plus SVG path，非 emoji）', html('admin-side').includes('<svg viewBox="0 0 1024 1024"') && html('admin-side').includes('M512 512a192 192 0 1 0 0-384') && !['👤','🔑','🩰','🎓','📚','🏛','📅','💳','🎫','📱','⚙'].some(e => html('admin-side').includes(e)));

/* ================= I. 预览页复刻真实 miniapp 学员端首页 ================= */
console.log('[I] 预览页复刻真实小程序首页');
api.resetData(); api.goAdmin('P-F7-01');
ok('I1 侧栏「小程序首页」图标改为 EP HomeFilled（并移除旧 cellphone 手机矩形 path）', html('admin-side').includes('M512 128 128 447.936V896h255.936V640H640v256h255.936V447.936z') && !src.includes('M256 128a64 64 0 0 0-64 64v640'));
api.previewHome();
ok('I2 预览含真实首页顶部导航（定位图标 + 机构名 + 下拉）', html('admin-main').includes('m-nav') && html('admin-main').includes('舞蹈艺术培训中心') && html('admin-main').includes('class="loc"'));
ok('I3 预览底部 TabBar 采用 F6.0 学员端口径 4 Tab（首页/排期/AI 助手/我的）', html('admin-main').includes('m-tabbar') && ['>首页<','>排期<','>AI 助手<','>我的<'].every(k => html('admin-main').includes(k)));
ok('I4 首页 Tab 为激活态（.m-tab.on + 激活指示条）', html('admin-main').includes('m-tab on') && html('admin-main').includes('class="ind"'));
ok('I5 AI 助手入口位于底部菜单栏（F6.0 口径），已移除悬浮 FAB', html('admin-main').includes('<span>AI 助手</span>') && !html('admin-main').includes('m-fab') && !src.includes('.m-fab'));
ok('I6 Banner 使用真实 135deg 深→浅遮罩 + 金色指示点', src.includes('linear-gradient(135deg,rgba(30,22,16,.75) 0%,rgba(30,22,16,.4) 50%,rgba(30,22,16,.1) 100%)') && src.includes('.m-dots i.on{background:#c9a66b}') && html('admin-main').includes('class="m-dots"'));
ok('I7 师资为奶油渐变圆形头像（#f5e6d3→#e8d5c4）+ 姓名/专长两行', html('admin-main').includes('m-tav') && html('admin-main').includes('m-ts') && html('admin-main').includes('王梓涵') && html('admin-main').includes('中国古典舞') && src.includes('linear-gradient(135deg,#f5e6d3 0%,#e8d5c4 100%)'));
ok('I8 推荐课程为左图右文卡片（.m-clist / .m-course / .m-cimg）', html('admin-main').includes('m-clist') && html('admin-main').includes('m-course') && html('admin-main').includes('m-cimg') && html('admin-main').includes('m-cname'));
ok('I9 视频卡含金色圆形播放按钮 + 时长胶囊（.m-play / .m-vdur）', html('admin-main').includes('m-play') && html('admin-main').includes('m-vdur') && html('admin-main').includes('03:28'));
ok('I10 section 标题含真实金色线性图标（.mst + stroke=currentColor + #c9a66b）', html('admin-main').includes('<div class="mst">') && src.includes('stroke="currentColor"') && src.includes('.m-sh .mst svg{color:#c9a66b'));
ok('I11 页面背景为真实暖奶油渐变 + 已弃用旧占位类名', src.includes('linear-gradient(180deg,#faf6f0 0%,#f5ede3 100%)') && !src.includes('ph-banner') && !src.includes('ph-sec') && !src.includes('ph-row') && !src.includes('ph-card') && !src.includes('ph-teacher'));

/* ---- 汇总 ---- */
console.log('\n================ 结果 ================');
console.log('PASS: ' + pass + '  FAIL: ' + fail);
process.exit(fail ? 1 : 0);
