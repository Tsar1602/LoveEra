import os
import random
import time
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request, render_template
from pywarera import wareraapi
from pywarera.wareraapi import WarEraServiceUnavailable

app = Flask(__name__)

DB_PATH    = 'loveera.db'
TIER_RANK  = {'platinum': 4, 'gold': 3, 'silver': 2, 'bronze': 1, 'unknown': 0}
WAR_SKILLS = ['attack', 'criticalChance', 'criticalDamages', 'armor', 'precision', 'dodge', 'lootChance']
ECO_SKILLS = ['companies', 'entrepreneurship', 'production', 'management']
RANDOM_SEEDS = [
    'wa','ar','ri','er','ra','an','na','al','el','en','ma','in',
    'on','or','sa','si','te','to','li','mi','di','co','ka','ke',
    'ro','ru','lu','mo','mu','ni','pa','pe','su','ta','vi','zo',
]

# ── Database ─────────────────────────────────────────────

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS player_searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        searched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player1 TEXT NOT NULL,
        player2 TEXT NOT NULL,
        score INTEGER NOT NULL,
        matched_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    con.commit()
    con.close()

init_db()

def record_searches(*usernames):
    try:
        con = sqlite3.connect(DB_PATH)
        con.executemany('INSERT INTO player_searches (username) VALUES (?)', [(u,) for u in usernames])
        con.commit()
        con.close()
    except Exception:
        pass

def record_match(p1, p2, score):
    try:
        con = sqlite3.connect(DB_PATH)
        con.execute('INSERT INTO matches (player1, player2, score) VALUES (?, ?, ?)', (p1, p2, score))
        con.commit()
        con.close()
    except Exception:
        pass

# ── Punchlines ───────────────────────────────────────────

