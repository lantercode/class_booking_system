export interface TeacherCourse {
  id: number
  name: string
  cover: string
  description: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  duration: number
  price: number
  capacity: number
  status: number
  classroom: string
  tags: string[]
  studentCount: number
  scheduleCount: number
  createdAt: string
}

export function getDifficultyLabel(d: string) {
  const map: Record<string, string> = { beginner: '入门', intermediate: '中级', advanced: '高级' }
  return map[d] || d
}

export const mockTeacherCourses: TeacherCourse[] = [
  {
    id: 1,
    name: '古典舞基础',
    cover: 'https://picsum.photos/seed/tc1/400/240',
    description: '专为零基础学员设计，从基本站姿、手位开始，逐步掌握古典舞核心技巧。',
    difficulty: 'beginner',
    duration: 60,
    price: 120,
    capacity: 15,
    status: 1,
    classroom: '舞蹈教室A',
    tags: ['古典舞', '零基础', '热门'],
    studentCount: 12,
    scheduleCount: 8,
    createdAt: '2026-06-01',
  },
  {
    id: 2,
    name: '街舞进阶',
    cover: 'https://picsum.photos/seed/tc2/400/240',
    description: '适合有一定舞蹈基础的学员，学习Popping、Locking等街舞风格。',
    difficulty: 'advanced',
    duration: 90,
    price: 150,
    capacity: 20,
    status: 1,
    classroom: '舞蹈教室B',
    tags: ['街舞', '进阶', '潮流'],
    studentCount: 8,
    scheduleCount: 5,
    createdAt: '2026-06-05',
  },
  {
    id: 3,
    name: '芭蕾形体',
    cover: 'https://picsum.photos/seed/tc3/400/240',
    description: '改善体态、提升气质，适合所有想要塑造优雅身形的学员。',
    difficulty: 'intermediate',
    duration: 75,
    price: 130,
    capacity: 12,
    status: 1,
    classroom: '舞蹈教室A',
    tags: ['芭蕾', '形体', '优雅'],
    studentCount: 15,
    scheduleCount: 10,
    createdAt: '2026-06-10',
  },
  {
    id: 4,
    name: '拉丁舞初级',
    cover: 'https://picsum.photos/seed/tc4/400/240',
    description: '从恰恰、伦巴的基本步伐开始，感受拉丁舞的热情与魅力。',
    difficulty: 'beginner',
    duration: 60,
    price: 100,
    capacity: 18,
    status: 0,
    classroom: '舞蹈教室C',
    tags: ['拉丁', '初级', '热情'],
    studentCount: 0,
    scheduleCount: 0,
    createdAt: '2026-06-15',
  },
  {
    id: 5,
    name: '现代舞创作',
    cover: 'https://picsum.photos/seed/tc5/400/240',
    description: '探索身体表达的可能性，学习即兴和编舞技巧。',
    difficulty: 'advanced',
    duration: 120,
    price: 180,
    capacity: 10,
    status: 1,
    classroom: '舞蹈教室B',
    tags: ['现代舞', '创作', '高级'],
    studentCount: 5,
    scheduleCount: 3,
    createdAt: '2026-06-20',
  },
]
