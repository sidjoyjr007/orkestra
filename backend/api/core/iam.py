# Centralized Identity and Access Management (IAM)

ROLE_PERMISSIONS = {
    "ADMIN": ["*"],
    "DEVELOPER": [
        "tools:read",
        "tools:create",
        "tools:edit",
        "tools:delete",
        "tools:execute",
        "agents:read",
        "agents:create",
        "agents:edit",
        "agents:delete",
        "agents:execute",
        "llms:read",
        "llms:create",
        "llms:edit",
        "llms:delete",
        "mcps:read",
        "mcps:create",
        "mcps:edit",
        "mcps:delete",
        "mcps:execute",
        "guardrails:read",
        "guardrails:create",
        "guardrails:edit",
        "guardrails:delete",
        "guardrails:execute"
    ],
    "VIEWER": [
        "tools:read",
        "tools:execute",
        "agents:read",
        "agents:execute",
        "llms:read",
        "mcps:read",
        "mcps:execute",
        "guardrails:read",
        "guardrails:execute"
    ]
}

def has_permission(user_role: str, required_permission: str) -> bool:
    """Check if a given role has the required permission."""
    if not user_role:
        return False
        
    permissions = ROLE_PERMISSIONS.get(user_role, [])
    
    if "*" in permissions:
        return True
        
    return required_permission in permissions
