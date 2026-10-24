"""Minimal client for invoice-api.xhub.io (Python standard library only).

Configuration (environment variables, or a .env file in the current directory):
  INVOICE_XHUB_API_KEY      required, API key from the invoice-api console
  INVOICE_XHUB_URL          optional, default https://service.invoice-api.xhub.io
  INVOICE_XHUB_TEMPLATE_ID  optional, saved PDF template for pdf/zugferd/facturx
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "https://service.invoice-api.xhub.io"


def load_config():
    cfg = {}
    if os.path.exists(".env"):
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("INVOICE_XHUB_API_KEY", "INVOICE_XHUB_URL", "INVOICE_XHUB_TEMPLATE_ID"):
        if os.environ.get(k):
            cfg[k] = os.environ[k]
    if not cfg.get("INVOICE_XHUB_API_KEY"):
        raise SystemExit(
            "INVOICE_XHUB_API_KEY is not set. Create a key in the invoice-api console "
            "and export it, or put it into a .env file in the current directory."
        )
    cfg.setdefault("INVOICE_XHUB_URL", DEFAULT_URL)
    cfg["INVOICE_XHUB_URL"] = cfg["INVOICE_XHUB_URL"].rstrip("/")
    return cfg


def post(cfg, path, body, timeout=120):
    """POST JSON, return (http_status, parsed_json). Never prints the key."""
    req = urllib.request.Request(
        cfg["INVOICE_XHUB_URL"] + path,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + cfg["INVOICE_XHUB_API_KEY"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"error": raw[:2000]}
    except urllib.error.URLError as e:
        raise SystemExit(
            f"Cannot reach {cfg['INVOICE_XHUB_URL']}: {e.reason}. "
            "If you run inside a sandbox (e.g. Claude Desktop / claude.ai), the host "
            "service.invoice-api.xhub.io must be allowed in the network settings."
        )


def strip_binary(resp):
    """Copy of a response without the large base64/XML fields, for reports."""
    if not isinstance(resp, dict):
        return resp
    return {k: v for k, v in resp.items() if k not in ("data", "embeddedXml")}
