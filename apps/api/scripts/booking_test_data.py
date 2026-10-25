"""预约管理页面测试数据构造脚本（F6.10 / interaction-spec P-A5）

通过 HTTP API 构造预约管理列表所需的全部演示场景：
  1. 已预约           —— 学员用有效卡预约未来排期（可演示：代取消 / 点名-代签到）
  2. 已取消           —— 管理员代取消（验证课时回补）
  3. 已签到           —— 点名页代签到（脚本内连续两次签到，演示重复签到拦截）
  4. 已完成           —— 已签到后完成（验证扣次流水）
  5. 卡失效警示(D3)   —— 先预约、后作废卡，列表出现红底失效行
  6. 未到场           —— 无手动端点：排期结束 + 调度器宽限后自动收口（脚本输出等待说明）

前置条件：
  - 后端已启动（默认 http://localhost:8000），已执行 seed.py：
      管理员 13800000001 / 教师 13800138001 / 学员 13900139001，密码均为 Test@123456
  - 租户 slug：dance-school
  - 存在至少 1 门课程、1 名学员、1 名教师（seed 已含）

用法：
  python3 scripts/booking_test_data.py                 # 全流程构造
  python3 scripts/booking_test_data.py --base-url http://localhost:8000
  python3 scripts/booking_test_data.py --keep-schedules 3   # 额外多建 N 个空排期备用
"""

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "http://localhost:8000"
TENANT = "dance-school"
ADMIN_PHONE, TEACHER_PHONE, STUDENT_PHONE = "13800000001", "13800138001", "13900139001"
PASSWORD = "Test@123456"


def call(method: str, path: str, token: str | None = None, body: dict | None = None,
         query: dict | None = None) -> dict:
    """调用后端 API，返回信封中的 data；业务失败抛 RuntimeError。"""
    url = f"{BASE}/api/v1{path}"
    if query:
        from urllib.parse import urlencode
        url += "?" + urlencode(query)
    req = urllib.request.Request(url, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("x-tenant-slug", TENANT)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data=data, timeout=15) as resp:
            envelope = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            envelope = json.loads(e.read().decode())
        except Exception:
            raise RuntimeError(f"{method} {path} -> HTTP {e.code}") from e
    if envelope.get("code") != 0:
        detail = (envelope.get("msg") or envelope.get("message") or envelope.get("detail")
                  or json.dumps(envelope, ensure_ascii=False)[:300])
        raise RuntimeError(f"{method} {path} -> 业务错误: {detail}")
    return envelope.get("data") or {}


def login(phone: str) -> str:
    data = call("POST", "/auth/login", body={"tenant_slug": TENANT, "phone": phone, "password": PASSWORD})
    print(f"  ✓ 登录 {phone}")
    return data["access_token"]


def _me(phone: str) -> dict:
    """登录并返回该账号的身份信息（id/nickname）。"""
    return call("GET", "/auth/me", login(phone))


def pick(items: list, label: str, phone: str | None = None) -> dict:
    """优先按 seed 手机号精确匹配（环境列表首位可能是脏数据），否则取第一个。"""
    if phone:
        for it in items:
            if it.get("phone") == phone:
                return it
    if not items:
        raise RuntimeError(f"没有可用的{label}，请先运行 seed.py / 录入基础数据")
    return items[0]


