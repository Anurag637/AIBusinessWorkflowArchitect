'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { api, HealthStatus } from '@/lib/api';

const navItems = [
  { href: '/?tab=orchestrator', icon: '🧠', label: 'Autonomous Agents' },
  { href: '/', icon: '📊', label: 'Dashboard & Studio' },
  { href: '/?tab=approvals', icon: '✅', label: 'Approvals' },
  { href: '/?tab=knowledge', icon: '📚', label: 'Knowledge Base' },
  { href: '/?tab=audit', icon: '📋', label: 'Audit Logs' },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isOnline, setIsOnline] = useState<boolean>(false);

  const checkHealth = async () => {
    try {
      const res = await api.getHealth();
      if (res.status === 'success' && res.data) {
        setHealth(res.data);
        setIsOnline(true);
      } else {
        setIsOnline(false);
      }
    } catch {
      setIsOnline(false);
    }
  };

  useEffect(() => {
    const startupTimer = window.setTimeout(() => {
      void checkHealth();
    }, 0);

    const interval = setInterval(() => {
      void checkHealth();
    }, 5000);

    return () => {
      window.clearTimeout(startupTimer);
      clearInterval(interval);
    };
  }, []);

  return (
    <nav className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-icon">🤖</div>
        <div>
          <div className="sidebar-logo-text">Workflow Architect</div>
          <div className="sidebar-logo-subtitle">AI-Powered</div>
        </div>
      </div>

      <div className="sidebar-nav">
        {navItems.map((item) => (
          <Link
            key={item.label}
            href={item.href}
            className={`nav-item ${pathname === '/' && item.href === '/' ? 'active' : ''}`}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </Link>
        ))}
      </div>

      <div className="connection-status" id="backend-status">
        <span
          className={`connection-dot ${isOnline ? 'connected' : 'disconnected'}`}
          id="status-dot"
          style={{ background: isOnline ? '#00b894' : '#ff7675' }}
        ></span>
        <span id="status-text" style={{ fontSize: '12px' }}>
          {isOnline ? `Backend Online (v${health?.version || '1.0.0'})` : 'Connecting...'}
        </span>
      </div>
    </nav>
  );
}
