from sqlalchemy import text


# --------------------------------------------------------------------------- ops

def test_health_does_not_need_db(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready_checks_schema(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_info_publishes_lending_rules(client):
    body = client.get("/api/info").json()
    assert body["app"] == "ShelfLend"
    assert body["version"] == "test"
    assert body["rules"]["loan_days"] == 14
    assert body["rules"]["fine_per_day"] == 10


# --------------------------------------------------------------------------- books

def test_create_book_normalises_isbn(client, book):
    assert book["isbn"] == "9780134685991"
    assert book["total_copies"] == 0


def test_duplicate_isbn_is_409(client, book):
    r = client.post("/api/books", json={"isbn": "9780134685991", "title": "Again", "author": "X"})
    assert r.status_code == 409


def test_invalid_isbn_is_422(client):
    r = client.post("/api/books", json={"isbn": "12345", "title": "Bad", "author": "X"})
    assert r.status_code == 422


def test_blank_title_is_422(client):
    r = client.post("/api/books", json={"isbn": "9780134685991", "title": "   ", "author": "X"})
    assert r.status_code == 422


def test_list_and_search_books(client, book):
    client.post("/api/books", json={"isbn": "9780262046305", "title": "Introduction to Algorithms", "author": "Cormen"})
    assert len(client.get("/api/books").json()) == 2
    hits = client.get("/api/books", params={"q": "cormen"}).json()
    assert [b["title"] for b in hits] == ["Introduction to Algorithms"]


def test_get_missing_book_is_404(client):
    assert client.get("/api/books/9999").status_code == 404


def test_update_book(client, book):
    r = client.put(f"/api/books/{book['id']}", json={
        "isbn": book["isbn"], "title": "The Pragmatic Programmer (20th Anniv.)", "author": "Thomas & Hunt",
    })
    assert r.status_code == 200
    assert r.json()["author"] == "Thomas & Hunt"
    assert client.get(f"/api/books/{book['id']}").json()["title"].endswith("(20th Anniv.)")


def test_delete_book_without_loans(client, book, copy):
    assert client.delete(f"/api/books/{book['id']}").status_code == 204
    assert client.get(f"/api/books/{book['id']}").status_code == 404
    assert client.get("/api/copies").json() == []


def test_delete_book_with_loan_history_is_409(client, book, copy, member):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    client.post(f"/api/loans/{loan['id']}/return")
    assert client.delete(f"/api/books/{book['id']}").status_code == 409


# --------------------------------------------------------------------------- copies

def test_copy_counts_on_book(client, book, copy):
    client.post(f"/api/books/{book['id']}/copies", json={"barcode": "LIB-0002"})
    b = client.get(f"/api/books/{book['id']}").json()
    assert (b["total_copies"], b["available_copies"]) == (2, 2)


def test_duplicate_barcode_is_409(client, book, copy):
    r = client.post(f"/api/books/{book['id']}/copies", json={"barcode": "LIB-0001"})
    assert r.status_code == 409


def test_copy_to_maintenance_and_back(client, copy):
    r = client.patch(f"/api/copies/{copy['id']}", json={"status": "maintenance"})
    assert r.json()["status"] == "maintenance"
    assert client.get("/api/copies", params={"status": "maintenance"}).json()[0]["barcode"] == "LIB-0001"
    assert client.patch(f"/api/copies/{copy['id']}", json={"status": "available"}).status_code == 200


# --------------------------------------------------------------------------- members

def test_duplicate_member_email_is_409(client, member):
    r = client.post("/api/members", json={"name": "Other", "email": "ASHA@example.com"})
    assert r.status_code == 409


def test_update_and_delete_member(client):
    m = client.post("/api/members", json={"name": "Ravi", "email": "ravi@example.com"}).json()
    r = client.put(f"/api/members/{m['id']}", json={"name": "Ravi K", "email": "ravi@example.com", "max_loans": 5})
    assert r.json()["max_loans"] == 5
    assert client.delete(f"/api/members/{m['id']}").status_code == 204
    assert client.delete(f"/api/members/{m['id']}").status_code == 404


def test_invalid_member_email_is_422(client):
    assert client.post("/api/members", json={"name": "X", "email": "not-an-email"}).status_code == 422


# --------------------------------------------------------------------------- loans

def test_borrow_marks_copy_on_loan(client, copy, member):
    r = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]})
    assert r.status_code == 201
    loan = r.json()
    assert loan["status"] == "active" and loan["overdue"] is False
    assert loan["book_title"] == "The Pragmatic Programmer"
    assert client.get("/api/copies").json()[0]["status"] == "on_loan"


def test_same_copy_cannot_be_lent_twice(client, copy, member):
    other = client.post("/api/members", json={"name": "Ben", "email": "ben@example.com"}).json()
    client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]})
    r = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": other["id"]})
    assert r.status_code == 409
    assert "on loan" in r.json()["detail"]


