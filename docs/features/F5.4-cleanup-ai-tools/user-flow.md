# F5.4 — User Flow

本 Feature 为纯代码清理，**无用户交互流程变化**。

## 对用户/调用方的影响

| 角色 | 影响 |
|------|------|
| 学员（小程序 AI 助手） | 无感知，预约/取消/查询行为完全不变（走 mcp_server 生效路径） |
| 教师/管理员 | 无感知 |
| AI 运行时 | import 路径不变，runtime.py 仍从 `app.ai.mcp_server` 导入 6 个 Tool |
| 开发者 | 代码库中只剩一套 Tool 实现，不再有"改哪个文件才生效"的歧义 |

## 调用链（删除前后一致）

```
POST /api/v1/ai/chat
  → modules/ai/router.py（get_current_user 注入身份）
  → AgentRuntime（runtime.py）
  → app.ai.mcp_server 的 Tool 函数（唯一注册点）
  → BookingService / CourseService / ScheduleService / MembershipCardService
  → Repository → DB
```

`ai/tools/` 从未出现在这条链路中，故删除对运行时行为零影响。
