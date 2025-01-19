import discord
from discord.ext import commands
import aiohttp
import asyncio
import sqlite3
from datetime import datetime
import random
import time
from config import TOKEN

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.reactions = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Database setup
def setup_database():
    conn = sqlite3.connect('trivia.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scores
                 (user_id INTEGER, username TEXT, points INTEGER, last_played TEXT)''')
    conn.commit()
    conn.close()

# Question cache for different categories
questions = {
    'anime': [],
    'general': [],
    'gaming': [],
    'science': []
}

# Active games tracker
active_games = {}

class TriviaGame:
    def __init__(self, channel):
        self.channel = channel
        self.active = True
        self.players = {}
        self.current_options = None
        self.answered_users = set()

    async def register_players(self):
        # Send registration message
        embed = discord.Embed(
            title="New Trivia Game Starting!",
            description="React with ✅ to join the game! Starting in 10 seconds...",
            color=0x00ff00
        )
        register_msg = await self.channel.send(embed=embed)
        await register_msg.add_reaction("✅")
        
        # Wait 10 seconds for reactions
        await asyncio.sleep(10)
        
        # Fetch the message again to get final reactions
        register_msg = await self.channel.fetch_message(register_msg.id)
        for reaction in register_msg.reactions:
            if str(reaction.emoji) == "✅":
                async for user in reaction.users():
                    if not user.bot:
                        self.players[user.id] = {"name": user.name, "score": 0}
        
        if not self.players:
            await self.channel.send("No players joined the game!")
            return False
        
        player_list = "\n".join([f"• {player['name']}" for player in self.players.values()])
        await self.channel.send(f"Game starting with players:\n{player_list}")
        return True

    async def display_leaderboard(self):
        sorted_players = sorted(
            self.players.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )[:10]
        
        # Create embed for channel
        channel_embed = discord.Embed(title="Current Standings", color=0x00ff00)
        for i, (_, player) in enumerate(sorted_players, 1):
            channel_embed.add_field(
                name=f"{i}. {player['name']}", 
                value=f"Score: {player['score']}", 
                inline=False
            )
        await self.channel.send(embed=channel_embed)
        
        # Send standings to each player's DM
        for player_id in self.players:
            try:
                member = await self.channel.guild.fetch_member(player_id)
                if member:
                    dm_embed = discord.Embed(title="Your Current Standing", color=0x00ff00)
                    player_score = self.players[player_id]["score"]
                    position = next(i for i, (pid, _) in enumerate(sorted_players, 1) if pid == player_id)
                    dm_embed.add_field(name="Your Position", value=f"#{position}", inline=False)
                    dm_embed.add_field(name="Your Score", value=str(player_score), inline=False)
                    await member.send(embed=dm_embed)
            except:
                continue
        
        await asyncio.sleep(5)  # Show standings for 5 seconds

    async def display_question(self, question):
        self.answered_users.clear()
        
        # Clean up HTML entities in the question text
        question_text = question['question'].replace("&quot;", '"').replace("&#039;", "'")
        
        # Shuffle options ONCE for all players
        options = question['incorrect_answers'] + [question['correct_answer']]
        random.shuffle(options)
        self.current_options = options
        
        for player_id in self.players:
            try:
                member = await self.channel.guild.fetch_member(player_id)
                if member:
                    dm_embed = discord.Embed(title=question_text, color=0x00ff00)
                    
                    # Use the same shuffled options for everyone
                    for i, option in enumerate(self.current_options, 1):
                        clean_option = option.replace("&quot;", '"').replace("&#039;", "'")
                        dm_embed.add_field(name=f"Option {i}", value=clean_option, inline=True)
                    
                    msg = await member.send(embed=dm_embed)
                    for i in range(len(options)):
                        await msg.add_reaction(f"{i+1}\u20e3")
            except:
                continue

        await self.channel.send("Question sent to all players! You have 30 seconds to answer.")

    async def start_game(self):
        if not await self.register_players():
            return

        questions = await self.fetch_questions()
        for question in questions:
            if not self.active:
                break

            await self.display_question(question)
            start_time = time.time()
            
            try:
                while time.time() - start_time < 30 and len(self.answered_users) < len(self.players):
                    try:
                        reaction, user = await bot.wait_for(
                            'reaction_add',
                            timeout=max(0, 30 - (time.time() - start_time)),
                            check=lambda r, u: (
                                not u.bot and
                                u.id in self.players and
                                u.id not in self.answered_users and
                                str(r.emoji)[0].isdigit() and
                                int(str(r.emoji)[0]) <= len(self.current_options)
                            )
                        )
                        
                        self.answered_users.add(user.id)
                        answer_index = int(str(reaction.emoji)[0]) - 1
                        
                        if self.current_options[answer_index] == question['correct_answer']:
                            # Calculate points based on speed (max 1000 points, minimum 500)
                            time_taken = time.time() - start_time
                            points = max(500, int(1000 * (1 - (time_taken / 30))))
                            self.players[user.id]["score"] += points
                            await user.send(f"Correct! +{points} points!")
                        else:
                            await user.send(f"Wrong! The correct answer was: {question['correct_answer']}")
                            
                    except asyncio.TimeoutError:
                        break
                        
            except asyncio.TimeoutError:
                pass
                
            await self.channel.send(f"Time's up! The correct answer was: {question['correct_answer']}")
            await self.display_leaderboard()
            await asyncio.sleep(3)  # Short break between questions

        # Game ended - show final results
        await self.channel.send("🎮 Game Over! 🎮")
        await self.display_leaderboard()
        
        # Update database with final scores
        for user_id, player in self.players.items():
            await self.update_score(user_id, player["name"], player["score"])

    async def fetch_questions(self):
        async with aiohttp.ClientSession() as session:
            async with session.get('https://opentdb.com/api.php?amount=10&type=multiple') as response:
                data = await response.json()
                return data['results']

    async def update_score(self, user_id, username, points):
        conn = sqlite3.connect('trivia.db')
        c = conn.cursor()
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute('''INSERT OR REPLACE INTO scores (user_id, username, points, last_played)
                     VALUES (?, ?, 
                            COALESCE((SELECT points FROM scores WHERE user_id = ?) + ?, ?),
                            ?)''',
                 (user_id, username, user_id, points, points, current_time))
        conn.commit()
        conn.close()

    def end_game(self):
        self.active = False
        if self.channel.id in active_games:
            del active_games[self.channel.id]

@bot.event
async def on_ready():
    print(f'Bot is ready as {bot.user}')
    setup_database()

@bot.command(name='trivia')
async def trivia(ctx):
    if ctx.channel.id in active_games:
        await ctx.send("A game is already in progress in this channel!")
        return

    game = TriviaGame(ctx.channel)
    active_games[ctx.channel.id] = game
    
    await ctx.send("Starting trivia! Get ready...")
    await game.start_game()

@bot.command(name='leaderboard')
async def leaderboard(ctx):
    conn = sqlite3.connect('trivia.db')
    c = conn.cursor()
    c.execute('''SELECT username, SUM(points) as total_points 
                 FROM scores 
                 GROUP BY username 
                 ORDER BY total_points DESC 
                 LIMIT 10''')
    leaders = c.fetchall()
    conn.close()

    embed = discord.Embed(title="🏆 Global Trivia Leaderboard 🏆", color=0x00ff00)
    for i, (username, points) in enumerate(leaders, 1):
        embed.add_field(name=f"{i}. {username}", value=f"Points: {points}", inline=False)

    await ctx.send(embed=embed)

@bot.command(name='mystats')
async def mystats(ctx):
    conn = sqlite3.connect('trivia.db')
    c = conn.cursor()
    c.execute('''SELECT points, last_played FROM scores 
                 WHERE user_id = ?''', (ctx.author.id,))
    stats = c.fetchone()
    conn.close()

    if stats:
        embed = discord.Embed(title=f"Stats for {ctx.author.name}", color=0x00ff00)
        embed.add_field(name="Total Points", value=stats[0])
        embed.add_field(name="Last Played", value=stats[1])
        await ctx.send(embed=embed)
    else:
        await ctx.send("You haven't played any trivia games yet!")

@bot.command(name='endtrivia')
async def end_trivia(ctx):
    if ctx.channel.id in active_games:
        game = active_games[ctx.channel.id]
        game.end_game()
        await ctx.send("Trivia game ended!")
    else:
        await ctx.send("No active trivia game in this channel!")

# Run the bot
bot.run(TOKEN) 