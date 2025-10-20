#!/usr/bin/env python3
"""
LOB-specific guidance prompts for field extraction.
These prompts can be customized per line of business.
"""

# AUTO (Automobile) guidance
AUTO_GUIDANCE = """
For AUTO insurance claims, extract the following fields:
- evaluation_date: The date of the loss run report
- carrier: Insurance company name
- claim_number: Unique claim identifier
- loss_date: Date when the loss occurred
- paid_loss: Amount already paid out for the claim
- reserve: Amount set aside for future payments
- alae: Allocated Loss Adjustment Expense (legal/administrative costs)

Focus on automobile-related claims, vehicle accidents, collision, comprehensive coverage.
"""

# GENERAL LIABILITY guidance
GL_GUIDANCE = """
For GENERAL LIABILITY insurance claims, extract the following fields:
- evaluation_date: The date of the loss run report
- carrier: Insurance company name
- claim_number: Unique claim identifier
- loss_date: Date when the loss occurred
- bi_paid_loss: Bodily Injury paid losses
- pd_paid_loss: Property Damage paid losses
- bi_reserve: Bodily Injury reserves
- pd_reserve: Property Damage reserves
- alae: Allocated Loss Adjustment Expense

Focus on premises liability, products liability, slip and fall, business liability claims.
"""

# WORKERS COMPENSATION guidance
WC_GUIDANCE = """
For WORKERS COMPENSATION insurance claims, extract the following fields:
- evaluation_date: The date of the loss run report
- carrier: Insurance company name
- claim_number: Unique claim identifier
- loss_date: Date when the injury occurred
- Indemnity_paid_loss: Indemnity benefits already paid
- Medical_paid_loss: Medical benefits already paid
- Indemnity_reserve: Indemnity reserves for future payments
- Medical_reserve: Medical reserves for future payments
- ALAE: Allocated Loss Adjustment Expense

Focus on employee injuries, workplace accidents, wage replacement, medical benefits.
"""

# Schema definitions for each LOB
AUTO_SCHEMA = {
    "evaluation_date": "string",
    "carrier": "string",
    "claims": [{
        "claim_number": "string",
        "loss_date": "string",
        "paid_loss": "string",
        "reserve": "string",
        "alae": "string"
    }]
}

GL_SCHEMA = {
    "evaluation_date": "string",
    "carrier": "string",
    "claims": [{
        "claim_number": "string",
        "loss_date": "string",
        "bi_paid_loss": "string",
        "pd_paid_loss": "string",
        "bi_reserve": "string",
        "pd_reserve": "string",
        "alae": "string"
    }]
}

WC_SCHEMA = {
    "evaluation_date": "string",
    "carrier": "string",
    "claims": [{
        "claim_number": "string",
        "loss_date": "string",
        "Indemnity_paid_loss": "string",
        "Medical_paid_loss": "string",
        "Indemnity_reserve": "string",
        "Medical_reserve": "string",
        "ALAE": "string"
    }]
}

# Dictionary mapping LOB to guidance and schema
LOB_CONFIGS = {
    'AUTO': {
        'guidance': AUTO_GUIDANCE,
        'schema': AUTO_SCHEMA
    },
    'GL': {
        'guidance': GL_GUIDANCE,
        'schema': GL_SCHEMA
    },
    'GENERAL LIABILITY': {
        'guidance': GL_GUIDANCE,
        'schema': GL_SCHEMA
    },
    'WC': {
        'guidance': WC_GUIDANCE,
        'schema': WC_SCHEMA
    }
}

def get_lob_config(lob: str) -> dict:
    """Get guidance and schema for a specific LOB."""
    lob_upper = lob.upper()
    return LOB_CONFIGS.get(lob_upper, LOB_CONFIGS['AUTO'])

def get_guidance(lob: str) -> str:
    """Get guidance text for a specific LOB."""
    config = get_lob_config(lob)
    return config['guidance']

def get_schema(lob: str) -> dict:
    """Get schema for a specific LOB."""
    config = get_lob_config(lob)
    return config['schema']
