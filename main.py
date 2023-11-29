import asyncio
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
        await interaction.response.send_message('Run Created!')
        self.stop()

active_runs = {}
active_runs_lock = asyncio.Lock()
runs_num = 0
runs_num_lock = asyncio.Lock()
run_timeouts = {}
run_timeouts_lock = asyncio.Lock()

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
intents = discord.Intents.all()
bot = commands.Bot(intents=intents)
guild_ids = [333045209279758336]

async def remove_run_after_timeout(run_owner):
    global active_runs
    await asyncio.sleep(2 * 60 * 60)  # 2 hours
    async with active_runs_lock:
        if run_owner in active_runs:
            del active_runs[run_owner]
            if run_owner in run_timeouts:
                del run_timeouts[run_owner]

@bot.event
async def on_ready():
    print('Ready!')

@bot.slash_command(name="add", description="Add a player to your game.", guild_ids=guild_ids)
async def add(ctx, player: Option(discord.Member, "Select a player to add.")):
    global active_runs
    user = ctx.author
    async with active_runs_lock:
        if user in active_runs.keys():
            run_info = active_runs[user]
            if len(run_info['attendees']) < 7:
                if player != user and player not in run_info['attendees']:
                    run_info['attendees'].append(player)
                    await ctx.respond(f"{player.mention} has been added to your run.", ephemeral=True)
                elif player == user:
                    try:
                        await ctx.respond("You can't add yourself to your own run.", ephemeral=True)
                    except:
                        await ctx.followup.send("You can't add yourself to your own run.", ephemeral=True)
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

@bot.slash_command(name="kick", description="Kick a player from your game.", guild_ids=guild_ids)
async def kick(ctx, player: Option(discord.Member, "Select a player to kick.")):
    global active_runs
    user = ctx.author
    async with active_runs_lock:
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

@bot.slash_command(name="host", description="Host a new game", guild_ids=guild_ids)
async def host(ctx,
               ladder: Option(str, "Ladder or non-ladder", choices=["Non-Ladder", "Ladder"], required=True),
               type: Option(str, "What type of run is this?", choices=["Baal", "TZ", "Chaos", "PVP", "Hardcore"], required=True)):
    global active_runs
    global runs_num
    async with active_runs_lock:
        if ctx.author not in active_runs.keys():
            async with runs_num_lock:
                if runs_num > 999:
                    runs_num = 0
                runs_num += 1
            modal = MyModal(title="Input for run")
            await ctx.send_modal(modal)
            await modal.wait()
            active_runs[ctx.author] = { 'ladder': ladder, 'type': type, 'runner': ctx.author,
                                    'attendees': [], 'runs_num': runs_num,
                                    'runs_name': modal.run_name, 'runs_password': modal.password, }
            async with run_timeouts_lock:
                timeout_task = asyncio.create_task(remove_run_after_timeout(ctx.author))
                run_timeouts[ctx.author] = timeout_task
            join_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Join Run")
            join_button.callback = functools.partial(join_run_callback, run_id=ctx.author)
            view = discord.ui.View()
            view.add_item(join_button)
            await ctx.respond(f"Join {type} runs on {ladder} hosted by {ctx.author.mention}!", view=view)
        else:
            await ctx.respond("You are already hosting a run!", ephemeral=True)

@bot.slash_command(name="end", description="End a run", guild_ids=guild_ids)
async def end(ctx):
    global active_runs
    global runs_num
    async with active_runs_lock:
        if ctx.author in active_runs.keys():
            del active_runs[ctx.author]
            await ctx.respond(f"{ctx.author.mention} has ended the run.")
        else:
            await ctx.respond("No runs exist under your user.", ephemeral=True)
        async with run_timeouts_lock:
            if ctx.author in run_timeouts:
                run_timeouts[ctx.author].cancel()
                del run_timeouts[ctx.author]

