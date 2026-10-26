import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { Layout } from './components/Layout'
import { About } from './pages/About'
import { Describe } from './pages/Describe'
import { Evaluation } from './pages/Evaluation'
import { Home } from './pages/Home'
import { RunPage, SamplePage } from './pages/ResultPage'
import './styles.css'

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <Home /> },
      { path: '/describe', element: <Describe /> },
      { path: '/samples/:id', element: <SamplePage /> },
      { path: '/runs/:id', element: <RunPage /> },
      { path: '/evaluation', element: <Evaluation /> },
      { path: '/about', element: <About /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
