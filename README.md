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
| `!removeclass <day> <start> <end>` | Remove a class from your schedule. Example: `!removeclass Mon 09:00 10:30` |
| `!myschedule` | Display your weekly schedule. |
| `!importschedule` | Import multiple class blocks at once. Example:<br>
`!importschedule`<br>
`Mon 10:00-12:30`<br>
`Mon 13:30-16:00`<br>
`Tue 10:00-11:30`
<code>aaa </code> |
| `!busy` | Mark yourself as busy manually (overrides schedule). |
| `!available` | Mark yourself as available manually (overrides schedule). |
| `!free` | Show members who are free right now. |
| `!ping <activity> [optional message]` | Ping users who are free and have the specified role. Example: `!ping studying Library until 5pm` |
| `!myroles` | Show your current activity roles. |
| `!help` | Show a list of all commands and usage instructions. |
