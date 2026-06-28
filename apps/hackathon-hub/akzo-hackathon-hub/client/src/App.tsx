import { createBrowserRouter, RouterProvider, NavLink, Outlet } from 'react-router';
import type { ComponentType } from 'react';
import {
  LayoutDashboard,
  Trophy,
  Target,
  BookOpen,
  UserPlus,
  Users,
  Upload,
  Gavel,
  Sparkles,
  Library,
  FileText,
  Wrench,
  Hammer,
  MonitorPlay,
} from 'lucide-react';
import { cn } from './lib/utils';

import OverviewPage from './pages/Overview';
import ChallengesPage from './pages/Challenges';
import GuidePage from './pages/Guide';
import HowToRunPage from './pages/HowToRun';
import BuildSetupPage from './pages/BuildSetup';
import DemosPage from './pages/Demos';
import RegisterPage from './pages/Register';
import TeamsPage from './pages/Teams';
import SubmitPage from './pages/Submit';
import JudgePage from './pages/Judge';
import LeaderboardPage from './pages/Leaderboard';
import LivePage from './pages/Live';
import ResourcesPage from './pages/Resources';
import MaterialsPage from './pages/Materials';
import OrganizerPage from './pages/Organizer';

interface NavItem {
  to: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  end?: boolean;
}
interface NavGroup {
  heading?: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    items: [
      { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
      { to: '/challenges', label: 'Challenges', icon: Target },
      { to: '/how-to-run', label: 'How to run it', icon: BookOpen },
      { to: '/build-setup', label: 'Build setup', icon: Hammer },
      { to: '/demos', label: 'Demos', icon: MonitorPlay },
    ],
  },
  {
    heading: 'Participate',
    items: [
      { to: '/register', label: 'Register', icon: UserPlus },
      { to: '/teams', label: 'Teams', icon: Users },
      { to: '/submit', label: 'Submit', icon: Upload },
    ],
  },
  {
    heading: 'Judging',
    items: [
      { to: '/judge', label: 'Judge', icon: Gavel },
      { to: '/leaderboard', label: 'Leaderboard', icon: Trophy },
    ],
  },
  {
    heading: 'Live',
    items: [{ to: '/live', label: 'Try it live', icon: Sparkles }],
  },
  {
    heading: 'Resources',
    items: [
      { to: '/resources', label: 'Resources', icon: Library },
      { to: '/materials', label: 'Materials', icon: FileText },
    ],
  },
  {
    heading: 'Organizer',
    items: [{ to: '/organizer', label: 'Organizer', icon: Wrench }],
  },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    'flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors',
    isActive
      ? 'bg-sidebar-accent text-sidebar-accent-foreground'
      : 'text-muted-foreground hover:bg-sidebar-accent/60 hover:text-foreground'
  );

function Sidebar() {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-foreground">Hackathon-in-the-Box</div>
          <div className="text-xs text-muted-foreground">AkzoNobel × Databricks</div>
        </div>
      </div>
      <nav className="flex-1 space-y-5 overflow-y-auto px-3 pb-6">
        {NAV.map((group, i) => (
          <div key={i}>
            {group.heading && (
              <div className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground/70">
                {group.heading}
              </div>
            )}
            <div className="space-y-0.5">
              {group.items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end} className={linkClass}>
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
      <div className="border-t border-sidebar-border px-5 py-3 text-[11px] text-muted-foreground">
        Built on Databricks AppKit
      </div>
    </aside>
  );
}

function Layout() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <main className="flex-1 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}

const router = createBrowserRouter([
  {
    element: <Layout />,
    children: [
      { path: '/', element: <OverviewPage /> },
      { path: '/challenges', element: <ChallengesPage /> },
      { path: '/guide/:track', element: <GuidePage /> },
      { path: '/how-to-run', element: <HowToRunPage /> },
      { path: '/build-setup', element: <BuildSetupPage /> },
      { path: '/demos', element: <DemosPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/teams', element: <TeamsPage /> },
      { path: '/submit', element: <SubmitPage /> },
      { path: '/judge', element: <JudgePage /> },
      { path: '/leaderboard', element: <LeaderboardPage /> },
      { path: '/live', element: <LivePage /> },
      { path: '/resources', element: <ResourcesPage /> },
      { path: '/materials', element: <MaterialsPage /> },
      { path: '/organizer', element: <OrganizerPage /> },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