PUNCHLINES = {
    'level_gap': [
        "Level: Veteran x Newbie! One carries the whole team, the other gets carried. Major sugar daddy/mommy vibes!",
        "Level: One of you has seen things the other can't even imagine yet. Classic 'I'll teach you everything' romance arc.",
        "Level: The gap is so wide, one of you is basically a tutorial NPC to the other. Adorable, honestly.",
        "Level: Seasoned war veteran meets fresh recruit. This relationship is either a mentorship or a disaster. Probably both.",
    ],
    'level_both_high': [
        "Level: Two dedicated no-lifers found each other. If you guys party up, the whole server is officially doomed.",
        "Level: You've both sacrificed sleep, social lives, and probably meals for this game. You deserve each other.",
        "Level: The server's top predators, now sharing a nest. The enemy factions are already filing a complaint.",
        "Level: Both elite. Both unhinged. The wedding invitation will just say 'No newbies allowed.' Iconic.",
    ],
    'level_both_low': [
        "Level: Double the deadweight! Forget about the clan wars, just go on a date and grind from level zero together.",
        "Level: Neither of you knows what you're doing yet, and honestly? That's the most romantic thing on this server.",
        "Level: You're both still figuring out the tutorial. Grow up together and maybe you'll conquer the server. Maybe.",
        "Level: Two lost souls, same clueless energy. You'll either level up together or ragequit holding hands.",
    ],
    'build_eco_war': [
        "Build: The perfect synergy. One acts as the Sugar Daddy/Mommy funding the military, the other acts as the ruthless enforcer.",
        "Build: Brains and brawn. One prints the gold, the other spends it on wars. The server's most dangerous power couple.",
        "Build: Economy meets army. You're basically a nation-state. Other players should be very, very worried.",
        "Build: One builds the empire, the other defends it. This isn't a relationship — it's a hostile takeover of the server.",
    ],
    'build_eco_eco': [
        "Build: Capitalism at its finest. You two will monopolize the server's market, but who is going to defend the base?",
        "Build: Two accountants in love. Your dates are spreadsheets and your honeymoon is a market crash you engineered.",
        "Build: Maximum profit, zero combat power. Cute couple though — right up until someone raids your undefended base.",
        "Build: You've cornered the server economy together. Congratulations. Nobody can afford anything. You're villains.",
    ],
    'build_war_war': [
        "Build: Total destruction! A toxic power couple that will burn the server to the ground. Highly volatile.",
        "Build: Two war machines in a relationship. Arguments escalate to sieges. Makeup gifts are weapons. It's fine.",
        "Build: Maximum aggression, zero compromise. Your couple energy is basically a controlled explosion — emphasis on 'explosion'.",
        "Build: The server's nightmare couple. Between the two of you, there is not a single peaceful cell. Terrifying.",
    ],
    'wealth_both_rich': [
        "Wealth: Crazy Rich WarEra! This isn't a romance; it's a corporate merger to monopolize the server's entire economy.",
        "Wealth: Two loaded wallets, one power couple. The prenup alone will be the most expensive document on the server.",
        "Wealth: You don't need each other — you CHOOSE each other. That's either true love or a tax strategy.",
        "Wealth: Both swimming in gold. Your couple nickname is literally 'The 1%'. Other players will hate you. Together.",
    ],
    'wealth_big_gap': [
        "Wealth: Love is blind, but gold is shiny. One has a loaded wallet, the other is a professional freeloader. A match made in heaven!",
        "Wealth: One of you is buying the server; the other can't afford a basic sword. Somehow this works.",
        "Wealth: Rich meets broke. Classic Cinderella arc, except Cinderella has a kill count and needs ammo.",
        "Wealth: One funds the whole operation. The other brings the vibes. Honestly? Fair trade.",
    ],
    'wealth_both_broke': [
        "Wealth: You're both broke and somehow found each other. That's not poverty — that's destiny. Painful, grinding destiny.",
        "Wealth: Neither of you can afford a date, so your relationship is just farming side by side in silence.",
        "Wealth: Two empty wallets, one shared struggle. Start farming. Like, immediately. Together. Right now.",
        "Wealth: Soulmates in the streets, broke in the sheets. True love. No money. Maximum grind.",
    ],
    'damage_both_high': [
        "Damage: You're both cold-blooded psychopaths. Your wedding souvenirs will be loot boxes from your enemies' corpses. Terrifying.",
        "Damage: The two most feared players on the server, sharing a bed. Everyone else just logged off permanently.",
        "Damage: Combined, you've caused more destruction than a server update. The enemy faction is already grieving.",
        "Damage: Peak violence, meet peak violence. Your love language is definitely coordinated annihilation.",
    ],
    'damage_big_gap': [
        "Damage: The War Criminal and the Pacifist. It's giving major 'Beauty and the Beast' energy.",
        "Damage: One has a kill count that keeps GMs up at night. The other is peacefully farming. Balance.",
        "Damage: Chaos incarnate meets someone who hasn't even finished the main quest. This is a crossover episode.",
        "Damage: One is a weapon of mass destruction. The other is basically a tourist. Somehow they work.",
    ],
    'conclusion_high': [
        "{p1} and {p2}: certified soulmates. The server was not ready for this.",
        "The algorithm is shaking — {p1} x {p2} is the most dangerous couple on the server.",
        "Lock in, {p1} and {p2}. The server belongs to you two now.",
        "{p1} x {p2}: the crossover nobody asked for and everyone needed. History has been made.",
    ],
    'conclusion_mid': [
        "There's real potential between {p1} and {p2}. Rough around the edges, but what great love story isn't?",
        "{p1} and {p2}: not perfect, but close enough to be interesting. Give it a chance.",
        "The chemistry is there, {p1} and {p2}. Don't waste it farming solo.",
        "{p1} x {p2}: a work in progress. Every empire started somewhere.",
    ],
    'conclusion_low': [
        "{p1} and {p2}: statistically risky, but stranger things have happened.",
        "The numbers aren't great for {p1} and {p2} — but love rarely follows spreadsheets.",
        "{p1} x {p2}: it's a long shot. The best underdog stories usually are.",
        "{p1} and {p2}: start as allies first. See where the battlefield takes you.",
    ],
    'conclusion_negative': [
        "{p1} and {p2}: the algorithm is actively concerned. This is either fate or a disaster. Probably a disaster.",
        "{p1} x {p2}: the server would like to file a restraining order on everyone's behalf.",
        "In another timeline, {p1} and {p2} work out. This is not that timeline.",
        "{p1} and {p2}: zero compatibility, maximum chaos. Somehow that makes it iconic.",
    ],
}

# ── API helpers ──────────────────────────────────────────

def get_api_session():
    return wareraapi.WarEraApiSession(api_token=os.environ.get('WARERA_API_KEY', ''))

def _api_call_with_retry(fn, retries=3, delay=1.2):
    """Run fn(), retrying on 503 up to `retries` times."""
    for attempt in range(retries):
        try:
            return fn(), None
        except WarEraServiceUnavailable:
            if attempt < retries - 1:
                time.sleep(delay)
        except Exception as e:
            return None, str(e)
    return None, "503"

def get_score_override(username1, username2):
    u1 = username1.lower().strip()
    u2 = username2.lower().strip()
    names   = {u1, u2}
    sagu    = 'sagukeju'
    leen_set = {'leen_ah2871', 'leen-ah2871'}
    if sagu not in names:
        return None
    other = next((n for n in names if n != sagu), None)
    if other is None:
        return None
    if other in leen_set:
        return (85, 100)
    if other == 'creep':
        return (0, 19)
    return (70, 100)

