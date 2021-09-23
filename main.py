# Sorry if my code sucks, at least it works (I hope)

import sys
from pymongo import *
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
from discord import *

MONGO_URL = sys.argv[1]
DISCORD_TOKEN = sys.argv[2]

mongo_client = MongoClient(MONGO_URL, server_api=ServerApi('1'))
discord_client = Client()

# EVENTS


@discord_client.event
async def on_ready():
    print("Ready.")


@discord_client.event
async def on_message(msg: Message):
    if msg.author != discord_client.user:
        await handle_commands(msg)


@discord_client.event
async def on_member_join(member: Member):
    embed, enabled = get_welcome(member.guild, member)
    welcome_channel = get_welcome_channel(member.guild)
    if enabled and welcome_channel is not None:
        await welcome_channel.send(embed=embed)

# LOGIC


def get_document(guild: Guild, collection: str, filter: dict):
    return mongo_client[str(guild.id)][collection].find_one(filter)


def insert_document(guild: Guild, collection: str, value: dict):
    return mongo_client[str(guild.id)][collection].insert_one(value)


def update_document(guild: Guild, collection: str, filter: dict, value: dict):
    return mongo_client[str(guild.id)][collection].update_one(filter, value)


def update_user(guild: Guild, user: User, update: dict):
    if get_document(guild, "profiles", {"id": user.id}) is not None:
        update_document(guild, "profiles", {"id": user.id}, update)
    else:
        insert_document(guild, "profiles", {"id": user.id})
        update_document(guild, "profiles", {"id": user.id}, update)


def get_prefix(guild: Guild) -> str:
    s = get_document(guild, "settings", {"name":"prefix"})
    if s is not None:
        return s["value"]
    else:
        insert_document(guild ,"settings", {"name":"prefix", "value":"!"})
        return "!"


def get_welcome_channel(guild: Guild) -> TextChannel:
    welcome_channel = get_document(guild,"settings",{"name":"welcome channel"})
    if welcome_channel is not None:
        for channel in guild.channels:
            if channel.id is welcome_channel["id"]:
                return channel
            elif welcome_channel["id"] is None:
                return None
    else:
        insert_document(guild,"settings",{"name":"welcome channel","id":None})
        return None


def get_welcome(guild: Guild, new_user: User) -> (Embed, bool):
    welcome_json = get_document(guild, "settings", {"name":"welcome embed"})
    if welcome_json is not None:
        embed = Embed()
        if welcome_json["header"] is True:
            embed.set_author(name="{}#{}".format(new_user.name, new_user.discriminator), icon_url=new_user.avatar_url)
        if welcome_json["footer"] is True:
            embed.set_author(name="{}#{}".format(new_user.name, new_user.discriminator), icon_url=new_user.avatar_url)
        if welcome_json["icon"] is True:
            embed.set_image(new_user.avatar_url)
        embed.color = Color.from_rgb(welcome_json["r"], welcome_json["g"], welcome_json["b"])
        embed.title = welcome_json["welcome message"]

        return embed, welcome_json["enabled"]
    else:
        insert_document(guild, "settings", {
            "name":"welcome embed",
            "enabled": True,
            "header": True,
            "footer": False,
            "welcome message": "Welcome to our server!",
            "icon": True,
            "r": 218,
            "g": 10,
            "b": 160
        })
        return get_welcome(guild)


def create_transaction(guild: Guild, sender: Member, recipient: Member, amount: int) -> str:
    if amount <= get_document(guild, "profiles", {"id":sender.id})["score"]:
        update_user(guild, sender, {"$inc":{"score":-abs(amount)}})
        update_user(guild, recipient, {"$inc": {"score": abs(amount)}})
        id = insert_document(guild, "transactions", {
            "from": sender.id,
            "to": recipient.id,
            "amount": abs(amount)
        }).inserted_id
        return id
    else:
        raise Exception("Transaction Unauthorized. Not enough score.")


def set_prefix(guild: Guild, prefix: str):
    get_prefix(guild)
    update_document(guild,"settings",{"name":"prefix"}, {"$set":{"value" : prefix}})


