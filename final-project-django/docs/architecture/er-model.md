# ER/3NF-модель — финальный проект LMS №271

**Исходное ревью:** 17.11.2026. **Актуализация 21.11.2026:** новые `listings.0004`/`bookings.0004` проверены на клоне и основной локальной MySQL; 90/90 тестов PASS. Подробности — [проверке моделей](../model-integrity-2026-11-21.md). Решения D01–D14, источники и оставшиеся вопросы: [decisions.md](decisions.md). Диаграмма: [er-diagram.mmd](er-diagram.mmd).

## Состав и связи

**9 логических сущностей:** CustomUser, штатная Django Group, City, District, Listing, Booking, Review, SearchEvent, ViewEvent. **10 узлов диаграммы** с автоматической связующей таблицей User.groups. Встроенные auth/admin/token таблицы инфраструктурные и здесь не перечисляются. Отдельного Property **нет**: один Listing является сдаваемой единицей жилья, местом, предложением и долговечным идентификатором для отзывов и бронирований; адресная уникальность не вводится. Это сознательное упрощение, а не требование LMS. Не исключает обхода рейтинга путём создания нового дубликата — такой риск остаётся.

| Таблица (app) | Атрибуты и ключи | Правила |
|---|---|---|
| CustomUser (accounts) | PK BigAutoField, email UNIQUE, display_name, password, is_active, date_joined, штатные поля AbstractUser/PermissionsMixin | AUTH_USER_MODEL до первой миграции, email для логина; нормализация и проверка case-insensitive уникальности на конкретной MySQL collation |
| auth.Group + User.groups | штатная Django auth_group и M2M через user_id/group_id UNIQUE вместе | Tenant и Landlord не исключают друг друга, User.role запрещён; регистрация назначает Tenant, Landlord — доверенный staff/seed |
| City / District (listings) | City(name UNIQUE), District(city FK, name), UNIQUE(city,name) | Контролируемые географические справочники, расширяемые Django admin |
| Listing (listings) | PK, landlord FK User, city FK City, district FK District nullable, legacy_city/legacy_district (архив), title, description, country_code, postal_code, street, house_number, unit_number, housing_type Choices, rooms, price_per_night Decimal, is_active, deleted_at, created_at, updated_at | Справочники вместо свободного текста; legacy-значения только для сверки. country_code DE, 1 <= rooms <= 100, price>0, нет UNIQUE адреса, soft DELETE |
| Booking (bookings) | PK, listing FK, tenant FK, check_in, check_out, status Choices, total_price Decimal(13,2) nullable для legacy, cancelled_at, created_at, updated_at | Снимок стоимости новых броней, CHECK CANCELLED ⇔ cancelled_at NOT NULL, CHECK total_price>0 либо NULL исторический; PROTECT сохраняет историю |
| Review (reviews) | PK, booking OneToOne UNIQUE, rating, comment, created_at, updated_at | рейтинг 1–5; автор и Listing определяются через Booking, не дублируются; отзыв после завершённой CONFIRMED брони, создание до checkout+30 включительно |
| SearchEvent (statistics, дополнительно) | PK, user nullable FK, query_text, created_at | нормализованный непустой поисковый текст; без IP, cookies и user agent |
| ViewEvent (statistics, дополнительно) | PK, listing FK, viewer nullable FK, created_at | событие открытия объявления, агрегат просмотров вычисляется |

CustomUser 1:N Listing (landlord); CustomUser 1:N Booking (tenant); Listing 1:N Booking; Booking 1:0..1 Review; User M:N Group через штатную M2M; User 0:N SearchEvent/ViewEvent и Listing 1:N ViewEvent. Поля FK у nullable-событий допускают отсутствие пользователя.

## Проверка 3NF

Атомарность полей удовлетворяет 1NF. Таблицы с одиночными PK не имеют частичных зависимостей, у M2M уникальна пара FK (2NF). Города и районы вынесены в справочники; точный старый ввод оставлен архивом для ручной сверки. При известном районе District.city определяет город, но Listing хранит city и nullable district для объявлений без района. Это осознанная избыточность, а не строгая 3NF для этой части схемы. Согласованность пары проверяется при записи через API на актуальной заблокированной строке, модельной валидацией и запретом смены города существующего района в admin. Два FK сами по себе не выражают межтабличный инвариант; прямые записи в обход сервисов остаются границей гарантии. Тариф за ночь и адрес зависят от Listing, а стоимость зафиксированного периода зависит от Booking; даты, статус и арендатор — от Booking; оценка — от Review; у Review нет собственного tenant/listing FK, которые были бы транзитивно получены через Booking. В списке пользователей не хранить группы в строковом поле, а в Listing — рейтинг, число просмотров и число ночей: вычислять из связанных строк (3NF). Формальную проверку ограничений выполнить после генерации миграций.

## Правила ссылочной целостности и валидаторы

