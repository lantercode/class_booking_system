export type BookingStatus = 'confirmed' | 'completed' | 'cancelled'

export interface BookingItem {
  id: number
  courseId: number
  courseName: string
  cover: string
  date: string
  startTime: string
  endTime: string
  teacherName: string
  classroom: string
  status: BookingStatus
  statusLabel: string
  createdAt: string
}

const STATUS_MAP: Record<BookingStatus, string> = {
  confirmed: '已预约',
  completed: '已完成',
  cancelled: '已取消',
}

export const mockBookings: BookingItem[] = [
  {
    id: 1,
    courseId: 1,
    courseName: '古典舞基础',
    cover: 'https://picsum.photos/seed/dance1/400/240',
    date: '2026-07-12',
    startTime: '10:30',
    endTime: '12:00',
    teacherName: '张老师',
    classroom: 'A101 舞蹈教室',
    status: 'confirmed',
    statusLabel: '已预约',
    createdAt: '2026-07-06 14:30',
  },
  {
    id: 2,
    courseId: 2,
    courseName: '街舞进阶',
    cover: 'https://picsum.photos/seed/dance2/400/240',
    date: '2026-07-15',
    startTime: '18:30',
    endTime: '20:00',
    teacherName: '李老师',
    classroom: 'B201 街舞教室',
    status: 'confirmed',
    statusLabel: '已预约',
    createdAt: '2026-07-06 15:00',
  },
  {
    id: 3,
    courseId: 3,
    courseName: '芭蕾形体',
    cover: 'https://picsum.photos/seed/dance3/400/240',
    date: '2026-07-05',
    startTime: '09:00',
    endTime: '10:30',
    teacherName: '王老师',
    classroom: 'A102 舞蹈教室',
    status: 'completed',
    statusLabel: '已完成',
    createdAt: '2026-07-03 10:00',
  },
  {
    id: 4,
    courseId: 4,
    courseName: '拉丁舞初级',
    cover: 'https://picsum.photos/seed/dance4/400/240',
    date: '2026-07-04',
    startTime: '14:00',
    endTime: '15:30',
    teacherName: '赵老师',
    classroom: 'C301 多功能教室',
    status: 'cancelled',
    statusLabel: '已取消',
    createdAt: '2026-07-02 09:00',
  },
]

export function getStatusTagType(status: BookingStatus): 'success' | 'info' | 'danger' {
  if (status === 'confirmed') return 'success'
  if (status === 'completed') return 'info'
  return 'danger'
}

export function getStatusLabel(status: BookingStatus): string {
  return STATUS_MAP[status]
}