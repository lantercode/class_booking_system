/* F6.0 会员卡原型生成器 — 插件自检器（CommonJS + vm 桩，零外部依赖）
 * ---------------------------------------------------------------------------
 * 用途：在无 Figma 的环境下，用桩对象模拟 Figma Plugin API，加载并真实运行
 *      `figma-plugin/code.js`，断言「紧凑模式」（Starter 免费计划 Page 上限 = 3）
 *      下的产出计数与"不越界建页"，使生成逻辑可在 CI / 本地被客观验证。
 * 运行：node verify-plugin.js     退出码 0 = 全通过；1 = 存在 FAIL 或异常。
 * 约束：不联网；不改业务代码；只读取本目录 code.js / manifest.json。
 * ---------------------------------------------------------------------------
 */
'use strict';

var fs = require('fs');
var path = require('path');
var vm = require('vm');

var DIR = __dirname;
var code = fs.readFileSync(path.join(DIR, 'code.js'), 'utf8');
var manifest = JSON.parse(fs.readFileSync(path.join(DIR, 'manifest.json'), 'utf8'));

// ---------------------------------------------------------------------------
// 模拟 Figma 对 paint 的校验：颜色通道必须为有限数值（NaN 会被 Figma 拒绝并抛错）。
// 若桩不校验，含 NaN 的颜色会被静默接受 → 「计数全过、真机却绘制中途中断」的假通过。
// 2026-10-18：正是 rgba()/transparent 被解析成 NaN，导致整屏只剩标题、大片空白。
// ---------------------------------------------------------------------------
function checkColorChannel(c) {
  if (!c) return;
  if (!isFinite(c.r) || !isFinite(c.g) || !isFinite(c.b) || (c.a !== undefined && !isFinite(c.a))) {
    throw new Error('Invalid paint color channel (NaN)');
  }
}
function validatePaints(v) {
  if (!Array.isArray(v)) return;
  for (var i = 0; i < v.length; i++) {
    var p = v[i];
    if (!p || typeof p !== 'object') continue;
    checkColorChannel(p.color);
    if (p.gradientStops) {
      for (var k = 0; k < p.gradientStops.length; k++) checkColorChannel(p.gradientStops[k].color);
    }
  }
}

