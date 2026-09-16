import { groupInfo, shortFault } from "../../lib/taxonomy.js";

// Compact 6-group taxonomy panel. Represented types are live chips; missing
// types are dimmed placeholders (never fabricated).
export function TaxonomyPanel({ meta, selectedType, selectedGroup, onSelectType, onSelectGroup }) {
  if (!meta) return null;
  const { groups, faultTaxonomy } = meta;

  return (
    <section className="panel taxonomy">
      <header className="panel__head">
        <h3 className="panel__title">Fault taxonomy</h3>
        <span className="panel__hint">16/20 represented in dataset</span>
      </header>
      <div className="taxonomy__grid">
        {groups.map((g) => {
          const info = groupInfo(g.id);
          const allMissing = g.represented === 0;
          return (
            <div className="taxonomy__group" key={g.id}>
              <button
                className={`taxonomy__group-head ${selectedGroup === g.id ? "is-active" : ""}`}
                onClick={() => onSelectGroup(selectedGroup === g.id ? "ALL" : g.id)}
                style={{ "--gc": info.color }}
              >
                <span className="taxonomy__gdot" />
                <span className="taxonomy__gname">{info.label}</span>
                <span className="taxonomy__gcount">
                  {g.represented}/{g.total}
                </span>
              </button>
              <div className="taxonomy__types">
                {faultTaxonomy
                  .filter((t) => t.group === g.id)
                  .map((t) => (
                    <button
                      key={t.type}
                      className={`taxonomy__type ${t.represented ? "" : "is-missing"} ${
                        selectedType === t.type ? "is-selected" : ""
                      }`}
                      onClick={() => t.represented && onSelectType(selectedType === t.type ? "ALL" : t.type)}
                      title={t.represented ? `${t.type} · ${t.count} injected` : `${t.type} · not present in dataset`}
                    >
                      <span className="taxonomy__tdot" style={{ "--gc": info.color }} />
                      {shortFault(t.type)}
                      {t.represented ? <em className="taxonomy__tcount">{t.count}</em> : <em className="taxonomy__missing">absent</em>}
                    </button>
                  ))}
              </div>
              {allMissing && <span className="taxonomy__absent-line">no trajectories in dataset</span>}
            </div>
          );
        })}
      </div>
    </section>
  );
}