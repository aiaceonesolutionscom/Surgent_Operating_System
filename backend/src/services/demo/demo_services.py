from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.demo_request import DemoRequest
from src.models.sales_lead import SalesLead, SalesLeadSource, SalesLeadStatus
from src.services.email.resend_service import ResendService

logger = logging.getLogger(__name__)


class DemoService:
    def __init__(self):
        self.email = ResendService()

    async def create_demo_request(
        self,
        db: AsyncSession,
        name: str,
        email: str,
        phone: str | None,
        practice_name: str | None,
        message: str | None,
    ) -> DemoRequest:
        request = DemoRequest(
            name=name,
            email=email,
            phone=phone,
            practice_name=practice_name,
            message=message,
        )
        db.add(request)
        await db.flush()

        # Also create a SalesLead for the platform sales team to track
        # 24-hour SLA commitment
        sla_deadline = datetime.now(timezone.utc) + timedelta(hours=24)
        sales_lead = SalesLead(
            full_name=name,
            email=email,
            phone=phone,
            company=practice_name,
            message=message,
            source=SalesLeadSource.DEMO_FORM,
            status=SalesLeadStatus.NEW,
            sla_deadline=sla_deadline,
        )
        db.add(sales_lead)
        await db.flush()

        # The request is already captured at this point — a confirmation
        # email is a nice-to-have on top of it, not a condition of success.
        # (Resend's sandbox sender also only delivers to the account's own
        # verified test address until a sending domain is verified, so this
        # will legitimately fail for real recipients until that's set up —
        # that must never take the lead-capture down with it.)
        try:
            await self.email.send(
                to=email,
                subject="We've got your request — AesthetixAI",
                html_content=self._confirmation_html(name),
            )
        except Exception:
            logger.warning("Demo request confirmation email failed to send to %s", email, exc_info=True)

        return request

    @staticmethod
    def _confirmation_html(name: str) -> str:
        first_name = name.split(" ")[0] if name else "there"
        return f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 480px; margin: 0 auto; color: #0B1D26;">
          <p>Hi {first_name},</p>
          <p>Thanks for requesting a demo of AesthetixAI — we've got it, and a real
          person from our team will reach out <strong>within 24 hours</strong> to
          get you set up.</p>
          <p>In the meantime, feel free to reply to this email with anything
          specific you'd like us to walk through.</p>
          <p style="margin-top: 24px; color: #6B7E86; font-size: 13px;">
          AesthetixAI is built by <strong>AceOne Solutions</strong>.</p>
        </div>
        """.strip()
