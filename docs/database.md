# Database

## Purpose

本文档描述 class_booking_system 的数据库设计、表结构、模型继承关系、Alembic 迁移状态及多租户隔离机制。所有描述基于 apps/api/src/app 下的 SQLAlchemy 模型代码。

## Current Implementation

### 数据库信息

| 项目 | 值 |
|------|------|
| 数据库 | PostgreSQL 15-alpine |
| Driver | asyncpg（异步） |
| URL 格式 | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| 时区 | UTC（所有 DateTime 使用 `timezone=True`） |
| ORM | SQLAlchemy 2.0 (mapped_column + Mapped[type]) |
| 迁移 | Alembic（28 个 migration 文件） |
| 模型聚合入口 | apps/api/src/app/models.py |

### 模型基类体系

所有模型继承三个抽象基类（`app/shared/base_model.py`）：

```python
class Base(DeclarativeBase):       # 所有 ORM 模型的基类
    pass

class TimestampMixin:               # created_at, updated_at
    created_at: DateTime(timezone=True), nullable=False, server_default=func.now()
    updated_at: DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()

class TenantMixin:                  # tenant_id（业务模型专属）
    tenant_id: BigInteger, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
```

继承关系图：

```mermaid
classDiagram
    class Base {
        <<DeclarativeBase>>
    }
    class TimestampMixin {
        <<abstract>>
        +created_at: DateTime
        +updated_at: DateTime
    }
    class TenantMixin {
        <<abstract>>
        +tenant_id: BigInteger FK
    }

    Base <|-- TimestampMixin
    TimestampMixin <|-- TenantMixin
    Base <|-- 纯 Base 继承模型

    Tenant --|> Base + TimestampMixin
    Role --|> Base + TenantMixin + TimestampMixin
    Permission --|> Base  (无 TenantMixin)
    User --|> Base + TenantMixin + TimestampMixin
    Course --|> Base + TenantMixin + TimestampMixin
    CourseSchedule --|> Base + TenantMixin + TimestampMixin
    Classroom --|> Base + TenantMixin + TimestampMixin
    Booking --|> Base + TenantMixin + TimestampMixin
    MembershipCard --|> Base + TenantMixin + TimestampMixin
    MembershipCardProduct --|> Base + TenantMixin + TimestampMixin
    MembershipCardTransaction --|> Base + TenantMixin + TimestampMixin
    MembershipCardFreeze --|> Base + TenantMixin + TimestampMixin
    WechatAccount --|> Base + TimestampMixin (无 TenantMixin，通过 user_id 关联)
    UserRole --|> Base (纯关联表，无 Mixin)
    RolePermission --|> Base (纯关联表，无 Mixin)
```

## Architecture

### 完整 ER 图

