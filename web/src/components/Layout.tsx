import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { api } from '../api'

export function Layout() {
  const [host, setHost] = useState('')
  const [provider, setProvider] = useState('')
  useEffect(() => {
    api
      .health()
      .then((h) => {
        setHost(h.host ?? '')
        setProvider(h.provider)
      })
      .catch(() => undefined)
  }, [])

  // A judge link like /?judge=1&code=XYZ unlocks the reserved judging lane, then the code leaves the address bar.
  useEffect(() => {
    const url = new URL(window.location.href)
    const code = url.searchParams.get('code')
    if (!code) return
    url.searchParams.delete('code')
    window.history.replaceState(null, '', url.pathname + (url.search ? url.search : '') + url.hash)
    api.judge(code).catch(() => undefined)
  }, [])

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <div className="shell">
        <header className="site-header">
          <NavLink to="/" className="wordmark" aria-label="Unsaid, home">
            Unsaid<span className="dot" aria-hidden="true" />
          </NavLink>
          <nav className="nav" aria-label="Main">
            <NavLink to="/" end>
              Hear it
            </NavLink>
            <NavLink to="/describe">Describe a lecture</NavLink>
            <NavLink to="/evaluation">Evaluation</NavLink>
            <NavLink to="/about">How it works</NavLink>
          </nav>
        </header>
        <main id="main" tabIndex={-1}>
          <Outlet />
        </main>
        <footer className="site-footer">
          <span>
            {provider === 'tokenfactory'
              ? 'Unsaid runs NVIDIA Nemotron models on Nebius Token Factory. '
              : "Unsaid is written for NVIDIA Nemotron models on Nebius Token Factory; the runs here used the same models on NVIDIA's API catalog. "}
            NVIDIA Parakeet speech recognition runs{host ? ` on ${host}` : ' on CPU'}. Context lookups by Tavily.
          </span>
          <span>
            Descriptions are drafts with checks, not a replacement for professional describers. Uploads are deleted
            after 24 hours. Open source under the MIT license.
          </span>
        </footer>
      </div>
    </>
  )
}
