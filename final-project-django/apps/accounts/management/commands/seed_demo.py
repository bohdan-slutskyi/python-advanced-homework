"""Idempotent, isolated synthetic dataset for development and API demos."""

import os
import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.bookings.models import Booking
from apps.listings.models import City, District, Listing
from apps.reviews.models import Review
from apps.statistics.models import SearchEvent, ViewEvent


class Command(BaseCommand):
    help = "Seed repeatable synthetic rental records without deleting existing data."

    def add_arguments(self, parser):
        parser.add_argument("--seed", type=int, default=271)
        parser.add_argument("--landlords", type=int, default=12)
        parser.add_argument("--tenants", type=int, default=40)
        parser.add_argument("--listings", type=int, default=120)
        parser.add_argument("--bookings", type=int, default=240)
        parser.add_argument("--reviews", type=int, default=80)
        parser.add_argument("--events", type=int, default=600)

    def handle(self, *args, **options):
        landlords_n = options["landlords"]
        tenants_n = options["tenants"]
        listings_n = options["listings"]
        bookings_n = options["bookings"]
        reviews_n = options["reviews"]
        events_n = options["events"]
        if min(landlords_n, tenants_n, listings_n) < 1:
            raise CommandError("Landlords, tenants and listings must be positive.")
        if min(bookings_n, reviews_n, events_n) < 0:
            raise CommandError("Bookings, reviews and events cannot be negative.")
        if bookings_n > listings_n * 5:
            raise CommandError("At most five nonoverlapping booking slots per listing.")
        if reviews_n > min(bookings_n, listings_n):
            raise CommandError("Reviews need completed confirmed bookings.")
        if events_n > tenants_n * listings_n:
            raise CommandError("Events cannot exceed unique tenant/listing pairs.")

        seed = options["seed"]
        fake = Faker("de_DE")
        fake.seed_instance(seed)
        rng = random.Random(seed)
        today = timezone.localdate()
        prior = (
            Booking.objects.filter(
                listing__title__startswith=f"[DEMO {seed}] Listing ",
                status=Booking.Status.CONFIRMED,
            )
            .order_by("check_in")
            .first()
        )
        if prior is not None:
            # Keep the seed's calendar anchor stable across subsequent days.
            today = prior.check_in + timedelta(days=40)
        # Optional from caller environment, never written into files or output.
        password = os.environ.get("DEMO_USER_PASSWORD")
        groups = {role: Group.objects.get(name=role) for role in ("Tenant", "Landlord")}
        User = get_user_model()
        counts = {
            "users": 0,
            "listings": 0,
            "bookings": 0,
            "reviews": 0,
            "search_events": 0,
            "view_events": 0,
        }

        def make_users(role, number):
            result = []
            for i in range(number):
                email = f"demo-{seed}-{role.lower()}-{i:05d}@example.invalid"
                user = User.objects.filter(email=email).first()
                if user is None:
                    user = User.objects.create_user(
                        email=email, display_name=fake.name(), password=password
                    )
                    user.groups.add(groups[role])
                    counts["users"] += 1
                elif not user.groups.filter(pk=groups[role].pk).exists():
                    raise CommandError(
                        f"Existing synthetic account has no {role} group."
                    )
                result.append(user)
            return result

        with transaction.atomic():
            landlords = make_users("Landlord", landlords_n)
            tenants = make_users("Tenant", tenants_n)
            listings = []
            # Only validated city/district pairs, not Faker-generated place names.
            location_options = (
                ("Berlin", "Mitte"),
                ("Berlin", "Kreuzberg"),
                ("Hamburg", None),
                ("Hannover", "Mitte"),
                ("Hannover", "List"),
                ("Köln", None),
            )
            housing_types = list(Listing.HousingType.values)
            for i in range(listings_n):
                landlord = landlords[i % landlords_n]
                title = f"[DEMO {seed}] Listing {i:05d}"
                listing = Listing.objects.filter(landlord=landlord, title=title).first()
                if listing is None:
                    city_name, district_name = rng.choice(location_options)
                    city = City.objects.get(name=city_name)
                    district = (
                        District.objects.get(city=city, name=district_name)
                        if district_name
                        else None
                    )
                    listing = Listing(
                        landlord=landlord,
                        title=title,
                        description=fake.paragraph(nb_sentences=3),
                        city=city,
                        district=district,
                        postal_code=fake.postcode(),
                        street=fake.street_name(),
                        house_number=str(rng.randint(1, 99)),
                        housing_type=housing_types[i % len(housing_types)],
                        rooms=rng.randint(1, 5),
                        price_per_night=Decimal(rng.randint(40, 240)),
                    )
                    listing.full_clean()
                    listing.save()
                    counts["listings"] += 1
                listings.append(listing)

            bookings = []
            for i in range(bookings_n):
                listing = listings[i % listings_n]
                slot = i // listings_n
                # Past completed stay, future confirmed, pending, rejected, cancelled.
                status = (
                    Booking.Status.CONFIRMED,
                    Booking.Status.CONFIRMED,
                    Booking.Status.PENDING,
                    Booking.Status.REJECTED,
                    Booking.Status.CANCELLED,
                )[slot]
                check_in = today + timedelta(days=(-40, 20, 40, 60, 80)[slot])
                check_out = check_in + timedelta(days=3)
                tenant = tenants[i % tenants_n]
                # A seed's stable listing/slot identifies exactly one sample booking.
                booking = Booking.objects.filter(
                    listing=listing,
                    tenant=tenant,
                    check_in=check_in,
                    check_out=check_out,
                ).first()
                if booking is None:
                    booking = Booking(
                        listing=listing,
                        tenant=tenant,
                        check_in=check_in,
                        check_out=check_out,
                        status=status,
                        total_price=listing.price_per_night
                        * Decimal((check_out - check_in).days),
                        cancelled_at=(
                            timezone.now()
                            if status == Booking.Status.CANCELLED
                            else None
                        ),
                    )
                    booking.full_clean()
                    booking.save()
                    counts["bookings"] += 1
                bookings.append(booking)

            for i in range(reviews_n):
                booking = bookings[i]  # First slot is a confirmed past stay.
                if not Review.objects.filter(booking=booking).exists():
                    review = Review(
                        booking=booking,
                        rating=rng.randint(1, 5),
                        comment=fake.sentence(nb_words=12),
                    )
                    review.full_clean()
                    review.save()
                    counts["reviews"] += 1

            for i in range(events_n):
                tenant = tenants[i % tenants_n]
                listing = listings[(i // tenants_n) % listings_n]
                query = f"demo-{seed} city-{i // tenants_n}"
                # These are append-only event logs, not unique user/query or
                # viewer/listing pairs. Existing duplicates are legitimate.
                if not SearchEvent.objects.filter(
                    user=tenant, query_text=query
                ).exists():
                    SearchEvent.objects.create(user=tenant, query_text=query)
                    counts["search_events"] += 1
                if not ViewEvent.objects.filter(
                    viewer=tenant, listing=listing
                ).exists():
                    ViewEvent.objects.create(viewer=tenant, listing=listing)
                    counts["view_events"] += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Synthetic seed={seed}: "
                + ", ".join(f"{name}={count} new" for name, count in counts.items())
            )
        )