// ---------------------------------------------------------------------------
// 桩：在给定「既有 Page 数」下运行 code.js，返回真实产出计数
// ---------------------------------------------------------------------------
function runScenario(initialPageCount, opts) {
  return new Promise(function (resolve, reject) {
    var idSeq = 0;
    var stats = {
      createPageCalls: 0,
      frames: [],
      components: [],
      sets: [],
      variantInSet: 0,
      reactions: [],
      texts: 0,
      notify: []
    };

    function makeNode(type, name) {
      var n = {
        type: type, name: name || '', parent: null, children: [], removed: false,
        _w: 100, _h: 100,
        fills: [], strokes: [], strokeWeight: 0, cornerRadius: 0,
        dashPattern: [], effects: [], rotation: 0,
        fontName: null, characters: '', fontSize: 0, reactions: null,
        id: 'n' + (++idSeq),
        get width() { return this._w; }, set width(v) { this._w = v; },
        get height() { return this._h; }, set height(v) { this._h = v; },
        appendChild: function (ch) { if (ch && this.children.indexOf(ch) < 0) { this.children.push(ch); ch.parent = this; } return ch; },
        remove: function () {
          if (this.parent && this.parent.children) {
            var i = this.parent.children.indexOf(this);
            if (i >= 0) this.parent.children.splice(i, 1);
          }
          this.parent = null; this.removed = true;
        },
        resize: function (w, h) { this._w = w; this._h = h; },
        setReactionsAsync: function (list) { this.reactions = list || []; stats.reactions.push(this); return Promise.resolve(); },
        createInstance: function () { var i = makeNode('INSTANCE', 'instance'); i._w = this._w; i._h = this._h; return i; }
      };
      // fills/strokes 写入时做与 Figma 一致的校验（颜色含 NaN 即抛错），杜绝静默假通过
      Object.defineProperty(n, 'fills', {
        enumerable: true, configurable: true,
        get: function () { return n._fills || []; },
        set: function (v) { validatePaints(v); n._fills = v; }
      });
      Object.defineProperty(n, 'strokes', {
        enumerable: true, configurable: true,
        get: function () { return n._strokes || []; },
        set: function (v) { validatePaints(v); n._strokes = v; }
      });
      return n;
    }

    function makeTextNode() {
      var n = makeNode('TEXT', 'text');
      Object.defineProperty(n, 'width', { get: function () { return Math.max(10, Math.round(String(this.characters || '').length * (this.fontSize || 12) * 0.62)); } });
      Object.defineProperty(n, 'height', { get: function () { return Math.max(8, Math.round((this.fontSize || 12) * 1.5)); } });
      return n;
    }

    var pages = [];
    for (var p = 0; p < initialPageCount; p++) pages.push(makeNode('PAGE', 'Page ' + (p + 1)));

    var doneResolve = null;
    var done = new Promise(function (r) { doneResolve = r; });

    var _cp = pages[0] || null; // figma.currentPage 的内部值

    var figma = {
      root: { children: pages },
      loadAllPagesAsync: function () { return Promise.resolve(); },
      listAvailableFontsAsync: function () { return Promise.resolve([]); },
      loadFontAsync: function () { return Promise.resolve(); },
      createPage: function () { stats.createPageCalls++; var pg = makeNode('PAGE', 'Page'); pages.push(pg); _cp = pg; return pg; },
      createFrame: function () { var f = makeNode('FRAME', 'Frame'); stats.frames.push(f); if (_cp) _cp.appendChild(f); return f; },
      createText: function () { stats.texts++; return makeTextNode(); },
      createRectangle: function () { return makeNode('RECTANGLE', 'Rectangle'); },
      createEllipse: function () { return makeNode('ELLIPSE', 'Ellipse'); },
      createNodeFromSvg: function (svg) { var f = makeNode('FRAME', 'SvgIcon'); f._svg = svg; return f; },
      createComponent: function () { var c = makeNode('COMPONENT', 'Component'); stats.components.push(c); if (_cp) _cp.appendChild(c); return c; },
      combineAsVariants: function (comps, pg) {
        stats.variantInSet += comps.length;
        comps.forEach(function (c) { pg.appendChild(c); });
        var set = makeNode('COMPONENT_SET', 'ComponentSet');
        pg.appendChild(set);
        stats.sets.push(set);
        return set;
      },
      createPaintStyle: function () { return makeNode('PAINT_STYLE', ''); },
      createTextStyle: function () { return makeNode('TEXT_STYLE', ''); },
      createEffectStyle: function () { return makeNode('EFFECT_STYLE', ''); },
      notify: function (msg, o) { stats.notify.push({ msg: msg, opts: o }); },
      closePlugin: function () { if (doneResolve) doneResolve(); }
      // 注意：不提供 figma.variables → 触发「降级为 Color Styles」路径
    };

    // currentPage 默认可读写；opts.throwOnCurrentPageSet = true 时模拟「插件无权赋值」的受限场景
    Object.defineProperty(figma, 'currentPage', {
      enumerable: true, configurable: true,
      get: function () { return _cp; },
      set: function (v) {
        if (opts && opts.throwOnCurrentPageSet) throw new Error('[stub] dynamic-page: figma.currentPage is not writable');
        _cp = v;
      }
    });

    var logs = [];
    var quietConsole = {
      log: function () { logs.push(Array.prototype.join.call(arguments, ' ')); },
      warn: function () { logs.push('WARN ' + Array.prototype.join.call(arguments, ' ')); },
      error: function () { logs.push('ERROR ' + Array.prototype.join.call(arguments, ' ')); }
    };

    var ctx = vm.createContext({ figma: figma, console: quietConsole });
    try {
      vm.runInContext(code, ctx, { filename: 'code.js' });
    } catch (e) {
      return reject(e);
    }

    var timer = setTimeout(function () {
      reject(new Error('主流程 5s 内未调用 figma.closePlugin（疑似挂起）'));
    }, 5000);

    done.then(function () {
      clearTimeout(timer);
      var SPEC = ctx.SPEC;
      if (!SPEC) return reject(new Error('未能从 code.js 读取到 SPEC（vm 上下文未暴露）'));
      resolve({ stats: stats, logs: logs, SPEC: SPEC, pages: pages });
    }).catch(reject);
  });
}

