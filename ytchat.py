import json
import re
import requests
from pathlib import Path
from typing import Any, Dict


class ChatOptions:
    def __init__(self):
        self.api_key: str = ""
        self.client_version: str = ""
        self.continuation: str = ""
        self.is_replay: bool = False
        self.live_id: str = ""


class ChatAction:
    def __init__(self):
        """
        "authorBadges",
        "authorExternalChannelId",
        "authorName",
        "authorPhoto",
        "id",
        "message",
        "timestampUsec",
        """

        self.action_type = "addChatItemAction"
        self.item_type = "liveChatTextMessageRenderer"

        self.id = ""
        self.timestamp_usec = 0

        self.author_external_channel_id = ""
        self.author_name = ""
        self.author_badges = ""
        self.author_photo = ""

        self.message = ""


class Chat:
    def __init__(self, stream_url: str):
        response = requests.get(stream_url)
        response.raise_for_status()

        data = response.text
        options = get_options_from_live_page(data)

        self.history = []
        self.options = options
        self.dirty = True

    def _raw_fetch(self) -> list[Any]:
        """
        Fetch without history modification
        """

        new_history, continuation = fetch_chat(self.options)
        self.options.continuation = continuation

        return new_history

    def fetch(self) -> list[Any]:
        new_history = self._raw_fetch()
        self.history += new_history

        return new_history

    def load_history(self, file: str | Path):
        """
        Load previous chat history from a file and updates history with new chats.

        Returns if the loaded history and current history intersected and the amount of new chats added.
        """

        with open(file, "r") as f:
            self.history = json.load(f)

        current_history = self._raw_fetch()

        latest_timestamp_usec = get_timestamp_usec(self.history[-1])
        new_history = [
            x for x in current_history if get_timestamp_usec(x) > latest_timestamp_usec
        ]

        self.history += new_history

        return len(current_history) > len(new_history), len(new_history)

    def write_history(self, file: str):
        with open(file, "w") as f:
            json.dump(self.history, f, indent=4)


def get_timestamp_usec(raw_entry):
    return int(
        raw_entry["addChatItemAction"]["item"]["liveChatTextMessageRenderer"][
            "timestampUsec"
        ]
    )


def get_options_from_live_page(data: str) -> ChatOptions:
    # Get live ID
    id_match = re.search(
        r'<link rel="canonical" href="https://www.youtube.com/watch\?v=(.+?)">', data
    )
    if not id_match:
        raise ValueError("Live Stream was not found")

    live_id = id_match.group(1)

    # Check if replay
    replay_match = re.search(r'"isReplay":\s*(true)', data)
    is_replay = replay_match is not None
    # if replay_match:
    #     raise ValueError(f"{live_id} is finished live")

    # Get API key
    key_match = re.search(r'"INNERTUBE_API_KEY":\s*"(.+?)"', data)
    if not key_match:
        raise ValueError("API Key was not found")

    api_key = key_match.group(1)

    # Get client version
    ver_match = re.search(r'"clientVersion":\s*"([\d.]+?)"', data)
    if not ver_match:
        raise ValueError("Client Version was not found")

    client_version = ver_match.group(1)

    # Get continuation
    continuation_match = re.search(r'"continuation":\s*"(.+?)"', data)
    if not continuation_match:
        raise ValueError("Continuation was not found")

    continuation = continuation_match.group(1)

    options = ChatOptions()
    options.live_id = live_id
    options.is_replay = is_replay
    options.api_key = api_key
    options.client_version = client_version
    options.continuation = continuation

    return options


def strip_tracking(obj):
    if isinstance(obj, dict):
        return {
            k: strip_tracking(v)
            for k, v in obj.items()
            if "tracking" not in str(k).lower()
        }
    elif isinstance(obj, list):
        return [strip_tracking(x) for x in obj]
    else:
        return obj


