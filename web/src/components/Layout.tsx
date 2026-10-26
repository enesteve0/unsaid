import { NavLink, Outlet } from 'react-router-dom'

export function Layout() {
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
            Unsaid runs NVIDIA Nemotron models on Nebius Token Factory and NVIDIA Parakeet speech recognition on Nebius
            AI Cloud. Context lookups by Tavily.
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
