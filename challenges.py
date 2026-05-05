"""Weekly 7-Powers challenge — one power per day, Sunday-first (Israeli week)."""
import datetime

POWERS = {
    0: {"emoji": "💧", "name_he": "כוח המים",
        "task_he": "לשתות 6 כוסות מים. צלמי את הבקבוק שלך."},
    1: {"emoji": "🌈", "name_he": "כוח הצבעים",
        "task_he": "3 צבעים שונים בצלחת אחת היום."},
    2: {"emoji": "🏃", "name_he": "כוח התנועה",
        "task_he": "20 דקות תנועה כיפית — ריקוד, חבל, הליכה."},
    3: {"emoji": "🧘", "name_he": "כוח הרגש",
        "task_he": "לפני שאת אוכלת — תשאלי: רעבה? משועממת? עצובה?"},
    4: {"emoji": "🍽️", "name_he": "כוח הקשב",
        "task_he": "ארוחה אחת בלי מסך, עם לעיסה אטית."},
    5: {"emoji": "💤", "name_he": "כוח השינה",
        "task_he": "ניסיון לישון 9 שעות. כיבוי מסכים שעה לפני."},
    6: {"emoji": "💝", "name_he": "כוח הבחירה",
        "task_he": "פינוק אחד, באהבה — לא בהסתר."},
}


def today_power_index() -> int:
    """0=Sunday, ..., 6=Saturday (Israeli week)."""
    return (datetime.date.today().weekday() + 1) % 7
