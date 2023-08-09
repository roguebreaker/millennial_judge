import discord
import os
import re
import functools
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
guild_ids = [901607478523998218]

@bot.event
async def on_ready():
    print('Ready!')

@bot.slash_command(name="add1", description="Add a player to your game.", guild_ids=guild_ids)
async def add1(ctx, player: Option(discord.Member, "Select a player to add.")):
    global active_runs
    user = ctx.author
    if user in active_runs.keys():
        run_info = active_runs[user]
        if len(run_info['attendees']) < 8:
            if player != user and player not in run_info['attendees']:
                run_info['attendees'].append(player)
                await ctx.respond(f"{player.mention} has been added to your run.", ephemeral=True)
            elif player == user:
                await ctx.respond("You can't add yourself to your own run.", ephemeral=True)
            else:
                await ctx.respond(f"{player.mention} is already in your run.", ephemeral=True)
        else:
            await ctx.respond("Your run is already full.", ephemeral=True)
    else:
        for run in active_runs.keys():
            run_info = active_runs[run]
            for attendee in run_info['attendees']:
                if ctx.author == attendee:
                    run_info['attendees'].append(player)
                    await ctx.respond(f"{player.mention} has been added to your run.", ephemeral=True)

@bot.slash_command(name="kick1", description="Kick a player from your game.", guild_ids=guild_ids)
async def kick1(ctx, player: Option(discord.Member, "Select a player to kick.")):
    global active_runs
    user = ctx.author
    if user in active_runs.keys():
        run_info = active_runs[user]
        if player in run_info['attendees']:
            run_info['attendees'].remove(player)
            await ctx.respond(f"{player.mention} has been kicked from your run.", ephemeral=True)
        else:
            await ctx.respond(f"{player.mention} is not in your run.", ephemeral=True)
    else:
        for run in active_runs.keys():
            run_info = active_runs[run]
            for attendee in run_info['attendees']:
                if ctx.author == attendee:
                    run_info['attendees'].remove(player)
                    await ctx.respond(f"{player.mention} has been kicked from your run.", ephemeral=True)

@bot.slash_command(name="host1", description="Host a new game", guild_ids=guild_ids)
async def host1(ctx,
               ladder: Option(str, "Ladder or non-ladder", choices=["Non-Ladder", "Ladder"], required=True),
               type: Option(str, "What type of run is this?", choices=["Baal", "TZ", "Chaos", "PVP"], required=True)):
    global active_runs
    global runs_num
    if ctx.author not in active_runs.keys():
        if runs_num > 999:
            runs_num = 0
        runs_num += 1
        modal = MyModal(title="Input for run")
        await ctx.send_modal(modal)
        await modal.wait()
        active_runs[ctx.author] = { 'ladder': ladder, 'type': type, 'runner': ctx.author,
                                    'attendees': [], 'runs_num': runs_num,
                                    'runs_name': modal.run_name, 'runs_password': modal.password, }
    else:
        await ctx.respond("You are already hosting a run!", ephemeral=True)

@bot.slash_command(name="end1", description="End a run", guild_ids=guild_ids)
async def end1(ctx):
    global active_runs
    global runs_num
    if ctx.author in active_runs.keys():
        del active_runs[ctx.author]
        await ctx.respond("You have ended the run.", ephemeral=True)
    else:
        await ctx.respond("No runs exist under your user.", ephemeral=True)

async def join_run_callback(interaction: discord.Interaction, run_id: int):
    run_info = active_runs.get(run_id)
    if run_info:
        user = interaction.user
        existing_run = None
        for run in active_runs.values():
            if user in run['attendees']:
                existing_run = run
                break
        if existing_run:
            existing_run['attendees'].remove(user)
            await interaction.response.send_message(content=f"You have left the run {existing_run['runs_name']}.", ephemeral=True)
        if user == run_info['runner']:
            await interaction.response.send_message(content="You can't join your own run.", ephemeral=True)
        elif len(run_info['attendees']) < 8:
            if user not in run_info['attendees']:
                run_info['attendees'].append(user)
                await interaction.response.send_message(content=f"You have been added to the run {run_info['runs_name']}.", ephemeral=True)
            else:
                await interaction.response.send_message(content="You are already in this run.", ephemeral=True)
        else:
            await interaction.response.send_message(content="The run is full.", ephemeral=True)

@bot.slash_command(name="runs1", description="Show current runs.", guild_ids=guild_ids)
async def runs1(ctx):
    global active_runs
    if len(active_runs) > 0:
        for run in active_runs.keys():
            run_info = active_runs[run]
            has_available_spots = len(run_info['attendees']) < 8
            run_num = str(active_runs[run]['runs_num'])
            runner = run
            ladder = active_runs[run]['ladder']
            type = active_runs[run]['type']
            name = active_runs[run]['runs_name']
            password = active_runs[run]['runs_password']
            message = f"Game Name: {str(name)}\nGame Password: {password}\nRunner: {str(runner)}, Ladder: {ladder}, Type: {type}\n"
            attendees = active_runs[run]['attendees']
            message += "Attendees:\n"
            for attendee in attendees:
                message += f"{str(attendee)}\n"
            message += "\n\n"
            if has_available_spots:
                join_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Join Run")
                join_button.callback = functools.partial(join_run_callback, run_id=run)
                view = discord.ui.View()
                view.add_item(join_button)
                await ctx.send(message, view=view)
            else:
                await ctx.send(message)
        await ctx.respond("See Runs Info Below:")
    else:
        await ctx.respond("There are no current runs.", ephemeral=True)

@bot.slash_command(name="leave1", description="Leave a run.", guild_ids=guild_ids)
async def leave1(ctx):
    global active_runs
    for runner in active_runs.keys():
        if ctx.author in active_runs[runner]['attendees']:
            active_runs[runner]['attendees'].remove(ctx.author)
            await ctx.respond("You have left the run.", ephemeral=True)

@bot.slash_command(name="ng1", description="Increment your run", guild_ids=guild_ids)
async def ng1(ctx):
    global active_runs
    if ctx.author in active_runs.keys():
        my_run = active_runs[ctx.author]
        run_name = my_run['runs_name']
        matches = re.findall("[0-9]*$", run_name)
        match = matches[0]
        if match == "":
            run_name = run_name + "-1"
        else:
            new_match = str(int(match) + 1).zfill(len(match))
            run_name = run_name.replace(match, new_match)
        active_runs[ctx.author]['runs_name'] = run_name
        await ctx.respond(f"New run at: {run_name}", ephemeral=True)
    else:
        for runner in active_runs.keys():
            for attendee in active_runs[runner]['attendees']:
                if attendee == ctx.author:
                    my_run = active_runs[runner]
                    run_name = my_run['runs_name']
                    matches = re.findall("[0-9]*$", run_name)
                    match = matches[0]
                    if match == "":
                        run_name = run_name + "-1"
                    else:
                        new_match = str(int(match) + 1).zfill(len(match))
                        run_name = run_name.replace(match, new_match)
                    active_runs[runner]['runs_name'] = run_name
                    await ctx.respond(f"New run at: {run_name}", ephemeral=True)

bot.run(TOKEN)