async def join_run_callback(interaction: discord.Interaction, run_id):
    async with active_runs_lock:
        run_info = active_runs.get(run_id)
        if run_info:
            has_available_spots = len(run_info['attendees']) < 7
            available_spots = 7 - len(run_info['attendees'])
            user = interaction.user
            existing_run = None
            for run in active_runs.values():
                if user in run['attendees']:
                    existing_run = run
                    break
            join_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Join Run")
            join_button.callback = functools.partial(join_run_callback, run_id=run_id)
            view = discord.ui.View()
            view.add_item(join_button)
            if existing_run:
                existing_run['attendees'].remove(user)
                available_spots = 7 - len(run_info['attendees'])
                await interaction.response.send_message(content=f"{user.mention} has left the run. There are {available_spots} spots left.")
            if user == run_info['runner']:
                try:
                    await interaction.response.send_message(content="You can't join your own run.", ephemeral=True)
                    return
                except:
                    await interaction.followup.send(content="You can't join your own run.", ephemeral=True)
                    return
            elif len(run_info['attendees']) < 7:
                if user not in run_info['attendees']:
                    run_info['attendees'].append(user)
                    available_spots = 7 - len(run_info['attendees'])
                    game_info_message = f"Game Name: {run_info['runs_name']}\nGame Password: {run_info['runs_password']}"
                    await interaction.response.send_message(content=game_info_message, ephemeral=True)  # Send game details privately to the joining user
                    if available_spots > 0:
                        await interaction.followup.send(content=f"{user.mention} has been added to {run_info['runner'].mention}'s run. There are {available_spots} spots left.", view=view)
                    else:
                        await interaction.followup.send(content=f"{user.mention} has been added to {run_info['runner'].mention}'s run. There are {available_spots} spots left.")
                else:
                    await interaction.response.send_message(content="You are already in this run.", ephemeral=True)
            else:
                await interaction.response.send_message(content="The run is full.", ephemeral=True)

@bot.slash_command(name="runs", description="Show current runs.", guild_ids=guild_ids)
async def runs(ctx):
    global active_runs
    async with active_runs_lock:
        if len(active_runs) > 0:
            await ctx.respond('Getting runs...', ephemeral=True)
            for run in active_runs.keys():
                run_info = active_runs[run]
                has_available_spots = len(run_info['attendees']) < 7
                run_num = str(active_runs[run]['runs_num'])
                runner = run
                ladder = active_runs[run]['ladder']
                type = active_runs[run]['type']
                name = active_runs[run]['runs_name']
                password = active_runs[run]['runs_password']
                attendees = active_runs[run]['attendees']
                if ctx.author in attendees:
                    message = f"Game Name: {str(name)}\nGame Password: {password}\nRunner: {str(runner)}, Ladder: {ladder}, Type: {type}\n"
                else:
                    message = f"Runner: {runner.mention}, Ladder: {ladder}, Type: {type}\n"
                message += "Attendees:\n"
                for attendee in attendees:
                    message += f"{attendee.mention}\n"
                message += "\n\n"
                if has_available_spots:
                    join_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Join Run")
                    join_button.callback = functools.partial(join_run_callback, run_id=run)
                    view = discord.ui.View()
                    view.add_item(join_button)
                    await ctx.followup.send(message, view=view, ephemeral=True)
                else:
                    await ctx.followup.send(message, ephemeral=True)
        else:
            await ctx.respond("There are no current runs.", ephemeral=True)

@bot.slash_command(name="leave", description="Leave a run.", guild_ids=guild_ids)
async def leave(ctx):
    global active_runs
    async with active_runs_lock:
        if ctx.author in active_runs:
            await ctx.respond("You are the runner of this game! Use /end to end the game instead.", ephemeral=True)
            return

        for runner in active_runs.keys():
            if ctx.author in active_runs[runner]['attendees']:
                active_runs[runner]['attendees'].remove(ctx.author)
                spots_available = 7 - len(active_runs[runner]['attendees'])
                join_button = discord.ui.Button(style=discord.ButtonStyle.green, label="Join Run")
                join_button.callback = functools.partial(join_run_callback, run_id=active_runs[runner])
                view = discord.ui.View()
                view.add_item(join_button)
                await ctx.respond(f"{ctx.author.mention} has left the run. There are {spots_available} spots available in {runner.mention}'s runs.", view=view)
                return

        await ctx.respond("You are not part of any runs.", ephemeral=True)

@bot.slash_command(name="ng", description="Increment your run", guild_ids=guild_ids)
async def ng(ctx):
    global active_runs
    async with run_timeouts_lock:
        if ctx.author in run_timeouts:
            run_timeouts[ctx.author].cancel()
            timeout_task = asyncio.create_task(remove_run_after_timeout(ctx.author))
            run_timeouts[ctx.author] = timeout_task
        else:
            for runner in active_runs.keys():
                for attendee in active_runs[runner]['attendees']:
                    if attendee == ctx.author:
                        my_run = active_runs[runner]
                        run_timeouts[runner].cancel()
                        timeout_task = asyncio.create_task(remove_run_after_timeout(runner))
                        run_timeouts[runner] = timeout_task
    async with active_runs_lock:
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
