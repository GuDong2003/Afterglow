/** @type {import('tailwindcss').Config} */
// 时光信笺主题
// - 明色：米色信笺 + 黛蓝墨痕
// - 暗色：深墨绿背景 + 柔白文字（避开纯黑）
export default {
  content: ['./index.html', './src/**/*.{vue,ts,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        paper: '#F5F1E4',        // 信笺底色
        'paper-soft': '#FBF7E9', // 更浅的信笺色（聊天区背景）
        'paper-shade': '#EBE3CD',// 略深的信笺（用户气泡）
        ink: '#1A2F4B',          // 黛蓝主文字
        'ink-soft': '#4A5D7A',   // 辅助文字
        accent: '#8B5A2B',       // 暖棕（强调 / 链接 / 波纹图标）
        'accent-soft': '#C49A6C',// 浅一些的暖棕（次要强调）
        warning: '#B85C38',
        night: {
          bg: '#101820',         // 暗色主背景（深墨绿）
          'bg-soft': '#172530',  // 略亮一些
          'bubble-user': '#1E2C3A',
          text: '#E6EAEF',
          'text-soft': '#9CA6B3',
          accent: '#D9B58A',
          'accent-soft': '#A88762',
        },
      },
      fontFamily: {
        serif: [
          '"Noto Serif SC"',
          '"Source Han Serif SC"',
          '"思源宋体"',
          '"宋体"',
          'STSong',
          'serif',
        ],
        sans: [
          '"Inter"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          'system-ui',
          'sans-serif',
        ],
      },
      fontSize: {
        // 微信级别的舒适字号
        chat: ['1.0625rem', { lineHeight: '1.7' }],
        'chat-lg': ['1.125rem', { lineHeight: '1.75' }],
      },
      boxShadow: {
        letter: '0 1px 2px rgba(26,47,75,0.04), 0 8px 24px rgba(26,47,75,0.06)',
        'letter-strong': '0 2px 6px rgba(26,47,75,0.08), 0 16px 40px rgba(26,47,75,0.1)',
      },
      borderRadius: {
        bubble: '1.25rem',
      },
      keyframes: {
        breathe: {
          '0%, 100%': { opacity: '0.4' },
          '50%': { opacity: '1' },
        },
        'fade-up': {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.6' },
          '50%': { transform: 'scale(1.08)', opacity: '1' },
        },
      },
      animation: {
        breathe: 'breathe 3.4s ease-in-out infinite',
        'fade-up': 'fade-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards',
        'pulse-soft': 'pulse-soft 2.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
