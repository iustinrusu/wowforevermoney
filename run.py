"""Start WoW Forever Money: python run.py [--port 8765] [--no-browser] [--no-update]"""
import argparse
import os
import sys

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='WoW Forever gold-making assistant')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true', help="don't open the page automatically")
    ap.add_argument('--no-update', action='store_true', help="don't pull the latest version first")
    args = ap.parse_args()
    # update first (setting auto_update, on by default): new code -> start again on it, once
    from wfm.settings import Settings
    if not args.no_update and Settings().snapshot().get('auto_update', True) and not os.environ.get('WFM_UPDATED'):
        from wfm.updater import update
        changed, what = update()
        print(f'Update check: {what}', flush=True)
        if changed:          # run the new code (a child process: on Windows exec would end start.bat's wait early)
            import subprocess
            sys.exit(subprocess.call([sys.executable] + sys.argv, env={**os.environ, 'WFM_UPDATED': '1'}))
    from wfm.app import main
    main(port=args.port, open_browser=not args.no_browser)
