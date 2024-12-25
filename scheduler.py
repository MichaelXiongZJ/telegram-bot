from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application, CallbackContext
from handlers import kick_inactive_members

def schedule_jobs(application: Application) -> None:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(kick_inactive_members, 'interval', days=1, args=[application])
    scheduler.start()

async def kick_inactive_members(context: CallbackContext) -> None:
    now = datetime.now()
    for user_id, last_active in list(user_activity.items()):
        if (now - last_active) > timedelta(days=30) and user_id not in whitelisted_users:
            await context.bot.ban_chat_member(CHAT_ID, user_id)
