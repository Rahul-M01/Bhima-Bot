import discord
from discord.ext import commands
import aiohttp
import json

DRISHYAM_API = "http://localhost:8080/api/recipes"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"


class Recipe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session = None

    async def get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def cog_unload(self):
        if self.session and not self.session.closed:
            self.bot.loop.create_task(self.session.close())

    async def fetch_recipes(self, query=""):
        session = await self.get_session()
        url = f"{DRISHYAM_API}/lookup?q={query}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception:
            return None

    async def fetch_all_recipes(self):
        session = await self.get_session()
        try:
            async with session.get(f"{DRISHYAM_API}/list", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception:
            return None

    async def ask_ollama(self, prompt):
        session = await self.get_session()
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "system": (
                "You are a recipe assistant. Answer the user's cooking question using ONLY the recipe data provided. "
                "Keep answers short and helpful. If no recipe data matches, say you don't have that recipe saved."
            ),
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 4096},
        }
        try:
            async with session.post(OLLAMA_URL, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "").strip()
                return None
        except Exception:
            return None

    def format_recipe_context(self, recipes):
        lines = []
        for r in recipes:
            lines.append(f"## {r.get('title', 'Untitled')}")
            if r.get('cuisine'):
                lines.append(f"Cuisine: {r['cuisine']}")
            if r.get('cookTime'):
                lines.append(f"Cook time: {r['cookTime']}")
            if r.get('servings'):
                lines.append(f"Servings: {r['servings']}")
            if r.get('ingredients'):
                lines.append(f"Ingredients:\n{r['ingredients']}")
            if r.get('instructions'):
                lines.append(f"Instructions:\n{r['instructions']}")
            lines.append("")
        return "\n".join(lines)

    @commands.command(name='recipes', help='List all saved recipes.')
    async def list_recipes(self, ctx):
        async with ctx.typing():
            recipes = await self.fetch_all_recipes()

        if recipes is None:
            await ctx.send("Couldn't reach the recipe server. Is Drishyam running?")
            return

        if not recipes:
            await ctx.send("No recipes saved yet.")
            return

        embed = discord.Embed(title="Saved Recipes", color=0xe67e22)
        for r in recipes[:25]:
            name = r.get('title', 'Untitled')
            cuisine = r.get('cuisine', '')
            embed.add_field(name=name, value=cuisine or "—", inline=True)
        embed.set_footer(text=f"{len(recipes)} recipe(s) total")
        await ctx.send(embed=embed)

    @commands.command(name='recipe', help='Search for a recipe. Usage: !recipe chicken tikka')
    async def search_recipe(self, ctx, *, query: str):
        async with ctx.typing():
            recipes = await self.fetch_recipes(query)

        if recipes is None:
            await ctx.send("Couldn't reach the recipe server. Is Drishyam running?")
            return

        if not recipes:
            await ctx.send(f"No recipes found for **{query}**.")
            return

        r = recipes[0]
        embed = discord.Embed(title=r.get('title', 'Untitled'), color=0x2ecc71)

        if r.get('cuisine'):
            embed.add_field(name="Cuisine", value=r['cuisine'], inline=True)
        if r.get('cookTime'):
            embed.add_field(name="Cook Time", value=r['cookTime'], inline=True)
        if r.get('servings'):
            embed.add_field(name="Servings", value=r['servings'], inline=True)

        if r.get('ingredients'):
            ingredients = r['ingredients']
            if len(ingredients) > 1024:
                ingredients = ingredients[:1021] + "..."
            embed.add_field(name="Ingredients", value=ingredients, inline=False)

        if r.get('instructions'):
            instructions = r['instructions']
            if len(instructions) > 1024:
                instructions = instructions[:1021] + "..."
            embed.add_field(name="Instructions", value=instructions, inline=False)

        if len(recipes) > 1:
            others = ", ".join(rr.get('title', '?') for rr in recipes[1:5])
            embed.set_footer(text=f"Also found: {others}")

        await ctx.send(embed=embed)

    @commands.command(name='ask', help='Ask a cooking question. AI answers from your saved recipes. Usage: !ask how do I make tikka masala?')
    async def ask_recipe(self, ctx, *, question: str):
        async with ctx.typing():
            recipes = await self.fetch_recipes("")

        if recipes is None:
            await ctx.send("Couldn't reach the recipe server. Is Drishyam running?")
            return

        if not recipes:
            await ctx.send("No recipes saved yet — add some first!")
            return

        context = self.format_recipe_context(recipes)
        prompt = f"Here are the user's saved recipes:\n\n{context}\n\nUser question: {question}"

        async with ctx.typing():
            answer = await self.ask_ollama(prompt)

        if not answer:
            await ctx.send("Couldn't get an answer from the AI. Is Ollama running?")
            return

        if len(answer) > 2000:
            answer = answer[:1997] + "..."

        embed = discord.Embed(description=answer, color=0x9b59b6)
        embed.set_author(name="Drishyam", icon_url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Asked: {question}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Recipe(bot))
