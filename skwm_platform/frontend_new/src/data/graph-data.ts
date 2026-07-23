export interface GraphNode {
  id: string; label_zh: string; label_en: string; label_ar: string
  type: string; degree: number; group: string
}
export interface GraphLink { source: string; target: string; relation: string }

const types = ['文献','作者','机构','主题','地点','政策','项目','事件','术语']

export const graphNodes: GraphNode[] = [
  { id: 'n1', label_zh: '文化遗产旅游', label_en: 'Cultural Heritage Tourism', label_ar: 'سياحة التراث الثقافي', type: '主题', degree: 8, group: '主题' },
  { id: 'n2', label_zh: '阿拉伯国家旅游传播', label_en: 'Arab Tourism Communication', label_ar: 'الاتصال السياحي العربي', type: '主题', degree: 6, group: '主题' },
  { id: 'n3', label_zh: '北京第二外国语学院', label_en: 'Beijing International Studies University', label_ar: 'جامعة بكين للدراسات الدولية', type: '机构', degree: 7, group: '机构' },
  { id: 'n4', label_zh: '中阿文旅知识图谱', label_en: 'Sino-Arab Cultural Tourism KG', label_ar: 'المعرفة السياحية الثقافية الصينية العربية', type: '主题', degree: 5, group: '主题' },
  { id: 'n5', label_zh: 'GraphRAG', label_en: 'GraphRAG', label_ar: 'غراف آر إيه جي', type: '术语', degree: 6, group: '术语' },
  { id: 'n6', label_zh: '非物质文化遗产', label_en: 'Intangible Cultural Heritage', label_ar: 'التراث الثقافي غير المادي', type: '主题', degree: 4, group: '主题' },
  { id: 'n7', label_zh: '一带一路', label_en: 'Belt and Road Initiative', label_ar: 'مبادرة الحزام والطريق', type: '政策', degree: 5, group: '政策' },
  { id: 'n8', label_zh: '中阿合作论坛', label_en: 'China-Arab Cooperation Forum', label_ar: 'منتدى التعاون الصيني العربي', type: '政策', degree: 3, group: '政策' },
  { id: 'n9', label_zh: '沙特阿拉伯', label_en: 'Saudi Arabia', label_ar: 'المملكة العربية السعودية', type: '地点', degree: 4, group: '地点' },
  { id: 'n10', label_zh: '阿联酋', label_en: 'United Arab Emirates', label_ar: 'الإمارات العربية المتحدة', type: '地点', degree: 3, group: '地点' },
  { id: 'n11', label_zh: '图书馆学科服务', label_en: 'Library Subject Services', label_ar: 'خدمات المكتبات الموضوعية', type: '主题', degree: 5, group: '主题' },
  { id: 'n12', label_zh: '大语言模型', label_en: 'Large Language Model', label_ar: 'نموذج اللغة الكبير', type: '术语', degree: 4, group: '术语' },
  { id: 'n13', label_zh: '科学计量学', label_en: 'Scientometrics', label_ar: 'القياسات العلمية', type: '术语', degree: 3, group: '术语' },
  { id: 'n14', label_zh: '阿拉伯语自然语言处理', label_en: 'Arabic NLP', label_ar: 'معالجة اللغة العربية الطبيعية', type: '术语', degree: 3, group: '术语' },
  { id: 'n15', label_zh: '数字文旅', label_en: 'Digital Cultural Tourism', label_ar: 'السياحة الثقافية الرقمية', type: '主题', degree: 4, group: '主题' },
  { id: 'n16', label_zh: '中国', label_en: 'China', label_ar: 'الصين', type: '地点', degree: 5, group: '地点' },
  { id: 'n17', label_zh: '埃及', label_en: 'Egypt', label_ar: 'مصر', type: '地点', degree: 2, group: '地点' },
  { id: 'n18', label_zh: '跨文化传播', label_en: 'Cross-cultural Communication', label_ar: 'التواصل بين الثقافات', type: '主题', degree: 3, group: '主题' },
  { id: 'n19', label_zh: '张教授', label_en: 'Prof. Zhang', label_ar: 'البروفيسور تشانغ', type: '作者', degree: 3, group: '作者' },
  { id: 'n20', label_zh: '李教授', label_en: 'Prof. Li', label_ar: 'البروفيسور لي', type: '作者', degree: 2, group: '作者' },
  { id: 'n21', label_zh: '中阿文明交流', label_en: 'Sino-Arab Civilization Exchange', label_ar: 'التبادل الحضاري الصيني العربي', type: '项目', degree: 3, group: '项目' },
  { id: 'n22', label_zh: '世界模型理论', label_en: 'World Model Theory', label_ar: 'نظرية النموذج العالمي', type: '文献', degree: 4, group: '文献' },
  { id: 'n23', label_zh: '2024文旅融合研讨会', label_en: '2024 Culture-Tourism Symposium', label_ar: 'ندوة دمج الثقافة والسياحة 2024', type: '事件', degree: 2, group: '事件' },
  { id: 'n24', label_zh: '知识蒸馏', label_en: 'Knowledge Distillation', label_ar: 'تقطير المعرفة', type: '术语', degree: 2, group: '术语' },
  { id: 'n25', label_zh: '智能问答系统', label_en: 'Intelligent QA System', label_ar: 'نظام الإجابة الذكي', type: '主题', degree: 3, group: '主题' },
]