// ---------------------------------------------------------------------------
// 断言器
// ---------------------------------------------------------------------------
var results = [];
function check(desc, actual, expected) {
  var ok = actual === expected;
  results.push({ ok: ok, desc: desc, actual: actual, expected: expected });
  return ok;
}
function checkTrue(desc, cond, actual) {
  results.push({ ok: !!cond, desc: desc, actual: actual, expected: 'true' });
  return !!cond;
}

// ---------------------------------------------------------------------------
// 场景运行 + 断言
// ---------------------------------------------------------------------------
function summarize(run) {
  var s = run.stats;
  var screenNames = {};
  run.SPEC.screenFrames.forEach(function (f) { screenNames[f.name] = 1; });
  var overlayNames = {};
  run.SPEC.overlayFrames.forEach(function (f) { overlayNames[f.name] = 1; });

  var screens = s.frames.filter(function (f) { return screenNames[f.name]; });
  var overlays = s.frames.filter(function (f) { return overlayNames[f.name]; });
  var triggers = s.frames.filter(function (f) { return f.name.indexOf('trigger: ') === 0; });

  return {
    pages: run.pages.length,
    createPageCalls: s.createPageCalls,
    screenFrames: screens.length,
    specOverlays: overlays.length,
    scaffolds: s.frames.filter(function (f) { return f.name.indexOf('OV-CONFIRM') === 0; }).length,
    triggers: triggers.length,
    // 已真正绘制 UI 的帧（有子图层）与「触发按钮被放进源 Frame 内」的反例计数
    drawnScreens: screens.filter(function (f) { return f.children.length > 0; }).length,
    drawnOverlays: overlays.filter(function (f) { return f.children.length > 0; }).length,
    triggersInsideScreen: triggers.filter(function (t) { return screenNames[t.parent && t.parent.name]; }).length,
    hotspots: s.frames.filter(function (f) { return f.name.indexOf('交互热点 · ') === 0; }).length,
    expectedHotspots: run.SPEC.connections.map(function (c) { return c.from; })
      .filter(function (v, i, a) { return a.indexOf(v) === i; }).length,
    stickers: s.frames.filter(function (f) { return f.name.indexOf('DecisionSticker D') === 0; }),
    // 长页「滚动续帧」（含 offset 绘制的续帧）：数量与是否确实画了内容
    splitFrames: s.frames.filter(function (f) { return f.name.indexOf('（滚动续）') >= 0; }),
    expectedSplits: Object.keys(run.SPEC.scrollSplit || {}).length,
    disabled: s.frames.filter(function (f) { return f.name.indexOf('disabled: ') === 0; }).length,
    componentSets: s.sets.length,
    singleComponents: s.components.length - s.variantInSet,
    variants: s.variantInSet,
    reactions: s.reactions.length,
    notify: s.notify,
    logs: run.logs,
    SPEC: run.SPEC
  };
}

