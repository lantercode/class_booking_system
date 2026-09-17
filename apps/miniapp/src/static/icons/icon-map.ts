// 图标SVG内容映射
// 这些SVG内容来自阿里图标库下载的SVG文件
// 使用 currentColor 作为 stroke 颜色，通过 CSS 控制

export const iconSvgMap: Record<string, string> = {
  crown: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 3L4 8L6 17H18L20 8L12 3Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M6 17H18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  calendar: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M16 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M8 14H8.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M12 14H12.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M16 14H16.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M8 18H8.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M12 18H12.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  card: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="5" width="20" height="14" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M2 10H22" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M6 15H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  wechat: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8.5 11C9.32843 11 10 10.3284 10 9.5C10 8.67157 9.32843 8 8.5 8C7.67157 8 7 8.67157 7 9.5C7 10.3284 7.67157 11 8.5 11Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15.5 11C16.3284 11 17 10.3284 17 9.5C17 8.67157 16.3284 8 15.5 8C14.6716 8 14 8.67157 14 9.5C14 10.3284 14.6716 11 15.5 11Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 13C5.68629 13 3 15.2386 3 18C3 18.5523 3.44772 19 4 19H14C14.5523 19 15 18.5523 15 18C15 15.2386 12.3137 13 9 13Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M15 13C17.2091 13 19 14.7909 19 17C19 17.3682 18.9467 17.7246 18.847 18.0623" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  logout: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V5C3 4.46957 3.21071 3.96086 3.58579 3.58579C3.96086 3.21071 4.46957 3 5 3H9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><polyline points="16 17 21 12 16 7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><line x1="21" y1="12" x2="9" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  edit: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M18.5 2.50001C18.8978 2.10219 19.4374 1.87869 20 1.87869C20.5626 1.87869 21.1022 2.10219 21.5 2.50001C21.8978 2.89784 22.1213 3.4374 22.1213 4.00001C22.1213 4.56262 21.8978 5.10219 21.5 5.50001L12 15L8 16L9 12L18.5 2.50001Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  "arrow-right": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M9 18L15 12L9 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  user: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20 21V19C20 17.9391 19.5786 16.9217 18.8284 16.1716C18.0783 15.4214 17.0609 15 16 15H8C6.93913 15 5.92172 15.4214 5.17157 16.1716C4.42143 16.9217 4 17.9391 4 19V21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="7" r="4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  phone: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="5" y="2" width="14" height="20" rx="2" ry="2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><line x1="12" y1="18" x2="12.01" y2="18" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  camera: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M23 19C23 19.5304 22.7893 20.0391 22.4142 20.4142C22.0391 20.7893 21.5304 21 21 21H3C2.46957 21 1.96086 20.7893 1.58579 20.4142C1.21071 20.0391 1 19.5304 1 19V8C1 7.46957 1.21071 6.96086 1.58579 6.58579C1.96086 6.21071 2.46957 6 3 6H7L9 3H15L17 6H21C21.5304 6 22.0391 6.21071 22.4142 6.58579C22.7893 6.96086 23 7.46957 23 8V19Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="13" r="4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  "tab-course": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M22 10V6C22 4.89543 21.1046 4 20 4H4C2.89543 4 2 4.89543 2 6V10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M2 10V18C2 19.1046 2.89543 20 4 20H20C21.1046 20 22 19.1046 22 18V10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 4V20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  "tab-schedule": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M16 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="currentColor" stroke-width="1.5"/><path d="M8 14H8.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M12 14H12.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M16 14H16.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M8 18H8.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M12 18H12.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,

  "tab-profile": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="8" r="4" stroke="currentColor" stroke-width="1.5"/><path d="M20 21C20 17.134 16.4183 14 12 14C7.58172 14 4 17.134 4 21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  "tab-home": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M3 9L12 2L21 9V20C21 20.5304 20.7893 21.0391 20.4142 21.4142C20.0391 21.7893 19.5304 22 19 22H5C4.46957 22 3.96086 21.7893 3.58579 21.4142C3.21071 21.0391 3 20.5304 3 20V9Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M9 22V12H15V22" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  "tab-booking": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M16 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="currentColor" stroke-width="1.5"/><path d="M8 14H8.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M12 14H12.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M16 14H16.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M8 18H8.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M12 18H12.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`,

  "ai-robot": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="4" y="8" width="16" height="12" rx="3" stroke="currentColor" stroke-width="1.5"/><circle cx="9" cy="14" r="1.5" fill="currentColor"/><circle cx="15" cy="14" r="1.5" fill="currentColor"/><path d="M12 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="2" r="1" fill="currentColor"/><path d="M2 14H4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M20 14H22" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M9 18H15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  location: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C8.13 2 5 5.13 5 9C5 14.25 12 22 12 22C12 22 19 14.25 19 9C19 5.13 15.87 2 12 2Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="12" cy="9" r="2.5" stroke="currentColor" stroke-width="1.5"/></svg>`,

  people: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="9" cy="7" r="3" stroke="currentColor" stroke-width="1.5"/><path d="M3 21V19C3 16.7909 4.79086 15 7 15H11C13.2091 15 15 16.7909 15 19V21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="17" cy="7" r="2.5" stroke="currentColor" stroke-width="1.5"/><path d="M21 21V19.5C21 17.567 19.433 16 17.5 16H16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  "card-valid": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="5" width="20" height="14" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M2 10H22" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M6 15H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M18 15L20 13L18 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  "card-invalid": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="2" y="5" width="20" height="14" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M2 10H22" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M6 15H10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M4 4L20 20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  tag: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20.59 13.41L13.42 20.58C13.05 20.95 12.55 21.16 12.02 21.16H4C3.47 21.16 2.96 20.95 2.59 20.58C2.22 20.21 2.01 19.71 2.01 19.18V11.15C2.01 10.62 2.22 10.12 2.59 9.75L9.76 2.58C10.13 2.21 10.63 2 11.16 2H19.19C19.72 2 20.22 2.21 20.59 2.58C20.96 2.95 21.17 3.45 21.17 3.98V12.01C21.17 12.54 20.96 13.04 20.59 13.41Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><circle cx="7.5" cy="7.5" r="1.5" fill="currentColor"/></svg>`,

  "calendar-check": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><rect x="3" y="4" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M16 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M8 2V6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M3 10H21" stroke="currentColor" stroke-width="1.5"/><path d="M9 16L11 18L15 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  heart: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M20.84 4.61C20.33 4.1 19.72 3.7 19.05 3.43C18.38 3.16 17.66 3.02 16.94 3.02C16.22 3.02 15.5 3.16 14.83 3.43C14.16 3.7 13.55 4.1 13.04 4.61L12 5.65L10.96 4.61C9.93 3.58 8.53 3 7.07 3C5.61 3 4.21 3.58 3.18 4.61C2.15 5.64 1.57 7.04 1.57 8.5C1.57 9.96 2.15 11.36 3.18 12.39L4.22 13.43L12 21.21L19.78 13.43L20.82 12.39C21.33 11.88 21.73 11.27 22 10.6C22.27 9.93 22.41 9.21 22.41 8.49C22.41 7.77 22.27 7.05 22 6.38C21.73 5.71 21.33 5.1 20.84 4.61Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  "calendar-dancer": `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M12 8C12 8 10 10 10 12C10 14 12 16 12 16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M12 8C12 8 14 10 14 12C14 14 12 16 12 16" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="6" r="1.5" fill="currentColor"/><path d="M10 16L8 20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M14 16L16 20" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M10 10L7 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><path d="M14 10L17 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>`,

  clock: `<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M12 7V12L15 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`,

  "empty-schedule": `<svg viewBox="0 0 280 220" fill="none" xmlns="http://www.w3.org/2000/svg">
    <!-- 底座 -->
    <ellipse cx="140" cy="195" rx="100" ry="18" fill="#f0e6d6" opacity="0.6"/>
    <ellipse cx="140" cy="192" rx="80" ry="12" fill="#e8dcc8" opacity="0.4"/>
    
    <!-- 左侧叶子 -->
    <path d="M45 160C30 145 25 120 35 100C40 90 50 85 55 90C45 105 48 130 60 150C65 158 55 165 45 160Z" fill="#e8d5b7" opacity="0.5"/>
    <path d="M35 140C25 130 22 115 30 100C33 95 40 92 43 96C36 108 38 125 48 140C52 146 44 150 35 140Z" fill="#d4b896" opacity="0.3"/>
    
    <!-- 右侧叶子 -->
    <path d="M235 160C250 145 255 120 245 100C240 90 230 85 225 90C235 105 232 130 220 150C215 158 225 165 235 160Z" fill="#e8d5b7" opacity="0.5"/>
    <path d="M245 140C255 130 258 115 250 100C247 95 240 92 237 96C244 108 242 125 232 140C228 146 236 150 245 140Z" fill="#d4b896" opacity="0.3"/>
    
    <!-- 日历主体 -->
    <rect x="85" y="55" width="110" height="130" rx="8" fill="#fff" stroke="#e8dcc8" stroke-width="2"/>
    <rect x="85" y="55" width="110" height="35" rx="8" fill="#f5ede3"/>
    <rect x="85" y="82" width="110" height="8" fill="#f5ede3"/>
    
    <!-- 日历环扣 -->
    <rect x="105" y="42" width="12" height="22" rx="6" fill="#c9a66b" opacity="0.6"/>
    <rect x="134" y="42" width="12" height="22" rx="6" fill="#c9a66b" opacity="0.6"/>
    <rect x="163" y="42" width="12" height="22" rx="6" fill="#c9a66b" opacity="0.6"/>
    
    <!-- 舞者剪影 -->
    <g transform="translate(140, 120)">
      <!-- 头部 -->
      <circle cx="0" cy="-28" r="8" fill="#c9a66b" opacity="0.7"/>
      <!-- 身体 -->
      <path d="M0 -20C-2 -10 -3 0 0 10" stroke="#c9a66b" stroke-width="2.5" stroke-linecap="round" fill="none" opacity="0.7"/>
      <!-- 左臂 -->
      <path d="M0 -15C-12 -20 -25 -18 -30 -10" stroke="#c9a66b" stroke-width="2" stroke-linecap="round" fill="none" opacity="0.7"/>
      <!-- 右臂 -->
      <path d="M0 -15C12 -25 22 -30 25 -35" stroke="#c9a66b" stroke-width="2" stroke-linecap="round" fill="none" opacity="0.7"/>
      <!-- 左腿 -->
      <path d="M0 10C-8 20 -15 35 -12 45" stroke="#c9a66b" stroke-width="2" stroke-linecap="round" fill="none" opacity="0.7"/>
      <!-- 右腿 -->
      <path d="M0 10C5 18 8 28 5 38" stroke="#c9a66b" stroke-width="2" stroke-linecap="round" fill="none" opacity="0.7"/>
      <!-- 裙摆 -->
      <path d="M-8 5C-12 15 -10 25 0 28C10 25 12 15 8 5" fill="#c9a66b" opacity="0.15"/>
    </g>
    
    <!-- 装饰丝带 -->
    <path d="M85 175C100 185 120 190 140 188C160 186 180 180 195 175" stroke="#e8d5b7" stroke-width="3" stroke-linecap="round" fill="none" opacity="0.5"/>
    
    <!-- 闪光星星 -->
    <path d="M65 65L67 70L72 72L67 74L65 79L63 74L58 72L63 70Z" fill="#c9a66b" opacity="0.6"/>
    <path d="M215 85L217 89L221 91L217 93L215 97L213 93L209 91L213 89Z" fill="#c9a66b" opacity="0.5"/>
    <path d="M75 100L76 103L79 104L76 105L75 108L74 105L71 104L74 103Z" fill="#c9a66b" opacity="0.4"/>
  </svg>`,
};

export type IconName = keyof typeof iconSvgMap;
