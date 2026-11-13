cat << 'EOF' > ~/TelReper/bot.py
import os
import json
import shutil
import secrets
import asyncio
import threading
from datetime import datetime, timedelta
import pexpect
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

BOT_TOKEN = "9036110348:AAE6I4EGVEle6zCgJTKqKnH92wj5cgnPgWQ" 
OWNER_ID  = 8506802066
BASE_DIR  = os.path.expanduser("~/TelReper")
USERS_DIR = os.path.expanduser("~/TelReper_users")
DB_FILE   = os.path.expanduser("~/TelReper/keys.json")
os.makedirs(USERS_DIR, exist_ok=True)

login_sessions = {}
user_locks = {}
VALID_REASONS = ["spam", "fake_account", "violence", "child_abuse", "pornography", "geoirrelevant"]
PHOTO_URL = "https://i.ibb.co/68ZqXqz/m2m-bot.jpg" 

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f: 
            db = json.load(f)
            for uid in db.get("users", {}):
                if "history" not in db["users"][uid]: db["users"][uid]["history"] = []
            return db
    return {"users": {}}

def save_db(db):
    with open(DB_FILE, "w") as f: json.dump(db, f, indent=2)

def is_owner(uid): return OWNER_ID and uid == OWNER_ID

def user_dir(uid):
    p = os.path.join(USERS_DIR, str(uid))
    if not os.path.exists(p):
        os.makedirs(p, exist_ok=True)
    if not os.path.exists(os.path.join(p, "reper.py")):
        shutil.copy(os.path.join(BASE_DIR, "reper.py"), os.path.join(p, "reper.py"))
    return p

def get_user_sessions(uid):
    udir = os.path.join(USERS_DIR, str(uid))
    sessions = []
    if os.path.exists(udir):
        for root, dirs, files in os.walk(udir):
            for f in files:
                if f.endswith(".session") and os.path.getsize(os.path.join(root, f)) > 0:
                    sessions.append(f.replace(".session", ""))
    return sessions

def get_sessions_count(uid): return len(get_user_sessions(uid))

def get_total_sessions():
    total = 0
    for root, dirs, files in os.walk(USERS_DIR):
        total += sum(1 for f in files if f.endswith(".session"))
    return total

def get_lock(uid):
    if uid not in user_locks: user_locks[uid] = asyncio.Lock()
    return user_locks[uid]

def status_line(uid):
    db = load_db()
    u = db["users"].get(str(uid))
    if not u: return None
    expires = datetime.fromisoformat(u["expires"])
    remaining = u["max_reports"] - u["used_reports"]
    return {"active": expires > datetime.now() and remaining > 0, "key": u["key"], "expires": expires.strftime("%Y-%m-%d %H:%M"), "days_left": max(0, (expires - datetime.now()).days), "used": u["used_reports"], "max": u["max_reports"], "remaining": max(0, remaining)}

