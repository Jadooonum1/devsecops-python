import { useEffect, useState } from "react";
import { api, dateLabel, rupees, timeAgo } from "./api.js";

function useLoad(path, version) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true }));
    api(path)
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((e) => live && setState({ data: null, error: e.message, loading: false }));
    return () => { live = false; };
  }, [path, version]);
  return state;
}

function Status({ state, empty, children }) {
  if (state.loading && !state.data) return <div className="placeholder">Loading…</div>;
  if (state.error) return <div className="placeholder error">Couldn't load: {state.error}</div>;
  if (Array.isArray(state.data) && state.data.length === 0) return <div className="placeholder">{empty}</div>;
  return children;
}

async function run(action, notify, refresh, okMsg) {
  try {
    const result = await action();
    notify(typeof okMsg === "function" ? okMsg(result) : okMsg);
    refresh();
    return true;
  } catch (e) {
    notify(e.message, "err");
    return false;
  }
}

const Pill = ({ value }) => <span className={`pill ${value}`}>{value.replace("_", " ")}</span>;

// --------------------------------------------------------------------------- dashboard

export function Dashboard({ version }) {
  const stats = useLoad("/stats", version);
  const overdue = useLoad("/loans?status=overdue", version);
  const feed = useLoad("/activity?limit=12", version);
  const s = stats.data;

  return (
    <>
      <header className="page-head">
        <h1>Today at the desk</h1>
        <p>Live from the ShelfLend API · counts update after every loan.</p>
      </header>

      <section className="tiles">
        <Tile label="Titles" value={s?.books} />
        <Tile label="Copies on shelf" value={s?.copies.available} />
        <Tile label="On loan" value={s?.active_loans} />
        <Tile label="Overdue" value={s?.overdue_loans} warn={s?.overdue_loans > 0} />
        <Tile label="Fines outstanding" value={s ? rupees(s.fines_outstanding) : undefined} />
      </section>

      <div className="two-col">
        <section className="card">
          <h2>Overdue loans</h2>
          <Status state={overdue} empty="Nothing overdue. 🎉">
            <ul className="rows">
              {overdue.data?.map((l) => (
                <li key={l.id}>
                  <div>
                    <strong>{l.book_title}</strong>
                    <small>{l.member_name} · {l.barcode}</small>
                  </div>
                  <span className="pill overdue">{l.days_overdue} d late</span>
                </li>
              ))}
            </ul>
          </Status>
        </section>

        <section className="card">
          <h2>Activity</h2>
          <Status state={feed} empty="No activity yet.">
            <ul className="feed">
              {feed.data?.map((e) => (
                <li key={e.id}>
                  <span className={`badge ${e.action}`}>{e.action.replace("_", " ")}</span>
                  <span className="feed-text">{e.detail}</span>
                  <time>{timeAgo(e.created_at)}</time>
                </li>
              ))}
            </ul>
          </Status>
        </section>
      </div>
    </>
  );
}

function Tile({ label, value, warn }) {
  return (
    <div className={`tile ${warn ? "warn" : ""}`}>
      <span>{label}</span>
      <strong>{value ?? "–"}</strong>
    </div>
  );
}

// --------------------------------------------------------------------------- catalogue

const emptyBook = { isbn: "", title: "", author: "", genre: "", published_year: "" };

