# F6.0 会员卡业务规则（Business Rules）

> 日期：2026-10-09（状态更新：2026-10-16）
> 性质：只读审计产物。每条规则区分【现状已固化】（代码强制，原型必须遵守）与【待确认】（open-decisions 有编号，原型用占位/双态表达，不得画成确定交互）
>
> **状态（2026-10-16）**：D1 / D3 / D4 / D5 / D9 已由产品负责人确认（2026-10-16），从「二、待确认」迁入「一、已固化」，正文见 R-B4（修订）、R-B7、R-B8。D2 / D6 / D7 / D8 仍待确认。

## 一、现状已固化的规则（原型必须如实表达）

### R-B1 卡产品规则
- 产品与卡实例分离：产品是模板（价格/次数/有效期/适用课程），卡是学员持有的实例（[REF] membership/models.py:83-145, 146-255）
- 三种计费类型：count（次卡，按 total_credits 扣）/ period（期限卡，按有效期使用）/ unlimited（不限次，仍受有效期约束）
- 产品可配置适用课程白名单（applicable_course_ids）与每周使用上限（max_weekly_usage）
- 产品软删除 + 回收站恢复（admin card-types 页已实现）

### R-B2 发卡规则
- 仅管理员发卡（`@require_roles("admin","super_admin")`）；发卡即生成 ISSUE 流水与卡号
- 同学员同产品默认不可重复发卡，可显式 `allow_duplicate` 续卡
- 发卡可指定生效时间；留空则立即可激活

### R-B3 卡状态规则（状态机详见 entity-state-model.md）
- 五态：PENDING(0) / ACTIVE(1) / EXPIRED(2) / FROZEN(3) / CANCELLED(6)（membership/models.py:49-57）
- 激活三路径：学员自助、管理员、定时任务按生效时间自动激活（scheduler.py:106-244）
- 过期由定时任务处理：expire_at < now 且 ACTIVE → EXPIRED，次卡剩余清零并写 EXPIRE 流水（scheduler.py:51-103）
- 冻结支持冻结天数与自动解冻；解冻前须通过同课程类型冲突检查（conflict-check），冲突卡可指定处理动作（admin-unfreeze 的 action/conflict_card_ids）
- 作废支持单卡与批量，必须填写原因（cancelled_reason）

### R-B4 次数与扣回规则（**预约预扣 + 排期 COMPLETED 确认 —— D1 已确认 2026-10-16**）
- **创建预约时预扣 1 次**（deduct_credit），预约与扣次同事务，任一失败整体回滚（booking/service.py:130-155）
- **排期状态变为 COMPLETED 时确认扣次**：CONSUME 流水已在预扣时记录，不再额外变动、不回补
- **取消预约或排期 CANCELLED 时回补**（restore_credit），行锁保护（booking/service.py:199-269）
- 每次变动写 MembershipCardTransaction 流水（CONSUME/RESTORE…），含 booking_id 与幂等键
- **签到只推进预约状态**（BOOKED→CHECKED_IN），不触发扣次——"正常上课"= 预约成功 + 排期 COMPLETED，不以签到为准（booking/service.py:275-332）
- 卡被删除时 booking.membership_card_id 置 NULL（FK ON DELETE SET NULL，booking/models.py:51-54），预约记录保留

### R-B5 预约规则
- 同一学员同一排期只能有一个有效预约：部分唯一索引 WHERE status IN (BOOKED, CHECKED_IN, COMPLETED)（booking/models.py:71-77）
- 预约状态五值：BOOKED(1)/CANCELLED(2)/CHECKED_IN(3)/COMPLETED(4)/NO_SHOW(5)，DB Check 约束兜底（booking/models.py:66-70）
- 预约来源记录：SELF/ADMIN/TEACHER（booking/models.py:19-22）
- 预约归属：学员只能看/取消自己的预约（F2.2 修复）；教师/管理员按 booking:manage 权限签到与完成（F2.3 行锁）

### R-B6 跨端与安全基线
- 所有卡/预约数据经 `/api/v1` + 租户三层隔离（middleware/ContextVar/ORM 自动注入）
- admin 操作端点全部有 RBAC 装饰器；GET 列表按身份自动过滤归属
- Web 三端统一 api-client（401 刷新/租户头/信封解包），小程序独立同语义实现

