#!/bin/bash
set -e

BASE="http://localhost:8000/api/v1"
H="-H Content-Type: application/json -H x-tenant-slug: dance-school"

echo "=========================================="
echo "  全面功能测试"
echo "=========================================="

# Step 1: Login
echo ""
echo "=== Step 1: 登录认证 ==="
R=$(curl -s -X POST $BASE/auth/login $H -d '{"phone":"13800000001","password":"Test@123456","tenant_slug":"dance-school"}')
ADMIN_TOKEN=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
echo "✅ 管理员 13800000001 登录成功"

R=$(curl -s -X POST $BASE/auth/login $H -d '{"phone":"13800138001","password":"Test@123456","tenant_slug":"dance-school"}')
TEACHER_TOKEN=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
echo "✅ 教师 13800138001 登录成功"

R=$(curl -s -X POST $BASE/auth/login $H -d '{"phone":"13900139001","password":"Test@123456","tenant_slug":"dance-school"}')
STUDENT_TOKEN=$(echo "$R" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
echo "✅ 学员 13900139001 登录成功"

# Step 2: Course CRUD
echo ""
echo "=== Step 2: 课程管理 ==="
R=$(curl -s -X POST $BASE/courses $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"name":"街舞基础","description":"入门街舞课程","duration_minutes":60,"max_capacity":20,"price":199}')
echo "2.1 创建课程: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), d.get('msg'))")"

R=$(curl -s -X POST $BASE/courses $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"name":"Jazz高级","description":"Jazz进阶","duration_minutes":90,"max_capacity":15,"price":299}')
echo "2.2 创建课程2: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), d.get('msg'))")"

R=$(curl -s -X GET "$BASE/courses?page_size=10" $H -H "Authorization: Bearer $STUDENT_TOKEN")
echo "2.3 课程列表(学生): $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), 'total:', d.get('data',{}).get('total'))")"

R=$(curl -s -X GET "$BASE/courses/1" $H -H "Authorization: Bearer $STUDENT_TOKEN")
echo "2.4 课程详情(学生): $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), 'name:', d.get('data',{}).get('name'))")"

R=$(curl -s -X PATCH "$BASE/courses/1" $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"level":"入门","category":"街舞"}')
echo "2.5 更新课程: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), d.get('msg'))")"

# Step 3: Classroom CRUD
echo ""
echo "=== Step 3: 教室管理 ==="
R=$(curl -s -X POST $BASE/classrooms $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"name":"A教室","capacity":30,"location":"1楼","facilities":"音响,镜子"}')
echo "3.1 创建教室: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), d.get('msg'))")"

R=$(curl -s -X POST $BASE/classrooms $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"name":"B教室","capacity":20,"location":"2楼"}')
echo "3.2 创建教室2: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), d.get('msg'))")"

R=$(curl -s -X GET "$BASE/classrooms?page_size=10" $H -H "Authorization: Bearer $ADMIN_TOKEN")
echo "3.3 教室列表: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), 'total:', d.get('data',{}).get('total'))")"

# Step 4: User Management
echo ""
echo "=== Step 4: 用户管理 ==="
R=$(curl -s -X GET "$BASE/users?page_size=10" $H -H "Authorization: Bearer $ADMIN_TOKEN")
echo "4.1 用户列表(admin): $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('code'), 'total:', d.get('data',{}).get('total'))")"

R=$(curl -s -X GET "$BASE/users?page_size=10" $H -H "Authorization: Bearer $STUDENT_TOKEN")
echo "4.2 用户列表(学生越权): $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

# Step 5: Schedule Management
echo ""
echo "=== Step 5: 排期管理 ==="
R=$(curl -s -X POST $BASE/schedules $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"course_id":1,"teacher_id":2,"classroom_id":1,"start_at":"2026-07-20T10:00:00","end_at":"2026-07-20T11:00:00","capacity":20}')
echo "5.1 创建排期: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

R=$(curl -s -X POST $BASE/schedules $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"course_id":1,"teacher_id":2,"classroom_id":1,"start_at":"2026-07-21T10:00:00","end_at":"2026-07-21T11:00:00","capacity":20}')
echo "5.2 创建排期2: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

# 时间冲突测试
R=$(curl -s -X POST $BASE/schedules $H -H "Authorization: Bearer $ADMIN_TOKEN" -d '{"course_id":1,"teacher_id":2,"classroom_id":1,"start_at":"2026-07-20T10:30:00","end_at":"2026-07-20T11:30:00","capacity":20}')
echo "5.3 时间冲突检测: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

R=$(curl -s -X GET "$BASE/schedules?page_size=10" $H -H "Authorization: Bearer $STUDENT_TOKEN")
echo "5.4 排期列表(学生): $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'total:', d.get('data',{}).get('total'))")"

# Step 6: Booking
echo ""
echo "=== Step 6: 预约流程 ==="
R=$(curl -s -X POST $BASE/bookings $H -H "Authorization: Bearer $STUDENT_TOKEN" -d '{"schedule_id":1}')
echo "6.1 创建预约: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

# 重复预约
R=$(curl -s -X POST $BASE/bookings $H -H "Authorization: Bearer $STUDENT_TOKEN" -d '{"schedule_id":1}')
echo "6.2 重复预约检测: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

R=$(curl -s -X GET "$BASE/bookings?page_size=10" $H -H "Authorization: Bearer $STUDENT_TOKEN")
echo "6.3 我的预约(学生): $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'total:', d.get('data',{}).get('total'))")"

R=$(curl -s -X POST "$BASE/bookings/1/cancel?reason=临时有事" $H -H "Authorization: Bearer $STUDENT_TOKEN")
echo "6.4 取消预约: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

# Re-book
R=$(curl -s -X POST $BASE/bookings $H -H "Authorization: Bearer $STUDENT_TOKEN" -d '{"schedule_id":1}')
echo "6.5 重新预约: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

# Check-in
R=$(curl -s -X POST "$BASE/bookings/2/check-in" $H -H "Authorization: Bearer $TEACHER_TOKEN")
echo "6.6 签到(教师): $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'msg:', d.get('msg'))")"

# Step 7: Role/Permission
echo ""
echo "=== Step 7: 角色权限 ==="
R=$(curl -s -X GET "$BASE/roles?page_size=10" $H -H "Authorization: Bearer $ADMIN_TOKEN")
echo "7.1 角色列表: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'total:', d.get('data',{}).get('total'))")"

R=$(curl -s -X GET "$BASE/roles/1/permissions" $H -H "Authorization: Bearer $ADMIN_TOKEN")
echo "7.2 角色权限详情: $(echo $R | python3 -c "import sys,json; d=json.load(sys.stdin); print('code:', d.get('code'), 'items:', len(d.get('data',{}).get('items',[])))")"

echo ""
echo "=========================================="
echo "  测试完成"
echo "=========================================="