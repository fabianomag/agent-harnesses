# Optional agent adapters

The four Agent Harnesses are agent-agnostic. Their release ZIPs contain the
complete local runtime, `operations.json`, and operator guides; they do not
require or install an agent-specific adapter.

Adapters in this directory are optional, explicit integrations for users who
want a particular agent platform to discover the same public operating
contract through that platform's native conventions. They are versioned in
the repository but are not included in the core package ZIPs, the standalone
installer, or the primary site snapshot.

