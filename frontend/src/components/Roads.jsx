import { Route, TriangleAlert } from 'lucide-react'
import { api } from '../api'

export default function Roads({ campuses, roads, act }) {
  const pairs = []
  for (let i = 0; i < campuses.length; i++)
    for (let j = i + 1; j < campuses.length; j++) pairs.push([campuses[i], campuses[j]])
  const isBlocked = (a, b) => roads.blocked_roads.some(([p, q]) => p === Math.min(a, b) && q === Math.max(a, b))

  return (
    <div className="roads">
      <span className="roads-title"><Route size={16} /> Road status</span>
      {pairs.map(([a, b]) => {
        const blocked = isBlocked(a.id, b.id)
        return (
          <button key={a.id + '-' + b.id} className={'road' + (blocked ? ' blocked' : '')}
            aria-pressed={blocked}
            onClick={() => act(() => api.road({ from_campus_id: a.id, to_campus_id: b.id, blocked: !blocked }),
              blocked ? 'Road reopened' : 'Road marked blocked')}>
            {blocked && <TriangleAlert size={14} />}
            {a.name.replace('Campus ', '')} to {b.name.replace('Campus ', '')}: {blocked ? 'Blocked' : 'Open'}
          </button>
        )
      })}
    </div>
  )
}
