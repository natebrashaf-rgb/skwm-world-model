export interface DataSource {
  name: string; language: string; count: number; updated: string
}
export const dataSources: DataSource[] = [
  { name: '中文文献', language: '中文', count: 6284, updated: '2026-07' },
  { name: '阿文文献', language: '阿拉伯语', count: 4193, updated: '2026-07' },
  { name: '英文文献', language: '英语', count: 5001, updated: '2026-07' },
  { name: '政策文本', language: '中/阿/英', count: 156, updated: '2026-06' },
  { name: '馆藏书目', language: '中文', count: 892, updated: '2026-05' },
  { name: '新闻会议', language: '中/阿/英', count: 423, updated: '2026-07' },
  { name: '文旅项目', language: '中文', count: 215, updated: '2026-04' },
  { name: '服务日志', language: '中文', count: 1204, updated: '2026-07' },
]
