// ═══════════════════════════════════════════════════════════════════════
// TFAEL-OMNI — Entry Point
// Provider stack: Auth → App → Toast → App component
// ═══════════════════════════════════════════════════════════════════════

import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { AuthProvider } from '@/context/AuthContext';
import { AppProvider } from '@/context/AppContext';
import { ToastProvider } from '@/hooks/useToast';
import App from './App';
import '@/styles/globals.css';
import '@/styles/tokens.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <AppProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </AppProvider>
    </AuthProvider>
  </StrictMode>
);