async def start(update, context):
    uid = update.effective_user.id
    s = status_line(uid)
    if not s: return await update.message.reply_text("❌ Aapke paas koi active key nahi hai. Owner se contact karein.")
    
    caption = (
        f"👑 Owner - @ntx_p4pa\n\n"
        f"📱 *Live IDs Logged In:* `{get_sessions_count(uid)}`\n"
        f"🌐 *Total IDs (All Users):* `{get_total_sessions()}`\n\n"
        f"🚀 *Your Reports Sent:* `{s['used']}`\n"
        f"📉 *Your Reports Remaining:* `{s['remaining']}`"
    )
    keyboard = [
        [InlineKeyboardButton("👤 My Accounts", callback_data='my_accounts'), InlineKeyboardButton("📜 My History", callback_data='my_history')],
        [InlineKeyboardButton("🧹 Clean Sessions (Logout)", callback_data='clean_sessions')],
        [InlineKeyboardButton("👑 Owner Panel", callback_data='owner_panel')] if is_owner(uid) else []
    ]
    keyboard = [row for row in keyboard if row]
    
    try: await update.message.reply_photo(photo=PHOTO_URL, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    except: await update.message.reply_text(caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_handler(update, context):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    s = status_line(uid)
    
    if query.data == 'start_menu':
        caption = (
            f"👑 Owner - @ntx_p4pa\n\n"
            f"📱 *Live IDs Logged In:* `{get_sessions_count(uid)}`\n"
            f"🌐 *Total IDs (All Users):* `{get_total_sessions()}`\n\n"
            f"🚀 *Your Reports Sent:* `{s['used'] if s else 0}`\n"
            f"📉 *Your Reports Remaining:* `{s['remaining'] if s else 0}`"
        )
        keyboard = [
            [InlineKeyboardButton("👤 My Accounts", callback_data='my_accounts'), InlineKeyboardButton("📜 My History", callback_data='my_history')],
            [InlineKeyboardButton("🧹 Clean Sessions (Logout)", callback_data='clean_sessions')],
            [InlineKeyboardButton("👑 Owner Panel", callback_data='owner_panel')] if is_owner(uid) else []
        ]
        keyboard = [row for row in keyboard if row]
        await query.edit_message_caption(caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == 'my_accounts':
        sessions = get_user_sessions(uid)
        txt = "❌ Aapne abhi tak koi ID login nahi ki hai.\n\nType karein: `/login +91XXXXXXXXXX`" if not sessions else "👤 *Aapki Logged In IDs:*\n\n" + "\n".join([f"✅ `{session}`" for session in sessions])
        await query.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='start_menu')]]))
        
    elif query.data == 'my_history':
        db = load_db(); u = db['users'].get(str(uid))
        lines = [f"📌 `{h['target']}` | {h['reason']} | {h['count']} | {h['date']}" for h in u.get('history', [])[-10:]] if u else []
        txt = "📜 *Aapki Last 10 Reports*\n\n" + "\n".join(lines) if lines else "📜 Aapne abhi tak koi report nahi bheji."
        await query.message.reply_text(txt, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='start_menu')]]))

    elif query.data == 'clean_sessions':
        udir = os.path.join(USERS_DIR, str(uid))
        if os.path.exists(udir):
            for root, dirs, files in os.walk(udir, topdown=False):
                for f in files:
                    if f.endswith(".session"): os.remove(os.path.join(root, f))
        await query.message.reply_text("🧹 *Saare accounts logout ho gaye!*\n\nAb `/login +91...` se naya account add karein.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='start_menu')]]))

    elif query.data == 'owner_panel':
        if not is_owner(uid): return await query.message.reply_text("❌ Sirf Owner use kar sakta hai.")
        keyboard = [
            [InlineKeyboardButton("📊 Live Stats", callback_data='admin_stats'), InlineKeyboardButton("👥 Access List", callback_data='admin_users')],
            [InlineKeyboardButton("📢 Global History", callback_data='admin_channels')],
            [InlineKeyboardButton("⬅️ Back", callback_data='start_menu')]
        ]
        await query.edit_message_caption(caption="👑 *Owner Panel*\n\nYahan se aap saari IDs, Reports aur Access control kar sakte hain.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        
    elif query.data == 'admin_stats':
        if not is_owner(uid): return
        db = load_db()
        total_users = len(db['users'])
        total_reports = sum(u.get('used_reports', 0) for u in db['users'].values())
        active_users = sum(1 for u in db['users'].values() if datetime.fromisoformat(u['expires']) > datetime.now() and u['used_reports'] < u['max_reports'])
        text = f"📊 *Live Statistics*\n\n👥 Total Users: `{total_users}`\n✅ Active Users: `{active_users}`\n📱 Total IDs Logged In: `{get_total_sessions()}`\n🚀 Total Reports Sent: `{total_reports}`"
        await query.edit_message_caption(caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='owner_panel')]]))
        
    elif query.data == 'admin_users':
        if not is_owner(uid): return
        db = load_db()
        lines = []
        for u_id, u in db['users'].items():
            rem = u['max_reports'] - u['used_reports']
            mark = "✅" if datetime.fromisoformat(u['expires']) > datetime.now() and rem > 0 else "❌"
            lines.append(f"{mark} `{u_id}` | {get_sessions_count(u_id)} IDs | Used: {u['used_reports']} | Rem: {rem}")
        text = "👥 *Access List*\n\n" + ("\n".join(lines) if lines else "No users found.")
        await query.edit_message_caption(caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='owner_panel')]]))

    elif query.data == 'admin_channels':
        if not is_owner(uid): return
        db = load_db()
        lines = []
        for u_id, u in db['users'].items():
            for h in u.get('history', [])[-3:]:
                lines.append(f"`{h['target']}` | {h['reason']} | {h['count']} | {h['date']}")
        text = "📢 *Global Report History*\n\n" + ("\n".join(lines[-15:]) if lines else "No history found.")
        await query.edit_message_caption(caption=text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data='owner_panel')]]))

