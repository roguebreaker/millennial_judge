import discord
import os
import re
from dotenv import load_dotenv
from discord.ext import commands
from discord.commands import Option

class MyModal(discord.ui.Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(discord.ui.InputText(label="Runs Name"))
        self.add_item(discord.ui.InputText(label="Password", required=False))
        self.run_name = None
        self.password = ''

    async def callback(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Run Info")
        embed.add_field(name="Runs Name", value=self.children[0].value)
        embed.add_field(name="Password", value=self.children[1].value)
        self.run_name = self.children[0].value.strip()
        self.password = self.children[1].value.strip()
        await interaction.response.send_message(embeds=[embed])
        self.stop()

active_runs = {}
runs_num = 0

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.all()
bot = commands.Bot(intents=intents)
guild_ids = [333045209279758336]

@bot.event
async def on_ready():
    print('Ready!')

@bot.slash_command(name="host", description="Host a new game", guild_ids=guild_ids)
async def host(ctx,
               ladder: Option(str, "Ladder or non-ladder", choices=["Non-Ladder", "Ladder"], required=True),
               type: Option(str, "What type of run is this?", choices=["Baal", "TZ", "Chaos", "PVP"], required=True)):
    global active_runs
    global runs_num
    if ctx.author not in active_runs.keys():
        runs_num += 1
        modal = MyModal(title="Input for run")
        await ctx.send_modal(modal)
        await modal.wait()
        active_runs[ctx.author] = { 'ladder': ladder, 'type': type, 'runner': ctx.author,
                                    'attendees': [], 'runs_num': runs_num,
                                    'runs_name': modal.run_name, 'runs_password': modal.password, }
    else:
        await ctx.respond("You are already hosting a run!")

@bot.slash_command(name="end", description="End a run", guild_ids=guild_ids)
async def end(ctx):
    global active_runs
    global runs_num
    if ctx.author in active_runs.keys():
        del active_runs[ctx.author]
        runs_num -= 1
        await ctx.respond("You have ended the run.")
    else:
        await ctx.respond("No runs exist under your user.")

@bot.slash_command(name="runs", description="Show current runs.", guild_ids=guild_ids)
async def runs(ctx):
    global active_runs
    if len(active_runs) > 0:
        message = 'Here is a list of the current runs:\n\n'
        for run in active_runs.keys():
            run_num = str(active_runs[run]['runs_num'])
            runner = active_runs[run]['runner']
            ladder = active_runs[run]['ladder']
            type = active_runs[run]['type']
            runner = str(active_runs[run]['runner'])
            name = active_runs[run]['runs_name']
            password = active_runs[run]['runs_password']
            message += f"Run ID: {run_num}\nGame Name: {str(name)}\nGame Password: {password}\nRunner: {runner}, Ladder: {ladder}, Type: {type}\n"
            attendees = [str(x) for x in active_runs[run]['attendees']]
            attendees = ', '.join(attendees)
            message += f"Attendees: {attendees}\n\n"
        await ctx.respond(message)
    else:
        await ctx.respond("There are no current runs.")

@bot.slash_command(name="join", description="Join a run.", guild_ids=guild_ids)
async def join(ctx,
               run: Option(str, "Choose a run.", required=True)):
    if ctx.author not in active_runs.keys():
        for my_run in active_runs.keys():
            if str(active_runs[my_run]['runs_num']) == run:
                if len(active_runs[my_run]['attendees']) < 8:
                    if ctx.author not in active_runs[my_run]['attendees']:
                        active_runs[my_run]['attendees'].append(ctx.author)
                        await ctx.respond(f"You have been added to {active_runs[my_run]['runner']}'s runs.")
                    else:
                        await ctx.respond(f"You are already in this run.")
                else:
                    await ctx.respond("The run is full.")

    else:
        await ctx.respond("You must stop hosting to join.")

@bot.slash_command(name="leave", description="Leave a run.", guild_ids=guild_ids)
async def leave(ctx):
    global active_runs
    for runner in active_runs.keys():
        if ctx.author in active_runs[runner]['attendees']:
            active_runs[runner]['attendees'].remove(ctx.author)
            await ctx.respond("You have left the run.")

@bot.slash_command(name="ng", description="Increment your run", guild_ids=guild_ids)
async def ng(ctx):
    global active_runs
    if ctx.author in active_runs.keys():
        my_run = active_runs[ctx.author]
        run_name = my_run['runs_name']
        matches = re.findall("[0-9]*$", run_name)
        match = matches[0]
        new_match = str(int(match) + 1).zfill(len(match))
        run_name = run_name.replace(match, new_match)
        active_runs[ctx.author]['runs_name'] = run_name
        await ctx.respond(f"New run at: {run_name}")
    else:
        for runner in active_runs.keys():
            for attendee in active_runs[runner]['attendees']:
                if attendee == ctx.author:
                    my_run = active_runs[runner]
                    run_name = my_run['runs_name']
                    matches = re.findall("[0-9]*$", run_name)
                    match = matches[0]
                    new_match = str(int(match) + 1).zfill(len(match))
                    run_name = run_name.replace(match, new_match)
                    active_runs[runner]['runs_name'] = run_name
                    await ctx.respond(f"New run at: {run_name}")

bot.run(TOKEN)