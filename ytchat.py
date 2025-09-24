import re
import requests
from typing import Dict, Any


class ChatOptions:
    def __init__(self):
        self.live_id: str = ""
        self.is_replay: bool = False
        self.api_key: str = ""
        self.client_version: str = ""
        self.continuation: str = ""


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


def fetch_chat(options: ChatOptions):
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

    data = response.json()

    raw_history = []

    if (
        data.get("continuationContents", {})
        .get("liveChatContinuation", {})
        .get("actions")
    ):
        raw_history = strip_tracking(
            response.json()["continuationContents"]["liveChatContinuation"]["actions"]
        )

    continuation_data = (
        response.json()
        .get("continuationContents", {})
        .get("liveChatContinuation", {})
        .get("continuations", [{}])[0]
    )

    continuation = ""

    if continuation_data.get("invalidationContinuationData"):
        continuation = continuation_data["invalidationContinuationData"]["continuation"]
    elif continuation_data.get("timedContinuationData"):
        continuation = continuation_data["timedContinuationData"]["continuation"]

    # with open(f"{options.live_id}_raw.json", "w") as f:
    #     json.dump(response.json(), f, indent=4)

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

    return stripped_history, continuation
