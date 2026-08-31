# Wiki.js content organization and metadata

Start small. Wiki.js paths provide a navigable hierarchy, while native tags add cross-cutting metadata for future filtered retrieval. Do not create empty pages merely to reproduce this entire outline.

## Suggested hierarchy

```text
Home

Projects/
  ARES/
  AutoIrrigation/
  Robotics/
  Software/
  Hardware/

Development/
  Python/
  C++/
  ROS2/
  Linux/
  Docker/
  Networking/

Infrastructure/
  Servers/
  RaspberryPi/
  Jetson/
  Tailscale/
  Backups/

University/
  Courses/
  Notes/
  Research/

Work/
  Projects/
  Documentation/

Personal/
  Ideas/
  Notes/
  TODO/

Knowledge/
  AI/
  MachineLearning/
  ComputerVision/
  Electronics/
```

A useful initial set is only `Home`, the active project's overview, and the pages needed for current notes. Add branches when real content appears.

## Page conventions

- Give each page one clear subject and a durable path.
- Put a short purpose/summary near the top; this improves both human scanning and future retrieval.
- Prefer Markdown headings and fenced code blocks over visual formatting that loses structure during export.
- Link related pages rather than duplicating long sections.
- Record decisions and their rationale, not only the final commands.
- Move or rename pages deliberately because the numeric Wiki.js page ID is stable but human-facing URLs can change.
- Use native Wiki.js tags for retrieval metadata. Keep the spelling and case consistent.

## Recommended tag convention

Use lowercase `key:value` tags. Add only dimensions that help filtering; every page does not need every tag.

| Dimension | Examples |
| --- | --- |
| Project | `project:ares`, `project:auto-irrigation` |
| Content type | `type:documentation`, `type:decision`, `type:runbook`, `type:note` |
| Topic | `topic:ros2`, `topic:networking`, `topic:computer-vision` |
| Status | `status:draft`, `status:active`, `status:stable`, `status:archived` |
| Hardware | `hardware:raspberry-pi`, `hardware:jetson`, `hardware:rtx-2070` |
| Software | `software:flask`, `software:docker`, `software:postgresql` |
| Importance | `importance:high`, `importance:reference` |
| Date | `date:2026-08-30`, `year:2026`, or a date in page content when a tag adds little value |

Example for an active ARES ROS 2 deployment note:

```text
project:ares
type:runbook
topic:ros2
status:active
hardware:raspberry-pi
importance:high
```

Avoid uncontrolled synonyms such as mixing `rpi`, `raspi`, and `raspberry-pi`. A future normalizer can split `key:value` into structured metadata while retaining the original tag list.

## Content quality for future retrieval

- Include enough context for a section to make sense when retrieved independently.
- Put commands beside prerequisites, expected results, and rollback notes.
- Date time-sensitive claims in the page body or metadata.
- Separate historical notes from the current runbook and tag obsolete pages `status:archived`.
- Never store passwords, private keys, API tokens, or recovery codes in ordinary Wiki pages unless an explicit encrypted secret-management design is added later.
