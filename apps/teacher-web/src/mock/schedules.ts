export interface ScheduleItem {
  id: number
  courseId: number
  courseName: string
  date: string
  startTime: string
  endTime: string
  status: number
  bookedCount: number
  capacity: number
}

export function generateSchedules(courseId: number, courseName: string): ScheduleItem[] {
  const schedules: ScheduleItem[] = []
  const today = new Date()
  const times = ['09:00', '10:30', '14:00', '15:30', '17:00']

  for (let d = 0; d < 14; d++) {
    const date = new Date(today)
    date.setDate(date.getDate() + d)
    if (date.getDay() === 0 || date.getDay() === 6) continue // skip weekends
    const dateStr = date.toISOString().split('T')[0]

    times.forEach((startTime, i) => {
      const [h, m] = startTime.split(':').map(Number)
      const endH = h + 1
      const endTime = `${String(endH).padStart(2, '0')}:${String(m).padStart(2, '0')}`
      schedules.push({
        id: schedules.length + 1,
        courseId,
        courseName,
        date: dateStr,
        startTime,
        endTime,
        status: d < 10 ? 1 : 0,
        bookedCount: Math.floor(Math.random() * 15),
        capacity: 15,
      })
    })
  }
  return schedules
}

export const mockAllSchedules: ScheduleItem[] = [
  ...generateSchedules(1, '古典舞基础'),
  ...generateSchedules(2, '街舞进阶'),
  ...generateSchedules(3, '芭蕾形体'),
]
