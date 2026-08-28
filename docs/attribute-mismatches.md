# Attribute mismatches

This document records names that do not currently match across the project's
models, views, routes, and templates. Keeping the list explicit makes the
remaining cleanup safe to schedule separately.

| Location | Expected name | Actual name or behavior | Status |
| --- | --- | --- | --- |
| `setup_course_holes` | `Course.tee_sets` | `TeeSet.course` defines `related_name="tees"`, exposed as `Course.tees` | Fixed in this change. |
| `setup_course_holes` POST redirect | `scoring:course_detail` | No `course_detail` URL is registered | Fixed by returning to the configured course's setup page. |
| `start_round.html` | `scoring:enter_scorecard` with no arguments | `enter_scorecard` requires `course_id` | Fixed by constructing the scorecard URL from the selected course. |
| `enter_scores` | `Hole.course` and `Hole.yardages` | `Hole` belongs to `tee_set` and has a direct `yardage` field | Unresolved; this view reflects an older hole data model. |
