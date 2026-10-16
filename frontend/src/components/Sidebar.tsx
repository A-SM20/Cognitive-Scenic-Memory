import { type PageId } from '../types';

interface NavItem {
  id: PageId;
  label: string;
  icon: string;
  enabled: boolean;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'overview', label: 'Overview', icon: '◉', enabled: true },
  { id: 'perception', label: 'Perception', icon: '◎', enabled: true },
  { id: 'memory', label: 'Memory', icon: '◈', enabled: true },
  { id: 'scene-graph', label: 'Scene Graph', icon: '◇', enabled: true },
  { id: 'changes', label: 'Changes', icon: '△', enabled: true },
  { id: 'timeline', label: 'Timeline', icon: '▬', enabled: true },
  { id: 'query', label: 'Chatbot & Query', icon: '💬', enabled: true },
  { id: 'settings', label: 'Settings', icon: '⚙', enabled: true },
];

interface SidebarProps {
  currentPage: PageId;
  onNavigate: (page: PageId) => void;
  systemStatus?: 'ok' | 'degraded' | 'offline';
}

export default function Sidebar({ currentPage, onNavigate, systemStatus = 'offline' }: SidebarProps) {
  const statusColor =
    systemStatus === 'ok'
      ? 'bg-status-active'
      : systemStatus === 'degraded'
        ? 'bg-status-warning'
        : 'bg-status-danger';

  return (
    <aside className="w-56 h-screen bg-bg-secondary border-r border-border flex flex-col fixed left-0 top-0 z-50">
      {/* Logo & Title */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center gap-2 mb-1">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent-cyan to-accent-emerald flex items-center justify-center text-bg-primary font-bold text-sm">
            CS
          </div>
          <div>
            <h1 className="text-sm font-semibold text-text-primary leading-tight">Cognitive</h1>
            <h1 className="text-sm font-semibold text-accent-cyan leading-tight">Scene Memory</h1>
          </div>
        </div>
        <div className="flex items-center gap-1.5 mt-2">
          <div className={`w-1.5 h-1.5 rounded-full ${statusColor} status-pulse`} />
          <span className="text-xs text-text-muted font-mono capitalize">{systemStatus}</span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        <div className="px-2 mb-2">
          <span className="text-[10px] font-semibold text-text-muted uppercase tracking-wider">Navigation</span>
        </div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => item.enabled && onNavigate(item.id)}
            disabled={!item.enabled}
            className={`
              w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left
              transition-all duration-150 group relative
              ${
                currentPage === item.id
                  ? 'bg-accent-cyan/10 text-accent-cyan border border-accent-cyan/20'
                  : item.enabled
                    ? 'text-text-secondary hover:bg-bg-card hover:text-text-primary border border-transparent'
                    : 'text-text-muted/40 cursor-not-allowed border border-transparent'
              }
            `}
          >
            <span className="text-base w-5 text-center">{item.icon}</span>
            <span className="text-sm font-medium">{item.label}</span>
            {item.badge && !item.enabled && (
              <span className="ml-auto text-[9px] px-1.5 py-0.5 rounded bg-bg-card text-text-muted font-mono">
                {item.badge}
              </span>
            )}
            {currentPage === item.id && (
              <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-accent-cyan rounded-r" />
            )}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-3 border-t border-border">
        <div className="text-[10px] text-text-muted font-mono leading-relaxed">
          <div>v0.2.0 · Phase 2</div>
          <div className="text-accent-cyan/50">SENSE → DETECT → UNDERSTAND</div>
        </div>
      </div>
    </aside>
  );
}
