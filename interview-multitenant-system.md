# 🎯 Python 多租户系统架构面试题集

> **基于实战项目的深度面试准备指南**
> 
> 涵盖：多租户架构 | ASGI协议 | 中间件设计 | ContextVar | 协程原理 | Starlette框架

---

## 📋 目录

- [第一部分：基础概念篇（★☆☆）](#第一部分基础概念篇)
- [第二部分：架构设计篇（★★☆）](#第二部分架构设计篇)
- [第三部分：核心原理篇（★★★）](#第三部分核心原理篇)
- [第四部分：实战场景篇（★★★）](#第四部分实战场景篇)
- [第五部分：高级优化篇（★★★★）](#第五部分高级优化篇)
- [参考答案](#参考答案)

---

## 第一部分：基础概念篇

### Q1: 什么是多租户（Multi-Tenancy）？有哪几种实现方式？

**考察点**：多租户基本概念与分类

**参考方向**：
- 定义：多个租户共享同一套应用实例
- 三种主流方案：
  1. **独立数据库**（最高隔离，成本高）
  2. **共享数据库+独立Schema**（中等隔离）
  3. **共享数据库+共享Schema**（最低隔离，成本最低）✅ *你的项目采用*

**追问**：
- 你的项目为什么选择方案3？
- 如何权衡隔离性与成本？

---

### Q2: 什么是 ASGI 协议？它与 WSGI 有什么区别？

**考察点**：Python Web 框架演进史

**关键对比维度**：

| 维度 | WSGI (旧) | ASGI (新) |
|------|-----------|-----------|
| **同步/异步** | 同步阻塞 | 异步非阻塞 |
| **WebSocket** | ❌ 不支持 | ✅ 原生支持 |
| **性能模型** | 多线程 | 单线程+协程 |
| **代表框架** | Flask, Django | FastAPI, Starlette |
| **并发能力** | 数千 | 数万至十万 |

**核心差异**：
- WSGI: `def app(environ, start_response)` - 同步函数
- ASGI: `async def app(scope, receive, send)` - 异步协程

---

### Q3: ContextVar 是什么？它解决了什么问题？

**考察点**：异步编程中的数据隔离

**核心要点**：
- Python 3.7 引入的标准库
- 解决全局变量在并发环境下的数据污染问题
- 比 `threading.local()` 更现代、更强大

**使用场景（你的项目中）**：
```python
from contextvars import ContextVar

tenant_id = ContextVar("tenant_id", default=None)

# 设置
set_tenant_id(10)

# 读取
current_tenant = get_tenant_id()  # 只获取当前请求的值
```

**追问**：ContextVar 与 threading.local 的区别？

---

## 第二部分：架构设计篇

### Q4: 请画出你设计的多租户中间件的完整数据流图

**考察点**：系统架构能力

**期望答案应包含**：

```
用户请求 → Uvicorn → TenantASGIMiddleware → AuthMiddleware 
         → 路由匹配 → 业务逻辑 → SQLAlchemy自动注入 → 数据库查询
              ↓                              ↓
        提取x-tenant-id               自动添加WHERE tenant_id=?
        写入ContextVar                返回过滤后的数据
```

**关键组件**：
1. **TenantASGIMiddleware** - 入口守卫
2. **ContextVar** - 数据存储层
3. **do_orm_execute** - 自动注入层
4. **TenantMixin** - 模型定义层

---

### Q5: 为什么选择中间件来处理多租户，而不是依赖注入或装饰器？

**考察点**：架构决策能力

**中间件的优势**：

| 方案 | 全局性 | 易用性 | 安全性 | 可维护性 |
|------|--------|--------|--------|----------|
| **中间件** ✅ | ✅ 所有请求自动经过 | ✅ 业务代码零侵入 | ✅ 无法绕过 | ✅ 统一管理 |
| 依赖注入 | ❌ 需手动添加 | ⚠️ 每个接口都要写 | ❌ 容易遗漏 | ❌ 代码重复 |
| 装饰器 | ❌ 需逐个添加 | ⚠️ 需要记住加 | ❌ 可能忘记 | ⚠️ 中等 |

**核心原因**：
1. **请求早期阶段**：在路由匹配前执行
2. **全局拦截**：100%覆盖所有接口
3. **代码解耦**：业务逻辑与租户逻辑完全分离

---

### Q6: 你的多租户系统有几层安全防护机制？分别是什么？

**考察点**：安全意识与纵深防御思想

**标准答案（5层防御）**：

```
第1️⃣ 层：请求入口控制
├─ TenantASGIMiddleware 强制提取 x-tenant-id 或 x-tenant-slug
├─ 缺少则返回 400 错误
└─ 校验租户状态（禁用租户拒绝访问）

第2️⃣ 层：数据存储隔离  
├─ ContextVar 为每个请求提供独立存储空间
├─ 线程安全、协程安全
└─ 请求结束自动清理

第3️⃣ 层：查询层面保护
├─ SQLAlchemy do_orm_execute 事件监听
├─ 自动注入 WHERE tenant_id = :current_tenant_id
└─ 即使开发者忘记写也能保护

第4️⃣ 层：数据库约束
├─ tenant_id NOT NULL（不能为空）
├─ FOREIGN KEY → tenants.id（引用完整性）
└─ ON DELETE CASCADE（级联删除）

第5️⃣ 层：ORM 模型规范
├─ 所有业务表必须继承 TenantMixin
├─ 强制包含 tenant_id 字段
└─ 从模型层面保证一致性
```

**追问**：如果某一层失效了怎么办？
**答**：其他层仍能保护！这就是纵深防御的价值。

---

## 第三部分：核心原理篇

### Q7: 请解释 ASGI 的三个核心参数 scope、receive、send 分别是什么？

**考察点**：ASGI 协议细节掌握程度

**scope（作用域字典）**：
```python
scope = {
    'type': 'http',                    # 类型：'http' | 'websocket' | 'lifespan'
    'method': 'GET',                   # HTTP 方法
    'path': '/api/v1/users',           # 路径
    'query_string': b'',               # 查询字符串
    'headers': [                       # 请求头列表
        (b'host', b'localhost:8000'),
        (b'x-tenant-id', b'10'),       # 自定义头部
    ],
    # ... 更多字段
}
```
*用途：包含请求的所有元信息*

**receive（接收消息的异步可调用对象）**：
```python
message = await receive()
# HTTP请求体：
{
    'type': 'http.request',
    'body': b'{"name": "张三"}',
    'more_body': False
}
```
*用途：流式读取请求体（POST/PUT/PATCH）*

**send（发送消息的异步可调用对象）**：
```python
await send({
    'type': 'http.response.start',
    'status': 200,
    'headers': [[b'content-type', b'application/json']],
})
await send({
    'type': 'http.response.body',
    body: b'{"data": "success"}',
})
```
*用途：分块发送响应头和响应体*

---

### Q8: 中间件的 `__call__` 方法为什么会被自动调用？

**考察点**：Python 魔法方法 + ASGI 规范

**完整调用链**：

```python
# 1. 启动命令
uvicorn app.main:app --port 8000

# 2. main.py 中创建 FastAPI 应用
app = FastAPI()  # 这是一个 ASGI 应用

# 3. 注册中间件
app.add_middleware(TenantASGIMiddleware, session_factory=SessionLocal)
# 内部发生的事情：
# middleware_instance = TenantASGIMiddleware(app=self.app, ...)
# self.app = middleware_instance  # 替换原来的 app

# 4. Uvicorn 处理请求时
async def handle_request(scope, receive, send):
    await current_app(scope, receive, send)  # 调用 __call__
    
# 5. 因为 Python 的 __call__ 魔法方法
class TenantASGIMiddleware:
    async def __call__(self, scope, receive, send):
        # 这个方法会被自动调用！
        ...
```

**关键机制**：
1. **`__call__` 魔法方法**：让对象可以像函数一样被调用
2. **ASGI 规范要求**：应用必须是 callable 对象
3. **Uvicorn 的行为**：调用 `app()` 时触发 `__call__`

---

### Q9: ContextVar 的数据到底存储在哪里？如何实现隔离？

**考察点**：底层实现原理

**存储结构（简化版）**：

```python
class ContextVar:
    def __init__(self, name, default=None):
        self.name = name
        self.default = default
        self._storage = {}  # 核心存储！
        # {
        #   <context_identity_1>: value_1,
        #   <context_identity_2>: value_2,
        # }
    
    def get(self):
        current_context = _get_current_context()  # 获取当前上下文标识
        return self._storage.get(current_context, self.default)
    
    def set(self, value):
        current_context = _get_current_context()
        self._storage[current_context] = value
```

**隔离机制**：
- **Key**: 当前上下文的唯一标识符（协程ID或线程ID）
- **Value**: 开发者设置的值
- **不同上下文 → 不同Key → 不同Value** → **完美隔离**

**内存布局**：
```
进程内存空间
├── 主线程
│   └── EventLoop
│       ├── Task_A (协程1)
│       │   └── Context_1 {tenant_id: 10}
│       ├── Task_B (协程2)
│       │   └── Context_2 {tenant_id: 20}
│       └── Task_C (协程3)
│           └── Context_3 {tenant_id: 10}  ← 值相同但独立存储
```

---

### Q10: 协程（Coroutine）和线程（Thread）有什么本质区别？

**考察点：** 并发编程核心概念

**核心区别表**：

| 维度 | 线程 (Thread) | 协程 (Coroutine) |
|------|---------------|------------------|
| **创建者** | 操作系统内核 | 编程语言运行时 |
| **调度者** | OS调度器（抢占式） | 程序/事件循环（协作式） |
| **内存开销** | ~8MB (栈空间) | ~几KB (状态信息) |
| **切换成本** | 高（需保存寄存器、缓存等） | 极低（只需保存局部变量和位置） |
| **切换时机** | OS决定（时钟中断） | 程序员决定（await关键字） |
| **数量限制** | 几千个就会耗尽内存 | 可轻松创建百万个 |
| **安全性** | 需要锁机制防竞争 | 单线程执行，无竞争问题 |
| **适用场景** | CPU密集型任务 | **I/O密集型任务** ✅ |

**生活类比**：
- **线程** = 雇佣多个厨师（每个厨师需要工资、工位）
- **协程** = 一个超级厨师（利用等待时间处理多道菜）

**性能对比实验结果**：
```
创建10000个并发I/O任务：
- 线程方案：耗时 ~15-20秒，内存 ~80MB
- 协程方案：耗时 ~0.15-0.2秒，内存 ~50MB
- 速度提升：100倍！
- 内存节省：37%
```

---

### Q11: Starlette 是什么？它在你的项目中扮演什么角色？

**考察点：** 技术栈理解深度

**定义**：
> Starlette 是一个轻量级的 **ASGI 工具包/框架**，是 FastAPI 的底层引擎。

**定位类比**：
```
Starlette = 汽车引擎（核心动力系统）
FastAPI = 整辆汽车（加了方向盘、仪表盘、导航）
```

**你在用的 Starlette 组件**：

```python
# 1. 类型定义（你的中间件文件中）
from starlette.types import ASGIApp, Receive, Scope, Send

# 2. Request 对象
from starlette.requests import Request
request = Request(scope, receive=receive)

# 3. Response 对象
from starlette.responses import JSONResponse
response = JSONResponse({"code": 0, "msg": "success"})

# 4. 中间件基类（虽然你没继承，但遵循其接口）
from starlette.middleware.base import BaseHTTPMiddleware
```

**Starlette vs FastAPI 功能对比**：

| 功能 | Starlette | FastAPI |
|------|-----------|---------|
| 路由系统 | ✅ `@app.route()` | ✅ `@app.get/post()` |
| 请求/响应 | ✅ Request/Response | ✅ 继承扩展 |
| 中间件 | ✅ BaseHTTPMiddleware | ✅ 复用 |
| WebSocket | ✅ 原生支持 | ✅ 原生支持 |
| 数据验证 | ❌ 无 | ✅ Pydantic集成 |
| 自动文档 | ❌ 无 | ✅ Swagger UI |
| 依赖注入 | ❌ 简单版 | ✅ 强大的Depends |

**性能基准**（TechEmpower 2024）：
- Starlette: ~850,000 req/s
- FastAPI: ~780,000 req/s
- Django: ~45,000 req/s
- Flask: ~52,000 req/s

**结论**：接近 Go 框架的性能！

---

## 第四部分：实战场景篇

### Q12: 如果开发者忘记在查询中加 tenant_id 过滤条件，会发生什么？

**考察点：** 自动注入机制的必要性

**❌ 如果没有自动注入机制**：
```python
# 开发者写的危险代码
result = await db.execute(select(User).where(User.phone == "13800138000"))

# 实际执行的 SQL：
SELECT * FROM users WHERE phone = '13800138000'
# 😱 会返回所有租户的用户！数据泄露！

# 后果：
# 1. 租户A能看到租户B的数据
# 2. 违反数据隔离原则
# 3. 可能导致法律合规问题（GDPR等）
```

**✅ 有自动注入机制后**：
```python
# 开发者写的同样的代码
result = await db.execute(select(User).where(User.phone == "13800138000"))

# do_orm_execute 事件触发后实际执行的 SQL：
SELECT * FROM users 
WHERE phone = '13800138000' 
  AND users.tenant_id = $1  ← 自动注入！✅
[PARAMETER: $1 = 10]  # 当前租户ID

# 结果：
# 1. 只返回当前租户的数据 ✅
# 2. 即使开发者犯错也能保护 ✅
# 3. 最后的安全网 ✅
```

**追问**：这个自动注入是如何实现的？
**答**：通过 SQLAlchemy 的 `before_compile` / `do_orm_execute` 事件监听。

---

### Q13: 你的中间件支持哪些方式传递租户信息？各有什么优缺点？

**考察点：** API 设计的灵活性

**两种方式**：

#### **方式1：直接提供 tenant_id（数字）**
```bash
curl http://localhost:8000/api/v1/users \
  -H "x-tenant-id: 10"
```

| 优点 | 缺点 |
|------|------|
| ✅ 性能好（无需查库） | ❌ 不够友好（暴露内部ID） |
| ✅ 实现简单 | ❌ 前端需要知道ID |
| ✅ 延迟低（<0.01ms） | ❌ 可读性差 |

**适用场景**：前端已知租户ID的SPA应用

---

#### **方式2：通过 slug 查询（字符串）**
```bash
curl http://localhost:8000/api/v1/users \
  -H "x-tenant-slug: dance-school"
```

| 优点 | 缺点 |
|------|------|
| ✅ 用户友好（URL美观） | ⚠️ 需要一次DB查询 |
| ✅ 可读性强 | ⚠️ 性能有损耗（~5-10ms） |
| ✅ 语义清晰 | ⚠️ 需要额外错误处理 |

**适用场景**：多租户SaaS平台（用户通过域名/subdomain识别）

**优化建议**：
```python
# 可以添加 Redis 缓存
async def _get_tenant_by_slug(self, slug: str):
    # 1. 先查 Redis 缓存
    cached = await redis.get(f"tenant:slug:{slug}")
    if cached:
        return json.loads(cached)
    
    # 2. 缓存未命中，查数据库
    result = await query_database(slug)
    
    # 3. 写入缓存（TTL=1小时）
    await redis.setex(f"tenant:slug:{slug}", 3600, result)
    
    return result
# 优化后：延迟从 ~5-10ms 降低到 ~1ms
```

---

### Q14: 如何测试多租户隔离是否生效？

**考察点：** 测试思维与验证能力

**测试策略（你的项目中的 test_tenant_isolation.py）**：

```python
@pytest.mark.asyncio
class TestTenantIsolation:
    
    async def test_tenant_a_cannot_see_b_data(self):
        """A租户只能看到自己的数据"""
        set_tenant_id(1)
        
        result = await db.execute(select(User))  # 不手动加过滤
        
        for user in result.scalars().all():
            assert user.tenant_id == 1  # 必须全是租户1的
    
    async def test_different_tenants_get_different_data(self):
        """不同租户看到不同的数据集"""
        set_tenant_id(1)
        users_a = set(u.id for u in await query_users())
        
        set_tenant_id(2)
        users_b = set(u.id for u in await query_users())
        
        # 两个集合应该无交集
        assert len(users_a & users_b) == 0
    
    async def test_non_tenant_model_not_affected(self):
        """非租户模型不受影响"""
        set_tenant_id(1)
        
        # Permission 表没有 tenant_id 字段
        result = await db.execute(select(Permission))
        assert len(result.all()) >= 0  # 正常查询，不过滤
```

**手动测试方法**：
```bash
# 1. 使用租户A登录
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -H "x-tenant-id: 10" \
  -d '{"phone":"13800138000","password":"P@ssw0rd"}' \
  | jq -r '.data.access_token')

# 2. 用该Token查询用户（应该只返回租户10的用户）
curl http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-tenant-id: 10"

# 3. 尝试伪造租户ID（应该失败或返回空）
curl http://localhost:8000/api/v1/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "x-tenant-id: 99"  # 不属于该用户的租户
```

---

### Q15: 如果一个请求不需要租户信息（如健康检查），怎么处理？

**考察点：** 边界情况处理

**你的项目解决方案**：

```python
# 定义跳过路径白名单
SKIP_TENANT_PATHS = [
    "/docs",                      # Swagger 文档
    "/redoc",                     # ReDoc 文档
    "/openapi.json",              # OpenAPI 规范
    "/api/v1/common/health",      # 健康检查 ✅
    "/api/v1/auth/register",      # 注册接口 ✅
    "/api/v1/auth/login",         # 登录接口 ✅
]

# 中间件中检查
def _should_skip_tenant(self, path: str) -> bool:
    for skip_path in SKIP_TENANT_PATHS:
        if path.startswith(skip_path):
            return True  # 跳过租户验证
    return False
```

**设计原则**：
- **公开接口**：注册、登录、文档、健康检查 → 不需要认证
- **业务接口**：所有需要身份鉴权的接口 → 必须提供租户信息
- **白名单机制**：比黑名单更安全（默认拒绝）

**追问**：未来新增公开接口怎么办？
**答**：只需在 `SKIP_TENANT_PATHS` 列表中添加路径前缀即可。

---

## 第五部分：高级优化篇

### Q16: 如何优化 slug 查询的性能瓶颈？

**考察点：** 性能优化思维

**当前问题**：
```python
# 每次请求都要查询数据库
async def _get_tenant_by_slug(self, slug: str):
    async with self.session_factory() as session:
        result = await session.execute(
            select(Tenant.id, Tenant.status).where(Tenant.slug == slug)
        )
        return result.first()
# 问题：延迟 5-10ms，高并发时成为瓶颈
```

**优化方案（三级缓存）**：

```python
import asyncio
from functools import lru_cache

class OptimizedTenantMiddleware:
    def __init__(self, app, session_factory, redis_client):
        self.app = app
        self.session_factory = session_factory
        self.redis = redis_client
        
        # L1: 进程内缓存（最快，但单机）
        self._local_cache = {}
        self._cache_ttl = 300  # 5分钟
    
    async def _get_tenant_by_slug(self, slug: str):
        """三级缓存查询"""
        
        # L1: 进程内存缓存 (~0.001ms)
        if slug in self._local_cache:
            cached_data, timestamp = self._local_cache[slug]
            if time.time() - timestamp < self._cache_ttl:
                return cached_data
        
        # L2: Redis 分布式缓存 (~1ms)
        redis_key = f"tenant:slug:{slug}"
        cached = await self.redis.get(redis_key)
        if cached:
            data = json.loads(cached)
            self._local_cache[slug] = (data, time.time())  # 回填L1
            return data
        
        # L3: 数据库查询 (~5-10ms)
        async with self.session_factory() as session:
            result = await session.execute(
                select(Tenant).where(Tenant.slug == slug)
            )
            tenant = result.scalar_one_or_none()
            
            if tenant:
                data = (tenant.id, tenant.status)
                
                # 写入L2 (TTL=1小时)
                await self.redis.setex(
                    redis_key, 
                    3600, 
                    json.dumps(data)
                )
                
                # 写入L1
                self._local_cache[slug] = (data, time.time())
                
                return data
            
            return None
```

**性能提升**：
- 首次请求：~10ms (DB)
- 1小时内重复请求：~1ms (Redis)
- 5分钟内重复请求：~0.001ms (内存)
- **命中率 > 99% 时，平均延迟降低 100倍！**

---

### Q17: 如何处理跨租户的管理员操作？（如超级管理员查看所有租户数据）

**考察点：** 权限系统的灵活性

**挑战**：
```python
# 普通用户的查询（自动注入）
set_tenant_id(10)
result = db.execute(select(User))  # 只能看租户10的数据

# 但超级管理员可能需要：
# 1. 查看所有租户的统计信息
# 2. 处理跨租户的投诉
# 3. 批量操作多个租户
```

**解决方案：临时禁用自动注入**

```python
# 方案1：使用 contextlib.contextmanager
from contextlib import contextmanager

@contextmanager
def disable_tenant_filter():
    """临时禁用租户过滤"""
    token = tenant_id.set(None)  # 清除租户ID
    try:
        yield
    finally:
        tenant_id.reset(token)  # 恢复原值

# 使用示例
@router.get("/admin/stats")
async def get_all_stats(current_user: User = Depends(get_current_user)):
    # 权限检查
    if not is_super_admin(current_user):
        raise HTTPException(403, "无权限")
    
    # 临时禁用过滤
    with disable_tenant_filter():
        total_users = await db.execute(
            select(func.count(User.id))  # 查询所有租户
        )
    
    return {"total_users": total_users.scalar()}
```

**方案2：特殊标记**
```python
# 在 ContextVar 中增加标记
skip_tenant_filter: ContextVar[bool] = ContextVar("skip_tenant_filter", default=False)

# 中间件/自动注入逻辑中检查
if skip_tenant_filter.get():
    pass  # 跳过注入
else:
    # 正常注入...
```

**安全考虑**：
- 只有超级管理员才能使用此功能
- 操作日志记录（审计追踪）
- 定期审查跨租户操作

---

### Q18: 如何监控和调试多租户系统的问题？

**考察点：** 生产环境运维能力

**监控指标**：

```python
# 1. 日志增强
class TenantASGIMiddleware:
    async def __call__(self, scope, receive, send):
        request = Request(scope, receive)
        tenant_id = await self._extract_tenant(request)
        
        # 在日志中添加租户信息
        logger.info(
            f"[Tenant={tenant_id}] "
            f"[Method={request.method}] "
            f"[Path={request.url.path}]",
            extra={
                "tenant_id": tenant_id,
                "path": request.url.path,
                "method": request.method,
            }
        )

# 2. 性能指标收集
from time import perf_counter

start_time = perf_counter()
try:
    await self.app(scope, receive, send)
finally:
    duration_ms = (perf_counter() - start_time) * 1000
    metrics.record(
        metric_name="request_duration_ms",
        value=duration_ms,
        tags={"tenant_id": tenant_id, "path": request.url.path}
    )
```

**常见问题排查清单**：

| 问题现象 | 排查步骤 | 可能原因 |
|---------|----------|----------|
| **数据泄露** | 1. 检查 ContextVar 是否正确设置<br>2. 检查自动注入是否启用<br>3. 检查是否有原生SQL绕过 | - 中间件未生效<br>- before_compile 未注册<br>- 使用了 raw SQL |
| **性能下降** | 1. 查看 slug 查询延迟<br>2. 检查缓存命中率<br>3. 分析慢查询日志 | - DB查询过多<br>- 缓存失效<br>- 索引缺失 |
| **400错误频繁** | 1. 检查前端是否传了 x-tenant-id<br>2. 检查租户是否存在<br>3. 检查租户状态 | - 前端遗漏header<br>- 租户被禁用<br>- slug拼写错误 |

**调试工具**：
```python
# 开发模式：打印详细日志
if settings.DEBUG:
    logger.debug(f"""
    [Tenant Middleware Debug]
    - Path: {request.url.path}
    - Headers: {dict(request.headers)}
    - Extracted tenant_id: {tenant_id}
    - ContextVar after set: {get_tenant_id()}
    """)
```

---

## 参考答案速查表

### ⭐ 必背核心知识点

1. **三层防护体系**：入口控制(ContextVar) + 存储隔离 + 查询注入
2. **ASGI三大参数**：scope(元信息)、receive(接收消息)、send(发送响应)
3. **协程vs线程**：协程更轻量(~KB vs ~MB)，适合I/O密集型
4. **ContextVar存储**：内部字典 `{context_identity: value}`，按上下文隔离
5. **中间件调用链**：`add_middleware()` → 包装app → Uvicorn调用 `__call__()`

### 🔥 高频面试题 TOP 5

1. **Q5**: 为什么用中间件而非装饰器？→ 全局性、安全性、解耦
2. **Q9**: ContextVar数据存在哪里？→ 内部字典，key是上下文标识
3. **Q10**: 协程和线程区别？→ 创建者、开销、切换机制、适用场景
4. **Q12**: 忘记加过滤会怎样？→ 数据泄露！自动注入是最后防线
5. **Q16**: 如何优化性能？→ 三级缓存(L1内存/L2 Redis/L3 DB)

### 💡 加分回答技巧

- **画图说明**：数据流图、架构图、时序图
- **举实例**：结合你的项目代码说明
- **说权衡**：没有绝对好的方案，要讲清楚trade-off
- **提扩展**：主动提及可能的优化方向

---

## 📚 延伸学习资源

### 官方文档
- [PEP 563 -- Async Generators](https://www.python.org/dev/peps/pep-0563/)
- [ContextVars — Context Variables](https://docs.python.org/3/library/contextvars.html)
- [ASGI Specification](https://asgi.readthedocs.io/)
- [Starlette Documentation](https://www.starlette.io/)
- [FastAPI Advanced: Middleware](https://fastapi.tiangolo.com/advanced/middleware/)

### 推荐阅读
- 《Fluent Python》第18章：asyncio
- 《Python High Performance Programming》第5章：Concurrency
- [Real Python: A Curated List of Awesome Python](https://realpython.com/awesome-python-resources/)

### 开源项目参考
- [FastAPI](https://github.com/tiangolo/fastapi) - 学习中间件实现
- [Starlette](https://github.com/encode/starlette) - 理解ASGI最佳实践
- [SQLAlchemy](https://github.com/sqlalchemy/sqlalchemy) - 研究事件系统

---

## ✅ 面试自检清单

使用前请确认已掌握：

- [ ] 能手画多租户中间件数据流图
- [ ] 能解释 ASGI 三个参数的作用
- [ ] 能说出 ContextVar 的底层存储结构
- [ ] 能对比协程和线程的5个以上区别
- [ ] 能列举至少3种多租户实现方案的优劣
- [ ] 能描述至少2种性能优化策略
- [ ] 能写出完整的中间件代码骨架
- [ ] 能设计测试用例验证租户隔离

**祝你面试顺利！🎉**

---

*文档版本：v1.0*
*最后更新：2026-06-29*
*基于项目实战经验整理*