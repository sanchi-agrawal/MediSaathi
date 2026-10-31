import { useLanguage } from '../lib/language'
export function AnatomyFallback({ loading = false }: { loading?: boolean }) {
  const { t } = useLanguage()
  return <div className="anatomy-static" role="status"><svg viewBox="0 0 200 350" aria-hidden="true"><g fill="#278dda33" stroke="#79c9ee"><ellipse cx="100" cy="40" rx="24" ry="30"/><path d="M87 70 L65 85 42 190 53 195 77 120 78 205 68 330 87 330 100 220 113 330 132 330 122 205 123 120 147 195 158 190 135 85 113 70Z"/><path d="M93 99 Q64 88 78 155 L94 148Z M107 99 Q136 88 122 155 L106 148Z" fill="#278dda88"/><path d="M99 130 C83 110 83 141 102 151 122 132 112 116 99 130" fill="#ff5967"/></g></svg><p>{t(loading ? 'Loading anatomy…' : '3D unavailable. Please reload to try again.')}</p></div>
}
