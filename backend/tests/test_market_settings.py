"""Per-market configuration: validation, storage and what it changes downstream.

Uses a fake session instead of a real one — the service only ever calls
`db.get(Practice, ...)` and `db.commit()`, so a stub exercises the whole write
path honestly and keeps these tests runnable with no database.
"""

from __future__ import annotations

import uuid

import pytest

from src.models.practice import Practice
from src.schemas.ai_receptionist import MarketSettingsUpdate
from src.server.exceptions import AppException, NotFoundException
from src.services.ai_receptionist.locale_service import LocaleService
from src.services.ai_receptionist.market_settings_service import MarketSettingsService
from src.services.ai_receptionist.prompt_blocks import build_system_prompt

PRACTICE_ID = uuid.uuid4()
OWNER_ID = uuid.uuid4()


class _FakeDB:
    """Just enough session for this service: fetch one practice, commit."""

    def __init__(self, practice: Practice | None):
        self.practice = practice
        self.commits = 0

    async def get(self, _model, _id):
        return self.practice

    async def commit(self):
        self.commits += 1


def _practice(settings: dict | None = None) -> Practice:
    return Practice(name="Aiaceone Clinic", settings=settings or {}, timezone="Asia/Karachi")


@pytest.mark.asyncio
async def test_a_saved_market_carries_the_currency_city_prices_and_payment_methods():
    practice = _practice()
    db = _FakeDB(practice)
    service = MarketSettingsService()

    response = await service.save_market(
        db,
        PRACTICE_ID,
        "pk",
        MarketSettingsUpdate(
            currency="pkr",
            clinic_name="Aiaceone Lahore",
            clinic_city="Lahore",
            consultation_fee="PKR 5,000",
            payment_methods="Bank transfer or card at the clinic",
            prices={"Rhinoplasty": "PKR 900,000", "": "PKR 1", "Botox": "  "},
            languages=["English", "Urdu"],
            is_home=True,
        ),
        OWNER_ID,
    )

    pk = next(market for market in response.markets if market.code == "PK")
    assert response.home_market == "PK"
    assert pk.configured is True and pk.is_home is True
    assert pk.currency == "PKR"
    assert pk.clinic_city == "Lahore"
    # Blank procedure names and blank prices are dropped rather than stored.
    assert pk.prices == {"Rhinoplasty": "PKR 900,000"}
    assert pk.languages == ["English", "Urdu"]
    assert practice.settings["markets"]["PK"]["clinic_name"] == "Aiaceone Lahore"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_saving_one_field_does_not_wipe_the_rest_of_the_market():
    practice = _practice()
    db = _FakeDB(practice)
    service = MarketSettingsService()

    await service.save_market(
        db, PRACTICE_ID, "PK",
        MarketSettingsUpdate(clinic_city="Lahore", prices={"Rhinoplasty": "PKR 900,000"}), OWNER_ID,
    )
    response = await service.save_market(
        db, PRACTICE_ID, "PK", MarketSettingsUpdate(consultation_fee="PKR 5,000"), OWNER_ID
    )

    pk = next(market for market in response.markets if market.code == "PK")
    assert pk.clinic_city == "Lahore"
    assert pk.prices == {"Rhinoplasty": "PKR 900,000"}
    assert pk.consultation_fee == "PKR 5,000"


@pytest.mark.asyncio
async def test_an_unsupported_currency_is_refused():
    db = _FakeDB(_practice())

    with pytest.raises(AppException) as excinfo:
        await MarketSettingsService().save_market(
            db, PRACTICE_ID, "PK", MarketSettingsUpdate(currency="BTC"), OWNER_ID
        )

    assert "Unsupported currency" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_an_unknown_market_code_is_refused():
    db = _FakeDB(_practice())

    with pytest.raises(AppException) as excinfo:
        await MarketSettingsService().save_market(
            db, PRACTICE_ID, "Mars", MarketSettingsUpdate(clinic_city="Olympus"), OWNER_ID
        )

    assert "Unknown market" in str(excinfo.value.detail)


@pytest.mark.asyncio
async def test_clearing_a_market_removes_it_and_its_home_status():
    practice = _practice()
    db = _FakeDB(practice)
    service = MarketSettingsService()
    await service.save_market(
        db, PRACTICE_ID, "AE", MarketSettingsUpdate(clinic_city="Dubai", is_home=True), OWNER_ID
    )

    response = await service.clear_market(db, PRACTICE_ID, "AE", OWNER_ID)

    # The cleared market is not left pointing at configuration that no longer
    # exists — home falls back to what can still be inferred (the clinic's own
    # time zone), and the receptionist stops quoting AED.
    assert response.home_market != "AE"
    uae = next(market for market in response.markets if market.code == "AE")
    assert uae.configured is False
    assert uae.currency == uae.default_currency


@pytest.mark.asyncio
async def test_clearing_a_market_that_was_never_configured_is_a_404():
    db = _FakeDB(_practice())

    with pytest.raises(NotFoundException):
        await MarketSettingsService().clear_market(db, PRACTICE_ID, "UK", OWNER_ID)


@pytest.mark.asyncio
async def test_an_unconfigured_market_reports_the_registry_defaults():
    response = await MarketSettingsService().get_settings(_FakeDB(_practice()), PRACTICE_ID)

    uae = next(market for market in response.markets if market.code == "AE")
    assert uae.configured is False
    assert uae.currency == "AED" and uae.default_currency == "AED"
    assert uae.timezone == "Asia/Dubai"
    assert uae.prices == {}


@pytest.mark.asyncio
async def test_the_saved_prices_are_exactly_what_the_prompt_quotes_from():
    """The whole point of the configuration: what the owner typed is what the
    receptionist is allowed to say — and nothing else."""
    practice = _practice()
    db = _FakeDB(practice)
    await MarketSettingsService().save_market(
        db, PRACTICE_ID, "PK",
        MarketSettingsUpdate(
            clinic_city="Lahore",
            prices={"Rhinoplasty": "PKR 900,000"},
            consultation_fee="PKR 5,000",
            payment_methods="Bank transfer",
        ),
        OWNER_ID,
    )

    from datetime import date

    locale = LocaleService().resolve(practice, "kya rhinoplasty ka price kitna hai")
    prompt = build_system_prompt(
        practice_name=practice.name, is_new_patient=True, today=date(2026, 9, 19), draft=None, locale=locale
    )

    assert "PKR 900,000" in prompt
    assert "Bank transfer" in prompt


@pytest.mark.asyncio
async def test_a_currency_override_reaches_the_prompt():
    practice = _practice(settings={"default_market": "AE"})
    db = _FakeDB(practice)
    await MarketSettingsService().save_market(
        db, PRACTICE_ID, "AE", MarketSettingsUpdate(currency="USD", clinic_city="Dubai"), OWNER_ID
    )

    from datetime import date

    locale = LocaleService().resolve(practice, "how much is a rhinoplasty?")
    assert locale.currency == "USD"
    prompt = build_system_prompt(
        practice_name=practice.name, is_new_patient=True, today=date(2026, 9, 19), draft=None, locale=locale
    )
    assert "Currency: USD" in prompt
    assert "Currency: AED" not in prompt
