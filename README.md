# Daily Briefing podcast

A weekday-morning news briefing, generated and narrated automatically.

**Feed:** https://namocol.github.io/daily_briefing-podcast/feed.xml

To follow it in Apple Podcasts, go to Library, tap **⋯**, then **Follow a Show by URL**, and paste the feed URL. In Overcast, tap **+**, then **Add URL**.

`publish.py` adds each new episode, keeps the last 30 days, and rebuilds `feed.xml`. The feed is marked `itunes:block` so it stays out of podcast directories.
