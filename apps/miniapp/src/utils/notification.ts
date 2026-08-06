interface Notification {
  id: string
  title: string
  content: string
  type: 'booking' | 'system' | 'reminder'
  read: boolean
  created_at: string
}

const STORAGE_KEY = 'dance_notifications'

function getAll(): Notification[] {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveAll(list: Notification[]) {
  uni.setStorageSync(STORAGE_KEY, JSON.stringify(list))
}

export function getNotifications(): Notification[] {
  return getAll().sort((a, b) => {
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
}

export function getUnreadCount(): number {
  return getAll().filter(n => !n.read).length
}

export function addNotification(notification: Omit<Notification, 'id' | 'read' | 'created_at'>) {
  const list = getAll()
  list.unshift({
    ...notification,
    id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
    read: false,
    created_at: new Date().toISOString()
  })
  if (list.length > 100) {
    list.splice(100)
  }
  saveAll(list)
}

export function markAsRead(id: string) {
  const list = getAll()
  const item = list.find(n => n.id === id)
  if (item) {
    item.read = true
    saveAll(list)
  }
}

export function markAllAsRead() {
  const list = getAll()
  list.forEach(n => { n.read = true })
  saveAll(list)
}

export function clearNotifications() {
  saveAll([])
}

export function removeNotification(id: string) {
  const list = getAll()
  saveAll(list.filter(n => n.id !== id))
}
