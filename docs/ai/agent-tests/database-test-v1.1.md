# Alembic Migration 方案分析 — Booking 表新增 booking_source 字段

## 1. 当前 Booking 表真实状态

### 1.1 ORM Model（当前代码）

```python
# modules/booking/models.py

class BookingSource(Enum):          # 🔴 当前已有！
    SELF = "self"
    ADMIN = "admin"
    TEACHER = "teacher"

class Booking(Base, TenantMixin, TimestampMixin):
    __tablename__ = "bookings"
    ...
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default=BookingSource.SELF.value
    )   # 🔴 当前已存在的 source 字段
```

### 1.2 关键发现

| 项 | 值 |
|----|-----|
| 当前字段名 | `source` |
| 类型 | String(20), NOT NULL |
| 默认值 | `"self"`（Python 端 default，**无** server_default） |
| 枚举值 | `self` / `admin` / `teacher` |
| 语义 | **操作人角色维度**：谁在操作？用户自己约？管理员代约？教师代约？ |
| 在 Alembic 中的定义 | `4bd04b738098_init_all_tables.py:465` — `sa.Column("source", sa.String(length=20), nullable=False)` |

---

## 2. 设计决策：扩展现有 source vs 新增 booking_source

### 2.1 用户需求分析

| 值 | 语义 | 与现有 source 的关系 |
|----|------|---------------------|
| `web` | 从 Web H5 入口发起 | **不存在于 source** — 不是操作人，是入口渠道 |
| `mini_program` | 从微信小程序发起 | **不存在于 source** — 入口渠道 |
| `admin` | 从管理后台发起 | source 里也有 admin，但语义不同（见下） |
| `ai_agent` | AI Agent 发起 | **不存在于 source** — 入口渠道 |

### 2.2 两个维度对比

| 维度 | 字段 | 枚举值 | 含义 |
|------|------|--------|------|
| **操作人角色** | `source`（现有） | self / admin / teacher | 谁在点击"提交"按钮？ |
| **入口渠道** | `booking_source`（新增） | web / mini_program / admin / ai_agent | 从哪个入口进来点的？ |

### 2.3 "admin" 在两个维度中的不同含义

```
场景：管理员从管理后台代用户约课

  source = "admin"          ← 操作人是管理员
  booking_source = "admin"  ← 入口是管理后台
  
  两者都是 admin，但一个说"谁做的"，一个说"从哪做的"
  独立维度，不能合并
```

```
场景：用户从 Web 自己约课

  source = "self"              ← 操作人是用户自己
  booking_source = "web"       ← 入口是 Web
  
  self ≠ web，两者互补不重叠
```

### 2.4 结论：**必须新增独立的 booking_source 字段**

❌ 不能给现有 source 加 web/mini_program/ai_agent 枚举值——语义混淆（操作人 vs 入口渠道）。
✅ 必须加新列 `booking_source`。

---

## 3. 字段设计

### 3.1 基本属性

| 属性 | 值 | 理由 |
|------|-----|------|
| 列名 | `booking_source` | 明确是"约课入口渠道"，区分于现有 `source` |
| Type | `VARCHAR(32)` | 比现有 source(20) 略宽，留扩展空间 |
| **NULL 允许** | **NOT NULL** | 不允许"未知来源"。所有预约必须有明确来源 |
| **DEFAULT** | **`'web'`（server_default）** | 见 3.2 说明 |
| Check Constraint | ❌ 不加（见 3.3 说明） | — |

### 3.2 Default 值选择

**选项 A：DEFAULT 'web'（推荐）**

```sql
ALTER TABLE bookings ADD COLUMN booking_source VARCHAR(32) NOT NULL DEFAULT 'web';
```

理由：
- 生产环境所有历史数据需要一个合理的默认值
- web 是最通用的入口，几乎覆盖所有历史预约场景
- PostgreSQL 11+ 中，**ADD COLUMN + DEFAULT 是元数据操作，不扫描全表**（O(1)），零锁表风险
- 新预约写入时，Router/Service 会显式传入 booking_source（见 3.4），server_default 只是历史数据回填和新开发环境的兜底

**选项 B：DEFAULT 'self'** — ❌ 不行，self 不是入口渠道
**选项 C：DEFAULT NULL** — ❌ 不行，丢失数据来源信息

### 3.3 关于 Check Constraint：**不加**

```sql
-- ❌ 不这样做：
ALTER TABLE bookings ADD CONSTRAINT chk_booking_source
  CHECK (booking_source IN ('web', 'mini_program', 'admin', 'ai_agent'));
```

**理由：**

