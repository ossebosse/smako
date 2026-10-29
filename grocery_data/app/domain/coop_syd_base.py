"""Owner-approved base-price assignment; source 730400 retains its identity."""

POLICY_VERSION = "stora-coop-syd-base-v1"
SOURCE_CONTEXT_ID = "730400"
# Exact public store identities, not name matching. Jägersro is registered as
# Coop Forum Jägersro in Coop's locator and as Stora Coop at Primat/Coop Östra.
TARGETS = {
    "1281": {"2696": "105760"},
    "1280": {"3850": "105810", "3853": "105860"},
}