```mermaid
erDiagram
    %% ===== 租户 =====
    tenants ||--o{ users : "has"
    tenants ||--o{ roles : "has"
    tenants ||--o{ courses : "has"
    tenants ||--o{ course_categories : "has"
    tenants ||--o{ course_types : "has"
    tenants ||--o{ classrooms : "has"
    tenants ||--o{ course_schedules : "has"
    tenants ||--o{ bookings : "has"
    tenants ||--o{ membership_card_products : "has"
    tenants ||--o{ membership_cards : "has"
    tenants ||--o{ membership_card_transactions : "has"
    tenants ||--o{ membership_card_freezes : "has"

    %% ===== RBAC =====
    users ||--o{ user_roles : "member"
    roles ||--o{ user_roles : "assigns"
    roles ||--o{ role_permissions : "has"
    permissions ||--o{ role_permissions : "granted_to"
    users ||--o| wechat_accounts : "bind"

    %% ===== 课程 =====
    courses ||--o{ course_schedules : "has"
    course_categories ||--o{ courses : "classify"
    course_types ||--o{ courses : "typed"
    classrooms ||--o{ course_schedules : "uses"
    users ||--o{ course_schedules : "teaches"

    %% ===== 预约 =====
    course_schedules ||--o{ bookings : "has"
    users ||--o{ bookings : "books"

    %% ===== 会员卡 =====
    users ||--o{ membership_cards : "owns"
    membership_card_products ||--o{ membership_cards : "generates"
    membership_cards ||--o{ membership_card_transactions : "tracks"
    membership_cards ||--o{ membership_card_freezes : "records"
    bookings }o--|| membership_cards : "uses"

    %% ===== 表定义 =====

    tenants {
        BigInteger id PK
        UUID public_id UK
        String name
        String slug UK
        SmallInteger status "0=DISABLED 1=ACTIVE"
        String plan "free"
        JSONB settings
        DateTime created_at
        DateTime updated_at
    }

    users {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        String user_code UK NULL
        String phone
        String email NULL
        String password_hash
        String nickname NULL
        String real_name NULL
        String avatar_url NULL
        SmallInteger gender NULL "0=UNKNOWN 1=MALE 2=FEMALE"
        Date birthday NULL
        String platform_role NULL
        SmallInteger status "0=DISABLED 1=ACTIVE"
        DateTime last_login_at NULL
        DateTime deleted_at NULL
        DateTime created_at
        DateTime updated_at
    }

    roles {
        BigInteger id PK
        BigInteger tenant_id FK NULL
        String code
        String name
        String description NULL
        Boolean is_system default false
        DateTime created_at
        DateTime updated_at
    }

    permissions {
        BigInteger id PK
        String code UK
        String name
        String module
        String description NULL
    }

    user_roles {
        BigInteger user_id PK FK
        BigInteger role_id PK FK
        DateTime created_at
    }

    role_permissions {
        BigInteger role_id PK FK
        BigInteger permission_id PK FK
    }

    wechat_accounts {
        BigInteger id PK
        BigInteger user_id FK NULL
        String open_id
        String unionid NULL
        String app_id NULL
        String phone NULL
        String nickname NULL
        String avatar_url NULL
        DateTime created_at
        DateTime updated_at
    }

    courses {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        String name
        String category NULL
        String course_type_code NULL
        String level NULL
        String cover_url NULL
        Text description NULL
        SmallInteger duration_minutes
        Numeric price
        SmallInteger required_credits default 1
        SmallInteger status "0=OFFLINE 1=ONLINE"
        DateTime deleted_at NULL
        DateTime created_at
        DateTime updated_at
    }

    course_categories {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        String name
        String code
        Text description NULL
        String icon_url NULL
        Integer sort_order default 0
        SmallInteger status "0=DISABLED 1=ACTIVE"
        DateTime created_at
        DateTime updated_at
    }

    course_types {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        String name
        String code
        Text description NULL
        ARRAY required_card_types NULL
        Integer sort_order default 0
        SmallInteger status "0=DISABLED 1=ACTIVE"
        SmallInteger min_students NULL
        SmallInteger cancel_before_minutes NULL
        DateTime created_at
        DateTime updated_at
    }

    classrooms {
        BigInteger id PK
        BigInteger tenant_id FK
        String name
        ARRAY equipment NULL
        SmallInteger status "0=DISABLED 1=ACTIVE"
        DateTime created_at
        DateTime updated_at
    }

    course_schedules {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        BigInteger course_id FK
        BigInteger teacher_id FK
        BigInteger classroom_id FK NULL
        DateTime start_at
        DateTime end_at
        SmallInteger capacity
        SmallInteger booked_count default 0
        DateTime booking_opens_at NULL
        DateTime booking_closes_at NULL
        DateTime cancel_deadline NULL
        SmallInteger status "1=NORMAL 2=CANCELLED 3=FINISHED"
        Text notes NULL
        Text preview_content NULL
        DateTime preview_updated_at NULL
        Text cancel_reason NULL
        BigInteger cancelled_by NULL
        DateTime cancelled_at NULL
        DateTime created_at
        DateTime updated_at
    }

    bookings {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        BigInteger schedule_id FK
        BigInteger student_id FK
        SmallInteger status "1=BOOKED 2=CANCELLED 3=CHECKED_IN 4=COMPLETED 5=NO_SHOW"
        String source "self/admin/teacher"
        BigInteger membership_card_id NULL
        DateTime booked_at
        DateTime cancelled_at NULL
        String cancelled_reason NULL
        DateTime checked_in_at NULL
        DateTime created_at
        DateTime updated_at
    }

    membership_card_products {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        String name
        String card_type "count/period/unlimited"
        Numeric price
        Integer total_credits NULL
        Integer validity_days NULL
        ARRAY applicable_course_ids NULL
        String applicable_course_type_code NULL
        Integer max_weekly_usage NULL
        Text description NULL
        SmallInteger status "0=OFFLINE 1=ONLINE"
        Integer sort_order default 0
        DateTime deleted_at NULL
        DateTime created_at
        DateTime updated_at
    }

    membership_cards {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        String card_no UK NULL "yyyyMMdd+9位"
        BigInteger student_id FK
        BigInteger product_id FK NULL
        String card_type
        Integer total_credits NULL
        Integer used_credits default 0
        DateTime valid_from NULL
        DateTime expire_at NULL
        ARRAY applicable_course_ids NULL
        String applicable_course_type_code NULL
        Integer max_weekly_usage NULL
        SmallInteger status "0=PENDING 1=ACTIVE 2=EXPIRED 3=FROZEN 6=CANCELLED"
        DateTime frozen_at NULL
        DateTime frozen_until NULL
        String frozen_reason NULL
        Integer frozen_remaining_days NULL
        BigInteger operator_id NULL
        DateTime cancelled_at NULL
        String cancelled_reason NULL
        DateTime created_at
        DateTime updated_at
    }

    membership_card_transactions {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        BigInteger card_id FK
        BigInteger booking_id FK NULL
        String operation_type "issue/consume/restore/recharge/refund/adjust/expire"
        Integer change_amount
        Integer balance_after
        BigInteger operator_id NULL
        String idempotency_key UK NULL
        String remark NULL
        DateTime created_at
        DateTime updated_at
    }

    membership_card_freezes {
        BigInteger id PK
        UUID public_id UK
        BigInteger tenant_id FK
        BigInteger card_id FK
        String reason
        DateTime frozen_at
        DateTime unfrozen_at NULL
        BigInteger operator_id NULL
        DateTime created_at
        DateTime updated_at
    }
```

