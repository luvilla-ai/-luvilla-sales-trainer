import os
import logging
from anthropic import Anthropic
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")
DANIEL_CHAT_ID = os.environ.get("DANIEL_CHAT_ID", "")

client = Anthropic(api_key=ANTHROPIC_KEY)

SYSTEM_PROMPT = """You are roleplaying as a wealthy Vancouver luxury property owner for a Luvilla sales training simulation.

YOUR PERSONA:
- Own a luxury vacant property worth $8M–$20M in Vancouver
- Busy, successful, skeptical but not hostile
- Care about: protecting your asset, reliable income, NO hassle, trusting who you work with
- You speak naturally — not like a script

LUVILLA DEAL STRUCTURE:
- Option A: Owner covers furnishing/setup costs → Owner earns 75% of net revenue (Luvilla prefers this)
- Option B: Luvilla covers all setup costs → Owner earns 60% of net revenue
- Luvilla handles everything: guests, cleaning, maintenance, insurance, platform management

REALISTIC OBJECTIONS YOU USE (rotate and mix naturally):
- "What happens if my property gets damaged?"
- "How much money can I actually make?"
- "Is this even legal in Vancouver?"
- "Why should I trust Luvilla? I've never heard of you."
- "I already have a property manager."
- "I don't want strangers in my home."
- "What are your fees exactly?"
- "How long is the contract?"
- "What if I want to sell the property?"
- "Can you guarantee occupancy?"
- "I need to think about it."
- "Send me something in writing first."

BEHAVIOR RULES:
- Start COLD. Short. Guarded. "Who is this?"
- Warm up ONLY if rep gives confident, specific, data-driven answers
- Push back HARD on vague or weak answers
- Ask 1–2 objections per message max
- Keep responses 2–4 sentences
- Be human — vary your tone, don't repeat the same objections

After EVERY owner response, add a feedback block separated by |||:
SCORE: X/10
✅ WORKED: [what the rep did well in 1 sentence]
❌ IMPROVE: [what was weak in 1 sentence]
💡 TIP: [1 specific actionable tip for next message]"""

SCRIPT_TEXT = """
📋 *LUVILLA REVENUE SHARE — PITCH SCRIPT*

━━━━━━━━━━━━━━━━━━━━━━
*① 오프닝 — 첫 10초가 전부*
━━━━━━━━━━━━━━━━━━━━━━
• "Hi, is this [Name]? This is [Your Name] from Luvilla."
• "I'll be quick — I help luxury property owners generate passive income from vacant properties. No tenants, no hassle."
• "Do you have 3 minutes? I think this might interest you."

🇰🇷 "안녕하세요, [오너이름] 맞으시죠? Luvilla의 [이름]입니다."
🇰🇷 "짧게 말씀드릴게요 — 공실 럭셔리 자산으로 패시브 인컴 만들어드립니다. 세입자 없이요."
🇰🇷 "3분만 시간 되세요?"

━━━━━━━━━━━━━━━━━━━━━━
*② 핵심 피치 — 숫자로 말해라*
━━━━━━━━━━━━━━━━━━━━━━
• "We operate luxury short-term rentals. You earn while doing absolutely nothing."
• "Revenue split: you keep 75%, we take 25%. That's it."
• "A 5-bed Vancouver property typically generates CA$20,000–$40,000 gross per month."
• "We handle everything — guests, cleaning, maintenance, insurance, platforms."

🇰🇷 수익 배분: 오너님 75%, 저희 25%
🇰🇷 밴쿠버 5베드 기준 월 CA$2만–$4만 그로스

━━━━━━━━━━━━━━━━━━━━━━
*③ Option A 설명 — 메인 딜*
━━━━━━━━━━━━━━━━━━━━━━
• "Option A: You cover setup & furnishing. You keep 75% net revenue."
• "Setup runs CA$30K–$80K depending on size. ROI is typically under 3 months."
• "This is the better deal long-term — 75% compounds fast."

⚠️ Option B (Luvilla 자금 부담 → 오너 60%)는 오너가 자금 없을 때만 꺼내라

━━━━━━━━━━━━━━━━━━━━━━
*④ Objection — 자산 보호*
━━━━━━━━━━━━━━━━━━━━━━
• "We carry $2M liability insurance on every property."
• "Dedicated PM does full inspection after every single checkout."
• "Airbnb Host Guarantee covers up to $3M USD separately."
• "We've operated [X] properties with zero major damage claims."

━━━━━━━━━━━━━━━━━━━━━━
*⑤ Objection — 수익/리스크*
━━━━━━━━━━━━━━━━━━━━━━
• "Can't guarantee exact numbers, but our average occupancy is 75–80%."
• "Let me pull a revenue projection for your specific property — 10 minutes."
• "Comparable properties nearby generate CA$X/month. Happy to share the data."

━━━━━━━━━━━━━━━━━━━━━━
*⑥ Objection — 합법성/신뢰*
━━━━━━━━━━━━━━━━━━━━━━
• "100% compliant with Vancouver STR regulations — licensed and registered."
• "I can connect you with one of our current property owners as a reference."
• "We currently manage [X] properties in Vancouver. Here's our portfolio."

━━━━━━━━━━━━━━━━━━━━━━
*⑦ 클로징 — 미팅만 잡아라*
━━━━━━━━━━━━━━━━━━━━━━
• "All I need is 30 minutes. I'll bring a full revenue projection for your property."
• "No commitment needed. Just look at the numbers first."
• "Would Tuesday or Thursday work better?"
• "I can send a quick overview first if you'd prefer to read before we meet."

🔑 결정 요구하지 마라. 다음 단계(미팅)만 요청해라.
"""

