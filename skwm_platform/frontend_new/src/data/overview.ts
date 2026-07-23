export interface OverviewStats {
  stateVectors: number; relations: number; snapshots: number; totalDocs: number
}
export const overviewStats: OverviewStats = { stateVectors: 43537, relations: 586912, snapshots: 89, totalDocs: 15478 }

export interface HotspotItem { rank: number; name: string; value: number }
export const topHotspots: HotspotItem[] = [
  { rank: 1, name: 'tourism', value: 50 }, { rank: 2, name: 'system', value: 10 },
  { rank: 3, name: 'model', value: 9 }, { rank: 4, name: 'network', value: 6 },
  { rank: 5, name: 'learning', value: 3 }, { rank: 6, name: 'knowledge', value: 2 },
  { rank: 7, name: 'data', value: 1 }, { rank: 8, name: 'heritage', value: 1 },
  { rank: 9, name: 'digital', value: 1 }, { rank: 10, name: 'travel', value: 1 },
]

export interface FrontierItem { rank: number; name: string; growth: number }
export const topFrontiers: FrontierItem[] = [
  { rank: 1, name: 'tourism', growth: 8760 }, { rank: 2, name: 'heritage', growth: 4760 },
  { rank: 3, name: 'model', growth: 4680 }, { rank: 4, name: 'arab', growth: 3860 },
  { rank: 5, name: 'language', growth: 3500 },
]

export interface TimelineYear { year: number; nodes: number }
export const timelineData: TimelineYear[] = Array.from({ length: 89 }, (_, i) => ({
  year: 1937 + i, nodes: Math.round(3 * Math.exp(0.05 * i) * (1 + Math.random() * 0.2))
}))
