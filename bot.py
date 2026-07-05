import asyncio
import time
import os
import io
import json
import random
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
import motor.motor_asyncio 

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import BufferedInputFile, InputMediaPhoto

# --- Graphics Libraries ---
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import warnings
warnings.filterwarnings("ignore")

# ============================================
# Load environment variables
# ============================================
from dotenv import load_dotenv
import os

# Load .env file if exists (local development)
load_dotenv()

# ============================================
# Configuration (Fallback to environment variables)
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
OWNER_ID = os.getenv("OWNER_ID")
MONGO_URI = os.getenv("MONGO_URI")
USERNAME = os.getenv("BIGWIN_USERNAME", "959680090540")
PASSWORD = os.getenv("BIGWIN_PASSWORD", "Mitheint11")
AUTO_BET_ENABLED = os.getenv("AUTO_BET_ENABLED", "true").lower() == "true"
AUTO_BET_AMOUNT = int(os.getenv("AUTO_BET_AMOUNT", "100"))
AUTO_BET_MAX_PER_SESSION = int(os.getenv("AUTO_BET_MAX_PER_SESSION", "50"))
AUTO_BET_STOP_LOSS = int(os.getenv("AUTO_BET_STOP_LOSS", "-5000"))
AUTO_BET_PROFIT_TARGET = int(os.getenv("AUTO_BET_PROFIT_TARGET", "10000"))

# Check required variables
if not all([BOT_TOKEN, CHANNEL_ID, MONGO_URI, OWNER_ID]):
    print("❌ Error: Required environment variables missing!")
    print("Please set: BOT_TOKEN, CHANNEL_ID, MONGO_URI, OWNER_ID")
    # Don't exit, just print error

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# MongoDB Setup
db_client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
db = db_client['bigwin_database'] 
history_collection = db['game_history'] 
predictions_collection = db['predictions'] 
bet_history_collection = db['bet_history']  # Auto Bet History

# ==========================================
# 🔧 SYSTEM VARIABLES
# ==========================================
CURRENT_TOKEN = ""
LAST_PROCESSED_ISSUE = None
MAIN_MESSAGE_ID = None 
SESSION_START_ISSUE = None 
LAST_NOTIFIED_ISSUE = None 

# ==========================================
# 🎯 AUTO BET STATE
# ==========================================
auto_bet_state = {
    "is_running": False,
    "total_bets": 0,
    "wins": 0,
    "losses": 0,
    "profit": 0,
    "current_streak": 0,
    "last_bet_issue": None,
    "session_id": None
}

BASE_HEADERS = {
    'authority': 'api.bigwinqaz.com',
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json;charset=UTF-8',
    'origin': 'https://www.777bigwingame.app',
    'referer': 'https://www.777bigwingame.app/',
    'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36',
}

async def init_db():
    try:
        await history_collection.create_index("issue_number", unique=True)
        await predictions_collection.create_index("issue_number", unique=True)
        await bet_history_collection.create_index("issue_number", unique=True)
        print("🗄 MongoDB ချိတ်ဆက်မှု အောင်မြင်ပါသည်။")
    except Exception as e:
        pass

# ==========================================
# 🔑 API FUNCTIONS
# ==========================================
async def fetch_with_retry(session, url, headers, json_data, retries=1):
    for attempt in range(retries):
        try:
            async with session.post(url, headers=headers, json=json_data, timeout=3.0) as response:
                if response.status == 200:
                    return await response.json()
        except Exception:
            await asyncio.sleep(0.2)
    return None

async def login_and_get_token(session: aiohttp.ClientSession):
    global CURRENT_TOKEN
    json_data = {
        'username': USERNAME,
        'pwd': PASSWORD,
        'phonetype': 1,
        'logintype': 'mobile',
        'packId': '',
        'deviceId': '51ed4ee0f338a1bb24063ffdfcd31ce6',
        'language': 7,
        'random': '4fc4413428be43faa1a3f30d9745ae3a',
        'signature': '5458639AF428AC897FDFF1102D82EB9C',
        'timestamp': int(time.time()),
    }
    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/Login', BASE_HEADERS, json_data)
    if data and data.get('code') == 0:
        token_str = data.get('data', {}) if isinstance(data.get('data'), str) else data.get('data', {}).get('token', '')
        CURRENT_TOKEN = f"Bearer {token_str}"
        print("✅ Login အောင်မြင်ပါသည်။ Token အသစ် ရရှိပါပြီ။\n")
        return True
    return False