def strip_actions(actions_dict: Dict[str, Any]):
    result = {}

    if "addChatItemAction" in actions_dict:
        chat_item = actions_dict["addChatItemAction"]["item"]

        if "liveChatTextMessageRenderer" in chat_item:
            chat_message_renderer = chat_item["liveChatTextMessageRenderer"]

            chat_keys = [
                "authorBadges",
                "authorExternalChannelId",
                "authorName",
                "authorPhoto",
                "id",
                "message",
                "timestampUsec",
            ]

            result["addChatItemAction"] = {
                "item": {
                    "liveChatTextMessageRenderer": {
                        k: v for k, v in chat_message_renderer.items() if k in chat_keys
                    }
                }
            }

    if "addLiveChatTickerItemAction" in actions_dict:
        print("Not implemented: Strip superchat")

    # if "removeChatItemByAuthorAction" in actions_dict:
    #     print("Not implemented: removeChatItemByAuthorAction")

    # if "replaceChatItemAction" in actions_dict:
    #     print("Not implemented: replaceChatItemAction")

    return result


def convert(actions_obj) -> list[ChatAction]:
    actions = []

    for action_name, item in actions_obj.items():
        if action_name == "addChatItemAction":
            renderer = item.get("liveChatTextMessageRenderer", {})

            if renderer:
                chat_action = ChatAction()

                chat_action.action_type = "addChatItemAction"
                chat_action.item_type = "liveChatTextMessageRenderer"

                chat_action.id = renderer["id"]
                chat_action.timestamp_usec = get_timestamp_usec(actions_obj)

                chat_action.author_external_channel_id = renderer[
                    "authorExternalChannelId"
                ]

                chat_action.author_name = renderer["authorName"]
                chat_action.author_badges = renderer["authorBadges"]
                chat_action.author_photo = renderer["authorPhoto"]

                chat_action.message = renderer["message"]["simpleText"]

                actions.append(chat_action)

    return actions


def fetch_raw(options: ChatOptions):
    url = f"https://www.youtube.com/youtubei/v1/live_chat/get_live_chat?key={options.api_key}"

    response = requests.post(
        url,
        json={
            "context": {
                "client": {
                    "clientVersion": options.client_version,
                    "clientName": "WEB",
                },
            },
            "continuation": options.continuation,
        },
    )
    response.raise_for_status()

    response = response.json()
    raw_history = []

    if (
        response.get("continuationContents", {})
        .get("liveChatContinuation", {})
        .get("actions")
    ):
        raw_history = strip_tracking(
            response["continuationContents"]["liveChatContinuation"]["actions"]
        )

    return response, raw_history


def fetch_chat(options: ChatOptions) -> tuple[list[Any], str]:
    response, raw_history = fetch_raw(options)

    if (
        response.get("continuationContents", {})
        .get("liveChatContinuation", {})
        .get("actions")
    ):
        raw_history = strip_tracking(
            response["continuationContents"]["liveChatContinuation"]["actions"]
        )

    continuation_data = (
        response.get("continuationContents", {})
        .get("liveChatContinuation", {})
        .get("continuations", [{}])[0]
    )

    new_continuation = ""

    if continuation_data.get("invalidationContinuationData"):
        new_continuation = continuation_data["invalidationContinuationData"][
            "continuation"
        ]
    elif continuation_data.get("timedContinuationData"):
        new_continuation = continuation_data["timedContinuationData"]["continuation"]

    # with open(f"{options.live_id}_raw.json", "w") as f:
    #     json.dump(response, f, indent=4)

    stripped_history = []

    for action in raw_history:
        try:
            stripped_action = strip_actions(action)

            if len(stripped_action.keys()) > 0:
                stripped_history.append(stripped_action)
        except Exception as e:
            print(action)
            print("Unknown exception")

    # with open(f"{options.live_id}.json", "w") as f:
    #     json.dump(stripped_history, f, indent=4)

    return stripped_history, new_continuation
