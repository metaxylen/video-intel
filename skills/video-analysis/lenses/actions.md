# Lens: actions

Concrete things the viewer can do after the video: to do, to try, to look up.

## Extract
- 3-10 items. Each has `id` (`a1`, `a2`, ...), `t` (the moment it rests on, seconds), `action` (imperative, a single action, first word a verb), `why` (the video's reasoning, one sentence), `effort` (`minutes|hours|days`), `priority` (`high|medium|low`), `depends_on` (the `id` of another item that must come first, or `null`).
- Sort by priority, then by dependency order.

## Rules
- Draw only from what the video advises or shows. When an item is your own inference, write "inference" in `why`.
- Make each item specific enough that someone else could start from that sentence alone: which tool, which setting, which number.
- When the `claims` lens ran and an action rests on a claim that turned out false, keep the item with a warning in `why`, or leave it out.

Done when every item is specific and sourced to a `t`, and each `depends_on` points to an existing `id` or is `null`.

## JSON
```json
"actions": [{"id": "a1", "t": 180, "action": "string", "why": "string", "effort": "minutes|hours|days", "priority": "high|medium|low", "depends_on": "string|null"}]
```
Example: `{"id": "a1", "t": 180, "action": "Set the cron job to run a weekly backup", "why": "Prevents data loss", "effort": "minutes", "priority": "high", "depends_on": null}`
