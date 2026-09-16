import { useEffect } from "react";
import { Loader2, TriangleAlert } from "lucide-react";
import { StoreProvider, useStore } from "./data/store.jsx";
import { TopBar } from "./components/TopBar.jsx";
import ListView from "./components/List/ListView.jsx";
import DetailView from "./components/detail/DetailView.jsx";
import { useRoute, navigate } from "./hooks.js";

export function LoadingScreen() {
  return (
    <div className="boot">
      <div className="boot__mark" />
      <Loader2 size={18} className="boot__spin" />
      <div className="boot__text">assembling dataset index…</div>
      <div className="boot__progress">
        <span />
      </div>
    </div>
  );
}

function ErrorScreen({ error }) {
  return (
    <div className="boot">
      <TriangleAlert size={20} className="boot__err" />
      <div className="boot__text">failed to load dataset assets</div>
      <code className="boot__code">{String(error?.message ?? error)}</code>
    </div>
  );
}

function Shell() {
  const route = useRoute();
  const { status, error, data } = useStore();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [route.name, route.id]);

  if (status === "loading") return <LoadingScreen />;
  if (status === "error" || !data) return <ErrorScreen error={error} />;

  const openDemo = () => {
    const id = data.meta?.demoIds?.[0];
    if (id) navigate({ name: "detail", id });
  };

  const runGlobalSearch = (q) => {
    navigate({ name: "list", params: { q } });
  };

  return (
    <div className="app">
      <TopBar
        onSearch={runGlobalSearch}
        onDemo={openDemo}
        counts={data.meta.counts}
      />
      <main className="app__main">
        {route.name === "detail" ? (
          <DetailView id={route.id} key={route.id} />
        ) : (
          <ListView route={route} />
        )}
      </main>
      <footer className="app__foot">
        <span>AgentFault Console</span>
        <span className="app__foot-sep">·</span>
        <span>read-only visualization of the existing dataset</span>
        <span className="app__foot-sep">·</span>
        <span className="mono">
          {data.meta.counts.baseline} baseline · {data.meta.counts.injected} injected ·{" "}
          {data.meta.faultTaxonomy.filter((t) => t.represented).length}/20 fault types
        </span>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <StoreProvider>
      <Shell />
    </StoreProvider>
  );
}