| 考量 | 说明 |
|------|------|
| 未来扩展性 | 新入口（如抖音小程序、iOS App）可能随时出现，加 CHECK 约束后每次加新值都要 DDL 变更 |
| 当前枚举规模 | 只有 4 个值，应用层校验足够 |
| 如果未来要加 CHECK | 可以在应用稳定后用新 migration 追加 |

**替代方案：在 Service 层校验**

```python
# create_booking 中显式校验
VALID_BOOKING_SOURCES = {'web', 'mini_program', 'admin', 'ai_agent'}
if booking_source not in VALID_BOOKING_SOURCES:
    raise ValidationException(f"无效的预约来源: {booking_source}")
```

### 3.4 应用层枚举定义

```python
# modules/booking/models.py 新增

class BookingChannel(Enum):  # 注意：避免和现有 BookingSource 混淆
    WEB = "web"
    MINI_PROGRAM = "mini_program"
    ADMIN = "admin"
    AI_AGENT = "ai_agent"
```

**命名为什么用 BookingChannel：**

| 候选名 | 问题 |
|--------|------|
| `BookingSource`（复用） | ❌ 已有同名枚举（self/admin/teacher），语义完全不同 |
| `BookingOrigin` | 可以，但不如 Channel 直观 |
| `BookingChannel` | ✅ 明确表达"入口渠道"，与现有 BookingSource（操作人角色）清晰区分 |

### 3.5 是否需要 Index？

**❌ 不需要。**

| 考量 | 说明 |
|------|------|
| 选择性 | 只有 4 个枚举值，区分度极低 |
| 典型查询模式 | 按 student_id 查、按 schedule_id 查、按 status 查——**几乎不会**单独按 booking_source 查 |
| 联合查询 | `tenant_id + booking_source` 可能有人想做维度统计，但这类低基数联合索引收益极低 |
| 写入成本 | 每次 INSERT/UPDATE 都要维护索引，纯开销 |
| 结论 | 应用层维度统计可以接受全表扫描（或用 tenant_id+status 现有索引辅助） |

---

## 4. 数据量评估

| 项 | 值 |
|----|-----|
| 生产 bookings 表数据量 | **UNKNOWN**（需 `SELECT COUNT(*) FROM bookings`） |
| 表增长速率 | UNKNOWN |
| 行大小（当前） | ~300 bytes/行（粗估） |
| 新增字段增加 | ~20 bytes/行（VARCHAR(32) + NULL bitmap 调整） |

**但无论数据量多少，本次迁移都是安全的**——见第 6 节锁表风险分析。

---

## 5. Alembic Migration 设计

### 5.1 Migration 文件结构

```
apps/api/alembic/versions/
  ├── 211f847af16c_merge_heads_for_frozen_remaining_days.py    (HEAD — 当前)
  └── abcdef123456_add_booking_source_to_bookings.py           ← 新增
```

### 5.2 Revision 元数据

```python
"""add booking_source column to bookings

Revision ID: abcdef123456
Revises: 211f847af16c
Create Date: 2026-09-21 18:00:00.000000

"""
```

### 5.3 Upgrade（生产环境执行）

```python
def upgrade() -> None:
    """
    PostgreSQL 11+:
      ALTER TABLE ADD COLUMN + DEFAULT is metadata-only (O(1)),
      does NOT rewrite the whole table. Zero lock risk.
    
    分两步执行（显式 server_default 以便后续可以安全移除）:
      1. ADD COLUMN booking_source VARCHAR(32) NOT NULL DEFAULT 'web'
      2. （可选）移除 server_default，改由应用层写入
    """
    op.add_column(
        "bookings",
        sa.Column("booking_source", sa.String(length=32), nullable=False,
                  server_default="web"),
    )
```

**注意事项：**

| 项 | 说明 |
|----|------|
| 为什么用 `server_default` 而不是 Python `default`？ | Alembic 执行时没有 Python 应用层，server_default 让 PostgreSQL 自己给历史行赋值 |
| 为什么 `nullable=False` + `default`？ | 两个一起加在 PostgreSQL 11+ 是元数据操作 |
| 如果 PostgreSQL < 11？ | 需要先 ADD COLUMN nullable + UPDATE 历史数据 + 再 ALTER SET NOT NULL |

### 5.4 Downgrade（回滚安全）

```python
def downgrade() -> None:
    """
    DROP COLUMN 在 PostgreSQL 11+ 也是元数据操作。
    唯一风险：如果迁移后有新数据写入 booking_source='ai_agent'，
    downgrade 会丢失这些信息。
    
    但 downgrade 本来就是最后手段（紧急回滚场景），
    丢失少量数据可接受。
    """
    op.drop_column("bookings", "booking_source")
```

### 5.5 Downgrade 安全等级

