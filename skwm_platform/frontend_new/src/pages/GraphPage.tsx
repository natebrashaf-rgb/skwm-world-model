import { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3-force'
import { Breadcrumb } from '../components/Breadcrumb'
import { graphNodes, graphLinks, typeColors } from '../data/graph-data'

const TYPE_LIST = ['文献','作者','机构','主题','地点','政策','项目','事件','术语']
const RELATION_LIST = ['引用','合作','共现','对应','影响','演化','隶属']

export default function GraphPage() {
  const [selected, setSelected] = useState<string | null>(null)
  const [filterTypes, setFilterTypes] = useState<string[]>(TYPE_LIST)
  const [search, setSearch] = useState('')
  const svgRef = useRef<SVGSVGElement>(null)
  const [dim, setDim] = useState({ w: 700, h: 500 })

  const filtered = graphNodes.filter(n => filterTypes.includes(n.type) && (!search || n.label_zh.includes(search) || n.label_en.toLowerCase().includes(search.toLowerCase())))
  const nodeIds = new Set(filtered.map(n => n.id))
  const flinks = graphLinks.filter(l => nodeIds.has(l.source) && nodeIds.has(l.target))

  const simRef = useRef<any>(null)

  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()
    const w = dim.w, h = dim.h

    const nodes = filtered.map(n => ({ ...n, x: w/2 + (Math.random()-0.5)*200, y: h/2 + (Math.random()-0.5)*200 }))
    const links = flinks.map(l => ({ source: l.source, target: l.target, relation: l.relation }))

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(w/2, h/2))
    simRef.current = sim

    const linkGrp = svg.append('g')
    const linkEls = linkGrp.selectAll('line').data(links).join('line')
      .attr('stroke', '#e5e7eb').attr('stroke-width', 1).attr('stroke-opacity', 0.6)

    const nodeGrp = svg.append('g')
    const nodeEls = nodeGrp.selectAll('g').data(nodes).join('g')
      .call(d3.drag<any, any>()
        .on('start', (e, d) => { if (!e.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y })
        .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y })
        .on('end', (e, d) => { if (!e.active) sim.alphaTarget(0); d.fx = null; d.fy = null })
      ) as any

    nodeEls.append('circle')
      .attr('r', d => Math.max(5, Math.sqrt((d as any).degree) * 4))
      .attr('fill', d => typeColors[d.type] || '#f5f5f4')
      .attr('stroke', '#cbd5e1').attr('stroke-width', 1)
      .attr('cursor', 'pointer')
      .on('click', (e: any, d: any) => { e.stopPropagation(); setSelected(d.id) })

    nodeEls.append('text')
      .text(d => d.label_zh.length > 6 ? d.label_zh.slice(0,6)+'..' : d.label_zh)
      .attr('dx', 0).attr('dy', d => Math.max(5, Math.sqrt(d.degree)*4) + 12)
      .attr('text-anchor', 'middle').attr('font-size', 9).attr('fill', '#6b7280')

    // Highlight on hover
    nodeEls.on('mouseenter', function(e: any, d: any) {
      const neighbors = new Set(links.filter(l => l.source.id === d.id || l.target.id === d.id).flatMap(l => [l.source.id, l.target.id]))
      neighbors.add(d.id)
      nodeEls.attr('opacity', n => neighbors.has(n.id) ? 1 : 0.15)
      linkEls.attr('stroke-opacity', l => l.source.id === d.id || l.target.id === d.id ? 0.8 : 0.05)
    }).on('mouseleave', () => { nodeEls.attr('opacity', 1); linkEls.attr('stroke-opacity', 0.6) })

    sim.on('tick', () => {
      linkEls.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y)
      nodeEls.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
    })

    svg.on('click', () => setSelected(null))

    return () => { sim.stop() }
  }, [filterTypes, search, dim])

  useEffect(() => {
    const resize = () => setDim({ w: Math.max(400, (document.getElementById('graph-area')?.clientWidth || 700) - 20), h: 500 })
    resize(); window.addEventListener('resize', resize); return () => window.removeEventListener('resize', resize)
  }, [])

  const selNode = graphNodes.find(n => n.id === selected)
  const selLinks = selNode ? graphLinks.filter(l => l.source === selNode.id || l.target === selNode.id) : []

  return (
    <div>
      <Breadcrumb items={['KNOWLEDGE GRAPH']} />
      <h1 className="text-2xl font-bold text-gray-900 mb-4">知识图谱</h1>

      <div className="flex gap-4 flex-col lg:flex-row">
        {/* Left: Filter */}
        <div className="w-full lg:w-44 shrink-0 space-y-3">
          <div>
            <div className="text-[10px] font-semibold uppercase text-gray-400 mb-2">实体类型</div>
            <div className="flex flex-wrap gap-1.5">
              {TYPE_LIST.map(t => (
                <button key={t} onClick={() => setFilterTypes(p => p.includes(t) ? p.filter(x => x !== t) : [...p, t])}
                  className={`px-2 py-0.5 text-[11px] rounded border transition-colors ${filterTypes.includes(t) ? 'bg-primary-50 border-primary-200 text-primary' : 'border-gray-200 text-gray-500 hover:bg-gray-50'}`}>{t}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[10px] font-semibold uppercase text-gray-400 mb-2">搜索</div>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="名称..." className="w-full px-2 py-1 text-xs border border-gray-200 rounded focus:outline-none focus:border-primary-200" />
          </div>
          {/* Legend */}
          <div className="text-[10px] font-semibold uppercase text-gray-400 mb-2">图例</div>
          {TYPE_LIST.map(t => (
            <div key={t} className="flex items-center gap-2 text-xs text-gray-500 mb-1">
              <span className="w-3 h-3 rounded-full inline-block" style={{ background: typeColors[t] || '#f5f5f4', border: '1px solid #cbd5e1' }} />
              {t}
            </div>
          ))}
        </div>

        {/* Center: Graph */}
        <div id="graph-area" className="flex-1 bg-white border border-gray-200 rounded-lg overflow-hidden shadow-sm">
          <svg ref={svgRef} width={dim.w} height={dim.h} className="w-full" />
        </div>

        {/* Right: Detail */}
        <div className="w-full lg:w-56 shrink-0">
          {selNode ? (
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
              <h3 className="text-sm font-semibold text-gray-800 mb-2">{selNode.label_zh}</h3>
              <div className="space-y-1 text-xs text-gray-500">
                <div><span className="text-gray-400">类型：</span>{selNode.type}</div>
                <div><span className="text-gray-400">英文：</span>{selNode.label_en}</div>
                <div><span className="text-gray-400">阿文：</span>{selNode.label_ar}</div>
                <div><span className="text-gray-400">关系数：</span>{selLinks.length}</div>
                <div className="pt-2 border-t border-gray-100 mt-2">
                  <div className="text-gray-400 mb-1">相邻节点：</div>
                  {selLinks.map(l => {
                    const other = graphNodes.find(n => n.id === (l.source === selNode.id ? l.target : l.source))
                    return other ? <div key={l.source+l.target} className="flex justify-between"><span>{other.label_zh}</span><span className="text-gray-400">{l.relation}</span></div> : null
                  })}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm text-xs text-gray-400 space-y-1">
              <div>节点：{graphNodes.length}</div>
              <div>关系：{graphLinks.length}</div>
              <div className="pt-2 border-t border-gray-100 mt-2">
                {TYPE_LIST.map(t => {
                  const cnt = graphNodes.filter(n => n.type === t).length
                  return cnt > 0 ? <div key={t} className="flex justify-between"><span>{t}</span><span>{cnt}</span></div> : null
                })}
              </div>
              <p className="pt-2 text-[10px]">点击节点查看详情</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