async def addkey(update, context):
    if not is_owner(update.effective_user.id): return
    if len(context.args) < 3: return await update.message.reply_text("Format: `/addkey <uid> <days> <max>`")
    try: uid, days, max_r = str(int(context.args[0])), int(context.args[1]), int(context.args[2])
    except: return await update.message.reply_text("Galat number.")
    db = load_db(); key = secrets.token_hex(8).upper(); expires = (datetime.now() + timedelta(days=days)).isoformat()
    db["users"][uid] = {"key": key, "expires": expires, "max_reports": max_r, "used_reports": 0, "phone": None, "history": []}
    save_db(db)
    await update.message.reply_text(f"✅ Key: `{key}`\nUser: `{uid}`\nDays: `{days}`\nReports: `{max_r}`", parse_mode="Markdown")

async def delkey(update, context):
    if not is_owner(update.effective_user.id): return
    if not context.args: return await update.message.reply_text("Format: `/delkey <uid>`")
    db = load_db()
    if context.args[0] in db["users"]: del db["users"][context.args[0]]; save_db(db); await update.message.reply_text("✅ User hataya.")

async def adddays(update, context):
    if not is_owner(update.effective_user.id): return
    db = load_db(); uid = context.args[0]
    if uid not in db["users"]: return await update.message.reply_text("Nahi mila.")
    old = datetime.fromisoformat(db["users"][uid]["expires"]); new = max(old, datetime.now()) + timedelta(days=int(context.args[1]))
    db["users"][uid]["expires"] = new.isoformat(); save_db(db); await update.message.reply_text(f"✅ Naya expiry: `{new.strftime('%Y-%m-%d %H:%M')}`", parse_mode="Markdown")

async def addreports(update, context):
    if not is_owner(update.effective_user.id): return
    db = load_db(); uid = context.args[0]
    if uid not in db["users"]: return await update.message.reply_text("Nahi mila.")
    db["users"][uid]["max_reports"] += int(context.args[1]); save_db(db); await update.message.reply_text(f"✅ Naya max: `{db['users'][uid]['max_reports']}`", parse_mode="Markdown")

