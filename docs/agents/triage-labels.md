# Triage Labels

Two **category** roles and five **state** roles. Each issue carries exactly one of each.

## Category roles

| Role | GitHub label |
|------|-------------|
| `bug` | `bug` |
| `enhancement` | `enhancement` |

## State roles

| Role | GitHub label | Description |
|------|-------------|-------------|
| `needs-triage` | `needs-triage` | Maintainer needs to evaluate |
| `needs-info` | `needs-info` | Waiting on reporter for more information |
| `ready-for-agent` | `ready-for-agent` | Fully specified, ready for an AFK agent |
| `ready-for-human` | `ready-for-human` | Needs human implementation |
| `wontfix` | `wontfix` | Will not be actioned |

## State machine

```
unlabeled → needs-triage
needs-triage → needs-info | ready-for-agent | ready-for-human | wontfix
needs-info → needs-triage (once reporter replies)
```

The maintainer can override at any time.