### 枚举值汇总

#### BookingStatus（booking/models.py）
| 值 | 名称 | 含义 |
|----|------|------|
| 1 | BOOKED | 已预约 |
| 2 | CANCELLED | 已取消 |
| 3 | CHECKED_IN | 已签到 |
| 4 | COMPLETED | 已完成 |
| 5 | NO_SHOW | 未到场 |

#### ScheduleStatus（schedule/models.py）
| 值 | 名称 | 含义 |
|----|------|------|
| 1 | NORMAL | 正常 |
| 2 | CANCELLED | 已取消 |
| 3 | FINISHED | 已完成 |

#### CardStatus（membership/models.py）
| 值 | 名称 | 含义 |
|----|------|------|
| 0 | PENDING | 未激活 |
| 1 | ACTIVE | 正常 |
| 2 | EXPIRED | 已过期 |
| 3 | FROZEN | 已冻结 |
| 6 | CANCELLED | 已作废 |

#### UserStatus（user/models.py）
| 值 | 名称 | 含义 |
|----|------|------|
| 0 | DISABLED | 禁用 |
| 1 | ACTIVE | 激活 |

#### TenantStatus（tenant/models.py）
| 值 | 名称 | 含义 |
|----|------|------|
| 0 | DISABLED | 禁用 |
| 1 | ACTIVE | 激活 |

#### TransactionType（membership/models.py）
| 值 | 名称 |
|----|------|
| issue | 发放/开卡 |
| consume | 扣减课时 |
| restore | 恢复课时 |
| recharge | 充值 |
| refund | 退款 |
| adjust | 手动调整 |
| expire | 过期清零 |

#### BookingSource（booking/models.py）
| 值 | 含义 |
|----|------|
| self | 学员自己预约 |
| admin | 管理员代约 |
| teacher | 教师代约 |

#### GenderStatus（user/models.py）
| 值 | 含义 |
|----|------|
| 0 | UNKNOWN |
| 1 | MALE |
| 2 | FEMALE |

## Important Rules

### 唯一约束 & 检查约束

| 表 | 约束名 | 约束内容 |
|----|--------|----------|
| users | uq_users_tenant_phone | `(tenant_id, phone)` 唯一（WHERE deleted_at IS NULL）|
| users | uq_users_tenant_email | `(tenant_id, email)` 唯一（WHERE deleted_at IS NULL AND email IS NOT NULL）|
| users | uq_users_tenant_phone | `user_code` 单独唯一 |
| roles | uq_roles_tenant_code | `(COALESCE(tenant_id,0), code)` 唯一（支持全局角色 tenant_id IS NULL）|
| course_categories | uq_course_categories_tenant_code | `(tenant_id, code)` 唯一 |
| course_categories | uq_course_categories_tenant_name | `(tenant_id, name)` 唯一 |
| course_types | uq_course_types_tenant_code | `(tenant_id, code)` 唯一 |
| course_types | uq_course_types_tenant_name | `(tenant_id, name)` 唯一 |
| classrooms | uq_classrooms_tenant_name | `(tenant_id, name)` 唯一 |
| bookings | uq_bookings_schedule_student_active | `(schedule_id, student_id)` 唯一（WHERE status IN (1,3,4)）——防止重复预约 |
| course_schedules | chk_schedule_time | `end_at > start_at` |
| course_schedules | chk_schedule_capacity | `booked_count <= capacity AND booked_count >= 0` |
| membership_cards | chk_credits_range | `used_credits >= 0 AND (total_credits IS NULL OR used_credits <= total_credits)` |
| membership_cards | card_no | 唯一 |
| membership_card_transactions | idempotency_key | 唯一（WHERE idempotency_key IS NOT NULL）|
| wechat_accounts | uq_wechat_accounts_open_id_app_id | `(open_id, app_id)` 唯一 |

