from .bot import build_app


def main():
    app = build_app()
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
