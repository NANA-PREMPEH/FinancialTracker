PROJECT_TYPE_OPTIONS = (
    ("Business", "Business"),
    ("Investments", "Investments"),
    ("Partnerships", "Partnerships"),
    ("Shareholding", "Shareholding"),
    ("Other", "Other"),
)


def is_project_category_name(category_name):
    return "project" in (category_name or "").strip().lower()


def is_project_category(category):
    return bool(category and is_project_category_name(getattr(category, "name", None)))


def normalize_project_type(project_type):
    cleaned_project_type = (project_type or "").strip()
    if not cleaned_project_type:
        return None

    allowed_project_types = {
        option_value.lower(): option_value for option_value, _ in PROJECT_TYPE_OPTIONS
    }
    return allowed_project_types.get(cleaned_project_type.lower())
