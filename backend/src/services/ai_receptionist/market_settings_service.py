"""The practice's own per-market configuration — what the receptionist is
allowed to quote, and where.

The SOP is unambiguous that the AI must never state a price that is not on the
relevant market's approved list, and must never convert between currencies
(s7, s10.1). That makes this configuration load-bearing rather than cosmetic:
`prompt_blocks` reads it to build the market block, and a market with no price
list produces an explicit "do not state a figure" instruction instead of a
plausible-sounding number.

Storage is `Practice.settings["markets"][<code>]` — the same JSONB blob the
system prompt and Green API credentials already live in, so there is no
migration and a practice can be configured before it has ever been live:

    "markets": {
      "PK": {
        "currency": "PKR",
        "clinic_name": "Aiaceone Lahore",
        "clinic_city": "Lahore",
        "consultation_fee": "PKR 5,000",
        "payment_methods": "Bank transfer or card at the clinic",
        "prices": {"Rhinoplasty": "PKR 900,000"},
        "languages": ["English", "Urdu"]
      }
    },
    "default_market": "PK"

Every field is optional and every empty value is removed on save, so "cleared
this" and "never configured" end up in the same state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.practice import Practice
from src.schemas.ai_receptionist import (
    ClinicLocation,
    MarketSettings,
    MarketSettingsUpdate,
    MarketsSettingsResponse,
)
from src.server.exceptions import AppException, NotFoundException
from src.services.ai_receptionist.markets import (
    MARKETS,
    MARKET_CODES,
    MarketConfig,
    default_market_code,
    market_config,
    normalize_market_code,
)

SETTINGS_KEY = "markets"
HOME_MARKET_KEY = "default_market"
SETTINGS_UPDATED_AT_KEY = "markets_updated_at"
SETTINGS_UPDATED_BY_KEY = "markets_updated_by"

# Currencies a practice may actually trade in. Deliberately small: the AI is told
# to name one currency per message and never convert, so a code that nothing
# else in the app understands (`Invoice.currency` is free text too, which is
# exactly how PKR/USD drift starts) is worth refusing at the door.
SUPPORTED_CURRENCIES: tuple[str, ...] = ("PKR", "AED", "SAR", "USD", "GBP", "EUR")

_MAX_PRICE_ROWS = 60
_MAX_WORD_LENGTH = 200
_MAX_LANGUAGES = 8
_MAX_CLINICS = 12


class MarketSettingsService:
    """Read and write the per-market block the receptionist quotes from."""

    async def get_settings(self, db: AsyncSession, practice_id: UUID) -> MarketsSettingsResponse:
        practice = await self._load(db, practice_id)
        return self._to_response(practice)

    async def save_market(
        self,
        db: AsyncSession,
        practice_id: UUID,
        code: str,
        payload: MarketSettingsUpdate,
        updated_by: UUID,
    ) -> MarketsSettingsResponse:
        """Write one market's block (and, when asked, make it the home market)."""
        practice = await self._load(db, practice_id)
        market_code = self._valid_code(code)
        settings = dict(practice.settings or {})
        markets = dict(settings.get(SETTINGS_KEY) or {})
        block = dict(markets.get(market_code) or {})

        if payload.currency is not None:
            self._put(block, "currency", self._valid_currency(payload.currency))
        for field in ("clinic_name", "clinic_city", "consultation_fee", "payment_methods"):
            value = getattr(payload, field)
            if value is not None:
                self._put(block, field, self._clean(value))
        if payload.prices is not None:
            prices = self._clean_prices(payload.prices)
            if prices:
                block["prices"] = prices
            else:
                block.pop("prices", None)
        if payload.languages is not None:
            languages = self._clean_languages(payload.languages)
            if languages:
                block["languages"] = languages
            else:
                block.pop("languages", None)
        if payload.clinics is not None:
            clinics = self._clean_clinics(payload.clinics)
            if clinics:
                block["clinics"] = clinics
                # Keep the legacy single-city field in sync with the first
                # branch, so anything still reading `clinic_city` alone (an
                # older cached UI, a report) shows something sane rather than
                # a stale city from before multi-branch support existed.
                block["clinic_city"] = clinics[0]["city"]
            else:
                block.pop("clinics", None)

        if block:
            markets[market_code] = block
        else:
            markets.pop(market_code, None)

        if markets:
            settings[SETTINGS_KEY] = markets
        else:
            settings.pop(SETTINGS_KEY, None)

        if payload.is_home:
            settings[HOME_MARKET_KEY] = market_code
        elif settings.get(HOME_MARKET_KEY) == market_code and market_code not in markets:
            # The home market's block was just emptied and it is no longer a
            # meaningful home — fall back to inference rather than pointing at
            # configuration that no longer exists.
            settings.pop(HOME_MARKET_KEY, None)

        self._stamp(settings, updated_by)
        practice.settings = settings
        await db.commit()
        return self._to_response(practice)

    async def clear_market(
        self, db: AsyncSession, practice_id: UUID, code: str, updated_by: UUID
    ) -> MarketsSettingsResponse:
        """Remove a market entirely — the receptionist then refuses to quote for
        it rather than quoting from stale numbers."""
        practice = await self._load(db, practice_id)
        market_code = self._valid_code(code)
        settings = dict(practice.settings or {})
        markets = dict(settings.get(SETTINGS_KEY) or {})
        if market_code not in markets:
            raise NotFoundException(f"{MARKETS[market_code].label} has no configuration to clear")
        markets.pop(market_code)
        if markets:
            settings[SETTINGS_KEY] = markets
        else:
            settings.pop(SETTINGS_KEY, None)
        if settings.get(HOME_MARKET_KEY) == market_code:
            settings.pop(HOME_MARKET_KEY, None)
        self._stamp(settings, updated_by)
        practice.settings = settings
        await db.commit()
        return self._to_response(practice)

    # -- internals ---------------------------------------------------------

    async def _load(self, db: AsyncSession, practice_id: UUID) -> Practice:
        practice = await db.get(Practice, practice_id)
        if practice is None:
            raise NotFoundException("Practice not found")
        return practice

    def _valid_code(self, code: str) -> str:
        market_code = normalize_market_code(code)
        if market_code is None or market_code not in MARKET_CODES:
            raise AppException(
                f"Unknown market '{code}'. Supported: {', '.join(MARKET_CODES)}."
            )
        return market_code

    def _valid_currency(self, currency: str) -> str | None:
        cleaned = (currency or "").strip().upper()
        if not cleaned:
            return None
        if cleaned not in SUPPORTED_CURRENCIES:
            raise AppException(
                f"Unsupported currency '{currency}'. Supported: {', '.join(SUPPORTED_CURRENCIES)}."
            )
        return cleaned

    @staticmethod
    def _clean(value: object) -> str | None:
        if value is None:
            return None
        text = " ".join(str(value).split())
        return text[:_MAX_WORD_LENGTH] or None

    @classmethod
    def _put(cls, block: dict, key: str, value: str | None) -> None:
        if value:
            block[key] = value
        else:
            block.pop(key, None)

    @classmethod
    def _clean_prices(cls, prices: dict[str, str]) -> dict[str, str]:
        if len(prices) > _MAX_PRICE_ROWS:
            raise AppException(f"Too many price rows (max {_MAX_PRICE_ROWS}).")
        cleaned: dict[str, str] = {}
        for name, value in prices.items():
            label = cls._clean(name)
            price = cls._clean(value)
            if label and price:
                cleaned[label[:_MAX_WORD_LENGTH]] = price
        return cleaned

    @classmethod
    def _clean_languages(cls, languages: list[str]) -> list[str]:
        cleaned = [text for text in (cls._clean(item) for item in languages or []) if text]
        return cleaned[:_MAX_LANGUAGES]

    @classmethod
    def _clean_clinics(cls, clinics: list[ClinicLocation]) -> list[dict]:
        cleaned: list[dict] = []
        for entry in clinics[:_MAX_CLINICS]:
            city = cls._clean(entry.city)
            if not city:
                continue
            cleaned.append({"city": city, "address": cls._clean(entry.address)})
        return cleaned

    @staticmethod
    def _stamp(settings: dict, updated_by: UUID) -> None:
        settings[SETTINGS_UPDATED_AT_KEY] = datetime.now(timezone.utc).isoformat()
        settings[SETTINGS_UPDATED_BY_KEY] = str(updated_by)

    def _to_response(self, practice: Practice) -> MarketsSettingsResponse:
        settings = practice.settings or {}
        home = default_market_code(settings, practice.timezone)
        markets: list[MarketSettings] = []
        for code in MARKET_CODES:
            market = MARKETS[code]
            config: MarketConfig = market_config(settings, code)
            markets.append(
                MarketSettings(
                    code=code,
                    label=market.label,
                    configured=bool(config.raw),
                    is_home=(code == home),
                    currency=config.currency or market.currency,
                    default_currency=market.currency,
                    language_label=market.language_label,
                    timezone=market.timezone,
                    regulator=market.regulator,
                    advertising_note=market.advertising_note,
                    consult_format=market.consult_format,
                    video_first=market.video_first,
                    clinic_name=config.clinic_name,
                    clinic_city=config.clinic_city,
                    clinics=[ClinicLocation(city=c["city"], address=c.get("address")) for c in config.clinics],
                    consultation_fee=config.consultation_fee,
                    payment_methods=config.payment_methods,
                    prices=config.prices,
                    languages=list(config.languages),
                )
            )
        return MarketsSettingsResponse(
            home_market=home,
            markets=markets,
            supported_currencies=list(SUPPORTED_CURRENCIES),
            updated_at=settings.get(SETTINGS_UPDATED_AT_KEY),
            updated_by=settings.get(SETTINGS_UPDATED_BY_KEY),
        )