async def handle_commands(msg: Message):
    message: str = msg.content
    prefix: str = get_prefix(msg.guild)
    if message.startswith(prefix):
        message = message.replace(prefix, "", 1)
        command = message.split()[0]
        args = message.split()[1:]
        try:
            if command == "test":
                await msg.channel.send("test")
            elif command == "prefix":
                await cmd_changeprefix(msg, args)
            elif command == "transaction":
                await cmd_transaction(msg, args)
            elif command == "peektransactions":
                await cmd_gettransactions(msg, args)
            elif command == "viewtransaction":
                await cmd_viewtransaction(msg, args)
            elif command == "setwelcomechannel":
                await cmd_setwelcomechannel(msg,args)
        except Exception as e:
            embed = Embed()
            embed.color = Color.red()
            embed.title = "Oh no! Something went wrong."
            embed.add_field(name="Error", value=e, inline=False)
            await msg.channel.send(embed=embed)
    else:
        update_user(msg.guild, msg.author, {"$inc": {"score": len(msg.clean_content)}})


# COMMANDS

async def cmd_setwelcomechannel(msg: Message, args: list):
    get_welcome_channel(msg.guild)
    id = int(args[0].replace("<", "").replace(">","").replace("#",""))
    print(id)
    for channel in msg.guild.channels:
        if channel.id == id:
            update_document(msg.guild,"settings",{"name":"welcome channel"},{"$set":{"id":channel.id}})
            embed = Embed()
            embed.color = Color.green()
            embed.title = "Success!"
            embed.add_field(name="Welcome messages will now be sent to", value="`#{}`".format(channel.name))
            await msg.channel.send(embed=embed)
            return
    raise Exception("Invalid channel!")


async def cmd_transaction(msg: Message, args: list):
    if len(args) == 2:
        id = create_transaction(msg.guild, msg.author, msg.mentions[0], int(args[1]))
        embed = Embed()
        embed.title = "Transaction complete!"
        embed.color = Color.green()
        embed.add_field(name="ID", value="`{}`".format(id), inline=False)
        await msg.channel.send(embed=embed)
    else:
        raise Exception("Invalid arguments.")


async def cmd_gettransactions(msg: Message, args: list):
    for mention in msg.mentions:
        embed = Embed()
        embed.set_author(name=mention.name, icon_url=mention.avatar_url)
        embed.color = Color.purple()
        embed.title = "Transactions"
        for transaction in mongo_client[str(msg.guild.id)]["transactions"].find({"from": mention.id}):
            embed.add_field(name="Sent", value="`{}`".format(transaction["_id"]), inline=False)
        for transaction in mongo_client[str(msg.guild.id)]["transactions"].find({"to": mention.id}):
            embed.add_field(name="Received", value="`{}`".format(transaction["_id"]), inline=False)
        await msg.channel.send(embed=embed)

async def cmd_viewtransaction(msg: Message, args: list):
    for transaction in args:
        transact: dict = get_document(msg.guild, "transactions", {"_id": ObjectId(transaction)})
        if(transact is not None):
            embed = Embed()
            embed.title = "Transaction Info"
            embed.add_field(name="ID", value="`{}`".format(transaction))
            embed.add_field(name="From", value="<@{}>".format(transact["from"]))
            embed.add_field(name="To", value="<@{}>".format(transact["to"]))
            embed.add_field(name="Amount", value=transact["amount"])
            embed.color = Color.orange()
            embed.set_footer(text="Requested by {}#{}".format(msg.author.name, msg.author.discriminator), icon_url=msg.author.avatar_url)
            await msg.channel.send(embed=embed)
        else:
            raise Exception("Transaction not found.")


async def cmd_changeprefix(msg: Message, args: list):
    embed = Embed()
    if len(args) > 0:
        set_prefix(msg.guild, args[0])
        embed.color = Color.green()
        embed.title = "Prefix successfully changed to: " + get_prefix(msg.guild)
        await msg.channel.send(embed=embed)
    else:
        raise Exception("Please provide a new prefix.")


discord_client.run(DISCORD_TOKEN)
