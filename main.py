import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
from flask import Flask
from threading import Thread

TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN が Render の Environment Variables に設定されていません")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print("Slash command sync failed:", e)

    print(f"Logged in as {bot.user}")

short_term = defaultdict(deque)
long_term = defaultdict(deque)

def has_everyone_or_here(text: str) -> bool:
    return "@everyone" in text or "@here" in text

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if not isinstance(message.author, discord.Member):
        return
    if not has_everyone_or_here(message.content):
        return

    now = datetime.now(timezone.utc)
    uid = message.author.id

    short_term[uid].append(now)
    while short_term[uid] and (now - short_term[uid][0]).total_seconds() > 10:
        short_term[uid].popleft()

    long_term[uid].append(now)
    while long_term[uid] and (now - long_term[uid][0]).total_seconds() > 300:
        long_term[uid].popleft()

    if len(short_term[uid]) >= 5:
        await message.author.timeout(
            now + timedelta(days=1),
            reason="10秒間に@everyone/@hereを5回使用"
        )
        short_term[uid].clear()
        return

    if len(long_term[uid]) >= 20:
        await message.author.timeout(
            now + timedelta(minutes=60),
            reason="5分間に@everyone/@hereを20回使用"
        )
        long_term[uid].clear()
        return

    await bot.process_commands(message)

@bot.tree.command(name="ban", description="ユーザーをBANします")
@app_commands.describe(user="BANするユーザー", reason="理由")
async def ban_cmd(interaction: discord.Interaction, user: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("権限がありません", ephemeral=True)
        return

    await user.ban(reason=reason)
    await interaction.response.send_message(f"{user.mention} をBANしました\n理由: {reason}")

@bot.tree.command(name="kick", description="ユーザーをキックします")
@app_commands.describe(user="キックするユーザー")
async def kick_cmd(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("権限がありません", ephemeral=True)
        return

    await user.kick()
    await interaction.response.send_message(f"{user.mention} をキックしました")

@bot.tree.command(name="timeout", description="ユーザーをタイムアウトします")
@app_commands.describe(user="対象ユーザー", time="時間（分）")
async def timeout_cmd(interaction: discord.Interaction, user: discord.Member, time: int):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("権限がありません", ephemeral=True)
        return

    until = datetime.now(timezone.utc) + timedelta(minutes=time)
    await user.timeout(until, reason=f"手動タイムアウト: {time}分")

    await interaction.response.send_message(f"{user.mention} を {time} 分タイムアウトしました")

@bot.tree.command(name="role-create", description="ロールを作成します")
@app_commands.describe(name="ロール名")
async def role_create(interaction: discord.Interaction, name: str):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("権限がありません", ephemeral=True)
        return

    role = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(f"ロール `{role.name}` を作成しました")

@bot.tree.command(name="role-add", description="ユーザーにロールを付与します")
@app_commands.describe(user="対象ユーザー", role="付与するロール")
async def role_add(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    if not interaction.user.guild_permissions.manage_roles:
        await interaction.response.send_message("権限がありません", ephemeral=True)
        return

    await user.add_roles(role)
    await interaction.response.send_message(f"{user.mention} に `{role.name}` を付与しました")

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive"

def run():
    app.run(host="0.0.0.0", port=8080)

Thread(target=run, daemon=True).start()

bot.run(TOKEN)
