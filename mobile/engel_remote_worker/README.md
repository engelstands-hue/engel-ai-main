# Engel Remote Worker

Android Flutter scaffold for a local Engel Remote Worker companion.

This app is intentionally local-only in this phase:

- no connection to Engel
- no queue mutation
- no trusted-memory write
- no route execution
- no provider/API/network behavior
- no background sync or startup service
- no Hermes/Hermes-style runtimes, rejected / do not install on this computer

The current UI supports visible status, empty approved task packet review, local draft result text, and safety rules. Returned work remains untrusted until Engel verifier review and human approval.
