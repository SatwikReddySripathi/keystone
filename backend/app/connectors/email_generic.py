"""
Email Generic connector.

Treats each email recipient as a "record" and the email
(subject + body) as the change set. Designed for observe_only
governance — Action Marshall evaluates policy and blast radius while
the calling agent sends the email itself via its own mail client
(Outlook, Gmail, SMTP, etc.).

Usage in ActionParams:
    connector = "email_generic"
    query     = {"recipients": ["alice@co.com", "bob@co.com"], "type": "daily_report"}
    changes   = {"subject": "Daily Report", "body_preview": "first 500 chars..."}

Blast radius  = number of recipients.
Flags exposed to policy:
    has_large_send          recipients > 20
    has_external_recipients more than one unique domain in the recipient list
    has_sensitive_keywords  subject or body contains flagged words
    has_all_staff           subject or body implies a company-wide send
"""
from app.connectors.base import BaseConnector

SENSITIVE_KEYWORDS = [
    "confidential", "sensitive", "internal only", "do not forward",
    "all staff", "all employees", "company-wide", "urgent action required",
    "critical", "breach", "incident report", "immediate action",
    "layoff", "restructure", "termination", "legal hold",
]

ALL_STAFF_PHRASES = [
    "all staff", "all employees", "company-wide", "everyone",
    "whole team", "entire org", "org-wide",
]


class EmailGenericConnector(BaseConnector):
    """
    Governance connector for outbound email sends.
    Each recipient becomes a governed "record"; the email content is the change.
    """

    def query(self, filters: dict) -> list[dict]:
        """
        Build one record per recipient from filters["recipients"].
        Supports a list or a comma-separated string.
        """
        recipients = filters.get("recipients", [])
        if isinstance(recipients, str):
            recipients = [r.strip() for r in recipients.split(",") if r.strip()]

        email_type = filters.get("type", "email")
        date = filters.get("date", "")

        return [
            {
                "sys_id": addr,
                "number": addr,
                "email": addr,
                "type": email_type,
                "date": date,
                "state": "unsent",
                "domain": addr.split("@")[-1] if "@" in addr else "unknown",
            }
            for addr in recipients
        ]

    def compute_diffs(self, records: list[dict], changes: dict) -> list[dict]:
        """
        Each recipient transitions from state=unsent to state=sent
        with the given subject and body preview.
        """
        subject = changes.get("subject", "")
        body_preview = changes.get("body_preview", changes.get("body", ""))
        if body_preview and len(body_preview) > 300:
            body_preview = body_preview[:300] + "..."

        diffs = []
        for rec in records:
            diffs.append({
                "sys_id": rec["sys_id"],
                "number": rec["email"],
                "fields": {
                    "state":        {"before": "unsent", "after": "sent"},
                    "subject":      {"before": None,     "after": subject},
                    "body_preview": {"before": None,     "after": body_preview},
                },
            })
        return diffs

    def execute_update(
        self,
        sys_ids: list[str],
        changes: dict,
        metadata: dict | None = None,
    ) -> list[dict]:
        """
        Observe-only: Action Marshall governs, the agent sends.
        If you want Action Marshall to send via SMTP, wire it up here.
        """
        return [
            {
                "sys_id": addr,
                "number": addr,
                "success": True,
                "changes_applied": ["state", "subject"],
                "note": "Governance record only — sending handled by the calling agent.",
            }
            for addr in sys_ids
        ]

    def get_record(self, sys_id: str) -> dict | None:
        return {
            "sys_id": sys_id,
            "number": sys_id,
            "email": sys_id,
            "state": "unsent",
            "domain": sys_id.split("@")[-1] if "@" in sys_id else "unknown",
        }

    def extra_flags(self, records: list[dict], changes: dict) -> dict:
        """
        Email-specific policy flags merged into the preview by the engine.
        Policy rules can reference these as  flag: has_large_send  etc.
        """
        subject = changes.get("subject", "")
        body = changes.get("body_preview", changes.get("body", ""))
        text = (subject + " " + body).lower()

        domains = {r.get("domain", "") for r in records if r.get("domain")}

        return {
            "has_large_send": len(records) > 20,
            "has_external_recipients": len(domains) > 1,
            "has_sensitive_keywords": any(kw in text for kw in SENSITIVE_KEYWORDS),
            "has_all_staff": any(phrase in text for phrase in ALL_STAFF_PHRASES),
        }


_connector = EmailGenericConnector()


def get_connector() -> EmailGenericConnector:
    return _connector