# Sorry if my code sucks, at least it works (I hope)

import sys
from pymongo import *
from pymongo.server_api import ServerApi
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
    update_user(msg.guild, msg.author, {"$inc":{"score":len(msg.content)}})

    if msg.author != discord_client.user:
        await handle_commands(msg)

# LOGIC


def get_document(guild: Guild, collection: str, filter: dict):
    return mongo_client[str(guild.id)][collection].find_one(filter)


def insert_document(guild: Guild, collection: str, value: dict):
    return mongo_client[str(guild.id)][collection].insert_one(value)


def update_document(guild: Guild, collection: str, filter: dict, value: dict):
    return mongo_client[str(guild.id)][collection].update_one(filter, value)


def update_user(guild: Guild, user: User, update: dict):
    if get_document(guild, "profiles", {"id":user.id}) is not None:
        update_document(guild, "profiles", {"id":user.id}, update)
    else:
        insert_document(guild, "profiles", {"id":user.id})
        update_document(guild, "profiles", {"id": user.id}, update)

def get_prefix(guild: Guild) -> str:
    s = get_document(guild, "settings", {"name":"prefix"})
    if s is not None:
        return s["value"]
    else:
        insert_document(guild ,"settings", {"name":"prefix", "value":"!"})
        return "!"


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
        if command == "test":
            await msg.channel.send("test")
        elif command == "prefix":
            await cmd_changeprefix(msg, args)
        elif command == "like":
            await cmd_like(msg, args)
        elif command == "dislike":
            await  cmd_dislike(msg, args)

# COMMANDS


async def cmd_like(msg: Message, args: list):
    update_user(msg.guild, msg.mentions[0], {"$inc":{"score":1}})


async def cmd_dislike(msg: Message, args: list):
    update_user(msg.guild, msg.mentions[0], {"$inc":{"score":-1}})


async def cmd_changeprefix(msg: Message, args: list):
    if len(args) > 0:
        set_prefix(msg.guild, args[0])
        await msg.channel.send("Prefix successfully changed to: " + get_prefix(msg.guild))
    else:
        await msg.channel.send("Please provide a new prefix.")

discord_client.run(DISCORD_TOKEN)
