from collections import defaultdict
from datetime import datetime, timedelta

# Store user actions and timestamps
rate_limit_dict = defaultdict(list)

def rate_limit(user_id: int, limit: int, time_window: int) -> bool:
    """
    Rate limits user actions.
    
    :param user_id: Telegram user ID
    :param limit: Maximum allowed actions in the time window
    :param time_window: Time window in seconds
    :return: True if the user exceeds the rate limit, False otherwise
    """
    current_time = datetime.now()
    user_actions = rate_limit_dict[user_id]

    # Remove old actions outside the time window
    rate_limit_dict[user_id] = [time for time in user_actions if current_time - time < timedelta(seconds=time_window)]

    # Check if the user exceeds the limit
    if len(rate_limit_dict[user_id]) >= limit:
        return True

    # Log the new action
    rate_limit_dict[user_id].append(current_time)
    return False