# ==========================================
# 🎯 AUTO BET FUNCTIONS
# ==========================================
async def place_bet(session: aiohttp.ClientSession, amount: int, prediction: str):
    """လောင်းကြေးထိုးခြင်း"""
    global CURRENT_TOKEN, auto_bet_state
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session):
            return None

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    # Prediction က BIG လား SMALL လား ဆုံးဖြတ်ပါ
    bet_value = "BIG" if "BIG" in prediction else "SMALL"
    
    json_data = {
        'gameType': 'wingo30s',
        'amount': amount,
        'betType': 'color',
        'betValue': bet_value,
        'issueNumber': str(int(LAST_PROCESSED_ISSUE) + 1) if LAST_PROCESSED_ISSUE else None,
        'timestamp': int(time.time()),
        'nonce': ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=16))
    }

    try:
        async with session.post('https://api.bigwinqaz.com/api/webapi/bet/place', 
                                headers=headers, json=json_data, timeout=5.0) as response:
            if response.status == 200:
                data = await response.json()
                return data
            else:
                print(f"❌ Bet failed: {response.status}")
                return None
    except Exception as e:
        print(f"❌ Bet error: {e}")
        return None

async def execute_auto_bet(session: aiohttp.ClientSession, prediction: str, issue_number: str):
    """Auto Bet ကို Execute လုပ်ခြင်း"""
    global auto_bet_state
    
    if not AUTO_BET_ENABLED:
        return
    
    if auto_bet_state["is_running"] and auto_bet_state["last_bet_issue"] == issue_number:
        return
    
    # Stop conditions
    if auto_bet_state["total_bets"] >= AUTO_BET_MAX_PER_SESSION:
        await bot.send_message(OWNER_ID, f"⏹ Auto Bet Stopped: Max bets reached ({AUTO_BET_MAX_PER_SESSION})")
        auto_bet_state["is_running"] = False
        return
    
    if auto_bet_state["profit"] <= AUTO_BET_STOP_LOSS:
        await bot.send_message(OWNER_ID, f"🛑 Auto Bet Stopped: Stop loss reached ({auto_bet_state['profit']})")
        auto_bet_state["is_running"] = False
        return
    
    if auto_bet_state["profit"] >= AUTO_BET_PROFIT_TARGET:
        await bot.send_message(OWNER_ID, f"🎯 Auto Bet Stopped: Profit target reached ({auto_bet_state['profit']})")
        auto_bet_state["is_running"] = False
        return
    
    # Calculate bet amount with Martingale
    current_streak = auto_bet_state["current_streak"]
    if current_streak >= 4:
        # Reset after 4 losses
        bet_amount = AUTO_BET_AMOUNT
    elif current_streak >= 3:
        bet_amount = AUTO_BET_AMOUNT * 8
    elif current_streak >= 2:
        bet_amount = AUTO_BET_AMOUNT * 4
    elif current_streak >= 1:
        bet_amount = AUTO_BET_AMOUNT * 2
    else:
        bet_amount = AUTO_BET_AMOUNT
    
    # Place bet
    result = await place_bet(session, bet_amount, prediction)
    
    if result and result.get('code') == 0:
        bet_data = result.get('data', {})
        win = bet_data.get('win', False)
        
        # Update state
        auto_bet_state["total_bets"] += 1
        auto_bet_state["last_bet_issue"] = issue_number
        
        if win:
            auto_bet_state["wins"] += 1
            auto_bet_state["profit"] += bet_amount
            auto_bet_state["current_streak"] = 0
            emoji = "🎉"
        else:
            auto_bet_state["losses"] += 1
            auto_bet_state["profit"] -= bet_amount
            auto_bet_state["current_streak"] += 1
            emoji = "😢"
        
        # Save bet history
        await bet_history_collection.update_one(
            {"issue_number": issue_number},
            {"$set": {
                "amount": bet_amount,
                "prediction": prediction,
                "win": win,
                "profit": auto_bet_state["profit"],
                "timestamp": datetime.now().isoformat()
            }},
            upsert=True
        )
        
        # Send notification to owner
        await bot.send_message(
            OWNER_ID,
            f"{emoji} <b>Auto Bet #{auto_bet_state['total_bets']}</b>\n"
            f"💰 Amount: {bet_amount}\n"
            f"📊 Prediction: {prediction}\n"
            f"📈 Result: {'WIN ✅' if win else 'LOSE ❌'}\n"
            f"📊 Total Profit: {auto_bet_state['profit']}\n"
            f"📉 Streak: {auto_bet_state['current_streak']}\n"
            f"🅿️ Issue: {issue_number}"
        )
        
        return True
    
    return False

