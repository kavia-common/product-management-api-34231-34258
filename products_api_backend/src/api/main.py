import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Path, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
import sqlite3
from contextlib import contextmanager

# Note on configuration:
# - If an external products_database is available, you can configure DATABASE_URL via environment variable.
# - Otherwise, this service will default to a local SQLite database file.
DEFAULT_DB_PATH = os.getenv("DATABASE_URL", "sqlite:///./products.db")


def _sqlite_path_from_url(url: str) -> str:
    """
    Convert a sqlite URL (sqlite:///path/to.db) to filesystem path (path/to.db).
    If the URL is already a filesystem path, return as-is.
    """
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "", 1)
    if url.startswith("file:"):
        # SQLite URI path like file:products.db?mode=rwc
        return url[5:].split("?")[0]
    return url


DB_FILE_PATH = _sqlite_path_from_url(DEFAULT_DB_PATH)


@contextmanager
def get_db_cursor():
    """Context manager for SQLite connection and cursor with row factory."""
    conn = sqlite3.connect(DB_FILE_PATH, check_same_thread=False)
    try:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        yield cur
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Initialize the SQLite database with the products table if it does not exist."""
    with get_db_cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL NOT NULL CHECK(price >= 0),
                quantity INTEGER NOT NULL CHECK(quantity >= 0)
            )
            """
        )


# PUBLIC_INTERFACE
class ProductCreate(BaseModel):
    """Input model for creating a product."""
    name: str = Field(..., description="The product's name", min_length=1, max_length=255)
    price: float = Field(..., description="The product's price, must be non-negative", ge=0)
    quantity: int = Field(..., description="Available quantity, must be non-negative integer", ge=0)

    @validator("price")
    def validate_price(cls, v):
        # Round to 2 decimal places to avoid floating artifacts
        return round(float(v), 2)


# PUBLIC_INTERFACE
class ProductUpdate(BaseModel):
    """Input model for updating a product. All fields optional."""
    name: Optional[str] = Field(None, description="Updated product name", min_length=1, max_length=255)
    price: Optional[float] = Field(None, description="Updated price, must be non-negative", ge=0)
    quantity: Optional[int] = Field(None, description="Updated quantity, must be non-negative integer", ge=0)

    @validator("price")
    def validate_price(cls, v):
        if v is None:
            return v
        return round(float(v), 2)


# PUBLIC_INTERFACE
class Product(BaseModel):
    """Product response model with id."""
    id: int = Field(..., description="Unique identifier of the product")
    name: str = Field(..., description="The product's name")
    price: float = Field(..., description="The product's price")
    quantity: int = Field(..., description="Available quantity")


