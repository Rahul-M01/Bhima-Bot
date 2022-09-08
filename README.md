# Bhima-Bot
## Info
Bhima is a discord bot, developed using Python. It has a variety of features, ranging from music to server management.

## Features
- Play music on voice chat, queue the music, adjust the volume.
- Get various stats of users on your server.
- Manage your server by banning, kicking or muting members, and also clearing the chat of any unwanted messages.

## APIs
- Perspective API
- Zen Quotes API

## List of Commands

#### Server Admin

  - !clear <messageCount> - Clears the chat of provided number of messages.
  - !kick <member> <reason> - Kicks a member with a message
  - !ban <member> <reason> - Bans a member with a message
  - !unban <member> - Unbans a member with a message
  - !mute <member> <reason> - Mutes a member with a message.
  - !unmute <member> - Unmutes a member
    
#### Music

  - !join - Joins the voice channel(NOTE: Need to be in a voice chat to work).
  - !play <query> - Plays the queried music by placing it in a queue, if valid.
  - !pause - Pauses the music
  - !resume - Resumes the music
  - !stop - Stops the music
  - !skip - Skips to the next song in the queue
  - !queue - Displays the music queue
  - !lower - Decreases the volume
  - !higher - Increases the volume
  
 #### Message Stats
 
 - !messages <member> - Displays the number of messages from a member.
 - !all-messages - Displays a count of messages form each member.
 
 #### Bot Maintenance
 - !reload <cog> - Reloads a given cog
 - !load <cog> - Loads a given cog
 - !unload <cog> - Unloads a given cog
 - !list - Displays a list of all loaded cogs
 
   
## Work in Progress
- [x] Welcoming new users to the server
- [ ] Get reminder over longer periods of time
- [x] Leveling system
- [ ] Minigame
- [ ] Polls
- [x] Weather statistics using Weather API

    