### R-B7 期限卡（period）生命周期与预约校验（**D9 + D4 + D5 已确认 2026-10-16**）
> 背景：期限卡 `total_credits=None` 不按次数计费（membership/service.py:1365-1366），仅按有效期计费。

- **发卡即 PENDING**：valid_from / expire_at 均留空待定，不在发卡时计算有效期
- **预约不激活、不扣次**：期卡预约时不写卡；按「排期日 + validity_days」计算**预期有效期**（valid_from=排期日，expire_at=排期日+validity_days-1），仅用于冲突预校验，不写入卡
- **预约时区间重叠冲突检查**：预期有效期与学员已有同课程类型 ACTIVE/PENDING 卡的有效期做标准区间重叠判断（复用 scheduler 区间重叠逻辑），有交集则拒绝预约
- **排期 COMPLETED 时激活**：若卡仍 PENDING → 激活（status=ACTIVE）并写入 valid_from=排期日、expire_at=排期日+validity_days；若已 ACTIVE（非首次）→ 无操作
- **排期 CANCELLED 时**：期卡不激活，PENDING 保持；次卡回补（见 R-B4）
- **有效期边界（D4）**：expire_at 当天 23:59:59 前可预约可签到；PENDING 卡（未到生效日）不可预约，选卡列表灰显"MM-DD 生效"
- **缺席（D5）**：排期 COMPLETED 即扣/激活，学员是否到场不影响结果——"课开即扣"；NO_SHOW 状态保留但不再有"扣不扣"的决策，教师/管理员可标记缺席仅作记录
- **配套规则**：a) PENDING 期卡发卡后 90 天无任何 COMPLETED 排期 → 定时任务自动 CANCELLED（"超期未激活"）；b) freeze 对 PENDING 拒绝（"未激活卡不可冻结"）；c) 定时任务 EXPIRED 扫描范围扩展至 `status IN (ACTIVE, PENDING)`

### R-B8 卡失效后的替代策略（**D3 已确认 2026-10-16**）
- **三层策略**：a) 卡状态变更（冻结/过期/作废）时，预约列表对受影响预约给出警示；b) 学员可自助换卡改派（复用改派事务骨架，原子化见 D7）；c) 无替代卡时引导学员联系机构
- 管理端作废/冻结前展示"该卡有 N 个有效预约"影响面提示
- 原型中"换卡"入口标注为「待新增 · 真实项目不存在」并灰置，不伪造后端改派端点

## 二、待确认规则（原型中用占位/双态呈现，禁止画成定论）

| # | 规则 | 现状与矛盾点 | 决策编号 |
|---|------|--------------|---------|
| 1 | 次卡用尽是否独立状态 | 现状无 EXHAUSTED，remaining=0 仍 ACTIVE；"已用尽"在原型上只能以余额徽标表达 | D2 |
| 2 | 多卡顺延策略 | 多张可用卡时的默认推荐逻辑在小程序有简单实现（getDefaultSelectedCard），但"优先消耗先过期卡"等策略未定义 | D6 |
| 3 | 原子改期 | 无改期端点；改期=取消+重约，中间存在"次数已回补但新名额未锁定"的窗口 | D7 |
| 4 | 退款与撤销核销 | REFUND/ADJUST 仅存在于枚举；退款流程依赖支付渠道（F6.1），撤销核销无产品化端点 | D8 |

## 三、原型表达约定

1. 已固化规则 → 原型按现状画**确定性交互**（如：预约成功页必须显示"已扣 1 次，剩余 N 次"）
2. 待确认规则 → 原型页面用**决策占位标记**（黄色便签样式，标注 D 编号），关键分叉可画双分支（如 D1 的两种扣次模式各画一版签到确认页）
3. 未实现但本次规划的功能（购卡、退款、预约管理）→ 原型可画理想流程，但必须在页面角落标注"依赖 F6.1/F6.2"
4. 任何原型页面不得出现后端不存在的 API 假调用路径（契约核对清单见 interaction-spec.md 附录）
