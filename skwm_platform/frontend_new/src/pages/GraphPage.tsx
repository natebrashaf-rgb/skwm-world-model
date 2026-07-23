import { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import { select } from 'd3-selection'
import { drag } from 'd3-drag'
import { zoom } from 'd3-zoom'
import { Breadcrumb } from '../components/Breadcrumb'
import { Search, Route, ZoomIn, ZoomOut, RotateCcw } from 'lucide-react'

const API = '/api/graph-v4'
const API_V2 = '/api/graph-v2'
const EGO_API = '/api/graph-ego'
const PATH_API = '/api/graph-path'
const SEARCH_API = '/api/graph-search'

const TYPE_COLORS: Record<string, string> = {
  'Paper': '#dbeafe','Author':'#ccfbf1','Organization':'#fef3c7',
  'Topic':'#e0e7ff','Location':'#d1fae5','Policy':'#fce7f3',
  'Term':'#f5f5f4','TourismDestination':'#ffedd5','CulturalHeritage':'#ede9fe',
}
const REL_CN: Record<string, string> = {
  'cites':'引用','collaborates':'合作','co_occurs':'共现',
  'affiliated_with':'隶属','corresponds_to':'对应','influences':'影响','evolves_to':'演化','same_as':'等同',
}
const COMM_COLORS = ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#3ba272','#fc8452','#9a60b4','#ea7ccc','#1ab394']

export default function GraphPage() {
  const [lang, setLang] = useState<'zh'|'en'>('zh')
  const [data, setData] = useState<any>(null)
  const [selected, setSelected] = useState<string | null>(null)
  const [hovered, setHovered] = useState<string | null>(null)
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState<any[]>([])
  const [pathSrc, setPathSrc] = useState('')
  const [pathTgt, setPathTgt] = useState('')
  const [pathResult, setPathResult] = useState<any>(null)
  const [filterType, setFilterType] = useState<string>('all')
  const [communityMode, setCommunityMode] = useState(true)
  const [viewMode, setViewMode] = useState<'cluster'|'node'>('cluster')
  const svgRef = useRef<SVGSVGElement>(null)
  const [dim, setDim] = useState({ w: 700, h: 500 })
  const simRef = useRef<any>(null)

  // Load communities (v4)
  useEffect(() => {
    fetch(`${API}?level=cluster&year=2026`).then(r => r.json()).then(d => {
      if (d.communities) {
        setData({...d, nodes: d.communities, edges: []})
        setViewMode('cluster')
      }
    })
  }, [])

  // Resize
  useEffect(() => {
    const resize = () => setDim({ w: Math.max(400, (document.getElementById('graph-area')?.clientWidth || 700) - 20), h: 500 })
    resize(); window.addEventListener('resize', resize); return () => window.removeEventListener('resize', resize)
  }, [])

  // Search
  useEffect(() => {
    if (!searchQ.trim()) { setSearchResults([]); return }
    const t = setTimeout(() => {
      fetch(`${SEARCH_API}?q=${encodeURIComponent(searchQ)}`).then(r => r.json()).then(d => {
        setSearchResults(d.results || [])
      })
    }, 300)
    return () => clearTimeout(t)
  }, [searchQ])

  // Render graph
  useEffect(() => {
    if (!svgRef.current || !data) return
    const svg = select(svgRef.current)
    svg.selectAll('*').remove()
    const w = dim.w, h = dim.h
    const g = svg.append('g')

    // Add zoom behavior
    svg.call(zoom<any, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
    )
    
    let nodes = data.nodes || []
    let edges = data.edges || []

    // Filter
    if (filterType !== 'all') {
      nodes = nodes.filter((n: any) => n.type === filterType)
      const ids = new Set(nodes.map((n: any) => n.id))
      edges = edges.filter((e: any) => ids.has(e.source) && ids.has(e.target))
    }

    if (!nodes.length) return

    const simNodes = nodes.map((n: any) => ({
      ...n, x: w/2 + (Math.random()-0.5)*200, y: h/2 + (Math.random()-0.5)*200
    }))
    const simLinks = edges.map((e: any) => ({
      source: e.source, target: e.target, relation: e.relation, label: e.label
    }))
    const nodeMap = new Map(simNodes.map((n: any) => [n.id, n]))

    const sim = forceSimulation(simNodes)
      .force('link', forceLink(simLinks).id((d: any) => d.id).distance(100))
      .force('charge', forceManyBody().strength(-250))
      .force('center', forceCenter(w/2, h/2))
      .force('collision', forceCollide(30))
    simRef.current = sim

    // Edges with labels
    const linkGrp = g.append('g')
    const linkEls = linkGrp.selectAll('line').data(simLinks).join('line')
      .attr('stroke', '#d1d5db').attr('stroke-width', 0.8).attr('stroke-opacity', 0.4)

    const labelGrp = g.append('g')
    const labelEls = labelGrp.selectAll('text').data(simLinks).join('text')
      .text(d => REL_CN[d.relation] || d.relation || '')
      .attr('font-size', 8).attr('fill', '#9ca3af').attr('text-anchor', 'middle')

    // Nodes
    const nodeGrp = g.append('g')
    const nodeEls = nodeGrp.selectAll('g').data(simNodes).join('g')
      .call(drag<any, any>()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      ) as any

    nodeEls.append('circle')
      .attr('r', d => {
        const n = d as any
        return Math.max(6, Math.min(20, (n.heat || n.degree || 10) / 5))
      })
      .attr('fill', d => {
        const n = d as any
        if (communityMode && n.community_id !== undefined) {
          return COMM_COLORS[n.community_id % COMM_COLORS.length]
        }
        return TYPE_COLORS[n.type] || '#f5f5f4'
      })
      .attr('stroke', d => {
        const n = d as any
        if (selected && (n.id === selected || nodeMap.get(selected)?.type === n.type)) return '#2563eb'
        return '#cbd5e1'
      })
      .attr('stroke-width', d => selected && (d as any).id === selected ? 3 : 1)
      .attr('cursor', 'pointer')
      .on('click', (e: any, d: any) => { e.stopPropagation(); setSelected(d.id) })
      .on('mouseenter', (e: any, d: any) => setHovered(d.id))
      .on('mouseleave', () => setHovered(null))

    // Labels (trilingual)
    nodeEls.append('text')
      .text(d => {
        const n = d as any
        const label = lang === 'zh' ? (n.label_zh || n.label_en) : n.label_en
        return (label || '').length > 8 ? label.slice(0,8)+'…' : (label || n.id || '')
      })
      .attr('dx', 0).attr('dy', d => Math.max(8, (d as any).heat || 10) / 5 + 14)
      .attr('text-anchor', 'middle').attr('font-size', 9).attr('fill', '#6b7280')
      .attr('dir', lang === 'ar' ? 'rtl' : 'ltr')

    // Highlight on hover
    nodeEls.on('mouseenter', function(e: any, d: any) {
      setHovered(d.id)
      const neighbors = new Set(simLinks.filter(l => l.source.id === d.id || l.target.id === d.id).flatMap(l => [l.source.id, l.target.id]))
      neighbors.add(d.id)
      nodeEls.attr('opacity', n => neighbors.has(n.id) ? 1 : 0.2)
      linkEls.attr('stroke-opacity', l => l.source.id === d.id || l.target.id === d.id ? 0.8 : 0.05)
      labelEls.attr('opacity', l => l.source.id === d.id || l.target.id === d.id ? 1 : 0)
    }).on('mouseleave', () => {
      setHovered(null)
      nodeEls.attr('opacity', 1)
      linkEls.attr('stroke-opacity', 0.4)
      labelEls.attr('opacity', 1)
    })

    // Tick
    sim.on('tick', () => {
      linkEls.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y)
      labelEls.attr('x', (d: any) => (d.source.x + d.target.x)/2)
        .attr('y', (d: any) => (d.source.y + d.target.y)/2)
      nodeEls.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    svg.on('click', () => setSelected(null))

    return () => { sim.stop() }
  }, [data, filterType, lang, communityMode, dim, selected])

  // Ego-network expansion
  const expandEgo = async (nodeId: string) => {
    const r = await fetch(`${EGO_API}?id=${nodeId}&hops=1`)
    const d = await r.json()
    if (d.nodes && data) {
      const existing = new Set(data.nodes.map((n: any) => n.id))
      const newNodes = d.nodes.filter((n: any) => !existing.has(n.id))
      if (newNodes.length > 0) {
        setData({
          ...data,
          nodes: [...data.nodes, ...newNodes],
          edges: [...data.edges, ...d.edges],
        })
      }
    }
  }

  // Shortest path
  const findPath = async () => {
    if (!pathSrc || !pathTgt) return
    const r = await fetch(`${PATH_API}?source=${pathSrc}&target=${pathTgt}`)
    const d = await r.json()
    setPathResult(d)
  }

  // Focus on search result
  const focusNode = (nodeId: string) => {
    setSelected(nodeId)
    expandEgo(nodeId)
  }

  const selNode = data?.nodes?.find((n: any) => n.id === selected)
  const selEdges = selNode ? data?.edges?.filter((e: any) => e.source === selNode.id || e.target === selNode.id) : []

  return (
    <div>
      <Breadcrumb items={['KNOWLEDGE GRAPH v2']} />
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900">知识图谱 · 本体驱动</h1>
        <div className="flex items-center gap-2">
          <select value={lang} onChange={e => setLang(e.target.value as any)} className="px-2 py-1 text-xs border border-gray-200 rounded bg-white">
            <option value="zh">中文</option><option value="en">English</option>
          </select>
          <button onClick={() => setCommunityMode(v => !v)}
            className={`px-2 py-1 text-xs rounded border ${communityMode ? 'bg-primary-50 border-primary-200 text-primary' : 'border-gray-200 text-gray-500'}`}>
            社区色
          </button>
        </div>
      </div>

      <div className="flex gap-4 flex-col lg:flex-row">
        {/* Left panel */}
        <div className="w-full lg:w-48 shrink-0 space-y-3">
          {/* Search */}
          <div className="relative">
            <Search size={14} className="absolute left-2 top-2.5 text-gray-400" />
            <input value={searchQ} onChange={e => setSearchQ(e.target.value)} placeholder="搜索实体..."
              className="w-full pl-7 pr-2 py-1.5 text-xs border border-gray-200 rounded focus:outline-none focus:border-primary-200" />
            {searchResults.length > 0 && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded shadow-lg z-10 max-h-40 overflow-y-auto">
                {searchResults.map(r => (
                  <button key={r.id} onClick={() => { focusNode(r.id); setSearchQ('') }}
                    className="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 border-b border-gray-50 last:border-0">
                    {r.label_zh || r.label_en || r.id}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Type filter */}
          <div>
            <div className="text-[10px] font-semibold text-gray-400 mb-1">类型</div>
            <select value={filterType} onChange={e => setFilterType(e.target.value)}
              className="w-full px-2 py-1 text-xs border border-gray-200 rounded bg-white">
              <option value="all">全部</option>
              {Object.keys(TYPE_COLORS).map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>

          {/* Shortest path */}
          <div>
            <div className="text-[10px] font-semibold text-gray-400 mb-1">最短路径</div>
            <input value={pathSrc} onChange={e => setPathSrc(e.target.value)} placeholder="起点ID" className="w-full px-2 py-1 text-xs border border-gray-200 rounded mb-1" />
            <input value={pathTgt} onChange={e => setPathTgt(e.target.value)} placeholder="终点ID" className="w-full px-2 py-1 text-xs border border-gray-200 rounded mb-1" />
            <button onClick={findPath} className="w-full flex items-center justify-center gap-1 px-2 py-1 text-xs bg-primary text-white rounded hover:bg-primary-700">
              <Route size={12} />查询路径
            </button>
            {pathResult?.path && (
              <div className="mt-1 p-2 bg-gray-50 rounded text-[10px] text-gray-600">
                路径: {pathResult.path.join(' → ')} (长度: {pathResult.length})
              </div>
            )}
          </div>

          {/* Stats */}
          {data && (
            <div className="text-[10px] text-gray-400 space-y-0.5">
              <div>节点: {data.nodes?.length || 0}</div>
              <div>边: {data.edges?.length || 0}</div>
              <div>社区: {Object.keys(data.communities || {}).length}</div>
            </div>
          )}
        </div>

        {/* Graph */}
        <div id="graph-area" className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <svg ref={svgRef} width={dim.w} height={dim.h} className="w-full" />
        </div>

        {/* Right detail */}
        <div className="w-full lg:w-56 shrink-0">
          {selNode ? (
            <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm text-xs space-y-1">
              <h3 className="text-sm font-semibold text-gray-800 mb-1">{selNode.label_zh || selNode.label_en}</h3>
              <div><span className="text-gray-400">类型：</span>{selNode.type}</div>
              {selNode.label_en && <div><span className="text-gray-400">EN：</span>{selNode.label_en}</div>}
              {selNode.label_ar && <div><span className="text-gray-400">AR：</span><span dir="rtl">{selNode.label_ar}</span></div>}
              {selNode.domain && <div><span className="text-gray-400">领域：</span>{selNode.domain}</div>}
              {selNode.heat && <div><span className="text-gray-400">热度：</span>{selNode.heat}</div>}
              {selNode.community_id !== undefined && <div><span className="text-gray-400">社区：</span>#{selNode.community_id}</div>}
              <div><span className="text-gray-400">关系：</span>{selEdges?.length || 0}</div>
              <div className="pt-1 border-t border-gray-100 mt-1 space-y-1">
                {selEdges?.slice(0,8).map((e: any, i: number) => {
                  const other = data.nodes.find((n: any) => n.id === (e.source === selNode.id ? e.target : e.source))
                  return other ? <div key={i} className="flex justify-between text-[10px]"><span>{other.label_zh || other.label_en}</span><span className="text-gray-400">{REL_CN[e.relation] || e.relation}</span></div> : null
                })}
              </div>
              <button onClick={() => expandEgo(selNode.id)} className="w-full mt-2 px-2 py-1 text-[10px] bg-gray-50 border border-gray-200 rounded hover:bg-gray-100">
                展开邻域 (+)
              </button>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg p-3 shadow-sm text-xs text-gray-400">
              <div>核心子图模式</div>
              <div className="text-[10px] mt-1">- 默认50节点 (社区代表)</div>
              <div className="text-[10px]">- 点击节点展开邻域</div>
              <div className="text-[10px]">- 搜索定位+聚焦</div>
              <div className="text-[10px]">- 查询两实体路径</div>
              <div className="mt-2 pt-2 border-t border-gray-100">
                <div className="flex flex-wrap gap-1">
                  {Object.entries(TYPE_COLORS).map(([t, c]) => (
                    <span key={t} className="flex items-center gap-1 text-[10px] text-gray-500">
                      <span className="w-2 h-2 rounded-full inline-block" style={{background:c}} />
                      {t.slice(0,4)}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
