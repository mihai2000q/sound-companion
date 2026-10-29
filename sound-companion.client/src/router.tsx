import { createBrowserRouter, Navigate } from 'react-router'
import { HomePage } from './pages/HomePage'
import { MonitoringPage } from './pages/MonitoringPage'

export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/monitoring', element: <MonitoringPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])
