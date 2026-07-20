export const mockUsers = Array.from({ length: 25 }, (_, i) => ({
  id: i + 1,
  phone: `1380000${String(i).padStart(4, '0')}`,
  nickname: `用户${i + 1}`,
  status: i % 5 === 0 ? 'disabled' : 'active',
  roles: i === 0 ? ['超级管理员'] : i < 5 ? ['管理员'] : i < 15 ? ['教师'] : ['学员'],
  createdAt: `2026-0${(i % 6) + 1}-${String((i % 28) + 1).padStart(2, '0')}`,
}))

export const mockRoles = [
  { id: 1, name: '超级管理员', code: 'super_admin', userCount: 1, permissions: ['全部权限'] },
  { id: 2, name: '管理员', code: 'admin', userCount: 4, permissions: ['用户管理', '课程管理', '排期管理', '教室管理', '机构设置'] },
  { id: 3, name: '教师', code: 'teacher', userCount: 10, permissions: ['课程管理', '排期管理', '学员查看'] },
  { id: 4, name: '学员', code: 'student', userCount: 10, permissions: ['课程浏览', '预约管理'] },
]

export const mockPermissions = [
  { id: 1, name: '用户管理', code: 'user:manage', children: [
    { id: 11, name: '查看用户', code: 'user:read' },
    { id: 12, name: '创建用户', code: 'user:create' },
    { id: 13, name: '编辑用户', code: 'user:update' },
    { id: 14, name: '删除用户', code: 'user:delete' },
  ]},
  { id: 2, name: '课程管理', code: 'course:manage', children: [
    { id: 21, name: '查看课程', code: 'course:read' },
    { id: 22, name: '创建课程', code: 'course:create' },
    { id: 23, name: '编辑课程', code: 'course:update' },
    { id: 24, name: '删除课程', code: 'course:delete' },
  ]},
  { id: 3, name: '排期管理', code: 'schedule:manage', children: [
    { id: 31, name: '查看排期', code: 'schedule:read' },
    { id: 32, name: '创建排期', code: 'schedule:create' },
    { id: 33, name: '取消排期', code: 'schedule:cancel' },
  ]},
  { id: 4, name: '预约管理', code: 'booking:manage', children: [
    { id: 41, name: '查看预约', code: 'booking:read' },
    { id: 42, name: '学员签到', code: 'booking:checkin' },
  ]},
  { id: 5, name: '教室管理', code: 'classroom:manage', children: [
    { id: 51, name: '查看教室', code: 'classroom:read' },
    { id: 52, name: '管理教室', code: 'classroom:write' },
  ]},
  { id: 6, name: '机构设置', code: 'tenant:manage', children: [
    { id: 61, name: '查看设置', code: 'tenant:read' },
    { id: 62, name: '编辑设置', code: 'tenant:write' },
  ]},
]

export const mockTeachers = Array.from({ length: 12 }, (_, i) => ({
  id: i + 1,
  name: `舞蹈老师${i + 1}`,
  phone: `1390000${String(i).padStart(4, '0')}`,
  speciality: ['中国舞', '芭蕾', '拉丁', '街舞', '爵士', '现代舞'][i % 6],
  status: i < 10 ? 'active' : 'disabled',
  courseCount: Math.floor(Math.random() * 5) + 1,
  studentCount: Math.floor(Math.random() * 80) + 20,
  rating: (4 + Math.random()).toFixed(1),
  joinedAt: `2025-0${(i % 9) + 1}-${String((i % 28) + 1).padStart(2, '0')}`,
}))

export const mockStudents = Array.from({ length: 30 }, (_, i) => ({
  id: i + 1,
  name: `学员${i + 1}`,
  phone: `1370000${String(i).padStart(4, '0')}`,
  status: i % 7 === 0 ? 'disabled' : 'active',
  bookingCount: Math.floor(Math.random() * 20) + 1,
  cardType: ['月卡', '季卡', '年卡', '次卡'][i % 4],
  cardExpire: `2026-${String((i % 12) + 1).padStart(2, '0')}-${String((i % 28) + 1).padStart(2, '0')}`,
  joinedAt: `2025-${String((i % 12) + 1).padStart(2, '0')}-${String((i % 28) + 1).padStart(2, '0')}`,
}))

export const mockCourses = Array.from({ length: 15 }, (_, i) => ({
  id: i + 1,
  name: ['中国舞基础', '芭蕾形体', '拉丁风情', '街舞入门', '爵士舞', '现代舞', '瑜伽', '民族舞', '古典舞', '肚皮舞', '韩舞', '国标舞', '霹雳舞', '健身操', '太极'][i],
  teacher: `舞蹈老师${(i % 5) + 1}`,
  difficulty: ['入门', '初级', '中级', '高级'][i % 4],
  duration: [45, 60, 90][i % 3],
  price: [80, 120, 150, 200][i % 4],
  status: i < 12 ? 'active' : 'disabled',
  studentCount: Math.floor(Math.random() * 30) + 5,
  scheduleCount: Math.floor(Math.random() * 8) + 1,
}))

export const mockSchedules = Array.from({ length: 20 }, (_, i) => ({
  id: i + 1,
  courseName: ['中国舞基础', '芭蕾形体', '拉丁风情', '街舞入门'][i % 4],
  teacher: `舞蹈老师${(i % 4) + 1}`,
  classroom: `${['A', 'B', 'C'][i % 3]}教室`,
  date: `2026-07-${String((i % 31) + 1).padStart(2, '0')}`,
  startTime: ['09:00', '10:30', '14:00', '16:00', '19:00'][i % 5],
  endTime: ['10:00', '11:30', '15:00', '17:00', '20:00'][i % 5],
  maxStudents: [10, 15, 20][i % 3],
  bookedCount: Math.floor(Math.random() * 15),
  status: i < 15 ? 'active' : 'cancelled',
}))

export const mockClassrooms = [
  { id: 1, name: 'A教室', capacity: 20, floor: 1, area: '80㎡', status: 'active', equipment: '把杆、镜子、音响' },
  { id: 2, name: 'B教室', capacity: 15, floor: 2, area: '60㎡', status: 'active', equipment: '把杆、镜子' },
  { id: 3, name: 'C教室', capacity: 30, floor: 1, area: '120㎡', status: 'active', equipment: '把杆、镜子、音响、投影' },
  { id: 4, name: 'D教室', capacity: 10, floor: 3, area: '40㎡', status: 'maintenance', equipment: '把杆、镜子' },
  { id: 5, name: 'E教室', capacity: 25, floor: 2, area: '90㎡', status: 'active', equipment: '把杆、镜子、音响、灯光' },
]