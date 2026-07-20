export interface StudentItem {
  id: number
  nickname: string
  avatar: string
  phone: string
  status: 'confirmed' | 'attended' | 'cancelled'
  bookedAt: string
}

export function generateStudents(scheduleId: number): StudentItem[] {
  const names = ['张同学', '李同学', '王同学', '刘同学', '陈同学', '杨同学', '赵同学', '黄同学', '周同学', '吴同学']
  const students: StudentItem[] = []
  const count = Math.floor(Math.random() * 8) + 2

  for (let i = 0; i < count; i++) {
    students.push({
      id: i + 1,
      nickname: names[i] || `学员${i + 1}`,
      avatar: `https://picsum.photos/seed/stu${scheduleId}${i}/80/80`,
      phone: `138****${String(i + 1).padStart(4, '0')}`,
      status: i < count - 2 ? 'confirmed' : 'attended',
      bookedAt: '2026-07-0' + (i + 1),
    })
  }
  return students
}
