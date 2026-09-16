# Python Advanced: Домашнее задание 4

- **Источник LMS:** <https://lms.itcareerhub.de/mod/assign/view.php?id=15667>
- **Статус:** точное условие, без решения

Задача 1: Наполнение данными
Добавьте в базу данных следующие категории и продукты

Добавление категорий: Добавьте в таблицу categories следующие категории:

Название: "Электроника", Описание: "Гаджеты и устройства."

Название: "Книги", Описание: "Печатные книги и электронные книги."

Название: "Одежда", Описание: "Одежда для мужчин и женщин."

Добавление продуктов: Добавьте в таблицу products следующие продукты, убедившись, что каждый продукт связан с соответствующей категорией:

Название: "Смартфон", Цена: 299.99, Наличие на складе: True, Категория: Электроника

Название: "Ноутбук", Цена: 499.99, Наличие на складе: True, Категория: Электроника

Название: "Научно-фантастический роман", Цена: 15.99, Наличие на складе: True, Категория: Книги

Название: "Джинсы", Цена: 40.50, Наличие на складе: True, Категория: Одежда

Название: "Футболка", Цена: 20.00, Наличие на складе: True, Категория: Одежда


Задача 2: Чтение данных

Извлеките все записи из таблицы categories. Для каждой категории извлеките и выведите все связанные с ней продукты, включая их названия и цены.



Задача 3: Обновление данных

Найдите в таблице products первый продукт с названием "Смартфон". Замените цену этого продукта на 349.99.



Задача 4: Агрегация и группировка

Используя агрегирующие функции и группировку, подсчитайте общее количество продуктов в каждой категории.



Задача 5: Группировка с фильтрацией

Отфильтруйте и выведите только те категории, в которых более одного продукта.

## Решение


```python
"""Домашнее задание 4: запросы к категориям и продуктам."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, create_engine, func, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


class Base(DeclarativeBase):
    """Базовый класс декларативных моделей."""


class Category(Base):
    """Категория, в которой может находиться несколько продуктов."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    products: Mapped[list[Product]] = relationship(back_populates="category")


class Product(Base):
    """Продукт, связанный с одной категорией."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column(Boolean)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    category: Mapped[Category] = relationship(back_populates="products")


# Создаём SQLite-базу в памяти и таблицы из описанных моделей.
engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


with Session() as session:
    # Задача 1: добавляем категории и сохраняем их в базе.
    categories = {
        "Электроника": Category(
            name="Электроника",
            description="Гаджеты и устройства.",
        ),
        "Книги": Category(
            name="Книги",
            description="Печатные книги и электронные книги.",
        ),
        "Одежда": Category(
            name="Одежда",
            description="Одежда для мужчин и женщин.",
        ),
    }
    session.add_all(categories.values())

    products = [
        Product(
            name="Смартфон",
            price=Decimal("299.99"),
            in_stock=True,
            category=categories["Электроника"],
        ),
        Product(
            name="Ноутбук",
            price=Decimal("499.99"),
            in_stock=True,
            category=categories["Электроника"],
        ),
        Product(
            name="Научно-фантастический роман",
            price=Decimal("15.99"),
            in_stock=True,
            category=categories["Книги"],
        ),
        Product(
            name="Джинсы",
            price=Decimal("40.50"),
            in_stock=True,
            category=categories["Одежда"],
        ),
        Product(
            name="Футболка",
            price=Decimal("20.00"),
            in_stock=True,
            category=categories["Одежда"],
        ),
    ]
    session.add_all(products)
    session.commit()

    # Задача 2: читаем категории и все продукты через relationship.
    print("Продукты по категориям:")
    for category in session.scalars(select(Category).order_by(Category.id)):
        print(f"{category.name}:")
        for product in category.products:
            print(f"  - {product.name}: {product.price:.2f}")

    # Задача 3: находим первый продукт с таким названием и меняем его цену.
    smartphone = session.scalars(
        select(Product)
        .where(Product.name == "Смартфон")
        .order_by(Product.id)
    ).first()
    if smartphone is None:
        raise LookupError("Продукт 'Смартфон' не найден")

    smartphone.price = Decimal("349.99")
    session.commit()
    print(f"Новая цена смартфона: {smartphone.price:.2f}")

    # Задача 4: считаем количество продуктов в каждой категории.
    product_counts = session.execute(
        select(
            Category.name,
            func.count(Product.id).label("product_count"),
        )
        .join(Product, Product.category_id == Category.id)
        .group_by(Category.id, Category.name)
        .order_by(Category.id)
    ).all()

    print("Количество продуктов по категориям:")
    for category_name, product_count in product_counts:
        print(f"  - {category_name}: {product_count}")

    # Задача 5: оставляем только группы, где продуктов больше одного.
    categories_with_many_products = session.execute(
        select(
            Category.name,
            func.count(Product.id).label("product_count"),
        )
        .join(Product, Product.category_id == Category.id)
        .group_by(Category.id, Category.name)
        .having(func.count(Product.id) > 1)
        .order_by(Category.id)
    ).all()

    print("Категории более чем с одним продуктом:")
    for category_name, product_count in categories_with_many_products:
        print(f"  - {category_name}: {product_count}")
```
