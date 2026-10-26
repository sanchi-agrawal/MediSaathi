import { useState } from 'react'
import { Heart, Info, RotateCcw } from 'lucide-react'

const organs = {
  heart: { label: 'Heart', detail: 'Part of the circulatory system.', x: 54, y: 35 },
  lungs: { label: 'Lungs', detail: 'Part of the respiratory system.', x: 38, y: 31 },
  brain: { label: 'Brain', detail: 'Part of the nervous system.', x: 50, y: 10 },
}
export default function Anatomy() {
  const [selected, setSelected] = useState<keyof typeof organs>('heart')
  const [angle, setAngle] = useState(0)
  return <div className="anatomy-scene">
    <div className="orbit orbit-one" /><div className="orbit orbit-two" />
    <span className="anatomy-label">THE HUMAN CONNECTION</span>
    <div className="anatomy-body" style={{ transform: `perspective(900px) rotateY(${angle}deg)` }}>
      <svg viewBox="0 0 300 600" role="img" aria-label="Stylized human anatomy illustration, not a clinical model">
        <defs><linearGradient id="body" x1="0" x2="1"><stop stopColor="#163e5d" stopOpacity=".35"/><stop offset=".5" stopColor="#7cc7ec" stopOpacity=".2"/><stop offset="1" stopColor="#19507b" stopOpacity=".4"/></linearGradient><radialGradient id="organ"><stop stopColor="#ff8b94"/><stop offset="1" stopColor="#ff5967" stopOpacity=".4"/></radialGradient><filter id="soft"><feGaussianBlur stdDeviation="4"/></filter></defs>
        <path d="M150 22 C117 22 113 45 116 65 Q117 89 132 98 L131 117 Q104 122 87 133 Q74 142 69 169 L54 241 L38 307 Q32 326 41 330 Q49 332 56 312 L83 249 L104 187 L108 259 Q97 297 104 341 L113 442 L111 548 Q96 564 102 572 L129 572 Q138 568 136 549 L141 443 L150 353 L159 443 L164 549 Q162 568 171 572 L198 572 Q204 564 189 548 L187 442 L196 341 Q203 297 192 259 L196 187 L217 249 L244 312 Q251 332 259 330 Q268 326 262 307 L246 241 L231 169 Q226 142 213 133 Q196 122 169 117 L168 98 Q183 89 184 65 C187 45 183 22 150 22Z" fill="url(#body)" stroke="#6db4d5" strokeWidth="1.3"/>
        <g fill="none" stroke="#79b1ca" opacity=".35"><path d="M150 115 V335 M114 151 Q150 168 186 151 M112 164 Q150 185 188 164 M110 180 Q150 202 190 180 M110 196 Q150 219 190 196 M112 212 Q150 234 188 212 M115 228 Q150 249 185 228 M114 290 Q150 316 186 290 M113 309 Q150 338 187 309 M124 342 L128 440 L123 548 M176 342 L172 440 L177 548 M97 159 L75 241 L45 316 M203 159 L225 241 L255 316"/>{Array.from({length:15},(_,i)=><path key={i} d={`M145 ${130+i*12} h10`} />)}</g>
        <path d="M140 146 Q118 134 112 163 Q101 191 112 223 Q127 237 139 217Z M160 146 Q182 134 188 163 Q199 191 188 223 Q173 237 161 217Z" fill="#278dda" opacity={selected === 'lungs' ? '.85' : '.3'} stroke="#58b4ec"/>
        <path d="M151 185 C134 169 123 194 139 211 L153 227 L168 207 C180 187 164 173 151 185Z" fill="url(#organ)" opacity={selected === 'heart' ? '1' : '.5'}/>
        <path d="M125 50 Q124 30 148 32 Q175 29 176 52 L170 72 Q149 82 130 69Z" fill="#278dda" opacity={selected === 'brain' ? '.8' : '.35'} stroke="#77bbdf"/>
        <path d="M123 252 Q147 238 177 250 Q181 272 160 277 Q146 291 120 279Z" fill="#ff8b94" opacity=".25"/>
        <g stroke="#73bddc" fill="none" opacity=".35"><path d="M124 53 Q142 38 151 60 Q158 40 171 52 M130 61 Q148 48 168 65 M120 268 Q155 256 176 266 M120 277 Q148 269 168 278"/></g>
      </svg>
      {Object.entries(organs).map(([key, organ]) => <button key={key} className={`organ-dot ${selected === key ? 'selected' : ''}`} style={{left:`${organ.x}%`,top:`${organ.y}%`}} onClick={() => setSelected(key as keyof typeof organs)} aria-label={`Explore ${organ.label}`} aria-pressed={selected === key} />)}
    </div>
    <div className="anatomy-info"><span className="icon-box coral"><Heart size={21}/></span><div><span className="micro">EXPLORE YOUR ANATOMY</span><strong>{organs[selected].label}</strong><p>{organs[selected].detail}</p></div></div>
    <div className="anatomy-controls"><label htmlFor="body-angle">Rotate view</label><input id="body-angle" type="range" min="-35" max="35" value={angle} onChange={e => setAngle(Number(e.target.value))}/><button className="icon-button" aria-label="Reset anatomy rotation" onClick={() => setAngle(0)}><RotateCcw size={15}/></button></div>
    <span className="anatomy-caption"><Info size={12}/> Stylized illustration · Educational only</span>
  </div>
}
