# your_project_name/models/schemas.py

# This file will hold your JSON schemas for validation.
# For example:

INVOICE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "invoice_number": {"type": "string"},
        "customer_id": {"type": "string"},
        "total_amount": {"type": "number", "minimum": 0},
        "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]},
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unit_price": {"type": "number", "minimum": 0}
                },
                "required": ["description", "quantity", "unit_price"]
            }
        }
    },
    "required": ["invoice_number", "customer_id", "total_amount", "currency"]
}

FRAUD_RISK_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "alert_id": {"type": "string"},
        "user_id": {"type": "string"},
        "event_type": {"type": "string", "enum": ["suspicious_login", "unusual_transaction", "account_takeover"]},
        "timestamp": {"type": "string", "format": "date-time"},
        "ip_address": {"type": "string", "format": "ipv4"},
        "amount": {"type": "number", "minimum": 0}
    },
    "required": ["alert_id", "user_id", "event_type", "timestamp", "ip_address"]
}

# You will add more schemas here as needed for different JSON types.