| 维度 | 评估 |
|------|------|
| 语法正确 | ✅ |
| 不丢其他数据 | ✅ 只删 booking_source 列 |
| 可重放性 | ✅ 先 upgrade 再 downgrade 可以回退到原始状态 |
| 新数据丢失风险 | ⚠️ 会丢失 migration 后写入的 booking_source 值（但 downgrade 是紧急场景） |
| 是否有依赖 | ❌ 不依赖其他表/约束，可以独立执行 |

---

## 6. 锁表风险分析

### 6.1 PostgreSQL 版本影响

| PostgreSQL 版本 | ADD COLUMN + DEFAULT 行为 | 锁表时间 |
|----------------|---------------------------|---------|
| **>= 11** | 元数据操作，不扫描全表 | **毫秒级**（几乎不锁） |
| 9.1 ~ 10 | 重写表，全量 UPDATE | 可能数分钟（取决于数据量） |
| < 9.1 | 不支持 | — |

### 6.2 本项目 PostgreSQL 版本

| 项 | 值 |
|----|-----|
| Docker Compose PostgreSQL 镜像 | **UNKNOWN**（需检查 docker-compose.yml） |
| 应用层配置 | UNKNOWN |

**检查命令：**
```sql
SELECT version();
-- 或
SHOW server_version;
```

### 6.3 假设是 PostgreSQL >= 11（最可能）

```sql
-- 实际执行的 DDL：
ALTER TABLE bookings ADD COLUMN booking_source VARCHAR(32) NOT NULL DEFAULT 'web';

-- PostgreSQL 11+ 内部行为：
-- 1. pg_catalog.pg_attribute 元数据更新          ← 微秒级
-- 2. pg_class 行描述符调整                      ← 微秒级
-- 3. 新行自动携带 default 值                    ← O(1)
-- 4. 旧行通过 pg_attribute.atttypmod 记录 default ← 不物理改写

锁等级：ACCESS EXCLUSIVE（ALTER TABLE 需要最高锁级别）
锁时间：**毫秒级**（几乎感知不到）
影响行数：0（不扫描数据行）
```

### 6.4 假设是 PostgreSQL < 11（不太可能）

```
风险：
  - ALTER TABLE ADD COLUMN NOT NULL DEFAULT 会重写整张表
  - 大表（如 100 万行）可能锁数十秒甚至数分钟
  - 期间所有对 bookings 的 DML 被阻塞

降低策略：
  分三步替代：
    1. ALTER TABLE bookings ADD COLUMN booking_source VARCHAR(32) NULL
       ← 元数据操作，无锁风险
    
    2. UPDATE bookings SET booking_source = 'web' WHERE booking_source IS NULL
       ← 可以分批执行（chunk 1000 行一次 + 短事务），避免长锁
    
    3. ALTER TABLE bookings ALTER COLUMN booking_source SET NOT NULL
       ← 元数据操作，检查全表无 NULL
```

**但按 Docker 官方 postgres 镜像惯例，默认都是 PostgreSQL 14/15/16。**

### 6.5 锁表风险总结

| 场景 | 锁等级 | 预估锁时间 | 风险 |
|------|--------|-----------|------|
| PostgreSQL >= 11（预期） | ACCESS EXCLUSIVE | **< 10ms** | **极低** |
| PostgreSQL < 11（假设） | ACCESS EXCLUSIVE | 数据量相关 | 中等（需分步） |

---

## 7. 完整 Migration 文件（Upgrade + Downgrade）

```python
"""add booking_source column to bookings

新增 booking_source 列，区分于现有 source（操作人角色维度）。
booking_source 是"入口渠道维度"：web / mini_program / admin / ai_agent

Upgrade:  ADD COLUMN + DEFAULT（PostgreSQL 11+ 元数据操作，零锁风险）
Downgrade: DROP COLUMN

Revision ID: abcdef123456
Revises: 211f847af16c
Create Date: 2026-09-21 18:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abcdef123456'
down_revision: str = '211f847af16c'
branch_labels: str | None = None
depends_on: str | None = None


VALID_SOURCES = ('web', 'mini_program', 'admin', 'ai_agent')


def upgrade() -> None:
    """
    PostgreSQL 11+: ALTER TABLE ADD COLUMN + DEFAULT 是元数据操作，
    不扫描全表、不重写数据、毫秒级锁。
    
    如果是 PostgreSQL < 11：分三步
      step1: ADD COLUMN nullable
      step2: UPDATE historical data in batches
      step3: ALTER COLUMN SET NOT NULL
    """
    op.add_column(
        'bookings',
        sa.Column(
            'booking_source',
            sa.String(length=32),
            nullable=False,
            server_default='web',
            comment='预约入口渠道: web / mini_program / admin / ai_agent',
        ),
    )


def downgrade() -> None:
    """DROP COLUMN — PostgreSQL 11+ 也是元数据操作"""
    op.drop_column('bookings', 'booking_source')
```

