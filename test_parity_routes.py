from app import create_app
from app.models import User


app = create_app()
app.config["TESTING"] = True


def run():
    parity_routes = [
        "/",
        "/transactions",
        "/budget",
        "/goals",
        "/debts",
        "/investments/",
        "/analytics",
        "/reports",
        "/calendar",
        "/cash-flow",
        "/net-worth",
        "/fixed-assets",
        "/recurring-transactions",
        "/smc",
        "/global-finance",
        "/commitments",
        "/construction-works",
        "/accounting",
        "/insurance",
        "/tax-center",
        "/ai-insights",
        "/automation",
        "/banking",
        "/security",
        "/backup",
        "/api-keys",
        "/ml-training",
        "/metrics",
        "/settings",
        "/admin",
    ]

    with app.test_client() as client:
        with app.app_context():
            user = User.query.first()
            if not user:
                raise RuntimeError("No users found in database for route parity test.")

        with client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)
            sess["_fresh"] = True

        lines = []
        for route in parity_routes:
            try:
                response = client.get(route, follow_redirects=False)
                lines.append(f"{route} -> {response.status_code}")
            except Exception as exc:  # pragma: no cover
                lines.append(f"{route} -> ERROR: {type(exc).__name__}: {exc}")

        with open("parity_routes_output.txt", "w", encoding="utf-8") as file:
            file.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    run()
