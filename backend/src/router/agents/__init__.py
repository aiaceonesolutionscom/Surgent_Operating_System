from fastapi import APIRouter

from src.router.v1.webhooks.webhook_router import router as webhook_router
from src.router.conversations.conversations_router import router as conversations_router
from src.router.checkout.checkout_router import router as checkout_router
from src.router.demo.demo_router import router as demo_router
from src.router.practice.practice_router import router as practice_router
from src.router.agent_costing.agent_costing_router import router as agent_costing_router
from src.router.patients.patients_router import router as patients_router
from src.router.doctors.doctors_router import router as doctors_router
from src.router.appointments.appointments_router import router as appointments_router
from src.router.agent_config.agent_config_router import router as agent_config_router
from src.router.doctor_applications.doctor_applications_router import router as doctor_applications_router
from src.router.staff_applications.staff_applications_router import router as staff_applications_router
from src.router.attendance.attendance_router import router as attendance_router
from src.router.command_center.command_center_router import router as command_center_router
from src.router.admin.admin_router import router as admin_router
from src.router.plans.plans_router import router as plans_router
from src.router.analytics.analytics_router import router as analytics_router
from src.router.staff.staff_router import router as staff_router
from src.router.procedures.procedures_router import router as procedures_router
from src.router.clinical.clinical_router import router as clinical_router
from src.router.patient_photos.patient_photos_router import router as patient_photos_router
from src.router.consent.consent_router import router as consent_router
from src.router.billing.billing_router import router as billing_router
from src.router.finance.finance_router import router as finance_router
from src.router.wallet.wallet_router import router as wallet_router
from src.router.inventory.inventory_router import router as inventory_router
from src.router.ai_receptionist.ai_receptionist_router import router as ai_receptionist_router
from src.router.ai_receptionist.inbound_router import router as inbound_router
from src.router.staff_messages.staff_message_router import router as staff_message_router
from src.router.patient_portal.patient_portal_router import router as patient_portal_router
from src.router.public.consultation_request_router import router as public_router
from src.router.waitlist.waitlist_router import router as waitlist_router
from src.router.surgery.surgery_router import router as surgery_router
from src.router.recovery.recovery_router import router as recovery_router
from src.router.notifications.notification_router import router as notification_router
from src.router.inventory.supplier_router import router as supplier_router
from src.router.inventory.purchase_order_router import router as purchase_order_router
from src.router.leads.leads_router import router as leads_router
from src.router.landing_chat.landing_chat_router import router as landing_chat_router
from src.router.audit_logs.audit_logs_router import router as audit_logs_router
from src.router.finance_agent.finance_agent_router import router as finance_agent_router

agent_routers = [
    patient_portal_router,
    public_router,
    ai_receptionist_router,
    inbound_router,
    staff_message_router,
    webhook_router,
    conversations_router,
    checkout_router,
    demo_router,
    practice_router,
    agent_costing_router,
    patients_router,
    doctors_router,
    appointments_router,
    agent_config_router,
    doctor_applications_router,
    staff_applications_router,
    attendance_router,
    command_center_router,
    admin_router,
    plans_router,
    analytics_router,
    staff_router,
    procedures_router,
    clinical_router,
    patient_photos_router,
    consent_router,
    billing_router,
    finance_router,
    wallet_router,
    inventory_router,
    waitlist_router,
    surgery_router,
    recovery_router,
    notification_router,
    supplier_router,
    purchase_order_router,
    leads_router,
    landing_chat_router,
    audit_logs_router,
    finance_agent_router,
]


def register_routes(app):
    for router in agent_routers:
        app.include_router(router, prefix="/api/v1")
