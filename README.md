# Discord Trivia Bot

A Kahoot style trivia bot for Discord that enables realtime multiplayer quiz competitions with private DM responses and speedbased scoring.

## Features
- Real time multiplayer trivia games
- Private DM answer submission
- Speed based scoring system (500-1000 points)
- Global leaderboard and player statistics
- Persistent score tracking
- Multiple concurrent game sessions
- Custom question support

## Commands
- `!trivia` - Start a new trivia game
- `!endtrivia` - End current game
- `!leaderboard` - View global rankings
- `!mystats` - View personal statistics

## Setup
1. Clone the repository
2. Install requirements: `pip install -r requirements.txt`
3. Create a `config.py` with your Discord bot token:
   ```python
   TOKEN = 'your_bot_token'
   ```
4. Run the bot: `python trivia_bot.py`

## Technologies
- Python 3.x
- Discord.py
- SQLite
- aiohttp 