export function Catalogue({ version, notify, refresh }) {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const books = useLoad(`/books${query ? `?q=${encodeURIComponent(query)}` : ""}`, version);
  const [form, setForm] = useState(emptyBook);
  const [editing, setEditing] = useState(null);
  const [open, setOpen] = useState(null);

  useEffect(() => {
    const t = setTimeout(() => setQuery(q.trim()), 250);
    return () => clearTimeout(t);
  }, [q]);

  const submit = async (e) => {
    e.preventDefault();
    const body = { ...form, genre: form.genre || null, published_year: form.published_year ? Number(form.published_year) : null };
    const ok = await run(
      () => (editing ? api(`/books/${editing}`, { method: "PUT", body }) : api("/books", { method: "POST", body })),
      notify, refresh, (b) => `${editing ? "Updated" : "Added"} “${b.title}”`,
    );
    if (ok) { setForm(emptyBook); setEditing(null); }
  };

  const edit = (b) => {
    setEditing(b.id);
    setForm({ isbn: b.isbn, title: b.title, author: b.author, genre: b.genre ?? "", published_year: b.published_year ?? "" });
    scrollTo({ top: 0, behavior: "smooth" });
  };

  const remove = (b) => run(() => api(`/books/${b.id}`, { method: "DELETE" }), notify, refresh, `Removed “${b.title}”`);

  return (
    <>
      <header className="page-head">
        <h1>Catalogue</h1>
        <p>Titles and the physical copies on the shelves.</p>
      </header>

      <form className="card form-grid" onSubmit={submit}>
        <h2>{editing ? "Edit book" : "Add a book"}</h2>
        <label>ISBN<input required value={form.isbn} onChange={(e) => setForm({ ...form, isbn: e.target.value })} placeholder="978-0-13-468599-1" /></label>
        <label className="wide">Title<input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
        <label>Author<input required value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} /></label>
        <label>Genre<input value={form.genre} onChange={(e) => setForm({ ...form, genre: e.target.value })} /></label>
        <label>Year<input type="number" min="1400" max="2100" value={form.published_year} onChange={(e) => setForm({ ...form, published_year: e.target.value })} /></label>
        <div className="actions">
          {editing && <button type="button" className="ghost" onClick={() => { setEditing(null); setForm(emptyBook); }}>Cancel</button>}
          <button type="submit">{editing ? "Save changes" : "Add book"}</button>
        </div>
      </form>

      <div className="toolbar">
        <input type="search" placeholder="Search title, author or ISBN…" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search books" />
      </div>

      <Status state={books} empty={query ? "No books match that search." : "The catalogue is empty. Add a book above."}>
        <div className="table">
          <div className="thead"><span>Title</span><span>Author</span><span>ISBN</span><span>Copies</span><span /></div>
          {books.data?.map((b) => (
            <div key={b.id} className="trow-group">
              <div className="trow">
                <span data-label="Title"><strong>{b.title}</strong>{b.genre && <small> · {b.genre}</small>}</span>
                <span data-label="Author">{b.author}</span>
                <span data-label="ISBN"><code>{b.isbn}</code></span>
                <span data-label="Copies">{b.available_copies} / {b.total_copies} available</span>
                <span className="row-actions">
                  <button className="ghost" onClick={() => setOpen(open === b.id ? null : b.id)}>{open === b.id ? "Hide copies" : "Copies"}</button>
                  <button className="ghost" onClick={() => edit(b)}>Edit</button>
                  <button className="ghost danger" onClick={() => remove(b)}>Delete</button>
                </span>
              </div>
              {open === b.id && <Copies book={b} version={version} notify={notify} refresh={refresh} />}
            </div>
          ))}
        </div>
      </Status>
    </>
  );
}

function Copies({ book, version, notify, refresh }) {
  const copies = useLoad(`/copies?book_id=${book.id}`, version);
  const [barcode, setBarcode] = useState("");
  const [shelf, setShelf] = useState("");

  const add = async (e) => {
    e.preventDefault();
    const ok = await run(
      () => api(`/books/${book.id}/copies`, { method: "POST", body: { barcode: barcode.toUpperCase(), shelf: shelf || null } }),
      notify, refresh, `Copy ${barcode.toUpperCase()} added`,
    );
    if (ok) { setBarcode(""); setShelf(""); }
  };
  const setStatus = (c, status) =>
    run(() => api(`/copies/${c.id}`, { method: "PATCH", body: { status } }), notify, refresh, `${c.barcode} → ${status}`);

  return (
    <div className="copies">
      <Status state={copies} empty="No copies yet.">
        <ul>
          {copies.data?.map((c) => (
            <li key={c.id}>
              <code>{c.barcode}</code>
              <small>{c.shelf ? `shelf ${c.shelf}` : "no shelf"}</small>
              <Pill value={c.status} />
              {c.status === "available" && <button className="link" onClick={() => setStatus(c, "maintenance")}>send to repair</button>}
              {c.status === "maintenance" && <button className="link" onClick={() => setStatus(c, "available")}>back on shelf</button>}
            </li>
          ))}
        </ul>
      </Status>
      <form className="inline" onSubmit={add}>
        <input required placeholder="Barcode e.g. LIB-0042" value={barcode} onChange={(e) => setBarcode(e.target.value)} />
        <input placeholder="Shelf" value={shelf} onChange={(e) => setShelf(e.target.value)} />
        <button type="submit">Add copy</button>
      </form>
    </div>
  );
}

