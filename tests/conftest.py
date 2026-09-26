"""Shared fixtures: two datasets, two backends, Mongo-aware skipping.

Two datasets are used:

- a 26-product HAND-BUILT set (known values, deliberate ties on price and
  units_sold, a boundary price, ~5% zero stock, one product with no category
  / no brand) for repository tests;
- a 1,000-product SEEDED set (seed 42, so stats are computable) for API tests.

The 50k set is manual/perf only and is NEVER used by tests. Every test is
parameterized over ``["memory", "mongo"]``; the Mongo variant SKIPS (never
fails) when no mongod is reachable. No test asserts on wall-clock time.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from memory_repository import InMemoryProductRepository
from models import Brand, Category, Product
from repository import ProductRepository

TEST_URI = "mongodb://localhost:27017"
TEST_DB = "warehouse_test"


@pytest.fixture(params=["memory", "mongo"])
def backend(request) -> str:
    return request.param


def _drop_mongo_database() -> None:
    """Drop the whole test database, not one collection.

    The student's Mongo schema is not ours: a Mongo implementation may store
    categories / brands in its own collections, so only dropping the entire
    ``TEST_DB`` guarantees a clean slate (and a clean teardown).
    """
    from pymongo import MongoClient

    client = MongoClient(TEST_URI, serverSelectionTimeoutMS=2000)
    try:
        client.drop_database(TEST_DB)
    finally:
        client.close()


def _make_repo(backend: str, products: list[Product]) -> ProductRepository:
    if backend == "memory":
        repo: ProductRepository = InMemoryProductRepository()
    else:
        from mongo_repository import MongoProductRepository

        repo = MongoProductRepository(TEST_URI, TEST_DB)
        _drop_mongo_database()
    repo.create_products(products)
    return repo


# --- 26-product hand-built dataset (repository tests) ---
BASE_DT = datetime(2026, 1, 1, 12, 0, 0)  # naive UTC


def _hp(name, description, category, brand, price, stock, rating, units_sold, seconds):
    return Product(
        id="",
        name=name,
        description=description,
        category=Category(id=None, name=category) if category is not None else None,
        brand=Brand(id=None, name=brand) if brand is not None else None,
        price=float(price),
        stock=int(stock),
        rating=float(rating),
        units_sold=int(units_sold),
        created_at=BASE_DT + timedelta(seconds=seconds),
    )


def build_hand_products() -> list[Product]:
    # Deliberate structure:
    #  - price tie: 0, 1, 2 all at 100.0 (boundary used by the inclusive test)
    #  - units_sold tie: 3, 4, 5 all at 500
    #  - boundary price: last product at exactly 1.0 (the min clamp)
    #  - ~5% zero stock: Zulu Rope and Vega Sock
    #  - search words: "zebra42" (name+desc), "zulu" (name only), "zebrawood"
    #    (description only), "chair" (Toys, name)
    #  - NO category / NO brand: Naked Gadget (the get_stats exclusion
    #    invariant: such products never appear in by_category)
    return [
        _hp("Zebra42 Widget", "Durable zebra42 gadget", "Books", "Acme", 100.0, 10, 4.5, 100, 0),
        _hp("Alpha Chair", "Made of zebrawood", "Toys", "Globex", 100.0, 20, 3.5, 200, 60),
        _hp("Beta Lamp", "Bright beta lamp for study", "Food", "Initech", 100.0, 30, 2.5, 300, 120),
        _hp("Gamma Cup", "Insulated gamma cup", "Sports", "Umbrella", 250.0, 40, 4.0, 500, 180),
        _hp("Delta Pen", "Smooth delta pen for notes", "Music", "Stark", 15.0, 5, 4.8, 500, 240),
        _hp("Epsilon Hat", "Cozy epsilon hat", "Books", "Acme", 75.0, 15, 3.9, 500, 300),
        _hp("Zulu Rope", "Strong climbing cord", "Toys", "Globex", 60.0, 0, 4.2, 75, 360),
        _hp("Kilo Board", "Sturdy kilo board", "Food", "Initech", 120.0, 25, 3.3, 45, 420),
        _hp("Mango Box", "Light mango box", "Sports", "Umbrella", 33.0, 8, 2.9, 60, 480),
        _hp("Nova Case", "Durable nova case", "Music", "Stark", 210.0, 12, 4.6, 90, 540),
        _hp("Orion Tool", "Precision orion tool", "Books", "Acme", 50.0, 18, 3.7, 55, 600),
        _hp("Puma Bag", "Roomy puma bag", "Toys", "Globex", 90.0, 22, 4.1, 70, 660),
        _hp("Quill Ink", "Rich quill ink", "Food", "Initech", 12.0, 4, 3.2, 35, 720),
        _hp("Raven Desk", "Elegant raven desk", "Sports", "Umbrella", 450.0, 9, 4.4, 80, 780),
        _hp("Sable Coat", "Warm sable coat", "Music", "Stark", 300.0, 14, 3.8, 65, 840),
        _hp("Terra Pot", "Tough terra pot", "Books", "Acme", 40.0, 6, 2.7, 40, 900),
        _hp("Ultra Fan", "Quiet ultra fan", "Toys", "Globex", 85.0, 11, 4.3, 50, 960),
        _hp("Vega Sock", "Soft vega socks", "Food", "Initech", 20.0, 0, 3.6, 30, 1020),
        _hp("Willow Shelf", "Stable willow shelf", "Sports", "Umbrella", 150.0, 7, 4.0, 55, 1080),
        _hp("Xenon Light", "Bright xenon light", "Music", "Stark", 275.0, 3, 4.7, 85, 1140),
        _hp("Yarrow Mat", "Cushioned yarrow mat", "Books", "Acme", 65.0, 16, 3.4, 60, 1200),
        _hp("Zephyr Kite", "Colorful zephyr kite", "Toys", "Globex", 28.0, 19, 3.1, 45, 1260),
        _hp("Aster Frame", "Slim aster frame", "Food", "Initech", 130.0, 13, 3.9, 70, 1320),
        _hp("Basil Clock", "Ticking basil clock", "Sports", "Umbrella", 190.0, 10, 4.2, 75, 1380),
        _hp("Coral Ring", "Glossy coral ring", "Music", "Stark", 1.0, 2, 5.0, 25, 1440),
        _hp("Naked Gadget", "Unclassified (stats invariant)", None, None, 55.5, 3, 1.0, 5, 1500),
    ]


@pytest.fixture
def hand_products() -> list[Product]:
    return build_hand_products()


@pytest.fixture
def repo(backend: str, hand_products: list[Product]) -> ProductRepository:
    r = _make_repo(backend, hand_products)
    yield r
    if backend == "mongo":
        _drop_mongo_database()
    r.close()


# --- 1,000-product seeded dataset (API tests) ---
@pytest.fixture
def seeded_products() -> list[Product]:
    from seed import make_products

    return make_products(1000)


@pytest.fixture
def api_repo(backend: str, seeded_products: list[Product]) -> ProductRepository:
    r = _make_repo(backend, seeded_products)
    yield r
    if backend == "mongo":
        _drop_mongo_database()
    r.close()


@pytest.fixture
def client(api_repo: ProductRepository):
    from app import create_app

    app = create_app(api_repo)
    app.config["TESTING"] = True
    with app.test_client() as test_client:
        yield test_client
