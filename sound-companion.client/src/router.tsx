import { createBrowserRouter, Navigate } from 'react-router'
import { AppShell } from './components/AppShell'
import { HomePage } from './pages/HomePage'
import { MonitoringPage } from './pages/MonitoringPage'

export const router = createBrowserRouter([
  {
    element: <AppShell />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/monitoring', element: <MonitoringPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
