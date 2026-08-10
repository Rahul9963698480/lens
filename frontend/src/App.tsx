import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'

import { LandingPage } from '@/pages/landing-page'
import { TablesPage } from '@/pages/tables-page'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/table/:projectId" element={<TablesPage />} />
      </Routes>
      <Toaster richColors closeButton position="top-center" />
    </BrowserRouter>
  )
}

export default App
