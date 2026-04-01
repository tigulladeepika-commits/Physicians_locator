"""
Salesforce lead integration service.
Handles pushing leads to Salesforce and saving to file backup.
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Tuple

from config import cfg
from services.http_client import http_client
from utils.helpers import sanitise

logger = logging.getLogger(__name__)


def push_to_salesforce(lead: Dict) -> Tuple[bool, int, str, str]:
    """
    Push lead to Salesforce Web-to-Lead form.
    
    Args:
        lead: Lead data dict
        
    Returns:
        Tuple of (success, http_status, response_snippet, error_message)
    """
    if not cfg.SF_OID:
        msg = "SF_OID not set — cannot push to Salesforce"
        logger.warning(msg)
        return False, 0, "", msg

    ctx = lead.get("search_context", {})
    sf_payload = {
        "oid": cfg.SF_OID,
        "retURL": cfg.SF_RET_URL or "https://www.aquarient.com",
        "first_name": sanitise(lead.get("first_name", ""), 80),
        "last_name": sanitise(lead.get("last_name", ""), 80),
        "email": sanitise(lead.get("email", ""), 254),
        "phone": sanitise(lead.get("phone", ""), 40),
        "company": sanitise(lead.get("company") or "N/A", 120),
        "title": sanitise(lead.get("title", ""), 80),
        "lead_source": "Physician Locator",
        "description": sanitise(
            "Physician Locator — "
            f"Location: {ctx.get('address', '')} | "
            f"Specialty: {', '.join(ctx.get('descriptions', []))} | "
            f"Results: {ctx.get('total_results', '')}",
            2000,
        ),
    }
    if cfg.SF_DEBUG_EMAIL:
        sf_payload["debug"] = "1"
        sf_payload["debugEmail"] = cfg.SF_DEBUG_EMAIL

    logger.info("Pushing to SF | OID=%s | email=%s", cfg.SF_OID, lead["email"])
    try:
        resp = http_client.post(
            "https://webto.salesforce.com/servlet/servlet.WebToLead?encoding=UTF-8",
            data=sf_payload,
            timeout=cfg.REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        snippet = (resp.text or "")[:500]
        body_lower = snippet.lower()
        has_error = (
            "error" in body_lower
            and "debugEmail" not in snippet
            and "successfully" not in body_lower
        )
        if has_error:
            logger.warning("SF response suggests failure: %.300s", snippet)
        success = resp.status_code in (200, 301, 302) and not has_error
        logger.info("SF HTTP %d | success=%s | email=%s", resp.status_code, success, lead["email"])
        return success, resp.status_code, snippet, ""
    except requests.Timeout:
        msg = f"SF request timed out after {cfg.REQUEST_TIMEOUT}s"
        logger.error(msg)
        return False, 0, "", msg
    except Exception as ex:
        msg = f"{type(ex).__name__}: {ex}"
        logger.error("SF push exception: %s", msg)
        return False, 0, "", msg


def save_to_file(lead: Dict) -> Tuple[bool, str, str]:
    """
    Save lead to local file as NDJSON backup.
    
    Note: Render free plan has ephemeral filesystem.
    Set LEADS_DIR to /var/data (paid disk) or leads will be lost on deploy.
    
    Args:
        lead: Lead data dict
        
    Returns:
        Tuple of (success, file_path, error_message)
    """
    try:
        os.makedirs(cfg.LEADS_DIR, exist_ok=True)
    except Exception:
        pass

    leads_file = os.path.join(cfg.LEADS_DIR, "leads.ndjson")
    try:
        with open(leads_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(lead) + "\n")
        logger.info("Lead saved | file=%s | id=%s", leads_file, lead["id"])
        return True, leads_file, ""
    except Exception as ex:
        msg = f"{type(ex).__name__}: {ex}"
        logger.error("File write failed: %s", msg)
        return False, leads_file, msg