# ==========================================
# 🧠 AI LOGIC (အရင်အတိုင်း)
# ==========================================
def dynamic_history_predict(history_docs):
    if len(history_docs) < 10:
        return "BIG (အကြီး) 🔴", 55.0, "⏳ Data စုဆောင်းဆဲ..."
        
    docs = list(reversed(history_docs))
    all_history = [d.get('size', 'BIG') for d in docs]
    
    predicted = "BIG (အကြီး) 🔴"
    base_prob = 55.0
    reason = "Pattern အသစ်ဖြစ်နေသဖြင့် သမိုင်းကြောင်းအရ တွက်ချက်ထားသည်"
    
    MAX_PATTERN_LENGTH = 10
    MIN_PATTERN_LENGTH = 9
    pattern_found = False
    
    for current_len in range(MAX_PATTERN_LENGTH, MIN_PATTERN_LENGTH - 1, -1):
        if len(all_history) > current_len:
            recent_pattern = all_history[-current_len:] 
            big_next_count = 0
            small_next_count = 0
            
            for i in range(len(all_history) - current_len):
                if all_history[i:i+current_len] == recent_pattern:
                    next_result = all_history[i+current_len] 
                    if next_result == 'BIG': big_next_count += 1
                    elif next_result == 'SMALL': small_next_count += 1
                        
            total_pattern_matches = big_next_count + small_next_count
            
            if total_pattern_matches > 0:
                big_prob = (big_next_count / total_pattern_matches) * 100
                small_prob = (small_next_count / total_pattern_matches) * 100
                pattern_str = "-".join(recent_pattern).replace('BIG', 'B').replace('SMALL', 'S')
                
                if big_prob > small_prob:
                    predicted = "BIG (အကြီး) 🔴"
                    base_prob = big_prob
                    reason = f"[{pattern_str}] လာလျှင် အကြီးဆက်ထွက်လေ့ရှိ၍"
                elif small_prob > big_prob:
                    predicted = "SMALL (အသေး) 🟢"
                    base_prob = small_prob
                    reason = f"[{pattern_str}] လာလျှင် အသေးဆက်ထွက်လေ့ရှိ၍"
                else:
                    predicted = "BIG (အကြီး) 🔴"
                    base_prob = 50.0
                    reason = f"[{pattern_str}] အရင်က မျှခြေထွက်ဖူး၍ အကြီးရွေးထားသည်"
                
                pattern_found = True
                break 
                
    if not pattern_found:
        b_count = all_history.count("BIG")
        s_count = all_history.count("SMALL")
        predicted = "BIG (အကြီး) 🔴" if s_count > b_count else "SMALL (အသေး) 🟢"
        base_prob = 55.0
        reason = "Pattern အသစ်ဖြစ်နေသဖြင့် အများစုထွက်မည့်ဘက်ကို ရွေးထားသည်"

    final_prob = min(round(base_prob, 1), 98.0) 
    return predicted, final_prob, reason

