import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { Catalogue, Dashboard, Loans, Members } from "./views.jsx";

const TABS = [
  { id: "dashboard", label: "Dashboard", icon: "◧" },
  { id: "catalogue", label: "Catalogue", icon: "▤" },
  { id: "loans", label: "Loans", icon: "⇄" },
  { id: "members", label: "Members", icon: "◉" },
];

export default function App() {
  const [tab, setTab] = useState(() => location.hash.slice(1) || "dashboard");
  const [info, setInfo] = useState(null);
  const [backendDown, setBackendDown] = useState(false);
  const [toast, setToast] = useState(null);
  const [version, setVersion] = useState(0); // bump to refetch every view

  useEffect(() => {
    api("/info")
      .then((i) => { setInfo(i); setBackendDown(false); })
      .catch(() => setBackendDown(true));
  }, [version]);

  useEffect(() => {
    const onHash = () => setTab(location.hash.slice(1) || "dashboard");
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);

  const notify = useCallback((msg, kind = "ok") => {
    setToast({ msg, kind, at: Date.now() });
  }, []);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 4000);
    return () => clearTimeout(t);
  }, [toast]);

  const refresh = useCallback(() => setVersion((v) => v + 1), []);
  const props = { notify, refresh, version, rules: info?.rules };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo" aria-hidden>❚❚⟋</span>
          <div>
            <strong>ShelfLend</strong>
            <small>Library lending</small>
          </div>
        </div>
        <nav>
          {TABS.map((t) => (
            <a key={t.id} href={`#${t.id}`} className={tab === t.id ? "active" : ""}>
              <span aria-hidden>{t.icon}</span>{t.label}
            </a>
          ))}
        </nav>
        <div className="build">
          {info ? (
            <>
              <span className="dot ok" /> build <code>{info.version}</code>
              <br />pod <code title={info.pod}>{info.pod}</code>
            </>
          ) : (
            <><span className="dot bad" /> backend offline</>
          )}
        </div>
      </aside>

      <main>
        {backendDown && (
          <div className="banner">
            Can't reach the ShelfLend API. Data below may be stale.{" "}
            <button className="link" onClick={refresh}>Retry</button>
          </div>
        )}
        {tab === "dashboard" && <Dashboard {...props} />}
        {tab === "catalogue" && <Catalogue {...props} />}
        {tab === "loans" && <Loans {...props} />}
        {tab === "members" && <Members {...props} />}
      </main>

      {toast && <div key={toast.at} className={`toast ${toast.kind}`} role="status">{toast.msg}</div>}
    </div>
  );
}