---

## 8. 生产环境执行步骤

### 8.1 执行前检查

```sql
-- 1. 确认 PostgreSQL 版本
SELECT version();

-- 2. 确认 bookings 表当前行数
SELECT count(*) FROM bookings;

-- 3. 确认目标列不存在（幂等检查）
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'bookings' AND column_name = 'booking_source';
-- 预期：0 行（不存在）
```

### 8.2 执行 Migration

```bash
cd apps/api
alembic upgrade head
```

### 8.3 执行后验证

```sql
-- 1. 确认列已存在且 NOT NULL
SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'bookings' AND column_name = 'booking_source';

-- 预期: booking_source | character varying | 32 | NO | 'web'::character varying

-- 2. 确认历史数据全部回填为 'web'
SELECT booking_source, count(*) FROM bookings GROUP BY booking_source;
-- 预期: web | N（所有历史行）

-- 3. 确认 Alembic 版本记录
SELECT version_num FROM alembic_version;
-- 预期: abcdef123456
```

### 8.4 回滚方案（如果 upgrade 失败）

```bash
# Alembic 执行失败时会自动回滚事务
# 如果已经成功但需要回退：
alembic downgrade -1
```

---

## 9. 后续代码适配（非 Migration 范畴，供参考）

### 9.1 Booking Model 加字段

```python
# modules/booking/models.py — 新增枚举和字段

class BookingChannel(Enum):
    WEB = "web"
    MINI_PROGRAM = "mini_program"
    ADMIN = "admin"
    AI_AGENT = "ai_agent"

class Booking(Base, ...):
    # ... 现有字段 ...
    booking_source: Mapped[str] = mapped_column(
        String(32), nullable=False, default=BookingChannel.WEB.value
    )
```

### 9.2 BookingCreate Schema 加字段

```python
# modules/booking/schemas.py

class BookingCreate(BaseModel):
    schedule_id: int
    membership_card_id: int | None = None
    source: str | None = "self"
    booking_source: str | None = None  # ← 新增，由 Router 注入
```

### 9.3 Router 根据请求入口自动填充

```python
# modules/booking/router.py

@router.post("/", ...)
async def create_booking(
    data: BookingCreate = Body(...),
    current_user: dict = Depends(get_current_user),
    request: Request = None,  # ← 注入 Request
):
    # 根据 User-Agent / 路由前缀 / 部署域名 判断入口渠道
    booking_source = detect_booking_source(request)
    result = await booking_service.create_booking(
        db, data, student_id=..., booking_source=booking_source
    )
```

---

## 10. 风险评估总览

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|------|------|------|
| R1 | PostgreSQL < 11 导致重写表 | **极低** | 中 | 分三步执行 |
| R2 | 生产执行时应用写入新预约但 booking_source 冲突 | 低 | 低 | server_default='web' 兜底，应用层会在 Migration 完成后同步部署 |
| R3 | Downgrade 丢失 migration 后新写入的 booking_source | 低 | 低 | Downgrade 是紧急回滚手段，丢失可接受 |
| R4 | 不加 CHECK 约束导致脏数据 | 低 | 低 | Service 层显式校验 |
| R5 | DEFAULT 'web' 不能准确反映历史数据入口 | 高 | 低 | 历史数据只能用合理默认回填，无法精确还原 |

---

## 11. UNKNOWN 项

| # | 项目 | 原因 | 建议 |
|---|------|------|------|
| UNK-1 | 生产 PostgreSQL 版本 | 未查询 `SELECT version()` | 执行 Migration 前先确认 |
| UNK-2 | bookings 表当前行数 | 未连接生产 DB | `SELECT count(*) FROM bookings` |
| UNK-3 | Docker 镜像 tag | 未读 docker-compose.yml | 确认 postgres 版本 |
| UNK-4 | 历史预约实际入口分布 | 没有入口渠道历史数据 | 接受用 'web' 作为合理默认 |

---

## 12. 最终 Migration 方案总结

| 项 | 决定 |
|----|------|
| 新增列 | `booking_source VARCHAR(32) NOT NULL DEFAULT 'web'` |
| 不加 Check Constraint | 应用层 Service 校验，保留未来扩展灵活性 |
| 不加 Index | 低基数枚举列，无有效查询模式 |
| Alembic head | `211f847af16c` → 新增 `abcdef123456` |
| Upgrade | 单次 `op.add_column()`（PostgreSQL 11+ 元数据操作） |
| Downgrade | `op.drop_column()` |
| 锁表风险 | PostgreSQL >= 11: **毫秒级**；< 11: 需分步 |
| 回滚安全 | ✅ 安全（DROP COLUMN 是元数据操作） |
| 生产执行建议 | 低峰期（即使毫秒级也建议习惯） |