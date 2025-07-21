import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from webserver import keep_alive
import asyncio
import os

DISCORD_TOKEN = os.environ["discordkey"]

intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

GUILD_ID = 804406656787939409  # pune ID-ul serverului tău aici

# ROLE IDs (updatează cu ID-urile tale reale)
LEADER_ROLE_ID = 804611140738088970
CO_LEADER_ROLE_ID = 1380299498164584619
COOLDOWN_ROLE_ID = 1383873402728743002

MAFIA_ROLE_IDS = [
    882036077563609158,
    1216122758162022410,
    1055264107072331876,
    1298037750372765706,
    991092843848302602,
    1031948217195171841,
    1354561447925125352,
    1354561452651843594,
    1354561456619786321,
    1354561460612763790,
    1354562419577323700,
    1354562426745520280,
    1354562743499358440,
    1354562746586239046,
    1354562748767539250,
    1354562789900812500,
    1354562792895545364,
    1236060939867131984
]

cooldown_users = {}

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    guild = discord.Object(id=GUILD_ID)
    try:
        await bot.tree.sync(guild=guild)
        print("Comenzile s-au sincronizat pe server.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

    remove_cooldown_roles.start()

@tasks.loop(minutes=5)
async def remove_cooldown_roles():
    now = datetime.now(timezone.utc)
    expired = [user_id for user_id, expiry in cooldown_users.items() if now >= expiry]
    for user_id in expired:
        for guild in bot.guilds:
            member = guild.get_member(user_id)
            if member:
                role = guild.get_role(COOLDOWN_ROLE_ID)
                if role in member.roles:
                    await member.remove_roles(role)
        del cooldown_users[user_id]


# Comanda /add
@tree.command(name="add", description="Adaugă un membru în mafie", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Membrul care trebuie adăugat", rank="Gradul pe care vrei să-l dai")
@app_commands.choices(rank=[
    app_commands.Choice(name="Membru", value="membru"),
    app_commands.Choice(name="Co-Lider", value="colider")
])
async def add(interaction: discord.Interaction, user: discord.Member, rank: app_commands.Choice[str]):
    commander_mafia_roles = set(role.id for role in interaction.user.roles if role.id in MAFIA_ROLE_IDS)
    target_mafia_roles = set(role.id for role in user.roles if role.id in MAFIA_ROLE_IDS)
    cooldown_role = interaction.guild.get_role(COOLDOWN_ROLE_ID)

    if LEADER_ROLE_ID not in [role.id for role in interaction.user.roles] and \
       CO_LEADER_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("❌ Nu ai permisiunea să folosești această comandă. Doar liderii sau co-liderii pot face asta.", ephemeral=True)
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Nu-ți poți adăuga singur grade.", ephemeral=True)
        return

    if cooldown_role in user.roles:
        now = datetime.now(timezone.utc)
        expiry = cooldown_users.get(user.id)
        remaining_time = expiry - now if expiry else timedelta(days=3)
        days, hours, minutes = remaining_time.days, remaining_time.seconds // 3600, (remaining_time.seconds % 3600) // 60
        await interaction.response.send_message(f"❌ {user.mention} este în cooldown pentru încă {days}d {hours}h {minutes}m.", ephemeral=True)
        return

    if target_mafia_roles and commander_mafia_roles.isdisjoint(target_mafia_roles):
        target_mafia_names = [interaction.guild.get_role(role_id).mention for role_id in target_mafia_roles]
        await interaction.response.send_message(f"❌ Nu poți modifica gradele lui {user.mention}, face parte din {'/'.join(target_mafia_names)}.", ephemeral=True)
        return

    co_leader_role = interaction.guild.get_role(CO_LEADER_ROLE_ID)

    if rank.value == "membru":
        if not target_mafia_roles:
            mafia_role_id = next(iter(commander_mafia_roles), None)
            if mafia_role_id is None:
                await interaction.response.send_message("❌ Nu ai niciun rol de mafie valid.", ephemeral=True)
                return
            mafia_role = interaction.guild.get_role(mafia_role_id)
            if mafia_role:
                await user.add_roles(mafia_role)
                await interaction.response.send_message(f"✅ {user.mention} a primit gradul {mafia_role.mention}.")
            else:
                await interaction.response.send_message("❌ Rolul mafiei nu este definit corect. Contactează un admin.", ephemeral=True)
                return
        else:
            existing_mafia_role = interaction.guild.get_role(next(iter(target_mafia_roles)))
            await interaction.response.send_message(f"❌ {user.mention} este deja membru {existing_mafia_role.mention}.", ephemeral=True)
            return

    elif rank.value == "colider":
        leader_role = interaction.guild.get_role(LEADER_ROLE_ID)

        if leader_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Doar liderii pot da gradul de co-lider.", ephemeral=True)
            return

        if commander_mafia_roles.isdisjoint([role.id for role in user.roles]):
            await interaction.response.send_message(f"❌ {user.mention} trebuie să fie membru al mafiei înainte de a primi gradul de co-lider.", ephemeral=True)
            return

        existing_coliders = [
            m for m in interaction.guild.members
            if co_leader_role in m.roles and not commander_mafia_roles.isdisjoint(set(role.id for role in m.roles))
        ]

        if len(existing_coliders) >= 2:
            mentions = ", ".join(m.mention for m in existing_coliders)
            await interaction.response.send_message(f"❌ Există deja 2 co-lideri în mafia ta: {mentions}.", ephemeral=True)
            return

        if co_leader_role.id in [role.id for role in user.roles]:
            await interaction.response.send_message(f"❌ {user.mention} are deja gradul de co-lider.", ephemeral=True)
            return

        await user.add_roles(co_leader_role)
        await interaction.response.send_message(f"✅ {user.mention} a primit gradul de {co_leader_role.mention}.")

# Comanda /rmv
@tree.command(name="rmv", description="Scoate un grad de la un membru", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user="Membrul căruia îi scoți gradul", grad="Gradul pe care vrei să îl scoți")
@app_commands.choices(grad=[
    app_commands.Choice(name="Membru", value="membru"),
    app_commands.Choice(name="Co-Lider", value="colider")
])
async def rmv(interaction: discord.Interaction, user: discord.Member, grad: app_commands.Choice[str]):
    if LEADER_ROLE_ID not in [role.id for role in interaction.user.roles] and \
       CO_LEADER_ROLE_ID not in [role.id for role in interaction.user.roles]:
        await interaction.response.send_message("❌ Nu ai permisiunea să folosești această comandă. Doar liderii sau co-liderii pot face asta.", ephemeral=True)
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("❌ Nu-ți poți scoate singur gradele.", ephemeral=True)
        return

    commander_mafia_roles = set(role.id for role in interaction.user.roles if role.id in MAFIA_ROLE_IDS)
    target_mafia_roles = set(role.id for role in user.roles if role.id in MAFIA_ROLE_IDS)

    if not target_mafia_roles:
        await interaction.response.send_message(f"❌ {user.mention} nu face parte din nicio mafie.", ephemeral=True)
        return

    if commander_mafia_roles.isdisjoint(target_mafia_roles):
        target_mafia_names = [interaction.guild.get_role(role_id).mention for role_id in target_mafia_roles]
        await interaction.response.send_message(f"❌ Nu poți modifica gradele lui {user.mention}, face parte din {'/'.join(target_mafia_names)}.", ephemeral=True)
        return

    co_leader_role = interaction.guild.get_role(CO_LEADER_ROLE_ID)
    cooldown_role = interaction.guild.get_role(COOLDOWN_ROLE_ID)

    if grad.value == "colider":
        leader_role = interaction.guild.get_role(LEADER_ROLE_ID)
        if leader_role not in interaction.user.roles:
            await interaction.response.send_message("❌ Doar liderii pot scoate gradul de co-lider.", ephemeral=True)
            return

        if co_leader_role and co_leader_role.id in [role.id for role in user.roles]:
            await user.remove_roles(co_leader_role)
            await interaction.response.send_message(f"✅ Gradul de {co_leader_role.mention} i-a fost scos lui {user.mention}.")
            return
        else:
            await interaction.response.send_message(f"❌ {user.mention} nu are gradul de co-lider.", ephemeral=True)
            return

    elif grad.value == "membru":
        if co_leader_role in user.roles:
            await interaction.response.send_message(f"❌ {user.mention} are gradul de co-lider. Scoate mai întâi acest grad.", ephemeral=True)
            return

        removed_any = False
        removed_role_name = None

        for mafia_id in MAFIA_ROLE_IDS:
            mafia_role = interaction.guild.get_role(mafia_id)
            if mafia_role and mafia_role in user.roles:
                await user.remove_roles(mafia_role)
                removed_any = True
                removed_role_name = mafia_role.mention

        if removed_any:
            if cooldown_role:
                await user.add_roles(cooldown_role)
                cooldown_users[user.id] = datetime.now(timezone.utc) + timedelta(days=3)
            await interaction.response.send_message(f"✅ Gradul {removed_role_name} i-a fost scos lui {user.mention}, și a intrat în cooldown.")
        else:
            await interaction.response.send_message(f"❌ {user.mention} nu are grad de membru care poate fi scos.", ephemeral=True)

# Comanda /list
@tree.command(name="list", description="Listează membrii mafiei tale", guild=discord.Object(id=GUILD_ID))
async def list_mafia(interaction: discord.Interaction):
    guild = interaction.guild
    user = interaction.user

    user_mafia_roles = [role for role in user.roles if role.id in MAFIA_ROLE_IDS]
    if not user_mafia_roles:
        await interaction.response.send_message("❌ Nu faci parte din nicio mafie.", ephemeral=True)
        return

    co_leader_role = guild.get_role(CO_LEADER_ROLE_ID)
    if not co_leader_role:
        await interaction.response.send_message("❌ Rolul Co-Lider nu este configurat corect.", ephemeral=True)
        return

    response = ""
    for mafia_role in user_mafia_roles:
        mafia_members = [m for m in guild.members if mafia_role in m.roles]
        leader_role = interaction.guild.get_role(LEADER_ROLE_ID)

        leaders = [m for m in mafia_members if leader_role in m.roles]
        co_leaders = [m for m in mafia_members if co_leader_role in m.roles]
        simple_members = [
            m for m in mafia_members
            if (co_leader_role not in m.roles and leader_role not in m.roles)
        ]

        response += f"**Mafia {mafia_role.mention}** are **{len(mafia_members)}** membri:\n"
        for member in leaders:
            response += f"👑 Lider - {member.mention}\n"
        for member in co_leaders:
            response += f"🛡️ Co-Lider - {member.mention}\n"
        for member in simple_members:
            response += f"👤 Membru - {member.mention}\n"
        response += "\n"

    await interaction.response.send_message(response, ephemeral=True)

# Pornește botul
bot.run(DISCORD_TOKEN)