def get_random_player(api_session, exclude_username=None):
    seeds = RANDOM_SEEDS.copy()
    random.shuffle(seeds)
    for seed in seeds[:10]:
        result, err = _api_call_with_retry(
            lambda s=seed: wareraapi.search_anything(search_text=s).execute(api_session)
        )
        if err or not result:
            continue
        user_ids = result.get('userIds', [])
        if not user_ids:
            continue
        random.shuffle(user_ids)
        for uid in user_ids:
            u, err2 = _api_call_with_retry(
                lambda i=uid: wareraapi.user_get_user_lite(user_id=i).execute(api_session)
            )
            if err2 or not u:
                continue
            player = parse_user(u)
            if exclude_username and player['username'].lower() == exclude_username.lower():
                continue
            return player, None
    return None, "WarEra server is busy right now. Please try again in a moment! ⏳"

def lookup_player(username, api_session):
    """Search for a player by username. Strictly prioritises an exact match."""
    result, err = _api_call_with_retry(
        lambda: wareraapi.search_anything(search_text=username).execute(api_session)
    )
    if err == "503":
        return None, "WarEra server is busy right now. Please try again in a moment! ⏳"
    if err:
        return None, f"Search failed: {err}"
    if not result:
        return None, f"Player '{username}' not found."
    user_ids = result.get('userIds', [])
    if not user_ids:
        return None, f"Player '{username}' not found on WarEra."

    # Load all results (up to 5) and return the exact-username match first
    username_lower = username.lower()
    first_player   = None
    for uid in user_ids[:5]:
        u, err2 = _api_call_with_retry(
            lambda i=uid: wareraapi.user_get_user_lite(user_id=i).execute(api_session)
        )
        if err2 or not u:
            continue
        player = parse_user(u)
        if first_player is None:
            first_player = player
        if player['username'].lower() == username_lower:
            return player, None          # ← exact match found, return immediately

    if first_player:
        return first_player, None
    return None, "WarEra server is busy right now. Please try again in a moment! ⏳"

def parse_user(u):
    level     = u.get('leveling', {}).get('level', 0)
    skills    = u.get('skills', {})
    war_score = sum((skills.get(s) or {}).get('level') or 0 for s in WAR_SKILLS)
    eco_score = sum((skills.get(s) or {}).get('level') or 0 for s in ECO_SKILLS)
    build     = 'eco' if eco_score >= war_score else 'war'
    return {
        'username':         u.get('username', '?'),
        'level':            level,
        'build':            build,
        'eco_score':        eco_score,
        'war_score':        war_score,
        'wealth':           u.get('rankings', {}).get('userWealth', {}).get('value') or 0,
        'military_rank':    u.get('militaryRank', 0),
        'damage_rank_tier': u.get('rankings', {}).get('userDamages', {}).get('tier', 'unknown'),
        'avatar_url':       u.get('avatarUrl') or '',
    }

def get_loveera_match(player1, player2):
    punchlines = []
    score      = random.randint(-20, 50)

    level_diff = abs(player1['level'] - player2['level'])
    if level_diff > 30:
        punchlines.append(random.choice(PUNCHLINES['level_gap']));      score += 10
    elif player1['level'] >= 80 and player2['level'] >= 80:
        punchlines.append(random.choice(PUNCHLINES['level_both_high'])); score += 15
    elif player1['level'] < 30 and player2['level'] < 30:
        punchlines.append(random.choice(PUNCHLINES['level_both_low']));  score += 3

    b1, b2 = player1['build'], player2['build']
    if 'eco' in {b1, b2} and 'war' in {b1, b2}:
        punchlines.append(random.choice(PUNCHLINES['build_eco_war']));   score += 25
    elif b1 == 'eco' and b2 == 'eco':
        punchlines.append(random.choice(PUNCHLINES['build_eco_eco']));   score -= 20
    else:
        punchlines.append(random.choice(PUNCHLINES['build_war_war']));   score -= 15

    w1, w2      = player1['wealth'], player2['wealth']
    wealth_diff = abs(w1 - w2)
    if w1 > 10000 and w2 > 10000:
        punchlines.append(random.choice(PUNCHLINES['wealth_both_rich'])); score += 15
    elif wealth_diff > 5000:
        punchlines.append(random.choice(PUNCHLINES['wealth_big_gap']));   score += 10
    elif w1 < 1000 and w2 < 1000:
        punchlines.append(random.choice(PUNCHLINES['wealth_both_broke'])); score -= 10

    t1 = TIER_RANK.get(player1['damage_rank_tier'], 0)
    t2 = TIER_RANK.get(player2['damage_rank_tier'], 0)
    if t1 >= 4 and t2 >= 4:
        punchlines.append(random.choice(PUNCHLINES['damage_both_high'])); score += 10
    elif abs(t1 - t2) >= 2:
        punchlines.append(random.choice(PUNCHLINES['damage_big_gap']));   score += 5

    override = get_score_override(player1['username'], player2['username'])
    score    = max(-99, min(100, score))
    if override:
        lo, hi = override
        score  = max(lo, min(hi, score))
        if score < lo:
            score = random.randint(lo, hi)

    p1n, p2n = player1['username'], player2['username']
    if score >= 75:   pool = 'conclusion_high'
    elif score >= 45: pool = 'conclusion_mid'
    elif score >= 0:  pool = 'conclusion_low'
    else:             pool = 'conclusion_negative'
    conclusion = random.choice(PUNCHLINES[pool]).format(p1=p1n, p2=p2n)

    return {"score": score, "punchlines": punchlines, "conclusion": conclusion}