# ==========================================
# 🎨 GRAPH GENERATOR (အရင်အတိုင်း)
# ==========================================
def generate_winrate_chart(predictions):
    # (အရင်အတိုင်း ထားပါ)
    wins, losses = 0, 0
    bar_colors, dots_list, bar_heights = [], [], []
    history_wr = []
    
    latest_preds = list(reversed(predictions))[-20:]
    
    for i, p in enumerate(latest_preds): 
        current_played = i + 1
        
        if 'WIN' in p.get('win_lose', ''):
            wins += 1
            bar_colors.append('#00e5ff')  
            dots_list.append(('G', '#1de9b6'))
        else:
            losses += 1
            bar_colors.append('#ff4444')  
            dots_list.append(('R', '#ef5350'))
            
        current_wr = (wins / current_played) * 100
        bar_heights.append(current_wr) 
        history_wr.append(current_wr)
            
    total_played = wins + losses
    win_rate = int((wins / total_played * 100)) if total_played > 0 else 0

    fig = plt.figure(figsize=(10.24, 7.68), facecolor='#1c1f26') 
    
    fig.text(0.05, 0.90, "AI PERFORMANCE ANALYTICS", color='#ffffff', fontsize=32, fontweight='bold', ha='left')

    ax_circle = fig.add_axes([0.08, 0.42, 0.35, 0.40])
    ax_circle.set_axis_off()
    ax_circle.set_xlim(0, 1)
    ax_circle.set_ylim(0, 1)
    
    theta_bg = np.linspace(-1.25*np.pi, 0.25*np.pi, 200)
    ax_circle.plot(0.5 + 0.45*np.cos(theta_bg), 0.5 + 0.45*np.sin(theta_bg), color='#2c313c', linewidth=12)
    
    if win_rate > 0:
        end_angle = 0.25*np.pi - (win_rate/100) * 1.5 * np.pi
        theta_fg = np.linspace(0.25*np.pi, end_angle, 100)
        ax_circle.plot(0.5 + 0.45*np.cos(theta_fg), 0.5 + 0.45*np.sin(theta_fg), color='#00e5ff', linewidth=12)
        ax_circle.plot(0.5 + 0.45*np.cos(theta_fg), 0.5 + 0.45*np.sin(theta_fg), color='#00e5ff', linewidth=22, alpha=0.2)
            
    ax_circle.text(0.5, 0.75, f"{total_played}/20", color='#a3a8b5', fontsize=16, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.65, "TOTAL WINRATE", color='#7a8294', fontsize=12, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.48, f"{win_rate}%", color='#00e5ff', fontsize=65, fontweight='bold', ha='center', va='center')
    ax_circle.text(0.5, 0.32, "PREDICTIONS MADE", color='#7a8294', fontsize=12, fontweight='bold', ha='center', va='center')
    
    badge = patches.FancyBboxPatch((0.35, 0.16), 0.3, 0.08, boxstyle="round,pad=0.03", fc="#164e63", ec="#00e5ff", lw=1.5)
    ax_circle.add_patch(badge)
    ax_circle.text(0.5, 0.20, "FINALISED ✓", color='#00e5ff', fontsize=11, fontweight='bold', ha='center', va='center')
    
    ax_circle.text(0.05, 0.05, "0", color='#7a8294', fontsize=12, fontweight='bold', ha='center')
    ax_circle.text(0.95, 0.05, "100%", color='#7a8294', fontsize=12, fontweight='bold', ha='center')

    fig.text(0.74, 0.85, "SESSION PERFORMANCE TREND", color='#a3a8b5', fontsize=14, fontweight='bold', ha='center')
    fig.lines.extend([plt.Line2D([0.55, 0.93], [0.83, 0.83], color='#2c313c', lw=2, transform=fig.transFigure)])
    
    ax_bar = fig.add_axes([0.55, 0.47, 0.38, 0.33])
    ax_bar.set_facecolor('#1c1f26')
    ax_bar.set_xlim(-0.5, 19.5)
    ax_bar.set_ylim(0, 105) 
    
    ax_bar.spines['top'].set_visible(False)
    ax_bar.spines['right'].set_visible(False)
    ax_bar.spines['left'].set_visible(False)
    ax_bar.spines['bottom'].set_visible(False)
    
    ax_bar.set_yticks([0, 25, 50, 75, 100])
    ax_bar.set_yticklabels(['0%', '25%', '50%', '75%', '100%'], color='#7a8294', fontsize=10, fontweight='bold') 
    ax_bar.tick_params(axis='y', length=0, pad=5)
    ax_bar.grid(axis='y', color='#2c313c', linestyle='-', linewidth=1.5)
    
    if total_played > 0:
        x_pos = np.arange(total_played)
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.8, alpha=0.15, zorder=2, align='center')
        ax_bar.bar(x_pos, bar_heights, color=bar_colors, width=0.45, alpha=0.9, zorder=3, align='center')
        ax_bar.plot(x_pos, history_wr, color='#3b82f6', linewidth=2.5, marker='o', markersize=6, markerfacecolor='#1c1f26', markeredgecolor='#00e5ff', markeredgewidth=2, zorder=4)
        
    ax_bar.set_xticks(np.arange(20))
    ax_bar.set_xticklabels([str(i+1) for i in range(20)], color='#7a8294', fontsize=10)

    ax_win = fig.add_axes([0.05, 0.22, 0.28, 0.16])
    ax_win.set_axis_off()
    ax_win.set_xlim(0, 1)
    ax_win.set_ylim(0, 1)
    rect_win = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#1de9b6", ec="none")
    ax_win.add_patch(rect_win)
    ax_win.text(0.1, 0.75, "TOTAL WINS:", color='#004d40', fontsize=16, fontweight='bold', va='center')
    ax_win.text(0.1, 0.35, f"{wins}", color='#000000', fontsize=48, fontweight='bold', va='center')
    circ_win = plt.Circle((0.85, 0.5), 0.22, color='none', ec='#004d40', lw=3)
    ax_win.add_patch(circ_win)
    ax_win.text(0.85, 0.5, "✓", color='#004d40', fontsize=28, fontweight='bold', ha='center', va='center')

    ax_lose = fig.add_axes([0.35, 0.22, 0.28, 0.16])
    ax_lose.set_axis_off()
    ax_lose.set_xlim(0, 1)
    ax_lose.set_ylim(0, 1)
    rect_lose = patches.FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.1", fc="#ef5350", ec="none")
    ax_lose.add_patch(rect_lose)
    ax_lose.text(0.1, 0.75, "TOTAL LOSSES:", color='#4d0000', fontsize=16, fontweight='bold', va='center')
    ax_lose.text(0.1, 0.35, f"{losses}", color='#ffffff', fontsize=48, fontweight='bold', va='center')
    shield = patches.RegularPolygon((0.85, 0.5), numVertices=6, radius=0.25, orientation=np.pi/6, color='none', ec='#4d0000', lw=3)
    ax_lose.add_patch(shield)

    ax_wm = fig.add_axes([0.65, 0.22, 0.30, 0.16])
    ax_wm.set_axis_off()
    ax_wm.text(0.5, 0.5, "DEV - WANG LIN", color='#ffffff', fontsize=26, fontweight='bold', style='italic', ha='center', va='center')
    ax_wm.plot([0.1, 0.9], [0.30, 0.30], color='#ffffff', lw=3)
    ax_wm.plot([0.1, 0.9], [0.70, 0.70], color='#ffffff', lw=3)

    fig.text(0.05, 0.16, "FULL PREDICTION TIMELINE (Oldest to Latest)", color='#a3a8b5', fontsize=12, fontweight='bold', ha='left')
    
    ax_time = fig.add_axes([0.05, 0.05, 0.9, 0.08])
    ax_time.set_axis_off()
    ax_time.set_xlim(-0.5, 19.5)
    ax_time.set_ylim(0, 1)
    
    if len(dots_list) > 0:
        for i, (char, color) in enumerate(dots_list):
            ax_time.scatter(i, 0.5, s=800, c=color, edgecolors='none', zorder=4, alpha=0.3) 
            ax_time.scatter(i, 0.5, s=400, c=color, edgecolors='none', zorder=5, alpha=1.0)
            ax_time.text(i, 0.5, char, color='#ffffff', fontsize=14, fontweight='bold', ha='center', va='center', zorder=6)

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=100, facecolor='#1c1f26') 
    buf.seek(0)
    plt.close(fig)
    return buf

