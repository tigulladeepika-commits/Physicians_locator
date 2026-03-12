"""
salesforce.py — Salesforce Lead Integration Module
===================================================
Stub implementation ready for activation.

To activate:
1. Install simple-salesforce: pip install simple-salesforce
2. Fill in .env with SF credentials
3. Uncomment the code blocks below
4. In app.py, replace _save_lead() call with salesforce_create_lead()

Salesforce Connected App setup:
- Login to Salesforce Setup → App Manager → New Connected App
- Enable OAuth, add scopes: api, refresh_token
- Note the Consumer Key (client_id) and Consumer Secret
"""

import os
import logging

logger = logging.getLogger(__name__)


def salesforce_create_lead(lead_data: dict) -> dict:
    """
    Create a Lead record in Salesforce.

    Args:
        lead_data: Dict with keys: first_name, last_name, email, phone,
                   company, title, search_context

    Returns:
        Dict with 'id' (Salesforce Lead ID) and 'success' bool
    """
    # ── Uncomment when ready ────────────────────────────────────────────────
    # from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
    #
    # try:
    #     sf = Salesforce(
    #         username=os.environ["SF_USERNAME"],
    #         password=os.environ["SF_PASSWORD"],
    #         security_token=os.environ["SF_SECURITY_TOKEN"],
    #         consumer_key=os.environ["SF_CLIENT_ID"],
    #         consumer_secret=os.environ["SF_CLIENT_SECRET"],
    #     )
    #
    #     search_ctx = lead_data.get("search_context", {})
    #     description = (
    #         f"Physician Locator Search\n"
    #         f"Address: {search_ctx.get('address', '')}\n"
    #         f"Radius: {search_ctx.get('radius', '')} miles\n"
    #         f"Taxonomy Code: {search_ctx.get('taxonomy_code', '')}\n"
    #         f"Description: {search_ctx.get('description', '')}\n"
    #         f"Total Results: {search_ctx.get('total_results', '')}\n"
    #         f"Submitted: {search_ctx.get('timestamp', '')}"
    #     )
    #
    #     result = sf.Lead.create({
    #         "FirstName":   lead_data["first_name"],
    #         "LastName":    lead_data["last_name"],
    #         "Email":       lead_data["email"],
    #         "Phone":       lead_data.get("phone", ""),
    #         "Company":     lead_data.get("company") or "Unknown",
    #         "Title":       lead_data.get("title", ""),
    #         "LeadSource":  "Web - Physician Locator",
    #         "Status":      "New",
    #         "Description": description,
    #     })
    #
    #     logger.info(f"Salesforce Lead created: {result['id']}")
    #     return {"id": result["id"], "success": True}
    #
    # except SalesforceAuthenticationFailed as e:
    #     logger.error(f"Salesforce auth failed: {e}")
    #     return {"id": None, "success": False, "error": str(e)}
    # except Exception as e:
    #     logger.error(f"Salesforce lead creation error: {e}")
    #     return {"id": None, "success": False, "error": str(e)}
    # ────────────────────────────────────────────────────────────────────────

    # Stub: log and return fake success
    logger.info(f"[STUB] Salesforce lead: {lead_data.get('email')} — integration not yet active")
    return {"id": None, "success": True, "stub": True}


def get_salesforce_client():
    """
    Return an authenticated Salesforce client instance.
    Useful for other operations (querying, updating leads, etc.)
    """
    # from simple_salesforce import Salesforce
    # return Salesforce(
    #     username=os.environ["SF_USERNAME"],
    #     password=os.environ["SF_PASSWORD"],
    #     security_token=os.environ["SF_SECURITY_TOKEN"],
    #     consumer_key=os.environ["SF_CLIENT_ID"],
    #     consumer_secret=os.environ["SF_CLIENT_SECRET"],
    # )
    raise NotImplementedError("Salesforce client not yet configured. See salesforce.py.")