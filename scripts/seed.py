#!/usr/bin/env python3
"""Fill ShelfLend with realistic demo data through its own public API.

    API=http://127.0.0.1:3000 python3 scripts/seed.py                  # Compose
    API=http://127.0.0.1 HOST_HEADER=shelflend.local python3 scripts/seed.py  # Ingress

Standard library only. Safe to re-run: existing ISBNs/barcodes/emails are skipped.
"""
import json
import os
import random
import urllib.error
import urllib.request

API = os.getenv("API", "http://127.0.0.1:3000").rstrip("/")
HOST = os.getenv("HOST_HEADER")

BOOKS = [
    ("9780134685991", "Effective Java", "Joshua Bloch", "Programming", 2018, 3),
    ("9780135957059", "The Pragmatic Programmer", "David Thomas, Andrew Hunt", "Programming", 2019, 2),
    ("9780262046305", "Introduction to Algorithms", "Cormen, Leiserson, Rivest, Stein", "Computer Science", 2022, 3),
    ("9781492078005", "Kubernetes: Up and Running", "Brendan Burns et al.", "DevOps", 2022, 2),
    ("9781098131821", "Terraform: Up & Running", "Yevgeniy Brikman", "DevOps", 2022, 2),
    ("9781950508693", "The DevOps Handbook", "Gene Kim et al.", "DevOps", 2021, 2),
    ("9780143127741", "The Wright Brothers", "David McCullough", "History", 2015, 1),
    ("9780143424604", "The Discovery of India", "Jawaharlal Nehru", "History", 2008, 2),
    ("9780143066286", "Train to Pakistan", "Khushwant Singh", "Fiction", 2016, 1),
    ("9780099578512", "Midnight's Children", "Salman Rushdie", "Fiction", 2013, 2),
    ("9780007441617", "The God of Small Things", "Arundhati Roy", "Fiction", 2017, 2),
    ("9781501161933", "Site Reliability Engineering", "Betsy Beyer et al.", "DevOps", 2016, 1),
    ("9780596517748", "JavaScript: The Good Parts", "Douglas Crockford", "Programming", 2008, 1),
    ("9781617294136", "Securing DevOps", "Julien Vehent", "Security", 2018, 1),
]
MEMBERS = [
    ("Ananya Iyer", "ananya.iyer@example.edu", 3), ("Rohan Mehta", "rohan.mehta@example.edu", 3),
    ("Kavya Nair", "kavya.nair@example.edu", 5), ("Arjun Singh", "arjun.singh@example.edu", 3),
    ("Meera Pillai", "meera.pillai@example.edu", 2), ("Vikram Rao", "vikram.rao@example.edu", 3),
    ("Sneha Kulkarni", "sneha.kulkarni@example.edu", 4), ("Aditya Verma", "aditya.verma@example.edu", 3),
]


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    if HOST:
        req.add_header("Host", HOST)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or "null")


def main():
    random.seed(10293)
    for isbn, title, author, genre, year, n in BOOKS:
        code, book = call("POST", "/api/books", dict(isbn=isbn, title=title, author=author, genre=genre, published_year=year))
        if code == 409:
            continue
        for i in range(n):
            call("POST", f"/api/books/{book['id']}/copies",
                 {"barcode": f"SL-{book['id']:03d}-{i + 1}", "shelf": f"{genre[:3].upper()}-{random.randint(1, 9)}"})
    for name, email, limit in MEMBERS:
        call("POST", "/api/members", {"name": name, "email": email, "max_loans": limit})

    _, members = call("GET", "/api/members")
    _, copies = call("GET", "/api/copies?status=available")
    random.shuffle(copies)
    made = 0
    for copy in copies[:14]:
        m = random.choice(members)
        code, loan = call("POST", "/api/loans", {"copy_id": copy["id"], "member_id": m["id"]})
        if code != 201:
            continue
        made += 1
        roll = random.random()
        if roll < 0.25:
            call("POST", f"/api/loans/{loan['id']}/return")
        elif roll < 0.4:
            call("POST", f"/api/loans/{loan['id']}/renew")
    call("PATCH", f"/api/copies/{copies[-1]['id']}", {"status": "maintenance"})
    _, stats = call("GET", "/api/stats")
    print(f"seeded {API}: {made} loans created; stats now {stats}")


if __name__ == "__main__":
    main()
