import argparse
import json
import requests
import time

from datetime import datetime
from pathlib import Path

import ytchat as ytc


def main():
    parser = argparse.ArgumentParser(description="YouTube Live Chat Recorder")
    parser.add_argument("url", help="YouTube live stream URL")
    parser.add_argument(
        "-o", "--output", help="Output file name (default: <live_id>.json)"
    )

    args = parser.parse_args()

    response = requests.get(args.url)
    response.raise_for_status()

    data = response.text
    options = ytc.get_options_from_live_page(data)

    output_file = args.output if args.output else f"{options.live_id}.json"

    history = []
    latest_time_usec = 0

    if Path(output_file).exists():
        print(f"Loading existing history from {output_file}")

        with open(output_file, "r") as f:
            history = json.load(f)

        for entry in history:
            timestamp_usec = int(
                entry["addChatItemAction"]["item"]["liveChatTextMessageRenderer"][
                    "timestampUsec"
                ]
            )

            latest_time_usec = max(timestamp_usec, latest_time_usec)

        recovered_timestamp = datetime.fromtimestamp(latest_time_usec / 1_000_000)
        print(f"Found previous data that ended at [{recovered_timestamp}]")

    print(f"[{datetime.now()}] Started")

    while True:
        try:
            new_history, new_continuation = ytc.fetch_chat(options)
            options.continuation = new_continuation

            if latest_time_usec > 0:
                # Chat position recovery

                appended_count = 0

                for entry in new_history:
                    timestamp_usec = int(
                        entry["addChatItemAction"]["item"][
                            "liveChatTextMessageRenderer"
                        ]["timestampUsec"]
                    )

                    if timestamp_usec > latest_time_usec:
                        history.append(entry)
                        appended_count += 1

                if appended_count == len(new_history):
                    print(
                        "\033[93mWARNING: All chat history from the server is newer, meaning there might be missed messages in between recovered data and current data!\033[0m"
                    )
                else:
                    print(
                        f"[{datetime.now()}] Skipped {len(new_history) - appended_count} existing chats, added {appended_count} new chats"
                    )

                latest_time_usec = 0
            elif len(new_history) > 0:
                history += new_history

                # print(f"[{datetime.now()}] Appended {len(new_history)} new messages")

            with open(output_file, "w") as f:
                json.dump(history, f, indent=4)

            time.sleep(1)
        except Exception as e:
            print(e)
            print(f"[{datetime.now()}] Breaking out of loop after exception")
            break

    print(f"Stopped at time {datetime.now()}")


if __name__ == "__main__":
    main()
