export function Badge({ children, tone = "slate", className = "", title }) {
  return (
    <span className={`badge badge--${tone} ${className}`} title={title}>
      {children}
    </span>
  );
}

export function Dot({ color, className = "" }) {
  return <span className={`dot ${className}`} style={{ "--dot-c": color }} />;
}