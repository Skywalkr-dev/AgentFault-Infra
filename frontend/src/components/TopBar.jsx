import { useState } from "react";
import { Search, Play, Bug, Database, ChevronRight } from "lucide-react";
import { navigate } from "../hooks.js";

export function Brand({ onClick }) {
  return (
    <button className="brand" onClick={onClick} title="Back to trajectory list">
      <span className="brand__mark">
        <Bug size={16} />
      </span>
      <span className="brand__text">
        <span className="brand__name">AgentFault</span>
        <span className="brand__sub">trajectory console</span>
      </span>
    </button>
  );
}

export function TopBar({
  onSearch,
  onDemo,
  counts,
  children,
}) {
  const [q, setQ] = useState("");
  const submit = (e) => {
    e.preventDefault();
    onSearch(q.trim());
  };

  return (
    <header className="topbar">
      <div className="topbar__left">
        <Brand onClick={() => navigate("/")} />
        {children}
      </div>

      <form className="topbar__search" onSubmit={submit}>
        <Search size={14} className="topbar__search-icon" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search trajectories, tasks, fault types…"
          aria-label="Global trajectory search"
        />
        <kbd className="topbar__kbd">↵</kbd>
      </form>

      {counts && (
        <span className="topbar__status" title="Dataset load status">
          <Database size={13} />
          <span>
            {counts.baseline} base · {counts.injected} inj
          </span>
        </span>
      )}

      <button className="btn btn--demo" onClick={onDemo} title="Open a curated injected trajectory">
        <Play size={13} />
        Demo trajectory
      </button>
    </header>
  );
}

export function Breadcrumb({ items }) {
  if (!items || items.length === 0) return null;
  return (
    <nav className="breadcrumb">
      {items.map((it, i) => (
        <span className="breadcrumb__item" key={i}>
          {i > 0 && <ChevronRight size={12} className="breadcrumb__sep" />}
          {it.to ? (
            <a onClick={(e) => { e.preventDefault(); navigate(it.to); }} href={it.to}>
              {it.label}
            </a>
          ) : (
            <span className="breadcrumb__cur">{it.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}