export const graphLinks: GraphLink[] = [
  { source: 'n1', target: 'n2', relation: '共现' }, { source: 'n1', target: 'n3', relation: '隶属' },
  { source: 'n1', target: 'n4', relation: '对应' }, { source: 'n1', target: 'n6', relation: '共现' },
  { source: 'n2', target: 'n3', relation: '合作' }, { source: 'n2', target: 'n9', relation: '对应' },
  { source: 'n2', target: 'n10', relation: '对应' }, { source: 'n3', target: 'n19', relation: '隶属' },
  { source: 'n3', target: 'n20', relation: '隶属' }, { source: 'n4', target: 'n5', relation: '对应' },
  { source: 'n4', target: 'n11', relation: '影响' }, { source: 'n4', target: 'n15', relation: '共现' },
  { source: 'n5', target: 'n12', relation: '引用' }, { source: 'n5', target: 'n22', relation: '引用' },
  { source: 'n6', target: 'n15', relation: '演化' }, { source: 'n7', target: 'n8', relation: '共现' },
  { source: 'n7', target: 'n16', relation: '对应' }, { source: 'n7', target: 'n21', relation: '影响' },
  { source: 'n8', target: 'n21', relation: '隶属' }, { source: 'n9', target: 'n16', relation: '合作' },
  { source: 'n10', target: 'n16', relation: '合作' }, { source: 'n11', target: 'n22', relation: '影响' },
  { source: 'n12', target: 'n24', relation: '引用' }, { source: 'n13', target: 'n4', relation: '引用' },
  { source: 'n14', target: 'n2', relation: '对应' }, { source: 'n15', target: 'n18', relation: '共现' },
  { source: 'n18', target: 'n21', relation: '影响' }, { source: 'n19', target: 'n20', relation: '合作' },
  { source: 'n22', target: 'n5', relation: '引用' }, { source: 'n23', target: 'n1', relation: '共现' },
  { source: 'n23', target: 'n15', relation: '共现' }, { source: 'n25', target: 'n5', relation: '引用' },
  { source: 'n25', target: 'n11', relation: '对应' },
]

export const typeColors: Record<string, string> = {
  '文献': '#e0e7ff', '作者': '#ccfbf1', '机构': '#fef3c7', '主题': '#dbeafe',
  '地点': '#d1fae5', '政策': '#fce7f3', '项目': '#ede9fe', '事件': '#fff7ed', '术语': '#f5f5f4',
}