// --------------------------------------------------------------------------- loans

const FILTERS = ["active", "overdue", "returned", "lost"];

export function Loans({ version, notify, refresh, rules }) {
  const [filter, setFilter] = useState("active");
  const loans = useLoad(`/loans?status=${filter}`, version);
  const copies = useLoad("/copies?status=available", version);
  const members = useLoad("/members", version);
  const [copyId, setCopyId] = useState("");
  const [memberId, setMemberId] = useState("");

  const borrow = async (e) => {
    e.preventDefault();
    const ok = await run(
      () => api("/loans", { method: "POST", body: { copy_id: Number(copyId), member_id: Number(memberId) } }),
      notify, refresh, (l) => `${l.book_title} lent to ${l.member_name}, due ${dateLabel(l.due_at)}`,
    );
    if (ok) setCopyId("");
  };

  const act = (loan, verb) =>
    run(() => api(`/loans/${loan.id}/${verb}`, { method: "POST" }), notify, refresh, (l) => ({
      return: l.fine ? `Returned, fine ${rupees(l.fine)}` : "Returned on time",
      renew: `Renewed, now due ${dateLabel(l.due_at)}`,
      lost: `Marked lost, fine ${rupees(l.fine)}`,
      pay: `Fine of ${rupees(l.fine)} settled`,
    })[verb]);

  return (
    <>
      <header className="page-head">
        <h1>Loans</h1>
        {rules && (
          <p>
            {rules.loan_days}-day loans · up to {rules.max_renewals} renewals · {rupees(rules.fine_per_day)}/day late ·
            borrowing blocked at {rupees(rules.fine_block_limit)} unpaid
          </p>
        )}
      </header>

      <form className="card form-grid" onSubmit={borrow}>
        <h2>Lend a copy</h2>
        <label className="wide">Copy
          <select required value={copyId} onChange={(e) => setCopyId(e.target.value)}>
            <option value="">{copies.data?.length ? "Choose an available copy…" : "No copies available"}</option>
            {copies.data?.map((c) => <option key={c.id} value={c.id}>{c.book_title} · {c.barcode}</option>)}
          </select>
        </label>
        <label className="wide">Member
          <select required value={memberId} onChange={(e) => setMemberId(e.target.value)}>
            <option value="">Choose a member…</option>
            {members.data?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name} ({m.active_loans}/{m.max_loans}{m.unpaid_fines ? `, owes ${rupees(m.unpaid_fines)}` : ""})
              </option>
            ))}
          </select>
        </label>
        <div className="actions"><button type="submit">Lend</button></div>
      </form>

      <div className="segmented" role="tablist">
        {FILTERS.map((f) => (
          <button key={f} role="tab" aria-selected={filter === f} className={filter === f ? "on" : ""} onClick={() => setFilter(f)}>{f}</button>
        ))}
      </div>

      <Status state={loans} empty={`No ${filter} loans.`}>
        <div className="table loans">
          <div className="thead"><span>Book</span><span>Member</span><span>Due</span><span>Status</span><span /></div>
          {loans.data?.map((l) => (
            <div key={l.id} className="trow">
              <span data-label="Book"><strong>{l.book_title}</strong><small> · {l.barcode}</small></span>
              <span data-label="Member">{l.member_name}</span>
              <span data-label="Due">{dateLabel(l.due_at)}{l.renewals > 0 && <small> · renewed {l.renewals}×</small>}</span>
              <span data-label="Status">
                {l.overdue ? <span className="pill overdue">{l.days_overdue} d late</span> : <Pill value={l.status} />}
                {l.fine > 0 && <small className={l.fine_paid ? "" : "owed"}> {rupees(l.fine)} {l.fine_paid ? "paid" : "owed"}</small>}
              </span>
              <span className="row-actions">
                {l.status === "active" && (
                  <>
                    <button onClick={() => act(l, "return")}>Return</button>
                    <button className="ghost" disabled={l.overdue || l.renewals >= (rules?.max_renewals ?? 2)} onClick={() => act(l, "renew")}>Renew</button>
                    <button className="ghost danger" onClick={() => act(l, "lost")}>Lost</button>
                  </>
                )}
                {l.status !== "active" && l.fine > 0 && !l.fine_paid && <button onClick={() => act(l, "pay")}>Settle fine</button>}
              </span>
            </div>
          ))}
        </div>
      </Status>
    </>
  );
}

