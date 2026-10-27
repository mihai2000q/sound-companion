import { createBrowserRouter, Navigate } from 'react-router'
import { HealthPage } from './pages/HealthPage'
import { HomePage } from './pages/HomePage'
import { MonitoringPage } from './pages/MonitoringPage'

export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/monitoring', element: <MonitoringPage /> },
  { path: '/health', element: <HealthPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])
