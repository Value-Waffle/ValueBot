# --- BEFORE: Duplicate Implementation Noise ---
# billing/validators.py
def validate_billing_contact(data):
    # Complex regex validation logic repeated here...
    cleaned = data["phone"].strip().replace("-", "").replace(" ", "")
    if not cleaned.startswith("+") or len(cleaned) < 10:
        raise ValueError("Invalid international format")
    return cleaned

# shipping/models.py
def update_shipping_address(address_dict):
    # ...and completely copy-pasted or slightly mutated over here
    phone = address_dict["phone_number"].strip().replace("-", "").replace(" ", "")
    if not phone.startswith("+") or len(phone) < 10:
        raise ValueError("Invalid phone layout")
    return phone


# --- AFTER: Centralized Minimal Interface ---
# core/telephony.py (Shared Utility Module)
def parse_phone_number(raw_input: str) -> str:
    """Centralized utility masking regex/parsing complexity behind a 1-input contract."""
    cleaned = raw_input.strip().replace("-", "").replace(" ", "")
    if not cleaned.startswith("+") or len(cleaned) < 10:
        raise ValueError("Invalid international phone format")
    return cleaned

# billing/validators.py
def validate_billing_contact(data):
    return parse_phone_number(data["phone"])

# shipping/models.py
def update_shipping_address(address_dict):
    return parse_phone_number(address_dict["phone_number"])