import random
import discord

class Question:
    def __init__(self, question, correct_answer, incorrect_answers, category):
        self.question = question
        self.correct_answer = correct_answer
        self.options = incorrect_answers + [correct_answer]
        random.shuffle(self.options)
        self.category = category

    async def display(self, channel):
        embed = discord.Embed(title=self.question, color=0x00ff00)
        for i, option in enumerate(self.options, 1):
            embed.add_field(name=f"Option {i}", value=option, inline=True)
        await channel.send(embed=embed) 