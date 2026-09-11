# Python Advanced: Домашнее задание 3

- **Источник LMS:** <https://lms.itcareerhub.de/mod/assign/view.php?id=15660>
- **Статус:** точное условие LMS сохранено; решение добавлено ниже отдельным разделом

Задача 1: Создайте экземпляр движка для подключения к SQLite базе данных в памяти.

Задача 2: Создайте сессию для взаимодействия с базой данных, используя созданный движок.

Задача 3: Определите модель продукта Product со следующими типами колонок:

id: числовой идентификатор

name: строка (макс. 100 символов)

price: числовое значение с фиксированной точностью

in_stock: логическое значение

Задача 4: Определите связанную модель категории Category со следующими типами колонок:

id: числовой идентификатор

name: строка (макс. 100 символов)

description: строка (макс. 255 символов)

Задача 5: Установите связь между таблицами Product и Category с помощью колонки category_id.

---

## Решение

```python
"""Домашнее задание 3: модели Product и Category на SQLAlchemy 2.x."""

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Numeric, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker


class Base(DeclarativeBase):
    """Базовый класс для моделей базы данных."""


# Задача 4: связанная модель категории Category.
class Category(Base):
    """Категория, в которой может быть несколько товаров."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    products: Mapped[list["Product"]] = relationship(back_populates="category")


# Задача 3: модель продукта Product.
class Product(Base):
    """Товар, относящийся к одной категории."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column(Boolean)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    category: Mapped[Category] = relationship(back_populates="products")


# Задача 1: движок SQLite в оперативной памяти.
engine = create_engine("sqlite:///:memory:")

# Создаём таблицы по описанным моделям.
Base.metadata.create_all(engine)

# Задача 2: фабрика сессий и экземпляр сессии для работы с БД.
Session = sessionmaker(bind=engine)

with Session() as session:
    # Проверяем связь из задачи 5: Category (одна) -> Product (много).
    electronics = Category(
        name="Электроника",
        description="Электронные устройства",
    )
    laptop = Product(
        name="Ноутбук",
        price=Decimal("999.99"),
        in_stock=True,
        category=electronics,
    )
    session.add(laptop)
    session.commit()

    print(laptop.name)
    print(laptop.category.name)
```
