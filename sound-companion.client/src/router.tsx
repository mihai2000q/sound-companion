import { createBrowserRouter, Navigate } from 'react-router'
import { HealthPage } from './pages/HealthPage'
import { HomePage } from './pages/HomePage'

export const router = createBrowserRouter([
  { path: '/', element: <HomePage /> },
  { path: '/health', element: <HealthPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])
