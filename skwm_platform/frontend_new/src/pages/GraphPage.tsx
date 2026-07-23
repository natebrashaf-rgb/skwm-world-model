import { useEffect, useRef, useState } from 'react'
import { forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide } from 'd3-force'
import { select } from 'd3-selection'
import { drag } from 'd3-drag'
import { zoom } from 'd3-zoom'
import { Breadcrumb } from '../components/Breadcrumb'
import { Search, RotateCcw, Network } from 'lucide-react'

const API = '/api/graph-v4'
const TYPE_COLORS: Record<string, string> = {
  'Topic':'#e0e7ff','Paper':'#dbeafe','Author':'#ccfbf1',
  'Location':'#d1fae5','Policy':'#fce7f3','CulturalHeritage':'#ede9fe',
  'TourismDestination':'#ffedd5','Organization':'#fef3c7',
}
const COMM_COLORS = ['#5470c6','#91cc75','#fac858','#ee6666','#73c0de','#3ba272','#fc8452','#9a60b4','#ea7ccc']

export default function GraphPage() {
  const [nodes, setNodes] = useState<any[]>([])
  const [edges, setEdges] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<string | null>(null)
  const [showCluster, setShowCluster] = useState(false)
  const [searchQ, setSearchQ] = useState('')
  const [topN, setTopN] = useState(200)
  const svgRef = useRef<SVGSVGElement>(null)
  const simRef = useRef<any>(null)

  // Load
  const loadGraph = async (params: string) => {
    setLoading(true)
    const r = await fetch(`${API}?${params}`)
    const d = await r.json()
    if (d.nodes) {
      setNodes(d.nodes); setEdges(d.edges || [])
    } else if (d.communities) {
      // Cluster view
      setNodes(d.communities.map((c: any, i: number) => ({
        id: `comm_${c.id}`,
        label_zh: c.name,
        size: Math.min(30, Math.max(8, c.size * 0.5)),
        heat: c.total_heat || 0,
        communityId: c.id,
        isCluster: true,
        x: c.x || (i * 80),
        y: c.y || (i % 2 === 0 ? 100 : 300),
      })))
      setEdges([])
    }
    setLoading(false)
  }

  useEffect(() => { loadGraph(`level=node&year=2026&top_n=${topN}`) }, [topN])

  // Search
  const doSearch = () => {
    if (!searchQ.trim()) return
    loadGraph(`level=node&year=2026&q=${encodeURIComponent(searchQ)}&top_n=30`)
  }

  // Cluster toggle
  const toggleCluster = () => {
    setShowCluster(v => !v)
    if (!showCluster) loadGraph('level=cluster&year=2026')
    else loadGraph(`level=node&year=2026&top_n=${topN}`)
  }

  // Node click
  const onNodeClick = async (node: any) => {
    if (node.isCluster) {
      // Expand community
      loadGraph(`level=node&year=2026&community_id=${node.communityId}&top_n=50`)
    } else {
      setSelected(node.id === selected ? null : node.id)
      // Expand 1-hop
      const r = await fetch(`${API}?level=node&year=2026&focus=${encodeURIComponent(node.id)}&top_n=30`)
      const d = await r.json()
      if (d.nodes) {
        const existing = new Set(nodes.map(n => n.id))
        const newNodes = d.nodes.filter((n: any) => !existing.has(n.id))
        if (newNodes.length > 0) {
          setNodes(prev => [...prev, ...newNodes])
          setEdges(prev => [...prev, ...(d.edges || [])])
        }
      }
    }
  }

  // D3 render
  useEffect(() => {
    if (!svgRef.current || nodes.length === 0) return
    const svg = select(svgRef.current)
    svg.selectAll('*').remove()
    const w = svgRef.current.clientWidth || 800
    const h = 500
    const g = svg.append('g')

    svg.call(zoom<any, unknown>().scaleExtent([0.1, 5])
      .on('zoom', e => g.attr('transform', e.transform)))

    const sim = forceSimulation(nodes)
      .force('link', forceLink(edges).id((d: any) => d.id).distance(60))
      .force('charge', forceManyBody().strength(-80))
      .force('center', forceCenter(w/2, h/2))
      .force('collision', forceCollide((d: any) => (d.size || 8) + 2))
    simRef.current = sim

    const link = g.append('g').selectAll('line').data(edges).join('line')
      .attr('stroke', '#d1d5db').attr('stroke-width', 0.5).attr('stroke-opacity', 0.3)

    const nodeGrp = g.append('g').selectAll('g').data(nodes).join('g')
      .call(drag<any, any>()
        .on('start', (e, d: any) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d: any) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d: any) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      ) as any

    nodeGrp.append('circle')
      .attr('r', d => Math.max(5, Math.min(25, (d as any).size || 8)))
      .attr('fill', d => {
        const n = d as any
        if (n.isCluster) return COMM_COLORS[n.communityId % COMM_COLORS.length]
        return TYPE_COLORS[n.type] || '#e0e7ff'
      })
      .attr('stroke', d => (d as any).id === selected ? '#2563eb' : '#cbd5e1')
      .attr('stroke-width', d => (d as any).id === selected ? 3 : 1)
      .attr('cursor', 'pointer')
      .on('click', (e: any, d: any) => { e.stopPropagation(); onNodeClick(d) })

    nodeGrp.append('text')
      .text(d => {
        const n = d as any
        const label = n.label_zh || n.label_en || n.id
        return (label || '').length > 6 ? label.slice(0, 6) + '…' : (label || '')
      })
      .attr('dx', 0).attr('dy', d => Math.max(5, (d as any).size || 8) + 14)
      .attr('text-anchor', 'middle').attr('font-size', 8).attr('fill', '#6b7280')

    nodeGrp.on('mouseenter', function(e: any, d: any) {
      const id = (d as any).id
      nodeGrp.attr('opacity', n => (n as any).id === id ? 1 : 0.3)
      link.attr('stroke-opacity', (l: any) => l.source.id === id || l.target.id === id ? 0.8 : 0.05)
    }).on('mouseleave', () => {
      nodeGrp.attr('opacity', 1)
      link.attr('stroke-opacity', 0.3)
    })

    sim.on('tick', () => {
      link.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y)
      nodeGrp.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    svg.on('click', () => setSelected(null))
    return () => sim.stop()
  }, [nodes, edges, selected])

  return (
    <div>
      <Breadcrumb items={['KNOWLEDGE GRAPH']} />
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-xl font-bold text-gray-900">知识图谱</h1>
        <div className="flex items-center gap-2">
          <div className="relative">
            <input value={searchQ} onChange={e => setSearchQ(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && doSearch()}
              placeholder="搜索..." className="w-32 px-2 py-1 text-xs border border-gray-200 rounded" />
          </div>
          <select value={topN} onChange={e => setTopN(Number(e.target.value))}
            className="px-2 py-1 text-xs border border-gray-200 rounded bg-white">
            <option value={100}>100节点</option>
            <option value={200}>200节点</option>
            <option value={500}>500节点</option>
          </select>
          <button onClick={toggleCluster}
            className={`px-2 py-1 text-xs rounded border ${showCluster ? 'bg-primary-50 border-primary-200 text-primary' : 'border-gray-200 text-gray-500'}`}>
            <Network size={12} className="inline mr-1" />社区
          </button>
          <button onClick={() => loadGraph(`level=node&year=2026&top_n=${topN}`)}
            className="p-1 text-gray-400 hover:text-gray-600"><RotateCcw size={14} /></button>
        </div>
      </div>
      {loading && <div className="text-xs text-gray-400 py-8 text-center">加载中...</div>}
      {!loading && nodes.length === 0 && <div className="text-xs text-gray-400 py-8 text-center">暂无数据</div>}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
        <svg ref={svgRef} width="100%" height={500} style={{ minHeight: 500 }} />
      </div>
      <div className="mt-2 flex justify-between text-[10px] text-gray-400">
        <span>{nodes.length} 节点 · {edges.length} 边</span>
        <span className="flex gap-2">
          {Object.entries(TYPE_COLORS).map(([t, c]) => (
            <span key={t} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full inline-block" style={{background:c}} />{t}
            </span>
          ))}
        </span>
      </div>
    </div>
  )
}