- PK/FK/NOT NULL/UNIQUE: User.email, Review.booking_id и штатная User.groups(user_id,group_id). DB CHECK: 1 <= Listing.rooms <= 100, Listing.price_per_night>0, Booking.check_in<check_out, Review.rating BETWEEN 1 AND 5 на проверенной версии MySQL (CHECK применяются MySQL начиная с 8.0.16).
- FK Booking.listing, Booking.tenant, Listing.landlord, Review.booking: Django on_delete=PROTECT для истории. Это ORM-поведение; SQL FK сами по себе нельзя представлять как автоматически созданное ON DELETE PROTECT. Для аналитики user/viewer nullable; стратегию физического удаления/анонимизации определить до публикации.
- Инварианты, которые CHECK не выражает: check_in > текущей даты Europe/Berlin для новой PENDING-заявки, период не дальше 365 дней, длительность 1–365 ночей (проектные ограничения, не LMS); права и членство в Groups; доступность Listing; невозможность брони собственником; отсутствие пересечений CONFIRMED; право отзыва только для завершённого проживания и создание не позднее checkout+30 календарных дней (Europe/Berlin, в сервисе create_review; PATCH не ограничен этим сроком). Первые проверки дат/доступности/self-booking реализованы в `Booking.clean()`, eligibility — в `Review.clean()`, но сервисы API должны явно вызывать валидацию. Отсутствие пересечений подтвердить транзакционным сервисом на этапе 4.
- Choices должны использоваться в Django и валидироваться в сервисе/DRF; MySQL не гарантирует их без дополнительного DB CHECK. Отсутствие ключа группы в запросе не должно самовольно давать Landlord.
- Неактивные и soft-deleted Listing исключаются из публичной выдачи; исторические Booking/Review не удаляются. Подтверждённые брони при деактивации/удалении Listing сохраняются.

## Бронирование: конечный автомат

PENDING -> CONFIRMED или REJECTED или CANCELLED. CONFIRMED -> CANCELLED **только до check_in**, в другое время перехода нет. REJECTED и CANCELLED терминальны. Завершённая бронь — это CONFIRMED, у которой check_out <= timezone.localdate(); отдельный статус COMPLETED не нужен.

Отмена разрешена только Tenant и только когда localdate (Europe/Berlin) меньше check_in, и для PENDING, и для CONFIRMED. Эта политика выбрана в отсутствие точных часов в LMS. Landlord может отклонить только PENDING. PENDING заявки могут пересекаться и не блокируют даты; блокирует только CONFIRMED. Подтверждать PENDING в день check_in или позже или для неактивного/удалённого Listing нельзя. Повторный конфликтующий переход — HTTP 409. active = будущие PENDING и не завершённые CONFIRMED; completed = завершённые CONFIRMED; остальные доступны через историю/status.

Полуоткрытые даты: [check_in,check_out), выезд — первый день после проживания; примыкающие интервалы не конфликтуют. Предикат: existing.check_in < new.check_out AND existing.check_out > new.check_in, только confirmed, того же listing.

## MySQL: конкурентное подтверждение

Все изменения состояния Booking, влияющие на календарь, выполняются единым сервисным маршрутом с порядком блокировок. Внутри transaction.atomic получить SELECT FOR UPDATE **строки Listing по PK**, затем прочитать состояние брони и пересечения среди CONFIRMED из свежего запроса, проверить права/статусы, обновить, зафиксировать. Использовать InnoDB и READ COMMITTED. Два подтверждения одного Listing сериализуются по одной строке; нельзя использовать сделанную до блокировки проверку. Обрабатывать deadlock/timeout и rollback. Параллельная TransactionTestCase с отдельными соединениями на реальной MySQL обязательна для технической приёмки; SQLite не подходит. CHECK/UNIQUE MySQL не могут выразить отсутствие перекрытия между строками; прямые SQL-записи в обход сервиса остаются риском.

## Индексы и запросы

- В MySQL-миграциях реально созданы Listing(landlord_id,deleted_at), Listing(city_id,district_id), Booking(listing_id,status,check_in,check_out), Booking(tenant_id,status). Состав индексов проверен в information_schema.STATISTICS 17.11.2026. Для Choices использована `utf8mb4_0900_bin` (сравнение строго по регистру и пробелам); email остаётся регистронезависимым. Для оценки селективности на объёмных данных EXPLAIN предстоит позднее.
- Индекс на один is_active/status не добавлять. Цена и created_at сортируются с обязательным tie-breaker id; поисковое icontains '%text%' может не использовать B-tree, проверить это отдельно.
- Review.booking_id обеспечен уникальным индексом; ViewEvent(listing_id,created_at) и SearchEvent(created_at) добавлять по сценариям/EXPLAIN, не заранее.

## Контракты API и тестов

| Область | Предлагаемые маршруты | Доказательство |
|---|---|---|
| accounts | register, login, logout (JWT + blacklist refresh) | уникальный email, две группы, только доверенное назначение Landlord, token/logout |
| listings | CRUD/soft DELETE, is_active; search, city, district, rooms, price, housing_type, ordering | права, фильтры, спрятанное удалённое, N+1, сохранение истории |
| bookings | create, list active/completed/history, confirm/reject/cancel | даты и переходы, две конкурирующие транзакции, rollback |
| reviews | create, list for listing, edit own | завершённость, booking UNIQUE, запреты чужих изменений |
| statistics | GET /api/statistics/{search-history,view-history,popular-searches,popular-listings}/; listing ?ordering=popular | записи событий только при успешных GET, личная история только своя, топы без viewer, порог трёх авторизованных пользователей |

**Подтверждено 17.11.2026:** Python 3.14.10, Django 5.2.19, MySQL 26.10.0, accounts.0001_initial до остальных прикладных миграций, группы accounts.0002, InnoDB/utf8mb4, CHECK/UNIQUE/FK/индексы, 21 MySQL-тест и 15 параметризованных проверок, HTTP smoke. Дополнительные ограничения Choices и SearchEvent проверены отдельными миграциями 0002/0003. **Остаётся:** EXPLAIN на представительном наборе данных, конкурирующий TransactionTestCase и сервисы Booking/Review. Вне рамок: платежи, frontend, физическая верификация адреса/собственника, перенос Listing между владельцами, AWS до согласования.
