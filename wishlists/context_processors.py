import datetime

from django.conf import settings

SEASONS = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
           6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}


def site(request):
    return {
        "allow_signup": settings.ALLOW_SIGNUP,
        # Pages without their own list theme follow the season
        "season_theme": SEASONS[datetime.date.today().month],
    }
