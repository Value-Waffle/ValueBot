# valuebot documentation

valuebot is a LibreChat Agent Plugin that gives agents grounded financial
research data: SEC XBRL fundamentals, ratio and DCF analysis, and sec-parser
filing semantics — every number traceable to a filing.

This folder is split by audience. Pick the path that matches what you are doing.

| I want to… | Read |
|:---|:---|
| Install the plugin and ask my first question | [users/01-getting-started.md](users/01-getting-started.md) |
| Run valuebot from another AI harness | [users/09-multi-harness.md](users/09-multi-harness.md) |
| Configure the SEC identity, paths, limits | [users/02-configuration.md](users/02-configuration.md) |
| Look up a tool, its arguments and return shape | [users/03-tools-reference.md](users/03-tools-reference.md) |
| Set up the six bundled agents and five skills | [users/04-agents-and-skills.md](users/04-agents-and-skills.md) |
| See worked research flows | [users/05-research-workflows.md](users/05-research-workflows.md) |
| Deploy inside a Dockerised LibreChat | [users/06-librechat-deployment.md](users/06-librechat-deployment.md) |
| Add model providers (DeepSeek, OpenCode Zen) | [users/07-model-endpoints.md](users/07-model-endpoints.md) |
| Fix an error or check a limitation | [users/08-troubleshooting-and-faq.md](users/08-troubleshooting-and-faq.md) |
| See what is planned and when | [roadmap.md](roadmap.md) |
| Understand the internals | [dev/01-architecture.md](dev/01-architecture.md) |
| Run and extend the test suite | [dev/05-testing.md](dev/05-testing.md) |
| Contribute a change | [dev/10-contributing.md](dev/10-contributing.md) |

## Structure

```
docs/
├── 00-index.md                      this file
├── roadmap.md                      what is being built, in which order
├── users/                           for people using the plugin
│   ├── 00-index.md
│   ├── 01-getting-started.md
│   ├── 02-configuration.md
│   ├── 03-tools-reference.md
│   ├── 04-agents-and-skills.md
│   ├── 05-research-workflows.md
│   ├── 06-librechat-deployment.md
│   ├── 07-model-endpoints.md
│   ├── 08-troubleshooting-and-faq.md
│   └── 09-multi-harness.md
└── dev/                             for people working on the plugin
    ├── 00-index.md
    ├── 01-architecture.md
    ├── 02-module-contracts.md
    ├── 03-data-model.md
    ├── 04-development-setup.md
    ├── 05-testing.md
    ├── 06-reports-parser.md
    ├── 07-analysis-and-dcf.md
    ├── 08-deployment.md
    ├── 09-roadmap.md
    └── 10-contributing.md
```

## Other sources of truth

| Resource | Purpose |
|:---|:---|
| [`../README.md`](../README.md) | repository overview, install summary, layout, license, disclaimer |
| [`../../architecture/design-docs/valuebot-v2/design.md`](../../architecture/design-docs/valuebot-v2/design.md) | full design rationale |
| [`../../architecture/design-docs/valuebot-v2/db-mapping.md`](../../architecture/design-docs/valuebot-v2/db-mapping.md) | data-element to storage mapping |
| [`../agent-builder-exports/INSTALL.md`](../agent-builder-exports/INSTALL.md) | importing the six agents |
| [`../librechat.example.yaml`](../librechat.example.yaml) | plugin enablement snippet |
| [`../THIRD-PARTY-NOTICES.md`](../THIRD-PARTY-NOTICES.md) | dependency licenses and attribution |
| [`../../CONTRIBUTING.md`](../../CONTRIBUTING.md) | how to contribute |
| [`../../CODE_OF_CONDUCT.md`](../../CODE_OF_CONDUCT.md) | community expectations |
| [`../../SECURITY.md`](../../SECURITY.md) | how to report a vulnerability |

Design documents describe intent; the code and these guides describe current
behaviour. When they disagree, the code wins and the design doc gets updated.
