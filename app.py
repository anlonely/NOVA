"""Compatibility entrypoint for the Discord bilingual NOVA build.

The legacy Tk interface was removed with the extra scenes and channels. Keep
`python app.py` working by forwarding to the current Web/Qt dashboard.
"""

from desktop_webview import main


if __name__ == "__main__":
    main()
