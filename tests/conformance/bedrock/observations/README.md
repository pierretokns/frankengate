# Sanitized AWS observations

These files are observational inputs, not service specifications. They preserve stable route,
shape, status, error classification, and header-name evidence while removing credentials,
signatures, session tokens, and request-ID values. An absent field is never treated as forbidden.

The matching raw exchanges may be held only in an access-controlled, short-lived local quarantine.
They must not be committed. Every observation set records the credential class, region, timestamp,
request shape, explicit omissions, and the narrow claims the sample can support.
