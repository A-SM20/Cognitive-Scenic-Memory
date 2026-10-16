import { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Overview from './pages/Overview';
import Perception from './pages/Perception';
import Memory from './pages/Memory';
import SceneGraph from './pages/SceneGraph';
import Changes from './pages/Changes';
import Timeline from './pages/Timeline';
import Query from './pages/Query';
import Settings from './pages/Settings';
import { getHealth } from './services/api';
import type { PageId } from './types';

export default function App() {
  const [currentPage, setCurrentPage] = useState<PageId>('overview');
  const [systemStatus, setSystemStatus] = useState<'ok' | 'degraded' | 'offline'>('offline');

  // Poll system health
  useEffect(() => {
    async function checkHealth() {
      try {
        const health = await getHealth();
        setSystemStatus(health.status as 'ok' | 'degraded' | 'offline');
      } catch {
        setSystemStatus('offline');
      }
    }

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const renderPage = () => {
    switch (currentPage) {
      case 'overview':
        return <Overview />;
      case 'perception':
        return <Perception />;
      case 'memory':
        return <Memory />;
      case 'scene-graph':
        return <SceneGraph />;
      case 'changes':
        return <Changes />;
      case 'timeline':
        return <Timeline />;
      case 'query':
        return <Query />;
      case 'settings':
        return <Settings />;
      default:
        return (
          <div className="flex items-center justify-center h-64">
            <div className="glass-panel p-8 text-center">
              <h3 className="text-lg font-semibold text-text-primary mb-2">
                {currentPage.replace('-', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
              </h3>
              <p className="text-sm text-text-muted">
                This module will be available in a future phase.
              </p>
            </div>
          </div>
        );
    }
  };

  return (
    <div className="flex min-h-screen bg-bg-primary">
      <Sidebar
        currentPage={currentPage}
        onNavigate={setCurrentPage}
        systemStatus={systemStatus}
      />

      {/* Main content area — offset by sidebar width */}
      <main className="flex-1 ml-56 p-6 max-w-6xl">
        {renderPage()}
      </main>
    </div>
  );
}

