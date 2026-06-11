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
        
        # Sistema de Placar Persistente
        self.wins = 0
        self.losses = 0
        self.ties = 0

    def deal(self):
        # Reinicia o baralho se estiver ficando vazio
        if len(self.deck) < 20:
            self.deck = [Card(s, r) for s in SUITS for r in RANKS] * 4
            random.shuffle(self.deck)
            
        self.player_hand = [self.deck.pop(), self.deck.pop()]
        self.dealer_hand = [self.deck.pop(), self.deck.pop()]
        self.game_over = False
        self.result = None

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
            self.losses += 1
        elif dealer_val > 21:
            self.result = "🎉 **Dealer estourou! Você venceu!**"
            self.wins += 1
        elif player_val > dealer_val:
            self.result = "🎉 **Você venceu!**"
            self.wins += 1
        elif player_val == dealer_val:
            self.result = "🤝 **Empate!**"
            self.ties += 1
        else:
            self.result = "😔 **Dealer venceu.**"
            self.losses += 1


class BlackjackView(View):
    def __init__(self, game: BlackjackGame):
        super().__init__(timeout=300) # 5 minutos de inatividade
        self.game = game
        
        # O botão de próxima mão começa desativado
        for child in self.children:
            if child.custom_id == "bj_next":
                child.disabled = True

    async def update(self, interaction: discord.Interaction):
        # Atualiza o estado de ativação de todos os botões dinamicamente
        for child in self.children:
            if child.custom_id in ["bj_hit", "bj_stand"]:
                child.disabled = self.game.game_over
            elif child.custom_id in ["bj_double", "bj_surrender"]:
                # Só permite double/surrender com exatamente 2 cartas na mão
                child.disabled = self.game.game_over or len(self.game.player_hand) > 2
            elif child.custom_id == "bj_next":
                # Só ativa a próxima mão quando o jogo atual terminar
                child.disabled = not self.game.game_over

        embed, file = self.create_embed()
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)

    def draw_cards_to_image(self):
        # Dimensões mais verticais (500x420) para ocupar melhor a tela do celular
        img = Image.new('RGB', (500, 420), color='#144728')
        draw = ImageDraw.Draw(img)
        
        # Fontes bem maiores para alta legibilidade no Mobile
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22)
            card_rank_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
            card_suit_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
        except:
            # Fallback caso o sistema não ache a fonte padrão do Linux
            try:
                font = ImageFont.load_default(size=22)
                card_rank_font = ImageFont.load_default(size=20)
                card_suit_font = ImageFont.load_default(size=38)
            except:
                font = ImageFont.load_default()
                card_rank_font = ImageFont.load_default()
                card_suit_font = ImageFont.load_default()

        def draw_hand(hand, start_y, hide_first=False):
            start_x = 30
            # Cartas maiores (85x125)
            for i, card in enumerate(hand):
                card_rect = [start_x, start_y, start_x + 85, start_y + 125]
                
                if hide_first and i == 0:
                    # Carta virada do Dealer
                    draw.rounded_rectangle(card_rect, radius=7, fill="#1c3b57", outline="#ffffff", width=2)
                    draw.text((start_x + 32, start_y + 45), "?", fill="#ffffff", font=card_suit_font)
                else:
                    # Carta aberta
                    draw.rounded_rectangle(card_rect, radius=7, fill="#ffffff", outline="#000000", width=1)
                    # Rank no canto superior esquerdo
                    draw.text((start_x + 8, start_y + 8), card.rank, fill=card.color, font=card_rank_font)
                    # Naipe grande centralizado
                    draw.text((start_x + 28, start_y + 45), card.suit, fill=card.color, font=card_suit_font)
                
                start_x += 92

        # Renderização do Painel do Dealer
        dealer_text = f"DEALER (Total: {self.game.hand_value(self.game.dealer_hand) if self.game.game_over else '?'})"
        draw.text((30, 15), dealer_text, fill="#ffffff", font=font)
        draw_hand(self.game.dealer_hand, 50, hide_first=not self.game.game_over)

        # Renderização do Painel do Jogador
        player_text = f"VOCÊ (Total: {self.game.hand_value(self.game.player_hand)})"
        draw.text((30, 200), player_text, fill="#ffffff", font=font)
        draw_hand(self.game.player_hand, 235)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return discord.File(buffer, filename="blackjack.png")

    def create_embed(self):
        embed = discord.Embed(title="🃏 **BLACKJACK MESA PRIVADA**", color=0x144728)
        
        # Placar persistente exibido no topo do embed
        embed.description = (
            f"🏆 **Seu Placar:** {self.game.wins} Vitórias | {self.game.losses} Derrotas | {self.game.ties} Empates\n"
            f"──────────────────────────"
        )

        if self.game.game_over:
            embed.add_field(name="**RODADA ENCERRADA**", value=self.game.result, inline=False)
            embed.set_footer(text="Clique em 'Próxima Mão 🔁' para continuar jogando nesta mesa.")
        else:
            embed.set_footer(text=f"Mesa ativa de: {self.game.player.display_name}")

        file = self.draw_cards_to_image()
        embed.set_image(url="attachment://blackjack.png")
        return embed, file

    def check_user(self, interaction: discord.Interaction):
        return interaction.user.id == self.game.player.id

    @discord.ui.button(label="Hit (Pedir)", style=discord.ButtonStyle.green, custom_id="bj_hit", row=0)
    async def hit(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.player_hit()
        if self.game.hand_value(self.game.player_hand) > 21:
            self.game.game_over = True
            self.game.evaluate_winner()

        await self.update(interaction)

    @discord.ui.button(label="Stand (Manter)", style=discord.ButtonStyle.grey, custom_id="bj_stand", row=0)
    async def stand(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.dealer_play()
        self.game.game_over = True
        self.game.evaluate_winner()
        await self.update(interaction)

    @discord.ui.button(label="Double (Dobrar)", style=discord.ButtonStyle.blurple, custom_id="bj_double", row=0)
    async def double(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.player_hit()
        self.game.dealer_play()
        self.game.game_over = True
        self.game.evaluate_winner()
        await self.update(interaction)

    @discord.ui.button(label="Surrender (Correr)", style=discord.ButtonStyle.red, custom_id="bj_surrender", row=0)
    async def surrender(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.game_over = True
        self.game.result = "🏳️ **Você rendeu-se desta mão! O Dealer recolhe as cartas.**"
        self.game.losses += 1
        await self.update(interaction)

    # NOVO BOTÃO: Permite continuar jogando infinitamente na mesma mesa
    @discord.ui.button(label="Próxima Mão 🔁", style=discord.ButtonStyle.blurple, custom_id="bj_next", row=1)
    async def next_hand(self, interaction: discord.Interaction, button: Button):
        if not self.check_user(interaction):
            return await interaction.response.send_message("Esta mesa não é sua!", ephemeral=True)

        self.game.deal() # Distribui novas cartas mantendo o placar intacto
        await self.update(interaction)


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

TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("ERRO: A variável de ambiente DISCORD_TOKEN não foi encontrada.")
