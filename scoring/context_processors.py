from .models import Course


def course_analytics_courses(request):
    """Provide courses for the shared course analytics navigation menu."""
    return {
        "course_analytics_courses": Course.objects.only("name", "slug").order_by(
            "name"
        )
    }
