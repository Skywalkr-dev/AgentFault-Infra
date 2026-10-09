import { Gauge, ShieldCheck, ShieldAlert, Check, X } from "lucide-react";
import { Badge } from "../shared/Badge.jsx";
import { humanize } from "../../lib/taxonomy.js";

function ScoreBar({ label, score, tone }) {
  const raw = Number(score);
  const pct = Math.max(0, Math.min(1, Number.isFinite(raw) ? raw : 0)) * 100;

  return (
    <div className="scorebar">
      <span className="scorebar__label">{label}</span>
      <div className="scorebar__track">
        <div
          className={`scorebar__fill scorebar__fill--${tone}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`scorebar__value scorebar__value--${tone}`}>
        {Number.isFinite(raw) ? raw.toFixed(2) : "—"}
      </span>
    </div>
  );
}

function CheckChip({ check }) {
  const tone = check.passed ? "green" : "red";

  return (
    <span className={`checkchip checkchip--${tone}`} title={`weight ${check.weight}`}>
      {check.passed ? <Check size={11} /> : <X size={11} />}
      <span className="checkchip__name">{humanize(check.name)}</span>
      <span className="checkchip__w">{check.weight}</span>
    </span>
  );
}

export function ReplayPanel({ replay, source }) {
  if (!replay) return null;

  const {
    baselineScore = 1,
    injectedScore = 0,
    successDelta = 0,
    failedChecks = [],
    checks = [],
    deterministic = {},
  } = replay;

  const passed = checks.filter((c) => c.passed).length;
  const delta = Number(successDelta) || 0;

  return (
    <section className="detail-section replay">
      <header className="detail-section__head">
        <span className="detail-section__title">
          <Gauge size={15} /> Replay comparison
        </span>
        <Badge tone={deterministic.baseline ? "green" : "slate"} title="baseline replays identically every run">
          <ShieldCheck size={11} /> baseline {deterministic.baseline ? "deterministic" : "drifted"}
        </Badge>
        {!deterministic.injected && (
          <Badge tone="violet" title="injected replay diverges from the recording">
            <ShieldAlert size={11} /> replay diverges
          </Badge>
        )}
        <span className="detail-section__hint">
          {source === "api" ? "live dashboard API" : "bundled replay index"}
        </span>
      </header>

      <div className="replay__grid">
        <div className="replay__scores">
          <ScoreBar label="baseline" score={baselineScore} tone="green" />
          <ScoreBar label="injected" score={injectedScore} tone={injectedScore >= 1 ? "green" : "red"} />

          <div className={`replay__delta ${delta > 0 ? "is-drop" : "is-flat"}`}>
            <span className="replay__delta-value">
              Δ {delta.toFixed(2)}
            </span>
            <span className="replay__delta-label">
              {delta > 0 ? "success-score drop after replay" : "no outcome-level impact"}
            </span>
          </div>

          <p className="replay__note">
            Weighted success score recomputed from mocked tool calls and a
            temperature-0 replay of every step.
          </p>
        </div>

        <div className="replay__checks">
          <div className="replay__checks-head">
            success checks
            <span className="replay__checks-count">
              {passed}/{checks.length} passed
            </span>
          </div>

          <div className="replay__chips">
            {checks.map((check) => (
              <CheckChip key={check.name} check={check} />
            ))}
          </div>

          {failedChecks.length > 0 ? (
            <ul className="replay__failed">
              {failedChecks.map((check) => (
                <li key={check.name}>
                  <span className="replay__failed-name">{humanize(check.name)}</span>
                  <span className="replay__failed-w">−{check.weight}</span>
                  <span className="replay__failed-reason">{check.reason}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="replay__ok">All success checks passed — the injected record still satisfies every criterion.</p>
          )}
        </div>
      </div>
    </section>
  );
}
