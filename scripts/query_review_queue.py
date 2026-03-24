import sqlite3


def main() -> None:
    conn = sqlite3.connect("data/reviews.db")
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        select thread_id, status, escalated, updated_at
        from review_queue
        order by updated_at desc
        limit 20
        """
    ).fetchall()

    for row in rows:
        print(dict(row))

    conn.close()


if __name__ == "__main__":
    main()
