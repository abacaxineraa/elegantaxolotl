# Discord Bot for studying/eating together

A Discord bot to manage friends’ availability and study sessions. Only pings users who are free according to their schedule. Built with Python and SQLite.

---

## Features

- Store weekly class schedules for each user.
- Announce study sessions, eating breaks, or hangouts.
- Only ping users who are free at that time.
- Check who’s free right now with `!free`.

---

## Commands

| Command | Description |
|---------|-------------|
| `!addclass <day> <start> <end>` | Add a class to your schedule. Example: `!addclass Mon 09:00 10:30` |
| `!study <location> [duration]` | Announce a study session and ping only free users. Default duration is `30min`. Example: `!study Library 45min` |
| `!free` | Check who is free right now. Example: `!free` |
| `!test` | Test that new commands are loaded. |