# ==========================================
# 🚀 CORE LOGIC (Auto Bet ပါ)
# ==========================================
async def check_game_and_predict(session: aiohttp.ClientSession):
    global CURRENT_TOKEN, LAST_PROCESSED_ISSUE, MAIN_MESSAGE_ID, SESSION_START_ISSUE
    global LAST_NOTIFIED_ISSUE, auto_bet_state
    
    if not CURRENT_TOKEN:
        if not await login_and_get_token(session): return False

    headers = BASE_HEADERS.copy()
    headers['authorization'] = CURRENT_TOKEN

    json_data = {
        'pageSize': 10, 'pageNo': 1, 'typeId': 30, 'language': 7,
        'random': '9ef85244056948ba8dcae7aee7758bf4', 
        'signature': '2EDB8C2B5264F62EC53116916A9EC05C',
        'timestamp': int(time.time()),
    }

    data = await fetch_with_retry(session, 'https://api.bigwinqaz.com/api/webapi/GetNoaverageEmerdList', headers, json_data)
    
    if data and data.get('code') == 0:
        records = data.get("data", {}).get("list", [])
        
        if records:
            latest_record = records[0]
            latest_issue = str(latest_record["issueNumber"])
            latest_number = int(latest_record["number"])
            latest_size = "BIG" if latest_number >= 5 else "SMALL"
            latest_parity = "EVEN" if latest_number % 2 == 0 else "ODD"
            
            is_new_issue = False
            if not LAST_PROCESSED_ISSUE:
                is_new_issue = True
            elif int(latest_issue) > int(LAST_PROCESSED_ISSUE):
                is_new_issue = True
            
            if is_new_issue:
                LAST_PROCESSED_ISSUE = latest_issue
                if not SESSION_START_ISSUE:
                    SESSION_START_ISSUE = latest_issue
                
                await history_collection.update_one(
                    {"issue_number": latest_issue}, 
                    {"$setOnInsert": {
                        "number": latest_number, "size": latest_size, 
                        "parity": latest_parity, "time_context": "CURRENT"
                    }}, upsert=True
                )
                
                pred_doc = await predictions_collection.find_one({"issue_number": latest_issue})
                if pred_doc and pred_doc.get("predicted_size"):
                    db_predicted_size = pred_doc.get("predicted_size")
                    clean_predicted = "BIG" if "BIG" in db_predicted_size else "SMALL"
                    is_win = (clean_predicted == latest_size)
                    win_lose_status = "WIN ✅" if is_win else "LOSE ❌"
                    await predictions_collection.update_one(
                        {"issue_number": latest_issue}, 
                        {"$set": {"actual_size": latest_size, "actual_number": latest_number, "win_lose": win_lose_status}}
                    )

                next_issue = str(int(latest_issue) + 1)
                
                current_session_count = await predictions_collection.count_documents({
                    "issue_number": {"$gte": SESSION_START_ISSUE}, 
                    "win_lose": {"$ne": None}
                })
                
                if current_session_count >= 20: 
                    SESSION_START_ISSUE = next_issue
                
                recent_preds_cursor = predictions_collection.find({"win_lose": {"$ne": None}}).sort("issue_number", -1).limit(15)
                recent_preds = await recent_preds_cursor.to_list(length=15)
                
                current_lose_streak = 0
                for p in recent_preds:
                    if p.get("win_lose") == "LOSE ❌":
                        current_lose_streak += 1
                    else: break

                # Alert System
                if current_lose_streak >= 5 and LAST_NOTIFIED_ISSUE != latest_issue:
                    try:
                        alert_text = (
                            f"🚨 <b>[SYSTEM ALERT] ကြီးမားသော ရှုံးပွဲဆက်မှု!</b>\n\n"
                            f"⚠️ လက်ရှိ ဆက်တိုက်ရှုံးပွဲ : <b>{current_lose_streak} ပွဲ</b> ❌\n"
                            f"🅿️ ပြီးခဲ့သော Period : <code>{latest_issue}</code>\n"
                            f"💡 စနစ်ကို ခေတ္တရပ်နားရန် (သို့) ပြန်လည်စစ်ဆေးရန် အကြံပြုပါသည်။"
                        )
                        await bot.send_message(chat_id=OWNER_ID, text=alert_text)
                        LAST_NOTIFIED_ISSUE = latest_issue 
                    except Exception as e:
                        pass

                cursor = history_collection.find().sort("issue_number", -1).limit(5000)
                history_docs = await cursor.to_list(length=5000)

                try:
                    mem_pred, mem_prob, mem_logic = await asyncio.to_thread(dynamic_history_predict, history_docs)
                    predicted = mem_pred
                    reason = mem_logic
                    final_prob = mem_prob
                except Exception as e:
                    predicted = "BIG (အကြီး) 🔴"
                    final_prob = 55.0
                    reason = "⚠️ AI Processing Error"
                
                predicted_result_db = "BIG" if "BIG" in predicted else "SMALL"
                await predictions_collection.update_one(
                    {"issue_number": next_issue}, 
                    {"$set": {"predicted_size": predicted_result_db}}, 
                    upsert=True
                )

                # ==========================================
                # 🎯 AUTO BET EXECUTE
                # ==========================================
                if AUTO_BET_ENABLED:
                    # Start auto bet if not running
                    if not auto_bet_state["is_running"]:
                        auto_bet_state["is_running"] = True
                        auto_bet_state["session_id"] = next_issue
                        await bot.send_message(
                            OWNER_ID,
                            f"🚀 <b>Auto Bet Started!</b>\n"
                            f"💰 Amount: {AUTO_BET_AMOUNT}\n"
                            f"🎯 Target Profit: {AUTO_BET_PROFIT_TARGET}\n"
                            f"🛑 Stop Loss: {AUTO_BET_STOP_LOSS}\n"
                            f"🔄 Max Bets: {AUTO_BET_MAX_PER_SESSION}"
                        )
                    
                    # Execute bet
                    await execute_auto_bet(session, predicted, next_issue)

                bet_advice = ""
                if current_lose_streak == 0: bet_advice = "💰 <b>လောင်းကြေး:</b> အခြေခံကြေး (1x)"
                elif current_lose_streak == 1: bet_advice = "💰 <b>လောင်းကြေး:</b> 2x (Martingale)"
                elif current_lose_streak == 2: bet_advice = "💰 <b>လောင်းကြေး:</b> 4x (Martingale)"
                elif current_lose_streak == 3: bet_advice = "💰 <b>လောင်းကြေး:</b> 8x (Martingale)"
                else: bet_advice = "⚠️ <b>[DANGER] ၄ ပွဲဆက်ရှုံးထားပါသည်!</b>\nခဏနားပါ (သို့) <b>1x မှ ပြန်စပါ။</b>"

                pred_cursor = predictions_collection.find({
                    "issue_number": {"$gte": SESSION_START_ISSUE},
                    "win_lose": {"$ne": None}
                }).sort("issue_number", -1)
                
                session_preds = await pred_cursor.to_list(length=20) 
                
                table_str = "<code>Period    | Result  | W/L\n"
                table_str += "----------|---------|----\n"
                for p in session_preds[:10]: 
                    iss = p.get('issue_number', '0000000')
                    iss_short = f"{iss[:3]}**{iss[-4:]}" 
                    act_size = p.get('actual_size', 'BIG')
                    act_num = p.get('actual_number', 0)
                    res_str = f"{act_num}-{act_size}"
                    wl_str = "✅" if "WIN" in p.get("win_lose", "") else "❌"
                    table_str += f"{iss_short:<10}| {res_str:<7} | {wl_str}\n"
                table_str += "</code>"

                img_buf = await asyncio.to_thread(generate_winrate_chart, session_preds)
                unique_filename = f"winrate_chart_{int(time.time())}.png"
                photo = BufferedInputFile(img_buf.read(), filename=unique_filename)
                
                sec_left = 30 - (int(time.time()) % 30)
                iss_display = f"{next_issue[:3]}**{next_issue[-4:]}"
                
                # Auto Bet Status
                bet_status = ""
                if AUTO_BET_ENABLED:
                    bet_status = (
                        f"\n━━━━━━━━━━━━━━━━━━\n"
                        f"🎯 <b>Auto Bet Status</b>\n"
                        f"💰 Profit: {auto_bet_state['profit']}\n"
                        f"📊 Bets: {auto_bet_state['total_bets']}\n"
                        f"📈 Wins: {auto_bet_state['wins']} | Losses: {auto_bet_state['losses']}\n"
                        f"📉 Streak: {auto_bet_state['current_streak']}\n"
                        f"🔄 Running: {'✅' if auto_bet_state['is_running'] else '❌'}"
                    )
                
                tg_caption = (
                    f"<b>🏆 WIN GO (30 SECONDS)</b>\n"
                    f"⏰ Next Result In: <b>{sec_left}s</b>\n\n"
                    f"{table_str}\n"
                    f"🅿️ <b>Period:</b> {iss_display}\n"
                    f"🤖 <b>AI Prediction : {predicted}</b>\n"
                    f"📈 <b>Probability : {final_prob}%</b>\n"
                    f"💡 <b>Reason :</b>\n"
                    f"{reason}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{bet_advice}"
                    f"{bet_status}"
                )
                
                if MAIN_MESSAGE_ID:
                    try:
                        media = InputMediaPhoto(media=photo, caption=tg_caption, parse_mode="HTML")
                        await bot.edit_message_media(chat_id=CHANNEL_ID, message_id=MAIN_MESSAGE_ID, media=media)
                    except Exception:
                        msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                        MAIN_MESSAGE_ID = msg.message_id
                else:
                    msg = await bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=tg_caption)
                    MAIN_MESSAGE_ID = msg.message_id
                
                return True 
        return False
        
    elif data and (data.get('code') == 401 or "token" in str(data.get('msg')).lower()): 
        CURRENT_TOKEN = ""
        return False