function assertCommon(tag, sum) {
  var SPEC = sum.SPEC;
  var expectedScreens = SPEC.screenFrames.length;
  var expectedOverlays = SPEC.overlayFrames.length;
  var expectedNonNone = SPEC.connections.filter(function (c) { return c.type !== 'none'; }).length;
  var expectedNone = SPEC.connections.filter(function (c) { return c.type === 'none'; }).length;

  check('[' + tag + '] Page 数 ≤ 3（Starter 上限）', sum.pages <= 3 ? true : false, true);
  check('[' + tag + '] Page 数 = 3（紧凑模式 3 组）', sum.pages, 3);
  check('[' + tag + '] Screen Frame 数', sum.screenFrames, expectedScreens);
  check('[' + tag + '] 规范 Overlay Frame 数', sum.specOverlays, expectedOverlays);
  check('[' + tag + '] 脚手架帧 OV-CONFIRM 数（各端 1）', sum.scaffolds, 2);
  check('[' + tag + '] 组件集数', sum.componentSets, 9);
  check('[' + tag + '] 单组件数（BookingListItem）', sum.singleComponents, 1);
  check('[' + tag + '] 顶层组件数（集 + 单）', sum.componentSets + sum.singleComponents, 10);
  check('[' + tag + '] 触发按钮数 = 非 none 连接数', sum.triggers, expectedNonNone);
  check('[' + tag + '] reaction 数 = 非 none 连接数', sum.reactions, expectedNonNone);
  check('[' + tag + '] 灰置占位数 = type=none 连接数', sum.disabled, expectedNone);

  // 保真度相关：每帧确实画了 UI、触发按钮不覆盖 UI、便签不溢出
  check('[' + tag + '] 已绘制 UI 的 Screen 帧数', sum.drawnScreens, expectedScreens);
  check('[' + tag + '] 已绘制 UI 的 Overlay 帧数', sum.drawnOverlays, expectedOverlays);
  check('[' + tag + '] 交互热点面板数 = 有出边连接的源 Frame 数', sum.hotspots, sum.expectedHotspots);
  check('[' + tag + '] 触发按钮落在源 Frame 内的数量（应为 0）', sum.triggersInsideScreen, 0);
  var overflow = sum.stickers.filter(function (s) { return s.parent && typeof s.parent.width === 'number' && s.width > s.parent.width + 0.5; });
  checkTrue('[' + tag + '] 决策便签不横向溢出父容器', overflow.length === 0, overflow.length);

  // 长页拆帧：数量正确、续帧确实画了内容、源为 TabBar 页的续帧保留 TabBar 实例
  check('[' + tag + '] 长页滚动续帧数', sum.splitFrames.length, sum.expectedSplits);
  checkTrue('[' + tag + '] 续帧已绘制内容', sum.splitFrames.every(function (f) { return f.children.length > 0; }),
    sum.splitFrames.map(function (f) { return f.children.length; }));
  var splitIdsWithTabBar = Object.keys(SPEC.scrollSplit || {}).filter(function (k) {
    return Object.prototype.hasOwnProperty.call(SPEC.tabBarPages, k);
  });
  var splitFramesWithTabBar = sum.splitFrames.filter(function (f) {
    return splitIdsWithTabBar.some(function (k) { return f.name.indexOf(SPEC.scrollSplit[k].id) === 0; });
  });
  check('[' + tag + '] 续帧中「源为 TabBar 页」的数量', splitFramesWithTabBar.length, splitIdsWithTabBar.length);
  checkTrue('[' + tag + '] 源为 TabBar 页的续帧含 TabBar 实例', splitFramesWithTabBar.every(function (f) {
    return f.children.some(function (c) { return c.type === 'INSTANCE'; });
  }), splitFramesWithTabBar.length);

  var drawFail = sum.logs.filter(function (l) { return l.indexOf('UI 绘制失败') >= 0; });
  checkTrue('[' + tag + '] 无 UI 绘制失败日志', drawFail.length === 0, drawFail.slice(0, 3));

  // 无"整体中断"：不应出现 生成失败 / 步骤失败
  var hardFail = sum.logs.filter(function (l) { return l.indexOf('生成失败') >= 0 || l.indexOf('步骤失败') >= 0; });
  checkTrue('[' + tag + '] 无生成失败/步骤失败日志', hardFail.length === 0, hardFail.length);
  var msg = sum.notify.map(function (n) { return n.msg; }).join(' | ');
  checkTrue('[' + tag + '] notify 含"紧凑模式"', msg.indexOf('紧凑模式') >= 0, msg);
  checkTrue('[' + tag + '] notify 未标记 error', (sum.notify[0] && sum.notify[0].opts && sum.notify[0].opts.error) !== true, msg);
}

function checkManifestAndStatic() {
  // 静态：无网络、Page 复用而非超限新建
  checkTrue('manifest.networkAccess.allowedDomains = ["none"]',
    !!(manifest.networkAccess && manifest.networkAccess.allowedDomains && manifest.networkAccess.allowedDomains.length === 1 && manifest.networkAccess.allowedDomains[0] === 'none'),
    JSON.stringify(manifest.networkAccess));
  checkTrue('code.js 无 fetch(', code.indexOf('fetch(') < 0, code.indexOf('fetch('));
  checkTrue('code.js 无 XMLHttpRequest', code.indexOf('XMLHttpRequest') < 0, code.indexOf('XMLHttpRequest'));
  // SVG 图标字符串含 xmlns="http://www.w3.org/2000/svg"（命名空间，非网络请求）；排除后不得出现任何 http(s) URL
  var codeNoSvgNs = code.split('http://www.w3.org/2000/svg').join('').split('https://www.w3.org/2000/svg').join('');
  checkTrue('code.js 无 http:// 或 https://（SVG 命名空间除外）',
    codeNoSvgNs.indexOf('http://') < 0 && codeNoSvgNs.indexOf('https://') < 0, 0);
  checkTrue('code.js 不含已移除的 createPages 旧实现', code.indexOf('复用文件默认首屏作为 Page 00') < 0, 0);
  checkTrue('code.js 含 preparePages（复用 + 清空重建）', code.indexOf('function preparePages') >= 0, 0);
}

