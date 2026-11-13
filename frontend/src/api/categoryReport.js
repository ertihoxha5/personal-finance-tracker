import { request } from './http.js'
import { categoryLabel } from '../lib/labels.js'

// Category report client (#26): GET /api/reports/categories?start=YYYY-MM-DD&end=YYYY-MM-DD,
// built by pft.services.reports (CategoryReport). Totals and percentages are calculated by the
// server and arrive as strings; this file only attaches display labels.

export async function fetchCategoryReport(start, end) {
  const query = `?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`
  const dto = await request(`/reports/categories${query}`)
  return {
    start: dto.start,
    end: dto.end,
    total: dto.total,
    categories: dto.categories.map((c) => ({
      id: c.category,
      name: categoryLabel(c.category),
      total: c.total,
      percent: c.percent,
    })),
  }
}
