export interface CourseTeacher {
  id: number
  name: string
  avatar: string
  intro: string
}

export interface CourseItem {
  id: number
  name: string
  cover: string
  description: string
  teacher: CourseTeacher
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  duration: number
  price: number
  capacity: number
  status: number
  classroom: string
  tags: string[]
}

const DIFFICULTY_MAP: Record<string, string> = {
  beginner: '入门',
  intermediate: '中级',
  advanced: '高级',
}

export const mockCourses: CourseItem[] = [
  {
    id: 1,
    name: '古典舞基础',
    cover: 'https://picsum.photos/seed/dance1/400/240',
    description:
      '本课程专为零基础学员设计，从古典舞基本手位、脚位开始，逐步学习经典组合。通过系统训练提升身体柔韧性和表现力，感受中国传统舞蹈的优雅魅力。',
    teacher: {
      id: 1,
      name: '张老师',
      avatar: 'https://picsum.photos/seed/teacher1/100/100',
      intro: '北京舞蹈学院毕业，10年教学经验，擅长古典舞和民族舞。',
    },
    difficulty: 'beginner',
    duration: 90,
    price: 120,
    capacity: 20,
    status: 1,
    classroom: 'A101 舞蹈教室',
    tags: ['古典舞', '零基础', '成人'],
  },
  {
    id: 2,
    name: '街舞进阶',
    cover: 'https://picsum.photos/seed/dance2/400/240',
    description:
      '针对有基础的学员，学习 Hip-Hop、Popping、Locking 等街舞风格的高阶动作和编舞技巧。课程节奏快、强度大，适合想要挑战自我的舞者。',
    teacher: {
      id: 2,
      name: '李老师',
      avatar: 'https://picsum.photos/seed/teacher2/100/100',
      intro: '全国街舞大赛冠军，签约艺人编舞师，5年成人街舞教学经验。',
    },
    difficulty: 'advanced',
    duration: 60,
    price: 150,
    capacity: 15,
    status: 1,
    classroom: 'B201 街舞教室',
    tags: ['街舞', 'Hip-Hop', '进阶'],
  },
  {
    id: 3,
    name: '芭蕾形体',
    cover: 'https://picsum.photos/seed/dance3/400/240',
    description:
      '融合芭蕾基本功和形体训练，改善体态、提升气质。课程包含把杆练习、地面练习和简单舞段，适合所有想要塑造优美体型的学员。',
    teacher: {
      id: 3,
      name: '王老师',
      avatar: 'https://picsum.photos/seed/teacher3/100/100',
      intro: '上海戏剧学院芭蕾专业，曾任职于上海芭蕾舞团，8年教学经验。',
    },
    difficulty: 'intermediate',
    duration: 90,
    price: 130,
    capacity: 18,
    status: 1,
    classroom: 'A102 舞蹈教室',
    tags: ['芭蕾', '形体', '塑形'],
  },
  {
    id: 4,
    name: '拉丁舞初级',
    cover: 'https://picsum.photos/seed/dance4/400/240',
    description:
      '学习伦巴、恰恰、桑巴等拉丁舞基本步伐和双人配合技巧。课程氛围轻松愉快，适合情侣或单人报名，零基础也能快速上手。',
    teacher: {
      id: 4,
      name: '赵老师',
      avatar: 'https://picsum.photos/seed/teacher4/100/100',
      intro: '国际标准舞国家级教师，多次获得全国拉丁舞比赛冠军，教学风格幽默风趣。',
    },
    difficulty: 'beginner',
    duration: 60,
    price: 100,
    capacity: 24,
    status: 1,
    classroom: 'C301 多功能教室',
    tags: ['拉丁舞', '双人舞', '零基础'],
  },
  {
    id: 5,
    name: '现代舞创作',
    cover: 'https://picsum.photos/seed/dance5/400/240',
    description:
      '探索现代舞的自由表达，学习地面技巧、即兴创作和编舞方法。课程鼓励学员发挥创造力，用身体表达情感，适合有舞蹈基础的学员。',
    teacher: {
      id: 5,
      name: '陈老师',
      avatar: 'https://picsum.photos/seed/teacher5/100/100',
      intro: '中央民族大学舞蹈编导硕士，独立舞者，作品曾入选国内外舞蹈节。',
    },
    difficulty: 'advanced',
    duration: 120,
    price: 180,
    capacity: 12,
    status: 0,
    classroom: 'A103 排练厅',
    tags: ['现代舞', '创作', '编舞'],
  },
  {
    id: 6,
    name: '少儿中国舞',
    cover: 'https://picsum.photos/seed/dance6/400/240',
    description:
      '专为 6-12 岁少儿设计的中国舞课程，融合基本功训练、舞蹈组合和考级内容。培养孩子的身体协调性和艺术感知力。',
    teacher: {
      id: 6,
      name: '刘老师',
      avatar: 'https://picsum.photos/seed/teacher6/100/100',
      intro: '中国舞蹈家协会注册教师，10年少儿舞蹈教学经验，耐心细致。',
    },
    difficulty: 'beginner',
    duration: 60,
    price: 80,
    capacity: 20,
    status: 1,
    classroom: 'A104 少儿教室',
    tags: ['少儿', '中国舞', '考级'],
  },
]

export function getCourseById(id: number): CourseItem | undefined {
  return mockCourses.find((c) => c.id === id)
}

export function getDifficultyLabel(difficulty: string): string {
  return DIFFICULTY_MAP[difficulty] || difficulty
}

export function getDifficultyType(difficulty: string): 'success' | 'warning' | 'danger' {
  if (difficulty === 'beginner') return 'success'
  if (difficulty === 'intermediate') return 'warning'
  return 'danger'
}