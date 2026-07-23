import { useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'

const TEMPLATES = ['研究热点分析报告', '需求调研报告', '学科服务案例']

export default function ReportPage() {
  const [tpl, setTpl] = useState(TEMPLATES[0])
  const [topic, setTopic] = useState('中阿文旅')
  const [preview, setPreview] = useState('')

  const generate = () => {
    setPreview(`# ${tpl}

**主题**: ${topic}
**生成时间**: 2026-07

## 概述
基于 SKWM 世界模型（89 年 × 43,537 条状态向量）的分析报告。

## 研究发现
- 核心热点：tourism (50), system (10), model (9)
- 新兴前沿：tourism (+8,760), heritage (+4,760)
- 数据来源：1,548 篇文献 · 8 个数据源

## 方法说明
本报告基于科学计量分析、知识图谱查询与 GraphRAG 智能问答生成。
待接入后端后将提供完整可交互版本。`)
  }

  return (
    <div>
      <Breadcrumb items={['REPORT']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">报告生成</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="space-y-3">
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="text-xs font-semibold text-gray-400 uppercase mb-3">报告模板</div>
            <div className="space-y-1">
              {TEMPLATES.map(t => (
                <button key={t} onClick={() => setTpl(t)}
                  className={`w-full text-left px-3 py-2 text-sm rounded-lg ${tpl === t ? 'bg-primary-50 text-primary font-medium' : 'text-gray-600 hover:bg-gray-50'}`}>{t}</button>
              ))}
            </div>
          </div>
          <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
            <div className="text-xs font-semibold text-gray-400 uppercase mb-3">参数</div>
            <div className="space-y-2">
              <div><label className="text-xs text-gray-500">主题</label><input value={topic} onChange={e => setTopic(e.target.value)} className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded-lg mt-1" /></div>
              <div><label className="text-xs text-gray-500">时间范围</label><select className="w-full px-2 py-1.5 text-sm border border-gray-200 rounded-lg mt-1"><option>近 5 年</option><option>近 10 年</option><option>全部</option></select></div>
              <button onClick={generate} className="w-full px-3 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-700">生成报告</button>
            </div>
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
          <div className="text-xs font-semibold text-gray-400 uppercase mb-3">预览</div>
          <div className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{preview || '选择模板和参数后点击生成'}</div>
        </div>
      </div>
    </div>
  )
}