### 软删除

部分表使用 `deleted_at` 字段实现软删除：
- `users`
- `courses`
- `membership_card_products`

这些表在查询时通常需要加 `WHERE deleted_at IS NULL` 过滤。`tenant_query.py` 自动注入的是 `tenant_id` 条件，不处理 `deleted_at`。

### membership_card_id 关联

Bookings 表中有 `membership_card_id` 字段但没有外键约束（nullable，在 schema 里只记录为 BigInteger）。关联关系由 Service 层手动维护（booking/service.py 的 deduct_credit / restore_credit）。

### public_id（UUID）

几乎所有业务表都有 `public_id` 字段（PostgreSQL UUID 类型），用于对外暴露（避免用自增 ID 遍历）。

## Dependencies

### Alembic 迁移

| 项目 | 位置 |
|------|------|
| 配置文件 | apps/api/alembic.ini |
| 迁移目录 | apps/api/alembic/versions/ |
| env.py | apps/api/alembic/env.py |
| 模型发现 | apps/api/src/app/models.py（`Base.metadata`） |

迁移文件命名：部分用 hash 前缀（如 `4bd04b738098_init_all_tables.py`），部分用 snake_case（如 `add_wechat_accounts.py`），不统一。

当前 versions 目录下文件数量：28 个。最新一个带 hash 前缀的是 `835a06fcf236_add_frozen_remaining_days_to_membership_cards.py`。

### Database 配置（apps/api/src/app/core/config.py）

```python
DATABASE_URL: str = "postgresql+asyncpg://dance:dance_dev_pass@localhost:5432/dance_saas"
```

### Database Session（apps/api/src/app/core/database.py）

使用 SQLAlchemy async engine + `async_sessionmaker`：

```python
engine = create_async_engine(settings.DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

Session 生命周期：每个请求从 `get_session` 依赖注入获得一个 `AsyncSession`，请求结束后关闭。

### Repository 基类（apps/api/src/app/core/base_repository.py）

定义了通用 CRUD 方法（get_by_id, create, update, delete），但不是所有 Repository 都继承它。

## Common Failure Points

1. **tenant_query 自动注入的是 SQLAlchemy 事件**：只有通过 `Session.execute(select(...))` 执行的 ORM 查询才会被注入，原生 SQL（`session.execute(text("..."))`）不会被注入租户过滤
2. **booked_count 通过应用层增减**：`course_schedules.booked_count` 在 Service 层手动 increment/decrement（`ScheduleRepository.increment_booked_count`），而非数据库触发器。高并发下可能出现竞态（代码中有版本号乐观锁 TODO）
3. **membership_card_id 无外键**：Bookings 的 membership_card_id 是纯整数列，没有 FK 约束，可能导致数据不一致
4. **Alembic env.py 使用 sync session_factory**：如果 env.py 中 sync 的 session_factory 与 async 的 engine 有冲突，需要确认
5. **membership_card_transactions 的 balance_after**：存储的是当时的余额快照，需要业务逻辑保证其与 membership_cards 的 used_credits 一致
6. **UserRole 是复合主键表**：`(user_id, role_id)` 为 PK，但 Role.role_id 可以是全局角色（tenant_id IS NULL），查询时需额外过滤 OR 条件
7. **Role 表的 tenant_id 是 nullable**：全局角色如 super_admin 的 tenant_id 为 NULL，查询全局角色需要 `OR role.tenant_id IS NULL`

## TODO / Known Issues

- [ ] bookings.membership_card_id 未设置外键约束，建议添加
- [ ] bookings 模型使用 `public_id` 但 unique 约束使用了 PG_UUID(as_uuid=True)，需要确认 Alembic 迁移已正确生成 public_id 列
- [ ] 迁移文件命名风格不统一（hash 前缀 vs snake_case）
- [ ] 部分模型有 `deleted_at` 但查询层未统一加过滤（依赖 Service 层手动处理）
- [ ] Role.role_id 的 tenant_id nullable 设计：全局角色查询时 OR 条件容易遗漏，需统一封装
- [ ] public_id 的 UUID 默认值（`default=uuid4`）需要确认 Alembic 迁移后数据库是否正确生成 default（因为 PostgreSQL 端需要 uuid-ossp 扩展）
- [ ] `booked_count` 增减的原子性：当前实现应该是 `UPDATE course_schedules SET booked_count = booked_count + 1 WHERE id = ? AND booked_count < capacity`，需要确认是否正确处理了并发
