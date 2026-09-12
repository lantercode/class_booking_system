# 会员卡冻结与到期处理方案

## 已修复的Bug

### 1. frozen_at 非空约束错误
**问题**：创建 MembershipCardFreeze 记录时未设置 frozen_at 字段
**修复**：在 service.py 的 freeze_card 方法中添加 frozen_at=datetime.now(timezone.utc)

### 2. 激活后未计算到期时间
**问题**：activate_card 和 admin_activate_card 方法中的逻辑错误
**修复**：修正 validity_days 的获取逻辑，确保正确计算 expire_at

---

## 次卡冻结方案

### 核心设计
次卡和期卡都需要冻结，冻结期间的核心逻辑：
1. 暂停有效期计算：冻结期间不计入有效期
2. 自动顺延到期时间：冻结时根据冻结天数延长 expire_at
3. 支持临时冻结和无限期冻结

### 实现细节

#### 1. 冻结时指定冻结天数
```python
async def freeze_card(
    self, 
    db: AsyncSession, 
    card_id: int, 
    tenant_id: int, 
    reason: str, 
    operator_id: int,
    freeze_days: int | None = None,
) -> MembershipCard:
    card.status = CardStatus.FROZEN.value
    card.frozen_reason = reason

    if freeze_days and card.expire_at:
        card.expire_at = card.expire_at + timedelta(days=freeze_days)

    freeze = MembershipCardFreeze(
        tenant_id=tenant_id, 
        card_id=card.id, 
        reason=reason, 
        operator_id=operator_id,
        frozen_at=datetime.now(timezone.utc)
    )
    db.add(freeze)
    return card
```

#### 2. API 请求体
```python
class MembershipCardFreezeRequest(BaseModel):
    reason: str = Field(..., max_length=255, description="冻结原因")
    freeze_days: int | None = Field(None, ge=1, description="冻结天数")
```

#### 3. 使用示例
```bash
# 临时冻结7天
POST /membership/cards/123/freeze
{
  "reason": "外出旅游",
  "freeze_days": 7
}

# 无限期冻结
POST /membership/cards/123/freeze
{
  "reason": "暂停使用"
}
```

---

## 次卡到期处理方案

### 方案A：到期自动清零（已实现）

**优点**：
- 业务逻辑简单清晰
- 符合大多数商业场景
- 避免长期负债

**实现逻辑**：
```python
async def auto_expire_membership_cards():
    for card in expired_cards:
        remaining = card.total_credits - card.used_credits
        
        if card.card_type == "count" and remaining > 0:
            txn = MembershipCardTransaction(
                operation_type=TransactionType.EXPIRE.value,
                change_amount=-remaining,
                balance_after=0,
                remark=f"会员卡到期，剩余{remaining}次自动清零"
            )
            card.used_credits = card.total_credits
        
        card.status = CardStatus.EXPIRED.value
```

**定时任务配置**：每小时执行一次

### 方案B：付费延期（已实现）

**实现逻辑**：
```python
async def extend_card(
    self,
    db: AsyncSession,
    card_id: int,
    tenant_id: int,
    extend_days: int,
    operator_id: int,
    remark: str = "付费延期",
) -> MembershipCard:
    card.expire_at = card.expire_at + timedelta(days=extend_days)
    
    txn = MembershipCardTransaction(
        operation_type=TransactionType.ADJUST.value,
        change_amount=0,
        balance_after=card.remaining_credits,
        operator_id=operator_id,
        remark=f"{remark}：有效期延长{extend_days}天"
    )
    return card
```

**API 端点**：
```bash
POST /membership/cards/{card_id}/extend
{
  "extend_days": 30,
  "remark": "付费延期"
}
```

**权限**：仅 admin 和 super_admin 可操作

---

## 到期提醒功能

### 实现
```python
async def notify_expiring_membership_cards():
    three_days_later = now + timedelta(days=3)
    
    for card in cards:
        days_left = (card.expire_at - now).days
        remaining = card.remaining_credits
        
        logger.info(
            f"[到期提醒] 会员卡 {card.id} "
            f"将在 {days_left} 天后到期，剩余次数: {remaining}"
        )
```

**定时任务配置**：每小时执行一次

**扩展建议**：
- 接入短信服务（阿里云、腾讯云）
- 微信模板消息推送
- App推送通知
- 邮件通知

---

## 完整生命周期

```
PENDING（待激活）
    ↓ [激活/到达valid_from]
ACTIVE（正常）
    ↓ [冻结]
FROZEN（已冻结）←→ [解冻] → ACTIVE
    ↓ [到期]
EXPIRED（已过期）

特殊状态：
- DEPLETED（次卡已用完）
- REFUNDED（已退款）
- CANCELLED（已取消）
```

---

## 修改文件清单

| 文件 | 修改内容 |
|------|---------|
| service.py | 修复frozen_at非空约束、修复激活逻辑、添加extend_card方法 |
| schemas.py | 添加freeze_days参数、添加MembershipCardExtendRequest |
| router.py | 更新freeze_card路由、添加extend_card路由 |
| scheduler.py | 完善auto_expire逻辑、添加notify_expiring任务 |
| main.py | 注册notify_expiring_membership_cards定时任务 |

---

## 业务建议

1. **冻结策略**：
   - 建议限制每年冻结次数（如最多3次）
   - 冻结天数上限（如最多30天）
   - 冻结期间不允许使用

2. **到期策略**：
   - 提前7天、3天、1天发送提醒
   - 到期后给予3天宽限期（可配置）
   - 支持付费延期（价格可配置）

3. **次卡设计**：
   - 次卡必须有到期时间（validity_days必填）
   - 到期未用完次数自动清零
   - 支持充值增加次数（不延长有效期）

4. **数据审计**：
   - 所有操作记录流水
   - 冻结/解冻记录完整历史
   - 支持导出报表