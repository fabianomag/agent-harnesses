# OpenAI adapters

These adapters preserve optional OpenAI Skill metadata separately from the
agent-agnostic harness runtimes. Installation is manual and opt-in.

1. Install and verify one core harness first.
2. Copy only the matching `adapters/openai/<id>/` contents into the
   repository-scoped `<target>/.agents/skills/<id>/` directory.
3. Keep the installed runtime's `operations.json` and operator guide as the
   command authorities. The adapter only adds OpenAI discovery metadata.
4. Remove that repository-scoped adapter directory to opt out; this does not
   uninstall or modify the core runtime.

Do not copy all four adapters, install them in a user-global directory, or
treat adapter discovery as part of core harness readiness.