def test_database_refuses_second_active_loan(client, copy, member):
    """Even if the API check is bypassed, the partial unique index holds."""
    import pytest
    from sqlalchemy.exc import IntegrityError

    from app.db import engine

    client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]})
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO loans (copy_id, member_id, status, borrowed_at, due_at, renewals, fine, fine_paid) "
            "VALUES (:c, :m, 'active', '2026-01-01', '2026-01-15', 0, 0, 0)"
        ), {"c": copy["id"], "m": member["id"]})


def test_member_loan_limit(client, book, member):
    ids = [client.post(f"/api/books/{book['id']}/copies", json={"barcode": f"LIM-{i}"}).json()["id"] for i in range(3)]
    for cid in ids[:2]:
        assert client.post("/api/loans", json={"copy_id": cid, "member_id": member["id"]}).status_code == 201
    r = client.post("/api/loans", json={"copy_id": ids[2], "member_id": member["id"]})
    assert r.status_code == 409
    assert "2 of 2" in r.json()["detail"]


def test_copy_in_maintenance_cannot_be_borrowed(client, copy, member):
    client.patch(f"/api/copies/{copy['id']}", json={"status": "maintenance"})
    r = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]})
    assert r.status_code == 409


def test_borrow_unknown_member_is_404(client, copy):
    assert client.post("/api/loans", json={"copy_id": copy["id"], "member_id": 999}).status_code == 404


def test_return_on_time_has_no_fine(client, copy, member):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    r = client.post(f"/api/loans/{loan['id']}/return")
    assert r.status_code == 200
    assert (r.json()["status"], r.json()["fine"], r.json()["fine_paid"]) == ("returned", 0, True)
    assert client.get("/api/copies").json()[0]["status"] == "available"


def test_returning_twice_is_409(client, copy, member):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    client.post(f"/api/loans/{loan['id']}/return")
    assert client.post(f"/api/loans/{loan['id']}/return").status_code == 409


def test_late_return_charges_fine_and_blocks_borrowing(client, book, copy, member, make_overdue):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    make_overdue(loan["id"], 10)
    assert client.get("/api/loans", params={"status": "overdue"}).json()[0]["id"] == loan["id"]

    r = client.post(f"/api/loans/{loan['id']}/return").json()
    assert r["fine"] == 110  # 10 days and 1 hour late -> 11 days x ₹10
    assert r["fine_paid"] is False

    second = client.post(f"/api/books/{book['id']}/copies", json={"barcode": "LIB-0002"}).json()
    blocked = client.post("/api/loans", json={"copy_id": second["id"], "member_id": member["id"]})
    assert blocked.status_code == 409 and "fines" in blocked.json()["detail"]

    assert client.post(f"/api/loans/{loan['id']}/pay").json()["fine_paid"] is True
    assert client.post(f"/api/loans/{loan['id']}/pay").status_code == 409
    assert client.post("/api/loans", json={"copy_id": second["id"], "member_id": member["id"]}).status_code == 201


def test_renew_extends_due_date_up_to_limit(client, copy, member):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    first = client.post(f"/api/loans/{loan['id']}/renew").json()
    assert first["renewals"] == 1 and first["due_at"] > loan["due_at"]
    assert client.post(f"/api/loans/{loan['id']}/renew").status_code == 200
    r = client.post(f"/api/loans/{loan['id']}/renew")
    assert r.status_code == 409 and "max 2" in r.json()["detail"]


def test_overdue_loan_cannot_be_renewed(client, copy, member, make_overdue):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    make_overdue(loan["id"], 2)
    assert client.post(f"/api/loans/{loan['id']}/renew").status_code == 409


def test_mark_lost_closes_loan_and_copy(client, copy, member):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    r = client.post(f"/api/loans/{loan['id']}/lost").json()
    assert (r["status"], r["fine"]) == ("lost", 500)
    assert client.get("/api/copies").json()[0]["status"] == "lost"
    assert client.post(f"/api/loans/{loan['id']}/renew").status_code == 409
    assert client.patch(f"/api/copies/{copy['id']}", json={"status": "available"}).status_code == 409


# --------------------------------------------------------------------------- dashboard + metrics

def test_stats_and_activity_feed(client, copy, member):
    client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]})
    s = client.get("/api/stats").json()
    assert s["books"] == 1 and s["members"] == 1 and s["active_loans"] == 1
    assert s["copies"]["on_loan"] == 1
    actions = [e["action"] for e in client.get("/api/activity").json()]
    assert actions[0] == "borrowed"
    assert {"created", "added", "joined"} <= set(actions)


def test_metrics_exposes_http_and_business_gauges(client, copy, member, make_overdue):
    loan = client.post("/api/loans", json={"copy_id": copy["id"], "member_id": member["id"]}).json()
    make_overdue(loan["id"], 3)
    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "shelflend_loans_active 1.0" in body
    assert "shelflend_loans_overdue 1.0" in body
    assert 'shelflend_copies{status="on_loan"} 1.0' in body
    assert "shelflend_db_up 1.0" in body
