"""
Library Book Management System
Flask web application with Azure SQL Server backend for managing books.
Uses raw SQL queries via pyodbc (no ORM).
"""

import os
from flask import Flask, render_template, request, redirect, url_for, flash
import pyodbc

app = Flask(__name__)
app.secret_key = "library-secret-key"  # Needed for flash messages


def get_db_connection():
    """
    Creates and returns a new Azure SQL Server database connection.
    Reads connection details from environment variables so that
    credentials are never hardcoded in the source code.
    Uses the ODBC Driver 18 for SQL Server.
    """
    server = os.environ.get("DB_HOST", "localhost")
    user = os.environ.get("DB_USER", "")
    password = os.environ.get("DB_PASS", "")
    database = os.environ.get("DB_NAME", "")

    connection_string = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"Encrypt=yes;"
        f"TrustServerCertificate=no;"
    )
    connection = pyodbc.connect(connection_string)
    return connection


def row_to_dict(cursor, row):
    """
    Converts a pyodbc Row object into a dictionary using column names.
    This makes it easy to access columns by name in Jinja2 templates
    (e.g., book.Title, book.Author).
    """
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def rows_to_dicts(cursor, rows):
    """Converts a list of pyodbc Row objects into a list of dictionaries."""
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


# ──────────────────────────────────────────────
# ROUTE 1: Home Page — List all books + Search
# ──────────────────────────────────────────────
@app.route("/")
def index():
    """
    Displays all books in a table.
    If a 'search' query parameter is provided, filters books whose
    Title OR Genre contain the search term (case-insensitive).
    SQL Server's LIKE is case-insensitive by default with the
    default collation, so no extra handling is needed.
    """
    search_term = request.args.get("search", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    if search_term:
        # Use LIKE with wildcards for partial matching
        # ? is the parameterized placeholder for pyodbc (NOT %s)
        query = """
            SELECT * FROM bookinfo
            WHERE Title LIKE ? OR Genre LIKE ?
            ORDER BY Title
        """
        wildcard = f"%{search_term}%"
        cursor.execute(query, (wildcard, wildcard))
    else:
        cursor.execute("SELECT * FROM bookinfo ORDER BY Title")

    books = rows_to_dicts(cursor, cursor.fetchall())
    cursor.close()
    conn.close()

    return render_template("index.html", books=books, search_term=search_term)


# ──────────────────────────────────────────────
# ROUTE 2: Add Book — Show form / Handle submit
# ──────────────────────────────────────────────
@app.route("/add", methods=["GET", "POST"])
def add_book():
    """
    GET  → Renders the empty 'Add Book' form.
    POST → Validates input, inserts a new book into the database,
           then redirects to the home page.
    """
    if request.method == "POST":
        # Collect form data
        book_id = request.form.get("book_id", "").strip()
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        genre = request.form.get("genre", "").strip()
        available_copies = request.form.get("available_copies", "").strip()

        # --- Basic Validation ---
        # Check all fields are filled
        if not all([book_id, title, author, genre, available_copies]):
            flash("All fields are required.", "error")
            return render_template("add.html")

        # Check AvailableCopies is a non-negative integer
        try:
            available_copies = int(available_copies)
            if available_copies < 0:
                raise ValueError
        except ValueError:
            flash("Available Copies must be a non-negative integer.", "error")
            return render_template("add.html")

        # --- Insert into database using parameterized query ---
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = """
                INSERT INTO bookinfo (BookID, Title, Author, Genre, AvailableCopies)
                VALUES (?, ?, ?, ?, ?)
            """
            cursor.execute(query, (book_id, title, author, genre, available_copies))
            conn.commit()
            cursor.close()
            conn.close()
            flash("Book added successfully!", "success")
        except pyodbc.IntegrityError:
            flash(f"A book with ID '{book_id}' already exists.", "error")
            return render_template("add.html")

        return redirect(url_for("index"))

    # GET request — just show the form
    return render_template("add.html")


# ──────────────────────────────────────────────
# ROUTE 3: Edit Book — Pre-filled form / Update
# ──────────────────────────────────────────────
@app.route("/edit/<bookid>", methods=["GET", "POST"])
def edit_book(bookid):
    """
    GET  → Fetches the existing book data and renders the edit form
           with fields pre-filled.
    POST → Validates input, updates the book record, then redirects
           to the home page.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        # Collect updated form data
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        genre = request.form.get("genre", "").strip()
        available_copies = request.form.get("available_copies", "").strip()

        # --- Basic Validation ---
        if not all([title, author, genre, available_copies]):
            flash("All fields are required.", "error")
            cursor.execute("SELECT * FROM bookinfo WHERE BookID = ?", (bookid,))
            book = row_to_dict(cursor, cursor.fetchone())
            cursor.close()
            conn.close()
            return render_template("edit.html", book=book)

        try:
            available_copies = int(available_copies)
            if available_copies < 0:
                raise ValueError
        except ValueError:
            flash("Available Copies must be a non-negative integer.", "error")
            cursor.execute("SELECT * FROM bookinfo WHERE BookID = ?", (bookid,))
            book = row_to_dict(cursor, cursor.fetchone())
            cursor.close()
            conn.close()
            return render_template("edit.html", book=book)

        # --- Update the record using parameterized query ---
        query = """
            UPDATE bookinfo
            SET Title = ?, Author = ?, Genre = ?, AvailableCopies = ?
            WHERE BookID = ?
        """
        cursor.execute(query, (title, author, genre, available_copies, bookid))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Book updated successfully!", "success")
        return redirect(url_for("index"))

    # GET request — fetch existing book data for the form
    cursor.execute("SELECT * FROM bookinfo WHERE BookID = ?", (bookid,))
    book = row_to_dict(cursor, cursor.fetchone())
    cursor.close()
    conn.close()

    if not book:
        flash("Book not found.", "error")
        return redirect(url_for("index"))

    return render_template("edit.html", book=book)


# ──────────────────────────────────────────────
# ROUTE 4: Delete Book
# ──────────────────────────────────────────────
@app.route("/delete/<bookid>")
def delete_book(bookid):
    """
    Deletes the book with the given BookID from the database.
    The JavaScript confirm() dialog is handled on the frontend
    (in index.html) before this route is ever called.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookinfo WHERE BookID = ?", (bookid,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Book deleted successfully!", "success")
    return redirect(url_for("index"))


# ──────────────────────────────────────────────
# Run the app
# ──────────────────────────────────────────────
if __name__ == "__main__":
    # debug=True enables auto-reload during development
    app.run(debug=True, host="0.0.0.0", port=5001)
