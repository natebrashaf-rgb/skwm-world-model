import { useState } from 'react'
import { Breadcrumb } from '../components/Breadcrumb'
import { skwmDimensions } from '../data/model-data'

export default function ModelPage() {
  const [view, setView] = useState<'grid' | 'ring'>('grid')
  const [active, setActive] = useState<string | null>(null)

  return (
    <div>
      <Breadcrumb items={['SKWM MODEL']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-1">科学知识世界模型</h1>
      <p className="text-sm text-gray-400 mb-6">SKWM = (E, R, S, T, C, U, P)</p>

      <div className="flex gap-2 mb-4">
        <button onClick={() => setView('grid')} className={`px-3 py-1.5 text-xs rounded-lg ${view==='grid'?'bg-primary text-white':'bg-white border border-gray-200 text-gray-600'}`}>集合视图</button>
        <button onClick={() => setView('ring')} className={`px-3 py-1.5 text-xs rounded-lg ${view==='ring'?'bg-primary text-white':'bg-white border border-gray-200 text-gray-600'}`}>关系环形</button>
      </div>

      {view === 'grid' ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {skwmDimensions.map(d => (
            <div key={d.letter} id={`dim-${d.letter}`}
              className={`bg-white border rounded-lg p-4 shadow-sm transition-colors ${active === d.letter ? 'border-primary-200 ring-1 ring-primary-100' : 'border-gray-200'}`}
              onMouseEnter={() => setActive(d.letter)} onMouseLeave={() => setActive(null)}>
              <div className="flex items-center gap-2 mb-2">
                <span className="w-7 h-7 rounded bg-primary-50 text-primary font-bold text-sm flex items-center justify-center">{d.letter}</span>
                <div><div className="text-sm font-semibold text-gray-800">{d.nameZh}</div><div className="text-[10px] text-gray-400">{d.nameEn}</div></div>
              </div>
              <div className="text-xs text-gray-500 mb-2">{d.definition}</div>
              <div className="flex flex-wrap gap-1">{d.elements.map(e => <span key={e} className="px-1.5 py-0.5 bg-gray-50 text-gray-500 rounded text-[10px] border border-gray-100">{e}</span>)}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg p-8 shadow-sm flex justify-center">
          <svg width="500" height="480" viewBox="0 0 500 480">
            {/* Center */}
            <circle cx="250" cy="240" r="36" fill="#eff6ff" stroke="#2563eb" strokeWidth="2" />
            <text x="250" y="244" textAnchor="middle" fontSize="12" fontWeight="bold" fill="#2563eb">SKWM</text>
            {/* 7 Dimensions in a circle */}
            {skwmDimensions.map((d, i) => {
              const angle = (i * 2 * Math.PI) / 7 - Math.PI / 2
              const cx = 250 + 150 * Math.cos(angle), cy = 240 + 150 * Math.sin(angle)
              return (
                <g key={d.letter}>
                  <line x1="250" y1="240" x2={cx} y2={cy} stroke={active === d.letter ? '#2563eb' : '#e5e7eb'} strokeWidth={active === d.letter ? 2 : 1} />
                  <circle cx={cx} cy={cy} r={active === d.letter ? 24 : 20} fill={active === d.letter ? '#eff6ff' : '#f9fafb'} stroke={active === d.letter ? '#2563eb' : '#d1d5db'} strokeWidth="1.5" />
                  <text x={cx} y={cy+1} textAnchor="middle" fontSize="11" fontWeight="bold" fill={active === d.letter ? '#2563eb' : '#6b7280'}>{d.letter}</text>
                  <text x={cx} y={cy+18} textAnchor="middle" fontSize="8" fill="#9ca3af">{d.nameZh}</text>
                </g>
              )
            })}
          </svg>
        </div>
      )}
    </div>
  )
}