def main() -> None:
    global BASE
    parser = argparse.ArgumentParser(description="预约管理测试数据构造")
    parser.add_argument("--base-url", default=BASE)
    parser.add_argument("--keep-schedules", type=int, default=0, help="额外创建的空排期数量")
    parser.add_argument("--credits", type=int, default=10, help="次卡总次数")
    args = parser.parse_args()
    BASE = args.base_url.rstrip("/")

    print("== 1. 登录三端账号 ==")
    admin = login(ADMIN_PHONE)
    login(TEACHER_PHONE)  # 教师端可用于点名页签到/完成的人工验证
    student = login(STUDENT_PHONE)

    print("== 2. 读取基础数据 ==")
    courses = call("GET", "/courses", admin, query={"page": 1, "page_size": 50})["items"]
    course = pick(courses, "课程")
    # 教师/学员 id 从各自 token 的 /auth/me 获取（users 列表手机号可能脱敏，且发卡/排期均按 user_id 归属）
    t_me = _me(TEACHER_PHONE)
    s_me = _me(STUDENT_PHONE)
    teacher_id, teacher_name = t_me["id"], t_me.get("nickname", "")
    stu_id, stu_name = s_me["id"], s_me.get("nickname", "")
    print(f"  ✓ 课程={course['name']}({course['id']}) 教师={teacher_name}({teacher_id}) 学员={stu_name}({stu_id})")

    print("== 3. 创建未来排期 S1/S2/S3 ==")
    now = datetime.now(timezone.utc) + timedelta(days=1)
    schedule_ids = {}
    for key, offset in (("S1", 0), ("S2", 1), ("S3", 2)):
        start = (now + timedelta(days=offset)).replace(hour=11, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=90)
        data = call("POST", "/schedules/", admin, body={
            "course_id": course["id"], "teacher_id": teacher_id,
            "start_at": start.isoformat(), "end_at": end.isoformat(), "capacity": 10,
        })
        schedule_ids[key] = data["id"] if isinstance(data, dict) and "id" in data else data.get("schedule_id")
        print(f"  ✓ {key}: schedule_id={schedule_ids[key]} ({start:%Y-%m-%d %H:%M} 本地时间需自行核对时区)")
    for i in range(args.keep_schedules):
        start = (now + timedelta(days=10 + i)).replace(hour=11, minute=0, second=0, microsecond=0)
        data = call("POST", "/schedules/", admin, body={
            "course_id": course["id"], "teacher_id": teacher_id,
            "start_at": start.isoformat(), "end_at": (start + timedelta(minutes=90)).isoformat(),
            "capacity": 10,
        })
        print(f"  ✓ 备用排期: {data.get('id')}")

    print("== 4. 发放两张次卡（卡A=主流程，卡B=作废演示）==")
    card_a = call("POST", "/membership/cards", admin, body={
        "student_id": stu_id, "total_credits": args.credits, "validity_days": 365,
        "allow_duplicate": True, "remark": "预约管理测试卡A",
    })
    card_b = call("POST", "/membership/cards", admin, body={
        "student_id": stu_id, "total_credits": args.credits, "validity_days": 365,
        "allow_duplicate": True, "remark": "预约管理测试卡B(稍后作废)",
    })
    card_a_id, card_b_id = card_a["id"], card_b["id"]
    print(f"  ✓ 卡A id={card_a_id} 卡号={card_a.get('card_no')}；卡B id={card_b_id} 卡号={card_b.get('card_no')}")

    print("== 5. 卡A 预约 S1 → 代取消（场景：已取消 + 课时回补）==")
    b1 = call("POST", "/bookings/", student, body={"schedule_id": schedule_ids["S1"], "membership_card_id": card_a_id})
    call("POST", f"/bookings/{b1['id']}/admin-cancel", admin, query={"reason": "脚本演示：管理员代取消"})
    print(f"  ✓ booking id={b1['id']} 已代取消（管理页应显示「已取消」+ 取消原因，卡流水出现回补 +1）")

    print("== 6. 卡A 再约 S1 → 代签到 → 重复签到拦截 → 完成（场景：已签到/已完成）==")
    b2 = call("POST", "/bookings/", student, body={"schedule_id": schedule_ids["S1"], "membership_card_id": card_a_id})
    call("POST", f"/bookings/{b2['id']}/check-in", admin)
    print(f"  ✓ booking id={b2['id']} 已签到")
    try:
        call("POST", f"/bookings/{b2['id']}/check-in", admin)
        print("  ⚠ 第二次签到未被拦截？请检查重复签到校验（预期业务错误）")
    except RuntimeError as e:
        print(f"  ✓ 重复签到被拦截（预期行为）: {e}")
    call("POST", f"/bookings/{b2['id']}/complete", admin)
    print(f"  ✓ booking id={b2['id']} 已完成（管理页显示「已完成」，卡流水出现扣次 -1）")

    print("== 7. 卡A 预约 S2 保留「已预约」（场景：代取消/点名-代签到入口演示）==")
    b3 = call("POST", "/bookings/", student, body={"schedule_id": schedule_ids["S2"], "membership_card_id": card_a_id})
    print(f"  ✓ booking id={b3['id']} 状态=已预约（可在点名页演示代签到）")

    print("== 8. 卡B 预约 S3 后作废（场景：D3 失效警示 / D9 签到拦截）==")
    b4 = call("POST", "/bookings/", student, body={"schedule_id": schedule_ids["S3"], "membership_card_id": card_b_id})
    call("POST", f"/membership/cards/{card_b_id}/cancel", admin, body={"reason": "脚本演示：构造失效卡的有效预约"})
    print(f"  ✓ booking id={b4['id']} 仍为「已预约」，但卡B已作废")
    print("    → 管理页该行红底 + 卡tag「已作废」(D3)；进点名页代签到，确认弹窗出现卡异常警示 (D9)")

    print("== 9. 未到场（无手动端点，自动收口）==")
    print("  · S1/S3 排期结束且超过 AUTO_FINISH_GRACE_MINUTES 宽限后，")
    print("    调度器自动收口：未签到的「已预约」→「未到场」(booking/service.finalize_schedule_bookings)")
    print("  · 如需观察：保留 b3/b4 不动，等待排期过期后用状态筛选「未到场」验证")

    print("\n== 构造完成，管理端预约管理页验证清单 ==")
    print(f"  已预约(可代取消/点名) booking={b3['id']}  已取消 booking={b1['id']}")
    print(f"  已签到→已完成 booking={b2['id']}  失效卡有效预约(D3/D9) booking={b4['id']}")
    print("  筛选：状态=全部/已预约/已取消/已签到/已完成/未到场；keyword=学员/课程/排期关键词")
    print("  点名页：/bookings/roll-call?schedule_id=<排期ID> 或从列表「点名」进入")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        print(f"\n✗ 失败: {e}", file=sys.stderr)
        print("  排查：后端是否启动？seed 是否执行？前置数据是否齐全？", file=sys.stderr)
        sys.exit(1)
