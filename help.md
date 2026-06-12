# Scrum

A daily standup for a household that runs like a software-dev team. Each morning
you get a short, personalized check-in — what you finished, what you're focused
on, and anything blocking you — and you answer it in a sentence or two.

## Overview

Every morning the daily PM update generates your **scrum items** and files them
here. You reply to them either right in chat (just answer your PM check-in
message) or from the Scrum app. Answering can also nudge the underlying task
forward — say a task is done and it gets marked done.

## Screens

- **Daily Scrum.** Your items grouped by day, newest first. Each day is split
  into the three standup questions: *What did you finish?*, *What are you working
  on today?*, *Any blockers?* — plus any findings or schedule reminders.
- **Person picker.** Defaults to you; switch to "All Users" or another person to
  see their standups.
- **Day range.** Show today, the last 3 / 7 / 14 / 30 days.

## Answering your standup

- *In the app:* click **Reply** on any of today's items, type your answer, and
  send. A "replied" badge appears and your answer shows below the item.
- *In chat:* just reply to your morning PM check-in. Skipper matches your reply
  to the right items, records each answer, and updates linked tasks (done /
  in progress / blocked) as appropriate.
- *Add your own:* on today's standup you can also add a freeform item under any
  question ("I also finished…", "I'm also working on…").

## Tips

- Items only appear after the daily PM update runs each morning.
- If you don't have any items yet today, that just means the PM update hasn't
  run or had nothing to ask you.

## Your data

Your scrum items and responses are saved in the database (in this app's own
`app_scrum` schema) and stay within your household.