# ── Routes ───────────────────────────────────────────────

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    try:
        api_session = get_api_session()
        result, err = _api_call_with_retry(
            lambda: wareraapi.search_anything(search_text=q).execute(api_session)
        )
        if err or not result:
            return jsonify([])
        user_ids = result.get('userIds', [])
        if not user_ids:
            return jsonify([])
        ql    = q.lower()
        users = []
        for uid in user_ids[:5]:
            try:
                u  = wareraapi.user_get_user_lite(user_id=uid).execute(api_session)
                ul = u.get('username', '').lower()
                users.append({
                    'username':   u.get('username', ''),
                    'level':      u.get('leveling', {}).get('level', 0),
                    'avatar_url': u.get('avatarUrl') or '',
                    '_sort':      0 if ul == ql else (1 if ul.startswith(ql) else 2),
                })
            except Exception:
                continue
        users.sort(key=lambda x: x['_sort'])
        for u in users:
            del u['_sort']
        return jsonify(users)
    except Exception:
        return jsonify([])

@app.route('/match')
def match():
    p1_name = request.args.get('p1', '').strip()
    p2_name = request.args.get('p2', '').strip()
    if not p1_name or not p2_name:
        return jsonify({"error": "Please provide both ?p1=USERNAME1&p2=USERNAME2"}), 400
    api_session = get_api_session()
    p1, err1 = lookup_player(p1_name, api_session)
    if err1:
        return jsonify({"error": err1}), 404
    p2, err2 = lookup_player(p2_name, api_session)
    if err2:
        return jsonify({"error": err2}), 404
    result = get_loveera_match(p1, p2)
    record_searches(p1['username'], p2['username'])
    record_match(p1['username'], p2['username'], result['score'])
    return jsonify({"player_1": p1, "player_2": p2, "match_result": result})

@app.route('/random-match')
def random_match():
    p1_name = request.args.get('p1', '').strip()
    if not p1_name:
        return jsonify({"error": "Please provide ?p1=USERNAME"}), 400
    api_session = get_api_session()
    p1, err1 = lookup_player(p1_name, api_session)
    if err1:
        return jsonify({"error": err1}), 404
    p2, err2 = get_random_player(api_session, exclude_username=p1['username'])
    if err2:
        return jsonify({"error": err2}), 500
    result = get_loveera_match(p1, p2)
    record_searches(p1['username'], p2['username'])
    record_match(p1['username'], p2['username'], result['score'])
    return jsonify({"player_1": p1, "player_2": p2, "match_result": result})

@app.route('/stats')
def stats():
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        now         = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        week_start  = (now - timedelta(days=7)).isoformat()

        def top_searched(where_clause='', params=()):
            return [dict(r) for r in con.execute(
                f'SELECT username, COUNT(*) as cnt FROM player_searches '
                f'{where_clause} GROUP BY LOWER(username) ORDER BY cnt DESC LIMIT 5',
                params
            ).fetchall()]

        leaderboard = {
            'today':   top_searched('WHERE searched_at >= ?', (today_start,)),
            'weekly':  top_searched('WHERE searched_at >= ?', (week_start,)),
            'alltime': top_searched(),
        }
        recent = [dict(r) for r in con.execute(
            'SELECT player1, player2, score, matched_at FROM matches ORDER BY matched_at DESC LIMIT 10'
        ).fetchall()]
        con.close()
        return jsonify({'leaderboard': leaderboard, 'recent_matches': recent})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/test-match')
def test_match():
    api_session = get_api_session()
    sr          = wareraapi.search_anything(search_text='test').execute(api_session)
    ids         = sr.get('userIds', [])
    if len(ids) < 2:
        return jsonify({"error": "Not enough players found"}), 500
    p1 = parse_user(wareraapi.user_get_user_lite(user_id=ids[0]).execute(api_session))
    p2 = parse_user(wareraapi.user_get_user_lite(user_id=ids[1]).execute(api_session))
    return jsonify({"player_1": p1, "player_2": p2, "match_result": get_loveera_match(p1, p2)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
