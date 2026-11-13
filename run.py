"""Start WoW Forever Money: python run.py [--port 8765] [--no-browser]"""
import argparse

from wfm.app import main

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='WoW Forever gold-making assistant')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true', help="don't open the page automatically")
    args = ap.parse_args()
    main(port=args.port, open_browser=not args.no_browser)