# ==========================================
# ⏱️ TIME TRIGGER SCHEDULER
# ==========================================
async def auto_broadcaster():
    await init_db() 
    async with aiohttp.ClientSession() as session:
        await login_and_get_token(session)
        while True:
            current_time = time.time()
            sec_passed = int(current_time) % 30
            
            if 5 <= sec_passed <= 28:
                try:
                    is_processed = await check_game_and_predict(session)
                    if is_processed:
                        sleep_time = 30 - (int(time.time()) % 30)
                        await asyncio.sleep(sleep_time)
                        continue 
                except Exception as e:
                    pass
            
            await asyncio.sleep(0.5)

# ==========================================
# 🤖 TELEGRAM COMMANDS
# ==========================================
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.reply(
        "👋 မင်္ဂလာပါ။\n\n"
        "🤖 <b>Auto Bet Bot</b>\n\n"
        "📋 <b>Commands:</b>\n"
        "/start - စတင်ရန်\n"
        "/status - Auto Bet အခြေအနေ\n"
        "/start_bet - Auto Bet စတင်ရန်\n"
        "/stop_bet - Auto Bet ရပ်ရန်\n"
        "/balance - လက်ကျန်ငွေစစ်ရန်\n"
        "/set_amount [amount] - လောင်းကြေးပမာဏ သတ်မှတ်ရန်\n"
        "/set_target [profit] - အမြတ်ပစ်မှတ် သတ်မှတ်ရန်\n"
        "/set_stoploss [loss] - ရပ်မည့်အရှုံး သတ်မှတ်ရန်"
    )

