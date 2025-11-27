# Harvard Yale Trading Competition

-as witnessed by Andrew Gu

# Setup
The Oracle uses a fictional currency called QTC, which you will use to buy and sell contracts. Below is the list of tickers for each contract and what values they will settle to (in QTC). 
* HRVD: 
This contract settles to 100 if Harvard wins The Game; 0 if Harvard does not. 
* YALE: 
This contract settles to 100 if Yale wins The Game; 0 if Yale does not. 
* SUM: 
This contract settles to the number of points scored in total by both teams.
* DIFF: 
This contract settles to the ABSOLUTE difference in points scored by the teams.
* TDS: 
This contract settles to the 10 times the total number of touchdowns scored in total by both teams.
* TIME: 
This contract settles to the number of (real, not game time) minutes between 12:00 pm and the time at which the first touchdown is scored from either team.

We had a designated market maker run by HUQT member Haozhe Stephen Yang, providing ~100% uptime liquidity. We also had consistent artificial retail flow. However, with the market maker’s spreads at 6–8 QTC, we wanted to incentivize individual traders to contribute liquidity themselves, both as a learning opportunity and as an intellectual challenge.

To start, every participant received 100 units of each contract and 50k QTC, since our exchange only supports spot trading. In particular, positions cannot go negative, meaning you cannot short a contract. This restriction limited traders’ ability to short and, as we will see, ultimately hindered effective price discovery.

We recorded every trade that happened during the event, producing the beautiful candle graphs below!

# Pregame Trading

See images in the [/full directory](./full)

Interestingly, we priced HRVD to be around 60% while Kalshi priced it to be around 70% (https://kalshi.com/markets/kxncaafgame/college-football-game/kxncaafgame-25nov22harvyale). Maybe this was due to skepticism, as we had not won a single game against Yale since I've been here (2022).

# Live Trading

See images in the [/in-game directory](./in-game)

During the game, it was a bit hard to make markets efficient because the Yale Bowl has terrible signal when there's a lot of people present. When Yale scored a touchdown 7 minutes in, the markets weren't really able to adjust, as a result. However, there were enough traders in Boston to pump Yale to above 70%. 

Unable to contact his market maker to change his quotes, Haozhe was in despair. However, HUQT member Derek Jin somehow had service and Haozhe swiftly changed several of his fair values. This can be seen in some of the large jumps in price around 14:00 PM (most noticeably in [TIME](./in-game/TIME.png) and [TDS](./in-game/TDS.png)).

# My Experience

As hinted before, Haozhe's market maker left enough space for individuals to market make. Thursday night, I quickly wrote a very simple market making bot, that would quote 3 wide. I believe I was the first to enter the market, but I soon found company (probably including our winner Jonathan Wu) while I was eating dinner. Seeing my PnL start to flatline, I just decided that people were figuring out my bot behavior and exploiting it, so I just paused my bot when I got home. In the process, I had made a good 30k QTC, that would give me a comfortable lead, assuming most people wouldn't make a bot themselves.

But due to the prize structure, where utility isn't linear with PnL, some "gambling" behavior is incentivized, in the sense that a 10% shot to make a ton of QTC at least gives you a 10% shot of landing top 10, while staying flat does nothing. To beat out traders that went full in on Harvard or Yale, I needed to join them. So I spent all the QTC I earned longing Harvard, expecting them to win. Sadly, this was not the case.

Towards the end of the game, I knew the only way to boost my PnL was to sell of all my assets and go full in on SUM and TDS, since there was still plenty of time to score points, while everything else had more or less settled. But Haozhe was able to price them approximately right, which reduced my edge.

# Strategy Ideas

There were various ideas you could play with in this competition:
* Doing arbitrage with HRVD and YALE
* Noticing TDS and SUM are highly correlated
* Noticing TDS and TIME have roughly a reciprocal relationship

However, these strategies had much lower yield than simple market making, because these ideas only work when you notice the inefficiency first and other people follow. Because these relationships were only guaranteed at settlement, these strategies would require a long holding period to complete, which made them unattractive compared to the low capital requirements of market making.