// --------------------------------------------------------------------------- members

const emptyMember = { name: "", email: "", max_loans: 3 };

export function Members({ version, notify, refresh }) {
  const members = useLoad("/members", version);
  const [form, setForm] = useState(emptyMember);
  const [editing, setEditing] = useState(null);

  const submit = async (e) => {
    e.preventDefault();
    const body = { ...form, max_loans: Number(form.max_loans) };
    const ok = await run(
      () => (editing ? api(`/members/${editing}`, { method: "PUT", body }) : api("/members", { method: "POST", body })),
      notify, refresh, (m) => `${editing ? "Updated" : "Welcome,"} ${m.name}`,
    );
    if (ok) { setForm(emptyMember); setEditing(null); }
  };

  return (
    <>
      <header className="page-head">
        <h1>Members</h1>
        <p>Each member has a loan limit; unpaid fines block new loans.</p>
      </header>

      <form className="card form-grid" onSubmit={submit}>
        <h2>{editing ? "Edit member" : "New member"}</h2>
        <label className="wide">Name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label className="wide">Email<input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
        <label>Loan limit<input type="number" min="1" max="10" value={form.max_loans} onChange={(e) => setForm({ ...form, max_loans: e.target.value })} /></label>
        <div className="actions">
          {editing && <button type="button" className="ghost" onClick={() => { setEditing(null); setForm(emptyMember); }}>Cancel</button>}
          <button type="submit">{editing ? "Save" : "Add member"}</button>
        </div>
      </form>

      <Status state={members} empty="No members yet.">
        <div className="table">
          <div className="thead"><span>Name</span><span>Email</span><span>Loans</span><span>Fines</span><span /></div>
          {members.data?.map((m) => (
            <div key={m.id} className="trow">
              <span data-label="Name"><strong>{m.name}</strong></span>
              <span data-label="Email">{m.email}</span>
              <span data-label="Loans">
                <span className="meter" aria-hidden><i style={{ width: `${(m.active_loans / m.max_loans) * 100}%` }} /></span>
                {m.active_loans} / {m.max_loans}
              </span>
              <span data-label="Fines" className={m.unpaid_fines ? "owed" : ""}>{m.unpaid_fines ? rupees(m.unpaid_fines) : "—"}</span>
              <span className="row-actions">
                <button className="ghost" onClick={() => { setEditing(m.id); setForm({ name: m.name, email: m.email, max_loans: m.max_loans }); scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button>
                <button className="ghost danger" onClick={() => run(() => api(`/members/${m.id}`, { method: "DELETE" }), notify, refresh, `Removed ${m.name}`)}>Delete</button>
              </span>
            </div>
          ))}
        </div>
      </Status>
    </>
  );
}
