"""DEFERRED (RED-zone) scrapers.

These target platforms whose Terms of Service prohibit automated scraping
(Facebook, Instagram, LinkedIn, Truecaller). Enforcement is active and may also
conflict with Egypt's PDPL when personal data is involved. They are gated behind
FEATURE_* flags (config/sources.yaml + .env) and are intentionally NOT
implemented in this build. Implementing/enabling them is opt-in and at your own
legal/operational risk. See README "Deferred sources" for compliant alternatives.
"""