@dp.message(Command("status"))
async def show_status(message: types.Message):
    status_text = (
        f"📊 <b>Auto Bet Status</b>\n\n"
        f"🔄 Running: {'✅' if auto_bet_state['is_running'] else '❌'}\n"
        f"💰 Total Profit: {auto_bet_state['profit']}\n"
        f"📊 Total Bets: {auto_bet_state['total_bets']}\n"
        f"🎉 Wins: {auto_bet_state['wins']}\n"
        f"😢 Losses: {auto_bet_state['losses']}\n"
        f"📉 Current Streak: {auto_bet_state['current_streak']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚙️ <b>Settings</b>\n"
        f"💰 Bet Amount: {AUTO_BET_AMOUNT}\n"
        f"🎯 Target Profit: {AUTO_BET_PROFIT_TARGET}\n"
        f"🛑 Stop Loss: {AUTO_BET_STOP_LOSS}\n"
        f"🔄 Max Bets: {AUTO_BET_MAX_PER_SESSION}"
    )
    await message.reply(status_text)

@dp.message(Command("start_bet"))
async def start_bet_command(message: types.Message):
    global auto_bet_state
    if auto_bet_state["is_running"]:
        await message.reply("⚠️ Auto Bet က လက်ရှိအလုပ်လုပ်နေပါပြီ။")
        return
    
    auto_bet_state["is_running"] = True
    auto_bet_state["total_bets"] = 0
    auto_bet_state["wins"] = 0
    auto_bet_state["losses"] = 0
    auto_bet_state["profit"] = 0
    auto_bet_state["current_streak"] = 0
    
    await message.reply(
        f"🚀 <b>Auto Bet Started!</b>\n\n"
        f"💰 Amount: {AUTO_BET_AMOUNT}\n"
        f"🎯 Target: {AUTO_BET_PROFIT_TARGET}\n"
        f"🛑 Stop Loss: {AUTO_BET_STOP_LOSS}\n"
        f"🔄 Max Bets: {AUTO_BET_MAX_PER_SESSION}"
    )

