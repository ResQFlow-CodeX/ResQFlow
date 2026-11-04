import { useState } from 'react'
import { MessageSquareText, Truck } from 'lucide-react'
import { api } from '../api'
import CampusCard from '../components/CampusCard'

export default function Campuses({ data, act }) {
  const { campuses, vehicles } = data

  const [f, setF] = useState({
    campus_id: campuses[0]?.id ?? 1,
    resource: 'water',
    quantity: '',
  })

  const [text, setText] = useState('A water 500')
  const [reply, setReply] = useState(null)

  const set = (k) => (e) =>
    setF({ ...f, [k]: e.target.value })

  const save = async () => {
    if (f.quantity === '' || Number(f.quantity) < 0) return

    const out = await act(
      () =>
        api.updateStock({
          campus_id: Number(f.campus_id),
          resource: f.resource,
          quantity: Number(f.quantity),
        }),
      'Stock updated'
    )

    if (out) setF({ ...f, quantity: '' })
  }

  const sendSms = async () => {
    const out = await act(() => api.sms(text))
    if (out) setReply(out.message)
  }

  return (
    <>
      <div className="campus-row">
        {campuses.map((c) => (
          <CampusCard key={c.id} campus={c} />
        ))}
      </div>

      <div className="grid-2">
        <section className="block">
          <h3 className="h">Update stock</h3>
          <p className="muted small">
            Select a campus, choose a resource, and enter the updated quantity.
          </p>

          <div className="form">
            <label>
              Campus
              <select
                value={f.campus_id}
                onChange={set('campus_id')}
              >
                {campuses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>

            <label>
              Resource
              <select
                value={f.resource}
                onChange={set('resource')}
              >
                <option value="water">Water</option>
                <option value="medicine">Medicine</option>
              </select>
            </label>

            <label>
              Quantity
              <input
                type="number"
                min="0"
                placeholder="Enter quantity"
                value={f.quantity}
                onChange={set('quantity')}
              />
            </label>

            <button
              className="btn primary wide"
              onClick={save}
              disabled={f.quantity === '' || Number(f.quantity) < 0}
            >
              Save stock update
            </button>

            <button
              className="btn wide"
              onClick={() =>
                act(
                  () =>
                    api.consume({
                      campus_id: Number(f.campus_id),
                      resource: f.resource,
                      hours: 1,
                    }),
                  'One hour of consumption simulated'
                )
              }
            >
              Simulate 1 hour of consumption
            </button>
          </div>
        </section>

        <div>
          <section className="block">
            <h3 className="h">
              <Truck size={18} /> Vehicles
            </h3>

            <ul className="vehicles">
              {vehicles.map((v) => (
                <li key={v.id}>
                  <div>
                    <b>{v.name}</b>
                    <span className="muted small">
                      {' '}based at {v.campus}, carries{' '}
                      {v.capacity.toLocaleString()}
                    </span>
                  </div>

                  <button
                    className={'switch' + (v.available ? ' on' : '')}
                    role="switch"
                    aria-checked={v.available}
                    onClick={() =>
                      act(
                        () => api.setVehicle(v.id, !v.available),
                        `${v.name} marked ${
                          v.available ? 'unavailable' : 'available'
                        }`
                      )
                    }
                  >
                    {v.available ? 'Available' : 'Unavailable'}
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="block">
            <h3 className="h">
              <MessageSquareText size={18} /> Text message update
            </h3>

            <p className="muted small">
              When there is no internet, volunteers can text a stock count.
              Format: campus letter, resource, number.
            </p>

            <div className="inline">
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                aria-label="Text message"
              />
              <button
                className="btn primary"
                onClick={sendSms}
              >
                Send text
              </button>
            </div>

            {reply && <p className="bubble">{reply}</p>}
          </section>
        </div>
      </div>
    </>
  )
}