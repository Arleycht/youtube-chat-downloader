import argparse
import json
import requests
import time

from datetime import datetime
from pathlib import Path

import ytchat as ytc


def live_record(chat: ytc.Chat, output_path: Path):
    print(f"[{datetime.now()}] Started live chat recording")

    last_new_chat_time = time.time()
    is_stale = False
    STALE_TIME = 120

    DT = 1

    while True:
        try:
            new_history = chat.fetch()

            if len(new_history) > 0:
                if is_stale:
                    print(f"{len(new_history)} new chat messages after going stale")

                last_new_chat_time = time.time()
                is_stale = False
            elif time.time() - last_new_chat_time > STALE_TIME and not is_stale:
                is_stale = True

                # Warn user that the chat is going stale, which could be a slow chat or
                # a bug within this program.
                print(f"No new chats have been seen for over {STALE_TIME} seconds")

            chat.write_history(output_path)

            time.sleep(DT)
        except Exception as e:
            print(f"Encountered exception: {e}")
            print(f"[{datetime.now()}] Breaking out of loop after exception")
            break

    print(f"Stopped live chat recording at {datetime.now()}")


def main():
    parser = argparse.ArgumentParser(description="YouTube Live Chat Recorder")
    parser.add_argument("url", help="YouTube live stream URL")
    parser.add_argument(
        "-o", "--output", help="Output file name (default: <live_id>.json)"
    )

    args = parser.parse_args()

    chat = ytc.Chat(args.url)

    output_path = args.output if args.output else f"{chat.options.live_id}.json"

    if Path(output_path).exists():
        print(f"Loading existing history from {output_path}")

        does_history_intersect, new_chat_count = chat.load_history(output_path)
        latest_timestamp_usec = ytc.get_timestamp_usec(chat.history[-1])

        print(
            f"Found previous data that ended at [{datetime.fromtimestamp(latest_timestamp_usec / 1_000_000)}]"
        )

        if does_history_intersect:
            print(f"[{datetime.now()}] Added {new_chat_count} new chats")
        else:
            print(
                "\033[93mWARNING: All chat history from the server is newer, meaning there might be missed messages in between recovered data and current data!\033[0m"
            )

    if chat.options.is_replay:
        print("Stream is offline")
        raise NotImplemented("Replay and live chat history merging")
    else:
        live_record(chat, output_path)


if __name__ == "__main__":
    main()
