# 🃏 Bot Cassino

Blackjack, Poker, Truco e Xadrez num bot só.

## Variáveis no Railway

| Variável | Descrição |
|---|---|
| `DISCORD_TOKEN` | Token do bot |
| `DATABASE_URL` | Postgres (Railway adiciona automaticamente) |

## Deploy

1. Suba no GitHub
2. Railway → New Project → Deploy from GitHub
3. Adicione um **Postgres** no projeto (DATABASE_URL vem automático)
4. Adicione `DISCORD_TOKEN`
5. Deploy — pronto

## Comandos

| Comando | Descrição |
|---|---|
| `/blackjack [aposta]` | Blackjack 21 |
| `/poker` | Texas Hold'em (2–6 jogadores) |
| `/truco` | Truco Paulista 2v2 |
| `/xadrez` | Xadrez 1v1 |
| `/fichas` | Ver saldo |
| `/bonus` | Bônus diário (300 fichas) |
| `/ranking` | Top 10 |
| `/transferir` | Transferir fichas |

## Sobre as imagens

Edite `cogs/render.py` quando tiver as imagens de IA prontas.