app = FastAPI(
    title="Product Management API",
    description="CRUD API for managing products with fields: id, name, price, quantity.",
    version="1.0.0",
    openapi_tags=[
        {"name": "health", "description": "Healthcheck endpoint"},
        {"name": "products", "description": "Operations with products"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    # Ensure directory exists for relative db paths
    db_dir = os.path.dirname(DB_FILE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    init_db()


# PUBLIC_INTERFACE
@app.get("/", tags=["health"], summary="Health Check", description="Simple health check endpoint returning a status.")
def health_check():
    """Healthcheck endpoint for service monitoring. Returns {'message': 'Healthy'}."""
    return {"message": "Healthy"}


# Data access helpers
def fetch_product_or_404(product_id: int) -> sqlite3.Row:
    with get_db_cursor() as cur:
        cur.execute("SELECT id, name, price, quantity FROM products WHERE id = ?", (product_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Product {product_id} not found")
        return row


# PUBLIC_INTERFACE
@app.get(
    "/products",
    response_model=List[Product],
    tags=["products"],
    summary="List products",
    description="Returns a list of all products in the catalog.",
)
def list_products():
    """List all products."""
    with get_db_cursor() as cur:
        cur.execute("SELECT id, name, price, quantity FROM products ORDER BY id ASC")
        rows = cur.fetchall()
        return [Product(id=row["id"], name=row["name"], price=row["price"], quantity=row["quantity"]) for row in rows]


# PUBLIC_INTERFACE
@app.post(
    "/products",
    response_model=Product,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
    summary="Create product",
    description="Create a new product with name, price, and quantity.",
)
def create_product(payload: ProductCreate):
    """Create a new product and return it."""
    with get_db_cursor() as cur:
        cur.execute(
            "INSERT INTO products (name, price, quantity) VALUES (?, ?, ?)",
            (payload.name.strip(), float(payload.price), int(payload.quantity)),
        )
        new_id = cur.lastrowid
        cur.execute("SELECT id, name, price, quantity FROM products WHERE id = ?", (new_id,))
        row = cur.fetchone()
        return Product(id=row["id"], name=row["name"], price=row["price"], quantity=row["quantity"])


# PUBLIC_INTERFACE
@app.get(
    "/products/{id}",
    response_model=Product,
    tags=["products"],
    summary="Get product by ID",
    description="Retrieve a single product by its ID.",
)
def get_product(
    id: int = Path(..., description="The ID of the product to retrieve", ge=1)
):
    """Get a product by ID."""
    row = fetch_product_or_404(id)
    return Product(id=row["id"], name=row["name"], price=row["price"], quantity=row["quantity"])


# PUBLIC_INTERFACE
@app.put(
    "/products/{id}",
    response_model=Product,
    tags=["products"],
    summary="Update product",
    description="Update an existing product by ID. Only provided fields will be updated.",
)
def update_product(
    payload: ProductUpdate,
    id: int = Path(..., description="The ID of the product to update", ge=1),
):
    """Update fields of a product."""
    # Load current product
    current = fetch_product_or_404(id)
    new_name = current["name"] if payload.name is None else payload.name.strip()
    new_price = current["price"] if payload.price is None else float(payload.price)
    new_quantity = current["quantity"] if payload.quantity is None else int(payload.quantity)

    with get_db_cursor() as cur:
        cur.execute(
            "UPDATE products SET name = ?, price = ?, quantity = ? WHERE id = ?",
            (new_name, new_price, new_quantity, id),
        )
        cur.execute("SELECT id, name, price, quantity FROM products WHERE id = ?", (id,))
        row = cur.fetchone()
        return Product(id=row["id"], name=row["name"], price=row["price"], quantity=row["quantity"])


# PUBLIC_INTERFACE
@app.delete(
    "/products/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["products"],
    summary="Delete product",
    description="Delete a product by its ID. Returns 204 on success.",
)
def delete_product(
    id: int = Path(..., description="The ID of the product to delete", ge=1),
):
    """Delete a product by ID."""
    # Ensure exists
    _ = fetch_product_or_404(id)
    with get_db_cursor() as cur:
        cur.execute("DELETE FROM products WHERE id = ?", (id,))
    # 204 No Content
    return None


# PUBLIC_INTERFACE
@app.get(
    "/products/balance",
    tags=["products"],
    summary="Get total inventory balance",
    description="Returns the total value of inventory as the sum over all products of price * quantity.",
)
def get_products_balance():
    """
    Calculate the total inventory value.

    Tries to perform efficient aggregation in SQLite using:
      SELECT COALESCE(SUM(price * quantity), 0) AS total FROM products

    If any database error occurs (e.g., file missing, table missing, or any unexpected condition),
    falls back to computing the balance in memory by reading all rows.

    Returns:
        JSON object: {"total_balance": <float>}
        - 0 if there are no products or in error conditions, ensuring a graceful response.
    """
    try:
        # Primary path: efficient SQL aggregation
        with get_db_cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(price * quantity), 0) AS total FROM products")
            row = cur.fetchone()
            total = row["total"] if row and row["total"] is not None else 0.0
            # Normalize to 2 decimal places similar to price handling
            return {"total_balance": round(float(total), 2)}
    except Exception:
        # Fallback path: compute in memory
        try:
            with get_db_cursor() as cur:
                cur.execute("SELECT price, quantity FROM products")
                rows = cur.fetchall()
                total = 0.0
                for r in rows or []:
                    try:
                        total += float(r["price"]) * int(r["quantity"])
                    except Exception:
                        # Skip malformed rows in worst case
                        continue
                return {"total_balance": round(float(total), 2)}
        except Exception:
            # If even fallback fails, return 0 per requirement
            return {"total_balance": 0.0}


if __name__ == "__main__":
    # Entrypoint to run via: python -m src.api.main
    import uvicorn

    port = int(os.getenv("PORT", "3001"))
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=port, reload=False)
