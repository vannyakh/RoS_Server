---
name: protocol-validation
description: Validates this server's versioned JSON messages and malformed input. Use when changing app/networking/protocol.py or message tests.
---

# Protocol validation

## Workflow

1. Parse with `tools.protocol_validator.validate_message`.
2. Check version 1, the known `type` values, and a non-decreasing sequence.
3. Add one invalid payload for every new message type.
4. Keep the token in the first WebSocket message, not the URL.

## Output

The test path and the validator result for the valid and invalid samples.

## Failure

Do not widen the schema to accept an official-client packet you cannot document.
