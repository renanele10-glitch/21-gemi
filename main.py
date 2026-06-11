import os
import io
import random
import discord
from discord.ext import commands
from discord.ui import View, Button
from PIL import Image, ImageDraw, ImageFont

# Configuração básica do Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

SUITS = ['♠', '♥', '♦', '♣']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
VALUES = {'A': 11, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 10, 'J': 10, 'Q': 10, 'K': 10}

class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        return f"{self.rank}{self.suit}"

    @property
    def color(self):
        return "#ff0000" if self.suit in ['♥', '♦'] else "#000000"


class BlackjackGame:
    def __init__(self, player):
        self.player = player
        self.deck = [Card(s, r) for s in SUITS for r in RANKS] * 4
        random.shuffle(self.deck)
        self.player_hand = []
        self.dealer_hand = []
        self.game_over = False
        self.result = None

    def deal(self):
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]

    def hand_value(self, hand):
        value = sum(VALUES[card.rank] for card in hand)
        aces = sum(1 for card in hand if card.rank == 'A')
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def player_hit(self):
        self.player_hand.append(self.deck.pop())

    def dealer_play(self):
        while self.hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop())

    def evaluate_winner(self):
        player_val = self.hand_value(self.player_hand)
        dealer_val = self.hand_value(self.dealer_hand)

        if player_val > 21:
            self.result = "💥 **Você estourou! Dealer vence.**"
        elif dealer_val > 21:
            self.result = "🎉 **Dealer estourou! Você venceu!**"
        elif player_val > dealer_val:
            self.result = "🎉 **Você venceu!**"
        elif player_val == dealer_val:
            self.result = "🤝 **Empate!**"
        else:
            self.result = "😔 **Dealer venceu.**"


class BlackjackView(View):
    def __init__(self, game: BlackjackGame):
        super().__init__(timeout=180)
        self.game = game

    async def update(self, interaction: discord.Interaction):
        if len(self.game.player_hand) > 2 or self.game.game_over:
            for child in self.children:
                if child.custom_id in ["bj_double", "bj_surrender"]:
                    child.disabled = True

        if self.game.game_over:
            self.disable_all()

        embed, file = self.create_embed()
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    def draw_cards_to_image(self):
        img = Image.new('RGB', (600, 350), color='#144728')
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            card_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
        except:
            font = ImageFont.load_default()
            card_font = ImageFont.load_default()

        def draw_hand(hand, start_y, hide_first=False):
            start_x = 50
            for i, card in enumerate(hand):
                card_rect = [start_x, start_y, start_x + 70, start_y + 100]
                
                if hide_first and i == 0:
                    draw.rounded_rectangle(card_rect, radius=5, fill="#1c3b57", outline="#ffffff", width=2)
                    draw.text((start_x + 25, start_y + 35), "?", fill="#ffffff", font=card_font)
                else:
                    draw.rounded_rectangle(card_rect, radius=5, fill="#ffffff", outline="#000000", width=1)
                    draw.text((start_x + 8, start_y + 8), card.rank, fill=card.color, font=font)
                    draw.text((start_x + 25, start_y + 40), card.suit, fill=card.color, font=card_font)
                
                start_x += 85

        draw.text((50, 20), f"DEALER (Total: {self.game.hand_value(self.game.dealer_hand) if self.game.game_over else '?'})", fill="#ffffff", font=font)
        draw_hand(self.game.dealer_hand, 50, hide_first=not self.game.game_over)

        draw.text((50, 170), f"VOCÊ (Total: {self.game.hand_value(self.game.player_hand)})", fill="#ffffff", font=font)
        draw_hand(self.game.player_hand, 200)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return discord.File(buffer, filename="blackjack.png")

    def create_embed(self):
        embed = discord.Embed(title="🃏 **BLACKJACK 21**", color=0x144728)
        embed.set_footer(text=f"Mesa de: {self.game.player.display_name}")

        if self.game.game_over:
            embed.add_field(name="**RESULTADO**", value=self.game.result, inline=False)
        else:
            embed.description = "Escolha sua ação nos botões abaixo."

        file = self.draw_cards_to_image()
        embed.set_image(url="attachment://blackjack.png")
        return embed, file

    def check_user(self, interaction: discord.Interaction):
        return interaction.user.id == self.game.player.id

    @discord.ui.button(label="Hit (Pedir)", style=discord.ButtonStyle.green, custom_id="bj_hit")
    async def hit(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.player_hit()
        if self.game.hand_value(self.game.player_hand) > 21:
            self.game.game_over = True
            self.game.evaluate_winner()

        await self.update(interaction)

    @discord.ui.button(label="Stand (Manter)", style=discord.ButtonStyle.grey, custom_id="bj_stand")
    async def stand(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.dealer_play()
        self.game.game_over = True
        self.game.evaluate_winner()
        await self.update(interaction)

    @discord.ui.button(label="Double (Dobrar)", style=discord.ButtonStyle.blurple, custom_id="bj_double")
    async def double(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.player_hit()
        self.game.dealer_play()
        self.game.game_over = True
        self.game.evaluate_winner()
        await self.update(interaction)

    @discord.ui.button(label="Surrender (Correr)", style=discord.ButtonStyle.red, custom_id="bj_surrender")
    async def surrender(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.game_over = True
        self.game.result = "🏳️ **Você rendeu-se! O Dealer recolhe metade da mesa.**"
        await self.update(interaction)

    def disable_all(self):
        for child in self.children:
            child.disabled = True


@bot.command(name="blackjack")
async def blackjack(ctx):
    game = BlackjackGame(ctx.author)
    game.deal()
    
    view = BlackjackView(game)
    embed, file = view.create_embed()
    await ctx.send(embed=embed, file=file, view=view)

@bot.event
async def on_ready():
    print(f"Bot online como {bot.user}")

# Puxa o Token das variáveis de ambiente (essencial para o Railway)
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("ERRO: A variável de ambiente DISCORD_TOKEN não foi encontrada.")
