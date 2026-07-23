export interface SkwmDimension {
  letter: string; nameZh: string; nameEn: string; definition: string; elements: string[]
}
export const skwmDimensions: SkwmDimension[] = [
  { letter: 'E', nameZh: '知识实体', nameEn: 'Entity', definition: '文献、作者、机构、主题、地点、政策、项目、事件、术语',
    elements: ['文献','作者','机构','主题','地点','政策','项目','事件','术语'] },
  { letter: 'R', nameZh: '知识关系', nameEn: 'Relation', definition: '引用、合作、共现、对应、影响、演化、隶属',
    elements: ['引用','合作','共现','对应','影响','演化','隶属'] },
  { letter: 'S', nameZh: '知识状态', nameEn: 'State', definition: '主题热度、合作强度、前沿程度、语言分布、传播范围',
    elements: ['主题热度','合作强度','前沿程度','语言分布','传播范围'] },
  { letter: 'T', nameZh: '时间序列', nameEn: 'Time', definition: '年度演化、阶段变化、突现主题',
    elements: ['年度演化','阶段变化','突现主题'] },
  { letter: 'C', nameZh: '语境变量', nameEn: 'Context', definition: '国家政策、区域合作、学科方向、国际形势',
    elements: ['国家政策','区域合作','学科方向','国际形势'] },
  { letter: 'U', nameZh: '用户需求', nameEn: 'User', definition: '教师科研、学生学习、馆员服务、科研管理',
    elements: ['教师科研','学生学习','馆员服务','科研管理'] },
  { letter: 'P', nameZh: '服务规则', nameEn: 'Policy', definition: '推荐规则、审核规则、推送规则、沉淀规则',
    elements: ['推荐规则','审核规则','推送规则','沉淀规则'] },
]