async def login(update, context):
    uid = update.effective_user.id; s = status_line(uid)
    if not s or not s["active"]: return await update.message.reply_text("❌ Active key nahi.")
    if not context.args or not context.args[0].startswith("+"): return await update.message.reply_text("Format: `/login +91...`")
    phone = context.args[0]; udir = user_dir(uid)
    await update.message.reply_text(f"⏳ `{phone}` add ho raha...", parse_mode="Markdown")
    loop = asyncio.get_running_loop()
    def worker():
        try:
            child = pexpect.spawn(f"python3 reper.py -an {phone}", cwd=udir, timeout=180, encoding="utf-8", codec_errors="ignore")
            login_sessions[uid] = {"child": child, "stage": "waiting", "phone": phone}
            idx = child.expect([r"(?i)enter the code you received", r"(?i)enter your password", r"(?i)successfully|logged in|added", pexpect.EOF, pexpect.TIMEOUT], timeout=60)
            if idx == 0:
                login_sessions[uid]["stage"] = "otp"
                asyncio.run_coroutine_threadsafe(update.message.reply_text("📩 OTP: `/otp 12345`", parse_mode="Markdown"), loop)
            elif idx == 1:
                login_sessions[uid]["stage"] = "2fa"
                asyncio.run_coroutine_threadsafe(update.message.reply_text("🔐 2FA: `/2fa pass`", parse_mode="Markdown"), loop)
            elif idx == 2:
                login_sessions.pop(uid, None)
                asyncio.run_coroutine_threadsafe(update.message.reply_text("✅ Logged in!"), loop)
            else:
                login_sessions.pop(uid, None)
                asyncio.run_coroutine_threadsafe(update.message.reply_text(f"❌ Fail.\n```\n{child.before[-400:]}\n```", parse_mode="Markdown"), loop)
        except Exception as e: asyncio.run_coroutine_threadsafe(update.message.reply_text(f"❌ `{e}`", parse_mode="Markdown"), loop)
    threading.Thread(target=worker, daemon=True).start()

async def otp_handler(update, context):
    uid = update.effective_user.id; sess = login_sessions.get(uid)
    if not sess or sess["stage"] != "otp": return await update.message.reply_text("Pehle `/login`.")
    if not context.args: return await update.message.reply_text("Format: `/otp 12345`")
    await update.message.reply_text("⏳ OTP check...")
    loop = asyncio.get_running_loop(); child = sess["child"]
    def worker():
        try:
            child.sendline(context.args[0])
            idx = child.expect([r"(?i)enter your password", r"(?i)successfully|logged in|added", r"(?i)invalid", pexpect.EOF, pexpect.TIMEOUT], timeout=60)
            if idx == 0:
                sess["stage"] = "2fa"
                asyncio.run_coroutine_threadsafe(update.message.reply_text("🔐 2FA: `/2fa pass`", parse_mode="Markdown"), loop)
            elif idx == 1:
                login_sessions.pop(uid, None)
                asyncio.run_coroutine_threadsafe(update.message.reply_text("✅ Logged in!"), loop)
            else:
                login_sessions.pop(uid, None)
                asyncio.run_coroutine_threadsafe(update.message.reply_text(f"❌ OTP fail.\n```\n{child.before[-400:]}\n```", parse_mode="Markdown"), loop)
        except Exception as e: asyncio.run_coroutine_threadsafe(update.message.reply_text(f"❌ `{e}`", parse_mode="Markdown"), loop)
    threading.Thread(target=worker, daemon=True).start()

async def twofa_handler(update, context):
    uid = update.effective_user.id; sess = login_sessions.get(uid)
    if not sess or sess["stage"] != "2fa": return await update.message.reply_text("Pehle `/login`.")
    if not context.args: return await update.message.reply_text("Format: `/2fa pass`")
    await update.message.reply_text("⏳ 2FA Check...")
    loop = asyncio.get_running_loop(); child = sess["child"]
    def worker():
        try:
            child.sendline(" ".join(context.args))
            idx = child.expect([r"(?i)successfully|logged in|added", r"(?i)password", pexpect.EOF, pexpect.TIMEOUT], timeout=60)
            login_sessions.pop(uid, None)
            if idx == 0:
                asyncio.run_coroutine_threadsafe(update.message.reply_text("✅ Logged in!"), loop)
            else:
                udir = os.path.join(USERS_DIR, str(uid))
                for root, dirs, files in os.walk(udir):
                    for f in files:
                        if f.endswith(".session"): os.remove(os.path.join(root, f))
                asyncio.run_coroutine_threadsafe(update.message.reply_text("❌ Galat 2FA Password. Session delete kar diya gaya. Dobara `/login` karein."), loop)
        except Exception as e: asyncio.run_coroutine_threadsafe(update.message.reply_text(f"❌ `{e}`", parse_mode="Markdown"), loop)
    threading.Thread(target=worker, daemon=True).start()

