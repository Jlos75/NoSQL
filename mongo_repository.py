"""=== TO COMPLETE ===

This file is the implementation gap: 15 of the 17 methods are stubs
(``ensure_indexes`` is a deliberate no-op, ``create_products`` is provided).

The ``InMemoryProductRepository`` in ``memory_repository.py`` is the reference
behavior. Implement this repository on MongoDB.

No application-level caching, no Python tricks: speed must come from the
database.
"""

from __future__ import annotations

import logging


## ajout
import re
import uuid
from pymongo import ASCENDING, DESCENDING, MongoClient, ReturnDocument

from models import Brand, CatalogStats, Category, CategoryStats, Product, ProductPage, ProductQuery
from repository import ProductRepository
from repository import EntityNotFoundError

LOGGER = logging.getLogger(__name__)

# The Mongo collection that holds products. A neutral contract detail: the
# test fixtures and seeder import this to know where to clean up. Deliberately
# NOT a performance hint (no mention of indexes, $text, keyset, projections).
PRODUCT_COLLECTION_NAME = "product"


class MongoProductRepository(ProductRepository):
    """MongoDB-backed repository. The 17 methods below are the same contract as
    ``InMemoryProductRepository``, implemented on MongoDB.

    ``__init__`` receives the URI and DB name from the factory; it does NOT
    read environment variables. 15 of the 17 methods currently raise
    ``NotImplementedError`` (``ensure_indexes`` is a deliberate no-op,
    ``create_products`` is provided).

    The member docstrings state the contract ONLY. They deliberately contain
    NO hints about indexes, ``$text``, keyset pagination, or projections.

    Name matching follows the same convention: every name comparison is
    case-sensitive (``Books`` and ``books`` are two distinct entities); the
    only case-insensitive match is ``ProductQuery.search_text``.
    """

    def __init__(self, uri: str, db_name: str) -> None:
        self._uri = uri
        self._db_name = db_name
        # Lazy client: no connection is opened until an operation actually runs.
        self._client = MongoClient(uri)
        self._db = self._client[db_name]
        self._products = self._db[PRODUCT_COLLECTION_NAME]
        self._categories = self._db["category"]
        self._brands = self._db["brand"]

    def close(self) -> None:
        """Release backend resources. Called once at shutdown."""
        LOGGER.info("close()")
        self._client.close() # fait
        #raise NotImplementedError("TODO: implement 'close' using MongoDB")

    def _entity(self, collection, value, entity_type):
        if value is None:
            return None
        doc = collection.find_one_and_update(
            {"name": value.name},
            {"$setOnInsert": {"_id": uuid.uuid4().hex, "name": value.name}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return entity_type(id=doc["_id"], name=doc["name"])

    def _document(self, product: Product) -> dict:
        category = self._entity(self._categories, product.category, Category)
        brand = self._entity(self._brands, product.brand, Brand)
        return {
            "name": product.name,
            "description": product.description,
            "category": {"id": category.id, "name": category.name} if category else None,
            "brand": {"id": brand.id, "name": brand.name} if brand else None,
            "price": product.price,
            "stock": product.stock,
            "rating": product.rating,
            "units_sold": product.units_sold,
            "created_at": product.created_at,
        }
            
    @staticmethod
    def _product(doc: dict) -> Product:
        category = doc.get("category")
        brand = doc.get("brand")
        return Product(
            id=doc["_id"],
            name=doc["name"],
            description=doc["description"],
            category=Category(**category) if category else None,
            brand=Brand(**brand) if brand else None,
            price=doc["price"],
            stock=doc["stock"],
            rating=doc["rating"],
            units_sold=doc["units_sold"],
            created_at=doc["created_at"],
        )
        
    def create_product(self, product: Product) -> Product:
        """Create a single product.

        The repository generates the product ``id`` (the placeholder carried
        on ``product`` is replaced); a referenced category / brand is
        auto-created on first sight of its name. Returns the stored product.
        """
        LOGGER.info("create_product(%r, %s, %d)", product.name, product.price, product.stock)
        #raise NotImplementedError("TODO: implement 'create_product' using MongoDB")
        
        doc = self._document(product)
        doc["_id"] = uuid.uuid4().hex
        self._products.insert_one(doc)
        return self._product(doc)
        

    def create_products(self, products: list[Product]) -> list[Product]:
        """Insert many products in one bulk call (the seed path).

        Each product ``id`` is generated by the repository, as in
        ``create_product``. The referenced entities are created ONCE per name
        for the whole batch. Returns the stored products in input order; an
        empty input returns an empty list.
        """
        LOGGER.info("create_products(%d)", len(products))
        # Not required immediately. Can be implemented later.
        if not products:
            return []
        docs = []
        for product in products:
            doc = self._document(product)
            doc["_id"] = uuid.uuid4().hex
            docs.append(doc)
        self._products.insert_many(docs)
        return [self._product(doc) for doc in docs]
            
            
    def get_product(self, product_id: str) -> Product | None:
        """Return the product with ``product_id`` (entities materialized at fetch time).

        Never raises: an unknown or malformed id yields ``None``.
        """
        LOGGER.info("get_product(%r)", product_id)
        #raise NotImplementedError("TODO: implement 'get_product' using MongoDB")
        # Vérifier que l'identifiant MongoDB est valide
        if not isinstance(product_id, str):
            return None
        doc = self._products.find_one({"_id": product_id})
        return self._product(doc) if doc else None

    def update_product(self, product: Product) -> Product:
        """Fully replace the mutable fields of the stored product targeted by ``product.id``.

        An unknown or malformed ``product.id`` raises
        ``repository.EntityNotFoundError``. The argument ``created_at`` is
        IGNORED: the stored value is kept. ``category`` / ``brand`` are
        re-bound BY NAME: the argument entity ids are ignored, an unknown name
        is auto-created, and ``None`` detaches the product from that entity.
        The repository does NOT re-validate the fields: it trusts the typed
        product. Returns the updated product.
        """
        LOGGER.info("update_product(%r, %r)", product.id, product.name)
        if not isinstance(product.id, str) or not self._products.find_one({"_id": product.id}, {"_id": 1}):
            raise EntityNotFoundError(f"product id {product.id!r} not found")
        fields = self._document(product)
        fields.pop("created_at")
        doc = self._products.find_one_and_update(
            {"_id": product.id}, {"$set": fields}, return_document=ReturnDocument.AFTER
        )
        if doc is None:
            raise EntityNotFoundError(f"product id {product.id!r} not found")
        return self._product(doc)        

    def list_products(self, query: ProductQuery) -> ProductPage:
        """Filter, sort and paginate products according to ``query``.

        ``price_min`` / ``price_max`` are inclusive; the ``category`` /
        ``brand`` filters are by NAME (exact, case-sensitive);
        ``search_text`` is a case-insensitive substring match on the product
        name or description. Ties on ``sort_field`` are broken by ``id`` ascending.
        """
        LOGGER.info("list_products(%r)", query)
        filters = {}
        if query.category is not None:
            filters["category.name"] = query.category
        if query.brand is not None:
            filters["brand.name"] = query.brand
        price = {}
        if query.price_min is not None:
            price["$gte"] = query.price_min
        if query.price_max is not None:
            price["$lte"] = query.price_max
        if price:
            filters["price"] = price
        if query.min_rating is not None:
            filters["rating"] = {"$gte": query.min_rating}
        if query.in_stock is not None:
            filters["stock"] = {"$gt": 0} if query.in_stock else 0
        if query.search_text is not None:
            pattern = re.escape(query.search_text)
            filters["$or"] = [
                {"name": {"$regex": pattern, "$options": "i"}},
                {"description": {"$regex": pattern, "$options": "i"}},
            ]

        total = self._products.count_documents(filters)
        page_size = max(1, min(100, query.page_size))
        page = max(1, query.page)
        total_pages = (total + page_size - 1) // page_size if total else 0
        direction = ASCENDING if query.sort_ascending else DESCENDING
        cursor = (self._products.find(filters)
                  .sort([(query.sort_field, direction), ("_id", ASCENDING)])
                  .skip((page - 1) * page_size).limit(page_size))
        return ProductPage(
            items=[self._product(doc) for doc in cursor],
            total=total, page=page, page_size=page_size, total_pages=total_pages,
        )        

    def delete_product(self, product_id: str) -> None:
        """Delete the product with ``product_id``; returns ``None``.

        An unknown or malformed id raises ``repository.EntityNotFoundError``.
        """
        LOGGER.info("delete_product(%r)", product_id)
        if not isinstance(product_id, str) or self._products.delete_one({"_id": product_id}).deleted_count == 0:
            raise EntityNotFoundError(f"product id {product_id!r} not found")
        

    def get_stats(self) -> CatalogStats:
        """Return whole-catalog statistics.

        ``total`` is the number of products in the catalog: a plain count of
        stored products, not a total price, not a total stock, and not a
        count of distinct product names. ``by_category`` contains ONLY
        products that HAVE a category, keyed by the current category name and
        sorted by codepoint order; uncategorized products are excluded from
        ``by_category`` (they still count in ``total`` / ``average_price``).
        """
        LOGGER.info("get_stats()")
        overall = list(self._products.aggregate([
            {"$group": {"_id": None, "total": {"$sum": 1}, "average": {"$avg": "$price"}}}
        ]))
        if not overall:
            return CatalogStats(total=0, average_price=0.0, by_category={})
        groups = self._products.aggregate([
            {"$match": {"category": {"$ne": None}}},
            {"$group": {
                "_id": "$category.name", "count": {"$sum": 1},
                "average": {"$avg": "$price"},
                "value": {"$sum": {"$multiply": ["$price", "$stock"]}},
            }},
            {"$sort": {"_id": 1}},
        ])
        return CatalogStats(
            total=overall[0]["total"], average_price=overall[0]["average"],
            by_category={g["_id"]: CategoryStats(
                count=g["count"], average_price=g["average"], total_value=g["value"]
            ) for g in groups},
        )

    def ensure_indexes(self) -> None:
        """Ensure backend indexes exist. Idempotent."""
        LOGGER.info("ensure_indexes()")
        # Not required immediately. Can be implemented later.
        pass

    def list_categories(self) -> list[Category]:
        """Return every category, sorted by name ascending (codepoint order).

        Categories are created implicitly when products are saved with an
        unknown name.
        """
        LOGGER.info("list_categories()")
        #raise NotImplementedError("TODO: implement 'list_categories' using MongoDB")
        return self._list_entities(self._categories, Category)

    def _list_entities(self, collection, entity_type):
        return [entity_type(id=doc["_id"], name=doc["name"])
                for doc in collection.find().sort("name", ASCENDING)]

    def get_category(self, category_id: str) -> Category | None:
        """Return the category with ``category_id`` or ``None``.

        Never raises: an unknown or malformed id yields ``None``. Categories
        are created implicitly when products are saved with an unknown name.
        """
        LOGGER.info("get_category(%r)", category_id)
        if not isinstance(category_id, str):
            return None

        doc = self._categories.find_one({"_id": category_id})

        if doc is None:
            return None

        return Category(id=doc["_id"], name=doc["name"])

    def rename_category(self, category_id: str, new_name: str) -> Category:
        """Rename the category; ``new_name`` is trimmed.

        An unknown or malformed ``category_id`` raises
        ``repository.EntityNotFoundError``; a name identical to the current
        one (case-sensitive) is a no-op returning the entity. Whether the
        ``id`` is preserved across a rename is implementation-defined (see
        the ``Category.id`` / ``Brand.id`` docstrings); every product
        referencing the category carries the new name at the next fetch.
        Returns the renamed entity.
        """
        LOGGER.info("rename_category(%r, %r)", category_id, new_name)

        category = self.get_category(category_id)

        if category is None:
            raise EntityNotFoundError(f"category id {category_id!r} not found")

        new_name = new_name.strip()

        if category.name == new_name:
            return category

        self._categories.update_one(
            {"_id": category_id},
            {"$set": {"name": new_name}}
        )

        self._products.update_many(
            {"category.id": category_id},
            {"$set": {"category.name": new_name}}
        )
        return Category(id=category_id, name=new_name)

    def delete_category(self, category_id: str) -> int:
        """Delete the category; returns the number of products affected.

        Every product that carried the category is detached (its ``category``
        becomes ``None``; the product survives, nothing is deleted on the
        product side). An unknown or malformed id raises
        ``repository.EntityNotFoundError``. The count is 0 for an orphaned
        category.
        """
        LOGGER.info("delete_category(%r)", category_id)

        category = self.get_category(category_id)

        if category is None:
            raise EntityNotFoundError(f"category id {category_id!r} not found")

        result = self._products.update_many(
            {"category.id": category_id},
            {"$set": {"category": None}}
        )

        self._categories.delete_one({"_id": category_id})

        return result.modified_count

    def list_brands(self) -> list[Brand]:
        LOGGER.info("list_brands()")
        return [
            Brand(id=doc["_id"], name=doc["name"])
            for doc in self._brands.find().sort("name", ASCENDING)
        ]

    def get_brand(self, brand_id: str) -> Brand | None:
        """Return the brand with ``brand_id`` or ``None``.

        Never raises: an unknown or malformed id yields ``None``. Brands are
        created implicitly when products are saved with an unknown name.
        """
        LOGGER.info("get_brand(%r)", brand_id)

        if not isinstance(brand_id, str):
            return None

        doc = self._brands.find_one({"_id": brand_id})

        if doc is None:
            return None

        return Brand(id=doc["_id"], name=doc["name"])

    def rename_brand(self, brand_id: str, new_name: str) -> Brand:
        """Rename the brand; ``new_name`` is trimmed.

        An unknown or malformed ``brand_id`` raises
        ``repository.EntityNotFoundError``; a name identical to the current
        one (case-sensitive) is a no-op returning the entity. Whether the
        ``id`` is preserved across a rename is implementation-defined (see
        the ``Category.id`` / ``Brand.id`` docstrings); every product
        referencing the brand carries the new name at the next fetch. Returns
        the renamed entity.
        """
        LOGGER.info("rename_brand(%r, %r)", brand_id, new_name)
        brand = self.get_brand(brand_id)
        if brand is None:
            raise EntityNotFoundError(f"brand id {brand_id!r} not found")
        new_name = new_name.strip()
        if brand.name == new_name:
            return brand
        self._brands.update_one(
            {"_id": brand_id},
            {"$set": {"name": new_name}}
        )
        self._products.update_many(
            {"brand.id": brand_id},
            {"$set": {"brand.name": new_name}}
        )
        return Brand(id=brand_id, name=new_name)

    def delete_brand(self, brand_id: str) -> int:
        """Delete the brand; returns the number of products affected.

        Every product that carried the brand is detached (its ``brand``
        becomes ``None``; the product survives, nothing is deleted on the
        product side). An unknown or malformed id raises
        ``repository.EntityNotFoundError``. The count is 0 for an orphaned
        brand.
        """
        LOGGER.info("delete_brand(%r)", brand_id)
        brand = self.get_brand(brand_id)
        if brand is None:
            raise EntityNotFoundError(f"brand id {brand_id!r} not found")
        result = self._products.update_many(
            {"brand.id": brand_id},
            {"$set": {"brand": None}}
        )
        self._brands.delete_one({"_id": brand_id})
        return result.modified_count