// ---------------------------------------------------------------------------
// 主流程
// ---------------------------------------------------------------------------
(function main() {
  console.log('== F6.0 插件自检（紧凑模式 / Starter 3-Page 上限）==\n');

  var allRuns = [];

  runScenario(3)  // A：文件既有 3 个空 Page（当前 "dance_v1" 的实际状态）
    .then(function (run) {
      var sum = summarize(run);
      allRuns.push(sum);
      console.log('[A] 既有 3 个空 Page（首次失败的真实场景）');
      console.log('    Page=' + sum.pages + '，createPage 调用=' + sum.createPageCalls + '，Screen=' + sum.screenFrames
        + '，规范Overlay=' + sum.specOverlays + '，脚手架=' + sum.scaffolds
        + '，组件集=' + sum.componentSets + '，单组件=' + sum.singleComponents
        + '，reaction=' + sum.reactions + '，灰置=' + sum.disabled);
      check('[A] 既有 3 页时不再新建 Page', sum.createPageCalls, 0);
      check('[A] Page 数保持 3', sum.pages, 3);
      assertCommon('A', sum);
      return runScenario(1); // B：文件只剩 1 个 Page（需补建 2 个）
    })
    .then(function (run) {
      var sum = summarize(run);
      allRuns.push(sum);
      console.log('\n[B] 既有 1 个 Page（验证"不足才建"）');
      console.log('    Page=' + sum.pages + '，createPage 调用=' + sum.createPageCalls + '，Screen=' + sum.screenFrames
        + '，reaction=' + sum.reactions + '，灰置=' + sum.disabled);
      check('[B] 既有 1 页时仅新建 2 个 Page', sum.createPageCalls, 2);
      check('[B] Page 数补足为 3', sum.pages, 3);
      assertCommon('B', sum);
      return runScenario(3, { throwOnCurrentPageSet: true }); // C：currentPage 赋值被拒
    })
    .then(function (run) {
      var sum = summarize(run);
      allRuns.push(sum);
      console.log('\n[C] currentPage 赋值被拒（模拟"插件无权改当前页"，验证守卫不中断）');
      console.log('    Page=' + sum.pages + '，Screen=' + sum.screenFrames + '，reaction=' + sum.reactions + '，灰置=' + sum.disabled);
      var hardFail = sum.logs.filter(function (l) { return l.indexOf('生成失败') >= 0 || l.indexOf('步骤失败') >= 0; });
      checkTrue('[C] 赋值失败不中断（无"生成失败/步骤失败"）', hardFail.length === 0, hardFail.length);
      checkTrue('[C] 记录了 currentPage 切换失败告警（可忽略）', sum.logs.some(function (l) { return l.indexOf('currentPage 切换失败') >= 0; }), 0);
      check('[C] Page 数 = 3', sum.pages, 3);
      check('[C] Screen Frame 数', sum.screenFrames, sum.SPEC.screenFrames.length);
      check('[C] reaction 数 = 非 none 连接数', sum.reactions,
        sum.SPEC.connections.filter(function (c) { return c.type !== 'none'; }).length);
      check('[C] 灰置占位数 = type=none 连接数', sum.disabled,
        sum.SPEC.connections.filter(function (c) { return c.type === 'none'; }).length);
      checkManifestAndStatic();
    })
    .then(function () {
      // 汇总
      console.log('\n' + '='.repeat(66));
      var pass = 0, fail = 0;
      results.forEach(function (r) {
        if (r.ok) { pass++; console.log('  PASS  ' + r.desc); }
        else { fail++; console.log('  FAIL  ' + r.desc + '  (actual=' + JSON.stringify(r.actual) + ', expected=' + JSON.stringify(r.expected) + ')'); }
      });
      console.log('='.repeat(66));
      console.log('PASS ' + pass + ' / FAIL ' + fail);
      var ok = fail === 0;
      console.log('EXIT=' + (ok ? 0 : 1));
      process.exitCode = ok ? 0 : 1;
    })
    .catch(function (err) {
      console.error('自检异常：', err && err.stack ? err.stack : err);
      process.exitCode = 1;
    });
})();
