"""Python Advanced: Домашнее задание 2

Разработать систему регистрации пользователя, используя Pydantic для валидации
входных данных, обработки вложенных структур и сериализации. Система должна
обрабатывать данные в формате JSON.

Задачи:
Создать классы моделей данных с помощью Pydantic для пользователя и его адреса.

Реализовать функцию, которая принимает JSON строку, десериализует её в объекты
Pydantic, валидирует данные, и в случае успеха сериализует объект обратно в JSON
и возвращает его.

Добавить кастомный валидатор для проверки соответствия возраста и статуса
занятости пользователя.

Написать несколько примеров JSON строк для проверки различных сценариев
валидации: успешные регистрации и случаи, когда валидация не проходит
(например возраст не соответствует статусу занятости).

Модели:

Address: Должен содержать следующие поля:
city: строка, минимум 2 символа.
street: строка, минимум 3 символа.
house_number: число, должно быть положительным.

User: Должен содержать следующие поля:
name: строка, должна быть только из букв, минимум 2 символа.
age: число, должно быть между 0 и 120.
email: строка, должна соответствовать формату email.
is_employed: булево значение, статус занятости пользователя.
address: вложенная модель адреса.

Валидация:
Проверка, что если пользователь указывает, что он занят (is_employed = true),
его возраст должен быть от 18 до 65 лет.

Пример JSON данных для регистрации пользователя:

json_input = '''{
    "name": "John Doe",
    "age": 70,
    "email": "john.doe@example.com",
    "is_employed": true,
    "address": {
        "city": "New York",
        "street": "5th Avenue",
        "house_number": 123
    }
}'''

Уточнение преподавателя:
вместо входного поля age используется date_of_birth. Возраст вычисляется
динамически на текущую дату с учётом того, наступил ли день рождения.
"""

import json
from datetime import date
from typing import Annotated

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


class Address(BaseModel):
    """Вложенная модель адреса."""

    city: Annotated[str, Field(min_length=2)]
    street: Annotated[str, Field(min_length=3)]
    house_number: Annotated[int, Field(gt=0)]


class User(BaseModel):
    """Данные регистрации и правила проверки пользователя."""

    name: Annotated[str, Field(min_length=2)]
    date_of_birth: date
    email: EmailStr
    is_employed: bool
    address: Address

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        """Разрешаем только буквы и пробелы между частями полного имени."""
        normalized_name = " ".join(value.split())
        if not normalized_name or not all(part.isalpha() for part in normalized_name.split()):
            raise ValueError("Имя должно состоять только из букв")
        return normalized_name

    @property
    def age(self) -> int:
        """Возраст вычисляется на сегодня, с учётом того, был ли день рождения."""
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day)
            < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @model_validator(mode="after")
    def validate_age_and_employment(self) -> "User":
        if not 0 <= self.age <= 120:
            raise ValueError("Возраст должен быть от 0 до 120 лет")
        if self.is_employed and not 18 <= self.age <= 65:
            raise ValueError(
                "Работающий пользователь должен быть в возрасте от 18 до 65 лет"
            )
        return self


def register_user(json_input: str) -> str:
    """Валидирует JSON регистрации и возвращает проверенную модель как JSON."""
    user = User.model_validate_json(json_input)
    return user.model_dump_json(indent=4)


def date_for_age(years: int) -> date:
    """Создаёт дату рождения для демонстрационного примера на текущую дату."""
    today = date.today()
    try:
        return today.replace(year=today.year - years)
    except ValueError:  # 29 февраля в невисокосном целевом году
        return today.replace(year=today.year - years, day=28)


def make_json_example(*, name: str, age: int, is_employed: bool) -> str:
    """Формирует JSON, чтобы примеры не устаревали с течением времени."""
    return json.dumps(
        {
            "name": name,
            "date_of_birth": date_for_age(age).isoformat(),
            "email": "john.doe@example.com",
            "is_employed": is_employed,
            "address": {
                "city": "New York",
                "street": "Fifth Avenue",
                "house_number": 123,
            },
        }
    )


EXAMPLES = {
    "Успешная регистрация работающего пользователя (30 лет)": make_json_example(
        name="John Doe", age=30, is_employed=True
    ),
    "Успешная регистрация неработающего пользователя (16 лет)": make_json_example(
        name="Anna Smith", age=16, is_employed=False
    ),
    "Ошибка: работающий пользователь младше 18 лет": make_json_example(
        name="Mark Lee", age=17, is_employed=True
    ),
    "Ошибка: работающий пользователь старше 65 лет": make_json_example(
        name="Maria Stone", age=66, is_employed=True
    ),
}


def run_examples() -> None:
    """Запускает успешные и неуспешные сценарии из условия задания."""
    for title, json_input in EXAMPLES.items():
        print(f"\n{title}")
        try:
            serialized_user = register_user(json_input)
            user = User.model_validate_json(json_input)
            print(f"Возраст: {user.age}")
            print(serialized_user)
        except ValidationError as error:
            print(error)


if __name__ == "__main__":
    run_examples()
