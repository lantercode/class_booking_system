export interface ScheduleItem {
  id: number
  courseId: number
  courseName: string
  date: string
  startTime: string
  endTime: string
  teacherName: string
  classroom: string
  capacity: number
  booked: number
  status: number
}

function generateDates(days: number): string[] {
  const dates: string[] = []
  const today = new Date()
  for (let i = 0; i < days; i++) {
    const d = new Date(today)
    d.setDate(d.getDate() + i)
    dates.push(d.toISOString().slice(0, 10))
  }
  return dates
}

const TIME_SLOTS = [
  { start: '09:00', end: '10:30' },
  { start: '10:30', end: '12:00' },
  { start: '14:00', end: '15:30' },
  { start: '15:30', end: '17:00' },
  { start: '18:30', end: '20:00' },
  { start: '20:00', end: '21:30' },
]

const TEACHERS = ['张老师', '李老师', '王老师', '赵老师']
const CLASSROOMS = ['A101', 'A102', 'B201', 'C301']

export function generateSchedules(courseId: number, courseName: string): ScheduleItem[] {
  const schedules: ScheduleItem[] = []
  const dates = generateDates(30)
  let id = 1

  for (let i = 0; i < dates.length; i++) {
    const dayOfWeek = new Date(dates[i]).getDay()
    if (dayOfWeek === 0) continue // 周日休息

    // 每天随机 1-2 个时段
    const slotCount = Math.random() > 0.3 ? 2 : 1
    const shuffledSlots = [...TIME_SLOTS].sort(() => Math.random() - 0.5)

    for (let j = 0; j < slotCount; j++) {
      const slot = shuffledSlots[j]
      const capacity = 15 + Math.floor(Math.random() * 10)
      const booked = Math.floor(Math.random() * capacity)

      schedules.push({
        id: id++,
        courseId,
        courseName,
        date: dates[i],
        startTime: slot.start,
        endTime: slot.end,
        teacherName: TEACHERS[Math.floor(Math.random() * TEACHERS.length)],
        classroom: CLASSROOMS[Math.floor(Math.random() * CLASSROOMS.length)],
        capacity,
        booked,
        status: booked >= capacity ? 0 : 1,
      })
    }
  }

  return schedules
}

export function getSchedulesByDate(
  schedules: ScheduleItem[],
  date: string
): ScheduleItem[] {
  return schedules.filter((s) => s.date === date)
}

export function getScheduleById(
  schedules: ScheduleItem[],
  id: number
): ScheduleItem | undefined {
  return schedules.find((s) => s.id === id)
}