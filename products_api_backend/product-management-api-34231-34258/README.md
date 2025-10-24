# Product Management API

FastAPI backend exposing CRUD endpoints for products with fields:
- id (int)
- name (string)
- price (float)
- quantity (int)

Runs on port 3001 by default.

## Quick start

1. Install dependencies:

   pip install -r products_api_backend/requirements.txt

2. Run the API:

   python -m products_api_backend.src.api.main

   The service starts on http://localhost:3001 (OpenAPI docs at /docs).

## Configuration

- DATABASE_URL: If provided, used for persistence. Defaults to sqlite:///./products.db.
  - Example: export DATABASE_URL="sqlite:///./products.db"
- PORT: HTTP port (default 3001)

If an external products_database is available, set DATABASE_URL to point to it. Otherwise, the service uses a local SQLite file.

## Endpoints

- GET / -> Health check

- GET /products
  - Returns: 200 OK, list of Product

- POST /products
  - Body:
    {
      "name": "Widget",
      "price": 19.99,
      "quantity": 10
    }
  - Returns: 201 Created, Product

- GET /products/{id}
  - Path: id (integer)
  - Returns: 200 OK, Product or 404 if not found

- PUT /products/{id}
  - Path: id (integer)
  - Body (all fields optional):
    {
      "name": "Widget Pro",
      "price": 24.99,
      "quantity": 8
    }
  - Returns: 200 OK, updated Product or 404 if not found

- DELETE /products/{id}
  - Path: id (integer)
  - Returns: 204 No Content or 404 if not found

## Example curl

- Create:
  curl -X POST http://localhost:3001/products -H "Content-Type: application/json" -d '{"name":"Widget","price":19.99,"quantity":10}'

- List:
  curl http://localhost:3001/products

- Get by id:
  curl http://localhost:3001/products/1

- Update:
  curl -X PUT http://localhost:3001/products/1 -H "Content-Type: application/json" -d '{"price":24.99}'

- Delete:
  curl -X DELETE http://localhost:3001/products/1

## Notes

- Basic validation and error handling are included.
- OpenAPI schema available at /openapi.json and interactive docs at /docs.