# Store per-user conversation history
user_sessions = {}

def get_session(user_id):
    if user_id not in user_sessions:
        user_sessions[user_id] = {"history": [], "scores": []}
    return user_sessions[user_id]

async def notify_daniel(context, user, text):
    """Send log to Daniel if DANIEL_CHAT_ID is set"""
    if DANIEL_CHAT_ID:
        try:
            msg = f"📊 *Sales Session Log*\n👤 {user.first_name} (@{user.username})\n\n{text[:500]}"
            await context.bot.send_message(chat_id=DANIEL_CHAT_ID, text=msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Failed to notify Daniel: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = {"history": [], "scores": []}

    welcome = (
        "🏛️ *LUVILLA Sales Trainer*\n\n"
        "AI가 밴쿠버 $10M+ 오너 역할을 합니다.\n"
        "Revenue Share Option A 계약을 따오세요.\n\n"
        "📋 /script — 피치 스크립트 보기\n"
        "🔄 /reset — 새 시뮬레이션 시작\n"
        "📊 /score — 현재 평균 점수\n\n"
        "메시지 보내면 시뮬레이션 시작됩니다. 👇"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")

    # Auto-start simulation
    session = get_session(user_id)
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "Start now. You just picked up the phone. Introduce yourself as the owner. Be brief and guarded. 2 sentences max."}]
    )
    raw = response.content[0].text
    owner_msg, _ = parse_feedback(raw)
    session["history"].append({"role": "assistant", "content": raw})
    await update.message.reply_text(f"🏠 *Owner:*\n{owner_msg}", parse_mode="Markdown")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_sessions[user_id] = {"history": [], "scores": []}
    await update.message.reply_text("🔄 새 시뮬레이션 시작합니다...", parse_mode="Markdown")

    session = get_session(user_id)
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": "Start now. You just picked up the phone. Introduce yourself as the owner. Be brief and guarded. 2 sentences max."}]
    )
    raw = response.content[0].text
    owner_msg, _ = parse_feedback(raw)
    session["history"].append({"role": "assistant", "content": raw})
    await update.message.reply_text(f"🏠 *Owner:*\n{owner_msg}", parse_mode="Markdown")

async def script(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(SCRIPT_TEXT, parse_mode="Markdown")

async def score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    session = get_session(user_id)
    scores = session.get("scores", [])
    if not scores:
        await update.message.reply_text("아직 점수가 없어요. 연습을 시작하세요!")
        return
    avg = sum(scores) / len(scores)
    best = max(scores)
    latest = scores[-1]
    emoji = "🟢" if avg >= 8 else "🟡" if avg >= 6 else "🔴"
    msg = (
        f"📊 *Score Summary*\n\n"
        f"{emoji} 평균: *{avg:.1f}/10*\n"
        f"🏆 최고: *{best}/10*\n"
        f"📍 최근: *{latest}/10*\n"
        f"🔢 총 연습: *{len(scores)}회*"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

def parse_feedback(text):
    parts = text.split("|||")
    owner_msg = parts[0].strip()
    feedback = None
    if len(parts) > 1:
        fb = parts[1].strip()
        lines = fb.split("\n")
        feedback = {"raw": fb, "score": None}
        for line in lines:
            if line.startswith("SCORE:"):
                try:
                    feedback["score"] = int(line.replace("SCORE:", "").strip().split("/")[0])
                except:
                    pass
    return owner_msg, feedback

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = update.effective_user
    user_text = update.message.text
    session = get_session(user_id)

    # If no history, auto-start
    if not session["history"]:
        await start(update, context)
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Build history
    history = [{"role": "user", "content": "Start now. You just picked up the phone. Introduce yourself as the owner. Be brief and guarded. 2 sentences max."}]
    for msg in session["history"]:
        history.append(msg)
    history.append({"role": "user", "content": user_text})

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=history
        )
        raw = response.content[0].text
        owner_msg, feedback = parse_feedback(raw)

        # Add to history
        session["history"].append({"role": "user", "content": user_text})
        session["history"].append({"role": "assistant", "content": raw})

        # Keep history manageable
        if len(session["history"]) > 20:
            session["history"] = session["history"][-20:]

        # Send owner response
        await update.message.reply_text(f"🏠 *Owner:*\n{owner_msg}", parse_mode="Markdown")

        # Send feedback
        if feedback and feedback.get("raw"):
            score_val = feedback.get("score")
            if score_val:
                session["scores"].append(score_val)
                emoji = "🟢" if score_val >= 8 else "🟡" if score_val >= 6 else "🔴"
                avg = sum(session["scores"]) / len(session["scores"])
                fb_text = f"{emoji} *{score_val}/10* (평균 {avg:.1f})\n\n{feedback['raw']}"
            else:
                fb_text = feedback["raw"]
            await update.message.reply_text(fb_text, parse_mode="Markdown")

        # Notify Daniel
        log_text = f"Rep: {user_text}\nOwner: {owner_msg}"
        await notify_daniel(context, user, log_text)

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text("⚠️ 오류가 발생했어요. /reset 으로 다시 시작해주세요.")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("script", script))
    app.add_handler(CommandHandler("score", score))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Luvilla Sales Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