async def report(update, context):
    uid = update.effective_user.id; s = status_line(uid)
    if not s or not s["active"]: return await update.message.reply_text("❌ Active key nahi.")
    if len(context.args) < 3: return await update.message.reply_text("Format: `/report @channel spam 50`")
    target, reason, count = context.args[0], context.args[1].lower(), context.args[2]
    if reason not in VALID_REASONS: return await update.message.reply_text("Galat reason.")
    try: count_int = int(count); assert count_int > 0
    except: return await update.message.reply_text("Galat count.")
    if count_int > s["remaining"]: return await update.message.reply_text(f"❌ Sirf `{s['remaining']}` rem.")
    
    udir = os.path.join(USERS_DIR, str(uid))
    if get_sessions_count(uid) == 0: return await update.message.reply_text("Pehle `/login` aur `/otp` complete karo.")
    lock = get_lock(uid)
    if lock.locked(): return await update.message.reply_text("⏳ Pehli report chal rahi hai, wait.")
    
    async with lock:
        msg = await update.message.reply_text(f"⏳ Reporting `{count_int}` (10 per sec)...", parse_mode="Markdown")
        sent_so_far = 0
        while sent_so_far < count_int:
            current_chunk = min(10, count_int - sent_so_far)
            proc = await asyncio.create_subprocess_exec("python3", "reper.py", "-r", str(current_chunk), "-t", target, "-m", reason, cwd=udir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            out = (stdout.decode() or stderr.decode() or "")
            
            if "channelinvalid" in out.lower() or "channelprivate" in out.lower():
                await msg.edit_text(f"🛑 **Channel Banned/Invalid!**", parse_mode="Markdown")
                if OWNER_ID:
                    try: await context.bot.send_message(OWNER_ID, f"🚨 *BAN ALERT*\n\nChannel: `{target}`\nUser: `{uid}`\nStatus: Banned/Invalid\n\nReporting rok di gayi hai.", parse_mode="Markdown")
                    except: pass
                return
                
            if "please enter your phone" in out.lower():
                await msg.edit_text("⚠️ **Account Limit Reached ya Session Kharab hai!**\n\nKripya `/start` pe jayen aur **🧹 Clean Sessions** pe click karke naya `/login` karein.", parse_mode="Markdown")
                return
                
            sent_so_far += current_chunk
            db = load_db()
            db["users"][str(uid)]["used_reports"] += current_chunk
            db["users"][str(uid)]["history"].append({"target": target, "reason": reason, "count": current_chunk, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
            save_db(db)
            
            await msg.edit_text(f"⏳ Reporting... `{sent_so_far}/{count_int}` done.", parse_mode="Markdown")
            if sent_so_far < count_int: await asyncio.sleep(1)
                
        await msg.edit_text(f"✅ Done! `{count_int}` reports successfully sent.", parse_mode="Markdown")

async def logout(update, context):
    uid = update.effective_user.id; udir = os.path.join(USERS_DIR, str(uid))
    if os.path.exists(udir):
        shutil.rmtree(udir, ignore_errors=True)
        os.makedirs(udir, exist_ok=True)
        shutil.copy(os.path.join(BASE_DIR, "reper.py"), os.path.join(udir, "reper.py"))
    login_sessions.pop(uid, None)
    await update.message.reply_text("✅ Saare accounts logout ho gaye (Data clear).")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    for cmd, fn in [("addkey", addkey), ("delkey", delkey), ("adddays", adddays), ("addreports", addreports), ("login", login), ("otp", otp_handler), ("2fa", twofa_handler), ("report", report), ("logout", logout)]:
        app.add_handler(CommandHandler(cmd, fn))
    print("🤖 Bot chal raha hai...")
    app.run_polling()

if __name__ == "__main__":
    main()
EOF