@dp.message(Command("stop_bet"))
async def stop_bet_command(message: types.Message):
    global auto_bet_state
    auto_bet_state["is_running"] = False
    await message.reply("⏹ Auto Bet Stopped!")

@dp.message(Command("balance"))
async def check_balance(message: types.Message):
    async with aiohttp.ClientSession() as session:
        if not CURRENT_TOKEN:
            await login_and_get_token(session)
        
        headers = BASE_HEADERS.copy()
        headers['authorization'] = CURRENT_TOKEN
        
        try:
            async with session.get('https://api.bigwinqaz.com/api/webapi/user/balance', 
                                   headers=headers, timeout=5.0) as response:
                if response.status == 200:
                    data = await response.json()
                    balance = data.get('data', {}).get('balance', 'N/A')
                    await message.reply(f"💰 <b>Balance:</b> {balance}")
                else:
                    await message.reply("❌ Balance စစ်လို့မရပါ။")
        except Exception as e:
            await message.reply(f"❌ Error: {e}")

@dp.message(Command("set_amount"))
async def set_amount(message: types.Message):
    global AUTO_BET_AMOUNT
    try:
        amount = int(message.text.split()[1])
        if amount <= 0:
            await message.reply("❌ Amount က 0 ထက်ကြီးရပါမယ်။")
            return
        AUTO_BET_AMOUNT = amount
        await message.reply(f"✅ Bet amount set to: {amount}")
    except:
        await message.reply("❌ Usage: /set_amount [amount]")

@dp.message(Command("set_target"))
async def set_target(message: types.Message):
    global AUTO_BET_PROFIT_TARGET
    try:
        target = int(message.text.split()[1])
        if target <= 0:
            await message.reply("❌ Target က 0 ထက်ကြီးရပါမယ်။")
            return
        AUTO_BET_PROFIT_TARGET = target
        await message.reply(f"✅ Target profit set to: {target}")
    except:
        await message.reply("❌ Usage: /set_target [amount]")

@dp.message(Command("set_stoploss"))
async def set_stoploss(message: types.Message):
    global AUTO_BET_STOP_LOSS
    try:
        stoploss = int(message.text.split()[1])
        if stoploss >= 0:
            await message.reply("❌ Stop loss က အနှုတ်ဖြစ်ရပါမယ်။ (ဥပမာ -5000)")
            return
        AUTO_BET_STOP_LOSS = stoploss
        await message.reply(f"✅ Stop loss set to: {stoploss}")
    except:
        await message.reply("❌ Usage: /set_stoploss [amount]")

# ==========================================
# 🚀 MAIN
# ==========================================
async def main():
    print("🚀 Bigwin Bot (Auto Bet + AI Prediction) စတင်နေပါပြီ...\n")
    print(f"🎯 Auto Bet: {'✅ Enabled' if AUTO_BET_ENABLED else '❌ Disabled'}")
    print(f"💰 Bet Amount: {AUTO_BET_AMOUNT}")
    print(f"🎯 Target: {AUTO_BET_PROFIT_TARGET}")
    print(f"🛑 Stop Loss: {AUTO_BET_STOP_LOSS}")
    print(f"🔄 Max Bets: {AUTO_BET_MAX_PER_SESSION}\n")
    
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(auto_broadcaster())
    await dp.start_polling(bot)

if __name__ == '__main__':
    try: 
        asyncio.run(main())
    except KeyboardInterrupt: 
        print("Bot ကို ရပ်တန့်လိုက်ပါသည်။")
